# 브리프 T2 — agents (W-044)

- **부모**: plan-control 컨트롤 세션 (Orca Run — 디스패치 spec 에 Run/Task id 가 실려 있다)
- **역할**: 에이전트 정의 26 파일의 감사 hunk 적용·검증 (`plugins/common/agents/**` 만)
- **워크트리**: Orca 가 만든 new-child 워크트리 (경로는 디스패치 통보). **자기 브랜치에만 커밋**
- **기준 커밋**: 디스패치 spec 의 해시. 착수 시 `git rev-parse HEAD` 와 대조 — 다르면 착수하지 말고 에스컬레이션
- 먼저 `child-session` 스킬을 로드하고 마커를 쓴다

## ① 전제 — 구현 전에 검증한다

1. `docs/specs/2026-09-25-prompt-audit/prompt-audit.patch` 는 HEAD `9e2dc39` 기준이며
   `git apply --check --include='plugins/common/agents/*' <patch>` 통과 `[confirmed 2026-09-25]`
2. 이 트랙의 hunk 는 `plugins/common/agents/**` 26 파일, 순삭제 약 1,300줄 `[confirmed]`.
   내용은 `prompt-audit-report.md` 의 H4·H5·H14~H17·M1~M12 다
3. `plugins/common/agents/**/references/` 디렉토리는 존재하지 않는다(`find` 0건) `[confirmed]` —
   `review-code:136`, `implement-code:36,64`, `plan-implementation:66-67` 이 그 경로를 가리킨다
4. `implement-code`·`fix-bugs`·`verify-code`·`verify-integration`·`write-tests` 는 `disallowedTools: [Task]`
   `[소스 기준]` — 위임 명령("반드시 verify-code로 위임하세요!")을 스스로 수행할 수 없다
5. `verify-code.md` frontmatter `maxTurns: 10` 인데 본문은 "15 tool calls 내에" `[confirmed]`
6. 에이전트는 디렉토리에서 자동 발견된다 — 매니페스트 등록 없음(`CLAUDE.md` Adding a New Agent) `[소스 기준]`.
   frontmatter 필수 필드(`name, description, model, maxTurns`)는 패치가 건드리지 않는다 `[confirmed]`

## ② 범위

**IN**
1. `git apply --include='plugins/common/agents/*' docs/specs/2026-09-25-prompt-audit/prompt-audit.patch`
2. 적용 결과 눈으로 확인 — 특히 블록 삭제 hunk(implement-code, review-code, git-workflow, write-api-tests,
   implement-api, optimize-logic, design-services, define-metrics, security-scan, write-tests,
   plan-implementation, define-business-logic, enforce-structure, facilitator, generate-boilerplate,
   analyze-tech-debt, manage-api-versions)가 **헤딩 경계에서 끊겼고 고아 구분선(`---` 연속)이나
   깨진 코드펜스가 없는지**. 있으면 그 파일만 최소 수정
3. `./scripts/run-evals.sh --validate` — rc 0 (에이전트 로드·시나리오 스키마)
4. `python3 scripts/check_doc_counts.py` — rc 0 (에이전트 수 32 유지)
5. `ruff check .` — rc 0 (변경 없음 확인용)
6. `./scripts/verify-done.sh > /tmp/vd-t2.out 2>&1; echo $?` — rc 와 red 섹션 목록 보고
7. 잔존 grep 보고: `grep -rn 'references/' plugins/common/agents` (남은 hit 는 전부 나열) ·
   `grep -rln '위임하세요\|반드시 verify-code' plugins/common/agents` · `grep -rn 'diagnose' plugins/common/agents`
8. maxTurns ≤ 10 에이전트 중 `## 출력 계약` 절이 **없는** 파일 목록(패치 적용 후) 보고 — 수정은 하지 않는다
9. 커밋(자기 브랜치): 1커밋

**OUT**: `plugins/common/agents/**` 밖 전부(skills, rules, hooks, evals, CLAUDE.md, AGENTS.md, docs/works),
버전·CHANGELOG, eval 실행(API), Low/flag 항목(review-code:28-33 문구, 로스터 통합, `Task tool 사용 금지` 불릿)

**완료 기준**: IN 3·4·5 rc 0, 커밋 1개, 보고 도착

## ③ 금지 — 명령 수준

- `git push` 금지. `main`·`This-HW/plan-control` 체크아웃·커밋 금지
- bare `git stash` / `git stash pop` / `git reset --hard` / `git clean -fd` 금지
- `git apply` 를 `--include` 없이 실행 금지
- `scripts/run-evals.sh` 는 `--validate` / `--dry-run` 만. 인자 없이·`--agent`·`--compare`·`--baseline` 실행 금지(API 비용)
- 패치 밖의 "추가 정리" 금지 — 삭제된 블록 옆의 다른 일반 지식 절이 눈에 띄어도 건드리지 않는다.
  hunk 가 틀렸다고 판단되면 **적용하지 않고** 근거(파일:줄) 인용해 보고
- 소유 밖 파일 편집 금지. `verify-done.sh` 의 소유 밖 red(§11 등) 수정 금지 — 보고만
- 게이트 rc 를 파이프에 물리지 말 것(`cmd > out 2>&1; rc=$?`)

## ④ 보고

- 첫 줄: `[T2 agents] 완료 — <hunk N개 적용, 파일 M개, 순삭제 L줄>, 커밋 <sha>, 테스트 <n passed>`
  (`--validate` 통과 시나리오 수를 테스트 수로 쓴다; 부분이면 `부분 —`)
- 본문: 명령과 rc · 최소 수정한 파일과 이유 · 적용하지 않은 hunk 와 근거 · IN 7·8 grep 결과 ·
  **병합 측 후속 조치**(없으면 "없음") · 사실 등급 표기
- **전달 수단**: Orca 디스패치 preamble 이 지정한 경로(`worker_done`)로 컨트롤 Run 에 보낸다.
  터미널 출력은 컨트롤에 닿지 않는다. 막히면 막힌 지점만 먼저 보낸다 — 침묵이 실패다
