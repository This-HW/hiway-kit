# hiway-kit

> Universal agent toolkit by [This-HW](https://github.com/This-HW) — 32 agents + 21 skills for software development, packaged for **Claude Code**, **Codex** and **Antigravity**.

A focused, single-plugin AI agent system built for Claude Code. Covers the full software development lifecycle: planning, implementation, review, testing, and meta-tooling. (Not a TUI component library or a scaffolding installer — this is the agents + skills plugin.)

Docs & development log: **[this-hw.github.io/hiway-kit](https://this-hw.github.io/hiway-kit/)** (한국어 · [English](https://this-hw.github.io/hiway-kit/en/))

A single, well-tested core plugin built on a native-first foundation, scale-appropriate orchestration, a feedback learning loop, loop engineering, and a Definition-of-Done gate. (see [CHANGELOG](CHANGELOG.md) · [docs/specs/](docs/specs/))

**Who this is for (design north-star):** a plugin installed into *your* projects — not a tool for this repo alone. Every change is judged by whether it works in a consumer's environment: plugin files live in the plugin cache (not your project cwd), MCP servers may be absent or different, and hooks run on every session. A change that only works in this repo is a defect.

---

## Quick Install

**Prerequisites:** [Claude Code CLI](https://code.claude.com) installed (`claude --version`).
The hooks run on your machine's `python3` and need **3.9+** (macOS system Python
qualifies); older interpreters make the hooks no-ops and the session warns you once.

**Install** (marketplace name: `hiway-kit`):

```bash
/plugin marketplace add This-HW/hiway-kit
/plugin install hiway-kit@hiway-kit

# Updating: refresh the marketplace, then the new version is picked up
/plugin marketplace update hiway-kit
```

> **Registry status — read this before looking for it in the catalog.** `hiway-kit` is
> **not yet in Anthropic's community catalog**. Listing is a one-time web submission and
> ours is pending, so **the command above is currently the only install path**. This note
> stays until the listing is live — an unverified claim of registry presence is exactly the
> "promise ≠ reality" defect this kit's gates exist to catch.

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
- `./setup.sh --migrate` — Migrate from legacy `.claude/agents/` setup
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
> `session-check.py` installs `setup/pre-commit` only when no `pre-commit` hook exists yet —
> it never replaces an existing one, so a repo set up before this release keeps its old hook
> indefinitely. Copy `plugins/common/setup/pre-commit` over it to upgrade (it overwrites any
> local edits to that hook, so diff first if you customized it).

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
| Skills (21) | ✅ `"skills": "./skills/"` | ✅ recognized (real skills install and run correctly) |
| Rules (15) | ⚠ no dedicated field → carried via `AGENTS.md`/`GEMINI.md` (see [`/harness-export`](plugins/common/skills/harness-export/SKILL.md)) | ❌ **not recognized** — `agy plugin validate` output is byte-identical with and without `rules/`; it counts only skills·agents·commands·mcpServers·hooks. Norms reach Antigravity **only** through the entrypoint file |
| Agents (32) | ⚠ no dedicated field | ❌ **not supported** — `agy plugin validate` does not recurse into `agents/`'s category subdirectories (`backend`/`dev`/`meta`/`planning`); it miscounts the 4 category folders as agent entries and finds none of the real 32. No config exists to opt into recursion (confirmed against official docs and the plugin schema) |
| Hooks | ⚠ shipped (`session-start`, `auto-format`) but **skipped silently until you trust them** — see *Trusting Codex hooks* below. `protect-sensitive` is deliberately **not** shipped: hooks fired but the command still ran, so the block does not hold | ❌ not shipped this batch — format unverified |
| MCP servers | ❌ not bundled (kit doesn't ship MCP servers) | ❌ not bundled |

**Parity contract**: rules and skills (norms and procedures) work on every harness.
How they arrive differs, and the difference is measured, not assumed:

| | Claude Code | Codex | Antigravity |
| --- | --- | --- | --- |
| Rules | hook injection | **hook injection** (measured) — `AGENTS.md` is the fallback | `AGENTS.md`/`GEMINI.md` only |
| Ledger digest (memory) | hook injection | **hook injection** (measured); rules also tell the agent to fetch it itself | self-fetch per the rule |
| Skills | native | **all 21 recognized** (measured) | recognized |
| Subagents | 32 agents | **not exposed** — skills degrade to in-session execution | not supported (nested layout) |
| Automatic blocking | `PreToolUse` veto | **no** — the hook runs but cannot veto | no |

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

Codex loads all 21 skills, but it exposes **no sub-agents**. Four skills (`debug`,
`review`, `test`, `skill-creator`) contain `Task tool 사용:` / `subagent_type:` blocks.
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
| **superpowers 규율** | brainstorming→plan→execute, phase gate, TDD, verification-before-completion | `brainstorming → plan-task → auto-dev` HARD-GATE 체인, Iron Law 검증 |
| **Hermes 피드백 루프** | "메모리·피드백 루프가 코어" | validation 결함 → feedback ledger → 다음 구현 컨텍스트 주입 (학습 루프) |
| **자체 Work 시스템** | 파일 기반 감사 가능 추적 | `docs/works/` Work ID·progress.md·decisions.md |

### Harness × Loop Engineering

두 상보 개념이 kit의 자율성을 만든다:

- **Harness Engineering** — *어디서·무엇으로* 행동하는가. 컨텍스트 주입(session-start),
  도구 큐레이션(per-agent tools), 가드레일(protect-sensitive·stop-validator), Work 메모리.
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
   continueOnBlock 자동수정 마이크로루프
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
| **Loop engineering** | 게이트(사람 멈춤) vs 루프(자율 완주) 분리 + 배치 드라이버 + 종료 가드 | P0 전까지 자율 완주, 런어웨이 방지 |
| **Feedback learning loop** (Hermes) | validation 결함 → ledger(상한·중복제거·감쇠) → 다음 세션 `=== LESSONS ===` 주입 | 같은 실수를 반복하지 않음 |
| **Scale-appropriate orchestration** | Small/Medium 스킬 주도 플랫, Large 네이티브 `ultracode` 위임 | 스케일별 최적, main 컨텍스트 병목 회피 |
| **Adversarial review** | `review-code`가 4 페르소나(hacker·murphy·future-self·picky-user)로 침투 검토 | 버그·엣지케이스를 능동 발굴 |
| **Multi-perspective deliberation** | 10 관점 × 3 라운드 합의(`/multi-perspective-review`) + devil's advocate | 설계 사각지대 제거 |
| **Agent specialization** | 32 전문 에이전트 × 모델 티어(Opus 전략 / Sonnet 구현 / Haiku 탐색) | 작업별 최적 모델·비용 |
| **Worktree isolation** | 파일 수정 에이전트를 격리 git worktree에서 실행 | 병렬 작업 충돌 방지 |
| **Harness engineering** | 컨텍스트 주입(session-start)·도구 큐레이션·가드레일 훅·Work 메모리 | 환경이 모델을 올바른 궤도로 유지 |
| **SSOT governance** | `rules/` + decisions 추적 + 거버넌스/시크릿 보호 훅 | 일관성·감사 가능성 |

> 심화 리서치 노트: [하네스 엔지니어링 & 루프 엔지니어링 — 2026 중반 지형도](docs/research/2026-07-harness-loop-engineering.md)
> (개념 계보 · 3대 루프 구현체 · 검증 원칙 · 병렬 에이전트 도구 생태계 · kit 대조)

## Works with superpowers

[obra/superpowers](https://github.com/obra/superpowers) 플러그인과 **상호보완**하도록 설계됐습니다 — 둘을 같이 켜도 충돌·중복이 없습니다.

- **각자 자동 적용**: 둘 다 세션 시작에 자기 메타스킬을 자동 주입 (`using-hiway-kit` / `using-superpowers`). 수동 호출 불필요.
- **중복 제거**: `using-hiway-kit`은 범용 스킬 규율(1% 룰·red flags)을 superpowers에 양보하고, **kit 고유 델타**(에이전트맵·Work 시스템·native/loop/DoD)만 제공 → 병행 시 중복 0.
- **역할 분담**: superpowers = 방법론 지휘자, hiway-kit = 실행 레이어(전문 에이전트·auto-dev 파이프라인·hooks·Work 추적).
- **시너지**: kit의 Definition-of-Done(기계 게이트) + superpowers의 verification-before-completion(원칙)이 상호보강.
- **단독 동작**: superpowers 없이 hiway-kit만으로도 자급자족.

## Works with your MCPs (memory 등)

kit은 **특정 MCP 서버를 가정하지 않습니다** (consumer-first). 대신 세션에 있는 MCP를
일반화된 방식으로 활용합니다:

- **메모리형 MCP** (`recall`/`search`/`remember` 류 툴 — [basic-memory](https://github.com/basicmachines-co/basic-memory),
  [agentcairn](https://github.com/ccf/agentcairn), 사내/개인 메모리 서버 등 무엇이든):
  kit 워크플로가 **계획 전 recall → 완료 후 remember** 패턴으로 자동 활용합니다.
  없으면 조용히 스킵 — 설치 의무 없음.
- **충돌 없음**: kit 에이전트는 MCP 툴을 허용목록에 하드코딩하지 않습니다
  (`rules/mcp-usage.md`) — 어떤 MCP 조합에서도 환각·충돌 없이 동작합니다.
- 다른 플러그인·MCP와의 호환은 kit의 **명시적 설계 목표**입니다 (superpowers 병행이
  그 예시).

---

## What's Included

| Plugin            | Agents | Skills | Description                               |
| ----------------- | ------ | ------ | ----------------------------------------- |
| `hiway-kit` | 32     | 21     | Core: planning, development, review, meta |

---

## Architecture

### 2-Tier Agent Model

```
Tier 1: plugins/common/  — Core agents for all projects (32 agents)
Tier 2: project-local/   — Project-specific agents (user-defined)
```

### Phase Gate Pattern

All workflows follow a 3-phase gate:

```
Phase 1 (Planning)     → Remove 100% ambiguity via planning agents
Phase 2 (Development)  → Implement based on Phase 1 artifacts
Phase 3 (Validation)   → Parallel review + security scan
```

### Delegation Signal — removed in v2.16.0

Agents used to end every response with a structured `---DELEGATION_SIGNAL---` block so that
main Claude could read `TYPE`/`TARGET` and auto-invoke the next agent. **That contract is gone.**

Two findings retired it. First, **nothing parsed it** — a full sweep of `hooks/`, `skills/`,
`scripts/` and `rules/` found no deterministic consumer; the one place that referenced it was a
rule telling main Claude to scan for it, which is an instruction to a model, not a parser.
Second, **orchestration had already moved on**: sequencing comes from the invoking skill
(see [Orchestration Model](CLAUDE.md)), not from a signal embedded in agent output.

Delegation itself is unchanged — main Claude still dispatches agents and collects their results.
What disappeared is the machine-readable block, not the delegation.

Full rationale and the exact removal scope: `docs/specs/2026-08-27-delegation-signal-contract-review.md`.

### Model Selection

| Model      | Use Case                   | Examples                                                     |
| ---------- | -------------------------- | ------------------------------------------------------------ |
| **Opus**   | Strategy, analysis, review | `clarify-requirements`, `review-code`, `plan-implementation` |
| **Sonnet** | Code implementation, fixes | `implement-code`, `fix-bugs`, `write-tests`                  |
| **Haiku**  | Exploration, quick checks  | `explore-codebase`, `verify-code`, `enforce-structure`       |

### Worktree Isolation

File-modifying agents run in an isolated git worktree to prevent conflicts:

- `implement-code`, `fix-bugs`, `write-tests`, `write-api-tests`
- `implement-api`, `generate-boilerplate`, `sync-docs`, `optimize-logic`

Merge-back rules (verify-then-exit, sequential merge, conflict escalation to
`git-workflow`) live in `rules/parallel-worktree.md`.

---

## Components (Core)

### Key Skills

| Skill                      | Command                     | Description                                                                |
| -------------------------- | --------------------------- | -------------------------------------------------------------------------- |
| `plan-task`                | `/plan-task`                | 5-phase planning pipeline: explore → clarify → journey → logic → implement |
| `auto-dev`                 | `/auto-dev`                 | Full automated development pipeline                                        |
| `web-research`             | `/web-research`             | MCP-powered research: Context7 (docs) + Exa (code) + Tavily (web)          |
| `review`                   | `/review`                   | Code review pipeline: ruff + review-code + security-scan                   |
| `multi-perspective-review` | `/multi-perspective-review` | 3-Round Deliberation: 10 perspectives, consensus-driven                    |
| `doc-coauthoring`          | `/doc-coauthoring`          | AI-assisted documentation authoring and review                             |
| `debug`                    | `/debug`                    | 4-Phase debug: diagnose → fix-bugs → verify-code                           |
| `test`                     | `/test`                     | Run tests and auto-fix failures via verify-code + fix-bugs                 |
| `agent-creator`            | `/agent-creator`            | Generate hiway-kit plugin agents with correct frontmatter            |
| `skill-creator`            | `/skill-creator`            | Generate hiway-kit skills with best practices                        |
| `mcp-builder`              | `/mcp-builder`              | Scaffold MCP servers and configure Claude Code integration                 |
| `native-watch`             | `/native-watch`             | Audit native-feature absorption against the SSOT ledger (`docs/native-absorption.md`) |
| `self-improve`             | `/self-improve`             | Propose agent/skill improvements from ledger + evals — proposal-only, double-gated    |
| `harness-export`           | `/harness-export`           | Export host-neutral rules to `AGENTS.md` so Codex/OpenCode/Pi/Hermes share the discipline |
| `eval-forge`               | `/eval-forge`               | Forge an eval scenario from an observed defect — generated, self-validated, atomic        |
| `skill-forge`              | `/skill-forge`              | Distill a solved hard problem into a reusable skill draft — proposal-only, 3-condition    |

### Planning Agents (5 — Opus)

Read-only. No file modifications. Used in Phase 1.

| Agent                   | Description                                                                   |
| ----------------------- | ----------------------------------------------------------------------------- |
| `clarify-requirements`  | Detects ambiguous requests, generates P0/P1/P2 questions                      |
| `analyze-domain`        | DDD-based domain analysis, bounded context identification                     |
| `define-business-logic` | Defines policies, rules, calculations, state transitions (CALC/VAL/STATE/POL) |
| `design-user-journey`   | UX flows, screen design, onboarding, payment processes                        |
| `define-metrics`        | KPI, SLO, SLA, dashboard metric definitions                                   |

### Meta Agents (6 — Opus)

Orchestrate multi-perspective review workflows. No `Bash` access.

| Agent               | Description                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------------- |
| `facilitator`       | Analyzes what perspectives are needed, assigns agents                                               |
| `synthesizer`       | Consolidates Round 1/2 results, identifies conflicts and duplicates                                 |
| `devils-advocate`   | Failure scenario analysis via 4 attack personas (scalability / dependency / maintainability / cost) |
| `consensus-builder` | Conflict analysis across perspectives → Win-Win resolution                                          |
| `impact-analyzer`   | System-wide impact, risk, and development cost of proposed changes                                  |

### Backend Agents (4)

| Agent             | Model  | Description                                                |
| ----------------- | ------ | ---------------------------------------------------------- |
| `design-services` | Opus   | Clean/Hexagonal architecture, microservices, DDD patterns  |
| `implement-api`   | Sonnet | REST/GraphQL API implementation (Express, FastAPI, NestJS) |
| `write-api-tests` | Sonnet | API unit / integration / E2E tests                         |
| `optimize-logic`  | Sonnet | Algorithm optimization, caching, N+1 query fixes           |

### Dev Agents (18)

Core development workflow agents.

| Agent                  | Model  | Description                                                                |
| ---------------------- | ------ | -------------------------------------------------------------------------- |
| `explore-codebase`     | Haiku  | Project structure, dependencies, pattern analysis                          |
| `plan-implementation`  | Opus   | Requirements → tech decisions → task breakdown → risk analysis             |
| `implement-code`       | Sonnet | Code implementation (worktree isolated)                                    |
| `write-tests`          | Sonnet | Unit / integration / E2E tests (worktree isolated)                         |
| `review-code`          | Opus   | Adversarial review via 4 personas: hacker, murphy, future-self, picky-user |
| `fix-bugs`             | Sonnet | Minimal-change bug fixes (worktree isolated)                               |
| `verify-code`          | Haiku  | Type check, lint, build, test execution                                    |
| `security-scan`        | Sonnet | OWASP Top 10, secret exposure, vulnerable component detection              |
| `verify-integration`   | Haiku  | Connection integrity, data flow, version compatibility                     |
| `git-workflow`         | Sonnet | Branches, PRs, commit messages, merge strategies                           |
| `sync-docs`            | Sonnet | API and architecture documentation sync                                    |
| `plan-refactor`        | Opus   | Structural improvement planning, ARCHITECTURE_LIMIT resolution             |
| `analyze-dependencies` | Sonnet | Library versions, security updates                                         |
| `manage-api-versions`  | Opus   | API versioning strategy, migration, backwards compatibility                |
| `analyze-tech-debt`    | Sonnet | Code quality analysis, tech debt prioritization                            |
| `research-external`    | Sonnet | External library / technology / best practice research                     |
| `generate-boilerplate` | Sonnet | Project templates, base structure generation                               |
| `enforce-structure`    | Haiku  | File placement, naming convention compliance                               |

---

## Typical Workflows

### Feature Development

```
clarify-requirements → analyze-domain → design-user-journey → define-business-logic
  → plan-implementation → implement-code → write-tests → verify-code
  → review-code + security-scan (parallel) → fix-bugs → sync-docs
```

### Multi-perspective Review

```
/multi-perspective-review
  → facilitator (assigns perspectives)
  → [devils-advocate + synthesizer + impact-analyzer] (Round 1 parallel)
  → synthesizer (Round 2 consolidation)
  → consensus-builder (Round 3 resolution)
```

### Debug

```
/debug
  → diagnose → fix-bugs → verify-code → (loop until green)
```

---

## Security

- **Hooks:** `protect-sensitive.py` runs on Edit/Write/MultiEdit/NotebookEdit/Read — blocks access to sensitive file paths (`.env`, keys). Commit-time secret scanning is gitleaks + `setup/pre-commit`, not this hook.
- **Auto-format:** `auto-format.py` runs after edits (uses ruff for Python)
- **CI:** gitleaks scans all pushes to `main`
- **Policy:** Never hardcode API keys, secrets, or internal IPs

---

## Project Structure

```
plugins/
└── common/      — Core agents (32) + skills (21) + rules (15) + hooks
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
