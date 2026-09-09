# 에이전트 시스템 아키텍처

> 이 문서는 이 킷의 에이전트 시스템 설계 원칙과 실전 운용 방법을 설명합니다.

---

## 1. 3-Tier 아키텍처

에이전트는 프로젝트 범용성에 따라 3개 계층으로 구분됩니다.

```
┌──────────────────────────────────────────────────────────┐
│  Tier 1: plugins/common/        (모든 프로젝트에 적용)   │
│  ├─ 33 agents  (planning, dev, meta, backend ...)        │
│  ├─ 16 skills  (plan-task, auto-dev, review ...)         │
│  ├─ 13 rules   (agent-system, code-quality ...)          │
│  └─ hooks      (protect-sensitive, auto-format)          │
├──────────────────────────────────────────────────────────┤
│  Tier 2: plugins/{domain}/      (도메인별 특화)          │
│  ├─ frontend/  (4 agents, 1 skill)                       │
│  ├─ infra/     (7 agents, 1 skill)                       │
│  ├─ ops/       (14 agents, 5 skills)                     │
│  ├─ data/      (4 agents, 3 skills)                      │
│  └─ integration/ (4 agents)                              │
├──────────────────────────────────────────────────────────┤
│  Tier 3: project-local/         (프로젝트 전용)          │
│  └─ 사용자가 직접 추가하는 프로젝트 특화 에이전트        │
└──────────────────────────────────────────────────────────┘
```

**왜 3-Tier인가?**

- Tier 1에만 모든 에이전트를 넣으면 도메인 무관한 에이전트가 오염됨
- 도메인별로 분리하면 마켓플레이스에서 선택적 설치 가능
- 프로젝트 로컬 Tier는 회사 내부 규칙·도구 등을 커스터마이즈 할 공간

---

## 2. 모델 선택 기준

모델별로 비용과 성능이 다르기 때문에, 작업 특성에 맞게 선택해야 합니다.

| 모델       | 적합한 작업           | 대표 에이전트                                     | 선택 이유                               |
| ---------- | --------------------- | ------------------------------------------------- | --------------------------------------- |
| **Opus**   | 전략, 분석, 리뷰      | `clarify-requirements`, `review-code`, `diagnose` | 복잡한 추론, 뉘앙스 이해가 필요한 작업  |
| **Sonnet** | 코드 구현, 버그 수정  | `implement-code`, `fix-bugs`, `write-tests`       | 속도와 품질의 균형, 코드 생성에 최적화  |
| **Haiku**  | 탐색, 검증, 단순 확인 | `explore-codebase`, `verify-code`, `monitor`      | 빠른 응답, 단순 조회·확인 작업에 효율적 |

**잘못된 모델 선택의 결과:**

```
# 잘못된 예: 단순 탐색에 Opus 사용
clarify-requirements로 코드베이스 탐색 → 비용 3-5배 낭비, 응답 느림

# 올바른 예: 탐색은 Haiku, 분석은 Opus
explore-codebase(Haiku) → 결과를 clarify-requirements(Opus)에 전달
```

---

## 3. 에이전트 선택

에이전트 선택 키워드 매핑 표는 제거됐다(D-18) — 하네스가 시스템 프롬프트에 에이전트
목록과 `MUST USE when:` 트리거를 이미 제공하므로, 정본이 이를 다시 나열하는 것은
네이티브 재기술이다. 필요한 것은 아래 두 원칙뿐이다.

**일반 에이전트(general-purpose) 사용 허용 조건:**

- 특화 에이전트가 존재하지 않는 작업
- 여러 도메인에 동시에 걸쳐있는 작업

**원칙:** `NEVER use general-purpose subagent when a specialized agent exists`

**적대적 병렬 검증:** 여러 관점의 적대적 검증이 필요하면 general-purpose 복제로 fan-out하지
말고 **이종 전용 에이전트로 fan-out**한다 — `review-code`(적대 리뷰) + `devils-advocate`
(실패 시나리오) + `verify-integration`(연동 검증). 동일 에이전트 다중 복제는 관점 다양성
(편향 방지)을 잃는다. 단, 다중도메인·외부지식 자유 조사는 위 general-purpose 예외를 유지한다.

---

## 4. DELEGATION_SIGNAL 형식 — 폐기됨 (2026-08-27, W-022 R1)

이 절은 원래 위임 신호 블록 형식을 여기서도 반복 설명했다. 정본
(`plugins/common/rules/agent-system.md`)에서 이 블록 정의를 제거했으므로 이 해설도
따라간다 — 이 문서는 정본을 재정의하지 않는다는 원칙 그대로다. 서브에이전트 출력을
받은 뒤의 절차는 `agent-delegation-chain.md`(해설본) §2를 보라. 폐기 근거:
`docs/specs/2026-08-27-delegation-signal-contract-review.md`(W-021).

---

## 5. isolation: worktree 기준

`isolation: worktree`는 에이전트가 별도의 git worktree에서 실행되도록 합니다. 파일을 수정하는 에이전트에 반드시 적용해야 합니다.

```yaml
# 파일 수정 에이전트 — isolation 필수
---
name: implement-code
isolation: worktree # ← 반드시 설정
---
# 읽기 전용 에이전트 — isolation 불필요
---
name: explore-codebase
# isolation 없음 — 파일 읽기만 하므로
---
```

| 에이전트              | isolation | 이유                              |
| --------------------- | --------- | --------------------------------- |
| `implement-code`      | ✅ 필요   | 새 코드 파일 생성, 기존 파일 수정 |
| `fix-bugs`            | ✅ 필요   | 버그 수정 = 파일 변경             |
| `write-tests`         | ✅ 필요   | 테스트 파일 생성                  |
| `write-api-tests`     | ✅ 필요   | API 테스트 파일 생성              |
| `implement-api`       | ✅ 필요   | API 코드 생성/수정                |
| `generate-boilerplate`| ✅ 필요   | 보일러플레이트 파일 생성          |
| `sync-docs`           | ✅ 필요   | 문서 파일 생성/수정               |
| `optimize-logic`      | ✅ 필요   | 소스 코드 Edit                    |
| `explore-codebase`    | ❌ 불필요 | 읽기 전용 탐색                    |
| `review-code`         | ❌ 불필요 | 읽기 전용 검토                    |
| `plan-implementation` | ❌ 불필요 | 계획 문서 작성만 (md 파일은 허용) |

**worktree 없이 파일 수정 에이전트를 실행하면?**

- 여러 에이전트가 동시에 같은 파일을 수정할 때 충돌 발생
- 작업 실패 시 원본 브랜치가 오염됨
- 격리 없이 부분 완료 상태가 메인 브랜치에 남음

---

## 6. disallowedTools 정책

에이전트 유형에 따라 사용 가능한 도구를 제한합니다.

```yaml
# 일반 에이전트 — 서브에이전트 생성 금지
disallowedTools:
  - Task

# 메타 에이전트 (facilitator, synthesizer 등) — Bash 금지
disallowedTools:
  - Bash
```

**왜 일반 에이전트는 Task를 사용할 수 없는가?**

- 서브에이전트가 또 다른 서브에이전트를 생성하면 무한 재귀 가능성
- 위임 체인 관리가 복잡해져 디버깅이 어려워짐
- 메인 Claude만 위임 체인을 조율하는 단일 조율자 원칙 위반

**왜 메타 에이전트는 Bash를 사용할 수 없는가?**

- 메타 에이전트(facilitator 등)는 분석·판단 역할
- Bash는 시스템 명령 실행 → 분석 에이전트의 책임 범위 초과
- 분석과 실행을 분리해 역할 명확화

---

## 7. Phase Gate 패턴

Phase Gate는 각 개발 단계를 완전히 완수하고 다음 단계로 넘어가는 원칙입니다.

```
┌──────────────────────┐
│   Phase 1: Planning  │
│   P0 모호함 = 0      │
│   비즈니스 규칙 정의  │
│   데이터 모델 완성   │
└──────────┬───────────┘
           │ Exit Gate: P0=0, 핵심 규칙 정의, 데이터 모델 완성
           ▼
┌──────────────────────┐
│  Phase 2: Development│
│  요구사항 구현 완료  │
│  핵심 로직 테스트    │
│  빌드·린트 통과      │
└──────────┬───────────┘
           │ Exit Gate: 빌드 성공, 테스트 80%+, 린트 통과
           ▼
┌──────────────────────┐
│  Phase 3: Validation │
│  코드 리뷰 완료      │
│  보안 스캔 통과      │
│  통합 테스트 통과    │
└──────────┬───────────┘
           │ Exit Gate: Must Fix=0, Critical 보안=0, 통합 테스트 통과
           ▼
        Complete
```

### Exit Gate 체크리스트

**Phase 1 → Phase 2 (Planning → Dev)**

- [ ] P0 모호함 0개 (핵심 비즈니스 규칙 모두 명확)
- [ ] 비즈니스 규칙 정의됨 (계산·권한·상태 전이)
- [ ] 데이터 모델 확정
- [ ] 주요 사용자 흐름 명확

**Phase 2 → Phase 3 (Dev → Validation)**

- [ ] 빌드 성공
- [ ] 핵심 로직 테스트 커버리지 ≥ 80%
- [ ] 린트/타입 체크 통과
- [ ] 모든 요구사항 구현 완료

**Phase 3 → Complete (Validation → Done)**

- [ ] 코드 리뷰 Must Fix 항목 0개
- [ ] Critical 보안 이슈 0개
- [ ] 통합 테스트 통과
- [ ] 최종 빌드 성공

---

## 8. 에이전트 Frontmatter 전체 옵션

```yaml
---
name: agent-name # kebab-case, 파일명과 일치
description: | # 한국어 + 영어 트리거 조건
  MUST USE when: "keywords"
  OUTPUT: 결과 형식
model: sonnet # opus | sonnet | haiku
effort: medium # low | medium | high | max
isolation: worktree # 파일 수정 에이전트만
tools:
  - Read
  - Edit
  - Bash
disallowedTools:
  - Task # 일반 에이전트
permissionMode: acceptEdits
hooks:
  PreToolUse:
    - matcher: "Edit"
      hooks:
        - type: command
          command: "python3 ~/.claude/hooks/protect-sensitive.py"
context_cache:
  use_session: true
  session_includes:
    - CLAUDE.md
---
```
