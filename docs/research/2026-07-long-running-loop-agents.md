# 장기 실행·루프 AI 코딩 에이전트 — 하네스 설계 딥리서치

> 2026-07-03 · claude-code-kit 리서치 노트 (2차)
> 5개 병렬 리서치 에이전트(Initializer-Executor / 상태 영속화 / 루프 내 검증 / 인접 구현체 / 실패모드) 결과를 교차검증해 종합.
> 목적: Initializer-Executor식 durable environment를 kit의 Work 시스템 위에 얹는 설계 근거.

## TL;DR

- **핵심 통찰**: 장기 실행의 병목은 컨텍스트 윈도우 크기가 아니라 **디스크에 영속화된 상태(external memory) + 매 세션 결정론적 재적재**다. 에이전트는 "이전 기억 없는 교대 근무자"로 취급한다.
- **Initializer-Executor 패턴**(Anthropic): `initializer`가 1회 durable environment(feature 체크리스트 JSON·init.sh·progress 로그·초기 커밋)를 구축하고, `executor`가 fresh context로 반복 소환되어 상태 복원→한 feature 전진→검증→커밋→progress 갱신.
- **JSON > Markdown for state**: 모델이 JSON을 부적절하게 덮어쓸 확률이 낮아 진행 플래그(`passes`/`status`)는 JSON에, 서술 계획은 마크다운에.
- **검증**: "작성자 에이전트는 오염됐다" — 검증은 세션 분리 + 결정론적 게이트 + (가능하면) 다른 model family. Agent-as-a-judge가 LLM-as-judge를 능가하며 human baseline만큼 신뢰.
- **실패 방어 4축**: disposable context / bounded durable workspace / machine-checkable verification / hard caps(iteration·token·wall-clock).

---

## 1. Initializer-Executor 패턴 (Anthropic)

원전: [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) (2025-11), 후속 [Harness Design for Long-Running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps) (2026-03), 공식 repo [anthropics/cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents).

**initializer가 1회 만드는 것:**

| Artifact | 형식 | 역할 |
|---|---|---|
| `feature_list.json` | JSON 배열 (`category`,`description`,`steps[]`,`passes:false`) | 초기 프롬프트를 end-to-end feature 체크리스트로 확장 (예제는 200+ 항목) |
| `init.sh` | 실행 스크립트 | dev server 기동 + 기본 E2E smoke |
| `claude-progress.txt` | append-only 로그 | 이전 인스턴스 행적 (lab notes) |
| 초기 git 커밋 | git | `git log`가 두 번째 상태 채널 |

**executor 루프(매 세션, no-memory):** ① `pwd`+`progress`+`git log`+`feature_list` 읽어 상태 복원 → ② `init.sh`로 환경 검증(smoke) → ③ `passes:false` 최우선 **한 feature만** 구현 → ④ 브라우저 자동화(Puppeteer MCP)로 human-level E2E 검증 → ⑤ `passes:true`로만 변경·커밋·progress 갱신 후 종료.

**왜 compaction만으론 부족한가**: 요약은 detail 손실 → 구조화 handoff 파일로부터의 **full context reset** 필요. compaction 없을 때 실패 3형: one-shot 시도, 조기 완료 선언, 토큰 낭비. **test ratchet**(테스트 삭제·편집 금지)로 "실패 테스트 지워 통과" 방지. ※ 원문에 정량 벤치마크 없음(유일 수치 "200+ features") — 정성적 주장으로만 존재.

**공식 후속(2026-03)**: planner/generator/evaluator triad, sprint 계약, grading rubric, fresh-context evaluator 서브에이전트(Write 없음, PASS/NEEDS_WORK), hooks(`verify-gate`·`commit-on-stop`·`kill-switch`·`steer`).

**오픈소스 등가물 — Ralph loop** (Geoffrey Huntley, [ghuntley.com/ralph](https://ghuntley.com/ralph)): `while :; do cat PROMPT.md | agent; done`. `prd.json`+`progress.txt`+`AGENTS.md`. snarktank/ralph(Ryan Carson)은 "1 스토리 = 1 컨텍스트 윈도", 기본 10 iteration 캡, git tag가 완료 게이트.

---

## 2. 상태 영속화 기법과 트레이드오프

**File/Git 기반 (클라이언트 주도):**
- **git = source of truth**: 커밋/태그 체크포인트로 bad state revert.
- **progress(append-only) + JSON feature checklist(`passes`) + init.sh**: 세션 핸드오프 최소 3종.
- **AGENTS.md = 절차적 기억**: 매 iteration 함정/패턴 누적(Patterns·Gotchas·Learnings), 단 주기적 아카이빙으로 bloat 방지. "각 개선이 미래 개선을 더 쉽게."
- **filesystem-as-context > vector/RAG** (Manus): 가역 압축(내용은 버리되 경로/URL은 남김). "10스텝 뒤 뭐가 중요할지 예측 불가 → 모든 비가역 압축은 리스크." 코드/기술문서는 semantic 검색 부적합. todo.md recitation으로 목표를 attention에 유지.

**Server-side (모델 주도, Anthropic):**
- **memory tool** `memory_20250818` (GA): view/create/str_replace/insert/delete/rename. path traversal 방어 필수.
- **context editing** `clear_tool_uses_20250919`: 오래된 tool 결과 제거(`keep`,`clear_at_least`,`exclude_tools:["memory"]`).
- **compaction** `compact_20260112`: 요약 후 컨텍스트 재초기화(서버사이드 권장, 클라이언트사이드 deprecated).
- memory+context editing 결합 시 내부 벤치 **토큰 84%↓·성능 39%↑**. 단 compaction=비가역 요약 손실 리스크.

**선택 가이드**: 다중 세션 SW 개발+사람 머지 게이트 → file/git 기반. tool 잦음+정밀 제어 → context editing. 세션·일 넘나드는 자율 → compaction+memory 병행. 상호 배타 아님, 상보적.

출처: [Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus) · [LangChain filesystem](https://www.langchain.com/blog/how-agents-can-use-filesystems-for-context-engineering) · [context editing docs](https://platform.claude.com/docs/en/build-with-claude/context-editing) · [snarktank/ralph](https://github.com/snarktank/ralph)

---

## 3. 루프 내 검증 (Author ≠ Verifier)

**핵심 명제**: "코드를 작성한 에이전트는 오염됐다. 자기가 뭘 만들었는지 알아서 합리화한다." Self-review 실패 3메커니즘: hallucinated correctness / error reinforcement / context blindness. 8+ 독립 출처 수렴.

- **세션 분리**가 구조적 해법: fresh AI session이 conversation drift 제거 + artifact-only 평가(Critic은 spec+diff만, builder 변명 못 봄). 실증: 테스트 다 통과하는데 아키텍처 계약("1k+는 DB단 필터")을 조용히 위반한 코드를 fresh Critic이 잡음.
- **Agent-as-a-judge > LLM-as-judge** ([Zhuge et al. arXiv 2410.10934](https://arxiv.org/abs/2410.10934), ICML 2025): 도구로 궤적 전체에 intermediate feedback, human baseline만큼 신뢰. DevAI 벤치(55 태스크).
- **Self-preference bias** ([arXiv 2410.21819](https://arxiv.org/html/2410.21819v2)): 판사가 자기/동족 모델 출력을 품질 무관하게 선호(낮은 perplexity). 해법 = **다른 model family judge / 이질 패널 다수결**(Council Mode). "크기가 아니라 다름."
- **결정론+확률론 2층 게이트**: Quality gate(문법·lint·test)를 확률적 Review gate(의미·spec·아키텍처)가 backing. **negation blindness**(LLM이 "DO NOT" 제약에 둔감, [arXiv 2306.08189](https://arxiv.org/abs/2306.08189)) 때문에 Critic 단독 불가.
- **DoD = 기계 검증 가능한 계약**: metric·schema·judge model id·rubric까지 git에 pin. cascading gate(값싼 결정론 floor + 필요시 비싼 LLM judge).
- **verify-loop 4원칙**: named(기계 체크) / fast(서브초) / aligned(acceptance criteria) / raw(원시 stdout·exit code가 완료 결정). "No PASS without proof."
- **Santa Method**: 두 리뷰어 병렬 spawn, context isolation, 동일 rubric, "한 명만 잡아도 실제 이슈." 각 라운드 fresh agent로 앵커링 회피.

---

## 4. 실패 모드와 완화

| 실패 모드 | 메커니즘 | 완화 |
|---|---|---|
| **Context rot** | attention 확산(n²·RoPE decay), 아키텍처 속성 → 큰 윈도우로 안 풀림 | just-in-time retrieval, 핵심을 처음/끝 배치, tool 결과 clearing |
| **Context poisoning/confusion/clash** | 환각 재참조, tool overload, 상충 정보 누적(샤딩 시 39%↓) | sources of truth 재앵커링, 동적 tool 로딩, 오염 컨텍스트 quarantine |
| **Drift** | fresh 루프가 자기 요약 의존해 원 의도 이탈 | **매 iteration SPEC 원본 재주입**, 1 feature+acceptance, 기계 검증 완료, 기계적 작업에 한정 |
| **Durable env pollution** | progress/AGENTS.md가 stale·모순 → 미래 세션 오도 | bounded 소형 역할분리 파일, AGENTS.md=짧은 체크리스트, plan은 scaffolding(repo에서 재생성), git-clean 게이트 |
| **무한 루프** | fuzzy exit, thrashing, stop-hook 재차단 | **`stop_hook_active` 조기 return**, hash(tool+args) no-progress 감지, two-tier escalation, hard caps |
| **비용 폭증** | tool call마다 컨텍스트 재전송(10–100x) | scheduled compaction(10–15콜마다 22.7%↓) vs isolation, per-run token/cost/wall-clock cap |

출처: [Chroma Context Rot](https://research.trychroma.com/context-rot) · [Breunig, How Contexts Fail](https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html) · [tessl Ralph 비판](https://tessl.io/blog/unpacking-the-unpossible-logic-of-ralph-wiggumstyle-ai-coding/) · [Bustamante](https://nicolasbustamante.com/blog/long-running-agent-engineering)

---

## 5. 인접 구현체 — 차용 vs 안티패턴

| 시스템 | 차용할 것 | 피할 안티패턴 |
|---|---|---|
| **spec-kit** | 에이전트 불가지론 마크다운 체인, `[P]` 병렬 마커, taskstoissues 브리지 | 동등 peer 파일 divergence(authority 없음), one-shot 재개 부재 |
| **BMAD** | story-packet(자기완결 핸드오프), ready-for-review≠done 게이트 | 역할별 무거운 핸드오프 오버헤드(front-heavy, 작은 작업엔 마찰) |
| **Task Master** | **MCP query-on-demand**(전체 로드 X), `testStrategy` 필드, 의존성 unblocking | tasks.json↔태스크파일 이중표현 drift(수동 regen) |
| **SWE-agent** | ACI 설계(LM 중심 최소 명령, 히스토리 curate) | 상태를 셸/컨텍스트에만(재시작 시 chat-only 복구 8–13%) |
| **OpenHands** | outer loop(무인 toil→PR-as-output), blast radius 축소 | 루프 재진입 상태머신 취약(finished→idle dispatch 누락) |
| **Cursor bg agents** | durable execution(Temporal)+상태를 실행머신서 분리, "짧게 종료 워크플로우 다수", worktree/PR | "eternal" 단일 장기 루프(업그레이드·복구 곤란) |
| **Amp** | **beads**(갱신형 PROGRESS.md 대신 history 보존 구조화 단위), Oracle(파일 접근 없는 독립 리뷰어), thread<10% 컨텍스트 | 갱신형 PROGRESS.md 의존(history 유실, "AI slop 부채") |

---

## 6. kit 통합 권고 — 무엇을 재사용하고 무엇을 추가하나

claude-code-kit은 이미 이 지형의 상당 부분을 **네이티브-우선**으로 갖고 있다. 원칙은 "중복 재구현 금지, 의견 레이어만 추가".

### 이미 있음 (재사용 — 새로 만들지 말 것)

| 연구가 말하는 것 | kit의 대응물 |
|---|---|
| append-only progress 핸드오프 | Work 시스템 `progress.md` (`docs/works/`) |
| AGENTS.md 절차적 기억(gotchas 누적) | `feedback_ledger.py` → session-start `=== LESSONS ===` 주입 |
| 매 세션 sources of truth 결정론적 재적재 | `session-start.py`(rules+Work 상태+ledger digest 주입) |
| DoD=기계 검증 계약, cascading gate | `scripts/verify-done.sh` + `rules/definition-of-done.md` |
| stop-hook 게이트 + `stop_hook_active` 가드 | `stop-validator.py` (연구가 "필수"라 한 가드 이미 구현) |
| Author≠Verifier / 세션 분리 | `review-code`(별도 에이전트, `disallowedTools:[Task]`) + `isolation:worktree` |
| Ralph loop / 배치 자율 완주 | `auto-dev` 배치 드라이버 + `rules/loop-engineering.md` |
| worktree/PR 격리 | `rules/parallel-worktree.md` (W-011) |

### 없음 (추가 후보 — 이번 로드맵)

1. **JSON 테스트게이트 체크리스트 (`passes` 플래그)** — 가장 큰 갭. 현재 계획은 서술형 `planning-results.md`뿐. 연구 컨센서스는 "JSON>MD for state". plan-task가 durable하게 `features.json`(항목별 `passes:false`+acceptance criteria)를 생성 = **initializer 역할**. (kit의 Task 시스템과 겹침 여부는 설계 시 판단 — 중복 회피.)
2. **Executor 루프 규율 명문화** — "1 세션 1 feature + SPEC 원본 재앵커(요약 아님) + E2E 검증 통과 전 `passes:true` 금지". auto-dev/rules에 반영.
3. **Fresh-context evaluator 분리 명시** — review-code가 작성 세션과 분리된 컨텍스트(가능하면 다른 model family)에서 돎을 규칙화. self-preference bias 문헌 근거.
4. **Loop guard 강화** — `stop_hook_active` 위에 hash(tool+args) no-progress 감지 + idle(최근 N iteration 새 커밋 0) 종료. loop-engineering 종료 가드 보강.
5. **Anti-pollution 규율** — progress bounded/append-only, plan은 scaffolding(repo에서 재생성), git-clean 완료 게이트.
6. **(소) Bash 편집 .py 검증 커버리지** — stop-validator 세션 스코프가 Edit/Write만 감지 → 루프에서 Bash로 쓴 .py 우회. (W-012 잔여, 루프 관점서 유효.)

### 피해야 할 안티패턴 (연구가 경고, kit이 이미 회피 중이거나 주의)

- BMAD식 역할별 무거운 핸드오프 → kit "scale-appropriate primitives"가 이미 회피.
- 갱신형 PROGRESS.md만 의존(history 유실) → JSON 플래그+git 커밋 이력으로 보완.
- 동등 peer 파일 divergence(spec-kit) → planning-results를 authority로, 체크리스트는 파생.
- "eternal" 단일 장기 루프 → auto-dev의 "짧게 종료+배치" 접근 유지.

---

## 핵심 출처

- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://www.anthropic.com/engineering/harness-design-long-running-apps
- https://github.com/anthropics/cwc-long-running-agents
- https://ghuntley.com/ralph · https://github.com/snarktank/ralph
- https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
- https://www.langchain.com/blog/how-agents-can-use-filesystems-for-context-engineering
- https://platform.claude.com/docs/en/build-with-claude/context-editing
- https://arxiv.org/abs/2410.10934 (Agent-as-a-Judge) · https://arxiv.org/html/2410.21819v2 (Self-Preference Bias)
- https://asdlc.io/patterns/adversarial-code-review · https://arxiv.org/abs/2306.08189 (negation blindness)
- https://research.trychroma.com/context-rot · https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html
- https://github.com/eyaltoledano/claude-task-master · https://ampcode.com/manual · https://cursor.com/blog/cloud-agent-lessons
