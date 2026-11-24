# hiway-kit — Hermes edition

The **Hermes Agent edition** of hiway-kit: an Agent Plugins v1 package generated from `main` by
`scripts/build-hermes-branch.py` onto the `hermes` branch. `main` keeps a manifest Hermes refuses, so an
install that is not pinned to this branch stops instead of loading the wrong tree.

What this page states was **observed** in a sandboxed, offline Hermes (`NousResearch/hermes-agent@352b249`,
the H1 measurement). Anything not measured is marked as such.

## Install (pinned to a commit)

`--ref` takes only a full 40-character commit sha of the `hermes` branch.

```bash
SHA="$(git ls-remote https://github.com/This-HW/hiway-kit refs/heads/hermes | cut -f1)"
test -n "$SHA" || { echo "hermes branch not found"; exit 1; }
hermes plugins install This-HW/hiway-kit/plugins/common --ref "$SHA" --force --no-enable
hermes plugins enable hiway-kit
```

H1 ran these steps against a local Git mirror of the same tree; the GitHub address is confirmed once the
branch is published.

**Why `--force` is needed.** Hermes' install scanner rates this edition **caution**
(critical 0). For a community source, a caution verdict blocks a non-interactive first install
with `Use --force to override.` The findings that drive it are **defensive example text** in documents, not
code that runs:

- `agents/review-code.md` — the security reviewer's examples of what to flag (access to a system password
  file, a recursive delete of the root directory)
- `skills/auto-dev/SKILL.md` — a mention of reading environment variables

## Update

There is **no automatic update**, and `hermes plugins update` refuses pinned installs. Install the new
sha over the old one:

```bash
hermes plugins install This-HW/hiway-kit/plugins/common --ref <new 40-char sha> --force --no-enable
```

Hermes replaces the files and keeps the plugin enabled (`Replacement installed; plugin selection was not changed.`).

## What is in it

- **15 skills** under the `hiway-kit:` namespace (for example `hiway-kit:plan-task`). They
  appear in the agent's skill list once the plugin is enabled, and disappear when it is disabled.
- `rules/` and `tools/`.
- `agents/` as **brief documents**: a skill may pass an agent body to `delegate_task` as context. Each
  agent starts with a note on what Hermes does not enforce (frontmatter, worktree isolation).

## What is not

- **No hooks.**
- **No agent loader** — agents are used only as `delegate_task` context.
- No `harness-export` and no `skill-forge` skill.
- No MCP servers.
- No behavioral evals (`evals/` is not shipped).

## Project rules (`AGENTS.md`)

Export the kit's rules into a project with the shipped CLI:

```bash
python3 <install root>/tools/export_harness.py --plugin-root <install root> --target <project> --entrypoints AGENTS.md
```

The install root is `hiway-kit` under the Hermes profile's `plugins/` directory — measured as
`<HERMES_HOME>/profiles/<profile>/plugins/hiway-kit`. Use that copy, not a same-named tool from another install. Hermes loaded the
generated `AGENTS.md`; a `.hermes.md` in the project **shadowed** it (measured). By Hermes' source,
`HERMES.md` and `AGENTS.override.md` take precedence the same way.

## `using-hiway-kit`

Hermes does not read the manual-only flag (`disable-model-invocation`), so the model can list and read
this skill on its own.

## Not measured

- Coexistence with Hermes' built-ins (verify-on-stop, automatic skill creation, memory) — needs a model run.
- No behavioral evals for this edition.

Details and caveats: `docs/harnesses.md#hermes-agent` in the repository.
