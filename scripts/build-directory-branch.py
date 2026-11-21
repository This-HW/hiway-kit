#!/usr/bin/env python3
"""build-directory-branch.py — Claude 디렉토리가 추적할 디렉토리판 브랜치(`directory`)를 만든다.

## 왜 있는가

2026-11-06 포털이 v5.6.0 을 거부했다: *"The directory accepts command hooks only from Verified
organizations, and your organization isn't one, so this version is refused. Remove every hook of
type command, then push a new commit."* 킷의 훅은 전부 `type: command` 이다. 그래서 `main`(직접
마켓플레이스 — 훅 포함 완전판)은 그대로 두고, 디렉토리에는 별도 브랜치로 줄인 트리를 준다. 처음
(5.7.1)에는 훅 선언 파일 하나만 뺐다 — 조사용 Validate 에서 `hooks/` 를 통째로 빼도 자격증명 보류의
근거만 옮겨 갔기 때문이다(`probe-nohook-a`/`-b`, 2026-11-06).

### 2026-11-21 — 비 Verified 조직은 스크립트와 일부 frontmatter 키도 못 낸다 (5.9.1)

v5.8.0·v5.9.0 이 무훅 트리로도 거부됐다. 새 차단 두 가지(포털 설명 원문, 2026-11-22 확인):
`LOCAL_CODE_FILE_TYPE` — *"Remove each file that, whatever its name, isn't Markdown, text, JSON, YAML,
or a PNG, JPEG, GIF, WebP, or ICO image, each that starts with #!, …"*(라이선스·readme·`.gitignore`·
아이콘은 남아도 된다), `LOCAL_CODE_FRONTMATTER_KEY` — *"Remove each frontmatter key outside the allowed
list"*(허용 목록은 공개되지 않는다). 그래서 디렉토리판은 **스크립트를 통째로 뺀다**: `hooks/`(선언과 훅
스크립트), `setup/`(session-check·git 훅), `tools/`(스킬이 부르는 Python 도구), 훅만 읽는
`rules/CHECKSUMS.sha256`·`rules/VERSION`, 그리고 **도구 없이는 동작하지 않는 스킬 셋**(code-intel·
session-history·harness-export — 남기면 설치되는데 돌지 않는 약속이 된다). 에이전트 frontmatter 에서는
`isolation` 을 지운다. 조사용 Validate 실측 `[관측 n=1, 2026-11-22, probe-dir-1 @ 2e01d24]`: 이 트리는
*"Validation passed: 5 warnings"* — 차단 0·보류 0. 같은 실측에서 `model`·`effort`·`maxTurns`·`tools`·
`disallowedTools`·`disable-model-invocation` 은 통과했다(거부된 키는 `isolation` 하나).

**뺀 것에 기대는 본문은 디렉토리판에서 머리말로 알린다.** 키와 파일만 빼면 남은 본문이 거짓이 된다 —
에이전트는 "격리 worktree 에서 커밋하고 돌아온다"고, 스킬은 "`<킷 루트>/tools/…` 를 실행하라"고 계속
말한다. 격리 없이 그대로 따르면 사용자 브랜치에 커밋하고, 도구를 찾다 다른 설치(옛 캐시)의 도구를 집는다.
그래서 디렉토리판에서만(`main` 본문은 그대로 — 행동 eval 기준선 불변) 해당 문서의 frontmatter 바로
뒤에 머리말을 넣는다: 격리를 지운 에이전트와 그들을 부르는 문서에는 `ISOLATION_NOTE`, 뺀 경로를
가리키는 문서에는 `MISSING_PATHS_NOTE`.

Verified 조직이 되면(도메인 증명 진행 중) 이 축소는 필요 없다 — 그때 `EXCLUDED`·`STRIP_FRONTMATTER`
를 되돌린다.

## 무엇을 만드는가

작업 트리가 아니라 **커밋**(`--source`, 기본 `HEAD`)에서 시작한다. 그 트리에서 `EXCLUDED`(파일이나
디렉토리)를 빼고, 문서를 위처럼 바꾼 트리로 커밋을 만들어 `refs/heads/<branch>` 에 올린다. 부모는
*직전 브랜치 끝 + 원본 커밋* 이라 브랜치는 fast-forward 로만 자라고, `git log <branch>` 로 어느 `main`
커밋에서 나왔는지 추적된다. **플러그인 폴더(`plugins/common`)가 직전 끝과 같으면 새 커밋을 만들지
않는다** — 디렉토리는 추적 브랜치의 새 커밋마다 다시 스캔하고 그 커밋이 심사 중인 버전을 대체하므로,
문서만 바뀐 `main` push 가 심사 대기를 갈아엎으면 안 된다. **원본이 직전 끝의 원본보다 오래됐으면
(조상이면) 아무것도 하지 않는다** — CI 작업이 push 순서와 다르게 끝나도 옛 트리로 되돌아가지 않는다.
push 는 하지 않는다 — 호출자 몫. `--check` 도 바꾼 문서의 blob 을 객체 DB 에 쓴다(ref 는 건드리지
않는다 — 남는 것은 가비지 수집 대상 객체뿐이다).

## 검사 조건 (한 문장)

**실행할 때마다(`--check` 포함) 원본 커밋에 `EXCLUDED` 경로가 전부 있는지, frontmatter 가 정확한
`---` 줄로 열리고 닫히는지, 지울 키가 한 줄짜리 `key: 값` 으로만 있는지, 그리고 결과 트리의 플러그인
폴더에 (1) Claude 매니페스트의 훅 선언(`hooks/hooks.json` · `.claude-plugin/plugin.json` 의 `hooks` 필드 —
Codex·Cursor 매니페스트는 디렉토리가 읽지 않는다), (2) 디렉토리가 받지 않는 파일(허용 형식 밖 · 심링크·
실행 비트 · `#!` 시작 · NUL · 비 UTF-8 · 깨진 JSON · 형식과 다른 이미지 — YAML 은 구조를 풀지 않는다),
(3) 지운 키(지우는 코드와 **다른** 바이트 검색으로 본다), (4) 머리말이 있어야 하는데 없는 문서,
(5) `DEGRADES_WITHOUT_REMOVED` 밖에서 뺀 경로·스킬을 가리키는 문서가 남지 않았는지를 확인하고, 하나라도
어긋나면 exit 1.** 뺄 경로가 원본에 없으면 이름이 바뀐 것이다 — 아무것도 빼지 않은 트리를 디렉토리판이라
부르지 않는다. (2)·(5)는 **제외 방식**이다: `hooks/`·`setup/`·`tools/` **밖**의 새 스크립트는 (2)가,
그 안의 새 도구를 부르는 새 스킬·문서는 (5)가 red 로 만들어, 디렉토리판에서 뺄지(`EXCLUDED`) 머리말을 달고
남길지(`DEGRADES_WITHOUT_REMOVED`)를 사람이 정하게 한다. `hooks/`·`setup/`·`tools/` 안의 새 파일 **자체**는
통째 제외라 조용히 빠진다.

**한계 — CI 동시성.** `directory-branch` 작업은 `concurrency` 로 직렬화되지만 GitHub 는 대기 중인 작업을
새 작업으로 바꿔 친다. main 에 플러그인을 바꾸는 push 가 연달아 들어오면 대기하던 더 새 원본이 취소되고 앞
원본이 게시될 수 있고(조상 검사는 실행된 작업끼리만 본다), 되돌림 커밋이 "변경 없음"으로 건너뛴 뒤 그 앞
커밋이 게시될 수도 있다. 둘 다 다음 main push 에서 바로잡힌다 — 그 사이 디렉토리판이 한 push 뒤처진다.

사용:
  scripts/build-directory-branch.py --check              # 결과 트리 sha 만 출력(ref 를 건드리지 않음)
  scripts/build-directory-branch.py --write              # refs/heads/directory 갱신
  scripts/build-directory-branch.py --write --source origin/main
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PLUGIN_ROOT = "plugins/common"
MANIFEST = f"{PLUGIN_ROOT}/.claude-plugin/plugin.json"

#: 디렉토리 브랜치에서 빼는 레포 루트 기준 경로(파일 또는 디렉토리)와 사유.
EXCLUDED = {
    f"{PLUGIN_ROOT}/hooks": (
        "훅 선언(hooks.json)과 훅 스크립트 — 디렉토리는 command 훅과 스크립트를 Verified 조직에게만 받는다"
    ),
    f"{PLUGIN_ROOT}/setup": "session-check.py 와 git 훅(#! 셸) — 스크립트",
    f"{PLUGIN_ROOT}/tools": "스킬이 부르는 Python 도구 — 스크립트",
    f"{PLUGIN_ROOT}/rules/CHECKSUMS.sha256": "허용 형식 밖 확장자 — 훅(session-start)만 읽는다",
    f"{PLUGIN_ROOT}/rules/VERSION": "확장자 없는 파일 — 훅만 읽는다",
    f"{PLUGIN_ROOT}/skills/code-intel": "tools/code_intel.py·lsp_* 없이는 동작하지 않는 스킬",
    f"{PLUGIN_ROOT}/skills/session-history": "tools/session_history.py 없이는 동작하지 않는 스킬",
    f"{PLUGIN_ROOT}/skills/harness-export": "tools/export_harness.py 없이는 동작하지 않는 스킬",
}

#: frontmatter 에서 지울 키 — 플러그인 폴더 기준 디렉토리 → 키. 디렉토리는 허용 목록 밖 키를 Verified
#: 조직에게만 받는다(목록 비공개 — 2026-11-22 Validate 실측으로 `isolation` 만 거부).
STRIP_FRONTMATTER = {"agents": ("isolation",)}

#: 디렉토리가 받는 파일 형식(LOCAL_CODE_FILE_TYPE 설명 원문). 이름으로 남겨도 되는 것은 정확한 이름만:
#: `.gitignore`·`LICENSE`(UTF-8 텍스트이고 `#!` 로 시작하지 않을 때). 내용도 형식과 맞아야 한다 —
#: 포털은 "whatever its name" 으로 내용을 본다.
TEXT_EXTENSIONS = frozenset({".md", ".txt", ".json", ".yaml", ".yml"})
IMAGE_MAGIC = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".ico": (b"\x00\x00\x01\x00",),
}
ALLOWED_TEXT_NAMES = frozenset({".gitignore", "LICENSE"})

#: 머리말 — frontmatter 바로 뒤(없으면 맨 앞)에 넣는다. 첫 줄은 이미 넣었는지 판정하는 표지다.
ISOLATION_NOTE = (
    "> **디렉토리판 — worktree 격리 없음.** 이 설치(Anthropic 디렉토리판)에서는 파일을 고치는 에이전트"
    "(implement-code·fix-bugs·write-tests·sync-docs)가 격리 worktree 가 아니라 **사용자의 작업 트리**에서"
    " 돈다. 아래의 worktree 절차(격리 트리에서 커밋하고 돌아오기)는 적용되지 않는다 — 그 에이전트는"
    " **커밋하지 말고** 바꾼 파일과 요약만 반환하고, 커밋·병합은 호출자가 한다. 같은 트리를 함께 고치지"
    " 않도록 그 에이전트들은 **병렬이 아니라 순차로** 부른다. 격리가 필요하면 전체판(이 레포를"
    " 마켓플레이스로 설치)을 쓴다.\n"
)
MISSING_PATHS_NOTE = (
    "> **디렉토리판 — 훅·도구 없음.** 이 설치에는 킷의 `hooks/`·`setup/`·`tools/` 와 `code-intel`·"
    "`session-history`·`harness-export` 스킬이 없다. 아래에서 그 파일을 실행하거나 켜라는 단계, 그 스킬을"
    " 쓰라는 단계는 **건너뛰고**(없음으로 처리), 다른 설치나 플러그인 캐시에서 같은 이름의 파일을 찾아 쓰지"
    " 않는다 — 버전이 다른 도구다. 그 기능이 필요하면 전체판(이 레포를 마켓플레이스로 설치)을 안내한다.\n"
)

#: 뺀 경로·스킬을 가리키지만 머리말을 달고 남겨도 되는 문서(플러그인 폴더 기준). 각각 그 단계를 건너뛰어도
#: 나머지가 돈다고 확인한 것만 둔다 — 새 문서가 뺀 것을 가리키면 빌드가 멈추고 여기 넣을지 사람이 정한다.
DEGRADES_WITHOUT_REMOVED = frozenset(
    {
        "rules/agent-delegation-chain.md",
        "rules/feedback-loop.md",
        "skills/auto-dev/SKILL.md",
        "skills/child-session/SKILL.md",
        "skills/control-loop/SKILL.md",
        "skills/debug/SKILL.md",
        "skills/plan-task/references/plan-format.md",
        "skills/plan-task/references/project-discovery.md",
        "skills/plan-task/references/task-tools-fallback.md",
    }
)

#: 뺀 경로·스킬을 가리키는 본문 — `tools/x.py`·`hooks/…`·`setup/…` 처럼 경로로 쓴 것과 뺀 스킬 이름.
#: 소비자 레포의 `.git/hooks/…` 같은 것도 걸리지만(앞 글자가 `/`) 머리말이 하나 더 붙을 뿐이다 — 킷 경로가
#: `<킷 루트>/tools/…` 처럼 `/` 뒤에 오므로 그 경우를 뺄 수 없다.
_MISSING_PATH_RE = re.compile(
    r"(?<![\w.-])(?:tools|hooks|setup)/[\w.*-]"
    r"|(?<![\w-])(?:code-intel|session-history|harness-export)(?![\w-])"
)
#: 격리를 지운 에이전트를 부르는 본문.
_ISOLATED_AGENT_RE = re.compile(r"(?<![\w-])(?:implement-code|fix-bugs|write-tests|sync-docs)(?![\w-])")

DEFAULT_BRANCH = "directory"


def _git(
    repo: Path, *args: str, env: dict[str, str] | None = None, check: bool = True
) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if check and proc.returncode != 0:
        sys.exit(
            f"[directory-branch] ✗ git {' '.join(args)} 실패: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def _git_bytes(
    repo: Path, *args: str, env: dict[str, str] | None = None, data: bytes | None = None
) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=data,
        capture_output=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        sys.exit(
            f"[directory-branch] ✗ git {' '.join(args)} 실패: "
            f"{proc.stderr.decode(errors='replace').strip()}"
        )
    return proc.stdout


def _rev(repo: Path, rev: str) -> str | None:
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "rev-parse",
            "--verify",
            "--quiet",
            f"{rev}^{{commit}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def _entries(raw: bytes) -> list[tuple[str, str, str]]:
    """`ls-files -s -z`·`ls-tree -r -z` 출력 → (모드, 종류 또는 단계, sha, 경로) 중 (모드, sha, 경로).

    `-z` 라 경로의 따옴표·이스케이프가 없다(한글·공백·탭 경로도 그대로).
    """
    out = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        fields = meta.decode().split()
        if len(fields) == 3 and fields[1] in ("blob", "tree", "commit"):  # ls-tree: 모드 종류 sha
            mode, kind, sha = fields
            if kind == "commit":
                sys.exit(
                    f"[directory-branch] ✗ 서브모듈은 받지 않는다: {path.decode(errors='replace')}"
                )
        else:  # ls-files -s: 모드 sha 단계
            mode, sha, _stage = fields
        out.append((mode, sha, path.decode("utf-8", errors="surrogateescape")))
    return out


def _decode(repo: Path, sha: str, path: str) -> str:
    data = _git_bytes(repo, "cat-file", "blob", sha)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        sys.exit(f"[directory-branch] ✗ UTF-8 이 아니다 — 디렉토리는 받지 않는다: {path}")


def _frontmatter_span(text: str, path: str = "") -> tuple[int, int] | None:
    """frontmatter 블록의 (시작, 닫는 `---` 줄의 시작) 위치. 첫 줄이 `---` 로 시작하지 않으면 None.

    디렉토리 규칙("a first line of exactly ---")에 맞게 **정확한** `---` 줄만 경계로 인정한다. 첫 줄이나
    닫는 줄이 `---` 처럼 보이는데 정확하지 않으면(BOM·뒤 공백·CRLF) 변환하지 않고 exit 1 — 엄격하게만 읽고
    넘어가면 머리말이 frontmatter 위나 본문 수평선 뒤에 들어간다(5.9.1 리뷰).
    """
    if not text.lstrip("\ufeff").startswith("---"):
        return None
    if not text.startswith("---\n"):
        sys.exit(
            f"[directory-branch] ✗ {path}: frontmatter 첫 줄이 정확히 `---` 가 아니다(BOM·뒤 공백·CRLF)"
            " — 원본을 고쳐라"
        )
    pos = 4
    for line in text[4:].split("\n"):
        if line.rstrip() == "---":
            if line != "---":
                sys.exit(
                    f"[directory-branch] ✗ {path}: frontmatter 닫는 줄이 정확히 `---` 가 아니다 — 원본을 고쳐라"
                )
            return 0, pos
        pos += len(line) + 1
    sys.exit(f"[directory-branch] ✗ {path}: frontmatter 닫는 `---` 줄이 없다")


def _strip_keys(text: str, keys: tuple[str, ...], path: str = "") -> str:
    """frontmatter 의 `key: 값` 한 줄만 지운다. 블록 밖과 다른 줄은 바이트 그대로.

    지울 키가 **한 줄짜리 스칼라**가 아니면(값이 비었거나 다음 줄이 들여쓴 이어짐 — 지우면 옆 키에 값이
    붙는다, 따옴표 키, 들여쓴 키) 손으로 고치게 exit 1. 조용히 남기거나 반쯤 지우지 않는다.
    """
    span = _frontmatter_span(text, path)
    if span is None:
        return text
    start, end = span
    lines = text[start:end].split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # 느슨하게 찾고(들여쓴·따옴표 키 포함) 엄격하게 지운다 — 들여쓴 줄은 블록 값 속 글일 수도 있지만
        # YAML 을 풀지 않고는 가를 수 없다. 모호하면 지우지도 남기지도 않고 멈춘다(원본을 고치게).
        loose = re.match(r"^\s*[\"']?([\w-]+)[\"']?\s*:", line)
        if loose and loose.group(1) in keys:
            exact = re.match(r"^([\w-]+):[ \t]*(\S.*)$", line)
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if line[:1] in (" ", "\t"):
                sys.exit(
                    f"[directory-branch] ✗ {path}: 들여쓴 `{loose.group(1)}:` 줄이 있다 — 블록 값 속 글일 수"
                    " 있지만 YAML 을 풀지 않고는 가를 수 없다. 표현을 바꿔라(한 줄짜리 키가 아닌 형태)"
                )
            if not exact or exact.group(1) != loose.group(1) or nxt[:1] in (" ", "\t"):
                sys.exit(
                    f"[directory-branch] ✗ {path}: `{loose.group(1)}` 를 한 줄짜리 `키: 값` 이 아닌 형태로"
                    " 썼다 — 지우면 옆 키가 오염된다. 원본을 한 줄로 고쳐라"
                )
            i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out) + text[end:]


def _note_marker(note: str) -> str:
    return note.split("\n", 1)[0][:40]


def _with_note(text: str, note: str, path: str = "") -> str:
    """frontmatter 바로 뒤(없으면 맨 앞)에 머리말을 넣는다. 이미 있으면 그대로. 뒤에 빈 줄을 보장한다 —
    빈 줄 없이 문단이 이어지면 Markdown 이 그 문단을 인용 블록에 흡수한다."""
    if _note_marker(note) in text:
        return text
    span = _frontmatter_span(text, path)
    if span is None:
        rest = text
        return note + ("" if rest.startswith("\n") else "\n") + rest
    _start, end = span
    line_end = text.find("\n", end)  # 닫는 `---` 줄의 끝 — 파일이 그 줄로 끝나면 줄바꿈이 없다
    close = len(text) if line_end == -1 else line_end + 1
    head = text[:close] if text[:close].endswith("\n") else text[:close] + "\n"
    rest = text[close:]
    return head + "\n" + note + ("" if not rest or rest.startswith("\n") else "\n") + rest


def _transform(rel: str, text: str) -> str:
    """디렉토리판 문서 변환 — 키 지우기 + 머리말. `rel` 은 플러그인 폴더 기준 경로."""
    new = text
    for folder, keys in STRIP_FRONTMATTER.items():
        if rel.startswith(folder + "/"):
            new = _strip_keys(new, keys, rel)
    stripped_here = new != text
    if rel == "README.md":
        return new  # 플러그인 README 는 디렉토리판을 본문에서 직접 설명한다
    body = new
    if stripped_here or _ISOLATED_AGENT_RE.search(body):
        new = _with_note(new, ISOLATION_NOTE, rel)
    if _MISSING_PATH_RE.search(body):
        new = _with_note(new, MISSING_PATHS_NOTE, rel)
    return new


def derive_tree(repo: Path, source: str) -> str:
    """원본 커밋 트리에서 EXCLUDED 를 빼고 문서를 디렉토리판으로 바꾼 트리 sha.

    임시 인덱스만 쓴다(작업 트리·인덱스 무변경). 바뀐 내용은 `hash-object -w` 로 객체만 만든다.
    """
    missing = [
        path
        for path in EXCLUDED
        if subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"{source}:{path}"],
            capture_output=True,
            check=False,
        ).returncode
        != 0
    ]
    if missing:
        sys.exit(
            "[directory-branch] ✗ 원본에 뺄 경로가 없다 — 이름이 바뀌었으면 EXCLUDED 를 고쳐라: "
            + ", ".join(missing)
        )
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        _git(repo, "read-tree", source, env=env)
        # `git rm` 이 아니라 update-index — 임시 인덱스만 고치므로 HEAD·작업 트리 기준 안전검사는 필요
        # 없고, `--source` 가 HEAD 와 다르면 그 검사가 엉뚱하게 실패한다(5.9.1 리뷰).
        paths = _git_bytes(repo, "ls-files", "-z", "--", *EXCLUDED, env=env)
        _git_bytes(repo, "update-index", "--force-remove", "-z", "--stdin", env=env, data=paths)
        for mode, sha, path in _entries(
            _git_bytes(repo, "ls-files", "-s", "-z", "--", PLUGIN_ROOT, env=env)
        ):
            if not path.endswith(".md"):
                continue
            rel = path[len(PLUGIN_ROOT) + 1 :]
            text = _decode(repo, sha, path)
            new = _transform(rel, text)
            if new != text:
                new_sha = _git_bytes(
                    repo, "hash-object", "-w", "--stdin", data=new.encode("utf-8")
                ).decode().strip()
                _git(repo, "update-index", "--cacheinfo", f"{mode},{new_sha},{path}", env=env)
        tree = _git(repo, "write-tree", env=env)
    _assert_directory_safe(repo, tree)
    return tree


def _content_ok(name: str, ext: str, data: bytes) -> bool:
    """디렉토리가 그 형식으로 받을 내용인가 — `#!` 시작(BOM 뒤 포함)·NUL·비 UTF-8·깨진 JSON·잘못된 이미지는 아니다."""
    if ext in IMAGE_MAGIC:
        return data.startswith(IMAGE_MAGIC[ext])
    if ext == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if ext not in TEXT_EXTENSIONS and name not in ALLOWED_TEXT_NAMES:
        return False
    body = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    if body.startswith(b"#!") or b"\0" in data:
        return False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if ext == ".json":
        try:
            json.loads(text)
        except ValueError:
            return False
    return True


def _assert_directory_safe(repo: Path, tree: str) -> None:
    """결과 트리의 플러그인 폴더에 훅 선언·받지 않는 파일·지운 키·머리말 없는 참조가 남았으면 exit 1."""
    bad: list[str] = []
    leftover_keys: list[str] = []
    unnoted: list[str] = []
    unlisted: list[str] = []
    for mode, sha, path in _entries(
        _git_bytes(repo, "ls-tree", "-r", "-z", tree, "--", PLUGIN_ROOT)
    ):
        rel = path[len(PLUGIN_ROOT) + 1 :]
        if rel == "hooks/hooks.json":
            sys.exit("[directory-branch] ✗ 결과 트리에 hooks/hooks.json 이 남았다")
        name = rel.rsplit("/", 1)[-1]
        ext = os.path.splitext(name)[1].lower()
        data = _git_bytes(repo, "cat-file", "blob", sha)
        if mode != "100644" or not _content_ok(name, ext, data):  # 심링크(120000)·실행 비트(100755)도
            bad.append(rel)
            continue
        if ext != ".md":
            continue
        text = data.decode("utf-8")
        # 지운 키 검사는 지우는 코드와 **다른 방법**으로 — 파일 앞쪽 frontmatter 후보 구간 전체를 느슨한
        # 바이트 패턴으로 훑는다(BOM·뒤 공백·따옴표 키·들여쓴 키 모두 걸린다). 같은 파서로 확인하면 동어반복이다.
        head = text.lstrip("\ufeff")
        if head.lstrip().startswith("---"):
            closing = re.search(r"\n\s*---\s*(\n|$)", head[3:])
            block = head[: 3 + closing.start()] if closing else head
            for folder, keys in STRIP_FRONTMATTER.items():
                if rel.startswith(folder + "/"):
                    for key in keys:
                        if re.search(rf"(?m)^\s*[\"']?{re.escape(key)}[\"']?\s*:", block):
                            leftover_keys.append(f"{rel}: {key}")
        if rel == "README.md":
            continue  # 플러그인 README 는 디렉토리판을 본문에서 직접 설명한다
        if _MISSING_PATH_RE.search(text):
            if rel not in DEGRADES_WITHOUT_REMOVED:
                unlisted.append(rel)
            elif _note_marker(MISSING_PATHS_NOTE) not in text:
                unnoted.append(rel)
        if _ISOLATED_AGENT_RE.search(text) and _note_marker(ISOLATION_NOTE) not in text:
            unnoted.append(rel)
    if bad:
        sys.exit(
            "[directory-branch] ✗ 디렉토리가 받지 않는 파일이 남았다(허용 형식 밖 · 내용이 형식과 다름 ·"
            " #! 로 시작) — EXCLUDED 에 넣을지, 그 스킬이 디렉토리판에서 도는지 정하라: "
            + ", ".join(sorted(bad))
        )
    if leftover_keys:
        sys.exit("[directory-branch] ✗ 지운 frontmatter 키가 남았다: " + "; ".join(leftover_keys))
    if unlisted:
        sys.exit(
            "[directory-branch] ✗ 뺀 경로·스킬을 가리키는 새 문서 — 디렉토리판에서 뺄지(EXCLUDED), 그 단계를"
            " 건너뛰어도 도는지 확인하고 DEGRADES_WITHOUT_REMOVED 에 넣을지 정하라: " + ", ".join(sorted(unlisted))
        )
    if unnoted:
        sys.exit(
            "[directory-branch] ✗ 머리말이 있어야 하는데 없는 문서: " + ", ".join(sorted(set(unnoted)))
        )
    raw = _git(repo, "cat-file", "-p", f"{tree}:{MANIFEST}")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"[directory-branch] ✗ {MANIFEST} 를 JSON 으로 읽지 못했다: {exc}")
    if "hooks" in manifest:
        sys.exit(
            f"[directory-branch] ✗ {MANIFEST} 에 hooks 필드가 있다 — 선언이 남는다"
        )


def _is_ancestor(repo: Path, older: str, newer: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", older, newer],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def write_branch(repo: Path, source: str, tree: str, branch: str) -> str:
    ref = f"refs/heads/{branch}"
    prev = _rev(repo, ref)
    if prev:
        parents = _git(repo, "rev-list", "--parents", "-n1", prev).split()[1:]
        prev_source = parents[-1] if parents else None
        # 원본이 직전 끝의 원본보다 오래됐으면(조상) 되돌리지 않는다 — CI 작업이 push 순서와 다르게
        # 끝나도 디렉토리가 옛 트리로 돌아가지 않게(5.9.1 리뷰).
        if prev_source and prev_source != source and _is_ancestor(repo, source, prev_source):
            print(
                f"[directory-branch] ✓ {branch} 원본 {source[:7]} 은 직전 원본 {prev_source[:7]} 의 조상 — 건너뜀"
            )
            return prev
    # 플러그인 폴더가 같으면 새 커밋을 만들지 않는다 — 디렉토리는 추적 브랜치의 커밋마다 새 버전으로
    # 스캔하고, 새 커밋은 심사 중인 버전을 대체한다. 문서만 바뀐 main push 로 심사 대기를 갈아엎지 않는다.
    if prev and _git(repo, "rev-parse", f"{prev}:{PLUGIN_ROOT}") == _git(
        repo, "rev-parse", f"{tree}:{PLUGIN_ROOT}"
    ):
        print(f"[directory-branch] ✓ {branch} 플러그인 폴더 변경 없음 ({prev[:7]})")
        return prev
    version = json.loads(_git(repo, "cat-file", "-p", f"{source}:{MANIFEST}")).get(
        "version", "?"
    )
    parents_args = ["-p", prev] if prev else []
    message = (
        f"directory: v{version} from {source[:7]}\n\n"
        f"Claude 디렉토리판 — 스크립트·훅·도구 의존 스킬 {len(EXCLUDED)}개 경로 제외, "
        f"frontmatter {', '.join(k for ks in STRIP_FRONTMATTER.values() for k in ks)} 제거, "
        "뺀 것에 기대는 문서에 머리말 (scripts/build-directory-branch.py)."
    )
    commit = _git(repo, "commit-tree", tree, *parents_args, "-p", source, "-m", message)
    _git(repo, "update-ref", ref, commit, *([prev] if prev else ["0" * 40]))
    print(
        f"[directory-branch] ✓ {branch} → {commit[:7]} (v{version}, 원본 {source[:7]})"
    )
    return commit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="결과 트리만 계산·검사")
    mode.add_argument("--write", action="store_true", help="refs/heads/<branch> 갱신")
    parser.add_argument("--source", default="HEAD", help="원본 커밋 (기본 HEAD)")
    parser.add_argument(
        "--branch", default=DEFAULT_BRANCH, help=f"대상 브랜치 (기본 {DEFAULT_BRANCH})"
    )
    parser.add_argument("--repo", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    source = _rev(args.repo, args.source)
    if source is None:
        sys.exit(f"[directory-branch] ✗ 원본 커밋을 찾지 못했다: {args.source}")
    tree = derive_tree(args.repo, source)
    if args.check:
        print(
            f"[directory-branch] ✓ 디렉토리판 트리 {tree[:12]} (원본 {source[:7]}, 제외 {len(EXCLUDED)}개)"
        )
        return 0
    write_branch(args.repo, source, tree, args.branch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
