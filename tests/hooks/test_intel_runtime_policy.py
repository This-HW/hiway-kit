"""Review4 regressions: launch policy, pinned multicall dispatch and cleanup."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
import code_intel
import intel_runtime
import lsp_query
import lsp_transport


def script(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o700)
    return path


def cli(monkeypatch, root, *extra):
    (root / "example.py").write_text("x  =  1\n")
    monkeypatch.setattr(sys, "argv", ["lsp_query", "symbols", "--root", str(root),
                                     "--file", "example.py", *extra])
    return lsp_query.main()


@pytest.mark.parametrize("entry", ["absolute", "relative", "empty", "symlink"])
@pytest.mark.parametrize("opt_in", [False, True])
def test_p1_child_path_cannot_launch_workspace_node(tmp_path, monkeypatch, entry, opt_in):
    root = tmp_path / "workspace"
    root.mkdir()
    marker = root / "node-ran"
    external_marker = tmp_path / "external-ran"
    external = tmp_path / "external"
    script(external / "pyright-langserver", "#!/usr/bin/env node\n")
    script(root / "node", f"#!/bin/sh\ntouch '{marker}'\n")
    script(external / "node", f"#!/bin/sh\ntouch '{external_marker}'\n")
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    entry_value = {"absolute": str(root), "relative": ".", "empty": "", "symlink": str(alias)}[entry]
    monkeypatch.chdir(root)
    monkeypatch.setenv("PATH", os.pathsep.join([entry_value, str(external), "/usr/bin", "/bin"]))
    rc = cli(monkeypatch, root, "--server", "pyright-langserver",
             *(["--allow-custom-server"] if opt_in else []))
    assert rc == 2  # Synthetic node exits without an LSP response.
    assert marker.exists() is opt_in
    assert external_marker.exists() is (not opt_in)


@pytest.mark.parametrize("name", ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_PROJECT", "CARGO_HTTP_CREDENTIAL",
                                  "CARGO_Registry_Token", "CARGO_BUILD_RUSTC_WRAPPER",
                                  "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER", "CARGO_TARGET_X_RUNNER",
                                  "CARGO_TARGET_X_LINKER", "RUSTC_WRAPPER"])
def test_p2_denials_precede_namespace_allowances(monkeypatch, name):
    monkeypatch.setenv(name, "fixture")
    assert not intel_runtime.allowed_environment_name(name)
    assert name not in intel_runtime.child_environment()


def test_p2_toolchain_configuration_remains_supported(monkeypatch):
    for name in ("GOPROXY", "GOFLAGS", "GOPRIVATE", "CPATH"):
        monkeypatch.setenv(name, "fixture")
    monkeypatch.setenv("GOTOOLCHAIN", "auto")
    env = intel_runtime.child_environment()
    assert all(env[name] == "fixture" for name in ("GOPROXY", "GOFLAGS", "GOPRIVATE", "CPATH"))
    assert env["GOTOOLCHAIN"] == "local"


@pytest.fixture
def multicall(tmp_path):
    compiler = shutil.which("clang")
    if compiler is None:
        pytest.skip("native multicall fixture requires clang")
    marker = tmp_path / "argv0"
    source = tmp_path / "shim.c"
    source.write_text('''#include <stdio.h>
#include <string.h>
#include <unistd.h>
int main(int argc, char **argv) {
 FILE *f = fopen(MARKER, "w");
 const char *name = strrchr(argv[0], '/');
 fprintf(f, "%s", name ? name + 1 : argv[0]); fclose(f);
 if (argc > 1 && strcmp(argv[1], "--version") == 0) puts("ast-grep 0.51.0");
 else if (argc > 1 && strcmp(argv[1], "run") == 0) puts("[]");
 else { const char *r = "{\\"jsonrpc\\":\\"2.0\\",\\"id\\":1,\\"result\\":[]}";
 printf("Content-Length: %zu\\r\\n\\r\\n%s", strlen(r), r); fflush(stdout); usleep(100000); }
 return 0;
}
''')
    target = tmp_path / "real" / "shim"
    target.parent.mkdir()
    subprocess.run([compiler, '-DMARKER=' + json.dumps(str(marker)), str(source), "-o", str(target)],
                   cwd=tmp_path, capture_output=True, check=True)
    return target, marker


@pytest.mark.parametrize("engine", ["clangd", "ast-grep"])
def test_p3_native_multicall_preserves_argv0(tmp_path, monkeypatch, multicall, engine):
    target, marker = multicall
    bindir = tmp_path / "bin"
    bindir.mkdir()
    alias = bindir / engine
    alias.symlink_to(target)
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("PATH", str(bindir))
    calls = []
    popen = subprocess.Popen

    def record(*args, **kwargs):
        calls.append(kwargs.get("executable"))
        return popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", record)
    if engine == "clangd":
        command = lsp_query.select_server("c", None, root=root)
        connection = lsp_transport.Connection(command, str(root))
        try:
            assert connection.request("initialize", {}) == []
        finally:
            connection.close()
    else:
        code_intel.query(argparse.Namespace(root=str(root), paths=["."], lang="c", pattern="f($A)", rewrite=None, limit=5))
    assert marker.read_text() == engine
    assert calls == [str(target)] * (3 if engine == "ast-grep" else 1)


@pytest.mark.parametrize("engine", ["clangd", "ast-grep"])
def test_p3_resolved_once_path_is_popen_executable(tmp_path, monkeypatch, multicall, engine):
    target, marker = multicall
    root = tmp_path / "workspace"
    root.mkdir()
    alias = tmp_path / engine
    alias.symlink_to(target)
    monkeypatch.setattr(shutil, "which", lambda name: str(alias))
    resolve = Path.resolve
    seen = []

    def once(path, *args, **kwargs):
        if path == alias:
            seen.append(path)
            assert len(seen) == 1
            fixed = resolve(path, *args, **kwargs)
            # Swap the symlink after pinning; the actual launch must use fixed.
            alias.unlink()
            alias.symlink_to("/usr/bin/false")
            return fixed
        return resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", once)
    if engine == "clangd":
        command = lsp_query.select_server("c", str(alias), root=root)
        connection = lsp_transport.Connection(command, str(root))
        try:
            assert connection.request("initialize", {}) == []
        finally:
            connection.close()
    else:
        assert code_intel.query(argparse.Namespace(root=str(root), paths=["."], lang="c", pattern="f($A)", rewrite=None, limit=5)) == 0
    assert marker.read_text() == engine
    assert len(seen) == 1


@pytest.mark.parametrize("actual", [False, True])
def test_p4_server_args_require_opt_in_before_launch(tmp_path, monkeypatch, capsys, actual):
    root = tmp_path / "workspace"
    root.mkdir()
    marker = tmp_path / "launched"
    if actual:
        installed = shutil.which("ruff")
        if installed is None:
            pytest.skip("optional installed ruff")
    else:
        installed = str(script(tmp_path / "external" / "ruff", f"#!/bin/sh\ntouch '{marker}'\n"))
    monkeypatch.setenv("PATH", str(Path(installed).parent) + ":/usr/bin:/bin")
    assert cli(monkeypatch, root, "--server", "ruff", "--server-arg=format", "--server-arg=example.py") == 2
    result = json.loads(capsys.readouterr().out)
    assert "allow-custom-server" in result["reason"]
    assert not marker.exists()
    assert (root / "example.py").read_text() == "x  =  1\n"


@pytest.mark.parametrize("name,defaults", [("ruff", ["server"]), ("clangd", ["--background-index=false", "--log=error"]),
                                           ("pyright-langserver", ["--stdio"]), ("typescript-language-server", ["--stdio"])])
def test_p4_explicit_known_server_receives_defaults(tmp_path, monkeypatch, name, defaults):
    (tmp_path / "workspace").mkdir()
    binary = script(tmp_path / "external" / name, "#!/bin/sh\nexit 0\n")
    monkeypatch.setenv("PATH", str(binary.parent))
    for explicit in (name, str(binary)):
        assert lsp_query.select_server("c", explicit, root=tmp_path / "workspace")[1:] == defaults


@pytest.mark.parametrize("link", [False, True])
def test_p8_workspace_ast_rejected_before_version(tmp_path, monkeypatch, capsys, link):
    root = tmp_path / "workspace"
    root.mkdir()
    marker = tmp_path / "ast-launched"
    engine = script(root / "bin" / "ast-grep", f"#!/bin/sh\ntouch '{marker}'\necho ast-grep 0.51.0\n")
    if link:
        alias = tmp_path / "external" / "ast-grep"
        alias.parent.mkdir()
        alias.symlink_to(engine)
        engine = alias
    monkeypatch.setenv("PATH", str(engine.parent) + ":/usr/bin:/bin")
    monkeypatch.setattr(sys, "argv", ["code_intel", "--root", str(root), "--lang", "c", "--pattern", "f($A)", "."])
    assert code_intel.main() == 2
    assert "Workspace" in json.loads(capsys.readouterr().out)["reason"]
    assert not marker.exists()


def test_p3_python39_style_symlink_loop_is_json_error(tmp_path, monkeypatch, capsys):
    (tmp_path / "example.py").write_text("x = 1\n")
    binary = tmp_path / "clangd"
    monkeypatch.setattr(shutil, "which", lambda name: str(binary))
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == binary:
            raise RuntimeError("Symlink loop from Python 3.9")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    assert cli(monkeypatch, tmp_path, "--server", "clangd") == 2
    assert json.loads(capsys.readouterr().out)["status"] == "error"


@pytest.mark.parametrize("initial", [False, True])
def test_close_reaped_eperm_does_not_mask_result(monkeypatch, initial):
    connection = lsp_transport.Connection.__new__(lsp_transport.Connection)
    connection.process = Mock(pid=123, stdin=Mock(), stdout=Mock())
    connection.process.poll.return_value = 0
    connection.reader = Mock()
    killpg = Mock(side_effect=PermissionError("exited group"))
    if not initial:
        killpg.side_effect = [None, PermissionError("exited group"), PermissionError("exited group")]
    monkeypatch.setattr(os, "killpg", killpg)
    connection.close()
    assert killpg.call_count >= 2
    connection.process.stdin.close.assert_called_once()
    connection.process.stdout.close.assert_called_once()
    connection.reader.join.assert_called_once()


def test_close_live_eperm_is_reported_and_streams_closed(monkeypatch):
    connection = lsp_transport.Connection.__new__(lsp_transport.Connection)
    connection.process = Mock(pid=123, stdin=Mock(), stdout=Mock())
    connection.process.poll.return_value = None
    connection.process.wait.side_effect = subprocess.TimeoutExpired("server", .05)
    connection.reader = Mock()
    monkeypatch.setattr(os, "killpg", Mock(side_effect=PermissionError("live denial")))
    with pytest.raises(PermissionError, match="live denial"):
        connection.close()
    connection.process.stdin.close.assert_called_once()
    connection.process.stdout.close.assert_called_once()


@pytest.mark.parametrize("value", ["", ".", "workspace"])
def test_p1_empty_filtered_path_does_not_fall_back_to_cwd(tmp_path, monkeypatch, value):
    root = tmp_path / "workspace"
    root.mkdir()
    marker = root / "node-ran"
    server = script(tmp_path / "external" / "pyright-langserver", "#!/usr/bin/env node\n")
    script(root / "node", f"#!/bin/sh\n/usr/bin/touch '{marker}'\n")
    monkeypatch.chdir(root)
    monkeypatch.setenv("PATH", value)
    connection = lsp_transport.Connection([str(server)], str(root))
    try:
        with pytest.raises(lsp_transport.LspError):
            connection.request("initialize", {})
    finally:
        connection.close()
    assert not marker.exists()


def test_p1_ast_uses_same_child_path_filter(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    marker = root / "node-ran"
    external = tmp_path / "external"
    server = script(external / "ast-grep", "#!/usr/bin/env node\n")
    script(root / "node", f"#!/bin/sh\n/usr/bin/touch '{marker}'\necho ast-grep 0.51.0\n")
    script(external / "node", "#!/bin/sh\necho ast-grep 0.51.0\n")
    monkeypatch.setenv("PATH", str(root) + ":" + str(external))
    monkeypatch.chdir(root)
    # Query's budget must carry the workspace root into every engine stage.
    args = argparse.Namespace(root=str(root), paths=["."], lang="c", pattern="f($A)", rewrite=None, limit=5)
    with pytest.raises(ValueError):  # Synthetic node returns version text for query JSON too.
        code_intel.query(args)
    assert server.exists() and not marker.exists()


@pytest.mark.parametrize("module", [code_intel, lsp_query])
def test_p9_cli_help_qualifies_engine_trust(module, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [module.__name__, "--help"])
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "trusted" in help_text
    assert "not sandboxed" in help_text


@pytest.mark.skipif(not shutil.which("ruff"), reason="optional installed Ruff server")
def test_p4_real_ruff_defaults_work_without_argument_override(tmp_path, monkeypatch, capsys):
    source = tmp_path / "example.py"
    for text, expected in (("x = 1\n", 0), ("def broken(:\n", 1)):
        source.write_text(text)
        monkeypatch.setattr(sys, "argv", ["lsp_query", "diagnostics", "--root", str(tmp_path),
                                         "--file", source.name, "--server", "ruff"])
        assert lsp_query.main() == expected
        result = json.loads(capsys.readouterr().out)
        assert result["complete"] is True
        assert bool(result["result"]) is bool(expected)
        assert source.read_text() == text


def test_p4_opted_in_arguments_append_to_known_defaults(tmp_path, monkeypatch, capsys):
    binary = script(tmp_path / "external" / "ruff", "#!/bin/sh\nexit 0\n")
    marker = tmp_path / "argv"
    binary.write_text(f"#!{sys.executable} -B\nimport json,sys\nfrom pathlib import Path\nPath({str(marker)!r}).write_text(json.dumps(sys.argv[1:]))\n")
    monkeypatch.setenv("PATH", str(binary.parent))
    root = tmp_path / "workspace"
    root.mkdir()
    assert cli(monkeypatch, root, "--server", "ruff", "--allow-custom-server", "--server-arg=--fixture") == 2
    assert json.loads(marker.read_text()) == ["server", "--fixture"]
    capsys.readouterr()
