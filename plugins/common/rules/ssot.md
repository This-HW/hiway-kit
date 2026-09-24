---
tier: core
portable: true
---

# SSOT (Single Source of Truth) Rules

- Define error types, API endpoints, and env vars in one place and reference that
  definition — copied values get fixed on one side only and drift.
- One change that needs edits in many files, or the same bug in several places, is an
  SSOT violation signal. If the project has a central error handler, route errors through it.
