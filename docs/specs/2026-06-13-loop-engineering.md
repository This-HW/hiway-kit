# Loop Engineering 설계 (Spec 5)

**Goal:** 승인된 계획을 P0 의사결정이나 완료 조건 도달 전까지 자율로 완주하는 "실행 루프" 레이어를 추가하여, 매 단계마다 멈추는 문제를 해소한다. Harness Engineering(어디서·무엇으로)의 상보 개념인 Loop Engineering(얼마나 오래·끈질기게)을 toolkit에 명문화한다.

**Architecture:** 루프 드라이버를 자체 데몬으로 만들지 않는다. 네이티브 프리미티브를 조립한다 — `/goal`(완료조건 지속), `continueOnBlock`(검증 마이크로루프, Spec 1), dynamic workflow(대규모 병렬, Spec 2), background/session_crons/ScheduleWakeup(장기·자기페이싱), Task+progress.md(진행 래칫). 핵심 안티-부채/안티-런어웨이 장치는 **종료 가드**(max iterations·P0-only stop·비용 인지)다. 설계 게이트(사람 승인)와 실행 루프(자율 완주)를 명확히 분리한다.

**Version:** 2.5.0 → 2.6.0 (minor bump, 엄격한 하위호환)

**Depends on:** Spec 1(continueOnBlock), Spec 2(workflow) — 루프 조각 제공. Spec 1·2 완료 후 통합이 자연스러움.

> **구현 노트 (2026-06-13):** VG-L 검증 결과 `/goal`이 대화형 전용으로 확인되어,
> 루프 드라이버는 `/goal` 대신 auto-dev 자체 while 루프 + TaskList 폴링 + progress.md
> 래칫으로 구현됨(자체 데몬 없음). 핵심 산출물인 `rules/loop-engineering.md`(게이트 vs
> 루프 규율)는 그대로. 상세: W-009 `decisions.md` DEC-001.

---

## 요구사항

1. "실행 루프" 개념을 정의하고 toolkit 규율에 명문화한다(게이트 vs 루프 구분).
2. 승인된 배치(여러 Work/Task)를 자율로 완주하는 드라이버를 제공한다 — 한 Work 완료 시 다음 unblocked Work로 자동 전진.
3. 완료 조건을 명시적으로 정의하고 네이티브 `/goal`로 구동한다.
4. 종료 가드(max iterations·P0 에스컬레이션·비용 인지)로 런어웨이를 차단한다.
5. P0(진짜 의사결정)·완료·가드 도달 시에만 사람에게 멈춘다.
6. 기존 단발 실행과 하위호환 — 루프는 opt-in.

## 접근 방식

**네이티브 프리미티브 조립 + 종료 가드.**
- 루프 드라이버: `/goal` 기반 완료조건 + Task/progress.md 래칫.
- 검증 마이크로루프: continueOnBlock(Spec 1).
- 대규모: dynamic workflow(Spec 2).
- 장기/자기페이싱: ScheduleWakeup / background.
- 안전: 종료 가드.

기각된 대안:
- 자체 루프 데몬/스케줄러: 네이티브 `/goal`·`loop`·cron으로 충분 → 신규 인프라는 부채.
- "항상 자율"(게이트 제거): 설계 승인 게이트는 의도된 안전장치 → 유지. 루프는 *실행* 단계만.

## 컴포넌트 구조

### 검증 게이트 (코딩 전 선행 — research-external)
- **VG-L1**: `/goal` 완료조건 시맨틱 — 스킬/비대화형에서 설정·평가 가능 여부, 평가자 발화 조건
- **VG-L2**: `loop` 스킬 / Ralph Loop / ScheduleWakeup의 자율 재invoke 패턴과 한계
- **VG-L3**: 종료 가드를 어디에 둘지 — 훅(Stop) vs 스킬 로직 vs `/goal` 자체 한계

### 변경 1 — 신규 룰: `rules/loop-engineering.md`
- Harness vs Loop 개념 정의
- 게이트(설계, 사람 멈춤) vs 루프(실행, 자율 완주) 구분 명문화
- "승인 후에는 P0·완료·가드 전까지 멈추지 말 것" 규율
- session-start.py ALWAYS_RULES에 추가

### 변경 2 — auto-dev 배치 완주 드라이버
- 대상: `plugins/common/skills/auto-dev/SKILL.md`
- 배치 모드: 여러 Work가 계획됐을 때, 한 Work의 validation 통과 → 다음 unblocked Work로 자동 전진(사람 확인 없이) → 배치 완료 조건까지 반복
- 완료 조건: 모든 계획 Work `completed` 또는 P0/가드 도달
- 진행 래칫: TaskList unblocked 폴링 + progress.md

### 변경 3 — 종료 가드
- 대상: auto-dev 루프 로직 + (필요시) Stop 훅
- max_iterations 카운터(Work 배치 단위), 초과 시 사람 에스컬레이션
- P0 감지 시 즉시 루프 탈출 → 사람 질문(AskUserQuestion)
- 비용 인지: 장기 루프는 ScheduleWakeup 자기페이싱으로 분할

### 변경 4 — 신규 스킬(선택): `auto-loop` 또는 auto-dev 확장
- VG 결과에 따라: 독립 `auto-loop` 스킬 신설 vs auto-dev 내 배치 모드로 흡수
- 기본 권고: **auto-dev 내 배치 모드로 흡수**(신규 스킬 = 표면적↑ = 부채). 독립 스킬은 VG에서 필요성 입증 시에만.

### 버전 bump
- `plugins/common/.claude-plugin/plugin.json` → 2.6.0

## 데이터 흐름

```
[승인된 배치: W-a, W-b, W-c]  (설계 게이트 통과 완료)
        │
        ▼  /goal: "배치 완료 조건" 설정
  ┌─────────────────────────────────────────┐
  │ auto-dev 배치 루프                        │
  │   while (미완료 Work 존재 && !P0 && iter<MAX):│
  │     unblocked Work 선택 → auto-dev 실행    │
  │       ├─ validation continueOnBlock 마이크로루프 (Spec 1)│
  │       └─ Large면 dynamic workflow (Spec 2)│
  │     완료 → progress.md 래칫 → 다음 Work     │
  └─────────────────────────────────────────┘
        │
   ┌────┴────┬──────────┐
   ▼         ▼          ▼
 완료      P0 도달     가드 초과
 보고    AskUserQ    에스컬레이션
```

## 에러 처리

- P0 모호함 → 즉시 루프 탈출, AskUserQuestion(런어웨이 방지의 핵심 분기).
- max_iterations 초과 → 진행 상황 보고 + 사람 판단 요청.
- Work 실패(validation 미통과) → 해당 Work에서 정지, 배치 전체는 보고 후 사람 결정.
- 네이티브 `/goal` 미지원 → 단발 실행으로 graceful degradation(루프 비활성).
- 비용 폭주 위험 → ScheduleWakeup 자기페이싱 + iter 카운터 이중 가드.

## 테스트 전략

- 배치 루프 단위: 3개 Work 배치 → 순차 자동 전진 → 완료 보고 (mock).
- 가드: max_iterations 초과 시 에스컬레이션 검증.
- P0 분기: P0 감지 시 루프 탈출 + AskUserQuestion 호출 검증.
- 하위호환: 단발 `/auto-dev W-XXX`는 기존 동작 유지(루프 미발동).
- 수동: 실제 2-Work 배치 자율 완주 1회.

## 범위 외

- 무인 24/7 자율 운영(OpenClaw식) — 종료 가드 있는 세션 내 루프까지만.
- 크로스-세션 영속 루프 상태(session_crons 깊은 통합) — 차기.

## 알려진 가변 지점

VG-L1~3 결과로 변경 4(독립 스킬 vs auto-dev 흡수)와 변경 3(가드 위치)이 확정된다. `/goal`이 스킬/비대화형에서 완전히 동작하면 드라이버를 `/goal` 중심으로, 제한적이면 auto-dev 자체 while 루프 + TaskList 폴링 중심으로 구현한다(어느 쪽도 자체 데몬 없이 네이티브/기존 인프라만 사용).
