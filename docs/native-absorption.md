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
> 근거 인용은 **커밋된 자산**(CHANGELOG 버전·`docs/specs/` 경로)만 — 내부 작업 ID(`W-…`·`Spec n`)는 풀리지 않으므로 쓰지 않는다.
> 셀 안의 `|` 는 코드 스팬 안에서도 `\|` 로 이스케이프한다(GFM 은 코드 스팬 안의 파이프로도 열을 가른다).
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
| `adopt(pilot)` | 네이티브를 파일럿으로 채택 중 — 결과에 따라 `native-adopted` 또는 `watch` 로 확정 |
| `absorbed(partial)` | 네이티브가 일부 구간만 흡수 — 나머지는 kit 유지 |
| `decide` | 기술 조건은 풀렸고 방침이 사용자 결정 대기 — 결정 전에는 배포물을 바꾸지 않는다 |

## 대조표

| kit 컴포넌트 | 네이티브 프리미티브 | 상태 | 근거 / 확인일 |
| --- | --- | --- | --- |
| 서브에이전트 위임 (15 agents, v5.0.0) | Agent tool / subagent 정의 (`agents/*.md`) | `native-adopted` | 에이전트는 네이티브 서브에이전트 규격의 정의 파일 — kit는 페르소나·도구 큐레이션만. v5.0.0 에서 32→15: 네이티브 대응물이 있거나(아래 행) 어떤 스킬도 부르지 않는 17종 제거, 일상 표현 트리거 제거 (spec: `docs/specs/2026-09-28-v5-slimming/spec.md` §B) |
| worktree 격리 병렬 실행 | `isolation: worktree` | `native-adopted` | 네이티브 worktree 격리 사용, kit는 merge-back 룰(`rules/parallel-worktree.md`)만 |
| 자동수정 마이크로루프 | Stop hook `decision:block` | `native-adopted` | stop-validator가 네이티브 블로킹 규격으로 재진입 유도 |
| 훅 실행 인프라 | native hooks (exec form, `${CLAUDE_PLUGIN_ROOT}`) | `native-adopted` | kit는 훅 '내용'만 소유, 실행·수명주기는 네이티브 |
| 에이전트 수명주기 관측 (`agent-lifecycle.py`) | OpenTelemetry agent spans + `/usage` | `superseded` | 2.6.0 배치에서 제거 (CHANGELOG [2.6.0] Removed, spec: `docs/specs/2026-06-13-native-foundation.md`) |
| 기획 정련 깊이 (`plan-task` + `clarify-requirements`) | (네이티브 대응물 없음) — 외부 선행 사례: dryforge `ready` | `kit-only` | 2026-09-15 조사(`docs/research/2026-09-15-dryforge-evaluation.md`) 결과 **도구가 아니라 설계를 흡수**. v3.35.0 에서 탐색 4자리·질문 선별·출처 3분류·실행 가능한 완료 조건을 `skills/plan-task/references/elicitation.md` 로 도입. 미흡수 잔여: `grounds-gate`(요구사항별 3근거 필터) · `intent-completeness` 독립 검증 |
| 스킬 자동 발동 차단 (수동 전용 지정) | `disable-model-invocation` frontmatter | `native-adopted` | **2026-09-28 재판정(v5.0.0)**: 공식 문서(code.claude.com/docs/en/skills)가 SKILL.md 지원과 효과를 명시한다 — *"Description not in context, full skill loads when you invoke"*. 즉 상시 비용이 실제로 준다. 아래 옛 판정의 두 미검증(지원·효과)이 모두 해소돼 `using-hiway-kit`·`harness-export`·`skill-forge` 에 적용. Codex/OpenAI 쪽은 모르는 키가 경고로 무시된다. 옛 판정 — 2026-09-17 실측: Anthropic 공식 플러그인은 **`commands/` 에서만** 사용(`code-review`), **`skills/` 사용 사례 0건**. dryforge 가 스킬에 쓰지만 제3자 사용은 지원 근거가 아니다. 또한 이 플래그가 **스킬 description 을 로스터에서 빼는지 `[미확인]`** — 빼지 않으면 상시 비용 절감 효과가 0이다. **지원·효과 양쪽이 미검증이라 도입하지 않는다.** 공식 문서가 skills 지원을 명시하거나 실측되면 재평가 — 우리 수동 전용 스킬 5종(`native-watch`·`eval-forge`·`harness-export`·`skill-forge`·`self-improve`)이 후보 |
| 컴팩션 후 규범 복원 | `SessionStart` matcher `compact` / `PostCompact` | `native-adopted` | 2026-09-20 실측: 우리 `hooks.json` 이 이미 `matcher: "startup\|clear\|compact"` 다. compact 페이로드로 훅을 직접 실행해 startup 과 **바이트 동일한** 출력(sha 일치, RULES·WORKFLOW·LESSONS 전부 포함)을 확인했다 — **구멍이 아니었다.** 경쟁 하네스(Xastra)가 `PostCompact` 훅으로 하는 것을 우리는 SessionStart 재발화로 이미 한다. 단 그 불변식을 지키는 테스트가 없어 이번에 추가 |
| 서브에이전트 계약 전파 | `SubagentStart` 훅 | `decide` | 2026-09-20: Claude Code 에 `SubagentStart`/`SubagentStop` 이 **존재**하나, 공식 문서의 "Decision Control by Event" 표에 **없어 반환 규약(`additionalContext` 지원 여부)이 미명시**다. 우리는 `child-session` 스킬 + 마커로 하고 있고 훅 강제는 없다. **지원이 문서로 확인되거나 실측되기 전에는 배포물에 넣지 않는다** — `disable-model-invocation` 과 같은 판정. 실측하려면 프로젝트/전역 설정에 프로브 훅을 걸어야 하는데 그건 소비자 환경을 건드리는 일이라 보류 **2026-10-05 갱신**: 공식 훅 레퍼런스(code.claude.com/docs/en/hooks)가 `SubagentStart` 의 `hookSpecificOutput.additionalContext`(문맥 전용·차단 불가)를 명시하고 Decision Control 표에 등재했다 — «문서 확인 전에는 넣지 않는다» 조건은 해소. 2.1.265(2026-09-08)는 SubagentStart 문맥이 캐시 접두부를 깨던 결함도 고쳤다. 남은 것은 방침(자동 주입 vs 명시적 위임 호출) — 사용자 결정 `D-SubagentStart`(spec: `docs/specs/2026-10-05-audit-remediation/spec.md`), 기본값은 하지 않음 |
| eval 측정 축 기록·검증 | (네이티브 대응물 없음) — 외부 선행: Xastra `run_model.py` 가 세션 JSONL 을 되읽어 실제 사용 모델·effort 를 검증하고 불일치 시 `invalid` 로 배제 | `kit-only` | 2026-09-20 흡수(v3.38.0). 우리 리포트에 **어느 모델로 돌았는지 기록이 없어** baseline 비교가 «같은 것을 셌는가»를 답할 수 없었다(`warning-signal.md` §측정 7). `model` 을 결과·summary 에 싣고 `compare_baseline` 이 축 불일치를 회귀로 잡는다. 축 **미지**는 회귀가 아니라 stderr notice — 구 baseline 에서 상시 참이 되어 옆의 진짜 회귀를 죽이기 때문(§검토 1·3). 미흡수 잔여: **실제 사용 모델을 응답에서 되읽는 것**(우리는 요청값만 기록한다 — 서버측 폴백은 여전히 안 보인다) |
| 코드베이스 탐색 에이전트 (`explore-codebase`) | 내장 `Explore` 서브에이전트 | `superseded` | v5.0.0 제거. 내장 Explore 가 같은 일을 읽기 전용·저비용으로 하고, 우리 에이전트의 "분석해줘"·"탐색" 트리거는 일상 요청을 빼돌렸다 (spec: `docs/specs/2026-09-28-v5-slimming/spec.md` §B) |
| 구현 계획 에이전트 (`plan-implementation`, 흡수: `plan-refactor`·`design-services`) | 내장 `Plan` 서브에이전트 · plan mode | `watch` | v5.0.0: 셋을 하나로. `plan-task` 스킬이 부르는 계획 산출(`docs/plans/`) 계약이 있어 유지 — 내장 Plan 은 파일 산출 계약이 없다. 내장 Plan 이 산출물 계약을 받으면 흡수 후보 |
| 코드 리뷰 (`/review` 스킬 + `review-code`·`security-scan` 에이전트) | `/code-review`(effort·`--fix`·`ultra`) · `/security-review` · `/simplify` | `watch` | 2026-09-28 확인: 네이티브가 정확성 리뷰·보안 리뷰·정리를 제공한다. 우리 `/review` 는 **Claude Code 가 아닌 하네스(Codex)** 에서도 같은 리뷰 경로를 주려고 유지하되 v5.0.0 에서 설명 과장·중복 블록을 걷어냈다. Claude Code 사용자에게는 네이티브가 우선 |
| 스킬 생성 (`skill-creator`) | 공식 skill-creator 스킬 · Codex 내장 스킬 생성 | `superseded` | v5.0.0 제거 — 공식 스킬이 템플릿·평가까지 제공하고, 우리 것은 소비자에게 없는 `plugins/{domain}/` 경로로 쓰게 했다 |
| MCP 서버 스캐폴딩 (`mcp-builder`) | 공식 mcp-builder 스킬 · MCP SDK 문서 | `superseded` | v5.0.0 제거 — SDK 릴리스마다 예시가 낡는 부채(4.0.1 에서 한 번 고쳤고 다시 낡았다) |
| 문서 공동 작성 (`doc-coauthoring`) | (범용 모델 능력) | `superseded` | v5.0.0 제거 — 일반 템플릿이었고, 서술한 자동 문서 갱신 트리거는 실재하지 않았다 |
| 에이전트 생성 (`agent-creator`) | `/agents` | `watch` | v5.0.0: 소비자 `.claude/agents/` 로 쓰게 고침. **2026-10-05 정정**: `/agents` 대화형 마법사는 Claude Code 2.1.198(2026-07-01)에서 제거됐다 — 지금 네이티브 경로는 «Claude 에게 요청하거나 `.claude/agents/` 를 직접 편집»이다(공식 sub-agents 문서). 우리 것은 그 위에 frontmatter 검증 관례만 얹는다. 킷 자체 에이전트 추가는 이 스킬이 아니라 `CLAUDE.md` «Adding a New Agent» |
| 대규모 병렬 오케스트레이션 (구 agent-teams 자체 조율) | `ultracode` (dynamic workflow) | `superseded` | agent-teams 스킬은 네이티브 라우팅 안내로 대체 (spec: `docs/specs/2026-06-13-orchestration.md`). 단 스킬발 자동 트리거는 여전히 불가 — 모델 호출형 Workflow 도구는 존재하나 사용자 opt-in 게이트(세션 실측 2026-07-07). 자동 위임은 Task+스킬 루프 유지 **2026-10-05 갱신**: «스킬발 자동 트리거 불가» 는 일부 낡았다 — 플러그인이 `workflows/` 를 컴포넌트로 싣고 `/<plugin>:<name>` 으로 실행하는 경로가 공식화됐고(docs/en/workflows), `Workflow(<name>)` allow 규칙이면 `-p`·SDK 에서도 돈다. `/goal` 도 `-p` 에서 동작한다. 사용자 opt-in(키워드·이름 호출·allow 규칙) 게이트는 그대로. 킷이 워크플로를 배포하는 것은 `watch` — 이번 라운드 미채택(Claude 전용이고 오케스트레이션 모델 변경이라 별도 결정) |
| 주기 실행/스케줄링 | `/schedule` (routines) | `native-adopted` | kit 자체 스케줄러 구현 금지 — zero-debt (spec: `docs/specs/2026-07-07-toolkit-improvement-batch.md`). /native-watch도 네이티브 경로만 안내 |
| 계획 파일 (`docs/plans/<날짜>-<slug>/plan.md` + checklist.json) | native TaskCreate/TaskList | `watch` | 4.0.0: Work 시스템(ID·단계 폴더·관리 스크립트)을 제거하고 계획 파일 한 장으로 줄였다. 네이티브 Tasks 는 보조로만 쓴다 — 완료를 verify 명령 결과로 막지 못하고 Codex 등 다른 하네스엔 영속 태스크가 없다. 네이티브가 verify-gated 완료를 제공하면 checklist 흡수 후보 (spec: `docs/specs/2026-09-28-plans-replace-works/`) **2026-10-05 정정**: 네이티브 Task 도구(TaskCreate/Get/List/Update·TodoWrite)는 Claude Code 2.1.233(2026-08-14)~2.1.268(2026-09-10)부터 Claude 3.x·Opus 4–4.7·Sonnet 4–4.6·Haiku 4.5 에서만 기본 제공된다(그 외 `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`; 공식 tools-reference «Task tool availability»). 현재 기본 모델에서는 «보조»도 기본 비활성이고, `plan-task`·`auto-dev`·`brainstorming` 의 Task 경로는 대체 경로(`skills/plan-task/references/task-tools-fallback.md`)로만 돈다 |
| feedback ledger (상한·중복제거·감쇠) | native memory + Auto Dream (research preview) | `kit-only` | 2026-07-07 /native-watch: Auto Dream(메모리 병합·모순 제거·인덱스 상한)이 research preview로 등장 — 동일 계열이나 GA 아님. GA 시 재평가, 그전까지 ledger 유지 (spec: `docs/specs/2026-06-13-feedback-memory.md`) |
| Agent Evals (`evals/`) | Skills 2.0 evals (스킬 대상, 부분) | `adopt(pilot)` | 2026-07-07 /native-watch: skill-creator에 스킬-대상 evals/A-B 등장했으나 **범용 에이전트 행동 평가 프리미티브는 부재** — kit evals 유지 (spec: `docs/specs/2026-07-07-toolkit-improvement-batch.md`). 네이티브 범용 evals 출시 시 최우선 흡수 후보. 2026-08-27 확인: 티어1 커버리지 4/33 → 13/13, 시나리오⇄기준선 드리프트 게이트(`scripts/check_eval_coverage.py`) 신설(spec: `docs/specs/2026-08-26-eval-coverage-and-gates.md`) — 판정(`kit-only`) 자체는 불변, kit 쪽 커버리지·게이트 성숙도만 갱신 **2026-10-05 재판정(`kit-only`→`adopt(pilot)`)**: `claude plugin eval`(Claude Code 2.1.269=2026-09-11, 공식 docs/en/plugin-evals)이 «범용 행동 평가 프리미티브 부재» 전제를 깼다 — 케이스·그레이더·무플러그인 baseline 대비 Δ·`--max-cost-usd`. 상보적이다: 우리 `evals/` 는 에이전트 단위 시나리오·기준선 회귀, 네이티브는 플러그인 단위 스킬 발동. 스킬 발동 eval 은 우리 공백이라 `plugins/common/evals/` 파일럿(spec: `docs/specs/2026-10-05-audit-remediation/spec.md` D15). 파일럿 결과로 확정 |
| multi-perspective-review (10 관점 합의) | ultracode judge panel 패턴 | `watch` | 부분 겹침 — 사용자 opt-in 게이트라 스킬 체인 내 자동 실행은 kit 유지(2026-07-07 재확인). 네이티브 패널이 스킬에서 트리거 가능해지면 재평가. 2026-10-05: 네이티브 워크플로 문서가 «독립 에이전트의 적대적 상호 검증» 패턴과 `/deep-research` 를 싣는다 — 부분 겹침 심화, 상태 유지 |
| 스킬 자동 주입 (session-start WORKFLOW/LESSONS) | SessionStart hook additionalContext | `native-adopted` | 네이티브 훅 규격 사용, 내용만 kit 소유 |
| 시크릿 커밋 차단 | gitleaks + pre-commit (외부 도구) | `kit-only` | 네이티브 무관 — 외부 표준 도구 조합 |
| Definition-of-Done 기계 게이트 (`scripts/verify-done.sh`) | (대응 네이티브 없음) | `kit-only` | 완료 판정을 명령 출력으로 강제하는 게이트 — 네이티브 대응물 부재 (2026-07-07 확인) |
| 재귀 개선 루프 (`/self-improve`) — v5.0.0 부터 이 레포 전용(`.claude/skills/`) | Auto Dream (research preview, 메모리 한정) | `kit-only` | Auto Dream은 메모리 정리 한정 — 정의 파일 개선 제안 루프는 네이티브 부재. Auto Dream GA·확장 시 재평가 (2026-07-07 확인) |
| 하네스 중립 규범 배포 (`/harness-export` → `AGENTS.md`) | (대응 네이티브 없음 — CC는 자기 세션만 주입) | `decide` | 2026-08-23 ADE 벤치마킹(spec: `docs/specs/2026-08-22-ade-benchmark-absorption.md`): Orca·Paseo가 한 레포에 다중 하네스를 붙이는 것이 표준이 됨. CC의 SessionStart 주입은 CC 세션에만 걸리므로 구멍. `AGENTS.md`는 Codex·OpenCode·Copilot·Cursor 공통 사실상 표준 — 네이티브 대응물 부재 **2026-10-05 부분 정정**: Claude Code 2.1.277(2026-09-18)부터 CLAUDE.md 가 없으면 AGENTS.md 를 직접 읽는다(docs/en/memory#agents-md) — «대응 네이티브 없음» 은 *읽는 쪽*에서 틀렸다. *내보내는 쪽*은 여전히 kit 구현이다. 부작용: CLAUDE.md 없는 소비자 + export 된 AGENTS.md → Claude Code 가 그것을 읽고 SessionStart 훅이 같은 규범을 또 주입한다(이중 도달). 처리 방침은 사용자 결정 `D-AGENTS-dup`(기본값: 문서만) |
| eval 시나리오 포징 (`/eval-forge`) — v5.0.0 부터 이 레포 전용(`.claude/skills/`) | Skills 2.0 evals (스킬 대상, 부분) | `kit-only` | 2026-08-23 ADE 벤치마킹: 위 `Agent Evals` 행과 동일 판정 — 범용 에이전트 행동 evals 프리미티브 부재. 포징 도구는 그 위의 커버리지 확장 수단이며 네이티브 대응물 없음 2026-10-05: `claude plugin eval init` 이 케이스·그레이더를 자동 초안한다 — 스킬 발동 케이스 한정으로 겹침. 위 `Agent Evals` 파일럿과 함께 재검토 |
| 성공 trajectory → 스킬 승격 (`/skill-forge`) | Hermes Agent의 자동 스킬 생성 (외부 하네스) / Auto Dream (research preview, 메모리 한정) | `kit-only` | 2026-08-23 ADE 벤치마킹: Hermes가 이 계열의 선행 사례이나 **다른 하네스의 기능**이지 CC 네이티브가 아님. CC 네이티브는 skill-creator(수동)까지 — trajectory 기반 자동 승격 프리미티브 부재. Auto Dream GA·확장 시 재평가 |
| 다중 하네스 패키지 배포 (Codex `.codex-plugin/`·Antigravity `plugin.json`) | Codex Plugin / Antigravity Plugin 네이티브 매니페스트 규격 | `native-adopted` | 2026-08-26(spec: `docs/specs/2026-08-26-multi-harness-packaging.md`): kit는 각 플랫폼의 플러그인 런타임을 재구현하지 않고, 그 플랫폼이 이미 읽는 매니페스트 포맷만 생성한다(`scripts/build-targets.py`). **현재 사실(2026-10-05 감사 A 실측, codex 0.159.3·agy 1.2.17)**: 에이전트는 양쪽 다 서브에이전트로 쓰이지 않는다 — Codex 는 플러그인 번들 에이전트 필드가 없고, Antigravity 는 5.3.0 평탄화 뒤에도 0개를 인식한다(원인은 레이아웃이 아니라 `model: haiku\|sonnet\|opus` frontmatter; `inherit`·생략은 인식). Codex 훅은 `hooks-codex.json` 으로 배포되며 마켓플레이스 설치에서 SessionStart 주입이 돈다(디렉토리 ZIP 은 훅 없음). 기록 위치: `packaging/targets.json`, `docs/specs/2026-10-05-audit-remediation/audit/A-harness.md`. 2026-08-26 당시의 «에이전트 33개·카테고리 중첩·Codex 훅 미로드» 서술은 대체됐다 |
| 완료 조건 루프 (`stop-validator`·`auto-dev` 검증 루프) | `/goal` (세션 범위 prompt 기반 Stop 훅 래퍼, `-p` 지원) | `watch` | 2026-10-05(공식 docs/en/goal): 평가자는 **명령·파일을 직접 실행하지 않고 대화에 드러난 것만 판정**한다 — «DoD = 명령 출력» 게이트(`verify-done.sh`)를 대체하지 못하고 보완 관계 |
| 멀티세션 위임 운송 (`control-loop`·`docs/control-loop-transport.md`) | `SendMessage`/`ListAgents`(Claude Code 2.1.224~), agent teams(실험) | `watch` | 2026-10-05(공식 cross-session-messaging): 텍스트만·권한 승인 불가. 우리 운송은 하네스 중립(Claude↔Codex↔…)이라 유지. agent teams 는 여전히 실험·기본 꺼짐 |
| 주입 예산·스킬 품질 점검 (`scripts/check_injection_budget.py`·`self-improve`) | `claude plugin details <name>`(always-on 토큰 추정), `/skill-doctor`(2.1.261), `/doctor prompt-audit`(2.1.283) | `watch` | 2026-10-05 실측: `claude --plugin-dir plugins/common plugin details hiway-kit` → Skills 15·Agents 15·Hooks 4, always-on ~3,568 tok — **훅이 주입하는 규범·WORKFLOW 는 이 수치에 불포함**이라 우리 게이트와 합쳐 읽는다 |
| (대응 없음 — 킷 훅은 Python 외부 프로세스) | Claude Mods(2.1.287=2026-10-01): JS/TS 함수 훅으로 도구 호출·프롬프트·UI 를 가로챔 | `watch` | 2026-10-05: Claude Code 전용·터미널/Desktop 한정. 킷은 하네스 중립·Python 3.9 floor·fail-open 이라 채택하지 않는다 |
| 완료 직전 검증 습관 (`verify-done.sh`·DoD 룰) | `verify` 스킬 관례(2.1.286=2026-09-30): 프로젝트·개인 `verify`/`simplify` 스킬이 있으면 커밋 직전 실행 안내(플러그인 스킬은 해당 없음) | `watch` | 2026-10-05(공식 skills 문서): 같은 방향이나 소비자가 프로젝트 `.claude/skills/verify` 를 직접 둬야 발동 — 킷은 소비자 레포에 쓰지 않는다 |
| 비신뢰 텍스트 규율 중 서브에이전트 결과 (`rules/untrusted-text.md`) | 서브에이전트 결과 «subagent output» 헤더·지시문 모양 스캔(2.1.210·2.1.277) | `absorbed(partial)` | 2026-10-05: 서브에이전트 결과 구간만 네이티브가 덮는다. 웹·메모리·타세션 텍스트 규율은 kit 유지 |
| 매니페스트 신규 기능 중 킷 미사용분 | `dependencies`(semver)·`claude plugin tag`(`<name>--v<version>`)·`userConfig`·디렉토리 listing 키·에이전트 `omitClaudeMd`·스킬 `context: fork`/`paths`/`when_to_use` | `watch` | 2026-10-05: 킷 태그는 `vX.Y.Z` 라 다른 플러그인이 킷에 버전 범위로 의존하면 해소 불가(`hiway-kit--vX.Y.Z` 필요) — 의존 사례가 생기면 재검토. listing 키는 2.1.281(2026-09-23)부터 `claude plugin validate` 가 경고하지 않는다(로컬 2.1.289 `--strict` rc=0) |

## 전수 검토 기록

최신순.

| 날짜 | 검토자 | 변경 |
| --- | --- | --- |
| 2026-10-05 | 감사 C 외부 동향 조사 (/native-watch 절차, 기준 v5.3.0) + 5.4.0 반영 | Claude Code 2.1.257~2.1.289 전수 대조(`docs/specs/2026-10-05-audit-remediation/audit/C-research.md` §8). 재판정 `Agent Evals` kit-only→`adopt(pilot)`, 정정 2(`/agents` 마법사 제거·Task 도구 기본 비활성), `decide` 2(SubagentStart·AGENTS.md 이중 도달), 갱신(워크플로·multi-perspective·eval-forge·다중 하네스), 신규 7행. 상태 3종(`adopt(pilot)`·`absorbed(partial)`·`decide`) 정의 추가. 작업 ID 를 스펙 경로로 치환 |
| 2026-10-05 | 5.3.0 에이전트 평탄화 | 다중 하네스 행: 에이전트 15개가 `agents/` 최상위로. Antigravity 의 에이전트 미인식 원인이 레이아웃이 아니었음을 감사 A 가 확인(위 행) |
| 2026-09-30 | 5.1.0~5.2.0 | 스킬 도구를 `hooks/` → `tools/` 로 분리(OpenAI 포털이 `hooks/` 를 거부) — 하네스 중립 규범 배포 행의 도구 위치. 5.1.0 아키텍처 경계 강제는 네이티브 대응물 없음(행 추가 없음) |
| 2026-09-28 | 4.0.0 계획 파일 규약 | 계획 파일 행 갱신 — Work 시스템을 걷어내고 `docs/plans/<날짜>-<slug>/plan.md` 로 교체(`docs/specs/2026-09-28-plans-replace-works/`) |
| 2026-09-28 | v5.0.0 전수 감사 (컨트롤) | 네이티브 대조가 빠져 있던 7행 추가(Explore·Plan·`/code-review` 계열·skill-creator·mcp-builder·doc-coauthoring·`/agents`). `disable-model-invocation` 을 공식 문서 근거로 `watch`→`native-adopted`. 에이전트 개수 33→15 정정. 이 표가 에이전트 한 행으로만 뭉뚱그려 개별 에이전트↔네이티브 대조를 한 번도 하지 않은 것이 이번 감사가 찾은 사각지대였다 |
| 2026-08-26 | 다중 하네스 패키지 배치 (`docs/specs/2026-08-26-multi-harness-packaging.md`) | 신규 1행 추가(다중 하네스 패키지 배포). Codex·Antigravity 네이티브 플러그인 규격을 실물 CLI로 검증 후 흡수. **범위 한계도 실측으로 확정해 같은 배치에서 문서화** — 양쪽 다 `agents/` 1급 미지원, Codex 훅 exec form 미로드(스펙 §5.5, 초안이 실측과 어긋났던 것을 정정) |
| 2026-08-23 | ADE 벤치마킹 (v2.14.0, `docs/specs/2026-08-22-ade-benchmark-absorption.md`) | 외부 ADE/하네스 3종(Orca·Paseo·Hermes) 대조 후 신규 3행 추가. **앱 레이어(병렬 플릿 UI·터미널·모바일·디프 뷰어)는 명시적 비목표로 확정** — 네이티브 `isolation: worktree`·`ultracode`가 이미 흡수했고 나머지는 플러그인이 복제할 영역이 아님 |
| 2026-07-07 | /native-watch 첫 실행 (v2.10.1) | 8행 watch 격상(cross-session Tasks 신호), 9·10행 근거 갱신(Auto Dream·Skills 2.0), 6·11행 확인일/뉘앙스, 신규 2행(DoD 게이트·self-improve). 호환성 경고 0건 |
| 2026-07-07 | v2.10.0 배치 (초기 역기입) | 기존 결정(CHANGELOG [2.3.0-계획→2.6.0]·[2.10.0], specs 참조) 역기입, 초기 13행 작성 |
