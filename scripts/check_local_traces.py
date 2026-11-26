#!/usr/bin/env python3
"""Report maintainer-specific paths in Git-tracked text, including symlink targets.

An exception identifies one tracked line by path, 1-based line number and SHA-256
of the line bytes without its line ending (UTF-16/32 with BOM is read as UTF-8).
A changed or removed line needs review.
"""

import argparse
import codecs
import hashlib
import json
import os
import re
from pathlib import Path

from check_unicode_safety import BINARY_SUFFIXES
from git_tracked import tracked_files

POLICY = "scripts/local-trace-exceptions.json"
# Use regex syntax for literals that would otherwise match the detector's own source.
TRACES = {
    "absolute-home": re.compile(
        r"""/(?:Users|home)/[\w-][\w.+@'-]*(?: [\w.+@'-]+)*(?=/|["'`]|$)"""
    ),
    "tool-cache": re.compile(r"hiway-(?:kit-tools|research)|venv[-]pinned"),
    "archify-install": re.compile(
        r"\.(?:claude|agents)/(?:skills|rules)/archify\b|\[archify\s+explainer:"
    ),
    "local-browser": re.compile(r"\baside\s+repl\b|\.aside/u/\d+/uploads\b"),
}


class PolicyError(ValueError):
    """A validation message safe for CI output."""


def contained_path(root: Path, name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise PolicyError("expected a repository-relative path")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise PolicyError("path escapes repository")
    return resolved


def load_exceptions(root: Path) -> set[tuple[str, int, str]]:
    policy = contained_path(root, POLICY)
    if policy != root / POLICY:
        raise PolicyError("policy path must be a tracked regular file")
    data = json.loads(policy.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or set(data) != {"exceptions"}
        or not isinstance(data["exceptions"], list)
    ):
        raise PolicyError("expected an exceptions array")
    exceptions = set()
    for entry in data["exceptions"]:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "line",
            "sha256",
            "reason",
        }:
            raise PolicyError("invalid exception fields")
        name, line, digest, reason = (
            entry[key] for key in ("path", "line", "sha256", "reason")
        )
        if not isinstance(name, str):
            raise PolicyError("invalid exception path")
        contained_path(root, name)
        if not isinstance(reason, str) or not reason.strip():
            raise PolicyError("exception needs a reason")
        if (
            type(line) is not int
            or line < 1
            or not isinstance(digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
        ):
            raise PolicyError("invalid line number or SHA-256")
        # An exception for a tracked link covers the link text, never the file it points to.
        key = (Path(name).as_posix(), line, digest)
        if key in exceptions:
            raise PolicyError("duplicate exception")
        exceptions.add(key)
    return exceptions


def display_path(name: str) -> str:
    for kind, pattern in TRACES.items():
        name = pattern.sub(f"/<{kind}>", name)
    return name.replace("\n", "\\n").replace("\r", "\\r")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    root = parser.parse_args().root.resolve()
    files = tracked_files(root, label="check-local-traces")
    if POLICY not in files:
        print(f"{POLICY}: policy must be tracked")
        return 1
    try:
        exceptions = load_exceptions(root)
    except PolicyError as error:
        print(f"{POLICY}: {error}")
        return 1
    except (OSError, ValueError, RuntimeError):
        # OS and parser messages may contain the absolute path or offending text.
        print(f"{POLICY}: invalid policy path or exception")
        return 1

    failed = False
    scanned = 0
    for name in files:
        path = root / name
        try:
            if not path.parent.resolve().is_relative_to(root):
                raise ValueError("directory outside repository")
            data = (
                os.fsencode(os.readlink(path))
                if path.is_symlink()
                else path.read_bytes()
            )
        except (OSError, ValueError, RuntimeError):
            print(f"{display_path(name)}: cannot read tracked path")
            failed = True
            continue
        if data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
            data = data.decode("utf-32", errors="replace").encode("utf-8")
        elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            data = data.decode("utf-16", errors="replace").encode("utf-8")
        elif b"\0" in data and path.suffix.lower() in BINARY_SUFFIXES:
            continue
        scanned += 1
        for number, raw_line in enumerate(data.split(b"\n"), 1):
            line = raw_line.removesuffix(b"\r")
            content = line.decode("utf-8", errors="replace")
            kinds = [
                kind for kind, pattern in TRACES.items() if pattern.search(content)
            ]
            if not kinds:
                continue
            key = (name, number, hashlib.sha256(line).hexdigest())
            if key in exceptions:
                exceptions.remove(key)
                continue
            for kind in kinds:
                print(f"{display_path(name)}:{number}: {kind}")
            failed = True

    for name, number, _ in sorted(exceptions):
        print(f"{display_path(name)}:{number}: unused exception")
    if failed or exceptions:
        return 1
    print(f"check-local-traces: {scanned} tracked text files checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
