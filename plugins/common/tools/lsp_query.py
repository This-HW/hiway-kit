#!/usr/bin/env python3
"""One-shot queries with trusted language servers; servers can execute workspace code and are not sandboxed."""
from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path

from intel_runtime import print_result, resolve_executable
from lsp_source import SourceUnavailable, read_source
from lsp_transport import Connection, LspError
from lsp_validation import LspBudgetExceeded, require, validate_navigation

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


def select_server(language: str, explicit: str | None, allow_custom: bool = False,
                  root: Path | None = None) -> list[str] | None:
    root = Path.cwd().resolve() if root is None else root
    resolved = {}

    def checked(path: str) -> str:
        return resolve_executable(path, root, allow_custom, resolved)

    if explicit is not None:
        if not explicit or explicit in (".", "..") or "\\" in explicit or (not Path(explicit).is_absolute() and "/" in explicit):
            raise ValueError("--server requires a bare executable name or absolute path; relative paths are forbidden")
        known = {name: arguments for candidates in SERVER_CANDIDATES.values() for name, arguments in candidates}
        if Path(explicit).name not in known and not allow_custom:
            raise ValueError("Unknown --server basename; --allow-custom-server permits arbitrary code execution")
        path = shutil.which(explicit)
        if path is None:
            return None
        fixed = checked(path)
        if Path(explicit).is_absolute() and not allow_custom:
            installed = shutil.which(Path(explicit).name)
            if installed is None or checked(installed).executable != fixed.executable:
                raise ValueError("Absolute server must match the installed PATH server; otherwise use --allow-custom-server")
        return [fixed, *known.get(Path(explicit).name, [])]
    for name, arguments in SERVER_CANDIDATES.get(language.removesuffix("react"), []):
        path = shutil.which(name)
        if path:
            return [checked(path), *arguments]
    return None


def query(args: argparse.Namespace) -> int:
    allow_custom = getattr(args, "allow_custom_server", False)
    if getattr(args, "server_arg", []) and not allow_custom:
        raise ValueError("--server-arg requires --allow-custom-server (arbitrary code execution and writes)")
    root, path, text = read_source(args.root, args.file, MAX_SOURCE_BYTES)
    language = LANGUAGES.get(path.suffix, "plaintext")
    command = select_server(language, args.server, allow_custom, root)
    if command is None:
        print_result({"status": "unavailable", "complete": False, "language": language, "reason": "No installed language server"})
        return 3
    command += args.server_arg
    # LSP lines end only at LF, CRLF, or CR. Keep a final empty line and
    # leave NEL/LS/PS in the line when computing UTF-16 character offsets.
    lines = re.split(r"\r\n|\r|\n", text)
    if not 1 <= args.line <= len(lines) or not 1 <= args.column <= len(lines[args.line - 1]) + 1:
        raise ValueError("Position is outside the source file (line/column start at 1)")
    position = {"line": args.line - 1, "character": len(lines[args.line - 1][:args.column - 1].encode("utf-16-le")) // 2}
    connection = Connection(command, str(root), allow_custom=allow_custom)
    try:
        initialization = connection.request("initialize", {
            "processId": os.getpid(), "rootUri": root.as_uri(),
            "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
            "capabilities": {"general": {"positionEncodings": ["utf-16"]},
                             "workspace": {"configuration": True, "workspaceFolders": True},
                             "textDocument": {"publishDiagnostics": {"versionSupport": True},
                                              "diagnostic": {"dynamicRegistration": False, "relatedDocumentSupport": False},
                                              "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                                              "definition": {"linkSupport": True}}},
        })
        if not isinstance(initialization, dict) or not isinstance(initialization.get("capabilities"), dict):
            raise LspError("Invalid language-server initialization response")
        if initialization["capabilities"].get("positionEncoding", "utf-16") != "utf-16":
            raise LspError("Language server did not negotiate UTF-16 positions")
        provider = initialization["capabilities"].get("diagnosticProvider")
        if provider is not None:
            require(isinstance(provider, dict) and type(provider.get("interFileDependencies")) is bool
                    and type(provider.get("workspaceDiagnostics")) is bool, "diagnosticProvider capability")
            if "identifier" in provider:
                require(isinstance(provider["identifier"], str), "diagnosticProvider identifier")
        connection.notify("initialized", {})
        connection.notify("textDocument/didOpen", {"textDocument": {
            "uri": path.as_uri(), "languageId": language, "version": 1, "text": text,
        }})
        methods = {"symbols": "textDocument/documentSymbol", "definition": "textDocument/definition",
                   "references": "textDocument/references"}
        if args.action == "diagnostics":
            result, complete = connection.diagnostics(path.as_uri(), provider)
        else:
            params = {"textDocument": {"uri": path.as_uri()}}
            if args.action != "symbols":
                params["position"] = position
            if args.action == "references":
                params["context"] = {"includeDeclaration": True}
            result = connection.request(methods[args.action], params)
            validate_navigation(args.action, result)
            complete = True
        print_result({"status": "ok" if complete else "unverified", "complete": complete,
                          "action": args.action, "server": getattr(command[0], "executable", command[0]),
                      "file": str(path.relative_to(root)), "result": result})
        if args.action == "diagnostics" and any(item.get("severity", 1) == 1 for item in result):
            return 1
        return 0 if complete else 2
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("diagnostics", "symbols", "definition", "references"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--file", required=True)
    parser.add_argument("--line", type=int, default=1)
    parser.add_argument("--column", type=int, default=1)
    parser.add_argument("--server", help="Known installed server: bare name or absolute path matching PATH; relative paths are forbidden")
    parser.add_argument("--allow-custom-server", action="store_true",
                        help="Permit custom, workspace, or relative PATH servers: arbitrary code execution; explicit relative paths remain forbidden")
    parser.add_argument("--server-arg", action="append", default=[],
                        help="Append to server defaults (repeatable); requires --allow-custom-server and permits code execution/writes")
    try:
        return query(parser.parse_args())
    except SourceUnavailable as exc:
        print_result({"status": "unavailable", "complete": False, "reason": str(exc)})
        return 3
    except LspBudgetExceeded as exc:
        print_result({"status": "unverified", "complete": False, "reason": str(exc)})
        return 2
    except (OSError, ValueError, LspError) as exc:
        print_result({"status": "error", "complete": False, "reason": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
