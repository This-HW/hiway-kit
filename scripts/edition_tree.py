"""Shared Git and frontmatter helpers for edition builders."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


def _git(
    repo: Path,
    *args: str,
    env: dict[str, str] | None = None,
    check: bool = True,
    label: str,
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
            f"[{label}] ✗ git {' '.join(args)} 실패: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def _git_bytes(
    repo: Path,
    *args: str,
    env: dict[str, str] | None = None,
    data: bytes | None = None,
    label: str,
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
            f"[{label}] ✗ git {' '.join(args)} 실패: "
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
    서브모듈은 파싱 결과에 포함한다. 허용 여부는 호출자가 판정한다.
    """
    out = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        fields = meta.decode().split()
        if len(fields) == 3 and fields[1] in ("blob", "tree", "commit"):  # ls-tree: 모드 종류 sha
            mode, _kind, sha = fields
        else:  # ls-files -s: 모드 sha 단계
            mode, sha, _stage = fields
        out.append((mode, sha, path.decode("utf-8", errors="surrogateescape")))
    return out


def _frontmatter_span(text: str, path: str = "", *, label: str) -> tuple[int, int] | None:
    """frontmatter 블록의 (시작, 닫는 `---` 줄의 시작) 위치. 첫 줄이 `---` 로 시작하지 않으면 None.

    **정확한** `---` 줄만 경계로 인정한다. 첫 줄이나 닫는 줄이 `---` 처럼 보이는데 정확하지
    않으면(BOM·뒤 공백·CRLF) 변환하지 않고 exit 1 — 넘어가면 머리말이 frontmatter 위나
    본문 수평선 뒤에 들어간다(5.9.1 리뷰).
    """
    if not text.lstrip("\ufeff").startswith("---"):
        return None
    if not text.startswith("---\n"):
        sys.exit(
            f"[{label}] ✗ {path}: frontmatter 첫 줄이 정확히 `---` 가 아니다(BOM·뒤 공백·CRLF)"
            " — 원본을 고쳐라"
        )
    pos = 4
    for line in text[4:].split("\n"):
        if line.rstrip() == "---":
            if line != "---":
                sys.exit(
                    f"[{label}] ✗ {path}: frontmatter 닫는 줄이 정확히 `---` 가 아니다 — 원본을 고쳐라"
                )
            return 0, pos
        pos += len(line) + 1
    sys.exit(f"[{label}] ✗ {path}: frontmatter 닫는 `---` 줄이 없다")


def _strip_keys(
    text: str, keys: tuple[str, ...], path: str = "", *, label: str
) -> str:
    """frontmatter 의 `key: 값` 한 줄만 지운다. 블록 밖과 다른 줄은 바이트 그대로.

    지울 키가 **한 줄짜리 스칼라**가 아니면(값이 비었거나 다음 줄이 들여쓴 이어짐 — 지우면 옆 키에 값이
    붙는다, 따옴표 키, 들여쓴 키) 손으로 고치게 exit 1. 조용히 남기거나 반쯤 지우지 않는다.
    """
    span = _frontmatter_span(text, path, label=label)
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
                    f"[{label}] ✗ {path}: 들여쓴 `{loose.group(1)}:` 줄이 있다 — 블록 값 속 글일 수"
                    " 있지만 YAML 을 풀지 않고는 가를 수 없다. 표현을 바꿔라(한 줄짜리 키가 아닌 형태)"
                )
            if not exact or exact.group(1) != loose.group(1) or nxt[:1] in (" ", "\t"):
                sys.exit(
                    f"[{label}] ✗ {path}: `{loose.group(1)}` 를 한 줄짜리 `키: 값` 이 아닌 형태로"
                    " 썼다 — 지우면 옆 키가 오염된다. 원본을 한 줄로 고쳐라"
                )
            i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out) + text[end:]


def _note_marker(note: str) -> str:
    return note.split("\n", 1)[0][:40]


def _with_note(text: str, note: str, path: str = "", *, label: str) -> str:
    """frontmatter 바로 뒤(없으면 맨 앞)에 머리말을 넣는다. 이미 있으면 그대로. 뒤에 빈 줄을 보장한다 —
    빈 줄 없이 문단이 이어지면 Markdown 이 그 문단을 인용 블록에 흡수한다."""
    if _note_marker(note) in text:
        return text
    span = _frontmatter_span(text, path, label=label)
    if span is None:
        rest = text
        return note + ("" if rest.startswith("\n") else "\n") + rest
    _start, end = span
    line_end = text.find("\n", end)  # 닫는 `---` 줄의 끝 — 파일이 그 줄로 끝나면 줄바꿈이 없다
    close = len(text) if line_end == -1 else line_end + 1
    head = text[:close] if text[:close].endswith("\n") else text[:close] + "\n"
    rest = text[close:]
    return head + "\n" + note + ("" if not rest or rest.startswith("\n") else "\n") + rest


def _is_ancestor(repo: Path, older: str, newer: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", older, newer],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def write_branch(
    repo: Path,
    source: str,
    tree: str,
    branch: str,
    *,
    plugin_root: str,
    commit_details: Callable[[Path, str], tuple[str, str]],
    label: str,
) -> str:
    """Update the edition ref, computing the version and commit message only if needed."""
    ref = f"refs/heads/{branch}"
    prev = _rev(repo, ref)
    if prev:
        parents = _git(repo, "rev-list", "--parents", "-n1", prev, label=label).split()[1:]
        prev_source = parents[-1] if parents else None
        # 원본이 직전 끝의 원본보다 오래됐으면(조상) 되돌리지 않는다 — CI 작업이 push 순서와 다르게
        # 끝나도 판이 옛 트리로 돌아가지 않게(5.9.1 리뷰).
        if prev_source and prev_source != source and _is_ancestor(repo, source, prev_source):
            print(
                f"[{label}] ✓ {branch} 원본 {source[:7]} 은 직전 원본 {prev_source[:7]} 의 조상 — 건너뜀"
            )
            return prev
    # 플러그인 폴더가 같으면 새 커밋을 만들지 않는다.
    if prev and _git(repo, "rev-parse", f"{prev}:{plugin_root}", label=label) == _git(
        repo, "rev-parse", f"{tree}:{plugin_root}", label=label
    ):
        print(f"[{label}] ✓ {branch} 플러그인 폴더 변경 없음 ({prev[:7]})")
        return prev
    version, message = commit_details(repo, source)
    parents_args = ["-p", prev] if prev else []
    commit = _git(repo, "commit-tree", tree, *parents_args, "-p", source, "-m", message, label=label)
    _git(repo, "update-ref", ref, commit, *([prev] if prev else ["0" * 40]), label=label)
    print(f"[{label}] ✓ {branch} → {commit[:7]} (v{version}, 원본 {source[:7]})")
    return commit
