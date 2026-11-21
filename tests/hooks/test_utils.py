"""Tests for utils.py hook utilities."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

HOOKS_DIR = Path(__file__).resolve().parents[2] / "plugins" / "common" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from utils import (
    debug_log,
    get_project_root,
    has_ruff_config,
    hook_disabled,
    is_debug_mode,
    safe_path,
)


class TestSafePath:
    def test_none_returns_false(self):
        assert safe_path(None) is False

    def test_empty_string_returns_false(self):
        assert safe_path("") is False

    def test_normal_path_allowed(self):
        assert safe_path("/home/user/project/main.py") is True

    def test_relative_path_allowed(self):
        assert safe_path("src/main.py") is True

    def test_path_traversal_blocked(self):
        assert safe_path("../../etc/passwd") is False

    def test_path_traversal_in_middle_blocked(self):
        assert safe_path("/home/user/../../../etc/passwd") is False

    def test_dotdot_as_filename_component_allowed(self):
        # "my..file" — ".." is a substring but not a path component
        assert safe_path("/app/my..file.py") is True

    def test_single_dot_allowed(self):
        assert safe_path("./src/main.py") is True

    def test_root_path_allowed(self):
        assert safe_path("/etc/hosts") is True


class TestIsDebugMode:
    def test_debug_off_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_HOOK_DEBUG", None)
            assert is_debug_mode() is False

    def test_debug_on_with_1(self):
        with patch.dict(os.environ, {"CLAUDE_HOOK_DEBUG": "1"}):
            assert is_debug_mode() is True

    def test_debug_on_with_true(self):
        with patch.dict(os.environ, {"CLAUDE_HOOK_DEBUG": "true"}):
            assert is_debug_mode() is True

    def test_debug_on_with_yes(self):
        with patch.dict(os.environ, {"CLAUDE_HOOK_DEBUG": "yes"}):
            assert is_debug_mode() is True

    def test_debug_off_with_false(self):
        with patch.dict(os.environ, {"CLAUDE_HOOK_DEBUG": "false"}):
            assert is_debug_mode() is False

    def test_debug_off_with_0(self):
        with patch.dict(os.environ, {"CLAUDE_HOOK_DEBUG": "0"}):
            assert is_debug_mode() is False


class TestDebugLog:
    def test_does_not_print_when_debug_off(self, capsys):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_HOOK_DEBUG", None)
            debug_log("should not appear")
        captured = capsys.readouterr()
        assert "should not appear" not in captured.err

    def test_prints_when_debug_on(self, capsys):
        with patch.dict(os.environ, {"CLAUDE_HOOK_DEBUG": "1"}):
            debug_log("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.err

    def test_handles_error_arg(self, capsys):
        with patch.dict(os.environ, {"CLAUDE_HOOK_DEBUG": "1"}):
            try:
                raise ValueError("test error")
            except ValueError as e:
                debug_log("with error", e)
        captured = capsys.readouterr()
        assert "with error" in captured.err


class TestGetProjectRoot:
    def test_uses_env_var_when_set(self, tmp_path):
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            result = get_project_root()
        assert result == str(tmp_path)

    def test_finds_git_dir(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)
        with (
            patch("os.getcwd", return_value=str(subdir)),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
            result = get_project_root()
        assert result == str(tmp_path)

    def test_falls_back_to_cwd_when_no_git(self, tmp_path):
        with (
            patch("os.getcwd", return_value=str(tmp_path)),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
            # tmp_path won't have .git going all the way to root
            result = get_project_root()
        # Should return some valid path (either tmp_path or actual git root above it)
        assert isinstance(result, str)
        assert len(result) > 0


def _repo(tmp_path: Path) -> Path:
    """레포 루트(.git)와 그 아래 파일 하나 — 탐색은 루트에서 멈춘다."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "jobs").mkdir()
    target = root / "jobs" / "daily.py"
    target.write_text("x = 1\n")
    return target


class TestHasRuffConfig:
    """외부 설치 보고(2026-11-09): ruff 를 쓰지 않는 레포에서 훅이 ruff 를 돌려 손대지 않은
    import 를 지웠다. 프로젝트 설정만 ruff 사용 동의로 본다."""

    def test_no_config_is_not_consent(self, tmp_path):
        assert not has_ruff_config(str(_repo(tmp_path)))

    def test_ruff_toml_at_repo_root(self, tmp_path):
        target = _repo(tmp_path)
        (tmp_path / "repo" / "ruff.toml").write_text("")
        assert has_ruff_config(str(target))

    def test_dot_ruff_toml_next_to_file(self, tmp_path):
        target = _repo(tmp_path)
        (target.parent / ".ruff.toml").write_text("")
        assert has_ruff_config(str(target))

    def test_pyproject_with_tool_ruff_section(self, tmp_path):
        target = _repo(tmp_path)
        (tmp_path / "repo" / "pyproject.toml").write_text(
            "[project]\nname = 'x'\n\n  [tool.ruff.lint]  # rules\nselect = ['F']\n"
        )
        assert has_ruff_config(str(target))

    def test_pyproject_without_tool_ruff_is_not_consent(self, tmp_path):
        target = _repo(tmp_path)
        (tmp_path / "repo" / "pyproject.toml").write_text(
            "[project]\nname = 'x'\n# [tool.ruff] is mentioned in a comment\n[tool.ruffle]\n"
        )
        assert not has_ruff_config(str(target))

    def test_config_above_repo_root_is_ignored(self, tmp_path):
        """레포 밖(상위 디렉토리)의 설정은 그 레포의 동의가 아니다."""
        target = _repo(tmp_path)
        (tmp_path / "ruff.toml").write_text("")
        assert not has_ruff_config(str(target))


class TestHookDisabled:
    def test_unset_enables_everything(self, monkeypatch):
        monkeypatch.delenv("HIWAY_KIT_DISABLE_HOOKS", raising=False)
        assert not hook_disabled("auto-format")

    def test_comma_list_with_spaces_and_case(self, monkeypatch):
        monkeypatch.setenv("HIWAY_KIT_DISABLE_HOOKS", " Auto-Format , stop-validator ")
        assert hook_disabled("auto-format")
        assert hook_disabled("stop-validator")
        assert not hook_disabled("protect-sensitive")

    def test_all_disables_every_hook(self, monkeypatch):
        monkeypatch.setenv("HIWAY_KIT_DISABLE_HOOKS", "all")
        assert hook_disabled("session-start")
        assert hook_disabled("protect-sensitive")
