from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
import session_history


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
