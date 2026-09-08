---
title: "Getting Started"
description: "Install hiway-kit and walk through the core skill workflow — brainstorming, /plan-task, /auto-dev, /review, /debug, /test."
keywords: ["claude code plugin install", "claude code skill workflow", "auto-dev", "plan-task", "AI coding agent harness"]
translationKey: "getting-started"
---

## Install

There are two paths.

```bash
# Path 1 — the version listed on the Anthropic community marketplace
/plugin marketplace add anthropics/claude-plugins-community
/plugin install hiway-kit@claude-community

# Path 2 — directly from the repository (tracks the latest commit)
/plugin marketplace add This-HW/hiway-kit
/plugin install hiway-kit@hiway-kit
```

To install the security hooks (`protect-sensitive`, `auto-format`,
`stop-validator`) and pre-commit locally, clone the repository and run
`setup.sh`.

```bash
git clone https://github.com/This-HW/hiway-kit
cd hiway-kit
./setup.sh
```

## Core workflow: from idea to shippable code

The typical flow: brainstorm to surface ambiguity, lock the plan behind a
gate, then let development and validation run as an autonomous loop.

```
brainstorming  ->  /plan-task  ->  /auto-dev  ->  /review  ->  /test
  (diverge)         (lock plan)     (dev pipeline)  (parallel review) (regression check)
```

### 1. Brainstorming — surfacing ambiguity before you plan

Before starting a new feature or refactor with loosely defined requirements,
brainstorm first. Forcing multiple perspectives (user scenarios, edge cases,
trade-offs) into the open surfaces exactly where you'll need a human gate
later.

### 2. `/plan-task` — structured task planning

```
/plan-task add avatar upload to the user profile page
```

The goal is to remove 100% of requirement ambiguity (the Phase 1 gate). This
is where API signatures, file locations, and the definition of done get
locked in — the next phase treats this artifact as the implementation
contract.

### 3. `/auto-dev` — an automated development pipeline

```
/auto-dev
```

Takes the planning artifact and drives implementation, integration, and
validation automatically. Agents that modify files run in isolated git
worktrees to prevent conflicts during parallel work. Large-scale work
(10-100+ files) gets chunked with guidance, and anything beyond that is
routed to the native `ultracode` (dynamic workflow), which the user triggers
manually.

### 4. `/review` — code review (ruff + review-code + security-scan)

```
/review
```

Runs linting (ruff), architecture/style review (review-code), and a security
scan (security-scan) in parallel — the Phase 3 validation gate. For deeper
deliberation, `/multi-perspective-review` runs a 3-round, 10-persona review.

### 5. `/debug` — a 4-phase debug pipeline

Forces reproduce -> isolate -> fix -> verify, preventing the common failure
mode of fixing a symptom while leaving the root cause in place.

```
/debug profile images intermittently break after login
```

### 6. `/test` — run tests and auto-fix failures

```
/test
```

Runs tests and automatically fixes failures. Scoped to the files edited in
the current session rather than the full suite — full regression runs belong
to CI.

## What's next

- Curious about the architecture? Read [About]({{< relref "/about" >}}).
- For real-world decisions and how the design evolved, see the (Korean)
  [dev log]({{< relref path="/posts" lang="ko" >}}).
- Code and issues live on the
  [GitHub repository](https://github.com/This-HW/hiway-kit).
