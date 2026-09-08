# T3 — 스킬 축 전수 문서 감사

> 워커: census-T3 (읽기 전용). 스코프 34개 파일 전수 확인.
> 정렬 대상: `docs/specs/2026-09-07-hiway-program-design.md`(D-1~D-21) — **주의**: 이 워크트리의
> 로컬 브랜치는 `main`(`c707729`)에서 생성되지 않고 그보다 오래된 `dd63b44`에서 분기돼 있어,
> 워크트리 안에 해당 스펙 파일이 실존하지 않는다(§4 실측 로그 참조). `git show origin/main:...`로
> 읽기 전용 추출해 대조했다 — 커밋·체크아웃·브랜치 조작 없음.

---

## 1. 커버리지 표 (34/34)

| 파일 | 판정 | 한 줄 근거 |
| --- | --- | --- |
| `plugins/common/skills/README.md` | **CONFLICT** | 제목은 "plan-task 스킬"인데 내용이 실제 `plan-task/SKILL.md`(Step 0-4 모델)와 다른 구식 5-Phase 모델을 서술하고, 존재하지 않는 경로(`.claude/rules/`, `skills/common/`)와 실제와 다른 W-023을 인용 |
| `plugins/common/skills/agent-creator/SKILL.md` | **CONFLICT** | 존재하지 않는 `plugin.json`의 `agents` 필드 등록을 지시하고, CLAUDE.md가 명시적으로 금지한 `permissionMode` 필드 추가를 가르치며, 예제 템플릿에 필수 필드 `maxTurns`가 없음 |
| `plugins/common/skills/agent-teams/SKILL.md` | OK | `docs/native-absorption.md`의 `superseded` 판정과 정합, D-7 1단계(폐기 예고 교체) 대상이나 현재 내용 자체는 정확 |
| `plugins/common/skills/auto-dev/SKILL.md` | OK | Step 구조·병렬 dispatch·durable executor 규율이 CLAUDE.md 오케스트레이션 모델과 정합, 최신 spec(W-006/007/009/013) 참조 일치 |
| `plugins/common/skills/brainstorming/SKILL.md` | OK | task-tools-fallback SSOT 참조·HARD-GATE 구조 일관 |
| `plugins/common/skills/debug/SKILL.md` | OK | 4-Phase 파이프라인, 실제 존재하는 에이전트(diagnose/fix-bugs/verify-code)만 참조 |
| `plugins/common/skills/doc-coauthoring/SKILL.md` | OK | 범용 문서 작성 가이드, 특정 MCP·플러그인 가정 없음 |
| `plugins/common/skills/eval-forge/SKILL.md` | OK | evals 하네스 세부와 정합(픽스처 금지 규칙 등), kit 레포 전용임을 명시 |
| `plugins/common/skills/harness-export/SKILL.md` | OK | AGENTS.md 마커 계약·불변식이 상세하고 실제 `verify-done.sh §11`과 일치 |
| `plugins/common/skills/mcp-builder/SKILL.md` | **CONFLICT** | `claude mcp restart`, `claude mcp status`는 실존하지 않는 하위 명령(`claude mcp --help`로 실측) |
| `plugins/common/skills/multi-perspective-review/SKILL.md` | **CONFLICT** | "Data/Schema" 관점의 관련 에이전트로 존재하지 않는 `design-database`를 지목 (실제 33개 에이전트에 없음) |
| `plugins/common/skills/multi-perspective-review/conflict-resolution.md` | OK | `SKILL.md`가 상대경로로 실제 참조하는 활성 사본 |
| `plugins/common/skills/multi-perspective-review/deliberation-pattern.md` | OK | 상동 |
| `plugins/common/skills/multi-perspective-review/examples.md` | OK | 상동 |
| `plugins/common/skills/multi-perspective-review/perspectives-guide.md` | OK | 상동 |
| `plugins/common/skills/native-watch/SKILL.md` | OK | `docs/native-absorption.md`를 SSOT로 참조하는 절차가 그 문서의 실제 구조(상태 정의·갱신 규칙)와 일치 |
| `plugins/common/skills/plan-task/SKILL.md` | OK | 현재의 Step 0-4 + Task 시스템 통합 모델, 참고문서 경로(`references/work-system.md`) 실존 |
| `plugins/common/skills/references/available-tools.md` | **ORPHAN** | 어떤 SKILL.md·에이전트도 참조하지 않음(전수 grep 0건), 2026-03-15 이후 미변경 |
| `plugins/common/skills/references/conflict-resolution.md` | **DUP** | `multi-perspective-review/conflict-resolution.md`와 바이트 단위 동일, 자신을 향한 참조는 0건 |
| `plugins/common/skills/references/deliberation-pattern.md` | **DUP** | `multi-perspective-review/deliberation-pattern.md`와 바이트 단위 동일, 참조 0건 |
| `plugins/common/skills/references/examples.md` | **DUP** | `multi-perspective-review/examples.md`와 바이트 단위 동일, 참조 0건 |
| `plugins/common/skills/references/model-selection.md` | **ORPHAN** | 참조 0건. 내용도 `plan-infrastructure`·`deploy`·`monitor` 등 이 레포의 33개 에이전트에 없는 이름을 나열 — 존재한 적 없는 로드맵의 잔재로 보임 |
| `plugins/common/skills/references/perspectives-guide.md` | **DUP** | `multi-perspective-review/perspectives-guide.md`와 바이트 단위 동일, 참조 0건 |
| `plugins/common/skills/references/phase-guides.md` | **ORPHAN** | 참조 0건. `skills/README.md`와 같은 구식 5-Phase 모델을 서술(같은 세대의 잔재) |
| `plugins/common/skills/references/task-tools-fallback.md` | OK | `brainstorming`·`plan-task`·`auto-dev` 3곳이 "규율 SSOT"로 실제 인용, 2026-08-28 최신 갱신 |
| `plugins/common/skills/references/work-integration.md` | **ORPHAN** | 참조 0건(단, 내용은 auto-dev의 실제 동작과 대체로 정합 — 죽은 문서일 뿐 틀린 문서는 아님) |
| `plugins/common/skills/references/work-system.md` | **CONFLICT** | `plan-task`·`auto-dev`가 "상세/전체"로 실제로 링크하는 활성 문서이지만, 서술 모델(Phase 0-6, Planning 중 다관점 리뷰)이 현재 `plan-task/SKILL.md`(Step 0-4, 리뷰는 auto-dev Validation 단계)와 어긋남 |
| `plugins/common/skills/review/SKILL.md` | OK | ruff+review-code+security-scan 파이프라인, 2026-08-23 실측 교훈(Bash 없는 review-code 제약) 반영 |
| `plugins/common/skills/self-improve/SKILL.md` | OK | HARD-GATE·롤백 규율이 상세하고 스스로 정직한 한계를 명시 |
| `plugins/common/skills/skill-creator/SKILL.md` | **CONFLICT** | 존재하지 않는 `plugin.json`의 `skills` 필드 등록을 지시, 어떤 실제 SKILL.md도 쓰지 않는 `argument-hint`/`allowed-tools` 필드를 표준 템플릿으로 제시 |
| `plugins/common/skills/skill-forge/SKILL.md` | OK | 3조건 포징 임계, delegation-signal 잔재 없음, "다른 플러그인 존재 가정 금지" 명시 |
| `plugins/common/skills/test/SKILL.md` | OK | 프레임워크 자동 감지 + verify-code/fix-bugs 파이프라인, 특정 스택 가정 없음 |
| `plugins/common/skills/using-claude-code-kit/SKILL.md` | **CONFLICT** | "Skill Trigger Map"·"Agent Selection" 표가 하네스 시스템 프롬프트가 이미 제공하는 19개 스킬·33개 에이전트의 트리거를 재기술 — 설계 문서 D-18이 정확히 이 두 표의 제거를 명시 |
| `plugins/common/skills/web-research/SKILL.md` | OK | Context7/Exa/Tavily를 구체 예시로 들지만 "MCP 존재를 가정하지 마세요" 명시 + 폴백 규율 + CC #13898 근거 포함 |

**합계: 34행. OK 21 · CONFLICT 7 · ORPHAN 4 · DUP 4** (DUP 4는 ORPHAN이기도 하지만 "활성 사본의 정확한 중복"이라는 더 구체적인 성격을 우선 표기했다.)

---

## 2. 발견 상세

### F1. `plugins/common/skills/README.md` — 정체불명의 구식 문서 (CONFLICT)

- **무엇**: 파일명은 "skills 디렉토리의 README"를 기대하게 하지만 실제 제목(1행)은
  "# plan-task 스킬"이고, 전체가 `plan-task`의 (구식) 사용법 설명이다.
- **어디**:
  - `README.md:1` — 제목이 "plan-task 스킬"
  - `README.md:10-24` — "5단계 파이프라인"(Phase 0~5) 서술. 실제 `plan-task/SKILL.md`는
    Step 0(Work ID 확보) → Step 1(Task 초기화) → Step 2(T1 요구사항) → Step 3(T2 계획) →
    Step 4(완료 처리)의 **Task 기반 모델**이라 구조 자체가 다르다.
  - `README.md:310` — `.claude/rules/planning-protocol.md` 인용. 이 레포에 `.claude/rules/`는
    없다(rules는 `plugins/common/rules/`에 있다).
  - `README.md:311` — `skills/common/auto-dev/README.md` 인용. 최상위 `skills/` 디렉토리는
    이 레포에 없다(`plugins/common/skills/`만 있음).
  - `README.md:328` — "참조: W-023 (Anthropic 표준 채택)". 이 레포의 실제 W-023은
    (`CHANGELOG.md:13`, 최근 커밋 로그) eval 커버리지/git-workflow 시나리오 배치이며
    "Anthropic 표준 채택"이 아니다 — Work 번호 재사용/문서 이관 과정에서 다른 문맥의
    W-023을 그대로 인용한 것으로 보인다.
- **왜 문제인가**: 사람/에이전트가 "skills/README.md"를 스킬 디렉토리 색인으로 오인하고
  읽으면 존재하지 않는 경로·틀린 Work 참조·실제와 다른 파이프라인 구조를 근거로 판단하게
  된다. `git log`상 2026-03-15 최초 커밋(`4a06307`) 이후 **단 한 번도 수정되지 않았다**
  (§4 실측).
- **무엇과 충돌하는가**: `plugins/common/skills/plan-task/SKILL.md` 전체(구조·경로 불일치),
  CLAUDE.md의 실제 저장소 레이아웃(`plugins/common/`만 존재, `.claude/rules/` 없음).
- **권고**: **축약+재작성**. `README.md`는 유일하게 `agy plugin validate`의 "21 vs 19"
  카운트 설명(`README.md:71`, 루트)의 근거로 쓰이므로 **삭제보다 대체**를 권한다 —
  스킬 디렉토리의 실제 색인(19개 스킬 한 줄 목록)으로 내용을 교체하면 그 카운트 설명은
  그대로 유효하면서 오정보는 사라진다.

### F2. `plugins/common/skills/agent-creator/SKILL.md` — 존재하지 않는 계약을 가르침 (CONFLICT)

- **무엇**: 새 에이전트 생성 절차가 (a) 존재하지 않는 매니페스트 필드 등록을 지시하고
  (b) 금지된 frontmatter 필드를 표준 선택지로 제시하며 (c) 필수 필드를 예제에서 누락한다.
- **어디**:
  - `agent-creator/SKILL.md:22, 43-49` — "권한 모드 선택" 표(`default`/`acceptEdits`/`plan`)를
    frontmatter에 넣도록 유도.
  - `agent-creator/SKILL.md:70` — "`plugins/{domain}/.claude-plugin/plugin.json`의 `agents`
    필드에 등록" 지시.
  - `agent-creator/SKILL.md:26, 78` — `plugins/{domain}/agents/{category}/` 구조 전제.
    실제 레포는 `plugins/common/`뿐이고 `{domain}` 다중 플러그인 구조가 아니다
    (`ls plugins/` → `common` 1개).
  - `agent-creator/SKILL.md:88-112` — 예제(`test-runner`) frontmatter에 `maxTurns`가 없음.
- **왜 문제인가**:
  - CLAUDE.md Contributing 체크리스트: "No forbidden fields: `permissionMode`, ..." —
    `permissionMode`는 명시적으로 금지된 필드다. 실제 33개 에이전트 중 이 필드를 쓰는
    파일은 0건(`grep -rl permissionMode plugins/common/agents/` → 공백).
  - CLAUDE.md: "No manifest edit needed — agents are auto-discovered from the directory
    (plugin.json has no agent/skill registry)". 실제 `plugins/common/.claude-plugin/plugin.json`을
    읽으면 `agents`/`skills` 필드 자체가 없다(§4).
  - CLAUDE.md Contributing: "Agent frontmatter has `name`, `description`, `model`,
    `maxTurns`" — 필수 필드인데 예제가 누락. 실제 33개 에이전트는 전부 `maxTurns`를
    갖는다(`grep -rL maxTurns` 결과 0건 = 전수 보유).
  - `.claude/agents/`를 프로젝트-로컬 옵션으로 제시하면서(27행) `session-check.py`가
    경고 대상으로 삼는 "이중 로드" 위험을 언급하지 않는다.
- **무엇과 충돌하는가**: CLAUDE.md "Contributing" 체크리스트 전문, 실제
  `plugins/common/.claude-plugin/plugin.json`(agents/skills 필드 없음), 실제 33개 에이전트
  정의 파일 전수(permissionMode 0건, maxTurns 전수).
- **권고**: **축약+갱신**. 권한 모드 절 삭제, 매니페스트 등록 절 삭제(자동 발견 서술로
  교체), 예제에 필수 필드(`maxTurns`, `isolation: worktree` 대상 안내) 추가, 구조 설명을
  `plugins/common/agents/{category}/`로 교정. 2026-08-27 최근 수정본인데도 이 결함이
  남아 있어 — 이 스킬 자체가 재작성 시 CLAUDE.md Contributing 체크리스트와 대조되지 않았다는 뜻.

### F3. `plugins/common/skills/mcp-builder/SKILL.md` — 존재하지 않는 CLI 명령 (CONFLICT)

- **무엇**: "Claude Code 통합"·"디버깅" 절이 실존하지 않는 `claude mcp` 하위 명령을 예시로
  든다.
- **어디**: `mcp-builder/SKILL.md:134` (`claude mcp restart`), `mcp-builder/SKILL.md:223`
  (`claude mcp status myproject`).
- **왜 문제인가**: 이 세션에서 직접 `claude mcp --help`를 실행해 실제 하위 명령을 확인했다
  — `add`, `add-from-claude-desktop`, `add-json`, `get`, `help`, `list`, `login`, `logout`,
  `remove`, `reset-project-choices`, `serve` 뿐이다. `restart`·`status`는 없다. 이 스킬을
  따라 하는 사람은 존재하지 않는 명령을 실행하게 된다.
- **무엇과 충돌하는가**: 실제 `claude mcp --help` 출력(§4 실측 로그).
- **권고**: **수정**. `claude mcp restart` → 삭제(재시작 개념 자체가 없음, 서버 설정을
  `remove`+`add`로 대체하거나 세션 재시작 안내로 교체), `claude mcp status X` → `claude mcp get X`로
  교정. `~/.claude/settings.json`에 `mcpServers`를 직접 쓰는 절(112-128행)도 `claude mcp add-json`
  경로와 대조해 재검증할 가치가 있음(이 부분은 시간 제약으로 UNKNOWN — 아래 참고).

### F4. `plugins/common/skills/multi-perspective-review/SKILL.md` — 존재하지 않는 에이전트 참조 (CONFLICT)

- **무엇**: "Data/Schema" 관점의 "관련 에이전트" 열이 `design-database`를 지목하는데, 이
  이름의 에이전트가 33개 중에 없다.
- **어디**: `multi-perspective-review/SKILL.md:42`.
- **왜 문제인가**: `find plugins/common/agents -name "*.md"`로 33개 전수 목록을 확인했고
  (§4), `design-database`는 없다. 이 관점이 실제로 트리거될 때 이 스킬을 읽는 에이전트는
  존재하지 않는 서브에이전트를 호출하려 하거나, 그 시도가 실패해 관점 하나가 조용히
  기능 저하될 수 있다.
- **무엇과 충돌하는가**: `plugins/common/agents/` 실제 33개 파일 목록.
- **권고**: **수정**. 표 9행(`plan-implementation` 또는 `analyze-domain` 등 실제 존재하는
  에이전트로 교체)만 고치면 되는 국소 수정. 나머지 9개 관점의 "관련 에이전트" 열은 전부
  실제 에이전트와 일치함을 확인했다(analyze-domain은 없지만 clarify-requirements·
  plan-implementation·security-scan·design-user-journey·define-business-logic·
  analyze-dependencies·review-code·define-metrics·devils-advocate는 전부 실존).

### F5. `plugins/common/skills/references/work-system.md` — 활성 참조인데 구식 모델 (CONFLICT)

- **무엇**: `plan-task/SKILL.md`와 `auto-dev/SKILL.md`가 "Work 시스템 상세/전체" 링크로
  실제 가리키는 유일한 문서인데, 그 내용이 지금의 `plan-task` 구조와 다른 세대의 모델을
  서술한다.
- **어디**:
  - `plan-task/SKILL.md:200`, `auto-dev/SKILL.md:386` — 링크 지점.
  - `references/work-system.md:39-40, 148, 162, 170, 176, 182, 188, 193, 339` — "Phase 0"~
    "Phase 6"(다관점 리뷰 포함) 모델을 서술.
  - 대조: `plan-task/SKILL.md`는 "Step 0~4"이고 Phase 번호 체계가 없다. 다관점 리뷰는
    `multi-perspective-review` 스킬이 별도로 담당하며, `auto-dev/SKILL.md` Step 3의
    `review-results.md`는 **Validation 단계**(Dev 이후)에서 review-code/security-scan
    결과를 담는 파일이지, work-system.md가 말하는 "Phase 6, Planning 중 다관점 리뷰"가
    아니다.
- **왜 문제인가**: `task-tools-fallback.md`처럼 실제 SSOT로 인용되는 문서인데, 인용하는
  스킬 본문과 서로 다른 파이프라인 모델을 말하고 있어 **"상세를 보러 갔다가 더 헷갈리는"**
  상태다. `git log`상 2026-04-06 마지막 수정 — `plan-task`가 Step 기반으로 재설계된
  시점 이후 이 문서가 따라가지 못한 것으로 보인다.
- **무엇과 충돌하는가**: `plugins/common/skills/plan-task/SKILL.md`(Step 0-4 구조),
  `plugins/common/skills/auto-dev/SKILL.md`(review-results.md의 실제 생성 시점).
- **권고**: **갱신**. Phase 번호 체계를 제거하고 현재 Step 0-4 서술로 재작성. 분량이
  많아(509행) 전면 재작성 비용이 있다면, 최소한 "이 문서는 구식 Phase 모델을 설명하며
  현재 plan-task와 다르다"는 경고 배너를 상단에 넣는 임시조치라도 필요.

### F6. `plugins/common/skills/skill-creator/SKILL.md` — 존재하지 않는 계약 + 미사용 관행 (CONFLICT)

- **무엇**: agent-creator와 같은 패턴의 결함 — 존재하지 않는 매니페스트 등록을 지시하고,
  실제 어떤 스킬도 쓰지 않는 frontmatter 필드를 표준으로 제시한다.
- **어디**:
  - `skill-creator/SKILL.md:67-68, 190` — `plugins/{domain}/.claude-plugin/plugin.json`의
    `skills` 필드 확인/등록 지시. 실제 `plugin.json`에는 그런 필드가 없다(§4, F2와 동일 근거).
  - `skill-creator/SKILL.md:42-50, 82` — 표준 frontmatter 템플릿에 `argument-hint`·
    `allowed-tools`를 포함. `grep -rl "argument-hint\|allowed-tools" plugins/common/skills/*/SKILL.md`
    결과 이 파일 자신 말고는 0건 — 19개 실제 스킬 중 이 필드를 쓰는 것이 하나도 없다.
- **왜 문제인가**: 새 스킬을 이 템플릿대로 만들면 레포의 실제 관행(`name`/`description`/
  `model`/`effort`만 쓰는 19개 스킬)과 다른 스킬이 하나 섞여 들어간다. `plugins/{domain}`
  전제도 F2와 동일하게 틀렸다.
- **무엇과 충돌하는가**: 실제 `plugin.json`(§4), 실제 19개 SKILL.md의 frontmatter 관행.
- **권고**: **수정**. 매니페스트 등록 절 삭제(자동 발견 서술로 교체), 템플릿에서
  `argument-hint`/`allowed-tools`를 제거하거나 "선택적, 이 레포 관행은 미사용"으로 각주.

### F7. `plugins/common/skills/using-claude-code-kit/SKILL.md` — 네이티브 재기술 (CONFLICT)

- **무엇**: "Skill Trigger Map"과 "Agent Selection" 두 표가 하네스가 이미 시스템 프롬프트에
  제공하는 정보(19개 스킬·33개 에이전트의 설명+`MUST USE when:` 트리거)를 다시 나열한다.
- **어디**: `using-claude-code-kit/SKILL.md:28-43`(Skill Trigger Map),
  `using-claude-code-kit/SKILL.md:45-55`(Agent Selection).
- **왜 문제인가**: 이 세션 자체의 시스템 프롬프트(`<system-reminder>` "Available agent
  types"·"available skills" 목록)가 33개 에이전트 전부와 19개 스킬 전부를 설명·트리거와
  함께 이미 나열하고 있음을 직접 확인했다(§4). 두 표는 그 위에 같은 정보를 압축 재기술한
  것이라 유지 비용만 있고(새 스킬/에이전트 추가 시 이 표도 손대야 함) 정보 이득이 없다.
- **무엇과 충돌하는가**: 설계문서 D-18이 이 정확한 두 표를 "네이티브가 이미 제공하는 것의
  재기술" 사례로 **명시적으로 지목**하며 제거를 결정했다(`hiway-design.md:728-730`).
- **권고**: **삭제(설계문서 지시 이행)**. D-18이 이미 이 결정을 내렸으므로 새 결정 불필요 —
  W-025/026 구현 시 그대로 반영하면 된다. kit 고유 체인(`brainstorming → plan-task →
  auto-dev`)과 Work 시스템 규약(16-26, 57-60행)은 네이티브가 모르는 정보이므로 유지.

### F8. `plugins/common/skills/references/*.md` 8종 — 미참조 (ORPHAN, 그중 4종은 DUP)

- **무엇**: `references/` 10개 파일 중 8개가 어떤 SKILL.md·에이전트로부터도 참조되지
  않는다. 그중 4개(`conflict-resolution.md`·`deliberation-pattern.md`·`examples.md`·
  `perspectives-guide.md`)는 `multi-perspective-review/` 아래의 동명 파일과 **바이트
  단위로 동일**하다(`diff` 결과 0줄, §4).
- **어디**: 8개 전 파일. 5개 메타 에이전트(`facilitator`·`synthesizer`·`consensus-builder`·
  `devils-advocate`·`facilitator-teams`)의 frontmatter `references:` 필드가
  `../../../skills/common/multi-perspective-review/references/*.md`를 가리키는데, 이 경로는
  **애초에 존재하지 않는다**(최상위 `skills/common/` 디렉토리 자체가 없음) — 즉 "의도된
  소비자"조차 깨져 있다. 이 사실은 T3(스킬 축) 범위 밖의 에이전트 파일에서 발견됐으므로
  참고용으로만 적는다(고치지 않음).
- **왜 문제인가**: 전부 2026-03-15 최초 커밋 이후 미변경(`task-tools-fallback.md`·
  `work-system.md`만 그 뒤 갱신됨, §4) — 최초 스캐폴딩 이후 방치된 자산이라는 정황과
  일치한다. 4종은 활성 사본과 완전히 같은 내용을 두 곳에서 관리해야 하는 상태라 향후 한쪽만
  고치면 조용히 갈라진다(드리프트 위험, 아직 실현되지 않았을 뿐).
- **무엇과 충돌하는가**: 직접적 텍스트 충돌은 없음(DUP 4종은 오히려 "완전 동일"이라 지금은
  안전하지만, 구조적으로 SSOT 위반).
- **권고**:
  - DUP 4종(`conflict-resolution`·`deliberation-pattern`·`examples`·`perspectives-guide`):
    **삭제**. `multi-perspective-review/` 안의 사본이 실제 SKILL.md가 링크하는 유일한
    소스이므로 그쪽을 SSOT로 확정하고 `references/` 사본을 제거. 단, 5개 메타 에이전트의
    깨진 `references:` 경로를 이 삭제와 **함께** 고치거나(에이전트 축 담당), 최소한 별도
    이슈로 남겨야 한다 — 지금 상태로는 그 필드가 어느 쪽을 가리켜도 깨져 있다.
  - 순수 ORPHAN 4종(`available-tools`·`model-selection`·`phase-guides`·`work-integration`):
    **삭제 또는 참조 신설 중 택1**. `model-selection.md`는 이 레포에 없는 에이전트
    이름(`plan-infrastructure`·`deploy`·`monitor` 등)을 나열하고 있어 내용 자체도
    신뢰할 수 없다 — 삭제 권고. `phase-guides.md`는 F5/F1과 같은 구식 Phase 모델의 잔재라
    work-system.md 재작성과 묶어 함께 정리하는 편이 낫다. `available-tools.md`·
    `work-integration.md`는 내용 자체는 대체로 유효하나 참조가 없어 죽어 있다 — 유지하려면
    최소 하나의 SKILL.md에서 실제로 링크해야 한다.

### F9. `docs/native-absorption.md` 대조 결과 — 참고용, 정정 없음

- 배경 확인용으로 읽은 이 대조표는 T3 스코프 밖이지만, `agent-teams`(F3와 무관, 별개
  판단) 관련 행이 이미 정확히 현재 상태(스킬은 라우팅 안내로 축소, `superseded`)를
  반영하고 있어 skills 축 감사와 충돌 없음을 확인했다. 별도 발견 없음.

---

## 3. 계획 정렬 (D-1~D-21 대조)

| 발견 | 흡수 결정 | 비고 |
| --- | --- | --- |
| F7 (using-claude-code-kit 네이티브 재기술) | **D-18** | 정확히 일치. 새 결정 불필요 — 실행만 남음(W-025/026 몫) |
| `agent-teams/SKILL.md` 현재 상태 | **D-7** | 1단계(폐기 예고 교체, v2.18.0)·2단계(제거, v3.0.0) 계획대로 진행하면 됨. 현재 파일 자체는 OK 판정이라 급하지 않음 |
| F1 (`skills/README.md` 구식·오참조) | **새 결정 필요** | 제안: "`skills/README.md`를 plan-task 사용법 사본이 아니라 19개 스킬의 실제 색인으로 재작성한다 — 삭제 시 README.md 루트의 21-vs-19 카운트 설명이 깨지므로 대체를 원칙으로 한다." |
| F2 (`agent-creator` 존재하지 않는 계약) | **새 결정 필요** | 제안: "`agent-creator`/`skill-creator`가 가르치는 템플릿을 CLAUDE.md Contributing 체크리스트(금지 필드·필수 필드·매니페스트 무등록 원칙)와 대조해 동기화하고, 이 동기화를 스킬 변경 시 재발 방지 체크로 못박는다." |
| F3 (mcp-builder 존재하지 않는 CLI) | **새 결정 필요** | 제안: "`mcp-builder`의 CLI 예시를 `claude mcp --help` 실측과 대조해 갱신하고, 이런 하네스 CLI 표면을 인용하는 스킬 문서에 대해 릴리스 체크리스트에 1회성 CLI diff 확인 항목을 추가할지 판단한다." |
| F4 (multi-perspective-review의 존재하지 않는 에이전트) | **새 결정 필요** (또는 에이전트 축과 공유) | 제안: "`design-database` 참조를 실제 존재하는 에이전트로 국소 수정한다 — 다른 스펙 결정에 의존하지 않는 1줄 수정" |
| F5 (`work-system.md`가 활성 링크인데 구식) | **새 결정 필요** | 제안: "`references/work-system.md`·`phase-guides.md`를 현재 `plan-task`의 Step 0-4 모델로 재작성하거나, 재작성 전까지 상단에 구식 경고 배너를 넣는다" |
| F6 (skill-creator 존재하지 않는 계약 + 미사용 필드) | F2와 **동일 새 결정**으로 묶을 수 있음 | agent-creator/skill-creator를 한 번에 동기화하는 것이 효율적 |
| F8 (references/ 8종 미참조, 그중 4종 DUP) | **새 결정 필요** | 이것이 바로 이 감사(T3)가 확인하라고 요청받은 항목이며, 설계문서 D-1~D-21 어디에도 다뤄지지 않았다. 제안: "`skills/references/`의 DUP 4종은 삭제해 `multi-perspective-review/`를 SSOT로 단일화하고, 순수 ORPHAN 4종은 `model-selection.md`(내용 신뢰 불가)를 우선 삭제, 나머지는 재참조 신설 또는 삭제 중 택1한다. 동시에 5개 메타 에이전트의 깨진 `references:` frontmatter 경로를 고치거나 제거한다(에이전트 축과 조율 필요)." |
| 이름/네임스페이스 관련 스킬 본문(`/claude-code-kit:plan-task` 등 표기) | **D-3, D-4** | 스코프 파일 다수가 `claude-code-kit:` 프리픽스를 프로즈에 쓰지만(예: `using-claude-code-kit/SKILL.md:33-43`), 이는 D-3(이름 SSOT화)·D-4(v3.0.0 개명) 실행 시 일괄 갱신 대상이지 지금 시점의 결함은 아니다 — 별도 판정 불필요, 실행 시점에 자동 포함됨 |

---

## 4. 실측 로그

### 4.1 워크트리/설계문서 정합성

```
$ git log --oneline -1                     # dd63b44 (로컬 브랜치 HEAD)
$ git merge-base --is-ancestor c707729 dd63b44   → NOT ancestor
$ git merge-base --is-ancestor dd63b44 c707729   → dd63b44 is ancestor of c707729
$ git cat-file -e HEAD:docs/specs/2026-09-07-hiway-program-design.md → NOT_IN_HEAD
$ git show origin/main:docs/specs/2026-09-07-hiway-program-design.md > (scratchpad)  → 792줄, 성공
```
→ 이 워크트리의 로컬 브랜치는 태스크 브리핑이 말한 `c707729`보다 오래된 커밋에서
분기됐다(다른 census 워크트리 T1/T2/T4/T5도 전부 `dd63b44` 동일 — `torpedo` 워크트리만
`c707729`). `origin/main`에는 이미 존재하므로 `git show`로 읽기 전용 추출해 대조했다.
커밋·체크아웃·브랜치 생성 없음(금지 사항 준수).

### 4.2 커버리지 표 대상 34개 파일 확인

```
$ for f in <34개 경로>; do wc -l < "$f"; done   # 전부 존재, MISSING 0건
```

### 4.3 multi-perspective-review ↔ references 중복 확인

```
$ diff plugins/common/skills/multi-perspective-review/conflict-resolution.md \
       plugins/common/skills/references/conflict-resolution.md            → 0줄 (동일)
$ diff .../deliberation-pattern.md .../deliberation-pattern.md            → 0줄 (동일)
$ diff .../examples.md .../examples.md                                    → 0줄 (동일)
$ diff .../perspectives-guide.md .../perspectives-guide.md                → 0줄 (동일)
```

### 4.4 references/*.md 소비자 실측 (전수 grep)

```
$ grep -rn "references/<파일명>" --include="*.md" --include="*.py" --include="*.json" .
```
결과 요약(자기 자신·바이트동일 사본 제외):
- `available-tools.md` → 0건
- `conflict-resolution.md` → 소비 의도로 보이는 참조 3건이 전부 `plugins/common/agents/meta/*.md`의
  `references:` frontmatter인데, 그 경로(`../../../skills/common/multi-perspective-review/references/...`)
  자체가 `skills/common/` 최상위 디렉토리 부재로 **깨져 있음**(아래 4.6). 유효한 소비자는 0건.
- `deliberation-pattern.md` → 상동, 유효 소비자 0건
- `examples.md` → `implement-code.md:26`에 `path: references/examples.md`가 있으나 이는
  **에이전트 자신의 `references/` 디렉토리**(`plugins/common/agents/dev/references/`)를
  향한 것이고 그 디렉토리도 존재하지 않는다(별도 결함, T3 스코프 밖). skills/references와는 무관.
- `model-selection.md` → 0건
- `perspectives-guide.md` → 소비 의도 경로 3건, 전부 깨짐(위와 동일 사유). 유효 소비자 0건
- `phase-guides.md` → 0건 (doc-coauthoring의 "단계별 가이드 작성"은 동음이의 일반 문구, 무관 확인)
- `task-tools-fallback.md` → `brainstorming/SKILL.md:20`, `plan-task/SKILL.md:42`,
  `auto-dev/SKILL.md:73`, `CHANGELOG.md:668`에서 "규율 SSOT" 문구로 실제 인용됨 → **참조 있음**
- `work-integration.md` → 0건
- `work-system.md` → `plan-task/SKILL.md:200`, `auto-dev/SKILL.md:386`의 "참고 문서" 표에서
  실제 인용됨 → **참조 있음**

### 4.5 최종 수정일 (전수, `git log -1 --date=short`)

```
available-tools.md         2026-03-15 4a06307
conflict-resolution.md     2026-03-15 4a06307
deliberation-pattern.md    2026-03-15 4a06307
examples.md                2026-03-15 4a06307
model-selection.md         2026-03-15 4a06307
perspectives-guide.md      2026-03-15 4a06307
phase-guides.md            2026-03-15 4a06307
task-tools-fallback.md     2026-08-28 09c527e   ← 활성 SSOT, 최근 갱신
work-integration.md        2026-03-15 4a06307
work-system.md             2026-04-06 4121622   ← 활성 링크 대상, 갱신됐으나 여전히 구식(F5)
plugins/common/skills/README.md          2026-03-15 4a06307 (최초 커밋 이후 무변경)
plugins/common/skills/agent-creator/SKILL.md   2026-08-27 d054723 (최근 수정인데도 F2 결함 잔존)
plugins/common/skills/skill-creator/SKILL.md   2026-04-22 f3e15f6
```

### 4.6 깨진 상대경로 확인 (에이전트 축, 참고용)

```
$ grep -rln "^references:" plugins/common/agents/ | xargs grep -l "skills"
  → facilitator.md, synthesizer.md, consensus-builder.md, devils-advocate.md, facilitator-teams.md
$ find . -path "*/skills/common/*"        → 0건 (해당 경로 자체가 없음)
$ ls plugins/common/agents/dev/references/  → NO SUCH DIR (implement-code.md의 자체 references도 깨짐)
```

### 4.7 `claude mcp` 실제 하위 명령 (mcp-builder/SKILL.md 검증, F3)

```
$ claude mcp --help
Commands: add, add-from-claude-desktop, add-json, get, help, list, login,
          logout, remove, reset-project-choices, serve
```
→ `restart`·`status`는 이 목록에 없음. `mcp-builder/SKILL.md:134,223`가 인용하는
명령은 실존하지 않는다.

### 4.8 에이전트 33종 전수 목록 (multi-perspective-review 검증, F4)

```
$ find plugins/common/agents -name "*.md" | wc -l   → 33
$ find plugins/common/agents -iname "*design-database*"  → 0건
```

### 4.9 CLAUDE.md 대비 실제 매니페스트/필드 (agent-creator·skill-creator 검증, F2/F6)

```
$ cat plugins/common/.claude-plugin/plugin.json
  → name/version/description/author/homepage/repository/license/keywords 뿐.
    "agents" 또는 "skills" 필드 없음.
$ ls plugins/                              → common (1개뿐, {domain} 다중 구조 아님)
$ grep -rl permissionMode plugins/common/agents/     → 0건 (33개 전수 미사용)
$ grep -rL maxTurns plugins/common/agents/**/*.md    → 0건 (33개 전수 보유)
$ grep -rl "argument-hint\|allowed-tools" plugins/common/skills/*/SKILL.md
  → skill-creator/SKILL.md 자신뿐 (19개 스킬 중 실사용 0건)
```

### 4.10 DELEGATION_SIGNAL 잔재 확인 (스코프 전체)

```
$ grep -rn "DELEGATION_SIGNAL\|DELEGATE_TO\|TYPE: DELEGATE" plugins/common/skills/
  → 0건. CLAUDE.md의 폐기 완료 서술과 일치.
```

### 4.11 네이티브 시스템 프롬프트의 스킬/에이전트 나열 (F7 검증)

이 세션 자체의 `<system-reminder>`가 33개 에이전트 전부(설명 + `MUST USE when:` 트리거
포함)와 19개 스킬 전부(설명 포함)를 이미 나열하고 있음을 대화 컨텍스트에서 직접 확인
(도구 호출 아님 — 세션 프롬프트 자체의 관측). `using-claude-code-kit/SKILL.md:28-55`의
두 표가 그 위에 같은 정보를 압축 재기술한다는 판단의 근거.

---

## 요약

- 34개 스코프 파일 전수 확인. **OK 21 / CONFLICT 7 / ORPHAN 4(순수) / DUP 4**.
- 가장 심각한 발견은 F1(`skills/README.md`, 실체와 완전히 다른 구식 문서)과 F2/F6
  (agent-creator·skill-creator가 존재하지 않는 계약과 금지 필드를 가르침) — 둘 다
  "만들어질 다음 산출물의 품질"에 직접 영향을 준다.
- F7(using-claude-code-kit의 네이티브 재기술)은 설계문서 D-18과 정확히 일치해 새 판단이
  필요 없다 — 실행만 남았다.
- F8(references/ 8종 미참조)은 설계문서가 명시적으로 감사하라고 지목한 항목이었고,
  실측 결과 8/10이 죽어 있으며 그중 4개는 활성 사본과 완전 동일한 방치된 이중 관리
  상태임을 확인했다. 이 항목에 대한 결정은 D-1~D-21에 없어 새 결정이 필요하다.
- 폐기된 `DELEGATION_SIGNAL` 계약의 잔재는 스코프 내 0건 — CLAUDE.md의 완료 서술과 일치.
