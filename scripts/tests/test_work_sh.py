"""Unit tests for scripts/work.sh (W-025 Track B / Worker C, D-29 · D-41 · D-51).

`work.sh`는 셸 스크립트라 파이썬 모듈로 import할 수 없다 — `subprocess`로 호출하고
종료코드·stdout·stderr·생성 파일을 검사한다. 전부 스크래치 사본(`tmp_path`)의 진짜
git 레포에서 돈다 — 실제 레포의 `docs/works/`·`.git`은 절대 건드리지 않는다
(`scripts/tests/test_bump_version.py`와 동일 원칙: 스크립트를 스크래치 `scripts/`로
복사하면 `${BASH_SOURCE[0]}` 기반 `REPO_ROOT` 계산이 스크래치 레포를 가리킨다).

커버 범위:
- D-41/25-31: W-XXX 카운터·claim 레지스트리를 `git rev-parse --git-common-dir`
  하위(모든 워크트리가 공유)로 옮긴 것 — 별도 워크트리의 동시 `new`가 더는
  같은 W-XXX를 중복 발급하지 않는다 (되돌려-FAIL: 이 테스트는 카운터를
  `docs/works/.claimed`로 되돌리면 실패한다 — 각 워크트리가 빈 `docs/works`만
  보므로 둘 다 W-001을 만든다).
- D-51/25-31 정정: "워크트리 개수" 만으로 발화하는 시작 경고가 없다(폐기됨) —
  대신 할당(claim) 시점에 이미 소진된 번호 공간은 오류로 멈춘다.
- D-29/25-22: `work.sh complete`가 본문 `> Status:` 인라인 줄을 frontmatter와
  동기화한다. 과거 이력 파일(W-001~W-004)은 건드리지 않는다는 불변조건은
  `sync_status_line`이 패턴 부재 시 아무 것도 쓰지 않는 것으로 보장된다.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
WORK_SH = SCRIPTS_DIR / "work.sh"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )


def _fake_repo(tmp_path: Path, *, name: str = "repo") -> Path:
    root = tmp_path / name
    (root / "scripts").mkdir(parents=True)
    (root / "docs" / "works" / "idea").mkdir(parents=True)
    (root / "docs" / "works" / "active").mkdir(parents=True)
    (root / "docs" / "works" / "completed").mkdir(parents=True)
    shutil.copy2(WORK_SH, root / "scripts" / "work.sh")
    (root / "scripts" / "work.sh").chmod(
        (root / "scripts" / "work.sh").stat().st_mode
        | stat.S_IEXEC
        | stat.S_IXGRP
        | stat.S_IXOTH
    )
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "fixture@example.com")
    _git(root, "config", "user.name", "Fixture")
    (root / ".gitkeep").write_text("", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _run_work(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(repo / "scripts" / "work.sh"), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _find_work_dir(repo: Path, stage: str, work_id: str) -> Path:
    matches = list((repo / "docs" / "works" / stage).glob(f"{work_id}-*"))
    assert len(matches) == 1, (
        f"expected exactly one match for {work_id} in {stage}: {matches}"
    )
    return matches[0]


# ── 1. claim 레지스트리 위치: git-common-dir 공유 자리로 옮겨졌다 (D-41) ──────────


def test_claim_registry_lives_under_git_common_dir_not_docs_works(tmp_path):
    repo = _fake_repo(tmp_path)
    result = _run_work(repo, "new", "레지스트리 위치 테스트")
    assert result.returncode == 0, result.stdout + result.stderr

    common_dir = _git(repo, "rev-parse", "--git-common-dir").stdout.strip()
    common_dir_path = (
        (repo / common_dir).resolve()
        if not Path(common_dir).is_absolute()
        else Path(common_dir)
    )

    assert (common_dir_path / "kit" / "claimed" / "W-001").is_dir()
    # 옛 위치(docs/works/.claimed)에는 아무것도 만들지 않는다
    assert not (repo / "docs" / "works" / ".claimed").exists()


# ── 2. 크로스 워크트리 충돌 회피 (핵심 회귀 테스트, 되돌려-FAIL) ──────────────────


def test_cross_worktree_new_does_not_duplicate_id(tmp_path):
    repo = _fake_repo(tmp_path)

    # 워크트리1: W-001 발급 (claim 레지스트리에 W-001이 공유 위치에 남는다)
    result1 = _run_work(repo, "new", "본체 작업")
    assert result1.returncode == 0, result1.stdout + result1.stderr
    assert "Created: W-001" in result1.stdout

    # 워크트리2: 별도 체크아웃 — 자신의 docs/works는 완전히 비어 있다(idea/active/
    # completed 셋 다). 카운터가 공유되지 않으면(D-41 이전 결함) 이 워크트리는
    # 자기 docs/works만 보고 다시 W-001을 발급해 중복이 생긴다.
    wt = tmp_path / "repo-wt2"
    _git(repo, "worktree", "add", "-q", "-b", "feature", str(wt))
    (wt / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(WORK_SH, wt / "scripts" / "work.sh")
    (wt / "scripts" / "work.sh").chmod(
        (wt / "scripts" / "work.sh").stat().st_mode
        | stat.S_IEXEC
        | stat.S_IXGRP
        | stat.S_IXOTH
    )
    for stage in ("idea", "active", "completed"):
        (wt / "docs" / "works" / stage).mkdir(parents=True, exist_ok=True)
    assert list((wt / "docs" / "works" / "idea").iterdir()) == []

    result2 = _run_work(wt, "new", "워크트리2 작업")
    assert result2.returncode == 0, result2.stdout + result2.stderr
    assert "Created: W-002" in result2.stdout, (
        "cross-worktree collision NOT avoided — expected W-002, got:\n" + result2.stdout
    )
    assert "Created: W-001" not in result2.stdout


# ── 3. 소진 시 오류로 멈춘다, 원인 제거 시 회복한다 (되돌려-FAIL) ────────────────


def test_claim_exhaustion_errors_then_recovers_when_writable_again(tmp_path):
    repo = _fake_repo(tmp_path)

    # claimed 디렉토리를 먼저 확보한 뒤(정상 claim 1회) 쓰기 권한을 제거해
    # 이후 모든 claim 시도가 EACCES로 실패하도록 강제한다 — 20회 재시도가
    # 전부 실패해야 오류로 멈추는지 결정론적으로 검증할 수 있다.
    result0 = _run_work(repo, "new", "선행 작업")
    assert result0.returncode == 0, result0.stdout + result0.stderr

    common_dir = _git(repo, "rev-parse", "--git-common-dir").stdout.strip()
    common_dir_path = (
        (repo / common_dir).resolve()
        if not Path(common_dir).is_absolute()
        else Path(common_dir)
    )
    claimed_dir = common_dir_path / "kit" / "claimed"
    assert claimed_dir.is_dir()

    original_mode = claimed_dir.stat().st_mode
    claimed_dir.chmod(0o555)  # read + execute only — mkdir 안의 새 항목 생성 불가
    try:
        result = _run_work(repo, "new", "충돌 테스트")
        assert result.returncode != 0, result.stdout + result.stderr
        assert "could not allocate a unique Work ID" in result.stderr
        # 실패한 시도가 docs/works에 흔적을 남기지 않았는지 확인
        assert list((repo / "docs" / "works" / "idea").glob("W-*충돌*")) == []
    finally:
        claimed_dir.chmod(original_mode)

    # 되돌려 — 쓰기 권한 복구 후 재시도하면 다음 번호로 정상 발급된다
    result_recovered = _run_work(repo, "new", "복구 후 작업")
    assert result_recovered.returncode == 0, (
        result_recovered.stdout + result_recovered.stderr
    )
    assert "Created: W-002" in result_recovered.stdout


# ── 4. D-51: 워크트리 개수만으로 발화하는 경고가 없다 ────────────────────────────


def test_no_startup_warning_gated_on_worktree_count():
    source = WORK_SH.read_text(encoding="utf-8")
    assert "git worktree list" not in source
    assert "worktree count" not in source.lower()


# ── 5. D-29: complete가 본문 `> Status:` 줄을 frontmatter와 동기화한다 ──────────


def test_complete_syncs_inline_status_line(tmp_path):
    repo = _fake_repo(tmp_path)
    _run_work(repo, "new", "상태줄 동기화 테스트")
    _run_work(repo, "start", "W-001")

    active_dir = _find_work_dir(repo, "active", "W-001")
    md = next(active_dir.glob("W-001-*.md"))
    assert "> Status: idea" in md.read_text(encoding="utf-8")

    result = _run_work(repo, "complete", "W-001")
    assert result.returncode == 0, result.stdout + result.stderr

    completed_dir = _find_work_dir(repo, "completed", "W-001")
    completed_md = next(completed_dir.glob("W-001-*.md"))
    content = completed_md.read_text(encoding="utf-8")
    assert "> Status: completed" in content
    assert "status: completed" in content  # frontmatter도 여전히 갱신됨
    assert "> Status: idea" not in content


def test_complete_does_not_inject_status_line_when_absent(tmp_path):
    # 과거 이력 파일(W-001~W-004류)처럼 `> Status:` 줄이 없는 파일을 completed로
    # 옮겨도 그 줄을 새로 만들어 넣지 않는다 — D-29의 "역사 기록은 고치지 않는다"를
    # 지키려면 sync_status_line은 패턴이 없을 때 조용히 아무 것도 하지 않아야 한다
    # (없던 줄을 새로 주입하면 그 자체가 원문 변형이다). 공개 CLI만으로 검증한다.
    repo = _fake_repo(tmp_path)
    _run_work(repo, "new", "상태줄 없는 케이스")
    _run_work(repo, "start", "W-001")

    active_dir = _find_work_dir(repo, "active", "W-001")
    md = next(active_dir.glob("W-001-*.md"))
    stripped = (
        "\n".join(
            line
            for line in md.read_text(encoding="utf-8").splitlines()
            if not line.startswith("> Status:")
        )
        + "\n"
    )
    assert "> Status:" not in stripped
    md.write_text(stripped, encoding="utf-8")

    result = _run_work(repo, "complete", "W-001")
    assert result.returncode == 0, result.stdout + result.stderr

    completed_dir = _find_work_dir(repo, "completed", "W-001")
    completed_md = next(completed_dir.glob("W-001-*.md"))
    content = completed_md.read_text(encoding="utf-8")
    assert "> Status:" not in content  # 없던 줄이 새로 생기지 않는다
    assert "status: completed" in content  # frontmatter는 여전히 갱신됨
