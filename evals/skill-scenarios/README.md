# Deterministic skill CLI coverage

`scripts/check_skill_eval_coverage.py` discovers every
`plugins/common/skills/*/SKILL.md`. Only the fixed pre-5.6 cohort has reasoned
exceptions in `evals/policy.json` under `skills.legacyExceptions`. The checker
seals its sorted names with the SHA256 of the tree identified in its source;
adding or replacing an exception with a new skill fails. The names and reasons
have one owner in policy, without a second generated list or dependency on git
history at runtime. Retiring that frozen debt cohort requires an explicit
checker/policy review.

Each remaining skill needs positive and negative cases in JSON files one
directory below this folder. Cases reference plain module-level pytest
functions under `tests/hooks`; the checker parses Python syntax without
importing tests or executing policy content. Unknown fields (including shell
commands), duplicate cases/nodes, missing functions, decorated tests, path
escapes, malformed policy and empty lists fail. Paths are resolved once and
checked against the allowed root before reading.

`tests/hooks/test_skill_cli_contracts.py` executes actual CLI subprocesses
against isolated synthetic logs and AST/LSP peers. JSON expectations describe
the assertions owned by those tests. The existing pytest gate executes these
tests; section 29 separately checks structural coverage. Synthetic AST peers
verify argument forwarding and read-only previews, not native pattern parsing.
Installed real-engine checks in `test_code_intel.py` and `test_lsp_query.py`
are separate evidence and may skip when the engines are absent.

Coverage passing is not evidence of natural-language skill selection, actual
skill loading in Codex, model quality, or equivalence of skill use. Those are
separate sample evaluations with their own transcripts and sample counts.
The existing agent checker, baseline and model evals remain separate.
