---
title: "LSP index Unit A: cache, coverage and resource primitives"
status: current
execution_status: in-progress
as_of: 2026-11-08
created: 2026-11-08
size: large
---

## 요구사항

[confirmed: delegated plan-control contract freeze] Implement Unit A of docs/specs/2026-11-08-default-lsp-index.md from fd7d612. Frozen contract/policy/plan hashes: cf938079457473e8cf88ff5ae57535f287e355434496bfe192bbc03193e1b4f9 / 706556a7537db7dc0892aabf7474c90681f113b64b64c5aad4296a054028e6e0 / 5c5c6a899eaa0c74a1b0bd6f6f5764af8a25438ef63f3d3bb4add6317eb27b2e. Implement secure cache/locks and stable semantic keys, bounded actual-shard coverage, child-tree monitoring and absolute deadlines. No lsp_query entrypoint integration in A.

## 결정

[confirmed] Separate local lsp-index-unit-a branch/worktree, no agent or push; preserve omo_test fd7d612. Independent review requires base+commit+diff. Unit B requires A ACCEPT. All third-party execution keeps approved proof sandbox; stdlib unit tests and kit development follow normal project workflow. New tests use unittest-compatible APIs to run under installed Python3.9 without installing pytest. Linux local fake tests are explicitly not CI evidence. Final integration/minor base/release remain plan-control decisions; do not fabricate tags for unreleased 5.7.2. API modules have no entrypoint caller until B; final release bump and full product gate belong to integration.

Repository document-status convention takes precedence over generic plan-format status vocabulary: current is document status and execution_status tracks the task. This follows the existing AST plan rather than weakening the document checker.

## 구현 계획

1. Policy/absolute deadline and platform resource adapters with fake-/proc and actual child controls.
2. Owned no-follow cache coordinator, global/key locks, durable first-attempt classification, safe retention and stable semantic key tests.
3. Bounded RIFF coverage parser using the same URI/filesystem identity as CDB descriptors, with synthetic and actual native fixture controls; no opaque hash implementation.
4. Review-focused regression/rollback and Python3.9 evidence, then A commit and independent review. Do not start B before ACCEPT.

## 완료 조건

- `python3 -m pytest -q tests/hooks/test_lsp_index_resources.py`
- `python3 -m pytest -q tests/hooks/test_lsp_index_cache.py`
- `python3 -m pytest -q tests/hooks/test_lsp_index_coverage.py`
- `python3.9 -B -m unittest discover -s tests/hooks -p 'test_lsp_index_*.py'`
- Production reversion must fail the new focused suites; original production files restored cleanly afterward.
- A independent review ACCEPT. Full fresh scripts/verify-done.sh/Ubuntu/directory Validate are final integration gates, not A-only claims.

## 검증 결과

- Focused macOS Python3.12 pytest and Python3.9 stdlib unittest: 42 passed each, no installation.
- Product parser readback of actual Apple21 shards: Build/Skip/same-basename/errors/External five cases, Python3.12 and3.9 output identical. These read stored shards; no new server timing claim.
- Base lacks all four new production modules: literal absence yields collection rc2 only. Five separate production-invariant defeats (semantic env key, durable grant, locking, coverage truthfulness, RSS guard) yield assertion rc1 and restore byte-identically; this distinction is preserved in evidence.
- Ruff and document reference/status checks passed. Existing project doc-status vocabulary is retained with execution_status for progress.
- Independent A review pending; Linux fake contracts executed locally, actual Ubuntu CI unverified. Unit B, full frozen product gate, minor bump and release are not complete.
