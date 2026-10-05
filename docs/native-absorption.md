---
status: current
as_of: 2026-10-05
---

# Native Absorption Ledger — 네이티브 흡수 대조표 (SSOT)

> **목적**: "기술부채의 최대 원천은 Claude Code가 네이티브로 하는 일을 자체 구현으로
> 중복하는 것"(README 설계 철학). 이 표는 kit 컴포넌트 ↔ 네이티브 프리미티브의 대응과
> 흡수 상태를 추적하는 단일 원장이다. `/native-watch` 스킬이 주기적으로 이 표를
> 릴리스 노트와 대조해 갱신을 제안한다.
>
> **갱신 규칙**: 상태 변경은 근거(릴리스 노트/문서 링크 + 확인일)와 함께. 표를 고치면
> 관련 결정을 CHANGELOG 또는 spec에 기록한다. 마지막 전수 검토일을 하단에 남긴다.
> 근거 인용은 **커밋된 자산**(CHANGELOG·docs/specs)만 — gitignore된 Work 문서 ID 금지.
>
> **정직한 한계**: 이 표의 최신성(freshness)은 기계 게이트로 강제되지 않는다 —
> `/native-watch`의 주기 실행(수동 /schedule 설정)에 의존한다. 전수 검토일이 오래됐다면
> 그만큼 신뢰를 낮춰 읽어라.

## 상태 정의

| 상태 | 의미 |
| --- | --- |
| `native-adopted` | 네이티브 프리미티브를 그대로 사용 — kit는 콘텐츠/정책만 얹음 |
| `kit-only` | 네이티브 대응물 없음(또는 요구 미충족) — kit 자체 구현 유지, watch 대상 |
| `superseded` | 네이티브가 흡수 완료 — kit 구현이 제거되었거나 위임-안내로 축소됨 (역사 기록; 파일 존속 가능) |
| `watch` | 네이티브가 부분 대응 — 성숙도를 관찰 중, 흡수 후보 |

## 대조표

| kit 컴포넌트 | 네이티브 프리미티브 | 상태 | 근거 / 확인일 |
| --- | --- | --- | --- |
| 서브에이전트 위임 (15 agents, v5.0.0) | Agent tool / subagent 정의 (`agents/*.md`) | `native-adopted` | 에이전트는 네이티브 서브에이전트 규격의 정의 파일 — kit는 페르소나·도구 큐레이션만. v5.0.0 에서 32→15: 네이티브 대응물이 있거나(아래 행) 어떤 스킬도 부르지 않는 17종 제거, 일상 표현 트리거 제거 (spec: `docs/specs/2026-09-28-v5-slimming/spec.md` §B) |
| worktree 격리 병렬 실행 | `isolation: worktree` | `native-adopted` | 네이티브 worktree 격리 사용, kit는 merge-back 룰(`rules/parallel-worktree.md`)만 |
| 자동수정 마이크로루프 | Stop hook `decision:block` | `native-adopted` | stop-validator가 네이티브 블로킹 규격으로 재진입 유도 |
| 훅 실행 인프라 | native hooks (exec form, `${CLAUDE_PLUGIN_ROOT}`) | `native-adopted` | kit는 훅 '내용'만 소유, 실행·수명주기는 네이티브 |
| 에이전트 수명주기 관측 (`agent-lifecycle.py`) | OpenTelemetry agent spans + `/usage` | `superseded` | 2.6.0 배치에서 제거 (CHANGELOG [2.6.0] Removed, Spec 1 / W-005) |
| 기획 정련 깊이 (`plan-task` + `clarify-requirements`) | (네이티브 대응물 없음) — 외부 선행 사례: dryforge `ready` | `kit-only` | 2026-09-15 조사(`docs/research/2026-09-15-dryforge-evaluation.md`) 결과 **도구가 아니라 설계를 흡수**. v3.35.0 에서 탐색 4자리·질문 선별·출처 3분류·실행 가능한 완료 조건을 `references/elicitation.md` 로 도입. 미흡수 잔여: `grounds-gate`(요구사항별 3근거 필터) · `intent-completeness` 독립 검증 |
| 스킬 자동 발동 차단 (수동 전용 지정) | `disable-model-invocation` frontmatter | `native-adopted` | **2026-09-28 재판정(v5.0.0)**: 공식 문서(code.claude.com/docs/en/skills)가 SKILL.md 지원과 효과를 명시한다 — *"Description not in context, full skill loads when you invoke"*. 즉 상시 비용이 실제로 준다. 아래 옛 판정의 두 미검증(지원·효과)이 모두 해소돼 `using-hiway-kit`·`harness-export`·`skill-forge` 에 적용. Codex/OpenAI 쪽은 모르는 키가 경고로 무시된다. 옛 판정: | 2026-09-17 실측: Anthropic 공식 플러그인은 **`commands/` 에서만** 사용(`code-review`), **`skills/` 사용 사례 0건**. dryforge 가 스킬에 쓰지만 제3자 사용은 지원 근거가 아니다. 또한 이 플래그가 **스킬 description 을 로스터에서 빼는지 `[미확인]`** — 빼지 않으면 상시 비용 절감 효과가 0이다. **지원·효과 양쪽이 미검증이라 도입하지 않는다.** 공식 문서가 skills 지원을 명시하거나 실측되면 재평가 — 우리 수동 전용 스킬 5종(`native-watch`·`eval-forge`·`harness-export`·`skill-forge`·`self-improve`)이 후보 |
| 컴팩션 후 규범 복원 | `SessionStart` matcher `compact` / `PostCompact` | `native-adopted` | 2026-09-20 실측: 우리 `hooks.json` 이 이미 `matcher: "startup|clear|compact"` 다. compact 페이로드로 훅을 직접 실행해 startup 과 **바이트 동일한** 출력(sha 일치, RULES·WORKFLOW·LESSONS 전부 포함)을 확인했다 — **구멍이 아니었다.** 경쟁 하네스(Xastra)가 `PostCompact` 훅으로 하는 것을 우리는 SessionStart 재발화로 이미 한다. 단 그 불변식을 지키는 테스트가 없어 이번에 추가 |
| 서브에이전트 계약 전파 | `SubagentStart` 훅 | `watch` | 2026-09-20: Claude Code 에 `SubagentStart`/`SubagentStop` 이 **존재**하나, 공식 문서의 "Decision Control by Event" 표에 **없어 반환 규약(`additionalContext` 지원 여부)이 미명시**다. 우리는 `child-session` 스킬 + 마커로 하고 있고 훅 강제는 없다. **지원이 문서로 확인되거나 실측되기 전에는 배포물에 넣지 않는다** — `disable-model-invocation` 과 같은 판정. 실측하려면 프로젝트/전역 설정에 프로브 훅을 걸어야 하는데 그건 소비자 환경을 건드리는 일이라 보류 |
| eval 측정 축 기록·검증 | (네이티브 대응물 없음) — 외부 선행: Xastra `run_model.py` 가 세션 JSONL 을 되읽어 실제 사용 모델·effort 를 검증하고 불일치 시 `invalid` 로 배제 | `kit-only` | 2026-09-20 흡수(v3.38.0). 우리 리포트에 **어느 모델로 돌았는지 기록이 없어** baseline 비교가 «같은 것을 셌는가»를 답할 수 없었다(`warning-signal.md` §측정 7). `model` 을 결과·summary 에 싣고 `compare_baseline` 이 축 불일치를 회귀로 잡는다. 축 **미지**는 회귀가 아니라 stderr notice — 구 baseline 에서 상시 참이 되어 옆의 진짜 회귀를 죽이기 때문(§검토 1·3). 미흡수 잔여: **실제 사용 모델을 응답에서 되읽는 것**(우리는 요청값만 기록한다 — 서버측 폴백은 여전히 안 보인다) |
| 코드베이스 탐색 에이전트 (`explore-codebase`) | 내장 `Explore` 서브에이전트 | `superseded` | v5.0.0 제거. 내장 Explore 가 같은 일을 읽기 전용·저비용으로 하고, 우리 에이전트의 "분석해줘"·"탐색" 트리거는 일상 요청을 빼돌렸다 (spec §B) |
| 구현 계획 에이전트 (`plan-implementation`, 흡수: `plan-refactor`·`design-services`) | 내장 `Plan` 서브에이전트 · plan mode | `watch` | v5.0.0: 셋을 하나로. `plan-task` 스킬이 부르는 계획 산출(`docs/plans/`) 계약이 있어 유지 — 내장 Plan 은 파일 산출 계약이 없다. 내장 Plan 이 산출물 계약을 받으면 흡수 후보 |
| 코드 리뷰 (`/review` 스킬 + `review-code`·`security-scan` 에이전트) | `/code-review`(effort·`--fix`·`ultra`) · `/security-review` · `/simplify` | `watch` | 2026-09-28 확인: 네이티브가 정확성 리뷰·보안 리뷰·정리를 제공한다. 우리 `/review` 는 **Claude Code 가 아닌 하네스(Codex)** 에서도 같은 리뷰 경로를 주려고 유지하되 v5.0.0 에서 설명 과장·중복 블록을 걷어냈다. Claude Code 사용자에게는 네이티브가 우선 |
| 스킬 생성 (`skill-creator`) | 공식 skill-creator 스킬 · Codex 내장 스킬 생성 | `superseded` | v5.0.0 제거 — 공식 스킬이 템플릿·평가까지 제공하고, 우리 것은 소비자에게 없는 `plugins/{domain}/` 경로로 쓰게 했다 |
| MCP 서버 스캐폴딩 (`mcp-builder`) | 공식 mcp-builder 스킬 · MCP SDK 문서 | `superseded` | v5.0.0 제거 — SDK 릴리스마다 예시가 낡는 부채(4.0.1 에서 한 번 고쳤고 다시 낡았다) |
| 문서 공동 작성 (`doc-coauthoring`) | (범용 모델 능력) | `superseded` | v5.0.0 제거 — 일반 템플릿이었고, 서술한 자동 문서 갱신 트리거는 실재하지 않았다 |
| 에이전트 생성 (`agent-creator`) | `/agents` | `watch` | v5.0.0: 소비자 `.claude/agents/` 로 쓰게 고침. 네이티브 `/agents` 가 대화형 생성을 제공 — 우리 것은 frontmatter 검증 관례만 얹는다 |
| 대규모 병렬 오케스트레이션 (구 agent-teams 자체 조율) | `ultracode` (dynamic workflow) | `superseded` | agent-teams 스킬은 네이티브 라우팅 안내로 대체 (Spec 2 / W-006). 단 스킬발 자동 트리거는 여전히 불가 — 모델 호출형 Workflow 도구는 존재하나 사용자 opt-in 게이트(세션 실측 2026-07-07). 자동 위임은 Task+스킬 루프 유지 |
| 주기 실행/스케줄링 | `/schedule` (routines) | `native-adopted` | kit 자체 스케줄러 구현 금지 — zero-debt (spec: `docs/specs/2026-07-07-toolkit-improvement-batch.md`). /native-watch도 네이티브 경로만 안내 |
| 계획 파일 (`docs/plans/<날짜>-<slug>/plan.md` + checklist.json) | native TaskCreate/TaskList | `watch` | 4.0.0: Work 시스템(ID·단계 폴더·work.sh)을 제거하고 계획 파일 한 장으로 줄였다. 네이티브 Tasks 는 보조로만 쓴다 — 완료를 verify 명령 결과로 막지 못하고 Codex 등 다른 하네스엔 영속 태스크가 없다. 네이티브가 verify-gated 완료를 제공하면 checklist 흡수 후보 (spec: `docs/specs/2026-09-28-plans-replace-works/`) |
| feedback ledger (상한·중복제거·감쇠) | native memory + Auto Dream (research preview) | `kit-only` | 2026-07-07 /native-watch: Auto Dream(메모리 병합·모순 제거·인덱스 상한)이 research preview로 등장 — 동일 계열이나 GA 아님. GA 시 재평가, 그전까지 ledger 유지 (Spec 3 / W-007) |
| Agent Evals (`evals/`) | Skills 2.0 evals (스킬 대상, 부분) | `kit-only` | 2026-07-07 /native-watch: skill-creator에 스킬-대상 evals/A-B 등장했으나 **범용 에이전트 행동 평가 프리미티브는 부재** — kit evals 유지 (spec: `docs/specs/2026-07-07-toolkit-improvement-batch.md`). 네이티브 범용 evals 출시 시 최우선 흡수 후보. 2026-08-27 확인: 티어1 커버리지 4/33 → 13/13, 시나리오⇄기준선 드리프트 게이트(`scripts/check_eval_coverage.py`) 신설(W-018) — 판정(`kit-only`) 자체는 불변, kit 쪽 커버리지·게이트 성숙도만 갱신 |
| multi-perspective-review (10 관점 합의) | ultracode judge panel 패턴 | `watch` | 부분 겹침 — 사용자 opt-in 게이트라 스킬 체인 내 자동 실행은 kit 유지(2026-07-07 재확인). 네이티브 패널이 스킬에서 트리거 가능해지면 재평가 |
| 스킬 자동 주입 (session-start WORKFLOW/LESSONS) | SessionStart hook additionalContext | `native-adopted` | 네이티브 훅 규격 사용, 내용만 kit 소유 |
| 시크릿 커밋 차단 | gitleaks + pre-commit (외부 도구) | `kit-only` | 네이티브 무관 — 외부 표준 도구 조합 |
| Definition-of-Done 기계 게이트 (`scripts/verify-done.sh`) | (대응 네이티브 없음) | `kit-only` | 완료 판정을 명령 출력으로 강제하는 게이트 — 네이티브 대응물 부재 (2026-07-07 확인) |
| 재귀 개선 루프 (`/self-improve`) — v5.0.0 부터 이 레포 전용(`.claude/skills/`) | Auto Dream (research preview, 메모리 한정) | `kit-only` | Auto Dream은 메모리 정리 한정 — 정의 파일 개선 제안 루프는 네이티브 부재. Auto Dream GA·확장 시 재평가 (2026-07-07 확인) |
| 하네스 중립 규범 배포 (`/harness-export` → `AGENTS.md`) | (대응 네이티브 없음 — CC는 자기 세션만 주입) | `kit-only` | 2026-08-23 ADE 벤치마킹(W-017): Orca·Paseo가 한 레포에 다중 하네스를 붙이는 것이 표준이 됨. CC의 SessionStart 주입은 CC 세션에만 걸리므로 구멍. `AGENTS.md`는 Codex·OpenCode·Copilot·Cursor 공통 사실상 표준 — 네이티브 대응물 부재 |
| eval 시나리오 포징 (`/eval-forge`) — v5.0.0 부터 이 레포 전용(`.claude/skills/`) | Skills 2.0 evals (스킬 대상, 부분) | `kit-only` | 2026-08-23 W-017: 위 `Agent Evals` 행과 동일 판정 — 범용 에이전트 행동 evals 프리미티브 부재. 포징 도구는 그 위의 커버리지 확장 수단이며 네이티브 대응물 없음 |
| 성공 trajectory → 스킬 승격 (`/skill-forge`) | Hermes Agent의 자동 스킬 생성 (외부 하네스) / Auto Dream (research preview, 메모리 한정) | `kit-only` | 2026-08-23 W-017: Hermes가 이 계열의 선행 사례이나 **다른 하네스의 기능**이지 CC 네이티브가 아님. CC 네이티브는 skill-creator(수동)까지 — trajectory 기반 자동 승격 프리미티브 부재. Auto Dream GA·확장 시 재평가 |
| 다중 하네스 패키지 배포 (Codex `.codex-plugin/`·Antigravity `plugin.json`) | Codex Plugin / Antigravity Plugin 네이티브 매니페스트 규격 | `native-adopted` | 2026-08-26 W-019: kit는 각 플랫폼의 플러그인 런타임을 재구현하지 않고, 그 플랫폼이 이미 읽는 매니페스트 포맷만 생성한다(`scripts/build-targets.py`). 양쪽 다 실물 CLI로 설치·인식 확인(`codex plugin marketplace add`→`list`, `agy plugin validate`→`install`→`list`). **범위 한계(실측 확정)**: 양쪽 플랫폼 모두 `agents/`(33) 1급 미지원(Codex는 전용 필드 없음, Antigravity는 `agy`가 카테고리 중첩을 재귀하지 않음) — kit 구조를 바꾸지 않고 사실대로 문서화(스펙 §5.5). Codex 훅(exec form)은 로드 안 됨을 직접 실측 확정, 편입 보류 |

## 전수 검토 기록

| 날짜 | 검토자 | 변경 |
| --- | --- | --- |
| 2026-09-28 | v5.0.0 전수 감사 (컨트롤) | 네이티브 대조가 빠져 있던 7행 추가(Explore·Plan·`/code-review` 계열·skill-creator·mcp-builder·doc-coauthoring·`/agents`). `disable-model-invocation` 을 공식 문서 근거로 `watch`→`native-adopted`. 에이전트 개수 33→15 정정. 이 표가 에이전트 한 행으로만 뭉뚱그려 개별 에이전트↔네이티브 대조를 한 번도 하지 않은 것이 이번 감사가 찾은 사각지대였다 |
| 2026-07-07 | /native-watch 첫 실행 (v2.10.1) | 8행 watch 격상(cross-session Tasks 신호), 9·10행 근거 갱신(Auto Dream·Skills 2.0), 6·11행 확인일/뉘앙스, 신규 2행(DoD 게이트·self-improve). 호환성 경고 0건 |
| 2026-08-26 | 다중 하네스 패키지 배치 (W-019) | 신규 1행 추가(다중 하네스 패키지 배포). Codex·Antigravity 네이티브 플러그인 규격을 실물 CLI로 검증 후 흡수. **범위 한계도 실측으로 확정해 같은 배치에서 문서화** — 양쪽 다 `agents/` 1급 미지원, Codex 훅 exec form 미로드(스펙 §5.5, 초안이 실측과 어긋났던 것을 정정) |
| 2026-08-23 | ADE 벤치마킹 (W-017, v2.14.0) | 외부 ADE/하네스 3종(Orca·Paseo·Hermes) 대조 후 신규 3행 추가. **앱 레이어(병렬 플릿 UI·터미널·모바일·디프 뷰어)는 명시적 비목표로 확정** — 네이티브 `isolation: worktree`·`ultracode`가 이미 흡수했고 나머지는 플러그인이 복제할 영역이 아님 |
| 2026-07-07 | v2.10.0 배치 (초기 역기입) | 기존 결정(CHANGELOG [2.3.0-계획→2.6.0]·[2.10.0], specs 참조) 역기입, 초기 13행 작성 |
