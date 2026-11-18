"""Bounded stdio transport for trusted servers; declining client edits is not a sandbox."""
from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import threading
import time
from contextlib import suppress
from pathlib import Path

from intel_runtime import child_environment
from lsp_index_policy import IndexUnavailable
from lsp_index_resources import ResourceGuard
from lsp_validation import (
    LspBudgetExceeded,
    LspError,
    validate_message,
    validate_publish,
    validate_pull_report,
)

MAX_MESSAGE_BYTES = 2 * 1024 * 1024
MAX_RECEIVED_BYTES = 16 * 1024 * 1024
MAX_PENDING_MESSAGES = 128
REQUEST_TIMEOUT = 15
BACKGROUND_INDEX = "backgroundIndexProgress"


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LspError("Duplicate JSON object key; result is unverified")
        result[key] = value
    return result


def _invalid_constant(value):
    raise LspError("Invalid JSON constant: " + value)


class Connection:
    def __init__(self, command: list[str], cwd: str, *, allow_custom: bool = False,
                 deadline=None, env=None, pass_fds=(), monitor=False, disk_check=None):
        self.guard_reason = None
        self.cleanup_verified = False
        self._stream_failed = False
        self._indexed_finished = False
        self.deadline = deadline
        self.guard = None
        self._write_lock = threading.Lock()
        self.process = subprocess.Popen(command, executable=getattr(command[0], "executable", command[0]), cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        start_new_session=True,
                                        pass_fds=tuple(pass_fds),
                                        env=(env if env is not None else
                                             child_environment(Path(cwd), allow_custom,
                                                               getattr(command[0], "workspace_identity", None))))
        if monitor:
            try:
                self.guard = ResourceGuard(self.process, deadline, disk_check=disk_check).start()
            except BaseException:
                with suppress(OSError):
                    os.killpg(self.process.pid, signal.SIGKILL)
                with suppress(Exception):
                    self.process.wait(timeout=1)
                raise
        self.messages = queue.Queue(maxsize=MAX_PENDING_MESSAGES)
        self.notifications = []
        self.notification_count = 0
        self.received_bytes = 0
        self.counter = 0
        self._progress_lock = threading.Lock()
        self._progress_tokens = set()
        self._progress_started = False
        self._progress_ended = False
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _remaining(self, *, cleanup=False):
        budget = getattr(self, "deadline", None)
        if budget is None:
            return REQUEST_TIMEOUT
        budget.check(cleanup=cleanup)
        remaining = budget.remaining(cleanup=cleanup)
        guard = getattr(self, "guard", None)
        if not cleanup and guard is not None and guard.cancelled.is_set():
            raise IndexUnavailable(self.guard.reason or "index_unavailable",
                                   "Indexed language-server process was cancelled")
        return min(REQUEST_TIMEOUT, remaining)

    def _accept_progress(self, message):
        params = message.get("params")
        if not isinstance(params, dict) or set(params) != {"token", "value"}:
            raise LspError("Invalid work-done progress parameters")
        token, value = params["token"], params["value"]
        if token != BACKGROUND_INDEX:
            return
        if not isinstance(value, dict) or value.get("kind") not in ("begin", "report", "end"):
            raise LspError("Invalid background-index progress value")
        with self._progress_lock:
            if token not in self._progress_tokens:
                raise LspError("Background-index progress arrived without token creation")
            kind = value["kind"]
            if kind == "begin":
                if self._progress_started or self._progress_ended:
                    raise LspError("Invalid duplicate background-index begin")
                if not isinstance(value.get("title"), str) or not value["title"]:
                    raise LspError("Invalid background-index progress title")
                self._progress_started = True
            elif kind == "report":
                if not self._progress_started or self._progress_ended:
                    raise LspError("Background-index report outside begin/end")
            else:
                if not self._progress_started or self._progress_ended:
                    raise LspError("Background-index end without a matching begin")
                self._progress_ended = True

    def _create_progress(self, message):
        params = message.get("params")
        token = params.get("token") if isinstance(params, dict) and set(params) == {"token"} else None
        if not (isinstance(token, str) or type(token) is int):
            raise LspError("Invalid work-done progress token")
        with self._progress_lock:
            if token in self._progress_tokens:
                raise LspError("Duplicate work-done progress token")
            self._progress_tokens.add(token)
        # clangd's create request precedes its progress notification. Reply in
        # the reader thread so the server can safely continue indexing.
        self.send({"jsonrpc": "2.0", "id": message["id"], "result": None})

    def _read(self) -> None:
        def account(raw):
            self.received_bytes += len(raw)
            if self.received_bytes > MAX_RECEIVED_BYTES:
                raise LspBudgetExceeded("Language-server receive byte budget exceeded; result is unverified")
            return raw

        try:
            while True:
                length = None
                header_size = 0
                while True:
                    line = account(self.process.stdout.readline(min(8193, MAX_RECEIVED_BYTES - self.received_bytes + 1)))
                    header_size += len(line)
                    if not line:
                        raise LspError("Language server closed stdout")
                    if header_size > 8192:
                        raise LspError("Oversized LSP header")
                    if line in (b"\r\n", b"\n"):
                        break
                    name, separator, value = line.partition(b":")
                    if separator and name.lower() == b"content-length":
                        length = int(value.strip())
                if length is None or length < 0:
                    raise LspError("Invalid LSP Content-Length")
                if length > MAX_MESSAGE_BYTES:
                    raise LspBudgetExceeded("Language-server message byte budget exceeded")
                raw = account(self.process.stdout.read(min(length, MAX_RECEIVED_BYTES - self.received_bytes + 1)))
                if len(raw) != length:
                    raise LspError("Truncated LSP response")
                message = json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_constant)
                validate_message(message)
                if message.get("method") == "window/workDoneProgress/create" and "id" in message:
                    self._create_progress(message)
                    continue
                if message.get("method") == "$/progress" and "id" not in message:
                    self._accept_progress(message)
                    continue
                if "method" in message and "id" not in message:
                    if message["method"] != "textDocument/publishDiagnostics":
                        # The receive byte budget bounds discarded log/progress
                        # notifications; only retained diagnostics count below.
                        del message, raw
                        continue
                    self.notification_count += 1
                    if self.notification_count > MAX_PENDING_MESSAGES:
                        raise LspBudgetExceeded("Language-server notification budget exceeded; result is unverified")
                self.messages.put(message, timeout=REQUEST_TIMEOUT)
        except (OSError, ValueError, RecursionError, LspError, IndexUnavailable, queue.Full) as exc:
            self._stream_failed = True
            try:
                self.messages.put(exc if isinstance(exc, (LspError, IndexUnavailable)) else LspError(str(exc)),
                                   timeout=1)
            except queue.Full:
                self.process.terminate()

    def send(self, message, *, cleanup=False) -> None:
        raw = json.dumps(message).encode("utf-8")
        errors = []

        def write() -> None:
            try:
                with self._write_lock:
                    self.process.stdin.write(f"Content-Length: {len(raw)}\r\n\r\n".encode() + raw)
                    self.process.stdin.flush()
            except (OSError, ValueError) as exc:
                errors.append(str(exc))

        timeout = self._remaining(cleanup=cleanup)
        writer = threading.Thread(target=write, daemon=True)
        writer.start()
        writer.join(timeout=timeout)
        if writer.is_alive():
            if getattr(self, "deadline", None) is not None and self.deadline.remaining(cleanup=cleanup) <= 0:
                self._remaining(cleanup=cleanup)
            self._stream_failed = True
            raise LspError("Language server input timed out")
        if errors:
            raise LspError(errors[0])

    def notify(self, method: str, params) -> None:
        self.send({"jsonrpc": "2.0", "method": method, "params": params})

    def receive(self, deadline: float, *, cleanup=False):
        if getattr(self, "deadline", None) is not None:
            self._remaining(cleanup=cleanup)
            deadline = min(deadline, time.monotonic() + self.deadline.remaining(cleanup=cleanup))
        try:
            message = self.messages.get(timeout=max(0, deadline - time.monotonic()))
        except queue.Empty as exc:
            if getattr(self, "deadline", None) is not None and self.deadline.remaining(cleanup=cleanup) <= 0:
                self._remaining(cleanup=cleanup)
            self._stream_failed = True
            raise LspError("Language server response timed out; result is unverified") from exc
        if isinstance(message, (LspError, IndexUnavailable)):
            raise message
        validate_message(message)
        if "method" in message and "id" in message:
            method = message["method"]
            result = None
            if method == "workspace/configuration":
                items = message.get("params", {}).get("items", [])
                if not isinstance(items, list) or len(items) > MAX_PENDING_MESSAGES:
                    raise LspError("Invalid configuration request")
                result = [None] * len(items)
            elif method == "workspace/workspaceFolders":
                result = []
            elif method == "workspace/applyEdit":
                result = {"applied": False, "failureReason": "read-only client"}
            else:
                self.send({"jsonrpc": "2.0", "id": message["id"],
                           "error": {"code": -32601, "message": "Unsupported client method"}})
                raise LspError("Unsupported language-server request: " + method)
            self.send({"jsonrpc": "2.0", "id": message["id"], "result": result})
        elif "method" in message:
            if message["method"] == "textDocument/publishDiagnostics":
                validate_publish(message.get("params"))
                if len(self.notifications) >= MAX_PENDING_MESSAGES:
                    raise LspBudgetExceeded("Language-server notification budget exceeded; result is unverified")
                self.notifications.append(message)
        return message

    def wait_for_background_index(self):
        """Wait only for clangd's created backgroundIndexProgress begin/end token."""
        if self.deadline is None:
            raise LspError("Index readiness requires an absolute deadline")
        while True:
            self._remaining()
            with self._progress_lock:
                if self._progress_ended:
                    return "progress_end"
            timeout = min(0.05, self._remaining())
            try:
                message = self.messages.get(timeout=timeout)
            except queue.Empty:
                continue
            if isinstance(message, (LspError, IndexUnavailable)):
                raise message
            # Drain server requests and diagnostics while indexing. Any response
            # not associated with a client request is a protocol failure.
            if "method" in message and "id" in message:
                self._respond_to_server_request(message)
            elif "method" in message:
                if message["method"] == "textDocument/publishDiagnostics":
                    validate_publish(message.get("params"))
                    if len(self.notifications) >= MAX_PENDING_MESSAGES:
                        raise LspBudgetExceeded("Language-server notification budget exceeded; result is unverified")
                    self.notifications.append(message)
            else:
                raise LspError("Unexpected server response while awaiting background-index readiness")

    def _respond_to_server_request(self, message):
        method = message["method"]
        params = message.get("params", {})
        if method == "workspace/configuration":
            items = params.get("items", [])
            if not isinstance(items, list) or len(items) > MAX_PENDING_MESSAGES:
                raise LspError("Invalid configuration request")
            result = [None] * len(items)
        elif method == "workspace/workspaceFolders":
            result = []
        elif method == "workspace/applyEdit":
            result = {"applied": False, "failureReason": "read-only client"}
        else:
            self.send({"jsonrpc": "2.0", "id": message["id"],
                       "error": {"code": -32601, "message": "Unsupported client method"}})
            raise LspError("Unsupported language-server request: " + method)
        self.send({"jsonrpc": "2.0", "id": message["id"], "result": result})

    def request(self, method: str, params, *, cleanup=False):
        timeout = self._remaining(cleanup=cleanup)
        self.counter += 1
        request_id = self.counter
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}, cleanup=cleanup)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = self.receive(deadline, cleanup=cleanup)
            if "method" not in message:
                if type(message["id"]) is not int or message["id"] != request_id:
                    raise LspError("Unexpected JSON-RPC response ID; result is unverified")
                if "error" in message:
                    raise LspError(str(message["error"]))
                if "result" not in message:
                    raise LspError("JSON-RPC response has no result")
                return message["result"]
        self._stream_failed = True
        raise LspError("Language server request timed out")

    def diagnostics(self, uri: str, provider=None):
        if provider is not None:
            params = {"textDocument": {"uri": uri}}
            if "identifier" in provider:
                params["identifier"] = provider["identifier"]
            # One-shot requests have no cached result and must receive a full
            # report. An unchanged report without previousResultId is invalid.
            result, _ = validate_pull_report(self.request("textDocument/diagnostic", params))
            return result, True
        deadline = time.monotonic() + REQUEST_TIMEOUT
        while time.monotonic() < deadline:
            batches = [message["params"]["diagnostics"] for message in self.notifications
                       if message.get("method") == "textDocument/publishDiagnostics"
                       and message["params"]["uri"] == uri and message["params"].get("version", 1) == 1]
            if batches:
                # Consume already queued pushes, without claiming a quiet period
                # is a completion signal. Retain errors observed before a clear.
                if not self.messages.empty():
                    self.receive(deadline)
                    continue
                result = list(batches[-1])
                seen = {json.dumps(item, sort_keys=True) for item in result}
                for batch in batches[:-1]:
                    for item in batch:
                        key = json.dumps(item, sort_keys=True)
                        if item.get("severity", 1) == 1 and key not in seen:
                            result.append(item)
                            seen.add(key)
                return result, False
            self.receive(deadline)
        raise LspError("No diagnostics received; result is unverified")

    def close(self) -> None:
        if getattr(self, "_indexed_finished", False):
            return
        if getattr(self, "guard", None) is not None:
            self.finish_indexed(graceful=False)
            return
        if getattr(self, "deadline", None) is not None:
            # Fallback shares the time budget, not indexed RSS/disk policy.
            # Kill the still-waitable leader's group before reaping its PID.
            try:
                if self.process.returncode is None:
                    with suppress(ProcessLookupError):
                        os.killpg(self.process.pid, signal.SIGKILL)
                    try:
                        self.process.wait(timeout=max(.05, self.deadline.remaining(cleanup=True)))
                    except subprocess.TimeoutExpired as exc:
                        raise IndexUnavailable("index_deadline", "Fallback child exit exceeded its cleanup deadline") from exc
            finally:
                with suppress(OSError, ValueError):
                    self.process.stdin.close()
                with suppress(OSError, ValueError):
                    self.process.stdout.close()
                self.reader.join(timeout=self.deadline.remaining(cleanup=True))
                self._indexed_finished = True
            return
        def signal_group(sig):
            try:
                os.killpg(self.process.pid, sig)
            except ProcessLookupError:
                return
            except PermissionError as denied:
                # A leader can be entering zombie state before poll observes
                # its exit. Allow a short bounded reap, never a live denial.
                if self.process.poll() is None:
                    try:
                        self.process.wait(timeout=0.05)
                    except subprocess.TimeoutExpired:
                        raise denied from None
                try:
                    os.killpg(self.process.pid, sig)
                except ProcessLookupError:
                    return
                except PermissionError:
                    if self.process.poll() is None:
                        raise
                    # Reaped/zombie-only groups can still return EPERM. A
                    # second denial must not mask the query result or error.

        try:
            if os.name == "posix":
                signal_group(signal.SIGTERM)
            elif self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        finally:
            try:
                if os.name == "posix":
                    signal_group(signal.SIGKILL)
            finally:
                # Finish local cleanup even if a live signal denial is raised.
                with suppress(OSError):
                    self.process.stdin.close()
                with suppress(OSError):
                    self.process.stdout.close()
                self.reader.join(timeout=1)

    def finish_indexed(self, *, graceful=True):
        """Shut down and reap an indexed server while the cache lease is held."""
        if getattr(self, "_indexed_finished", False):
            return
        if self.guard is None:
            return self.close()
        guard = self.guard
        error = None
        voluntary = False
        try:
            healthy = not getattr(self, "_stream_failed", False) and self.reader.is_alive()
            if (graceful and healthy and not guard.cancelled.is_set()
                    and guard.reason is None and self.deadline.remaining() > 0):
                try:
                    self.request("shutdown", None)
                    self.send({"jsonrpc": "2.0", "method": "exit", "params": None})
                    with suppress(OSError, ValueError):
                        self.process.stdin.close()
                    voluntary = True
                except (LspError, IndexUnavailable, OSError, ValueError):
                    # A broken handshake is not an untrusted cache. The guard's
                    # verified group kill/reap below owns cleanup trust.
                    guard._kill()
            else:
                guard._kill()
            if voluntary:
                guard.reap(graceful=True)
            else:
                guard.reap()
        except BaseException as exc:
            error = exc
            try:
                guard._kill()
                guard.reap()
            except BaseException:
                pass
        finally:
            try:
                guard.close()
            except BaseException as exc:
                if error is None:
                    error = exc
            self.guard_reason = guard.reason
            self.cleanup_verified = guard.cleanup_verified
            self.guard = None
            self._indexed_finished = True
            with suppress(OSError):
                self.process.stdin.close()
            with suppress(OSError):
                self.process.stdout.close()
            self.reader.join(timeout=1)
        if error is not None:
            raise error
