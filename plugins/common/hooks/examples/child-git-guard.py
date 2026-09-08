#!/usr/bin/env python3
"""
opt-in 예시 훅 (PreToolUse) — 다중 세션 개발에서 위험한 git 명령을 차단한다 (D-36).

**이 파일은 `hooks.json` 에 등록돼 있지 않다.** 킷의 훅은 설치 즉시 모든 소비자에게
활성이므로, 정당한 자식 세션(`git push`가 실제로 필요한 사용)에서 이 훅이 발동하면
소비자 환경을 깨뜨린다(북극성 위반). 프로젝트가 직접 켜는 opt-in 경로로만 존재한다.
설치 방법·한계는 `examples/README.md` 참고.

차단 대상:
  1. bare `git stash` (인자 없이 저장) · `git stash pop` — 워크트리 간 공유 스택 오염(CLAUDE.md
     "git stash 스택은 다른 워크트리와 공유" 규율과 동일 근거)
  2. `git reset --hard` — 커밋되지 않은 작업 파괴
  3. `git clean -fd` 류(force+directory 조합) — 추적 안 된 파일 파괴
  4. `git push` — **자식 세션에서만** 차단(주 체크아웃·부모 세션은 통과)

자식 판별은 워크트리 로컬 마커(`$(git rev-parse --git-dir)/cck/child.json`)로 한다.
`CLAUDE_CODE_CHILD_SESSION` 은 쓰지 않는다 — 부모·자식·서브에이전트 전부 `1`이라
역할 판별 신호가 아님이 실측됐다(설계 §13.5). 마커가 없으면(스킬 미로드) 이 훅은
git push 를 막지 않는다 — **fail-open**이며, 없는 보호를 있다고 믿게 하지 않는다.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys

MARKER_REL = ("cck", "child.json")


def _git(args: list[str]) -> str | None:
    try:
        r = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=5, check=False
        )
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def is_child_session() -> bool:
    """워크트리 로컬 마커 + 주 체크아웃 예외로 자식 여부를 판별한다.

    `--git-common-dir`은 주 체크아웃에서 상대경로(`.git`), 워크트리에서 절대경로를
    반환한다(설계 §14.7 구현 함정) — 문자열 비교 전에 반드시 resolve한다.
    """
    git_dir = _git(["rev-parse", "--git-dir"])
    common_dir = _git(["rev-parse", "--git-common-dir"])
    if git_dir is None or common_dir is None:
        return False  # git 리포지토리가 아니면 자식일 수 없다 — fail-open

    from pathlib import Path

    if Path(git_dir).resolve() == Path(common_dir).resolve():
        return False  # 주 체크아웃은 마커가 있어도 자식이 아니다(§13.6)

    marker = Path(git_dir).joinpath(*MARKER_REL)
    if not marker.is_file():
        return False  # 마커 없음 = 자식 스킬 미로드 = 보호 대상 아님(fail-open)

    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return False  # 손상된 마커는 없는 것과 동일하게 취급(fail-open)

    # 스키마 검증 — `rules/child-marker.md` 가 키 이름을 고정한다.
    # 검증 없이 "파일이 있으면 자식"으로 두면, 쓰는 쪽이 키를 다르게 써도 통과한다.
    # 실측: 두 세션이 각각 `base_commit`·`baseline_commit` 을 썼다. 키가 갈리면
    # 마커의 내용을 쓰는 순간(기준 커밋 대조 등) 오판이 된다.
    if not isinstance(data, dict) or data.get("schema") != 1:
        return False  # 모르는 스키마 버전 = 판정 불가 = 보호하지 않는다(fail-open)
    if not all(
        isinstance(data.get(k), str) and data[k]
        for k in ("parent", "role", "base_commit")
    ):
        return False

    # 낡은 마커 경고 — 값을 대조하지 않으면 치환 규율이 집행되지 않는다.
    # 차단하지 않는 이유: 자식이 정당하게 기준보다 앞선 커밋 위에 있을 수 있다(작업 커밋).
    # 목적은 "브리프가 바뀌었는데 마커를 안 갈았는가" 를 사람이 보게 하는 것이다.
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        ).stdout.strip()
        base = data["base_commit"]
        if head and base and not head.startswith(base) and not base.startswith(head):
            merge_base = subprocess.run(
                ["git", "merge-base", "--is-ancestor", base, head],
                capture_output=True, timeout=5, check=False,
            ).returncode
            if merge_base != 0:
                print(
                    f"[cck] 경고: 마커의 base_commit({base[:8]})이 현재 HEAD({head[:8]})의 "
                    "조상이 아니다 — 브리프 교체 시 마커를 치환하지 않았을 수 있다 "
                    "(rules/child-marker.md)",
                    file=sys.stderr,
                )
    except (OSError, subprocess.TimeoutExpired, KeyError):
        pass  # 판정 불가는 침묵 — 오탐 경고는 전체 경고를 죽인다

    return True


def _split_commands(command: str) -> list[list[str]]:
    """`&&`·`;`·`|`로 이어진 셸 명령을 토큰 리스트들로 분리한다.

    완전한 셸 파서가 아니다 — 이 예시가 잡으려는 것은 사람·에이전트가 그대로
    타이핑하는 흔한 형태이지, 난독화를 뚫는 것이 아니다(opt-in 예시의 목적).
    """
    segments: list[list[str]] = []
    for raw in _shell_split_top_level(command):
        try:
            tokens = shlex.split(raw)
        except ValueError:
            continue  # 따옴표가 안 맞는 등 파싱 불가 — 이 세그먼트는 건너뛴다
        if tokens:
            segments.append(tokens)
    return segments


def _shell_split_top_level(command: str) -> list[str]:
    """따옴표 밖에서만 `&&`·`||`·`;`·`|`로 분리(순수 문자열 스캔, 완전한 셸 파서 아님)."""
    parts: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    n = len(command)
    while i < n:
        c = command[i]
        if quote:
            buf.append(c)
            if c == quote:
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            buf.append(c)
            i += 1
            continue
        if command[i : i + 2] in ("&&", "||"):
            parts.append("".join(buf))
            buf = []
            i += 2
            continue
        if c in (";", "|"):
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    parts.append("".join(buf))
    return parts


def _find_git_subcommand(tokens: list[str]) -> tuple[str | None, list[str]]:
    """토큰 리스트에서 `git <subcommand> <나머지>`를 찾는다. git 호출이 아니면 (None, [])."""
    try:
        idx = tokens.index("git")
    except ValueError:
        return None, []
    rest = tokens[idx + 1 :]
    if not rest:
        return None, []
    return rest[0], rest[1:]


def _is_bare_stash_or_pop(sub: str, rest: list[str]) -> bool:
    if sub != "stash":
        return False
    if not rest:
        return True  # `git stash` — 인자 없는 암묵적 저장
    return rest[0] == "pop"


def _is_reset_hard(sub: str, rest: list[str]) -> bool:
    return sub == "reset" and "--hard" in rest


def _is_clean_force_dir(sub: str, rest: list[str]) -> bool:
    if sub != "clean":
        return False
    has_force = False
    has_dir = False
    for tok in rest:
        if tok in ("--force", "-f") or (
            tok.startswith("-") and not tok.startswith("--") and "f" in tok[1:]
        ):
            has_force = True
        if tok in ("--directory", "-d") or (
            tok.startswith("-") and not tok.startswith("--") and "d" in tok[1:]
        ):
            has_dir = True
    return has_force and has_dir


def _is_push(sub: str) -> bool:
    return sub == "push"


def check_command(command: str) -> str | None:
    """차단해야 하면 이유 문자열, 통과면 None."""
    child = None  # lazy — push 검사에서만 필요
    for tokens in _split_commands(command):
        sub, rest = _find_git_subcommand(tokens)
        if sub is None:
            continue
        if _is_bare_stash_or_pop(sub, rest):
            return (
                "bare `git stash`/`git stash pop`은 차단됩니다 — stash 스택은 다른 "
                '워크트리와 공유됩니다. `git stash push -u -m "<tag>"`로 저장하고 '
                "`git stash apply <sha>`로 복원하세요(pop 아님)."
            )
        if _is_reset_hard(sub, rest):
            return (
                "`git reset --hard`는 차단됩니다 — 커밋되지 않은 변경을 되돌릴 수 "
                "없이 파괴합니다. 임시 커밋 또는 `git stash push`를 먼저 검토하세요."
            )
        if _is_clean_force_dir(sub, rest):
            return (
                "`git clean` force+directory 조합은 차단됩니다 — 추적 안 된 파일을 "
                "되돌릴 수 없이 삭제합니다. `git clean -n`(dry-run)으로 먼저 확인하세요."
            )
        if _is_push(sub):
            if child is None:
                child = is_child_session()
            if child:
                return (
                    "이 세션은 자식 세션 마커(cck/child.json)를 갖고 있어 `git push`가 "
                    "차단됩니다 — main 병합·푸시는 부모(컨트롤) 세션의 몫입니다."
                )
    return None


def main() -> None:
    try:
        if sys.stdin.isatty():
            sys.exit(0)
        input_data = json.load(sys.stdin)
        if input_data.get("tool_name") != "Bash":
            sys.exit(0)
        command = input_data.get("tool_input", {}).get("command", "")
        if not command:
            sys.exit(0)
        reason = check_command(command)
        if reason:
            print(f"🔒 차단됨(child-git-guard 예시 훅): {reason}", file=sys.stderr)
            sys.exit(2)
        sys.exit(0)
    except json.JSONDecodeError:
        sys.exit(0)  # fail-open
    except Exception as e:  # fail-open — 예시 훅의 오류가 작업을 막으면 안 됨
        print(f"[child-git-guard] warning: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
