# 브리프 M2 — eval-model-axis (W-045)

- **부모**: plan-control 컨트롤 세션 (Orca Run — 디스패치 spec 에 Run id)
- **역할**: eval 측정 축에 **실제로 돈 모델 ID** 를 싣는다 — 별칭 축(`models`)은 유지하고 옆에 추가
- **워크트리**: Orca new-child. 자기 브랜치에만 커밋
- **기준 커밋**: 디스패치 spec 의 해시 — 착수 시 대조, 다르면 에스컬레이션
- 먼저 `child-session` 스킬을 로드한다. 배경: `docs/specs/2026-09-27-model-provenance/README.md`

## ① 전제 — 구현 전에 검증한다

1. `evals/run.py` `ClaudeCodeHarness.run_scenario_cmd` 는 `--output-format text` 로 시나리오를 돌리고(:206), 어서션은
   그 stdout 텍스트를 본다(`output_regex`·`output_contains_any`·`output_not_contains` 등, :949~) `[confirmed]`
2. 측정 축: 결과 레코드 `model`·`effort`, summary `models`·`efforts`, `compare_baseline` 은 `MEASUREMENT_AXES` 루프 +
   `_axis_mismatch`(축 부재 = stderr 알림, 불일치 = 회귀) `[confirmed — v3.39.0 T4]`. 기준선 `evals/baseline/2026-09-24.json`
   의 `models` 는 `['haiku','opus','sonnet']` 별칭뿐 `[confirmed]`
3. `claude -p … --output-format json` 결과 JSON 에 `result`(최종 텍스트)와 `modelUsage`(키 = 실제 모델 ID) 가 있다
   `[confirmed 2026-09-24, haiku 1회 — judge 실측 때]`. **착수 시 `--dry-run` 이 아니라 실제 JSON 형태를 기존 리포트나
   CLI 문서로 재확인할 방법이 없으면 `[소스 기준]` 으로 두고, 테스트 픽스처는 그 형태로 쓴다** — 모델 호출 금지(③)
4. `modelUsage` 는 서브에이전트·툴용 보조 모델(예: haiku)이 섞여 키가 여럿일 수 있다 `[미확인]` — 축에는 **전부**를
   정렬해 싣고, 주 모델 판정은 하지 않는다

## ② 범위

**IN**
1. 시나리오 실행을 `--output-format json` 으로 바꾸고, 어서션에는 기존과 **같은 텍스트**(`result`)를 넘긴다 — 어서션
   의미가 바뀌지 않아야 한다. JSON 파싱 실패·`result` 부재는 **fail-closed**(그 시나리오 fail, 사유 명시)
2. 결과 레코드에 `resolved_models`(정렬된 `modelUsage` 키 목록, 없으면 `[]`), summary 에 `resolved_models`(고유 정렬),
   `MEASUREMENT_AXES` 에 한 줄 추가 — 규칙은 model·effort 와 동일(기준선에 없으면 알림, 다르면 회귀)
3. 테스트: (a) json stdout → 어서션이 `result` 텍스트로 판정 (b) `resolved_models` 기록 (c) 축 불일치 = 회귀 문구
   (d) 기준선 축 부재 = 알림·비회귀 (e) 깨진 JSON = fail-closed. 각 테스트 **되돌려-FAIL 인용**
4. `evals/README.md` 에 측정 축 설명이 있으면 한 줄 추가(없으면 건너뜀)
5. 게이트: `python3 -m pytest -q evals/tests` rc 0 · `ruff check .` rc 0 · `./scripts/run-evals.sh --validate` rc 0 ·
   `./scripts/run-evals.sh --dry-run` 으로 커맨드에 `--output-format json` 이 실리는지 인용 ·
   `./scripts/verify-done.sh > /tmp/vd-m2.out 2>&1; echo $?` → 0
6. 커밋 1개(자기 브랜치)

**OUT**: 기준선 재생성(컨트롤이 병합 후 API 비용으로), `evals/policy.json`, 에이전트 정의, `evals/run.py` 밖의 러너
동작 변경, judge 경로(이미 json), 그 외 전 파일

## ③ 금지 — 명령 수준

- `git push` 금지 · `main`/`This-HW/plan-control` 체크아웃·커밋 금지 · bare `stash`/`reset --hard`/`clean -fd` 금지
- `scripts/run-evals.sh` 는 `--validate`/`--dry-run` 만 — 인자 없이·`--agent`·`--compare`·`--baseline` 금지(API 비용)
- `claude -p` 직접 호출 금지
- 기존 어서션 타입의 판정 의미를 바꾸지 말 것 — 입력 텍스트만 `result` 로 바뀐다
- 게이트 rc 를 파이프에 물리지 말 것

## ④ 보고

- 첫 줄: `[M2 eval-model-axis] 완료 — <테스트 N개 추가>, 커밋 <sha>, 테스트 <n passed>`
- 본문: 명령·rc(`--dry-run` 인용) · 되돌려-FAIL 인용 · 전제 3·4 등급 갱신 · **병합 측 후속 조치**(기준선 재생성 필요 여부 등) · 사실 등급
- **전달**: Orca `worker_done` 경로로 컨트롤 Run 에. 막히면 막힌 지점만 먼저
