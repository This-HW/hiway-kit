---
status: historical
as_of: 2026-10-05
---

# W1 docs — 완료 보고

- 브랜치 `This-HW/remed-docs` · 기준 `ea87de2fcca573b4061760d6544a0dbdce6e6a40`(ancestor 확인) · 커밋 10개(`fcbaa4d`..이 파일 커밋)
- 소유 밖 파일 수정 0건(`git diff --name-only ea87de2..HEAD` 를 금지 경로로 grep → 0). 버전·CHANGELOG.md 불변. CHANGELOG 조각: `changelog-W1.md`

## 반영한 발견 ID → 파일

| ID | 파일 |
| --- | --- |
| B-P0-1 | `README.md` Full Mode 절 · `CLAUDE.md` Installation |
| B-P0-5, B-P1-6, D-2 | `docs/architecture/phase-gate-pattern.md` (머리 해설 선언·«Stop 훅은 Phase Gate 가 아니다»·출구 표) |
| B-P0-6 | `docs/pipeline-reinforcement-plan-v2.md` 삭제, 역사 스펙 3곳 링크 → `delegation-signal-retirement.md` |
| B-P1-1, D-4, D-5, B-P2-12 | `CLAUDE.md` Release Checklist(포인터) · `docs/conventions/release-process.md`(정본화) |
| B-P1-2 | `CLAUDE.md` «Editing an agent/skill» 캐시 경로 · `release-process.md` 머리 |
| B-P1-3, B-P1-4, C-F6 | `docs/marketplace-submission.md` 요약표·머리·Install Commands·개명 절·listing 키 문단 |
| B-P1-5 | `docs/codex-submission-checklist.md` 머리·Tracking·§14·역사 절 |
| B-P1-7 | `README.md` Codex 표 Status 행(요약표 포인터) |
| B-P1-8 | `README.md` 머리 문단·Codex 출력 한도 문단(현재 사실만) |
| B-P1-9, A-P1-3 | `README.md` Other Harnesses 두 표 · `docs/native-absorption.md` 다중 하네스 행 |
| B-P1-13, B-P2-8 | `CLAUDE.md` frontmatter 템플릿·오케스트레이션 표 |
| B-P1-14, B-P3-3 | `CLAUDE.md` Phase Gate·Key Skills · `README.md` 핵심 개념 표 |
| B-P1-15, B-P1-16 | `CLAUDE.md` CI/CD·드리프트 게이트 절 · `docs/conventions/no-gate-integration.md` |
| B-P1-17 | `docs/conventions/path-containment.md` |
| B-P1-18 | `docs/conventions/README.md` |
| B-P1-29, D-6 | `README.md` Typical Workflows·Project Structure·Contributing · `plugins/common/README.md` |
| B-P1-30 | `docs/control-loop-transport.md` |
| B-P1-31, B-P3-6, A-P2-1 | `docs/research/2026-09-11-cross-harness-norm-integration.md` · `2026-07-long-running-loop-agents.md` · `2026-09-15-dryforge-evaluation.md` |
| B-P2-1, B-P2-2, C-F1, C-F2, C-F7, C-F8, D5 | `docs/native-absorption.md` |
| B-P2-4 | `docs/conventions/reference-vs-judgment.md` |
| B-P2-5 | `CLAUDE.md` Delegation Signal · `docs/architecture/delegation-signal-retirement.md` |
| B-P2-6 | `docs/conventions/warning-signal.md` |
| B-P2-7 | `docs/conventions/rules-mirror.md` |
| B-P2-11 | `packaging/README.md` · `plugins/common/README.md` |
| B-P2-13 | `docs/specs/2026-09-30-boundary-enforcement/spec.md` 완료 조건 주석 · `research/2026-07-harness-loop-engineering.md` · `research/2026-09-08-plugin-directory-status.md` · frontmatter 통일 |
| B-P3-2 | `README.md` Delegation Signal 포인터 |
| B-P3-4 | `CLAUDE.md` · `delegation-signal-retirement.md` · `native-absorption.md` · `marketplace-submission.md` · `packaging/README.md` · `docs/conventions/*` · specs 색인 제목 |
| B-P3-5 | `docs/conventions/measurement-traps.md` |
| C-F4, C-F10 | `CLAUDE.md` 오케스트레이션 인용문·Sub-agent Rules |
| D-1, D-3 | `CLAUDE.md` Key Skills·Adding a New Agent 5번 · `plugins/common/README.md` |
| D-7 | `CLAUDE.md` 첫 줄 · `README.md` 머리 |
| D-9 | `plugins/common/README.md` Hooks 절 |
| A-P0-2 | `README.md` Automatic blocking 행 · `docs/codex-submission-checklist.md` What's NOT included |
| A-P1-1 | `README.md` Codex 경로 비교표 · `docs/codex-submission-checklist.md` |
| A-P1-7, A #9 | `README.md` Gemini CLI 절 · `~/.agents/skills` 절 |
| D0-2 | `docs/**/*.md` 91개 frontmatter(+ `research/README.md`·`specs/README.md` 신설) |
| D2 | `CLAUDE.md` + @import 42,971B → 38,603B |
| D3 | `docs/marketplace-submission.md` 상단 요약표 |

## 반영하지 못한 ID와 이유

| ID | 이유 |
| --- | --- |
| B-P0-4, B-P1-19, B-P1-20, B-P1-21 | 브리프 지정 W2 소유(`docs/architecture/rules/`) |
| B-P2-3 | `CHANGELOG.md:3` 의 구 이름 — 브리프가 CHANGELOG.md 수정 금지. 제외 범위 축소(`name-targets.json`)는 W4 |
| B-P2-9, B-P2-10 | 스킬 파일(W3 소유, 스펙 D11 이 W3 에 배정) |
| B-P2-11 일부 | `plugins/common/hooks/examples/README.md:90` "CLAUDE.md 최상위 안전 규율과 동일"(stash 규율은 CLAUDE.md 에 없음) — `plugins/common/hooks/**` 금지 |
| B-P1-17 일부 | `scripts/build-targets.py:47` 주석의 `_resolve_target` — W2 소유(스펙 완료 조건 grep 에 걸린다) |
| B-P3-5 일부 | 룰 frontmatter `activates:` 이중 서술 — `rules/**` 금지 |
| D0-2 일부 | `docs/architecture/rules/*.md` 5개 frontmatter — W2 소유. 완료 조건 frontmatter 검사가 지금 5 |

## 명령별 rc (HEAD 기준)

| 명령 | rc | 비고 |
| --- | --- | --- |
| `python3 scripts/check_injection_budget.py` | 0 | 프로젝트 지침 38,603B ≤ 43,008B |
| `python3 scripts/check_doc_counts.py` | 0 | |
| `test ! -f docs/pipeline-reinforcement-plan-v2.md` | 0 | |
| 완료 조건 `git grep` 금지 패턴 | 히트 있음 | 전부 W1 밖: `AGENTS.md`·`GEMINI.md`(컨트롤 재생성), `export_harness.py:453`·`build-targets.py:47`·미러 `mcp-usage.md:50`(W2), `scripts/verify-done.sh:290` 주석의 `db-tunnel.sh`(W4). W1 소유 파일 0건 |
| 완료 조건 frontmatter 검사 | 5 | 전부 `docs/architecture/rules/`(W2). 기준 커밋에서는 91 |
| `scripts/verify-done.sh` | 1 | 32 pass / 1 fail — §11 진입점 conventions 블록 드리프트(`path-containment.md`·`no-gate-integration.md` 를 고쳤으므로 예정된 red, 재생성은 컨트롤) |
| GFM 표 열 수(현행 문서 전부) | 0 위반 | 자체 스크립트 |

되돌려-FAIL: 기준 커밋 `ea87de2` 에서 같은 검사는 frontmatter 누락 91, W1 범위 금지 패턴 히트 2(`path-containment.md:14,20`)였다.

## 미결 (컨트롤·다른 워커에게)

1. **frontmatter 가 `AGENTS.md`/`GEMINI.md` 에 인라인된다** — `export_harness.py` `build_conventions_block` 이 `path-containment.md`·`no-gate-integration.md` 본문을 그대로 넣으므로 재생성하면 `---`/`status:`/`as_of:` 가 들어가 setext 헤딩으로 렌더된다. W2 가 인라인 시 frontmatter 를 벗기거나 컨트롤이 재생성 후 확인해야 한다(착수 시 통보함).
2. W4 의 `check_doc_status.py` 가 구 이름을 금지 토큰으로 잡으면 `docs/marketplace-submission.md`(current)가 red 다 — 전임 킷 등재 기록을 실측 근거로 인용하는 문서라 기존 `oldNameScanExclude` 와 같은 예외가 필요하다.
3. `plugins/common/rules/VERSION`(1.4.0)을 올리는 기준이 정해져 있지 않다 — `release-process.md` 에 미결로 적었다.
4. README 의 Codex 차단 문장은 `packaging/targets.json`(W2 갱신 예정)을 인용한다 — W2 가 그 기록을 넣지 않으면 인용이 허공을 가리킨다.

## SSOT 지도(B (b)) 대비 — 정본 1개 + 포인터만 남았나

| 주제 | 정본 | W1 범위의 포인터 측 상태 | 판정 |
| --- | --- | --- | --- |
| 에이전트 모델·isolation·maxTurns | 각 `agents/*.md` frontmatter | `CLAUDE.md` 템플릿은 "frontmatter 가 소유", README 모델 표는 예시만 | ✅ |
| 크기 기준 Small/Medium/Large | `elicitation.md §6` | `CLAUDE.md`·`phase-gate-pattern.md` 는 §6 을 가리킴. 스킬·룰·미러 측은 W2·W3 | ✅(W1 범위) |
| Phase Gate 출구 조건 | `rules/agent-system.md` | `phase-gate-pattern.md` 해설 선언 + 정본 우선, `CLAUDE.md` 는 그 룰을 가리킴 | ✅ |
| 릴리스 절차 | `docs/conventions/release-process.md` | `CLAUDE.md` 포인터 한 줄 + CRITICAL 문장, README 체크리스트는 링크 | ✅ |
| 설치·마켓 경로·캐시 구조 | `README.md` 설치 절 | `CLAUDE.md` Installation 은 명령 블록이 남아 있다(세션 지침 편의) · `plugins/common/README.md` 는 배포 README 라 명령을 싣는다 | ⚠ 명령 블록 3곳(README·CLAUDE·plugins/common/README) — 배포물 README 는 레포 README 를 볼 수 없는 소비자용이라 의도적 |
| 배포 채널별 상태 | `marketplace-submission.md` 요약표 | `CLAUDE.md`·README·codex 체크리스트는 포인터. README Codex 표의 상태 행도 포인터 | ✅ |
| 네이티브 흡수 판정 | `native-absorption.md` | 근거 열은 판정·스펙 경로 중심으로 정리. 긴 날짜별 근거 문단은 행 안에 남아 있다 | ⚠ 행 근거 문단이 길다(삭제는 근거 소실이라 남김) |
| 컨벤션 색인 | `docs/conventions/README.md` | 전부 색인, import 여부는 `CLAUDE.md` 가 권위 | ✅ |
| 폐기된 기능 기록 | `delegation-signal-retirement.md` | `CLAUDE.md` 한 단락·README 한 단락 모두 그 문서를 가리킴 | ✅ |
| harness-export 종료코드·분류 | `export_harness.py` docstring | 스킬 측은 W2 | — (W2) |
| Task 도구 폴백 | `task-tools-fallback.md` | `native-absorption.md` 는 그 파일을 가리킴. 스킬 측은 W3 | ✅(W1 범위) |
| 시점 고정 문서 지위 | 각 문서 frontmatter `status:` | `research/README.md`·`specs/README.md` 는 색인이며 "frontmatter 가 정본"을 선언 | ✅ |
