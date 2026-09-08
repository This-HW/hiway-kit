---
work_id: "W-000"
title: "하이브리드 Work-Task 시스템 구현"
status: completed
current_phase: validation
phases_completed: [planning, development, validation]
size: Medium
priority: P0
tags: [work-system, task-system, infrastructure, meta]
created_at: "2026-03-29T00:00:00+09:00"
updated_at: "2026-04-02T04:21:27Z"
completed_at: "2026-04-02T04:21:27Z"
started_at: "2026-04-02T04:21:24Z"
---

# 하이브리드 Work-Task 시스템 구현

> Work ID: W-000
> Status: completed ✅
> 설계 문서: docs/works/idea/W-000-hybrid-work-task-system/design-draft.md

## 요약

Work 파일(영구 저장)과 Claude Code Task 시스템(세션 런타임)을 통합하는
하이브리드 추적 시스템. 설계는 완료, 실제 구현 필요.

## 구현 필요 항목

### 인프라

- [x] `docs/works/` 폴더 구조 확립 (idea / active / completed)
- [x] Work 파일 템플릿 (W-XXX-{slug}.md, progress.md, decisions.md, planning-results.md)
- [x] `scripts/work.sh` — Work 상태 관리 CLI (new/list/show/start/next-phase/complete)

### 스킬 통합

- [x] `plan-task` 스킬 — Work 파일 생성 + Planning Tasks 자동 생성
- [x] `auto-dev` 스킬 — Work 파일 로드 + Development Tasks 생성 (병렬 분해)
- [x] Validation Phase — review + security-scan 병렬 Task 패턴

### 에이전트 통합

- [x] Task 완료 시 Work 파일 업데이트 규칙 (progress.md, decisions.md)
- [x] Phase Gate 강제 (Task blocks/blockedBy)
- [x] Work ID를 Task metadata에 연결하는 규약

### Plugin 완전 통합

- [x] `plugins/common/hooks/hooks.json`에 PreToolUse/PostToolUse 훅 등록
- [x] 훅 커맨드 경로 → `${CLAUDE_PLUGIN_ROOT}/hooks/` 로 변경
- [x] `session-check.py` → rules additionalContext 주입 방식으로 전환 (5개 룰)
- [x] `setup.sh` 슬림화 — 훅 관련 로직 제거 (플러그인이 대신)

## 완료 요약

이 시스템으로 W-001(Claude Code 업데이트 적용)을 첫 번째 실전 Work로 진행 예정.
