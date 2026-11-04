from __future__ import annotations

import json
import os
import pwd
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
import session_history
import session_history_io


@pytest.fixture(autouse=True)
def controlled_passwd_home(tmp_path, monkeypatch):
    """Keep passwd protection metadata in scratch, outside each selected root."""
    home = tmp_path.with_name(tmp_path.name + "-passwd-home")
    home.mkdir()
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: SimpleNamespace(pw_dir=str(home)))


def write_message(path, text="needle inside", **metadata):
    raw = json.dumps({"type": "user", "message": {"content": text}, **metadata}).encode() + b"\n"
    path.write_bytes(raw)
    return raw


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX named pipe")
def test_named_pipe_is_not_opened_as_a_log(tmp_path):
    os.mkfifo(tmp_path / "blocked.jsonl")
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["scanned_files"] == 0


def test_default_configuration_root_stays_blocked_with_alternate_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "alternate"))
    default = tmp_path / ".codex"
    default.mkdir()
    with pytest.raises(ValueError, match="configuration root"):
        session_history.search(default, ["needle"], 10)


def test_codex_and_claude_messages_are_found_without_tool_payloads(tmp_path):
    codex = [
        {"type": "session_meta", "payload": {"id": "c1", "cwd": "/project"}},
        {"type": "response_item", "payload": {"role": "user", "content": [{"text": "fix timeout"}]}},
        {"type": "response_item", "payload": {"role": "tool", "content": [{"text": "private tool timeout"}]}},
    ]
    (tmp_path / "codex.jsonl").write_text("\n".join(map(json.dumps, codex)))
    (tmp_path / "claude.jsonl").write_text(json.dumps({
        "type": "user", "sessionId": "cl1", "message": {"content": "타임아웃 수정"},
    }))
    result = session_history.search(tmp_path, ["TIMEOUT", "타임아웃"], 10)
    assert result["matched_sessions"] == 2
    assert {record["id"] for record in result["results"]} == {"c1", "cl1"}
    assert sum(len(record["matches"]) for record in result["results"]) == 2


def test_malformed_and_oversized_records_are_visible(tmp_path, monkeypatch):
    monkeypatch.setattr(session_history, "MAX_LINE_BYTES", 128)
    (tmp_path / "broken.jsonl").write_text("bad-json\n" + "x" * 200)
    result = session_history.search(tmp_path, ["query"], 10)
    assert result["malformed_records"] == 1
    assert result["limited_files"] == 1 and result["matched_sessions"] == 0


def test_symlinks_and_non_jsonl_files_are_not_read(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    secret = tmp_path / "secret.jsonl"
    secret.write_text(json.dumps({"type": "user", "message": {"content": "needle"}}))
    (logs / "linked.jsonl").symlink_to(secret)
    (logs / "elsewhere").symlink_to(tmp_path, target_is_directory=True)
    (logs / "auth.json").write_text(secret.read_text())
    result = session_history.search(logs, ["needle"], 10)
    assert result["scanned_files"] == 0 and not result["results"]


def test_search_limit_and_scan_limit_are_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(session_history, "MAX_SCAN_FILES", 2)
    for number in range(3):
        (tmp_path / f"{number}.jsonl").write_text(json.dumps({"type": "user", "message": {"content": "needle"}}))
    result = session_history.search(tmp_path, ["needle"], 1)
    assert result["scanned_files"] == 2 and result["scan_truncated"]
    assert result["matched_sessions"] == 2 and result["results_truncated"]
    assert len(result["results"]) == 1


def test_whole_home_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(session_history.Path, "home", lambda: tmp_path)
    with pytest.raises(ValueError, match="session-log"):
        session_history.search(tmp_path, ["needle"], 10)


@pytest.mark.parametrize("swap_ancestor", [False, True])
def test_replacement_after_validation_never_reads_outside(tmp_path, monkeypatch, swap_ancestor):
    """Also fails against the old path-based reader, without needing new IO APIs."""
    logs = tmp_path / "logs"
    logs.mkdir()
    nested = logs / "nested"
    nested.mkdir()
    candidate = nested / "swap.jsonl"
    write_message(candidate)
    outside = tmp_path / "outside"
    outside.mkdir()
    write_message(outside / candidate.name, "needle outside")
    original = session_history.scan_file

    def swap(*args):
        if swap_ancestor:
            nested.rename(logs / "moved")
            nested.symlink_to(outside, target_is_directory=True)
        else:
            candidate.unlink()
            candidate.symlink_to(outside / candidate.name)
        return original(*args)

    monkeypatch.setattr(session_history, "scan_file", swap)
    result = session_history.search(logs, ["needle"], 10)
    assert result["results"][0]["matches"][0]["preview"] == "needle inside"


@pytest.mark.parametrize("replacement", ["symlink", "fifo"])
def test_file_replacement_immediately_before_open_is_rejected(tmp_path, monkeypatch, replacement):
    logs = tmp_path / "logs"
    logs.mkdir()
    candidate = logs / "swap.jsonl"
    write_message(candidate)
    outside = tmp_path / "outside.jsonl"
    write_message(outside, "needle outside")
    original = os.open
    opened = []

    def swap(name, flags, *args, **kwargs):
        if name == candidate.name:
            opened.append(name)
            candidate.unlink()
            if replacement == "symlink":
                candidate.symlink_to(outside)
            else:
                os.mkfifo(candidate)
            # Assert before the call so a broken flag cannot hang this test.
            assert flags & os.O_NOFOLLOW and flags & os.O_NONBLOCK
        return original(name, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap)
    result = session_history.search(logs, ["needle"], 10)
    assert opened == [candidate.name]
    assert result["scanned_files"] == result["read_bytes"] == 0
    assert not result["results"]
    assert result["scan_truncated"] and "entry_unavailable" in result["scan_truncation_reasons"]


def test_directory_symlink_replacement_before_pin_is_rejected(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    nested = logs / "nested"
    nested.mkdir(parents=True)
    write_message(nested / "log.jsonl")
    outside = tmp_path / "outside"
    outside.mkdir()
    write_message(outside / "log.jsonl", "needle outside")
    original = os.open

    def swap(name, *args, **kwargs):
        if name == "nested":
            nested.rename(logs / "moved")
            nested.symlink_to(outside, target_is_directory=True)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap)
    result = session_history.search(logs, ["needle"], 10)
    assert result["read_bytes"] == 0 and not result["results"]
    assert result["scan_truncated"]


def test_pinned_directory_survives_ancestor_swap_before_file_open(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    nested = logs / "nested"
    nested.mkdir(parents=True)
    write_message(nested / "log.jsonl")
    outside = tmp_path / "outside"
    outside.mkdir()
    write_message(outside / "log.jsonl", "needle outside")
    original = os.open

    def swap(name, *args, **kwargs):
        if name == "log.jsonl":
            nested.rename(logs / "moved")
            nested.symlink_to(outside, target_is_directory=True)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap)
    result = session_history.search(logs, ["needle"], 10)
    assert result["results"][0]["matches"][0]["preview"] == "needle inside"


def test_growing_file_is_limited_to_initial_size(tmp_path, monkeypatch):
    log = tmp_path / "log.jsonl"
    raw = write_message(log)
    original = os.read

    def grow(fd, size):
        chunk = original(fd, size)
        with log.open("ab") as destination:
            destination.write(raw * 100)
        return chunk

    monkeypatch.setattr(os, "read", grow)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["read_bytes"] == len(raw)
    assert len(result["results"][0]["matches"]) == 1
    assert "file_changed" in result["scan_truncation_reasons"]
    assert result["limited_files"] == 1


def test_ten_thousand_empty_directories_are_bounded(tmp_path):
    for index in range(10_000):
        (tmp_path / str(index)).mkdir()
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["scanned_directories"] == session_history.MAX_SCAN_DIRECTORIES
    assert result["scanned_entries"] < 10_000
    assert result["scanned_files"] == result["read_bytes"] == 0
    assert result["scan_truncated"]
    assert "directories_limit" in result["scan_truncation_reasons"]


def test_large_non_jsonl_directory_is_bounded_before_materialization(tmp_path, monkeypatch):
    for index in range(300):
        (tmp_path / f"{index}.txt").touch()
    monkeypatch.setattr(session_history, "MAX_SCAN_ENTRIES", 128)
    original = os.scandir
    visited = []

    class CountEntries:
        def __init__(self, fd):
            self.iterator = original(fd)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.iterator.close()

        def __next__(self):
            entry = next(self.iterator)
            visited.append(entry.name)
            assert len(visited) <= 128, "Entry materialization exceeded the scan budget"
            return entry

    monkeypatch.setattr(os, "scandir", CountEntries)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["scanned_entries"] == 128
    assert len(visited) == 128
    assert result["scanned_files"] == result["read_bytes"] == 0
    assert result["scan_truncated"] and result["scan_truncation_reasons"] == ["entries_limit"]


@pytest.mark.parametrize("extra", [-1, 0, 1])
def test_total_read_budget_boundary(tmp_path, monkeypatch, extra):
    raw = write_message(tmp_path / "log.jsonl")
    monkeypatch.setattr(session_history, "MAX_TOTAL_READ_BYTES", len(raw) + extra)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["read_bytes"] == min(len(raw), len(raw) + extra)
    assert result["scan_truncated"] == (extra <= 0)
    assert result["malformed_records"] == 0
    assert result["matched_sessions"] == int(extra >= 0)
    assert ("read_bytes_limit" in result["scan_truncation_reasons"]) == (extra <= 0)


def test_total_read_budget_is_shared_across_files(tmp_path, monkeypatch):
    raw = write_message(tmp_path / "one.jsonl")
    write_message(tmp_path / "two.jsonl")
    monkeypatch.setattr(session_history, "MAX_TOTAL_READ_BYTES", len(raw) + 5)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["scanned_files"] == 2
    assert result["read_bytes"] == len(raw) + 5
    assert result["matched_sessions"] == 1 and result["malformed_records"] == 0
    assert result["scan_truncation_reasons"] == ["read_bytes_limit"]


@pytest.mark.parametrize("extra", [-1, 0, 1])
def test_per_file_byte_budget_boundary(tmp_path, monkeypatch, extra):
    raw = write_message(tmp_path / "log.jsonl")
    monkeypatch.setattr(session_history, "MAX_FILE_BYTES", len(raw) + extra)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["read_bytes"] == min(len(raw), len(raw) + extra)
    assert result["matched_sessions"] == int(extra >= 0)
    assert result["malformed_records"] == 0
    assert result["scan_truncated"] == (extra < 0)
    assert ("file_bytes_limit" in result["scan_truncation_reasons"]) == (extra < 0)


@pytest.mark.parametrize("extra", [-1, 0, 1])
def test_line_byte_budget_boundary(tmp_path, monkeypatch, extra):
    raw = write_message(tmp_path / "log.jsonl")
    monkeypatch.setattr(session_history, "MAX_LINE_BYTES", len(raw) + extra)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["matched_sessions"] == int(extra >= 0)
    assert result["scan_truncated"] == (extra < 0)
    assert ("line_bytes_limit" in result["scan_truncation_reasons"]) == (extra < 0)


@pytest.mark.parametrize("cap", [1, 2, 3])
def test_entry_budget_boundary(tmp_path, monkeypatch, cap):
    (tmp_path / "one.txt").touch()
    (tmp_path / "two.txt").touch()
    monkeypatch.setattr(session_history, "MAX_SCAN_ENTRIES", cap)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["scanned_entries"] == min(cap, 2)
    assert result["scan_truncated"] == (cap <= 2)


@pytest.mark.parametrize("cap", [1, 2, 3])
def test_directory_budget_boundary(tmp_path, monkeypatch, cap):
    (tmp_path / "nested").mkdir()
    write_message(tmp_path / "nested/log.jsonl")
    monkeypatch.setattr(session_history, "MAX_SCAN_DIRECTORIES", cap)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["scanned_directories"] == min(cap, 2)
    assert result["matched_sessions"] == int(cap >= 2)
    assert result["scan_truncated"] == (cap < 2)


@pytest.mark.parametrize("cap", [1, 2, 3])
def test_file_budget_boundary(tmp_path, monkeypatch, cap):
    write_message(tmp_path / "one.jsonl")
    write_message(tmp_path / "two.jsonl")
    monkeypatch.setattr(session_history, "MAX_SCAN_FILES", cap)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["scanned_files"] == min(cap, 2)
    assert result["matched_sessions"] == min(cap, 2)
    assert result["scan_truncated"] == (cap <= 2)


def test_deadline_before_traversal_reports_no_reads(tmp_path, monkeypatch):
    write_message(tmp_path / "log.jsonl")
    clock = iter([0, session_history.MAX_SCAN_SECONDS])
    monkeypatch.setattr(session_history.time, "monotonic", lambda: next(clock, session_history.MAX_SCAN_SECONDS))
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["scanned_entries"] == result["scanned_files"] == result["read_bytes"] == 0
    assert result["scan_truncated"] and result["scan_truncation_reasons"] == ["deadline"]


def test_deadline_during_read_preserves_actual_byte_counts(tmp_path, monkeypatch):
    raw = write_message(tmp_path / "log.jsonl")
    now = [0.0]
    monkeypatch.setattr(session_history.time, "monotonic", lambda: now[0])
    original = os.read

    def read(fd, size):
        data = original(fd, size)
        now[0] = session_history.MAX_SCAN_SECONDS
        return data

    monkeypatch.setattr(os, "read", read)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["scanned_files"] == 1 and result["read_bytes"] == len(raw)
    assert result["matched_sessions"] == 0 and result["limited_files"] == 1
    assert result["scan_truncation_reasons"] == ["deadline"]


def test_deadline_during_non_jsonl_traversal(tmp_path, monkeypatch):
    for index in range(20):
        (tmp_path / f"{index}.txt").touch()
    monkeypatch.setattr(session_history, "MAX_SCAN_SECONDS", 3)
    ticks = iter(range(10))
    monkeypatch.setattr(session_history.time, "monotonic", lambda: next(ticks))
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["scanned_entries"] == 2
    assert result["scanned_files"] == result["read_bytes"] == 0
    assert result["scan_truncated"] and result["scan_truncation_reasons"] == ["deadline"]


@pytest.mark.parametrize("extra", [-0.1, 0, 0.1])
def test_deadline_boundary(tmp_path, monkeypatch, extra):
    write_message(tmp_path / "log.jsonl")
    moment = session_history.MAX_SCAN_SECONDS + extra
    ticks = iter([0.0])
    monkeypatch.setattr(session_history.time, "monotonic", lambda: next(ticks, moment))
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["matched_sessions"] == int(extra < 0)
    assert result["scan_truncated"] == (extra >= 0)


def test_depth_budget_is_explicit(tmp_path, monkeypatch):
    log = tmp_path / "one/two/log.jsonl"
    log.parent.mkdir(parents=True)
    write_message(log)
    monkeypatch.setattr(session_history, "MAX_SCAN_DEPTH", 1)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["scanned_directories"] == 2 and result["scanned_files"] == 0
    assert result["skipped_entries"] == 1 and result["scan_truncated"]
    assert result["scan_truncation_reasons"] == ["depth_limit"]


@pytest.mark.parametrize("relative", [".", ".codex", ".claude", "active"])
def test_all_home_and_configuration_roots_stay_blocked(tmp_path, monkeypatch, relative):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "active"))
    root = tmp_path / relative
    root.mkdir(exist_ok=True)
    with pytest.raises(ValueError, match="session-log"):
        session_history.search(root, ["needle"], 10)


@pytest.mark.parametrize("relative", [".codex/sessions", ".claude/projects", "active/sessions"])
def test_explicit_session_subdirectories_are_allowed(tmp_path, monkeypatch, relative):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "active"))
    logs = tmp_path / relative
    logs.mkdir(parents=True)
    write_message(logs / "log.jsonl")
    result = session_history.search(logs, ["needle"], 10)
    assert result["matched_sessions"] == 1 and not result["scan_truncated"]


@pytest.mark.parametrize("protected", ["home", "codex", "claude", "codex_home", "claude_config"])
@pytest.mark.parametrize("ancestor", [False, True])
@pytest.mark.parametrize("alias", [False, True])
def test_protected_root_and_ancestors_rejected_before_read(tmp_path, monkeypatch, protected, ancestor, alias):
    roots = {name: tmp_path / name / "private"
             for name in ("home", "codex", "claude", "codex_home", "claude_config")}
    for root in roots.values():
        root.mkdir(parents=True)
    home = roots["home"]
    (home / ".codex").symlink_to(roots["codex"], target_is_directory=True)
    (home / ".claude").symlink_to(roots["claude"], target_is_directory=True)
    active_alias = tmp_path / "active-alias"
    active_alias.symlink_to(roots["codex_home"], target_is_directory=True)
    claude_alias = tmp_path / "claude-config-alias"
    claude_alias.symlink_to(roots["claude_config"], target_is_directory=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CODEX_HOME", str(active_alias))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_alias))
    private = roots[protected]
    write_message(private / "history.jsonl", "needle private history")
    logs = private / ("projects" if protected == "claude" else "sessions")
    logs.mkdir()
    write_message(logs / "log.jsonl", "needle selected session")
    selected = private.parent if ancestor else private
    if alias:
        selected_alias = tmp_path / "selected-alias"
        selected_alias.symlink_to(selected, target_is_directory=True)
        selected = selected_alias
    reads = []
    original = os.read

    def capture(fd, size):
        raw = original(fd, size)
        reads.append(raw)
        return raw

    monkeypatch.setattr(os, "read", capture)
    with pytest.raises(ValueError, match="session-log"):
        session_history.search(selected, ["needle"], 10)
    assert reads == []
    # Positive control: the same reader must actually read the allowed subtree.
    allowed = tmp_path / "allowed-alias"
    allowed.symlink_to(logs, target_is_directory=True)
    result = session_history.search(allowed, ["needle"], 10)
    assert result["matched_sessions"] == result["scanned_files"] == 1
    assert result["results"][0]["matches"][0]["preview"] == "needle selected session"
    assert b"needle selected session" in b"".join(reads)
    assert b"needle private history" not in b"".join(reads)


@pytest.mark.parametrize("variant", [".CODEX", ".CLAUDE", "USERS", "users/FAKE", "CUSTOMCLAUDE"])
def test_case_alias_protected_roots_are_rejected_before_scan(tmp_path, monkeypatch, variant):
    """Skips on case-sensitive Linux; review4 descent fixtures mock FD aliases."""
    home = tmp_path / "users/fake"
    codex = home / ".codex"
    claude = home / ".claude"
    custom = tmp_path / "customclaude"
    for root, subdir in ((codex, "sessions"), (claude, "projects"), (custom, "projects")):
        (root / subdir).mkdir(parents=True)
        write_message(root / "history.jsonl", "needle private history")
        write_message(root / subdir / "log.jsonl", "needle selected session")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
    selected = home / variant if variant.startswith(".") else tmp_path / variant
    if not selected.exists():
        pytest.skip("Filesystem distinguishes the actual case variant")
    reads = []
    scans = []
    original_read, original_scan = os.read, os.scandir

    def read(fd, size):
        reads.append(fd)
        return original_read(fd, size)

    def scan(fd):
        scans.append(fd)
        return original_scan(fd)

    monkeypatch.setattr(os, "read", read)
    monkeypatch.setattr(os, "scandir", scan)
    with pytest.raises(ValueError, match="session-log"):
        session_history.search(selected, ["needle"], 10)
    assert reads == scans == []
    for allowed in (codex / "sessions", claude / "projects", custom / "projects"):
        result = session_history.search(allowed, ["needle"], 10)
        assert result["matched_sessions"] == result["scanned_files"] == 1
        assert result["results"][0]["matches"][0]["preview"] == "needle selected session"
    assert reads and scans


def test_distinct_case_directory_is_allowed_when_filesystem_distinguishes_it(tmp_path, monkeypatch):
    home = tmp_path / "fake"
    home.mkdir()
    selected = tmp_path / "FAKE"
    if selected.exists():
        pytest.skip("Filesystem aliases different case spellings")
    selected.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    write_message(selected / "log.jsonl")
    assert session_history.search(selected, ["needle"], 10)["matched_sessions"] == 1


@pytest.mark.parametrize("variable", ["CODEX_HOME", "CLAUDE_CONFIG_DIR"])
def test_empty_config_environment_does_not_protect_cwd(tmp_path, monkeypatch, variable):
    home = tmp_path / "home"
    home.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    write_message(logs / "log.jsonl")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv(variable, "")
    monkeypatch.delenv("CLAUDE_CONFIG_DIR" if variable == "CODEX_HOME" else "CODEX_HOME", raising=False)
    monkeypatch.chdir(logs)
    result = session_history.search(logs, ["needle"], 10)
    assert result["matched_sessions"] == 1 and not result["scan_truncated"]


@pytest.mark.parametrize("variable", ["CODEX_HOME", "CLAUDE_CONFIG_DIR"])
@pytest.mark.parametrize("case_alias", [False, True])
def test_missing_protected_path_still_protects_existing_ancestor(tmp_path, monkeypatch, variable, case_alias):
    home = tmp_path / "home"
    home.mkdir()
    config_parent = tmp_path / "custom"
    config_parent.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv(variable, str(config_parent / "not-created/config"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR" if variable == "CODEX_HOME" else "CODEX_HOME", raising=False)
    selected = tmp_path / "CUSTOM" if case_alias else config_parent
    if not selected.exists():
        pytest.skip("Filesystem distinguishes the actual case variant")
    write_message(config_parent / "history.jsonl")

    def forbidden(*args):
        pytest.fail("Protected ancestor must be rejected before scanning or reading")

    monkeypatch.setattr(os, "scandir", forbidden)
    monkeypatch.setattr(os, "read", forbidden)
    with pytest.raises(ValueError, match="session-log"):
        session_history.search(selected, ["needle"], 10)


@pytest.mark.parametrize("error", [PermissionError, OSError])
@pytest.mark.parametrize("operation", ["open", "fstat"])
def test_protection_identity_error_prevents_scan(tmp_path, monkeypatch, error, operation):
    home = tmp_path / "home"
    home.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    original_open, original_fstat = os.open, os.fstat
    protected = home.stat()

    def unavailable(name, *args, **kwargs):
        if name == "home" and operation == "open":
            raise error("synthetic protected identity failure")
        return original_open(name, *args, **kwargs)

    def uninspectable(fd):
        info = original_fstat(fd)
        if operation == "fstat" and (info.st_dev, info.st_ino) == (protected.st_dev, protected.st_ino):
            raise error("synthetic protected identity failure")
        return info

    def forbidden(*args):
        pytest.fail("Unverified protection must never proceed to a scan")

    monkeypatch.setattr(os, "open", unavailable)
    monkeypatch.setattr(os, "fstat", uninspectable)
    monkeypatch.setattr(os, "scandir", forbidden)
    monkeypatch.setattr(os, "read", forbidden)
    with pytest.raises(error, match="protected identity failure"):
        session_history.search(logs, ["needle"], 10)


@pytest.mark.parametrize("swap_before_pin", [False, True])
def test_root_identity_and_scan_use_the_same_pinned_descriptor(tmp_path, monkeypatch, swap_before_pin):
    home = tmp_path / "home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    write_message(home / "history.jsonl", "needle private history")
    write_message(logs / "log.jsonl", "needle selected session")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    original_open, original_fstat, original_read = os.open, os.fstat, os.read
    selected_fd = []
    reads = []
    swapped = []

    def swap():
        logs.rename(tmp_path / "moved-logs")
        home.rename(logs)
        home.symlink_to(logs, target_is_directory=True)
        swapped.append(True)

    def opened(name, *args, **kwargs):
        if name == "logs" and not selected_fd:
            if swap_before_pin:
                swap()
            fd = original_open(name, *args, **kwargs)
            selected_fd.append(fd)
            return fd
        return original_open(name, *args, **kwargs)

    def inspected(fd):
        info = original_fstat(fd)
        if not swap_before_pin and selected_fd == [fd] and not swapped:
            swap()
        return info

    def read(fd, size):
        data = original_read(fd, size)
        reads.append(data)
        return data

    monkeypatch.setattr(os, "open", opened)
    monkeypatch.setattr(os, "fstat", inspected)
    monkeypatch.setattr(os, "read", read)
    if swap_before_pin:
        with pytest.raises(ValueError, match="session-log"):
            session_history.search(logs, ["needle"], 10)
        assert reads == []
    else:
        result = session_history.search(logs, ["needle"], 10)
        assert result["matched_sessions"] == result["scanned_files"] == 1
        assert result["results"][0]["matches"][0]["preview"] == "needle selected session"
        assert b"needle private history" not in b"".join(reads)
    assert swapped == [True]


def test_root_replacement_after_protection_check_cannot_redirect_scan(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    write_message(logs / "log.jsonl", "needle selected session")
    write_message(home / "history.jsonl", "needle private history")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    original = session_history_io.reject_protected_root
    checked = []

    def check(fd, protected):
        identities = original(fd, protected)
        checked.append(os.fstat(fd).st_ino)
        logs.rename(tmp_path / "moved")
        home.rename(logs)
        return identities

    original_scan = session_history.scan_directory

    def scan(fd, *args):
        assert checked == [os.fstat(fd).st_ino]
        return original_scan(fd, *args)

    monkeypatch.setattr(session_history_io, "reject_protected_root", check)
    monkeypatch.setattr(session_history, "scan_directory", scan)
    result = session_history.search(logs, ["needle"], 10)
    assert result["scanned_files"] == result["matched_sessions"] == 1
    assert result["results"][0]["matches"][0]["preview"] == "needle selected session"


@pytest.mark.parametrize("format_name", ["codex", "claude"])
@pytest.mark.parametrize("length", [20, 511, 512, 513, 30_000])
def test_external_metadata_is_bounded_and_marked(tmp_path, monkeypatch, format_name, length):
    # Unicode makes this a character boundary test, independently of byte limits.
    identifier = "경" * length
    cwd = "/" + "로" * (length - 1)
    metadata = {"id": identifier, "cwd": cwd}
    message = "needle " + "x" * 300
    if format_name == "codex":
        records = [{"type": "session_meta", "payload": metadata},
                   {"type": "user", "message": {"content": message}}]
    else:
        records = [{"type": "user", "sessionId": identifier, "cwd": cwd,
                    "message": {"content": message}}]
    (tmp_path / "log.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in records))
    opened = []
    original = session_history_io.open_entry

    def capture(name, parent_fd, *, directory):
        if not directory:
            opened.append(name)
        return original(name, parent_fd, directory=directory)

    monkeypatch.setattr(session_history_io, "open_entry", capture)
    result = session_history.search(tmp_path, ["needle"], 10)
    record = result["results"][0]
    assert record["id"] == identifier[:512]
    assert record["cwd"] == cwd[:512]
    assert record["id_truncated"] == (length > 512)
    assert record["cwd_truncated"] == (length > 512)
    assert session_history.MAX_SESSION_ID_CHARS == session_history.MAX_CWD_CHARS == 512
    assert opened == ["log.jsonl"]
    assert record["matches"][0]["preview"] == message[:session_history.PREVIEW_CHARS]
    assert not record["truncated"] and not result["scan_truncated"]
    assert "Untrusted transcript data" in result["notice"]


def test_missing_metadata_preserves_filename_and_null_cwd(tmp_path):
    write_message(tmp_path / "fallback.jsonl")
    record = session_history.search(tmp_path, ["needle"], 10)["results"][0]
    assert record["id"] == "fallback" and record["cwd"] is None
    assert record["id_truncated"] is False and record["cwd_truncated"] is False


@pytest.mark.parametrize("id_length,cwd_length", [(600, 20), (20, 600)])
def test_metadata_truncation_flags_are_independent(tmp_path, id_length, cwd_length):
    write_message(tmp_path / "log.jsonl", sessionId="i" * id_length, cwd="/" * cwd_length)
    record = session_history.search(tmp_path, ["needle"], 10)["results"][0]
    assert record["id_truncated"] == (id_length > 512)
    assert record["cwd_truncated"] == (cwd_length > 512)


def test_unsupported_platform_fails_closed(tmp_path, monkeypatch):
    write_message(tmp_path / "log.jsonl")
    monkeypatch.setattr(session_history_io, "SECURE_IO_SUPPORTED", False)
    with pytest.raises(ValueError, match="requires POSIX"):
        session_history.search(tmp_path, ["needle"], 10)


def test_preview_match_limit_metadata_and_malformed_counts(tmp_path):
    log = tmp_path / "log.jsonl"
    records = [b"bad-json\n", b"[]\n", b"\xff\n", json.dumps({
        "type": "session_meta", "payload": {"id": "codex-id", "cwd": "/project"},
    }).encode() + b"\n"]
    message = "nEeDlE " + "x" * 300
    records += [json.dumps({"type": "assistant", "message": {"content": message}}).encode() + b"\n"] * 6
    log.write_bytes(b"".join(records))
    result = session_history.search(tmp_path, ["absent", "NEEDLE"], 10)
    record = result["results"][0]
    assert result["malformed_records"] == record["malformed_records"] == 3
    assert record["id"] == "codex-id" and record["cwd"] == "/project"
    assert len(record["matches"]) == 5 and record["matches"][0]["line"] == 5
    assert record["matches"][0]["preview"] == message[:240]
    assert record["truncated"] and record["truncation_reasons"] == ["matches_limit"]


def test_excessively_nested_json_is_reported_as_malformed(tmp_path):
    (tmp_path / "deep.jsonl").write_bytes(b"[" * 5000 + b"]" * 5000 + b"\n")
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["malformed_records"] == 1 and not result["results"]
