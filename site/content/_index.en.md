---
title: "hiway-kit"
description: "A universal Claude Code toolkit — 33 specialized agents, 20 skills, and 13 governance rules for building a multi-agent development pipeline."
keywords: ["claude code plugin", "multi-agent development system", "agent harness engineering", "AI coding agent evals", "claude code skills"]
---

**hiway-kit** is a universal development toolkit built on top of
[Claude Code](https://claude.com/claude-code)'s agent harness. It composes a
three-phase pipeline — Planning, Development, Validation — out of specialized
agents, aiming not just to ship fast but to **finish every task in a verified
state**.

<div class="callout">
<strong>By the numbers</strong>

- **33** specialized agents (planning, implementation, review, refactoring)
- **20** skills (`/plan-task`, `/auto-dev`, `/review`, `/debug`, `/test`, and more)
- **13** governance rules (worktree isolation, delegation chains, definition of done)
- **220+** unit tests
- **11** agent behavior eval scenarios (deterministic-first scoring)
- **8+** machine gates (`verify-done.sh`)
</div>

## Install

```bash
# Path 1 — Anthropic community marketplace
/plugin marketplace add anthropics/claude-plugins-community
/plugin install hiway-kit@claude-community

# Path 2 — register the repository directly
/plugin marketplace add This-HW/hiway-kit
/plugin install hiway-kit@hiway-kit
```

For the full local install (security hooks, auto-format, pre-commit), see the
[README](https://github.com/This-HW/hiway-kit#installation).

Learn more: [Getting Started]({{< relref "/getting-started" >}}) · [About / Architecture]({{< relref "/about" >}})
