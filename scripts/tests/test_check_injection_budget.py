"""Unit tests for scripts/check_injection_budget.py — 예산 축소측정 회귀 방지 (ATK-006).

`rules_bytes()` 가 `load_rules(PLUGIN_ROOT, False)` 를 부르고 있었다 — `signals` 인자가
없어 `tier: conditional` 규범이 하나도 포함되지 않았고, 결국 **core 규범만** 쟀다.
실제 세션은 conditional 신호를 켜서 부르므로 게이트가 **실제보다 적게 재고 통과**시켰다.

픽스처 `rules/` 를 쓰되 `session-start.py` 는 **실물을 복사**한다 — 측정 대상이
그 함수이므로 재구현하면 테스트가 실물을 건드리지 않는다(픽스처로 통과한 것은
"동작한다"가 아니다, `warning-signal.md` §측정 오염 1).
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

CORE_BODY = "core rule body\n"
COND_BODY = "conditional rule body — 이 문장이 최악 측정에 들어가야 한다\n"


def _fake_plugin_root(tmp_path: Path, *, conditional_names: tuple[str, ...]) -> Path:
    root = tmp_path / "common"
    (root / "rules").mkdir(parents=True)
    (root / "hooks").mkdir(parents=True)
    shutil.copy(
        REPO_ROOT / "plugins" / "common" / "hooks" / "session-start.py",
        root / "hooks" / "session-start.py",
    )
    (root / "rules" / "aa-core.md").write_text(
        f"---\ntier: core\n---\n\n{CORE_BODY}", encoding="utf-8"
    )
    for name in conditional_names:
        (root / "rules" / f"{name}.md").write_text(
            f"---\ntier: conditional\n---\n\n{COND_BODY}", encoding="utf-8"
        )
    return root


def _load(plugin_root: Path):
    mod = load_module_by_path(
        SCRIPTS_DIR / "check_injection_budget.py", "check_injection_budget_t"
    )
    mod.PLUGIN_ROOT = plugin_root
    return mod


def test_conditional_signals_are_derived_not_hardcoded(tmp_path):
    """새 conditional 규범이 코드 수정 없이 측정 대상에 들어와야 한다.

    목록을 하드코딩하면 새 규범이 추가될 때 **조용히 커버리지를 잃는다**
    (`warning-signal.md` §검토 절차 5).
    """
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one", "brand-new-rule"))
    assert _load(root).conditional_signals() == {
        "cond-one": True,
        "brand-new-rule": True,
    }


def _rules_text(root: Path, *, signals):
    session_start = load_module_by_path(
        root / "hooks" / "session-start.py", "session_start_probe"
    )
    return session_start.load_rules(root, False, signals=signals)


def test_worst_case_includes_conditional_bodies(tmp_path):
    """최악 측정이 conditional 본문을 실제로 포함해야 한다 — core 만 재면 안 된다."""
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one",))
    mod = _load(root)
    _always, peak, signals = mod.rules_bytes()

    assert signals == {"cond-one": True}
    # conditional 본문의 바이트가 최악 측정에 실제로 반영됐는가.
    assert peak > len(CORE_BODY.encode()) + len(COND_BODY.encode())
    # 그리고 **항상** 축에는 들어가지 않아야 한다 — 그게 두 축을 나눈 이유다.
    assert COND_BODY.strip() not in _rules_text(root, signals=None)


def test_always_axis_excludes_conditional(tmp_path):
    """'항상' 축은 신호 없는 세션의 바닥값이다 — conditional 이 섞이면 과대보고다."""
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one", "cond-two"))
    always, peak, _sig = _load(root).rules_bytes()
    assert always < peak, (
        f"'항상'({always}B)이 '최악'({peak}B)보다 작지 않다 — 두 축이 같은 것을 재고 있다"
    )


def test_worst_case_is_strictly_larger_than_core_only(tmp_path):
    """되돌림 감지의 핵심 — signals 없이 부르면 나오는 수보다 반드시 커야 한다."""
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one", "cond-two"))
    mod = _load(root)
    _, peak, _ = mod.rules_bytes()

    session_start = load_module_by_path(
        root / "hooks" / "session-start.py", "session_start_t"
    )
    core_only = len(session_start.load_rules(root, False).encode()) + len(
        session_start.load_workflow_skill(root).encode()
    )
    assert peak > core_only, (
        f"최악 측정({peak}B)이 core 전용 측정({core_only}B)보다 크지 않다 — "
        "conditional 규범이 측정에서 빠졌다"
    )


def test_zero_conditional_rules_is_an_error(tmp_path):
    """파생 결과가 0개면 파싱 경로가 깨진 것이다 — 조용히 core 만 재고 통과시키지 않는다."""
    root = _fake_plugin_root(tmp_path, conditional_names=())
    with pytest.raises(RuntimeError, match="conditional 규범을 하나도 파생하지 못했다"):
        _load(root).rules_bytes()


def test_signal_key_schema_drift_is_red(tmp_path):
    """파생한 신호가 `load_rules` 에 **닿았는지**를 따로 증명한다 (W6 F-4).

    0-파생 가드만으로는 부족하다. `conditional_signals()` 와 `load_rules()` 는 신호 키가
    **파일명 stem** 이라는 약속으로만 이어져 있고 그 정합을 아무도 강제하지 않았다.
    `load_rules` 쪽 스키마가 stem 에서 바뀌면 신호가 전부 무시되는데, 파생은 여전히
    성공하므로 0-파생 가드는 통과하고 게이트는 **green** 이었다 — 이 파일 독스트링이
    고쳤다고 선언한 과소측정으로 조용히 되돌아간다.

    `warning-signal.md` §측정 3: 음성 결과는 "그 지점에 도달했다"를 따로 증명해야 한다.
    """
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one", "cond-two"))
    mod = _load(root)
    # 키 스키마 드리프트 — stem 이 아닌 키를 준다. load_rules 는 전부 무시한다.
    mod.conditional_signals = lambda: {
        f"rules/{k}.md": True for k in ("cond-one", "cond-two")
    }
    with pytest.raises(RuntimeError, match="신호가 load_rules 에 닿지 않았다"):
        mod.rules_bytes()


def test_reached_signals_still_pass(tmp_path):
    """**양성 대조** — 정상 신호는 그대로 통과해야 한다. 아니면 가드가 아니라 고장이다."""
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one", "cond-two"))
    always, peak, signals = _load(root).rules_bytes()
    assert signals == {"cond-one": True, "cond-two": True}
    assert peak > always


def test_unparseable_agent_is_red_not_silently_skipped(tmp_path):
    """에이전트 하나가 깨지면 그만큼 예산에서 빠져 **더 쉽게 통과**한다 (W6 F-4).

    결함이 게이트를 느슨하게 만드는, 정확히 거꾸로 된 방향이다. `SkipTally` 로
    건너뜀을 집계하고 1건이라도 있으면 경로·사유와 함께 red 다.

    `report()` 는 **비치명 사유**를 받는다(치명 사유가 아니다) — 이 게이트에 노랑
    예외는 없으므로 빈 집합을 넘긴다. 옛 치명 화이트리스트를 그대로 넘기면 의미가
    정반대로 뒤집혀 사각지대가 전부 노랑이 된다.
    """
    root = _fake_plugin_root(tmp_path, conditional_names=("cond-one",))
    agents = root / "agents" / "dev"
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
        _policy_file(tmp_path, session_start, **extra), _PEAK, _LESSONS_WORST
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


def test_real_policy_passes_and_lessons_worst_reads_the_ledger_cap():
    """실물 대조 — 픽스처 초록은 "동작한다"가 아니다(`warning-signal.md` §측정 1)."""
    mod = _real_module()
    ledger = load_module_by_path(
        REPO_ROOT / "plugins" / "common" / "hooks" / "feedback_ledger.py", "fl_probe"
    )
    worst = mod.lessons_worst_bytes()
    assert worst > ledger.DIGEST_CHAR_CAP * 4  # 머리말까지 더해졌다
    assert mod.check_host_delivery(mod.TARGETS_POLICY, mod.RULES_PEAK_CAP, worst) == 0
