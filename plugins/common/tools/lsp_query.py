#!/usr/bin/env python3
"""One-shot, read-only LSP queries; missing servers are never installed."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from code_intel import contained_path
from lsp_transport import Connection, LspError

MAX_SOURCE_BYTES = 1024 * 1024
SERVER_CANDIDATES = {
    "c": [("clangd", ["--background-index=false", "--log=error"])],
    "cpp": [("clangd", ["--background-index=false", "--log=error"])],
    "python": [("basedpyright-langserver", ["--stdio"]), ("pyright-langserver", ["--stdio"]), ("ruff", ["server"])],
    "typescript": [("typescript-language-server", ["--stdio"])],
    "javascript": [("typescript-language-server", ["--stdio"])],
    "rust": [("rust-analyzer", [])],
    "go": [("gopls", [])],
}
LANGUAGES = {".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".hpp": "cpp",
             ".py": "python", ".ts": "typescript", ".tsx": "typescriptreact",
             ".js": "javascript", ".jsx": "javascriptreact", ".rs": "rust", ".go": "go"}


def select_server(language: str, explicit: str | None) -> list[str] | None:
    if explicit:
        path = shutil.which(explicit)
        return [path] if path else None
    for name, arguments in SERVER_CANDIDATES.get(language.removesuffix("react"), []):
        path = shutil.which(name)
        if path:
            return [path, *arguments]
    return None


def query(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve(strict=True)
    path = contained_path(root, args.file)
    if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Expected a source file no larger than 1 MiB")
    text = path.read_text(encoding="utf-8")
    language = LANGUAGES.get(path.suffix, "plaintext")
    command = select_server(language, args.server)
    if command is None:
        print(json.dumps({"status": "unavailable", "language": language, "reason": "No installed language server"}))
        return 3
    command += args.server_arg
    lines = text.splitlines() or [""]
    if not 1 <= args.line <= len(lines) or not 1 <= args.column <= len(lines[args.line - 1]) + 1:
        raise ValueError("Position is outside the source file (line/column start at 1)")
    position = {"line": args.line - 1, "character": len(lines[args.line - 1][:args.column - 1].encode("utf-16-le")) // 2}
    connection = Connection(command, str(root))
    try:
        initialization = connection.request("initialize", {
            "processId": os.getpid(), "rootUri": root.as_uri(),
            "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
            "capabilities": {"general": {"positionEncodings": ["utf-16"]},
                             "textDocument": {"publishDiagnostics": {"versionSupport": True}}},
        })
        if not isinstance(initialization, dict) or not isinstance(initialization.get("capabilities"), dict):
            raise LspError("Invalid language-server initialization response")
        if initialization["capabilities"].get("positionEncoding", "utf-16") != "utf-16":
            raise LspError("Language server did not negotiate UTF-16 positions")
        connection.notify("initialized", {})
        connection.notify("textDocument/didOpen", {"textDocument": {
            "uri": path.as_uri(), "languageId": language, "version": 1, "text": text,
        }})
        methods = {"symbols": "textDocument/documentSymbol", "definition": "textDocument/definition",
                   "references": "textDocument/references"}
        if args.action == "diagnostics":
            result = connection.diagnostics(path.as_uri())
        else:
            params = {"textDocument": {"uri": path.as_uri()}}
            if args.action != "symbols":
                params["position"] = position
            if args.action == "references":
                params["context"] = {"includeDeclaration": True}
            result = connection.request(methods[args.action], params)
            valid_types = (list, dict) if args.action == "definition" else (list,)
            if result is not None and not isinstance(result, valid_types):
                raise LspError("Invalid symbol/navigation response")
        print(json.dumps({"status": "ok", "action": args.action, "server": command[0],
                          "file": str(path.relative_to(root)), "result": result}, ensure_ascii=False))
        return int(args.action == "diagnostics" and any(item.get("severity", 1) == 1 for item in result))
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("diagnostics", "symbols", "definition", "references"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--file", required=True)
    parser.add_argument("--line", type=int, default=1)
    parser.add_argument("--column", type=int, default=1)
    parser.add_argument("--server", help="Explicit installed executable; no shell evaluation")
    parser.add_argument("--server-arg", action="append", default=[])
    try:
        return query(parser.parse_args())
    except (OSError, ValueError, LspError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
