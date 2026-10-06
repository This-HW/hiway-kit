#!/usr/bin/env python3
"""check_agent_frontmatter.py — 배포 에이전트 frontmatter 의 필수·금지 필드.

`verify-done.sh` §2 와 CI(`validate.yml`)가 같은 이 스크립트를 호출한다.

## 왜 단일 스크립트인가

같은 검사가 CI 두 단계·`verify-done.sh` §2·`setup/pre-commit` 네 곳에 인라인으로
복제돼 있었고, 넷 다 대상을 **`plugins/**/*.md` 에서 `skills/`·`rules/` 만 빼는**
방식으로 잡았다. 그래서 에이전트가 아닌 문서(플러그인 루트의 eval 케이스 `.md` 등)에
frontmatter 가 있으면 **에이전트로 보고** `name`/`description` 을 요구했다 — 5.4.0 의
`claude plugin eval` 파일럿은 케이스를 `.md` 로 둘 수 없어 `case.yaml` 로 우회했다.
반대로 **frontmatter 가 없는 에이전트는 조용히 건너뛰었다** — 검사하지 못한 것을
통과로 셌다.

## 검사 조건 (한 문장)

**`plugins/*/agents/*.md` 전부에 대해 항상** — frontmatter 가 있어야 하고, 최상위
`name`·`description`·`model`·`maxTurns` 가 있어야 하며, `name` 은 파일 이름과 같고,
금지 필드(`FORBIDDEN_KEYS`)는 없어야 한다. 대상은 나열하지 않고 디렉토리에서 파생한다
— 새 에이전트는 놓이는 것만으로 대상이 된다. Claude Code 가 에이전트를 찾는 곳이
바로 그 디렉토리이므로 대상의 정의도 거기서 온다(하위 폴더 금지는 `check_doc_counts.py`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: CLAUDE.md Contributing 체크리스트의 필수 필드.
REQUIRED_KEYS = ("name", "description", "model", "maxTurns")

#: CLAUDE.md Contributing 의 금지 필드 — 플러그인 에이전트에서 무시되거나 의미가 없다.
FORBIDDEN_KEYS = (
    "permissionMode",
    "context_cache",
    "output_schema",
    "next_agents",
    "hooks",
)

_TOP_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:", re.MULTILINE)
_NAME_RE = re.compile(
    r"^name\s*:\s*['\"]?([^'\"\n#]+?)['\"]?\s*(?:#.*)?$", re.MULTILINE
)


def frontmatter(text: str) -> str | None:
    """첫 줄 `---` 과 다음 `---` 줄 사이를 돌려준다. 구조가 없으면 None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:i])
    return None


def check(path: Path) -> list[str]:
    """한 에이전트 파일의 위반 목록. 비어 있으면 통과."""
    try:
        fm = frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as err:
        return [f"읽지 못함 ({err})"]
    if fm is None:
        return [
            "frontmatter 없음 또는 닫히지 않음 — 에이전트는 frontmatter 가 계약이다"
        ]
    keys = set(_TOP_KEY_RE.findall(fm))
    errs = [f"필수 필드 없음: {k}" for k in REQUIRED_KEYS if k not in keys]
    errs += [f"금지 필드: {k}" for k in FORBIDDEN_KEYS if k in keys]
    m = _NAME_RE.search(fm)
    if m and m.group(1).strip() != path.stem:
        errs.append(f"name '{m.group(1).strip()}' ≠ 파일 이름 '{path.stem}'")
    return errs


def main() -> int:
    agents = sorted((REPO_ROOT / "plugins").glob("*/agents/*.md"))
    if not agents:
        # 0 건은 통과가 아니다 — 파생 경로가 깨졌다는 뜻이다.
        print(
            "[agent-frontmatter] ✗ 에이전트 .md 를 하나도 찾지 못했다 — 파생 경로가 깨졌다"
        )
        return 1
    bad: list[str] = []
    for p in agents:
        rel = p.relative_to(REPO_ROOT).as_posix()
        bad += [f"{rel}: {e}" for e in check(p)]
    if bad:
        print(f"[agent-frontmatter] ✗ 위반 {len(bad)}건")
        for b in bad:
            print(f"    {b}")
        print("    → CLAUDE.md 'Agent Frontmatter' 템플릿대로 고쳐라")
        return 1
    print(
        f"[agent-frontmatter] ✓ 에이전트 {len(agents)}종 — 필수 필드·이름 일치·금지 필드 없음"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
