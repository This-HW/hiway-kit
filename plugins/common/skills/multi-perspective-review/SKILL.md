---
name: multi-perspective-review
description: Multi-perspective review of a plan or design document. Up to ten viewpoints deliberate in 3 rounds; the main session orchestrates, with a sequential path for harnesses without subagents.
---

# multi-perspective-review: 다관점 협업 리뷰

> Deliberation Pattern 기반 문서 검토 — 관점별 독립 의견 → 상호 검토 → 합의

---

## 개요

복잡한 기획·설계 문서를 여러 관점이 **독립적으로** 검토한 뒤, 서로의 의견을 보고 재검토하고,
충돌을 트레이드오프로 정리해 합의안을 낸다. 단순 체크리스트가 아니라 **의견 교류와 합의**가 산출물이다.

**조율은 이 스킬을 실행하는 메인 세션이 한다.** 관점 선택·종합·충돌 분석·영향도 분석은
별도 에이전트가 아니라 아래 절차의 **스킬 단계**다. 관점 검토만 서브에이전트에 맡길 수 있고,
서브에이전트가 없는 하네스에서는 메인 세션이 순차로 수행한다(아래 [실행 경로](#실행-경로)).

---

## 10개 관점 (Perspectives)

| 관점                 | 역할            | 맡길 수 있는 에이전트 | 포커스                                    |
| -------------------- | --------------- | --------------------- | ----------------------------------------- |
| **Requirements**     | 기획자          | clarify-requirements  | P0 모호함, 엣지 케이스, 비기능 요구사항   |
| **Technical**        | 개발자          | plan-implementation   | 기술적 실현가능성, 개발 기간, 시스템 충돌 |
| **Security**         | 보안            | security-scan         | 인증/권한, 민감 데이터, 공격 벡터         |
| **UX/Flow**          | UX 디자이너     | design-user-journey   | 사용자 흐름, 상호작용, 접근성             |
| **Business Logic**   | 비즈니스 분석가 | define-business-logic | 비즈니스 규칙, 도메인 로직, 정책          |
| **Dependencies**     | 아키텍트        | analyze-dependencies  | 외부 연동, 라이브러리, 시스템 간 의존성   |
| **Code Quality**     | 리뷰어          | review-code           | 코드 품질, 유지보수성, 테스트 가능성      |
| **Metrics**          | 데이터 엔지니어 | — (관점 프롬프트)     | 성능 지표, 모니터링, SLA                  |
| **Data/Schema**      | DB 설계자       | — (관점 프롬프트)     | 스키마 설계, 데이터 모델, 마이그레이션    |
| **Devil's Advocate** | 전략 비평가     | devils-advocate       | 실패 시나리오, 설계 약점, 리스크 정량화   |

"맡길 수 있는 에이전트"는 **선택**이다. 에이전트가 없거나(—), 설치돼 있지 않거나, 하네스가
서브에이전트를 지원하지 않으면 그 관점은 **관점 프롬프트**(perspectives-guide.md 의 해당 절:
역할·책임·질문 항목)로 수행한다. 에이전트 이름은 호스트가 노출하는 이름을 쓴다(플러그인 접두사가
붙을 수 있다).

**상세:** [perspectives-guide.md](perspectives-guide.md)

---

## 워크플로우 (3-Round Deliberation)

```
Round 0  관점 선택          (메인 세션)
  → 문서 유형·복잡도·도메인 파악, 필요한 관점과 관점별 초점 영역 결정
  → 공통 컨텍스트 수집: 대상 문서 + 프로젝트 에이전트 지침 파일(CLAUDE.md·AGENTS.md 중 있는 것)
         ↓
Round 1  독립 의견          (관점마다 — 병렬 가능)
  → 각 관점은 공통 컨텍스트 + 자기 초점 영역만 받는다. 다른 관점 의견은 주지 않는다
         ↓
종합 1   중복·충돌 식별      (메인 세션)
  → Critical / Important / Nice-to-have 분류, 동일 이슈 통합, 관점 간 충돌 목록
         ↓
Round 2  상호 검토          (관점마다 — 순차)
  → Round 1 종합 + 자기 의견 + 다른 관점 의견을 보고 유지/변경/추가/충돌 해결 제안
  → 새 이슈·입장 변경이 하나도 없으면 Round 2 를 끝내고 Round 3 으로
         ↓
Round 3  합의 + 영향도       (메인 세션)
  → 충돌별 근본 원인·트레이드오프·합의안 (conflict-resolution.md)
  → Hard Constraint 충돌은 사용자 결정으로 올린다 (호스트의 질문 수단)
  → 합의된 변경의 영향 범위·리스크·비용 추정 — 코드베이스 영향이 크면 analyze-dependencies 로 확인
         ↓
최종 리포트                 (메인 세션)
```

**상세:** [deliberation-pattern.md](deliberation-pattern.md)

---

## 실행 경로

### A. 서브에이전트가 있는 하네스 (예: Claude Code)

- Round 1: 관점마다 서브에이전트를 **한 메시지에 병렬로** 띄운다. 에이전트가 없는 관점은
  범용 서브에이전트에 관점 프롬프트를 준다.
- Round 2: 관점마다 순차로 띄운다(앞 관점의 재검토가 뒤 관점의 입력이 된다).
- 종합·Round 3·최종 리포트는 메인 세션이 직접 한다 — 서브에이전트에 맡기지 않는다.
- 서브에이전트는 다른 서브에이전트를 부르지 않는다. 조율은 전부 메인 세션에 있다.

### B. 서브에이전트가 없는 하네스 (예: Codex) — 순차 경로

메인 세션이 모든 관점을 **차례로** 수행한다. 독립성이 이 패턴의 핵심이므로 순서를 지킨다:

1. Round 1 의 관점 블록을 하나씩 쓴다. 각 블록은 그 관점의 질문 항목에만 답하고,
   **앞서 쓴 관점 블록을 근거로 인용하지 않는다.** 다 쓴 블록은 고치지 않는다.
2. 모든 Round 1 블록을 쓴 **뒤에** 종합 1 을 한다.
3. Round 2 는 관점별로 "유지/변경/추가/충돌 제안"을 한 블록씩 쓴다.
4. Round 3·최종 리포트는 경로 A 와 같다.

같은 컨텍스트에서 수행하므로 관점 간 독립성은 경로 A 보다 약하다. 최종 리포트의
Executive Summary 에 `실행 경로: 순차(단일 컨텍스트)` 를 적어 읽는 사람이 이를 알게 한다.

---

## 사용법

```bash
# 문서 파일 직접 지정
/multi-perspective-review docs/planning/point-system.md

# 계획 파일 지정
/multi-perspective-review docs/plans/2026-09-28-point-system/plan.md
```

---

## 실행 예시

### 입력 문서

```markdown
# 포인트 시스템 추가

## 요구사항

- 사용자가 구매 시 포인트 적립
- 포인트로 결제 가능
- 포인트 유효기간 1년
```

### 실행 과정

```
🔍 Round 0: 관점 선택 (메인 세션)
  → 복잡도: Large
  → 선택된 관점: Requirements, Technical, Security, Business Logic, Data/Schema

⚡ Round 1: 독립 의견 (병렬)
  ├─ Requirements: P0 모호함 3개 발견 (사용자 정의, 적립률, 사용 제한)
  ├─ Technical: 개발 3주 예상, 트랜잭션 무결성 필요
  ├─ Security: 포인트 조작 방지, 감사 로그 필수
  ├─ Business Logic: 적립률 5%, 최소/최대 사용 제한
  └─ Data/Schema: points, point_transactions 테이블 필요

📊 종합 1 (메인 세션)
  → Critical: 2개, Important: 3개, Nice-to-have: 2개
  → 충돌: 2개 (개발 기간, Rate Limiting 우선순위)

🔄 Round 2: 상호 검토 (순차)
  ├─ Technical (재검토): 보안 요구사항 반영 → 3주 확정
  └─ Security (재검토): Rate limiting Phase 2 연기 수용

🤝 Round 3: 합의 + 영향도 (메인 세션)
  ├─ 충돌 2개 해결 (Phase 분할, 우선순위 조정) — 합의율 100%
  └─ 영향도: 3개 시스템, 총 26.5일 예상

📝 최종 리포트
  → Critical 2개, Important 3개, 액션 아이템 5개
  → 권장: 조건부 승인 (트랜잭션 테스트 필수)
```

**상세 예시:** [examples.md](examples.md)

---

## 출력 형식

### 최종 리포트 구조

```markdown
# 다관점 리뷰 최종 결과

## 📋 Executive Summary

- 문서: [문서명]
- 복잡도: [Small/Medium/Large]
- 참여 관점: [N]개
- 실행 경로: [병렬(서브에이전트) / 순차(단일 컨텍스트)]
- 합의 상태: [X]% 합의

---

## 🔴 Critical (즉시 수정 필요)

### 1. [이슈명]

**제기 관점:** [관점 목록]
**내용:** [상세 설명]
**영향:** [영향 범위]
**해결:** [구체적 해결책]
**합의:** ✅ 전원 합의 / ⚠️ 조건부 / ❓ 사용자 결정 필요

---

## 🟡 Important (수정 권장)

...

## 🟢 Nice-to-have (선택 사항)

...

---

## 💬 합의 과정

### 충돌 #1: [충돌 설명]

**Round 1:** [초기 의견]
**Round 2:** [재검토 의견]
**합의안:** [최종 합의]
**결과:** ✅ 해결 / ❓ 사용자 결정 대기

---

## 📊 영향도 분석

**변경 범위:**

- 시스템: [영향받는 시스템 목록]
- 파일: [예상 변경 파일 수]

**개발 기간:** [예상 시간]
**리스크:** [리스크 레벨 및 완화 방안]

---

## 🎯 다음 단계

1. [ ] [액션 아이템 1]
2. [ ] [액션 아이템 2]
       ...
```

---

## 비용 조절

관점 수를 문서 복잡도에 맞게 줄인다(Small 문서면 Requirements·Technical 둘로 충분하다).
Round 2 에서 새 이슈·입장 변경이 없으면 바로 Round 3 으로 간다.

---

## 주의사항

```
⚠️ 복잡한 문서에만 사용
   → 단순 변경은 단일 관점 리뷰로 충분

⚠️ 충돌이 많으면 시간 증가
   → 사전에 기획 명확화 권장

⚠️ 사용자 결정 필요 시 중단
   → 호스트의 질문 수단으로 묻고 답을 기다린다
```

---

## 관련 스킬

| 스킬          | 관계 | 설명                        |
| ------------- | ---- | --------------------------- |
| **plan-task** | 선행 | 작업 계획 수립 후 문서 리뷰 |
| **auto-dev**  | 후행 | 리뷰 통과 후 자동 개발      |
| **review**    | 대안 | 코드 리뷰 (구현 후)         |

---

## References

- [deliberation-pattern.md](deliberation-pattern.md) - 3-Round 패턴 상세
- [perspectives-guide.md](perspectives-guide.md) - 10개 관점 가이드 (관점 프롬프트)
- [conflict-resolution.md](conflict-resolution.md) - 충돌 해결 전략
- [examples.md](examples.md) - 실제 리뷰 예시
