---
status: historical
as_of: 2026-10-05
---

# 감사 D — 콜드 리딩 보고서

기준 커밋: `e7181cbbfb6c8c3bc38b7ae4e979da09fa30a618` — 현재 HEAD와 일치했고 `git merge-base --is-ancestor … HEAD`도 성공했다. 보고 기준일은 2026-10-05이다. 감사 동안 저장소 파일은 수정하지 않았으며, 검증 후 `git status --short --branch`에는 브랜치 이름만 나왔다.

## (a) 이 킷이 무엇이고 어떻게 쓰는가 — 콜드 리딩 요약

문서상 hiway-kit은 개발 작업에 의견 있는 흐름과 규율을 얹는 플러그인으로, Claude Code를 중심으로 15개 에이전트·15개 스킬·규칙·훅을 제공한다. Large 새 기능은 `brainstorming → plan-task → auto-dev`, Medium은 `plan-task → auto-dev`, Small·버그는 바로 구현하고 완료 조건 명령으로 검증한다. Claude Code는 서브에이전트와 자동 차단 훅까지 쓰지만 Codex는 15개 스킬을 인식하고, 프로젝트에 export된 `AGENTS.md`가 있거나 훅 신뢰를 승인하면 portable 규범을 받는다. Codex는 전용 에이전트와 자동 차단을 제공하지 않으며, 훅 신뢰 전에는 `AGENTS.md`가 규범 전달 경로이고 신뢰 승인 뒤에도 일부 규범은 중복 전달될 수 있다. 플러그인 동작이 바뀌면 버전·CHANGELOG·생성 타겟 매니페스트를 맞추고 완료 게이트를 통과시켜 릴리스 태그로 배포한다. 다만 새 킷 에이전트 생성 절차, eval 등록, 릴리스 버전 갱신 방식은 문서 사이에 빈틈이나 충돌이 남는다.

## 읽은 순서와 그때 생긴 질문

질문은 각 문서를 읽은 직후 떠오른 것으로 기록했다. 뒤에서 답이 확인되면 괄호에 적고, 아직 맞춰지지 않은 것은 미해결로 남겼다.

| 순서 | 문서 | 그 시점의 질문 / 뒤의 답 |
| --- | --- | --- |
| 1 | `README.md` | “Universal”이면서 “built for Claude Code”라는 말은 주력 하네스와 부분 지원 하네스를 어떻게 나누는가? Quick Install은 Claude만 보여 주는데 Codex는 어디서 설치하는가? (같은 문서 후반의 플랫폼 표·설치 절이 답함.) 새 agent를 plugin.json에 등록해야 하는가? (CLAUDE와 packaging 문서를 더 읽어야 답할 수 있음.) |
| 2 | `CLAUDE.md` | `/agent-creator`가 킷 플러그인용 파일도 만드는가? 새 agent를 파일 외 어디에 등록하는가? 버전은 직접 편집하는가? (에이전트 스킬·SSOT 규칙·릴리스 관례를 읽은 뒤 일부 충돌 발견.) |
| 3 | `docs/conventions/path-containment.md` | 새 agent 추가 작업에도 설정 경로 봉쇄 규약을 적용해야 하나? (일반 코드 관례로는 명확하지만 이 작업과의 직접 관계는 없음.) |
| 4 | `docs/conventions/lint-single-ruleset.md` | 개발자가 써야 할 Ruff 버전은 무엇인가? (`.ruff-version` pin이 SSOT라는 답. 실행 결과는 v0.16.1.) |
| 5 | `docs/conventions/rules-mirror.md` | 주입 규칙을 바꾸면 어떤 장문 문서·체크섬을 같이 고쳐야 하나? (미러 대상만 동기화한다. agent-system roster를 고칠 경우 관계 있음.) |
| 6 | `docs/conventions/shell-lint.md` | 로컬 shellcheck가 없으면 릴리스 판정이 면제되는가? (CI가 권위 있는 판정이고 로컬은 노란 안내라는 답.) |
| 7 | `docs/conventions/warning-signal.md` | 게이트를 추가·수정할 때 정상 사용 경로에서 실제로 도는지 어떻게 판단하는가? (적용 조건·양성 대조·대상 밖 확인 규약이 답.) |
| 8 | `docs/conventions/coordination.md` | Orca 협업 규약이 킷 소비자에게도 강제되는가? (이 저장소 전용이라고 명시.) |
| 9 | `docs/architecture/delegation-signal-retirement.md` | `DELEGATION_SIGNAL`은 여전히 실행 계약인가? (폐기된 역사 기록이며 자동 파서는 없었다고 답.) |
| 10 | `docs/architecture/phase-gate-pattern.md` | 현재 Stop hook이 Planning/Validation phase gate를 실제 자동 판정하는가? (CLAUDE의 훅 설명과 모순되어 미해결.) |
| 11 | `docs/architecture/rules/task-resume.md` | 세션이 끝나도 무엇이 완료 상태의 기준으로 남는가? (`checklist.json` 또는 `plan.md`라는 답.) |
| 12 | `docs/architecture/rules/agent-delegation-chain.md` | 위임 사전 승인이 실제 위임을 보장하는가? Stop hook이 어떤 행동까지 보장하는가? (이 문서의 “Stop hook이 강제” 표현과 실제 훅 설명 사이에 모호함.) |
| 13 | `docs/architecture/rules/agent-system.md` | 에이전트 목록은 어디가 권위 있는가? 새 agent 추가 때 표를 갱신해야 하는가? (“Roster (SSOT)”라고 적혀 있지만 CLAUDE의 추가 절차에는 이 작업이 빠져 있음.) |
| 14 | `docs/architecture/rules/planning-protocol.md` | Small/Medium/Large 구분 및 elicitation 절차는 어디서 더 보는가? (`plan-task`와 `references/elicitation.md`가 소유한다고 답.) |
| 15 | `docs/architecture/rules/mcp-usage.md` | 사용자 전역 MCP가 있어도 conditional 규칙이 주입되는가? (`.mcp.json` 감지만 한다는 제한과 이유를 설명.) |
| 16 | `docs/architecture/rules/MIRROR.sha256` | 규칙 미러 drift를 어떤 명령이 잡는가? `verify-done.sh §7`과 regenerate 명령을 확인함. |
| 17 | `plugins/common/skills/using-hiway-kit/SKILL.md` | 규모 기준은 여기 정의되어 있는가? `plan-task`가 소유한다고 명시. |
| 18 | `plugins/common/skills/agent-creator/SKILL.md` | 이 스킬은 킷 plugin agent를 만드는가? `.claude/agents/` 또는 사용자 agent를 만드는 프로젝트 전용 절차라고 답해 CLAUDE 표와 충돌을 드러냄. |
| 19 | `plugins/common/skills/auto-dev/SKILL.md` | 호스트 태스크 도구·서브에이전트가 없으면 실행이 막히는가? durable checklist와 같은 계약의 인라인 실행 경로가 있다고 답. |
| 20 | `plugins/common/skills/brainstorming/SKILL.md` | 모든 새 기능에 필요한가? Large 새 기능만이며 Medium은 plan-task라는 답. |
| 21 | `plugins/common/skills/child-session/SKILL.md` | 기준 커밋·마커·보고는 무엇으로 정하는가? 명시된 스키마와 부모 보고 규율을 확인. |
| 22 | `plugins/common/skills/control-loop/SKILL.md` | 조사·결정·구현을 한 위임으로 묶어도 되는가? 분리해야 한다고 답. |
| 23 | `plugins/common/skills/cross-engine-review/SKILL.md` | 메시징 도구가 없어도 교차 리뷰가 가능한가? 파일 우편함 경로가 있다고 답. |
| 24 | `plugins/common/skills/debug/SKILL.md` | 서브에이전트 없는 하네스에서 디버깅은 중단되는가? 같은 계약을 직접 수행하는 경로가 있음. |
| 25 | `plugins/common/skills/harness-export/SKILL.md` | Codex 규범은 훅 신뢰 전에도 도달하는가? `AGENTS.md`가 유일한 폴백이라는 답. |
| 26 | `plugins/common/skills/multi-perspective-review/SKILL.md` | Codex에서 10 관점은 어떻게 실행되는가? 같은 세션의 순차 경로와 독립성 한계를 명시. |
| 27 | `plugins/common/skills/plan-task/SKILL.md` | Medium/Large만 계획 파일을 쓰는가? 그렇고 Small은 대화 내 계획을 사용한다고 답. |
| 28 | `plugins/common/skills/review/SKILL.md` | 파일 수가 많으면 어떻게 리뷰하는가? review-code 입력을 6개 이하 배치로 나누라는 답. |
| 29 | `plugins/common/skills/skill-forge/SKILL.md` | 어려운 일을 한 번 해결하면 새 스킬을 만드는가? 재현성·반복성·비중복 세 조건이 모두 필요. |
| 30 | `plugins/common/skills/test/SKILL.md` | 테스트 수정 위임이 불가능하면 어떻게 하는가? 이 세션에서 같은 계약을 수행. |
| 31 | `plugins/common/skills/web-research/SKILL.md` | 지정된 MCP가 없을 때 조사 결과를 만들 수 있는가? 빌트인 도구로 전환하고 미사용 소스를 명시. |
| 32 | `plugins/common/rules/agent-delegation-chain.md` | 신호 문자열로 다음 에이전트를 고르는가? 아니며 호출 스킬의 순서가 권위 있음. |
| 33 | `plugins/common/rules/agent-system.md` | 새 agent의 모델·isolation·로스터 표를 누가 소유하는가? 이 규칙은 표를 SSOT로 선언함. |
| 34 | `plugins/common/rules/child-marker.md` | 자식 marker의 필드명·수명은 무엇인가? `base_commit` 포함 고정 schema와 회수 전 삭제를 확인. |
| 35 | `plugins/common/rules/definition-of-done.md` | 완료 선언 외에 무엇을 증명해야 하는가? fresh gate 실행·수동 attest·계획 상태 완료가 답. |
| 36 | `plugins/common/rules/delegation-contract.md` | worker 결과는 어디로 보내야 하는가? 브리프에 수단과 컨트롤 식별자를 적어야 함. |
| 37 | `plugins/common/rules/feedback-loop.md` | Codex에서 LESSONS가 자동 주입되지 않으면 어떻게 하는가? ledger digest를 직접 조회. |
| 38 | `plugins/common/rules/loop-engineering.md` | 단일 실행도 모든 unblocked 작업을 계속 도는가? 단발 작업은 loop가 아니며 배치는 opt-in. |
| 39 | `plugins/common/rules/mcp-usage.md` | MCP가 항상 있다고 가정해도 되는가? 없거나 실패할 때 built-in fallback을 쓰도록 함. |
| 40 | `plugins/common/rules/parallel-worktree.md` | 특정 격리 도구를 설치해야 하는가? 메커니즘은 호스트가 고르며 파일 소유권·통합 불변식만 정함. |
| 41 | `plugins/common/rules/planning-protocol.md` | 불확실성만 있으면 멈추는가? P0만 묻고 나머지는 등급별 처리. |
| 42 | `plugins/common/rules/task-resume.md` | 사용자가 다른 질문을 해도 활성 계획을 재개하는가? 재개를 명시하지 않으면 질문에 답함. |
| 43 | `plugins/common/rules/untrusted-text.md` | Codex에서 이 규칙은 자동 차단인가? 지침으로 작동하며 자동 차단은 없다고 명시. |
| 44 | `docs/specs/2026-10-02-product-site/spec.md` | 완료된 사이트 spec이 현재 배포 경로를 뜻하는가? status는 done이나 실제로 서빙되는지는 이 문서만으로 알 수 없음. |
| 45 | `docs/specs/2026-09-30-tools-dir/spec.md` | 5.2.0 경로 변경은 현재 지침인가? 완료된 변경의 역사 기록으로 읽음. |
| 46 | `docs/specs/2026-09-30-boundary-enforcement/spec.md` | 이 변경은 agent를 추가하는가? 결정 D2에서 새 agent를 만들지 않는다고 하며, 완료된 범위의 기록. |
| 추가 | `packaging/README.md` | 타겟 매니페스트를 언제 다시 생성하는가? 버전 변경·targets 정책 변경 때 생성하라는 답. |
| 추가 | `docs/conventions/release-process.md` | 버전 갱신은 수동인가 자동인가? `scripts/bump-version.sh`를 쓰라고 해서 CLAUDE의 편집 예시와 충돌. |
| 추가 | `evals/README.md` | 새 agent는 어떤 eval 등록을 해야 하는가? 시나리오 추가 방법과 릴리스 전 전체 eval은 있지만 새 agent의 tier 등록 경로는 불명확. |
| 추가 | `plugins/common/README.md` | `/agent-creator`는 어느 범위의 agent를 만드는가? “project agent”라고 명시, CLAUDE 표와 충돌. |

## (b) 혼란·모순·누락

1. **[P0] `/agent-creator`가 킷 agent를 만든다고 안내한다.** `CLAUDE.md:66` 표는 “Generate plugin agents”라고 하지만 스킬은 프로젝트/사용자용이며 `.claude/agents/<name>.md`에 쓰라고 한다 (`plugins/common/skills/agent-creator/SKILL.md:8-18`). `plugins/common/README.md:30`도 “Create a project agent”라고 설명한다. 새 킷 agent 작성자가 잘못된 디렉터리에 파일을 만들 수 있다. **추가할 문장:** “`/agent-creator`는 소비자 프로젝트의 `.claude/agents/` agent를 만든다. 배포되는 킷 agent는 아래 ‘Adding a New Agent’ 절차로 `plugins/common/agents/`에 추가한다.”

2. **[P0] Phase Gate가 Stop hook에서 자동으로 판정된다고 읽힌다.** `docs/architecture/phase-gate-pattern.md:138-145`는 Stop hook이 Planning/Development/Validation gate를 자동화하며 스킬 호출 없이 적용된다고 한다. 현재 hook 설명인 `CLAUDE.md:242-247`은 수정된 Python 린트와 수정된 테스트 실행만 설명한다. 신규 기획자는 `/plan-task`를 호출하지 않아도 gate가 돈다고 오해할 수 있다. **추가할 문장:** “이 문서는 과거 권장 패턴이며 현재 구현 설명이 아니다. Stop hook은 수정된 Python 파일과 테스트만 검사하고 기획 단계 전환은 해당 스킬이 수행한다.” 또는 문서를 현재 상태에 맞게 다시 작성한다.

3. **[P1] 새 킷 agent 절차가 로스터·eval·숫자 갱신을 말하지 않는다.** `CLAUDE.md:163-170`은 flat 파일, frontmatter, manifest 미수정까지만 안내한다. 반면 `plugins/common/rules/agent-system.md:14-36`은 agent roster 표를 SSOT라고 선언하고, `evals/README.md:208-220`은 agent 이름으로 시나리오를 추가하는 절차를 둔다. 실행한 `scripts/verify-done.sh`도 “tier1 전 에이전트”, “tier2 전 에이전트”, “전체 에이전트(15종) 분류 완전” 검사를 통과시켰다. 어느 tier로 분류하고 어떤 경우 시나리오·기준선을 더해야 하는지 CLAUDE의 추가 절차만으로 결정할 수 없다. **추가할 문장:** “새 agent는 agent-system.md 로스터 및 eval tier 분류를 갱신하고, 해당 tier의 coverage 요건에 맞춰 시나리오·기준선을 갱신한다. 관련 수치 문서도 `verify-done.sh`가 가리키는 범위에서 동기화한다.” 정확한 등록 파일과 시나리오 의무 조건은 문서화가 더 필요하다.

4. **[P1] 버전 변경 방식이 서로 다르다.** `CLAUDE.md:358-387`은 manifest 버전 변경을 릴리스 체크리스트와 예시로 안내하지만, `docs/conventions/release-process.md:10-14`는 직접 편집하지 말고 `scripts/bump-version.sh <version>`을 사용하라고 한다. 이 스크립트는 타겟 재생성까지 묶는다고 설명한다. **추가할 문장:** CLAUDE 릴리스 절에 “버전은 `scripts/bump-version.sh <version>`으로 갱신하고 manifest를 손으로 수정하지 않는다”를 넣고, 수동 편집 예시를 제거한다.

5. **[P1] 완료 게이트와 릴리스 전 행동 eval의 관계가 드러나지 않는다.** `CLAUDE.md:382`는 `scripts/verify-done.sh` green을 릴리스 준비 조건으로 든다. `evals/README.md:16-20,243-248`은 실제 행동 eval을 별도 수동 릴리스 전 필수 게이트로 두고 `--baseline`을 갱신한다고 한다. `verify-done.sh` 실행 출력은 eval 스키마·coverage 검사를 통과했지만 전체 행동 eval을 실행했다고 하지 않았다. **추가할 문장:** “`verify-done.sh` 외에 릴리스 전 전체 행동 eval을 실행하고, 허용된 기준선 절차를 완료한다.” 새 agent가 eval suite에 포함되는 범위도 함께 밝혀야 한다.

6. **[P1] README의 ‘plugin.json 등록’은 컴포넌트 등록으로 오해된다.** `README.md:509`는 “Registered in plugin.json (with homepage, repository, license, author.email)”라고 적는다. 반면 `CLAUDE.md:169-170,423-424`는 plugin.json에 agent/skill registry가 없고 디렉터리에서 자동 발견된다고 한다. 괄호의 필드명은 패키지 metadata로 보이지만, 신규 agent 등록 단계처럼 배치되어 있다. **추가할 문장:** “이 체크는 플러그인 metadata가 채워졌는지 확인한다. 개별 agent는 manifest에 등록하지 않고 `plugins/common/agents/`에서 자동 발견된다.”

7. **[P2] 제품의 주력 범위가 첫 화면에서 모호하다.** `README.md:3-5`는 universal toolkit과 Claude 중심 제품을 연달아 부르고, `CLAUDE.md:3`도 “Universal Claude Code toolkit”이라고 한다. 후반 표가 Codex 제한을 설명하므로 문서 전체를 읽으면 범위가 드러나지만 첫 인상은 엇갈린다. **추가할 문장:** “Claude Code가 완전 기능 기준이며 Codex·Antigravity는 아래 capability 표에 적힌 부분 지원을 제공한다.”

## 검증 명령 결과

각 명령은 따로 실행했고 종료 코드를 보존했다.

| 명령 | 결과 |
| --- | --- |
| `claude plugin validate ./plugins/common` | rc 0 — `✔ Validation passed` |
| `python3 -m pytest -q` | rc 0 — 전체 진행 출력 완료. 이 명령의 quiet 출력에는 총계 요약 줄이 없고 `ss` 구간이 보였다. 이어 실행된 완료 게이트는 `pytest: 1246 passed`라고 출력했다. |
| `ruff check .` | rc 0 — `All checks passed!`; 완료 게이트는 Ruff v0.16.1로 clean이라고 보고했다. |
| `scripts/verify-done.sh` | rc 0 — 기계 검사 `33 pass / 0 fail`. 단, 끝부분의 수동 DoD attest 4개는 체크박스 상태로 출력되므로 gate 실행만으로 그 항목을 attest한 것은 아니다. 오래된 이름 검사에서 바이너리 icon 1개는 비-UTF-8이라 줄 단위 검사 대상이 아니라고 경고했지만 검사 대상 315개에서 구 이름은 0건이었다. |
| `python3 scripts/build-targets.py --check` | rc 0 — 생성물 4개 모두 SSOT와 일치. |

## (c) 유지보수자에게 물을 질문 10개

1. `/agent-creator` 표 설명을 “project-local agent”로 고치고, 킷 agent 추가에는 쓰지 않는다고 명시해야 하나요?
2. 킷 agent를 추가할 때 `plugins/common/rules/agent-system.md`의 roster 표는 매번 갱신해야 하나요?
3. 새 agent의 eval tier를 결정하는 기준과 갱신할 파일은 무엇이며, 모든 새 agent에 행동 시나리오가 필요한가요?
4. 버전은 `scripts/bump-version.sh`만 사용해야 하나요? CLAUDE의 수동 manifest 편집 예시는 제거해도 되나요?
5. 릴리스 전 전체 행동 eval과 baseline 갱신을 항상 해야 하나요? 새 agent를 eval suite 밖에 두는 예외 기준이 있나요?
6. `README.md:509`의 plugin.json 등록은 manifest metadata 확인만 뜻하나요, 아니면 다른 컴포넌트 registry를 말하나요?
7. 새 agent 추가 때 수치를 고쳐야 하는 문서 목록을 어디서 관리하나요? 자동 수치 게이트가 최종 기준인가요?
8. `docs/architecture/phase-gate-pattern.md`를 폐기 기록으로 표시할까요, 현재 동작에 맞춰 다시 쓸까요?
9. `plugins/common/README.md`의 PreToolUse 블록 설명은 Claude Code 전용이라고 표기해야 하나요? 현재 Codex 설명과 함께 읽으면 플랫폼 범위가 헷갈립니다.
10. 릴리스 배포의 완료 기준은 git tag/push인가요, 아니면 Claude 디렉토리·OpenAI 디렉토리 심사 완료까지를 의미하나요? 플랫폼별 배포 대기 상태를 어디에 기록하나요?

## (d) 과제 답과 막힌 지점

### 3. 새 agent 1개를 추가해 릴리스하려면

문서만으로 읽은 절차는 다음과 같다.

1. 킷에서 배포할 agent인지 프로젝트 사용자만 쓸 agent인지 정한다. `/agent-creator`는 `.claude/agents/`의 프로젝트 agent용이므로 킷 배포본 작성에는 적용하지 않는다 (`plugins/common/skills/agent-creator/SKILL.md:8-18`; `plugins/common/README.md:30`).
2. 킷 agent라면 `plugins/common/agents/{name}.md`에 flat 파일로 추가한다. `name`은 파일명과 같은 kebab-case, `description`에는 구체적인 `MUST USE when:` 조건, frontmatter에는 `name`, `description`, `model`, `maxTurns`를 둔다. 불필요한 도구와 금지 필드는 배제하고, 정규 agent는 `Task`를 금지하며 파일 수정 agent는 `isolation: worktree`를 둔다 (`CLAUDE.md:85-105,163-188`; `plugins/common/rules/agent-system.md:44-56,117-124`).
3. `agent-system.md`의 roster를 갱신할 필요가 있어 보인다(그 문서가 roster SSOT라고 선언). 이 규칙을 바꾸면 `CHECKSUMS.sha256` 및 장문 미러도 동기화해야 한다 (`docs/conventions/rules-mirror.md:1-16`; `CLAUDE.md:371-372`). 다만 CLAUDE의 “Adding a New Agent” 절은 이 업데이트를 언급하지 않는다.
4. `verify-done.sh`가 요구하는 agent tier 분류와 coverage를 반영한다. 새 agent에 eval 시나리오가 반드시 필요한지, 어떤 tier로 분류할지는 현재 문서만으로 완전히 답할 수 없다. `evals/README.md:208-220`은 시나리오를 추가할 때의 디렉터리·fixture·task·assertion·검증 절차를 제공한다.
5. 새 agent는 minor version 변경 대상이다. matching `CHANGELOG.md` 항목을 만들고, 버전 변경에 따라 Codex·Antigravity target manifests를 재생성·확인한다. 여기서 버전 변경 명령은 `docs/conventions/release-process.md:10-14`와 `CLAUDE.md:384-387`이 다르게 안내한다. `packaging/README.md:45-58`은 버전 변경 때 생성 타겟을 다시 만들고 `--check`를 게이트에 맡긴다고 설명한다.
6. `scripts/verify-done.sh`와 전체 행동 eval을 통과시킨다. `evals/README.md:16-20,243-248`은 전체 행동 eval이 API 비용이 있는 수동 릴리스 전 게이트라고 구분한다. 완료 게이트 출력의 수동 attest 항목도 별도로 수행해야 한다.
7. 배포할 커밋에 `vX.Y.Z` 태그를 붙이고 push한다 (`CLAUDE.md:373-382`; `docs/conventions/release-process.md:34-37`). 직접 marketplace는 업데이트 시 main HEAD를 반영한다. Claude 디렉토리 경로는 push 후 스캔을 거쳐 전파되고, OpenAI 공개 디렉토리는 문서상 검토 중이며 로컬/Git marketplace 설치는 가능하다 (`CLAUDE.md:389-405`; `README.md:195-198`).

**막힌 지점:** 추가 절차에서 roster/eval tier/coverage 등록 파일과 새 agent의 eval 의무를 특정하지 않는다. 버전 갱신 명령도 수동 편집 예시와 자동 helper 사이에서 모순된다. 따라서 실제 agent 작업을 시작한다면 이 두 결정을 먼저 유지보수자에게 확인해야 한다.

### 4. Codex에서 얻는 것과 못 얻는 것

- **얻는 것:** native Codex plugin 설치; 15개 skill 인식; 프로젝트에 export된 `AGENTS.md`가 있으면 portable 규범을 읽고, hook trust 승인 후에는 `SessionStart`에서 규범과 ledger digest가 주입됨; `session-start`와 `auto-format` hook 제공; child marker와 durable plan/checklist는 git 파일 기반으로 계속 사용. 위임을 요구하는 일부 skill은 같은 계약을 현재 세션에서 실행하는 강등 절차가 있다 (`README.md:96-198`; `plugins/common/skills/harness-export/SKILL.md:15-33,153-173`; `plugins/common/skills/auto-dev/SKILL.md:79-84`).
- **못 얻는 것:** dedicated subagent 실행·agent별 model/effort 적용이 없다(에이전트 파일은 패키지에 있어도 Codex가 subagent로 노출하지 않음); `PreToolUse` 자동 차단이 없고 `protect-sensitive`와 `stop-validator`는 Codex 배포 대상이 아님; MCP 서버는 킷이 제공하지 않음; hooks는 trust 승인 전 조용히 건너뛰므로 이때는 `AGENTS.md`가 유일한 규범 경로; eval harness는 현재 Claude Code만 구동한다 (`README.md:104-142,161-180,182-198`; `plugins/common/skills/harness-export/SKILL.md:163-173`).
- **설치 조건:** local/Git marketplace 경로는 문서에 있지만 공용 OpenAI/Codex plugin directory 제출은 미완료로 기록되어 있다 (`README.md:146-159,195-198`).

## (e) 가장 먼저 고칠 문서 3개

1. **`CLAUDE.md`** — 최고 우선순위 안내 문서다. agent-creator의 용도를 바로잡고, roster/eval/count 갱신과 릴리스 전 행동 eval을 추가하며, 버전 변경 helper를 단일 경로로 안내해야 한다.
2. **`docs/architecture/phase-gate-pattern.md`** — 현재 hook이 자동 phase gate를 시행한다고 읽히는 주장을 없애거나 역사 문서로 명확히 표시해야 한다.
3. **`docs/conventions/release-process.md`** — 실제 bump helper, 타겟 manifest 재생성, 행동 eval, gate 및 tag/push 요구사항을 하나의 일관된 릴리스 흐름으로 연결해야 한다. CLAUDE와 같은 버전 갱신 문구를 유지해야 한다.

추가 편집 후보로 `README.md:3-5,509`의 하네스 포지셔닝과 manifest 등록 표현을 정리하면 콜드 리딩 혼란을 줄일 수 있다.
