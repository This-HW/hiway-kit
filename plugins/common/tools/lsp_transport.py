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

MAX_MESSAGE_BYTES = 2 * 1024 * 1024
MAX_PENDING_MESSAGES = 128
REQUEST_TIMEOUT = 15


class LspError(RuntimeError):
    pass


class Connection:
    def __init__(self, command: list[str], cwd: str):
        self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        start_new_session=True)
        self.messages = queue.Queue(maxsize=MAX_PENDING_MESSAGES)
        self.notifications = []
        self.counter = 0
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        try:
            while True:
                length = None
                header_size = 0
                while True:
                    line = self.process.stdout.readline(8193)
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
                raw = self.process.stdout.read(length)
                if len(raw) != length:
                    raise LspError("Truncated LSP response")
                message = json.loads(raw)
                if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                    raise LspError("Invalid JSON-RPC response")
                if "method" in message and (not isinstance(message["method"], str) or not isinstance(message.get("params", {}), dict)):
                    raise LspError("Invalid LSP method or parameters")
                self.messages.put(message, timeout=REQUEST_TIMEOUT)
        except (OSError, ValueError, LspError, queue.Full) as exc:
            try:
                self.messages.put(LspError(str(exc)), timeout=1)
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
            self.send({"jsonrpc": "2.0", "id": message["id"], "result": result})
        elif "method" in message:
            if len(self.notifications) >= MAX_PENDING_MESSAGES:
                self.notifications.pop(0)
            self.notifications.append(message)
        return message

    def request(self, method: str, params):
        self.counter += 1
        request_id = self.counter
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + REQUEST_TIMEOUT
        while time.monotonic() < deadline:
            message = self.receive(deadline)
            if message.get("id") == request_id and "method" not in message:
                if "error" in message:
                    raise LspError(str(message["error"]))
                if "result" not in message:
                    raise LspError("JSON-RPC response has no result")
                return message["result"]
        raise LspError("Language server request timed out")

    def diagnostics(self, uri: str):
        deadline = time.monotonic() + REQUEST_TIMEOUT
        while time.monotonic() < deadline:
            for message in reversed(self.notifications):
                params = message.get("params", {})
                if message.get("method") == "textDocument/publishDiagnostics" and params.get("uri") == uri and params.get("version", 1) == 1:
                    if not isinstance(params.get("diagnostics"), list) or any(not isinstance(item, dict) for item in params["diagnostics"]):
                        raise LspError("Invalid diagnostics response")
                    return params["diagnostics"]
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
        self.process.stdin.close()
        self.process.stdout.close()
        self.reader.join(timeout=1)
