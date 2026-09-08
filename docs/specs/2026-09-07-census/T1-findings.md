# T1 — 규범 축 전수 문서 감사

읽기 전용 감사. 스코프 26개 파일. 정렬 대상: `docs/specs/2026-09-07-hiway-program-design.md`
(commit `c707729`, 브랜치 `This-HW/planning-control-session` — **이 워크트리의 `main`(`dd63b44`)에는
없다.** `git show c707729:docs/specs/2026-09-07-hiway-program-design.md`로 체크아웃 없이 읽었다.
D-1~D-21 전부 확인함.

---

## 1. 커버리지 표 (26/26)

| # | 파일 | 판정 | 한 줄 근거 |
|---|------|------|-----------|
| 1 | `AGENTS.md` | CONFLICT | `rules/tool-usage-priority.md`를 원문 그대로 임베드(§406-421) — 호스트 bypass 모드 지시와 충돌(D-18 대상), `AskUserQuestion`을 4곳(§260,293,331,352)에서 P0 탈출구로 전제(비-Claude-Code 하네스엔 그 툴이 없을 수 있음) |
| 2 | `CLAUDE.md` | CONFLICT | `docs/conventions/*.md`를 `@import`해야 한다는 자신의 설계(W-022 R7)를 어기고 손 복제 중이며, Release Checklist(§426-457)가 `docs/conventions/release-process.md`·`scripts/bump-version.sh`(W-022 R8)보다 낡은 수동 절차를 지시 |
| 3 | `docs/architecture/phase-gate-pattern.md` | OK | 커뮤니티 패턴임을 명시하고 정본(`agent-system.md` Phase Gate)과 내용 일치, 재정의 없음 |
| 4 | `docs/architecture/rules/agent-delegation-chain.md` | OK | 정본을 설명만 하고 재정의하지 않음; DELEGATION_SIGNAL 폐기 기록도 역사 서술로 적절히 보존 |
| 5 | `docs/architecture/rules/agent-system.md` | STALE | §1 "3-Tier Architecture"가 v2.7.0(commit `284c801`)에 삭제된 5개 도메인 플러그인(frontend/infra/ops/data/integration)을 현재형으로 서술, 스킬 수도 "16"(실제 19) |
| 6 | `docs/architecture/rules/code-quality.md` | OK | 정본과 완전 일치, 예시만 추가 |
| 7 | `docs/architecture/rules/mcp-usage.md` | CONFLICT | §8 "NotebookLM 활용 규칙"이 3줄 위 "정본 원칙: 특정 서버 설치를 가정하지 않는다"와 정면 모순 (D-19 대상) |
| 8 | `docs/architecture/rules/planning-check.md` | OK | CLAUDE.md가 기록한 과거 결함(Notion/Figma MCP 순서 강제)이 이미 수정돼 "설치돼 있을 때만" 조건부로 서술됨 |
| 9 | `docs/architecture/rules/planning-protocol.md` | OK | DELEGATION_SIGNAL 잔재를 역사적 정정 각주로 명시(§81-83), 정본과 일치 |
| 10 | `docs/architecture/rules/ssot.md` | CONFLICT | 전체가 TypeScript 특정 예시(`@/config/env`, `src/infrastructure/errors/*.ts`) — 소비자 중립성 위반 (D-19 대상) |
| 11 | `docs/architecture/rules/task-resume.md` | OK | 정본과 일치, 재정의 없음 |
| 12 | `docs/architecture/rules/tool-usage-priority.md` | CONFLICT | 문서 전체가 폐기 예정 규범(D-18)의 상세 해설 — 호스트 bypass 모드 지시와 충돌하는 규범을 그대로 옹호 |
| 13 | `evals/scenarios/define-business-logic/point-service-rules/expect.json` | OK | fixture(`domain.md`)가 인가 로직을 요구하지 않아 CALC/VAL/STATE/POL만 검사하는 것이 타당; `_designNote`가 W-023 수정 근거를 실측으로 남김 |
| 14 | `plugins/common/rules/agent-delegation-chain.md` | OK | Standing Authorization·On Receiving Subagent Output 모두 스킬 주도 모델과 일치, DELEGATION_SIGNAL은 폐기 기록만 남음 |
| 15 | `plugins/common/rules/agent-system.md` | DUP | "Agent Selection by Keyword" 표(§14-22)가 네이티브 시스템 프롬프트가 이미 제공하는 정보의 재기술 (D-18 대상) |
| 16 | `plugins/common/rules/code-quality.md` | OK | 내용 자체는 일관되고 완결됨(예시가 TS이지만 "규칙"이 아니라 "예시"로 한정돼 있어 §17 findings 참고) |
| 17 | `plugins/common/rules/definition-of-done.md` | OK | 자기 완결적, 다른 규범과 충돌 없음 |
| 18 | `plugins/common/rules/feedback-loop.md` | OK | 짧고 명확, opt-in/fail-open 명시 |
| 19 | `plugins/common/rules/loop-engineering.md` | CONFLICT | §종료 가드가 `AskUserQuestion`을 P0 탈출구로 전제(§40) — 헤드리스/디스패치 호스트에선 존재하지 않거나 응답 불가할 수 있음 |
| 20 | `plugins/common/rules/mcp-usage.md` | CONFLICT | §NotebookLM Rules(§65-71)이 §MCP Servers 원칙(§6 "never assume a server is present")과 자기모순 (D-19 대상) |
| 21 | `plugins/common/rules/parallel-worktree.md` | OK | `DELEGATE_TO: git-workflow`는 CLAUDE.md가 명시적으로 보존을 선언한 에스컬레이션 산문(기계 계약 아님) |
| 22 | `plugins/common/rules/planning-check.md` | CONFLICT | §3(§17)이 `AskUserQuestion`을 유일 탈출구로 전제 — 위 19/20와 같은 결함 클래스 |
| 23 | `plugins/common/rules/planning-protocol.md` | CONFLICT | P0 프로토콜 2곳(§16, §37)이 `AskUserQuestion` 하드코딩 |
| 24 | `plugins/common/rules/ssot.md` | CONFLICT | §6(임포트 예시), §16-20(에러 로깅 디렉터리 레이아웃)이 TypeScript 전제 (D-19 대상) |
| 25 | `plugins/common/rules/task-resume.md` | OK | 정본, 조건부 주입 로직과 일치, 문제 없음 |
| 26 | `plugins/common/rules/tool-usage-priority.md` | CONFLICT | 전체가 "NEVER use Bash for file operations" — bypass 모드 호스트 지시("read files with cat, head, or sed -n … rather than using the dedicated Read, Edit, or Write tools")와 정면 충돌. 설계문서 §9.2(a)가 이미 실측한 사례 (D-18: 삭제 결정 존재) |

**요약**: OK 12 / CONFLICT 10 / DUP 1 / STALE 1 / UNABSTRACTED 0 / ORPHAN 0 / UNKNOWN 0 = 26.

---

## 2. 발견 상세

### F1 — `tool-usage-priority.md`(정본+미러) vs bypass 모드 호스트 지시 [이미 D-18로 결정됨]

- **무엇**: `plugins/common/rules/tool-usage-priority.md:5-11`, `docs/architecture/rules/tool-usage-priority.md:7-18`,
  `AGENTS.md:406-421`(cck 블록 안에 원문 그대로 임베드) 모두 "NEVER use Bash for file
  operations. ALWAYS use the dedicated tool (Read/Edit/Write/Glob/Grep)."을 규정.
- **어디가**: 위 3개 파일 전체.
- **왜 문제**: 설계문서 §9.2(a)가 실측한 대로, `--permission-mode bypassPermissions` 호스트의
  시스템 프롬프트는 반대로 "read files with cat, head, or sed -n, search with grep and
  find … rather than using the dedicated Read, Edit, or Write tools"를 지시한다. 세션에
  주입된 규범이 호스트 지시와 정면 충돌한다.
- **무엇과 충돌**: bypass 모드 호스트 시스템 프롬프트(원문은 설계문서 §9.2(a) 인용, 이
  워크트리에선 직접 재현 불가 — 이 세션은 대화형 모드라 반대 지시("Read 도구 우선")가
  적용돼 있음을 이 세션 자체의 Bash 도구 설명으로 교차 확인했다).
- **권고**: 삭제. 이미 D-18/D-21이 삭제를 결정했고 W-025-12에 작업 항목이 있다. 추가 결정
  불필요 — 실행만 남음.

### F2 — `AskUserQuestion` 하드코딩이 헤드리스/디스패치 호스트와 충돌 [신규, 결정 없음]

- **무엇**: P0/모호함 에스컬레이션의 유일한 메커니즘으로 `AskUserQuestion` 툴 호출을
  전제하는 산문이 최소 5개 지점에 있다:
  - `plugins/common/rules/agent-delegation-chain.md:45`
  - `plugins/common/rules/loop-engineering.md:40`
  - `plugins/common/rules/planning-protocol.md:16,37`
  - `plugins/common/rules/planning-check.md:17`
  - 미러: `docs/architecture/rules/agent-delegation-chain.md:97`,
    `docs/architecture/rules/planning-protocol.md:67,81,83`,
    `docs/architecture/rules/planning-check.md:110`
  - `AGENTS.md:260,293,331,352`(cck 블록 — Codex·OpenCode·Pi·Hermes 등 비-Claude-Code
    하네스에도 그대로 이식됨)
- **왜 문제**: 이 감사 자체가 실측 사례다 — 이 세션은 orca가 디스패치한 워커이고, 호스트
  프리앰블이 "**NEVER use AskUserQuestion**; use `orca orchestration ask`. AskUserQuestion
  opens a local TUI prompt that the coordinator cannot see and cannot answer — your session
  will hang forever"라고 명시한다. 헤드리스 디스패치·`-p` eval 실행·orca 워커 등
  비대화형/비원본세션 컨텍스트에서 `AskUserQuestion`은 존재하지 않거나 응답 불가능하다.
  이는 F1(tool-usage-priority)과 **같은 결함 클래스** — "특정 호스트 런타임에서만 참인
  가정을 전 하네스 규범에 하드코딩" — 이지만 D-18은 tool-usage-priority만 다루므로
  이 인스턴스는 다루지 않는다.
- **무엇과 충돌**: (a) orca 워커 호스트 프리앰블(이 세션 자체, 원문 위 인용), (b) 하네스
  중립을 표방하는 `AGENTS.md`가 Claude-Code 전용 툴명을 리터럴로 이식.
- **권고**: 축약(추상화). P0 에스컬레이션 산문을 툴 이름이 아니라 **역할**로 재기술 —
  예: "AskUserQuestion(대화형) 또는 그 호스트의 동등 수단(비대화형 디스패치라면
  에스컬레이션 채널)으로 즉시 질문한다." D-9가 이미 "4블록 브리프는 워커가 완료 조건을
  모르면 에스컬레이션한다"는 유사 원칙을 세워뒀으므로 그 어휘와 맞출 수 있다.

### F3 — `mcp-usage.md`(정본+미러) NotebookLM 자기모순 [이미 D-19로 결정됨]

- **무엇**: `plugins/common/rules/mcp-usage.md:65-71` "## NotebookLM Rules" (Source 50개 상한
  등 특정 서버 세부 규정), `docs/architecture/rules/mcp-usage.md:157-170` "## 8. NotebookLM
  활용 규칙"(동일 내용).
- **어디가**: 두 파일의 해당 섹션.
- **왜 문제**: 같은 파일 6줄 위(`plugins/common/rules/mcp-usage.md:6`, 미러는 §5 "정본
  원칙")가 "never assume a server is present / MCP는 스킬에서만, 미설치 시 환각 유발"이라고
  말하면서, 바로 그 파일이 NotebookLM이라는 특정 서버의 수치 제한을 규범으로 못박는다.
  자기모순.
- **무엇과 충돌**: 같은 파일 내부(자기 자신), 그리고 CLAUDE.md의 "never assume a specific
  plugin/MCP is present" 북극성.
- **권고**: 삭제(정본), 정본 삭제 후 `sync-rule-mirror.sh --regenerate`로 미러 반영.
  D-19/25-13이 이미 이 작업을 배정함 — 추가 결정 불필요.

### F4 — `ssot.md`(정본+미러) TypeScript 특정 예시 [이미 D-19로 결정됨]

- **무엇**: `plugins/common/rules/ssot.md:6,16-20`, `docs/architecture/rules/ssot.md:29-63,
  78-90,108-133` — `import { API_URL } from "@/config/env"`, `src/infrastructure/errors/*.ts`
  4파일 레이아웃 등 전부 TypeScript/Node 프로젝트 전제.
- **왜 문제**: 이 킷은 "어떤 언어의 프로젝트에도 설치되는" 범용 플러그인(CLAUDE.md 북극성)
  인데, SSOT 원칙 자체(언어 중립)를 TypeScript 문법으로만 예시해 Python/Go/Rust 등
  프로젝트에 설치된 소비자에게는 코드가 그대로 적용 불가능한 이질적 규범으로 읽힌다.
- **무엇과 충돌**: CLAUDE.md "Who this is for" 북극성.
- **권고**: 축약(언어 중립화) — 원칙 문장만 남기고 코드 예시는 삭제하거나 언어를 pseudocode로
  치환. D-19/25-13이 이미 배정. 추가 결정 불필요.

### F5 — `agent-system.md`(정본) "Agent Selection by Keyword" 표 [이미 D-18로 결정됨]

- **무엇**: `plugins/common/rules/agent-system.md:14-22`.
- **왜 문제**: 설계문서 §9.2(b) 실측대로, Claude Code 네이티브 시스템 프롬프트가 이미
  33개 에이전트·19개 스킬을 `MUST USE when:` 트리거까지 붙여 나열한다. 이 표는 그 정보의
  재기술이며 세션 주입 예산만 소비한다.
- **권고**: 삭제. D-18/D-21이 이미 결정("agent-system.md의 Agent Selection by Keyword 표
  제거"). 미러(`docs/architecture/rules/agent-system.md:65-85` "3. 에이전트 키워드 매핑")도
  같이 정리 대상 — 미러가 정본을 재정의하는 사례이므로 정본 삭제 시 미러도 규모를 맞춰야
  드리프트가 재발하지 않는다.

### F6 — `docs/architecture/rules/agent-system.md` §1 "3-Tier Architecture"가 v2.7.0에 삭제된 구조를 서술 [신규, 결정 없음]

- **무엇**: `docs/architecture/rules/agent-system.md:7-29`. Tier 2로 "plugins/{domain}/
  (frontend 4 agents 1 skill, infra 7 agents 1 skill, ops 14 agents 5 skills, data 4
  agents 3 skills, integration 4 agents)"를 현재형으로 서술. 같은 다이어그램(§15)이
  스킬 수를 "16"이라 적음.
- **왜 문제**: `git log --all --oneline --diff-filter=D -- plugins/frontend plugins/infra
  plugins/ops plugins/data plugins/integration` → commit `284c801`
  "chore: consolidate to core-only — remove 5 untested/frozen domain plugins (2.7.0)"가
  이 5개 디렉터리를 전부 삭제했음을 확인(§4 실측 로그). 현재 `plugins/`에는 `common`
  하나뿐(`ls plugins/` 실측). 이 파일은 그 이후에도 최소 1회(`d054723`, W-022
  DELEGATION_SIGNAL 정리) 편집됐지만 §1은 그때도 고쳐지지 않았다 — 편집자가 자기
  담당 섹션(§4 DELEGATION_SIGNAL)만 고치고 나머지를 검토하지 않은 전형적 "부분 편집이
  전체를 최신으로 착각하게 만드는" 패턴. 스킬 수 "16"도 실제 19(`find
  plugins/common/skills -name SKILL.md | wc -l` 실측)와 불일치.
  CLAUDE.md 자신의 "2-Tier Model"(Tier 1: common, Tier 2: project-local)과도 정면으로
  다른 계층 구조를 주장한다.
- **무엇과 충돌**: 현재 저장소 구조(`plugins/common`만 존재), `CLAUDE.md`의 2-Tier 서술.
- **권고**: 축약 — §1을 CLAUDE.md의 2-Tier Model과 일치시키고 스킬 수를 19로 수정.
  **새 결정 필요**: D-1~D-21 어디에도 "미러 문서의 사실관계 정확성 재검증"이 없다.
  W-025/26/27 배치 중 하나에 "미러 9종 사실관계 스윕(구조·카운트)"을 추가하거나,
  최소한 `sync-rule-mirror.sh`가 체크섬 일치는 보장해도 **내용의 사실 정확성은 보장하지
  않는다**는 한계를 CLAUDE.md의 "Rules have a long-form mirror" 절에 명시할 것을 제안한다.

### F7 — `CLAUDE.md`가 자신이 문서화한 `@docs/conventions/*.md` import 설계를 따르지 않음 [신규, 결정 없음]

- **무엇**: `CLAUDE.md` 전체에 `@docs/conventions` 문자열이 0회 등장(`grep -n
  "@docs/conventions" CLAUDE.md` → 무출력, §4 실측 로그). 대신 `CLAUDE.md:303-324`
  ("설정값으로 경로를 만들면...")과 `CLAUDE.md:344-360`("드리프트 게이트는 셋이고...")이
  `docs/conventions/path-containment.md`, `docs/conventions/no-gate-integration.md`의
  내용을 손으로 거의 그대로 복제(diff 확인, §4). `CLAUDE.md:362-424`("Lint is one
  ruleset", "Rules have a long-form mirror", "Shell is linted too")도 각각
  `docs/conventions/lint-single-ruleset.md`, `rules-mirror.md`, `shell-lint.md`와 동일
  패턴(손 복제, import 아님). `docs/conventions/reference-vs-judgment.md`의 내용은
  `CLAUDE.md`에 전혀 없음(완전 누락).
- **왜 문제**: `docs/conventions/README.md:5`("`CLAUDE.md` pulls these in via
  `@docs/conventions/<file>.md` imports instead of repeating them")와
  `CHANGELOG.md:270-272`(W-022 R7 항목: "`docs/conventions/*.md`로 분리해 `CLAUDE.md`는
  `@docs/conventions/<file>.md` import로 읽고...")가 명시한 설계와 실제 `CLAUDE.md`가
  다르다. `scripts/export-harness.sh --check`는 `AGENTS.md`의 두 마커 블록(rules-v1.4.0,
  conventions-v1.0.0)만 검사하며 `CLAUDE.md`의 import 여부는 검사 대상이 아니다(§4
  실측 — `verify-done.sh`에도 `CLAUDE.md` 내용 검사 없음, grep 결과 CHANGELOG 언급
  1건뿐). 즉 "생성물이 SSOT와 일치하는가"를 묻는 기존 3개 드리프트 게이트(§11·§13·§14)
  어디에도 이 케이스가 걸리지 않는다 — CLAUDE.md 자신이 §9.3에서 경고한 "검사 대상이
  아닌 것은 결코 red가 되지 않는다"의 또 다른 사례.
- **무엇과 충돌**: `docs/conventions/README.md:5`, `CHANGELOG.md:267-279`(W-022 R7 항목).
- **권고**: 이동(수정) — `CLAUDE.md`의 6개 손-복제 섹션을 실제 `@docs/conventions/<file>.md`
  import로 치환하고 `reference-vs-judgment.md` 참조를 추가. **새 결정 필요**: D-1~D-21
  범위 밖. W-025(현재 "위생·구조 정비" 배치)에 "CLAUDE.md → docs/conventions/ import
  전환 + 드리프트 게이트 추가(가능하면 §11 확장, 새 번호는 아님 — 같은 SSOT-생성물
  질문이므로 CLAUDE.md 자신의 '통합하지 않는다' 원칙과도 맞음)" 항목 추가를 제안한다.

### F8 — `CLAUDE.md` Release Checklist가 `scripts/bump-version.sh`(W-022 R8) 이전 수동 절차를 지시 [F7의 하위 사례, 결정 없음 — F7에 흡수 제안]

- **무엇**: `CLAUDE.md:426-457` "Release Checklist"가 "plugin.json → version 필드를
  손으로 올려라"(§454-457 코드블록)와 "버전을 올렸으면 `python3
  scripts/build-targets.py --write`를 따로 실행하라"(§437-440)를 **별개의 두 수동 단계**로
  지시한다.
- **왜 문제**: `scripts/bump-version.sh`(commit `a630ab3`, W-022 R8)는 정확히 이 두 단계를
  하나로 묶고 자기검증까지 추가한 스크립트다 — 스크립트 자신의 주석(§4-14)이 "SSOT만
  올리고 재생성을 잊는 실수"(v2.15.0 실제 사고)를 예방하기 위해 만들어졌다고 명시한다.
  `docs/conventions/release-process.md:9`는 이미 "**버전은 `scripts/bump-version.sh
  <version>`로 올린다** (수동으로 SSOT를 직접 고치지 마라)"로 갱신돼 있다. `CLAUDE.md`는
  이 갱신 이전 버전의 절차를 그대로 유지 중 — 이 파일을 따르는 기여자는 정확히
  `bump-version.sh`가 방지하려는 실수를 재현할 위험이 있다.
- **무엇과 충돌**: `docs/conventions/release-process.md:9`, `scripts/bump-version.sh` 자체.
- **권고**: F7과 함께 이동 — `CLAUDE.md`의 Release Checklist 섹션을
  `@docs/conventions/release-process.md` import로 치환하면 이 불일치는 자동 해소된다.
  별도 결정 불필요, F7 실행에 포함.

### F9 — `CLAUDE.md` Key Skills 표가 19개 중 17개만 나열, `brainstorming` 누락 [경미, 신규]

- **무엇**: `CLAUDE.md:53-73` 표에 17개 스킬만 나열(`plan-task`부터 `skill-forge`까지
  카운트, §4 실측). 실제 `plugins/common/skills/*/SKILL.md`는 19개(§4 실측). 누락 2종:
  `brainstorming`, `using-claude-code-kit`.
- **왜 문제**: `using-claude-code-kit`은 세션 시작 메타스킬이라 사용자 직접 호출 표에서
  빠지는 것이 합리적일 수 있으나, `brainstorming`은 CLAUDE.md 자신이 "Workflow Chain
  (kit)"에서 `brainstorming → plan-task → auto-dev`의 첫 단계이자 HARD-GATE로 지목하는
  핵심 스킬이다(세션 시작 시 주입되는 `using-claude-code-kit/SKILL.md`에서도 동일하게
  강조됨, 시스템 프롬프트 컨텍스트로 확인). 이 표에서만 빠져 있어 CLAUDE.md를 훑는
  사람에게 그 스킬의 존재가 드러나지 않는다.
- **무엇과 충돌**: 없음(다른 문서와의 충돌이 아니라 자체 누락) — STALE보다는 표 자체의
  완전성 결함.
- **권고**: 축약(보강) — 표에 `brainstorming` 행 추가. 저비용·저위험 수정이라 결정 없이도
  바로 처리 가능한 수준이지만, T1은 감사이므로 실행하지 않고 보고만 한다.

---

## 3. 계획 정렬 (D-1~D-21 대조)

| 발견 | 흡수 결정 | 상태 |
|------|-----------|------|
| F1 (tool-usage-priority 삭제) | **D-18** | 이미 결정됨, W-025-12 실행 대기 |
| F2 (AskUserQuestion 하드코딩) | 없음 | **신규 결정 필요** — 제안: "P0 에스컬레이션 산문은 툴 이름이 아니라 호스트 무관 역할로 기술한다"를 D-18(호스트 충돌 규범 처리)의 자매 결정으로 추가, 또는 D-21 티어 배정 작업 시 `planning-protocol`·`planning-check`·`loop-engineering`·`agent-delegation-chain` 4종의 P0 절을 함께 축약 |
| F3 (mcp-usage NotebookLM) | **D-19** | 이미 결정됨, W-025-13 실행 대기 |
| F4 (ssot TypeScript) | **D-19** | 이미 결정됨, W-025-13 실행 대기 |
| F5 (agent-system 키워드 표) | **D-18** | 이미 결정됨, D-21 티어표에도 "agent-system → reference(축약)"로 반영됨 |
| F6 (agent-system 미러 3-Tier 허구 구조) | 없음 | **신규 결정 필요** — 제안: "미러 9종의 사실관계(구조·카운트)를 W-025/26/27 중 한 배치에서 1회 스윕하고, `sync-rule-mirror.sh`의 체크섬 보장 범위(형식 동기화이지 사실 정확성 아님)를 CLAUDE.md에 명시한다" |
| F7 (CLAUDE.md가 conventions import 미사용) | 없음 | **신규 결정 필요** — 제안: "CLAUDE.md의 6개 conventions 섹션을 `@docs/conventions/<file>.md` import로 치환하고, 드리프트 검사를 기존 게이트(§11 계열, 통합하지 않는다는 CLAUDE.md 원칙 유지)에 추가한다" — W-025(위생·구조 정비 배치)의 성격과 정확히 맞음 |
| F8 (Release Checklist 구식) | 없음 (F7에 흡수) | F7 실행 시 자동 해소 |
| F9 (Key Skills 표 누락) | 없음 | 경미 — 별도 결정 불필요, 아무 배치에서나 1줄 수정 가능 |
| (참고) 모든 rules/*.md에 `tier:` frontmatter 없음 | **D-17** | 이미 결정됨(25-11), 13종 전부 미착수 상태 확인(§4 실측) — 예상된 상태, 새 발견 아님 |

---

## 4. 실측 로그

```
# 워크트리/설계문서 위치 확인
$ pwd && git log -1 --format='%H %s' && git status
/Users/hw/orca/workspaces/claude-code-kit/census-T1
dd63b44 fix(ci): gitleaks private-project-names 오탐 해소 — 테스트 식별자 개명
(clean)

$ find / -iname "*hiway-program-design*" 2>/dev/null
(census-T1 워크트리에는 없음 — torpedo 워크트리와 플러그인 캐시 사본만 존재)

$ git log --all --oneline -- 'docs/specs/2026-09-07*'
c707729 docs(spec): §9 주입 예산 재설계 — 규범 활성화를 규범 자신이 선언 (D-17~D-21)
fe0806c docs(spec): §8 구조 감사 추가 — 추상화·교체가능성 결정 5건 (D-12~D-16)
c84ab28 docs(spec): 하이웨이 프로그램 설계 최종본 — W-025~027 (하네스 중립 전환)

$ git merge-base --is-ancestor c707729 HEAD  → 실패(NOT ancestor)
$ git branch --all --contains c707729 → This-HW/planning-control-session (main 아님)
→ 설계문서는 main에 머지되지 않은 별도 브랜치에 있음. git show로 체크아웃 없이 읽음:
$ git show c707729:docs/specs/2026-09-07-hiway-program-design.md > (scratchpad)/hiway-design.md
(792줄, D-1~D-21 전부 확인)

# 스킬/에이전트/룰 카운트 실측
$ find plugins/common/skills -maxdepth 2 -name "SKILL.md" | wc -l
19
$ find plugins/common/agents -name "*.md" | wc -l
33
$ ls plugins/common/rules/*.md | wc -l
13
$ grep -m1 '"version"' plugins/common/.claude-plugin/plugin.json
  "version": "2.17.0",

# CLAUDE.md Key Skills 표 행 수(수동 카운트, plan-task~skill-forge) = 17
# (brainstorming, using-claude-code-kit 누락 확인)

# AGENTS.md 드리프트 게이트 자체 점검 (export-harness --check, 읽기 전용)
$ bash scripts/export-harness.sh --check
[export-harness] ✓ AGENTS.md 규범 블록 최신 (rules-v1.4.0 sha256:0a03ad2f1a...)
[export-harness] ✓ AGENTS.md conventions 블록 최신 (conventions-v1.0.0 sha256:fdd35efc...)
→ AGENTS.md는 rules/ 및 docs/conventions/의 2개 인라인 파일과 완전 동기화돼 있음.
  즉 AGENTS.md의 CONFLICT(F1,F2)는 "드리프트"가 아니라 정본 자체의 결함이 충실히
  전파된 것 — 정본을 고치고 재생성하면 자동 해소됨.

# CLAUDE.md가 docs/conventions/*.md를 @import 하는지 확인
$ grep -n "@docs/conventions\|@docs" CLAUDE.md
(무출력 — 0건)
$ grep -n "conventions" CLAUDE.md
(무출력 — 0건, 섹션 제목에도 "conventions" 문자열 없음)
$ diff <(sed -n '303,324p' CLAUDE.md) docs/conventions/path-containment.md
(끝부분 문구만 다름 — 나머지 내용 거의 동일한 손 복제 확인)
$ diff <(sed -n '/^### Lint is one ruleset/,/^### Rules have a long/p' CLAUDE.md) \
       docs/conventions/lint-single-ruleset.md
(CLAUDE.md 쪽에 헤더 한 줄 추가된 것 외 본문 동일 — 손 복제 확인)
# reference-vs-judgment.md 내용이 CLAUDE.md 어디에도 없음:
$ grep -n "reference-vs-judgment\|superpowers.*audit\|version-bump.json" CLAUDE.md
(무출력)

# CLAUDE.md Release Checklist가 최신 절차(bump-version.sh)를 반영하는지
$ grep -n "bump-version" CLAUDE.md
(무출력 — 0건)
$ ls scripts/bump-version.sh
scripts/bump-version.sh (존재함)
$ git log --oneline -- scripts/bump-version.sh docs/conventions/release-process.md | head -4
b0ebb02 feat(W-022 trackB S2): docs/conventions/ SSOT + AGENTS.md second cck2: block (R7)
20806a4 WIP(W-022 trackB S2): in-progress conventions extraction, not final
a630ab3 feat(W-022 trackB S1): bump-version.sh -- prevent, not just detect (R8)
$ sed -n '1,15p' docs/conventions/release-process.md
(9번째 줄: "**버전은 `scripts/bump-version.sh <version>` 로 올린다** (수동으로 SSOT를
직접 고치지 마라)." — CLAUDE.md는 이 문장이 없고 구식 수동 절차만 있음 확인)

# agent-system.md 미러의 3-Tier 도메인 플러그인이 실존하는지
$ ls plugins/
common
$ git log --all --oneline --diff-filter=D -- plugins/frontend plugins/infra plugins/ops \
    plugins/data plugins/integration
284c801 chore: consolidate to core-only — remove 5 untested/frozen domain plugins (2.7.0) (#3)
$ git log --oneline -- docs/architecture/rules/agent-system.md | tail -3
d054723 feat: DELEGATION_SIGNAL 계약 폐기 완료 (W-022 Track A R1)   ← 284c801 이후에도 편집됐으나 §1 미수정
8254231 fix: MCP 이식성 ...
33a40a3 feat: W-004 — Rules Injection 최적화

# AskUserQuestion 하드코딩 지점 전수 검색
$ grep -rn "AskUserQuestion" plugins/common/rules/*.md docs/architecture/rules/*.md \
    AGENTS.md CLAUDE.md
plugins/common/rules/agent-delegation-chain.md:45
plugins/common/rules/loop-engineering.md:40
plugins/common/rules/planning-protocol.md:16
plugins/common/rules/planning-protocol.md:37
plugins/common/rules/planning-check.md:17
docs/architecture/rules/agent-delegation-chain.md:97
docs/architecture/rules/planning-protocol.md:67,81,83
docs/architecture/rules/planning-check.md:110
AGENTS.md:260,293,331,352
(CLAUDE.md 자체엔 없음 — AGENTS.md의 cck 블록에만 이식됨)

# orca 문자열이 규범에 있는지 (D-6 정합성 확인 — 있으면 안 됨)
$ grep -rn "orca" plugins/common/rules/*.md docs/architecture/rules/*.md AGENTS.md CLAUDE.md
(무출력 — 0건, D-6 정합)

# DELEGATION_SIGNAL 잔재가 기계 계약으로 남아있는지 (전수 검색 — 이력 서술만이어야 함)
$ grep -rln "DELEGATION_SIGNAL" AGENTS.md CLAUDE.md docs/architecture/rules/*.md \
    plugins/common/rules/*.md
docs/architecture/rules/agent-system.md
docs/architecture/rules/planning-protocol.md
docs/architecture/rules/agent-delegation-chain.md
plugins/common/rules/agent-delegation-chain.md
CLAUDE.md
→ 5개 파일 전부 확인 결과 전부 "폐기 기록"류 역사 서술이고 TYPE/TARGET 파싱 지시는
  없음(각 파일 본문 직접 읽어 확인). 기계 계약 잔재 0건.

# NotebookLM/TypeScript 자기모순 확인
$ grep -rn "NotebookLM" plugins/common/rules/*.md docs/architecture/rules/*.md
plugins/common/rules/mcp-usage.md:65
docs/architecture/rules/mcp-usage.md:157,159
(각 파일 내 "never assume a server is present"류 원칙 문장과의 거리 3~6줄 —
 파일 직접 읽어 확인)

# eval 시나리오 fixture와 expect.json 정합성
$ cat evals/scenarios/define-business-logic/point-service-rules/fixture/domain.md
(포인트 적립/사용 — 인가·역할 로직 없음 → AUTH- 카테고리 미검사가 타당함을 fixture로 확인)
```

---

## 5. 미확인 / UNKNOWN 사항

없음 — 26개 파일 전부 직접 읽고 실측 근거를 남겼다. 단, F6·F7의 "새 결정 필요" 제안은
T2~T5 다른 트랙(코드/스크립트/eval 축)의 발견과 합쳐 컨트롤 세션이 최종 판단해야 하는
영역이므로, 이 보고서는 판단이 아니라 재료로만 제출한다.
