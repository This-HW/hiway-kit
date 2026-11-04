from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
import lsp_query
import lsp_transport
import lsp_validation

RANGE = {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}}
ERROR = {"range": RANGE, "message": "fixture error", "severity": 1}
LOCATION = {"uri": "file:///fixture.c", "range": RANGE}
SYMBOL = {"name": "fixture", "kind": 12, "range": RANGE, "selectionRange": RANGE}

WIRE_SERVER = r'''
import json, sys, time
case = json.loads(sys.argv[1])
def send(message):
    raw = json.dumps(dict(jsonrpc="2.0", **message)).encode()
    sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(raw) + raw)
    sys.stdout.buffer.flush()
while True:
    length = None
    while True:
        line = sys.stdin.buffer.readline()
        if not line: sys.exit(0)
        if line == b"\r\n": break
        if line.lower().startswith(b"content-length:"): length = int(line.split(b":")[1])
    message = json.loads(sys.stdin.buffer.read(length))
    method = message.get("method")
    if method == "initialize":
        if case.get("check_env"):
            import os
            assert 'INTEL_TEST_API_TOKEN' not in os.environ
            assert 'NODE_OPTIONS' not in os.environ
            assert os.environ['GOTOOLCHAIN'] == 'local'
        caps = case.get("capabilities", {})
        if case.get("pull"):
            caps["diagnosticProvider"] = {"interFileDependencies": False, "workspaceDiagnostics": False}
        if case.get("check_capabilities"):
            client = message["params"]["capabilities"]["textDocument"]
            assert client["diagnostic"]["relatedDocumentSupport"] is False
            assert client["documentSymbol"]["hierarchicalDocumentSymbolSupport"] is True
            assert client["definition"]["linkSupport"] is True
        send(dict(id=case.get("initialize_id", message["id"]), result={"capabilities": caps}))
    elif method == "textDocument/didOpen":
        uri = message["params"]["textDocument"]["uri"]
        for index, batch in enumerate(case.get("push", [[]])):
            if index: time.sleep(case.get("delay", 0))
            send(dict(method="textDocument/publishDiagnostics", params={"uri": uri, "version": case.get("version", 1), "diagnostics": batch}))
    elif method and "id" in message:
        for _ in range(case.get("flood_count", 0)):
            if case.get("flood_diagnostics"):
                diagnostic = {"range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}}, "message": "x"*case["flood_size"]}
                send(dict(method="textDocument/publishDiagnostics", params={"uri": uri, "diagnostics": [diagnostic]}))
            else:
                send(dict(method="window/logMessage", params={"message": "x"*case["flood_size"]}))
        if "expected_position" in case:
            assert message["params"]["position"] == case["expected_position"]
        if "wire_response" in case:
            response = dict(id=message["id"], **case["wire_response"])
        elif method == "textDocument/diagnostic":
            response = dict(id=message["id"], result=case.get("report", {"kind": "full", "items": []}))
            if case.get("report_message_size"):
                response["result"]["items"][0]["message"] = "x"*case["report_message_size"]
        else:
            response = dict(id=message["id"], result=case.get("result", []))
        send(response)
'''


@pytest.fixture
def wire(tmp_path, monkeypatch, capsys):
    source = tmp_path / "example.c"
    source.write_text("int fixture;\n")
    server = tmp_path / "server.py"
    server.write_text(WIRE_SERVER)

    def run(case, action="diagnostics", text=None, line=1, column=1):
        if text is not None:
            source.write_text(text)
        monkeypatch.setattr(sys, "argv", ["lsp_query", action, "--root", str(tmp_path),
                                         "--file", source.name, "--line", str(line), "--column", str(column),
                                         "--server", sys.executable, "--allow-custom-server",
                                         "--server-arg=-B", "--server-arg=" + str(server),
                                         "--server-arg=" + json.dumps(case)])
        rc = lsp_query.main()
        return rc, json.loads(capsys.readouterr().out)

    return run


def test_initial_empty_then_delayed_error_is_provisional(wire):
    rc, result = wire({"push": [[], [ERROR]], "delay": .2})
    assert rc == 2
    assert result["status"] == "unverified"
    assert result["complete"] is False


def test_push_error_is_preserved_and_never_complete(wire):
    rc, result = wire({"push": [[ERROR]]})
    assert rc == 1
    assert result["status"] == "unverified"
    assert result["complete"] is False
    assert result["result"] == [ERROR]


@pytest.mark.parametrize("items,expected", [([], 0), ([ERROR], 1)])
def test_pull_full_is_complete(wire, items, expected):
    rc, result = wire({"pull": True, "report": {"kind": "full", "resultId": "r1", "items": items},
                       "check_capabilities": True})
    assert rc == expected
    assert result["status"] == "ok"
    assert result["complete"] is True
    assert result["result"] == items


@pytest.mark.parametrize("case,action", [
    ({"initialize_id": True}, "symbols"),
    ({"result": [42]}, "symbols"),
    ({"push": [[{"severity": "1"}]]}, "diagnostics"),
    ({"push": [[{"message": "bad"}]]}, "diagnostics"),
    ({"push": [[dict(ERROR, severity="1")]]}, "diagnostics"),
    ({"push": [[dict(ERROR, severity=True)]]}, "diagnostics"),
    ({"push": [[dict(ERROR, range={})]]}, "diagnostics"),
    ({"version": True}, "diagnostics"),
    ({"wire_response": {"result": [], "error": {"code": -1, "message": "bad"}}}, "symbols"),
    ({"wire_response": {"method": "bad", "result": []}}, "symbols"),
    ({"wire_response": {"error": {"code": True, "message": "bad"}}}, "symbols"),
    ({"wire_response": {"error": {"code": -1}}}, "symbols"),
    ({"wire_response": {"error": {"code": -32601, "message": "unsupported"}}}, "symbols"),
    ({"result": [{"uri": "file:///bad"}]}, "references"),
    ({"result": {"uri": "file:///bad"}}, "definition"),
    ({"result": [{"targetUri": "file:///bad", "targetRange": RANGE}]}, "definition"),
    ({"result": [dict(SYMBOL, kind=True)]}, "symbols"),
    ({"result": [dict(SYMBOL, children=[42])]}, "symbols"),
    ({"pull": True, "report": {"kind": "unchanged", "resultId": "r1"}}, "diagnostics"),
    ({"pull": True, "report": {"kind": "full", "items": [], "resultId": 1}}, "diagnostics"),
    ({"pull": True, "report": {"kind": "full", "items": [42]}}, "diagnostics"),
    ({"pull": True, "report": {"kind": "unknown", "items": []}}, "diagnostics"),
])
def test_invalid_wire_responses_are_unverified(wire, case, action):
    rc, result = wire(case, action)
    assert rc == 2
    assert result["status"] == "error"
    assert result["complete"] is False


@pytest.mark.parametrize("action,result", [
    ("symbols", [SYMBOL]),
    ("symbols", [{"name": "fixture", "kind": 12, "location": LOCATION, "containerName": "scope"}]),
    ("definition", LOCATION),
    ("definition", [LOCATION]),
    ("definition", [{"targetUri": "file:///fixture.c", "targetRange": RANGE, "targetSelectionRange": RANGE}]),
    ("references", [LOCATION]),
    ("definition", None),
    ("symbols", []),
])
def test_valid_wire_navigation_remains_successful(wire, action, result):
    rc, response = wire({"result": result}, action)
    assert rc == 0
    assert response["result"] == result


def test_source_ancestor_swap_does_not_read_outside(tmp_path, monkeypatch):
    import code_intel

    root = tmp_path / "workspace"
    inside = root / "nested"
    inside.mkdir(parents=True)
    (inside / "example.c").write_text("int inside;\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "example.c").write_text("int outside;\n")
    real_resolve = code_intel.contained_path

    def swap(root, value):
        resolved = real_resolve(root, value)
        inside.rename(root / "old")
        inside.symlink_to(outside, target_is_directory=True)
        return resolved

    # Covers the old query import as well as the new source helper.
    monkeypatch.setattr(code_intel, "contained_path", swap)
    monkeypatch.setattr(lsp_query, "contained_path", swap, raising=False)
    observed = []
    monkeypatch.setattr(lsp_query, "select_server", lambda *a: observed.append(True))
    args = type("Args", (), {"root": str(root), "file": "nested/example.c", "server": None})()
    with pytest.raises((OSError, ValueError)):
        lsp_query.query(args)
    assert not observed


def test_source_growth_is_bounded(tmp_path, monkeypatch):
    import lsp_source

    source = tmp_path / "example.c"
    source.write_text("small")
    original = os.read
    counts = []

    def growing(fd, size):
        counts.append(size)
        source.write_bytes(b"x" * 1000)
        return original(fd, size)

    monkeypatch.setattr(lsp_source.os, "read", growing)
    with pytest.raises(ValueError, match="larger"):
        lsp_source.read_source(str(tmp_path), "example.c", 16)
    assert sum(counts) <= 17


@pytest.mark.parametrize("kind", ["fifo", "directory", "symlink"])
def test_source_special_files_do_not_block(tmp_path, kind):
    import lsp_source

    source = tmp_path / "example.c"
    if kind == "fifo":
        os.mkfifo(source)
    elif kind == "directory":
        source.mkdir()
    else:
        outside = tmp_path.parent / (tmp_path.name + "-outside.c")
        outside.write_text("outside")
        source.symlink_to(outside)
    started = time.monotonic()
    with pytest.raises((OSError, ValueError)):
        lsp_source.read_source(str(tmp_path), source.name, 16)
    assert time.monotonic() - started < 1


def test_utf16_position_contract(wire):
    rc, response = wire({"expected_position": {"line": 0, "character": 3}, "result": LOCATION},
                        "definition", text="😀xy\n", column=3)
    assert rc == 0
    assert response["result"] == LOCATION


@pytest.mark.parametrize("text,line,column,position", [
    ("a\u0085\u2028\u2029😀z", 1, 6, {"line": 0, "character": 6}),
    ("a\r\nb\rc\n", 4, 1, {"line": 3, "character": 0}),
    ("😀\r\nx\u2028y", 2, 4, {"line": 1, "character": 3}),
])
def test_only_lsp_line_endings_split_source(wire, text, line, column, position):
    rc, response = wire({"expected_position": position, "result": LOCATION}, "definition", text=text, line=line, column=column)
    assert rc == 0
    assert response["result"] == LOCATION


@pytest.mark.parametrize("diagnostics", [False, True])
def test_cumulative_receive_budget_is_unverified(wire, diagnostics):
    rc, result = wire({"push": [], "flood_count": 17, "flood_size": 1024*1024,
                       "flood_diagnostics": diagnostics}, "symbols")
    assert rc == 2
    assert result["status"] == "unverified"
    assert result["complete"] is False
    assert "byte budget" in result["reason"]


def test_notification_count_limit_remains_enforced(wire):
    rc, result = wire({"push": [], "flood_count": 129, "flood_size": 0}, "symbols")
    assert rc == 2
    assert "notification budget" in result["reason"]


def test_large_valid_diagnostics_below_budget_remain_accepted(wire):
    rc, result = wire({"pull": True, "report": {"kind": "full", "items": [ERROR]}, "report_message_size": 1024*1024}, "diagnostics")
    assert rc == 1
    assert result["complete"] is True
    assert len(result["result"][0]["message"]) == 1024*1024


@pytest.mark.parametrize("diagnostics", [False, True])
def test_large_repeated_notifications_below_budget_remain_accepted(wire, diagnostics):
    rc, result = wire({"push": [], "flood_count": 14, "flood_size": 1024*1024,
                       "flood_diagnostics": diagnostics}, "symbols")
    assert rc == 0
    assert result["complete"] is True


def test_lsp_child_environment_is_filtered(wire, monkeypatch):
    monkeypatch.setenv("INTEL_TEST_API_TOKEN", "fixture-value")
    monkeypatch.setenv("NODE_OPTIONS", "fixture-value")
    monkeypatch.setenv("GOTOOLCHAIN", "auto")
    rc, result = wire({"check_env": True, "result": []}, "symbols")
    assert rc == 0
    assert "untrusted" in result["notice"].lower()


@pytest.mark.parametrize("case,expected", [({"result": []}, 0), ({"result": [42]}, 2)])
def test_lsp_notice_on_success_and_error(wire, case, expected):
    rc, result = wire(case, "symbols")
    assert rc == expected
    assert "untrusted" in result["notice"].lower()
    assert "instructions" in result["notice"].lower()


@pytest.mark.parametrize("identifier", [True, False, 1.0, [], {}, 2147483648])
def test_strict_jsonrpc_ids(identifier):
    with pytest.raises(lsp_validation.LspError, match="ID"):
        lsp_validation.validate_message({"jsonrpc": "2.0", "id": identifier, "result": []})


@pytest.mark.parametrize("message", [
    {"id": "a", "result": None},
    {"id": "a", "error": {"code": -32601, "message": "unsupported"}},
    {"id": None, "error": {"code": -32700, "message": "parse"}},
    {"id": 7, "method": "workspace/applyEdit", "params": {}},
    {"method": "window/logMessage", "params": {}},
])
def test_valid_jsonrpc_shapes(message):
    lsp_validation.validate_message(dict(jsonrpc="2.0", **message))


def test_unchanged_report_requires_prior_result_and_retains_it():
    report = {"kind": "unchanged", "resultId": "new"}
    assert lsp_validation.validate_pull_report(report, "old", [ERROR]) == ([ERROR], "new")
    with pytest.raises(lsp_validation.LspError):
        lsp_validation.validate_pull_report(report)


def test_push_error_followed_by_clear_is_retained(tmp_path):
    connection = lsp_transport.Connection([sys.executable, "-B", "-c", "import time; time.sleep(30)"], str(tmp_path))
    for batch in ([ERROR], []):
        connection.messages.put({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                                 "params": {"uri": "file:///fixture.c", "version": 1, "diagnostics": batch}})
    try:
        assert connection.diagnostics("file:///fixture.c") == ([ERROR], False)
    finally:
        connection.close()


def test_unknown_client_request_gets_method_not_found(tmp_path):
    connection = lsp_transport.Connection([sys.executable, "-B", "-c", "import time; time.sleep(30)"], str(tmp_path))
    sent = []
    connection.send = sent.append
    connection.messages.put({"jsonrpc": "2.0", "id": "server-request", "method": "unknown", "params": {}})
    try:
        with pytest.raises(lsp_transport.LspError, match="Unsupported"):
            connection.receive(time.monotonic() + 1)
        assert sent == [{"jsonrpc": "2.0", "id": "server-request",
                         "error": {"code": -32601, "message": "Unsupported client method"}}]
    finally:
        connection.close()


@pytest.mark.parametrize("raw", [
    '{"jsonrpc":"2.0","id":1,"id":true,"result":[]}',
    '{"jsonrpc":"2.0","id":1,"result":NaN}',
    '{"jsonrpc":"2.0","id":1,"result":Infinity}',
])
def test_non_json_or_duplicate_keys_are_rejected(tmp_path, raw):
    script = "import sys; raw=sys.argv[1].encode(); sys.stdout.buffer.write(b'Content-Length: %d\\r\\n\\r\\n'%len(raw)+raw); sys.stdout.buffer.flush()"
    connection = lsp_transport.Connection([sys.executable, "-B", "-c", script, raw], str(tmp_path))
    try:
        with pytest.raises(lsp_transport.LspError):
            connection.request("initialize", {})
    finally:
        connection.close()


@pytest.mark.parametrize("swap_kind", ["file", "root", "above-root"])
def test_source_symlink_swap_at_each_level(tmp_path, monkeypatch, swap_kind):
    import code_intel
    import lsp_source

    parent = tmp_path / "parent"
    root = parent / "root"
    root.mkdir(parents=True)
    source = root / "example.c"
    source.write_text("inside")
    outside = tmp_path / "outside"
    (outside / "root").mkdir(parents=True)
    (outside / "example.c").write_text("outside")
    (outside / "root" / "example.c").write_text("outside")
    original = code_intel.contained_path

    def swap(resolved_root, value):
        path = original(resolved_root, value)
        target = {"file": source, "root": root, "above-root": parent}[swap_kind]
        target.rename(target.with_name("old"))
        target.symlink_to(outside / "example.c" if swap_kind == "file" else outside)
        return path

    monkeypatch.setattr(code_intel, "contained_path", swap)
    with pytest.raises(OSError):
        lsp_source.read_source(str(root), "example.c", 16)


def test_held_directory_fd_does_not_follow_replacement(tmp_path, monkeypatch):
    import lsp_source

    root = tmp_path / "root"
    root.mkdir()
    nested = root / "nested"
    nested.mkdir()
    (nested / "example.c").write_text("inside")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "example.c").write_text("outside")
    original = os.open

    def swapping_open(path, flags, *args, **kwargs):
        fd = original(path, flags, *args, **kwargs)
        if path == "nested":
            nested.rename(root / "old")
            nested.symlink_to(outside, target_is_directory=True)
        return fd

    monkeypatch.setattr(os, "supports_dir_fd", {*os.supports_dir_fd, swapping_open})
    monkeypatch.setattr(lsp_source.os, "open", swapping_open)
    assert lsp_source.read_source(str(root), "nested/example.c", 16)[2] == "inside"


def test_missing_safe_source_primitive_is_explicitly_unavailable(tmp_path, monkeypatch, capsys):
    (tmp_path / "example.c").write_text("inside")
    monkeypatch.delattr(os, "O_NOFOLLOW")
    monkeypatch.setattr(sys, "argv", ["lsp_query", "diagnostics", "--root", str(tmp_path), "--file", "example.c"])
    assert lsp_query.main() == 3
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "unavailable"
    assert result["complete"] is False


def test_source_symlink_loop_is_an_unverified_error(tmp_path, monkeypatch, capsys):
    (tmp_path / "example.c").symlink_to("example.c")
    monkeypatch.setattr(sys, "argv", ["lsp_query", "diagnostics", "--root", str(tmp_path), "--file", "example.c"])
    assert lsp_query.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert result["complete"] is False


def test_blocked_writer_and_descendant_are_cleaned_up(tmp_path, monkeypatch):
    monkeypatch.setattr(lsp_transport, "REQUEST_TIMEOUT", .2)
    pid_file = tmp_path / "child.pid"
    script = "import subprocess,sys,time; from pathlib import Path; child=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(30)']); Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(30)"
    connection = lsp_transport.Connection([sys.executable, "-B", "-c", script, str(pid_file)], str(tmp_path))
    try:
        deadline = time.monotonic() + 3
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        assert pid_file.exists()
        with pytest.raises(lsp_transport.LspError, match="input timed out"):
            connection.send({"payload": "x" * lsp_transport.MAX_MESSAGE_BYTES})
    finally:
        connection.close()
    assert connection.process.returncode is not None
    assert not connection.reader.is_alive()
    child = int(pid_file.read_text())
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        time.sleep(.02)
    else:
        pytest.fail("language-server descendant survived close")


@pytest.mark.skipif(not shutil.which("ruff"), reason="optional installed Ruff server")
def test_real_ruff_pull_diagnostics_and_unsupported_navigation(tmp_path, monkeypatch, capsys):
    source = tmp_path / "example.py"
    for text, expected in [("x = 1\n", 0), ("def broken(:\n", 1)]:
        source.write_text(text)
        monkeypatch.setattr(sys, "argv", ["lsp_query", "diagnostics", "--root", str(tmp_path),
                                         "--file", source.name, "--server", "ruff", "--server-arg=server"])
        rc = lsp_query.main()
        result = json.loads(capsys.readouterr().out)
        assert rc == expected
        assert result["complete"] is True
        assert result["status"] == "ok"
        assert bool(result["result"]) is bool(expected)
    monkeypatch.setattr(sys, "argv", ["lsp_query", "symbols", "--root", str(tmp_path),
                                     "--file", source.name, "--server", "ruff", "--server-arg=server"])
    assert lsp_query.main() == 2
    assert json.loads(capsys.readouterr().out)["complete"] is False
