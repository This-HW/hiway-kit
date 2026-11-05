"""JSON AST rule preview and rule-test contracts (code_intel --rule-json).

Synthetic engines prove CLI, path, schema and budget handling. Tests named
``real_engine`` need the installed ast-grep (>= 0.51.0); with
HIWAY_REQUIRE_AST_GREP=1 a missing engine fails instead of skipping. Native
``scan -U`` runs only on test copies, as a differential oracle: matching native
bytes is not semantic correctness, which the fixture check scripts judge.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "plugins/common/tools"
FIXTURES = ROOT / "tests/fixtures/ast-rules"
sys.path.insert(0, str(TOOLS))
import code_intel
import code_intel_rules

NO_IGNORE = [flag for kind in code_intel_rules.NO_IGNORE for flag in ("--no-ignore", kind)]
REQUIRE_ENGINE = os.environ.get("HIWAY_REQUIRE_AST_GREP") == "1"


# ------------------------------------------------------------------ helpers
def run_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["code_intel.py", *map(str, args)])
    rc = code_intel.main()
    out = capsys.readouterr().out
    result = json.loads(out)
    assert next(iter(result)) == "notice" and "untrusted" in result["notice"].lower()
    assert result["environment"] == "filtered"
    return rc, result


def tree_digest(root: Path) -> dict:
    return {str(path.relative_to(root)): (hashlib.sha256(path.read_bytes()).hexdigest()
                                          if path.is_file() and not path.is_symlink() else path.is_symlink())
            for path in sorted(root.rglob("*"))}


def rules_json(*rules) -> str:
    return json.dumps(list(rules))


def simple_rule(rule_id="r", pattern="f($X)", fix="h($X)", language="python", **extra):
    rule = {"id": rule_id, "language": language, "rule": {"pattern": pattern}}
    if fix is not None:
        rule["fix"] = fix
    rule.update(extra)
    return rule


def external_dir(tmp_path: Path) -> Path:
    path = tmp_path.parent / (tmp_path.name + "-external")
    path.mkdir(exist_ok=True)
    return path


def install_engine(tmp_path, monkeypatch, program: str, version: str = "0.51.0") -> Path:
    """Synthetic engine outside the workspace; PATH lookup is pinned to it."""
    engine = external_dir(tmp_path) / "ast-grep"
    engine.write_text(f"#!{sys.executable} -B\n"
                      "import json, os, sys, time\nfrom pathlib import Path\n"
                      f"if '--version' in sys.argv: print('ast-grep {version}'); sys.exit(0)\n"
                      + program, encoding="utf-8")
    engine.chmod(0o700)
    monkeypatch.setattr(code_intel.shutil, "which", lambda name: str(engine) if name == "ast-grep" else None)
    return engine


SCANNER = r"""
SPEC = json.loads({spec!r})
tree = Path(sys.argv[-1])
rows = []
for path in sorted(p for p in tree.rglob('*') if p.is_file()):
    data = path.read_bytes()
    for item in SPEC['rules']:
        needle = item['find'].encode()
        start = data.find(needle)
        while start != -1:
            end = start + len(needle)
            def pos(i):
                return {{'line': data[:i].count(b'\n'), 'column': i - (data.rfind(b'\n', 0, i) + 1)}}
            row = {{'text': needle.decode(), 'file': str(path), 'ruleId': item['ruleId'],
                   'range': {{'byteOffset': {{'start': start, 'end': end}}, 'start': pos(start), 'end': pos(end)}}}}
            if item.get('replace') is not None:
                row['replacement'] = item['replace']
                row['replacementOffsets'] = {{'start': start, 'end': end}}
            rows.append(row)
            start = data.find(needle, start + 1)
{mutate}
print(json.dumps(rows))
"""


def scanner(rules, mutate: str = "") -> str:
    return SCANNER.format(spec=json.dumps({"rules": rules}), mutate=mutate)


def workspace(tmp_path, files: dict) -> Path:
    root = tmp_path / "work"
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
    root.mkdir(exist_ok=True)
    return root


def preview(monkeypatch, capsys, root, rules, *paths, extra=()):
    return run_cli(monkeypatch, capsys, "--root", root, "--rule-json", rules, *extra, *(paths or (".",)))


def engine_version_ok() -> str | None:
    found = shutil.which("ast-grep")
    if not found:
        return None
    try:
        engine = code_intel.find_ast_grep(root=Path(tempfile.gettempdir()).resolve())
    except ValueError:
        return None
    if engine is None or code_intel_rules._version_tuple(engine[1]) < code_intel_rules.MINIMUM_ENGINE:
        return None
    return engine[0]


@pytest.fixture
def real_engine():
    binary = engine_version_ok()
    if binary is None:
        message = "installed ast-grep >= 0.51.0 is required for real_engine tests"
        if REQUIRE_ENGINE:
            pytest.fail(message + " (HIWAY_REQUIRE_AST_GREP=1)")
        pytest.skip(message)
    return binary


def run_bounded(command, cwd, timeout=60):
    """Test-side runner: DEVNULL stdin, hard timeout, process-group cleanup."""
    process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    finally:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    return process.returncode, stdout, stderr


def hint_flags(rules) -> list:
    return [f"--hint={rule['id']}" for rule in rules]


def native_fixed_point(binary, rules, tree: Path, scratch: Path, limit=12):
    """TEST ONLY: native scan -U on a disposable copy until bytes stop changing."""
    config = scratch / "neutral" / "sgconfig.yml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("ruleDirs: []\n", encoding="utf-8")
    _, inline = code_intel_rules.parse_rules(json.dumps(rules))
    passes = []
    for _ in range(limit):
        before = tree_digest(tree)
        rc, _, stderr = run_bounded([binary, "scan", "--config", str(config), f"--inline-rules={inline}", "-U",
                                     *hint_flags(rules), *NO_IGNORE, "--", str(tree)], cwd=config.parent)
        assert rc == 0, stderr
        after = tree_digest(tree)
        passes.append(sorted(rel for rel in after if after[rel] != before.get(rel)))
        if after == before:
            return passes
    raise AssertionError("native -U did not reach a fixed point")


def assert_preview_matches_native(result, original: Path, native: Path, prefix: str = ""):
    """Final bytes of every native-rewritten file equal the preview's result hashes."""
    changed = {entry["path"][len(prefix):]: entry["result_sha256"] for entry in result["files"]}
    sources = {rel[len(prefix):]: sha for rel, sha in result["source_sha256"].items() if rel.startswith(prefix)}
    native_files = {rel: sha for rel, sha in tree_digest(native).items() if isinstance(sha, str)}
    assert set(native_files) == set(sources)
    for rel, sha in native_files.items():
        assert sha == changed.get(rel, sources[rel]), rel
    original_files = tree_digest(original)
    assert set(changed) == {rel for rel, sha in native_files.items() if sha != original_files[rel]}


def copy_fixture(name: str, tmp_path: Path, label: str) -> Path:
    target = tmp_path / label
    shutil.copytree(FIXTURES / name, target)
    return target


# ================================================================ boundaries
@pytest.mark.parametrize(("text", "code"), [
    ('{"id":"a","id":"b","language":"python","rule":{"pattern":"f()"}}', "invalid_json"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"metadata":{"x":NaN}}', "invalid_json"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"metadata":{"x":-Infinity}}', "invalid_json"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"metadata":{"x":1e999}}', "invalid_json"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"metadata":{"x":99999999999999999999}}', "invalid_json"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"message":"\\ud800"}', "invalid_json"),
    ("[]", "invalid_input"), ("[1]", "invalid_input"), ('"x"', "invalid_input"), ("not json", "invalid_json"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"utils":{}}', "unsupported_key"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"transform":{}}', "unsupported_key"),
    ('{"id":"","language":"python","rule":{"pattern":"f()"}}', "invalid_rule_id"),
    ('{"id":123,"language":"python","rule":{"pattern":"f()"}}', "invalid_rule_id"),
    ('{"id":"a b","language":"python","rule":{"pattern":"f()"}}', "invalid_rule_id"),
    ('{"id":"-a","language":"python","rule":{"pattern":"f()"}}', "invalid_rule_id"),
    ('{"id":"a\\n","language":"python","rule":{"pattern":"f()"}}', "invalid_rule_id"),
    ('{"language":"python","rule":{"pattern":"f()"}}', "invalid_rule_id"),
    ('{"id":"no-suppress-all","language":"python","rule":{"pattern":"f()"}}', "reserved_rule_id"),
    ('{"id":"unused-suppression","language":"python","rule":{"pattern":"f()"}}', "reserved_rule_id"),
    ('[{"id":"a","language":"python","rule":{"pattern":"f()"}},{"id":"a","language":"python","rule":{"pattern":"g()"}}]',
     "duplicate_rule_id"),
    ('{"id":"a","rule":{"pattern":"f()"}}', "invalid_rule"),
    ('{"id":"a","language":"python","rule":"f()"}', "invalid_rule"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"fix":null}', "invalid_rule"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"fix":{"template":1}}', "invalid_rule"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"fix":{"template":"","expandEnd":{"regex":","}}}',
     "unsupported_fix_expansion"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"fix":{"template":"","expandStart":{"regex":","}}}',
     "unsupported_fix_expansion"),
    ('{"id":"a","language":"python","rule":{"pattern":"f()"},"fix":{"template":"","extra":1}}', "unsupported_key"),
])
def test_boundaries_strict_rule_json_rejected_before_engine(tmp_path, monkeypatch, capsys, text, code):
    marker = tmp_path / "engine-ran"
    install_engine(tmp_path, monkeypatch, f"Path({str(marker)!r}).touch()\nprint('[]')\n")
    root = workspace(tmp_path, {"a.py": "f()\n"})
    rc, result = preview(monkeypatch, capsys, root, text)
    assert rc == 2 and result["status"] == "error" and result["error"] == code, result
    assert result["mode"] == "rule-preview"
    assert not marker.exists()


def test_boundaries_canonical_inline_documents_and_argv(tmp_path, monkeypatch, capsys):
    """--hint is followed by an option, paths follow '--', no apply flags, neutral cwd/config."""
    log = external_dir(tmp_path) / "argv.json"
    root = workspace(tmp_path, {"src/a.py": "f(1)\n"})
    install_engine(tmp_path, monkeypatch,
                   f"Path({str(log)!r}).write_text(json.dumps({{'argv': sys.argv[1:], 'cwd': os.getcwd()}}))\n"
                   "print('[]')\n")
    rules = [simple_rule("a-1", message="line1\n---\nline3 ... # x", note="é-😀"),
             simple_rule("b.2", fix=None, severity="off")]
    rc, result = preview(monkeypatch, capsys, root, json.dumps(rules), "src")
    assert rc == 0 and result["stop_reason"] == "no_match", result
    seen = json.loads(log.read_text())
    argv = seen["argv"]
    assert argv[0] == "scan"
    assert not {"-U", "--update-all", "-i", "--interactive"} & set(argv)
    config = Path(argv[argv.index("--config") + 1])
    assert config.is_absolute() and Path(seen["cwd"]).resolve() != root.resolve()
    inline = [item for item in argv if item.startswith("--inline-rules=")]
    assert len(inline) == 1
    documents = inline[0][len("--inline-rules="):].split("\n---\n")
    assert [json.loads(doc) for doc in documents] == rules
    assert all("\n" not in doc for doc in documents)
    hints = [i for i, item in enumerate(argv) if item.startswith("--hint")]
    assert [argv[i] for i in hints] == ["--hint=a-1", "--hint=b.2"]  # every caller rule, never bare
    assert hints == list(range(hints[0], hints[0] + len(hints)))
    after = argv[hints[-1] + 1]
    assert after.startswith("--") and after != "--"
    for kind in code_intel_rules.NO_IGNORE:
        assert ["--no-ignore", kind] in [argv[i:i + 2] for i in range(len(argv) - 1)]
    separator = argv.index("--")
    assert separator == len(argv) - 2 and Path(argv[-1]).is_absolute() and argv[-1] != str(root)
    assert "--json=compact" in argv[:separator]


@pytest.mark.parametrize("args", [
    ("--lang", "python"), ("--pattern", "f($A)"), ("--rewrite", "g($A)"),
])
def test_boundaries_rule_json_cannot_mix_with_pattern_mode(tmp_path, monkeypatch, capsys, args):
    root = workspace(tmp_path, {"a.py": "f()\n"})
    rc, result = run_cli(monkeypatch, capsys, "--root", root, "--rule-json", rules_json(simple_rule()), *args, ".")
    assert rc == 2 and result["error"] == "invalid_input"


@pytest.mark.parametrize(("extra", "paths"), [(("--max-passes", "0"), (".",)), (("--max-passes", "33"), (".",)),
                                              ((), ())])
def test_boundaries_preview_arguments(tmp_path, monkeypatch, capsys, extra, paths):
    root = workspace(tmp_path, {"a.py": "f()\n"})
    monkeypatch.setattr(sys, "argv", ["code_intel.py", "--root", str(root), "--rule-json",
                                      rules_json(simple_rule()), *extra, *paths])
    assert code_intel.main() == 2
    assert json.loads(capsys.readouterr().out)["error"] == "invalid_input"


@pytest.mark.parametrize("flag", [("--max-passes", "3"), ("--rule-tests-json", "[]")])
def test_boundaries_new_flags_require_rule_json_in_pattern_mode(tmp_path, monkeypatch, capsys, flag):
    monkeypatch.setattr(sys, "argv", ["code_intel.py", "--root", str(tmp_path), "--lang", "c",
                                      "--pattern", "f($A)", *flag, "."])
    assert code_intel.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error" and result["pattern_validated"] is False


@pytest.mark.parametrize(("argv", "missing"), [
    (["."], "--lang, --pattern"), (["--lang", "c", "."], "--pattern"), (["--lang", "c", "--pattern", "x"], "paths"),
])
def test_boundaries_pattern_mode_keeps_argparse_required_errors(monkeypatch, capsys, argv, missing):
    monkeypatch.setattr(sys, "argv", ["code_intel.py", *argv])
    with pytest.raises(SystemExit) as raised:
        code_intel.main()
    assert raised.value.code == 2
    assert f"the following arguments are required: {missing}" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["../outside.py", "sub/../../outside.py", "/etc/hosts"])
def test_boundaries_paths_cannot_escape(tmp_path, monkeypatch, capsys, value):
    install_engine(tmp_path, monkeypatch, "print('[]')\n")
    root = workspace(tmp_path, {"sub/a.py": "f()\n"})
    (tmp_path / "outside.py").write_text("f()\n")
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule()), value)
    assert rc == 2 and result["error"] == "path_escape"


@pytest.mark.parametrize("kind", ["file-link", "dir-link", "target-link", "fifo"])
def test_boundaries_symlinks_and_special_files_are_rejected_without_blocking(tmp_path, monkeypatch, capsys, kind):
    marker = tmp_path / "engine-ran"
    install_engine(tmp_path, monkeypatch, f"Path({str(marker)!r}).touch()\nprint('[]')\n")
    root = workspace(tmp_path, {"src/a.py": "f()\n"})
    outside = tmp_path / "secret"
    outside.mkdir()
    (outside / "s.py").write_text("f(secret)\n")
    target = "src"
    if kind == "file-link":
        (root / "src/link.py").symlink_to(outside / "s.py")
    elif kind == "dir-link":
        (root / "src/linked").symlink_to(outside)
    elif kind == "target-link":
        (root / "alias").symlink_to(root / "src")
        target = "alias"
    else:
        os.mkfifo(root / "src/pipe.py")
    start = time.monotonic()
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule()), target)
    assert time.monotonic() - start < 10
    assert rc == 2 and result["error"] == "unsupported_file_type", result
    assert not marker.exists()


def test_boundaries_missing_path_is_rc2(tmp_path, monkeypatch, capsys):
    root = workspace(tmp_path, {"a.py": "f()\n"})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule()), "nope.py")
    assert rc == 2 and result["error"] == "path_missing"


@pytest.mark.parametrize(("constant", "value", "files"), [
    ("MAX_FILES", 2, {"a.py": "f()\n", "b.py": "f()\n", "c.py": "f()\n"}),
    ("MAX_FILE_BYTES", 8, {"a.py": "f(123456789)\n"}),
    ("MAX_SOURCE_BYTES", 10, {"a.py": "f(1)\n", "b.py": "f(2)\n", "c.py": "f(3)\n"}),
    ("MAX_DEPTH", 2, {"a/b/c/d/e.py": "f()\n"}),
    ("MAX_DIRECTORY_ENTRIES", 3, {"a.py": "", "b.py": "", "c.py": "", "d.py": ""}),
])
def test_boundaries_input_limits(tmp_path, monkeypatch, capsys, constant, value, files):
    marker = tmp_path / "engine-ran"
    install_engine(tmp_path, monkeypatch, f"Path({str(marker)!r}).touch()\nprint('[]')\n")
    monkeypatch.setattr(code_intel_rules, constant, value)
    root = workspace(tmp_path, files)
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule()))
    assert rc == 2 and result["error"] == "limit", result
    assert not marker.exists()


def test_boundaries_limits_allow_equality(tmp_path, monkeypatch, capsys):
    install_engine(tmp_path, monkeypatch, "print('[]')\n")
    monkeypatch.setattr(code_intel_rules, "MAX_FILES", 2)
    monkeypatch.setattr(code_intel_rules, "MAX_FILE_BYTES", 5)
    monkeypatch.setattr(code_intel_rules, "MAX_SOURCE_BYTES", 10)
    root = workspace(tmp_path, {"a.py": "f(1)\n", "b.py": "f(2)\n"})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule()))
    assert rc == 0 and result["files_copied"] == 2


@pytest.mark.parametrize(("constant", "text"), [
    ("MAX_RULE_BYTES", None), ("MAX_CASES_BYTES", "cases"),
])
def test_boundaries_rule_and_case_bytes_limited(tmp_path, monkeypatch, capsys, constant, text):
    install_engine(tmp_path, monkeypatch, "print('[]')\n")
    rules = rules_json(simple_rule("r", fix=None))
    monkeypatch.setattr(code_intel_rules, constant, len(rules) - 1 if text is None else 20)
    args = ["--root", tmp_path, "--rule-json", rules]
    if text is None:
        args.append(".")
    else:
        args += ["--rule-tests-json", json.dumps([{"id": "r", "valid": ["x"], "invalid": ["f(1)"]}])]
    rc, result = run_cli(monkeypatch, capsys, *args)
    assert rc == 2 and result["error"] == "input_too_large"


def test_boundaries_intermediate_growth_is_bounded(tmp_path, monkeypatch, capsys):
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "grow", "find": "x", "replace": "xx"}]))
    monkeypatch.setattr(code_intel_rules, "MAX_FILE_BYTES", 64)
    root = workspace(tmp_path, {"a.py": "x" * 40})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("grow", fix="xx")),
                         extra=("--max-passes", "32"))
    assert rc == 2 and result["error"] == "limit"
    assert (root / "a.py").read_text() == "x" * 40


@pytest.mark.parametrize(("mutate", "code"), [
    ("rows[0]['file'] = '/elsewhere/a.py'", "schema_mismatch"),
    ("rows[0]['ruleId'] = 'ghost'", "schema_mismatch"),
    ("rows[0]['range']['byteOffset']['start'] = True", "schema_mismatch"),
    ("rows[0]['range']['byteOffset']['end'] = 10**6", "schema_mismatch"),
    ("rows[0]['text'] = 'f(9)'", "schema_mismatch"),
    ("rows[0]['range']['start'] = None", "schema_mismatch"),
    ("rows[0]['replacementOffsets']['end'] += 1", "schema_mismatch"),
    ("rows[0]['replacementOffsets']['start'] = -1", "schema_mismatch"),
    ("del rows[0]['replacement']", "schema_mismatch"),
    ("del rows[0]['replacementOffsets']", "schema_mismatch"),
    ("rows[0]['replacementOffsets'] = {'start': 0, 'end': '4'}", "schema_mismatch"),
    ("rows.append(dict(rows[0], replacement='k(1)'))", "schema_mismatch"),
    ("rows.append(dict(rows[0], ruleId='s'))", "cross_rule_same_range"),
    ("rows = {'not': 'a list'}", "schema_mismatch"),
    ("rows.append(1)", "schema_mismatch"),
    ("print('not json'); sys.exit(0)", "schema_mismatch"),
    ("print('boom', file=sys.stderr); sys.exit(8)", "engine_error"),
    ("print(json.dumps(rows)); sys.exit(1)", "engine_error"),
])
def test_boundaries_malformed_native_output_is_json_rc2(tmp_path, monkeypatch, capsys, mutate, code):
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": "f(1)", "replace": "h(1)"}], mutate))
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    rules = rules_json(simple_rule("r"), simple_rule("s"))
    rc, result = preview(monkeypatch, capsys, root, rules)
    assert rc == 2 and result["status"] == "error" and result["error"] == code, result
    assert "files" not in result and "matches" not in result
    assert (root / "a.py").read_text() == "f(1)\n"


def test_boundaries_utf8_splitting_offsets_are_rejected(tmp_path, monkeypatch, capsys):
    mutate = ("for r in rows:\n"
              "    r['range']['byteOffset']['start'] -= 1\n"
              "    r['replacementOffsets']['start'] -= 1\n"
              "    r['text'] = 'X'\n")
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": "f(1)", "replace": "h(1)"}], mutate))
    root = workspace(tmp_path, {"a.py": "x = éf(1)\n"})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "schema_mismatch"


def test_boundaries_no_fix_rule_must_not_carry_replacement(tmp_path, monkeypatch, capsys):
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": "f(1)", "replace": "h(1)"}]))
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r", fix=None)))
    assert rc == 2 and result["error"] == "schema_mismatch"


def test_boundaries_no_fix_matches_report_without_changes(tmp_path, monkeypatch, capsys):
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": "f(1)"}]))
    root = workspace(tmp_path, {"a.py": "f(1)\nf(1)\n"})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r", fix=None)),
                         extra=("--limit", "1"))
    assert rc == 0 and result["stop_reason"] == "idempotent" and result["changed_passes"] == 0
    assert result["iterations"] == 1 and result["match_count"] == 2 and len(result["matches"]) == 1
    assert result["truncated"] is True and result["files"] == [] and result["converged"] is True


def test_boundaries_select_edits_outermost_first_and_touching():
    data = b"f(f(f(1))) + g(2)"
    edits = [(0, 10, "a", b"OUT"), (2, 9, "a", b"MID"), (4, 8, "b", b"IN"), (13, 17, "a", b"G"), (10, 13, "c", b" ~ ")]
    selected = code_intel_rules.select_edits("x", edits)
    assert [(s, e) for s, e, _ in selected] == [(0, 10), (10, 13), (13, 17)]
    assert code_intel_rules.apply_edits(data, selected) == b"OUT ~ G"
    with pytest.raises(code_intel_rules.RuleError) as partial:
        code_intel_rules.select_edits("x", [(0, 5, "a", b""), (3, 8, "b", b"")])
    assert partial.value.code == "schema_mismatch"
    with pytest.raises(code_intel_rules.RuleError) as same:
        code_intel_rules.select_edits("x", [(0, 5, "a", b"1"), (0, 5, "b", b"1")])
    assert same.value.code == "cross_rule_same_range"
    assert code_intel_rules.select_edits("x", [(0, 5, "a", b"1"), (0, 5, "a", b"1")]) == [(0, 5, b"1")]


def test_boundaries_cycle_and_pass_limit_report_no_diff(tmp_path, monkeypatch, capsys):
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "ab", "find": "a", "replace": "b"},
                                                   {"ruleId": "ba", "find": "b", "replace": "a"}]))
    root = workspace(tmp_path, {"x.py": "a\n"})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("ab"), simple_rule("ba")))
    assert rc == 2 and result["error"] == "nonconvergence" and result["stop_reason"] == "cycle"
    assert result["iterations"] == 2 and result["changed_passes"] == 2 and result["last_changed_files"] == ["x.py"]
    assert "files" not in result and result["converged"] is False
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "grow", "find": "a", "replace": "aa"}]))
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("grow")), extra=("--max-passes", "3"))
    assert rc == 2 and result["stop_reason"] == "pass_limit" and result["iterations"] == 3
    assert result["changed_passes"] == 3 and "files" not in result


@pytest.mark.parametrize(("chain", "max_passes", "rc"), [(2, 3, 0), (3, 3, 2), (2, 2, 2), (0, 1, 0), (1, 1, 2)])
def test_boundaries_confirm_scan_counts_toward_pass_cap(tmp_path, monkeypatch, capsys, chain, max_passes, rc):
    """A chain a->b->c needs chain change passes plus one confirm scan inside the cap."""
    letters = "abcdefgh"
    steps = [{"ruleId": f"s{i}", "find": letters[i], "replace": letters[i + 1]} for i in range(chain)]
    install_engine(tmp_path, monkeypatch, scanner(steps))
    root = workspace(tmp_path, {"x.py": "a" if chain else "z"})
    rules = rules_json(*(simple_rule(step["ruleId"]) for step in steps)) if chain else rules_json(simple_rule("s0"))
    got, result = preview(monkeypatch, capsys, root, rules, extra=("--max-passes", str(max_passes)))
    assert got == rc, result
    assert result["iterations"] == min(chain + 1, max_passes)
    assert result["changed_passes"] == min(chain, max_passes)
    expected = ("no_match" if chain == 0 else "fixed_point") if rc == 0 else "pass_limit"
    assert result["stop_reason"] == expected
    if rc == 0 and chain:
        assert result["files"][0]["result_sha256"] == hashlib.sha256(letters[chain].encode()).hexdigest()


def test_boundaries_source_changed_during_preview_is_rc2_and_not_rolled_back(tmp_path, monkeypatch, capsys):
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    install_engine(tmp_path, monkeypatch, scanner(
        [{"ruleId": "r", "find": "f(1)", "replace": "h(1)"}],
        f"Path({str(root / 'a.py')!r}).write_text('changed by someone else\\n')"))
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "source_changed" and result["changed_paths"] == ["a.py"]
    assert (root / "a.py").read_text() == "changed by someone else\n"
    assert "files" not in result


def test_boundaries_source_added_during_preview_is_detected(tmp_path, monkeypatch, capsys):
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    install_engine(tmp_path, monkeypatch, scanner([], f"Path({str(root / 'new.py')!r}).write_text('x')"))
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "source_changed" and result["changed_paths"] == ["new.py"]


def test_boundaries_preview_never_writes_sources_or_plugin_tree(tmp_path, monkeypatch, capsys):
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": "f(1)", "replace": "h(1)"}]))
    root = workspace(tmp_path, {"a.py": "f(1)\n", "sub/b.py": "x = f(1)\n", ".hidden/c.py": "f(1)"})
    before, plugin = tree_digest(root), tree_digest(TOOLS.parent)
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 0 and result["changed_file_count"] == 3 and result["files_copied"] == 3
    assert tree_digest(root) == before and tree_digest(TOOLS.parent) == plugin
    assert result["source_sha256"]["a.py"] == hashlib.sha256(b"f(1)\n").hexdigest()
    diff = {entry["path"]: entry["diff"] for entry in result["files"]}
    assert "-f(1)\n+h(1)\n" in diff["a.py"] and "\\ No newline at end of file" in diff[".hidden/c.py"]


def test_boundaries_copy_set_is_not_cut_by_display_limit(tmp_path, monkeypatch, capsys):
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": "f(1)", "replace": "h(1)"}]))
    root = workspace(tmp_path, {f"m{i}.py": "f(1)\n" for i in range(5)})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")), extra=("--limit", "2"))
    assert rc == 0 and result["files_copied"] == 5 and result["changed_file_count"] == 5
    assert len(result["files"]) == 2 and len(result["matches"]) == 2 and result["truncated"] is True


def test_boundaries_ignore_comment_notice_counts_files(tmp_path, monkeypatch, capsys):
    install_engine(tmp_path, monkeypatch, "print('[]')\n")
    root = workspace(tmp_path, {"a.py": "# ast-grep-ignore\nf(1)\n", "b.ts": "// ast-grep-ignore\n", "c.py": "f()\n"})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 0 and result["stop_reason"] == "no_match"
    assert any(notice.startswith("2 copied file(s) contain 'ast-grep-ignore'") for notice in result["notices"])


@pytest.mark.parametrize(("version", "rc", "status"), [("0.50.9", 3, "unavailable"), ("0.52.0", 0, "ok"),
                                                       ("1.0.0", 0, "ok")])
def test_boundaries_engine_version_policy(tmp_path, monkeypatch, capsys, version, rc, status):
    install_engine(tmp_path, monkeypatch, "print('[]')\n", version=version)
    root = workspace(tmp_path, {"a.py": "f()\n"})
    got, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert got == rc and result["status"] == status
    if rc == 3:
        assert result["error"] == "unsupported_engine" and result["engine_version"] == version
    else:
        assert result["tested_version"] == "0.51.0" and result["engine_version"] == version
        assert any("differs from tested 0.51.0" in notice for notice in result["notices"])


def test_boundaries_missing_engine_is_rc3_for_both_modes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(code_intel.shutil, "which", lambda name: None)
    root = workspace(tmp_path, {"a.py": "f()\n"})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 3 and result["status"] == "unavailable"
    rc, result = run_cli(monkeypatch, capsys, "--root", root, "--rule-json", rules_json(simple_rule("r")),
                         "--rule-tests-json", json.dumps({"id": "r", "valid": ["x"], "invalid": ["f(1)"]}))
    assert rc == 3 and result["status"] == "unavailable" and result["mode"] == "rule-test"


def test_boundaries_workspace_engine_is_never_executed(tmp_path, monkeypatch, capsys):
    root = workspace(tmp_path, {"a.py": "f()\n"})
    marker = tmp_path / "executed"
    engine = root / "ast-grep"
    engine.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n")
    engine.chmod(0o700)
    monkeypatch.setattr(code_intel.shutil, "which", lambda name: str(engine))
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")), "a.py")
    assert rc == 2 and result["error"] == "engine_rejected" and not marker.exists()


def test_boundaries_one_deadline_covers_all_passes_and_kills_children(tmp_path, monkeypatch, capsys):
    pidfile = tmp_path / "child.pid"
    install_engine(tmp_path, monkeypatch, scanner(
        [{"ruleId": "f", "find": "a", "replace": "aa"}],
        "import subprocess\n"
        f"child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"Path({str(pidfile)!r}).write_text(str(child.pid))\n"
        "time.sleep(0.4)\n"))
    monkeypatch.setattr(code_intel, "QUERY_TIMEOUT", 2.5)
    root = workspace(tmp_path, {"x.py": "a"})
    start = time.monotonic()
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("f")), extra=("--max-passes", "32"))
    assert time.monotonic() - start < 8
    assert rc == 2 and result["error"] == "budget", result
    time.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)


def test_boundaries_shared_output_budget(tmp_path, monkeypatch, capsys):
    install_engine(tmp_path, monkeypatch, "os.write(2, b'e' * 990)\nprint('[]')\n")
    monkeypatch.setattr(code_intel, "MAX_OUTPUT_BYTES", 1000)
    root = workspace(tmp_path, {"a.py": "f()\n"})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "budget" and "output exceeded" in result["reason"]


def test_boundaries_own_result_size_is_bounded(tmp_path, monkeypatch, capsys):
    """Engine output fits, but the per-file hash report does not: rc2, never a partial success."""
    install_engine(tmp_path, monkeypatch, "print('[]')\n")
    root = workspace(tmp_path, {f"file-{i:03d}.py": "" for i in range(150)})
    monkeypatch.setattr(code_intel, "MAX_OUTPUT_BYTES", 4000)
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["status"] == "error" and result["error"] == "budget", result
    assert "source_sha256" not in result


def stdin_cli(tmp_path, args, data: bytes, *, path_dir, timeout=20):
    """Real CLI subprocess fed only test-controlled JSON bytes through a bounded PIPE."""
    env = {**os.environ, "PYTHONPATH": "", "PYTHONNOUSERSITE": "1", "PATH": str(path_dir)}
    process = subprocess.Popen([sys.executable, "-B", str(TOOLS / "code_intel.py"), *map(str, args)], cwd=tmp_path,
                               env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)
    try:
        stdout, stderr = process.communicate(data, timeout=timeout)
    finally:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    assert not stderr, stderr
    return process.returncode, json.loads(stdout)


def path_engine(tmp_path, program: str) -> Path:
    directory = tmp_path.parent / (tmp_path.name + "-bin")
    directory.mkdir(exist_ok=True)
    engine = directory / "ast-grep"
    engine.write_text(f"#!{sys.executable} -B\nimport json, sys\nfrom pathlib import Path\n"
                      "if '--version' in sys.argv: print('ast-grep 0.51.0'); sys.exit(0)\n" + program)
    engine.chmod(0o700)
    return directory


def test_boundaries_rule_json_from_bounded_stdin(tmp_path):
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    bin_dir = path_engine(tmp_path, scanner([{"ruleId": "r", "find": "f(1)", "replace": "h(1)"}]))
    rc, result = stdin_cli(tmp_path, ["--root", root, "--rule-json", "-", "a.py"],
                           rules_json(simple_rule("r")).encode(), path_dir=bin_dir)
    assert rc == 0 and result["changed_file_count"] == 1, result
    rc, result = stdin_cli(tmp_path, ["--root", root, "--rule-json", "-", "a.py"],
                           b" " * (code_intel_rules.MAX_RULE_BYTES + 1), path_dir=bin_dir)
    assert rc == 2 and result["error"] == "input_too_large"
    rc, result = stdin_cli(tmp_path, ["--root", root, "--rule-json", "-", "a.py"], b"\xff{}", path_dir=bin_dir)
    assert rc == 2 and result["error"] == "invalid_json"


def test_boundaries_stdin_never_blocks_past_deadline(tmp_path, monkeypatch, capsys):
    read_end, write_end = os.pipe()
    try:
        monkeypatch.setattr(sys, "stdin", os.fdopen(read_end, "r", closefd=False))
        monkeypatch.setattr(code_intel, "QUERY_TIMEOUT", 1)
        os.write(write_end, b"[")
        start = time.monotonic()
        rc, result = run_cli(monkeypatch, capsys, "--root", tmp_path, "--rule-json", "-", ".")
        assert time.monotonic() - start < 5
        assert rc == 2 and result["error"] == "budget"
    finally:
        os.close(read_end)
        os.close(write_end)


def test_boundaries_stdin_tty_is_refused(tmp_path, monkeypatch, capsys):
    """A terminal stdin is refused before any read (isatty is faked: openpty may be denied)."""
    read_end, write_end = os.pipe()
    try:
        monkeypatch.setattr(sys, "stdin", os.fdopen(read_end, "r", closefd=False))
        monkeypatch.setattr(code_intel_rules.os, "isatty", lambda fd: fd == read_end)
        start = time.monotonic()
        rc, result = run_cli(monkeypatch, capsys, "--root", tmp_path, "--rule-json", "-", ".")
        assert time.monotonic() - start < 2
        assert rc == 2 and result["error"] == "stdin_tty"
    finally:
        os.close(read_end)
        os.close(write_end)


# =============================================================== rule tests
RULE_TEST_STDOUT = "Running {n} tests\n\n----------- Case Details -----------\n{lines}\n\ntest result: ok. {p} passed; {f} failed;\n"


def rule_test_engine(tmp_path, monkeypatch, stdout: str, stderr: str = "", rc: int = 0, extra: str = ""):
    log = external_dir(tmp_path) / "test-argv.json"
    install_engine(tmp_path, monkeypatch,
                   "config = Path(sys.argv[sys.argv.index('--config') + 1])\n"
                   f"Path({str(log)!r}).write_text(json.dumps({{'argv': sys.argv[1:], 'cwd': os.getcwd(), "
                   "'config': config.read_text(), 'rules': (config.parent / 'rules/rules.yml').read_text(), "
                   "'tests': sorted(p.name for p in (config.parent / 'tests').iterdir())}))\n"
                   + extra + f"sys.stdout.write({stdout!r})\nsys.stderr.write({stderr!r})\nsys.exit({rc})\n")
    return log


def rule_test_cli(monkeypatch, capsys, root, rules, tests):
    return run_cli(monkeypatch, capsys, "--root", root, "--rule-json", json.dumps(rules),
                   "--rule-tests-json", json.dumps(tests))


TWO_RULES = [simple_rule("t-one", fix=None), simple_rule("t-two", pattern="g($X)", fix=None, severity="off")]
TWO_TESTS = [{"id": "t-one", "valid": ["g(1)"], "invalid": ["f(1)", "f(2)"]},
             {"id": "t-two", "valid": ["f(1)"], "invalid": ["g(1)"]}]


def test_rule_tests_pass_argv_and_counts(tmp_path, monkeypatch, capsys):
    log = rule_test_engine(tmp_path, monkeypatch, RULE_TEST_STDOUT.format(
        n=2, lines="PASS t-one  ...\nPASS t-two  ..", p=2, f=0))
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, TWO_RULES, TWO_TESTS)
    assert rc == 0 and result["status"] == "ok" and result["mode"] == "rule-test", result
    assert result["cases_run"] == 5 and result["cases_passed"] == 5 and result["tests_failed"] == 0
    assert any("match/non-match only" in notice for notice in result["notices"])
    seen = json.loads(log.read_text())
    assert seen["argv"][:1] == ["test"] and {"--skip-snapshot-tests", "--include-off"} <= set(seen["argv"])
    assert not {"-U", "--update-all", "-i", "--interactive"} & set(seen["argv"])
    assert json.loads(seen["config"]) == {"ruleDirs": ["rules"], "testConfigs": [{"testDir": "tests"}]}
    assert [json.loads(doc) for doc in seen["rules"].strip().split("\n---\n")] == TWO_RULES
    assert seen["tests"] == ["case-0001.yml", "case-0002.yml"]


def test_rule_tests_genuine_mismatch_is_rc1(tmp_path, monkeypatch, capsys):
    rule_test_engine(tmp_path, monkeypatch,
                     "Running 2 tests\n\n----------- Case Details -----------\n[Noisy] Expect t-two to report no "
                     "issue, but some issues found in:\n\n  f(1)\n\nPASS t-one  ...\nFAIL t-two  N.\n\n\n",
                     "Error: test failed. 1 passed; 1 failed;\n", rc=4)
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, TWO_RULES, TWO_TESTS)
    assert rc == 1 and result["status"] == "failed" and result["tests_failed"] == 1
    assert result["results"][1] == {"id": "t-two", "status": "FAIL", "valid": {"total": 1, "passed": 0},
                                    "invalid": {"total": 1, "passed": 1}}
    assert result["cases_failed"] == 1


@pytest.mark.parametrize(("stdout", "stderr", "rc", "code"), [
    (RULE_TEST_STDOUT.format(n=3, lines="Configuration not found! x\nPASS t-one  ...\nPASS t-two  ..", p=2, f=0),
     "", 0, "unverified_test"),
    (RULE_TEST_STDOUT.format(n=2, lines="PASS t-one  ...\nSKIP t-two  ", p=2, f=0), "", 0, "unverified_test"),
    (RULE_TEST_STDOUT.format(n=0, lines="", p=0, f=0), "", 0, "unrecognized_output"),
    (RULE_TEST_STDOUT.format(n=2, lines="PASS t-one  ...", p=1, f=0), "", 0, "unrecognized_output"),
    (RULE_TEST_STDOUT.format(n=2, lines="PASS t-one  ...\nPASS t-two  ..\nPASS t-two  ..", p=2, f=0), "", 0,
     "unrecognized_output"),
    (RULE_TEST_STDOUT.format(n=2, lines="PASS t-one  ..\nPASS t-two  ..", p=2, f=0), "", 0, "unrecognized_output"),
    (RULE_TEST_STDOUT.format(n=2, lines="PASS t-one  ..M\nPASS t-two  ..", p=2, f=0), "", 0, "unrecognized_output"),
    (RULE_TEST_STDOUT.format(n=2, lines="PASS t-one  M..\nPASS t-two  ..", p=2, f=0), "", 0, "unrecognized_output"),
    (RULE_TEST_STDOUT.format(n=2, lines="PASS t-one  ...\nPASS t-two  ..", p=1, f=1), "", 0, "unrecognized_output"),
    (RULE_TEST_STDOUT.format(n=2, lines="PASS t-one  ...\nFAIL t-two  N.", p=1, f=1), "", 0, "unrecognized_output"),
    ("Running 2 tests\nPASS t-one  ...\nPASS t-two  ..\n", "", 0, "unrecognized_output"),
    ("Running 2 tests\nPASS t-one  ...\nFAIL t-two  ..\n", "Error: test failed. 1 passed; 1 failed;\n", 4,
     "unrecognized_output"),
    ("", "Error: Cannot parse rule\n", 8, "unrecognized_output"),
    ("garbage", "", 0, "unrecognized_output"),
])
def test_rule_tests_false_success_shapes_are_rc2(tmp_path, monkeypatch, capsys, stdout, stderr, rc, code):
    rule_test_engine(tmp_path, monkeypatch, stdout, stderr, rc)
    got, result = rule_test_cli(monkeypatch, capsys, tmp_path, TWO_RULES, TWO_TESTS)
    assert got == 2 and result["error"] == code, result


@pytest.mark.parametrize(("tests", "code"), [
    ([{"id": "t-one", "valid": ["x"], "invalid": ["f(1)"]}], "untested_rule"),
    ([*TWO_TESTS, {"id": "ghost", "valid": ["x"], "invalid": ["y"]}], "unknown_test_id"),
    ([TWO_TESTS[0], TWO_TESTS[0], TWO_TESTS[1]], "duplicate_test_id"),
    ([{"id": "t-one", "valid": [], "invalid": ["f(1)"]}, TWO_TESTS[1]], "invalid_test"),
    ([{"id": "t-one", "valid": ["g(1)"], "invalid": []}, TWO_TESTS[1]], "invalid_test"),
    ([{"id": "t-one", "valid": ["g(1)"]}, TWO_TESTS[1]], "invalid_test"),
    ([{"id": "t-one", "valid": [1], "invalid": ["f(1)"]}, TWO_TESTS[1]], "invalid_test"),
    ([{**TWO_TESTS[0], "snapshots": {}}, TWO_TESTS[1]], "unsupported_key"),
    ([{"id": "../x", "valid": ["a"], "invalid": ["b"]}], "invalid_rule_id"),
    ([], "invalid_input"),
])
def test_rule_tests_input_contract_rejected_before_engine(tmp_path, monkeypatch, capsys, tests, code):
    marker = tmp_path / "engine-ran"
    install_engine(tmp_path, monkeypatch, f"Path({str(marker)!r}).touch()\n")
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, TWO_RULES, tests)
    assert rc == 2 and result["error"] == code, result
    assert not marker.exists()


@pytest.mark.parametrize("extra", [("a.py",), ("--max-passes", "2")])
def test_rule_tests_reject_paths_and_passes(tmp_path, monkeypatch, capsys, extra):
    (tmp_path / "a.py").write_text("f()\n")
    rc, result = run_cli(monkeypatch, capsys, "--root", tmp_path, "--rule-json", json.dumps(TWO_RULES),
                         "--rule-tests-json", json.dumps(TWO_TESTS), *extra)
    assert rc == 2 and result["error"] == "invalid_input"


def test_rule_tests_snapshot_write_is_rejected(tmp_path, monkeypatch, capsys):
    rule_test_engine(tmp_path, monkeypatch, RULE_TEST_STDOUT.format(
        n=2, lines="PASS t-one  ...\nPASS t-two  ..", p=2, f=0),
        extra="snap = config.parent / 'tests' / '__snapshots__'\nsnap.mkdir()\n(snap / 's.yml').write_text('x')\n")
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, TWO_RULES, TWO_TESTS)
    assert rc == 2 and result["error"] == "snapshot_written"


# =============================================================== real engine
def real_preview(monkeypatch, capsys, root, rules, *paths, extra=()):
    rc, result = preview(monkeypatch, capsys, root, json.dumps(rules), *paths, extra=extra)
    assert result.get("engine_version") or result["error"] in ("cross_rule_same_range", "nonconvergence"), result
    return rc, result


@pytest.mark.parametrize(("version", "iterations", "changed", "check_rc"), [("v1", 2, 1, 12), ("v2", 3, 2, 0)])
def test_real_engine_python_fixture_matches_native_and_fixed_point_is_not_correctness(
        real_engine, tmp_path, monkeypatch, capsys, version, iterations, changed, check_rc):
    rules = json.loads((FIXTURES / f"rules/py-{version}.json").read_text())
    source = copy_fixture("py", tmp_path, "source")
    before = tree_digest(source)
    rc, result = real_preview(monkeypatch, capsys, source, rules, "app")
    assert rc == 0 and result["converged"] and result["stop_reason"] == "fixed_point", result
    assert (result["iterations"], result["changed_passes"]) == (iterations, changed)
    assert result["passes"][0]["match_count"] == 9 and result["passes"][0]["edits_selected"] == 8
    assert tree_digest(source) == before
    native = copy_fixture("py", tmp_path, "native")
    passes = native_fixed_point(real_engine, rules, native / "app", tmp_path / "scratch")
    assert len(passes) == iterations
    assert [p["changed_files"] for p in result["passes"]] == [[f"app/{rel}" for rel in p] for p in passes]
    assert_preview_matches_native(result, source / "app", native / "app", prefix="app/")
    original_rc, _, _ = run_bounded([sys.executable, "-B", "check.py", "original"], cwd=source)
    migrated_rc, out, _ = run_bounded([sys.executable, "-B", "check.py", "migrated"], cwd=native)
    assert original_rc == 0
    # v1 loses its import guard after pass 1 and converges to wrong code (NameError).
    assert migrated_rc == check_rc, out
    a_diff = next(entry["diff"] for entry in result["files"] if entry["path"] == "app/a.py")
    assert ("+    return new_api(old_api(2), scale=3)" in a_diff) is (version == "v1")
    b_diff = next(entry["diff"] for entry in result["files"] if entry["path"] == "app/b.py")
    assert "w.old_api(1) + new_api(10)" in b_diff
    assert "app/shadow.py" not in {entry["path"] for entry in result["files"]}


def test_real_engine_typescript_fixture_matches_native(real_engine, tmp_path, monkeypatch, capsys):
    rules = json.loads((FIXTURES / "rules/ts-v1.json").read_text())
    source = copy_fixture("ts", tmp_path, "source")
    targets = ["a.ts", "obj.ts", "shadow.ts"]
    rc, result = real_preview(monkeypatch, capsys, source, rules, *targets)
    assert rc == 0 and (result["iterations"], result["changed_passes"]) == (2, 1), result
    assert result["files_copied"] == 3
    native = copy_fixture("ts", tmp_path, "native")
    work = tmp_path / "native-targets"
    work.mkdir()
    for name in targets:
        shutil.copy2(native / name, work / name)
    assert len(native_fixed_point(real_engine, rules, work, tmp_path / "scratch")) == 2
    assert_preview_matches_native(result, source, work)
    diff = "".join(entry["diff"] for entry in result["files"])
    assert '+  return fmt.legacyFormat(1) + "|" + formatV2(2);' in diff
    assert "-export const label" not in diff and "shadow.ts" not in {e["path"] for e in result["files"]}
    node = shutil.which("node")
    if node:
        for name in targets:
            shutil.copy2(work / name, native / name)
        original_rc, _, _ = run_bounded([node, "check.ts", "original"], cwd=source)
        migrated_rc, out, err = run_bounded([node, "check.ts", "migrated"], cwd=native)
        if original_rc == 0:  # this node strips TypeScript types
            assert migrated_rc == 0, (out, err)


NESTED = {
    "same-rule-chain-multibyte": ({"m.py": "# 한글 주석\nx = f(f(f(1)))\ns = \"한\" + f(f(\"é\"))\nt = f(f(1), f(2))\n"},
                                  [simple_rule("call-f", "f($$$A)", "h($$$A)")], 4),
    "same-start-binop": ({"b.py": "z = 1 + 2 + 3 + 4\nw = (5 + 6) + 7\n"},
                         [simple_rule("add", "$A + $B", "add($A, $B)")], 4),
    "same-start-callcall": ({"c.py": "y = g(1)(2)(3)\n"},
                            [{"id": "callcall", "language": "python", "rule": {"kind": "call", "pattern": "$F($X)"},
                              "fix": "c($F, $X)"}], 4),
    "ts-crlf-multibyte": ({"n.ts": "const a = f(f(1));\r\nconst b = \"ü\" + f(f(f(2)));\r\nconst c = 1 + 2 + 3;\r\n"},
                          [simple_rule("ts-call-f", "f($X)", "h($X)", "typescript"),
                           {"id": "ts-add", "language": "typescript",
                            "rule": {"pattern": "$A + $B", "not": {"has": {"kind": "string", "stopBy": "end"}}},
                            "fix": "add($A, $B)"}], 4),
    "cross-rule-nested": ({"y.py": "v = f(g(1))\n"},
                          [simple_rule("outer-f", "f($X)", "h($X)"), simple_rule("inner-g", "g($X)", "k($X)")], 3),
    "template-only": ({"u.py": "v = f(f(1))\n"}, [simple_rule("tmpl", "f($X)", {"template": "h($X)"})], 3),
}


@pytest.mark.parametrize("case", sorted(NESTED))
def test_real_engine_strict_nesting_outermost_first_matches_native(real_engine, tmp_path, monkeypatch, capsys, case):
    files, rules, iterations = NESTED[case]
    source = workspace(tmp_path, files)
    rc, result = real_preview(monkeypatch, capsys, source, rules)
    assert rc == 0 and result["iterations"] == iterations and result["stop_reason"] == "fixed_point", result
    native = tmp_path / "native"
    shutil.copytree(source, native)
    assert len(native_fixed_point(real_engine, rules, native, tmp_path / "scratch")) == iterations
    assert_preview_matches_native(result, source, native)


@pytest.mark.parametrize(("files", "rules", "rc", "stop", "error"), [
    ({"i.py": "v = f(1)\n"}, [simple_rule("ident", "f($X)", "f($X)")], 0, "idempotent", None),
    ({"w.py": "v = f(1)\n"}, [simple_rule("no-fix", "f($X)", None)], 0, "idempotent", None),
    ({"s.py": "v = swap(1, 2)\n"}, [simple_rule("swap", "swap($A, $B)", "swap($B, $A)")], 2, "cycle", "nonconvergence"),
    ({"x.py": "v = f(1)\n"}, [simple_rule("r-one", "f($X)", "h($X)"), simple_rule("r-two", "f($X)", "k($X)")], 2,
     None, "cross_rule_same_range"),
    ({"q.py": "v = q(1)\n"}, [simple_rule("none", "f($X)", "h($X)")], 0, "no_match", None),
])
def test_real_engine_terminal_states(real_engine, tmp_path, monkeypatch, capsys, files, rules, rc, stop, error):
    source = workspace(tmp_path, files)
    before = tree_digest(source)
    got, result = real_preview(monkeypatch, capsys, source, rules)
    assert got == rc and result.get("error") == error and result.get("stop_reason") == stop, result
    assert result.get("changed_passes", 0) == (2 if stop == "cycle" else 0)
    assert tree_digest(source) == before
    if stop == "idempotent":
        assert result["match_count"] == 1 and result["files"] == []


def test_real_engine_hint_keeps_off_and_error_rules_and_paths(real_engine, tmp_path, monkeypatch, capsys):
    """--hint must not swallow the path and must include severity off/error rules."""
    source = workspace(tmp_path, {"a.py": "e(1)\no(1)\nn(1)\n", "sub/b.py": "e(2)\no(2)\n"})
    rules = [simple_rule("err", "e($X)", None, severity="error"), simple_rule("off", "o($X)", None, severity="off"),
             simple_rule("plain", "n($X)", None)]
    rc, result = real_preview(monkeypatch, capsys, source, rules, "a.py", "sub")
    assert rc == 0, result
    control_rules = [{key: value for key, value in rule.items() if key != "severity"} for rule in rules]
    rc_control, control = real_preview(monkeypatch, capsys, source, control_rules, "a.py", "sub")
    assert rc_control == 0

    def key(res):
        return sorted((m["file"], m["ruleId"], m["text"]) for m in res["matches"])

    assert key(result) == key(control)
    assert {m["file"] for m in result["matches"]} == {"a.py", "sub/b.py"}
    assert {m["ruleId"] for m in result["matches"]} == {"err", "off", "plain"}
    # Without hint flags native skips the off rule and exits 1 for error severity:
    # the inclusion above comes from the per-id hints, not from path handling.
    config = tmp_path / "neutral" / "sgconfig.yml"
    config.parent.mkdir()
    config.write_text("ruleDirs: []\n")
    _, inline = code_intel_rules.parse_rules(json.dumps(rules))
    base = [real_engine, "scan", "--config", str(config), f"--inline-rules={inline}", "--json=compact"]
    native_rc, stdout, _ = run_bounded([*base, "--", str(source)], cwd=config.parent)
    assert native_rc == 1
    assert "off" not in {row["ruleId"] for row in json.loads(stdout)}
    # Trap: a path placed right after hint flags must still be a path (same match files).
    native_rc, stdout, _ = run_bounded([*base, *hint_flags(rules), str(source / "a.py"), str(source / "sub")],
                                       cwd=config.parent)
    assert native_rc == 0 and {Path(row["file"]).name for row in json.loads(stdout)} == {"a.py", "b.py"}


def test_real_engine_copy_set_equals_query_set_despite_ignore_files(real_engine, tmp_path, monkeypatch, capsys):
    global_config = tmp_path / "xdg"
    (global_config / "git").mkdir(parents=True)
    (global_config / "git" / "ignore").write_text("glob.py\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(global_config))
    source = workspace(tmp_path, {
        ".gitignore": "proj/\n", "proj/.gitignore": "vcs.py\n", "proj/.ignore": "dot.py\n",
        "proj/.git/info/exclude": "excl.py\n", "proj/.git/HEAD": "ref: refs/heads/main\n",
        "proj/vcs.py": "f(1)\n", "proj/dot.py": "f(2)\n", "proj/excl.py": "f(3)\n", "proj/glob.py": "f(4)\n",
        "proj/.hidden_dir/h.py": "f(5)\n", "proj/.h.py": "f(6)\n", "proj/plain.py": "f(7)\n",
    })
    rc, result = real_preview(monkeypatch, capsys, source, [simple_rule("r", "f($X)", None)], "proj")
    assert rc == 0, result
    python_files = {rel for rel in result["source_sha256"] if rel.endswith(".py")}
    assert {m["file"] for m in result["matches"]} == python_files and len(python_files) == 7


def test_boundaries_display_order_is_stable_before_limit(tmp_path, monkeypatch, capsys):
    root = workspace(tmp_path, {"z.py": "f(1)\nf(22)\n", "a.py": "f(1)\nf(22)\n", "é.py": "f(1)\n"})
    spec = [{"ruleId": "z", "find": "f(1)"}, {"ruleId": "a", "find": "f(1)"},
            {"ruleId": "wide", "find": "f(1)\nf(22)"}, {"ruleId": "later", "find": "f(22)"}]
    rules = rules_json(*(simple_rule(item["ruleId"], fix=None) for item in spec))
    displayed = []
    for mutate in ("rows.reverse()", "rows[:] = rows[3:] + rows[:3]", ""):
        install_engine(tmp_path, monkeypatch, scanner(spec, mutate))
        rc, result = preview(monkeypatch, capsys, root, rules, extra=("--limit", "4"))
        assert rc == 0 and result["match_count"] == 10 and result["truncated"], result
        displayed.append(result["matches"])
    assert displayed[0] == displayed[1] == displayed[2]
    assert [(row["file"], row["ruleId"]) for row in displayed[0]] == [
        ("a.py", "a"), ("a.py", "z"), ("a.py", "wide"), ("a.py", "later"),
    ]


def test_real_engine_display_subset_is_stable_across_runs(real_engine, tmp_path, monkeypatch, capsys):
    source = workspace(tmp_path, {f"part{i:02}.py": "f(1)\nf(2)\n" for i in range(12)})
    displays = []
    for _ in range(3):
        rc, result = real_preview(monkeypatch, capsys, source, [simple_rule(fix=None)], extra=("--limit", "3"))
        assert rc == 0 and result["match_count"] == 24 and result["truncated"], result
        displays.append(result["matches"])
    assert displays[0] == displays[1] == displays[2]
    assert [(row["file"], row["text"]) for row in displays[0]] == [
        ("part00.py", "f(1)"), ("part00.py", "f(2)"), ("part01.py", "f(1)"),
    ]


def test_real_engine_ignore_comment_suppresses_and_is_noticed(real_engine, tmp_path, monkeypatch, capsys):
    """Suppression stays; native built-in suppression lints are not enabled or applied."""
    source = workspace(tmp_path, {"a.py": "# ast-grep-ignore\nf(1)\n", "b.py": "f(2)\n",
                                  "c.py": "# ast-grep-ignore: other-rule\nf(3)\n", "d.py": "f(4)  # ast-grep-ignore\n"})
    rc, result = real_preview(monkeypatch, capsys, source, [simple_rule("r", "f($X)", "h($X)")])
    assert rc == 0, result
    assert [entry["path"] for entry in result["files"]] == ["b.py", "c.py"]
    c_diff = result["files"][1]["diff"]
    assert " # ast-grep-ignore: other-rule\n" in c_diff and "-f(3)\n+h(3)\n" in c_diff
    assert {m["ruleId"] for m in result["matches"]} == {"r"}
    assert any(notice.startswith("3 copied file(s)") for notice in result["notices"])


def test_real_engine_workspace_and_temp_configs_are_not_loaded(real_engine, tmp_path, monkeypatch, capsys):
    planted = "ruleDirs:\n  - planted\nlanguageGlobs:\n  javascript: ['*.py']\n"
    source = workspace(tmp_path, {"sgconfig.yml": planted, "planted/p.yml":
                                  "id: planted-rule\nlanguage: python\nrule:\n  pattern: f($X)\n", "a.py": "f(1)\n"})
    temp_parent = tmp_path / "temp"
    temp_parent.mkdir()
    (temp_parent / "sgconfig.yml").write_text(planted)
    monkeypatch.setattr(tempfile, "tempdir", str(temp_parent))
    rc, result = real_preview(monkeypatch, capsys, source, [simple_rule("r", "f($X)", None)], "a.py")
    assert rc == 0 and [(m["file"], m["ruleId"]) for m in result["matches"]] == [("a.py", "r")]
    assert list(temp_parent.iterdir()) == [temp_parent / "sgconfig.yml"]


def test_real_engine_native_semantic_rejection_is_rc2(real_engine, tmp_path, monkeypatch, capsys):
    source = workspace(tmp_path, {"a.py": "f(1)\n"})
    for rules in ([{"id": "bad", "language": "python", "rule": {"kind": "no_such_kind_xyz"}}],
                  [{"id": "bad", "language": "nope-lang", "rule": {"pattern": "f($X)"}}]):
        rc, result = preview(monkeypatch, capsys, source, json.dumps(rules))
        assert rc == 2 and result["error"] == "engine_error" and result["detail"], result


def test_rule_tests_real_engine_contracts_and_no_snapshots(real_engine, tmp_path, monkeypatch, capsys):
    temp_parent = tmp_path / "temp"
    temp_parent.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp_parent))
    rules = [simple_rule("t-one", "old($X)", None), simple_rule("t-off", "off_api($X)", None, severity="off")]
    good = [{"id": "t-one", "valid": ["new(1)", "x = 1"], "invalid": ["old(1)"]},
            {"id": "t-off", "valid": ["nothing()"], "invalid": ["off_api(1)"]}]
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, rules, good)
    assert rc == 0 and result["cases_run"] == 5 and result["cases_passed"] == 5, result
    wrong_off = [good[0], {"id": "t-off", "valid": ["off_api(1)"], "invalid": ["nothing()"]}]
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, rules, wrong_off)
    assert rc == 1 and result["results"][1]["status"] == "FAIL", result  # --include-off reaches off rules
    assert result["results"][1]["valid"]["passed"] == 0 and result["results"][1]["invalid"]["passed"] == 0
    wrong_valid = [{"id": "t-one", "valid": ["old(2)"], "invalid": ["old(1)"]}, good[1]]
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, rules, wrong_valid)
    assert rc == 1 and result["cases_failed"] == 1
    special = [{"id": "t-one", "valid": ["s = '---'\r\n\tx = 'é'"], "invalid": ["old('\\n---\\n')"]}, good[1]]
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, rules, special)
    assert rc == 0, result
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path,
                               [{"id": "t-one", "language": "python", "rule": {"kind": "no_such_kind_xyz"}}, rules[1]],
                               good)
    assert rc == 2, result
    assert list(temp_parent.iterdir()) == []


def test_real_engine_plugin_tree_and_sources_unchanged(real_engine, tmp_path, monkeypatch, capsys):
    source = copy_fixture("py", tmp_path, "source")
    before, plugin, fixtures = tree_digest(source), tree_digest(TOOLS.parent), tree_digest(FIXTURES)
    rules = json.loads((FIXTURES / "rules/py-v2.json").read_text())
    assert real_preview(monkeypatch, capsys, source, rules, ".")[0] == 0
    assert tree_digest(source) == before and tree_digest(TOOLS.parent) == plugin
    assert tree_digest(FIXTURES) == fixtures


@pytest.mark.parametrize("builtin", sorted(code_intel_rules.RESERVED_RULE_IDS))
def test_real_engine_builtin_rule_id_collision_is_reserved(real_engine, tmp_path, monkeypatch, capsys, builtin):
    """Control: a caller id equal to a built-in enables that built-in under --hint=<id>."""
    source = workspace(tmp_path, {"a.py": "# ast-grep-ignore\nzz(1)\n# ast-grep-ignore: other\nq(2)\nf(3)\n"})
    config = tmp_path / "neutral" / "sgconfig.yml"
    config.parent.mkdir()
    config.write_text("ruleDirs: []\n")
    rule = simple_rule(builtin, "f($X)", None)
    native_rc, stdout, _ = run_bounded([real_engine, "scan", "--config", str(config),
                                        "--inline-rules=" + json.dumps(rule), f"--hint={builtin}", "--json=compact",
                                        "--", str(source)], cwd=config.parent)
    texts = {row["text"] for row in json.loads(stdout)}
    assert native_rc == 0 and "f(3)" in texts and any(text.startswith("# ast-grep-ignore") for text in texts)
    rc, result = preview(monkeypatch, capsys, source, json.dumps([rule]))
    assert rc == 2 and result["error"] == "reserved_rule_id"


@pytest.mark.parametrize("builtin", sorted(code_intel_rules.RESERVED_RULE_IDS))
def test_rule_tests_reserved_builtin_ids_rejected_before_engine(tmp_path, monkeypatch, capsys, builtin):
    marker = tmp_path / "engine-ran"
    install_engine(tmp_path, monkeypatch, f"Path({str(marker)!r}).touch()\n")
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, [simple_rule(builtin, fix=None)],
                               [{"id": builtin, "valid": ["g(1)"], "invalid": ["f(1)"]}])
    assert rc == 2 and result["error"] == "reserved_rule_id" and result["mode"] == "rule-test"
    assert not marker.exists()


def test_boundaries_replacement_offsets_must_not_split_utf8_beyond_display_limit(tmp_path, monkeypatch, capsys):
    """Text matches the bytes, but the replacement starts inside 'é'; the file is not displayed (--limit 1)."""
    mutate = ("for r in rows:\n"
              "    if r['text'] == 'é':\n"
              "        r['replacementOffsets']['start'] += 1\n")
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": "f(1)", "replace": "h(1)"},
                                                   {"ruleId": "r", "find": "é", "replace": "e"}], mutate))
    root = workspace(tmp_path, {"a.py": "f(1)\n", "b.py": "x = é\n"})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")), extra=("--limit", "1"))
    assert rc == 2 and result["error"] == "schema_mismatch", result


# ====================================================== review-fix regressions
# A. diff rendering: isolated child, LF-only lines, shared budget.
DIFF_CASES = {
    "formfeed": ("x = 1\f\nprint(x)\n", "x = 1\f\nlog(x)\n", "@@ -1,2 +1,2 @@\n x = 1\f\n-print(x)\n+log(x)\n"),
    "carriage-return": ("a\rb\nc\n", "a\rb\nd\n", "@@ -1,2 +1,2 @@\n a\rb\n-c\n+d\n"),
    "line-separator": ("s = 'a\u2028b'\nf(1)\n", "s = 'a\u2028b'\nh(1)\n",
                       "@@ -1,2 +1,2 @@\n s = 'a\u2028b'\n-f(1)\n+h(1)\n"),
    "no-final-newline": ("a\nf(1)", "a\nh(1)",
                         "@@ -1,2 +1,2 @@\n a\n-f(1)\n\\ No newline at end of file\n+h(1)\n\\ No newline at end of file\n"),
    "newline-added": ("a\nf(1)", "a\nh(1)\n", "@@ -1,2 +1,2 @@\n a\n-f(1)\n\\ No newline at end of file\n+h(1)\n"),
}


@pytest.mark.parametrize("case", sorted(DIFF_CASES))
def test_boundaries_diff_lines_split_on_lf_only(tmp_path, monkeypatch, capsys, case):
    before, after, hunk = DIFF_CASES[case]
    root = workspace(tmp_path, {"f.py": before})
    if case in ("formfeed", "carriage-return"):
        find, replace = ("print(x)", "log(x)") if case == "formfeed" else ("c\n", "d\n")
    else:
        find, replace = "f(1)", "h(1)" + ("\n" if case == "newline-added" else "")
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": find, "replace": replace}]))
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 0, result
    assert result["files"][0]["diff"] == f"--- a/f.py\n+++ b/f.py\n{hunk}"
    assert (root / "f.py").read_bytes() == before.encode()
    sha = hashlib.sha256(after.encode()).hexdigest()
    assert result["files"][0]["result_sha256"] == sha


def test_boundaries_diff_runs_in_isolated_child_from_plugin_tree(tmp_path, monkeypatch, capsys):
    calls = []
    original = code_intel_rules.ProcessBudget.run

    def spy(self, command, **kwargs):
        calls.append((list(map(str, command)), kwargs.get("cwd")))
        return original(self, command, **kwargs)

    monkeypatch.setattr(code_intel_rules.ProcessBudget, "run", spy)
    root = workspace(tmp_path, {"a.py": "f(1)\n",
                                # Planted stdlib shadows must not load in the helper.
                                "difflib.py": "raise SystemExit('planted difflib ran')\n",
                                "json.py": "raise SystemExit('planted json ran')\n"})
    monkeypatch.chdir(root)
    monkeypatch.setenv("PYTHONPATH", str(root))
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": "f(1)", "replace": "h(1)"}]))
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")), "a.py")
    assert rc == 0 and result["files"][0]["diff"].endswith("-f(1)\n+h(1)\n"), result
    helper = [(command, cwd) for command, cwd in calls if command[0] == sys.executable]
    assert len(helper) == 1
    command, cwd = helper[0]
    assert command[1:4] == ["-I", "-S", "-B"]
    assert Path(command[4]) == TOOLS / "code_intel_rules_diff.py" == code_intel_rules.DIFF_HELPER
    assert Path(cwd).resolve() != root.resolve() and root.resolve() not in Path(cwd).resolve().parents


def _swap_lines(count: int) -> tuple:
    lines = [f"line{i:07d}\n" for i in range(count)]
    swapped = [lines[i + 1 - 2 * (i % 2)] for i in range(count)]
    return "".join(lines).encode(), "".join(swapped).encode()


def test_boundaries_large_diff_hits_shared_deadline_without_partial(tmp_path):
    before, after = _swap_lines(20000)
    assert len(before) == 240000
    budget = code_intel_rules.ProcessBudget(1.0, 8 * 1024 * 1024)
    start = time.monotonic()
    with pytest.raises(code_intel_rules.RuleError) as raised:
        code_intel_rules.render_diffs(budget, tmp_path, [("big.py", before, after)])
    assert raised.value.code == "budget" and "no partial diff" in raised.value.reason
    assert time.monotonic() - start < 4


def test_boundaries_diff_output_counts_toward_shared_budget(tmp_path, monkeypatch, capsys):
    long_line = "f(1)" + "x" * 6000 + "\n"
    root = workspace(tmp_path, {"a.py": long_line})
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": "f(1)", "replace": "h(1)"}]))
    monkeypatch.setattr(code_intel, "MAX_OUTPUT_BYTES", 8000)
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "budget" and "output exceeded" in result["reason"], result
    assert "files" not in result


def test_boundaries_diff_helper_children_are_killed_on_deadline(tmp_path, monkeypatch, capsys):
    pidfile = tmp_path / "grandchild.pid"
    helper = external_dir(tmp_path) / "slow_diff.py"
    helper.write_text("import subprocess, sys, time\n"
                      "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                      f"open({str(pidfile)!r}, 'w').write(str(child.pid))\n"
                      "time.sleep(60)\n")
    monkeypatch.setattr(code_intel_rules, "DIFF_HELPER", helper)
    monkeypatch.setattr(code_intel, "QUERY_TIMEOUT", 3)
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": "f(1)", "replace": "h(1)"}]))
    start = time.monotonic()
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert time.monotonic() - start < 8
    assert rc == 2 and result["error"] == "budget" and "files" not in result, result
    time.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)


@pytest.mark.parametrize("output", ["", "{\"diffs\": [{\"path\": \"other.py\", \"diff\": \"\"}]}", "garbage"])
def test_boundaries_diff_helper_failure_is_rc2_without_partial(tmp_path, monkeypatch, capsys, output):
    helper = external_dir(tmp_path) / "bad_diff.py"
    helper.write_text(f"import sys\nsys.stdout.write({output!r})\n")
    monkeypatch.setattr(code_intel_rules, "DIFF_HELPER", helper)
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    install_engine(tmp_path, monkeypatch, scanner([{"ruleId": "r", "find": "f(1)", "replace": "h(1)"}]))
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "internal_error" and "files" not in result, result


# B. private copy writes/readback through pinned descriptors.
def _copy_tree(tmp_path):
    budget = code_intel_rules.ProcessBudget(30, 1024)
    tree = code_intel_rules.CopyTree(tmp_path / "tree", budget)
    tree.write("sub/a.py", b"f(1)\n", create=True)
    tree.write("b.py", b"f(2)\n", create=True)
    outside = tmp_path / "original"
    (outside / "sub").mkdir(parents=True)
    (outside / "sub/a.py").write_bytes(b"ORIGINAL\n")
    (outside / "b.py").write_bytes(b"ORIGINAL-B\n")
    return tree, outside


TAMPER = {
    "subdir-to-symlink": "shutil.rmtree(T / 'sub'); (T / 'sub').symlink_to(O / 'sub')",
    "subdir-replaced": "shutil.rmtree(T / 'sub'); (T / 'sub').mkdir(); (T / 'sub/a.py').write_bytes(b'f(1)\\n')",
    "file-replaced": "(T / 'b.py').unlink(); (T / 'b.py').write_bytes(b'f(2)\\n')",
    "file-hardlinked-to-original": "(T / 'b.py').unlink(); os.link(O / 'b.py', T / 'b.py')",
    "file-gains-outside-link": "os.link(T / 'b.py', O / 'b-link.py')",
    "file-to-symlink": "(T / 'b.py').unlink(); (T / 'b.py').symlink_to(O / 'b.py')",
    "file-truncated-in-place": "open(T / 'b.py', 'r+b').truncate(0)",
}


@pytest.mark.parametrize("case", sorted(TAMPER))
def test_boundaries_copy_tree_rejects_swapped_components_without_writing_through(tmp_path, case):
    tree, outside = _copy_tree(tmp_path)
    before = tree_digest(outside)
    held_inodes = []
    try:
        # Keep the original inode alive while replacing ordinary files/directories.
        # Otherwise Linux may immediately recycle the inode number and make this
        # identity test nondeterministic across filesystems.
        if case == "file-replaced":
            held_inodes.append(os.open(tree.path / "b.py", os.O_RDONLY))
        elif case == "subdir-replaced":
            held_inodes.append(os.open(tree.path / "sub", os.O_RDONLY))
        exec(TAMPER[case], {"T": tree.path, "O": outside, "os": os, "shutil": shutil})  # noqa: S102 - fixed test table
        current = {"sub/a.py": b"f(1)\n", "b.py": b"f(2)\n"}
        with pytest.raises(code_intel_rules.RuleError) as verified:
            tree.verify(current)
        assert verified.value.code == "copy_changed"
        target = "sub/a.py" if case.startswith("subdir") else "b.py"
        if case != "file-truncated-in-place":  # same private inode: rewriting it is legitimate
            with pytest.raises(code_intel_rules.RuleError) as written:
                tree.write(target, b"h(0)\n")
            assert written.value.code == "copy_changed"
        after = tree_digest(outside)
        after.pop("b-link.py", None)
        assert after == before  # never truncated or rewrote anything outside the copy
    finally:
        for fd in held_inodes:
            os.close(fd)
        tree.close()


def test_boundaries_copy_tree_root_swap_is_detected(tmp_path):
    tree, _ = _copy_tree(tmp_path)
    try:
        tree.path.rename(tmp_path / "moved")
        shutil.copytree(tmp_path / "moved", tree.path)
        with pytest.raises(code_intel_rules.RuleError) as raised:
            tree.verify({"sub/a.py": b"f(1)\n", "b.py": b"f(2)\n"})
        assert raised.value.code == "copy_changed"
    finally:
        tree.close()


def test_boundaries_copy_tree_readback_and_intact_verify(tmp_path):
    tree, _ = _copy_tree(tmp_path)
    try:
        tree.write("b.py", b"h(2)\n")
        tree.verify({"sub/a.py": b"f(1)\n", "b.py": b"h(2)\n"})
        assert stat.S_IMODE((tree.path / "b.py").stat().st_mode) == 0o600
        with pytest.raises(code_intel_rules.RuleError):
            tree.verify({"sub/a.py": b"f(1)\n", "b.py": b"f(2)\n"})
    finally:
        tree.close()


def test_boundaries_subdir_swapped_to_original_between_passes_is_rc2(tmp_path, monkeypatch, capsys):
    """Engine run 2 swaps copy dir 'sub' for a symlink to the ORIGINAL 'sub'; nothing may write through."""
    root = workspace(tmp_path, {"sub/a.py": "a\n", "top.py": "x\n"})
    before = tree_digest(root)
    counter = external_dir(tmp_path) / "calls"
    tamper = (f"calls = Path({str(counter)!r})\n"
              "n = int(calls.read_text()) + 1 if calls.exists() else 1\n"
              "calls.write_text(str(n))\n"
              "if n == 2:\n"
              "    import shutil\n"
              "    shutil.rmtree(tree / 'sub')\n"
              f"    (tree / 'sub').symlink_to(Path({str(root / 'sub')!r}))\n")
    install_engine(tmp_path, monkeypatch, scanner(
        [{"ruleId": "ab", "find": "a", "replace": "b"}, {"ruleId": "bc", "find": "b", "replace": "c"}],
        tamper))
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("ab"), simple_rule("bc")))
    assert rc == 2 and result["error"] == "copy_changed", result
    assert tree_digest(root) == before and (root / "sub/a.py").read_text() == "a\n"


def test_boundaries_copy_tampered_during_final_scan_is_not_a_clean_result(tmp_path, monkeypatch, capsys):
    """A copy truncated while the engine scans would otherwise read as rc0 no_match."""
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    install_engine(tmp_path, monkeypatch, scanner([], "open(tree / 'a.py', 'r+b').truncate(0)"))
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "copy_changed", result
    assert (root / "a.py").read_text() == "f(1)\n"


# C. non-UTF-8 names and unencodable output.
def test_boundaries_non_utf8_path_argument_and_root_are_rc2(tmp_path, monkeypatch, capsys):
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    install_engine(tmp_path, monkeypatch, "print('[]')\n")
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")), "caf\udce9.py")
    assert rc == 2 and result["error"] == "unsupported_file_name" and "\\udce9" in result["reason"], result
    rc, result = run_cli(monkeypatch, capsys, "--root", str(root) + "/x\udcff", "--rule-json",
                         rules_json(simple_rule("r")), ".")
    assert rc == 2 and result["error"] == "unsupported_file_name"


def test_boundaries_raw_byte_file_name_is_rc2(tmp_path, monkeypatch, capsys):
    root = workspace(tmp_path, {"sub/ok.py": "f(1)\n"})
    marker = tmp_path / "engine-ran"
    install_engine(tmp_path, monkeypatch, f"Path({str(marker)!r}).touch()\nprint('[]')\n")
    raw = os.fsencode(root / "sub") + b"/caf\xe9.py"
    try:
        os.close(os.open(raw, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    except OSError as exc:
        if sys.platform == "darwin":  # APFS: EILSEQ (EPERM under sandbox-exec); Linux must not skip
            pytest.skip(f"macOS cannot create non-UTF-8 file names (errno {exc.errno}); runs on Linux CI")
        raise
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")), "sub")
    assert rc == 2 and result["error"] == "unsupported_file_name", result
    assert "\\udce9" in result["reason"] and not marker.exists()


def test_boundaries_unencodable_success_and_error_results_stay_json_rc2(tmp_path, monkeypatch, capsys):
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    monkeypatch.setattr(code_intel_rules, "preview",
                        lambda *a: (0, {"status": "ok", "source_sha256": {"caf\udce9.py": "0" * 64}}))
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["status"] == "error" and result["error"] == "internal_error", result
    assert "source_sha256" not in result

    def broken(*_):
        raise code_intel_rules.RuleError("limit", "bad name caf\udcff.py", rc=3)

    monkeypatch.setattr(code_intel_rules, "preview", broken)
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "internal_error"
    monkeypatch.setattr(code_intel_rules, "preview", lambda *a: (_ for _ in ()).throw(OSError("x\udcff")))
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "io_error" and "\\udcff" in result["reason"]


def test_boundaries_unencodable_result_subprocess_has_no_traceback(tmp_path):
    """Real CLI process: a surrogate in an error reason yields JSON on stdout, nothing on stderr."""
    code = ("import sys\n"
            f"sys.path.insert(0, {str(TOOLS)!r})\n"
            "import code_intel, code_intel_rules\n"
            "def boom(*a):\n"
            "    raise code_intel_rules.RuleError('limit', 'caf\\udcff')\n"
            "code_intel_rules.parse_rules = boom\n"
            f"sys.argv = ['code_intel.py', '--root', {str(tmp_path)!r}, '--rule-json', '{{}}', '.']\n"
            "raise SystemExit(code_intel.main())\n")
    rc, stdout, stderr = run_bounded([sys.executable, "-B", "-c", code], cwd=tmp_path)
    assert rc == 2 and stderr == b"", stderr
    assert json.loads(stdout)["error"] == "internal_error"


# D. empty scan output.
@pytest.mark.parametrize("output", ["", "\n", "   "])
def test_boundaries_empty_scan_stdout_is_schema_mismatch(tmp_path, monkeypatch, capsys, output):
    install_engine(tmp_path, monkeypatch, f"sys.stdout.write({output!r})\n")
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "schema_mismatch", result
    install_engine(tmp_path, monkeypatch, "print('[]')\n")
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 0 and result["stop_reason"] == "no_match"


# ATK-006: exec argument size.
def test_boundaries_argument_limit_is_input_classified(tmp_path, monkeypatch, capsys):
    marker = tmp_path / "engine-ran"
    install_engine(tmp_path, monkeypatch, f"Path({str(marker)!r}).touch()\nprint('[]')\n")
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    monkeypatch.setattr(code_intel_rules, "_argument_limit", lambda: 64)
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "limit" and "argument limit" in result["reason"]
    assert not marker.exists()

    def e2big(self, command, **kwargs):
        if command[1:2] == ["scan"]:
            raise OSError(__import__("errno").E2BIG, "Argument list too long")
        return original(self, command, **kwargs)

    original = code_intel_rules.ProcessBudget.run
    monkeypatch.setattr(code_intel_rules, "_argument_limit", lambda: None)
    monkeypatch.setattr(code_intel_rules.ProcessBudget, "run", e2big)
    rc, result = preview(monkeypatch, capsys, root, rules_json(simple_rule("r")))
    assert rc == 2 and result["error"] == "limit", result


def test_boundaries_platform_argument_limit_with_policy_sized_rule(tmp_path, monkeypatch, capsys):
    """A <=64KiB emoji rule escapes to ~3x; Linux 4KiB pages cap one argv at 128KiB, macOS does not."""
    install_engine(tmp_path, monkeypatch, "print('[]')\n")
    root = workspace(tmp_path, {"a.py": "f(1)\n"})
    rule = json.dumps([simple_rule("r", message="\U0001f680" * 16000)], ensure_ascii=False)
    assert len(rule.encode()) <= code_intel_rules.MAX_RULE_BYTES
    limit = code_intel_rules._argument_limit()
    rc, result = preview(monkeypatch, capsys, root, rule)
    if limit is not None and limit < 3 * 64000:
        assert rc == 2 and result["error"] == "limit", result
    else:
        assert rc == 0 and result["stop_reason"] == "no_match", result


# ATK-008: the marker is a line start, not an echoed snippet.
def test_rule_tests_echoed_snippet_text_is_not_a_skip_marker(tmp_path, monkeypatch, capsys):
    rule_test_engine(tmp_path, monkeypatch,
                     "Running 2 tests\n\n----------- Case Details -----------\n[Noisy] Expect t-two to report no "
                     "issue, but some issues found in:\n\n  Configuration not found! f(1)\n\nPASS t-one  ...\n"
                     "FAIL t-two  N.\n\n\n", "Error: test failed. 1 passed; 1 failed;\n", rc=4)
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, TWO_RULES, TWO_TESTS)
    assert rc == 1 and result["status"] == "failed", result


# E. real engine: emoji / DEL / U+2028 in patterns, fixes and snippets.
UNICODE_RULES = [
    simple_rule("emoji", 'print("\U0001f680")', 'log("\U0001f680\u2705")', message="\U0001f680 note"),
    simple_rule("del", 'print("a\x7fb")', 'log("a\x7fb")', note="del \x7f note"),
    simple_rule("lsep", 'print("a\u2028b")', 'log("a\u2028b")', message="line\u2028sep"),
]
UNICODE_SOURCE = 'print("\U0001f680")\nprint("a\x7fb")\nprint("a\u2028b")\nprint("plain")\n'


def test_real_engine_unicode_rules_preview_matches_native(real_engine, tmp_path, monkeypatch, capsys):
    source = workspace(tmp_path, {"u.py": UNICODE_SOURCE})
    rc, result = real_preview(monkeypatch, capsys, source, UNICODE_RULES)
    assert rc == 0 and result["changed_passes"] == 1 and result["match_count"] == 3, result
    assert result["files"][0]["diff"] == (
        "--- a/u.py\n+++ b/u.py\n@@ -1,4 +1,4 @@\n"
        '-print("\U0001f680")\n-print("a\x7fb")\n-print("a\u2028b")\n'
        '+log("\U0001f680\u2705")\n+log("a\x7fb")\n+log("a\u2028b")\n print("plain")\n')
    native = tmp_path / "native"
    shutil.copytree(source, native)
    native_fixed_point(real_engine, UNICODE_RULES, native, tmp_path / "scratch")
    assert_preview_matches_native(result, source, native)


def test_rule_tests_real_engine_unicode_snippets(real_engine, tmp_path, monkeypatch, capsys):
    tests = [{"id": "emoji", "valid": ['print("x")', 'print("\U0001f680\u2705")'], "invalid": ['print("\U0001f680")']},
             {"id": "del", "valid": ['print("ab")'], "invalid": ['print("a\x7fb")']},
             {"id": "lsep", "valid": ['print("a b")'], "invalid": ['print("a\u2028b")']}]
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, UNICODE_RULES, tests)
    assert rc == 0 and result["cases_run"] == 7 and result["cases_passed"] == 7, result
    wrong = [{**tests[0], "valid": ['print("\U0001f680")'], "invalid": ['print("x")']}, *tests[1:]]
    rc, result = rule_test_cli(monkeypatch, capsys, tmp_path, UNICODE_RULES, wrong)
    assert rc == 1 and result["results"][0]["status"] == "FAIL", result
