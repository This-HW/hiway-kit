---
tier: conditional
activates: MCP 설정 존재 감지 (.mcp.json)
portable: false
---

# MCP Usage Rules

## MCP Servers

PREFER these MCP servers when installed, falling back to built-in tools when absent —
never assume a server is present:

- **Context7** — library/framework docs; prefer over WebFetch for API references (fall back to WebFetch)
- **Exa** — semantic code/tech search; prefer over WebSearch for precise technical queries (fall back to WebSearch)
- **Tavily** — comprehensive research, fact-checking, tech comparison
- **Playwright** — dynamic page scraping, E2E tests; prefer over WebFetch for JS-rendered pages
- **Sequential Thinking** — complex multi-step design and problem decomposition
- **PostgreSQL** — DB queries, schema exploration, query optimization
- **Magic** (21st.dev) — natural language → UI components

## Tool Selection

In the **main session or a skill** (where MCP is safely inherited), PREFER MCP over
built-in tools when the server is available, and fall back to built-in on absence/failure:

- Library/framework docs → **Context7** (fall back to WebFetch)
- Semantic/code search → **Exa** (fall back to WebSearch)
- Dynamic page → **Playwright** (fall back to WebFetch)
- DB queries → **PostgreSQL** (fall back to Bash psql)

Never assume an MCP server is installed — different users have different (or no) MCP
servers. If a preferred MCP is missing or errors, use the built-in equivalent; never
fabricate results.

DO use built-in tools when:

- Simple web search → **WebSearch**
- Static page fetch → **WebFetch**

## Required Rules

If your PostgreSQL MCP needs a tunnel/proxy, start it before use — this is
environment-specific (the kit ships no tunnel script).

When using Context7, ALWAYS specify the version: `"use context7 for Next.js 15 App Router"` — never omit it.

Verify library APIs against docs, not training memory alone — with Context7 when available,
otherwise official docs via WebFetch/WebSearch.

## Agent MCP Configuration — MCP lives in skills, NOT agent allowlists

**NEVER put `mcp__*` tools in a shipped agent's `tools:` allowlist.** Consumers install
different (or no) MCP servers, and a project-scoped MCP tool that is listed but absent
makes the agent **hallucinate plausible-but-wrong results or hard-fail** — see Claude Code
issue #13898 "Custom Subagents Cannot Access Project-Scoped MCP Servers (Hallucinate
Instead)" (github.com/anthropics/claude-code/issues/13898). Therefore:

- **MCP-dependent research / docs lookup → the `web-research` skill.** A skill runs in the
  main session context, safely inherits installed MCP servers, and falls back to built-in
  WebSearch/WebFetch when they are absent.
- **Shipped agents use built-in WebSearch/WebFetch only** (research-external included).
- For library-API verification during coding, reach Context7 via the main session / a
  skill — do NOT wire MCP into the agent frontmatter.

> Regression guard: no `agents/**/*.md` **frontmatter `tools:` block** contains an `mcp__`
> entry, **and no agent description/body directs use of Context7/Exa/Tavily as its own
> capability** (route such research to the `web-research` skill instead). Both are checked
> by `scripts/verify-done.sh`.
