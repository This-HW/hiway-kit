#!/usr/bin/env python3
"""check_doc_status.py — 문서 지위 표기와, 살아있는 문서의 낡은 토큰·깨진 표.

`verify-done.sh §28` 과 CI 가 **같은 스크립트**를 호출한다(F-023).

## 검사 조건 (한 문장)

**① 추적 중인 모든 `docs/**/*.md` 의 frontmatter 가 `status`·`as_of`(·`superseded_by`) 스키마를
어기면 fail, ② `status: current` 인 `docs/` 문서와 `docs/` 밖의 살아있는 문서(제외 아래)에
금지 토큰이 있거나 GFM 표의 열 수가 헤더와 다른 행이 있으면 fail.** 분기가 없다 — 항상 돈다
(`docs/conventions/warning-signal.md` §검토 절차 4).

## 왜 있는가

감사(`docs/specs/2026-10-05-audit-remediation/audit/B-docs.md`)가 낸 P0 급 사실 오류 9건의 공통
원인 첫째가 **시점 고정 문서에 지위 표기가 없는 것**이었다 — 4.0.0 에서 Work 시스템을 걷어냈는데
`docs/` 곳곳이 `docs/works`·`work.sh`·`W-0xx` 를 현재형으로 말했고, 독자는 그 문서가 *그때의
기록* 인지 *지금의 안내* 인지 가릴 수 없었다. 표 열 수 불일치는 렌더에서 조용히 잘리는 셀이다.

## 지위 스키마 (스펙 D0-2)

| 필드 | 값 |
| --- | --- |
| `status` | `current` · `historical` · `proposal` · `superseded` |
| `as_of` | `YYYY-MM-DD` — 그 지위가 확인된 날 |
| `superseded_by` | `status: superseded` 일 때만 필수 — 대체 문서의 **레포 상대 경로**(추적 파일이어야 한다) |

`historical`·`superseded` 문서는 ②(금지 토큰·표)와 `check_doc_refs.py` 에서 **제외**한다. 시점 고정
기록은 그때의 이름·경로를 쓰는 것이 정확하다. 본문에 지위를 한 줄로 반복하지 않는다 — 필드가 SSOT 다.

## ② 의 대상 — 제외를 나열한다 (`warning-signal.md` §검토 절차 5)

`docs/` 밖의 마크다운(README·CLAUDE.md·플러그인 문서·스킬·에이전트)은 지위 필드가 없지만 **살아있는
문서**이므로 current 로 본다. 빠지는 것은 정당화된 아래뿐이다.

- `CHANGELOG.md` — 옛 이름이 사실로서 적힌다.
- `AGENTS.md`·`GEMINI.md` — 생성물이다. 원본(`rules/`·`docs/conventions/`)이 검사 대상이고 드리프트는
  `verify-done.sh §11` 이 잡는다 — 여기서 또 걸면 같은 결함을 두 번 보고한다.
- `evals/scenarios/` — 의도적으로 틀린 코드를 담은 픽스처다.
- 구 플러그인 이름 토큰만: `packaging/name-targets.json` 의 `oldNameScanExclude` 에 걸리는 파일
  (구 이름이 사실로서 등장해야 하는 곳 — `check_old_names.py` 와 **같은 정책 파일**이 소유한다).
- 줄 단위: 그 줄에 `doc-status-ok` 가 있으면 건너뛴다(`old-name-ok` 와 같은 관례).

## 표 열 수 — GFM 규칙 그대로

헤더 행·구분 행(`|---|---|`)의 셀 수가 같아야 표고, 이후 행의 셀 수가 다르면 fail 이다.
GFM 은 이스케이프(`\\|`)하지 않은 `|` 를 **코드 스팬 안에서도** 셀 구분자로 센다 — 그래서
`` `a|b` `` 는 열이 하나 늘어난다(렌더는 초과 셀을 조용히 버린다). 펜스 코드블록 안은 표가 아니다.

## `superseded_by` 는 경로를 만든다 — 봉쇄한다

`docs/conventions/path-containment.md`: 문서에서 읽은 값으로 경로를 만드는 코드는 그 값을 검증해야
한다. 여기서는 파일을 열지 않고 **추적 파일 집합과 대조**한다 — 값을 한 번 정규화(`posixpath.normpath`)해
쓰고, 절대경로·`..` 탈출·빈 값은 red 다. 파일시스템을 다시 resolve 하지 않으므로 검사와 사용 사이
틈(TOCTOU)이 없다.

## red 메시지

고치는 법을 한 줄로 적는다(`C-M3`). 낡은 토큰은 *현재 대응물로 고치거나, 시점 고정 기록이면
`status: historical`* 을 달라고 안내한다.
"""

from __future__ import annotations

import datetime
import json
import posixpath
import re
import sys
from pathlib import Path

from git_tracked import SkipTally, tracked_files

REPO_ROOT = Path(__file__).resolve().parent.parent
NAME_POLICY = REPO_ROOT / "packaging" / "name-targets.json"
LABEL = "check-doc-status"
LINE_OPT_OUT = "doc-status-ok"

STATUSES = ("current", "historical", "proposal", "superseded")
#: 지위 때문에 ②(금지 토큰·표)에서 빠지는 값 — check_doc_refs.py 와 같은 집합.
SKIPPED_STATUSES = frozenset({"historical", "superseded"})

#: ② 에서 빠지는 파일 — 정당화된 것만(위 독스트링).
EXCLUDE_FILES = frozenset({"CHANGELOG.md", "AGENTS.md", "GEMINI.md"})
EXCLUDE_PREFIXES = ("evals/scenarios/",)

#: 금지 토큰 — 4.0.0(Work 제거)·5.2.0(`tools/` 분리)·5.3.0(에이전트 평탄화) 이후 **현재형으로 쓰면 틀리는**
#: 이름이다. (정규식, 가리키는 것, 고치는 법)
FORBIDDEN: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"agents/(?:dev|meta|planning)/"),
        "5.3.0 에서 평탄화된 `agents/<분류>/` 경로",
        "`plugins/common/agents/<name>.md` 로 고쳐라",
    ),
    (
        re.compile(r"hooks/(?:checklist|feedback_ledger|export_harness)\b"),
        "5.2.0 에서 `tools/` 로 옮긴 스크립트 경로",
        "`plugins/common/tools/<name>.py` 로 고쳐라",
    ),
    (
        re.compile(r"docs/works\b"),
        "4.0.0 에서 제거된 Work 시스템 경로",
        "계획은 `docs/plans/<날짜>-<slug>/plan.md`, 이 레포 산출물은 `docs/specs/<날짜>-<주제>/` 다",
    ),
    (
        re.compile(r"\bwork\.sh\b"),
        "4.0.0 에서 제거된 Work 스크립트",
        "문장을 지우거나 plan-task 스킬 절차로 바꿔라",
    ),
    (
        re.compile(r"\bW-0\d\d\b"),
        "4.0.0 에서 제거된 Work ID",
        "스펙 경로(`docs/specs/<날짜>-<주제>/`)로 바꾸거나, 시점 고정 기록이면 `status: historical`",
    ),
)
OLD_NAME_WHAT = "개명 전 플러그인 이름"
OLD_NAME_FIX = "현재 이름으로 고치거나, 사실로서 인용하는 기록이면 `status: historical`"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
FIELD_RE = re.compile(r"^([A-Za-z_][\w-]*):[ \t]*(.*?)[ \t]*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
DELIM_CELL_RE = re.compile(r"^:?-+:?$")
UNESCAPED_PIPE_RE = re.compile(r"(?<!\\)\|")


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """최상위 `key: value` 만 읽는다(지위 스키마는 평면이다). 없으면 None."""
    fm = FRONTMATTER_RE.match(text)
    if fm is None:
        return None
    fields: dict[str, str] = {}
    for line in fm.group(1).splitlines():
        m = FIELD_RE.match(line)
        if m:
            fields[m.group(1)] = m.group(2).strip("\"'")
    return fields


def schema_problems(fields: dict[str, str] | None, tracked: set[str]) -> list[str]:
    """D0-2 스키마 위반 사유. 비었으면 통과."""
    if fields is None:
        return [
            "frontmatter 가 없다 — 맨 위에 `---` / `status: current` / `as_of: YYYY-MM-DD` / `---` 를 달아라"
        ]
    out: list[str] = []
    status = fields.get("status")
    if status is None:
        out.append(
            f"`status` 가 없다 — {' | '.join(STATUSES)} 중 하나를 달아라(시점 고정 기록이면 historical)"
        )
    elif status not in STATUSES:
        out.append(
            f"`status: {status}` 는 스키마 밖이다 — {' | '.join(STATUSES)} 중 하나"
        )
    as_of = fields.get("as_of")
    if as_of is None:
        out.append(
            "`as_of` 가 없다 — 그 지위를 확인한 날을 `as_of: YYYY-MM-DD` 로 달아라"
        )
    else:
        try:
            datetime.date.fromisoformat(as_of)
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
                raise ValueError(as_of)
        except ValueError:
            out.append(f"`as_of: {as_of}` 가 `YYYY-MM-DD` 날짜가 아니다")
    if status == "superseded":
        out.extend(_superseded_by_problems(fields.get("superseded_by"), tracked))
    return out


def _superseded_by_problems(value: str | None, tracked: set[str]) -> list[str]:
    if not value:
        return [
            "`status: superseded` 인데 `superseded_by` 가 없다 — 대체 문서의 레포 상대 경로를 달아라"
        ]
    norm = posixpath.normpath(value)
    if posixpath.isabs(value) or norm == ".." or norm.startswith("../") or norm == ".":
        return [
            f"`superseded_by: {value}` 가 레포 밖을 가리킨다 — 레포 상대 경로여야 한다"
        ]
    if norm not in tracked:
        return [
            f"`superseded_by: {value}` 가 추적 파일이 아니다 — 대체 문서의 실제 경로로 고쳐라"
        ]
    return []


def split_cells(row: str) -> list[str]:
    """GFM 셀 분할 — 이스케이프하지 않은 `|` 는 코드 스팬 안에서도 구분자다."""
    body = row.strip()
    body = body.removeprefix("|")
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return UNESCAPED_PIPE_RE.split(body)


def is_delimiter_row(row: str) -> bool:
    if "|" not in row and "-" not in row:
        return False
    cells = [c.strip() for c in split_cells(row)]
    return bool(cells) and all(DELIM_CELL_RE.match(c) for c in cells)


def table_problems(text: str) -> list[tuple[int, str]]:
    """(줄, 사유) — 헤더와 열 수가 다른 표 행. 펜스·frontmatter 안은 보지 않는다."""
    fm = FRONTMATTER_RE.match(text)
    skip = text[: fm.end()].count("\n") if fm else 0
    lines = text.splitlines()
    out: list[tuple[int, str]] = []
    in_fence = False
    i = skip
    while i < len(lines):
        line = lines[i]
        if FENCE_RE.match(line):
            in_fence = not in_fence
            i += 1
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if (
            not in_fence
            and "|" in line
            and "|" in nxt
            and is_delimiter_row(nxt)
            and LINE_OPT_OUT not in line
        ):
            width = len(split_cells(line))
            if len(split_cells(nxt)) == width:
                j = i + 2
                while j < len(lines) and "|" in lines[j] and lines[j].strip():
                    n = len(split_cells(lines[j]))
                    if n != width and LINE_OPT_OUT not in lines[j]:
                        out.append(
                            (
                                j + 1,
                                f"표 행의 열이 {n}개인데 헤더는 {width}개다 — 셀 안의 `|` 는 `\\|` 로 "
                                "이스케이프하라(코드 스팬 안에서도 구분자로 센다)",
                            )
                        )
                    j += 1
                i = j
                continue
        i += 1
    return out


def token_problems(
    text: str, check_old_names: bool, old_names: list[str]
) -> list[tuple[int, str, str]]:
    """(줄, 설명, 고치는 법) — 금지 토큰이 든 줄. frontmatter 는 보지 않는다(지위 필드는 메타데이터다)."""
    fm = FRONTMATTER_RE.match(text)
    skip = text[: fm.end()].count("\n") if fm else 0
    out: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if lineno <= skip or LINE_OPT_OUT in line:
            continue
        for pat, what, fix in FORBIDDEN:
            m = pat.search(line)
            if m:
                out.append((lineno, f"`{m.group(0)}` — {what}", fix))
        if check_old_names:
            for name in old_names:
                if name in line:
                    out.append((lineno, f"`{name}` — {OLD_NAME_WHAT}", OLD_NAME_FIX))
                    break
    return out


def load_old_name_policy() -> tuple[list[str], tuple[str, ...]]:
    """(구 이름 목록, 구 이름 검사 제외 접두사). 정책을 못 읽으면 exit 1(green 위장 금지)."""
    try:
        policy = json.loads(NAME_POLICY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        print(f"[{LABEL}] ✗ 이름 정책을 읽지 못했다: {NAME_POLICY} ({err})")
        raise SystemExit(1) from err
    names = [
        n for n in policy.get("previousNames", []) if isinstance(n, str) and n.strip()
    ]
    if not names:
        print(
            f"[{LABEL}] ✗ previousNames 가 비었다 — 구 이름 검사가 영원히 아무것도 못 잡는다"
        )
        raise SystemExit(1)
    exclude = tuple(
        x for x in policy.get("oldNameScanExclude", []) if isinstance(x, str)
    )
    return names, exclude


def main() -> int:
    files = tracked_files(REPO_ROOT, label=LABEL)
    tracked = set(files)
    mds = [f for f in files if f.endswith(".md")]
    if not mds:
        print(f"[{LABEL}] ✗ 추적 중인 마크다운이 0개다 — 파일 선택 경로의 결함이다")
        return 1
    old_names, old_exclude = load_old_name_policy()
    skipped = SkipTally(LABEL)
    schema_bad: list[tuple[str, list[str]]] = []
    content_bad: list[tuple[str, int, str, str]] = []
    n_docs = n_scanned = n_status_skipped = 0
    for rel in mds:
        in_docs = rel.startswith("docs/")
        if not in_docs and (rel in EXCLUDE_FILES or rel.startswith(EXCLUDE_PREFIXES)):
            continue
        skipped.attempted += 1
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except OSError as err:
            skipped.add(rel, "읽기실패", str(err))
            continue
        except UnicodeDecodeError:
            skipped.add(rel, "비-UTF-8", "문서가 아니다")
            continue
        fields = parse_frontmatter(text)
        if in_docs:
            n_docs += 1
            problems = schema_problems(fields, tracked)
            if problems:
                schema_bad.append((rel, problems))
        if rel in EXCLUDE_FILES or rel.startswith(EXCLUDE_PREFIXES):
            continue
        if fields is not None and fields.get("status") in SKIPPED_STATUSES:
            n_status_skipped += 1
            continue
        if in_docs and (fields is None or fields.get("status") != "current"):
            # proposal 이거나 스키마 위반(이미 ① 에서 red) — 지위가 current 로 확정된 것만 ② 를 건다
            continue
        n_scanned += 1
        skip_old = rel.startswith(old_exclude)
        for lineno, what, fix in token_problems(text, not skip_old, old_names):
            content_bad.append((rel, lineno, what, fix))
        for lineno, why in table_problems(text):
            content_bad.append((rel, lineno, why, "표 행의 셀 수를 헤더에 맞춰라"))
    rc = skipped.report(frozenset({"비-UTF-8"}))
    if schema_bad:
        print(
            f"[{LABEL}] ✗ 문서 지위 스키마 위반 {len(schema_bad)}개 파일 — `docs/` 문서 {n_docs}개 중"
        )
        for rel, problems in schema_bad:
            print(f"    {rel}")
            for p in problems:
                print(f"        → {p}")
        rc = 1
    if content_bad:
        print(f"[{LABEL}] ✗ 살아있는 문서의 낡은 토큰·깨진 표 {len(content_bad)}건")
        for rel, lineno, what, fix in content_bad:
            print(f"    {rel}:{lineno}  {what}")
            print(f"        → {fix}")
        rc = 1
    if rc == 0:
        print(
            f"[{LABEL}] ✓ 지위 스키마 {n_docs}개 · 토큰·표 {n_scanned}개 검사 "
            f"({n_status_skipped}개는 지위로 제외)"
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
