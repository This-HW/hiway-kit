# hiway-kit

> Universal Claude Code toolkit — agents and skills for software development

## Who this is for (design north-star)

This is a **published plugin installed into other people's projects**, not a tool for this
repo alone. Every design decision is judged by: **does this work in a consumer's
environment** — where the plugin's files live in the plugin cache (not the project cwd),
where MCP servers may be absent or different, where hooks run on every session? A change
that only works in this repo is a defect. (Concrete gate in the Contributing checklist.)

**Interoperability is a first-class goal**: the kit must compose cleanly with other
plugins (e.g., superpowers) and with whatever MCP servers the user has (memory MCPs,
search MCPs, private/company servers). Three rules: never *assume* a specific plugin/MCP
is present; never *conflict* with one that is; *leverage* generically when available
(e.g., recall-before-plan / remember-after-done if memory-style tools exist — fail-open
otherwise). Guidance lives in skills, never in agent `tools:` allowlists.

## Installation

```bash
# Basic — direct marketplace (현재 **유일하게 성립하는** 설치 경로)
/plugin marketplace add This-HW/hiway-kit
/plugin install hiway-kit@hiway-kit

# Full (with security hooks + auto-format + pre-commit)
git clone https://github.com/This-HW/hiway-kit && cd hiway-kit && ./setup.sh
```

> **커뮤니티 카탈로그 경로는 아직 없다.** `hiway-kit` 은 미등재이고 재제출은 웹 폼이라
> 자동화할 수 없다(`docs/marketplace-submission.md`). 등재되기 전까지 카탈로그 설치
> 명령을 문서에 적지 않는다 — 없는 경로를 적는 것이 이 킷의 게이트들이 존재하는 이유인
> "약속 ≠ 실물" 결함이다.

## Structure

```
plugins/
└── common/      — Core agents (32) + skills (21) + rules (14) + hooks
```

`plugins/common/` contains:

- `.claude-plugin/plugin.json` — plugin manifest
- `agents/` — agent `.md` files
- `skills/` — skill `.md` files
- `hooks/` — Python hook scripts (common only)
- `rules/` — governance rules (common only)
- `.codex-plugin/plugin.json`, `plugin.json` — **생성물**. Codex·Antigravity 타겟 매니페스트로,
  `.claude-plugin/plugin.json` 을 SSOT 삼아 `scripts/build-targets.py` 가 만든다. 손으로 고치지 말 것
  (`verify-done.sh` §14가 드리프트를 exit 1로 잡는다). 정책은 레포 루트 `packaging/targets.json`

## Key Skills

| Skill                    | Command                     | Description                                     |
| ------------------------ | --------------------------- | ----------------------------------------------- |
| plan-task                | `/plan-task`                | Structured task planning                        |
| auto-dev                 | `/auto-dev`                 | Automated development pipeline                  |
| web-research             | `/web-research`             | MCP-powered research                            |
| review                   | `/review`                   | Code review: ruff + review-code + security-scan |
| multi-perspective-review | `/multi-perspective-review` | 3-Round Deliberation with 10 perspectives       |
| doc-coauthoring          | `/doc-coauthoring`          | AI-assisted documentation authoring             |
| debug                    | `/debug`                    | 4-Phase debug pipeline                          |
| test                     | `/test`                     | Run tests and auto-fix failures                 |
| agent-creator            | `/agent-creator`            | Generate plugin agents                          |
| skill-creator            | `/skill-creator`            | Generate plugin skills                          |
| mcp-builder              | `/mcp-builder`              | Scaffold MCP servers                            |
| control-loop              | `/control-loop`             | Multi-session control discipline — investigate/decide/dispatch/verify/merge |
| child-session              | (loaded, not invoked)       | Discipline a dispatched worker session loads at start |
| native-watch             | `/native-watch`             | Audit native-feature absorption vs the kit (SSOT: docs/native-absorption.md) |
| self-improve             | `/self-improve`             | Propose agent/skill/rule improvements from ledger+evals (proposal-only, gated) |
| harness-export           | `/harness-export`           | Export host-neutral rules to AGENTS.md + GEMINI.md for hosts without hooks (drift-gated) |
| eval-forge               | `/eval-forge`               | Forge an eval scenario from an observed defect — generated + self-validated       |
| skill-forge              | `/skill-forge`              | Distill a solved hard problem into a reusable skill draft (proposal-only)         |
| cross-engine-review      | `/cross-engine-review`      | Evidence-backed consensus between sessions on **different engines** (Claude ↔ Codex ↔ …) |

## Agent Architecture

### 2-Tier Model

```
Tier 1: plugins/common/  — All projects (32 agents)
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
maxTurns: 20 # 20 for implementation agents, 10 for exploration/review
isolation: worktree # optional: run in isolated git worktree
tools:
  - Read
  - Edit
  - Bash
disallowedTools:
  - Task # regular agents cannot spawn sub-agents
---
```

### Model Selection

| Model      | Use case                   | Examples                              |
| ---------- | -------------------------- | ------------------------------------- |
| **Opus**   | Strategy, analysis, review | clarify-requirements, review-code     |
| **Sonnet** | Code implementation, fixes | implement-code, fix-bugs, write-tests |
| **Haiku**  | Exploration, simple checks | explore-codebase, verify-code         |

### isolation: worktree

Apply to agents that **modify files** — prevents filesystem conflicts:

- ✅ implement-code, fix-bugs, write-tests, write-api-tests, implement-api, generate-boilerplate, sync-docs, optimize-logic
- ❌ explore-codebase, review-code, plan-implementation (read-only)

Merge-back protocol (exit conditions, sequential merge, conflict escalation) is
governed by `plugins/common/rules/parallel-worktree.md`.

### Delegation Signal — 폐기됨 (2026-08-27, W-022 R1)

에이전트 출력 끝에 붙던 `---DELEGATION_SIGNAL---` 블록은 **폐기됐다.** 파싱하는 결정론적
코드가 어디에도 없었고(유일한 소비 지점이 «신호를 스캔해 다음 에이전트를 호출하라»는
자연어 지시였다), 오케스트레이션은 이미 스킬 주도 플랫 위임으로 넘어가 있었다.
**비결정적 보조 경로는 없는 것보다 나쁘다**는 판정이다.

산문의 `DELEGATE_TO: X` 같은 **에스컬레이션 의도 서술**은 기계 계약이 아니므로 유지한다.
폐기 경위·근거·걷어낸 범위(에이전트 33종·스킬 4종·주입 규칙 2종·게이트 §12·eval 체크 타입)는
`docs/architecture/delegation-signal-retirement.md` 가 소유한다 — **§12 번호는 재사용하지
않고 비워 둔다**(스펙·decision-log 47곳 이상이 섹션 번호로 게이트를 참조한다).

## Development Conventions

### Editing an agent/skill does NOT affect the current session

Agents and skills are loaded from the **installed plugin cache**
(`~/.claude/plugins/cache/hiway-kit/hiway-kit/<version>/`), not from this
repo's working tree. So editing `plugins/common/agents/*.md` and immediately dispatching
that agent runs the **old** definition — the change is invisible until the version is
bumped, pushed, and the plugin updated.

This bit us in 2.14.0 development: `review-code`'s output contract was buried 496 lines
from the end of its definition, its reports came back empty twice, and the working-tree
fix could not be verified in the same session. Two consequences:

- **Never conclude "the definition change worked" from in-session behavior.** Verify by
  reading the file, or by a machine check (`verify-done.sh` § checks against the working
  tree; note that `§12`, the check this incident originally motivated, was retired in
  W-022 R1 — see the Delegation Signal section above).
- To actually exercise a definition change, bump the version and reinstall
  (`/plugin marketplace update` → `/plugin install`), or point a scratch install at the
  working tree.

Hooks and `scripts/` are different — hooks run from `${CLAUDE_PLUGIN_ROOT}` (also the
cache), but `scripts/` and `evals/` are repo-local and take effect immediately.

### Adding a New Agent

1. Create `plugins/common/agents/{category}/{name}.md`
2. Add required frontmatter (see template above)
3. Write Korean description with `MUST USE when:` trigger conditions
4. No manifest edit needed — agents are auto-discovered from the directory
   (plugin.json has no agent/skill registry)

### Adding a New Skill

1. Create `plugins/common/skills/{name}/SKILL.md`
2. Optionally add `README.md` in the same directory
3. No manifest edit needed — skills are auto-discovered from the directory

### Naming Conventions

- Agents: `verb-noun.md` (fix-bugs, plan-refactor, explore-codebase)
- Skills: `noun-action` (web-research, plan-task, auto-dev)
- All agent names must be kebab-case and match the `name:` frontmatter field

### Sub-agent Rules

- Regular agents: `disallowedTools: [Task]` — cannot spawn sub-agents
- Meta agents (facilitator, synthesizer, devil's advocate, impact-analyzer, consensus-builder — 5 total): `disallowedTools: [Bash]`
- Skills (auto-dev, etc.) drive delegation; leaf agents stay flat.

### Orchestration Model — Scale-Appropriate Primitives (Spec 2 / W-006)

오케스트레이션은 전통이 아니라 **스케일별로 올바른 프리미티브**를 쓴다. leaf 에이전트가
Task를 갖지 않는 이유는 "main만 조율" 도그마가 아니라, 우리 스케일에서 에이전트 중첩이
성능 이득 없이 예측불가능성·디버깅 부채만 더하기 때문이다.

킷이 **소비자에게** 제공하는 모델이다(이 레포 자체의 협업 수단은 `coordination.md`).

| 작업 규모 | 오케스트레이션 |
| --------- | -------------- |
| Small / Medium | 스킬 주도 플랫 위임 (main이 Agent 병렬 dispatch → 결과 수집). 예측가능·검증된 경로 |
| Large (10~100+) | 네이티브 `ultracode`(dynamic workflow)를 **사용자가 수동 트리거** — 백그라운드 오케스트레이션. auto-dev는 Large 작업을 청크로 분할해 안내 |

> 네이티브 dynamic workflow / `/goal`은 대화형 전용이라 스킬에서 프로그래밍 트리거가
> 불가하다(2026.6 기준). 따라서 자동 위임은 검증된 Task 시스템 + 스킬 루프로 하고,
> 대규모 병렬은 사용자가 `ultracode`로 트리거한다. 실험적 자체 조율(구 agent-teams)은
> 이 네이티브 경로로 대체됐다.

### Phase Gate Pattern

```
Phase 1 (Planning)    → 100% ambiguity removed via planning agents
Phase 2 (Development) → implement based on Phase 1 artifacts
Phase 3 (Validation)  → review + security scan (parallel)
```

## Hooks

Located in `plugins/common/hooks/` (except `session-check.py`, which lives in
`plugins/common/setup/`):

- `session-check.py` — `SessionStart` environment/setup check (runs before
  `session-start.py`; registered from `setup/`). Warns on: python below the 3.9
  floor, missing global setup, `.claude/agents` dual-load, and a **stale venv**
  (`.venv`/`venv` console-script shebangs still pointing at the project's old
  path after a directory move/copy — `bin/python` keeps working while every
  script dies with `bad interpreter`, or silently runs the old site-packages)
- `session-start.py` — injects rules + active Work status at `SessionStart`
- `protect-sensitive.py` — `PreToolUse` on Edit/Write/MultiEdit/NotebookEdit/Read:
  blocks access to **sensitive file paths** (`.env`, keys, `.pem`) by path. env
  templates (`.env.example`/`.sample`/`.template`/`.dist`) are exempt; writes to
  them get a best-effort high-confidence secret-format content scan (W-016). It
  does **not** otherwise scan file *content* or intercept `Bash`/`git commit` —
  commit-time secret scanning is gitleaks + `setup/pre-commit`.
- `auto-format.py` — auto-formats code after edits (uses ruff for Python) (`PostToolUse`)
- `stop-validator.py` — on `Stop`, lints edited `.py` (ruff) and runs pytest on
  the test files this session edited (never the full suite — that's CI/`/test`'s
  job); on failure emits native `{"decision":"block","reason":...}` so Claude
  continues and auto-fixes. Timeouts are non-blocking (`CLAUDE_STOP_TEST_TIMEOUT`)
- Stop state reuses `$TMPDIR/claude-{uid}` only when it is an owned, non-symlink
  directory with mode `0700`. Unsafe or unavailable stable state uses a private
  temporary directory for that process; it never trusts counters from the shared
  temporary root. This fallback loses cross-process marker/retry reuse.
- `utils.py` — shared utilities

### git 훅은 배포되지만 자동으로 켜지지 않는다

`plugins/common/setup/` 에는 세션 훅이 아닌 **git 훅** 정본도 있다 — `pre-commit`
(시크릿 스캔 등)과 `git-hooks/reference-transaction`(레퍼런스 변경 가드). `setup.sh`
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
> ships a custom `agent-lifecycle.py` (removed in the 2.6.0 batch, Spec 1 / W-005).

### 설정값으로 경로를 만들면 반드시 봉쇄한다 (2026-08-27 확정)

@docs/conventions/path-containment.md

## Security

- `gitleaks` scans all pushes/PRs (config: `.gitleaks.toml`)
- Never hardcode secrets, API keys, internal IPs, or project names
- `protect-sensitive.py` runs as a `PreToolUse` hook on Edit/Write/MultiEdit/NotebookEdit/Read — path-based (plus a best-effort content scan only for env-template writes), not commit-based (see Hooks section)

## CI/CD

`.github/workflows/validate.yml` runs on push to `main` (and PRs):

1. Validates JSON syntax (`plugin.json`, `marketplace.json`)
2. Checks agent frontmatter completeness (`name`, `description` required)
3. Lints with `ruff check .` and runs pytest
4. Lints shell via `scripts/lint-shell.sh` (same script as the local gate §3b)
5. Verifies doc counts via `scripts/check_doc_counts.py` (same script as the local gate)
6. Runs gitleaks security scan
7. `python39-compat` job: loads every hook under Python 3.9 (consumer floor)

### 드리프트 게이트는 통합하지 않는다 (2026-08-27 판정 · 2026-09-10 재검토)

`verify-done.sh` 에는 "생성물·사본이 SSOT와 일치하는가"를 묻는 게이트가 여럿 있다
(진입점 마커 · 타겟 매니페스트 · 이름 파생 · eval 기준선 · 룰 체크섬 · 버전 sync ·
설치된 훅). **몇 개인지 여기 적지 않는다** — 이유는 아래에 있다.

**같은 질문처럼 보이지만 입력·판정 기준·실패 메시지가 전부 다르다.** 어떤 것은 입력의
sha256 을 기록해 두고 대조하고, 어떤 것은 재생성해서 내용을 비교하고, 어떤 것은 집합
양방향 대조다. 공통 프리미티브로 묶으면 추상이 모든 케이스를 감당하지 못해 분기
파라미터가 늘고, **게이트 코드가 어려워진다.** 게이트는 읽기 쉬워야 신뢰된다 —
아무도 이해하지 못하는 게이트는 red 가 떴을 때 무시된다(`no-gate-integration.md`).

**그래서 통합하지 않는다.** 중복은 코드가 아니라 **규약**으로 줄인다(위 경로 봉쇄
관례가 그 예다).

**재검토(2026-09-10) — 원래 약속은 "네 번째가 필요해지면 재검토한다"였다.**
그 시점은 조용히 지났고, 실제로는 넷째·다섯째·여섯째·일곱째까지 늘어난 뒤에야
이 문단을 다시 읽었다. 통합 판정은 위와 같은 이유로 **유지** 한다. 바뀐 것은 서술
방식이다:

이 문단은 게이트를 **표로 열거** 하고 있었고, 게이트가 늘어날 때마다 아무도 고치지
않아 **셋으로 멈춘 채 낡았다.** 이 레포는 바로 이 실패를 두 곳에 이미 적어 두었다 —
`rules/definition-of-done.md` 의 *"기계 검사 목록은 게이트가 소유한다 — 열거하면 검사를
더할 때마다 낡는다(실제로 그랬다)"*, `docs/conventions/warning-signal.md` §5 의
*"대상을 나열하지 말고 제외를 나열한다"*. 자기 규약을 자기 문서가 어긴 것이다.

**그래서 목록을 지웠다.** 무엇이 드리프트 게이트인지는 `scripts/verify-done.sh` 가
소유한다 — 알고 싶으면 그것을 읽어라. 이 문단이 남기는 것은 **판정과 그 근거** 뿐이고,
그 둘은 게이트가 몇 개든 변하지 않는다.

### Lint is one ruleset, everywhere

@docs/conventions/lint-single-ruleset.md

### Rules have a long-form mirror — and it is checksum-guarded

@docs/conventions/rules-mirror.md

### Shell is linted too

@docs/conventions/shell-lint.md

### 경고는 상시 참이 되면 죽는다

@docs/conventions/warning-signal.md

## Release Checklist

**CRITICAL: Every commit that changes plugin behavior MUST bump the version in `plugins/common/.claude-plugin/plugin.json`.**

Plugin cache is keyed by `{plugin-name}/{version}` — same version = no update fetched = users never get the fix.

- Patch bump (2.x.y) for bug fixes and hook changes
- Minor bump (2.x.0) for new agents, skills, or features
- Add a matching `## [x.y.z]` entry to `CHANGELOG.md` (verify-done.sh §6 fails if
  the plugin.json version and the CHANGELOG top entry diverge)
- Keep README/docs version-agnostic (link to CHANGELOG) so they can't drift
- **버전을 올렸으면 타겟 매니페스트를 재생성한다**: `python3 scripts/build-targets.py --write`.
  `.claude-plugin/plugin.json` 만 올리고 이것을 빠뜨리면 Codex·Antigravity 패키지에 **옛 버전이
  실린 채** 나간다. v2.15.0 릴리스에서 실제로 밟았고 `verify-done.sh` §14가 잡았다 —
  게이트가 없었다면 그대로 배포됐을 실수다
- Rules `.md` 변경 시 CHECKSUMS 재생성: `(cd plugins/common/rules && shasum -a 256 *.md | grep -v CHECKSUMS > CHECKSUMS.sha256)` — 이 매니페스트는 보안 경계가 아니라 우발적 드리프트 감지기다 (verify-done §7이 집합 동등성까지 강제)
- 그 룰에 **해설본 미러**가 있으면(아래 참조) 해설본도 함께 손보고 `scripts/sync-rule-mirror.sh --regenerate`
- Tag **the commit you push as the release**: `git tag -a vX.Y.Z <commit> -m "vX.Y.Z"`,
  then `git push --tags`. Later commits that leave the version untouched (docs, repo
  tooling) are not a new release and do not move the tag. `verify-done.sh §6` fails when
  any past CHANGELOG release lacks a tag — the practice lapsed silently once (20 untagged
  releases between 2.10.4 and 2.12.3), so it is a machine check now, not a convention.
  Two caveats on existing tags: the 2026-08-17 backfill could not recover which commit was
  actually pushed as each old release, so it used the closest approximation — the last
  commit carrying that version; and tags predating v2.11.0 were placed ad hoc and follow
  no single rule. Every tag does point at a commit whose `plugin.json` matches it.
- Run `scripts/verify-done.sh` (green) before claiming a release ready (definition-of-done)

```bash
# Before git commit — update version field:
# plugins/common/.claude-plugin/plugin.json  → "version": "x.y.z"
```

### Distribution & catalog propagation

두 설치 경로가 pushed `main` 을 다르게 전파한다 — 사용자가 어느 쪽인지 알고 안내해야 한다.

- **직접 마켓플레이스** (`This-HW/hiway-kit` → `@hiway-kit`): `/plugin marketplace update` 시
  **즉시** main HEAD 를 반영한다. 현재 **유일하게 성립하는** 경로다.
- **커뮤니티 카탈로그** (`@claude-community`): **미등재**이고, 등재돼도 **pin 전진을 신뢰하면
  안 된다.** 상류의 `Bump Plugin SHAs` 워크플로가 `disabled_manually` 상태로 2026-08-13 이후
  한 번도 실행되지 않았다 — **우리 결함이 아니라 상류 자동화가 꺼진 것**이고 카탈로그의 모든
  항목이 같이 멈춰 있다. 전수 근거·재현 명령:
  `docs/research/2026-09-08-plugin-directory-status.md`.

우리가 통제할 수 있는 것은 **재개되는 순간 green 으로 통과하는가** 하나뿐이라, 상류가 bump 시
돌리는 `claude plugin validate` 를 §19 게이트·CI 로 앞당겨 건다.

**함의**: 릴리스 안내에 **"하루면 전파된다"고 쓰지 마라** — 약속할 근거가 없다. 즉시성이
필요한 사용자는 직접 마켓플레이스 경로로 보낸다.

## Contributing

PRs welcome. Checklist:

- [ ] **Consumer-first**: works in an installing user's environment, not just this repo —
      no reliance on the project cwd containing plugin files, no assumption a specific MCP
      server is installed, hooks fail-open when their assumptions don't hold
- [ ] No `mcp__*` tools in any agent `tools:` allowlist (MCP lives in skills — see
      `rules/mcp-usage.md`; absent MCP in an agent allowlist hallucinates, CC #13898)
- [ ] Agent frontmatter has `name`, `description`, `model`, `maxTurns`
- [ ] No forbidden fields: `permissionMode`, `context_cache`, `output_schema`, `next_agents`, inline `hooks`
- [ ] Description includes `MUST USE when:` trigger conditions
- [ ] File-modifying agents have `isolation: worktree`
- [ ] Regular agents have `disallowedTools: [Task]`
- [ ] Skill `description` field is in English
- [ ] Version bumped in `plugins/common/.claude-plugin/plugin.json` + matching `CHANGELOG.md` entry
      (the manifest has **no** agent/skill registry — both are auto-discovered from their
      directories; the only thing a new component must touch there is the version)
- [ ] CI passes (JSON valid, frontmatter complete, no forbidden fields, pytest green, no secrets)

@docs/conventions/coordination.md
