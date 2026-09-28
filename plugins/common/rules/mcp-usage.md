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
