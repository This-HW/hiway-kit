---
tier: conditional
activates: 기존 task 재개 신호 (active Work 존재)
portable: false
---

# Task Resume Rules

## 트리거 조건

이 파일이 주입되었다 = Active Work가 존재한다.

- 사용자가 작업 재개를 명시하면 → Task 재생성 알고리즘 즉시 실행
- 단순 질문/조회이면 → "W-XXX 작업이 진행 중입니다. 재개할까요?" 안내 후 대기
- NEVER 자동으로 Task를 생성하거나 코드를 수정한다

## Task 재생성 알고리즘

**Step 1: 준비**

```
ToolSearch("select:TaskCreate,TaskUpdate,TaskList")
TaskList → 이미 Task 있으면 재생성 스킵
```

**Step 2: progress.md 읽기**

```
complete   = ✅ Task ID 집합
incomplete = ⬜·⏳ Task 목록 (순서 유지)
```

**Step 3: incomplete Task를 순서대로 생성**

```
id_map = {}

for task in incomplete:
  실제_blockedBy = [
    id_map[dep]
    for dep in task.blocked_by
    if dep not in complete and dep in id_map
  ]
  new_id = TaskCreate(
    subject=f"[W-XXX][Phase] {task.title}",
    metadata={"work_id": "W-XXX", "phase": "planning|development|validation"}
  )
  id_map[task.id] = new_id
  if 실제_blockedBy:
    TaskUpdate(new_id, addBlockedBy=실제_blockedBy)
```

**Step 4: in_progress 복원**

```
⏳이었던 Task → TaskUpdate(new_id, status="in_progress")
```

**Step 5: 실행 재개**

```
blockedBy 없는 Task부터 실행
2개 이상 → Agent 동시 dispatch
```

## Task 생성 규칙

- ALWAYS subject 형식: `[W-XXX][Phase] 제목`
- ALWAYS metadata: `{"work_id": "W-XXX", "phase": "planning|development|validation"}`
- NEVER 완료된 Task(✅) 재생성
- ALWAYS 완료 Task는 blockedBy에서 제거

## 예시

```
T-1✅, T-2✅, T-3✅ (완료)
T-4⏳ blockedBy T-3 → blockedBy=[] → id=51
T-5⬜ blockedBy T-3 → blockedBy=[] → id=52
T-6⬜ blockedBy T-4,T-5 → blockedBy=[51,52] → id=53
T-4⏳ → TaskUpdate(51, in_progress)
실행: 51, 52 동시 dispatch
```

## 설계 게이트 대기 태스크 (brainstorming 고아 방지)

`{"phase": "brainstorming"}` 태스크는 Work ID가 없어 ACTIVE WORK 스캔에 안 잡힌다.
STALE TASKS 알림에서 이런 태스크를 보면: 정당한 대기(스펙 검토 중)일 수 있다 —
`docs/specs/`의 최신 스펙 존재 여부로 판단하고, 스펙이 있으면 "검토 재개 vs 폐기"를
사용자에게 확인한다. 오래된 고아(스펙 없음/이미 구현됨)는 정리 대상으로 보고한다.
