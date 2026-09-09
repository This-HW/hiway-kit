"""Unit tests for feedback_ledger.py (Spec 3 / W-007)."""

import importlib.util
from pathlib import Path
from types import ModuleType

HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "feedback_ledger", HOOKS_DIR / "feedback_ledger.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


# ── upsert: 신규 추가 ─────────────────────────────────────────────
def test_upsert_adds_new_entry(tmp_path):
    result = _mod.upsert("lint", "low", "unused import", root=tmp_path)
    assert result == "added"
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) == 1
    assert entries[0]["category"] == "lint"
    assert entries[0]["frequency"] == 1


# ── upsert: 중복 → frequency 증가 (dedupe) ───────────────────────
def test_upsert_increments_on_duplicate(tmp_path):
    _mod.upsert("security", "high", "Hardcoded API key", root=tmp_path)
    # 대소문자/공백 차이는 같은 패턴으로 정규화되어야 함
    result = _mod.upsert("security", "high", "hardcoded   api  key", root=tmp_path)
    assert result == "incremented"
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) == 1
    assert entries[0]["frequency"] == 2


# ── decay: 상한 초과 시 하위 제거 ────────────────────────────────
def test_decay_enforces_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "CAP", 3)
    for i in range(5):
        _mod.upsert("convention", "low", f"pattern number {i}", root=tmp_path)
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) <= 3


# ── decay: 고빈도 엔트리는 상한에서 보존 ─────────────────────────
def test_decay_keeps_high_frequency(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "CAP", 2)
    # high-freq 엔트리
    for _ in range(5):
        _mod.upsert("test", "medium", "flaky timing assertion", root=tmp_path)
    # low-freq 엔트리들
    _mod.upsert("lint", "low", "trailing whitespace", root=tmp_path)
    _mod.upsert("lint", "low", "long line", root=tmp_path)
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    patterns = [e["pattern"] for e in entries]
    assert any("flaky timing" in p for p in patterns), "고빈도 엔트리가 감쇠로 제거됨"


# ── load_digest: 상위 K + 빈도 표시 ──────────────────────────────
def test_load_digest_returns_top_k(tmp_path):
    for _ in range(3):
        _mod.upsert("security", "critical", "SQL injection risk", root=tmp_path)
    _mod.upsert("lint", "low", "unused var", root=tmp_path)
    digest = _mod.load_digest(top_k=5, root=tmp_path)
    assert "SQL injection risk" in digest
    assert "x3" in digest


# ── fail-open: ledger 부재 시 빈 digest ──────────────────────────
def test_load_digest_empty_when_no_ledger(tmp_path):
    assert _mod.load_digest(root=tmp_path) == ""


# ── invalid category → convention으로 폴백 ───────────────────────
def test_invalid_category_falls_back(tmp_path):
    _mod.upsert("nonsense", "low", "weird thing", root=tmp_path)
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert entries[0]["category"] == "convention"


# ── '|' 포함 패턴: 테이블 깨짐 없이 저장·dedupe ──────────────────
def test_pipe_in_pattern_is_sanitized(tmp_path):
    # review 결함에 '|'가 흔함 (예: 'string | null')
    _mod.upsert(
        "architecture", "high", "prefer composition | over inheritance", root=tmp_path
    )
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) == 1, "'|'로 행이 깨져 엔트리가 유실됨"
    assert entries[0]["frequency"] == 1
    assert "|" not in entries[0]["pattern"]
    # 재upsert 시 dedupe 되어야 함 (중복 누적 방지)
    result = _mod.upsert(
        "architecture", "high", "prefer composition | over inheritance", root=tmp_path
    )
    assert result == "incremented"
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) == 1
    assert entries[0]["frequency"] == 2


# ── 개행 포함 패턴: 단일 행 유지 ─────────────────────────────────
def test_newline_in_pattern_collapsed(tmp_path):
    _mod.upsert("test", "low", "line one\nline two", root=tmp_path)
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert len(entries) == 1
    assert "\n" not in entries[0]["pattern"]


# ── digest 문자 상한 ─────────────────────────────────────────────
def test_digest_char_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "DIGEST_CHAR_CAP", 80)
    for i in range(10):
        _mod.upsert(
            "architecture",
            "high",
            f"very long architectural smell pattern {i}",
            root=tmp_path,
        )
    digest = _mod.load_digest(top_k=10, root=tmp_path)
    assert len(digest) <= 82  # cap + " …"


# ── 동시 upsert: lost-update / F-id 충돌 방지 (W-011) ─────────────
def test_concurrent_upserts_preserve_all_entries(tmp_path):
    """auto-dev가 T-review/T-security를 병렬 실행하며 둘 다 upsert하는 시나리오.

    CLI 프로세스 N개를 동시에 띄워 서로 다른 패턴을 upsert — 락이 없으면
    read-modify-write 레이스로 일부 기록이 소실되고 F-id가 중복 채번된다.
    """
    import subprocess as sp
    import sys

    n = 8
    env = {**__import__("os").environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    script = str(HOOKS_DIR / "feedback_ledger.py")
    procs = [
        sp.Popen(
            [sys.executable, script, "upsert", "lint", "low", f"concurrent pattern {i}"],
            env=env,
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )
        for i in range(n)
    ]
    for p in procs:
        assert p.wait(timeout=30) == 0

    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    patterns = {e["pattern"] for e in entries}
    ids = [e["id"] for e in entries]
    assert len(entries) == n, f"동시 upsert 중 기록 소실: {n}개 중 {len(entries)}개만 보존"
    assert patterns == {f"concurrent pattern {i}" for i in range(n)}
    assert len(ids) == len(set(ids)), f"F-id 중복 채번: {sorted(ids)}"


def test_write_ledger_leaves_no_tmp_files(tmp_path):
    """원자 교체 후 tmp 파일이 잔존하지 않는다."""
    _mod.upsert("lint", "low", "atomic write check", root=tmp_path)
    leftovers = list(_mod.ledger_path(tmp_path).parent.glob("*.tmp.*"))
    assert leftovers == []


# ── F7: 심링크된 ledger.md는 링크 대상을 보존하며 갱신 ──────────────
def test_write_ledger_preserves_symlink_target(tmp_path):
    """ledger.md가 공유 원장으로 심링크돼 있으면 링크를 파괴하지 않고 대상에 쓴다."""
    import os
    central = tmp_path / "central.md"
    central.write_text("seed", encoding="utf-8")
    ledger = _mod.ledger_path(tmp_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(central, ledger)

    _mod.upsert("lint", "low", "via symlink", root=tmp_path)

    assert ledger.is_symlink(), "심링크가 일반 파일로 대체되면 안 된다(F7)"
    assert "via symlink" in central.read_text(encoding="utf-8"), (
        "실제 대상 파일(중앙 원장)이 갱신돼야 한다"
    )


# ── F10: 락 파일이 저장소 트리 밖(사용자 tmp)에 생성된다 ───────────
def test_lock_file_not_in_repo_tree(tmp_path):
    """ledger.md.lock이 docs/works 안이 아니라 사용자별 tmp에 생성돼 커밋 오염·
    porcelain 교란을 일으키지 않는다."""
    _mod.upsert("test", "low", "lock location check", root=tmp_path)
    stray = list((tmp_path / "docs" / "works" / "feedback").glob("*.lock"))
    assert stray == [], f"저장소 트리에 락 파일이 남았다: {stray}"


# ── F9: 락 타임아웃 시 stderr 경고 ────────────────────────────────
def test_lock_timeout_warns(tmp_path, monkeypatch, capsys):
    """데드라인 초과로 무락 진행할 때 stderr 경고를 남겨 관측 가능하게 한다."""
    monkeypatch.setattr(_mod, "_LOCK_TIMEOUT_SECONDS", 0)  # 즉시 데드라인

    real_flock = _mod.fcntl.flock

    def _always_busy(fh, flags):
        if flags & _mod.fcntl.LOCK_NB:
            raise OSError("locked")
        return real_flock(fh, flags)

    monkeypatch.setattr(_mod.fcntl, "flock", _always_busy)
    _mod.upsert("lint", "low", "timeout warn", root=tmp_path)

    assert "lock timeout" in capsys.readouterr().err
    # 무락이어도 쓰기는 성공해야 한다(fail-open)
    entries = _mod.parse_ledger(_mod.ledger_path(tmp_path))
    assert any(e["pattern"] == "timeout warn" for e in entries)


# ── 원장 위치: 워크트리 공유 (v3.16.0) ──────────────────────────────────────
#
# 구 위치(docs/works/feedback/ledger.md)는 **작업 트리 안**이라 워크트리마다 별도
# 파일이 됐다. 이 킷은 워크트리 운영을 권장하므로(isolation: worktree·parallel-worktree·
# control-loop) 권장을 따르는 순간 **학습 원장이 세션마다 갈라졌다.**
# 실측: 같은 레포의 두 워크트리에 서로 다른 50항목 원장이 있었다.


def _init_repo(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    return tmp_path


def test_ledger_lives_under_shared_gitdir_not_worktree(tmp_path):
    repo = _init_repo(tmp_path)
    path = _mod.ledger_path(repo)
    assert path.parent.name == "kit"
    assert ".git" in str(path), "작업 트리 안이면 워크트리마다 갈라진다"
    assert "docs" not in str(path)


def test_falls_back_to_legacy_outside_git(tmp_path):
    """git 저장소가 아니면 구 위치로 물러선다 — 임의 디렉토리에서도 동작해야 한다."""
    assert _mod.ledger_path(tmp_path) == _mod.legacy_ledger_path(tmp_path)


def test_legacy_is_merged_not_overwritten(tmp_path):
    """두 워크트리가 각자 다른 원장을 갖고 있었다 — 먼저 온 하나만 채택하면 유실이다."""
    repo = _init_repo(tmp_path)
    _mod.upsert("security", "high", "공용 원장에 이미 있던 것", root=repo)
    legacy = _mod.legacy_ledger_path(repo)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    _mod._write_ledger(legacy, [
        {"id": "F-001", "category": "test", "pattern": "구 원장에만 있던 것",
         "frequency": 3, "last_seen": "2026-01-01", "severity": "high"},
    ])
    assert _mod.migrate_legacy_ledger(repo) == "merged"
    patterns = [e["pattern"] for e in _mod.parse_ledger(_mod.ledger_path(repo))]
    assert "공용 원장에 이미 있던 것" in patterns
    assert "구 원장에만 있던 것" in patterns, "구 원장 항목이 유실됐다"


def test_migration_is_idempotent(tmp_path):
    """두 번 돌려도 frequency 가 부풀지 않아야 한다 — 원본을 개명해서 보장한다."""
    repo = _init_repo(tmp_path)
    legacy = _mod.legacy_ledger_path(repo)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    _mod._write_ledger(legacy, [
        {"id": "F-001", "category": "test", "pattern": "한 번만 세어야 한다",
         "frequency": 1, "last_seen": "2026-01-01", "severity": "low"},
    ])
    assert _mod.migrate_legacy_ledger(repo) == "merged"
    assert _mod.migrate_legacy_ledger(repo) == "noop"
    entries = [e for e in _mod.parse_ledger(_mod.ledger_path(repo))
               if e["pattern"] == "한 번만 세어야 한다"]
    assert len(entries) == 1 and entries[0]["frequency"] == 1
    assert not legacy.exists() and legacy.with_suffix(".md.migrated").exists()


def test_symlinked_legacy_is_left_alone(tmp_path):
    """사용자가 공유 원장으로 심링크해 둔 경우(F7)는 건드리지 않는다."""
    repo = _init_repo(tmp_path)
    legacy = _mod.legacy_ledger_path(repo)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    real = tmp_path / "elsewhere.md"
    real.write_text("| F-001 | test | x | 1 | 2026-01-01 | low |\n", encoding="utf-8")
    legacy.symlink_to(real)
    assert _mod.migrate_legacy_ledger(repo) == "noop"
    assert legacy.is_symlink()

