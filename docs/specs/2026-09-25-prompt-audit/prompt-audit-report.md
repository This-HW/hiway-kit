# Prompt Audit — hiway-kit (2026-09-24)

## 가정 (Step 0)

- **범위**: 레포 전체 프롬프트 표면 — `plugins/common/agents/**` (32), `plugins/common/skills/**` (29 파일),
  `plugins/common/rules/*.md` (14), SessionStart 훅이 주입하는 텍스트(`session-start.py`, `using-hiway-kit`),
  `CLAUDE.md`, `evals/run.py` 요청 구성. Anthropic SDK 직접 호출 코드는 없음.
- **타깃 모델**: frontmatter 가 `opus`/`sonnet`/`haiku` 별칭을 쓰므로 현 세대 — **Claude Opus 5.5**(메인·opus 에이전트),
  Sonnet 5, Haiku 4.5. 비-Anthropic 프로바이더 표식 없음.
- **Provenance**: 이 레포는 규칙마다 근거·실측을 적어 두는 관례가 있어, 근거는 context 로 보존하고(keep #1)
  근거 없는 명령·폐기된 메커니즘·레포 전용 경로만 찾았다.

## 요약

| 그룹 | 건수 | 성격 |
| --- | --- | --- |
| G1a 압박 언어 | 6 | `1%라도`, `⚠️ 반드시 위임하세요!`, `설명하지 말고`, reasonless ALWAYS/NEVER |
| G1b API로 대체된 스캐폴드 | 3 | judge `SCORE:` 정규식, Sequential Thinking 유도, 토큰 % 계산 |
| G1c 과잉 명세 / 골드 예시 | 8 | 채워진 "포인트 시스템" 예시, 지어낸 성공률, 결정론적 관점 선택 스크립트 |
| G1d 화석 | 7 | 폐기된 delegation signal 인용, 없는 `diagnose` 에이전트, 없는 참조 파일 |
| G1e 근거 없는 금지 군집 | 3 | code-quality, ssot, planning-protocol 첫 두 줄 |
| G2 스킬/정의 파일 결함 | 14 | 일반 튜토리얼 ~1,300줄, 서로 모순되는 사본, 레포 전용 경로 |
| G3 도구/참조 | 3 | 상대경로 indexLine, 7개 MCP 서버 이름 나열 |
| G4 요청 구성 | 3 | eval 이 `effort` 무시, LLM 으로 테스트 카운트, 출력 계약 부재 |

**가장 영향이 큰 셋** (전부 문장 스타일이 아니라 **기능 결함**이다):

1. **리뷰 계약 3중 불일치** — `review` 스킬이 A~F 형식을 요구해 `review-code` 자체 계약(`## 판정`/`## 완료:`)을
   덮어쓰고, 그러면 스킬 스스로 "`## 완료:` 없음 = 잘림"으로 판정한다. `auto-dev` 는 아무 형식에도 없는
   `decision`/`critical_count` 필드로 게이트한다. 문자 그대로 따르는 모델에서 리뷰 게이트가 구조적으로 성립하지 않는다.
2. **소비자 환경에서 없는 경로를 가리킨다** — 매 세션 주입되는 indexLine 이 cwd 상대 `rules/…` (소비자 프로젝트엔 없음),
   facilitator 의 `.claude/rules/*`, implement-code/review-code/plan-implementation 의 `references/*.md`(존재한 적 없음),
   `debug` 의 `subagent_type: diagnose`(에이전트 없음), web-research/research-external 의 사라진 SSOT 절,
   DoD 의 `scripts/verify-done.sh`, 스킬 3곳의 `./scripts/checklist.sh`·`feedback.sh`.
   maxTurns 10 에이전트가 없는 파일을 찾느라 턴을 쓰면 리포트 유실(이미 실측된 실패)로 이어진다.
3. **위임 불가능한 에이전트에게 위임을 외친다** — `disallowedTools: [Task]` 인 leaf 5종에
   "⚠️ 반드시 verify-code로 위임하세요!". 할 수 없는 명령은 "위임합니다" 서술로 끝나는 반환값을 만든다.

## 발견 (신뢰도 순)

형식: **위치** — 증거 · 패턴 · 이유 · 조치. 전부 원문 대조 확인했다(★ = 직접 재확인).

### High

| # | 위치 | 증거 | 패턴 | 이유 → 조치 |
|---|---|---|---|---|
| H1★ | `skills/review/SKILL.md:284-292`, `skills/auto-dev/SKILL.md:283-284` | `## 전체 평가: [A/B/C/D/F]` / `decision 필드 == ACCEPT` | G2 모순 사본 | review-code 계약과 충돌·없는 필드로 게이트 → review-code 형식 위임, 게이트를 `## 판정:`/`## 완료:` 로 **rewrite** |
| H2★ | `skills/debug/SKILL.md:77` | `subagent_type: diagnose` | G1d 화석 | 없는 에이전트 → `fix-bugs`(진단 전용 지시) **rewrite** |
| H3★ | `hooks/session-start.py:297` + `rules/agent-*.md` indexLine | `rules/agent-delegation-chain.md 를 읽어라` | G3/G2 경로 | 소비자 cwd 에 없음 → 플러그인 절대경로로 렌더 **rewrite**(+테스트) |
| H4★ | `agents/dev/review-code.md:136`, `implement-code.md:36,64`, `plan-implementation.md:66-67` | `references/checklist.md`의 공격 매뉴얼 로드 | G2 휘발 | 없는 파일 → 인라인 절 참조 **rewrite** |
| H5★ | `agents/meta/facilitator.md:179-203,217-220` | `.claude/rules/planning-protocol.md` | G2 휘발 | 소비자에 없음 + 출처 없는 "46% 절감" → **remove** |
| H6★ | `skills/web-research/SKILL.md:76`, `agents/dev/research-external.md:85` | `using-hiway-kit 스킬의 "비신뢰 텍스트 취급" 절` | G1d | 그 절 없음(규칙은 `rules/untrusted-text.md`) → **rewrite** |
| H7★ | `skills/skill-forge/SKILL.md:70-71,85`, `self-improve/SKILL.md:71-72` | `→ delegation signal` | G1d 화석 | W-022 에서 폐기된 메커니즘을 **생성 템플릿**이 계속 복제 → **remove/rewrite** |
| H8 | `skills/brainstorming:18-20`, `plan-task:40-42`, `auto-dev:71-73,258-259` | `./scripts/checklist.sh 기반` | G2 모순 사본 | 자기 SSOT(`task-tools-fallback.md`)가 "레포 전용"이라 경고하는 경로 → SSOT 포인터로 **rewrite** |
| H9★ | `skills/using-hiway-kit/SKILL.md:8` (매 세션 주입) | `스킬이 1%라도 있으면 먼저 invoke` | G1a 부스터 | 능동적 모델 + brainstorming HARD-GATE → 사소한 요청 과잉 발동 → **rewrite** |
| H10 | `rules/code-quality.md` (core, 주입) | `ALWAYS under 20 lines/3 params` … `NEVER … log-only` | G1e/G1f | 근거 없는 수치 clamp 9개; 킷 자체 훅의 의도된 fail-open 과 모순 → 근거 있는 산문 **rewrite** |
| H11 | `rules/planning-protocol.md:8` | `NEVER implement based on assumption. ALWAYS … ask` | G1a + 모순 | 바로 아래 P1(기본값 진행)/P3(자율) 과 충돌 → 과잉 질문 → **rewrite** |
| H12 | `rules/{definition-of-done,loop-engineering,feedback-loop,parallel-worktree}.md` | `(Spec 6 / W-010)` 등 | G2 역사 | 소비자에겐 해석 불가 + 소비자 `W-XXX` 네임스페이스와 충돌, 주입 예산 소모 → **remove** |
| H13 | `rules/mcp-usage.md:18` | `Sequential Thinking — complex multi-step design` | G1b | 항상-사고 모델에 외부 think 도구 유도 = 과잉 계획 → **remove** |
| H14★ | `agents/dev/{implement-code:102,fix-bugs:290,verify-code:267,verify-integration:344,write-tests:262}` | `⚠️ … 반드시 verify-code로 위임하세요!` | G1a+G1d | Task 없는 leaf 에 불가능한 명령 → "다음 권장: X" 한 줄 **rewrite** |
| H15★ | `agents/dev/implement-code.md:141-431` (~290줄, 파일의 65%) | `src/features/[기능명]/`, React Query/Zustand | G2 일반지식 | React 레이아웃을 모든 소비자 스택에 강요 → **remove** |
| H16★ | `agents/dev/git-workflow.md:35-136,178-270` | `git rebase -i HEAD~N`, `git stash pop`, `rm -rf …; worktree prune` | G2/G1c | 에이전트에서 실행 불가·공유 stash 위험 명령을 예시로 → **remove**(충돌 프로토콜·위험 명령·출력은 유지) |
| H17 | `agents/dev/enforce-structure.md:82-134` | `src/widgets/` … `*.md (루트 제외) → 금지` | G2 자유도 | yaml 없을 때 FSD 레이아웃을 기본 규칙으로 → 소비자에 거짓 Critical → 지배적 관례 기준 **rewrite** |

### Medium

| # | 위치 | 증거 | 패턴 | 조치 |
|---|---|---|---|---|
| M1 | `agents/dev/review-code.md:600-788` (~190줄) | `### God Object`, `### Callback Hell` | G2 일반지식 | **remove** (공격 매뉴얼·우선순위 표는 유지) |
| M2 | `backend/write-api-tests:34-210`, `implement-api:42-130`, `optimize-logic:35-139`, `backend/design-services:32-98`, `planning/define-metrics:32-124`, `dev/security-scan:94-151`, `dev/write-tests:130-174`, `dev/plan-implementation:203-285` | Jest/Prisma 스위트, SOLID, Four Golden Signals, O(n²) 예시 | G2 일반지식 | **remove** + "프로젝트 기존 패턴을 따른다/근거를 단다" 한 줄 |
| M3 | `impact-analyzer:246+`, `synthesizer:175+,233+`, `consensus-builder:370+`, `manage-api-versions:61+`, `analyze-tech-debt:89+` | `총 비용: 23일`, `분석일: 2026-01-30` | G1c 골드 예시 | "형식 예시 — 값 복사 금지" 라벨 **rewrite**; 추세·점수 계산 절 **remove** |
| M4 | `define-business-logic.md:203-365` | 이메일/주문/RBAC/환불 5종 예시 | G1c | STATE-001 하나만 라벨 달아 유지, 나머지 **remove** |
| M5 | `consensus-builder.md:167,172` | `성공률: 60%` | G1c 지어낸 수치 | **remove** |
| M6 | `facilitator.md:135-173` | `if "사용자" in doc …` | G1c 자유도 | 판단 기준 한 줄로 **rewrite** |
| M7 | `clarify-requirements.md:342` | `불확실하면 P0으로 취급` | G1a default-to | 판별 기준으로 **rewrite** |
| M8 | `verify-code, verify-integration, impact-analyzer, synthesizer, plan-refactor, research-external, manage-api-versions` | (출력 계약 절 없음) | G2 계약 누락 | security-scan 이 이미 재현한 빈 반환 → 3줄 계약 **add** |
| M9 | `verify-code.md:27` | `15 tool calls 내에` (frontmatter maxTurns 10) | G1d | **rewrite** |
| M10 | implement-code/review-code/plan-implementation 출력 계약 서두 | `위임 신호 규격을 문서 중간에 두면` | G1d | 현재 규칙 한 줄로 **rewrite** |
| M11 | `manage-api-versions.md:54-57,165-171` | `이 킷은 에이전트별 버전을 관리하지 않는다` | G2 레포 내부 | **remove** |
| M12 | `generate-boilerplate.md:37-157` | 필수 frontmatter 없는 에이전트 템플릿 | G2 모순 | agent-creator/skill-creator 로 위임 **rewrite** |
| M13 | `skills/review:10`, `debug:13`, `test:10` | `설명하지 말고 바로 실행합니다` | G1d 업데이트 억제 | 단계 전환 한 줄 알림으로 **rewrite** |
| M14 | `brainstorming/SKILL.md:11` | `작업이 단순해 보여도 예외 없음` | G1a | 승인 게이트는 유지, 근거 붙여 **rewrite** (체크리스트 Task 규율은 실측 근거 있어 유지) |
| M15 | `multi-perspective-review/SKILL.md:145-156, 283-307, 313-322` | `--auto-fix`(미구현), `모델: sonnet`(실제 opus), `80% → 범위 축소` | G2/G1b | **remove/rewrite** |
| M16 | `self-improve:33`, `eval-forge:11`, `harness-export:169` | `(현재 review-code·fix-bugs·implement-code)`, `33개`/`33종` | G2 휘발 | 실제 커버리지 29/32 → 판정 규칙으로 **rewrite** |
| M17 | `skills/test/SKILL.md:89-103` | verify-code(haiku)로 통과/실패 수 세기 | G4 결정론적 단계에 LLM | 러너 요약줄·rc 직접 읽기로 **rewrite** |
| M18 | `control-loop/SKILL.md:172-175` | `같은 날 이 세션도…` | G2 역사 | 1인칭 고고학만 **remove** (규칙·실측 근거는 유지) |
| M19 | `rules/ssot.md:12-13` | `ALWAYS route all errors through a single central handler` | G1e | 모든 소비자에 에러 아키텍처 강요 → **rewrite** |
| M20 | `rules/definition-of-done.md:9,29` | `scripts/verify-done.sh` / `응답 직전 … 조회` | G2 / G1f | 소비자 일반화 + 마감 보고 시점으로 **rewrite** |
| M21 | `rules/loop-engineering.md:12` | `대화형 전용 네이티브 트리거는 스킬에서 못 쓴다` | G2 휘발 API 주장 | 헤딩 단순화 **rewrite** (근거는 CLAUDE.md 에 있음) |
| M22 | `rules/mcp-usage.md:66-69` | `Regression guard … checked by scripts/verify-done.sh` | G2 메인테이너 내용 | **remove** (CLAUDE.md Contributing 에 동등 항목 있음) |
| M23 | `rules/task-resume.md:62-63` | `2개 이상 → Agent 동시 dispatch` | 모순 사본 | parallel-worktree 의 파일 겹침 전제 **rewrite** |
| M24★ | `evals/run.py:1154-1178` | `'SCORE: <정수>' 형식으로만` + `re.search` | G1b | `--json-schema` → `structured_output`(실측 확인) **replace-with-API-feature**; 비신뢰 프레이밍 추가 |
| M25★ | `evals/run.py:187-205` | effort 미전달 | G4 | Opus 5.5 에선 effort 가 유일한 깊이 제어 → frontmatter `effort` 를 `--effort` 로 **add** |
| M26 | `CLAUDE.md:197` | 오케스트레이션 표 vs `coordination.md` | 모순 사본(개발 세션 전용) | 표가 소비자 모델임을 명시 **rewrite** |

### Low / flag (diff 없음)

- `review-code.md:28-33` "이 코드는 결함이 있다. 아직 찾지 못했을 뿐" — effort:max 에서 결함 날조 압력 가능. 재작성 후보:
  "배포하면 안 되는 구체적·재현 가능한 이유를 찾는다. 없으면 [ACCEPT]가 정답이다." **eval 로 확인 후 결정.**
- `mcp-usage.md:11-39` 7개 MCP 서버명 나열(G3) — 원칙만 남기는 재작성 가능하나 conditional tier 라 영향 작음.
- `verify-integration.md:71-200`, `analyze-domain.md:34-81` — 감사자는 일반지식으로 봤으나 **검증 방법(grep 패턴)·분석 절차**라 저자 고유 내용으로 판단, 유지.
- `write-api-tests`↔`write-tests`, `implement-api`↔`implement-code` 로스터 중복(G4) — 통합은 별도 설계 결정.
- 스킬 전반의 `Task tool 사용:` + per-call `model:` 핀 — 호스트 도구명은 `Agent`, 모델은 frontmatter 소유. 다음 수정 시 정리.
- `CLAUDE.md` Delegation Signal·agent-lifecycle·드리프트 게이트 절의 날짜 서술 — 개발 세션 전용, 근거 서술이 레포 관례라 유지.
- `impact-analyzer`/`synthesizer` 의 "Task tool 사용 금지" 불릿 — allowlist 가 이미 강제. 무해.

## 제안 diff

`prompt-audit.patch` (49 파일, +154 / −1,943 프롬프트 줄 + 코드·테스트). `git apply --check` 통과.
발견 1건 = 대체로 hunk 1개. 과감한 블록 삭제(M1·M2·H15·H16)는 hunk 단위로 골라 받을 수 있다.

**scratch 에서 검증한 것**: ruff green (`run.py`, `session-start.py`); `test_session_start.py` 46 passed;
`evals/tests` 122 passed. diff 가 바꾼 테스트 2건: indexLine 절대경로 기대값, DoD 마커(`verify-done.sh` → `# Definition of Done`),
judge 픽스처(`structured_output`). 상시 주입 core 룰 합계 **−351 B**.

## 적용 시 따라와야 하는 것 (패치에 포함 안 됨)

1. 룰 변경 → `plugins/common/rules/CHECKSUMS.sha256` 재생성, 미러(`docs/architecture/rules/{code-quality,ssot,planning-protocol,mcp-usage,task-resume}.md`) 손본 뒤 `scripts/sync-rule-mirror.sh --regenerate`.
2. 버전 범프(minor 권장 — 에이전트 행동 변경) + CHANGELOG + `scripts/build-targets.py --write`.
3. **Step 7 — 제거는 가설이다**: 에이전트 정의 변경은 in-session 으로 검증 불가(캐시). `scripts/run-evals.sh --compare evals/baseline/2026-09-20.json` 으로 29개 커버 에이전트 회귀 확인. 특히 M1(review-code 안티패턴 제거)·H14(위임 문구)는 한 번에 하나씩.
4. `scripts/verify-done.sh` green 확인 후에만 완료 주장.
