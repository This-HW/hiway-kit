# 브리프 T3 — skills-evals (W-044)

- **부모**: plan-control 컨트롤 세션 (Orca Run — 디스패치 spec 에 Run/Task id 가 실려 있다)
- **역할**: 스킬 14 파일 + eval 러너(judge 구조화 출력·effort 전달) + CLAUDE.md 1곳의 감사 hunk 적용·검증
- **워크트리**: Orca 가 만든 new-child 워크트리 (경로는 디스패치 통보). **자기 브랜치에만 커밋**
- **기준 커밋**: 디스패치 spec 의 해시. 착수 시 `git rev-parse HEAD` 와 대조 — 다르면 착수하지 말고 에스컬레이션
- 먼저 `child-session` 스킬을 로드하고 마커를 쓴다

## ① 전제 — 구현 전에 검증한다

1. `docs/specs/2026-09-25-prompt-audit/prompt-audit.patch` 는 HEAD `9e2dc39` 기준이며
   `git apply --check --include='plugins/common/skills/*' --include='evals/*' --include='CLAUDE.md' <patch>` 통과 `[confirmed 2026-09-25]`
2. 이 트랙의 hunk: 스킬 14 파일 + `evals/run.py` + `evals/tests/test_runner.py` + `CLAUDE.md` 1곳 `[confirmed]`.
   내용은 `prompt-audit-report.md` 의 H1·H2·H6~H9·M13~M18·M24~M26 다
3. `plugins/common/agents/` 에 `diagnose` 에이전트는 없다(`find` 0건) `[confirmed]` — `skills/debug/SKILL.md:77` 이 dispatch 한다
4. `skills/using-hiway-kit/SKILL.md` 에 "비신뢰 텍스트 취급" 절은 없다(grep 0) `[confirmed]` —
   `skills/web-research/SKILL.md:76` 이 그 절을 SSOT 로 가리킨다. 규칙의 실제 위치는 `rules/untrusted-text.md`
5. `review` 스킬(`:284-292`)이 요구하는 A~F 형식은 `agents/dev/review-code.md` 의 출력 계약(`## 판정`/`## 완료:`)과
   다르고, `auto-dev/SKILL.md:283-284` 는 어느 형식에도 없는 `decision`/`critical_count` 필드로 게이트한다 `[confirmed]`
6. `claude -p --output-format json --json-schema <schema>` 의 결과 JSON 에 `structured_output` 필드가 있다
   `[confirmed — 2026-09-24 haiku 1회 실측, CLI 2.1.280]`. `claude --help` 에 `--effort <level>` 존재 `[confirmed]`
7. scratch 복사본에서 패치 적용 후 `pytest evals/tests` 122 passed, ruff green `[confirmed, scratch — 실 레포 아님]`.
   패치가 `test_runner.py` 의 judge 픽스처를 `structured_output` JSON 으로 바꾼다 `[confirmed]`
8. `evals/scenarios/**/expect.json` 에 `judge.enabled: true` 인 시나리오는 없다(grep 0) `[confirmed]` — judge 경로는 휴면

## ② 범위

**IN**
1. `git apply --include='plugins/common/skills/*' --include='evals/*' --include='CLAUDE.md' docs/specs/2026-09-25-prompt-audit/prompt-audit.patch`
2. `python3 -m pytest -q evals/tests` — rc 0
3. `ruff check .` — rc 0
4. `./scripts/run-evals.sh --validate` — rc 0 · `./scripts/run-evals.sh --dry-run` 으로 `--effort` 가 커맨드에 실리는지 확인(출력 인용)
5. `python3 scripts/check_doc_counts.py` — rc 0 (CLAUDE.md Key Skills 표는 패치가 건드리지 않는다)
6. `./scripts/verify-done.sh > /tmp/vd-t3.out 2>&1; echo $?` — rc 와 red 섹션 목록 보고
7. 잔존 grep 보고(수정은 소유 파일만): `git grep -n -e 'subagent_type: diagnose' -e './scripts/checklist.sh' -e 'delegation signal' -e '전체 평가: \[A/B/C/D/F\]' -e '33개 에이전트' -e '33종' -- plugins/common/skills evals CLAUDE.md`
8. 커밋(자기 브랜치): 스킬 1커밋, evals+CLAUDE.md 1커밋

**OUT**: `plugins/common/agents/**`, `plugins/common/rules/**`, `plugins/common/hooks/**`, `AGENTS.md`/`GEMINI.md`,
`docs/works/**`, 버전·CHANGELOG·`build-targets.py`, eval 행동 실행(API), Low/flag 항목
(`Task tool 사용:` 표기·per-call `model:` 핀 정리, brainstorming 체크리스트 Task 규율)

**완료 기준**: IN 2·3·4·5 rc 0, 커밋 2개, 보고 도착

## ③ 금지 — 명령 수준

- `git push` 금지. `main`·`This-HW/plan-control` 체크아웃·커밋 금지
- bare `git stash` / `git stash pop` / `git reset --hard` / `git clean -fd` 금지
- `git apply` 를 `--include` 없이 실행 금지
- `scripts/run-evals.sh` 는 `--validate` / `--dry-run` 만. 인자 없이·`--agent`·`--compare`·`--baseline` 실행 금지(API 비용).
  `claude -p` 직접 호출도 금지 — judge 필드명은 전제 6 으로 이미 실측됐다
- 패치 밖의 "추가 정리" 금지. hunk 가 틀렸다고 판단되면 **적용하지 않고** 근거(파일:줄) 인용해 보고.
  특히 `debug` 의 `diagnose → fix-bugs(진단 전용)` 치환이 부적절하다고 보면 대안을 **제안만** 한다
- 소유 밖 파일 편집 금지. `verify-done.sh` 의 소유 밖 red(§11 등) 수정 금지 — 보고만
- 게이트 rc 를 파이프에 물리지 말 것(`cmd > out 2>&1; rc=$?`)

## ④ 보고

- 첫 줄: `[T3 skills-evals] 완료 — <hunk N개 적용, 파일 M개>, 커밋 <sha>, 테스트 <n passed>`
  (`pytest evals/tests` 의 passed 수; 부분이면 `부분 —`)
- 본문: 명령과 rc(`--dry-run` 의 `--effort` 인용 포함) · 적용하지 않은 hunk 와 근거 · IN 7 grep 결과 ·
  **병합 측 후속 조치**(없으면 "없음") · 사실 등급 표기
- **전달 수단**: Orca 디스패치 preamble 이 지정한 경로(`worker_done`)로 컨트롤 Run 에 보낸다.
  터미널 출력은 컨트롤에 닿지 않는다. 막히면 막힌 지점만 먼저 보낸다 — 침묵이 실패다
