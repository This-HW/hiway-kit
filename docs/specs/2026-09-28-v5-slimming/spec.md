---
status: historical
as_of: 2026-09-28
---

# v5.0.0 — 필요 없거나 성능을 깎는 것을 걷어낸다

**상태**: 완료 — v5.0.0 (`49e451d`, 태그 v5.0.0, CI green) · **결정자**: 컨트롤(plan-control) — 사용자 위임 2026-09-28 *"claude, codex 모두 고려하면서
v5.0.0 진행해. 너가 판단해서 끝까지 완료해"* · **기준 커밋**: 이 문서가 들어간 커밋(브리프에 SHA 로 고정)

## 왜

4.0.0 에서 Work 시스템을 걷어낸 뒤 같은 종류의 결함을 전수 점검했다(읽기 전용 감사 4건 + 컨트롤 직접 확인,
2026-09-28). 같은 결함 클래스가 킷 곳곳에 남아 있었다: **소비자 환경에서 성립하지 않는 지시, 매 세션 비용만
드는 텍스트, 일상 요청을 느린 경로로 빼돌리는 트리거, 소비자 레포에 묻지 않고 쓰는 동작.**

실측 요지(감사 원문은 이 세션 기록, 핵심만):

| 축 | 측정 |
| --- | --- |
| 매 세션 주입(RULES+WORKFLOW) | 빈 레포 5,453자(~1.6k tok) · 이 워크트리 8,656자(~2.5k tok) |
| 에이전트 설명(상시 컨텍스트) | 32종 7,933B / 예산 8,192B |
| 스킬 설명 | 21종 4,103~4,333자 |
| auto-format 의 `.md` 편집 1회 | 245ms — prettier 미설치 프로젝트에서도 `npx --no-install prettier` 호출 |
| stop-validator | 변경 없어도 트랜스크립트 전량 파싱(173MB 에서 729ms) |
| 배포물 | 116파일 1.09MB 중 `hooks/tests/` 290KB(26.5%), 가짜 키 픽스처 포함 |

## 판정 (컨트롤 결정 — 작업자는 재론하지 않는다. 전제가 틀렸으면 근거와 함께 반려한다)

### A. 훅·런타임 (Claude·Codex 공통 경로 주의)

Codex 에 실리는 훅은 `session-start.py`(SessionStart)·`auto-format.py`(PostToolUse) 둘이다
(`packaging/targets.json` → `hooks/hooks-codex.json` 생성물). `session-check.py`·`stop-validator.py`·
`protect-sensitive.py` 는 Claude 전용이다.

- **A1** `setup/session-check.py`: SessionStart 에서 소비자 `.git/hooks/pre-commit` 을 **쓰지 않는다**(설치·갱신 모두
  제거 — 설치는 `setup.sh` 의 명시적 opt-in 경로만). 결과를 버리는 `init.templateDir` 조회도 필요할 때만.
  경고는 stderr(모델·사용자 모두 못 봄)가 아니라 **사용자에게 보이는 채널**(`systemMessage`)로 — 실재 결함
  조건(파이썬 하한·이중 로드·낡은 venv)만. 상시 참이 되는 경고는 만들지 않는다(`docs/conventions/warning-signal.md`).
- **A2** `hooks/auto-format.py`: prettier·eslint 는 **프로젝트 로컬 바이너리가 있을 때만**(`node_modules/.bin/<tool>`)
  — `npx` 레지스트리 조회 금지. ruff 호출은 파일당 2회 이하. `MultiEdit` 는 처리하거나 matcher 에서 뺀다
  (처리 쪽을 택한다: 입력의 `file_path`). 내부 단계 타임아웃 합이 훅 타임아웃(30s)을 넘지 않게.
  Codex PostToolUse 페이로드에서도 깨지지 않을 것(모르는 tool_name 은 조용히 통과 = 지금과 같음).
- **A3** `hooks/stop-validator.py`: 편집된 `.py` 가 없으면 **트랜스크립트를 파싱하기 전에** 끝낸다(싼 신호 먼저).
  auto-format 과 중복되는 ruff 는 Bash 로 쓴 파일처럼 auto-format 이 못 본 경우로 한정. pytest 내부 타임아웃은
  훅 타임아웃보다 작게 유지하고 문서화.
- **A4** `hooks/protect-sensitive.py`: 제거된 Agent Teams 의 `message|broadcast` matcher·분기 삭제. Read 차단
  메시지가 "수정할 수 없습니다"로 나오는 문구 정정.
- **A5** `hooks/session-start.py`:
  - STALE TASKS 스캐너 삭제(`~/.claude/tasks` 가 없어 발화 0).
  - `loop-engineering` 을 **조건부**로: 신호 = 활성 계획 존재(`task-resume` 과 같은 신호). `parallel-worktree` 는
    **참조 등급**으로 내려가므로 그 신호 삭제. (규칙 frontmatter 는 C 담당이 바꾼다 — 계약: `loop-engineering`
    `tier: conditional` / `activates: 활성 계획 존재`, `parallel-worktree` `tier: reference` + `indexLine`.)
  - 주입되는 core·conditional 본문의 `skills/…`·`rules/…` 상대경로를 indexLine 처럼 **플러그인 절대경로로
    렌더**한다 — 소비자 cwd 에는 그 경로가 없다.
- **A6** 죽은 코드: `hooks/utils.py` 의 `format_size`·`load_yaml_safe`·`DEFAULT_SCRATCH_MAX_AGE_DAYS`,
  `feedback_ledger.py` 의 `promote` 하위명령과 레지스트리 기계(호출자 0 — 삭제 전 `git grep` 으로 재확인),
  `export_harness.py` 의 구 이름(`cck`) 마커 이주 경로(개명 v3.0.0 뒤 두 메이저). 4.0 의 `docs/works` 이주·안내는
  **유지**(4.x→5 업그레이드 경로 — 6.0 에서 제거한다고 주석에 날짜와 함께 적는다).
- **A7** `scripts/check_injection_budget.py`: **실제 `main()` 출력**을 픽스처 레포(빈 레포·원장 있음·활성 계획 있음·
  워크트리)에서 재서 게이트한다 — 지금은 LESSONS·ACTIVE PLANS 를 빼고 잰다. "활성 Work" 문구 정리.
  에이전트 설명 예산은 v5 로스터 기준으로 다시 잡는다(여유를 두되 빈 숫자가 아니게).
- **A8** `hooks/examples/README.md`: 인라인 `cp`/`chmod` 설치 블록을 **opt-in 절차 서술**로(다운로드-실행 오인 제거).
- **A9** `plugins/common/hooks/tests/` → 레포 루트 `tests/hooks/` 로 이동. 소비자에게 실리지 않게.
  `pytest.ini`·`ruff.toml` per-file-ignores·각 테스트의 경로 설정·`.github/workflows/validate.yml`·
  `scripts/verify-done.sh` 의 테스트 경로 줄·문서 인용을 함께.

### B. 에이전트 32 → 15

**남긴다(15)**: `dev/`{analyze-dependencies, fix-bugs, git-workflow, implement-code, plan-implementation,
research-external, review-code, security-scan, sync-docs, verify-code, write-tests} · `meta/devils-advocate` ·
`planning/`{clarify-requirements, define-business-logic, design-user-journey}

**없앤다(17)**: `dev/`{explore-codebase(네이티브 Explore 중복), analyze-tech-debt, enforce-structure,
generate-boilerplate, manage-api-versions, plan-refactor→plan-implementation, verify-integration→verify-code}
· `backend/` 전부{design-services→plan-implementation, implement-api·optimize-logic→implement-code,
write-api-tests→write-tests} · `planning/`{analyze-domain, define-metrics} · `meta/`{facilitator, synthesizer,
consensus-builder, impact-analyzer}. 흡수 대상에 **실제로 고유한** 내용만 짧게 옮긴다(복붙 금지).

- **B1 트리거**: 남는 15종의 `description` 을 다시 쓴다. 일상 표현 금지 — "~해줘", "수정해줘", "안돼", "안됨",
  "오류", "에러", "봐줘", "확인해줘", "분석해줘", "탐색", "개선해줘", "정리해줘", "git", "커밋", "브랜치",
  "테스트"(단독), "상태", "권한", "규칙", "계산", "흐름", "화면", "패키지", "라이브러리" 같은 단어 단독 트리거.
  에이전트 간 트리거 충돌 0. `MUST USE when:` 형식은 유지하되 **구체 조건**(무엇이 주어졌을 때)으로.
- **B2 frontmatter**: `review-code` maxTurns 10→25(도구 17회 소진 실패 기록 `review-code.md:629`),
  `security-scan` effort max→high·maxTurns 상향. `define-business-logic`·`design-user-journey` 는 **읽기 전용
  분석가**로(Write·worktree 제거 — 산출물을 반환하고 호출자가 쓴다). 지원되지 않는 frontmatter(`references:`) 제거.
- **B3 죽은 본문**: 서브에이전트가 실행할 수 없는 "다음 단계 위임" 표 전부 삭제(위임 신호 폐기 W-022 R1 이후 잔재).
- **B4 `skills/multi-perspective-review`**: 메타 4종·define-metrics 의 역할을 **스킬 단계**(메인 세션이 수행)로
  흡수. 관점 검토는 남는 에이전트 또는 관점 프롬프트로. 서브에이전트가 없는 하네스(Codex)의 순차 경로 명시.
  stale 참조(`POL-002` 등) 정리.
- **B5 규칙** `rules/agent-system.md`: 로스터·모델 표를 **한 곳**에(스킬 2곳의 중복 표는 C 담당이 지운다),
  "NEVER general-purpose" 삭제(네이티브 에이전트로의 강등을 막는다), 메타 개수 정정, 어디에도 없는 "tests ≥80%"
  게이트 삭제. `rules/agent-delegation-chain.md`: 사전 승인(재확인 불요)은 유지하되 **위임 범위를 좁힌다** —
  작업이 에이전트 전문과 명확히 맞고 **별도 컨텍스트가 이득일 때**(여러 파일·독립·병렬·리뷰 독립성) 위임,
  대화형·단순·한 단계 작업은 인라인. 해설본 미러(`docs/architecture/rules/` 의 두 파일)도 함께.
- **B6 evals**: 없앤 에이전트의 시나리오 삭제, 기준선·커버리지 정책·`scripts/check_eval_coverage.py`(+테스트)의
  참조 정리. **eval 재실행 금지**(API 비용) — 기준선 파일은 삭제 반영으로만 갱신하고 게이트가 통과해야 한다.

### C. 스킬 21 → 15, 규칙 14 → 12

- **C1 삭제**: `skill-creator`(네이티브·공식 스킬 중복), `doc-coauthoring`(없는 자동 갱신을 서술),
  `mcp-builder`(공식 mcp-builder 스킬·SDK 문서와 중복, SDK 릴리스마다 낡는 부채).
- **C2 킷 개발 전용 스킬을 플러그인 밖으로**: `eval-forge`·`native-watch`·`self-improve` → 레포 `.claude/skills/<name>/`
  (`.gitignore` 에 `!.claude/skills/` 예외). 이 레포 세션에서는 프로젝트 스킬로 그대로 쓴다 — 경로를 레포 기준으로
  고쳐라. `skill-forge` 는 소비자 가치가 있으니 **남기되** 레포 전용 단계(`./scripts/feedback.sh`,
  `plugins/common/skills/`, `check_doc_counts.py`, `verify-done.sh`)를 소비자에서 성립하게 고친다.
- **C3 절차 과다 제거**: `brainstorming` 에 **크기 게이트** — 새 기능·설계가 필요한 Large 만. 버그 수정·Small·Medium 은
  건너뛴다. description 의 "MUST USE before … any implementation" 삭제. `plan-task`·`auto-dev` 의 크기 기준과
  **일관**되게(Small 경로는 가볍게 — 필수 보안 스캔 등 재검토). `using-hiway-kit` 슬림 + `disable-model-invocation: true`
  (session-start 가 이미 WORKFLOW 로 주입 — 호출 시 이중 주입).
- **C4 중복·결함**: `review`·`test`·`debug` 에 복사된 ~36줄 강등 블록을 짧은 공통 서술로. `debug` 의 존재하지 않는
  "diagnose" 에이전트, `test` 다이어그램 모순, `review` description 과장 정정. `auto-dev` 의 정의 없는
  `NEED_USER_INPUT`, 비는 `$CLAUDE_PLUGIN_ROOT` 에서 깨지는 마커 경로(→ `task-tools-fallback.md` 의 해석 방식),
  parallel-worktree 와 중복된 병렬 절. `task-tools-fallback.md`·`skill-forge` 의 재번호된 원장 ID 삭제.
  `agent-creator` 는 소비자의 `.claude/agents/` 로 쓰게, "MUST USE when" 강요와 중복 모델 표 삭제.
  `plan-task`·`auto-dev`·`cross-engine-review`·`control-loop`·`harness-export` 의 `plugins/common/...` 레포 경로 표를
  소비자에서 성립하는 서술로. `web-research` 트리거 좁히기. 삭제된 에이전트를 가리키는 스킬 서술 정리.
- **C5 규칙**: `code-quality`·`ssot` **삭제**(모델 기본 행동과 같은 일반론 — 해설본 미러도 삭제).
  `loop-engineering` → conditional(A5 계약), 정의 없는 `N`·`max_iterations` 는 정의하거나 지운다.
  `parallel-worktree` → reference(+indexLine). `definition-of-done` 의 레포 전용 attest("CHANGELOG·README·CLAUDE 반영",
  "적대적 리뷰")를 **프로젝트에 그런 관례가 있을 때**로. `task-resume`: 단순 질문은 **그냥 답한다** — 활성 계획은
  한 줄 언급까지, 대기 금지. `planning-protocol` 은 경로가 A5 렌더로 풀리게 `skills/plan-task/references/elicitation.md`
  표기 유지. `mcp-usage` 의 킷 저작자용 절 삭제. `feedback-loop` 슬림. 해설본 미러가 있는 규칙은 미러도.
  **`agent-system`·`agent-delegation-chain` 은 B 담당.**

### D. 통합 (컨트롤 단독 — 공유 파일)

`rules/CHECKSUMS.sha256`·`docs/architecture/rules/MIRROR.sha256` 재생성, `AGENTS.md`·`GEMINI.md` 재생성
(`scripts/export-harness.sh`), `README.md`·`plugins/common/README.md`·`CLAUDE.md`(개수·표·isolation 목록),
`CHANGELOG.md`(**이주 표**: 없앤 에이전트·스킬 → 대체), 버전 5.0.0 + `build-targets.py --write`,
`docs/native-absorption.md`(네이티브 `/code-review`·`/security-review`·`/simplify`·Explore·Plan 행 추가, 개수 정정),
`scripts/build-codex-zip.py --check`, 격리 `CODEX_HOME` 설치 확인, `scripts/verify-done.sh`, CI, 태그, push, 워크트리 회수.

## Codex 관점 체크 (모든 작업자)

- Codex 는 **스킬만** 인식한다(에이전트 0 — 실측). 스킬이 에이전트를 부르면 **서브에이전트 없는 경로**가 있어야 한다.
- 규칙은 Codex 에 `AGENTS.md`(portable 만)와 session-start 주입(`--portable-only`)으로 간다. 규칙 삭제·등급 변경은
  두 경로 모두에 반영된다 — D 에서 `AGENTS.md` 재생성으로 확인.
- Codex 훅 페이로드(tool_name 이 Claude 와 다를 수 있음)에서 A2·A5 가 깨지지 않을 것.
- OpenAI 제출 ZIP 규칙(`scripts/build-codex-zip.py --check`)을 깨지 않을 것 — 스킬 frontmatter 는 `name`·`description`
  외 필드가 경고(무시)로만 남는다.

## 완료 조건

- `scripts/verify-done.sh` green(컨트롤이 통합 트리에서 직접), CI green
- `scripts/build-codex-zip.py --check` rc=0, 격리 `CODEX_HOME` 설치에서 스킬 15종 인식
- `python3 scripts/check_injection_budget.py` 가 실제 출력 기준으로 통과, 매 세션 주입·에이전트 설명·스킬 설명이
  위 표보다 줄어든 수치를 CHANGELOG 에 기록
- `git grep` 으로 없앤 에이전트·스킬 이름이 배포물(`plugins/`)·README·CLAUDE.md 에 0건(CHANGELOG 이주 표·과거 기록 제외)
- v5.0.0 태그, main push, 병합된 워커 워크트리 회수
