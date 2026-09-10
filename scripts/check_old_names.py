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

## 예외

파일 단위 제외(`oldNameScanExclude`)는 **역사 기록에만** 쓴다. 코드에서 구 이름이
정당한 경우 — 구 마커를 읽어 새 마커로 옮기는 **이행 경로** 같은 것 — 는 그 **줄에**
`old-name-ok` 를 적어 예외로 둔다. 파일을 통째로 빼면 그 파일의 미래 잔재까지 안 잡힌다.

## 검사 조건 (한 문장)

**`oldNameScanExclude` 에 없는 git-tracked 파일에 `previousNames` 문자열이 하나라도
있으면 fail.** 분기가 없다 — 항상 돈다(`docs/conventions/warning-signal.md` §검토 절차 4).

제외는 **구 이름이 사실로서 등장해야 하는 곳**만이다: 역사 기록(`docs/`·`CHANGELOG.md`)과
이 정책 파일 자신. 나머지는 전부 대상이다 — 처음에 `plugins/` 만 봤다면 `site/` 의 브랜드
문자열과 `setup.sh` 의 **전임 플러그인 설치 명령**을 놓쳤을 것이다(실측).

구 이름은 매직 리터럴로 박지 않고 이름 정책에서 읽는다(F-022: 게이트를 매직 리터럴에
커플링하면 값이 바뀔 때 검사가 조용히 skip-green 된다). 매칭은 정규식이 아니라
**리터럴 부분문자열**이다 — 이름에 정규식 메타문자가 있어도 오작동하지 않는다.

## 검사 대상 0개는 green 이 아니다

`previousNames` 가 비면 **exit 1** 이다. 예전에는 *"검사 대상 없음"* 이라며 exit 0 을
냈는데, 그 상태의 게이트는 **영원히 아무것도 잡지 않으면서 초록**이다 — 정책 파일이
편집돼 목록이 비는 순간 §20 은 장식이 된다. 바로 옆 `check_shadowed_defs.py` 가 같은
질문에 이미 *"검사 대상 0개는 green 이 아니다"* 로 답하고 있었다. 같은 레포의 두
게이트가 같은 질문에 반대로 답하면, 둘 중 하나는 반드시 틀린 것이다(F-012).

## 읽지 못한 파일은 집계해서 보고한다

읽기 실패를 `continue` 로 삼키면 *"구 이름 0건"* 과 *"파일을 한 개도 못 읽었다"* 가
출력에서 구분되지 않는다. `git_tracked.SkipTally` 로 사유별로 모아 개수·비율·경로를
인쇄한다. `OSError` 는 **red** 다(경로가 틀렸거나 권한이 없다 = 사각지대), 비-UTF-8
바이너리는 노란 보고다(줄 단위 텍스트 검사의 대상이 아닌 것이 정상).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from git_tracked import SkipTally, tracked_files

REPO_ROOT = Path(__file__).resolve().parent.parent
POLICY = REPO_ROOT / "packaging" / "name-targets.json"
DEFAULT_EXCLUDE = ("docs/", "CHANGELOG.md", "packaging/name-targets.json")

# 줄 단위 예외 표기. **파일 단위 제외를 쓰지 않는 이유**가 여기 있다 — 파일을 통째로
# 빼면 그 파일의 *미래* 잔재까지 영영 안 잡힌다(warning-signal.md §검토 절차 5의
# "검사 대상이 아닌 것은 결코 red 가 되지 않는다"). 구 이름이 정당한 줄은 소수이고
# 이유가 분명하므로(구 마커 인식 = 이행 경로), 그 줄만 표기하고 나머지는 계속 검사한다.
LINE_OPT_OUT = "old-name-ok"
LABEL = "check-old-names"

# **기본은 red 다** — 노랑으로 내릴 사유만 등재한다(git_tracked.SkipTally.report 참고).
# 바이너리는 줄 단위 텍스트 검사 대상이 아니므로 정상이고, 읽기 실패는 사각지대이므로
# 등재하지 않는다(= red). 새 사유가 생기면 여기 없으므로 red 가 된다 — 의도한 기본값이다.
NONFATAL_SKIP_REASONS = frozenset({"비-UTF-8"})


def load_previous_names() -> list[str]:
    """이름 정책에서 구 이름 목록을 읽는다. 정책을 못 읽으면 exit 1.

    빈 목록을 그대로 반환한다 — 그것을 통과로 볼지 결함으로 볼지는 `main` 이 정한다.
    """
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


def scan_targets(exclude: tuple[str, ...]) -> list[str]:
    """추적 파일 중 제외 접두사에 걸리지 않는 것 — 생성물·캐시의 우연한 매치를 배제한다."""
    return [
        rel for rel in tracked_files(REPO_ROOT, label=LABEL)
        if not any(rel.startswith(pre) for pre in exclude)
    ]


def find_hits(
    names: list[str], exclude: tuple[str, ...]
) -> tuple[list[tuple[str, str]], SkipTally]:
    """(파일, 걸린 이름) 목록과 **못 읽은 파일 집계**를 함께 반환한다.

    집계를 함께 돌려주는 것이 핵심이다 — 반환값이 hits 뿐이면 호출부는 "0건"이
    *검사해서 없음* 인지 *못 읽어서 없음* 인지 구분할 수 없다.
    """
    hits: list[tuple[str, str]] = []
    skipped = SkipTally(LABEL)
    for rel in scan_targets(exclude):
        skipped.attempted += 1
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except OSError as err:
            skipped.add(rel, "읽기실패", str(err))
            continue
        except UnicodeDecodeError:
            skipped.add(rel, "비-UTF-8", "바이너리 — 줄 단위 텍스트 검사 대상 아님")
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if LINE_OPT_OUT in line:
                continue
            for name in names:
                if name in line:
                    hits.append((f"{rel}:{lineno}", name))
                    break
    return hits, skipped


def main() -> int:
    names = load_previous_names()
    if not names:
        print(
            f"[{LABEL}] ✗ 검사할 이름이 0개다 — 통과가 아니라 설정 결함이다. "
            f"{POLICY.relative_to(REPO_ROOT)} 의 'previousNames' 가 비어 있으면 "
            "이 게이트는 영원히 아무것도 잡지 않으면서 초록을 낸다."
        )
        return 1
    exclude = load_exclude()
    hits, skipped = find_hits(names, exclude)
    rc = skipped.report(NONFATAL_SKIP_REASONS)
    if hits:
        print(f"[{LABEL}] ✗ 구 이름 {len(hits)}건 — 살아있는 표면에 개명 잔재")
        for rel, name in hits:
            print(f"    {rel}  ({name})")
        return 1
    print(
        f"[{LABEL}] {'✗' if rc else '✓'} 살아있는 표면에 구 이름 0건 "
        f"({', '.join(names)}) — {skipped.parsed}개 파일 검사"
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())
