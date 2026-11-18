"""Private FD-anchored index cache and leases; callers own server lifecycle.

This module never launches a process or edits a workspace. Locks remain held
through the caller's server shutdown. Cache targets are not physical quotas.
"""
from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import os
import re
import secrets
import stat
import threading
import time
from pathlib import Path

from intel_runtime import filesystem_identity, within_workspace
from lsp_index_policy import (
    CDB_BYTES,
    EXISTING_KEY_SECONDS,
    KEY_BYTES,
    LOCK_SECONDS,
    MAX_DEPTH,
    NEW_KEY_SECONDS,
    RETAINED_BYTES,
    RETAINED_KEYS,
    SCHEMA,
    SEMANTIC_ENV,
    STRINGS_COUNT,
    TRANSIENT_BYTES,
    IndexUnavailable,
)

KEY_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
FAILURE_REASONS = frozenset({"index_disabled", "no_compile_db", "compile_db_unsupported", "config_unsupported",
                             "index_unavailable", "index_deadline", "lock_timeout", "cache_limit",
                             "index_resource_limit", "index_transient_limit", "index_response_limit", "index_response_unverified", "index_coverage_unverified", "index_had_errors",
                             "index_inputs_changed", "project_index_not_verified"})
DIR_FLAGS = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0))


def key_for(*, cdb: bytes, source_identities, root_identity, engine_identity, compiler_identities,
            sdk_identity, config_inventory, environment: dict[str, str]) -> str:
    """Only semantic environment participates; absent and empty are distinct.

    ``source_identities`` contains the canonical CDB path and canonical TU
    paths. TU inodes belong only to coverage certification, never this key.
    """
    if len(cdb) > CDB_BYTES:
        raise IndexUnavailable("compile_db_unsupported", "Compilation database exceeds the input policy")
    data = {"schema": SCHEMA, "cdb": hashlib.sha256(cdb).hexdigest(),
            "sources": source_identities, "root": root_identity,
            "engine": engine_identity, "compilers": compiler_identities, "sdk": sdk_identity,
            "config": config_inventory, "env": {k: environment[k] for k in SEMANTIC_ENV if k in environment}}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _key(key: str) -> str:
    if not isinstance(key, str) or KEY_PATTERN.fullmatch(key) is None:
        raise ValueError("Invalid index key")
    return key


def _owned(info, *, private=False, directory=False, check_mode=True):
    kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    mask = 0o077 if private else 0o022
    if (not kind or info.st_uid != os.getuid() or (check_mode and info.st_mode & mask)
            or (not directory and info.st_nlink != 1)):
        raise IndexUnavailable("index_unavailable", "Unsafe index cache ownership, permissions, link or type")


def _directory(parent, name, *, create=False, private=False, check_mode=True):
    if create:
        with contextlib.suppress(FileExistsError):
            os.mkdir(name, 0o700, dir_fd=parent)
    fd = os.open(name, DIR_FLAGS, dir_fd=parent)
    try:
        _owned(os.fstat(fd), private=private, directory=True, check_mode=check_mode)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _file(parent, name, flags=os.O_RDONLY, mode=0o600, *, check_mode=True):
    fd = os.open(name, flags | os.O_NOFOLLOW | os.O_CLOEXEC | getattr(os, "O_NONBLOCK", 0), mode, dir_fd=parent)
    try:
        _owned(os.fstat(fd), check_mode=check_mode)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _atomic(parent, name, raw):
    temp = ".tmp-" + secrets.token_hex(12)
    fd = _file(parent, temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        view = memoryview(raw)
        while view:
            wrote = os.write(fd, view)
            if wrote <= 0:
                raise OSError("Incomplete cache write")
            view = view[wrote:]
        os.fsync(fd)
        os.rename(temp, name, src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)
        check = _file(parent, name)
        try:
            with os.fdopen(check, "rb", closefd=False) as stream:
                readback = stream.read(len(raw) + 1)
            if os.fstat(check).st_size != len(raw) or readback != raw:
                raise IndexUnavailable("index_unavailable", "Index cache write/readback mismatch")
        finally:
            os.close(check)
    finally:
        os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp, dir_fd=parent)


def _scan(fd, deadline, *, depth=0, counter=None, cleanup=False, active=False, skip_tmp=False):
    if depth > MAX_DEPTH:
        raise IndexUnavailable("cache_limit", "Index cache traversal exceeds policy")
    counter = [0] if counter is None else counter
    size = shards = 0
    with os.scandir(fd) as entries:
        for entry in entries:
            if skip_tmp and depth == 0 and entry.name == "tmp":
                continue
            deadline.check(cleanup=cleanup)
            counter[0] += 1
            if counter[0] > STRINGS_COUNT:
                raise IndexUnavailable("cache_limit", "Index cache traversal exceeds policy")
            try:
                before = entry.stat(follow_symlinks=False)
            except FileNotFoundError:
                if active:
                    continue
                raise
            if stat.S_ISDIR(before.st_mode):
                try:
                    child = _directory(fd, entry.name, check_mode=False)
                except OSError as exc:
                    if active and exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
                        continue
                    raise
                try:
                    if (before.st_dev, before.st_ino) != filesystem_identity_fd(child):
                        if active:
                            continue
                        raise IndexUnavailable("index_unavailable", "Cache directory changed")
                    result = _scan(child, deadline, depth=depth + 1, counter=counter, cleanup=cleanup, active=active)
                    size += result[0]
                    shards += result[1]
                finally:
                    os.close(child)
            else:
                try:
                    child = _file(fd, entry.name, check_mode=False)
                except OSError as exc:
                    if active and exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
                        continue
                    raise
                try:
                    current = os.fstat(child)
                    if active and (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
                        # A regular shard may have been atomically replaced
                        # between readdir and open; count the safely-opened
                        # current object, never the vanished directory entry.
                        pass
                    elif (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
                        raise IndexUnavailable("index_unavailable", "Cache file changed")
                    size += current.st_size
                    if entry.name.endswith(".idx") and current.st_size:
                        shards += 1
                finally:
                    os.close(child)
    return size, shards


def filesystem_identity_fd(fd):
    info = os.fstat(fd)
    return info.st_dev, info.st_ino


def _remove_tree_fd(parent, name, deadline, *, cleanup=False, preserve=frozenset(), depth=0):
    """Remove an entry by its directory FD; never open a leaf for reading."""
    if depth > MAX_DEPTH:
        raise IndexUnavailable("cache_limit", "Index cache removal exceeds depth policy")
    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        # unlink is safe for symlinks, FIFOs and other non-directories: it
        # removes the name itself and never follows/opens its target.
        os.unlink(name, dir_fd=parent)
        return
    child = _directory(parent, name, check_mode=False)
    try:
        if filesystem_identity_fd(child) != (info.st_dev, info.st_ino):
            raise IndexUnavailable("index_unavailable", "Cache removal directory changed")
        with os.scandir(child) as entries:
            names = [entry.name for entry in entries if entry.name not in preserve]
        for entry in names:
            deadline.check(cleanup=cleanup)
            _remove_tree_fd(child, entry, deadline, cleanup=cleanup, depth=depth + 1)
        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise IndexUnavailable("index_unavailable", "Cache removal directory changed")
        os.rmdir(name, dir_fd=parent)
    finally:
        os.close(child)


def _remove(parent, name, deadline, *, cleanup=False):
    _remove_tree_fd(parent, name, deadline, cleanup=cleanup)


def _clear_key(fd, deadline, *, cleanup=False):
    """Drop native contents while keeping the durable attempt marker."""
    preserve = {"meta.json"}
    with os.scandir(fd) as entries:
        names = [entry.name for entry in entries if entry.name not in preserve]
    for name in names:
        deadline.check(cleanup=cleanup)
        _remove_tree_fd(fd, name, deadline, cleanup=cleanup)


def _metadata(fd):
    try:
        f = _file(fd, "meta.json")
    except FileNotFoundError:
        return None
    try:
        if os.fstat(f).st_size > 1024:
            raise ValueError("Oversized cache metadata")
        pairs = json.loads(os.read(f, 1025), object_pairs_hook=list)
        if not isinstance(pairs, list) or len(pairs) != 3 or len({k for k, _ in pairs}) != 3:
            raise ValueError("Invalid cache metadata")
        value = dict(pairs)
        if (set(value) != {"schema", "attempted", "last_used_ns"} or type(value["schema"]) is not int or value["schema"] != SCHEMA
                or type(value["attempted"]) is not bool or type(value["last_used_ns"]) is not int
                or value["last_used_ns"] < 0):
            raise ValueError("Invalid cache metadata")
        return value
    except (ValueError, TypeError, UnicodeError) as exc:
        raise IndexUnavailable("index_unavailable", "Invalid index cache metadata") from exc
    finally:
        os.close(f)


def _normalize_io(function):
    """Translate filesystem/runtime failures to the indexed fixed-reason contract."""
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except IndexUnavailable:
            raise
        except (OSError, RuntimeError, RecursionError) as exc:
            raise IndexUnavailable("index_unavailable", "Index cache operation is unavailable") from exc
    wrapped.__name__ = function.__name__
    wrapped.__doc__ = function.__doc__
    return wrapped


def _normalize_context(function):
    @contextlib.contextmanager
    def wrapped(*args, **kwargs):
        try:
            with function(*args, **kwargs) as value:
                yield value
        except IndexUnavailable:
            raise
        except (OSError, RuntimeError, RecursionError) as exc:
            raise IndexUnavailable("index_unavailable", "Index cache operation is unavailable") from exc
    wrapped.__name__ = function.__name__
    wrapped.__doc__ = function.__doc__
    return wrapped


class Cache:
    @_normalize_io
    def __init__(self, root: Path, workspace: Path, plugin: Path):
        self._lease_thread = None
        if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
            raise IndexUnavailable("index_unavailable", "Index cache requires POSIX no-follow and locking")
        if not root.is_absolute() or ".." in root.parts:
            raise IndexUnavailable("index_unavailable", "Index cache must be an absolute private external directory")
        # Resolve once, then retain the canonical path and owned directory FD.
        # Existing links anywhere in the requested cache chain are rejected.
        for ancestor in (root, *root.parents):
            if ancestor.is_symlink():
                raise IndexUnavailable("index_unavailable", "Index cache path contains a symbolic link")
        self.path = root.resolve(strict=False)
        for boundary in (workspace, plugin):
            boundary_identity = filesystem_identity(boundary)
            contained = (within_workspace(self.path, boundary_identity) if self.path.exists() else
                         any(filesystem_identity(p) == boundary_identity for p in self.path.parents if p.exists()))
            if contained:
                raise IndexUnavailable("index_unavailable", "Index cache must be outside workspace and plugin")
        parent = os.open("/", DIR_FLAGS)
        try:
            for part in self.path.parts[1:]:
                with contextlib.suppress(FileExistsError):
                    os.mkdir(part, 0o700, dir_fd=parent)
                child = os.open(part, DIR_FLAGS, dir_fd=parent)
                os.close(parent)
                parent = child
                info = os.fstat(parent)
                if info.st_uid not in (0, os.getuid()) or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
                    raise IndexUnavailable("index_unavailable", "Unsafe index cache ancestor")
            _owned(os.fstat(parent), private=True, directory=True)
            self.fd = parent
            parent = None
            self.identity = filesystem_identity_fd(self.fd)
            try:
                self.entries = _directory(self.fd, "entries", create=True, private=True)
            except BaseException:
                os.close(self.fd)
                self.fd = None
                raise
        finally:
            if parent is not None:
                os.close(parent)

    @_normalize_io
    def close(self):
        if self._lease_thread is not None:
            raise IndexUnavailable("index_unavailable", "Cannot close index cache with an active lease")
        for name in ("entries", "fd"):
            fd = getattr(self, name, None)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @_normalize_io
    def validate(self):
        if self.fd is None or filesystem_identity_fd(self.fd) != self.identity:
            raise IndexUnavailable("index_unavailable", "Index cache anchor is closed or changed")
        current = os.open(self.path, DIR_FLAGS)
        try:
            _owned(os.fstat(current), private=True, directory=True)
            if filesystem_identity_fd(current) != self.identity:
                raise IndexUnavailable("index_unavailable", "Index cache root changed")
        finally:
            os.close(current)
        current = _directory(self.fd, "entries", private=True)
        try:
            if filesystem_identity_fd(current) != filesystem_identity_fd(self.entries):
                raise IndexUnavailable("index_unavailable", "Index entries directory changed")
        finally:
            os.close(current)

    @_normalize_io
    def _lock(self, name, deadline, *, wait=LOCK_SECONDS):
        import fcntl

        fd = _file(self.fd, name, os.O_RDWR | os.O_CREAT)
        stop = min(deadline.work_ends, deadline.clock() + wait)
        try:
            while True:
                self.validate()
                deadline.check()
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return fd
                except BlockingIOError:
                    if deadline.clock() >= stop:
                        raise IndexUnavailable("lock_timeout", "Another indexed query holds the cache lease") from None
                    time.sleep(min(0.01, max(0, stop - deadline.clock())))
        except BaseException:
            os.close(fd)
            raise

    @_normalize_context
    @contextlib.contextmanager
    def lease(self, key, deadline, *, wait=LOCK_SECONDS):
        key = _key(key)
        lock_started = deadline.clock()
        global_lock = self._lock("scheduler.lock", deadline, wait=wait)
        key_lock = None
        key_fd = None
        try:
            self._lease_thread = threading.get_ident()
            key_lock = self._lock("key-" + key + ".lock", deadline,
                                  wait=max(0, wait - (deadline.clock() - lock_started)))
            self.prune(deadline, exclude=key, incoming=True)
            key_fd = _directory(self.entries, key, create=True, private=True)
            yield Lease(self, key, key_fd, deadline, global_lock)
        finally:
            try:
                if key_lock is not None:
                    try:
                        os.stat(key, dir_fd=self.entries, follow_symlinks=False)
                    except FileNotFoundError:
                        self._remove_key_lock(key, key_lock)
            finally:
                self._lease_thread = None
                for fd in (key_fd, key_lock, global_lock):
                    if fd is not None:
                        os.close(fd)

    def _remove_key_lock(self, key, fd):
        """Global lease excludes new key-lock waiters while this inode is removed."""
        name = "key-" + key + ".lock"
        current = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != filesystem_identity_fd(fd):
            raise IndexUnavailable("index_unavailable", "Index lock file changed")
        os.unlink(name, dir_fd=self.fd)

    @_normalize_io
    def prune(self, deadline, *, exclude=None, incoming=False, max_keys=RETAINED_KEYS, max_bytes=RETAINED_BYTES):
        """Requires caller's global lease; never removes a contended key."""
        if self._lease_thread != threading.get_ident():
            raise IndexUnavailable("index_unavailable", "Cache cleanup requires the caller's global lease")
        candidates = []
        with os.scandir(self.entries) as entries:
            names = [entry.name for entry in entries]
        if len(names) > STRINGS_COUNT:
            raise IndexUnavailable("cache_limit", "Index key count exceeds traversal policy")
        total = 0
        bad = []
        for name in names:
            try:
                _key(name)
            except ValueError:
                # Private store noise (for example Finder metadata) is not a
                # key and cannot block all indexed work. Remove only the name
                # itself, without following/opening a leaf.
                try:
                    _remove_tree_fd(self.entries, name, deadline)
                except IndexUnavailable as exc:
                    if exc.reason == "index_deadline":
                        raise
                    continue
                except (OSError, RuntimeError, RecursionError):
                    continue
                continue
            try:
                fd = _directory(self.entries, name, private=True)
                try:
                    if name != exclude:
                        try:
                            inactive_lock = self._lock("key-" + name + ".lock", deadline, wait=0)
                        except IndexUnavailable as exc:
                            if exc.reason != "lock_timeout":
                                raise
                        else:
                            try:
                                try:
                                    _remove_tree_fd(fd, "tmp", deadline)
                                except IndexUnavailable as exc:
                                    if exc.reason == "index_deadline":
                                        raise
                                except (OSError, RuntimeError, RecursionError):
                                    pass
                            finally:
                                os.close(inactive_lock)
                    size, _ = _scan(fd, deadline, skip_tmp=True)
                    meta = _metadata(fd)
                    total += size
                    candidates.append((meta["last_used_ns"] if meta else 0, name, size))
                finally:
                    os.close(fd)
            except IndexUnavailable as exc:
                if exc.reason == "index_deadline":
                    raise
                if name != exclude:
                    bad.append(name)
            except (OSError, RuntimeError, RecursionError):
                if name != exclude:
                    bad.append(name)
        unresolved_bad = set()
        for name in bad:
            try:
                lock = self._lock("key-" + name + ".lock", deadline, wait=0)
            except IndexUnavailable as exc:
                if exc.reason == "lock_timeout":
                    unresolved_bad.add(name)
                    continue
                if exc.reason == "index_deadline":
                    raise
                unresolved_bad.add(name)
                continue
            try:
                _remove(self.entries, name, deadline)
                self._remove_key_lock(name, lock)
            except IndexUnavailable as exc:
                if exc.reason == "index_deadline":
                    raise
                # A bad unrelated key is quarantined from this operation; it
                # must not make every other key unusable.
                unresolved_bad.add(name)
            except (OSError, RuntimeError, RecursionError):
                unresolved_bad.add(name)
            finally:
                os.close(lock)
        keys = len(candidates) + len(unresolved_bad) + int(incoming and exclude not in {name for _, name, _ in candidates})
        # An unremovable key has unknown size: conservatively count one full
        # key against the retained target rather than claiming capacity.
        total += len(unresolved_bad) * KEY_BYTES
        current_size = next((size for _, name, size in candidates if name == exclude), 0)
        reserve = max(0, KEY_BYTES - current_size) if incoming else 0
        for _, name, size in sorted(candidates):
            if keys <= max_keys and total + reserve <= max_bytes:
                break
            if name == exclude:
                continue
            try:
                lock = self._lock("key-" + name + ".lock", deadline, wait=0)
            except IndexUnavailable as exc:
                if exc.reason == "lock_timeout":
                    continue
                raise
            try:
                _remove(self.entries, name, deadline)
                self._remove_key_lock(name, lock)
                total -= size
                keys -= 1
            finally:
                os.close(lock)
        if keys > max_keys or total + reserve > max_bytes:
            raise IndexUnavailable("cache_limit", "Cache retention target cannot be safely satisfied")


class Lease:
    def __init__(self, cache, key, fd, deadline, global_lock_fd):
        self.cache, self.key, self.fd, self.deadline = cache, key, fd, deadline
        # The LSP integration passes this CLOEXEC descriptor explicitly to the
        # native helper so the global lease survives if the Python coordinator dies.
        self.global_lock_fd = global_lock_fd

    @property
    def path(self):
        return self.cache.path / "entries" / self.key

    @_normalize_io
    def validate(self):
        self.cache.validate()
        current = _directory(self.cache.entries, self.key, private=True)
        try:
            if filesystem_identity_fd(current) != filesystem_identity_fd(self.fd):
                raise IndexUnavailable("index_unavailable", "Index key directory changed")
        finally:
            os.close(current)

    @_normalize_io
    def usage(self, *, active=False, cleanup=False):
        """Return sampled bytes and raw nonempty .idx count.

        ``persisted_shards`` is only a zero/nonzero first-budget signal. It is
        not validated progress; retry decisions must compare
        ``lsp_index_coverage.Coverage.covered`` values.
        """
        self.validate()
        # A live native writer atomically replaces regular shard files. Use
        # the safely opened current file for sampled sizes; strict inventories
        # used for classification/cleanup keep the identity-change rejection.
        persistent, shards = _scan(self.fd, self.deadline, active=active, cleanup=cleanup, skip_tmp=True)
        transient = 0
        try:
            tmp = _directory(self.fd, "tmp", private=True)
        except FileNotFoundError:
            pass
        else:
            try:
                try:
                    transient, _ = _scan(tmp, self.deadline, active=active, cleanup=cleanup)
                except IndexUnavailable as exc:
                    if exc.reason == "cache_limit":
                        raise IndexUnavailable("index_transient_limit", "Transient traversal exceeded sampled policy") from exc
                    raise
            finally:
                os.close(tmp)
        return {"bytes": persistent + transient, "persistent_bytes": persistent, "transient_bytes": transient,
                "persisted_shards": shards}

    @_normalize_io
    def begin_attempt(self):
        self.deadline.check()
        self.validate()
        self.clear_tmp()
        before = self.usage()
        meta = _metadata(self.fd)
        new = before["persisted_shards"] == 0 and not (meta and meta["attempted"])
        total_seconds = NEW_KEY_SECONDS if new else EXISTING_KEY_SECONDS
        # Rebase the shared object in place: a ResourceGuard constructed with
        # the caller's original Deadline must observe the classified budget.
        self.deadline.rebase(total_seconds)
        _atomic(self.fd, "meta.json", json.dumps({"schema": SCHEMA, "attempted": True,
                                                 "last_used_ns": time.time_ns()}, sort_keys=True).encode())
        self.validate()
        return {"classification": "new" if new else "existing", "total_seconds": total_seconds,
                "persisted_shards_before": before["persisted_shards"]}

    @_normalize_io
    def write_cdb(self, raw):
        if not isinstance(raw, bytes) or len(raw) > CDB_BYTES:
            raise IndexUnavailable("compile_db_unsupported", "Compilation database exceeds input policy")
        self.deadline.check()
        self.validate()
        _atomic(self.fd, "compile_commands.json", raw)
        self.validate()

    @_normalize_io
    def prepare_tmp(self):
        self.deadline.check()
        self.validate()
        self.clear_tmp()
        fd = _directory(self.fd, "tmp", create=True, private=True)
        os.close(fd)
        return self.path / "tmp"

    @_normalize_io
    def clear_tmp(self):
        """Only after the server has exited; include transients in live usage."""
        self.validate()
        with contextlib.suppress(FileNotFoundError):
            _remove_tree_fd(self.fd, "tmp", self.deadline, cleanup=True)

    @_normalize_io
    def check_disk(self):
        usage = self.usage(active=True)
        if usage["persistent_bytes"] > KEY_BYTES:
            raise IndexUnavailable("cache_limit", "Persistent index exceeded sampled disk target")
        if usage["transient_bytes"] > TRANSIENT_BYTES:
            raise IndexUnavailable("index_transient_limit", "Transient preamble space exceeded sampled disk target")

    @_normalize_io
    def discard(self, failure_reason="index_resource_limit"):
        """Caller must stop and reap the native server before discarding its key."""
        if failure_reason not in FAILURE_REASONS:
            raise ValueError("Invalid discarded index failure reason")
        self.validate()
        # Preserve the attempt-consumed marker across failure cleanup so a
        # zero-shard retry cannot repeatedly obtain the 30-second grant. Clear
        # bulky native data first so ENOSPC cannot prevent cleanup; meta.json
        # remains pinned by _clear_key and still records the consumed attempt.
        _clear_key(self.fd, self.deadline, cleanup=True)
        _atomic(self.fd, "meta.json", json.dumps({"schema": SCHEMA, "attempted": True,
                                                 "last_used_ns": time.time_ns()}, sort_keys=True).encode())
        _atomic(self.fd, "failure.json", json.dumps({"reason": failure_reason}, sort_keys=True).encode())
