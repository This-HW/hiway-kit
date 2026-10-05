### 스킬 로직·폴백·경로 규약 (W3 — 스펙 D10·D11·D12)

- **킷 도구 탐색 규약 신설** — `skills/plan-task/references/task-tools-fallback.md` §A 가 SSOT.
  순서 ① `$CLAUDE_PLUGIN_ROOT` ② SKILL.md 기준 `../../` ③ `~/.claude/plugins/cache/*/hiway-kit/*/`
  ④ `~/.codex/plugins/cache/*/hiway-kit/*/` ⑤ 실패 시 사용자에게 루트 경로를 묻고 직접 지정(`--plugin-root`).
  쉘 함수 `kit_root` 한 토막만 두고 auto-dev(ledger·stop-validator 마커)·plan-task·skill-forge·
  test/debug/review 의 `~/.claude/plugins/cache/*/*/*/` 글롭을 그 절 참조로 교체(B-P2-9, A-P1-6).
  ③ 은 마켓플레이스 디렉토리가 아니라 **버전 디렉토리 이름**으로 정렬한다 — 경로 전체를 `sort -V` 하면
  실측에서 `anthropic-plugin-directory/…/5.3.0` 대신 `hiway-kit/…/5.2.2` 가 이겼다.
- **Task 도구 폴백을 실행 가능하게 고침** (B-P1-12) — `checklist.py` 의 `_REQUIRED_FIELDS` 는 항목마다
  비어 있지 않은 `verify` 를 요구하고 `blockedBy` 필드가 없다. 그래서 `[Planning]`·`[Brainstorm]`·
  `[Validation]` 은 checklist 가 아니라 **대화창 진행표 + `plan.md`**(`## 검증 결과`)로, `[Dev]` 만
  checklist(`## 완료 조건` 명령 = `verify`, 선행은 id 순서 + `description` 의 `(선행: …)`)로 추적한다.
  auto-dev 의 `TaskUpdate(failed)`·`TaskList` 잔존 확인은 "도구가 있으면" 으로 가드. Task 도구 없는
  하네스에서 plan-task → auto-dev 를 처음부터 끝까지 한 번 실제로 따라가며 검증.
- **Small 경로·크기 기준 정본을 `elicitation.md §6` 한 곳으로** (B-P1-11) — plan-task·brainstorming·
  using-hiway-kit 의 임계값 복제를 참조로 교체. plan-task 는 Small 이면 계획 파일·checklist·Validation
  3단계를 씌우지 않는다.
- **brainstorming** 의 "대기 태스크가 다음 세션에 잔존한다 — 정상" 오서술을 정정하고 존재하지 않는
  `task-resume` 참조를 제거(B-P1-23).
- **test/debug**: `fix-bugs`(worktree 격리) 결과를 이 세션에 **반영한 뒤** 재실행·검증하는 단계와
  재시도 상한(최대 3회 · 무진전 2회) 추가, debug 진단 전용 호출의 격리 이득 없음 명시(B-P1-24).
- **auto-dev T-review** 가 `review-code` 호출 규칙(diff 인라인·6파일 배치·`## 완료:` 줄)을
  `review` 스킬 2단계 참조로 가리킨다 — 빈 리뷰가 "결함 0건"으로 읽혀 T-merge 를 통과하던 경로(B-P1-25).
- **review**: 0단계를 **대상 확정**으로 앞당기고 ruff 는 그 목록으로 실행(대상 없는 "통과" 제거),
  `--diff-filter=d`, stderr 비은닉, ruff 종료코드 판독(0/1/2), 4단계 표를 `review-code` 실제 출력
  (REJECT/CONDITIONAL/ACCEPT · CRITICAL/HIGH/MEDIUM/LOW)으로, 보안 파일 패턴·기본 범위의 킷 전용
  경로(`hooks/*.py`·`agents/**`) 제거(B-P1-26, B-P2-9). 시뮬레이션에서 zsh 가 따옴표 없는 목록 변수를
  단어 분리하지 않아 `ruff check $PYS` 가 깨지는 것을 발견 → `sh -c` 로 전달.
- **skill-forge**: 재현성 미충족 강등 경로를 feedback ledger 가 아닌 "완료 보고에만 기록"으로(B-P1-27).
- **cross-engine-review**: 우편함 기본값을 트리 상대경로에서 **모든 워크트리가 공유하는
  `git-common-dir` 아래 절대경로**로, 쓰기 확인·결론 보존 방법 추가(B-P1-28).
- **multi-perspective-review**: (C-M4) **관점별 근거 필수**(근거 없는 주장은 집계 제외·리포트 "집계 제외"
  절에 보존) + Round 2 말미 **명시적 반대 라운드**(반대자가 근거를 내야 합의 통과, 미반박 반대는 Round 3
  충돌로, 시도 기록 없는 "반대 없음"은 무효) — 병렬·순차(서브에이전트 없는 하네스) 경로 모두 적용.
  3중 복제 정리(SKILL 은 개요+링크, 리포트 구조는 `deliberation-pattern.md` 로), 실행 시간 합계
  26-41 → 26-39(행 상한 합) 정정(B-P2-10). web-research 의 MCP 선택 3중 반복을 가이드 표 하나로,
  Context7 예시에 버전 명시(B-P2-10).
- 경로 기준을 `skills/<name>/references/…`(플러그인 루트 기준)로 통일(plan-task, B-P2-9).
- 스킬 `description` 은 불변(발동률 회귀 방지 — W5 파일럿 측정 전까지).
