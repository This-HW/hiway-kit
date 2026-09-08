# Work 시스템 통합 가이드

> `plan-task` 스킬의 Work 시스템 자동화 상세 가이드. `plan-task/SKILL.md`가 쓰는
> **Step 0~4** 모델을 그대로 따른다 — 이 문서는 그 모델의 산출물(파일 구조·
> frontmatter·progress.md 포맷)을 상세히 보여준다.

---

## 개요

`plan-task`는 Work 시스템과 완전히 통합되어 있습니다:

- ✅ Work ID 자동 생성 (W-XXX)
- ✅ 폴더 구조 자동 생성
- ✅ Frontmatter 자동 작성
- ✅ progress.md 자동 초기화/업데이트
- ✅ decisions.md P0 결정 자동 기록

---

## Step 0: Work ID 확보 시

### 1. Work ID 생성

```bash
# 최신 Work ID 확인
ls -1 docs/works/idea/ | grep -oE 'W-[0-9]+' | sort -V | tail -1
# → W-042

# 다음 ID: W-043
```

### 2. 폴더 구조 생성

```
docs/works/idea/
└── W-043-user-authentication/    # W-{ID}-{slug}
    ├── W-043-user-authentication.md    # 메인 Work 파일
    ├── progress.md                      # 진행 상황
    ├── decisions.md                     # 의사결정 기록
    └── planning-results.md              # Planning 상세 결과 (Step 2~3)
```

> `review-results.md`는 Planning 산출물이 아니다 — `auto-dev`의 Validation
> 단계(T-merge)에서 review-code/security-scan 결과를 통합 기록하며 처음 생긴다.
> Work 폴더가 `docs/works/active/`로 옮겨간 뒤 만들어지는 파일이므로 여기 목록에
> 두지 않는다. 아래 "auto-dev와의 접점" 참고.

### 3. Work 파일 Frontmatter

```yaml
---
work_id: "W-043"
title: "사용자 인증 시스템 추가"
status: idea
current_phase: planning
phases_completed: []
size: [Small/Medium/Large]
priority: [P0/P1/P2/P3]
tags: [authentication, security, user-management]
created_at: "2026-01-30T10:30:00+09:00"
updated_at: "2026-01-30T10:30:00+09:00"
---

# 사용자 인증 시스템 추가

> Work ID: W-043
> Status: idea → planning
> Size: [판단 결과]

---

## 요구사항

[사용자 요청 내용]

---

## Planning 결과

[Step 완료 후 여기에 결과 추가]
```

### 4. progress.md 초기화

Task Map 포맷을 사용한다. Step 체크리스트 대신 Task 단위로 추적하여 세션 재시작 시
Task 재생성의 소스로 활용한다.

```markdown
# Progress: 사용자 인증 시스템 추가

> Work ID: W-043
> Last Updated: 2026-01-30T10:30:00+09:00

---

## Task Map

### Planning

| Task ID | 제목            | 설명                          | 상태 | blockedBy |
| ------- | --------------- | ----------------------------- | ---- | --------- |
| T-1     | 요구사항 명확화 | clarify-requirements 에이전트 | ⬜   | -         |
| T-2     | 구현 계획 수립  | plan-implementation 에이전트  | ⬜   | T-1       |

### Development

| Task ID                               | 제목 | 설명 | 상태 | blockedBy |
| ------------------------------------- | ---- | ---- | ---- | --------- |
| (plan-task 완료 후 auto-dev에서 채움) |      |      |      |           |

### Validation

| Task ID | 제목      | 설명                   | 상태 | blockedBy  |
| ------- | --------- | ---------------------- | ---- | ---------- |
| T-V1    | 코드 리뷰 | review-code 에이전트   | ⬜   | (Dev 전체) |
| T-V2    | 보안 스캔 | security-scan 에이전트 | ⬜   | (Dev 전체) |
| T-V3    | 결과 통합 | 리뷰+보안 결과 통합    | ⬜   | T-V1, T-V2 |

## Task 업데이트 로그

- 2026-01-30T10:30:00Z: W-043 시작
```

**Task 상태 기호**

| 기호 | 의미    | TaskCreate 상태 |
| ---- | ------- | --------------- |
| ✅   | 완료    | completed       |
| ⏳   | 진행 중 | in_progress     |
| ⬜   | 대기    | pending         |

**Task 완료 시 의무 업데이트:**

1. Task Map 해당 행 상태를 ✅로 수정
2. Task 업데이트 로그에 완료 시각 기록
3. Work frontmatter `updated_at` 갱신

### 5. decisions.md 초기화

```markdown
# Decisions: 사용자 인증 시스템 추가

> Work ID: W-043
> Last Updated: 2026-01-30T10:30:00+09:00

---

## 의사결정 기록

### DEC-001: 규모 판단

- **날짜**: 2026-01-30
- **결정**: [Small/Medium/Large]
- **근거**: [Step 2 판단 이유]
- **영향**: Planning 경로 결정
```

### 6. planning-results.md 초기화

`plan-task/SKILL.md`의 Step 2(요구사항 명확화)·Step 3(구현 계획 수립) 결과를 담는다.
규모가 Medium/Large면 Step 3 안에서 사용자 여정 설계·비즈니스 로직 정의가 추가된다
(`rules/planning-protocol.md` 기준).

```markdown
# Planning 상세 결과

> Work ID: W-043
> Last Updated: 2026-01-30T10:30:00+09:00

---

## 규모 판단

- **크기**: [Small/Medium/Large]
- **판단 근거**: [...]

---

## 요구사항 명확화 (Step 2)

[clarify-requirements 에이전트 전체 결과]

---

## 구현 계획 (Step 3)

[plan-implementation 에이전트 전체 결과 — Medium+는 사용자 여정 설계 포함,
Large+는 비즈니스 로직 정의 포함]
```

---

## 기존 Work 계획 시

### 1. Work 파일 읽기

```bash
# Work 위치 파악
docs/works/idea/W-043-user-authentication/W-043-user-authentication.md
```

### 2. 현재 상태 확인

```yaml
# Frontmatter 확인
status: idea # idea 상태여야 함
current_phase: planning # planning이어야 함
```

### 3. 진행 상황 확인

```bash
# progress.md 읽기
cat docs/works/idea/W-043-user-authentication/progress.md

# 체크포인트 확인
- 어디까지 진행되었는가?
- 어느 Step에서 중단되었는가?
- 중단된 지점부터 재개
```

---

## Planning 진행 중 업데이트 (Step 2~3)

### Step 완료 후 업데이트

**1. progress.md 업데이트**

```markdown
### Planning

| Task ID | 제목            | 설명                          | 상태 | blockedBy |
| ------- | --------------- | ----------------------------- | ---- | --------- |
| T-1     | 요구사항 명확화 | clarify-requirements 에이전트 | ✅   | -         |
| T-2     | 구현 계획 수립  | plan-implementation 에이전트  | ⏳   | T-1       |

---

## 체크포인트

| 날짜       | Step     | 체크포인트      | 상태 |
| ---------- | -------- | --------------- | ---- |
| 2026-01-30 | Step 2   | 요구사항 명확화 | ✅   |
```

**2. decisions.md 업데이트**

P0 결정 사항 기록:

```markdown
### DEC-002: 인증 방식

- **날짜**: 2026-01-30
- **질문**: JWT vs Session 기반 인증?
- **결정**: JWT 기반 인증
- **근거**: 마이크로서비스 아키텍처에 적합
- **영향**: 토큰 관리, 리프레시 로직 필요
```

**3. Work 파일에 결과 추가**

```markdown
## Planning 결과

### 요구사항 명확화 (Step 2)

[Step 2 결과 전체 내용]

### 구현 계획 (Step 3)

[Step 3 결과 전체 내용]
```

---

## Planning 완료 시 (Step 4)

### 1. Frontmatter 업데이트

```yaml
---
work_id: "W-043"
title: "사용자 인증 시스템 추가"
status: idea
current_phase: planning # 유지
phases_completed: [planning] # ← 추가
size: Large
priority: P0
tags: [authentication, security, user-management]
created_at: "2026-01-30T10:30:00+09:00"
updated_at: "2026-01-30T14:20:00+09:00" # ← 갱신
---
```

### 2. progress.md 업데이트

```markdown
### Planning

| Task ID | 제목            | 설명                          | 상태 | blockedBy |
| ------- | --------------- | ----------------------------- | ---- | --------- |
| T-1     | 요구사항 명확화 | clarify-requirements 에이전트 | ✅   | -         |
| T-2     | 구현 계획 수립  | plan-implementation 에이전트  | ✅   | T-1       |

### Development

- [ ] ⏳ 준비됨 (auto-dev 전환 대기)
```

### 3. Work 파일에 최종 결과 저장

```markdown
## Planning 결과

### 규모 판단

- 규모: Large
- 근거: 4개 모듈 영향, 새 데이터 구조, 핵심 보안 규칙

### 요구사항 명확화

[Step 2 전체 결과]

### 구현 계획

[Step 3 전체 결과]
```

### 4. 상태 전환 안내 — `plan-task/SKILL.md` Step 4 [건너뛰기 금지]

Step 4는 `TaskList`로 이 Work의 `[Planning]`/`[Brainstorm]` Task 중 완료됐는데
마킹만 안 된 것을 정리한 뒤(`rules/definition-of-done.md#task-마감-규율`), 곧바로
`auto-dev`를 invoke한다(사용자가 나중을 원하면 아래 명령만 안내):

```bash
/auto-dev W-043        # 개발 파이프라인 시작
./scripts/work.sh next-phase W-043  # Phase만 전환
```

---

## auto-dev와의 접점 — Planning이 끝난 뒤에 일어나는 일

`plan-task`는 여기서 끝난다. 아래는 이 스킬의 산출물이 **다음에** 어떻게 쓰이는지
참고용으로만 적는다 — `auto-dev`가 소유하는 절차다.

- `auto-dev`는 `planning-results.md` 존재를 전제로 시작한다(없으면 `/plan-task`를
  먼저 실행하라고 안내하고 중단한다).
- Work 폴더는 `docs/works/idea/` → `docs/works/active/`로 이동한다.
- `review-results.md`는 **Validation 단계**(T-merge)에서 review-code·security-scan
  결과를 통합 기록하며 처음 생긴다. Planning 중에는 존재하지 않는다.

---

## Fallback: Work 시스템 없는 경우

`docs/works/` 폴더가 없으면 Work 파일 없이 Planning만 진행한다(`plan-task/SKILL.md`
Fallback 절 참고):

1. 요구사항 명확화 (P0 질문 포함)
2. 규모 판단
3. 구현 계획 수립
4. 결과를 대화창에 출력

---

## 파일 위치 규칙

```
docs/works/
├── idea/                    # Planning 중 (Step 0~4)
│   └── W-XXX-{slug}/
│       ├── W-XXX-{slug}.md      # 메인 파일
│       ├── progress.md          # 진행 상황
│       ├── decisions.md         # 의사결정
│       └── planning-results.md  # Planning 상세 결과 (Step 2~3)
│
├── active/                  # Development·Validation 중 (auto-dev)
│   └── W-XXX-{slug}/
│       └── review-results.md    # Validation 결과 (auto-dev T-merge에서 생성)
│
└── completed/               # 완료
    └── W-XXX-{slug}/
```

**Phase 전환 시 폴더 이동:**

```bash
# Planning 완료 → Development 시작
mv docs/works/idea/W-043-user-authentication \
   docs/works/active/
```

---

## 관련 도구

| 도구              | 용도                      |
| ----------------- | ------------------------- |
| `scripts/work.sh` | Work 상태 관리            |
| `/plan-task`      | Planning 자동화 (이 문서가 상세를 보여주는 스킬) |
| `/auto-dev`       | Development·Validation 자동화 |

---

## 참고

- 전체 Work 시스템: `docs/works/README.md`
- Planning Step 모델: `plugins/common/skills/plan-task/SKILL.md`
- Development·Validation 파이프라인: `plugins/common/skills/auto-dev/SKILL.md`
- Phase Gate 패턴(Planning→Dev→Validation 게이트 개념): `docs/architecture/phase-gate-pattern.md`
