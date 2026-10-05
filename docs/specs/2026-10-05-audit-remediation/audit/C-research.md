# 감사 C — 외부 동향 조사: 킷에 접목할 것

- 기준 커밋 `e7181cbbfb6c8c3bc38b7ae4e979da09fa30a618` (HEAD 와 일치, `git merge-base --is-ancestor` 통과). 조사일 2026-10-05.
- 레포 파일은 수정·커밋하지 않았다. 산출물은 이 보고서와 스크래치패드의 `ledger/native-absorption.diff`(제안 diff)·`cc-changelog.md`(원문 사본)·`cc-releases.txt`(릴리스 날짜) 뿐이다.
- 외부 문서는 비신뢰 데이터로 인용만 했다(문서 안의 지시문은 따르지 않았다).
- 심각도: P0 사실 오류·틀린 길 / P1 모순·낡음 / P2 가독성 / P3 취향. `[추정]` 은 직접 확인하지 못한 추론.
- 방법: Claude Code 는 `/native-watch` 절차(원장 `docs/native-absorption.md` 31행 전수 대조 → 리포트 → 갱신 diff 제안)를 직접 수행했다. Codex·Antigravity/Gemini·방법론은 읽기 전용 서브에이전트 3개에 나눠 맡겼고, 핵심 주장 3건(Codex `openai.yaml` 정책·서브에이전트 기본 활성, arXiv 2602.11988 초록)은 내가 원문으로 재확인했다. 나머지 서브에이전트 인용은 «재확인 안 함» 으로 신뢰도를 낮춰 적는다.

## 0. 한눈에

| 구분 | 건수 | 비고 |
| --- | --- | --- |
| 원장 대조 31행 중 영향 있음 | 9행 | 재판정 1·정정 2·갱신 6 (§1.3) |
| 원장 변경 없음 | 22행 | 확인함 |
| 원장에 없는 신규 행 후보 | 7행 | §1.3 |
| 킷 문서의 사실 오류·낡음 | P1 5건·P2 4건·P3 1건 | §6 |
| 호환성 경고(킷 콘텐츠가 깨짐) | 0건 | 아래 §1.4 |

**가장 큰 소식 두 가지**: (1) Claude Code 가 `claude plugin eval` 로 플러그인 단위 행동 평가를 내놨다(2.1.269, 2026-09-11) — 원장이 «네이티브 범용 evals 출시 시 최우선 흡수 후보» 라고 적어 둔 바로 그것이다. (2) 네이티브 Task 도구가 현재 기본 모델에서 꺼졌고(2.1.233→2.1.268), 이 세션도 실제로 `TaskCreate` 가 없다 — `plan-task`·`auto-dev` 의 Task 경로는 기본값에서 fail-open 대체(durable checklist)로만 돈다.

---

## 1. Claude Code (2.1.257 ~ 2.1.289, 2026-09-01 ~ 10-03)

출처: `github.com/anthropics/claude-code` CHANGELOG(날짜 없음) + `gh api repos/anthropics/claude-code/releases`(날짜) + `code.claude.com/docs/llms.txt` 하위 공식 문서. 릴리스 날짜: 2.1.257=09-01 · 2.1.261=09-04 · 2.1.265=09-08 · 2.1.268=09-10 · 2.1.269=09-11 · 2.1.271=09-14 · 2.1.275=09-17 · 2.1.277=09-18 · 2.1.281=09-23 · 2.1.283=09-25 · 2.1.284=09-28 · 2.1.286=09-30 · 2.1.287=10-01 · 2.1.289=10-03. 로컬 `claude --version` = 2.1.289.

### 1.1 흡수·채택 후보 표

| # | 출처(URL·날짜) | 무엇인가 | 킷 현황 | 판정 | 근거 | 크기 |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | docs/en/plugin-evals · 2.1.269 (09-11) | `claude plugin eval`: 플러그인의 `evals/<case>/{prompt.md,graders/*.md\|case.yaml}` 실행. 그레이더 regex·tool_used·tool_order·file_exists·llm(3표 중 2)·baseline. 기본 3회 반복, **무플러그인 baseline 대비 Δ**, mock MCP, `--scaffold` 픽스처, `--json`·종료코드·`--max-cost-usd`·`--model` 고정(CI), `eval init` 자동 초안. `experimental.evals` 로 디렉토리 지정 | `evals/`(레포 루트): 에이전트 단위 시나리오+픽스처+pytest+기준선 회귀. **스킬 15종 행동 eval 은 0**(`evals/scenarios/` 13 디렉토리, 전부 에이전트 단위)(스킬 발동률·description 회귀 공백). 원장 50·57행이 «범용 evals 출시 시 최우선 흡수 후보» | **채택(파일럿)** — 대체가 아니라 보완 | 겹치지 않는 영역(스킬 발동 `tool_used: Skill`·Δ)이 우리 공백. 우리 `evals/` 는 에이전트 행동·기준선이 강점. 주의: eval 디렉토리가 플러그인 루트 아래여야 해 **배포물에 실림**(우리 README 는 «plugins/ 밖에 둔다»가 전제) | M |
| C2 | docs/en/plugins/measure · 2.1.261 (09-04), 2.1.283 (09-25) | `claude plugin details <name>` always-on 토큰 추정, `/skill-doctor`(미사용·비용), `/doctor prompt-audit`(구모델용 문구 점검) | `check_injection_budget.py` 는 훅 주입 규범만 잰다 | **채택(측정 병행)** | 실측: `claude --plugin-dir plugins/common plugin details hiway-kit` → Skills 15·Agents 15·Hooks 4, always-on ~3,568 tok(훅 주입 규범·WORKFLOW 는 불포함 — 두 수치를 합쳐야 실제 상시 비용). 에이전트 15 집계는 5.3.0 평탄화 결과 확인 | S |
| C3 | docs/en/workflows · 2.1.269~2.1.284 | 플러그인 `workflows/*.js` 컴포넌트(매니페스트 `workflows`), 실행은 `/<plugin>:<name>`. `Workflow`/`Workflow(<name>)` allow 규칙이면 `-p`·SDK 에서도 실행. 크기 가이드 medium<10(2.1.271), `/deep-research` 내장 | CLAUDE.md «대규모는 ultracode 수동 트리거 안내·스킬발 프로그래밍 트리거 불가(2026.6 기준)» | **채택(파일럿 1개)** | 이름 호출이 곧 사용자 명시 opt-in → 킷이 `multi-perspective-review`·대규모 감사를 워크플로로 배포 가능. 단 Claude Code 전용(하네스 중립 스킬은 병행 유지) | M |
| C4 | docs/en/memory#agents-md · 2.1.277 (09-18), 2.1.281 (09-23) | CLAUDE.md 가 없으면 **AGENTS.md 를 직접 읽음**(모든 프로바이더로 확대). `claude-md-and-agents-md` 값이면 둘 다 로드 | `harness-export` SKILL 이 «Claude Code 는 훅이 주입하므로 CLAUDE.md 제외, Codex 만 이중 도달 예외» 로 서술 | **채택(방침 결정)** | CLAUDE.md 없는 소비자 + export 된 AGENTS.md → CC 가 읽고 SessionStart 훅이 같은 규범을 또 주입(이중 도달). 서술이 낡았다(§6-F5) | S(문서)~M(훅 중복 억제) |
| C5 | docs/en/hooks · 현재 문서 | `SubagentStart` 가 `hookSpecificOutput.additionalContext` 지원(문맥 전용·차단 불가), Decision Control 표 등재. 2.1.265(09-08) 캐시 접두부 결함 수정 | 원장 37행 `watch`: «문서 확인 전에는 배포물에 넣지 않는다» | **판정 이월(사용자 결정)** | 기술 조건은 해소. 남은 쟁점은 memory `no-system-prompt-injection`(자동 위임 주입 가드) — 임의로 도입하지 않는다 | S |
| C6 | docs/en/sub-agents · 2.1.198 (07-01) | `/agents` 대화형 마법사 **제거** — 지금은 «Claude 에게 요청하거나 `.claude/agents/` 직접 편집» 안내만 | 원장 45행이 «네이티브 `/agents` 가 대화형 생성을 제공» 이라 적음 | **정정** | 사실 오류(§6-F2). CHANGELOG 2.1.198 «Removed the `/agents` wizard» | S |
| C7 | docs/en/tools-reference#task-tool-availability · 2.1.233 (08-14)→2.1.268 (09-10) | TaskCreate/Get/List/Update·TodoWrite 는 Claude 3.x·Opus 4–4.7·Sonnet 4–4.6·Haiku 4.5 에서만 기본. 그 외 `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`. 백그라운드·클라우드는 전 모델 | `plan-task`·`auto-dev`·`brainstorming` 이 `ToolSearch select:TaskCreate…`, DoD 룰 «Task 마감 규율»(매 세션 주입) | **정정 + 룰 수정 제안** | 이 세션(Sonnet 5.5)의 도구 목록에 TaskCreate 없음(실측). fail-open 대체(durable checklist)가 있어 파이프라인은 안 죽으나 주입 룰이 존재하지 않는 도구를 지시(§6-F3) | S |
| C8 | docs/en/goal.md · 2.1.269~ | `/goal`: 세션 범위 prompt-Stop 훅 래퍼. `-p`·Remote Control 지원. **평가자는 명령·파일을 직접 실행하지 않고 대화에 드러난 것만 판정** | CLAUDE.md «`/goal` 은 대화형 전용이라 프로그래밍 트리거 불가» | **관망 + 서술 정정** | `verify-done`(명령 출력)을 대체 못 함. 조건 문장에 «`verify-done.sh` exit 0» 을 적는 사용법 안내만 후보 | S |
| C9 | docs/en/skills · 2.1.286 (09-30) | `verify`/`simplify` **프로젝트·개인** 스킬이 있으면 커밋 직전 실행 지시(플러그인 스킬은 해당 안 됨) | `verify-done.sh`·DoD 룰(같은 방향) | **관망(제안만)** | 소비자가 `.claude/skills/verify` 를 직접 둬야 발동 — 킷은 소비자 레포에 쓰지 않는다 | S |
| C10 | docs/en/plugins/manifest-reference · 2.1.281 (09-23) | `claude plugin validate` 가 listing 키(`icon`·`documentationUrl`·`supportUrl`·`privacyPolicyUrl`) 를 더는 unknown 으로 경고 안 함 | `docs/marketplace-submission.md:115-120` 은 «스키마에 없는 키라 validate 가 경고하고 로드 시 제거 → 넣지 않았다» | **정정(근거 하나 낡음)** | 실측: 스크래치 복사본에 4키 추가 후 `claude plugin validate . --strict` rc=0. 둘째 근거(제출 시점 고정)는 유효 → 키 추가 자체의 이득은 «이후 목록 편집 수단 생길 때» 로 한정 | S |
| C11 | docs/en/plugins/dependencies · docs/en/plugins/publish | `dependencies`(semver)·`claude plugin tag`(태그 `<name>--v<version>`) | 킷 태그 `vX.Y.Z`. 소비자 플러그인이 킷에 버전 범위로 의존하면 태그 해소 불가 | **관망 → 의존 사례 생기면 채택** | 상호운용(north-star) 관점의 잠재 결함. 지금은 의존 사례 확인 못 함 | S |
| C12 | docs/en/plugins/manifest-reference | `userConfig`(`CLAUDE_PLUGIN_OPTION_*` 훅 env 노출)·`experimental.monitors`·`settings.json`(plugin 기본 agent) | 킷 노브는 환경변수(`CLAUDE_STOP_TEST_TIMEOUT` 등) | **관망** | `userConfig` 는 `/config` 에서 값 입력 UI 를 얻지만 Claude Code 전용이고 Codex 매니페스트는 미지원(OpenAI 가이드). 노브가 늘 때 재검토 | S |
| C13 | docs/en/sub-agents · 2.1.271 (09-14) | 에이전트 frontmatter `omitClaudeMd`(CLAUDE.md 없이 서브에이전트 실행) | `review-code` 는 «작성자와 분리된 컨텍스트» 를 요구 | **관망** | 독립 리뷰어에 의미 있을 수 있으나 프로젝트 규범까지 빠지는 부작용 `[추정]` — 실험 필요 | S |
| C14 | docs/en/sub-agents · 2.1.210 (07-14), 2.1.277 | 서브에이전트 결과를 «subagent output» 헤더 아래로 전달하고 지시문 모양 패턴 스캔 | `rules/untrusted-text.md` | **흡수(부분)** | 서브에이전트 결과 구간만 네이티브가 덮는다. 웹·메모리·타세션 규율은 그대로 | S |
| C15 | docs/en/plugins/mods/* · 2.1.287 (10-01) | Claude Mods: 플러그인이 JS 함수 훅으로 도구 호출·프롬프트·UI 를 가로챔. `claude plugin validate` 가 hooks/calls 열거 | 킷 훅은 Python 외부 프로세스·하네스 중립·fail-open | **무시** | Claude Code 전용·터미널/Desktop 한정. 킷 방침과 충돌. 단 소비자가 «mod 인 플러그인» 을 평가할 때 validate 출력을 쓴다는 점만 인지 | - |
| C16 | docs/en/cross-session-messaging · 2.1.224~ | `SendMessage`/`ListAgents`, 같은 머신은 소켓·타 머신은 Remote Control, 텍스트만·권한 승인 불가 | `control-loop`·Orca 운송(하네스 중립) | **관망** | 운송 부록에 «Claude 세션끼리 한정 네이티브 대안» 한 줄 후보. agent teams 는 아직 실험·기본 꺼짐 | S |
| C17 | docs/en/hooks | 훅 이벤트 33종(PostToolBatch·TaskCreated/Completed·PermissionDenied·InstructionsLoaded·PreModelSwitch 등), `if` 필드(권한 규칙 문법으로 필터), `mcp_tool`/`agent` 핸들러, 2.1.289: PreToolUse 매칭 실패 시 **차단**(fail-closed) | 훅 4종(SessionStart·PreToolUse·PostToolUse·Stop) | **관망** | `if` 로 `protect-sensitive` 프로세스 스폰을 줄일 수 있으나 이득 작음. fail-closed 는 보안 훅에 호재 | S |
| C18 | 2.1.284 (09-28), 2.1.289 | 인터랙티브·VS Code 세션이 **auto mode 기본 시작**, 서버측 분류기 | 킷 보안은 경로 기반 `protect-sensitive` | **관망** | 소비자 세션이 auto mode 에서 도는 비중이 늘면 훅·분류기 상호작용 점검 `[추정]` | S |
| C19 | 2.1.275 (09-17) | claude.ai 계정에 켠 스킬·플러그인이 터미널 세션으로 동기화(`<name>@synced`), 디렉토리 상장 플러그인의 도달 경로 | CLAUDE.md «디렉토리 = 내장 마켓플레이스 `anthropic-plugin-directory`(공식 문서에 이름 없음 — 실측)» | **관망** | 문서의 도달 경로(`@synced`)와 우리 실측(`@anthropic-plugin-directory`)이 다르다 — 서로 다른 경로일 수 있음 `[미확인]`. 기록만 | - |

### 1.2 Claude Code — 확인했으나 킷에 영향 없음/무시
- 모델 추가(Fable 5.1·Opus 5.5·Sonnet 5.5), 게이트웨이·Bedrock·Mantle·Cowork·Claude Tag·VS Code·클라우드 세션·화면낭독·vim 모드 항목 다수: 킷 컴포넌트와 무관.
- `claude --bare` 가 MCP·시스템 리마인더·백그라운드 태스크를 끔(2.1.286): `--bare` 에서 훅이 도는지는 `[확인 못 함]`(문서 «bare mode 에서 훅» 미확인).
- `claude project purge`→`claude purge`, `TaskOutput` 제거(2.1.277): 킷 참조 없음(grep 0).

### 1.3 원장 `docs/native-absorption.md` 갱신 제안 요약
상세 diff 는 §8 과 `ledger/native-absorption.diff`. 31행 대조 결과:

| 행(원장 번호) | 구분 | 내용 |
| --- | --- | --- |
| 37 SubagentStart | 갱신 | 문서 확인 조건 해소, 방침 판정 남음 |
| 45 agent-creator | **정정** | `/agents` 마법사는 2.1.198 에서 제거 |
| 46 대규모 오케스트레이션 | 갱신 | 플러그인 `workflows/`·`-p` 실행·`/goal` -p |
| 48 계획 파일 | **정정** | Task 도구 기본 비활성 |
| 50 Agent Evals | **재판정** `kit-only`→`watch` | `claude plugin eval` |
| 51 multi-perspective-review | 갱신 | 워크플로 적대적 검증 패턴·`/deep-research` |
| 56 harness-export | 갱신 | 읽는 쪽은 네이티브화, 이중 도달 |
| 57 eval-forge | 갱신 | `eval init` 과 겹침 |
| 59 다중 하네스 패키지 | 갱신 | agents 33→15 정정, Codex/agy 재측정 후보 |
| 나머지 22행 | 변경 없음 | 원장 파일 기준 29·30·31·32·33·34·35·36·38·39·40·41·42·43·44·47·49·52·53·54·55·58행. Auto Dream(49·55·58행)은 이번 공식 문서·changelog 에서 언급을 **찾지 못함 `[확인 못 함]`** — GA/폐기 여부 불명이라 `watch` 유지 |
| 신규 7행 | 추가 | `/goal`·크로스세션 메시징·비용 측정·Mods·`verify` 관례·서브에이전트 헤더·미사용 매니페스트 기능 |

### 1.4 호환성 경고
0건. 확인한 위험 후보와 결과: (a) `disallowedTools: Task` → 공식 문서 «2.1.63 에서 Task 가 Agent 로 개명, 기존 `Task(...)` 참조는 별칭으로 동작» — 안전. (b) 서브에이전트 중첩이 기본 3단계 허용(`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`) — 킷은 leaf 에이전트에 `Task` 를 막아 두므로 설계가 유지됨(네이티브 기본과 다른 의도적 선택임을 문서에 한 줄 적으면 좋음, P3). (c) 플러그인 에이전트는 `hooks`·`mcpServers`·`permissionMode` frontmatter 가 무시됨 — 킷은 이미 금지 필드. (d) 예약 이름 접두(`claude-`·`anthropic-`·`cc-plugin-`) — `hiway-kit` 안전. (e) `claude plugin validate --strict` 로컬 통과(2.1.289).

---

## 2. Codex (서브에이전트 조사 → 일부 재확인)

문서 URL 이전: `developers.openai.com/codex/*` 가 `learn.chatgpt.com/docs/*` 로 308 이동(서브에이전트 보고). 킷 문서의 `[confirmed: developers.openai.com/codex/...]` 인용 경로가 낡았을 수 있다(P2). 재확인: ★ = 내가 원문 확인.

| # | 출처(URL·날짜) | 무엇인가 | 킷 현황 | 판정 | 크기 |
| --- | --- | --- | --- | --- | --- |
| X1 ★ | learn.chatgpt.com/docs/build-skills (열람 10-05) | `agents/openai.yaml` 의 `policy.allow_implicit_invocation: false` 가 암묵 호출을 끄고 `$skill` 명시 호출은 유지. 이 파일에 `interface.display_name`·`short_description` 필수(`skill_agent_interface_missing`, submission-errors). SKILL.md 필수 키는 `name`·`description` 뿐 | 킷의 `disable-model-invocation: true` 3종(using-hiway-kit·harness-export·skill-forge)은 Codex 대응물이 없어 Codex 에서 **암묵 호출됨**. `build-targets.py` 에 `openai.yaml` 파생 없음(서브에이전트 grep 0) | **채택**: frontmatter 에서 `agents/openai.yaml` 파생 | S~M |
| X2 ★ | learn.chatgpt.com/docs/agent-configuration/subagents | «Current Codex releases enable subagent workflows by default.» 커스텀 에이전트 `.codex/agents/*.toml`(필수 name·description·developer_instructions). **플러그인 번들 언급 없음** | `targets.json` 과 `scripts/check_skill_degradation.py` 독스트링·`rules/parallel-worktree.md` 운송 중립화가 «Codex 에는 서브에이전트 위임 수단이 없다(실측)» 를 전제 — 게이트의 존재 이유가 약해졌을 수 있음 | **재측정 후 정정**. 에이전트 15종은 여전히 번들 불가 → opt-in `.codex/agents/` 내보내기가 후보(M~L, 관망) | S~M |
| X3 | learn.chatgpt.com/docs/hooks, CLI 0.158.0 (09-28) | 플러그인 번들 훅 로드(기본 `hooks/hooks.json`), `CLAUDE_PLUGIN_ROOT` 호환 주입, 정규식 matcher 해석, PreToolUse 차단 계약(`permissionDecision:"deny"` 또는 exit 2+stderr; 지원 안 하는 필드를 쓰면 훅 실패+도구 계속), 비관리 훅은 정의 해시별 신뢰 승인 필요 | 실측 «훅 exec form 로드 안 됨·차단 무시·matcher 미실측» (2026-08). 서브에이전트 지적: 당시 프로브가 exit 2+최상위 JSON 을 동시에 내 문서의 «형식 틀리면 실패+계속» 과 부합 `[추정]`. 또 `protect-sensitive.py` 는 `Edit/Write/Read`+`file_path` 만 보나 Codex 는 `Bash`/`apply_patch`+`command` 를 보냄 | **재측정 묶음**(차단 형식 교정·exec form·0.158+ 스모크) 후 판정 | M |
| X4 | developers.openai.com/plugins/deploy/submission (스크린샷 09-27) | 심사 포털 단일 흐름(ZIP→자동검사→스킬 보안스캔→심사→Publish), **ZIP 에 hooks/apps 있으면 제출 불가**, 버전마다 새 ZIP·재심사 | 5.2.0 이 ZIP 에서 hooks 를 뺀 판단과 일치(레포가 이미 앎) | 흡수(문서 확인만) | S |
| X5 | developers.openai.com/plugins/guides/submit-claude-plugin | `.claude-plugin/plugin.json` 자동 변환, `commands`/`agents` 는 스킬로 변환 권고, `userConfig` 미지원, hooks 는 Codex 용으로 어댑트(prompt·agent 핸들러는 실행 안 됨) | «agents 미지원 [2026-08 실측]» | **1차 근거 확보**(agents 비번들이 문서로 재확인) | S |
| X6 | developers.openai.com/plugins/plugin-guidelines | skills-only 플러그인은 «내장 기능이 지원하지 않는 기능» 등 추가 적격 요건 가능, Fair play 금지(과도 트리거·모델 선택 조작 문구) | 스킬 description 에 «MUST USE» 류 없음(에이전트 description 에는 있음; 에이전트는 Codex 미적재) | 관망 + 반려 대비 점검 | S |
| X7 | learn.chatgpt.com/docs/agent-configuration/agents-md | 전역→프로젝트 루트→cwd 연결, 디렉토리당 1개(`AGENTS.override.md` 우선), `project_doc_max_bytes` 기본 **32 KiB**(초과 시 cwd 쪽이 잘림) | 레포 AGENTS.md 16,863 B(≈51%). 소비자 전역·기존 AGENTS.md 와 합쳐 초과 가능 | 관망(여유 모니터링) + 문서: 하위 `override` 가 킷 블록을 가리는 점 | S |
| X8 | learn.chatgpt.com/docs/plugins | IDE 확장은 플러그인 미지원, 클라우드(ChatGPT Work)는 플러그인 훅 미지원 | README 가 IDE 한계를 안 적었다 `[추정]` | 흡수(문구) | S |
| X9 | learn.chatgpt.com/docs/changelog (09-05) | `codex mcp-server` 제거(app-server 로 대체) | `cross-engine-review` 의 Codex 사용 경로가 이에 의존하는지 `[확인 못 함]` | 관망 | S |
| X10 | developers.openai.com/plugins/build/plugins | 신규 포터블 `plugin.json`(`agent-plugins.org/schemas/1.0.0`, `extensions.com.openai`); `.codex-plugin` 은 호환 폴백 | 킷은 폴백 포맷 | 관망 | M |

확인 못 한 것: OpenAI 심사 기준·5.2.0 결과, 0.154~0.156 개별 항목, 현행 모델명(문서에 `gpt-5.6` 과 `GPT-6` 혼재).

---

## 3. Antigravity · Gemini CLI (서브에이전트 조사, 인용은 서브에이전트 보고 기준 — 로컬 `agy` 출력은 재확인 안 함)

| # | 출처(URL·날짜) | 무엇인가 | 킷 현황 | 판정 | 크기 |
| --- | --- | --- | --- | --- | --- |
| A1 | developers.googleblog.com «transitioning Gemini CLI to Antigravity CLI» (05-19), gemini-cli discussions/28017 (06-18) | 2026-06-18 부터 Gemini CLI 는 개인 계정(Pro·Ultra·무료) 서빙 중단(엔터프라이즈·유료 API 키는 계속). 터미널 주력은 `agy`. Gemini CLI 저장소는 계속 릴리스(v0.59~0.62, 09-08~09-29, 보안 하드닝 중심) | `harness-export` 가 «Gemini CLI 계열 → GEMINI.md» 를 주 대상으로 서술 | 문서 표현 정정 채택, 기능 변경은 관망 | S |
| A2 | 로컬 `agy` 1.2.17 `plugin validate plugins/common` | skills 15·**agents 15 processed**(2026-09-09 실측 땐 agents 4=카테고리 수) | `targets.json`·원장 59행 «agents 1급 미지원» (5.3.0 평탄화 이전 실측) | **재측정 후 정정**(validate 는 존재만 센다 — 런타임 인식 미측정) | M |
| A3 | 로컬 `agy plugin import claude <경로>` | 킷의 Claude 형식 `hooks.json` 을 `${CLAUDE_PLUGIN_ROOT}`·Claude 이벤트명 그대로 `plugins/hiway-kit/hooks.json` 로 복사. agy 훅 이벤트는 5종(PreToolUse·PostToolUse·PreInvocation·PostInvocation·Stop)이라 SessionStart 없음 | **소비자 경로 위험**: `agy plugin import claude` 로 들이면 무력/오작동 훅이 실릴 수 있음 `[추정]` — 발화 미측정 | **채택(격리 HOME 에서 마커 실측)** | M |
| A4 | antigravity.google/docs/rules·gcli-migration (날짜 없음) | AGENTS.md·GEMINI.md 모두 읽음(누적, 가까운 쪽 우선); 플러그인 `rules/` 자동 활성화(frontmatter `trigger` 필요 `[불명확]`), 파일당 24,000 B·상시 활성 합계 20,000 토큰 | 킷 rules 12개 ≈30 KB, `trigger` 없음. `targets.json` «rules 는 인식 대상 아님» 은 validate 출력만 근거 | 관망 후 canary 토큰 실측 | M |
| A5 | `agy changelog` 1.2.6·1.2.10·1.2.14 | 헤드리스 기본 타임아웃 5분→무제한, 오류 후 exit 0→**3**+`AGY_ERROR`, `--json-schema` 검증 | `targets.json` `_entrypointObservation` 의 «agy -p 는 타임아웃해도 rc=0» 은 1.1.28 기준 | 재측정 후 정정 | S |
| A6 | antigravity.google/docs/marketplace, changelog 2.18.1 (09-28) | Customizations 탭·플러그인 마켓플레이스(큐레이션). 서드파티 게재는 «interest form», 공개 제출 절차·스키마 없음 | `_marketplaceReason` «공식 공개 레지스트리 없음» 은 부분적으로 낡음 | 관망(interest form 은 사용자 판단) | S |
| A7 | gemini-cli `docs/cli/gemini-md.md` | Gemini CLI 는 기본 GEMINI.md 만 읽음(`context.fileName` 으로 AGENTS.md 추가) | GEMINI.md 별도 export 가 맞음 | 유지 | - |

확인 못 한 것: agy 가 킷의 `.claude-plugin/marketplace.json` 을 읽는지, agy 에서 `model: sonnet`·Claude 도구명 처리, Gemini CLI 저장소 장기 유지 여부.

---

## 4. 방법론 동향 (서브에이전트 조사 — [1차-읽음]/[2차]/[요약만] 라벨은 서브에이전트 표기. ★ = 내가 재확인)

| # | 출처(URL·날짜) | 무엇인가 | 킷과의 관계 | 판정 | 크기 |
| --- | --- | --- | --- | --- | --- |
| M1 ★ | arxiv.org/abs/2602.11988 (2026-02-12, v3 09-29) | «Evaluating AGENTS.md»: 컨텍스트 파일은 대체로 성공률을 높이지 못하고 비용 +20% 초과, 저장소 개요는 무익, 비표준 관행 지시만 유효. «배포 전 엄밀히 평가하라» | 킷은 규범을 세션마다 주입·AGENTS.md 생성. 레포 CLAUDE.md 427줄·AGENTS.md 294줄·rules 30,385 B. **규칙별 효과 측정 없음** | **채택**: 주입량 예산 게이트(S) + 규칙 A/B eval(M) | S/M |
| M2 | aaif.io (2026-08-13) + 5회 벤치 | «이 지시가 행동을 바꾸는가?» 기준, 짧을수록 좋음(12줄 사례 시간 -27%·비용 -24%, 저자 스스로 단일 사례), Codex 32 KiB 절단 | `harness-export` 마커 블록과 같은 방향 | 채택(예산 기준에 32 KiB 반영) | S |
| M3 | OpenAI «Harness engineering» (2026-02-11), Anthropic «Harness design for long-running apps» (03-24), Fowler/Böckeler (04-02) | 경계를 린터·구조 테스트로 강제하고 **린터 오류 메시지에 교정 지시 포함**, 작성자-평가자 분리·평가자 few-shot 보정, guides/sensors × computational/inferential 어휘 | 기계 게이트·분리 리뷰는 이미 있음. 없는 것: 게이트 실패 메시지의 교정 지시 관례, 평가자 보정 | **채택**: 게이트 메시지에 교정 지시(S), 어휘 표기(S). 청소 에이전트는 `/schedule` 원칙과 충돌 → 관망 | S |
| M4 | arxiv 2608.18167 (2026-08) «Adversarial Review» | 에이전트를 늘리면 수확체감, 순진한 합의는 **증거 없는 합의(false consensus)**, 명시적 반대 프롬프트 한 줄로 F1 최고, 3명이 5-에이전트 기준선 능가 | `multi-perspective-review`(10관점 3라운드) — 서브에이전트 grep 에서 합의 방어 문구 못 찾음(키워드 한계) | **채택**: 관점별 증거 필수·명시적 반대 라운드 | S~M |
| M5 | Anthropic «Demystifying evals for AI agents» (2026-01-09) 외 LLM-judge 편향 연구 3건(요약만) | 결과 상태 우선·모델 채점 보조·다중 시행(pass^k)·judge 사람 보정, 같은 계열 judge 의 자기선호·위치 편향 | `evals/` 는 결정적 어서션 우선·LLM-judge opt-in(방향 일치). 다중 시행·judge 보정 키워드 grep 0 | **채택**: pass^k + judge 계열 분리/위치 섞기 문서화 | M / S |
| M6 | modelcontextprotocol.io 2026-07-28 스펙·로드맵(08-22) | 무상태화(`initialize` 제거)·MRTR·Tasks 확장 이동·Sampling/Roots/SSE/DCR deprecated(12개월 유예). Claude Code 는 2.1.274 부터 MCP 2026-07-28 협상을 기본 사용(changelog) | 킷은 MCP 번들 안 함, `mcp-usage.md` 에 해당 키워드 0 | 관망(원장 한 줄) | S |
| M7 | Anthropic «How we contain Claude» (2026-05-25), arxiv 2608.23550 (08-24), Rule of Two 기사(06-11, 2차) | 승인 피로(약 93% 승인)라 격리가 중요, 설정 파일 보안 규칙의 4~16% 만 내장 통제와 대응(이 수치는 «통제가 있는 비율»이지 «준수율» 아님 — marmelab 글이 오독) | `untrusted-text` 가 프롬프트 규율임을 스스로 인정. 어떤 규칙이 **강제**이고 **지침**인지 표기 없음 | **채택**: 강제/지침 구분 표기 + 설계 체크(개인데이터·비신뢰·외부통신 중 2개까지) | S~M |
| M8 | spec-kit v1.0.0 (08-21), `/speckit.converge`(06), Kiro, OpenSpec, A2A v1.0(03-12) | 스펙 플랫폼화, converge=스펙↔코드 격차 재평가 후 잔여 태스크 생성 | plan-task 가 완료 조건·verify-done 을 가짐. «완료 시 격차 재평가» 단계 없음 `[추정]` | spec-kit/Kiro/OpenSpec/A2A 무시, **converge 설계만 흡수 후보**(M) | M |
| M9 | agentskills.io/specification, aaif/AGENTS.md 거버넌스(LF 2026-02-24) | Agent Skills 표준 필드(`name` ≤64·`description` ≤1024 등), AGENTS.md 는 필수 필드 없음 | 킷 스킬 `name` 전부 디렉토리명 일치, 최장 315줄. 표준 밖 키 `disable-model-invocation` 3개(원장이 이미 기록) | 채택(검증기 `skills-ref validate` 를 게이트에 — Claude 확장 키 허용 여부 `[확인 못 함]`) | S |

신뢰도 주의: marmelab 블로그(09-24, 2차)는 서브에이전트가 부정확 인용을 지적해 근거로 쓰지 않았다. Claude Code Projects 재출시(09-17, 2차 MarkTechPost)·Rehberger RCE 보고는 1차 확인 못 함 → 근거로 쓰지 않음.

---

## 5. 상위 5개 추천

| 순위 | 추천 | 이유(근거) | 크기 |
| --- | --- | --- | --- |
| 1 | **킷의 사실 오류·낡음 정정**(P1 5건·P2~P3 5건, §6) + 원장 갱신 | 대부분 문서 수정(S)이고 원장·CLAUDE.md·스킬 본문의 낡은 서술이다(주입 룰 1건 포함). 정정 근거가 전부 1차 문서·실측으로 확보됨 | S |
| 2 | **`claude plugin eval` 파일럿** — 스킬 발동·description 회귀 케이스 3~5개 | 원장이 «최우선 흡수 후보» 로 예고한 바로 그것. 우리 evals 의 공백(스킬 15종 0건)과 겹치지 않아 보완적. 배포물에 실리는 크기 비용을 파일럿에서 확인 | M |
| 3 | **`harness-export` × 네이티브 AGENTS.md 이중 도달 방침 결정** | CC 2.1.277+ 가 CLAUDE.md 없는 프로젝트에서 AGENTS.md 를 읽으므로 «Claude Code 는 훅이 주입하니 중복 없음» 서술이 거짓이 됐다. 문서(S) 후 훅의 중복 억제(M)는 사용자 판단 | S~M |
| 4 | **Codex 재측정 묶음 + `agents/openai.yaml` 파생** | `disable-model-invocation` 3종이 Codex 에서 암묵 호출되는 실제 결함(공식 문서 재확인). 훅 차단·서브에이전트·matcher 실측이 낡았을 가능성(문서 근거). 상호운용 north-star | S~M |
| 5 | **플러그인 배포 워크플로 파일럿**(`workflows/`, 이름 호출 opt-in) | 대규모 작업을 «ultracode 수동 트리거 안내» 로만 두던 한계를 이름 호출로 푼다. `multi-perspective-review` 를 1호로. Claude Code 전용이므로 하네스 중립 스킬은 병행 | M |

차순위: 6) `multi-perspective-review` 거짓 합의 방어(S~M, M4) · 7) 주입 규범·AGENTS.md 크기 예산 게이트 + 규칙 A/B(M1·M2) · 8) 강제/지침 구분 표기(M7) · 9) 게이트 실패 메시지에 교정 지시(M3) · 10) agy `import claude` 훅 실측(A3) · 11) listing 키 정정(C10) · 12) 태그 `<name>--v<ver>` 병행(C11).

---

## 6. 킷 문서의 사실 오류·낡음 (심각도·근거)

| ID | 심각도 | 위치 | 문제 | 근거 |
| --- | --- | --- | --- | --- |
| F1 | P1 | `docs/native-absorption.md:45` | «네이티브 `/agents` 가 대화형 생성을 제공» — 마법사는 2.1.198(2026-07-01)에서 제거됨 | CHANGELOG 2.1.198 «Removed the `/agents` wizard»(원문 사본 line 3562), docs/en/sub-agents |
| F2 | P1 | `docs/native-absorption.md:48` | 네이티브 Task 도구를 «보조로 쓴다» — 현재 기본 모델에선 도구 자체가 없음 | docs tools-reference «Task tool availability», CHANGELOG 2.1.233·2.1.268, 이 세션 도구 목록 |
| F3 | P2 | `plugins/common/rules/definition-of-done.md:26-30` «Task 마감 규율»(매 세션 주입) | 조건부 문장(«태스크를 쓰는 작업을…»)이라 Task 도구가 없는 세션에서도 위반은 아니나, 현재 기본 모델에선 사실상 죽은 지시이고 상시 주입 토큰만 쓴다. 대체 경로(`skills/plan-task/references/task-tools-fallback.md`)를 룰이 가리키지 않음 | F2 와 동일 |
| F4 | P1 | `CLAUDE.md` «네이티브 dynamic workflow / `/goal` 은 대화형 전용이라 스킬에서 프로그래밍 트리거가 불가(2026.6 기준)» | `/goal` 은 `-p` 에서 동작, `Workflow(<name>)` allow 규칙으로 `-p`·SDK 실행, 플러그인 `workflows/` 이름 호출 가능. 사용자 opt-in 게이트는 여전 | docs/en/goal.md, docs/en/workflows.md |
| F5 | P1 | `plugins/common/skills/harness-export/SKILL.md` | «Claude Code 는 훅이 주입하므로 CLAUDE.md 제외 — 같은 규범이 두 번 들어간다. 예외는 Codex 뿐» | CC 2.1.277+ 가 CLAUDE.md 없는 프로젝트에서 AGENTS.md 를 직접 읽는다(docs/en/memory#agents-md) → 이중 도달은 CC 에서도 발생 |
| F6 | P1 | `docs/marketplace-submission.md:115-120` | «listing 키는 스키마에 없어 validate 가 경고하고 로드 시 제거 → 넣지 않았다» | CHANGELOG 2.1.281 line 813, docs manifest-reference «Directory listing fields», 로컬 2.1.289 `validate --strict` rc=0 실측. 둘째 근거(제출 시점 고정)는 유효 |
| F7 | P2 | `docs/native-absorption.md:59`, 전수 검토 기록 | `agents/`(33) — 현재 15 | `plugins/common/agents/` 15개, CLAUDE.md |
| F8 | P2 | `docs/native-absorption.md:35,36` | 표 셀 안의 `|` 가 열을 깨뜨림(35행 «옛 판정: | 2026-09-17…», 36행 `startup|clear|compact`) | 열 수 검사(35행 5개·36행 6개, 기대 4) |
| F9 | P2 | `packaging/targets.json` 노트들 | «Codex subagent 수단 없음»·«agents 비지원 확정»·«rules 인식 안 함»·«agy -p rc=0» 이 2026-08~09-09 실측 기준 | §2·§3 (재측정 전에는 `[추정]`) |
| F10 | P3 | CLAUDE.md «Sub-agent Rules» | leaf 에이전트에 `Task` 를 막는 것은 네이티브 기본(중첩 3단계 허용)과 다른 **의도적 선택** — 한 줄 명시 권장 | docs/en/sub-agents «can spawn subagents … up to three layers» |

호환성(킷 콘텐츠 파손) 0건, 보안 이슈 0건.

---

## 7. 확인 못 한 것·한계

- Auto Dream(원장 49·55·58행): 이번 공식 메모리 문서·changelog 에서 언급을 찾지 못함 → GA 여부 판정 불가.
- `/doctor prompt-audit`·`claude plugin eval` 는 API 비용이 들어 실행하지 않았다(문서·`--help` 로만 확인). `claude plugin eval` 이 «early access» 게이트 에러를 내는 빌드가 있다는 문서 문구가 있으나, 로컬 2.1.289 에서 실제 실행 가능 여부는 미확인.
- `agy plugin import` 의 훅 발화, Codex 훅 차단·서브에이전트 스폰, agy 에이전트 런타임 인식: 문서·validate 출력 기준이며 런타임은 미측정.
- 방법론 항목의 arXiv 숫자(2608.18167·2608.23550 등)와 2차 자료는 서브에이전트가 읽은 초록 수준이며, 내가 원문을 재확인한 것은 2602.11988 하나다. 나머지는 «방향 근거» 로만 쓰고 수치 인용은 하지 않는다.
- MCP 2026-07-28: 방법론 서브에이전트는 Claude Code 지원 시점을 «확인 못 함» 이라 했으나 CHANGELOG 2.1.274(09-17)에 «MCP 2026-07-28 협상을 기본 사용» 이 있어 내가 보완했다(M6).
- Claude Code 디렉토리 노출 경로(문서의 `@synced` vs 실측 `anthropic-plugin-directory`)의 관계는 확인 못 함.
- Codex 심사 결과·SLA, Antigravity 공개 제출 절차는 외부 비공개.
- 서브에이전트 3개의 호출 사실: 방법론/Codex/Antigravity 각 1개(총 3), 각자 읽기 전용.

---

## 8. `docs/native-absorption.md` 갱신 제안 (diff 텍스트)

적용은 사용자/메인 세션 승인 후. 스크래치패드 `ledger/native-absorption.diff`(unified diff, 레포 파일은 건드리지 않음)에 동일 내용이 있다. 요약 적용 위치:

- 수정 9행: 37(SubagentStart)·45(agent-creator, **정정**)·46(대규모 오케스트레이션)·48(계획 파일, **정정**)·50(Agent Evals, `kit-only`→`watch`)·51(multi-perspective-review)·56(harness-export)·57(eval-forge)·59(다중 하네스, `agents/`(33)→(15) 포함)
- 신규 7행(59행 아래): `/goal`·크로스세션 메시징·`plugin details`/`skill-doctor` 비용·Mods·`verify` 스킬 관례·서브에이전트 출력 헤더·미사용 매니페스트 기능
- 전수 검토 기록 맨 위에 2026-10-05 행 추가

전체 diff 는 아래 «부록 A» 에 그대로 싣는다.

## 9. 후속 작업 제안(별도 계획, 이 감사의 범위 밖)

1. F1–F7 정정 커밋(문서 변경만, 룰 파일을 건드리면 CHECKSUMS·미러 재생성 필요 — `definition-of-done` 은 미러 없음).
2. `plan-task` 로 «`claude plugin eval` 파일럿»·«플러그인 워크플로 파일럿»·«Codex 재측정» 3건 기획.
3. 사용자 결정 필요: ① SubagentStart 주입 방침(memory `no-system-prompt-injection`), ② AGENTS.md 이중 도달 처리(문서만 vs 훅 억제), ③ Antigravity interest form 제출 여부.

---

## 부록 A — 원장 갱신 diff (unified)

(전문은 `ledger/native-absorption.diff`; 아래는 같은 내용)

```diff
--- native-absorption.orig.md	2026-10-05 19:15:06
+++ native-absorption.new.md	2026-10-05 19:15:16
@@ -34,7 +34,7 @@
 | 기획 정련 깊이 (`plan-task` + `clarify-requirements`) | (네이티브 대응물 없음) — 외부 선행 사례: dryforge `ready` | `kit-only` | 2026-09-15 조사(`docs/research/2026-09-15-dryforge-evaluation.md`) 결과 **도구가 아니라 설계를 흡수**. v3.35.0 에서 탐색 4자리·질문 선별·출처 3분류·실행 가능한 완료 조건을 `references/elicitation.md` 로 도입. 미흡수 잔여: `grounds-gate`(요구사항별 3근거 필터) · `intent-completeness` 독립 검증 |
 | 스킬 자동 발동 차단 (수동 전용 지정) | `disable-model-invocation` frontmatter | `native-adopted` | **2026-09-28 재판정(v5.0.0)**: 공식 문서(code.claude.com/docs/en/skills)가 SKILL.md 지원과 효과를 명시한다 — *"Description not in context, full skill loads when you invoke"*. 즉 상시 비용이 실제로 준다. 아래 옛 판정의 두 미검증(지원·효과)이 모두 해소돼 `using-hiway-kit`·`harness-export`·`skill-forge` 에 적용. Codex/OpenAI 쪽은 모르는 키가 경고로 무시된다. 옛 판정: | 2026-09-17 실측: Anthropic 공식 플러그인은 **`commands/` 에서만** 사용(`code-review`), **`skills/` 사용 사례 0건**. dryforge 가 스킬에 쓰지만 제3자 사용은 지원 근거가 아니다. 또한 이 플래그가 **스킬 description 을 로스터에서 빼는지 `[미확인]`** — 빼지 않으면 상시 비용 절감 효과가 0이다. **지원·효과 양쪽이 미검증이라 도입하지 않는다.** 공식 문서가 skills 지원을 명시하거나 실측되면 재평가 — 우리 수동 전용 스킬 5종(`native-watch`·`eval-forge`·`harness-export`·`skill-forge`·`self-improve`)이 후보 |
 | 컴팩션 후 규범 복원 | `SessionStart` matcher `compact` / `PostCompact` | `native-adopted` | 2026-09-20 실측: 우리 `hooks.json` 이 이미 `matcher: "startup|clear|compact"` 다. compact 페이로드로 훅을 직접 실행해 startup 과 **바이트 동일한** 출력(sha 일치, RULES·WORKFLOW·LESSONS 전부 포함)을 확인했다 — **구멍이 아니었다.** 경쟁 하네스(Xastra)가 `PostCompact` 훅으로 하는 것을 우리는 SessionStart 재발화로 이미 한다. 단 그 불변식을 지키는 테스트가 없어 이번에 추가 |
-| 서브에이전트 계약 전파 | `SubagentStart` 훅 | `watch` | 2026-09-20: Claude Code 에 `SubagentStart`/`SubagentStop` 이 **존재**하나, 공식 문서의 "Decision Control by Event" 표에 **없어 반환 규약(`additionalContext` 지원 여부)이 미명시**다. 우리는 `child-session` 스킬 + 마커로 하고 있고 훅 강제는 없다. **지원이 문서로 확인되거나 실측되기 전에는 배포물에 넣지 않는다** — `disable-model-invocation` 과 같은 판정. 실측하려면 프로젝트/전역 설정에 프로브 훅을 걸어야 하는데 그건 소비자 환경을 건드리는 일이라 보류 |
+| 서브에이전트 계약 전파 | `SubagentStart` 훅 | `watch` | 2026-09-20: Claude Code 에 `SubagentStart`/`SubagentStop` 이 **존재**하나, 공식 문서의 "Decision Control by Event" 표에 **없어 반환 규약(`additionalContext` 지원 여부)이 미명시**다. 우리는 `child-session` 스킬 + 마커로 하고 있고 훅 강제는 없다. **지원이 문서로 확인되거나 실측되기 전에는 배포물에 넣지 않는다** — `disable-model-invocation` 과 같은 판정. 실측하려면 프로젝트/전역 설정에 프로브 훅을 걸어야 하는데 그건 소비자 환경을 건드리는 일이라 보류 **2026-10-05 갱신**: 공식 훅 레퍼런스(code.claude.com/docs/en/hooks)가 `SubagentStart` 의 `hookSpecificOutput.additionalContext` 지원(문맥 전용·차단 불가)을 명시하고 Decision Control 표에도 등재했다 — 위 «문서 확인 전에는 넣지 않는다» 조건은 해소됐다. 2.1.265(2026-09-08)는 SubagentStart 문맥이 프롬프트 접두부에서 밀려 캐시를 깨던 결함도 고쳤다. 남은 것은 기술이 아니라 방침 판정이다(자동 주입 vs 명시적 위임 호출, memory `no-system-prompt-injection`) — 도입 전 사용자 결정 필요 |
 | eval 측정 축 기록·검증 | (네이티브 대응물 없음) — 외부 선행: Xastra `run_model.py` 가 세션 JSONL 을 되읽어 실제 사용 모델·effort 를 검증하고 불일치 시 `invalid` 로 배제 | `kit-only` | 2026-09-20 흡수(v3.38.0). 우리 리포트에 **어느 모델로 돌았는지 기록이 없어** baseline 비교가 «같은 것을 셌는가»를 답할 수 없었다(`warning-signal.md` §측정 7). `model` 을 결과·summary 에 싣고 `compare_baseline` 이 축 불일치를 회귀로 잡는다. 축 **미지**는 회귀가 아니라 stderr notice — 구 baseline 에서 상시 참이 되어 옆의 진짜 회귀를 죽이기 때문(§검토 1·3). 미흡수 잔여: **실제 사용 모델을 응답에서 되읽는 것**(우리는 요청값만 기록한다 — 서버측 폴백은 여전히 안 보인다) |
 | 코드베이스 탐색 에이전트 (`explore-codebase`) | 내장 `Explore` 서브에이전트 | `superseded` | v5.0.0 제거. 내장 Explore 가 같은 일을 읽기 전용·저비용으로 하고, 우리 에이전트의 "분석해줘"·"탐색" 트리거는 일상 요청을 빼돌렸다 (spec §B) |
 | 구현 계획 에이전트 (`plan-implementation`, 흡수: `plan-refactor`·`design-services`) | 내장 `Plan` 서브에이전트 · plan mode | `watch` | v5.0.0: 셋을 하나로. `plan-task` 스킬이 부르는 계획 산출(`docs/plans/`) 계약이 있어 유지 — 내장 Plan 은 파일 산출 계약이 없다. 내장 Plan 이 산출물 계약을 받으면 흡수 후보 |
@@ -42,26 +42,34 @@
 | 스킬 생성 (`skill-creator`) | 공식 skill-creator 스킬 · Codex 내장 스킬 생성 | `superseded` | v5.0.0 제거 — 공식 스킬이 템플릿·평가까지 제공하고, 우리 것은 소비자에게 없는 `plugins/{domain}/` 경로로 쓰게 했다 |
 | MCP 서버 스캐폴딩 (`mcp-builder`) | 공식 mcp-builder 스킬 · MCP SDK 문서 | `superseded` | v5.0.0 제거 — SDK 릴리스마다 예시가 낡는 부채(4.0.1 에서 한 번 고쳤고 다시 낡았다) |
 | 문서 공동 작성 (`doc-coauthoring`) | (범용 모델 능력) | `superseded` | v5.0.0 제거 — 일반 템플릿이었고, 서술한 자동 문서 갱신 트리거는 실재하지 않았다 |
-| 에이전트 생성 (`agent-creator`) | `/agents` | `watch` | v5.0.0: 소비자 `.claude/agents/` 로 쓰게 고침. 네이티브 `/agents` 가 대화형 생성을 제공 — 우리 것은 frontmatter 검증 관례만 얹는다 |
-| 대규모 병렬 오케스트레이션 (구 agent-teams 자체 조율) | `ultracode` (dynamic workflow) | `superseded` | agent-teams 스킬은 네이티브 라우팅 안내로 대체 (Spec 2 / W-006). 단 스킬발 자동 트리거는 여전히 불가 — 모델 호출형 Workflow 도구는 존재하나 사용자 opt-in 게이트(세션 실측 2026-07-07). 자동 위임은 Task+스킬 루프 유지 |
+| 에이전트 생성 (`agent-creator`) | `/agents` | `watch` | v5.0.0: 소비자 `.claude/agents/` 로 쓰게 고침. **2026-10-05 정정**: 옛 근거(«네이티브 `/agents` 가 대화형 생성을 제공»)는 사실이 아니다 — `/agents` 대화형 마법사는 2.1.198(2026-07-01)에서 제거됐고 지금은 «Claude 에게 만들게 하거나 `.claude/agents/` 를 직접 편집하라»는 안내만 출력한다(공식 sub-agents 문서, 로컬 CHANGELOG 2.1.198). 네이티브 경로는 «Claude 에게 요청»이고, 우리 것은 frontmatter 검증 관례만 얹는다 |
+| 대규모 병렬 오케스트레이션 (구 agent-teams 자체 조율) | `ultracode` (dynamic workflow) | `superseded` | agent-teams 스킬은 네이티브 라우팅 안내로 대체 (Spec 2 / W-006). 단 스킬발 자동 트리거는 여전히 불가 — 모델 호출형 Workflow 도구는 존재하나 사용자 opt-in 게이트(세션 실측 2026-07-07). 자동 위임은 Task+스킬 루프 유지 **2026-10-05 갱신**: 위 «스킬발 자동 트리거 불가» 서술은 일부 낡았다. 플러그인이 `workflows/` 를 컴포넌트로 싣고 `/<plugin>:<name>` 으로 실행하게 하는 경로가 공식화됐다(매니페스트 `workflows` 필드, docs/en/workflows.md) — 이름 호출은 사용자의 명시 호출이라 `ultracode` 키워드 없이도 opt-in 이 성립한다. `Workflow`/`Workflow(<name>)` allow 규칙이면 `-p`·SDK 에서도 실행되고, `/goal` 도 `-p` 에서 동작한다(docs/en/goal.md). 사용자 opt-in 게이트(키워드·이름 호출·allow 규칙) 자체는 그대로. 상태 `superseded` 유지, 다만 Large 작업의 선택지에 «킷이 워크플로를 배포» 가 추가됨(채택 후보, M) |
 | 주기 실행/스케줄링 | `/schedule` (routines) | `native-adopted` | kit 자체 스케줄러 구현 금지 — zero-debt (spec: `docs/specs/2026-07-07-toolkit-improvement-batch.md`). /native-watch도 네이티브 경로만 안내 |
-| 계획 파일 (`docs/plans/<날짜>-<slug>/plan.md` + checklist.json) | native TaskCreate/TaskList | `watch` | 4.0.0: Work 시스템(ID·단계 폴더·work.sh)을 제거하고 계획 파일 한 장으로 줄였다. 네이티브 Tasks 는 보조로만 쓴다 — 완료를 verify 명령 결과로 막지 못하고 Codex 등 다른 하네스엔 영속 태스크가 없다. 네이티브가 verify-gated 완료를 제공하면 checklist 흡수 후보 (spec: `docs/specs/2026-09-28-plans-replace-works/`) |
+| 계획 파일 (`docs/plans/<날짜>-<slug>/plan.md` + checklist.json) | native TaskCreate/TaskList | `watch` | 4.0.0: Work 시스템(ID·단계 폴더·work.sh)을 제거하고 계획 파일 한 장으로 줄였다. 네이티브 Tasks 는 보조로만 쓴다 — 완료를 verify 명령 결과로 막지 못하고 Codex 등 다른 하네스엔 영속 태스크가 없다. 네이티브가 verify-gated 완료를 제공하면 checklist 흡수 후보 (spec: `docs/specs/2026-09-28-plans-replace-works/`) **2026-10-05 갱신**: 네이티브 Task 도구(TaskCreate/Get/List/Update·TodoWrite)는 이제 Opus 4.8·Sonnet 5·Fable 5 이상에서 기본 제공되지 않는다(2.1.233=2026-08-14 제거 → 2.1.268=2026-09-10 기본 목록 확정: Claude 3.x·Opus 4–4.7·Sonnet 4–4.6·Haiku 4.5 만 기본, 그 외는 `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`, 백그라운드·클라우드 세션은 전 모델 제공 — 공식 tools-reference «Task tool availability»). 현재 기본 모델(Opus 5.5·Sonnet 5.5)에서는 `ToolSearch select:TaskCreate…` 가 빈 결과라 `plan-task`·`auto-dev`·`brainstorming` 의 Task 경로는 기본적으로 fail-open 대체(durable checklist)로만 돈다 — 이 행의 «네이티브 Tasks 는 보조로 쓴다» 는 «보조로도 기본 비활성» 으로 읽어야 한다. `TaskCompleted`/`TaskCreated` 훅(exit 2 로 완료 차단)은 존재하나 Task 도구가 있는 세션·agent teams 한정이라 verify-gated 완료의 흡수 근거로는 부족 |
 | feedback ledger (상한·중복제거·감쇠) | native memory + Auto Dream (research preview) | `kit-only` | 2026-07-07 /native-watch: Auto Dream(메모리 병합·모순 제거·인덱스 상한)이 research preview로 등장 — 동일 계열이나 GA 아님. GA 시 재평가, 그전까지 ledger 유지 (Spec 3 / W-007) |
-| Agent Evals (`evals/`) | Skills 2.0 evals (스킬 대상, 부분) | `kit-only` | 2026-07-07 /native-watch: skill-creator에 스킬-대상 evals/A-B 등장했으나 **범용 에이전트 행동 평가 프리미티브는 부재** — kit evals 유지 (spec: `docs/specs/2026-07-07-toolkit-improvement-batch.md`). 네이티브 범용 evals 출시 시 최우선 흡수 후보. 2026-08-27 확인: 티어1 커버리지 4/33 → 13/13, 시나리오⇄기준선 드리프트 게이트(`scripts/check_eval_coverage.py`) 신설(W-018) — 판정(`kit-only`) 자체는 불변, kit 쪽 커버리지·게이트 성숙도만 갱신 |
-| multi-perspective-review (10 관점 합의) | ultracode judge panel 패턴 | `watch` | 부분 겹침 — 사용자 opt-in 게이트라 스킬 체인 내 자동 실행은 kit 유지(2026-07-07 재확인). 네이티브 패널이 스킬에서 트리거 가능해지면 재평가 |
+| Agent Evals (`evals/`) | Skills 2.0 evals (스킬 대상, 부분) | `watch` | 2026-07-07 /native-watch: skill-creator에 스킬-대상 evals/A-B 등장했으나 **범용 에이전트 행동 평가 프리미티브는 부재** — kit evals 유지 (spec: `docs/specs/2026-07-07-toolkit-improvement-batch.md`). 네이티브 범용 evals 출시 시 최우선 흡수 후보. 2026-08-27 확인: 티어1 커버리지 4/33 → 13/13, 시나리오⇄기준선 드리프트 게이트(`scripts/check_eval_coverage.py`) 신설(W-018) — 판정(`kit-only`) 자체는 불변, kit 쪽 커버리지·게이트 성숙도만 갱신 **2026-10-05 재판정(`kit-only`→`watch`)**: `claude plugin eval`(2.1.269=2026-09-11, 공식 docs/en/plugin-evals)이 «범용 행동 평가 프리미티브 부재» 전제를 깼다 — 케이스(`prompt.md`+`graders/*.md`)·그레이더(regex·tool_used·tool_order·file_exists·llm·baseline)·무플러그인 baseline 대비 Δ·mock·`--json`/종료코드/`--max-cost-usd` CI 게이트·`plugin eval init` 자동 초안. 겹치지 않는 것: 우리는 에이전트 단위 시나리오+픽스처+pytest 실행+기준선 회귀(`evals/`)이고 네이티브는 플러그인 단위(스킬 발동률·Δ). 상보적 — 스킬 description 발동 평가는 우리 쪽 공백(스킬 15종 행동 eval 0). 흡수 전 파일럿 필요(eval 디렉토리가 플러그인 루트 아래여야 해 배포물에 실림 — `experimental.evals` 로 위치 지정) |
+| multi-perspective-review (10 관점 합의) | ultracode judge panel 패턴 | `watch` | 부분 겹침 — 사용자 opt-in 게이트라 스킬 체인 내 자동 실행은 kit 유지(2026-07-07 재확인). 네이티브 패널이 스킬에서 트리거 가능해지면 재평가 2026-10-05: 네이티브 워크플로 문서가 «독립 에이전트가 서로의 발견을 적대적으로 검증»·«여러 각도 초안 후 비교» 패턴을 공식 사례로 싣고 `/deep-research`(투표·교차검증) 내장 워크플로를 제공한다 — 부분 겹침 심화, 상태 유지 |
 | 스킬 자동 주입 (session-start WORKFLOW/LESSONS) | SessionStart hook additionalContext | `native-adopted` | 네이티브 훅 규격 사용, 내용만 kit 소유 |
 | 시크릿 커밋 차단 | gitleaks + pre-commit (외부 도구) | `kit-only` | 네이티브 무관 — 외부 표준 도구 조합 |
 | Definition-of-Done 기계 게이트 (`scripts/verify-done.sh`) | (대응 네이티브 없음) | `kit-only` | 완료 판정을 명령 출력으로 강제하는 게이트 — 네이티브 대응물 부재 (2026-07-07 확인) |
 | 재귀 개선 루프 (`/self-improve`) — v5.0.0 부터 이 레포 전용(`.claude/skills/`) | Auto Dream (research preview, 메모리 한정) | `kit-only` | Auto Dream은 메모리 정리 한정 — 정의 파일 개선 제안 루프는 네이티브 부재. Auto Dream GA·확장 시 재평가 (2026-07-07 확인) |
-| 하네스 중립 규범 배포 (`/harness-export` → `AGENTS.md`) | (대응 네이티브 없음 — CC는 자기 세션만 주입) | `kit-only` | 2026-08-23 ADE 벤치마킹(W-017): Orca·Paseo가 한 레포에 다중 하네스를 붙이는 것이 표준이 됨. CC의 SessionStart 주입은 CC 세션에만 걸리므로 구멍. `AGENTS.md`는 Codex·OpenCode·Copilot·Cursor 공통 사실상 표준 — 네이티브 대응물 부재 |
-| eval 시나리오 포징 (`/eval-forge`) — v5.0.0 부터 이 레포 전용(`.claude/skills/`) | Skills 2.0 evals (스킬 대상, 부분) | `kit-only` | 2026-08-23 W-017: 위 `Agent Evals` 행과 동일 판정 — 범용 에이전트 행동 evals 프리미티브 부재. 포징 도구는 그 위의 커버리지 확장 수단이며 네이티브 대응물 없음 |
+| 하네스 중립 규범 배포 (`/harness-export` → `AGENTS.md`) | (대응 네이티브 없음 — CC는 자기 세션만 주입) | `kit-only` | 2026-08-23 ADE 벤치마킹(W-017): Orca·Paseo가 한 레포에 다중 하네스를 붙이는 것이 표준이 됨. CC의 SessionStart 주입은 CC 세션에만 걸리므로 구멍. `AGENTS.md`는 Codex·OpenCode·Copilot·Cursor 공통 사실상 표준 — 네이티브 대응물 부재 **2026-10-05 부분 정정**: Claude Code 가 2.1.277(2026-09-18)부터 CLAUDE.md 가 없으면 AGENTS.md 를 직접 읽는다(2.1.281=09-23 에 Bedrock·Vertex·Foundry·게이트웨이·텔레메트리 off 세션까지 확대, `/config` «Project instructions», 값 `claude-md-and-agents-md` 로 둘 다 로드, docs/en/memory#agents-md). «대응 네이티브 없음» 은 *읽는 쪽*에서는 틀렸다 — *내보내는 쪽*은 여전히 kit-only. 부작용: CLAUDE.md 없는 소비자 프로젝트에 `/harness-export` 산출 AGENTS.md 가 있으면 Claude Code 가 그것을 읽고 SessionStart 훅이 같은 규범을 또 주입한다(이중 도달) — `harness-export` SKILL 은 이를 Codex 만의 예외로 서술한다. 중복 처리 방침 결정 필요 |
+| eval 시나리오 포징 (`/eval-forge`) — v5.0.0 부터 이 레포 전용(`.claude/skills/`) | Skills 2.0 evals (스킬 대상, 부분) | `kit-only` | 2026-08-23 W-017: 위 `Agent Evals` 행과 동일 판정 — 범용 에이전트 행동 evals 프리미티브 부재. 포징 도구는 그 위의 커버리지 확장 수단이며 네이티브 대응물 없음 2026-10-05: `claude plugin eval init`(2.1.269)이 케이스·그레이더를 인터뷰·시험 실행 후 자동 생성한다 — 포징 도구와 일부 겹침(스킬 발동 케이스 한정). 위 `Agent Evals` 재판정과 함께 재검토 |
 | 성공 trajectory → 스킬 승격 (`/skill-forge`) | Hermes Agent의 자동 스킬 생성 (외부 하네스) / Auto Dream (research preview, 메모리 한정) | `kit-only` | 2026-08-23 W-017: Hermes가 이 계열의 선행 사례이나 **다른 하네스의 기능**이지 CC 네이티브가 아님. CC 네이티브는 skill-creator(수동)까지 — trajectory 기반 자동 승격 프리미티브 부재. Auto Dream GA·확장 시 재평가 |
-| 다중 하네스 패키지 배포 (Codex `.codex-plugin/`·Antigravity `plugin.json`) | Codex Plugin / Antigravity Plugin 네이티브 매니페스트 규격 | `native-adopted` | 2026-08-26 W-019: kit는 각 플랫폼의 플러그인 런타임을 재구현하지 않고, 그 플랫폼이 이미 읽는 매니페스트 포맷만 생성한다(`scripts/build-targets.py`). 양쪽 다 실물 CLI로 설치·인식 확인(`codex plugin marketplace add`→`list`, `agy plugin validate`→`install`→`list`). **범위 한계(실측 확정)**: 양쪽 플랫폼 모두 `agents/`(33) 1급 미지원(Codex는 전용 필드 없음, Antigravity는 `agy`가 카테고리 중첩을 재귀하지 않음) — kit 구조를 바꾸지 않고 사실대로 문서화(스펙 §5.5). Codex 훅(exec form)은 로드 안 됨을 직접 실측 확정, 편입 보류 |
+| 다중 하네스 패키지 배포 (Codex `.codex-plugin/`·Antigravity `plugin.json`) | Codex Plugin / Antigravity Plugin 네이티브 매니페스트 규격 | `native-adopted` | 2026-08-26 W-019: kit는 각 플랫폼의 플러그인 런타임을 재구현하지 않고, 그 플랫폼이 이미 읽는 매니페스트 포맷만 생성한다(`scripts/build-targets.py`). 양쪽 다 실물 CLI로 설치·인식 확인(`codex plugin marketplace add`→`list`, `agy plugin validate`→`install`→`list`). **범위 한계(실측 확정)**: 양쪽 플랫폼 모두 `agents/`(15; 작성 시점엔 33) 1급 미지원(Codex는 전용 필드 없음, Antigravity는 `agy`가 카테고리 중첩을 재귀하지 않음) — kit 구조를 바꾸지 않고 사실대로 문서화(스펙 §5.5). Codex 훅(exec form)은 로드 안 됨을 직접 실측 확정, 편입 보류 **2026-10-05 재측정 후보**(감사 C, 판정은 실측 후): ① Antigravity 1.2.17 `agy plugin validate plugins/common` 가 agents 15 processed(5.3.0 평탄화 이후; validate 는 존재만 센다 — 런타임 인식 미측정). `agy plugin import claude` 는 Claude 형식 훅을 `${CLAUDE_PLUGIN_ROOT}` 그대로 복사한다(발화 미측정). ② Codex 문서(learn.chatgpt.com)가 서브에이전트 기본 활성·커스텀 에이전트 `.codex/agents/*.toml`(플러그인 번들 필드는 없음 — OpenAI 변환 가이드도 agents→skills 변환 권고)을 명시하고, 플러그인 번들 훅 로드·matcher 해석·PreToolUse 차단 계약을 문서화해 «훅 로드 안 됨/차단 무시/matcher 미실측» 실측의 재측정이 필요하다. 단 OpenAI 심사 포털은 ZIP 에 hooks 가 있으면 제출 불가 |
+| 완료 조건 루프 (`stop-validator`·`auto-dev` 검증 루프) | `/goal` (세션 범위 prompt 기반 Stop 훅 래퍼, `-p`·Remote Control 지원) | `watch` | 2026-10-05(감사 C): 공식 docs/en/goal.md — 평가자는 **명령·파일을 직접 실행하지 않고 대화에 드러난 것만 판정**한다. 우리 «DoD = 명령 출력» 게이트(`verify-done.sh`)를 대체하지 못하고 보완 관계(조건 문장에 «`verify-done.sh` exit 0» 을 적는 사용법 안내 가능). `disableAllHooks`·`allowManagedHooksOnly` 면 비활성 |
+| 멀티세션 위임 운송 (`control-loop`·`docs/control-loop-transport.md` 의 Orca 운송) | `SendMessage`/`ListAgents`(2.1.224~, 같은 머신은 소켓·타 머신은 Remote Control), `claude --bg`·agent view, agent teams(실험) | `watch` | 2026-10-05: 텍스트 메시지만·권한 승인 불가·루프 스로틀(공식 cross-session-messaging). 우리 운송은 하네스 중립(Claude↔Codex↔…)이라 유지 — 운송 부록에 «네이티브 대안(Claude 세션끼리 한정)» 한 줄 후보. agent teams 는 여전히 실험·기본 꺼짐 |
+| 주입 예산·스킬 품질 점검 (`scripts/check_injection_budget.py`·`self-improve`) | `claude plugin details <name>`(always-on 토큰 추정), `/skill-doctor`(2.1.261), `/doctor prompt-audit`(2.1.283) | `watch` | 2026-10-05 실측: `claude --plugin-dir plugins/common plugin details hiway-kit` → Skills 15·Agents 15·Hooks 4, always-on ~3,568 tok(**훅이 주입하는 규범·WORKFLOW 는 이 수치에 불포함**). 에이전트 15개가 집계되는 것은 5.3.0 평탄화의 결과 확인 |
+| (대응 없음 — 킷 훅은 Python 외부 프로세스) | Claude Mods(2.1.287=2026-10-01): 플러그인이 JS/TS 함수 훅으로 도구 호출·프롬프트·UI 를 가로챔 | `watch` | 2026-10-05: Claude Code 전용·터미널/Desktop 만 그림. 킷은 하네스 중립·Python 3.9 floor·fail-open 이라 채택하지 않는다(무시 판정). 단 `claude plugin validate` 가 mod 의 hooks/calls 를 열거하므로 소비자 신뢰 평가 대상이 될 수 있음 |
+| 완료 직전 검증 습관 (`verify-done.sh`·DoD 룰) | `verify` 스킬 관례(2.1.286=2026-09-30): 프로젝트·개인 위치에 `verify`/`simplify` 스킬이 있으면 커밋 직전 실행하라고 안내(플러그인 스킬은 해당 안 됨) | `watch` | 2026-10-05(공식 skills 문서). 같은 방향이나 소비자가 프로젝트 `.claude/skills/verify` 를 직접 두어야 발동 — `setup.sh`(opt-in)가 스캐폴드를 제안하는 방안은 «소비자 레포에 쓰지 않는다» 원칙과 충돌하지 않게 제안만 |
+| 비신뢰 텍스트 규율 중 서브에이전트 결과 (`rules/untrusted-text.md`) | 서브에이전트 결과 «subagent output» 헤더·지시문 모양 스캔(2.1.210·2.1.277), 메모리 로드 시 보이지 않는 문자 무력화(2.1.284) | `watch` | 2026-10-05: 서브에이전트 결과 구간만 부분 흡수. 웹·메모리·타세션 텍스트 규율은 kit-only 유지 |
+| 매니페스트 신규 기능 중 킷 미사용분 | `dependencies`(semver)·`claude plugin tag`(태그 `<name>--v<version>`)·`userConfig`(`CLAUDE_PLUGIN_OPTION_*`)·디렉토리 listing 키(`icon`·`supportUrl`·`privacyPolicyUrl`…)·에이전트 `omitClaudeMd`·스킬 `context: fork`/`paths`/`when_to_use` | `watch` | 2026-10-05: 킷 스킬은 `name`·`description`·`disable-model-invocation` 만, 에이전트는 7키만 쓴다. 태그가 `vX.Y.Z` 라 다른 플러그인이 킷에 버전 범위로 의존하면 해소 불가(`hiway-kit--vX.Y.Z` 필요). listing 키는 2.1.281(2026-09-23)부터 `claude plugin validate` 가 경고하지 않음을 로컬 2.1.289 에서 실측(`--strict` rc=0) — `docs/marketplace-submission.md` 의 «경고하고 제거» 근거는 낡음(제출 시점 고정이라는 둘째 근거는 유효) |
 
 ## 전수 검토 기록
 
 | 날짜 | 검토자 | 변경 |
 | --- | --- | --- |
+| 2026-10-05 | 감사 C 외부 동향 조사 (/native-watch 절차, 기준 e7181cb) | CC 2.1.257~2.1.289 전수 대조. 재판정 1건(`Agent Evals` kit-only→watch), 정정 2건(`/agents` 마법사 제거·Task 도구 기본 비활성), 갱신 6건(SubagentStart·ultracode/workflows·multi-perspective·AGENTS.md·eval-forge·다중 하네스), 신규 7행. 변경 없음 22행. 수동 제안(적용은 승인 후) |
 | 2026-09-28 | v5.0.0 전수 감사 (컨트롤) | 네이티브 대조가 빠져 있던 7행 추가(Explore·Plan·`/code-review` 계열·skill-creator·mcp-builder·doc-coauthoring·`/agents`). `disable-model-invocation` 을 공식 문서 근거로 `watch`→`native-adopted`. 에이전트 개수 33→15 정정. 이 표가 에이전트 한 행으로만 뭉뚱그려 개별 에이전트↔네이티브 대조를 한 번도 하지 않은 것이 이번 감사가 찾은 사각지대였다 |
 | 2026-07-07 | /native-watch 첫 실행 (v2.10.1) | 8행 watch 격상(cross-session Tasks 신호), 9·10행 근거 갱신(Auto Dream·Skills 2.0), 6·11행 확인일/뉘앙스, 신규 2행(DoD 게이트·self-improve). 호환성 경고 0건 |
 | 2026-08-26 | 다중 하네스 패키지 배치 (W-019) | 신규 1행 추가(다중 하네스 패키지 배포). Codex·Antigravity 네이티브 플러그인 규격을 실물 CLI로 검증 후 흡수. **범위 한계도 실측으로 확정해 같은 배치에서 문서화** — 양쪽 다 `agents/` 1급 미지원, Codex 훅 exec form 미로드(스펙 §5.5, 초안이 실측과 어긋났던 것을 정정) |
```
