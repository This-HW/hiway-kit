"""Python 3.9 stdlib runtime smoke for indexed-input discovery."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))

import lsp_query
from lsp_index_inputs import discover_compile_database
from lsp_index_policy import IndexUnavailable
from lsp_index_resources import Deadline


class IndexedInputsPython39Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "project"
        self.source = self.root / "src/example.c"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("int example(void);\n")
        self.home = self.base / "home"
        self.home.mkdir()
        self.cdb = self.root / "build/compile_commands.json"
        self.cdb.parent.mkdir()
        self.write_cdb([{"directory": str(self.cdb.parent), "file": "../src/example.c",
                         "arguments": [str(Path(sys.executable).resolve()), "-c", "../src/example.c"]}])

    def write_cdb(self, value):
        self.cdb.write_text(json.dumps(value))

    def discover(self):
        return discover_compile_database(self.root, self.source, {"HOME": str(self.home)}, Deadline(5))

    def test_absolute_compiler_and_source_identity_are_accepted(self):
        database, _stamp, _config = self.discover()
        self.assertEqual(database.sources[0].path, self.source.resolve())
        self.assertEqual(database.compiler_identities[0][0], str(Path(sys.executable).resolve()))

    def test_bare_compiler_is_rejected_with_fixed_reason(self):
        self.write_cdb([{"directory": str(self.cdb.parent), "file": "../src/example.c",
                         "arguments": ["clang", "-c", "../src/example.c"]}])
        with self.assertRaises(IndexUnavailable) as raised:
            self.discover()
        self.assertEqual(raised.exception.reason, "compile_db_unsupported")

    def test_invalid_effective_config_is_rejected(self):
        (self.root / ".clangd").write_text("Index: { Background: Skip }\n")
        with self.assertRaises(IndexUnavailable) as raised:
            self.discover()
        self.assertEqual(raised.exception.reason, "config_unsupported")

    def test_indexed_entrypoint_contract_runs_on_python39(self):
        instances = []
        source = self.source

        class FakeConnection:
            def __init__(self, command, cwd, **kwargs):
                self.command = command
                self.requests = []
                self.finished = False
                self.cache_entry = Path(next(arg.split("=", 1)[1] for arg in command
                                             if arg.startswith("--compile-commands-dir=")))
                instances.append(self)

            def request(self, method, params, **kwargs):
                self.requests.append(method)
                if method == "initialize":
                    return {"capabilities": {}}
                return [{"uri": source.as_uri(), "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 6}}}]

            def notify(self, method, params):
                pass

            def wait_for_background_index(self):
                index = self.cache_entry / ".cache/clangd/index"
                index.mkdir(parents=True)
                (index / "example.c.0123456789abcdef.idx").write_bytes(b"fixture")

            def finish_indexed(self, *, graceful=True):
                self.finished = True

        cache_home = self.base / "cache"
        cache_home.mkdir()
        fake_server = self.base / "clangd"
        fake_server.write_text("fixture")
        coverage = lsp_query.Coverage(1, 1, True, None)
        args = argparse.Namespace(root=str(self.root), file="src/example.c", action="references",
                                  line=1, column=1, server=None, server_arg=[], allow_custom_server=False)
        output = io.StringIO()
        with (patch.dict(os.environ, {"HOME": str(self.home), "XDG_CACHE_HOME": str(cache_home)}),
              patch.object(lsp_query, "select_server", return_value=[str(fake_server)]),
              patch.object(lsp_query, "_indexed_toolchain",
                           return_value=(str(fake_server), ("fake-clangd", 1), None, (str(self.root), 1, 2))),
              patch.object(lsp_query, "certify", return_value=coverage),
              patch.object(lsp_query, "Connection", FakeConnection),
              contextlib.redirect_stdout(output)):
            result = lsp_query.query(args)
        payload = json.loads(output.getvalue())
        self.assertEqual(result, 0)
        self.assertTrue(payload["complete"])
        self.assertTrue(instances[0].finished)
        self.assertIn("--limit-references=0", instances[0].command)


if __name__ == "__main__":
    unittest.main()
