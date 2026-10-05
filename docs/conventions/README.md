---
status: current
as_of: 2026-10-05
---

# docs/conventions/ — host-neutral project conventions

This directory is the **single source** for the parts of this repo's engineering discipline that
apply regardless of which coding-agent harness (Claude Code, Codex, Antigravity, ...) a
contributor is using. `CLAUDE.md` pulls **some** of these in via `@docs/conventions/<file>.md`
imports (the "Imported" column below — `CLAUDE.md` itself is the authority) and points at the
rest by path, because every import is inlined into every session and counts against the
injection budget (`scripts/check_injection_budget.py`). `AGENTS.md`'s generated block (see below)
inlines a smaller, size-budgeted subset for harnesses that don't support `@` imports.

## Index

| File | Imported by `CLAUDE.md` | What it owns |
| --- | --- | --- |
| `path-containment.md` | yes | Config-driven file paths are resolved once and contained in the repo — the defect recurred four times |
| `no-gate-integration.md` | no (pointer) | Why the drift gates stay separate, and how to tell whether a new one is needed |
| `lint-single-ruleset.md` | yes | `ruff.toml` + pinned ruff/pytest versions — why local and CI agree |
| `rules-mirror.md` | yes | `plugins/common/rules/` ↔ `docs/architecture/rules/` and its checksum guard |
| `shell-lint.md` | yes | shellcheck over every tracked shell script, pinned and gated |
| `warning-signal.md` | yes | Before adding a warning/check: when is it false, when does it run, what is out of scope |
| `measurement-traps.md` | no | The evidence behind `warning-signal.md`'s measurement rules — read when doubting them |
| `release-process.md` | no (pointer) | **Release procedure SSOT** — version bump, CHANGELOG, regeneration, eval, tag, gate |
| `reference-vs-judgment.md` | no | Check whether this repo has a reference project's problem before porting its tool |
| `coordination.md` | yes | This repo's own supervised-worker transport (not imposed on consumers) |

## How a section was classified

Each convention that used to live directly in `CLAUDE.md` was judged against one question:

> **If a contributor working through a different harness doesn't know this, will they make a
> wrong commit?**

That is a narrower bar than "is this interesting" or "is this true regardless of harness." A lot
of `CLAUDE.md` is genuinely host-neutral in the sense that it's *true* for any harness (e.g. the
2-tier agent model) but doesn't change what a contributor should *do* — those stayed in
`CLAUDE.md`, or in the `AGENTS.md` block that carries the portable `rules/*.md` content (each
rule declares `portable:` in its own frontmatter; `plugins/common/tools/export_harness.py` reads it).

**Stayed Claude-Code-specific (didn't clear the bar), examples:**

- `/plugin` install commands and channel propagation — Claude Code's own distribution mechanics;
  a Codex contributor installs via `codex plugin ...` (see README's "Other Harnesses" section).
- Agent frontmatter schema and `isolation: worktree` — Claude Code subagent primitives. No other
  target loads the kit's `agents/` as subagents (README capability table) — a non-Claude-Code
  contributor can't act on this even if they read it.
- The plugin-cache-versioning gotcha ("editing an agent/skill does NOT affect the current
  session") — specific to how Claude Code loads plugins from its cache.

## What's inlined into `AGENTS.md` vs referenced by path

Codex's `project_doc_max_bytes` (merged-total, silently-truncating — see
`docs/research/2026-08-27-superpowers-distribution.md`'s appendix) means `AGENTS.md` cannot
inline everything in this directory without risking silent truncation for consumers who also
have a sizeable global `~/.codex/AGENTS.md`. `plugins/common/tools/export_harness.py`'s second
marker block inlines only the most concrete "you will repeat a real bug without this" entries and
points at this directory by path for the rest. Its `CONVENTIONS_INLINE` / `CONVENTIONS_REFERENCE_ONLY`
lists are the exact set — changing what's inlined is a one-line change there, not a redesign.
