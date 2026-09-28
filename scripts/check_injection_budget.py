#!/usr/bin/env python3
"""check_injection_budget.py — 매 세션 **무조건** 들어가는 컨텍스트의 총량 예산.

`verify-done.sh §16` 과 CI 가 **같은 스크립트**를 호출한다(F-023: 복제 로직은 반드시
드리프트한다). 이 검사는 원래 verify-done.sh 안 인라인이었고 **CI 에 없었다** —
"누가 로컬에서 게이트를 돌릴 때만" 발화하는 상태였다.

## 축이 둘인 이유

상시 비용의 출처가 둘인데 **한쪽만 재고 있었다**:

| 축 | 출처 | 우리가 줄이는 방법 |
| --- | --- | --- |
| 세션 주입(WORKFLOW·규범·LESSONS·활성 계획) | 이 킷의 SessionStart 훅이 주입 | core 티어를 축약하거나 conditional/reference 로 내린다 |
| 에이전트 설명 | **하네스**가 에이전트 선택용으로 노출 | 에이전트 수 / description 길이 |

두 번째 축은 `claude plugin details` 의 `Always-on` 추정에도 **잡히지 않는다** —
그 명령은 `agents/*.md` 만 세고 하위 디렉토리를 무시하는데(실측), 이 킷의 에이전트는
전부 `agents/{category}/` 에 있다. 도구가 못 세는 것을 우리가 대신 센다.

## 왜 축을 합치지 않는가

주입 축은 합산이 옳다 — 절을 파일 사이로 **옮기는 것만으로** 통과시키는 게이밍이
가능하기 때문이다(실측). 반면 에이전트 축은 다른 축과 재료가 다르고(우리가 쓰는 산문 vs
하네스가 노출하는 목록) **줄이는 수단도 다르다.** 합치면 "규범을 깎아 에이전트를 늘리는"
교환이 조용히 통과한다 — 그 둘은 교환 가능한 자원이 아니다.

## 왜 축이 둘이 아니라 셋인가 (2026-09-10 컨트롤 판정)

주입 축은 다시 **둘**로 나뉜다. 한 숫자로 합치면 둘 다 못 답한다:

| 축 | 묻는 것 | 상한 |
| --- | --- | --- |
| 주입(항상) | *"모든 세션이 무조건 내는 비용은?"* — 빈 레포 | 7 KiB |
| 주입(최악) | *"조건이 다 겹치면 얼마까지?"* — 원장·활성 계획·MCP·구 Work 흔적 | 22 KiB |
| 에이전트 | *"하네스가 노출하는 목록의 비용은?"* | 6 KiB |

**항상만 재면** 조용히 과소측정한다(ATK-006). **최악만 재면** 평범한 세션에 대해
과대보고해서 경고가 죽는다(`warning-signal.md`).

## 무엇을 재는가 — 훅의 **실제 출력** (v5.0.0)

v5.0.0 전에는 `load_rules()`·`load_workflow_skill()` 을 직접 불러 **규범만** 쟀다.
LESSONS·ACTIVE PLANS 는 측정 밖이었고, conditional 신호는 게이트가 frontmatter 에서
파생해 **전부 켠** 가상 조합이었다 — 훅(main)이 실제로 켜는 조합과 따로 놀았다.
그래서 **main() 에 신호가 없어 한 번도 주입되지 않는 conditional 규범**(워크트리 신호가
빠진 뒤의 `parallel-worktree` 가 그랬다)도 게이트에서는 최악 측정에 잡혀 멀쩡해 보였다.

이제 픽스처 레포(빈 레포·원장 있음·활성 계획 있음·워크트리·전부 겹침)를 만들고
`session-start.py` 를 **하네스가 부르는 그대로** 서브프로세스로 돌려 `additionalContext`
바이트를 잰다. 원장은 실물 `feedback_ledger.py upsert` 로 채우고(4바이트 문자로 digest
상한까지), 활성 계획은 표시 상한을 넘겨 생략 줄까지 나오게 한다 — 최악은 최악이어야 한다.

conditional 규범마다 두 가지를 본다(`check_conditional_coverage`): **최악에는 들어가고**
(아니면 신호가 없거나 발화하지 않는다 — 한 번도 발화하지 않는 검사), **빈 레포에는 안
들어간다**(아니면 상시 참 신호다 — core 로 재야 한다). 규범 목록은 frontmatter 에서
파생한다(나열하면 새 규범이 조용히 빠진다).

## 왜 넷째 축인가 — 호스트 전달 한도 (2026-09-11, W13)

셋 다 *"우리가 얼마를 내보내는가"* 만 물었다. **"그것이 모델에 닿는가"** 는 아무도 묻지
않았다. Codex 는 SessionStart 훅 출력이 **2,500 토큰**(`ceil(bytes / 4)`)을 넘으면 머리·
꼬리만 모델에 주고 가운데를 버린다. 실측: 16,622B 출력 중 10,028B 만 도착했고 가운데
RULES 의 규범 3종이 사라졌다 — 예산 게이트는 green 이었다.

그래서 이 축은 `packaging/targets.json` 의 session-start 훅마다 한도를 읽는다. 키가 없으면
상류 기본값이고, `0`(spill 비활성)이면 한도의 소유자가 이 게이트 하나라 통과, 유한값이면
`ceil(INJECTION_PEAK_CAP / bytes_per_token) ≤ 한도` 여야 통과한다. 최악 상한은 이제
LESSONS·ACTIVE PLANS 를 포함한 실제 출력의 상한이므로 따로 더하지 않는다.

Claude Code 는 SessionStart 주입을 자르지 않으므로(2.1.268 실측) 이 축에 들어가지 않는다.
훅을 싣는 새 호스트가 생기면 그 호스트의 한도 모델을 `HOST_HOOK_LIMITS` 에 **조사해서**
등재해야 한다 — 등재 전에는 red 다.

## 상한 도출

**먼저 깎고 나서 숫자를 정한다(D-46)** — 반대로 하면 예산이 압력을 잃고 장식이 된다.
v5.0.0 에서 규칙 14→12(code-quality·ssot 삭제, loop-engineering conditional,
parallel-worktree reference), STALE TASKS 삭제, 에이전트 32→15 를 **한 뒤** 잡았다.
통합 트리 실측(컨트롤 브랜치 규칙·스킬 + 이 훅, 레포 경로에서): 빈 레포 6,587B · 최악 20,909B.
출력의 킷 경로는 절대경로로 렌더되므로 **설치 경로 길이만큼 수치가 움직인다**(수십 바이트 ×
경로 수) — 여유는 그 변동을 흡수할 만큼 둔다.

- 항상 7 KiB — 여유 581B. 짧은 규범 하나가 겨우 들어간다: 규범을 core 로 더하려면 이 질문을
  먼저 해야 한다 — *"매 세션 이 비용을 낼 값어치가 있는가."*
- 최악 22 KiB — 여유 1.6 KiB. LESSONS(4바이트 최악)·활성 계획 12개가 이미 들어 있다.
- 에이전트 6 KiB — v5 통합 실측 5,329B(15종, 이전 32종 7,933B). 4 KiB 로 먼저 잡았다가
  (정리 **전** 설명 합 3,236B 기준 추정) 통합 실측이 넘었다 — B1 이 트리거를 "무엇이 주어졌을 때"
  라는 **입력 조건**으로 다시 쓰면서 종당 평균 ~355B 가 됐다. 추정치로 조이지 않고 실측 위 약
  800B(15%) 로 둔다. 에이전트를 하나 더하려면 그 설명이 이 여유 안에 들어가야 한다.

이전 판(v3.36.0)의 상한 9 KiB·20 KiB·8 KiB 는 **규범만** 잰 값이라 이 표와 직접 비교되지 않는다.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from git_tracked import SkipTally

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "common"
TARGETS_POLICY = REPO_ROOT / "packaging" / "targets.json"
LABEL = "injection-budget"

# ── 호스트 전달 한도 (넷째 축) — 값의 소유자는 각 호스트의 상류다.
#    근거·실측: packaging/targets.json `hooks._evidence.hookContextSpill`
#: 타겟 id → 훅 출력 한도 모델. 여기 없는 호스트가 훅을 실으면 red 다 — 다른 호스트의
#: 기본값을 빌려 쓰면 이번 결함(아무도 대조하지 않은 두 번째 숫자)이 다시 생긴다.
HOST_HOOK_LIMITS: dict[str, dict[str, int]] = {
    "codex": {
        # openai/codex codex-rs/hooks/src/output_spill.rs — DEFAULT_HOOK_OUTPUT_TOKEN_LIMIT
        # (핸들러에 additionalContextLimit 이 없을 때의 한도)
        "default_tokens": 2_500,
        # openai/codex codex-rs/utils/string/src/truncate.rs — APPROX_BYTES_PER_TOKEN
        # (approx_token_count = ceil(bytes / 4))
        "bytes_per_token": 4,
    },
}
SESSION_START_SCRIPT = "hooks/session-start.py"

INJECTION_ALWAYS_CAP = 7168  # 7 KiB — **항상** 내는 비용 (빈 레포의 실제 훅 출력)
INJECTION_PEAK_CAP = 22528  # 22 KiB — 신호·원장·계획이 전부 겹칠 때의 **최대** 출력
AGENTS_CAP = 6144  # 6 KiB — 에이전트 name + description (v5 로스터 15종 실측 5,329B)
#: CLAUDE.md 본문 + `@docs/...` 로 인라인되는 문서 전량. 훅이 아니라 **호스트**가 싣지만
#: 세션마다 무조건 들어간다는 성질은 같다 — 그래서 같은 게이트가 소유한다.
#: v3.37.0 실측 41,007B 위 약 2 KiB(4.9%). 규범 축과 같은 압력이다.
PROJECT_DOC_CAP = 43008  # 42 KiB

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)
DESC_RE = re.compile(r"^description:[ \t]*(.*)$", re.MULTILINE)
BLOCK_STYLE_RE = re.compile(r"[|>][+-]?(?:[ \t]+#.*)?")


def _description_body(lines: list[str]) -> str:
    body: list[str] = []
    for line in lines:
        if line and not line.startswith((" ", "\t")):
            break
        if line.startswith("\t"):
            raise ValueError("description block indentation must use spaces")
        body.append(line)
    if not any(line.strip() for line in body):
        raise ValueError("description block is empty")
    first = next(line for line in body if line.strip())
    indent = len(first) - len(first.lstrip(" "))
    if any(
        line.strip() and len(line) - len(line.lstrip(" ")) < indent for line in body
    ):
        raise ValueError("description block indentation is inconsistent")
    # Raw indentation/newlines conservatively cover folded and literal scalar bytes.
    return "\n".join(body) + "\n"


def _agent_description(frontmatter: str) -> str:
    matches = list(DESC_RE.finditer(frontmatter))
    if len(matches) != 1:
        raise ValueError("exactly one description is required")
    match = matches[0]
    value = match.group(1).strip()
    following = frontmatter[match.end() :].split("\n")[1:]
    if value.startswith(("|", ">")):
        if not BLOCK_STYLE_RE.fullmatch(value):
            raise ValueError("unsupported description block header")
        return _description_body(following)
    if not value or value[0] in "&*!{[#%@`" or "\\" in value:
        raise ValueError("unsupported or empty description scalar")
    if value[0] in "\"'" and (len(value) < 2 or value[-1] != value[0]):
        raise ValueError("unterminated description quote")
    next_line = next((line for line in following if line.strip()), "")
    if next_line.startswith((" ", "\t")):
        raise ValueError("multiline description requires a block style")
    return value


TIER_RE = re.compile(r"^tier:\s*(\S+)\s*$", re.MULTILINE)

#: 픽스처 git 이 사용자 전역 설정(서명·templateDir 훅 등)에 흔들리지 않게 한다.
_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "budget",
    "GIT_AUTHOR_EMAIL": "budget@example.invalid",
    "GIT_COMMITTER_NAME": "budget",
    "GIT_COMMITTER_EMAIL": "budget@example.invalid",
}
#: LESSONS 최악 — UTF-8 4바이트 문자로 digest 문자 상한까지 채운다.
_WORST_CHAR = "\U0001d538"
#: 활성 계획 최악 — session-start 의 표시 상한(10)을 넘겨 생략 줄까지 나오게 한다.
_WORST_PLAN_COUNT = 12


def conditional_rules(plugin_root: Path | None = None) -> list[str]:
    """`rules/*.md` 의 frontmatter 에서 `tier: conditional` 규범의 stem 을 **파생**한다.

    목록을 하드코딩하지 않는다 — 새 conditional 규범이 조용히 측정에서 빠지면
    예산은 실제보다 작게 나오고, 그것이 바로 이 게이트가 막아야 할 false-green 이다
    (`warning-signal.md` §검토 절차 5).
    """
    root = plugin_root or PLUGIN_ROOT
    stems: list[str] = []
    for path in sorted((root / "rules").glob("*.md")):
        fm = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
        if fm is None:
            continue
        tier = TIER_RE.search(fm.group(1))
        if tier is not None and tier.group(1) == "conditional":
            stems.append(path.stem)
    return stems


def _rule_probe(path: Path) -> str:
    """규범 본문의 첫 줄 — 주입 출력에 그 규범이 들어갔는지 가르는 탐침."""
    body = FRONTMATTER_RE.sub("", path.read_text(encoding="utf-8"), count=1)
    return next(line.strip() for line in body.splitlines() if line.strip())


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), env={**os.environ, **_GIT_ENV},
        capture_output=True, text=True, timeout=30, check=True,
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(["init", "-q", "--template="], path)
    _git(["commit", "-q", "--allow-empty", "-m", "init"], path)
    return path


def _add_worst_ledger(repo: Path, plugin_root: Path, home: Path) -> None:
    """실물 `feedback_ledger.py upsert` 로 원장을 채운다 — 형식을 재구현하지 않는다."""
    for i in range(6):
        subprocess.run(
            [sys.executable, str(plugin_root / "hooks" / "feedback_ledger.py"), "upsert",
             "convention", "high", f"측정용 교훈 {i} " + _WORST_CHAR * 400],
            cwd=str(repo), env=_hook_env(repo, home),
            capture_output=True, text=True, timeout=30, check=True,
        )


def _add_worst_plans(repo: Path) -> None:
    for i in range(_WORST_PLAN_COUNT):
        d = repo / "docs" / "plans" / f"2026-01-{i + 1:02d}-{_WORST_CHAR * 20}"
        d.mkdir(parents=True)
        (d / "plan.md").write_text(
            f'---\ntitle: "{_WORST_CHAR * 80}"\nstatus: {_WORST_CHAR * 20}\n---\n',
            encoding="utf-8",
        )
        (d / "checklist.json").write_text(
            json.dumps([{"passes": False}] * 999), encoding="utf-8"
        )


def _hook_env(project: Path, home: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(project),
        **_GIT_ENV,
    }


def run_session_start(plugin_root: Path, project: Path, home: Path) -> str:
    """훅을 **하네스가 부르는 그대로** 실행해 `additionalContext` 를 돌려준다."""
    r = subprocess.run(
        [sys.executable, str(plugin_root / SESSION_START_SCRIPT)],
        cwd=str(project), env=_hook_env(project, home), input="{}",
        capture_output=True, text=True, timeout=60, check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(f"session-start 가 rc={r.returncode} 로 끝났다: {r.stderr[:300]}")
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def measure_scenarios(plugin_root: Path | None = None) -> dict[str, str]:
    """픽스처 레포마다 **실제 main() 출력**. 키: empty · ledger · plan · worktree · peak.

    예전에는 `load_rules()` 를 직접 불러 규범만 쟀다 — LESSONS·ACTIVE PLANS 는 측정 밖이었고
    조합 방식(main 의 신호 계산)이 게이트와 따로 놀았다. 이제 훅 프로세스를 그대로 돌린다.
    """
    root = plugin_root or PLUGIN_ROOT
    with tempfile.TemporaryDirectory(prefix="injection-budget-") as tmp:
        base = Path(tmp)
        home = base / "home"
        home.mkdir()
        empty = _init_repo(base / "empty")
        ledger = _init_repo(base / "ledger")
        _add_worst_ledger(ledger, root, home)
        plan = _init_repo(base / "plan")
        _add_worst_plans(plan)
        worktree = base / "worktree"
        _git(["worktree", "add", "-q", "-b", "wt", str(worktree)], empty)
        peak = _init_repo(base / "peak")
        _add_worst_ledger(peak, root, home)
        _add_worst_plans(peak)
        (peak / ".mcp.json").write_text("{}", encoding="utf-8")
        (peak / "docs" / "works" / "active" / "legacy").mkdir(parents=True)
        return {
            name: run_session_start(root, repo, home)
            for name, repo in (
                ("empty", empty), ("ledger", ledger), ("plan", plan),
                ("worktree", worktree), ("peak", peak),
            )
        }


def check_conditional_coverage(outputs: dict[str, str], plugin_root: Path | None = None) -> list[str]:
    """conditional 규범마다: 최악에는 **들어가고** 빈 레포에는 **안 들어가야** 한다.

    - 최악에 없다 → 신호가 main() 에 없거나 발화하지 않는다. 그 규범은 한 번도 주입되지
      않는다(한 번도 발화하지 않는 검사 — `warning-signal.md` §검토 절차 4).
    - 빈 레포에도 있다 → 신호가 상시 참이다. conditional 이 아니라 core 로 재야 한다
      (§검토 절차 1 — 워크트리 신호가 정확히 이것이었다).
    반환: red 사유 목록(비었으면 통과).
    """
    root = plugin_root or PLUGIN_ROOT
    stems = conditional_rules(root)
    if not stems:
        return [
            "conditional 규범을 하나도 파생하지 못했다 — frontmatter 파싱 경로가 깨졌다"
        ]
    problems: list[str] = []
    for stem in stems:
        probe = _rule_probe(root / "rules" / f"{stem}.md")
        if probe not in outputs["peak"]:
            problems.append(
                f"{stem}: 최악 조합에서도 주입되지 않는다 — session-start 의 "
                "conditional_signals() 에 신호가 없거나 발화하지 않는다"
            )
        elif probe in outputs["empty"]:
            problems.append(f"{stem}: 빈 레포에서도 주입된다 — 상시 참 신호다(core 로 재라)")
    return problems


def agent_entries() -> tuple[list[tuple[int, str]], SkipTally]:
    """하네스가 노출하는 형태(`<name>: <description>`)의 바이트 수를 에이전트마다.

    **건너뛴 파일을 함께 돌려준다** (W6 F-4). 예전에는 frontmatter 파싱 실패를 조용히
    `continue` 했는데, 그러면 에이전트 하나가 깨질 때마다 그만큼 예산에서 빠져 게이트가
    **더 쉽게 통과**한다 — 결함이 게이트를 느슨하게 만드는, 정확히 거꾸로 된 방향이다.
    반환값이 목록뿐이면 호출부는 "N종 쟀다"가 *검사해서 N종* 인지 *못 읽어서 N종* 인지
    구분할 수 없다.
    """
    out: list[tuple[int, str]] = []
    skipped = SkipTally(LABEL)
    for path in sorted((PLUGIN_ROOT / "agents").rglob("*.md")):
        skipped.attempted += 1
        rel = str(path.relative_to(PLUGIN_ROOT.parent.parent))
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as err:
            skipped.add(rel, "read-error", str(err))
            continue
        fm = FRONTMATTER_RE.match(raw)
        if fm is None:
            skipped.add(rel, "no-frontmatter", "YAML frontmatter 를 찾지 못했다")
            continue
        name = NAME_RE.search(fm.group(1))
        try:
            text = _agent_description(fm.group(1))
        except ValueError as err:
            skipped.add(rel, "invalid-description", str(err))
            continue
        entry = f"{name.group(1) if name else path.stem}: {text}"
        out.append((len(entry.encode()), path.stem))
    return sorted(out, reverse=True), skipped


def session_start_limits(policy: dict) -> tuple[list[tuple[str, object, bool]], int]:
    """enabled 타겟의 session-start 훅마다 (타겟 id, 한도 원값, 명시 여부) + 훅 타겟 수."""
    found: list[tuple[str, object, bool]] = []
    hook_targets = 0
    for target in policy.get("targets", []):
        hooks = target.get("hooks")
        if not target.get("enabled") or not hooks:
            continue
        hook_targets += 1
        for entry in hooks.get("events", {}).get("SessionStart", []):
            if entry.get("script") != SESSION_START_SCRIPT:
                continue
            explicit = "additionalContextLimit" in entry
            found.append((target["id"], entry.get("additionalContextLimit"), explicit))
    return found, hook_targets


def _effective_limit(
    target_id: str, raw: object, explicit: bool
) -> tuple[int | None, str]:
    """(한도, 출처 설명). 한도가 None 이면 두 번째 값이 red 사유다."""
    host = HOST_HOOK_LIMITS.get(target_id)
    if host is None:
        return None, (
            f"'{target_id}' 의 훅 출력 한도 모델이 조사되지 않았다 — 상류 기본값·토큰 근사를 "
            "HOST_HOOK_LIMITS 에 출처와 함께 등재하라(다른 호스트의 기본값을 빌려 쓰지 않는다)"
        )
    if not explicit:
        return host["default_tokens"], "키 부재 → 상류 기본값"
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return None, f"additionalContextLimit 이 0 이상의 정수가 아니다 — {raw!r}"
    return raw, "명시"


def _report_delivery(
    target_id: str, raw: object, explicit: bool, worst_bytes: int
) -> int:
    label = f"호스트 전달 한도[{target_id} SessionStart]"
    limit, source = _effective_limit(target_id, raw, explicit)
    if limit is None:
        print(f"[injection-budget] ✗ {label}: {source}")
        return 1
    if limit == 0:
        print(f"[injection-budget] ✓ {label} 0 — spill 비활성, 한도 소유자는 이 게이트")
        return 0
    tokens = math.ceil(worst_bytes / HOST_HOOK_LIMITS[target_id]["bytes_per_token"])
    if tokens <= limit:
        print(
            f"[injection-budget] ✓ {label} 최악 {tokens:,} ≤ {limit:,} 토큰 ({source})"
        )
        return 0
    print(
        f"[injection-budget] ✗ {label} 최악 {tokens:,} > {limit:,} 토큰 ({source}) "
        "— 넘는 만큼 가운데(RULES)가 잘려 모델에 닿지 않는다"
    )
    print(
        "    → packaging/targets.json 의 그 SessionStart 엔트리에 "
        '"additionalContextLimit": 0 (근거: hooks._evidence.hookContextSpill)'
    )
    return 1


def check_host_delivery(policy_path: Path, worst_bytes: int) -> int:
    """넷째 축. 훅 출력이 **호스트에서 잘리지 않고** 모델에 닿는가.

    최악 출력 = 주입 최악 상한(`INJECTION_PEAK_CAP` — LESSONS·ACTIVE PLANS 를 포함한
    실제 출력의 상한). 경로를 인자로 받는 것은 테스트가 픽스처 정책을 주입하기 위해서다.
    """
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        print(f"[injection-budget] ✗ 호스트 전달 한도: 정책을 읽지 못했다 — {err}")
        return 1
    entries, hook_targets = session_start_limits(policy)
    if hook_targets == 0:
        print("[injection-budget] · 호스트 전달 한도: 훅을 싣는 enabled 타겟 없음")
        return 0
    if not entries:
        print(
            f"[injection-budget] ✗ 호스트 전달 한도: 훅을 싣는 타겟 {hook_targets}개에서 "
            f"{SESSION_START_SCRIPT} 엔트리를 하나도 찾지 못했다 — 파싱 경로가 깨졌다"
        )
        return 1
    rc = 0
    for target_id, raw, explicit in entries:
        rc |= _report_delivery(target_id, raw, explicit, worst_bytes)
    return rc


def _report(label: str, used: int, cap: int, hint: str) -> int:
    if used <= cap:
        print(f"[injection-budget] ✓ {label} {used:,}B ≤ {cap:,}B")
        return 0
    print(f"[injection-budget] ✗ {label} {used:,}B > {cap:,}B — 매 세션 이만큼을 쓴다")
    print(f"    → {hint}")
    return 1


def project_doc_bytes() -> tuple[int, list[str]]:
    """CLAUDE.md + 그것이 `@경로` 로 인라인하는 문서의 총 바이트.

    호스트가 `@docs/x.md` 를 **본문에 펼쳐** 싣는다. 그래서 import 한 줄이
    그 파일 전체만큼 비싸다 — 링크로 착각하기 쉬운 자리라 여기서 실측한다.
    중첩 import 는 따라가지 않는다(현재 0건이고, 생기면 아래 목록에 안 잡혀
    **과소측정**이 되므로 그때 이 함수를 확장한다).
    """
    doc = REPO_ROOT / "CLAUDE.md"
    total = len(doc.read_bytes())
    parts = [f"CLAUDE.md {total}B"]
    for line in doc.read_text(encoding="utf-8").splitlines():
        if not line.startswith("@"):
            continue
        target = REPO_ROOT / line[1:].strip()
        size = len(target.read_bytes())  # 없으면 예외 — 깨진 import 를 green 으로 넘기지 않는다
        total += size
        parts.append(f"{target.name} {size}B")
    return total, parts


def main() -> int:
    try:
        outputs = measure_scenarios()
    except Exception as err:  # noqa: BLE001 — 측정 실패를 green 으로 위장하지 않는다
        print(f"[injection-budget] ✗ 주입 측정 실패: {err}")
        return 1

    sizes = {name: len(text.encode()) for name, text in outputs.items()}
    print(
        "[injection-budget] · 실제 main() 출력 — "
        + " · ".join(f"{name} {size:,}B" for name, size in sizes.items())
    )
    problems = check_conditional_coverage(outputs)
    for problem in problems:
        print(f"[injection-budget] ✗ conditional {problem}")
    rc = 1 if problems else 0
    rc |= _report(
        "세션 주입(항상 — 빈 레포)",
        sizes["empty"],
        INJECTION_ALWAYS_CAP,
        "core 티어를 축약하거나 상시 필요 없는 것을 conditional/reference 로 내려라 (D-17)",
    )
    rc |= _report(
        "세션 주입(최악 — 원장·활성 계획·MCP·구 Work 흔적 겹침)",
        max(sizes.values()),
        INJECTION_PEAK_CAP,
        "conditional 규범·LESSONS·ACTIVE PLANS 상한을 줄이거나 신호 조건을 좁혀라",
    )
    rc |= check_host_delivery(TARGETS_POLICY, INJECTION_PEAK_CAP)

    try:
        proj, proj_parts = project_doc_bytes()
    except OSError as err:  # 깨진 @import 를 green 으로 위장하지 않는다
        print(f"[injection-budget] ✗ 프로젝트 지침 축 측정 실패: {err}")
        return 1
    rc |= _report(
        "프로젝트 지침(CLAUDE.md + @import)",
        proj,
        PROJECT_DOC_CAP,
        "역사·사례·증거는 `docs/` 로 내리고 한 줄 포인터만 남겨라 — @import 는 링크가"
        " 아니라 **본문 인라인**이다 (" + " · ".join(proj_parts) + ")",
    )

    entries, skipped = agent_entries()
    # 건너뛴 것이 1건이라도 있으면 red — 그만큼 예산에서 빠져 **더 쉽게 통과**한다.
    # 두 사유 모두 치명이다: 못 읽은 것도, frontmatter 가 없는 것도 사각지대다.
    # 노랑으로 내릴 사유만 등재한다 — 없다. 읽기 실패도 frontmatter 부재도 사각지대다
    # (`git_tracked.SkipTally.report`: 기본이 red, 예외에만 정당화를 요구한다).
    rc |= skipped.report(frozenset())
    if not entries:
        print("[injection-budget] ✗ 에이전트를 하나도 찾지 못했다 — 측정 경로가 깨졌다")
        return 1
    used_agents = sum(b for b, _ in entries)
    rc |= _report(
        f"에이전트 설명({len(entries)}종)",
        used_agents,
        AGENTS_CAP,
        "에이전트를 줄이거나 description 을 짧게 — 상위: "
        + ", ".join(f"{n}({b}B)" for b, n in entries[:3]),
    )
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
