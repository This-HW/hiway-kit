---
status: current
as_of: 2026-11-21
---

# hiway-kit 설계 개념 (한국어)

5.9.0 에서 영문 단일로 정리한 [README](../README.md) 에 있던 한국어 절(Architecture & Concepts ·
핵심 개념 & AI 엔지니어링 로직 · Works with your MCPs)을 내용을 잃지 않게 옮긴 문서다. 옮기면서
사실과 어긋난 두 곳만 고쳤고, 고친 자리에 그 사실을 적었다.

## Architecture & Concepts

hiway-kit이 무엇을 어떻게 융합하는지 — 한눈에 보는 설계 원리.

### 설계 철학 — 네이티브 우선, kit은 의견 레이어

> **기술부채의 최대 원천은 Claude Code가 네이티브로 하는 일을 자체 구현으로 중복하는 것이다.**

네이티브 프리미티브(agents·skills·hooks·dynamic workflows·OTEL·memory)는 거의 매주
진화한다. 그래서 이 kit의 가치는 **인프라가 아니라, 그 위에 얹는 "의견이 담긴
에이전트·스킬·규율 레이어"** 다. 관측·위임·훅 실행 같은 인프라는 네이티브에 위임하고,
손으로 만든 대체물은 삭제한다 → zero-debt.

### 네 갈래의 융합

| 갈래 | 무엇을 가져왔나 | kit에서 |
| --- | --- | --- |
| **Claude Code 네이티브** | agents, skills, hooks, dynamic workflow, OTEL, memory | 토대 프리미티브 — 매니페스트 의존성, exec-form 훅, `decision:block` 자동수정, 네이티브 관측 |
| **개발 방법론 규율** | brainstorming→plan→execute, phase gate, TDD, verification-before-completion | `brainstorming → plan-task → auto-dev` HARD-GATE 체인, Iron Law 검증 |
| **Hermes 피드백 루프** | "메모리·피드백 루프가 코어" | validation 결함 → feedback ledger → 다음 구현 컨텍스트 주입 (학습 루프) |
| **계획 파일 규약** | 파일 기반 진행 추적 | `docs/plans/<slug>/plan.md`·checklist.json — 포맷은 [`plan-format.md`](../plugins/common/skills/plan-task/references/plan-format.md) |

### Harness × Loop Engineering

두 상보 개념이 kit의 자율성을 만든다:

- **Harness Engineering** — *어디서·무엇으로* 행동하는가. 컨텍스트 주입(session-start),
  도구 큐레이션(per-agent tools), 가드레일(protect-sensitive·stop-validator), 계획 파일(plan.md·checklist).
- **Loop Engineering** — *얼마나 오래·끈질기게* 행동하는가. 승인된 배치를 P0·완료·가드
  전까지 자율 완주. 게이트(설계·사람 멈춤)와 루프(실행·자율)를 분리한다.

### 결합 방식

![계획 승인 뒤 배치 실행이 진행되고, 검증에서 확인한 결함이 다음 세션에 주입되는 흐름](architecture/diagrams/harness-loop/harness-loop.svg)

승인된 배치는 P0 모호함, 완료 또는 종료 가드에 닿을 때까지 진행한다. 독립 청크는 스킬이
플랫 위임하고, 많은 병렬 청크를 가진 Large 계획은 사용자가 네이티브 workflow를 선택할 수
있도록 `auto-dev`가 안내한다. 검증에서 발견한 결함은 feedback ledger에 기록하며, 다음
세션 시작에 LESSONS로 들어갈 수 있다. Claude Code의 Stop 훅은 변경 파일의 린트와 수정된
테스트를 확인하는 별도의 안전망이다.

2026-11-21에 옛 README의 작업 크기별 오케스트레이션 분기를 병렬 청크 기준으로 고쳤다.
Large 계획에서 네이티브 workflow를 안내하는 구체적인 조건은 `auto-dev`의 Large 라우팅을 따른다.

세부는 SSOT 문서 참조: [CLAUDE.md](../CLAUDE.md) (오케스트레이션·규율),
[docs/specs/](specs/) (설계 스펙), `plugins/common/rules/` (규칙).

## 핵심 개념 & AI 엔지니어링 로직

kit에 녹아 있는 개념과 그 장점 — *어떻게* 구현되는지와 함께.

| 개념 / 로직 | kit에서 어떻게 | 장점 |
| --- | --- | --- |
| **Native-first (zero-debt)** | 네이티브 프리미티브를 최대 활용하고 자체 중복 구현은 삭제 | 유지보수 부채 0, 네이티브가 진화해도 항상 최신 |
| **Phase-gate discipline** | `brainstorming → plan-task → auto-dev` HARD-GATE 체인 | P0 모호성을 0 으로 만든 뒤 구현 → 재작업·헛수고 최소화 |
| **Verification-before-completion (DoD)** | Iron Law + `scripts/verify-done.sh` 기계 게이트 | 증거 없는 "완료" 주장을 구조적으로 차단 |
| **경계 검사의 완료 조건화** | 프로젝트에 경계 검사 도구(import-linter·dependency-cruiser 등)가 있으면 계획의 `## 완료 조건` 으로 태운다 — [`boundary-check.md`](../plugins/common/skills/plan-task/references/boundary-check.md) | 설계로 정한 모듈 경계가 다음 변경에서 조용히 깨지는 것을 명령으로 막음 (도구가 없으면 없다고 적고 도입은 사용자 결정) |
| **Loop engineering** | 게이트(사람 멈춤) vs 루프(자율 완주) 분리 + 배치 드라이버 + 종료 가드 | P0 전까지 자율 완주, 런어웨이 방지 |
| **Feedback learning loop** (Hermes) | validation 결함 → ledger(상한·중복제거·감쇠) → 다음 세션 `=== LESSONS ===` 주입 | 같은 실수를 반복하지 않음 |
| **Scale-appropriate orchestration** | 병렬 청크 수 개는 스킬 주도 플랫 dispatch, 10~100+ 는 네이티브 workflow(사용자 opt-in) 안내 | 스케일별 최적, main 컨텍스트 병목 회피 |
| **Adversarial review** | `review-code`가 4 페르소나(hacker·murphy·future-self·picky-user)로 침투 검토 | 버그·엣지케이스를 능동 발굴 |
| **Multi-perspective deliberation** | 10 관점 × 3 라운드 합의(`/multi-perspective-review`) + devil's advocate | 설계 사각지대 제거 |
| **Agent specialization** | 전문 에이전트 × 모델 티어(Opus 전략 / Sonnet 구현 / Haiku 탐색) — 개수는 README 의 What's Included 표 | 작업별 최적 모델·비용 |
| **Worktree isolation** | 파일 수정 에이전트를 격리 git worktree에서 실행 | 병렬 작업 충돌 방지 |
| **Harness engineering** | 컨텍스트 주입(session-start)·도구 큐레이션·가드레일 훅·계획 파일 | 환경이 모델을 올바른 궤도로 유지 |
| **SSOT governance** | `rules/` + decisions 추적 + 거버넌스/시크릿 보호 훅 | 일관성·감사 가능성 |

> 심화 리서치 노트: [하네스 엔지니어링 & 루프 엔지니어링 — 2026 중반 지형도](research/2026-07-harness-loop-engineering.md)
> (개념 계보 · 3대 루프 구현체 · 검증 원칙 · 병렬 에이전트 도구 생태계 · kit 대조)

## Works with your MCPs (memory 등)

kit은 **특정 MCP 서버를 가정하지 않습니다** (consumer-first). 대신 세션에 있는 MCP를
일반화된 방식으로 활용합니다:

- **검색·문서형 MCP**: 규칙(`rules/mcp-usage.md`)이 설치돼 있으면 그것을 우선하고, 없거나
  실패하면 내장 도구로 돌아가라고 지시합니다. 설치 의무 없음.
- **메모리형 MCP** (`recall`/`search`/`remember` 류 툴 — [basic-memory](https://github.com/basicmachines-co/basic-memory),
  [agentcairn](https://github.com/ccf/agentcairn), 사내/개인 메모리 서버 등 무엇이든):
  설계 목표는 **계획 전 recall → 완료 후 remember** 패턴이다. 메모리 도구가 돌려준 내용은
  비신뢰 데이터로 다룬다(`rules/untrusted-text.md`).
- **충돌 없음**: kit 에이전트는 MCP 툴을 허용목록에 하드코딩하지 않습니다
  (`rules/mcp-usage.md`) — 어떤 MCP 조합에서도 환각·충돌 없이 동작합니다.
- 다른 플러그인·MCP와의 호환은 kit의 **명시적 설계 목표**입니다 — 함께 설치된 플러그인의
  존재를 가정하지도, 충돌하지도 않으며, 단독으로도 자급자족합니다.

> **고친 곳 2** (2026-11-21): 옛 README 는 *"kit 워크플로가 계획 전 recall → 완료 후 remember
> 패턴으로 **자동 활용합니다**"* 라고 적었다. 확인 결과 `plugins/` 의 스킬·규칙 어디에도 recall·remember
> 를 부르라는 지시가 없다(2026-11-21 `git grep -i remember -- plugins/` 0건). 그래서 *설계 목표* 로 고쳐
> 적었다. 이 패턴을 실제 절차로 넣는 일은 별도 결정이다.
