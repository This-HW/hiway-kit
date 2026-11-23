---
status: current
as_of: 2026-11-24
---

# hiway-kit on other harnesses — install details

The README's [Where it runs](../README.md#where-it-runs) section owns **what reaches each harness** (the
measured capability and parity tables). This page holds the per-harness install commands and the
operational detail behind them. It was split out of the README in 5.9.0; the text is unchanged
apart from relative links, pointers back to the README where it used to say "above", and two
free-text skill counts, which now live only in the README table that `scripts/check_doc_counts.py`
guards.

## Keep one install

This section is about Claude Code. Path A (`hiway-kit@anthropic-plugin-directory`) and path B
(`hiway-kit@hiway-kit`) are two installation IDs of the same plugin, and the predecessor
`claude-code-kit@claude-code-kit` is a third. <!-- old-name-ok doc-status-ok: names the predecessor install to remove -->
Claude Code loads every enabled ID. With two `hiway-kit` IDs enabled you do not get two clean
copies, you get a mix (measured with `--debug`, Claude Code 2.1.330, 2026-11-21, n=1: directory
5.5.1 + direct 5.7.1):

| Component | Two `hiway-kit` IDs enabled |
| --- | --- |
| Skills | loaded from both copies — 15 + 17 = 32 entries, nothing deduplicated |
| Hooks | registered from one copy only; the other is skipped (`Skipping duplicate hook registration`) |
| Agents | one copy per name — in this run all 15 came from the older directory copy |

The predecessor has a different plugin name, so nothing is merged at all: its skills, agents and hooks
load next to the current ones ([rename probe](specs/2026-09-07-rename-probe.md)). Installing the
**same** ID at both user and project scope is one install — its hooks ran once.

From 5.9.0 the path B session check warns at session start (and again after `/clear` or compaction)
when two or more of these IDs are enabled for the current project. It can only warn when Claude Code
registered path B's hooks: with two `hiway-kit` IDs enabled the hooks come from one copy, and which
copy was not recorded in the measurement above. It reads Claude Code's install record (`installed_plugins.json` in its config directory) and
the `enabledPlugins` settings; it does not see managed settings, `--plugin-dir` copies or other harnesses.

**From path A to path B:**

```bash
claude plugin uninstall hiway-kit@anthropic-plugin-directory
claude plugin marketplace add This-HW/hiway-kit
claude plugin install hiway-kit@hiway-kit
claude plugin list   # exactly one hiway-kit entry
```

**From path B to path A:**

```bash
claude plugin marketplace remove hiway-kit   # also uninstalls hiway-kit@hiway-kit
claude plugin install hiway-kit@anthropic-plugin-directory
claude plugin list
```

Removing a marketplace uninstalls every plugin installed from it (the CLI reports *"Also uninstalled 1
plugin from this marketplace"*). To keep the marketplace, run `claude plugin uninstall
hiway-kit@hiway-kit` instead. If you installed with `setup.sh`, `./setup.sh --uninstall` removes the
pre-commit hook copies it wrote (only while they are still byte-identical to the shipped file),
unsets `init.templateDir` when that folder holds nothing but its copy, and deletes its state file. It
prints the plugin commands above instead of running them (`--dry-run` shows what it would do).

**From the predecessor:**

```bash
claude plugin uninstall claude-code-kit@claude-code-kit   # predecessor: old-name-ok doc-status-ok
claude plugin marketplace remove claude-code-kit          # predecessor: old-name-ok doc-status-ok
```

Then install path A or B.

**What was measured.** Every command above ran against an empty `CLAUDE_CONFIG_DIR` with no sign-in,
Claude Code 2.1.330, on 2026-11-21. Each `--json` result was `"outcome":"ok"`, and
`installed_plugins.json` and `enabledPlugins` were read back after every step: `uninstall` and
`marketplace remove` leave no `enabledPlugins` entry behind, while `disable` keeps the install and sets
its entry to `false`. Uninstalling does **not** delete the plugin's cache directory
(`plugins/cache/<marketplace>/<name>/<version>`), so a cache directory is not evidence of an install.
The in-session slash forms (`/plugin uninstall …`) were not part of this measurement.

## Codex

Two install paths deliver **different things** — pick deliberately:

| | Marketplace install (below) | OpenAI directory ZIP |
| --- | --- | --- |
| Skills | all | all (same bytes) |
| Hooks | `session-start` + `auto-format` (after trust) | **none** — the portal rejects plugins containing hooks, so the ZIP drops `hooks/` |
| How norms arrive | `SessionStart` injection; `AGENTS.md` fallback | **only** `AGENTS.md` — run `/harness-export` in your project, or nothing is injected (measured 2026-10-05, n=1) |
| Status | works today | see the channel table in [`docs/marketplace-submission.md`](marketplace-submission.md) |

```bash
# Add this repo as a plugin marketplace, straight from GitHub (measured codex-cli 0.160.1, 2026-10-19)
codex plugin marketplace add This-HW/hiway-kit
# ...or from a local clone
codex plugin marketplace add /path/to/hiway-kit

# Install
codex plugin add hiway-kit@hiway-kit-marketplace

# Verify
codex plugin list   # shows hiway-kit@hiway-kit-marketplace

# Remove
codex plugin remove hiway-kit@hiway-kit-marketplace
codex plugin marketplace remove hiway-kit-marketplace
```

Codex also reads the repo's existing `.claude-plugin/marketplace.json` as a legacy path, alongside
the generated `.agents/plugins/marketplace.json`.

The generated Codex hook sets `additionalContextLimit: 0` (no trimming — Codex otherwise trims hook
output above 2,500 tokens), so the kit's own injection budget gate is the only limit. Codex asks you
to trust a hook once per handler-config hash, so it asks again whenever that config changes.

Keep the configured marketplace source consistent with the version you intend to use. A one-command
`-c` source override does not change the persistent source: a later ordinary install can replace the
preview build with the configured source's version. Test unpublished builds in a separate `CODEX_HOME`
with a persistent local marketplace; keep the release installation on its chosen source.

For a read-only installation/source comparison, run the installed tool with an explicit home:

```bash
python3 -B /path/to/hiway-kit/tools/install_doctor.py \
  --codex-home /path/to/codex-home --plugin hiway-kit@hiway-kit-marketplace
```

For a Git source, add `--source-checkout /path/to/existing-checkout`; its local origin URL must match
the configured source. This currently requires an ordinary checkout: a git worktree's `.git` file
returns `source_checkout_is_worktree_unsupported` with exit 2 and is not followed.
The doctor never fetches or reinstalls. Exit 0 confirms version and identity agreement with the
source being compared. For a Git source, this means only the supplied checkout:
`installation.comparison_scope` is `supplied_checkout` and `remote_freshness` is `unverified`.
Git checkout manifest, identity or version problems return exit 2 with a
`source_checkout_unverified_*` reason; version mismatches include both versions.
Exit 1 means a confirmed installation/store/hook defect or a mismatch with the configured local source;
exit 2 means insufficient, unsupported or stale evidence. Confirmed defects take priority over unknown
evidence; `decision` gives the final result and `observations` preserves reasons by layer. An absent
explicit `--installed-path` is unknown; an existing installation missing its manifest is a defect.
It reports hook discovery, trust, enabled
choice and execution separately; an unknown hook state is not proof of failure or success. A safe shared
`plugins` store is supported, and `--plugin-store` can constrain its canonical root. Python 3.11+ reads
TOML directly; Python 3.9/3.10 can use `--snapshot` captured with `--capture-snapshot` on 3.11+.
Snapshots bind to the original paths and hashes and become unusable when those originals change.
`--capture-snapshot` is an explicit write mode: it creates the requested new JSON file.
Config and snapshot symlinks (including symlink parents) are unsupported and return exit 2 without
reading the target. For an ancestor symlink, `pass_canonical_path` asks for the canonical path explicitly;
system aliases such as `/tmp`, `/var` or `/home` are not automatically trusted.
Unsafe links below the plugin store remain confirmed defects (exit 1). Authentication filenames,
including `.credentials.json`, `.env` and `.env.*`, are rejected before opening them.

### Trusting and enabling Codex hooks

Installing, discovering, trusting, enabling and executing a hook are separate states. Native approval
must match the current plugin contents; updates can require approval again. A hook explicitly disabled
in configuration stays disabled after trust approval. Do not infer rule injection from installation or
trust alone. Depending on the CLI version and failure, unavailable trust may appear as a skipped hook
or a hook-approval error.

- **Interactive `codex`**: review the native hook trust prompt and your enabled choices, then
  verify execution in a new session. The kit does not approve or enable hooks automatically.
- **Non-interactive `codex exec`**: a run cannot rely on an interactive approval prompt.
  Check the native trust and enabled states before treating hook output as available.

**Hooks are the better path, not the only one.** Even with hooks off, the norms still
reach Codex through the entrypoint file (`AGENTS.md`, see
[`/harness-export`](../plugins/common/skills/harness-export/SKILL.md)), and a session can
fetch the ledger digest itself — the `feedback-loop` rule tells it how. What you lose
without trust is automatic delivery, not the discipline.

### Skills that name a sub-agent: read them as a contract, not a transport

Delegation availability depends on the host and its enabled tools. Check the current session's
capabilities instead of assuming a named sub-agent is available. Skills that dispatch an agent
(`debug`, `review`, `test`, `auto-dev`, `multi-perspective-review`) name the agent as a contract.
Each of those skills carries an explicit degradation path: the delegation is one
**transport**, and the invariant is the **contract** inside the block — persona, checks,
output format, completion declaration. On a harness with no delegation, perform the same
contract in the session itself and produce the same output. **Do not skip the step, and
do not report a delegation that did not happen.** The cost is stated in each skill:
performing it inline shares the session's context, so the blind-spot separation a
separate agent would give you is gone — which matters most for `review`'s adversarial
pass, where the isolation is part of the value.

## Antigravity

```bash
# Validate (checks the manifest and component dirs — it counts files, it does not prove recognition)
agy plugin validate /path/to/hiway-kit/plugins/common

# Install from GitHub (agy finds plugins/common in the repo; measured agy 1.4.2, 2026-10-18)
agy plugin install https://github.com/This-HW/hiway-kit

# ...or from a local clone
agy plugin install /path/to/hiway-kit/plugins/common

# Verify
agy plugin list   # shows hiway-kit

# Remove
agy plugin uninstall hiway-kit
```

Norms reach Antigravity only through `AGENTS.md`/`GEMINI.md` — run `/harness-export` in your
project. Antigravity reads **both** files, so the identical copies the export writes are loaded
twice (measured 2026-10-05).

**No official public registry is confirmed for Antigravity.** `agy plugin` also offers
`install <plugin>@<marketplace>`, `link`, and `import [gemini|claude]`; none of these is verified
with this kit, so the GitHub and local paths above are the only ones documented here. Both install
hiway-kit 5.4.2 with its then-current skill set; agents are skipped (see the capability table in the [README](../README.md#where-it-runs)).

## Cursor

`plugins/common/.cursor-plugin/plugin.json` (generated, like the others) ships **the skills only**.
Hooks are set to an empty inline config, so Cursor does not pick up the Claude Code `hooks/hooks.json`.
That file's exec form and `${CLAUDE_PLUGIN_ROOT}` are unmeasured on Cursor. Agents (`model: opus` and
other Claude values) and rules (`.md`; Cursor expects `.mdc`) are left out for the same reason. The
manifest passes Cursor's published JSON schema. An install round trip has **not** been measured: this
machine has no Cursor. Norms reach Cursor only through `AGENTS.md` (run `/harness-export`).

## Gemini CLI

The kit provides **only `GEMINI.md`** for Gemini CLI (written by `/harness-export`; Gemini CLI reads
`GEMINI.md` by default, not `AGENTS.md`). There is no Gemini extension package, and no skills, hooks,
or agents are shipped for it. Its runtime has **not been measured** with this kit (the test machine
had no working API key). Gemini CLI is not a supported target beyond that file; this will be
reconsidered once it can be measured.

## Hermes Agent

**Researched, not supported yet.** No Hermes package is published. The design (a generated `hermes`
branch carrying an Agent Plugins v1 edition, installed by commit sha) and its measurement plan are in
[`specs/2026-11-24-hermes-edition/`](specs/2026-11-24-hermes-edition/design-verdict.md). This section
will gain install commands only after that edition has been installed and observed in a sandbox. Every
statement below comes from reading Hermes source and docs at `NousResearch/hermes-agent@352b249`
(stable v0.23.3), not from running it.

**Rules reach Hermes today through `AGENTS.md`.** Run `/harness-export` in another harness, or the
exporter directly:

```bash
python3 <kit root>/tools/export_harness.py --plugin-root <kit root> --target <project> --entrypoints AGENTS.md
```

Hermes loads **one** project context file, the first that exists: `.hermes.md`/`HERMES.md` →
`AGENTS.override.md` → `AGENTS.md` → `CLAUDE.md` → Cursor rules. If your project has one of the first two,
`AGENTS.md` is not read — export into that file instead (it is your file; the exporter only writes
between its own markers). Hermes scans context files for prompt-injection patterns and replaces the
**whole file** when one line matches, so a line elsewhere in that file can hide the kit block too. The
per-file size budget defaults to 20,000 characters and is configurable.

**Skills, for evaluation only:** list a **read-only** clone's `plugins/common/skills` under
`skills.external_dirs` in `~/.hermes/config.yaml`. Three caveats:

- Hermes does not read `disable-model-invocation`, so `harness-export`, `skill-forge` and `using-hiway-kit`
  become ordinary skills the model may call on its own on this path — `harness-export` writes files.
- Hermes can edit files in external skill folders (`skill_manage`); keep the clone read-only.
- If the `~/.agents/skills` symlinks below are also listed there, every skill loads twice.

**Not available on Hermes:** kit agents (Hermes has no agent-definition loader — `delegate_task` takes a
goal and context, and the child inherits the parent's tools), kit hooks (Hermes shell hooks live in the
user's `config.yaml` and receive a different payload), and MCP servers (the kit bundles none).

`hermes plugins install This-HW/hiway-kit/plugins/common` is **refused** (`manifest_invalid`):
`plugins/common/plugin.json` is the Antigravity manifest, and Hermes accepts a `plugin.json` only with
the Agent Plugins v1 `$schema`. Keep it that way — that tree carries the hooks and the manual-only
skills, and `build-targets.py --check` guards the refusal.

## Sharing skills across harnesses (`~/.agents/skills`)

Several harnesses also read a user-level skills folder — Codex and Gemini CLI read
`~/.agents/skills`, Antigravity a workspace `.agents/skills`. Symlinking the kit's skill folders
there makes them visible to those harnesses without a plugin install. Two costs: the skills lose
the `hiway-kit:` namespace (they appear under their bare names), and if the same harness **also**
has the plugin installed, every skill loads twice — the same "never run two copies" rule as the [README install note](../README.md#quick-install).

The [`skills` CLI](https://skills.sh) copies the published skills into whichever agents it detects (listed at
[skills.sh/this-hw/hiway-kit](https://skills.sh/this-hw/hiway-kit)). This repo's three maintainer skills in
`.claude/skills/` carry `metadata.internal: true`, so the CLI skips them and finds the published skills under
`plugins/common/skills/` (measured skills 1.7.2, 2026-10-19 — without the flag it found only those three):

```bash
npx skills add This-HW/hiway-kit
```
