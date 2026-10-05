"""Unit tests for scripts/check_injection_budget.py — 예산 축소측정 회귀 방지.

v5.0.0: 규범 축이 `load_rules()` 직접 호출에서 **훅의 실제 main() 출력**으로 바뀌었다.
예전 측정은 LESSONS·ACTIVE PLANS 를 빼고 쟀고, conditional 신호를 게이트가 가상으로
전부 켜서 main() 에 신호가 없는 규범도 멀쩡해 보였다.

픽스처 `rules/` 를 쓰되 훅 스크립트(`session-start.py`·`utils.py`)와 도구(`tools/feedback_ledger.py`)는
**실물을 복사**한다 — 측정 대상이 그 프로세스이므로 재구현하면 테스트가 실물을 건드리지
않는다(`warning-signal.md` §측정 1).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from module_loader import load_module_by_path

CORE_BODY = "# Core Rule\ncore rule body\n"
#: session-start.conditional_signals() 의 실제 키 — 픽스처 규범 이름은 이것과 같아야 켜진다.
SIGNALLED = ("feedback-loop", "loop-engineering", "mcp-usage", "task-resume")
HOOK_FILES = ("session-start.py", "utils.py")
TOOL_FILES = ("feedback_ledger.py",)


def _fake_plugin_root(tmp_path: Path, *, conditional_names: tuple[str, ...]) -> Path:
    root = tmp_path / "common"
    (root / "rules").mkdir(parents=True)
    (root / "hooks").mkdir(parents=True)
    for name in HOOK_FILES:
        shutil.copy(REPO_ROOT / "plugins" / "common" / "hooks" / name, root / "hooks" / name)
    (root / "tools").mkdir(parents=True)
    for name in TOOL_FILES:
        shutil.copy(REPO_ROOT / "plugins" / "common" / "tools" / name, root / "tools" / name)
    (root / "rules" / "aa-core.md").write_text(
        f"---\ntier: core\n---\n\n{CORE_BODY}", encoding="utf-8"
    )
    for name in conditional_names:
        (root / "rules" / f"{name}.md").write_text(
            f"---\ntier: conditional\n---\n\n# COND {name}\nbody\n", encoding="utf-8"
        )
    return root


def _load(plugin_root: Path):
    mod = load_module_by_path(
        SCRIPTS_DIR / "check_injection_budget.py", "check_injection_budget_t"
    )
    mod.PLUGIN_ROOT = plugin_root
    return mod


def test_conditional_rules_are_derived_not_hardcoded(tmp_path):
    """새 conditional 규범이 코드 수정 없이 검사 대상에 들어와야 한다(§검토 절차 5)."""
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one", "brand-new-rule"))
    assert _load(root).conditional_rules() == ["brand-new-rule", "cond-one"]


def test_measures_real_main_output_including_lessons_and_plans(tmp_path):
    """측정 대상은 훅의 실제 출력이다 — LESSONS·ACTIVE PLANS 가 최악에 들어가야 한다."""
    root = _fake_plugin_root(tmp_path, conditional_names=SIGNALLED)
    out = _load(root).measure_scenarios(root)
    assert set(out) == {"empty", "ledger", "plan", "worktree", "peak"}
    assert "=== LESSONS ===" in out["peak"] and "=== ACTIVE PLANS ===" in out["peak"]
    assert "=== LESSONS ===" in out["ledger"] and "=== ACTIVE PLANS ===" in out["plan"]
    assert "=== LESSONS ===" not in out["empty"]
    assert "Core Rule" in out["empty"]
    sizes = {k: len(v.encode()) for k, v in out.items()}
    assert sizes["empty"] < sizes["ledger"] < sizes["peak"]
    assert sizes["empty"] < sizes["plan"] < sizes["peak"]


def test_signalled_conditionals_pass_coverage(tmp_path):
    """**양성 대조** — main() 이 켜는 신호의 규범은 통과해야 한다. 아니면 가드가 고장이다."""
    root = _fake_plugin_root(tmp_path, conditional_names=SIGNALLED)
    mod = _load(root)
    assert mod.check_conditional_coverage(mod.measure_scenarios(root), root) == []


def test_conditional_without_signal_is_red(tmp_path):
    """main() 에 신호가 없는 conditional 은 **한 번도 주입되지 않는다** — red.

    워크트리 신호를 지운 뒤 `parallel-worktree` 가 conditional 로 남아 있으면 정확히 이
    상태다. 예전 게이트는 신호를 가상으로 켜서 재 이것을 못 봤다.
    """
    root = _fake_plugin_root(tmp_path, conditional_names=(*SIGNALLED, "parallel-worktree"))
    mod = _load(root)
    problems = mod.check_conditional_coverage(mod.measure_scenarios(root), root)
    assert len(problems) == 1 and problems[0].startswith("parallel-worktree:"), problems


def test_always_on_signal_is_red(tmp_path):
    """빈 레포에서도 켜지는 신호는 상시 참이다 — conditional 이 아니다."""
    root = _fake_plugin_root(tmp_path, conditional_names=SIGNALLED)
    hook = root / "hooks" / "session-start.py"
    src = hook.read_text(encoding="utf-8")
    assert '"mcp-usage": _mcp_config_present(project_root),' in src
    hook.write_text(
        src.replace('"mcp-usage": _mcp_config_present(project_root),', '"mcp-usage": True,'),
        encoding="utf-8",
    )
    mod = _load(root)
    problems = mod.check_conditional_coverage(mod.measure_scenarios(root), root)
    assert any(p.startswith("mcp-usage:") and "상시" in p for p in problems), problems


def test_zero_conditional_rules_is_an_error(tmp_path):
    """파생 결과가 0개면 파싱 경로가 깨진 것이다 — 조용히 통과시키지 않는다."""
    root = _fake_plugin_root(tmp_path, conditional_names=())
    mod = _load(root)
    problems = mod.check_conditional_coverage(mod.measure_scenarios(root), root)
    assert problems and "하나도 파생하지 못했다" in problems[0]


def test_broken_hook_is_a_measurement_failure_not_green(tmp_path):
    root = _fake_plugin_root(tmp_path, conditional_names=SIGNALLED)
    (root / "hooks" / "session-start.py").write_text("raise SystemExit(3)\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="rc=3"):
        _load(root).measure_scenarios(root)


def test_unparseable_agent_is_red_not_silently_skipped(tmp_path):
    """에이전트 하나가 깨지면 그만큼 예산에서 빠져 **더 쉽게 통과**한다 (W6 F-4).

    결함이 게이트를 느슨하게 만드는, 정확히 거꾸로 된 방향이다. `SkipTally` 로
    건너뜀을 집계하고 1건이라도 있으면 경로·사유와 함께 red 다.

    `report()` 는 **비치명 사유**를 받는다(치명 사유가 아니다) — 이 게이트에 노랑
    예외는 없으므로 빈 집합을 넘긴다. 옛 치명 화이트리스트를 그대로 넘기면 의미가
    정반대로 뒤집혀 사각지대가 전부 노랑이 된다.
    """
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one",))
    agents = root / "agents"
    agents.mkdir(parents=True)
    (agents / "good.md").write_text(
        "---\nname: good\ndescription: 정상 에이전트\n---\n\n본문\n", encoding="utf-8"
    )
    mod = _load(root)

    entries, skipped = mod.agent_entries()
    assert len(entries) == 1 and len(skipped) == 0
    assert skipped.report(frozenset()) == 0

    (agents / "broken.md").write_text("frontmatter 가 없는 산문\n", encoding="utf-8")
    entries, skipped = mod.agent_entries()
    assert len(entries) == 1, "깨진 파일이 항목으로 들어갔다"
    assert len(skipped) == 1 and skipped.attempted == 2
    assert skipped.entries[0][1] == "no-frontmatter"
    assert skipped.report(frozenset()) == 1, "깨진 에이전트를 건너뛴 채 green 을 냈다"


# ── 넷째 축: 호스트 전달 한도 (W13) ──────────────────────────────────────────
#
# Codex 는 훅 출력을 기본 2,500 토큰에서 잘라 머리·꼬리만 모델에 준다. 실측: 16,622B
# 출력 중 10,028B 만 도착했고 RULES 가운데 규범 3종이 사라졌다. 우리 예산은 22 KiB 인데
# 호스트 한도와 **아무도 대조하지 않았다** — 이 축이 그 대조다.

_PEAK = 22528
_LESSONS_WORST = 5000


def _real_module():
    return load_module_by_path(
        SCRIPTS_DIR / "check_injection_budget.py", "check_injection_budget_host"
    )


def _policy_file(tmp_path: Path, session_start: dict | None, **target_extra) -> Path:
    events: dict = {"PostToolUse": [{"script": "hooks/auto-format.py", "timeout": 30}]}
    if session_start is not None:
        events["SessionStart"] = [
            {"script": "hooks/session-start.py", "timeout": 10, **session_start}
        ]
    target = {
        "id": "codex",
        "enabled": True,
        "hooks": {"events": events},
        **target_extra,
    }
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "targets.json"
    path.write_text(json.dumps({"targets": [target]}), encoding="utf-8")
    return path


def _host_check(tmp_path: Path, capsys, session_start: dict | None, **extra):
    rc = _real_module().check_host_delivery(
        _policy_file(tmp_path, session_start, **extra), _PEAK + _LESSONS_WORST
    )
    return rc, capsys.readouterr().out


def test_host_limit_absent_falls_back_to_upstream_default_and_is_red(tmp_path, capsys):
    """키가 없으면 Codex 기본 2,500 — 우리 최악(≈6,882 토큰)은 그걸 넘는다. 이번 결함 그대로."""
    rc, out = _host_check(tmp_path, capsys, {})
    assert rc == 1, out
    assert "2,500" in out and "키 부재" in out


def test_host_limit_zero_is_green(tmp_path, capsys):
    rc, out = _host_check(tmp_path, capsys, {"additionalContextLimit": 0})
    assert rc == 0, out
    assert "spill 비활성" in out


def test_host_limit_small_finite_is_red(tmp_path, capsys):
    rc, out = _host_check(tmp_path, capsys, {"additionalContextLimit": 3000})
    assert rc == 1, out
    assert "3,000" in out


def test_host_limit_sufficient_finite_is_green(tmp_path, capsys):
    """양성 대조 — 유한값 자체를 거부하는 게 아니라 **예산과 대조**한다."""
    worst_tokens = -(-(_PEAK + _LESSONS_WORST) // 4)
    rc, out = _host_check(tmp_path, capsys, {"additionalContextLimit": worst_tokens})
    assert rc == 0, out
    rc, out = _host_check(
        tmp_path, capsys, {"additionalContextLimit": worst_tokens - 1}
    )
    assert rc == 1, out


def test_host_limit_no_session_start_entry_is_red(tmp_path, capsys):
    """훅을 싣는 타겟이 있는데 session-start 를 못 찾으면 파싱 경로가 깨진 것이다(false-green 금지)."""
    rc, out = _host_check(tmp_path, capsys, None)
    assert rc == 1, out
    assert "하나도 찾지 못했다" in out


def test_host_limit_invalid_value_is_red(tmp_path, capsys):
    for bad in (-1, True, "0"):
        rc, out = _host_check(
            tmp_path / str(bad), capsys, {"additionalContextLimit": bad}
        )
        assert rc == 1, (bad, out)


def test_host_limit_unknown_host_is_red_not_borrowed(tmp_path, capsys):
    """다른 호스트가 훅을 싣기 시작하면 Codex 기본값을 빌려 쓰지 않고 멈춘다."""
    rc, out = _host_check(tmp_path, capsys, {}, id="newhost")
    assert rc == 1, out
    assert "조사되지 않았다" in out


def test_real_policy_passes_with_the_real_peak_cap():
    """실물 대조 — 픽스처 초록은 "동작한다"가 아니다(`warning-signal.md` §측정 1)."""
    mod = _real_module()
    assert mod.check_host_delivery(mod.TARGETS_POLICY, mod.INJECTION_PEAK_CAP) == 0


@pytest.mark.parametrize("style", ["|", ">", "|-", ">-", "|+", ">+"])
def test_agent_block_description_exceeds_budget(tmp_path, style):
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one",))
    agents = root / "agents"
    agents.mkdir()
    body = "한" * 3000
    (agents / "large.md").write_text(
        f"---\nname: large\ndescription: {style}\n  {body}\n\n  끝\nmodel: sonnet\n---\n",
        encoding="utf-8",
    )
    mod = _load(root)
    entries, skipped = mod.agent_entries()
    assert not len(skipped)
    assert entries[0][0] >= len(f"large: {body}\n\n끝".encode())
    assert mod._report("agents", entries[0][0], mod.AGENTS_CAP, "reduce") == 1


@pytest.mark.parametrize(
    "description",
    [
        "",
        "|2\n  body",
        ">oops\n  body",
        "|",
        "*alias",
        "[one, two]",
        '"unclosed',
        "|\n    first\n  bad",
        "|\n\tbody",
        "plain\n  continued",
        "plain\n\n  continued",
    ],
)
def test_unsupported_agent_description_is_red(tmp_path, description):
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one",))
    agents = root / "agents"
    agents.mkdir()
    (agents / "bad.md").write_text(
        f"---\nname: bad\ndescription: {description}\nmodel: sonnet\n---\n",
        encoding="utf-8",
    )
    entries, skipped = _load(root).agent_entries()
    assert entries == []
    assert skipped.entries[0][1] == "invalid-description"
    assert skipped.report(frozenset()) == 1


def test_block_description_keeps_blank_lines_and_stops_at_next_key():
    text = "description: >- # folded\n  one\n\n  two\nmodel: sonnet"
    assert _real_module()._agent_description(text) == "  one\n\n  two\n"


@pytest.mark.parametrize("style", ["|+", ">+"])
def test_keep_chomping_trailing_blank_lines_exceed_budget(tmp_path, style):
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one",))
    agents = root / "agents"
    agents.mkdir()
    trailing = "\n" * 9000
    (agents / "large.md").write_text(
        f"---\nname: large\ndescription: {style}\n  body{trailing}model: sonnet\n---\n",
        encoding="utf-8",
    )
    mod = _load(root)
    entries, skipped = mod.agent_entries()
    assert not len(skipped)
    assert entries[0][0] >= len(f"large: body{trailing}".encode())
    assert mod._report("agents", entries[0][0], mod.AGENTS_CAP, "reduce") == 1


@pytest.mark.parametrize("style", ["|", ">", "|-", ">-", "|+", ">+"])
def test_leading_block_blank_lines_exceed_budget(tmp_path, style):
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one",))
    agents = root / "agents"
    agents.mkdir()
    leading = "\n" * 9000
    (agents / "large.md").write_text(
        f"---\nname: large\ndescription: {style}\n{leading}  body\n---\n",
        encoding="utf-8",
    )
    mod = _load(root)
    entries, skipped = mod.agent_entries()
    assert not len(skipped)
    assert entries[0][0] > mod.AGENTS_CAP


# ── 프로젝트 지침 축 (CLAUDE.md + @import) ──────────────────────────────
#
# 이 축이 있는 이유: `@docs/x.md` 는 **링크가 아니라 본문 인라인**이다. 한 줄이
# 그 파일 전체만큼 비싸서 눈으로는 비용이 보이지 않는다 — v3.37.0 이전에
# CLAUDE.md + import 6종이 62 KiB(≈15.5k 토큰)였고 아무 게이트도 그것을 보지
# 않았다. 훅 주입(8.9 KiB)을 두 릴리스에 걸쳐 깎는 동안 그 7배가 무측정으로
# 있었다는 것이 이 축의 존재 근거다.


def _fake_project(root: Path, body: str, imports: dict[str, str]) -> None:
    lines = [body]
    for rel in imports:
        lines.append(f"@{rel}")
    (root / "CLAUDE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for rel, content in imports.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def test_project_doc_counts_imported_bodies_not_the_line(tmp_path):
    """@import 는 한 줄이지만 비용은 파일 전체다 — 그 둘을 혼동하면 측정이 무의미하다."""
    mod = _load(_fake_plugin_root(tmp_path, conditional_names=()))
    mod.REPO_ROOT = tmp_path
    _fake_project(tmp_path, "# Kit", {"docs/a.md": "x" * 5000})
    total, parts = mod.project_doc_bytes()
    assert total > 5000  # 인라인된 본문이 합산됐다
    assert any("a.md 5000B" in p for p in parts)  # 어느 파일이 비싼지 보고한다


def test_project_doc_missing_import_is_red_not_silent(tmp_path):
    """깨진 @import 를 0B 로 세면 **줄어든 것처럼 보인다** — 조용히 넘기지 않는다."""
    mod = _load(_fake_plugin_root(tmp_path, conditional_names=()))
    mod.REPO_ROOT = tmp_path
    (tmp_path / "CLAUDE.md").write_text("# Kit\n@docs/missing.md\n", encoding="utf-8")
    with pytest.raises(OSError):
        mod.project_doc_bytes()


def test_project_doc_over_cap_reports_fail(tmp_path):
    mod = _load(_fake_plugin_root(tmp_path, conditional_names=()))
    mod.REPO_ROOT = tmp_path
    _fake_project(tmp_path, "# Kit", {"docs/a.md": "x" * (mod.PROJECT_DOC_CAP + 1)})
    total, _ = mod.project_doc_bytes()
    assert mod._report("proj", total, mod.PROJECT_DOC_CAP, "move evidence out") == 1
