# 브리프 T3 — rules-docs (W-046)

- **부모**: plan-control 컨트롤 세션 (Orca Run — 디스패치 spec 에 Run/Task id)
- **역할**: task-resume 룰을 계획 파일 기준으로 재작성 + 연관 룰·미러·루트 README 정합
- **워크트리**: Orca new-child 워크트리. **자기 브랜치에만 커밋**
- **기준 커밋**: 디스패치 spec 의 해시 — 착수 시 `git rev-parse HEAD` 대조
- 먼저 `child-session` 스킬 로드. 스펙 전문: `docs/specs/2026-09-28-plans-replace-works/README.md` — **§2.1 계약 변경 금지**

## ① 전제 — 구현 전에 검증한다

1. `rules/task-resume.md`(tier conditional, 활성 Work 존재 시 주입)는 progress.md Task Map 기반 Task 재생성
   알고리즘(ID 매핑 의사코드 포함)이다 `[confirmed]`. session-start 가 이 룰을 켜는 신호 키·파일명은 T1 이 **유지**한다
2. `rules/parallel-worktree.md:54` 가 공유 상태 파일 예시로 `docs/works/**` 를 든다 `[confirmed]`
3. `docs/architecture/rules/task-resume.md` 가 이 룰의 해설본 미러이고 `MIRROR.sha256` 이 체크섬을 기록한다.
   룰을 바꾸면 미러를 손보고 `scripts/sync-rule-mirror.sh --regenerate`, CHECKSUMS 재생성 필요 `[confirmed — CLAUDE.md]`
4. 루트 `README.md` L240("자체 Work 시스템" 표 행)·L301("Work 시스템" 언급)이 Work 를 소개한다 `[confirmed]`

## ② 범위

**IN**
1. `task-resume.md` 재작성 — 트리거: 활성 계획(`docs/plans/*/plan.md`, status≠done) 존재. 규칙:
   사용자가 재개를 명시하면 plan.md **원문**과 checklist 를 다시 읽고(요약 금지 — loop-engineering 재앵커),
   미완 checklist 항목부터 진행; 호스트 태스크 도구가 있으면 미완 항목으로 태스크를 만들 수 있으나 영속 상태는
   checklist 다. 단순 질문이면 "<계획> 이 진행 중이다, 재개할까요" 안내 후 대기. 자동으로 코드 수정 금지(기존 유지).
   병렬 위임은 parallel-worktree 의 파일 겹침 전제(기존 문구 유지). **짧게** — 현재보다 바이트가 줄어야 한다.
   frontmatter `activates:` 문구를 "활성 계획 존재" 로.
2. `parallel-worktree.md:54` 의 `docs/works/**` → `docs/plans/**`(계획 status·checklist).
3. CHECKSUMS 재생성, 미러 `docs/architecture/rules/task-resume.md` 를 새 룰에 맞춰 설명·참조만 하도록 갱신 →
   `scripts/sync-rule-mirror.sh --regenerate`.
4. 루트 README L240·L301 을 계획 파일 규약으로(짧게, SSOT 는 `skills/plan-task/references/plan-format.md` 를 가리킴 —
   그 파일은 T2 가 만든다).
5. 게이트: `python3 scripts/check_injection_budget.py` rc 0 · `python3 scripts/check_doc_counts.py` rc 0 ·
   `./scripts/verify-done.sh > /tmp/vd-t3.out 2>&1` rc 와 red 목록(§11 등 컨트롤 몫 red 는 보고만; §7 은 green 이어야 함)
6. 커밋 1~2개(자기 브랜치)

**OUT**: hooks·scripts·skills·CLAUDE.md·AGENTS/GEMINI·CHANGELOG·버전, 다른 룰

**완료 기준**: IN 5 통과(소유 밖 red 제외), §7 green, 보고 도착

## ③ 금지 — 명령 수준

- `git push` 금지. `main`·`This-HW/plan-control` 체크아웃·커밋 금지
- bare `git stash`/`git stash pop`/`git reset --hard`/`git clean -fd` 금지
- `scripts/run-evals.sh`·`claude -p` 실행 금지
- `scripts/export-harness.sh` 는 `--check` 만(재생성은 컨트롤)
- §2.1 계약 변경 금지. 소유 밖 파일 편집 금지. 게이트 rc 를 파이프에 물리지 말 것

## ④ 보고

- 첫 줄: `[T3 rules-docs] 완료 — <파일 N개, task-resume 바이트 전→후>, 커밋 <sha>, 테스트 <게이트 통과 수>`
- 본문: 명령과 rc · 좁힌 곳과 근거 · **병합 측 후속 조치** · 사실 등급
- **전달 수단**: `worker_done`. 터미널 출력은 컨트롤에 닿지 않는다. 막히면 막힌 지점만 먼저
