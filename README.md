# hiway-kit

> Universal agent toolkit by [This-HW](https://github.com/This-HW) — 15 agents + 15 skills for software development, packaged for **Claude Code**, **Codex** and **Antigravity**.

A focused, single-plugin AI agent system built for Claude Code. Covers the full software development lifecycle: planning, implementation, review, testing, and meta-tooling. (Not a TUI component library or a scaffolding installer — this is the agents + skills plugin.)

Validation hardening covers packaging input paths, literal hook commands, agent
description budgets, malformed eval inputs, and private Stop-hook state. See the
[changelog](CHANGELOG.md) for the fixes and their scope.

Docs & blog: **[hiway.thishw.com](https://hiway.thishw.com/)** (English · [한국어](https://hiway.thishw.com/ko/))

A single, well-tested core plugin built on a native-first foundation, scale-appropriate orchestration, a feedback learning loop, loop engineering, and a Definition-of-Done gate. (see [CHANGELOG](CHANGELOG.md) · [docs/specs/](docs/specs/))

**Who this is for (design north-star):** a plugin installed into *your* projects — not a tool for this repo alone. Every change is judged by whether it works in a consumer's environment: plugin files live in the plugin cache (not your project cwd), MCP servers may be absent or different, and hooks run on every session. A change that only works in this repo is a defect.

---

## Quick Install

**Prerequisites:** [Claude Code CLI](https://code.claude.com) installed (`claude --version`).
The hooks run on your machine's `python3` and need **3.9+** (macOS system Python
qualifies); older interpreters make the hooks no-ops and the session warns you once.

**Install** — pick **one** of the two (installing both loads every skill and hook twice):

```bash
# A. Anthropic's directory — built into Claude Code, no marketplace to add
/plugin install hiway-kit@anthropic-plugin-directory

# B. This repository as a marketplace — tracks main the moment you update it
/plugin marketplace add This-HW/hiway-kit
/plugin install hiway-kit@hiway-kit
/plugin marketplace update hiway-kit   # later, to pick up a new version
```

Path A is the reviewed listing: each version reaches it after Anthropic's directory scan, so it can
trail `main` briefly. Both paths were verified on a clean Claude Code config (no claude.ai sign-in)
on 2026-10-05. The listing does not yet show up in claude.ai's web directory search; the install
command above works regardless.

## Installing changes the whole machine, not just this project

Plugins install at **user scope**, so installing, updating or removing one changes hook
registration and rule injection for **every session on this machine — including ones running
right now**. A session that started under a previous install keeps its already-injected
context, but its hooks may stop resolving mid-flight.

Do it when no long-running work is in progress, or accept that in-flight sessions should be
restarted afterward. There is also **no plugin aliasing**: two differently-named plugins that
ship the same skills both register, silently, because the dedup key is
`<plugin name>:<skill name>` (measured — `docs/specs/2026-09-07-rename-probe.md`). Never run
two kits that carry the same skills at once.

## Full Mode (Security Hooks + Auto-format)

```bash
git clone https://github.com/This-HW/hiway-kit
cd hiway-kit
./setup.sh
```

Options:

- `./setup.sh --status` — Check setup state
- `./setup.sh --migrate` — Run from your project: moves only the `.claude/agents`·`.claude/skills` entries whose **name collides** with a plugin one into `*.bak/` (your own project-local agents stay put)
- `./setup.sh --force` — Reset and re-run setup

---

### Keep your private project names out of commits

Pattern-based scanners can't catch an arbitrary private name — you'd have to write the name
into a committed config, and that file then *is* the leak. So the list lives in a
**gitignored local file** and the pre-commit hook reads it:

```bash
printf 'my-internal-project\nacme-codename\n' > .private-names   # already in .gitignore
```

Any staged file containing one of those strings blocks the commit — **provided the hook
installed in your repo is the one carrying this check**. With no `.private-names` the check
is skipped and says so — it never reports protection it isn't providing.

> **Check before you rely on it**: `grep -c private-names "$(git rev-parse --git-path hooks)/pre-commit"`.
> A `0` means your installed hook predates this feature and the guard is **not** active.
> Nothing installs this hook for you at session start — since v5.0.0 the plugin never writes into
> your `.git/hooks/` (earlier versions silently installed it in plugin-only mode). Install it
> explicitly with `./setup.sh`, or copy `plugins/common/setup/pre-commit` over your hook (that
> overwrites local edits to it, so diff first if you customized it).

This exists because it actually happened: on 2026-09-08 a private project name reached three
design documents and the repo's gitleaks rule caught **none** of them (its regex only matched
a `_suffix` form). Measured precision of that rule across full history: 4%.

## Other Harnesses (Codex · Antigravity)

kit's plugin root (`plugins/common/`) also ships **native plugin manifests** for
Codex and Antigravity, generated from the same source of truth as the Claude Code
manifest (`packaging/targets.json` + `scripts/build-targets.py` — see
[`packaging/README.md`](packaging/README.md)). What actually ships per platform
differs by platform capability, verified against the real CLIs (not assumed):

| Component | Codex | Antigravity |
| --- | --- | --- |
| Skills (15) | ✅ `"skills": "./skills/"` | ✅ recognized (real skills install and run correctly) |
| Rules (12) | ⚠ no dedicated field → carried via `AGENTS.md`/`GEMINI.md` (see [`/harness-export`](plugins/common/skills/harness-export/SKILL.md)) | ❌ **not recognized** — `agy plugin validate` output is byte-identical with and without `rules/`; it counts only skills·agents·commands·mcpServers·hooks. Norms reach Antigravity **only** through the entrypoint file |
| Agents (15) | ⚠ no dedicated field | ❌ **not supported** — `agy plugin validate` does not recurse into `agents/`'s category subdirectories (`dev`/`meta`/`planning`); it miscounts the category folders as agent entries and finds none of the real agents. No config exists to opt into recursion (confirmed against official docs and the plugin schema) |
| Hooks | ⚠ shipped (`session-start`, `auto-format`) but **skipped silently until you trust them** — see *Trusting Codex hooks* below. `protect-sensitive` is deliberately **not** shipped: hooks fired but the command still ran, so the block does not hold | ❌ not shipped this batch — format unverified |
| MCP servers | ❌ not bundled (kit doesn't ship MCP servers) | ❌ not bundled |

**Parity contract**: rules and skills (norms and procedures) work on every harness.
How they arrive differs, and the difference is measured, not assumed:

| | Claude Code | Codex | Antigravity |
| --- | --- | --- | --- |
| Rules | hook injection | **hook injection** (measured) — `AGENTS.md` is the fallback. Before 3.34.1 Codex cut the hook output at 2,500 tokens and the **middle rules were lost**; see the note below | `AGENTS.md`/`GEMINI.md` only |
| Ledger digest (memory) | hook injection | **hook injection** (measured); rules also tell the agent to fetch it itself | self-fetch per the rule |
| Skills | native | **all 15 recognized** (measured, v5.0.0) | recognized |
| Subagents | 15 agents | **not exposed** — skills degrade to in-session execution | not supported (nested layout) |
| Agent `model` / `effort` frontmatter | ✅ applied per agent | ❌ **not applied** — agents are shipped in the package but not exposed as subagents (measured: the files land in the installed plugin cache, but the Codex manifest has no agent field — `packaging/targets.json` `omit.agents`), so everything runs on the model/effort in the user's Codex config | ❌ not applied — agents are not recognized (see above) |
| Automatic blocking | `PreToolUse` veto | **no** — no blocking hook is shipped: in measurement a `PreToolUse` block did not stop the command, so `protect-sensitive` is left out (see *Hooks* above) | no |

**Codex hook output limit (fixed in 3.34.1).** Codex trims any hook's `additionalContext`
above 2,500 tokens (≈ bytes / 4) down to a head + tail preview, and the kit's output was
over that — in a measured session 16,622 B went in and 10,028 B reached the model; three
rules in the middle (Feedback Loop, Loop Engineering, Parallel Worktree) never arrived.
The earlier "memory arrives intact" result was wrong: that probe only checked the *first*
LESSONS line, which survives a middle cut every time. The generated Codex hook now sets
`additionalContextLimit: 0` (no trimming), so the kit's own injection budget gate is the
only limit. **Codex will ask you to trust the hook once more** after this update, because
the trust hash covers the whole handler config.

Put plainly: **what a non-Claude-Code harness loses is dedicated executors (subagents)
and automatic blocking.** Injection is no longer on that list for Codex. Everything else
keeps working, because it depends only on git and external processes, not on any
harness-specific runtime:
discipline (rules), procedure (skills), state (child session markers under
`gitdir/kit/child.json`), and the registry `describe` seam all carry over unchanged.
One caveat: behavioral evals (`evals/`) currently drive only Claude Code — the harness
call is centralized behind one seam (`evals/run.py`'s `Harness` protocol) but a
Codex/Antigravity implementation hasn't been built yet.

### Codex

```bash
# Add this repo (or your installed copy) as a plugin marketplace
codex plugin marketplace add /path/to/hiway-kit

# Install
codex plugin add hiway-kit@hiway-kit-marketplace

# Verify
codex plugin list   # shows hiway-kit@hiway-kit-marketplace

# Remove
codex plugin remove hiway-kit@hiway-kit-marketplace
codex plugin marketplace remove hiway-kit-marketplace
```

#### Trusting Codex hooks (do this once, or the norms never arrive)

Installing is not enough. Codex asks for **hook trust** before it will run a plugin's
hooks, and until you grant it the hooks are **skipped in silence** — no warning, no
error, and nothing in the session says the rules were not injected. Measured directly:
the same install answered `NONE` when asked about the completion gate, then answered
correctly once trust was in place.

- **Interactive `codex`**: start a session in the project once and approve the hook
  trust prompt. After that, `SessionStart` fires and the rules plus the feedback-ledger
  digest are injected the same way Claude Code injects them.
- **Non-interactive `codex exec`**: there is no prompt to answer, so hooks stay skipped
  unless you pass `--dangerously-bypass-hook-trust`. Read the flag's name literally —
  it bypasses the approval gate, so use it only where you already trust the plugin.

**Hooks are the better path, not the only one.** Even with hooks off, the norms still
reach Codex through the entrypoint file (`AGENTS.md`, see
[`/harness-export`](plugins/common/skills/harness-export/SKILL.md)), and a session can
fetch the ledger digest itself — the `feedback-loop` rule tells it how. What you lose
without trust is automatic delivery, not the discipline.

#### Skills that name a sub-agent: read them as a contract, not a transport

Codex loads all 15 skills, but it exposes **no sub-agents**. Skills that dispatch an agent
(`debug`, `review`, `test`, `auto-dev`, `multi-perspective-review`) name the agent as a contract.
Each of those skills now carries an explicit degradation path: the delegation is one
**transport**, and the invariant is the **contract** inside the block — persona, checks,
output format, completion declaration. On a harness with no delegation, perform the same
contract in the session itself and produce the same output. **Do not skip the step, and
do not report a delegation that did not happen.** The cost is stated in each skill:
performing it inline shares the session's context, so the blind-spot separation a
separate agent would give you is gone — which matters most for `review`'s adversarial
pass, where the isolation is part of the value.

Codex also reads the repo's existing `.claude-plugin/marketplace.json` as a legacy
path, alongside the generated `.agents/plugins/marketplace.json`. Public listing in
the shared ChatGPT/Codex plugin directory requires OpenAI's submission review —
not done; install via a local/Git marketplace as above works today.

### Antigravity

```bash
# Validate first (checks the manifest and component dirs)
agy plugin validate /path/to/hiway-kit/plugins/common

# Install
agy plugin install /path/to/hiway-kit/plugins/common

# Verify
agy plugin list   # shows hiway-kit

# Remove
agy plugin uninstall hiway-kit
```

**No official public registry is confirmed for Antigravity** — Google's docs
describe only local/workspace installation, so that's the only supported path here.

---

## Architecture & Concepts

hiway-kit이 무엇을 어떻게 융합하는지 — 한눈에 보는 설계 원리.

### 설계 철학 — 네이티브 우선, kit은 의견 레이어

> **기술부채의 최대 원천은 Claude Code가 네이티브로 하는 일을 자체 구현으로 중복하는 것이다.**

네이티브 프리미티브(agents·skills·hooks·dynamic workflows·OTEL·memory)는 거의 매주
진화한다. 그래서 이 kit의 가치는 **인프라가 아니라, 그 위에 얹는 "의견이 담긴
에이전트·스킬·규율 레이어"** 다. 관측·위임·훅 실행 같은 인프라는 네이티브에 위임하고,
손으로 만든 대체물은 삭제한다 → zero-debt.

### 네 갈래의 융합

| 갈래 | 무엇을 가져왔나 | kit에서 |
| --- | --- | --- |
| **Claude Code 네이티브** | agents, skills, hooks, dynamic workflow, OTEL, memory | 토대 프리미티브 — 매니페스트 의존성, exec-form 훅, `decision:block` 자동수정, 네이티브 관측 |
| **개발 방법론 규율** | brainstorming→plan→execute, phase gate, TDD, verification-before-completion | `brainstorming → plan-task → auto-dev` HARD-GATE 체인, Iron Law 검증 |
| **Hermes 피드백 루프** | "메모리·피드백 루프가 코어" | validation 결함 → feedback ledger → 다음 구현 컨텍스트 주입 (학습 루프) |
| **계획 파일 규약** | 파일 기반 진행 추적 | `docs/plans/<slug>/plan.md`·checklist.json — 포맷은 [`plan-format.md`](plugins/common/skills/plan-task/references/plan-format.md) |

### Harness × Loop Engineering

두 상보 개념이 kit의 자율성을 만든다:

- **Harness Engineering** — *어디서·무엇으로* 행동하는가. 컨텍스트 주입(session-start),
  도구 큐레이션(per-agent tools), 가드레일(protect-sensitive·stop-validator), 계획 파일(plan.md·checklist).
- **Loop Engineering** — *얼마나 오래·끈질기게* 행동하는가. 승인된 배치를 P0·완료·가드
  전까지 자율 완주. 게이트(설계·사람 멈춤)와 루프(실행·자율)를 분리한다.

### 결합 방식

```
 [설계 게이트 — 사람 승인]              [실행 루프 — 자율 완주]
 brainstorming → plan-task    ──승인──▶  auto-dev 배치 드라이버
 (무엇을 만들지 HARD-GATE)               (TaskList 폴링 + 종료 가드)
                                              │
        ┌─────────────────────────────────────┤ 스케일별 오케스트레이션
        ▼                                     ▼
   Small/Medium: 스킬 주도 플랫 dispatch   Large: 네이티브 ultracode
        │                                     │
        ▼  validation (review + security)     ▼
   Stop 훅 block 자동수정 마이크로루프
        │
        ▼  결함 → feedback ledger → 다음 세션 LESSONS 주입  ◀─┐
        └──────────────────── 학습 루프 ──────────────────────┘
```

세부는 SSOT 문서 참조: [CLAUDE.md](CLAUDE.md) (오케스트레이션·규율),
[docs/specs/](docs/specs/) (설계 스펙), `plugins/common/rules/` (규칙).

---

## 핵심 개념 & AI 엔지니어링 로직

kit에 녹아 있는 개념과 그 장점 — *어떻게* 구현되는지와 함께.

| 개념 / 로직 | kit에서 어떻게 | 장점 |
| --- | --- | --- |
| **Native-first (zero-debt)** | 네이티브 프리미티브를 최대 활용하고 자체 중복 구현은 삭제 | 유지보수 부채 0, 네이티브가 진화해도 항상 최신 |
| **Phase-gate discipline** | `brainstorming → plan-task → auto-dev` HARD-GATE 체인 | 모호성 100% 제거 후 구현 → 재작업·헛수고 최소화 |
| **Verification-before-completion (DoD)** | Iron Law + `scripts/verify-done.sh` 기계 게이트 | 증거 없는 "완료" 주장을 구조적으로 차단 |
| **경계 검사의 완료 조건화** | 프로젝트에 경계 검사 도구(import-linter·dependency-cruiser 등)가 있으면 계획의 `## 완료 조건` 으로 태운다 — [`boundary-check.md`](plugins/common/skills/plan-task/references/boundary-check.md) | 설계로 정한 모듈 경계가 다음 변경에서 조용히 깨지는 것을 명령으로 막음 (도구가 없으면 없다고 적고 도입은 사용자 결정) |
| **Loop engineering** | 게이트(사람 멈춤) vs 루프(자율 완주) 분리 + 배치 드라이버 + 종료 가드 | P0 전까지 자율 완주, 런어웨이 방지 |
| **Feedback learning loop** (Hermes) | validation 결함 → ledger(상한·중복제거·감쇠) → 다음 세션 `=== LESSONS ===` 주입 | 같은 실수를 반복하지 않음 |
| **Scale-appropriate orchestration** | Small/Medium 스킬 주도 플랫, Large 네이티브 `ultracode` 위임 | 스케일별 최적, main 컨텍스트 병목 회피 |
| **Adversarial review** | `review-code`가 4 페르소나(hacker·murphy·future-self·picky-user)로 침투 검토 | 버그·엣지케이스를 능동 발굴 |
| **Multi-perspective deliberation** | 10 관점 × 3 라운드 합의(`/multi-perspective-review`) + devil's advocate | 설계 사각지대 제거 |
| **Agent specialization** | 15 전문 에이전트 × 모델 티어(Opus 전략 / Sonnet 구현 / Haiku 탐색) | 작업별 최적 모델·비용 |
| **Worktree isolation** | 파일 수정 에이전트를 격리 git worktree에서 실행 | 병렬 작업 충돌 방지 |
| **Harness engineering** | 컨텍스트 주입(session-start)·도구 큐레이션·가드레일 훅·계획 파일 | 환경이 모델을 올바른 궤도로 유지 |
| **SSOT governance** | `rules/` + decisions 추적 + 거버넌스/시크릿 보호 훅 | 일관성·감사 가능성 |

> 심화 리서치 노트: [하네스 엔지니어링 & 루프 엔지니어링 — 2026 중반 지형도](docs/research/2026-07-harness-loop-engineering.md)
> (개념 계보 · 3대 루프 구현체 · 검증 원칙 · 병렬 에이전트 도구 생태계 · kit 대조)

## Works with your MCPs (memory 등)

kit은 **특정 MCP 서버를 가정하지 않습니다** (consumer-first). 대신 세션에 있는 MCP를
일반화된 방식으로 활용합니다:

- **메모리형 MCP** (`recall`/`search`/`remember` 류 툴 — [basic-memory](https://github.com/basicmachines-co/basic-memory),
  [agentcairn](https://github.com/ccf/agentcairn), 사내/개인 메모리 서버 등 무엇이든):
  kit 워크플로가 **계획 전 recall → 완료 후 remember** 패턴으로 자동 활용합니다.
  없으면 조용히 스킵 — 설치 의무 없음.
- **충돌 없음**: kit 에이전트는 MCP 툴을 허용목록에 하드코딩하지 않습니다
  (`rules/mcp-usage.md`) — 어떤 MCP 조합에서도 환각·충돌 없이 동작합니다.
- 다른 플러그인·MCP와의 호환은 kit의 **명시적 설계 목표**입니다 — 함께 설치된 플러그인의
  존재를 가정하지도, 충돌하지도 않으며, 단독으로도 자급자족합니다.

---

## What's Included

| Plugin            | Agents | Skills | Description                               |
| ----------------- | ------ | ------ | ----------------------------------------- |
| `hiway-kit` | 15     | 15     | Core: planning, development, review, meta |

v5.0.0 cut the kit roughly in half, down to what earns its place: components with a native
equivalent, that no skill ever invoked, or that only worked inside this repository were removed —
see the migration table in [CHANGELOG](CHANGELOG.md).

---

## Architecture

### 2-Tier Agent Model

```
Tier 1: plugins/common/  — Core agents for all projects (15 agents)
Tier 2: project-local/   — Project-specific agents (user-defined)
```

### Phase Gate Pattern

Larger work follows a 3-phase gate; small fixes don't need the ceremony:

```
Phase 1 (Planning)     → Remove ambiguity (brainstorming only for Large new features)
Phase 2 (Development)  → Implement based on Phase 1 artifacts
Phase 3 (Validation)   → Review + security scan
```

### Delegation Signal — removed in v2.16.0

Agents used to end every response with a structured `---DELEGATION_SIGNAL---` block so that
main Claude could read `TYPE`/`TARGET` and auto-invoke the next agent. **That contract is gone.**
Nothing parsed it, and sequencing already came from the invoking skill. Full rationale:
`docs/specs/2026-08-27-delegation-signal-contract-review.md`.

### Model Selection

| Model      | Use Case                   | Examples                                                     |
| ---------- | -------------------------- | ------------------------------------------------------------ |
| **Opus**   | Strategy, analysis, review | `clarify-requirements`, `review-code`, `plan-implementation` |
| **Sonnet** | Code implementation, fixes | `implement-code`, `fix-bugs`, `write-tests`                  |
| **Haiku**  | Quick checks               | `verify-code`, `git-workflow`, `analyze-dependencies`        |

### Worktree Isolation

File-modifying agents run in an isolated git worktree to prevent conflicts:
`implement-code`, `fix-bugs`, `write-tests`, `sync-docs`.

Merge-back rules (verify-then-exit, sequential merge, conflict escalation to
`git-workflow`) live in `rules/parallel-worktree.md`.

---

## Components (Core)

### Key Skills

| Skill                      | Command                     | Description                                                                |
| -------------------------- | --------------------------- | -------------------------------------------------------------------------- |
| `brainstorming`            | `/brainstorming`            | Design and spec for Large new features, before planning                    |
| `plan-task`                | `/plan-task`                | Structured planning into `docs/plans/<date>-<slug>/plan.md`                |
| `auto-dev`                 | `/auto-dev`                 | Run a completed plan through development and validation                    |
| `web-research`             | `/web-research`             | Research with whatever search/docs/browser tools the session has           |
| `review`                   | `/review`                   | Lint + adversarial `review-code` + `security-scan` (also works on Codex)   |
| `multi-perspective-review` | `/multi-perspective-review` | 3-round deliberation across perspectives, consensus-driven                 |
| `debug`                    | `/debug`                    | Diagnose an error, fix it with `fix-bugs`, confirm with `verify-code`      |
| `test`                     | `/test`                     | Run tests and fix failures                                                 |
| `agent-creator`            | `/agent-creator`            | Create a project agent in `.claude/agents/` with valid frontmatter         |
| `control-loop`             | `/control-loop`             | Coordinate worker sessions — investigate, decide, dispatch, verify, merge  |
| `child-session`            | (loaded by workers)         | Discipline a dispatched worker session follows                             |
| `cross-engine-review`      | `/cross-engine-review`      | Evidence-backed consensus between sessions on different engines            |
| `harness-export`           | `/harness-export`           | Export host-neutral rules to `AGENTS.md`/`GEMINI.md` for other harnesses   |
| `skill-forge`              | `/skill-forge`              | Distill a solved hard problem into a reusable skill draft                  |
| `using-hiway-kit`          | (injected at session start) | Workflow chain and plan file rules                                         |

### Planning Agents (3 — Opus)

Used in Phase 1. They return analysis; the caller writes any files.

| Agent                   | Description                                                                   |
| ----------------------- | ----------------------------------------------------------------------------- |
| `clarify-requirements`  | Detects ambiguous requests, generates P0/P1/P2 questions                      |
| `define-business-logic` | Defines policies, rules, calculations, state transitions (CALC/VAL/STATE/POL) |
| `design-user-journey`   | User flows, screens, onboarding, state transitions                            |

### Meta Agent (1 — Opus)

| Agent             | Description                                                                                         |
| ----------------- | --------------------------------------------------------------------------------------------------- |
| `devils-advocate` | Failure scenario analysis via 4 attack personas (scalability / dependency / maintainability / cost) |

### Dev Agents (11)

| Agent                  | Model  | Description                                                                |
| ---------------------- | ------ | -------------------------------------------------------------------------- |
| `plan-implementation`  | Opus   | Requirements → tech decisions → task breakdown → risk analysis             |
| `implement-code`       | Sonnet | Code implementation (worktree isolated)                                    |
| `write-tests`          | Sonnet | Unit / integration / API / E2E tests (worktree isolated)                   |
| `review-code`          | Opus   | Adversarial review via 4 personas: hacker, murphy, future-self, picky-user |
| `fix-bugs`             | Sonnet | Minimal-change bug fixes (worktree isolated)                               |
| `verify-code`          | Haiku  | Type check, lint, build, test execution                                    |
| `security-scan`        | Sonnet | OWASP Top 10, secret exposure, vulnerable component detection              |
| `git-workflow`         | Haiku  | Branches, merges, rebases; reports conflicts instead of guessing           |
| `sync-docs`            | Haiku  | API and architecture documentation sync (worktree isolated)                |
| `analyze-dependencies` | Haiku  | Dependency versions, impact range, security updates                        |
| `research-external`    | Sonnet | External library / technology / best practice research                     |

---

## Typical Workflows

### Feature Development

```
clarify-requirements → design-user-journey → define-business-logic
  → plan-implementation → implement-code → write-tests → verify-code
  → review-code + security-scan (parallel) → fix-bugs → sync-docs
```

### Multi-perspective Review

```
/multi-perspective-review
  → the main session picks the perspectives
  → Round 1: perspective reviews in parallel (devils-advocate among them)
  → Round 2: the main session consolidates and resolves conflicts
```

### Debug

```
/debug
  → diagnose → fix-bugs → verify-code → (loop until green)
```

---

## Security

- **Hooks:** `protect-sensitive.py` runs on Edit/Write/MultiEdit/NotebookEdit/Read — blocks access to sensitive file paths (`.env`, keys). It does not scan commits; secret scanning of this repository is gitleaks in CI (every commit in each push/PR range) and `scripts/verify-done.sh` §24 locally.
- **Auto-format:** `auto-format.py` runs after edits (uses ruff for Python)
- **Policy:** Never hardcode API keys, secrets, or internal IPs

## Data handling

The plugin collects nothing and sends nothing anywhere.
The full policy is in [PRIVACY.md](PRIVACY.md).

- **No network calls.** The shipped hooks (`plugins/common/hooks/`) and skill tools
  (`plugins/common/tools/`) make no HTTP or socket connections. They only run local commands: `git`, the formatter/linter for the edited file
  (e.g. `ruff`), `pytest` on test files you edited, and verification commands you define in a
  plan checklist.
- **No telemetry, no accounts, no personal data.** The plugin does not read, store, or transmit
  personal data.
- **What it writes stays on your machine.** The feedback ledger (recurring review findings) is
  kept under your repository's `.git/kit/` (untracked; outside a git repo it falls back to a
  file in the project); hook state and locks live in a per-user `0700` directory under your
  system temp dir. Delete them at any time.
- **Web access is your agent's, not the plugin's.** Skills such as `web-research` tell the agent
  to use search/browser tools *you* have installed; the plugin itself ships no connector.

---

## Project Structure

```
plugins/
└── common/      — Core agents (15) + skills (15) + rules (12) + hooks
```

The plugin contains:

- `.claude-plugin/plugin.json` — plugin manifest
- `agents/` — agent `.md` files with YAML frontmatter
- `skills/` — skill `.md` files
- `hooks/` — Python hook scripts
- `rules/` — governance rules

---

## Contributing

PRs welcome. Checklist:

- [ ] **Consumer-first**: works in an installing user's environment (plugin files in the cache, not project cwd; no assumed MCP server; hooks fail-open) — not just this repo
- [ ] No `mcp__*` tools in any agent `tools:` allowlist (MCP lives in skills; absent MCP in an agent allowlist hallucinates, CC #13898)
- [ ] Agent frontmatter has `name`, `description`, `model`, `maxTurns`
- [ ] Description includes `MUST USE when:` trigger conditions
- [ ] No forbidden fields: `permissionMode`, `context_cache`, `output_schema`, `next_agents`, inline `hooks`
- [ ] File-modifying agents have `isolation: worktree`
- [ ] Regular agents have `disallowedTools: [Task]`
- [ ] Skill `description` field is in English
- [ ] Registered in `plugin.json` (with `homepage`, `repository`, `license`, `author.email`)
- [ ] CI passes (JSON valid, frontmatter complete, no forbidden fields, pytest green, no secrets)

---

## License

MIT

### Collaboration across harnesses

Shared isolation, integration and cleanup responsibilities are separated from runtime-specific
execution in the [control-loop transport guide](docs/control-loop-transport.md). It covers external
orchestration, native subagents, large parallel workflows and single-session execution.
The [repository collaboration choice](docs/conventions/coordination.md) applies to this repository,
not to projects that install the kit.
