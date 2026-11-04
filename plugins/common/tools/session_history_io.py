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


@contextmanager
def open_root(root: Path):
    """Open every canonical absolute component; never reopen a validated path."""
    require_secure_io()
    # Only the current component stays open during root pinning. Once pinned,
    # renaming an ancestor cannot redirect subsequent relative opens.
    fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        for component in root.parts[1:]:
            with open_entry(component, fd, directory=True) as child_fd:
                next_fd = os.dup(child_fd)
            os.close(fd)
            fd = next_fd
        yield fd
    finally:
        os.close(fd)
