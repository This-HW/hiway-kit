---
tier: core
portable: true
---

# Loop Engineering Rule (Spec 5 / W-009)

**얼마나 오래·끈질기게** 행동하는가. 게이트(설계 — 사람 승인, **의도적 멈춤**:
brainstorming/plan-task HARD-GATE) ≠ 루프(실행 — 승인된 계획을 P0·완료·가드 도달
전까지 자율 완주, 매 단계 확인 없이). 루프는 게이트를 우회하지 않는다.

## 드라이버 (검증된 Task 시스템 + 스킬 루프, 자체 데몬 없음 — 대화형 전용 네이티브 트리거는 스킬에서 못 쓴다)

`while(미완료 Work/Task):` 재앵커(요약이 아닌 `planning-results.md` 원본 재확인 — 요약은
drift한다) → unblocked Task 선택 → 실행 → 완료 시 checklist pass → `progress.md` 래칫 →
`TaskUpdate(completed)` → 종료 가드 점검(아래) → 확인 없이 다음 unblocked로 → 완료 보고.

## 종료 가드 (안티-런어웨이 = 필수)

**P0**(데이터/보안/결제/핵심로직 모호 → 선택지 제시, 호스트 수단으로) · **완료**(검증
게이트 green + 수동 DoD attest + 배치 전체 Work/Task 해소, `definition-of-done.md` —
"마지막 스텝 도달"≠완료) · **max_iterations/루프 감지**(동일 Task 무진전 반복 상한/2회+
→ 에스컬레이션·중단 보고) · **idle**(N iteration 새 커밋 0건 → 종료, git 커밋 기준) ·
**검증 실패 잔존**(가드 재시도 후에도 실패 → 보고) 에서 반드시 멈춘다.

`auto-dev` 배치는 Work 완료 시 자동 전진, 단발 실행은 루프 없음 — opt-in, 루프 실패가
본 작업을 막지 않는다.
