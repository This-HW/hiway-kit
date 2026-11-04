from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
import session_history
import session_history_io


def test_regular_file_is_read_via_pinned_fd(tmp_path):
    (tmp_path / "log.jsonl").write_bytes(b"inside")
    with session_history_io.open_root(tmp_path.resolve()) as root_fd:
        with session_history_io.open_entry("log.jsonl", root_fd, directory=False) as source_fd:
            assert os.read(source_fd, 100) == b"inside"
        with pytest.raises(OSError):
            os.fstat(source_fd)
    with pytest.raises(OSError):
        os.fstat(root_fd)


@pytest.mark.parametrize("directory", [False, True])
def test_static_symlink_is_never_opened(tmp_path, directory):
    target = tmp_path / "target"
    if directory:
        target.mkdir()
    else:
        target.write_bytes(b"outside")
    (tmp_path / "link").symlink_to(target, target_is_directory=directory)
    with session_history_io.open_root(tmp_path.resolve()) as root_fd, pytest.raises(OSError), session_history_io.open_entry("link", root_fd, directory=directory):
        pytest.fail("A symlink must never yield a descriptor")


def test_fifo_is_nonblocking_and_rejected_by_fstat(tmp_path, monkeypatch):
    os.mkfifo(tmp_path / "pipe")
    original = os.open
    rejected_fd = []

    def capture(name, flags, *args, **kwargs):
        if name == "pipe":
            assert flags & os.O_NONBLOCK and flags & os.O_NOFOLLOW
        fd = original(name, flags, *args, **kwargs)
        if name == "pipe":
            rejected_fd.append(fd)
        return fd

    monkeypatch.setattr(os, "open", capture)
    with session_history_io.open_root(tmp_path.resolve()) as root_fd:
        with pytest.raises(OSError, match="regular file"), session_history_io.open_entry("pipe", root_fd, directory=False):
            pytest.fail("A FIFO must never yield a descriptor")
        with pytest.raises(OSError):
            os.fstat(rejected_fd[0])


def test_root_symlink_replacement_after_resolve_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / "logs"
    root.mkdir()
    resolved = root.resolve(strict=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    original = os.open

    def swap(name, *args, **kwargs):
        if name == "logs":
            root.rename(tmp_path / "moved")
            root.symlink_to(outside, target_is_directory=True)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap)
    with pytest.raises(OSError), session_history_io.open_root(resolved):
        pytest.fail("A raced-in root symlink must not be opened")


def test_root_ancestor_swap_does_not_redirect_relative_open(tmp_path, monkeypatch):
    ancestor = tmp_path / "ancestor"
    root = ancestor / "logs"
    root.mkdir(parents=True)
    (root / "log.jsonl").write_bytes(b"inside")
    outside = tmp_path / "outside"
    (outside / "logs").mkdir(parents=True)
    (outside / "logs/log.jsonl").write_bytes(b"outside")
    resolved = root.resolve(strict=True)
    original = os.open

    def swap(name, *args, **kwargs):
        if name == "logs":
            ancestor.rename(tmp_path / "moved")
            ancestor.symlink_to(outside, target_is_directory=True)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap)
    with session_history_io.open_root(resolved) as root_fd, session_history_io.open_entry("log.jsonl", root_fd, directory=False) as source_fd:
        assert os.read(source_fd, 100) == b"inside"


@pytest.mark.parametrize("read_error", [False, True])
def test_search_closes_every_owned_descriptor(tmp_path, monkeypatch, read_error):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "log.jsonl").write_bytes(b"{}\n")
    open_original, dup_original, close_original = os.open, os.dup, os.close
    owned = set()

    def opened(*args, **kwargs):
        fd = open_original(*args, **kwargs)
        owned.add(fd)
        return fd

    def duplicated(fd):
        duplicate = dup_original(fd)
        owned.add(duplicate)
        return duplicate

    def closed(fd):
        owned.remove(fd)
        return close_original(fd)

    def broken_read(*args):
        raise OSError("synthetic read failure")

    monkeypatch.setattr(os, "open", opened)
    monkeypatch.setattr(os, "dup", duplicated)
    monkeypatch.setattr(os, "close", closed)
    if read_error:
        monkeypatch.setattr(os, "read", broken_read)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert not owned
    assert result["scanned_files"] == 1
    assert result["scan_truncated"] == read_error
    if read_error:
        assert result["scan_truncation_reasons"] == ["read_error"]


def test_fd_traversal_never_reopens_display_paths(tmp_path, monkeypatch):
    (tmp_path / "log.jsonl").write_text('{"type":"user","message":{"content":"needle"}}')

    def forbidden(*args, **kwargs):
        pytest.fail("A validated Path must not be reopened")

    monkeypatch.setattr(Path, "open", forbidden)
    result = session_history.search(tmp_path, ["needle"], 10)
    assert result["matched_sessions"] == 1
