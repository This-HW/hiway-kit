"""P-7 uses mocked directory identities, including on case-sensitive Linux.

The existing case-alias tests skip on Linux filesystems which distinguish case;
the alternate-identity fixture here exercises the same FD defense everywhere,
without directory hard links, symlink rejection, or real home traversal.
"""
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


@pytest.fixture
def homes(tmp_path, monkeypatch):
    env_home = tmp_path / "env-home"
    passwd_home = tmp_path / "passwd-parent/home"
    env_home.mkdir()
    passwd_home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(env_home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: SimpleNamespace(pw_dir=str(passwd_home)))
    return env_home, passwd_home


def message(path, text):
    path.write_text(json.dumps({"type": "user", "message": {"content": text}}) + "\n")


@pytest.mark.parametrize("protected", ["home", "passwd", "codex", "claude", "custom"])
def test_protected_identity_during_descent(tmp_path, monkeypatch, homes, protected):
    """Simulate firmlink identity through a real, non-symlink child directory."""
    home, passwd_home = homes
    custom = tmp_path / "custom"
    custom.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
    roots = {"home": home, "passwd": passwd_home, "codex": home / ".codex",
             "claude": home / ".claude", "custom": custom}
    private = roots[protected]
    private.mkdir(exist_ok=True)
    sessions = private / "sessions"
    sessions.mkdir()
    message(sessions / "log.jsonl", "needle selected session")
    selected = tmp_path / "volume"
    alias = selected / "hard-path"
    alias.mkdir(parents=True)
    message(alias / "history.jsonl", "needle private history")
    message(selected / "allowed.jsonl", "needle allowed")
    identity = private.stat()
    alias_identity = alias.stat()
    original_fstat, original_scan, original_read = os.fstat, os.scandir, os.read
    scanned, reads = [], []

    def fstat(fd):
        info = original_fstat(fd)
        if (info.st_dev, info.st_ino) == (alias_identity.st_dev, alias_identity.st_ino):
            values = list(info)
            values[1], values[2] = identity.st_ino, identity.st_dev
            return os.stat_result(values)
        return info

    def scan(fd):
        info = original_fstat(fd)
        scanned.append((info.st_dev, info.st_ino))
        return original_scan(fd)

    def read(fd, size):
        raw = original_read(fd, size)
        reads.append(raw)
        return raw

    monkeypatch.setattr(os, "fstat", fstat)
    monkeypatch.setattr(os, "scandir", scan)
    monkeypatch.setattr(os, "read", read)
    result = session_history.search(selected, ["needle"], 10)
    assert (alias_identity.st_dev, alias_identity.st_ino) not in scanned
    assert b"private history" not in b"".join(reads)
    assert result["scanned_files"] == result["matched_sessions"] == 1
    assert result["results"][0]["matches"][0]["preview"] == "needle allowed"
    assert result["scan_truncated"] and result["skipped_entries"] == 1
    assert result["scan_truncation_reasons"] == ["protected_directory"]
    allowed = session_history.search(sessions, ["needle"], 10)
    assert allowed["matched_sessions"] == 1 and not allowed["scan_truncated"]


@pytest.mark.parametrize("kind", ["home", "codex", "claude", "ancestor"])
def test_passwd_home_is_protected_with_alternate_home(tmp_path, monkeypatch, homes, kind):
    _, passwd_home = homes
    selected = {"home": passwd_home, "codex": passwd_home / ".codex",
                "claude": passwd_home / ".claude", "ancestor": passwd_home.parent}[kind]
    selected.mkdir(exist_ok=True)
    with pytest.raises(ValueError, match="session-log"):
        session_history.search(selected, ["needle"], 10)


def test_empty_home_does_not_protect_cwd(tmp_path, monkeypatch, homes):
    monkeypatch.setenv("HOME", "")
    selected = tmp_path / "cwd"
    selected.mkdir()
    monkeypatch.chdir(selected)
    message(selected / "log.jsonl", "needle allowed")
    result = session_history.search(selected, ["needle"], 10)
    assert result["matched_sessions"] == 1 and not result["scan_truncated"]


@pytest.mark.parametrize("variable", ["CODEX_HOME", "CLAUDE_CONFIG_DIR"])
def test_tilde_config_root_and_ancestor_are_protected(tmp_path, monkeypatch, homes, variable):
    home, _ = homes
    config = home / "alternate/config"
    config.mkdir(parents=True)
    monkeypatch.setenv(variable, "~/alternate/config")
    for selected in (config, config.parent):
        with pytest.raises(ValueError, match="session-log"):
            session_history.search(selected, ["needle"], 10)
    logs = config / "sessions"
    logs.mkdir()
    message(logs / "log.jsonl", "needle allowed")
    assert session_history.search(logs, ["needle"], 10)["matched_sessions"] == 1


@pytest.mark.parametrize("protection", [False, True])
def test_python39_symlink_loop_runtime_error_is_json(tmp_path, monkeypatch, homes, capsys, protection):
    original = Path.resolve
    selected = tmp_path / "logs"
    selected.mkdir()

    def resolve(path, *args, **kwargs):
        if path == (homes[0] if protection else selected):
            raise RuntimeError("Symlink loop from synthetic Python 3.9 resolver " + "x" * 4096)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(sys, "argv", ["session-history", "--root", str(selected), "--query", "needle"])
    assert session_history.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error" and "Symlink loop" in result["reason"]
    assert len(result["reason"]) <= 1024
