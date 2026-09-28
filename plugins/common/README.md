# hiway-kit

> Turn any task into production-ready code. Specialized agents handle planning, implementation, code review, and security scanning for any stack.

## Install

```bash
# Direct marketplace (marketplace name: hiway-kit)
/plugin marketplace add This-HW/hiway-kit
/plugin install hiway-kit@hiway-kit
```

> The published plugin is **`hiway-kit`** (15 agents + 15 skills + 12 rules + hooks).
> Project-specific extensions live in a user's own `project-local/` tier, not as separate
> published plugins.

## Key Skills

A selection below — 15 skills total, auto-discovered from `skills/` (not hand-listed here).

| Command                     | Description                                              |
| --------------------------- | -------------------------------------------------------- |
| `/plan-task`                | Structured task planning into a plan file                |
| `/auto-dev`                 | Run a completed plan through development and validation  |
| `/review`                   | Lint + adversarial review + security scan                |
| `/debug`                    | Diagnose an error, fix it, confirm the fix               |
| `/test`                     | Run tests and fix failures                               |
| `/multi-perspective-review` | Multi-perspective deliberation, consensus-driven         |
| `/web-research`             | Research with the search/docs/browser tools you have     |
| `/agent-creator`            | Create a project agent with valid frontmatter            |

## Agents

15 agents across planning, development, review, and meta categories.

| Category   | Count | Examples                                                          |
| ---------- | ----- | ----------------------------------------------------------------- |
| Planning   | 3     | `clarify-requirements`, `define-business-logic`, `design-user-journey` |
| Dev        | 11    | `implement-code`, `fix-bugs`, `review-code`, `security-scan`      |
| Meta       | 1     | `devils-advocate`                                                 |

## Hooks (auto-registered)

- **SessionStart** — Injects governance rules, recurring review lessons, and open plan files
- **PreToolUse** — Blocks reads and edits of sensitive file paths such as `.env` and keys (`protect-sensitive.py`)
- **PostToolUse** — Auto-formats the edited file (`auto-format.py`: ruff for Python; prettier/eslint only when the project has them installed)
- **Stop** — Lints edited Python files and runs the tests you edited; on failure, the turn continues so the agent fixes it

The hooks make no network calls and write nothing outside your machine.

## License

MIT — [github.com/This-HW/hiway-kit](https://github.com/This-HW/hiway-kit)
