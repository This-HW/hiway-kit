"""Unit tests for scripts/check_old_names.py — false-green 경로 회귀 방지 (ATK-005).

세 결함을 각각 고정한다:

- **005a** `previousNames` 가 비면 exit 0 이었다 — 검사 대상 0개인 채 영원히 초록.
- **005b** `git ls-files` 를 `-z` 없이 불러 비-ASCII 파일명이 8진 이스케이프로 나왔고,
  그 경로는 열리지 않아 **조용히 건너뛰어졌다**.
- **005c** 읽기 실패를 `continue` 로 삼켜 몇 개를 못 읽었는지 보고하지 않았다.

`test_derive_name.py` 관례대로 실제 레포를 건드리지 않는다 — 모듈을 로드한 뒤
`REPO_ROOT`/`POLICY` 를 임시 git 레포로 갈아끼운다.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))  # 스크립트가 옆의 git_tracked 를 import 한다

from module_loader import load_module_by_path

OLD_NAME = "fixture-oldkit"


def _init_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "packaging").mkdir()
    return root


def _write_policy(root: Path, previous_names: list[str]) -> None:
    (root / "packaging" / "name-targets.json").write_text(
        json.dumps({"previousNames": previous_names, "oldNameScanExclude": ["docs/"]}),
        encoding="utf-8",
    )


def _commit_all(root: Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)


def _load(root: Path):
    mod = load_module_by_path(SCRIPTS_DIR / "check_old_names.py", "check_old_names_t")
    mod.REPO_ROOT = root
    mod.POLICY = root / "packaging" / "name-targets.json"
    return mod


def test_empty_previous_names_is_red(tmp_path, capsys):
    """005a — 검사할 이름이 0개면 통과가 아니라 설정 결함이다."""
    root = _init_repo(tmp_path)
    _write_policy(root, [])
    (root / "clean.md").write_text("nothing here\n", encoding="utf-8")
    _commit_all(root)

    assert _load(root).main() == 1
    out = capsys.readouterr().out
    assert "검사할 이름이 0개다" in out
    assert "통과가 아니라 설정 결함" in out


def test_non_ascii_filename_is_actually_scanned(tmp_path, capsys):
    """005b — 한글 파일명 안의 구 이름이 실제로 잡혀야 한다.

    수정 전에는 `git ls-files` 가 `"\\355\\225\\234..."` 를 내놓아 열리지 않았고,
    그 파일은 **건너뛰어진 채 exit 0** 이었다.
    """
    root = _init_repo(tmp_path)
    _write_policy(root, [OLD_NAME])
    (root / "한글-파일.md").write_text(f"install {OLD_NAME} now\n", encoding="utf-8")
    _commit_all(root)

    assert _load(root).main() == 1
    out = capsys.readouterr().out
    assert "한글-파일.md:1" in out
    assert OLD_NAME in out


def test_unreadable_file_is_tallied_and_red(tmp_path, capsys):
    """005c — 추적되지만 읽을 수 없는 파일은 개수·비율·경로와 함께 red 다."""
    root = _init_repo(tmp_path)
    _write_policy(root, [OLD_NAME])
    (root / "gone.md").write_text("placeholder\n", encoding="utf-8")
    (root / "clean.md").write_text("fine\n", encoding="utf-8")
    _commit_all(root)
    (root / "gone.md").unlink()  # 추적 중이지만 워킹트리에 없다 → OSError

    assert _load(root).main() == 1
    out = capsys.readouterr().out
    assert "검사하지 못한 파일 1건" in out
    assert "gone.md" in out
    assert "%" in out  # 비율이 사람에게 보여야 한다
    assert "사각지대" in out


# ── D14: 변경 이력은 항목 본문만 제외한다 (감사 B-P2-3) ───────────────────────────


def _policy_with_exclude_from(root: Path, marker: str = "## [") -> None:
    (root / "packaging" / "name-targets.json").write_text(
        json.dumps(
            {
                "previousNames": [OLD_NAME],
                "oldNameScanExclude": ["docs/", "packaging/name-targets.json"],
                "oldNameScanExcludeFrom": {"CHANGELOG.md": marker},
            }
        ),
        encoding="utf-8",
    )


def test_changelog_header_is_scanned_but_entry_bodies_are_not(tmp_path, capsys):
    """되돌려-FAIL: 머리말의 구 이름은 red, 같은 이름이 항목 본문에 있으면 green."""
    root = _init_repo(tmp_path)
    _policy_with_exclude_from(root)
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\nAll notable changes to {OLD_NAME}.\n\n## [1.0.0]\n- renamed from {OLD_NAME}\n",
        encoding="utf-8",
    )
    _commit_all(root)
    assert _load(root).main() == 1
    out = capsys.readouterr().out
    assert "CHANGELOG.md:3" in out
    assert "CHANGELOG.md:6" not in out

    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\nAll notable changes to the kit.\n\n## [1.0.0]\n- renamed from {OLD_NAME}\n",
        encoding="utf-8",
    )
    _commit_all(root)
    assert _load(root).main() == 0


def test_changelog_without_the_marker_is_scanned_whole(tmp_path, capsys):
    """마커가 사라진 채 파일 전체가 조용히 제외되는 쪽이 위험하다 — 마커 없으면 전량 검사."""
    root = _init_repo(tmp_path)
    _policy_with_exclude_from(root)
    (root / "CHANGELOG.md").write_text(
        f"no entries yet, but {OLD_NAME}\n", encoding="utf-8"
    )
    _commit_all(root)
    assert _load(root).main() == 1
    assert "CHANGELOG.md:1" in capsys.readouterr().out


def test_real_policy_no_longer_excludes_changelog_wholesale():
    policy = json.loads(
        (SCRIPTS_DIR.parent / "packaging" / "name-targets.json").read_text()
    )
    assert "CHANGELOG.md" not in policy["oldNameScanExclude"]
    assert policy["oldNameScanExcludeFrom"]["CHANGELOG.md"] == "## ["
