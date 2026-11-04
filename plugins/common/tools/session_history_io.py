"""POSIX descriptor-only access for an explicitly resolved session-log root."""
from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from pathlib import Path

SECURE_IO_SUPPORTED = (
    os.name == "posix"
    and os.open in os.supports_dir_fd
    and os.scandir in os.supports_fd
    and all(getattr(os, name, 0) for name in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK"))
)


def require_secure_io():
    if not SECURE_IO_SUPPORTED:
        raise ValueError("Secure session-log access requires POSIX dir_fd, fd scandir and O_NOFOLLOW")


@contextmanager
def open_entry(name: str, parent_fd: int | None, *, directory: bool):
    """Pin one component without following links, including a raced-in FIFO."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    if directory:
        flags |= os.O_DIRECTORY
    fd = os.open(name, flags, dir_fd=parent_fd)
    try:
        mode = os.fstat(fd).st_mode
        if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
            raise OSError("Session entry is not a directory" if directory else "Session entry is not a regular file")
        yield fd
    finally:
        os.close(fd)


def _reject_identity(fd: int, forbidden_identity: tuple[int, int] | None):
    if forbidden_identity is not None:
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) == forbidden_identity:
            raise ValueError("Choose a session-log directory, not a home or configuration root")


@contextmanager
def open_root(root: Path, *, forbidden_identity: tuple[int, int] | None = None, missing_ok: bool = False):
    """Pin canonical components, optionally rejecting any ancestor's identity.

    missing_ok is only for protection checks: absent config trees still protect
    their existing ancestors. Other IO errors must propagate before any scan.
    """
    require_secure_io()
    # Only the current component stays open during root pinning. Once pinned,
    # renaming an ancestor cannot redirect subsequent relative opens.
    fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        _reject_identity(fd, forbidden_identity)
        for component in root.parts[1:]:
            try:
                with open_entry(component, fd, directory=True) as child_fd:
                    next_fd = os.dup(child_fd)
            except FileNotFoundError:
                if not missing_ok:
                    raise
                break
            os.close(fd)
            fd = next_fd
            _reject_identity(fd, forbidden_identity)
        yield fd
    finally:
        os.close(fd)


def reject_protected_root(root_fd: int, protected_paths: list[Path]):
    """Compare the pinned search root with real protected ancestor identities."""
    info = os.fstat(root_fd)
    root_identity = (info.st_dev, info.st_ino)
    for path in protected_paths:
        # Resolve aliases once. Even if non-strict resolution encounters an
        # unavailable component, the NOFOLLOW opens above cannot silently pass
        # it: only ENOENT is tolerated, and every existing ancestor is checked.
        with open_root(path.resolve(), forbidden_identity=root_identity, missing_ok=True):
            pass
