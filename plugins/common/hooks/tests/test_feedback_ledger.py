"""Unit tests for feedback_ledger.py (Spec 3 / W-007)."""

import contextlib
import importlib.util
import os
import stat
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


def _row(entry_id: str) -> dict:
    """`_write_ledger` 가 기대하는 최소 항목."""
    return {
        "id": entry_id,
        "category": "lint",
        "pattern": "sample pattern",
        "frequency": 1,
        "last_seen": "2026-09-10",
        "severity": "low",
    }


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


def test_invalid_category_reclassification_is_announced(tmp_path, capsys):
    """재분류는 유지하되 **조용하지 않다**.

    바로 아래 `severity` 는 화이트리스트 밖 값을 `''` 로 비워 기존값을 보존하는
    대칭 처리를 하는데, category 만 강제 재분류였다. 게다가 `_normalize` 가 category
    를 dedupe 키에 넣으므로 오타 하나가 잘못된 버킷에 누적되면서 **키까지 오염**된다.
    한 줄 남기면 오타를 낸 호출자가 그 자리에서 본다.
    """
    _mod.upsert("securty", "low", "typo in category", root=tmp_path)
    err = capsys.readouterr().err
    assert "securty" in err, f"재분류가 조용히 일어났다: {err!r}"
    assert "convention" in err
    for known in _mod.VALID_CATEGORIES:
        assert known in err, "허용 목록을 알려주지 않으면 호출자가 무엇을 쓸지 모른다"


def test_valid_category_is_not_announced(tmp_path, capsys):
    """상시 참인 줄은 소음이다 (`warning-signal.md`) — 정상 경로는 침묵한다."""
    _mod.upsert("security", "low", "hardcoded secret", root=tmp_path)
    assert capsys.readouterr().err == ""


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
    """원자 교체 후 tmp 파일이 잔존하지 않는다.

    **glob 을 이름 패턴으로 좁히지 않는다.** 구 구현은 `<name>.tmp.<pid>` 였고 이
    테스트는 `*.tmp.*` 를 봤다 — 구현이 `mkstemp` 로 바뀌면 그 glob 은 아무것도 잡지
    못한 채 **초록으로 남는다**(false-green). 대신 "원장 파일 하나만 남았다"를 본다.
    """
    _mod.upsert("lint", "low", "atomic write check", root=tmp_path)
    ledger = _mod.ledger_path(tmp_path)
    leftovers = [
        p for p in ledger.parent.iterdir() if p.name != ledger.name
    ]
    assert leftovers == [], f"tmp 잔여물: {[p.name for p in leftovers]}"


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


def test_legacy_vanishing_at_lock_entry_does_not_double_count(tmp_path, monkeypatch):
    """다른 프로세스가 먼저 이관한 뒤 잠금을 얻으면 **다시 세지 않아야** 한다.

    초판은 존재 검사·`parse_ledger(legacy)`·개명이 모두 **잠금 밖**이었다. 그래서 잠금을
    기다리는 쪽이 이미 읽어 둔 항목을 그대로 병합해 **frequency 가 두 배**가 됐다 —
    검사와 상태 변경 사이의 틈이 곧 TOCTOU 다.

    스레드로는 이 창을 결정적으로 못 벌린다(스케줄러가 정하므로 **깨진 코드에서도
    통과한다** — 커버리지를 주장하면서 아무것도 안 잡는 테스트가 된다). 그래서 경합의
    **결과 상태**를 직접 만든다: 잠금에 진입하는 순간 legacy 가 이미 개명돼 있는 상황.
    """
    repo = _init_repo(tmp_path)
    legacy = _mod.legacy_ledger_path(repo)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    row = {"id": "F-001", "category": "test", "pattern": "정확히 한 번",
           "frequency": 1, "last_seen": "2026-01-01", "severity": "low"}
    _mod._write_ledger(legacy, [row])
    # 먼저 이관한 쪽이 남긴 상태: 정본에 이미 반영돼 있다.
    _mod._write_ledger(_mod.ledger_path(repo), [dict(row)])

    real_lock = _mod._ledger_lock

    def racing_lock(path):
        # 잠금을 얻는 순간 legacy 는 이미 개명돼 있다(먼저 이관한 쪽이 끝냈다).
        if legacy.is_file():
            legacy.rename(legacy.with_suffix(".md.migrated"))
        return real_lock(path)

    monkeypatch.setattr(_mod, "_ledger_lock", racing_lock)
    assert _mod.migrate_legacy_ledger(repo) == "noop"

    hits = [e for e in _mod.parse_ledger(_mod.ledger_path(repo))
            if e["pattern"] == "정확히 한 번"]
    assert len(hits) == 1
    assert hits[0]["frequency"] == 1, f"중복 계수: {hits[0]['frequency']}"


# ── ATK-008: 이관 순서 — 개명이 먼저다 ────────────────────────────
def test_rename_failure_does_not_inflate_frequency(tmp_path, monkeypatch, capsys):
    """개명 실패 후 재실행해도 frequency 가 부풀지 않는다.

    초판은 `_write_ledger(target, kept)` 를 **먼저**, `legacy.rename(backup)` 을
    **나중** 에 했다. 둘은 원자적이지 않으므로 개명이 실패하면(권한·파일시스템·경합)
    구 원장이 그대로 남고, 다음 SessionStart 가 같은 항목을 또 병합해 frequency 가
    2배가 된다. frequency 는 digest 순위를 정하므로 부푼 항목이 진짜 반복 결함을
    digest 밖으로 밀어낸다(ATK-008).
    """
    repo = _init_repo(tmp_path)
    legacy = _mod.legacy_ledger_path(repo)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    _mod._write_ledger(legacy, [
        {"id": "F-001", "category": "test", "pattern": "정확히 한 번만 세어야 한다",
         "frequency": 1, "last_seen": "2026-01-01", "severity": "low"},
    ])

    real_rename = Path.rename
    state = {"failed": False}

    def flaky_rename(self, target):
        if not state["failed"] and self == legacy:
            state["failed"] = True
            raise OSError("rename blocked")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", flaky_rename)

    _mod._try_migrate(repo)  # 1회차 — 개명 실패
    assert state["failed"], "개명 실패 경로에 도달하지 않았다 (양성 대조)"
    _mod._try_migrate(repo)  # 2회차 — 재시도

    hits = [e for e in _mod.parse_ledger(_mod.ledger_path(repo))
            if e["pattern"] == "정확히 한 번만 세어야 한다"]
    assert len(hits) == 1, f"항목이 중복됐다: {hits}"
    assert hits[0]["frequency"] == 1, (
        f"중복 병합으로 frequency 가 부풀었다: {hits[0]['frequency']}"
    )


def test_migration_failure_is_not_silent(tmp_path, monkeypatch, capsys):
    """이관 실패를 완전히 침묵시키지 않는다 — fail-open 은 유지하되 관측 가능하게.

    warning-signal §4 — 이 경고가 도는 조건: *"구 원장이 실제로 존재해서 이관을
    시도했고, 그 이관이 예외로 실패했을 때만."* 아래 양성 대조가 그 조건을 만든다.
    """
    repo = _init_repo(tmp_path)
    legacy = _mod.legacy_ledger_path(repo)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    _mod._write_ledger(legacy, [
        {"id": "F-001", "category": "test", "pattern": "관측 가능해야 한다",
         "frequency": 1, "last_seen": "2026-01-01", "severity": "low"},
    ])

    def boom(self, target):
        raise OSError("rename blocked")

    monkeypatch.setattr(Path, "rename", boom)
    _mod._try_migrate(repo)  # fail-open — 예외가 밖으로 새지 않는다
    err = capsys.readouterr().err
    assert "이관 실패" in err, f"이관 실패가 침묵됐다 (stderr={err!r})"


def test_migration_warning_is_silent_in_normal_operation(tmp_path, capsys):
    """음성 대조 — 구 원장이 없는 정상 운영에서는 발화하지 않는다(상시 참 경고 금지)."""
    repo = _init_repo(tmp_path)
    _mod._try_migrate(repo)
    assert "이관 실패" not in capsys.readouterr().err


# ── M-1: 락 디렉토리 소유권·퍼미션 검사 ───────────────────────────
def _fake_tmpdir(monkeypatch, tmp_path):
    d = tmp_path / "fake_tmp"
    d.mkdir()
    monkeypatch.setattr(_mod.tempfile, "gettempdir", lambda: str(d))
    return d


def _hijack_name(fake_tmp):
    import os
    try:
        uid = os.getuid()
    except AttributeError:
        uid = os.environ.get("USER", "user")
    return fake_tmp / f"claude-{uid}"


def test_lock_dir_reused_when_owned_and_private(monkeypatch, tmp_path):
    """양성 대조 — 내 소유 0700 디렉토리는 그대로 재사용한다."""
    fake_tmp = _fake_tmpdir(monkeypatch, tmp_path)
    d = _hijack_name(fake_tmp)
    d.mkdir(mode=0o700)
    lock = _mod._lock_path_for(tmp_path / "ledger.md")
    assert lock.parent == d


def test_world_writable_lock_dir_falls_back(monkeypatch, tmp_path):
    """공용 /tmp 에서 이름이 선점돼 group/other 쓰기 가능하면 쓰지 않는다 (M-1).

    `exist_ok=True` 는 기존 디렉토리를 그대로 받아들이고 `mode=` 는 생성 시에만
    적용되므로, 검사 없이는 남이 통제하는 디렉토리에 락 파일을 연다.
    """
    import os
    fake_tmp = _fake_tmpdir(monkeypatch, tmp_path)
    d = _hijack_name(fake_tmp)
    d.mkdir()
    # S103 억제 근거: 이 테스트가 **검사하려는 위험 조건 자체**를 만드는 픽스처다.
    # 안전한 모드로 바꾸면 테스트가 아무것도 잡지 못한다(false-green).
    os.chmod(d, 0o777)  # noqa: S103
    ledger = tmp_path / "ledger.md"
    assert _mod._lock_path_for(ledger) == ledger.with_name("ledger.md.lock")


def test_symlinked_lock_dir_falls_back(monkeypatch, tmp_path):
    """O_NOFOLLOW 는 락 **파일**의 심링크만 막는다 — 디렉토리 자체는 lstat 로 본다."""
    fake_tmp = _fake_tmpdir(monkeypatch, tmp_path)
    elsewhere = tmp_path / "attacker_dir"
    elsewhere.mkdir(mode=0o700)
    _hijack_name(fake_tmp).symlink_to(elsewhere, target_is_directory=True)
    ledger = tmp_path / "ledger.md"
    assert _mod._lock_path_for(ledger) == ledger.with_name("ledger.md.lock")


def test_foreign_owned_lock_dir_falls_back(monkeypatch, tmp_path):
    """소유자가 내가 아니면 쓰지 않는다 — lstat 결과의 st_uid 로 판정한다."""
    import stat as _stat
    fake_tmp = _fake_tmpdir(monkeypatch, tmp_path)
    d = _hijack_name(fake_tmp)
    d.mkdir(mode=0o700)

    real_lstat = _mod.os.lstat

    def foreign_lstat(p):
        st = real_lstat(p)
        if Path(p) == d:
            return _stat_result_with_uid(st, st.st_uid + 1)
        return st

    def _stat_result_with_uid(st, uid):
        class _S:
            st_mode = st.st_mode | _stat.S_IFDIR
            st_uid = uid
        return _S()

    monkeypatch.setattr(_mod.os, "lstat", foreign_lstat)
    ledger = tmp_path / "ledger.md"
    assert _mod._lock_path_for(ledger) == ledger.with_name("ledger.md.lock")


# ─────────────────────────────────────────────────────────────────────────────
# 원장이 심링크일 때: 내 것이면 따라가고, 남의 것이면 쓰지 않는다
# (같은 파일의 락 디렉토리 검사와 같은 기준 — 이전에는 원장 쪽만 가정으로 열려 있었다)
# ─────────────────────────────────────────────────────────────────────────────


def test_symlinked_ledger_owned_by_me_is_followed(tmp_path):
    """F7(공유 원장 심링크)은 **의도된 기능**이다 — 봉쇄가 이 기능을 깨면 안 된다."""
    shared = tmp_path / "shared-ledger.md"
    shared.write_text(_mod._HEADER, encoding="utf-8")
    link = tmp_path / "ledger.md"
    link.symlink_to(shared)

    _mod._write_ledger(link, [_row("E-1")])

    assert "E-1" in shared.read_text(encoding="utf-8")
    assert link.is_symlink(), "심링크가 일반 파일로 교체됐다 — F7 이 깨졌다"


def test_symlinked_ledger_owned_by_someone_else_is_refused(tmp_path, monkeypatch, capsys):
    """남이 심어 둔 링크는 따라가지 않는다. 예외는 올리지 않는다(학습 루프는 fail-open)."""
    victim = tmp_path / "victim.txt"
    victim.write_text("DO NOT OVERWRITE\n", encoding="utf-8")
    link = tmp_path / "ledger.md"
    link.symlink_to(victim)

    # 실제로 남의 uid 로 파일을 만들 수 없으므로 "내 uid" 쪽을 바꿔 같은 조건을 만든다.
    monkeypatch.setattr(_mod.os, "getuid", lambda: os.stat(victim).st_uid + 1)

    _mod._write_ledger(link, [_row("E-2")])

    assert victim.read_text(encoding="utf-8") == "DO NOT OVERWRITE\n", "남의 파일이 덮였다"
    assert "남의 소유" in capsys.readouterr().err


# ─────────────────────────────────────────────────────────────────────────────
# 내구성 계약 — `export_harness.py::_atomic_write` 와 **동일**해야 한다
# (D-15: 구현은 여러 벌, 계약만 하나). 한쪽을 고치면 다른 쪽도 고쳐라.
# ─────────────────────────────────────────────────────────────────────────────


def test_write_ledger_preserves_existing_file_mode(tmp_path):
    """기존 파일 모드를 보존한다 — 0600 으로 관리하던 원장이 world-readable 이 되면 안 된다.

    구 구현은 tmp 를 `0o644` 로 만들고 그대로 replace 했으므로 **무조건 0644 로 덮였다.**
    원장은 심링크로 공유되는 것이 의도된 기능(F7)이므로 모드도 남의 결정이다.
    """
    ledger = tmp_path / "ledger.md"
    _mod._write_ledger(ledger, [_row("M-1")])
    os.chmod(ledger, 0o600)

    _mod._write_ledger(ledger, [_row("M-2")])

    mode = stat.S_IMODE(os.stat(ledger).st_mode)
    assert mode == 0o600, f"모드가 보존되지 않았다: {oct(mode)}"
    assert "M-2" in ledger.read_text(encoding="utf-8")


def test_write_ledger_preserves_mode_through_symlink(tmp_path):
    """심링크 대상의 모드도 보존한다 — 봉쇄·내구성 강화가 F7 을 깨면 안 된다."""
    shared = tmp_path / "shared-ledger.md"
    shared.write_text(_mod._HEADER, encoding="utf-8")
    os.chmod(shared, 0o640)
    link = tmp_path / "ledger.md"
    link.symlink_to(shared)

    _mod._write_ledger(link, [_row("M-3")])

    assert link.is_symlink(), "심링크가 일반 파일로 교체됐다 — F7 이 깨졌다"
    mode = stat.S_IMODE(os.stat(shared).st_mode)
    assert mode == 0o640, f"심링크 대상의 모드가 보존되지 않았다: {oct(mode)}"
    assert "M-3" in shared.read_text(encoding="utf-8")


def test_write_ledger_does_not_clobber_the_predictable_tmp_name(tmp_path):
    """tmp 이름이 pid 로 예측 가능하면 안 된다 — `mkstemp` 를 쓴다.

    이름을 직접 볼 수는 없으므로 **구 이름 자리에 있던 파일이 살아남는가**로 본다.
    구 구현은 `<name>.tmp.<pid>` 를 `unlink(missing_ok=True)` 로 **먼저 지우고**
    `O_EXCL` 로 만들었다 — 그 이름을 선점당하면(컨테이너의 PID 재사용, 또는 고의)
    남의 파일이 조용히 사라진다. `mkstemp` 는 이름이 예측 불가하므로 건드리지 않는다.
    """
    ledger = tmp_path / "ledger.md"
    squatter = tmp_path / f"ledger.md.tmp.{os.getpid()}"
    squatter.write_text("squatted", encoding="utf-8")

    _mod._write_ledger(ledger, [_row("T-1")])

    assert "T-1" in ledger.read_text(encoding="utf-8")
    assert squatter.exists(), "예측 가능한 tmp 이름의 기존 파일이 지워졌다"
    assert squatter.read_text(encoding="utf-8") == "squatted"


def test_write_ledger_content_is_exact(tmp_path):
    """기록 후 내용이 정확하다 — 헤더 + 행, 잘리지 않는다."""
    ledger = tmp_path / "ledger.md"
    _mod._write_ledger(ledger, [_row("C-1"), _row("C-2")])

    text = ledger.read_text(encoding="utf-8")
    assert text.startswith(_mod._HEADER)
    assert text.endswith("\n")
    rows = [line for line in text.splitlines() if line.startswith("| C-")]
    assert rows == [
        "| C-1 | lint | sample pattern | 1 | 2026-09-10 | low |",
        "| C-2 | lint | sample pattern | 1 | 2026-09-10 | low |",
    ], rows


def test_write_ledger_fsyncs_file_and_directory(tmp_path, monkeypatch):
    """파일 fsync + 디렉토리 fsync 를 **실제로** 호출한다.

    `os.replace` 는 원자적이지만 **디스크 도달을 보장하지 않는다** — 호스트가 죽으면
    rename 만 반영되고 내용이 안 반영돼 빈/잘린 원장이 남는다. 이 어서션이 없으면
    fsync 를 지워도 다른 모든 테스트가 초록이다.
    """
    synced = []
    real_fsync = os.fsync

    def spy(fd):
        with contextlib.suppress(OSError):
            synced.append(os.fstat(fd).st_mode)
        return real_fsync(fd)

    monkeypatch.setattr(_mod.os, "fsync", spy)
    _mod._write_ledger(tmp_path / "ledger.md", [_row("S-1")])

    assert any(stat.S_ISREG(m) for m in synced), "파일 fsync 가 호출되지 않았다"
    assert any(stat.S_ISDIR(m) for m in synced), "디렉토리 fsync 가 호출되지 않았다"


def test_write_ledger_survives_unsupported_directory_fsync(tmp_path, monkeypatch):
    """디렉토리 fsync 가 지원되지 않는 파일시스템에서도 쓰기는 성공한다(fail-open)."""
    real_fsync = os.fsync

    def picky(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("directory fsync unsupported")
        return real_fsync(fd)

    monkeypatch.setattr(_mod.os, "fsync", picky)
    ledger = tmp_path / "ledger.md"
    _mod._write_ledger(ledger, [_row("S-2")])

    assert "S-2" in ledger.read_text(encoding="utf-8")


def test_plain_ledger_file_is_unaffected(tmp_path):
    """심링크가 아니면 검사가 개입하지 않는다 — 정상 경로에서 조용해야 한다."""
    plain = tmp_path / "ledger.md"
    _mod._write_ledger(plain, [_row("E-3")])
    assert "E-3" in plain.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# "부재"와 "못 읽음"을 구분한다 — 뭉개면 upsert 가 원장을 통째로 덮어쓴다
# ─────────────────────────────────────────────────────────────────────────────


def test_absent_ledger_is_empty_not_an_error(tmp_path):
    """부재는 정상이다 — 아직 배운 게 없을 뿐이다."""
    assert _mod.parse_ledger(tmp_path / "nope.md") == []


def test_unreadable_ledger_raises_instead_of_looking_empty(tmp_path):
    """**있는데 못 읽음**은 빈 원장이 아니다."""
    bad = tmp_path / "ledger.md"
    bad.write_bytes(b"| F-001 | lint | \xff\xfe broken | 1 | 2026-09-10 | low |\n")
    try:
        _mod.parse_ledger(bad)
    except _mod.LedgerUnreadable:
        return
    raise AssertionError("읽기 실패가 빈 원장으로 뭉개졌다")


def test_upsert_refuses_to_overwrite_an_unreadable_ledger(tmp_path, monkeypatch, capsys):
    """★핵심 회귀: 못 읽은 원장 위에 쓰면 학습 항목이 통째로 사라진다."""
    path = _mod.ledger_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = b"| F-001 | lint | \xff\xfe broken | 7 | 2026-09-10 | low |\n"
    path.write_bytes(raw)

    result = _mod.upsert("lint", "low", "new pattern", root=tmp_path)

    assert result == "skipped"
    assert path.read_bytes() == raw, "읽지 못한 원장이 덮어써졌다"
    assert "읽지 못해" in capsys.readouterr().err


def test_digest_is_empty_but_loud_when_unreadable(tmp_path, capsys):
    """읽기 전용 경로는 빈 문자열로 물러서되 **조용하지는 않다**."""
    path = _mod.ledger_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"| F-001 | lint | \xff\xfe | 1 | 2026-09-10 | low |\n")

    assert _mod.load_digest(root=tmp_path) == ""
    assert "읽지 못해" in capsys.readouterr().err
