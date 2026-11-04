# Privacy Policy — hiway-kit

_Last updated: 2026-11-04_

hiway-kit is an open-source plugin (skills, rules and local hooks) for coding agents such as Claude Code and
Codex. It is published by This-HW. This policy describes what the plugin does with data.

## What the plugin collects

The plugin has no accounts, telemetry, analytics or publisher server. The publisher receives no data
from its helpers. Local tools read explicitly selected project files and session logs, which can contain
personal or sensitive information, and return results to the calling agent. Your agent provider's data
policy applies to the content you make available to that agent.

## Network access

The kit does not send telemetry. Its hooks and helpers invoke local commands, including language servers,
AST search, formatters, tests and your verification commands. Those processes can execute workspace code,
write files or make network requests. For example, a language server may run project build scripts or macros.
Use code intelligence only in trusted workspaces. Read-only query and preview modes describe the client's
editing behavior; they do not sandbox the executed tools or guarantee an offline run.

Skills such as `web-research` tell your agent to use search or browser tools that **you** have installed. Any such
request is made by your agent and those tools under their own terms; the plugin ships no connector of its own.

## What stays on your machine

- A feedback ledger of recurring review findings, stored under your repository's `.git/kit/` (untracked). Outside a
  git repository it falls back to a file in the project.
- Hook state and lock files in a per-user directory (mode `0700`) under your system's temporary directory.
- Plan files you create under `docs/plans/` in your own repository.

You can delete these local files at any time. The kit does not upload them to the publisher.
Content shared with your calling agent or external tools follows those services' policies.

## Children

The plugin is a developer tool and is not directed at children.

## Changes

Changes to this policy are made in this file in the public repository, with the history visible in git.

## Contact

Questions about this policy: open an issue at https://github.com/This-HW/hiway-kit/issues
