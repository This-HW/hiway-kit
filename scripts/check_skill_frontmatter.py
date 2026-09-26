#!/usr/bin/env python3
"""check_skill_frontmatter.py — 스킬 frontmatter 는 `model`·`effort` 를 선언하지 않는다.

`verify-done.sh` §25 와 CI(`validate.yml`)가 같은 이 스크립트를 호출한다.

## 무엇을 막는가

스킬 frontmatter 의 `effort` 는 스킬을 로드한 **세션 자체의** effort 를 덮어쓴다 —
에이전트처럼 별도 컨텍스트에서 도는 것이 아니다. 양성 대조 `[confirmed 2026-09-27]`:
같은 프롬프트·`--effort high` 로 (A) 스킬 없이 → 3턴 모두 high, (B) `effort: medium`
스킬을 로드 → 로드 이후 세션 끝까지 **medium**. W-045 워커 전원이 `--effort high` 로
떴는데 `child-session`(`effort: medium`) 로드 직후부터 조용히 medium 으로 돌았다.

방향은 양쪽이다 — `medium` 스킬은 세션을 몰래 낮추고, `max` 스킬은 세션 끝까지
max 로 올려 비용을 쓴다. 어느 쪽이든 **킷이 사용자 설정을 덮어쓰는 것**이고,
"모델·effort 는 사용자/호스트 설정의 몫"(control-loop)과 정면으로 충돌한다.
`model` 은 메인 스레드에 적용되지 않는 것이 관측됐지만 `[관측 n=1]`, 적용되는
호스트가 있으면 같은 결함이므로 함께 금지한다.

**에이전트 frontmatter 는 대상이 아니다** — 에이전트는 별도 컨텍스트에서 돌고,
그 깊이가 배포되는 계약이다(evals 가 그것을 잰다).

## 검사 조건 (한 문장)

**`plugins/*/skills/` 아래의 모든 `SKILL.md` 의 frontmatter 에 최상위 `model:`·`effort:`
키가 있으면 red.** 대상은 나열하지 않고 디렉토리에서 파생한다 — 새 스킬은 놓이는
것만으로 대상이 된다(`docs/conventions/warning-signal.md` §검토 절차 5). 예외는
`EXEMPT` 에만, 사유와 함께 등재한다.

frontmatter 를 읽지 못한 스킬(구분자 없음·닫힘 없음)도 red 다 — 검사하지 못한 것을
통과로 세지 않는다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: 스킬 frontmatter 에 있으면 안 되는 키. 둘 다 세션 설정을 덮어쓸 수 있다.
FORBIDDEN_KEYS = ("model", "effort")

#: 금지 키를 선언해도 되는 스킬. **비우는 것이 기본이다** — 등재하려면 왜 그 스킬은
#: 세션 effort·model 을 덮어써도 되는지를 여기 한 줄로 적어라.
EXEMPT: dict[str, str] = {}

_KEY_RE = re.compile(rf"^({'|'.join(FORBIDDEN_KEYS)})\s*:", re.MULTILINE)


def frontmatter(text: str) -> str | None:
    """첫 줄 `---` 과 다음 `---` 줄 사이를 돌려준다. 구조가 없으면 None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:i])
    return None


def main() -> int:
    plugins_dir = REPO_ROOT / "plugins"
    skills = sorted(plugins_dir.glob("*/skills/**/SKILL.md"))
    if not skills:
        # 0 건은 통과가 아니다 — 파생 경로가 깨졌다는 뜻이다.
        print(
            "[skill-frontmatter] ✗ SKILL.md 를 하나도 찾지 못했다 — 파생 경로가 깨졌다"
        )
        return 1

    violations: list[str] = []
    unreadable: list[str] = []
    for p in skills:
        rel = p.relative_to(REPO_ROOT).as_posix()
        try:
            fm = frontmatter(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as err:
            unreadable.append(f"{rel} ({err})")
            continue
        if fm is None:
            unreadable.append(f"{rel} (frontmatter 구분자 없음)")
            continue
        if p.parent.name in EXEMPT:
            continue
        keys = sorted(set(_KEY_RE.findall(fm)))
        if keys:
            violations.append(f"{rel}: {', '.join(keys)}")

    rc = 0
    if unreadable:
        print(
            f"[skill-frontmatter] ✗ frontmatter 를 읽지 못한 스킬 {len(unreadable)}건 — 검사 불가"
        )
        for u in unreadable:
            print(f"    {u}")
        rc = 1
    if violations:
        print(
            f"[skill-frontmatter] ✗ model/effort 를 선언한 스킬 {len(violations)}건 — "
            "스킬 frontmatter 의 effort 는 로드한 세션의 effort 를 세션 끝까지 덮어쓴다"
        )
        for v in violations:
            print(f"    {v}")
        print("    → 그 줄을 지워라. 모델·effort 는 사용자/호스트 설정의 몫이다")
        print(
            "      (깊이가 필요한 일은 frontmatter 에 effort 를 가진 에이전트에 위임한다)"
        )
        rc = 1
    if rc == 0:
        print(f"[skill-frontmatter] ✓ 스킬 {len(skills)}종 모두 model/effort 미선언")
    return rc


if __name__ == "__main__":
    sys.exit(main())
