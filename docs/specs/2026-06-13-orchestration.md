# Orchestration 설계 (Spec 2)

**Goal:** 오케스트레이션을 스케일별로 올바른 네이티브 프리미티브에 위임하고, 실험적·수동인 자체 중복(agent-teams)을 제거하여, 기술부채 없이 대규모 작업의 성능 천장을 없앤다.

**Architecture:** 오케스트레이션 성능 천장은 *대규모 병렬*에서만 실재한다. Small/Medium은 스킬 주도 플랫 위임이 이미 최적이고 예측가능하다(중첩은 이득 0 + 부채). Large(10~100+ 에이전트)는 네이티브 dynamic workflow 엔진이 main 컨텍스트를 소비하지 않고 백그라운드 오케스트레이션한다 — 손으로 만든 orchestrator 에이전트나 agent-teams보다 우월. 따라서 leaf 에이전트는 Task를 갖지 않으며(전통이 아니라 스케일상 부채이므로), 대규모만 네이티브 workflow에 위임한다.

**Version:** 2.3.0 → 2.4.0 (minor bump, 엄격한 하위호환) — Spec 1(2.3.0) 이후

**Depends on:** Spec 1 (Native Foundation) — 매니페스트/관측 토대 위에서 검증.

> **구현 노트 (2026-06-13):** VG-W 검증 결과 네이티브 dynamic workflow가 대화형 전용
> (스킬 트리거 불가)으로 확인되어, 본 스펙은 "알려진 가변 지점"의 축소 시나리오로
> 구현됨 — 네이티브 workflow 자동 위임 대신 agent-teams를 `ultracode` 수동 가이드로
> 재정의 + auto-dev Large 청크 라우팅 안내. 상세: W-006 `decisions.md` DEC-001.

---

## 요구사항

1. 대규모 병렬 작업을 네이티브 dynamic workflow 엔진에 위임하는 경로를 만든다.
2. 실험적·수동 조율인 `agent-teams` 스킬을 네이티브 workflow 래퍼로 재정의(또는 deprecate)한다.
3. `auto-dev`가 작업 규모(Small/Medium/Large)에 따라 오케스트레이션 경로를 자동 선택한다.
4. leaf 에이전트의 플랫 정책을 유지하되, CLAUDE.md에 근거를 "스케일별 프리미티브"로 재서술한다.
5. `---DELEGATION_SIGNAL---` 컨벤션은 유지하고 문서/포맷을 표준화한다(네이티브 대체재 없음).
6. 모든 변경은 하위호환 — 네이티브 workflow 미지원 환경에서 기존 수동 dispatch로 graceful degradation.

## 접근 방식

**스케일별 네이티브 프리미티브 + 자체 중복 삭제.**
- Small/Medium → 현행 스킬 주도 플랫 위임 유지(무변경).
- Large → 네이티브 dynamic workflow 위임.
- 자체 agent-teams → 네이티브 래퍼로 축소 또는 deprecate.

기각된 대안:
- 통제된 2-tier(orchestrator 에이전트에 Task 허용): 우리 스케일에서 성능 이득 없이 예측불가능성·디버깅 부채. 대규모는 native workflow가 더 잘 처리.
- delegation-signal 네이티브 교체: 깔끔한 네이티브 대체 프리미티브 부재 → 교체가 오히려 부채.

## 컴포넌트 구조

### 검증 게이트 (코딩 전 선행 — research-external)
- **VG-W1**: 네이티브 dynamic workflow(`ultracode`/`/workflows`) 트리거 방법 — 스킬/비대화형(-p)에서 호출 가능 여부
- **VG-W2**: workflow 결과 수신 방식 — 완료 신호, 산출물 회수 경로
- **VG-W3**: workflow와 우리 Work 시스템(progress.md/Task) 통합 가능성 — 상태 동기화 패턴
- 검증 결과에 따라 아래 구조가 조정될 수 있음(설계의 알려진 가변 지점)

### 변경 1 — auto-dev 스케일 라우팅
- 대상: `plugins/common/skills/auto-dev/SKILL.md`
- 추가: Step 2(Development 실행)에서 Work `size` 확인 →
  - Small/Medium → 현행 병렬 dispatch(무변경)
  - Large → 네이티브 workflow 위임 경로
- Large 경로의 진입/결과수신/progress.md 동기화는 VG-W1~3 결과 반영

### 변경 2 — agent-teams 재정의
- 대상: `plugins/common/skills/agent-teams/SKILL.md`
- 네이티브 dynamic workflow의 thin 래퍼/가이드로 재작성 — 실험적 수동 조율 절차 제거
- 네이티브가 케이스를 완전히 흡수하면 deprecate 명시(스킬 유지하되 "네이티브 workflow 사용" 안내)

### 변경 3 — CLAUDE.md 오케스트레이션 모델 재서술
- 대상: `CLAUDE.md` (Sub-agent Rules / Agent Architecture 섹션)
- "main만 조율" → "스케일별 네이티브 프리미티브: Small/Medium 스킬 주도 플랫, Large 네이티브 workflow"
- leaf 에이전트 `disallowedTools: [Task]` 유지 근거 명문화(중첩 = 우리 스케일 부채)

### 변경 4 — delegation-signal 표준화
- 대상: `plugins/common/rules/agent-delegation-chain.md` + 에이전트 출력 포맷
- 포맷/필드 표준화 + 문서화. 동작 변경 없음(하위호환).

### 버전 bump
- `plugins/common/.claude-plugin/plugin.json` → 2.4.0
- 변경된 스킬 포함 플러그인 동기 bump

## 데이터 흐름

```
auto-dev Step 2 (Development)
  ├─ size ∈ {Small, Medium} → 현행: Agent(task) 병렬 dispatch → 결과 main 수집 → progress.md
  └─ size = Large → 네이티브 dynamic workflow 트리거 (백그라운드 10~100+ 에이전트)
                     → 완료 신호 수신 → 산출물/상태 회수 → progress.md 동기화
(미지원 환경) → Large도 현행 수동 dispatch로 graceful degradation
```

## 에러 처리

- 네이티브 workflow 미지원/실패 → 현행 수동 병렬 dispatch로 fallback(graceful degradation).
- workflow 부분 실패(일부 에이전트 실패) → 실패 Task만 재dispatch, 완료분 유지(현행 auto-dev 재시도 패턴 준용).
- VG-W3에서 상태 동기화 불가 판명 시 → Large 경로를 "수동 dispatch + 청크 분할"로 대체(스코프 축소, 부채 회피).

## 테스트 전략

- auto-dev 스케일 라우팅 분기 로직 검증(Small/Medium 무변경 회귀, Large 분기 진입).
- agent-teams 재작성 후 스킬 description/manifest 유효성(CI).
- CLAUDE.md/rules 문서 변경은 frontmatter/링크 무결성 확인.
- 수동 검증: Large 작업 1건을 네이티브 workflow로 실행 → progress.md 동기화 확인.

## 범위 외

- Hermes식 피드백 메모리 학습 루프 → **Spec 3**
- Spec 1 항목(매니페스트/훅/관측) → 완료 전제
- OpenClaw cron 자율성, superpowers 스킬 리포 분리 → 채택 안 함

## 알려진 가변 지점

VG-W1~3 검증 결과에 따라 변경 1·2의 구체 구현이 조정된다. 네이티브 workflow가 스킬/비대화형에서 트리거 불가하거나 Work 시스템과 통합 불가로 판명되면, Spec 2는 "auto-dev Large 경로의 청크 분할 + 수동 dispatch 최적화"로 축소하고 agent-teams만 deprecate한다(여전히 부채 제거 + 무위험).
