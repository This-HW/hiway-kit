---
status: historical
as_of: 2026-10-05
---

# 감사 B — 설계·기획·규약 문서의 싱크와 로직

- 기준 커밋 `e7181cbbfb6c8c3bc38b7ae4e979da09fa30a618` (v5.3.0). `merge-base --is-ancestor` 통과, HEAD 와 동일.
- 레포 파일은 수정·커밋하지 않았다. 산출물은 이 파일뿐이다.
- 게이트: `bash scripts/verify-done.sh` → **rc=0, 기계 검사 33 pass / 0 fail**. 아래 결함은 전부 green 게이트를 통과한 상태에서 나온 것이다.
- 방법: 메인 세션이 전수 스크립트(링크·표 열 수·낡은 토큰 grep·에이전트 frontmatter 대조)를 직접 돌렸고, 읽기 전용 하위 에이전트 4개(README군 / 스킬군 / 규칙·미러·컨벤션군 / docs·research·specs군)가 구역별로 정독했다. 하위 에이전트 보고 중 P0 급과 대표 P1 은 메인이 원본을 직접 열어 재확인했다.
- 표기: **[확인]** = 메인이 파일·명령 출력으로 직접 확인. **[보고]** = 하위 에이전트가 근거를 댔으나 메인이 재확인하지 않음. **[추정]** = 근거 부족.
- 라인 번호는 e7181cb 기준이다. 하위 에이전트가 적은 일부 라인은 몇 줄 어긋나 있어 내가 확인한 것은 바로잡았다.
- 범위 메모: `docs/personal/` 은 **레포에 없다**. 언급은 `.gitignore:43`, `docs/specs/2026-07-07-toolkit-improvement-batch.md:92`, `docs/CHANGELOG-archive.md:1873` 뿐이고 모두 "gitignore 된 비공개 폴더"라는 뜻이라 끊어진 참조가 아니다 [확인].

---

## 총평

1. **기계로 셀 수 있는 사실은 정확하다.** 개수(15/15/12/미러 5), 버전, 에이전트 모델 표 ↔ frontmatter, 규칙 CHECKSUMS, 미러 sha, §번호 참조가 전부 맞다.
2. **결함은 게이트가 보지 않는 곳에 몰려 있다.** 세 부류다.
   - **A. 시점 고정 문서에 지위 표기가 없고, 정정이 본문이 아니라 문서 끝이나 다른 절에만 붙은 것.** pipeline-reinforcement-plan-v2, marketplace-submission 후반, codex-submission-checklist, research 일부, phase-gate-pattern.
   - **B. 같은 내용을 두 곳에 유지하다 한쪽만 갱신된 것.** CLAUDE.md 릴리스 절 ↔ release-process.md, README ↔ CLAUDE.md(설치·기여 체크리스트), conventions/README 색인, 스킬 크기 기준 3중.
   - **C. 5.2.0 `tools/` 이동 / 5.3.0 평탄화 / 4.0.0 Work 제거 / `PORTABLE` 딕셔너리 제거 이후 코드는 바뀌었는데 서술이 남은 것.**
3. **사용자를 틀린 길로 보내는 P0 가 6건 있다.** 아래 표의 `P0-1~6` 이다. 설치 충돌(`setup.sh` ↔ 경로 A)과 `harness-export` 스킬의 종료코드·분류 서술이 가장 위험하다.
4. **로직 결함이 구조적으로 가장 큰 것**은 Task 도구가 없을 때의 폴백이다. 폴백이 `checklist.py` 스키마(`verify` 필수)와 맞지 않는다(P1-12). 그 다음이 Small 경로·Phase Gate 기준이 스킬·규칙·using-hiway-kit 사이에서 갈리는 것(P1-10, 11)이다.

---

## (a) 발견 표

심각도: P0 사실 오류·사용자를 틀린 길로 보냄 / P1 모순·낡음 / P2 가독성 / P3 취향.

### P0

| ID | 파일:라인 | 무엇이 틀렸나 | 근거 | 고치는 법 |
|---|---|---|---|---|
| P0-1 [확인] | `README.md:25-35, 55-61` ↔ `setup.sh:139-140` | README 는 설치를 "둘 중 **하나만**"(이중 로딩 경고)이라 하면서 "Full Mode"(`./setup.sh`)를 조건 없이 안내한다. 그런데 `setup.sh` 1단계가 `claude plugin marketplace add This-HW/hiway-kit` + `claude plugin install hiway-kit@hiway-kit --scope user` 를 무조건 실행한다. 경로 A(`anthropic-plugin-directory`) 사용자가 Full Mode 를 하면 README 가 금지한 이중 설치가 된다. | `setup.sh:139-140`. 현 머신 캐시에도 `~/.claude/plugins/cache/{anthropic-plugin-directory,hiway-kit}/hiway-kit` 가 공존한다. | Full Mode 절에 "경로 B 를 설치한다. 경로 A 를 이미 썼다면 먼저 제거하라"를 적거나, `setup.sh` 에 플러그인 설치 건너뛰기 옵션을 둔다. |
| P0-2 [확인] | `plugins/common/skills/harness-export/SKILL.md:96-97, 108-114` | "`--plugin-root` 를 명시했는데 `rules/` 가 없으면 **exit 2**"라고 쓴다. 실제는 **exit 1** 이다. exit code 표에는 exit 3(conventions 블록 건너뜀)도 빠져 있다. | `tools/export_harness.py:1229-1235` explicit 지정 실패는 `return 1`, `:1239-1241` 자동 탐색 실패만 `return 2`. | 96-97행을 exit 1 로 고치고 표에 3행을 추가한다. |
| P0-3 [확인] | 같은 파일 `:113, 126-128`(불변식 4) | "새 룰을 추가하면 `export_harness.py` 의 `PORTABLE` 또는 `NOT_PORTABLE` 에 사유와 함께 등재 … 유령 엔트리도 exit 1"이라 쓴다. 그 두 딕셔너리는 이미 없다. 분류는 룰 frontmatter 의 `portable:`·`tier:` 가 한다. | `export_harness.py:369-375`("이전에는 PORTABLE / NOT_PORTABLE 딕셔너리 두 개가 이 파일에 있었다"), `grep PORTABLE` 결과가 이 주석뿐. 따라 하면 존재하지 않는 코드를 찾게 된다. | 불변식 4 를 "룰 frontmatter 에 `portable: true\|false` 와 `tier:` 를 선언한다. 미선언은 exit 1"로 바꾸고, exit 1 행의 "유령 엔트리"를 뺀다. |
| P0-4 [확인] | `docs/architecture/rules/mcp-usage.md:50` | "(반드시 `db-tunnel.sh start` 먼저)". 같은 파일 :111 과 규범 `rules/mcp-usage.md:42` 는 "킷은 터널 스크립트를 제공하지 않는다"고 한다. 존재하지 않는 스크립트를 먼저 실행하라는 지시다. | `git grep db-tunnel` 은 이 줄과 CHANGELOG-archive 에서만 나온다. verify-done §7 은 `plugins/common` 안의 `scripts/*.sh` 참조만 보므로 `docs/` 는 안 잡힌다. | 해당 줄을 "터널이 필요하면 환경별 수단으로 먼저 기동"으로 교체한다. |
| P0-5 [확인] | `docs/architecture/phase-gate-pattern.md:140-145, 204, 244` | "`Stop` hook(prompt type)을 활용하여 Phase Gate 판단을 자동화 … **명시적 스킬 호출 없이** 자동 적용". 실제 Stop 훅은 `type: command` 이고 `stop-validator.py` 는 수정된 `.py` 의 ruff·pytest 만 돌린다. Phase Gate 판정은 하지 않는다. | `hooks/hooks.json` Stop 항목, `stop-validator.py`. 같은 문서 :54·:61·:165·:174 의 "핵심 로직 테스트 80%+" 는 미러 `agent-system.md:111-113`("80% 는 v5 에서 지웠다")과도 모순이다(P1-6). | Stop 훅은 lint/pytest 안전망일 뿐 Phase Gate 판정이 아니라고 고치고 "자동 적용" 문구를 삭제한다. |
| P0-6 [확인] | `docs/pipeline-reinforcement-plan-v2.md:32, 62, 337`, `:38-313` | 머리에 지위 표기가 없는 채로, 폐기된 auto-dev 마커 레시피 `touch "/tmp/.claude_validated_$(md5 cwd)"` 와 "파일 1: stop-validator.py **(신규)**" 293줄 스케치가 현재형 명세로 남아 있다. 이대로 하면 Stop 훅이 검증을 건너뛰지 않고, `block()` 이 `sys.exit(2)` 인 구버전 계약을 따르게 된다. | 현행 마커는 상태 디렉토리(0700)에 두고 HEAD+`.py` sha256 지문을 쓴다(`skills/auto-dev/SKILL.md:224-240`, `stop-validator.py`). `block()` 은 `{"decision":"block"}` + exit 0. hooks.json 은 exec form. 문서 4행은 "Track 2 보류"인데 11행·398행은 "폐기"라 한 문서 안에서도 모순이다. | 맨 위에 `> 상태: 역사 — Track 1 은 stop-validator.py 로 구현 완료, Track 2 는 2026-08-27 폐기(→ docs/architecture/delegation-signal-retirement.md)` 를 둔다. 코드 블록은 걷어내거나 삭제한다(처분안 (c) 참조). |

### P1 — 낡음·모순 (설치·릴리스·배포 상태)

| ID | 파일:라인 | 무엇이 틀렸나 | 근거 | 고치는 법 |
|---|---|---|---|---|
| P1-1 [확인] | `CLAUDE.md:367-387`(Release Checklist) ↔ `docs/conventions/release-process.md:10-30` | CLAUDE.md 는 plugin.json 을 직접 편집하고 `build-targets.py --write` 를 수동 실행하라고 한다. release-process.md 는 `scripts/bump-version.sh <ver>` 를 쓰고 "수동으로 SSOT 를 고치지 마라"고 한다. CLAUDE.md 에는 `export-harness` 재생성도, CHANGELOG 에 AGENTS.md 마커 sha 를 적는 규칙도 없다. 릴리스 절차 SSOT 가 둘이다. | `scripts/bump-version.sh` 실존. release-process.md 는 CLAUDE.md 에서 `@import` 되지 않는다. [보고] `rules/VERSION`(1.4.0)을 언제 올리는지 어느 문서에도 없다. | CLAUDE.md 릴리스 절을 release-process.md 의 `@import` 로 대체하거나 한 줄 포인터로 줄인다. 단, CLAUDE.md 크기가 상한에 37B 차이라는 보고가 있다(P3-9). |
| P1-2 [확인] | `CLAUDE.md:143` 외 "Plugin cache is keyed by `{plugin-name}/{version}`" | 캐시 경로를 `cache/hiway-kit/hiway-kit/<version>/` 하나로 적었다. 디렉토리 경로 설치본은 `cache/anthropic-plugin-directory/hiway-kit/<version>-<sha12>/`(예: `5.3.0-e7181cbbfb6c`)다. "same version = no update fetched" 도 이 경로에서는 키에 sha 가 붙어 다르게 동작할 수 있다 [추정]. | `ls ~/.claude/plugins/cache/anthropic-plugin-directory/hiway-kit/` → `5.2.2-79cbfe860780`, `5.3.0-e7181cbbfb6c`. 직접 마켓 쪽은 `5.2.0` 형식. | `<marketplace>/hiway-kit/<version>[-<sha>]` 로 일반화하고, "같은 버전이면 갱신 안 됨"은 직접 마켓플레이스 경로에 한정하거나 디렉토리 경로 동작을 실측해 적는다. |
| P1-3 [확인] | `docs/marketplace-submission.md:3-8, 220-226, 276-293` vs `:18, 73-94, 123-126` | 머리 Note 는 제출 도착지가 "community 카탈로그"라 하고, 220행은 "**직접 마켓플레이스만 성립**(카탈로그 재제출 대기 중)"이라 한다. 같은 파일 18·73-94행과 README·CLAUDE.md 는 `anthropic-plugin-directory` 설치가 성공한다고 한다(10-05 실측). 291행은 구 항목을 "지우지 않는다"인데 123-126행은 삭제 요청을 보냈다고 한다. 287-290행의 "신규 제출한다"는 이미 한 일(9-28)을 현재형 지시로 쓴다. | 같은 파일 내 직접 모순 + CLAUDE.md "Distribution". | 266-312행을 "개명 시점 기록(2026-09-08)"으로 접고, 맨 위에 "현재 상태 요약표(채널별 상태·확인일)"를 둔다. |
| P1-4 [보고] | `docs/marketplace-submission.md:228, 299-300` vs `:80, 126, 158` | 전임 킷이 "v2.21.0 에서 멈춘다"고 쓰고, 다른 곳은 카탈로그 pin 이 `292ba07e`(v2.12.3)에서 멈췄다고 쓴다. 239행 "agents — planning, dev, **backend**, meta, **review** 카테고리"는 5.0.0 에서 backend 제거, 5.3.0 평탄화 이후 낡았다. | 같은 파일 내 불일치. 외부 카탈로그 상태는 레포 밖이라 확인하지 못했다. | 한쪽으로 통일하고 확인일을 붙인다. 개수는 `check_doc_counts.py` 를 가리킨다. |
| P1-5 [보고] | `docs/codex-submission-checklist.md:3-7, 203-204` vs `:117-123`; `:50-114, 185-204`; `:133-135` | "agent 세션이 제출해서는 안 된다"고 하면서 117-123행은 에이전트 트래커가 "Skills only 가 뜨는 순간 제출하고 Publish 를 누른다"고 쓴다. "Once Skills only appears"·"What a human still needs to do 1~4" 는 이미 9-30 에 제출해 In review 인데 현재형이다. 133행 "full local gate, including **§14 above**" 의 §14 는 이 파일에 정의가 없다(verify-done.sh §14 로 보인다 [추정]). | 같은 파일 16-48행. | 50행 절 제목에 `(역사)` 를 붙이고, 185-204행은 "승인 후 Publish → 노출 확인"으로 교체한다. §14 는 `verify-done.sh §14` 로 적는다. |
| P1-6 [확인] | `docs/architecture/phase-gate-pattern.md:54, 61, 165, 174` | "핵심 로직 테스트 80%+", "통합 테스트 통과"가 출구 조건으로 남아 있다. 규범 `agent-system.md:68-72` 에는 둘 다 없다. | 미러 `docs/architecture/rules/agent-system.md:111-113`. | 규범 출구 조건에 맞춘다. |
| P1-7 [확인] | `README.md:195-198` | "Public listing … requires OpenAI's submission review — **not done**". 5.2.0 은 이미 In review 다. | `docs/codex-submission-checklist.md:16`, CLAUDE.md "Distribution". | "submitted 2026-09-30, in review"로 고친다. |
| P1-8 [보고] | `README.md:7-9`, `:124-132` | `Validation hardening covers…` 문단은 v3.34.2 릴리스 노트다(`git log -S` → `5b31f91`). "fixed in 3.34.1", "after this update" 도 이력 서사다. CLAUDE.md 의 "README/docs 는 버전 무관" 규약 위반이다. | 하위 에이전트의 `git log -S` 결과. | 삭제하고 CHANGELOG 로 보낸다. 현재 사실("`additionalContextLimit: 0`, 신뢰는 config 해시당 1회")만 남긴다. |
| P1-9 [확인] | `README.md:120`, `docs/native-absorption.md:59` | README 표는 Antigravity 서브에이전트를 "not supported (**nested layout**)"이라 쓴다. 같은 README :108 은 5.3.0 평탄화 후 재검증을 안 했다고 쓴다. 에이전트가 평탄해졌으므로 "nested layout"은 근거가 사라졌다. native-absorption 59행도 "`agents/`(**33**) 1급 미지원 … 카테고리 중첩을 재귀하지 않음"이고 "Codex 훅(exec form)은 로드 안 됨 … 편입 보류"라 한다. 그런데 `hooks-codex.json` 이 배포돼 있고 codex-submission-checklist 는 그 결론이 "superseded"라고 적는다. | `plugins/common/agents/` 최상위 15개, 하위 디렉토리 0. `docs/codex-submission-checklist.md:~180-182`. | 120행을 "not supported (not re-verified against flat layout)"으로 통일한다. native-absorption 59행에서 33·중첩·훅 문장을 현재 사실로 고치거나 "(2026-08-26 시점)"을 붙인다. |

### P1 — 낡음·모순 (규칙·컨벤션·미러)

| ID | 파일:라인 | 무엇이 틀렸나 | 근거 | 고치는 법 |
|---|---|---|---|---|
| P1-10 [확인] | `rules/agent-system.md:72` ↔ `skills/auto-dev/SKILL.md:196-205` | Phase 3→Complete 기준이 다르다. 규칙: "review-code **Must Fix = 0**, Critical security = 0, verify-code PASS". auto-dev T-merge: `[ACCEPT]`(CRITICAL·HIGH 0), security CRITICAL/HIGH 0, 완료 조건 rc 0 이며 verify-code 는 호출하지 않는다. "Must Fix"는 정의된 곳이 없다. review-code 는 C/H/M/L 과 REJECT/CONDITIONAL/ACCEPT 를 쓴다. | `grep 'Must Fix' plugins/common` → `agent-system.md:72` 한 곳뿐. | 규칙을 auto-dev 기준에 맞추거나 auto-dev 에 verify-code 단계를 넣는다. "Must Fix"는 정의하거나 지운다. |
| P1-11 [보고] | `skills/using-hiway-kit` ↔ `plan-task:3, 143` ↔ `auto-dev:30-31, 272`; `rules/agent-system.md` Phase Gate 1→2 ↔ `plan-task/references/elicitation.md §6` | using 은 "Small·버그: 바로 구현"인데 plan-task description 은 "any new feature, bug fix"에 쓰라 하고, plan-task Step 3 은 Small 도 auto-dev 를 즉시 invoke 한다. 규칙 Phase Gate 1→2 는 모든 작업에 "business rules·data model·user flows"를 요구하지만 elicitation §6 은 규모별이다. 크기 임계값은 plan-task:61-62, brainstorming:7-8, elicitation §6 세 곳에 있다. | 파일 대조(하위 에이전트). | Small 경로의 정본을 한 곳으로 정하고 나머지는 §6 참조만 둔다. 규칙 Phase Gate 는 "규모별 기준은 elicitation §6"으로 위임한다. |
| P1-12 [보고, 일부 확인] | `skills/plan-task:34-40`, `auto-dev:36-40, 60-75, 222, 250`, `brainstorming:25-28` ↔ `plan-task/references/task-tools-fallback.md` | Task 도구가 없을 때의 대체 경로가 실행 불가능하다. checklist 는 항목마다 비어 있지 않은 `verify` 명령이 필수(`checklist.py:50` `_REQUIRED_FIELDS=(id,description,acceptance,verify)`, 하위 에이전트 보고에 따르면 빈 verify 는 exit 2)다. `[Planning]`·`[Brainstorm]` 단계에는 걸 verify 가 없다. 의존 순서(`blockedBy`)를 담을 필드도 없다. auto-dev T-spec/T-review/T-merge 와 `TaskList` 잔존 확인(:250)은 "도구가 있으면" 조건도 대체도 없다. | 같은 파일들. fallback 문서는 `init` 예시와 "Small 은 대화창 표"만 있다. | Planning·Brainstorm·Validation T-* 단계의 대체를 "대화창 진행표 + plan.md"로 명시하고, auto-dev:222, 250 을 "도구가 있으면"으로 가드한다. |
| P1-13 [확인] | `CLAUDE.md:97` | "maxTurns: 20 for implementation, 10 for exploration/review". review-code 25, security-scan 25, plan-implementation 20(읽기 전용), sync-docs 20. | 에이전트 frontmatter 전수(메인이 awk 로 확인). CHANGELOG 에 "review-code 10→25" 기록. | "값은 frontmatter 가 소유한다"로 바꾼다. |
| P1-14 [보고] | `CLAUDE.md:211` | "Phase 1 → **100% ambiguity removed**". 규범 `planning-protocol.md:13-16` 은 P0 만 멈추고 P1~P3 는 기본값·TODO·자율이다. `agent-system.md:64` 는 "P0 ambiguity = 0". | 세 곳 대조. | "P0 ambiguity = 0"으로 정정한다. |
| P1-15 [보고] | `CLAUDE.md:300-308, 425`(CI/CD 7항목) | validate.yml 은 약 20단계인데 7항목만 열거한다. CLAUDE.md:336 이 스스로 세운 "열거하면 낡는다" 원칙과 충돌한다. | 하위 에이전트의 validate.yml 대조. | 열거를 지우고 "validate.yml 이 소유"로 바꾼다. |
| P1-16 [확인] | `docs/conventions/no-gate-integration.md:1, 8, 26`; `CLAUDE.md:312-314`; `docs/conventions/README.md:~28` | 같은 파일에 "three checks"와 "게이트가 넷이 돼도"가 함께 있다. CLAUDE.md 는 "몇 개인지 적지 않는다 / 목록을 지웠다"면서 같은 절에서 7종을 괄호로 열거한다. AGENTS.md·GEMINI.md 인라인 사본에도 낡은 문장이 있다 [보고]. | 파일 직접 대조. | 개수와 열거를 지운다. 고친 뒤 AGENTS.md·GEMINI.md 를 재생성한다(P2-12 의 sha 규칙 참조). |
| P1-17 [확인] | `docs/conventions/path-containment.md:14, 20`(+ AGENTS.md:243·249, GEMINI.md:242·248 인라인 사본); `scripts/build-targets.py:47` | "`_resolve_target()` / export_harness.py(`_resolve_target`)의 헬퍼를 그대로 따라라". `export_harness.py` 에는 `_resolve_target` 이 없다. 실제 이름은 `_resolve_in_repo`(`:885`)다. 관례 문서가 가리키는 헬퍼 이름이 틀렸다. 문서는 "세 번", 코드 주석은 "네 번" 반복이라고 한다 [보고]. | `grep` 결과: `export_harness.py:885 def _resolve_in_repo`, `build-targets.py:47` 의 낡은 이름. | 이름을 `_resolve_in_repo` 로 정정하고 횟수를 맞춘다. AGENTS.md·GEMINI.md 재생성 + CHANGELOG sha. |
| P1-18 [보고] | `docs/conventions/README.md:5-6, 20-21, 25-33, 40-41` | "CLAUDE.md 가 이것들을 `@import` 한다"고 하지만 import 는 6개(path-containment, lint-single-ruleset, rules-mirror, shell-lint, warning-signal, coordination)뿐이다. release-process·no-gate-integration·reference-vs-judgment·measurement-traps 는 import 안 된다. 색인표 7종에는 warning-signal·measurement-traps·coordination 이 없다. "`PORTABLE` list", "Delegation Signal contract"를 Claude Code 프리미티브로 현재형 서술한다(둘 다 폐기·제거됨). | `CLAUDE.md` `@docs/conventions/` 줄 대조(메인이 CLAUDE.md 원문으로 6개 확인), `export_harness.py` 주석. | 색인표를 전부 채우거나 "모두 import 한다"를 삭제한다. 두 현재형 서술은 정정한다. |
| P1-19 [보고] | `docs/architecture/rules/mcp-usage.md:5-7, 124, 145, 157-167` | 머리말·§7 이 "정본 원칙: 배포 에이전트엔 MCP 미배선"이라 하는데 규범 `mcp-usage.md` 에는 그 원칙이 없다. §8 의 "10,240B 여유 77B", "AGENTS.md 여유 1,425B" 등이 낡았다(실측 6,599B ≤ 7,168B 등). | 하위 에이전트 측정. | 머리말·§7 을 "저작 규칙(CLAUDE.md Contributing 소유)"으로 정정하고 §8 숫자는 삭제하거나 갱신한다. |
| P1-20 [보고] | `docs/architecture/rules/planning-protocol.md:131-133, 95` | 규모표의 "~10시간 / 20~50시간 / 50시간+" 열은 소유자 `elicitation.md §6` 에 없다. 미러가 기준을 새로 정의한 것이라 `rules-mirror.md` 규약("미러는 재정의하지 않는다") 위반이다. `MISSING_SPEC → Planning 에이전트 재호출`은 규범의 "명세에 추가"와 다르다. | 하위 에이전트 대조. | 시간 열 삭제, MISSING_SPEC 처리를 규범 문구로 맞춘다. |
| P1-21 [보고] | `docs/architecture/rules/agent-delegation-chain.md:4, 28` ↔ `rules/agent-delegation-chain.md:2` | 미러는 "세션에 주입되는 룰", "주입 룰 최상단의 Standing… 조항"이라 하는데 규범은 `tier: reference` 라 인덱스 한 줄만 나간다. 이 세션의 실제 주입도 "참고: 서브에이전트 위임 전 … 읽어라" 한 줄이다(메인 세션 컨텍스트로 확인). 사전 승인 문단이 컨텍스트에 있어야 위임이 일어난다는 근거(:28-37)와 현재 구조가 맞지 않는다 [추정]. | session-start 실제 출력(이 세션), 하위 에이전트의 빈 레포 실행. | tier 를 올리거나 승인 문단만 core 로 분리한다. 미러의 "주입된다"도 정정한다. |
| P1-22 [확인] | `rules/child-marker.md:57` ↔ `hooks/examples/child-git-guard.py:94-104` | 규범은 "base_commit 을 현재 HEAD 와 **대조**하고 불일치하면 경고"라 쓴다. 코드는 "base 가 HEAD 의 **조상이 아닐 때만**" 경고한다. 문자 그대로 읽으면 첫 커밋 후 상시 참이 되는 경고(warning-signal §1 위반)가 된다. 바로 다음 문장("정당하게 앞선 커밋 위에 있을 수 있다")과도 충돌한다. | 코드 `merge-base --is-ancestor` 확인. | "조상이 아니면 경고"로 정정한다. 규칙을 고치면 CHECKSUMS 재생성이 필요하다. |

### P1 — 스킬 로직·참조

| ID | 파일:라인 | 무엇이 틀렸나 | 근거 | 고치는 법 |
|---|---|---|---|---|
| P1-23 [확인] | `skills/brainstorming/SKILL.md:99-100` | "세션이 끝나면 대기 태스크가 다음 세션에 **잔존한다 — 정상이다**. 재개 기준은 `docs/specs/` (task-resume.md 참고)". plan-task:28 은 태스크가 "세션을 넘지 못한다"고 한다. task-resume 은 `docs/plans/*/plan.md` 만 다루고 활성 계획이 없으면 주입되지도 않는다. | `plan-task/SKILL.md:27-30`, `task-resume.md:26`. | "태스크는 사라진다. 재개는 `docs/specs/` 스펙 파일 존재로 판단한다"로 고치고 task-resume 참조는 지운다. |
| P1-24 [보고] | `skills/test/SKILL.md:20, 64-79` / `debug/SKILL.md:66-102` | fix-bugs 는 `isolation: worktree` 인데 두 스킬에는 반환·병합 단계가 없다. 같은 트리에서 재실행·verify-code 를 돌리면 수정이 격리 트리에 남아 옛 코드를 검증한다 [추정: 호스트 동작]. test 는 재시도 상한도 없다("전부 통과할 때까지"). debug 는 진단 전용 호출에도 worktree 격리 에이전트를 쓴다(`rules/parallel-worktree` 의 "읽기 전용에 격리 금지"와 어긋남). | fix-bugs.md:10, parallel-worktree. 두 스킬에 병합 언급 0건. | "fix-bugs 결과를 이 세션이 반영한 뒤 재실행"을 명시하고 N회/무진전 2회 가드를 넣는다. |
| P1-25 [보고] | `skills/auto-dev:171-173` ↔ `skills/review/SKILL.md:201-221` | auto-dev 는 `review-code` 를 그냥 지시한다. review-code 는 Bash 가 없어 diff 를 인라인으로 주지 않으면 빈 리뷰가 나오고, 6파일 초과는 배치 분할, `## 완료:` 줄이 없으면 잘린 것이다. 이 주의가 review 스킬에만 있다. T-merge 는 `## 완료:` 를 검사하면서 받는 법은 말하지 않는다. | `review-code.md` `tools: Read,Glob,Grep`, review/SKILL.md 의 실측 서술. | auto-dev T-review 에 "diff 인라인·6파일 배치 규칙은 review/SKILL.md 2단계"를 참조로 건다. |
| P1-26 [보고] | `skills/review/SKILL.md:296-309, 27 ↔ 88-89` | 4단계 표에 "전체 평가 [A/B/C/D/F]", "Warning", "Suggestion" 행이 있으나 review-code 는 REJECT/CONDITIONAL/ACCEPT 와 C/H/M/L 만 낸다. 0단계 ruff 는 `git diff HEAD` 만 보지만 diff 가 없으면 1단계는 `HEAD~1` 로 폴백해 0단계가 대상 없이 "통과"로 보고된다. 삭제된 `.py` 는 `2>/dev/null` 에 묻히고 rc 는 파이프에 삼켜진다. | 하위 에이전트 대조. | 대상 확정(1단계)을 먼저 하고 그 목록으로 ruff 를 돌린다. `--diff-filter=d` 를 쓰고 stderr 를 숨기지 않는다. |
| P1-27 [보고] | `skills/skill-forge/SKILL.md:30` ↔ `rules/feedback-loop.md:16-17` | 재현성 미충족의 강등 경로로 ledger `upsert` 를 쓰라 한다. 규칙은 "검증에서 **실제로 발견된** 결함만, 추측은 노이즈"이고 ledger 카테고리도 결함용이다. | `feedback_ledger.py:47-48` VALID_CATEGORIES. | 강등 경로를 "완료 보고에만 기록"으로 바꾼다. |
| P1-28 [보고] | `skills/cross-engine-review/SKILL.md:37-42` | 참여자는 각자 별도 작업 트리에서 도는데 우편함 기본값이 상대경로 `.cross-engine/<슬러그>/` 다. 트리마다 따로면 서로의 답신이 보이지 않는다. | 같은 파일. | 모든 트리가 보는 경로(절대경로 또는 git-common-dir 하위)를 명시한다. |
| P1-29 [보고] | `README.md:428-434, 436-443, 484-493, 509`; `plugins/common/README.md:7-11` | README 의 "Feature Development" 체인(`clarify-requirements → … → write-tests → verify-code → … → sync-docs`)을 실행하는 스킬이 없다(`write-tests`·`sync-docs`·`git-workflow` 는 skills/ 에서 0건). Multi-perspective Review 흐름은 Round 3 이 없고 Round 2 설명이 틀렸다. Project Structure 에 `tools/`·`setup/` 가 없고 "skills/ — skill .md files"도 틀렸다. 기여 체크리스트의 "Registered in `plugin.json`"은 등록부가 없는 현실과 다르고 버전 bump·CHANGELOG 항목이 빠져 있다. `plugins/common/README.md` 설치 안내는 직접 마켓만 적는다. | 하위 에이전트의 grep, CLAUDE.md Contributing("the manifest has no registry"). | 체인·리뷰 절은 삭제하거나 스킬 링크로 줄이고, 구조·체크리스트·설치는 CLAUDE.md 를 가리키는 한 줄로 바꾼다. |
| P1-30 [확인] | `docs/control-loop-transport.md:153` | "Work progress/decisions 는 gitignore 될 수 있어 보조로만 쓴다". Work 시스템은 4.0.0 에서 제거됐다. | `git grep 'Work progress'` 에서 이 줄만 걸린다. | "plan.md `## 검증 결과`·`docs/plans/` 의 진행 기록은 보조"로 바꾼다. |
| P1-31 [보고] | `docs/research/2026-09-11-cross-harness-norm-integration.md:235-243 vs 324-338`; `2026-07-long-running-loop-agents.md:5, 111-127` | 본문은 "버전 팬아웃 배워올 점"·"build-targets 수동 호출"을 그대로 두고, 정정(이미 `bump-version.sh` 로 구현)은 문서 끝에만 있다. 7월 문서는 "이미 있음: Work 시스템 progress.md", "추가 후보 — 이번 로드맵"이 현재형이고 머리에 지위 표기가 없다. | `scripts/bump-version.sh` 실존, Work 제거(4.0.0). | 머리에 "작성 시점 고정 / 정정은 하단" 배너를 두고 본문 해당 절에 "정정: 이미 구현됨"을 인라인한다. |

### P2·P3

| ID | 파일:라인 | 무엇이 틀렸나 | 근거 | 고치는 법 |
|---|---|---|---|---|
| P2-1 [확인] | `docs/native-absorption.md:35, 36` | 표 행이 깨진다. 35행은 셀 안의 `옛 판정: \|`(이스케이프 없는 파이프)로 5셀, 36행은 `` `matcher: "startup|clear|compact"` `` 의 파이프로 열이 더 늘어난다(표 머리는 4셀). GFM 에서는 코드 스팬 안의 파이프도 열을 가른다. | 메인이 만든 열 수 검사기(`tables.py`)로 35행 확인, 36행은 GFM 규칙과 하위 에이전트 `awk -F'|'` 로 확인. 레포 전체 md 에서 어긋난 표는 이 파일뿐. | `\|` 로 이스케이프하거나 "옛 판정"을 별도 문단으로 뺀다. |
| P2-2 [확인] | `docs/native-absorption.md:10 vs 33, 46, 49, 56-59, 65-68` | "근거 인용은 커밋된 자산만 — gitignore 된 Work 문서 ID 금지"라 선언하면서 근거 열에 `W-005/006/007/017/019`, `Spec 1/2/3` 을 13곳 쓴다. 전수 검토 로그는 날짜순이 아니다(09-28, 07-07, 08-26, 08-23, 07-07). 5.1~5.3(plans-replace-works, tools 이동, 평탄화)은 로그에 없다. | 직접 읽음. | W-ID 를 스펙 경로나 CHANGELOG 버전으로 치환하고 로그를 내림차순으로 정렬한다. |
| P2-3 [확인] | `CHANGELOG.md:3` | "All notable changes to **claude-code-kit**" — 구 이름이 현재형 문장에 남아 있다. `packaging/name-targets.json` 의 `oldNameScanExclude` 에 `CHANGELOG.md` 가 있어 §20 이 못 잡는다 [보고]. | 직접 읽음. | 제품명을 hiway-kit 으로 고친다. 제외는 항목 본문에만 두고 헤더 문장은 검사 대상으로 되돌린다. |
| P2-4 [확인] | `docs/conventions/reference-vs-judgment.md:~11` | "see `CHANGELOG.md`'s `[Unreleased]` entry"가 가리키는 항목이 없다(CHANGELOG.md 에 `Unreleased` 0건, archive 에 간접 언급 1건). | `grep Unreleased CHANGELOG.md` → 0. | 아카이브 항목 또는 커밋 해시로 교체한다. |
| P2-5 [확인] | `CLAUDE.md:136`, `docs/architecture/delegation-signal-retirement.md:50, 68` | "스펙·decision-log 47곳 이상이 섹션 번호로 게이트를 참조한다"는 §12 결번의 근거가 `decision-log` 인데 레포에 그런 문서가 없다(Work 제거로 사라짐). "47곳"은 검증 불가 숫자다. | `git ls-files | grep decision-log` → 0. | "스펙·CHANGELOG 가 §번호로 참조한다"로 바꾸고 숫자를 지운다. |
| P2-6 [보고] | `docs/conventions/warning-signal.md:19, 27, 133` | "넷을 확인한다"는데 항목은 6개다. `W-XXX` 발급·충돌을 현재형 예시로 쓴다(Work 제거됨). | 항목 1~6. | "여섯"으로 정정하고 W-XXX 예시를 현존 사례로 교체한다. |
| P2-7 [보고] | `docs/conventions/rules-mirror.md:1` | "`plugins/common/rules/`(12) is what gets injected every session". 본문 주입은 core 3 + 조건부 최대 4 이고 5개는 인덱스 한 줄만 나간다(`session-start.py:307-312`). 이 세션의 주입(본문 4 + 참고 5)과도 맞는다. | 실제 주입 출력. | tier 별로 정확히 서술한다. |
| P2-8 [보고] | `CLAUDE.md:99-105 ↔ parallel-worktree.md:22-23`, `198-201` | frontmatter 템플릿이 `isolation: worktree` 를 보이면서 tools 에 `ExitWorktree` 가 없다(실제 worktree 에이전트 4종은 모두 가짐). "Large (10~100+)"는 plan-task 의 Large(4모듈+/10파일+)와 다른 축(병렬 청크 수)인데 같은 10 으로 읽힌다. 크기 구간 Medium "4-10파일"과 Large "10파일+"는 10 에서 겹친다. | 하위 에이전트 대조. | 템플릿에 ExitWorktree 주석을 추가하고 표 머리에 단위(파일/청크)를 쓴다. |
| P2-9 [보고] | `plan-task:36 ↔ 57, 61`, `review/SKILL.md:112-117, 133`, `skills/harness-export:80`, `task-tools-fallback.md:35` | 한 파일 안에서 경로 기준이 섞여 있다(`skills/plan-task/references/…` vs `references/…`). review 스킬의 보안 파일 패턴에 킷 전용 경로(`hooks/*.py`, `agents/**`)가 있다. 플러그인 위치 탐색이 `~/.claude/plugins/cache/*/*/*/…` 뿐이라 비-Claude 하네스(harness-export 의 주 대상)에는 해당 경로가 없다 [추정]. | 하위 에이전트 + 메인이 글롭을 확인. | 기준을 통일하고, 탐색 실패 시 `--plugin-root` 직접 지정 안내를 앞세운다. |
| P2-10 [보고] | `skills/multi-perspective-review/SKILL.md ↔ deliberation-pattern.md ↔ examples.md`, `skills/web-research/SKILL.md` | 워크플로·실행경로·최종 리포트 구조가 3중으로 있다. "실행 예시"는 examples.md 예시 1 의 복제다. web-research 의 MCP 선택이 3곳에 반복되고 예시 `context7: FastAPI authentication` 은 규칙의 "버전 명시 필수"와 어긋난다. deliberation-pattern 의 "실행 시간" 합계 26-41분은 행 상한 합 39 와 다르다. | 하위 에이전트 대조. | SKILL 은 개요와 링크만 남긴다. |
| P2-11 [보고] | `packaging/README.md:1, 68, 71, 74, 77-80`; `plugins/common/hooks/examples/README.md:90`; `plugins/common/README.md:34-40` | 폐기된 W-019·D-3 ID 를 현재 문서 본문에 쓴다. 비활성 타겟 목록에 `pi` 가 빠졌다. "CLAUDE.md 최상위 안전 규율과 동일"은 CLAUDE.md 에 stash 규율이 없어서 틀렸다. "planning, development, review, meta categories"는 평탄화 이후 폴더 카테고리가 아니고 review 카테고리도 표에 없다. | 하위 에이전트 대조. | ID 를 스펙 경로로 바꾸고 목록·설명을 현재 사실로 맞춘다. |
| P2-12 [보고] | `docs/conventions/release-process.md`(Rules 변경 절), AGENTS.md/GEMINI.md 재생성 | 컨벤션 문서를 고치면 `AGENTS.md`·`GEMINI.md` 인라인 사본 재생성과 CHANGELOG 의 마커 sha 갱신이 필요하다. 이 문서 수정 작업(P1-16, P1-17)에 딸린 비용이다. | release-process.md 의 sha 절. | 고칠 때 한 묶음으로 처리한다. |
| P2-13 [보고] | 여러 research·spec 파일 | `docs/specs/2026-09-28-plans-replace-works/README.md`(+brief-T1/T2/T3)에는 `status` 필드와 frontmatter 가 없고 제목이 "W-046"이다(최근 5건의 지위 형식이 frontmatter 2·본문 `**상태**` 2·없음 1 로 제각각). `2026-09-30-boundary-enforcement/spec.md:119-130` 은 `status: done` 인데 완료 조건 블록이 존재하지 않는 `plugins/common/agents/dev/*.md` 를 쓴다(5.3.0 이후 실행 불가) [확인]. `2026-08-27-superpowers-distribution.md` 부록 5·120행 번호, `research/2026-07-harness-loop-engineering.md` 의 "별도 Work" 등. | 메인이 boundary-enforcement 완료 조건을 직접 읽어 `agents/dev/` 경로 확인. | frontmatter `status:`·`shipped:` 로 통일하고, 5.3.0 이전 경로 블록에는 "당시 기준" 주석을 단다. |
| P3-1 | `packaging/README.md:77-80`, `CHANGELOG.md:68-70`(5.2.2 "73개 파일"), `README.md:22-24`("warns you once") | 설명이 실제 구성과 몇 군데 어긋난다. "once"를 뒷받침하는 중복 억제 로직이 `session-check.py` 에서 grep 으로 보이지 않는다. | 하위 에이전트 보고. | 각각 현재 사실로 정정하거나 단어를 삭제한다. |
| P3-2 | `README.md:345-350` | Delegation Signal 폐기 포인터가 `docs/specs/2026-08-27-delegation-signal-contract-review.md` 인데 CLAUDE.md 는 `docs/architecture/delegation-signal-retirement.md` 를 소유 문서로 가리킨다. | 둘 다 실존. | 소유 문서로 통일한다. |
| P3-3 | `CLAUDE.md:55-74`, `:63`, `:66`, `:208-213` | Key Skills 표에 `brainstorming`·`using-hiway-kit` 이 없다. `web-research` 를 "MCP-powered"라고 쓰고, `agent-creator` 를 "Generate plugin agents"라고 쓴다(스킬은 프로젝트·사용자 에이전트를 만든다). Phase 3 이 `review + security scan (parallel)` 로만 적혀 auto-dev 의 T-spec 선행이 없다. | 하위 에이전트 대조, `skills/` 목록. | 한 줄씩 보정한다. |
| P3-4 | `CLAUDE.md:126, 190, 235, 284`; `README.md:1`; `docs/architecture/**`; `docs/specs/**` 외 | 풀리지 않는 `W-xxx`, `D-xx`, `Spec n` ID 가 현재형 본문에 남아 있다. `delegation-contract.md` 의 `D-35` 등 내부 결정 ID 는 소비자 세션에서 풀리지 않는다. | `git grep -n '\bW-0[0-9][0-9]\b'`. | 날짜·스펙 경로로 대체하거나 규범 문장에서는 ID 를 빼고 근거를 인라인한다. |
| P3-5 | `docs/conventions/measurement-traps.md:11`, `rules/*.md` frontmatter `activates:` | "아래 둘은 오늘 하루에…"인데 본문은 §1~9 다. `activates:` 는 서술 전용이고 코드가 읽지 않는다(`session-start.py::conditional_signals` 가 SSOT). | 하위 에이전트 보고. | 문장 수정, `activates:` 이중 서술 정리. |
| P3-6 | `docs/research/2026-09-11-cross-harness-norm-integration.md:19, 62`; `2026-09-15-dryforge-evaluation.md:287` | `plugins/common/hooks/export_harness.py`(5.2.0 이후 `tools/`) 경로, `poitne-radiant-inc` 오타, 해소된 `[미확인]` 이 남아 있다. | `git grep 'hooks/export_harness'` 에서 이 줄만 걸린다. | 정정하거나 "→ 해소" 주석을 단다. |
| P3-7 | `docs/codex-submission-checklist.md:81`, `marketplace-submission.md:19, 23` | OpenAI org-id·지원 케이스 번호·webhook id 가 레포에 평문으로 있다. 비밀은 아니다(민감도는 [추정]). | 하위 에이전트 보고. | 필요 없으면 제거한다. |
| P3-8 | `scripts/verify-done.sh:679-680`, `scripts/sync-rule-mirror.sh:5` | "§17 은 D-22 몫으로 예약"이 낡았다(§17 은 이미 사용 중). 미러 "(9개)"는 5개가 맞다. 문서 범위 밖. | 하위 에이전트 보고. | 주석 정정. |
| P3-9 | `CLAUDE.md` + `@import` 합계 | [보고] 합계가 상한 43,008B 에 37B 차이(42,971B)다. 이 문서들을 늘리는 수정(import 추가 등)은 §15 예산 게이트에 걸린다. | 하위 에이전트 측정. | 수정 계획에 "줄이면서 고친다"를 전제로 넣는다. |

---

## 보류·제외한 발견 (오탐 또는 증거 부족)

- `hooks/examples/README.md:71` 의 설치 JSON 이 `${CLAUDE_PLUGIN_ROOT}` 를 프로젝트 `.claude/settings.json` 에서 쓰라는 점: 하위 에이전트는 P0 로 올렸지만 근거가 공식 문서의 fast-model 요약이고 실행은 하지 않았다. **P1 [추정, 미실측]** 로 낮춘다. 프로젝트 설정에서 이 변수가 풀리는지 한 번 실측해야 한다(풀리지 않으면 P0).
- `docs/architecture/rules/task-resume.md:82` 의 `docs/works/active/`: 구버전 Work 소비자를 위한 정당한 서술(`session-start.py:97,172` 가 실제로 그 안내를 낸다). 결함 아님.
- 링크 전수 결과: Markdown 링크(`[…](…)`)와 `@import` 에서 실제로 끊어진 것은 **0건**(자기 스크립트 `links.py`로 확인). 백틱 경로는 상대 기준이 섞여 오탐이 많았고, 실제 결함은 위 표에 반영했다(`reference-vs-judgment`, `native-absorption:59`, `path-containment`, `harness-export` 등).
- 스킬이 부르는 에이전트 15종, `tools/*.py` 3개, 규칙 12개, `hooks/examples/*`, `setup/git-hooks/*` 이름은 모두 실존한다 [보고, 일부 메인 확인]. `checklist.py init/show/status/verify/complete` 인자와 exit 코드도 스킬 호출과 일치한다.

---

## (b) 문서 소유(SSOT) 지도 제안

원칙: 주제마다 정본은 **하나**. 나머지는 한 줄 요약 + 링크만 둔다. 요약에는 숫자·목록을 쓰지 않는다(열거하면 낡는다 — 이 레포가 두 번 적은 교훈).

| 주제 | 정본(1개) | 가리키기만 해야 할 문서 | 현재 어긋난 곳 |
|---|---|---|---|
| 에이전트 모델·isolation·maxTurns | 각 `agents/*.md` frontmatter (표 역할: `rules/agent-system.md`) | CLAUDE.md, 미러 agent-system, README, native-absorption | CLAUDE.md:97 maxTurns, README 모델 표 |
| 크기 기준 Small/Medium/Large · 규모별 완료 조건 | `skills/plan-task/references/elicitation.md §6` | plan-task, brainstorming, using-hiway-kit, CLAUDE.md, 미러 planning-protocol, `rules/agent-system.md` Phase Gate | 3중 중복(P1-11), 미러 시간 열(P1-20), CLAUDE.md "10~100+" |
| Phase Gate 출구 조건 | `rules/agent-system.md` Phase Gate | `docs/architecture/phase-gate-pattern.md`(해설만), auto-dev, CLAUDE.md | P0-5, P1-6, P1-10, P1-14 |
| 릴리스 절차 | `docs/conventions/release-process.md` | CLAUDE.md(`@import` 또는 포인터 1줄), CONTRIBUTING | P1-1 |
| 설치·마켓 경로·캐시 구조 | `README.md` 설치 절 | CLAUDE.md Installation/Distribution, `plugins/common/README.md`, `marketplace-submission.md` 상단 | P0-1, P1-2, P1-3 |
| 배포 채널별 상태(Claude 디렉토리·OpenAI·커뮤니티) | `docs/marketplace-submission.md` 상단 **요약표**(신설: 채널 / 상태 / 확인일) | CLAUDE.md Distribution(한 줄+링크), README, codex-submission-checklist(절차·기록만) | 4곳 중복(P1-3~5, P1-7) |
| 네이티브 흡수 판정 | `docs/native-absorption.md`(표는 판정+스펙 경로만) | specs, CHANGELOG | 근거 열이 스펙 본문 복제(P2-2) |
| 컨벤션 색인 | `docs/conventions/README.md`(전부 색인) | CLAUDE.md(`@import` 대상 선택) | P1-18 |
| 폐기된 기능 기록 | `docs/architecture/delegation-signal-retirement.md` | CLAUDE.md 한 줄, README 한 줄 | README:345 포인터 불일치(P3-2) |
| harness-export 종료코드·분류 | `tools/export_harness.py` docstring | `skills/harness-export/SKILL.md`(코드를 인용하지 말고 `--help`/docstring 가리키기) | P0-2, P0-3 |
| Task 도구 폴백 | `skills/plan-task/references/task-tools-fallback.md` | plan-task, auto-dev, brainstorming | P1-12 |
| 시점 고정 문서(research, specs) | 각 문서 머리의 `status:` 배너 | 현행 판단은 위 정본으로 | pipeline-plan-v2, research 일부 |

---

## (c) 고아·중복 목록과 처분안

inbound 링크 수는 `git grep -F <파일명>` 으로 CHANGELOG·archive·자기 자신을 제외하고 센 값이다.

| 문서 | inbound | 문제 | 처분 |
|---|---|---|---|
| `docs/pipeline-reinforcement-plan-v2.md` | specs 3건·census 뿐(README·CLAUDE.md 0) | 지위 표기 없음. 틀린 마커 레시피와 구버전 Track 1 명세가 현재형(P0-6). 같은 문서에서 Track 2 가 "보류"와 "폐기"로 갈린다. | **삭제를 권고.** Track 2 판정은 이미 `delegation-signal-retirement.md` 가 소유하고, Track 1 명세는 코드(807줄)와 어긋나 읽는 사람을 틀린 길로 보낸다. 삭제가 부담스러우면 머리에 `> 상태: 역사`를 달고 코드 블록만 걷어낸다. |
| `docs/research/2026-09-11-cross-harness-norm-integration.md` | **0** | 고아. `superpowers-distribution` 과 중복이고 결론 절반이 하단 검토에서 정정됐다. | 역사 배너 + 정정 인라인 후 보존, 또는 가치가 낮으면 삭제. |
| `docs/research/2026-07-long-running-loop-agents.md`, `2026-07-harness-loop-engineering.md` | census 에서만 | 지위 표기 없음, Work 시스템 현재형. | 시점 고정 배너. `docs/research/README.md` 를 신설해 research 6건을 한 곳에서 지위와 함께 소개. |
| `docs/research/2026-09-08-plugin-directory-status.md` | 1 | §4 "`[unresolved]` 중첩 레이아웃"이 5.3.0 평탄화로 해소됐는데 미반영. | 갱신 후 유지. |
| `docs/marketplace-submission.md` ↔ `docs/codex-submission-checklist.md` ↔ CLAUDE.md "Distribution" ↔ README | 4곳 중복 | 상태가 네 곳에 있고 각각 다른 시점 스냅샷이다. | 상태 SSOT 를 marketplace-submission 상단 요약표로 일원화. codex 문서는 절차·기록만, CLAUDE.md·README 는 한 줄+링크. |
| `docs/native-absorption.md` ↔ specs | 근거 열이 스펙 본문을 복제 | 장문 복제가 낡는다. | 표에는 판정과 스펙 경로만. |
| `docs/specs/2026-04-21-superpowers-upgrade-{design,plan}.md`, `2026-09-13-audit-hardening.md`, `2026-09-14-neutral-coordination-lifecycle.md`, `2026-09-27-model-provenance/brief-*`, `2026-09-28-plans-replace-works/brief-*` | 0 | 고아 스펙·브리프. 일부는 status 필드가 없다. | specs 는 이력 보존이 목적이라 삭제하지 않는다. `docs/specs/README.md`(색인 + status)를 신설하거나, 각 파일 머리에 `status:`·`shipped:` 를 단다. |
| `docs/conventions/` 11개 중 색인에 없는 3개(warning-signal, measurement-traps, coordination) | — | 색인 불완전(P1-18). | 색인표를 전부 채운다. |
| `docs/personal/` | — | 레포에 없음(`.gitignore` 로 의도된 비공개). 문서에서 가리키는 곳도 없다. | 조치 없음. 범위 정의에서 제외. |

---

## (d) 게이트 커버리지 — 게이트가 못 잡는 종류, 그리고 자동화 제안

### 게이트가 지금 잡는 것 (확인)

`verify-done.sh` 33 pass. 문서 관련은 개수/버전(§6), 배포물 안 `scripts/*.sh`·`plugins/common/(skills|agents|rules|hooks|tools)/…` 풀경로 참조(§7), AGENTS.md·타겟 매니페스트·이름 파생 드리프트, 룰 CHECKSUMS·미러 sha, 구 이름 잔재(§20), 스킬 강등 경로(§23)다. 게이트 번호는 11/13/15/16 순으로 뒤섞여 있고 §12 는 의도된 결번이다(코드 쪽 문제는 아님).

### 게이트가 못 잡는 종류

| 종류 | 이번에 걸린 예 | 왜 못 잡나 |
|---|---|---|
| 1. `docs/`·루트 md 의 **참조 실재성**(스크립트·도구·헬퍼 이름·§번호) | P0-4(`db-tunnel.sh`), P1-17(`_resolve_target`), P1-30, `codex-submission-checklist` §14 | §7 은 `plugins/common` 만 본다. `docs/`·`README`·`CLAUDE.md` 는 대상 밖이다(warning-signal §5 "대상 밖은 어디인가"가 정확히 이 구멍). |
| 2. **시점 고정 문서의 지위 표기 유무**(현행/역사/제안) | P0-6, P1-3~5, P1-31 | 지위라는 필드가 없어 기계가 "이 문서가 낡은지"를 판정할 입력이 없다. |
| 3. **코드가 바뀐 뒤 코드를 인용한 서술**(exit code, 딕셔너리, 헬퍼 이름, 훅 타입) | P0-2, P0-3, P0-5, P1-17 | 서술이 코드의 사실을 복제한 것인데 복제본을 코드와 대조하는 장치가 없다. |
| 4. **문서 내부 모순**(같은 파일의 "보류"/"폐기", "three"/"넷", 표 열 수) | P0-6, P1-16, P2-1 | 의미 검사다. 표 열 수 같은 형식 문제는 기계로 가능한데 하지 않는다. |
| 5. **절차의 실행 가능성**(폴백이 도구 스키마와 맞는가) | P1-12, P1-24 | 스킬 절차를 도구 CLI 와 대조하는 검사가 없다. §23 은 "강등 경로가 있는가"만 보고 "그 경로가 실행 가능한가"는 보지 않는다. |
| 6. **미러의 내용 동기**(sha 가 안 바뀌면 통과) | P0-4, P1-19, P1-20, P1-21 | §7 미러 게이트는 주입 룰 sha 가 바뀔 때만 울린다. 사람이 `--regenerate` 만 하고 해설을 안 고친 미러도, 처음부터 틀린 미러도 통과한다(warning-signal §4 "이 검사가 도는 조건을 한 문장으로": "규범 sha 가 바뀌었을 때 검사한다" — 미러가 틀려 있는 상태 자체는 도달 경로가 없다). |

### 자동화 제안 (재발 방지 효과 순)

1. **`scripts/check_doc_refs.py` — 전 문서 참조 실재성 게이트 (종류 1, 3 의 일부 해소)**
   - 대상: `git ls-files '*.md'` 중 `docs/CHANGELOG-archive.md`·`CHANGELOG.md`·`status: historical` 문서를 **제외**(대상 나열이 아니라 제외 나열 — warning-signal §5).
   - 검사: ① 마크다운 링크·`@import` ② 슬래시를 포함한 백틱 경로 ③ 백틱 `*.sh|*.py` 파일명(레포 전체에서 basename 이 하나도 없으면 red) ④ 코드 인용 식별자(`def`/함수명 형태 백틱)는 `git grep -F` 로 소스에 있는지(없으면 red; 표본 규모가 작아 오탐 가능성은 예외 파일로 관리).
   - 도는 조건(한 문장): "모든 PR/푸시에서, 제외 목록에 없는 md 가 가리키는 경로·스크립트·함수 이름이 레포에 없으면 실패한다." 이번 감사의 P0-4·P1-17·P1-30 이 이것 하나로 잡혔을 것이다. `links.py` 프로토타입을 정리하면 된다.
2. **문서 지위 front matter + 게이트 (종류 2, 4)**
   - `docs/**/*.md`(research·specs 포함)에 `status: current | historical | proposal | superseded` 와 `as_of:` 를 필수로 한다. 게이트 규칙: ① 필드 없으면 red(신규 파일에 기본값 강제) ② `status: historical` 이 아닌 문서는 제안 1 의 검사 대상, historical 은 검사 제외 ③ `status: current` 인 문서는 `packaging/name-targets.json` 식 **금지 토큰 목록**(`agents/(dev|meta|planning)`, `hooks/(checklist|feedback_ledger|export_harness)`, `docs/works`, `work.sh`, `claude-code-kit`, `W-0\d\d`)을 포함하면 red. §20(구 이름)의 확장판이며, 도입 비용이 낮다.
   - 이번 감사가 찾은 "정정이 문서 끝에만 붙음" 부류는 `status:` 를 올리는 순간(`current → superseded`) 본문 수정을 강제하는 장치가 된다.
3. **표 형식 검사 + 코드 사실 복제 대조 (종류 4, 3)**
   - `scripts/tests` 에 이미 있는 `check_doc_counts.py` 옆에 마크다운 표 열 수 검사를 추가한다(`tables.py` 프로토타입은 이미 레포 전체를 훑어 `native-absorption.md` 한 군데만 잡았고 오탐 0건). 코드 스팬 안의 파이프도 GFM 에서는 열을 가르므로 이스케이프 여부까지 본다.
   - 보너스: "코드 사실을 복제한 서술" 은 가능하면 문서에서 지우고 `--help`·docstring 으로 가리킨다(`harness-export` 가 대표). 복제를 못 지우면 제안 1 ④ 가 담당한다. 미러 게이트에는 "미러 파일의 mtime/sha 를 규범 변경과 같은 커밋에서 건드렸는가"가 아니라 **미러가 인용한 숫자·경로·스크립트 이름을 소스에서 재확인**하는 단계를 추가해 종류 6 을 줄일 수 있다(예: `db-tunnel.sh`, `10,240B`).

### 사람이 직접 해야 하는 것 (자동화로 못 닫음)

- Task 도구 폴백(P1-12)처럼 **절차의 의미적 실행 가능성**은 사람이 한 번 시뮬레이션해야 한다. `plan-task`→`auto-dev` 를 Task 도구 없는 하네스에서 끝까지 돌려 보는 eval 시나리오를 `evals/` 에 하나 넣는 것이 가장 싸다(`/eval-forge`).
- `hooks/examples/README.md` 의 `${CLAUDE_PLUGIN_ROOT}` 실측(위 "보류" 항목), Antigravity 평탄화 후 에이전트 인식 실측은 사람이 한 번 돌려야 한다.

---

## 부록 — 직접 재확인한 항목 목록

메인이 원본을 열어 일치를 확인한 항목: P0-1(`setup.sh:139-140`), P0-2·3(`export_harness.py:369-375, 1229-1241` + SKILL 본문), P0-4(`mcp-usage` 미러 50행·규범 42행), P0-5(phase-gate-pattern 140-145·hooks.json), P0-6(`pipeline-plan` 337행·머리), P1-1(release-process ↔ CLAUDE.md), P1-2(캐시 디렉토리 실측), P1-3(marketplace-submission 220-226·3-8), P1-7·9, P1-10(`grep 'Must Fix'`), P1-13(frontmatter awk), P1-17(`grep _resolve_`), P1-22(`child-git-guard.py:94-104`), P1-23, P1-30, P2-1(열 수 검사기), P2-3~5, P2-13(boundary-enforcement 완료 조건).
재확인하지 않은 항목은 **[보고]** 로 표시했다.

산출 스크립트(참고): 스크래치패드 `links.py`(참조 전수), `tables.py`(표 열 수), `verify.out`(게이트 전체 출력, rc=0).
