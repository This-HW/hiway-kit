---
tier: conditional
activates: 활성 계획 존재
portable: false
---

# Task Resume Rules

## 트리거 조건

이 파일이 주입되었다 = `docs/plans/*/plan.md` 중 `status`가 `done`이 아닌 활성 계획이 있다.

- 사용자가 재개를 명시하면 → 재개 절차 즉시 실행
- 단순 질문/조회면 → "<계획> 이 진행 중입니다. 재개할까요?" 안내 후 대기
- NEVER 자동으로 코드를 수정한다

## 재개 절차

1. **plan.md 원문을 다시 읽는다** — 요약본이 아니라 파일 그대로 (loop-engineering 재앵커).
   `checklist.json`이 있으면 함께 읽는다.
2. `checklist.json`의 미완 항목(`passes: false`)부터 순서대로 진행한다. `passes: true`
   항목은 건너뛴다. `checklist.json`이 없으면 `## 완료 조건`(plan.md)의 항목을 같은
   방식으로 취급한다.
3. 호스트 태스크 도구가 있으면 미완 항목으로 태스크를 만들 수 있다 — 단 영속 상태는
   `checklist.json`(또는 plan.md)이다. 태스크는 세션 종료 시 사라지므로 재개할 때마다
   여기서 다시 파생한다.
4. 2개 이상 → 수정 파일이 겹치지 않을 때만 병렬 위임, 겹치면 순차 (parallel-worktree)
