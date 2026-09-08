# Phase Gate 패턴 (커뮤니티 권장 패턴)

> **중요**: 이 패턴은 Anthropic 공식 기능이 아닌 커뮤니티 베스트 프랙티스입니다.
> zhsama/claude-sub-agent, wshobson/agents 등의 구현을 참고한 권장 패턴입니다.

---

## 이 패턴이 필요한 이유

**문제:**

```
Planning 불완전 → Dev 구현 시작 → Planning Gap 발견 → 재구현 필요
→ 시간/비용 2-3배 낭비
```

**해결:**

```
Planning → Gap 발견 → Planning 내에서 해결 → 충분히 완료 → Dev 시작
→ 재작업 최소화
```

---

## Exit Gate란?

### Exit Gate는 자동 검증 시스템이 아닙니다

**Exit Gate = 메인 Claude의 판단 기준**

```
실제 작동 방식:

1. Planning subagent 실행 완료
2. 메인 Claude가 결과물 검토
3. 메인 Claude 판단: "이 정도면 Dev 시작해도 되나?"
   ├─ 충분함 → Dev agent 호출
   └─ 부족함 → 추가 Planning agent 호출 (피드백 루프)
```

### Exit Gate 판단 기준

**Planning Phase:**

- P0 모호함 모두 해결되었는가?
- 핵심 비즈니스 규칙이 명확한가?
- 데이터 모델이 정의되었는가?
- 주요 사용자 흐름이 명확한가?

**Development Phase:**

- 요구사항이 모두 구현되었는가?
- 핵심 로직에 테스트가 있는가?
- 빌드가 성공하는가?

**Validation Phase:**

- 코드 리뷰가 완료되었는가?
- 보안 검사를 통과했는가?
- 통합 테스트가 통과하는가?

---

## 현실적인 Phase 흐름

### Phase 1: Planning (목표: 최대한 완전하게)

```
┌─────────────────────────────────────────┐
│ Planning Phase                          │
├─────────────────────────────────────────┤
│ Round 1: 초기 Planning                  │
│   ├─ clarify-requirements               │
│   ├─ design-user-journey (필요시)       │
│   └─ define-business-logic (필요시)     │
│                                          │
│ 메인 Claude 판단:                       │
│   "충분한가?" → 부족 → Round 2          │
│                                          │
│ Round 2: 피드백 루프                    │
│   ├─ AskUserQuestion (P0 모호함)        │
│   ├─ explore-codebase (기존 패턴 확인)  │
│   └─ analyze-domain (도메인 분석)       │
│                                          │
│ 메인 Claude 판단:                       │
│   "충분한가?" → 충분 → Dev Phase        │
│                                          │
│ 목표: 재작업 최소화                     │
└─────────────────────────────────────────┘
```

### Phase 2: Development (목표: 구현 완료)

```
┌─────────────────────────────────────────┐
│ Development Phase                       │
├─────────────────────────────────────────┤
│ Step 1: Planning artifacts 활용         │
│   └─ requirements.md, journey.md 등     │
│                                          │
│ Step 2: 구현                            │
│   ├─ implement-code                     │
│   ├─ write-tests                        │
│   └─ sync-docs                          │
│                                          │
│ Step 3: Planning Gap 발견 (현실)        │
│   메인 Claude 선택:                     │
│   ├─ A) 사용자에게 질문                 │
│   ├─ B) Planning agent 재호출 (역위임)  │
│   └─ C) 합리적 추측 후 진행 (리스크)   │
│                                          │
│ Step 4: 완료 판단                       │
│   메인 Claude: "구현 완료되었는가?"     │
│   → Validation Phase                    │
└─────────────────────────────────────────┘
```

### Phase 3: Validation

```
┌─────────────────────────────────────────┐
│ Validation Phase                        │
├─────────────────────────────────────────┤
│ 병렬 검증:                              │
│   ├─ verify-code                        │
│   ├─ review-code                        │
│   ├─ security-scan                      │
│   └─ verify-integration                 │
│                                          │
│ 메인 Claude 판단:                       │
│   "프로덕션 배포 가능한가?"             │
│   → 가능 → 완료                         │
└─────────────────────────────────────────┘
```

---

## Stop Hook에 의한 자동 품질 검증

Claude Code의 `Stop` hook(prompt type)을 활용하여 Phase Gate 판단을 자동화합니다.
Claude가 작업을 멈추려 할 때 자동으로 품질 기준을 체크합니다.

**구현:** `plugins/common/hooks/hooks.json`의 Stop hook 참조

이 방식으로 **명시적 스킬 호출 없이** Phase Gate 조건이 자동 적용됩니다.

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

| 항목   | 판단 질문                     | 목표 |
| ------ | ----------------------------- | ---- |
| 구현   | 요구사항이 모두 구현되었는가? | 100% |
| 테스트 | 핵심 로직에 테스트가 있는가?  | 80%+ |
| 품질   | 빌드/린트가 통과하는가?       | 통과 |

### Validation Phase Exit Criteria

| 항목 | 판단 질문                 | 목표 |
| ---- | ------------------------- | ---- |
| 리뷰 | 코드 리뷰가 완료되었는가? | 완료 |
| 보안 | Critical 이슈가 없는가?   | 0개  |
| 통합 | 통합 테스트가 통과하는가? | 통과 |

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

올바른 방법: 메인 Claude의 주관적 판단 + Stop hook 자동 검증

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

```
Dev 중 Planning Gap 발견:
├─ 즉시 멈춤
├─ 사용자 질문 또는 Planning agent 호출
├─ 답변 받은 후 진행
└─ 결정 사항 문서화
```

---

## 핵심 요약

```
1. Phase Gate = 메인 Claude의 판단 기준 (자동 시스템 아님)
2. Stop hook이 자동 품질 검증 담당 (명시적 호출 불필요)
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
- `plugins/common/hooks/hooks.json` — Stop hook 구현
