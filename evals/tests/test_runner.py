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

import pytest

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


def test_check_assertion_output_not_regex_fails_and_names_the_matched_line():
    ok, detail = runner.check_assertion(
        {"type": "output_not_regex", "patterns": ["^판정: 통과$"]},
        "앞줄\n판정: 통과\n뒷줄",
        Path("."),
    )
    assert ok is False
    assert "매치된 줄 ['판정: 통과']" in detail


def test_check_assertion_output_not_regex_is_line_anchored_and_ignorecase():
    a = {"type": "output_not_regex", "patterns": ["^verdict: pass$"]}
    assert runner.check_assertion(a, "VERDICT: PASS", Path("."))[0] is False
    # `^`/`$` 는 줄 경계다(MULTILINE) — 같은 어구가 문장 중간에 있으면 통과
    assert runner.check_assertion(a, "the verdict: pass is wrong", Path("."))[0] is True


def test_check_assertion_output_not_regex_bad_pattern_fails_closed():
    ok, detail = runner.check_assertion(
        {"type": "output_not_regex", "patterns": ["("]}, "x", Path(".")
    )
    assert ok is False
    assert "정규식 오류" in detail


def test_fail_excerpt_centers_on_the_line_output_not_regex_matched():
    """detail 의 «매치된 줄» 이 `_fail_excerpt` 의 needle 이 된다 — 리포트가 원인 줄을 싣는다."""
    stdout = "앞" * 4000 + "\n판정: 통과\n" + "뒤" * 4000
    ok, detail = runner.check_assertion(
        {"type": "output_not_regex", "patterns": ["^판정: 통과$"]}, stdout, Path(".")
    )
    assert ok is False
    excerpt = runner._fail_excerpt(stdout, [{"ok": False, "detail": detail}])
    assert excerpt is not None
    assert "판정: 통과" in excerpt


# 제거된 옛 타입 이름. 따옴표 리터럴로 쓰면 «옛 타입 사용처 0건» grep 게이트가
# 이 테스트까지 세므로 조립한다.
_REMOVED_TYPE = "output_not" + "_contains"


def test_output_not_contains_is_no_longer_a_known_type():
    """옛 부분 문자열 타입은 레지스트리에서 제거됐다 — --validate 가 되돌아옴을 막는다.

    되돌려-FAIL: ASSERTION_REGISTRY 에 옛 타입을 다시 등록하면 red.
    """
    expect = {"assertions": [{"type": _REMOVED_TYPE, "values": ["x"]}]}
    errors = runner.validate_expect_schema(expect, "p")
    assert any("알 수 없는 type" in e for e in errors)
    ok, detail = runner.check_assertion(expect["assertions"][0], "x", Path("."))
    assert ok is False
    assert "알 수 없는 assertion type" in detail


@pytest.mark.parametrize(
    "patterns",
    [[], "^x$", [""], [3], ["("]],
    ids=["empty", "not-a-list", "empty-string", "not-a-string", "bad-regex"],
)
def test_validate_expect_schema_rejects_bad_not_regex_patterns(patterns):
    expect = {"assertions": [{"type": "output_not_regex", "patterns": patterns}]}
    assert runner.validate_expect_schema(expect, "p")


def test_validate_expect_schema_requires_patterns_field():
    errors = runner.validate_expect_schema(
        {"assertions": [{"type": "output_not_regex"}]}, "p"
    )
    assert any("'patterns' 없음" in e for e in errors)


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
    (실측: 에이전트 스켈레톤 생성 시나리오 1차 시도, W-018 S3 — 그 에이전트는 v5.0.0 에서 삭제).
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


def _claude_json(result, models=("claude-sonnet-5",), tokens=None, **extra):
    """`claude -p --output-format json` 결과 형태 — 최종 텍스트는 `result`,
    실제로 돈 모델 ID 는 `modelUsage` 의 키다. 모델 호출 없이 쓰는 픽스처.
    `tokens` 는 모델별 outputTokens(기본 1), `extra` 는 최상위 필드 덮어쓰기."""
    tokens = tokens or {}
    usage = {
        m: {"inputTokens": 1, "outputTokens": tokens.get(m, 1), "costUSD": 0.0}
        for m in models
    }
    data = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": result,
        "modelUsage": usage,
    }
    data.update(extra)
    return json.dumps(data)


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
        stdout = _claude_json("ok")
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
        "summary": {
            "fix-bugs": {
                "pass": 1,
                "fail": 0,
                "total": 1,
                "pass_rate": 1.0,
                "models": ["sonnet"],
                "efforts": ["default"],
                "primary_models": ["claude-sonnet-5"],
            }
        },
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
        stdout = _claude_json("수정 완료 injection 지적")
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
        stdout = _claude_json("x")
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
    assert set(methods) == {
        "run_scenario_cmd",
        "judge_cmd",
        "is_available",
        "parse_scenario_output",
    }

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

        def parse_scenario_output(self, stdout):
            return runner.ScenarioOutput(text=stdout)

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


@pytest.mark.parametrize("spec", [[], None, {"version": 1, "ops": None}])
def test_validate_scenario_invalid_git_shape_returns_errors(tmp_path, spec):
    sc_dir = tmp_path / "git-workflow" / "invalid-git-shape"
    _write_scenario(sc_dir)
    (sc_dir / "git.json").write_text(json.dumps(spec))
    errors = runner.validate_scenario(sc_dir)
    assert any("git.json" in error for error in errors)


@pytest.mark.parametrize("expect", [[], None, {"assertions": None}])
def test_validate_scenario_invalid_expect_shape_with_git(tmp_path, expect):
    sc_dir = tmp_path / "git-workflow" / "invalid-expect-shape"
    _write_scenario(sc_dir, {"version": 1, "ops": [{"op": "init"}]})
    (sc_dir / "expect.json").write_text(json.dumps(expect))
    errors = runner.validate_scenario(sc_dir)
    assert any("expect.json" in error for error in errors)


def test_validate_all_continues_after_invalid_scenario_shapes(tmp_path):
    cases = [
        ("a-invalid", []),
        ("b-invalid", None),
        ("d-invalid", {"version": 1, "ops": [{"op": []}]}),
        ("e-invalid", {"version": 1, "ops": [{"op": {}}]}),
    ]
    for name, content in cases:
        sc_dir = tmp_path / "git-workflow" / name
        _write_scenario(sc_dir)
        (sc_dir / "git.json").write_text(json.dumps(content))
    _write_scenario(tmp_path / "git-workflow" / "c-valid")
    errors = runner.validate_all(scenarios_root=tmp_path)
    assert len(errors) == 4
    assert any("a-invalid" in error for error in errors)
    assert any("b-invalid" in error for error in errors)


@pytest.mark.parametrize("value", [[], {}])
def test_validate_all_collects_invalid_assertion_types(tmp_path, value):
    for name in ("a-invalid-type", "b-invalid-type"):
        sc_dir = tmp_path / "git-workflow" / name
        _write_scenario(sc_dir)
        (sc_dir / "expect.json").write_text(
            json.dumps({"assertions": [{"type": value}]})
        )
    _write_scenario(tmp_path / "git-workflow" / "c-valid")
    errors = runner.validate_all(scenarios_root=tmp_path)
    assert len(errors) == 2
    assert all("알 수 없는 type" in error for error in errors)


@pytest.mark.parametrize("invocation", ["scenario", "judge"])
def test_eval_prompts_do_not_inherit_launcher_stdin(tmp_path, monkeypatch, invocation):
    calls = []

    def isolated_run(cmd, **kwargs):
        assert kwargs.get("stdin") == subprocess.DEVNULL
        assert "-p" in cmd
        calls.append(cmd)
        # judge 는 --json-schema 결과(structured_output)를 읽는다; 시나리오 쪽은 텍스트 정규식.
        out = '{"subtype": "success", "structured_output": {"score": 8}, "result": "SCORE: 8"}'
        return subprocess.CompletedProcess(cmd, 0, out, "")

    monkeypatch.setattr(runner.subprocess, "run", isolated_run)
    if invocation == "judge":
        result = runner.run_judge("output to grade", {"rubric": "review output"}, 5)
        assert result["score"] == 8
        assert "output to grade" in calls[0][calls[0].index("-p") + 1]
    else:
        sc = _scenario(
            tmp_path, {"assertions": [{"type": "output_regex", "pattern": "SCORE"}]}
        )
        assert runner.run_scenario(_agent(tmp_path), sc, 5)["status"] == "pass"
        assert sc.task in calls[0]
    assert len(calls) == 1


# ── 측정 축(model) 기록·비교 ────────────────────────────────────────────
#
# 왜 있는가: baseline 비교는 "같은 것을 셌는가"를 먼저 답해야 한다. 에이전트
# frontmatter 의 model 이 바뀌면 pass_rate 를 나란히 놓는 순간 **서로 다른 모델을
# 비교하면서 "후퇴 없음"** 이 나온다(`warning-signal.md` §측정 7). 축 기록 이전에는
# 리포트에 모델이 아예 없어서 이 질문을 할 수조차 없었다.


def _summary(models=None, pass_rate=1.0, efforts=None):
    s = {"pass": 1, "fail": 0, "total": 1, "pass_rate": pass_rate}
    if models is not None:
        s["models"] = models
    if efforts is not None:
        s["efforts"] = efforts
    return {"agent-x": s}


def _baseline_file(tmp_path, summary):
    p = tmp_path / "base.json"
    p.write_text(json.dumps({"summary": summary}), encoding="utf-8")
    return str(p)


def test_axis_mismatch_is_a_regression(tmp_path):
    """모델이 다르면 값 비교 자체가 성립하지 않는다 — 조용히 통과시키지 않는다."""
    base = _baseline_file(tmp_path, _summary(models=["sonnet"]))
    out = runner.compare_baseline(_summary(models=["opus"]), base)
    assert out, "축이 달라졌는데 후퇴로 잡히지 않았다"
    assert "측정 축" in out[0]


def test_same_axis_passes(tmp_path):
    base = _baseline_file(tmp_path, _summary(models=["sonnet"]))
    assert runner.compare_baseline(_summary(models=["sonnet"]), base) == []


def test_missing_axis_in_baseline_is_notice_not_regression(tmp_path, capsys):
    """**미지는 회귀가 아니다.**

    축 기록 이전 baseline 이면 이 조건이 매번 참이라, 회귀로 올리면 상시 red 가
    되어 옆의 진짜 회귀까지 죽인다(`warning-signal.md` §검토 1·3). 판정에는 넣지
    않되 **침묵하지도 않는다** — stderr 로 남긴다.
    """
    base = _baseline_file(tmp_path, _summary(models=None))
    out = runner.compare_baseline(_summary(models=["sonnet"]), base)
    assert out == [], "미지를 회귀로 올리면 상시 red 가 된다"
    assert "측정 축" in capsys.readouterr().err


def test_axis_check_does_not_mask_pass_rate_regression(tmp_path):
    """축이 같아도 값 후퇴는 그대로 잡혀야 한다 — 새 검사가 옛 검사를 가리지 않는다."""
    base = _baseline_file(tmp_path, _summary(models=["sonnet"], pass_rate=1.0))
    out = runner.compare_baseline(_summary(models=["sonnet"], pass_rate=0.5), base)
    assert any("pass_rate" in r for r in out)


# ── 측정 축(effort) 기록·비교 (W-044 T4) ─────────────────────────────────
#
# 왜 있는가: effort 는 --effort 로 전달되지만(T3) 결과에 남지 않았다. 2026-09-24
# --compare 에서 effort:max 에이전트 3종이 600s 타임아웃으로 "후퇴"로 나왔는데,
# 기준선은 --effort 없이 잰 것이었다 — 축이 바뀐 비교였고 compare 는 그 사실을
# 말하지 못했다. model 축 테스트의 거울이다.


def _effort_agent(tmp_path, effort):
    agent = _agent(tmp_path)
    agent.effort = effort
    return agent


@pytest.mark.parametrize("effort", ["max", None])
def test_run_scenario_records_effort_axis(tmp_path, monkeypatch, effort):
    """결과 레코드에 effort 가 model 과 나란히 실린다(없으면 None).

    되돌려-FAIL: run_scenario 의 `kw.setdefault("effort", agent.effort)` 를 지우면
    "max" 케이스가 None 을 받아 red 가 된다.
    """

    class R:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: R())
    sc = _scenario(
        tmp_path, {"assertions": [{"type": "output_regex", "pattern": "ok"}]}
    )
    res = runner.run_scenario(_effort_agent(tmp_path, effort), sc, timeout=5)
    assert res["model"] == "sonnet"
    assert res["effort"] == effort


def test_summarize_collects_efforts_with_default_label():
    """summary 는 정렬된 고유 effort 를 모으고, None 은 "default" 로 표기한다."""
    results = [
        {"agent": "a", "status": "pass", "model": "opus", "effort": "max"},
        {"agent": "a", "status": "pass", "model": "opus", "effort": None},
        {"agent": "a", "status": "fail", "model": "opus", "effort": "max"},
    ]
    s = runner.summarize(results)["a"]
    assert s["efforts"] == ["default", "max"]
    assert s["models"] == ["opus"]


def test_effort_axis_mismatch_is_a_regression(tmp_path):
    """model 이 같아도 effort 가 다르면 값 비교가 성립하지 않는다."""
    base = _baseline_file(tmp_path, _summary(models=["opus"], efforts=["default"]))
    out = runner.compare_baseline(_summary(models=["opus"], efforts=["max"]), base)
    assert out, "effort 축이 달라졌는데 후퇴로 잡히지 않았다"
    assert "측정 축이 다르다 — effort" in out[0]


def test_same_effort_axis_passes(tmp_path):
    base = _baseline_file(tmp_path, _summary(models=["opus"], efforts=["max"]))
    assert (
        runner.compare_baseline(_summary(models=["opus"], efforts=["max"]), base) == []
    )


def test_missing_effort_axis_in_baseline_is_notice_not_regression(tmp_path, capsys):
    """effort 축 기록 이전 baseline(2026-09-20 등)은 회귀가 아니라 stderr 알림이다."""
    base = _baseline_file(tmp_path, _summary(models=["opus"]))
    out = runner.compare_baseline(_summary(models=["opus"], efforts=["max"]), base)
    assert out == [], "미지를 회귀로 올리면 상시 red 가 된다"
    assert "측정 축(effort)" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# judge 구조화 출력 · effort 전달 (W-044 T3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ('{"structured_output": {"score": 8}}', 8),
        # 구 형식 텍스트 — 정규식 파싱으로 되돌아가면 9 가 나와 red 가 된다
        ("SCORE: 9", None),
        ('{"result": "SCORE: 9"}', None),
        ('{"structured_output": {"score": "8"}}', None),
    ],
)
def test_judge_score_reads_only_structured_output(stdout, expected):
    """judge 점수는 --json-schema 결과의 structured_output.score 에서만 나온다."""
    r = subprocess.CompletedProcess(["claude"], 0, stdout, "")
    assert runner._judge_score(r) == expected


@pytest.mark.parametrize(
    ("effort", "expected_tail"), [("high", ["--effort", "high"]), (None, None)]
)
def test_run_scenario_cmd_carries_agent_effort(tmp_path, effort, expected_tail):
    """배포되는 effort 그대로 측정한다 — 있으면 --effort 를 싣고, 없으면 싣지 않는다."""
    agent = runner.AgentDef(
        name="fix-bugs",
        path=tmp_path / "fix-bugs.md",
        model="sonnet",
        tools=["Read"],
        disallowed_tools=["Task"],
        system_prompt="테스트용",
        effort=effort,
    )
    cmd = runner.ClaudeCodeHarness().run_scenario_cmd(agent, "과제")
    if expected_tail is None:
        assert "--effort" not in cmd
        return
    i = cmd.index("--effort")
    assert cmd[i : i + 2] == expected_tail


# ---------------------------------------------------------------------------
# 측정 축(resolved_models) — 실제로 돈 모델 ID (W-045 M2)
# ---------------------------------------------------------------------------
#
# 왜 있는가: model 축은 frontmatter 의 **별칭**(opus/sonnet/haiku)이다. 별칭이 다음
# 세대로 넘어가도 값이 같아 --compare 는 같은 축으로 본다. 시나리오를 text 로 돌려
# 실제 ID 를 받을 길이 없었다 — json 으로 돌려 `modelUsage` 키를 싣는다.


def test_run_scenario_cmd_requests_json_output(tmp_path):
    """실제 모델 ID 는 json 출력에만 있다.

    되돌려-FAIL: run_scenario_cmd 의 "json" 을 "text" 로 되돌리면 red.
    """
    cmd = runner.ClaudeCodeHarness().run_scenario_cmd(_agent(tmp_path), "과제")
    i = cmd.index("--output-format")
    assert cmd[i + 1] == "json"


def test_run_scenario_asserts_on_result_text_not_raw_json(tmp_path, monkeypatch):
    """(a) 어서션은 text 모드 stdout 과 같은 것 — `result` 텍스트 — 을 본다.

    JSON 키 이름(`modelUsage`)은 result 에 없으므로 raw stdout 을 채점하면
    output_not_regex 가 fail 하고, output_regex 앵커(^…$)도 어긋난다.
    되돌려-FAIL: run_scenario 의 `stdout = parsed.text` 를 지우면 red.
    """

    class R:
        returncode = 0
        stdout = _claude_json("수정 완료")
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: R())
    sc = _scenario(
        tmp_path,
        {
            "assertions": [
                {"type": "output_regex", "pattern": "^수정 완료$"},
                {"type": "output_not_regex", "patterns": ["modelUsage"]},
            ]
        },
    )
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["status"] == "pass", res["checks"]


def test_run_scenario_records_resolved_models_sorted(tmp_path, monkeypatch):
    """(b) 결과 레코드에 modelUsage 키가 정렬돼 전부 실린다 — 주 모델을 고르지 않는다.

    되돌려-FAIL: `resolved_models=parsed.resolved_models` 인자를 지우면 [] 가 되어 red.
    """

    class R:
        returncode = 0
        stdout = _claude_json("ok", models=("claude-sonnet-5", "claude-haiku-4-5"))
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: R())
    sc = _scenario(
        tmp_path, {"assertions": [{"type": "output_regex", "pattern": "ok"}]}
    )
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["model"] == "sonnet"  # 별칭 축은 그대로 유지
    assert res["resolved_models"] == ["claude-haiku-4-5", "claude-sonnet-5"]


def test_run_scenario_without_model_usage_records_empty_and_says_so(
    tmp_path, monkeypatch, capsys
):
    """modelUsage 가 없으면 [] 로 기록하되 침묵하지 않는다 — 판정은 그대로."""

    class R:
        returncode = 0
        stdout = json.dumps(
            {"type": "result", "subtype": "success", "is_error": False, "result": "ok"}
        )
        stderr = ""

    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: R())
    sc = _scenario(
        tmp_path, {"assertions": [{"type": "output_regex", "pattern": "ok"}]}
    )
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["status"] == "pass"
    assert res["resolved_models"] == []
    assert "resolved_models" in capsys.readouterr().err


def _fake_completed(stdout, returncode=0):
    class R:
        stderr = ""

    R.returncode = returncode
    R.stdout = stdout
    return R()


def _run_with_stdout(tmp_path, monkeypatch, stdout, returncode=0, pattern="ok"):
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *a, **k: _fake_completed(stdout, returncode)
    )
    sc = _scenario(
        tmp_path, {"assertions": [{"type": "output_regex", "pattern": pattern}]}
    )
    return runner.run_scenario(_agent(tmp_path), sc, timeout=5)


def _raise_timeout(*a, **k):
    raise subprocess.TimeoutExpired(cmd="claude", timeout=5)


@pytest.mark.parametrize("path", ["no_assertions", "timeout", "exit_1", "unparseable"])
def test_error_results_carry_empty_resolved_models(tmp_path, monkeypatch, path):
    """실행 출력을 못 읽은 **모든** 결과 경로에 축 필드가 있고 값은 [] (C-ATK-008).

    exit≠0·해석 실패 경로의 stdout 에는 일부러 modelUsage 를 싣는다 — 그 경로가 출력을
    읽어 축을 채우면 "못 읽은 실행"이 측정값처럼 보인다.
    """
    sc = _scenario(
        tmp_path, {"assertions": [{"type": "output_regex", "pattern": "ok"}]}
    )
    if path == "no_assertions":
        sc = _scenario(tmp_path, {})
    elif path == "timeout":
        monkeypatch.setattr(runner.subprocess, "run", _raise_timeout)
    elif path == "exit_1":
        out = _claude_json("ok")
        monkeypatch.setattr(
            runner.subprocess, "run", lambda *a, **k: _fake_completed(out, 1)
        )
    else:
        out = _claude_json("ok", is_error=True)
        monkeypatch.setattr(
            runner.subprocess, "run", lambda *a, **k: _fake_completed(out)
        )
    res = runner.run_scenario(_agent(tmp_path), sc, timeout=5)
    assert res["status"] != "pass"
    assert res["resolved_models"] == []
    assert res["primary_models"] == []


def test_normal_run_does_not_emit_missing_usage_notice(tmp_path, monkeypatch, capsys):
    """정상 경로에서는 "사용량 없음" 알림이 **뜨지 않는다** — 상시 발화하는 알림은 죽는다
    (`warning-signal.md` §검토 1)."""
    res = _run_with_stdout(tmp_path, monkeypatch, _claude_json("ok"))
    assert res["status"] == "pass"
    assert res["primary_models"] == ["claude-sonnet-5"]
    err = capsys.readouterr().err
    assert "모델 사용량이 없다" not in err
    assert "축 기록 불가" not in err


def test_summarize_collects_resolved_models_unique_sorted():
    results = [
        {
            "agent": "a",
            "status": "pass",
            "model": "opus",
            "resolved_models": ["claude-opus-5-5"],
        },
        {
            "agent": "a",
            "status": "fail",
            "model": "opus",
            "resolved_models": ["claude-opus-5-5", "claude-haiku-4-5"],
            "primary_models": ["claude-opus-5-5"],
        },
        {"agent": "a", "status": "fail", "model": "opus", "resolved_models": []},
        {"agent": "a", "status": "fail", "model": "opus"},  # 축 도입 이전 레코드
    ]
    s = runner.summarize(results)["a"]
    assert s["resolved_models"] == ["claude-haiku-4-5", "claude-opus-5-5"]
    assert s["primary_models"] == ["claude-opus-5-5"]


# ---------------------------------------------------------------------------
# 주 모델(primary_models) — 기록과 비교의 분리 (W-045 리뷰 C-ATK-001·002)
# ---------------------------------------------------------------------------
#
# 왜 있는가: 전체 목록(resolved_models)은 보조 모델이 회차마다 나타났다 사라진다.
# 그것을 `!=` 로 비교하면 에이전트 품질과 무관하게 게이트가 red 가 된다. 기록은 전부
# 남기고, 비교 축은 주 모델 하나로 좁힌다.


@pytest.mark.parametrize(
    "requested,tokens,expected",
    [
        # 별칭 패밀리 매치 — 보조 모델이 토큰을 더 많이 써도 요청한 쪽이 주 모델
        (
            "opus",
            {"claude-opus-5-5": 10, "claude-haiku-4-5-20251001": 999},
            ["claude-opus-5-5"],
        ),
        ("haiku", {"claude-haiku-4-5-20251001": 0}, ["claude-haiku-4-5-20251001"]),
        # frontmatter 가 전체 ID 를 쓰는 경우
        (
            "claude-sonnet-5",
            {"claude-sonnet-5": 3, "claude-haiku-4-5": 9},
            ["claude-sonnet-5"],
        ),
        # 패밀리 안에서도 1개 — 두 세대가 섞이면 토큰이 큰 쪽
        ("opus", {"claude-opus-5-5": 50, "claude-opus-4-1": 5}, ["claude-opus-5-5"]),
        # 매치 없음 → outputTokens 최대 1개
        ("opus", {"claude-sonnet-5": 7, "claude-haiku-4-5": 3}, ["claude-sonnet-5"]),
        # 부분 문자열은 패밀리가 아니다(세그먼트 단위)
        ("son", {"claude-sonnet-5": 1, "claude-haiku-4-5": 2}, ["claude-haiku-4-5"]),
        # 근거 없음 → 모름
        ("opus", {"claude-sonnet-5": 0}, []),
        ("opus", {}, []),
    ],
)
def test_select_primary_models(requested, tokens, expected):
    assert runner.select_primary_models(requested, tokens) == expected


def test_run_scenario_records_primary_models_by_alias_family(tmp_path, monkeypatch):
    """전체 목록은 기록으로 남고, 주 모델은 별칭 패밀리로 골라진다.

    되돌려-FAIL: `primary_models=primary` 인자를 지우면 [] 가 되어 red.
    """
    agent = _agent(tmp_path)
    out = _claude_json(
        "ok",
        models=("claude-sonnet-5", "claude-haiku-4-5"),
        tokens={"claude-sonnet-5": 5, "claude-haiku-4-5": 50},
    )
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: _fake_completed(out))
    sc = _scenario(
        tmp_path, {"assertions": [{"type": "output_regex", "pattern": "ok"}]}
    )
    res = runner.run_scenario(agent, sc, timeout=5)
    assert res["resolved_models"] == ["claude-haiku-4-5", "claude-sonnet-5"]
    assert res["primary_models"] == ["claude-sonnet-5"]


def _axes(primary, resolved):
    s = _summary(models=["opus"], efforts=["max"])
    s["agent-x"]["primary_models"] = primary
    s["agent-x"]["resolved_models"] = resolved
    return s


def test_auxiliary_model_drift_is_notice_not_regression(tmp_path, capsys):
    """(C-ATK-001) 주 모델이 같고 보조 모델만 나타났다면 회귀가 아니다 — 알림만.

    되돌려-FAIL: MEASUREMENT_AXES 의 비교 대상을 resolved_models 로 되돌리면
    "측정 축이 다르다" 가 나와 red.
    """
    base = _baseline_file(tmp_path, _axes(["claude-opus-5-5"], ["claude-opus-5-5"]))
    cur = _axes(["claude-opus-5-5"], ["claude-haiku-4-5", "claude-opus-5-5"])
    assert runner.compare_baseline(cur, base) == []
    assert "전체 모델 목록이 다르다(비회귀)" in capsys.readouterr().err


def test_primary_model_axis_mismatch_is_a_regression(tmp_path):
    """(c) 별칭이 같아도 주 모델(실제 ID)이 바뀌면 값 비교가 성립하지 않는다.

    되돌려-FAIL: MEASUREMENT_AXES 에서 primary_models 줄을 지우면 [] 가 나와 red.
    """
    base = _baseline_file(tmp_path, _axes(["claude-opus-5-1"], ["claude-opus-5-1"]))
    out = runner.compare_baseline(_axes(["claude-opus-5-5"], ["claude-opus-5-5"]), base)
    assert out, "실제 모델이 바뀌었는데 후퇴로 잡히지 않았다"
    assert "측정 축이 다르다 — primary_model" in out[0]


def test_same_primary_model_axis_passes(tmp_path, capsys):
    base = _baseline_file(tmp_path, _axes(["claude-opus-5-5"], ["claude-opus-5-5"]))
    assert (
        runner.compare_baseline(_axes(["claude-opus-5-5"], ["claude-opus-5-5"]), base)
        == []
    )
    assert capsys.readouterr().err == ""


def test_missing_primary_model_axis_in_baseline_is_notice_not_regression(
    tmp_path, capsys
):
    """(d) 축 도입 이전 기준선(2026-09-26 등)은 회귀가 아니라 stderr 알림이다.

    되돌려-FAIL: MEASUREMENT_AXES 에서 primary_models 줄을 지우면 알림이 사라져 red.
    """
    cur = _axes(["claude-opus-5-5"], ["claude-opus-5-5"])
    out = runner.compare_baseline(
        cur, _baseline_file(tmp_path, _summary(models=["opus"]))
    )
    assert out == [], "미지를 회귀로 올리면 상시 red 가 된다"
    assert "측정 축(primary_model)" in capsys.readouterr().err


@pytest.mark.parametrize("side", ["current", "baseline"])
def test_empty_axis_is_unknown_like_missing(tmp_path, capsys, side):
    """(C-ATK-002) `[]` 는 `None` 과 같은 "모름" — 회귀도 아니지만 **침묵도 아니다**.

    되돌려-FAIL: `_axis_mismatch` 의 `if not cur_axis or not base_axis` 를 원래의
    `if cur_axis and base_axis is None` 로 되돌리면 `[]` 쪽 알림이 사라져 red.
    """
    full, empty = _axes(["claude-opus-5-5"], ["claude-opus-5-5"]), _axes([], [])
    cur, base = (empty, full) if side == "current" else (full, empty)
    assert runner.compare_baseline(cur, _baseline_file(tmp_path, base)) == []
    assert "측정 축(primary_model) 기록이 없다" in capsys.readouterr().err


def test_main_refuses_baseline_with_empty_compare_axis(tmp_path, monkeypatch, capsys):
    """(C-ATK-002) 비교 축이 빈 에이전트가 있으면 기준선 저장을 거부하고 exit 1.

    빈 축 기준선은 이후 모든 compare 에서 그 축을 "모름"으로 만들어 회귀를 영구히 못 본다.
    되돌려-FAIL: main 의 `empty_axis_agents` 분기를 지우면 저장되고 rc 0 이라 red.
    """
    summary = {
        "fix-bugs": {
            "pass": 1,
            "fail": 0,
            "total": 1,
            "pass_rate": 1.0,
            "models": ["sonnet"],
            "efforts": ["default"],
            "primary_models": [],
        }
    }
    report = {"results": [], "summary": summary}
    monkeypatch.setattr(runner, "run_all", lambda *a, **k: (report, runner.EXIT_PASS))
    monkeypatch.setattr(runner, "BASELINE_DIR", tmp_path / "baseline")
    monkeypatch.setattr(runner, "REPORTS_DIR", tmp_path / "reports")
    assert runner.main(["--baseline"]) == runner.EXIT_FAIL
    assert not (tmp_path / "baseline").exists()
    assert "fix-bugs: primary_model" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 출력 해석 — 실행 실패·형태 관용·fail-closed (C-ATK-003·005·006)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stdout",
    [
        "수정 완료 injection",  # text 모드 출력 — 키워드가 우연히 있어도
        '{"result": "수정 완료 injection"',  # 잘린 JSON
        '["수정 완료 injection"]',  # 최상위가 리스트인데 result 원소 없음
        '{"type": "result", "subtype": "success", "note": "수정 완료 injection"}',  # result 부재
        '{"subtype": "success", "result": null, "note": "injection"}',  # result 가 문자열 아님
        "잡음\n수정 완료 injection",  # 마지막 줄도 json 아님
    ],
)
def test_unparseable_scenario_output_fails_closed(tmp_path, monkeypatch, stdout):
    """(e) JSON 파싱 실패·result 부재는 채점하지 않는다 — 인프라 분류(error)로 사유를 남긴다.

    raw stdout 에 키워드가 있어도 pass 가 나오면 안 된다.
    되돌려-FAIL: run_scenario 의 해석 실패 분기를 `parsed = ScenarioOutput(text=stdout)`
    폴백으로 바꾸면 모든 케이스가 pass 로 red.
    """
    res = _run_with_stdout(tmp_path, monkeypatch, stdout, pattern="injection")
    assert res["status"] == "error"
    assert res["checks"][0]["type"] == "scenario_output"
    assert "fail-closed" in res["checks"][0]["detail"]
    assert res["resolved_models"] == []


@pytest.mark.parametrize(
    "extra",
    [
        {"is_error": True},
        {"subtype": "error_max_turns"},
        {"subtype": "error_during_execution", "is_error": True},
        {"subtype": None},  # subtype 부재도 "성공"의 증거가 아니다
    ],
)
def test_failed_execution_result_is_error_not_graded(tmp_path, monkeypatch, extra):
    """(C-ATK-003·005) CLI 가 실행 실패를 보고한 결과는 `result` 에 키워드가 있어도
    채점하지 않는다 — error 로, detail 에 subtype·is_error 를 싣는다.

    되돌려-FAIL: parse_scenario_output 의 `is_error is True or subtype != "success"`
    검사를 지우면 result 텍스트가 채점돼 pass 로 red.
    """
    stdout = _claude_json("ok", **extra)
    if extra.get("subtype", "x") is None:
        data = json.loads(stdout)
        del data["subtype"]
        stdout = json.dumps(data)
    res = _run_with_stdout(tmp_path, monkeypatch, stdout)
    assert res["status"] == "error"
    detail = res["checks"][0]["detail"]
    assert "subtype=" in detail and "is_error=" in detail


@pytest.mark.parametrize(
    "stdout",
    [
        # 최상위 배열(스트림 전체) — 마지막 type=="result" 원소
        json.dumps(
            [
                {"type": "system", "subtype": "init"},
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": "옛 답",
                },
                {"type": "assistant", "message": "…"},
                json.loads(_claude_json("ok")),
            ]
        ),
        # 앞에 잡음 줄 — 마지막 비지 않은 줄
        "Warning: something\n" + _claude_json("ok") + "\n\n",
        # 앞에 잡음 줄 + 마지막 줄이 배열
        "noise\n" + json.dumps([json.loads(_claude_json("ok"))]),
    ],
)
def test_scenario_output_shape_tolerance(tmp_path, monkeypatch, stdout):
    """(C-ATK-006) JSON 객체 하나가 아닌 출력도 결과 객체를 찾아 읽는다.

    되돌려-FAIL: parse_scenario_output 을 `json.loads(stdout)` + dict 강제로 되돌리면
    세 케이스 모두 error 로 red.
    """
    res = _run_with_stdout(tmp_path, monkeypatch, stdout, pattern="^ok$")
    assert res["status"] == "pass", res["checks"]
    assert res["primary_models"] == ["claude-sonnet-5"]


# ---------------------------------------------------------------------------
# output_not_regex 가드 — 실물 expect.json 의 패턴을 러너의 **실제 매처**로 양방향 검증
#
# 부분 문자열 가드(옛 output_not_contains)는 정확한 출력을 6번 fail 시켰다(오탐 원문은
# 아래 두 excerpt). 여기서 고정하는 것: (a) 오탐 원문·판정이 옳은데 어구가 섞인 출력은
# **통과**, (b) 시나리오별 거짓 green 선언은 **fail**. 패턴은 테스트에 복사하지 않고
# expect.json 에서 읽는다 — 시나리오의 실제 가드가 검증 대상이다.
# 되돌려-FAIL: `_check_output_not_regex` 를 `any(p in stdout for p in patterns)` 같은
# 부분 문자열 매칭으로 되돌리면 (a) 가 전부 red 다.
# ---------------------------------------------------------------------------

_SCENARIOS_ROOT = runner.SCENARIOS_ROOT

# 2026-09-29 전량 --baseline 런(20260929T171425098275Z)의 fail 레코드 output_excerpt 원문.
# 에이전트는 옳았고 옛 가드가 틀렸다.
_FP_PLAN_PIPX = """\
(없는 고객은 0) | `OrderRepository` 와 같은 메모리 구현 패턴이고 같은 모듈에 둡니다. 변경을 최소로 합니다. | 별도 파일 `infra/point_repository.py` (규모가 커지면 분리) | 같은 계약 |
| 유스케이스 연결 | `checkout(repo, points, order)` 에 **필수 인자** 추가. 순서: 주문 저장 → `calculate_points` → `points.add` | 누락되면 적립이 조용히 건너뛰어지지 않게 합니다. 확인 결과 호출자는 `tests/test_checkout.py` 한 곳뿐입니다. | `points=None` 기본값 → 적립이 조용히 누락될 수 있어 기각. Protocol 포트 도입 → 지금 app이 infra 구현을 직접 import하는 패턴과 달라 과설계 | 같은 계약 |
| 경계 | **계약 변경은 없습니다.** 새 import는 app→domain, app→infra 두 방향뿐이고 모두 허용됩니다. `domain/points.py` 는 아무것도 import하지 않습니다. | 기존 계약이 패키지 단위라 새 모듈도 자동으로 검사됩니다. | — | 도구: import-linter (확인 결과 `pyproject.toml` dev 의존성과 `.importlinter` 에 있음). 레포 안에는 이 도구를 부르는 스크립트·Makefile·CI가 **없습니다**(확인 결과). 검사 명령 `lint-imports` 는 import-linter 패키지가 설치하는 CLI이고, 레포 코드로 확인한 명령은 아닙니다. 그래서 배치 0에서 존재를 확인합니다. |

### 파일 구조 계획
```
shop/
├── domain/points.py        (생성) POINT_RATE_PERCENT, calculate_points
├── infra/repository.py     (수정) PointRepository 추가
└── app/checkout.py         (수정) points 인자 추가, 적립 호출
tests/
├── test_points.py          (생성) 도메인 규칙 단위 테스트
├── test_repository.py      (생성) PointRepository 단위 테스트
└── test_checkout.py        (수정) 새 시그니처 반영, 적립 검증 추가
```

### 구현 계획

#### 📦 배치 0: 기준선 확인 (선행)
| # | 작업 | 파일 | 복잡도 | 의존 | 설명 |
|---|---|---|---|---|---|
| 0.1 | dev 의존성 설치, 기준선 green 확인 | — | Low | - | `python -m pip install -e '.[dev]'` 실행 후 아래 명령을 실행합니다 |

**완료 조건** (모두 exit 0):
```
python -m pytest -q
lint-imports
```
`lint-imports` 가 없으면(command not found) 계획을 멈추고 보고합니다. 전역 설치나 `pipx run` 같은 우회는 쓰지 않습니다.

#### 📦 배치 1: 도메인 규칙과 저장소 (1.1과 1.2는 병렬 가능)
| # | 작업 | 파일 | 복잡도 | 의존 | 설명 |
|---|---|---|---|---|---|
| 1.1 | 적립 규칙 | `shop/domain/points.py`, `tests/test_points.py` | Low | 0 | 테스트를 먼저 씁니다. 케이스: `12000→120`, `0→0`, `99→0`, `12345→123` (**Q1 답에 따라 확정**, 반올림이면 123, 올림이면 124) |
| 1.2 | 잔액 저장소 | `shop/infra/repository.py`, `tests/test_repository.py` | Low | 0 | 케이스: 없는 고객 잔액 0, `add` 두 번 누적, 고객 간 격리 |

**완료 조건** (모두 exit 0):
```
python -m pytest -q tests/test_points.py tests/test_repository.py
python -m pytest -q          # 기존 test_checkout 회귀 없음
lint-imports
```

#### 📦 배치 2: checkout 연결 (배치 1 이후)
| # | 작업 | 파일 | 복잡도 | 의존 | 설명 |
|---|---|---|---|---|---|
| 2.1 | 유스케이스 수정 | `shop/app/checkout.py` | Medium | 1.1, 1.2 | 시그니처를 `checkout(repo: OrderRepository, points: PointRepository, order: Order) -> Order` 로 바꿉니다. `repo.save(order)` 다음에 `points.add(order.customer_id, calculate_points(order.total))` 를 호출합니다. 반환값은 그대로 둡니다. |
| 2.2 | 테스트 갱신 | `tests/test_checkout.py` | Low | 2.1 | 기존 테스트를 새 시그니처로 고칩니다. 추가 케이스: 12000원 결제 후 `get_balance("c-1") == 120`, 같은 고객이 두 번 결제하면 누적, 다른 고객 잔액은 영향 없음 |

**완료 조건** (모두 exit 0):
```
python -m pytest -q
lint-imports
```

#### 📦 배치 3: 중복 적립 처리 (Q2 답에 따라)
- **Q2=(A)** 로 정해지면 다음과 같이 진행합니다.
  - `OrderRepository` 에 `exists(order_id) -> bool` 을 추가합니다.
  - `checkout` 은 이미 있는 주문이면 적립을 건너뜁니다.
  - 테스트 `같은 주문으로 checkout 2회 → 잔액 120` 을 추가합니다.
  - 파일: `shop/infra/repository.py`, `shop/app/checkout.py`, `tests/test_checkout.py`
- **Q2=(B)**"""

_FP_VERIFY_MULTIPLY = """\
## 전체 상태: ❌ FAIL

| 항목      | 상태  | 상세               |
| --------- | ----- | ------------------ |
| 의존성    | ✅    | pytest 설치됨      |
| 타입 체크 | ⊖     | Python(타입 체크 미실시) |
| 린트      | ⊖     | 린트 도구 미실시    |
| 테스트    | ❌    | 2개 중 1개 실패     |
| 빌드      | ⊖     | N/A (순수 Python)  |

---

## 실패 분석

### High 심각도 에러

#### test_multiply 실패
```
test_calc.py::test_multiply FAILED
assert 5 == 6
 where 5 = multiply(2, 3)
```

- **파일**: calc.py:5-6
- **테스트**: test_calc.py::test_multiply (라인 8-9)
- **원인**: `multiply(a, b)` 함수가 곱셈(a \u00d7 b)이 아니라 덧셈(a + b)을 반환함
  - 호출: `multiply(2, 3)`
  - 예상값: `6` (2 \u00d7 3)
  - 실제값: `5` (2 + 3)
  - 소스코드에 명시된 버그: `return a + b  # 버그: 곱셈이 아니라 덧셈`

---

## 테스트 결과 요약

| 테스트 | 상태 | 예상 | 실제 |
| ------ | ---- | ---- | ---- |
| test_add | ✅ PASS | 5 | 5 |
| test_multiply | ❌ FAIL | 6 | 5 |

---

## 권장 조치

1. **calc.py:6번 라인 수정** — `multiply()` 함수의 반환문을 `a + b`에서 `a * b`로 변경
2. 변경 후 `python3 -m pytest`를 다시 실행하여 모든 테스트 통과 확인

---

## 완료: 전체 — 2건 검토 (1건 실패, 1건 통과)"""


# 결함 부재를 판정 줄로 선언하는 거짓 green — 결함 탐지 시나리오(8종) 공통 형태.
_DEFECT_FALSE_GREEN = [
    "## 판정: 취약점 없음",
    "**결론**: 취약점이 없습니다.",
    "검토 결과 취약점이 없습니다.",
    "전체 상태: ✅ 취약점 없음",
    "요약: 버그가 없다.",
    "- 버그 없음",
    "이 코드에는 취약점은 없습니다.",
    "종합: 취약점이 발견되지 않았습니다.",
    "결론적으로 취약점을 발견하지 못했습니다.",
    "> **판정:** 버그 없음 ✅",
    "no vulnerabilities found.",
    "Verdict: no issues found",
    "Summary: No vulnerabilities detected",
]

# 정확한 분석인데 같은 어구가 판정 줄이 아닌 곳에 섞인 출력 — 통과해야 한다.
_DEFECT_ACCURATE = [
    # 2026-09-20 4번째 오탐: 기술적 한정절
    "`json.load` 자체는 코드 실행 취약점은 없지만(안전한 파서), H-1 과 결합하면 임의 경로 쓰기가 됩니다.",
    # 2026-09-01 3번째 오탐: 수정안 코드 주석
    "```python\n# 원자적 rename, 심볼릭 링크 문제 없음\nos.replace(tmp, path)\n```",
    "| 인증 | 취약점 없음 |",
    "### 인증/인가 — 취약점 없음",
    "그 외 취약점은 없습니다.",
    "- SQL 인젝션 외에는 다른 취약점이 없습니다.",
    "판정: SQL injection 취약점 발견 (Critical). 이 함수 외 취약점 없음",
    "판정: ❌ 취약점 2건. 다른 항목에는 취약점이 없습니다.",
    "취약점이 없다고 가정하면 안 됩니다.",
    "No issues found in the linter output, but the tests reveal a bug.",
    "버그 없음 여부를 확인하려면 재현이 필요합니다.",
]

_DEFECT_SCENARIOS = [
    "define-business-logic/point-service-rules",
    "devils-advocate/single-instance-sync",
    "design-user-journey/checkout-edge-cases",
    "review-code/false-green",
    "review-code/sql-injection",
    "review-code/race-condition",
    "review-code/off-by-one",
    "security-scan/shared-tmp-and-hardcoded-token",
]

_PLAN_SCENARIO = "plan-implementation/boundary-loyalty-points"
_PLAN_FALSE_GREEN = [
    "npx import-linter",
    "$ uvx --from import-linter lint-imports",
    "  pipx run import-linter",
    "```bash\npython -m pytest -q\nnpx lint-imports\n```",
]
_PLAN_ACCURATE = [
    "전역 설치나 `pipx run` 같은 우회는 쓰지 않습니다.",
    "`lint-imports` 가 없으면 계획을 멈춥니다. `uvx` 로 대신 실행하지 않습니다.",
    "| 도구 | import-linter (npx 없이 프로젝트 의존성으로 실행) |",
]

_VERIFY_SCENARIO = "verify-code/multiply-bug-detected"
_VERIFY_FALSE_GREEN = [
    "## 전체 상태: ✅ 모든 테스트 통과",
    "모든 테스트 통과",
    "✅ 모든 테스트 통과했습니다",
    "결과: 전부 통과",
    "테스트: ✅ 모든 테스트 통과",
    "- 모든 검증 통과",
    "테스트 통과했습니다.",
    "All tests passed.",
    "Summary: all tests pass",
    "## 전체 상태: ✅ PASS",
    "Verdict: PASS",
    "**최종 판정**: ✅ 통과",
]
_VERIFY_ACCURATE = [
    # 2026-09-29 오탐: 판정은 FAIL, 권장 조치 문장에 어구가 들어 있다
    "2. 변경 후 `python3 -m pytest`를 다시 실행하여 모든 테스트 통과 확인",
    "## 전체 상태: ❌ FAIL",
    "| test_add | ✅ PASS | 5 | 5 |",
    "완료: 전체 — 2건 검토 (1건 실패, 1건 통과)",
    "- 수정 후 모든 테스트 통과를 목표로 합니다",
    "판정: FAIL (모든 테스트 통과 전까지 병합 금지)",
    "모든 테스트 통과 여부: 아니오",
    "test_add 는 통과했지만 test_multiply 는 실패했습니다.",
]

_GUARD_CASES: dict[str, tuple[list[str], list[str]]] = {
    **dict.fromkeys(_DEFECT_SCENARIOS, (_DEFECT_FALSE_GREEN, _DEFECT_ACCURATE)),
    _PLAN_SCENARIO: (_PLAN_FALSE_GREEN, _PLAN_ACCURATE),
    _VERIFY_SCENARIO: (_VERIFY_FALSE_GREEN, _VERIFY_ACCURATE),
}


def _guard(sc: str) -> dict:
    """시나리오 expect.json 의 output_not_regex 어서션(정확히 1개)."""
    expect = json.loads((_SCENARIOS_ROOT / sc / "expect.json").read_text("utf-8"))
    found = [a for a in expect["assertions"] if a["type"] == "output_not_regex"]
    assert len(found) == 1, f"{sc}: output_not_regex 는 정확히 1개여야 함"
    return found[0]


def _guard_verdict(sc: str, text: str) -> bool:
    return runner.check_assertion(_guard(sc), text, Path("."))[0]


def test_no_scenario_still_uses_removed_output_not_contains():
    """어서션 타입으로도, 값 삭제로 우회한 채로도 옛 타입이 남으면 red."""
    offenders = [
        str(p.relative_to(_SCENARIOS_ROOT))
        for p in _SCENARIOS_ROOT.glob("*/*/expect.json")
        if any(
            a.get("type") == _REMOVED_TYPE
            for a in json.loads(p.read_text("utf-8")).get("assertions", [])
        )
    ]
    assert offenders == []


def test_guard_cases_cover_every_scenario_that_has_a_guard():
    """가드를 가진 시나리오가 이 표에 없으면 그 가드는 양방향 검증을 받지 못한 것이다."""
    guarded = {
        str(p.parent.relative_to(_SCENARIOS_ROOT))
        for p in _SCENARIOS_ROOT.glob("*/*/expect.json")
        if any(
            a.get("type") == "output_not_regex"
            for a in json.loads(p.read_text("utf-8")).get("assertions", [])
        )
    }
    assert guarded == set(_GUARD_CASES)


def test_real_false_positive_excerpts_pass_their_guards():
    """(a) 2026-09-29 오탐 원문 — 부분 문자열 가드는 이 둘을 fail 시켰다."""
    assert _guard_verdict(_PLAN_SCENARIO, _FP_PLAN_PIPX) is True
    assert _guard_verdict(_VERIFY_SCENARIO, _FP_VERIFY_MULTIPLY) is True


@pytest.mark.parametrize(
    ("sc", "text"),
    [(sc, t) for sc, (fg, _) in _GUARD_CASES.items() for t in fg],
)
def test_guard_catches_false_green_declaration(sc, text):
    """(b) 거짓 green 선언은 fail — 약화되지 않았음의 증거."""
    assert _guard_verdict(sc, text) is False, text
    # 리포트 한가운데에 있어도 잡는다(줄 앵커는 문서 앞머리 앵커가 아니다)
    report = f"## 분석\n\n발견 사항을 정리합니다.\n\n{text}\n\n끝."
    assert _guard_verdict(sc, report) is False, report


@pytest.mark.parametrize(
    ("sc", "text"),
    [(sc, t) for sc, (_, ok) in _GUARD_CASES.items() for t in ok],
)
def test_guard_passes_accurate_output_containing_the_phrase(sc, text):
    """(a) 판정이 옳은데 어구가 산문·주석·권장 조치·금지 서술에 섞인 출력은 통과."""
    assert _guard_verdict(sc, text) is True, text
