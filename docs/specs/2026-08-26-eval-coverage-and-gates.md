# Spec — 내부 결함 배치: eval 커버리지·기준선 게이트·학습루프 (W-018)

- **작성일**: 2026-08-26
- **작성**: 기획 세션(torpedo-c4). 구현은 별도 세션에 인계
- **상태**: 승인됨 (범위: 티어1 커버리지 확장 — 사용자 결정 2026-08-26)
- **연관**: `docs/specs/2026-08-22-ade-benchmark-absorption.md` (§1.2 P2가 이 스펙이 갚는 부채),
  `docs/native-absorption.md` (Agent Evals 행), `evals/README.md`
- **목표 버전**: 2.15.0

---

## 1. 현행 동작 고정 (특성화 — 의도가 아니라 관측)

기존 프로젝트이므로 **바꾸지 않는 것을 먼저 못박는다.** 아래는 2026-08-26 실측값이다.

| 항목 | 실측값 | 근거 |
| --- | --- | --- |
| 기준 커밋 | `017ee39` (v2.14.2) | worktree clean, origin/main 동일 |
| 완료 게이트 | `scripts/verify-done.sh` **19 pass / 0 fail** | 기획 세션 직접 실행 |
| eval 스위트 | **12/12 pass**, 3분28초, exit 0 | 구현 세션 실측 1회 완주 |
| 커버리지 | 에이전트 **4/33** (fix-bugs 4 · review-code 4 · implement-code 3 · security-scan 1) | `evals/scenarios/` 실측 |
| check 타입 | **7종 전부 결정론적** — `output_regex`, `contains_any`, `not_contains`, `pytest_green`, `file_contains`, `file_unchanged`, `delegation_signal` | `evals/run.py` 실측 |
| judge | 정의만 존재. 12건 전부 `judge.enabled:false`, `CKKIT_EVAL_JUDGE` 미설정 → **실사용 0건** | 실행 결과 `judge:null` |
| 비용 지배 요인 | `review-code`(opus) 4건이 wall-clock의 **60%** (93~150s/건, sonnet 계열의 3~5배) | 실측 |
| 기준선 | `evals/baseline/2026-07-06.json` — **11건 / 3에이전트** | 파일 실측 |

**이 12건이 특성화 테스트다.** 이번 배치에서 12건의 status가 하나라도 pass에서 벗어나면 회귀다.
`[confirmed: 실측, 2026-08-26]`

## 2. 문제 정의

- **P1-a 커버리지 구멍.** `/self-improve`의 HARD-GATE는 "eval 회귀 없음 + 사용자 승인" 이중 게이트인데,
  eval 커버리지가 없는 29개 에이전트에서는 **사용자 승인 단일 게이트로 퇴화**한다. ADE 스펙(§1.2 P2)이
  이 문제를 정의했고 `/eval-forge`라는 **도구**를 만들었으나, 커버리지는 3→4로 1 늘었을 뿐이다.
  도구를 만든 것과 부채를 갚은 것은 다르다.
- **P1-b 기준선 드리프트 — 기계 검사 부재.** 시나리오는 12건인데 기준선은 11건이다. 2.14.0에서 추가된
  `security-scan` 시나리오는 **비교 기준이 없는 채로 존재**한다. 회귀 판정이 부분적으로만 성립하는데
  게이트 19종 중 어느 것도 이것을 잡지 못했다. 이 배치가 놓친 것과 **정확히 같은 종류**의 드리프트다.
- **P2-a 학습 루프 입력 공백.** `docs/works/feedback/ledger.md` 가 존재하지 않는다. ledger→LESSONS→
  self-improve / eval-forge 경로가 설계상 존재하지만 **입력이 0건**이라 한 번도 돌지 않았다.
- **P3 낡은 판단 방치.** `docs/pipeline-reinforcement-plan-v2.md`(2026-05)의 Track 2가 "보류" 상태로
  15개월 방치됐다. 보류인지 폐기인지 문서가 답하지 않는다.

## 3. 성공 기준 (측정 가능)

| ID | 기준 | 측정 방법 |
| --- | --- | --- |
| S1 | 티어1 에이전트 **13종 전부**가 최소 1개 시나리오를 갖는다 | `evals/policy.json`의 `tiers.tier1` 각 항목에 대해 `evals/scenarios/<agent>/` 존재 |
| S2 | 시나리오 집합 ⊄ 기준선이면 **게이트가 exit 1** | `verify-done.sh` 신설 §에서 실증 (일부러 시나리오 추가 → red 확인) |
| S3 | 전체 스위트가 기준선 대비 **회귀 0건** | 신규 기준선 생성 시 기존 12건 status 전부 pass 유지 |
| S4 | `verify-done.sh` **전 항목 green** | 명령 출력 |
| S5 | ledger에 실제 결함 항목이 **1건 이상** 존재하고 그 경로가 문서화됨 | `docs/works/feedback/ledger.md` + README 갱신 |
| S6 | Track 2 보류 건이 **판정**된다 (진행/폐기 중 하나, 근거와 함께) | `docs/pipeline-reinforcement-plan-v2.md` 갱신 or 폐기 표시 |

## 4. 티어 정의 (이 배치의 범위선)

**선정 기준은 "위험도"다.** 파일을 수정하는 에이전트가 최우선 — 잘못 동작하면 사용자 코드가 깨진다.

### 티어1 = 13종 (이번 배치 대상)

| 분류 | 에이전트 | 현재 | 근거 |
| --- | --- | --- | --- |
| **파일 수정 (8)** | `implement-code`✅ `fix-bugs`✅ `write-tests` `write-api-tests` `implement-api` `generate-boilerplate` `sync-docs` `optimize-logic` | 2/8 | `isolation: worktree` 보유 = 파일을 쓴다 = 최고 위험 |
| **검증/리뷰 (3)** | `review-code`✅ `security-scan`✅ `verify-code` | 2/3 | 게이트 역할. 오탐/미탐이 곧 품질 사고 |
| **탐색/계획 (2)** | `explore-codebase` `plan-implementation` | 0/2 | 모든 체인의 진입점. 출력 계약(DELEGATION_SIGNAL) 검증 대상 |

→ **신규 시나리오 9건 이상** (에이전트 9종 × 최소 1건)

### 티어2 = 나머지 20종 (명시적 후속)

티어 정의만 `evals/policy.json`에 남기고 이번 배치에서는 만들지 않는다.
`clarify-requirements` 계열 대화형 에이전트는 `AskUserQuestion` 의존이라 시나리오화 난도가 다르므로
**후속 배치에서 별도 설계**한다. 이번에 억지로 넣지 않는다. `[confirmed: 사용자 결정, 2026-08-26]`

## 5. 아키텍처 (결정. 선택지를 남기지 않는다)

### 5.1 정책은 데이터로 분리한다 — `evals/policy.json` 신설

**왜**: 티어 목록·임계값이 스크립트와 문서에 산문으로 흩어지면 반드시 드리프트한다
(`pytest.ini`가 F-023에서 이미 겪은 실패). 대상 목록의 **단일 소스**를 만든다.

- 파일: `evals/policy.json` (추적됨)
- 소비자: `scripts/verify-done.sh` 신설 §, `evals/run.py`, CI
- **산문에 숫자·목록이 남아 있으면 미완성이다.** 티어 목록은 이 파일에만 존재한다

### 5.2 기준선 포인터는 명시적이다 — "최신 파일 자동 선택" 금지

**왜**: 파일명으로 최신을 추정하면 조용히 틀린 기준선을 쓴다. 이 레포는 이미
`MIRROR.sha256` / `CHECKSUMS.sha256` 에서 **"재생성은 의도적 행위"** 규약을 쓰고 있다. 같은 규약을 따른다.

- `evals/policy.json` 의 `baseline.file` 이 유일한 포인터
- 기준선 재생성은 명령으로만: `scripts/run-evals.sh --write-baseline`
- 과거 기준선 파일은 **아카이브로 존속**한다 (삭제하지 않는다 — 추이가 회귀 탐지 근거다)

### 5.3 새 게이트는 결정적이고 에이전트를 호출하지 않는다

**왜**: eval 실행은 실제 에이전트 호출이라 분당 비용이 붙는다. CI가 매 커밋 스위트를 돌리면 파산한다.
그러나 **드리프트 검사 자체는 파일 목록 비교**라 공짜다. 둘을 분리한다.

| 레이어 | 검사 | 비용 | 실행 시점 |
| --- | --- | --- | --- |
| CI + `verify-done.sh` | 스키마 `--validate` + **기준선 커버리지 대조** | 0 (에이전트 호출 없음) | 매 커밋 |
| 수동 / 릴리스 | 전체 스위트 실행 → 기준선 재생성 | 에이전트 호출 N건 | 릴리스 전, self-improve 전 |

- 게이트 판정: `{시나리오 디렉토리 집합}` ⊆ `{기준선 results의 (agent,scenario) 집합}` 이 아니면 **exit 1**
- 반대 방향(기준선에만 있고 시나리오가 사라짐)도 **exit 1** — 시나리오 삭제를 침묵으로 통과시키지 않는다
  (기존 §9 test-ratchet과 같은 철학)

### 5.4 judge는 이번 배치에서 켜지 않는다

**왜**: judge는 유일한 비결정 경로다. 결정적 게이트에 비결정 점수를 섞으면 게이트가 노이즈가 되어
아무도 보지 않게 된다(spec-handoff §에이전트 시스템 2). 신규 9건은 **전부 결정적 check만** 쓴다.
judge 활성화는 별도 배치에서 "고정 평가셋 + 임계값" 설계와 함께 다룬다.

- `evals/policy.json`: `gate.judgeEnabledByDefault: false`
- **권한 위반·금지 행위는 임계값이 아니라 0**이며 결정적 게이트로 취급한다 (해당 시 `not_contains` / `file_unchanged`)

### 5.5 비용 통제

`review-code`(opus)가 wall-clock의 60%를 먹는 실측이 있다. 신규 9건은 대부분 sonnet 계열이므로
스위트 총 시간은 **9~11분** 수준으로 예상한다 `[researched: 실측 3분28초 + 신규 9건 × 30~45s 추정, n=1]`.
10분을 넘으면 그 사실을 기준선 파일에 기록만 하고 **분할 실행은 이번 범위가 아니다.**

## 6. 수용 테스트 (사람이 손으로 확인)

1. `evals/scenarios/` 에 새 디렉토리를 하나 만들고 `./scripts/verify-done.sh` → **fail** 하는가
2. 그 디렉토리를 지우면 다시 **green** 인가
3. `evals/policy.json` 의 `baseline.file` 을 존재하지 않는 파일명으로 바꾸면 **fail** 하는가 (조용히 skip하지 않는가)
4. 신규 시나리오 중 하나를 골라 `task.md`를 읽었을 때, **에이전트가 무엇을 해야 하는지 사람이 이해**되는가
5. 신규 시나리오의 `expect.json` assertion이 "실행하면 당연히 통과하는" 껍데기가 아닌가
   — 일부러 틀린 구현을 넣었을 때 red가 되는가

## 7. 비목표 (명시적 배제)

- 티어2 20종 시나리오 — 후속 배치
- judge(비결정 평가) 활성화 — 별도 설계 필요
- CI에서 전체 스위트 실행 — 비용상 금지
- 에이전트 정의(`plugins/common/agents/**`) 수정 — **이번 배치는 측정만 늘린다. 대상을 바꾸지 않는다**
- 스위트 분할·병렬 실행 러너 개선
- `rules/` 변경 (0개)

## 8. 단계 (의존성 순서)

| Stage | 내용 | 산출물 |
| --- | --- | --- |
| **S1 골격** | `evals/policy.json` 도입 + 기준선 커버리지 검사 + `verify-done.sh` 신설 § + CI 동등 | 게이트가 **실제로 red를 감지**함을 실증 |
| **S2 확장 1차** | 파일 수정 에이전트 4종 시나리오 (`write-tests` `generate-boilerplate` `sync-docs` `optimize-logic`) | 시나리오 4건, `--validate` green |
| **S3 확장 2차** | 나머지 5종 (`write-api-tests` `implement-api` `verify-code` `explore-codebase` `plan-implementation`) | 시나리오 5건, `--validate` green |
| **S4 통합** | 전체 스위트 실행 → 기준선 재생성 → 게이트 green + ledger 부트스트랩 + P3 판정 + 문서/버전 | v2.15.0 릴리스 준비 완료 |

**S1의 골격 함정 대비**: 게이트를 만들고 "통과했다"로 넘어가지 않는다. **일부러 깨뜨려 red를 확인**하는 것이
S1의 완료 조건이다. 러너 설정이 잘못돼 검사가 아예 실행되지 않는데 green으로 보고되는 실패를 막는다.

## 9. 리스크

| 리스크 | 완화 |
| --- | --- |
| 저품질 시나리오 양산 (통과가 보장된 껍데기) | 수용 테스트 5번을 완료 조건에 넣는다 — **일부러 틀린 구현으로 red 확인** |
| 신규 시나리오가 기존 12건을 깨뜨림 | 12건은 특성화 테스트. S4에서 status 전부 pass 유지가 회귀 판정 기준 |
| 스위트 시간 폭증 | 실측을 기준선에 기록. 10분 초과는 기록만 하고 이번 범위 밖 |
| eval-forge 자체 결함이 드러남 | **그것이 도그푸딩의 목적이다.** 결함은 ledger로 회수 (P2-a의 첫 입력이 된다) |
