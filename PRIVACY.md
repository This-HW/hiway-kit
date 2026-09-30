# Privacy Policy — hiway-kit

_Last updated: 2026-09-30_

hiway-kit is an open-source plugin (skills, rules and local hooks) for coding agents such as Claude Code and
Codex. It is published by This-HW. This policy describes what the plugin does with data.

## What the plugin collects

**Nothing.** The plugin has no accounts, no telemetry, no analytics and no server. It does not read, store or
transmit personal data, and the publisher receives no data from your use of it.

## Network access

**The plugin makes no network calls.** Its hooks and helper scripts only run local commands: `git`, the formatter
or linter for the file being edited (for example `ruff`), your own test runner, and the verification commands you
write into a plan checklist.

Skills such as `web-research` tell your agent to use search or browser tools that **you** have installed. Any such
request is made by your agent and those tools under their own terms; the plugin ships no connector of its own.

## What stays on your machine

- A feedback ledger of recurring review findings, stored under your repository's `.git/kit/` (untracked). Outside a
  git repository it falls back to a file in the project.
- Hook state and lock files in a per-user directory (mode `0700`) under your system's temporary directory.
- Plan files you create under `docs/plans/` in your own repository.

You can delete any of these at any time. None of them is sent anywhere.

## Children

The plugin is a developer tool and is not directed at children.

## Changes

Changes to this policy are made in this file in the public repository, with the history visible in git.

## Contact

Questions about this policy: open an issue at https://github.com/This-HW/hiway-kit/issues
