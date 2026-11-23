#!/usr/bin/env python3
"""build-hermes-branch.py — Hermes Agent 용 판(`hermes` 브랜치)을 main 커밋에서 만든다.

## 왜 있는가

Hermes 는 `plugin.json` 을 **Agent Plugins(AP) v1 `$schema`** 일 때만 받는다. main 의
`plugins/common/plugin.json` 은 Antigravity 매니페스트라 거부되고(`manifest_invalid`), 그 거부가
"ref 없이 설치하면 막힌다"는 fail-closed 장치다(판정 D1). 그래서 main 은 그대로 두고, Hermes 에는
생성 브랜치 `hermes` 의 **AP v1 축소판**을 40자 커밋 sha 고정으로 설치하게 한다. 무엇을 싣고 빼는지는
판정 D2, 이 빌더의 범위는 D3 "H1 전 — 빌더" 다(`docs/specs/2026-11-24-hermes-edition/design-verdict.md`).

## 판 변환 (전부 fail-closed — 기대와 다르면 exit 1)

1. **빼기** — `EXCLUDED`: `hooks/`·`setup/`, 사용자 파일을 쓰는 `harness-export`, Hermes 내장 스킬 생성과
   경합하는 `skill-forge`, 훅만 읽는 `rules/CHECKSUMS.sha256`. 원본에 없으면 멈춘다
   (이름이 바뀐 것이다 — 아무것도 빼지 않은 트리를 판이라 부르지 않는다). `tools/` 는 **싣는다**
   (스킬 도구·규칙 내보내기 CLI).
2. **루트 매니페스트** — `plugins/common/plugin.json` 을 `build-targets.py` 의 `load_policy`·`load_ssot`·
   `build_manifest`(hermes 타겟)로 만든 AP v1 매니페스트로 **교체**한다. 매핑은 정책 한 벌뿐이고, 직렬화도
   build-targets 의 `_dumps` 다. 정책과 SSOT 는 작업 트리가 아니라 **원본 커밋**의 것을 읽는다.
3. **`using-hiway-kit` description** — 원본이 `EXPECTED_USING_DESCRIPTION` 과 **정확히** 같을 때만
   `HERMES_USING_DESCRIPTION` 으로 바꾼다. 원본이 바뀌면 사람이 Hermes 문구를 다시 정한다.
4. **Hermes 머리말** — 공용 배관 `_with_note` 로 frontmatter 바로 뒤에 넣는다. 문구는 디렉토리판과 따로다.
   `HERMES_AGENT_NOTE` 는 모든 `agents/*.md`, `HERMES_ISOLATION_NOTE` 는 수정 에이전트 4종과 그들을
   부르는 문서(`ISOLATION_NOTE_DOCS`), `HERMES_MISSING_PATHS_NOTE` 는 뺀 경로를 가리키는 문서
   (`MISSING_PATHS_DOCS`)에 단다.
5. **판 README** — `plugins/common/README.md` 를 `HERMES_README` 로 교체한다.

## 검사 조건 (한 문장)

**실행할 때마다(`--check`·`--out`·`--write` 모두) 원본 커밋에 `EXCLUDED` 가 전부 있는지, 원본 정책의
hermes 타겟으로 계산한 매니페스트가 AP v1 판정을 통과하는지, `using-hiway-kit` description 이 기대 문자열과
같은지를 보고, 결과 트리의 `plugins/common` 에 대해 (1) 뺀 경로가 없는지, (2) `plugin.yaml`(`.yml`)이 없는지,
(3) 루트 `plugin.json` 이 AP v1 판정을 통과하고 계산값과 바이트가 같은지, (4) `.claude-plugin/plugin.json` 이
있는지, (5) 스킬이 정확히 `EXPECTED_SKILL_COUNT` 개이고 각 `SKILL.md` frontmatter 가 AP 제약을 지키는지,
(6) 심링크·서브모듈이 0개인지, (7) 원본을 **따로 스캔한** 머리말 대상 집합이 허용 목록과 같고 머리말이 정확히
그 문서들에만 있는지, (8) description 교체와 README 교체가 적용됐는지를 확인해 하나라도 어긋나면 exit 1.**
(7)은 양방향이다 — 허용 목록 밖에서 뺀 경로·수정 에이전트를 가리키는 새 문서도, 더는 가리키지 않는데
목록에 남은 문서도 red 다(디렉토리 빌더의 `DEGRADES_WITHOUT_REMOVED` 관례, 낡은 목록 방지).

스킬 frontmatter 제약의 근거: Hermes `hermes_cli/agent_plugins.py` `_valid_skill_frontmatter` @352b249
(조사 보고서 §2.3). YAML 을 풀지 않으므로 한 줄 스칼라와 한 단계 맵·목록만 읽고, 그 밖의 형태(블록 스칼라·
흐름 컬렉션·앵커·주석이 붙은 값·중복 키)는 **판정할 수 없으므로** exit 1 이다.

## 출력

- `--check` — `enabled` 와 무관하게 판 트리를 계산·판정하고
  `[hermes-edition] ✓ 판 트리 <sha> (원본 <short>)`·`[hermes-edition] plugin tree: <sha>`(디렉토리 빌더와
  같은 형식 계약)·`[hermes-edition] skills: <n>` 을 출력한다. 바꾼 문서의 blob 은 객체 DB 에 쓴다(ref 무변경).
- `--out <dir>` — 판의 `plugins/common` 을 파일로 내보낸다(H1 실측 설치 입력). 레포 안 경로·비어 있지 않은
  디렉토리는 거부하고, 내보낸 파일 집합·내용(blob sha)·실행 비트를 트리와 스스로 대조한다.
- `--write [--branch hermes]` — 원본 정책의 hermes 타겟이 `enabled:true` 일 때만 `refs/heads/<branch>` 를
  공용 배관 `edition_tree.write_branch` 로 갱신한다. 아니면 이유를 출력하고 exit 1. push 는 하지 않는다.

사용:
  scripts/build-hermes-branch.py --check [--source <rev>]
  scripts/build-hermes-branch.py --out /private/tmp/hermes-edition-out
  scripts/build-hermes-branch.py --write [--branch hermes]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from edition_tree import (
    _entries,
    _frontmatter_span,
    _git,
    _git_bytes,
    _note_marker,
    _rev,
    _with_note,
)
from edition_tree import write_branch as _write_edition_branch

REPO_ROOT = Path(__file__).resolve().parent.parent
_LOG_LABEL = "hermes-edition"


def _load_build_targets():
    """하이픈 파일명 `build-targets.py` 를 모듈로 읽는다 — 매니페스트 매핑을 두 벌 두지 않기 위해."""
    path = Path(__file__).resolve().parent / "build-targets.py"
    spec = importlib.util.spec_from_file_location("_hermes_build_targets", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bt = _load_build_targets()

PLUGIN_ROOT = "plugins/common"
POLICY = "packaging/targets.json"
TARGET_ID = "hermes"
CLAUDE_MANIFEST = f"{PLUGIN_ROOT}/.claude-plugin/plugin.json"
ROOT_MANIFEST = f"{PLUGIN_ROOT}/{bt.AP_V1_MANIFEST_NAME}"
README = f"{PLUGIN_ROOT}/README.md"
USING_SKILL = "skills/using-hiway-kit/SKILL.md"
EXPECTED_SKILL_COUNT = 15
DEFAULT_BRANCH = "hermes"

#: 판에서 빼는 레포 루트 기준 경로(파일 또는 디렉토리)와 사유 — 판정 D2.
EXCLUDED = {
    f"{PLUGIN_ROOT}/hooks": "Hermes 는 킷 훅을 읽지 않는다(셸 훅은 사용자 config.yaml 소관, 페이로드가 다르다)",
    f"{PLUGIN_ROOT}/setup": "session-check·git 훅 — Claude Code·git 설치 경로 전용",
    f"{PLUGIN_ROOT}/skills/harness-export": "사용자 파일을 쓰는 스킬 — consumer-footprint 규칙 1·4, CLI 로 대신 안내",
    f"{PLUGIN_ROOT}/skills/skill-forge": "Hermes 내장 스킬 생성과 경합(판정 기준 5)",
    f"{PLUGIN_ROOT}/rules/CHECKSUMS.sha256": "훅(session-start)만 읽는다 — tools/ 참조 0건(grep)",
    # rules/VERSION 은 **빼지 않는다**: tools/export_harness.py(`_rules_version`)가 마커 sha 입력으로
    # 필수로 읽는다. "훅만 읽는다"로 오분류해 뺐다가 H1 P4 실측에서 판의 규칙 내보내기가 rc 1 로 죽었다.
    # 회귀는 실레포 판을 --out 으로 내보내 도구를 실제로 돌리는 테스트가 막는다.
}

#: `using-hiway-kit` description — 원본 원문(정확 일치)과 Hermes 판 문구. Hermes 에는 세션 시작 주입 훅이
#: 없으므로 "(hook-injected)"·Session-start 표현을 빼고 워크플로 진입 안내로 쓴다.
EXPECTED_USING_DESCRIPTION = (
    "Session-start meta-skill (hook-injected). Kit workflow chain and plan file rules."
)
HERMES_USING_DESCRIPTION = (
    "Workflow entry guide for the kit. Read it when starting a task to pick the workflow chain by task"
    " size and to follow the plan file rules."
)

#: 머리말 — frontmatter 바로 뒤(없으면 맨 앞)에 넣는다. 첫 줄 40자가 이미 넣었는지 판정하는 표지다.
#: 디렉토리판 문구(build-directory-branch.py)를 재사용하지 않는다 — 판마다 없는 것이 다르다.
HERMES_AGENT_NOTE = (
    "> **Hermes 판 — 서브에이전트 정의로 로드되지 않음.** Hermes 는 이 파일을 서브에이전트로 로드하지 않는다"
    " (에이전트 정의 로더가 없다). 스킬이 이 본문을 `delegate_task` 의 context 로 넘겨 위임 브리프로 쓸 수"
    " 있다. 위 frontmatter(`model`·`tools`·`isolation` 등)는 Hermes 에서 **집행되지 않는다** — 위임받은 쪽은"
    " 부모의 도구를 물려받는다.\n"
)
HERMES_ISOLATION_NOTE = (
    "> **Hermes 판 — 자동 worktree 격리 없음.** Hermes 에는 자동 worktree 가 없고,"
    " `delegation.worktree_isolation` 은 worktree 를 만들지 못하면 **공유 CWD 로 진행**할 수 있다. 그래서 파일을"
    " 고치는 에이전트(implement-code·fix-bugs·write-tests·sync-docs)는 호출자가 별도 worktree 와 기준 커밋을"
    " 확인해 주지 않았으면 **커밋하지 말고** 편집 결과(diff·요약)를 부모에게 돌려준다. 수정 위임은 격리가"
    " 확인되는 운송으로만 하고, 확인되지 않으면 부모가 그 작업을 **순차로** 직접 실행한다.\n"
)
HERMES_MISSING_PATHS_NOTE = (
    "> **Hermes 판 — 훅·설치 스크립트·일부 스킬 없음.** 이 판에는 킷의 `hooks/`·`setup/` 과 `harness-export`·"
    "`skill-forge` 스킬이 없다. 아래에서 그것을 실행하거나 켜라는 단계는 건너뛴다(없음으로 처리). 규칙"
    " 내보내기는 CLI 로 한다: `python3 <설치 루트>/tools/export_harness.py --plugin-root <설치 루트> --target"
    " <프로젝트> --entrypoints AGENTS.md`. 다른 설치(예: `~/.claude/plugins/cache`)에서 같은 이름의 파일·도구를"
    " 찾아 쓰지 않는다 — 버전이 다른 도구다.\n"
)

#: 머리말을 다는 문서(플러그인 폴더 기준) — **허용 목록**. 원본 스캔 결과와 양방향으로 같아야 한다.
#: 새 문서가 뺀 경로·수정 에이전트를 가리키면 빌드가 멈추고, 그 단계를 건너뛰어도 도는지 사람이 확인해 넣는다.
MISSING_PATHS_DOCS = frozenset(
    {
        "rules/agent-delegation-chain.md",
        "skills/auto-dev/SKILL.md",
        "skills/child-session/SKILL.md",
        "skills/control-loop/SKILL.md",
        "skills/plan-task/references/task-tools-fallback.md",
    }
)
ISOLATED_AGENTS = ("implement-code", "fix-bugs", "write-tests", "sync-docs")
ISOLATION_NOTE_DOCS = frozenset(
    {
        *(f"agents/{name}.md" for name in ISOLATED_AGENTS),
        "rules/agent-system.md",
        "skills/auto-dev/SKILL.md",
        "skills/debug/SKILL.md",
        "skills/multi-perspective-review/examples.md",
        "skills/test/SKILL.md",
    }
)

#: 뺀 경로를 가리키는 본문 — `hooks/…`·`setup/…` 경로와 뺀 스킬 이름(디렉토리 빌더 `_MISSING_PATH_RE` 관례,
#: 이 판에서는 `tools/` 를 싣으므로 대상이 아니다).
_MISSING_PATH_RE = re.compile(
    r"(?<![\w.-])(?:hooks|setup)/[\w.*-]|(?<![\w-])(?:harness-export|skill-forge)(?![\w-])"
)
#: 수정 에이전트를 부르는 본문(디렉토리 빌더 `_ISOLATED_AGENT_RE` 관례).
_ISOLATED_AGENT_RE = re.compile(
    r"(?<![\w-])(?:implement-code|fix-bugs|write-tests|sync-docs)(?![\w-])"
)
_AGENT_DOC_RE = re.compile(r"agents/[^/]+\.md")

#: AP 스킬 frontmatter 제약 — Hermes `_valid_skill_frontmatter` @352b249(조사 보고서 §2.3).
SKILL_NAME_RE = re.compile(r"^(?!.*--)[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILL_DESCRIPTION_MAX = 1024
SKILL_COMPATIBILITY_MAX = 500
SKILL_STRING_FIELDS = ("license", "compatibility", "allowed-tools")

HERMES_README = """\
# hiway-kit — Hermes edition

This is the **Hermes Agent edition** of hiway-kit, generated from `main` by
`scripts/build-hermes-branch.py` onto the `hermes` branch. It is an Agent Plugins v1 package:
`plugin.json` here carries the Agent Plugins schema, while `main` keeps a manifest Hermes refuses, so
installing without a pinned ref stops instead of loading the wrong tree.

**Status: researched, not yet measured.** Nothing below has been observed in a running Hermes yet;
the sandbox measurement (H1) decides whether this edition is published.

## What is in it

- **15 skills**, **no hooks**. `hooks/` and `setup/` are not shipped, and neither are
  `harness-export` (it writes the user's files) and `skill-forge` (Hermes creates skills itself).
- `agents/` are shipped as **brief documents**, not subagents: Hermes has no agent-definition loader,
  so a skill may pass an agent body to `delegate_task` as context. Their frontmatter is not enforced,
  and there is no automatic worktree isolation — see the note at the top of each agent.
- `rules/` and `tools/` are shipped. Export the rules into a project with the CLI:
  `python3 <install root>/tools/export_harness.py --plugin-root <install root> --target <project> --entrypoints AGENTS.md`
- **No behavioral evals** have been run for this edition.

## Install (pinned to a commit)

Install only by a full 40-character commit sha of the `hermes` branch. A branch name or tree URL as
the ref is refused or dropped, and there is **no automatic update**.

```bash
sha=$(git ls-remote https://github.com/This-HW/hiway-kit refs/heads/hermes | cut -f1)
test ${#sha} -eq 40 || { echo "no hermes branch sha"; exit 1; }
hermes plugins install This-HW/hiway-kit/plugins/common --ref "$sha" --no-enable
```

Hermes asks you to confirm the install; its security review is expected to report **caution**
(pending the H1 verdict). Enable the plugin yourself after reviewing it.

Update by installing a newer sha over it — `hermes plugins update` refuses pinned installs:

```bash
hermes plugins install This-HW/hiway-kit/plugins/common --force --ref <new 40-char sha>
```

Details, caveats and the measurement plan: `docs/harnesses.md#hermes-agent` in the repository.
"""


# --- 정책·매니페스트 --------------------------------------------------------------------------------


def _blob_text(repo: Path, rev: str, path: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "blob", f"{rev}:{path}"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.exit(f"[{_LOG_LABEL}] ✗ 원본 {rev[:7]} 에 {path} 가 없다")
    try:
        return proc.stdout.decode("utf-8")
    except UnicodeDecodeError:
        sys.exit(f"[{_LOG_LABEL}] ✗ UTF-8 이 아니다: {path}")


def _source_policy(repo: Path, source: str) -> tuple[dict, dict, dict]:
    """원본 커밋의 정책·hermes 타겟·SSOT 매니페스트. build-targets 의 로더를 그대로 쓴다.

    로더는 디스크를 읽으므로 원본 커밋의 두 파일을 임시 루트에 옮겨 두고 읽는다. SSOT 경로는 정책 값이라
    `_source_path`(레포 봉쇄 resolver)로 **한 번만** 해석한 결과에 쓰고 그대로 읽힌다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        policy_path = root / POLICY
        policy_path.parent.mkdir(parents=True)
        policy_path.write_text(_blob_text(repo, source, POLICY), encoding="utf-8")
        try:
            policy = bt.load_policy(policy_path)
            targets = bt.validate_targets(policy)
            plugin_root = bt._require(policy.get("source"), "pluginRoot", "source")
            if plugin_root != PLUGIN_ROOT:
                raise bt.PolicyError(
                    f"source.pluginRoot 가 {plugin_root!r} — 이 빌더는 {PLUGIN_ROOT!r} 만 안다"
                )
            target = next((t for t in targets if t.get("id") == TARGET_ID), None)
            if target is None:
                raise bt.PolicyError(f"타겟 '{TARGET_ID}' 가 없다")
            if not bt.is_edition(target):
                raise bt.PolicyError(
                    f"타겟 '{TARGET_ID}' 가 delivery:edition 이 아니다"
                )
            ssot_path = bt._source_path(root, policy, "manifest")
            rel = ssot_path.relative_to(root).as_posix()
            ssot_path.parent.mkdir(parents=True, exist_ok=True)
            ssot_path.write_text(_blob_text(repo, source, rel), encoding="utf-8")
            ssot = bt.load_ssot(root, policy)
        except bt.PolicyError as err:
            sys.exit(f"[{_LOG_LABEL}] ✗ 정책: {err}")
    return policy, target, ssot


def _manifest_text(policy: dict, target: dict, ssot: dict, present: set[str]) -> str:
    try:
        manifest = bt.build_manifest(ssot, target, present)
    except bt.PolicyError as err:
        sys.exit(f"[{_LOG_LABEL}] ✗ 매니페스트: {err}")
    problems = bt.ap_v1_violations(manifest)
    if problems:
        sys.exit(f"[{_LOG_LABEL}] ✗ AP v1 판정 실패 — " + "; ".join(problems))
    return bt._dumps(manifest)


# --- frontmatter(AP 판정용 — YAML 을 풀지 않는 보수적 읽기) -------------------------------------------

_YAML_NULL = frozenset({"", "~", "null", "Null", "NULL"})
_YAML_BOOL = frozenset(
    w
    for b in ("yes", "no", "true", "false", "on", "off")
    for w in (b, b.capitalize(), b.upper())
)
#: PyYAML(YAML 1.1) 암묵 타입 — 이 모양의 평문 스칼라는 문자열이 아니다.
_YAML_NON_STR_RE = re.compile(
    r"[-+]?(?:0b[01_]+|0x[0-9a-fA-F_]+|0[0-7_]+|(?:0|[1-9][0-9_]*)|[1-9][0-9_]*(?::[0-5]?[0-9])+)"
    r"|[-+]?(?:[0-9][0-9_]*)?\.[0-9_]*(?:[eE][-+][0-9]+)?|[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*"
    r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN)"
    r"|[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}(?:(?:[Tt]|[ \t]+)[0-9].*)?"
)
_FM_KEY_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*):(?:[ \t]+(.*?))?[ \t]*$")
_FM_CHILD_RE = re.compile(
    r"^([ \t]+)([A-Za-z0-9_][A-Za-z0-9_.-]*):(?:[ \t]+(.*?))?[ \t]*$"
)
_FM_ITEM_RE = re.compile(r"^([ \t]+)-[ \t]+(.*?)[ \t]*$")


class _NonStr:
    """문자열이 아닌 YAML 스칼라(숫자·불리언·날짜·null) — 값의 원문만 보관한다."""

    def __init__(self, raw: str) -> None:
        self.raw = raw

    def __repr__(self) -> str:
        return f"<비문자열 {self.raw!r}>"


def _scalar(raw: str, where: str) -> object:
    """한 줄 스칼라를 읽는다. 판정할 수 없는 형태면 exit 1."""
    if raw.startswith('"'):
        if not re.fullmatch(r'"(?:[^"\\]|\\.)*"', raw):
            sys.exit(
                f"[{_LOG_LABEL}] ✗ {where}: 값을 읽을 수 없는 형태다(따옴표 뒤 내용) — 한 줄 스칼라로 고쳐라"
            )
        try:
            return json.loads(raw)
        except ValueError:
            sys.exit(
                f"[{_LOG_LABEL}] ✗ {where}: 값을 읽을 수 없는 형태다(이스케이프) — 한 줄 스칼라로 고쳐라"
            )
    if raw.startswith("'"):
        if not re.fullmatch(r"'(?:[^']|'')*'", raw):
            sys.exit(
                f"[{_LOG_LABEL}] ✗ {where}: 값을 읽을 수 없는 형태다(따옴표 뒤 내용) — 한 줄 스칼라로 고쳐라"
            )
        return raw[1:-1].replace("''", "'")
    if (
        (
            raw[:1] in tuple("-?:,[]{}#&*!|>%@`")
            and not (raw[:1] in "-?:" and len(raw) > 1 and not raw[1].isspace())
        )
        or ": " in raw
        or " #" in raw
        or "\t#" in raw
        or raw.endswith(":")
    ):
        sys.exit(
            f"[{_LOG_LABEL}] ✗ {where}: 값을 읽을 수 없는 형태다(블록 스칼라·흐름 컬렉션·앵커·주석·`: ` 포함)"
            " — 한 줄 스칼라로 고치거나 따옴표로 감싸라"
        )
    if raw in _YAML_NULL or raw in _YAML_BOOL or _YAML_NON_STR_RE.fullmatch(raw):
        return _NonStr(raw)
    return raw


def _frontmatter(text: str, rel: str) -> dict[str, object] | None:
    """frontmatter 를 {키: 문자열 | _NonStr | dict | list} 로 읽는다. 없으면 None. 모호하면 exit 1."""
    span = _frontmatter_span(text, rel, label=_LOG_LABEL)
    if span is None:
        return None
    lines = text[4 : span[1]].split("\n")
    out: dict[str, object] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or (
            line.lstrip().startswith("#") and not line[:1].isspace()
        ):
            continue
        m = _FM_KEY_RE.match(line)
        if not m:
            sys.exit(
                f"[{_LOG_LABEL}] ✗ {rel}: frontmatter 줄을 읽을 수 없는 형태다 — {line[:60]!r}"
            )
        key, raw = m.group(1), m.group(2) or ""
        if key in out:
            sys.exit(
                f"[{_LOG_LABEL}] ✗ {rel}: frontmatter 키 `{key}` 중복 — Hermes 는 마지막 값만 본다"
            )
        where = f"{rel}: `{key}`"
        children = []
        while i < len(lines) and lines[i][:1] in (" ", "\t"):
            children.append(lines[i])
            i += 1
        if raw:
            if children:
                sys.exit(
                    f"[{_LOG_LABEL}] ✗ {where}: 값을 읽을 수 없는 형태다(여러 줄 이어짐)"
                )
            out[key] = _scalar(raw, where)
            continue
        if not children:
            out[key] = _NonStr("")  # 빈 값은 null
            continue
        indent = re.match(r"[ \t]+", children[0]).group(0)
        if all(
            _FM_ITEM_RE.match(c)
            and c.startswith(indent)
            and not c[len(indent)].isspace()
            for c in children
        ):
            out[key] = [_scalar(_FM_ITEM_RE.match(c).group(2), where) for c in children]
            continue
        mapping: dict[object, object] = {}
        for c in children:
            cm = _FM_CHILD_RE.match(c)
            if not cm or cm.group(1) != indent or not cm.group(3):
                sys.exit(
                    f"[{_LOG_LABEL}] ✗ {where}: 한 단계 `키: 값` 맵만 읽는다 — {c.strip()[:60]!r}"
                )
            raw_key = cm.group(2)
            child_key = _scalar(raw_key, where)
            if child_key in mapping:
                sys.exit(f"[{_LOG_LABEL}] ✗ {where}: 맵 키 `{raw_key}` 중복")
            mapping[child_key] = _scalar(cm.group(3), f"{where}.{raw_key}")
        out[key] = mapping
    return out


def _skill_problems(rel: str, text: str) -> list[str]:
    """`skills/<dir>/SKILL.md` frontmatter 의 AP 제약 위반 목록."""
    fm = _frontmatter(text, rel)
    if fm is None:
        return [f"{rel}: frontmatter 가 없다"]
    folder = rel.split("/")[1]
    out = []
    name = fm.get("name")
    if not isinstance(name, str) or name != folder or not SKILL_NAME_RE.fullmatch(name):
        out.append(
            f"{rel}: name {name!r} 은 디렉토리명 {folder!r} 와 같고 {SKILL_NAME_RE.pattern} 를 만족해야 한다"
        )
    desc = fm.get("description")
    if not isinstance(desc, str) or not 1 <= len(desc) <= SKILL_DESCRIPTION_MAX:
        shown = desc if not isinstance(desc, str) else f"{len(desc)}자"
        out.append(
            f"{rel}: description 은 1~{SKILL_DESCRIPTION_MAX}자 문자열이어야 한다 — {shown!r}"
        )
    for field in SKILL_STRING_FIELDS:
        if field in fm and not isinstance(fm[field], str):
            out.append(f"{rel}: {field} 는 문자열이어야 한다 — {fm[field]!r}")
    compat = fm.get("compatibility")
    if isinstance(compat, str) and len(compat) > SKILL_COMPATIBILITY_MAX:
        out.append(
            f"{rel}: compatibility 는 {SKILL_COMPATIBILITY_MAX}자 이하 — {len(compat)}자"
        )
    if "metadata" in fm:
        meta = fm["metadata"]
        if not isinstance(meta, dict):
            out.append(f"{rel}: metadata 는 문자열→문자열 맵이어야 한다 — {meta!r}")
        elif not all(
            isinstance(k, str) and isinstance(v, str) for k, v in meta.items()
        ):
            out.append(f"{rel}: metadata 의 키·값은 문자열이어야 한다 — {meta!r}")
    return out


# --- 판 변환 ------------------------------------------------------------------------------------------


def _replace_using_description(text: str, rel: str) -> str:
    """원본 description 이 기대 문자열과 정확히 같을 때만 Hermes 문구로 바꾼다(그 한 줄만)."""
    fm = _frontmatter(text, rel) or {}
    if fm.get("description") != EXPECTED_USING_DESCRIPTION:
        sys.exit(
            f"[{_LOG_LABEL}] ✗ {rel}: description 이 EXPECTED_USING_DESCRIPTION 과 다르다 — 원본이 바뀌었으면"
            f" Hermes 문구(HERMES_USING_DESCRIPTION)를 다시 정하고 두 상수를 고쳐라. 원본: {fm.get('description')!r}"
        )
    end = _frontmatter_span(text, rel, label=_LOG_LABEL)[1]
    old = f"\ndescription: {EXPECTED_USING_DESCRIPTION}\n"
    head = "\n" + text[4:end]
    if head.count(old) != 1:
        sys.exit(
            f"[{_LOG_LABEL}] ✗ {rel}: description 줄이 정확히 한 번 평문 그대로 있어야 바꾼다"
        )
    new_head = head.replace(old, f"\ndescription: {HERMES_USING_DESCRIPTION}\n")
    return text[:4] + new_head[1:] + text[end:]


def _transform(rel: str, text: str) -> str:
    """Hermes 판 문서 변환. `rel` 은 플러그인 폴더 기준 경로. 머리말은 아래서부터 넣는다(위: 에이전트)."""
    new = _replace_using_description(text, rel) if rel == USING_SKILL else text
    if _MISSING_PATH_RE.search(text):
        new = _with_note(new, HERMES_MISSING_PATHS_NOTE, rel, label=_LOG_LABEL)
    if rel in {f"agents/{a}.md" for a in ISOLATED_AGENTS} or _ISOLATED_AGENT_RE.search(
        text
    ):
        new = _with_note(new, HERMES_ISOLATION_NOTE, rel, label=_LOG_LABEL)
    if _AGENT_DOC_RE.fullmatch(rel):
        new = _with_note(new, HERMES_AGENT_NOTE, rel, label=_LOG_LABEL)
    return new


def _reject_links(entries: list[tuple[str, str, str]]) -> None:
    for mode, _sha, path in entries:
        shown = path.encode("utf-8", errors="surrogateescape").decode(errors="replace")
        if mode == "160000":
            sys.exit(f"[{_LOG_LABEL}] ✗ 서브모듈(gitlink)은 판에 실을 수 없다: {shown}")
        if mode == "120000":
            sys.exit(
                f"[{_LOG_LABEL}] ✗ 심링크는 판에 실을 수 없다(AP 로더가 루트 밖 심링크를 거부): {shown}"
            )


def _hash(repo: Path, data: bytes) -> str:
    return (
        _git_bytes(repo, "hash-object", "-w", "--stdin", data=data, label=_LOG_LABEL)
        .decode()
        .strip()
    )


def derive_tree(repo: Path, source: str) -> str:
    """원본 커밋에서 Hermes 판 트리를 만든다(임시 인덱스만 — 작업 트리·인덱스·ref 무변경)."""
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
            f"[{_LOG_LABEL}] ✗ 원본에 뺄 경로가 없다 — 이름이 바뀌었으면 EXCLUDED 를 고쳐라: "
            + ", ".join(missing)
        )
    for required in (ROOT_MANIFEST, README):
        _blob_text(repo, source, required)  # 교체 대상이 없으면 멈춘다
    policy, target, ssot = _source_policy(repo, source)
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        _git(repo, "read-tree", source, env=env, label=_LOG_LABEL)
        paths = _git_bytes(
            repo, "ls-files", "-z", "--", *EXCLUDED, env=env, label=_LOG_LABEL
        )
        _git_bytes(
            repo,
            "update-index",
            "--force-remove",
            "-z",
            "--stdin",
            env=env,
            data=paths,
            label=_LOG_LABEL,
        )
        entries = _entries(
            _git_bytes(
                repo,
                "ls-files",
                "-s",
                "-z",
                "--",
                PLUGIN_ROOT,
                env=env,
                label=_LOG_LABEL,
            )
        )
        _reject_links(entries)
        for mode, sha, path in entries:
            if not path.endswith(".md") or path == README:
                continue
            rel = path[len(PLUGIN_ROOT) + 1 :]
            data = _git_bytes(repo, "cat-file", "blob", sha, label=_LOG_LABEL)
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                sys.exit(f"[{_LOG_LABEL}] ✗ UTF-8 이 아니다: {path}")
            new = _transform(rel, text)
            if new != text:
                _git(
                    repo,
                    "update-index",
                    "--cacheinfo",
                    f"{mode},{_hash(repo, new.encode())},{path}",
                    env=env,
                    label=_LOG_LABEL,
                )
        components = bt._require(
            bt._require(policy.get("source"), "_meta", "source"),
            "componentDirs",
            "source._meta",
        )
        present = {
            c
            for c in components
            if any(p.startswith(f"{PLUGIN_ROOT}/{c}/") for _m, _s, p in entries)
        }
        replacements = {
            ROOT_MANIFEST: _manifest_text(policy, target, ssot, present),
            README: HERMES_README,
        }
        for path, text in replacements.items():
            _git(
                repo,
                "update-index",
                "--cacheinfo",
                f"100644,{_hash(repo, text.encode())},{path}",
                env=env,
                label=_LOG_LABEL,
            )
        tree = _git(repo, "write-tree", env=env, label=_LOG_LABEL)
    _assert_hermes_edition(repo, source, tree, replacements[ROOT_MANIFEST])
    return tree


# --- 결과 판정 ----------------------------------------------------------------------------------------


def _assert_hermes_edition(
    repo: Path, source: str, tree: str, manifest_text: str
) -> None:
    """결과 트리 판정 — 변환 코드와 따로, 결과 트리와 원본 blob 을 다시 읽어 본다. 어긋나면 exit 1."""
    entries = _entries(
        _git_bytes(
            repo, "ls-tree", "-r", "-z", tree, "--", PLUGIN_ROOT, label=_LOG_LABEL
        )
    )
    _reject_links(entries)
    files = {path[len(PLUGIN_ROOT) + 1 :]: sha for _mode, sha, path in entries}

    def text_of(rel: str) -> str:
        return _git_bytes(
            repo, "cat-file", "blob", files[rel], label=_LOG_LABEL
        ).decode("utf-8")

    removed = [
        r
        for r in files
        if any(
            f"{PLUGIN_ROOT}/{r}".startswith(e + "/") or f"{PLUGIN_ROOT}/{r}" == e
            for e in EXCLUDED
        )
    ]
    if removed:
        sys.exit(
            f"[{_LOG_LABEL}] ✗ 뺀 경로가 결과 트리에 남았다: "
            + ", ".join(sorted(removed))
        )
    native = [n for n in bt.HERMES_NATIVE_MANIFESTS if n in files]
    if native:
        sys.exit(
            f"[{_LOG_LABEL}] ✗ {', '.join(native)} 가 있다 — Hermes 가 네이티브로 읽고 plugin.json 을 보지 않는다"
        )
    if ".claude-plugin/plugin.json" not in files:
        sys.exit(
            f"[{_LOG_LABEL}] ✗ {CLAUDE_MANIFEST} 가 없다 — export_harness.py 의 플러그인 루트 확인에 쓰인다"
        )
    root_text = text_of(bt.AP_V1_MANIFEST_NAME)
    try:
        root_manifest = json.loads(root_text)
    except ValueError as err:
        sys.exit(f"[{_LOG_LABEL}] ✗ {ROOT_MANIFEST} 를 JSON 으로 읽지 못했다: {err}")
    problems = (
        bt.ap_v1_violations(root_manifest)
        if isinstance(root_manifest, dict)
        else ["객체가 아니다"]
    )
    if problems or root_text != manifest_text:
        sys.exit(
            f"[{_LOG_LABEL}] ✗ {ROOT_MANIFEST} AP v1 판정 실패 또는 계산값과 다름 — "
            + "; ".join(problems)
        )
    if text_of("README.md") != HERMES_README:
        sys.exit(f"[{_LOG_LABEL}] ✗ {README} 가 HERMES_README 로 교체되지 않았다")

    skill_dirs = {
        r.split("/")[1] for r in files if r.startswith("skills/") and r.count("/") >= 2
    }
    no_md = sorted(d for d in skill_dirs if f"skills/{d}/SKILL.md" not in files)
    if no_md:
        sys.exit(
            f"[{_LOG_LABEL}] ✗ SKILL.md 가 없는 스킬 디렉토리: " + ", ".join(no_md)
        )
    if len(skill_dirs) != EXPECTED_SKILL_COUNT:
        sys.exit(
            f"[{_LOG_LABEL}] ✗ 스킬이 정확히 {EXPECTED_SKILL_COUNT}종이어야 한다 — {len(skill_dirs)}종: "
            + ", ".join(sorted(skill_dirs))
        )
    skill_problems = [
        p
        for d in sorted(skill_dirs)
        for p in _skill_problems(
            f"skills/{d}/SKILL.md", text_of(f"skills/{d}/SKILL.md")
        )
    ]
    if skill_problems:
        sys.exit(
            f"[{_LOG_LABEL}] ✗ 스킬 frontmatter AP 제약 위반 — "
            + "; ".join(skill_problems)
        )
    if USING_SKILL not in files:
        sys.exit(f"[{_LOG_LABEL}] ✗ {USING_SKILL} 가 없다")
    using_fm = _frontmatter(text_of(USING_SKILL), USING_SKILL) or {}
    source_using = (
        _frontmatter(
            _blob_text(repo, source, f"{PLUGIN_ROOT}/{USING_SKILL}"), USING_SKILL
        )
        or {}
    )
    if using_fm.get("description") != HERMES_USING_DESCRIPTION:
        sys.exit(
            f"[{_LOG_LABEL}] ✗ {USING_SKILL}: description 이 Hermes 문구로 교체되지 않았다"
        )
    if using_fm.get("disable-model-invocation") is None or str(
        using_fm.get("disable-model-invocation")
    ) != str(source_using.get("disable-model-invocation")):
        sys.exit(
            f"[{_LOG_LABEL}] ✗ {USING_SKILL}: disable-model-invocation 은 원본 그대로 남아야 한다"
        )

    # 머리말 — 원본 blob 을 따로 스캔해 필요한 집합을 세고, 허용 목록·결과의 표지와 양방향으로 대조한다.
    docs = sorted(r for r in files if r.endswith(".md") and r != "README.md")
    need_missing: set[str] = set()
    need_iso = {f"agents/{a}.md" for a in ISOLATED_AGENTS}
    for rel in docs:
        original = _blob_text(repo, source, f"{PLUGIN_ROOT}/{rel}")
        if _MISSING_PATH_RE.search(original):
            need_missing.add(rel)
        if _ISOLATED_AGENT_RE.search(original):
            need_iso.add(rel)
    errors = []
    for name, need, allow in (
        ("MISSING_PATHS_DOCS", need_missing, MISSING_PATHS_DOCS),
        ("ISOLATION_NOTE_DOCS", need_iso, ISOLATION_NOTE_DOCS),
    ):
        if need - allow:
            errors.append(
                f"{name} 밖의 문서가 뺀 경로·수정 에이전트를 가리킨다 — 그 단계를 건너뛰어도 도는지 확인하고 목록에"
                f" 넣거나 문서를 고쳐라: {', '.join(sorted(need - allow))}"
            )
        if allow - need:
            errors.append(
                f"{name} 가 낡은 목록이다 — 더는 머리말이 필요 없는 문서: {', '.join(sorted(allow - need))}"
            )
    if errors:
        sys.exit(f"[{_LOG_LABEL}] ✗ " + " / ".join(errors))
    want = {
        HERMES_AGENT_NOTE: {r for r in docs if _AGENT_DOC_RE.fullmatch(r)},
        HERMES_ISOLATION_NOTE: set(ISOLATION_NOTE_DOCS),
        HERMES_MISSING_PATHS_NOTE: set(MISSING_PATHS_DOCS),
    }
    for note, expected in want.items():
        have = {r for r in docs if _note_marker(note) in text_of(r)}
        if have != expected:
            sys.exit(
                f"[{_LOG_LABEL}] ✗ 머리말 `{_note_marker(note)}` 배치가 틀렸다 — 빠짐: "
                f"{', '.join(sorted(expected - have)) or '-'} / 남는 곳: {', '.join(sorted(have - expected)) or '-'}"
            )


# --- 출력: --out --------------------------------------------------------------------------------------


def _forbidden_roots(repo: Path) -> list[Path]:
    roots = {
        repo.resolve(),
        Path(_git(repo, "rev-parse", "--show-toplevel", label=_LOG_LABEL)).resolve(),
    }
    common = (
        repo / _git(repo, "rev-parse", "--git-common-dir", label=_LOG_LABEL)
    ).resolve()
    roots.add(common)
    if common.name == ".git":
        roots.add(common.parent)
    return sorted(roots)


def _out_dir(repo: Path, raw: str) -> Path:
    """`--out` 경로를 **한 번만** resolve 해 레포 밖·비어 있음을 확인한 결과를 돌려준다(그 값을 끝까지 쓴다)."""
    dest = Path(raw).expanduser().resolve()
    for root in _forbidden_roots(repo):
        if dest == root or root in dest.parents:
            sys.exit(
                f"[{_LOG_LABEL}] ✗ --out 이 레포 안 경로다({root}) — 실측 입력은 레포 밖에 둔다: {dest}"
            )
    if dest.exists():
        if not dest.is_dir():
            sys.exit(f"[{_LOG_LABEL}] ✗ --out 이 디렉토리가 아니다: {dest}")
        if any(dest.iterdir()):
            sys.exit(
                f"[{_LOG_LABEL}] ✗ --out 디렉토리가 비어 있지 않다 — 덮어쓰지 않는다: {dest}"
            )
    return dest


def _export_files(repo: Path, entries: list[tuple[str, str, str]], dest: Path) -> None:
    for mode, sha, path in entries:
        rel = path[len(PLUGIN_ROOT) + 1 :]
        target = (dest / rel).resolve()
        if dest not in target.parents:
            sys.exit(f"[{_LOG_LABEL}] ✗ 내보낼 경로가 --out 밖을 가리킨다: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_git_bytes(repo, "cat-file", "blob", sha, label=_LOG_LABEL))
        target.chmod(0o755 if mode == "100755" else 0o644)


def _verify_export(repo: Path, entries: list[tuple[str, str, str]], dest: Path) -> None:
    """내보낸 파일 집합·blob sha·실행 비트를 트리 항목과 대조한다."""
    expected = {
        path[len(PLUGIN_ROOT) + 1 :]: (mode, sha) for mode, sha, path in entries
    }
    found: dict[str, Path] = {}
    for dirpath, dirnames, filenames in os.walk(dest):
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            if p.is_symlink():
                sys.exit(f"[{_LOG_LABEL}] ✗ 대조 실패 — 내보낸 곳에 심링크: {p}")
        for name in filenames:
            p = Path(dirpath) / name
            found[p.relative_to(dest).as_posix()] = p
    if set(found) != set(expected):
        extra, lost = (
            sorted(set(found) - set(expected)),
            sorted(set(expected) - set(found)),
        )
        sys.exit(
            f"[{_LOG_LABEL}] ✗ 대조 실패 — 파일 집합이 트리와 다르다. 더 있음: {extra[:5]} / 없음: {lost[:5]}"
        )
    order = sorted(found)
    if any("\n" in str(found[r]) for r in order):
        sys.exit(f"[{_LOG_LABEL}] ✗ 대조 불가 — 줄바꿈이 든 경로")
    # `--no-filters` — 레포 밖 경로라 속성(gitattributes)을 찾지 않고 바이트 그대로 해시한다.
    paths = "".join(f"{found[r]}\n" for r in order)
    shas = (
        _git_bytes(
            repo,
            "hash-object",
            "--no-filters",
            "--stdin-paths",
            data=paths.encode("utf-8", errors="surrogateescape"),
            label=_LOG_LABEL,
        )
        .decode()
        .split()
    )
    bad = [
        r
        for r, got in zip(order, shas)
        if got != expected[r][1]
        or bool(found[r].stat().st_mode & 0o100) != (expected[r][0] == "100755")
    ]
    if bad or len(shas) != len(order):
        sys.exit(
            f"[{_LOG_LABEL}] ✗ 대조 실패 — 내용·실행 비트가 트리와 다르다: {bad[:5]}"
        )


# --- 출력: --write ------------------------------------------------------------------------------------


def _commit_details(repo: Path, source: str) -> tuple[str, str]:
    _policy, _target, ssot = _source_policy(repo, source)
    version = ssot.get("version", "?")
    message = (
        f"hermes: v{version} from {source[:7]}\n\n"
        f"Hermes 판(Agent Plugins v1) — {len(EXCLUDED)}개 경로 제외, 루트 plugin.json 을 AP v1 매니페스트로 교체,"
        " using-hiway-kit description 교체, Hermes 머리말·판 README (scripts/build-hermes-branch.py)."
    )
    return str(version), message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="판 트리를 계산·판정하고 sha 출력 (enabled 무관)",
    )
    mode.add_argument(
        "--out",
        metavar="DIR",
        help="판의 plugins/common 을 레포 밖 빈 디렉토리에 내보낸다",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="refs/heads/<branch> 갱신 (hermes 타겟 enabled:true 필요)",
    )
    parser.add_argument("--source", default="HEAD", help="원본 커밋 (기본 HEAD)")
    parser.add_argument(
        "--branch", default=DEFAULT_BRANCH, help=f"대상 브랜치 (기본 {DEFAULT_BRANCH})"
    )
    parser.add_argument("--repo", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    source = _rev(args.repo, args.source)
    if source is None:
        sys.exit(f"[{_LOG_LABEL}] ✗ 원본 커밋을 찾지 못했다: {args.source}")
    if args.write:
        _policy, target, _ssot = _source_policy(args.repo, source)
        if target.get("enabled") is not True:
            reason = target.get("_disabledReason", "(사유 없음)")
            print(
                f"[{_LOG_LABEL}] ✗ --write 거부 — {POLICY} 의 '{TARGET_ID}' 타겟이 enabled:true 가 아니다"
                f" (enabled={target.get('enabled')!r}). 사유: {reason}"
            )
            return 1
    dest = _out_dir(args.repo, args.out) if args.out else None
    tree = derive_tree(args.repo, source)
    plugin_tree = _git(
        args.repo, "rev-parse", f"{tree}:{PLUGIN_ROOT}", label=_LOG_LABEL
    )
    if args.check:
        skills = {
            p.split("/")[3]
            for p in _git(
                args.repo,
                "ls-tree",
                "-r",
                "--name-only",
                tree,
                "--",
                f"{PLUGIN_ROOT}/skills",
                label=_LOG_LABEL,
            ).splitlines()
        }
        print(f"[{_LOG_LABEL}] ✓ 판 트리 {tree} (원본 {source[:7]})")
        print(f"[{_LOG_LABEL}] plugin tree: {plugin_tree}")
        print(f"[{_LOG_LABEL}] skills: {len(skills)}")
        return 0
    if dest is not None:
        entries = _entries(
            _git_bytes(
                args.repo,
                "ls-tree",
                "-r",
                "-z",
                tree,
                "--",
                PLUGIN_ROOT,
                label=_LOG_LABEL,
            )
        )
        dest.mkdir(parents=True, exist_ok=True)
        _export_files(args.repo, entries, dest)
        _verify_export(args.repo, entries, dest)
        print(
            f"[{_LOG_LABEL}] ✓ --out {dest} — 파일 {len(entries)}개, plugin tree {plugin_tree} 와 일치"
            f" (원본 {source[:7]})"
        )
        return 0
    _write_edition_branch(
        args.repo,
        source,
        tree,
        args.branch,
        plugin_root=PLUGIN_ROOT,
        commit_details=_commit_details,
        label=_LOG_LABEL,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
