# hiway-kit

> Turn any task into production-ready code. Specialized agents automatically handle planning, implementation, code review, and security scanning for any stack.

## Install

```bash
# Anthropic community catalog (marketplace name: claude-community)
/plugin marketplace add anthropics/claude-plugins-community
/plugin install hiway-kit@claude-community
```

```bash
# Direct marketplace (fastest updates; marketplace name: hiway-kit)
/plugin marketplace add This-HW/hiway-kit
/plugin install hiway-kit@hiway-kit
```

> The published plugin is **`hiway-kit`** (the `common` set — 32 agents + 20 skills).
> Project-specific extensions live in a user's own `project-local/` tier, not as separate
> published plugins.

## Key Skills

A selection below — 20 skills total, auto-discovered from `skills/` (not hand-listed here).

| Command                     | Description                                     |
| --------------------------- | ----------------------------------------------- |
| `/plan-task`                | Structured task planning with Work system       |
| `/auto-dev`                 | Automated development pipeline                  |
| `/review`                   | Code review: ruff + adversarial review + security scan |
| `/debug`                    | 4-Phase debug pipeline                          |
| `/test`                     | Run tests and auto-fix failures                 |
| `/multi-perspective-review` | 10-perspective deliberation, consensus-driven   |
| `/web-research`             | MCP-powered research (Context7 + Exa + Tavily)  |
| `/doc-coauthoring`          | AI-assisted documentation authoring             |
| `/agent-creator`            | Generate plugin agents with correct frontmatter |
| `/skill-creator`            | Generate plugin skills                          |
| `/mcp-builder`              | Scaffold MCP servers                            |

## Agents

32 agents across planning, development, review, backend, and meta categories.

| Category   | Count | Examples                                                    |
| ---------- | ----- | ----------------------------------------------------------- |
| Planning   | 5     | `clarify-requirements`, `analyze-domain`, `define-business-logic` |
| Dev        | 18    | `implement-code`, `fix-bugs`, `review-code`, `security-scan` |
| Backend    | 4     | `design-services`, `implement-api`, `write-api-tests`       |
| Meta       | 6     | `facilitator`, `devils-advocate`, `consensus-builder`       |

## Hooks (auto-registered)

- **SessionStart** — Injects governance rules + active work context
- **PreToolUse** — Blocks edits containing secrets (`protect-sensitive.py`)
- **PostToolUse** — Auto-formats code after edits (`auto-format.py`, ruff)
- **Stop** — Phase-gate check before session ends

## License

MIT — [github.com/This-HW/hiway-kit](https://github.com/This-HW/hiway-kit)
