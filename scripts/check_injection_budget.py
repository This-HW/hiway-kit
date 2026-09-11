#!/usr/bin/env python3
"""check_injection_budget.py — 매 세션 **무조건** 들어가는 컨텍스트의 총량 예산.

`verify-done.sh §16` 과 CI 가 **같은 스크립트**를 호출한다(F-023: 복제 로직은 반드시
드리프트한다). 이 검사는 원래 verify-done.sh 안 인라인이었고 **CI 에 없었다** —
"누가 로컬에서 게이트를 돌릴 때만" 발화하는 상태였다.

## 축이 둘인 이유

상시 비용의 출처가 둘인데 **한쪽만 재고 있었다**:

| 축 | 출처 | 우리가 줄이는 방법 |
| --- | --- | --- |
| 규범 + WORKFLOW | 이 킷의 SessionStart 훅이 주입 | core 티어를 축약하거나 conditional/reference 로 내린다 |
| 에이전트 설명 | **하네스**가 에이전트 선택용으로 노출 | 에이전트 수 / description 길이 |

두 번째 축은 `claude plugin details` 의 `Always-on` 추정에도 **잡히지 않는다** —
그 명령은 `agents/*.md` 만 세고 하위 디렉토리를 무시하는데(실측), 이 킷의 에이전트는
전부 `agents/{category}/` 에 있다. 도구가 못 세는 것을 우리가 대신 센다.

## 왜 축을 합치지 않는가

규범 축은 합산이 옳다 — 절을 파일 사이로 **옮기는 것만으로** 통과시키는 게이밍이
가능하기 때문이다(실측). 반면 에이전트 축은 다른 축과 재료가 다르고(우리가 쓰는 산문 vs
하네스가 노출하는 목록) **줄이는 수단도 다르다.** 합치면 "규범을 깎아 에이전트를 늘리는"
교환이 조용히 통과한다 — 그 둘은 교환 가능한 자원이 아니다.

## 왜 축이 둘이 아니라 셋인가 (2026-09-10 컨트롤 판정)

규범 축은 다시 **둘**로 나뉜다. 한 숫자로 합치면 둘 다 못 답한다:

| 축 | 묻는 것 | 상한 |
| --- | --- | --- |
| 규범(항상) | *"모든 세션이 무조건 내는 비용은?"* | 10 KiB |
| 규범(최악) | *"조건이 다 겹치면 얼마까지?"* | 22 KiB |
| 에이전트 | *"하네스가 노출하는 목록의 비용은?"* | 8 KiB |

**항상만 재면** 지금까지처럼 조용히 과소측정한다(그것이 ATK-006 이다).
**최악만 재면** 평범한 세션에 대해 과대보고해서 경고가 죽는다 — 상시 참인 경고는
정보가 아니라 소음이고, 소음은 옆의 진짜 경고까지 죽인다(`warning-signal.md`).

최악 상한 22 KiB 는 판정 시점 실측 20,675B 위 약 1.8 KiB 다. 넉넉하지 않은 것이
의도다 — 이 레포의 상한은 미학이 아니라 **조용한 증가를 막는 래칫**이다.

## 왜 넷째 축인가 — 호스트 전달 한도 (2026-09-11, W13)

셋 다 *"우리가 얼마를 내보내는가"* 만 물었다. **"그것이 모델에 닿는가"** 는 아무도 묻지
않았다. Codex 는 SessionStart 훅 출력이 **2,500 토큰**(`ceil(bytes / 4)`)을 넘으면 머리·
꼬리만 모델에 주고 가운데를 버린다. 우리 규범 최악 상한 22 KiB 는 그 자체로 5,632 토큰 —
**기본 한도의 2.25배**다. 예산 게이트는 green 이었는데 실제 세션에서는:

| 세션 | 훅 출력 | 모델에 도착 | 사라진 규범 |
| --- | --- | --- | --- |
| 이 킷 워크트리 (원장 있음) | 16,622B (4,156 토큰) | 10,028B | Feedback Loop · Loop Engineering · Parallel Worktree |
| 다른 레포 워크트리 (원장 없음) | 13,843B | 10,026B | Parallel Worktree |

출력 순서상 RULES 가 가운데라 **규범이** 잘렸고, 머리와 꼬리가 살아 있어 겉보기엔 온전했다.
두 숫자(Codex 의 2,500 · 우리의 22 KiB)가 **따로 움직였고 대조하는 곳이 없었다.**

그래서 이 축은 `packaging/targets.json` 의 session-start 훅마다 한도를 읽는다. 키가 없으면
상류 기본값이고, `0`(spill 비활성)이면 한도의 소유자가 이 게이트 하나라 통과, 유한값이면
`ceil((RULES_PEAK_CAP + LESSONS 최악) / bytes_per_token) ≤ 한도` 여야 통과한다.
LESSONS 최악은 `feedback_ledger.DIGEST_CHAR_CAP` 을 **import** 해 UTF-8 최악(4B/문자)으로
환산하고 섹션 머리말을 더한다 — 상수를 복사하면 저쪽이 바뀔 때 이 축이 조용히 낡는다.
active work·stale 은 개수 상한으로 따로 묶여 있어 여기서 더하지 않는다.

Claude Code 는 SessionStart 주입을 자르지 않으므로(2.1.268 실측) 이 축에 들어가지 않는다.
훅을 싣는 새 호스트가 생기면 그 호스트의 한도 모델을 `HOST_HOOK_LIMITS` 에 **조사해서**
등재해야 한다 — 등재 전에는 red 다.

## 왜 **최악의 경우**도 재는가

`rules_bytes()` 는 `load_rules(PLUGIN_ROOT, False)` 를 불렀다 — `signals` 인자가 **없는**
호출이라 `tier: conditional` 규범이 하나도 포함되지 않았고, 결국 **core 규범만** 재고
있었다. 그런데 실제 세션은 `parallel-worktree`·`feedback-loop`·`mcp-usage`·`task-resume`
신호를 켜서 부른다(`session-start.py` 의 호출부). 즉 **게이트가 실제 주입량보다 적게
재고 통과시켰다.** 예산 게이트의 존재 이유가 *"매 세션 이만큼을 쓴다"* 인데 그 숫자가
실제보다 작으면, 그 게이트는 예산이 아니라 장식이다.

이제 **conditional 신호를 전부 켠 상태**를 잰다. 신호 이름은 **하드코딩하지 않고**
`rules/*.md` 의 frontmatter `tier: conditional` 에서 파생한다 — 목록을 코드에 나열하면
새 conditional 규범이 추가될 때 **조용히 커버리지를 잃는다**(`warning-signal.md`
§검토 절차 5: "대상을 나열하지 말고 제외를 나열한다"). 파생 결과가 0개면 red 다:
파싱 경로가 깨진 채 "core 만 쟀다"로 되돌아가는 것을 막는다.

## 상한 도출

**먼저 깎고 나서 숫자를 정한다(D-46)** — 반대로 하면 예산이 압력을 잃고 장식이 된다.
에이전트 축은 죽은 `facilitator-teams`(제거된 Agent Teams 모드의 Lead, 470B)를 걷어낸
**뒤** 7,837B 에서 8,192B(8 KiB)로 잡았다. 여유 355B 는 **평균 에이전트 1개분**이라,
에이전트를 하나 더할 때마다 "매 세션 이 비용을 낼 값어치가 있는가"를 묻게 된다.
규범 축의 여유율(4.0%)과 같은 압력이다.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import math
import os
import re
import sys
import types
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
#: UTF-8 한 문자의 최대 바이트 — LESSONS 상한은 **문자** 수라 바이트 최악을 곱으로 구한다.
UTF8_MAX_BYTES_PER_CHAR = 4
#: `feedback_ledger.load_digest` 가 절단 시 붙이는 `" …"` 의 바이트 수(공백 1 + U+2026 3).
DIGEST_TRUNCATION_SUFFIX_BYTES = 4
SESSION_START_SCRIPT = "hooks/session-start.py"

RULES_CORE_CAP = 10240  # 10 KiB — **항상** 내는 비용 (core 규범 + WORKFLOW)
RULES_PEAK_CAP = 22528  # 22 KiB — conditional 이 전부 겹칠 때의 **최대** 비용
AGENTS_CAP = 8192  # 8 KiB — 에이전트 name + description

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)
DESC_RE = re.compile(
    r"^description:\s*\|?\s*\n((?:[ \t]+.*\n?)*)|^description:\s*(.*)$", re.MULTILINE
)


TIER_RE = re.compile(r"^tier:\s*(\S+)\s*$", re.MULTILINE)


def conditional_signals() -> dict[str, bool]:
    """`rules/*.md` 의 frontmatter 에서 `tier: conditional` 규범을 **파생**해 전부 켠다.

    신호 키는 `load_rules` 가 쓰는 것과 같은 **파일명 stem** 이다. 목록을 하드코딩하지
    않는 이유는 위 독스트링 참고 — 새 conditional 규범이 조용히 측정에서 빠지면
    예산은 실제보다 작게 나오고, 그것이 바로 이 게이트가 막아야 할 false-green 이다.
    """
    signals: dict[str, bool] = {}
    for path in sorted((PLUGIN_ROOT / "rules").glob("*.md")):
        fm = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
        if fm is None:
            continue
        tier = TIER_RE.search(fm.group(1))
        if tier is not None and tier.group(1) == "conditional":
            signals[path.stem] = True
    return signals


def rules_bytes() -> tuple[int, int, dict[str, bool]]:
    """(항상 비용, 최악 비용, 켠 신호). 재구현하지 않고 session-start.py 의 함수를 부른다.

    - **항상**: core 전부 + reference 색인. 신호가 하나도 없는 세션이 내는 바닥값이다.
    - **최악**: 거기에 conditional 전부. `include_task_resume` 도 True(활성 Work 세션).

    두 값을 **따로** 돌려주는 이유는 아래 "왜 축이 둘이 아니라 셋인가" 참고.
    """
    spec = importlib.util.spec_from_file_location(
        "session_start", PLUGIN_ROOT / "hooks" / "session-start.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("session-start.py 를 로드할 수 없다")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    signals = conditional_signals()
    if not signals:
        raise RuntimeError(
            "conditional 규범을 하나도 파생하지 못했다 — frontmatter 파싱 경로가 깨졌다. "
            "이대로면 core 만 재고 통과시키던 옛 결함으로 되돌아간다"
        )
    workflow = len(mod.load_workflow_skill(PLUGIN_ROOT).encode())
    always = len(mod.load_rules(PLUGIN_ROOT, False).encode()) + workflow
    peak = len(mod.load_rules(PLUGIN_ROOT, True, signals=signals).encode()) + workflow

    # ── 양성 대조 (W6 F-4) ────────────────────────────────────────────────
    # 0-파생 가드만으로는 부족하다. `conditional_signals()` 와 `load_rules()` 는 신호
    # 키가 **파일명 stem** 이라는 약속으로만 이어져 있고, **그 정합을 아무도 강제하지
    # 않았다.** `load_rules` 쪽 스키마가 stem 에서 바뀌면 파생한 신호가 전부 무시되는데,
    # `conditional_signals()` 는 여전히 4종을 파생하므로 0-파생 가드는 통과하고 게이트는
    # **green** 이 된다 — 이 파일 독스트링이 고쳤다고 선언한 과소측정으로 조용히 되돌아간다.
    #
    # `warning-signal.md` §측정 3: *음성 결과는 "그 지점에 도달했다"를 따로 증명해야
    # 한다.* 그래서 신호마다 **그 신호 하나만 켠 결과가 실제로 커지는지** 확인한다 —
    # 커지지 않았다면 그 키는 `load_rules` 에 닿지 않은 것이다.
    base = len(mod.load_rules(PLUGIN_ROOT, False).encode())
    unreached = [
        key
        for key in sorted(signals)
        if len(mod.load_rules(PLUGIN_ROOT, False, signals={key: True}).encode()) <= base
    ]
    if unreached:
        raise RuntimeError(
            f"신호가 load_rules 에 닿지 않았다: {', '.join(unreached)} — "
            "conditional_signals() 의 키 스키마와 load_rules() 가 갈렸다. "
            "이대로면 파생은 성공한 채 측정만 조용히 과소평가된다"
        )
    if peak <= always:
        raise RuntimeError(
            f"최악({peak}B)이 항상({always}B)보다 크지 않다 — conditional 규범이 "
            "하나도 반영되지 않았다는 뜻이다"
        )
    return always, peak, signals


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
        desc = DESC_RE.search(fm.group(1))
        text = (desc.group(1) or desc.group(2) or "") if desc else ""
        entry = f"{name.group(1) if name else path.stem}: {text.strip()}"
        out.append((len(entry.encode()), path.stem))
    return sorted(out, reverse=True), skipped


@contextlib.contextmanager
def _stubbed_ledger(digest: str):
    """`session-start.load_lessons` 가 import 하는 `feedback_ledger` 를 잠시 바꿔 끼운다.

    `load_lessons` 는 `CLAUDE_PROJECT_DIR` 도 `setdefault` 하므로 함께 되돌린다 —
    게이트 프로세스의 상태를 측정이 오염시키지 않게.
    """
    stub = types.ModuleType("feedback_ledger")
    stub.load_digest = lambda **_kw: digest  # type: ignore[attr-defined]
    saved_mod = sys.modules.get("feedback_ledger")
    saved_env = os.environ.get("CLAUDE_PROJECT_DIR")
    sys.modules["feedback_ledger"] = stub
    try:
        yield
    finally:
        if saved_mod is None:
            sys.modules.pop("feedback_ledger", None)
        else:
            sys.modules["feedback_ledger"] = saved_mod
        if saved_env is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = saved_env


def _load_hook(plugin_root: Path, stem: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"budget_{stem.replace('-', '_')}", plugin_root / "hooks" / f"{stem}.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{stem}.py 를 로드할 수 없다")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lessons_worst_bytes(plugin_root: Path | None = None) -> int:
    """LESSONS 섹션이 낼 수 있는 최대 바이트 — 상한도 머리말도 **실물에서 읽는다**.

    상한은 `feedback_ledger.DIGEST_CHAR_CAP`(문자 수)를 import 해 UTF-8 최악 바이트로
    환산하고, 머리말은 `session-start.load_lessons` 에 탐침 digest 를 넣어 잰다.
    둘 중 하나라도 복사하면 저쪽이 바뀔 때 이 축이 조용히 낡는다.
    """
    root = plugin_root or PLUGIN_ROOT
    ledger = _load_hook(root, "feedback_ledger")
    session_start = _load_hook(root, "session-start")
    probe = "\x00"
    with _stubbed_ledger(probe):
        section = session_start.load_lessons(REPO_ROOT)
    if probe not in section:
        raise RuntimeError(
            "LESSONS 섹션이 탐침 digest 를 싣지 않았다 — 머리말 측정 경로가 깨졌다"
        )
    framing = len(section.encode()) - len(probe.encode())
    digest = ledger.DIGEST_CHAR_CAP * UTF8_MAX_BYTES_PER_CHAR
    return framing + digest + DIGEST_TRUNCATION_SUFFIX_BYTES


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


def check_host_delivery(policy_path: Path, peak_cap: int, lessons_worst: int) -> int:
    """넷째 축. 훅 출력이 **호스트에서 잘리지 않고** 모델에 닿는가.

    최악 출력 = 규범 최악 상한 + LESSONS 최악. 경로를 인자로 받는 것은 테스트가
    픽스처 정책을 주입하기 위해서다.
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
        rc |= _report_delivery(target_id, raw, explicit, peak_cap + lessons_worst)
    return rc


def _report(label: str, used: int, cap: int, hint: str) -> int:
    if used <= cap:
        print(f"[injection-budget] ✓ {label} {used:,}B ≤ {cap:,}B")
        return 0
    print(f"[injection-budget] ✗ {label} {used:,}B > {cap:,}B — 매 세션 이만큼을 쓴다")
    print(f"    → {hint}")
    return 1


def main() -> int:
    try:
        always, peak, signals = rules_bytes()
    except Exception as err:  # noqa: BLE001 — 측정 실패를 green 으로 위장하지 않는다
        print(f"[injection-budget] ✗ 규범 축 측정 실패: {err}")
        return 1

    print(
        f"[injection-budget] · conditional {len(signals)}종: "
        + ", ".join(sorted(signals))
    )
    rc = _report(
        "규범+WORKFLOW(항상)",
        always,
        RULES_CORE_CAP,
        "core 티어를 축약하거나 상시 필요 없는 것을 conditional/reference 로 내려라 (D-17)",
    )
    rc |= _report(
        "규범+WORKFLOW(최악)",
        peak,
        RULES_PEAK_CAP,
        "conditional 규범을 축약하거나 신호 조건을 좁혀라 — 최악은 흔한 조합이다"
        " (워크트리 + 활성 Work + MCP 존재 + 원장 있음)",
    )

    try:
        lessons_worst = lessons_worst_bytes()
    except Exception as err:  # noqa: BLE001 — 측정 실패를 green 으로 위장하지 않는다
        print(f"[injection-budget] ✗ LESSONS 최악 측정 실패: {err}")
        return 1
    rc |= check_host_delivery(TARGETS_POLICY, RULES_PEAK_CAP, lessons_worst)

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
