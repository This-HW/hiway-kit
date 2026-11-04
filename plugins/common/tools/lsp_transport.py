"""Bounded stdio transport for one read-only language-server conversation."""
from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import threading
import time
from contextlib import suppress

from intel_runtime import child_environment
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
    def __init__(self, command: list[str], cwd: str):
        self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        start_new_session=True, env=child_environment())
        self.messages = queue.Queue(maxsize=MAX_PENDING_MESSAGES)
        self.notifications = []
        self.notification_count = 0
        self.received_bytes = 0
        self.counter = 0
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

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
                if length is None or not 0 <= length <= MAX_MESSAGE_BYTES:
                    raise LspError("Invalid LSP Content-Length")
                raw = account(self.process.stdout.read(min(length, MAX_RECEIVED_BYTES - self.received_bytes + 1)))
                if len(raw) != length:
                    raise LspError("Truncated LSP response")
                message = json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_constant)
                validate_message(message)
                if "method" in message and "id" not in message:
                    self.notification_count += 1
                    if self.notification_count > MAX_PENDING_MESSAGES:
                        raise LspBudgetExceeded("Language-server notification budget exceeded; result is unverified")
                    if message["method"] != "textDocument/publishDiagnostics":
                        # Count log/progress notifications without retaining
                        # their payloads in either the queue or history.
                        del message, raw
                        continue
                self.messages.put(message, timeout=REQUEST_TIMEOUT)
        except (OSError, ValueError, RecursionError, LspError, queue.Full) as exc:
            try:
                self.messages.put(exc if isinstance(exc, LspError) else LspError(str(exc)), timeout=1)
            except queue.Full:
                self.process.terminate()

    def send(self, message) -> None:
        raw = json.dumps(message).encode("utf-8")
        errors = []

        def write() -> None:
            try:
                self.process.stdin.write(f"Content-Length: {len(raw)}\r\n\r\n".encode() + raw)
                self.process.stdin.flush()
            except (OSError, ValueError) as exc:
                errors.append(str(exc))

        writer = threading.Thread(target=write, daemon=True)
        writer.start()
        writer.join(timeout=REQUEST_TIMEOUT)
        if writer.is_alive():
            raise LspError("Language server input timed out")
        if errors:
            raise LspError(errors[0])

    def notify(self, method: str, params) -> None:
        self.send({"jsonrpc": "2.0", "method": method, "params": params})

    def receive(self, deadline: float):
        try:
            message = self.messages.get(timeout=max(0, deadline - time.monotonic()))
        except queue.Empty as exc:
            raise LspError("Language server response timed out; result is unverified") from exc
        if isinstance(message, LspError):
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
                    raise LspError("Language-server notification budget exceeded; result is unverified")
                self.notifications.append(message)
        return message

    def request(self, method: str, params):
        self.counter += 1
        request_id = self.counter
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + REQUEST_TIMEOUT
        while time.monotonic() < deadline:
            message = self.receive(deadline)
            if "method" not in message:
                if type(message["id"]) is not int or message["id"] != request_id:
                    raise LspError("Unexpected JSON-RPC response ID; result is unverified")
                if "error" in message:
                    raise LspError(str(message["error"]))
                if "result" not in message:
                    raise LspError("JSON-RPC response has no result")
                return message["result"]
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
        try:
            if os.name == "posix":
                os.killpg(self.process.pid, signal.SIGTERM)
            elif self.process.poll() is None:
                self.process.terminate()
        except ProcessLookupError:
            pass
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=3)
        if os.name == "posix":
            with suppress(ProcessLookupError):
                os.killpg(self.process.pid, signal.SIGKILL)
        # A server that exits during a write may leave a broken buffered pipe;
        # still close the other stream and join the reader in that case.
        with suppress(OSError):
            self.process.stdin.close()
        with suppress(OSError):
            self.process.stdout.close()
        self.reader.join(timeout=1)
