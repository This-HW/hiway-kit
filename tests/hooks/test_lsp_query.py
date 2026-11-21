from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
import lsp_query
import lsp_transport
from lsp_index_policy import IndexUnavailable
from lsp_index_resources import Deadline


def arguments(root, action="diagnostics", file="example.c"):
    return argparse.Namespace(root=str(root), file=file, action=action, line=1, column=1,
                              server=None, server_arg=[])


def test_indexed_clangd_argv_includes_unlimited_references(tmp_path):
    assert lsp_query.indexed_server_command("/opt/clangd", tmp_path) == [
        "/opt/clangd", "--background-index", "--limit-references=0", "-j", "2",
        "--enable-config=false", "--compile-commands-dir=" + str(tmp_path), "--log=error",
    ]


@pytest.mark.parametrize("failure", [None, "progress", "coverage", "final"])
def test_indexed_query_marks_complete_only_after_progress_coverage_and_cleanup(
        tmp_path, monkeypatch, capsys, failure):
    root = tmp_path / "workspace"
    root.mkdir()
    source = root / "main.c"
    source.write_text("int value;\n")
    compiler = Path(sys.executable).resolve()
    cdb = root / "compile_commands.json"
    cdb.write_text(json.dumps([{"directory": str(root), "file": str(source),
                                "arguments": [str(compiler), "-c", str(source)]}]))
    cache_home = tmp_path / "cache-home"
    cache_home.mkdir()
    monkeypatch.setenv("HOME", str(cache_home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home / "xdg"))
    fake_server = tmp_path / "clangd"
    fake_server.write_text("fixture")
    monkeypatch.setattr(lsp_query, "select_server", lambda *args, **kwargs: [str(fake_server)])
    monkeypatch.setattr(lsp_query, "_indexed_toolchain",
                        lambda command, root, env, deadline: (command[0], ("clangd", 21), None,
                                                              (str(root), 1, 2)))
    coverage_complete = failure != "coverage"
    monkeypatch.setattr(lsp_query, "certify", lambda fd, sources, deadline, **kwargs:
                        lsp_query.Coverage(len(sources), len(sources) if coverage_complete else 0,
                                           coverage_complete, None if coverage_complete else
                                           "index_coverage_unverified"))

    location = {"uri": source.as_uri(), "range": {
        "start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}}}
    instances = []

    class FakeConnection:
        def __init__(self, command, cwd, **kwargs):
            self.command, self.cwd, self.kwargs = command, cwd, kwargs
            self.requests = []
            self.finished = False
            self.compile_dir = Path(next(arg.split("=", 1)[1] for arg in command
                                         if arg.startswith("--compile-commands-dir=")))
            instances.append(self)

        def request(self, method, params, **kwargs):
            self.requests.append(method)
            if method == "initialize":
                return {"capabilities": {}}
            if failure == "final" and self.requests.count(method) > 1:
                return ["malformed final location"]
            return [location]

        def notify(self, method, params):
            pass

        def wait_for_background_index(self):
            if failure == "progress":
                raise lsp_query.IndexUnavailable("index_deadline", "test withheld progress end")
            index = self.compile_dir / ".cache" / "clangd" / "index"
            index.mkdir(parents=True, exist_ok=True)
            (index / "main.c.0123456789abcdef.idx").write_bytes(b"fixture-shard")
            return "progress_end"

        def finish_indexed(self, *, graceful=True):
            self.finished = True

    monkeypatch.setattr(lsp_query, "Connection", FakeConnection)
    args = arguments(root, "references", "main.c")
    args.line = args.column = 1

    assert lsp_query.query(args) == (0 if failure is None else 2)
    payload = json.loads(capsys.readouterr().out)
    assert payload["complete"] is (failure is None)
    assert payload["result"] == [location]
    assert payload["index"]["cache_classification"] == "new"
    assert payload["index"]["deadline_seconds"] == 30.0
    assert payload["index"]["cache_reused"] is False
    assert instances[0].finished is True
    expected_requests = ["initialize", "textDocument/references"]
    if failure not in ("progress", "coverage"):
        expected_requests.append("textDocument/references")
    assert instances[0].requests == expected_requests
    if failure is not None:
        expected_reason = {"progress": "index_deadline", "coverage": "index_coverage_unverified",
                           "final": "index_response_unverified"}[failure]
        assert payload["reason"] == expected_reason
    assert instances[0].command == [
        str(fake_server), "--background-index", "--limit-references=0", "-j", "2",
        "--enable-config=false", "--compile-commands-dir=" + str(instances[0].compile_dir), "--log=error"]


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
        command = lsp_query.select_server("c", value, root=root)
        defaults = next(args for candidates in lsp_query.SERVER_CANDIDATES.values() for name, args in candidates if name == server)
        assert command == [str(binary), *defaults]


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
    command = lsp_query.select_server("c", str(link), True, root=root)
    assert command == [str(link), "--background-index=false", "--log=error"]
    assert command[0].executable == str(Path("/bin/sh").resolve())


def test_external_known_symlink_matches_path_server(tmp_path, monkeypatch):
    (tmp_path / "workspace").mkdir()
    trusted = executable(tmp_path / "external", "clangd")
    aliases = tmp_path / "aliases"
    aliases.mkdir()
    alias = aliases / "clangd"
    alias.symlink_to(trusted)
    monkeypatch.setenv("PATH", str(trusted.parent))
    command = lsp_query.select_server("c", str(alias), root=tmp_path / "workspace")
    assert command == [str(alias), "--background-index=false", "--log=error"]
    assert command[0].executable == str(trusted)


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
    (tmp_path / "workspace").mkdir()
    binary = executable(tmp_path / "external", "clangd")
    calls = []
    resolve = Path.resolve
    def once(path, *args, **kwargs):
        calls.append(str(path))
        assert calls.count(str(path)) == 1
        return resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", once)
    monkeypatch.setattr(lsp_query.shutil, "which", lambda name: str(binary))
    command = lsp_query.select_server("c", str(binary), root=tmp_path / "workspace")
    assert command == [str(binary), "--background-index=false", "--log=error"]
    assert command[0].executable == str(binary)


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


@pytest.fixture
def navigation_connection(monkeypatch):
    """Exercise result classification without requiring any installed server."""
    state = {"response": [], "closed": False, "methods": []}

    class FakeConnection:
        def __init__(self, command, cwd, **kwargs):
            state["command"] = list(command)

        def request(self, method, params):
            state["methods"].append(method)
            if method == "initialize":
                return {"capabilities": {}}
            return state["response"]

        def notify(self, method, params):
            pass

        def diagnostics(self, uri, provider):
            return [], True

        def close(self):
            state["closed"] = True

    monkeypatch.setattr(lsp_query, "select_server", lambda *args: ["fixture-server"])
    monkeypatch.setattr(lsp_query, "Connection", FakeConnection)
    return state


def navigation_location(path):
    return {"uri": path.as_uri(), "range": {
        "start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1},
    }}


@pytest.mark.parametrize("action", ["definition", "references"])
@pytest.mark.parametrize("suffix", [".c", ".cpp"])
@pytest.mark.parametrize("empty", [False, True])
def test_c_family_navigation_retains_partial_results(tmp_path, capsys, navigation_connection, action, suffix, empty):
    source = tmp_path / ("example" + suffix)
    source.write_text("int value;\n")
    location = navigation_location(source)
    response = [] if empty else (location if action == "definition" else [location])
    navigation_connection["response"] = response

    assert lsp_query.query(arguments(tmp_path, action, source.name)) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "unverified"
    assert payload["complete"] is False
    assert payload["reason"] == "project_index_not_verified"
    assert "readiness was not verified" in payload["message"]
    assert payload["result"] == response
    assert payload["action"] == action
    assert payload["file"] == source.name
    assert navigation_connection["closed"] is True


@pytest.mark.parametrize("action", ["definition", "references"])
def test_background_index_flag_does_not_certify_readiness(tmp_path, capsys, navigation_connection, action):
    source = tmp_path / "example.c"
    source.write_text("int value;\n")
    navigation_connection["response"] = [navigation_location(source)]
    args = arguments(tmp_path, action)
    args.allow_custom_server = True
    args.server_arg = ["--background-index"]

    assert lsp_query.query(args) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["complete"] is False
    assert payload["reason"] == "project_index_not_verified"
    assert navigation_connection["command"] == ["fixture-server", "--background-index"]


def test_index_disable_switch_uses_partial_path_without_cache_write(
        tmp_path, monkeypatch, capsys, navigation_connection):
    source = tmp_path / "example.c"
    source.write_text("int value;\n")
    navigation_connection["response"] = [navigation_location(source)]
    monkeypatch.setenv("HIWAY_CODE_INTEL_INDEX", "0")
    assert lsp_query.query(arguments(tmp_path, "references")) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["complete"] is False
    assert payload["reason"] == "index_disabled"
    assert payload["result"] == [navigation_location(source)]
    assert navigation_connection["command"] == ["fixture-server"]
    assert not (tmp_path / ".cache").exists()


def test_preflight_deadline_exposes_no_progress_retry_signal(
        tmp_path, monkeypatch, capsys, navigation_connection):
    source = tmp_path / "example.c"
    source.write_text("int value;\n")
    navigation_connection["response"] = [navigation_location(source)]

    def deadline(*args, **kwargs):
        raise IndexUnavailable("index_deadline", "test preflight cutoff")

    monkeypatch.setattr(lsp_query, "select_server", lambda *args, **kwargs: ["/fake/clangd"])
    monkeypatch.setattr(lsp_query, "discover_compile_database", deadline)
    assert lsp_query.query(arguments(tmp_path, "references")) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["reason"] == "index_deadline"
    assert payload["index"]["cache_attempted"] is False
    assert payload["index"]["progress_increased"] is False
    assert "retry only when index.progress_increased is true" in payload["message"]


@pytest.mark.parametrize("suffix,action", [
    (".c", "symbols"), (".cpp", "symbols"),
    (".py", "definition"), (".py", "references"),
    (".c", "diagnostics"), (".cpp", "diagnostics"),
])
def test_non_target_query_contract_is_preserved(tmp_path, capsys, navigation_connection, suffix, action):
    source = tmp_path / ("example" + suffix)
    source.write_text("value = 1\n")
    navigation_connection["response"] = [] if action == "symbols" else [navigation_location(source)]
    assert lsp_query.query(arguments(tmp_path, action, source.name)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["complete"] is True
    assert "reason" not in payload
    assert "message" not in payload


@pytest.mark.parametrize("action", ["definition", "references"])
def test_malformed_navigation_is_not_valid_partial_data(tmp_path, monkeypatch, capsys, navigation_connection, action):
    (tmp_path / "example.c").write_text("int value;\n")
    navigation_connection["response"] = [{"uri": (tmp_path / "example.c").as_uri(), "range": {}}]
    monkeypatch.setattr(sys, "argv", ["lsp_query", action, "--root", str(tmp_path), "--file", "example.c"])
    assert lsp_query.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert payload["complete"] is False
    assert payload["reason"] != "project_index_not_verified"
    assert "result" not in payload


@pytest.mark.parametrize("language,name", [("c", "clangd"), ("cpp", "clangd"), ("python", "basedpyright-langserver"),
                                          ("typescriptreact", "typescript-language-server"),
                                          ("javascriptreact", "typescript-language-server"),
                                          ("rust", "rust-analyzer"), ("go", "gopls")])
def test_automatic_server_support_is_preserved(tmp_path, monkeypatch, language, name):
    (tmp_path / "workspace").mkdir()
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


def test_indexed_finish_shuts_down_once_and_reaps(tmp_path):
    server = """
import json, sys
while True:
    header = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            raise SystemExit(0)
        if line in (b'\\r\\n', b'\\n'):
            break
        key, value = line.decode().split(':', 1)
        header[key.lower()] = value.strip()
    message = json.loads(sys.stdin.buffer.read(int(header['content-length'])))
    if message.get('method') == 'exit':
        break
    if 'id' in message:
        raw = json.dumps({'jsonrpc': '2.0', 'id': message['id'], 'result': None}).encode()
        sys.stdout.buffer.write(b'Content-Length: ' + str(len(raw)).encode() + b'\\r\\n\\r\\n' + raw)
        sys.stdout.buffer.flush()
"""
    connection = lsp_transport.Connection([sys.executable, "-B", "-c", server], str(tmp_path),
                                          deadline=Deadline(8), monitor=True)
    connection.finish_indexed()
    assert connection.process.returncode == 0
    assert connection.guard is None


def progress_connection(seconds=1):
    connection = object.__new__(lsp_transport.Connection)
    connection.deadline = Deadline(seconds, reserve=0)
    connection.guard = None
    connection._progress_lock = threading.Lock()
    connection._progress_tokens = set()
    connection._progress_started = False
    connection._progress_ended = False
    connection.messages = queue.Queue()
    connection.send = lambda message, **kwargs: None
    return connection


def test_background_index_progress_requires_matching_created_token():
    connection = progress_connection()
    connection._create_progress({"id": 12, "params": {"token": "backgroundIndexProgress"}})
    for kind in ("begin", "report", "end"):
        value = {"kind": kind}
        if kind == "begin":
            value["title"] = "Indexing"
        connection._accept_progress({"params": {"token": "backgroundIndexProgress", "value": value}})
    assert connection.wait_for_background_index() == "progress_end"


def test_background_index_missing_end_hits_absolute_deadline():
    connection = progress_connection(.03)
    connection._create_progress({"id": 12, "params": {"token": "backgroundIndexProgress"}})
    connection._accept_progress({"params": {"token": "backgroundIndexProgress",
                                             "value": {"kind": "begin", "title": "Indexing"}}})
    with pytest.raises(IndexUnavailable, match="deadline"):
        connection.wait_for_background_index()


def test_background_index_rejects_uncreated_or_duplicate_progress():
    connection = progress_connection()
    with pytest.raises(lsp_transport.LspError, match="without token creation"):
        connection._accept_progress({"params": {"token": "backgroundIndexProgress",
                                                 "value": {"kind": "begin", "title": "Indexing"}}})
    connection._create_progress({"id": 12, "params": {"token": "backgroundIndexProgress"}})
    connection._accept_progress({"params": {"token": "backgroundIndexProgress",
                                             "value": {"kind": "begin", "title": "Indexing"}}})
    with pytest.raises(lsp_transport.LspError, match="duplicate background-index begin"):
        connection._accept_progress({"params": {"token": "backgroundIndexProgress",
                                                 "value": {"kind": "begin", "title": "Again"}}})


def test_unrelated_progress_token_never_certifies_background_index():
    connection = progress_connection(.03)
    connection._create_progress({"id": 4, "params": {"token": "otherProgress"}})
    connection._accept_progress({"params": {"token": "otherProgress",
                                             "value": {"kind": "begin", "title": "Other task"}}})
    connection._accept_progress({"params": {"token": "otherProgress", "value": {"kind": "end"}}})
    assert connection._progress_ended is False
    with pytest.raises(IndexUnavailable, match="deadline"):
        connection.wait_for_background_index()


def test_response_without_result_is_not_success(tmp_path):
    connection = lsp_transport.Connection([sys.executable, "-c", "import time; time.sleep(30)"], str(tmp_path))
    connection.send = lambda message, **kwargs: None
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
        elif action in ("definition", "references"):
            assert rc == 2
            assert result["status"] == "unverified"
            assert result["complete"] is False
            assert result["reason"] == "no_compile_db"
            assert result["result"]
        else:
            assert rc == 0
            assert result["status"] == "ok"
            assert result["result"]
    assert source.read_bytes() == original
    source.write_text("int broken(void) { return missing_symbol; }\n")
    assert lsp_query.query(arguments(tmp_path)) == 1
    assert any(row["severity"] == 1 for row in json.loads(capsys.readouterr().out)["result"])


@pytest.mark.skipif(not shutil.which("clangd"), reason="local cross-TU control unverified: optional clangd is not installed")
@pytest.mark.parametrize("action", ["definition", "references"])
@pytest.mark.parametrize("suffix", [".c", ".cpp"])
def test_real_clangd_cross_tu_navigation_is_partial(tmp_path, capsys, action, suffix):
    header = tmp_path / "helper.h"
    implementation = tmp_path / ("helper" + suffix)
    caller = tmp_path / ("main" + suffix)
    header.write_text("int fixture(int n);\n")
    implementation.write_text('#include "helper.h"\nint fixture(int n) { return n + 1; }\n')
    caller.write_text('#include "helper.h"\nint caller(void) { return fixture(2); }\n')
    cdb = tmp_path / "compile_commands.json"
    cdb.write_text(json.dumps([
        {"directory": str(tmp_path), "file": str(path),
         "arguments": ["clang++" if suffix == ".cpp" else "clang", "-c", str(path)]}
        for path in (implementation, caller)
    ]))
    before = {p.name: p.read_bytes() for p in (header, implementation, caller, cdb)}
    args = arguments(tmp_path, action, caller.name)
    args.line = 2
    args.column = caller.read_text().splitlines()[1].index("fixture") + 1
    assert lsp_query.query(args) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "unverified"
    assert payload["complete"] is False
    assert payload["reason"] == "compile_db_unsupported"
    # A nonempty location proves the server reached the requested symbol.
    # Which other TUs it happens to return is version-dependent, not certified.
    assert payload["result"]
    assert {p.name: p.read_bytes() for p in (header, implementation, caller, cdb)} == before
    assert not (tmp_path / ".cache").exists()


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
