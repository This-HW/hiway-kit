---
status: current
as_of: 2026-10-05
---

# CHANGELOG 조각 — W2 harness (5.4.0 조립용)

컨트롤이 `CHANGELOG.md` 의 `## [5.4.0]` 에 조립한다. 발견 ID 는 같은 폴더 `audit/*.md` 를 가리킨다.

### Added — Codex 스킬 메타데이터 `agents/openai.yaml` 파생 (C-X1)

- `scripts/build-targets.py` 가 각 스킬의 `SKILL.md` frontmatter 에서 `skills/<name>/agents/openai.yaml` 을
  생성한다 — `interface.display_name`(=`name`)·`interface.short_description`(=`description` 첫 문장), 그리고
  `disable-model-invocation: true` 인 스킬(`harness-export`·`skill-forge`·`using-hiway-kit`)에만
  `policy.allow_implicit_invocation: false`. 그 키가 없는 스킬에는 `policy` 를 쓰지 않는다.
  이전에는 Claude Code 에서 자동 발동하지 않는 이 세 스킬이 **Codex 에서는 암묵 호출됐다**.
- 위치·필드·필수 여부는 공식 문서를 2026-10-05 에 다시 읽어 확인했다(learn.chatgpt.com/docs/build-skills,
  submission-errors `skill_agent_interface_missing`) — 근거는 `packaging/targets.json` `codex.skillInterface`.
- 생성물은 `build-targets.py --check` 의 드리프트·미생성 판정을 받는다(지우면 red). 디렉토리 ZIP 에 15개 모두 실린다.
  Claude Code 는 이 파일을 무시한다(`claude plugin validate --strict` rc 0, `plugin details` Skills 15·Agents 15 불변).

### Changed — 규범 3건 (`rules/` — CHECKSUMS 재생성)

- `definition-of-done` «Task 마감 규율»: Task 도구가 **있는 세션에서만** 적용하고, 없으면
  `skills/plan-task/references/task-tools-fallback.md` 의 대체 경로를 가리킨다(C-F3).
- `agent-system` Phase Gate: Validation→Done 을 auto-dev T-merge 와 같은 기준(완료 조건 rc 0 · review-code
  `[ACCEPT]` · security CRITICAL/HIGH 0)으로 맞추고, 정의된 적 없는 "Must Fix" 와 auto-dev 가 부르지 않는
  "verify-code PASS" 를 지웠다(B-P1-10). Planning→Dev 는 P0 = 0 만 공통이고 나머지는 `elicitation.md` §6 의
  규모별 기준에 위임한다(B-P1-11).
- `child-marker`: `base_commit` 이 HEAD 의 **조상이 아닐 때** 경고한다(코드와 일치). 문자 그대로의 "불일치면 경고"는
  첫 작업 커밋부터 상시 참이 되는 경고였다(B-P1-22).

### Fixed — 해설본 미러 5종 내용 동기 (`docs/architecture/rules/` — MIRROR.sha256 재생성)

- `mcp-usage`: 존재하지 않는 `db-tunnel.sh start` 지시 삭제(B-P0-4). "배포 에이전트엔 MCP 미배선"을 정본 원칙이 아니라
  CLAUDE.md Contributing 이 소유하는 **저작 규칙**으로 정정, 낡은 예산 숫자(10,240B·여유 77B·1,425B) 삭제 — 숫자는
  게이트 출력이 소유한다(B-P1-19).
- `planning-protocol`: 소유자 §6 에 없는 시간 열(~10시간/20~50시간/50시간+)과 §6 과 다른 필요 산출물 열 삭제,
  `MISSING_SPEC` 처리를 규범 문구("명세에 추가")로(B-P1-20).
- `agent-delegation-chain`: 정본은 `tier: reference` 라 본문이 주입되지 않는다고 정정(B-P1-21). 승인 문단이 컨텍스트에
  있어야 위임이 일어난다는 A/B 근거와 현재 구조의 간극은 **미결**로 명시했다.
- `agent-system` §9: Phase Gate 정렬의 이유. `task-resume`: checklist 예시를 실제 스키마(`acceptance`·`verify` 필수)로.
- 5종 모두 문서 지위 frontmatter(`status: current`, `as_of`) 추가(D0-2).

### Fixed — 하네스 사실 정정 (`harness-export`·`child-session`·생성물 원본)

- **Codex 는 PreToolUse 차단을 지원한다**(codex-cli 0.159.3 실측 — exit 2 와 `permissionDecision:"deny"` 모두, 양성 대조
  포함). "차단이 유지되지 않는다"는 0.153.4 기록이었다. `export_harness.py` 의 생성물 문구·`child-session` 파리티 절을
  "Codex 도 차단은 되지만 킷은 Codex 에 차단 훅을 싣지 않는다(페이로드 파서 없음)"로 고쳤다(A-P0-2). 이식 여부는 별도 결정.
- `harness-export` SKILL: Antigravity 는 플러그인 설치로 **스킬만** 받는다 — 규범은 진입점 파일로만(A-P0-1). 전달 형태 표에
  Antigravity 행(AGENTS.md·GEMINI.md 둘 다 읽음, A-P2-5)과 Codex 디렉토리 ZIP 설치(훅 없음) 구분. 같은 규범이 두 번 들어가는
  곳 3개(Codex 훅+AGENTS.md · Antigravity 두 파일 · **Claude Code 2.1.277+ 가 CLAUDE.md 없는 프로젝트에서 AGENTS.md 를 직접
  읽음**)를 표로(C-F5, A-P1-8). exit code 표를 지우고 `--help` 를 가리킨다 — 복제본은 명시 `--plugin-root` 실패를 exit 2 로,
  exit 3 을 누락, 사라진 `PORTABLE`/`NOT_PORTABLE` 딕셔너리를 현행으로 적고 있었다(B-P0-2·P0-3). 킷 도구 경로 해석은
  `task-tools-fallback.md` 의 탐색 규약을 가리킨다(A-P1-6, D10).
- `export_harness.py`: `--help` 가 모듈 docstring 의 종료코드 절을 보여 준다(종료코드 SSOT). 생성물 하네스 목록에
  Antigravity·Gemini CLI 명시(A-P1-7), "이식하지 못하는 것" 표에 Antigravity·Gemini CLI **주입 없음 — 정적 파일만**과
  Antigravity 이중 로드 행(A-P1-8·P2-4). conventions 인라인 시 문서 지위 frontmatter 를 벗긴다(닫히지 않으면 exit 1).
  **AGENTS.md·GEMINI.md 는 재생성 필요**(컨트롤).

### Changed — 하네스 실측 기록 갱신 (`packaging/targets.json`)

- 옛 관측 키는 지우지 않고 `[superseded by 2026-10-05]` 를 붙였다. 새 관측은 `_observations20261005`(codex·antigravity).
- Codex 0.159.3: 스킬 15/15, PreToolUse 차단 가능, 훅 페이로드 `Bash`/`apply_patch` + `tool_input.command`, 모델 셸 환경에
  `CLAUDE_PLUGIN_ROOT` 없음, ZIP 설치는 규범 미도착. `hooks._omitted` 사유를 "차단 불가" → "차단 가능 확인, 이식은 별도 결정"
  으로(옛 원문은 `_supersedes`).
- agy 1.2.17: 진입점 두 파일 모두 도달·이중 로드, 스킬 인식, plugin `rules/` 런타임 미도착(공식 문서와 충돌), 에이전트 미인식
  원인은 레이아웃이 아니라 `model:` 값, `validate` 는 개수만 센다, 낡은 "33개·카테고리" 서술 삭제(A-P1-3·P1-4·P1-5).
  `agy -p` 는 타임아웃해도 **rc 0 에 `status:"SUCCESS"`·빈 응답**(재측정 — status 필드로도 절단을 못 가린다, C-A5·F9).
  `$schema` URL 404 기록, `plugin@marketplace`·`import` CLI(A-P2-2·C-A6). Gemini CLI 런타임은 미측정(키 무효).
