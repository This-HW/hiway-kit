# W3 skills 완료 보고

브랜치 `This-HW/remed-skills` · 기준 커밋 `ea87de2` (조상 확인 OK) · 구현 커밋 `5e42440`. 버전·CHANGELOG 불변,
조각은 `changelog-W3.md`. 소유 표 밖 파일 수정 0 (`git diff --stat ea87de2..HEAD` 가 `plugins/common/skills/**` 와 이 폴더뿐).

## 발견 ID → 파일:라인 (D11·D12·C-M4)

| ID | 반영 위치 |
| --- | --- |
| B-P1-11 | `plan-task/SKILL.md` Step 1-1 (임계값 복제 삭제 → elicitation §6) · `:149` Small 경로 · `brainstorming/SKILL.md:11` · `using-hiway-kit/SKILL.md:20` |
| B-P1-12 | `plan-task/references/task-tools-fallback.md` §B(`:56-`) · `auto-dev/SKILL.md:18,40-43,61,76,125,169,185,255-` · `plan-task/SKILL.md:36-,Step 3` · `brainstorming/SKILL.md` 체크리스트 절 |
| B-P1-23 | `brainstorming/SKILL.md:100` |
| B-P1-24 | `test/SKILL.md:20,62-,88-` · `debug/SKILL.md:20,37-,89-94` |
| B-P1-25 | `auto-dev/SKILL.md:178` (T-review → review/SKILL.md 2단계 참조) |
| B-P1-26 | `review/SKILL.md:19-` (0단계 대상 확정) · `:48-` (0.2 ruff, rc 판독) · 4단계 표 (REJECT/CONDITIONAL/ACCEPT·C/H/M/L) |
| B-P1-27 | `skill-forge/SKILL.md:30` |
| B-P1-28 | `cross-engine-review/SKILL.md:39-` (`git-common-dir` 절대경로) |
| B-P2-9 | `task-tools-fallback.md` §A · 경로 통일 `plan-task/SKILL.md` · `review/SKILL.md` 보안 패턴·기본 범위 · auto-dev/skill-forge/test/debug/review 의 cache 글롭 제거 |
| B-P2-10 | `multi-perspective-review/SKILL.md` (개요+링크) · `deliberation-pattern.md` (리포트 구조 이관, 26-39분) · `web-research/SKILL.md` (MCP 선택 가이드 표 1곳, 버전 명시 예시) |
| C-M4 | `multi-perspective-review/SKILL.md:50-` · `deliberation-pattern.md` "Round 2 마지막: 명시적 반대"·근거 규칙·종합 1 의 0단계 · 순차 경로 `SKILL.md` B-4 · `perspectives-guide.md`/`conflict-resolution.md`/`examples.md` 정합 |
| D10/D12 | `task-tools-fallback.md` §A (순서 ①~⑤, `kit_root` 쉘 토막 1개) |

반영 못 한 ID: 없음. (`harness-export/SKILL.md:80` 의 글롭은 W2 소유라 건드리지 않았다 — D10 §A 참조로 바꾸는 것은 W2 몫.)

## 시뮬레이션 — Task 도구 없는 하네스에서 plan-task → auto-dev (scratch 소비자 레포, 플러그인 파일 없음)

이 세션은 TaskCreate/TaskUpdate/TaskList 가 없는 환경이라 전제가 실제로 성립한다. `CLAUDE_PLUGIN_ROOT` 미설정, `SKILL_DIR` 만 지정.

1. plan-task Step 0 → fallback §B: Planning 단계는 진행표(대화창). `checklist.py init` 에 빈 verify 를 넣어 보면 **rc 2** (`항목 0('P1') verify가 비어있음`) — Planning 을 checklist 에 걸 수 없음을 확인.
2. Step 1-1: 규모 판정 = elicitation §6 (Medium) → `docs/plans/2026-10-05-demo/plan.md` (plan-format 절 5개).
3. Step 3: `status: in-progress`, auto-dev invoke.
4. auto-dev Step 0: `plan.md` 읽기 → checklist 없음 → 재개 위치 Step 1. 도구 없음 → §B.
5. Step 1: `kit_root`(②, `SKILL_DIR`=auto-dev) → `checklist.py init` D1·D2 (D2 description `(선행: D1)`) rc 0, `status` rc 1.
6. Step 2: 미구현 상태 `complete D1` → rc 1(verify 거부, AttributeError 출력) → 구현 → D1 rc 0 · D2 rc 0 · `status` rc 0.
7. Step 3 T-review 대상 확정(review 0단계): `BASE=HEAD~1`, `--diff-filter=d` 목록, `PYS`. **여기서 결함 발견**: zsh 에서 `ruff check $PYS` 가 단어 분리되지 않아 `E902 No such file` → `sh -c` 로 수정, 재실행 rc 0. 위반 파일(`import os`)로 rc 1 도 확인.
8. feedback ledger: `kit_root` 로 `feedback_ledger.py digest` rc 0 (upsert 는 호출하지 않음).
9. T-merge 마커: `kit_root` → `stop-validator.py` 로드 → 마커 기록 rc 0 (`$TMPDIR/claude-<uid>/.claude_validated_*` 생성 확인).
10. `## 검증 결과` 추가, `status: done`, `checklist.py status` rc 0. 재개 시뮬(진행표 소실): `plan.md`·`checklist.json` 만으로 상태 복원 확인.

한계: `review-code`/`security-scan` 에이전트 호출 자체(T-review/T-security 본체)와 MPR 실제 실행은 하지 않았다 — 에이전트·스킬 정의는 설치 캐시에서 로드되므로 이 세션에서 변경 효과를 관측할 수 없다(CLAUDE.md "Editing an agent/skill does NOT affect the current session"). MPR 변경은 문서 검토만 했다.

## `kit_root` 검증 (실물 환경)

| 경로 | 결과 |
| --- | --- |
| ① `CLAUDE_PLUGIN_ROOT` 유효 / 무효(없는 디렉토리) | 유효→그 경로 / 무효→③ 으로 폴백 |
| ② `SKILL_DIR` | `<루트>` 해석 |
| ③ 실 HOME | `anthropic-plugin-directory/hiway-kit/5.3.0-e7181cbbfb6c` — **수정 전엔 `hiway-kit/hiway-kit/5.2.2`(옛 버전)가 이겼다**: 경로 전체를 `sort -V` 하면 마켓플레이스 이름이 먼저 정렬됨. 버전 디렉토리 이름(`$NF`)만 정렬하도록 고침 (되돌려-FAIL 실증) |
| ④ 가짜 HOME(.codex 만) 5.9.0·5.10.0 | 5.10.0 |
| ⑤ 아무것도 없음 | stderr 안내 + rc 1 |
| zsh/bash 양쪽, 공백 낀 HOME | 동일 결과. zsh `no matches found` 소음은 `2>/dev/null` 로 제거 |

## 명령별 rc

- `scripts/verify-done.sh` → **rc 0, 기계 검사 33 pass / 0 fail** (§23 "위임 스킬 전부 강등 경로 보유" ✓ 포함). red 섹션 없음.
- `./scripts/run-evals.sh --validate` → **rc 0** ("모든 시나리오 스키마 OK").
- `bash -n` 으로 스킬 내 bash 블록 14개 문법 검사: 12 OK, 2건은 `<placeholder>` 가 든 템플릿(원래부터 그런 형식).

## 미결 / 컨트롤에게

- `rules/definition-of-done.md` "Task 마감 규율"의 Task 도구 조건부화(C-F3, D6)는 W2 몫 — 이쪽은 `task-tools-fallback.md` §B 를 가리키기만 하면 되도록 맞춰 둠.
- `harness-export/SKILL.md:80` 글롭 → §A 참조(W2).
- 위 changelog 조각과 별개로, `docs/` 쪽 서술(README 등)이 `task-tools-fallback.md` 의 옛 구조(대체 경로 = durable checklist 하나)를 인용하면 W1/컨트롤이 정합해야 한다. `git grep task-tools-fallback -- docs README.md ':!docs/specs'` 결과는 `docs/CHANGELOG-archive.md` 두 줄(역사 기록)뿐이다.
- auto-dev T-merge 마커 스니펫의 heredoc 종결자(`PY`)는 마크다운 목록 안에서 들여쓰기돼 있어 복사 시 dedent 가 필요하다 — 기존부터의 상태이며 이번엔 손대지 않았다.
- MPR 의 외부 근거(arxiv 2608.18167)는 감사 C-M4 인용이고 원문 재검증 전임을 스킬 본문에 그대로 적었다.
