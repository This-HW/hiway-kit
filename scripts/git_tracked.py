#!/usr/bin/env python3
"""git_tracked.py — 게이트 스크립트가 공유하는 **추적 파일 목록 + 건너뜀 집계**.

`check_old_names.py` 와 `check_shadowed_defs.py` 가 같은 방식으로 파일을 고르고
같은 방식으로 "못 읽은 파일"을 보고하게 만드는 단일 지점이다. 두 게이트가 각자
`git ls-files` 를 부르던 시절, **둘 다 같은 두 결함을 갖고 있었다** — 복제 로직은
결함까지 복제한다(F-023).

## 왜 `-z` + `core.quotePath=false` 인가

git 의 기본값 `core.quotePath=true` 는 비-ASCII 경로를 **따옴표 + 8진 이스케이프**로
출력한다:

    plugins/한글.md  →  "plugins/\\355\\225\\234\\352\\270\\200.md"

그 문자열은 **실제 경로가 아니다.** 호출부가 그것으로 파일을 열면 `OSError` 가 나고,
두 게이트는 그것을 `continue` / `return {}` 로 **조용히 건너뛰었다** — 한글 파일명
하나가 곧 게이트의 사각지대였다. 개행이 든 파일명은 `splitlines()` 가 한 줄을 둘로
쪼개 같은 결과를 낳는다.

`-z`(NUL 구분) + `core.quotePath=false`(이스케이프 금지) 조합이 이 둘을 동시에 막는다.
**둘 다 필요하다** — `-z` 만 쓰면 이스케이프가 남고, `quotePath=false` 만 쓰면 개행이
든 파일명이 여전히 쪼개진다.

## 왜 건너뜀을 집계하는가

*"통과했다"* 와 *"돌지 않았다"* 가 집계에서 구분되지 않으면 게이트 전체의 신뢰가
무너진다. 못 읽은 파일이 하나라도 있으면 **개수·비율·경로를 인쇄한다** — 조용한
초록은 이 레포에서 최악의 결함 등급이다(F-012,
`docs/conventions/warning-signal.md` §검토 절차 4·5).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def tracked_files(
    repo_root: Path,
    patterns: tuple[str, ...] = (),
    label: str = "gate",
) -> list[str]:
    """`repo_root` 가 추적하는 파일 경로 목록. 실패하면 exit 1(green 으로 위장하지 않는다).

    비-ASCII·개행이 든 파일명도 **실제 경로 그대로** 돌아온다 — 위 독스트링 참고.

    **디코딩도 명시한다.** git 쪽만 `-z` + `core.quotePath=false` 로 고치고 Python 쪽
    디코딩을 미지정으로 두면, `text=True` 가 로케일 인코딩(`LC_ALL=C` 인 CI 컨테이너·
    cron·sudo 환경에서는 ASCII)으로 **strict** 디코딩해 비-ASCII 파일명 하나에
    `UnicodeDecodeError` 로 죽는다 — 이 모듈이 고치려던 바로 그 사각지대가 다른 층에서
    되살아난다. UTF-8 이 아닌 파일명(리눅스는 바이트열이면 무엇이든 허용한다)도
    `surrogateescape` 로 받아 **경로를 잃지 않는다** — 파일시스템 경로 규약과 같은 처리다.

    타임아웃도 건다. 이 레포의 다른 subprocess 호출은 전부 시한이 있는데 여기만
    무기한이면, 깨진 저장소에서 게이트가 조용히 멈춘다.
    """
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", "ls-files", "-z", *patterns],
        cwd=str(repo_root), capture_output=True, check=False,
        encoding="utf-8", errors="surrogateescape", timeout=30,
    )
    if result.returncode != 0:
        print(f"[{label}] git ls-files 실패: {result.stderr.strip()}")
        raise SystemExit(1)
    return [rel for rel in result.stdout.split("\0") if rel]


class SkipTally:
    """읽기·파싱에 실패한 파일을 사유별로 모아 **비율과 함께** 보고한다.

    `attempted` 는 시도한 수, `len(self)` 는 못 읽은 수다. 둘을 함께 인쇄하지 않으면
    *"N개 파일 검사함"* 이 실제로는 *"N개를 시도했고 전부 실패함"* 일 수 있다.
    """

    def __init__(self, label: str) -> None:
        self.label = label
        self.attempted = 0
        self.entries: list[tuple[str, str, str]] = []  # (경로, 사유코드, 상세)

    def __len__(self) -> int:
        return len(self.entries)

    def add(self, rel: str, reason: str, detail: str) -> None:
        self.entries.append((rel, reason, detail))

    @property
    def parsed(self) -> int:
        return self.attempted - len(self.entries)

    def report(self, nonfatal_reasons: frozenset[str]) -> int:
        """건너뜀을 인쇄하고 종료코드 기여분을 반환한다(**기본이 치명**, 예외만 노랑).

        사유가 하나도 없으면 아무것도 인쇄하지 않는다 — 상시 참인 줄은 소음이고,
        소음은 옆의 진짜 경고까지 죽인다(`warning-signal.md`).

        ## 왜 `fatal_reasons` 가 아니라 `nonfatal_reasons` 인가

        이 인자는 원래 **치명 사유의 화이트리스트**였다. 그러면 호출부가 새 건너뜀
        사유를 추가할 때 그 사유는 목록에 없으므로 **기본이 노랑**이 되고, 게이트는
        조용히 커버리지를 잃는다 — 이 모듈 독스트링이 비판하는 바로 그 구조다
        (`warning-signal.md` §검토 절차 5: *"대상을 나열하는 검사는 목록에 없는 것을
        결코 red 로 만들지 못한다. 가능하면 대상을 나열하지 말고 제외를 나열한다."*).

        뒤집으면 **새 사유는 기본으로 red** 가 되고, 노랑으로 내리려면 호출부가
        그 사유를 명시적으로 등재해 정당화해야 한다. 사각지대는 침묵이 아니라
        선언을 요구한다.
        """
        if not self.entries:
            return 0
        pct = 100.0 * len(self.entries) / self.attempted if self.attempted else 100.0
        fatal = [e for e in self.entries if e[1] not in nonfatal_reasons]
        mark = "✗" if fatal else "!"
        print(
            f"[{self.label}] {mark} 검사하지 못한 파일 {len(self.entries)}건 "
            f"/ 시도 {self.attempted}건 ({pct:.1f}%) — 실제로 검사한 것은 {self.parsed}건이다"
        )
        for rel, reason, detail in self.entries:
            print(f"    {rel}  [{reason}] {detail}")
        if fatal:
            print(
                f"    → 이 {len(fatal)}건은 게이트의 사각지대다 — "
                "건너뛴 채 초록을 내지 않는다"
            )
            return 1
        return 0


if __name__ == "__main__":  # 진단용 — 게이트가 무엇을 보는지 눈으로 확인할 때
    root = Path(__file__).resolve().parent.parent
    listed = tracked_files(root, tuple(sys.argv[1:]))
    print(f"{len(listed)}개 파일")
