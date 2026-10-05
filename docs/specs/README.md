---
status: current
as_of: 2026-10-05
---

# docs/specs/ — 이 레포의 설계·작업 스펙

이 레포 자체의 변경을 기획한 문서다(소비자 프로젝트의 계획 규약은 `docs/plans/<날짜>-<slug>/plan.md` —
`plugins/common/skills/plan-task/references/plan-format.md`). 스펙은 이력 보존이 목적이라 지우지 않는다.

**지위의 정본은 각 파일의 frontmatter** 다: `proposal`(미완) · `historical`(완료됐거나 시점 고정 조사 —
본문의 경로·명령은 당시 기준이다) · `superseded`(`superseded_by` 가 대체 문서를 가리킨다). 현재 사실을
알려면 스펙이 아니라 README·`CLAUDE.md`·`docs/conventions/` 를 본다. 아래 표는 색인이다 — 새 스펙을
추가하면 frontmatter 를 달고 한 줄 더한다.

| 파일 | 제목 | status |
| --- | --- | --- |
| [`2026-04-21-superpowers-upgrade-design.md`](2026-04-21-superpowers-upgrade-design.md) | (전임 킷) Upgrade & Official Plugin Registry Design | `historical` |
| [`2026-04-21-superpowers-upgrade-plan.md`](2026-04-21-superpowers-upgrade-plan.md) | (전임 킷) Upgrade Implementation Plan — ✅ COMPLETED 2026-04-22 | `historical` |
| [`2026-06-13-architecture-readme.md`](2026-06-13-architecture-readme.md) | Architecture README 설계 (Spec 4) | `historical` |
| [`2026-06-13-definition-of-done.md`](2026-06-13-definition-of-done.md) | Definition of Done — 완료 게이트 (Spec 6) | `historical` |
| [`2026-06-13-feedback-memory.md`](2026-06-13-feedback-memory.md) | Feedback Memory Loop 설계 (Spec 3) | `historical` |
| [`2026-06-13-loop-engineering.md`](2026-06-13-loop-engineering.md) | Loop Engineering 설계 (Spec 5) | `historical` |
| [`2026-06-13-native-foundation.md`](2026-06-13-native-foundation.md) | Native Foundation 설계 (Spec 1) | `historical` |
| [`2026-06-13-orchestration.md`](2026-06-13-orchestration.md) | Orchestration 설계 (Spec 2) | `historical` |
| [`2026-07-03-durable-executor-discipline.md`](2026-07-03-durable-executor-discipline.md) | Durable Executor Checklist & Machine Gate 설계 (v2 — 적대적 리뷰 반영) | `historical` |
| [`2026-07-07-toolkit-improvement-batch.md`](2026-07-07-toolkit-improvement-batch.md) | Toolkit 개선 배치 — 등재 반영 · Evals · Native Watch · Self-Improve · Portfolio | `historical` |
| [`2026-07-09-mcp-portability-consumer-first.md`](2026-07-09-mcp-portability-consumer-first.md) | MCP 이식성 + 소비자-우선 거버넌스 설계 | `historical` |
| [`2026-08-22-ade-benchmark-absorption.md`](2026-08-22-ade-benchmark-absorption.md) | Spec — ADE 벤치마킹 흡수 배치 (Orca · Paseo · Hermes) | `historical` |
| [`2026-08-26-eval-coverage-and-gates.md`](2026-08-26-eval-coverage-and-gates.md) | Spec — 내부 결함 배치: eval 커버리지·기준선 게이트·학습루프 | `historical` |
| [`2026-08-26-multi-harness-packaging.md`](2026-08-26-multi-harness-packaging.md) | Spec — 다중 하네스 공식 패키지 런칭 (Codex · Antigravity) | `historical` |
| [`2026-08-27-delegation-signal-contract-review.md`](2026-08-27-delegation-signal-contract-review.md) | Spec 초안 — DELEGATION_SIGNAL 계약 실효성 검토 | `superseded` |
| [`2026-08-27-remaining-debt-batch.md`](2026-08-27-remaining-debt-batch.md) | Spec — 잔여 부채 일괄 상환 배치 (v2.16.0) | `historical` |
| [`2026-08-31-eval-git-coverage.md`](2026-08-31-eval-git-coverage.md) | Spec — eval 커버리지 최종 갭: git 저장소 시나리오 프리미티브 | `historical` |
| [`2026-09-04-eval-tier2-coverage-gate.md`](2026-09-04-eval-tier2-coverage-gate.md) | 티어2 커버리지 갭 봉쇄 + `consensus-builder` eval 신설 | `historical` |
| [`2026-09-07-census/README.md`](2026-09-07-census/README.md) | 전수 감사 원본 리포트 — 2026-09-07 | `historical` |
| [`2026-09-07-census/T1-findings.md`](2026-09-07-census/T1-findings.md) | T1 — 규범 축 전수 문서 감사 | `historical` |
| [`2026-09-07-census/T2-findings.md`](2026-09-07-census/T2-findings.md) | T2 — 에이전트 축 전수 문서 감사 | `historical` |
| [`2026-09-07-census/T3-findings.md`](2026-09-07-census/T3-findings.md) | T3 — 스킬 축 전수 문서 감사 | `historical` |
| [`2026-09-07-census/T4-findings.md`](2026-09-07-census/T4-findings.md) | T4 — eval 자산 축 전수 문서 감사 | `historical` |
| [`2026-09-07-census/T5-findings.md`](2026-09-07-census/T5-findings.md) | T5 — 배포·프로젝트 문서 축 감사 결과 | `historical` |
| [`2026-09-07-handoff/00-REVIEW.md`](2026-09-07-handoff/00-REVIEW.md) | 00 — 적대적 검수: `2026-09-07-hiway-program-design.md` (D-1~D-33) | `historical` |
| [`2026-09-07-handoff/02-stages.md`](2026-09-07-handoff/02-stages.md) | 02 — Stage 분해 (층 3): 구현 LLM 지시서 | `historical` |
| [`2026-09-07-handoff/03-gate-spec.md`](2026-09-07-handoff/03-gate-spec.md) | 03 — 게이트 규격 (층 4): 수용 테스트 32개 → 실행 가능한 명령 | `historical` |
| [`2026-09-07-handoff/04-handoff.md`](2026-09-07-handoff/04-handoff.md) | 04 — HANDOFF: 구현 LLM 진입점 | `historical` |
| [`2026-09-07-handoff/05-coverage.md`](2026-09-07-handoff/05-coverage.md) | 05 — 추적 매트릭스: 감사 발견 → Stage 항목 (미배정 0건 증명) | `historical` |
| [`2026-09-07-handoff/README.md`](2026-09-07-handoff/README.md) | 실행 인계 문서 세트 — 2026-09-07 | `historical` |
| [`2026-09-07-hiway-program-design.md`](2026-09-07-hiway-program-design.md) | 하이웨이 프로그램 설계 — 하네스 중립 전환 | `historical` |
| [`2026-09-07-rename-probe.md`](2026-09-07-rename-probe.md) | 마켓플레이스 개명 이행 프로브 (실측) — 2026-09-07 | `historical` |
| [`2026-09-13-audit-hardening.md`](2026-09-13-audit-hardening.md) | Audit hardening | `historical` |
| [`2026-09-14-neutral-coordination-lifecycle.md`](2026-09-14-neutral-coordination-lifecycle.md) | 하네스 중립 협업·자원 생명주기 정비 | `historical` |
| [`2026-09-25-prompt-audit/brief-T1-rules-hook.md`](2026-09-25-prompt-audit/brief-T1-rules-hook.md) | 브리프 T1 — rules-hook | `historical` |
| [`2026-09-25-prompt-audit/brief-T2-agents.md`](2026-09-25-prompt-audit/brief-T2-agents.md) | 브리프 T2 — agents | `historical` |
| [`2026-09-25-prompt-audit/brief-T3-skills-evals.md`](2026-09-25-prompt-audit/brief-T3-skills-evals.md) | 브리프 T3 — skills-evals | `historical` |
| [`2026-09-25-prompt-audit/decisions.md`](2026-09-25-prompt-audit/decisions.md) | Decisions: prompt-audit 적용 — 정의 파일 cruft 제거 | `historical` |
| [`2026-09-25-prompt-audit/planning-results.md`](2026-09-25-prompt-audit/planning-results.md) | Planning 결과: prompt-audit 적용 — 정의 파일 cruft 제거 | `historical` |
| [`2026-09-25-prompt-audit/prompt-audit-report.md`](2026-09-25-prompt-audit/prompt-audit-report.md) | Prompt Audit — hiway-kit (2026-09-24) | `historical` |
| [`2026-09-27-model-provenance/README.md`](2026-09-27-model-provenance/README.md) | 실행 모델 기록 + Codex 규범 도달성 (2026-09-27) | `historical` |
| [`2026-09-27-model-provenance/brief-C-codex-parity.md`](2026-09-27-model-provenance/brief-C-codex-parity.md) | 브리프 C — codex-parity | `historical` |
| [`2026-09-27-model-provenance/brief-M1-provenance-docs.md`](2026-09-27-model-provenance/brief-M1-provenance-docs.md) | 브리프 M1 — provenance-docs | `historical` |
| [`2026-09-27-model-provenance/brief-M2-eval-model-axis.md`](2026-09-27-model-provenance/brief-M2-eval-model-axis.md) | 브리프 M2 — eval-model-axis | `historical` |
| [`2026-09-27-model-provenance/brief-R1-evals.md`](2026-09-27-model-provenance/brief-R1-evals.md) | 브리프 R1 — evals 리뷰 반영 | `historical` |
| [`2026-09-27-model-provenance/brief-R2-skills-rules-hooks.md`](2026-09-27-model-provenance/brief-R2-skills-rules-hooks.md) | 브리프 R2 — 스킬 frontmatter·규범·훅 리뷰 반영 | `historical` |
| [`2026-09-27-model-provenance/brief-R3-docs.md`](2026-09-27-model-provenance/brief-R3-docs.md) | 브리프 R3 — 운송 문서·README·checklist 리뷰 반영 | `historical` |
| [`2026-09-27-model-provenance/review-fix.md`](2026-09-27-model-provenance/review-fix.md) | 리뷰 반영 — 공통 전제와 트랙 (2026-09-27) | `historical` |
| [`2026-09-28-plans-replace-works/README.md`](2026-09-28-plans-replace-works/README.md) | Work 시스템을 걷어내고 계획 파일 규약으로 교체 (+ Aside 웹 사용 안내) | `historical` |
| [`2026-09-28-plans-replace-works/brief-T1-hooks-gates.md`](2026-09-28-plans-replace-works/brief-T1-hooks-gates.md) | 브리프 T1 — hooks-gates | `historical` |
| [`2026-09-28-plans-replace-works/brief-T2-skills.md`](2026-09-28-plans-replace-works/brief-T2-skills.md) | 브리프 T2 — skills | `historical` |
| [`2026-09-28-plans-replace-works/brief-T3-rules-docs.md`](2026-09-28-plans-replace-works/brief-T3-rules-docs.md) | 브리프 T3 — rules-docs | `historical` |
| [`2026-09-28-v5-slimming/spec.md`](2026-09-28-v5-slimming/spec.md) | v5.0.0 — 필요 없거나 성능을 깎는 것을 걷어낸다 | `historical` |
| [`2026-09-30-boundary-enforcement/spec.md`](2026-09-30-boundary-enforcement/spec.md) | 아키텍처 경계를 문서가 아니라 프로젝트 도구로 강제한다 | `historical` |
| [`2026-09-30-tools-dir/spec.md`](2026-09-30-tools-dir/spec.md) | v5.2.0 — 스킬이 부르는 도구를 `hooks/` 에서 `tools/` 로 분리 | `historical` |
| [`2026-10-02-product-site/spec.md`](2026-10-02-product-site/spec.md) | hiway-kit 제품 사이트 설계 | `historical` |
| [`2026-10-05-audit-remediation/audit/A-harness.md`](2026-10-05-audit-remediation/audit/A-harness.md) | 감사 A — 하네스 연계(Claude · Codex · Antigravity · Gemini) | `historical` |
| [`2026-10-05-audit-remediation/audit/B-docs.md`](2026-10-05-audit-remediation/audit/B-docs.md) | 감사 B — 설계·기획·규약 문서의 싱크와 로직 | `historical` |
| [`2026-10-05-audit-remediation/audit/C-research.md`](2026-10-05-audit-remediation/audit/C-research.md) | 감사 C — 외부 동향 조사: 킷에 접목할 것 | `historical` |
| [`2026-10-05-audit-remediation/audit/D-coldread.md`](2026-10-05-audit-remediation/audit/D-coldread.md) | 감사 D — 콜드 리딩 보고서 | `historical` |
| [`2026-10-05-audit-remediation/changelog-W1.md`](2026-10-05-audit-remediation/changelog-W1.md) | CHANGELOG 조각 — W1 docs (5.4.0 조립용) | `proposal` |
| [`2026-10-05-audit-remediation/report-W1.md`](2026-10-05-audit-remediation/report-W1.md) | W1 docs — 완료 보고 | `historical` |
| [`2026-10-05-audit-remediation/spec.md`](2026-10-05-audit-remediation/spec.md) | 전수 감사 후속 (v5.4.0) | `proposal` |
