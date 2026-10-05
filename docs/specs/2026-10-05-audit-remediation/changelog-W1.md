---
status: historical
as_of: 2026-10-05
---

# CHANGELOG 조각 — W1 docs (5.4.0 조립용)

발견 ID 는 `audit/{A-harness,B-docs,C-research,D-coldread}.md` 를 가리킨다.

### Changed — 문서 지위가 frontmatter 로 선언된다

- `docs/**/*.md` 전부(룰 미러 제외 — W2)에 `status: current|historical|proposal|superseded`·`as_of` 를 단다. 시점 고정 조사·완료 스펙은 `historical`, 대체된 스펙은 `superseded` + `superseded_by`. 시점 고정 문서 머리에는 배너를, 바뀐 사실에는 «정정»을 인라인했다 (B 총평 A·B-P1-31·P2-13·P3-6, A-P2-1)
- `docs/research/README.md`·`docs/specs/README.md` 색인 신설, `docs/conventions/README.md` 색인을 전부 채움 — 무엇을 `CLAUDE.md` 가 import 하는지 정정 (B-P1-18, B (c))
- `docs/pipeline-reinforcement-plan-v2.md` 삭제 — 폐기된 마커 레시피와 구버전 Stop 훅 스케치가 현재형 명세로 남아 있었다. 판정은 `docs/architecture/delegation-signal-retirement.md` 가 소유 (B-P0-6)

### Changed — `CLAUDE.md` 를 줄이면서 고쳤다 (프로젝트 지침 CLAUDE.md + @import 42,971B → 38,603B, `check_injection_budget.py` 측정)

- 릴리스 절을 `docs/conventions/release-process.md` 포인터로 — 버전은 `scripts/bump-version.sh` 로만 올린다(수동 편집 예시 삭제). release-process 에 `AGENTS.md` 재생성·행동 eval·태그 경위를 모아 정본화 (B-P1-1, D-4, D-5, B-P2-12)
- CI 단계·드리프트 게이트 열거 삭제 — `validate.yml`·`verify-done.sh` 가 소유 (B-P1-15, B-P1-16)
- maxTurns 는 각 에이전트 frontmatter 가 소유, Phase 1 은 "P0 ambiguity = 0", Phase 3 에 spec compliance 선행 (B-P1-13, B-P1-14, B-P3-3)
- 플러그인 캐시 경로를 `<marketplace>/hiway-kit/<version>[-<sha>]` 로 일반화 (B-P1-2)
- `/agent-creator` 는 소비자 프로젝트 에이전트용이라고 명시, 킷 에이전트 추가 절차에 로스터·eval tier·시나리오 의무 추가 (D-1, D-3)
- leaf 에이전트 중첩 금지는 네이티브 기본(3단계)과 다른 의도적 선택임을 명시, 워크플로 opt-in 서술을 현행으로 (C-F10, C-F4)
- frontmatter 템플릿에 `ExitWorktree`, 오케스트레이션 표 단위를 "병렬 청크 수" 로 (B-P2-8). 첫 줄에 지원 범위(D-7), Full Mode 는 직접 마켓플레이스를 설치한다고 명시(B-P0-1). 풀리지 않는 작업 ID 제거 (B-P3-4)

### Changed — 배포 상태의 정본은 하나

- `docs/marketplace-submission.md` 상단에 채널별 상태 요약표(채널 / 상태 / 확인일 / 다음 행동) 신설. 아래 절은 `(역사)`·`(기록)` 으로 접고, 머리 Note·개명 절의 모순, 전임 킷 pin(v2.12.3) vs 최종본(v2.21.0) 서술을 통일 (B-P1-3, B-P1-4)
- listing 키에 대한 "validate 가 경고하고 제거" 근거를 낡음으로 정정 — Claude Code 2.1.281+ 는 경고하지 않는다 (C-F6)
- `docs/codex-submission-checklist.md` 는 절차·기록만. 제출 전 단계·트래커 서술을 역사로, `§14` 를 `verify-done.sh` 것으로 명시 (B-P1-5)

### Changed — README 의 하네스 서술을 실측에 맞췄다

- Codex 자동 차단: 0.153.4 에선 막히지 않았고 **0.159.3 에선 막힌다**(2026-10-05 감사 A 실측, 기록 `packaging/targets.json`). `protect-sensitive` 이식은 별도 결정 (A-P0-2)
- Codex 마켓플레이스 설치 vs OpenAI 디렉토리 ZIP 비교표 — ZIP 은 훅이 없어 `/harness-export` 가 필요 (A-P1-1)
- Antigravity 에이전트 미인식의 원인은 레이아웃이 아니라 `model:` frontmatter, `agy plugin validate` 는 개수만 센다 (A-P1-3, B-P1-9)
- Gemini CLI 절 신설 — `GEMINI.md` 만 제공, 런타임 미측정, 정식 타겟 아님 (A-P1-7). `~/.agents/skills` 공용 경로 안내와 네임스페이스·중복 로드 경고 (A #9)
- 이력 서사(3.34.x 릴리스 노트) 삭제, OpenAI 상태는 요약표 포인터, Feature Development 체인·Multi-perspective 흐름을 스킬 링크로 축소, Project Structure 에 `tools/`·`setup/`, 기여 체크리스트의 "plugin.json 등록" 을 메타데이터 확인으로 (B-P1-7, B-P1-8, B-P1-29, D-6, B-P3-2)
- `plugins/common/README.md`: 두 설치 경로, 평탄 `agents/` 역할 표, 차단 훅은 Claude Code 동작임을 명시 (B-P1-29, B-P2-11, D-9). `packaging/README.md`: 작업 ID 제거, 비활성 타겟 열거 삭제 (B-P2-11)

### Changed — 해설·규약 문서 정정

- `docs/architecture/phase-gate-pattern.md`: Stop 훅은 Phase Gate 를 판정하지 않는다(린트·수정 테스트 안전망), 출구 조건은 `rules/agent-system.md` 가 정본 — "80%+"·"통합 테스트" 삭제 (B-P0-5, B-P1-6, D-2)
- `docs/native-absorption.md`: 감사 C §8 반영 — `Agent Evals` → `adopt(pilot)`, SubagentStart·AGENTS.md 이중 도달 → `decide`, 서브에이전트 결과 헤더 → `absorbed(partial)`, 워크플로 배포는 `watch`(미채택), 신규 7행, 상태 3종 정의. `/agents` 마법사 제거·Task 도구 기본 비활성 정정, 에이전트 33→15·Codex 훅 현재 사실, 셀 파이프 이스케이프, 작업 ID → 스펙 경로, 검토 기록 최신순·4.0~5.3 항목 (C-F1, C-F2, C-F7, C-F8, B-P1-9, B-P2-1, B-P2-2)
- `docs/conventions/`: path-containment 헬퍼 이름 `_resolve_in_repo`·반복 횟수 네 번(B-P1-17), no-gate-integration 개수·열거 삭제(B-P1-16), reference-vs-judgment 깨진 `[Unreleased]` 링크(B-P2-4), warning-signal "여섯"·현존 예시(B-P2-6), rules-mirror tier 별 주입 서술(B-P2-7), measurement-traps 문장(B-P3-5)
- `docs/architecture/delegation-signal-retirement.md`: 검증 불가 "decision-log 47곳" 삭제, 작업 ID → 버전·스펙 경로 (B-P2-5, B-P3-4). `docs/control-loop-transport.md`: Work 잔재 (B-P1-30)
