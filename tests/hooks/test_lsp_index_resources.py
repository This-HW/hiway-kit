"""Resource contracts run in pytest and stdlib unittest under Python3.9."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/common/tools"))
from lsp_index_policy import IndexUnavailable
from lsp_index_resources import (
    Deadline,
    ResourceGuard,
    linux_snapshot,
    parse_linux_stat,
    snapshot,
    tree_rows,
)


def proc_stat(pid=20, ppid=10, pgid=20, start=123, pages=7):
    fields = ["S", str(ppid), str(pgid)] + ["0"] * 19
    fields[19], fields[21] = str(start), str(pages)
    return (str(pid) + " (space ) and name) " + " ".join(fields)).encode()


class ResourceContracts(unittest.TestCase):
    def child(self):
        p = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(10)"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(lambda: self.finish(p))
        return p

    @staticmethod
    def finish(p):
        if p.poll() is None:
            p.kill()
        p.wait(timeout=3)

    def test_shared_absolute_deadline_and_cleanup_boundary(self):
        now = [10.0]
        d = Deadline(5, clock=lambda: now[0])
        now[0] = 14.0
        with self.assertRaises(IndexUnavailable) as e:
            d.check()
        self.assertEqual(e.exception.reason, "index_deadline")
        self.assertEqual(d.remaining(cleanup=True), 1)
        now[0] = 15.0
        self.assertEqual(d.remaining(cleanup=True), 0)

    def test_invalid_reserve(self):
        for reserve in [-1, 5, 6]:
            with self.subTest(reserve=reserve), self.assertRaises(ValueError):
                Deadline(5, reserve=reserve)
        for value in [float('inf'), float('nan')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                Deadline(value)

    def test_linux_stat_handles_parentheses_and_page_units(self):
        self.assertEqual(parse_linux_stat(proc_stat(), 4096),
                         {"pid": 20, "ppid": 10, "pgid": 20, "start": 123, "rss": 7 * 4096,
                          "state": "S"})

    def test_linux_stat_malformed_and_negative_refused(self):
        for raw in [b"", b"20 () S 1", proc_stat(pages=-1), b"x" * 4097]:
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                parse_linux_stat(raw, 4096)

    def test_fake_proc_includes_owned_processes_and_refuses_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "20").mkdir()
            (root / "20/stat").write_bytes(proc_stat())
            self.assertEqual(linux_snapshot(Deadline(5), root)[0]["pid"], 20)
            (root / "20/stat").write_bytes(proc_stat(pid=21))
            with self.assertRaises(ValueError):
                linux_snapshot(Deadline(5), root)

    def test_tree_keeps_orphaned_same_group_and_descendants(self):
        rows = [{"pid": 10, "ppid": 1, "pgid": 10}, {"pid": 11, "ppid": 10, "pgid": 10},
                {"pid": 12, "ppid": 1, "pgid": 10}, {"pid": 13, "ppid": 11, "pgid": 13},
                {"pid": 14, "ppid": 1, "pgid": 14}]
        self.assertEqual([r["pid"] for r in tree_rows(rows, 10)], [10, 11, 12, 13])

    def test_unsupported_platform_refuses_monitor(self):
        with self.assertRaises(IndexUnavailable) as e:
            snapshot(Deadline(5), "win32")
        self.assertEqual(e.exception.reason, "index_unavailable")

    def test_runtime_monitor_failure_is_normalized(self):
        with (patch("lsp_index_resources.darwin_snapshot", side_effect=RuntimeError("monitor failure")),
              self.assertRaises(IndexUnavailable) as error):
            snapshot(Deadline(5), "darwin")
        self.assertEqual(error.exception.reason, "index_unavailable")

    def test_process_group_lookup_failure_is_normalized(self):
        p = self.child()
        with (patch("lsp_index_resources.os.getpgid", side_effect=ProcessLookupError("gone")),
              self.assertRaises(IndexUnavailable) as error):
            ResourceGuard(p, Deadline(2))
        self.assertEqual(error.exception.reason, "index_unavailable")

    def test_reap_sampler_failure_uses_fixed_reason(self):
        p = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(0.1)"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(lambda: p.wait(timeout=3))
        g = ResourceGuard(p, Deadline(2), sampler=lambda _d: (_ for _ in ()).throw(OSError("sampling failed")))
        p.wait(timeout=2)
        with self.assertRaises(IndexUnavailable) as error:
            g.reap()
        self.assertEqual(error.exception.reason, "index_unavailable")

    def test_kill_error_does_not_overwrite_specific_reason(self):
        p = self.child()
        g = ResourceGuard(p, Deadline(2))
        g.reason = "index_deadline"
        with patch("lsp_index_resources.os.killpg", side_effect=OSError("signal denied")):
            g._signal_group()
        self.assertEqual(g.reason, "index_deadline")

    def test_native_self_sample_available(self):
        if sys.platform not in ("darwin", "linux"):
            self.skipTest("POSIX resource adapter unavailable on this test platform")
        rows = snapshot(Deadline(5))
        row = next(r for r in rows if r["pid"] == os.getpid())
        self.assertGreater(row["rss"], 0)

    def test_memory_guard_kills_owned_child(self):
        p = self.child()
        def sampler(_deadline):
            return [{"pid": p.pid, "ppid": os.getpid(), "pgid": p.pid, "start": 1, "rss": 11}]
        g = ResourceGuard(p, Deadline(2, reserve=0.1), sampler=sampler, rss_limit=10, interval=0.01).start()
        self.assertTrue(g.cancelled.wait(1))
        p.wait(timeout=1)
        self.assertEqual(g.reason, "index_resource_limit")
        with self.assertRaises(IndexUnavailable) as error:
            g.close()
        self.assertEqual(error.exception.reason, "index_resource_limit")

    def test_unknown_monitor_fails_closed(self):
        p = self.child()
        g = ResourceGuard(p, Deadline(2, reserve=0.1), sampler=lambda d: [], interval=0.01).start()
        self.assertTrue(g.cancelled.wait(1))
        p.wait(timeout=1)
        self.assertEqual(g.reason, "index_unavailable")
        with self.assertRaises(IndexUnavailable):
            g.close()

    def test_watchdog_baseexception_cannot_silently_disable_guard(self):
        p = self.child()
        def broken(_deadline):
            raise MemoryError("injected watchdog failure")
        g = ResourceGuard(p, Deadline(2, reserve=0.1), sampler=broken, interval=0.01).start()
        self.assertTrue(g.cancelled.wait(1))
        p.wait(timeout=1)
        self.assertEqual(g.reason, "index_unavailable")
        with self.assertRaises(IndexUnavailable):
            g.close()

    def test_outer_watchdog_baseexception_boundary_is_covered(self):
        p = self.child()
        g = ResourceGuard(p, Deadline(2, reserve=0.1), sampler=lambda _d: [])
        with patch.object(g, "_watch_loop", side_effect=BaseException("outer watchdog failure")), \
                patch.object(g, "_kill") as kill:
            g._watch()
        self.assertEqual(g.reason, "index_unavailable")
        self.assertTrue(g.cancelled.is_set())
        self.assertFalse(g.watch_finished)
        kill.assert_called_once_with()

    def test_close_reports_surviving_group_member_after_leader_exit(self):
        p = self.child()
        samples = [0]

        def sampler(_deadline):
            samples[0] += 1
            if samples[0] <= 2:
                return [{"pid": p.pid + 1, "ppid": 1, "pgid": p.pid, "start": 2, "rss": 1}]
            return []

        g = ResourceGuard(p, Deadline(2, reserve=0.1), sampler=sampler, interval=0.01)
        p.kill()
        p.wait(timeout=1)
        with patch("lsp_index_resources.os.killpg") as kill_group:
            g.start()
            self.assertTrue(g.cancelled.wait(1))
            with self.assertRaises(IndexUnavailable) as error:
                g.close()
        self.assertTrue(kill_group.called)
        self.assertEqual(error.exception.reason, "index_unavailable")

    def test_reap_waits_for_clean_exit_before_collecting_leader(self):
        p = self.child()
        g = ResourceGuard(p, Deadline(3, reserve=0.2), interval=0.01).start()
        p.terminate()
        self.assertNotEqual(g.reap(), None)
        self.assertIsNotNone(p.returncode)
        g.close()

    def test_reap_keyboardinterrupt_kills_child_before_reraising(self):
        p = self.child()
        def sampler(_deadline):
            return [{"pid": p.pid, "ppid": os.getpid(), "pgid": p.pid, "start": 1, "rss": 1}]
        g = ResourceGuard(p, Deadline(3, reserve=0.2), sampler=sampler, interval=0.01).start()
        wait = g.stopped.wait
        def interrupt_main_thread(*args, **kwargs):
            if threading.current_thread() is threading.main_thread():
                raise KeyboardInterrupt
            return wait(*args, **kwargs)
        with (patch.object(g.stopped, "wait", side_effect=interrupt_main_thread),
              self.assertRaises(KeyboardInterrupt)):
            g.reap()
        self.assertTrue(g.cancelled.is_set())
        self.assertIsNotNone(p.poll())
        g.stopped.set()
        g.thread.join(timeout=1)
        self.assertFalse(g.thread.is_alive())

    def test_close_keyboardinterrupt_kills_child_before_reraising(self):
        p = self.child()
        def sampler(_deadline):
            return [{"pid": p.pid, "ppid": os.getpid(), "pgid": p.pid, "start": 1, "rss": 1}]
        g = ResourceGuard(p, Deadline(3, reserve=0.2), sampler=sampler, interval=0.01).start()
        with (patch.object(g.thread, "join", side_effect=KeyboardInterrupt),
              self.assertRaises(KeyboardInterrupt)):
            g.close()
        self.assertTrue(g.cancelled.is_set())
        self.assertIsNotNone(p.poll())
        g.thread.join(timeout=1)
        self.assertFalse(g.thread.is_alive())

    def test_leader_exit_sampling_uses_cleanup_deadline(self):
        now = [0.0]
        p = subprocess.Popen([sys.executable, "-B", "-c", "pass"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(lambda: p.wait(timeout=3))
        deadline = Deadline(5, started=0, reserve=1, clock=lambda: now[0])
        sampled = []

        def sampler(d):
            d.check()
            sampled.append(d)
            return []

        guard = ResourceGuard(p, deadline, sampler=sampler)
        p.wait(timeout=2)
        now[0] = 4.5  # past the work cutoff but within the cleanup reserve
        guard.start()
        guard.thread.join(timeout=1)
        self.assertFalse(guard.thread.is_alive())
        self.assertIsNone(guard.reason)
        self.assertTrue(sampled)
        self.assertTrue(all(d.remaining() > 0 for d in sampled))
        guard.close()

    def test_reap_post_join_sample_rejects_late_group_member(self):
        p = subprocess.Popen([sys.executable, "-B", "-c", "pass"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(lambda: p.wait(timeout=3))
        calls = [0]

        def sampler(_deadline):
            calls[0] += 1
            if calls[0] == 3:
                return [{"pid": p.pid + 1, "ppid": 1, "pgid": p.pid, "start": 2, "rss": 1}]
            return []

        guard = ResourceGuard(p, Deadline(3), sampler=sampler)
        p.wait(timeout=2)
        guard.start()
        guard.thread.join(timeout=1)  # sample 1: monitor exit
        with self.assertRaises(IndexUnavailable):
            guard.reap()  # sample 2 before join; sample 3 after join
        self.assertEqual(calls[0], 3)

    def test_kill_pre_signal_sample_uses_cleanup_deadline(self):
        now = [4.5]
        p = subprocess.Popen([sys.executable, "-B", "-c", "pass"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(lambda: p.wait(timeout=3))
        deadline = Deadline(5, started=0, reserve=1, clock=lambda: now[0])
        calls = [0]

        def sampler(sample_deadline):
            sample_deadline.check()
            calls[0] += 1
            if calls[0] == 1:
                return [{"pid": p.pid + 1, "ppid": 1, "pgid": p.pid, "start": 2, "rss": 1}]
            return []

        guard = ResourceGuard(p, deadline, sampler=sampler)
        p.wait(timeout=2)
        with patch("lsp_index_resources.os.killpg") as kill_group:
            guard._kill()
        kill_group.assert_called_once_with(p.pid, signal.SIGKILL)
        self.assertEqual(calls[0], 2)

    def test_kill_sampling_waits_even_when_watcher_stopped(self):
        p = self.child()
        deadline = Deadline(0.3, reserve=0.1)
        calls = [0]

        def sampler(_deadline):
            calls[0] += 1
            return [{"pid": p.pid + 1, "ppid": 1, "pgid": p.pid, "start": 2, "rss": 1}]

        g = ResourceGuard(p, deadline, sampler=sampler, interval=0.01).start()
        g.reason = "index_deadline"
        with self.assertRaises(IndexUnavailable):
            g.close()
        self.assertLess(calls[0], 100)
        self.assertIsNotNone(p.poll())

    @unittest.skipUnless(hasattr(os, "fork") and hasattr(os, "killpg"), "POSIX fork/process groups required")
    def test_kill_terminates_orphaned_group_child_after_leader_was_reaped(self):
        with tempfile.TemporaryDirectory() as directory:
            child_pid_file = Path(directory) / "child.pid"
            code = ("import os,time,sys; child=os.fork(); "
                    "(open(sys.argv[1],'w').write(str(os.getpid())),time.sleep(30),os._exit(0)) "
                    "if child==0 else (time.sleep(0.4),os._exit(0))")
            p = subprocess.Popen([sys.executable, "-B", "-c", code, str(child_pid_file)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
            guard = ResourceGuard(p, Deadline(4, reserve=0.5), interval=0.01)
            child_pid = None
            try:
                stop = time.monotonic() + 2
                while child_pid is None and time.monotonic() < stop:
                    try:
                        raw_pid = child_pid_file.read_text()
                    except FileNotFoundError:
                        raw_pid = ""
                    if raw_pid.isdecimal():
                        child_pid = int(raw_pid)
                        break
                    time.sleep(0.01)
                self.assertIsNotNone(child_pid, "child PID file was not fully written")
                p.wait(timeout=2)  # reap leader while its orphan remains in the group
                guard._kill()
                stop = time.monotonic() + 2
                while time.monotonic() < stop:
                    rows = snapshot(Deadline(1, reserve=0))
                    child = next((row for row in rows if row["pid"] == child_pid), None)
                    if child is None or child.get("state") in ("Z", 5):
                        break
                    time.sleep(0.01)
                else:
                    self.fail("orphaned group child remained running after the reaped leader was cleaned")
                self.assertTrue(child is None or child.get("state") in ("Z", 5))
            finally:
                if p.returncode is None:
                    p.kill()
                    p.wait(timeout=2)
                if child_pid is not None:
                    rows = snapshot(Deadline(1, reserve=0))
                    if any(row["pid"] == child_pid and row["pgid"] == p.pid
                           and row.get("state") not in ("Z", 5) for row in rows):
                        os.kill(child_pid, signal.SIGKILL)

    @unittest.skipUnless(hasattr(os, "fork") and hasattr(os, "killpg"), "POSIX fork/process groups required")
    def test_orphaned_group_child_is_killed_before_leader_reap(self):
        with tempfile.TemporaryDirectory() as directory:
            child_pid_file = Path(directory) / "child.pid"
            code = ("import os,time,sys; child=os.fork(); "
                    "(open(sys.argv[1],'w').write(str(os.getpid())),time.sleep(30),os._exit(0)) "
                    "if child==0 else (time.sleep(0.3),os._exit(0))")
            p = subprocess.Popen([sys.executable, "-B", "-c", code, str(child_pid_file)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
            g = ResourceGuard(p, Deadline(5, reserve=0.5), interval=0.01).start()
            try:
                self.assertTrue(g.cancelled.wait(3))
                self.assertEqual(g.reason, "index_unavailable")
                with self.assertRaises(IndexUnavailable):
                    g.reap()
                p.wait(timeout=2)
                with self.assertRaises(IndexUnavailable):
                    g.close()
                child_pid = int(child_pid_file.read_text())
                stop = time.monotonic() + 2
                while time.monotonic() < stop:
                    try:
                        os.kill(child_pid, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.01)
                else:
                    self.fail("orphaned process-group child remained after guard shutdown")
            finally:
                if p.returncode is None:
                    p.kill()
                    p.wait(timeout=2)

    def test_work_cutoff_preserves_cleanup_reserve_then_kills(self):
        p = self.child()
        def sampler(_deadline):
            return [{"pid": p.pid, "ppid": os.getpid(), "pgid": p.pid, "start": 1, "rss": 1}]
        g = ResourceGuard(p, Deadline(0.5, reserve=0.3), sampler=sampler, interval=0.01).start()
        self.assertTrue(g.cancelled.wait(0.4))
        self.assertIsNone(p.poll())
        p.wait(timeout=0.6)
        self.assertEqual(g.reason, "index_deadline")
        with self.assertRaises(IndexUnavailable) as error:
            g.close()
        self.assertEqual(error.exception.reason, "index_deadline")


if __name__ == "__main__":
    unittest.main()
