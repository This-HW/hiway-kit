---
tier: core
portable: true
---

# Planning Protocol Rules

NEVER implement based on assumption. ALWAYS verify against specs or ask the user.
NEVER hedge ("~할 것 같다", "아마", "보통은"); say "기획에 따르면"/"확인 결과" instead.

## 모호함 등급 (P0~P3)

**P0** 데이터 무결성·보안·금융·핵심 비즈니스 → 즉시 중단+질문 / **P1** UX 분기·비즈니스
디테일 → 기본값 적용 후 확인 / **P2** UI 디테일·엣지케이스 → TODO 기록 / **P3** 기술
선택(라이브러리·패턴) → 자율 판단.

## Dev ↔ Planning

구현 중 기획 모호함 발견 시 분류하고 Planning으로 돌아간다: `P0_AMBIGUITY`(사용자에게
선택지를 제시하고 답을 받는다 — 호스트가 제공하는 수단으로, 맥락/질문/옵션 명시) ·
`MISSING_SPEC`(명세를 여정/규칙에 추가) · `INFEASIBLE`(대안 검토 후 보고).

## 작업 규모 → Planning 완료 조건

**Small**(1개 모듈·1-3파일) 요구사항만 / **Medium**(2-3개 모듈·4-10파일) +사용자 여정·
상태 전이·에러 전략 / **Large**(4개+ 모듈·10파일+) +비즈니스 규칙·관계·예외 처리.
공통: P0 모호함 = 0, 영향 범위·리스크 분석 완료해야 Dev로 넘긴다.
