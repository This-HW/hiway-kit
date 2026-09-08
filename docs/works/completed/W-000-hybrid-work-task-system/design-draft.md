# 하이브리드 Work-Task 시스템

> Work 파일(영구 저장)과 Claude Code Task 시스템(세션 런타임)의 통합 설계

---

## 핵심 개념

두 시스템은 서로 다른 역할을 담당합니다:

| 시스템                          | 역할                                        | 수명            |
| ------------------------------- | ------------------------------------------- | --------------- |
| **Work 파일** (`docs/works/`)   | **무엇을** 할지 — 요구사항, 결정, 히스토리  | 영구 (Git 저장) |
| **Task 시스템** (TaskCreate 등) | **어떻게** 할지 — 실행 조율, 병렬화, 의존성 | 세션 내         |

```
Work 파일 (Source of Truth)
    ↓ 세션 시작 시 Task 생성
Task 시스템 (Runtime Engine)
    ↓ Task 완료 시 Work 파일 업데이트
Work 파일 (최신 상태 반영)
```

---

## Work 파일 구조 (영구)

```
docs/works/
├── idea/       # 기획 중
├── active/     # 개발 중
└── completed/  # 완료

각 Work 폴더:
W-XXX-{slug}/
├── W-XXX-{slug}.md      # 메인 파일 (frontmatter + 요구사항 + 결과)
├── progress.md           # Phase 진행 상황 (체크리스트)
├── decisions.md          # 의사결정 기록 (DEC-XXX)
├── planning-results.md   # Planning Phase 상세 결과
└── review-results.md     # 다관점 리뷰 결과 (Medium/Large)
```

### Work frontmatter

```yaml
---
work_id: "W-001"
title: "기능명"
status: idea # idea | active | completed
current_phase: planning # idea | planning | development | validation
phases_completed: []
size: Medium # Small | Medium | Large
priority: P1 # P0 | P1 | P2 | P3
tags: []
created_at: "2026-01-30T10:00:00+09:00"
updated_at: "2026-01-30T10:00:00+09:00"
---
```

---

## Task 시스템 역할 (세션 런타임)

Task 시스템은 Work 항목을 **이번 세션에서 어떻게 실행할지** 관리합니다.

### Task metadata 규약

모든 Work 관련 Task에는 다음 metadata를 포함합니다:

```json
{
  "work_id": "W-001",
  "phase": "development",
  "type": "agent_task | validation | review"
}
```

### Task 네이밍 규약

```
[W-001][Planning] 요구사항 명확화
[W-001][Dev] Conditional Hooks 구현
[W-001][Validation/A] 코드 리뷰       ← 병렬 그룹 A
[W-001][Validation/B] 보안 스캔        ← 병렬 그룹 B
[W-001][Validation] 리뷰 결과 통합
```

---

## Phase Gate 패턴 (Task 의존성으로 구현)

Phase Gate는 Task의 `blocks`/`blockedBy` 관계로 강제합니다.

```
[Planning Tasks]
    ↓ blocks
[Development Tasks]
    ↓ blocks
[Validation Tasks (병렬)]
    ↓ blocks
[완료 처리]
```

### 예시: W-001 Medium 규모 Work

```
T-1: [W-001][Planning] 요구사항 명확화
T-2: [W-001][Planning] 구현 계획 수립        blockedBy: T-1
T-3: [W-001][Dev] HIGH 항목 구현             blockedBy: T-2
T-4: [W-001][Dev] MEDIUM 항목 구현          blockedBy: T-2
T-5: [W-001][Validation/A] 코드 리뷰         blockedBy: T-3, T-4
T-6: [W-001][Validation/B] 보안 스캔         blockedBy: T-3, T-4
T-7: [W-001][완료] Work 파일 업데이트        blockedBy: T-5, T-6
```

### Task 생성 코드 패턴

```
세션 시작 시:
1. Work 파일 읽기 → current_phase, phases_completed 확인
2. 현재 Phase에 맞는 Task 세트 생성
3. blocks/blockedBy 의존성 설정
4. 병렬 실행 가능한 Task는 동일 Phase, 별도 owner로 분리
```

---

## 병렬 실행 패턴

Task 시스템의 핵심 가치: **서로 독립적인 작업의 병렬화**

### Validation Phase 병렬화

```
Development 완료
    │
    ├──→ T-5: 코드 리뷰 (owner: review-agent)    ─┐
    ├──→ T-6: 보안 스캔 (owner: security-agent)  ─┤→ T-7: 통합
    └──→ T-?: 성능 분석 (owner: perf-agent)      ─┘
```

### Development Phase 병렬화 (독립 모듈)

```
Planning 완료
    │
    ├──→ T-3: hooks.json 수정 (독립)       ─┐
    ├──→ T-4: agent frontmatter 수정 (독립) ─┤→ T-7: 통합 검증
    └──→ T-5: skill 파일 수정 (독립)        ─┘
```

---

## Work-Task 생명주기

### 1. Work 생성 (idea 단계)

```
사용자 요청
→ Work 파일 생성 (docs/works/idea/W-XXX/)
→ frontmatter: status=idea, current_phase=idea
→ Task는 아직 생성 안 함 (세션 필요시 생성)
```

### 2. Planning 세션 시작

```
/plan-task W-XXX
→ Work 파일 로드
→ Planning Tasks 생성:
   T-1: 요구사항 명확화
   T-2: [블록됨] 구현 계획 수립
→ T-1 완료 → planning-results.md 업데이트 → T-2 unblock
→ T-2 완료 → Work frontmatter phases_completed에 planning 추가
```

### 3. Development 세션 시작

```
/auto-dev W-XXX
→ Work 파일 + planning-results.md 로드
→ Development Tasks 생성 (병렬 가능한 것은 분리)
→ 각 Task 완료 시 progress.md 업데이트
→ 전체 완료 시 Work를 idea/ → active/ 이동
```

### 4. Validation 세션

```
→ Validation Tasks 생성 (리뷰 + 보안 병렬)
→ 결과를 review-results.md에 저장
→ 이슈 없으면 active/ → completed/ 이동
```

---

## Work 파일 업데이트 규칙

Task 완료 시 Work 파일에 반영해야 할 내용:

| Task 완료 시점        | 업데이트 대상                              |
| --------------------- | ------------------------------------------ |
| Planning Task 완료    | `planning-results.md` + `progress.md` 체크 |
| P0 결정 발생          | `decisions.md`에 DEC-XXX 추가              |
| Development Task 완료 | `progress.md` 체크                         |
| Phase 전체 완료       | `frontmatter.phases_completed` 업데이트    |
| Validation 완료       | `review-results.md` + Phase 전환           |

---

## 스킬/에이전트 통합 포인트

### plan-task 스킬

```
1. Work 파일 생성 또는 로드
2. Planning Tasks 생성 (TaskCreate)
3. 의존성 설정 (TaskUpdate addBlockedBy)
4. Planning 에이전트들 순차 실행
5. 결과 → Work 파일 업데이트
6. planning-results.md 저장
```

### auto-dev 스킬

```
1. Work 파일 + planning-results.md 로드
2. 구현 항목을 Tasks로 분해 (병렬 가능한 것 분리)
3. implement-code 에이전트 → 각 Task owner로 할당
4. 완료 시 progress.md 업데이트
```

### review/security-scan 병렬 실행

```
1. Development Tasks 완료 확인
2. T-review + T-security Task 동시 생성 (동일 blockedBy)
3. 두 Task 병렬 실행 (별도 에이전트 세션)
4. 둘 다 완료 → review-results.md 통합 저장
```

---

## 요약

```
영구 저장 (Work 파일)     세션 실행 (Task 시스템)
─────────────────────     ──────────────────────
무엇을 만들어야 하나       지금 무엇을 하고 있나
왜 이 결정을 내렸나        어떤 순서로 실행하나
이전에 무엇을 했나         어떤 것을 병렬로 돌리나
팀 전체에 공유             이번 세션 에이전트 조율
```

Work 파일은 **프로젝트 메모리**, Task 시스템은 **실행 엔진**.
