"""Unit tests for scripts/check_injection_budget.py — 예산 축소측정 회귀 방지 (ATK-006).

`rules_bytes()` 가 `load_rules(PLUGIN_ROOT, False)` 를 부르고 있었다 — `signals` 인자가
없어 `tier: conditional` 규범이 하나도 포함되지 않았고, 결국 **core 규범만** 쟀다.
실제 세션은 conditional 신호를 켜서 부르므로 게이트가 **실제보다 적게 재고 통과**시켰다.

픽스처 `rules/` 를 쓰되 `session-start.py` 는 **실물을 복사**한다 — 측정 대상이
그 함수이므로 재구현하면 테스트가 실물을 건드리지 않는다(픽스처로 통과한 것은
"동작한다"가 아니다, `warning-signal.md` §측정 오염 1).
"""

from __future__ import annotations

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
    mod.conditional_signals = lambda: {f"rules/{k}.md": True for k in ("cond-one", "cond-two")}
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
    assert skipped.report(frozenset({"read-error", "no-frontmatter"})) == 0

    (agents / "broken.md").write_text("frontmatter 가 없는 산문\n", encoding="utf-8")
    entries, skipped = mod.agent_entries()
    assert len(entries) == 1, "깨진 파일이 항목으로 들어갔다"
    assert len(skipped) == 1 and skipped.attempted == 2
    assert skipped.entries[0][1] == "no-frontmatter"
    assert skipped.report(frozenset({"read-error", "no-frontmatter"})) == 1, (
        "깨진 에이전트를 건너뛴 채 green 을 냈다"
    )
