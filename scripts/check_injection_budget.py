#!/usr/bin/env python3
"""check_injection_budget.py — 매 세션 **무조건** 들어가는 컨텍스트의 총량 예산.

`verify-done.sh §16` 과 CI 가 **같은 스크립트**를 호출한다(F-023: 복제 로직은 반드시
드리프트한다). 이 검사는 원래 verify-done.sh 안 인라인이었고 **CI 에 없었다** —
"누가 로컬에서 게이트를 돌릴 때만" 발화하는 상태였다.

## 축이 둘인 이유

상시 비용의 출처가 둘인데 **한쪽만 재고 있었다**:

| 축 | 출처 | 우리가 줄이는 방법 |
| --- | --- | --- |
| 규범 + WORKFLOW | 이 킷의 SessionStart 훅이 주입 | core 티어를 축약하거나 conditional/reference 로 내린다 |
| 에이전트 설명 | **하네스**가 에이전트 선택용으로 노출 | 에이전트 수 / description 길이 |

두 번째 축은 `claude plugin details` 의 `Always-on` 추정에도 **잡히지 않는다** —
그 명령은 `agents/*.md` 만 세고 하위 디렉토리를 무시하는데(실측), 이 킷의 에이전트는
전부 `agents/{category}/` 에 있다. 도구가 못 세는 것을 우리가 대신 센다.

## 왜 축을 합치지 않는가

규범 축은 합산이 옳다 — 절을 파일 사이로 **옮기는 것만으로** 통과시키는 게이밍이
가능하기 때문이다(실측). 반면 에이전트 축은 다른 축과 재료가 다르고(우리가 쓰는 산문 vs
하네스가 노출하는 목록) **줄이는 수단도 다르다.** 합치면 "규범을 깎아 에이전트를 늘리는"
교환이 조용히 통과한다 — 그 둘은 교환 가능한 자원이 아니다.

## 왜 축이 둘이 아니라 셋인가 (2026-09-10 컨트롤 판정)

규범 축은 다시 **둘**로 나뉜다. 한 숫자로 합치면 둘 다 못 답한다:

| 축 | 묻는 것 | 상한 |
| --- | --- | --- |
| 규범(항상) | *"모든 세션이 무조건 내는 비용은?"* | 10 KiB |
| 규범(최악) | *"조건이 다 겹치면 얼마까지?"* | 22 KiB |
| 에이전트 | *"하네스가 노출하는 목록의 비용은?"* | 8 KiB |

**항상만 재면** 지금까지처럼 조용히 과소측정한다(그것이 ATK-006 이다).
**최악만 재면** 평범한 세션에 대해 과대보고해서 경고가 죽는다 — 상시 참인 경고는
정보가 아니라 소음이고, 소음은 옆의 진짜 경고까지 죽인다(`warning-signal.md`).

최악 상한 22 KiB 는 판정 시점 실측 20,675B 위 약 1.8 KiB 다. 넉넉하지 않은 것이
의도다 — 이 레포의 상한은 미학이 아니라 **조용한 증가를 막는 래칫**이다.

## 왜 **최악의 경우**도 재는가

`rules_bytes()` 는 `load_rules(PLUGIN_ROOT, False)` 를 불렀다 — `signals` 인자가 **없는**
호출이라 `tier: conditional` 규범이 하나도 포함되지 않았고, 결국 **core 규범만** 재고
있었다. 그런데 실제 세션은 `parallel-worktree`·`feedback-loop`·`mcp-usage`·`task-resume`
신호를 켜서 부른다(`session-start.py` 의 호출부). 즉 **게이트가 실제 주입량보다 적게
재고 통과시켰다.** 예산 게이트의 존재 이유가 *"매 세션 이만큼을 쓴다"* 인데 그 숫자가
실제보다 작으면, 그 게이트는 예산이 아니라 장식이다.

이제 **conditional 신호를 전부 켠 상태**를 잰다. 신호 이름은 **하드코딩하지 않고**
`rules/*.md` 의 frontmatter `tier: conditional` 에서 파생한다 — 목록을 코드에 나열하면
새 conditional 규범이 추가될 때 **조용히 커버리지를 잃는다**(`warning-signal.md`
§검토 절차 5: "대상을 나열하지 말고 제외를 나열한다"). 파생 결과가 0개면 red 다:
파싱 경로가 깨진 채 "core 만 쟀다"로 되돌아가는 것을 막는다.

## 상한 도출

**먼저 깎고 나서 숫자를 정한다(D-46)** — 반대로 하면 예산이 압력을 잃고 장식이 된다.
에이전트 축은 죽은 `facilitator-teams`(제거된 Agent Teams 모드의 Lead, 470B)를 걷어낸
**뒤** 7,837B 에서 8,192B(8 KiB)로 잡았다. 여유 355B 는 **평균 에이전트 1개분**이라,
에이전트를 하나 더할 때마다 "매 세션 이 비용을 낼 값어치가 있는가"를 묻게 된다.
규범 축의 여유율(4.0%)과 같은 압력이다.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

from git_tracked import SkipTally

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "common"
LABEL = "injection-budget"

RULES_CORE_CAP = 10240  # 10 KiB — **항상** 내는 비용 (core 규범 + WORKFLOW)
RULES_PEAK_CAP = 22528  # 22 KiB — conditional 이 전부 겹칠 때의 **최대** 비용
AGENTS_CAP = 8192       # 8 KiB — 에이전트 name + description

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)
DESC_RE = re.compile(
    r"^description:\s*\|?\s*\n((?:[ \t]+.*\n?)*)|^description:\s*(.*)$", re.MULTILINE
)


TIER_RE = re.compile(r"^tier:\s*(\S+)\s*$", re.MULTILINE)


def conditional_signals() -> dict[str, bool]:
    """`rules/*.md` 의 frontmatter 에서 `tier: conditional` 규범을 **파생**해 전부 켠다.

    신호 키는 `load_rules` 가 쓰는 것과 같은 **파일명 stem** 이다. 목록을 하드코딩하지
    않는 이유는 위 독스트링 참고 — 새 conditional 규범이 조용히 측정에서 빠지면
    예산은 실제보다 작게 나오고, 그것이 바로 이 게이트가 막아야 할 false-green 이다.
    """
    signals: dict[str, bool] = {}
    for path in sorted((PLUGIN_ROOT / "rules").glob("*.md")):
        fm = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
        if fm is None:
            continue
        tier = TIER_RE.search(fm.group(1))
        if tier is not None and tier.group(1) == "conditional":
            signals[path.stem] = True
    return signals


def rules_bytes() -> tuple[int, int, dict[str, bool]]:
    """(항상 비용, 최악 비용, 켠 신호). 재구현하지 않고 session-start.py 의 함수를 부른다.

    - **항상**: core 전부 + reference 색인. 신호가 하나도 없는 세션이 내는 바닥값이다.
    - **최악**: 거기에 conditional 전부. `include_task_resume` 도 True(활성 Work 세션).

    두 값을 **따로** 돌려주는 이유는 아래 "왜 축이 둘이 아니라 셋인가" 참고.
    """
    spec = importlib.util.spec_from_file_location(
        "session_start", PLUGIN_ROOT / "hooks" / "session-start.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("session-start.py 를 로드할 수 없다")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    signals = conditional_signals()
    if not signals:
        raise RuntimeError(
            "conditional 규범을 하나도 파생하지 못했다 — frontmatter 파싱 경로가 깨졌다. "
            "이대로면 core 만 재고 통과시키던 옛 결함으로 되돌아간다"
        )
    workflow = len(mod.load_workflow_skill(PLUGIN_ROOT).encode())
    always = len(mod.load_rules(PLUGIN_ROOT, False).encode()) + workflow
    peak = len(mod.load_rules(PLUGIN_ROOT, True, signals=signals).encode()) + workflow

    # ── 양성 대조 (W6 F-4) ────────────────────────────────────────────────
    # 0-파생 가드만으로는 부족하다. `conditional_signals()` 와 `load_rules()` 는 신호
    # 키가 **파일명 stem** 이라는 약속으로만 이어져 있고, **그 정합을 아무도 강제하지
    # 않았다.** `load_rules` 쪽 스키마가 stem 에서 바뀌면 파생한 신호가 전부 무시되는데,
    # `conditional_signals()` 는 여전히 4종을 파생하므로 0-파생 가드는 통과하고 게이트는
    # **green** 이 된다 — 이 파일 독스트링이 고쳤다고 선언한 과소측정으로 조용히 되돌아간다.
    #
    # `warning-signal.md` §측정 3: *음성 결과는 "그 지점에 도달했다"를 따로 증명해야
    # 한다.* 그래서 신호마다 **그 신호 하나만 켠 결과가 실제로 커지는지** 확인한다 —
    # 커지지 않았다면 그 키는 `load_rules` 에 닿지 않은 것이다.
    base = len(mod.load_rules(PLUGIN_ROOT, False).encode())
    unreached = [
        key
        for key in sorted(signals)
        if len(mod.load_rules(PLUGIN_ROOT, False, signals={key: True}).encode()) <= base
    ]
    if unreached:
        raise RuntimeError(
            f"신호가 load_rules 에 닿지 않았다: {', '.join(unreached)} — "
            "conditional_signals() 의 키 스키마와 load_rules() 가 갈렸다. "
            "이대로면 파생은 성공한 채 측정만 조용히 과소평가된다"
        )
    if peak <= always:
        raise RuntimeError(
            f"최악({peak}B)이 항상({always}B)보다 크지 않다 — conditional 규범이 "
            "하나도 반영되지 않았다는 뜻이다"
        )
    return always, peak, signals


def agent_entries() -> tuple[list[tuple[int, str]], SkipTally]:
    """하네스가 노출하는 형태(`<name>: <description>`)의 바이트 수를 에이전트마다.

    **건너뛴 파일을 함께 돌려준다** (W6 F-4). 예전에는 frontmatter 파싱 실패를 조용히
    `continue` 했는데, 그러면 에이전트 하나가 깨질 때마다 그만큼 예산에서 빠져 게이트가
    **더 쉽게 통과**한다 — 결함이 게이트를 느슨하게 만드는, 정확히 거꾸로 된 방향이다.
    반환값이 목록뿐이면 호출부는 "N종 쟀다"가 *검사해서 N종* 인지 *못 읽어서 N종* 인지
    구분할 수 없다.
    """
    out: list[tuple[int, str]] = []
    skipped = SkipTally(LABEL)
    for path in sorted((PLUGIN_ROOT / "agents").rglob("*.md")):
        skipped.attempted += 1
        rel = str(path.relative_to(PLUGIN_ROOT.parent.parent))
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as err:
            skipped.add(rel, "read-error", str(err))
            continue
        fm = FRONTMATTER_RE.match(raw)
        if fm is None:
            skipped.add(rel, "no-frontmatter", "YAML frontmatter 를 찾지 못했다")
            continue
        name = NAME_RE.search(fm.group(1))
        desc = DESC_RE.search(fm.group(1))
        text = (desc.group(1) or desc.group(2) or "") if desc else ""
        entry = f"{name.group(1) if name else path.stem}: {text.strip()}"
        out.append((len(entry.encode()), path.stem))
    return sorted(out, reverse=True), skipped


def _report(label: str, used: int, cap: int, hint: str) -> int:
    if used <= cap:
        print(f"[injection-budget] ✓ {label} {used:,}B ≤ {cap:,}B")
        return 0
    print(f"[injection-budget] ✗ {label} {used:,}B > {cap:,}B — 매 세션 이만큼을 쓴다")
    print(f"    → {hint}")
    return 1


def main() -> int:
    try:
        always, peak, signals = rules_bytes()
    except Exception as err:  # noqa: BLE001 — 측정 실패를 green 으로 위장하지 않는다
        print(f"[injection-budget] ✗ 규범 축 측정 실패: {err}")
        return 1

    print(
        f"[injection-budget] · conditional {len(signals)}종: " + ", ".join(sorted(signals))
    )
    rc = _report(
        "규범+WORKFLOW(항상)", always, RULES_CORE_CAP,
        "core 티어를 축약하거나 상시 필요 없는 것을 conditional/reference 로 내려라 (D-17)",
    )
    rc |= _report(
        "규범+WORKFLOW(최악)", peak, RULES_PEAK_CAP,
        "conditional 규범을 축약하거나 신호 조건을 좁혀라 — 최악은 흔한 조합이다"
        " (워크트리 + 활성 Work + MCP 존재 + 원장 있음)",
    )

    entries, skipped = agent_entries()
    # 건너뛴 것이 1건이라도 있으면 red — 그만큼 예산에서 빠져 **더 쉽게 통과**한다.
    # 두 사유 모두 치명이다: 못 읽은 것도, frontmatter 가 없는 것도 사각지대다.
    rc |= skipped.report(frozenset({"read-error", "no-frontmatter"}))
    if not entries:
        print("[injection-budget] ✗ 에이전트를 하나도 찾지 못했다 — 측정 경로가 깨졌다")
        return 1
    used_agents = sum(b for b, _ in entries)
    rc |= _report(
        f"에이전트 설명({len(entries)}종)", used_agents, AGENTS_CAP,
        "에이전트를 줄이거나 description 을 짧게 — 상위: "
        + ", ".join(f"{n}({b}B)" for b, n in entries[:3]),
    )
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
