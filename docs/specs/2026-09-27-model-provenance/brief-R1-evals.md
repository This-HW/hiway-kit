# 브리프 R1 — evals 리뷰 반영 (W-045)

- 부모: plan-control 컨트롤 (Orca Run). 역할: `evals/run.py`·`evals/tests/test_runner.py` 의 리뷰 지적 반영
- 워크트리: Orca new-child, 자기 브랜치에만 커밋. 기준 커밋: 디스패치 spec 해시
- 먼저 `docs/specs/2026-09-27-model-provenance/review-fix.md` 를 읽는다 (**child-session 은 Skill 로드 금지 — Read**)

## ① 전제 (코드 리뷰어 지적 — 착수 전 코드로 재확인)

- C-ATK-001 [H]: `resolved_models` 축이 `modelUsage` 키 **전부**의 합집합을 목록 `!=` 로 비교한다(`run.py` parse ~:252,
  summarize ~:1575, `_axis_mismatch` ~:1705). 보조 모델이 회차마다 나타나면 회귀 없이 게이트 red. 기준선 2026-09-26 은
  에이전트당 모델 1개였다 `[관측 n=1]`
- C-ATK-002 [M]: `_axis_mismatch` 가 `None` 만 "모름"으로 본다 — `[]` 는 알림도 회귀도 없이 통과. 빈 축 기준선 저장도 막지 않는다
- C-ATK-003/005 [M/L]: 파서가 `is_error`/`subtype` 을 보지 않는다. 해석 실패는 품질 `fail` 로 기록된다(인프라 실패는 이 파일
  분류상 `error`)
- C-ATK-006 [L]: stdout 이 JSON 객체 하나가 아니면(배열·잡음 줄) 전량 거짓 red
- C-ATK-008 [L]: `test_error_results_carry_empty_resolved_models` 가 조기 반환 경로만 탄다(timeout·exit≠0·해석실패 미실행)
- 개행 민감 앵커 어서션 0건, 부정형 어서션만인 시나리오 0건 `[confirmed, 컨트롤]` — `result` 개행 차이는 무해

## ② 범위

IN:
1. 기록/비교 분리: 결과·summary 에 전체 `resolved_models` 는 **기록**으로 유지하되, compare 축은 **주 모델**
   (`primary_models`) — 별칭 패밀리 매치(`opus` ⊂ `claude-opus-5-5`), 없으면 outputTokens 최대 1개. `MEASUREMENT_AXES`
   의 비교 대상은 `primary_models`. 전체 목록 차이는 stderr 알림(비회귀)
2. 축 "모름" = `None` 과 `[]` 동일 취급(한쪽이라도 비면 알림, 회귀 아님). `--baseline` 저장 시 비교 축이 빈 에이전트가
   있으면 **저장 거부**(exit 1, 사유)
3. 파서: `is_error is True` 또는 `subtype != "success"` → 해석 실패로 올린다. 해석 실패 상태는 `error`(분류 규약 따름),
   detail 에 subtype·is_error
4. 출력 형태 관용: 최상위가 리스트면 마지막 `type=="result"` 원소, 아니면 마지막 비지 않은 줄을 재시도 — 둘 다 실패 시 fail-closed
5. 테스트: 위 각각 + timeout·exit 1 주입 경로에서 `resolved_models == []`, 정상 경로에서 "사용량 없음" 알림이 **안** 뜸.
   전부 되돌려-FAIL 인용
6. 게이트: `python3 -m pytest -q evals/tests` · `ruff check .` · `./scripts/run-evals.sh --validate` · `--dry-run` ·
   `./scripts/verify-done.sh > /tmp/vd-r1.out 2>&1; echo $?`
7. 커밋 1~2개

OUT: 기준선 재생성(컨트롤), `evals/policy.json`, 그 외 파일

## ③ 금지

push · main/plan-control 쓰기 · bare stash/reset --hard/clean -fd · `run-evals.sh` 는 `--validate`/`--dry-run` 만 ·
`claude -p` 호출 금지 · 게이트 rc 를 파이프에 물리지 말 것

## ④ 보고

`[R1 evals] 완료 — <테스트 N개>, 커밋 <sha>, 테스트 <n passed>` + 되돌려-FAIL 인용 + 병합 측 후속. `worker_done` 으로.
