"""check_doc_counts.py 의 에이전트 평탄 배치 게이트 (5.3.0).

Claude Code 가 `agents/` 하위 폴더의 에이전트를 표시하지 않으므로(세션 로드는 정상,
`claude plugin details` 는 Agents (0)) 하위 디렉토리가 생기면 red 여야 한다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_doc_counts.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_doc_counts", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def _agent(path: Path, name: str = "a") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\n---\n", encoding="utf-8")


def test_flat_agents_pass(tmp_path, capsys):
    _agent(tmp_path / "plugins" / "common" / "agents" / "one.md", "one")
    assert mod.check_agents_flat(tmp_path) is True


def test_subdirectory_is_red_with_reason(tmp_path, capsys):
    _agent(tmp_path / "plugins" / "common" / "agents" / "dev" / "nested.md", "nested")
    assert mod.check_agents_flat(tmp_path) is False
    out = capsys.readouterr().out
    assert "plugins/common/agents/dev/" in out
    assert "Claude Code" in out and "표시하지 않는다" in out


def test_empty_subdirectory_is_red(tmp_path):
    (tmp_path / "plugins" / "common" / "agents" / "meta").mkdir(parents=True)
    assert mod.check_agents_flat(tmp_path) is False


def test_no_agents_dir_passes(tmp_path):
    assert mod.check_agents_flat(tmp_path) is True


def test_count_ignores_nested_but_main_is_red(tmp_path, monkeypatch):
    _agent(tmp_path / "plugins" / "common" / "agents" / "top.md", "top")
    _agent(tmp_path / "plugins" / "common" / "agents" / "sub" / "n.md", "n")
    assert mod.count_actuals(tmp_path)["agents"] == 1
    monkeypatch.setattr("sys.argv", ["check_doc_counts.py", "--root", str(tmp_path)])
    assert mod.main() == 1


def test_real_repo_is_flat():
    assert mod.check_agents_flat(SCRIPT.parents[1]) is True
