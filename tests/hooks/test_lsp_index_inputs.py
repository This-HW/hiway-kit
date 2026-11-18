from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))

from lsp_index_inputs import config_still_absent, discover_compile_database
from lsp_index_policy import IndexUnavailable
from lsp_index_resources import Deadline


def fixture(tmp_path, *, command=None, file="../src/a.cpp"):
    root = tmp_path / "project"
    source = root / "src/a.cpp"
    build = root / "build"
    source.parent.mkdir(parents=True)
    build.mkdir()
    source.write_text("int f();\n")
    database = [{"directory": str(build), "file": file,
                 "arguments": [command or "/usr/bin/true", "-c", file]}]
    (build / "compile_commands.json").write_text(json.dumps(database))
    home = tmp_path / "home"
    home.mkdir()
    return root, source, build / "compile_commands.json", {"HOME": str(home)}


def test_compile_database_is_strictly_parsed_and_sources_are_pinned(tmp_path):
    root, source, cdb, env = fixture(tmp_path)
    database, stamp, inventory = discover_compile_database(root, source, env, Deadline(5))
    assert database.path == cdb
    assert database.raw == cdb.read_bytes()
    assert database.source_key == {"cdb": str(cdb),
                                   "sources": [str(source.resolve())]}
    assert database.compiler_identities[0][0] == str(Path("/usr/bin/true").resolve())
    assert stamp[2] == len(database.raw)
    assert config_still_absent(inventory)


def test_compile_database_duplicate_json_key_is_rejected(tmp_path):
    root, source, cdb, env = fixture(tmp_path)
    cdb.write_text('[{"directory":"build","directory":"build","file":"../src/a.cpp",'
                   '"arguments":["/usr/bin/clang++"]}]')
    with pytest.raises(IndexUnavailable) as error:
        discover_compile_database(root, source, env, Deadline(5))
    assert error.value.reason == "compile_db_unsupported"


@pytest.mark.parametrize("compiler", ["clang++", "./clang++"])
def test_compile_database_bare_compiler_is_unsupported(tmp_path, compiler, monkeypatch):
    root, source, _cdb, env = fixture(tmp_path, command=compiler)
    existing = root / "build/clang++"
    existing.write_text("#!/bin/sh\nexit 0\n")
    existing.chmod(0o700)
    monkeypatch.chdir(existing.parent)
    with pytest.raises(IndexUnavailable) as error:
        discover_compile_database(root, source, env, Deadline(5))
    assert error.value.reason == "compile_db_unsupported"


def test_compile_database_response_file_is_unsupported(tmp_path):
    root, source, _cdb, env = fixture(tmp_path)
    value = [{"directory": str(root / "build"), "file": "../src/a.cpp",
              "arguments": ["/usr/bin/true", "@flags.rsp"]}]
    (root / "build/compile_commands.json").write_text(json.dumps(value))
    with pytest.raises(IndexUnavailable) as error:
        discover_compile_database(root, source, env, Deadline(5))
    assert error.value.reason == "compile_db_unsupported"


def test_compile_database_rejects_outside_source(tmp_path):
    outside = tmp_path / "outside.cpp"
    outside.write_text("int out();\n")
    root, source, _cdb, env = fixture(tmp_path)
    value = [{"directory": str(root / "build"), "file": str(outside),
              "arguments": ["/usr/bin/true", str(outside)]}]
    (root / "build/compile_commands.json").write_text(json.dumps(value))
    with pytest.raises(IndexUnavailable) as error:
        discover_compile_database(root, source, env, Deadline(5))
    assert error.value.reason == "compile_db_unsupported"


def test_compile_flags_or_effective_config_disable_indexing(tmp_path):
    root, source, _cdb, env = fixture(tmp_path)
    (root / "src/compile_flags.txt").write_text("-DLOCAL=1\n")
    with pytest.raises(IndexUnavailable) as error:
        discover_compile_database(root, source, env, Deadline(5))
    assert error.value.reason == "compile_db_unsupported"
    (root / "src/compile_flags.txt").unlink()
    (tmp_path / ".clangd").write_text("Index: { Background: Skip }\n")
    with pytest.raises(IndexUnavailable) as error:
        discover_compile_database(root, source, env, Deadline(5))
    assert error.value.reason == "config_unsupported"


def test_user_config_and_new_config_race_are_detected(tmp_path):
    root, source, _cdb, env = fixture(tmp_path)
    _database, _stamp, inventory = discover_compile_database(root, source, env, Deadline(5))
    config = (Path(env["HOME"]) / "Library/Preferences/clangd/config.yaml" if sys.platform == "darwin"
              else Path(env["HOME"]) / ".config/clangd/config.yaml")
    config.parent.mkdir(parents=True)
    config.write_text("CompileFlags: {}\n")
    assert not config_still_absent(inventory)
    with pytest.raises(IndexUnavailable) as error:
        discover_compile_database(root, source, env, Deadline(5))
    assert error.value.reason == "config_unsupported"


def test_missing_compile_database_has_fixed_reason(tmp_path):
    root = tmp_path / "project"
    source = root / "src/a.cpp"
    source.parent.mkdir(parents=True)
    source.write_text("int f();\n")
    home = tmp_path / "home"
    home.mkdir()
    with pytest.raises(IndexUnavailable) as error:
        discover_compile_database(root, source, {"HOME": str(home)}, Deadline(5))
    assert error.value.reason == "no_compile_db"


def test_object_policy_aborts_during_parse_before_entry_resolution(tmp_path, monkeypatch):
    import lsp_index_inputs as inputs
    root, source, cdb, env = fixture(tmp_path)
    monkeypatch.setattr(inputs, 'CDB_ENTRIES', 2)
    cdb.write_text('[{},{},{}]')
    monkeypatch.setattr(inputs, '_entry_paths', lambda *a: pytest.fail('must abort while parsing'))
    with pytest.raises(IndexUnavailable, match='object policy'):
        discover_compile_database(root, source, env, Deadline(5))


def test_config_inventory_observes_shared_deadline(tmp_path):
    import lsp_index_inputs as inputs
    root, source, _cdb, env = fixture(tmp_path)
    deadline = Deadline(5)
    deadline.work_ends = 0
    with pytest.raises(IndexUnavailable) as raised:
        inputs._config_inventory(root, [source], env, deadline)
    assert raised.value.reason == 'index_deadline'


def test_config_inventory_checks_deadline_while_enumerating_ancestors(tmp_path, monkeypatch):
    import lsp_index_inputs as inputs
    root, source, _cdb, env = fixture(tmp_path)
    monkeypatch.setattr(inputs, '_lstat', lambda p: pytest.fail('deadline must be checked before ancestor I/O'))
    deadline = Deadline(5)
    deadline.work_ends = 0
    with pytest.raises(IndexUnavailable) as raised:
        inputs._config_inventory(root, [source], env, deadline)
    assert raised.value.reason == 'index_deadline'


def test_config_inventory_checks_deadline_before_each_presence_probe(tmp_path, monkeypatch):
    import lsp_index_inputs as inputs
    root, source, _cdb, env = fixture(tmp_path)
    deadline = Deadline(5)
    original = inputs._lstat

    def probe(path):
        if path.name == '.clangd':
            deadline.work_ends = 0
        return original(path)
    monkeypatch.setattr(inputs, '_lstat', probe)
    with pytest.raises(IndexUnavailable) as raised:
        inputs._config_inventory(root, [source], env, deadline)
    assert raised.value.reason == 'index_deadline'
