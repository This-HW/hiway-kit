---
title: "Archify 도식 업그레이드 — controller 검수"
status: current
as_of: 2026-11-25
---

# Archify 도식 업그레이드 — controller 검수

결론: 커밋 `4858c14` 를 main 에 반영한다.

- 도식 11장: 정본 `candidate.json` 과 정적 SVG
- 검사 `scripts/check_archify_diagrams.py` (`verify-done.sh` §32 와 CI 가 함께 쓴다)

검수 대상은 워커(Codex) 보고서 [`report.md`](report.md) 와 브랜치 `This-HW/archify-diagrams` 다. 검수는 두 갈래로 했다.

- **1차 검수**(커밋 `2459261`): 도식을 직접 렌더해 봤고, 독립 리뷰 에이전트가 게이트를 적대적으로 봤다. 결과는 CONDITIONAL, HIGH 1·MEDIUM 1·LOW 4 였다
- **2차 검수**(커밋 `4858c14`): 1차 지적이 반영됐는지 controller 가 직접 실행해 확인했다

## 1차 검수에서 바꾼 결정

| 항목 | 1차 산출물 | 결정 | 근거 |
| --- | --- | --- | --- |
| 인터랙티브 HTML | 12개 커밋(10.8MB) | 추적하지 않는다(`.gitignore`) | 도식마다 같은 뷰어 런타임(약 0.9MB)이 들어 있다. 직접 마켓플레이스 설치는 레포 전체를 받는다. GitHub 는 HTML 을 렌더하지 않는다 |
| README "What to type first" | 세로로 긴 SVG | 원래 `skills` 펜스로 복원 | 빠른 참조 카드는 텍스트여야 검색·복사가 되고, 기존 도식 블록 검사도 그대로 받는다 |
| 브랜치 히스토리 | HTML 포함 | 다시 만들었다 | `git rev-list --objects origin/main..4858c14` 에 `.html` 이 0개다 |

## 게이트 리뷰 지적과 처리

| 등급 | 지적 | 처리(`4858c14`) |
| --- | --- | --- |
| H | 매니페스트를 다시 만들면 정본만 고치고 렌더하지 않아도 green 이 된다. SVG 글자는 어떤 규칙도 보지 않는다 | SVG 를 파싱해 `<text>`·`<title>`·`data-node-*`·`data-edge-*` 에 스킬·개수 규칙을 적용한다. 노드·엣지 메타데이터를 정본과 대조한다 |
| M | `sources[].path`·줄 범위를 검사하지 않는다 | 추적 파일이어야 하고 줄 범위가 파일 안이어야 한다. 경로를 봉쇄한다 |
| L | 검사할 필드를 나열하는 방식이다 | 제외 방식(`STRUCTURE_KEYS`)으로 바꿨다. 나머지 문자열은 전부 보이는 텍스트로 본다 |
| L | 예상 밖 파일·중첩 디렉토리를 건너뛴다 | 예상 밖 추적 파일은 fail 이다. 도식 루트 밖 SVG 를 문서에 싣는 것도 fail 이다 |
| L | `check_doc_refs.py` 독스트링이 낡았다 | 고쳤다. README `skills` 펜스가 돌아와 도식 블록 검사 대상이 다시 생겼다 |
| L | 실행 조건 주석이 없다 | §32 와 CI 단계에 주석을 달았다 |

## controller 실측

scratch 워크트리(`4858c14`, detached)에서 한 번에 하나씩 바꾸고, 매니페스트를 매번 다시 만든 뒤 `python3 scripts/check_archify_diagrams.py` 를 돌렸다:

| 변조 | rc | 첫 위반 줄 요지 |
| --- | --- | --- |
| 없음(기준) | 0 | — |
| 정본 노드 라벨만 변경 | 1 | `task-size.svg: 노드 메타데이터 불일치` |
| SVG `<text>` 에 `/no-such-skill` | 1 | `[도식 스킬] /no-such-skill` |
| SVG `<text>` 에 `15 skills` | 1 | `[도식 수치] 15 skills` |
| 정본 근거 줄을 99999 로 | 1 | `줄 범위 99999-99999가 파일 범위 밖이다` |
| 도식 디렉토리에 추적 파일 추가 | 1 | `예상 밖 추적 파일` |
| 원복 | 0 | — |

이어서 워커 워크트리에서 확인한 것:

- 고정 ruff venv 로 `verify-done.sh` 를 돌렸다 → `42 pass / 0 fail`(pytest 3459 passed, §32 포함)
- `git diff --quiet origin/main -- plugins/common` → rc 0
- `.claude/rules/archify.md` 는 무시되고, `.claude/skills/archify` 링크도 미추적이다(`git status --porcelain .claude` 0줄)

도식은 Chrome 헤드리스로 SVG 다섯 장을 렌더해 직접 봤다(plan-build-verify·task-size·skill-selector·harness-loop·mcp-routing). 레이아웃·한글 렌더링·화살표 경로에 결함은 없었다. `skill-selector` 는 위 결정에 따라 뺐다.

## 남은 것

- **Code Analysis**: 발견(순환 1건 `code_intel.py`↔`code_intel_rules.py`, 큰 파일)은 보고서에만 있다
  - 고치는 일은 `plugins/common` 변경이라 디렉토리 심사가 끝난 뒤 다룬다
- **SVG 가독성**: README 도식의 sublabel 은 원본 크기에서 작다. 내용은 본문의 텍스트 요약이 함께 전한다
- **재생성 절차**: [`docs/architecture/diagrams/README.md`](../../architecture/diagrams/README.md) 에 있다
  - Archify 가 이 레포 전용으로 설치돼 있어야 다시 만들 수 있다
  - CI 는 Node 없이 정본·SVG 일치만 판정한다
