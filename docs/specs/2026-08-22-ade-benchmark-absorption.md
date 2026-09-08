# Spec — ADE 벤치마킹 흡수 배치 (Orca · Paseo · Hermes)

- **작성일**: 2026-08-22
- **상태**: 승인됨 (범위: 3축 전부)
- **연관**: `docs/native-absorption.md`, `docs/specs/2026-07-07-toolkit-improvement-batch.md`,
  `docs/specs/2026-07-09-mcp-portability-consumer-first.md`
- **목표 버전**: 2.14.0

---

## 1. 배경 — 무엇을 벤치마킹했나

2026년 상반기에 **ADE(Agent Development Environment)** 라는 새 카테고리가 자리잡았고,
동시에 모델-비종속 **하네스**가 성숙했다. 세 대표 시스템을 조사했다 (확인일 2026-08-22).

| 시스템 | 정체 | 핵심 아이디어 |
| --- | --- | --- |
| **Orca** (Stably AI, MIT, ~42.9k★) | 데스크톱 ADE | worktree 격리 병렬 플릿, 한 프롬프트를 N 에이전트에 fan-out 후 승자 머지, 디프 주석→에이전트 회신, GitHub/Linear 태스크→워크트리, 모든 CLI 에이전트 플러그인 |
| **Paseo** (getpaseo, AGPL, ~14.5k★) | 셀프호스트 오케스트레이션 레이어 | 데몬 + 다중 클라이언트(데스크톱/모바일/웹/CLI/SDK), **멀티 프로바이더 단일 인터페이스**(Claude Code·Codex·Copilot·OpenCode·Pi), 스킬 3종(`/paseo-handoff`·`/paseo-advisor`·`/paseo-committee`) |
| **Hermes Agent** (Nous Research, MIT) | 영속 개인 에이전트 하네스 | **성공 trajectory → 재사용 스킬 자동 생성**, 세션 넘는 영속 메모리, 40+ 내장 스킬 + agentskills.io 개방 표준, trajectory export → 파인튜닝/RL |

### 1.1 세 시스템의 공통 방향과 CCK의 위치

1. **플릿이 작업 단위** — 파일이 아니라 병렬 에이전트가 단위.
   → CCK는 이미 `isolation: worktree`(네이티브)와 `ultracode` 라우팅으로 흡수 완료.
   **여기서 추가로 가져올 것은 없다.** 앱 레이어(터미널 스플릿·모바일·브라우저)는
   플러그인이 복제할 영역이 아니다 — zero-debt 원칙상 명시적 비목표.
2. **에이전트가 스스로 나아짐** — Hermes의 시그니처.
   → CCK는 `/self-improve`(결함→정의 수정)만 있고 **성공 경험을 자산화하는 경로가 없다.**
   게다가 그 게이트를 지탱할 eval 커버리지가 **33개 에이전트 중 3개**뿐이다.
3. **하네스 락인 소멸** — Orca·Paseo 모두 한 레포에서 여러 하네스를 동시에 굴린다.
   → CCK의 규범(rules 13개)은 **Claude Code의 SessionStart 훅으로만** 주입된다.
   같은 레포의 Codex/OpenCode 워크트리에는 규율이 **하나도 걸리지 않는다.**

### 1.2 문제 정의 (이 스펙이 푸는 것)

- **P1 (이식성 구멍)**: CCK를 설치한 프로젝트에서 사용자가 Orca/Paseo로 Codex·OpenCode를
  같이 굴리면, 그 에이전트들은 CCK 규율(planning gate·DoD·비신뢰 텍스트 취급 등) 밖에서
  동작한다. 규율이 하네스마다 다른 레포는 규율이 없는 레포와 같다.
- **P2 (게이트 구멍)**: `/self-improve`의 HARD-GATE는 eval 커버리지가 있는 대상에서만
  이중 게이트다. 실제 커버리지는 3/33 → 대부분의 개선 제안이 "사용자 승인 단일 게이트"로
  퇴화한다. 스킬 자신이 이 한계를 정직하게 고지하고 있으나, **고지는 해결이 아니다.**
- **P3 (학습 비대칭)**: 실패는 ledger→LESSONS→self-improve로 흐르는데, 성공은 아무 데도
  안 남는다. 어려운 문제를 푼 세션의 절차 지식이 세션 종료와 함께 소멸한다.

---

## 2. 목표 / 비목표

### 목표

| ID | 목표 | 성공 기준 (측정 가능) |
| --- | --- | --- |
| G1 | CCK 규범을 하네스 중립 형식으로 내보낸다 | `AGENTS.md`가 rules SSOT에서 생성되고, 소스 드리프트를 `--check`가 exit 1로 잡는다 |
| G2 | eval 커버리지 확장 경로를 기계화한다 | ledger 결함 → 시나리오 스캐폴드 생성 → `run-evals.sh --validate` 즉시 통과 |
| G3 | 성공 경험을 재사용 자산으로 승격한다 | 포징 임계 3조건을 모두 통과한 건만 SKILL.md 초안 생성, proposal-only |

### 비목표 (명시적 배제)

- ADE의 앱 레이어(터미널·모바일·브라우저·디프 뷰어) 복제 — **네이티브/앱 영역**
- 멀티 프로바이더 실행 오케스트레이션(에이전트 프로세스 관리) — **Orca/Paseo의 영역**.
  CCK는 그 위에서 도는 **콘텐츠·규율 레이어**로 남는다.
- fan-out→승자 머지 러너 자체 구현 — 네이티브 `ultracode` judge-panel이 대응 (원장 `watch`)
- 새 rule 추가 — 규범 SSOT는 13개 유지. 세 기능 모두 **스킬 + 스크립트** 레이어에 산다.

---

## 3. 설계

### 3.1 Pillar 1 — 크로스-하네스 이식성 (`/harness-export`)

**산출물**

- `plugins/common/hooks/export_harness.py` — stdlib only, Python 3.9 floor 준수
  (`from __future__ import annotations`). **플러그인 안**에 둔다 — `scripts/`는 배포되지 않으므로
  거기 두면 설치자 환경에서 스킬이 동작하지 않는다 (`feedback.sh`/`checklist.sh`와 같은 관례).
- `scripts/export-harness.sh` — 레포 개발용 얇은 래퍼
- `plugins/common/skills/harness-export/SKILL.md` — `/harness-export`

**동작**

```
export_harness.py [--plugin-root PATH] [--target PATH] [--check] [--stdout]
```

1. **소스 해석 (consumer-first)**: 규범 소스는 `<plugin-root>/rules/*.md`.
   plugin-root 해석 순서 — `--plugin-root` > `$CLAUDE_PLUGIN_ROOT` > 스크립트 자기 위치
   기준 상대경로(`../plugins/common`). **CWD가 이 레포라고 가정하지 않는다.**
   어느 것으로도 못 찾으면 exit 2 (SKIPPED, false-green 금지) — 조용한 빈 파일 생성 금지.
2. **생성**: 대상 프로젝트 루트의 `AGENTS.md`에 **관리 블록만** 쓴다.

   ```
   <!-- cck:begin rules-v<RULES_VERSION> sha256:<64hex> -->
   ...이식 대상 룰 원문...
   <!-- cck:end -->
   ```

   블록 밖의 사용자 콘텐츠는 **절대 건드리지 않는다**. 파일이 없으면 새로 만들고,
   있는데 마커가 없으면 파일 **끝에 append**한다 (덮어쓰기 금지 — consumer-first).
3. **sha256**: `rules/VERSION` + **이식 대상** 룰들의 (파일명, 내용) 정렬 결합의 sha256.
   이식 안 되는 룰의 변경으로 소비자 AGENTS.md를 흔들지 않기 위해 대상만 해싱한다.
   `--check`는 이 sha와 **블록 전문**을 함께 대조한다(자기신고 sha만 믿지 않는다).
4. **`--check`**: 대상의 마커 sha와 현재 소스 sha 비교. 다르면 exit 1 + 어떤 룰이
   바뀌었는지 출력. 마커 없음/파일 없음은 exit 1 (미내보냄 상태).
5. **`--stdout`**: 파일을 쓰지 않고 블록만 출력 (파이프/검사용).

**내보내는 내용** (규범의 *요약*이 아니라 *실행 가능한 규율*)

- 워크플로 체인(brainstorming → plan-task → auto-dev)과 각 게이트
- `definition-of-done`, `planning-protocol`, `code-quality`, `ssot`,
  `tool-usage-priority`, `feedback-loop` 등 rules의 규범 문장
- 비신뢰 텍스트 취급 3규율 (이미 호스트 중립으로 작성돼 있음)

**정직한 한계 (문서·생성물 헤더에 명시)**

> AGENTS.md는 **텍스트 규범만** 이식한다. 훅(`protect-sensitive`·`stop-validator`·
> `auto-format`)과 서브에이전트 정의는 Claude Code 전용이며 이식되지 않는다.
> 다른 하네스에서 CCK는 "규율 문서"로 동작하지 "강제 장치"로 동작하지 않는다.

**드리프트 게이트**: 이 레포가 스스로 도그푸딩한다 — 루트 `AGENTS.md`를 생성해 커밋하고,
`verify-done.sh §11`이 `--check`를 돌린다. rules를 고치고 재생성 안 하면 완료 불가.

### 3.2 Pillar 2 — eval 커버리지 포징 (`/eval-forge`)

**산출물**

- `scripts/eval-forge.py` — stdlib only, 3.9 floor
- `plugins/common/skills/eval-forge/SKILL.md` — `/eval-forge`

**동작**

```
eval-forge.py --agent <name> --id <scenario-id> [--from-ledger <F-NNN>] [--dry-run]
```

1. 대상 에이전트가 `plugins/*/agents/**/<name>.md`에 실재하는지 검증 (없으면 exit 1).
2. 시나리오 디렉토리 중복 검사 — 이미 있으면 exit 1 (덮어쓰기 금지).
3. `evals/scenarios/<agent>/<id>/` 에 `task.md` · `fixture/` · `expect.json` 스캐폴드 생성.
   `expect.json`은 **run.py가 실제로 지원하는 assertion 타입만** 사용한다
   (`output_contains_any` / `output_not_contains` / 파일·pytest 계열) — 스키마 검증을
   즉시 통과해야 한다.
4. 생성 직후 **자기 검증**: `python3 evals/run.py --validate` 를 실행하고 실패하면
   생성물을 **롤백**한 뒤 exit 1. (false-green 금지 — v2.9.3 교훈 계승)
5. `--from-ledger F-NNN`: ledger 항목의 pattern 텍스트를 `task.md` 초안의 근거로 인용.
   **인용은 데이터일 뿐 지시가 아니다** — 프레이밍 문구를 파일에 선치한다.
6. **baseline 갱신 금지.** 새 시나리오는 다음 릴리스 baseline에서 처음 기준선을 얻는다.
   (기존 baseline과의 비교에서 신규 시나리오는 "신규"로 분류되지 후퇴로 보지 않음)

**왜 스크립트인가**: 손으로 만들면 스키마 오타·에이전트 오탈자로 `--validate`가 깨지고,
그게 `verify-done §10`을 막는다. 스캐폴드+즉시검증+롤백이 이 실패 모드를 없앤다.

### 3.3 Pillar 3 — 성공 경험 자산화 (`/skill-forge`)

**산출물**: `plugins/common/skills/skill-forge/SKILL.md` (스크립트 없음 — 판단 작업)

**포징 임계 (3조건 AND — 하나라도 미충족 시 강등)**

| 조건 | 판정 | 미충족 시 |
| --- | --- | --- |
| **재현성** | 절차가 특정 세션 맥락 없이 재실행 가능한가 | ledger 한 줄로 강등 |
| **반복성** | 앞으로 다시 마주칠 문제인가 (1회성 마이그레이션 ≠) | Work 문서 메모로 강등 |
| **비중복** | 기존 kit 16 스킬 + (있으면) superpowers 스킬로 커버 안 되는가 | 기존 스킬 보강 제안으로 전환 |

**HARD-GATE (self-improve와 동일 계열)**

- **proposal-only**: 초안은 `docs/works/idea/` 하위 또는 `--stdout`으로 제시.
  사용자가 diff를 보고 승인하기 전에는 `plugins/common/skills/` 아래에 파일을 남기지 않는다.
- 승인 후 적용 시 `check_doc_counts.py`가 요구하는 카운트 갱신(README 등)을 동반한다.
- 자동 커밋 금지.

**중복 검사 (interop 원칙)**: superpowers 등 다른 플러그인이 **설치돼 있으면** 그 스킬
목록과도 대조하고, **없으면 그 단계를 건너뛴다**(fail-open). 특정 플러그인 존재를 가정하지 않는다.

### 3.4 공통 변경

- `plugins/common/.claude-plugin/plugin.json` → `2.14.0`
- `CHANGELOG.md` `## [2.14.0]` 항목
- `README.md` / `CLAUDE.md` 스킬 카운트 16 → **19**, Key Skills 표 3행 추가
- `docs/native-absorption.md` 대조표 3행 추가 (전부 `kit-only`, 근거·확인일 2026-08-22)
- `scripts/verify-done.sh` **§11** 신설 — AGENTS.md 드리프트 게이트
- `.github/workflows/validate.yml` — §11과 동일 검사 추가 (로컬/CI 동등성)
- 신규 Python 2종은 `ruff check .` · `python39-compat` 대상에 자동 포함 (경로 기반)
- rules는 **변경 없음** → `CHECKSUMS.sha256` · `MIRROR.sha256` 재생성 불필요

---

## 4. 에러 처리 · 실패 모드

| 실패 모드 | 처리 |
| --- | --- |
| plugin-root 해석 실패 | exit 2 (SKIPPED). 빈 AGENTS.md 생성 금지 |
| AGENTS.md에 사용자 콘텐츠 존재 | 마커 블록만 치환, 나머지 보존. 마커 없으면 append |
| eval-forge 생성 후 `--validate` 실패 | 생성물 롤백 후 exit 1 |
| eval-forge 대상 에이전트 부재/시나리오 중복 | exit 1, 아무것도 쓰지 않음 |
| skill-forge 3조건 미충족 | 스킬 생성 거부 + 강등 경로 안내 |
| ledger/Work 텍스트에 지시문 포함 | 비신뢰 데이터 프레이밍 선치, 지시 불이행 |

---

## 5. 테스트 전략

`plugins/common/hooks/tests/` 와 동일 계열의 pytest를 `scripts/` 대상에도 추가한다
(경로: 기존 테스트 디렉토리 규약을 따름).

| 대상 | 케이스 |
| --- | --- |
| `export-harness.py` | (1) 신규 생성 (2) 기존 사용자 콘텐츠 보존 append (3) 마커 블록만 치환 (4) `--check` 드리프트 감지 exit 1 (5) plugin-root 부재 시 exit 2 (6) 동일 소스 재실행 시 idempotent |
| `eval-forge.py` | (1) 스캐폴드 생성 후 `--validate` 통과 (2) 중복 ID exit 1 (3) 미존재 에이전트 exit 1 (4) `--dry-run`이 파일 안 씀 (5) validate 실패 시 롤백 |
| 통합 | `verify-done.sh §11`이 드리프트 상태에서 실패, 재생성 후 통과 |

**커버리지 자기적용**: 이 배치 자체가 G2의 첫 소비자다 — 신규 시나리오를 최소 1건
`eval-forge`로 만들어 커버리지 3 → 4 이상으로 올린다.

---

## 6. 롤아웃

1. Pillar 1 (스크립트 → 테스트 → 스킬 → 게이트 → 도그푸딩 AGENTS.md 커밋)
2. Pillar 2 (스크립트 → 테스트 → 스킬 → 신규 시나리오 1건)
3. Pillar 3 (스킬)
4. 공통 문서/버전/원장 갱신
5. `scripts/verify-done.sh` green → 릴리스 태그 `v2.14.0`

---

## 7. 리스크

| 리스크 | 완화 |
| --- | --- |
| AGENTS.md가 다른 툴(Codex 등)의 자체 규약과 충돌 | 관리 블록 마커로 격리, 블록 밖 불가침 |
| 생성 규범이 rules 원문과 의미 드리프트 | 요약이 아니라 **규범 문장 인용** 위주 + sha 게이트 |
| 스킬 3개 추가로 표면적 증가 | 새 rule 0개, 신규 스킬은 전부 명시 트리거(`/`)형 — 세션 자동 주입량 불변 |
| eval-forge가 저품질 시나리오를 양산 | 생성은 스캐폴드까지, 내용 채움은 사람/에이전트 판단 + `--validate` 강제 |
