#!/usr/bin/env python3
"""check_doc_refs.py — 살아있는 문서가 가리키는 파일·함수가 **실제로 있는가**.

`verify-done.sh §27` 과 CI 가 **같은 스크립트**를 호출한다(F-023).

## 검사 조건 (한 문장)

**`git ls-files '*.md'` 에서 제외(아래)를 뺀 모든 문서의 링크·`@import`·백틱 경로·백틱
파일명·백틱 함수명이, 추적 파일 트리(와 추적 `.py`/`.sh` 의 정의)에서 찾아지지 않으면
fail.** 분기가 없다 — 항상 돈다(`docs/conventions/warning-signal.md` §검토 절차 4).

## 왜 있는가

`verify-done.sh` 가 33/0 green 인 상태에서 P0 급 사실 오류가 9건 나왔다(감사
`docs/specs/2026-10-05-audit-remediation/audit/B-docs.md`). 전부 **문서가 가리키는 대상이
이미 사라진 것**이었다 — 4.0.0 에서 지운 `db-tunnel.sh`, 5.2.0 에서 옮긴 `hooks/checklist.py`,
5.3.0 에서 평탄화한 `agents/<분류>/`. 게이트가 문서의 참조 실재성을 보지 않았다.

## 무엇을 보는가 — 다섯 종류

| 종류 | 예 | 존재 판정 |
| --- | --- | --- |
| 마크다운 링크 | `[t](../x.md)` | 문서 디렉토리 기준(`/` 시작이면 레포 루트). `#frag`·`?q` 제거, URL 제외 |
| `@import` | 줄 머리 `@docs/x.md` | 문서 디렉토리 → 레포 루트 순 |
| 슬래시 든 백틱 경로 | `` `scripts/x.py` `` | 아래 **기준점** 중 하나에서 |
| 백틱 파일명 | `` `verify-done.sh` `` | 추적 파일 어디서든 basename 일치 |
| 백틱 함수명 | `` `snake_case()` `` · `` `def f` `` | 추적 `.py`/`.sh` 의 정의(`def`·`class`·`name()`) |

경로 기준점: 레포 루트 · 문서 디렉토리 · `plugins/common/`(스킬이 *"경로는 플러그인 루트 기준"*
으로 적는다) · 문서가 속한 스킬 디렉토리. 넷 중 어느 하나에서라도 있으면 실재한다 —
거짓 red(상시 참인 경고는 죽는다)보다 낫기 때문이다.

## 제외 — 대상이 아니라 **제외를 나열한다** (`warning-signal.md` §검토 절차 5)

새 문서는 기본으로 검사 대상이다. 빠지는 것은 정당화된 아래뿐이다.

- **지위** — frontmatter `status: historical | superseded` 인 문서(`docs/conventions/` 문서 지위 스키마,
  스펙 D0-2). 시점 고정 기록은 *그때의* 경로를 쓰는 것이 정확하다.
- **`CHANGELOG.md`·`docs/CHANGELOG-archive.md`** — 옛 경로가 사실로서 적힌다.
- **`evals/scenarios/`** — 의도적으로 틀린 코드를 담은 픽스처다.
- **펜스 코드블록** — 예시·출력·트리 그림이다. 실재를 주장하지 않는다.
- **자리표시자·소비자 쪽 경로** — `<…>` `{…}` `*` `$` `~` `…`, `.claude/`·`.git/`, 절대경로,
  `docs/plans/`(소비자 프로젝트 규약), URL.
- **줄 단위** — 그 줄에 `doc-ref-ok` 가 있으면 건너뛴다(구 이름 게이트의 `old-name-ok` 와 같은 관례).
- **(파일, 참조) 쌍** — `ALLOWED_REFS` 에 이유와 함께. 파일 통째 제외는 그 파일의 *미래* 결함까지
  가리므로 쓰지 않는다.

## 못 읽은 파일은 집계한다

`git_tracked.SkipTally` — 읽기 실패는 red(사각지대), 비-UTF-8 은 문서가 아니므로 노랑.

## red 메시지

고치는 법을 한 줄로 적는다(`C-M3`) — 가리키는 문서를 고치거나, 옮긴 대상이면 새 경로로 바꾼다.
시점 고정 기록이면 `status: historical` 을 단다.
"""

from __future__ import annotations

import builtins
import re
import subprocess
import sys
from pathlib import Path

from git_tracked import SkipTally, tracked_files

REPO_ROOT = Path(__file__).resolve().parent.parent
LABEL = "check-doc-refs"
LINE_OPT_OUT = "doc-ref-ok"
SKILLS_PREFIX = "plugins/common/skills/"
PLUGIN_ROOT_REL = "plugins/common/"

#: 파일 통째 제외 — 정당화된 것만(위 독스트링 참조).
EXCLUDE_FILES = frozenset({"CHANGELOG.md", "docs/CHANGELOG-archive.md"})
EXCLUDE_PREFIXES = ("evals/scenarios/",)
#: 지위 때문에 빠지는 값(스펙 D0-2). 문서 지위 스키마의 SSOT 는 check_doc_status.py.
SKIPPED_STATUSES = frozenset({"historical", "superseded"})

#: (문서, 참조 문자열) 쌍 예외. 값은 **이유** — 이유 없는 예외는 두지 않는다.
ALLOWED_REFS: dict[tuple[str, str], str] = {
    (
        ".claude/skills/eval-forge/SKILL.md",
        "conftest.py",
    ): "소비자 pytest 관례 파일명 예시",
    ("evals/README.md", "conftest.py"): "소비자 pytest 관례 파일명 예시",
    (
        "docs/native-absorption.md",
        "run_model.py",
    ): "외부 프로젝트(Xastra)의 파일을 인용한 것",
    (
        "README.md",
        "gitdir/kit/child.json",
    ): "`$(git rev-parse --git-dir)/kit/child.json` 의 약식 표기",
    (
        "plugins/common/hooks/examples/README.md",
        "kit/child.json",
    ): "git-dir 안 마커 경로의 약식 표기",
    (
        "plugins/common/agents/sync-docs.md",
        "docs/api/users.md",
    ): "소비자 프로젝트 예시 경로",
    (
        "plugins/common/agents/write-tests.md",
        "tests/unit/",
    ): "소비자 프로젝트 예시 경로",
    (
        "plugins/common/agents/write-tests.md",
        "tests/integration/",
    ): "소비자 프로젝트 예시 경로",
    (
        "plugins/common/agents/write-tests.md",
        "tests/scratch/",
    ): "소비자 프로젝트 예시 경로",
    (
        "CLAUDE.md",
        "agent-lifecycle.py",
    ): "제거된 파일을 **부재로** 서술하는 문장(2.6.0 에서 삭제)",
    (
        "docs/native-absorption.md",
        "agent-lifecycle.py",
    ): "제거된 파일을 흡수 이력으로 서술하는 행(2.6.0 에서 삭제)",
    (
        "docs/conventions/warning-signal.md",
        "site/hugo.toml",
    ): "과거 결함 사례 서술 — 그 파일은 5.2.2 에서 사이트와 함께 이전됐다",
}

#: 소비자 프로젝트 쪽·생성 경로 접두사 — 이 레포가 소유하지 않으므로 실재를 요구하지 않는다.
CONSUMER_PREFIXES = (
    ".claude/",
    ".git/",
    ".venv/",
    "venv/",
    "node_modules/",
    "graphify-out/",
    "docs/plans/",
    "docs/works/",
    "__pycache__/",
)
PLACEHOLDER_CHARS = set("<>{}*$~…|\\\"' ,;()=!?[]")

FENCE_TOKEN_RE = re.compile(r"[\w./\-]+")
FENCE_SH_RE = re.compile(r"^[\w\-]+\.sh$")
#: 이 레포에도 소비자 프로젝트에도 흔한 최상위 이름 — 펜스 안에서는 어느 쪽 예시인지 가릴 수 없다.
#: 목록은 **제외**다(`warning-signal.md` §검토 절차 5): 새 최상위 이름은 기본으로 검사 대상이 된다.
FENCE_GENERIC_ROOTS = frozenset({"docs", "tests", "test", "src", "lib", "site"})
FIX_PATH = "경로를 현재 위치로 고치거나, 옮겨진 것이면 새 경로를 적어라"
FIX_FILE = "파일이 지워졌으면 문장을 지우고, 옮겼으면 새 이름을 적어라"
FENCE_RE = re.compile(r"^\s*(```|~~~)")
LINK_RE = re.compile(r"(?<!\\)!?\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
IMPORT_RE = re.compile(r"^@([\w./-]+(?:\.\w+|/))\s*$")
CODE_SPAN_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
#: 슬래시가 든 백틱 토큰이 경로 모양인가. 확장자는 **이 레포가 실제로 추적하는 것만** 경로로
#: 본다(`Index.exts`) — 목록을 박으면 새 파일 종류가 생길 때 조용히 빠진다(§검토 절차 5).
#: 추적하지 않는 종류(`.ts` 등)는 소비자 프로젝트의 예시 파일이다.
PATH_TOKEN_RE = re.compile(r"^[\w.\-]+(?:/[\w.\-]+)+/?$")
PLACEHOLDER_SEGMENTS = ("path/to/",)
BARE_FILE_RE = re.compile(r"^[\w\-]+\.(?:sh|py)$")
FUNC_CALL_RE = re.compile(r"^([A-Za-z_]\w*)\(\)$")
DEF_RE = re.compile(
    r"^(?:def|class)\s+([A-Za-z_]\w*_\w*)\b"
)  # 밑줄 없는 한 단어는 예시 이름이다
DEF_DECL_RE = re.compile(
    r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)", re.MULTILINE
)
SH_FUNC_RE = re.compile(
    r"^\s*(?:function\s+)?([A-Za-z_]\w*)\s*\(\)\s*\{?", re.MULTILINE
)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
STATUS_RE = re.compile(r"^status:[ \t]*(\S+)[ \t]*$", re.MULTILINE)
BUILTINS = frozenset(dir(builtins))


class Index:
    """추적 파일 트리 + 정의 이름 색인. 존재 판정은 전부 여기서 한다(실제 FS 가 아니라 git)."""

    def __init__(self, files: list[str], root: Path) -> None:
        self.root = root
        self._ignored: dict[str, bool] = {}
        self.files = set(files)
        self.dirs: set[str] = set()
        self.basenames: set[str] = set()
        self.exts: set[str] = set()
        for rel in files:
            base = rel.rsplit("/", 1)[-1]
            self.basenames.add(base)
            if "." in base.lstrip("."):
                self.exts.add(base.rsplit(".", 1)[-1])
            parts = rel.split("/")
            for i in range(1, len(parts)):
                self.dirs.add("/".join(parts[:i]))
        self.defs: set[str] = set()
        #: 이 레포 루트와 플러그인 루트 바로 아래 항목 — 펜스 안에서 "우리 경로"를 알아보는 기준
        self.own_roots = {r.split("/")[0] for r in files} | {
            r.split("/")[3]
            for r in files
            if r.startswith(PLUGIN_ROOT_REL) and r.count("/") >= 3
        }

    def exists(self, rel: str) -> bool:
        rel = rel.rstrip("/")
        return rel in self.files or rel in self.dirs or self.ignored(rel)

    def ignored(self, rel: str) -> bool:
        """`.gitignore` 가 가리는 경로 — 빌드 산출 디렉토리다. 추적하지 않으므로 색인에 없지만 실재한다."""
        if rel not in self._ignored:
            # 끝 슬래시 없이는 `/public/` 같은 디렉토리 전용 패턴이 아직 없는 경로에 안 걸린다
            self._ignored[rel] = any(
                subprocess.run(
                    ["git", "check-ignore", "-q", "--", cand],
                    cwd=str(self.root),
                    capture_output=True,
                    check=False,
                    timeout=30,
                ).returncode
                == 0
                for cand in (rel, rel + "/")
            )
        return self._ignored[rel]

    def load_defs(self, root: Path, skipped: SkipTally) -> None:
        for rel in sorted(self.files):
            if not rel.endswith((".py", ".sh")) and rel.rsplit("/", 1)[-1] not in {
                "pre-commit",
                "pre-push",
            }:
                continue
            skipped.attempted += 1
            try:
                text = (root / rel).read_text(encoding="utf-8")
            except OSError as err:
                skipped.add(rel, "읽기실패", str(err))
                continue
            except UnicodeDecodeError:
                skipped.add(rel, "비-UTF-8", "정의 색인 대상이 아니다")
                continue
            self.defs.update(DEF_DECL_RE.findall(text))
            self.defs.update(SH_FUNC_RE.findall(text))


def _norm(parts: list[str]) -> str | None:
    """`..` 를 접어 레포 상대 경로로. 레포 밖으로 나가면 None."""
    out: list[str] = []
    for p in parts:
        if p in ("", "."):
            continue
        if p == "..":
            if not out:
                return None
            out.pop()
        else:
            out.append(p)
    return "/".join(out)


def _doc_status(text: str) -> str | None:
    fm = FRONTMATTER_RE.match(text)
    if fm is None:
        return None
    m = STATUS_RE.search(fm.group(1))
    return m.group(1).strip("\"'") if m else None


def _bases(doc: str) -> list[list[str]]:
    """경로 후보 기준점(레포 상대 디렉토리 조각 목록)."""
    doc_dir = doc.split("/")[:-1]
    plugin_root = PLUGIN_ROOT_REL.rstrip("/").split("/")
    bases = [[], doc_dir, plugin_root, [*plugin_root, "skills"]]
    if doc.startswith(SKILLS_PREFIX):
        bases.append(doc.split("/")[:4])  # plugins/common/skills/<name>
    return bases


def path_exists(index: Index, doc: str, target: str) -> bool:
    for base in _bases(doc):
        rel = _norm([*base, *target.split("/")])
        if rel is not None and index.exists(rel):
            return True
    return False


def is_placeholder(token: str) -> bool:
    return any(c in PLACEHOLDER_CHARS for c in token) or ".." in token.replace(
        "../", ""
    )


def is_consumer_path(token: str) -> bool:
    return (
        token.startswith(("/", "-"))
        or token.startswith(CONSUMER_PREFIXES)
        or (token.removeprefix("./").startswith(CONSUMER_PREFIXES))
    )


def iter_lines(text: str) -> list[tuple[int, str, bool]]:
    """frontmatter 를 뺀 (줄번호, 줄, 펜스 안인가). 펜스 여닫는 줄 자체는 뺀다."""
    fm = FRONTMATTER_RE.match(text)
    skip = text[: fm.end()].count("\n") if fm else 0
    out: list[tuple[int, str, bool]] = []
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if lineno <= skip:
            continue
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        out.append((lineno, line, in_fence))
    return out


Ref = tuple[str, str, str]  # (종류, 참조, 고치는 법)


def _check_links(doc: str, line: str, index: Index) -> list[Ref]:
    out: list[Ref] = []
    no_code = CODE_SPAN_RE.sub("", line)  # 코드 스팬 안의 링크 모양은 설명이다
    for m in LINK_RE.finditer(no_code):
        target = m.group(1).strip("<>")
        if URL_RE.match(target) or target.startswith("#"):
            continue
        target = re.split(r"[#?]", target, maxsplit=1)[0]
        if not target or is_placeholder(target) or not ("/" in target or "." in target):
            continue  # 슬래시도 점도 없으면 파일 링크가 아니다(`[x](URL)` 같은 자리표시자)
        base = [] if target.startswith("/") else doc.split("/")[:-1]
        rel = _norm([*base, *target.lstrip("/").split("/")])
        if rel is None or not index.exists(rel):
            out.append(
                (
                    "링크",
                    target,
                    "링크를 현재 경로로 고치거나, 시점 고정 기록이면 `status: historical` 을 달아라",
                )
            )
    return out


def _check_span(doc: str, span: str, index: Index) -> Ref | None:
    """백틱 한 덩어리. 종류를 **먼저** 가른 뒤 그 종류에 맞는 자리표시자 규칙만 건다."""
    md = DEF_RE.match(span)
    mf = FUNC_CALL_RE.match(span)
    if md or (mf and "_" in mf.group(1)):
        name = (md or mf).group(1)  # type: ignore[union-attr]
        if name not in index.defs and name not in BUILTINS:
            return (
                "정의" if md else "함수",
                span,
                "그 이름이 코드에 있는지 확인해 문서를 고쳐라(이름이 바뀌었으면 새 이름)",
            )
        return None
    if is_placeholder(span) or is_consumer_path(span):
        return None
    if (
        PATH_TOKEN_RE.match(span)
        and not any(seg in span for seg in PLACEHOLDER_SEGMENTS)
        and (span.endswith("/") or span.rsplit(".", 1)[-1] in index.exts)
        and not path_exists(index, doc, span)
    ):
        return (
            "경로",
            span,
            FIX_PATH,
        )
    if BARE_FILE_RE.match(span) and span not in index.basenames:
        return (
            "파일명",
            span,
            FIX_FILE,
        )
    return None


def _check_fence_line(doc: str, line: str, index: Index) -> list[Ref]:
    """펜스 안은 예시·출력·트리 그림이라 **이 레포 소유로 보이는 것만** 본다.

    소비자 프로젝트 예시(`src/`·`app.py`)까지 걸면 상시 참인 경고가 된다. 그렇다고 펜스를 통째로
    빼면 트리 그림 안의 죽은 스크립트(`db-tunnel.sh start`)가 영영 안 잡힌다(B-P0-4 실측).
    그래서 ① 첫 조각이 이 레포·플러그인 루트의 실제 항목인 경로 ② 이 레포의 `.sh` 이름만 본다.
    """
    out: list[Ref] = []
    for raw in FENCE_TOKEN_RE.findall(line):
        tok = raw.removeprefix("./").rstrip(".,:;")
        if is_consumer_path(tok):
            continue
        if "/" in tok:
            first = tok.split("/", 1)[0]
            if (
                first in index.own_roots
                and first not in FENCE_GENERIC_ROOTS
                and PATH_TOKEN_RE.match(tok)
                and not any(seg in tok for seg in PLACEHOLDER_SEGMENTS)
                and (tok.endswith("/") or tok.rsplit(".", 1)[-1] in index.exts)
                and not path_exists(index, doc, tok)
            ):
                out.append(("경로", tok, FIX_PATH))
        elif FENCE_SH_RE.match(tok) and tok not in index.basenames:
            out.append(("파일명", tok, FIX_FILE))
    return out


def find_refs(
    doc: str, text: str, index: Index, used: set[tuple[str, str]] | None = None
) -> list[tuple[int, str, str, str]]:
    """(줄, 종류, 참조, 고치는 법) — 실재하지 않는 것만."""
    bad: list[tuple[int, str, str, str]] = []

    def keep(refs: list[Ref]) -> list[Ref]:
        allowed = [r for r in refs if (doc, r[1]) in ALLOWED_REFS]
        if used is not None:
            used.update((doc, r[1]) for r in allowed)
        return [r for r in refs if r not in allowed]

    for lineno, line, in_fence in iter_lines(text):
        if LINE_OPT_OUT in line:
            continue
        if in_fence:
            bad.extend((lineno, *r) for r in keep(_check_fence_line(doc, line, index)))
            continue
        found = _check_links(doc, line, index)
        mi = IMPORT_RE.match(line)
        if (
            mi
            and not is_placeholder(mi.group(1))
            and not path_exists(index, doc, mi.group(1))
        ):
            found.append(
                (
                    "@import",
                    mi.group(1),
                    "import 대상을 현재 경로로 고쳐라 — 호스트는 없는 파일을 조용히 건너뛴다",
                )
            )
        for m in CODE_SPAN_RE.finditer(line):
            ref = _check_span(doc, m.group(1).strip(), index)
            if ref is not None:
                found.append(ref)
        bad.extend((lineno, *r) for r in keep(found))
    return bad


def scan_targets(files: list[str]) -> list[str]:
    return [
        rel
        for rel in files
        if rel.endswith(".md")
        and rel not in EXCLUDE_FILES
        and not rel.startswith(EXCLUDE_PREFIXES)
    ]


def main() -> int:
    files = tracked_files(REPO_ROOT, label=LABEL)
    index = Index(files, REPO_ROOT)
    skipped = SkipTally(LABEL)
    index.load_defs(REPO_ROOT, skipped)
    docs = scan_targets(files)
    if not docs:
        print(
            f"[{LABEL}] ✗ 검사할 문서가 0개다 — 통과가 아니라 파일 선택 경로의 결함이다"
        )
        return 1
    problems: list[tuple[str, int, str, str, str]] = []
    used: set[tuple[str, str]] = set()
    by_status = 0
    checked = 0
    for rel in docs:
        skipped.attempted += 1
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except OSError as err:
            skipped.add(rel, "읽기실패", str(err))
            continue
        except UnicodeDecodeError:
            skipped.add(rel, "비-UTF-8", "문서가 아니다")
            continue
        if _doc_status(text) in SKIPPED_STATUSES:
            by_status += 1
            continue
        checked += 1
        problems.extend((rel, *r) for r in find_refs(rel, text, index, used))
    rc = skipped.report(frozenset({"비-UTF-8"}))
    # 쓰이지 않은 예외는 죽은 설정이다 — 문서가 고쳐졌다는 뜻이므로 지우라고 알린다(노랑).
    for pair in sorted(set(ALLOWED_REFS) - used):
        print(
            f"[{LABEL}] ! 쓰이지 않는 예외 {pair[0]} · {pair[1]} — ALLOWED_REFS 에서 지워라"
        )
    if problems:
        print(
            f"[{LABEL}] ✗ 존재하지 않는 참조 {len(problems)}건 — 문서가 가리키는 대상이 없다"
        )
        for rel, lineno, kind, ref, hint in problems:
            print(f"    {rel}:{lineno}  [{kind}] {ref}")
            print(f"        → {hint}")
        return 1
    print(
        f"[{LABEL}] {'✗' if rc else '✓'} 참조 실재 — 문서 {checked}개 검사 "
        f"({by_status}개는 지위로 제외)"
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())
