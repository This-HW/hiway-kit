#!/usr/bin/env python3
"""
PostToolUse Hook: 파일 저장 후 자동 포맷팅 + Lint 피드백

Edit 또는 Write 도구 사용 후 파일 타입에 따라:
1. 자동 수정 (FIX)   - ruff --fix, eslint --fix 등 (토큰 0)
2. 자동 포맷 (FORMAT) - ruff format, prettier 등 (토큰 0)
3. 잔여 에러 피드백   - 수정 불가 에러만 exit 2로 Claude에게 전달

exit 코드:
  0 = 에러 없음 (정상)
  2 = 수정 불가 에러 있음 (Claude에게 피드백 → 수정 유도)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

# 공통 유틸리티 import
hook_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, hook_dir)
try:
    from utils import FORMATTER_TIMEOUT_SECONDS, debug_log, safe_path
except ImportError:

    def debug_log(msg, error=None):
        pass

    def safe_path(path):
        if not path:
            return False
        try:
            from pathlib import PurePath

            return ".." not in PurePath(path).parts
        except Exception:
            return False

    FORMATTER_TIMEOUT_SECONDS = 30

STEP_TIMEOUT = 10

# ESLint config 탐색 최대 깊이 (ATK-004)
_MAX_PARENT_DEPTH = 10

# ESLint config 파일명 목록
_ESLINT_CONFIGS = [
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.json",
    ".eslintrc.yml",
    "eslint.config.js",
]


@lru_cache(maxsize=16)
def _has_tool(tool: str) -> bool:
    """도구 설치 여부 확인 (캐싱)"""
    return shutil.which(tool) is not None


def _validate_path(file_path: str) -> str | None:
    """경로 검증 + 정규화. 안전하면 절대경로 반환, 아니면 None."""
    if not safe_path(file_path):
        debug_log(f"Unsafe path rejected: {file_path}")
        return None

    # 절대경로로 정규화 (ATK-010)
    abs_path = os.path.abspath(file_path)

    # 심볼릭 링크 검증 (ATK-001)
    real_path = os.path.realpath(abs_path)
    if real_path != abs_path:
        debug_log(f"Symlink detected: {abs_path} -> {real_path}")
        return None

    if not os.path.isfile(abs_path):
        debug_log(f"File not found: {abs_path}")
        return None

    return abs_path


def _get_file_dir(file_path: str) -> str:
    """파일의 부모 디렉토리 (subprocess cwd 용)"""
    return str(Path(file_path).parent)


def _has_eslint_config(file_path: str) -> bool:
    """ESLint config 존재 확인 (ATK-005: 공통 함수로 추출)"""
    project_root = Path(file_path).parent
    if any(project_root.joinpath(cfg).exists() for cfg in _ESLINT_CONFIGS):
        return True
    for depth, parent in enumerate(project_root.parents):
        if depth >= _MAX_PARENT_DEPTH:
            break
        if any(parent.joinpath(cfg).exists() for cfg in _ESLINT_CONFIGS):
            return True
        if parent.joinpath(".git").exists():
            break
    return False


# ── Pipeline Steps ────────────────────────────────────────────
# 각 step은 (file_path, feedback_list)를 받음 (ATK-003: 글로벌 변수 제거)


def _ruff_fix(file_path, feedback):
    """ruff check --fix: 자동 수정 가능한 lint 이슈 수정"""
    if not _has_tool("ruff"):
        debug_log("ruff not installed, skipping fix")
        return
    subprocess.run(
        ["ruff", "check", "--fix", "--quiet", file_path],
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT,
        cwd=_get_file_dir(file_path),
        check=False,
    )


def _ruff_format(file_path, feedback):
    """ruff format: 코드 포맷팅 (black 대체)"""
    if not _has_tool("ruff"):
        debug_log("ruff not installed, skipping format")
        return
    result = subprocess.run(
        ["ruff", "format", "--quiet", file_path],
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT,
        cwd=_get_file_dir(file_path),
        check=False,
    )
    if result.returncode == 0:
        print(f"✓ Formatted with ruff: {file_path}")


def _ruff_feedback(file_path, feedback):
    """ruff check: 수정 불가 에러 → Claude 피드백 (exit 2)"""
    if not _has_tool("ruff"):
        return
    result = subprocess.run(
        ["ruff", "check", file_path],
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT,
        cwd=_get_file_dir(file_path),
        check=False,
    )
    if result.returncode != 0 and result.stdout.strip():
        lines = result.stdout.strip().split("\n")[:5]
        feedback.append(
            f"ruff 에러 ({file_path}):\n" + "\n".join(f"  {line}" for line in lines)
        )


def _prettier(file_path, feedback):
    """prettier --write: 포맷팅 (npx --no-install로 supply chain 공격 방지)"""
    if not _has_tool("npx"):
        debug_log("npx not found, skipping prettier")
        return
    result = subprocess.run(
        ["npx", "--no-install", "prettier", "--write", file_path],
        capture_output=True,
        text=True,
        timeout=FORMATTER_TIMEOUT_SECONDS,
        cwd=_get_file_dir(file_path),
        check=False,
    )
    if result.returncode == 0:
        print(f"✓ Formatted with Prettier: {file_path}")
    elif result.stderr.strip():
        debug_log(f"prettier failed: {result.stderr.strip()[:200]}")


def _eslint_fix(file_path, feedback):
    """eslint --fix: 자동 수정 가능한 lint 이슈 수정"""
    if not _has_tool("npx"):
        return
    if not _has_eslint_config(file_path):
        debug_log("No ESLint config found, skipping")
        return
    subprocess.run(
        ["npx", "--no-install", "eslint", "--fix", "--quiet", file_path],
        capture_output=True,
        text=True,
        timeout=FORMATTER_TIMEOUT_SECONDS,
        cwd=_get_file_dir(file_path),
        check=False,
    )


def _eslint_feedback(file_path, feedback):
    """eslint: 수정 불가 에러 → Claude 피드백 (exit 2)"""
    if not _has_tool("npx"):
        return
    if not _has_eslint_config(file_path):
        debug_log("No ESLint config found, skipping feedback")
        return
    result = subprocess.run(
        ["npx", "--no-install", "eslint", "--format=compact", file_path],
        capture_output=True,
        text=True,
        timeout=FORMATTER_TIMEOUT_SECONDS,
        cwd=_get_file_dir(file_path),
        check=False,
    )
    if result.returncode != 0 and result.stdout.strip():
        error_lines = [
            ln for ln in result.stdout.strip().split("\n") if ": error " in ln
        ][:5]
        if error_lines:
            feedback.append(
                f"eslint 에러 ({file_path}):\n"
                + "\n".join(f"  {ln}" for ln in error_lines)
            )


def _gofmt(file_path, feedback):
    """gofmt -w: Go 포맷팅"""
    if not _has_tool("gofmt"):
        debug_log("gofmt not found, skipping")
        return
    result = subprocess.run(
        ["gofmt", "-w", file_path],
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT,
        cwd=_get_file_dir(file_path),
        check=False,
    )
    if result.returncode == 0:
        print(f"✓ Formatted with gofmt: {file_path}")


def _rustfmt(file_path, feedback):
    """rustfmt: Rust 포맷팅"""
    if not _has_tool("rustfmt"):
        debug_log("rustfmt not found, skipping")
        return
    result = subprocess.run(
        ["rustfmt", file_path],
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT,
        cwd=_get_file_dir(file_path),
        check=False,
    )
    if result.returncode == 0:
        print(f"✓ Formatted with rustfmt: {file_path}")


def _shellcheck_feedback(file_path, feedback):
    """shellcheck: .sh 파일 에러 수준 → Claude 피드백 (exit 2)"""
    if not _has_tool("shellcheck"):
        debug_log("shellcheck not installed, skipping")
        return
    result = subprocess.run(
        ["shellcheck", "--severity=error", "--format=gcc", file_path],
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT,
        check=False,
    )
    if result.returncode != 0 and result.stdout.strip():
        lines = result.stdout.strip().split("\n")[:5]
        feedback.append(
            f"shellcheck 에러 ({file_path}):\n"
            + "\n".join(f"  {line}" for line in lines)
        )


# ── Pipeline Definitions ─────────────────────────────────────

PIPELINES = {
    # Python: fix → format → feedback (ruff 공식 순서)
    ".py": [_ruff_fix, _ruff_format, _ruff_feedback],
    # JavaScript/TypeScript: prettier(format) → eslint --fix → eslint feedback
    ".js": [_prettier, _eslint_fix, _eslint_feedback],
    ".jsx": [_prettier, _eslint_fix, _eslint_feedback],
    ".ts": [_prettier, _eslint_fix, _eslint_feedback],
    ".tsx": [_prettier, _eslint_fix, _eslint_feedback],
    # Data/Config: prettier만 (lint 불필요)
    ".json": [_prettier],
    ".yaml": [_prettier],
    ".yml": [_prettier],
    ".md": [_prettier],
    # Go
    ".go": [_gofmt],
    # Rust
    ".rs": [_rustfmt],
    # Shell: feedback (auto-formatter 없음)
    ".sh": [_shellcheck_feedback],
}


def run_pipeline(file_path: str) -> int:
    """파일 확장자에 맞는 파이프라인 실행. 잔여 에러 시 exit 2 반환."""
    validated = _validate_path(file_path)
    if not validated:
        return 0

    ext = Path(validated).suffix.lower()
    pipeline = PIPELINES.get(ext)

    if not pipeline:
        debug_log(f"No pipeline for: {validated}")
        return 0

    feedback = []  # 로컬 변수로 피드백 수집 (ATK-003)

    for step in pipeline:
        try:
            step(validated, feedback)
        except FileNotFoundError:
            debug_log(f"{step.__name__}: tool not installed, skipping")
        except subprocess.TimeoutExpired:
            print(f"⚠ Timeout in {step.__name__}: {validated}", file=sys.stderr)
        except Exception as e:
            debug_log(f"{step.__name__} error: {e}", e)

    if feedback:
        print("\n수정이 필요합니다:", file=sys.stderr)
        for msg in feedback:
            print(msg, file=sys.stderr)
        return 2

    return 0


def main():
    try:
        # stdin이 TTY면 json.load 무한 블록 방지 — 즉시 통과.
        if sys.stdin.isatty():
            sys.exit(0)
        input_data = json.load(sys.stdin)

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        if tool_name not in ("Edit", "Write"):
            sys.exit(0)

        file_path = tool_input.get("file_path", "")
        if not file_path:
            sys.exit(0)

        exit_code = run_pipeline(file_path)
        sys.exit(exit_code)

    except json.JSONDecodeError:
        debug_log("JSON decode error in stdin")
        sys.exit(0)
    except Exception as e:
        debug_log(f"Hook error: {e}", e)
        sys.exit(0)


if __name__ == "__main__":
    main()
