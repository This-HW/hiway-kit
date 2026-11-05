"""JSON AST rule preview and snapshot-free rule-test with trusted installed ast-grep.

Preview never writes consumer sources. It reads bounded sources through pinned
directory descriptors, copies them to a private temp tree, scans only the copy
and rebuilds bytes from validated replacement offsets until a fixed point. A
fixed point is not semantic correctness. Executing the engine is not sandboxed.
"""
from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import re
import selectors
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import code_intel
from bounded_process import ProcessBudget
from intel_runtime import print_result

# Policy values (plan-control approved). The rule module owns them.
MINIMUM_ENGINE = (0, 51, 0)
TESTED_VERSION = "0.51.0"
MAX_PASSES_DEFAULT = 8
MAX_PASSES_LIMIT = 32
MAX_FILES = 200
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_FILE_BYTES = 1024 * 1024
MAX_RULE_BYTES = 64 * 1024
MAX_CASES_BYTES = 256 * 1024
# Internal traversal bounds, not policy values: a tree of empty directories or
# a deep chain must fail fast instead of consuming descriptors or the deadline.
MAX_DIRECTORY_ENTRIES = 20000
MAX_DEPTH = 64

RULE_KEYS = ("id", "language", "rule", "constraints", "fix", "message", "severity", "note", "metadata")
TEST_KEYS = frozenset({"id", "valid", "invalid"})
FIX_EXPANSION_KEYS = frozenset({"expandStart", "expandEnd"})
RULE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
# Native built-in rule ids (observed in 0.51.0): `--hint=<id>` with a caller
# rule of the same name also enables the built-in, whose rows would then pass
# the unknown-id check. Reserve them rather than filter native output.
RESERVED_RULE_IDS = frozenset({"no-suppress-all", "unused-suppression"})
NO_IGNORE = ("hidden", "dot", "vcs", "parent", "global", "exclude")
IGNORE_MARKER = b"ast-grep-ignore"
INT64_BOUND = 2 ** 63
READ_CHUNK = 64 * 1024
DETAIL_CHARS = 2000
STATUS_LINE = re.compile(r"(PASS|FAIL) ([A-Za-z0-9][A-Za-z0-9_.-]*)  ([.NM]+)")
RUNNING_LINE = re.compile(r"Running (\d+) tests")
SUMMARY = re.compile(r"(?:test result: ok\.|Error: test failed\.) (\d+) passed; (\d+) failed;")
OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
DIR_FLAGS = OPEN_FLAGS | os.O_DIRECTORY
# Copy files are opened read-write without O_TRUNC: identity is checked before
# any byte changes, and the same descriptor reads the bytes back.
COPY_FLAGS = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
# Rendered in an isolated child (-I -S -B) under the shared ProcessBudget; the
# path comes from this plugin file, never from cwd or PATH.
DIFF_HELPER = Path(__file__).resolve().with_name("code_intel_rules_diff.py")


class RuleError(Exception):
    """An expected refusal reported as JSON; never a traceback."""

    def __init__(self, code: str, reason: str, rc: int = 2, **extra):
        super().__init__(reason)
        self.code, self.reason, self.rc, self.extra = code, reason, rc, extra


# ---------------------------------------------------------------- strict JSON
def _pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuleError("invalid_json", f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _constant(name: str):
    raise RuleError("invalid_json", f"Non-finite JSON number {name} is not allowed")


def _float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise RuleError("invalid_json", "A JSON number overflows to a non-finite value")
    return value


def _int(text: str) -> int:
    value = int(text)
    if not -INT64_BOUND <= value < INT64_BOUND:
        raise RuleError("invalid_json", "A JSON integer is outside the signed 64-bit range")
    return value


def strict_json(text: str, label: str, limit: int):
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError:
        raise RuleError("invalid_json", f"{label} is not valid UTF-8") from None
    if len(encoded) > limit:
        raise RuleError("input_too_large", f"{label} exceeds {limit} bytes")
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant,
                           parse_float=_float, parse_int=_int)
        # Lone surrogates are valid JSON escapes but not Unicode text.
        json.dumps(value, ensure_ascii=False).encode("utf-8")
    except RuleError:
        raise
    except UnicodeEncodeError:
        raise RuleError("invalid_json", f"{label} contains a lone surrogate escape") from None
    except (ValueError, RecursionError) as exc:
        raise RuleError("invalid_json", f"{label} is not valid JSON: {exc}") from None
    return value


def _objects(value, label: str) -> list:
    items = [value] if isinstance(value, dict) else value
    if not isinstance(items, list) or not items or not all(isinstance(item, dict) for item in items):
        raise RuleError("invalid_input", f"{label} must be an object or a non-empty array of objects")
    return items


def _rule_id(value, label: str) -> str:
    if not isinstance(value, str) or not RULE_ID.fullmatch(value):
        raise RuleError("invalid_rule_id", f"{label} id must be a string matching [A-Za-z0-9][A-Za-z0-9_.-]*")
    return value


def parse_rules(text: str) -> tuple[dict, str]:
    """Return {id: has_fix} in input order and the native inline document stream."""
    rules: dict = {}
    documents = []
    for index, rule in enumerate(_objects(strict_json(text, "--rule-json", MAX_RULE_BYTES), "--rule-json")):
        unknown = sorted(set(rule) - set(RULE_KEYS))
        if unknown:
            raise RuleError("unsupported_key", f"Rule {index} has unsupported top-level key(s): {', '.join(map(repr, unknown))}")
        rule_id = _rule_id(rule.get("id"), f"Rule {index}")
        if rule_id in RESERVED_RULE_IDS:
            raise RuleError("reserved_rule_id", f"Rule id {rule_id} is reserved by the engine's built-in rules")
        if rule_id in rules:
            raise RuleError("duplicate_rule_id", f"Duplicate rule id: {rule_id}")
        if not isinstance(rule.get("language"), str) or not rule["language"]:
            raise RuleError("invalid_rule", f"Rule {rule_id} needs a non-empty string language")
        if not isinstance(rule.get("rule"), dict):
            raise RuleError("invalid_rule", f"Rule {rule_id} needs a rule object")
        if "fix" in rule:
            fix = rule["fix"]
            if isinstance(fix, dict):
                if set(fix) & FIX_EXPANSION_KEYS:
                    raise RuleError("unsupported_fix_expansion", f"Rule {rule_id}: expandStart/expandEnd are not supported")
                if set(fix) - {"template"}:
                    raise RuleError("unsupported_key", f"Rule {rule_id}: a fix object supports only template")
                fix = fix.get("template")
            if not isinstance(fix, str):
                raise RuleError("invalid_rule", f"Rule {rule_id}: fix must be a string or {{\"template\": string}}")
        rules[rule_id] = "fix" in rule
        # One line per document: escapes keep newlines and `---` inside strings.
        documents.append(json.dumps(rule, ensure_ascii=True))
    return rules, "\n---\n".join(documents)


def parse_tests(text: str, rules: dict) -> list:
    tests = []
    seen = set()
    for index, test in enumerate(_objects(strict_json(text, "--rule-tests-json", MAX_CASES_BYTES), "--rule-tests-json")):
        if set(test) - TEST_KEYS:
            raise RuleError("unsupported_key", f"Test {index} supports only id, valid and invalid")
        if set(test) != TEST_KEYS:
            raise RuleError("invalid_test", f"Test {index} needs id, valid and invalid")
        test_id = _rule_id(test["id"], f"Test {index}")
        if test_id in seen:
            raise RuleError("duplicate_test_id", f"Duplicate test id: {test_id}")
        seen.add(test_id)
        for key in ("valid", "invalid"):
            cases = test[key]
            if not isinstance(cases, list) or not cases or not all(isinstance(case, str) for case in cases):
                raise RuleError("invalid_test", f"Test {test_id}: {key} must be a non-empty list of strings")
        tests.append(test)
    unknown = sorted(seen - set(rules))
    if unknown:
        raise RuleError("unknown_test_id", "Tests name unknown rule id(s): " + ", ".join(unknown))
    untested = [rule_id for rule_id in rules if rule_id not in seen]
    if untested:
        raise RuleError("untested_rule", "Rule(s) without tests: " + ", ".join(untested))
    return tests


def read_stdin(budget: ProcessBudget, limit: int) -> str:
    """Read at most limit bytes from non-TTY stdin within the shared deadline."""
    if sys.stdin is None:
        raise RuleError("stdin_unavailable", "--rule-json - needs a readable stdin")
    fd = sys.stdin.fileno()
    if os.isatty(fd):
        raise RuleError("stdin_tty", "--rule-json - refuses an interactive terminal; pipe the JSON instead")
    data = bytearray()
    regular = stat.S_ISREG(os.fstat(fd).st_mode)
    with selectors.DefaultSelector() as selector:
        if not regular:
            try:
                selector.register(fd, selectors.EVENT_READ)
            except (OSError, ValueError):
                raise RuleError("stdin_unavailable", "stdin cannot be polled with a deadline") from None
        while True:
            remaining = budget.deadline - time.monotonic()
            if remaining <= 0:
                raise RuleError("budget", "Deadline exceeded while reading stdin")
            if not regular and not selector.select(remaining):
                continue
            chunk = os.read(fd, min(READ_CHUNK, limit + 1 - len(data)))
            if not chunk:
                break
            data += chunk
            if len(data) > limit:
                raise RuleError("input_too_large", f"--rule-json - exceeds {limit} bytes")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise RuleError("invalid_json", "--rule-json stdin is not valid UTF-8") from None


# ----------------------------------------------------------- bounded snapshot
def _check_deadline(budget: ProcessBudget) -> None:
    if time.monotonic() >= budget.deadline:
        raise RuleError("budget", "Command deadline exceeded")


def _safe_text(text: str) -> str:
    """Text as-is when it is valid Unicode, else its ASCII escape form."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return ascii(text)
    return text


def _utf8_name(name: str, where: str) -> None:
    """Reject names that are not strict UTF-8 (surrogate-escaped bytes) where they are produced."""
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        raise RuleError("unsupported_file_name", f"Non-UTF-8 file name {name!a} in {where!a}") from None


def target_parts(root: Path, given_root: Path, value: str) -> tuple:
    _utf8_name(value, "path argument")
    path = Path(value)
    if path.is_absolute():
        for base in (root, given_root):
            try:
                path = path.relative_to(base)
                break
            except ValueError:
                continue
        else:
            raise RuleError("path_escape", f"Path escapes workspace: {value}")
    parts = tuple(part for part in path.parts if part not in ("", "."))
    if ".." in parts:
        raise RuleError("path_escape", f"Path escapes workspace: {value}")
    return parts


def _open_entry(dir_fd: int, name: str, rel: str) -> tuple:
    try:
        info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except FileNotFoundError:
        raise RuleError("path_missing", f"Path does not exist: {rel}") from None
    if stat.S_ISLNK(info.st_mode):
        raise RuleError("unsupported_file_type", f"Symbolic links are not followed: {rel}")
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise RuleError("unsupported_file_type", f"Only regular files and directories are read: {rel}")
    try:
        fd = os.open(name, OPEN_FLAGS, dir_fd=dir_fd)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOENT, errno.ENOTDIR):
            raise RuleError("source_changed", f"Path changed while opening: {rel}") from None
        raise
    opened = os.fstat(fd)
    if (opened.st_dev, opened.st_ino, stat.S_IFMT(opened.st_mode)) != (
            info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)):
        os.close(fd)
        raise RuleError("source_changed", f"Path changed while opening: {rel}")
    return fd, opened


class _Walk:
    def __init__(self, budget: ProcessBudget):
        self.budget = budget
        self.files: dict = {}
        self.total = 0
        self.entries = 0

    def add_file(self, fd: int, before: os.stat_result, rel: str) -> None:
        if rel in self.files:
            return
        if len(self.files) >= MAX_FILES:
            raise RuleError("limit", f"More than {MAX_FILES} files; narrow the paths")
        if before.st_size > MAX_FILE_BYTES:
            raise RuleError("limit", f"File exceeds {MAX_FILE_BYTES} bytes: {rel}")
        chunks, size = [], 0
        while True:
            _check_deadline(self.budget)
            chunk = os.read(fd, min(READ_CHUNK, MAX_FILE_BYTES + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                raise RuleError("limit", f"File exceeds {MAX_FILE_BYTES} bytes: {rel}")
            chunks.append(chunk)
        after = os.fstat(fd)
        if size != after.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuleError("source_changed", f"Source changed while reading: {rel}")
        self.total += size
        if self.total > MAX_SOURCE_BYTES:
            raise RuleError("limit", f"Sources exceed {MAX_SOURCE_BYTES} bytes; narrow the paths")
        data = b"".join(chunks)
        self.files[rel] = {"data": data, "sha256": hashlib.sha256(data).hexdigest(),
                           "identity": (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)}

    def directory(self, fd: int, prefix: tuple, depth: int) -> None:
        if depth > MAX_DEPTH:
            raise RuleError("limit", f"Directory nesting exceeds {MAX_DEPTH} levels")
        names = []
        with os.scandir(fd) as iterator:
            for entry in iterator:
                self.entries += 1
                if self.entries > MAX_DIRECTORY_ENTRIES:
                    raise RuleError("limit", f"More than {MAX_DIRECTORY_ENTRIES} directory entries; narrow the paths")
                _check_deadline(self.budget)
                _utf8_name(entry.name, "/".join(prefix) or ".")
                names.append(entry.name)
        for name in sorted(names):
            parts = (*prefix, name)
            child, info = _open_entry(fd, name, "/".join(parts))
            try:
                if stat.S_ISDIR(info.st_mode):
                    self.directory(child, parts, depth + 1)
                else:
                    self.add_file(child, info, "/".join(parts))
            finally:
                os.close(child)


def snapshot(root_fd: int, targets: list, budget: ProcessBudget) -> dict:
    """Read every regular file under the targets through descriptor traversal only."""
    walk = _Walk(budget)
    for parts in targets:
        current = os.dup(root_fd)
        try:
            info = os.fstat(current)
            for index, name in enumerate(parts):
                rel = "/".join(parts[:index + 1])
                if not stat.S_ISDIR(info.st_mode):
                    raise RuleError("path_missing", f"Not a directory: {'/'.join(parts[:index])}")
                child, info = _open_entry(current, name, rel)
                os.close(current)
                current = child
            if stat.S_ISDIR(info.st_mode):
                walk.directory(current, parts, len(parts))
            else:
                walk.add_file(current, info, "/".join(parts))
        finally:
            os.close(current)
    return walk.files


def _state(files: dict) -> dict:
    return {rel: (record["sha256"], record["identity"]) for rel, record in files.items()}


def _copy_changed(rel: str) -> RuleError:
    return RuleError("copy_changed", f"The private copy changed outside this tool: {rel}; nothing was trusted")


class CopyTree:
    """Private scan copy reached only from a pinned root descriptor.

    Directories are re-opened per component with O_NOFOLLOW|O_DIRECTORY and
    compared with the identity recorded at creation; files must keep their
    creation inode and a single link before any byte is truncated, and the
    same descriptor reads the bytes back. A swapped component is rc2, never a
    write through it. Replacing a component with identical bytes while the
    filesystem reuses its inode cannot be distinguished, but remains confined
    to the private copy and scans the same bytes.
    """

    def __init__(self, path: Path, budget: ProcessBudget):
        self.path, self.budget = path, budget
        os.mkdir(path, 0o700)
        self.fd = os.open(path, DIR_FLAGS)
        info = os.fstat(self.fd)
        self.dirs = {(): (info.st_dev, info.st_ino)}
        self.files: dict = {}

    def close(self) -> None:
        os.close(self.fd)

    def _directory(self, parts: tuple, create: bool) -> int:
        fd = os.dup(self.fd)
        try:
            for index, name in enumerate(parts):
                key = parts[:index + 1]
                fresh = create and key not in self.dirs
                try:
                    if fresh:
                        os.mkdir(name, 0o700, dir_fd=fd)
                    child = os.open(name, DIR_FLAGS, dir_fd=fd)
                except OSError:
                    raise _copy_changed("/".join(key)) from None
                os.close(fd)
                fd = child
                info = os.fstat(fd)
                if fresh:
                    self.dirs[key] = (info.st_dev, info.st_ino)
                elif self.dirs.get(key) != (info.st_dev, info.st_ino):
                    raise _copy_changed("/".join(key))
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _open_file(self, rel: str, create: bool) -> int:
        parts = tuple(rel.split("/"))
        parent = self._directory(parts[:-1], create)
        try:
            flags = COPY_FLAGS | (os.O_CREAT | os.O_EXCL if create else 0)
            try:
                fd = os.open(parts[-1], flags, 0o600, dir_fd=parent)
            except OSError:
                raise _copy_changed(rel) from None
        finally:
            os.close(parent)
        info = os.fstat(fd)
        identity = (info.st_dev, info.st_ino)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or (not create and self.files.get(rel) != identity):
            os.close(fd)
            raise _copy_changed(rel)
        if create:
            self.files[rel] = identity
        return fd

    def _read_back(self, fd: int, rel: str, data: bytes) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        chunks, size = [], 0
        while size <= len(data):
            _check_deadline(self.budget)
            chunk = os.read(fd, min(READ_CHUNK, len(data) + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        if b"".join(chunks) != data:
            raise _copy_changed(rel)

    def write(self, rel: str, data: bytes, create: bool = False) -> None:
        fd = self._open_file(rel, create)
        try:
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            self._read_back(fd, rel, data)
        finally:
            os.close(fd)

    def verify(self, current: dict) -> None:
        """Re-read every copy file after a scan: the scan must have seen exactly `current`."""
        try:
            info = os.stat(self.path, follow_symlinks=False)
        except OSError:
            raise _copy_changed(".") from None
        if (info.st_dev, info.st_ino) != self.dirs[()]:
            raise _copy_changed(".")
        for rel in sorted(current):
            fd = self._open_file(rel, create=False)
            try:
                self._read_back(fd, rel, current[rel])
            finally:
                os.close(fd)


# ------------------------------------------------------------- engine access
def _version_tuple(version: str) -> tuple:
    return tuple(int(part) for part in version.split("."))


def select_engine(budget: ProcessBudget, cwd: Path, root: Path) -> tuple:
    try:
        engine = code_intel.find_ast_grep(budget, cwd=cwd, root=root)
    except ValueError as exc:
        raise RuleError("engine_rejected", str(exc)) from None
    if engine is None:
        raise RuleError("unavailable", "ast-grep is not installed or its version output is unrecognized", rc=3)
    binary, version = engine
    if _version_tuple(version) < MINIMUM_ENGINE:
        raise RuleError("unsupported_engine", f"ast-grep {version} is below the minimum {'.'.join(map(str, MINIMUM_ENGINE))}",
                        rc=3, engine_version=version)
    return binary, version


def _argument_limit() -> int | None:
    """Linux caps each exec argument at 32 pages (MAX_ARG_STRLEN). Elsewhere
    (e.g. macOS) only the total ARG_MAX applies, reported as E2BIG at exec."""
    if sys.platform.startswith("linux"):
        return 32 * os.sysconf("SC_PAGE_SIZE")
    return None


def _too_long(size: int | None = None) -> RuleError:
    detail = "" if size is None else f" ({size} bytes)"
    return RuleError("limit", f"Serialized rules{detail} exceed this platform's exec argument limit; "
                     "split the rules into smaller runs or shorten them")


def run_engine(budget: ProcessBudget, command: list, cwd: Path) -> subprocess.CompletedProcess:
    try:
        return budget.run(command, cwd=cwd)
    except subprocess.TimeoutExpired:
        raise RuleError("budget", "Command deadline exceeded while the engine ran") from None
    except ValueError as exc:
        raise RuleError("budget", str(exc)) from None
    except OSError as exc:
        if exc.errno == errno.E2BIG:
            raise _too_long() from None
        raise


def _detail(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").strip()[:DETAIL_CHARS]


def _version_notices(version: str) -> list:
    if version == TESTED_VERSION:
        return []
    return [f"Engine {version} differs from tested {TESTED_VERSION}; each match is schema-checked, "
            "but other native behavior is unverified for this version."]


# --------------------------------------------------------- match validation
def _integer(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _offsets(value) -> tuple | None:
    if not isinstance(value, dict) or not _integer(value.get("start")) or not _integer(value.get("end")):
        return None
    return value["start"], value["end"]


def _position(value) -> dict | None:
    if (not isinstance(value, dict) or not _integer(value.get("line")) or not _integer(value.get("column"))
            or value["line"] < 0 or value["column"] < 0):
        return None
    return {"line": value["line"], "column": value["column"]}


def _boundary(data: bytes, index: int) -> bool:
    return index == len(data) or (data[index] & 0xC0) != 0x80


def _mismatch(reason: str) -> RuleError:
    return RuleError("schema_mismatch", "Engine output failed validation: " + reason)


def validate_matches(rows, prefix: str, current: dict, rules: dict) -> tuple:
    """Check every native match against the current copy bytes; return edits and display rows."""
    if not isinstance(rows, list):
        raise _mismatch("top level is not an array")
    edits: dict = {}
    shown = []
    for row in rows:
        if not isinstance(row, dict):
            raise _mismatch("a match is not an object")
        file, rule_id, text, span = row.get("file"), row.get("ruleId"), row.get("text"), row.get("range")
        if not isinstance(file, str) or not file.startswith(prefix) or file[len(prefix):] not in current:
            raise _mismatch("a match names a file outside the copied set")
        rel = file[len(prefix):]
        if not isinstance(rule_id, str) or rule_id not in rules:
            raise _mismatch("a match names an unknown rule id")
        if not isinstance(text, str) or not isinstance(span, dict):
            raise _mismatch("a match lacks text or range")
        data = current[rel]
        offsets, start, end = _offsets(span.get("byteOffset")), _position(span.get("start")), _position(span.get("end"))
        if offsets is None or start is None or end is None:
            raise _mismatch("a match range is malformed")
        low, high = offsets
        if not 0 <= low <= high <= len(data) or not (_boundary(data, low) and _boundary(data, high)):
            raise _mismatch(f"a match range is outside the file or splits UTF-8 in {rel}")
        if data[low:high] != text.encode("utf-8"):
            raise _mismatch(f"match text differs from the copied bytes in {rel}")
        item = {"file": rel, "ruleId": rule_id, "start": start, "end": end, "text": text}
        has_replacement = "replacement" in row or "replacementOffsets" in row
        if rules[rule_id]:
            replacement, target = row.get("replacement"), _offsets(row.get("replacementOffsets"))
            if not isinstance(replacement, str) or target is None:
                raise _mismatch(f"rule {rule_id} declares fix but a match lacks replacement fields")
            first, last = target
            if not low <= first <= last <= high or not (_boundary(data, first) and _boundary(data, last)):
                raise _mismatch(f"replacement offsets leave the match range or split UTF-8 in {rel}")
            edits.setdefault(rel, []).append((first, last, rule_id, replacement.encode("utf-8")))
            item["replacement"] = replacement
        elif has_replacement:
            raise _mismatch(f"rule {rule_id} has no fix but a match carries replacement fields")
        shown.append(((rel.encode("utf-8"), low, high, rule_id), item))
    # Native scan order varies; select a stable display subset before --limit.
    return edits, [item for _key, item in sorted(shown, key=lambda pair: pair[0])]


def select_edits(rel: str, edits: list) -> list:
    """Choose outermost non-overlapping edits; nested ones wait for the next pass."""
    unique: dict = {}
    for first, last, rule_id, replacement in edits:
        key = (first, last, rule_id)
        if unique.setdefault(key, replacement) != replacement:
            raise _mismatch(f"rule {rule_id} gave two replacements for one range in {rel}")
    ordered = sorted(unique.items(), key=lambda item: (item[0][0], -item[0][1], item[0][2]))
    selected, stack, previous = [], [], None
    for (first, last, _rule_id), replacement in ordered:
        if previous == (first, last):
            raise RuleError("cross_rule_same_range",
                            f"Different rules rewrite the same range in {rel}; the native winner is not guessed")
        previous = (first, last)
        while stack and stack[-1][1] <= first:
            stack.pop()
        if stack and last > stack[-1][1]:
            raise _mismatch(f"replacement ranges partially overlap in {rel}")
        if not stack:
            selected.append((first, last, replacement))
        stack.append((first, last))
    return selected


def apply_edits(data: bytes, selected: list) -> bytes:
    result = bytearray(data)
    for first, last, replacement in reversed(selected):
        result[first:last] = replacement
    return bytes(result)


def _digest(current: dict) -> str:
    hasher = hashlib.sha256()
    for rel in sorted(current):
        hasher.update(rel.encode("utf-8", "surrogateescape") + b"\0" + hashlib.sha256(current[rel]).digest())
    return hasher.hexdigest()


def _private_file(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0), 0o600)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
    finally:
        os.close(fd)


def render_diffs(budget: ProcessBudget, base: Path, entries: list) -> list:
    """Unified diffs from an isolated child under the shared deadline and output budget.

    entries: [(rel, before, after)] already within the byte limits. Any failure is
    rc2 with no partial diff; nothing is omitted to make a deadline.
    """
    if not entries:
        return []
    work = base / "diff"
    work.mkdir(mode=0o700)
    manifest = []
    for index, (rel, before, after) in enumerate(entries):
        pair = {"path": rel, "before": str(work / f"{index:04d}.before"), "after": str(work / f"{index:04d}.after")}
        _private_file(Path(pair["before"]), before)
        _private_file(Path(pair["after"]), after)
        manifest.append(pair)
    listing = work / "manifest.json"
    _private_file(listing, json.dumps({"files": manifest}, ensure_ascii=True).encode("ascii"))
    cwd = work / "cwd"
    cwd.mkdir(mode=0o700)
    try:
        result = budget.run([sys.executable, "-I", "-S", "-B", str(DIFF_HELPER), str(listing)], cwd=cwd)
    except subprocess.TimeoutExpired:
        raise RuleError("budget", "Command deadline exceeded while rendering the diff; no partial diff is reported") from None
    except ValueError as exc:
        raise RuleError("budget", str(exc)) from None
    try:
        reply = json.loads(result.stdout.decode("ascii"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        reply = None
    if result.returncode == 3 and isinstance(reply, dict) and reply.get("error") == "not_utf8":
        raise _mismatch(f"rewritten file is not UTF-8: {reply.get('path')!a}")
    diffs = reply.get("diffs") if result.returncode == 0 and isinstance(reply, dict) else None
    if (not isinstance(diffs, list) or [item.get("path") if isinstance(item, dict) else None for item in diffs]
            != [rel for rel, _, _ in entries] or not all(isinstance(item.get("diff"), str) for item in diffs)):
        raise RuleError("internal_error", "Diff helper failed; no partial diff is reported",
                        native_rc=result.returncode, detail=_detail(result.stderr))
    return [item["diff"] for item in diffs]


# --------------------------------------------------------------- preview mode
def preview(args, root: Path, budget: ProcessBudget, rules: dict, inline: str) -> tuple:
    if not args.paths:
        raise RuleError("invalid_input", "Preview needs at least one path inside --root")
    max_passes = MAX_PASSES_DEFAULT if args.max_passes is None else args.max_passes
    if not 1 <= max_passes <= MAX_PASSES_LIMIT:
        raise RuleError("invalid_input", f"--max-passes must be 1..{MAX_PASSES_LIMIT}")
    given = Path(os.path.abspath(args.root))
    targets = [target_parts(root, given, value) for value in args.paths]
    limit = _argument_limit()
    size = len(f"--inline-rules={inline}".encode()) + 1
    if limit is not None and size > limit:
        raise _too_long(size)
    root_fd = os.open(root, OPEN_FLAGS | os.O_DIRECTORY)
    try:
        files = snapshot(root_fd, targets, budget)
        with tempfile.TemporaryDirectory(prefix="hiway-ast-rules-") as directory:
            base = Path(os.path.realpath(directory))
            result = _iterate(args, root, budget, rules, inline, files, base, max_passes)
        # Recheck through the same pinned root descriptor; never restore others' edits.
        after = snapshot(root_fd, targets, budget)
    finally:
        os.close(root_fd)
    before_state, after_state = _state(files), _state(after)
    if before_state != after_state:
        changed = sorted(rel for rel in set(before_state) | set(after_state)
                         if before_state.get(rel) != after_state.get(rel))
        raise RuleError("source_changed", "Sources changed during the preview; the result was discarded",
                        changed_paths=changed[:args.limit], changed_count=len(changed))
    return result


def _iterate(args, root, budget, rules, inline, files, base, max_passes) -> tuple:
    cwd, neutral, tree = base / "cwd", base / "neutral", base / "tree"
    cwd.mkdir(mode=0o700)
    neutral.mkdir(mode=0o700)
    # Explicit config plus neutral cwd: no workspace/temp-ancestor sgconfig loads.
    config = neutral / "sgconfig.yml"
    config.write_text("ruleDirs: []\n", encoding="utf-8")
    copy = CopyTree(tree, budget)
    try:
        for rel, record in files.items():
            copy.write(rel, record["data"], create=True)
        return _passes(args, root, budget, rules, inline, files, base, max_passes, copy, cwd, config)
    finally:
        copy.close()


def _passes(args, root, budget, rules, inline, files, base, max_passes, copy, cwd, config) -> tuple:
    tree = copy.path
    binary, version = select_engine(budget, cwd, root)
    # Force every caller rule (incl. severity error/off) to hint so severity
    # cannot change rc or the match set. Per-id '=' values, not a bare --hint:
    # bare --hint also enables native built-ins (no-suppress-all, and
    # unused-suppression whose fix deletes comments). An option follows the
    # hint flags and '--' precedes the path, so no path is read as a rule id.
    command = [binary, "scan", "--config", str(config), f"--inline-rules={inline}",
               *(f"--hint={rule_id}" for rule_id in rules), "--json=compact"]
    for kind in NO_IGNORE:
        command += ["--no-ignore", kind]
    command += ["--", str(tree)]
    prefix = str(tree) + os.sep
    current = {rel: record["data"] for rel, record in files.items()}
    history = {_digest(current)}
    passes, first_matches = [], None
    iterations = changed_passes = 0
    stop_reason = None
    while stop_reason is None:
        if iterations >= max_passes:
            stop_reason = "pass_limit"
            break
        _check_deadline(budget)
        iterations += 1
        result = run_engine(budget, command, cwd)
        if result.returncode != 0:
            raise RuleError("engine_error", "ast-grep scan failed (rule rejected or engine error)",
                            native_rc=result.returncode, detail=_detail(result.stderr), iterations=iterations)
        # The scan must have read exactly the bytes this pass reasons about.
        copy.verify(current)
        if not result.stdout.strip():
            raise _mismatch("scan produced no output (a match-free scan prints [])")
        try:
            rows = json.loads(result.stdout)
        except (ValueError, RecursionError):
            raise _mismatch("scan output is not JSON") from None
        edits, shown = validate_matches(rows, prefix, current, rules)
        if first_matches is None:
            first_matches = shown
        updated = {}
        selected_count = 0
        for rel in sorted(edits):
            selected = select_edits(rel, edits[rel])
            selected_count += len(selected)
            data = apply_edits(current[rel], selected)
            if data != current[rel]:
                updated[rel] = data
        passes.append({"iteration": iterations, "match_count": len(shown), "edits_selected": selected_count,
                       "changed_files": sorted(updated)})
        if not updated:
            stop_reason = ("no_match" if iterations == 1 and not shown else
                           "fixed_point" if changed_passes else "idempotent")
            break
        candidate = {**current, **updated}
        if any(len(data) > MAX_FILE_BYTES for data in updated.values()) or \
                sum(map(len, candidate.values())) > MAX_SOURCE_BYTES:
            raise RuleError("limit", "Intermediate rewrite exceeded the source byte limits", iterations=iterations)
        for rel, data in updated.items():
            copy.write(rel, data)
        current = candidate
        changed_passes += 1
        digest = _digest(current)
        if digest in history:
            stop_reason = "cycle"
            break
        history.add(digest)
    originals = {rel: record["data"] for rel, record in files.items()}
    common = {
        "engine_version": version, "tested_version": TESTED_VERSION,
        "rule_ids": list(rules), "files_copied": len(files),
        "source_sha256": {rel: record["sha256"] for rel, record in sorted(files.items())},
        "iterations": iterations, "changed_passes": changed_passes, "stop_reason": stop_reason,
        "passes": passes,
    }
    notices = _version_notices(version)
    ignored = sum(IGNORE_MARKER in data for data in originals.values())
    if ignored:
        notices.append(f"{ignored} copied file(s) contain 'ast-grep-ignore'; source suppression comments still "
                       "hide matches, so a missing match may be suppression.")
    if not files:
        notices.append("No files were copied; nothing was scanned.")
    if stop_reason in ("cycle", "pass_limit"):
        return 2, {"status": "error", "error": "nonconvergence", "converged": False,
                   "reason": f"Rewrites did not reach a fixed point ({stop_reason}); no diff is reported",
                   **common, "last_changed_files": passes[-1]["changed_files"], "notices": notices}
    changed = sorted(rel for rel in current if current[rel] != originals[rel])
    shown_files = changed[:args.limit]
    diffs = render_diffs(budget, base, [(rel, originals[rel], current[rel]) for rel in shown_files])
    entries = [{"path": rel, "source_sha256": files[rel]["sha256"],
                "result_sha256": hashlib.sha256(current[rel]).hexdigest(), "diff": diff}
               for rel, diff in zip(shown_files, diffs)]
    notices.append("Preview only: no source was written. A fixed point is not semantic correctness; apply edits "
                   "with your own editor and run the project's tests. External apply tools can leave partial edits.")
    return 0, {"status": "ok", "converged": True, **common,
               "match_count": len(first_matches or []), "final_match_count": passes[-1]["match_count"],
               "changed_file_count": len(changed), "files": entries,
               "matches": (first_matches or [])[:args.limit],
               "truncated": len(changed) > args.limit or len(first_matches or []) > args.limit,
               "notices": notices}


# ------------------------------------------------------------- rule-test mode
def _listing(directory: Path) -> dict:
    return {str(path.relative_to(directory)): path.read_bytes() if path.is_file() else None
            for path in sorted(directory.rglob("*"))}


def rule_test(args, root: Path, budget: ProcessBudget, rules: dict, inline: str, tests: list) -> tuple:
    if args.paths or args.max_passes is not None:
        raise RuleError("invalid_input", "--rule-tests-json takes no paths or --max-passes")
    with tempfile.TemporaryDirectory(prefix="hiway-ast-rule-test-") as directory:
        base = Path(os.path.realpath(directory))
        cwd, project = base / "cwd", base / "project"
        for path in (cwd, project, project / "rules", project / "tests"):
            path.mkdir(mode=0o700)
        config = project / "sgconfig.yml"
        config.write_text(json.dumps({"ruleDirs": ["rules"], "testConfigs": [{"testDir": "tests"}]}) + "\n",
                          encoding="utf-8")
        (project / "rules" / "rules.yml").write_text(inline + "\n", encoding="utf-8")
        # Fixed generated names: ids are never used as paths.
        for index, test in enumerate(tests, 1):
            (project / "tests" / f"case-{index:04d}.yml").write_text(json.dumps(test, ensure_ascii=True) + "\n",
                                                                       encoding="utf-8")
        before = _listing(project)
        binary, version = select_engine(budget, cwd, root)
        result = run_engine(budget, [binary, "test", "--config", str(config), "--skip-snapshot-tests",
                                     "--include-off", "--color=never"], cwd)
        if _listing(project) != before:
            raise RuleError("snapshot_written", "The engine changed the generated test project (snapshot write)")
    return _judge_tests(result, tests, version)


def _judge_tests(result, tests: list, version: str) -> tuple:
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    context = {"native_rc": result.returncode, "detail": (stdout + "\n" + stderr).strip()[:DETAIL_CHARS],
               "engine_version": version}
    if any(line.startswith("Configuration not found!") for line in (stdout + "\n" + stderr).splitlines()):
        raise RuleError("unverified_test", "The engine skipped tests whose rule was not loaded", **context)
    running = RUNNING_LINE.findall("\n".join(line for line in stdout.splitlines() if RUNNING_LINE.fullmatch(line)))
    if running != [str(len(tests))]:
        raise RuleError("unrecognized_output", "Engine test output does not report the expected test count", **context)
    statuses = {}
    for line in stdout.splitlines():
        if line.startswith("SKIP "):
            raise RuleError("unverified_test", "The engine skipped a test entry", **context)
        if line.startswith(("PASS ", "FAIL ")):
            match = STATUS_LINE.fullmatch(line)
            if match is None or match[2] in statuses:
                raise RuleError("unrecognized_output", "Engine test status lines are malformed or repeated", **context)
            statuses[match[2]] = (match[1], match[3])
    if set(statuses) != {test["id"] for test in tests}:
        raise RuleError("unrecognized_output", "Engine test status lines do not match the test ids", **context)
    results = []
    for test in tests:
        status, marks = statuses[test["id"]]
        valid, invalid = len(test["valid"]), len(test["invalid"])
        if (len(marks) != valid + invalid or set(marks[:valid]) - {".", "N"} or set(marks[valid:]) - {".", "M"}
                or (status == "PASS") != (set(marks) == {"."})):
            raise RuleError("unrecognized_output", f"Engine case marks for {test['id']} are inconsistent", **context)
        results.append({"id": test["id"], "status": status,
                        "valid": {"total": valid, "passed": marks[:valid].count(".")},
                        "invalid": {"total": invalid, "passed": marks[valid:].count(".")}})
    failed = sum(item["status"] == "FAIL" for item in results)
    summary = SUMMARY.findall(stdout if result.returncode == 0 else stderr)
    if summary != [(str(len(results) - failed), str(failed))] or (result.returncode == 0) != (failed == 0):
        raise RuleError("unrecognized_output", "Engine test summary disagrees with the status lines", **context)
    cases = sum(item["valid"]["total"] + item["invalid"]["total"] for item in results)
    passed = sum(item["valid"]["passed"] + item["invalid"]["passed"] for item in results)
    notices = [*_version_notices(version),
               "Rule tests check match/non-match only; they do not verify fix output or program behavior."]
    return (1 if failed else 0), {
        "status": "failed" if failed else "ok", "engine_version": version, "tested_version": TESTED_VERSION,
        "rule_ids": [item["id"] for item in results], "tests_run": len(results), "tests_failed": failed,
        "cases_run": cases, "cases_passed": passed, "cases_failed": cases - passed,
        "results": results, "notices": notices}


# ------------------------------------------------------------------ dispatch
def _emit(mode: str, result: dict) -> bool:
    """Print the result; returns False when it had to be replaced by an rc2 error.

    An oversized result becomes `budget`; one that cannot be encoded as UTF-8
    JSON (e.g. surrogate-escaped bytes) becomes an ASCII-only `internal_error`.
    """
    try:
        size = len(json.dumps(result, ensure_ascii=False).encode("utf-8"))
    except (UnicodeEncodeError, ValueError, TypeError) as exc:
        result, ok = {"status": "error", "error": "internal_error",
                      "reason": "Result could not be encoded as UTF-8 JSON: " + ascii(str(exc))[:DETAIL_CHARS]}, False
    else:
        ok = size <= code_intel.MAX_OUTPUT_BYTES
        if not ok:
            result = {"status": "error", "error": "budget",
                      "reason": f"Result exceeds {code_intel.MAX_OUTPUT_BYTES} bytes; narrow the paths or lower --limit"}
    try:
        print_result({"mode": mode, **result})
    except UnicodeEncodeError:
        # stdout cannot encode the text: fall back to pure ASCII JSON.
        print_result({"mode": mode, "status": "error", "error": "internal_error",
                      "reason": "Result could not be written to stdout in its encoding"})
        return False
    return ok


def main(args) -> int:
    mode = "rule-test" if args.rule_tests_json is not None else "rule-preview"
    try:
        if args.lang is not None or args.pattern is not None or args.rewrite is not None:
            raise RuleError("invalid_input", "--rule-json cannot be combined with --lang, --pattern or --rewrite")
        _utf8_name(args.root, "--root")
        root = Path(args.root).resolve(strict=True)
        _utf8_name(str(root), "--root")
        if not root.is_dir():
            raise RuleError("invalid_input", "Workspace root must be a directory")
        # One budget: stdin, IO, version probe, every pass and the confirm scan.
        budget = ProcessBudget(code_intel.QUERY_TIMEOUT, code_intel.MAX_OUTPUT_BYTES, root=root)
        text = read_stdin(budget, MAX_RULE_BYTES) if args.rule_json == "-" else args.rule_json
        rules, inline = parse_rules(text)
        if mode == "rule-test":
            rc, result = rule_test(args, root, budget, rules, inline, parse_tests(args.rule_tests_json, rules))
        else:
            rc, result = preview(args, root, budget, rules, inline)
    except RuleError as exc:
        status = "unavailable" if exc.rc == 3 else "error"
        return exc.rc if _emit(mode, {"status": status, "error": exc.code, "reason": exc.reason, **exc.extra}) else 2
    except subprocess.TimeoutExpired:
        _emit(mode, {"status": "error", "error": "budget", "reason": "Command deadline exceeded"})
        return 2
    except OSError as exc:
        _emit(mode, {"status": "error", "error": "io_error", "reason": _safe_text(str(exc))})
        return 2
    except Exception as exc:
        # Malformed native output or an unforeseen shape must stay a JSON rc2.
        _emit(mode, {"status": "error", "error": "internal_error", "reason": _safe_text(f"{type(exc).__name__}: {exc}")})
        return 2
    return rc if _emit(mode, result) else 2
