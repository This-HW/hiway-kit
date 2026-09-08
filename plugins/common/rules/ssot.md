---
tier: core
portable: true
---

# SSOT (Single Source of Truth) Rules

- ALWAYS define error types, API endpoints, and env vars in exactly one place;
  NEVER copy values — reference the single definition (import/include/require, …)
- ALWAYS structure code so one change propagates everywhere — editing 10 files
  for one change is an SSOT violation signal, as is the same bug in multiple places
- ALWAYS route all errors through a single central handler with structured fields
  (`code`, `message`, `timestamp`, `severity`) — NEVER scatter error logic across modules
