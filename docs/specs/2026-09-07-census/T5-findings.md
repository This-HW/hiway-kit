# T5 — 배포·프로젝트 문서 축 감사 결과

> 감사자: T5 워커 (읽기 전용) · 대상 커밋: 워크트리 HEAD `dd63b44`(로컬 `main`)
> 정렬 대상: `docs/specs/2026-09-07-hiway-program-design.md` (D-1~D-21) — **주의**: 이 파일은
> 이 워크트리에 물리적으로 존재하지 않는다. §0과 §4 참고.

---

## §0. 선행 경고 — 워크트리 기준점 불일치 (감사 신뢰도에 영향)

작업 지시서는 "워크트리가 `main`(커밋 `c707729`)에서 생성됐다"고 명시했다. 그러나 실측 결과:

- 이 워크트리의 로컬 `main` 브랜치는 `dd63b44`를 가리킨다 (`git log --oneline main -1`).
- `origin/main`(GitHub 원격의 실제 main)은 `c707729`를 가리킨다 — 로컬 `main`보다 **8개 커밋 앞서 있다**.
- `git merge-base --is-ancestor dd63b44 c707729` → true. 즉 로컬 `main`은 원격 `main`의
  **오래된 조상**이고, 이 워크트리는 그 오래된 지점에서 분기됐다.
- 그 8개 커밋 안에 **W-024 전체**(티어2 커버리지 갭 봉쇄)와 **하이웨이 프로그램 설계 문서
  전체**(D-1~D-21, §8·§9 포함)가 들어 있다 — 즉 스코프 목록에 있는
  `docs/specs/2026-09-04-eval-tier2-coverage-gate.md`와
  `docs/specs/2026-09-07-hiway-program-design.md` **두 파일 모두 이 워크트리에 없다.**

**대응**: 두 파일은 `git show c707729:<path>`로 git 객체 DB에서 읽어(작업트리를 건드리지 않는
읽기 전용 조회) 내용을 확인했고, 정렬 대상 문서(D-1~D-21)의 실제 내용은 확보했다. 이 두
파일은 커버리지 표에서 `CONFLICT`로 표시했다 — 충돌 상대는 "이 워크트리의 물리적 부재"
자체다. 나머지 70개 파일은 전부 워크트리에 실재한다.

---

## §1. 커버리지 표 (72/72)

| # | 파일 | 판정 | 한 줄 근거 |
|---|---|---|---|
| 1 | `.claude-plugin/marketplace.json` | OK | 필드·source·category 전부 현재 배포 구성(git-subdir, plugins/common)과 일치 |
| 2 | `CHANGELOG.md` | OK | 최상단 `[2.17.0]`이 `plugin.json`의 `version`과 일치(§4 실측) |
| 3 | `README.md` | OK | 33/19/13 카운트, 설치 경로, Delegation Signal 이력 서술 전부 실측과 일치 |
| 4 | `docs/codex-submission-checklist.md` | OK | 사람 행동 체크리스트; `[unresolved]` 표기가 정직하게 유지됨 |
| 5 | `docs/conventions/README.md` | OK | 이관 기준·대상 서술이 실제 `docs/conventions/*` 7종과 일치 |
| 6 | `docs/conventions/lint-single-ruleset.md` | OK | `ruff.toml`/`.ruff-version`/`.pytest-version` 관례 서술이 현재와 일치 |
| 7 | `docs/conventions/no-gate-integration.md` | OK | "3종 게이트 통합 안 함" 판단이 CLAUDE.md 본문과 축자 일치 |
| 8 | `docs/conventions/path-containment.md` | OK | 경로 봉쇄 규칙 3인스턴스 서술이 CLAUDE.md와 일치, 현재도 유효한 관례 |
| 9 | `docs/conventions/reference-vs-judgment.md` | OK | 사례(버전 감사 도구 폐기)가 CHANGELOG `[Unreleased]`/git log로 확인 가능한 역사 기록 |
| 10 | `docs/conventions/release-process.md` | OK | `scripts/bump-version.sh` 실재 확인(§4), 절차 서술 일치 |
| 11 | `docs/conventions/rules-mirror.md` | OK | "9개 미러 + definition-of-done 등 4개 미러 없음" 실측과 정확히 일치(§4) |
| 12 | `docs/conventions/shell-lint.md` | OK | `scripts/lint-shell.sh` 관례 서술이 현재와 일치 |
| 13 | `docs/marketplace-submission.md` | OK | v2.7.0 시점 기록임을 스스로 명시("현재 버전은 CHANGELOG 참조") — 역사 기록으로 보존 적절 |
| 14 | `docs/native-absorption.md` | OK | 마지막 전수 검토 2026-08-26, 현재(2026-09-07)까지 12일 — watch 2행 모두 아직 유효, 자체 신선도 경고 문구 보유 |
| 15 | `docs/pipeline-reinforcement-plan-v2.md` | OK | Track 2 폐기 이력·Track 1 구현 상태 모두 최신 판정으로 갱신돼 있음(2026-08-27) |
| 16 | `docs/research/2026-07-harness-loop-engineering.md` | OK | 리서치 노트, 날짜·범위 명시, 이후 batch(W-011) 반영 여부까지 자체 기록 |
| 17 | `docs/research/2026-07-long-running-loop-agents.md` | OK | 리서치 노트, kit 통합 권고가 이후 구현(§8 durable-executor)과 일관 |
| 18 | `docs/research/2026-08-27-superpowers-distribution.md` | OK | 조사일 명시, 부록 1~5 전부 `[confirmed]` 태그, 이후 스펙들의 근거로 정확히 인용됨 |
| 19 | `docs/specs/2026-06-13-architecture-readme.md` | OK | 완료된 설계 스펙, README "Architecture & Concepts" 섹션으로 실현됨 |
| 20 | `docs/specs/2026-06-13-definition-of-done.md` | OK | 완료된 설계 스펙, `rules/definition-of-done.md` + `verify-done.sh`로 실현됨 |
| 21 | `docs/specs/2026-06-13-feedback-memory.md` | OK | ledger 경로(`docs/works/feedback/ledger.md`)가 `feedback_ledger.py` 실물과 일치(§4) |
| 22 | `docs/specs/2026-06-13-loop-engineering.md` | OK | "`/goal` 대화형 전용" 구현 노트가 실제 구현(auto-dev while-loop)과 일치 |
| 23 | `docs/specs/2026-06-13-native-foundation.md` | OK | 완료된 설계 스펙(exec form 훅 전환 등), 현재 hooks.json과 일치 |
| 24 | `docs/specs/2026-06-13-orchestration.md` | OK | "네이티브 workflow 대화형 전용" 구현 노트가 이후 agent-teams 실제 상태와 일치 |
| 25 | `docs/specs/2026-07-03-durable-executor-discipline.md` | OK | v1 폐기 근거 명시, v2(checklist.json)가 §8 verify-done.sh와 일치 |
| 26 | `docs/specs/2026-07-07-toolkit-improvement-batch.md` | OK | W-A~E 전부 완료 흔적 확인(evals/, native-watch, self-improve 실재) |
| 27 | `docs/specs/2026-07-09-mcp-portability-consumer-first.md` | OK | R1~R8 판정이 현재 agents `tools:`에 `mcp__*` 0건인 상태와 일치 |
| 28 | `docs/specs/2026-08-22-ade-benchmark-absorption.md` | OK | harness-export/eval-forge/skill-forge 스킬 3종 실재로 완료 확인 |
| 29 | `docs/specs/2026-08-26-eval-coverage-and-gates.md` | OK | W-018 완료, 후속 W-023/W-024로 이어지는 티어 체계가 현재 `evals/policy.json` 개념과 일치 |
| 30 | `docs/specs/2026-08-26-multi-harness-packaging.md` | OK | `packaging/targets.json`·`build-targets.py` 실재로 완료 확인, 초안 오류 정정 이력도 투명 |
| 31 | `docs/specs/2026-08-27-delegation-signal-contract-review.md` | OK | "판별 후 실행"이 W-022 R1으로 이어졌고 CLAUDE.md 본문이 그 결과를 정확히 반영 |
| 32 | `docs/specs/2026-08-27-remaining-debt-batch.md` | OK | R1~R9 전부 CHANGELOG [2.16.0]/[2.17.0] 항목으로 처리 완료 확인 |
| 33 | `docs/specs/2026-08-31-eval-git-coverage.md` | OK | git-workflow eval 승격이 CHANGELOG [2.17.0] "Fixed" 절과 정확히 일치 |
| 34 | `docs/specs/2026-09-04-eval-tier2-coverage-gate.md` | CONFLICT | 워크트리에 파일 없음(§0) — `git show c707729:<path>`로만 확인 가능 |
| 35 | `docs/specs/2026-09-07-hiway-program-design.md` | CONFLICT | 워크트리에 파일 없음(§0) — 정렬 대상 문서 자체가 로컬에 부재 |
| 36 | `docs/superpowers/plans/2026-04-21-claude-upgrade.md` | ORPHAN | 레포 전체에서 `docs/superpowers` 문자열 참조 0건(§4 grep 실측) |
| 37 | `docs/superpowers/specs/2026-04-21-claude-upgrade-design.md` | ORPHAN | 위와 동일 — 이 디렉토리를 가리키는 문서·스크립트가 없음 |
| 38 | `docs/works/README.md` | OK | idea/active/completed 구조·work.sh 서브커맨드가 실물(work.sh case문)과 일치(§4) |
| 39 | `docs/works/completed/W-000.../W-000-hybrid-work-task-system.md` | STALE | L20 `docs/works/idea/W-000.../design-draft.md` — 완료 후 `idea/`→`completed/` 이동이 본문 경로에 반영 안 됨 |
| 40 | `docs/works/completed/W-000.../design-draft.md` | OK | 순수 설계 개념 문서, 시점 종속 서술 없음 |
| 41 | `docs/works/completed/W-001.../W-001-claude-code-updates.md` | STALE | L19 `> Status: planning`(frontmatter는 `completed`), L20 `idea/` 경로 — 완료 후 미갱신 |
| 42 | `docs/works/completed/W-001.../decisions.md` | OK | DEC-001~003 실제 기록, 내용·날짜 일관 |
| 43 | `docs/works/completed/W-001.../planning-results.md` | OK | 구현 계획 상세, 완료 시점과 모순 없음 |
| 44 | `docs/works/completed/W-001.../progress.md` | OK | 전 Phase 체크 완료, 완료 상태와 일치 |
| 45 | `docs/works/completed/W-002.../W-002-....md` | STALE | L19 `> Status: active / Planning`(frontmatter는 `completed`) — 미갱신 |
| 46 | `docs/works/completed/W-002.../decisions.md` | UNABSTRACTED | 헤더만 있고 DEC 항목 0건 — 실제 DEC-001~003은 `planning-results.md`에 인라인으로 존재(같은 내용의 SSOT가 갈라짐) |
| 47 | `docs/works/completed/W-002.../planning-results.md` | OK | DEC-001~003 + 전체 구현 계획 상세, 완료 흔적과 일치 |
| 48 | `docs/works/completed/W-002.../progress.md` | STALE/CONFLICT | 전 항목 `[ ]`(미체크) + 체크포인트 표 공란 — `planning-results.md`의 완료 체크포인트(#366~381 전부 `[x]`)와 정면 모순 |
| 49 | `docs/works/completed/W-003.../W-003-task-work-integration.md` | STALE | L18 `> Status: idea → planning`, L57 `[Phase 완료 후 여기에 결과 추가]`(미충전 placeholder) |
| 50 | `docs/works/completed/W-003.../decisions.md` | OK | DEC-001~003 실제 기록, planning-results.md와 일관 |
| 51 | `docs/works/completed/W-003.../design.md` | STALE | L5 `> 상태: 설계 확정 대기` — Work 전체가 완료됐는데도 "확정 대기"로 남음 |
| 52 | `docs/works/completed/W-003.../planning-results.md` | STALE | 말미 "설계 문서 위치: `docs/works/idea/W-003.../design.md`" — `idea/`가 아니라 `completed/`에 있음 |
| 53 | `docs/works/completed/W-003.../progress.md` | OK | Task Map 전 항목 완료 로그와 정확히 일치 |
| 54 | `docs/works/completed/W-004.../W-004-rules-injection-optimization.md` | STALE | L17 `> Status: planning → development`(frontmatter는 `completed`) |
| 55 | `docs/works/completed/W-004.../progress.md` | OK | 전 Task 완료 로그, 토큰 측정치까지 기록되어 완료 상태와 일치 |
| 56 | `packaging/targets.json` | OK | codex/antigravity enabled, cursor/pi/opencode/copilot disabled — 근거·확인일 전부 최신(2026-08-27) |
| 57 | `plugins/common/.claude-plugin/plugin.json` | OK | version 2.17.0, CHANGELOG와 일치(§4) |
| 58 | `plugins/common/README.md` | CONFLICT | L56 "Blocks edits containing secrets"가 protect-sensitive.py의 실제 동작(경로 기반 차단, 콘텐츠 스캔 아님)과 충돌 — 루트 `README.md`(정확한 서술)·`CLAUDE.md` Hooks 절과 다른 말을 함 |
| 59 | `plugins/common/hooks/hooks.json` | OK | 5개 훅 등록이 CLAUDE.md Hooks 절 서술과 정확히 일치(§4) |
| 60 | `site/README.md` | OK | Hugo 빌드·배포 절차 서술이 `.github/workflows/pages.yml` 존재와 부합(경로만 확인, 워크플로 파일은 스코프 밖) |
| 61 | `site/content/_index.en.md` | STALE | "11 agent behavior eval scenarios"(실제 37) — check_doc_counts.py가 agents/skills만 검사, eval 수는 게이트 안 됨 |
| 62 | `site/content/_index.md` | STALE | 위와 동일(한국어판) — "11개 시나리오"(실제 37), "220개 이상"(실제 455, 기술적으로 거짓은 아니나 2배 이상 과소) |
| 63 | `site/content/about.en.md` | CONFLICT | L40 "33 Agents, 16 Skills" — 실제 스킬 19개(§4 실측), README.md·CLAUDE.md·site/_index.en.md 자신과도 불일치. `check_doc_counts.py`는 이 파일을 검사 대상에 포함하지 않음(§4) |
| 64 | `site/content/about.md` | CONFLICT | L38 "33 에이전트 · 16 스킬" — 위와 동일 결함(한국어판) |
| 65 | `site/content/getting-started.en.md` | OK | 워크플로 설명(brainstorming→plan-task→auto-dev→review→test)이 현재 스킬 체인과 일치, 수치 주장 없음 |
| 66 | `site/content/getting-started.md` | OK | 위와 동일(한국어판) |
| 67 | `site/content/posts/2026-07-02-harness-engineering-in-practice.md` | OK | 날짜 있는 케이스 스터디, W-011 인용이 CHANGELOG와 부합 |
| 68 | `site/content/posts/2026-07-02-harness-loop-engineering-landscape.md` | DUP | `docs/research/2026-07-harness-loop-engineering.md`와 본문·표·출처가 사실상 동일 — 블로그 신디케이션 목적으로 보이나 두 곳에 같은 내용의 SSOT가 존재 |
| 69 | `site/content/posts/2026-07-03-auditing-your-own-gates.md` | OK | 날짜 있는 케이스 스터디, v2.9.0 시점 서술이 "직전 릴리스"로 정확히 프레이밍됨 |
| 70 | `site/content/posts/2026-07-03-durable-executor-machine-gate.md` | OK | `docs/specs/2026-07-03-durable-executor-discipline.md`의 v1 폐기 서사와 일관, 별개 내러티브 관점이라 DUP 아님 |
| 71 | `site/content/posts/2026-07-07-the-last-task-never-closes.md` | OK | 날짜 있는 케이스 스터디, 서술된 3중 방어가 이후 구현과 상충 없음 |
| 72 | `site/content/posts/_index.md` | OK | 트리비얼 인덱스, 시점 종속 주장 없음 |

**요약**: OK 53 · STALE 8 · CONFLICT 5 · ORPHAN 2 · UNABSTRACTED 1 · DUP 1 · UNKNOWN 0 · DUP 1 → 합계 72.

---

## §2. 발견 상세 (OK 아닌 19건)

### F-01. `docs/specs/2026-09-04-eval-tier2-coverage-gate.md` — CONFLICT
- **무엇이**: 스코프에 지정된 파일이 이 워크트리의 작업 디렉토리에 물리적으로 없음.
- **어디가**: 파일 전체(경로 자체).
- **왜 문제인가**: 감사 스코프가 "72개 전부 확인"을 요구하는데, 실물이 없어 워크트리
  기준으로는 검증 불가능하다. 내용 확인은 `git show c707729:<path>`로 우회했다.
- **무엇과 충돌하는가**: 작업 지시서의 전제("워크트리는 main@c707729에서 생성됨") ↔
  실측(`git log --oneline main -1` = `dd63b44`, `c707729`의 8커밋 이전 조상).
- **권고**: **유지 + 에스컬레이션**. 문서 자체는 정상(내용 확인 결과 OK 수준)이므로 삭제·수정
  대상이 아니다. 대신 컨트롤 세션에 워크트리 베이스 불일치를 보고해 재생성 여부를 판단받아야
  한다. 이 감사 결과 중 "워크트리에 없는 최신 변경"에 의존하는 판단(예: hiway 설계 D-1~D-21
  자체의 최신성)은 이 파일로는 검증 못 했다는 한계로 남긴다.

### F-02. `docs/specs/2026-09-07-hiway-program-design.md` — CONFLICT
- **무엇이**: F-01과 동일한 워크트리 부재 문제. 이 파일은 **정렬 대상 문서 자체**이므로 특히
  중요하다.
- **어디가**: 파일 전체.
- **왜 문제인가**: 태스크가 "네 발견은 이 계획과 대조돼야 한다"고 지시했는데, 그 대조 대상이
  워크트리에 없다. `git show`로 확보한 내용을 기준으로 §3을 작성했지만, 이는 이 워크트리의
  파일 시스템 상태가 아니라 git 객체 DB 조회 결과다.
- **무엇과 충돌하는가**: F-01과 동일.
- **권고**: **유지 + 에스컬레이션**. 컨트롤 세션에 이 사실을 명시적으로 알려, 정렬 결과(§3)를
  "실제 워크트리 파일 대조"가 아니라 "git 히스토리 조회 기반 대조"로 신뢰 수준을 낮춰 읽게
  해야 한다.

### F-03·F-04. `docs/superpowers/plans/2026-04-21-claude-upgrade.md`, `docs/superpowers/specs/2026-04-21-claude-upgrade-design.md` — ORPHAN
- **무엇이**: `docs/superpowers/` 디렉토리 전체(plans/·specs/ 각 1파일)가 레포 어디에서도
  참조되지 않는다.
- **어디가**: 디렉토리 경로 자체.
- **왜 문제인가**: `git grep -rn "docs/superpowers"`(작업 디렉토리 전체, 이 두 파일 자신
  제외) → **0건**(§4). `docs/works/README.md`, `docs/specs/` 색인, CLAUDE.md 어디에도 이
  디렉토리의 존재나 용도를 설명하는 문장이 없다. 디렉토리명이 "superpowers"라 `obra/superpowers`
  플러그인 관련 문서로 오인하기 쉬운데, 실제 내용은 claude-code-kit 자체의 2026-04 업그레이드
  계획(v2.0.0, 당시 멀티도메인 플러그인 구조)이며 `superpowers:writing-plans`류 스킬로
  생성된 산출물로 추정된다(계획 본문의 "REQUIRED SUB-SKILL: superpowers:subagent-driven-development"
  문구가 근거).
- **무엇과 충돌하는가**: 특정 파일과 충돌하지 않음 — 참조 부재 자체가 결함.
- **권고**: **이동 또는 색인화**. `docs/works/completed/`나 `docs/specs/`처럼 이미 있는
  역사 기록 디렉토리 관례로 옮기거나, 최소한 `docs/superpowers/README.md`를 추가해 "이
  디렉토리는 superpowers 플러그인 산출물이 아니라 그 스킬로 생성된 kit 자체 계획 문서다"를
  명시해 오인 가능성을 없앤다. 내용 자체는 완료 이력이라 삭제 대상은 아니다(보존 원칙).

### F-05. `docs/works/completed/W-000-hybrid-work-task-system/W-000-hybrid-work-task-system.md` — STALE
- **무엇이**: 본문 L20 "설계 문서: `docs/works/idea/W-000-hybrid-work-task-system/design-draft.md`".
- **어디가**: `W-000-hybrid-work-task-system.md:20`.
- **왜 문제인가**: 실제 파일 위치는 `docs/works/completed/...`다(스코프 목록 자체가 이를
  증명). Work가 `idea → active → completed`로 이동할 때 본문의 상대 경로 언급이 갱신되지
  않았다.
- **무엇과 충돌하는가**: 실제 파일 시스템 경로(`ls docs/works/completed/W-000.../`).
- **권고**: **축약/유지**. 히스토리 훼손 없이 경로 한 줄만 `completed/`로 고치면 되는 저비용
  수정이지만, 이 감사는 읽기 전용이라 실행하지 않는다. 우선순위 낮음(경로가 깨졌을 뿐 오해를
  유발할 사실 주장은 아님).

### F-06. `docs/works/completed/W-001-claude-code-updates/W-001-claude-code-updates.md` — STALE
- **무엇이**: 본문 L19 `> Status: planning`, L20 `docs/works/idea/W-001.../planning-results.md`.
- **어디가**: `W-001-claude-code-updates.md:19-20`.
- **왜 문제인가**: frontmatter는 `status: completed`, `phases_completed: [idea, planning,
  development, validation]`인데 본문 헤더는 아직 "planning"이라 말한다. 같은 파일 안에서
  frontmatter와 본문이 서로 다른 완료 상태를 주장한다.
- **무엇과 충돌하는가**: 같은 파일의 frontmatter(L4-6) 및 `progress.md`(전 Phase 체크 완료).
- **권고**: **유지**(역사 기록, 낮은 심각도). 다만 이 패턴이 W-001~W-004에 걸쳐 반복되므로
  §3에서 근본 원인으로 새 결정을 제안한다.

### F-07. `docs/works/completed/W-002-.../W-002-....md` — STALE
- **무엇이**: 본문 L19 `> Status: active / Planning`.
- **어디가**: `W-002-common-skills-마이그레이션-및-phase-gate-아키텍처-정비.md:19`.
- **왜 문제인가**: F-06과 동일 패턴. frontmatter `status: completed`와 모순.
- **무엇과 충돌하는가**: 같은 파일 frontmatter, `planning-results.md`의 완료 체크포인트.
- **권고**: F-06과 동일.

### F-08. `docs/works/completed/W-002-.../decisions.md` — UNABSTRACTED
- **무엇이**: 파일에 헤더(`## 의사결정 기록`)만 있고 DEC 항목이 0건.
- **어디가**: `decisions.md` 전체(6줄).
- **왜 문제인가**: 실제 결정 3건(DEC-001 phase-gates 스킬화 안 함, DEC-002 최신 기능 반영,
  DEC-003 agent-teams experimental 표기)은 `planning-results.md`의 "P0 결정사항" 절에
  인라인으로 존재한다. `docs/works/completed/W-000.../design-draft.md`가 정의한 템플릿
  ("decisions.md — 의사결정 기록 DEC-XXX")과 실제 관행이 W-002에서 어긋났다 — 같은 종류의
  기록(의사결정)이 Work마다 다른 파일에 산다.
- **무엇과 충돌하는가**: `planning-results.md`(같은 W-002 폴더)의 "P0 결정사항" 절이 사실상
  같은 내용의 다른 SSOT.
- **권고**: **유지**(역사 기록이므로 수정 불필요). 다만 향후 Work 템플릿 준수 여부를
  plan-task/auto-dev 스킬이 점검하게 하면 재발을 막을 수 있다 — §3에서 논의.

### F-09. `docs/works/completed/W-002-.../progress.md` — STALE/CONFLICT
- **무엇이**: 전체 체크박스가 `[ ]`(미완료)이고 "체크포인트" 표가 완전히 비어 있음.
- **어디가**: `progress.md:8-24` (Planning/Development/Validation 절 전부, 체크포인트 표).
- **왜 문제인가**: 같은 Work의 `planning-results.md:363-381` "체크포인트" 표는 A~E, F까지
  전 항목이 `[x]`로 표시돼 있다(F=commit & push만 `[ ]`). `progress.md`는 Work 생성
  직후(2026-04-05T06:47:55Z) 시점에서 멈춘 채 한 번도 갱신되지 않은 것으로 보인다 — 이
  Work의 실제 진행 상황을 알려면 `progress.md`가 아니라 `planning-results.md`를 봐야 한다.
- **무엇과 충돌하는가**: 같은 폴더의 `planning-results.md` 체크포인트 표, 메인 파일의
  `status: completed` frontmatter.
- **권고**: **유지**(역사 기록). 다만 이것은 "진행 상황의 SSOT가 어디인가"에 대한 실제
  운영 사고이므로, W-000 설계가 규정한 "Task 완료 시 progress.md 갱신 의무"가 W-002에서
  지켜지지 않은 사례로 §3에 기록한다.

### F-10. `docs/works/completed/W-003-task-work-integration/W-003-task-work-integration.md` — STALE
- **무엇이**: 본문 L18 `> Status: idea → planning`, L57 `## Planning 결과\n\n[Phase 완료 후
  여기에 결과 추가]`(미충전 placeholder).
- **어디가**: `W-003-task-work-integration.md:18`, `:56-57`.
- **왜 문제인가**: F-06/F-07과 같은 상태-불일치 패턴에 더해, "여기에 결과 추가"라는
  placeholder 문구가 그대로 남아 있다 — 실제 Planning 결과는 별도 파일
  `planning-results.md`에 상세히 존재하므로 이 placeholder는 그냥 채워지지 않은 채 방치됐다.
- **무엇과 충돌하는가**: frontmatter(`status: completed`), `planning-results.md`(실제 내용
  보유), `progress.md`(전 Task 완료).
- **권고**: F-06과 동일 — 유지 + 근본원인 §3 반영.

### F-11. `docs/works/completed/W-003-task-work-integration/design.md` — STALE
- **무엇이**: 헤더 L5 `> 상태: 설계 확정 대기`.
- **어디가**: `design.md:5`.
- **왜 문제인가**: Work 전체가 `completed`인데 설계 문서만 "확정 대기" 상태로 남아 있다.
  실제로는 이 설계가 구현됐다(`progress.md`의 T-1~T-8 전부 완료, session-start.py/
  task-resume.md 실재).
- **무엇과 충돌하는가**: 메인 파일 frontmatter, `progress.md`.
- **권고**: 유지 + §3.

### F-12. `docs/works/completed/W-003-task-work-integration/planning-results.md` — STALE
- **무엇이**: 말미 "설계 문서 위치: `docs/works/idea/W-003-task-work-integration/design.md`".
- **어디가**: `planning-results.md:76`(파일 끝부분).
- **왜 문제인가**: F-05와 동일한 `idea/` 잔존 경로 패턴. 실제 `design.md`는
  `docs/works/completed/W-003-task-work-integration/design.md`에 있다.
- **무엇과 충돌하는가**: 실제 파일 시스템 경로.
- **권고**: 유지(낮은 심각도, 경로 참조만 깨짐).

### F-13. `docs/works/completed/W-004-rules-injection-optimization/W-004-rules-injection-optimization.md` — STALE
- **무엇이**: 본문 L17 `> Status: planning → development`.
- **어디가**: `W-004-rules-injection-optimization.md:17`.
- **왜 문제인가**: F-06/F-07/F-10과 동일한 패턴. frontmatter는 `status: completed`.
- **무엇과 충돌하는가**: 같은 파일 frontmatter, `progress.md`(전 Task 완료 + 토큰 측정치
  기록까지 있음).
- **권고**: 유지 + §3.

### F-14·F-15. `site/content/_index.md`, `site/content/_index.en.md` — STALE
- **무엇이**: "Agent Behavior Evals **11개 시나리오**"/"**11** agent behavior eval scenarios"
  (한국어판 L19, 영어판 L20), "유닛 테스트 **220개 이상**"/"**220+** unit tests"(한국어판
  L18, 영어판 L19).
- **어디가**: `site/content/_index.md:18-19`, `site/content/_index.en.md:19-20`.
- **왜 문제인가**: 실측(§4) — `evals/scenarios/` 하위 시나리오 디렉토리 **37개**,
  `python3 -m pytest --collect-only` **455개** 수집. "11개"는 명시적 정수 주장이라 실제
  37과 정면으로 어긋난다(3배 이상 과소). "220개 이상"/"220+"은 "이상"이라는 하한 표현이라
  기술적으로는 거짓이 아니지만(455 ≥ 220), 실제가 2배 이상이라 현재를 대표하는 수치로 보기
  어렵다. "기계 게이트 **8개 이상**"(L20/L21)도 같은 성격 — 실측 `verify-done.sh`의 명명된
  섹션은 **15개**(§4)다.
- **무엇과 충돌하는가**: `evals/scenarios/`(실측 37), `python3 -m pytest`(실측 455),
  `scripts/verify-done.sh`의 `hdr` 15종(실측).
- **권고**: **갱신**. `scripts/check_doc_counts.py`가 이 두 파일의 agents/skills 카운트는
  검사하지만(§4 확인) eval 시나리오 수·유닛 테스트 수·게이트 수는 검사 대상이 아니다 — 이
  숫자들이 게이트 밖에 있어서 조용히 낡았다.

### F-16·F-17. `site/content/about.md`, `site/content/about.en.md` — CONFLICT
- **무엇이**: "## 2. 33 에이전트 · 16 스킬 · 3단 모델 티어링" / "## 2. 33 Agents, 16 Skills,
  Three-Tier Model Selection".
- **어디가**: `site/content/about.md:38`, `site/content/about.en.md:40`.
- **왜 문제인가**: 실제 스킬 수는 **19개**(`find plugins/common/skills -maxdepth 2 -iname
  SKILL.md | wc -l` = 19, §4). "16"은 2026-08-22 ADE 배치 이전 수치로 보인다(당시
  스펙 문서가 "16 → 19"라는 갱신을 명시했다 — `docs/specs/2026-08-22-ade-benchmark-
  absorption.md` §3.4 "README.md / CLAUDE.md 스킬 카운트 16 → 19"). about 페이지만 그
  갱신에서 빠졌다.
- **무엇과 충돌하는가**: `README.md`("19 skills"), `CLAUDE.md`("skills (19)"),
  `plugins/common/README.md`("19 skills"), 그리고 **같은 사이트의**
  `site/content/_index.md`/`_index.en.md`("스킬 19개"/"19 skills") — 같은 사이트 안에서도
  페이지끼리 다른 숫자를 말한다.
- **권고**: **갱신**. `scripts/check_doc_counts.py`의 site 검사 루프가 `_index.md`/
  `_index.en.md`만 대상으로 하고 `about.md`/`about.en.md`는 포함하지 않는다(§4 코드 확인)
  — 검사 범위 확장이 재발 방지책이다.

### F-18. `plugins/common/README.md` — CONFLICT
- **무엇이**: "## Hooks (auto-registered)" 절, "**PreToolUse** — Blocks edits containing
  secrets (`protect-sensitive.py`)".
- **어디가**: `plugins/common/README.md:56`.
- **왜 문제인가**: `protect-sensitive.py`의 실제 동작은 **경로 기반** 차단(`.env`, 키,
  `.pem` 등 민감 **경로**를 막음)이고, 콘텐츠 스캔은 env 템플릿 쓰기에 대한 best-effort
  케이스 하나뿐이다(CLAUDE.md Hooks 절, 루트 `README.md` Security 절이 이를 정확히
  서술한다). "Blocks edits containing secrets"라는 문구는 이 훅이 임의 파일의 **내용**에서
  시크릿을 찾아 차단한다는 인상을 준다 — 실제로는 그렇지 않다(내용 기반 커밋 시크릿 차단은
  gitleaks의 몫).
- **무엇과 충돌하는가**: 루트 `README.md`("blocks access to sensitive file paths ...
  Commit-time secret scanning is gitleaks + setup/pre-commit, not this hook" — 정확한
  서술), `CLAUDE.md` Hooks 절("path-based ... It does not otherwise scan file content").
- **권고**: **축약/정정**. 같은 레포 안에 정확한 서술(루트 README)이 이미 있으므로, 이
  파일의 문구를 그것과 같은 말로 맞추면 된다(신규 조사 불필요).

### F-19. `site/content/posts/2026-07-02-harness-loop-engineering-landscape.md` — DUP
- **무엇이**: `docs/research/2026-07-harness-loop-engineering.md`와 본문(TL;DR, 3개 표,
  "이미 정합인 것"/"W-011에서 반영한 것" 절, 출처 목록)이 사실상 동일하다.
- **어디가**: 파일 전체(양쪽 모두 약 200줄, 구조·문장이 거의 1:1 대응).
- **왜 문제인가**: 같은 내용에 대한 SSOT가 두 곳에 있다. `docs/research/`가 원본 리서치
  노트이고 `site/content/posts/`가 공개 발행본으로 보이나(블로그 신디케이션), 원본이
  수정되면 발행본이 조용히 뒤처질 수 있다.
- **무엇과 충돌하는가**: `docs/research/2026-07-harness-loop-engineering.md` — 다만 둘 다
  날짜가 박힌 리서치 노트라 시점상 "동시에 확정된 스냅샷"으로 볼 수도 있다.
- **권고**: **유지**. 블로그 포스트는 정적 발행물(공개 사이트, 특정 날짜의 스냅샷)이라
  사후에 계속 동기화할 성격이 아니다 — 이 감사 규칙("과거 기록은 보존이 원칙")을 그대로
  적용하면 두 파일 모두 OK에 가깝다. 다만 향후 리서치 노트를 대폭 수정할 계획이 있다면
  발행본과의 괴리를 인지하고 있어야 한다는 점만 기록해 둔다(우선순위 낮음).

---

## §3. 계획 정렬 — 발견을 D-1~D-21과 대조

`docs/specs/2026-09-07-hiway-program-design.md`(§0 경고 참고, git show로 확보한 내용
기준)의 D-1~D-21과 대조한 결과:

| 발견 | 흡수되는 결정 | 근거 / 새 결정 제안 |
|---|---|---|
| F-14·F-15 (site index 페이지 eval/test 수 낡음) | **D-3에 흡수** | D-3은 "이름을 SSOT에서 파생시킨다"며 적용 대상에 `site/` 콘텐츠를 명시한다. eval 시나리오 수·유닛 테스트 수·게이트 수도 같은 파생 파이프라인의 확장 대상이 될 수 있다 — 다만 D-3 원문은 "이름"(name)에 한정돼 있고 수치 카운트는 명시 대상이 아니므로, D-3의 구현 시(W-027 27-2) `check_doc_counts.py` 부류의 검사를 이 두 수치까지 넓히자는 **세부 제안**으로 남긴다. |
| F-16·F-17 (about 페이지 "16 스킬" 오기재) | **새 결정 필요** | D-1~D-21 중 이 결함을 직접 다루는 항목이 없다. `check_doc_counts.py`의 site 검사 루프가 `_index.md`/`_index.en.md`만 보고 `about.md`/`about.en.md`를 빠뜨린 것은 **검사 대상 목록의 완전성 문제**이지 이름 파생(D-3) 문제가 아니다 — 정확히는 W-024 스펙(§1)이 지적한 "검사 대상이 아닌 것은 결코 red가 되지 않는다"는 결함 클래스의 또 다른 사례다. **제안**: `check_doc_counts.py`의 site 검사 대상 목록에 `about.md`/`about.en.md`를 추가한다(신규 결정 D-22 후보, 또는 W-025의 위생 작업 항목에 편입). |
| F-18 (plugins/common/README.md 훅 서술 부정확) | **새 결정 불필요** | 단순 편집 오류다. D-2(파리티 계약)나 D-3(이름 파생)의 범위가 아니다 — 이미 정확한 서술(루트 README)이 존재하므로 그것과 맞추면 끝나는 저비용 수정. 결정이 필요한 사안이 아니라 즉시 반영 가능한 정정 항목으로 분류한다. |
| F-03·F-04 (`docs/superpowers/` orphan) | **새 결정 필요** | D-1~D-21 어디에도 이 디렉토리를 언급하지 않는다. **제안**: "kit 자체 계획 문서와 superpowers 플러그인 관련 문서를 디렉토리명으로 구분한다" — 예컨대 `docs/superpowers/` → `docs/plans/`(또는 기존 `docs/works/` 관례에 편입)로 재배치하거나, 최소한 README 한 줄로 오인 가능성을 차단한다. D-3(이름 SSOT화) 작업 시 문서 디렉토리 구조를 훑는 김에 함께 처리할 수 있는 저비용 항목이다. |
| F-06·F-07·F-09·F-10·F-11·F-13 (`docs/works/` 완료 후 inline status 미갱신 패턴, W-001~W-004 반복) | **새 결정 필요** | D-1~D-21은 규범 주입(§9)·이름(§2-§3)·구조 감사(§8)를 다루지만 **Work 문서 자체의 라이프사이클 정합성**은 다루지 않는다. 이 패턴이 4개 Work에 걸쳐 반복된다는 것은 §8이 발견한 "같은 결함 클래스가 여러 번 반복"과 같은 성격이다. **제안**: `work.sh complete <id>` 커맨드가 메인 파일의 `> Status:` 인라인 줄을 frontmatter와 동기화하도록 자동화하거나(기계적 수정, 결합도 0 원칙에 부합), 최소한 W-000이 정의한 템플릿에 "완료 시 본문 상태 줄도 갱신할 것"을 명시한다. 신규 결정 D-23 후보 — 단 이 감사 자체는 역사 기록 보존 원칙상 기존 4개 파일을 고치라고 권고하지 않는다(F-06 등 참고). |
| F-08 (`decisions.md`가 비고 실제 DEC은 `planning-results.md`에 존재, W-002) | **D-13과 유사 계열, 새 결정 후보** | D-13(어서션 계약 이중 선언 통합)과 같은 근본 원인 — "같은 내용에 대한 선언 지점이 둘"이다. 다만 D-13은 `evals/run.py`의 코드 계약을 다루고, 이 건은 Work 문서 템플릿 준수 문제라 직접 흡수 대상은 아니다. **제안**: plan-task/auto-dev 스킬이 Work 완료 전 "decisions.md에 실제 DEC 항목이 있는가"를 최소 점검하게 한다 — F-06~F-13 제안과 통합 가능. |
| F-19 (블로그 포스트 ↔ 리서치 노트 DUP) | **결정 불필요 — 현행 유지가 맞음** | 블로그는 발행 시점 스냅샷이라는 성격상 D-3(이름 SSOT화)이나 D-13(계약 통합)의 대상이 아니다. 이 감사의 보존 원칙을 그대로 적용하면 OK에 가깝다. |
| F-01·F-02 (워크트리 기준점 불일치) | **결정 불필요 — 감사 인프라 문제** | D-1~D-21은 kit의 배포·아키텍처 결정이고, 이 문제는 이 감사 세션의 워크트리 생성 프로세스(오케스트레이션 레이어) 결함이다. 컨트롤 세션에 별도 에스컬레이션이 필요하다(§4 참고). |

**요약**: 19건의 non-OK 중 1건(F-14/F-15)만 기존 결정(D-3)에 부분 흡수되고, 나머지는 대부분
**새 결정 후보**(문서 위생·게이트 커버리지 확장류, 전부 저위험·저비용)이거나 **결정 불필요**
(단순 정정 또는 보존이 정답)로 분류된다. D-1~D-21이 다루는 것은 하네스 중립 전환이라는 큰
그림이고, 이번 T5 감사가 잡은 것은 대부분 "생성물이 SSOT와 다시 어긋난" 종류의 지엽적
드리프트다 — CLAUDE.md가 이미 명명한 결함 클래스("검사 대상이 아닌 것은 결코 red가 되지
않는다")의 반복 사례들이다.

---

## §4. 실측 로그

### 4.1 워크트리 기준점 확인
```bash
git log --oneline -5                 # HEAD/로컬 main = dd63b44
git branch -a                        # main, origin/main 등 목록
git log --oneline main -5            # 로컬 main 최상단 = dd63b44
git merge-base dd63b44 c707729       # → dd63b44 (dd63b44가 공통 조상)
git merge-base --is-ancestor c707729 dd63b44   # → no
git merge-base --is-ancestor dd63b44 c707729   # → yes  (dd63b44가 c707729의 조상)
git branch --contains c707729 -a     # → origin/main, origin/HEAD, This-HW/planning-control-session
git log -1 --format='%H %D' c707729  # → c707729 ... origin/main, origin/HEAD, This-HW/planning-control-session
git cat-file -e c707729:docs/specs/2026-09-07-hiway-program-design.md   # 존재
git cat-file -e c707729:docs/specs/2026-09-04-eval-tier2-coverage-gate.md  # 존재
test -f docs/specs/2026-09-07-hiway-program-design.md   # 워크트리엔 없음
test -f docs/specs/2026-09-04-eval-tier2-coverage-gate.md  # 워크트리엔 없음
```
→ 결론: 로컬 `main`이 `origin/main`보다 8커밋 뒤처져 있고, 그 차이에 두 스코프 파일이
포함됨. `git show c707729:<path>`로 내용만 확보해 §1/§3 판정에 사용.

### 4.2 스코프 72개 파일 존재 확인
```bash
while IFS= read -r f; do [ -f "$f" ] || echo "MISSING: $f"; done < scope_files.txt
# → MISSING: docs/specs/2026-09-04-eval-tier2-coverage-gate.md
# → MISSING: docs/specs/2026-09-07-hiway-program-design.md
# (나머지 70개는 전부 존재 확인)
```

### 4.3 컴포넌트 실측 카운트 (README/CLAUDE.md/site 주장 대조용)
```bash
find plugins/common/agents -name "*.md" | wc -l          # → 33
find plugins/common/skills -maxdepth 2 -iname "SKILL.md" | wc -l  # → 19 (references/·README.md 제외)
find plugins/common/skills -maxdepth 1 -mindepth 1 -type d | wc -l # → 20 (SKILL.md 없는 references/ 포함)
find plugins/common/rules -maxdepth 1 -name "*.md" | wc -l # → 13
grep '"version"' plugins/common/.claude-plugin/plugin.json # → "2.17.0"
head -20 CHANGELOG.md                                       # 최상단 [2.17.0] 확인
```

### 4.4 hooks.json 실측 (등록된 훅 = 5개)
```bash
cat plugins/common/hooks/hooks.json
# SessionStart: session-check.py + session-start.py
# PreToolUse: protect-sensitive.py
# PostToolUse: auto-format.py
# Stop: stop-validator.py
find plugins/common/hooks -maxdepth 1 -name "*.py" | wc -l  # → 8 (checklist.py·export_harness.py·
                                                              #    feedback_ledger.py·utils.py는 훅 미등록 지원 스크립트)
```

### 4.5 rules mirror 카운트 (docs/conventions/rules-mirror.md 대조)
```bash
ls docs/architecture/rules/   # 9개 .md + MIRROR.sha256
ls plugins/common/rules/*.md  # 13개
# 차집합 4개: definition-of-done, feedback-loop, loop-engineering, parallel-worktree
# → rules-mirror.md의 "9개 미러 + 4개 미러 없음" 서술과 정확히 일치
```

### 4.6 feedback ledger 경로 (docs/specs/2026-06-13-feedback-memory.md 대조)
```bash
grep -n "ledger_path\|docs.*works.*feedback" plugins/common/hooks/feedback_ledger.py
# → return root / "docs" / "works" / "feedback" / "ledger.md"
# → 스펙의 "docs/works/feedback/ledger.md" 서술과 일치
```

### 4.7 pytest / eval 시나리오 / verify-done.sh 섹션 수 (site 페이지 대조용)
```bash
python3 -m pytest --collect-only 2>&1 | tail -1       # → 455 tests collected
find evals/scenarios -mindepth 2 -maxdepth 2 -type d | wc -l  # → 37
grep -n '^hdr ' scripts/verify-done.sh
# → 1,2,3,3b,4,5,6,7,8,9,10,13,11,14,15 (총 15개 명명 섹션; §12는 의도적으로 비워짐,
#    §16은 아직 미구현 — hiway 설계 D-20이 제안하는 미래 섹션)
```
→ site/content/_index.md·_index.en.md의 "11개 시나리오"(실제 37), "220개 이상"(실제 455),
  "8개 이상 게이트"(실제 15, 표현상 거짓은 아님) 판정의 근거.

### 4.8 check_doc_counts.py의 site 검사 범위 확인
```bash
grep -n "site/" scripts/check_doc_counts.py
# → line 147: for rel in ("site/content/_index.md", "site/content/_index.en.md"):
# → about.md/about.en.md는 이 루프에 없음 — F-16·F-17이 게이트 밖에 있는 이유
```

### 4.9 `docs/superpowers/` 참조 여부
```bash
grep -rn "docs/superpowers" --include="*.md" --include="*.py" . 2>/dev/null | grep -v "^./docs/superpowers"
grep -rln "docs/superpowers" .
# → 두 명령 모두 결과 없음(0건) — ORPHAN 판정의 근거
```

### 4.10 `docs/works/` gitignore·work.sh 서브커맨드 확인
```bash
grep -n "works" .gitignore
# → 39:docs/works/  (전체가 gitignore 대상, "내부 개발 기록, 공개 리포에 포함하지 않음")
git ls-files docs/works/
# → W-000~W-004만 추적됨(force-add 예외), active/·completed/ 의 .gitkeep만 그 외 추적
grep -n '^\s*[a-z-]*)\s*cmd_' scripts/work.sh
# → new/list/show/start/next-phase/complete/resume — docs/works/README.md의 서술과 일치
```
→ "W-005~W-024가 없는 것은 의도"라는 태스크의 전제를 확인 — `.gitignore`가 명시적으로
  `docs/works/`를 제외하고, W-000~W-004만 예외적으로 추적된 상태.

### 4.11 plugins/common/README.md 훅 서술 대조
```bash
grep -n "Blocks edits containing secrets\|Phase-gate check" plugins/common/README.md
# → 56: PreToolUse — Blocks edits containing secrets (protect-sensitive.py)
```
→ 루트 `README.md`("blocks access to sensitive file paths ... not this hook")·`CLAUDE.md`
  Hooks 절과 문구 대조해 F-18 판정.

### 4.12 hiway 설계 문서(D-1~D-21) 확보
```bash
git show c707729:docs/specs/2026-09-07-hiway-program-design.md > <scratchpad>/hiway-design.md
git show c707729:docs/specs/2026-09-04-eval-tier2-coverage-gate.md > <scratchpad>/tier2-spec.md
```
→ 워크트리에 없는 두 파일의 내용을 읽기 전용으로 확보(§3 정렬 분석에 사용). 워크트리
파일은 수정하지 않았음 — 스크래치패드 디렉토리에만 복사.

---

## 부기 — 감사 범위/한계 고지

- `docs/specs/2026-09-04-eval-tier2-coverage-gate.md`·`docs/specs/2026-09-07-hiway-program-
  design.md` 두 건은 워크트리 부재로 git 히스토리 조회를 통해서만 검증했다(§0). 이 두 파일에
  대한 판정은 "파일 내용"이 아니라 "워크트리 상태"를 근거로 한 CONFLICT다 — 내용 자체는
  읽어본 결과 이상 없음(설계 문서로서 완결적이고 자기 근거가 명확함).
- 이 보고서가 인용한 D-1~D-21은 전부 `git show c707729:...`로 얻은 텍스트를 근거로 한다.
  워크트리가 재생성되어 실제로 그 커밋을 포함하게 되면, 이 정렬 분석(§3)을 그 시점 파일
  기준으로 재확인할 것을 권고한다.
