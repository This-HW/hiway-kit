"""HIWAY_KIT_DISABLE_HOOKS — 훅을 끄는 공식 스위치.

외부 설치 보고(2026-11-09)에서 분석이 권한 우회책은 "캐시의 hooks.json 에서 Stop 절을 지워라"였다 —
업데이트로 조용히 되돌아간다. 프로젝트 `.claude/settings.json` 의 `env` 가 플러그인 훅 프로세스까지
전달되므로(같은 날 실측) 그 자리에 넣는 환경 변수 하나로 끈다. 각 훅을 **실제 프로세스로** 띄우고,
스위치가 없을 때 원래 동작이 나는지(양성 대조)도 함께 본다.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "common"
HOOKS = PLUGIN / "hooks"


def _run(script: Path, payload: dict, tmp_path: Path, disable: str | None) -> subprocess.CompletedProcess:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "CLAUDE_PROJECT_DIR": str(tmp_path / "proj"),
    }
    if disable is not None:
        env["HIWAY_KIT_DISABLE_HOOKS"] = disable
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload), capture_output=True, text=True,
        cwd=str(tmp_path / "proj"), env=env, timeout=60, check=False,
    )


@pytest.fixture()
def proj(tmp_path: Path) -> Path:
    (tmp_path / "home").mkdir()
    root = tmp_path / "proj"
    (root / ".git").mkdir(parents=True)
    return root


def test_protect_sensitive_switch(proj: Path, tmp_path: Path) -> None:
    payload = {"tool_name": "Read", "tool_input": {"file_path": str(proj / ".env")}}
    assert _run(HOOKS / "protect-sensitive.py", payload, tmp_path, None).returncode == 2
    assert _run(HOOKS / "protect-sensitive.py", payload, tmp_path, "protect-sensitive").returncode == 0
    assert _run(HOOKS / "protect-sensitive.py", payload, tmp_path, "all").returncode == 0
    # 다른 훅 이름만 끄면 그대로 막는다
    assert _run(HOOKS / "protect-sensitive.py", payload, tmp_path, "auto-format").returncode == 2


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")
def test_auto_format_switch(proj: Path, tmp_path: Path) -> None:
    (proj / "ruff.toml").write_text("")
    target = proj / "m.py"
    source = "x=1\n"
    target.write_text(source)
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(target)}}
    _run(HOOKS / "auto-format.py", payload, tmp_path, "auto-format")
    assert target.read_text() == source
    _run(HOOKS / "auto-format.py", payload, tmp_path, None)
    assert target.read_text() == "x = 1\n"


def test_session_start_switch(proj: Path, tmp_path: Path) -> None:
    on = _run(HOOKS / "session-start.py", {}, tmp_path, None)
    assert on.returncode == 0 and json.loads(on.stdout)["hookSpecificOutput"]["additionalContext"]
    off = _run(HOOKS / "session-start.py", {}, tmp_path, "session-start")
    assert off.returncode == 0 and off.stdout.strip() == ""


def test_session_check_switch(proj: Path, tmp_path: Path) -> None:
    off = _run(PLUGIN / "setup" / "session-check.py", {}, tmp_path, "session-check")
    assert off.returncode == 0 and off.stdout.strip() == ""


def test_stop_validator_switch_touches_no_state(monkeypatch) -> None:
    """꺼져 있으면 재시도 카운터도 건드리지 않는다 — allow() 의 리셋이 세션 스코프 적용 전에
    돌면 공유 카운터를 지운다(ATK-001)."""
    spec = importlib.util.spec_from_file_location("stop_validator_switch", HOOKS / "stop-validator.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setenv("HIWAY_KIT_DISABLE_HOOKS", "stop-validator")

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("disabled hook touched retry state")

    monkeypatch.setattr(mod, "reset_retry", _forbidden)
    monkeypatch.setattr(mod, "_apply_session_scope", _forbidden)
    with patch("sys.stdin", StringIO(json.dumps({"session_id": "s"}))), pytest.raises(SystemExit) as stop:
        mod.main()
    assert stop.value.code == 0


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")
def test_auto_format_respects_project_ruff_exclude(proj: Path, tmp_path: Path) -> None:
    """ruff 는 경로를 직접 받으면 설정의 exclude 를 무시한다 — 프로젝트가 뺀 파일도 고치면 안 된다."""
    (proj / "ruff.toml").write_text('extend-exclude = ["vendor"]\n')
    (proj / "vendor").mkdir()
    target = proj / "vendor" / "lib.py"
    source = "import os, sys\nx=1\n"
    target.write_text(source)
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(target)}}
    _run(HOOKS / "auto-format.py", payload, tmp_path, None)
    assert target.read_text() == source
