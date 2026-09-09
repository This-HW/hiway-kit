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

## 왜 **최악의 경우**를 재는가

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

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "common"

RULES_CAP = 10240   # 10 KiB — core 규범 + WORKFLOW
AGENTS_CAP = 8192   # 8 KiB — 에이전트 name + description

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


def rules_bytes() -> tuple[int, dict[str, bool]]:
    """**최악의 경우** 주입 바이트 수. 재구현하지 않고 session-start.py 의 함수를 부른다.

    최악 = core 전부 + conditional 전부 + reference 색인. `include_task_resume` 도
    True 다(활성 Work 가 있는 세션).
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
    used = len(mod.load_rules(PLUGIN_ROOT, True, signals=signals).encode()) + len(
        mod.load_workflow_skill(PLUGIN_ROOT).encode()
    )
    return used, signals


def agent_entries() -> list[tuple[int, str]]:
    """하네스가 노출하는 형태(`<name>: <description>`)의 바이트 수를 에이전트마다."""
    out: list[tuple[int, str]] = []
    for path in sorted((PLUGIN_ROOT / "agents").rglob("*.md")):
        fm = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
        if fm is None:
            continue
        name = NAME_RE.search(fm.group(1))
        desc = DESC_RE.search(fm.group(1))
        text = (desc.group(1) or desc.group(2) or "") if desc else ""
        entry = f"{name.group(1) if name else path.stem}: {text.strip()}"
        out.append((len(entry.encode()), path.stem))
    return sorted(out, reverse=True)


def _report(label: str, used: int, cap: int, hint: str) -> int:
    if used <= cap:
        print(f"[injection-budget] ✓ {label} {used:,}B ≤ {cap:,}B")
        return 0
    print(f"[injection-budget] ✗ {label} {used:,}B > {cap:,}B — 매 세션 이만큼을 쓴다")
    print(f"    → {hint}")
    return 1


def main() -> int:
    try:
        used_rules, signals = rules_bytes()
    except Exception as err:  # noqa: BLE001 — 측정 실패를 green 으로 위장하지 않는다
        print(f"[injection-budget] ✗ 규범 축 측정 실패: {err}")
        return 1

    print(
        f"[injection-budget] · 최악의 경우로 측정 — conditional {len(signals)}종 전부 켬: "
        + ", ".join(sorted(signals))
    )
    rc = _report(
        "규범+WORKFLOW(최악)", used_rules, RULES_CAP,
        "core 티어를 축약하거나 상시 필요 없는 것을 conditional/reference 로 내려라 (D-17)",
    )

    entries = agent_entries()
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
