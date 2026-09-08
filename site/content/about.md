---
title: "소개"
description: "hiway-kit의 아키텍처와 구현 원리 — 하네스 × 루프 엔지니어링, 결정적 가드레일, Definition-of-Done 기계 게이트."
keywords: ["claude code plugin", "multi-agent development system", "agent harness engineering", "AI coding agent evals", "definition of done"]
translationKey: "about"
---

**hiway-kit**은 [Claude Code](https://claude.com/claude-code) 하네스 위에서
동작하는 멀티 에이전트 개발 시스템이다. 이 페이지는 무엇을 만들었는지가 아니라
**왜 이렇게 설계했는지**를 설명한다.

## 1. Harness × Loop Engineering

업계는 AI 코딩 에이전트의 성숙도를 3단계로 본다: 프롬프트 엔지니어링 →
컨텍스트 엔지니어링 → **하네스 엔지니어링**. 하네스는 툴 오케스트레이션·상태
영속화·검증 루프·에러 복구를 태스크 전체 생애주기에 걸쳐 통제한다.

hiway-kit은 이 구분을 다음과 같이 명문화한다.

<div class="callout">
<strong>게이트 vs 루프</strong>

- **게이트(Gate)** — 사람이 멈추고 판단해야 하는 지점. 요구사항 모호성 해소,
  아키텍처 결정, 릴리스 승인.
- **루프(Loop)** — 기계가 자율적으로 완주할 수 있는 지점. 구현 → 검증 →
  실패 시 자동 수정, 명확한 종료 조건(exit criteria)이 있는 반복.
</div>

계획 단계에서 모호성을 100% 제거(게이트)하고, 구현·검증 단계는 루프로
자율 완주시키는 것 — 이것이 3단계 파이프라인의 핵심이다.

```
Phase 1 (Planning)    → 요구사항 모호성 제거 (게이트)
Phase 2 (Development) → Phase 1 산출물 기반 구현 (루프)
Phase 3 (Validation)  → 리뷰 + 보안 스캔 병렬 실행 (루프 + 게이트)
```

## 2. 33 에이전트 · 16 스킬 · 3단 모델 티어링

에이전트는 역할별로 나뉘고, 스킬(`/plan-task`, `/auto-dev`, `/review`, `/debug`,
`/test` 등)이 실제 위임을 구동한다. 각 에이전트는 작업 성격에 맞는 모델 티어를
쓴다.

| 모델 | 용도 | 예시 |
|------|------|------|
| Opus | 전략·분석·리뷰 | clarify-requirements, review-code |
| Sonnet | 코드 구현·수정 | implement-code, fix-bugs, write-tests |
| Haiku | 탐색·단순 점검 | explore-codebase, verify-code |

leaf 에이전트는 서브 에이전트를 다시 생성하지 않는다(`disallowedTools: [Task]`).
이건 "메인만 조율해야 한다"는 도그마가 아니라, 현재 스케일에서 에이전트 중첩이
성능 이득 없이 예측불가능성만 늘리기 때문이다 — **스케일에 맞는 프리미티브를
쓴다**는 원칙이다.

<div class="loop">
  <span class="node start">Small/Medium</span>
  <span class="arrow">→</span>
  <span class="node step">스킬 주도 플랫 위임</span>
  <span class="arrow">→</span>
  <span class="node done">검증된 경로</span>
</div>
<div class="loop">
  <span class="node start">Large (10~100+)</span>
  <span class="arrow">→</span>
  <span class="node step">네이티브 ultracode</span>
  <span class="arrow">→</span>
  <span class="node done">사용자 수동 트리거</span>
</div>

## 3. 병렬 worktree 격리

파일을 수정하는 에이전트(implement-code, fix-bugs, write-tests 등)는
`isolation: worktree`로 격리된 git worktree에서 실행된다. 목적은 파일시스템
경합 방지이지 그 자체가 목적이 아니다 — 실제 병목은 격리가 아니라 **병합과
리뷰**라는 것이 업계 공통 관찰이다.

```
격리 실행 → 검증 그린 → 순차 병합
                ↓ 레드
          plan-refactor 또는 git-workflow로 에스컬레이션 (충돌 임의 선택 금지)
```

## 4. 결정적 가드레일(Deterministic Guardrails)

LLM 판단만으로 품질을 보장하지 않는다. 결정론적 훅이 매 단계를 강제한다.

- **protect-sensitive.py** — 민감 경로(`.env`, 키, `.pem`) 접근 차단 (path 기반)
- **auto-format.py** — 편집 후 자동 포맷 (Python은 ruff)
- **stop-validator.py** — 세션 종료 전 린트 + 관련 테스트 실행, 실패 시
  `decision: block`으로 재진입시켜 자동 수정 유도 (전체 스위트가 아니라 **이
  세션에서 편집한 파일**만 스코핑 — 그건 CI/`/test`의 몫)

Fowler의 프레임으로 정리하면: `rules/`는 **feedforward**(행동 전 조향),
`hooks/`는 **feedback**(행동 후 관찰)이다.

## 5. Definition-of-Done — 기계 게이트

"완료"는 주장이 아니라 검증이다. `scripts/verify-done.sh`가 8개 이상의
기계 게이트를 통과해야 릴리스 후보로 인정한다 — 버전 동기화, 에이전트
frontmatter 완결성, 금지 필드 검사, pytest 그린, 시크릿 스캔 등.

작성자 에이전트는 자신이 만든 것을 합리화하는 경향이 있다(오염된
self-evaluation). 그래서 검증은 별도 세션·별도 에이전트가 담당한다 — 크지
않아도 되지만 **달라야** 한다.

## 6. Agent Behavior Evals — 신규

에이전트 자체의 행동 품질을 회귀 테스트하는 계층. **deterministic-first**
채점(가능한 한 규칙 기반, LLM 채점은 보조)으로 11개 시나리오를 검증하고,
"false-green"(실패했는데 통과로 보이는 것)을 릴리스 게이트에서 차단한다.

## 7. Feedback Ledger + /self-improve

세션에서 발견한 패턴·실수는 feedback ledger에 기록되어 다음 이터레이션의
컨텍스트로 재사용된다. `/self-improve`는 이 학습 루프를 재귀적으로 실행하되
**제안-전용**이다 — evals 통과 + 사람 승인이라는 이중 게이트 없이는 스스로를
바꾸지 않는다.

## 8. /native-watch — 흡수 감시

Claude Code 자체가 새 네이티브 기능을 내놓으면 kit의 커스텀 구현은 중복이 된다.
`/native-watch`는 이런 흡수(subsumption) 신호를 감시해, 자체 구현을 유지할지
네이티브로 이전할지 판단하는 근거를 만든다. 실제 사례: 서브에이전트 생명주기
추적은 OpenTelemetry 네이티브 지원으로 흡수되어 커스텀 훅(`agent-lifecycle.py`)을
2.6.0 배치에서 제거했다.

---

더 알아보기: [시작하기](/getting-started/)에서 실제 설치·사용 시나리오를 확인하거나,
[개발 기록](/posts/)에서 이 설계가 어떻게 진화해왔는지 읽어본다.

저장소: [github.com/This-HW/hiway-kit](https://github.com/This-HW/hiway-kit) (MIT)
