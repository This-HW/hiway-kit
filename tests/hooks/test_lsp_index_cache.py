"""Cache boundary and lifecycle contracts, compatible with stdlib unittest."""
from __future__ import annotations

import errno
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/common/tools"))
import lsp_index_cache
from lsp_index_cache import Cache, key_for
from lsp_index_policy import IndexUnavailable
from lsp_index_resources import Deadline, ResourceGuard


class KeyContracts(unittest.TestCase):
    def key(self, environment=None, **changes):
        args = {'cdb': b'[]', 'source_identities': {'cdb': '/project/compile_commands.json', 'sources': ['/project/a.c']},
                'root_identity': ['/project', 1, 2], 'engine_identity': ['/tool/clangd', 'v21'],
                'compiler_identities': ['/tool/clang'], 'sdk_identity': '/sdk', 'config_inventory': [], 'environment': environment or {}}
        args.update(changes)
        return key_for(**args)

    def test_session_noise_does_not_fragment_key(self):
        a = {'PATH': '/one', 'TMPDIR': '/session1', 'CONDA_PREFIX': '/env1', 'SHELL': '/bin/sh', 'LANG': 'C'}
        b = {'PATH': '/two', 'TMPDIR': '/session2', 'CONDA_PREFIX': '/env2', 'SHELL': '/bin/zsh', 'LANG': 'ko_KR.UTF-8'}
        self.assertEqual(self.key(a), self.key(b))

    def test_semantic_environment_changes_key_and_absence_differs_from_empty(self):
        for name in ['CPATH', 'SDKROOT', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'DEVELOPER_DIR']:
            with self.subTest(name=name):
                self.assertNotEqual(self.key({name: '/one'}), self.key({name: '/two'}))
                self.assertNotEqual(self.key(), self.key({name: ''}))

    def test_inputs_invalidate_without_echoing_values(self):
        base = self.key({'CPATH': 'private-path'})
        for changes in [{'cdb': b'[{}]'}, {'root_identity': ['/other']}, {'engine_identity': ['v22']},
                        {'source_identities': {'cdb': '/project/other/compile_commands.json', 'sources': ['/project/a.c']}},
                        {'compiler_identities': ['other-compiler']}, {'sdk_identity': 'other-sdk'}]:
            with self.subTest(changes=changes):
                self.assertNotEqual(base, self.key({'CPATH': 'private-path'}, **changes))
        self.assertEqual(len(base), 64)
        self.assertNotIn('private-path', base)


class CacheContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.workspace = self.base / 'workspace'
        self.plugin = self.base / 'plugin'
        self.workspace.mkdir()
        self.plugin.mkdir()
        self.root = self.base / 'cache'

    def cache(self):
        c = Cache(self.root, self.workspace, self.plugin)
        self.addCleanup(c.close)
        return c

    def test_zero_shard_attempt_consumed_before_work_and_reopen(self):
        c = self.cache()
        with c.lease('a' * 64, Deadline(30)) as key:
            first = key.begin_attempt()
            self.assertEqual((first['classification'], first['total_seconds']), ('new', 30))
            key.write_cdb(b'[]')
            self.assertEqual((key.path / 'compile_commands.json').read_bytes(), b'[]')
        with c.lease('a' * 64, Deadline(5)) as key:
            second = key.begin_attempt()
            self.assertEqual((second['classification'], second['total_seconds']), ('existing', 5))
            self.assertEqual(second['persisted_shards_before'], 0)

    def test_shards_without_metadata_are_conservatively_existing(self):
        c = self.cache()
        with c.lease('b' * 64, Deadline(30)) as key:
            (key.path / 'native.idx').write_bytes(b'prior native bytes')
            self.assertEqual(key.begin_attempt()['classification'], 'existing')

    def test_malformed_metadata_is_not_treated_as_first_use(self):
        c = self.cache()
        for i, value in enumerate([b'{}', b'null', b'[1,2,3]', b'{"schema":true,"attempted":false,"last_used_ns":0}',
                                   b'{"schema":1,"schema":1,"attempted":false,"last_used_ns":0}']):
            with c.lease(str(i) * 64, Deadline(30)) as key:
                (key.path / 'meta.json').write_bytes(value)
                with self.assertRaises(IndexUnavailable):
                    key.begin_attempt()
                (key.path / 'meta.json').unlink()

    def test_deep_metadata_and_atomic_write_errors_use_fixed_reason(self):
        c = self.cache()
        with c.lease('6' * 64, Deadline(10)) as key:
            nested = b'[' * 400 + b']' * 400
            (key.path / 'meta.json').write_bytes(nested)
            with self.assertRaises(IndexUnavailable) as error:
                key.begin_attempt()
            self.assertEqual(error.exception.reason, 'index_unavailable')
            (key.path / 'meta.json').unlink()
            with (patch.object(lsp_index_cache.os, 'fsync', side_effect=OSError('ENOSPC')),
                  self.assertRaises(IndexUnavailable) as error):
                key.write_cdb(b'[]')
            self.assertEqual(error.exception.reason, 'index_unavailable')

    def test_key_path_traversal_refused_and_workspace_unchanged(self):
        c = self.cache()
        for key in ['../escape', '/escape', '.', 'a' * 63, 'A' * 64]:
            with self.subTest(key=key), self.assertRaises(ValueError), c.lease(key, Deadline(5)):
                self.fail('invalid key yielded')
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_workspace_and_plugin_cache_locations_refused(self):
        for location in [self.workspace / 'cache', self.plugin / 'cache']:
            with self.subTest(location=location), self.assertRaises(IndexUnavailable):
                Cache(location, self.workspace, self.plugin)

    def test_root_symlink_and_other_writable_root_refused(self):
        target = self.base / 'target'
        target.mkdir(mode=0o700)
        self.root.symlink_to(target, target_is_directory=True)
        with self.assertRaises(IndexUnavailable):
            self.cache()
        self.root.unlink()
        self.root.mkdir(mode=0o777)
        self.root.chmod(0o777)
        with self.assertRaises(IndexUnavailable):
            self.cache()

    def test_filesystem_errors_are_normalized_to_fixed_reason(self):
        blocked = self.base / 'not-a-directory'
        blocked.write_text('x')
        with self.assertRaises(IndexUnavailable) as error:
            Cache(blocked / 'cache', self.workspace, self.plugin)
        self.assertEqual(error.exception.reason, 'index_unavailable')

    def test_entries_swap_and_key_symlink_do_not_write_through(self):
        c = self.cache()
        sentinel = self.workspace / 'compile_commands.json'
        sentinel.write_bytes(b'original')
        with c.lease('c' * 64, Deadline(30)) as key:
            path = key.path
            path.rename(path.with_name('saved-key'))
            path.symlink_to(self.workspace, target_is_directory=True)
            with self.assertRaises(IndexUnavailable):
                key.write_cdb(b'overwrite')
            path.unlink()
            path.with_name('saved-key').rename(path)
        entries = self.root / 'entries'
        entries.rename(self.root / 'saved-entries')
        entries.symlink_to(self.workspace, target_is_directory=True)
        with self.assertRaises(IndexUnavailable):
            c.validate()
        self.assertEqual(sentinel.read_bytes(), b'original')
        entries.unlink()
        (self.root / 'saved-entries').rename(entries)

    def test_symlink_or_hardlink_file_inside_cache_refused(self):
        c = self.cache()
        outside = self.workspace / 'outside'
        outside.write_bytes(b'keep')
        with c.lease('d' * 64, Deadline(30)) as key:
            (key.path / 'link').symlink_to(outside)
            with self.assertRaises(IndexUnavailable):
                key.usage()
            (key.path / 'link').unlink()
            os.link(outside, key.path / 'hardlink')
            with self.assertRaises(IndexUnavailable):
                key.usage()
            (key.path / 'hardlink').unlink()
        self.assertEqual(outside.read_bytes(), b'keep')

    def test_discard_preserves_attempt_marker_and_failure_reason(self):
        c = self.cache()
        with c.lease('e' * 64, Deadline(30)) as key:
            key.begin_attempt()
            key.discard('index_resource_limit')
            self.assertTrue((key.path / 'meta.json').exists())
            self.assertEqual((key.path / 'failure.json').read_bytes(), b'{"reason": "index_resource_limit"}')
            self.assertFalse((key.path / 'compile_commands.json').exists())
        with c.lease('e' * 64, Deadline(30)) as key:
            attempt = key.begin_attempt()
            self.assertEqual((attempt['classification'], attempt['total_seconds']), ('existing', 5))

    def test_discard_uses_cleanup_reserve_after_work_expired(self):
        c = self.cache()
        now = [10.0]
        deadline = Deadline(30, clock=lambda: now[0])
        with c.lease('e' * 64, deadline) as key:
            key.begin_attempt()
            now[0] = 39.0
            with self.assertRaises(IndexUnavailable):
                key.usage()
            self.assertEqual(key.usage(cleanup=True)["persisted_shards"], 0)
            key.discard()
        self.assertTrue((self.root / 'entries' / ('e' * 64) / 'meta.json').exists())

    def test_discard_clears_native_data_before_metadata_write_can_fail_enospc(self):
        c = self.cache()
        with c.lease('2' * 64, Deadline(30)) as key:
            key.begin_attempt()
            payload = key.path / 'native.idx'
            payload.write_bytes(b'x' * 1024 * 1024)
            original = lsp_index_cache._atomic

            def full_until_payload_is_removed(fd, name, raw):
                if name == 'meta.json' and payload.exists():
                    raise OSError(errno.ENOSPC, 'disk full')
                return original(fd, name, raw)

            with patch.object(lsp_index_cache, '_atomic', side_effect=full_until_payload_is_removed):
                key.discard('index_resource_limit')
            self.assertFalse(payload.exists())
            self.assertTrue((key.path / 'meta.json').exists())
            self.assertEqual((key.path / 'failure.json').read_bytes(), b'{"reason": "index_resource_limit"}')

    def test_begin_attempt_rebases_the_callers_shared_deadline_in_place(self):
        c = self.cache()
        with c.lease('c' * 64, Deadline(30)) as key:
            key.begin_attempt()
        child = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(10)'],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(lambda: child.wait(timeout=3))
        self.addCleanup(lambda: child.kill() if child.poll() is None else None)
        now = [0.0]
        deadline = Deadline(30, started=0, clock=lambda: now[0])
        guard = ResourceGuard(child, deadline, sampler=lambda _d: [])
        with c.lease('c' * 64, deadline) as key:
            result = key.begin_attempt()
        self.assertEqual(result['classification'], 'existing')
        self.assertIs(guard.deadline, deadline)
        self.assertEqual(deadline.ends, 5.0)
        now[0] = 4.5
        self.assertEqual(deadline.remaining(), 0)
        self.assertEqual(deadline.remaining(cleanup=True), 0.5)

    def test_begin_attempt_maps_unusable_classified_reserve_to_fixed_reason(self):
        c = self.cache()
        with c.lease('d' * 64, Deadline(30)) as key:
            key.begin_attempt()
        with c.lease('d' * 64, Deadline(30, reserve=5)) as key:
            with self.assertRaises(IndexUnavailable) as error:
                key.begin_attempt()
            self.assertEqual(error.exception.reason, 'index_unavailable')

    def test_lru_removes_oldest_and_preserves_excluded_key(self):
        c = self.cache()
        for char in ['a', 'b', 'c']:
            with c.lease(char * 64, Deadline(30)) as key:
                key.begin_attempt()
        with c.lease('c' * 64, Deadline(30)) as key:
            c.prune(key.deadline, exclude='c' * 64, max_keys=2)
        self.assertEqual(sorted(p.name for p in (self.root / 'entries').iterdir()), ['b' * 64, 'c' * 64])
        self.assertFalse((self.root / ('key-' + 'a' * 64 + '.lock')).exists())

    def test_lru_enforces_sampled_byte_target(self):
        c = self.cache()
        for char in ['d', 'e']:
            with c.lease(char * 64, Deadline(10)) as key:
                key.begin_attempt()
                (key.path / 'payload').write_bytes(b'x' * 8)
        with c.lease('e' * 64, Deadline(10)) as key:
            c.prune(key.deadline, exclude='e' * 64, max_keys=16, max_bytes=100)
        remaining = [p.name for p in (self.root / 'entries').iterdir() if len(p.name) == 64]
        self.assertEqual(remaining, ['e' * 64])

    def test_prune_preserves_index_deadline_instead_of_reclassifying_key(self):
        c = self.cache()
        now = [0.0]
        deadline = Deadline(30, started=0, clock=lambda: now[0])
        with c.lease('f' * 64, deadline) as key:
            key.begin_attempt()
            now[0] = 29.5
            with self.assertRaises(IndexUnavailable) as error:
                c.prune(key.deadline, exclude=key.key)
            self.assertEqual(error.exception.reason, 'index_deadline')

    def test_cleanup_without_owned_global_lease_is_refused(self):
        c = self.cache()
        with self.assertRaises(IndexUnavailable):
            c.prune(Deadline(5))

    def test_anchor_cannot_close_while_lease_is_active(self):
        c = self.cache()
        with c.lease('4' * 64, Deadline(5)) as key:
            with self.assertRaises(IndexUnavailable):
                c.close()
            key.write_cdb(b'[]')
            self.assertEqual((key.path / 'compile_commands.json').read_bytes(), b'[]')

    def test_stray_store_entry_is_removed_without_blocking_other_keys(self):
        c = self.cache()
        unknown = self.root / 'entries/.DS_Store'
        unknown.write_bytes(b'finder metadata')
        with c.lease('a' * 64, Deadline(5)) as key:
            self.assertEqual(key.begin_attempt()['classification'], 'new')
        self.assertFalse(unknown.exists())

    def test_live_scan_skips_entries_removed_or_replaced_during_iteration(self):
        c = self.cache()
        with c.lease('7' * 64, Deadline(5)) as key:
            shard = key.path / 'racing.idx'
            shard.write_bytes(b'first')
            folder = key.path / 'racing-dir'
            folder.mkdir()
            original_file = lsp_index_cache._file
            original_directory = lsp_index_cache._directory
            changed = {'file': False, 'directory': False}

            def race_file(parent, name, *args, **kwargs):
                if name == 'racing.idx' and not changed['file']:
                    changed['file'] = True
                    shard.unlink()
                return original_file(parent, name, *args, **kwargs)

            def race_directory(parent, name, *args, **kwargs):
                if name == 'racing-dir' and not changed['directory']:
                    changed['directory'] = True
                    folder.rmdir()
                return original_directory(parent, name, *args, **kwargs)

            with patch.object(lsp_index_cache, '_file', side_effect=race_file), \
                    patch.object(lsp_index_cache, '_directory', side_effect=race_directory):
                self.assertGreaterEqual(key.usage(active=True)['bytes'], 0)
            self.assertTrue(changed['file'] and changed['directory'])

    def test_umask_002_native_layout_and_bad_unrelated_key_do_not_block(self):
        c = self.cache()
        previous = os.umask(0o002)
        try:
            with c.lease('8' * 64, Deadline(10)) as key:
                shard = key.path / '.cache/clangd/index/native.idx'
                shard.parent.mkdir(parents=True, mode=0o777)
                shard.write_bytes(b'clangd shard')
                self.assertEqual(os.stat(shard).st_mode & 0o777, 0o664)
                self.assertEqual(os.stat(shard.parent).st_mode & 0o777, 0o775)
                self.assertEqual(key.usage()['persisted_shards'], 1)
            bad = self.root / 'entries' / ('9' * 64)
            bad.mkdir(mode=0o700)
            sentinel = self.workspace / 'sentinel'
            sentinel.write_bytes(b'outside cache')
            (bad / 'stray').symlink_to(sentinel)
            bad.chmod(0o775)
            with c.lease('a' * 64, Deadline(10)) as key:
                self.assertEqual(key.begin_attempt()['classification'], 'new')
            self.assertFalse(bad.exists())
            self.assertEqual(sentinel.read_bytes(), b'outside cache')
        finally:
            os.umask(previous)

    def test_fifo_leaf_does_not_block_cache_inventory(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO is unavailable on this platform')
        c = self.cache()
        with c.lease('b' * 64, Deadline(5)) as key:
            os.mkfifo(key.path / 'blocked.idx')
            started = time.monotonic()
            with self.assertRaises(IndexUnavailable):
                key.usage()
            self.assertLess(time.monotonic() - started, 0.5)

    def test_existing_key_rebases_to_five_seconds_from_original_start(self):
        c = self.cache()
        now = [0.0]
        def clock():
            return now[0]
        with c.lease('c' * 64, Deadline(30, started=0.0, clock=clock)) as key:
            key.begin_attempt()
        now[0] = 6.0
        with c.lease('c' * 64, Deadline(30, started=0.0, clock=clock)) as key:
            with self.assertRaises(IndexUnavailable) as error:
                key.begin_attempt()
            self.assertEqual(error.exception.reason, 'index_deadline')

    def test_live_size_sampling_tolerates_owned_atomic_regular_file_replacement(self):
        c = self.cache()
        with c.lease('3' * 64, Deadline(5)) as key:
            native = key.path / 'native.idx'
            native.write_bytes(b'old')
            original = lsp_index_cache._file
            replaced = [False]

            def replace(parent, name, *args, **kwargs):
                if name == 'native.idx' and not replaced[0]:
                    replaced[0] = True
                    native.rename(key.path / 'previous.idx')
                    native.write_bytes(b'new native data')
                return original(parent, name, *args, **kwargs)

            with patch.object(lsp_index_cache, '_file', side_effect=replace):
                self.assertGreaterEqual(key.usage(active=True)['bytes'], len(b'new native data'))
            self.assertTrue(replaced[0])

    def test_global_contention_is_bounded_and_does_not_grant_second_long_budget(self):
        c = self.cache()
        ready = self.base / 'ready'
        module_path = str(Path(__file__).resolve().parents[2] / 'plugins/common/tools')
        code = '''import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from lsp_index_cache import Cache
from lsp_index_resources import Deadline
with Cache(Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4])) as c:
 with c.lease('f'*64,Deadline(30)) as k:
  k.begin_attempt();Path(sys.argv[5]).write_text('ready');time.sleep(10)
'''
        p = subprocess.Popen([sys.executable, '-B', '-c', code, module_path, str(self.root), str(self.workspace), str(self.plugin), str(ready)],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            stop = time.monotonic() + 3
            while not ready.exists() and p.poll() is None and time.monotonic() < stop:
                time.sleep(0.01)
            self.assertTrue(ready.exists())
            t = time.monotonic()
            with self.assertRaises(IndexUnavailable) as e, c.lease('f' * 64, Deadline(5), wait=0.05):
                self.fail('contended lease acquired')
            self.assertEqual(e.exception.reason, 'lock_timeout')
            self.assertLess(time.monotonic() - t, 0.5)
        finally:
            if p.poll() is None:
                p.kill()
            p.wait(timeout=3)
        with c.lease('f' * 64, Deadline(5)) as key:
            os.fstat(key.global_lock_fd)
            self.assertEqual(key.begin_attempt()['classification'], 'existing')


if __name__ == '__main__':
    unittest.main()
