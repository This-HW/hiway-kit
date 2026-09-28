---
tier: reference
portable: false
indexLine: 에이전트 선택·모델 정책은 rules/agent-system.md 를 읽어라
---

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

- P0 ambiguity = 0, business rules defined, data model defined, user flows clear

Phase 2 → Phase 3 (Dev → Validation):

- Build passes, tests for the changed behavior pass, lint/type checks pass

Phase 3 → Complete (Validation → Done):

- review-code Must Fix = 0, Critical security issues = 0, verify-code PASS
