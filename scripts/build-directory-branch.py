#!/usr/bin/env python3
"""build-directory-branch.py — Claude 디렉토리가 추적할 무훅 브랜치(`directory`)를 만든다.

## 왜 있는가

2026-11-06 포털이 v5.6.0 을 거부했다: *"The directory accepts command hooks only from Verified
organizations, and your organization isn't one, so this version is refused. Remove every hook of
type command, then push a new commit."* 킷의 훅은 전부 `type: command` 이고, Verified 조직이 되는
공개 경로는 없다. 그래서 `main`(직접 마켓플레이스 — 훅 포함 완전판)은 그대로 두고, 디렉토리에는
**훅 선언만 뺀 트리**를 별도 브랜치로 준다.

조사용 Validate 실측 `[관측 n=1, 2026-11-06]`: `hooks/hooks.json` 하나만 뺀 트리(`probe-nohook-a`)는
blocking 0. `hooks/` 를 통째로 빼도(`probe-nohook-b`) 자격증명 보류는 근거 파일만 바꿔 남았다 —
그래서 디렉토리째가 아니라 **선언 파일만** 뺀다. 남는 보류는 심사자 확인 경로다(거부 아님).

## 무엇을 만드는가

작업 트리가 아니라 **커밋**(`--source`, 기본 `HEAD`)에서 시작한다. 그 트리에서 `EXCLUDED` 를
뺀 트리로 커밋을 만들어 `refs/heads/<branch>` 에 올린다. 부모는 *직전 브랜치 끝 + 원본 커밋*
이라 브랜치는 fast-forward 로만 자라고, `git log <branch>` 로 어느 `main` 커밋에서 나왔는지
추적된다. 트리가 직전 끝과 같으면 새 커밋을 만들지 않는다. push 는 하지 않는다 — 호출자 몫.

## 검사 조건 (한 문장)

**실행할 때마다(`--check` 포함) 원본 커밋에 `EXCLUDED` 경로가 전부 있는지와, 결과 트리에 훅
선언(`hooks/hooks.json` · 매니페스트 `hooks` 필드)이 남지 않았는지를 확인하고, 하나라도 어긋나면
exit 1.** 뺄 파일이 원본에 없으면 이름이 바뀐 것이다 — 아무것도 빼지 않은 트리를 "무훅"이라
부르지 않는다.

사용:
  scripts/build-directory-branch.py --check              # 결과 트리 sha 만 출력(ref 를 건드리지 않음)
  scripts/build-directory-branch.py --write              # refs/heads/directory 갱신
  scripts/build-directory-branch.py --write --source origin/main
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PLUGIN_ROOT = "plugins/common"
MANIFEST = f"{PLUGIN_ROOT}/.claude-plugin/plugin.json"

#: 디렉토리 브랜치에서 빼는 레포 루트 기준 경로와 사유.
EXCLUDED = {
    f"{PLUGIN_ROOT}/hooks/hooks.json": (
        "Claude Code 가 자동으로 읽는 훅 선언 — 디렉토리는 command 훅을 Verified 조직에게만 받는다"
    ),
}

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


def derive_tree(repo: Path, source: str) -> str:
    """원본 커밋 트리에서 EXCLUDED 를 뺀 트리 sha. 임시 인덱스만 쓴다(작업 트리·인덱스 무변경)."""
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
            "[directory-branch] ✗ 원본에 뺄 파일이 없다 — 이름이 바뀌었으면 EXCLUDED 를 고쳐라: "
            + ", ".join(missing)
        )
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        _git(repo, "read-tree", source, env=env)
        _git(repo, "update-index", "--force-remove", "--", *EXCLUDED, env=env)
        tree = _git(repo, "write-tree", env=env)
    _assert_hookless(repo, tree)
    return tree


def _assert_hookless(repo: Path, tree: str) -> None:
    listed = _git(
        repo, "ls-tree", "-r", "--name-only", tree, "--", f"{PLUGIN_ROOT}/hooks"
    )
    if f"{PLUGIN_ROOT}/hooks/hooks.json" in listed.splitlines():
        sys.exit("[directory-branch] ✗ 결과 트리에 hooks/hooks.json 이 남았다")
    raw = _git(repo, "cat-file", "-p", f"{tree}:{MANIFEST}")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"[directory-branch] ✗ {MANIFEST} 를 JSON 으로 읽지 못했다: {exc}")
    if "hooks" in manifest:
        sys.exit(
            f"[directory-branch] ✗ {MANIFEST} 에 hooks 필드가 있다 — 선언이 남는다"
        )


def write_branch(repo: Path, source: str, tree: str, branch: str) -> str:
    ref = f"refs/heads/{branch}"
    prev = _rev(repo, ref)
    if prev and _git(repo, "rev-parse", f"{prev}^{{tree}}") == tree:
        print(f"[directory-branch] ✓ {branch} 이미 최신 ({prev[:7]})")
        return prev
    version = json.loads(_git(repo, "cat-file", "-p", f"{source}:{MANIFEST}")).get(
        "version", "?"
    )
    parents = ["-p", prev] if prev else []
    message = (
        f"directory: v{version} from {source[:7]}\n\n"
        f"Claude 디렉토리용 트리 — {', '.join(EXCLUDED)} 제외 (scripts/build-directory-branch.py)."
    )
    commit = _git(repo, "commit-tree", tree, *parents, "-p", source, "-m", message)
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
            f"[directory-branch] ✓ 무훅 트리 {tree[:12]} (원본 {source[:7]}, 제외 {len(EXCLUDED)}개)"
        )
        return 0
    write_branch(args.repo, source, tree, args.branch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
