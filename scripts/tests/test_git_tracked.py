"""Unit tests for scripts/git_tracked.py — `SkipTally.report` 의 **기본 fatal** 계약.

이 파일이 고정하는 것은 하나다: **등재되지 않은 건너뜀 사유는 red 다.**

이전 판은 `report(fatal_reasons)` 로 **치명 사유를 화이트리스트**로 받았다. 그러면
호출부가 새 사유를 추가할 때 그 사유는 목록에 없으므로 기본이 노랑이 되고, 게이트는
조용히 커버리지를 잃는다 — `git_tracked.py` 자신의 독스트링과
`docs/conventions/warning-signal.md` §검토 절차 5 가 비판하는 구조다.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from module_loader import load_module_by_path

_mod = load_module_by_path(SCRIPTS_DIR / "git_tracked.py", "git_tracked")


def _tally(*entries: tuple[str, str, str], attempted: int = 10):
    t = _mod.SkipTally("test")
    t.attempted = attempted
    for rel, reason, detail in entries:
        t.add(rel, reason, detail)
    return t


def test_unlisted_reason_defaults_to_fatal(capsys):
    """**핵심 회귀**: 호출부가 모르는 새 사유는 등재되지 않았으므로 red 다."""
    t = _tally(("a.py", "새로생긴사유", "이 사유는 어느 호출부에도 등재돼 있지 않다"))
    rc = t.report(frozenset({"비-UTF-8"}))
    assert rc == 1, "등재되지 않은 사유가 노랑으로 통과했다 — 조용한 커버리지 손실"
    out = capsys.readouterr().out
    assert "✗" in out
    assert "사각지대" in out


def test_listed_nonfatal_reason_is_yellow(capsys):
    t = _tally(("bin.png", "비-UTF-8", "바이너리"))
    rc = t.report(frozenset({"비-UTF-8"}))
    assert rc == 0
    out = capsys.readouterr().out
    assert "!" in out and "✗" not in out


def test_mixed_reasons_are_fatal_if_any_is_unlisted(capsys):
    t = _tally(
        ("bin.png", "비-UTF-8", "바이너리"),
        ("a.py", "읽기실패", "permission denied"),
    )
    assert t.report(frozenset({"비-UTF-8"})) == 1


def test_empty_nonfatal_set_makes_everything_fatal():
    t = _tally(("a.py", "무엇이든", "detail"))
    assert t.report(frozenset()) == 1


def test_no_entries_prints_nothing_and_passes(capsys):
    t = _tally()
    assert t.report(frozenset()) == 0
    assert capsys.readouterr().out == ""


def test_all_callers_pass_a_nonfatal_set_not_a_fatal_set():
    """호출부가 옛 이름을 그대로 두면 의미가 **정반대로 뒤집힌다** — 이름으로 고정한다.

    `FATAL_SKIP_REASONS` 를 그대로 넘기면 '치명 사유'가 '비치명 사유'로 읽혀,
    사각지대가 전부 노랑이 되고 정상 건너뜀이 red 가 된다. 조용한 반전이다.
    """
    import inspect
    import re

    sig = inspect.signature(_mod.SkipTally.report)
    assert list(sig.parameters)[1] == "nonfatal_reasons"

    calls = re.compile(r"\.report\(\s*([^)]*)\)")
    for rel in ("check_old_names.py", "check_shadowed_defs.py", "check_injection_budget.py"):
        src = (SCRIPTS_DIR / rel).read_text(encoding="utf-8")
        args = calls.findall(src)
        assert args, f"{rel} 이 report() 를 부르지 않는다"
        for arg in args:
            assert not re.search(r"(?<!NON)FATAL_SKIP_REASONS", arg), (
                f"{rel} 이 치명 화이트리스트를 비치명 인자로 넘긴다 — 의미가 정반대다: {arg}"
            )
