"""Tests for examples/child-git-guard.py (opt-in hook, D-36)."""

import importlib.util
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

HOOKS_DIR = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = HOOKS_DIR / "examples"

_spec = importlib.util.spec_from_file_location(
    "child_git_guard", EXAMPLES_DIR / "child-git-guard.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["child_git_guard"] = _mod
_spec.loader.exec_module(_mod)

check_command = _mod.check_command


def run_main(input_data: dict) -> int:
    stdin_text = json.dumps(input_data)
    with patch("sys.stdin", StringIO(stdin_text)):
        try:
            _mod.main()
        except SystemExit as e:
            return e.code
    return 0


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo_with_worktree(tmp_path):
    """주 체크아웃 + 워크트리 1개를 만들고 (main_repo, worktree_dir)을 반환한다."""
    main_repo = tmp_path / "main"
    main_repo.mkdir()
    _git(["init", "-q"], main_repo)
    _git(["config", "user.email", "t@example.com"], main_repo)
    _git(["config", "user.name", "T"], main_repo)
    (main_repo / "a.txt").write_text("seed")
    _git(["add", "a.txt"], main_repo)
    _git(["commit", "-q", "-m", "seed"], main_repo)

    worktree_dir = tmp_path / "wt1"
    _git(["worktree", "add", "-q", "-b", "wt1-branch", str(worktree_dir)], main_repo)
    return main_repo, worktree_dir


# ── check_command: 항상 차단(bare stash/pop, reset --hard, clean -fd) ──
class TestAlwaysBlocked:
    def test_bare_stash_blocked(self):
        assert check_command("git stash") is not None

    def test_stash_pop_blocked(self):
        assert check_command("git stash pop") is not None

    def test_stash_push_with_message_allowed(self):
        assert check_command('git stash push -u -m "wip"') is None

    def test_stash_apply_with_ref_allowed(self):
        assert check_command("git stash apply stash@{0}") is None

    def test_stash_list_allowed(self):
        assert check_command("git stash list") is None

    def test_reset_hard_blocked(self):
        assert check_command("git reset --hard") is not None

    def test_reset_hard_with_ref_blocked(self):
        assert check_command("git reset --hard origin/main") is not None

    def test_reset_soft_allowed(self):
        assert check_command("git reset --soft HEAD~1") is None

    def test_clean_fd_blocked(self):
        assert check_command("git clean -fd") is not None

    def test_clean_df_blocked(self):
        assert check_command("git clean -df") is not None

    def test_clean_force_and_directory_separate_flags_blocked(self):
        assert check_command("git clean --force --directory") is not None

    def test_clean_dry_run_allowed(self):
        assert check_command("git clean -n") is None

    def test_clean_force_only_allowed(self):
        # -f 단독은 파일만 지우고 디렉토리는 남긴다 — 이 훅의 차단 대상이 아니다
        assert check_command("git clean -f") is None

    def test_chained_command_still_detected(self):
        assert check_command("cd repo && git stash pop") is not None

    def test_unrelated_command_allowed(self):
        assert check_command("git status") is None

    def test_non_git_command_allowed(self):
        assert check_command("ls -la") is None


# ── check_command: git push는 자식 세션에서만 차단 ──────────────────
class TestPushChildOnly:
    def test_push_allowed_when_no_git_repo(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # git 리포지토리 밖
        assert check_command("git push") is None

    def test_push_allowed_in_main_checkout_without_marker(self, tmp_path):
        main_repo, _ = _init_repo_with_worktree(tmp_path)
        result = subprocess.run(
            [sys.executable, str(EXAMPLES_DIR / "child-git-guard.py")],
            cwd=main_repo,
            input=json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": "git push"}}
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0

    def test_push_allowed_in_worktree_without_marker(self, tmp_path):
        _, worktree_dir = _init_repo_with_worktree(tmp_path)
        result = subprocess.run(
            [sys.executable, str(EXAMPLES_DIR / "child-git-guard.py")],
            cwd=worktree_dir,
            input=json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": "git push"}}
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0  # 마커 없음 = fail-open

    def test_push_blocked_in_worktree_with_marker(self, tmp_path):
        """되돌려-FAIL: 마커를 심으면 차단, 지우면 다시 통과한다."""
        _, worktree_dir = _init_repo_with_worktree(tmp_path)
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=worktree_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        marker_dir = (worktree_dir / git_dir / "cck").resolve()
        marker_dir.mkdir(parents=True)
        marker = marker_dir / "child.json"
        marker.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "parent": "test",
                    "role": "child",
                    "base_commit": "0" * 40,
                }
            )
        )

        result = subprocess.run(
            [sys.executable, str(EXAMPLES_DIR / "child-git-guard.py")],
            cwd=worktree_dir,
            input=json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": "git push"}}
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2, result.stderr

        marker.unlink()  # 되돌리면 다시 통과
        result2 = subprocess.run(
            [sys.executable, str(EXAMPLES_DIR / "child-git-guard.py")],
            cwd=worktree_dir,
            input=json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": "git push"}}
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result2.returncode == 0

    def test_push_allowed_in_main_checkout_even_with_marker(self, tmp_path):
        """주 체크아웃은 마커가 있어도 자식으로 취급하지 않는다(§13.6 방어선)."""
        main_repo, _ = _init_repo_with_worktree(tmp_path)
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=main_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        marker_dir = (main_repo / git_dir / "cck").resolve()
        marker_dir.mkdir(parents=True)
        (marker_dir / "child.json").write_text(json.dumps({"role": "child"}))

        result = subprocess.run(
            [sys.executable, str(EXAMPLES_DIR / "child-git-guard.py")],
            cwd=main_repo,
            input=json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": "git push"}}
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0


# ── main(): stdin/exit code 계약 ────────────────────────────────────
class TestMainContract:
    def test_non_bash_tool_passes(self):
        assert run_main({"tool_name": "Edit", "tool_input": {}}) == 0

    def test_empty_command_passes(self):
        assert run_main({"tool_name": "Bash", "tool_input": {"command": ""}}) == 0

    def test_blocked_command_exits_2(self):
        assert (
            run_main({"tool_name": "Bash", "tool_input": {"command": "git stash"}}) == 2
        )

    def test_malformed_json_fails_open(self):
        with patch("sys.stdin", StringIO("not json")):
            try:
                _mod.main()
                code = 0
            except SystemExit as e:
                code = e.code
        assert code == 0
