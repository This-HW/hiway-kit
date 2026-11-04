from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
from bounded_process import ProcessBudget

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX process groups and pipe selectors")


def command(source):
    return [sys.executable, "-B", "-c", source]


@pytest.fixture
def processes(monkeypatch):
    """Track and clean up only subprocesses started in their own process group."""
    real_popen = subprocess.Popen
    started = []

    def popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        if kwargs.get("start_new_session"):
            started.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", popen)
    yield started
    for process in started:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)


def assert_stopped(pid):
    # A killed orphan can briefly be a zombie until init reaps it on Linux.
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True,
                           text=True, timeout=2, check=False).stdout.strip()
    assert not state or state.startswith("Z"), (pid, state)


@pytest.mark.parametrize("limit", [0, 1, 1000])
def test_exact_byte_budget_accepts_eof(limit):
    result = ProcessBudget(2, limit).run(command(f"import os; os.write(1, b'x' * {limit})"))
    assert result.stdout == b"x" * limit
    assert result.stderr == b""
    assert result.returncode == 0


def test_one_over_budget_rejected(processes):
    with pytest.raises(ValueError, match="output exceeded 1000 bytes"):
        ProcessBudget(2, 1000).run(command("import os; os.write(2, b'x' * 1001)"))
    assert processes[0].poll() is not None


def test_concurrent_stdout_and_stderr_are_drained():
    size = 128 * 1024
    source = (
        "import os, threading\n"
        f"t = threading.Thread(target=lambda: os.write(2, b'e' * {size}))\n"
        "t.start()\n"
        f"os.write(1, b'o' * {size})\n"
        "t.join()\n"
    )
    result = ProcessBudget(2, size * 2).run(command(source))
    assert result.stdout == b"o" * size
    assert result.stderr == b"e" * size


def test_stdout_stderr_share_one_budget():
    with pytest.raises(ValueError, match="output exceeded 1000 bytes"):
        ProcessBudget(2, 1000).run(command("import os; os.write(1, b'o' * 600); os.write(2, b'e' * 600)"))


def test_multiple_commands_share_remaining_bytes():
    budget = ProcessBudget(2, 10)
    assert budget.run(command("import os; os.write(1, b'abc')")).stdout == b"abc"
    assert budget.remaining_bytes == 7
    assert budget.run(command("import os; os.write(2, b'd' * 7)")).stderr == b"d" * 7
    assert budget.remaining_bytes == 0
    with pytest.raises(ValueError, match="output exceeded"):
        budget.run(command("print('x')"))


def test_output_overflow_after_leader_exits_preserves_budget_error(monkeypatch):
    read = os.read

    def delayed_read(*args):
        chunk = read(*args)
        # Let the short-lived leader exit before overflow cleanup. On macOS a
        # group containing only an unreaped leader returns EPERM to killpg.
        if chunk:
            time.sleep(.1)
        return chunk

    monkeypatch.setattr(os, "read", delayed_read)
    with pytest.raises(ValueError, match="output exceeded"):
        ProcessBudget(2, 1).run(command("print('overflow')"))


@pytest.mark.parametrize("close_pipes", [False, True])
def test_deadline_includes_wait_after_pipe_eof(processes, close_pipes):
    source = "import os, time\n"
    if close_pipes:
        source += "os.close(1); os.close(2)\n"
    source += "time.sleep(60)\n"
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        ProcessBudget(0.2, 1000).run(command(source))
    assert time.monotonic() - start < 2
    assert processes[0].poll() is not None


def test_deadline_checked_while_output_is_ready(processes):
    source = "import os, time\nwhile True:\n os.write(1, b'x')\n time.sleep(0.001)\n"
    with pytest.raises(subprocess.TimeoutExpired):
        ProcessBudget(0.2, 1024 * 1024).run(command(source))
    assert processes[0].poll() is not None


def test_stage_timeout_cannot_extend_request_deadline(processes):
    budget = ProcessBudget(0.3, 1000)
    budget.run(command("import time; time.sleep(0.1)"))
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        budget.run(command("import time; time.sleep(60)"), timeout=10)
    assert time.monotonic() - start < 1
    assert all(process.poll() is not None for process in processes)


@pytest.mark.parametrize("case", ["timeout", "overflow", "leader-exited", "success"])
def test_descendants_cleaned_even_after_leader_exit(tmp_path, processes, case):
    pidfile = tmp_path / "child.pid"
    child = (
        "import os, signal, time\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(60)\n"
    )
    redirect = ", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL" if case == "success" else ""
    source = (
        "import os, subprocess, sys, time\n"
        "from pathlib import Path\n"
        f"subprocess.Popen([sys.executable, '-B', '-c', {child!r}]{redirect})\n"
        f"while not Path({str(pidfile)!r}).exists(): time.sleep(0.001)\n"
    )
    if case == "overflow":
        source += "while True: os.write(2, b'x' * 4096)\n"
    elif case == "timeout":
        source += "time.sleep(60)\n"
    start = time.monotonic()
    try:
        budget = ProcessBudget(0.5, 1000)
        if case == "success":
            assert budget.run(command(source)).returncode == 0
        else:
            expected = ValueError if case == "overflow" else subprocess.TimeoutExpired
            with pytest.raises(expected):
                budget.run(command(source))
        assert time.monotonic() - start < 2
        assert processes[0].poll() is not None
        assert pidfile.exists()
        child_pid = int(pidfile.read_text())
        # Give the kernel a moment to report delivery of SIGKILL.
        for _ in range(50):
            try:
                assert_stopped(child_pid)
                break
            except AssertionError:
                time.sleep(0.01)
        else:
            assert_stopped(child_pid)
    finally:
        if pidfile.exists():
            with suppress(ProcessLookupError):
                os.kill(int(pidfile.read_text()), signal.SIGKILL)


def test_expired_budget_does_not_launch(processes):
    budget = ProcessBudget(2, 1000)
    budget.deadline = time.monotonic() - 1
    with pytest.raises(subprocess.TimeoutExpired):
        budget.run(command("raise SystemExit(99)"))
    assert processes == []


def test_child_environment_has_only_explicit_defaults(monkeypatch):
    import json

    banned = ["INTEL_TEST_API_TOKEN", "NODE_OPTIONS", "PYTHONPATH", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES",
              "RUSTC_WRAPPER", "BASH_ENV", "GIT_CONFIG_COUNT", "CODEX_HOME"]
    for name in banned:
        monkeypatch.setenv(name, "fixture-value")
    monkeypatch.setenv("GOTOOLCHAIN", "auto")
    monkeypatch.setenv("LANG", "C")
    result = ProcessBudget(3, 16384).run(command("import json,os; print(json.dumps(dict(os.environ)))"))
    env = json.loads(result.stdout)
    assert not set(banned) & env.keys()
    assert env["GOTOOLCHAIN"] == "local"
    assert env["LANG"] == "C"
    assert env["HOME"] == os.environ["HOME"]
    assert env["PATH"] == os.environ["PATH"]


def test_toolchain_environment_preserves_configuration_and_denies_secrets(monkeypatch):
    import json

    allowed = ["GOPRIVATE", "GOFLAGS", "GOPROXY", "CARGO_NET_OFFLINE", "CARGO_HOME",
               "RUSTUP_HOME", "RUSTUP_TOOLCHAIN", "VIRTUAL_ENV", "CONDA_PREFIX",
               "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH",
               "PKG_CONFIG_PATH", "SDKROOT", "DEVELOPER_DIR", "USER", "LOGNAME", "SHELL"]
    denied = ["CARGO_REGISTRY_TOKEN", "CARGO_REGISTRIES_PRIVATE_TOKEN", "GO_SECRET",
              "RUSTUP_PASSWORD", "CONDA_API_KEY", "go_private_token", "cargo_secret",
              "rustup_password", "conda_api_key", "ld_preload", "dyld_library_path",
              "node_options", "pythonpath", "pythonstartup", "bash_env", "env",
              "git_config_count", "rustc_wrapper", "UNRELATED_SETTING"]
    for name in allowed + denied:
        monkeypatch.setenv(name, "fixture-value")
    monkeypatch.setenv("GOTOOLCHAIN", "auto")
    result = ProcessBudget(3, 32768).run(command("import json,os; print(json.dumps(dict(os.environ)))"))
    assert result.returncode == 0
    env = json.loads(result.stdout)
    assert {name: env.get(name) for name in allowed} == dict.fromkeys(allowed, "fixture-value")
    assert not set(denied) & env.keys()
    assert env["GOTOOLCHAIN"] == "local"
