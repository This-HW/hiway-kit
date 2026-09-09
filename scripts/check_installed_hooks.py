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

## 미설치의 의미는 **위치에서 파생된다**

- `setup/pre-commit` — `session-check` 가 자동 설치한다. **없으면** 집행이 안 도는
  것이므로 알린다.
- `setup/git-hooks/*` — 그 디렉토리는 **opt-in 훅을 담으려고** 존재한다. **없는 것이
  정상**이므로 침묵한다. 안 켠 것을 결함으로 보고하면 켜지 않은 모든 소비자에게 상시
  참이 되어 그 경고가 죽는다.

훅을 손으로 등록하지 않는다 — 새 훅은 `setup/git-hooks/` 에 놓이는 것만으로 대상이 된다.

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

# 킷 훅 정본이 사는 두 자리. **나열하지 않고 파생한다.**
#
# 이 목록은 원래 훅 세 요소를 손으로 나열했고, 그 옆에 *"훅은 소수이고 각각 미설치
# 의미가 달라 제외 방식이 맞지 않는다"* 는 정당화까지 적혀 있었다. **바로 다음에
# 추가된 훅(`pre-push`)이 그 나열에서 빠졌다** — 등록되지 않은 훅의 드리프트는
# 영원히 잡히지 않는다. `warning-signal.md` §검토 절차 5 가 예측한 그대로다:
# *"대상 목록을 나열하는 검사는 목록에 없는 것을 결코 red 로 만들지 못한다."*
# 나열을 정당화하는 주석을 쓴다고 나열이 안전해지지는 않는다.
#
# 정당화의 전제("각각 미설치 의미가 다르다")도 틀렸다 — 그 의미는 **위치에서
# 파생된다**: `setup/pre-commit` 은 `session-check` 가 자동 설치하므로 없으면 알리고,
# `setup/git-hooks/` 는 **opt-in 훅을 담으려고 존재하는 디렉토리**이므로 없는 것이
# 정상이다. 파일마다 사람이 아는 지식이 아니라 규칙이다.
AUTO_INSTALLED = ("plugins/common/setup/pre-commit",)
OPT_IN_DIR = "plugins/common/setup/git-hooks"

# 설치본이 킷 소유인지 가르는 마커. 소스가 어느 쪽을 갖고 있는지로 고른다.
MARKERS = ("# kit-managed-hook", "# Auto-installed by session-check.py")

# **파생에는 제외 정책이 따라와야 한다.** 나열을 파생으로 바꾼 것만으로는 부족하다 —
# `git-hooks/` 에 README 나 편집기 백업이 하나 생기면 "마커 없는 킷 훅"으로 잡혀
# 훅을 하나도 안 건드렸는데 게이트가 red 가 된다. `warning-signal.md` §5 가 권하는
# 형태는 "대상을 나열하지 말고 **제외를 나열한다**" 이고, 제외 목록이 없으면 그 절반만
# 한 것이다. 제외는 주석이 아니라 **코드 상수**로 둔다.
NON_HOOK_NAMES = frozenset({"README.md", ".gitignore", ".gitkeep"})
NON_HOOK_SUFFIXES = (".md", ".sample", ".bak", ".orig", ".rej", "~")


def _looks_like_hook(path: Path) -> bool:
    """훅 디렉토리 안의 파일 중 **훅이 아닌 것**을 걸러낸다 (제외 방식)."""
    return path.name not in NON_HOOK_NAMES and not path.name.endswith(NON_HOOK_SUFFIXES)


def discover_hooks() -> tuple[list[tuple[str, str, str, bool]], list[str]]:
    """(검사 대상, 마커 없는 정본). 나열이 아니라 파생이다.

    **이 검사가 도는 조건**(`warning-signal.md` §4): `setup/git-hooks/` 안의 모든 파일과
    `AUTO_INSTALLED` 에 적힌 경로. 새 훅은 그 디렉토리에 놓이는 것만으로 대상이 된다.

    마커가 없는 정본은 **건너뛰지 않고 돌려준다** — 호출자가 red 로 만든다. 마커 없는
    킷 훅은 설치본과 대조할 수단이 없으므로, 조용히 통과시키면 그 훅만 감시 밖이 된다.
    """
    targets: list[tuple[str, str, str, bool]] = []
    unmarked: list[str] = []
    srcs = [REPO_ROOT / rel for rel in AUTO_INSTALLED]
    opt_in = REPO_ROOT / OPT_IN_DIR
    if opt_in.is_dir():
        srcs += sorted(p for p in opt_in.iterdir() if p.is_file() and _looks_like_hook(p))
    for src in srcs:
        if not src.is_file():
            continue
        rel = src.relative_to(REPO_ROOT).as_posix()
        try:
            body = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            unmarked.append(rel)
            continue
        marker = next((m for m in MARKERS if m in body), None)
        if marker is None:
            unmarked.append(rel)
            continue
        targets.append((rel, src.name, marker, rel in AUTO_INSTALLED))
    return targets, unmarked


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
    targets, unmarked = discover_hooks()
    reds = 0
    for rel in unmarked:
        reds += 1
        print(f"  ✗ 킷 훅 정본에 드리프트 마커가 없다: {rel}")
        print(f"      → 첫 줄들 중 하나에 {MARKERS[0]!r} 를 넣어라 (없으면 이 훅만 감시 밖이 된다)")
    if not targets:
        # 0 건은 통과가 아니다 — 파생 경로가 깨졌다는 뜻이다 (이 레포의 false-green 정책).
        print("  ✗ 킷 훅 정본을 하나도 찾지 못했다 — 파생 경로가 깨졌다(통과가 아니다)")
        return 1
    for src_rel, name, marker, notify in targets:
        red, line = check_one(src_rel, name, marker, notify)
        reds += red
        print(line)
    return 1 if reds else 0


if __name__ == "__main__":
    sys.exit(main())
