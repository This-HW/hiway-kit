# W-024 — 티어2 커버리지 갭 봉쇄 + `consensus-builder` eval 신설

- 작성: 2026-09-04, 컨트롤 세션(torpedo-b5)
- 상태: 인계 전 선커밋 (구현은 하위 워크트리 2종 병렬)
- 선행: W-018(커버리지 게이트 신설) · W-022 R3(티어2 A등급 15종) · W-023(git-workflow 승격)

---

## 1. 관측된 결함

`evals/policy.json` 의 `_tier2Rationale` 는 이렇게 주장한다:

> **회계(2026-08-31): 티어1 13 + 티어2 A 16 + B 3 + C 1 = 33종. 미분류 잔여 0.**

그런데 실제 시나리오 디렉토리는 **28개**다. 차이 1건이 `consensus-builder` —
`tiers.tier2` 에 A등급으로 등재돼 있으나 `evals/scenarios/consensus-builder/` 는
**어느 브랜치·어느 커밋에도 존재한 적이 없다**(`git log --all -- 'evals/scenarios/consensus-builder*'`
결과 0건).

**왜 게이트가 green 이었나.** `scripts/check_eval_coverage.py` 에 문자열 `tier2` 가
**한 번도 나오지 않는다.** 이 스크립트가 하는 검사는 셋뿐이다:

1. 시나리오 ⊆ 기준선
2. 기준선 ⊆ 시나리오
3. **티어1** 각 에이전트 최소 시나리오 보유 (`tier1CoverageEnforceFail: true`)

`consensus-builder` 는 시나리오가 없으니 (1)(2) 어느 집합에도 등장하지 않고, 티어1이
아니므로 (3)에도 걸리지 않는다. **검사 대상이 아닌 것은 결코 red 가 되지 않는다.**

`_tier2Rationale` 는 "tier2 는 경고 수준 커버리지로만 다룬다"고 적어 뒀지만,
**경고조차 구현돼 있지 않다.** 정책 문서가 주장하는 강제와 코드가 하는 일이 어긋난
형태이며, 이것이 W-022 R3 에서 A등급 16종 중 1종이 조용히 빠진 것을 아무도 잡지 못한
경로다.

> 이 결함은 CLAUDE.md 가 이미 세 번 기록한 클래스와 같다 — **"검사 전용 모드에도 같은
> 봉쇄를 건다"**(설정값 경로 봉쇄 §4)와 **"검사할 대상이 0개를 통과로 오인하는 거짓
> green"**(`validate_policy_schema` docstring). 이번 것은 그 세 번째 변주다:
> *선언된 검사 범위와 실제 검사 범위가 다르다.*

---

## 2. 결정

### D-1 — `consensus-builder` 는 A등급이 맞다. 시나리오를 만든다

재분류(B강등)가 아니라 승격 이행이 정답이다. 근거:

- 이 에이전트의 `tools:` 는 `Read` + `AskUserQuestion` 뿐이고 파일을 쓰지 않는다.
  산출물이 **출력 텍스트뿐**인 에이전트는 이미 A등급으로 검증되고 있다
  (`impact-analyzer`·`devils-advocate` 가 `output_contains_any` + `file_unchanged`
  조합으로 채점된다). 러너 밖 조건이 필요 없다.
- `AskUserQuestion` 보유가 자동으로 B등급 사유가 되지는 않는다. `clarify-requirements`
  가 B인 이유는 그 에이전트의 **주된 산출물 자체가 사용자 왕복**이기 때문이고,
  `consensus-builder` 에게 그것은 정의상 **"최후"** 경로다(정의 §3단계 합의 전략:
  Win-Win 60% → 조건부 30% → 사용자 위임 10%).

### D-2 — 시나리오는 "위장된 합의"를 잡는 것으로 설계한다

`hard-constraint-standoff`. fixture 는 Round 1 종합 결과를 담고, 충돌 2건을 준다:

| 충돌 | 성격 | 기대 행동 |
| --- | --- | --- |
| A | **Hard vs Hard** (법적 의무 vs 계약 SLA) — 양쪽 다 양보 불가 | 합의안을 지어내지 않고 **사용자 결정으로 올린다** |
| B | 협상 가능 (일정 vs 범위) | 트레이드오프 제시 후 **합의안 도출** |

잡으려는 실패는 **W-023 의 `git-workflow` 결함과 같은 클래스**다: 해결 불가를
"✅ 전원 합의"로 위장해 보고하는 것. 그때는 충돌을 `--theirs` 로 조용히 밀고
"성공적으로 병합되었습니다"라고 했다. 여기서는 양보 불가 제약을 깎아 만든 가짜
Win-Win 이 같은 모양이다. 에이전트 정의의 주의사항 *"안전을 희생하지 않는다"*,
*"합의를 강요하지 않는다 → 진짜 합의 vs 굴복 구분"* 이 검사 대상 규범이다.

**자기충족 어서션 금지**(`evals/README.md` §): `task.md` 는 *"충돌을 분석해 합의안을
도출하라"* 까지만 말한다. 충돌 식별자·에스컬레이션 여부·Hard Constraint 라는 판정은
전부 fixture 를 읽어야만 나오는 값이어야 한다. `task.md` 에 기대 출력의 형식이나
값을 적으면 그 시나리오는 능력이 아니라 지시 따르기를 측정한다.

### D-3 — 게이트에 티어2 검사를 넣되, 플래그로 승격 가능하게

`check_eval_coverage.py` 에 두 검사를 추가한다. 숫자·목록은 하드코딩하지 않고
`evals/policy.json` 이 단일 소스라는 기존 관례를 그대로 따른다.

| 검사 | 대상 | 판정 | 플래그 |
| --- | --- | --- | --- |
| 티어2 커버리지 | `tiers.tier2`(A등급) 각 에이전트 최소 시나리오 | **fail** | `gate.tier2CoverageEnforceFail: true` |
| 분류 완전성 | 전체 에이전트 = tier1 ∪ tier2 ∪ `_tier2Classification`(B·C) | **warn** | `gate.classificationCompleteEnforceFail: false` |

- **커버리지를 곧바로 fail 로 놓는 이유**: 이 배치가 유일한 갭(`consensus-builder`)을
  같이 갚으므로 승격 직후 16/16 green 이다. 영구 노란 경고를 남기면 아무도 안 본다 —
  `tier1CoverageEnforceFail` 이 S1 경고 → S4 fail 로 간 전례와 달리, 여기서는 갭과
  게이트가 같은 배치에 있으므로 단계를 나눌 이유가 없다.
- **분류 완전성을 warn 으로 두는 이유**: 새 에이전트를 추가하는 무관한 작업이
  분류 등재 전까지 red 가 되면, 게이트가 작업을 막는 방향으로 오작동한다. 경고는
  `verify-done.sh` 매 실행에 출력되므로 침묵하지 않는다. 승격이 필요해지면 플래그만
  올린다(코드 무변경 — D1 관례).
- 플래그 부재 시 기본값은 **안전한 쪽**(미승격 = warn)이며, 섹션(`tiers`/`gate`/
  `coverage`) 자체가 통째로 없으면 기존 `validate_policy_schema` 가 그대로 exit 1 을
  낸다. `tiers.tier2` 가 **빈 배열이거나 없으면 fail** 이다 — "검사 대상 0개를
  통과로 오인"하는 거짓 green 이 바로 이 배치가 잡은 결함이므로, 같은 구멍을
  새 검사에 다시 뚫지 않는다.

### D-4 — 버전은 올리지 않는다

변경 범위가 `evals/`·`scripts/`·`docs/` 로 전부 **레포 로컬**이다. `plugins/` 아래
배포물(에이전트·스킬·룰·훅) 무변경이므로 소비자 동작 변경이 없고, 플러그인 캐시 키를
움직일 이유가 없다. CHANGELOG `[Unreleased]` 에 기록한다.

> 단, `consensus-builder.md` 를 **고치게 되면** 그 순간 소비자 동작 변경이므로 이
> 결정은 무효다 — 패치 범프 + CHANGELOG 릴리스 엔트리 + 태그로 전환한다.
> (D-6 이 이 분기를 다룬다.)

### D-5 — 기준선은 전량 재실행으로 재생성한다

시나리오를 1건 추가하면 `requireBaselineCoversAllScenarios` 가 즉시 red 다.
`baseline._meta.regenerationCadence` 가 이미 규정한다 — *"시나리오를 추가한 Stage 는
그 Stage 안에서 기준선을 재생성한다"*. 부분 실행(`--agent`)은 `--baseline` 저장이
거부되므로 **38건 전량 재실행**이 유일한 경로이며, 이 배치의 주된 실행 비용이다.
포인터(`baseline.file`)와 `_meta.sourceW024` 를 함께 갱신한다.

### D-6 — 첫 실행 실패는 결함 관측이다. 어서션을 약화시키지 않는다

`hard-constraint-standoff` 가 첫 실행에서 실패하면 그것은 **실재하는 에이전트 결함**이다
(W-023 에서 `merge-conflict-escalation` 이 정확히 그랬고, 그 관측이 v2.17.0 의 유일한
소비자 동작 변경이 됐다). 어서션을 느슨하게 고치는 것이 아니라, 정의를 고치고
연속 2회 통과로 검증한 뒤 D-4 를 패치 릴리스로 전환한다.

---

## 3. 작업 분할 (병렬 워크트리)

| 트랙 | 산출물 | 모델 |
| --- | --- | --- |
| **A** | `evals/scenarios/consensus-builder/hard-constraint-standoff/` 3파일 + 실측 실행 로그 | sonnet |
| **B** | `check_eval_coverage.py` 티어2·분류 검사 + `policy.json` 키 + 단위 테스트 + 문서 회계 | sonnet |
| **C** | 통합 후 문서 회계 전수 대조 (읽기 전용) | haiku |

**머지는 순차**(`rules/parallel-worktree.md`): A → B → C. B 의 워크트리에서는
`tier2CoverageEnforceFail: true` 가 A 의 시나리오 부재로 red 를 낼 수 있다 — 이는
예상된 상태이며, B 는 `--root` 가짜 레포 픽스처 테스트로 로직을 증명한다
(`scripts/tests/test_eval_coverage.py` 의 기존 관례).

---

## 4. 범위 밖 (명시적으로 하지 않는 것)

- **B등급 3종 승격**(`research-external`·`analyze-domain`·`clarify-requirements`) —
  승격 조건이 러너 밖에 있다. W-023 §5 판정 그대로 유지.
- **`facilitator-teams`(C) 승격** — 팀 모드 구동 경로 부재. C로 유지.
- **드리프트 게이트 3종 통합** — CLAUDE.md 가 rule of three 근거로 보류한 판정. 유효하다.
  이번에 추가하는 것은 4번째 드리프트 게이트가 아니라 **기존 §13 의 검사 범위 확장**이다.
- **`define-business-logic/point-service-rules` 안정화** — 기준선 재생성 중 재실패
  가능성이 알려져 있다(`_meta.sourceW023`: "동전 던지기"). 별도 배치의 몫이며, 이
  배치에서 재실패하면 재실행으로 처리하고 사실대로 기록한다.

---

## 5. 수용 테스트 (사람이 손으로 확인할 것)

1. `./scripts/verify-done.sh` → 기계 검사 **전부 pass**, §13 출력에 티어2 줄이 보인다
2. `python3 -m pytest` → **455건 이상**, 순감소 없음
3. `python3 scripts/check_eval_coverage.py` 단독 실행 → 티어2 16/16 + 분류 33/33
4. **역실증**: `evals/scenarios/consensus-builder` 를 임시로 옮기면 §13 이 **red**
   (`tier1CoverageEnforceFail` 승격을 STAGE4 에서 실증한 것과 같은 방식)
5. `evals/scenarios/consensus-builder/hard-constraint-standoff/` 에 3파일 존재,
   `task.md` 에 기대 출력값·형식 지시 **없음**
6. 새 기준선에 `consensus-builder/hard-constraint-standoff` 등재, 기존 37건 status 유지
7. `_tier2Rationale` 의 회계 문장이 실제 파일 수와 일치
