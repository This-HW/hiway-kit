---
tier: conditional
activates: LESSONS 주입 시 (feedback ledger digest 존재)
portable: true
---

# Feedback Loop Rule (Spec 3 / W-007)

validation·review에서 반복 발견된 결함을 학습해 같은 실수를 반복하지 않는다.

## 적용

- session-start가 `=== LESSONS ===` 컨텍스트를 주입하면, **구현·리뷰 전 우선 점검**한다.
  - `implement-code`: LESSONS의 패턴을 사전 회피하며 작성.
  - `review-code`: LESSONS 패턴을 우선 검사 항목으로 포함.
- auto-dev validation(T-merge)에서 발견된 결함은 `feedback_ledger.py upsert`로 누적한다.
- ledger는 헬퍼(`hooks/feedback_ledger.py`)가 SSOT — 상한·중복제거·감쇠를 코드로 보장한다. 직접 테이블을 편집하지 않는다.

## 경계

- 발견된 실제 결함만 기록 (통과 패턴·추측은 노이즈).
- ledger 부재 시 전 구간 무동작 (opt-in, fail-open) — 학습 루프가 본 작업을 막지 않는다.
