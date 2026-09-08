# T2 — 에이전트 축 전수 문서 감사

> 감사 워커. 읽기 전용. 스코프: `plugins/common/agents/**` 33개 파일.
> 정렬 대상: `docs/specs/2026-09-07-hiway-program-design.md`(D-1~D-21, origin/main c707729 기준 — §4 참고).

## 0. 워크트리 상태 고지 (읽기 전 필수)

이 워크트리(`This-HW/census-T2`, HEAD `dd63b44`)는 `origin/main`(HEAD `c707729`)보다
**11개 커밋 뒤처져 있다**(`git log --oneline dd63b44..origin/main`, §4 참고). 뒤처진 커밋에는
`docs/specs/2026-09-07-hiway-program-design.md` 자체와 W-024(eval tier2 게이트) 커밋들이
포함된다.

**영향 범위를 실측으로 봉쇄했다**: `git diff --stat dd63b44..origin/main -- plugins/common/agents/`
가 **빈 출력**이다 — 스코프 33개 파일은 이 두 지점 사이에서 **한 글자도 바뀌지 않았다**
(파일별 `diff` 개별 대조로 재확인, §4). 따라서 아래 §1~§3의 에이전트 파일 findings는
전부 현재 SSOT(`origin/main`) 기준으로 유효하다. 단, §3에서 인용하는 `evals/policy.json`·
`scripts/check_eval_coverage.py`는 이 워크트리와 `origin/main` 사이에 **실제로 차이가 있어**
직접 읽지 않고 `git show origin/main:<path>`로 조회했다(§4에 그 diff를 남긴다) — 이 판단이
왜 필요했는지는 §3의 consensus-builder 항목에서 상세히 다룬다.

---

## 1. 커버리지 표 (33/33)

| # | 파일 | 판정 | 한 줄 근거 |
|---|------|------|-----------|
| 1 | `backend/design-services.md` | OK | frontmatter 완전, 금지 필드 없음, 위임/충돌 없음 |
| 2 | `backend/implement-api.md` | UNABSTRACTED | Worktree 복귀 프로토콜 4줄이 `rules/parallel-worktree.md`와 동일 내용으로 8개 파일에 복제 |
| 3 | `backend/optimize-logic.md` | UNABSTRACTED | 상동 |
| 4 | `backend/write-api-tests.md` | UNABSTRACTED | 상동 |
| 5 | `dev/analyze-dependencies.md` | OK | 읽기전용 계약·위임 체인 정상 |
| 6 | `dev/analyze-tech-debt.md` | STALE | 예시 리포트에 무관 프로젝트명 `claude_setting` 잔존 |
| 7 | `dev/enforce-structure.md` | CONFLICT | 존재하지 않는 `project-structure.yaml`·`governance-check.py`를 필수 입력/연동으로 서술 |
| 8 | `dev/explore-codebase.md` | OK | 동일 파일을 참조하지만 소프트(있으면 확인) 방식이라 동작에 지장 없음 |
| 9 | `dev/fix-bugs.md` | UNABSTRACTED | Worktree 복귀 프로토콜 중복 |
| 10 | `dev/generate-boilerplate.md` | CONFLICT | 새 에이전트 생성 템플릿에 폐기된 `DELEGATE_TO`/`TASK_COMPLETE` 신호 계약 잔존 |
| 11 | `dev/git-workflow.md` | OK | W-023 충돌 처리 수정 반영, 최신 |
| 12 | `dev/implement-code.md` | STALE | `references:` 필드가 가리키는 파일 3개 전부 미존재 + SSOT 자기참조 경로가 실제 경로와 불일치 |
| 13 | `dev/manage-api-versions.md` | STALE | 존재하지 않는 에이전트 `version:` 필드·`agents/**/index.json` 레지스트리를 관리 대상으로 서술 |
| 14 | `dev/plan-implementation.md` | STALE | `references:` 필드 미존재 파일 2개 + 존재하지 않는 `design-database` 에이전트로 위임 서술 |
| 15 | `dev/plan-refactor.md` | OK | 읽기전용 계약·위임 체인 정상 |
| 16 | `dev/research-external.md` | OK | MCP/빌트인 분리 서술이 현재 규율과 일치 |
| 17 | `dev/review-code.md` | STALE | `references:` 필드가 가리키는 파일 2개 전부 미존재(본문에 내용은 인라인으로 존재) |
| 18 | `dev/security-scan.md` | OK | 위임 체인·심각도 분류 정상 |
| 19 | `dev/sync-docs.md` | UNABSTRACTED | Worktree 복귀 프로토콜 중복 |
| 20 | `dev/verify-code.md` | OK | 시간 제약·위임 체인 정상 |
| 21 | `dev/verify-integration.md` | CONFLICT | `tools:`에 실재하지 않는 도구 `LSP` 등재 |
| 22 | `dev/write-tests.md` | UNABSTRACTED | Worktree 복귀 프로토콜 중복 |
| 23 | `meta/consensus-builder.md` | CONFLICT | "듀얼 모드 지원(W-032)" 절이 이미 레거시로 재규정된 Agent Teams를 상시 대안으로 서술 |
| 24 | `meta/devils-advocate.md` | CONFLICT | 상동(듀얼 모드 호환성 표) |
| 25 | `meta/facilitator-teams.md` | CONFLICT | 파일 전체가 폐기 예정(D-7) 시스템(`spawnTeam`/`message`/`broadcast`) 위에 설계 + 존재하지 않는 `explore-infrastructure` 에이전트 참조 |
| 26 | `meta/facilitator.md` | CONFLICT | CALC-001 점수식으로 Agent Teams를 자동 선택 모드처럼 서술 + 존재하지 않는 `design-database` 참조 |
| 27 | `meta/impact-analyzer.md` | CONFLICT | 존재하지 않는 `design-database` 에이전트를 선행 작업으로 명시 |
| 28 | `meta/synthesizer.md` | CONFLICT | 듀얼 모드 호환성 절 + 존재하지 않는 `design-database` 참조 |
| 29 | `planning/analyze-domain.md` | OK | tier2 B 등급과 본문(WebSearch/WebFetch 비결정성) 일치 |
| 30 | `planning/clarify-requirements.md` | CONFLICT | 존재하지 않는 `Infra/plan-infrastructure` 에이전트·도메인으로 위임 서술 |
| 31 | `planning/define-business-logic.md` | CONFLICT | `tools: Write` + 고정 파일 저장 경로 명시(문서 산출물)인데 `isolation: worktree` 없음 |
| 32 | `planning/define-metrics.md` | OK | 읽기전용, 위임 없음(설계상 정상) |
| 33 | `planning/design-user-journey.md` | CONFLICT | define-business-logic와 동일한 isolation 누락 패턴 |

**집계**: OK 10 · UNABSTRACTED 6 · STALE 4 · CONFLICT 13 · DUP 0 · ORPHAN 0 · UNKNOWN 0 = **33**

---

## 2. 발견 상세

### 2.1 STALE

**[analyze-tech-debt.md:95]** — 예시 리포트 템플릿에 `대상: claude_setting`이라는, 이 레포(`claude-code-kit`)와 무관한 프로젝트명이 하드코딩돼 있다.
- 왜 문제: 이 킷은 "설치되는 프로젝트마다 다른" 범용 플러그인이다(CLAUDE.md 북극성). 예시 값 자체는 플레이스홀더로 봐줄 수 있으나, 실제 프로젝트명이 아닌 낯선 고유명사가 박혀 있으면 다른 코드베이스에서 복붙된 잔재로 읽힌다.
- 무엇과 충돌: CLAUDE.md "Consumer-first" 원칙(설치 환경에 결합된 값을 남기지 않는다).
- 권고: **축약** — `claude_setting`을 `[프로젝트명]` 같은 진짜 플레이스홀더로 교체.

**[implement-code.md:21-27, :115]** — frontmatter `references:` 필드가 `references/patterns.md`, `references/code-quality.md`, `references/examples.md`를 가리키지만 세 파일 모두 실존하지 않는다(`find plugins/common/agents -type d -iname references` 결과 0건, §4). 본문에는 해당 내용이 "## Reference: ..." 섹션으로 이미 인라인 복제돼 있다. 또한 라인 115의 SSOT 주석 `<!-- 참조 위치: agents/common/dev/implement-code/implement-code.md#L169-188 -->`는 실제 경로(`plugins/common/agents/dev/implement-code.md`)와 다르고, 자신을 디렉토리인 것처럼 가리키는 구조 자체도 틀렸다(리포지토리에 `agents/common/...` 경로는 존재하지 않는다 — 실제 계층은 `plugins/common/agents/...`).
- 무엇과 충돌: `references:` 필드가 실제로 아무것도 로드하지 않아 frontmatter의 선언과 실물이 어긋난다("약속과 실물의 일치" — hiway 설계 문서 §0 판단 기준 1과 같은 클래스의 결함).
- 권고: **삭제** — `references:` 필드 제거(내용이 이미 본문에 있어 기능 손실 없음), SSOT 주석의 경로를 현재 실제 경로로 정정하거나 라인 범위 대신 섹션 제목으로 참조.

**[manage-api-versions.md:54-61, :159-176]** — "3. 에이전트 버전"에서 `agents/**/index.json`을 데이터 소스로, "에이전트 버전 관리"에서 frontmatter `version:` 필드를 관리 대상으로 서술한다. 그러나 33개 스코프 파일 어디에도 `version:` 필드가 없고(`grep -rln '^version:' plugins/common/agents/` → 0건, §4), `index.json`도 레포 전체에 존재하지 않는다. CLAUDE.md는 명시적으로 "매니페스트에 에이전트/스킬 레지스트리가 없다 — 디렉토리에서 자동 발견"이라고 선언한다.
- 무엇과 충돌: CLAUDE.md "Adding a New Agent" 절("No manifest edit needed... plugin.json has no agent/skill registry").
- 권고: **축약** — 에이전트 버전 관리 절 전체 삭제 또는 "현재 이 킷은 에이전트별 버전을 관리하지 않는다"로 명시.

**[plan-implementation.md:19-23, :97]** — `references:` 필드가 `references/templates.md`, `references/risk-analysis.md`를 가리키나 미존재(implement-code.md와 동일 패턴). 라인 97에서 "(DB 변경) → design-database"로 위임하지만 `design-database` 에이전트는 33개 스코프에도, 스코프 밖 전체 검색(`find . -iname "design-database*"`)에도 존재하지 않는다(§4).
- 무엇과 충돌: 존재하지 않는 위임 대상은 실행 시점에 사용자를 막다른 곳으로 보낸다.
- 권고: **삭제** — references 필드 제거. `design-database` 위임 줄은 삭제하거나 "DB 스키마 변경도 plan-implementation 자체가 포함"으로 수정.

**[review-code.md:19-23]** — `references:`가 `references/checklist.md`, `references/anti-patterns.md`를 가리키나 미존재(본문에 "## Reference: 리뷰 체크리스트"·"## Reference: 안티패턴"으로 이미 인라인).
- 권고: **삭제** — references 필드 제거.

### 2.2 CONFLICT

**[enforce-structure.md:31, :47, :198-203]** — "참조 파일(반드시 읽기)"로 `project-structure.yaml`을 지정하고 1단계 프로세스의 첫 항목으로 "project-structure.yaml 읽기"를 명시한다. 그러나 이 파일은 리포지토리 어디에도 존재하지 않으며(`find . -iname "project-structure.yaml"` → eval 픽스처 1건뿐, §4), 이 킷이 사용자에게 이런 파일을 만들라고 안내하는 스킬·문서도 없다. "Hook 연동" 절은 `governance-check.py`와의 연동을 서술하지만 그런 훅은 `plugins/common/hooks/`(hooks.json 목록: session-check, session-start, protect-sensitive, auto-format, stop-validator)에 없다(§4).
- 왜 문제: 이 에이전트의 1단계 자체가 "존재하지 않는 필수 입력을 읽는다"로 시작한다. 파일이 없으면 에이전트가 규칙 자체를 확인할 수 없는 상태로 진행하게 된다.
- 무엇과 충돌: CLAUDE.md 북극성 "Consumer-first"("설치하는 사람의 환경에서 동작해야 한다") — 이 에이전트는 이 리포에도 없는 파일 컨벤션을 전제한다.
- 권고: **축약** — "있으면 읽고, 없으면 CLAUDE.md/일반 컨벤션(src 레이아웃, 파일 네이밍)으로 대체 판단"으로 완화. Hook 연동 절은 실재하지 않으므로 삭제하거나 향후 계획으로 명시.

**[generate-boilerplate.md:44-46]** — "에이전트 템플릿" 블록에 다음이 그대로 남아 있다:
```
MUST USE when: 다른 에이전트가 "DELEGATE_TO: {{name}}" 반환 시.
OUTPUT: {{output}} + "DELEGATE_TO: [{{next_agents}}]" 또는 "TASK_COMPLETE"
```
CLAUDE.md의 "Delegation Signal — 폐기됨(2026-08-27, W-022 R1)" 절은 정확히 이 형태(OUTPUT에 박힌 `DELEGATE_TO:`/`TASK_COMPLETE` 토큰)를 "기계 계약"으로 규정하고 33종 에이전트 정의에서 전부 제거했다고 기록한다. 같은 절은 "`agent-creator`는 특히 중요했다: 새 에이전트 템플릿에 블록이 박혀 있어 폐기를 무효화할 수 있었다"고 명시하는데, **`generate-boilerplate.md` 자신도 새 에이전트를 찍어내는 템플릿 소유 에이전트이면서 정리 대상에서 빠졌다.**
- 왜 문제: 이 에이전트가 호출되어 새 에이전트를 생성할 때마다, 이미 폐기된 신호 계약이 새 에이전트에 재주입된다 — 폐기가 "무효화"되는 정확한 경로.
- 무엇과 충돌: CLAUDE.md "Delegation Signal — 폐기됨" 절, "어디까지 걷어냈나" 목록(스킬 4종은 정리됐다고 기록하지만 이 에이전트는 스킬이 아니라 목록 밖에 있었다).
- 권고: **삭제** — 두 줄을 프로젝트의 현재 서술 관례(산문 `DELEGATE_TO: X` 에스컬레이션 서술 + 실제 산출물 설명)로 교체.

**[verify-integration.md:14]** — `tools:` allowlist에 `LSP`가 있다. Claude Code 네이티브 도구 목록(Read/Write/Edit/Bash/Glob/Grep/WebFetch/WebSearch/Task/NotebookEdit/AskUserQuestion/ExitWorktree 등)에 `LSP`라는 도구는 없고, 레포 전체에서 이 문자열이 다른 어떤 에이전트나 스킬에서도 도구로 언급되지 않는다(`grep -rn "LSP" plugins/common/agents/ plugins/common/skills/` → 이 파일 1건뿐, §4).
- 왜 문제: CLAUDE.md의 `mcp__*` 금지 규칙과 같은 클래스의 결함이다 — allowlist에 존재하지 않는 도구를 넣으면 "미설치 소비자에게 환각/실패를 유발"하는 것과 동일한 메커니즘으로, 이 경우는 도구 자체가 애초에 존재하지 않는다.
- 무엇과 충돌: Contributing 체크리스트 "No `mcp__*` tools in any agent `tools:` allowlist" 뒤에 깔린 원칙(존재하지 않는/불확실한 도구를 allowlist에 넣지 않는다)과 같은 취지.
- 권고: **삭제** — `LSP` 항목 제거. 본문의 "LSP 활용" 절이 의도하는 기능(정의로 이동/참조 찾기)은 현재 `Grep`/`Glob`으로 대체 서술되어 있으므로 도구 목록에서만 빼면 된다.

**[consensus-builder.md:483-507] / [devils-advocate.md:450-457] / [synthesizer.md:418-442] / [facilitator.md:312-346] / [facilitator-teams.md 전체]** — 5개 메타 에이전트 모두 "듀얼 모드 지원(W-032)" 절에서 **Agent Teams 모드**(`spawnTeam()`, Lead/Teammate, `message`/`broadcast` 툴)를 지금도 선택 가능한 정상 실행 경로로 서술한다. `facilitator.md:321-327`은 "모드 자동 선택(CALC-001)" 점수식("점수 >= 9 → Agent Teams 모드")까지 제시해 이것이 상시 자동 분기되는 것처럼 보이게 한다.

그러나 실측 결과 이는 현재 SSOT와 어긋난다:
1. `plugins/common/skills/agent-teams/SKILL.md`(현재 버전) 자체가 "Large-scale parallel work guidance. Routes 10+ parallel independent tasks to native dynamic workflows (ultracode), **with legacy experimental Agent Teams as fallback**"이라고 스스로를 재규정했고 본문에 "실험적 자체 Agent Teams 조율은 네이티브가 흡수했으며"라고 명시한다(§4).
2. CLAUDE.md "Orchestration Model" 절: "실험적 자체 조율(구 agent-teams)은 이 네이티브 경로로 대체됐다"(과거형, 이미 대체됨).
3. `spawnTeam`/`message`/`broadcast`는 레포 전체에서 이 5개 메타 에이전트 파일과 `multi-perspective-review/SKILL.md`에서만 나타나며(§4), Claude Code의 네이티브 도구가 아니다.
4. 정렬 대상 설계 문서(D-7)는 "`agent-teams`는 흡수 후 폐기(기한 있는 2단계)"를 이미 결정했고 v2.18.0에 "본문을 폐기 예고로 교체"·v3.0.0에 "완전 제거"를 명시한다.

- 왜 문제: 5개 메타 에이전트 정의는 이미 legacy/폴백으로 재규정된 시스템을 여전히 "정상 작동하는 1급 병렬 모드"처럼 서술한다. 사용자가 이 문서만 읽으면 Agent Teams가 지금도 자동 선택되는 활성 경로라고 오인한다.
- 무엇과 충돌: 위 1~4 (agent-teams/SKILL.md 현재 서술, CLAUDE.md Orchestration Model, D-7).
- 권고: **이동/축약** — 5개 파일의 "듀얼 모드 지원" 절을 "Agent Teams는 레거시 폴백이며 기본 경로는 `ultracode`"로 재작성하거나, D-7의 v2.18.0 단계에 맞춰 통째로 삭제 예고 각주만 남긴다. **역사 기록이 아니라 현재를 서술하는 문장**이므로 §5 보존 원칙의 예외에 해당하지 않는다(현재 시제로 "이 파일은 변경 없이 유지됩니다" 같은 문장까지 있어 활성 서술로 판정).

**[facilitator-teams.md:243]** — 관점-에이전트 매핑 표에서 "Deployment | explore-infrastructure"로 위임하지만 `explore-infrastructure` 에이전트는 33개 스코프에도, 전체 레포에도 존재하지 않는다(§4).
- 권고: **삭제** — 해당 행 제거 또는 "Infra 도메인이 생기면 추가" 각주로 대체.

**[facilitator.md:81, :259] / [impact-analyzer.md:476] / [synthesizer.md:347] / [plan-implementation.md:97]** — 4개 파일이 공통적으로 `design-database`라는 에이전트로 위임/선행작업을 지정하지만, 이 에이전트는 33개 스코프는 물론 레포 전체 어디에도 존재하지 않는다(`find . -iname "design-database*"` → 0건, §4). Backend/Dev 도메인에 DB 스키마 설계를 전담하는 에이전트가 아예 없다.
- 왜 문제: 4개 파일이 동일한 phantom 에이전트를 서로 다른 위치에서 참조 — 우연이 아니라 "DB 스키마 설계 에이전트가 있어야 한다"는 암묵적 합의가 문서에만 있고 구현이 빠진 상태.
- 무엇과 충돌: 위임 체인의 종착점이 없다는 점에서 D-9("4블록 브리프는... 워커가 완료 조건을 몰라 에스컬레이션한다")의 취지와 반대로, 존재하지 않는 대상에게 "위임됨"으로 문서가 조용히 끝난다.
- 권고: **신설 필요(새 결정 후보, §3 참고)** 또는 4개 파일 모두에서 해당 위임 줄을 제거하고 "DB 스키마는 plan-implementation/design-services 범위에 포함"으로 정정.

**[clarify-requirements.md:298-299, :309]** — "인프라 관련 → Infra/plan-infrastructure"로 위임하지만 `Infra` 도메인 자체가 33개 스코프(backend/dev/meta/planning 4개 도메인만 존재)에도 레포 전체에도 없다.
- 권고: **삭제** — 해당 행 제거, 또는 "인프라 도메인은 아직 없음, dev/plan-implementation으로 통합"으로 정정.

**[define-business-logic.md:1-20, :469-476] / [design-user-journey.md:1-20, :370-377]** — 두 파일 모두 `tools:`에 `Write`가 있고 본문에 각각 `docs/planning/business-logic/[도메인명]-rules.md`, `docs/planning/user-journeys/[기능명]-journey.md`라는 고정 파일 저장 경로를 명시한다(즉 실제로 리포지토리에 파일을 쓴다). 그러나 두 파일 모두 frontmatter에 `isolation: worktree`가 없다(`grep -n "^isolation"` → 0건, §4).
- 왜 문제: CLAUDE.md "isolation: worktree" 절은 "파일을 **수정**하는 에이전트"에 적용하라고 하며, 예시로 든 대상 목록에 문서만 쓰는 `sync-docs`도 포함돼 있다(sync-docs는 `tools: Write`+`isolation: worktree`). 같은 기준을 적용하면 define-business-logic·design-user-journey도 대상이어야 하는데 빠져 있다. 병렬 dispatch 중 이 두 에이전트가 다른 file-mutating 에이전트와 동시에 실행되면, 검증 없이 메인 워크스페이스에 직접 문서를 쓰는 유일한 두 예외가 된다.
- 무엇과 충돌: CLAUDE.md "Adding a New Agent" 체크리스트("File-modifying agents have isolation: worktree")·`rules/parallel-worktree.md`("ALWAYS: 소스 파일을 수정하는 에이전트는 frontmatter isolation: worktree").
- 권고: **신설 필요(새 결정 후보, §3 참고)** — Planning 산출물(`docs/planning/**`)이 병렬-worktree 규칙의 "소스 파일"에 해당하는지 자체가 D-1~D-21 어디에도 명시돼 있지 않다. 컨트롤 세션의 판단이 필요.

### 2.3 UNABSTRACTED

**[implement-api.md:139-146] [optimize-logic.md:171-178] [write-api-tests.md:227-234] [fix-bugs.md:335-342] [write-tests.md:268-275] [sync-docs.md:280-287]** (+ 참고: `implement-code.md:441-448`, `generate-boilerplate.md:279-286`는 각각 STALE/CONFLICT로 이미 분류됐지만 동일 중복을 포함) — 8개 파일 전부가 다음 4줄을 **글자 그대로 동일하게** 포함한다:

```
1. 작업 완료 후 worktree 안에서 검증(린트 + 관련 테스트)을 실행합니다.
2. **검증 그린일 때만** `ExitWorktree`를 호출해 변경을 복귀(병합)시킵니다 — 레드 상태로 병합 금지.
3. 병합 충돌 시 임의로 ours/theirs를 선택하지 않습니다 — `DELEGATE_TO: git-workflow`로 위임해...
4. worktree 안에서 `docs/works/**`(progress, feedback ledger)를 갱신하지 않습니다...
```

`plugins/common/rules/parallel-worktree.md`(§4에 본문 확인)가 이미 "진입"·"복귀"·"충돌 에스컬레이션"·"공유 상태 파일" 4개 절로 **동일한 규범을 원문으로 갖고 있고**, 각 에이전트는 이미 "규칙: `rules/parallel-worktree.md`"라는 한 줄 포인터도 갖고 있다. 그런데도 4단계 전문을 매번 다시 박아 넣는다 — SSOT(규칙 파일)가 있는데 참조 대신 복제를 택한 상태.
- 왜 문제: `rules/parallel-worktree.md`가 바뀌면(예: 충돌 에스컬레이션 절차 변경) 8개 파일을 전부 수동으로 맞춰야 한다. CLAUDE.md 자신이 규칙 파일과 해설본 간에 이런 드리프트를 겪었다고 기록한다("Rules have a long-form mirror — and it is checksum-guarded" 절).
- 무엇과 충돌: 없음(모순은 아님) — 다만 SSOT 원칙("생성물은 SSOT에서 파생한다", hiway 설계 §0 판단 기준 2) 위반.
- 권고: **추상화** — 8개 파일의 4줄을 "복귀 절차는 `rules/parallel-worktree.md`를 따른다(진입/복귀/충돌 에스컬레이션/공유 상태 파일)" 한 줄로 축약하고, 원문은 규칙 파일에만 둔다. 이미 CHECKSUMS.sha256로 규칙 파일 드리프트를 감시하는 인프라(`docs/architecture/rules/MIRROR.sha256`, `verify-done.sh §7`)가 있으므로 같은 패턴을 여기 재사용할 수 있다.

**참고(추상화 후보 아님)**: `다음 단계 위임` 절은 15개 파일에 나타나지만(`grep -c` 결과) 각 파일의 위임 대상·조건이 서로 다른 실질 콘텐츠라서 이건 **구조적 패턴의 반복**이지 내용 중복이 아니다 — 추상화 권고 대상에서 제외한다.

---

## 3. 계획 정렬 (D-1~D-21 대조)

design doc는 W-025~W-027(하네스 중립 전환) 배치를 다루며, T2에서 발견한 이슈 다수는 **이 배치의 범위 밖**이다(하네스 이식성이 아니라 에이전트 정의 자체의 정합성 문제이기 때문). 매핑 결과:

| 발견 | 대응 결정 | 판정 |
|------|-----------|------|
| Agent Teams 듀얼 모드 서술 잔존 (5개 메타 에이전트) | **D-7**(agent-teams 흡수 후 폐기, 2단계) | **흡수됨** — D-7이 스킬 폐기 시점(v2.18.0/v3.0.0)을 이미 계획했다. 다만 D-7 원문은 `agent-teams` **스킬**만 언급하고 5개 메타 **에이전트 파일**의 "듀얼 모드 지원" 절은 명시하지 않는다. **컨트롤 세션에 전달할 보정**: W-026(26-3, agent-teams 폐기 예고 교체) 작업 항목에 "5개 메타 에이전트의 듀얼 모드 절도 같은 배치에서 정리"를 추가하지 않으면, 스킬만 폐기되고 에이전트 정의는 죽은 참조로 남는다. |
| `references:` 필드 dangling (implement-code, plan-implementation, review-code) | 없음 | **새 결정 필요**. §8 구조 감사(D-12~D-16)는 스크립트/평가 인프라의 추상화만 다루고 에이전트 frontmatter의 `references:` 필드는 대상이 아니다. 제안: "에이전트 frontmatter의 `references:` 필드는 실재 파일만 가리켜야 하며, 내용이 본문에 이미 인라인돼 있으면 필드 자체를 제거한다"는 1문장 결정이 필요하다. |
| `design-database`/`explore-infrastructure`/`Infra 도메인`/`plan-infrastructure` phantom 위임 대상 (4+ 파일) | 없음 | **새 결정 필요**. 제안: "존재하지 않는 에이전트/도메인으로의 위임 서술은 금지하며, 향후 계획이면 '(미구현)' 각주를 명시한다"는 문서 정합성 규칙이 필요하다. 이 킷의 33개 에이전트가 SSOT(자동 발견 디렉토리)라는 CLAUDE.md 원칙과 직접 연결된다. |
| `generate-boilerplate.md`의 폐기된 DELEGATE_TO 템플릿 잔존 | CLAUDE.md "Delegation Signal — 폐기됨" 절(과거 결정, 2026-08-27) | **미완료 실행** — 이미 내려진 결정이 이 한 파일에서 누락됐을 뿐, 새 결정은 필요 없다. 컨트롤 세션이 CLAUDE.md의 "어디까지 걷어냈나" 목록에 `generate-boilerplate.md`를 추가하고 즉시 제거만 하면 된다. |
| `project-structure.yaml`/`governance-check.py` 미존재 의존 (enforce-structure 등) | 없음(design doc 범위 밖) | **새 결정 필요**. hiway 설계 문서 §0 판단 기준 3("소비자 우선")과 직접 연관되지만, W-025~027 어느 항목도 이를 다루지 않는다. 제안: "이 킷이 전제하는 프로젝트 컨벤션 파일(project-structure.yaml 등)은 실존 여부를 코드로 확인 후 없으면 우아하게 폴백한다"로 enforce-structure를 개정하는 결정이 필요. |
| `define-business-logic`/`design-user-journey`의 isolation 누락 | 없음 | **새 결정 필요**. `rules/parallel-worktree.md`의 "소스 파일을 수정하는 에이전트" 정의에 `docs/planning/**` 같은 Planning 산출물이 포함되는지 명시가 없다. §9(D-17~D-21, 주입 예산)는 `parallel-worktree`를 **conditional 티어**로 재분류하는 안(D-21)까지 다루지만 "무엇이 대상 에이전트인가"는 건드리지 않는다. |
| `LSP` 존재하지 않는 도구 (verify-integration) | 없음 | **새 결정 필요는 아님, 단순 수정 항목**. Contributing 체크리스트의 "존재하지 않는 도구를 allowlist에 넣지 않는다" 정신을 명문화한 항목이 없어 발생했다 — `mcp__*` 규칙처럼 "실재하지 않는 임의 문자열 도구명 금지"로 체크리스트 문구를 넓히는 것을 권고하나, 이는 이 배치의 스코프가 아니라 별도 후속 과제로 남긴다. |
| Worktree 복귀 프로토콜 8개 파일 중복 | 없음 | **새 결정 필요는 아님** — hiway 설계 §8(D-12~D-16)이 이미 "레포 내부 모듈 간 import 0건... 데이터 주도 확장 지점 1곳"을 최대 강점으로 평가하고 중복을 규약으로 줄이는 패턴(D-15)을 쓴다. 같은 정신을 에이전트 본문에도 적용하면 되므로, 신규 결정보다는 **D-15 패턴의 재사용 사례**로 처리 가능. 컨트롤 세션 판단만 있으면 됨(코드 변경 없이 각 에이전트 4줄 → 1줄 축약). |
| consensus-builder eval 시나리오 부재 | **D-8**(control-loop C등급 등재 원칙과 동일 클래스의 선례) | **완전 해소됨(참고용 기록)** — 이 문제는 이미 W-024(2026-09-04, `origin/main` c707729 계열)에서 발견·수정됐다. `evals/policy.json`(origin/main판) 자신이 "이 회계는 **거짓이었다**"라고 기록하며 `check_tier2`/`check_classification_complete` 게이트 신설과 `consensus-builder/hard-constraint-standoff` 시나리오 신설로 해소했다(§4). 이 워크트리가 그 커밋들보다 뒤처져 있어 로컬 파일에서는 갭이 보이지만, **현재 SSOT에는 없는 갭**이다. D-8이 "이것이 consensus-builder 사고의 재발 방지"라고 명시한 바로 그 사고였다. |

---

## 4. 실측 로그

```bash
# 워크트리 위치·상태
$ git status && git log -1 --oneline
# → clean, HEAD dd63b44 (fix(ci): gitleaks ...)

# design doc 부재 확인 → origin/main에서 발견
$ ls docs/specs/2026-09-07-hiway-program-design.md          # No such file
$ git log --all --oneline -- "docs/specs/2026-09-07-hiway-program-design.md"
# → c707729 / fe0806c / c84ab28 (origin/main 계열)

$ git branch -a --contains c707729                            # +This-HW/planning-control-session, remotes/origin/main
$ git merge-base --is-ancestor dd63b44 origin/main && echo YES # YES (내 HEAD가 origin/main의 조상)
$ git log --oneline dd63b44..origin/main | wc -l               # 11 commits behind

# 스코프 33개 파일이 origin/main과 바이트 단위로 동일한지 전수 검증
$ while read f; do
    git show "origin/main:$f" > /tmp/o.md 2>/tmp/o.err
    [ -s /tmp/o.err ] && echo "MISSING_ORIGIN: $f"
    diff -q /tmp/o.md "$f" >/dev/null || echo "DIFF: $f"
  done < scope33.txt
# → 출력 없음 (33개 전부 동일)
$ git diff --stat dd63b44..origin/main -- plugins/common/agents/
# → 빈 출력 (agents/ 트리 전체가 두 지점 사이 무변경)

# design doc 본문 확보 (브랜치 전환 없이)
$ git show origin/main:docs/specs/2026-09-07-hiway-program-design.md > hiway-design.md   # 792 lines

# evals/policy.json, scripts/check_eval_coverage.py는 origin/main과 실제로 다름을 확인
$ diff <(git show origin/main:evals/policy.json) evals/policy.json | head
# → tier2 관련 항목 다수 상이 (W-024 반영 여부 차이, 상세는 본문 §3 표 참고)
$ diff <(git show origin/main:scripts/check_eval_coverage.py) scripts/check_eval_coverage.py
# → docstring 1줄 상이 (tier2 경고 문구 유무)

# consensus-builder eval 시나리오 부재 → origin/main엔 이미 존재 확인
$ ls evals/scenarios/ | grep consensus          # (로컬: 없음)
$ git ls-tree -r --name-only origin/main -- evals/scenarios/ | grep -i consensus
# → evals/scenarios/consensus-builder/hard-constraint-standoff/{expect.json,fixture/round1-synthesis.md,task.md}
$ grep -n "check_classification_complete" scripts/check_eval_coverage.py   # 로컬: 0건
$ for f in $(git ls-tree -r --name-only origin/main -- scripts/ evals/); do
    git show "origin/main:$f" | grep -q check_classification_complete && echo "FOUND: $f"
  done
# → evals/policy.json, scripts/check_eval_coverage.py, scripts/tests/test_eval_coverage.py

# reference/ 디렉토리 실재 여부
$ find plugins/common/agents -type d -iname "references"    # → 0건

# claude_setting 잔재
$ grep -rn "claude_setting" plugins/                          # → analyze-tech-debt.md:95

# governance-check.py / project-structure.yaml 실재 여부
$ find . -iname "governance-check.py"                         # → 0건
$ find . -iname "project-structure.yaml"                      # → evals/scenarios/enforce-structure/misplaced-source/fixture/ 1건뿐(픽스처)

# 존재하지 않는 위임 대상 에이전트
$ find . -iname "design-database*"                             # → 0건
$ grep -rln "design-database" plugins/common/agents/           # → facilitator.md, synthesizer.md, impact-analyzer.md, plan-implementation.md
$ find . -iname "explore-infrastructure*"                      # → 0건
$ grep -rln "explore-infrastructure" plugins/common/agents/     # → facilitator-teams.md
$ find . -iname "plan-infrastructure*"                          # → 0건
$ grep -rln "plan-infrastructure" plugins/common/agents/         # → clarify-requirements.md

# LSP 도구 실재 여부
$ grep -rn "LSP" plugins/common/agents/ plugins/common/skills/ | grep -v verify-integration.md
# → 0건 (verify-integration.md 단독 사용)

# Agent Teams 잔존 폭 확인
$ grep -rln "spawnTeam" plugins/common/
# → plugins/common/agents/meta/facilitator-teams.md, plugins/common/skills/multi-perspective-review/SKILL.md
$ sed -n '1,15p' plugins/common/skills/agent-teams/SKILL.md
# → description: "...legacy experimental Agent Teams as fallback."
$ grep -n "실험적 자체 조율" CLAUDE.md
# → 252: "...실험적 자체 조율(구 agent-teams)은..." (과거형, 대체됨)

# 에이전트 버전 필드/레지스트리 실재 여부
$ grep -rln "^version:" plugins/common/agents/                  # → 0건(실제 frontmatter 아님, manage-api-versions.md는 예시 코드블록 안에서만 등장)
$ find plugins/common/agents -iname "index.json"                 # → 0건

# 33개 = 전체 에이전트 수 확인 (스코프 밖 잔여 없음)
$ find plugins/common/agents -name "*.md" | wc -l                # → 33

# isolation 누락 확인
$ grep -n "^isolation" plugins/common/agents/planning/define-business-logic.md \
                        plugins/common/agents/planning/design-user-journey.md \
                        plugins/common/agents/meta/facilitator.md \
                        plugins/common/agents/meta/synthesizer.md
# → 0건 (4개 파일 모두 isolation 필드 없음; 이 중 Write+고정 파일경로가 있는 2개만 CONFLICT로 판정)

# Worktree 복귀 프로토콜 중복 스코프
$ grep -rl "Worktree 복귀 프로토콜 (isolation: worktree)" plugins/common/agents/ | wc -l   # → 8
# 다음 단계 위임 절 등장 빈도 (구조 반복이지 내용 중복 아님 — 참고용)
$ grep -rl "^## 다음 단계 위임" plugins/common/agents/ | wc -l                              # → 15

# rules/parallel-worktree.md가 SSOT로 이미 같은 내용을 갖고 있는지 확인
$ sed -n '1,60p' plugins/common/rules/parallel-worktree.md
# → "진입(Isolation)"/"복귀(ExitWorktree)"/"충돌 에스컬레이션"/"공유 상태 파일" 4절, 8개 파일 위임 대상 목록과 이름까지 일치

# eval tier 분류 완전성 (policy.json, origin/main 최신판 기준) 대조 — 33개 전부 tier1/tier2 A/B/C 어딘가에 등재됨을 수기 대조로 확인, 미분류 0건
```
