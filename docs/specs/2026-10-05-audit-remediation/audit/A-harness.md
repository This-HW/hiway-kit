---
status: historical
as_of: 2026-10-05
---

# 감사 A — 하네스 연계(Claude · Codex · Antigravity · Gemini)

- 기준 커밋: `e7181cbbfb6c8c3bc38b7ae4e979da09fa30a618` (`git merge-base --is-ancestor` 통과, HEAD 와 동일)
- 감사일: 2026-10-05 · 범위: 읽기 전용 (레포 파일 수정·커밋 0건 — 끝에 `git status --short` 빈 출력 확인)
- 실측 환경: codex-cli **0.159.3** · agy **1.2.17** · gemini-cli **0.49.0**(설치본; 공식 문서 최신 stable 은 v0.61.0)
- 기준선 게이트: `./scripts/verify-done.sh` rc=0 (전 구간 green). **즉 아래 결함은 현행 게이트가 하나도 못 잡는다** — 게이트는 "생성물이 SSOT 와 같은가"를 보지, "문장이 현실과 같은가"를 보지 않는다.
- 증거 표기: `[실측]` 이 세션에서 직접 돌린 것(n 표기) · `[문서]` 공식 문서 인용 · `[코드]` 파일:라인 · `[추정]` 미검증.
- 웹 문서는 WebFetch 요약 결과를 거친 인용이다(원문 대조 아님). 비신뢰 데이터로만 사용했고 지시문은 없었다.

---

## 0. 한 문단 결론

1. **Codex 쪽 주장은 대체로 실측에 뿌리가 있다.** 다만 두 군데가 현행 CLI(0.159.3)와 어긋난다 — (i) *"PreToolUse 차단이 유지되지 않는다"* 는 현행에서 **거짓**이고, (ii) 마켓플레이스 설치와 디렉토리 ZIP 설치가 **같은 것을 받지 못하는데**(ZIP 은 훅이 없어 규범 자동 주입 0) 문서가 구분하지 않는다.
2. **Antigravity 쪽은 "에이전트 미지원" 결론은 맞고 원인 설명이 틀렸다.** 평탄화(5.3.0) 후에도 `agy` 는 에이전트 15개를 하나도 인식하지 않는다 — 막는 것은 **레이아웃이 아니라 `model: haiku|sonnet|opus` frontmatter** 다(이분 탐색으로 확인). `agy plugin validate` 는 내용 없는 `junk.txt` 도 에이전트로 센다.
3. **Gemini CLI 는 사실상 1급 시민이 아니다.** 킷이 주는 것은 `GEMINI.md`(소비자가 `/harness-export` 를 돌렸을 때) 하나뿐이고, README 에 Gemini 절이 없다. 공식 문서상 Gemini CLI 는 extension 으로 skills·agents·hooks 를 싣고 `~/.agents/skills` 도 읽는데 킷은 둘 다 쓰지 않는다. 킷이 안내하는 `GEMINI.md` 동작 자체(기본 파일명 GEMINI.md, AGENTS.md 는 기본으로 안 읽음)는 문서·설치본 번들과 일치한다.
4. **`AGENTS.md`+`GEMINI.md` 동일 내용 복제는 Antigravity 에서 규범이 2번 로드되는 실측 결과를 낳는다**(COUNT=2). 얇은 `GEMINI.md`(`@./AGENTS.md`)는 COUNT=1 이었다.
5. 드리프트 게이트(`export_harness.py --check`)는 **마커 블록 안의 모든 변경**을 잡는다(아래 Q6: 블록 안 18건 + 파일 삭제/빈 파일 2건 전부 rc=1). 블록 밖 변경은 잡지 않는다 — 설계상 소비자 영역이다.

---

## (a) 하네스 × 구성요소 표 — 주장 / 검증 방법 / 결과 / 갭

범례: ✅ 주장이 이번 감사에서 실측·문서로 확인 · ⚠ 부분 · ❌ 주장이 틀림/낡음 · ❓ 측정 기록 없음(또는 이번에도 못 잼)

### Codex (codex-cli 0.159.3)

| 구성요소 | README/매니페스트 주장 | 이번 검증 방법 | 결과 | 갭 |
| --- | --- | --- | --- | --- |
| 스킬 | "all 15 recognized (measured, v5.0.0)" `README.md:119` | 격리 `CODEX_HOME` 에 `codex plugin marketplace add <repo>` → `plugin add` → `codex exec` 로 모델에게 스킬명 나열 요청 | ✅ 15종 전량(`hiway-kit:agent-creator … web-research`) [실측 n=1] | 기록 라벨 불일치: `packaging/targets.json` `_skillRuntimeObservation` 은 **0.153.4 에서 21종**을 잰 기록이다. "v5.0.0 에서 15 측정" 기록은 CHANGELOG·targets.json 어디에도 없다 → 이번 측정이 처음 |
| 규범 주입(훅, 마켓플레이스 설치) | "hook injection (measured)" `README.md:117` | 같은 설치 + `--dangerously-bypass-hook-trust`, 모델에게 DoD 규칙 첫 구절 인용 요청 | ✅ `"Definition of Done — 완료 게이트"` 인용, `hook: SessionStart` 발화 [실측 n=1] | 신뢰 승인 전 침묵 건너뜀은 기존 기록(`targets.json` `_evidence`)을 신뢰 — 이번엔 재측정 안 함 |
| 규범 주입(**디렉토리 ZIP 설치**) | README 는 이 경로를 구분하지 않음 | `build-codex-zip.py --out` 으로 만든 ZIP 을 풀어 로컬 마켓플레이스로 `plugin add`(근사) | ❌ **스킬 15종은 동일하게 도착, 규범 주입 `NOINJECT`**, `hook: SessionStart` 0회 [실측 n=1] | **문서가 두 경로를 같은 것처럼 서술.** P1-1 |
| 파일 트리 동일성 | — | 마켓플레이스 캐시(76 파일) vs ZIP(65 파일) `find`+`cmp` | ✅ 차이는 정확히 `hooks/` 10파일 + 루트 `plugin.json` + 매니페스트의 `hooks` 필드 | `skills/`·`tools/`·`rules/`·`agents/`·`setup/` 는 바이트 동일. ZIP 에도 `agents/` 15개·`rules/` 가 죽은 채로 실린다 |
| 도구(`tools/`) 도착 | 5.2.0 이동 | ZIP 트리에서 `export_harness.py --stdout`·`checklist.py --help` 실행 | ✅ `hooks/` 없이도 동작(import 의존 0) [실측] | — |
| 훅: 차단 | "no — PreToolUse block did not stop the command" `README.md:122`, `targets.json hooks._omitted`, 생성물 AGENTS/GEMINI 표, 플러그인 description | 격리 `CODEX_HOME` + 스크래치 `hooks.json`: PreToolUse 에서 ① `exit 2`+stderr ② `hookSpecificOutput.permissionDecision:"deny"` JSON, 대상 `touch` | ❌ **둘 다 차단됨**(`Command blocked by PreToolUse hook`, 파일 미생성). 양성 대조(훅 없음)는 파일 생성 [실측 n=1 각] | P0-2. 기록은 0.153.4, 현행 0.159.3 |
| 훅 페이로드 | "스키마 미측정" `_hookPayloadProbeStatus` | PreToolUse 입력 덤프 | ✅ 새로 측정: 쉘=`tool_name:"Bash"`,`tool_input.command`; 파일 편집=`tool_name:"apply_patch"`,`tool_input.command`=패치 본문. `Read` 도구 없음 [실측] | `protect-sensitive.py:243` 은 `Edit/MultiEdit/Write/Read/NotebookEdit` 만 → Codex 이식에는 `apply_patch`·`Bash` 파서 필요 |
| 서브에이전트 | "not exposed" | 기존 기록(0.153.4 `NO`) + 공식 문서에 플러그인 번들 에이전트 언급 없음 [문서] | ✅ (재측정 안 함) | Codex 커스텀 에이전트는 `.codex/agents/*.toml`(필수 `name`,`description`,`developer_instructions`) [문서] — Claude `.md` 와 형식 다름, 변환 필요 |
| 환경변수 | 훅 커맨드 `${CLAUDE_PLUGIN_ROOT}` `hooks-codex.json` | 공식 문서 | ✅ Codex 가 훅에 `CLAUDE_PLUGIN_ROOT` 호환 설정 [문서: learn.chatgpt.com/docs/hooks] | **모델의 쉘 도구 환경에는 없다** [실측 n=1: `env|grep PLUGIN_ROOT` 빈 출력] → 스킬의 `${CLAUDE_PLUGIN_ROOT:-}/tools/…` 는 비고, 폴백 글롭은 `~/.claude/...` 뿐 (P1-6) |
| 진입점 `AGENTS.md` | "Codex 가 읽는다" | 기존 기록(0.153.4)·문서 | ✅ [문서] 계층 로딩, `project_doc_max_bytes` 32KiB 기본 | 킷 AGENTS.md 16.9KB(<24KB soft cap) |

### Antigravity (agy 1.2.17)

| 구성요소 | 주장 | 검증 방법 | 결과 | 갭 |
| --- | --- | --- | --- | --- |
| 스킬 | "recognized (real skills install and run correctly)" `README.md:106` | ① `agy plugin validate`: skills 15 ② 워크스페이스 `.agents/plugins/hiway-kit/` 에 킷 복사 후 `agy -p` 로 스킬명 질의 | ✅ 모델이 `auto-dev`·`control-loop`·`plan-task` 를 스킬로 나열 [실측 n=1] | "run correctly" 는 기록 없음(당시 `agy -p` 완주 0/6). 이번에 인식은 확인, **실행**은 미확인 |
| 에이전트 | "❌ not supported — validate did not recurse into category subdirs … flat not re-verified" `README.md:108,120` | ① 평탄 레이아웃 `validate` ② 격리 `HOME` 설치 후 `agy agents` ③ frontmatter 이분 탐색 | ❌→⚠ **결론(미지원)은 맞고 원인이 틀림.** 15 processed 인데 `agy agents` 는 0개. 이분 탐색: `model: haiku`·`sonnet`·`opus`·`gemini-3.8-flash-low` 는 제외, **`model: inherit` 또는 `model` 생략은 인식**. `tools`/`effort`/`maxTurns`/`disallowedTools`/`Bash` 는 무관 [실측 n=1 각] | P1-3 |
| `validate` 신뢰도 | "validate 통과" 를 인식 근거로 사용 | 내용 없는 `junk.txt` 를 `agents/` 에 둠 | ❌ `agents : 1 processed` — **파일 개수만 센다** [실측] | `targets.json` 이 이미 적어 둔 사실. 그런데 README Antigravity 검증 안내(`agy plugin validate`)가 "recognized" 의 근거처럼 읽힌다 |
| 규칙(plugin `rules/`) | "❌ not recognized — validate output byte-identical with/without rules/" `README.md:107` | 워크스페이스 플러그인에 `rules/r.md`(토큰 `PLUGRULE-5521`)+`skills/pskill`, 모델 질의 | ✅ **결론 맞음**: pskill 은 인식, 규칙 토큰은 **도착 안 함** [실측 n=1]. 단 **기존 근거(validate 출력 동일)는 가르지 못하는 측정**이었다 | 공식 문서는 plugin 구조에 `rules/` 를 나열한다 [문서: antigravity.google/docs/plugins] — 문서와 런타임이 충돌. P1-4 |
| 진입점 | "AGENTS.md/GEMINI.md only" | 토큰이 다른 두 파일 + `agy -p --output-format json` | ✅ **둘 다 읽는다**(응답 `AGENTSTOKEN-4492 GEMTOKEN-7731`) [실측 n=1] ; 동일 내용 두 파일 → `COUNT=2`, `GEMINI.md`=`@./AGENTS.md` 한 줄 → `COUNT=1` [실측 n=1 각, 모델 자기집계] | 기록(`targets.json`)은 "agy 런타임 쿼터/스트림 중단으로 진입점 실도달 미관측" — 1.2.17 에서는 `status:SUCCESS` 6.7s. 낡음 (P1-5) |
| 훅 | "not shipped — format unverified" | 공식 문서 | ✅ 정직한 표기. 문서에 `hooks.json` 존재 [문서], 이벤트·형식은 못 봄 | — |
| 설치/레지스트리 | "No official public registry confirmed … only local/workspace" `README.md:216` | `agy plugin` 도움말 | ⚠ `install <target>` 는 **`plugin[@marketplace]` 지원**, `link <mp> <target>`, `import [source]`("Import plugins from gemini or claude") 존재 [실측: `agy plugin` 출력] | README 가 이 셋을 모른다. 문서 표현("로컬만")은 CLI 현실과 다름 [추정: 마켓플레이스 소스 규격은 못 봄] (P2-2) |
| 매니페스트 | `$schema` = `https://antigravity.google/schemas/v1/plugin.json` | HTTP 요청 | ⚠ 이 URL 은 **404** [문서 조사: WebFetch "HTTP 404"]; 문서 예시는 같은 URL 을 `$schema` 로 쓰고 있음 | 생성물 `plugins/common/plugin.json:2` 에 죽은 `$schema` — 무해하나 검증 근거로 쓰지 말 것(`targets.json` 이 이미 기록) |

### Gemini CLI (gemini-cli 0.49.0 설치 / 문서 v0.61.0)

| 구성요소 | 주장 | 검증 방법 | 결과 | 갭 |
| --- | --- | --- | --- | --- |
| 진입점 | "Gemini CLI 계열은 `GEMINI.md`" (`harness-export/SKILL.md:20`, `export_harness.py:389-404`) | 설치본 번들 grep + 공식 문서 | ✅ `DEFAULT_CONTEXT_FILENAME = "GEMINI.md"`, 번들에 `AGENTS.md` 문자열 없음 [실측] ; 문서: AGENTS.md 는 `context.fileName` 으로 지정할 때만 [문서: geminicli.com/docs/cli/gemini-md/] | **런타임 도달은 미측정** — 이 머신 API 키 무효(400 `API_KEY_INVALID`, 재현). `targets.json`·CHANGELOG 도 같은 상태를 기록 |
| 스킬 | (주장 없음) | 문서 | 킷이 안 줌. Gemini CLI 는 `~/.gemini/skills`·`~/.agents/skills`(사용자), `.gemini/skills`·`.agents/skills`(워크스페이스) 를 읽고 extension 이 `skills/` 번들 가능 [문서: geminicli.com/docs/cli/skills/, /extensions/reference/] | 공급 경로 없음 (P1-6) |
| 에이전트 | AGENTS.md "서브에이전트 정의 15종 — Claude Code 규격 전용" | 문서 + 로컬 | ✅ 정직. Gemini 서브에이전트는 `.gemini/agents/*.md`, 실험적, frontmatter `name/description/kind/tools/model/max_turns` [문서]. 로컬 증거: caveman 확장의 Claude 형식 에이전트가 `tools.N: Invalid tool name` 로 로드 실패 [실측, 킷 것은 아님 — 유추] | — |
| 훅 | "차단 훅이 없는 하네스" 로 묶음 | 문서 | ❌/⚠ Gemini CLI 에 훅이 **있다**: SessionStart·BeforeTool·AfterTool 등, exit 2 / `decision:"deny"` 차단 [문서: geminicli.com/docs/hooks/]. 확장은 `hooks/hooks.json` 번들 가능 | 출력 스키마·주입 필드는 못 봄. 킷은 Gemini 훅을 "없다"고 취급 |
| 확장 매니페스트 | (없음) | 문서 + 이 머신 | `gemini-extension.json`(`contextFileName`,`mcpServers`,`excludeTools`…)이 표준. **이 머신에 설치된 superpowers 가 정확히 이 방식**(`~/.gemini/extensions/superpowers/gemini-extension.json`) [실측] | 킷은 Gemini 타겟이 없음 (`targets.json` 에 `gemini` 항목 부재) |

### 측정 기록 없는 칸 — 전수 (Q1 요구)

README 하네스 비교표(`README.md:104-110` 구성요소, `:115-122` Parity) 중 **측정 기록이 없거나 이번 감사 전까지 없었던** 칸:

| 칸 | 상태 |
| --- | --- |
| Codex 스킬 "all 15 … (measured, v5.0.0)" | 기록은 21종/0.153.4 뿐 → 라벨 불일치 |
| Antigravity 스킬 "run correctly" | "실행" 기록 없음(인식만 이번에 처음 확인) |
| Antigravity Rules 행(`:117`) "AGENTS.md/GEMINI.md only" | 이번 감사 전 **미측정**(agy 런타임 막힘) → 이번에 확인 |
| Antigravity Ledger digest "self-fetch per the rule" | **미측정** (아직도) |
| Antigravity Subagents/model·effort "(nested layout)" | 원인 서술 틀림(실제: `model:` frontmatter) |
| Codex Automatic blocking "no" | 0.153.4 기록이 현행에서 뒤집힘 |
| Antigravity Automatic blocking "no" | 기록 없음 — 훅 미탑재라 "없음"은 사실이나 **Antigravity 에 훅 자체가 없다는 뜻이 아님** |
| Codex "Agent model/effort not applied — measured: files land in cache" | 측정은 "파일이 캐시에 떨어진다"까지. "서브에이전트로 노출 안 됨"은 별도 기록(`NO`)이 뒷받침하나 표 문장이 둘을 섞음 |
| Gemini 열 전체 | **표에 열이 없음**. Gemini CLI 런타임 측정 0건 |

---

## (b) 발견 목록 (P0 → P3)

### P0 — 사실 오류 / 사용자를 틀린 길로

**P0-1. 배포되는 스킬 문서가 Antigravity 가 규범(rules)을 받는다고 적는다 — 킷 스스로의 실측과 정반대.**
- 근거: `plugins/common/skills/harness-export/SKILL.md:161` *"Antigravity 는 스킬+규범(에이전트는 비지원)"*.
  반대편: `README.md:107`("❌ not recognized … Norms reach Antigravity only through the entrypoint file"), `packaging/targets.json:140`, 이번 실측(plugin `rules/` 토큰 미도착, n=1).
- 영향: 이 스킬은 소비자 환경에 설치되는 문서다. Antigravity 사용자가 `agy plugin install` 만으로 규범이 들어온다고 믿고 `/harness-export` 를 건너뛸 수 있다 (주입 0).
- 같은 단락이 *"Codex 는 스킬만"* 이라고 쓰지만 Codex 매니페스트는 `hooks` 도 싣는다(`.codex-plugin/plugin.json`).

**P0-2. "Codex 는 PreToolUse 차단이 유지되지 않는다"는 현행(0.159.3)에서 거짓이다.** (방향은 보수적 — 해는 *보호 기회 상실*이지 허위 안심이 아님. 기록은 0.153.4 시점.)
- 근거(실측, 격리 `CODEX_HOME`): `exit 2`+stderr → `ERROR codex_core::tools::router: error=Command blocked by PreToolUse hook: …`, 대상 파일 미생성. `hookSpecificOutput.permissionDecision:"deny"` JSON → 동일. 훅 없는 양성 대조 → 파일 생성. 공식 문서도 두 방식을 지원한다고 적는다 [문서: learn.chatgpt.com/docs/hooks].
- 틀린 문장이 있는 곳(소비자에게 가는 것 포함):
  `README.md:122` · 생성물 `AGENTS.md`/`GEMINI.md` "이식하지 못하는 것" 표(*"Codex 에는 싣지 않는다(PreToolUse 차단이 유지되지 않는다)"*; 원본 문구 `export_harness.py:453`) · `packaging/targets.json` `hooks._omitted["protect-sensitive.py"]`·`stop-validator.py` · `docs/codex-submission-checklist.md` "What's NOT included" · `plugins/common/skills/child-session/SKILL.md:99-101` · 플러그인 `description`(*"automatic hook enforcement are a Claude Code deepening feature"*, `.claude-plugin/plugin.json` — 디렉토리 노출 문구).
- 원 측정이 틀렸는지(출력 형식)·CLI 가 바뀌었는지는 가르지 못함 [추정: CLI 변경]. 어느 쪽이든 현행 기록과 문장은 맞지 않는다.

### P1 — 모순 / 낡음

**P1-1. 마켓플레이스 설치와 디렉토리 ZIP 설치가 다른 것을 받는데 문서가 같은 것처럼 쓴다. (OpenAI 5.2.0 이 Publish 되면 P0 로 승격)**
- 근거: `scripts/build-codex-zip.py` `EXCLUDED_DIRS={"hooks/"}`·`MANIFEST_DROPPED={"hooks"}`; 트리 diff(위); `NOINJECT` 실측. README Codex 절·Parity 표는 훅 주입을 Codex 의 기본 경로로 서술하고 ZIP 경로를 언급하지 않는다(`README.md:117,134` 대, ZIP 은 `docs/codex-submission-checklist.md` 에만).
- ZIP 설치자의 실제 경로: 훅 0 → 규범 0 → `/harness-export` 로 AGENTS.md 생성해야 함. 그런데 스킬의 도구 탐색은 Claude 전용이다(P1-6). 이번 실측에서 Codex 모델이 임의 `find`/`rg` 로 도구를 **스스로 찾아** 성공(exit 0, AGENTS.md+GEMINI.md 생성)했으나 이는 스킬 설계가 아니라 모델의 임기응변이다 [실측 n=1].
- 플러그인 description 의 *"Rules and skills work on any coding harness"* 는 ZIP 설치 Codex 에서 규범에 대해 사실이 아니다(`/harness-export` 필요).

**P1-2. `README.md:197-198` 낡음.** *"Public listing … requires OpenAI's submission review — not done"* ↔ `docs/codex-submission-checklist.md` "5.2.0 submitted, In review (2026-09-30)", `CLAUDE.md` "OpenAI 디렉토리: 5.2.0 검토 중".

**P1-3. Antigravity 에이전트 미지원의 원인이 잘못 서술돼 있고, 그 때문에 5.3.0 의 "미재검증" 이 지금도 열려 있다.**
- 잘못된 서술: `README.md:108,120`("nested layout"), `CHANGELOG.md` 5.3.0("Codex·Antigravity 는 에이전트를 싣지 않으므로 영향이 없다"), `packaging/targets.json:140` `_recognizedDirsNote`(*"4개 카테고리 아래 33개 … kit의 agents/ 구조를 이 배치를 위해 바꾸지 않는다"* — 33개도 카테고리도 5.3.0 이전에 이미 낡음).
- 답: **평탄화로 달라진 것 없음.** `validate` 는 15 processed 로 올라가지만 `agy agents` 는 0개, 모델 질의에서도 `review-code`/`verify-code` 미인식. 원인은 `model:` 값(위 표).
- 부수: `agy plugin validate` 가 이제 `agents : 15 processed` 를 초록으로 찍어, README 의 검증 안내를 따라간 사람에게 **거짓 확신**을 준다 (`targets.json` 이 이미 경고한 "개수만 세는 도구" 문제의 재발).

**P1-4. Antigravity "rules 미인식" 결론은 맞지만 근거 측정이 가르지 못했다 (§측정 9: "가르지 못하는 값은 증거가 아니다").** 이번에 가르는 측정(토큰 도착 여부)으로 결론은 확인. 그러나 공식 문서가 plugin 구조에 `rules/` 를 나열하므로 *문서와 런타임 충돌*이라는 사실이 README/targets.json 에 없다 — 문서가 고쳐지면(또는 agy 가 지원하면) 조용히 낡는다.

**P1-5. 측정 기록 낡음: agy 런타임 "막힘" → 1.2.17 에서 풀림.** `targets.json codex._entrypointObservation` 의 agy 절(쿼터/스트림 중단, "2026-09-10T22:12Z 이후 재측정" 예정)은 닫지 못한 채 남아 있다. 이번 `agy -p --output-format json` 은 `status:SUCCESS` 6.7~12.6s. 진입점 도달(양 파일 모두), 스킬 인식을 지금 닫을 수 있다.

**P1-6. 스킬의 킷 도구 탐색이 Claude 캐시 전용이다 (Codex 소비자에게 죽은 경로).**
- 근거: `skills/harness-export/SKILL.md:79-80`, `skills/plan-task/references/task-tools-fallback.md:34-35`, `skills/auto-dev/SKILL.md:228-229` — 폴백이 `~/.claude/plugins/cache/*/*/*/…` 뿐. Codex 캐시는 `~/.codex/plugins/cache/<marketplace>/<plugin>/<ver>/`(이 머신 `~/.codex/plugins/cache/hiway-kit-marketplace/hiway-kit/5.1.2` 실물). 쉘 도구 환경에 `CLAUDE_PLUGIN_ROOT`·`PLUGIN_ROOT` 없음(실측).
- 이 머신은 `~/.claude` 캐시도 있어 폴백이 **다른 버전의 Claude 설치본을 잡아** 성공할 수 있다 — Codex 전용 머신에서만 깨진다 (§측정 4 "인접 기능이 폴백으로 살아 있으면 죽은 경로가 살아 있는 것처럼 보인다").
- 훅 쪽(`hooks-codex.json`)은 문서상 `CLAUDE_PLUGIN_ROOT` 호환이 있어 문제 없음.

**P1-7. Gemini CLI 는 킷의 1급 하네스가 아닌데 그렇다고 어디에도 쓰여 있지 않다.**
- README 에 Gemini 절·열 없음(`grep -n -i gemini README.md` = 3줄, 모두 `GEMINI.md` 파일명). 생성물 AGENTS/GEMINI 서두 *"Claude Code·Codex·OpenCode·Copilot·Pi·Hermes 등"*(`export_harness.py:422`) — Gemini 이름 없음.
- 공식 문서상 이용 가능한 것(extension 의 `skills/`·`agents/`·`hooks/hooks.json`·`contextFileName`, `~/.agents/skills`)을 킷이 쓰지도, "못 쓴다"고 밝히지도 않는다. `~/.agents/skills`·`.agents/skills` 문자열이 킷 문서에 **0건**(grep).
- 이 머신의 Gemini 에는 superpowers 가 extension 으로 설치돼 있다 — 같은 부류의 도구는 이미 그 경로로 배포된다.
- 런타임 측정은 0건이고 막힌 사유(API 키)는 환경이라 정직하게 기록돼 있다 — 그 정직함은 유지할 가치가 있다.

**P1-8. Antigravity 진입점 이중 로드 미문서화 (실측).** `AGENTS.md`+`GEMINI.md`(각 ~16.8KB, 내용 동일)를 둘 다 읽어 규범이 2번 들어간다(`COUNT=2`). Antigravity 문서는 파일당 24KB·합산 20,000 토큰 한도와 초과 시 온디맨드 강등을 적는다 [문서: antigravity.google/docs/rules/]. 두 파일 합산 토큰은 [추정] 한도의 상당 부분. `harness-export/SKILL.md:15-35` 는 "파일 이름이 달라서 둘 다 필요"만 설명하고 Codex 이중 도달은 적었지만(`:30-37`) Antigravity 이중 로드는 모른다. 얇은 `GEMINI.md`(`@./AGENTS.md`)는 COUNT=1 [실측 n=1, 모델 자기집계 — 약한 근거].

### P2 — 가독성/보강

- **P2-1.** `docs/research/2026-09-11-cross-harness-norm-integration.md:19` 가 `plugins/common/hooks/export_harness.py` 라고 적는다 — 5.2.0 이후 `tools/`. `:51` *"superpowers (Anthropic 공식 플러그인)"* 은 출처 없는 단정(같은 문서 다른 곳과 2026-08-27 조사는 `obra/superpowers` 로 적음) [추정: 오기]. 이 조사는 Gemini/Antigravity 공식 문서를 직접 대조하지 않았다(`[researched]` 수준).
- **P2-2.** `agy plugin import [gemini|claude]`, `plugin@marketplace`, `link` 가 README·targets.json 에 없다. `import claude` 가 Claude 플러그인(=킷)을 가져오는 경로일 수 있다 [추정, 미실행].
- **P2-3.** `docs/control-loop-transport.md` 의 로그 레시피·하네스 표는 Claude Code·Codex 두 열만 있다(Gemini/Antigravity 부재는 `:§3` "그 밖의 하네스 — 미검증으로 표기" 로 정직). 버전 인용 Codex 0.154.0 (현행 0.159.3).
- **P2-4.** 생성된 `AGENTS.md` 의 "이식하지 못하는 것" 은 Codex 칸에서 위 P0-2 로 낡고, Antigravity/Gemini 에서의 *"주입 없음 — 정적 파일만"* 문장이 없다.
- **P2-5.** `harness-export/SKILL.md` 전달 형태 표(`:13-21`)에 Antigravity 행이 없다(GEMINI.md+AGENTS.md 둘 다 읽는 하네스).

### P3 — 취향

- `CHANGELOG.md:3` 서두 *"claude-code-kit"* (개명 전 이름, 역사 서술이면 무해).
- `AGENTS.md`/`GEMINI.md` 블록 **밖** 헤더(제목·"재생성" 안내 3줄)와 EOF 추가는 게이트가 안 본다(설계상 소비자 영역; 이 레포가 도그푸딩하는 헤더도 동일).
- `export_harness.py --check` 는 줄 끝 `\r` 를 정규화해 통과시킨다(Python 유니버설 개행; 의도로 보임).

---

## Q 별 직접 답

### Q2. Gemini
- 킷이 Gemini 에 주는 것: **`GEMINI.md` 하나**(소비자가 `/harness-export` 를 돌린 레포의 파일). 스킬·훅·extension·에이전트 0.
- 공식 문서 대조: GEMINI.md 기본 파일명 ✅ · AGENTS.md 기본 미로딩 ✅ (`geminicli.com/docs/cli/gemini-md/`) · 설치본 0.49.0 번들도 동일(`DEFAULT_CONTEXT_FILENAME = "GEMINI.md"`, `AGENTS.md` 문자열 0). 킷의 "Gemini CLI 계열은 GEMINI.md" 는 **맞다.** 다만 이 문서는 "AGENTS.md 는 `context.fileName` 으로 추가하면 읽힌다"(= GEMINI.md 없이 AGENTS.md 하나로도 가능)는 점은 안내하지 않는다.
- `AGENTS.md` 와 `GEMINI.md` 가 거의 같은 이유는 문서화돼 있다(`harness-export/SKILL.md:15-35`, `export_harness.py:389-404`): 하네스별 파일명이 다르다. 문서화돼 있지 않은 것: ① Antigravity 이중 로드(P1-8) ② superpowers 식 *얇은 부트스트랩* 대안(`docs/research/2026-08-27-superpowers-distribution.md` 가 사실로 기록, 2026-09-11 조사가 "안 배워올 것"으로 정리하며 이중 로드를 고려하지 않음).

### Q3. Codex 두 경로
위 (a) 표. 요약: **스킬 15·`tools/`·`rules/` 파일은 동일, 훅·루트 plugin.json·매니페스트 `hooks` 필드만 ZIP 에서 빠진다.** 죽은 경로: `auto-dev` 의 `hooks/stop-validator.py`(fail-open, "Claude Code 전용" 주석 있음 → 무해), `control-loop/SKILL.md:185,213` 의 `hooks/examples/*`(opt-in 예시, ZIP 에서 부재), 스킬 도구 탐색 `~/.claude` 글롭(P1-6). 5.3.0 평탄화로 Codex 쪽에 깨진 것은 발견 못함(Codex 는 에이전트를 안 읽음). 단 ZIP·마켓플레이스 모두 `agents/` 15개가 **죽은 채로 실린다**(65/76 파일 중 15).

### Q4. Antigravity
(a) 표와 P1-3/P1-4. 공식 문서 대조: 플러그인 구조 `plugin.json`(필수 `name`)·`skills/<name>/SKILL.md`·`agents/`·`rules/`·`hooks.json`·`mcp_config.json` 나열 [문서: antigravity.google/docs/plugins]; 킷 생성물 `plugin.json` 은 `$schema`+`name`+`description` — 일치. 문서에 없는 것: `agy plugin validate`(CLI 에는 있음), Git URL 설치. `~/.agents/skills` 호환은 문서의 전역 경로 목록에 없다(워크스페이스 `.agents/skills` 만).

### Q5. 복제 표면과 표준
| 규범 텍스트 | 디스크상 복제 | 런타임 도달 |
| --- | --- | --- |
| 이식 대상 5룰 본문(예: DoD) | `rules/*.md`(원본) + `AGENTS.md` + `GEMINI.md` = **3** (grep: `definition-of-done` 고유 문장이 rules/ + AGENTS + GEMINI + `skills/auto-dev/SKILL.md` 에 등장 = 4) | Claude: 훅 1회. Codex(훅 신뢰 후): 훅 + AGENTS.md = **2**(킷이 감수한다고 명시). **Antigravity: AGENTS.md + GEMINI.md = 2**(미문서). Gemini: GEMINI.md 1 |
| `planning-protocol` | 위 3 + `docs/architecture/rules/planning-protocol.md`(해설 미러) = 4 | — |
| conventions(`kit2:` 블록) | `docs/conventions/*.md` + AGENTS + GEMINI(+ `CLAUDE.md` `@import`) | 동일 규칙 |
- 드리프트 방어: 룰 CHECKSUMS(§7), 미러 MIRROR.sha256, 진입점 §11. 즉 복제는 **전부 기계 게이트가 있다** — 약점은 복제 수가 아니라 *복제의 로드 중복*이다.
- 표준: `~/.agents/skills`/`.agents/skills` 는 Codex[문서]·Gemini CLI[문서]·Antigravity(워크스페이스)[문서]가 읽고 Claude Code 는 안 읽는다(메모리: 심링크로 해결). 킷은 이 경로를 사용도 안내도 하지 않는다(0건).
- "킷이 못 주는 것" 정직성: Codex 열은 정직하나 현행에서 낡았고(P0-2), Antigravity 는 *"주입 없음 — 정적 파일만"*·*"규범은 이중 로드"* 가 없다. Gemini 는 열 자체가 없다. README 의 총괄 문장 *"what a non-Claude-Code harness loses is dedicated executors and automatic blocking"* (`README.md:134`)은 Codex 에 대해 blocking 부분이 틀리고, Antigravity/Gemini 에 대해 *"자동 주입 상실"* 을 빠뜨린다.

### Q6. `harness-export` 드리프트 게이트 — 의도적 변경 실험
방법: `python3 plugins/common/tools/export_harness.py --check` (= `verify-done.sh §11` 가 호출하는 `./scripts/export-harness.sh --check` 와 동일 구현). 변형 후 `git checkout --` 복구, 매번 `git status` 빈 출력 확인.

| 변형 (AGENTS.md · GEMINI.md 각각) | rc |
| --- | --- |
| 규범 블록 본문 1글자 대문자화 | 1 |
| 마커 sha 한 자리 변경 | 1 |
| 규범 블록 한 줄 삭제 | 1 |
| 줄 끝 공백 1개 추가 | 1 |
| 블록 내 빈 줄 삽입 | 1 |
| 블록 내 zero-width 문자 삽입 | 1 |
| conventions(`kit2:`) 블록 본문 1글자 | 1 |
| conventions 마커 sha 변경 | 1 |
| conventions 블록 삭제 | 1 |
| 파일 삭제 / 빈 파일 | 1 / 1 |
| 블록 **밖**: 제목 줄 수정 | 0 (설계) |
| 블록 밖: 헤더 인용문 수정 | 0 (설계) |
| 블록 밖: EOF 한 줄 추가 | 0 (설계) |
| 블록 사이 사용자 문장 삽입 | 0 (설계) |
| 블록 내 줄 끝 `\r` | 0 (유니버설 개행 정규화 — P3) |

결과: **블록 안 변형 9종×2파일=18건 + 파일 삭제/빈 파일 2건 = 20건 전부 rc=1.** 통과한 것은 블록 밖 4종×2파일=8건과 줄 끝 `\r` 2건뿐. 복구 후 `--check` rc=0, `git status --short` 빈 출력. 기준선 `verify-done.sh` rc=0.

---

## (c) 개선 제안 — 우선순위

| # | 제안 | 예상 변경 파일 | 크기 |
| --- | --- | --- | --- |
| 1 | **P0-1 수정**: `harness-export/SKILL.md:161` 을 README 와 일치시킴(Antigravity = 스킬만, 규범은 진입점 파일) | `skills/harness-export/SKILL.md`, 버전 범프 + CHANGELOG + `build-targets.py --write` | S |
| 2 | **P0-2 정정**: "Codex 차단 안 됨" 문장 전부를 "0.153.4 에서 관측됨 / 0.159.3 에서 차단 확인(이번 감사 기록)" 으로 교체 + `targets.json` 의 `_omitted` 사유 갱신 + `export_harness.py` 의 해당 문구 → AGENTS/GEMINI 재생성 + 플러그인 description 재검토. **훅 이식 자체는 별도 결정**(제안 6) | `README.md`, `packaging/targets.json`, `plugins/common/tools/export_harness.py`, 생성물 2, `docs/codex-submission-checklist.md`, `child-session/SKILL.md`, `.claude-plugin/plugin.json`, `rules/CHECKSUMS`·미러(해당 시) | M |
| 3 | **P1-1 문서화**: README Codex 절에 "마켓플레이스 vs 디렉토리 ZIP" 표(훅 유무·규범 도착 경로) + ZIP 소비자에게 `/harness-export` 필수 안내. 게시 전에 | `README.md`, `docs/codex-submission-checklist.md` | S |
| 4 | **P1-2/P1-5 낡은 기록 닫기**: README:197 갱신, `targets.json` agy 절에 1.2.17 측정(진입점 양 파일 도달·스킬 인식·규칙 미도착·에이전트 `model:`) 기록 후 "막힘" 문구 정리 | `README.md`, `packaging/targets.json` | S |
| 5 | **P1-3 원인 정정 + 선택지 기록**: Antigravity 에이전트 미지원 원인을 `model:` 으로 정정(README·targets.json·CHANGELOG 다음 항목). 해결책 후보는 기록만: (a) 포기(권장), (b) Antigravity 전용 생성 루트(`model` 제거본) — `agents/` 가 Claude 와 같은 디렉토리라 별도 플러그인 루트 필요 | `README.md`, `packaging/targets.json` (a) / `build-targets.py`+신규 루트 (b) | S (a) / L (b) |
| 6 | **Codex `protect-sensitive` 이식 타당성**: 실측한 페이로드(`apply_patch`·`Bash`)로 파서 추가 + `hooks-codex.json` PreToolUse 항목. 대화형/PermissionRequest 경로·신뢰 흐름은 미측정이라 *"엄격히 측정 후 켠다"* 규약(`omit` 사유 문서) 유지 | `hooks/protect-sensitive.py`, `packaging/targets.json` (`hooks.events`), `hooks-codex.json`(생성), 테스트 | M |
| 7 | **스킬 도구 탐색을 하네스 중립으로**: SKILL.md 기준 상대(`../../tools/…`) 먼저, 그다음 `~/.claude`·`~/.codex`·`~/.gemini/config/plugins` 순회 | `skills/{harness-export,plan-task(references),auto-dev}`, 테스트, 문서 | M |
| 8 | **Gemini CLI 타겟**: `gemini-extension.json`(`name`,`version`,`contextFileName`)을 SSOT 에서 생성(`targets.json` 에 `gemini` 항목, `enabled:false` → 런타임 검증 후 승격). 스킬은 extension 의 `skills/` 가 같은 디렉토리 구조를 읽는지 검증 필요(문서는 지원) | `packaging/targets.json`, `scripts/build-targets.py`, 생성물 1 | M |
| 9 | **공용 스킬 경로 안내**: README "Other Harnesses" 에 `~/.agents/skills` 심링크 한 단락(Codex·Gemini CLI·Antigravity 워크스페이스 공통) — 네임스페이스(`hiway-kit:`)가 사라지는 점·중복 설치 위험(`README` 의 "never run two kits") 함께 명시 | `README.md` | S |
| 10 | **이중 로드 해소 실험**: 소비자 생성 `GEMINI.md` 를 얇은 `@./AGENTS.md` 로(`--entrypoints` 옵션/모드) — Gemini CLI import[문서]·Antigravity COUNT=1[실측 n=1] 근거. **반드시 Gemini CLI 쪽도 실측(키 복구 후) 뒤 적용** | `export_harness.py`(+테스트), `harness-export/SKILL.md`, 생성물 | M |
| 11 | **게이트 확장 후보**: README/targets.json 의 `[measured]` 라벨은 `docs/` 의 기록 id 를 가리키도록 하는 검사 — 단 `no-gate-integration.md` 원칙상 *새 게이트는 읽기 쉬워야 함*. 대안: `native-watch`/버전 범프 체크리스트에 "하네스 CLI 버전 재측정" 항목 | `scripts/verify-done.sh` 또는 `docs/conventions/release-process.md` | M |

권고 순서: 1 → 2(문구만) → 3 → 4 → 5(a) → 9 → 7 → 6 → 8 → 10. (1–5 는 문서·기록 교정이라 한 번의 패치 릴리스로 묶을 수 있다. 6–8 은 설계 결정이 필요.)

---

## (d) 확인하지 못한 것 / 한계

- **Gemini CLI 런타임 전부.** 이 머신의 키가 무효(400 `API_KEY_INVALID`, 재현). GEMINI.md 실도달·extension·훅·스킬 경로는 문서·번들 문자열 수준. 설치본 0.49.0 ≠ 문서 최신 v0.61.0.
- **디렉토리 ZIP 의 실제 포털 설치 흐름.** ZIP 을 풀어 로컬 마켓플레이스로 설치한 *근사*다. OpenAI 포털이 사용자에게 어떤 형태로 설치시키는지는 미확인.
- **Codex**: 훅 신뢰 대화형 승인 흐름, `PermissionRequest`, 인터랙티브 모드의 차단 동작, 플러그인 번들 에이전트 가능 여부(문서에 언급 없음), `marketplace.json` 상세 스키마, `shortDescription` 길이 한도(30 vs 240 — 출처 불일치, 미해결). `legacy .claude-plugin/marketplace.json` 읽기는 문서 나열만, 동작 미검증.
- **Antigravity**: 설치(영구) 플러그인과 워크스페이스 플러그인의 로드 차이(실측은 워크스페이스 위주, 에이전트·validate 는 격리 HOME 설치), 훅 형식, `plugin@marketplace` 소스 규격, `agy plugin import claude`(실행하지 않음), 이중 로드의 토큰 비용 실값(`COUNT` 는 모델 자기집계 n=1). 문서 날짜·버전 불명(페이지에 표시 없음).
- 모든 런타임 실측은 **n=1** 이다(Codex 차단 3회·양성 대조 1회 포함). 재현 수는 관측에 붙는 라벨이다(§측정 9).
- 웹 인용은 WebFetch 요약본이라 원문 대조가 안 된 구절이 있다(조사 에이전트 보고에 명시).
- Claude Code 쪽 동작(훅·플러그인 캐시)은 범위 밖이라 검증하지 않았다.

---

## 고지 (감사 중 발생한 상태 변화)

- 레포 파일 변경 0건 (`git status --short` 빈 출력, HEAD 불변). 드리프트 실험은 `git checkout -- <파일>` 로 매번 복구.
- **실수 1건**: `agy plugin import` 를 인자 없이 도움말 확인용으로 호출 → 실제 가져오기가 실행됐다. 결과는 *"already imported" skip ×2, superpowers 복사 오류, "No claude extensions found"* 로 **내용 변경은 없었다**(`~/.gemini/config/import_manifest.json` 의 `importedAt` 값 불변, mtime 만 갱신). 이후 `agy` 설치·실험은 전부 스크래치 `HOME` 또는 스크래치 워크스페이스에서만 했다.
- Codex 실험은 스크래치 `CODEX_HOME` 에서 했다. 인증 파일을 일시 복사했고 **각 사용 직후 삭제**(`find … -name auth.json` 0건 확인). 사용자 전역 `~/.codex`·`~/.claude`·`~/.gemini` 설정은 건드리지 않았다(위 import mtime 제외).
- 모델 호출 비용: codex ≈ 8회(소형), agy ≈ 8회, gemini 1회(실패). 스크래치패드: `/private/tmp/claude-501/-Users-hw-orca-workspaces-hiway-kit-audit-harness/dd96a387-3461-4622-8fa4-51a4933f8f6d/scratchpad/` (`hiway-kit.zip`, 프로브 디렉토리).

## 재현 명령 (핵심)

```bash
# Codex PreToolUse 차단 (격리 CODEX_HOME, 인증 복사 후 삭제)
CODEX_HOME=$SCRATCH/ch codex exec --dangerously-bypass-hook-trust --skip-git-repo-check \
  "Run exactly this shell command: touch blocked.txt ..." </dev/null   # hooks.json: PreToolUse -> exit 2
# ZIP vs 마켓플레이스
python3 scripts/build-codex-zip.py --out $SCRATCH/hiway-kit.zip && unzip -l $SCRATCH/hiway-kit.zip
# agy 에이전트 이분 탐색 (격리 HOME)
HOME=$SCRATCH/h agy plugin install $SCRATCH/probe && HOME=$SCRATCH/h agy agents
# agy 진입점/규칙/이중 로드
agy -p '…' --output-format json --print-timeout 90s </dev/null     # AGENTS.md·GEMINI.md 토큰, COUNT
# 드리프트 게이트
python3 plugins/common/tools/export_harness.py --check
```
