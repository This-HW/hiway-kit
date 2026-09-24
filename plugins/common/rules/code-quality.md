---
tier: core
portable: true
---

# Code Quality Rules

- **Functions**: one job, a name that says it (`calculateTotalPrice`, not `calc`/`handle`).
  Growing length, parameter count, or nesting is the signal to split.
- **Errors**: don't swallow them. Handle the types you can; otherwise rethrow upward with
  context (code, message, cause) preserved. A deliberate fail-open gets a comment saying why.
- **Conditionals**: prefer early return over nesting; name complex boolean expressions.
- **Type safety**: bypassing the type system (`any`, unchecked casts) hides bugs — use
  explicit types and guards, and handle null/absent values explicitly.
- **Testability**: construction hardcoded inside a function is hard to test — inject it.
  Prefer pure functions.
