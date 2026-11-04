#!/usr/bin/env python3
"""Read-only structural queries using the consumer's installed ast-grep."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

QUERY_TIMEOUT = 30
MAX_OUTPUT_BYTES = 8 * 1024 * 1024


def contained_path(root: Path, value: str) -> Path:
    resolved = (root / value).resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError(f"Path escapes workspace: {value}")
    return resolved


def find_ast_grep() -> str | None:
    for name in ("ast-grep", "sg"):
        candidate = shutil.which(name)
        if not candidate:
            continue
        result = subprocess.run(
            [candidate, "--version"], capture_output=True, text=True,
            timeout=5, check=False,
        )
        if result.returncode == 0 and result.stdout.startswith("ast-grep "):
            return candidate
    return None


def query(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Workspace root must be a directory")
    paths = [contained_path(root, value) for value in args.paths]
    binary = find_ast_grep()
    if binary is None:
        print(json.dumps({"status": "unavailable", "reason": "ast-grep is not installed"}))
        return 3
    validation = subprocess.run(
        [binary, "run", "--pattern", args.pattern, "--lang", args.lang, "--debug-query=ast", "--stdin"],
        input="", capture_output=True, text=True, timeout=5, check=False,
    )
    if validation.returncode not in (0, 1) or re.search(r"(?m)^\s+ERROR\b", validation.stderr):
        print(json.dumps({"status": "error", "reason": "Pattern does not parse as valid code", "detail": validation.stderr[:2000]}))
        return 2
    command = [binary, "run", "--pattern", args.pattern, "--lang", args.lang, "--json=compact"]
    if args.rewrite is not None:
        command += ["--rewrite", args.rewrite]
    command += ["--", *map(str, paths)]
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(command, cwd=root, stdout=output, stderr=subprocess.PIPE,
                                timeout=QUERY_TIMEOUT, check=False)
        output.seek(0)
        raw = output.read(MAX_OUTPUT_BYTES + 1)
    if len(raw) > MAX_OUTPUT_BYTES:
        raise ValueError("Query output exceeded 8 MiB; narrow the paths or pattern")
    if result.returncode not in (0, 1):
        print(json.dumps({"status": "error", "reason": result.stderr.decode(errors="replace").strip()}))
        return 2
    matches = json.loads(raw or b"[]")
    if not isinstance(matches, list):
        raise ValueError("ast-grep returned an unexpected response")
    files = set()
    for match in matches:
        if not isinstance(match, dict) or not isinstance(match.get("file"), str):
            raise ValueError("ast-grep returned an invalid match")
        file = contained_path(root, match["file"])
        match["file"] = str(file.relative_to(root))
        files.add(match["file"])
    print(json.dumps({"status": "ok", "mode": "preview" if args.rewrite is not None else "search",
                      "match_count": len(matches), "file_count": len(files),
                      "truncated": len(matches) > args.limit, "matches": matches[:args.limit]},
                     ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--lang", required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--rewrite", help="Preview replacements; never writes files")
    parser.add_argument("--limit", type=int, choices=range(1, 501), default=50, metavar="1..500")
    parser.add_argument("paths", nargs="+", help="Files/directories inside --root")
    try:
        return query(parser.parse_args())
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
