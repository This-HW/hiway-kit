from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
import lsp_query
import lsp_transport


def arguments(root, action="diagnostics", file="example.c"):
    return argparse.Namespace(root=str(root), file=file, action=action, line=1, column=1,
                              server=None, server_arg=[])


@pytest.mark.parametrize("server", ["sh", "python3", "./clangd", "bin/clangd", "../clangd", "a\\clangd", "", ".", ".."])
def test_server_policy_rejects_implicit_arbitrary_execution(monkeypatch, server):
    monkeypatch.setattr(lsp_query.shutil, "which", lambda name: pytest.fail("rejected server must not be resolved"))
    with pytest.raises(ValueError):
        lsp_query.select_server("c", server)


def executable(directory, name):
    directory.mkdir(exist_ok=True)
    path = directory / name
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o700)
    return path


@pytest.mark.parametrize("server", ["clangd", "ruff", "gopls", "rust-analyzer",
                                   "basedpyright-langserver", "pyright-langserver", "typescript-language-server"])
def test_known_server_basenames_remain_allowed(tmp_path, monkeypatch, server):
    binary = executable(tmp_path / "external", server)
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("PATH", str(binary.parent))
    for value in (server, str(binary)):
        assert lsp_query.select_server("c", value, root=root) == [str(binary)]


def test_custom_server_requires_opt_in_but_relative_paths_stay_forbidden(tmp_path, monkeypatch):
    binary = executable(tmp_path / "external", "custom-engine")
    monkeypatch.setenv("PATH", str(binary.parent))
    for value in (str(binary), binary.name):
        assert lsp_query.select_server("c", value, True, root=tmp_path) == [str(binary)]
    for server in ("./custom-engine", "nested/custom-engine"):
        with pytest.raises(ValueError):
            lsp_query.select_server("c", server, True, root=tmp_path)


@pytest.mark.parametrize("explicit", [False, True])
def test_workspace_server_requires_opt_in_before_execution(tmp_path, monkeypatch, capsys, explicit):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "example.c").write_text("int x;\n")
    marker = tmp_path / "executed"
    binary = executable(root / "tools", "clangd")
    binary.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n")
    monkeypatch.setenv("PATH", str(binary.parent))
    monkeypatch.setattr(sys, "argv", ["lsp_query", "symbols", "--root", str(root), "--file", "example.c",
                                     *(["--server", str(binary)] if explicit else [])])
    assert lsp_query.main() == 2
    assert "allow-custom-server" in json.loads(capsys.readouterr().out)["reason"]
    assert not marker.exists()
    assert lsp_query.select_server("c", str(binary) if explicit else None, True, root=root)[0] == str(binary)


def test_workspace_known_symlink_cannot_impersonate_path_server(tmp_path, monkeypatch):
    trusted = executable(tmp_path / "external", "clangd")
    root = tmp_path / "workspace"
    root.mkdir()
    link = root / "clangd"
    link.symlink_to("/bin/sh")
    monkeypatch.setenv("PATH", str(trusted.parent))
    with pytest.raises(ValueError, match="allow-custom-server"):
        lsp_query.select_server("c", str(link), root=root)
    assert lsp_query.select_server("c", str(link), True, root=root) == [str(Path("/bin/sh").resolve())]


def test_external_known_symlink_matches_path_server(tmp_path, monkeypatch):
    trusted = executable(tmp_path / "external", "clangd")
    aliases = tmp_path / "aliases"
    aliases.mkdir()
    alias = aliases / "clangd"
    alias.symlink_to(trusted)
    monkeypatch.setenv("PATH", str(trusted.parent))
    assert lsp_query.select_server("c", str(alias), root=tmp_path / "workspace") == [str(trusted)]


def test_different_external_known_basename_requires_opt_in(tmp_path, monkeypatch, capsys):
    trusted = executable(tmp_path / "trusted", "clangd")
    binary = executable(tmp_path / "other", "clangd")
    marker = tmp_path / "executed"
    binary.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n")
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "example.c").write_text("int x;\n")
    monkeypatch.setenv("PATH", str(trusted.parent))
    monkeypatch.setattr(sys, "argv", ["lsp_query", "symbols", "--root", str(root), "--file", "example.c",
                                     "--server", str(binary)])
    assert lsp_query.main() == 2
    assert "allow-custom-server" in json.loads(capsys.readouterr().out)["reason"]
    assert not marker.exists()


@pytest.mark.parametrize("explicit", [None, "clangd", "absolute"])
def test_relative_which_requires_opt_in_and_is_fixed_before_launch(tmp_path, monkeypatch, explicit):
    root = tmp_path / "workspace"
    root.mkdir()
    binary = executable(tmp_path / "tools", "clangd")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "tools")
    value = str(binary) if explicit == "absolute" else explicit
    with pytest.raises(ValueError, match="allow-custom-server"):
        lsp_query.select_server("c", value, root=root)
    assert lsp_query.select_server("c", value, True, root=root)[0] == str(binary)


def test_relative_path_server_is_rejected_before_execution(tmp_path, monkeypatch, capsys):
    binary = executable(tmp_path / "tools", "clangd")
    marker = tmp_path / "executed"
    binary.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n")
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "example.c").write_text("int x;\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "tools")
    monkeypatch.setattr(sys, "argv", ["lsp_query", "symbols", "--root", str(root), "--file", "example.c"])
    assert lsp_query.main() == 2
    assert "allow-custom-server" in json.loads(capsys.readouterr().out)["reason"]
    assert not marker.exists()


def test_selected_server_is_resolved_only_once(tmp_path, monkeypatch):
    binary = executable(tmp_path / "external", "clangd")
    calls = []
    resolve = Path.resolve
    def once(path, *args, **kwargs):
        calls.append(str(path))
        assert calls.count(str(path)) == 1
        return resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", once)
    monkeypatch.setattr(lsp_query.shutil, "which", lambda name: str(binary))
    assert lsp_query.select_server("c", str(binary), root=tmp_path / "workspace") == [str(binary)]


def test_server_symlink_loop_is_a_json_error(tmp_path, monkeypatch, capsys):
    binary = tmp_path / "clangd"
    binary.symlink_to(binary)
    (tmp_path / "example.c").write_text("int x;\n")
    monkeypatch.setattr(lsp_query.shutil, "which", lambda name: str(binary))
    monkeypatch.setattr(sys, "argv", ["lsp_query", "symbols", "--root", str(tmp_path),
                                     "--file", "example.c", "--server", "clangd"])
    assert lsp_query.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error" and result["environment"] == "filtered"


@pytest.mark.parametrize("shortfall", [0, 1])
def test_receive_byte_budget_counts_headers_at_boundary(tmp_path, monkeypatch, shortfall):
    raw = json.dumps({"jsonrpc": "2.0", "id": 1, "result": []}).encode()
    frame = b"X-Padding: " + b"x"*900 + b"\r\nContent-Length: %d\r\n\r\n" % len(raw) + raw
    maximum = len(frame) - shortfall
    monkeypatch.setattr(lsp_transport, "MAX_RECEIVED_BYTES", maximum)
    script = f"import sys,time; sys.stdout.buffer.write({frame!r}); sys.stdout.buffer.flush(); time.sleep(30)"
    connection = lsp_transport.Connection([sys.executable, "-B", "-c", script], str(tmp_path))
    try:
        if shortfall:
            with pytest.raises(lsp_transport.LspError, match="byte budget"):
                connection.request("initialize", {})
        else:
            assert connection.request("initialize", {}) == []
        assert connection.received_bytes == len(frame)
    finally:
        connection.close()


def test_lsp_reader_discards_log_payloads_without_retaining_or_counting_them(tmp_path):
    script = """
import json,sys,time
def send(message):
    raw=json.dumps(dict(jsonrpc='2.0', **message)).encode()
    sys.stdout.buffer.write(b'Content-Length: %d\\r\\n\\r\\n'%len(raw)+raw)
    sys.stdout.buffer.flush()
for _ in range(300): send(dict(method='window/logMessage',params={'message':'x'*4096}))
send(dict(id=1,result=[]))
time.sleep(30)
"""
    connection = lsp_transport.Connection([sys.executable, "-B", "-c", script], str(tmp_path))
    try:
        assert connection.request("initialize", {}) == []
        assert connection.notifications == []
        assert connection.notification_count == 0
    finally:
        connection.close()


def test_missing_server_is_unverified(tmp_path, monkeypatch, capsys):
    (tmp_path / "example.c").write_text("int x;\n")
    monkeypatch.setattr(lsp_query, "select_server", lambda *args: None)
    assert lsp_query.query(arguments(tmp_path)) == 3
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "unavailable"
    assert "untrusted" in result["notice"].lower()


@pytest.mark.parametrize("language,name", [("c", "clangd"), ("cpp", "clangd"), ("python", "basedpyright-langserver"),
                                          ("typescriptreact", "typescript-language-server"),
                                          ("javascriptreact", "typescript-language-server"),
                                          ("rust", "rust-analyzer"), ("go", "gopls")])
def test_automatic_server_support_is_preserved(tmp_path, monkeypatch, language, name):
    binary = executable(tmp_path / "external", name)
    monkeypatch.setenv("PATH", str(binary.parent))
    command = lsp_query.select_server(language, None, root=tmp_path / "workspace")
    assert command[0] == str(binary)


def test_cli_rejects_custom_server_before_execution(tmp_path, monkeypatch, capsys):
    (tmp_path / "example.c").write_text("int x;\n")
    marker = tmp_path / "executed"
    server = tmp_path / "custom-server"
    server.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n")
    server.chmod(0o700)
    monkeypatch.setattr(sys, "argv", ["lsp_query", "symbols", "--root", str(tmp_path),
                                     "--file", "example.c", "--server", str(server)])
    assert lsp_query.main() == 2
    assert not marker.exists()
    assert "allow-custom-server" in json.loads(capsys.readouterr().out)["reason"]


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


def test_close_after_unreaped_server_exit(tmp_path):
    connection = lsp_transport.Connection([sys.executable, "-B", "-c", "pass"], str(tmp_path))
    connection.reader.join(timeout=2)
    # Leave the exited leader unreaped to exercise macOS's zombie-group EPERM.
    time.sleep(.1)
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


@pytest.mark.skipif(not (shutil.which("clangd") and shutil.which("clang")), reason="optional clang/clangd")
def test_real_clangd_preserves_cpath_header_resolution(tmp_path, monkeypatch, capsys):
    include = tmp_path / "include"
    include.mkdir()
    (include / "fixture_header.h").write_text("int fixture(void);\n")
    source = tmp_path / "example.c"
    source.write_text('#include <fixture_header.h>\nint caller(void) { return fixture(); }\n')
    monkeypatch.setenv("CPATH", str(include))
    compiled = subprocess.run([shutil.which("clang"), "-fsyntax-only", str(source)], cwd=tmp_path,
                              env=dict(os.environ), capture_output=True, check=False)
    assert compiled.returncode == 0, compiled.stderr
    rc = lsp_query.query(arguments(tmp_path))
    result = json.loads(capsys.readouterr().out)
    assert result["result"] == []
    assert rc == (0 if result["complete"] else 2)
    assert result["environment"] == "filtered"
    monkeypatch.delenv("CPATH")
    assert lsp_query.query(arguments(tmp_path)) == 1
    broken = json.loads(capsys.readouterr().out)
    assert any("file not found" in row["message"] for row in broken["result"])


@pytest.mark.skipif(not shutil.which("clangd"), reason="optional clangd language server")
@pytest.mark.parametrize("alias", [False, True])
def test_real_clangd_absolute_path_and_known_symlink(tmp_path, monkeypatch, capsys, alias):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "example.c").write_text("int fixture;\n")
    installed = Path(shutil.which("clangd")).resolve()
    server = installed
    if alias:
        server = tmp_path / "clangd"
        server.symlink_to(installed)
    monkeypatch.setattr(sys, "argv", ["lsp_query", "symbols", "--root", str(root), "--file", "example.c",
                                     "--server", str(server)])
    assert lsp_query.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["result"] and result["server"] == str(installed)
