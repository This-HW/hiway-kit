# Definition of Done — 완료 게이트 (Spec 6)

**Goal:** 거짓 "완료" 주장을 구조적으로 불가능하게 만든다. "완료"를 판단이 아니라
명령(`verify-done.sh`)의 출력으로 만들고, 수동 DoD 항목을 강제 attest한다.

**Architecture:** 원인은 "완료"가 검증 가능한 체크리스트에 묶이지 않아 약한 대용물
("편집 끝 + 내가 고른 검사 통과")로 치환된 것. 해결은 규칙(soft)만으로는 같은 실패를
반복하므로 **기계적 게이트**를 둔다 — 기존에 흩어진 검사(ruff·pytest·JSON·CI 필드·카운트
sync·stale 참조·시크릿)를 단일 SSOT 스크립트로 통합 실행하고, FAIL 시 비정상 종료한다.
verification-before-completion의 확장(코드 → 완료 주장 자체).

**Version:** 2.6.0 배치에 포함 (미릴리스 — 별도 bump 없이 Spec 1~5와 함께).

**계기:** Spec 1~5 배치 후 "완료" 오보고 → 근본원인 분석 → 재발방지 설계.

---

## 요구사항

1. "완료" 주장 전 모든 기계 검사를 단일 명령으로 실행·통과해야 한다.
2. 자동화 불가한 DoD 항목(스펙 대조·적대적 리뷰·Work 상태·문서 반영)은 명시 attest.
3. 금지 어휘 규율 — 검증 전 "완료/done" 사용 금지.
4. loop-engineering 종료 조건을 "마지막 스텝 도달"에서 "verify-done green + attest"로 교체.

## 컴포넌트

- `rules/definition-of-done.md` — DoD 정의 + Iron Law of Completion + 금지 어휘 (ALWAYS_RULES 등록).
- `scripts/verify-done.sh` — 기계 게이트(JSON·필드·ruff·pytest·시크릿·카운트 sync·stale 참조). exit 1 on any FAIL.
- `rules/loop-engineering.md` 연계 — 완료 조건 = verify-done green + attest.

## 검증 기준

- verify-done.sh가 의도적 결함(카운트 불일치·삭제 스크립트 참조)에서 FAIL 종료.
- 정상 상태에서 green + exit 0.
- 수동 attest 4항목이 항상 출력됨.

## 범위 외

- 수동 attest 항목의 완전 자동화(적대적 리뷰는 본질적으로 판단 — 강제 가시화까지만).
- CI 통합(차기: verify-done.sh를 validate.yml에서 호출).
