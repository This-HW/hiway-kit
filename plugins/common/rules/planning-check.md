---
tier: core
portable: true
---

# Planning Check Rules

NEVER implement based on assumption. ALWAYS stop and verify specs first — 요구사항
불명확, 엣지 케이스(빈 값·오류·권한 없음), 다중 해석 가능한 표현, 비즈니스 로직
(할인·권한·상태 전이)은 반드시 기획서/명세 기반으로 확인한다.

## 확인 절차

불확실성 감지 즉시 멈춤 → 프로젝트의 기획 문서를 찾는다(레포 내 `docs/` 및 프로젝트가
제공하는 지식 소스 — **특정 도구의 설치를 가정하지 않는다**) → 정보 부재 시 사용자에게
상황·불명확한 점·옵션 A/B 를 제시하고 답을 받는다(호스트가 제공하는 수단으로) →
결정과 근거를 코드 주석에 기록.

체크리스트 — 구현 전: 요구사항 문서·상태 정의(성공/실패/로딩/빈 값)·엣지 케이스 명시.
구현 중: NEVER guess/deviate from spec/add unspecified features. 구현 후: 결과가
기획과 전 케이스 일치.
