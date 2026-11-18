"""Bounded, non-executing discovery for automatic C/C++ background indexing."""
from __future__ import annotations

import errno
import json
import os
import re
import shlex
import stat
from dataclasses import dataclass
from pathlib import Path

from intel_runtime import filesystem_identity, within_workspace
from lsp_index_coverage import SourceIdentity, source_identity
from lsp_index_policy import CDB_BYTES, CDB_ENTRIES, IndexUnavailable
from lsp_source import read_source


@dataclass(frozen=True)
class CompileDatabase:
    root: Path
    path: Path
    raw: bytes
    sources: tuple[SourceIdentity, ...]
    compiler_identities: tuple[tuple[str, int, int], ...]
    directories: tuple[Path, ...]
    cdb_identity: tuple[int, int]

    @property
    def source_key(self):
        return {"cdb": str(self.path),
                "sources": [str(item.path) for item in self.sources]}


def _unsupported(message):
    raise IndexUnavailable("compile_db_unsupported", message)


def _config_unsupported(message):
    raise IndexUnavailable("config_unsupported", message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(_value):
    raise ValueError("non-finite JSON number")


def _within(path: Path, root: Path, root_identity) -> bool:
    try:
        return within_workspace(path, root_identity)
    except (OSError, RuntimeError):
        return False


def _lstat(path: Path):
    try:
        return path.lstat()
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            return None
        raise


def _read_candidate(root: Path, candidate: Path, deadline):
    deadline.check()
    try:
        fixed = candidate.resolve(strict=True)
        if not _within(fixed, root, filesystem_identity(root)):
            _unsupported("Compilation database resolves outside the explicit workspace")
        before = fixed.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > CDB_BYTES:
            _unsupported("Compilation database is not a bounded regular file")
        relative = fixed.relative_to(root)
        _, observed, text = read_source(root, str(relative), CDB_BYTES)
        after = observed.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise IndexUnavailable("index_inputs_changed", "Compilation database changed while read")
        raw = text.encode("utf-8", errors="strict")
        if len(raw) > CDB_BYTES:
            _unsupported("Compilation database exceeds the input byte policy")
        return fixed, raw, (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    except IndexUnavailable:
        raise
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        _unsupported("Compilation database cannot be read safely: " + type(exc).__name__)


def _config_inventory(root: Path, source_paths, env, deadline):
    candidates = set()
    for start in {root, *(Path(item).parent for item in source_paths)}:
        current = start
        while True:
            deadline.check()
            candidates.add(current / ".clangd")
            if _lstat(current / "compile_flags.txt") is not None:
                _unsupported("compile_flags.txt is present in an effective discovery chain")
            if current == current.parent:
                break
            current = current.parent
    home = env.get("HOME")
    if not home or not Path(home).is_absolute():
        _config_unsupported("Cannot establish the user's clangd configuration path")
    if sys_platform() == "darwin":
        candidates.add(Path(home) / "Library/Preferences/clangd/config.yaml")
    else:
        config_home = env.get("XDG_CONFIG_HOME", str(Path(home) / ".config"))
        if not Path(config_home).is_absolute():
            _config_unsupported("XDG_CONFIG_HOME is not absolute")
        candidates.add(Path(config_home) / "clangd/config.yaml")
    inventory = []
    for candidate in sorted(candidates, key=lambda path: os.fsencode(str(path))):
        deadline.check()
        try:
            info = _lstat(candidate)
        except OSError:
            _config_unsupported("Cannot safely inspect clangd configuration presence")
        if info is not None:
            _config_unsupported("A clangd configuration file is present")
        inventory.append((str(candidate), None))
    return tuple(inventory)


def sys_platform():
    import sys
    return sys.platform


def _find_cdb(root: Path, source: Path, deadline):
    root_identity = filesystem_identity(root)
    current = source.parent
    while True:
        deadline.check()
        directories = (current, current / "build")
        for directory in directories:
            if not _within(directory, root, root_identity):
                continue
            flags = _lstat(directory / "compile_flags.txt")
            if flags is not None:
                _unsupported("compile_flags.txt is present in the CDB discovery chain")
            candidate = directory / "compile_commands.json"
            if _lstat(candidate) is not None:
                path, raw, stamp = _read_candidate(root, candidate, deadline)
                return path, raw, stamp, tuple(directories)
        if current == root:
            return None
        current = current.parent
        if not _within(current, root, root_identity):
            return None


def _entry_paths(entry, root: Path, root_identity):
    if not isinstance(entry, dict) or set(entry) - {"directory", "file", "command", "arguments", "output"}:
        _unsupported("Compilation database entry has unsupported fields")
    directory = entry.get("directory")
    file_value = entry.get("file")
    if not isinstance(directory, str) or not directory or not isinstance(file_value, str) or not file_value:
        _unsupported("Compilation database entry lacks directory or file")
    directory_path = Path(directory)
    if not directory_path.is_absolute():
        _unsupported("Compilation database directory must be absolute")
    try:
        fixed_directory = directory_path.resolve(strict=True)
        if not fixed_directory.is_dir() or not _within(fixed_directory, root, root_identity):
            _unsupported("Compilation database directory is outside the explicit workspace")
        source_path = Path(file_value)
        if not source_path.is_absolute():
            source_path = fixed_directory / source_path
        source = source_identity(source_path)
        if not _within(source.path, root, root_identity):
            _unsupported("Compilation database source is outside the explicit workspace")
        return fixed_directory, source
    except IndexUnavailable:
        raise
    except (OSError, RuntimeError, ValueError, UnicodeError) as exc:
        _unsupported("Compilation database source path is unavailable: " + type(exc).__name__)


def _argv(entry):
    if ("arguments" in entry) == ("command" in entry):
        _unsupported("Compilation database must contain exactly one of command or arguments")
    arguments = entry.get("arguments")
    if arguments is not None:
        if not isinstance(arguments, list) or not arguments or any(not isinstance(arg, str) for arg in arguments):
            _unsupported("Compilation database arguments are invalid")
        argv = arguments
    else:
        command = entry.get("command")
        if not isinstance(command, str) or not command:
            _unsupported("Compilation database command is invalid")
        try:
            argv = shlex.split(command, posix=True)
        except ValueError:
            _unsupported("Compilation database command quoting is invalid")
    if not argv or not Path(argv[0]).is_absolute():
        _unsupported("Compiler argv[0] must be absolute")
    if any(arg.startswith("@") for arg in argv):
        _unsupported("Compiler response files are unsupported")
    return argv


def _compiler_identity(argv0):
    try:
        path = Path(argv0).resolve(strict=True)
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or not os.access(path, os.X_OK):
            _unsupported("Compilation database compiler is not an executable regular file")
        return (str(path), info.st_dev, info.st_ino)
    except IndexUnavailable:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        _unsupported("Compilation database compiler cannot be pinned: " + type(exc).__name__)


_STRUCTURAL_TOKENS = re.compile(rb'"[^"\\]*(?:\\[\s\S][^"\\]*)*(?:"|\\?$)|[{}\[\],]')


def _bounded_structure(raw, deadline):
    """C-speed token scan bounds allocations; stdlib still validates JSON."""
    deadline.check()
    max_containers = CDB_ENTRIES * 4 + 1
    max_strings = CDB_ENTRIES * 32
    max_commas = CDB_ENTRIES * 64
    if b'"' not in raw and raw.count(b',') > max_commas:
        _unsupported("Compilation database structural allocation policy exceeded (literal count)")
    containers = strings = commas = depth = 0
    for count, match in enumerate(_STRUCTURAL_TOKENS.finditer(raw)):
        if count % 1024 == 0:
            deadline.check()
        token = raw[match.start()]
        if token == 34:
            strings += 1
        elif token in (91, 123):
            containers += 1
            depth += 1
        elif token in (93, 125):
            depth -= 1
        else:
            commas += 1
        if containers > max_containers:
            _unsupported("Compilation database structural allocation policy exceeded (container count)")
        if strings > max_strings:
            _unsupported("Compilation database structural allocation policy exceeded (string count)")
        if depth > 64:
            _unsupported("Compilation database structural allocation policy exceeded (nesting depth)")
        if commas > max_commas:
            _unsupported("Compilation database structural allocation policy exceeded (literal count)")
    deadline.check()


def _bounded_int(value):
    if len(value) > 32:
        _unsupported("Compilation database integer literal exceeds 32 characters")
    return int(value)


def _bounded_float(value):
    if len(value) > 32:
        _unsupported("Compilation database float literal exceeds 32 characters")
    return float(value)


def discover_compile_database(root: Path, source: Path, env: dict[str, str], deadline):
    found = _find_cdb(root, source, deadline)
    if found is None:
        raise IndexUnavailable("no_compile_db", "No supported compile_commands.json was found in the workspace")
    path, raw, stamp, _directories = found
    _bounded_structure(raw, deadline)
    object_count = 0

    def bounded_pairs(pairs):
        nonlocal object_count
        deadline.check()
        object_count += 1
        if object_count > CDB_ENTRIES:
            _unsupported("Compilation database exceeds the object policy")
        return _pairs(pairs)

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=bounded_pairs, parse_constant=_constant,
                           parse_int=_bounded_int, parse_float=_bounded_float)
    except (ValueError, UnicodeError, RecursionError):
        _unsupported("Compilation database JSON is invalid")
    if not isinstance(value, list) or not value or len(value) > CDB_ENTRIES:
        _unsupported("Compilation database is empty or exceeds the entry policy")
    root_identity = filesystem_identity(root)
    sources, compiler_ids, checked_dirs = [], set(), []
    for entry in value:
        deadline.check()
        directory, source_identity_value = _entry_paths(entry, root, root_identity)
        argv = _argv(entry)
        sources.append(source_identity_value)
        compiler_ids.add(_compiler_identity(argv[0]))
        checked_dirs.append(directory)
        for candidate_dir in (directory, directory / "build"):
            if _lstat(candidate_dir / "compile_flags.txt") is not None:
                _unsupported("compile_flags.txt is present in a compilation directory")
    for item in (source, *(identity.path for identity in sources)):
        current = Path(item).parent
        while _within(current, root, root_identity):
            deadline.check()
            if _lstat(current / "compile_flags.txt") is not None:
                _unsupported("compile_flags.txt is present in a source discovery chain")
            if current == root:
                break
            current = current.parent
    if len({source.identity for source in sources}) != len(sources):
        _unsupported("Compilation database has duplicate or ambiguous translation units")
    config = _config_inventory(root, [str(item.path) for item in sources] + [str(source)]
                               + [str(item / "_") for item in checked_dirs], env, deadline)
    return CompileDatabase(root, path, raw, tuple(sources), tuple(sorted(compiler_ids)), tuple(checked_dirs), stamp[:2]), stamp, config


def config_still_absent(inventory):
    for name, expected in inventory:
        try:
            current = _lstat(Path(name))
        except OSError:
            return False
        if current is not None or expected is not None:
            return False
    return True


def cdb_unchanged(database: CompileDatabase, stamp):
    try:
        info = database.path.stat()
        relative = database.path.relative_to(database.root)
        _, observed, text = read_source(database.root, str(relative), CDB_BYTES)
        raw = text.encode("utf-8", errors="strict")
        final = observed.stat()
        return ((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) == stamp
                and (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) == stamp
                and len(raw) <= CDB_BYTES and raw == database.raw)
    except (OSError, RuntimeError, UnicodeError, ValueError):
        return False
