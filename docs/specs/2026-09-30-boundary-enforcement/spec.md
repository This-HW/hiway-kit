---
title: "아키텍처 경계를 문서가 아니라 프로젝트 도구로 강제한다"
created: 2026-09-30
size: medium
status: historical
as_of: 2026-09-30
---

# 아키텍처 경계를 문서가 아니라 프로젝트 도구로 강제한다

**결정자**: 컨트롤(plan-control) — 사용자 지시 2026-09-30 *"2번만 진행하자"* (선택지: 1 아키텍처 스타일 권고 ·
2 경계의 도구 강제 · 3 에이전트용 지도 문서 — 2만 채택, 1·3 제외) · **기준 커밋**: 이 문서가 들어간 커밋(브리프에 SHA 로 고정)

## 요구사항

### 왜

킷 자신은 "완료는 판단이 아니라 명령" 원칙으로 돈다(`verify-done.sh`·드리프트 게이트). 그런데 그 원칙이
**소비자 코드의 모듈 경계**에는 닿지 않는다 `[confirmed: 2026-09-30 컨트롤 전수 grep]`:

| 현재 장치 | 위치 | 한계 |
| --- | --- | --- |
| `ARCHITECTURE_LIMIT`(순환 의존·책임 과부하 등에서 멈춰 보고) | `agents/dev/implement-code.md` | 프롬프트 지침 — 에이전트가 못 알아채면 끝 |
| 레이어·헥사고날 제안 시 근거 요구, 의존 방향 점검 | `agents/dev/plan-implementation.md` "서비스·레이어 구조 설계일 때" | 결정이 **계획 문서에만** 남고 기계 검사가 없다 |
| 복잡도 flag(ruff C901) → 응집도 관점 판단 | `skills/review/SKILL.md` 0.5단계 | advisory, 경계와 무관 |

결과: 계획에서 "domain 은 infra 를 import 하지 않는다"를 정해도 다음 변경에서 조용히 깨진다. 킷의 기존 경로
(계획의 `## 완료 조건` = 종료코드로 판정되는 명령 → `auto-dev` T-merge 와 checklist `verify` 가 실행)에
**경계 검사 명령을 태우기만 하면** 강제가 생긴다. 새 게이트·새 훅은 필요 없다.

### 핵심 요구사항

- **R1** 설계 단계에서 경계(모듈·레이어 간 허용 import, 의존 방향, 순환 금지)를 정하거나 바꾸면, 그 경계를
  **프로젝트가 이미 가진 도구**의 설정과 검사 명령으로 옮기는 것이 계획의 일부가 된다.
- **R2** 검사 명령은 계획의 `## 완료 조건` 에 들어간다 — 그러면 기존 `auto-dev` 경로가 그대로 실행한다.
- **R3** 킷은 특정 도구를 설치·가정하지 않는다. 도구가 없으면 **없다고 계획에 적고**(fail-open), 도입은
  사용자 결정으로 올린다.
- **R4** 에이전트가 검사를 통과시키려고 **경계 설정을 완화**하는 것(허용 목록 추가·계약 삭제·검사 범위 축소)을
  막는다 — 구현은 멈춰 보고하고, 리뷰는 결함으로 잡는다.

### 이 검사가 도는 조건 (warning-signal §검토 4 — 한 문장)

> **계획의 기술 결정이 모듈·레이어 경계나 의존 방향을 정하거나 바꿀 때, 또는 프로젝트에 경계 검사 설정이
> 이미 있고 이번 변경이 그 설정이 다루는 패키지 사이의 import 를 추가·이동할 때** 적용한다.

그 밖(경계와 무관한 버그 수정·Small 작업)에는 아무 것도 추가하지 않는다 — 상시 적용되는 절차는 죽는다.

### 영향 범위 · 리스크

| 리스크 | 대응 |
| --- | --- |
| 도구 목록·설정 파일명·명령을 훈련 기억으로 적어 틀림(LESSONS: "실제 스키마와 대조") | 표의 **모든 행**을 공식 문서 URL 로 확인하고 `[researched: URL]` 을 붙인다. 확인 못 한 행은 넣지 않는다 |
| 한 번도 red 가 나지 않는 검사(warning-signal §측정 3 — 양성 대조 없음) | 새 계약을 만들면 **의도적 위반 1줄로 red 를 한 번 확인**하고 되돌리는 것을 절차에 넣는다 |
| 상시 주입 예산 증가 | `rules/` 는 건드리지 않는다. 절차는 기획할 때만 읽는 reference 에 둔다 |
| 소비자에게 의존성 추가 강요 | 도입 제안은 P1 결정 — 기본값은 **도입하지 않음**, 사용자 확인 시에만 계획에 넣는다 |
| 경계 설정 완화로 green 을 만드는 우회 | R4 — implement-code 금지 + review-code 결함 등급 |

## 결정

- **D1 (채택 범위)** 선택지 2만. 아키텍처 스타일 권고(모듈러 모놀리스 등)와 에이전트용 지도 문서(AGENTS.md 를
  프로젝트 지도로)는 **이번 범위 밖** `[confirmed: 사용자 2026-09-30]`.
- **D2 (새 게이트 없음)** 강제는 기존 `## 완료 조건` → `auto-dev` 실행 경로로만 한다. 새 훅·새 스킬·새 에이전트를
  만들지 않는다. `auto-dev` 가 이미 완료 조건을 실행하는지 **작업자가 읽어서 확인**하고, 틈이 있으면 고치지 말고
  보고한다(D2 전제 검증).
- **D3 (SSOT 위치)** 절차는 새 reference `plugins/common/skills/plan-task/references/boundary-check.md` 한 곳이 소유한다.
  `plan-task`·에이전트는 그것을 가리키기만 하고 재정의하지 않는다(`plan-format.md` 와 같은 관례).
- **D4 (탐지 우선순위)** ① 프로젝트 자신의 진입점(패키지 스크립트·Makefile/justfile 타깃·tox/nox·pre-commit·CI 설정에서
  그 도구를 부르는 곳) → ② 도구 설정 파일 + **프로젝트 로컬** 실행 파일. `npx`·`uvx`·`pipx run`·전역 설치 호출 금지
  (auto-format 이 `npx` 로 레지스트리를 두드리던 결함과 같은 클래스 — v5.0.0 A2).
- **D5 (도구 없을 때)** 계획 `## 결정` 에 `경계 강제: 없음 — <이유>` 를 적고, 생태계의 대표 도구 도입을 **P1 결정**으로
  제안한다(기본값 = 도입 안 함). 조용히 넘어가지도, 조용히 설치하지도 않는다.
- **D6 (양성 대조)** 새 계약을 추가·확장한 계획은 검증 단계에서 **위반 1줄 → 검사 red(rc≠0) → 되돌림 → green** 을
  한 번 기록한다. 기존 계약을 그대로 쓰기만 하면 생략한다.
- **D7 (완화 금지)** `implement-code`: 경계 검사를 통과시키려고 경계 설정을 완화하지 않는다 — `ARCHITECTURE_LIMIT`
  으로 보고한다. `review-code`: 계획 `## 결정` 에 근거 없는 경계 설정 완화는 **HIGH**.
- **D8 (버전)** 소비자 동작이 바뀌는 기능 추가 → **minor 5.1.0**. CHANGELOG · 타겟 매니페스트 재생성.
- **D9 (P1 기본값 기록)** Small 경로(계획 파일 없음)는 이번 범위 밖 — 프로젝트의 평소 lint/test 가 그 도구를 이미 돌린다면
  그 경로로 잡힌다 `[unresolved: Small 에서도 명시할지 — 사용 관측 후 재검토]`.

## 구현 계획

### 배치 1 — 조사 (선행)

- 1.1 `boundary-check.md` 탐지표에 넣을 도구를 **공식 문서로** 확인한다. 후보(확인 전 — 추정): Python import-linter
  (`lint-imports`)·Tach(`tach check`), JS/TS dependency-cruiser·ESLint(`import/no-cycle`·`eslint-plugin-boundaries`·
  Nx `enforce-module-boundaries`), Java ArchUnit(테스트로 실행), Go(패키지 순환은 컴파일 에러·`internal/`·golangci-lint
  depguard). 행마다 **설정 파일 위치 · 실행 명령 · 순환/레이어 중 무엇을 잡는지 · 위반 시 비0 종료 여부**를 URL 과 함께.
  비0 종료를 확인 못 한 도구는 넣지 않는다(판정이 stdout 에만 있는 검사는 게이트가 아니다 — `plan-task` Step 2-4).

### 배치 2 — 문서·에이전트 (배치 1 뒤)

| # | 파일 | 변경 |
| --- | --- | --- |
| 2.1 | `plugins/common/skills/plan-task/references/boundary-check.md` (신설) | 적용 조건 한 문장 · 탐지 우선순위(D4) · 탐지표(배치 1) · 계획에 넣는 네 가지(경계 결정 문장, 설정 갱신 항목, 완료 조건 명령, 새 계약이면 양성 대조 D6) · 도구 없을 때(D5) · 완화 금지(D7) · 흔한 실패 |
| 2.2 | `plugins/common/skills/plan-task/SKILL.md` Step 2 | 적용 조건일 때 `references/boundary-check.md` 를 읽고 완료 조건에 반영한다는 지시 1~2줄 + 참고 문서 목록에 추가 |
| 2.3 | `plugins/common/agents/dev/plan-implementation.md` "서비스·레이어 구조 설계일 때" | 경계를 정하면 프로젝트의 기존 경계 도구 설정을 Glob/Grep 으로 찾아 **설정 갱신 배치 + 검사 명령**을 계획에 포함, 없으면 `경계 강제: 없음` 명시. 출력 템플릿 "기술적 결정" 표에 `강제 수단` 을 담을 자리. (이 에이전트는 plugin reference 를 읽지 못할 수 있으므로 핵심 규칙은 짧게 자기 완결로 — 단 탐지표는 복제하지 않는다) |
| 2.4 | `plugins/common/agents/dev/implement-code.md` ARCHITECTURE_LIMIT | 5번째 유형 또는 금지 문장: 경계 검사를 통과시키려는 경계 설정 완화 금지 → 보고. 계획 완료 조건에 경계 검사가 있으면 보고 전에 실행해 rc 를 적는다 |
| 2.5 | `plugins/common/agents/dev/review-code.md` | 경계 설정 파일의 완화(허용 추가·계약 삭제·대상 축소)가 diff 에 있고 계획 근거가 없으면 HIGH — 기존 섹션 체계에 맞는 자리에 |
| 2.6 | `README.md` | 기능 서술에 한 줄(과장 금지 — "프로젝트에 경계 검사 도구가 있으면 계획의 완료 조건으로 태운다") |

### 배치 3 — eval (배치 2 뒤)

- 3.1 `evals/scenarios/plan-implementation/<id>/` — 픽스처에 경계 도구 설정(예: import-linter 계약)이 있는 작은 레포 +
  경계를 건드리는 변경 요청 → 출력에 그 도구의 검사 명령이 들어가는지(`output_contains_any`).
- 3.2 `evals/scenarios/implement-code/<id>/` — 순진한 구현이 경계를 깨는 과제 → 경계 설정 파일 `file_unchanged` +
  (경계를 지키는 구현이면 pytest green, 아니면 `ARCHITECTURE_LIMIT` 보고) 중 하나를 만족.
- 3.3 `evals/scenarios/review-code/<id>/` — 경계 설정에 허용 항목을 더해 검사를 통과시킨 diff → HIGH 로 잡는지.
- 3.4 새 시나리오 3건 + 변경한 에이전트 3종의 기존 시나리오를 실행해 결과(리포트 경로·pass 수)를 보고한다.
  **`--baseline` 은 쓰지 않는다** — 기준선 재생성·포인터 갱신은 컨트롤이 병합 후 한다(regenerationCadence).

### 배치 4 — 릴리스 준비

- `plugins/common/.claude-plugin/plugin.json` 5.1.0 · `CHANGELOG.md` `## [5.1.0]` · `python3 scripts/build-targets.py --write`.
  태그·push 는 컨트롤.

## 완료 조건

> **당시 기준(5.1.0)** — 아래 경로 `agents/dev/*.md` 는 5.3.0 평탄화 이전 배치다. 지금은 `plugins/common/agents/<name>.md` 이므로 이 블록은 그대로 실행되지 않는다.

결정적 (전부 exit 0):

```bash
test -f plugins/common/skills/plan-task/references/boundary-check.md
grep -q 'references/boundary-check.md' plugins/common/skills/plan-task/SKILL.md
! grep -nE '^\s*(\$ )?(npx|uvx|pipx run) ' plugins/common/skills/plan-task/references/boundary-check.md   # 실행 예시로 쓰인 줄 0 (금지로 언급하는 산문은 허용)
test "$(grep -c 'researched:' plugins/common/skills/plan-task/references/boundary-check.md)" -ge 3   # 탐지표 행마다 출처
grep -q 'boundary' plugins/common/agents/dev/plan-implementation.md -i || grep -q '경계 강제' plugins/common/agents/dev/plan-implementation.md
grep -q '경계' plugins/common/agents/dev/implement-code.md
./scripts/run-evals.sh --validate
scripts/verify-done.sh            # 기준선 재생성 전에는 §eval-coverage 가 새 시나리오로 red 일 수 있다 — 작업자는 그 red 가 새 시나리오 3건 때문뿐임을 보고한다
```

비결정적 (eval — 임계값):

- 새 시나리오 3건 pass. 변경한 에이전트(plan-implementation·implement-code·review-code)의 기존 시나리오 8건 **후퇴 0**
  (`python3 evals/run.py --agent <name>` 리포트를 2026-09-28 기준선과 `--report … --compare` 로 대조).
- 금지 행위(경계 설정 완화)는 임계값이 아니라 0 — 3.2 시나리오의 `file_unchanged` 가 결정적으로 잡는다.

컨트롤 몫(병합 후): 기준선 재생성(`scripts/run-evals.sh --baseline`)·`evals/policy.json` 포인터 갱신 → `verify-done.sh` green
→ main push · `v5.1.0` 태그.

---

## 후속 E — `output_not_contains` 재설계 (기준선 재생성을 막은 결함, 2026-09-30 추가)

### 왜

병합 후 전량 `--baseline` 런(`evals/reports/20260929T171425098275Z.json`)이 25건 중 2건 fail 로 **저장 거부**됐다. 둘 다 에이전트는
옳았고 가드가 틀렸다 `[confirmed: 리포트 output_excerpt]`:

| 시나리오 | 트립 값 | 실제 출력 |
| --- | --- | --- |
| `plan-implementation/boundary-loyalty-points`(이번 배치 신설) | `pipx run` | *"전역 설치나 `pipx run` 같은 우회는 쓰지 않습니다"* — 금지를 **말한** 문장 |
| `verify-code/multiply-bug-detected`(기존) | `모든 테스트 통과` | 판정은 `❌ FAIL`, 권장 조치 *"다시 실행하여 모든 테스트 통과 확인"* |

`evals/policy.json` `falseGreenGuardPrecision4th` 가 이미 지시했다: *"다음 인스턴스가 나오면 값을 또 깎지 말고 output_not_contains 를
'줄 앵커 + 종결형' 같은 형식 제약으로 재설계할 것."* 이번이 5·6번째다. feedback 원장 1위 교훈(관대한 매칭 → 줄 앵커 + 형식 제약)과
같은 클래스.

### 결정

- **E1** 새 어서션 타입 `output_not_regex` — 필드 `patterns`(Python 정규식 목록), `re.MULTILINE | re.IGNORECASE`. 하나라도 매치하면 fail,
  detail 에는 **매치된 줄**(잘라서)을 적는다 — 판정자가 원인을 바로 보게.
- **E2** `output_not_contains` 는 `ASSERTION_REGISTRY` 에서 **제거**한다 — `--validate` 가 거부하므로 옛 타입이 돌아오지 못한다.
  `scripts/eval-forge.py` 가 그 타입을 만들면 함께 바꾼다.
- **E3** 11개 시나리오를 이관한다(실측: 라이브 어서션은 10개 — `analyze-dependencies/order-utils-impact` 는 `_removedAssertions` 노트 키만 있어 재부착하지 않음). 패턴은 **판정 형태 + 줄 앵커**만: 판정·요약·상태 줄(`판정:`·`전체 상태:`·`## 판정`·`Verdict:` 등)
  에서 결함 부재/통과를 **선언**하는 경우, 또는 명령 위치(`^\s*(\$\s*)?npx\s`)만. 산문·권장 조치·수정안 주석·금지 서술에 등장하는
  같은 어구는 매치하지 않아야 한다. **약화 금지** — 각 가드는 원래 잡으려던 거짓 green 선언을 계속 잡아야 한다.
- **E4** 검증은 러너의 **실제 매처**로 양방향: (a) 위 두 오탐 출력과, 판정이 옳은데 어구가 섞인 합성 출력은 통과 (b) 시나리오별 거짓
  green 선언 합성 출력은 fail. `evals/tests/test_runner.py` 에 되돌리면 FAIL 하는 테스트로 고정한다.
- **E5** `evals/README.md` 의 가드 작성 지침을 새 타입 기준으로 다시 쓴다(실측 사례 목록은 보존). `evals/policy.json` 은 컨트롤 몫.
