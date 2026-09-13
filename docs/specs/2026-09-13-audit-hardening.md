# Audit hardening

Goal: repair the five defects reproduced in the project audit without widening the toolkit's runtime responsibilities.

Approval: the user requested implementation of the reported remediation on 2026-09-13. Existing path-containment and validation contracts determine the behavior; no unresolved P0 decisions remain.

## Requirements and approach

1. Agent description accounting includes literal and folded YAML block bodies, including chomping indicators. Unsupported or malformed descriptions must fail visibly rather than disappear from the byte budget. Preserve stdlib-only tooling and Python 3.9 compatibility.
2. Packaging source.manifest and source.pluginRoot, including component discovery, must remain within their declared root after one resolution. Both check and write modes reject escaped inputs with PolicyError before trusting them. Reuse the existing containment convention.
3. Eval schema validation must collect meaningful errors for invalid git/expect object shapes without executing cross-field checks on invalid structures. Continue validating other scenarios.
4. Stop-validator state must use a private directory whose existing ownership, permissions and non-symlink identity are verified. Never fall back to a shared temporary root. If the stable state directory is unsafe, use a newly allocated private directory so validation can continue without trusting an attacker's counters. Preserve marker interoperability for the normal safe path.
5. Generated hook commands must treat configured interpreter and script names as literal shell arguments. Preserve plugin-root environment expansion, validate interpreter syntax, and cover spaces and shell metacharacters. Generated artifacts must match the generator.

## Alternatives

Targeted contract fixes with regression tests are selected. A generic YAML dependency or shared gate abstraction would add unrelated dependency/architecture changes. Rejecting all nontrivial script names would unnecessarily restrict valid filenames; shell quoting can preserve them.

## Components, flow and errors

Budget parser -> entries or explicit skipped/error result; packaging policy -> confined source paths -> literal hook commands -> artifacts; eval structural errors -> conditional cross-checks; stop hook -> verified private state -> ordinary validation. Preserve the central error/reporting mechanisms in each subsystem.

## Validation

Regression fixtures cover YAML block styles and excessive text; absolute, parent and symlink source escapes in check/write; malformed git and expect shapes; preexisting state symlinks, foreign ownership, permissive modes and directory-creation failures; shell literal round trips. Run affected tests and lint, independent code/security review, then scripts/verify-done.sh. Release metadata receives one patch bump through scripts/bump-version.sh.

## Scope and risk

Four implementation modules and their tests, release/generated metadata, and documentation are affected. No budget increase, broad complexity refactor, external release, plugin reinstall or behavioral model-eval rerun is required. Persistent state fallback may lose cross-process caching only when the established directory is unsafe; it must not bypass validation.
