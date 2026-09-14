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
읽는 시점엔 이미 실행된 뒤라 게이트가 아니라 로그다. **rc 를 잃는 둘**(실측): 판정이
stdout 에만 있다(`gh pr view` — CI 가 빨개도 exit 0) · 파이프가 삼킨다(`gate | tail` 의
rc 는 `tail` 것이다). 둘 다 `&&` 를 통과시킨다 — `pipefail`. 상세: control-loop.

## DoD 체크리스트

**기계 검사 목록은 게이트가 소유한다** — 열거하면 검사를 더할 때마다 낡는다(실제로 그랬다).
수동 attest: 스펙 전항목 · 적대적 리뷰 · Work 상태 · CHANGELOG/README/CLAUDE 반영.
위임했다면 산출물 보존·자원 처리도 확인한다(`control-loop`). 완료 = 게이트 green + attest + Work 해소.

## Task 마감 규율

<!-- 앵커: #task-마감-규율 -->

**응답 직전 호스트의 태스크 목록을 조회해 끝난 항목을 completed로 정리한 뒤 보고한다.**
진행·대기 항목은 남기고 사유를 명시한다. 마지막 보고 태스크도 먼저 마킹한다 — 보고 후
마킹은 유실된다(반복 실측). ad-hoc에도 동일하며 completed 위장은 금지한다.
