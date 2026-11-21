---
tier: reference
portable: false
indexLine: 에이전트 선택·모델 정책은 rules/agent-system.md 를 읽어라
---

> **디렉토리판 — worktree 격리 없음.** 이 설치(Anthropic 디렉토리판)에서는 파일을 고치는 에이전트(implement-code·fix-bugs·write-tests·sync-docs)가 격리 worktree 가 아니라 **사용자의 작업 트리**에서 돈다. 아래의 worktree 절차(격리 트리에서 커밋하고 돌아오기)는 적용되지 않는다 — 그 에이전트는 **커밋하지 말고** 바꾼 파일과 요약만 반환하고, 커밋·병합은 호출자가 한다. 같은 트리를 함께 고치지 않도록 그 에이전트들은 **병렬이 아니라 순차로** 부른다. 격리가 필요하면 전체판(이 레포를 마켓플레이스로 설치)을 쓴다.

# Agent System Rules

Agents are auto-discovered from the plugin directory — pick from the agent list the host
exposes (there is no manifest to consult). Each agent's `MUST USE when:` trigger is the
selection rule; this file does not redefine it. When no kit agent fits, the host's native
agents (general-purpose, Explore, Plan, …) are fine — do not force a kit agent onto a task.

## Roster (SSOT — skills and docs point here instead of copying this table)

| Agent | Model | Writes files | isolation |
| --- | --- | --- | --- |
| clarify-requirements | opus | no | — |
| define-business-logic | opus | no (returns spec; caller saves) | — |
| design-user-journey | opus | no (returns spec; caller saves) | — |
| plan-implementation | opus | no | — |
| devils-advocate | opus | no | — |
| review-code | opus | no | — |
| implement-code | sonnet | yes | worktree |
| fix-bugs | sonnet | yes | worktree |
| write-tests | sonnet | yes | worktree |
| security-scan | sonnet | no | — |
| research-external | sonnet | no | — |
| sync-docs | haiku | yes | worktree |
| verify-code | haiku | no | — |
| analyze-dependencies | haiku | no | — |
| git-workflow | haiku | git state only | — |

Model follows the job: opus for specs, plans, and adversarial review; sonnet for writing
code; haiku for running commands and mechanical checks. The frontmatter owns the actual
value — if this table and a frontmatter disagree, the frontmatter wins and this table is stale.

## Adversarial Parallel Verification

When several independent adversarial views are needed, fan out to **different** agents —
`review-code` (defects) + `security-scan` (security) + `devils-advocate` (design failure
scenarios) — rather than cloning one agent. Clones share blind spots.

## isolation: worktree

ALWAYS set `isolation: worktree` on agents that modify source files (the `worktree` rows above).
NEVER set it on read-only agents. `git-workflow` changes repository state, not the working
tree's sources, and runs unisolated because its job is the integration point.
Merge-back protocol: see parallel-worktree.md.

## disallowedTools Policy

- Every agent: `disallowedTools: [Task]` — agents do not spawn agents; the calling skill or
  session orchestrates.
- Document-only analysts with no need for a shell (`devils-advocate`): also `Bash`.
- Skills: no restriction (the main session runs them).

## Phase Gate

ALWAYS complete each phase before proceeding to the next.

Phase 1 → Phase 2 (Planning → Dev):

- P0 ambiguity = 0. What else Planning must produce depends on task size — the size
  criteria and per-size Planning exit live in `skills/plan-task/references/elicitation.md` §6

Phase 2 → Phase 3 (Dev → Validation):

- Build passes, tests for the changed behavior pass, lint/type checks pass

Phase 3 → Complete (Validation → Done) — same bar as auto-dev's T-merge:

- Every completion-condition command run fresh, all rc 0
- review-code verdict `[ACCEPT]` (0 CRITICAL, 0 HIGH)
- security-scan CRITICAL/HIGH = 0
