#!/usr/bin/env python3
"""check_installed_hooks.py — 설치된 git 훅이 이 레포의 정본과 같은지 대조한다.

`verify-done.sh §21` 이 호출한다. **로컬 전용이다** — CI 에는 `~/.claude` 도 설치된
훅도 없으므로 CI 스텝을 만들지 않는다(없는 것을 검사한다고 주장하지 않는다).

## 무엇을 막는가

이 킷의 대표 결함 클래스는 *"커밋·테스트·문서를 다 갖춘 가드가 설치본에 없어 집행이
0회"* 다. 실측(v3.7.0): `.private-names` 비공개 이름 차단이 `setup/pre-commit` 소스에만
있고 어느 저장소에도 설치되지 않은 채 "활성"으로 릴리스 보고됐다. 원인은 `session-check`
가 훅이 **없을 때만** 설치해 최초 판이 영구 동결된 것이었다(v3.8.0 수정). 고쳤어도 이
검사가 있어야 다음번에 같은 형태가 조용히 지나가지 않는다.

## 왜 red 가 아니라 경고인가

훅 소스를 고치는 중에는 repo 가 설치본보다 앞선 것이 **정상**이다. red 로 두면 훅 작업
내내 발화해 죽은 경고가 된다(`docs/conventions/warning-signal.md` §검토 절차 1).
`§3b`·`§19` 와 같은 비대칭이다.

## 미설치의 의미가 훅마다 다르다

- `pre-commit` — `session-check` 가 자동 설치한다. **없으면** 집행이 안 도는 것이므로 알린다.
- `reference-transaction` — opt-in 이다. **없는 것이 정상**이므로 침묵한다. 안 켠 것을
  결함으로 보고하면 켜지 않은 모든 소비자에게 상시 참이 되어 그 경고가 죽는다.

## 검사 조건 (한 문장)

**설치된 훅이 킷 마커를 갖고 있는데 repo 정본과 내용이 다르면 노란 줄.**
마커가 없으면 소비자 소유 훅이므로 손대지도 대조하지도 않는다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

YELLOW = "\033[33m"
GREEN = "\033[32m"
RESET = "\033[0m"

# (정본 경로, 설치 이름, 마커, 미설치 시 알릴 것인가)
#
# 새 킷 훅이 생기면 여기 한 줄만 더한다 — `warning-signal.md` §검토 절차 5
# ("대상 목록을 나열하는 검사는 목록에 없는 것을 결코 red 로 만들지 못한다")를
# 알고 쓰는 나열이다. 훅은 소수이고 각각 미설치 의미가 달라 제외 방식이 맞지 않는다.
KIT_HOOKS: tuple[tuple[str, str, str, bool], ...] = (
    (
        "plugins/common/setup/pre-commit",
        "pre-commit",
        "# Auto-installed by session-check.py",
        True,
    ),
    (
        "plugins/common/setup/git-hooks/reference-transaction",
        "reference-transaction",
        "# kit-managed-hook",
        False,
    ),
)


def hooks_dir() -> Path | None:
    """`git rev-parse --git-path hooks` 로 얻는다.

    `<repo>/.git/hooks` 로 조립하면 **워크트리에서 깨진다** — 워크트리의 `.git` 은
    디렉토리가 아니라 포인터 파일이다. 이 킷은 워크트리 운영을 권장하므로 조립하지 않는다.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--git-path", "hooks"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else (REPO_ROOT / path)


def check_one(src_rel: str, name: str, marker: str, notify_missing: bool) -> tuple[int, str]:
    """(빨강 수, 출력 한 줄)."""
    src = REPO_ROOT / src_rel
    if not src.is_file():
        return 1, f"  ✗ 훅 정본 없음: {src_rel}"
    hooks = hooks_dir()
    if hooks is None:
        return 0, f"  {YELLOW}! git hooks 경로를 얻지 못했다 — {name} 대조 생략{RESET}"
    dst = hooks / name
    if not dst.is_file():
        if notify_missing:
            return 0, (
                f"  {YELLOW}! {name} 미설치 — 커밋타임 집행이 이 저장소에서 돌지 않는다{RESET}"
            )
        return 0, f"  {GREEN}✓{RESET} {name}: 미설치 (opt-in — 안 켠 것은 결함이 아니다)"
    try:
        installed = dst.read_bytes()
    except OSError as err:
        return 0, f"  {YELLOW}! {name} 을 읽지 못했다 ({err}) — 대조 생략{RESET}"
    if marker.encode() not in installed:
        return 0, f"  {YELLOW}! {name} 이 킷 소유가 아니다(마커 없음) — 대조 생략{RESET}"
    if installed == src.read_bytes():
        return 0, f"  {GREEN}✓{RESET} 설치된 {name} = repo 정본"
    return 0, (
        f"  {YELLOW}! 설치된 {name} 가 repo 정본과 다르다{RESET}\n"
        f"      정본 {src.stat().st_size} B / 설치본 {dst.stat().st_size} B"
    )


def main() -> int:
    reds = 0
    for src_rel, name, marker, notify in KIT_HOOKS:
        red, line = check_one(src_rel, name, marker, notify)
        reds += red
        print(line)
    return 1 if reds else 0


if __name__ == "__main__":
    sys.exit(main())
