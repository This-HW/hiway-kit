"""Deterministic subprocess CLI contracts, with synthetic AST/LSP fixtures.

No models or installed engines are needed. Real engine behavior is tested
separately by test_code_intel/test_lsp_query; these cases prove CLI handling,
not language parsing, natural-language selection, or skill-use equivalence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"


def cli(tmp_path, tool, *args, path=None):
    home = tmp_path / "isolated-home"
    home.mkdir(exist_ok=True)
    env = {**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex"),
           "PYTHONPATH": "", "PYTHONNOUSERSITE": "1"}
    if path is not None:
        env["PATH"] = str(path)
    process = subprocess.run([sys.executable, "-B", str(TOOLS / tool), *map(str, args)],
                             cwd=tmp_path, env=env, capture_output=True, text=True,
                             check=False, timeout=15)
    assert not process.stderr, process.stderr
    return process.returncode, json.loads(process.stdout)


def test_ast_metavariables_and_preview_preserve_source(tmp_path):
    """Synthetic engine checks literal Python/Go argv, not native parsing."""
    # The positive installed-engine fixture must be outside the queried root.
    binary_dir = tmp_path.parent / (tmp_path.name + "-external-bin")
    binary_dir.mkdir()
    engine = binary_dir / "ast-grep"
    engine.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "if '--version' in sys.argv: print('ast-grep 0.51.0'); sys.exit(0)\n"
        "lang = sys.argv[sys.argv.index('--lang') + 1]\n"
        "pattern = sys.argv[sys.argv.index('--pattern') + 1]\n"
        "assert pattern == ('print($A)' if lang == 'python' else 'println($A)')\n"
        "if '--stdin' in sys.argv: sys.exit(1)\n"
        "file = sys.argv[-1]\n"
        "assert 'name' in Path(file).read_text()\n"
        "match = {'file': file, 'text': 'name'}\n"
        "if '--rewrite' in sys.argv:\n"
        "    assert sys.argv[sys.argv.index('--rewrite') + 1] == 'log($A)'\n"
        "    match['replacement'] = 'log(name)'\n"
        "print(json.dumps([match]))\n", encoding="utf-8")
    engine.chmod(0o700)
    for language, name, source, pattern in (
        ("python", "example.py", "print(name)\n", "print($A)"),
        ("go", "example.go", "package main\nfunc f() { println(name) }\n", "println($A)"),
    ):
        file = tmp_path / name
        file.write_text(source, encoding="utf-8")
        for preview in (False, True):
            args = ["--root", tmp_path, "--lang", language, "--pattern", pattern]
            if preview:
                args += ["--rewrite", "log($A)"]
            rc, result = cli(tmp_path, "code_intel.py", *args, name, path=binary_dir)
            assert rc == 0 and result["status"] == "ok"
            assert result["mode"] == ("preview" if preview else "search")
            assert result["match_count"] == 1 and result["file_count"] == 1
            assert result["truncated"] is False
            if preview:
                assert result["matches"][0]["replacement"] == "log(name)"
            assert file.read_text(encoding="utf-8") == source


def rule_engine(tmp_path):
    """Synthetic native replies; validates dispatch/argv, not AST semantics."""
    binary_dir = tmp_path.parent / (tmp_path.name + "-rule-bin")
    binary_dir.mkdir()
    engine = binary_dir / "ast-grep"
    engine.write_text(
        f"#!{sys.executable} -B\n"
        "import json, sys\nfrom pathlib import Path\n"
        "if '--version' in sys.argv: print('ast-grep 0.51.0'); sys.exit(0)\n"
        "assert '-U' not in sys.argv and '--update-all' not in sys.argv\n"
        "if sys.argv[1] == 'test':\n"
        "    assert '--skip-snapshot-tests' in sys.argv and '--include-off' in sys.argv\n"
        "    config = Path(sys.argv[sys.argv.index('--config') + 1])\n"
        "    test = json.loads((config.parent / 'tests/case-0001.yml').read_text())\n"
        "    assert test['id'] == 'r' and test['invalid'] == ['f(x)']\n"
        "    passed = test['valid'] == ['g(x)']\n"
        "    print('Running 1 tests\\n')\n"
        "    print('PASS r  ..' if passed else 'FAIL r  N.')\n"
        "    print('test result: ok. 1 passed; 0 failed;' if passed else\n"
        "          'Error: test failed. 0 passed; 1 failed;', file=sys.stdout if passed else sys.stderr)\n"
        "    sys.exit(0 if passed else 1)\n"
        "assert sys.argv[1] == 'scan' and '--hint=r' in sys.argv and '--hint' not in sys.argv\n"
        "assert sys.argv[-2] == '--'\n"
        "rule = json.loads(next(x.split('=', 1)[1] for x in sys.argv if x.startswith('--inline-rules=')))\n"
        "assert rule['rule']['pattern'] == 'f($X)' and rule['fix'] == 'g($X)'\n"
        "source = Path(sys.argv[-1]) / 'sample.py'\n"
        "data = source.read_bytes()\n"
        "row = {'file': str(source), 'ruleId': 'r', 'text': 'f(x)', 'replacement': 'g(x)',\n"
        "       'range': {'byteOffset': {'start': 0, 'end': 4},\n"
        "                 'start': {'line': 0, 'column': 0}, 'end': {'line': 0, 'column': 4}},\n"
        "       'replacementOffsets': {'start': 0, 'end': 4}}\n"
        "assert data in (b'f(x)\\n', b'g(x)\\n')\n"
        "print(json.dumps([row] if data.startswith(b'f') else []))\n", encoding="utf-8")
    engine.chmod(0o700)
    return binary_dir


RULE = {"id": "r", "language": "Python", "rule": {"pattern": "f($X)"}, "fix": "g($X)"}


def test_json_rule_preview_subprocess_preserves_source(tmp_path):
    source = tmp_path / "sample.py"
    source.write_bytes(b"f(x)\n")
    rc, result = cli(tmp_path, "code_intel.py", "--root", tmp_path, "--rule-json", json.dumps(RULE),
                     source.name, path=rule_engine(tmp_path))
    assert rc == 0 and result["mode"] == "rule-preview" and result["converged"] is True
    assert result["iterations"] == 2 and result["changed_passes"] == 1
    assert result["files_copied"] == 1 and result["changed_file_count"] == 1
    assert "-f(x)\n+g(x)" in result["files"][0]["diff"]
    assert source.read_bytes() == b"f(x)\n"


def test_json_rule_test_subprocess_distinguishes_mismatch(tmp_path):
    binary_dir = rule_engine(tmp_path)
    for valid, expected_rc in (("g(x)", 0), ("f(x)", 1)):
        cases = [{"id": "r", "valid": [valid], "invalid": ["f(x)"]}]
        rc, result = cli(tmp_path, "code_intel.py", "--root", tmp_path, "--rule-json", json.dumps(RULE),
                         "--rule-tests-json", json.dumps(cases), path=binary_dir)
        assert rc == expected_rc and result["mode"] == "rule-test"
        assert result["cases_run"] == 2 and result["cases_failed"] == expected_rc


def test_json_rule_missing_test_is_unverified(tmp_path):
    second = {**RULE, "id": "untested"}
    cases = [{"id": "r", "valid": ["g(x)"], "invalid": ["f(x)"]}]
    empty = tmp_path / "empty-path"
    empty.mkdir()
    rc, result = cli(tmp_path, "code_intel.py", "--root", tmp_path, "--rule-json", json.dumps([RULE, second]),
                     "--rule-tests-json", json.dumps(cases), path=empty)
    assert rc == 2 and result["error"] == "untested_rule"


def test_json_rule_empty_engine_output_is_unverified(tmp_path):
    source = tmp_path / "sample.py"
    source.write_bytes(b"f(x)\n")
    binary_dir = rule_engine(tmp_path)
    engine = binary_dir / "ast-grep"
    engine.write_text(engine.read_text().replace(
        "print(json.dumps([row] if data.startswith(b'f') else []))", "pass"), encoding="utf-8")
    rc, result = cli(tmp_path, "code_intel.py", "--root", tmp_path, "--rule-json", json.dumps(RULE),
                     source.name, path=binary_dir)
    assert rc == 2 and result["error"] == "schema_mismatch"
    assert "files" not in result and source.read_bytes() == b"f(x)\n"


def test_json_rule_non_utf8_argument_stays_json(tmp_path):
    rc, result = cli(tmp_path, "code_intel.py", "--root", tmp_path, "--rule-json", json.dumps(RULE),
                     "bad-\udcff.py")
    assert rc == 2 and result["error"] == "unsupported_file_name"
    assert "\\udcff" in result["reason"]


def diagnostics(tmp_path, errors):
    source = tmp_path / "example.c"
    source.write_text("int fixture;\n", encoding="utf-8")
    server = tmp_path / "server.py"
    server.write_text(r'''
import json, sys
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
    if message.get("method") == "initialize":
        send(dict(id=message["id"], result={"capabilities": {}}))
    if message.get("method") == "textDocument/didOpen":
        send(dict(method="textDocument/publishDiagnostics", params={
            "uri": message["params"]["textDocument"]["uri"], "version": 1,
            "diagnostics": json.loads(sys.argv[1])}))
''', encoding="utf-8")
    original = source.read_bytes()
    result = cli(tmp_path, "lsp_query.py", "diagnostics", "--root", tmp_path,
                 "--file", source.name, "--allow-custom-server", "--server", sys.executable,
                 "--server-arg=-I", "--server-arg=-B", "--server-arg=" + str(server),
                 "--server-arg=" + json.dumps(errors))
    assert source.read_bytes() == original
    return result


def test_provisional_empty_diagnostics_are_unverified(tmp_path):
    rc, result = diagnostics(tmp_path, [])
    assert rc == 2 and result["status"] == "unverified"
    assert result["complete"] is False and result["result"] == []


def test_provisional_error_diagnostics_keep_error_exit(tmp_path):
    error = {"range": {"start": {"line": 0, "character": 0},
                       "end": {"line": 0, "character": 1}},
             "message": "synthetic error", "severity": 1}
    rc, result = diagnostics(tmp_path, [error])
    assert rc == 1 and result["status"] == "unverified"
    assert result["complete"] is False and result["result"] == [error]


def test_missing_executables_are_unavailable(tmp_path):
    empty = tmp_path / "empty-path"
    empty.mkdir()
    source = tmp_path / "example.c"
    source.write_text("int x;\n", encoding="utf-8")
    for tool, args in (
        ("code_intel.py", ["--lang", "c", "--pattern", "f($A)", source.name]),
        ("lsp_query.py", ["diagnostics", "--file", source.name]),
    ):
        rc, result = cli(tmp_path, tool, "--root", tmp_path, *args, path=empty)
        assert rc == 3 and result["status"] == "unavailable"


def write_log(tmp_path, count=1):
    logs = tmp_path / "logs"
    logs.mkdir()
    record = {"type": "user", "sessionId": "fixture-session", "message": {"content": "needle in fixture"}}
    (logs / "fixture.jsonl").write_text((json.dumps(record) + "\n") * count, encoding="utf-8")
    return logs


def test_history_explicit_root_finds_source_lines(tmp_path):
    logs = write_log(tmp_path)
    rc, result = cli(tmp_path, "session_history.py", "--root", logs, "--query", "NEEDLE")
    assert rc == 0 and result["status"] == "ok"
    assert result["matched_sessions"] == 1 and result["scanned_files"] == 1
    assert result["scan_truncated"] is False
    assert "Untrusted" in result["notice"]
    record = result["results"][0]
    assert record["id"] == "fixture-session"
    assert Path(record["path"]) == (logs / "fixture.jsonl").resolve()
    assert record["matches"] == [{"line": 1, "preview": "needle in fixture"}]


def test_history_absent_query_is_complete_empty(tmp_path):
    logs = write_log(tmp_path)
    rc, result = cli(tmp_path, "session_history.py", "--root", logs, "--query", "absent")
    assert rc == 0 and result["matched_sessions"] == 0 and result["results"] == []
    assert result["scan_truncated"] is False and result["scanned_files"] == 1
    assert result["limited_files"] == 0 and result["malformed_records"] == 0


def test_history_configuration_scope_is_refused(tmp_path):
    home = tmp_path / "isolated-home"
    home.mkdir()
    for root in (home, home / ".codex"):
        root.mkdir(exist_ok=True)
        rc, result = cli(tmp_path, "session_history.py", "--root", root, "--query", "needle")
        assert rc == 2 and result["status"] == "error"
        assert "configuration root" in result["reason"]


def test_history_truncated_search_is_not_complete_empty(tmp_path):
    logs = write_log(tmp_path, count=6)
    rc, result = cli(tmp_path, "session_history.py", "--root", logs, "--query", "needle")
    assert rc == 0 and result["matched_sessions"] == 1
    assert result["scan_truncated"] is True and result["limited_files"] == 1
    assert "matches_limit" in result["scan_truncation_reasons"]
    assert len(result["results"][0]["matches"]) == 5
