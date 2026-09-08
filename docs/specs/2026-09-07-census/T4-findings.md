# T4 — eval 자산 축 전수 문서 감사

> 감사자: 워커 (읽기 전용). 스코프 57개 파일. 정렬 대상:
> `docs/specs/2026-09-07-hiway-program-design.md`(D-1~D-21) — **단, 이 워크트리(census-T4)에는
> 이 파일이 없다.** §0 참고.

## §0. 선행 발견 — 이 워크트리는 origin/main보다 뒤처져 있다 (감사 전체에 영향)

작업 지시는 "워크트리가 `main`(커밋 `c707729`)에서 생성됐다"고 전제했다. **실측 결과 사실이 아니다.**

- 이 워크트리(census-T4)의 HEAD: `dd63b44`
- `origin/main`의 실제 HEAD: `c707729`
- `git merge-base --is-ancestor dd63b44 origin/main` → **참** (dd63b44는 origin/main의 조상, 즉
  이 워크트리는 origin/main에서 뒤처진 상태다 — first-parent 기준 7커밋, 병합된 커밋까지
  포함하면 총 11커밋: `git log --oneline dd63b44..origin/main` 실측, §4)
- 뒤처진 커밋에는 다음이 포함된다: `44c97c7`(W-024 트랙 A: consensus-builder eval 시나리오
  신설), `4b7b261`(W-024 트랙 B: tier2 커버리지·분류 완전성 게이트, `8fc29ff` "0종 발견 거짓
  green 봉쇄" 포함), `086b2ae`(W-024 기준선 재생성), 그리고 정렬 대상 자체인 설계 문서
  3커밋(`c84ab28`·`fe0806c`·`c707729`)
- 정렬 대상 문서는 `torpedo` 워크트리(브랜치 `This-HW/planning-control-session`, `c707729`)에서
  읽기 전용으로 확인했다(§4 참고)

**영향**: 스코프 57개 중 2개 파일(`evals/scenarios/consensus-builder/...`)이 이 워크트리에
**물리적으로 존재하지 않는다** — 파일이 나쁜 게 아니라 브리프가 가정한 워크트리 상태와 실제
워크트리 상태가 다르다. 아래 §1 표는 "이 워크트리 기준" 판정이다. 근본 원인은 콘텐츠 결함이
아니라 **워커 디스패치 시점에 브랜치 최신성을 확인하지 않은 것**이다 — §3에 새 결정으로 제안한다.

---

## §1. 커버리지 표 (57/57)

| # | 파일 | 판정 | 한 줄 근거 |
|---|------|------|-----------|
| 1 | evals/README.md | STALE | 서두(3~5행)가 "핵심 에이전트(review-code, fix-bugs, implement-code) 3종"만 서술 — 실제 커버리지는 tier1 13 + tier2 A 16 = 29종(2026-07-07 최초 작성 이후 미갱신) |
| 2 | evals/policy.json | CONFLICT | tiers.tier2에 `consensus-builder`(A등급)가 등재돼 있으나 이 워크트리엔 해당 시나리오 디렉토리가 없음 — §0 |
| 3 | evals/scenarios/analyze-dependencies/order-utils-impact/task.md | OK | 내용·참조 정합 |
| 4 | evals/scenarios/analyze-tech-debt/billing-fixme/task.md | OK | 내용 정합 |
| 5 | evals/scenarios/consensus-builder/hard-constraint-standoff/fixture/round1-synthesis.md | CONFLICT | 이 워크트리에 파일 부재(§0) — origin/main엔 존재, 내용 자체는 정상(§4) |
| 6 | evals/scenarios/consensus-builder/hard-constraint-standoff/task.md | CONFLICT | 이 워크트리에 파일 부재(§0) — origin/main엔 존재, 내용 자체는 정상(§4) |
| 7 | evals/scenarios/define-business-logic/point-service-rules/fixture/domain.md | OK | task.md와 참조 정합 |
| 8 | evals/scenarios/define-business-logic/point-service-rules/task.md | OK | 산출물 경로(docs/planning/business-logic/point-rules.md)가 W-023 file_contains 수정과 정합 |
| 9 | evals/scenarios/define-metrics/payment-api-metrics/fixture/system.md | OK | task.md와 참조 정합 |
| 10 | evals/scenarios/define-metrics/payment-api-metrics/task.md | OK | 내용 정합 |
| 11 | evals/scenarios/design-services/point-service-design/fixture/domain.md | OK | define-business-logic와 내용 동일(의도된 중복 — 아래 §4 비고) |
| 12 | evals/scenarios/design-services/point-service-design/task.md | OK | 내용 정합 |
| 13 | evals/scenarios/design-user-journey/checkout-edge-cases/fixture/checkout-request.md | OK | task.md와 참조 정합 |
| 14 | evals/scenarios/design-user-journey/checkout-edge-cases/task.md | OK | 산출물 경로가 W-023 file_contains 수정과 정합 |
| 15 | evals/scenarios/devils-advocate/single-instance-sync/fixture/design.md | OK | task.md와 참조 정합 |
| 16 | evals/scenarios/devils-advocate/single-instance-sync/task.md | OK | 내용 정합 |
| 17 | evals/scenarios/enforce-structure/misplaced-source/task.md | OK | fixture/project-structure.yaml 실재(§4) |
| 18 | evals/scenarios/explore-codebase/inventory-function-inventory/fixture/README.md | OK | 정황 설명용, 정합 |
| 19 | evals/scenarios/explore-codebase/inventory-function-inventory/task.md | OK | 내용 정합 |
| 20 | evals/scenarios/facilitator/review-rating-spec/fixture/feature-spec.md | OK | task.md와 참조 정합 |
| 21 | evals/scenarios/facilitator/review-rating-spec/task.md | OK | 내용 정합 |
| 22 | evals/scenarios/fix-bugs/mutable-default-arg/task.md | OK | fixture/{registry.py,test_registry.py} 실재(§4) |
| 23 | evals/scenarios/fix-bugs/none-handling/task.md | OK | fixture/{parser.py,test_parser.py} 실재(§4) |
| 24 | evals/scenarios/fix-bugs/off-by-one/task.md | OK | fixture/{stats.py,test_stats.py} 실재(§4) |
| 25 | evals/scenarios/fix-bugs/unstable-sort-key/task.md | OK | fixture/{ranking.py,test_ranking.py} 실재(§4) |
| 26 | evals/scenarios/generate-boilerplate/agent-md-skeleton/fixture/agents/dev/existing-example.md | OK | DELEGATION_SIGNAL 잔재 없음(§4 grep) |
| 27 | evals/scenarios/generate-boilerplate/agent-md-skeleton/task.md | OK | expect.json의 `# 역할:` 검사와 정합, 신호 재요구 없음 |
| 28 | evals/scenarios/git-workflow/feature-branch-commit/task.md | OK | git.json 실재, DELEGATION_SIGNAL 잔재 없음 |
| 29 | evals/scenarios/git-workflow/merge-conflict-escalation/task.md | OK | git.json 실재, DELEGATION_SIGNAL 잔재 없음 |
| 30 | evals/scenarios/impact-analyzer/3ds-payment-change/fixture/change.md | OK | task.md와 참조 정합 |
| 31 | evals/scenarios/impact-analyzer/3ds-payment-change/task.md | OK | 내용 정합 |
| 32 | evals/scenarios/implement-api/add-item-handler/task.md | OK | DELEGATION_SIGNAL 잔재 없음 |
| 33 | evals/scenarios/implement-code/add-function-to-module/task.md | OK | DELEGATION_SIGNAL 잔재 없음(W-022 R1 정화 확인) |
| 34 | evals/scenarios/implement-code/lru-cache/task.md | OK | DELEGATION_SIGNAL 잔재 없음 |
| 35 | evals/scenarios/implement-code/merge-intervals/task.md | OK | DELEGATION_SIGNAL 잔재 없음 |
| 36 | evals/scenarios/manage-api-versions/v2-breaking-change/fixture/CHANGELOG.md | OK | task.md와 참조 정합 |
| 37 | evals/scenarios/manage-api-versions/v2-breaking-change/task.md | OK | 내용 정합 |
| 38 | evals/scenarios/optimize-logic/on-squared-duplicate-finder/task.md | OK | 지시-이행 측정이 expect.json `_designNote`로 선언돼 있음(README 원칙과 정합) |
| 39 | evals/scenarios/plan-implementation/remove-all-widgets-plan/fixture/README.md | OK | 정황 설명용, 정합 |
| 40 | evals/scenarios/plan-implementation/remove-all-widgets-plan/task.md | OK | DELEGATION_SIGNAL 잔재 없음 |
| 41 | evals/scenarios/plan-refactor/god-function-decompose/task.md | OK | 내용 정합 |
| 42 | evals/scenarios/review-code/false-green/task.md | OK | 내용 정합, 금지 어구 없음 |
| 43 | evals/scenarios/review-code/off-by-one/task.md | OK | 내용 정합 |
| 44 | evals/scenarios/review-code/race-condition/task.md | OK | 내용 정합 |
| 45 | evals/scenarios/review-code/sql-injection/task.md | OK | 내용 정합 |
| 46 | evals/scenarios/security-scan/shared-tmp-and-hardcoded-token/NOTES.md | OK | fixture 밖 저엔트로피 근거 문서 — 죽은 자산 아님(작성자용 설계 기록) |
| 47 | evals/scenarios/security-scan/shared-tmp-and-hardcoded-token/task.md | OK | README §output_not_contains 사고(W-023)와 정합, 금지 어구 없음 |
| 48 | evals/scenarios/sync-docs/readme-function-count-drift/fixture/README.md | OK | "Functions: 2" 드리프트 셋업, task.md와 정합 |
| 49 | evals/scenarios/sync-docs/readme-function-count-drift/task.md | OK | 내용 정합 |
| 50 | evals/scenarios/synthesizer/launch-timeline-conflict/fixture/developer.md | OK | task.md와 참조 정합 |
| 51 | evals/scenarios/synthesizer/launch-timeline-conflict/fixture/planner.md | OK | task.md와 참조 정합 |
| 52 | evals/scenarios/synthesizer/launch-timeline-conflict/fixture/security.md | OK | task.md와 참조 정합 |
| 53 | evals/scenarios/synthesizer/launch-timeline-conflict/task.md | OK | 내용 정합 |
| 54 | evals/scenarios/verify-code/multiply-bug-detected/task.md | OK | DELEGATION_SIGNAL 잔재 없음 |
| 55 | evals/scenarios/verify-integration/signature-mismatch/task.md | OK | 내용 정합 |
| 56 | evals/scenarios/write-api-tests/divide-handler/task.md | OK | DELEGATION_SIGNAL 잔재 없음 |
| 57 | evals/scenarios/write-tests/clamp-function/task.md | OK | DELEGATION_SIGNAL 잔재 없음 |

**요약**: OK 53 · STALE 1 · CONFLICT 3 · DUP 0 · UNABSTRACTED 0 · ORPHAN 0 · UNKNOWN 0

---

## §2. 발견 상세

### F-1. `evals/README.md:3-5` — 서두 서술이 실제 커버리지를 크게 과소 서술 (STALE)

- **무엇이**: "핵심 에이전트(`review-code`, `fix-bugs`, `implement-code`)의 **행동 회귀**를 기계로
  검증하는 하네스"라는 문장이 마치 3종이 전체 대상인 것처럼 읽힌다.
- **어디가**: `evals/README.md:3-5`
- **왜 문제인가**: 이 문장은 2026-07-07 최초 작성(`f357a1b`, 시나리오 11개 시절) 이후 한 번도
  갱신되지 않았다. 현재 `evals/policy.json`의 tiers.tier1(13종) + tiers.tier2 A등급(16종) =
  **29종**이 커버리지 대상이고, 시나리오 디렉토리는 이 워크트리 기준 28개 에이전트 아래 37개
  존재한다(§4). 신규 독자가 이 문서만 보고 "3개 에이전트만 대상"이라고 오판할 수 있다.
- **무엇과 충돌하는가**: `evals/policy.json`의 `tiers.tier1`/`tiers.tier2` 목록, 그리고
  `evals/scenarios/` 실제 디렉토리 구조(§4 grep)와 규모가 어긋난다.
- **권고**: **축약·갱신**. "핵심 예시 3종"이라는 표현을 "tier1(파일 수정·게이트키핑·진입점
  13종) + tier2 A등급(16종), 총 29종 — 목록의 단일 소스는 `evals/policy.json`"으로 바꾸고
  구체적 에이전트 이름 나열은 policy.json에 위임한다(레포의 "산문에 숫자 중복 기재 금지"
  원칙, `evals/policy.json:3`의 `_comment`와 같은 논리).

### F-2. `evals/policy.json:58-76` — tier2 A등급 `consensus-builder`가 이 워크트리에서 시나리오 0건 (CONFLICT)

- **무엇이**: `tiers.tier2`(16종, A등급)에 `consensus-builder`가 등재돼 있고,
  `_tier2Rationale`(:76)은 "회계(2026-08-31): 티어1 13 + 티어2 A 16 + B 3 + C 1 = 33종.
  미분류 잔여 0"이라고 주장한다. **회계 산술 자체는 실측 검증 결과 정확하다**(§4) — 과거
  incident(문서에서 언급하는 "consensus-builder 사고": 분류엔 있는데 시나리오가 없어 조용히
  통과)와 달리 33종 분류 집합은 실제 에이전트 33종과 정확히 일치, 중복·누락 0이다.
  **그러나** 이 등재가 "A등급 = 시나리오를 갖추고 결정적으로 채점 가능"을 함의하는데, 정작
  `consensus-builder`의 시나리오 디렉토리(`evals/scenarios/consensus-builder/`) 자체가 **이
  워크트리에 없다**.
- **어디가**: `evals/policy.json:72`(tier2 배열의 `consensus-builder` 항목), `evals/policy.json:76`
  (그 항목이 정상 커버리지를 함의하는 회계 문장)
- **왜 문제인가**: §0에서 확인했듯 이 워크트리는 origin/main보다 뒤처져 있고(총 11커밋, §4), 뒤처진
  커밋에 W-024 트랙 A(consensus-builder 시나리오 신설)·트랙 B(정확히 이런 갭을 잡는
  `check_classification_complete` 게이트 신설)가 포함된다. 이 워크트리의
  `scripts/check_eval_coverage.py`에는 그 게이트가 없다 — tier1만 강제하고 tier2는
  경고조차 없다(§4). 즉 "분류엔 A로 있는데 시나리오가 없다"는, 문서 자신이 재발 방지
  대상으로 지목한 바로 그 결함 패턴이 **이 워크트리에서는 조용히 재현되고 있다.**
- **무엇과 충돌하는가**: `evals/scenarios/` 실제 디렉토리 목록(consensus-builder 없음),
  `evals/baseline/2026-08-31.json`의 results(consensus-builder 항목 없음 — 37건, 모두 다른
  28개 에이전트). 그리고 origin/main(`c707729`)의 실제 상태와도 충돌한다 — 그쪽엔 시나리오가
  이미 존재한다(§4, git show 확인).
- **권고**: **유지** — policy.json 자체를 고칠 필요는 없다. origin/main에는 이미 이 갭을 메운
  커밋(`44c97c7`, `4b7b261`, `086b2ae`)이 존재한다. 문제는 파일 내용이 아니라 **이 워크트리가
  그 커밋들을 담고 있지 않다는 것**이다 — §3의 새 결정(워크트리 최신성 확인) 채택으로 해소된다.

### F-3, F-4. `evals/scenarios/consensus-builder/hard-constraint-standoff/{task.md, fixture/round1-synthesis.md}` — 이 워크트리에 파일 부재 (CONFLICT)

- **무엇이**: 스코프에 지정된 두 파일이 이 워크트리에 존재하지 않는다.
- **어디가**: 경로 자체 (파일 부재이므로 줄 번호 없음)
- **왜 문제인가**: §0 근본 원인과 동일. `git log --all`로 확인한 결과 두 파일은 커밋
  `4332b47`("feat(evals): consensus-builder hard-constraint-standoff 시나리오 신설 —
  W-024 트랙 A")에서 생성됐고, 그 커밋은 브랜치 `This-HW/w024-track-a-eval`과
  `This-HW/planning-control-session`에는 있지만 이 워크트리가 기반한 `dd63b44`에는 없다.
- **무엇과 충돌하는가**: 브리프의 "워크트리는 main(c707729)에서 생성됐다"는 전제, 그리고
  `evals/policy.json`의 tier2 A등급 등재(F-2)와 충돌한다.
- **내용 자체 검증**: `git show origin/main:<path>`로 읽기 전용 확인한 결과(§4), 두 파일 모두
  내용상 결함이 없다 — task.md는 명확한 과제 지시, fixture는 GDPR(EU 역내 저장 의무) vs
  SLA(대륙 간 이중화) 두 개의 "양보 불가" 제약이 정면 충돌하는 시나리오로, README의 자기충족
  어서션 금지 원칙과도 상충하지 않는다(task.md가 정답 형식을 지시하지 않음).
- **권고**: **유지** — 파일 내용 자체는 손댈 것이 없다(이미 origin/main에 정상 병합돼 있음).
  이 워크트리에서 완전한 감사를 하려면 워크트리를 origin/main 기준으로 갱신해야 한다(컨트롤
  세션 몫 — §3).

---

## §3. 계획 정렬 (D-1~D-21 대조)

| 발견 | 흡수되는 결정 | 비고 |
|------|--------------|------|
| F-2, F-3, F-4 (consensus-builder 갭) | **어느 것에도 흡수 안 됨** — 근접 결정은 D-8("control-loop eval C등급 명시 등재" — 같은 "분류엔 있는데 시나리오 없음" 결함 클래스를 다루지만 대상이 다름)과 D-10(eval 잔재 청소 + 회귀 가드 — 유령 프로젝트 레지스트리 문제로, 워크트리 최신성과는 무관) | 내용 자체는 이미 origin/main에서 해결됨(W-024). 이 워크트리에 국한된 증상 |
| §0 (워크트리가 origin/main보다 뒤처짐, 총 11커밋) | **새 결정 필요** | 하이웨이 설계문서(W-025~027)는 이 문제를 다루지 않는다 — 그 문서는 레포 콘텐츠·배포 위생을 다루지, 감사·워커 디스패치용 워크트리 생성 시점의 브랜치 최신성은 다루지 않는다. 제안: "워커용 워크트리를 생성할 때 origin/main의 실제 HEAD 커밋을 브리프에 명시하고, 워커는 세션 시작 시 `git merge-base --is-ancestor <워크트리 HEAD> origin/main`으로 스테일 여부를 확인해 뒤처짐이 있으면 즉시 에스컬레이션한다." (orca 오케스트레이션 소관 — 이 킷의 D-1~21 범위 밖) |
| F-1 (README.md 서두 stale) | **새 결정 필요** | D-1~D-21 중 이 파일 내용을 직접 다루는 결정 없음. D-2(파리티 계약 "약속 문장이 같은 말을 해야 한다")는 하네스 파리티 이야기라 대상이 다르다. 제안: "evals/README.md 서두를 tier1/tier2 종수와 policy.json 참조로 축약하고, 향후 tier 종수가 바뀔 때 이 문단도 갱신 대상임을 policy.json의 `_comment`처럼 명시한다." |
| (참고) D-8 "control-loop eval은 C등급으로 명시 등재" | 이 트랙 스코프 밖 — `control-loop`는 W-026 산출물이며 아직 `evals/policy.json`에 없다(§4 확인). 존재하지 않는 게 정상(아직 신설 전) | 감사 대상 아님, 결함 아님 |
| (참고) D-13 "어서션 계약 단일 등록" | 이 트랙 스코프 파일(README/policy.json/task.md/fixture)에는 영향 없음 — `KNOWN_ASSERTION_TYPES`/`check_assertion` 이중 선언은 `evals/run.py` 내부 문제이고 실측 결과 현재 동기 상태(9=9, §4) | 정보성 확인만, 새 발견 아님 |

---

## §4. 실측 로그

```bash
# 워크트리/브랜치 상태
$ pwd && git log -1 --format="%H %s"
/Users/hw/orca/workspaces/claude-code-kit/census-T4
dd63b44 fix(ci): gitleaks private-project-names 오탐 해소 — 테스트 식별자 개명

$ git rev-parse origin/main
c70772962506c1fae2ddc7e188cc040d2c1106ca

$ git merge-base --is-ancestor dd63b44 origin/main && echo YES
YES   # census-T4 HEAD는 origin/main의 조상 — 뒤처짐

$ git log --oneline dd63b44..origin/main | wc -l
11    # 총 11커밋 (병합된 하위 커밋 포함)

$ git log --oneline dd63b44..origin/main
c707729 docs(spec): §9 주입 예산 재설계 — 규범 활성화를 규범 자신이 선언 (D-17~D-21)
fe0806c docs(spec): §8 구조 감사 추가 — 추상화·교체가능성 결정 5건 (D-12~D-16)
c84ab28 docs(spec): 하이웨이 프로그램 설계 최종본 — W-025~027 (하네스 중립 전환)
086b2ae chore(evals): W-024 기준선 재생성 + 포인터 갱신 + CHANGELOG
4b7b261 merge: W-024 트랙 B — 티어2 커버리지·분류 완전성 게이트
44c97c7 merge: W-024 트랙 A — consensus-builder hard-constraint-standoff 시나리오
aedacae fix(evals): 에스컬레이션 어서션 과대매칭 값 "사용자에게" 제거, 판정형 값 보강
4332b47 feat(evals): consensus-builder hard-constraint-standoff 시나리오 신설 (W-024 트랙 A)
8fc29ff fix(evals): check_classification_complete의 "0종 발견" 거짓 green 봉쇄
fdfea93 feat(evals): tier2 커버리지·분류 완전성 검사 신설 (W-024 Track B, D-3)
1631b65 docs(spec): W-024 티어2 커버리지 갭 봉쇄 배치 스펙 — 인계 전 선커밋

# 설계문서 SSOT 위치 확인 (이 워크트리엔 없음)
$ find . -iname "2026-09-07-hiway-program-design.md"   # 이 워크트리 내부, 결과 없음
$ find / -iname "2026-09-07-hiway-program-design.md" 2>/dev/null
/Users/hw/orca/workspaces/claude-code-kit/torpedo/docs/specs/2026-09-07-hiway-program-design.md
(+ 마켓플레이스 캐시 사본, 무시)

# 스코프 파일 존재 여부 (57개 전수)
$ while read -r f; do [ -f "$f" ] || echo "MISSING: $f"; done < scope_t4.txt
MISSING: evals/scenarios/consensus-builder/hard-constraint-standoff/fixture/round1-synthesis.md
MISSING: evals/scenarios/consensus-builder/hard-constraint-standoff/task.md

# 해당 파일의 실제 위치 확인
$ git log --all --oneline -- evals/scenarios/consensus-builder
aedacae fix(evals): 에스컬레이션 어서션 과대매칭 값 "사용자에게" 제거, 판정형 값 보강
4332b47 feat(evals): consensus-builder hard-constraint-standoff 시나리오 신설 (W-024 트랙 A)

$ git branch --all --contains 4332b47
+ This-HW/planning-control-session
  This-HW/w024-track-a-eval
  remotes/origin/HEAD -> origin/main
  remotes/origin/main

$ git show origin/main:evals/scenarios/consensus-builder/hard-constraint-standoff/task.md
$ git show origin/main:evals/scenarios/consensus-builder/hard-constraint-standoff/fixture/round1-synthesis.md
# (내용은 §2 F-3/F-4에 인용, 결함 없음 확인)

# 에이전트/시나리오 개수 실측
$ find plugins/common/agents -name "*.md" | wc -l
33

$ find evals/scenarios -mindepth 2 -maxdepth 2 -type d | wc -l
37    # 시나리오 인스턴스 수

$ find evals/scenarios -mindepth 1 -maxdepth 1 -type d | wc -l
28    # 시나리오를 가진 고유 에이전트 수 (consensus-builder 제외 상태)

# policy.json 회계 주장 검증 — 티어1 13 + 티어2 A 16 + B 3 + C 1 = 33, 미분류 0
$ python3 -c "
import json
d = json.load(open('evals/policy.json'))
tier1 = set(d['tiers']['tier1']); tier2 = set(d['tiers']['tier2'])
cls = d['tiers']['_tier2Classification']
b = {k for k,v in cls.items() if k!='_comment' and v.get('grade')=='B'}
c = {k for k,v in cls.items() if k!='_comment' and v.get('grade')=='C'}
union = tier1|tier2|b|c
agents = set(open('/tmp/agents33.txt').read().split())
print(len(tier1), len(tier2), len(b), len(c), len(tier1)+len(tier2)+len(b)+len(c))
print('agents - union:', agents-union, '| union - agents:', union-agents)
"
13 16 3 1 33
agents - union: set() | union - agents: set()
# → 산술·집합 대조 모두 정확. 회계 주장 자체는 참(과거 incident와 달리 이번엔 거짓 아님)

# check_eval_coverage.py가 tier2 갭을 잡는지 확인
$ python3 scripts/check_eval_coverage.py
✓ 모든 시나리오 디렉토리가 기준선에 존재
✓ 기준선의 모든 항목이 시나리오 디렉토리로 존재
✓ tier1 전 에이전트(13종) 최소 시나리오 보유
# → tier2 갭(consensus-builder 시나리오 0건)에 대한 언급 없음 — 이 워크트리의
#   check_eval_coverage.py에는 W-024 트랙B의 classification-completeness 검사가 없음(아래)
$ grep -n "def check\|classification" scripts/check_eval_coverage.py
175:def check_coverage(...)
210:def check_tier1(...)
# → check_classification_complete 없음

# DELEGATION_SIGNAL 잔재 검색 (스코프 57개 파일 대상)
$ grep -rn "DELEGATION_SIGNAL\|delegation_signal\|DELEGATE_TO" evals/scenarios/*/*/task.md evals/scenarios/*/*/fixture 2>/dev/null
(스코프 내 0건 — expect.json·baseline·tests에서만 발견되며 이들은 스코프 밖)

# 금지 어구("문제 없음" 등 5종) 잔재 검색 — 스코프 task.md/fixture 대상
$ grep -rln "문제 없음\|문제가 없\|이상 없음\|looks fine\|looks good" evals/scenarios/ 2>/dev/null
evals/scenarios/analyze-dependencies/order-utils-impact/expect.json   # 스코프 밖
evals/scenarios/define-business-logic/point-service-rules/expect.json # 스코프 밖
# → 스코프 파일(task.md/fixture .md) 자체에는 0건

# 어서션 타입 9종 동기화 확인 (README 문서화 vs run.py 실제)
$ grep -n "KNOWN_ASSERTION_TYPES" -A15 evals/run.py | head -14
output_regex, output_contains_any, output_not_contains, pytest_green,
file_contains, file_unchanged, git_log_contains, git_branch_exists, git_status_clean  = 9종
# → README.md의 예시 9종과 정확히 일치, delegation_signal 없음(정상 제거 확인)

# verify-done.sh §10 = evals/run.py --validate 매핑 확인
$ sed -n '460,480p' scripts/verify-done.sh | grep -n "10\.\|run.py --validate"
468:hdr "10. Agent evals 스키마 ..."
474:  python3 evals/run.py --validate ...
# → README의 "§10" 인용 정확

# README §자기충족 어서션 금지에서 인용한 _designNote 실재 확인
$ grep -n "_designNote" evals/scenarios/optimize-logic/on-squared-duplicate-finder/expect.json
25: "_designNote": "이 시나리오는 최적화 발상이 아니라 지시 이행 + 정확성을 측정한다..."
# → README의 인용 정확

# fixture 참조 실재 확인 (fix-bugs 4종, enforce-structure)
$ find evals/scenarios/enforce-structure/misplaced-source -maxdepth 3
.../fixture/project-structure.yaml, fixture/utils/parser_helper.py, fixture/src/main.py  (모두 존재)
$ find evals/scenarios/fix-bugs/{mutable-default-arg,none-handling,off-by-one,unstable-sort-key} -maxdepth 2
(각 registry.py/test_registry.py, parser.py/test_parser.py, stats.py/test_stats.py,
 ranking.py/test_ranking.py 모두 존재)

# baseline 2026-08-31.json 내용 대조
$ python3 -c "import json; d=json.load(open('evals/baseline/2026-08-31.json')); print(len(d['results']))"
37   # 시나리오 수와 일치, consensus-builder 항목 없음(§4 위 grep과 일치)

# design-services/point-service-design/fixture/domain.md 와
# define-business-logic/point-service-rules/fixture/domain.md 내용 동일 여부
$ diff evals/scenarios/design-services/point-service-design/fixture/domain.md \
       evals/scenarios/define-business-logic/point-service-rules/fixture/domain.md
(차이 없음 — 완전 동일)
# → README의 시나리오 아키텍처(각 fixture/는 실행 시 temp 디렉토리로 격리 복사되어야
#   하므로 심링크/공유 include를 지원하지 않음)상 의도된 중복으로 판단, OK 유지
```
