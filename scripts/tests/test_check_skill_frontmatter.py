"""Unit tests for scripts/check_skill_frontmatter.py (§25, W-045 R2).

스킬 frontmatter 의 `effort` 는 로드한 세션의 effort 를 세션 끝까지 덮어쓴다(양성 대조
[confirmed 2026-09-27]). 게이트가 red 를 내는 조건과, 검사하지 못한 것을 green 으로
세지 않는 조건을 고정한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from module_loader import load_module_by_path

SCRIPT = Path(__file__).resolve().parent.parent / "check_skill_frontmatter.py"


def _load(root: Path):
    mod = load_module_by_path(SCRIPT, "check_skill_frontmatter_t")
    mod.REPO_ROOT = root
    return mod


def _skill(root: Path, name: str, frontmatter: str, body: str = "# body\n") -> None:
    d = root / "plugins" / "common" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")


def test_clean_skills_pass(tmp_path, capsys):
    _skill(tmp_path, "a", "name: a\ndescription: x\n")
    assert _load(tmp_path).main() == 0
    assert "스킬 1종 모두" in capsys.readouterr().out


@pytest.mark.parametrize("line", ["effort: high", "model: opus", "effort:max"])
def test_forbidden_key_is_red(tmp_path, capsys, line):
    """되돌려-FAIL 의 단위판 — 스킬 하나에 `effort: high` 를 넣으면 red."""
    _skill(tmp_path, "a", "name: a\ndescription: x\n")
    _skill(tmp_path, "b", f"name: b\ndescription: x\n{line}\n")
    assert _load(tmp_path).main() == 1
    out = capsys.readouterr().out
    assert "plugins/common/skills/b/SKILL.md" in out
    assert "skills/a/" not in out


def test_body_templates_are_not_frontmatter(tmp_path):
    """본문의 Task 호출 템플릿(`model: sonnet`)은 위임 에이전트 것이라 대상이 아니다."""
    _skill(
        tmp_path,
        "a",
        "name: a\ndescription: x\n",
        body="```\nmodel: sonnet\neffort: high\n```\n",
    )
    assert _load(tmp_path).main() == 0


def test_nested_skill_dir_is_covered(tmp_path):
    """대상은 나열이 아니라 파생 — 다른 플러그인·하위 디렉토리의 스킬도 본다."""
    d = tmp_path / "plugins" / "other" / "skills" / "group" / "deep"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: deep\neffort: low\n---\n", encoding="utf-8")
    assert _load(tmp_path).main() == 1


@pytest.mark.parametrize("text", ["# no frontmatter\n", "---\nname: a\neffort: high\n"])
def test_unreadable_frontmatter_is_red(tmp_path, capsys, text):
    """구분자가 없거나 닫히지 않으면 검사 불가 — green 으로 세지 않는다."""
    d = tmp_path / "plugins" / "common" / "skills" / "a"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    assert _load(tmp_path).main() == 1
    assert "검사 불가" in capsys.readouterr().out


def test_zero_skills_is_red(tmp_path):
    (tmp_path / "plugins").mkdir()
    assert _load(tmp_path).main() == 1


def test_exempt_skill_is_skipped(tmp_path):
    _skill(tmp_path, "a", "name: a\neffort: high\n")
    mod = _load(tmp_path)
    mod.EXEMPT = {"a": "test"}
    assert mod.main() == 0
