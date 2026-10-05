---
status: historical
as_of: 2026-09-28
---

# 브리프 T1 — hooks-gates (W-046)

- **부모**: plan-control 컨트롤 세션 (Orca Run — 디스패치 spec 에 Run/Task id)
- **역할**: session-start 의 활성 작업 주입을 계획 파일 규약으로 교체 + checklist·게이트·레포 도구에서 Work 제거
- **워크트리**: Orca new-child 워크트리. **자기 브랜치에만 커밋**
- **기준 커밋**: 디스패치 spec 의 해시 — 착수 시 `git rev-parse HEAD` 대조, 다르면 착수하지 말고 에스컬레이션
- 먼저 `child-session` 스킬 로드. 스펙 전문: `docs/specs/2026-09-28-plans-replace-works/README.md` — **§2.1 계약은 변경 금지**

## ① 전제 — 구현 전에 검증한다

1. `hooks/session-start.py` `main()` 이 `docs/works/active/*` 를 스캔해 `=== ACTIVE WORK ===` 블록을 만들고
   (`summarize_work`, `_MAX_ACTIVE_WORKS=10`, `progress.md` Task Map 파싱), 활성 Work 가 있으면 `task-resume`
   조건부 룰 신호를 켠다 `[소스 기준 — L149-196, L553-590 부근]`
2. `hooks/checklist.py` 는 `<work_dir>/checklist.json` 을 다루며 레이아웃 비의존(`_repo_root` 가 git 으로 루트를 구함).
   docstring·usage 에 `docs/works/<stage>/<W>` 가 적혀 있다 `[소스 기준]`
3. `scripts/verify-done.sh` §8 이 `docs/works/active/*/checklist.json` 을 순회한다 `[소스 기준 L354]`
4. `scripts/work.sh` 와 `scripts/tests/test_work_sh.py` 는 레포 전용이며 배포되지 않는다 `[confirmed]`
5. `scripts/check_registry_describe.py:422`, `scripts/feedback.sh:5` 가 docs/works·work.sh 를 언급 `[confirmed]`
6. `feedback_ledger.py` 의 `legacy_ledger_path`(`docs/works/feedback/ledger.md`)는 **구 원장 이관 원본**이다 — 건드리지 않는다

## ② 범위

**IN**
1. session-start: `docs/plans/*/plan.md` 중 `status != done` 을 스캔해 `=== ACTIVE PLANS ===` 블록 주입.
   항목 = `[<디렉토리명>] <title> — <status>, checklist <pass>/<total>`(checklist 없으면 생략). 상한 10 + 초과 한 줄.
   frontmatter 는 기존 파서 재사용, `title`/`status` 가 없거나 파싱 불가면 그 항목만 건너뛴다(fail-open).
   **비신뢰 텍스트 규율**: title 은 기존 subject 정제 함수로 정제하고, 블록 앞에 기존과 같은 비신뢰 프레이밍을 둔다.
   활성 계획이 있으면 기존 `task-resume` 신호를 켠다(신호 키·룰 파일명 변경 금지 — T3 가 그 룰 본문을 고친다).
   블록 끝 안내문: `재개 시 plan.md 원문과 checklist 를 다시 읽는다 (규칙: task-resume)`.
2. 구버전 안내: `docs/works/active/` 에 디렉토리가 하나라도 있으면 컨텍스트에 한 줄 —
   `구버전 docs/works/active 가 있다 — hiway-kit 4.0 부터 docs/plans/<날짜>-<slug>/plan.md 를 쓴다(CHANGELOG 4.0.0).`
   구 원장은 읽지 않는다. `summarize_work`·`parse_task_map` 등 Work 전용 코드는 제거.
3. checklist.py: docstring·usage·주석의 `<work_dir>`/`docs/works/...` 를 `<plan_dir>`/`docs/plans/<날짜>-<slug>` 로.
   동작 변경 없음.
4. verify-done §8: `docs/plans/*/checklist.json` 중 **같은 디렉토리 plan.md 의 status 가 done 이 아닌 것**만 검사
   (done 계획의 checklist 는 과거 기록). 헤더 문구에서 "active Work, W-013" → "활성 계획". §8 번호 유지.
5. `scripts/work.sh`·`scripts/tests/test_work_sh.py` 삭제. `scripts/checklist.sh` usage 의 `<work_dir>` → `<plan_dir>`.
   check_registry_describe·feedback.sh 의 문구에서 work.sh/docs/works 언급 제거(동작 무변경).
6. 테스트: session-start — 활성 계획 주입, done 제외, 상한 초과, frontmatter 손상 건너뜀, 구버전 안내 발화/비발화,
   title 인젝션 문자열 정제. checklist — 경로 문구 변경에 따른 기존 테스트 정합. **되돌려-FAIL**: 스캔 대상을
   구 경로로 되돌리면 새 테스트가 red 인지 확인해 보고에 인용.
7. 게이트: `python3 -m pytest -q plugins/common/hooks/tests scripts/tests` rc 0 · `ruff check .` rc 0 ·
   `./scripts/lint-shell.sh` rc 0 · `./scripts/verify-done.sh > /tmp/vd-t1.out 2>&1` rc 와 red 목록
   (§11 AGENTS/GEMINI·§7 CHECKSUMS 는 다른 트랙/컨트롤 몫이라 red 예상 — 보고만)
8. 커밋 2개(자기 브랜치): hooks+tests / scripts

**OUT**: 스킬·룰·README·CLAUDE.md·AGENTS/GEMINI·CHANGELOG·버전, feedback_ledger 의 구 원장 이관 로직

**완료 기준**: IN 7 의 pytest·ruff·lint-shell rc 0, 되돌려-FAIL 인용, 커밋 2개, 보고 도착

## ③ 금지 — 명령 수준

- `git push` 금지. `main`·`This-HW/plan-control` 체크아웃·커밋 금지
- bare `git stash`/`git stash pop`/`git reset --hard`/`git clean -fd` 금지
- `scripts/run-evals.sh` 는 `--validate`/`--dry-run` 만. `claude -p` 호출 금지
- §2.1 계약(경로·frontmatter 키·status 값) 변경 금지 — 맞지 않는다고 판단되면 구현하지 말고 근거와 함께 보고
- 소유 밖 파일 편집 금지. 소유 밖 red 는 보고만
- 게이트 rc 를 파이프에 물리지 말 것

## ④ 보고

- 첫 줄: `[T1 hooks-gates] 완료 — <테스트 N개 추가, 파일 M개>, 커밋 <sha>, 테스트 <n passed>`(부분이면 `부분 —`)
- 본문: 명령과 rc · 되돌려-FAIL 인용 · 좁힌 곳과 근거 · **병합 측 후속 조치**(없으면 "없음") · 사실 등급
- **전달 수단**: Orca 디스패치 preamble 이 지정한 경로(`worker_done`). 터미널 출력은 컨트롤에 닿지 않는다.
  막히면 막힌 지점만 먼저 보낸다
