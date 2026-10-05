---
status: historical
as_of: 2026-09-30
---

# v5.2.0 — 스킬이 부르는 도구를 `hooks/` 에서 `tools/` 로 분리

**상태**: 완료(v5.2.0 릴리스, 2026-09-30 OpenAI 자동 검사 통과·검토 제출) · **결정자**: 컨트롤(plan-control) · 사용자 지시(2026-09-28): OpenAI 공개까지 능동 완주

## 왜

OpenAI 플러그인 디렉토리 업로드가 메타데이터 검사 *"Plugins containing hooks cannot be submitted"* 로 막힌다.
실측(2026-09-30, 조사용 ZIP 2개를 초안 수정본으로 업로드): 훅 선언(`hooks/hooks.json`·`hooks-codex.json`·매니페스트
`hooks` 필드)을 빼도 막히고, **`hooks/` 디렉토리를 통째로 빼면** "No issues found". `setup/`(git 훅)은 무관.
즉 포털은 `hooks/` **디렉토리의 존재**를 훅으로 본다.

그런데 `hooks/` 에는 진짜 훅 외에 **스킬이 직접 부르는 도구**가 섞여 있다 — `checklist.py`(계획 체크리스트),
`feedback_ledger.py`(교훈 원장), `export_harness.py`(AGENTS.md 내보내기). 이것들을 빼면 디렉토리로 설치한
사용자에게서 스킬이 깨진다. 도구가 `hooks/` 에 있는 것은 역사적 우연이다.

## 판정

- 세 도구를 `plugins/common/tools/` 로 **이동**한다(git mv). `hooks/` 에는 진짜 훅(`session-start`·`auto-format`·
  `stop-validator`·`protect-sensitive`, 그 공용 `utils.py`, 선언 json, `examples/`)만 남긴다.
- 훅이 도구를 import 하는 곳(`session-start.py` → `feedback_ledger`)은 플러그인 루트 기준 `tools/` 를 경로에 넣어
  import 한다(`__file__` 기반 — cwd·캐시 위치 무관, 기존 D-012 관례).
- 모든 참조를 새 경로로: 스킬(plan-task references·auto-dev·skill-forge·harness-export 등)의 `hooks/<tool>.py` 와
  캐시 탐색 fallback 글롭(`~/.claude/plugins/cache/*/*/*/hooks/<tool>.py`), 규칙(`feedback-loop` 등), 레포
  `.claude/skills/*`, `scripts/*.sh` 래퍼·`scripts/build-targets.py`·`scripts/verify-done.sh`, 테스트, 문서
  (CLAUDE.md Hooks 절·docs/conventions 등 **현행 서술**만 — docs/specs·CHANGELOG 등 과거 기록은 두지 않는다).
- `session-start.py` 의 주입 본문 경로 렌더(A5, `skills/`·`rules/`·`hooks/`)에 `tools/` 접두사를 추가한다.
- `scripts/build-codex-zip.py`: 디렉토리 제출본에서 `hooks/` **전체**를 뺀다(지금의 선언 두 파일 제외 규칙을 대체).
  검증기는 `hooks/` 아래 항목이 하나라도 있으면 오류. `tools/` 는 반드시 포함되는지 실물 ZIP 테스트로 고정.
- Codex 로컬 설치(마켓플레이스)의 훅 선언 경로(`hooks/hooks-codex.json`)는 그대로 — 훅은 계속 `hooks/` 에 있다.
- 되돌리면 실패하는 테스트: (1) 실물 ZIP 에 `hooks/` 없음 + `tools/checklist.py` 등 있음 (2) 검증기가 `hooks/` 항목을 오류로
  (3) session-start 가 `tools/` 에서 feedback_ledger 를 찾아 LESSONS 를 낸다(플러그인 픽스처 서브프로세스).

## 완료 조건

`scripts/verify-done.sh` green, 전체 pytest green, `python3 scripts/build-codex-zip.py --check` rc=0,
`git grep -n -E 'hooks/(checklist|feedback_ledger|export_harness)\.py'` 이 현행 파일(plugins/·scripts/·tests/·.claude/·CLAUDE.md·README·docs/conventions)에서 0건,
격리 CODEX_HOME 설치 확인은 컨트롤이 한다.
