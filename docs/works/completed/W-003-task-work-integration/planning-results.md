# Planning 상세 결과

> Work ID: W-003
> Last Updated: 2026-04-06T00:00:00Z

---

## 규모 판단 (Phase 0)

- **크기**: Medium
- **판단 근거**: 8개 파일 수정/신규 (스킬 2개, hook 2개, rules 1개, 참조문서 2개, work.sh)
- **실행 경로**: Planning → Development → Validation

---

## 요구사항 명확화 (Phase 1)

### 핵심 목표

| ID  | 목표                                            | 우선순위 |
| --- | ----------------------------------------------- | -------- |
| A   | Task 생성/추적 — plan-task, auto-dev 하드게이트 | P0       |
| B   | 병렬 실행 — blockedBy 의존성 그래프 실제 적용   | P0       |
| C   | SessionStart hook — active Work 자동 로드       | P0       |
| D   | progress.md Task Map (description 컬럼 포함)    | P0       |
| E   | Task 재생성 알고리즘 — ID 매핑 + 완료 Task 제외 | P0       |
| F   | work.sh 한글 버그 수정 + resume 명령 추가       | P1       |

### 영향 범위 (v2 — 적대적 리뷰 반영)

- `plugins/common/skills/plan-task/skill.md` — Step 순서 재정립, TaskList 선행 체크
- `plugins/common/skills/auto-dev/skill.md` — 병렬 dispatch, 직접 탐색
- `plugins/common/skills/references/work-system.md` — Task Map 포맷 변경
- `plugins/common/hooks/session-start.py` — 신규 (get_project_root, JSON 출력)
- `plugins/common/hooks/hooks.json` — session-start.py SessionStart 등록
- `plugins/common/setup/session-check.py` — RULE_FILES에 task-resume.md 추가
- `plugins/common/rules/task-resume.md` — 신규 (재생성 알고리즘)
- `scripts/work.sh` — to_slug 한글 버그 수정 + resume 명령

### 기술적 제약 (공식 문서 확인)

- TaskCreate는 deferred tool → 스킬에서 ToolSearch 선행 필수
- Task는 세션 스코프 → Work 파일이 ground truth, Task는 매 세션 재생성
- SessionStart hook output: `{"hookSpecificOutput": {"additionalContext": "..."}}` JSON 필수
- CLAUDE_CODE_TASK_LIST_ID로 named task list 공유 가능하나 Claude Code 시작 전 env 필요
- rules는 session-check.py RULE_FILES 목록에 추가해야 additionalContext로 주입됨

---

## 구현 계획 (Phase 2)

### Task 그래프 (v2)

| Task | 제목                                                  | blockedBy                    |
| ---- | ----------------------------------------------------- | ---------------------------- |
| T-1  | work.sh 버그 수정 + resume 명령 추가                  | -                            |
| T-2  | progress.md Task Map 포맷 확정 (description 컬럼)     | -                            |
| T-3  | work-system.md 업데이트                               | T-2                          |
| T-4  | plan-task 스킬 수정 (Step 순서 재정립, TaskList 선행) | T-2                          |
| T-5  | auto-dev 스킬 수정 (병렬 dispatch, 직접 탐색)         | T-2                          |
| T-6  | task-resume.md 규칙 파일 작성 (재생성 알고리즘)       | T-2                          |
| T-7  | session-start.py 작성 (get_project_root, JSON 출력)   | T-2                          |
| T-8  | session-check.py 수정 (RULE_FILES에 task-resume.md)   | T-6                          |
| T-9  | hooks.json 수정 (session-start.py 등록)               | T-7                          |
| T-10 | 통합 테스트                                           | T-1, T-3, T-4, T-5, T-8, T-9 |

### 병렬 실행 계획

- T-1, T-2 동시 실행 가능
- T-2 완료 후 T-3, T-4, T-5, T-6, T-7 동시 실행 가능
- T-6 완료 후 T-8 / T-7 완료 후 T-9
- 전체 완료 후 T-10

### 설계 문서 위치

`docs/works/idea/W-003-task-work-integration/design.md`
