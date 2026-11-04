from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
import code_intel


def query_args(tmp_path, **kwargs):
    values = {"root": str(tmp_path), "paths": ["."], "pattern": "f($A)", "lang": "c", "rewrite": None, "limit": 5}
    values.update(kwargs)
    return argparse.Namespace(**values)


@pytest.mark.skipif(not shutil.which("ast-grep"), reason="optional ast-grep binary")
@pytest.mark.parametrize(("lang", "filename", "source", "pattern", "rewrite"), [
    ("python", "example.py", "def greet(name):\n    print(name)\n", "print($A)", "log($A)"),
    ("python", "example.py", "def greet(name):\n    print(name)\n",
     "def $F($$$ARGS):\n    $$$BODY", "def $F($$$ARGS):\n    pass"),
    ("go", "example.go", "package main\nfunc greet(name string) { println(name) }\n",
     "println($A)", "log($A)"),
    ("typescript", "example.ts", "function greet(name: string) { console.log(name); }\n",
     "console.log($A)", "console.warn($A)"),
])
def test_real_metavariables_search_and_preview(tmp_path, capsys, lang, filename, source, pattern, rewrite):
    file = tmp_path / filename
    file.write_text(source)
    args = query_args(tmp_path, paths=[filename], pattern=pattern, lang=lang)
    for replacement in (None, rewrite):
        args.rewrite = replacement
        assert code_intel.query(args) == 0
        result = json.loads(capsys.readouterr().out)
        assert result["match_count"] == 1
        assert result["mode"] == ("search" if replacement is None else "preview")
        if replacement is not None:
            assert result["matches"][0]["replacement"]
        assert file.read_text() == source


@pytest.mark.parametrize("stage", ["version", "preflight", "query"])
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_output_limit_stops_engine_while_running(tmp_path, monkeypatch, capsys, stage, stream):
    engine = tmp_path / "engine"
    finished = tmp_path / "finished"
    engine.write_text(
        f"#!{sys.executable} -B\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "stage = 'version' if '--version' in sys.argv else 'preflight' if '--stdin' in sys.argv else 'query'\n"
        f"if stage == {stage!r}:\n"
        f"    for _ in range(512): os.write({1 if stream == 'stdout' else 2}, b'x' * 4096)\n"
        f"    Path({str(finished)!r}).touch()\n"
        "elif stage == 'version': print('ast-grep 0.51.0')\n"
        "elif stage == 'query': print('[]')\n"
    )
    engine.chmod(0o700)
    monkeypatch.setattr(code_intel.shutil, "which", lambda name: str(engine))
    monkeypatch.setattr(code_intel, "MAX_OUTPUT_BYTES", 1024)
    monkeypatch.setattr(sys, "argv", ["code_intel.py", "--root", str(tmp_path), "--lang", "c", "--pattern", "f($A)", "."])
    assert code_intel.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert "output" in result["reason"].lower()
    assert not finished.exists(), "engine finished writing before the limit was enforced"


def fake_engine(tmp_path, monkeypatch, program):
    engine = tmp_path / "engine"
    engine.write_text(f"#!{sys.executable} -B\n" + program)
    engine.chmod(0o700)
    monkeypatch.setattr(code_intel.shutil, "which", lambda name: str(engine))
    monkeypatch.setattr(sys, "argv", ["code_intel.py", "--root", str(tmp_path), "--lang", "c", "--pattern", "f($A)", "."])


@pytest.mark.parametrize("stage", ["version", "preflight", "query"])
def test_each_stage_has_a_deadline_and_json_error(tmp_path, monkeypatch, capsys, stage):
    pidfile = tmp_path / "engine.pid"
    fake_engine(tmp_path, monkeypatch,
                "import os, sys, time\n"
                "from pathlib import Path\n"
                "stage = 'version' if '--version' in sys.argv else 'preflight' if '--stdin' in sys.argv else 'query'\n"
                f"if stage == {stage!r}:\n"
                f"    Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
                "    time.sleep(60)\n"
                "elif stage == 'version': print('ast-grep 0.51.0')\n"
                "elif stage == 'query': print('[]')\n")
    # Newly created executable scripts can incur macOS launch inspection.
    # Leave startup room while still bounding the engine's 60-second sleep.
    monkeypatch.setattr(code_intel, "QUERY_TIMEOUT", 3)
    monkeypatch.setattr(code_intel, "PROBE_TIMEOUT", 1)
    start = time.monotonic()
    assert code_intel.main() == 2
    assert time.monotonic() - start < 5
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error" and "timed out" in result["reason"]
    assert pidfile.exists(), result
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)


@pytest.mark.parametrize("stage", ["version", "preflight", "query"])
def test_combined_stream_budget_in_every_stage(tmp_path, monkeypatch, capsys, stage):
    fake_engine(tmp_path, monkeypatch,
                "import os, sys, threading\n"
                "stage = 'version' if '--version' in sys.argv else 'preflight' if '--stdin' in sys.argv else 'query'\n"
                f"if stage == {stage!r}:\n"
                "    t = threading.Thread(target=lambda: os.write(2, b'e' * 600))\n"
                "    t.start()\n"
                "    os.write(1, b'o' * 600)\n"
                "    t.join()\n"
                "elif stage == 'version': print('ast-grep 0.51.0')\n"
                "elif stage == 'query': print('[]')\n")
    monkeypatch.setattr(code_intel, "MAX_OUTPUT_BYTES", 1000)
    assert code_intel.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error" and "output exceeded" in result["reason"]


def test_budget_is_shared_across_version_preflight_and_query(tmp_path, monkeypatch, capsys):
    fake_engine(tmp_path, monkeypatch,
                "import os, sys\n"
                "if '--version' in sys.argv: print('ast-grep 0.51.0')\n"
                "elif '--stdin' in sys.argv: os.write(2, b'p' * 600)\n"
                "else: os.write(2, b'q' * 600); print('[]')\n")
    monkeypatch.setattr(code_intel, "MAX_OUTPUT_BYTES", 1000)
    assert code_intel.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error" and "output exceeded" in result["reason"]


@pytest.mark.parametrize(("native_rc", "diagnostic", "reason"), [
    (2, "Error: Cannot parse pattern", "Pattern compilation failed"),
    (0, code_intel.INVALID_PATTERN_WARNING.decode(), "Engine reported an invalid pattern"),
])
def test_native_pattern_failures_remain_distinct(tmp_path, monkeypatch, capsys, native_rc, diagnostic, reason):
    fake_engine(tmp_path, monkeypatch,
                "import sys\n"
                "if '--version' in sys.argv: print('ast-grep 0.51.0')\n"
                "elif '--stdin' in sys.argv:\n"
                f"    print({diagnostic!r}, file=sys.stderr)\n"
                f"    sys.exit({native_rc})\n"
                "else: raise RuntimeError('query must not run')\n")
    assert code_intel.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error" and result["reason"] == reason


def test_incidental_error_text_is_not_a_pattern_rejection(tmp_path, monkeypatch, capsys):
    fake_engine(tmp_path, monkeypatch,
                "import sys\n"
                "assert '--debug-query=ast' not in sys.argv\n"
                "if '--version' in sys.argv: print('ast-grep 0.51.0')\n"
                "elif '--stdin' in sys.argv: print('  ERROR from unrelated debug text', file=sys.stderr); sys.exit(1)\n"
                "else: print('[]'); sys.exit(1)\n")
    assert code_intel.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ok" and result["match_count"] == 0


def test_cli_missing_binary_is_rc3(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(code_intel.shutil, "which", lambda name: None)
    monkeypatch.setattr(sys, "argv", ["code_intel.py", "--root", str(tmp_path), "--lang", "c", "--pattern", "f($A)", "."])
    assert code_intel.main() == 3
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "unavailable"
    assert "untrusted" in result["notice"].lower()


def test_query_rejects_path_escape(tmp_path):
    workspace = tmp_path / "work"
    workspace.mkdir()
    outside = tmp_path / "secret.c"
    outside.write_text("secret")
    (workspace / "link.c").symlink_to(outside)
    for value in ("../secret.c", str(outside), "link.c"):
        with pytest.raises(ValueError, match="escapes"):
            code_intel.contained_path(workspace, value)


def test_linux_sg_is_not_accepted(monkeypatch):
    monkeypatch.setattr(code_intel.shutil, "which", lambda name: "/usr/bin/sg" if name == "sg" else None)
    monkeypatch.setattr(code_intel.ProcessBudget, "run", lambda *a, **kw:
                        argparse.Namespace(returncode=0, stdout=b"sg from util-linux\n"))
    assert code_intel.find_ast_grep() is None


def test_sg_is_never_probed(monkeypatch):
    calls = []
    monkeypatch.setattr(code_intel.shutil, "which", lambda name: "/usr/bin/sg" if name == "sg" else None)
    def probe(*args, **kwargs):
        calls.append(args)
        return argparse.Namespace(returncode=0, stdout=b"sg from util-linux\n")

    monkeypatch.setattr(code_intel.ProcessBudget, "run", probe)
    assert code_intel.find_ast_grep() is None
    assert calls == []


@pytest.mark.parametrize("version,matches,expected", [("0.51.0", False, 0), ("0.52.0", False, 2),
                                                      ("0.52.0", True, 0)])
def test_pattern_validation_is_version_scoped(tmp_path, monkeypatch, capsys, version, matches, expected):
    source = tmp_path / "example.c"
    source.write_text("f(x);\n")
    rows = [{"file": str(source)}] if matches else []
    fake_engine(tmp_path, monkeypatch,
                "import sys\n"
                f"if '--version' in sys.argv: print('ast-grep {version}')\n"
                "elif '--stdin' in sys.argv: pass\n"
                f"else: print({json.dumps(rows)!r})\n")
    assert code_intel.main() == expected
    result = json.loads(capsys.readouterr().out)
    assert result["pattern_validated"] is (version == "0.51.0")
    assert result["status"] == ("unverified" if expected == 2 else "ok")
    assert "untrusted" in result["notice"].lower()


@pytest.mark.parametrize("version", ["ast-grep 0.51.0 extra", "ast-grep 0.51.0\nmalicious", "ast-grep 0.51", "ast-grep 0.51.0 "])
def test_version_output_is_strict(tmp_path, monkeypatch, capsys, version):
    fake_engine(tmp_path, monkeypatch, f"print({version!r})\n")
    assert code_intel.main() == 3
    result = json.loads(capsys.readouterr().out)
    assert result["pattern_validated"] is False
    assert "untrusted" in result["notice"].lower()


def test_engine_runs_with_neutral_cwd_and_explicit_config(tmp_path, monkeypatch, capsys):
    fake_engine(tmp_path, monkeypatch,
                "import os, sys\n"
                "from pathlib import Path\n"
                f"assert Path.cwd() != Path({str(tmp_path)!r})\n"
                "if '--version' in sys.argv: print('ast-grep 0.51.0')\n"
                "else:\n"
                "    config = Path(sys.argv[sys.argv.index('--config') + 1])\n"
                "    assert config.is_absolute() and config.read_text().strip() == 'ruleDirs: []'\n"
                "    if '--stdin' not in sys.argv:\n"
                "        assert all(Path(p).is_absolute() for p in sys.argv[sys.argv.index('--') + 1:])\n"
                "        print('[]')\n")
    assert code_intel.main() == 0
    assert json.loads(capsys.readouterr().out)["pattern_validated"] is True


@pytest.mark.skipif(not shutil.which("ast-grep"), reason="optional ast-grep binary")
def test_real_workspace_and_temp_ancestor_configs_are_ignored(tmp_path, monkeypatch, capsys):
    import tempfile

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "example.py").write_text("print('hello')\n")
    for parent in (tmp_path, workspace):
        (parent / "sgconfig.yml").write_text("[invalid yaml config")
    neutral_parent = tmp_path / "temp"
    neutral_parent.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(neutral_parent))
    assert code_intel.query(query_args(workspace, lang="python", pattern="print($A)")) == 0
    assert json.loads(capsys.readouterr().out)["match_count"] == 1


def test_missing_binary_reports_unavailable(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(code_intel, "find_ast_grep", lambda budget, **kwargs: None)
    args = argparse.Namespace(root=str(tmp_path), paths=["."], pattern="f($A)", lang="c", rewrite=None, limit=5)
    assert code_intel.query(args) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "unavailable"


@pytest.mark.skipif(not shutil.which("ast-grep"), reason="optional ast-grep binary")
def test_real_ast_search_and_preview_are_read_only(tmp_path, capsys):
    source = tmp_path / "example.c"
    original = "int f(void) { puts(\"one\"); puts(\"two\"); return 0; }\n"
    source.write_text(original)
    args = argparse.Namespace(root=str(tmp_path), paths=["example.c"], pattern="puts($A);",
                              lang="c", rewrite=None, limit=1)
    assert code_intel.query(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["match_count"] == 2 and result["file_count"] == 1
    assert result["truncated"] and len(result["matches"]) == 1
    args.rewrite = "log($A);"
    assert code_intel.query(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "preview" and result["matches"][0]["replacement"] == 'log("one");'
    assert source.read_text() == original


@pytest.mark.skipif(not shutil.which("ast-grep"), reason="optional ast-grep binary")
def test_real_ast_bad_pattern_is_not_a_clean_result(tmp_path, capsys):
    (tmp_path / "example.c").write_text("int x;\n")
    args = argparse.Namespace(root=str(tmp_path), paths=["example.c"], pattern="\\w+",
                              lang="c", rewrite=None, limit=5)
    assert code_intel.query(args) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"


@pytest.mark.skipif(not shutil.which("ast-grep"), reason="optional ast-grep binary")
def test_real_native_compile_failure_is_rc2(tmp_path, capsys):
    (tmp_path / "example.py").write_text("print('hello')\n")
    args = query_args(tmp_path, paths=["example.py"], lang="python", pattern="print($A); print($B)")
    assert code_intel.query(args) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error" and result["reason"] == "Pattern compilation failed"
    assert "Cannot parse query" in result["detail"]


def test_ast_error_has_notice(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["code_intel.py", "--root", str(tmp_path / "missing"),
                                     "--lang", "c", "--pattern", "f($A)", "."])
    assert code_intel.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert "untrusted" in result["notice"].lower()
