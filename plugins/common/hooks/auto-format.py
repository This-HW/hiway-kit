#!/usr/bin/env python3
"""
PostToolUse Hook: 파일 저장 후 자동 포맷팅 + Lint 피드백

파일을 쓴 도구(Claude Code `Edit`/`MultiEdit`/`Write`, Codex `apply_patch`) 사용 후 파일 타입에 따라:
1. 자동 수정 (FIX)   - ruff --fix, eslint --fix 등 (토큰 0)
2. 자동 포맷 (FORMAT) - ruff format, prettier 등 (토큰 0)
3. 잔여 에러 피드백   - 수정 불가 에러만 exit 2로 Claude에게 전달

**이 훅은 모든 파일 쓰기마다 돈다** — 지연이 곧 사용자가 체감하는 비용이다. 그래서:

- prettier·eslint 는 **프로젝트 로컬 바이너리**(`node_modules/.bin/<tool>`)가 있을 때만
  부른다. `npx --no-install` 은 설치되지 않은 도구에도 npm 을 띄워 레지스트리·캐시를
  뒤진다 — prettier 가 없는 프로젝트의 `.md` 편집 1회가 245ms 였다(v5.0.0 실측).
- ruff 는 파일당 2회(`format` → `check --fix` 가 남은 오류까지 보고).
- 한 번의 호출 전체가 `BUDGET_SECONDS` 안에서 끝난다 — 각 단계의 타임아웃은 남은
  예산으로 깎인다. 훅 타임아웃(hooks.json 30s)을 넘기면 하네스가 훅을 죽이고 그
  사실은 어디에도 남지 않으므로, 넘기기 전에 스스로 멈추고 stderr 에 남긴다.

exit 코드:
  0 = 에러 없음 (정상)
  2 = 수정 불가 에러 있음 (Claude에게 피드백 → 수정 유도)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

# 공통 유틸리티 import
hook_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, hook_dir)
try:
    from utils import debug_log, safe_path
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


#: 단계 하나의 타임아웃 상한(초).
STEP_TIMEOUT = 10
#: 훅 호출 **전체**의 예산(초). hooks.json · hooks-codex.json 의 PostToolUse 타임아웃(30s)
#: 보다 작아야 한다 — 하네스가 죽이기 전에 스스로 멈춰야 그 사실을 남길 수 있다.
BUDGET_SECONDS = 25
#: 남은 예산이 이보다 작으면 다음 단계를 시작하지 않는다.
_MIN_STEP_SECONDS = 1

# 설정·로컬 바이너리 탐색 최대 깊이 (ATK-004)
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


def _ancestors(file_path: str):
    """파일 디렉토리부터 위로 — `.git` 을 가진 디렉토리(레포 루트)에서 멈춘다."""
    start = Path(file_path).parent
    for depth, directory in enumerate([start, *start.parents]):
        if depth > _MAX_PARENT_DEPTH:
            return
        yield directory
        if directory.joinpath(".git").exists():
            return


def _has_eslint_config(file_path: str) -> bool:
    """ESLint config 존재 확인 (ATK-005: 공통 함수로 추출)"""
    return any(
        directory.joinpath(cfg).exists()
        for directory in _ancestors(file_path)
        for cfg in _ESLINT_CONFIGS
    )


def _local_node_bin(file_path: str, tool: str) -> str | None:
    """프로젝트 로컬 `node_modules/.bin/<tool>` — 없으면 None(= 부르지 않는다).

    `npx` 를 쓰지 않는 이유는 모듈 독스트링 참고. 전역 설치본도 쓰지 않는다 — 프로젝트가
    고정하지 않은 버전으로 포맷하면 그 프로젝트의 포맷 규칙과 어긋난 diff 가 생긴다.
    """
    for directory in _ancestors(file_path):
        candidate = directory / "node_modules" / ".bin" / tool
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


# ── Pipeline Steps ────────────────────────────────────────────
# 각 step은 (file_path, feedback_list, timeout)를 받음 (ATK-003: 글로벌 변수 제거).
# timeout 은 호출 예산에서 깎인 값이다 — 단계가 스스로 상수를 쓰지 않는다.


def _ruff(file_path, feedback, timeout):
    """ruff format → ruff check --fix(남은 오류 보고). 파일당 ruff 2회.

    `check --fix` 가 고친 뒤 **남은** 진단을 그대로 출력하므로 별도의 `ruff check`
    재실행이 필요 없다. check 를 **마지막**에 두는 이유: 피드백의 줄 번호가 최종
    파일 기준이어야 모델이 그 줄을 고칠 수 있다(format 이 뒤에 오면 줄이 밀린다).
    대가: fix 가 남긴 공백(지운 import 자리의 빈 줄 등)은 그 파일의 다음 편집 때 정리된다.
    """
    if not _has_tool("ruff"):
        debug_log("ruff not installed, skipping")
        return
    started = time.monotonic()
    result = subprocess.run(
        ["ruff", "format", "--quiet", file_path],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=_get_file_dir(file_path),
        check=False,
    )
    if result.returncode == 0:
        print(f"✓ Formatted with ruff: {file_path}")
    remaining = timeout - (time.monotonic() - started)
    if remaining < _MIN_STEP_SECONDS:
        return
    check = subprocess.run(
        ["ruff", "check", "--fix", "--quiet", "--output-format=concise", file_path],
        capture_output=True,
        text=True,
        timeout=remaining,
        cwd=_get_file_dir(file_path),
        check=False,
    )
    if check.returncode != 0 and check.stdout.strip():
        lines = check.stdout.strip().split("\n")[:5]
        feedback.append(
            f"ruff 에러 ({file_path}):\n" + "\n".join(f"  {line}" for line in lines)
        )


def _prettier(file_path, feedback, timeout):
    """prettier --write — 프로젝트 로컬 바이너리가 있을 때만."""
    prettier = _local_node_bin(file_path, "prettier")
    if prettier is None:
        debug_log("node_modules/.bin/prettier not found, skipping")
        return
    result = subprocess.run(
        [prettier, "--write", file_path],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=_get_file_dir(file_path),
        check=False,
    )
    if result.returncode == 0:
        print(f"✓ Formatted with Prettier: {file_path}")
    elif result.stderr.strip():
        debug_log(f"prettier failed: {result.stderr.strip()[:200]}")


def _eslint(file_path, feedback, timeout):
    """eslint --fix(남은 error 보고) — 로컬 바이너리 + 설정이 있을 때만. 1회 호출."""
    eslint = _local_node_bin(file_path, "eslint")
    if eslint is None:
        debug_log("node_modules/.bin/eslint not found, skipping")
        return
    if not _has_eslint_config(file_path):
        debug_log("No ESLint config found, skipping")
        return
    result = subprocess.run(
        [eslint, "--fix", "--format=compact", file_path],
        capture_output=True,
        text=True,
        timeout=timeout,
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


def _gofmt(file_path, feedback, timeout):
    """gofmt -w: Go 포맷팅"""
    if not _has_tool("gofmt"):
        debug_log("gofmt not found, skipping")
        return
    result = subprocess.run(
        ["gofmt", "-w", file_path],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=_get_file_dir(file_path),
        check=False,
    )
    if result.returncode == 0:
        print(f"✓ Formatted with gofmt: {file_path}")


def _rustfmt(file_path, feedback, timeout):
    """rustfmt: Rust 포맷팅"""
    if not _has_tool("rustfmt"):
        debug_log("rustfmt not found, skipping")
        return
    result = subprocess.run(
        ["rustfmt", file_path],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=_get_file_dir(file_path),
        check=False,
    )
    if result.returncode == 0:
        print(f"✓ Formatted with rustfmt: {file_path}")


def _shellcheck_feedback(file_path, feedback, timeout):
    """shellcheck: .sh 파일 에러 수준 → Claude 피드백 (exit 2)"""
    if not _has_tool("shellcheck"):
        debug_log("shellcheck not installed, skipping")
        return
    result = subprocess.run(
        ["shellcheck", "--severity=error", "--format=gcc", file_path],
        capture_output=True,
        text=True,
        timeout=timeout,
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
    # Python: format → check --fix(+잔여 보고)
    ".py": [_ruff],
    # JavaScript/TypeScript: prettier(format) → eslint --fix(+잔여 보고)
    ".js": [_prettier, _eslint],
    ".jsx": [_prettier, _eslint],
    ".ts": [_prettier, _eslint],
    ".tsx": [_prettier, _eslint],
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


def run_pipeline(file_path: str, deadline: float | None = None) -> int:
    """파일 확장자에 맞는 파이프라인 실행. 잔여 에러 시 exit 2 반환.

    `deadline`(time.monotonic 기준)을 넘기지 않는다. 없으면 이 파일 하나에 예산 전체.
    """
    validated = _validate_path(file_path)
    if not validated:
        return 0

    ext = Path(validated).suffix.lower()
    pipeline = PIPELINES.get(ext)

    if not pipeline:
        debug_log(f"No pipeline for: {validated}")
        return 0

    if deadline is None:
        deadline = time.monotonic() + BUDGET_SECONDS
    feedback = []  # 로컬 변수로 피드백 수집 (ATK-003)

    for step in pipeline:
        remaining = deadline - time.monotonic()
        if remaining < _MIN_STEP_SECONDS:
            print(
                f"⚠ auto-format 예산({BUDGET_SECONDS}s) 소진 — {step.__name__} 이후 생략: "
                f"{validated}",
                file=sys.stderr,
            )
            break
        try:
            step(validated, feedback, min(STEP_TIMEOUT, remaining))
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


# `apply_patch` 패치 봉투에서 **쓰기 대상 파일**을 뽑는 줄 앵커 패턴.
#
# 관대한 패턴을 쓰지 않는 이유: 이 마커를 *설명하는* 텍스트(문서·테스트 픽스처)가
# 패치 본문 안에 diff 로 들어올 수 있고, 관대한 패턴은 그것을 진짜 마커로 오인한다
# (원장 교훈 — 구조 마커는 줄 앵커 + 형식 제약으로 좁힌다). 그래서 `^`/`$` 로 줄
# 전체를 고정하고, diff 본문 줄(` `/`+`/`-` 로 시작)은 구조적으로 매치될 수 없다.
_APPLY_PATCH_TARGET = re.compile(
    r"^\*\*\* (?:Update|Add) File: (.+)$|^\*\*\* Move to: (.+)$",
    re.MULTILINE,
)


def _targets_from_apply_patch(command: str) -> list[str]:
    """Codex `apply_patch` 의 patch 봉투에서 포맷 대상 경로들을 뽑는다.

    `*** Delete File:` 는 제외한다 — 지워진 파일을 포맷할 수 없다.
    `*** Move to:` 는 이동 **후** 경로가 실재하므로 대상이다.
    """
    out: list[str] = []
    for update_or_add, move_to in _APPLY_PATCH_TARGET.findall(command):
        path = (update_or_add or move_to).strip()
        if path and path not in out:
            out.append(path)
    return out


def _targets_from_payload(input_data: dict) -> list[str]:
    """훅 페이로드에서 포맷 대상 파일 경로 목록을 뽑는다 — 하네스 무관.

    두 하네스가 **같은 페이로드 스키마**(`tool_name`/`tool_input`)를 쓰지만 파일을
    쓰는 도구가 다르다 [confirmed: codex-cli 0.153.4 실측, 2026-09-10]:

    - Claude Code — `Edit`/`MultiEdit`/`Write`, 경로는 `tool_input.file_path`
    - Codex — `apply_patch`, 경로는 `tool_input.command` 의 patch 봉투 안

    모르는 도구 이름은 빈 목록이다(no-op). 여기서 도구 이름을 넓게 받으면 그 순간
    "무엇을 보는가"가 흐려진다 — 대상은 실측된 둘뿐이다.
    """
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return []
    if tool_name in ("Edit", "MultiEdit", "Write"):
        file_path = tool_input.get("file_path", "")
        return [file_path] if isinstance(file_path, str) and file_path else []
    if tool_name == "apply_patch":
        command = tool_input.get("command", "")
        return _targets_from_apply_patch(command) if isinstance(command, str) else []
    return []


def main():
    try:
        # stdin이 TTY면 json.load 무한 블록 방지 — 즉시 통과.
        if sys.stdin.isatty():
            sys.exit(0)
        input_data = json.load(sys.stdin)

        targets = _targets_from_payload(input_data)
        if not targets:
            sys.exit(0)

        # apply_patch 는 파일 여럿을 한 호출로 쓴다 — 예산은 파일마다가 아니라 호출 전체다.
        deadline = time.monotonic() + BUDGET_SECONDS
        exit_code = 0
        for file_path in targets:
            if run_pipeline(file_path, deadline) == 2:
                exit_code = 2
        sys.exit(exit_code)

    except json.JSONDecodeError:
        debug_log("JSON decode error in stdin")
        sys.exit(0)
    except Exception as e:
        debug_log(f"Hook error: {e}", e)
        sys.exit(0)


if __name__ == "__main__":
    main()
