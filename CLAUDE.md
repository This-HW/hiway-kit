# hiway-kit

> Universal Claude Code toolkit — agents and skills for software development.
> Claude Code is the full-feature baseline; other harnesses get the partial support in README's capability table.

## Who this is for (design north-star)

This is a **published plugin installed into other people's projects**, not a tool for this
repo alone. Every design decision is judged by: **does this work in a consumer's
environment** — where the plugin's files live in the plugin cache (not the project cwd),
where MCP servers may be absent or different, where hooks run on every session? A change
that only works in this repo is a defect. (Concrete gate in the Contributing checklist.)

**Interoperability is a first-class goal**: the kit must compose cleanly with other
plugins (e.g., other workflow/methodology plugins) and with whatever MCP servers the user has (memory MCPs,
search MCPs, private/company servers). Three rules: never *assume* a specific plugin/MCP
is present; never *conflict* with one that is; *leverage* generically when available
(e.g., recall-before-plan / remember-after-done if memory-style tools exist — fail-open
otherwise). Guidance lives in skills, never in agent `tools:` allowlists.

## Installation

```bash
# Anthropic 디렉토리 — Claude Code 내장 마켓플레이스(추가 불필요). 아래 직접 경로와 **둘 중 하나만**
/plugin install hiway-kit@anthropic-plugin-directory
# 직접 마켓플레이스 — main HEAD 즉시 반영
/plugin marketplace add This-HW/hiway-kit
/plugin install hiway-kit@hiway-kit

# Full (+ pre-commit) — setup.sh installs the DIRECT path; uninstall the directory one first
git clone https://github.com/This-HW/hiway-kit && cd hiway-kit && ./setup.sh
```

> 디렉토리 경로는 **로그인 없는 빈 설정에서 실측**한 뒤 적었다(2026-10-05) — 확인 전 명령을 적는 것은 "약속 ≠ 실물" 결함이다.

## Structure

```
plugins/
└── common/      — Core agents (15) + skills (15) + rules (12) + hooks
```

`plugins/common/` contains:

- `.claude-plugin/plugin.json` — plugin manifest
- `agents/` — agent `.md` files
- `skills/` — skill `.md` files
- `hooks/` — Python hook scripts (common only)
- `tools/` — Python tools skills call (not hooks — see Hooks)
- `rules/` — governance rules (common only)
- `assets/icon.png` — plugin icon (Codex manifest `interface.logo`·`composerIcon`; directory listings)
- `.codex-plugin/plugin.json`, `plugin.json` — **생성물**. Codex·Antigravity 타겟 매니페스트로,
  `.claude-plugin/plugin.json` 을 SSOT 삼아 `scripts/build-targets.py` 가 만든다. 손으로 고치지 말 것
  (`verify-done.sh` §14가 드리프트를 exit 1로 잡는다). 정책은 레포 루트 `packaging/targets.json`

## Key Skills

| Skill                    | Command                     | Description                                     |
| ------------------------ | --------------------------- | ----------------------------------------------- |
| plan-task                | `/plan-task`                | Structured task planning                        |
| auto-dev                 | `/auto-dev`                 | Automated development pipeline                  |
| web-research             | `/web-research`             | Multi-source research (MCP if installed, else built-in) |
| review                   | `/review`                   | Code review: ruff + review-code + security-scan |
| multi-perspective-review | `/multi-perspective-review` | 3-Round Deliberation with 10 perspectives       |
| debug                    | `/debug`                    | 4-Phase debug pipeline                          |
| test                     | `/test`                     | Run tests and auto-fix failures                 |
| agent-creator            | `/agent-creator`            | Create a **project/user** agent (`.claude/agents/`) — not kit agents (see Adding a New Agent) |
| brainstorming            | `/brainstorming`            | Design a Large feature before plan-task          |
| using-hiway-kit          | (injected, manual-only)     | Workflow chain by task size                     |
| control-loop              | `/control-loop`             | Multi-session control discipline — investigate/decide/dispatch/verify/merge |
| child-session              | (loaded, not invoked)       | Discipline a dispatched worker session loads at start |
| native-watch             | `/native-watch`             | **Repo-only** (`.claude/skills/`) — audit native-feature absorption vs the kit (SSOT: docs/native-absorption.md) |
| self-improve             | `/self-improve`             | **Repo-only** (`.claude/skills/`) — propose agent/skill/rule improvements from ledger+evals (proposal-only, gated) |
| harness-export           | `/harness-export`           | Export host-neutral rules to AGENTS.md + GEMINI.md for hosts without hooks (drift-gated) |
| eval-forge               | `/eval-forge`               | **Repo-only** (`.claude/skills/`) — forge an eval scenario from an observed defect — generated + self-validated |
| skill-forge              | `/skill-forge`              | Distill a solved hard problem into a reusable skill draft (proposal-only)         |
| cross-engine-review      | `/cross-engine-review`      | Evidence-backed consensus between sessions on **different engines** (Claude ↔ Codex ↔ …) |

## Agent Architecture

### 2-Tier Model

```
Tier 1: plugins/common/  — All projects (15 agents)
Tier 2: project-local/   — Project-specific (user-added)
```

### Agent Frontmatter

Every agent is a `.md` file with YAML frontmatter:

```yaml
---
name: agent-name # kebab-case, matches filename
description: | # Korean + English trigger conditions
  MUST USE when: "keywords"
  OUTPUT: result format
model: sonnet # opus | sonnet | haiku
effort: medium # low | medium | high | max
maxTurns: 20 # value is owned by each agent's frontmatter
isolation: worktree # optional: file-modifying agents only
tools:
  - Read
  - Edit
  - Bash
  - ExitWorktree # required with isolation: worktree
disallowedTools:
  - Task # regular agents cannot spawn sub-agents
---
```

### Model Selection

| Model      | Use case                   | Examples                              |
| ---------- | -------------------------- | ------------------------------------- |
| **Opus**   | Strategy, analysis, review | clarify-requirements, review-code     |
| **Sonnet** | Code implementation, fixes | implement-code, fix-bugs, write-tests |
| **Haiku**  | Quick checks               | verify-code, git-workflow             |

### isolation: worktree

Apply to agents that **modify files** — prevents filesystem conflicts:

- ✅ implement-code, fix-bugs, write-tests, sync-docs
- ❌ review-code, plan-implementation, define-business-logic, design-user-journey (read-only — they return analysis, the caller writes)

Merge-back protocol (exit conditions, sequential merge, conflict escalation) is
governed by `plugins/common/rules/parallel-worktree.md`.

### Delegation Signal — 폐기됨 (2026-08-27)

에이전트 출력 끝에 붙던 `---DELEGATION_SIGNAL---` 블록은 **폐기됐다.** 파싱하는 결정론적
코드가 어디에도 없었고(유일한 소비 지점이 «신호를 스캔해 다음 에이전트를 호출하라»는
자연어 지시였다), 오케스트레이션은 이미 스킬 주도 플랫 위임으로 넘어가 있었다.
**비결정적 보조 경로는 없는 것보다 나쁘다**는 판정이다.

산문의 `DELEGATE_TO: X` 같은 **에스컬레이션 의도 서술**은 기계 계약이 아니므로 유지한다.
폐기 경위·근거·걷어낸 범위(에이전트 33종·스킬 4종·주입 규칙 2종·게이트 §12·eval 체크 타입)는
`docs/architecture/delegation-signal-retirement.md` 가 소유한다 — **§12 번호는 재사용하지
않고 비워 둔다**(스펙·CHANGELOG 가 섹션 번호로 게이트를 참조한다).

## Development Conventions

### Editing an agent/skill does NOT affect the current session

Agents and skills are loaded from the **installed plugin cache**
(`~/.claude/plugins/cache/<marketplace>/hiway-kit/<version>[-<sha>]/`), not from this
repo's working tree. So editing `plugins/common/agents/*.md` and immediately dispatching
that agent runs the **old** definition — the change is invisible until the version is
bumped, pushed, and the plugin updated.

This bit us in 2.14.0 development: `review-code`'s output contract was buried 496 lines
from the end of its definition, its reports came back empty twice, and the working-tree
fix could not be verified in the same session. Two consequences:

- **Never conclude "the definition change worked" from in-session behavior.** Verify by
  reading the file, or by a machine check (`verify-done.sh` § checks against the working
  tree; `§12`, the check this incident motivated, is retired — see Delegation Signal above).
- To actually exercise a definition change, bump the version and reinstall
  (`/plugin marketplace update` → `/plugin install`), or point a scratch install at the
  working tree.

Hooks and `scripts/` are different — hooks run from `${CLAUDE_PLUGIN_ROOT}` (also the
cache), but `scripts/`, `evals/` and `tests/` (hook tests live in `tests/hooks/` since v5.0.0 — they are not shipped) are repo-local and take effect immediately.

### Adding a New Agent

1. Create `plugins/common/agents/{name}.md` — flat only (Claude Code hides subfolder agents;
   `check_doc_counts.py` fails on any subdirectory)
2. Add required frontmatter (see template above)
3. Write Korean description with `MUST USE when:` trigger conditions
4. No manifest edit needed — agents are auto-discovered from the directory
   (plugin.json has no agent/skill registry)
5. Add it to the roster in `plugins/common/rules/agent-system.md` (CHECKSUMS + mirror), classify it
   in `evals/policy.json` `tiers`, and add the scenario + baseline its tier requires
   (`scripts/check_eval_coverage.py` is the gate). `/agent-creator` is for consumer agents, not this

### Adding a New Skill

1. Create `plugins/common/skills/{name}/SKILL.md`
2. Optionally add `README.md` in the same directory
3. No manifest edit needed — skills are auto-discovered from the directory

### Naming Conventions

- Agents: `verb-noun.md` (fix-bugs, implement-code, review-code)
- Skills: `noun-action` (web-research, plan-task, auto-dev)
- All agent names must be kebab-case and match the `name:` frontmatter field

### Sub-agent Rules

- Regular agents: `disallowedTools: [Task]` — cannot spawn sub-agents
- Meta agent (`devils-advocate` — the only one since v5.0.0; the multi-perspective-review roles it used to share with 4 others are now skill steps): `disallowedTools: [Bash]`
- Skills (auto-dev, etc.) drive delegation; leaf agents stay flat — a deliberate choice: native
  subagents may nest up to three levels by default.

### Orchestration Model — Scale-Appropriate Primitives

오케스트레이션은 전통이 아니라 **스케일별로 올바른 프리미티브**를 쓴다. leaf 에이전트가
Task를 갖지 않는 이유는 "main만 조율" 도그마가 아니라, 우리 스케일에서 에이전트 중첩이
성능 이득 없이 예측불가능성·디버깅 부채만 더하기 때문이다.

킷이 **소비자에게** 제공하는 모델이다(이 레포 자체의 협업 수단은 `coordination.md`).

| 병렬 청크 수(파일 수 아님) | 오케스트레이션 |
| --------- | -------------- |
| 수 개 | 스킬 주도 플랫 위임 (main이 Agent 병렬 dispatch → 결과 수집). 예측가능·검증된 경로 |
| 10~100+ | 네이티브 workflow(`ultracode` 등)를 **사용자가 opt-in** — auto-dev는 청크로 분할해 안내 |

> 워크플로는 사용자 opt-in(키워드·이름 호출·allow 규칙)이 있어야 돈다 — 스킬이 스스로 켜지 않는다
> (판정·근거: `docs/native-absorption.md`). 작업 크기(Small/Medium/Large) 기준은 `plan-task` 의 `elicitation.md §6`.

### Phase Gate Pattern

```
Phase 1 (Planning)    → P0 ambiguity = 0 (criteria: rules/agent-system.md Phase Gate)
Phase 2 (Development) → implement based on Phase 1 artifacts
Phase 3 (Validation)  → spec compliance, then review + security scan (auto-dev T-*)
```

## Hooks

Located in `plugins/common/hooks/` (except `session-check.py`, which lives in
`plugins/common/setup/`):

- `session-check.py` — `SessionStart` environment/setup check (runs before
  `session-start.py`; registered from `setup/`). **Writes nothing into the consumer's
  repo** (until v5.0.0 it silently installed `setup/pre-commit` in plugin-only mode —
  installation is now `setup.sh` only). Warnings go out as `systemMessage` (a
  SessionStart hook's stderr is seen by no one) and only for real defects: python below the 3.9
  floor, missing global setup (setup.sh users only), a project `.claude/{agents,skills}` entry whose
  **name collides** with a plugin one (project-local agents alone never warn), and a **stale venv**
  (`.venv`/`venv` console-script shebangs still pointing at the project's old
  path after a directory move/copy — `bin/python` keeps working while every
  script dies with `bad interpreter`, or silently runs the old site-packages)
- `session-start.py` — injects rules + active plan status (`docs/plans/*/plan.md`, status≠done) at `SessionStart`
- `protect-sensitive.py` — `PreToolUse` on Edit/Write/MultiEdit/NotebookEdit/Read:
  blocks access to **sensitive file paths** (`.env`, keys, `.pem`) by path. env
  templates (`.env.example`/`.sample`/`.template`/`.dist`) are exempt; writes to
  them get a best-effort high-confidence secret-format content scan. It
  does **not** otherwise scan file *content* or intercept `Bash`/`git commit` —
  secret scanning is gitleaks at push time — CI, and `verify-done.sh` §24 locally over
  unpushed commits. `setup/pre-commit` does **not** run gitleaks.
- `auto-format.py` — auto-formats code after edits (`PostToolUse`): ruff for Python (≤2 runs);
  prettier/eslint **only when the project has them in `node_modules/.bin`** — never `npx`
  (it looked up the registry on every Markdown edit). Whole hook fits a 25 s budget (< 30 s timeout)
- `stop-validator.py` — on `Stop`, lints edited `.py` (ruff) and runs pytest on
  the test files this session edited (never the full suite — that's CI/`/test`'s
  job); on failure emits native `{"decision":"block","reason":...}` so Claude
  continues and auto-fixes. Timeouts are non-blocking (`CLAUDE_STOP_TEST_TIMEOUT`).
  If git reports no modified `.py`, it returns **before reading the transcript**; ruff runs
  only on files auto-format could not see (e.g. written via Bash). Everything fits 110 s (< 120 s)
- Stop state reuses `$TMPDIR/claude-{uid}` only when it is an owned, non-symlink
  directory with mode `0700`. Unsafe or unavailable stable state uses a private
  temporary directory for that process; it never trusts counters from the shared
  temporary root. This fallback loses cross-process marker/retry reuse.
- `utils.py` — shared utilities

### 스킬 도구는 `tools/` 에 둔다 (v5.2.0)

OpenAI 디렉토리 포털은 `hooks/` 가 **있기만 해도** 거부해 제출본이 그것을 통째로 뺀다 —
스킬이 부르는 도구(checklist·feedback_ledger·export_harness)는 `tools/` 에 둔다. 3.9 floor·fail-open 은 훅과 같다.

### git 훅은 배포되지만 자동으로 켜지지 않는다

`plugins/common/setup/` 에는 세션 훅이 아닌 **git 훅** 정본도 있다 — `pre-commit`
(ruff·JSON·frontmatter·비공개 이름 검사 — gitleaks 는 없다)과 `git-hooks/reference-transaction`(레퍼런스 변경 가드). `setup.sh`
가 `pre-commit` 을 설치하고, `reference-transaction` 은 **opt-in** 이라 켜지 않은 것이
결함이 아니다.

**"배포됐다"와 "설치돼서 실제로 돈다"는 다른 상태다.** 정본을 고쳐도 각자의
`.git/hooks/` 에 있는 사본은 그대로이므로, 고친 사람만 그 훅이 도는 줄 안다. 이
결함 클래스를 실제로 밟은 뒤 `verify-done.sh` §21(`scripts/check_installed_hooks.py`)이
설치된 사본과 레포 정본을 대조한다 — 미설치(opt-in)와 낡은 설치를 구분해서 보고한다.

Hooks are defined in `plugins/common/hooks/hooks.json` using the **exec form**
(`command` + `args[]`) so `${CLAUDE_PLUGIN_ROOT}` paths need no shell quoting.

**Python floor: 3.9** — hooks run on the *consumer's* `python3`, and macOS still
ships 3.9.x. So hook sources must stay 3.9-loadable: use
`from __future__ import annotations` and keep 3.10-only syntax out of anything
evaluated at import time. This is enforced twice, not by convention: ruff's `FA`
rules (statically, via root `ruff.toml`) and the `python39-compat` CI job (it
actually loads every hook under 3.9). Four hooks were silently dead on 3.9 until
2.12.1 — that is the failure this guards against.

> Subagent lifecycle tracking is delegated to native OpenTelemetry
> (`agent_id` / `parent_agent_id` spans, `/usage` breakdown) — the kit no longer
> ships a custom `agent-lifecycle.py` (removed in 2.6.0).

### 설정값으로 경로를 만들면 반드시 봉쇄한다 (2026-08-27 확정)

@docs/conventions/path-containment.md

## Security

- `gitleaks` scans **every commit** in each push/PR range, merge side branches included
  (config `.gitleaks.toml`, per-finding ignores `.gitleaksignore`, pin `.gitleaks-version`);
  `verify-done.sh` §24 runs the same scan on unpushed commits before you push
- Never hardcode secrets, API keys, internal IPs, or project names
- `protect-sensitive.py` runs as a `PreToolUse` hook on Edit/Write/MultiEdit/NotebookEdit/Read — path-based (plus a best-effort content scan only for env-template writes), not commit-based (see Hooks section)

## CI/CD

`.github/workflows/validate.yml` runs on push to `main` (and PRs) and **owns its step list** — read it;
most steps call the same scripts as `verify-done.sh`.

### 드리프트 게이트는 통합하지 않는다

생성물·사본이 SSOT 와 일치하는지 묻는 게이트가 여럿이지만 입력·판정·실패 메시지가 전부 달라
**통합하지 않는다** — 게이트는 읽기 쉬워야 red 가 떴을 때 믿고 고친다. 무엇이 드리프트 게이트인지는
`scripts/verify-done.sh` 가 소유한다(여기 열거하지 않는다). 판정·근거·재검토 경위: `docs/conventions/no-gate-integration.md`.

### Lint is one ruleset, everywhere

@docs/conventions/lint-single-ruleset.md

### Rules have a long-form mirror — and it is checksum-guarded

@docs/conventions/rules-mirror.md

### Shell is linted too

@docs/conventions/shell-lint.md

### 경고는 상시 참이 되면 죽는다

@docs/conventions/warning-signal.md

## Release Checklist

**CRITICAL: Every commit that changes plugin behavior MUST bump the version** — via
`scripts/bump-version.sh <ver>`, never by hand. Plugin cache is keyed by version: same version = users never get the fix.
절차(CHANGELOG·타겟 재생성·`AGENTS.md` 재생성·룰 sha·CHECKSUMS·미러·행동 eval·태그·게이트)의 정본은
`docs/conventions/release-process.md` 다. 배포 채널별 상태는 `docs/marketplace-submission.md` 상단 요약표가 소유한다.

## Contributing

PRs welcome. Checklist:

- [ ] **Consumer-first**: works in an installing user's environment, not just this repo —
      no reliance on the project cwd containing plugin files, no assumption a specific MCP
      server is installed, hooks fail-open when their assumptions don't hold
- [ ] No `mcp__*` tools in any agent `tools:` allowlist (MCP lives in skills — see
      `docs/architecture/rules/mcp-usage.md` §4; absent MCP in an agent allowlist hallucinates, CC #13898)
- [ ] Agent frontmatter has `name`, `description`, `model`, `maxTurns`
- [ ] No forbidden fields: `permissionMode`, `context_cache`, `output_schema`, `next_agents`, inline `hooks`
- [ ] Description includes `MUST USE when:` trigger conditions
- [ ] File-modifying agents have `isolation: worktree`
- [ ] Regular agents have `disallowedTools: [Task]`
- [ ] Skill `description` field is in English
- [ ] Version bumped with `scripts/bump-version.sh` + matching `CHANGELOG.md` entry
      (the manifest has **no** agent/skill registry — both are auto-discovered from their
      directories; the only thing a new component must touch there is the version)
- [ ] `scripts/verify-done.sh` green locally and CI green

@docs/conventions/coordination.md
