"""
evals/run.py 단위 테스트 — claude CLI 호출은 전부 mock/서브프로세스 스텁.

커버리지:
  - frontmatter/본문 파싱
  - expect.json 스키마 검증(--validate 로직)
  - 각 assertion 타입 채점기
  - exit code 규율 (claude 부재 → SKIPPED=2)
  - baseline 비교(후퇴 검출)
  - dry-run이 실제 subprocess를 호출하지 않음
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import run as runner

# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


def test_parse_frontmatter_scalar_and_list():
    content = (
        "---\n"
        "name: fix-bugs\n"
        "model: sonnet\n"
        "tools:\n"
        "  - Read\n"
        "  - Edit\n"
        "  - Bash\n"
        "---\n"
        "# 역할: 버그 수정 전문가\n"
        "본문 내용\n"
    )
    fm, body = runner.parse_frontmatter(content)
    assert fm["name"] == "fix-bugs"
    assert fm["model"] == "sonnet"
    assert fm["tools"] == ["Read", "Edit", "Bash"]
    assert "본문 내용" in body
    assert "---" not in body.split("\n")[0]


def test_parse_frontmatter_block_scalar_description():
    content = (
        "---\n"
        "name: review-code\n"
        "description: |\n"
        "  적대적 코드 리뷰어.\n"
        "  MUST USE when: 리뷰 요청.\n"
        "model: opus\n"
        "---\n"
        "본문\n"
    )
    fm, body = runner.parse_frontmatter(content)
    assert fm["name"] == "review-code"
    assert "적대적 코드 리뷰어" in fm["description"]
    assert fm["model"] == "opus"
    assert body.strip() == "본문"


def test_parse_frontmatter_no_frontmatter_returns_empty():
    fm, body = runner.parse_frontmatter("그냥 본문입니다")
    assert fm == {}
    assert body == "그냥 본문입니다"


def test_parse_frontmatter_unterminated_returns_empty():
    fm, _body = runner.parse_frontmatter("---\nname: x\n(닫는 --- 없음)")
    assert fm == {}


# ---------------------------------------------------------------------------
# load_agent (실제 레포 에이전트 정의 파싱)
# ---------------------------------------------------------------------------


def test_load_agent_review_code_resolves_model_and_tools():
    agent = runner.load_agent("review-code")
    assert agent.name == "review-code"
    assert agent.model == "opus"
    assert "Read" in agent.tools
    assert agent.system_prompt  # 본문이 비어있지 않음


def test_load_agent_unknown_raises():
    import pytest as _pytest

    with _pytest.raises(FileNotFoundError):
        runner.load_agent("no-such-agent-xyz")


# ---------------------------------------------------------------------------
# expect.json 스키마 검증
# ---------------------------------------------------------------------------


def test_validate_expect_schema_valid():
    expect = {"assertions": [{"type": "output_regex", "pattern": "x"}]}
    assert runner.validate_expect_schema(expect, "p") == []


def test_validate_expect_schema_missing_assertions():
    errors = runner.validate_expect_schema({}, "p")
    assert any("assertions" in e for e in errors)


def test_validate_expect_schema_unknown_type():
    expect = {"assertions": [{"type": "made_up_type"}]}
    errors = runner.validate_expect_schema(expect, "p")
    assert any("알 수 없는 type" in e for e in errors)


def test_validate_expect_schema_missing_required_field():
    expect = {"assertions": [{"type": "output_regex"}]}
    errors = runner.validate_expect_schema(expect, "p")
    assert any("pattern" in e for e in errors)


def test_validate_expect_schema_judge_enabled_without_rubric():
    expect = {
        "assertions": [{"type": "output_regex", "pattern": "x"}],
        "judge": {"enabled": True},
    }
    errors = runner.validate_expect_schema(expect, "p")
    assert any("rubric" in e for e in errors)


def test_validate_all_scenarios_root_missing(tmp_path):
    errors = runner.validate_all(scenarios_root=tmp_path / "does-not-exist")
    assert errors  # fail-closed: 부재는 항상 오류


def test_validate_scenario_unknown_agent(tmp_path):
    sc_dir = tmp_path / "no-such-agent" / "scenario-1"
    (sc_dir / "fixture").mkdir(parents=True)
    (sc_dir / "task.md").write_text("task")
    (sc_dir / "expect.json").write_text(
        json.dumps({"assertions": [{"type": "output_regex", "pattern": "x"}]})
    )
    errors = runner.validate_scenario(
        sc_dir, agents_root=tmp_path / "empty-agents-root"
    )
    assert any("알 수 없는 agent" in e for e in errors)


def test_validate_scenario_missing_files(tmp_path):
    sc_dir = tmp_path / "fix-bugs" / "broken"
    sc_dir.mkdir(parents=True)
    errors = runner.validate_scenario(sc_dir, agents_root=runner.AGENTS_ROOT)
    joined = "\n".join(errors)
    assert "task.md" in joined
    assert "fixture/" in joined
    assert "expect.json" in joined


def test_validate_all_on_repo_scenarios_is_clean():
    # 저장소에 커밋된 11개 시나리오 자체가 스키마를 통과해야 한다.
    errors = runner.validate_all()
    assert errors == []


# ---------------------------------------------------------------------------
# assertion 채점기
# ---------------------------------------------------------------------------


def test_check_assertion_output_regex_match():
    ok, _ = runner.check_assertion(
        {"type": "output_regex", "pattern": r"off-by-one"},
        "found an off-by-one bug",
        Path("."),
    )
    assert ok is True


def test_check_assertion_output_regex_no_match():
    ok, detail = runner.check_assertion(
        {"type": "output_regex", "pattern": r"nope"}, "all good", Path(".")
    )
    assert ok is False
    assert "매치 없음" in detail


def test_check_assertion_output_contains_any_case_insensitive():
    ok, _ = runner.check_assertion(
        {"type": "output_contains_any", "values": ["SQL Injection", "other"]},
        "there is a sql injection risk",
        Path("."),
    )
    assert ok is True


def test_check_assertion_output_not_contains_fails_when_present():
    ok, detail = runner.check_assertion(
        {"type": "output_not_contains", "values": ["secret"]},
        "the secret is here",
        Path("."),
    )
    assert ok is False
    assert "발견됨" in detail


def test_validate_expect_schema_rejects_removed_delegation_signal():
    """delegation_signal은 W-023 D-6에서 제거됐다 — 이제 알 수 없는 type으로
    거부된다(사용자 0 확인 후 계약 폐기, CLAUDE.md 근거 정정과 함께)."""
    expect = {"assertions": [{"type": "delegation_signal"}]}
    errors = runner.validate_expect_schema(expect, "p")
    assert any("알 수 없는 type" in e for e in errors)


def test_check_assertion_rejects_removed_delegation_signal():
    ok, detail = runner.check_assertion({"type": "delegation_signal"}, "x", Path("."))
    assert ok is False
    assert "알 수 없는" in detail


def test_check_assertion_file_contains(tmp_path):
    (tmp_path / "out.py").write_text("def foo():\n    return 42\n")
    ok, _ = runner.check_assertion(
        {"type": "file_contains", "file": "out.py", "pattern": r"return 42"},
        "",
        tmp_path,
    )
    assert ok is True


def test_check_assertion_file_contains_missing_file(tmp_path):
    ok, detail = runner.check_assertion(
        {"type": "file_contains", "file": "nope.py", "pattern": "x"}, "", tmp_path
    )
    assert ok is False
    assert "파일 없음" in detail


def test_check_assertion_file_contains_multiline_anchor(tmp_path):
    """`file_contains` MULTILINE 회귀 테스트 — `^` 앵커가 파일 첫 줄이 아닌 줄에서도 매치해야 한다.

    수정 전에는 re.search에 MULTILINE이 전달되지 않아 `^`가 문자열 전체의
    시작(=파일 첫 바이트)에만 매치했다. frontmatter처럼 구분선 뒤에 오는 필드
    (`---\nname: foo\n...`)를 앵커링하는 흔한 패턴이 항상 false-fail이었다
    (실측: generate-boilerplate/agent-md-skeleton 1차 시도, W-018 S3).
    """
    (tmp_path / "agent.md").write_text("---\nname: format-code\ndescription: x\n---\n")
    ok, _ = runner.check_assertion(
        {
            "type": "file_contains",
            "file": "agent.md",
            "pattern": r"^name:\s*format-code",
        },
        "",
        tmp_path,
    )
    assert ok is True


def test_check_assertion_pytest_green_pass(tmp_path):
    (tmp_path / "test_ok.py").write_text("def test_trivial():\n    assert 1 == 1\n")
    ok, _ = runner.check_assertion({"type": "pytest_green", "path": "."}, "", tmp_path)
    assert ok is True


def test_check_assertion_pytest_green_fail(tmp_path):
    (tmp_path / "test_bad.py").write_text("def test_trivial():\n    assert 1 == 2\n")
    ok, detail = runner.check_assertion(
        {"type": "pytest_green", "path": "."}, "", tmp_path
    )
    assert ok is False
    assert "exit" in detail


def test_check_assertion_unknown_type():
    ok, detail = runner.check_assertion({"type": "bogus"}, "", Path("."))
    assert ok is False
    assert "알 수 없는" in detail


# ---------------------------------------------------------------------------
# exit code 규율 — claude CLI 부재 → SKIPPED(2), 절대 0 위장 금지
# ---------------------------------------------------------------------------


def test_run_all_skipped_when_claude_missing(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    sc_dir = scenarios_root / "fix-bugs" / "s1"
    (sc_dir / "fixture").mkdir(parents=True)
    (sc_dir / "task.md").write_text("do it")
    (sc_dir / "expect.json").write_text(
        json.dumps({"assertions": [{"type": "output_regex", "pattern": "x"}]})
    )

    with (
        patch.object(runner, "SCENARIOS_ROOT", scenarios_root),
        patch("shutil.which", return_value=None),
    ):
        report, exit_code = runner.run_all(None, None, 1, 5, dry_run=False)
    assert exit_code == runner.EXIT_SKIPPED
    assert report["results"] == []


def test_run_all_no_scenarios_matched_is_fail(tmp_path):
    _report, exit_code = runner.run_all(
        "no-such-agent",
        None,
        1,
        5,
        dry_run=False,
    )
    assert exit_code == runner.EXIT_FAIL


def test_dry_run_does_not_invoke_subprocess(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    sc_dir = scenarios_root / "fix-bugs" / "s1"
    (sc_dir / "fixture").mkdir(parents=True)
    (sc_dir / "task.md").write_text("do it")
    (sc_dir / "expect.json").write_text(
        json.dumps({"assertions": [{"type": "output_regex", "pattern": "x"}]})
    )

    with (
        patch.object(runner, "SCENARIOS_ROOT", scenarios_root),
        patch("subprocess.run") as mock_run,
    ):
        report, exit_code = runner.run_all(None, None, 1, 5, dry_run=True)
    mock_run.assert_not_called()
    assert exit_code == runner.EXIT_PASS
    assert report["results"] == []


# ---------------------------------------------------------------------------
# baseline 비교(후퇴 검출)
# ---------------------------------------------------------------------------


def test_compare_baseline_detects_regression(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"summary": {"fix-bugs": {"pass_rate": 1.0}}}))
    current = {"fix-bugs": {"pass_rate": 0.5}}
    regressions = runner.compare_baseline(current, str(baseline_path))
    assert regressions
    assert "fix-bugs" in regressions[0]


def test_compare_baseline_no_regression_when_improved(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"summary": {"fix-bugs": {"pass_rate": 0.5}}}))
    current = {"fix-bugs": {"pass_rate": 1.0}}
    regressions = runner.compare_baseline(current, str(baseline_path))
    assert regressions == []


def test_claude_json_projects_count_reads_projects(tmp_path, monkeypatch):
    """D-10: ~/.claude.json 의 projects 딕셔너리 개수를 센다."""
    fake_home = tmp_path
    (fake_home / ".claude.json").write_text(
        json.dumps({"projects": {"a": {}, "b": {}, "c": {}}})
    )
    monkeypatch.setattr(runner.Path, "home", lambda: fake_home)
    assert runner._claude_json_projects_count() == 3


def test_claude_json_projects_count_fail_open_when_missing(tmp_path, monkeypatch):
    """D-10 fail-open: 파일이 없으면 None (경고를 강제하지 않는다)."""
    monkeypatch.setattr(runner.Path, "home", lambda: tmp_path)
    assert runner._claude_json_projects_count() is None


def test_claude_json_projects_count_fail_open_on_malformed_json(tmp_path, monkeypatch):
    """D-10 fail-open: 파싱 실패해도 None — 크래시 금지."""
    (tmp_path / ".claude.json").write_text("{not valid json")
    monkeypatch.setattr(runner.Path, "home", lambda: tmp_path)
    assert runner._claude_json_projects_count() is None


def test_summarize_pass_rate():
    results = [
        {"agent": "fix-bugs", "status": "pass"},
        {"agent": "fix-bugs", "status": "fail"},
        {"agent": "review-code", "status": "pass"},
    ]
    summary = runner.summarize(results)
    assert summary["fix-bugs"]["pass_rate"] == 0.5
    assert summary["review-code"]["pass_rate"] == 1.0


# ---------------------------------------------------------------------------
# CLI main() — validate 모드
# ---------------------------------------------------------------------------


def test_main_validate_exit_zero_on_repo_scenarios():
    assert runner.main(["--validate"]) == runner.EXIT_PASS


def test_main_validate_exit_one_on_bad_scenarios(tmp_path):
    scenarios_root = tmp_path / "scenarios"
    sc_dir = scenarios_root / "fix-bugs" / "broken"
    sc_dir.mkdir(parents=True)
    with patch.object(runner, "SCENARIOS_ROOT", scenarios_root):
        assert runner.main(["--validate"]) == runner.EXIT_FAIL


# ---------------------------------------------------------------------------
# pytest 인터프리터 해석 (baseline 0% 사건 — 시스템 python3에 pytest 부재)
# ---------------------------------------------------------------------------


def test_pytest_green_fails_explicitly_when_no_pytest(tmp_path):
    """pytest 인터프리터 부재 시 green 위장 없이 명시적 실패해야 한다."""
    with patch.object(runner, "resolve_pytest_python", return_value=None):
        ok, detail = runner.check_assertion(
            {"type": "pytest_green", "path": "."}, "무관한 출력", tmp_path
        )
    assert ok is False
    assert "pytest" in detail and "없" in detail


def test_resolve_pytest_python_caches_and_probes(monkeypatch):
    """탐색 결과는 캐시되고, import pytest 성공 후보를 반환한다."""
    runner._PYTEST_PY = None
    calls = []

    class R:
        def __init__(self, rc):
            self.returncode = rc

    def fake_run(cmd, **kw):
        calls.append(cmd[0])
        # 첫 후보만 성공
        return R(0 if len(calls) == 1 else 1)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    first = runner.resolve_pytest_python()
    assert first == calls[0]
    # 캐시 — 추가 probe 없음
    n = len(calls)
    assert runner.resolve_pytest_python() == first
    assert len(calls) == n
    runner._PYTEST_PY = None


# ---------------------------------------------------------------------------
# run_scenario 채점 코어 (적대적 리뷰 B / ATK-001·003·004·008)
# ---------------------------------------------------------------------------


def _agent(tmp_path):
    return runner.AgentDef(
        name="fix-bugs",
        path=tmp_path / "fix-bugs.md",
        model="sonnet",
        tools=["Read", "Edit", "Bash"],
        disallowed_tools=["Task"],
        system_prompt="테스트용",
    )


def _scenario(tmp_path, expect):
    fx = tmp_path / "fixture"
    fx.mkdir(exist_ok=True)
    return runner.Scenario(
        agent="fix-bugs",
        scenario_id="s1",
        path=tmp_path,
        task="과제",
        fixture_dir=fx,
        expect=expect,
    )


def test_run_scenario_empty_assertions_fails_closed(tmp_path):
    """assertions 0개 = 채점 불가 = fail (유령 pass 금지)."""
    res = runner.run_scenario(_agent(tmp_path), _scenario(tmp_path, {}), timeout=5)
    assert res["status"] == "fail"
    assert res["checks"][0]["type"] == "schema"


def test_run_scenario_claude_nonzero_exit_is_error(tmp_path, monkeypatch):
    """claude 비정상 종료(인프라 실패)는 error로 분류되고 pass가 아니어야 한다."""

    class R:
        returncode = 1
        stdout = "부분 출력 injection parameterize"  # 우연히 키워드 포함해도
        stderr = "auth expired"

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: R())
    sc = _scenario(
        tmp_path,
        {"assertions": [{"type": "output_contains_any", "values": ["injection"]}]},
    )
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["status"] == "error"
    assert "claude exit 1" in res["checks"][0]["detail"]


def test_run_scenario_work_dir_does_not_leak_agent_or_scenario(tmp_path, monkeypatch):
    """D-39/25-30: 실행 cwd 이름에 에이전트명·시나리오 id가 나타나면 안 된다.

    되돌려-FAIL: prefix를 f"ckkit-eval-{agent.name}-{scenario.scenario_id}-"로
    되돌리면 이 테스트가 red가 된다. 매핑 자체는 리포트의 work_dir 필드로 남는다
    (디버깅 편의 유지).
    """
    captured_cwd = {}

    class R:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(*a, **k):
        captured_cwd["cwd"] = k["cwd"]
        return R()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    agent = _agent(tmp_path)
    sc = _scenario(
        tmp_path, {"assertions": [{"type": "output_regex", "pattern": "ok"}]}
    )
    res = runner.run_scenario(agent, sc, timeout=5)

    assert agent.name not in captured_cwd["cwd"]
    assert sc.scenario_id not in captured_cwd["cwd"]
    assert res["work_dir"] == captured_cwd["cwd"]


def test_run_scenario_assertion_exception_degrades_to_fail(tmp_path, monkeypatch):
    """채점기 예외는 크래시가 아니라 해당 assertion fail로 강등."""

    class R:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: R())

    def boom(*a, **k):
        raise RuntimeError("scorer bug")

    monkeypatch.setattr(runner, "check_assertion", boom)
    sc = _scenario(tmp_path, {"assertions": [{"type": "output_regex", "pattern": "x"}]})
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["status"] == "fail"
    assert "채점 예외" in res["checks"][0]["detail"]


def test_pytest_green_timeout_is_fail(tmp_path, monkeypatch):
    """pytest 타임아웃은 전체 런 크래시가 아니라 fail."""
    monkeypatch.setattr(runner, "resolve_pytest_python", lambda: "python3")

    def timeout_run(*a, **k):
        raise runner.subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    monkeypatch.setattr(runner.subprocess, "run", timeout_run)
    ok, detail = runner.check_assertion(
        {"type": "pytest_green", "path": "."}, "", tmp_path
    )
    assert ok is False and "타임아웃" in detail


def test_file_unchanged_detects_test_tampering(tmp_path):
    """테스트 파일 변조(채점 게이밍)를 잡는다."""
    src = tmp_path / "src_fixture"
    work = tmp_path / "work"
    src.mkdir()
    work.mkdir()
    (src / "test_x.py").write_text("assert True\n")
    (work / "test_x.py").write_text("assert True  # tampered\n")
    ok, detail = runner.check_assertion(
        {"type": "file_unchanged", "file": "test_x.py"}, "", work, source_fixture=src
    )
    assert ok is False and "변조" in detail
    (work / "test_x.py").write_text("assert True\n")
    ok, _ = runner.check_assertion(
        {"type": "file_unchanged", "file": "test_x.py"}, "", work, source_fixture=src
    )
    assert ok is True


def test_resolve_in_repo_blocks_traversal(tmp_path):
    assert runner._resolve_in_repo(tmp_path, "../../etc/passwd") is None
    assert runner._resolve_in_repo(tmp_path, "sub/file.py") is not None


def test_compare_baseline_flags_coverage_loss(tmp_path):
    """시나리오 수 감소·에이전트 소실도 후퇴로 판정 (ATK-007)."""
    baseline = {
        "summary": {
            "fix-bugs": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0},
            "review-code": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0},
        }
    }
    bp = tmp_path / "b.json"
    bp.write_text(json.dumps(baseline))
    current = {"fix-bugs": {"pass": 1, "fail": 0, "total": 1, "pass_rate": 1.0}}
    regs = runner.compare_baseline(current, str(bp))
    joined = "\n".join(regs)
    assert "시나리오 수 감소" in joined
    assert "review-code" in joined and "커버리지 소실" in joined


def test_compare_baseline_agent_filter_no_false_coverage_loss(tmp_path):
    """--agent 필터 실행 시 미실행 에이전트를 커버리지 소실로 오탐하지 않는다 (ATK-004)."""
    baseline = {
        "summary": {
            "fix-bugs": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0},
            "review-code": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0},
        }
    }
    bp = tmp_path / "b.json"
    bp.write_text(json.dumps(baseline))
    current = {"fix-bugs": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0}}
    assert runner.compare_baseline(current, str(bp), agent_filter="fix-bugs") == []
    # 필터 없으면 여전히 소실 검출
    regs = runner.compare_baseline(current, str(bp))
    assert any("review-code" in r for r in regs)


# ---------------------------------------------------------------------------
# v2.10.1 재감사 하드닝 회귀 고정 (R1/R2 발견)
# ---------------------------------------------------------------------------


def test_discover_skips_cache_and_dot_dirs(tmp_path):
    """.ruff_cache 등 로컬 부산물이 유령 시나리오로 잡히지 않는다 (R1/ATK-004)."""
    (tmp_path / ".ruff_cache" / "0.15").mkdir(parents=True)
    (tmp_path / "fix-bugs" / "__pycache__").mkdir(parents=True)
    (tmp_path / "fix-bugs" / "real-scenario").mkdir()
    dirs = runner.discover_scenario_dirs(scenarios_root=tmp_path)
    assert [d.name for d in dirs] == ["real-scenario"]


def test_norm_nfc_normalization():
    """NFD 출력과 NFC expect 값이 일치 판정된다 (R1/ATK-006)."""
    import unicodedata

    nfd = unicodedata.normalize("NFD", "인젝션")
    assert runner._norm("인젝션") in runner._norm(f"이 코드엔 {nfd} 위험이 있다")


def test_compare_baseline_malformed_entry_flagged_not_crash(tmp_path):
    """pass_rate 누락 baseline 항목은 크래시가 아니라 회귀로 플래그 (R1/ATK-008)."""
    bp = tmp_path / "b.json"
    bp.write_text(json.dumps({"summary": {"fix-bugs": {"pass": 1}}}))
    current = {"fix-bugs": {"pass": 4, "fail": 0, "total": 4, "pass_rate": 1.0}}
    regs = runner.compare_baseline(current, str(bp))
    assert regs and "pass_rate 없음" in regs[0]


def test_main_refuses_baseline_with_filter(tmp_path, monkeypatch):
    """--agent 필터 + --baseline 은 기준선 저장을 거부한다 (R1/ATK-001)."""
    report = {
        "results": [
            {
                "agent": "fix-bugs",
                "scenario": "s",
                "status": "pass",
                "checks": [],
                "judge": None,
                "duration_s": 0.1,
            }
        ],
        "summary": {"fix-bugs": {"pass": 1, "fail": 0, "total": 1, "pass_rate": 1.0}},
    }
    monkeypatch.setattr(runner, "run_all", lambda *a, **k: (report, runner.EXIT_PASS))
    monkeypatch.setattr(runner, "BASELINE_DIR", tmp_path / "baseline")
    monkeypatch.setattr(runner, "REPORTS_DIR", tmp_path / "reports")
    rc = runner.main(["--agent", "fix-bugs", "--baseline"])
    assert rc == runner.EXIT_PASS
    assert (
        not list((tmp_path / "baseline").glob("*.json"))
        if (tmp_path / "baseline").exists()
        else True
    )
    # 필터 없으면 정상 저장
    rc = runner.main(["--baseline"])
    assert rc == runner.EXIT_PASS
    assert list((tmp_path / "baseline").glob("*.json"))


def test_run_scenario_pass_path_judge_advisory(tmp_path, monkeypatch):
    """전 assertion 통과 → pass, judge 결과는 advisory로만 기록 (R1/ATK-005)."""

    class R:
        returncode = 0
        stdout = "수정 완료 injection 지적"
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: R())
    monkeypatch.setenv("CKKIT_EVAL_JUDGE", "1")
    monkeypatch.setattr(runner, "run_judge", lambda *a, **k: {"ok": False, "score": 2})
    sc = _scenario(
        tmp_path,
        {
            "assertions": [{"type": "output_contains_any", "values": ["injection"]}],
            "judge": {"enabled": True, "rubric": "r"},
        },
    )
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["status"] == "pass"  # judge 실패해도 advisory — 판정 불변
    assert res["judge"]["advisory"] is True


def test_validate_scenario_rejects_module_scope_danger(tmp_path):
    """fixture 모듈 스코프의 위험 호출과 시나리오 루트 .py를 거부 (R2/ATK-003·005)."""
    sc = tmp_path / "fix-bugs" / "evil"
    fx = sc / "fixture"
    fx.mkdir(parents=True)
    (sc / "task.md").write_text("t")
    (sc / "expect.json").write_text(
        json.dumps({"assertions": [{"type": "pytest_green", "path": "."}]})
    )
    (fx / "mod.py").write_text("import os\nos.system('echo pwned')\n")
    (sc / "helper.py").write_text("x = 1\n")
    agents_root = tmp_path / "agents"
    agents_root.mkdir()
    (agents_root / "fix-bugs.md").write_text("---\nname: fix-bugs\n---\nbody")
    errors = runner.validate_scenario(sc, agents_root)
    joined = "\n".join(errors)
    assert "위험 호출" in joined and "시나리오 루트에 .py 금지" in joined


# ─────────────────────────────────────────────────────────────────────
# fixture 모듈 스코프 위험 호출 판정 (2026-08-23 적대적 리뷰 Critical)
#
# 이 검사의 유일한 목적은 "import 시 임의 코드가 도는 fixture를 커밋되게 두지 않는다"다.
# 1세대(정규식)는 별칭으로, 2세대(AST)는 클래스 본문·데코레이터·기본인자로 뚫렸다.
# 두 세대 모두 **우회 케이스 테스트가 0건**이었다는 게 진짜 결함이었으므로,
# 알려진 우회를 전부 표로 고정한다.
# ─────────────────────────────────────────────────────────────────────

MUST_BLOCK = [
    ("직접", 'import os\nos.system("x")\n'),
    ("import 별칭", 'import os as x\nx.system("x")\n'),
    ("from-import", 'from os import system\nsystem("x")\n'),
    ("클래스 본문(import 시 실행됨)", 'import os\nclass C:\n    _ = os.system("p")\n'),
    ("데코레이터 참조", "import os\n@os.popen\ndef f(): pass\n"),
    ("데코레이터 호출", 'import os\n@os.popen("x")\ndef f(): pass\n'),
    ("기본 인자", 'import os\ndef f(x=os.system("id")): pass\n'),
    ("star import", 'from os import *\nsystem("p")\n'),
    ("재바인딩", 'import os\nf = os.system\nf("p")\n'),
    ("getattr 우회", 'import os\ngetattr(os,"system")("p")\n'),
    ("importlib 우회", 'import importlib\nimportlib.import_module("os").system("x")\n'),
    ("subprocess", 'import subprocess\nsubprocess.run(["id"])\n'),
    ("from subprocess", 'from subprocess import run\nrun(["id"])\n'),
    ("shutil.rmtree", 'import shutil\nshutil.rmtree("/x")\n'),
    ("NUL 바이트(파싱 불가)", "a=1\x00\n"),
    ("구문 오류(검사 불가)", "this is not python(((\n"),
]

MUST_PASS = [
    ("정상 fixture", "def f(a=[]):\n    a.append(1)\n    return a\n"),
    ("함수 본문(import 시 미실행)", 'def f():\n    import os\n    os.system("x")\n'),
    ("os.path.join", 'import os\nP = os.path.join("a","b")\n'),
    ("urlparse", 'from urllib.parse import urlparse\nU = urlparse("http://x")\n'),
    ("shutil.which", 'from shutil import which\nW = which("git")\n'),
    ("open", 'D = open("data.txt")\n'),
    ("json", 'import json\nD = json.loads("{}")\n'),
    (
        "클래스 메서드 본문",
        'class C:\n    def m(self):\n        import os\n        os.system("x")\n',
    ),
    ("정상 데코레이터", "import functools\n@functools.cache\ndef f(): pass\n"),
]


def test_module_scope_danger_blocks_known_bypasses():
    missed = [
        label for label, src in MUST_BLOCK if not runner._module_scope_danger(src)
    ]
    assert missed == [], f"우회가 통과했다: {missed}"


def test_module_scope_danger_has_no_false_positives():
    """오탐은 단순한 불편이 아니다 — 정상 fixture를 만들 수 없게 만들어
    eval 커버리지 확대를 막는다."""
    flagged = [
        (label, runner._module_scope_danger(src))
        for label, src in MUST_PASS
        if runner._module_scope_danger(src)
    ]
    assert flagged == [], f"정상 코드가 거부됐다: {flagged}"


def test_unparseable_source_is_never_silently_passed():
    """검사 불가를 통과로 삼지 않는다 (false-green 금지)."""
    assert runner._module_scope_danger("def f(:\n") != []


# ---------------------------------------------------------------------------
# git.json 실체화 (W-023 Stage 0 — 러너 골격, D-1~D-4)
# ---------------------------------------------------------------------------


def _write_scenario(sc_dir: Path, git_spec: dict | None = None) -> None:
    (sc_dir / "fixture").mkdir(parents=True)
    (sc_dir / "task.md").write_text("task")
    (sc_dir / "expect.json").write_text(
        json.dumps({"assertions": [{"type": "output_regex", "pattern": "x"}]})
    )
    if git_spec is not None:
        (sc_dir / "git.json").write_text(json.dumps(git_spec))


def test_load_scenario_without_git_json_sets_none(tmp_path):
    """git.json 없는 시나리오는 종전대로 동작한다 (회귀 없음 — 최소 테스트 1)."""
    sc_dir = tmp_path / "fix-bugs" / "no-git"
    _write_scenario(sc_dir)
    sc = runner.load_scenario(sc_dir)
    assert sc.git_spec is None


def test_load_scenario_with_git_json_parses_spec(tmp_path):
    sc_dir = tmp_path / "git-workflow" / "with-git"
    spec = {"version": 1, "ops": [{"op": "init"}]}
    _write_scenario(sc_dir, git_spec=spec)
    sc = runner.load_scenario(sc_dir)
    assert sc.git_spec == spec


def test_validate_git_spec_valid_spec_is_clean():
    spec = {
        "version": 1,
        "ops": [
            {"op": "init", "defaultBranch": "main"},
            {"op": "write", "path": "a.txt", "content": "x"},
            {"op": "add", "paths": ["."]},
            {"op": "commit", "message": "m"},
        ],
    }
    assert runner.validate_git_spec(spec, "p") == []


def test_validate_git_spec_rejects_bad_version():
    """최소 테스트 7: version != 1 은 거부."""
    errors = runner.validate_git_spec({"version": 2, "ops": [{"op": "init"}]}, "p")
    assert any("version" in e for e in errors)


def test_validate_git_spec_rejects_missing_version():
    errors = runner.validate_git_spec({"ops": [{"op": "init"}]}, "p")
    assert any("version" in e for e in errors)


def test_validate_git_spec_rejects_empty_op_list():
    errors = runner.validate_git_spec({"version": 1, "ops": []}, "p")
    assert any("ops" in e for e in errors)


def test_validate_git_spec_rejects_absolute_write_path():
    """최소 테스트 3: 절대경로 write.path 는 거부."""
    spec = {
        "version": 1,
        "ops": [{"op": "write", "path": "/etc/passwd", "content": "x"}],
    }
    errors = runner.validate_git_spec(spec, "p")
    assert errors and any("write.path" in e for e in errors)


def test_validate_git_spec_rejects_parent_traversal_write_path():
    """최소 테스트 4: `..` 포함 write.path 는 거부."""
    spec = {
        "version": 1,
        "ops": [{"op": "write", "path": "../escape.txt", "content": "x"}],
    }
    errors = runner.validate_git_spec(spec, "p")
    assert errors and any("write.path" in e for e in errors)


def test_validate_git_spec_rejects_op_outside_whitelist():
    """최소 테스트 5: 화이트리스트 밖 연산(`run`)은 거부."""
    spec = {"version": 1, "ops": [{"op": "run", "cmd": "id"}]}
    errors = runner.validate_git_spec(spec, "p")
    assert any("화이트리스트" in e for e in errors)


def test_validate_git_spec_rejects_missing_required_field():
    errors = runner.validate_git_spec({"version": 1, "ops": [{"op": "commit"}]}, "p")
    assert any("message" in e for e in errors)


def test_validate_git_spec_not_object_is_rejected():
    errors = runner.validate_git_spec([], "p")
    assert errors


def test_validate_scenario_catches_git_json_path_escape(tmp_path):
    """validate_scenario가 git.json 스키마 위반을 --validate 경로에서 잡는다."""
    sc_dir = tmp_path / "git-workflow" / "bad-git"
    _write_scenario(
        sc_dir,
        git_spec={
            "version": 1,
            "ops": [{"op": "write", "path": "/etc/passwd", "content": "x"}],
        },
    )
    errors = runner.validate_scenario(sc_dir, agents_root=runner.AGENTS_ROOT)
    assert any("write.path" in e for e in errors)


def test_validate_scenario_catches_git_json_malformed_json(tmp_path):
    sc_dir = tmp_path / "git-workflow" / "malformed-git"
    _write_scenario(sc_dir)
    (sc_dir / "git.json").write_text("{not json")
    errors = runner.validate_scenario(sc_dir, agents_root=runner.AGENTS_ROOT)
    assert any("git.json 파싱 실패" in e for e in errors)


def test_validate_scenario_clean_git_json_has_no_errors(tmp_path):
    sc_dir = tmp_path / "git-workflow" / "clean-git"
    _write_scenario(
        sc_dir,
        git_spec={
            "version": 1,
            "ops": [
                {"op": "init", "defaultBranch": "main"},
                {"op": "write", "path": "a.txt", "content": "x"},
                {"op": "add", "paths": ["."]},
                {"op": "commit", "message": "m"},
            ],
        },
    )
    errors = runner.validate_scenario(sc_dir, agents_root=runner.AGENTS_ROOT)
    assert errors == []


def test_materialize_git_repo_creates_log_and_branch(tmp_path):
    """최소 테스트 2: 정상 git.json → 실체화 후 git log/git branch가 기대대로 나온다."""
    work = tmp_path / "work"
    work.mkdir()
    spec = {
        "version": 1,
        "ops": [
            {"op": "init", "defaultBranch": "main"},
            {
                "op": "write",
                "path": "src/app.py",
                "content": "def f():\n    return 1\n",
            },
            {"op": "add", "paths": ["."]},
            {"op": "commit", "message": "feat: initial"},
            {"op": "branch", "name": "feature/x"},
            {"op": "checkout", "ref": "feature/x"},
            {
                "op": "write",
                "path": "src/app.py",
                "content": "def f():\n    return 2\n",
            },
            {"op": "add", "paths": ["."]},
            {"op": "commit", "message": "feat: change to 2"},
            {"op": "checkout", "ref": "main"},
        ],
    }
    runner.materialize_git_repo(work, spec)

    log = subprocess.run(
        ["git", "-C", str(work), "log", "--all", "--format=%B"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "feat: initial" in log
    assert "feat: change to 2" in log

    branches = subprocess.run(
        ["git", "-C", str(work), "branch", "--list"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "feature/x" in branches

    status = subprocess.run(
        ["git", "-C", str(work), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert status.strip() == ""

    current = subprocess.run(
        ["git", "-C", str(work), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert current == "main"


def test_materialize_git_repo_write_path_escape_raises(tmp_path):
    """실체화 자체도 방어적으로 경로 탈출을 거부한다 (검증 우회 경로 대비, D-2)."""
    import pytest as _pytest

    work = tmp_path / "work"
    work.mkdir()
    spec = {
        "version": 1,
        "ops": [
            {"op": "init"},
            {"op": "write", "path": "../escape.txt", "content": "x"},
        ],
    }
    with _pytest.raises(RuntimeError):
        runner.materialize_git_repo(work, spec)
    # 탈출 대상 파일이 실제로 생성되지 않았는지 확인 — 거부가 부작용 없이 일어난다.
    assert not (tmp_path / "escape.txt").exists()


def test_materialize_git_repo_unknown_op_raises(tmp_path):
    import pytest as _pytest

    work = tmp_path / "work"
    work.mkdir()
    with _pytest.raises(RuntimeError):
        runner.materialize_git_repo(work, {"version": 1, "ops": [{"op": "run"}]})


def test_materialize_git_repo_failed_git_command_raises(tmp_path):
    """최소 테스트 6 전제: 실패하는 git 명령(존재하지 않는 ref로 checkout)은 예외를 던진다."""
    import pytest as _pytest

    work = tmp_path / "work"
    work.mkdir()
    spec = {
        "version": 1,
        "ops": [{"op": "init"}, {"op": "checkout", "ref": "no-such-branch"}],
    }
    with _pytest.raises(RuntimeError):
        runner.materialize_git_repo(work, spec)


def test_run_scenario_git_materialize_failure_is_error(tmp_path):
    """최소 테스트 6: 실체화 중 git 명령 실패 → run_scenario가 error를 반환하고
    pass가 아니다. claude 호출 전에 실패하므로 claude 부재와 무관하게 검증 가능."""
    sc = _scenario(
        tmp_path,
        {"assertions": [{"type": "output_regex", "pattern": "x"}]},
    )
    sc.git_spec = {
        "version": 1,
        "ops": [{"op": "init"}, {"op": "checkout", "ref": "no-such-branch"}],
    }
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["status"] == "error"
    assert res["checks"][0]["type"] == "git_materialize"
    assert "git.json 실체화 실패" in res["checks"][0]["detail"]


def test_run_scenario_without_git_spec_skips_materialize(tmp_path, monkeypatch):
    """git_spec=None인 시나리오는 실체화를 아예 시도하지 않는다 (회귀 없음)."""

    def boom(*a, **k):
        raise AssertionError("git_spec이 None인데 materialize_git_repo가 호출됨")

    monkeypatch.setattr(runner, "materialize_git_repo", boom)

    class R:
        returncode = 0
        stdout = "x"
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: R())
    sc = _scenario(tmp_path, {"assertions": [{"type": "output_regex", "pattern": "x"}]})
    assert sc.git_spec is None
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["status"] == "pass"


# ---------------------------------------------------------------------------
# 앞 단계 보완 (W-023 Stage 1 — decision-log D-1): config op 제거
# ---------------------------------------------------------------------------


def test_validate_git_spec_rejects_config_op():
    """config는 화이트리스트 **안**의 연산만으로 임의 코드 실행이 성립함이
    실증돼 제거됐다(decision-log D-1) — 이제 화이트리스트 밖 연산으로 거부된다."""
    spec = {"version": 1, "ops": [{"op": "config", "key": "user.name", "value": "x"}]}
    errors = runner.validate_git_spec(spec, "p")
    assert any("화이트리스트" in e for e in errors)


def test_materialize_git_repo_rejects_config_op(tmp_path):
    import pytest as _pytest

    work = tmp_path / "work"
    work.mkdir()
    spec = {
        "version": 1,
        "ops": [
            {"op": "init"},
            {"op": "config", "key": "user.name", "value": "x"},
        ],
    }
    with _pytest.raises(RuntimeError):
        runner.materialize_git_repo(work, spec)


# ---------------------------------------------------------------------------
# git 상태 어서션 3종 (W-023 Stage 1 — D-5)
# ---------------------------------------------------------------------------


def _git_repo(tmp_path, extra_op_list=None):
    """공용 fixture: materialize_git_repo로 최소 저장소(커밋 1개)를 만든다."""
    work = tmp_path / "repo"
    work.mkdir()
    ops = [
        {"op": "init", "defaultBranch": "main"},
        {"op": "write", "path": "a.txt", "content": "hello\n"},
        {"op": "add", "paths": ["."]},
        {"op": "commit", "message": "feat: initial commit"},
    ]
    if extra_op_list:
        ops += extra_op_list
    runner.materialize_git_repo(work, {"version": 1, "ops": ops})
    return work


def test_check_assertion_git_log_contains_pass(tmp_path):
    work = _git_repo(tmp_path)
    ok, _ = runner.check_assertion(
        {"type": "git_log_contains", "pattern": "initial commit"}, "", work
    )
    assert ok is True


def test_check_assertion_git_log_contains_fail(tmp_path):
    """red 실증 1: 존재하지 않는 패턴 → fail."""
    work = _git_repo(tmp_path)
    ok, detail = runner.check_assertion(
        {"type": "git_log_contains", "pattern": "no-such-pattern-xyz"}, "", work
    )
    assert ok is False
    assert "expect=True actual=False" in detail


def test_check_assertion_git_log_contains_expect_false(tmp_path):
    work = _git_repo(tmp_path)
    ok, _ = runner.check_assertion(
        {
            "type": "git_log_contains",
            "pattern": "no-such-pattern-xyz",
            "expect": False,
        },
        "",
        work,
    )
    assert ok is True


def test_check_assertion_git_log_contains_rejects_option_injection_ref(tmp_path):
    work = _git_repo(tmp_path)
    ok, detail = runner.check_assertion(
        {"type": "git_log_contains", "pattern": "x", "ref": "--upload-pack=x"},
        "",
        work,
    )
    assert ok is False
    assert "옵션 주입" in detail


def test_check_assertion_git_branch_exists_pass(tmp_path):
    work = _git_repo(tmp_path, extra_op_list=[{"op": "branch", "name": "feature/x"}])
    ok, _ = runner.check_assertion(
        {"type": "git_branch_exists", "branch": "feature/x"}, "", work
    )
    assert ok is True


def test_check_assertion_git_branch_exists_fail(tmp_path):
    """red 실증 2: 존재하지 않는 브랜치 → fail."""
    work = _git_repo(tmp_path)
    ok, detail = runner.check_assertion(
        {"type": "git_branch_exists", "branch": "no-such-branch"}, "", work
    )
    assert ok is False
    assert "expect=True actual=False" in detail


def test_check_assertion_git_branch_exists_expect_false(tmp_path):
    work = _git_repo(tmp_path)
    ok, _ = runner.check_assertion(
        {"type": "git_branch_exists", "branch": "no-such-branch", "expect": False},
        "",
        work,
    )
    assert ok is True


def test_check_assertion_git_branch_exists_rejects_option_injection_branch(tmp_path):
    work = _git_repo(tmp_path)
    ok, detail = runner.check_assertion(
        {"type": "git_branch_exists", "branch": "--list"}, "", work
    )
    assert ok is False
    assert "옵션 주입" in detail


def test_check_assertion_git_status_clean_pass(tmp_path):
    work = _git_repo(tmp_path)
    ok, _ = runner.check_assertion({"type": "git_status_clean"}, "", work)
    assert ok is True


def test_check_assertion_git_status_clean_fail(tmp_path):
    """red 실증 3: 더러운 워킹트리 → fail."""
    work = _git_repo(tmp_path)
    (work / "dirty.txt").write_text("uncommitted\n")
    ok, detail = runner.check_assertion({"type": "git_status_clean"}, "", work)
    assert ok is False
    assert "expect=True actual=False" in detail


def test_check_assertion_git_status_clean_expect_false(tmp_path):
    work = _git_repo(tmp_path)
    (work / "dirty.txt").write_text("uncommitted\n")
    ok, _ = runner.check_assertion(
        {"type": "git_status_clean", "expect": False}, "", work
    )
    assert ok is True


def test_check_assertion_git_assertions_fail_closed_on_non_repo(tmp_path):
    """비-저장소 디렉토리에서 3종 전부 명시적 fail — 'porcelain 비었으니 clean'
    오독으로 거짓 green이 나오는 것을 막는다."""
    non_repo = tmp_path / "not-a-repo"
    non_repo.mkdir()
    for assertion in (
        {"type": "git_log_contains", "pattern": "x"},
        {"type": "git_branch_exists", "branch": "main"},
        {"type": "git_status_clean"},
    ):
        ok, detail = runner.check_assertion(assertion, "", non_repo)
        assert ok is False, assertion
        assert "비-저장소" in detail


# ---------------------------------------------------------------------------
# W-023 리뷰 Critical — `write` 로 `.git/` 에 쓰면 제거한 config op 이 되살아난다
#
# _resolve_in_repo 는 "base 밖으로 나가는가"만 본다. `.git/config` 는 base **안**이라
# 통과하는데, 거기에 `[filter "x"] clean = <셸 명령>` 을 심고 `.gitattributes`(write)
# + `add` 하면 **실행 비트 없이** 발화한다 — 화이트리스트에서 config 를 뺀 조치가
# write 경유로 무효화된다. 아래 테스트가 그 경로를 고정한다.
# ---------------------------------------------------------------------------

_GIT_INTERNAL_PATHS = [
    ".git/config",
    ".GIT/config",  # macOS 기본 FS는 대소문자 비구분
    "sub/.git/config",
    ".git/hooks/pre-commit",
]


def _git_internal_spec(bad_path: str) -> dict:
    return {
        "version": 1,
        "ops": [
            {"op": "init"},
            {"op": "write", "path": bad_path, "content": "x"},
        ],
    }


def test_validate_git_spec_rejects_git_internal_write():
    for bad_path in _GIT_INTERNAL_PATHS:
        errors = runner.validate_git_spec(_git_internal_spec(bad_path), "sc")
        assert any(".git/" in e for e in errors), (
            f"{bad_path} 가 오프라인 검증에서 거부되지 않았다: {errors}"
        )


def test_materialize_git_repo_blocks_git_internal_write(tmp_path):
    """검증을 거치지 않고 직접 호출되는 경로에서도 막혀야 한다 (fail-closed)."""
    import pytest as _pytest

    for i, bad_path in enumerate(_GIT_INTERNAL_PATHS):
        work = tmp_path / f"w{i}"
        work.mkdir()
        with _pytest.raises(RuntimeError, match=r"\.git/"):
            runner.materialize_git_repo(work, _git_internal_spec(bad_path))


def test_git_internal_block_does_not_break_dotfiles(tmp_path):
    """`.gitattributes`·`.gitignore` 같은 정상 dotfile 은 계속 허용된다 —
    위험한 것은 저장소 메타디렉토리(.git/)이지 점으로 시작하는 이름이 아니다."""
    spec = {
        "version": 1,
        "ops": [
            {"op": "init"},
            {"op": "write", "path": ".gitignore", "content": "*.pyc\n"},
            {"op": "write", "path": ".gitattributes", "content": "* text=auto\n"},
            {"op": "add", "paths": ["."]},
            {"op": "commit", "message": "chore: dotfiles"},
        ],
    }
    assert runner.validate_git_spec(spec, "sc") == []
    runner.materialize_git_repo(tmp_path, spec)
    assert (tmp_path / ".gitignore").is_file()
    assert (tmp_path / ".gitattributes").is_file()


# ---------------------------------------------------------------------------
# W-023 리뷰 C-2 — 실체화 경로에 옵션 주입 가드가 없었다
#
# 화이트리스트가 "연산 8종"을 제한해도 전달 인자가 무제한이면 보안 주장이 성립하지
# 않는다. _check_git_assertion 은 ref/branch 에 이미 이 경계를 세웠는데 실체화
# 경로에는 없었다 — 같은 파일 안의 방어 비대칭이었다.
# ---------------------------------------------------------------------------

_OPTION_INJECTION_OPS = [
    {"op": "add", "paths": ["--renormalize", "."]},
    {"op": "checkout", "ref": "--orphan"},
    {"op": "branch", "name": "--force"},
    {"op": "merge", "ref": "--strategy-option=theirs"},
    {"op": "tag", "name": "--delete"},
    {"op": "init", "defaultBranch": "--bare"},
]


def test_git_args_for_rejects_option_like_values():
    import pytest as _pytest

    for op_entry in _OPTION_INJECTION_OPS:
        with _pytest.raises(RuntimeError, match="옵션 주입"):
            runner._git_args_for(op_entry)


def test_git_args_for_uses_argument_terminator():
    """`--` 종결자가 붙는지 — 값이 옵션으로 재해석되는 것을 막는 두 번째 층."""
    assert runner._git_args_for({"op": "add", "paths": ["."]}) == ["add", "--", "."]
    assert runner._git_args_for({"op": "checkout", "ref": "feature/x"}) == [
        "checkout",
        "-q",
        "feature/x",
        "--",
    ]


def test_git_args_for_accepts_normal_values():
    assert runner._git_args_for({"op": "branch", "name": "feature/x"}) == [
        "branch",
        "feature/x",
    ]
    assert runner._git_args_for({"op": "merge", "ref": "feature/x"}) == [
        "merge",
        "--no-edit",
        "feature/x",
    ]
    # write 는 git 명령이 아니다 — 조립기는 None 을 돌려주고 호출부가 파일로 처리한다.
    assert runner._git_args_for({"op": "write", "path": "a", "content": "b"}) is None


# ---------------------------------------------------------------------------
# W-023 리뷰 W-5 — file_unchanged 와 git.json write 가 겹치면 영구 fail
#
# file_unchanged 는 실행 후 파일을 **원본 fixture** 와 바이트 비교하는데, git.json 의
# write 는 실체화 단계에서 같은 파일을 덮어쓴다. 겹치면 에이전트가 아무것도 하지
# 않아도 fail 이고, 메시지는 "변조됨 (게이밍 의심)" 이라 원인을 정반대로 오도한다.
# ---------------------------------------------------------------------------


def _write_overlap_scenario(root: Path, *, git_op_list: list, assertions: list) -> Path:
    sc = root / "fix-bugs" / "sc"
    (sc / "fixture").mkdir(parents=True)
    (sc / "fixture" / "a.txt").write_text("x\n", encoding="utf-8")
    (sc / "task.md").write_text("t", encoding="utf-8")
    (sc / "git.json").write_text(
        json.dumps({"version": 1, "ops": git_op_list}), encoding="utf-8"
    )
    (sc / "expect.json").write_text(
        json.dumps({"assertions": assertions}), encoding="utf-8"
    )
    return sc


def test_validate_scenario_rejects_file_unchanged_overlapping_git_write(tmp_path):
    sc = _write_overlap_scenario(
        tmp_path,
        git_op_list=[
            {"op": "init"},
            {"op": "write", "path": "a.txt", "content": "y\n"},
        ],
        assertions=[{"type": "file_unchanged", "file": "a.txt"}],
    )
    errors = runner.validate_scenario(sc, agents_root=runner.AGENTS_ROOT)
    assert any("겹침" in e for e in errors), errors


def test_validate_scenario_allows_file_unchanged_without_overlap(tmp_path):
    """겹치지 않으면 통과해야 한다 — 과잉 차단이 아님을 고정한다."""
    sc = _write_overlap_scenario(
        tmp_path,
        git_op_list=[
            {"op": "init"},
            {"op": "write", "path": "b.txt", "content": "y\n"},
        ],
        assertions=[{"type": "file_unchanged", "file": "a.txt"}],
    )
    errors = runner.validate_scenario(sc, agents_root=runner.AGENTS_ROOT)
    assert not any("겹침" in e for e in errors), errors


# ---------------------------------------------------------------------------
# 하네스 결합점 봉쇄 (D-12/§12.4, 수용 16) — grep -c claude는 판정 기준이 아니다:
# "claude_exit" 같은 CLI 무관 문자열이 카운트를 오염시킨다. ast로 리터럴
# "claude" 노드의 실제 위치만 본다.
# ---------------------------------------------------------------------------


def _claude_code_harness_line_range(tree: ast.Module) -> tuple[int, int]:
    harness = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.ClassDef) and n.name == "ClaudeCodeHarness"
        ),
        None,
    )
    assert harness is not None, "ClaudeCodeHarness 클래스를 찾을 수 없음"
    end = max(getattr(n, "end_lineno", harness.lineno) for n in ast.walk(harness))
    return harness.lineno, end


def test_claude_literal_confined_to_claude_code_harness():
    """CLI 리터럴 "claude"는 ClaudeCodeHarness 구현체 안에만 존재해야 한다.
    run_scenario_cmd/judge_cmd/is_available 세 결합점 모두 여기로 모여야 하며,
    run.py 본문(run_scenario/run_judge/run_all 등)에는 리터럴이 하나도 없어야 한다."""
    src = Path(runner.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    start, end = _claude_code_harness_line_range(tree)

    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and node.value == "claude"
        and not (start <= node.lineno <= end)
    ]
    assert offenders == [], (
        f"'claude' 리터럴이 ClaudeCodeHarness({start}-{end}) 밖에 있음: 라인 {offenders}"
    )


def test_claude_code_harness_calls_are_subprocess_run_or_shutil_which_first_arg():
    """ClaudeCodeHarness 안의 "claude" 리터럴이 실제로 subprocess.run 첫 인자
    (judge_cmd/run_scenario_cmd가 만드는 커맨드 리스트가 흘러가는 지점)이거나
    shutil.which 인자로만 쓰이는지 — 즉 셋(run_scenario_cmd/judge_cmd/
    is_available)이 프로토콜이 약속한 결합점 모양을 실제로 갖췄는지 확인한다."""
    src = Path(runner.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)

    harness = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef) and n.name == "ClaudeCodeHarness"
    )
    methods = {n.name: n for n in harness.body if isinstance(n, ast.FunctionDef)}
    assert set(methods) == {"run_scenario_cmd", "judge_cmd", "is_available"}

    def _returns_or_builds_claude_list(fn: ast.FunctionDef) -> bool:
        for node in ast.walk(fn):
            if isinstance(node, ast.List) and any(
                isinstance(elt, ast.Constant) and elt.value == "claude"
                for elt in node.elts
            ):
                return True
        return False

    assert _returns_or_builds_claude_list(methods["run_scenario_cmd"])
    assert _returns_or_builds_claude_list(methods["judge_cmd"])

    which_calls = [
        node
        for node in ast.walk(methods["is_available"])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "which"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "claude"
    ]
    assert which_calls, "is_available은 shutil.which('claude')를 호출해야 한다"


def test_run_scenario_and_run_judge_use_harness_indirection(monkeypatch, tmp_path):
    """run_scenario/run_judge가 HARNESS(Harness 프로토콜)를 거쳐 커맨드를 얻는지 —
    HARNESS를 가짜로 바꿔치면 다른(비-claude) 커맨드가 subprocess.run에 전달돼야
    한다. 이것이 되돌려-FAIL 대상: build_claude_command나 run_judge가 다시
    리터럴 "claude"를 직접 조립하도록 되돌리면 이 테스트가 깨진다."""

    class FakeHarness:
        def run_scenario_cmd(self, agent, task):
            return ["fake-harness-cli", "-p", task]

        def judge_cmd(self, prompt):
            return ["fake-harness-cli", "-p", prompt]

        def is_available(self):
            return True

    captured_cmds = []

    class R:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return R()

    monkeypatch.setattr(runner, "HARNESS", FakeHarness())
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    sc = _scenario(
        tmp_path,
        {"assertions": [{"type": "output_contains_any", "values": ["ok"]}]},
    )
    runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert captured_cmds
    assert captured_cmds[0][0] == "fake-harness-cli"

    captured_cmds.clear()
    runner.run_judge("stdout text", {"rubric": "r"}, timeout=5)
    assert captured_cmds
    assert captured_cmds[0][0] == "fake-harness-cli"


class TestFailExcerpt:
    """ATK-011 / L-3 — 발췌의 인덱스 정렬과 시크릿 마스킹.

    ① 인덱스를 `_norm(stdout)`(NFC + lower) 에서 계산해 **원본** `stdout` 을 잘랐다.
       두 변환 모두 길이를 바꾸므로(NFD 자모 3 → NFC 음절 1) 한글이 섞인 출력에서
       오프셋이 밀려 **엉뚱한 구간**이 발췌됐다.
    ② 발췌가 그대로 리포트에 실렸다 — 리포트는 터미널에 머물지 않는다
       (`warning-signal.md` §6). 시크릿 형식 문자열은 가려야 한다.
    """

    FAILED_CHECK: ClassVar[list[dict]] = [
        {"ok": False, "detail": "발견됨 ['NEEDLE_MARKER']"}
    ]

    def test_excerpt_is_centred_on_the_needle_with_decomposed_hangul(self):
        """NFD 한글이 앞에 깔려 있어도 발췌가 needle 주변이어야 한다."""
        # NFD(자모 분해) — macOS 파일명 출력이 이 형태다. 코드포인트 3개 = 음절 1개.
        prefix = unicodedata.normalize("NFD", "한글" * 400)
        assert len(prefix) > len(unicodedata.normalize("NFC", prefix))
        stdout = prefix + "NEEDLE_MARKER" + ("x" * 200)

        excerpt = runner._fail_excerpt(stdout, self.FAILED_CHECK)

        assert excerpt is not None
        assert "NEEDLE_MARKER" in excerpt

    def test_excerpt_masks_secret_shaped_strings(self):
        """형식-확정 시크릿은 라벨로 치환돼야 한다."""
        token = "AKIA" + "Q" * 16  # 형식만 맞춘 가짜 — 실제 자격증명이 아니다
        stdout = f"NEEDLE_MARKER aws={token} done"

        excerpt = runner._fail_excerpt(stdout, self.FAILED_CHECK)

        assert excerpt is not None
        assert token not in excerpt
        assert "가려짐" in excerpt

    def test_excerpt_is_suppressed_when_patterns_unavailable(self, monkeypatch):
        """마스킹 패턴을 못 읽으면 발췌를 내지 않는다 — fail-closed."""
        monkeypatch.setattr(runner, "_secret_patterns", lambda: None)

        excerpt = runner._fail_excerpt("NEEDLE_MARKER secret-ish", self.FAILED_CHECK)

        assert excerpt is not None
        assert "발췌 생략" in excerpt
        assert "NEEDLE_MARKER" not in excerpt

    def test_secret_patterns_come_from_the_hook(self):
        """패턴 목록을 복사하지 않고 훅에서 읽는다(SSOT)."""
        patterns = runner._secret_patterns()
        assert patterns, "훅에서 시크릿 패턴을 읽지 못했다"
        assert any("AKIA" in p for p, _ in patterns)
