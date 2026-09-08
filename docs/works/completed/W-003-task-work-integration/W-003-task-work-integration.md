---
work_id: "W-003"
title: "Task-Work 통합 고도화"
status: completed
current_phase: development
phases_completed: [planning, development, validation]
size: Medium
priority: P1
tags: [task-system, work-system, session-hook, integration]
created_at: "2026-04-05T00:00:00Z"
updated_at: "2026-04-05T16:27:34Z"
completed_at: "2026-04-05T16:27:34Z"
---

# Task-Work 통합 고도화

> Work ID: W-003
> Status: idea → planning
> Size: Medium

---

## 요구사항

Claude Code의 공식 Task 시스템(TaskCreate/TaskUpdate/blockedBy)과 기존 Work 파일 시스템을 완전히 통합한다.

### 핵심 목표

**A. Claude가 Task를 실제로 생성하고 추적**

- plan-task, auto-dev 스킬에 TaskCreate 하드게이트 추가
- Task 완료 시 Work 파일(progress.md) 의무 업데이트
- blockedBy 의존성 그래프 실제 적용

**B. 병렬 실행 최대화**

- 독립 Task는 Agent 동시 dispatch
- Validation Phase: review + security-scan 병렬
- Dev Phase: 독립 모듈 병렬 구현

**C. 세션 간 맥락 자동 복원**

- SessionStart hook으로 active Work 상태 자동 출력
- 새 세션/resume 시 Task 목록 자동 재생성
- Work 파일 기반 Task 재구성

### 추가 발견 사항 (브레인스토밍 중)

- progress.md 구조가 Task 재생성에 부적합 (phase 단위, Task 단위 아님)
- Task 최초 생성 시 소스코드 탐색 필요 (이미 구현된 항목 감지)
- Resume 시 Work 파일 우선, 불일치 의심 시 코드 확인

---

## Planning 결과

[Phase 완료 후 여기에 결과 추가]
