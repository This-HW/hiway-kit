#!/usr/bin/env python3
"""문서 카운트 drift 가드 — 단일 소스 (F-023).

verify-done.sh §6(로컬 DoD 게이트)과 .github/workflows/validate.yml(CI)이 **둘 다
이 스크립트를 호출**한다. 카운트 검사 로직을 bash/CI에 각각 두면 반드시 드리프트한다
(원장 F-023) — 정의와 검사 전부를 여기 한 곳에만 둔다.

정의 (SSOT):
  - agent  = plugins/*/agents/ 아래 frontmatter `name:` 보유 .md
             (경로 기반 전체 .md 카운트는 보조 문서가 끼면 부풀므로 사용하지 않음)
  - skill  = plugins/*/skills/**/SKILL.md
  - rule   = plugins/common/rules/*.md

시맨틱 (verify-done §6 계승):
  - 문서에 카운트 주장이 없으면 skip(통과) — 주장 없음은 drift가 아님.
  - 단 README "What's Included" 표 행은 **부재 자체가 실패** — 값이 바뀌면 검사가
    조용히 skip-green되는 self-disable 패턴 차단 (재감사 R2/ATK-001, F-022).

exit 0 = 전부 일치 / exit 1 = drift 또는 표 행 부재.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

OK = "\033[32m✓\033[0m"
NG = "\033[31m✗\033[0m"


def count_actuals(root: Path) -> dict:
    agents = 0
    for f in root.glob("plugins/*/agents/**/*.md"):
        try:
            if re.search(r"^name:", f.read_text(encoding="utf-8"), re.MULTILINE):
                agents += 1
        except OSError:
            pass
    return {
        "agents": agents,
        "skills_common": len(list(root.glob("plugins/common/skills/**/SKILL.md"))),
        "skills_total": len(list(root.glob("plugins/*/skills/**/SKILL.md"))),
        "rules": len(list(root.glob("plugins/common/rules/*.md"))),
    }


def check_claim(root: Path, rel: str, pattern: str, actual: int, label: str) -> bool:
    """**모든** 매치의 숫자를 실측과 대조. 주장 없음 = skip(통과).

    첫 매치만 보면 같은 파일에 같은 주장이 여러 번 있을 때 앞의 하나가 뒤를 가린다 —
    실제로 `site/content/_index.md`의 설명줄이 본문 불릿을 가려, 불릿만 stale해도
    게이트가 초록이었다(2026-08-23 리뷰 후속 실측). 매직 리터럴에 커플링된 검사가
    조용히 무력해지는 F-022와 같은 계열이다.
    """
    p = root / rel
    if not p.exists():
        print(f"{OK} {label}: 파일 없음 (skip)")
        return True
    text = p.read_text(encoding="utf-8")
    # **대소문자 무관**으로 찾는다. 소문자 패턴(`rules \(N\)`)만 보던 시절 README 의
    # 하네스 표에 있는 `Rules (13)` 이 **한 번도 검사되지 않았고**, 실제로 15 와 어긋난
    # 채 공개 표면에 남아 있었다(2026-09-09 실측). 같은 파일의 소문자 주장은 정상이라
    # 게이트가 초록이었다 — 검사 대상 밖에 결함이 쌓이는 §5 형태 그대로다.
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    if len(matches) > 1:
        bad = [int(m.group(1)) for m in matches if int(m.group(1)) != actual]
        if bad:
            print(f"{NG} {label}: 주장 {bad} ≠ 실제 {actual} ({rel}, 매치 {len(matches)}건)")
            return False
        print(f"{OK} {label}: {actual} 일치 (매치 {len(matches)}건 전부)")
        return True
    m = matches[0] if matches else None
    if m is None:
        print(f"{OK} {label}: 주장 없음 (skip)")
        return True
    claim = int(m.group(1))
    if claim == actual:
        print(f"{OK} {label}: {actual} 일치")
        return True
    print(f"{NG} {label}: 문서 주장 {claim} ≠ 실제 {actual} ({rel})")
    return False


def check_included_table(root: Path, a: dict) -> bool:
    """README 'What's Included' 표의 플러그인 행 — 부재 = 실패 (anti self-disable).

    행을 찾는 이름은 **SSOT(plugin.json)에서 읽는다** — 하드코딩하면 개명이
    검사기 자신을 깨뜨린다(v3.0.0 개명에서 실제로 그랬다). D-3 의 "이름은 SSOT 에서
    파생한다"가 게이트에도 적용된다.
    """
    p = root / "README.md"
    if not p.exists():
        print(f"{NG} README.md 없음")
        return False
    import json as _json
    _mp = root / "plugins" / "common" / ".claude-plugin" / "plugin.json"
    _name = _json.loads(_mp.read_text(encoding="utf-8"))["name"]
    row = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\|\s*.?" + re.escape(_name) + r".?\s*\|", line):
            row = line
            break
    if row is None:
        print(f"{NG} README What's Included 표 행을 찾지 못함 (형식 변경? 게이트 갱신 필요)")
        return False
    nums = re.findall(r"\d+", row)
    ok = True
    if len(nums) < 2:
        print(f"{NG} README 표 행에서 숫자 2개(agents/skills)를 찾지 못함: {row!r}")
        return False
    if int(nums[0]) != a["agents"]:
        print(f"{NG} README 표 에이전트 셀: {nums[0]} ≠ 실제 {a['agents']}")
        ok = False
    else:
        print(f"{OK} README 표 에이전트 셀: {a['agents']} 일치")
    if int(nums[1]) != a["skills_common"]:
        print(f"{NG} README 표 스킬 셀: {nums[1]} ≠ 실제 {a['skills_common']}")
        ok = False
    else:
        print(f"{OK} README 표 스킬 셀: {a['skills_common']} 일치")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."), help="repo root (테스트용)")
    args = ap.parse_args()
    root = args.root

    a = count_actuals(root)
    ok = True
    # 루트 CLAUDE.md / README.md (verify-done §6 계승 패턴)
    ok &= check_claim(root, "CLAUDE.md", r"rules \((\d+)\)", a["rules"], "rules(CLAUDE.md)")
    ok &= check_claim(root, "README.md", r"rules \((\d+)\)", a["rules"], "rules(README)")
    ok &= check_claim(root, "CLAUDE.md", r"skills \((\d+)\)", a["skills_common"], "common skills(CLAUDE.md)")
    ok &= check_claim(root, "CLAUDE.md", r"agents \((\d+)\)", a["agents"], "agents(CLAUDE.md)")
    ok &= check_claim(root, "README.md", r"(\d+) skills", a["skills_total"], "total skills(README)")
    ok &= check_claim(root, "README.md", r"(\d+) agents", a["agents"], "agents(README)")
    ok &= check_included_table(root, a)
    # 배포 플러그인 README (2026-07-29 외부 검증에서 stale 발견된 파일 — 이후 상시 검사)
    ok &= check_claim(root, "plugins/common/README.md", r"(\d+) agents", a["agents"], "agents(common/README)")
    ok &= check_claim(root, "plugins/common/README.md", r"(\d+) skills", a["skills_common"], "skills(common/README)")
    # 공개 사이트도 카운트를 주장한다. 여기 없으면 README/CLAUDE.md만 갱신되고
    # 사이트가 조용히 stale해진다 — 게이트의 사각지대였다(2026-08-23 리뷰 지적).
    # 한국어/영어 페이지는 **어순이 다르다**("19개 스킬" vs "스킬 **19개**"). 한 패턴만
    # 걸면 한쪽 표기가 아예 매치되지 않아 조용히 skip(통과)된다 — 검사가 있는 척만 한다.
    site_patterns = [
        (r"(\d+)\s*개 전문 에이전트", "agents"),
        (r"에이전트\s*\*\*(\d+)\s*개\*\*", "agents"),
        (r"(\d+)\s+specialized agents", "agents"),
        (r"\*\*(\d+)\*\*\s+agents", "agents"),
        (r"(\d+)\s*개 스킬", "skills"),
        (r"스킬\s*\*\*(\d+)\s*개\*\*", "skills"),
        (r"(\d+)\s+skills", "skills"),
        (r"\*\*(\d+)\*\*\s+skills", "skills"),
        # 룰 카운트는 **대상 밖이었다.** agents·skills 만 걸어 두고 rules 를 빼 놓았더니
        # 사이트 두 페이지가 13 에 멈춘 채 실제 15 와 어긋나 있었다(2026-09-10 실측).
        # 이 파일이 위에서 두 번이나 적은 §5 형태를 이 목록 자신이 또 밟았다.
        (r"(\d+)\s*개 거버넌스 룰", "rules"),
        (r"거버넌스 룰\s*\*\*(\d+)\s*개\*\*", "rules"),
        (r"(\d+)\s+governance rules", "rules"),
        (r"\*\*(\d+)\*\*\s+governance rules", "rules"),
    ]
    kind_actual = {
        "agents": a["agents"],
        "skills": a["skills_common"],
        "rules": a["rules"],
    }
    for rel in ("site/content/_index.md", "site/content/_index.en.md"):
        for pat, kind in site_patterns:
            ok &= check_claim(root, rel, pat, kind_actual[kind], f"{kind}({rel}: {pat[:18]}…)")

    if ok:
        print(f"{OK} doc counts: {a['agents']} agents / {a['skills_common']} skills / {a['rules']} rules — 문서와 일치")
        return 0
    print("→ 문서의 수기 카운트가 실측과 drift. 문서를 갱신하세요.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
