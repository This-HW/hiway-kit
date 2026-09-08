"""Unit tests for stop-validator.py"""

import json
from pathlib import Path
from types import ModuleType

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    """stop-validator.py는 하이픈 이름이라 import 불가."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "stop_validator", HOOKS_DIR / "stop-validator.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


@pytest.fixture(autouse=True)
def _isolate_tmp_files(tmp_path, monkeypatch):
    """마커/카운터를 tmp_path 기준 경로로 교체 — 실제 /tmp 및 동시 세션 간섭 방지."""
    fake_marker = tmp_path / "claude_validated"
    fake_counter = tmp_path / "claude_stop_retries"
    monkeypatch.setattr(_mod, "VALIDATED_MARKER", fake_marker)
    monkeypatch.setattr(_mod, "RETRY_COUNTER", fake_counter)


def _extract_json(output: str) -> dict:
    """stdout에서 첫 번째 JSON 객체를 추출."""
    start = output.find("{")
    assert start != -1, "stdout에 JSON 출력이 없습니다."
    depth, end = 0, start
    for i, ch in enumerate(output[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    return json.loads(output[start : end + 1])


# ── TC1: no_py_changes ───────────────────────────────────────────
def test_no_py_changes_exits_zero(monkeypatch):
    monkeypatch.setattr(_mod, "get_modified_py_files", list)

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0


# ── TC2a: lint_auto_fixed (stderr 정보 메시지 + exit 0) ───────────
def test_lint_auto_fixed_reports_on_stderr_and_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["file.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (False, "E501 line too long"))
    monkeypatch.setattr(_mod, "auto_fix_lint", lambda files: (True, ["file.py"], ""))
    monkeypatch.setattr(_mod, "check_tests", lambda files: (True, ""))

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    # 정보성 메시지는 stderr로 — stdout은 decision 프로토콜 전용.
    assert "자동 수정" in capsys.readouterr().err


# ── TC2b: lint_auto_fixed (수정 파일이 stderr에 보고) ────────────
def test_lint_auto_fixed_lists_files_on_stderr(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["file.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (False, "E501 error"))
    monkeypatch.setattr(_mod, "auto_fix_lint", lambda files: (True, ["file.py"], ""))
    monkeypatch.setattr(_mod, "check_tests", lambda files: (True, ""))

    with pytest.raises(SystemExit):
        _mod.main()

    assert "file.py" in capsys.readouterr().err


# ── TC3: test_failure (decision:block + exit 0) ──────────────────
def test_test_failure_emits_block_decision(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["app.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (True, ""))
    monkeypatch.setattr(
        _mod, "check_tests", lambda files: (False, "FAILED test_foo - AssertionError")
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    # 네이티브 스키마: decision 필드가 차단 제어, exit 0.
    assert exc_info.value.code == 0
    payload = _extract_json(capsys.readouterr().out)
    assert payload["decision"] == "block"
    assert "test_failure" in payload["reason"]
    assert "FAILED test_foo" in payload["reason"]


# ── TC4: marker_skip — 유효(상태 해시 일치) 마커만 스킵을 유발 ────
def test_marker_skip_exits_zero_and_consumes_marker(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "_worktree_state_hash", lambda: "state-x")
    _mod.VALIDATED_MARKER.write_text("state-x", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert "marker found" in capsys.readouterr().out
    assert not _mod.VALIDATED_MARKER.exists(), "마커 파일이 소비(삭제)되지 않았습니다."


def test_marker_empty_touch_never_skips(monkeypatch, capsys):
    """빈 내용 마커(구버전 touch)는 무효 — 파일 생성만으로 검증을 우회할 수 없다(M-1)."""
    _mod.VALIDATED_MARKER.touch()
    monkeypatch.setattr(_mod, "get_modified_py_files", list)

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert "marker found" not in capsys.readouterr().out
    assert not _mod.VALIDATED_MARKER.exists(), "무효 마커도 소비(삭제)돼야 한다"


def test_marker_symlink_is_rejected(monkeypatch, tmp_path, capsys):
    """심링크 마커는 내용을 읽지 않고 즉시 무효 처리한다(CWE-59, H-1)."""
    target = tmp_path / "attacker_target"
    monkeypatch.setattr(_mod, "_worktree_state_hash", lambda: "state-y")
    target.write_text("state-y", encoding="utf-8")  # 내용이 일치해도 링크면 무효
    _mod.VALIDATED_MARKER.symlink_to(target)
    monkeypatch.setattr(_mod, "get_modified_py_files", list)

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert "marker found" not in capsys.readouterr().out
    assert not _mod.VALIDATED_MARKER.is_symlink(), "심링크 마커는 제거돼야 한다"
    assert target.exists(), "링크 대상 파일을 건드리면 안 된다"


# ── TC5: lint_error (auto-fix 실패 → decision:block) ─────────────
def test_lint_error_when_auto_fix_fails_emits_block(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["bad.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (False, "E999 SyntaxError"))
    monkeypatch.setattr(
        _mod, "auto_fix_lint", lambda files: (False, [], "E999 SyntaxError remains")
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    payload = _extract_json(capsys.readouterr().out)
    assert payload["decision"] == "block"
    assert "lint_error" in payload["reason"]


# ── TC6: max_retries 도달 → block이 아니라 allow (무한 루프 방지) ──
def test_max_retries_exceeded_allows_not_blocks(monkeypatch, capsys):
    """cap 도달 시 block()하면 test_failure↔max_retries 무한 루프가 된다.
    cap = '검증 중단·턴 종료'이므로 allow(exit 0, decision JSON 없음)여야 한다.
    """
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["app.py"])
    _mod.RETRY_COUNTER.write_text(str(_mod.MAX_RETRIES), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert '"decision"' not in out, "cap에서 차단(block) JSON을 내면 안 된다."
    assert not _mod.RETRY_COUNTER.exists(), (
        "max_retries 후 카운터가 리셋되지 않았습니다."
    )


# ── TC7: stop_hook_active=true → 즉시 통과 (네이티브 무한 루프 가드) ──
def test_stop_hook_active_short_circuits(monkeypatch, capsys):
    monkeypatch.setattr(_mod, "_read_input", lambda: {"stop_hook_active": True})
    # 변경 파일/카운터가 차단 조건이어도 stop_hook_active가 우선해 통과해야 한다.
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["app.py"])
    _mod.RETRY_COUNTER.write_text("1", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert '"decision"' not in capsys.readouterr().out


# ── TC8: _read_input — TTY hang 가드 + JSON 파싱 ──────────────────
def test_read_input_returns_empty_on_tty(monkeypatch):
    """수동 실행(TTY)에서 stdin.read()로 멈추지 않고 빈 dict 반환."""

    class _FakeStdin:
        def isatty(self):
            return True

        def read(self):  # 호출되면 안 됨 (호출 시 hang을 의미)
            raise AssertionError("TTY에서 read()를 호출하면 안 된다")

    monkeypatch.setattr("sys.stdin", _FakeStdin())
    assert _mod._read_input() == {}


def test_read_input_parses_json(monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO('{"stop_hook_active": true}'))
    assert _mod._read_input() == {"stop_hook_active": True}


# ── TC9: _session_edited_files — 세션 편집 파일 스코핑 ─────────────
def _write_transcript(tmp_path, edited_paths):
    """tool_use(Edit) 이벤트 + 노이즈 라인(비 tool_use, 깨진 JSON)을 섞은 transcript."""
    lines = [
        json.dumps(
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Edit",
                            "input": {"file_path": str(p)},
                        }
                    ]
                }
            }
        )
        for p in edited_paths
    ]
    lines.append("not valid json")  # 견고성: 깨진 줄 무시
    lines.append(json.dumps({"message": {"content": "plain text"}}))  # content 비리스트
    f = tmp_path / "transcript.jsonl"
    f.write_text("\n".join(lines), encoding="utf-8")
    return f


def test_session_edited_none_without_transcript():
    assert _mod._session_edited_files({}) is None


def test_session_edited_none_when_file_missing(tmp_path):
    data = {"transcript_path": str(tmp_path / "nope.jsonl")}
    assert _mod._session_edited_files(data) is None


def test_session_edited_parses_tool_use(tmp_path):
    edited = _mod.PROJECT_ROOT / "app.py"
    f = _write_transcript(tmp_path, [edited])
    assert _mod._session_edited_files({"transcript_path": str(f)}) == {
        _mod._real(str(edited))
    }


# ── W-012 #3: Bash로 쓴 .py의 명시적 대상만 스코프에 추가(정밀), untracked union ──
def _write_bash_transcript(tmp_path, command, edited=None):
    """Edit 이벤트(옵션) + Bash tool_use 이벤트를 섞은 transcript."""
    lines = []
    if edited:
        lines.append(
            json.dumps(
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Edit",
                                "input": {"file_path": str(edited)},
                            }
                        ]
                    }
                }
            )
        )
    lines.append(
        json.dumps(
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": command},
                        }
                    ]
                }
            }
        )
    )
    f = tmp_path / "transcript.jsonl"
    f.write_text("\n".join(lines), encoding="utf-8")
    return f


def test_bash_py_write_targets_extracts_writes():
    # 명시적 .py write 대상만 정밀 추출 (redirect/tee/sed -i/cp/mv)
    assert "foo.py" in _mod._bash_py_write_targets("cat <<'EOF' > foo.py\nx=1\nEOF")
    assert "pkg/mod.py" in _mod._bash_py_write_targets("sed -i 's/a/b/' pkg/mod.py")
    assert "conf.py" in _mod._bash_py_write_targets("echo 'x=1' >> conf.py")
    assert "b.py" in _mod._bash_py_write_targets("cp a.py b.py")
    assert "out.py" in _mod._bash_py_write_targets("tee out.py < in.txt")


def test_bash_py_write_targets_ignores_reads():
    # 적대적 리뷰 F3: benign redirect/grep은 write 대상이 없어야(오탐 방지)
    assert _mod._bash_py_write_targets("pytest tests/test_x.py -q") == []
    assert _mod._bash_py_write_targets("grep -n 'open(' app.py") == []
    assert _mod._bash_py_write_targets("python app.py > out.log") == []
    assert _mod._bash_py_write_targets("ls -la") == []


def test_bash_py_write_targets_strips_quotes():
    # 적대적 리뷰: `> "config.py"`가 따옴표 포함으로 잡혀 존재하지 않던 버그
    assert "config.py" in _mod._bash_py_write_targets('echo x > "config.py"')
    assert "config.py" in _mod._bash_py_write_targets("echo x > 'config.py'")


def test_session_edited_falls_back_when_only_bash_writes_py(tmp_path):
    """적대적 리뷰 P1: .py를 Bash로만 쓰고(신뢰가능 Edit .py 없음) 정밀추출도 놓친 형태면
    스코핑을 신뢰 못 해 None(전체 dirty 검증)으로 폴백 — false-green 방지."""
    # 문서(.md)만 Edit + .py는 python -c로 opaque하게 씀 → 폴백(None)
    f = _write_bash_transcript(
        tmp_path,
        "python -c \"open('gen.py','w').write(src)\"",
        edited=_mod.PROJECT_ROOT / "README.md",
    )
    assert _mod._session_edited_files({"transcript_path": str(f)}) is None


def test_session_edited_trusts_scope_when_reliable_py_edit(tmp_path):
    """신뢰가능한 .py Edit이 있으면 bash writeish여도 스코핑 유지(폴백 안 함)."""
    edited = _mod.PROJECT_ROOT / "app.py"
    f = _write_bash_transcript(
        tmp_path, "python -c \"open('gen.py','w')\"", edited=edited
    )
    result = _mod._session_edited_files({"transcript_path": str(f)})
    assert result is not None and _mod._real(str(edited)) in result


def test_session_edited_adds_bash_write_target(tmp_path):
    """Bash가 기존 .py를 in-place로 쓰면(sed -i) 그 대상이 스코프에 추가된다(F2)."""
    edited = _mod.PROJECT_ROOT / "app.py"
    f = _write_bash_transcript(tmp_path, "sed -i 's/a/b/' gen.py", edited=edited)
    result = _mod._session_edited_files({"transcript_path": str(f)})
    assert _mod._real(str(edited)) in result
    assert _mod._real("gen.py") in result  # bash write 대상도 포함


def test_session_edited_keeps_scope_on_readonly_bash(tmp_path):
    """읽기 전용 Bash(.py 대상 pytest)는 대상 추가 안 함 → Edit 스코프만 유지(F3)."""
    edited = _mod.PROJECT_ROOT / "app.py"
    f = _write_bash_transcript(tmp_path, "pytest app.py -q", edited=edited)
    assert _mod._session_edited_files({"transcript_path": str(f)}) == {
        _mod._real(str(edited))
    }


def test_main_skips_parallel_session_file(tmp_path, monkeypatch, capsys):
    """사건 재현: 병렬 세션이 dirty 만든 .py는 transcript에 없어 검증에서 제외 → 통과."""
    # git은 parallel 파일이 변경됐다 보고하지만, 이 세션은 docs(.md)만 편집했다.
    monkeypatch.setattr(
        _mod, "get_modified_py_files", lambda: ["scripts/resolve_approval.py"]
    )
    transcript = _write_transcript(tmp_path, [tmp_path / "docs" / "spec.md"])
    monkeypatch.setattr(
        _mod, "_read_input", lambda: {"transcript_path": str(transcript)}
    )

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert '"decision"' not in capsys.readouterr().out  # 차단 없이 통과


def test_main_validates_session_edited_file(tmp_path, monkeypatch):
    """이 세션이 편집한 .py는 스코핑을 통과해 검증 단계로 진입한다."""
    edited = _mod.PROJECT_ROOT / "app.py"
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["app.py"])
    transcript = _write_transcript(tmp_path, [edited])
    monkeypatch.setattr(
        _mod, "_read_input", lambda: {"transcript_path": str(transcript)}
    )
    called = {"lint": False, "tests": False}

    def _fake_lint(files):
        called["lint"] = True
        return True, ""

    def _fake_tests(files):
        called["tests"] = True
        return True, ""

    monkeypatch.setattr(_mod, "check_lint", _fake_lint)
    monkeypatch.setattr(_mod, "check_tests", _fake_tests)

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert called["lint"] and called["tests"], "스코핑 통과 후 검증이 실행돼야 한다"


# ── TC10: check_tests — 편집한 테스트 파일만 스코프 실행 ──────────
def test_check_tests_scopes_to_edited_test_files(tmp_path, monkeypatch):
    """편집한 test_*.py 만 pytest 인자로 넘긴다(전체 스위트 실행 금지)."""
    test_file = tmp_path / "test_thing.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    monkeypatch.setattr(_mod, "_resolve_paths", lambda files: [str(test_file)])

    captured = {}

    def _fake_run(cmd, **kw):
        captured["cmd"] = cmd

        class _R:
            returncode = 0
            stdout = ""
            stderr = ""

        return _R()

    monkeypatch.setattr(_mod.subprocess, "run", _fake_run)
    passed, _ = _mod.check_tests([str(test_file)])

    assert passed
    assert str(test_file) in captured["cmd"], "변경 테스트 파일이 pytest 인자에 없다"


# ── TC10b: check_tests — 소스만 편집 시 pytest 실행 없이 스킵 ──────
def test_check_tests_source_only_skips_without_running_pytest(tmp_path, monkeypatch):
    """편집한 테스트 파일이 없으면(소스만 변경) 전체 스위트를 돌리지 않고
    즉시 통과한다 — 매 턴 끝 지연이 스위트 크기에 비례하지 않게(이번 버그의 근본 차단).
    전체 회귀는 CI/`/test`에 위임."""
    monkeypatch.setattr(
        _mod, "_resolve_paths", lambda files: [str(tmp_path / "app.py")]
    )

    def _boom(*a, **k):
        raise AssertionError("소스만 변경 시 pytest를 실행하면 안 된다")

    monkeypatch.setattr(_mod.subprocess, "run", _boom)
    passed, output = _mod.check_tests(["app.py"])

    assert passed is True and output == ""


# ── TC11: check_tests — 타임아웃은 차단이 아니라 비차단 통과 ───────
def test_check_tests_timeout_is_non_blocking(tmp_path, monkeypatch, capsys):
    """스코프 실행이 타임아웃나도 (False, ...) 가 아니라 (True, "") 를 반환해
    main()이 test_failure로 block 하지 않는다(오탐 차단 방지)."""
    test_file = tmp_path / "test_slow.py"
    test_file.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    monkeypatch.setattr(_mod, "_resolve_paths", lambda files: [str(test_file)])

    def _timeout_run(cmd, **kw):
        raise _mod.subprocess.TimeoutExpired(cmd, kw.get("timeout", 60))

    monkeypatch.setattr(_mod.subprocess, "run", _timeout_run)
    passed, output = _mod.check_tests([str(test_file)])

    assert passed is True, "타임아웃을 실패로 보고하면 안 된다(오탐 차단)"
    assert output == ""
    assert "timeout" in capsys.readouterr().err.lower(), "비차단 WARN을 내야 한다"


# ── TC12: check_tests — 실제 실패는 여전히 차단 신호 ──────────────
def test_check_tests_real_failure_still_blocks(tmp_path, monkeypatch):
    """타임아웃과 달리 실제 실패(returncode!=0,5)는 (False, output) 유지."""
    test_file = tmp_path / "test_thing.py"
    test_file.write_text("def test_no():\n    assert False\n", encoding="utf-8")
    monkeypatch.setattr(_mod, "_resolve_paths", lambda files: [str(test_file)])

    def _fail_run(cmd, **kw):
        class _R:
            returncode = 1
            stdout = "FAILED test_thing::test_no"
            stderr = ""

        return _R()

    monkeypatch.setattr(_mod.subprocess, "run", _fail_run)
    passed, output = _mod.check_tests([str(test_file)])

    assert passed is False
    assert "FAILED" in output


# ── TC13: _test_timeout — 환경변수 설정/폴백 ──────────────────────
def test_test_timeout_default(monkeypatch):
    monkeypatch.delenv("CLAUDE_STOP_TEST_TIMEOUT", raising=False)
    assert _mod._test_timeout() == 60


def test_test_timeout_env_override(monkeypatch):
    monkeypatch.setenv("CLAUDE_STOP_TEST_TIMEOUT", "300")
    assert _mod._test_timeout() == 300


@pytest.mark.parametrize("bad", ["0", "-5", "abc", ""])
def test_test_timeout_invalid_falls_back(monkeypatch, bad):
    monkeypatch.setenv("CLAUDE_STOP_TEST_TIMEOUT", bad)
    assert _mod._test_timeout() == 60


# ── TC14: 마커 내용 검증 — 병렬 세션 크로스 오염 방지 (W-011) ──────
def test_marker_with_matching_state_hash_skips(monkeypatch, capsys):
    """마커 내용이 현재 작업트리 상태 해시와 일치하면 검증을 스킵한다."""
    monkeypatch.setattr(_mod, "_worktree_state_hash", lambda: "abc123")
    _mod.VALIDATED_MARKER.write_text("abc123", encoding="utf-8")
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["app.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (False, "여기 오면 안 됨"))

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert "marker found" in capsys.readouterr().out
    assert not _mod.VALIDATED_MARKER.exists()


def test_marker_with_stale_state_hash_does_not_skip(monkeypatch, capsys):
    """검증 후 파일이 바뀌었거나 다른 세션 상태의 마커는 스킵을 유발하지 않는다."""
    monkeypatch.setattr(_mod, "_worktree_state_hash", lambda: "current-state")
    _mod.VALIDATED_MARKER.write_text("other-session-state", encoding="utf-8")
    monkeypatch.setattr(_mod, "get_modified_py_files", list)

    with pytest.raises(SystemExit) as exc_info:
        _mod.main()

    assert exc_info.value.code == 0
    assert "marker found" not in capsys.readouterr().out, (
        "무효 마커로 검증을 스킵하면 안 된다"
    )
    assert not _mod.VALIDATED_MARKER.exists(), "무효 마커도 소비(삭제)돼야 한다"


# ── TC15: retry 카운터 세션 스코프 (W-011) ────────────────────────
def test_session_scope_isolates_retry_counter():
    """session_id가 있으면 카운터 경로가 세션별로 분리된다."""
    base = _mod.RETRY_COUNTER
    try:
        _mod._apply_session_scope("session-a")
        path_a = _mod.RETRY_COUNTER
        _mod.RETRY_COUNTER = base
        _mod._apply_session_scope("session-b")
        path_b = _mod.RETRY_COUNTER
        _mod.RETRY_COUNTER = base
        _mod._apply_session_scope(None)
        path_none = _mod.RETRY_COUNTER

        assert path_a != base and path_b != base
        assert path_a != path_b, "세션이 다르면 카운터 경로도 달라야 한다"
        assert path_none == base, "session_id 부재 시 기존 경로 유지(하위호환)"
    finally:
        _mod.RETRY_COUNTER = base


def test_parallel_session_retry_counters_do_not_collide(monkeypatch, capsys):
    """세션 B의 카운터가 max여도 세션 A(session_id 다름)는 영향받지 않는다."""
    base = _mod.RETRY_COUNTER
    # 세션 B가 남긴 카운터 (다른 세션 스코프)
    sid_b = __import__("hashlib").md5(b"session-b").hexdigest()[:8]
    counter_b = base.with_name(f"{base.name}_{sid_b}")
    counter_b.write_text(str(_mod.MAX_RETRIES), encoding="utf-8")

    monkeypatch.setattr(_mod, "_read_input", lambda: {"session_id": "session-a"})
    monkeypatch.setattr(_mod, "get_modified_py_files", lambda: ["app.py"])
    monkeypatch.setattr(_mod, "check_lint", lambda files: (True, ""))
    monkeypatch.setattr(_mod, "check_tests", lambda files: (True, ""))

    try:
        with pytest.raises(SystemExit) as exc_info:
            _mod.main()

        assert exc_info.value.code == 0
        # 세션 A는 정상 검증 경로를 탔고(cap 조기중단 아님), B의 카운터는 보존.
        assert "자동 수정" not in capsys.readouterr().out
        assert counter_b.exists(), "다른 세션의 카운터를 건드리면 안 된다"
    finally:
        counter_b.unlink(missing_ok=True)
        _mod.RETRY_COUNTER = base


# ── TC16: stop_hook_active + session_id → 세션 스코프 카운터가 리셋 (ATK-001) ──
def test_stop_hook_active_resets_session_scoped_counter(monkeypatch):
    """세션 스코프 적용이 stop_hook_active 가드보다 늦으면, 이 경로의 reset이
    repo 공유 카운터를 지우고 세션 카운터는 누적돼 cap 도달 후 실제 실패가
    조용히 통과한다(fail-open). 스코프 적용이 반드시 선행돼야 한다."""
    base = _mod.RETRY_COUNTER
    sid = __import__("hashlib").md5(b"session-x").hexdigest()[:8]
    session_counter = base.with_name(f"{base.name}_{sid}")
    session_counter.write_text("1", encoding="utf-8")

    monkeypatch.setattr(
        _mod,
        "_read_input",
        lambda: {"stop_hook_active": True, "session_id": "session-x"},
    )

    try:
        with pytest.raises(SystemExit) as exc_info:
            _mod.main()

        assert exc_info.value.code == 0
        assert not session_counter.exists(), (
            "stop_hook_active 경로의 reset은 세션 스코프 카운터를 지워야 한다 "
            "(repo 공유 카운터가 아니라)"
        )
    finally:
        session_counter.unlink(missing_ok=True)
        _mod.RETRY_COUNTER = base


# ── TC17: _write_nofollow — 심링크 카운터를 따라가지 않음 (H-1) ────
def test_increment_retry_does_not_follow_symlink(tmp_path):
    """RETRY_COUNTER가 심링크로 선점돼 있어도 링크 대상 파일을 덮어쓰지 않는다."""
    target = tmp_path / "victim_file"
    target.write_text("victim data", encoding="utf-8")
    base = _mod.RETRY_COUNTER
    base.unlink(missing_ok=True)
    base.symlink_to(target)

    try:
        _mod.increment_retry()
        assert target.read_text(encoding="utf-8") == "victim data", (
            "심링크 대상 파일이 덮어써졌다 (CWE-59)"
        )
        assert not _mod.RETRY_COUNTER.is_symlink(), (
            "os.replace가 심링크 자체를 교체해야 한다"
        )
        assert _mod.get_retry_count() == 1
    finally:
        _mod.RETRY_COUNTER.unlink(missing_ok=True)


# ── TC18: 지문이 검증 스코프 내용을 반영 (F1) — untracked .py 내용 변경 감지 ──
def _git_init(tmp_path):
    import subprocess as sp

    env = {
        **__import__("os").environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }

    def g(*a):
        sp.run(
            ["git", *a],
            cwd=tmp_path,
            env=env,
            check=True,
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )

    g("init")
    g("commit", "--allow-empty", "-m", "root")
    return g


def test_fingerprint_detects_untracked_py_content_change(tmp_path, monkeypatch):
    """이미 untracked인 .py의 내용을 바꾸면 지문이 달라져야 한다(F1 우회 차단).
    porcelain 기반 옛 구현은 경로만 봐서 이 변경을 놓쳤다."""
    _git_init(tmp_path)
    monkeypatch.setattr(_mod, "PROJECT_ROOT", tmp_path)
    f = tmp_path / "new_mod.py"
    f.write_text("x = 1\n", encoding="utf-8")  # untracked
    h1 = _mod._worktree_state_hash()
    assert h1, "커밋이 있으므로 지문이 계산돼야 한다"
    f.write_text(
        "x = 1\nBAD SYNTAX(\n", encoding="utf-8"
    )  # 내용만 변경, 여전히 untracked
    h2 = _mod._worktree_state_hash()
    assert h1 != h2, "untracked .py 내용 변경이 지문에 반영돼야 한다"


def test_fingerprint_stable_across_non_py_change(tmp_path, monkeypatch):
    """.py 아닌 파일(review-results.md 등) 변경은 지문에 영향을 주지 않는다(F2)."""
    _git_init(tmp_path)
    monkeypatch.setattr(_mod, "PROJECT_ROOT", tmp_path)
    (tmp_path / "app.py").write_text("y = 2\n", encoding="utf-8")
    h1 = _mod._worktree_state_hash()
    (tmp_path / "review-results.md").write_text("# report\n", encoding="utf-8")
    h2 = _mod._worktree_state_hash()
    assert h1 == h2, "비 .py 파일 변경으로 마커가 무효화되면 안 된다"


def test_fingerprint_empty_before_first_commit(tmp_path, monkeypatch):
    """최초 커밋 전(unborn HEAD)에는 '' 반환 → 마커 보수적 무효(F3)."""
    import subprocess as sp

    sp.run(
        ["git", "init"], cwd=tmp_path, check=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL
    )
    monkeypatch.setattr(_mod, "PROJECT_ROOT", tmp_path)
    assert _mod._worktree_state_hash() == ""


# ── TC19: 원자적 consume — 두 번째 소비자는 검증 경로로 폴백 (F8) ──
def test_consume_marker_is_atomic(monkeypatch):
    """os.rename 기반 claim으로 첫 호출만 마커를 가져가고, 두 번째는 False."""
    monkeypatch.setattr(_mod, "_worktree_state_hash", lambda: "s")
    _mod.VALIDATED_MARKER.write_text("s", encoding="utf-8")
    first = _mod._consume_marker_if_valid()
    second = _mod._consume_marker_if_valid()
    assert first is True and second is False, "마커는 정확히 한 번만 소비돼야 한다"


# ── TC20: entry() fail-safe — 예기치 못한 예외는 통과(F4) ──
def test_entry_fail_safe_on_unexpected_error(monkeypatch, capsys):
    """main()이 PermissionError(타 소유 상태파일 접근 등)를 던져도 entry()가
    트레이스백으로 죽지 않고 exit 0으로 통과시킨다(안전망은 fail-safe)."""

    def _boom():
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(_mod, "main", _boom)
    with pytest.raises(SystemExit) as exc_info:
        _mod.entry()
    assert exc_info.value.code == 0
    assert "unexpected error" in capsys.readouterr().err


def test_entry_passes_through_normal_exit(monkeypatch):
    """정상 경로의 SystemExit(allow/block)은 entry()가 삼키지 않고 전파한다."""

    def _normal():
        raise SystemExit(0)

    monkeypatch.setattr(_mod, "main", _normal)
    with pytest.raises(SystemExit) as exc_info:
        _mod.entry()
    assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# eval fixture 제외 (W-014 T-B — fixture는 의도적 red 테스트 데이터)
# ---------------------------------------------------------------------------


def test_is_eval_fixture_paths():
    sv = _mod
    assert sv._is_eval_fixture("evals/scenarios/fix-bugs/off-by-one/fixture/test_x.py")
    assert not sv._is_eval_fixture("evals/run.py")
    assert not sv._is_eval_fixture("evals/tests/test_runner.py")
    assert not sv._is_eval_fixture("plugins/common/hooks/utils.py")


def test_get_modified_py_files_excludes_eval_fixtures(monkeypatch):
    """untracked eval fixture .py는 검증 스코프에서 제외되어야 한다."""
    sv = _mod

    class R:
        def __init__(self, out):
            self.stdout = out
            self.returncode = 0

    outputs = {
        "diff": "evals/run.py\n",
        "cached": "",
        "ls-files": "evals/scenarios/fix-bugs/off-by-one/fixture/test_math.py\nplugins/common/hooks/new.py\n",
    }

    def fake_run(cmd, **kw):
        if "ls-files" in cmd:
            return R(outputs["ls-files"])
        if "--cached" in cmd:
            return R(outputs["cached"])
        return R(outputs["diff"])

    monkeypatch.setattr(sv.subprocess, "run", fake_run)
    files = sorted(sv.get_modified_py_files())
    assert files == ["evals/run.py", "plugins/common/hooks/new.py"]


def test_is_eval_fixture_narrowed_to_fixture_segment():
    """제외는 /fixture/ 하위만 — scenarios 루트의 실코드는 검증 대상 유지 (재감사 R2/ATK-005)."""
    sv = _mod
    assert sv._is_eval_fixture("evals/scenarios/fix-bugs/off-by-one/fixture/stats.py")
    assert not sv._is_eval_fixture("evals/scenarios/fix-bugs/off-by-one/helper.py")
    assert not sv._is_eval_fixture("evals/scenarios/helper.py")
