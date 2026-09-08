#!/usr/bin/env python3
"""
opt-in 예시 훅 (PreToolUse) — 검증과 상태 변경을 한 Bash 호출에 잇는 것을 차단한다.

**이 파일은 `hooks.json` 에 등록돼 있지 않다.** 설치 방법·한계는 `examples/README.md`.

무엇을 막는가
--------------
`pytest ... ; git push` 처럼 **검증 뒤에 상태 변경을 무조건 실행**하는 한 줄.
에이전트가 검증 출력을 읽는 시점엔 이미 푸시·머지가 끝나 있다.

    출력은 읽어야 게이트가 된다. 읽기 전에 다음 명령이 실행되면 그건 게이트가
    아니라 로그다.

근거 (실측 n=2, 서로 독립, 같은 날 다른 두 세션):

1. PR 상태 4축 검증이 `FAILURE`/`UNSTABLE` 을 **출력했는데**, 같은 Bash 블록 다음
   줄의 `gh pr merge` 가 조건 없이 실행돼 CI 실패 상태로 main 머지
2. `pytest`/`ruff` 뒤에 `commit`·`push` 를 `;` 로 체인 — 린트 오류가 main 에 올라감

두 종류의 검증을 구분한다 (이 구분이 이 훅의 핵심이다)
------------------------------------------------------
* **종료코드 검증** (`pytest`·`ruff`·`verify-done.sh` 등) — 판정이 exit code 에 있다.
  `&&` 로 이으면 **진짜 게이트**이므로 통과시킨다. `;`·개행·`&` 로 이으면 차단한다.
* **출력 검증** (`gh pr view`·`gh pr checks`·`gh run list` 등) — 판정이 **stdout 에**
  있고 종료코드는 "조회에 성공했다"만 뜻한다. CI 가 빨간데도 exit 0 이다. 그래서
  `&&` 도 게이트가 아니다 — **구분자와 무관하게 차단**한다.
  (`git status`·`git diff`·`git log` 는 CI 판정을 담지 않는 단순 조회라 목록에 없다.)

이 훅이 하지 않는 것
--------------------
"직전 턴에 CI 결과를 읽었는가"는 판정하지 않는다 — 훅은 한 번의 도구 호출만 본다.
판정할 수 없는 것을 판정한다고 주장하지 않는다(`docs/conventions/warning-signal.md`).
막는 것은 정확히 하나: **한 호출 안에서 검증 뒤에 상태 변경이 오는 형태.**

완전한 셸 파서가 아니다 — `child-git-guard.py` 와 같은 이유·같은 한계다(D-15: 구현은
여러 벌, 계약만 하나). 난독화 우회 방지가 아니라 사람·에이전트가 실제로 타이핑하는
흔한 형태를 잡는 것이 목적이다.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

# 종료코드가 판정인 검증 — `&&` 로 이으면 진짜 게이트다.
EXIT_CODE_VERIFIERS = (
    ("pytest",),
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("ruff",),
    ("mypy",),
    ("eslint",),
    ("tsc",),
    ("shellcheck",),
    ("cargo", "test"),
    ("go", "test"),
    ("npm", "test"),
    ("pnpm", "test"),
    ("yarn", "test"),
    ("make", "test"),
)
# 파일명으로 알아보는 종료코드 검증 (프로젝트마다 이름이 다르다).
#
# **한계**: 이름이 verify/check/validate/lint/test 로 시작하지 않는 검증기(예: `audit_*`)는
# 여기 걸리지 않는다. 그런 스크립트를 쓰면 아래 EXIT_CODE_VERIFIERS 에 직접 추가하라 —
# 인터프리터 경유(`python scripts/audit_x.py`)까지 잡으려면 2토큰 패턴으로 넣어야 한다.
# 판별 기준은 **위반 시 비-0 으로 종료하는가**다: 그렇다면 종료코드 검증, 후보만 출력하고
# 항상 0 이면 **출력 검증**(OUTPUT_VERIFIERS)이다.
EXIT_CODE_VERIFIER_RE = re.compile(
    r"(verify|check|validate|lint|test)[\w.-]*\.(sh|py)$"
)

# 판정이 stdout 에 있는 검증 — 종료코드는 "조회 성공"만 뜻하므로 `&&` 도 게이트가 아니다.
OUTPUT_VERIFIERS = (
    ("gh", "pr", "view"),
    ("gh", "pr", "checks"),
    ("gh", "pr", "status"),
    ("gh", "run", "view"),
    ("gh", "run", "list"),
    ("gh", "api"),
)
# `git status`·`git diff`·`git log` 는 **일부러 뺐다.** CI 판정을 담지 않는 단순 조회이고,
# `git status && git push` 는 흔하고 무해한 관용구다. 그것까지 막으면 이 훅이 상시
# 발동해 죽는다 — 상시 참인 경고는 옆의 진짜 경고까지 죽인다
# (`docs/conventions/warning-signal.md`).

# 되돌리기 어렵거나 외부에 효과를 내는 상태 변경.
MUTATIONS = (
    ("git", "push"),
    ("git", "merge"),
    ("gh", "pr", "merge"),
    ("gh", "release", "create"),
    ("gh", "workflow", "run"),
    ("npm", "publish"),
    ("pnpm", "publish"),
    ("yarn", "publish"),
    ("cargo", "publish"),
    ("twine", "upload"),
    ("docker", "push"),
    ("kubectl", "apply"),
    ("terraform", "apply"),
)

# 검증 스크립트를 대신 실행하는 인터프리터 — `python scripts/verify.py` 처럼 앞에 붙으면
# 이름 규칙(EXIT_CODE_VERIFIER_RE)이 두 번째 토큰에 걸려야 한다.
_INTERPRETERS = (
    "bash",
    "sh",
    "zsh",
    "python",
    "python3",
    "node",
    "ruby",
    "uv",
    "poetry",
)
# 이들은 `<도구> run <스크립트>` 형태라 스크립트가 한 칸 더 뒤에 있다.
_RUN_WRAPPERS = ("uv", "poetry")

# 무조건 이어짐 — 앞 명령의 결과와 무관하게 다음이 실행된다.
UNCONDITIONAL = {";", "&", "\n"}


def _split_with_separators(command: str) -> list[tuple[str, list[str]]]:
    """`(앞 구분자, 토큰들)` 목록으로 분리한다. 첫 세그먼트의 구분자는 ""."""
    parts: list[tuple[str, str]] = []
    buf: list[str] = []
    sep = ""
    i = 0
    quote: str | None = None
    depth = 0
    while i < len(command):
        ch = command[i]
        if quote:
            buf.append(ch)
            if ch == quote and (i == 0 or command[i - 1] != "\\"):
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if depth == 0:
            two = command[i : i + 2]
            if two in ("&&", "||"):
                parts.append((sep, "".join(buf)))
                sep = two
                buf = []
                i += 2
                continue
            if ch in (";", "\n", "|", "&"):
                parts.append((sep, "".join(buf)))
                # `|` 는 파이프 — 다음 명령이 앞의 **출력**을 받는 것이지 게이트가
                # 아니다. 무조건 실행되므로 무조건 구분자로 취급한다.
                sep = "\n" if ch == "|" else ch
                buf = []
                i += 1
                continue
        buf.append(ch)
        i += 1
    parts.append((sep, "".join(buf)))

    out: list[tuple[str, list[str]]] = []
    for s, raw in parts:
        try:
            tokens = shlex.split(raw)
        except ValueError:
            continue  # 따옴표 불일치 등 — 이 세그먼트는 건너뛴다
        if tokens:
            out.append((s, tokens))
    return out


def _strip_prefixes(tokens: list[str]) -> list[str]:
    """`env A=1`·`sudo`·`VAR=x` 같은 선행 토큰을 걷어낸다."""
    out = list(tokens)
    while out:
        head = out[0]
        if head in ("sudo", "env", "time", "nohup", "command"):
            out = out[1:]
            continue
        if "=" in head and not head.startswith("-") and "/" not in head.split("=")[0]:
            out = out[1:]
            continue
        break
    return out


def _matches(tokens: list[str], patterns: tuple[tuple[str, ...], ...]) -> bool:
    toks = _strip_prefixes(tokens)
    if not toks:
        return False
    name = toks[0].rsplit("/", 1)[-1]
    head = [name, *toks[1:]]
    for pat in patterns:
        if len(head) >= len(pat) and all(head[i] == pat[i] for i in range(len(pat))):
            return True
    return False


def classify(tokens: list[str]) -> str | None:
    """'exit' | 'output' | 'mutate' | None."""
    if _matches(tokens, MUTATIONS):
        return "mutate"
    if _matches(tokens, OUTPUT_VERIFIERS):
        return "output"
    if _matches(tokens, EXIT_CODE_VERIFIERS):
        return "exit"
    toks = _strip_prefixes(tokens)
    if toks and EXIT_CODE_VERIFIER_RE.search(toks[0].rsplit("/", 1)[-1]):
        return "exit"
    # 인터프리터 경유 형태: `python scripts/x.py` 는 toks[0] 이 "python" 이라 이름
    # 규칙이 걸리지 않는다. 직접 실행(`./scripts/x.py`)은 위 한 줄로 잡히지만 인터프리터를
    # 앞에 붙이면 안 잡힌다 — 외부 도입 세션이 실측으로 짚은 함정이다.
    if toks and toks[0] in _INTERPRETERS:
        rest = toks[1:]
        # `uv run x.py`·`poetry run x.py` 는 스크립트가 한 칸 더 뒤다.
        if rest and rest[0] == "run" and toks[0] in _RUN_WRAPPERS:
            rest = rest[1:]
        if rest and EXIT_CODE_VERIFIER_RE.search(rest[0].rsplit("/", 1)[-1]):
            return "exit"
    return None


def check_command(command: str) -> str | None:
    segments = _split_with_separators(command)
    kinds = [(sep, classify(tokens), tokens) for sep, tokens in segments]

    for m_idx, (_, kind, tokens) in enumerate(kinds):
        if kind != "mutate":
            continue
        for v_idx in range(m_idx - 1, -1, -1):
            v_kind = kinds[v_idx][1]
            if v_kind not in ("exit", "output"):
                continue
            # v_idx → m_idx 사이의 구분자를 전부 본다.
            seps = [kinds[k][0] for k in range(v_idx + 1, m_idx + 1)]
            unconditional = any(s in UNCONDITIONAL for s in seps)
            verifier = " ".join(kinds[v_idx][2][:3])
            mutation = " ".join(tokens[:3])
            if v_kind == "output":
                return (
                    f"`{verifier}` 의 판정은 **출력에** 있고 종료코드는 '조회 성공'만 "
                    f"뜻합니다 — CI 가 빨개도 exit 0 입니다. 그런데 같은 호출에서 "
                    f"`{mutation}` 이 뒤따릅니다. 출력을 읽는 시점엔 이미 실행된 뒤이므로 "
                    f"게이트가 아니라 로그입니다.\n"
                    f"→ 검증 호출과 상태 변경 호출을 **다른 도구 호출로 나누세요.** "
                    f"사이에 출력을 읽는 턴이 반드시 들어가야 합니다."
                )
            if unconditional:
                return (
                    f"`{verifier}` 의 결과와 **무관하게** `{mutation}` 이 실행됩니다 "
                    f"(구분자가 `&&` 가 아님). 검증 출력을 읽는 시점엔 이미 끝나 있습니다.\n"
                    f"→ 다른 도구 호출로 나누거나, 최소한 `&&` 로 이어 종료코드가 "
                    f"게이트가 되게 하세요."
                )
            break  # `&&` 로만 이어진 종료코드 검증 — 진짜 게이트다. 통과.
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
            print(
                f"🔒 차단됨(verify-mutate-split 예시 훅): {reason}",
                file=sys.stderr,
            )
            sys.exit(2)
        sys.exit(0)
    except json.JSONDecodeError:
        sys.exit(0)  # fail-open
    except Exception as e:  # fail-open — 예시 훅의 오류가 작업을 막으면 안 됨
        print(f"[verify-mutate-split] warning: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
