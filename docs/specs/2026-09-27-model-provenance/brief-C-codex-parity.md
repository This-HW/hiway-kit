# 브리프 C — codex-parity (W-045)

- **부모**: plan-control 컨트롤 세션 (Orca Run — 디스패치 spec 에 Run id)
- **역할**: 워크트리 위임 규범의 SSOT(`delegation-contract`·`child-marker`)가 **어느 하네스에서든 도달 가능**하게 하고,
  Codex 훅 지원에 관한 모순된 서술을 사실에 맞춘다
- **워크트리**: Orca new-child. 자기 브랜치에만 커밋
- **기준 커밋**: 디스패치 spec 의 해시 — 착수 시 대조, 다르면 에스컬레이션
- 먼저 `child-session` 스킬을 로드한다. 배경: `docs/specs/2026-09-27-model-provenance/README.md`

## ① 전제 — 구현 전에 검증한다

1. `rules/delegation-contract.md`·`rules/child-marker.md` 는 `tier: reference`, `portable: true`, **`indexLine` 없음** `[confirmed]`.
   `session-start.py` `load_rules` 는 reference 티어를 `indexLine` 으로만 알린다 → 두 규범은 Claude·Codex 어디에도
   주입·안내되지 않는다 `[소스 기준]`. 스킬은 이 둘을 SSOT 로 10곳에서 가리킨다(`git grep -o 'rules/delegation-contract.md\|rules/child-marker.md' plugins/common/skills`) `[confirmed]`
2. v3.39.0 에서 indexLine 은 플러그인 루트의 **절대 경로**로 렌더된다(`session-start.py` `load_rules`) `[confirmed]`.
   Codex 는 `hooks-codex.json` 으로 `session-start.py --portable-only` 를 돌린다 — portable 규범과 그 indexLine 만 남긴다 `[confirmed]`
3. 상시 주입 예산: `scripts/check_injection_budget.py` — 항상 8,706B/9,216B, 최악 18,757B/20,480B `[confirmed 2026-09-27]`.
   indexLine 은 절대 경로라 **설치 경로 길이만큼** 늘어난다. 예산 게이트는 레포 경로로 잰다 `[소스 기준]`
4. `plugins/common/hooks/export_harness.py:818` 은 참조 티어를 AGENTS.md 에 "본문은 **킷 레포**에서 읽어라"로 쓴다 —
   소비자에겐 킷 레포가 없다 `[confirmed]`. 같은 파일 :496 한계표는 훅(… auto-format)을 "Claude Code 훅 런타임 전용 —
   다른 하네스에는 실행 지점이 없다"로 쓴다 `[confirmed]`
5. Codex 는 SessionStart(`--portable-only`) + PostToolUse(auto-format) 훅을 **실제로 돌린다** — `README.md:108,116`,
   `~/.codex/config.toml` 의 `hooks.state."hiway-kit@…:hooks/hooks-codex.json:session_start"`·`post_tool_use` trusted_hash
   `[confirmed]`. `protect-sensitive`(PreToolUse 차단)는 Codex 에 **싣지 않는다**(README:108 — 차단이 유지되지 않음) `[confirmed]`
6. 그런데 `plugins/common/skills/child-session/SKILL.md` "파리티" 절(:97~)은 "훅은 Claude Code 전용 … Codex 등 훅이 없는
   하네스", `docs/codex-submission-checklist.md:47` 은 "Codex's hook runtime does not load this kit's … hook format" 이라
   쓴다 `[confirmed]` — README 와 모순

## ② 범위

**IN**
1. 두 규범에 `indexLine` 추가(짧게 — 예: `위임 브리프·보고 형식 계약은 rules/delegation-contract.md 를 읽어라`,
   `자식 마커 스키마는 rules/child-marker.md 를 읽어라`). CHECKSUMS 재생성
   (`(cd plugins/common/rules && shasum -a 256 *.md | grep -v CHECKSUMS > CHECKSUMS.sha256)`). 두 규범은 미러가 없다 `[confirmed]`
2. 테스트: `--portable-only` 로 로드했을 때 두 indexLine 이 **절대 경로**로 렌더되고, 비-portable reference(agent-system 등)는
   빠지는지(`plugins/common/hooks/tests/test_session_start.py` 기존 portable 테스트 옆에). 되돌려-FAIL 인용
3. `check_injection_budget.py` rc 0 확인. **red 면 상한을 올리지 말고** indexLine 문구를 줄이고, 그래도 red 면
   멈추고 보고(예산 상한은 컨트롤 결정)
4. `export_harness.py:818` 문구를 "본문은 **플러그인 설치 경로**의 `rules/<name>.md`(훅이 있는 하네스는 세션 시작 시
   절대 경로로 안내된다)"로. `:496` 한계표 훅 행을 사실대로: session-start·auto-format 은 Codex 에서도 돈다(신뢰 필요),
   protect-sensitive·stop-validator 는 Claude Code 전용. `plugins/common/hooks/tests/test_export_harness.py` 가 문구를
   고정하면 함께 갱신
5. `child-session/SKILL.md` 파리티 절: "훅이 없는 하네스" → "**차단 훅**(PreToolUse)은 Claude Code 전용이다. Codex 는
   세션 시작 주입·자동 포맷 훅만 돈다 — 자동 **차단**은 없고 이 규율은 지침으로 작동한다"
6. `docs/codex-submission-checklist.md` hooks 항목을 README 와 일치하게(무엇이 실리고 무엇이 안 실리는지)
7. 게이트: `python3 -m pytest -q plugins/common/hooks/tests` rc 0 · `python3 scripts/check_injection_budget.py` rc 0 ·
   `ruff check .` rc 0 · `./scripts/export-harness.sh --check`(rc 1 예상 — 재생성은 컨트롤, 보고만) ·
   `./scripts/verify-done.sh > /tmp/vd-c.out 2>&1; echo $?` — §11(AGENTS/GEMINI 드리프트) red 는 예상, 그 외 red 는 보고
8. 커밋 1~2개(자기 브랜치)

**OUT**: `AGENTS.md`/`GEMINI.md`(컨트롤 재생성), `docs/control-loop-transport.md`·`control-loop` 스킬·`cross-engine-review`·
`README.md`(M1), `evals/**`(M2), 버전·CHANGELOG, `docs/works/**`, `docs/specs/**`, 예산 상한값

## ③ 금지 — 명령 수준

- `git push` 금지 · `main`/`This-HW/plan-control` 체크아웃·커밋 금지 · bare `stash`/`reset --hard`/`clean -fd` 금지
- `scripts/export-harness.sh` 는 `--check` 만 · `scripts/run-evals.sh` 실행 금지 · `codex exec`/`claude -p` 호출 금지
- `scripts/check_injection_budget.py` 의 상한값 변경 금지
- `~/.codex/**` 쓰기 금지(읽기만)
- 게이트 rc 를 파이프에 물리지 말 것

## ④ 보고

- 첫 줄: `[C codex-parity] 완료 — <파일 N개>, 커밋 <sha>, 테스트 <n passed>`
- 본문: 명령·rc(예산 수치 인용) · 되돌려-FAIL 인용 · verify-done red 섹션 목록 · **병합 측 후속 조치**
  (AGENTS/GEMINI 재생성, 버전 범프 필요 — 규범·스킬·훅 변경) · 사실 등급
- **전달**: Orca `worker_done` 경로로 컨트롤 Run 에. 막히면 막힌 지점만 먼저
