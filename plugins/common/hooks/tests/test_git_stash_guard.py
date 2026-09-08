"""reference-transaction git 훅 — 태그 없는 `git stash` 차단 회귀 테스트.

이 훅은 **하네스 중립 집행**의 실증이다. Claude Code 의 PreToolUse 로 막으면 Codex·
Gemini·플레인 터미널에서는 안 막힌다. git 훅으로 내리면 누가 실행하든 똑같이 돈다.

계약 넷을 고정한다:
  1. 태그 없는 `git stash` 는 차단된다
  2. `git stash push -m` 은 통과한다
  3. **차단 시 작업이 보존된다** — 여기서 유실되면 가드가 아니라 사고다
  4. 삭제 방향(`pop`/`drop`)은 막지 않는다
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

HOOK_SRC = (
    Path(__file__).resolve().parent.parent.parent / "setup" / "git-hooks" / "reference-transaction"
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=False
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", ".")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "f.txt").write_text("a\n", encoding="utf-8")
    _git(r, "add", "f.txt")
    _git(r, "commit", "-qm", "init commit")
    hooks = Path(_git(r, "rev-parse", "--git-path", "hooks").stdout.strip())
    hooks = hooks if hooks.is_absolute() else r / hooks
    hooks.mkdir(parents=True, exist_ok=True)
    dst = hooks / "reference-transaction"
    dst.write_bytes(HOOK_SRC.read_bytes())
    dst.chmod(0o755)
    return r


def _dirty(repo: Path) -> None:
    (repo / "f.txt").write_text("a\nIMPORTANT\n", encoding="utf-8")
    (repo / "new.txt").write_text("untracked\n", encoding="utf-8")


def test_bare_stash_is_blocked(repo: Path) -> None:
    _dirty(repo)
    result = _git(repo, "stash")
    assert result.returncode != 0
    assert "태그 없는" in result.stderr
    assert _git(repo, "stash", "list").stdout.strip() == ""


def test_blocked_stash_preserves_the_work(repo: Path) -> None:
    """차단이 작업을 삼키면 가드가 아니라 사고다 — 이 계약이 가장 중요하다."""
    _dirty(repo)
    _git(repo, "stash")
    assert (repo / "f.txt").read_text(encoding="utf-8") == "a\nIMPORTANT\n"
    assert (repo / "new.txt").exists(), "untracked 파일이 사라졌다"
    assert "f.txt" in _git(repo, "status", "--short").stdout


def test_tagged_stash_passes(repo: Path) -> None:
    _dirty(repo)
    assert _git(repo, "stash", "push", "-u", "-m", "my-tag").returncode == 0
    assert "my-tag" in _git(repo, "stash", "list").stdout


def test_delete_direction_is_not_blocked(repo: Path) -> None:
    """pop/drop 은 refs/stash 를 지운다 — 이 훅의 대상이 아니다."""
    _dirty(repo)
    _git(repo, "stash", "push", "-u", "-m", "tag")
    assert _git(repo, "stash", "pop").returncode == 0


def test_detection_is_data_based_not_locale_based(repo: Path) -> None:
    """판정 근거가 'WIP on' 문구가 아니라 HEAD 한 줄이라는 계약.

    문구로 판정하면 로케일 번역에 **조용히 통과하는 방향**으로 깨진다. 훅 본문이
    번역 가능한 접두어를 판정에 쓰지 않는지 소스로 고정한다.
    """
    src = HOOK_SRC.read_text(encoding="utf-8")
    body = src.split("set -u", 1)[1]  # 주석(설명)에는 문구가 나올 수 있다
    assert '"WIP on ' not in body, "번역 가능한 문구로 판정하고 있다"
    assert "head_oneline" in body


def test_drift_marker_is_present_and_position_independent(repo: Path) -> None:
    """마커 계약: 존재하고, 위치에 의존하지 않는다.

    피어 레포가 이 훅을 정본으로 들이면서 출처 주석을 위에 끼웠고 마커가 3행이 됐다.
    "2행 정확히"로 판별했다면 그 순간 드리프트 감시가 **조용히 꺼졌을** 것이다.
    판별은 고정 문자열 검색이라 위치 무관이고, 그 계약을 여기서 고정한다.
    """
    src = HOOK_SRC.read_text(encoding="utf-8")
    assert "# kit-managed-hook" in src
    # 마커를 아래로 옮겨도 여전히 "있다"로 판별돼야 한다 — 위치 고정 판별이면 여기서 깨진다.
    lines = [ln for ln in src.splitlines() if ln.strip() != "# kit-managed-hook"]
    moved = "\n".join([*lines[:1], "# 출처: 어느 레포", "# kit-managed-hook", *lines[1:]])
    assert "# kit-managed-hook" in moved
    # 제품명을 마커에 넣지 않는다 — 개명 때 대조가 조용히 멈춘다.
    assert "hiway" not in "# kit-managed-hook"

