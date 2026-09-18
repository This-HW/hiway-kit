# Delegation Signal 계약 폐기 기록 (W-022 R1, 2026-08-27)

> **이미 제거된 기능의 역사 기록이다.** 운영 지시가 아니므로 상시 주입하지 않는다 —
> `CLAUDE.md` 가 한 줄로 가리킨다. 읽어야 할 때: 산문에서 `---DELEGATION_SIGNAL---`
> 잔재를 발견했거나, 비슷한 «모델 판단에 의존하는 기계 계약»을 새로 만들려 할 때.

## 무엇을 왜 폐기했나

과거 모든 에이전트는 출력 끝에 아래 블록으로 끝나야 했다:

```
---DELEGATION_SIGNAL---
TYPE: DELEGATE_TO | TASK_COMPLETE | NEED_USER_INPUT | NEED_CLARIFICATION
TARGET: [agent-name]
REASON: [reason]
CONTEXT: [handoff context]
---END_SIGNAL---
```

**왜 있었나.** 구 순차 체인 오케스트레이션 모델에서, 서브에이전트가 이 신호로 메인
Claude에게 다음 에이전트를 지목했다.

**왜 없앴나.** 판별 결과(W-021): **hooks·skills·scripts·rules 어디에도 이 블록을
파싱하는 결정론적 코드가 없었다.** 유일한 소비 지점은 `rules/agent-delegation-chain.md`가
메인 Claude에게 "신호 블록을 스캔해 TARGET이 있으면 다음 에이전트를 자동 호출하라"고
준 **자연어 지시**였다 — 파서가 아니라 모델 판단에 의존하는 경로였다는 점이 이 결론의
무게다. 게다가 오케스트레이션은 이미 §Orchestration Model의 스킬 주도 플랫 위임으로
넘어가 있었다 — 신호를 스캔해 다음 에이전트를 자동 호출하는 구 순차 체인 모델 자체가
더 이상 쓰이지 않았다.

이 조사를 시작하게 만든 트리거는 커버리지를 13종으로 넓히던 중(W-018) 드러난 준수율
관측이었다 — **8종 중 6종(75%)**이 이 마커를 간헐적으로 생략했다(`implement-code`
6/6·`plan-implementation` 2/2만 안정, `implement-api`는 모델·effort가 낮지 않은데도
실패해 "좋은 모델이면 안정" 가설을 반증했다). 단, 이 관측은 교란돼 있다 —
`implement-code` 시나리오의 `task.md`가 형식을 직접 지시했으므로 6/6은 대조군이
아니다. 무지시 준수 사례는 `plan-implementation` 2/2(n=2)뿐이다. 그럼에도 폐기
결론(B: 사문화) 자체는 이 통계가 아니라 위 두 근거로 유지된다 — 비결정적 보조 경로는
없는 것보다 나쁘다는 판단(이번 배치에서 evals `delegation_signal` 어서션을 분리한
것과 같은 논리)에 따라 폐기를 실행했다. 상세 근거:
`docs/specs/2026-08-27-delegation-signal-contract-review.md`(W-021).

**어디까지 걷어냈나** (다음 사람이 잔재를 찾을 때 기준):

- 에이전트 정의 33종 — 본문 `---DELEGATION_SIGNAL---` 블록 전부 제거
- 위 33종 중 32종의 frontmatter `OUTPUT:`/`MUST USE when:` — 신호 토큰만 제거,
  실제 산출물 서술과 무관한 트리거 문구는 보존. 산문 중 `DELEGATE_TO: git-workflow`
  같은 **에스컬레이션 의도 서술**은 기계 계약이 아니므로 그대로 유지
- `verify-done.sh` §12(에이전트 출력 계약 위치 검사) + CI 동등 스텝 — 제거. **번호 12는
  재사용하지 않고 비워 둔다** (아래 verify-done.sh 섹션 규약 참고 — 스펙·
  decision-log 47곳 이상이 섹션 번호로 게이트를 참조한다)
- 스킬 4종(`agent-creator`·`eval-forge`·`harness-export`·`skill-forge`)의 예시
  블록 — 제거. `agent-creator`는 특히 중요했다: 새 에이전트 템플릿에 블록이 박혀
  있어 폐기를 무효화할 수 있었다
- 주입 규칙 2종(`plugins/common/rules/agent-system.md`,
  `agent-delegation-chain.md`) — **외과적** 삭제. 신호 기계 계약(형식 정의·
  TYPE→Action 매핑·자동 호출 절차)만 제거하고, 무관한 정책(Standing User
  Authorization, "서브에이전트는 서브에이전트를 호출하지 않는다")은 보존.
  `On Receiving Subagent Output` 절은 삭제가 아니라 스킬 주도 모델에 맞게 재작성.
  해설본(`docs/architecture/rules/`)도 같은 원칙으로 갱신, CHECKSUMS/MIRROR 재생성
- eval `delegation_signal` 체크 타입 — 계약 폐기 시점에는 **삭제하지 않았다.**
  `implement-code`·`plan-implementation` 등 안정 통과 시나리오가 있어 체크 자체는
  유효하다고 판단했으나, 그 판단의 근거였던 시나리오 어서션은 **바로 그 배치에서
  이미 제거돼 있었다** — 판단 시점에 이미 사실이 아니었다. W-023(2026-08-31)이
  실사용 조사로 확인: 어서션 117건 중 `delegation_signal` 사용자 **0건**. 검사할
  대상이 없는 채로 남은 채점 코드는 계약이 아직 살아 있다는 잘못된 신호만 주므로,
  `KNOWN_ASSERTION_TYPES`·`check_assertion`(`evals/run.py`) 두 지점에서 제거했다
- 유지: 본문 산문의 `DELEGATE_TO: X` 같은 에스컬레이션 서술(기계 계약 아님),
  역사 기록(CHANGELOG, decision-log, 과거 spec)
