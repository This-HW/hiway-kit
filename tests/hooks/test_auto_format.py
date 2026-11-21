"""Tests for auto-format.py hook."""

import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS_DIR = Path(__file__).resolve().parents[2] / "plugins" / "common" / "hooks"
_spec = importlib.util.spec_from_file_location(
    "auto_format", HOOKS_DIR / "auto-format.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["auto_format"] = _mod
_spec.loader.exec_module(_mod)

run_pipeline = _mod.run_pipeline
_validate_path = _mod._validate_path
_has_eslint_config = _mod._has_eslint_config


def run_main(input_data: dict) -> int:
    stdin_text = json.dumps(input_data)
    with patch("sys.stdin", StringIO(stdin_text)):
        try:
            _mod.main()
        except SystemExit as e:
            return e.code
    return 0


class TestValidatePath:
    def test_returns_none_for_path_traversal(self):
        assert _validate_path("../../etc/passwd") is None

    def test_returns_none_for_nonexistent_file(self):
        assert _validate_path("/nonexistent/path/file.py") is None

    def test_returns_none_for_empty(self):
        assert _validate_path("") is None

    def test_returns_abspath_for_valid_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        result = _validate_path(str(f))
        assert result == str(f)

    def test_returns_none_for_symlink(self, tmp_path):
        real = tmp_path / "real.py"
        real.write_text("x = 1\n")
        link = tmp_path / "link.py"
        link.symlink_to(real)
        assert _validate_path(str(link)) is None


class TestHasEslintConfig:
    def test_no_config_returns_false(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("const x = 1;")
        assert _has_eslint_config(str(f)) is False

    def test_eslintrc_in_same_dir_returns_true(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("const x = 1;")
        (tmp_path / ".eslintrc.json").write_text("{}")
        assert _has_eslint_config(str(f)) is True

    def test_eslint_config_js_in_parent_returns_true(self, tmp_path):
        subdir = tmp_path / "src"
        subdir.mkdir()
        f = subdir / "app.js"
        f.write_text("const x = 1;")
        (tmp_path / "eslint.config.js").write_text("module.exports = {};")
        assert _has_eslint_config(str(f)) is True


class TestRunPipeline:
    def test_unknown_extension_returns_0(self, tmp_path):
        f = tmp_path / "file.xyz"
        f.write_text("data")
        assert run_pipeline(str(f)) == 0

    def test_invalid_path_returns_0(self):
        assert run_pipeline("/nonexistent/path/file.py") == 0

    def test_path_traversal_returns_0(self):
        assert run_pipeline("../../etc/passwd") == 0

    def test_python_file_no_tools_returns_0(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch.object(_mod, "_has_tool", return_value=False):
            assert run_pipeline(str(f)) == 0

    def test_pipeline_step_timeout_returns_0(self, tmp_path):
        import subprocess

        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with (
            patch.object(_mod, "_has_tool", return_value=True),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ruff", 10)),
        ):
            result = run_pipeline(str(f))
        assert result == 0

    def test_pipeline_collects_ruff_feedback(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("import os\nx=1\n")
        (tmp_path / "ruff.toml").write_text("")  # 프로젝트가 ruff 를 쓰기로 했다
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "test.py:1:1: F401 unused import\n"
        mock_result.stderr = ""

        def fake_run(cmd, **kwargs):
            if "check" in cmd:
                return mock_result
            ok = MagicMock()
            ok.returncode = 0
            ok.stdout = ""
            ok.stderr = ""
            return ok

        with (
            patch.object(_mod, "_has_tool", return_value=True),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = run_pipeline(str(f))
        assert result == 2


class TestMainIntegration:
    def test_non_edit_write_tool_exits_0(self):
        code = run_main({"tool_name": "Read", "tool_input": {"file_path": "/app/f.py"}})
        assert code == 0

    def test_missing_file_path_exits_0(self):
        code = run_main({"tool_name": "Edit", "tool_input": {}})
        assert code == 0

    def test_malformed_json_exits_0(self):
        with patch("sys.stdin", StringIO("not json")):
            try:
                _mod.main()
            except SystemExit as e:
                assert e.code == 0

    def test_bash_tool_exits_0(self):
        code = run_main({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert code == 0


class TestApplyPatchTargets:
    """Codex `apply_patch` 페이로드에서 포맷 대상 경로 추출.

    실측 근거 [confirmed: codex-cli 0.153.4, 2026-09-10]: Codex 는 파일을 쓸 때
    `tool_name="apply_patch"`, `tool_input={"command": "*** Begin Patch ..."}` 를
    PostToolUse 로 보낸다 — Claude Code 의 `Edit`/`file_path` 와 스키마는 같지만
    도구 이름과 경로 위치가 다르다.
    """

    def test_extracts_update_and_add_but_not_delete(self):
        patch_text = (
            "*** Begin Patch\n"
            "*** Update File: /tmp/a.py\n"
            "@@\n"
            "-x = 1\n"
            "+x = 2\n"
            "*** Add File: /tmp/b.py\n"
            "+y = 1\n"
            "*** Delete File: /tmp/c.py\n"
            "*** End Patch"
        )
        assert _mod._targets_from_apply_patch(patch_text) == ["/tmp/a.py", "/tmp/b.py"]

    def test_extracts_move_destination(self):
        patch_text = (
            "*** Begin Patch\n*** Move to: /tmp/moved.py\n*** End Patch"
        )
        assert _mod._targets_from_apply_patch(patch_text) == ["/tmp/moved.py"]

    def test_marker_inside_diff_body_is_not_a_target(self):
        """diff 본문(` `/`+`/`-` 로 시작)에 든 마커 텍스트는 진짜 마커가 아니다.

        관대한 패턴이면 문서·픽스처가 자기 자신을 대상으로 만든다(원장 교훈).
        """
        patch_text = (
            "*** Begin Patch\n"
            "*** Update File: /tmp/doc.md\n"
            "@@\n"
            "+*** Update File: /etc/passwd\n"
            " *** Update File: /etc/shadow\n"
            "-*** Add File: /etc/hosts\n"
            "*** End Patch"
        )
        assert _mod._targets_from_apply_patch(patch_text) == ["/tmp/doc.md"]

    def test_deduplicates(self):
        patch_text = (
            "*** Begin Patch\n"
            "*** Update File: /tmp/a.py\n"
            "*** Update File: /tmp/a.py\n"
            "*** End Patch"
        )
        assert _mod._targets_from_apply_patch(patch_text) == ["/tmp/a.py"]


class TestTargetsFromPayload:
    def test_claude_code_edit(self):
        assert _mod._targets_from_payload(
            {"tool_name": "Edit", "tool_input": {"file_path": "/x.py"}}
        ) == ["/x.py"]

    def test_codex_apply_patch(self):
        assert _mod._targets_from_payload(
            {
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: /x.py\n*** End Patch"
                },
            }
        ) == ["/x.py"]

    def test_unknown_tool_is_noop(self):
        assert _mod._targets_from_payload(
            {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        ) == []

    def test_non_dict_tool_input_is_noop(self):
        assert _mod._targets_from_payload(
            {"tool_name": "apply_patch", "tool_input": "not-a-dict"}
        ) == []

    def test_apply_patch_runs_pipeline_on_each_target(self, tmp_path):
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("x = 1\n")
        b.write_text("y = 1\n")
        seen = []
        with patch.object(_mod, "run_pipeline", side_effect=lambda p, *_a: seen.append(p) or 0):
            code = run_main(
                {
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": (
                            f"*** Begin Patch\n*** Update File: {a}\n"
                            f"*** Update File: {b}\n*** End Patch"
                        )
                    },
                }
            )
        assert code == 0
        assert seen == [str(a), str(b)]

    def test_apply_patch_propagates_feedback_exit_code(self, tmp_path):
        a = tmp_path / "a.py"
        a.write_text("x = 1\n")
        with patch.object(_mod, "run_pipeline", return_value=2):
            code = run_main(
                {
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": f"*** Begin Patch\n*** Update File: {a}\n*** End Patch"
                    },
                }
            )
        assert code == 2


# ── v5.0.0 A2: 지연 비용 ─────────────────────────────────────────────────────
#
# 이 훅은 모든 파일 쓰기마다 돈다. 아래는 되돌리면 red 가 되는 계약들이다:
# npx 미호출(로컬 바이너리 없으면 subprocess 0회) · ruff 파일당 2회 이하 ·
# 호출 전체 예산이 훅 타임아웃보다 작음 · MultiEdit 처리 · 모르는 페이로드 무해 통과.


def _ok(*_a, **_kw):
    r = MagicMock()
    r.returncode = 0
    r.stdout = ""
    r.stderr = ""
    return r


def _repo(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


def _fake_bin(root, tool):
    bindir = root / "node_modules" / ".bin"
    bindir.mkdir(parents=True, exist_ok=True)
    exe = bindir / tool
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(0o755)
    return exe


class TestNoNpx:
    def test_md_without_local_prettier_spawns_nothing(self, tmp_path):
        """prettier 가 없는 프로젝트의 .md 편집 — 예전엔 npx 가 매번 떴다(245ms)."""
        f = _repo(tmp_path) / "README.md"
        f.write_text("# x\n")
        with patch("subprocess.run", side_effect=_ok) as run:
            assert run_pipeline(str(f)) == 0
        assert run.call_count == 0

    def test_js_with_eslint_config_but_no_local_bins_spawns_nothing(self, tmp_path):
        root = _repo(tmp_path)
        (root / ".eslintrc.json").write_text("{}")
        f = root / "app.js"
        f.write_text("const x = 1;\n")
        with patch("subprocess.run", side_effect=_ok) as run:
            assert run_pipeline(str(f)) == 0
        assert run.call_count == 0

    def test_local_prettier_is_used_directly(self, tmp_path):
        root = _repo(tmp_path)
        (root / ".prettierrc").write_text("{}")  # 프로젝트가 prettier 를 쓰기로 했다
        exe = _fake_bin(root, "prettier")
        sub = root / "docs"
        sub.mkdir()
        f = sub / "a.md"
        f.write_text("# x\n")
        with patch("subprocess.run", side_effect=_ok) as run:
            run_pipeline(str(f))
        cmds = [c.args[0] for c in run.call_args_list]
        assert cmds == [[str(exe), "--write", str(f)]]
        assert not any("npx" in part for cmd in cmds for part in cmd)

    def test_local_eslint_runs_once_with_fix(self, tmp_path):
        root = _repo(tmp_path)
        (root / ".eslintrc.json").write_text("{}")
        eslint = _fake_bin(root, "eslint")
        f = root / "app.js"
        f.write_text("const x = 1;\n")
        with patch("subprocess.run", side_effect=_ok) as run:
            run_pipeline(str(f))
        cmds = [c.args[0] for c in run.call_args_list]
        assert cmds == [[str(eslint), "--fix", "--format=compact", str(f)]]

    def test_bin_lookup_stops_at_repo_root(self, tmp_path):
        """레포 밖(상위 디렉토리)의 node_modules 는 이 프로젝트의 도구가 아니다."""
        _fake_bin(tmp_path, "prettier")
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        f = repo / "a.md"
        f.write_text("# x\n")
        assert _mod._local_node_bin(str(f), "prettier") is None


class TestRuffCallCount:
    def test_python_file_invokes_ruff_at_most_twice(self, tmp_path):
        f = tmp_path / "m.py"
        f.write_text("x = 1\n")
        (tmp_path / "ruff.toml").write_text("")
        with (
            patch.object(_mod, "_has_tool", return_value=True),
            patch("subprocess.run", side_effect=_ok) as run,
        ):
            assert run_pipeline(str(f)) == 0
        ruff_calls = [c.args[0] for c in run.call_args_list if c.args[0][0] == "ruff"]
        assert 1 <= len(ruff_calls) <= 2, ruff_calls


class TestBudget:
    def test_budget_is_below_hook_timeouts(self):
        """호출 전체 예산 < 훅 타임아웃 — 하네스가 죽이기 전에 스스로 멈춘다."""
        for manifest in ("hooks.json", "hooks-codex.json"):
            data = json.loads((HOOKS_DIR / manifest).read_text(encoding="utf-8"))
            timeouts = [
                h["timeout"]
                for entry in data["hooks"]["PostToolUse"]
                for h in entry["hooks"]
                if "auto-format.py" in json.dumps(h)
            ]
            assert timeouts, manifest
            assert all(t > _mod.BUDGET_SECONDS for t in timeouts), (manifest, timeouts)
        assert _mod.STEP_TIMEOUT <= _mod.BUDGET_SECONDS

    def test_step_timeout_is_cut_by_remaining_budget(self, tmp_path):
        import time

        f = tmp_path / "m.py"
        f.write_text("x = 1\n")
        (tmp_path / "ruff.toml").write_text("")
        with (
            patch.object(_mod, "_has_tool", return_value=True),
            patch("subprocess.run", side_effect=_ok) as run,
        ):
            run_pipeline(str(f), time.monotonic() + 3)
        assert run.call_args_list
        assert all(c.kwargs["timeout"] <= 3 for c in run.call_args_list)

    def test_exhausted_budget_skips_steps_and_says_so(self, tmp_path, capsys):
        import time

        f = tmp_path / "m.py"
        f.write_text("x = 1\n")
        with patch("subprocess.run", side_effect=_ok) as run:
            assert run_pipeline(str(f), time.monotonic() - 1) == 0
        assert run.call_count == 0
        assert "예산" in capsys.readouterr().err


class TestPayloadShapes:
    def test_multiedit_is_formatted(self):
        assert _mod._targets_from_payload(
            {"tool_name": "MultiEdit", "tool_input": {"file_path": "/x.py", "edits": []}}
        ) == ["/x.py"]

    def test_unknown_codex_payloads_pass_silently(self, capsys):
        """Codex PostToolUse 가 보낼 수 있는 모르는 tool_name — 예외 없이 exit 0."""
        payloads = [
            {"tool_name": "shell", "tool_input": {"command": ["ls", "-la"]}},
            {"tool_name": "exec_command", "tool_input": {"cmd": "ls"}},
            {"tool_name": "update_plan", "tool_input": {"plan": [{"step": "x"}]}},
            {"tool_name": "mcp__server__tool", "tool_input": None},
            {"tool_name": None},
            {},
        ]
        with patch("subprocess.run", side_effect=_ok) as run:
            for payload in payloads:
                assert run_main(payload) == 0, payload
        assert run.call_count == 0
        assert capsys.readouterr().err == ""

    def test_non_object_payload_exits_zero(self):
        with patch("sys.stdin", StringIO("[1, 2, 3]")):
            try:
                _mod.main()
            except SystemExit as e:
                assert e.code == 0


class TestRuffNeedsProjectConfig:
    """외부 설치 보고(2026-11-09): ruff 를 쓰지 않는 레포에서 훅이 ruff format·check --fix 를 돌려
    손대지 않은 `import os, sys` 를 지우고 따옴표를 전부 바꿨다. prettier·eslint 처럼 프로젝트가
    ruff 를 쓰기로 했을 때만 돈다."""

    def test_no_project_config_never_invokes_ruff(self, tmp_path):
        (tmp_path / ".git").mkdir()
        f = tmp_path / "job.py"
        f.write_text("import os, sys\nx=1\n")
        with (
            patch.object(_mod, "_has_tool", return_value=True),
            patch("subprocess.run", side_effect=_ok) as run,
        ):
            assert run_pipeline(str(f)) == 0
        assert not [c for c in run.call_args_list if c.args[0][0] == "ruff"]

    def test_pyproject_tool_ruff_enables_ruff(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
        f = tmp_path / "job.py"
        f.write_text("x=1\n")
        with (
            patch.object(_mod, "_has_tool", return_value=True),
            patch("subprocess.run", side_effect=_ok) as run,
        ):
            run_pipeline(str(f))
        assert [c for c in run.call_args_list if c.args[0][0] == "ruff"]



class TestGoRustNeedProjectConsent:
    """PATH 에 gofmt·rustfmt 가 있다는 것은 그 프로젝트의 동의가 아니다(소비자 흔적 규칙 2).
    gofmt 는 Go 모듈(go.mod) 안에서, rustfmt 는 rustfmt.toml·.rustfmt.toml 이 있을 때만 돈다."""

    @staticmethod
    def _calls(path, tool):
        with (
            patch.object(_mod, "_has_tool", return_value=True),
            patch("subprocess.run", side_effect=_ok) as run,
        ):
            assert run_pipeline(str(path)) == 0
        return [c for c in run.call_args_list if c.args[0][0] == tool]

    def test_go_file_outside_a_module_is_left_alone(self, tmp_path):
        _repo(tmp_path)
        f = tmp_path / "main.go"
        f.write_text("package main\n")
        assert self._calls(f, "gofmt") == []

    def test_go_file_in_a_module_is_formatted(self, tmp_path):
        """양성 대조 — 같은 파일이 go.mod 아래면 gofmt 를 부른다."""
        _repo(tmp_path)
        (tmp_path / "go.mod").write_text("module example.com/x\n")
        f = tmp_path / "cmd" / "main.go"
        f.parent.mkdir()
        f.write_text("package main\n")
        assert len(self._calls(f, "gofmt")) == 1

    def test_go_mod_above_the_repo_root_does_not_count(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/outer\n")
        (tmp_path / "inner").mkdir()
        repo = _repo(tmp_path / "inner")
        f = repo / "main.go"
        f.write_text("package main\n")
        assert self._calls(f, "gofmt") == []

    def test_go_fmt_scope_skips_testdata_vendor_and_hidden_dirs(self, tmp_path):
        """`go fmt ./...` 가 건너뛰는 곳(골든 픽스처 testdata 등)은 고치지 않는다 — 모듈 밖 경로의
        이름은 보지 않는다(레포 위 디렉토리 이름이 vendor 여도 포맷한다)."""
        root = tmp_path / "vendor" / "proj"
        root.mkdir(parents=True)
        _repo(root)
        (root / "go.mod").write_text("module example.com/x\n")
        for rel in ("testdata/bad.go", "vendor/dep/d.go", "_tools/t.go", ".gen/g.go"):
            f = root / rel
            f.parent.mkdir(parents=True)
            f.write_text("package x\n")
            assert self._calls(f, "gofmt") == [], rel
        ok = root / "pkg" / "ok.go"
        ok.parent.mkdir()
        ok.write_text("package pkg\n")
        assert len(self._calls(ok, "gofmt")) == 1

    def test_rust_file_without_rustfmt_config_is_left_alone(self, tmp_path):
        _repo(tmp_path)
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "x"\n')
        f = tmp_path / "src" / "main.rs"
        f.parent.mkdir()
        f.write_text("fn main(){}\n")
        assert self._calls(f, "rustfmt") == []

    def test_rust_file_with_rustfmt_config_is_formatted(self, tmp_path):
        """양성 대조 — rustfmt.toml 이 있으면 부른다(.rustfmt.toml 도 같다)."""
        for index, name in enumerate(("rustfmt.toml", ".rustfmt.toml")):
            (tmp_path / f"crate{index}").mkdir()
            root = _repo(tmp_path / f"crate{index}")
            (root / name).write_text('edition = "2021"\n')
            f = root / "src" / "main.rs"
            f.parent.mkdir()
            f.write_text("fn main(){}\n")
            assert len(self._calls(f, "rustfmt")) == 1, name
