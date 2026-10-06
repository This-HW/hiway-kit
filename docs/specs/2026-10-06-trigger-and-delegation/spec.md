---
title: "스킬 발동률(debug) 교정 + 위임 승인 문단 재실측"
created: 2026-10-06
size: medium
status: historical
as_of: 2026-10-06
---

# 스킬 발동률 교정 + 위임 승인 문단 재실측 (5.4.1)

5.4.0 후속 후보 중 두 건을 실측으로 판정했다. 숫자는 전부 이 세션의 실행 결과다
(claude 2.1.291, 플러그인 작업 트리 또는 설치본 5.4.0).

## 1. debug 스킬 발동률

**문제 제기(5.4.0 W5 파일럿)**: debug 3/6 · plan-task 2/6 으로 낮다.

**재측정 기준선**(`claude plugin eval`, sonnet 5.5, 6회, `--ablation none`): brainstorming 6/6 ·
review 6/6 · **plan-task 5/6** · **debug 2/6** · 음성(Small 버그) 6/6 무발동. plan-task 는 W5 의 2/6 이
표본 변동이었다 — 이번 두 측정 합 10/12. 고칠 근거가 없어 설명문을 바꾸지 않았다.

**debug 원인은 케이스였다.** 프롬프트가 메시지에 원인이 보이는 `KeyError: 'DEBUG'` 였다. debug 는 opus
서브에이전트를 쓰는 4단계 파이프라인이고 킷 규약은 "Small 은 바로 고친다"이므로 여기서 안 뜨는 것이 맞다.
케이스를 둘로 나눴다 — 원인이 안 보이는 간헐 실패(`debug-fires`, 양성)와 원인이 보이는 오류
(`debug-obvious-no-skill`, 음성).

| 설명문 | 간헐 실패 → debug 발동 | 명백한 오류 → debug 미발동 |
| --- | --- | --- |
| 이전 "Analyze errors and apply fixes. Use when you have an error message, traceback, or failing log…" (sonnet, 6회) | 1/6 | 4/6 (2회 과발동) |
| 새 "Investigate a failure whose cause is not evident from the error itself … Skip it when the message already shows the fix" (sonnet, 6회) | **6/6** | **6/6** |
| 새 설명문 (opus 5.5, 4회) | 4/4 | 4/4 |

새 설명문으로 발동 케이스 6종 전체 재측정(sonnet, 6회): 전 케이스 5/6 이상, 음성 2종 6/6 — 다른 스킬 후퇴 없음.
두 판정 모두 응답 품질(llm 그레이더)은 6/6 — 바뀐 것은 **어느 경로로 푸는가**다.

## 2. 위임 승인 문단이 주입되지 않는 구조

**문제 제기(5.4.0 W2)**: `agent-delegation-chain` 은 `tier: reference` 라 승인 문단 본문이 세션에 들어가지
않는다. 2026-08-21 A/B(Sonnet 5, n=3+3)는 문단이 없으면 위임 0/3, 있으면 3/3 이었다.

**재실측**: 임시 git 레포(파일 3개)에서 *"cancel_order 를 구현하고 테스트를 단 뒤 병합 전에 버그 리뷰를
받아 달라"* — 이 세션이 쓴 코드의 리뷰라 규칙상 위임 조건(작성자와 분리된 리뷰)이 성립한다. 대조군은 설치된
5.4.0 그대로(인덱스 줄만 주입), 처치군은 `--append-system-prompt` 로 승인 문단을 추가. `claude -p`,
`--permission-mode bypassPermissions`, 메인 루프의 `Agent` 호출을 센다.

| 모델 | 대조군(문단 없음) | 처치군(문단 주입) |
| --- | --- | --- |
| Opus 5.5 | 6/6 → `review-code` | 6/6 → `review-code` |
| Sonnet 5.5 | 6/6 → `review-code` | 6/6 → `review-code` |

어느 실행도 규칙 파일을 열지 않았다 — 위임은 문단 없이 에이전트 `description` 만으로 일어났다. 반대 방향
스모크(위임 조건이 약한 32줄 diff 리뷰, 각 1회)는 두 조건 모두 인라인으로 처리했다 `[관측 n=1]`.

**판정**: 2026-08-21 의 억제는 현 버전에서 재현되지 않는다. `tier: reference` 유지 — 상시 주입 예산을 쓸
근거가 없다. 원인(모델·CLI·에이전트 설명문 개선 중 무엇이 바뀌었는가)은 가르지 않았다 — 이 측정이 가르는
것은 "지금 문단이 필요한가"뿐이다.

## 3. 같이 고친 것

에이전트 frontmatter 검사가 `plugins/**/*.md` 에서 `skills/`·`rules/` 만 빼서 대상을 잡아, frontmatter 가
있는 비-에이전트 문서를 에이전트로 보고 frontmatter 없는 에이전트는 건너뛰었다 —
`scripts/check_agent_frontmatter.py` 로 단일화, 대상은 `plugins/*/agents/*.md` 에서 파생.
