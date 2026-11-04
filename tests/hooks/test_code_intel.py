from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
import code_intel


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
    monkeypatch.setattr(code_intel.subprocess, "run", lambda *a, **kw:
                        argparse.Namespace(returncode=0, stdout="sg from util-linux\n"))
    assert code_intel.find_ast_grep() is None


def test_missing_binary_reports_unavailable(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(code_intel, "find_ast_grep", lambda: None)
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
