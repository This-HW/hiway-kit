# 하네스 엔지니어링 & 루프 엔지니어링 — 2026 중반 지형도

> 2026-07-02 · claude-code-kit 리서치 노트
> 3개 병렬 리서치 에이전트(개념 계보 / 도구·오픈소스 생태계 / kit 자체 분석) 결과 종합.
> kit에 반영된 개선은 W-011 (v2.8.0) 참조.

## TL;DR

- **Harness engineering**이 프롬프트 → 컨텍스트에 이은 AI 엔지니어링 3단계 성숙도로
  정착했다. 공식은 `Agent = Model + Harness`.
- **루프 엔지니어링**의 사실상 표준 구현체는 3개로 수렴: Ralph Wiggum Loop,
  Anthropic Initializer-Executor 패턴, Claude Code Dynamic Workflows(`ultracode`).
  공통 뼈대는 "장시간 자율 실행 + 기계가 체크 가능한 완료 조건 + 파일시스템/git 기반
  영속 메모리".
- **검증 원칙 합의**: 완료는 주장이 아니라 검증이다. 작성자 에이전트는 오염되어
  있으므로(compromised) 검증은 세션을 분리하고, 검증자는 크지 않아도 되지만
  **달라야** 한다.
- **병렬 에이전트 도구**는 전부 "worktree(또는 컨테이너) 격리 + 태스크별 브랜치 +
  리뷰 후 병합"으로 수렴했다. 격리는 필요조건일 뿐 — 병목은 병합과 리뷰다.

---

## 1. Harness Engineering

### 계보

| 시점 | 사건 |
|------|------|
| 2025-12 | Andrej Karpathy, "context engineering" 용어 제안 |
| 2026-02 초 | Mitchell Hashimoto, 블로그에서 "harness engineering" 비공식 첫 언급 |
| 2026-02-11 | OpenAI "Harness engineering: leveraging Codex in an agent-first world" — 용어 공식화·확산 ("Humans steer. Agents execute.") |
| 2026-02 | Karpathy, "agentic engineering" |

Faros AI는 이를 성숙도 3단계로 정리한다: ① Prompt engineering → ② Context
engineering → ③ **Harness engineering**. 스코프 구분(Augment Code):

| 구분 | 통제 대상 | 시간 경계 |
|------|----------|----------|
| Prompt | 지시문 표현 | 1턴 |
| Context | 토큰 선택/순서/압축 | 1개 컨텍스트 윈도우 |
| Harness | 툴 오케스트레이션, 상태 영속화, 검증 루프, 에러 복구 | 태스크 전체 생애주기 |

핵심 원칙(Hashimoto): **"에이전트가 실수할 때마다, 다시는 그 실수를 하지 않도록
시스템을 엔지니어링하라."** 해법은 대부분 "개선된 하네스"의 형태로 나타난다.

### 표준 컴포넌트 (독립 하네스들이 수렴한 설계)

while-loop 엔진 / 컨텍스트 압축(compaction) / 툴·스킬 계층(progressive disclosure) /
서브에이전트 컨텍스트 격리 / 세션 영속성 / 동적 시스템 프롬프트 조립(CLAUDE.md 등) /
**라이프사이클 훅(결정론적 강제)** / 권한·안전 시스템.

Arize의 비교 분석에 따르면 Pi, Claude Code, Letta 등 서로 다른 하네스가 **독립적으로
동일한 설계에 수렴**했다(대형 툴 결과 디스크 영속화, 컴팩션 시 tool-call 경계 보존,
부모 트랜스크립트 포크 등) — 즉 이 패턴들은 유행이 아니라 검증된 수렴점이다.

Martin Fowler 계열(Birgitta Böckeler)의 프레임: **Feedforward**(행동 전 조향 —
규칙·컨텍스트 주입·툴 제한) vs **Feedback**(행동 후 관찰 — 린터·테스트·훅).
kit 매핑: `rules/` = feedforward, `hooks/` = feedback.

### 주목할 연구/사례

- **Anthropic, "Effective harnesses for long-running agents"** — SDK 압축만으로는
  장시간 품질 유지 불가를 실증. **Initializer-Executor 패턴** 제안: 초기화 에이전트가
  1회 durable project environment(init.sh, 기능 목록, progress 파일, 초기 커밋)를
  구축하고, 이후 각 executor 세션이 이를 세션 간 공유 메모리로 사용.
- **arXiv 2603.05344** (OpenDev) — scaffolding(첫 호출 전 정적 구성) vs
  harness(런타임 조율) 구분, 5-layer defense-in-depth.
- **arXiv 2604.25850** (Agentic Harness Engineering) — 하네스를 파일로 노출된
  컴포넌트로 분해하고 관측성 기반으로 하네스 자체를 자동 진화시키는 폐루프.
- **AGENTS.md 스펙**(2025-08, OpenAI·Google·Cursor 등) — 크로스툴 제약 하네스 표준.
- **최소주의 반례**: Pi(4개 코어 툴, 시스템 프롬프트 <1000 토큰), Vercel의 "툴 80%
  삭제로 성능 개선" — 툴 스코핑 최소화 원칙의 근거.

---

## 2. Loop Engineering — 3대 표준 구현체

### Ralph Wiggum Loop (Geoffrey Huntley, 2025)

```bash
while :; do cat PROMPT.md | agent; done
```

- 매 이터레이션 **fresh context**. 메모리는 git 히스토리 + progress 파일 + PRD.
  "완벽한 컨텍스트 유지 대신 매번 새 출발 + git을 메모리 레이어로."
- 필수 조건 2가지: ① 상세 스펙, ② **명확한 종료 기준(exit criteria)**.
- 매 이터레이션 후 발견한 패턴/함정을 AGENTS.md에 기록 → 다음 이터레이션이 활용.
- 2026 초 Anthropic 공식 플러그인화(`--max-iterations`, `--completion-promise`).
- 한계(tessl.io): 초기 스펙이 압축·손실되면 에이전트가 자기 요약에 의존해 드리프트.

### Initializer-Executor (Anthropic)

프로젝트 환경 자체를 세션 간 계약으로 만든다. 위 1절 참조.

### Dynamic Workflows / `ultracode` (Anthropic, 2026-05-28)

계획이 JavaScript 오케스트레이션 코드로 이동 — Claude가 스크립트를 작성하고 별도
런타임이 백그라운드 실행(동시 16, 총 1000 에이전트 한도, 중단 후 재개 가능).
Agent Teams(세션 소실 시 비영속)와 달리 재개 가능이 특징.

### 검증 원칙 (합의된 것들)

- **DoD는 기계가 체크 가능한 계약**(Verdent): "모듈을 개선하라"는 계약이 아니다.
  "auth/ 테스트 전부 통과, 린트 0 에러"는 계약이다 — 각 절이 관측 가능하므로.
- **Stop hook 품질 게이트**: 검증 통과 전 에이전트 종료를 차단하고 실패 컨텍스트를
  주입해 자동 수정 턴을 유도. 빠른 결정론적 체크를 앞에, LLM 판단을 뒤에 배치
  (3-layer: PostToolUse 문법 → Stop 커맨드 회귀 → Stop 프롬프트 의도).
- **Adversarial verification**: "코드를 작성한 에이전트는 오염되어 있다 — 자신이
  만든 것을 합리화한다"(ASDLC) → 세션 분리 필수. 검증자는 크지 않아도 되지만
  **다른** 모델/에이전트여야 self-evaluation bias가 줄어든다(ICLR 2026 사례).
- **Verify Loop 4원칙**(Neural Nexus): named(정확한 커맨드 지정) / fast enough to
  repeat / aligned with goal / **raw**(에이전트가 요약하지 않은 원본 stderr 제공).
- 신조어: "understanding theater", "completion theater" — 이해/완료하지 않았는데
  그렇게 보이는 문제. 검증 게이트가 정면 대응책.

---

## 3. 병렬 에이전트 오케스트레이션 생태계

공통 패턴: **git worktree(또는 컨테이너) 격리 + 태스크별 브랜치 + 병렬 실행 후
리뷰/병합**. 사실상 업계 표준.

| 도구 | 패턴 | 비고 |
|------|------|------|
| uzi (devflowinc) | `uzi start --agents claude:3,codex:2` 멀티모델 + tmux + worktree | Go, 성숙 |
| Vibe Kanban (BloopAI) | 칸반 카드 이동 → worktree 자동 생성 + 에이전트 배정 | 9.4k★, Apache-2.0 |
| claude-squad | 터미널 네이티브 tmux + worktree | 터미널 선호층 표준 픽 |
| Conductor | GUI, 멀티레포 worktree 자동관리 + PR 생성 | 상용 |
| **Container Use** (Dagger) | **컨테이너 + worktree 이중 격리**, MCP 서버, 체크포인트/롤백 | 3.6k★, worktree보다 강한 격리 |
| Parallel Code | symlink node_modules로 격리 유지 + 의존성 중복 방지 | 신생 |

**업계 합의**: 1인이 감당 가능한 동시 worktree는 4-8개. 그 이상은 리뷰가 병목 —
"worktree는 필요조건이지 충분조건이 아니다"(런타임 격리 + 충돌 예측 + 통합 리뷰
뷰가 추가로 필요).

Claude Code 네이티브 3계층(2026-06 기준, 구분 기준은 "누가 계획을 쥐는가"):
Subagents(메인이 계획) → Agent Teams(공유 워크스페이스, 3-5명 실질 한계, 비영속) →
Dynamic Workflows(계획이 코드로, 재개 가능).

### 인접 하네스에서 빌릴 만한 아이디어

| 출처 | 아이디어 |
|------|---------|
| Codex CLI | OS 레벨 샌드박스(Seatbelt/Landlock) 기본 활성화 |
| OpenCode | Plan/Build 에이전트 명시 분리 + 30+ LSP 통합 |
| Kiro (AWS) | EARS 표기법(`WHEN [조건] THE SYSTEM SHALL [동작]`) + SMT 기반 요구사항 모순 사전 탐지 |
| spec-kit (GitHub, 117k★) | `spec.md → plan.md → tasks.md` 에이전트-애그노스틱 마크다운 체인 |
| BMAD (반면교사) | 페르소나별 파일 핸드오프 → 오버헤드 과다로 흐름 단절. 플랫 위임의 정당성 방증 |
| claude-mem (반면교사) | 인기 메모리 플러그인이 무인증 로컬 HTTP API를 `0.0.0.0`에 바인딩 — 보안 감사 HIGH. 서드파티 플러그인 감사 항목에 "로컬 포트 바인딩" 추가 근거 |

---

## 4. kit 현황 대조 및 반영

### 이미 정합인 것

- CLAUDE.md 오케스트레이션 모델(Small/Medium 플랫 위임, Large는 사용자 수동
  `ultracode`)은 네이티브 3계층과 정합 — 2026-06 시점 최신.
- `stop-validator.py`는 업계 표준 "Stop hook 품질 게이트"와 동일 설계
  (편집 파일 스코핑, 비차단 타임아웃, decision:block 재진입).
- `rules/` = feedforward, `hooks/` = feedback — Fowler 프레임과 일치.
- 읽기 전용 병렬 리뷰(multi-perspective-review)는 설계적으로 충돌 배제.

### W-011에서 반영한 것 (v2.8.0)

- 레이스 컨디션 3건 수정: stop-validator 마커/카운터 크로스세션 오염,
  feedback ledger lost-update, work.sh Work ID TOCTOU.
- **병합 복귀 프로토콜 명문화**: `rules/parallel-worktree.md` 신설(검증 후 복귀,
  순차 병합, 파일 소유권, git-workflow 충돌 에스컬레이션) + 파일 수정 에이전트
  8개 정비.

### 로드맵 후보 (별도 Work)

- **Initializer-Executor 패턴**: plan-task 완료 시 durable environment 생성 단계 —
  Ralph Loop형 장기 자율 실행의 기반.
- **EARS 표기법**: clarify-requirements / define-business-logic의 요구사항 형식화.
- **Adversarial 세션 분리 명문화**: review-code의 fresh-context 실행 규칙화.
- 컨테이너 + worktree 이중 격리(Container Use 패턴)는 현재 스케일에서 과잉 — 관찰.

---

## 출처

- https://openai.com/index/harness-engineering
- https://www.augmentcode.com/guides/harness-engineering-ai-coding-agents
- https://www.faros.ai/blog/harness-engineering
- https://martinfowler.com/articles/harness-engineering.html
- https://addyosmani.com/blog/agent-harness-engineering
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://www.anthropic.com/research/long-running-Claude
- https://www.anthropic.com/news/claude-opus-4-8
- https://arxiv.org/html/2603.05344v1 · https://arxiv.org/html/2604.25850v2 · https://arxiv.org/html/2508.02994v1
- https://arize.com/blog/context-management-in-agent-harnesses
- https://ghuntley.com/loop
- https://www.aihero.dev/tips-for-ai-coding-with-ralph-wiggum
- https://tessl.io/blog/unpacking-the-unpossible-logic-of-ralph-wiggumstyle-ai-coding
- https://www.verdent.ai/guides/tutorial/build-coding-agent-loop
- https://www.sonarsource.com/blog/loop-engineering-without-verification-is-just-automation/
- https://asdlc.io/patterns/adversarial-code-review
- https://www.infoq.com/news/2026/06/dynamic-workflows-claude-code
- https://github.com/dagger/container-use · https://github.com/devflowinc/uzi · https://github.com/github/spec-kit
- https://github.com/obra/Superpowers · https://github.com/ai-boost/awesome-harness-engineering
- https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools
- https://www.stackone.com/blog/agent-suicide-by-context
