"""Unit tests for scripts/check_agent_frontmatter.py (§2 + CI).

대상은 `plugins/*/agents/*.md` 에서 파생한다 — 그 밖의 `.md`(eval 케이스·문서)는
frontmatter 가 있어도 에이전트로 보지 않고, 에이전트인데 frontmatter 가 없으면 red 다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from module_loader import load_module_by_path

SCRIPT = Path(__file__).resolve().parent.parent / "check_agent_frontmatter.py"
GOOD = "name: {n}\ndescription: x\nmodel: sonnet\nmaxTurns: 10\n"


def _load(root: Path):
    mod = load_module_by_path(SCRIPT, "check_agent_frontmatter_t")
    mod.REPO_ROOT = root
    return mod


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _agent(root: Path, name: str, fm: str | None = None) -> None:
    body = GOOD.format(n=name) if fm is None else fm
    _write(root, f"plugins/common/agents/{name}.md", f"---\n{body}---\n\n# {name}\n")


def test_clean_agents_pass(tmp_path, capsys):
    _agent(tmp_path, "fix-bugs")
    assert _load(tmp_path).main() == 0
    assert "에이전트 1종" in capsys.readouterr().out


def test_non_agent_markdown_with_frontmatter_is_ignored(tmp_path):
    """회귀 고정 — 예전 검사는 이것을 에이전트로 보고 name/description 을 요구했다."""
    _agent(tmp_path, "fix-bugs")
    _write(
        tmp_path, "plugins/common/evals/case-a/prompt.md", "---\ntitle: x\n---\nhi\n"
    )
    _write(tmp_path, "plugins/common/docs/guide.md", "---\nstatus: current\n---\n")
    assert _load(tmp_path).main() == 0


def test_agent_without_frontmatter_is_red(tmp_path, capsys):
    """예전 검사는 frontmatter 없는 파일을 건너뛰었다 — 에이전트면 red 여야 한다."""
    _agent(tmp_path, "fix-bugs")
    _write(tmp_path, "plugins/common/agents/bare.md", "# no frontmatter\n")
    assert _load(tmp_path).main() == 1
    assert "bare.md: frontmatter 없음" in capsys.readouterr().out


@pytest.mark.parametrize("missing", ["name", "description", "model", "maxTurns"])
def test_missing_required_key_is_red(tmp_path, capsys, missing):
    fm = "".join(
        line + "\n"
        for line in GOOD.format(n="a").splitlines()
        if not line.startswith(f"{missing}:")
    )
    _agent(tmp_path, "a", fm)
    assert _load(tmp_path).main() == 1
    assert f"필수 필드 없음: {missing}" in capsys.readouterr().out


@pytest.mark.parametrize("field", ["permissionMode", "hooks", "next_agents"])
def test_forbidden_key_is_red(tmp_path, capsys, field):
    _agent(tmp_path, "a", GOOD.format(n="a") + f"{field}: x\n")
    assert _load(tmp_path).main() == 1
    assert f"금지 필드: {field}" in capsys.readouterr().out


def test_name_must_match_filename(tmp_path, capsys):
    _agent(tmp_path, "fix-bugs", GOOD.format(n="fix-bug"))
    assert _load(tmp_path).main() == 1
    assert "≠ 파일 이름 'fix-bugs'" in capsys.readouterr().out


def test_zero_agents_is_red(tmp_path):
    (tmp_path / "plugins" / "common" / "agents").mkdir(parents=True)
    assert _load(tmp_path).main() == 1


def test_real_repo_is_green():
    mod = load_module_by_path(SCRIPT, "check_agent_frontmatter_real")
    assert mod.main() == 0
