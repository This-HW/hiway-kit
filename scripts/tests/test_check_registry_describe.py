"""check_registry_describe.py 테스트 (26-17, D-42·D-44·D-48·D-49·D-50)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from module_loader import load_module_by_path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
FIXTURE = SCRIPTS_DIR / "tests" / "fixtures" / "fake_registry.py"

_mod = load_module_by_path(
    SCRIPTS_DIR / "check_registry_describe.py", "check_registry_describe"
)


def _fake_command(mode: str) -> list[str]:
    """mode를 env로 넘기지 않고 argv로 인코딩 — 병렬 테스트에서 env 오염을 피한다."""
    return [sys.executable, str(FIXTURE), f"--mode={mode}"]


# fake_registry.py는 env로 모드를 받으므로, argv 전달을 위한 얇은 셸 래퍼 대신
# 여기서 subprocess env를 직접 구성해 invoke_describe를 호출한다.
def _run_with_mode(mode: str, monkeypatch):
    monkeypatch.setenv("FAKE_REGISTRY_MODE", mode)
    return _mod.invoke_describe([sys.executable, str(FIXTURE)])


class TestPointerLoading:
    def test_rejects_url_field(self, tmp_path):
        p = tmp_path / "registry.json"
        p.write_text(json.dumps({"url": "http://localhost:9"}))
        try:
            _mod.load_pointer(p)
            raise AssertionError("url 포인터가 거절되지 않았다")
        except _mod.ProbeError as e:
            assert "url" in str(e)

    def test_accepts_command_pointer(self, tmp_path):
        p = tmp_path / "registry.json"
        p.write_text(json.dumps({"command": ["/usr/bin/env", "true"]}))
        assert _mod.load_pointer(p) == ["/usr/bin/env", "true"]

    def test_rejects_missing_command(self, tmp_path):
        p = tmp_path / "registry.json"
        p.write_text(json.dumps({"notes": "no command here"}))
        try:
            _mod.load_pointer(p)
            raise AssertionError("command 없는 포인터가 거절되지 않았다")
        except _mod.ProbeError:
            pass

    def test_rejects_invalid_json(self, tmp_path):
        p = tmp_path / "registry.json"
        p.write_text("{ broken")
        try:
            _mod.load_pointer(p)
            raise AssertionError("깨진 JSON 포인터가 거절되지 않았다")
        except _mod.ProbeError:
            pass

    def test_returned_fail_url_pointer(self, tmp_path):
        """되돌려-FAIL: url을 넣으면 거절, 지우면 통과한다(수용 48)."""
        p = tmp_path / "registry.json"
        p.write_text(json.dumps({"command": ["x"], "url": "http://x"}))
        try:
            _mod.load_pointer(p)
            raise AssertionError("url이 있는데 통과했다")
        except _mod.ProbeError:
            pass
        p.write_text(json.dumps({"command": ["x"]}))
        assert _mod.load_pointer(p) == ["x"]


class TestSchemaValidation:
    def test_valid_schema_passes(self):
        response = {
            "verbs": [{"name": "a", "args": [], "effect": "read"}],
        }
        assert _mod.validate_schema(response) == []

    def test_missing_verbs_key_fails(self):
        assert _mod.validate_schema({}) != []

    def test_missing_args_fails(self):
        response = {"verbs": [{"name": "a", "effect": "read"}]}
        errors = _mod.validate_schema(response)
        assert errors and "args" in errors[0]

    def test_missing_name_fails(self):
        response = {"verbs": [{"args": [], "effect": "read"}]}
        errors = _mod.validate_schema(response)
        assert errors and "name" in errors[0]


class TestEffectClassification:
    def test_declared_read(self):
        assert _mod.classify_effect({"effect": "read"}) == "read"

    def test_declared_write(self):
        assert _mod.classify_effect({"effect": "write"}) == "write"

    def test_undeclared_defaults_write(self):
        assert _mod.classify_effect({}) == "write"

    def test_garbage_value_defaults_write(self):
        assert _mod.classify_effect({"effect": "readish"}) == "write"

    def test_idempotent_undeclared_is_false(self):
        assert _mod.classify_idempotent({}) is False

    def test_idempotent_declared_true(self):
        assert _mod.classify_idempotent({"idempotent": True}) is True

    def test_idempotent_non_bool_is_false(self):
        assert _mod.classify_idempotent({"idempotent": "yes"}) is False


class TestChildExposure:
    def test_only_declared_read_exposed(self):
        verbs = [
            {"name": "a", "effect": "read"},
            {"name": "b", "effect": "write"},
            {"name": "c"},  # 미선언
        ]
        assert _mod.child_exposed_verbs(verbs) == ["a"]

    def test_undeclared_not_in_exposed_set(self):
        """수용 44: effect 미선언 동사가 자식 노출 집합에 들어가면 안 된다."""
        verbs = [{"name": "mystery"}, {"name": "safe", "effect": "read"}]
        assert _mod.check_undeclared_not_exposed(verbs) == []

    def test_undeclared_effect_verbs_listed(self):
        verbs = [{"name": "a", "effect": "read"}, {"name": "b"}]
        assert _mod.undeclared_effect_verbs(verbs) == ["b"]


class TestFreshness:
    def test_match(self):
        assert _mod.classify_freshness("abc", "abc") == "match"

    def test_mismatch(self):
        assert _mod.classify_freshness("abc", "def") == "mismatch"

    def test_undeclared(self):
        assert _mod.classify_freshness(None, "abc") == "undeclared"

    def test_unknown_when_no_repo_head(self):
        assert _mod.classify_freshness("abc", None) == "unknown"


class TestBootCommitPattern:
    def test_no_history_file_returns_false(self, tmp_path):
        assert _mod.detect_boot_commit_pattern(tmp_path / "missing.jsonl") is False

    def test_static_head_with_varying_actual_is_flagged(self, tmp_path):
        hist = tmp_path / "history.jsonl"
        for actual in ("c1", "c2", "c3"):
            _mod.record_observation(hist, "boot-sha", actual)
        assert _mod.detect_boot_commit_pattern(hist, streak_threshold=3) is True

    def test_matching_head_is_not_flagged(self, tmp_path):
        hist = tmp_path / "history.jsonl"
        for c in ("c1", "c2", "c3"):
            _mod.record_observation(hist, c, c)
        assert _mod.detect_boot_commit_pattern(hist, streak_threshold=3) is False

    def test_below_threshold_not_flagged(self, tmp_path):
        hist = tmp_path / "history.jsonl"
        _mod.record_observation(hist, "boot-sha", "c1")
        _mod.record_observation(hist, "boot-sha", "c2")
        assert _mod.detect_boot_commit_pattern(hist, streak_threshold=3) is False

    def test_returned_fail_pattern_then_recovery(self, tmp_path):
        """되돌려-FAIL 정신: 고정 head 관측을 쌓으면 탐지, declaredHead가 실제와
        맞춰지기 시작하면(정상화) 새 윈도우에서 더는 탐지되지 않는다."""
        hist = tmp_path / "history.jsonl"
        for actual in ("c1", "c2", "c3"):
            _mod.record_observation(hist, "boot-sha", actual)
        assert _mod.detect_boot_commit_pattern(hist, streak_threshold=3) is True
        for actual in ("c4", "c5", "c6"):
            _mod.record_observation(hist, actual, actual)  # 이제 정확히 보고
        assert _mod.detect_boot_commit_pattern(hist, streak_threshold=3) is False


class TestFakeRegistryIntegration:
    """실제 서브프로세스로 가짜 파사드를 호출하는 통합 테스트."""

    def test_good_facade_conforms(self, monkeypatch):
        response, error = _run_with_mode("good", monkeypatch)
        assert error is None
        ok, lines = _mod.evaluate(response, _mod.current_git_head(), None)
        assert ok, lines

    def test_missing_args_facade_fails(self, monkeypatch):
        response, error = _run_with_mode("missing_args", monkeypatch)
        assert error is None
        ok, _lines = _mod.evaluate(response, _mod.current_git_head(), None)
        assert not ok

    def test_undeclared_effect_is_not_a_failure(self, monkeypatch):
        """effect 미선언 자체는 통과(fail-closed로 write 처리·보고)."""
        response, error = _run_with_mode("undeclared_effect", monkeypatch)
        assert error is None
        ok, _lines = _mod.evaluate(response, _mod.current_git_head(), None)
        assert ok

    def test_bad_json_triggers_full_fallback(self, monkeypatch):
        response, error = _run_with_mode("bad_json", monkeypatch)
        assert response is None
        assert error is not None

    def test_nonzero_exit_triggers_full_fallback(self, monkeypatch):
        response, error = _run_with_mode("nonzero_exit", monkeypatch)
        assert response is None
        assert error is not None

    def test_head_mismatch_is_warning_not_failure(self, monkeypatch):
        response, error = _run_with_mode("head_mismatch", monkeypatch)
        assert error is None
        ok, lines = _mod.evaluate(response, _mod.current_git_head(), None)
        assert ok  # 단발 불일치는 red가 아니라 경고
        assert any("불일치" in ln for ln in lines)

    def test_command_not_found_triggers_full_fallback(self):
        response, error = _mod.invoke_describe(["/no/such/registry-binary"])
        assert response is None
        assert error is not None


class TestCliEndToEnd:
    def test_main_exits_zero_on_good_pointer(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FAKE_REGISTRY_MODE", "good")
        pointer = tmp_path / "registry.json"
        pointer.write_text(json.dumps({"command": [sys.executable, str(FIXTURE)]}))
        rc = _mod.main(["--pointer", str(pointer)])
        assert rc == 0

    def test_main_exits_one_on_missing_args(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FAKE_REGISTRY_MODE", "missing_args")
        pointer = tmp_path / "registry.json"
        pointer.write_text(json.dumps({"command": [sys.executable, str(FIXTURE)]}))
        rc = _mod.main(["--pointer", str(pointer)])
        assert rc == 1

    def test_main_exits_one_on_url_pointer(self, tmp_path):
        pointer = tmp_path / "registry.json"
        pointer.write_text(json.dumps({"url": "http://localhost"}))
        rc = _mod.main(["--pointer", str(pointer)])
        assert rc == 1

    def test_main_via_real_subprocess(self, tmp_path, monkeypatch):
        """--pointer/-- 인자 파싱과 프로세스 exit code 전체를 실제 서브프로세스로 확인."""
        monkeypatch.setenv("FAKE_REGISTRY_MODE", "good")
        env = {**__import__("os").environ}
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "check_registry_describe.py"),
                "--",
                sys.executable,
                str(FIXTURE),
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
