#!/usr/bin/env python3
"""check_consumer_footprint.py — 배포되는 지침이 남의 환경에 설치를 시키지 않는가.

`verify-done.sh §30` 과 CI 가 **같은 스크립트**를 호출한다.

## 검사 조건 (한 문장)

**배포되는 모든 마크다운(`plugins/common/**/*.md`)의 각 줄에 의존성 설치·패키지 내려받아 실행 명령
(`npm ci`·`pip install`·`poetry install`·`uv sync`·`npx …`·`uvx …`·`pipx run` 등)이 있는데 그 줄에
`footprint-ok: <이유>` 표시가 없으면 fail.** 분기가 없다 — 항상 돈다. 대상은 나열하지 않고 디렉토리 전체다
(새 에이전트·스킬은 기본으로 검사 대상이다 — `docs/conventions/warning-signal.md` §5).

## 왜 있는가

`verify-code` 에이전트는 스스로 "읽기 전용"이라 선언하고는 `npm ci`·`pip install -r`·`poetry install`·
`npx` 를 지시했다 — 검증하러 들어간 남의 프로젝트에서 `node_modules`·활성 Python 환경을 바꾼다
(독립 자문 2건, 2026-11-09). 정책은 `docs/conventions/consumer-footprint.md`: 킷은 설치하지 않고
제안만 한다. 금지 문장처럼 명령을 **언급**해야 하는 줄은 그 줄에 `footprint-ok: <이유>` 를 단다 —
문장 해석으로 금지문을 가려내려 하면 오탐과 미탐이 같이 난다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED = REPO_ROOT / "plugins" / "common"

INSTALL_RE = re.compile(
    r"\b("
    r"npm (?:ci|install|i|exec)\b|yarn (?:install|add|dlx)\b|pnpm (?:install|add|i|dlx)\b"
    r"|bun (?:add|install|i)\b|bunx\b"
    r"|pip3? install\b|python3? -m pip install\b|conda install\b"
    r"|poetry (?:install|add)\b|uv (?:sync|add|pip install|tool (?:install|run))\b|uv run --with\b"
    r"|pipx (?:install|run)\b"
    r"|npx\s+(?:-\S+\s+)*[a-z@]|uvx\s+(?:-\S+\s+)*[a-z]"
    r"|brew install\b|apt(?:-get)? install\b|cargo install\b|go (?:install|get)\b|gem install\b"
    r")"
)
#: 예외 표시는 이유가 있어야 한다 — `footprint-ok` 만 붙여 지시를 통과시키지 못하게(리뷰 ATK-008).
OPT_OUT_RE = re.compile(r"footprint-ok:\s*\S")


def violations(root: Path = SHIPPED) -> list[tuple[str, int, str]]:
    found = []
    for path in sorted(root.rglob("*.md")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(lines, start=1):
            match = INSTALL_RE.search(line)
            if match and not OPT_OUT_RE.search(line):
                found.append((str(path.relative_to(REPO_ROOT)), number, match.group(1)))
    return found


def main() -> int:
    found = violations()
    if not found:
        print("[consumer-footprint] ✓ 배포 지침에 설치·패키지 실행 지시 없음")
        return 0
    print(f"[consumer-footprint] ✗ 설치·패키지 실행 명령 {len(found)}건 — 킷은 남의 환경에 설치하지 않는다")
    for rel, number, command in found:
        print(f"    {rel}:{number}  {command}")
    print("    → 지시라면 지우고 '미설치 — 명령 제안'으로 바꿔라. 금지·설명 문장이면 그 줄에 "
          "`<!-- footprint-ok: 이유 -->` (docs/conventions/consumer-footprint.md)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
