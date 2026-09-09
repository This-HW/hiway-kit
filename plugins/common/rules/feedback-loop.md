---
tier: conditional
activates: 과거 결함 digest를 얻을 수 있을 때 (주입되었거나 직접 조회 가능)
portable: true
portable_reason: 저장은 파일, 읽기는 CLI — 훅이 없는 하네스도 직접 조회하면 성립한다
---

# Feedback Loop Rule (Spec 3 / W-007)

validation·review에서 반복 발견된 결함을 학습해 같은 실수를 반복하지 않는다.

## digest 확보 — 방법은 하네스마다 다르고 규율은 같다

훅이 있으면 세션 시작 시 `=== LESSONS ===`로 **자동 주입**된다. 훅이 없으면
**직접 조회한다** — `python3 <킷 hooks 경로>/feedback_ledger.py digest`.
세션이 아닌 API 성 호출이면 **호출자가 미리 조회해 프롬프트에 싣는다**.

**"주입을 못 받았으니 해당 없음"으로 넘어가지 마라** — 조회 수단이 있으면 조회한다.
경로를 못 찾으면 무동작이다(fail-open, 학습 루프가 본 작업을 막지 않는다).

## 적용

- digest를 확보했으면 **구현·리뷰 전 우선 점검**한다 — 구현 시 그 패턴을 사전 회피하고,
  리뷰 시 우선 검사 항목에 넣는다.
- 검증에서 **실제로 발견된** 결함만 `feedback_ledger.py upsert`로 누적한다
  (통과 패턴·추측은 노이즈).
- ledger는 헬퍼(`hooks/feedback_ledger.py`)가 SSOT — 상한·중복제거·감쇠를 코드로
  보장한다. **직접 테이블을 편집하지 않는다.**
