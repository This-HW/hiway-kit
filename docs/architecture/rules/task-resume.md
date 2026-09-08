# Task 재생성 규칙

> 이 문서는 중단된 작업을 재개할 때 Task 목록을 재생성하는 알고리즘과 그 이유를 설명합니다.

---

## 1. Task 재생성이 필요한 이유

Claude Code의 Task는 세션이 종료되면 사라집니다. 작업이 도중에 중단되었다가 재개될 때, 이전에 만들었던 Task ID가 더 이상 유효하지 않기 때문에 `progress.md`의 완료/미완료 상태를 기반으로 Task를 새로 생성해야 합니다.

```
세션 종료 전:
  Task #45 (implement-auth) — in_progress
  Task #46 (write-tests)    — pending
  Task #47 (review-code)    — pending, blockedBy: [45, 46]

세션 재시작 후:
  Task #45, #46, #47 모두 사라짐
  → progress.md의 ⏳/⬜ 상태를 보고 재생성 필요
```

---

## 2. 트리거 조건

| 상황                                                  | 행동                                                   |
| ----------------------------------------------------- | ------------------------------------------------------ |
| 사용자가 작업 재개를 명시 ("계속해줘", "이어서 해줘") | Task 재생성 알고리즘 즉시 실행                         |
| 단순 질문/조회                                        | "W-XXX 작업이 진행 중입니다. 재개할까요?" 안내 후 대기 |
| 자동 감지 (progress.md 존재)                          | 자동으로 Task 생성하거나 코드 수정 절대 금지           |

**중요:** `NEVER 자동으로 Task를 생성하거나 코드를 수정한다`

사용자 명시 없이 자동 재개하면 사용자가 의도하지 않은 작업이 진행될 수 있습니다.

---

## 3. Task 재생성 알고리즘 (5단계)

### Step 1: 준비 — 도구 로드 및 중복 생성 방지

```python
# 필요한 Task 도구 확인
ToolSearch("select:TaskCreate,TaskUpdate,TaskList")

# 이미 Task가 있으면 재생성 불필요 (중복 방지)
existing = TaskList()
if existing:
    print("Task가 이미 존재합니다. 재생성을 건너뜁니다.")
    # 바로 Step 5(실행 재개)로 이동
```

**이유:** 세션이 끊겼다가 재연결된 경우 Task가 살아있을 수 있습니다. 중복 생성을 방지합니다.

---

### Step 2: progress.md 읽기 — 완료/미완료 분류

```
progress.md 예시:
  ✅ T-1: 요구사항 분석
  ✅ T-2: 데이터 모델 설계
  ✅ T-3: 인증 API 구현
  ⏳ T-4: 테스트 코드 작성 (blockedBy: T-3)
  ⬜ T-5: 코드 리뷰 (blockedBy: T-3)
  ⬜ T-6: 배포 준비 (blockedBy: T-4, T-5)

분류 결과:
  complete   = {T-1, T-2, T-3}         # ✅ Task ID 집합
  incomplete = [T-4, T-5, T-6]         # ⬜·⏳ Task 목록 (순서 유지)
```

**이유:** 완료된 Task는 재생성하지 않습니다. 이미 완료된 작업을 다시 실행하면 시간 낭비이고 충돌 위험이 있습니다.

---

### Step 3: 미완료 Task를 순서대로 생성 — id_map 추적

```python
id_map = {}  # 구 Task ID → 새 Task ID 매핑

for task in incomplete:  # 순서 유지가 중요
    # blockedBy 의존성 재계산
    # 완료된 Task에 대한 의존성은 이미 충족됨 → 제거
    실제_blockedBy = [
        id_map[dep]                    # 새 Task ID로 변환
        for dep in task.blocked_by
        if dep not in complete         # 완료된 것은 제외
        and dep in id_map              # 재생성된 것만 포함
    ]

    # Task 생성 (표준 형식)
    new_id = TaskCreate(
        subject=f"[W-XXX][Phase] {task.title}",
        metadata={"work_id": "W-XXX", "phase": "planning|development|validation"}
    )

    # 매핑 기록
    id_map[task.id] = new_id

    # blockedBy 설정
    if 실제_blockedBy:
        TaskUpdate(new_id, addBlockedBy=실제_blockedBy)
```

**id_map이 필요한 이유:**

```
T-4의 새 ID = #51
T-5의 새 ID = #52
T-6은 T-4, T-5에 의존 → blockedBy: [51, 52]
id_map 없이는 새 ID를 알 수 없음
```

---

### Step 4: in_progress 상태 복원

```python
# ⏳이었던 Task는 in_progress로 복원
for task in incomplete:
    if task.status == "in_progress":  # ⏳
        TaskUpdate(id_map[task.id], status="in_progress")
```

**이유:** 세션 중단 시점에 진행 중이던 작업이 있으면, 재개 후 해당 Task부터 이어서 시작해야 합니다.

---

### Step 5: 실행 재개 — 의존성 없는 Task부터

```python
# blockedBy가 없는 Task = 지금 바로 실행 가능
ready_tasks = [
    id_map[t.id]
    for t in incomplete
    if not 실제_blockedBy_of(t)
]

# 2개 이상이면 병렬 실행
if len(ready_tasks) >= 2:
    # Agent 동시 dispatch
    for task_id in ready_tasks:
        dispatch_agent(task_id)
else:
    # 단일 실행
    execute(ready_tasks[0])
```

---

## 4. 전체 예시

### 입력: progress.md 상태

```
✅ T-1: 요구사항 분석
✅ T-2: API 설계
✅ T-3: DB 스키마 구현
⏳ T-4: 사용자 서비스 구현 (blockedBy: T-3)
⬜ T-5: 인증 서비스 구현 (blockedBy: T-3)
⬜ T-6: API 통합 테스트 (blockedBy: T-4, T-5)
```

### 처리 과정

```
complete   = {T-1, T-2, T-3}
incomplete = [T-4, T-5, T-6]

T-4: blockedBy [T-3] → T-3은 complete → 실제_blockedBy=[]
     TaskCreate("[W-007][development] 사용자 서비스 구현") → id=#51
     id_map = {T-4: 51}
     T-4가 ⏳이므로 → TaskUpdate(51, status="in_progress")

T-5: blockedBy [T-3] → T-3은 complete → 실제_blockedBy=[]
     TaskCreate("[W-007][development] 인증 서비스 구현") → id=#52
     id_map = {T-4: 51, T-5: 52}

T-6: blockedBy [T-4, T-5] → 둘 다 incomplete → [id_map[T-4], id_map[T-5]] = [51, 52]
     TaskCreate("[W-007][development] API 통합 테스트") → id=#53
     TaskUpdate(53, addBlockedBy=[51, 52])
```

### 실행 결과

```
Task #51 (사용자 서비스 구현) — in_progress, blockedBy: 없음  ← 즉시 실행
Task #52 (인증 서비스 구현)   — pending,     blockedBy: 없음  ← 동시 실행
Task #53 (API 통합 테스트)     — pending,     blockedBy: [51, 52] ← 51, 52 완료 후

실행: #51, #52 Agent 동시 dispatch
```

---

## 5. Task 생성 형식 규칙

```
subject 형식: "[W-XXX][Phase] 제목"
  예시:
    "[W-007][planning] 요구사항 분석"
    "[W-007][development] 인증 API 구현"
    "[W-007][validation] 코드 리뷰"

metadata 형식:
  {
    "work_id": "W-007",
    "phase": "planning" | "development" | "validation"
  }

설계 게이트 대기 태스크 (Work ID 없음):
  {
    "phase": "brainstorming"     ← work_id 없음. ACTIVE WORK 스캔에 안 잡힌다
  }
```

### brainstorming 고아 방지

`{"phase": "brainstorming"}` 태스크는 Work ID가 없어 ACTIVE WORK 스캔에 걸리지 않는다.
STALE TASKS 알림에서 이런 태스크를 보면 **바로 정리 대상으로 단정하지 않는다**:

| 상황                                     | 판단                                        |
| ---------------------------------------- | ------------------------------------------- |
| `docs/specs/`에 대응 최신 스펙이 있음    | 정당한 대기 — "검토 재개 vs 폐기"를 사용자에게 확인 |
| 스펙 없음 / 이미 구현됨                  | 오래된 고아 — 정리 대상으로 보고             |

| 규칙                                  | 설명                            |
| ------------------------------------- | ------------------------------- |
| ALWAYS subject 형식 준수              | 작업 ID와 단계 추적을 위해      |
| ALWAYS metadata 포함                  | 필터링 및 대시보드 표시를 위해  |
| NEVER 완료 Task(✅) 재생성            | 이미 완료된 작업 중복 실행 방지 |
| ALWAYS 완료 Task는 blockedBy에서 제거 | 이미 충족된 의존성 제거         |

---

## 6. CLAUDE_CODE_TASK_LIST_ID 고급 활용

특정 Task 목록 ID를 환경변수로 지정하면 여러 세션에서 같은 Task 목록을 공유할 수 있습니다.

```bash
# 특정 프로젝트 Task 목록 고정
export CLAUDE_CODE_TASK_LIST_ID="list_abc123"

# 이후 TaskCreate, TaskList 모두 이 목록에서 동작
```

**활용 케이스:**

- 팀원 간 Task 공유 (같은 LIST_ID 설정)
- CI/CD에서 자동화된 Task 관리
- 여러 Claude 세션이 동일 작업 목록 참조
