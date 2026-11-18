"""Unit tests for scripts/check_consumer_footprint.py (verify-done §30)."""

from __future__ import annotations

from pathlib import Path

from module_loader import load_module_by_path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
mod = load_module_by_path(REPO_ROOT / "scripts" / "check_consumer_footprint.py", "check_consumer_footprint_t")


def _shipped(tmp_path: Path, body: str) -> Path:
    root = tmp_path / "plugins" / "common" / "agents"
    root.mkdir(parents=True)
    (root / "a.md").write_text(body, encoding="utf-8")
    return tmp_path / "plugins" / "common"


def test_install_instruction_fails(tmp_path, monkeypatch):
    """2026-11-09 의 verify-code 형태 — 읽기 전용이라면서 설치를 지시했다."""
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    root = _shipped(tmp_path, "```bash\nnpm ci\npip install -r requirements.txt\nnpx tsc --noEmit\n```\n")
    assert [command for _, _, command in mod.violations(root)] == ["npm ci", "pip install", "npx t"]


def test_marked_prohibition_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    root = _shipped(tmp_path, "`npm ci`·`npx` 는 쓰지 않는다 <!-- footprint-ok: 금지 문장 -->\n")
    assert mod.violations(root) == []


def test_similar_words_are_not_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    root = _shipped(tmp_path, "npm run lint · npm test · pipeline install notes · uv run pytest\n")
    assert mod.violations(root) == []


def test_real_shipped_tree_passes():
    """픽스처만으로는 '동작한다'가 아니다 — 실제 배포 트리도 통과해야 한다."""
    assert mod.violations() == []


def test_flagged_runners_and_reasonless_opt_out(tmp_path, monkeypatch):
    """리뷰 ATK-008 — 옵션이 앞선 npx, dlx·bunx, 이유 없는 예외 표시."""
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    root = _shipped(tmp_path, "npx -y tsc\npnpm dlx eslint\nbunx prettier\nnpm ci <!-- footprint-ok -->\n")
    assert [command for _, _, command in mod.violations(root)] == ["npx -y t", "pnpm dlx", "bunx", "npm ci"]
