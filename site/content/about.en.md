---
title: "About"
description: "The architecture and implementation principles behind hiway-kit — harness x loop engineering, deterministic guardrails, and definition-of-done machine gates."
keywords: ["claude code plugin", "multi-agent development system", "agent harness engineering", "AI coding agent evals", "definition of done"]
translationKey: "about"
---

**hiway-kit** is a multi-agent development system built on the
[Claude Code](https://claude.com/claude-code) agent harness. This page is not
about what we built, but **why we built it this way**.

## 1. Harness x Loop Engineering

The industry frames AI coding agent maturity in three stages: prompt
engineering, context engineering, and **harness engineering**. A harness
governs tool orchestration, state persistence, verification loops, and error
recovery across a task's entire lifecycle.

hiway-kit makes this distinction explicit:

<div class="callout">
<strong>Gate vs. Loop</strong>

- **Gate** — a point where a human must stop and decide: resolving requirement
  ambiguity, architectural decisions, release approval.
- **Loop** — a point where a machine can autonomously drive to completion:
  implement → verify → auto-fix on failure, with a clear exit criterion.
</div>

The core of the three-phase pipeline is to remove 100% of ambiguity in
planning (a gate), then let development and validation run as loops to
autonomous completion.

```
Phase 1 (Planning)    -> remove requirement ambiguity (gate)
Phase 2 (Development) -> implement against Phase 1 artifacts (loop)
Phase 3 (Validation)  -> review + security scan in parallel (loop + gate)
```

## 2. 33 Agents, 16 Skills, Three-Tier Model Selection

Agents are split by role, and skills (`/plan-task`, `/auto-dev`, `/review`,
`/debug`, `/test`, and more) drive the actual delegation. Each agent uses the
model tier that matches the nature of its work.

| Model | Use case | Examples |
|-------|----------|----------|
| Opus | Strategy, analysis, review | clarify-requirements, review-code |
| Sonnet | Code implementation, fixes | implement-code, fix-bugs, write-tests |
| Haiku | Exploration, simple checks | explore-codebase, verify-code |

Leaf agents never spawn further sub-agents (`disallowedTools: [Task]`). This
isn't dogma that "only the orchestrator coordinates" — at our current scale,
nesting agents adds unpredictability and debugging debt without a
corresponding performance gain. The principle is **using the primitive that
matches the scale of the work**.

<div class="loop">
  <span class="node start">Small/Medium</span>
  <span class="arrow">-&gt;</span>
  <span class="node step">Skill-driven flat delegation</span>
  <span class="arrow">-&gt;</span>
  <span class="node done">Predictable, verified path</span>
</div>
<div class="loop">
  <span class="node start">Large (10-100+)</span>
  <span class="arrow">-&gt;</span>
  <span class="node step">Native ultracode</span>
  <span class="arrow">-&gt;</span>
  <span class="node done">User-triggered manually</span>
</div>

## 3. Parallel Worktree Isolation

Agents that modify files (implement-code, fix-bugs, write-tests, and others)
run in isolated git worktrees (`isolation: worktree`). The point is preventing
filesystem contention, not isolation for its own sake — the real bottleneck,
as observed across the industry, is **merging and review**, not isolation
itself.

```
Isolated run -> verification green -> sequential merge
                    | red
              escalate to plan-refactor or git-workflow (never pick sides arbitrarily)
```

## 4. Deterministic Guardrails

Quality is not left to LLM judgment alone. Deterministic hooks enforce every
stage:

- **protect-sensitive.py** — blocks access to sensitive paths (`.env`, keys,
  `.pem`) by path
- **auto-format.py** — auto-formats code after edits (ruff for Python)
- **stop-validator.py** — before a session ends, lints and runs the tests
  relevant to files edited in that session; on failure it emits
  `decision: block` to force an auto-fix turn (scoped to **this session's**
  edited files, never the full suite — that belongs to CI / `/test`)

In Fowler's framing: `rules/` is **feedforward** (steering before action),
`hooks/` is **feedback** (observation after action).

## 5. Definition of Done — Machine Gates

Completion is not a claim, it's a verification. `scripts/verify-done.sh` must
pass 8+ machine gates before a change is considered release-ready: version
sync, agent frontmatter completeness, forbidden-field checks, a green pytest
run, secret scanning, and more.

The agent that wrote the code tends to rationalize its own output (a
compromised self-evaluation). That's why verification runs in a separate
session by a separate agent — it doesn't need to be bigger, but it needs to
be **different**.

## 6. Agent Behavior Evals — New

A regression-testing layer for the agents' own behavior. Scoring is
**deterministic-first** (rule-based wherever possible, LLM scoring as a
fallback) across 11 scenarios, and the release gate blocks "false-green"
results — failures that look like passes.

## 7. Feedback Ledger + /self-improve

Patterns and mistakes discovered in a session are recorded in a feedback
ledger and reused as context in the next iteration. `/self-improve` runs this
learning loop recursively, but it is **proposal-only** — it never changes
itself without passing both gates: evals plus explicit human approval.

## 8. /native-watch — Watching for Subsumption

When Claude Code itself ships a new native capability, a custom
implementation in the kit becomes redundant. `/native-watch` watches for this
subsumption signal, producing the evidence needed to decide whether to keep a
custom implementation or migrate to the native one. A real example: sub-agent
lifecycle tracking was absorbed by native OpenTelemetry support, letting us
remove the custom hook (`agent-lifecycle.py`) in the 2.6.0 batch.

---

Learn more: check out [Getting Started]({{< relref "/getting-started" >}}) for real
installation and usage scenarios, or read the (Korean) [dev log]({{< relref path="/posts" lang="ko" >}}) to
see how this design evolved.

Repository: [github.com/This-HW/hiway-kit](https://github.com/This-HW/hiway-kit) (MIT)
