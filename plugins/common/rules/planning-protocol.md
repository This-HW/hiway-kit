---
tier: core
portable: true
---

# Planning Protocol Rules

NEVER implement based on assumption. ALWAYS verify against specs or ask the user.
NEVER hedge; 추측 어휘 대신 "기획에 따르면"/"확인 결과".

## 모호함 등급 (P0~P3) — 이 규범이 소유한다

**P0** 데이터 무결성·보안·금융·핵심 비즈니스 → 즉시 중단+질문 / **P1** UX 분기·비즈니스
디테일 → 기본값 적용 후 확인 / **P2** UI 디테일·엣지케이스 → TODO 기록 / **P3** 기술
선택 → 자율 판단. **"불확실하니 일단 멈춤"도 "사소하니 일단 진행"도 등급 판정을 건너뛴
것이다** — 먼저 등급을 매긴다.

## Dev ↔ Planning

구현 중 모호함 발견 시 분류해 Planning으로 돌아간다: `P0_AMBIGUITY`(맥락/질문/옵션 제시 후
답을 받는다 — 호스트 수단으로) · `MISSING_SPEC`(명세에 추가) · `INFEASIBLE`(대안 검토 후
보고). 명세는 레포 `docs/`와 프로젝트의 지식 소스에서 찾는다 — **특정 도구의 설치를
가정하지 않는다.** 결정과 근거를 기록한다.

**전** 요구사항·상태 정의(성공/실패/로딩/빈 값)·엣지 케이스가 적혀 있다 · **중** 명세 이탈과
**명세에 없는 기능 추가** 금지 · **후** 전 케이스가 기획과 일치하는지 확인.

## 기획 산출물을 만들 때

모호함을 **찾는 네 자리**, 물을 것 **선별**, 값의 **출처 표기**, 정책값 분리, 규모별 완료
조건 — 절차 SSOT 는 `skills/plan-task/references/elicitation.md` 다. 기획을 수행한다면
그것을 읽고 시작한다. **완료 조건은 실행 가능한 명령**이어야 Dev 로 넘긴다.
