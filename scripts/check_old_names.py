#!/usr/bin/env python3
"""check_old_names.py — 배포물(plugins/)에 구 프로젝트 이름이 실렸는지 검사한다.

`verify-done.sh §20` 과 CI 가 **같은 스크립트**를 호출한다 — bash 로 재구현하면
로직이 이중화되어 반드시 드리프트한다(F-023).

## 왜 §18(이름 SSOT 파생)로 부족한가

`packaging/name-targets.json` 의 파생 정책은 `files`/`directories` 에 나열된 **산문
문서**만 치환·검사한다. `plugins/` 는 그 목록에 없었고, 그 사이로 구 이름 14건이
배포 표면에 그대로 실려 나갔다. 그중 둘은 주석이 아니라 **기능 결함**이었다 —
스킬의 플러그인 캐시 fallback glob 이 구 이름 디렉토리를 찾도록 박혀 있어서
개명 이후 영영 매치되지 않았다. "검사 대상이 아닌 것은 결코 red 가 되지 않는다"
(D-23)의 실측 사례다.

## 검사 조건 (한 문장)

**`oldNameScanExclude` 에 없는 git-tracked 파일에 `previousNames` 문자열이 하나라도
있으면 fail.** 분기가 없다 — 항상 돈다(`docs/conventions/warning-signal.md` §검토 절차 4).

제외는 **구 이름이 사실로서 등장해야 하는 곳**만이다: 역사 기록(`docs/`·`CHANGELOG.md`)과
이 정책 파일 자신. 나머지는 전부 대상이다 — 처음에 `plugins/` 만 봤다면 `site/` 의 브랜드
문자열과 `setup.sh` 의 **전임 플러그인 설치 명령**을 놓쳤을 것이다(실측).

구 이름은 매직 리터럴로 박지 않고 이름 정책에서 읽는다(F-022: 게이트를 매직 리터럴에
커플링하면 값이 바뀔 때 검사가 조용히 skip-green 된다). 매칭은 정규식이 아니라
**리터럴 부분문자열**이다 — 이름에 정규식 메타문자가 있어도 오작동하지 않는다.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
POLICY = REPO_ROOT / "packaging" / "name-targets.json"
DEFAULT_EXCLUDE = ("docs/", "CHANGELOG.md", "packaging/name-targets.json")


def load_previous_names() -> list[str]:
    """이름 정책에서 구 이름 목록을 읽는다. 정책이 없으면 빈 목록(검사 대상 없음)."""
    try:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        print(f"[check-old-names] 이름 정책을 읽지 못했다: {POLICY} ({err})")
        raise SystemExit(1) from err
    names = policy.get("previousNames") or []
    return [n for n in names if isinstance(n, str) and n.strip()]


def load_exclude() -> tuple[str, ...]:
    """제외 접두사를 정책에서 읽는다 — 코드에 박으면 정책과 검사가 갈린다."""
    try:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_EXCLUDE
    raw = policy.get("oldNameScanExclude")
    if not isinstance(raw, list):
        return DEFAULT_EXCLUDE
    return tuple(x for x in raw if isinstance(x, str) and x.strip())


def tracked_files(exclude: tuple[str, ...]) -> list[str]:
    """git 이 추적하는 파일 중 제외 대상이 아닌 것 — 생성물·캐시의 우연한 매치를 배제한다."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(f"[check-old-names] git ls-files 실패: {result.stderr.strip()}")
        raise SystemExit(1)
    return [
        line for line in result.stdout.splitlines()
        if line and not any(line.startswith(pre) for pre in exclude)
    ]


def find_hits(names: list[str], exclude: tuple[str, ...]) -> list[tuple[str, str]]:
    """(파일, 걸린 이름) 목록. 읽을 수 없는 파일은 건너뛴다(바이너리·권한)."""
    hits: list[tuple[str, str]] = []
    for rel in tracked_files(exclude):
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for name in names:
            if name in text:
                hits.append((rel, name))
    return hits


def main() -> int:
    names = load_previous_names()
    if not names:
        print("[check-old-names] ✓ previousNames 비어 있음 — 검사 대상 없음")
        return 0
    exclude = load_exclude()
    hits = find_hits(names, exclude)
    if not hits:
        print(f"[check-old-names] ✓ 살아있는 표면에 구 이름 0건 ({', '.join(names)})")
        return 0
    print(f"[check-old-names] ✗ 구 이름 {len(hits)}건 — 살아있는 표면에 개명 잔재")
    for rel, name in hits:
        print(f"    {rel}  ({name})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
