"""Bounded, synchronous subprocess capture for POSIX command-line tools."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from contextlib import suppress
from pathlib import Path

from intel_runtime import child_environment

READ_CHUNK_BYTES = 64 * 1024


class ProcessBudget:
    """Share a received-byte limit and an absolute deadline across invocations.

    Both output streams count toward the same budget. No output is spooled to
    disk, and at most the remaining budget plus one overflow byte is read.
    Descendants must stay in the new process group; deliberate session escape
    is outside this runner's containment contract.
    """

    def __init__(self, timeout: float, max_output_bytes: int):
        if timeout <= 0 or max_output_bytes < 0:
            raise ValueError("Invalid subprocess budget")
        self.deadline = time.monotonic() + timeout
        self.remaining_bytes = max_output_bytes
        self.max_output_bytes = max_output_bytes

    def run(self, command: list[str], *, cwd: Path | None = None,
            timeout: float | None = None) -> subprocess.CompletedProcess:
        # selectors cannot monitor anonymous subprocess pipes on Windows.
        # Fail before launching rather than provide an unbounded fallback.
        if os.name != "posix":
            raise OSError("Bounded subprocess capture requires POSIX pipes")
        deadline = self.deadline
        if timeout is not None:
            deadline = min(deadline, time.monotonic() + timeout)
        time_limit = max(0.0, deadline - time.monotonic())

        def remaining_time() -> float:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, time_limit)
            return remaining

        remaining_time()
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True, env=child_environment())
        stdout, stderr = bytearray(), bytearray()
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, stdout)
                selector.register(process.stderr, selectors.EVENT_READ, stderr)
                while selector.get_map():
                    for key, _ in selector.select(remaining_time()):
                        remaining_time()
                        chunk = os.read(key.fd, min(READ_CHUNK_BYTES, self.remaining_bytes + 1))
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        if len(chunk) > self.remaining_bytes:
                            raise ValueError(f"Process output exceeded {self.max_output_bytes} bytes; narrow the paths or pattern")
                        self.remaining_bytes -= len(chunk)
                        key.data.extend(chunk)
                returncode = process.wait(timeout=remaining_time())
            return subprocess.CompletedProcess(command, returncode, bytes(stdout), bytes(stderr))
        finally:
            # Kill the group even if its leader exited: children can still hold
            # a pipe open, or close both pipes and outlive a successful command.
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            try:
                process.wait(timeout=1)
            finally:
                process.stdout.close()
                process.stderr.close()
