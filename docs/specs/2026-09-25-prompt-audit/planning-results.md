# Planning 결과: prompt-audit 적용 — 정의 파일 cruft 제거

> Work ID: W-044
> Last Updated: 2026-09-25

## 규모 판단

**Medium** — 49 파일 +154/−1,943 이지만 결정은 이미 끝났다(`prompt-audit-report.md`).
남은 것은 (a) 제안 diff 를 트랙별로 적용·검증하고 (b) 룰 변경에 따라오는 생성물
(미러·CHECKSUMS·harness export)을 맞추고 (c) 병합 후 eval 회귀를 재는 일이다.

## 요구사항 명확화

- 입력: `prompt-audit-report.md`(감사 리포트, High 17 / Medium 26) + `prompt-audit.patch`
  (HEAD `9e2dc39` 기준, `git apply --check` 통과 `[confirmed 2026-09-25]`).
- 적용 단위는 **리포트의 finding = patch 의 hunk** 다. 워커는 hunk 를 적용하고 검증한다 —
  설계를 바꾸지 않는다. hunk 가 틀렸다고 판단되면 적용하지 않고 근거를 인용해 보고한다
  (`rules/delegation-contract.md` "좁히되 드러낸다").
- Low/flag 항목은 이 Work 의 범위 밖이다.

## 구현 계획 — 파일 소유권이 겹치지 않는 3 트랙

| 트랙 | 모델 | 소유 파일 | 트랙 고유 후속 |
| --- | --- | --- | --- |
| T1 rules-hook | opus | `plugins/common/rules/*.md`, `rules/CHECKSUMS.sha256`, `hooks/session-start.py`, `hooks/tests/test_session_start.py`, `docs/architecture/rules/*.md`, `docs/architecture/rules/MIRROR.sha256` | 미러 해설본을 새 룰 문구에 맞춰 갱신 → `sync-rule-mirror.sh --regenerate`, CHECKSUMS 재생성, 주입 예산 확인 |
| T2 agents | sonnet | `plugins/common/agents/**/*.md` | `run-evals.sh --validate`, 잔존 `references/` 포인터 grep |
| T3 skills-evals | opus | `plugins/common/skills/**/*.md`, `evals/run.py`, `evals/tests/test_runner.py`, `CLAUDE.md` | `pytest evals/tests`, 잔존 화석 grep |

**컨트롤 소유(워커 편집 금지)**: `AGENTS.md`·`GEMINI.md`(룰 export 본 — 병합 후
`scripts/export-harness.sh` 로 재생성, §11), `plugins/common/.claude-plugin/plugin.json` 버전,
`CHANGELOG.md`, 타겟 매니페스트(`build-targets.py --write`), `docs/works/**`, eval 기준선.

(트랙 문서는 `docs/specs/2026-09-25-prompt-audit/` 에 트래킹된다 — docs/works 는 gitignore) 브리프: `brief-T1-rules-hook.md` · `brief-T2-agents.md` · `brief-T3-skills-evals.md`.

## 완료 조건 (실행 가능한 명령)

1. 세 트랙 병합 후 통합 브랜치에서 `./scripts/verify-done.sh > /tmp/vd.out 2>&1; echo $?` → `0`
2. `./scripts/run-evals.sh --compare evals/baseline/2026-09-20.json` → exit 0 (후퇴 없음)
   — 에이전트 정의 변경은 in-session 검증 불가(캐시), 이것이 유일한 행동 검증이다
3. 버전 minor 범프 + CHANGELOG + `python3 scripts/build-targets.py --write` + `scripts/export-harness.sh`
