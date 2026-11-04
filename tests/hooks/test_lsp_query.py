from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
import lsp_query
import lsp_transport


def arguments(root, action="diagnostics", file="example.c"):
    return argparse.Namespace(root=str(root), file=file, action=action, line=1, column=1,
                              server=None, server_arg=[])


def test_missing_server_is_unverified(tmp_path, monkeypatch, capsys):
    (tmp_path / "example.c").write_text("int x;\n")
    monkeypatch.setattr(lsp_query, "select_server", lambda *args: None)
    assert lsp_query.query(arguments(tmp_path)) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "unavailable"


def test_request_timeout_is_not_empty_success(tmp_path, monkeypatch):
    monkeypatch.setattr(lsp_transport, "REQUEST_TIMEOUT", .1)
    connection = lsp_transport.Connection([sys.executable, "-c", "import time; time.sleep(30)"], str(tmp_path))
    try:
        with pytest.raises(lsp_transport.LspError, match="timed out"):
            connection.request("initialize", {})
    finally:
        connection.close()
    assert connection.process.returncode is not None


def test_malformed_frame_is_rejected(tmp_path):
    command = [sys.executable, "-c", "import sys; sys.stdout.write('Content-Length: 999999999\\r\\n\\r\\n'); sys.stdout.flush()"]
    connection = lsp_transport.Connection(command, str(tmp_path))
    try:
        with pytest.raises(lsp_transport.LspError):
            connection.request("initialize", {})
    finally:
        connection.close()


def test_workspace_edit_request_is_declined(tmp_path):
    connection = lsp_transport.Connection([sys.executable, "-c", "import time; time.sleep(30)"], str(tmp_path))
    sent = []
    connection.send = sent.append
    connection.messages.put({"jsonrpc": "2.0", "id": 90, "method": "workspace/applyEdit", "params": {"edit": {}}})
    try:
        connection.receive(1e12)
        assert sent[0]["result"]["applied"] is False
    finally:
        connection.close()


def test_invalid_server_configuration_request_is_rejected(tmp_path):
    connection = lsp_transport.Connection([sys.executable, "-c", "import time; time.sleep(30)"], str(tmp_path))
    connection.messages.put({"jsonrpc": "2.0", "id": 90, "method": "workspace/configuration", "params": {"items": None}})
    try:
        with pytest.raises(lsp_transport.LspError, match="configuration"):
            connection.receive(1e12)
    finally:
        connection.close()


def test_close_after_server_exits(tmp_path):
    connection = lsp_transport.Connection([sys.executable, "-c", "pass"], str(tmp_path))
    connection.process.wait(timeout=3)
    connection.close()
    assert connection.process.returncode == 0


def test_response_without_result_is_not_success(tmp_path):
    connection = lsp_transport.Connection([sys.executable, "-c", "import time; time.sleep(30)"], str(tmp_path))
    connection.send = lambda message: None
    connection.messages.put({"jsonrpc": "2.0", "id": 1})
    try:
        with pytest.raises(lsp_transport.LspError, match="no result"):
            connection.request("initialize", {})
    finally:
        connection.close()


@pytest.mark.skipif(not shutil.which("clangd"), reason="optional clangd language server")
def test_real_clangd_diagnostics_and_navigation(tmp_path, capsys):
    source = tmp_path / "example.c"
    source.write_text("int twice(int x) { return x * 2; }\nint caller(void) { return twice(3); }\n")
    original = source.read_bytes()
    for action in ("diagnostics", "symbols", "definition", "references"):
        args = arguments(tmp_path, action)
        args.line, args.column = 2, 27
        rc = lsp_query.query(args)
        result = json.loads(capsys.readouterr().out)
        if action == "diagnostics":
            # clangd may only support push: empty push is provisional, never a
            # verified clean result. A negotiated full pull may be complete.
            assert rc == (0 if result["complete"] else 2)
            assert result["status"] == ("ok" if result["complete"] else "unverified")
            assert result["result"] == []
        else:
            assert rc == 0
            assert result["status"] == "ok"
            assert result["result"]
    assert source.read_bytes() == original
    source.write_text("int broken(void) { return missing_symbol; }\n")
    assert lsp_query.query(arguments(tmp_path)) == 1
    assert any(row["severity"] == 1 for row in json.loads(capsys.readouterr().out)["result"])
