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

from bounded_process import ProcessBudget
from intel_runtime import print_result

QUERY_TIMEOUT = 30
PROBE_TIMEOUT = 5
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
# This native diagnostic is version dependent (verified with ast-grep 0.51.0).
# Raw debug ASTs precede metavariable preprocessing and are not a validity test.
INVALID_PATTERN_WARNING = b"Warning: Pattern contains an ERROR node and may cause unexpected results."


def contained_path(root: Path, value: str) -> Path:
    resolved = (root / value).resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError(f"Path escapes workspace: {value}")
    return resolved


def output(result: dict) -> None:
    print_result({"pattern_validated": False, **result})


def find_ast_grep(budget: ProcessBudget | None = None, cwd: Path | None = None) -> tuple[str, str] | None:
    if budget is None:
        budget = ProcessBudget(PROBE_TIMEOUT, MAX_OUTPUT_BYTES)
    # Never execute `sg` while probing: on Linux it can be a group-switching
    # utility, and identifying that after execution is too late.
    candidate = shutil.which("ast-grep")
    if candidate:
        if not Path(candidate).is_absolute():
            raise ValueError("ast-grep PATH result is relative; use an absolute PATH entry")
        candidate = str(Path(candidate).resolve(strict=True))
        result = budget.run([candidate, "--version"], timeout=PROBE_TIMEOUT, cwd=cwd)
        version = re.fullmatch(rb"ast-grep ([0-9]+\.[0-9]+\.[0-9]+)(?:\r?\n)?", result.stdout)
        if result.returncode == 0 and version:
            return candidate, version[1].decode("ascii")
    return None


def query(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Workspace root must be a directory")
    paths = [contained_path(root, value) for value in args.paths]
    budget = ProcessBudget(QUERY_TIMEOUT, MAX_OUTPUT_BYTES)
    with tempfile.TemporaryDirectory(prefix="hiway-ast-") as directory:
        return run_query(args, root, paths, budget, Path(directory))


def run_query(args, root: Path, paths: list[Path], budget: ProcessBudget, cwd: Path) -> int:
    engine = find_ast_grep(budget, cwd=cwd)
    if engine is None:
        output({"status": "unavailable", "reason": "ast-grep is not installed or its version output is unrecognized"})
        return 3
    binary, version = engine
    pattern_validated = version == "0.51.0"
    # Override upward sgconfig discovery as well as using a neutral cwd. A
    # config in a temp ancestor must not load custom workspace parsers/rules.
    config = cwd / "sgconfig.yml"
    config.write_text("ruleDirs: []\n", encoding="utf-8")
    base = [binary, "run", "--config", str(config), "--pattern", args.pattern, "--lang", args.lang]
    validation = budget.run(
        [*base, "--stdin"], timeout=PROBE_TIMEOUT, cwd=cwd,
    )
    if validation.returncode not in (0, 1):
        output({"status": "error", "reason": "Pattern compilation failed", "detail": validation.stderr.decode(errors="replace")[:2000]})
        return 2
    if pattern_validated and INVALID_PATTERN_WARNING in validation.stderr.splitlines():
        output({"status": "error", "reason": "Engine reported an invalid pattern", "detail": validation.stderr.decode(errors="replace")[:2000]})
        return 2
    command = [*base, "--json=compact"]
    if args.rewrite is not None:
        command += ["--rewrite", args.rewrite]
    command += ["--", *map(str, paths)]
    result = budget.run(command, cwd=cwd)
    if result.returncode not in (0, 1):
        output({"status": "error", "reason": result.stderr.decode(errors="replace").strip()[:2000]})
        return 2
    if pattern_validated and INVALID_PATTERN_WARNING in result.stderr.splitlines():
        output({"status": "error", "reason": "Engine reported an invalid pattern", "detail": result.stderr.decode(errors="replace")[:2000]})
        return 2
    matches = json.loads(result.stdout or b"[]")
    if not isinstance(matches, list):
        raise ValueError("ast-grep returned an unexpected response")
    files = set()
    for match in matches:
        if not isinstance(match, dict) or not isinstance(match.get("file"), str):
            raise ValueError("ast-grep returned an invalid match")
        file = contained_path(root, match["file"])
        match["file"] = str(file.relative_to(root))
        files.add(match["file"])
    verified = pattern_validated or bool(matches)
    output({"status": "ok" if verified else "unverified", "pattern_validated": pattern_validated,
            "engine_version": version, "mode": "preview" if args.rewrite is not None else "search",
            "match_count": len(matches), "file_count": len(files),
            "truncated": len(matches) > args.limit, "matches": matches[:args.limit]})
    return 0 if verified else 2


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
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        output({"status": "error", "reason": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
