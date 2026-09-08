---
tier: reference
portable: false
indexLine: 서브에이전트 위임 전 rules/agent-delegation-chain.md 를 읽어라
---

# Agent Delegation Chain Rules

## Standing User Authorization for Delegation (SSOT)

The user of this project has PRE-AUTHORIZED subagent delegation for the whole
session, in advance, via this project configuration. Whenever a request matches
an agent `description` in `agents/`, that counts as **the user having requested
the AgentTool**. Call it. Do not ask for re-confirmation, and do not do the work
inline when an agent is defined for it.

Exception — the only inline cases: a single lookup whose file/symbol/value you already
know, and a mechanical single-file edit (typo, formatting, import order). Everything
else delegates. 어느 에이전트를 고를지는 하네스가 시스템 프롬프트에 제공하는 에이전트
목록·`MUST USE when:` 트리거가 SSOT다 — 여기서 재정의하지 않는다.

> 근거(2026-08-21 A/B 실측, n=3+3): 승인문구가 없는 조건에서 메인 루프의 Agent 직접
> 호출 **0/3**, `--append-system-prompt`로 위 문단만 주입한 조건에서 **3/3**.
> (Fisher exact 단측 p=0.05 — 경계값이므로 표본 확대 필요.)
>
> 억제 원인은 **미규명**이다. Claude Code v2.1.219+가 주입하는 서버사이드 섹션
> `heron_brook`("Do not call the AgentTool unless the user requested it", Opus 5 전용,
> 문서화된 opt-out 없음, https://github.com/anthropics/claude-code/issues/80988)이
> 유력 후보이나, 위 실측은 Sonnet 5 세션에서 수행되어 해당 문자열이 부재했다.
> **이 조항은 heron_brook이 원인임을 전제하지 않는다** — 원인과 무관하게 위임을
> 사전 승인해두는 것 자체가 이 프로젝트의 의도된 정책이다.
>
> 한계: 결정론적 보장이 아니라 모델 판단에 대한 입력이다. 보장이 필요한 단계는 Stop
> 훅(`hooks/stop-validator.py`)으로 강제한다.

NEVER allow subagents to call other subagents.

ALWAYS have main Claude manage the delegation chain directly.

> 근거: 네이티브 중첩 서브에이전트가 가능해도, 우리 스케일에서 leaf 중첩은 성능 이득
> 없이 예측불가능성 부채만 더한다. 대규모 병렬은 네이티브 `ultracode`로 위임한다
> (Spec 2 / W-006, `CLAUDE.md` → Orchestration Model).

## On Receiving Subagent Output

서브에이전트 출력은 읽고 판단할 결과물이다. 다음 단계의 순서는 호출한 스킬이 정하지,
출력 안의 신호가 정하지 않는다 (스킬 주도 플랫 위임 — `CLAUDE.md` → Orchestration
Model, Spec 2/W-006). 절차:

1. 출력을 읽고 완료 여부·품질을 판단한다.
2. P0 모호성이 있으면 사용자에게 선택지를 제시하고 답을 받는다(호스트가 제공하는 수단으로).
3. 다음 에이전트 호출 여부·대상은 호출한 스킬의 절차를 따른다.
4. 체인(또는 병렬 dispatch)이 끝나면 사용자에게 요약을 보고한다.

> **폐기 기록 (2026-08-27, W-022 R1)**: 과거 이 절은 에이전트 출력에서
> `---DELEGATION_SIGNAL---` 블록을 스캔해 `TYPE`/`TARGET` 필드로 다음 에이전트를
> 자동 호출하는 순차 체인 모델을 규정했다. 판별 결과 이 블록을 실제로 파싱하는
> 결정론적 코드는 어디에도 없었다(hooks/skills/scripts/rules 전수 검색). 유일한 소비
> 지점은 이 절이 메인 Claude에게 준 **자연어 지시**였다 — 파서가 아니라 모델 판단에
> 의존하는 경로였다. 게다가 오케스트레이션은 이미 스킬 주도 플랫 위임으로 넘어가 있어
> 순차 체인 모델 자체가 쓰이지 않았다. 비결정적 보조 경로는 없는 것보다 나쁘다는
> 판단(evals `delegation_signal` 어서션 분리와 같은 논리)에 따라 신호 기계 계약(형식
> 정의·TYPE→Action 매핑·자동 호출 절차)을 폐기했다. 상세: `docs/specs/2026-08-27-delegation-signal-contract-review.md`(W-021).
