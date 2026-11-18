---
title: "LSP index Unit B: lsp_query and transport integration"
status: current
execution_status: in-progress
as_of: 2026-11-09
created: 2026-11-09
size: large
---

## 요구사항

[confirmed: `docs/specs/2026-11-08-default-lsp-index.md` frozen contract and plan-control Unit A ACCEPT, 2026-11-09]
Implement Unit B on top of Unit A commit `2c5d007613b6d5e7a749719b776844ddb376d2ef`. Connect the existing one-shot C/C++ definition/references CLI to the reviewed cache, lock, coverage, absolute-deadline, and resource primitives. No persistent daemon, opt-in enable flag, install, new model evaluation, token/speed promise, main merge, tag, or push. Keep the global cache lease held through child exit, coverage/result finalization, cleanup, and output decision.

C/C++ definition/references use indexed mode only when every frozen input/config/platform/command condition is met. They retain the existing verified partial query on disable, unsupported inputs, timeout, or cache/index failures, and must preserve a previously validated partial response. Only progress-end plus exact shard coverage plus a fully validated final navigation response can set `complete: true`. `symbols`, diagnostics, other languages, and custom-server/custom-argument behavior retain their established contracts. Read `failure.json` written by Unit A and expose only its fixed reason/message; never print CDB or semantic environment values.

[confirmed: plan-control Unit A R3 ACCEPT] This work has its own Orca worktree/branch `lsp-index-unit-b`, based on the accepted Unit A commit above. The accepted Unit A branch and `omo_test` remain untouched. Unit A's binding single-squash/no-leaked-fixture-blob gate and the v5.7.1 directory review release gate remain in force; do not publish.

## 결정

- [confirmed: frozen spec + plan-control Unit B interface] `Connection` is the sole owner of each server `Popen`; no outside `poll()`/`wait()`. Indexed lifecycle uses `ResourceGuard.reap()` and closes the guard before releasing `Lease`.
- [confirmed: frozen spec] Pass `lease.global_lock_fd` via `pass_fds`; retain the cache global/key locks until process exit and all coverage/metadata work ends.
- [confirmed: frozen spec] Pass `lease.deadline` after `lease.begin_attempt()` has rebased the same object. Use one deadline for discovery, CDB/config reads, cache lock, initialize/open, partial request, progress readiness, coverage, final request, and shutdown.
- [confirmed: frozen spec] Retry only the same request when reason is `index_deadline` and validated `Coverage.covered` strictly increases; obey the additional-attempt bound. There is no internal retry loop.
- [confirmed: frozen spec + plan-control Unit B review] The child command for indexed mode is exactly `pinned clangd --background-index --limit-references=0 -j 2 --enable-config=false --compile-commands-dir=<frozen copy> --log=error`; no caller `--server-arg` or inferred extra flags. `--limit-references=0` prevents clangd's default 1000-reference ceiling from silently truncating indexed results. Custom arguments never opt into indexing.
- [confirmed: frozen spec] Keep existing non-indexed argv and output contracts for every fallback path. Add explicit partial reason/message and index metadata only where the spec calls for it; don't mislabel a partial response as no-match.
- [confirmed: user/plan-control] The behavioral change targets the 5.8.0 minor at final integration. This Unit B branch does not independently bump package versions or release artifacts.

## 구현 계획

1. Add strict, bounded CDB/config/toolchain preflight for C/C++ navigation: nearest supported in-workspace CDB, source identities, absolute compiler and pinned clangd identities, SDK resolution, semantic key inputs, and fail-closed unsupported/config reasons. Do not execute CDB commands or parse YAML.
2. Extend the LSP transport with a shared absolute deadline, per-connection progress token tracking, work-done progress creation/notifications, bounded receive/write/request waits, child environment and `pass_fds` injection, and ResourceGuard-owned process lifecycle. Preserve existing connection behavior when no index options are supplied.
3. Integrate the indexed path in `lsp_query`: disable/custom/no-CDB/config/platform fallbacks, cache/key/lease/attempt metadata, fixed server argv, validated initial partial response, readiness and exact coverage, final response, fallback reason/reporting, durable failure metadata, cleanup, and bounded evidence output.
4. Add fake-server CLI/transport contracts for response validation, progress sequences, withheld/malformed/unrelated progress, timeout and partial retention, lock loser, zero-shard attempted key, coverage growth/retry cap, config/CDB changes, semantic/nonsemantic key changes, exact argv including `--limit-references=0`, disable/custom/no-CDB, and unchanged non-target actions. Add test nodes proving `complete:true` cannot arise without every prerequisite.
5. Add documented cache location/caps/cleanup/disable behavior and partial-result/retry interpretation to README and the code-intel skill. Preserve the existing 5.7.2 completeness wording where Unit B does not supersede it; disclose cache cleanup as permitted only when no indexed query is active.
6. Run focused suites on Python 3.12 and 3.9, real local clangd controls under the approved proof sandbox where available, production-reversion tests, ruff and doc checks. Prepare one Unit B commit plus base/commit/delta hashes and evidence for plan-control independent review. Do not run release gates or publish from this branch.

## 실행 기록

- Plan-control 추가 계약인 indexed argv `--limit-references=0` 회귀를 추가했다. Fake integration 경로는 progress 누락·coverage 부족·잘못된 최종 응답 때 기존에 검증한 부분 결과를 유지하며 `complete: false`를 반환한다.
- Python 3.12 focused suite, final rerun: `python3 -m pytest -o addopts= -q tests/hooks/test_lsp_query.py tests/hooks/test_lsp_validation.py tests/hooks/test_lsp_index_inputs.py tests/hooks/test_lsp_index_cache.py tests/hooks/test_lsp_index_coverage.py tests/hooks/test_lsp_index_resources.py` — rc 0, 256 passed / 43 subtests (`unit-b/native-proof/py312-focused.*`).
- Python 3.9 stdlib runtime: input/entrypoint compatibility 4, cache 30, coverage 24, resource 27 tests 모두 pass(총 85); `lsp_query`·`lsp_transport` imports와 CLI `--help`도 통과. 전체 `unittest discover -p 'test_lsp_*.py'`는 Python 3.9 환경에 pytest가 없어 pytest 기반 테스트 모듈을 import할 수 없었고, 첫 전체 시도에서 ResourceGuard timing case 하나도 fail했다. 해당 unittest-compatible suites를 각각 재실행해 모두 통과했으며, 이 환경에는 pytest를 설치하지 않았다.
- Python 3.9 final runtime-compatible suites: stdlib unittest 85 tests passed (`unit-b/native-proof/py39-compatible.*`); `lsp_query --help` also passed. The dedicated raw-name Linux branch remains for the later Ubuntu CI gate.
- Real Apple clangd 21 sandbox control: the native-review-final.json report and raw query-final2 files in the local migration evidence outside the repository. Cold rc 0 in 0.606s, 2/2 TU coverage, shard 0→3, exact cross-TU locations; warm rc 0 in 0.417s, 2/2, existing/reused cache, 5s class. Source/CDB SHA-256 were unchanged. `sandbox-exec` allowed writes only under proof and denied fixture workspace writes, network, and reads of auth/browser paths.
- Production reversion, final code: resetting only `lsp_query.py` and `lsp_transport.py` to the Unit A base made the new unlimited-reference argv and progress-token tests fail (rc 1); both files were restored byte-identically. Raw output and per-file hashes are in `unit-b/native-proof/reversion-final.{json,stdout}`.
- A Python 3.9 `unittest discover -p 'test_lsp_*.py'` attempt could not import pytest-based test modules because pytest is absent from that interpreter. One timing-sensitive ResourceGuard test also failed once because its child PID file was observed before it was fully written; the test now waits for a complete PID, and the compatible suite passed on rerun. No dependency was installed.
- ruff, `scripts/check_doc_counts.py`, `scripts/check_doc_status.py` 모두 통과. Full `scripts/verify-done.sh`, CI, directory Validate 및 independent review는 아직 하지 않았다.

## 완료 조건

- `python3 -m pytest -o addopts= -q tests/hooks/test_lsp_query.py tests/hooks/test_lsp_validation.py tests/hooks/test_lsp_index_inputs.py tests/hooks/test_lsp_index_cache.py tests/hooks/test_lsp_index_coverage.py tests/hooks/test_lsp_index_resources.py`
- Python 3.9 compatible runtime modules: `python3.9 -B -m unittest tests.hooks.test_lsp_index_inputs_compat tests.hooks.test_lsp_index_cache tests.hooks.test_lsp_index_coverage tests.hooks.test_lsp_index_resources`
- `ruff check plugins/common/tools tests/hooks/test_lsp_query.py tests/hooks/test_lsp_validation.py`
- Production reversion of Unit B integration must fail its new CLI/transport contract tests; all source files restored byte-identically afterward.
- Approved real clangd controls either pass with raw evidence or report exact skip/unavailable reason; no native failure is reinterpreted as a pass.
- Independent Unit B review ACCEPT on the frozen commit and delta. Full `scripts/verify-done.sh`, Ubuntu CI, directory Validate, version bump, squash integration, tag and push remain later integration/release gates owned by plan-control.

## B-R1 수정 및 재검수 대기

Plan-control rejected 6951385. The following delta implements B-R1; independent ACCEPT remains pending.

- B-R1-1/6: routine protocol/response budgets retain native shards (`index_response_limit` / `index_response_unverified`); work cutoff reports `index_deadline`. Only resource/cache limits or untrusted cleanup discard native data. `failure.json` survives that call and is consumed by the next call. Fallback connections use the shared deadline and retain validated partials on cleanup failure.
- B-R1-2: key input now includes pinned CDB identity/bytes and canonical TU paths; TU inodes are coverage evidence only. Rename-style source replacement preserves the key; CDB replacement invalidates it.
- B-R1-3/4: late context-exit failure always downgrades complete; child TMPDIR/TMP/TEMP use an FD-anchored key-local tmp directory, counted during execution and removed after reap.
- B-R1-7/8: macOS xcrun replacement applies only to the system shim; other selected clangd binaries stay pinned. Parsing aborts at the object-count policy during JSON loading; config discovery checks the shared deadline. Effective compile_flags ancestor chains are checked.
- B-R1-5/9: new focused regressions cover inherited live lock fd, guard deadline identity, both CDB/config rechecks, cleanup downgrade, existing relative compiler rejection, key identity, failure consumption/discard scope and strict coverage growth. Final source mutations are in the local migration evidence (round B-R1, mutations.json); 14/14 produce expected test failures, source bytes restored.
- Python 3.9 scratch venv uses PyPI pytest 8.4.2 because repo pin 9.1.1 requires Python >=3.10 (plan-control approved). Repo pin stays unchanged. Both Python versions execute 286 collected nodes with identical node lists; full focused runtime suites pass. Versions, argv, rc, collected nodes and raw output are in `unit-b/native-proof/r1/{verification.json,py312-*,py39-*}`.
- Unit A production correction, separately disclosed: an initial focused run failed `test_reap_waits_for_clean_exit_before_collecting_leader`. Instrumented baseline serial failure rate was 9/200, four concurrent target suites 3/200. A classification run failed 7/200: 5 concurrent-poll false-live observations and 2 exit-transition RSS-unknown observations. Production now serializes guard poll observers and confirms missing/zombie transition before tolerating one unknown-RSS sample; live unknown RSS still fails closed. The same post-fix workload failed 0/200 serial and 0/200 concurrent. `reap-*.json` preserves every iteration's sampled rows, branch assignments, exceptions and original output. Instrumentation changes timing; these are stress results, not a statistical reliability guarantee.
- Native proof is rerun on the final code: cold/warm references, rename-edit/warm references and independent definition golden. No source or CDB changes by the query process; authored edit is restored by the runner. Raw records are in the local migration evidence for round B-R1.

## B-R2 수정 및 재검수 대기

Plan-control rejected 94cd554 after independently accepting the B-R1 runtime/native/mutation evidence and Unit A race fixes. This delta remains unaccepted until independent re-review.

- ATK-001: actual transport tracks broken streams/timeouts; unhealthy readers skip shutdown. A failed handshake followed by verified kill/reap is trusted cleanup. ResourceGuard exposes its post-reap group-absence evidence separately from an earlier failure reason, and query cleanup preserves shards when this evidence is valid. Real transport plus authored fake server tests cover 3MiB Content-Length, delayed replies, duplicate progress creation and notification overflow; each asserts no shutdown request, retained shard, verified process exit and bounded elapsed time.
- ATK-002/003: persistent key target stays 128MiB. Temporary preambles use a separate proposed sampled target of 512MiB (policy decision, not a hard filesystem quota), with index_transient_limit preserving shards. Live accounting counts both independently; preparation/classification clears stale tmp before starting another native writer. Temp traversal overflow is also transient, not cache_limit. README/SKILL disclose the separate target.
- ATK-004/005: a bounded lexical preflight limits JSON containers/strings/depth before stdlib parsing; stdlib still owns syntax and duplicate-key validation. The semantic key uses canonical CDB path/bytes + canonical TU paths. Neither CDB nor TU inode enters the key; CDB identity remains only in the in-call change check. The same-byte CDB rewrite reuses the key; byte changes invalidate.
- ATK-006/007/008: fallback shares only the deadline, without indexed RSS/sampler policy. Reason retains the original fallback classification and cause records a secondary response/deadline failure. No message claims index persistence when nothing was attempted. Deadline error classification checks the lease deadline.
- ATK-009–012: separate tests discriminate both config discovery deadline checks; actual transport pass_fds removal is mutated; consecutive unknown-RSS exit-transition exemptions are capped at two; invalid/unsafe/symlink failure.json is ignored and safely unlinked without following it, before classification can be blocked by it.
- Evidence in migration unit-b/native-proof/r2: 17 source mutations each fail their targeted test; paired Python3.12/pytest9.1.1 and Python3.9/pytest8.4.2 suites pass 307 nodes with node-list diff0. Native controls include source rename-edit warm and same-byte CDB rewrite warm (one key, full golden). One development test run did not reach the oversized-response condition because the fake interpreter's initialization also had a 250ms timeout; raw output is retained and the harness now gives initialization 3s, reducing to 250ms only after initialized. A surviving first mutation exposed a duplicate-cleanup-path test gap; the final test includes idempotent and failure-after-partial paths and both variants are detected.
- Worktree cleanup remains as reported: accepted Unit A checkout/idle shell removed, branch retained for the squash gate; Unit B and A/B raw evidence, final native cache, authored fixtures/runners and Python3.9 proof venv retained for independent re-execution. No main merge/push, version bump or release gates run here.

## B-R3 수정 및 재검수 대기

Plan-control rejected dd42d62; this revision still needs independent ACCEPT.

- HIGH reproduction on dd42d62 used the actual transport, a real guard with delayed sampling, and an authored server that remains alive two seconds after exit. Main-thread work cutoff sent shutdown and exhausted the cleanup reserve: cleanup_verified=false. The observed run retained the shard because cleanup was already out of time; physical deletion was not observed. Baseline raw result is r3/deadline-dd42d62.*. The same regression now skips the handshake and verifies kill/reap while retaining the shard.
- Indexed cleanup also skips handshakes when guard.reason is already set. The transport snapshots the guard reason after cleanup, and query uses it as the authoritative failure reason so cache_limit/RSS retain their discard policy while index_transient_limit retains shards. Real guard-thread disk_check tests exercise all three reasons against reader EOF.
- Prune clears inactive tmp only after acquiring its key lock; contended/active tmp is left alone. Retained accounting excludes active tmp, which is explicitly disclosed in README. TRANSIENT_BYTES=512MiB was accepted by plan-control; no further numeric tuning here.
- Structural allocation checks use a compiled token scanner with C-level string runs, preserve container/string/depth caps and add bounded comma/literal counts. Escaped string contents do not count as structure; stdlib still validates syntax. Serial 8.3MB/10,000-entry CDB n3 preprocessing benchmark median: dd42d62 0.3848s, current 0.0818s, json.loads 0.0170s. This is only preprocessing overhead, not LSP/token savings. Raw vectors/runner and first slower regex attempt remain in r3.
- Cheap items: reader death outside caught protocol exceptions and verified guard.close OSError have discriminating tests; lease.deadline is deadline in production today (the prior identity-difference test is defensive); numeric arrays and byte-relative string bound are covered; a first reap reporting an unsafe reaped-leader group permanently prevents cleanup certification; fallback close timeout normalizes to index_deadline and closes pipes in finally.
- r3 evidence: both Python runtimes pass 320 collected nodes (3.12 pytest9.1.1: 43 additional subtests), node-list diff0; 11 targeted source mutations all fail. Native cold/warm, source rename-edit warm, identical CDB rewrite warm and definition are complete/golden with one key. Source/CDB bytes are restored. Full release gates and independent delta review remain plan-control's responsibility.

## B-R4 좁은 수정 및 delta 재검수 대기

Scope is exactly the final B-R4 list from plan-control-review-r3.md; independent ACCEPT remains pending.

- Numeric conversion is bounded before int/float construction: parse_int/parse_float reject literals longer than 32 characters. Exact 32-character positive controls and long-run regressions distinguish the cap. On /usr/bin/python3 3.9.6, old unbounded 400k integer conversion took 0.6585s; full current CDB discovery rejected 400k in 0.0043s and 8MiB integer/float in 0.0801/0.0891s. Raw argv/version/timing/rc is in r4/numeric-floor.*; generated 8MiB input is cleaned after the probe.
- Active-key protection has an actual contended flock regression. Inactive tmp deletion failures retain persistent keys and their metadata; only index_deadline propagates. All retained targets remain the accepted values.
- Graceful shutdown request/send and voluntary-exit reaping use work budget/cancellation. Cleanup reserve is used for forced kill/reap. The 50ms failure case checks that the 2s voluntary-exit marker is never reached, and a separate delayed shutdown-response case cannot spend reserve waiting for that reply.
- Deadline test robustness: first 20x4 run failed 2/80 invocations; diagnostic run failed 3/80. All raw records are retained. The test-only watchdog interval=10s was also stretching kill/reap polling to the whole reserve. The fixture now restores .01s cleanup polling before changing the deadline, and widens cleanup end while leaving work budget at expired/50ms. The corrected 20 batches x4 parallel invocations pass 80/80 (160 parameter cases); all160 verify cleanup, all80 50ms cases reach shutdown, no2s voluntary exit occurs. Production default polling was not retuned.
- Cheap items: quoted numeric-array comma path tested; each structural bound names its own error; removed the nonbinding byte-cap min in favor of the existing named string-count cap; guard limits alone override reason and preserve the original as cause; any observed children after leader reap compromise certification, including kill/watch/close paths; fallback wait restores the .05s minimum.
- Final r4 evidence: both Python runtimes 339 collected nodes pass (3.12 includes 43 subtests), collection diff0; 13 targeted mutations fail; native5 controls are complete/golden with one key and restored source/CDB bytes. Ruff/doc gates pass. Unit A squash/no-old-blob and directory/release gates unchanged; no publishing here.

## Unit B ACCEPT 및 통합 조건 후속

Plan-control independently ACCEPTED Unit B at 952cb9d (plan-control-review-r4.md). This is implementation approval; integration/release gates remain pending. The five explicit integration conditions are prepared as a separate follow-up for the final single Unit A+B squash, without changing main or publishing:

1. The 50ms test positively asserts shutdown arrival. Test time freezes only until the server's handshake marker, then live monotonic work time advances for 50ms; this prevents loaded-CI vacuity without simulating transport/kill/reap.
2. A voluntary-exit work cutoff records index_deadline before forced kill/reap; a watchdog-free real-child regression discriminates that branch.
3. ResourceGuard.cleanup_verified is computed from _verified_once and not _cleanup_compromised, so late compromise invalidates prior certification.
4. A leader reaped during a root-exited+children snapshot causes a fresh sample rather than a stale group signal. A real-process raced-snapshot regression and direct D7 late-group marker regression cover both paths.
5. ResourceGuard docstring states cooperative work uses work time; reserve is for forced kill+verified reap.

Evidence under migration unit-b/native-proof/integration-conditions: both runtimes 342 nodes pass (3.12 includes43 subtests), collection diff0; 5 targeted mutations detected; 20x4 parallel target invocations all pass (160 cases, all80 positive handshakes reached); native5 controls complete/golden with one key and source/CDB restored. Source hashes preserve tested bytes for the follow-up commit. Final full verify-done/Ubuntu/directory Validate/no-old-blob and squash checks are still plan-control's integration gates; no release action here.
