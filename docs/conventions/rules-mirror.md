`plugins/common/rules/` (13) is what gets **injected every session**, so it is compressed.
`docs/architecture/rules/` (8) is the long-form human explanation of eight of those rules,
created in W-004 — tables, worked examples, anti-patterns. The remaining five
(`definition-of-done`, `feedback-loop`, `loop-engineering`, `parallel-worktree`,
`untrusted-text`) have no mirror by design; the injected rule is the whole story for them.

Nothing linked the two, so they drifted silently — a 2026-08-17 audit found three behind,
and the `planning-check` mirror still told readers to search Notion/Figma MCP in order,
**assuming those MCPs are installed**, which contradicts the consumer-first north-star.
`docs/architecture/rules/MIRROR.sha256` now records, per mirrored rule, the sha256 of the
injected rule the explanation last reflected. `verify-done.sh §7` fails when they diverge;
`scripts/sync-rule-mirror.sh --regenerate` updates it. Regeneration is deliberate on
purpose — auto-updating the manifest would make the check meaningless.

Normative statements live in the injected rule. The mirror explains and points at it; it
must not redefine anything, or the drift comes back through the front door.
