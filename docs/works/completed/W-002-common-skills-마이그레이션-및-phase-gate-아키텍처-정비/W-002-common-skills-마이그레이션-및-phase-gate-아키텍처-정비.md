---
work_id: "W-002"
title: "Common Skills 마이그레이션 및 Phase Gate 아키텍처 정비"
status: completed
current_phase: validation
phases_completed: [planning, development, validation]
size: "large"
priority: P1
tags: ["migration", "skills", "architecture", "phase-gate"]
created_at: "2026-04-05T06:47:55Z"
updated_at: "2026-04-05T07:18:24Z"
started_at: "2026-04-05T06:53:49Z"
completed_at: "2026-04-05T07:18:24Z"
---

# Common Skills 마이그레이션 및 Phase Gate 아키텍처 정비

> Work ID: W-002
> Status: active / Planning

## 요약

`claude_setting`에서 `claude-code-kit`으로 플러그인을 분리할 때 누락된 10개 common 스킬을 마이그레이션하고,
최신 Claude Code 기능을 반영하여 업그레이드한다.
또한 phase-gates를 스킬이 아닌 아키텍처 문서 + Stop hook으로 전환하여 개발 플로우 품질 게이트를 강화한다.

## 요구사항

### 기능 요구사항

1. 누락된 10개 common skill 마이그레이션 (review, multi-perspective-review, doc-coauthoring, debug, test, agent-creator, skill-creator, mcp-builder, agent-teams, web-research 구조 이동)
2. 각 스킬 최신 Claude Code 기능으로 업그레이드 (effort, argument-hint, Stop hook 연동 등)
3. phase-gates를 Stop hook(prompt type)으로 대체 — 명시적 호출 없이 자동 품질 검증
4. `docs/architecture/phase-gate-pattern.md` 문서 추가
5. `agent-system.md` 규칙 Phase Gate 섹션 보강
6. multi-perspective-review references/ 파일 4개 마이그레이션
7. README.md, CLAUDE.md 스킬 카운트 업데이트

### 비기능 요구사항

- claude_setting 원본 기능 100% 보존
- 각 스킬 독립적으로 동작 가능
- 최신 Claude Code v2.1.89 기준 frontmatter 필드 준수

## 다음 단계

구현 계획: `planning-results.md` 참조
