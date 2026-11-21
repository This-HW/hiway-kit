"""Bounded clangd CdIx metadata coverage; native owns symbol/ref correctness.

Only actually observed schema versions are accepted. Unknown formats safely
degrade. Filename basenames select candidates; source identities prove coverage.
"""
from __future__ import annotations

import contextlib
import os
import re
import stat
import struct
import sys
import unicodedata
import zlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from lsp_index_cache import _directory, _file, _owned
from lsp_index_policy import (
    CDB_ENTRIES,
    COMMAND_ARGS,
    KEY_BYTES,
    SHARD_BYTES,
    SHARD_VERSIONS,
    STRINGS_BYTES,
    STRINGS_COUNT,
    IndexUnavailable,
)


@dataclass(frozen=True)
class SourceIdentity:
    path: Path
    device: int
    inode: int

    @property
    def identity(self):
        return self.device, self.inode


def source_identity(path: Path) -> SourceIdentity:
    """Shared by the CDB reader and shard URI matcher, including aliases."""
    if not path.is_absolute():
        raise ValueError("Compilation source path must be absolute")
    str(path).encode("utf-8", errors="strict")
    fixed = path.resolve(strict=True)
    info = fixed.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Compilation source is not regular")
    return SourceIdentity(fixed, info.st_dev, info.st_ino)


def uri_identity(uri: str) -> SourceIdentity:
    parts = urlsplit(uri)
    if (parts.scheme != "file" or parts.netloc or parts.query or parts.fragment
            or re.search(r"%(?![0-9a-fA-F]{2})", parts.path)):
        raise ValueError("Invalid local source URI")
    decoded = unquote(parts.path, encoding="utf-8", errors="strict")
    if "\0" in decoded:
        raise ValueError("Invalid local source URI")
    return source_identity(Path(decoded))


def _basename(name):
    return unicodedata.normalize("NFC", name).casefold() if sys.platform == "darwin" else name


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError("Truncated index metadata")
        raw = self.data[self.pos:self.pos + count]
        self.pos += count
        return raw

    def varint(self):
        value = 0
        for i in range(5):
            byte = self.take(1)[0]
            if i == 4 and byte > 15:
                raise ValueError("Invalid metadata varint")
            value |= (byte & 127) << (i * 7)
            if byte < 128:
                return value
        raise ValueError("Invalid metadata varint")

    @property
    def done(self):
        return self.pos == len(self.data)


def decode_metadata(raw: bytes, deadline) -> tuple[SourceIdentity, bool]:
    deadline.check()
    if len(raw) > SHARD_BYTES or len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"CdIx":
        raise ValueError("Invalid index shard")
    if struct.unpack_from("<I", raw, 4)[0] != len(raw) - 8:
        raise ValueError("Invalid index shard length")
    reader = Reader(raw[12:])
    known = {b"meta", b"stri", b"srcs", b"cmdl", b"symb", b"refs", b"rela"}
    chunks = {}
    while not reader.done:
        deadline.check()
        tag = reader.take(4)
        count = struct.unpack("<I", reader.take(4))[0]
        if tag not in known or tag in chunks:
            raise ValueError("Unknown or duplicate index chunk")
        chunks[tag] = reader.take(count)
        if count % 2 and reader.take(1) != b"\0":
            raise ValueError("Invalid RIFF odd-byte padding")
    if not {b"meta", b"stri", b"srcs", b"cmdl", b"symb", b"refs"} <= chunks.keys():
        raise ValueError("Missing index metadata chunk")
    if len(chunks[b"meta"]) != 4 or struct.unpack("<I", chunks[b"meta"])[0] not in SHARD_VERSIONS:
        raise ValueError("Unobserved index schema version")
    table = Reader(chunks[b"stri"])
    count = struct.unpack("<I", table.take(4))[0]
    compressed = table.take(len(table.data) - table.pos)
    if count > STRINGS_BYTES:
        raise ValueError("Index string table exceeds policy")
    if count:
        decompressor = zlib.decompressobj()
        text = decompressor.decompress(compressed, STRINGS_BYTES + 1)
        if (len(text) != count or decompressor.unconsumed_tail or decompressor.unused_data
                or not decompressor.eof):
            raise ValueError("Invalid or oversized compressed index metadata")
    else:
        text = compressed
    deadline.check()
    if len(text) > STRINGS_BYTES or not text.endswith(b"\0"):
        raise ValueError("Invalid index string table")
    if text.count(b"\0") > STRINGS_COUNT + 1:
        raise ValueError("Index string count exceeds policy")
    parts = text[:-1].split(b"\0")
    if len(parts) > STRINGS_COUNT:
        raise ValueError("Index string count exceeds policy")
    strings = [s.decode("utf-8", errors="strict") for s in parts]

    def string(reader):
        index = reader.varint()
        if index >= len(strings):
            raise ValueError("Invalid index string reference")
        return strings[index]

    reader = Reader(chunks[b"srcs"])
    tus = []
    source_count, had_errors = 0, False
    while not reader.done:
        deadline.check()
        source_count += 1
        if source_count > STRINGS_COUNT:
            raise ValueError("Index source count exceeds policy")
        flags = reader.take(1)[0]
        if flags & ~3:
            raise ValueError("Unknown index source flag")
        uri = string(reader)
        digest = reader.take(8)
        includes = reader.varint()
        if includes > STRINGS_COUNT:
            raise ValueError("Index include count exceeds policy")
        for _ in range(includes):
            string(reader)
        had_errors |= bool(flags & 2)
        if flags & 1:
            if not any(digest):
                raise ValueError("Empty translation-unit digest")
            tus.append(uri_identity(uri))
    if len(tus) != 1:
        raise ValueError("Index shard lacks one unambiguous translation unit")
    reader = Reader(chunks[b"cmdl"])
    directory = string(reader)
    if not Path(directory).is_absolute():
        raise ValueError("Invalid index command directory")
    count = reader.varint()
    if not 1 <= count <= COMMAND_ARGS:
        raise ValueError("Index command count exceeds policy")
    arguments = [string(reader) for _ in range(count)]
    if not reader.done:
        raise ValueError("Trailing index command bytes")
    matched = False
    for argument in arguments:
        deadline.check()
        if argument.startswith("-"):
            continue
        path = Path(argument)
        path = path if path.is_absolute() else Path(directory) / path
        # Check candidate spelling before filesystem access: arbitrary command
        # argument values are not an invitation to inspect unrelated paths.
        if _basename(path.name) != _basename(tus[0].path.name):
            continue
        if source_identity(path).identity == tus[0].identity:
            matched = True
    if not matched:
        raise ValueError("Index command source differs from TU metadata")
    return tus[0], had_errors


@dataclass(frozen=True)
class Coverage:
    total: int
    covered: int
    complete: bool
    reason: str | None


def certify(key_fd: int, sources: list[SourceIdentity], deadline, *, validate_anchor=None) -> Coverage:
    """No readiness claim: caller additionally needs progress-end and full response.

    All shard I/O is read-only and relative to the caller's pinned key FD. An
    unreadable/unknown/corrupt candidate never counts as coverage. Native owns
    symbols/refs body decoding; this only validates source/command metadata.
    """
    if not sources or len(sources) > CDB_ENTRIES or len({s.identity for s in sources}) != len(sources):
        raise IndexUnavailable("compile_db_unsupported", "Compilation scope is empty, oversized or ambiguous")
    expected = {s.identity for s in sources}
    basenames = {_basename(s.path.name) for s in sources}
    seen, had_errors, invalid, byte_count, count = set(), False, False, 0, 0
    fd = os.dup(key_fd)
    try:
        # Relaxed mode checks for clangd-owned shards are safe only while the
        # containing key directory itself remains private and caller-owned.
        _owned(os.fstat(fd), private=True, directory=True)
        if validate_anchor:
            validate_anchor()
        for name in (".cache", "clangd", "index"):
            child = _directory(fd, name, check_mode=False)
            os.close(fd)
            fd = child
        with os.scandir(fd) as entries:
            for entry in entries:
                deadline.check()
                count += 1
                if count > STRINGS_COUNT:
                    raise ValueError("Index entry count exceeds policy")
                if not entry.name.endswith(".idx"):
                    continue
                name = entry.name[:-4].rsplit(".", 1)
                if len(name) != 2 or _basename(name[0]) not in basenames:
                    continue
                if re.fullmatch(r"[0-9A-Fa-f]{16}", name[1]) is None:
                    raise ValueError("Unknown shard filename scheme")
                # clangd inherits the consumer's umask and may create 0775
                # directories/0664 shards. The enclosing key dir is private;
                # ownership, inode type, no-follow and hardlink checks remain.
                f = _file(fd, entry.name, check_mode=False)
                try:
                    before = os.fstat(f)
                    byte_count += before.st_size
                    if before.st_size > SHARD_BYTES or byte_count > KEY_BYTES:
                        raise ValueError("Index metadata read budget exceeded")
                    with os.fdopen(f, "rb", closefd=False) as stream:
                        raw = stream.read(SHARD_BYTES + 1)
                    source, errors = decode_metadata(raw, deadline)
                    after = os.fstat(f)
                    bound = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                    def stamp(s):
                        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns
                    if stamp(before) != stamp(after) or stamp(before) != stamp(bound):
                        raise ValueError("Index shard changed while inspected")
                    if source.identity not in expected or source.identity in seen:
                        raise ValueError("Index shard TU mapping is unexpected or duplicated")
                    seen.add(source.identity)
                    had_errors |= errors
                finally:
                    os.close(f)
        if validate_anchor:
            validate_anchor()
    except IndexUnavailable as exc:
        if exc.reason == "index_deadline":
            raise
        invalid = True
    except (OSError, ValueError, UnicodeError, struct.error, zlib.error, RuntimeError, RecursionError):
        invalid = True
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)
    reason = "index_had_errors" if had_errors else ("index_coverage_unverified" if invalid or seen != expected else None)
    return Coverage(len(expected), len(seen), reason is None, reason)
