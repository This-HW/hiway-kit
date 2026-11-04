"""Read a resolved, contained source through directory descriptors, with a byte cap."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import code_intel


class SourceUnavailable(ValueError):
    pass


def read_source(root_value: str, file_value: str, maximum: int) -> tuple[Path, Path, str]:
    try:
        root = Path(root_value).resolve(strict=True)
        path = code_intel.contained_path(root, file_value)
    except RuntimeError as exc:
        # Python 3.9 reports resolution loops as RuntimeError, rather than the
        # OSError used by newer pathlib versions.
        raise ValueError("Cannot safely resolve source path: " + str(exc)) from exc
    relative = path.relative_to(root)
    required = ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")
    if os.name != "posix" or any(not hasattr(os, name) for name in required) or os.open not in os.supports_dir_fd:
        raise SourceUnavailable("Safe directory-descriptor source reading is unavailable on this platform")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    # Anchor at / and open every ancestor, including those above root. A final-file
    # O_NOFOLLOW alone would still follow a swapped ancestor or workspace root.
    directory = os.open(root.anchor, flags | os.O_DIRECTORY)
    try:
        for part in (*root.parts[1:], *relative.parts[:-1]):
            child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
            os.close(directory)
            directory = child
        if not relative.parts:
            raise ValueError("Expected a regular source file")
        source = os.open(relative.parts[-1], flags, dir_fd=directory)
        try:
            metadata = os.fstat(source)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("Expected a regular source file")
            if metadata.st_size > maximum:
                raise ValueError("Source file is larger than the byte budget")
            chunks = []
            total = 0
            while total <= maximum:
                chunk = os.read(source, min(65536, maximum + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            if total > maximum or os.fstat(source).st_size > maximum:
                raise ValueError("Source file is larger than the byte budget")
            text = b"".join(chunks).decode("utf-8")
        finally:
            os.close(source)
    finally:
        os.close(directory)
    return root, path, text
