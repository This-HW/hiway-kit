"""Tests for examples/verify-mutate-split.py (opt-in hook).

실측 근거 n=2 (서로 독립, 같은 날 다른 두 세션):
  1. `gh pr view --json statusCheckRollup` 이 FAILURE 를 출력했는데 같은 블록의
     `gh pr merge` 가 조건 없이 실행돼 CI 실패 상태로 main 머지
  2. `pytest`/`ruff` 뒤에 `commit`·`push` 를 `;` 로 체인 — 린트 오류가 main 에 올라감
"""

import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = HOOKS_DIR / "examples"

_spec = importlib.util.spec_from_file_location(
    "verify_mutate_split", EXAMPLES_DIR / "verify-mutate-split.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["verify_mutate_split"] = _mod
_spec.loader.exec_module(_mod)

check_command = _mod.check_command


def run_main(input_data: dict) -> int:
    stdin_text = json.dumps(input_data)
    with (
        patch.object(sys, "stdin", StringIO(stdin_text)),
        pytest.raises(SystemExit) as exc,
    ):
        _mod.main()
    return exc.value.code


# ── 차단: 무조건 체인 (실측 사례 2) ────────────────────────────────────────────


@pytest.mark.parametrize(
    "command",
    [
        "pytest -q ; git push",
        "python3 -m pytest ; git commit -m x ; git push origin main",
        "ruff check . ; git push",
        "scripts/verify-done.sh\ngit push",
        "npm test & git push",
        "pytest && ruff check . ; git push",  # 중간에 `;` 하나면 체인이 끊긴다
    ],
)
def test_blocks_unconditional_chain_after_exit_code_verifier(command):
    reason = check_command(command)
    assert reason is not None
    assert "무관하게" in reason


# ── 차단: 출력 검증 뒤 상태 변경 (실측 사례 1) — `&&` 여도 막는다 ─────────────


@pytest.mark.parametrize(
    "command",
    [
        "gh pr view 266 --json statusCheckRollup && gh pr merge 266 --squash",
        "gh pr checks 12 ; gh pr merge 12",
        "gh run list --limit 1 && gh release create v1.0.0",
        "gh api repos/o/r/commits/main/status && git push",
    ],
)
def test_blocks_output_verifier_before_mutation_regardless_of_separator(command):
    reason = check_command(command)
    assert reason is not None
    assert "출력에" in reason


# ── 통과: `&&` 로 이은 종료코드 검증은 진짜 게이트다 ──────────────────────────


@pytest.mark.parametrize(
    "command",
    [
        "pytest -q && git push",
        "scripts/verify-done.sh && git push origin main",
        "ruff check . && python3 -m pytest && git push",
        "bash scripts/verify-done.sh && git push",
        "make test && npm publish",
    ],
)
def test_allows_exit_code_gated_chain(command):
    assert check_command(command) is None


# ── 통과: 오탐을 만들지 않는다 ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "command",
    [
        "git push",  # 검증이 앞에 없다
        "git push ; pytest",  # 순서가 반대 — 변경 뒤의 검증은 이 훅의 대상이 아니다
        "pytest -q",  # 상태 변경이 없다
        "git status && git push",  # CI 판정을 담지 않는 조회 — 흔하고 무해한 관용구
        "git diff ; git push",
        "git log --oneline -1 && git push",
        "echo 'pytest ; git push'",  # 따옴표 안 — 실행되는 명령이 아니다
        # `git add && git commit` 뒤의 push: **검증이 없다.** add·commit 은 검증기가
        # 아니므로 이 훅의 대상이 아니다. 외부 세션이 이 형태를 보고했으나, 실측하니
        # 훅이 막는 것은 앞에 ruff/pytest 가 있을 때였다 — 계약이 옳고 보고가 좁았다.
        "git add -A && git commit -m x\ngit push",
        "ls && cd /tmp",
    ],
)
def test_no_false_positive(command):
    assert check_command(command) is None


# ── 실사용에서 나온 형태 (외부 도입 세션 실측) ───────────────────────────────


@pytest.mark.parametrize(
    "command",
    [
        # 종료코드 검증 둘을 `&&` 로 잇고, **개행 뒤에** 변이가 온다.
        # 앞이 실패해도 다음 줄의 push 는 그대로 돈다 — 오탐이 아니라 참 양성이다.
        ".venv/bin/ruff check X && .venv/bin/ruff format X\ngit push",
        "pytest -q && ruff check .\ngit push origin main",
    ],
)
def test_blocks_and_chain_followed_by_newline_mutation(command):
    reason = check_command(command)
    assert reason is not None
    assert "무관하게" in reason


@pytest.mark.parametrize(
    "command",
    [
        # 인터프리터 경유 검증기 — toks[0] 이 인터프리터라 이름 규칙이 두 번째 토큰에
        # 걸려야 한다. 이 형태를 놓치면 "검증 뒤 변이" 판정 자체가 성립하지 않는다.
        "python scripts/verify-done.py ; git push",
        "python3 scripts/check_thing.py ; git push",
        "uv run scripts/test_x.py ; git push",
    ],
)
def test_interpreter_prefixed_verifier_is_recognized(command):
    assert check_command(command) is not None


def test_interpreter_prefixed_verifier_passes_when_and_chained():
    assert check_command("python scripts/verify-done.py && git push") is None


# ── 접두어를 걷어낸다 ─────────────────────────────────────────────────────────


def test_strips_env_and_sudo_prefixes():
    assert check_command("CI=1 pytest ; git push") is not None
    assert check_command("env FOO=bar pytest && git push") is None


def test_absolute_paths_are_matched_by_basename():
    assert check_command("/usr/local/bin/pytest ; /usr/bin/git push") is not None


# ── 훅 계약 ───────────────────────────────────────────────────────────────────


def test_main_blocks_with_exit_2():
    assert (
        run_main({"tool_name": "Bash", "tool_input": {"command": "pytest ; git push"}})
        == 2
    )


def test_main_allows_with_exit_0():
    assert (
        run_main({"tool_name": "Bash", "tool_input": {"command": "pytest && git push"}})
        == 0
    )


def test_non_bash_tool_is_ignored():
    assert (
        run_main({"tool_name": "Edit", "tool_input": {"command": "pytest ; git push"}})
        == 0
    )


def test_malformed_input_fails_open():
    with (
        patch.object(sys, "stdin", StringIO("not json")),
        pytest.raises(SystemExit) as exc,
    ):
        _mod.main()
    assert exc.value.code == 0


def test_unbalanced_quotes_fail_open_on_that_segment():
    # 파싱 불가한 세그먼트는 건너뛴다 — 훅이 예외로 죽지 않는다.
    assert check_command("pytest 'unclosed ; git push") is None
