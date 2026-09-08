#!/usr/bin/env python3
"""
Stop hook: last-resort safety net for ad-hoc coding sessions.
Runs ruff + pytest when Python files are modified. Blocks on failure.
Skips if auto-dev pipeline already ran validation (marker file present).

Failure taxonomy:
  lint_error    → auto-fix with ruff, re-validate. If fixed: inform Claude.
  test_failure  → structured error output, block (NOT auto-fixable)
  no_py_changes → skip entirely (no Python files modified)

Tests are scoped to the test files THIS session edited — the hook never runs the
full suite (it fires on every turn-end, so latency must not scale with suite
size). Full regression testing is delegated to CI, `/test`, and verify-done.sh.
Source-only edits skip the test check. A pytest timeout is NOT a failure — it is
downgraded to a non-blocking [WARN] (configurable via CLAUDE_STOP_TEST_TIMEOUT,
default 60s). This makes timeout false-blocks structurally impossible on large
repos while still blocking real failures in edited test files.

To disable: in plugins/common/hooks/hooks.json, replace the Stop section with
the prompt-based hook (see CHANGELOG.md [2.2.0]) or remove it entirely.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


# ── 프로젝트 루트 결정 ───────────────────────────────────────────
def _get_project_root() -> Path:
    """git rev-parse로 stable한 프로젝트 루트를 반환. git 없으면 cwd fallback."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except Exception:
        pass
    return Path.cwd()


def _state_dir() -> Path:
    """훅 상태(마커/카운터)를 담는 **현재 사용자 전용** 0700 디렉토리.

    이전엔 상태를 world-writable /tmp의 예측 가능한 경로에 직접 뒀다 — 공유 호스트의
    다른 사용자가 심링크 없이도 평범한 파일을 미리 만들어 두는 것만으로 카운터를
    '999'로 오염(cap 상시 발동→검증 무력화)하거나 유효 마커를 심어 검증을 우회할 수
    있었다. `$TMPDIR/claude-{uid}`(0700)로 격리하면 타 사용자가 경로 자체에 접근할 수
    없다. auto-dev 마커 스니펫은 이 모듈의 VALIDATED_MARKER를 직접 사용한다(v2.10.1 단일소스화).
    """
    try:
        uid = os.getuid()
    except AttributeError:  # 비-POSIX(Windows 등) — kit 주 대상은 darwin/linux
        uid = os.environ.get("USER", "user")
    d = Path(tempfile.gettempdir()) / f"claude-{uid}"
    try:
        d.mkdir(mode=0o700, exist_ok=True)
    except Exception:
        return Path(tempfile.gettempdir())
    return d


PROJECT_ROOT = _get_project_root()
_hash = hashlib.md5(str(PROJECT_ROOT).encode(), usedforsecurity=False).hexdigest()[:8]
_STATE_DIR = _state_dir()
VALIDATED_MARKER = _STATE_DIR / f".claude_validated_{_hash}"
RETRY_COUNTER = _STATE_DIR / f".claude_stop_retries_{_hash}"
MAX_RETRIES = 2
_MAX_FILE_SIZE = 1_048_576  # 1MB: auto_fix_lint에서 파일 읽기 상한


# ── 유틸 ────────────────────────────────────────────────────────
def _read_input() -> dict:
    """Stop 훅 stdin(JSON)을 파싱. 비어있거나 깨졌으면 빈 dict.

    수동 실행(TTY) 시 read()가 EOF를 기다리며 멈추지 않도록 isatty 가드.
    프로덕션 Stop 훅은 항상 이벤트 JSON을 stdin으로 파이프한다.
    """
    try:
        if sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _apply_session_scope(session_id) -> None:
    """retry 카운터를 세션 단위로 격리한다.

    카운터는 원래 repo 해시로만 키가 만들어져, 같은 프로젝트 루트에서 도는
    병렬 세션들이 서로의 카운터를 덮어쓰거나 리셋할 수 있었다(크로스세션 오염).
    Stop 훅 stdin의 session_id가 있으면 파일명에 세션 해시를 덧붙여 세션별로
    분리한다. session_id 부재(구 하니스)면 기존 repo 스코프 유지(하위호환).

    VALIDATED_MARKER는 auto-dev(T-merge)와의 크로스-프로세스 계약이라 이름을
    바꾸지 않는다 — 대신 _consume_marker_if_valid()가 내용으로 유효성을 판정한다.
    """
    global RETRY_COUNTER  # noqa: PLW0603 — 세션별 카운터 경로를 한 번 확정
    if session_id:
        sid = hashlib.md5(str(session_id).encode(), usedforsecurity=False).hexdigest()[
            :8
        ]
        RETRY_COUNTER = RETRY_COUNTER.with_name(f"{RETRY_COUNTER.name}_{sid}")


def get_retry_count() -> int:
    try:
        return int(RETRY_COUNTER.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def _write_nofollow(path: Path, content: str) -> None:
    """심볼릭링크를 따라가지 않는 쓰기 (CWE-59/377 방어).

    /tmp의 예측 가능한 경로는 공유 호스트에서 다른 사용자가 심링크로 선점할 수
    있다 — 직접 write_text 하면 링크가 가리키는 임의 파일을 덮어쓴다. O_NOFOLLOW
    tmp 파일에 쓴 뒤 os.replace(rename)로 교체한다: rename은 목적지의 심링크
    자체를 교체하므로 링크 대상 파일을 건드리지 않는다.
    """
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def increment_retry() -> int:
    count = get_retry_count() + 1
    _write_nofollow(RETRY_COUNTER, str(count))
    return count


def reset_retry():
    RETRY_COUNTER.unlink(missing_ok=True)


def allow(message: str = ""):
    """정상 종료: Claude Code가 stop을 허용."""
    if message:
        print(message)
    reset_retry()
    sys.exit(0)


def block(failure_type: str, reason: str, details: dict | None = None):
    """
    Stop을 차단: 네이티브 Stop 훅 스키마(decision=block + reason)로
    Claude에게 수정 컨텍스트를 전달해 자동 수정 턴을 유도한다.

    참조: DEC-002 (W-005) — 미문서화 continueOnBlock 대신 공식 문서의
    {"decision":"block","reason":...} + exit 0 사용. decision 필드가
    exit code와 무관하게 차단을 제어하며, reason이 Claude 컨텍스트에 주입된다.
    """
    retry = get_retry_count()
    parts = [
        reason,
        f"[{failure_type}] {_get_action_hint(failure_type)}",
        f"자동 수정 재시도: {retry}/{MAX_RETRIES}",
    ]
    details = details or {}
    if details.get("errors"):
        parts.append("린트 오류:\n" + str(details["errors"]))
    if details.get("output"):
        parts.append("테스트 출력:\n" + str(details["output"]))
    if details.get("files"):
        parts.append("대상 파일: " + ", ".join(details["files"]))
    if details.get("modified_files"):
        parts.append("변경 파일: " + ", ".join(details["modified_files"]))
    full_reason = "\n\n".join(parts)
    print(json.dumps({"decision": "block", "reason": full_reason}, ensure_ascii=False))
    sys.exit(0)


def _get_action_hint(failure_type: str) -> str:
    hints = {
        "lint_error": "남은 린트 오류를 수동으로 수정하세요.",
        "test_failure": "실패한 테스트를 확인하고 코드를 수정하세요.",
    }
    return hints.get(failure_type, "확인이 필요합니다.")


# ── 변경 파일 감지 ───────────────────────────────────────────────
def get_modified_py_files() -> list[str]:
    """
    수정/추가된 Python 파일 목록을 반환.
    1) git diff HEAD      — tracked 파일 중 수정된 것
    2) git diff --cached  — staged 파일
    3) git ls-files --others --exclude-standard — untracked 새 파일
    git 없는 환경이면 빈 리스트 (검증 스킵).

    제외: `evals/scenarios/` 하위 — eval fixture는 '의도적으로 red인 테스트'를
    포함하는 데이터라 lint/pytest 검증 대상이 아니다 (evals/run.py가 임시 복사본에서
    실행·채점). 이 필터는 _worktree_state_hash 지문에 그대로 반영된다 — auto-dev
    T-merge 스니펫은 이 모듈을 로드해 호출하므로 복제 계약(MUST MATCH)은 소멸(v2.10.1).
    """
    try:
        files: set[str] = set()
        git_opts = {
            "capture_output": True,
            "text": True,
            "timeout": 5,
            "cwd": str(PROJECT_ROOT),
        }

        r1 = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"], **git_opts, check=False
        )
        files.update(f for f in r1.stdout.splitlines() if f.endswith(".py"))

        r2 = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], **git_opts, check=False
        )
        files.update(f for f in r2.stdout.splitlines() if f.endswith(".py"))

        r3 = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            **git_opts,
            check=False,
        )
        files.update(f for f in r3.stdout.splitlines() if f.endswith(".py"))

        return [f for f in files if not _is_eval_fixture(f)]
    except Exception:
        return []


def _is_eval_fixture(rel: str) -> bool:
    """eval fixture 데이터 경로 여부 (git-relative 경로 기준).

    `/fixture/` 세그먼트까지 요구해 제외를 좁힌다 — scenarios 하위의 fixture 밖
    .py(있어선 안 되지만)는 검증 대상으로 남긴다 (재감사 R2/ATK-005; 구조 자체는
    evals/run.py --validate가 '시나리오 루트 .py 금지'로 강제).
    """
    return rel.startswith("evals/scenarios/") and "/fixture/" in rel


def _real(f: str) -> str:
    """git-relative/절대 경로를 심볼릭링크까지 정규화한 절대 경로로 변환."""
    return os.path.realpath(f if os.path.isabs(f) else str(PROJECT_ROOT / f))


def _session_edited_files(data: dict) -> set[str] | None:
    """이번 세션이 Edit/Write 계열 도구로 만진 파일의 정규화 절대경로 집합.

    Stop 훅 stdin의 transcript_path(JSONL 대화 기록)에서 tool_use 블록을 스캔한다.
    이로써 '레포 전체 dirty .py'가 아니라 '이 세션이 실제로 편집한 파일'만 검증
    대상으로 좁혀, 병렬 세션이 남긴 미커밋 .py에 의한 오탐(이번 사건 1차 트리거)을 막는다.

    transcript_path가 없거나(구 하니스) 파싱 실패면 None을 반환 → 호출부는
    기존 동작(전체 dirty .py 검증)으로 폴백한다(그레이스풀 디그레이드).
    """
    tp = data.get("transcript_path")
    if not tp:
        return None
    path = Path(tp).expanduser()
    if not path.exists():
        return None
    edit_tools = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
    edited: set[str] = set()
    has_reliable_py = False  # Edit/Write류로 .py를 만졌나 (스코핑 신뢰 근거)
    bash_py_writeish = False  # Bash로 .py를 썼을 가능성 (폴백 판정)
    try:
        # 대용량 transcript를 통째로 올리지 않도록 줄 단위 스트리밍.
        with path.open(encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                msg = event.get("message", event)
                content = msg.get("content") if isinstance(msg, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name")
                    if name in edit_tools:
                        inp = block.get("input") or {}
                        fp = inp.get("file_path") or inp.get("notebook_path")
                        if fp:
                            edited.add(_real(str(fp)))
                            if str(fp).endswith(".py"):
                                has_reliable_py = True
                    elif name == "Bash":
                        # W-012 #3: Bash(heredoc/sed/tee/redirect/cp)로 .py를 쓰면
                        # Edit/Write 스코프에 안 잡혀 Stop 검증을 우회한다. 명시적 .py
                        # write 대상은 정밀 추출해 스코프에 추가한다(오탐 없이).
                        cmd = (block.get("input") or {}).get("command")
                        if isinstance(cmd, str):
                            for tgt in _bash_py_write_targets(cmd):
                                edited.add(_real(tgt))
                            if _bash_writeish_py(cmd):
                                bash_py_writeish = True
        # 적대적 리뷰 P1(false-green): 세션이 .py를 Bash로만 쓰고(신뢰가능한 Edit/Write
        # .py 편집이 없음) 정밀추출도 놓친 형태(따옴표/변수/python -c/xargs)면, 스코핑이
        # 그 tracked .py를 통째로 drop해 검증을 건너뛴다. 이때는 스코핑을 신뢰하지 않고
        # None(전체 dirty 검증)으로 폴백한다 — 안전망은 미검증(green)보다 오검증(red)이 낫다.
        if bash_py_writeish and not has_reliable_py:
            return None
        return edited
    except Exception:
        return None


# redirect(> >>), tee, sed -i, cp/mv/install 의 .py 대상 경로. blanket 감지 대신
# 실제 쓰기 대상만 뽑아 오탐 없이(F3) in-place bash 편집을 커버한다(F2 잔여분).
_BASH_PY_TARGET_PATTERNS = (
    re.compile(r">>?\s*([^\s;|&<>]+\.py)\b"),
    re.compile(r"\btee\b(?:\s+-\S+)*\s+([^\s;|&<>]+\.py)\b"),
)
_BASH_PY_WRITEISH = ("<<", "open(", "write_text", "writelines", ".write(", "truncate(")


def _strip_quotes(s: str) -> str:
    return s.strip().strip("'\"")


def _bash_py_write_targets(cmd: str) -> list[str]:
    """Bash 명령이 명시적으로 쓰는 .py 경로 목록(정밀 추출). 따옴표는 제거한다."""
    if ".py" not in cmd:
        return []
    targets: list[str] = []
    for pat in _BASH_PY_TARGET_PATTERNS:
        targets += pat.findall(cmd)
    # sed -i / cp / mv / install: 해당 명령 세그먼트 안의 .py 인자를 대상으로 본다.
    for seg in re.split(r"[;|&]{1,2}", cmd):
        if re.search(r"\bsed\b\s+\S*-i", seg) or re.match(
            r"\s*(?:cp|mv|install)\b", seg
        ):
            targets += re.findall(r"([^\s;|&<>]+\.py)\b", seg)
    return [t for t in (_strip_quotes(x) for x in targets) if t]


def _bash_writeish_py(cmd: str) -> bool:
    """Bash 명령이 .py를 '썼을 가능성'이 있는지(느슨). 정밀추출이 못 잡는 형태
    (따옴표/변수확장/python -c/xargs/heredoc)를 폴백 판정하는 데만 쓴다."""
    if ".py" not in cmd:
        return False
    write_redirs = (">", ">>", "tee ", "sed -i", "cp ", "mv ", "install ", "dd ")
    if any(op in cmd for op in write_redirs):
        return True
    return any(tok in cmd for tok in _BASH_PY_WRITEISH)


def _untracked_py_files() -> set[str]:
    """git-untracked .py의 _real 경로 집합. 새로 생성된 .py는 대개 이 세션의 codegen
    산출물이라(python gen.py 등 opaque 생성), 세션 스코프에 union해 검증 누락(F2)을 막는다.
    병렬 세션이 만든 untracked .py를 포함할 수 있으나, 그건 미검증(위험)이 아니라
    오검증(안전) 방향이다."""
    try:
        r = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        return {_real(f) for f in r.stdout.splitlines() if f.endswith(".py")}
    except Exception:
        return set()


# ── 린트 ────────────────────────────────────────────────────────
def _resolve_paths(target_files: list[str]) -> list[str]:
    """git-relative 경로를 PROJECT_ROOT 기준 절대 경로로 변환.
    이미 절대 경로면 그대로 반환. 존재하지 않는 파일은 제외.
    """
    resolved = []
    for f in target_files:
        p = Path(f)
        abs_p = p if p.is_absolute() else PROJECT_ROOT / p
        if abs_p.exists():
            resolved.append(str(abs_p))
    return resolved


def check_lint(target_files: list[str]) -> tuple[bool, str]:
    existing = _resolve_paths(target_files)
    if not existing:
        return True, ""
    try:
        result = subprocess.run(
            ["ruff", "check", *existing],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except FileNotFoundError:
        print("[WARN] ruff not found — lint check skipped", file=sys.stderr)
        return True, ""
    except subprocess.TimeoutExpired:
        print("[WARN] ruff timeout — lint check skipped", file=sys.stderr)
        return True, ""


def auto_fix_lint(target_files: list[str]) -> tuple[bool, list[str], str]:
    """
    Returns: (now_passing, fixed_files, remaining_errors)
    1MB 초과 파일은 비교 대상에서 제외 (OOM 방지).
    """
    try:
        existing = [
            f
            for f in _resolve_paths(target_files)
            if Path(f).stat().st_size < _MAX_FILE_SIZE
        ]
        before = {
            f: Path(f).read_text(encoding="utf-8", errors="replace") for f in existing
        }
        subprocess.run(
            ["ruff", "check", "--fix", *existing],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        after = {
            f: Path(f).read_text(encoding="utf-8", errors="replace") for f in existing
        }
        fixed_files = [f for f in existing if before.get(f) != after.get(f)]

        passed, errors = check_lint(target_files)
        return passed, fixed_files, errors
    except FileNotFoundError:
        print("[WARN] ruff not found — auto-fix skipped", file=sys.stderr)
        return True, [], ""
    except subprocess.TimeoutExpired:
        print("[WARN] ruff --fix timeout — auto-fix skipped", file=sys.stderr)
        return True, [], ""


# ── 테스트 ───────────────────────────────────────────────────────
def _pytest_python() -> str:
    """pytest 실행에 쓸 Python 인터프리터를 결정.
    프로젝트 .venv/venv를 최우선 — 시스템 python3에 pytest가 없어
    'No module named pytest'로 오판 차단되던 문제(#332) 방지.
    """
    for candidate in (".venv/bin/python", "venv/bin/python"):
        p = PROJECT_ROOT / candidate
        if p.exists():
            return str(p)
    return sys.executable or "python3"


_DEFAULT_TEST_TIMEOUT = 60


def _test_timeout() -> int:
    """pytest 타임아웃(초). 환경변수 CLAUDE_STOP_TEST_TIMEOUT로 조절, 기본 60.
    잘못된 값(비정수·0·음수)이면 기본값으로 폴백."""
    try:
        val = int(os.environ.get("CLAUDE_STOP_TEST_TIMEOUT", ""))
        return val if val > 0 else _DEFAULT_TEST_TIMEOUT
    except (TypeError, ValueError):
        return _DEFAULT_TEST_TIMEOUT


def _is_test_file(path: str) -> bool:
    name = Path(path).name
    return name.startswith("test_") or name.endswith("_test.py")


def check_tests(modified_files: list[str]) -> tuple[bool, str]:
    """이 세션이 편집한 테스트 파일만 검증한다(check_lint와 동일한 스코프 철학).

    Stop 훅은 매 턴 종료마다 돌기 때문에 빠르고 예측가능해야 한다. 따라서 지연이
    전체 스위트 크기에 비례하는 '전체 pytest 실행'은 의도적으로 하지 않는다 — 전체
    회귀 검증은 CI(`validate.yml`)·`/test`·`verify-done.sh`의 몫이다. 이 결정으로
    대형 레포에서의 타임아웃 오탐(이번 버그)이 구조적으로 발생하지 않는다.

    - 편집한 test_*.py / *_test.py 만 pytest로 실행 → 항상 작은 스코프, 빠름.
    - 소스만 편집했으면(편집 테스트 없음) 테스트 검증을 스킵(통과)한다.
    - 만일의 느린 단일 테스트를 위해 타임아웃은 '실패'가 아니라 비차단 WARN으로
      강등하고 CLAUDE_STOP_TEST_TIMEOUT으로 조절 가능하게 둔다.
    """
    edited_tests = [f for f in _resolve_paths(modified_files) if _is_test_file(f)]
    if not edited_tests:
        # 소스만 변경 → 전체 회귀는 CI/`/test`에 위임. 훅은 차단하지 않는다.
        return True, ""

    timeout = _test_timeout()
    try:
        result = subprocess.run(
            [
                _pytest_python(),
                "-m",
                "pytest",
                "--tb=short",
                "-q",
                "--no-header",
                *edited_tests,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        combined = result.stdout + result.stderr
        # pytest 미설치 → 검증 불가. 차단이 아니라 스킵(통과)으로 처리(#332).
        if "No module named pytest" in combined:
            print("[WARN] pytest not installed — test check skipped", file=sys.stderr)
            return True, ""
        # exit 5 = no tests collected — 통과로 처리
        return result.returncode in (0, 5), combined
    except FileNotFoundError:
        print("[WARN] python/pytest not found — test check skipped", file=sys.stderr)
        return True, ""
    except subprocess.TimeoutExpired:
        # 타임아웃은 실제 실패와 다르다 → 차단하지 않고 비차단 WARN으로 강등.
        # (CLAUDE_STOP_TEST_TIMEOUT으로 한도 조절 가능.)
        print(
            f"[WARN] pytest timeout ({timeout}s, 변경 테스트 {len(edited_tests)}개) — "
            "test check skipped. 필요시 CLAUDE_STOP_TEST_TIMEOUT으로 한도를 늘리세요.",
            file=sys.stderr,
        )
        return True, ""


# ── auto-dev 검증 마커 ───────────────────────────────────────────
def _worktree_state_hash() -> str:
    """검증 스코프 지문: HEAD + 검증 대상 .py 각각의 (경로, 내용 sha256)의 md5.

    지문 대상을 **훅이 실제 검증하는 파일 집합**(get_modified_py_files — tracked
    수정 ∪ staged ∪ untracked .py)의 *내용*으로 잡는다. 이전 구현은 `git status
    --porcelain`을 썼는데, porcelain은 untracked 파일의 '경로'만 찍고 '내용'은
    반영하지 않아, 이미 untracked인 .py를 마커 생성 후 수정하면 지문이 그대로여서
    미검증 코드가 스킵될 수 있었다(F1 — 검증 우회). 파일 내용을 직접 해시하면 그
    우회가 닫히고, 동시에 .py가 아닌 파일(review-results.md 등)의 변경은 지문에
    영향을 주지 않아 마커가 불필요하게 무효화되지도 않는다(F2).

    `git rev-parse HEAD` 실패(예: 최초 커밋 전) 시 '' 반환 → 마커 항상 무효(보수적
    재검증). 이 계산은 auto-dev SKILL.md T-merge 스니펫과 정확히 일치해야 한다
    (MUST MATCH — get_modified_py_files 3-쿼리, 정렬, sha256, 조인 형식, 타임아웃).
    """
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        if r.returncode != 0:
            return ""
        head = r.stdout.strip()
        parts = [head]
        for rel in sorted(get_modified_py_files()):
            abs_p = Path(rel)
            if not abs_p.is_absolute():
                abs_p = PROJECT_ROOT / rel
            try:
                content_sha = hashlib.sha256(abs_p.read_bytes()).hexdigest()
            except Exception:
                content_sha = "MISSING"
            parts.append(f"{rel}\0{content_sha}")
        return hashlib.md5("\n".join(parts).encode(), usedforsecurity=False).hexdigest()
    except Exception:
        return ""


def _consume_marker_if_valid() -> bool:
    """auto-dev 검증 마커가 '현재 검증 스코프 상태'에 유효하면 소비하고 True.

    마커 파일은 repo 스코프 공유 경로라 같은 체크아웃의 병렬 세션이 만든 것일 수
    있다. 따라서:
    - **원자적 소비**: 먼저 os.rename으로 세션 고유 이름으로 옮겨 '가로챈다'. rename은
      원자적이라 두 병렬 Stop 훅 중 한쪽만 성공하고, 진 쪽은 FileNotFoundError로
      전체 검증 경로를 탄다(F8 — 이전 exists→read→unlink는 둘 다 읽고 둘 다 스킵 가능).
    - 심볼릭링크면 즉시 무효 (CWE-59: 링크를 따라 임의 파일을 읽지 않는다).
    - 가로챈 파일 내용이 현재 _worktree_state_hash()와 일치할 때만 유효.
    - 빈 내용은 무효 — 파일 생성만으로 검증을 우회하지 못하게 한다.
    """
    if VALIDATED_MARKER.is_symlink():
        VALIDATED_MARKER.unlink(missing_ok=True)
        return False
    claimed = VALIDATED_MARKER.with_name(f"{VALIDATED_MARKER.name}.claim.{os.getpid()}")
    try:
        os.rename(VALIDATED_MARKER, claimed)
    except (FileNotFoundError, OSError):
        return False  # 마커 없음 또는 다른 프로세스가 이미 가로챔
    try:
        content = claimed.read_text(encoding="utf-8").strip()
    except Exception:
        content = ""
    valid = bool(content) and content == _worktree_state_hash()
    claimed.unlink(missing_ok=True)
    return valid


# ── 메인 ────────────────────────────────────────────────────────
def main():
    # 0. 네이티브 무한 루프 가드: 이미 stop-hook 재진입 루프 중이면 재차단 금지.
    #    (Claude는 직전 block 후 한 턴 수정을 시도했고, 그 턴의 Stop에서
    #     stop_hook_active=true로 들어온다. 여기서 멈추지 않으면 무한 반복.)
    data = _read_input()

    # 0.1. retry 카운터 세션 스코프를 **모든 allow()/reset 경로보다 먼저** 적용.
    #      stop_hook_active 가드보다 늦으면 그 경로의 reset_retry()가 스코프
    #      미적용(repo 공유) 카운터를 지워, 세션 카운터가 리셋되지 않고 누적돼
    #      cap 도달 후 실제 실패가 조용히 통과한다(fail-open) — ATK-001.
    _apply_session_scope(data.get("session_id"))

    if data.get("stop_hook_active"):
        allow()

    # 1. auto-dev Phase 5 마커 확인 → 이중 검증 방지.
    #    마커는 이름이 아니라 내용(작업트리 상태 해시)으로 유효성을 판정한다 —
    #    병렬 세션이 만든 마커나 검증 후 변경된 상태에서는 스킵하지 않는다.
    if _consume_marker_if_valid():
        allow("auto-dev validation marker found. Skipping stop-validator.")

    # 2. 변경된 .py를 '이 세션이 편집한 파일'로 스코핑 → 병렬 세션의 미커밋 .py에
    #    의한 오탐 차단. transcript 없으면 전체 dirty .py로 폴백. session_edited에
    #    더해 git-untracked .py도 union — opaque codegen(python gen.py 등)이 검증에서
    #    누락되지 않도록(적대적 리뷰 F2). 새 .py는 대개 이 세션 산출물.
    modified_files = get_modified_py_files()
    session_edited = _session_edited_files(data)
    if session_edited is not None:
        scope = session_edited | _untracked_py_files()
        modified_files = [f for f in modified_files if _real(f) in scope]

    # 3. 검증 대상 .py 없음 → 스킵
    if not modified_files:
        allow()

    # 4. max retries guard — 한계 도달 시 차단(block)이 아니라 중단(allow).
    #    block()은 "턴을 끝내지 말라"는 신호라 cap에서 block+counter reset 하면
    #    test_failure↔max_retries 사이클로 영원히 반복됐다. cap = "검증 그만, 턴 종료".
    #    stop_hook_active 미전달 환경을 위한 백스톱이기도 하다.
    retry_count = get_retry_count()
    if retry_count >= MAX_RETRIES:
        reset_retry()
        allow(
            f"[stop-validator] 자동 수정 {MAX_RETRIES}회 시도 후에도 문제가 "
            "남아 검증을 중단합니다. 수동 확인이 필요합니다."
        )

    # 5. 린트 검사
    lint_passed, _lint_errors = check_lint(modified_files)
    if not lint_passed:
        fixed, fixed_files, remaining = auto_fix_lint(modified_files)
        if fixed:
            # 정보성 메시지는 stderr로 — stdout은 decision 프로토콜 전용으로 유지.
            print(
                f"[stop-validator] ruff가 {len(fixed_files)}개 파일을 자동 수정: "
                f"{', '.join(fixed_files)}",
                file=sys.stderr,
            )
        else:
            increment_retry()
            block(
                "lint_error",
                "자동 수정 후에도 린트 오류가 남아있습니다.",
                {"errors": remaining[:2000], "files": modified_files},
            )

    # 6. 테스트 검사 (test_failure는 자동 수정 불가 → 바로 block)
    #    변경 테스트 파일만 스코프 실행, 타임아웃은 비차단(check_tests 참조).
    tests_passed, test_output = check_tests(modified_files)
    if not tests_passed:
        increment_retry()
        block(
            "test_failure",
            "테스트가 실패했습니다. 코드를 수정하세요.",
            {"output": test_output[:3000]},
        )

    allow()


def entry():
    """fail-safe 엔트리포인트: 예기치 못한 예외(예: 타 소유 상태파일 접근 시
    PermissionError)로 훅이 트레이스백 종료하면 Stop이 애매하게 막힐 수 있다 —
    안전망은 실패해도 턴을 통과시켜야 한다. allow()/block()의 SystemExit은
    Exception이 아니라 그대로 전파(정상 통과)된다.
    """
    try:
        main()
    except Exception as e:
        print(f"[stop-validator] unexpected error, allowing stop: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    entry()
