# Durable Executor Checklist & Machine Gate 설계 (v2 — 적대적 리뷰 반영)

> v1(네이티브 Task 재사용 + 규율)은 3건 적대적 리뷰로 폐기. 근거: 네이티브 Task는
> `~/.claude/tasks/<session-UUID>/` **세션 스코프**라 durable checklist 불가 →
> test-gate 계약(acceptance/verify)이 다음 세션 executor에 도달 못 함. 규율-only 항목은 코드 필요.

**Goal:** 장기·다세션 실행에서 **완료 상태를 기계로 검증 가능하게** 만든다. kit은 루프 엔진을
재발명하지 않고(네이티브 위임), 네이티브가 없는 것 — durable 상태 파일 + 결정론 완료 게이트
+ 검증 계약 — 만 얇게 추가한다.

**Architecture:** 완료 상태의 단일 authority = Work당 `checklist.json`
(`{id, description, acceptance, verify, passes}`), plan-task가 `planning-results.md`(authority)
에서 파생. 네이티브 Task=세션 내 working queue, `progress.md`=서술 전용(상태 컬럼 제거) →
상태 표현이 하나로 축소. `verify-done.sh`가 `checklist.json`을 읽어 `passes:false` 잔존 시 FAIL.

## 정직한 범위 선언

- kit은 프로그래밍으로 fresh 세션을 못 띄운다(`/loop`·`ralph-loop`·ultracode는 사용자 트리거).
  "fresh-context-per-iteration 루프 엔진"은 **네이티브 위임**: 세션 내=Task당 fresh subagent(이미),
  크로스프로세스=사용자 `/loop`/`ralph-loop`. kit은 그 패턴의 **상태·게이트 레이어**만 제공.

## 요구사항

### R1. `checklist.json` — 완료 상태 단일 authority (신규 코드)
- 스키마: `[{ "id","description","acceptance","verify","passes":false }]`. `verify`=acceptance/E2E
  레벨 명령(raw exit-code proof; unit-test 경로 축소 금지). plan-task가 planning-results에서 파생.
- 위치 `docs/works/<W>/checklist.json`. 원자 쓰기(W-011 flock/rename 재사용). 헬퍼
  `work.sh checklist init|show|pass <id>`, `pass`는 verify 증거 없이 거부.

### R2. `verify-done.sh` 결정론 완료 게이트 (신규 코드)
- active Work checklist에 `passes:false` 잔존 시 FAIL. 부재 시 스킵(회귀 없음).

### R3. test-ratchet 기계 체크 (신규 코드)
- diff에서 test/assert 수가 allow-marker 없이 감소하면 감지/FAIL. 산문 아닌 코드.

### R4. 작은 인라인 규율 (신규 rule 파일 없음 — ssot.md 준수)
- `loop-engineering.md`: 기존 no-progress 가드에 "최근 N iter 새 커밋 0=idle 종료" 1줄 + 재앵커
  "요약 아닌 planning-results 원본 재독" 1줄.
- `auto-dev/SKILL.md`: executor는 미완 1항목/iter, verify 통과 전 passes 금지, checklist/progress
  쓰기는 메인 세션 소유(worktree subagent 금지 — parallel-worktree 충돌 해소).
- `review-code.md`: fresh-context·no-Write 분리는 충족 명시, cross-family judge는 **미충족 갭** 정직 표기.

### R5. 공통
- verify-done 변경 + checklist 헬퍼 테스트. plugin 2.8.0→2.9.0, CHANGELOG. 신규 rule 0 → count/CHECKSUMS 변동 0.

## 범위 외 / 분리
- **구 R6(stop-validator Bash 편집 .py 커버리지) → W-012 독립 patch로 분리**(durable-env 무관 + MUST-MATCH 해시 리스크).
- 신규 `durable-execution.md` rule 신설 취소(ssot 위반). 자동 cross-model judge, memory tool, init.sh 이식 — 후속.
- 크로스-클론 재개: checklist 커밋되는 사용자 프로젝트만 가능, kit 자체 Work는 gitignore(로컬 durable로 충분).

## 컴포넌트 구조
- 신규 코드: checklist 헬퍼(`scripts/`) + `verify-done.sh` 통합 + test-ratchet 체크 + 테스트.
- 인라인 문서: plan-task/auto-dev/loop-engineering/review-code(+definition-of-done 재확인).
- 릴리스: plugin.json 2.9.0, CHANGELOG.

## 데이터 흐름
```
plan-task: planning-results(authority) ─파생→ checklist.json (passes:false, acceptance, verify)
루프(네이티브 위임): 세션 내=Task당 fresh subagent / 크로스프로세스=사용자 /loop·ralph-loop
executor(각 iter): planning-results 원본 재앵커 → 미완 1항목 → 구현 → verify(raw exit-code)+review-code(분리)
   → 통과 시 checklist pass <id> + 커밋
verify-done: checklist 전항목 passes:true + 기존 기계검사 → 완료
```

## 에러 처리 / 리스크
- drift: checklist 단일 authority(planning-results 파생), progress 상태 미보유.
- 종이 게이트: verify-done가 checklist 직접 grep → 결정론.
- 무한 루프: `stop_hook_active` + idle(커밋 0) 신호.
- ratchet 우회: 기계 체크.
- 동시 쓰기: W-011 flock/rename.

## 테스트 전략
- checklist 헬퍼 단위 + 동시 쓰기 무손실. verify-done 미완 FAIL/부재 스킵. ratchet 삭제 감지.
- 완료 게이트: `verify-done.sh` 그린 + 기존 훅 테스트 그린.

## 발행 (필수 후속)
리서치 리포트 + 이 설계·적대적 리뷰 과정 + 구현 기록을 `site/content/posts/`에 블로그 게시(자동 배포). 별도 Task.
