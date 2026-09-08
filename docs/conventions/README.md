# docs/conventions/ — host-neutral project conventions (W-022 R7)

This directory is the **single source** for the parts of this repo's engineering discipline that
apply regardless of which coding-agent harness (Claude Code, Codex, Antigravity, ...) a
contributor is using. `CLAUDE.md` pulls these in via `@docs/conventions/<file>.md` imports instead
of repeating them; `AGENTS.md`'s generated block (see below) inlines a small, size-budgeted subset
directly for harnesses that don't support `@` imports.

## How a section was classified

Each convention that used to live directly in `CLAUDE.md` was judged against one question:

> **If a contributor working through a different harness doesn't know this, will they make a
> wrong commit?**

That is a narrower bar than "is this interesting" or "is this true regardless of harness." A lot
of `CLAUDE.md` is genuinely host-neutral in the sense that it's *true* for any harness (e.g. the
2-tier agent model, the delegation signal format) but doesn't change what a contributor should
*do* — those stayed in `CLAUDE.md` as-is, or in the `AGENTS.md` block that already carries the
portable `rules/*.md` content (see `plugins/common/hooks/export_harness.py`'s `PORTABLE` list,
which made the same kind of judgment for rules and already covers `definition-of-done`).

**Moved to `docs/conventions/` (this bar, met):**

| File | Why it clears the bar |
| --- | --- |
| `path-containment.md` | The same defect (unsanitized config-driven file path) recurred three times across this repo's own code. Any contributor building a script that turns a config value into a path needs this regardless of which harness they're using. |
| `no-gate-integration.md` | Explains why the repo has three similar-looking drift gates instead of one — without it, a contributor might "helpfully" merge them and lose the specificity that makes each one trustworthy. |
| `lint-single-ruleset.md` | Explains why `ruff.toml`/pinned versions exist — skip it and a contributor's local lint disagrees with CI for reasons that look like flakiness. |
| `rules-mirror.md` | Explains the checksum-guarded relationship between `plugins/common/rules/` and its long-form mirror — edit one without the other and the drift gate (§7) fails for a reason that isn't obvious from the error alone. |
| `shell-lint.md` | Same category as the lint-ruleset entry, for shell scripts. |
| `release-process.md` | The version-bump discipline (bump via script, regenerate, tag, gate) applies to any commit that changes plugin behavior, regardless of which harness authored it. |
| `reference-vs-judgment.md` | A general discipline (check whether this repo's structure has the problem a reference project's tool solves before porting the tool), illustrated with a concrete case from this same batch. |

**Stayed Claude-Code-specific (didn't clear the bar), examples:**

- `/plugin` install commands, marketplace propagation timing — these are Claude Code's own
  distribution mechanics; a Codex contributor installs via `codex plugin ...` (see README's "Other
  Harnesses" section), and this content wouldn't change what they commit.
- Agent frontmatter schema, `isolation: worktree`, the Delegation Signal contract — these are
  Claude Code subagent primitives. `agents/` isn't ported to any other target at all (see
  `docs/specs/2026-08-26-multi-harness-packaging.md` §5.5) — a non-Claude-Code contributor can't
  act on this even if they read it.
- The plugin-cache-versioning gotcha ("editing an agent/skill does NOT affect the current
  session") — specific to how Claude Code loads plugins from its cache.

## What's inlined into `AGENTS.md` vs referenced by path

Codex's `project_doc_max_bytes` (merged-total, silently-truncating — see
`docs/research/2026-08-27-superpowers-distribution.md`'s appendix) means `AGENTS.md` cannot
inline everything in this directory without risking silent truncation for consumers who also
have a sizeable global `~/.codex/AGENTS.md`. `plugins/common/hooks/export_harness.py`'s second
marker block inlines only `path-containment.md` and `no-gate-integration.md` in full — the two
most concrete, "you will repeat a real bug without this" entries — and points at this directory by
path for the rest. See that script's `CONVENTIONS_INLINE` list for the exact set; changing what's
inlined is a one-line change there, not a redesign.
