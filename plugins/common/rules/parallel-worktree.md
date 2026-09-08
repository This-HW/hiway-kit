---
tier: conditional
activates: 워크트리 여부 감지 (.git 파일 == linked worktree)
portable: false
---

# Parallel Worktree Rules

병렬 dispatch에서 파일을 수정하는 에이전트는 worktree로 "격리 진입"하고, 검증
통과 후에만 "복귀(병합)"한다. 격리는 필요조건일 뿐이다 — 병합 규범이 없으면
충돌은 사라지는 게 아니라 병합 시점으로 이연된다. (W-011)

## 진입 (Isolation)

- ALWAYS: 소스 파일을 수정하는 에이전트는 frontmatter `isolation: worktree` + tools에 `ExitWorktree`.
  대상: implement-code, fix-bugs, write-tests, write-api-tests, implement-api, generate-boilerplate, sync-docs, optimize-logic
- NEVER: read-only 에이전트(explore-codebase, review-code, plan-implementation 등)에 isolation 설정.
- git-workflow는 의도적으로 비격리 — 병합·충돌 해결은 메인 워크스페이스에서 일어나야 한다.

## 파일 소유권 = 병렬 안전의 전제조건 (dispatch 전)

병렬 안전은 **병합 시점의 직렬화가 아니라 dispatch 시점의 파일 분리**로 확보한다.
메인 세션은 서브에이전트가 각자 호출하는 ExitWorktree의 타이밍을 직렬화할 수단이
없다 — 따라서 "순차 병합"은 강제 불가능한 규범이다. 대신 병렬 청크의 수정 대상
파일을 disjoint하게 만들면, 각 worktree가 언제 복귀하든 트리 수준 충돌이 원천적으로
없다(git은 index 연산을 내부적으로 직렬화한다).

- ALWAYS: 병렬 dispatch 전에 청크 간 수정 대상 파일이 겹치지 않는지(disjoint) 확인.
- 겹침을 피할 수 없으면 → 해당 청크들을 **순차 dispatch**로 강등한다(메인이 하나
  dispatch → 완료(ExitWorktree까지) 확인 → 다음). 이때 의존성 상류(공유 타입/유틸)
  청크를 먼저 dispatch한다. "순차 병합"이 아니라 "순차 dispatch"가 메인이 실제로
  통제하는 레버다.
- 공유 파일(설정, 배럴 export, 라우트 등록부 등)은 병렬 청크에 배정하지 않고 마지막에
  메인 세션이 단독 수정한다.

## 복귀 (ExitWorktree) — 에이전트 자신이 수행

- ALWAYS: 파일 수정 에이전트는 worktree 안 검증(린트 + 관련 테스트)이 그린일 때만
  스스로 `ExitWorktree`를 호출해 복귀한다. 레드 상태로 병합 금지.
- disjoint 파일 전제가 지켜지면 병렬 에이전트들의 ExitWorktree가 동시에 일어나도
  내용 충돌은 없다. 전제가 깨질 위험이 있으면 위의 순차 dispatch로 강등한다.
- 메인 세션은 서브에이전트 tool 호출을 직렬화하지 못하므로 "메인이 순차 병합" 규범은
  두지 않는다 — 직렬화가 필요하면 dispatch 단계에서 처리한다.

## 충돌 에스컬레이션

- NEVER: 충돌 시 에이전트가 임의로 ours/theirs 선택. 반드시 `DELEGATE_TO: git-workflow`로 위임 —
  git-workflow가 충돌 파일/내용을 보고하고 NEED_USER_INPUT(ours/theirs/manual)으로 사용자에게 선택지를 제시한다.
- 같은 지점에서 충돌 2회 반복 = 청크 분해 오류 신호 → plan-implementation으로 에스컬레이션.

## 공유 상태 파일

- NEVER: worktree 안에서 `docs/works/**`(progress.md, feedback ledger 등) 갱신 —
  병합 전까지 메인 저장소에 반영되지 않아 상태가 유실/분기된다. Work 상태 갱신은 메인 세션(오케스트레이터)의 몫.
