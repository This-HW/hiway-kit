"""
Hooks 공통 유틸리티

여러 hook 스크립트에서 공통으로 사용하는 함수들을 모아놓은 모듈입니다.
"""
from __future__ import annotations

import os
import pathlib
import sys
import traceback


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
