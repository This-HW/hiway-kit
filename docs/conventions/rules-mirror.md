---
status: current
as_of: 2026-10-05
---

`plugins/common/rules/` is what the SessionStart hook injects, so it is compressed. Each rule's
`tier:` frontmatter decides how: `core` bodies every session, `conditional` bodies only when
`session-start.py` sees the matching signal, `reference` as a one-line index pointer only.
`docs/architecture/rules/` is the long-form human explanation of some of those rules — tables,
worked examples, anti-patterns. Rules without a mirror have none by design; the injected rule is
the whole story for them. Which rules are mirrored is whatever `MIRROR.sha256` lists.

Nothing linked the two, so they drifted silently — a 2026-08-17 audit found three behind,
and the (since-merged) `planning-check` mirror still told readers to search Notion/Figma MCP in order,
**assuming those MCPs are installed**, which contradicts the consumer-first north-star.
`docs/architecture/rules/MIRROR.sha256` now records, per mirrored rule, the sha256 of the
injected rule the explanation last reflected. `verify-done.sh §7` fails when they diverge;
`scripts/sync-rule-mirror.sh --regenerate` updates it. Regeneration is deliberate on
purpose — auto-updating the manifest would make the check meaningless.

Normative statements live in the injected rule. The mirror explains and points at it; it
must not redefine anything, or the drift comes back through the front door.
