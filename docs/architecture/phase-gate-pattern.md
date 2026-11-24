---
status: current
as_of: 2026-10-05
---

# Phase Gate 패턴 (커뮤니티 권장 패턴)

> **중요**: 이 패턴은 Anthropic 공식 기능이 아닌 커뮤니티 베스트 프랙티스입니다.
> zhsama/claude-sub-agent, wshobson/agents 등의 구현을 참고한 권장 패턴입니다.
>
> **이 문서는 해설이다.** 단계별 출구 조건의 정본은 `plugins/common/rules/agent-system.md`
> "Phase Gate" 이고, 작업 크기별로 무엇이 필요한지는 `plan-task` 의
> `references/elicitation.md §6` 이 소유한다. 아래 기준은 그 둘을 풀어 쓴 것이며,
> 값이 갈리면 정본이 맞다. **어떤 훅도 Phase Gate 를 자동 판정하지 않는다** — 단계 전환은
> 해당 스킬(`plan-task`·`auto-dev`)과 메인 세션의 판단이 수행한다.

---

## 이 패턴이 필요한 이유

기획에서 핵심 모호함을 해결하고 구현 전에 계획을 검토하면, 구현 중에 기획을 다시 열어야
하는 상황을 줄일 수 있다.

---

## Exit Gate란?

### Exit Gate는 자동 검증 시스템이 아닙니다

**Exit Gate = 메인 Claude의 판단 기준**

![요구사항 확인에서 P0 질문과 계획 승인을 거쳐 구현을 시작하는 흐름](diagrams/planning-gate/planning-gate.svg)

메인 세션은 요구사항에서 P0 모호함을 찾는다. P0가 있으면 멈추고 사용자에게 질문해 답과
근거를 기록한다. 구현 계획에 완료 명령을 담고 승인을 받은 뒤 구현으로 넘어간다.

### Exit Gate 판단 기준

**Planning Phase:**

- P0 모호함 모두 해결되었는가?
- 핵심 비즈니스 규칙이 명확한가?
- 데이터 모델이 정의되었는가?
- 주요 사용자 흐름이 명확한가?

**Development Phase:**

- 요구사항이 모두 구현되었는가?
- 바꾼 동작의 테스트가 통과하는가?
- 빌드·린트·타입 검사가 통과하는가?

**Validation Phase:**

- 코드 리뷰에서 막는 결함이 없는가?
- 보안 검사에 Critical 이 없는가?
- 완료 조건 명령이 통과하는가?

---

## 현실적인 Phase 흐름

### Phase 1: Planning (목표: 최대한 완전하게)

요구사항 정리는 `clarify-requirements`에 위임하거나 직접 수행한다. Medium 이상은 사용자
여정을, Large는 비즈니스 로직을 계획에 포함한다. [위 기획 도식](#exit-gate란)에서 P0를
확인하고 사용자 승인을 받는 위치를 볼 수 있다.

### Phase 2: Development (목표: 구현 완료)

![계획의 미완 항목을 구현하고 개발 검사를 통과하면 Validation으로 넘어가는 흐름](diagrams/development-gate/development-gate.svg)

계획 원문에서 미완 항목을 찾아 구현한다. 구현 중 기획 공백을 만나면 유형에 맞게 기획으로
돌아간다. 빌드, 변경 동작의 테스트, 린트와 타입 검사를 통과하면 Validation으로 넘어간다.

### Phase 3: Validation

![스펙 준수를 먼저 확인하고 리뷰와 보안 검사 후 완료 명령을 다시 실행하는 흐름](diagrams/validation-gate/validation-gate.svg)

스펙 준수를 먼저 확인한 뒤 코드 리뷰와 보안 검사를 병렬로 실행한다. 완료 조건 명령을
다시 실행해 모두 rc 0인지 확인한다. 리뷰가 ACCEPT이고 보안 검사에서 CRITICAL·HIGH가
없어야 완료로 판정한다. 기준에 못 미치면 남은 항목을 사용자에게 보고한다.

---

## Stop 훅은 Phase Gate 가 아니다

킷의 `Stop` 훅(`stop-validator.py`, `type: command`)은 **안전망**이다 — 이 세션에서 수정된
`.py` 를 ruff 로 린트하고, 이 세션이 고친 테스트 파일만 pytest 로 돌려 실패하면 계속 작업하게
한다. 단계 전환·기획 완결성·리뷰 통과 여부는 **판정하지 않는다.** Phase Gate 는 스킬을
호출해야 돈다.

---

## 판단 기준 (참고용)

### Planning Phase Exit Criteria

| 항목          | 판단 질문                           | 목표   |
| ------------- | ----------------------------------- | ------ |
| 요구사항      | P0 모호함이 모두 해결되었는가?      | 100%   |
| 사용자 여정   | 핵심 흐름이 명확한가?               | 명확   |
| 비즈니스 규칙 | 계산/검증/상태 규칙이 정의되었는가? | 정의됨 |
| 데이터 모델   | 스키마가 정의되었는가?              | 정의됨 |

### Development Phase Exit Criteria

| 항목   | 판단 질문                         | 목표 |
| ------ | --------------------------------- | ---- |
| 구현   | 요구사항이 모두 구현되었는가?     | 100% |
| 테스트 | 바꾼 동작의 테스트가 통과하는가?  | 통과 |
| 품질   | 빌드/린트/타입 검사가 통과하는가? | 통과 |

### Validation Phase Exit Criteria

| 항목 | 판단 질문                         | 목표 |
| ---- | --------------------------------- | ---- |
| 리뷰 | 리뷰가 막는 결함을 냈는가?        | 0개  |
| 보안 | Critical 이슈가 없는가?           | 0개  |
| 완료 | 완료 조건 명령이 통과하는가?      | 통과 |

리뷰 판정 등급(`review-code` 의 REJECT/CONDITIONAL/ACCEPT·심각도)과 정확한 통과선은
정본(`rules/agent-system.md`, `auto-dev` 의 T-merge)을 따른다.

---

## 안티패턴

### ❌ 1. Planning 불충분 상태로 Dev 시작

```
Planning 70% 완료 → "일단 시작하자" → Dev 시작
→ Dev 중 Planning Gap 대량 발견 → 재구현 필요
```

### ❌ 2. 역위임을 완전히 금지

```
"Dev에서 Planning agent 호출 절대 불가"
→ 현실적으로 불가능
→ Planning Gap 발견 시 막힘
```

올바른 방법: 역위임 **최소화**가 목표, 발생 시 신속히 처리

### ❌ 3. Exit Gate 자동화 시도 (스킬로 구현)

```
"자동으로 95% 계산해서 통과/실패 판단하는 스킬"
→ 구현 복잡도 높음, 실제 효과 제한적
```

올바른 방법: 메인 Claude의 판단 + 완료 조건 명령의 출력(`definition-of-done`)

---

## 베스트 프랙티스

### 1. Planning Phase에 충분한 시간 투자

```
Planning 1시간 → Dev 5시간 (총 6시간)
Planning 2시간 → Dev 3시간 (총 5시간) ✅
```

### 2. P0 모호함 Zero Tolerance

P0 (핵심 비즈니스) 모호함은 Planning 단계에서 100% 제거:

- 결제 금액 계산 방식
- 권한 체크 로직
- 데이터 삭제 정책
- 금융/보안 규칙

P1/P2는 Dev 중 해결 가능

### 3. 역위임 발생 시 즉시 처리

`P0_AMBIGUITY`는 즉시 멈추고 사용자 답을 받아 결정 사항을 기록한다. `MISSING_SPEC`는
명세에 추가하고, `INFEASIBLE`은 대안을 검토한 뒤 보고한다. [기획 공백 분기 도식](rules/planning-protocol.md#3-dev--planning-역위임-프로토콜)을
참고한다.

---

## 핵심 요약

```
1. Phase Gate = 메인 Claude의 판단 기준 (자동 시스템 아님)
2. Stop 훅은 린트·수정 테스트 안전망일 뿐 — Phase Gate 는 스킬 호출로 돈다
3. Planning → 최대한 완전하게 → Dev 시작
4. Dev 중 Planning Gap 발견 = 현실적으로 발생 가능
5. 역위임 최소화가 목표 (완전 금지 아님)
6. 커뮤니티 권장 패턴 (공식 기능 아님)
```

---

## 참고 문서

**커뮤니티 구현:**

- [zhsama/claude-sub-agent - Quality Gates](https://github.com/zhsama/claude-sub-agent)
- [wshobson/agents - Multi-agent Coordination](https://github.com/wshobson/agents)

**관련 파일:**

- `plugins/common/rules/agent-system.md` — Phase Gate 판단 기준
- `plugins/common/hooks/stop-validator.py` — Stop 훅(안전망, Phase Gate 아님)
