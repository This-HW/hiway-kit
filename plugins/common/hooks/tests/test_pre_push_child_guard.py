"""pre-push git 훅 — 자식 워크트리의 push 차단 회귀 테스트.

이 훅은 **하네스 중립 집행**의 두 번째 실증이다. 같은 차단이 이미
`hooks/examples/child-git-guard.py` 에 있지만 그것은 PreToolUse 라 Claude Code 에서만
돈다 — 실측으로 Codex 워커에서는 기계 강제가 0 이었다. git 훅은 누가 실행하든 돈다.

계약 일곱을 고정한다:
  1. 자식 마커가 있는 워크트리의 push 는 차단된다
  2. 마커가 없으면 통과한다(fail-open) — 없는 보호를 있다고 믿게 하지 않는다
  3. 주 체크아웃은 마커가 있어도 통과한다(자식으로 *승격*하지 않는다)
  4. 탈출구 환경변수로 우회가 성립한다
  5. 모르는 스키마·손상된 마커는 통과한다(fail-open, child-git-guard 와 동일)
  6. **차단해도 커밋은 보존되고 원격에는 아무것도 가지 않는다**
  7. 마커 경로가 `child-git-guard.py` 의 `MARKER_REL` 과 **같다** — 갈리면 그 자체가 결함
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

HOOKS_ROOT = Path(__file__).resolve().parent.parent
HOOK_SRC = HOOKS_ROOT.parent / "setup" / "git-hooks" / "pre-push"
GUARD_SRC = HOOKS_ROOT / "examples" / "child-git-guard.py"

MARKER = {
    "schema": 1,
    "parent": "control",
    "role": "worker",
    "base_commit": "0" * 40,
}


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None):
    run_env = None
    if env is not None:
        run_env = {**os.environ, **env}
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True,
        check=False, env=run_env,
    )


def _hooks_dir(repo: Path) -> Path:
    raw = Path(_git(repo, "rev-parse", "--git-path", "hooks").stdout.strip())
    return raw if raw.is_absolute() else repo / raw


def _gitdir(repo: Path) -> Path:
    raw = Path(_git(repo, "rev-parse", "--git-dir").stdout.strip())
    return raw if raw.is_absolute() else repo / raw


def _write_marker(repo: Path, data: object) -> Path:
    d = _gitdir(repo) / "kit"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "child.json"
    p.write_text(
        data if isinstance(data, str) else json.dumps(data, indent=2), encoding="utf-8"
    )
    return p


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """주 저장소 + 로컬 bare 원격 + 설치된 pre-push 훅. 네트워크를 쓰지 않는다."""
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", str(remote))
    r = tmp_path / "main"
    r.mkdir()
    _git(r, "init", "-q", ".")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    _git(r, "remote", "add", "origin", str(remote))
    (r / "f.txt").write_text("a\n", encoding="utf-8")
    _git(r, "add", "f.txt")
    _git(r, "commit", "-qm", "init commit")
    hooks = _hooks_dir(r)
    hooks.mkdir(parents=True, exist_ok=True)
    dst = hooks / "pre-push"
    dst.write_bytes(HOOK_SRC.read_bytes())
    dst.chmod(0o755)
    return r


@pytest.fixture
def child(repo: Path) -> Path:
    """자식 워크트리 — 훅은 주 저장소에 깔려 있고 공유 hooks 디렉토리로 도달한다."""
    wt = repo.parent / "child-wt"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", "feat")
    (wt / "g.txt").write_text("work\n", encoding="utf-8")
    _git(wt, "add", "g.txt")
    _git(wt, "commit", "-qm", "worker commit")
    return wt


def _push(wt: Path, env: dict[str, str] | None = None):
    return _git(wt, "push", "origin", "feat", env=env)


# ── 1. 마커가 있으면 차단 ────────────────────────────────────────────────────


def test_child_worktree_push_is_blocked(repo: Path, child: Path) -> None:
    _write_marker(child, MARKER)
    result = _push(child)
    assert result.returncode != 0, result.stderr
    assert "자식 세션 워크트리" in result.stderr


def test_shared_hooks_dir_reaches_the_worktree(repo: Path, child: Path) -> None:
    """훅은 **주 저장소에만** 깔았다 — 워크트리에 따로 깐 적이 없다.

    이 훅의 설계가 성립하는 근거(공유 설치 + 국소 판정)를 고정한다. 워크트리가
    자기 hooks 디렉토리를 갖는다면 여기서 깨진다.
    """
    assert not (_gitdir(child) / "hooks" / "pre-push").exists()
    assert _hooks_dir(child).resolve() == _hooks_dir(repo).resolve()
    _write_marker(child, MARKER)
    assert _push(child).returncode != 0


def test_blocked_push_sends_nothing_and_keeps_the_commit(repo: Path, child: Path) -> None:
    """차단이 작업을 삼키거나 원격을 절반만 갱신하면 가드가 아니라 사고다."""
    _write_marker(child, MARKER)
    head_before = _git(child, "rev-parse", "HEAD").stdout.strip()
    assert _push(child).returncode != 0
    assert _git(child, "rev-parse", "HEAD").stdout.strip() == head_before
    assert (child / "g.txt").read_text(encoding="utf-8") == "work\n"
    remote = repo.parent / "remote.git"
    assert _git(remote, "rev-parse", "--verify", "refs/heads/feat").returncode != 0


# ── 2. 마커가 없으면 통과 (fail-open) ────────────────────────────────────────


def test_worktree_without_marker_passes(repo: Path, child: Path) -> None:
    assert not (_gitdir(child) / "kit" / "child.json").exists()
    result = _push(child)
    assert result.returncode == 0, result.stderr


# ── 3. 주 체크아웃은 승격되지 않는다 ─────────────────────────────────────────


def test_main_checkout_passes_even_with_marker(repo: Path) -> None:
    """마커는 자식임을 *확인*하는 것이지 부모가 쓰는 자리를 자식으로 *승격*하지 않는다."""
    _write_marker(repo, MARKER)
    result = _git(repo, "push", "origin", "main")
    assert result.returncode == 0, result.stderr


# ── 4. 탈출구 ────────────────────────────────────────────────────────────────


def test_escape_hatch_allows_the_push(repo: Path, child: Path) -> None:
    _write_marker(child, MARKER)
    assert _push(child).returncode != 0
    result = _push(child, env={"KIT_ALLOW_CHILD_PUSH": "1"})
    assert result.returncode == 0, result.stderr
    remote = repo.parent / "remote.git"
    assert _git(remote, "rev-parse", "--verify", "refs/heads/feat").returncode == 0


def test_block_message_prints_the_escape_hatch(repo: Path, child: Path) -> None:
    """막기만 하고 푸는 법을 안 알려주는 훅은 사람이 훅 자체를 지운다."""
    _write_marker(child, MARKER)
    err = _push(child).stderr
    assert "KIT_ALLOW_CHILD_PUSH=1" in err
    assert "rm" in err  # 마커 삭제·훅 해제 경로


def test_escape_hatch_only_honours_exact_value(repo: Path, child: Path) -> None:
    """빈 값·임의 값으로 조용히 열리면 탈출구가 아니라 구멍이다."""
    _write_marker(child, MARKER)
    for value in ("", "0", "yes", "true"):
        assert _push(child, env={"KIT_ALLOW_CHILD_PUSH": value}).returncode != 0, value


# ── 5. 스키마 검증 (child-git-guard 와 동일한 fail-open) ─────────────────────


@pytest.mark.parametrize(
    "marker",
    [
        pytest.param("not json at all", id="corrupt"),
        pytest.param({**MARKER, "schema": 2}, id="unknown-schema-version"),
        pytest.param({k: v for k, v in MARKER.items() if k != "base_commit"},
                     id="missing-base_commit"),
        pytest.param({**MARKER, "parent": ""}, id="empty-parent"),
        pytest.param({"schema": 1, "parent": "p", "role": "r", "baseline_commit": "x"},
                     id="wrong-key-name"),
    ],
)
def test_invalid_marker_fails_open(repo: Path, child: Path, marker: object) -> None:
    """모르는/손상된 마커는 판정 불가 = 보호하지 않는다.

    `wrong-key-name` 케이스가 특히 중요하다 — 실측으로 두 세션이 `base_commit` 과
    `baseline_commit` 으로 갈렸다. 스키마 검증이 없으면 "파일이 있으면 자식"이 되어
    키가 갈려도 통과한다.
    """
    _write_marker(child, marker)
    result = _push(child)
    assert result.returncode == 0, result.stderr


def test_compact_json_marker_is_recognised(repo: Path, child: Path) -> None:
    """들여쓰기 없는 한 줄 JSON 도 같은 판정이어야 한다(포맷에 의존하지 않는다)."""
    _write_marker(child, json.dumps(MARKER, separators=(",", ":")))
    assert _push(child).returncode != 0


# ── 6. 두 훅이 같은 것을 본다 ────────────────────────────────────────────────


def test_marker_path_matches_child_git_guard(repo: Path) -> None:
    """두 훅이 다른 마커를 보면 한쪽은 막고 한쪽은 통과하는 상태를 아무도 설명 못 한다."""
    guard = GUARD_SRC.read_text(encoding="utf-8")
    assert 'MARKER_REL = ("kit", "child.json")' in guard
    hook = HOOK_SRC.read_text(encoding="utf-8")
    assert "kit/child.json" in hook


def test_hook_documents_undetectable_dry_run(repo: Path) -> None:
    """탐지할 수 없는 것은 탐지할 수 없다고 적는다(warning-signal.md).

    dry-run 을 휴리스틱으로 추정해 통과시키는 코드가 들어오면 이 계약이 깨진다.
    """
    src = HOOK_SRC.read_text(encoding="utf-8")
    assert "--dry-run" in src
    body = src.split("set -u", 1)[1]
    assert "dry" not in body.lower(), "dry-run 을 판정에 쓰고 있다 — 구분할 신호가 없다"


def test_hook_consumes_stdin(repo: Path) -> None:
    """읽지 않고 종료하면 환경에 따라 SIGPIPE/EPIPE 가 난다."""
    body = HOOK_SRC.read_text(encoding="utf-8").split("set -u", 1)[1]
    assert "cat >/dev/null" in body


# ── 7. 드리프트 마커 계약 (reference-transaction 과 동일) ────────────────────


def test_drift_marker_is_present_and_has_no_product_name(repo: Path) -> None:
    src = HOOK_SRC.read_text(encoding="utf-8")
    assert "# kit-managed-hook" in src
    assert "hiway" not in "# kit-managed-hook"
    assert src.splitlines()[0] == "#!/bin/bash"
