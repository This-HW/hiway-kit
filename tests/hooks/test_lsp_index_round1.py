"""Failure retention, warm identity, and lifecycle regressions for Unit B R1."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'plugins/common/tools'))
import lsp_query as q
import lsp_transport as transport
from lsp_index_cache import Cache, Lease
from lsp_index_policy import IndexUnavailable
from lsp_index_resources import Deadline


@pytest.fixture
def indexed(tmp_path, monkeypatch, capsys):
    root = tmp_path / 'project'
    root.mkdir()
    source = root / 'main.c'
    source.write_text('int value;\n')
    cdb = root / 'compile_commands.json'
    cdb.write_text(json.dumps([{'directory': str(root), 'file': str(source),
                              'arguments': [str(Path(sys.executable).resolve()), '-c', str(source)]}]))
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
    server = tmp_path / 'clangd'
    server.write_text('fixture')
    monkeypatch.setattr(q, 'select_server', lambda *a, **kw: [str(server)])
    monkeypatch.setattr(q, '_indexed_toolchain', lambda *a: (str(server), ('engine', 21), None, (1, 2)))
    state = {'connections': [], 'error': None, 'certifies': 0, 'leases': []}
    original_begin = Lease.begin_attempt

    def begin(lease):
        state['leases'].append(lease)
        return original_begin(lease)
    monkeypatch.setattr(Lease, 'begin_attempt', begin)

    def certify(fd, sources, deadline, **kw):
        state['certifies'] += 1
        if state.get('post_bad') and state['certifies'] == 2:
            return q.Coverage(1, 0, False, 'index_coverage_unverified')
        return q.Coverage(1, 1, True, None)
    monkeypatch.setattr(q, 'certify', certify)
    loc = {'uri': source.as_uri(), 'range': {'start': {'line': 0, 'character': 0},
                                           'end': {'line': 0, 'character': 3}}}

    class Connection:
        def __init__(self, command, cwd, **kw):
            self.kw = kw
            self.path = Path(next(x.split('=', 1)[1] for x in command if x.startswith('--compile-commands-dir=')))
            state['connections'].append(self)
            self.count = 0
            self.finished = False

        def request(self, method, params, **kw):
            if method == 'initialize':
                return {'capabilities': {}}
            self.count += 1
            return [loc]

        def notify(self, *a):
            pass

        def wait_for_background_index(self):
            shard = self.path / '.cache/clangd/index/main.c.123.idx'
            shard.parent.mkdir(parents=True, exist_ok=True)
            shard.write_bytes(b'retained')
            (Path(self.kw['env']['TMPDIR']) / 'preamble.pch').write_bytes(b'p' * 20000)
            state['tmp_usage_bytes'] = state['leases'][-1].usage(active=True)['bytes']
            if state['error']:
                if state.get('expired'):
                    state['leases'][-1].deadline.work_ends = time.monotonic() - .01
                raise state['error']

        def finish_indexed(self, **kw):
            self.finished = True
    monkeypatch.setattr(q, 'Connection', Connection)
    args = argparse.Namespace(root=str(root), file='main.c', action='references', line=1, column=1,
                              server=None, server_arg=[], allow_custom_server=False)

    def run():
        state['certifies'] = 0
        rc = q.query(args)
        return rc, json.loads(capsys.readouterr().out)
    state.update(run=run, root=root, source=source, cdb=cdb, args=args)
    return state


@pytest.mark.parametrize('error,reason', [
    (q.LspError('request timed out'), 'index_response_unverified'),
    (q.LspBudgetExceeded('oversized references'), 'index_response_limit'),
    (q.LspBudgetExceeded('notification budget'), 'index_response_limit'),
    (q.LspError('Duplicate work-done progress token'), 'index_response_unverified'),
    (IndexUnavailable('index_deadline', 'deadline'), 'index_deadline'),
])
def test_routine_failures_retain_shards_and_partial(indexed, error, reason):
    indexed['error'] = error
    rc, payload = indexed['run']()
    assert rc == 2 and payload['reason'] == reason
    assert payload['result']
    assert list(Path(payload['index']['cache_path']).rglob('*.idx'))
    assert payload['index']['progress_increased'] is True
    assert not (Path(payload['index']['cache_path']) / 'failure.json').exists()


def test_expired_request_error_is_deadline_and_retains_progress(indexed):
    indexed.update(error=q.LspError('timed out'), expired=True)
    rc, payload = indexed['run']()
    assert rc == 2 and payload['reason'] == 'index_deadline'
    assert list(Path(payload['index']['cache_path']).rglob('*.idx'))


def test_tu_and_identical_cdb_replacement_reuse_key(indexed):
    _, first = indexed['run']()
    src = indexed['source']
    replacement = src.with_suffix('.new')
    replacement.write_text('int value;\nint new_value;\n')
    replacement.replace(src)
    _, warm = indexed['run']()
    assert warm['index']['cache_key'] == first['index']['cache_key']
    assert warm['index']['cache_classification'] == 'existing'
    cdb = indexed['cdb']
    replacement = cdb.with_suffix('.new')
    replacement.write_bytes(cdb.read_bytes())
    replacement.replace(cdb)
    _, same = indexed['run']()
    assert same['index']['cache_key'] == first['index']['cache_key']
    cdb.write_bytes(cdb.read_bytes() + b'\n')
    _, changed = indexed['run']()
    assert changed['index']['cache_key'] != first['index']['cache_key']


@pytest.mark.parametrize('exit_error', [IndexUnavailable('index_unavailable', 'late exit'), OSError('late exit')])
def test_late_cache_exit_downgrades_complete(indexed, monkeypatch, exit_error):
    original = Cache.__exit__

    def exit(cache, *a):
        original(cache, *a)
        raise exit_error
    monkeypatch.setattr(Cache, '__exit__', exit)
    rc, payload = indexed['run']()
    assert rc == 2 and payload['complete'] is False
    assert payload['result']


@pytest.mark.parametrize('check', ['cdb', 'config'])
@pytest.mark.parametrize('call', [1, 2])
def test_both_input_rechecks_are_required(indexed, monkeypatch, check, call):
    count = 0

    def unchanged(*a):
        nonlocal count
        count += 1
        return count != call
    monkeypatch.setattr(q, 'cdb_unchanged' if check == 'cdb' else 'config_still_absent', unchanged)
    rc, payload = indexed['run']()
    assert rc == 2 and payload['reason'] == 'index_inputs_changed'


def test_post_cleanup_coverage_downgrades_complete(indexed):
    indexed['post_bad'] = True
    rc, payload = indexed['run']()
    assert rc == 2 and payload['reason'] == 'index_coverage_unverified'


def test_lease_deadline_lock_fd_and_tmp_reach_connection(indexed):
    rc, payload = indexed['run']()
    conn = indexed['connections'][0]
    lease = indexed['leases'][0]
    assert conn.kw['deadline'] is lease.deadline
    assert conn.kw['pass_fds'] == (lease.global_lock_fd,)
    assert conn.kw['monitor'] is True
    assert conn.kw['env']['TMPDIR'] == str(conn.path / 'tmp')
    assert not (conn.path / 'tmp').exists()
    assert indexed['tmp_usage_bytes'] >= 20000
    assert rc == 0 and payload['complete']


@pytest.mark.parametrize('reason', ['cache_limit', 'index_resource_limit'])
def test_resource_discard_is_durable_and_consumed_next_call(indexed, reason):
    indexed['error'] = IndexUnavailable(reason, 'guard')
    _, first = indexed['run']()
    path = Path(first['index']['cache_path'])
    assert not list(path.rglob('*.idx'))
    assert json.loads((path / 'failure.json').read_text()) == {'reason': reason}
    indexed['error'] = None
    _, second = indexed['run']()
    assert second['index']['previous_failure'] == reason
    assert second['index']['cache_classification'] == 'existing'
    assert not (path / 'failure.json').exists()


def test_fallback_has_shared_deadline_wall_bound(indexed, monkeypatch, capsys):
    deadline = Deadline(.08, reserve=.02)
    monkeypatch.setattr(q, 'discover_compile_database', lambda *a: (_ for _ in ()).throw(IndexUnavailable('no_compile_db', 'none')))
    monkeypatch.setattr(q, 'Deadline', lambda *a, **kw: deadline)
    real_connection = transport.Connection
    source = indexed['source']

    def connection(command, cwd, **kw):
        assert kw['deadline'] is deadline
        return real_connection([sys.executable, '-c', 'import time; time.sleep(10)'], cwd, **kw)
    monkeypatch.setattr(q, 'Connection', connection)
    started = time.monotonic()
    rc = q.query(indexed['args'])
    assert time.monotonic() - started < 1.5
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2 and not payload['complete'] and payload['reason'] == 'no_compile_db'
    assert payload['cause'] == 'index_deadline'
    assert source.exists()


def test_lock_inherited_by_live_server_and_guard_deadline(tmp_path):
    cache_home = tmp_path / 'cache'
    workspace = tmp_path / 'workspace'
    plugin = tmp_path / 'plugin'
    workspace.mkdir()
    plugin.mkdir()
    d = Deadline(5)
    with Cache(cache_home, workspace, plugin) as cache, cache.lease('a' * 64, d) as lease:
        lease.begin_attempt()
        connection = transport.Connection([sys.executable, '-c', 'import time; time.sleep(10)'],
                                          str(workspace), deadline=lease.deadline, monitor=True,
                                          pass_fds=(lease.global_lock_fd,))
        try:
            assert connection.guard.deadline is lease.deadline
            # Retain only the child's inherited descriptor, then prove another
            # process still cannot acquire this global lock while child lives.
            os.close(lease.global_lock_fd)
            replacement = os.open(cache_home / 'scheduler.lock', os.O_RDWR)
            assert replacement == lease.global_lock_fd
            result = subprocess.run([sys.executable, '-c',
                                     'import fcntl,sys; f=open(sys.argv[1],"r+"); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)',
                                     str(cache_home / 'scheduler.lock')], capture_output=True, check=False)
            assert result.returncode != 0
        finally:
            connection.finish_indexed(graceful=False)
            connection.close()  # idempotent; never signal a reaped numeric PID


def test_apple_selected_binary_preserved_except_system_shim(tmp_path, monkeypatch):
    root = tmp_path / 'workspace'
    root.mkdir()
    tools = tmp_path / 'external'
    tools.mkdir()
    binary = tools / 'clangd'
    binary.write_text('fixture')
    binary.chmod(0o700)
    sdk = tmp_path / 'SDK'
    sdk.mkdir()
    monkeypatch.setattr(q.sys, 'platform', 'darwin')
    monkeypatch.setattr(q.shutil, 'which', lambda name: '/usr/bin/xcrun')
    from types import SimpleNamespace
    monkeypatch.setattr(q, 'resolve_executable', lambda path, *a: SimpleNamespace(executable=str(path)))
    calls = []

    def probe(argv, *a):
        calls.append(argv)
        if '--find' in argv:
            return str(binary)
        if '--show-sdk-path' in argv:
            return str(sdk)
        return 'clangd 21'
    monkeypatch.setattr(q, '_probe', probe)
    for selected, expected_find in [(str(binary), False), ('/usr/bin/clangd', True)]:
        calls.clear()
        result, *_ = q._indexed_toolchain([selected], root, {}, Deadline(5))
        assert str(getattr(result, 'executable', result)) == str(binary)
        assert any('--find' in argv for argv in calls) is expected_find


def test_untrusted_cleanup_discards_native_data(indexed, monkeypatch):
    connection = q.Connection
    original_finish = connection.finish_indexed

    def finish(self, **kw):
        original_finish(self, **kw)
        raise IndexUnavailable('index_unavailable', 'untrusted child cleanup')
    monkeypatch.setattr(connection, 'finish_indexed', finish)
    rc, payload = indexed['run']()
    assert rc == 2 and not payload['complete']
    assert not list(Path(payload['index']['cache_path']).rglob('*.idx'))
    assert (Path(payload['index']['cache_path']) / 'failure.json').exists()


@pytest.mark.parametrize('transition', [True, False])
def test_rss_unknown_only_tolerates_confirmed_exit(tmp_path, transition):
    from lsp_index_resources import ResourceGuard
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'], start_new_session=True)
    calls = []
    guard = None

    def sampler(deadline):
        calls.append(1)
        row = {'pid': process.pid, 'ppid': os.getpid(), 'pgid': process.pid,
               'rss': None, 'state': 2, 'start': 1}
        if len(calls) == 2:
            guard.stopped.set()
            return [] if transition else [row]
        return [row]
    guard = ResourceGuard(process, Deadline(2), sampler=sampler)
    try:
        guard._watch_loop()
        assert (guard.reason is None) is transition
        assert len(calls) >= 2
    finally:
        process.kill()
        process.wait(timeout=2)


def test_resource_guard_serializes_concurrent_popen_poll(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from lsp_index_resources import ResourceGuard
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'], start_new_session=True)
    guard = ResourceGuard(process, Deadline(2))
    entered = threading.Event()
    release = threading.Event()
    second_entered = threading.Event()
    active = 0
    original = process.poll

    def poll():
        nonlocal active
        active += 1
        try:
            assert active == 1, 'concurrent poll may report None during another reap'
            entered.set()
            assert release.wait(1)
            return original()
        finally:
            active -= 1
    process.poll = poll
    try:
        with ThreadPoolExecutor(2) as pool:
            a = pool.submit(guard._poll)
            assert entered.wait(1)
            def second():
                second_entered.set()
                return guard._poll()
            b = pool.submit(second)
            assert second_entered.wait(1)
            time.sleep(.02)
            release.set()
            assert a.result() is None
            assert b.result() is None
    finally:
        process.poll = original
        process.kill()
        process.wait(timeout=2)


@pytest.mark.parametrize('mode', ['oversized', 'delayed', 'duplicate', 'notifications'])
def test_real_transport_error_retains_shards_and_skips_shutdown(indexed, monkeypatch, mode):
    script = indexed['root'].parent / 'clangd'
    script.write_text('#!' + sys.executable + '\n' + r'''
import json,pathlib,sys,time
entry=pathlib.Path(next(a.split('=',1)[1] for a in sys.argv if a.startswith('--compile-commands-dir=')))
def send(obj):
 raw=json.dumps(obj).encode();sys.stdout.buffer.write(b'Content-Length: '+str(len(raw)).encode()+b'\r\n\r\n'+raw);sys.stdout.buffer.flush()
while True:
 header=sys.stdin.buffer.readline()
 if not header: break
 length=int(header.split(b':')[1]);sys.stdin.buffer.readline();msg=json.loads(sys.stdin.buffer.read(length))
 method=msg.get('method')
 if method=='initialize': send({'jsonrpc':'2.0','id':msg['id'],'result':{'capabilities':{}}})
 elif method=='shutdown': (entry/'unexpected-shutdown').touch();send({'jsonrpc':'2.0','id':msg['id'],'result':None})
 elif method=='textDocument/references':
  index=entry/'.cache/clangd/index';index.mkdir(parents=True,exist_ok=True);(index/'main.c.123.idx').write_bytes(b'keep-me')
  mode=MODE
  if mode=='delayed': time.sleep(.8)
  send({'jsonrpc':'2.0','id':msg['id'],'result':[]})
  if mode=='oversized': sys.stdout.buffer.write(b'Content-Length: 3145728\r\n\r\n');sys.stdout.buffer.flush()
  if mode=='duplicate':
   for id in [500,501]: send({'jsonrpc':'2.0','id':id,'method':'window/workDoneProgress/create','params':{'token':'backgroundIndexProgress'}})
  if mode=='notifications':
   for i in range(140): send({'jsonrpc':'2.0','method':'textDocument/publishDiagnostics','params':{'uri':msg['params']['textDocument']['uri'],'diagnostics':[]}})
  time.sleep(10)
'''.replace('MODE', repr(mode)))
    script.chmod(0o700)
    sent = []
    original_send = transport.Connection.send

    def send(connection, message, **kwargs):
        sent.append(message.get('method'))
        if message.get('method') == 'initialized':
            monkeypatch.setattr(transport, 'REQUEST_TIMEOUT', .25)
        return original_send(connection, message, **kwargs)
    monkeypatch.setattr(transport.Connection, 'send', send)
    connections = []

    def connect(*args, **kwargs):
        connection = transport.Connection(*args, **kwargs)
        connection.test_guard = connection.guard
        connections.append(connection)
        return connection
    monkeypatch.setattr(q, 'Connection', connect)
    monkeypatch.setattr(transport, 'REQUEST_TIMEOUT', 3)
    started = time.monotonic()
    rc, payload = indexed['run']()
    assert time.monotonic() - started < 4
    assert rc == 2 and payload['complete'] is False
    path = Path(payload['index']['cache_path'])
    shard = path / '.cache/clangd/index/main.c.123.idx'
    assert shard.exists(), (payload, connections[0].cleanup_verified, connections[0].test_guard.reason, sent)
    assert shard.read_bytes() == b'keep-me'
    assert not (path / 'unexpected-shutdown').exists()
    assert 'shutdown' not in sent
    assert connections[0].cleanup_verified is True
    assert connections[0].process.returncode is not None
    assert not (path / 'failure.json').exists()


def test_transient_budget_is_separate_and_shards_survive(indexed, monkeypatch):
    import lsp_index_cache as cache_module
    monkeypatch.setattr(cache_module, 'TRANSIENT_BYTES', 1000)
    original = q.Connection.wait_for_background_index

    def write_tmp_then_check(connection):
        original(connection)
        indexed['leases'][-1].check_disk()
    monkeypatch.setattr(q.Connection, 'wait_for_background_index', write_tmp_then_check)
    rc, payload = indexed['run']()
    assert rc == 2 and payload['reason'] == 'index_transient_limit'
    path = Path(payload['index']['cache_path'])
    assert list(path.rglob('*.idx'))
    assert not (path / 'tmp').exists()
    assert not (path / 'failure.json').exists()


def test_tmp_does_not_use_persistent_budget_and_stale_tmp_is_cleared(tmp_path, monkeypatch):
    import lsp_index_cache as cache_module
    workspace, plugin = tmp_path/'w', tmp_path/'p'
    workspace.mkdir()
    plugin.mkdir()
    with Cache(tmp_path/'cache', workspace, plugin) as cache, cache.lease('c'*64, Deadline(5)) as lease:
        tmp = lease.prepare_tmp()
        (tmp/'old.pch').write_bytes(b'x'*10000)
        monkeypatch.setattr(cache_module, 'KEY_BYTES', 1000)
        lease.check_disk()  # temp is not persistent data
        tmp = lease.prepare_tmp()
        assert list(tmp.iterdir()) == []
        (tmp/'abandoned.pch').write_bytes(b'x'*10000)
        lease.begin_attempt()  # startup classification must also recover stale tmp
        assert not tmp.exists()


@pytest.mark.parametrize('raw', [b'['+b'[],'*10+b'[]]', b'['+b'"",'*70+b'""]'])
def test_array_and_string_amplification_rejected_before_json_load(monkeypatch, raw):
    import lsp_index_inputs as inputs
    monkeypatch.setattr(inputs, 'CDB_ENTRIES', 2)
    with pytest.raises(IndexUnavailable, match='structural allocation'):
        inputs._bounded_structure(raw, Deadline(5))


@pytest.mark.parametrize('content', ['invalid', 'unsafe', 'symlink'])
def test_invalid_failure_record_does_not_pin_key(indexed, content):
    _, first = indexed['run']()
    record = Path(first['index']['cache_path'])/'failure.json'
    if content == 'symlink':
        target = record.parent/'untouched'
        target.write_text('keep')
        record.symlink_to(target)
    else:
        record.write_text('invalid json')
        record.chmod(0o666 if content == 'unsafe' else 0o600)
    rc, payload = indexed['run']()
    assert rc == 0 and payload['complete']
    assert not record.exists()
    if content == 'symlink':
        assert target.read_text() == 'keep'



@pytest.mark.parametrize('guard_reason', ['index_unavailable', 'index_resource_limit'])
def test_fallback_returns_partial_when_indexed_sampler_or_rss_would_fail(indexed, monkeypatch, guard_reason):
    script = indexed['root'].parent/'clangd'
    script.write_text('#!' + sys.executable + '\n' + r'''
import json,sys
while True:
 header=sys.stdin.buffer.readline()
 if not header: break
 size=int(header.split(b':')[1]);sys.stdin.buffer.readline();msg=json.loads(sys.stdin.buffer.read(size))
 if 'id' not in msg: continue
 result={'capabilities':{}} if msg['method']=='initialize' else []
 raw=json.dumps({'jsonrpc':'2.0','id':msg['id'],'result':result}).encode()
 sys.stdout.buffer.write(b'Content-Length: '+str(len(raw)).encode()+b'\r\n\r\n'+raw);sys.stdout.buffer.flush()
''')
    script.chmod(0o700)
    indexed['cdb'].unlink()

    def guard(*args, **kwargs):
        raise IndexUnavailable(guard_reason, 'indexed-only policy rejects this server')
    monkeypatch.setattr(transport, 'ResourceGuard', guard)
    monkeypatch.setattr(q, 'Connection', transport.Connection)
    rc, payload = indexed['run']()
    assert rc == 2 and payload['reason'] == 'no_compile_db'
    assert payload['result'] == []


def test_error_classification_checks_lease_deadline(indexed, monkeypatch):
    original = Lease.begin_attempt

    def begin(lease):
        value = original(lease)
        lease.deadline = Deadline(5)
        return value
    monkeypatch.setattr(Lease, 'begin_attempt', begin)
    indexed.update(error=q.LspError('timed out'), expired=True)
    rc, payload = indexed['run']()
    assert rc == 2 and payload['reason'] == 'index_deadline'


def test_unknown_rss_transition_exemptions_are_bounded(tmp_path):
    from lsp_index_resources import ResourceGuard
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'], start_new_session=True)
    calls = 0

    def sampler(deadline):
        nonlocal calls
        calls += 1
        return [{'pid': process.pid, 'ppid': os.getpid(), 'pgid': process.pid, 'start': 1,
                 'rss': None, 'state': 2 if calls % 2 else 5}]
    guard = ResourceGuard(process, Deadline(2), sampler=sampler, interval=.001)
    try:
        guard._watch_loop()
        assert guard.reason == 'index_unavailable'
        assert guard._unknown_rss_exemptions == 3
    finally:
        process.kill()
        process.wait(timeout=2)



@pytest.mark.parametrize("earlier_error", [None, q.LspError("stream failed")])
def test_verified_cleanup_error_preserves_shards(indexed, monkeypatch, earlier_error):
    indexed["error"] = earlier_error
    original = q.Connection.finish_indexed

    def finish(connection, **kwargs):
        if connection.finished:
            return
        original(connection, **kwargs)
        connection.cleanup_verified = True
        raise IndexUnavailable('index_unavailable', 'guard reported an earlier error, group verified gone')
    monkeypatch.setattr(q.Connection, 'finish_indexed', finish)
    rc, payload = indexed['run']()
    assert rc == 2 and not payload['complete']
    assert list(Path(payload['index']['cache_path']).rglob('*.idx'))
    assert not (Path(payload['index']['cache_path'])/'failure.json').exists()


@pytest.mark.parametrize('raw', [b'['+b'[],'*10+b'[]]', b'['+b'"",'*70+b'""]'])
def test_structural_bound_runs_before_cdb_json_allocation(indexed, monkeypatch, raw):
    import lsp_index_inputs as inputs
    monkeypatch.setattr(inputs, 'CDB_ENTRIES', 2)
    indexed['cdb'].write_bytes(raw)
    with pytest.raises(IndexUnavailable, match='structural allocation'):
        inputs.discover_compile_database(indexed['root'], indexed['source'],
                                         {'HOME': str(indexed['root'].parent/'home')}, Deadline(5))


@pytest.mark.parametrize("work_left", [0, .05])
def test_work_cutoff_skips_handshake_and_verifies_cleanup(indexed, monkeypatch, work_left):
    from lsp_index_resources import ResourceGuard
    script = indexed['root'].parent/'clangd'
    script.write_text('#!' + sys.executable + '\n' + r'''
import json,pathlib,sys,time
entry=pathlib.Path(next(a.split('=',1)[1] for a in sys.argv if a.startswith('--compile-commands-dir=')))
def send(obj):
 raw=json.dumps(obj).encode();sys.stdout.buffer.write(b'Content-Length: '+str(len(raw)).encode()+b'\r\n\r\n'+raw);sys.stdout.buffer.flush()
while True:
 header=sys.stdin.buffer.readline()
 if not header: break
 size=int(header.split(b':')[1]);sys.stdin.buffer.readline();msg=json.loads(sys.stdin.buffer.read(size))
 method=msg.get('method')
 if method=='initialize': send({'jsonrpc':'2.0','id':msg['id'],'result':{'capabilities':{}}})
 elif method=='textDocument/references':
  index=entry/'.cache/clangd/index';index.mkdir(parents=True,exist_ok=True);(index/'retained.idx').write_bytes(b'keep')
  send({'jsonrpc':'2.0','id':msg['id'],'result':[]})
 elif method=='shutdown': (entry/'shutdown-sent').touch();send({'jsonrpc':'2.0','id':msg['id'],'result':None})
 elif method=='exit': time.sleep(2);(entry/'voluntary-exit').touch();break
''')
    if indexed.get('slow_shutdown'):
        script.write_text(script.read_text().replace("(entry/'shutdown-sent').touch();send(",
            "(entry/'shutdown-sent').touch();time.sleep(2);(entry/'shutdown-waited').touch();send("))
    script.chmod(0o700)
    connections = []
    cleanup_errors = []
    def guard(process, deadline, **kwargs):
        return ResourceGuard(process, deadline, interval=10, **kwargs)
    monkeypatch.setattr(transport, 'ResourceGuard', guard)
    def connect(*args, **kwargs):
        connection = transport.Connection(*args, **kwargs)
        original_finish = connection.finish_indexed
        def finish(**options):
            try:
                return original_finish(**options)
            except BaseException as exc:
                cleanup_errors.append(type(exc).__name__+": "+str(exc))
                raise
        connection.finish_indexed = finish
        connections.append(connection)
        return connection
    monkeypatch.setattr(q, 'Connection', connect)
    original_wait = transport.Connection.wait_for_background_index
    def expire(connection):
        end = time.monotonic()+5
        while not connection.guard.peak_rss and time.monotonic() < end:
            time.sleep(.001)
        assert connection.guard.peak_rss > 0
        assert connection.guard.reason is None and not connection.guard.cancelled.is_set()
        # Delay the watchdog to choose the expiry interleaving, but do not
        # stretch kill/reap polling to the entire cleanup reserve.
        connection.guard.interval = .01
        started = time.monotonic()
        if work_left:
            released = []
            marker = indexed['leases'][-1].path/'shutdown-sent'
            def handshake_clock():
                if not released and marker.exists():
                    released.append(time.monotonic())
                return started if not released else started + time.monotonic()-released[0]
            # Freeze only test work time until handshake arrival, then give the
            # real transport/server 50ms of live work time before forced cleanup.
            connection.deadline.clock = handshake_clock
        connection.deadline.work_ends = started+work_left
        connection.deadline.ends = started+3
        if work_left:
            raise IndexUnavailable("index_coverage_unverified", "query failed just before work cutoff")
        return original_wait(connection)
    monkeypatch.setattr(transport.Connection, 'wait_for_background_index', expire)
    try:
        rc, payload = indexed['run']()
        path = Path(payload['index']['cache_path'])
        observation = {'cleanup_errors': cleanup_errors, 'rc': rc, 'reason': payload.get('reason'),
                       'shutdown': (path/'shutdown-sent').exists(),
                       'voluntary_exit': (path/'voluntary-exit').exists(),
                       'cleanup_verified': connections[0].cleanup_verified,
                       'shard_retained': (path/'.cache/clangd/index/retained.idx').exists()}
        print(json.dumps(observation))
        assert rc == 2 and payload['reason'] == ('index_coverage_unverified' if work_left else 'index_deadline')
        if work_left:
            assert observation['shutdown'], observation
        else:
            assert not observation['shutdown'], observation
        assert not observation['voluntary_exit'], observation
        assert observation['cleanup_verified'], observation
        assert observation['shard_retained'], observation
    finally:
        for connection in connections:
            if connection.process.poll() is None:
                connection.process.kill()
                connection.process.wait(timeout=2)


@pytest.mark.parametrize('reason', ['cache_limit', 'index_transient_limit', 'index_resource_limit'])
def test_real_guard_reason_wins_over_reader_eof(indexed, monkeypatch, reason):
    import threading

    from lsp_index_resources import ResourceGuard
    script = indexed['root'].parent/'clangd'
    script.write_text('#!' + sys.executable + '\n' + r'''
import json,pathlib,sys,time
entry=pathlib.Path(next(a.split('=',1)[1] for a in sys.argv if a.startswith('--compile-commands-dir=')))
while True:
 header=sys.stdin.buffer.readline()
 if not header: break
 size=int(header.split(b':')[1]);sys.stdin.buffer.readline();msg=json.loads(sys.stdin.buffer.read(size))
 if msg.get('method')=='initialize':
  raw=json.dumps({'jsonrpc':'2.0','id':msg['id'],'result':{'capabilities':{}}}).encode();sys.stdout.buffer.write(b'Content-Length: '+str(len(raw)).encode()+b'\r\n\r\n'+raw);sys.stdout.buffer.flush()
 elif msg.get('method')=='textDocument/references':
  index=entry/'.cache/clangd/index';index.mkdir(parents=True);(index/'keep.idx').write_bytes(b'keep');time.sleep(10)
''')
    script.chmod(0o700)
    fired = []
    def connect(command, cwd, **kwargs):
        entry = Path(next(a.split('=',1)[1] for a in command if a.startswith('--compile-commands-dir=')))
        def disk():
            if (entry/'.cache/clangd/index/keep.idx').exists():
                fired.append(threading.get_ident())
                raise IndexUnavailable(reason, 'test guard limit')
        kwargs['disk_check'] = disk
        return transport.Connection(command, cwd, **kwargs)
    def guard(process, deadline, **kwargs):
        return ResourceGuard(process, deadline, interval=.01, **kwargs)
    monkeypatch.setattr(transport, 'ResourceGuard', guard)
    monkeypatch.setattr(q, 'Connection', connect)
    rc, payload = indexed['run']()
    assert fired and all(t != threading.get_ident() for t in fired)
    assert rc == 2 and payload['reason'] == reason
    retained = list(Path(payload['index']['cache_path']).rglob('*.idx'))
    assert bool(retained) is (reason == 'index_transient_limit')


def test_dead_reader_without_caught_protocol_error_skips_handshake(tmp_path, monkeypatch):
    import threading
    errors = []
    monkeypatch.setattr(threading, 'excepthook', lambda args: errors.append(args.exc_value))
    def invalid(message):
        raise TypeError('unexpected reader failure outside caught tuple')
    monkeypatch.setattr(transport, 'validate_message', invalid)
    code = "import sys,time; sys.stdout.buffer.write(b'Content-Length: 45\\r\\n\\r\\n{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":null}');sys.stdout.buffer.flush();time.sleep(10)"
    # Serialize the body so Content-Length itself is valid; only injected TypeError kills the reader.
    body = json.dumps({'jsonrpc':'2.0','id':1,'result':None}).encode()
    frame = b'Content-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body
    code = f'import sys,time;sys.stdout.buffer.write({frame!r});sys.stdout.buffer.flush();time.sleep(10)'
    connection = transport.Connection([sys.executable, '-c', code], str(tmp_path), deadline=Deadline(5), monitor=True)
    def send(message, **kwargs):
        assert message.get('method') != 'shutdown', 'dead reader must skip handshake'
    connection.send = send
    try:
        connection.reader.join(timeout=2)
        assert errors and isinstance(errors[0], TypeError)
        assert not connection.reader.is_alive() and not connection._stream_failed
        connection.finish_indexed()
        assert connection.cleanup_verified
    finally:
        connection.close()


def test_verified_guard_close_oserror_keeps_shards(indexed, monkeypatch):
    from lsp_index_resources import ResourceGuard
    original = ResourceGuard.close
    def close(guard):
        original(guard)
        assert guard.cleanup_verified
        raise OSError('close failed after verified cleanup')
    monkeypatch.setattr(ResourceGuard, 'close', close)
    test_real_transport_error_retains_shards_and_skips_shutdown(indexed, monkeypatch, 'oversized')


def test_prune_clears_inactive_tmp_and_keeps_persistent_shards(tmp_path):
    workspace, plugin = tmp_path/'w', tmp_path/'p'
    workspace.mkdir()
    plugin.mkdir()
    with Cache(tmp_path/'cache', workspace, plugin) as cache:
        with cache.lease('d'*64, Deadline(5)) as lease:
            lease.begin_attempt()
            old = lease.path
            (lease.prepare_tmp()/'abandoned.pch').write_bytes(b'x'*10000)
            (old/'persist.idx').write_bytes(b'keep')
        with cache.lease('e'*64, Deadline(5)):
            assert not (old/'tmp').exists()
            assert (old/'persist.idx').read_bytes() == b'keep'


def test_prune_retained_budget_excludes_active_tmp(tmp_path):
    workspace, plugin = tmp_path/'w', tmp_path/'p'
    workspace.mkdir()
    plugin.mkdir()
    with Cache(tmp_path/'cache', workspace, plugin) as cache, cache.lease('f'*64, Deadline(5)) as lease:
        lease.begin_attempt()
        (lease.prepare_tmp()/'active.pch').write_bytes(b'x'*10000)
        cache.prune(lease.deadline, exclude=lease.key, max_bytes=1000)
        assert (lease.path/'tmp/active.pch').exists()


def test_fallback_close_timeout_normalized_and_pipes_closed(tmp_path, monkeypatch):
    connection = transport.Connection([sys.executable, '-c', 'import time;time.sleep(10)'], str(tmp_path), deadline=Deadline(5))
    original = connection.process.wait
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('fixture', 0)
    monkeypatch.setattr(connection.process, 'wait', timeout)
    try:
        with pytest.raises(IndexUnavailable) as error:
            connection.close()
        assert error.value.reason == 'index_deadline'
        assert connection.process.stdin.closed and connection.process.stdout.closed
    finally:
        monkeypatch.setattr(connection.process, 'wait', original)
        if connection.process.poll() is None:
            connection.process.kill()
        connection.process.wait(timeout=2)


def test_numeric_array_allocation_bound(monkeypatch):
    import lsp_index_inputs as inputs
    monkeypatch.setattr(inputs, 'CDB_ENTRIES', 2)
    with pytest.raises(IndexUnavailable, match='literal'):
        inputs._bounded_structure(b'['+b'0,'*200+b'0]', Deadline(5))


def test_failed_first_reap_cannot_later_certify_cleanup(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from lsp_index_resources import ResourceGuard
    process = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(10)'], start_new_session=True)
    bad = [True]
    def sampler(deadline):
        return ([{'pid':process.pid+1,'pgid':process.pid,'ppid':1,'start':1,'rss':1}]
                if bad[0] else [])
    guard = ResourceGuard(process, Deadline(5), sampler=sampler)
    guard.thread = SimpleNamespace(join=lambda **kwargs: None, is_alive=lambda: False)
    guard.watch_finished = True
    monkeypatch.setattr(guard, '_kill', lambda **kwargs: None)
    process.kill()
    process.wait(timeout=2)
    with pytest.raises(IndexUnavailable, match='Leader was reaped'):
        guard.reap()
    bad[0] = False
    with pytest.raises(IndexUnavailable):
        guard.reap()
    assert guard.cleanup_verified is False


def test_guard_reason_without_cancel_or_expiry_skips_handshake():
    import io
    from types import SimpleNamespace
    calls = []
    connection = transport.Connection.__new__(transport.Connection)
    connection._indexed_finished = False
    connection._stream_failed = False
    connection.deadline = Deadline(5)
    connection.reader = SimpleNamespace(is_alive=lambda:True, join=lambda **kwargs:None)
    connection.process = SimpleNamespace(stdin=io.BytesIO(), stdout=io.BytesIO())
    connection.guard = SimpleNamespace(reason='cache_limit', cancelled=SimpleNamespace(is_set=lambda:False),
        cleanup_verified=True, _kill=lambda:calls.append('kill'), reap=lambda:calls.append('reap'), close=lambda:None)
    connection.request = lambda *args, **kwargs: pytest.fail('guard reason must skip handshake')
    connection.finish_indexed()
    assert calls == ['kill','reap']
    assert connection.cleanup_verified


def test_lexical_guard_ignores_escaped_structural_characters(monkeypatch):
    import lsp_index_inputs as inputs
    monkeypatch.setattr(inputs, 'CDB_ENTRIES', 2)
    raw = json.dumps(['quotes \\" , [{ }]'*1000]).encode()
    inputs._bounded_structure(raw, Deadline(5))


@pytest.mark.parametrize('literal,name', [('9'*1000,'integer'), ('1.'+'0'*1000,'float')])
def test_cdb_numeric_conversion_length_is_bounded(indexed, literal, name):
    import lsp_index_inputs as inputs
    indexed['cdb'].write_text('['+literal+']')
    with pytest.raises(IndexUnavailable, match=name+' literal exceeds 32'):
        inputs.discover_compile_database(indexed['root'], indexed['source'],
                                         {'HOME':str(indexed['root'].parent/'home')}, Deadline(5))


def test_prune_does_not_remove_contended_key_tmp(tmp_path):
    import fcntl
    workspace, plugin = tmp_path/'w', tmp_path/'p'
    workspace.mkdir()
    plugin.mkdir()
    with Cache(tmp_path/'cache', workspace, plugin) as cache:
        key = '1'*64
        with cache.lease(key, Deadline(5)) as lease:
            lease.begin_attempt()
            active = lease.path
            (lease.prepare_tmp()/'active.pch').write_bytes(b'keep active')
        fd = os.open(cache.path/('key-'+key+'.lock'), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with cache.lease('2'*64, Deadline(5)):
                assert (active/'tmp/active.pch').read_bytes() == b'keep active'
        finally:
            os.close(fd)


@pytest.mark.parametrize('failure', [PermissionError('undeletable tmp'), IndexUnavailable('index_unavailable','tmp unavailable'), IndexUnavailable('index_deadline','expired')])
def test_prune_tmp_removal_failure_does_not_classify_key_bad(tmp_path, monkeypatch, failure):
    import lsp_index_cache as cache_module
    workspace, plugin = tmp_path/'w', tmp_path/'p'
    workspace.mkdir()
    plugin.mkdir()
    with Cache(tmp_path/'cache', workspace, plugin) as cache:
        with cache.lease('3'*64, Deadline(5)) as lease:
            lease.begin_attempt()
            old = lease.path
            (lease.prepare_tmp()/'stubborn.pch').write_bytes(b'x')
            (old/'keep.idx').write_bytes(b'persistent')
        original = cache_module._remove_tree_fd
        def removal(parent, name, *args, **kwargs):
            if name == 'tmp':
                raise failure
            assert name != old.name, 'tmp failure must not quarantine persistent key'
            return original(parent, name, *args, **kwargs)
        monkeypatch.setattr(cache_module, '_remove_tree_fd', removal)
        if isinstance(failure, IndexUnavailable) and failure.reason == 'index_deadline':
            with pytest.raises(IndexUnavailable, match='expired'), cache.lease('4'*64, Deadline(5)):
                pass
        else:
            with cache.lease('4'*64, Deadline(5)):
                pass
        assert (old/'keep.idx').read_bytes() == b'persistent'
        assert (old/'tmp/stubborn.pch').exists()


def test_comma_bound_with_a_string_present(monkeypatch):
    import lsp_index_inputs as inputs
    monkeypatch.setattr(inputs, 'CDB_ENTRIES', 2)
    with pytest.raises(IndexUnavailable, match='literal count'):
        inputs._bounded_structure(b'["text",'+b'0,'*200+b'0]', Deadline(5))


def test_nonlimit_guard_reason_does_not_replace_primary_cause(indexed, monkeypatch):
    original = q.Connection.finish_indexed
    def finish(connection, **kwargs):
        original(connection, **kwargs)
        connection.guard_reason = 'index_deadline'
    monkeypatch.setattr(q.Connection, 'finish_indexed', finish)
    indexed['error'] = q.LspError('protocol failure')
    rc, payload = indexed['run']()
    assert rc == 2 and payload['reason'] == 'index_response_unverified'


def test_limit_guard_reason_keeps_original_cause(indexed, monkeypatch):
    original = q.Connection.finish_indexed
    def finish(connection, **kwargs):
        original(connection, **kwargs)
        connection.guard_reason = 'index_transient_limit'
    monkeypatch.setattr(q.Connection, 'finish_indexed', finish)
    indexed['error'] = q.LspError('protocol failure')
    rc, payload = indexed['run']()
    assert rc == 2 and payload['reason'] == 'index_transient_limit'
    assert payload['cause'] == 'index_response_unverified'


def test_observed_reaped_children_stay_compromised_after_recovery(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from lsp_index_resources import ResourceGuard
    process = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(10)'], start_new_session=True)
    calls = []
    def sampler(deadline):
        calls.append(1)
        return ([{'pid':process.pid+1,'pgid':process.pid,'ppid':1,'start':1,'rss':1}]
                if len(calls)==1 else [])
    guard = ResourceGuard(process, Deadline(5), sampler=sampler)
    guard.thread = SimpleNamespace(join=lambda **kwargs:None, is_alive=lambda:False)
    guard.watch_finished = True
    monkeypatch.setattr(guard, '_kill', lambda **kwargs:None)
    process.kill()
    process.wait(timeout=2)
    with pytest.raises(IndexUnavailable):
        guard.reap()
    assert guard.cleanup_verified is False


@pytest.mark.parametrize('entries,raw,message', [
    (2,b'['*10+b']'*10,'container count'),
    (2,json.dumps(['s']*65).encode(),'string count'),
    (100,b'['*65+b']'*65,'nesting depth'),
    (2,json.dumps(['s']+[0]*130).encode(),'literal count'),
])
def test_structural_allocation_failures_name_the_bound(monkeypatch, entries, raw, message):
    import lsp_index_inputs as inputs
    monkeypatch.setattr(inputs,'CDB_ENTRIES',entries)
    with pytest.raises(IndexUnavailable, match=message):
        inputs._bounded_structure(raw, Deadline(5))


@pytest.mark.parametrize('kind,value', [('int','9'*32), ('float','1.'+'0'*30)])
def test_numeric_literal_accepts_exact_32_character_boundary(kind, value):
    import lsp_index_inputs as inputs
    helper = inputs._bounded_int if kind == 'int' else inputs._bounded_float
    assert helper(value) is not None
    with pytest.raises(IndexUnavailable, match='32 characters'):
        helper(value+'0')



def test_graceful_shutdown_response_cannot_spend_cleanup_reserve(indexed, monkeypatch):
    indexed['slow_shutdown'] = True
    test_work_cutoff_skips_handshake_and_verifies_cleanup(indexed, monkeypatch, .05)
    assert not (indexed['leases'][-1].path/'shutdown-waited').exists()


def test_fallback_wait_keeps_small_positive_minimum(tmp_path, monkeypatch):
    connection = transport.Connection([sys.executable,'-c','import time;time.sleep(10)'],str(tmp_path),deadline=Deadline(5))
    original = connection.process.wait
    waits = []
    def wait(*args, **kwargs):
        waits.append(kwargs['timeout'])
        assert kwargs['timeout'] >= .05
        return original(*args, **kwargs)
    monkeypatch.setattr(connection.process,'wait',wait)
    connection.deadline.ends = 0
    try:
        connection.close()
        assert waits
    finally:
        monkeypatch.setattr(connection.process,'wait',original)
        if connection.process.poll() is None:
            connection.process.kill()
        original(timeout=2)


def test_voluntary_work_cutoff_has_deterministic_deadline_reason(tmp_path):
    from types import SimpleNamespace

    from lsp_index_resources import ResourceGuard
    process = subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'], start_new_session=True)
    guard = ResourceGuard(process, Deadline(5), interval=.01)
    guard.thread = SimpleNamespace(join=lambda **kwargs:None, is_alive=lambda:False)
    guard.watch_finished = True
    guard.deadline.work_ends = 0
    try:
        with pytest.raises(IndexUnavailable) as error:
            guard.reap(graceful=True)
        assert error.value.reason == 'index_deadline'
        assert guard.reason == 'index_deadline'
        assert guard.cleanup_verified
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_reap_resamples_if_leader_was_reaped_during_snapshot(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from lsp_index_resources import ResourceGuard
    process = subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'], start_new_session=True)
    samples = []
    def sampler(deadline):
        samples.append(1)
        if len(samples)==1:
            process.wait(timeout=2)
            return [{'pid':process.pid,'pgid':process.pid,'ppid':os.getpid(),'state':'Z','start':1,'rss':0},
                    {'pid':process.pid+1,'pgid':process.pid,'ppid':process.pid,'state':'S','start':2,'rss':1}]
        return []
    guard = ResourceGuard(process, Deadline(5), sampler=sampler)
    guard.thread = SimpleNamespace(join=lambda **kwargs:None, is_alive=lambda:False)
    guard.watch_finished = True
    process.kill()
    monkeypatch.setattr(guard,'_kill',lambda **kwargs:pytest.fail('stale group snapshot must be refreshed'))
    assert guard.reap() is not None
    assert len(samples)>=3 and guard.cleanup_verified
    assert not guard._cleanup_compromised


def test_d7_late_group_observation_invalidates_prior_verification(tmp_path, monkeypatch):
    from lsp_index_resources import ResourceGuard
    process = subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'], start_new_session=True)
    guard = ResourceGuard(process, Deadline(5), sampler=lambda deadline:[])
    process.kill()
    process.wait(timeout=2)
    guard._verified_once = True
    assert guard.cleanup_verified
    monkeypatch.setattr(guard,'_signal_group',lambda:None)
    guard._kill(group_member_observed=True)
    assert guard._cleanup_compromised
    assert not guard.cleanup_verified
