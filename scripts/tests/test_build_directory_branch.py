"""Unit tests for scripts/build-directory-branch.py.

Claude 디렉토리는 command 훅을 Verified 조직에게만 받는다(2026-11-06 거부). 디렉토리가 추적할
브랜치가 **훅 선언만 빠진 트리**인지, 이름이 바뀐 제외 대상을 조용히 통과시키지 않는지,
그리고 **실제 레포 HEAD 가 통과하는지**(픽스처만으로는 "동작한다"가 아니다)를 고정한다.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from module_loader import load_module_by_path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build-directory-branch.py"

mod = load_module_by_path(SCRIPT, "build_directory_branch_t")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "-q",
        "-m",
        message,
    )
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@example.com")
    _git(tmp_path, "init", "-q", "-b", "main")
    root = tmp_path / "plugins" / "common"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "kit", "version": "1.0.0"})
    )
    (root / "hooks").mkdir()
    (root / "hooks" / "hooks.json").write_text('{"hooks": {}}')
    (root / "hooks" / "session-start.py").write_text("print('x')\n")
    (root / "skills" / "a").mkdir(parents=True)
    (root / "skills" / "a" / "SKILL.md").write_text(
        "---\nname: a\ndescription: d\n---\n"
    )
    _commit_all(tmp_path, "init")
    return tmp_path


def _files(repo: Path, rev: str) -> set[str]:
    return set(_git(repo, "ls-tree", "-r", "--name-only", rev).splitlines())


def test_write_drops_only_hook_declaration(repo: Path) -> None:
    src = _git(repo, "rev-parse", "HEAD")
    assert mod.main(["--write", "--repo", str(repo)]) == 0
    files = _files(repo, "directory")
    assert "plugins/common/hooks/hooks.json" not in files
    # 선언만 뺀다 — 훅 스크립트·스킬은 그대로 (hooks/ 통째 제거는 보류를 옮길 뿐이었다)
    assert {
        "plugins/common/hooks/session-start.py",
        "plugins/common/skills/a/SKILL.md",
    } <= files
    assert _git(repo, "rev-list", "--parents", "-n1", "directory").split()[1:] == [src]
    # 작업 트리·인덱스는 건드리지 않는다
    assert (repo / "plugins/common/hooks/hooks.json").exists()
    assert _git(repo, "status", "--porcelain") == ""


def test_write_is_idempotent_and_fast_forward(repo: Path) -> None:
    mod.main(["--write", "--repo", str(repo)])
    first = _git(repo, "rev-parse", "directory")
    mod.main(["--write", "--repo", str(repo)])
    assert _git(repo, "rev-parse", "directory") == first

    (repo / "plugins/common/skills/a/SKILL.md").write_text(
        "---\nname: a\ndescription: e\n---\n"
    )
    src2 = _commit_all(repo, "change")
    mod.main(["--write", "--repo", str(repo)])
    second = _git(repo, "rev-parse", "directory")
    assert _git(repo, "rev-list", "--parents", "-n1", second).split()[1:] == [
        first,
        src2,
    ]


def test_check_does_not_touch_refs(repo: Path) -> None:
    assert mod.main(["--check", "--repo", str(repo)]) == 0
    assert (
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "rev-parse",
                "--verify",
                "--quiet",
                "refs/heads/directory",
            ],
            capture_output=True,
            check=False,
        ).returncode
        != 0
    )


def test_missing_excluded_path_fails(repo: Path) -> None:
    """뺄 파일이 원본에 없으면(이름 변경) 아무것도 빼지 않은 트리를 무훅이라 부르지 않는다."""
    _git(
        repo,
        "mv",
        "plugins/common/hooks/hooks.json",
        "plugins/common/hooks/renamed.json",
    )
    _commit_all(repo, "rename")
    with pytest.raises(SystemExit, match="뺄 파일이 없다"):
        mod.main(["--check", "--repo", str(repo)])


def test_manifest_hooks_field_fails(repo: Path) -> None:
    manifest = repo / "plugins/common/.claude-plugin/plugin.json"
    manifest.write_text(
        json.dumps({"name": "kit", "version": "1.0.0", "hooks": "./hooks/other.json"})
    )
    _commit_all(repo, "inline hooks")
    with pytest.raises(SystemExit, match="hooks 필드"):
        mod.main(["--check", "--repo", str(repo)])


def test_real_repo_head_passes() -> None:
    assert mod.main(["--check", "--repo", str(REPO_ROOT)]) == 0
