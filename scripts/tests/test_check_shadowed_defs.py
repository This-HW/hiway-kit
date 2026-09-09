"""Unit tests for scripts/check_shadowed_defs.py — 사각지대 회귀 방지 (ATK-005b/c).

이 게이트의 0-대상 정책(`검사 대상 0개는 green 이 아니다`)은 원래 옳았다. 깨져 있던
것은 그 옆의 두 가지다:

- **005b** `git ls-files` 를 `-z` 없이 불러 비-ASCII `.py` 가 8진 이스케이프로 나왔고,
  `ast.parse` 가 `OSError` 를 내면 `return {}` 로 **조용히 건너뛰어졌다** — 한글
  파일명 하나가 곧 그림자 정의 검사의 사각지대였다.
- **005c** 그 건너뜀이 집계되지 않았고, 성공 줄의 `({len(files)}개 파일)` 은 **시도한
  수**였지 파싱한 수가 아니었다 — 전부 못 읽어도 초록으로 나왔다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))  # 스크립트가 옆의 git_tracked 를 import 한다

from module_loader import load_module_by_path

SHADOWED_SOURCE = "def helper():\n    return 1\n\n\ndef helper():\n    return 2\n"


def _init_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    return root


def _commit_all(root: Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)


def _load(root: Path):
    mod = load_module_by_path(
        SCRIPTS_DIR / "check_shadowed_defs.py", "check_shadowed_defs_t"
    )
    mod.REPO_ROOT = root
    return mod


def test_no_python_files_is_red(tmp_path, capsys):
    """0-대상 정책 고정 — `check_old_names` 를 여기에 맞췄으므로 되돌아가지 않게 못 박는다."""
    root = _init_repo(tmp_path)
    (root / "readme.md").write_text("no python here\n", encoding="utf-8")
    _commit_all(root)

    assert _load(root).main() == 1
    assert "검사 대상 0개는 green 이 아니다" in capsys.readouterr().out


def test_non_ascii_filename_is_actually_scanned(tmp_path, capsys):
    """005b — 한글 `.py` 안의 그림자 정의가 실제로 잡혀야 한다."""
    root = _init_repo(tmp_path)
    (root / "한글모듈.py").write_text(SHADOWED_SOURCE, encoding="utf-8")
    _commit_all(root)

    assert _load(root).main() == 1
    out = capsys.readouterr().out
    assert "한글모듈.py: helper x2" in out


def test_unparseable_file_is_tallied_and_red(tmp_path, capsys):
    """005c — 파싱 못 한 `.py` 는 개수·비율·경로와 함께 red 다."""
    root = _init_repo(tmp_path)
    (root / "clean.py").write_text("def only_once():\n    return 1\n", encoding="utf-8")
    (root / "broken.py").write_text("def oops(:\n", encoding="utf-8")
    _commit_all(root)

    assert _load(root).main() == 1
    out = capsys.readouterr().out
    assert "검사하지 못한 파일 1건" in out
    assert "broken.py" in out
    assert "문법오류" in out
    assert "%" in out


def test_success_line_reports_parsed_not_attempted(tmp_path, capsys):
    """005c — 성공 줄의 숫자는 **실제로 파싱한 수**여야 한다."""
    root = _init_repo(tmp_path)
    for i in range(3):
        (root / f"m{i}.py").write_text(f"def f{i}():\n    return {i}\n", encoding="utf-8")
    _commit_all(root)

    assert _load(root).main() == 0
    assert "3개 파일 파싱 / 시도 3개" in capsys.readouterr().out
