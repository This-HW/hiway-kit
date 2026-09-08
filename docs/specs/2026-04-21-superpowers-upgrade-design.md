# Claude Code Kit — Upgrade & Official Plugin Registry Design

**Date**: 2026-04-21  
**Status**: Completed — 2026-04-22  
**Goal**: Upgrade claude-code-kit to latest Claude Code specs, prepare for official plugin registry submission, fix all errors and strengthen exception handling.

---

## Context

Current version: 1.1.5 (33 agents + 12 skills across 6 domains).  
Target: Meet `claude-plugins-official` marketplace quality standards and submit via [platform.claude.com/plugins/submit](https://platform.claude.com/plugins/submit).

Key findings from official docs (`code.claude.com/docs/en/plugins-reference`):
- Plugin agents do NOT support `hooks`, `permissionMode`, `mcpServers` in frontmatter
- `plugin.json` requires `homepage`, `repository`, `license`, `author.email` for marketplace quality
- Hook paths must use `${CLAUDE_PLUGIN_ROOT}` — not absolute `~/.claude/hooks/` paths
- New hook events available: `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `PreCompact`, `PostCompact`
- New agent frontmatter fields supported: `maxTurns`, `background`, `memory`

---

## Approach: Sequential Layer Upgrade (Option 1)

Three independent phases, each CI-verified before the next:

```
Phase 1 (Structure/Manifest) → Phase 2 (Model/Prompt) → Phase 3 (Errors/Tests)
```

---

## Phase 1: Structure & Manifest Cleanup

### 1-1. plugin.json — Add Missing Fields

All domain `plugin.json` files (`common`, `frontend`, `infra`, `ops`, `data`, `integration`) need:

```json
{
  "author": {
    "name": "This-HW",
    "email": "thisyj.work@gmail.com",
    "url": "https://github.com/This-HW"
  },
  "homepage": "https://github.com/This-HW/claude-code-kit",
  "repository": "https://github.com/This-HW/claude-code-kit",
  "license": "MIT"
}
```

### 1-2. Agent Frontmatter — Remove Unsupported Fields

Official spec: plugin agents only support `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `skills`, `memory`, `background`, `isolation`.

Fields to remove from all agents:
- `permissionMode` — not supported for plugin agents (found in 6 agents)
- `hooks` (inline) — not supported for plugin agents; already dead references (`governance-check.py` intentionally removed in eb9e11b)
- `context_cache` — non-standard field
- `output_schema` — non-standard field  
- `next_agents` — non-standard field

Agents affected: `implement-code`, `fix-bugs`, `write-tests`, `sync-docs`, `define-business-logic`, `design-user-journey`, plus infra/ops agents.

### 1-3. Hook Paths — Use ${CLAUDE_PLUGIN_ROOT}

Current agent frontmatter hooks reference `~/.claude/hooks/` (absolute path, breaks on other machines).  
After removing agent-level hooks (1-2 above), verify `hooks/hooks.json` uses only `${CLAUDE_PLUGIN_ROOT}/hooks/`.

### 1-4. CI Validate — Strengthen Checks

Add to `.github/workflows/validate.yml`:
- Check `homepage`, `repository`, `license` exist in each `plugin.json`
- Check no agent `.md` contains `permissionMode:` or inline `hooks:` in frontmatter
- Version field presence check

---

## Phase 2: Model IDs & Prompt Quality

### 2-1. Model Field Completeness

Model aliases (`sonnet`, `opus`, `haiku`, `inherit`) resolve automatically to latest Claude versions — no alias changes needed. Action: find agents missing `model` field and add appropriate one per category:

- `opus`: strategy, analysis, review agents
- `sonnet`: implementation, fix, test agents  
- `haiku`: exploration, verification, simple agents

### 2-2. New Frontmatter Fields

Add to appropriate agents:
- `maxTurns`: prevent infinite loops — suggest 20 for implementation agents, 10 for exploration
- `background: true`: ops agents that run async (notify-team, schedule-task, trigger-pipeline)
- `memory`: enable for agents that need cross-session state

### 2-3. Skill description Field Quality

Official docs: `description` field is used by Claude for auto-invocation. Requirements:
- Must be in English (current: Korean mixed)
- Must be specific enough for Claude to know when to invoke
- Remove non-standard frontmatter fields (`argument-hint`, `domain`, `allowed-tools`)
- Add `disable-model-invocation: true` to pure instruction skills (no LLM needed)

### 2-4. New Hook Events

Add to `hooks/hooks.json`:

| Event | Purpose |
|---|---|
| `SubagentStart` | Log agent invocation start |
| `SubagentStop` | Log agent completion + delegation signal |
| `TaskCreated` / `TaskCompleted` | Track task lifecycle |
| `PreCompact` | Save active work state before compaction |

---

## Phase 3: Error Scan + Exception Handling + Tests

### 3-1. Python Hook Hardening

Scan all hook Python files (`protect-sensitive.py`, `auto-format.py`, `session-start.py`, `utils.py`):

| Issue | Fix |
|---|---|
| `subprocess.run()` without timeout | Add `timeout=FORMATTER_TIMEOUT_SECONDS` consistently |
| Missing `safe_path()` on some inputs | Apply to all file path inputs |
| JSON parse errors on stdin | Graceful fallback: allow-on-parse-error |
| `CLAUDE_PLUGIN_ROOT` not set | Add fallback to script directory |
| Exit codes inconsistent | Document and standardize: 0=allow, 2=block/feedback |

### 3-2. Agent/Skill Validation Scan

Detect and fix:
- Agents missing `MUST USE when:` in description
- Agents with `description` over 500 chars (too long for Claude to parse reliably)
- Agents missing `model` field

### 3-3. Hook Unit Tests

Create `plugins/common/hooks/tests/`:

```
tests/
├── test_protect_sensitive.py   — block cases (secrets) + allow cases
├── test_auto_format.py         — Python/JS format trigger verification
├── test_session_start.py       — frontmatter parsing, output format
└── test_utils.py               — safe_path, debug_log utilities
```

Run with: `python3 -m pytest plugins/common/hooks/tests/ -v`

### 3-4. CI Test Stage

Add `pytest` execution to `.github/workflows/validate.yml` after JSON validation step.

---

## Success Criteria

- [x] All domain `plugin.json` files have `homepage`, `repository`, `license`, `author.email`
- [x] No agent contains `permissionMode`, inline `hooks`, `context_cache`, `output_schema`, `next_agents`
- [x] `hooks/hooks.json` uses only `${CLAUDE_PLUGIN_ROOT}` paths
- [x] All agents have `model` field set
- [x] Skill `description` fields are in English and specific
- [x] All `subprocess.run()` calls have timeout
- [x] Hook unit tests pass: `pytest plugins/common/hooks/tests/ -v` (91 passed)
- [x] CI passes all new validation checks
- [x] Version bumped to 2.0.0 (breaking changes to frontmatter schema)

---

## Version Strategy

- Phase 1 → 2.0.0-beta.1 (breaking: removes non-standard frontmatter fields)
- Phase 2 → 2.0.0-beta.2
- Phase 3 → 2.0.0 stable ✅ Released 2026-04-22
- Submit to official registry at 2.0.0

---

## Submission Checklist (Post-Implementation)

- [x] README updated with new features and installation instructions
- [x] CHANGELOG.md documents all breaking changes
- [ ] Plugin tested with `claude --plugin-dir ./plugins/common`
- [ ] Submit at `platform.claude.com/plugins/submit`
