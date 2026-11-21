"""
Hooks 공통 유틸리티

여러 hook 스크립트에서 공통으로 사용하는 함수들을 모아놓은 모듈입니다.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
import traceback

#: 훅을 끄는 스위치. 쉼표 목록(`auto-format,stop-validator`) 또는 `all`.
#: 프로젝트 `.claude/settings.json`(팀)·`settings.local.json`(개인)의 `env` 로 넣는다 —
#: 그 값이 플러그인 훅 프로세스까지 전달됨을 실측했다(2026-11-09, SessionStart·Stop).
DISABLE_ENV = "HIWAY_KIT_DISABLE_HOOKS"

#: ruff 가 읽는 프로젝트 설정. `pyproject.toml` 은 `[tool.ruff` 절이 있을 때만 설정이다.
_RUFF_CONFIGS = ("ruff.toml", ".ruff.toml")
_RUFF_PYPROJECT_RE = re.compile(r"^[ \t]*\[tool\.ruff(?:\.[^\]\n]*)?\][ \t]*(?:#.*)?$", re.MULTILINE)
_PYPROJECT_READ_BYTES = 1024 * 1024
_MAX_CONFIG_DEPTH = 40


def get_project_root() -> str:
    """
    프로젝트 루트 디렉토리 찾기

    우선순위:
    1. CLAUDE_PROJECT_DIR 환경변수
    2. .git 폴더가 있는 상위 디렉토리
    3. 현재 디렉토리
    """
    # 환경변수에서
    if "CLAUDE_PROJECT_DIR" in os.environ:
        return os.environ["CLAUDE_PROJECT_DIR"]

    # 현재 디렉토리에서 .git 찾기
    cwd = os.getcwd()
    while cwd != "/":
        if os.path.exists(os.path.join(cwd, ".git")):
            return cwd
        cwd = os.path.dirname(cwd)

    return os.getcwd()


def is_debug_mode() -> bool:
    """디버그 모드 확인 (CLAUDE_HOOK_DEBUG 환경변수)"""
    return os.environ.get("CLAUDE_HOOK_DEBUG", "").lower() in ("1", "true", "yes")


def debug_log(message: str, error: Exception | None = None):
    """
    디버그 로그 출력

    CLAUDE_HOOK_DEBUG=1 환경변수가 설정된 경우에만 출력됩니다.
    """
    if not is_debug_mode():
        return

    print(f"[DEBUG] {message}", file=sys.stderr)
    if error:
        traceback.print_exc(file=sys.stderr)


def safe_path(file_path: str) -> bool:
    """
    경로 안전성 검사

    Path traversal 공격 방지를 위한 기본 검사.
    경로 컴포넌트 단위로 '..'를 검사하여 'my..file' 같은
    정당한 경로명을 오거부하지 않습니다.
    """
    if not file_path:
        return False

    # 경로 컴포넌트 단위로 '..' 검사 (부분문자열 매칭 우회 방지)
    try:
        parts = pathlib.PurePath(file_path).parts
    except Exception:
        debug_log(f"Path parse error: {file_path}")
        return False

    if ".." in parts:
        debug_log(f"Path traversal detected: {file_path}")
        return False

    return True


def hook_disabled(name: str) -> bool:
    """`HIWAY_KIT_DISABLE_HOOKS` 가 이 훅(파일 이름에서 `.py` 를 뺀 것)을 끄는가."""
    raw = os.environ.get(DISABLE_ENV, "")
    names = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return "all" in names or name.lower() in names


def has_ruff_config(file_path: str) -> bool:
    """파일에서 레포 루트(`.git` 을 가진 디렉토리)까지 ruff 프로젝트 설정이 있는가.

    ruff 는 설정이 없으면 기본 규칙(또는 사용자 전역 설정)으로 돈다. 그 레포가 ruff 를
    쓰기로 한 적이 없는데 포맷·`--fix` 를 하면 손대지 않은 줄까지 바뀐다 — 외부 설치 실측
    (2026-11-09): 설정 없는 PySpark 파일에서 `import os, sys` 가 지워지고 따옴표가 전부 바뀌었다.
    그래서 프로젝트 설정만 동의로 본다(전역 `~/.config/ruff/ruff.toml` 은 동의가 아니다).
    """
    try:
        start = pathlib.Path(file_path).resolve().parent
    except (OSError, RuntimeError, ValueError):
        return False
    for depth, directory in enumerate([start, *start.parents]):
        if depth > _MAX_CONFIG_DEPTH:
            return False
        if any(directory.joinpath(name).is_file() for name in _RUFF_CONFIGS):
            return True
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            try:
                with pyproject.open("rb") as stream:
                    text = stream.read(_PYPROJECT_READ_BYTES).decode("utf-8", errors="replace")
            except OSError:
                text = ""
            if _RUFF_PYPROJECT_RE.search(text):
                return True
        if directory.joinpath(".git").exists():
            return False
    return False
