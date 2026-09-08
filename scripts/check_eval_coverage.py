#!/usr/bin/env python3
"""Eval 커버리지·기준선 드리프트 가드 (W-018 / S1).

시나리오 디렉토리 집합과 baseline의 (agent, scenario) 집합을 양방향 대조하고,
티어1 에이전트의 최소 시나리오 보유 여부를 검사한다.

`scripts/verify-done.sh` 신설 §와 `.github/workflows/validate.yml`이 **둘 다 이
스크립트를 호출**한다. 로직을 bash/CI에 각각 두면 반드시 드리프트한다(F-023,
`check_doc_counts.py`와 동일 관례) — 정의와 검사 전부를 여기 한 곳에만 둔다.

정책(대상 티어·임계값·기준선 포인터)의 단일 소스는 `evals/policy.json`이다.
숫자·목록을 이 스크립트에 하드코딩하지 않는다.

시나리오 발견 로직(디렉토리 스킵 규칙 포함)은 `evals/run.py::discover_scenario_dirs`를
그대로 재사용한다 — 여기서 별도로 재구현하면 스킵 목록이 갈라질 수 있다.

exit 0 = 커버리지 정합 (tier1/tier2 경고, 분류 미등재 경고는 있을 수 있음, policy로
         fail 승격 전까지)
exit 1 = 시나리오⊄기준선 / 기준선⊄시나리오 / baseline.file 부재·파싱 실패 /
         policy.json 부재·파싱 실패 / (승격 시) tier1 미달 / tiers.tier2 부재·빈 배열 /
         (승격 시) tier2 미달 / (승격 시) 분류 완전성 미달

W-024(티어2 커버리지 갭 봉쇄): `evals/policy.json`의 `_tier2Rationale`이 "티어2는
경고 수준으로 다룬다"고 주장했으나 이 스크립트에 문자열 'tier2'가 한 번도 나오지
않아 경고조차 구현돼 있지 않았다 — `consensus-builder`가 tiers.tier2(A등급)에
등재된 채 시나리오 없이 조용히 통과한 원인. check_tier2/check_classification_complete
두 검사로 메운다. 상세: docs/specs/2026-09-04-eval-tier2-coverage-gate.md (D-3).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

OK = "\033[32m✓\033[0m"
NG = "\033[31m✗\033[0m"
WARN = "\033[33m!\033[0m"


class PolicyError(Exception):
    """policy.json 스키마 위반 — main이 exit 1과 명확한 메시지로 변환한다.

    scripts/build-targets.py의 PolicyError 관례를 그대로 따른다. 이 레포에서
    SSOT/정책 로더마다 서로 다른 예외 관례를 쓰는 것 자체가 부채라는 W-019
    교차 리뷰(Medium) 지적을 반영했다.
    """


def validate_policy_schema(policy: object) -> dict:
    """필수 섹션이 통째로 없거나 형태가 틀리면 명확히 실패한다.

    "검사할 대상이 0개"를 "통과"로 오인하는 게 이 검사의 존재 이유를 무력화하는
    거짓 green이다 — sanddab의 W-019 교차 리뷰가 실측으로 잡았다: evals/policy.json
    에서 'tiers' 키를 지우면 check_eval_coverage.py가 "tier1 전 에이전트(0종) 최소
    시나리오 보유"로 exit 0을 냈다. D1(gate.tier1CoverageEnforceFail 승격)이 막으려던
    것과 정확히 같은 클래스의 결함이 검사 대상 선정 단계에서 재발한 것이다.

    구분 원칙: **섹션 자체(tiers/gate/coverage)가 통째로 없으면** 정책 파일이
    손상됐거나 잘못 편집된 것이므로 즉시 실패한다. 반면 섹션은 있는데 그 **안의
    개별 키**(예: gate.tier1CoverageEnforceFail)가 없는 것은 단계적 롤아웃 중
    정상 상태일 수 있어(예: S1~S3에서 이 플래그가 존재하지 않다가 S4에서 추가됐다)
    안전한 기본값(False = 아직 미승격)을 유지한다 — 이 함수는 그 개별 키까지
    강제하지 않는다.
    """
    if not isinstance(policy, dict):
        raise PolicyError(
            f"policy.json 최상위가 object가 아니다 (실제 타입: {type(policy).__name__})"
        )
    tiers = policy.get("tiers")
    if not isinstance(tiers, dict):
        raise PolicyError("policy.json: 'tiers' 섹션이 없거나 object가 아니다")
    tier1 = tiers.get("tier1")
    if not isinstance(tier1, list) or not tier1:
        raise PolicyError(
            "policy.json: 'tiers.tier1'이 없거나 빈 배열이다 — "
            "검사 대상 0개를 전부 통과로 오인하는 거짓 green을 막기 위해 거부한다"
        )
    if not all(isinstance(a, str) and a for a in tier1):
        raise PolicyError(
            "policy.json: 'tiers.tier1'의 각 원소는 비어있지 않은 문자열이어야 한다"
        )
    if not isinstance(policy.get("gate"), dict):
        raise PolicyError("policy.json: 'gate' 섹션이 없거나 object가 아니다")
    if not isinstance(policy.get("coverage"), dict):
        raise PolicyError("policy.json: 'coverage' 섹션이 없거나 object가 아니다")
    return policy


def _load_run_module(root: Path) -> ModuleType:
    """`evals/run.py`를 경로 기반으로 로드한다(패키지 임포트에 기대지 않음 —
    `--root`로 가짜 레포를 가리킬 때도 그 레포의 run.py를 쓰게 하기 위함,
    scripts/tests/test_eval_forge.py와 동일 관례)."""
    run_py = root / "evals" / "run.py"
    spec = importlib.util.spec_from_file_location("_ckkit_eval_run", run_py)
    if spec is None or spec.loader is None:
        raise ImportError(f"evals/run.py 로드 실패: {run_py}")
    mod = importlib.util.module_from_spec(spec)
    # exec 전에 sys.modules 등록 필요 — run.py의 @dataclass가 클래스 소속 모듈을
    # sys.modules에서 찾는데, 미등록 상태면 3.10+에서 AttributeError로 죽는다.
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(spec.name, None)
    return mod


def load_policy(root: Path) -> dict:
    return json.loads((root / "evals" / "policy.json").read_text(encoding="utf-8"))


def _resolve_in_repo(
    container_root: Path, rel_path: str
) -> tuple[Path | None, str | None]:
    """`rel_path`(정책 파일의 문자열)를 `container_root` 안으로만 한정해 해석한다.

    `container_root / rel_path`는 `rel_path`가 절대경로면 `container_root`를 버리고
    `rel_path` 그대로가 된다(pathlib의 문서화된 동작). `..`나 심링크로도 트리 밖으로
    나갈 수 있다 — 셋 다 `resolve()` 한 번으로 정규화한 뒤 `container_root` 하위인지
    대조하면 전부 같은 검사로 잡힌다.

    `scripts/build-targets.py::_resolve_in_repo`와 **동일한 관례**이자 **동일한
    시그니처**다(W-019 교차 리뷰 후속, sanddab 실측 — daggertooth의 `baseline.file`도
    정확히 같은 클래스로 경로 탈출됐다: 절대경로를 주면 레포 밖 파일을 기준선으로
    신뢰해 green을 냈다). 이 결함이 반복되는 이유가 관례 부재였으므로, 새로 발명하지
    않고 그대로 이식했다. 호출자는 이 결과(Path)를 그대로 재사용해야 한다 — 다시
    조합하면 검증한 값과 실제로 읽는 값이 달라질 수 있다(TOCTOU).

    구현은 합치지 않는다(D-15: 구현은 여러 벌, 계약만 하나). 공유 적대적 케이스 표는
    `scripts/tests/resolve_in_repo_contract.py` — 두 구현을 같은 표로 검증한다.
    """
    real = (container_root / rel_path).resolve()
    try:
        real.relative_to(container_root.resolve())
    except ValueError:
        return None, f"허용된 디렉토리 밖을 가리킨다 → {real}"
    return real, None


def current_scenarios(root: Path) -> set[tuple[str, str]]:
    run_mod = _load_run_module(root)
    dirs = run_mod.discover_scenario_dirs(root / "evals" / "scenarios")
    return {(d.parent.name, d.name) for d in dirs}


def baseline_scenarios(
    root: Path, policy: dict
) -> tuple[set[tuple[str, str]], list[str]]:
    """baseline.file이 가리키는 파일을 읽어 (agent,scenario) 집합을 돌려준다.
    실패 시 빈 집합 + 에러 메시지 목록 — **조용한 skip 금지**(fail-closed)."""
    errors: list[str] = []
    fname = policy.get("baseline", {}).get("file")
    if not fname:
        errors.append("evals/policy.json: baseline.file 없음")
        return set(), errors
    baseline_dir = root / "evals" / "baseline"
    p, escape_error = _resolve_in_repo(baseline_dir, fname)
    if p is None:
        errors.append(f"baseline.file 경로 탈출 차단 — {fname}: {escape_error}")
        return set(), errors
    if not p.is_file():
        errors.append(f"baseline 파일 없음 — evals/baseline/{fname}")
        return set(), errors
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"baseline 파일 파싱 실패 — evals/baseline/{fname} ({e})")
        return set(), errors
    results = data.get("results")
    if not isinstance(results, list):
        errors.append(f"baseline 파일 스키마 오류 — 'results' 배열 없음: {p}")
        return set(), errors
    pairs = set()
    for i, r in enumerate(results):
        if not isinstance(r, dict) or "agent" not in r or "scenario" not in r:
            errors.append(f"baseline results[{i}] — agent/scenario 없음: {p}")
            continue
        pairs.add((r["agent"], r["scenario"]))
    return pairs, errors


def check_coverage(root: Path, policy: dict) -> tuple[bool, list[str]]:
    lines: list[str] = []
    baseline_set, errs = baseline_scenarios(root, policy)
    if errs:
        return False, [f"{NG} {e}" for e in errs]

    scenario_set = current_scenarios(root)
    gate = policy.get("gate", {})
    ok = True

    if gate.get("requireBaselineCoversAllScenarios", True):
        extra = scenario_set - baseline_set
        if extra:
            ok = False
            lines.append(
                f"{NG} 기준선에 없는 시나리오(⊄ baseline, 회귀 판정 불가): "
                f"{sorted(f'{a}/{s}' for a, s in extra)}"
            )
        else:
            lines.append(f"{OK} 모든 시나리오 디렉토리가 기준선에 존재")

    if gate.get("requireScenariosCoverBaseline", True):
        missing = baseline_set - scenario_set
        if missing:
            ok = False
            lines.append(
                f"{NG} 기준선에만 있고 시나리오 디렉토리가 사라짐: "
                f"{sorted(f'{a}/{s}' for a, s in missing)}"
            )
        else:
            lines.append(f"{OK} 기준선의 모든 항목이 시나리오 디렉토리로 존재")

    return ok, lines


def check_tier1(root: Path, policy: dict) -> tuple[bool, list[str]]:
    """티어1 각 에이전트가 최소 시나리오를 보유하는지 검사.

    S1에서는 `gate.tier1CoverageEnforceFail`이 false면 미달을 경고로만 출력하고
    전체 판정에는 반영하지 않는다(9종이 아직 비어 있어 영구 red가 되는 것을 피함).
    S4에서 이 플래그를 true로 올리면 동일 코드가 fail로 승격된다(policy 플래그 —
    코드 변경 불필요, decision-log D1).
    """
    lines: list[str] = []
    tier1 = policy.get("tiers", {}).get("tier1", [])
    min_n = policy.get("coverage", {}).get("tier1MinScenariosPerAgent", 1)
    enforce_fail = policy.get("gate", {}).get("tier1CoverageEnforceFail", False)

    counts: dict[str, int] = {}
    for agent, _scenario in current_scenarios(root):
        counts[agent] = counts.get(agent, 0) + 1

    missing = [a for a in tier1 if counts.get(a, 0) < min_n]
    if not missing:
        lines.append(f"{OK} tier1 전 에이전트({len(tier1)}종) 최소 시나리오 보유")
        return True, lines

    if enforce_fail:
        lines.append(
            f"{NG} tier1 커버리지 미달 ({len(missing)}/{len(tier1)}): {missing}"
        )
        return False, lines
    lines.append(
        f"{WARN} tier1 커버리지 미달, 경고만(S4에서 fail 승격 예정) "
        f"({len(missing)}/{len(tier1)}): {missing}"
    )
    return True, lines


def check_tier2(root: Path, policy: dict) -> tuple[bool, list[str]]:
    """티어2(A등급) 각 에이전트가 최소 시나리오를 보유하는지 검사.

    tier1과 달리 미달을 처음부터 fail로 승격해 둘 수 있다(policy 플래그
    `gate.tier2CoverageEnforceFail`) — W-024에서 유일한 갭(consensus-builder)을
    같은 배치에서 메우므로 tier1처럼 경고 단계를 거칠 이유가 없다(decision D-3,
    docs/specs/2026-09-04-eval-tier2-coverage-gate.md). 플래그 부재 시 기본값은
    안전한 쪽(False = 경고만)이며, 이는 check_tier1과 동일한 관례다.

    `tiers.tier2`가 없거나 빈 배열이면 gate 플래그와 무관하게 즉시 fail이다 —
    "검사 대상 0개"를 통과로 오인하는 거짓 green이 이 배치가 잡은 결함 그 자체이므로
    (consensus-builder가 등재됐으나 시나리오 없이 통과한 경로), validate_policy_schema가
    tier1에 대해 하는 검사와 같은 급으로 다룬다.
    """
    lines: list[str] = []
    tier2 = policy.get("tiers", {}).get("tier2")
    if not isinstance(tier2, list) or not tier2:
        lines.append(
            f"{NG} policy.json: 'tiers.tier2'가 없거나 빈 배열이다 — "
            "검사 대상 0개를 전부 통과로 오인하는 거짓 green을 막기 위해 거부한다"
        )
        return False, lines

    min_n = policy.get("coverage", {}).get("tier2MinScenariosPerAgent", 1)
    enforce_fail = policy.get("gate", {}).get("tier2CoverageEnforceFail", False)

    counts: dict[str, int] = {}
    for agent, _scenario in current_scenarios(root):
        counts[agent] = counts.get(agent, 0) + 1

    missing = [a for a in tier2 if counts.get(a, 0) < min_n]
    if not missing:
        lines.append(
            f"{OK} tier2(A등급) 전 에이전트({len(tier2)}종) 최소 시나리오 보유"
        )
        return True, lines

    if enforce_fail:
        lines.append(
            f"{NG} tier2 커버리지 미달 ({len(missing)}/{len(tier2)}): {missing}"
        )
        return False, lines
    lines.append(
        f"{WARN} tier2 커버리지 미달, 경고만"
        f"(gate.tier2CoverageEnforceFail 승격 시 fail) "
        f"({len(missing)}/{len(tier2)}): {missing}"
    )
    return True, lines


def _discover_all_agents(root: Path) -> set[str]:
    """`plugins/common/agents/**/*.md` 파일명(확장자 제외)에서 전체 에이전트
    목록을 얻는다 — 하드코딩 금지, 하위 카테고리(backend/dev/meta/planning 등)
    재귀 포함."""
    agents_dir = root / "plugins" / "common" / "agents"
    if not agents_dir.is_dir():
        return set()
    return {p.stem for p in agents_dir.rglob("*.md")}


def check_classification_complete(root: Path, policy: dict) -> tuple[bool, list[str]]:
    """전체 에이전트 = tier1 + tier2 + `_tier2Classification`(B·C 등급) 합집합인지 검사.

    미분류 에이전트가 있을 때의 warn/fail 전환은 `gate.classificationCompleteEnforceFail`
    (부재 시 False)이 관여한다 — 새 에이전트를 추가하는 무관한 작업이 분류 등재
    전까지 게이트를 막으면 오작동이다(D-3). 경고는 매 실행에 출력되므로 침묵하지
    않고, 필요해지면 플래그만 올린다(코드 변경 불필요).

    **이 플래그가 관여하지 않는 별도의 실패 단계가 있다**: `_discover_all_agents`가
    에이전트를 0종 발견하면(디렉토리 부재·`.md` 0건 둘 다) `missing`도 공집합이 되어
    "전체 에이전트(0종) 분류 완전 — 일치"로 오판한다 — `check_tier2`의
    `tiers.tier2` 부재·빈 배열 처리, `validate_policy_schema`의 tier1 처리와 같은
    급의 거짓 green이다("검사 대상 0개"는 정합이 아니라 정책/레포 손상). 이 실패는
    플래그와 무관하게 즉시 fail이다 — enforce_fail이 False여도 통과시키지 않는다.
    """
    lines: list[str] = []
    all_agents = _discover_all_agents(root)
    if not all_agents:
        lines.append(
            f"{NG} plugins/common/agents 아래에서 에이전트를 0종 발견했다 "
            "(디렉토리 부재 또는 .md 0건) — 검사 대상 0개를 전부 통과로 오인하는 "
            "거짓 green을 막기 위해 거부한다"
        )
        return False, lines

    tiers = policy.get("tiers", {})
    tier1 = set(tiers.get("tier1", []))
    tier2 = set(tiers.get("tier2", []))
    classification = tiers.get("_tier2Classification", {})
    classified = (
        set(classification.keys()) if isinstance(classification, dict) else set()
    )

    covered = tier1 | tier2 | classified
    missing = sorted(all_agents - covered)

    enforce_fail = policy.get("gate", {}).get(
        "classificationCompleteEnforceFail", False
    )

    if not missing:
        lines.append(
            f"{OK} 전체 에이전트({len(all_agents)}종) 분류 완전 — "
            "tier1+tier2+_tier2Classification 합집합과 일치"
        )
        return True, lines

    if enforce_fail:
        lines.append(f"{NG} 미분류 에이전트 존재 ({len(missing)}종): {missing}")
        return False, lines
    lines.append(
        f"{WARN} 미분류 에이전트 존재, 경고만"
        f"(gate.classificationCompleteEnforceFail 승격 시 fail) "
        f"({len(missing)}종): {missing}"
    )
    return True, lines


# 검사 추가 = 이 목록에 함수 하나 추가 (F6). 각 항목은 `(root, policy) ->
# tuple[bool, list[str]]` 시그니처(위 check_* 함수들과 동일)를 지켜야 한다 —
# main()의 루프가 그 계약에 의존한다.
CHECKS: list[Callable[[Path, dict], tuple[bool, list[str]]]] = [
    check_coverage,
    check_tier1,
    check_tier2,
    check_classification_complete,
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."), help="repo root (테스트용)")
    args = ap.parse_args(argv)
    root = args.root.resolve()

    policy_path = root / "evals" / "policy.json"
    if not policy_path.is_file():
        print(f"{NG} evals/policy.json 없음")
        return 1
    try:
        policy = load_policy(root)
    except json.JSONDecodeError as e:
        print(f"{NG} evals/policy.json 파싱 실패: {e}")
        return 1

    try:
        validate_policy_schema(policy)
    except PolicyError as e:
        print(f"{NG} {e}")
        return 1

    ok = True
    for check in CHECKS:
        check_ok, lines = check(root, policy)
        ok &= check_ok
        for line in lines:
            print(line)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
