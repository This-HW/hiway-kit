"""Unit tests for scripts/check_eval_coverage.py (W-018 / S1).

**실제 evals/ 트리를 건드리지 않는다** — 매 테스트가 tmp_path에 최소 가짜 레포를
만들고 `--root`로 그곳을 가리킨다. 게이트용 도구의 테스트가 게이트 자산(진짜
baseline/scenarios)을 오염시키면 안 된다(scripts/tests/test_eval_forge.py와 동일 원칙).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import ModuleType

from module_loader import load_module_by_path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent


def _load_module() -> ModuleType:
    return load_module_by_path(
        SCRIPTS_DIR / "check_eval_coverage.py", "check_eval_coverage"
    )


cec = _load_module()


def _base_policy(**gate_overrides) -> dict:
    gate = {
        "requireBaselineCoversAllScenarios": True,
        "requireScenariosCoverBaseline": True,
        "tier1CoverageEnforceFail": False,
        "tier2CoverageEnforceFail": False,
        "classificationCompleteEnforceFail": False,
    }
    gate.update(gate_overrides)
    return {
        "baseline": {"file": "baseline.json"},
        "tiers": {
            "tier1": ["fix-bugs", "review-code"],
            # 기본은 시나리오 없는 tier2 에이전트 1종 — enforce_fail 기본 False라
            # 기존 테스트들의 rc는 그대로 유지되고, tier2 관련 신규 테스트만 이 값을
            # 오버라이드한다.
            "tier2": ["analyze-tech-debt"],
        },
        "coverage": {
            "tier1MinScenariosPerAgent": 1,
            "tier2MinScenariosPerAgent": 1,
        },
        "gate": gate,
    }


def _make_repo(
    tmp_path: Path,
    scenario_pairs: list[tuple[str, str]],
    baseline_pairs: list[tuple[str, str]] | None,
    policy: dict,
    populate_agents: bool = True,
) -> Path:
    """`populate_agents`(기본 True)는 policy의 tier1+tier2 목록을 그대로
    `plugins/common/agents/dev/*.md`로 심어준다 — check_classification_complete가
    "에이전트 0종"으로 무조건 fail하는 새 가드(코디네이터 실증, W-024 후속) 때문에,
    분류를 직접 검사하지 않는 다른 테스트(baseline/tier1/tier2 케이스들)까지
    영향받지 않게 하기 위함이다. 0종 가드 자체를 검사하는 테스트만
    `populate_agents=False`로 이 기본을 끈다."""
    root = tmp_path / "repo"
    scenarios_root = root / "evals" / "scenarios"
    for agent, scenario in scenario_pairs:
        (scenarios_root / agent / scenario).mkdir(parents=True)

    # 실물 run.py를 그대로 복사 — discover_scenario_dirs 스킵 규칙까지 실물과 동일해야
    # 검사 경로가 의미 있다 (test_eval_forge.py와 동일 관례).
    (root / "evals").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "evals" / "run.py", root / "evals" / "run.py")

    if baseline_pairs is not None:
        baseline_dir = root / "evals" / "baseline"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        results = [{"agent": a, "scenario": s} for a, s in baseline_pairs]
        (baseline_dir / "baseline.json").write_text(
            json.dumps({"results": results}), encoding="utf-8"
        )

    (root / "evals" / "policy.json").write_text(json.dumps(policy), encoding="utf-8")

    if populate_agents:
        tiers = policy.get("tiers", {})
        default_agents = sorted(
            set(tiers.get("tier1", [])) | set(tiers.get("tier2", []))
        )
        _add_agent_files(root, default_agents)

    return root


def _add_agent_files(root: Path, names: list[str]) -> None:
    """가짜 레포에 `plugins/common/agents/dev/<name>.md` 파일을 심는다 — 실물
    레포의 하위 카테고리 재귀 구조(backend/dev/meta/planning)를 대표해 dev/ 하나만
    써도 _discover_all_agents의 rglob 경로가 동일하게 동작한다."""
    agents_dir = root / "plugins" / "common" / "agents" / "dev"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (agents_dir / f"{name}.md").write_text(
            f"---\nname: {name}\n---\n", encoding="utf-8"
        )


# ── 4개 필수 케이스 (STAGE1_LLM.md 완료조건 2) ─────────────────────────────


def test_extra_scenario_not_in_baseline_fails():
    """시나리오 초과 — baseline에 없는 시나리오 디렉토리가 있으면 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
            baseline_pairs=[("fix-bugs", "a")],  # review-code/b 없음
            policy=_base_policy(),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_baseline_entry_without_scenario_dir_fails():
    """기준선 초과 — 기준선에만 있고 시나리오 디렉토리가 사라진 항목이 있으면 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
            policy=_base_policy(),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_missing_baseline_file_fails_not_skips():
    """baseline.file이 가리키는 파일이 없으면 조용히 skip이 아니라 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=None,  # baseline.json 자체를 만들지 않음
            policy=_base_policy(),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_matching_sets_pass_green():
    """정상 — 시나리오 집합과 기준선 집합이 완전히 일치하면 exit 0."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
            baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
            policy=_base_policy(),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 0


# ── 추가 케이스 — tier1 경고/승격 스위치, 게이트 플래그 off ─────────────────


def test_tier1_gap_warns_only_when_enforce_fail_false():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],  # review-code(tier1) 시나리오 0건
            baseline_pairs=[("fix-bugs", "a")],
            policy=_base_policy(tier1CoverageEnforceFail=False),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 0  # 커버리지는 정합, tier1 미달은 경고일 뿐


def test_tier1_gap_fails_when_enforce_fail_true():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a")],
            policy=_base_policy(tier1CoverageEnforceFail=True),
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1  # S4 승격 시나리오


def test_missing_policy_json_fails():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "repo"
        (root / "evals").mkdir(parents=True)
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_real_repo_baseline_covers_scenarios_direction_holds():
    """실물 레포 대조: 이 스크립트가 진짜 evals/를 읽었을 때도 판정 로직 자체가
    죽지 않고 동작함을 확인 — 실제 값의 pass/fail 여부는 단언하지 않는다.
    (2026-08-27 기준 실물은 21/21·tier1 13/13으로 green이지만, 향후 다시
    드리프트가 생기면 fail이 정상 — 이 테스트는 '크래시 없이 판정 가능'만
    검증하고 어느 쪽 결과도 실패로 취급하지 않는다. W-019 교차 리뷰 Low 지적
    — 특정 시점의 pass/fail 사실을 주석에 박아두면 다음 실패 때 오판을 부른다)."""
    rc = cec.main(["--root", str(REPO_ROOT)])
    assert rc in (0, 1)


# ── policy.json 스키마 방어 (W-018/W-019 교차 리뷰 — sanddab 실측 거짓 green) ──
#
# sanddab이 daggertooth의 evals/policy.json에서 "tiers" 키를 통째로 지우고
# check_eval_coverage.py를 돌려 exit 0("tier1 전 에이전트(0종) 최소 시나리오
# 보유")을 재현했다 — 검사 대상 0개를 "전부 통과"로 오인하는 거짓 green이다.
# 아래는 그 정확한 재현을 회귀 테스트로 고정한 것.


def test_policy_missing_tiers_section_fails():
    """tiers 섹션이 통째로 없으면 vacuous pass가 아니라 exit 1이어야 한다."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        policy = _base_policy()
        del policy["tiers"]
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a")],
            policy=policy,
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_policy_empty_tier1_list_fails():
    """tiers.tier1이 빈 배열이면(섹션은 있으나 내용 없음) 여전히 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        policy = _base_policy()
        policy["tiers"] = {"tier1": []}
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a")],
            policy=policy,
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_policy_missing_gate_section_fails():
    """gate 섹션이 통째로 없으면 조용한 기본값(전부 통과) 대신 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        policy = _base_policy()
        del policy["gate"]
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a")],
            policy=policy,
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_policy_missing_coverage_section_fails():
    """coverage 섹션이 통째로 없으면 조용한 기본값 대신 exit 1."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        policy = _base_policy()
        del policy["coverage"]
        root = _make_repo(
            Path(td),
            scenario_pairs=[("fix-bugs", "a")],
            baseline_pairs=[("fix-bugs", "a")],
            policy=policy,
        )
        rc = cec.main(["--root", str(root)])
        assert rc == 1


def test_policy_top_level_not_dict_fails_cleanly():
    """policy.json이 문법상 유효한 JSON이어도 최상위가 dict가 아니면(예: 배열)
    raw AttributeError 트레이스백 대신 명확한 메시지로 exit 1이어야 한다
    (W-019 교차 리뷰 Medium — SSOT 로더가 이런 경우 원인불명으로 죽던 문제와
    같은 클래스)."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "repo"
        (root / "evals").mkdir(parents=True)
        (root / "evals" / "policy.json").write_text("[]", encoding="utf-8")
        rc = cec.main(["--root", str(root)])
        assert rc == 1


# ── baseline.file 경로 봉쇄 (W-019 교차 리뷰 3번째 인스턴스 — sanddab 실측) ──
#
# sanddab이 daggertooth의 evals/policy.json에서 baseline.file을 절대경로로
# 바꿔 check_eval_coverage.py를 돌려 exit 0("모든 시나리오 디렉토리가 기준선에
# 존재", "tier1 전 에이전트 최소 시나리오 보유")을 재현했다 — 레포 밖 파일을
# 기준선으로 신뢰하는 경로 탈출 + 거짓 green이 겹친 형태다. 같은 클래스가
# scripts/build-targets.py(W-019, 쓰기 경로)에서도 나왔던 결함이다 —
# `_resolve_in_repo()` 관례를 그대로 이식해 막는다.


def _plant_valid_baseline_outside(tmp_path: Path) -> Path:
    """레포 밖에 스키마상 완전히 유효한 baseline JSON을 심는다 — '파일이 없어서
    실패'가 아니라 '유효한 파일인데 위치가 틀려서 거부되는지'를 검증하기 위함."""
    outside = tmp_path / "outside" / "evil-baseline.json"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text(
        json.dumps({"results": [{"agent": "fix-bugs", "scenario": "a"}]}),
        encoding="utf-8",
    )
    return outside


def test_baseline_file_absolute_path_escape_blocked(tmp_path):
    outside = _plant_valid_baseline_outside(tmp_path)
    policy = _base_policy()
    policy["baseline"]["file"] = str(outside)  # 절대경로
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a")],
        baseline_pairs=None,  # evals/baseline/ 안에는 아무것도 안 둔다
        policy=policy,
    )
    rc = cec.main(["--root", str(root)])
    assert rc == 1


def test_baseline_file_relative_traversal_escape_blocked(tmp_path):
    outside = _plant_valid_baseline_outside(tmp_path)
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a")],
        baseline_pairs=None,
        policy=_base_policy(),
    )
    # evals/baseline/ 디렉토리 자체는 실물 레포처럼 존재해야 한다 — 없으면 OS가
    # '..' 순회 자체를 못 하고(중간 경로 부재) is_file()이 그냥 False가 되어,
    # "탈출이 막혀서"가 아니라 "애초에 순회가 안 돼서" 통과하는 가짜 테스트가 된다
    # (이 파일 초안에서 실제로 걸렸던 실수 — 봉쇄 없이도 오탐 green이 났었다).
    baseline_dir = root / "evals" / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    import os

    rel = Path(os.path.relpath(outside, start=baseline_dir))
    policy = _base_policy()
    policy["baseline"]["file"] = str(rel)
    (root / "evals" / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
    rc = cec.main(["--root", str(root)])
    assert rc == 1


def test_baseline_file_symlink_escape_blocked(tmp_path):
    outside = _plant_valid_baseline_outside(tmp_path)
    policy = _base_policy()
    policy["baseline"]["file"] = "linked.json"
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a")],
        baseline_pairs=None,
        policy=policy,
    )
    baseline_dir = root / "evals" / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    (baseline_dir / "linked.json").symlink_to(outside)
    rc = cec.main(["--root", str(root)])
    assert rc == 1


def test_baseline_file_within_baseline_dir_still_works(tmp_path):
    """봉쇄가 정상적인 상대경로까지 막지 않는지 확인 — 과도한 봉쇄로 인한
    false-red 방지."""
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a")],
        baseline_pairs=[("fix-bugs", "a")],
        policy=_base_policy(),
    )
    rc = cec.main(["--root", str(root)])
    assert rc == 0


def test_resolve_in_repo_shared_adversarial_table(tmp_path):
    """`_resolve_in_repo`가 build-targets.py와 공유하는 적대적 케이스 표를
    통과하는지 검증한다 (D-15: 구현은 여러 벌, 계약만 하나 —
    scripts/tests/resolve_in_repo_contract.py 참고)."""
    from resolve_in_repo_contract import assert_resolve_in_repo_contract

    assert_resolve_in_repo_contract(cec._resolve_in_repo, tmp_path)


# ── tier2 커버리지 (W-024, docs/specs/2026-09-04-eval-tier2-coverage-gate.md D-3) ──


def test_tier2_gap_fails_when_enforce_fail_true(tmp_path):
    """tier2 에이전트 1종에 시나리오 없음 + enforce_fail:true → exit 1."""
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        policy=_base_policy(tier2CoverageEnforceFail=True),
    )
    rc = cec.main(["--root", str(root)])
    assert rc == 1


def test_tier2_gap_warns_only_when_enforce_fail_false(tmp_path, capsys):
    """같은 상황에서 플래그 false → exit 0 + 경고 출력."""
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        policy=_base_policy(tier2CoverageEnforceFail=False),
    )
    rc = cec.main(["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 0
    assert cec.WARN in captured.out
    assert "analyze-tech-debt" in captured.out


def test_tier2_missing_key_fails_regardless_of_flag(tmp_path):
    """tiers.tier2 자체가 없으면 gate 플래그와 무관하게 거짓 green 방지를 위해
    exit 1 — enforce_fail:false 여도 마찬가지다."""
    policy = _base_policy(tier2CoverageEnforceFail=False)
    del policy["tiers"]["tier2"]
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        policy=policy,
    )
    rc = cec.main(["--root", str(root)])
    assert rc == 1


def test_tier2_empty_list_fails_regardless_of_flag(tmp_path):
    """tiers.tier2가 빈 배열이어도(섹션은 있으나 내용 없음) 거짓 green 방지를
    위해 exit 1 — enforce_fail:false 여도 마찬가지다."""
    policy = _base_policy(tier2CoverageEnforceFail=False)
    policy["tiers"]["tier2"] = []
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        policy=policy,
    )
    rc = cec.main(["--root", str(root)])
    assert rc == 1


# ── 분류 완전성 (W-024, 같은 스펙 D-3) ──────────────────────────────────────


def test_classification_missing_agent_warns_by_default(tmp_path, capsys):
    """분류 미등재 에이전트 존재 + 기본(warn) → exit 0 + 경고 출력."""
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        policy=_base_policy(),
    )
    _add_agent_files(
        root, ["fix-bugs", "review-code", "analyze-tech-debt", "mystery-agent"]
    )
    rc = cec.main(["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 0
    assert cec.WARN in captured.out
    assert "mystery-agent" in captured.out


def test_classification_missing_agent_fails_when_enforced(tmp_path):
    """같은 상황에서 플래그 승격(classificationCompleteEnforceFail:true) → exit 1."""
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        policy=_base_policy(classificationCompleteEnforceFail=True),
    )
    _add_agent_files(
        root, ["fix-bugs", "review-code", "analyze-tech-debt", "mystery-agent"]
    )
    rc = cec.main(["--root", str(root)])
    assert rc == 1


def test_all_aligned_pass_clean_no_warnings(tmp_path, capsys):
    """tier1·tier2·baseline·분류·에이전트 파일이 전부 정합 → exit 0, 경고 없음."""
    root = _make_repo(
        tmp_path,
        scenario_pairs=[
            ("fix-bugs", "a"),
            ("review-code", "b"),
            ("analyze-tech-debt", "c"),
        ],
        baseline_pairs=[
            ("fix-bugs", "a"),
            ("review-code", "b"),
            ("analyze-tech-debt", "c"),
        ],
        policy=_base_policy(),
    )
    _add_agent_files(root, ["fix-bugs", "review-code", "analyze-tech-debt"])
    rc = cec.main(["--root", str(root)])
    captured = capsys.readouterr()
    assert rc == 0
    assert cec.WARN not in captured.out
    assert cec.NG not in captured.out


# ── 분류 완전성의 "0종 발견" 거짓 green 봉쇄 (코디네이터 실증, W-024 후속) ──
#
# _discover_all_agents가 에이전트를 0종 발견하면 missing도 공집합이 되어
# "전체 에이전트(0종) 분류 완전 — 일치"로 오판했다 — check_tier2의 tiers.tier2
# 부재·빈 배열 처리, validate_policy_schema의 tier1 처리와 같은 급의 거짓 green.
# classificationCompleteEnforceFail 플래그와 무관하게(False여도) 즉시 fail이어야
# 한다.


def test_classification_zero_agents_dir_missing_fails_regardless_of_flag(tmp_path):
    """plugins/common/agents 디렉토리 자체가 없으면 플래그 false여도 exit 1."""
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        policy=_base_policy(classificationCompleteEnforceFail=False),
        populate_agents=False,  # plugins/ 디렉토리 자체를 만들지 않는다
    )
    rc = cec.main(["--root", str(root)])
    assert rc == 1


def test_classification_zero_agents_dir_empty_fails_regardless_of_flag(tmp_path):
    """plugins/common/agents 디렉토리는 있으나 .md가 0건이면 플래그 false여도 exit 1."""
    root = _make_repo(
        tmp_path,
        scenario_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        baseline_pairs=[("fix-bugs", "a"), ("review-code", "b")],
        policy=_base_policy(classificationCompleteEnforceFail=False),
        populate_agents=False,
    )
    # 디렉토리는 존재하되 .md 파일은 하나도 없다 — "부재"가 아니라 "빈 디렉토리"
    # 경로까지 막는지 별도로 확인한다.
    (root / "plugins" / "common" / "agents" / "dev").mkdir(parents=True)
    rc = cec.main(["--root", str(root)])
    assert rc == 1
