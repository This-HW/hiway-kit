---
status: historical
as_of: 2026-09-27
---

# 브리프 R2 — 스킬 frontmatter·규범·훅 리뷰 반영 (W-045)

- 부모: plan-control 컨트롤 (Orca Run). 역할: 스킬 effort 덮어쓰기 제거 + 게이트, 규범·훅 리뷰 지적 반영
- 워크트리: Orca new-child, 자기 브랜치에만 커밋. 기준 커밋: 디스패치 spec 해시
- 먼저 `docs/specs/2026-09-27-model-provenance/review-fix.md` 를 읽는다 (**child-session 은 Skill 로드 금지 — Read**)

## ① 전제 (착수 전 재확인)

1. 스킬 frontmatter `effort` 가 세션 effort 를 덮어쓴다 — 양성 대조 `[confirmed]`(review-fix.md). `model` 은 메인 스레드에
   적용되지 않았다 `[관측 n=1]`. `plugins/common/skills/*/SKILL.md` 19종 중 17종이 `model`·`effort` 선언 `[confirmed]`
2. 킷은 모델·effort 를 사용자/호스트 설정의 몫으로 둔다(control-loop SKILL "모델 이름과 기본값은 사용자/호스트 설정의 몫")
3. 규범 리뷰 지적:
   - N-ATK-004 [M]: `skills/harness-export/SKILL.md:19` Codex 행 "훅 없음"(+:26-28 CLAUDE.md 제외 사유), `hooks/export_harness.py:446`
     주석, `rules/untrusted-text.md:23-24` "훅이 없는 하네스" — 이번 릴리스가 고쳤다고 한 부류가 남아 있다
   - N-ATK-006 [M]: `cross-engine-review` "실행 주체" 줄 — 종료 체크리스트(:231)에 없음, 출처 요건 없음, 머리 줄 3개 순서 미정,
     :130 "다른 증거원" 문구가 운송 문서 §6(같은 하네스의 다른 모델은 다른 엔진이 아니다)과 충돌
   - N-ATK-008 [L]: `child-session` 파리티 절 — 훅 신뢰 승인 전제 누락, opt-in git 훅(`setup/git-hooks/reference-transaction`)은
     하네스 무관하게 차단한다는 사실 누락
4. 코드 리뷰 지적:
   - C-ATK-004 [M]: `export_harness.py:818` 참조 티어 안내가 훅 없는 하네스(Gemini CLI·OpenCode 등, AGENTS.md 의 1차 독자)에서
     해석 불가 — 결정적 폴백(킷 홈페이지 URL + 레포 경로) 병기 필요
   - C-ATK-009 [L]: `test_session_start.py` 신규 테스트가 주입 전문 부분문자열에 걸려 무관한 변경에 깨진다; 렌더된 indexLine
     대상 파일이 **실재하는지** 아무도 보지 않는다

## ② 범위

IN:
1. `plugins/common/skills/*/SKILL.md` **전부**에서 frontmatter `model:`·`effort:` 줄 제거. `skill-creator`(와 `agent-creator` 가
   스킬 템플릿을 낸다면 그것)의 **스킬** 템플릿에서도 제거 — 에이전트 템플릿은 유지
2. 게이트 신설 `scripts/check_skill_frontmatter.py`: 모든 스킬(대상 나열 말고 제외 나열 — `warning-signal.md` §5)이
   `model`/`effort` 를 선언하면 exit 1, 이유 문장 포함. `verify-done.sh` 다음 빈 번호(§25)와 CI(`validate.yml`)에 같은 스크립트.
   되돌려-FAIL(한 스킬에 `effort: high` 넣으면 red) 인용
3. N-ATK-004: harness-export Codex 행을 "주입·포맷 훅 있음(신뢰 승인 후), 차단 훅 없음 — 신뢰 전엔 AGENTS.md 폴백"으로,
   :26-28 의 이중 도달 예외 명시, `export_harness.py:446` 주석 정정, `untrusted-text.md:24` "차단 훅이 없는 하네스(Codex 포함)" →
   CHECKSUMS 재생성(미러 없음 확인). 되돌려-FAIL: `rg -n '훅 없음|훅이 없는|without hooks' plugins/` 결과 인용
4. N-ATK-006: 체크리스트에 실행 주체 줄 + 출처(로그 경로·필드 또는 명령 출력) 항목, 머리 줄 순서 명시, :130 을
   "재현을 위해 기록한다 — 같은 하네스의 다른 모델을 다른 엔진으로 치지 않는다"로
5. N-ATK-008: child-session 파리티 절에 "(훅 신뢰 승인 후)", opt-in git 훅 문장
6. C-ATK-004: 안내 문구에 결정적 폴백(`KIT_HOMEPAGE` 등 export_harness 가 이미 가진 상수 재사용) + "세션 시작 훅이 도는
   하네스(Claude Code, 신뢰 승인된 Codex)는 절대 경로로 안내된다"
7. C-ATK-009: 테스트 단언을 `참고(필요할 때 읽어라):` 이후 구간으로 한정 + **모든 reference 규범**에 대해 렌더된 절대 경로
   `is_file()` 매개변수화 테스트
8. 게이트: hooks pytest · `check_injection_budget.py`(상한 변경 금지 — red 면 멈추고 보고) · `ruff` · `lint-shell.sh` ·
   `export-harness.sh --check`(rc1 예상, 재생성은 컨트롤) · `verify-done.sh > /tmp/vd-r2.out 2>&1; echo $?`(§11 외 red 보고)
9. 커밋 2~3개(스킬 frontmatter+게이트 / 규범·훅 / 테스트)

OUT: `AGENTS.md`/`GEMINI.md`, `CHANGELOG.md`, `CLAUDE.md`, 버전, `docs/control-loop-transport.md`·`README.md`·checklist(R3),
`evals/**`(R1), 에이전트 frontmatter

## ③ 금지

push · main/plan-control 쓰기 · bare stash/reset --hard/clean -fd · `export-harness.sh` 는 `--check` 만 · `run-evals.sh` 실행 금지 ·
`claude -p`·`codex exec` 금지 · 예산 상한 변경 금지 · 게이트 rc 파이프 금지

## ④ 보고

`[R2 skills-rules-hooks] 완료 — <파일 N개>, 커밋 <sha>, 테스트 <n passed>` + 되돌려-FAIL 인용 + verify-done red 목록 +
병합 측 후속(AGENTS/GEMINI 재생성 등). `worker_done` 으로.
