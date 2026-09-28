# Task Resume — 계획 파일 기반 재개

> 규범 본문(정의)은 `plugins/common/rules/task-resume.md` 가 SSOT다. 이 문서는 그 규칙이
> 왜 이런 모양인지, 어떻게 적용되는지를 표·예시로 풀어 설명한다 — 여기서 새로 정의하지
> 않는다.

---

## 1. 왜 checklist가 authority이고 Task는 파생물인가

호스트 태스크 도구(Claude Code 네이티브 Task 등)는 **세션 스코프**다 — 세션이 끊기면
사라진다. Codex 처럼 영속 태스크가 아예 없는 하네스도 있다. 반대로
`docs/plans/<slug>/plan.md`와 `checklist.json`은 git 파일이라 세션 경계를 넘어 남는다.

```
세션 종료 전:
  checklist.json: [C-1 passes✅] [C-2 passes✅] [C-3 passes:false]

세션 재시작 후:
  호스트 태스크는 전부 사라짐
  → checklist.json 을 다시 읽고 C-3 부터 재개
```

그래서 "무엇이 끝났는가"의 **단일 authority**는 `checklist.json`(없으면 `plan.md`의
`## 완료 조건`)이고, 호스트 태스크는 재개할 때마다 거기서 다시 파생시키는 **캐시**일
뿐이다. 이 authority/파생물 구분이 규칙의 핵심이다.

## 2. 트리거 조건

| 상황 | 판정 |
| --- | --- |
| `docs/plans/*/plan.md` 중 `status`가 `done`이 아닌 것이 하나 이상 있음 | 이 룰이 주입된다 |
| 활성 계획이 하나도 없음 | 주입되지 않는다 |

정상 운영(진행 중인 계획이 없는 세션)에서는 두 번째 행이 참이므로, 이 트리거는
`warning-signal.md` §검토1이 요구하는 "상시 참이 아닌 조건"을 만족한다 — 항상 뜨는
안내는 소음이 되어 옆의 진짜 안내까지 죽이기 때문이다.

## 3. 재개 절차 예시

### 입력: `docs/plans/2026-09-20-auth-refactor/checklist.json`

```json
[
  { "id": "C-1", "description": "요구사항 분석", "passes": true },
  { "id": "C-2", "description": "인증 API 구현", "passes": true },
  { "id": "C-3", "description": "테스트 작성", "passes": false },
  { "id": "C-4", "description": "리뷰", "passes": false }
]
```

### 재개 시 진행

```
1. plan.md 원문을 다시 읽는다 — 요약 금지(loop-engineering 재앵커와 동일 원칙).
2. passes:false 부터 순서대로: C-3, C-4.
3. 호스트에 태스크 도구가 있으면 C-3·C-4 로 태스크를 만들 수 있다.
   이 태스크는 파생물 — 다음 재개 때는 checklist.json 을 다시 읽어 재생성한다.
4. C-3·C-4 가 수정하는 파일이 겹치면 순차, 겹치지 않으면 병렬 위임
   (판정 기준은 parallel-worktree 규범의 파일 소유권 절).
```

### `checklist.json`이 없는 경우

`plan.md`의 `## 완료 조건` 절 각 항목을 같은 방식으로 취급한다 — 실행 가능한 명령으로
적혀 있어야 하므로(`planning-protocol` 규범), 그 명령의 성공 여부가 사실상 `passes`
역할을 한다.

## 4. 단순 질문일 때

사용자가 재개를 명시하지 않고 단순히 묻기만 했다면(또는 다른 일을 요청했다면), 재개
절차를 실행하지 않고 **그 질문에 그냥 답한다.** 활성 계획은 필요하면 답 끝에 한 줄
언급까지만 한다.

v5.0.0 전에는 *"<계획>이 진행 중입니다. 재개할까요?"* 안내 후 **대기**했다. 활성 계획이
있는 레포에서는 이 규범이 매 세션 주입되므로, 그 규칙은 일상 질문마다 답 대신 확인
질문을 끼워 넣는 비용이 됐다. 재개 여부는 사용자가 말하면 된다 — 계획의 코드를 요청
없이 고치지 않는다는 금지만 남긴다.

## 5. 구버전(Work 시스템) 소비자

`docs/works/active/`에 디렉토리가 남아 있으면 session-start가 한 줄 안내만 낸다 —
과거처럼 progress.md를 읽어 Task ID를 매핑하는 재생성 알고리즘은 더 이상 없다.
이전 Work 시스템에서 계획 파일로 옮기는 방법은 CHANGELOG의 4.0.0 항목이 설명한다.
