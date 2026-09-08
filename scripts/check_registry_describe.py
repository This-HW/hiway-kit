#!/usr/bin/env python3
"""`describe` 이음매 적합성 프로브 (26-17, D-42·D-44·D-48·D-49·D-50).

컨트롤 프로젝트가 자기 레지스트리 파사드를 **이 킷을 설치하지 않고도** 검증할 수 있게
하는 결정론적 스크립트다. 이 킷 쪽 D-42 이음매는 동사 `describe` 하나만 알고, 그것이
JSON으로 자기 능력을 선언하면 이 킷은 선언된 것만 호출한다. 이 프로브는 그 반대편
계약을 검증한다 — 킷이 실제로 설치되기 전에 계약이 맞물려 보는 유일한 방법이다.

검사(전부 D-44의 fail-closed 표에서 기계적으로 도출):
  1. `describe` 호출이 유효 JSON을 반환하는가
  2. 동사마다 `name`·`args`가 있는가
  3. `effect`가 `read`|`write`이거나 미선언인가(미선언은 write로 간주되고 그렇게 보고)
  4. 자식 노출 집합(`effect=="read"`)에 미선언 동사가 없는가
  5. 포인터에 `url` 필드가 있으면 거절하는가(D-48 — exec 전용, 자격증명을 킷이 다루지 않는다)
  6. `head`(선택) — 현재 git HEAD와 대조해 신선도를 보고한다(D-49). 지속 불일치 패턴은
     `--observe`로 누적 기록해 감지한다(D-50 — "기동 커밋 보고" 파사드 판정).
  7. 깨진 응답(비-JSON, 실행 실패, 타임아웃) → 전면 폴백 판정(부분 신뢰 없음)

사용:
  # 포인터 파일 경유(레지스트리 discovery 형식과 동일 — command만, url 불허)
  check_registry_describe.py --pointer registry.json

  # 커맨드를 직접 지정
  check_registry_describe.py -- /path/to/registry-cli --some-flag

  # 신선도 지속 불일치(기동 커밋 파사드) 관측 누적
  check_registry_describe.py --pointer registry.json --observe .kit-probe-history.jsonl

exit 0 = green(적합), exit 1 = red(부적합 — 이유를 stdout에 나열)

이 프로브는 **어떤 게이트에도 물려 있지 않다 — 의도적이다.**
`verify-done.sh` 도 CI 도 이것을 부르지 않는다. 발화 조건은 *"컨트롤 프로젝트가 실제로
`describe` 를 내놓았을 때, 사람이 그 커맨드를 지목해 부른다"* 이고, 그 실물이 아직
없으므로(설계 SSOT §20.2) 자동 실행할 대상이 없다. 대조할 것이 없는데 게이트에 물리면
"검사 대상 0개"를 green 으로 보고하게 되고, 그것은 정합이 아니라 손상이다.

**적어 두는 이유**: 게이트에 물려 있다고 오해하면 없는 보호를 있다고 믿게 된다.
검사를 넣을 때는 그 검사가 도는 조건을 한 문장으로 적는다 —
`docs/conventions/warning-signal.md` §검토 절차 4.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

DESCRIBE_TIMEOUT_SECONDS = 10
BOOT_COMMIT_STREAK_THRESHOLD = (
    3  # 이 이상 "선언 head 불변, 실제 head 변함"이면 기동 커밋 의심
)


class ProbeError(Exception):
    """포인터·실행 단계의 즉시 실패 — main이 red 한 줄로 변환한다."""


def load_pointer(path: Path) -> list[str]:
    """레지스트리 포인터 JSON을 읽어 command(argv)를 반환한다.

    `url` 필드가 있으면 무조건 거절한다(D-48) — 이 킷은 exec 전용 계약이고, HTTP
    레지스트리는 자격증명 취급을 스스로 떠안는 shim을 내야 한다(소비자 몫).
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ProbeError(f"포인터 파일을 읽을 수 없다: {path} ({e})") from e
    try:
        pointer = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProbeError(f"포인터가 유효 JSON이 아니다: {path} ({e})") from e
    if not isinstance(pointer, dict):
        raise ProbeError(f"포인터가 JSON 객체가 아니다: {path}")
    if "url" in pointer:
        raise ProbeError(
            "포인터에 'url' 필드가 있다 — 거절 대상이다(D-48, exec 전용 계약). "
            "HTTP 레지스트리는 소비자 쪽 shim으로 command(argv)를 노출해야 한다."
        )
    command = pointer.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(c, str) for c in command)
    ):
        raise ProbeError(
            "포인터의 'command'가 비어 있지 않은 문자열 리스트(argv)가 아니다."
        )
    return command


def invoke_describe(command: list[str]) -> tuple[dict | None, str | None]:
    """command + ['describe']를 실행해 (파싱된 JSON, 오류메시지)를 반환한다.

    오류메시지가 None이 아니면 첫 값은 항상 None이다 — 부분 신뢰를 만들지 않는다
    (D-44: "describe 부재·파싱 실패·스키마 미해석 → 전면 폴백, 부분 신뢰하지 않는다").
    """
    try:
        r = subprocess.run(
            [*command, "describe"],
            capture_output=True,
            text=True,
            timeout=DESCRIBE_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return None, f"명령을 찾을 수 없다: {command[0]}"
    except subprocess.TimeoutExpired:
        return None, f"describe 호출이 {DESCRIBE_TIMEOUT_SECONDS}초 안에 끝나지 않았다"
    except OSError as e:
        return None, f"describe 실행 실패: {e}"
    if r.returncode != 0:
        return (
            None,
            f"describe가 종료코드 {r.returncode}로 실패했다: {r.stderr.strip()}",
        )
    try:
        parsed = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        return None, f"describe 응답이 유효 JSON이 아니다: {e}"
    if not isinstance(parsed, dict):
        return None, "describe 응답이 JSON 객체가 아니다"
    return parsed, None


def classify_effect(verb: dict) -> str:
    """D-44 fail-closed: read|write가 아니면(미선언 포함) write로 간주."""
    e = verb.get("effect")
    return e if e in ("read", "write") else "write"


def classify_idempotent(verb: dict) -> bool:
    """D-44 fail-closed: 미선언은 false(재시도 안전하지 않음)로 간주."""
    return verb.get("idempotent") is True


def validate_schema(response: dict) -> list[str]:
    """동사 스키마 필수 필드(name·args) 검사. 위반 목록을 반환(비면 통과)."""
    errors: list[str] = []
    verbs = response.get("verbs")
    if not isinstance(verbs, list):
        return ["최상위 'verbs'가 리스트가 아니다"]
    for i, v in enumerate(verbs):
        if not isinstance(v, dict):
            errors.append(f"verbs[{i}]가 객체가 아니다")
            continue
        name = v.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"verbs[{i}] — 'name'이 없거나 문자열이 아니다")
        if not isinstance(v.get("args"), list):
            label = name if isinstance(name, str) and name else f"verbs[{i}]"
            errors.append(f"동사 '{label}' — 'args'가 없거나 리스트가 아니다")
    return errors


def child_exposed_verbs(verbs: list[dict]) -> list[str]:
    """킷이 자식에게 노출할 동사 이름 목록 — effect가 명시적으로 'read'인 것만."""
    return [
        v.get("name")
        for v in verbs
        if isinstance(v, dict) and v.get("effect") == "read"
    ]


def undeclared_effect_verbs(verbs: list[dict]) -> list[str]:
    """effect가 read/write 어느 쪽도 아니거나(미선언 포함) 아닌 동사 이름."""
    return [
        v.get("name")
        for v in verbs
        if isinstance(v, dict) and v.get("effect") not in ("read", "write")
    ]


def check_undeclared_not_exposed(verbs: list[dict]) -> list[str]:
    """미선언 동사가 자식 노출 집합에 들어가면 그 이름을 반환한다(수용 44).

    구조상 child_exposed_verbs()는 effect=='read' 명시 선언만 담으므로 항상
    비어야 한다 — 회귀 방지 목적의 명시적 재확인이다.
    """
    exposed = set(child_exposed_verbs(verbs))
    return [name for name in undeclared_effect_verbs(verbs) if name in exposed]


def current_git_head(cwd: Path | None = None) -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def classify_freshness(declared_head: str | None, actual_head: str | None) -> str:
    """'match' | 'mismatch' | 'undeclared' | 'unknown'(실제 HEAD를 알 수 없음)."""
    if declared_head is None:
        return "undeclared"
    if actual_head is None:
        return "unknown"
    return "match" if declared_head == actual_head else "mismatch"


def record_observation(
    history_path: Path, declared_head: str | None, actual_head: str | None
) -> None:
    entry = {
        "ts": time.time(),
        "declaredHead": declared_head,
        "actualHead": actual_head,
    }
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def detect_boot_commit_pattern(
    history_path: Path, streak_threshold: int = BOOT_COMMIT_STREAK_THRESHOLD
) -> bool:
    """최근 관측에서 declaredHead가 고정인데 actualHead가 변한 연속 기록이
    streak_threshold 이상이면 "기동 커밋 보고" 파사드로 판정한다(D-50/17.2).

    "장수 stdio 프로세스가 기동 시점 커밋을 그대로 되돌려주는" 패턴을 잡는다 —
    한 번의 불일치는 정상적인 지연일 수 있으므로 임계값 미만은 판정하지 않는다.
    """
    if not history_path.is_file():
        return False
    lines = [
        ln for ln in history_path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    if len(lines) < streak_threshold:
        return False
    recent = [json.loads(ln) for ln in lines[-streak_threshold:]]
    declared = {e.get("declaredHead") for e in recent}
    actual_values = [e.get("actualHead") for e in recent]
    if len(declared) != 1 or None in declared:
        return False  # declaredHead가 흔들리면 기동 커밋 패턴이 아니다
    if len(set(actual_values)) < 2:
        return False  # 실제 HEAD가 안 바뀌었으면 판별 불가
    return all(v != next(iter(declared)) for v in actual_values)


def evaluate(
    response: dict, repo_head: str | None, history_path: Path | None
) -> tuple[bool, list[str]]:
    """describe 응답 하나를 평가해 (green?, 보고 라인 목록)을 반환한다."""
    lines: list[str] = []
    ok = True

    schema_errors = validate_schema(response)
    if schema_errors:
        ok = False
        for e in schema_errors:
            lines.append(f"[FAIL] 스키마: {e}")
        return ok, lines
    lines.append("[PASS] 스키마: 모든 동사에 name·args 존재")

    verbs = response.get("verbs", [])
    undeclared = undeclared_effect_verbs(verbs)
    if undeclared:
        lines.append(
            f"[INFO] effect 미선언 동사 {undeclared} — write로 간주, 자식에 노출 안 됨"
        )
    else:
        lines.append("[PASS] 모든 동사가 effect를 명시했다")

    bad_exposure = check_undeclared_not_exposed(verbs)
    if bad_exposure:
        ok = False
        lines.append(f"[FAIL] 자식 노출 집합에 effect 미선언 동사 포함: {bad_exposure}")
    else:
        lines.append("[PASS] 자식 노출 집합에 effect 미선언 동사 없음")

    exposed = child_exposed_verbs(verbs)
    lines.append(f"[INFO] 자식 노출 동사(effect=='read'): {exposed or '(없음)'}")

    non_idempotent_writes = [
        v.get("name")
        for v in verbs
        if isinstance(v, dict)
        and classify_effect(v) == "write"
        and not classify_idempotent(v)
    ]
    if non_idempotent_writes:
        lines.append(
            f"[INFO] 재시도 안전하지 않은 write 동사: {non_idempotent_writes} "
            "(킷은 재시도하지 않는다)"
        )

    declared_head = response.get("head")
    if declared_head is not None and not isinstance(declared_head, str):
        ok = False
        lines.append("[FAIL] 'head' 필드가 문자열이 아니다")
        declared_head = None

    freshness = classify_freshness(declared_head, repo_head)
    if freshness == "match":
        lines.append(f"[PASS] 신선도: head 일치({declared_head})")
    elif freshness == "mismatch":
        lines.append(
            f"[WARN] 신선도: head 불일치(선언 {declared_head} != 실제 {repo_head}) "
            "— 실제 소비자(킷 ledger)는 승격을 보류한다(D-49)"
        )
    elif freshness == "undeclared":
        lines.append("[WARN] 신선도: head 미선언 — 낡음을 탐지할 수 없다(D-49)")
    else:
        lines.append("[INFO] 신선도: 실제 git HEAD를 확인할 수 없어 대조 불가")

    if history_path is not None:
        record_observation(history_path, declared_head, repo_head)
        if detect_boot_commit_pattern(history_path):
            ok = False
            lines.append(
                "[FAIL] 신선도: 최근 관측에서 head가 실제 저장소 변화와 무관하게 "
                "고정돼 있다 — '기동 커밋'을 보고하는 파사드로 판정한다(D-50). "
                "head는 '이 응답이 반영하는 레포 커밋'이어야 한다."
            )

    return ok, lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pointer", type=Path, help="레지스트리 포인터 JSON 경로")
    parser.add_argument(
        "--observe",
        type=Path,
        default=None,
        help="신선도 관측을 누적할 JSONL 파일(기동 커밋 패턴 감지용)",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="--pointer 대신 직접 실행할 커맨드(-- 뒤에 적는다)",
    )
    args = parser.parse_args(argv)

    command_argv = [c for c in args.command if c != "--"]

    if args.pointer and command_argv:
        print("[FAIL] --pointer와 커맨드 인자를 동시에 줄 수 없다", file=sys.stderr)
        return 1
    if not args.pointer and not command_argv:
        print(
            "[FAIL] --pointer <파일> 또는 -- <커맨드...> 중 하나가 필요하다",
            file=sys.stderr,
        )
        return 1

    try:
        command = load_pointer(args.pointer) if args.pointer else command_argv
    except ProbeError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1

    response, error = invoke_describe(command)
    if error is not None:
        print(f"[FAIL] {error}", file=sys.stderr)
        print(
            "[FAIL] 깨진 응답 — 전면 폴백 판정(부분 신뢰 없음). "
            "킷은 이 레지스트리를 신뢰하지 않고 docs/works/ 폴백으로 간다.",
            file=sys.stderr,
        )
        return 1

    repo_head = current_git_head()
    ok, lines = evaluate(response, repo_head, args.observe)
    for line in lines:
        print(line)
    print()
    print("=== GREEN(적합) ===" if ok else "=== RED(부적합) ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
