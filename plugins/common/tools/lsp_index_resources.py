"""Absolute indexed-query budget and bounded POSIX child-tree observations.

Sampling is a termination/watchdog policy, not a hard physical RSS limit.
These primitives do not launch a process; the LSP integration owns lifecycle.
"""
from __future__ import annotations

import ctypes
import errno
import math
import os
import signal
import struct
import sys
import threading
import time
from pathlib import Path

from lsp_index_policy import (
    CLEANUP_SECONDS,
    RSS_BYTES,
    SAMPLE_SECONDS,
    IndexUnavailable,
)

MAX_PROCESSES = 20000
PROC_STAT_BYTES = 4096
DARWIN_ZOMBIE_STATE = 5


class Deadline:
    def __init__(self, seconds: float, *, started: float | None = None,
                 reserve: float = CLEANUP_SECONDS, clock=time.monotonic):
        if not math.isfinite(seconds) or not math.isfinite(reserve) or not 0 <= reserve < seconds:
            raise ValueError("Cleanup reserve must be smaller than total budget")
        self.clock = clock
        self.started = clock() if started is None else started
        if not math.isfinite(self.started):
            raise ValueError("Invalid deadline origin")
        self.ends = self.started + seconds
        self.work_ends = self.ends - reserve

    def rebase(self, seconds: float) -> None:
        """Change this shared budget in place without moving its origin."""
        reserve = self.ends - self.work_ends
        if (not math.isfinite(seconds) or seconds <= 0 or reserve < 0 or reserve >= seconds):
            raise IndexUnavailable("index_unavailable", "Classified index budget cannot preserve cleanup reserve")
        self.ends = self.started + seconds
        self.work_ends = self.ends - reserve
        self.check()

    def remaining(self, *, cleanup: bool = False) -> float:
        return max(0.0, (self.ends if cleanup else self.work_ends) - self.clock())

    def check(self, *, cleanup: bool = False) -> None:
        if self.remaining(cleanup=cleanup) <= 0:
            raise IndexUnavailable("index_deadline", "Index work deadline reached; retained progress can be reused")


def parse_linux_stat(raw: bytes, page_size: int) -> dict:
    """proc stat's command can itself contain whitespace and closing parentheses."""
    if len(raw) > PROC_STAT_BYTES:
        raise ValueError("Oversized proc stat")
    left, right = raw.find(b"("), raw.rfind(b")")
    if left <= 0 or right <= left or page_size <= 0:
        raise ValueError("Invalid proc stat")
    fields = raw[right + 1:].split()
    if len(fields) < 22 or len(fields[0]) != 1:
        raise ValueError("Truncated proc stat")
    pid, ppid, pgid, start, rss = (int(raw[:left].strip()), int(fields[1]),
                                   int(fields[2]), int(fields[19]), int(fields[21]))
    if min(pid, page_size) <= 0 or min(ppid, pgid, start, rss) < 0:
        raise ValueError("Invalid proc counters")
    return {"pid": pid, "ppid": ppid, "pgid": pgid, "start": start, "rss": rss * page_size,
            "state": fields[0].decode("ascii", errors="strict")}


def linux_snapshot(deadline: Deadline, root: Path = Path("/proc")) -> list[dict]:
    rows = []
    page_size = os.sysconf("SC_PAGE_SIZE")
    with os.scandir(root) as entries:
        count = 0
        for entry in entries:
            deadline.check()
            if not entry.name.isdecimal():
                continue
            count += 1
            if count > MAX_PROCESSES:
                raise ValueError("Process snapshot limit")
            try:
                # Unrelated other-user processes need not be readable. All
                # members of this unprivileged server tree share the caller uid.
                if entry.stat(follow_symlinks=False).st_uid != os.getuid():
                    continue
                with open(Path(entry.path) / "stat", "rb") as stream:
                    row = parse_linux_stat(stream.read(PROC_STAT_BYTES + 1), page_size)
                if row["pid"] != int(entry.name):
                    raise ValueError("Process identity mismatch")
                rows.append(row)
            except OSError as exc:
                if exc.errno not in (errno.ENOENT, errno.ESRCH):
                    raise
    return rows


def darwin_snapshot(deadline: Deadline) -> list[dict]:
    lib = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    lib.proc_listallpids.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
    count = lib.proc_listallpids(None, 0)
    if not 0 < count < MAX_PROCESSES:
        raise ValueError("Process snapshot count unavailable")
    ids = (ctypes.c_int * min(count + 256, MAX_PROCESSES))()
    seen = lib.proc_listallpids(ids, ctypes.sizeof(ids))
    if not 0 < seen < len(ids):
        raise ValueError("Process snapshot changed beyond buffer")
    rows = []
    for pid in list(ids)[:seen]:
        deadline.check()
        if pid <= 0:
            continue
        bsd = ctypes.create_string_buffer(136)
        if lib.proc_pidinfo(pid, 3, 0, bsd, 136) != 136:
            # Processes disappear during enumeration; if it is the observed
            # root, ResourceGuard separately requires its record while live.
            continue
        if struct.unpack_from("I", bsd.raw, 20)[0] != os.getuid():
            continue
        task = ctypes.create_string_buffer(96)
        rss = None
        if lib.proc_pidinfo(pid, 4, 0, task, 96) == 96:
            rss = struct.unpack_from("Q", task.raw, 8)[0]
        rows.append({"pid": pid, "ppid": struct.unpack_from("I", bsd.raw, 16)[0],
                     "pgid": struct.unpack_from("I", bsd.raw, 100)[0],
                     "start": struct.unpack_from("QQ", bsd.raw, 120), "rss": rss,
                     "state": struct.unpack_from("I", bsd.raw, 4)[0]})
    return rows


def snapshot(deadline: Deadline, platform: str | None = None) -> list[dict]:
    platform = sys.platform if platform is None else platform
    try:
        if platform == "darwin":
            return darwin_snapshot(deadline)
        if platform.startswith("linux"):
            return linux_snapshot(deadline)
        raise ValueError("Unsupported index monitoring platform")
    except IndexUnavailable:
        raise
    except (OSError, ValueError, AttributeError, struct.error, RuntimeError, RecursionError) as exc:
        raise IndexUnavailable("index_unavailable", "Child-process resource monitoring is unavailable") from exc


def tree_rows(rows: list[dict], pid: int) -> list[dict]:
    selected = {pid}
    while True:
        expanded = selected | {r["pid"] for r in rows if r["ppid"] in selected or r["pgid"] == pid}
        if expanded == selected:
            break
        selected = expanded
    return [r for r in rows if r["pid"] in selected]


class ResourceGuard:
    """Cancel at the work cutoff; kill the owned process group at the hard stop.

    Caller must use start_new_session=True for its child, never its own group.
    Memory/cache failures kill immediately. Cooperative shutdown and voluntary
    exit waiting use only work time; reserve is for forced kill and verified
    reaping. The watchdog kills at the hard stop if the caller cannot react.
    """

    def __init__(self, process, deadline: Deadline, *, sampler=snapshot,
                 rss_limit: int = RSS_BYTES, interval: float = SAMPLE_SECONDS, disk_check=None):
        if type(rss_limit) is not int or rss_limit <= 0 or not math.isfinite(interval) or interval <= 0:
            raise ValueError("Invalid resource sampling policy")
        try:
            process_group = os.getpgid(process.pid)
        except (OSError, RuntimeError, RecursionError) as exc:
            raise IndexUnavailable("index_unavailable", "Cannot verify indexed child process group") from exc
        if process.pid == os.getpid() or process_group != process.pid:
            raise IndexUnavailable("index_unavailable", "Indexed child must own a separate process group")
        self.process, self.deadline = process, deadline
        self.sampler, self.rss_limit, self.interval, self.disk_check = sampler, rss_limit, interval, disk_check
        self._cleanup_compromised = False
        self._verified_once = False
        self._poll_lock = threading.Lock()
        self.reason = None
        self.peak_rss = 0
        self.root_start = None
        self._unknown_rss_exemptions = 0
        self.watch_finished = False
        self.cancelled = threading.Event()
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._watch, daemon=True)

    @property
    def cleanup_verified(self):
        return self._verified_once and not self._cleanup_compromised

    def _poll(self):
        # Popen.poll uses a nonblocking internal waitpid lock and can return
        # None while another observer is already reaping an exited leader.
        # Serialize the guard's two observers so None still means running.
        with self._poll_lock:
            return self.process.poll()

    def _sample(self, deadline):
        try:
            return self.sampler(deadline)
        except (KeyboardInterrupt, SystemExit):
            raise
        except IndexUnavailable:
            raise
        except BaseException as exc:
            raise IndexUnavailable("index_unavailable", "Child-process resource monitoring is unavailable") from exc

    def _signal_group(self):
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            self.reason = self.reason or "index_unavailable"

    def _kill(self, *, group_member_observed=False):
        # A waitable leader anchors its group. If the leader was already
        # reaped, signal only after a fresh inventory proves a same-pgid member
        # still exists, so the numeric group id cannot have been recycled.
        if self.process.returncode is not None and group_member_observed:
            self._cleanup_compromised = True
        if self.process.returncode is not None and not group_member_observed:
            try:
                rows = self._sample(self._cleanup_deadline())
            except (KeyboardInterrupt, SystemExit):
                self.reason = self.reason or "index_unavailable"
                raise
            except IndexUnavailable as exc:
                self.reason = self.reason or exc.reason
                return
            if not any(row["pgid"] == self.process.pid and row["pid"] != self.process.pid for row in rows):
                return
            self._cleanup_compromised = True
        self._signal_group()
        while self.deadline.remaining(cleanup=True) > 0:
            cleanup = self._cleanup_deadline()
            try:
                rows = self._sample(cleanup)
            except (KeyboardInterrupt, SystemExit):
                self.reason = self.reason or "index_unavailable"
                raise
            except IndexUnavailable as exc:
                self.reason = self.reason or exc.reason
                return
            children = [row for row in rows
                        if row["pgid"] == self.process.pid and row["pid"] != self.process.pid]
            # Reap only after a fresh snapshot confirms no other process can
            # be affected by this numeric process-group id.
            if not children and self._poll() is not None:
                return
            time.sleep(min(self.interval, self.deadline.remaining(cleanup=True)))

    def _cleanup_deadline(self):
        now = self.deadline.clock()
        return Deadline(max(1e-9, self.deadline.ends - now), started=now, reserve=0,
                        clock=self.deadline.clock)

    def _watch(self):
        try:
            self._watch_loop()
        except BaseException as exc:
            # The watchdog is a safety boundary. Even MemoryError and
            # unexpected runtime failures must not silently disable it.
            self.reason = self.reason or "index_unavailable"
            try:
                self._kill()
            finally:
                self.cancelled.set()
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
        else:
            self.watch_finished = True

    def _watch_loop(self):
        while not self.stopped.is_set():
            if self.process.returncode is not None:
                try:
                    rows = self._sample(self._cleanup_deadline())
                    if any(r["pgid"] == self.process.pid and r["pid"] != self.process.pid for r in rows):
                        self._cleanup_compromised = True
                        self.reason = self.reason or "index_unavailable"
                        self._kill(group_member_observed=True)
                        self.cancelled.set()
                except (KeyboardInterrupt, SystemExit):
                    self.reason = self.reason or "index_unavailable"
                    self._kill()
                    self.cancelled.set()
                    raise
                except IndexUnavailable as exc:
                    self.reason = self.reason or exc.reason
                    self.cancelled.set()
                return
            if self.deadline.remaining(cleanup=True) <= 0:
                self.reason = self.reason or "index_deadline"
                self._kill()
                self.cancelled.set()
                return
            if self.deadline.remaining() <= 0:
                self.reason = self.reason or "index_deadline"
                self.cancelled.set()
            if not self.cancelled.is_set():
                try:
                    observed = self._sample(self.deadline)
                    roots = [r for r in observed if r["pid"] == self.process.pid]
                    if not roots:
                        children = [r for r in observed
                                    if r["pid"] != self.process.pid and r["pgid"] == self.process.pid]
                        if children:
                            self.reason = self.reason or "index_unavailable"
                            self._kill()
                            self.cancelled.set()
                            self.stopped.wait(min(self.interval, self.deadline.remaining(cleanup=True)))
                            continue
                        if self._poll() is not None:
                            return
                        raise ValueError("Live child is missing from resource snapshot")
                    root = roots[0]
                    if root.get("state") in ("Z", DARWIN_ZOMBIE_STATE):
                        children = [r for r in observed
                                    if r["pid"] != self.process.pid and r["pgid"] == self.process.pid]
                        if children:
                            self.reason = self.reason or "index_unavailable"
                            self._kill()
                            self.cancelled.set()
                        else:
                            # The leader is the only remaining group member, so
                            # reaping it cannot redirect a later group signal.
                            self._poll()
                            return
                        self.stopped.wait(min(self.interval, self.deadline.remaining(cleanup=True)))
                        continue
                    current_start = root["start"]
                    if self.root_start is not None and self.root_start != current_start:
                        raise ValueError("Child PID identity changed")
                    self.root_start = current_start
                    members = tree_rows(observed, self.process.pid)
                    unknown = [r for r in members if r["rss"] is None or r["rss"] < 0]
                    if unknown:
                        # libproc reads BSD state and task RSS separately. A
                        # process may exit between them; confirm that transition
                        # instead of rejecting a normal shutdown as unknown RSS.
                        confirmed = {r["pid"]: r for r in self._sample(self.deadline)}
                        if all(r["pid"] not in confirmed or
                               (confirmed[r["pid"]].get("state") in ("Z", DARWIN_ZOMBIE_STATE)
                                and confirmed[r["pid"]]["start"] == r["start"]) for r in unknown):
                            self._unknown_rss_exemptions += 1
                            if self._unknown_rss_exemptions > 2:
                                raise ValueError("Repeated unknown RSS exit transitions")
                            self.stopped.wait(min(self.interval, self.deadline.remaining(cleanup=True)))
                            continue
                        raise ValueError("Child RSS is unknown")
                    self._unknown_rss_exemptions = 0
                    rss = sum(r["rss"] for r in members)
                    self.peak_rss = max(self.peak_rss, rss)
                    if rss > self.rss_limit:
                        raise IndexUnavailable("index_resource_limit", "Indexed child exceeded the sampled RSS policy")
                    if self.disk_check is not None:
                        self.disk_check()
                except IndexUnavailable as exc:
                    self.reason = exc.reason
                    if exc.reason != "index_deadline":
                        self._kill()
                        self.cancelled.set()
                        return
                    self.cancelled.set()
                except (KeyboardInterrupt, SystemExit):
                    self.reason = self.reason or "index_unavailable"
                    self._kill()
                    self.cancelled.set()
                    raise
                except BaseException:
                    self.reason = self.reason or "index_unavailable"
                    self._kill()
                    self.cancelled.set()
                    return
            self.stopped.wait(min(self.interval, self.deadline.remaining(cleanup=True)))

    def start(self):
        self.thread.start()
        return self

    def reap(self, *, graceful=False):
        try:
            return self._reap(graceful=graceful)
        except (KeyboardInterrupt, SystemExit):
            self.reason = self.reason or "index_unavailable"
            try:
                self._kill()
            finally:
                self.cancelled.set()
            raise

    def _reap(self, *, graceful=False):
        """Wait for graceful exit, then safely reap only after group children are gone.

        Call this instead of Popen.wait(): it keeps the leader waitable while
        an orphaned same-group child is identified and killed, so no signal is
        ever sent to a reused process-group id.
        """
        while self.deadline.remaining(cleanup=True) > 0:
            if graceful and (self.deadline.remaining() <= 0 or self.cancelled.is_set()):
                self.reason = self.reason or "index_deadline"
                self._kill()
                graceful = False
            if self.process.returncode is not None:
                try:
                    rows = self._sample(self._cleanup_deadline())
                except IndexUnavailable as exc:
                    self.reason = self.reason or exc.reason
                    self._kill()
                    raise IndexUnavailable(self.reason, "Cannot verify reaped process group") from exc
                children = [row for row in rows
                            if row["pgid"] == self.process.pid and row["pid"] != self.process.pid]
                if children:
                    self._cleanup_compromised = True
                    self.reason = self.reason or "index_unavailable"
                    self._kill(group_member_observed=True)
                    try:
                        rows = self._sample(self._cleanup_deadline())
                    except IndexUnavailable as exc:
                        self.reason = self.reason or exc.reason
                        raise IndexUnavailable(self.reason, "Cannot verify cleaned process group") from exc
                    if any(row["pgid"] == self.process.pid and row["pid"] != self.process.pid for row in rows):
                        self._cleanup_compromised = True
                        raise IndexUnavailable(self.reason, "Leader was reaped before its process group was empty")
                break
            try:
                rows = self._sample(self._cleanup_deadline())
            except IndexUnavailable as exc:
                self.reason = self.reason or exc.reason
                self._kill()
                raise IndexUnavailable(self.reason, "Cannot verify indexed process exit") from exc
            roots = [row for row in rows if row["pid"] == self.process.pid]
            children = [row for row in rows
                        if row["pgid"] == self.process.pid and row["pid"] != self.process.pid]
            root_exited = not roots or roots[0].get("state") in ("Z", DARWIN_ZOMBIE_STATE)
            if root_exited and children:
                if self.process.returncode is not None:
                    # Another observer reaped the leader during this snapshot.
                    # Re-enter the reaped-leader branch for fresh group evidence.
                    continue
                self.reason = self.reason or "index_unavailable"
                self._kill(group_member_observed=True)
            elif root_exited and not children:
                self._poll()
                if self.process.returncode is not None:
                    break
            self.stopped.wait(min(self.interval, self.deadline.remaining(cleanup=not graceful)))
        else:
            self.reason = self.reason or "index_deadline"
            self._kill()
            raise IndexUnavailable(self.reason, "Indexed process did not exit within its cleanup budget")
        self.stopped.set()
        self.thread.join(timeout=self.deadline.remaining(cleanup=True))
        if self.thread.is_alive():
            self.reason = self.reason or "index_unavailable"
            raise IndexUnavailable(self.reason, "Resource monitor did not finish after child exit")
        try:
            rows = self._sample(self._cleanup_deadline())
        except IndexUnavailable as exc:
            self.reason = self.reason or exc.reason
            self._kill()
            raise IndexUnavailable(self.reason, "Cannot verify post-reap process cleanup") from exc
        if any(row["pgid"] == self.process.pid and row["pid"] != self.process.pid for row in rows):
            self._cleanup_compromised = True
            self.reason = self.reason or "index_unavailable"
            raise IndexUnavailable(self.reason, "Indexed process group left child processes behind")
        self._verified_once = True
        if self._cleanup_compromised:
            raise IndexUnavailable("index_unavailable", "Earlier reaping left an unverified process group")
        if self.reason is not None:
            raise IndexUnavailable(self.reason, "Indexed child resource guard observed an incomplete run")
        return self.process.returncode

    def close(self):
        try:
            return self._close()
        except (KeyboardInterrupt, SystemExit):
            self.reason = self.reason or "index_unavailable"
            try:
                self._kill()
            finally:
                self.cancelled.set()
            raise

    def _close(self):
        self.stopped.set()
        self.thread.join(timeout=self.deadline.remaining(cleanup=True))
        if self.thread.is_alive():
            self.reason = "index_unavailable"
            self._kill()
            self.cancelled.set()
            raise IndexUnavailable(self.reason, "Resource monitoring did not terminate")
        if not self.watch_finished and self.reason is None:
            self.reason = "index_unavailable"
            raise IndexUnavailable(self.reason, "Resource monitor ended without a result")
        if self.reason is not None:
            self._kill()
            self.cancelled.set()
            raise IndexUnavailable(self.reason, "Indexed child resource guard observed an incomplete run")
        if self.reason is None:
            try:
                rows = self._sample(self._cleanup_deadline())
            except IndexUnavailable as exc:
                self.reason = self.reason or exc.reason
                self._kill()
                self.cancelled.set()
                raise IndexUnavailable(self.reason, "Cannot verify indexed child cleanup") from exc
            roots = [row for row in rows if row["pid"] == self.process.pid]
            survivors = [row for row in rows
                         if row["pgid"] == self.process.pid and row["pid"] != self.process.pid]
            if survivors:
                if self.process.returncode is not None:
                    self._cleanup_compromised = True
                self.reason = "index_unavailable"
                self._kill(group_member_observed=True)
                self.cancelled.set()
                raise IndexUnavailable("index_unavailable", "Indexed process group left child processes behind")
            if self.process.returncode is None and roots and roots[0].get("state") not in ("Z", DARWIN_ZOMBIE_STATE):
                self.reason = "index_unavailable"
                self._kill()
                self.cancelled.set()
                raise IndexUnavailable(self.reason, "Resource guard closed while the child was still running")
            if self.process.returncode is None:
                # No group members remain besides a verified zombie leader (or
                # the sampler no longer reports it), so it is now safe to reap.
                self._poll()
                if self.process.returncode is None:
                    self.reason = "index_unavailable"
                    self._kill()
                    raise IndexUnavailable(self.reason, "Indexed child did not exit")
        if self.reason is not None:
            self._kill()
            self.cancelled.set()
            raise IndexUnavailable(self.reason, "Indexed child resource guard observed an incomplete run")
