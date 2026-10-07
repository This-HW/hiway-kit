---
status: historical
as_of: 2026-10-07
---

# Agensh(오케스트레이터 없는 멀티 에이전트 하네스) — 1차 출처 대조와 흡수 판정

> 조사 시점: 2026-10-07. 기준 커밋 `d60faa0` (v5.4.1). 리서치 전용 문서다 — 코드·규칙·스킬은 바꾸지 않았다.
> 출발점은 theaxlabs.com 2026-09-29 블로그 리뷰(2차 요약)였다. 주장은 하나씩 논문 원문(arXiv HTML·TeX 소스·그림 PDF)과
> 공식 문서로 대조했다. 확인 수준 표기: `[1차 확인]` 원문에서 직접 봤다 · `[2차 출처만]` 블로그에만 있다 · `[확인 불가]` 접근하지 못했다.
> 표에서 **추론**이라고 적은 것은 출처가 아니라 이 조사의 판단이다.

## 요약

1. 블로그가 옮긴 논문 내용은 대부분 맞다. 5단계 루프, Git·채팅·append-only 공유 컨텍스트, 레코드 타입 5종, 100자 상한, 라우터·디스패처·유휴 감지기, 1→128 에이전트 19.31%→28.78% 모두 원문에 있다. 단 100자 상한에는 예외가 있다(`PATCH_SUMMARY` 는 300자). `[1차 확인]`
2. 뒤집히거나 출처가 다른 것: «오케스트레이터는 없애도 검증 오라클은 못 없앤다»와 한계 목록 전체는 **블로그의 해석**이다. 논문에는 Limitations 절이 없다. Claude Code 적용법(`board.py`·훅·환경변수)도 전부 블로그가 만든 것이다. 논문 코드 저장소는 2026-10-07 현재 404다.
3. 실험 조건: 모델은 GPT-5.6-sol(high) 하나, 하네스는 Copilot 하나다. 예산은 6시간이고, 반복 실행·분산·비용 보고는 없다. 과제별로 보면 스케일 효과가 단조롭지 않다(ctags 1→8 에이전트 25.82→18.47). **오케스트레이터 기반 비교군도 없다.** `[1차 확인]`
4. Claude Code 쪽: agent teams 는 2.1.292 현재도 experimental 이고 기본 꺼짐이다. `TeammateIdle`·`TaskCompleted` 훅은 실재하며 exit 2 로 막을 수 있다. 다만 `TaskCompleted` 는 Task 도구가 있을 때만 발화한다. `[1차 확인]`
5. 킷 판정: 공유 보드 런타임·CLAIM·유휴 훅·오케스트레이터 없는 모드는 **reject/watch** 다. 흡수할 만한 것은 **FAIL(반증된 가설) 레코드를 위임 보고 계약의 필드로 들이는 것 하나**로, `adopt(pilot)` 이다. «오라클 통과로만 완료»는 킷의 `checklist complete` 가 이미 하네스 중립으로 하고 있다.

## 1. 1차 출처 대조표

논문: Zhan, Song, Dong, Huang, Lian, Xia, Wei (Microsoft Research), *Agensh*, arXiv 2609.26781v1 (2026-09-22). 절·그림 번호는 HTML v1 기준이다(그림 라벨은 TeX 소스 기준).

| 블로그 주장 | 판정 | 1차 근거 | 수준 |
| --- | --- | --- | --- |
| 5단계 루프 Gather→Claim→Act→Verify→Merge, 동기화 장벽 없음 | **일치** («barrier»라는 단어는 없고 같은 뜻으로 서술) | §2.1, Fig. 3(`fig:loop`): "executes the following five-step cooperation loop concurrently and asynchronously", "without waiting for all peers to complete an iteration" | `[1차 확인]` |
| 공유 작업공간(Git) + 메시지(채팅) | **일치** | §2.3: "We implement the shared workspace with Gitea … and the message interface with Mattermost" | `[1차 확인]` |
| append-only 공유 컨텍스트, OBSERVED/FACT/FAIL/CLAIM/PATCH_SUMMARY | **일치**. 아이디어는 DeLM 에서 가져왔다고 명시 | §2.2: "append-only database with recent memory" + context grep 도구. "The idea is adopted from DeLM" | `[1차 확인]` |
| 레코드 100자 제한 | **부분 일치** — `PATCH_SUMMARY` 는 300자. 긴 내용은 `detail` 로 접어 두고 `board_unfold` 로 펼친다 | App. A 워커 프롬프트: "Entries are capped (100 chars, 300 for `PATCH_SUMMARY`)" | `[1차 확인]` |
| «FAIL 이 가장 값진 레코드» | **일치하나 출처 위치가 다르다** — 본문 주장이 아니라 워커 프롬프트의 지시문이다 | App. A: "`FAIL` for a hypothesis you falsified (the highest-value entry: it stops peers spending budget on it)" | `[1차 확인]` |
| 라우터 / 디스패처 / 유휴 감지 런타임 | **일치**. 다만 블로그의 «지수 백오프»는 논문에 없다(논문은 "progressively longer"). 유휴 기준은 10분 | App. B.1: "If a worker remains idle for 10 minutes, an idle detector sends a prompt". 메시지·컨텍스트는 턴 시작 시, 또는 턴 중 인프라 도구 결과 뒤에 붙여 전달(App. B.2) | `[1차 확인]` |
| ProgramBench 1→128 에이전트 19.31%→28.78% | **일치**. 중간값은 8개 20.68%, 32개 26.52%. pandoc 은 1,024개 55.06%(Fig. 1) | §3.1, Fig. 5(`fig:scaling`). Table 1 은 저장소 규모뿐이다 | `[1차 확인]` |
| 비단조 스케일 | **사실이나 저자가 언급하지 않았다**. 본문은 "generally increasing trend"라고만 쓴다 | Fig. 5 과제별 값(아래 표) | `[1차 확인]`(그림 수치) |
| 비용 미보고 | **사실**(부재 확인). 토큰·달러 수치가 없다 | 본문·부록 전체 | `[1차 확인]`(부재) |
| 단일 실행 | **추론**: 반복 횟수·시드·분산·오차막대가 어디에도 없다. «1회»라고 명시한 문장은 없다 | 본문·부록 전체 | `[1차 확인]`(부재) / 횟수는 `[확인 불가]` |
| 단일 모델·하네스 | **사실** | App. C: "All reported configurations use `gpt-5.6-sol` with high reasoning effort … We use Copilot as the underlying single-agent harness" | `[1차 확인]` |
| 한계 목록(비용·비단조·단일 실행·단일 모델 등) | **블로그의 분석이다**. 논문에는 Limitations·Threats 절이 없다. 각 항목은 논문과 모순되지 않지만 저자가 적은 것이 아니다 | 절 목록: 1–5 + App. A–C | `[2차 출처만]` |
| «협업 루프는 런타임 코드가 아니라 프롬프트로 구현» | **일치**. 단 메시지 전달·유휴 감지·재시도는 런타임 코드다. «루프는 프롬프트, 전달은 런타임»이 정확하다 | §2.3: "through workflow instructions in each worker's prompt rather than hard-coding the loop into the runtime infrastructure"; 프롬프트는 "exactly the same for each worker except for the worker ID" | `[1차 확인]` |
| «오케스트레이터는 없앨 수 있어도 검증 오라클은 없앨 수 없다» | **블로그의 해석이다.** 논문은 오라클의 필요성을 시험하지도 주장하지도 않는다. 다만 실험 설정에는 강한 오라클이 들어 있다: 모든 워커가 참조 바이너리를 실행해 자기 빌드와 비교할 수 있다(차등 오라클) | §2.1 Verify: "matches its local progress against the sub-task's acceptance criteria"; App. A: "Check your work by running the reference and your build on the same inputs and comparing" | 주장 자체는 `[2차 출처만]`, 설정은 `[1차 확인]` |
| 병합 주체 | (블로그가 강조하지 않은 사실) **워커가 직접 `main` 에 병합하고 충돌도 직접 해결한다** | §2.1 Merge: "If the merge is blocked by a conflict, the worker incorporates the latest peer progress, resolves the conflict, and merges again"; App. A: "You claim what to build, you build it, you merge it" | `[1차 확인]` |
| 오케스트레이터 대비 우위 | **검증되지 않았다.** 결과는 Agensh 의 에이전트 수 스케일링뿐이고, 같은 규모의 오케스트레이터형 비교군이 없다. Related Work 는 Claude Code agent teams 를 "organized around a fixed lead session"이라고 분류만 한다 | §3, §4 | `[1차 확인]`(부재) |
| Claude Code 적용(`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`, `TeammateIdle`/`TaskCompleted` 훅, `board.py`, 3단계 스케일 계획) | **전부 블로그 저작이다.** 블로그 스스로 `board.py` 를 «재구성한 예시»라고 적는다. 논문의 대응물은 MCP 도구 `board_write`/`board_read`/`board_unfold`/`board_grep` 이다(App. A). `board.py` 의 파일 락은 블로그의 발명이다 | 논문에서 Claude Code 언급은 §2.3(어댑터로 연결 가능)과 §4 두 곳뿐이고, Claude Code 로 돌린 실험은 없다 | `[2차 출처만]` |
| 저자·소속 Microsoft Research | **일치** | arXiv abs 페이지 | `[1차 확인]` |
| 코드 공개 | **미공개**. https://github.com/microsoft/Agensh 가 404 를 반환한다. https://aka.ms/Agensh 는 프로젝트 페이지(리플레이)로 연결되며 추가 수치는 없다 | 2026-10-07 접속 | `[1차 확인]` |

### 1.1 Fig. 5 과제별 최종 test-pass rate (%)

출처: 논문 TeX 소스의 그림 PDF(`scaling.pdf`)를 렌더링해서 읽은 값이다. 평균의 재계산값(1 에이전트 19.31)은 본문 수치와 일치한다. `[1차 확인]`

| 과제 | 1 | 8 | 32 | 128 |
| --- | --- | --- | --- | --- |
| **평균(5과제)** | 19.31 | 20.68 | 26.52 | 28.78 |
| FFmpeg | 6.54 | 11.97 | 13.22 | 12.89 ↓ |
| gromacs | 19.69 | 19.37 ↓ | 19.37 | 22.12 |
| pandoc | 33.89 | 41.75 | 43.11 | 50.94 (1,024: 55.06) |
| PHP-src | 10.63 | 11.86 | 12.23 | 12.35 |
| ctags | 25.82 | 18.47 ↓ | 44.69 | 45.62 |

### 1.2 실험 조건 (App. C) `[1차 확인]`

- 과제: ProgramBench(arXiv 2605.03546, 200 과제)에서 가장 어려운 5개. 내용은 참조 실행파일의 동작을 처음부터 재현하는 것이다. 채점은 숨은 행동 테스트(fuzzing 으로 생성)의 "canonical-kept pass rate" 로 한다.
- 예산: 6시간, 인터넷 차단. 에이전트는 처음 1시간 동안 30초마다, 이후 3초마다 하나씩 투입된다. T−45분·T−5분에 리마인더를 보낸다. 1,024 실행은 16노드 × 64 에이전트다.
- 단일 에이전트 기준선에는 6시간을 다 쓰도록 stop hook 을 붙였다(App. C "Single-agent baseline").
- 시간 결과(Fig. 6, `fig:trajectories`): pandoc 에서 30% 를 넘는 시점이 128 에이전트 30분, 32 에이전트 60분, 8 에이전트 90분이다. 1 에이전트는 첫 2시간 안에 넘지 못한다.
- DeLM(arXiv 2606.10662): 중앙 오케스트레이터 대신 "a shared context and a task queue" 를 쓰는 탈중앙 다중 에이전트 연구다. Agensh 의 공유 컨텍스트 개념의 원천이다. `[1차 확인]`

## 2. Claude Code 네이티브 현황

로컬: `claude --version` → `2.1.292 (Claude Code)`. `claude --help` 에는 team·teammate 가 한 줄도 없다. 문서도 "The `--teammate-mode` flag is experimental and doesn't appear in `claude --help`" 라고 적는다. `[1차 확인]`

| 항목 | 현재 상태 | 근거 | 수준 |
| --- | --- | --- | --- |
| agent teams 지위 | **experimental, 기본 꺼짐**. `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`(셸 env 또는 settings `env`)로 켠다. `-p`·Agent SDK 세션에서는 teammate 를 띄우지 않는다 | [agent-teams 문서](https://code.claude.com/docs/en/agent-teams): "Agent teams are experimental and disabled by default." | `[1차 확인]` |
| 도입·변경 이력 | 2.1.32 research preview 로 도입 → 2.1.33 `TeammateIdle`·`TaskCompleted` 추가 → 2.1.69 `continue:false` 지원 → 2.1.84 `TaskCreated` 추가 → 2.1.178 `TeamCreate`/`TeamDelete` 제거("one implicit team") → 2.1.290 서브에이전트·포크에서는 `TeammateIdle` 미발화. 2.1.292 까지 experimental 해제 항목 없음 | [CHANGELOG](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md) | `[1차 확인]` |
| 협업 구조 | 고정 lead, teammates, 공유 task list(`~/.claude/tasks/{team}/`), mailbox. 작업 선점은 파일 락("Task claiming uses file locking"), self-claim 지원. 중첩 팀 불가. 같은 파일을 둘이 고치면 덮어쓴다 | agent-teams 문서 | `[1차 확인]` |
| 비용 | "significantly more tokens than a single session". 3–5 teammates 로 시작하길 권장 | agent-teams 문서 | `[1차 확인]` |
| `TeammateIdle` | 있음. "about to go idle after finishing its turn"에 발화. **exit 2**: stderr 를 피드백으로 받고 idle 대신 계속 일한다. **JSON** `{"continue": false, "stopReason": …}`: teammate 를 정지시킨다(Stop 훅과 같음). `decision:"block"` 은 이 이벤트의 결정 방식이 아니다. matcher 없음 | [hooks 문서](https://code.claude.com/docs/en/hooks) "TeammateIdle decision control" | `[1차 확인]` |
| `TaskCompleted` | 있음. 두 경우에 발화한다: **어떤 에이전트든** `TaskUpdate` 로 완료 표시할 때, 또는 teammate 가 in-progress 태스크를 둔 채 턴을 끝낼 때. **exit 2**: 완료 표시를 막고 stderr 를 모델에 돌려준다. `continue:false` 는 teammate 턴 종료로 발화했을 때만 유효하다("When the `TaskUpdate` tool triggered the event, Claude Code ignores `continue: false`; exit code 2 still blocks"). 문서 예시는 `npm test` 실패 시 exit 2 | hooks 문서 "TaskCompleted decision control" | `[1차 확인]` |
| `TaskCreated` | 있음. `TaskCreate` 시 발화하며 exit 2 또는 `decision:"block"` 으로 막는다. Task 도구가 없는 세션에서는 발화하지 않는다 | hooks 문서 | `[1차 확인]` |
| Task 도구 기본 제공 여부 | 킷 원장에 따르면 현재 기본 모델에서는 Task 도구가 기본 비활성이다. 그렇다면 `TaskCompleted`/`TaskCreated` 는 agent teams 밖에서 발화 경로가 좁다 | `docs/native-absorption.md` «계획 파일» 행(2026-10-05 정정) | `[소스 기준]` — 이번에 재측정하지 않음 |

참고 — [Anthropic «Building a C compiler»](https://www.anthropic.com/engineering/building-c-compiler)(2026-02-05)의 «agent teams» 는 위 네이티브 기능이 **아니다**. 저자가 `claude -p` 를 무한 반복하는 셸 루프를 컨테이너마다 돌렸다. 작업 선점은 `current_tasks/` 에 락 파일을 쓰는 방식이었고, git 동기화가 중복 선점을 걸렀다. 그 밖에 글에 적힌 것:

- 에이전트 16개, 오케스트레이터 없음: "I don't use an orchestration agent".
- 비용: 약 2,000 세션 · 2주 · "a total cost just under $20,000".
- 병렬화가 막힌 지점: "Every agent would hit the same bug, fix that bug, and then overwrite each other's changes". GCC 를 known-good 오라클로 쓰고서야 풀렸다.
- 오라클에 대해: "the task verifier is nearly perfect, otherwise Claude will solve the wrong problem."

모두 `[1차 확인]` 이다.

## 3. 킷 대조표

| Agensh 요소 | hiway-kit 대응물 | 겹침 / 차이 |
| --- | --- | --- |
| 조율 모델: 동등한 워커, 중앙 없음 | `plugins/common/skills/control-loop/SKILL.md` — 컨트롤이 조사·결정·디스패치·검증·병합. CLAUDE.md «Orchestration Model»: 수 개 청크는 스킬 주도 플랫 위임, 10~100+ 는 사용자 opt-in 네이티브 workflow | **정반대다.** 킷은 «결정은 위임 불가»를 축으로 삼는다. Agensh 는 결정(무엇을 할지)까지 워커에 분산한다 |
| Claim(자기 배정) + 겹치면 DM 으로 해소 | `plugins/common/rules/parallel-worktree.md` «파일 소유권 = 병렬 안전의 전제조건»: **위임 전에** disjoint 하게 나누고, 겹치면 순차 위임으로 강등. `plugins/common/skills/auto-dev/SKILL.md` «dispatch 전 파일 소유권 확인 [건너뛰기 금지]» | 킷은 충돌을 **사전 배정**으로 막고, Agensh 는 **사후 협상**(CLAIM 레코드 + DM)으로 줄인다 |
| Merge: 워커가 `main` 에 직접 병합, 충돌도 워커가 해결 | control-loop P3 «통합 브랜치는 컨트롤만 쓴다» · «병합 전 게이트를 컨트롤이 직접 실행» · «통합 후 통합 브랜치에서 한 번 더 전량». parallel-worktree «NEVER: 충돌 시 작업자가 임의로 ours/theirs 선택» | **킷 불변식과 정면으로 충돌한다.** Agensh 를 그대로 들이면 이 세 규범을 버려야 한다 |
| Verify: 하위 작업의 수용 기준에 대조(실험에서는 참조 바이너리와 차등 비교) | `plugins/common/tools/checklist.py` `complete` — 항목의 `verify` 명령을 실제로 실행해 exit 0 일 때만 `passes=true`. `stop-validator` Stop 훅(`decision:block`). `scripts/verify-done.sh` | 방향은 같다(완료 = 명령 결과). 차이: 킷의 `verify` 는 계획 단계에서 파생되고 self-authored trivial verify 는 막지 못한다고 스스로 적는다. Agensh 의 오라클은 **과제가 공짜로 준 것**(참조 바이너리)이다 |
| append-only 공유 컨텍스트(FAIL 등), 실시간, 턴 중 주입 | `plugins/common/tools/feedback_ledger.py` — `<git-common-dir>/kit/ledger.md`(**모든 워크트리 공유**, flock). 상한 50·중복제거·감쇠. **검증에서 실제로 발견된 결함만** upsert. 세션 시작 시 digest 로 주입 | 저장 위치(워크트리 간 공유)는 겹친다. 성격은 다르다: 원장은 **세션 간·누적·압축**(append-only 가 아니다), Agensh 보드는 **실행 중·실시간·무압축**이다. 킷에는 실행 중 워커 간 채널이 **없다** — 의도된 것이다(공유 상태 파일은 오케스트레이터만 쓴다, parallel-worktree «공유 상태 파일») |
| FAIL(반증된 가설) | 위임 보고 계약(`plugins/common/rules/delegation-contract.md`): 부분 보고 요구, 사실 등급(`[confirmed]`/`[소스 기준]`/`[미확인]`). 원장은 «통과 패턴·추측은 노이즈»라며 결함만 받는다 | **빈칸이다.** 킷은 «무엇이 사실인가»는 등급으로 보내지만 «무엇을 시도해 반증했는가»를 보낼 자리가 없다(추론: 다음 브리프의 ① 전제에 실어 같은 시도를 막을 경로가 없다) |
| 유휴 감지(10분) + 마감 리마인더(T−45/T−5) | `docs/control-loop-transport.md` §8 «조용한 idle 이 있다… 침묵은 성공도 실패도 아니다». Orca 운송의 heartbeat(호스트 소유). `plugins/common/rules/loop-engineering.md` «무진전» 가드(같은 항목 2회 연속 진전 없음 → 중단) | 킷은 유휴를 **호스트·운송의 상태**로 보고 직접 감지하지 않는다. 마감은 시간이 아니라 **진전 기준**이다 |
| 루프를 프롬프트로, 전달은 런타임 | 킷 전체가 «행동은 스킬(프롬프트), 판정은 결정론적 코드»(checklist·verify-done·Stop 훅). Delegation Signal 폐기 판정: 자연어로만 소비되는 비결정적 보조 경로는 없는 것보다 나쁘다 | 층 분리는 같다. Agensh 의 런타임(라우터·디스패처)은 킷이 **가질 수 없는 층**이다 — 킷에는 상주 프로세스가 없다(`docs/conventions/warning-signal.md` §검토 4의 «발화 조건이 없다» 사례) |
| 1,024 에이전트 규모 | `docs/native-absorption.md` «대규모 병렬 오케스트레이션» 행: 킷의 옛 agent-teams 스킬은 `superseded`, 네이티브 `ultracode` 로 라우팅. «멀티세션 위임 운송» 행: agent teams 는 `watch`(실험·기본 꺼짐) | 대규모는 이미 «킷이 하지 않는다»로 판정돼 있다 |

## 4. 흡수 후보 판정표

판정 기준: CLAUDE.md consumer-first(소비자 환경에서 동작하는가 · 특정 플러그인/MCP/플래그를 가정하지 않는가 · 다른 플러그인과 충돌하지 않는가)와 «비결정적 보조 경로는 없는 것보다 나쁘다». **판정은 이 조사의 제안이며, 채택 결정은 컨트롤 몫이다.**

| 후보 | 판정 | 근거 |
| --- | --- | --- |
| **A. 타입 있는 append-only 공유 보드를 병렬 워커/워크트리 운영에 넣기** | **reject** (런타임 보드) | Agensh 보드가 쓸모 있는 이유는 **런타임이 턴 중에 밀어 넣기 때문**이다(App. B.2). 킷에는 그 런타임이 없다. 파일로 두면 «워커가 기억나면 읽는» 경로가 되는데, 이것이 정확히 Delegation Signal 이 폐기된 형태다(소비 지점이 자연어 지시뿐인 비결정적 보조 경로). 또 parallel-worktree «공유 상태 파일» NEVER 와 충돌한다(워커가 쓰는 공유 상태). 실행 중 공유 채널이 필요한 규모는 호스트(agent teams mailbox·Orca 메시지)가 소유한다 |
| **A′. FAIL 레코드(반증된 가설)를 위임 보고 계약의 필드로** | **adopt(pilot)** | 보드가 아니라 **이미 결정론적으로 소비되는 경로**(컨트롤이 반드시 읽는 완료 보고)에 실으므로 새 보조 경로가 생기지 않는다. 컨트롤은 그것을 다음 브리프의 ① 전제에 인용할 수 있다(control-loop «브리프의 전제 서술은 P1의 실측을 그대로 인용»). 하네스 중립이고 플래그를 가정하지 않는다. 파일럿 형태(제안): `rules/delegation-contract.md` 보고에 «반증한 가설(없으면 없음)» 필수란을 추가한다. 이는 «병합 측 후속 조치» 필수란과 같은 패턴이다. 효과는 **미검증(추론)** — 파일럿 성공 기준을 따로 정해야 한다 |
| **B. 워커 간 CLAIM(작업 범위 선점) vs 현재의 컨트롤 분배** | **reject** (킷 규범으로서) / 네이티브는 `watch` | 킷이 다루는 규모(수 개 청크)에서는 **사전 disjoint 배정이 더 강한 보장**이다. 충돌 자체가 생기지 않는다. CLAIM 은 «배정하는 자가 없을 때»의 차선책이고, 협상(DM)이 실패하면 사후 충돌 해결로 넘어가는데 킷은 그것을 임의로 하지 않는다. C 컴파일러 글의 «같은 버그를 모두가 고치고 서로 덮어씀»은 CLAIM 류 선점만으로는 부족했다는 1차 사례다. 네이티브 agent teams 가 이미 파일 락 기반 task claiming 을 제공하므로, 킷이 재구현하면 zero-debt 원칙(네이티브 중복 금지)에도 어긋난다 |
| **C. 유휴 감지·마감(deadline) 훅** | **reject** (킷 배포 훅) / `watch` | `TeammateIdle` 은 experimental 플래그가 켜진 agent teams 안에서만 발화한다. 킷이 배포하면 대부분 소비자에게 **한 번도 발화하지 않는 훅**이 된다(warning-signal §검토 4의 거울상). 시간 기반 마감은 상태(시작 시각) 저장이 필요한데 «유휴=결함»은 상시 참에 가까워 경고가 죽는다(§검토 1). 킷의 «무진전» 가드가 진전 기준으로 같은 목적을 이미 다룬다. 유휴 관측은 호스트·운송(heartbeat)의 몫이다. agent teams 가 GA 가 되면 opt-in 예시(`hooks/examples/`)로 재평가한다 |
| **D. «완료는 오라클 통과로만»(TaskCompleted 차단)** | **reject** (배포 훅) — **기능은 이미 보유** | 킷의 `checklist.py complete` 가 같은 의미(verify exit 0 일 때만 완료)를 **하네스 중립·세션 간 영속**으로 이미 집행하고, `stop-validator`(Stop `decision:block`)와 `verify-done.sh` 가 겹겹이 있다. `TaskCompleted` 는 Claude Code 전용이고, Task 도구가 있어야 발화한다(현재 기본 모델에서 기본 비활성 — `[소스 기준]`). 또 **모든** `TaskUpdate` 완료에 발화하므로, 킷이 테스트 실행 훅을 배포하면 소비자의 모든 태스크 완료마다 테스트가 돈다. 이는 소비자 자신의 훅과 충돌하고 비용도 든다. 중복이다. 옵션: Task 도구가 기본 제공되면 `checklist.py verify` 를 부르는 opt-in 예시를 `watch` |
| **E. 오케스트레이터 없는 모드를 킷이 제공** | **reject** (현재) / `watch` (재평가 조건 아래) | **잃는 것**: control-loop 의 «병합 전 컨트롤 게이트», «통합 후 전량 재실행»(실측 n=2 로 근거가 있는 규범), parallel-worktree 의 «임의 ours/theirs 금지». Agensh 는 이 셋을 모두 워커에게 넘긴다. **어느 스케일부터인가**: 논문에서 평균 이득이 의미 있게 나타나는 구간은 32 에이전트 이상이다(1→8 은 +1.37pt 로, 과제 하나의 변동 −7.35pt 보다 작다). 이는 CLAUDE.md 가 이미 «사용자 opt-in 네이티브 workflow» 로 보낸 영역이다. 킷이 따로 모드를 만들면 네이티브(agent teams·workflow)와 중복된다. **재평가 조건**: 코드 공개, 독립 재현, 비용 보고, 오케스트레이터 비교군이 있는 후속 연구 |
| (부가) 루프를 프롬프트로 정의 | 이미 그렇게 하고 있음 — 변경 없음 | 킷의 스킬이 프롬프트 루프이고, 판정은 코드다. Agensh 도 같은 분리다(루프는 프롬프트, 전달·유휴는 런타임) |

## 5. 반론 — 이 결과를 킷에 일반화하면 안 되는 이유

1. **오라클이 과제에 내장돼 있다.** ProgramBench 는 모든 워커가 참조 바이너리를 실행해 자기 빌드와 차등 비교할 수 있는 과제다(App. A). 수용 기준을 각 워커가 **공짜로, 자율적으로** 확인할 수 있으니 중앙 검증이 덜 필요하다. 소비자의 일반 작업(기능 추가·버그 수정)에는 이런 오라클이 없다. 킷의 `checklist` 조차 «trivial verify 는 못 막는다»고 적는다. C 컴파일러 글도 같은 경고를 남겼다: "the task verifier is nearly perfect, otherwise Claude will solve the wrong problem". `[1차 확인]`
2. **비용이 없다.** 논문은 토큰·달러를 보고하지 않는다. 128 에이전트 × 6시간의 비용을 모르니 «49% 상대 향상»의 효율을 판정할 수 없다. 규모를 가늠할 1차 수치는 C 컴파일러 글이다: 에이전트 16개 · 2주 · 약 $20,000. 킷 소비자는 개인·소규모 팀이다. `[1차 확인]`(부재와 C 컴파일러 수치)
3. **재현성이 낮다.** 모델 1개(GPT-5.6-sol), 하네스 1개(Copilot), 과제 5개, 반복·분산 없음, 코드 미공개(404)다. 표본 5개의 평균에서 과제 하나의 변동(ctags 1→8: −7.35pt)이 평균 이득(1→8: +1.37pt)보다 크다. 저자는 이 비단조성을 언급하지 않는다. Claude Code 로 돌린 실험이 없으므로 «Claude Code 에서도 된다»는 것은 블로그의 추론이다. `[1차 확인]`
4. **비교군이 없다.** 논문은 오케스트레이터가 병목이라고 문제를 제기하지만, 결과는 Agensh 의 에이전트 수 스케일링뿐이다. 같은 규모의 오케스트레이터형 시스템과 비교하지 않았다. 따라서 «오케스트레이터를 없앤 덕»과 «에이전트를 늘린 덕»이 분리되지 않는다. `[1차 확인]`(부재)
5. **과제 형태가 병렬에 유리하다.** 큰 프로그램을 처음부터 재구현하는 과제는 서로 독립적인 기능이 수천 개라 자연스럽게 나눠진다. 부분 통과율로 채점하므로 폭넓게 일부라도 맞추면 점수가 오른다. 킷의 전형적 작업은 기존 코드베이스의 Small/Medium 변경이고, 공유 파일(설정·등록부·CHANGELOG)이 있어 사전 배정과 단독 수정이 필요하다. **추론**
6. **병합 책임이 사라진다.** 워커가 `main` 에 직접 병합하고 충돌을 해결하는 구조에서는 «통합 후에야 보이는 결함»(control-loop 의 실측 n=2)을 잡는 자리가 없다. 논문의 최종 판정은 실행이 끝난 뒤 숨은 테스트로 한 번 하는 외부 채점이다. 운영 환경에는 그런 사후 채점자가 없다. **추론**(1차 사실 위에서)

## 6. 출처 목록

1차:

- Agensh — https://arxiv.org/abs/2609.26781 · HTML https://arxiv.org/html/2609.26781v1 · TeX 소스 https://arxiv.org/src/2609.26781 (2026-10-07 접속; 그림 PDF 렌더링으로 Fig. 5 수치 판독)
- 프로젝트 페이지 — https://aka.ms/Agensh → https://agens-harness.github.io/project/
- 코드 — https://github.com/microsoft/Agensh (404, 2026-10-07)
- DeLM — https://arxiv.org/abs/2606.10662
- ProgramBench — https://arxiv.org/abs/2605.03546
- Claude Code agent teams — https://code.claude.com/docs/en/agent-teams
- Claude Code hooks — https://code.claude.com/docs/en/hooks («TaskCompleted decision control», «TeammateIdle decision control»)
- Claude Code CHANGELOG — https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md (2.1.292 까지)
- Anthropic, Building a C compiler — https://www.anthropic.com/engineering/building-c-compiler
- 로컬: `claude --version`(2.1.292), `claude --help`

2차(검증 대상, 비신뢰 데이터로 취급):

- theaxlabs.com, «Agensh 논문 리뷰…» (2026-09-29) — https://theaxlabs.com/blog/agensh-multi-agent-harness-paper-review

킷 내부(기준 `d60faa0`):

- `plugins/common/skills/control-loop/SKILL.md`, `plugins/common/skills/child-session/SKILL.md`, `plugins/common/skills/auto-dev/SKILL.md`
- `plugins/common/rules/parallel-worktree.md`, `plugins/common/rules/delegation-contract.md`, `plugins/common/rules/loop-engineering.md`
- `plugins/common/tools/feedback_ledger.py`, `plugins/common/tools/checklist.py`
- `docs/native-absorption.md`, `docs/control-loop-transport.md`, `docs/conventions/warning-signal.md`, `CLAUDE.md`
