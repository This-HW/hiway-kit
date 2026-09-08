---
tier: core
portable: true
---

# Definition of Done — 완료 게이트 (Spec 6 / W-010)

"완료/끝/통과"는 **판단이 아니라 명령의 출력**이다 — 완료 주장 전: 검증 명령을 fresh
run(`scripts/verify-done.sh`; 스크립트 없음은 면제 사유가 아니다) → 출력 전부 읽기 →
FAIL 있으면 "완료" 대신 실제 상태를 증거와 함께 보고 → 수동 DoD 항목 명시적 attest.
**명령을 실행하지 않고 완료를 주장하는 것은 오류다.** 검증 전엔 "완료/done/통과" 대신
"구현 + self-validation 완료, 미결: [...]"로 말한다.

**검증과 상태 변경(push·merge·release·deploy)을 한 도구 호출에 잇지 마라** — 출력을
읽는 시점엔 이미 실행된 뒤라 게이트가 아니라 로그다(실측 n=2). 판정이 stdout 에 있는
검증(`gh pr view` — CI 가 빨개도 exit 0)은 `&&` 로도 게이트가 안 된다. 상세: control-loop.

## DoD 체크리스트

**기계 검사 목록은 게이트가 소유한다** — 열거하면 검사를 더할 때마다 낡는다(실제로 그랬다).
수동 attest(기계 불가): 스펙 전 항목 구현 · 적대적 리뷰 1회 · Work 상태 정확 보고 ·
CHANGELOG·README·CLAUDE.md 반영. 완료 = 게이트 green + attest + Work 해소.

## Task 마감 규율

<!-- 앵커: #task-마감-규율 -->

**턴을 끝내기 직전 `TaskList`를 조회해 "끝났는데 마킹만 안 된" 태스크를 completed로
정리한다 — 마킹이 보고보다 먼저다. 진행 중/대기 태스크는 마킹하지 않는다(잔존 사유
명시).** 마지막 태스크=보고/마무리라 마킹을 뒤에 두면 완료 처리가 증발한다(실측된
반복 버그) — ad-hoc 태스크에도 적용. completed 위장 금지(false-green 금지).
