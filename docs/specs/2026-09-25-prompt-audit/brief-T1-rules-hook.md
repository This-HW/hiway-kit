# 브리프 T1 — rules-hook (W-044)

- **부모**: plan-control 컨트롤 세션 (Orca Run — 디스패치 spec 에 Run/Task id 가 실려 있다)
- **역할**: 주입 룰 9종 + SessionStart 훅 indexLine 렌더 + 룰 생성물(미러·CHECKSUMS) 정합
- **워크트리**: Orca 가 만든 new-child 워크트리 (경로는 디스패치 통보). **자기 브랜치에만 커밋**
- **기준 커밋**: 디스패치 spec 의 해시. 착수 시 `git rev-parse HEAD` 와 대조 — 다르면 착수하지 말고 에스컬레이션
- 먼저 `child-session` 스킬을 로드하고 마커를 쓴다(이 워크트리에는 hiway-kit 플러그인이 설치돼 있다)

## ① 전제 — 구현 전에 검증한다

1. `docs/specs/2026-09-25-prompt-audit/prompt-audit.patch` 는 HEAD `9e2dc39` 기준이며, 컨트롤 트리에서
   `git apply --check --include='plugins/common/rules/*' --include='plugins/common/hooks/*' <patch>` 통과 `[confirmed 2026-09-25]`
2. 이 트랙의 hunk: 룰 9 파일(`code-quality, ssot, planning-protocol, definition-of-done, loop-engineering,
   feedback-loop, parallel-worktree, mcp-usage, task-resume`) + `hooks/session-start.py` 1곳 +
   `hooks/tests/test_session_start.py` 2곳 `[confirmed]`
3. `rules/agent-delegation-chain.md`·`rules/agent-system.md` 의 `indexLine` 은 cwd 상대 경로 `rules/…` 로
   그대로 주입된다(`session-start.py:297`) `[confirmed]` — 소비자 프로젝트에는 그 경로가 없다
4. `docs/architecture/rules/code-quality.md` 는 "≤20줄 / ≤3개 / ≤2단계" 표를 **설명**한다 `[confirmed]`.
   `ssot.md`·`planning-protocol.md`·`mcp-usage.md`·`task-resume.md` 미러도 존재 `[confirmed]`.
   미러는 룰을 설명·참조만 하고 재정의하지 않는다(`docs/conventions/rules-mirror.md`)
5. `AGENTS.md`·`GEMINI.md` 에 룰 본문이 export 돼 있다(`under 20 lines` 각 1곳) `[confirmed]` —
   **컨트롤 소유**, 병합 후 `export-harness.sh` 로 재생성한다. 워커의 `verify-done.sh §11` red 는 예상됨
6. scratch 복사본에서 패치 적용 후 `pytest plugins/common/hooks/tests/test_session_start.py` 46 passed,
   ruff green `[confirmed, scratch — 실 레포 아님]`. 상시 주입 core 룰 합계 −351 B `[confirmed]`

## ② 범위

**IN**
1. `git apply --include='plugins/common/rules/*' --include='plugins/common/hooks/*' docs/specs/2026-09-25-prompt-audit/prompt-audit.patch`
2. `python3 -m pytest -q plugins/common/hooks/tests` (전체) — rc 0
3. `python3 scripts/check_injection_budget.py` — rc 0
4. 미러 5종(`docs/architecture/rules/{code-quality,ssot,planning-protocol,mcp-usage,task-resume}.md`)을
   새 룰 문구에 맞춰 갱신: 사라진 수치 표·중앙 에러 핸들러 강제·Sequential Thinking·regression guard
   서술을 제거하거나 "왜 수치를 두지 않는가"로 바꾼다. **재정의 금지 — 설명과 참조만.**
   그 뒤 `scripts/sync-rule-mirror.sh --regenerate`
5. CHECKSUMS 재생성: `(cd plugins/common/rules && shasum -a 256 *.md | grep -v CHECKSUMS > CHECKSUMS.sha256)`
6. `ruff check .` — rc 0
7. `./scripts/verify-done.sh > /tmp/vd-t1.out 2>&1; echo $?` — rc 와 red 섹션 목록을 보고.
   §11(AGENTS/GEMINI 드리프트) red 는 예상된 것 — **고치지 말고 보고**
8. 잔존 grep 보고(수정은 소유 파일만): `git grep -n -e 'under 20 lines' -e 'Sequential Thinking' -e 'Spec [0-9] / W-0' -- ':!docs/works' ':!docs/CHANGELOG-archive.md' ':!CHANGELOG.md'`
9. 커밋(자기 브랜치): 룰+훅+테스트 1커밋, 미러+CHECKSUMS+MIRROR 1커밋

**OUT**: `AGENTS.md`/`GEMINI.md`, 버전·CHANGELOG·`build-targets.py`, `docs/works/**`, 다른 트랙 파일
(`plugins/common/agents/**`, `plugins/common/skills/**`, `evals/**`, `CLAUDE.md`), Low/flag 항목

**완료 기준**: IN 2·3·6 rc 0, `sync-rule-mirror.sh` 재생성 후 verify-done §7 green, 커밋 2개, 보고 도착

## ③ 금지 — 명령 수준

- `git push` 금지. `main`·`This-HW/plan-control` 체크아웃·커밋 금지
- bare `git stash` / `git stash pop` / `git reset --hard` / `git clean -fd` 금지
- `git apply` 를 `--include` 없이(전체 패치) 실행 금지
- `scripts/run-evals.sh` 실행 금지(이 트랙 무관 + API 비용)
- `scripts/export-harness.sh` 의 `--check` 외 실행 금지(재생성은 컨트롤)
- 패치 hunk 의 문구를 "개선"하지 말 것. 틀렸다고 판단되면 그 hunk 를 **적용하지 않고** 근거(파일:줄)를 인용해 보고
- 소유 밖 파일 편집 금지. `verify-done.sh` 의 소유 밖 red 수정 금지 — 보고만
- 게이트 rc 를 파이프에 물리지 말 것(`cmd > out 2>&1; rc=$?`)

## ④ 보고

- 첫 줄: `[T1 rules-hook] 완료 — <hunk N개 적용, 미러 M개 갱신>, 커밋 <sha>, 테스트 <n passed>`
  (부분이면 `완료` 대신 `부분 —` 로 시작하고 남은 것을 적는다)
- 본문: 실행한 명령과 rc(verify-done red 섹션 목록 포함) · 적용하지 않은 hunk 와 근거 · 잔존 grep 결과 ·
  **병합 측 후속 조치**(없으면 "없음") · 사실마다 `[confirmed]`/`[소스 기준]`/`[미확인]`
- **전달 수단**: Orca 디스패치 preamble 이 지정한 경로(`worker_done`)로 컨트롤 Run 에 보낸다.
  **자기 터미널에 출력하는 것은 컨트롤에 닿지 않는다.** 막히면 막힌 지점만 먼저 보낸다 — 침묵이 실패다
