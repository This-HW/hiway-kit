# packaging/ — multi-harness target manifests (W-019)

`targets.json` is the **single source of truth** for the plugin manifests kit ships
to non-Claude-Code harnesses (currently Codex and Antigravity). `../scripts/build-targets.py`
computes those manifests from `targets.json` + `plugins/common/.claude-plugin/plugin.json`
(the existing Claude Code SSOT — name/version/description/author/license/homepage/
repository/keywords) + a real-time scan of which component directories
(`skills/`, `agents/`, `rules/`, `hooks/`) actually exist. No target-specific value is
hardcoded anywhere else — a target's field mapping, interface copy, and pass-through
fields all live in `targets.json`.

## Why a generator instead of hand-written manifests

Hand-maintained target manifests drift from the Claude Code SSOT the moment either
changes — the same failure class this repo already guards against for doc counts,
rule checksums, and the `AGENTS.md` export (see `docs/architecture/rules/`). The
generator + drift gate make "the generated file matches the SSOT" a machine check
instead of a promise.

## Usage

```bash
# Check for drift (read-only, never writes). Scans every enabled target.
python3 scripts/build-targets.py --check

# Check a single target
python3 scripts/build-targets.py --check --only codex

# Write. Requires --only — there is no bare "write everything" mode by design,
# so a stray invocation can't silently regenerate every target at once.
python3 scripts/build-targets.py --write --only codex
python3 scripts/build-targets.py --write --only antigravity
```

`--check` treats a missing manifest for an `enabled:true` target as **drift** (exit 1),
not as "not built yet" — a target is either fully generated and verified, or disabled
in `targets.json`. There is no in-between state the gate tolerates.

## When to regenerate

Run `--write --only <id>` (and commit the result) whenever:

- `plugins/common/.claude-plugin/plugin.json` changes (version bump, new keywords, a
  passthrough field's value changes, etc.) — every enabled target needs to pick up
  the new SSOT value.
- `targets.json` itself changes (new `passthroughFields`, a target's `enabled` flips,
  interface copy changes).
- A component directory (`skills/`, `agents/`, `rules/`) is added or removed, which
  changes what `componentFields` resolve to.

`scripts/verify-done.sh` §14 (and the equivalent CI step) run `--check` on every
push — a stale generated manifest fails the gate, the same way a stale `AGENTS.md`
does.

## Adding a target

A target entry in `targets.json` needs, at minimum: `id`, `enabled`, `manifestPath`,
and `requiredFields`. See the `codex` and `antigravity` entries for the full field
vocabulary (`componentFields`, `passthroughFields`, `schemaUrl`, `interface`,
`marketplace`). Disabled targets (`cursor`, `opencode`, `copilot`) carry a
`_disabledReason` explaining why they're not live yet — keep that convention so the
next person doesn't have to re-derive the reasoning from scratch.

**Before flipping a target to `enabled:true`**, verify against the real CLI — this
repo's history (S1–S4 of W-019) is a generator built ahead of two targets that were
verified one at a time against `codex`/`agy`, not assumed from documentation alone.

## `name-targets.json` — deriving the product name into prose docs (D-3)

`targets.json` (above) generates *manifests* — pure, never-hand-edited artifacts, so
full byte-for-byte regeneration is safe. `name-targets.json` +
`../scripts/derive-name.py` solve a related but different problem: `README.md`,
`plugins/common/README.md`, `CLAUDE.md`, and everything under `site/content/` are
prose that people edit by hand. Regenerating them wholesale from a template would
create a second copy of nearly all their content — the exact SSOT-duplication failure
this repo's gates exist to catch.

So `derive-name.py` doesn't regenerate files; it tracks the SSOT name it last applied
(`lastAppliedName`) and, on `--write`, does a literal find-and-replace of that old name
with the current SSOT name (`plugins/common/.claude-plugin/plugin.json`'s `name`)
across the policy's `files` and `directories` (the latter scanned recursively for
`*.md` — never hand-listed, same principle as `check_doc_counts.py`'s count detection).
Everything else in those files is untouched. `--check` (wired into `verify-done.sh`
§18) fails when the policy's `lastAppliedName` no longer matches the SSOT name — i.e.
the name changed but nobody ran `--write` yet.

```bash
python3 scripts/derive-name.py --check   # drift only, never writes
python3 scripts/derive-name.py --write   # propagate a name change, update the policy
```

This can't catch a hand-typed wrong name that was never derived from the SSOT in the
first place — see `name-targets.json`'s `_meta.known_limitation`. It only guarantees
that once a name *was* derived, changing the SSOT and forgetting to re-derive shows up
as a red gate.
