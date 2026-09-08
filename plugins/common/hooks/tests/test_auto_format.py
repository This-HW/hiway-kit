"""Tests for auto-format.py hook."""

import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "auto_format", HOOKS_DIR / "auto-format.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["auto_format"] = _mod
_spec.loader.exec_module(_mod)

run_pipeline = _mod.run_pipeline
_validate_path = _mod._validate_path
_has_eslint_config = _mod._has_eslint_config


def run_main(input_data: dict) -> int:
    stdin_text = json.dumps(input_data)
    with patch("sys.stdin", StringIO(stdin_text)):
        try:
            _mod.main()
        except SystemExit as e:
            return e.code
    return 0


class TestValidatePath:
    def test_returns_none_for_path_traversal(self):
        assert _validate_path("../../etc/passwd") is None

    def test_returns_none_for_nonexistent_file(self):
        assert _validate_path("/nonexistent/path/file.py") is None

    def test_returns_none_for_empty(self):
        assert _validate_path("") is None

    def test_returns_abspath_for_valid_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        result = _validate_path(str(f))
        assert result == str(f)

    def test_returns_none_for_symlink(self, tmp_path):
        real = tmp_path / "real.py"
        real.write_text("x = 1\n")
        link = tmp_path / "link.py"
        link.symlink_to(real)
        assert _validate_path(str(link)) is None


class TestHasEslintConfig:
    def test_no_config_returns_false(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("const x = 1;")
        assert _has_eslint_config(str(f)) is False

    def test_eslintrc_in_same_dir_returns_true(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("const x = 1;")
        (tmp_path / ".eslintrc.json").write_text("{}")
        assert _has_eslint_config(str(f)) is True

    def test_eslint_config_js_in_parent_returns_true(self, tmp_path):
        subdir = tmp_path / "src"
        subdir.mkdir()
        f = subdir / "app.js"
        f.write_text("const x = 1;")
        (tmp_path / "eslint.config.js").write_text("module.exports = {};")
        assert _has_eslint_config(str(f)) is True


class TestRunPipeline:
    def test_unknown_extension_returns_0(self, tmp_path):
        f = tmp_path / "file.xyz"
        f.write_text("data")
        assert run_pipeline(str(f)) == 0

    def test_invalid_path_returns_0(self):
        assert run_pipeline("/nonexistent/path/file.py") == 0

    def test_path_traversal_returns_0(self):
        assert run_pipeline("../../etc/passwd") == 0

    def test_python_file_no_tools_returns_0(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch.object(_mod, "_has_tool", return_value=False):
            assert run_pipeline(str(f)) == 0

    def test_pipeline_step_timeout_returns_0(self, tmp_path):
        import subprocess

        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with (
            patch.object(_mod, "_has_tool", return_value=True),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", 10)),
        ):
            result = run_pipeline(str(f))
        assert result == 0

    def test_pipeline_collects_ruff_feedback(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("import os\nx=1\n")
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "test.py:1:1: F401 unused import\n"
        mock_result.stderr = ""

        def fake_run(cmd, **kwargs):
            if "check" in cmd and "--fix" not in cmd:
                return mock_result
            ok = MagicMock()
            ok.returncode = 0
            ok.stdout = ""
            ok.stderr = ""
            return ok

        with (
            patch.object(_mod, "_has_tool", return_value=True),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_pipeline(str(f))
        assert result == 2


class TestMainIntegration:
    def test_non_edit_write_tool_exits_0(self):
        code = run_main({"tool_name": "Read", "tool_input": {"file_path": "/app/f.py"}})
        assert code == 0

    def test_missing_file_path_exits_0(self):
        code = run_main({"tool_name": "Edit", "tool_input": {}})
        assert code == 0

    def test_malformed_json_exits_0(self):
        with patch("sys.stdin", StringIO("not json")):
            try:
                _mod.main()
            except SystemExit as e:
                assert e.code == 0

    def test_bash_tool_exits_0(self):
        code = run_main({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert code == 0
