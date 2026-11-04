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


def _relative_path(relative: str) -> Path:
    rel = Path(relative)
    if not relative or rel.is_absolute() or ".." in rel.parts:
        raise ObservationError("unsafe_path", 1)
    if any(part.casefold().startswith(("auth", "credential", "token", ".env")) for part in rel.parts):
        raise ObservationError("forbidden_file", 1)
    return rel


def _identity(info) -> dict:
    return {"device": info.st_dev, "inode": info.st_ino, "uid": info.st_uid, "mode": info.st_mode}


def _link_observation(path: Path) -> dict:
    info = path.lstat()
    if not stat.S_ISLNK(info.st_mode):
        return {"target": None, "identity": None}
    return {"target": os.readlink(path), "identity": {
        **_identity(info), "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns}}


def _safe_store(info):
    if not stat.S_ISDIR(info.st_mode):
        raise ObservationError("plugin_store_not_directory", 1)
    if info.st_uid != os.getuid():
        raise ObservationError("plugin_store_wrong_owner", 1)
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ObservationError("plugin_store_writable_by_others", 1)


class Reader:
    def __init__(self):
        self.used = 0
        self.started = time.monotonic()
        self.origins: list[dict] = []
        self.store_root: Path | None = None
        self.store_fd: int | None = None
        self.store: dict | None = None

    def check(self):
        if time.monotonic() - self.started > MAX_SECONDS:
            raise ObservationError("time_budget_exceeded")

    def close(self):
        if self.store_fd is not None:
            os.close(self.store_fd)
            self.store_fd = None

    def bind_store(self, home: Path, expected: str | None = None) -> dict:
        """Resolve only HOME/plugins, once; all subsequent reads use its pinned FD."""
        logical = home / "plugins"
        try:
            link = _link_observation(logical)
            root = logical.resolve(strict=True)
            if _link_observation(logical) != link:
                raise ObservationError("plugin_store_changed")
            info = root.lstat()
            self.store = {"store_root": str(root), "store_shared": link["target"] is not None,
                          "link_source": str(logical) if link["target"] is not None else None,
                          "logical_path": str(logical), "link": link, "root_identity": _identity(info)}
            _safe_store(info)
            if expected is not None:
                # An explicit scope must already name the canonical root. Do not
                # resolve it (or the logical plugins path) a second time.
                given = Path(expected)
                if ".." in given.parts or given.absolute() != root:
                    raise ObservationError("plugin_store_scope_mismatch")
            fd = self._open_absolute(root, root, directory=True)
            try:
                opened = os.fstat(fd)
                _safe_store(opened)
                if _identity(opened) != _identity(info):
                    raise ObservationError("plugin_store_changed")
                self.store_fd = fd
                self.store_root = root
            finally:
                if self.store_fd != fd:
                    os.close(fd)
            self.origins.append({"kind": "plugin_store", "path": str(logical),
                                 "sha256": hashlib.sha256(json.dumps(self.store, sort_keys=True).encode()).hexdigest()})
            return self.store
        except (OSError, RuntimeError) as exc:
            raise ObservationError("plugin_store_unavailable") from exc

    def verify_store(self):
        """Recheck metadata/identity without resolving or reading through a new root."""
        if self.store_fd is None or self.store is None:
            return
        try:
            pinned = os.fstat(self.store_fd)
            _safe_store(pinned)
            if _identity(pinned) != self.store["root_identity"]:
                raise ObservationError("plugin_store_changed")
            if _link_observation(Path(self.store["logical_path"])) != self.store["link"]:
                raise ObservationError("plugin_store_changed")
            fd = self._open_absolute(self.store_root, self.store_root, directory=True)
            try:
                current = os.fstat(fd)
                _safe_store(current)
                if _identity(current) != self.store["root_identity"]:
                    raise ObservationError("plugin_store_changed")
            finally:
                os.close(fd)
        except (OSError, RuntimeError) as exc:
            raise ObservationError("plugin_store_unavailable") from exc

    def path(self, root: Path, relative: str) -> Path:
        if self.store_root is not None and root.is_relative_to(self.store_root):
            # Lexical containment only: never re-resolve any part of the store.
            return root / _relative_path(relative)
        return _resolve_in_repo(root, relative)

    def user_path(self, path: Path) -> tuple[Path, str]:
        """Map explicit snapshot paths into the same fixed boundary, if inside it."""
        if self.store is not None:
            logical = Path(self.store["logical_path"])
            if path.is_relative_to(logical):
                return self.store_root, str(path.relative_to(logical))
            if path.is_relative_to(self.store_root):
                return self.store_root, str(path.relative_to(self.store_root))
        return path.parent.resolve(strict=True), path.name

    def _walk(self, fd: int, components: tuple, directory: bool) -> int:
        try:
            self.check()
            if not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")):
                raise ObservationError("safe_file_access_unavailable")
            for index, part in enumerate(components):
                self.check()
                before = os.stat(part, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISLNK(before.st_mode):
                    raise ObservationError("unsafe_symlink", 1)
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

    def _open_absolute(self, root: Path, path: Path, directory: bool = False) -> int:
        """Anchor from / without resolving; used to pin/recheck store identity."""
        if not hasattr(os, "O_DIRECTORY"):
            raise ObservationError("safe_file_access_unavailable")
        fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY)
        return self._walk(fd, root.parts[1:] + path.relative_to(root).parts, directory)

    def _open(self, root: Path, path: Path, directory: bool = False) -> int:
        """Store reads start from the pinned FD, never a reopened logical path."""
        self.check()
        if self.store_root is not None and root.is_relative_to(self.store_root):
            opened = os.fstat(self.store_fd)
            _safe_store(opened)
            if _identity(opened) != self.store["root_identity"]:
                raise ObservationError("plugin_store_changed")
            return self._walk(os.dup(self.store_fd), path.relative_to(self.store_root).parts, directory)
        return self._open_absolute(root, path, directory)

    def read(self, root: Path, relative: str, kind: str, record: bool = True) -> bytes:
        path = self.path(root, relative)
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
        path = self.path(root, relative)
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


def write_snapshot(path: Path, value: dict, reader: Reader | None = None):
    """Only explicit, new user outputs; never overwrite existing files or symlinks."""
    if any(part.casefold().startswith(("auth", "credential", "token", ".env")) for part in path.parts):
        raise ObservationError("forbidden_output", 1)
    reader = reader or Reader()
    root, relative = reader.user_path(path)
    parent = reader.path(root, str(Path(relative).parent))
    directory = reader._open(root, parent, directory=True)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True, indent=2)
            stream.write("\n")
    except OSError as exc:
        raise ObservationError("snapshot_output_unavailable") from exc
    finally:
        os.close(directory)
