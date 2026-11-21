# Security Policy

## Reporting a vulnerability

Report security issues privately through GitHub's private vulnerability reporting:
<https://github.com/This-HW/hiway-kit/security/advisories/new>

Please do not open a public issue for a suspected vulnerability. Include the kit version
(`plugins/common/.claude-plugin/plugin.json`), the harness you ran it on (Claude Code, Codex,
Cursor, Antigravity), and the steps to reproduce.

## Supported versions

Only the latest release receives fixes. Releases are tagged `vX.Y.Z`; `CHANGELOG.md` lists what
each one changed.

## Scope

In scope: everything under `plugins/common/` (skills, agents, rules, hooks, tools) and the
installer `setup.sh`.

Out of scope: third-party plugins, MCP servers and tools that the kit calls only when you have
installed them.
