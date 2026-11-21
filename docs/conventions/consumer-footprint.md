---
status: current
as_of: 2026-11-09
---

# 소비자 흔적 — 킷이 남의 프로젝트에 무엇을, 언제 만들거나 바꿀 수 있는가

이 킷은 **남의 프로젝트에 설치된다.** 킷이 그 프로젝트의 구조를 스스로 정하면(디렉토리를 만들고, 테스트
배치를 강요하고, 사용자 지침 파일을 고치고, 설치를 하고) 사용자는 그것을 *도움*이 아니라 *침범*으로 겪는다.
2026-11-09 외부 설치 검토와 독립 자문 2건(Claude Opus·Codex)이 같은 결론을 냈다 — 문제는 파일을 만든다는
사실보다 **요청 범위와 위치를 킷이 대신 결정한다**는 데 있다.

## 규칙

1. **자동 트리거는 작업 트리와 사용자 파일을 바꾸지 않는다.** 세션 이벤트(SessionStart·Stop·PreToolUse),
   설명만 보고 불리는 에이전트, 스킬의 자동 연쇄는 생성·개명·삭제를 하지 않고 "다음 단계 제안"까지만 한다.
   PostToolUse 포맷터는 *방금 편집된 그 파일*만, 프로젝트 설정이 그 도구를 골랐을 때만 고친다.
2. **동의 신호는 사용자 요청·승인된 계획·프로젝트 설정 파일뿐이다.** 실행 파일이 설치돼 있다는 것, 설명이
   맞아떨어졌다는 것, 파일이 있다는 것은 쓰기 동의가 아니다.
3. **기존 구조를 따른다.** 없는 디렉토리·새 배치 체계는 사용자가 그 산출물을 요청했거나 경로를 확인한 뒤에만
   만든다. 킷 경로(`docs/plans/`·`docs/specs/`)는 기본 *제안*이지 기본 동작이 아니다.
4. **사용자 소유 파일은 이름으로 요청받았을 때만 고친다** — CLAUDE.md·AGENTS.md·GEMINI.md·`.gitignore`·
   매니페스트·lock·CI·에디터 설정·`.claude/settings*`. 그 밖에는 "권장 변경(diff)"으로 보고한다.
5. **설치하지 않는다.** 의존성 설치·패키지 내려받아 실행(npm/pip/poetry/uv/npx/uvx/pipx/brew 류)은 명령을
   제안만 한다. 프로젝트가 정의한 빌드·테스트 명령이 원래 만드는 산출물은 허용한다.
6. **트리 밖 상태는 정해진 자리뿐이다** — `<git-common-dir>/kit/`·`<git-dir>/kit/`·`$TMPDIR/claude-<uid>/`.
   조회에 실패하면 작업 트리로 물러서지 않고 기록을 건너뛴다(fail-open). 심링크를 따라 그 밖에 쓰지 않는다
   (`path-containment.md`).
7. **새 쓰기 경로는 아래 등록부에 적는다** — 경로·컴포넌트·트리거·동의·되돌리는 법.

정책 본문은 세션 주입에 넣지 않는다(상시 주입 예산 7,168B 에 거의 닿아 있다). 규칙은 이 문서, 강제는 아래
기계 검사, 기여자 확인은 `CLAUDE.md` Contributing 체크리스트가 맡는다.

이 예산은 **소비자 세션 기준**으로 잰다. 주입 출력은 플러그인 루트 절대경로를 머리 한 줄에서만 밝히고
나머지 킷 경로는 `<킷 루트>/…` 로 쓴다(v5.9.0 — 전에는 빈 세션에서 7회 반복). 게이트는 측정 전에 실제 루트를
경로 B(직접 마켓플레이스) 캐시 형태의 고정 길이 대표값(`check_injection_budget.py::REPRESENTATIVE_PLUGIN_ROOT`, 78자)
으로 바꾼다. 경로 B 를 고른 이유: Claude Code 에서 세션 훅이 도는 설치는 경로 B 뿐이다(경로 A 디렉토리판은 훅이
없다). 그래서 판정은 이 레포가 어디 체크아웃됐는지와 무관하다. 소비자마다 실제 바이트는 사용자 이름·버전 길이만큼
±수십 B 움직인다.

## 강제

| 수단 | 무엇을 잡나 |
|---|---|
| `tests/hooks/test_consumer_footprint.py` | 픽스처 레포에서 훅·도구를 실제 프로세스로 돌린 전후 트리·index 불변 — 세션 시작의 구 원장 개명, 비-git 원장 쓰기, 설정 없는 prettier, pre-commit 의 무설정 수정·부분 스테이징 재스테이징·JSONC 거부(macOS `/bin/bash` 3.2 포함), checklist 심링크 탈출 |
| `tests/hooks/test_auto_format.py` | 설정·`go.mod` 없는 ruff·gofmt·rustfmt 미호출, `testdata`·`vendor` 의 gofmt 미호출(양성 대조 포함) |
| `setup.sh` 격리 실행(`test_consumer_footprint.py`) | 비대화형에서 전역 무변경, 워크트리·`core.hooksPath` 레포 처리, 낡은 템플릿 사본, `--uninstall` 설치→제거 왕복·수정본·심링크·남의 templateDir 보존·`--dry-run` 무변경·플러그인 자동 제거 없음 |
| `scripts/check_consumer_footprint.py` (verify-done §30·CI) | 배포 지침(`plugins/common/**/*.md`)의 설치·패키지 실행 명령. 금지·설명 문장은 그 줄에 `footprint-ok` 표시 |
| 행동 eval (`evals/`) | 에이전트가 실제로 만든 경로 — 기존 테스트 배치 존중, 지침 파일 무수정, 설치 없음 |

## 쓰기 등록부

| 경로 | 컴포넌트 | 트리거 | 동의 | 되돌리는 법 |
|---|---|---|---|---|
| 편집한 그 파일(포맷) | `hooks/auto-format.py` | 파일 쓰기 직후 | 프로젝트 설정(ruff·prettier·eslint·`rustfmt.toml`), Go 는 `go.mod` 의 `go fmt ./...` 범위(gofmt 는 설정 파일이 없다) | git |
| 편집한 `.py`(린트 수정) | `hooks/stop-validator.py` | 턴 종료 | 프로젝트 ruff 설정 | git |
| 스테이징한 `.py`(린트 수정·재스테이징) | `setup/pre-commit` | `git commit` | `setup.sh` 설치 + 프로젝트 ruff 설정 + 부분 스테이징 아님 | git |
| `docs/plans/<날짜>-<slug>/plan.md`·`checklist.json` | `plan-task`·`auto-dev`·`tools/checklist.py` | 계획 요청 | 사용자가 정한 자리 또는 기존 `docs/plans/`, 없으면 물어서 | 파일 삭제 |
| `docs/specs/<날짜>-<주제>.md` | `brainstorming` | 설계 승인 후 | 위와 같음 | 파일 삭제 |
| `.claude/agents/<name>.md`·`~/.claude/agents/` | `agent-creator` | 사용자 호출 | 위치 선택 | 파일 삭제 |
| `.claude/skills/<name>/SKILL.md` | `skill-forge` | 사용자 호출 | 초안 승인 | 파일 삭제 |
| `AGENTS.md`·`GEMINI.md` 마커 블록 | `harness-export` | 사용자 호출 | 호출 자체 | 마커 블록 삭제 |
| 프로젝트의 기존 문서 | `sync-docs` | 위임 | 지침 파일은 지정됐을 때만 | git |
| 기존 테스트 배치 안의 테스트 | `write-tests` | 위임 | 새 최상위 디렉토리는 보고 후 | git |
| `<git-common-dir>/kit/ledger.md` | `tools/feedback_ledger.py upsert` | 리뷰 결함 기록 | auto-dev 실행 | 파일 삭제 |
| `<git-common-dir>/cross-engine/<slug>/` | `cross-engine-review` | 사용자 호출 | 호출 자체 | 디렉토리 삭제 |
| `<git-dir>/kit/child.json`·워크트리·브랜치 | `control-loop`·`child-session`·`isolation: worktree` 에이전트 | 위임 | 위임 자체 | `git worktree remove` |
| `$TMPDIR/claude-<uid>/` | 훅 상태·잠금 | 자동 | — (트리 밖) | 디렉토리 삭제 |
| 플러그인 user 범위 설치(Claude Code 사용자 설정의 `enabledPlugins`)·`~/.claude/.setup-state.json` | `setup.sh` | 사용자 실행(Full 설치) | 설치 실행 | 상태 파일은 `./setup.sh --uninstall`. 플러그인은 그 명령이 **안내만** 한다 — `claude plugin uninstall hiway-kit@hiway-kit` |
| 실행한 레포의 공용 hooks 디렉토리 `pre-commit`(`core.hooksPath` 레포는 설치하지 않음) | `setup.sh` | 사용자 실행(Full 설치) | 설치 실행 | `./setup.sh --uninstall` — 배포본과 바이트가 같을 때만 지우고, 다르면 남기고 알린다 |
| `git init.templateDir`(→ `~/.claude/git-templates`) | `setup.sh` | 사용자 실행 | 대화형 질문에 y(비대화형은 건너뜀). 낡은 사본은 `--force` 때만 갱신 | `./setup.sh --uninstall` — 값이 그 경로일 때만 해제, 템플릿 사본은 배포본과 같을 때만 삭제. 손으로는 `git config --global --unset init.templateDir` |

구 원장(`docs/works/feedback/ledger.md`)은 읽기 호환만 남는다 — 옮기는 것은 사용자가 <!-- doc-status-ok: 구 원장 읽기 호환을 설명한다 -->
`tools/feedback_ledger.py migrate` 로 할 때뿐이다.

## 관련

- `path-containment.md` — 설정값·심링크로 만든 경로의 봉쇄
- `warning-signal.md` — 검사가 도는 조건 한 문장, 대상 나열 대신 제외 나열
