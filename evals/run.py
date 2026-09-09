#!/usr/bin/env python3
"""
Agent Evals runner (Spec 2 / W-B, toolkit-improvement-batch).

핵심 에이전트(review-code, fix-bugs, implement-code)의 행동 회귀를 기계로 검증한다.
프롬프트/정의 수정이 품질을 후퇴시켰는지 deterministic 채점(+opt-in LLM-judge)으로
탐지한다. API 비용이 들기 때문에 per-commit CI가 아니라 릴리스 전 필수 게이트로
운영한다(오프라인 스키마 검증만 scripts/verify-done.sh §10에 편입).

stdlib만 사용 — 외부 의존성 추가 금지(zero-debt).

exit code 규율 (false-green 금지 — v2.9.3 교훈):
  0 = 전체 pass (또는 --validate/--dry-run 정상)
  1 = 하나라도 fail, 또는 --compare 시 baseline 대비 후퇴, 또는 스키마 오류
  2 = SKIPPED — claude CLI 부재 등으로 실행 불가. 절대 0으로 위장하지 않는다.

사용:
  python3 evals/run.py --validate              # 오프라인 스키마 검증 (API 불필요)
  python3 evals/run.py --dry-run                # 실행 계획만 출력 (claude 미호출)
  python3 evals/run.py [--agent X] [--scenario Y] [--parallel N] [--timeout SEC]
  python3 evals/run.py --baseline               # 결과를 evals/baseline/<date>.json 저장
  python3 evals/run.py --compare evals/baseline/<date>.json   # 후퇴 시 exit 1 (전량 재실행)
  python3 evals/run.py --compare <baseline> --report evals/reports/<ts>.json  # 재실행 없이 비교

환경 변수:
  CKKIT_EVAL_TIMEOUT   시나리오당 기본 타임아웃(초). override 전용 — 기본값의
                       SSOT는 evals/policy.json의 cost.scenarioTimeoutSeconds다
                       (W-022 R3). 미설정 시 정책 파일 값을 쓴다.
  CKKIT_EVAL_JUDGE=1   opt-in LLM-judge 실행 (deterministic 전부 통과 시에만).
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

EVALS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EVALS_ROOT.parent
AGENTS_ROOT = REPO_ROOT / "plugins" / "common" / "agents"
SCENARIOS_ROOT = EVALS_ROOT / "scenarios"
REPORTS_DIR = EVALS_ROOT / "reports"
BASELINE_DIR = EVALS_ROOT / "baseline"


def _policy_default_timeout() -> int:
    """정책 파일의 timeout이 기본값의 SSOT다(W-022 R3) — 환경변수는 override로만
    남긴다. 실행자마다 다른 기본값으로 스위트를 돌리면 "누구는 통과, 누구는
    타임아웃"이 되는 드리프트가 생긴다 — 이 레포가 계속 잡아온 것과 같은 클래스."""
    try:
        policy = json.loads((EVALS_ROOT / "policy.json").read_text(encoding="utf-8"))
        return int(policy.get("cost", {}).get("scenarioTimeoutSeconds", 300))
    except (OSError, ValueError, json.JSONDecodeError):
        return 300


try:
    DEFAULT_TIMEOUT = int(os.environ["CKKIT_EVAL_TIMEOUT"])
except KeyError:
    DEFAULT_TIMEOUT = _policy_default_timeout()
except ValueError:
    print("[eval] CKKIT_EVAL_TIMEOUT 비정수 — 정책 기본값 사용", file=sys.stderr)
    DEFAULT_TIMEOUT = _policy_default_timeout()

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_SKIPPED = 2

_PYTEST_PY: str | None = None


def resolve_pytest_python() -> str | None:
    """pytest 가용 인터프리터 탐색 (verify-done.sh §4와 동일 순서).

    sys.executable에 pytest가 없을 수 있으므로(시스템 python3) repo venv를
    우선 탐색한다. 없으면 None — 호출부는 이를 '검증 불가'로 명시 처리해야
    하며 green으로 위장해선 안 된다 (false-green 금지).
    """
    global _PYTEST_PY  # noqa: PLW0603 — 프로세스 1회 탐색 결과 메모이제이션
    if _PYTEST_PY is not None:
        return _PYTEST_PY or None
    for cand in (
        str(REPO_ROOT / ".venv" / "bin" / "python"),
        str(REPO_ROOT / "venv" / "bin" / "python"),
        sys.executable,
        "python3",
        # 여기에 /tmp 경로를 후보로 되돌리지 말 것: world-writable + 예측 가능한
        # 이름이라 아무 로컬 사용자나 인터프리터를 심어둘 수 있다. ruff S108이 잡는다.
    ):
        try:
            r = subprocess.run(
                [cand, "-c", "import pytest"],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if r.returncode == 0:
                _PYTEST_PY = cand
                return cand
        except (OSError, subprocess.TimeoutExpired):
            continue
    _PYTEST_PY = ""
    return None


# assertion 타입 계약은 ASSERTION_REGISTRY 한 곳에 있다 (아래 '채점' 절).

# git.json 연산 어휘 -> 필수 필드 (W-023 D-1, config 제거는 D-1 결정log — 화이트리스트
# **안**의 연산만으로 임의 코드 실행이 성립함이 실증됨: filter.<n>.clean 같은 임의 git
# config 값 + .gitattributes(write) + add 만으로 실행 비트 없이 발화한다). 이 8종이 전부다.
# run/exec/clone/fetch/push/remote/submodule/config 등은 의도적으로 없다(임의 셸 실행
# 통로 금지). validate_git_spec의 스키마 검증과 materialize_git_repo의 실행 분기가 이
# SSOT를 공유한다.
ALLOWED_GIT_OPS: dict[str, set[str]] = {
    "init": set(),
    "write": {"path", "content"},
    "add": {"paths"},
    "commit": {"message"},
    "branch": {"name"},
    "checkout": {"ref"},
    "tag": {"name"},
    "merge": {"ref"},
}

# 재현성 고정값 (D-4) — 사용자 전역 git 설정(user.name 미설정, init.defaultBranch 등)이
# 실체화 결과를 실행자마다 다르게 만들지 않도록 매 git 호출에 고정 환경을 준다.
_GIT_FIXED_IDENTITY = {
    "GIT_AUTHOR_NAME": "eval",
    "GIT_AUTHOR_EMAIL": "eval@example.invalid",
    "GIT_COMMITTER_NAME": "eval",
    "GIT_COMMITTER_EMAIL": "eval@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}


# ---------------------------------------------------------------------------
# 에이전트 정의 파싱 (frontmatter + 본문 시스템 프롬프트)
# ---------------------------------------------------------------------------


@dataclass
class AgentDef:
    name: str
    path: Path
    model: str
    tools: list[str]
    disallowed_tools: list[str]
    system_prompt: str


class Harness(Protocol):
    """하네스 결합점 프로토콜 (D-12/§12.4 정정). `run.py`가 특정 CLI에 묶이지
    않도록 3개 결합점 — 시나리오 실행 커맨드·judge 커맨드·가용성 게이트 —
    을 여기로 뽑는다. 리터럴 `"claude"` 문자열은 구현체(`ClaudeCodeHarness`)
    안에만 존재해야 한다."""

    def run_scenario_cmd(self, agent: AgentDef, task: str) -> list[str]:
        """시나리오 실행 CLI 인자 조립. 타임아웃은 호출부 subprocess.run(timeout=)이 강제한다."""

    def judge_cmd(self, prompt: str) -> list[str]:
        """LLM-judge 호출 CLI 인자 조립. judge 모델명도 구현체 소유다."""

    def is_available(self) -> bool:
        """이 하네스의 CLI가 PATH에서 실행 가능한지."""


class ClaudeCodeHarness:
    """유일한 구현체 — Claude Code CLI(`claude`)."""

    def run_scenario_cmd(self, agent: AgentDef, task: str) -> list[str]:
        cmd = [
            "claude",
            "-p",
            task,
            "--model",
            agent.model,
            "--append-system-prompt",
            agent.system_prompt,
            "--permission-mode",
            "bypassPermissions",
            "--output-format",
            "text",
        ]
        if agent.tools:
            cmd += ["--allowedTools", *agent.tools]
        if agent.disallowed_tools:
            cmd += ["--disallowedTools", *agent.disallowed_tools]
        return cmd

    def judge_cmd(self, prompt: str) -> list[str]:
        return ["claude", "-p", prompt, "--model", "sonnet", "--output-format", "text"]

    def is_available(self) -> bool:
        return shutil.which("claude") is not None


HARNESS: Harness = ClaudeCodeHarness()


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """최소 YAML 서브셋 파서. 에이전트 .md의 frontmatter(scalar + 단순 리스트/블록
    스칼라)만 지원한다 — 범용 YAML 파서가 아니다(stdlib-only 제약, 외부 yaml 금지)."""
    if not content.startswith("---"):
        return {}, content
    end = content.find("\n---", 3)
    if end == -1:
        return {}, content
    fm_text = content[3:end]
    body = content[end + 4 :].lstrip("\n")

    fm: dict[str, Any] = {}
    lines = fm_text.split("\n")
    i = 0
    key_re = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = key_re.match(line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val and val not in ("|", "|-", ">"):
            fm[key] = val
            i += 1
            continue
        # 블록(리스트 또는 블록 스칼라) — 다음 들여쓰기 줄들을 소비
        j = i + 1
        block_lines: list[str] = []
        is_list = False
        while j < len(lines) and (lines[j].startswith("  ") or not lines[j].strip()):
            sub = lines[j]
            stripped = sub.strip()
            if stripped.startswith("- "):
                is_list = True
                block_lines.append(stripped[2:].strip())
            elif stripped:
                block_lines.append(sub[2:] if sub.startswith("  ") else stripped)
            else:
                block_lines.append("")
            j += 1
        if is_list:
            fm[key] = [b for b in block_lines if b]
        else:
            fm[key] = "\n".join(block_lines).strip("\n")
        i = j
    return fm, body


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def load_agent(name: str, agents_root: Path = AGENTS_ROOT) -> AgentDef:
    matches = sorted(agents_root.rglob(f"{name}.md"))
    if not matches:
        raise FileNotFoundError(
            f"agent definition not found for '{name}' under {agents_root}"
        )
    path = matches[0]
    content = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    return AgentDef(
        name=name,
        path=path,
        model=str(fm.get("model", "sonnet")),
        tools=_as_list(fm.get("tools")),
        disallowed_tools=_as_list(fm.get("disallowedTools")),
        system_prompt=body.strip(),
    )


# ---------------------------------------------------------------------------
# 시나리오 로딩
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    agent: str
    scenario_id: str
    path: Path
    task: str
    fixture_dir: Path
    expect: dict[str, Any] = field(default_factory=dict)
    # git.json 선언적 명세 (W-023 Stage 0). 없으면 None — 기존 시나리오는 회귀 없이 동작한다.
    git_spec: dict[str, Any] | None = None


def discover_scenario_dirs(
    scenarios_root: Path | None = None,
    agent_filter: str | None = None,
    scenario_filter: str | None = None,
) -> list[Path]:
    # None 기본값 + 모듈 속성을 호출 시점에 읽음 — 테스트가 runner.SCENARIOS_ROOT를
    # monkeypatch할 때도 반영되도록 한다(파라미터 기본값은 정의 시점에 고정되어 버림).
    if scenarios_root is None:
        scenarios_root = SCENARIOS_ROOT
    if not scenarios_root.is_dir():
        return []
    # 로컬 캐시 부산물(.ruff_cache 등)이 유령 에이전트/시나리오로 잡혀
    # 게이트를 무너뜨리지 않게 dot/캐시 디렉토리는 스킵 (재감사 R1/ATK-004).
    skip = {"__pycache__", ".pytest_cache", ".ruff_cache"}
    dirs: list[Path] = []
    for agent_dir in sorted(scenarios_root.iterdir()):
        if (
            not agent_dir.is_dir()
            or agent_dir.name.startswith(".")
            or agent_dir.name in skip
        ):
            continue
        if agent_filter and agent_dir.name != agent_filter:
            continue
        for sc_dir in sorted(agent_dir.iterdir()):
            if (
                not sc_dir.is_dir()
                or sc_dir.name.startswith(".")
                or sc_dir.name in skip
            ):
                continue
            if scenario_filter and sc_dir.name != scenario_filter:
                continue
            dirs.append(sc_dir)
    return dirs


def load_scenario(sc_dir: Path) -> Scenario:
    agent = sc_dir.parent.name
    scenario_id = sc_dir.name
    task_path = sc_dir / "task.md"
    expect_path = sc_dir / "expect.json"
    fixture_dir = sc_dir / "fixture"
    git_spec_path = sc_dir / "git.json"
    task = task_path.read_text(encoding="utf-8") if task_path.is_file() else ""
    expect = (
        json.loads(expect_path.read_text(encoding="utf-8"))
        if expect_path.is_file()
        else {}
    )
    git_spec = (
        json.loads(git_spec_path.read_text(encoding="utf-8"))
        if git_spec_path.is_file()
        else None
    )
    return Scenario(
        agent=agent,
        scenario_id=scenario_id,
        path=sc_dir,
        task=task,
        fixture_dir=fixture_dir,
        expect=expect,
        git_spec=git_spec,
    )


# ---------------------------------------------------------------------------
# 오프라인 스키마 검증 (--validate / verify-done §10)
# ---------------------------------------------------------------------------


def validate_expect_schema(expect: dict, prefix: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(expect, dict):
        return [f"{prefix}: expect.json은 object여야 함"]
    assertions = expect.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        errors.append(
            f"{prefix}: expect.json 'assertions'는 비어있지 않은 배열이어야 함"
        )
        assertions = []
    for i, a in enumerate(assertions):
        if not isinstance(a, dict) or "type" not in a:
            errors.append(f"{prefix}: assertions[{i}]에 'type' 없음")
            continue
        t = a["type"]
        if t not in KNOWN_ASSERTION_TYPES:
            errors.append(f"{prefix}: assertions[{i}] 알 수 없는 type '{t}'")
            continue
        for req_field in KNOWN_ASSERTION_TYPES[t]:
            if req_field not in a:
                errors.append(f"{prefix}: assertions[{i}] ({t})에 '{req_field}' 없음")
    judge = expect.get("judge")
    if judge is not None:
        if not isinstance(judge, dict):
            errors.append(f"{prefix}: 'judge'는 object여야 함")
        elif judge.get("enabled") and "rubric" not in judge:
            errors.append(f"{prefix}: judge.enabled=true인데 'rubric' 없음")
    return errors


def _is_git_internal(rel: str) -> bool:
    """경로가 저장소 메타디렉토리(`.git/`) 안을 가리키는가.

    **왜 _resolve_in_repo 로 부족한가 (W-023 리뷰, Critical).** `_resolve_in_repo` 는 "base 밖으로
    나가는가"만 본다 — `.git/config` 는 base **안**이므로 통과한다. 그런데 거기에 쓰면
    `[filter "x"] clean = <셸 명령>` 을 심을 수 있고, `.gitattributes`(write) + `add` 로
    **실행 비트 없이** 발화한다. 즉 화이트리스트에서 `config` op 을 제거한 조치(D-1)가
    `write` 경유로 무효화된다. 실증: 임시 저장소에서 마커 파일 생성 확인.

    대소문자를 접어 비교한다 — macOS 기본 파일시스템은 대소문자를 구분하지 않아
    `.GIT/config` 가 같은 파일에 도달한다.
    """
    return any(part.casefold() == ".git" for part in pathlib.PurePosixPath(rel).parts)


def validate_git_spec(spec: dict, prefix: str) -> list[str]:
    """git.json 오프라인 스키마 검증 (W-023 D-1/D-2). 실체화(materialize_git_repo) 전에
    구조·화이트리스트·경로 탈출을 잡는다 — `--validate`/게이트 §10이 이 함수로 커버된다.

    `write.path`의 경로 탈출 차단은 여기서도 구조적으로(절대경로·`..`) 걸지만, 유일한
    영구 봉쇄는 materialize_git_repo가 쓰는 _resolve_in_repo이다 — 이 함수는 실행 전 조기
    거부일 뿐, 대체하지 않는다 (D-2: 한 번 resolve하고 그 결과를 끝까지 쓴다).
    """
    errors: list[str] = []
    if not isinstance(spec, dict):
        return [f"{prefix}: git.json은 object여야 함"]
    if spec.get("version") != 1:
        errors.append(
            f"{prefix}: git.json 'version'은 1이어야 함 (got {spec.get('version')!r})"
        )
    ops = spec.get("ops")
    if not isinstance(ops, list) or not ops:
        errors.append(f"{prefix}: git.json 'ops'는 비어있지 않은 배열이어야 함")
        ops = []
    for i, op_entry in enumerate(ops):
        if not isinstance(op_entry, dict) or "op" not in op_entry:
            errors.append(f"{prefix}: git.json ops[{i}]에 'op' 없음")
            continue
        op = op_entry["op"]
        if op not in ALLOWED_GIT_OPS:
            errors.append(
                f"{prefix}: git.json ops[{i}] 알 수 없는 op '{op}' (화이트리스트 밖 — "
                f"허용: {sorted(ALLOWED_GIT_OPS)})"
            )
            continue
        for req_field in ALLOWED_GIT_OPS[op]:
            if req_field not in op_entry:
                errors.append(
                    f"{prefix}: git.json ops[{i}] ({op})에 '{req_field}' 없음"
                )
        if op == "write":
            path = op_entry.get("path")
            if isinstance(path, str):
                p = Path(path)
                if p.is_absolute() or ".." in p.parts:
                    errors.append(
                        f"{prefix}: git.json ops[{i}] write.path 경로 탈출/절대경로 "
                        f"금지: {path!r}"
                    )
                elif _is_git_internal(path):
                    errors.append(
                        f"{prefix}: git.json ops[{i}] write.path 가 저장소 메타디렉토리"
                        f"(.git/)를 가리킴 — 금지: {path!r}"
                    )
    return errors


# fixture 모듈 스코프 위험 호출 판정 (AST 우선 + 정규식 폴백)
#
# 판정 원칙: **import 시 실제로 실행되는 위치**만 본다.
#   실행됨   — 모듈 최상위 문장, 클래스 본문, 데코레이터 표현식, 기본 인자 값
#   실행 안 됨 — 함수/메서드 **본문**
# 함수든 클래스든 통째로 스킵하면 위 셋이 전부 새어나간다(2026-08-23 적대적 리뷰가
# 클래스 본문·데코레이터·기본인자 우회를 실증했다).
# 모듈 등급 2단:
#   ANY  — 이 모듈의 **어떤 호출이든** 모듈 스코프에서는 위험 (프로세스/네트워크/동적 import)
#   ATTR — 위험한 **속성 이름일 때만** 위험. `os.path.join`·`shutil.which`·`urlparse` 같은
#          정상 사용을 막지 않기 위해 필요하다(1단 블록리스트는 이들을 오탐했다).
_ANY_CALL_DANGER = frozenset({"subprocess", "socket", "requests", "importlib"})
_ATTR_CALL_DANGER = frozenset({"os", "shutil", "urllib"})
_DANGER_MODULES = _ANY_CALL_DANGER | _ATTR_CALL_DANGER
# 이름만으로 위험한 호출 (from-import 되어 모듈 접두어가 사라진 경우)
_DANGER_NAMES = frozenset(
    {
        "system",
        "popen",
        "execv",
        "execve",
        "execl",
        "execlp",
        "spawnv",
        "spawnl",
        "remove",
        "unlink",
        "rmdir",
        "removedirs",
        "rmtree",
        "kill",
        "urlopen",
    }
)
# 빌트인: 임의 실행·동적 해석 통로만. `open`/`input`/`compile`은 **넣지 않는다** —
# 모듈 스코프에서 데이터를 읽는 정상 fixture를 막아버린다(오탐으로 실증됨).
_DANGER_BUILTINS = frozenset({"eval", "exec", "__import__", "getattr", "setattr"})
_DANGER_DYNAMIC = frozenset({"importlib"})
_DANGER_RE = re.compile(
    r"^(?!\s)(?:.*\b(?:os\.system|subprocess\.|socket\.|eval\(|exec\(|__import__)\b)"
)


def _danger_ref(node: ast.AST) -> tuple[str | None, str | None]:
    """참조 표현식에서 (최상위 이름, 마지막 속성)을 뽑는다.

    `os.system` → ("os", "system") · `os.path.join` → ("os", "join") · `f` → ("f", None)
    `getattr(os,"x")("id")` 처럼 호출이 중첩되면 안쪽으로 내려간다.
    """
    f = node.func if isinstance(node, ast.Call) else node
    last = f.attr if isinstance(f, ast.Attribute) else None
    while isinstance(f, ast.Attribute):
        f = f.value
    if isinstance(f, ast.Name):
        return f.id, last
    if isinstance(f, ast.Call):
        root, inner = _danger_ref(f)
        return root, last or inner
    return None, last


def _collect_aliases(tree: ast.AST) -> tuple[dict, dict, list]:
    """import 별칭과 위험 재바인딩을 추적한다.

    `import os as x` / `from os import system` / `f = os.system` / `from os import *`
    — 전부 모듈 접두어를 지우거나 바꿔서 단순 부분문자열 검사를 무력화하는 경로다.
    """
    alias_mod: dict[str, str] = {}  # 별칭 → 원본 모듈
    alias_name: dict[str, str] = {}  # 별칭 → "module.name"
    star_imports: list[str] = []  # `from X import *` 의 X
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                alias_mod[a.asname or a.name.split(".")[0]] = a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            for a in node.names:
                if a.name == "*":
                    star_imports.append(mod)
                else:
                    alias_name[a.asname or a.name] = f"{mod}.{a.name}"
        elif isinstance(node, ast.Assign):
            # `f = os.system` 재바인딩 — 대입 자체는 Call이 아니라 별도로 잡는다.
            target = node.targets[0] if node.targets else None
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Attribute):
                base = node.value.value
                if isinstance(base, ast.Name):
                    origin = alias_mod.get(base.id, base.id)
                    if origin in _DANGER_MODULES or node.value.attr in _DANGER_NAMES:
                        alias_name[target.id] = f"{origin}.{node.value.attr}"
    return alias_mod, alias_name, star_imports


def _executed_at_import(tree: ast.Module) -> list[ast.AST]:
    """import 시 실제로 평가되는 노드만 모은다."""
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 본문은 실행되지 않지만 데코레이터와 기본 인자 값은 실행된다.
            out.extend(node.decorator_list)
            out.extend(d for d in node.args.defaults if d is not None)
            out.extend(
                d for d in getattr(node.args, "kw_defaults", []) if d is not None
            )
            continue
        if isinstance(node, ast.ClassDef):
            # 클래스 **본문은 import 시 실행된다**.
            out.extend(node.decorator_list)
            out.extend(node.bases)
            stack.extend(node.body)
            continue
        out.append(node)
    return out


def _module_scope_danger(src: str) -> list[str]:
    """모듈 스코프(=import 시 실행되는 위치)의 위험 호출 목록."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        # 파싱 불가 = 검사 불가. 통과로 삼지 않는다 (NUL 바이트는 ValueError를 던진다 —
        # 이걸 안 잡으면 --validate 전체가 트레이스백으로 죽는다).
        return [ln.strip()[:60] for ln in src.splitlines() if _DANGER_RE.match(ln)] or [
            "구문 오류로 AST 검사 불가"
        ]

    alias_mod, alias_name, star_imports = _collect_aliases(tree)
    hits: list[str] = []

    # `from os import *` 는 이름이 통째로 쏟아져 들어와 추적이 불가능하다 — 거부한다.
    for mod in star_imports:
        if mod in _DANGER_MODULES:
            hits.append(f"from {mod} import * (별칭 추적 불가 — 명시 import를 쓰라)")

    for node in _executed_at_import(tree):
        for sub in ast.walk(node):
            # 데코레이터는 `@os.popen` 처럼 **Call이 아닌 참조**로도 쓰이고, 그때도
            # import 시 평가·적용된다. Call만 보면 이 경로가 통째로 샌다.
            if not isinstance(sub, (ast.Call, ast.Attribute, ast.Name)):
                continue
            if isinstance(sub, (ast.Attribute, ast.Name)) and not _is_decorator(
                sub, node
            ):
                continue
            root, last = _danger_ref(sub)
            if root is None:
                continue
            if _is_dangerous(root, last, alias_mod, alias_name):
                hits.append(f"line {getattr(sub, 'lineno', '?')}: {root}(...)")
    return hits


def _is_decorator(node: ast.AST, parent: ast.AST) -> bool:
    """`_executed_at_import`가 데코레이터 표현식을 그대로 넘겨준다 — 그 자신인지 확인."""
    return node is parent


def _is_dangerous(
    root: str, last: str | None, alias_mod: dict, alias_name: dict
) -> bool:
    origin = alias_mod.get(root)
    imported = alias_name.get(root)
    if root in _DANGER_BUILTINS or root in _DANGER_DYNAMIC or origin in _DANGER_DYNAMIC:
        return True
    if origin in _ANY_CALL_DANGER:
        return True
    if origin in _ATTR_CALL_DANGER:
        # `os.path.join`은 통과, `os.system`은 차단.
        return last in _DANGER_NAMES
    if imported is not None:
        head, tail = imported.split(".")[0], imported.split(".")[-1]
        if head in _ANY_CALL_DANGER:
            return True
        return tail in _DANGER_NAMES
    return False


def validate_scenario(sc_dir: Path, agents_root: Path = AGENTS_ROOT) -> list[str]:
    errors: list[str] = []
    agent_name = sc_dir.parent.name
    scenario_id = sc_dir.name
    prefix = f"{agent_name}/{scenario_id}"

    task_path = sc_dir / "task.md"
    fixture_dir = sc_dir / "fixture"
    expect_path = sc_dir / "expect.json"

    if not task_path.is_file():
        errors.append(f"{prefix}: task.md 없음")
    if not fixture_dir.is_dir():
        errors.append(f"{prefix}: fixture/ 없음")
    else:
        # 보안(ATK-002 보강): pytest는 수집 시 conftest.py를 자동 실행한다 —
        # fixture에 conftest가 있으면 채점 단계에서 임의 코드 실행이 가능해 금지.
        for bad in fixture_dir.rglob("conftest.py"):
            errors.append(f"{prefix}: fixture에 conftest.py 금지 ({bad.name})")
        # 모듈 스코프 부작용 차단 (재감사 R2/ATK-003): fixture는 stop-validator
        # 검증에서 제외되므로, import-time에 실행되는 위험 호출을 여기서 거부한다.
        #
        # 1차는 AST다. 이전에는 정규식 부분문자열 블록리스트뿐이었고, 그건 **별칭으로
        # 뚫린다** — `import os as x; x.system("id")`, `from os import system;
        # system("id")`가 전부 통과했다(2026-08-23 보안 점검 실증). AST는 import 별칭을
        # 따라가므로 그 경로를 닫는다. 정규식은 파싱 불가(SyntaxError) 파일에 대한
        # 2차 방어로 남긴다 — 검사 불가를 통과로 삼지 않기 위해서다.
        for py in sorted(fixture_dir.rglob("*.py")):
            src = py.read_text(encoding="utf-8", errors="replace")
            for hit in _module_scope_danger(src):
                errors.append(
                    f"{prefix}: fixture 모듈 스코프에 위험 호출 금지 ({py.name}: {hit})"
                )
    # scenario 디렉토리에 fixture 밖 .py 금지 (재감사 R2/ATK-005): stop-validator의
    # evals/scenarios/ 제외가 실코드를 은닉하는 통로가 되지 않게 구조로 강제.
    for stray in sorted(sc_dir.glob("*.py")):
        errors.append(
            f"{prefix}: 시나리오 루트에 .py 금지 ({stray.name}) — 코드는 fixture/ 안에만"
        )
    if not expect_path.is_file():
        errors.append(f"{prefix}: expect.json 없음")
        return errors

    try:
        expect = json.loads(expect_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"{prefix}: expect.json 파싱 실패 ({e})")
        return errors

    errors += validate_expect_schema(expect, prefix)

    git_spec_path = sc_dir / "git.json"
    if git_spec_path.is_file():
        try:
            git_spec = json.loads(git_spec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{prefix}: git.json 파싱 실패 ({e})")
        else:
            errors += validate_git_spec(git_spec, prefix)
            # file_unchanged는 실행 후 파일을 **원본 fixture**와 바이트 비교한다.
            # 그런데 git.json의 write는 실체화 단계에서 같은 파일을 덮어쓰므로,
            # 둘이 겹치면 에이전트가 아무것도 하지 않아도 영구 fail이고 실패
            # 메시지는 "변조됨 (게이밍 의심)"이라 원인을 정반대로 오도한다
            # (W-023 리뷰 W-5). 조합 자체를 스키마 오류로 막는다.
            written = {
                str(op.get("path"))
                for op in git_spec.get("ops", [])
                if isinstance(op, dict) and op.get("op") == "write"
            }
            for a in expect.get("assertions", []):
                if isinstance(a, dict) and a.get("type") == "file_unchanged":
                    f = str(a.get("file"))
                    if f in written:
                        errors.append(
                            f"{prefix}: file_unchanged '{f}' 가 git.json write 대상과 "
                            f"겹침 — 실체화가 원본을 덮어써 영구 fail이 된다"
                        )

    if not list(agents_root.rglob(f"{agent_name}.md")):
        errors.append(
            f"{prefix}: 알 수 없는 agent '{agent_name}' ({agents_root} 하위에 대응 .md 없음)"
        )

    return errors


def validate_all(
    scenarios_root: Path | None = None,
    agents_root: Path | None = None,
    agent_filter: str | None = None,
    scenario_filter: str | None = None,
) -> list[str]:
    # None 기본값 + 모듈 속성을 호출 시점에 읽음 — patch.object(runner, "SCENARIOS_ROOT", ...)
    # 로 테스트가 오버라이드할 때도 반영되도록 한다.
    if scenarios_root is None:
        scenarios_root = SCENARIOS_ROOT
    if agents_root is None:
        agents_root = AGENTS_ROOT
    if not scenarios_root.is_dir():
        # fail-closed — evals/ 부재를 조용한 green으로 위장하지 않는다.
        return [f"scenarios root 없음: {scenarios_root}"]
    dirs = discover_scenario_dirs(
        scenarios_root, agent_filter=agent_filter, scenario_filter=scenario_filter
    )
    if not dirs:
        return [f"scenarios root에 시나리오 없음(필터 포함): {scenarios_root}"]
    errors: list[str] = []
    for sc_dir in dirs:
        errors += validate_scenario(sc_dir, agents_root)
    return errors


# ---------------------------------------------------------------------------
# git.json 실체화 (W-023 Stage 0 — D-1~D-4)
# ---------------------------------------------------------------------------


def _git_env() -> dict[str, str]:
    """고정 커밋 작성자/시각(D-4) — 사용자 전역 git 설정에 결과가 좌우되지 않는다."""
    env = os.environ.copy()
    env.update(_GIT_FIXED_IDENTITY)
    return env


# git 실체화 한 명령의 상한. 없으면 자격증명 프롬프트·파일 잠금에서 **스위트가 무한
# 대기한다** — run_scenario의 timeout은 claude 호출에만 걸려 있어 여기를 덮지 않는다
# (W-023 리뷰 W-6).
_GIT_OP_TIMEOUT_SECONDS = 60


def _reject_option_like(value: str, where: str) -> None:
    """`-`로 시작하는 author-제어 값을 거부한다 (W-023 리뷰 C-2).

    화이트리스트가 "연산 8종"을 제한해도 **전달 인자가 무제한이면 보안 주장이
    성립하지 않는다**. `_check_git_assertion`은 ref/branch에 이미 이 경계를 세웠는데
    실체화 경로에는 없었다 — 같은 파일 안의 방어 비대칭이었다.

    `--` 종결자와 병행한다(종결자만으로는 `git branch <name>`처럼 종결자를 받지 않는
    서브커맨드를 못 막는다).
    """
    if not isinstance(value, str) or value.startswith("-"):
        raise RuntimeError(f"git.json {where} 옵션 주입 의심 값 거부: {value!r}")


def _git_args_for(op_entry: dict) -> list[str] | None:
    """op 하나를 git 인자 리스트로 조립한다 — **순수 함수, 부수효과 없음**.

    실행(_run_git)과 조립을 분리해 새니타이즈를 단위 테스트할 수 있게 한다
    (W-023 리뷰 S-4). `write`는 git 명령이 아니므로 None을 반환한다.
    """
    op = op_entry["op"]
    if op == "init":
        branch = str(op_entry.get("defaultBranch", "main"))
        _reject_option_like(branch, "init.defaultBranch")
        return ["init", "-q", "-b", branch]
    if op == "add":
        paths = [str(x) for x in op_entry["paths"]]
        for x in paths:
            _reject_option_like(x, "add.paths[]")
        return ["add", "--", *paths]
    if op == "commit":
        # -m 뒤 값은 위치상 옵션으로 해석되지 않으므로 종결자 불필요.
        return ["commit", "-q", "-m", str(op_entry["message"])]
    if op == "branch":
        name = str(op_entry["name"])
        _reject_option_like(name, "branch.name")
        return ["branch", name]
    if op == "checkout":
        ref = str(op_entry["ref"])
        _reject_option_like(ref, "checkout.ref")
        return ["checkout", "-q", ref, "--"]
    if op == "tag":
        name = str(op_entry["name"])
        _reject_option_like(name, "tag.name")
        return ["tag", name]
    if op == "merge":
        ref = str(op_entry["ref"])
        _reject_option_like(ref, "merge.ref")
        return ["merge", "--no-edit", ref]
    return None


def _run_git(work_dir: Path, args: list[str]) -> None:
    """`git -C work_dir` 고정 — cwd 상대경로에 의존하지 않는다 (D-2).

    gpgsign은 명령별로 끈다(-c commit.gpgsign=false) — 사용자 전역 설정이
    commit.gpgsign=true면 서명 프롬프트로 실체화가 멈춘다 (D-4).
    """
    try:
        r = subprocess.run(
            ["git", "-C", str(work_dir), "-c", "commit.gpgsign=false", *args],
            capture_output=True,
            text=True,
            env=_git_env(),
            timeout=_GIT_OP_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"git {' '.join(args)} 타임아웃 ({_GIT_OP_TIMEOUT_SECONDS}s)"
        ) from e
    if r.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} 실패 (exit {r.returncode}): {r.stderr.strip()[:300]}"
        )


def materialize_git_repo(work_dir: Path, spec: dict) -> None:
    """git.json 선언적 명세를 work_dir(temp fixture 작업 디렉토리)에 실체화한다.

    화이트리스트(ALLOWED_GIT_OPS) 밖의 op는 이 함수가 아니라 validate_git_spec이
    먼저 걸러야 정상이지만, 방어적으로 여기서도 거부한다(fail-closed, D-3) —
    검증을 거치지 않고 이 함수를 직접 호출하는 경로(단위 테스트 등)가 있을 수 있다.

    `write.path`는 반드시 _resolve_in_repo(work_dir, path)을 통과해야 한다 — 한 번
    resolve하고 그 결과(target)를 끝까지 쓴다. 검사와 사용이 각각 resolve하면
    그 틈이 TOCTOU다 (D-2, CLAUDE.md "설정값으로 경로를 만들면 반드시 봉쇄한다").

    실패하면 예외를 던진다 — 호출부(run_scenario)가 'error'로 분리해 어서션
    채점에 들어가지 않게 한다 (D-3 fail-closed).
    """
    for op_entry in spec.get("ops", []):
        op = op_entry.get("op")
        if op not in ALLOWED_GIT_OPS:
            raise RuntimeError(f"git.json 알 수 없는 op '{op}' (화이트리스트 밖)")
        if op == "write":
            raw_path = op_entry["path"]
            # `.git/` 봉쇄가 _resolve_in_repo 보다 **먼저**다 — _resolve_in_repo 는 base 밖으로
            # 나가는 것만 막고 `.git/config` 는 base 안이라 통과시킨다 (리뷰 C-1).
            if _is_git_internal(raw_path):
                raise RuntimeError(
                    f"git.json write.path 저장소 메타디렉토리(.git/) 쓰기 차단: {raw_path!r}"
                )
            target = _resolve_in_repo(work_dir, raw_path)
            if target is None:
                raise RuntimeError(f"git.json write.path 경로 탈출 차단: {raw_path!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(op_entry["content"], encoding="utf-8")
            continue
        args = _git_args_for(op_entry)
        if args is None:  # pragma: no cover - 화이트리스트와 조립기가 어긋난 경우
            raise RuntimeError(f"git.json op '{op}' 인자 조립기 없음 (러너 버그)")
        _run_git(work_dir, args)


# ---------------------------------------------------------------------------
# 채점 (deterministic assertions)
# ---------------------------------------------------------------------------


def _norm(s: str) -> str:
    # NFC 정규화 — NFD(자모 분해) 출력과 NFC expect 값의 코드포인트 불일치로 인한
    # 한글 false-red 방지 (재감사 R1/ATK-006). stdlib unicodedata — zero-debt.
    return unicodedata.normalize("NFC", s).lower()


def _resolve_in_repo(base: Path, rel: str) -> Path | None:
    """author-제어 상대경로를 base 밖으로 못 나가게 정규화 (ATK-012 경로 탈출 가드)."""
    p = (base / rel).resolve()
    return p if p.is_relative_to(base.resolve()) else None


def _check_output_regex(
    a: dict, stdout: str, fx: Path, src_fx: Path | None
) -> tuple[bool, str]:
    flags = 0
    for ch in a.get("flags", ""):
        flags |= {"i": re.IGNORECASE, "s": re.DOTALL, "m": re.MULTILINE}.get(ch, 0)
    pattern = a["pattern"]
    ok = re.search(pattern, stdout, flags) is not None
    return ok, f"output_regex '{pattern}'" + ("" if ok else " — 매치 없음")


def _check_output_contains_any(
    a: dict, stdout: str, fx: Path, src_fx: Path | None
) -> tuple[bool, str]:
    values = a.get("values", [])
    low = _norm(stdout)
    ok = any(_norm(v) in low for v in values)
    return ok, f"output_contains_any {values}" + ("" if ok else " — 하나도 없음")


def _check_output_not_contains(
    a: dict, stdout: str, fx: Path, src_fx: Path | None
) -> tuple[bool, str]:
    values = a.get("values", [])
    low = _norm(stdout)
    hit = [v for v in values if _norm(v) in low]
    ok = not hit
    return ok, "output_not_contains" + ("" if ok else f" — 발견됨 {hit}")


def _check_pytest_green(
    a: dict, stdout: str, fx: Path, src_fx: Path | None
) -> tuple[bool, str]:
    rel = a.get("path", ".")
    target = _resolve_in_repo(fx, rel)
    if target is None:
        return False, f"pytest_green — 경로 탈출 차단: {rel}"
    py = resolve_pytest_python()
    if py is None:
        # pytest 부재 = 검증 불가. green 위장 금지 — 명시적 실패로 드러낸다.
        return (
            False,
            "pytest_green — pytest 인터프리터 없음 (검증 불가, .venv 확인)",
        )
    try:
        r = subprocess.run(
            [py, "-m", "pytest", str(target), "-q", "-p", "no:cacheprovider"],
            cwd=str(fx),
            capture_output=True,
            text=True,
            timeout=int(a.get("timeout", 120)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        # 무한루프 fixture 하나가 전체 런을 크래시시키지 않게 fail로 강등 (ATK-003).
        return False, "pytest_green — pytest 타임아웃"
    ok = r.returncode == 0
    return ok, "pytest_green" + (
        "" if ok else f" — exit {r.returncode}: {r.stdout[-400:]} {r.stderr[-200:]}"
    )


def _check_file_contains(
    a: dict, stdout: str, fx: Path, src_fx: Path | None
) -> tuple[bool, str]:
    f = _resolve_in_repo(fx, a["file"])
    if f is None:
        return False, f"file_contains — 경로 탈출 차단: {a['file']}"
    if not f.is_file():
        return False, f"file_contains — 파일 없음 {a['file']}"
    content = f.read_text(encoding="utf-8")
    # MULTILINE 기본 적용 (W-018 S3 실측): 이게 없으면 '^'/'$'가 파일 전체의
    # 시작/끝에만 매치해, frontmatter처럼 구분선 뒤에 오는 필드를 앵커링하는
    # 흔한 패턴이 실제로 false-fail을 냈다(2026-08-26 실측). 인라인 `(?m)`
    # 워크어라운드가 이미 있던 시나리오는 중복 지정이라도 무해하다.
    ok = re.search(a["pattern"], content, re.MULTILINE) is not None
    return ok, "file_contains" + ("" if ok else " — 패턴 없음")


def _check_file_unchanged(
    a: dict, stdout: str, fx: Path, src_fx: Path | None
) -> tuple[bool, str]:
    # 채점 게이밍 방지(ATK-006): 에이전트가 테스트 파일을 고쳐 green을 만드는
    # 우회를 차단 — 실행 후 파일이 원본 fixture와 byte-동일해야 통과.
    rel_f = a["file"]
    cur = _resolve_in_repo(fx, rel_f)
    if cur is None:
        return False, f"file_unchanged — 경로 탈출 차단: {rel_f}"
    if src_fx is None:
        return False, "file_unchanged — 원본 fixture 참조 없음 (러너 버그)"
    orig = _resolve_in_repo(src_fx, rel_f)
    if orig is None or not orig.is_file():
        return False, f"file_unchanged — 원본에 없는 파일 {rel_f}"
    if not cur.is_file():
        return False, f"file_unchanged — 실행 후 파일 삭제됨 {rel_f}"
    ok = cur.read_bytes() == orig.read_bytes()
    return ok, "file_unchanged" + ("" if ok else f" — {rel_f} 변조됨 (게이밍 의심)")


def _check_git_assertion(
    assertion: dict, t: str, fixture_dir: Path
) -> tuple[bool, str]:
    """git 상태 어서션 3종 채점 (W-023 D-5). fixture_dir은 run_scenario가 넘기는
    실행 후 temp work_dir — materialize_git_repo가 이미 저장소를 만들어 둔 상태다.

    ref/branch는 author 제어 문자열이다. `-`로 시작하는 값은 git이 옵션으로
    오인할 수 있어(옵션 주입) 거부한다 — shell=True는 쓰지 않지만 리스트 인자
    자체가 신뢰 경계다.
    """
    expect_ok = bool(assertion.get("expect", True))
    timeout_s = int(assertion.get("timeout", 30))

    if t == "git_log_contains":
        ref = assertion.get("ref", "HEAD")
        if not isinstance(ref, str) or ref.startswith("-"):
            return (
                False,
                f"git_log_contains — 유효하지 않은 ref(옵션 주입 의심): {ref!r}",
            )
        args = ["log", "--format=%B", ref]
    elif t == "git_branch_exists":
        branch = assertion["branch"]
        if not isinstance(branch, str) or branch.startswith("-"):
            return (
                False,
                f"git_branch_exists — 유효하지 않은 branch(옵션 주입 의심): {branch!r}",
            )
        args = ["branch", "--list", "--format=%(refname:short)"]
    else:  # git_status_clean
        args = ["status", "--porcelain"]

    try:
        r = subprocess.run(
            ["git", "-C", str(fixture_dir), *args],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # 무한대기 하나가 전체 런을 크래시시키지 않게 fail로 강등 (ATK-003 관례).
        return False, f"{t} — git 명령 타임아웃"

    if r.returncode != 0:
        # 비-저장소(또는 다른 git 실패)는 항상 명시적 fail이다. "porcelain이 비어
        # 있으니 clean"으로 오독하면 저장소 없는 상태가 통과로 위장되는 거짓
        # green이 된다 — 이 분기가 그 오독을 막는다.
        return (
            False,
            f"{t} — git 명령 실패(비-저장소 가능성, exit {r.returncode}): "
            f"{r.stderr.strip()[:200]}",
        )

    if t == "git_log_contains":
        matched = re.search(assertion["pattern"], r.stdout, re.MULTILINE) is not None
    elif t == "git_branch_exists":
        branches = {ln.strip() for ln in r.stdout.splitlines() if ln.strip()}
        matched = assertion["branch"] in branches
    else:  # git_status_clean
        matched = r.stdout.strip() == ""

    ok = matched == expect_ok
    return ok, t + ("" if ok else f" — expect={expect_ok} actual={matched}")


# ─────────────────────────────────────────────────────────────────────────────
# 어서션 계약 레지스트리 — **한 곳뿐** (D-13 / 25-7)
#
# 이전에는 필수 필드표(KNOWN_ASSERTION_TYPES)와 채점 if-체인이 **두 곳에** 있었고
# 동기화를 강제하는 것이 없었다. 실패 모드가 fail-closed 라 안 물렸을 뿐이다.
# 이제 스키마 검증과 디스패치가 이 표 하나를 읽는다 — 타입 추가는 여기 한 줄이다.
# ─────────────────────────────────────────────────────────────────────────────
def _git_checker(t: str):
    def _run(a: dict, stdout: str, fx: Path, src_fx: Path | None) -> tuple[bool, str]:
        return _check_git_assertion(a, t, fx)

    return _run


ASSERTION_REGISTRY: dict[str, tuple[set[str], object]] = {
    "output_regex": ({"pattern"}, _check_output_regex),
    "output_contains_any": ({"values"}, _check_output_contains_any),
    "output_not_contains": ({"values"}, _check_output_not_contains),
    "pytest_green": ({"path"}, _check_pytest_green),
    "file_contains": ({"file", "pattern"}, _check_file_contains),
    "file_unchanged": ({"file"}, _check_file_unchanged),
    # git 상태 어서션 3종 (W-023 D-5). expect:false로 부정을 표현한다 —
    # *_not_* 타입은 만들지 않는다(타입 표가 읽기 어려워지면 시나리오 작성자가
    # 틀린 타입을 고른다).
    "git_log_contains": ({"pattern"}, _git_checker("git_log_contains")),
    "git_branch_exists": ({"branch"}, _git_checker("git_branch_exists")),
    "git_status_clean": (set(), _git_checker("git_status_clean")),
}

# 스키마 검증이 쓰는 뷰. 레지스트리에서 **파생**되므로 따로 유지하지 않는다.
KNOWN_ASSERTION_TYPES: dict[str, set[str]] = {
    k: v[0] for k, v in ASSERTION_REGISTRY.items()
}


def check_assertion(
    assertion: dict,
    stdout: str,
    fixture_dir: Path,
    source_fixture: Path | None = None,
) -> tuple[bool, str]:
    entry = ASSERTION_REGISTRY.get(assertion.get("type"))
    if entry is None:
        return False, f"알 수 없는 assertion type: {assertion.get('type')}"
    return entry[1](assertion, stdout, fixture_dir, source_fixture)


# ---------------------------------------------------------------------------
# LLM-judge (opt-in, deterministic 전부 통과 시에만)
# ---------------------------------------------------------------------------


def run_judge(stdout: str, judge_cfg: dict, timeout: int) -> dict:
    rubric = judge_cfg.get("rubric", "")
    threshold = judge_cfg.get("threshold", 7)
    prompt = (
        "다음은 AI 에이전트의 출력입니다. 아래 rubric에 따라 0~10점으로 채점하고 "
        "응답 첫 줄에 정확히 'SCORE: <정수>' 형식으로만 점수를 적으세요.\n\n"
        f"Rubric: {rubric}\n\n--- 에이전트 출력 ---\n{stdout}\n"
    )
    try:
        r = subprocess.run(
            HARNESS.judge_cmd(prompt),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": None, "score": None, "note": "judge timeout"}
    m = re.search(r"SCORE:\s*(\d+)", r.stdout)
    if not m:
        return {
            "ok": None,
            "score": None,
            "note": "judge 점수 파싱 실패 (deterministic만으로 판정)",
        }
    score = int(m.group(1))
    return {"ok": score >= threshold, "score": score, "threshold": threshold}


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------


def build_claude_command(agent: AgentDef, task: str) -> list[str]:
    """CLI 인자만 조립한다. 타임아웃은 호출부의 subprocess.run(timeout=)이 강제한다
    (여기서 받던 timeout 인자는 어디에도 쓰이지 않는 죽은 파라미터였다).
    실제 조립은 `HARNESS`(현재 `ClaudeCodeHarness`) 소유 — 하네스 결합점은 거기 하나뿐이다."""
    return HARNESS.run_scenario_cmd(agent, task)


# 실패 리포트에 남기는 출력 발췌 상한. 리포트는 커밋되지 않지만 baseline 은 커밋되므로
# 무한정 키우지 않는다 — 진단에 필요한 만큼만.
FAIL_EXCERPT_CHARS = 3000


def _fail_excerpt(stdout: str, checks: list[dict]) -> str | None:
    """실패한 어서션 주변 출력을 잘라 둔다.

    **왜 필요한가.** 리포트가 판정만 남기고 출력을 버려서, 실패를 만나면 *"무엇이
    출력됐길래 걸렸는지"* 를 알 수 없었다. 비결정적 시나리오는 수동 재현으로 잡히지도
    않는다 — 실제로 `output_not_contains` 실패 하나를 수동 재현 3회로 못 잡았고,
    가드를 고칠지 에이전트를 고칠지 **추측할 수밖에 없는 상태**가 됐다.
    추측으로 어서션을 약화시키면 그때부터 그 시나리오는 아무것도 안 잡는다.

    실패한 검사의 detail 에 나온 문자열을 출력에서 찾아 그 **주변**을 남긴다.
    못 찾으면 앞부분을 남긴다(그것만으로도 형식·길이 판단이 된다).
    """
    if not stdout:
        return None
    needle = None
    for c in checks:
        if c.get("ok"):
            continue
        detail = str(c.get("detail", ""))
        # "발견됨 ['모든 테스트 통과']" 처럼 detail 에 실린 값을 뽑는다
        m = re.search(r"\['([^']+)'", detail)
        if m:
            needle = m.group(1)
            break
    if needle:
        i = _norm(stdout).find(_norm(needle))
        if i >= 0:
            half = FAIL_EXCERPT_CHARS // 2
            return stdout[max(0, i - half): i + half]
    return stdout[:FAIL_EXCERPT_CHARS]


def _result(
    agent: str,
    scenario: Scenario,
    status: str,
    checks: list[dict],
    duration: float,
    judge=None,
    work_dir: str | None = None,
    stdout: str = "",
) -> dict:
    excerpt = _fail_excerpt(stdout, checks) if status != "pass" else None
    return {
        "agent": agent,
        "scenario": scenario.scenario_id,
        "status": status,
        "checks": checks,
        "judge": judge,
        "duration_s": round(duration, 2),
        # 작업 디렉토리 이름 자체는 중립(에이전트명·시나리오 id 미노출, D-39) —
        # 디버깅용 매핑은 여기 리포트에만 남긴다.
        "work_dir": work_dir,
        # 실패했을 때만 출력 발췌를 남긴다 — 통과한 실행의 출력은 진단 가치가 없고
        # 리포트만 키운다.
        "output_excerpt": excerpt,
    }


def run_scenario(agent: AgentDef, scenario: Scenario, timeout: int) -> dict:
    # fail-closed 가드: assertions 0개 = 채점 불가 = fail (적대적 리뷰 B / ATK-001).
    # "검사 0건"이 pass로 합산되면 baseline 희석·후퇴 은폐가 생긴다 (v2.9.3 P0 계열).
    assertions = scenario.expect.get("assertions", [])
    if not assertions:
        return _result(
            agent.name,
            scenario,
            "fail",
            [
                {
                    "type": "schema",
                    "ok": False,
                    "detail": "assertions 비어있음/누락 — 채점 불가 (fail-closed)",
                }
            ],
            0.0,
        )

    # prefix는 중립이어야 한다(D-39) — 에이전트명·시나리오 id를 넣으면 `pwd` 한 번으로
    # 평가 대상 에이전트가 "나는 지금 평가받는 중"임을 알 수 있다. 디버깅용
    # (디렉토리 → 에이전트/시나리오) 매핑은 _result()의 work_dir 필드로 리포트에만 남긴다.
    with tempfile.TemporaryDirectory(prefix="ckkit-eval-") as td:
        work_dir = Path(td) / "fixture"
        if scenario.fixture_dir.is_dir():
            shutil.copytree(
                scenario.fixture_dir,
                work_dir,
                ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
            )
        else:
            work_dir.mkdir(parents=True)

        if scenario.git_spec is not None:
            try:
                materialize_git_repo(work_dir, scenario.git_spec)
            # 실체화 실패 = error, 어서션 채점에 들어가지 않는다 (D-3 fail-closed).
            # 저장소 없는 상태로 조용히 넘어가 "검사했는데 통과"가 나오는 것이 최악이다.
            except Exception as e:  # noqa: BLE001
                return _result(
                    agent.name,
                    scenario,
                    "error",
                    [
                        {
                            "type": "git_materialize",
                            "ok": False,
                            "detail": f"git.json 실체화 실패: {e!r}",
                        }
                    ],
                    0.0,
                    work_dir=str(work_dir),
                )

        cmd = build_claude_command(agent, scenario.task)
        start = time.time()
        try:
            r = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            stdout = r.stdout
        except subprocess.TimeoutExpired:
            return _result(
                agent.name,
                scenario,
                "fail",
                [{"type": "timeout", "ok": False, "detail": f"{timeout}s 초과"}],
                time.time() - start,
                work_dir=str(work_dir),
            )

        # 인프라 실패(비정상 exit)는 품질 fail과 구분해 'error'로 기록하되,
        # 집계에서는 pass가 아니므로 동일하게 게이트를 막는다 (ATK-004).
        if r.returncode != 0:
            return _result(
                agent.name,
                scenario,
                "error",
                [
                    {
                        "type": "claude_exit",
                        "ok": False,
                        "detail": f"claude exit {r.returncode}: {r.stderr[-300:]}",
                    }
                ],
                time.time() - start,
                work_dir=str(work_dir),
            )

        checks = []
        all_ok = True
        for a in assertions:
            try:
                ok, detail = check_assertion(
                    a, stdout, work_dir, source_fixture=scenario.fixture_dir
                )
            # 채점기 예외 = fail (크래시로 전체 런 유실 금지, ATK-003)
            except Exception as e:  # noqa: BLE001
                ok, detail = False, f"{a.get('type')} — 채점 예외: {e!r}"
            checks.append({"type": a.get("type"), "ok": ok, "detail": detail})
            all_ok = all_ok and ok

        judge_result = None
        judge_cfg = scenario.expect.get("judge") or {}
        if (
            all_ok
            and judge_cfg.get("enabled")
            and os.environ.get("CKKIT_EVAL_JUDGE") == "1"
        ):
            judge_result = run_judge(stdout, judge_cfg, timeout)
            if judge_result is not None:
                # advisory-only: 최종 판정에 영향 없음을 리포트에 명시 (ATK-009).
                judge_result["advisory"] = True

        status = "pass" if all_ok else "fail"
        return _result(
            agent.name,
            scenario,
            status,
            checks,
            time.time() - start,
            judge=judge_result,
            work_dir=str(work_dir),
            stdout=stdout,
        )


def summarize(results: list[dict]) -> dict:
    summary: dict[str, dict] = {}
    for r in results:
        s = summary.setdefault(r["agent"], {"pass": 0, "fail": 0, "total": 0})
        s["total"] += 1
        s["pass" if r["status"] == "pass" else "fail"] += 1
    for s in summary.values():
        s["pass_rate"] = s["pass"] / s["total"] if s["total"] else 0.0
    return summary


def _shdisplay(cmd: list[str]) -> str:
    parts = []
    for c in cmd:
        shown = c if len(c) < 60 else c[:57] + "..."
        parts.append(shlex.quote(shown))
    return " ".join(parts)


def _claude_json_projects_count() -> int | None:
    """`~/.claude.json` 의 projects 키 개수. 없거나 파싱 실패면 None (fail-open, D-10).

    유령 프로젝트 항목이 몇 달간 아무도 모르게 쌓인 적이 있다 — run_all 전후로 이 수를
    비교해 증가하면 그날 바로 경고한다. 하네스가 이 파일을 다시 등록하기 시작해도 조용히
    넘어가지 않게 하는 것이 목적이다.
    """
    path = Path.home() / ".claude.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    projects = data.get("projects")
    return len(projects) if isinstance(projects, dict) else None


def run_all(
    agent_filter: str | None,
    scenario_filter: str | None,
    parallel: int,
    timeout: int,
    dry_run: bool = False,
) -> tuple[dict, int]:
    # 실행 전 스키마 검증 강제 (ATK-001): 유령 디렉토리/깨진 expect.json이
    # "검사 0건 pass"로 흘러드는 경로를 실행 경로 자체에서 차단한다.
    # 실행 경로에서는 필터 범위만 검증 — 무관한 WIP 시나리오가 건강한 시나리오의
    # 실행/dry-run을 막지 않게 (재감사 R1/ATK-002). 전체 검증은 --validate/verify-done §10.
    schema_errors = validate_all(
        agent_filter=agent_filter, scenario_filter=scenario_filter
    )
    if schema_errors:
        for e in schema_errors:
            print(f"[eval] 스키마 오류: {e}", file=sys.stderr)
        return {"results": [], "summary": {}}, EXIT_FAIL

    sc_dirs = discover_scenario_dirs(
        agent_filter=agent_filter, scenario_filter=scenario_filter
    )
    if not sc_dirs:
        print("[eval] 매치되는 시나리오 없음", file=sys.stderr)
        return {"results": [], "summary": {}}, EXIT_FAIL

    scenarios = [load_scenario(d) for d in sc_dirs]
    agents_cache: dict[str, AgentDef] = {}
    plan: list[tuple[AgentDef, Scenario]] = []
    for sc in scenarios:
        if sc.agent not in agents_cache:
            try:
                agents_cache[sc.agent] = load_agent(sc.agent)
            except FileNotFoundError as e:
                print(f"[eval] {e}", file=sys.stderr)
                return {"results": [], "summary": {}}, EXIT_FAIL
        plan.append((agents_cache[sc.agent], sc))

    if dry_run:
        for agent, sc in plan:
            cmd = build_claude_command(agent, sc.task)
            print(f"[dry-run] {sc.agent}/{sc.scenario_id} model={agent.model}")
            print(f"          cmd: {_shdisplay(cmd)}")
        return {"results": [], "summary": {}}, EXIT_PASS

    if not HARNESS.is_available():
        print("[eval] SKIPPED — claude CLI를 PATH에서 찾을 수 없음", file=sys.stderr)
        return {"results": [], "summary": {}}, EXIT_SKIPPED

    projects_before = _claude_json_projects_count()

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        futs = [ex.submit(run_scenario, agent, sc, timeout) for agent, sc in plan]
        for fut in concurrent.futures.as_completed(futs):
            results.append(fut.result())

    projects_after = _claude_json_projects_count()
    if (
        projects_before is not None
        and projects_after is not None
        and projects_after > projects_before
    ):
        print(
            f"[eval] 경고: ~/.claude.json projects {projects_before} → {projects_after} "
            f"(+{projects_after - projects_before}) — 유령 등록 의심",
            file=sys.stderr,
        )

    summary = summarize(results)
    exit_code = EXIT_PASS if all(r["status"] == "pass" for r in results) else EXIT_FAIL
    return {"results": results, "summary": summary}, exit_code


def compare_baseline(
    current_summary: dict, baseline_path: str, agent_filter: str | None = None
) -> list[str]:
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    base_summary = baseline.get("summary", {})
    # --agent 필터 실행 시 baseline도 그 에이전트로 좁힌다 — 필터로 실행하지 않은
    # 에이전트를 "커버리지 소실"로 오탐하는 것을 방지 (최종 재감사 ATK-004).
    if agent_filter is not None:
        base_summary = {k: v for k, v in base_summary.items() if k == agent_filter}
    regressions = []
    for agent, cur in current_summary.items():
        base = base_summary.get(agent)
        if not base:
            continue
        if base.get("pass_rate") is None:
            regressions.append(
                f"{agent}: baseline 항목에 pass_rate 없음 (손상된 baseline)"
            )
            continue
        if cur["pass_rate"] < base["pass_rate"]:
            regressions.append(
                f"{agent}: pass_rate {cur['pass_rate']:.2f} < baseline {base['pass_rate']:.2f}"
            )
        # 커버리지 감소도 후퇴 (ATK-007): 시나리오 삭제로 pass_rate를 유지하는
        # 우회를 차단 — 개수가 줄면 그 자체로 회귀 취급.
        if (
            cur.get("total") is not None
            and base.get("total") is not None
            and cur["total"] < base["total"]
        ):
            regressions.append(
                f"{agent}: 시나리오 수 감소 {cur['total']} < baseline {base['total']}"
            )
    # baseline에 있던 에이전트가 통째로 사라진 경우 (ATK-007)
    for agent in base_summary:
        if agent not in current_summary:
            regressions.append(
                f"{agent}: baseline에 있으나 현재 결과에 없음 (커버리지 소실)"
            )
    return regressions


def print_console_summary(summary: dict) -> None:
    print("\n=== Agent Evals Summary ===")
    if not summary:
        print("  (결과 없음)")
        return
    for agent, s in sorted(summary.items()):
        print(f"  {agent}: {s['pass']}/{s['total']} pass ({s['pass_rate'] * 100:.0f}%)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="hiway-kit agent evals runner")
    p.add_argument(
        "--validate",
        action="store_true",
        help="오프라인 스키마 검증만 수행 (API 불필요)",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="claude 호출 없이 실행 계획만 출력"
    )
    p.add_argument("--agent", help="에이전트 이름으로 필터")
    p.add_argument("--scenario", help="시나리오 id로 필터")
    p.add_argument(
        "--parallel", type=int, default=1, help="동시 실행 시나리오 수 (기본 1)"
    )
    p.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT, help="시나리오당 타임아웃(초)"
    )
    p.add_argument(
        "--baseline",
        action="store_true",
        help="결과를 evals/baseline/<date>.json에 저장",
    )
    p.add_argument(
        "--compare", metavar="BASELINE_JSON", help="baseline 대비 pass-rate 후퇴 검출"
    )
    p.add_argument(
        "--report",
        metavar="REPORT_JSON",
        help="이미 기록된 리포트로 --compare 수행 (재실행하지 않음 — API 비용 0)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.validate:
        # --agent/--scenario는 --validate에도 적용된다. 예전에는 조용히 무시돼서,
        # "내 시나리오 하나만 검증"이 불가능했다 — 무관한 기존 시나리오의 결함이
        # 신규 생성 도구(eval-forge)의 판정을 오염시키는 원인이었다.
        errors = validate_all(agent_filter=args.agent, scenario_filter=args.scenario)
        if errors:
            for e in errors:
                print(f"  [FAIL] {e}")
            print(f"\n{len(errors)}건 검증 실패")
            return EXIT_FAIL
        print("[validate] 모든 시나리오 스키마 OK")
        return EXIT_PASS

    if args.report:
        # 이미 실행한 리포트를 재사용해 비교만 한다.
        #   --compare는 항상 전체를 **다시 실행**했다. 방금 전량 실행을 마친 직후에도
        #   후퇴 여부를 보려면 API 비용을 한 번 더 내야 했다(2026-08-23 릴리스 작업에서
        #   실측). 실행과 판정은 분리 가능한 관심사다.
        if not args.compare:
            print("[report] --report 는 --compare 와 함께 써야 한다.", file=sys.stderr)
            return EXIT_FAIL
        try:
            prev = json.loads(Path(args.report).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[report] 리포트 읽기 실패: {e}", file=sys.stderr)
            return EXIT_FAIL
        summary = prev.get("summary")
        if not summary:
            print(f"[report] summary 없음: {args.report}", file=sys.stderr)
            return EXIT_FAIL
        print_console_summary(summary)
        try:
            regressions = compare_baseline(
                summary, args.compare, agent_filter=args.agent
            )
        except (OSError, json.JSONDecodeError) as e:
            print(f"[compare] baseline 읽기 실패: {e}", file=sys.stderr)
            return EXIT_FAIL
        if regressions:
            print("\n[compare] baseline 대비 후퇴 감지:")
            for r in regressions:
                print(f"  - {r}")
            return EXIT_FAIL
        print("\n[compare] baseline 대비 후퇴 없음")
        return EXIT_PASS

    report, exit_code = run_all(
        args.agent, args.scenario, args.parallel, args.timeout, dry_run=args.dry_run
    )

    if args.dry_run:
        return exit_code
    if exit_code == EXIT_SKIPPED:
        return exit_code

    print_console_summary(report["summary"])

    # 리포트를 compare보다 먼저 기록 — compare 크래시로 실측 결과가 유실되지 않게 (ATK-011).
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = REPORTS_DIR / f"{ts}.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n[eval] report written: {report_path}")

    if args.compare:
        try:
            regressions = compare_baseline(
                report["summary"], args.compare, agent_filter=args.agent
            )
        except (OSError, json.JSONDecodeError) as e:
            print(f"[compare] baseline 읽기 실패: {e}", file=sys.stderr)
            return EXIT_FAIL
        if regressions:
            print("\n[compare] baseline 대비 후퇴 감지:")
            for r in regressions:
                print(f"  - {r}")
            exit_code = EXIT_FAIL
        else:
            print("\n[compare] baseline 대비 후퇴 없음")

    if args.baseline:
        if args.agent or args.scenario:
            # 부분 실행을 기준선으로 저장하면 이후 compare가 미포함 에이전트의
            # 회귀를 영구히 못 본다 — 침묵 커버리지 은닉 차단 (재감사 R1/ATK-001).
            print(
                "[eval] baseline 저장 거부 — 필터(--agent/--scenario)가 걸린 부분 실행은 기준선이 될 수 없음"
            )
        elif exit_code != EXIT_PASS:
            # 실패 런을 기준선으로 저장하면 이후 compare가 오염된다 (ATK-010).
            print("[eval] baseline 저장 거부 — 실패한 런은 기준선이 될 수 없음")
        else:
            BASELINE_DIR.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            baseline_path = BASELINE_DIR / f"{date_str}.json"
            if baseline_path.exists():
                baseline_path.replace(baseline_path.with_suffix(".json.bak"))
                print(f"[eval] 기존 baseline 백업: {baseline_path}.bak")
            baseline_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"[eval] baseline written: {baseline_path}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
