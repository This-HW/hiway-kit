---
tier: core
portable: true
---

# Code Quality Rules

- **Functions**: ALWAYS under 20 lines/3 params/2 nesting, single responsibility,
  role-expressing names (`calculateTotalPrice`); NEVER 50+ lines, vague names
  (`calc`, `handle`, `doStuff`).
- **Errors**: NEVER ignore or log-only; ALWAYS handle each type explicitly, rethrow
  unknown errors upward with context (code, message, cause) preserved.
- **Conditionals**: ALWAYS early return over nested conditions; extract complex
  boolean expressions into named variables.
- **Type safety**: NEVER bypass the type system (`any`/untyped escape hatches,
  overused type-assertion casts) — use explicit types and type guards. ALWAYS
  handle null/absent values explicitly.
- **Testability**: ALWAYS inject dependencies (constructor/factory param), NEVER
  hardcode object construction inside a function. Prefer pure functions.
