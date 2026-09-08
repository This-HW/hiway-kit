---
tier: reference
portable: false
indexLine: 에이전트 선택·모델 정책은 rules/agent-system.md 를 읽어라
---

# Agent System Rules

Agents are auto-discovered from the plugin directory — check the available
subagent_type list before calling Task (there is no manifest to consult).
NEVER use general-purpose subagent when a specialized agent exists.
ALWAYS specify subagent_type explicitly — no general-purpose fallback.

## Model Selection

- Opus: strategy/analysis/review (clarify-requirements, review-code)
- Sonnet: code implementation/fixes (implement-code, fix-bugs, write-tests)
- Haiku: exploration/verification/simple tasks (explore-codebase, verify-code, verify-integration)

## general-purpose Allowed Only When

- No specialized agent exists for the task
- Task spans multiple domains simultaneously

## Adversarial Parallel Verification

여러 관점의 적대적 검증이 필요하면 general-purpose 복제로 fan-out하지 말고 **이종 전용
에이전트로 fan-out**한다: `review-code`(적대 리뷰) + `devils-advocate`(실패 시나리오) +
`verify-integration`(연동 검증). 동일 에이전트 다중 복제는 관점 다양성(편향 방지)을 잃는다.
단, 다중도메인·외부지식이 필요한 자유 조사는 위 general-purpose 예외를 유지한다.

## isolation: worktree

ALWAYS set `isolation: worktree` for file-modifying agents: implement-code, fix-bugs, write-tests, write-api-tests, implement-api, generate-boilerplate, sync-docs, optimize-logic.
NEVER set `isolation: worktree` on read-only agents: explore-codebase, review-code, plan-implementation.
Merge-back protocol: see parallel-worktree.md (verify-then-exit, sequential merge, conflict → git-workflow).

## disallowedTools Policy

- Meta agents (facilitator, synthesizer, etc. — 6 total): disallowedTools: [Bash]
- Regular agents (implement-code, fix-bugs, etc.): disallowedTools: [Task]
- Skills: no restriction (main Claude runs them via Task)

## Phase Gate

ALWAYS complete each phase before proceeding to the next.

Phase 1 → Phase 2 (Planning → Dev):

- P0 ambiguity = 0, business rules defined, data model defined, user flows clear

Phase 2 → Phase 3 (Dev → Validation):

- Build passes, core logic tests ≥80%, lint/type checks pass

Phase 3 → Complete (Validation → Done):

- review-code Must Fix = 0, Critical security issues = 0, integration tests pass
