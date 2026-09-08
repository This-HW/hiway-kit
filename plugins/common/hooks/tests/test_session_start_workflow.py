"""Tests for using-hiway-kit workflow injection in session-start.py."""

import importlib.util
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "session_start", HOOKS_DIR / "session-start.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["session_start"] = _mod
_spec.loader.exec_module(_mod)

load_workflow_skill = _mod.load_workflow_skill


class TestLoadWorkflowSkill:
    def test_returns_workflow_section_when_skill_exists(self, tmp_path):
        skill_dir = tmp_path / "skills" / "using-hiway-kit"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: using-hiway-kit\n---\n\n# Using hiway-kit\n\nWorkflow content here."
        )
        result = load_workflow_skill(tmp_path)
        assert "=== WORKFLOW ===" in result
        assert "# Using hiway-kit" in result
        assert "Workflow content here." in result

    def test_strips_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "skills" / "using-hiway-kit"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: using-hiway-kit\ndescription: test\n---\n\n# Content"
        )
        result = load_workflow_skill(tmp_path)
        assert "name: using-hiway-kit" not in result
        assert "description: test" not in result
        assert "# Content" in result

    def test_returns_empty_string_when_skill_missing(self, tmp_path):
        result = load_workflow_skill(tmp_path)
        assert result == ""

    def test_fail_open_on_read_error(self, tmp_path, monkeypatch):
        skill_dir = tmp_path / "skills" / "using-hiway-kit"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("content")

        def boom(*args, **kwargs):
            raise OSError("simulated read error")

        monkeypatch.setattr(Path, "read_text", boom)
        result = load_workflow_skill(tmp_path)
        assert result == ""
