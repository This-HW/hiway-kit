#!/usr/bin/env python3
"""check_skill_degradation.py — 위임을 지시하는 스킬은 **강등 경로**를 가져야 한다.

`verify-done.sh` 가 호출한다.

## 무엇을 막는가

이 킷의 스킬은 **모든 하네스에 배송된다** — Codex 세션이 21종 전량을 인식하는 것이
실측됐다. 그런데 그중 일부는 본문에서 `subagent_type:` 으로 **서브에이전트 위임을
지시**하고, **Codex 에는 그 수단이 없다**(같은 실측에서 확인).

그 상태는 "수단이 없어 그냥 진행"보다 나쁘다 — **없는 도구를 쓰라고 지시**하므로 모델이
실패하거나, 지시를 무시하고 임의로 진행하거나, **하지 않은 위임을 했다고 보고**한다.
`rules/parallel-worktree.md` 가 같은 이유로 운송 중립화됐다: *주입되는 지시가 그
하네스에 없는 수단을 가리킨다.* 그때 판정은 **"규범 없음보다 나쁘다"** 였다.

## 왜 규약이 아니라 게이트인가

강등 경로를 4종에 넣은 것은 **인스턴스 수정**이다. 다음 달 새 스킬이 `subagent_type:` 을
쓰면 **조용히 재발**한다 — 이 레포가 반복해서 배운 형태다(열거는 낡고, 규약은 드리프트한다).
그래서 검사로 고정한다.

## 검사 조건 (한 문장)

**`plugins/common/skills/*/SKILL.md` 중 위임 토큰을 포함한 파일은 강등 마커도 포함해야
한다.** 대상은 나열하지 않고 디렉토리에서 **파생**한다 — 새 스킬은 놓이는 것만으로 대상이
된다(`docs/conventions/warning-signal.md` §검토 절차 5).

`DEGRADATION_MARKER` 문자열 자체가 계약이다. 문구를 바꾸면 이 게이트가 **시끄럽게**
깨진다 — 그것이 의도다. 조용히 통과하는 것보다 낫다.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "plugins" / "common" / "skills"

#: 위임을 **지시**하는 토큰. 산문 언급이 아니라 실행 지시에만 등장하는 형태로 좁힌다.
DELEGATION_TOKENS = ("subagent_type:", "Task tool 사용:")

#: 강등 경로가 있다는 계약 문자열. 이 문구가 계약이다 — 바꾸면 게이트가 깨진다.
DEGRADATION_MARKER = "위임 수단이 없는 하네스"

#: 위임 토큰을 갖지만 강등이 면제되는 스킬. **비우는 것이 기본이다** — 등재하려면
#: 왜 그 스킬은 다른 하네스에서 강등할 필요가 없는지를 여기 한 줄로 적어라.
EXEMPT: dict[str, str] = {}


def main() -> int:
    if not SKILLS_DIR.is_dir():
        print(f"[skill-degradation] ✗ 스킬 디렉토리가 없다: {SKILLS_DIR}")
        return 1
    skills = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    if not skills:
        # 0 건은 통과가 아니다 — 파생 경로가 깨졌다는 뜻이다.
        print("[skill-degradation] ✗ SKILL.md 를 하나도 찾지 못했다 — 파생 경로가 깨졌다")
        return 1

    delegating: list[str] = []
    missing: list[str] = []
    unreadable: list[str] = []
    for p in skills:
        name = p.parent.name
        try:
            body = p.read_text(encoding="utf-8")
        except OSError as err:
            unreadable.append(f"{name} ({err})")
            continue
        if not any(tok in body for tok in DELEGATION_TOKENS):
            continue
        delegating.append(name)
        if name in EXEMPT:
            continue
        if DEGRADATION_MARKER not in body:
            missing.append(name)

    if unreadable:
        print(f"[skill-degradation] ✗ 읽지 못한 스킬 {len(unreadable)}건: {', '.join(unreadable)}")
        return 1
    if missing:
        print(
            f"[skill-degradation] ✗ 위임을 지시하면서 강등 경로가 없는 스킬 {len(missing)}건 "
            f"— 그 하네스에 없는 도구를 쓰라고 지시한다"
        )
        for n in missing:
            print(f"    {n}: {DELEGATION_TOKENS} 는 있는데 {DEGRADATION_MARKER!r} 가 없다")
        print("    → 위임을 **계약**과 **운송**으로 나누고, 수단이 없는 하네스에서 같은")
        print("      계약을 직접 수행하는 경로를 적어라 (skills/review 를 본떠라)")
        return 1
    print(
        f"[skill-degradation] ✓ 위임 지시 {len(delegating)}종 모두 강등 경로 보유 "
        f"(스킬 {len(skills)}종 검사)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
