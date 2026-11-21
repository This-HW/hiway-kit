#!/usr/bin/env python3
"""check_unicode_safety.py — 추적되는 텍스트에 **보이지 않는 Unicode** 가 실렸는지 검사한다.

`verify-done.sh §31` 과 CI 가 **같은 스크립트**를 호출한다(F-023 — bash 로 재구현하면 갈린다).

## 왜

킷의 배포물은 LLM 이 읽는 프롬프트다(rules·skills·agents·AGENTS.md …). zero-width·bidi 제어·
tag 문자(U+E0000–E007F)는 리뷰 화면에서 보이지 않지만 모델 입력에는 그대로 들어간다 — tag 문자는
ASCII 를 한 글자씩 숨겨 실을 수 있다. 사람이 diff 를 읽어서는 잡을 수 없으므로 기계가 본다.
범위는 `plugins/common/tools/hidden_chars.py` 하나가 정의한다(런타임 정제와 같은 표).

## 검사 조건 (한 문장)

**git 이 추적하는 모든 파일(바이너리로 인정된 것 제외)의 내용과 경로에서, 예외 파일에 사유와
함께 등재되지 않은 은닉 문자가 하나라도 나오면 fail.** 분기가 없다 — 항상 돈다.

대상을 나열하지 않고 **제외를 나열한다**(`warning-signal.md` §검토 5): 새 파일은 기본으로 검사
대상이고, 예외는 `scripts/unicode-safety-exceptions.json` 에 `path`·`codepoint`·`reason`(+선택
`line`)으로만 둔다. 사유 없는 예외, 대상 범위 밖 코드포인트, **아무것도 가리지 않는 예외**는
전부 fail 이다 — 쓰이지 않는 예외는 다음 결함을 숨길 자리만 남긴다.

## 출력은 문자를 찍지 않는다

실패 줄은 `file:line:col U+XXXX (분류)` 뿐이다. 은닉 문자를 원문 그대로 찍으면 그 출력이
CI 로그·트랜스크립트로 옮겨 가 **페이로드를 다시 실어 나른다**(`warning-signal.md` §검토 6).
경로에 든 은닉 문자는 `\\u{XXXX}` 로 바꿔 찍는다.

## 예외 경로는 레포 안으로 봉쇄한다

예외 파일의 `path` 는 설정에서 온 경로다 — 한 번만 resolve 해서 레포 루트 안이 아니면 fail
(`docs/conventions/path-containment.md`). 절대경로·`..`·심링크 탈출 전부.

## 읽기

비-UTF-8 바이트는 `errors="replace"` 로 읽어 **건너뛰지 않는다** — 올바른 UTF-8 로 인코딩된
은닉 문자는 파일의 나머지가 깨져 있어도 찾는다. 추적되는 심링크는 git 이 저장하는 것(링크 대상
문자열)을 검사한다. 읽기 실패(`OSError`)는 사각지대이므로 red 다 — 그 메시지의 경로·오류 문자열도
은닉 문자를 이스케이프해 찍는다(OS 오류 문자열에는 파일명이 그대로 들어 있다).

## 바이너리는 **구조로** 인정한다 — NUL 바이트는 판정 근거가 아니다

예전에는 NUL 바이트 하나가 있으면 바이너리로 보고 통째로 건너뛰었다. 그러면 `.md` 에 `\\x00` 하나를
넣는 것만으로 같은 파일의 tag 문자가 전부 게이트를 빠져나간다(보안 리뷰 M-1, 5.9.0). 그래서 NUL 이
든 파일은 다음 둘 중 하나로 **바이너리임이 확인될 때만** 제외한다:

1. 확장자가 `BINARY_SUFFIXES`(이미지·아카이브·폰트·컴파일 산출물·인덱스) 중 하나
2. `.gitattributes` 가 그 경로를 바이너리로 선언(`binary` 매크로 또는 `-text`) — `git check-attr`

둘 다 아니면 **fail** 이다(NUL 이 든 텍스트 파일). 내용도 그대로 검사해 은닉 문자를 따로 보고한다.
NUL 이 없는 파일은 확장자와 무관하게 텍스트로 검사한다 — 확장자만 바꿔 다는 회피가 통하지 않는다.
제외한 바이너리는 **개수가 아니라 목록으로** 찍는다(무엇을 안 봤는지가 보여야 한다).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parent / "plugins" / "common" / "tools"))

from git_tracked import SkipTally, tracked_files  # noqa: E402
from hidden_chars import HIDDEN_RE, classify  # noqa: E402

LABEL = "check-unicode-safety"
EXCEPTIONS_REL = "scripts/unicode-safety-exceptions.json"
_CODEPOINT_RE = re.compile(r"^U\+([0-9A-F]{4,6})$")
_EXCEPTION_KEYS = frozenset({"path", "line", "codepoint", "reason"})
#: NUL 이 들어 있어도 바이너리로 인정하는 확장자(소문자). 여기 없는 확장자의 NUL 파일은 fail 이다 —
#: 정당한 바이너리라면 이 목록에 넣거나 `.gitattributes` 에 `binary` 로 선언한다.
BINARY_SUFFIXES: frozenset[str] = frozenset(
    {
        # 이미지
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".icns", ".webp", ".bmp", ".tif", ".tiff",
        # 문서·아카이브
        ".pdf", ".zip", ".gz", ".tgz", ".bz2", ".xz", ".zst", ".7z", ".tar", ".jar",
        # 폰트
        ".woff", ".woff2", ".ttf", ".otf", ".eot",
        # 컴파일·직렬화 산출물 (clangd 인덱스 픽스처 `.idx` 포함)
        ".pyc", ".so", ".dylib", ".dll", ".exe", ".o", ".a", ".class", ".wasm", ".idx", ".bin",
        ".sqlite", ".db",
    }
)
#: 읽기 실패는 사각지대다 — 노랑으로 내릴 사유는 없다(git_tracked.SkipTally.report 참고).
NONFATAL_SKIP_REASONS: frozenset[str] = frozenset()


class PolicyError(Exception):
    """예외 파일이 규칙을 어겼다 — 게이트는 판정 대신 exit 1."""


def _resolve_in_repo(
    container_root: Path, rel_path: str
) -> tuple[Path | None, str | None]:
    """`rel_path` 를 `container_root` 안으로만 한정해 **한 번** 해석한다.

    `scripts/build-targets.py::_resolve_in_repo` 와 같은 계약(D-15 — 구현은 여러 벌, 계약은
    하나; 공유 적대적 케이스 `scripts/tests/resolve_in_repo_contract.py`). 호출자는 반환된
    Path 를 그대로 쓴다 — 다시 `container_root / rel_path` 를 계산하지 않는다.
    """
    real = (container_root / rel_path).resolve()
    try:
        real.relative_to(container_root.resolve())
    except ValueError:
        return None, f"레포 루트 밖을 가리킨다 → {real}"
    return real, None


def escape_hidden(text: str) -> str:
    """출력용 — 은닉 문자를 `\\u{XXXX}` 로, 인코딩할 수 없는 바이트는 백슬래시 표기로."""
    escaped = HIDDEN_RE.sub(lambda m: f"\\u{{{ord(m.group()):04X}}}", text)
    return escaped.encode("utf-8", "backslashreplace").decode("utf-8")


def load_exceptions(root: Path) -> list[dict]:
    """예외 목록. 파일이 없으면 빈 목록(더 엄격해질 뿐이다), 규칙 위반이면 PolicyError.

    반환 항목: `{"rel": 레포 상대 posix 경로, "line": int|None, "cp": int, "label": 표시용}`.
    """
    path = root / EXCEPTIONS_REL
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as err:
        raise PolicyError(f"{EXCEPTIONS_REL} 를 읽지 못했다 — {err}") from err
    raw = data.get("exceptions") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raise PolicyError(f"{EXCEPTIONS_REL}: 최상위 'exceptions' 배열이 필요하다")
    root_real = root.resolve()
    out: list[dict] = []
    for i, item in enumerate(raw):
        where = f"{EXCEPTIONS_REL} exceptions[{i}]"
        if not isinstance(item, dict):
            raise PolicyError(f"{where}: 객체가 아니다")
        unknown = set(item) - _EXCEPTION_KEYS
        if unknown:
            raise PolicyError(
                f"{where}: 모르는 키 {sorted(unknown)} — 허용 키는 {sorted(_EXCEPTION_KEYS)}"
            )
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise PolicyError(
                f"{where}: 'reason' 이 비었다 — 사유 없는 예외는 받지 않는다"
            )
        rel = item.get("path")
        if not isinstance(rel, str) or not rel or "\0" in rel:
            raise PolicyError(f"{where}: 'path' 는 비어 있지 않은 문자열이어야 한다")
        try:
            real, error = _resolve_in_repo(root, rel)
        except (OSError, RuntimeError) as err:
            raise PolicyError(f"{where}: 경로를 해석하지 못했다 — {err}") from err
        if real is None:
            raise PolicyError(f"{where}: 경로 탈출 차단 — {error}")
        cp_raw = item.get("codepoint")
        m = _CODEPOINT_RE.match(cp_raw) if isinstance(cp_raw, str) else None
        if not m:
            raise PolicyError(f"{where}: 'codepoint' 는 'U+200D' 형식이어야 한다")
        cp = int(m.group(1), 16)
        if classify(cp) is None:
            raise PolicyError(
                f"{where}: {cp_raw} 는 검사 대상 범위가 아니다 — 예외가 필요 없다"
            )
        line = item.get("line")
        if line is not None and (
            isinstance(line, bool) or not isinstance(line, int) or line < 1
        ):
            raise PolicyError(f"{where}: 'line' 은 1 이상의 정수여야 한다")
        out.append(
            {
                "rel": real.relative_to(root_real).as_posix(),
                "line": line,
                "cp": cp,
                "label": f"{escape_hidden(rel)}{':' + str(line) if line else ''} U+{cp:04X}",
            }
        )
    return out


def _read(path: Path) -> tuple[str, bool]:
    """(검사할 텍스트, NUL 포함 여부). 읽기 실패는 OSError 로 올린다.

    NUL 이 있어도 내용을 돌려준다 — 바이너리 인정 여부는 호출부가 구조로 정한다(독스트링).
    """
    if path.is_symlink():
        return os.readlink(path), False  # git 이 저장하는 것은 링크 대상 문자열이다
    data = path.read_bytes()
    return data.decode("utf-8", errors="replace"), b"\0" in data


def _attr_binary(root: Path, rels: list[str]) -> set[str]:
    """`.gitattributes` 가 바이너리로 선언한 경로(`binary` 매크로 또는 `-text`).

    `git check-attr` 를 **NUL 이 든 파일에만** 한 번 부른다. 실패하면 빈 집합 — 더 엄격해질 뿐이다
    (확장자로 인정되지 않은 NUL 파일이 fail 로 남는다).
    """
    if not rels:
        return set()
    try:
        res = subprocess.run(
            ["git", "check-attr", "-z", "--stdin", "binary", "text"],
            cwd=str(root), input="\0".join(rels) + "\0", capture_output=True,
            encoding="utf-8", errors="surrogateescape", timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if res.returncode != 0:
        return set()
    fields = res.stdout.split("\0")
    out: set[str] = set()
    for i in range(0, len(fields) - 2, 3):
        rel, attr, value = fields[i], fields[i + 1], fields[i + 2]
        if (attr == "binary" and value == "set") or (attr == "text" and value == "unset"):
            out.add(rel)
    return out


def scan(
    root: Path,
) -> tuple[list[tuple[str, int, int, int]], SkipTally, list[str], list[str]]:
    """(경로, 줄, 열, 코드포인트) 히트 목록, 읽기 실패 집계, 제외한 바이너리, 인정되지 않은 NUL 파일.

    줄은 `\\n` 기준(편집기와 같은 번호 — `splitlines()` 는 U+2028 등에서도 쪼갠다), 열은
    1부터 센 코드포인트 위치다. 경로 자체의 은닉 문자는 줄 0 으로 보고한다.
    """
    hits: list[tuple[str, int, int, int]] = []
    skipped = SkipTally(LABEL)
    texts: dict[str, str] = {}
    nul_files: list[str] = []
    for rel in tracked_files(root, label=LABEL):
        for m in HIDDEN_RE.finditer(rel):
            hits.append((rel, 0, m.start() + 1, ord(m.group())))
        skipped.attempted += 1
        try:
            text, has_nul = _read(root / rel)
        except OSError as err:
            skipped.add(escape_hidden(rel), "읽기실패", escape_hidden(str(err)))
            continue
        texts[rel] = text
        if has_nul:
            nul_files.append(rel)
    attr_binary = _attr_binary(root, nul_files)
    binaries: list[str] = []
    unexplained_nul: list[str] = []
    for rel in nul_files:
        if Path(rel).suffix.lower() in BINARY_SUFFIXES or rel in attr_binary:
            binaries.append(rel)
            del texts[rel]
        else:
            unexplained_nul.append(rel)
    for rel, text in texts.items():
        if not HIDDEN_RE.search(text):
            continue
        for lineno, line in enumerate(text.split("\n"), 1):
            for m in HIDDEN_RE.finditer(line):
                hits.append((rel, lineno, m.start() + 1, ord(m.group())))
    return hits, skipped, binaries, unexplained_nul


def _covered(hit: tuple[str, int, int, int], exceptions: list[dict]) -> dict | None:
    rel, lineno, _col, cp = hit
    for exc in exceptions:
        if exc["rel"] == rel and exc["cp"] == cp and exc["line"] in (None, lineno):
            return exc
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=SCRIPTS_DIR.parent,
        help="검사할 저장소 루트(기본: 이 스크립트의 레포)",
    )
    root = parser.parse_args(argv).root
    try:
        exceptions = load_exceptions(root)
    except PolicyError as err:
        print(f"[{LABEL}] ✗ 예외 파일 규칙 위반 — {err}")
        return 1
    hits, skipped, binaries, unexplained_nul = scan(root)
    rc = skipped.report(NONFATAL_SKIP_REASONS)
    if unexplained_nul:
        print(
            f"[{LABEL}] ✗ NUL 바이트가 든 파일 {len(unexplained_nul)}건 — 바이너리로 인정되지 않았다"
            "(확장자·.gitattributes 근거 없음). 내용은 텍스트로 검사했다"
        )
        for rel in unexplained_nul:
            print(f"    {escape_hidden(rel)}")
        print(
            "    → 텍스트라면 NUL 을 지워라. 정당한 바이너리라면 .gitattributes 에 `<경로> binary` 로 "
            "선언하거나 BINARY_SUFFIXES 에 확장자를 넣는다."
        )
        rc = 1

    used: set[int] = set()
    bad: list[tuple[str, int, int, int]] = []
    for hit in hits:
        exc = _covered(hit, exceptions)
        if exc is None:
            bad.append(hit)
        else:
            used.add(id(exc))
    if bad:
        print(
            f"[{LABEL}] ✗ 보이지 않는 Unicode {len(bad)}건 — 문자는 찍지 않는다(코드포인트만)"
        )
        for rel, lineno, col, cp in bad:
            where = "경로" if lineno == 0 else "내용"
            print(
                f"    {escape_hidden(rel)}:{lineno}:{col} U+{cp:04X} ({classify(cp)}, {where})"
            )
        print(
            "    → 우연히 들어간 것이면 지워라. 정당하면(예: 이모지 ZWJ 시퀀스) "
            f"{EXCEPTIONS_REL} 에 path·codepoint·reason(+line) 으로 등재한다."
        )
        rc = 1
    stale = [e for e in exceptions if id(e) not in used]
    if stale:
        print(
            f"[{LABEL}] ✗ 아무것도 가리지 않는 예외 {len(stale)}건 — 지워라(쓰이지 않는 예외는 다음 결함을 숨긴다)"
        )
        for exc in stale:
            print(f"    {exc['label']}")
        rc = 1
    if rc == 0:
        print(
            f"[{LABEL}] ✓ 보이지 않는 Unicode 0건 — 텍스트 {skipped.parsed - len(binaries)}개 파일 검사"
            f"(바이너리 {len(binaries)}개 제외, 예외 {len(exceptions)}건)"
        )
    if binaries:
        print(f"[{LABEL}]   제외한 바이너리(확장자·.gitattributes 로 인정):")
        for rel in binaries:
            print(f"    {escape_hidden(rel)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
