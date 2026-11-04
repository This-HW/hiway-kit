"""Bounded, descriptor-based reads for install_doctor (stdlib, Python 3.9+)."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from pathlib import Path

MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 128
MAX_SECONDS = 5


class ObservationError(Exception):
    def __init__(self, reason: str, rc: int = 2):
        super().__init__(reason)
        self.reason = reason
        self.rc = rc


def _resolve_in_repo(root: Path, relative: str) -> Path:
    """Resolve once, contain reads as well as checks; reject all symlink inputs."""
    rel = Path(relative)
    if not relative or rel.is_absolute() or ".." in rel.parts:
        raise ObservationError("unsafe_path", 1)
    current = root
    for part in rel.parts:
        if part.casefold().startswith(("auth", "credential", "token", ".env")):
            raise ObservationError("forbidden_file", 1)
        current = current / part
        if current.is_symlink():
            raise ObservationError("unsafe_symlink", 1)
    resolved = (root / rel).resolve()
    if not resolved.is_relative_to(root):
        raise ObservationError("unsafe_path", 1)
    return resolved


class Reader:
    def __init__(self):
        self.used = 0
        self.started = time.monotonic()
        self.origins: list[dict] = []

    def check(self):
        if time.monotonic() - self.started > MAX_SECONDS:
            raise ObservationError("time_budget_exceeded")

    def _open(self, root: Path, path: Path, directory: bool = False) -> int:
        """Every component uses NOFOLLOW; a renamed parent cannot redirect a read."""
        self.check()
        if not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")):
            raise ObservationError("safe_file_access_unavailable")
        parts = path.relative_to(root).parts
        # Anchor even the explicit root from /, avoiding a root-ancestor swap.
        fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY)
        try:
            components = root.parts[1:] + parts
            for index, part in enumerate(components):
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                if index < len(components) - 1 or directory:
                    flags |= os.O_DIRECTORY
                next_fd = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            result = fd
            fd = -1
            return result
        except OSError as exc:
            raise ObservationError("file_unavailable") from exc
        finally:
            if fd >= 0:
                os.close(fd)

    def read(self, root: Path, relative: str, kind: str, record: bool = True) -> bytes:
        path = _resolve_in_repo(root, relative)
        fd = self._open(root, path)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise ObservationError("not_regular_file", 1)
            remaining = min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - self.used)
            if before.st_size > remaining or remaining < 0:
                raise ObservationError("read_budget_exceeded")
            chunks = []
            size = 0
            while True:
                self.check()
                chunk = os.read(fd, min(65536, remaining - size + 1))
                self.used += len(chunk)
                size += len(chunk)
                if size > remaining:
                    raise ObservationError("read_budget_exceeded")
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(fd)
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns
            ):
                raise ObservationError("file_changed_during_read")
            data = b"".join(chunks)
        finally:
            os.close(fd)
        if record:
            self.origins.append({"kind": kind, "path": str(path), "sha256": hashlib.sha256(data).hexdigest()})
        return data

    def json(self, root: Path, relative: str, kind: str) -> dict:
        try:
            value = json.loads(self.read(root, relative, kind))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise ObservationError("invalid_json", 1) from exc
        if not isinstance(value, dict):
            raise ObservationError("invalid_json_object", 1)
        return value

    def directories(self, root: Path, relative: str) -> list[str]:
        path = _resolve_in_repo(root, relative)
        fd = self._open(root, path, directory=True)
        try:
            result = []
            with os.scandir(fd) as entries:
                for count, entry in enumerate(entries):
                    self.check()
                    if count >= MAX_ENTRIES:
                        raise ObservationError("directory_budget_exceeded")
                    if entry.is_symlink():
                        raise ObservationError("unsafe_symlink", 1)
                    if entry.is_dir(follow_symlinks=False):
                        result.append(entry.name)
            return sorted(result)
        finally:
            os.close(fd)


def write_snapshot(path: Path, value: dict):
    """Only explicit, new user outputs; never overwrite existing files or symlinks."""
    if any(part.casefold().startswith(("auth", "credential", "token", ".env")) for part in path.parts):
        raise ObservationError("forbidden_output", 1)
    parent = path.parent.resolve(strict=True)
    reader = Reader()
    directory = reader._open(parent, parent, directory=True)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True, indent=2)
            stream.write("\n")
    except OSError as exc:
        raise ObservationError("snapshot_output_unavailable") from exc
    finally:
        os.close(directory)
