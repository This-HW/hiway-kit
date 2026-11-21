#!/usr/bin/env python3
"""One-shot queries with trusted language servers; servers can execute workspace code and are not sandboxed."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from intel_runtime import (
    child_environment,
    filesystem_identity,
    print_result,
    resolve_executable,
)
from lsp_index_cache import FAILURE_REASONS, Cache, key_for
from lsp_index_coverage import Coverage, certify
from lsp_index_inputs import (
    cdb_unchanged,
    config_still_absent,
    discover_compile_database,
)
from lsp_index_policy import CLEANUP_SECONDS, NEW_KEY_SECONDS, WORKERS, IndexUnavailable
from lsp_index_resources import Deadline
from lsp_source import SourceUnavailable, read_source
from lsp_transport import Connection, LspError
from lsp_validation import LspBudgetExceeded, require, validate_navigation

MAX_SOURCE_BYTES = 1024 * 1024
INDEX_DISABLE_ENV = "HIWAY_CODE_INTEL_INDEX"
SERVER_CANDIDATES = {
    "c": [("clangd", ["--background-index=false", "--log=error"])],
    "cpp": [("clangd", ["--background-index=false", "--log=error"])],
    "python": [("basedpyright-langserver", ["--stdio"]), ("pyright-langserver", ["--stdio"]), ("ruff", ["server"])],
    "typescript": [("typescript-language-server", ["--stdio"])],
    "javascript": [("typescript-language-server", ["--stdio"])],
    "rust": [("rust-analyzer", [])],
    "go": [("gopls", [])],
}
LANGUAGES = {".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".hpp": "cpp",
             ".py": "python", ".ts": "typescript", ".tsx": "typescriptreact",
             ".js": "javascript", ".jsx": "javascriptreact", ".rs": "rust", ".go": "go"}


def indexed_server_command(server, compile_directory: Path) -> list[str]:
    """The frozen indexed clangd argv; keep it explicit for contract tests."""
    return [server, "--background-index", "--limit-references=0", "-j", str(WORKERS),
            "--enable-config=false", "--compile-commands-dir=" + str(compile_directory), "--log=error"]


def _probe(argv, env, deadline):
    deadline.check()
    try:
        result = subprocess.run(argv, cwd="/", stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, env=env, timeout=deadline.remaining(), check=False)
    except subprocess.TimeoutExpired as exc:
        raise IndexUnavailable("index_deadline", "Indexed tool identity probe exceeded its deadline") from exc
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise IndexUnavailable("index_unavailable", "Indexed tool identity probe failed") from exc
    if result.returncode != 0 or len(result.stdout) > 8192:
        raise IndexUnavailable("index_unavailable", "Indexed tool identity is unavailable or oversized")
    try:
        value = result.stdout.decode("utf-8", errors="strict").strip()
    except UnicodeError as exc:
        raise IndexUnavailable("index_unavailable", "Indexed tool identity is not UTF-8") from exc
    if not value or "\0" in value:
        raise IndexUnavailable("index_unavailable", "Indexed tool identity is empty")
    return value


def _executable_identity(path):
    try:
        fixed = Path(path).resolve(strict=True)
        info = fixed.stat()
        if not stat.S_ISREG(info.st_mode) or not os.access(fixed, os.X_OK):
            raise ValueError("not executable")
        return fixed, (str(fixed), info.st_dev, info.st_ino)
    except (OSError, RuntimeError, ValueError) as exc:
        raise IndexUnavailable("index_unavailable", "Indexed executable cannot be pinned") from exc


def _indexed_toolchain(command, root, env, deadline):
    selected = command[0]
    root_identity = getattr(selected, "workspace_identity", None) or filesystem_identity(root)
    sdk_identity = None
    if sys.platform == "darwin":
        xcrun_path = shutil.which("xcrun")
        if not xcrun_path:
            raise IndexUnavailable("index_unavailable", "xcrun is required to pin the Apple clangd and SDK")
        xcrun = resolve_executable(xcrun_path, root, False, {("workspace_identity", root): root_identity})
        if str(getattr(selected, "executable", selected)) == "/usr/bin/clangd":
            actual = _probe([xcrun.executable, "--find", "clangd"], env, deadline)
            selected = resolve_executable(actual, root, False, {("workspace_identity", root): root_identity})
        sdk_path = Path(_probe([xcrun.executable, "--show-sdk-path"], env, deadline))
        sdk, sdk_identity = _executable_or_directory_identity(sdk_path)
        sdk_identity = (str(sdk), *sdk_identity)
    fixed, binary_identity = _executable_identity(getattr(selected, "executable", selected))
    version = _probe([str(fixed), "--version"], env, deadline)
    engine_identity = (*binary_identity, version)
    return selected, engine_identity, sdk_identity, root_identity


def _executable_or_directory_identity(path):
    try:
        fixed = path.resolve(strict=True)
        info = fixed.stat()
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("not a directory")
        return fixed, (info.st_dev, info.st_ino)
    except (OSError, RuntimeError, ValueError) as exc:
        raise IndexUnavailable("index_unavailable", "Default SDK cannot be pinned") from exc


def _cache_root(env):
    xdg = env.get("XDG_CACHE_HOME")
    if xdg is not None:
        base = Path(xdg)
        if not base.is_absolute():
            raise IndexUnavailable("index_unavailable", "XDG_CACHE_HOME must be absolute")
    else:
        home = env.get("HOME")
        if not home or not Path(home).is_absolute():
            raise IndexUnavailable("index_unavailable", "HOME must be absolute for the index cache")
        base = Path(home) / ".cache"
    return base / "hiway-kit" / "code-intel" / "clangd"


def _consume_failure(lease):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open("failure.json", flags, dir_fd=lease.fd)
    except FileNotFoundError:
        return None
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink("failure.json", dir_fd=lease.fd)
        return None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                or info.st_mode & 0o077 or info.st_size > 1024):
            raise IndexUnavailable("index_unavailable", "Cached failure evidence is unsafe")
        raw = os.read(fd, 1025)
        pairs = json.loads(raw, object_pairs_hook=_unique_pairs)
        if not isinstance(pairs, dict) or set(pairs) != {"reason"} or pairs["reason"] not in FAILURE_REASONS:
            raise IndexUnavailable("index_unavailable", "Cached failure evidence is invalid")
        current = os.stat("failure.json", dir_fd=lease.fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise IndexUnavailable("index_unavailable", "Cached failure evidence changed")
        os.unlink("failure.json", dir_fd=lease.fd)
        return pairs["reason"]
    except (IndexUnavailable, OSError, ValueError, TypeError, UnicodeError, RecursionError):
        return None
    finally:
        os.close(fd)
        # Remove only the entry name under the private pinned key; never follow
        # a malformed/symlink failure record into another location.
        with contextlib.suppress(OSError):
            os.unlink("failure.json", dir_fd=lease.fd)


def _unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def select_server(language: str, explicit: str | None, allow_custom: bool = False,
                  root: Path | None = None) -> list[str] | None:
    root = Path.cwd().resolve() if root is None else root
    resolved = {}

    def checked(path: str) -> str:
        return resolve_executable(path, root, allow_custom, resolved)

    if explicit is not None:
        if not explicit or explicit in (".", "..") or "\\" in explicit or (not Path(explicit).is_absolute() and "/" in explicit):
            raise ValueError("--server requires a bare executable name or absolute path; relative paths are forbidden")
        known = {name: arguments for candidates in SERVER_CANDIDATES.values() for name, arguments in candidates}
        if Path(explicit).name not in known and not allow_custom:
            raise ValueError("Unknown --server basename; --allow-custom-server permits arbitrary code execution")
        path = shutil.which(explicit)
        if path is None:
            return None
        fixed = checked(path)
        if Path(explicit).is_absolute() and not allow_custom:
            installed = shutil.which(Path(explicit).name)
            if installed is None or checked(installed).executable != fixed.executable:
                raise ValueError("Absolute server must match the installed PATH server; otherwise use --allow-custom-server")
        return [fixed, *known.get(Path(explicit).name, [])]
    for name, arguments in SERVER_CANDIDATES.get(language.removesuffix("react"), []):
        path = shutil.which(name)
        if path:
            return [checked(path), *arguments]
    return None


def _query_standard(args: argparse.Namespace, root: Path, path: Path, text: str, language: str,
                   command, *, fallback_reason=None, index_metadata=None, deadline=None) -> int:
    allow_custom = getattr(args, "allow_custom_server", False)
    if command is None:
        print_result({"status": "unavailable", "complete": False, "language": language, "reason": "No installed language server"})
        return 3
    command += args.server_arg
    # LSP lines end only at LF, CRLF, or CR. Keep a final empty line and
    # leave NEL/LS/PS in the line when computing UTF-16 character offsets.
    lines = re.split(r"\r\n|\r|\n", text)
    if not 1 <= args.line <= len(lines) or not 1 <= args.column <= len(lines[args.line - 1]) + 1:
        raise ValueError("Position is outside the source file (line/column start at 1)")
    position = {"line": args.line - 1, "character": len(lines[args.line - 1][:args.column - 1].encode("utf-16-le")) // 2}
    if deadline is not None:
        deadline.check()
    connection = Connection(command, str(root), allow_custom=allow_custom,
                            **({"deadline": deadline, "monitor": False} if deadline is not None else {}))
    try:
        initialization = connection.request("initialize", {
            "processId": os.getpid(), "rootUri": root.as_uri(),
            "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
            "capabilities": {"general": {"positionEncodings": ["utf-16"]},
                             "workspace": {"configuration": True, "workspaceFolders": True},
                             "textDocument": {"publishDiagnostics": {"versionSupport": True},
                                              "diagnostic": {"dynamicRegistration": False, "relatedDocumentSupport": False},
                                              "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                                              "definition": {"linkSupport": True}}},
        })
        if not isinstance(initialization, dict) or not isinstance(initialization.get("capabilities"), dict):
            raise LspError("Invalid language-server initialization response")
        if initialization["capabilities"].get("positionEncoding", "utf-16") != "utf-16":
            raise LspError("Language server did not negotiate UTF-16 positions")
        provider = initialization["capabilities"].get("diagnosticProvider")
        if provider is not None:
            require(isinstance(provider, dict) and type(provider.get("interFileDependencies")) is bool
                    and type(provider.get("workspaceDiagnostics")) is bool, "diagnosticProvider capability")
            if "identifier" in provider:
                require(isinstance(provider["identifier"], str), "diagnosticProvider identifier")
        connection.notify("initialized", {})
        connection.notify("textDocument/didOpen", {"textDocument": {
            "uri": path.as_uri(), "languageId": language, "version": 1, "text": text,
        }})
        methods = {"symbols": "textDocument/documentSymbol", "definition": "textDocument/definition",
                   "references": "textDocument/references"}
        index_unverified = False
        if args.action == "diagnostics":
            result, complete = connection.diagnostics(path.as_uri(), provider)
        else:
            params = {"textDocument": {"uri": path.as_uri()}}
            if args.action != "symbols":
                params["position"] = position
            if args.action == "references":
                params["context"] = {"includeDeclaration": True}
            result = connection.request(methods[args.action], params)
            validate_navigation(args.action, result)
            # Navigation responses are valid partial data, but this one-shot
            # client never establishes clangd's project-index readiness. Extra
            # server flags alone do not establish it either.
            index_unverified = language in ("c", "cpp") and args.action in ("definition", "references")
            complete = not index_unverified
        payload = {"status": "ok" if complete else "unverified", "complete": complete,
                   "action": args.action, "server": getattr(command[0], "executable", command[0]),
                   "file": str(path.relative_to(root)), "result": result}
        if index_unverified:
            fallback_messages = {
                "project_index_not_verified": "Project index readiness was not verified; targets in other translation units may be missing.",
                "no_compile_db": "No supported compile database was found; this is a partial C/C++ navigation result.",
                "compile_db_unsupported": "The compile database is outside the supported indexing subset; this is a partial C/C++ navigation result.",
                "config_unsupported": "A clangd configuration is present; this is a partial C/C++ navigation result.",
                "index_disabled": "Indexing is disabled; this is a partial C/C++ navigation result.",
                "index_deadline": "Index work reached its deadline; retry only when index.progress_increased is true.",
                "lock_timeout": "Another query holds the index cache; this is a partial C/C++ navigation result.",
                "cache_limit": "The private index cache could not meet its cleanup target; this is a partial result.",
                "index_resource_limit": "The indexed server reached a resource guard; this is a partial result.",
                "index_coverage_unverified": "Index shards did not verify coverage for every compile-database TU.",
                "index_had_errors": "clangd recorded errors while indexing; project-wide coverage is unverified.",
                "index_inputs_changed": "CDB or clangd configuration inputs changed during the query.",
                "index_unavailable": "Indexed navigation could not be verified; this is a partial result.",
            }
            payload.update(reason=fallback_reason or "project_index_not_verified",
                           message=fallback_messages.get(
                               fallback_reason,
                               "Partial C/C++ navigation result; project-wide completeness is not verified."
                               if fallback_reason else fallback_messages["project_index_not_verified"]))
        if index_metadata is not None:
            payload["index"] = index_metadata
    finally:
        try:
            connection.close()
        except IndexUnavailable as exc:
            if deadline is None or "payload" not in locals():
                raise
            complete = False
            payload.update(status="unverified", complete=False, reason=exc.reason, message=exc.message)
    print_result(payload)
    if args.action == "diagnostics" and any(item.get("severity", 1) == 1 for item in result):
        return 1
    return 0 if complete else 2


def _fallback(args, root, path, text, language, command, *, fallback_reason, index_metadata, deadline):
    try:
        return _query_standard(args, root, path, text, language, command,
                               fallback_reason=fallback_reason, index_metadata=index_metadata, deadline=deadline)
    except (IndexUnavailable, LspError, OSError) as exc:
        cause = exc.reason if isinstance(exc, IndexUnavailable) else "index_response_unverified"
        print_result({"status": "unverified", "complete": False, "action": args.action,
                      "file": str(path.relative_to(root)), "reason": fallback_reason, "cause": cause,
                      "message": "Partial navigation could not finish within its shared budget or response contract.",
                      "index": index_metadata})
        return 2


def _navigation_params(args, path, position):
    params = {"textDocument": {"uri": path.as_uri()}, "position": position}
    if args.action == "references":
        params["context"] = {"includeDeclaration": True}
    return params


def _initialize(connection, root, path, language, text, *, progress=False):
    capabilities = {"general": {"positionEncodings": ["utf-16"]},
                    "workspace": {"configuration": True, "workspaceFolders": True},
                    "textDocument": {"publishDiagnostics": {"versionSupport": True},
                                     "diagnostic": {"dynamicRegistration": False, "relatedDocumentSupport": False},
                                     "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                                     "definition": {"linkSupport": True}}}
    if progress:
        capabilities["window"] = {"workDoneProgress": True}
    result = connection.request("initialize", {
        "processId": os.getpid(), "rootUri": root.as_uri(),
        "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
        "capabilities": capabilities,
    })
    if not isinstance(result, dict) or not isinstance(result.get("capabilities"), dict):
        raise LspError("Invalid language-server initialization response")
    if result["capabilities"].get("positionEncoding", "utf-16") != "utf-16":
        raise LspError("Language server did not negotiate UTF-16 positions")
    connection.notify("initialized", {})
    connection.notify("textDocument/didOpen", {"textDocument": {
        "uri": path.as_uri(), "languageId": language, "version": 1, "text": text,
    }})
    return result.get("capabilities", {})


def _cleanup_deadline(deadline):
    now = deadline.clock()
    remaining = deadline.remaining(cleanup=True)
    if remaining <= 0:
        raise IndexUnavailable("index_deadline", "Index cleanup deadline reached")
    return Deadline(remaining, started=now, reserve=0, clock=deadline.clock)


def _indexed_result(args, root, path, text, language, command):
    deadline = Deadline(NEW_KEY_SECONDS, reserve=CLEANUP_SECONDS)
    allow_custom = False
    env = child_environment(root, allow_custom, getattr(command[0], "workspace_identity", None))
    try:
        database, cdb_stamp, config_inventory = discover_compile_database(root, path, env, deadline)
        server, engine_identity, sdk_identity, root_identity = _indexed_toolchain(command, root, env, deadline)
        cache_key = key_for(cdb=database.raw, source_identities=database.source_key,
                            root_identity=[str(root), *root_identity], engine_identity=engine_identity,
                            compiler_identities=database.compiler_identities, sdk_identity=sdk_identity,
                            config_inventory=config_inventory, environment=env)
        plugin_root = Path(__file__).resolve().parents[1]
        cache = Cache(_cache_root(env), root, plugin_root)
    except IndexUnavailable as exc:
        preflight = {"scope": "selected_compile_database", "cache_path": None, "cache_key": None,
                     "cache_classification": None, "cache_attempted": False, "cache_reused": False,
                     "deadline_seconds": NEW_KEY_SECONDS, "readiness": "not_observed",
                     "persisted_shards_before": 0, "persisted_shards_after": 0,
                     "covered_tu_count": 0, "progress_increased": False}
        return _fallback(args, root, path, text, language, command,
                               fallback_reason=exc.reason, index_metadata=preflight, deadline=deadline)
    except (OSError, RuntimeError, ValueError):
        unavailable = IndexUnavailable("index_unavailable", "Indexed preflight could not be completed safely")
        preflight = {"scope": "selected_compile_database", "cache_path": None, "cache_key": None,
                     "cache_classification": None, "cache_attempted": False, "cache_reused": False,
                     "deadline_seconds": NEW_KEY_SECONDS, "readiness": "not_observed",
                     "persisted_shards_before": 0, "persisted_shards_after": 0,
                     "covered_tu_count": 0, "progress_increased": False}
        return _fallback(args, root, path, text, language, command,
                               fallback_reason=unavailable.reason, index_metadata=preflight, deadline=deadline)

    lines = re.split(r"\r\n|\r|\n", text)
    if not 1 <= args.line <= len(lines) or not 1 <= args.column <= len(lines[args.line - 1]) + 1:
        cache.close()
        raise ValueError("Position is outside the source file (line/column start at 1)")
    position = {"line": args.line - 1,
                "character": len(lines[args.line - 1][:args.column - 1].encode("utf-16-le")) // 2}
    method = {"definition": "textDocument/definition", "references": "textDocument/references"}[args.action]
    server_path = str(getattr(server, "executable", server))
    result = None
    reason = None
    message = None
    cause = None
    complete = False
    metadata = {
        "scope": "selected_compile_database", "input_tu_count": len(database.sources),
        "covered_tu_count": 0, "persisted_shards_before": 0, "persisted_shards_after": 0,
        "cache_path": None, "cache_key": cache_key, "cache_classification": None,
        "cache_attempted": False, "cache_reused": False,
        "deadline_seconds": None, "readiness": "not_observed", "progress_increased": False,
    }
    connection = None
    connection_started = False
    discard_untrusted = False
    try:
        with cache, cache.lease(cache_key, deadline) as lease:
                metadata["cache_path"] = str(lease.path)
                previous_failure = _consume_failure(lease)
                attempt = lease.begin_attempt()
                metadata["cache_classification"] = attempt["classification"]
                metadata["cache_attempted"] = True
                metadata["deadline_seconds"] = attempt["total_seconds"]
                if previous_failure:
                    metadata["previous_failure"] = previous_failure
                lease.write_cdb(database.raw)
                before = lease.usage()
                metadata["persisted_shards_before"] = before["persisted_shards"]
                before_coverage = (
                    certify(lease.fd, list(database.sources), deadline, validate_anchor=lease.validate)
                    if before["persisted_shards"] else
                    Coverage(len(database.sources), 0, False, "index_coverage_unverified")
                )
                metadata["covered_tu_before"] = before_coverage.covered
                metadata["cache_reused"] = before_coverage.covered > 0
                indexed_env = dict(env, TMPDIR=str(lease.prepare_tmp()))
                indexed_env["TMP"] = indexed_env["TEMP"] = indexed_env["TMPDIR"]
                try:
                    connection = Connection(
                        indexed_server_command(server, lease.path), str(root), allow_custom=False,
                        deadline=lease.deadline, env=indexed_env, pass_fds=(lease.global_lock_fd,),
                        monitor=True, disk_check=lease.check_disk,
                    )
                    connection_started = True
                    _initialize(connection, root, path, language, text, progress=True)
                    initial_result = connection.request(method, _navigation_params(args, path, position))
                    validate_navigation(args.action, initial_result)
                    result = initial_result
                    connection.wait_for_background_index()
                    metadata["readiness"] = "progress_end"
                    coverage = certify(lease.fd, list(database.sources), deadline,
                                       validate_anchor=lease.validate)
                    metadata["covered_tu_count"] = coverage.covered
                    if not coverage.complete:
                        raise IndexUnavailable(coverage.reason or "index_coverage_unverified",
                                               "Background index coverage could not be verified")
                    if not cdb_unchanged(database, cdb_stamp) or not config_still_absent(config_inventory):
                        raise IndexUnavailable("index_inputs_changed", "Index inputs changed during the query")
                    final_result = connection.request(method, _navigation_params(args, path, position))
                    validate_navigation(args.action, final_result)
                    result = final_result
                    try:
                        connection.finish_indexed(graceful=True)
                    except IndexUnavailable:
                        discard_untrusted = not getattr(connection, "cleanup_verified", False)
                        raise
                    connection = None
                    if not cdb_unchanged(database, cdb_stamp) or not config_still_absent(config_inventory):
                        raise IndexUnavailable("index_inputs_changed", "Index inputs changed before result completion")
                    complete = True
                except IndexUnavailable as exc:
                    reason, message = exc.reason, exc.message
                except (LspError, LspBudgetExceeded) as exc:
                    connection._stream_failed = True
                    reason = ("index_deadline" if lease.deadline.remaining() <= 0 else
                              "index_response_limit" if isinstance(exc, LspBudgetExceeded) else
                              "index_response_unverified")
                    message = "Indexed navigation did not complete a validated response."
                except (OSError, RuntimeError, ValueError, RecursionError):
                    reason = "index_unavailable"
                    message = "Indexed navigation could not be completed safely."
                finally:
                    if connection is not None:
                        try:
                            connection.finish_indexed(graceful=True)
                        except IndexUnavailable as exc:
                            discard_untrusted = not getattr(connection, "cleanup_verified", False)
                            if reason is None:
                                reason, message = exc.reason, exc.message
                        except (OSError, RuntimeError, LspError):
                            discard_untrusted = not getattr(connection, "cleanup_verified", False)
                            if reason is None:
                                reason, message = "index_unavailable", "Indexed server cleanup could not be verified."
                        guard_reason = getattr(connection, "guard_reason", None)
                        if guard_reason in ("cache_limit", "index_resource_limit", "index_transient_limit"):
                            if reason and reason != guard_reason:
                                cause = reason
                            reason = guard_reason
                            message = "Indexed server stopped at its resource or work guard."
                        connection = None
                try:
                    lease.clear_tmp()
                    after = lease.usage(cleanup=True)
                    metadata["persisted_shards_after"] = after["persisted_shards"]
                    cleanup_deadline = _cleanup_deadline(deadline)
                    after_coverage = certify(lease.fd, list(database.sources), cleanup_deadline,
                                             validate_anchor=lease.validate)
                    metadata["covered_tu_count"] = after_coverage.covered
                    metadata["progress_increased"] = after_coverage.covered > before_coverage.covered
                    if complete and not after_coverage.complete:
                        complete = False
                        reason = after_coverage.reason or "index_coverage_unverified"
                        message = "Background index coverage changed before completion."
                except IndexUnavailable as exc:
                    discard_untrusted = discard_untrusted or exc.reason == "index_unavailable"
                    if complete:
                        complete = False
                        reason, message = exc.reason, exc.message
                if reason in ("cache_limit", "index_resource_limit") or discard_untrusted:
                    with contextlib.suppress(IndexUnavailable):
                        lease.discard(reason)
    except IndexUnavailable as exc:
        complete = False
        if reason is None:
            reason, message = exc.reason, exc.message
    except (OSError, RuntimeError, ValueError):
        complete = False
        if reason is None:
            reason, message = "index_unavailable", "Indexed cache operation could not be completed safely."
    if not connection_started:
        return _fallback(args, root, path, text, language, command,
                               fallback_reason=reason or "index_unavailable", index_metadata=metadata, deadline=deadline)
    payload = {"status": "ok" if complete else "unverified", "complete": complete,
               "action": args.action, "server": server_path,
               "file": str(path.relative_to(root)), "index": metadata}
    if result is not None:
        payload["result"] = result
    if cause is not None:
        payload["cause"] = cause
    if not complete:
        reason = reason or "index_unavailable"
        payload["reason"] = reason
        payload["message"] = message or "Partial C/C++ navigation result; project-wide completeness is not verified."
    print_result(payload)
    return 0 if complete else 2


def query(args: argparse.Namespace) -> int:
    allow_custom = getattr(args, "allow_custom_server", False)
    if getattr(args, "server_arg", []) and not allow_custom:
        raise ValueError("--server-arg requires --allow-custom-server (arbitrary code execution and writes)")
    root, path, text = read_source(args.root, args.file, MAX_SOURCE_BYTES)
    language = LANGUAGES.get(path.suffix, "plaintext")
    command = select_server(language, args.server, allow_custom, root)
    if command is None:
        return _query_standard(args, root, path, text, language, command)
    index_action = language in ("c", "cpp") and args.action in ("definition", "references")
    if not index_action:
        return _query_standard(args, root, path, text, language, command)
    if os.environ.get(INDEX_DISABLE_ENV) == "0":
        return _query_standard(args, root, path, text, language, command, fallback_reason="index_disabled")
    supported = (os.name == "posix" and sys.platform in ("darwin", "linux", "linux2")
                 and not allow_custom and not args.server_arg
                 and Path(getattr(command[0], "executable", command[0])).name == "clangd")
    if not supported:
        fallback = ("index_unavailable" if os.name != "posix" or sys.platform not in ("darwin", "linux", "linux2")
                    else "project_index_not_verified")
        return _query_standard(args, root, path, text, language, command,
                               fallback_reason=fallback)
    return _indexed_result(args, root, path, text, language, command)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("diagnostics", "symbols", "definition", "references"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--file", required=True)
    parser.add_argument("--line", type=int, default=1)
    parser.add_argument("--column", type=int, default=1)
    parser.add_argument("--server", help="Known installed server: bare name or absolute path matching PATH; relative paths are forbidden")
    parser.add_argument("--allow-custom-server", action="store_true",
                        help="Permit custom, workspace, or relative PATH servers: arbitrary code execution; explicit relative paths remain forbidden")
    parser.add_argument("--server-arg", action="append", default=[],
                        help="Append to server defaults (repeatable); requires --allow-custom-server and permits code execution/writes")
    try:
        return query(parser.parse_args())
    except SourceUnavailable as exc:
        print_result({"status": "unavailable", "complete": False, "reason": str(exc)})
        return 3
    except LspBudgetExceeded as exc:
        print_result({"status": "unverified", "complete": False, "reason": str(exc)})
        return 2
    except (OSError, ValueError, LspError) as exc:
        print_result({"status": "error", "complete": False, "reason": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
