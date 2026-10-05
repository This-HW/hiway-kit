---
title: "전수 감사 후속 — 문서 싱크·하네스 연계·스킬 로직·게이트·외부 동향 흡수"
created: 2026-10-05
size: large
status: proposal
as_of: 2026-10-05
---

# 전수 감사 후속 (v5.4.0)

**결정자**: 컨트롤(plan-control) — 사용자 지시 2026-10-05 *"프로젝트 기능·하네스 기능 전체 체크, 최신 방법론 접목, Claude·Codex·Antigravity·Gemini 연계 최적 조합, 설계·기획 문서 싱크·로직, 맥락 없는 기획 개발자 이해 가능성, 개선 병렬 진행"*.
**근거**: 읽기 전용 감사 4건(기준 커밋 `e7181cb` = v5.3.0) — `audit/A-harness.md`(하네스 연계) · `audit/B-docs.md`(문서 싱크·로직) · `audit/C-research.md`(외부 동향) · `audit/D-coldread.md`(Codex 엔진 콜드 리딩). 발견 ID(`A-P0-2`, `B-P1-12`, `C-C1`, `D-1` 식)는 그 파일을 가리킨다.
**기준 커밋**: 이 스펙이 들어간 커밋(브리프에 SHA 로 고정).

## 왜

`verify-done.sh` 33/0 green 상태에서 P0 급 사실 오류가 **9건** 나왔다(B 6 + A 2 + D 1). 전부 **게이트가 보지 않는 곳**이다 — `docs/`·README·CLAUDE.md 의 참조 실재성, 시점 고정 문서의 지위, 코드 사실을 복제한 서술, 미러 내용, 하네스 실측 기록의 유효기간. 공통 원인 3가지(B 총평): ① 시점 고정 문서에 지위 표기 없음 ② 같은 내용을 두 곳에 유지 ③ 코드는 바뀌었는데(4.0.0 Work 제거·5.2.0 `tools/`·5.3.0 평탄화·`PORTABLE` 제거) 서술이 남음. 하네스 쪽은 실측 기록이 CLI 한 세대 전(Codex 0.153.4 → 0.159.3, agy 1.1.28 → 1.2.17)이라 **뒤집힌 주장 2건**(Codex PreToolUse 차단 가능, Antigravity 에이전트 미인식 원인은 `model:` frontmatter)이 소비자 문서에 남아 있다.

## 결정 (재론 금지 — 전제가 실물과 다르면 근거와 함께 질문)

### 공통
- **D0** 버전 **5.4.0**(minor — 스킬 동작·게이트·Codex 매니페스트 파생이 바뀜). 버전 범프·CHANGELOG 조립·타겟 재생성·AGENTS/GEMINI 최종 재생성·태그·push 는 **컨트롤**이 병합 후 한 번에 한다. 워커는 버전을 올리지 않고, CHANGELOG 본문 대신 `docs/specs/2026-10-05-audit-remediation/changelog-<W>.md` **조각**을 쓴다.
- **D0-2** 문서 지위 frontmatter 스키마(모든 `docs/**/*.md`, README·CLAUDE.md 제외): `status: current | historical | proposal | superseded`, `as_of: YYYY-MM-DD`, superseded 는 `superseded_by: <경로>`. `historical`·`superseded` 문서는 참조 실재성·금지 토큰 검사 **제외**. 본문 첫 줄 아래에 지위를 한 줄로 반복하지 않는다(필드가 SSOT).
- **D0-3** 숫자·목록을 산문에 복제하지 않는다 — 개수는 `check_doc_counts.py`, 게이트 목록은 `verify-done.sh`, CI 단계는 `validate.yml`, 종료코드는 `--help`/docstring 이 소유. 문서는 가리키기만 한다(B (b) SSOT 지도 채택).
- **D0-4** 레포 밖 근거(공식 문서 URL·실측)는 날짜·CLI 버전을 붙여 적는다. "measured" 라벨은 기록 위치(`packaging/targets.json` 의 관측 키 또는 `docs/specs/.../audit/*.md` 절)를 가리켜야 한다.

### 문서 (W1)
- **D1** B 의 P0-1·4·5·6, P1-1~9·13~20·29~31, P2-1~13, P3-2~6, D 의 1~7, C 의 F1·F2·F4·F6·F7·F8·F10 을 전부 반영한다. 처분: `docs/pipeline-reinforcement-plan-v2.md` **삭제**(B (c)), research 6건에 지위 frontmatter + 머리 정정 인라인, `docs/research/README.md`·`docs/specs/README.md` 색인 신설(status 포함), `docs/conventions/README.md` 색인 전부 채움.
- **D2** CLAUDE.md 는 **줄이면서** 고친다(예산 42,971/43,008B): 릴리스 절 → `docs/conventions/release-process.md` 포인터 한 줄(`@import` 아님 — 예산), CI 7항목 열거 삭제, 게이트 7종 괄호 열거 삭제, maxTurns 는 "frontmatter 가 소유", "100% ambiguity" → "P0 ambiguity = 0", Adding a New Agent 에 로스터·eval tier·시나리오 의무 한 줄, `/agent-creator` 는 프로젝트 에이전트용, Sub-agent Rules 에 "네이티브 기본(중첩 3단계)과 다른 의도적 선택" 한 줄, Distribution 은 marketplace-submission 상단 요약표 포인터. 캐시 경로는 `<marketplace>/hiway-kit/<version>[-<sha>]` 로 일반화.
- **D3** `docs/marketplace-submission.md` 상단에 **채널별 상태 요약표**(채널 / 상태 / 확인일 / 다음 행동)를 신설하고 그것을 배포 상태 SSOT 로 한다. 아래 역사 절들은 `(역사)` 표기로 접는다. `codex-submission-checklist.md` 는 절차·기록만.
- **D4** README: 이력 서사(v3.34 릴리스 노트 문단) 삭제, "Feature Development 체인"·Multi-perspective 절은 스킬 링크로 축소, Project Structure 에 `tools/`·`setup/`, 기여 체크리스트의 "Registered in plugin.json" 은 메타데이터 확인으로 정정, 첫 화면에 "Claude Code 가 완전 기능 기준, 나머지는 capability 표의 부분 지원" 한 줄(D-7), Codex 절에 **마켓플레이스 vs 디렉토리 ZIP 표**(훅 유무·규범 도착 경로·ZIP 소비자는 `/harness-export` 필수 — A-P1-1), Antigravity 에이전트 원인 정정(`model:` — A-P1-3), Gemini CLI 절 신설("GEMINI.md 만 제공, extension·스킬·훅 미제공 — 런타임 미측정" — A-P1-7, **D-Gemini 결정: 정식 타겟으로 올리지 않는다**, 키 복구 후 재검토), `~/.agents/skills` 공용 경로 안내 한 단락(A #9, 네임스페이스 소실·중복 설치 경고 포함), `README.md:122` Codex 차단 문구 정정(A-P0-2 — 문구는 W2 가 `targets.json` 에 적는 기록을 인용).
- **D5** `docs/native-absorption.md`: C §8 diff 적용 + 신규 7행 + 표 파이프 이스케이프 + W-ID → 스펙 경로 치환 + 로그 내림차순 + 5.1~5.3 항목 추가. **판정**: C1 `claude plugin eval` → `adopt(pilot)`(W5), C3 workflows → `watch`(이번 라운드 미채택 — Claude 전용·오케스트레이션 모델 변경이라 별도 결정), C4 AGENTS.md 이중 도달 → `decide`(사용자 결정 대기, 문서는 이번에 정정), C5 SubagentStart → `decide`(사용자), C14 서브에이전트 헤더 → `absorbed(partial)`, M1/M2 주입 예산 → 이미 §15 게이트 있음 — AGENTS.md 32 KiB(Codex 절단) 상한을 §15 에 추가하는 것은 W4.

### 하네스·규칙·생성물 (W2)
- **D6** `rules/` 변경 3건: `definition-of-done.md` "Task 마감 규율" 을 Task 도구 유무 조건부로 고치고 폴백(`skills/plan-task/references/task-tools-fallback.md`)을 가리킨다(C-F3) · `agent-system.md` Phase 3→Complete 기준을 auto-dev T-merge 와 일치시키고 "Must Fix" 를 정의하거나 삭제, Phase Gate 1→2 는 "규모별 기준은 elicitation §6"(B-P1-10·11) · `child-marker.md:57` "조상이 아니면 경고"(B-P1-22). → CHECKSUMS 재생성, 미러 5종 내용 동기(B-P0-4 `db-tunnel.sh` 삭제, P1-19·20·21 정정) + `MIRROR.sha256 --regenerate`.
- **D7** `tools/export_harness.py` 문구 정정(A-P0-2 Codex 차단 문장, `:422` 하네스 목록에 Antigravity·Gemini CLI 명시, "이식하지 못하는 것" 표에 Antigravity/Gemini "주입 없음 — 정적 파일만"·"Antigravity 는 AGENTS.md+GEMINI.md 둘 다 읽어 이중 로드"(A-P1-8)) + `skills/harness-export/SKILL.md` 전면 정정(B-P0-2·3 exit code·`PORTABLE`, A-P0-1 Antigravity 규범, C-F5 CC 2.1.277+ AGENTS.md 직접 읽음, 전달 형태 표에 Antigravity 행, 도구 탐색은 D10 규약 참조) + `skills/child-session/SKILL.md:99-101` 정정. AGENTS.md/GEMINI.md 재생성은 **컨트롤이 병합 후** 한다(W2 는 `--check` 가 red 임을 보고만).
- **D8** `packaging/targets.json` 실측 기록 갱신(A (a) 표 전부): Codex 0.159.3 — PreToolUse 차단 **가능**(exit 2·`permissionDecision:"deny"`, 양성 대조 포함), 훅 페이로드 스키마(`Bash`/`apply_patch` + `tool_input.command`), 스킬 15/15, 쉘 환경에 `CLAUDE_PLUGIN_ROOT` 없음; agy 1.2.17 — 진입점 양 파일 도달·이중 로드 COUNT=2·스킬 인식·plugin `rules/` 미도착·에이전트는 `model:` 값으로 제외(`inherit`/생략 인식)·`validate` 는 개수만 셈·`agy -p` rc 규약 변경; Gemini 런타임 미측정(키 무효). `_omitted` 사유는 "차단 불가" → "차단 가능 확인(2026-10-05), 이식은 별도 결정(D-Codex-hook)". `$schema` 404 기록. 낡은 "33개·카테고리" 삭제.
- **D9** **Codex `agents/openai.yaml` 파생**(C-X1): `build-targets.py` 가 각 스킬의 frontmatter에서 `interface.display_name`·`short_description`(필수) 과 `disable-model-invocation: true` → `policy.allow_implicit_invocation: false` 를 만든다. 생성물은 `plugins/common/skills/<name>/agents/openai.yaml`(Codex 규격 위치 — 공식 문서 URL 을 `targets.json` 에 기록). Claude Code 가 이 파일을 무시하는지 `claude plugin validate --strict` 로 확인. `--check` 드리프트 포함. ZIP(`build-codex-zip.py`)에 실리는지 확인.
- **D10** 스킬의 킷 도구 탐색 규약(A-P1-6): SSOT 는 `skills/plan-task/references/task-tools-fallback.md`(W3 소유). 순서: ① `$CLAUDE_PLUGIN_ROOT` ② SKILL.md 기준 상대 경로 `../../tools/` ③ `~/.claude/plugins/cache/*/hiway-kit/*/tools` ④ `~/.codex/plugins/cache/*/hiway-kit/*/tools` ⑤ 실패 시 `--plugin-root` 직접 지정 안내. W2 의 harness-export 는 그 절을 **가리키기만** 한다.
- **D-Codex-hook / D-SubagentStart / D-AGENTS-dup**: 사용자 결정 대기(아래 "사용자 결정"). 이번 라운드는 **문서·기록만** 현재 사실로 고친다.

### 스킬 로직 (W3)
- **D11** B-P1-11·12·23~28, P2-9·10, C-M4 반영: Small 경로·크기 기준 정본 = `elicitation.md §6`(나머지는 참조) · Task 도구 폴백을 실행 가능하게(Planning/Brainstorm/Validation 단계의 대체 = 대화창 진행표 + plan.md, `checklist.py` `verify` 필수와 충돌 없게, auto-dev `:222,250` "도구가 있으면" 가드) · brainstorming 태스크 잔존 문장 정정 · test/debug 에 fix-bugs(worktree) 결과 반영 단계 + 재시도 상한(N회/무진전 2회) · auto-dev T-review 가 review 스킬의 diff 인라인·6파일 배치 규칙을 참조 · review 0단계 대상 확정 선행·`--diff-filter=d`·stderr 숨기지 않음·평가 등급 표를 review-code 실제 출력(REJECT/CONDITIONAL/ACCEPT·C/H/M/L)으로 · skill-forge 강등 경로를 ledger 가 아닌 보고로 · cross-engine-review 우편함을 모든 트리가 보는 경로로 · MPR/web-research 3중 복제를 개요+링크로 · **MPR 에 "관점별 근거 필수 + 명시적 반대 라운드"**(C-M4; 합의만으로 통과 금지) · 경로 기준 통일(`skills/<name>/references/...`).
- **D12** D10 탐색 규약을 `task-tools-fallback.md` 에 쓰고 auto-dev·plan-task 가 그것을 쓴다.
- 스킬 `description`(영어) 은 바꾸지 않는다(발동률 회귀 방지 — W5 파일럿이 측정하기 전까지).

### 게이트 (W4)
- **D13** 신설 3종(각각 독립 스크립트 + `verify-done.sh` 새 §번호 + `validate.yml` 호출, `no-gate-integration.md` 원칙 — 읽기 쉬운 게이트, red 메시지에 **고치는 법**을 적는다 C-M3):
  1. `scripts/check_doc_refs.py` — `git ls-files '*.md'` 에서 제외(CHANGELOG·archive·`status: historical|superseded`)를 뺀 전 문서의 마크다운 링크·`@import`·슬래시 포함 백틱 경로·백틱 `*.sh|*.py` 파일명·`def`/함수형 식별자 실재성. 예외는 파일 단위 목록으로.
  2. `scripts/check_doc_status.py` — D0-2 스키마 필수(없으면 red), `status: current` 문서의 금지 토큰(`agents/(dev|meta|planning)/`, `hooks/(checklist|feedback_ledger|export_harness)`, `docs/works`, `work.sh`, `W-0\d\d`, 구 플러그인 이름)·표 열 수 불일치(GFM — 코드 스팬 안 파이프 포함).
  3. `check_injection_budget.py` 에 **AGENTS.md ≤ 24 KiB(agy 파일 상한)·GEMINI.md 동일** 검사 추가(C-M2·A-X7; Codex 32 KiB 는 전역 AGENTS.md 와 합산이라 경고 수준).
  각 게이트는 **의도적 위반 1건으로 red 를 확인**하고 되돌리는 테스트를 `scripts/tests/` 에 둔다. 도는 조건을 docstring 한 문장으로.
- **D14** `scripts/verify-done.sh:679-680` §17 주석·`sync-rule-mirror.sh` "(9개)" 정정(B-P3-8). `packaging/name-targets.json` 의 CHANGELOG 제외는 항목 본문에만(헤더 문장은 검사 대상 — B-P2-3).

### 외부 동향 흡수 (W5)
- **D15** `claude plugin eval` **파일럿**(C-C1): `plugins/common/evals/` 에 스킬 발동 케이스 **3~5개**(예: 새 기능 요청 → `plan-task` 발동, 에러 로그 → `debug`, 리뷰 요청 → `review`, Small 버그 → 스킬 미발동) + 무플러그인 baseline Δ. 먼저 `claude plugin eval --help` 와 **실제 실행 가능 여부**(early-access 게이트) 확인 — 안 되면 케이스만 커밋하고 보고. 비용 상한 `--max-cost-usd` 명시. `build-codex-zip.py` 에서 `evals/` 제외(디렉토리 ZIP 크기·심사 표면). `evals/README.md` 에 "레포 `evals/`(에이전트 행동·기준선) vs 플러그인 `evals/`(스킬 발동)" 구분 절. 기존 `evals/` 는 건드리지 않는다.

## 사용자 결정 (P0 — 제품 범위·보안) — **2026-10-05 답: 세 건 모두 기본값 확정**

| ID | 질문 | 기본값(답 없으면) |
| --- | --- | --- |
| D-Codex-hook | Codex 0.159.3 에서 PreToolUse 차단이 가능해졌다. `protect-sensitive`(경로 차단)를 Codex 에 이식할까(페이로드 `Bash`/`apply_patch` 파서 추가, 대화형·PermissionRequest 경로 실측 후 켬) | **보류** — 문서만 정정, 이식은 별도 스펙 |
| D-SubagentStart | `SubagentStart` 훅으로 서브에이전트에 규범을 주입할까(기술 조건 해소, 메모리 `no-system-prompt-injection` 가드와 충돌) | **하지 않음** — 원장 `decide` 로 기록 |
| D-AGENTS-dup | CC 2.1.277+ 가 CLAUDE.md 없는 프로젝트에서 AGENTS.md 를 읽어 훅 주입과 **이중 도달**. (a) 문서만 (b) SessionStart 훅이 마커 있는 AGENTS.md + CLAUDE.md 부재를 감지하면 규범 본문 주입을 건너뜀 | **(a)** — (b)는 별도 스펙 |

## 워커 분할 (파일 소유 — 겹치지 않는다)

| W | 소유 | 금지 |
| --- | --- | --- |
| W1 docs | `README.md`, `CLAUDE.md`, `plugins/common/README.md`, `packaging/README.md`, `docs/**`(아래 W2 소유 제외), `docs/native-absorption.md`, `docs/specs/**` frontmatter, `docs/research/README.md`·`docs/specs/README.md` 신설, `.gitleaksignore`(경로 변경 시) | `plugins/common/{rules,skills,tools,hooks}/**`, `docs/architecture/rules/**`, `packaging/targets.json`, `AGENTS.md`, `GEMINI.md`, `scripts/**` |
| W2 harness | `plugins/common/rules/**`(+CHECKSUMS), `docs/architecture/rules/**`(+MIRROR.sha256), `plugins/common/tools/export_harness.py`(+tests), `plugins/common/skills/{harness-export,child-session}/**`, `packaging/targets.json`, `scripts/build-targets.py`(+tests, D9), `scripts/build-codex-zip.py`(openai.yaml 포함 확인만), `plugins/common/hooks/hooks-codex.json`(생성물) | 그 밖의 `skills/**`, `README.md`, `CLAUDE.md`, `docs/**`(위 제외), `AGENTS.md`·`GEMINI.md` 수정(재생성은 컨트롤) |
| W3 skills | `plugins/common/skills/**` 중 W2 소유 2종 제외 전부(+references), `plugins/common/tools/checklist.py` 는 읽기만(스키마 불변) | `rules/**`, `tools/**` 수정, `README.md`, `CLAUDE.md`, `docs/**` |
| W4 gates | `scripts/check_doc_refs.py`·`scripts/check_doc_status.py`(신설)·`scripts/check_injection_budget.py`·`scripts/verify-done.sh`·`scripts/sync-rule-mirror.sh`·`.github/workflows/validate.yml`·`packaging/name-targets.json`·`scripts/tests/**` | 문서 본문 수정(게이트가 red 를 내면 **보고**, 고치는 것은 W1/컨트롤) |
| W5 plugin-eval | `plugins/common/evals/**`(신설), `scripts/build-codex-zip.py` 의 `evals/` 제외 1줄, `evals/README.md` 구분 절 | 그 밖 전부 |

병합 순서(컨트롤): W2 → W3 → W1 → W4 → W5. W4 의 새 게이트가 W1 결과에 red 를 내면 컨트롤이 그 자리에서 고친다(문서 1파일 국소 수정 범위). 그 뒤 `bump-version.sh 5.4.0` → CHANGELOG 조립(조각 5개 + 룰 sha) → `export-harness` 재생성 → `verify-done.sh` → push → 태그.

## 완료 조건

결정적(전부 exit 0, 컨트롤이 병합 후 실행):

```bash
scripts/verify-done.sh                                        # 신설 게이트 3종 포함 green
python3 scripts/check_doc_refs.py && python3 scripts/check_doc_status.py
python3 scripts/build-targets.py --check                      # openai.yaml 생성물 포함
./scripts/export-harness.sh --check                           # 재생성 후
test ! -f docs/pipeline-reinforcement-plan-v2.md
! git grep -n -E 'PreToolUse 차단이 유지되지 않|db-tunnel\.sh|_resolve_target\b|PORTABLE 또는' -- ':!docs/specs' ':!CHANGELOG.md' ':!docs/CHANGELOG-archive.md'
test "$(python3 - <<'EOF'
import os,re,glob
bad=[p for p in glob.glob('docs/**/*.md',recursive=True) if not re.search(r'^status: (current|historical|proposal|superseded)$', open(p).read()[:600], re.M)]
print(len(bad))
EOF
)" = 0
```

비결정적: 콜드 리딩 재검(D 절차를 병합 후 한 번 더 — 질문 10개 중 문서로 답할 수 있는 수가 ≥ 8), eval 25건 후퇴 0(기준선 재생성 — 컨트롤), W5 파일럿 실행 결과 기록.

## 범위 외

Codex `protect-sensitive` 이식 · SubagentStart 주입 · AGENTS.md 이중 도달 억제 훅 · Gemini extension 타겟 · Antigravity 전용 생성 루트(`model` 제거본) · 플러그인 `workflows/` 파일럿 · 얇은 GEMINI.md(`@./AGENTS.md`) 전환(Gemini 런타임 실측 전) · 스킬 description 변경.
