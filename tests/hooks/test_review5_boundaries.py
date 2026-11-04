"""Q regressions: real case aliases on APFS plus identity controls on every FS."""
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
import code_intel
import install_doctor
import intel_runtime
import lsp_query
import lsp_transport
import session_history


def script(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o700)
    return path


@pytest.mark.parametrize("mode", ["node", "ast", "lsp"])
@pytest.mark.parametrize("case_alias", [False, True])
def test_workspace_alias_never_executes(tmp_path, monkeypatch, capsys, mode, case_alias):
    root = tmp_path / "Workspace"
    root.mkdir()
    selected = tmp_path / "WORKSPACE" if case_alias else root
    if not selected.exists() or not selected.samefile(root):
        pytest.skip("Distinct-case FS: identity policy is covered by mocked alias tests")
    (root / "example.py").write_text("x = 1\n")
    marker, safe_marker = tmp_path / "workspace-ran", tmp_path / "external-ran"
    external = tmp_path / "external"
    external.mkdir()
    name = {"node": "node", "ast": "ast-grep", "lsp": "clangd"}[mode]
    script(root / "tools" / name, f"#!/bin/sh\n/usr/bin/touch '{marker}'\necho ast-grep 0.51.0\n")
    monkeypatch.setenv("PATH", str(root / "tools") + ":" + str(external) + ":/usr/bin:/bin")
    if mode == "node":
        script(external / "pyright-langserver", "#!/usr/bin/env node\n")
        script(external / "node", f"#!/bin/sh\n/usr/bin/touch '{safe_marker}'\n")
    if mode == "ast":
        monkeypatch.setattr(sys, "argv", ["code_intel", "--root", str(selected), "--lang", "python",
                                         "--pattern", "print($A)", "example.py"])
        rc = code_intel.main()
    else:
        monkeypatch.setattr(sys, "argv", ["lsp_query", "symbols", "--root", str(selected), "--file", "example.py",
                                         "--server", "pyright-langserver" if mode == "node" else "clangd"])
        rc = lsp_query.main()
    assert not marker.exists()
    assert safe_marker.exists() is (mode == "node")
    assert rc == 2
    result = json.loads(capsys.readouterr().out)
    if mode != "ast":
        assert result["complete"] is False


@pytest.mark.parametrize("operation", ["executable", "path"])
def test_nonlexical_workspace_identity_is_rejected(tmp_path, monkeypatch, operation):
    root, alias, external = (tmp_path / name for name in ("root", "alias", "external"))
    for path in (root, alias, external):
        path.mkdir()
    binary = script(alias / "clangd", "#!/bin/sh\nexit 0\n")
    safe = script(external / "clangd", "#!/bin/sh\nexit 0\n")
    stat = Path.stat
    identity = root.stat()
    monkeypatch.setattr(Path, "stat", lambda path, *a, **kw: identity if path == alias else stat(path, *a, **kw))
    if operation == "executable":
        with pytest.raises(ValueError, match="Workspace"):
            intel_runtime.resolve_executable(str(binary), root)
        assert str(intel_runtime.resolve_executable(str(safe), root)) == str(safe)
    else:
        assert intel_runtime.child_path(str(alias) + os.pathsep + str(external), root) == str(external)


@pytest.mark.parametrize("passwd_value", [None, "", "relative/home"])
def test_missing_or_invalid_passwd_uses_valid_home(tmp_path, monkeypatch, capsys, passwd_value):
    home, logs, config = (tmp_path / name for name in ("home", "logs", "config"))
    for path in (home, logs, config):
        path.mkdir()
    (logs / "log.jsonl").write_text(json.dumps({"type": "user", "message": {"content": "needle"}}) + "\n")

    def lookup(uid):
        if passwd_value is None:
            raise KeyError(uid)
        return SimpleNamespace(pw_dir=passwd_value)

    monkeypatch.setattr(pwd, "getpwuid", lookup)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.chdir(logs)
    for selected, expected in ((logs, 0), (home, 2), (config, 2)):
        monkeypatch.setattr(sys, "argv", ["history", "--root", str(selected), "--query", "needle"])
        assert session_history.main() == expected
        result = json.loads(capsys.readouterr().out)
        if expected == 0:
            assert result["matched_sessions"] == 1
        else:
            assert result["status"] == "error"


@pytest.mark.parametrize("home", [None, "", "relative/home"])
def test_no_usable_home_is_json_error(tmp_path, monkeypatch, capsys, home):
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: SimpleNamespace(pw_dir=""))
    if home is None:
        monkeypatch.delenv("HOME", raising=False)
    else:
        monkeypatch.setenv("HOME", home)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(sys, "argv", ["history", "--root", str(tmp_path), "--query", "needle"])
    assert session_history.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error" and "home" in result["reason"].lower()


def test_doctor_help_discloses_snapshot_write(capsys):
    with pytest.raises(SystemExit) as result:
        install_doctor.main(["--help"])
    assert result.value.code == 0
    text = capsys.readouterr().out
    assert "snapshot capture writes" in text
    assert "Read-only Codex" not in text


@pytest.mark.parametrize("error", [FileNotFoundError, PermissionError])
def test_uninspectable_child_path_is_removed(tmp_path, monkeypatch, error):
    root, unsafe, safe = (tmp_path / name for name in ("root", "unsafe", "safe"))
    for path in (root, unsafe, safe):
        path.mkdir()
    stat = Path.stat

    def inspect(path, *args, **kwargs):
        if path == unsafe:
            raise error("fixture unavailable")
        return stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", inspect)
    assert intel_runtime.child_path(str(unsafe) + os.pathsep + str(safe), root) == str(safe)


def test_selection_and_child_path_share_root_identity(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    binary = script(tmp_path / "external" / "clangd", "#!/bin/sh\nexit 0\n")
    monkeypatch.setenv("PATH", str(binary.parent))
    stat_identity = intel_runtime.filesystem_identity
    observed = []

    def identity(path):
        if path == root:
            observed.append(path)
        return stat_identity(path)

    monkeypatch.setattr(intel_runtime, "filesystem_identity", identity)
    command = lsp_query.select_server("c", str(binary), root=root)
    connection = lsp_transport.Connection(command, str(root))
    try:
        with pytest.raises(lsp_transport.LspError):
            connection.request("initialize", {})
    finally:
        connection.close()
    assert observed == [root]


@pytest.mark.parametrize("home", ["", "relative/home"])
def test_invalid_environment_home_keeps_passwd_protection(tmp_path, monkeypatch, capsys, home):
    passwd_home = tmp_path / "account"
    passwd_home.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setenv("HOME", home)
    monkeypatch.setattr(pwd, "getpwuid", lambda uid: SimpleNamespace(pw_dir=str(passwd_home)))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.chdir(logs)
    for root, expected in ((logs, 0), (passwd_home, 2)):
        monkeypatch.setattr(sys, "argv", ["history", "--root", str(root), "--query", "needle"])
        assert session_history.main() == expected
        assert json.loads(capsys.readouterr().out)["status"] == ("ok" if expected == 0 else "error")
