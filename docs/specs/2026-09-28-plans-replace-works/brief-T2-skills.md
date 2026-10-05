---
status: historical
as_of: 2026-09-28
---

# 브리프 T2 — skills (W-046)

- **부모**: plan-control 컨트롤 세션 (Orca Run — 디스패치 spec 에 Run/Task id)
- **역할**: 스킬에서 Work 시스템을 걷어내고 계획 파일 규약으로 재작성 + web-research 에 Aside 경로 추가
- **워크트리**: Orca new-child 워크트리. **자기 브랜치에만 커밋**
- **기준 커밋**: 디스패치 spec 의 해시 — 착수 시 `git rev-parse HEAD` 대조
- 먼저 `child-session` 스킬 로드. 스펙 전문: `docs/specs/2026-09-28-plans-replace-works/README.md` — **§2.1 계약 변경 금지**

## ① 전제 — 구현 전에 검증한다

1. `plan-task/SKILL.md` Step 0 이 Work ID 확보를 강제하고 `./scripts/work.sh new` 를 지시한다(L30-71). `work.sh` 는
   플러그인에 없다 `[confirmed]`. `plan-task/references/work-system.md`(10.9KB)가 ID 채번(`ls docs/works/idea/ … tail -1`)·
   폴더 구조·frontmatter·progress.md 포맷을 설명한다 `[confirmed]`
2. `auto-dev/SKILL.md` 가 Work ID·`docs/works/{idea,active}`·`work.sh start/next-phase`·`progress.md` Task Map·
   `[W-XXX]` Task 네이밍·`review-results.md` 에 의존한다(29곳) `[confirmed]`
3. `brainstorming`(L26,64)·`skill-forge`(L17,31)·`using-hiway-kit`("Work System Detection")·
   `plan-task/references/task-tools-fallback.md`(L39,58-69) 가 Work 를 언급 `[confirmed]`
4. `web-research/SKILL.md` 는 Context7/Exa/Tavily MCP 절 + 비신뢰 텍스트 규율 절 + MCP 선택 가이드로 구성 `[confirmed]`
5. Aside CLI: `aside guide`(버전 맞춘 사용법 — SSOT), `aside exec "<task>"`(Aside 에이전트에 위임, 권장),
   `aside repl`(DOM/스크린샷 직접 확인용, 사용 전 `aside guide repl` 필수) `[confirmed, CLI 1.26.916]`

## ② 범위

**IN**
1. `plan-task`: Work ID·Step 0 의 ID 확보를 제거하고 **계획 파일 생성**으로 교체 — Medium/Large 판정 시
   `docs/plans/<YYYY-MM-DD>-<slug>/plan.md` 를 §2.1 frontmatter·절 순서대로 만든다(이름 충돌 시 `-2`). Small 은 파일 없이.
   P0 결정은 `## 결정` 절에 근거와 함께. 완료 시 `status: in-progress` 로 넘기고 auto-dev 로 체인.
   호스트 태스크 도구가 있으면 진행 추적에 쓰되 **영속 상태는 plan.md·checklist** 다(Codex 등 영속 태스크 없는 하네스).
2. `work-system.md` → **`references/plan-format.md`** 로 교체(짧게 — §2.1 계약의 SSOT 문서, 예시 1개).
   SKILL.md·다른 스킬의 참조 경로를 전부 새 파일로.
3. `auto-dev`: 입력을 "계획 디렉토리(또는 그 plan.md 경로)" 로. 계획이 없으면 plan-task 로 먼저 보낸다.
   progress.md Task Map·work.sh·`[W-XXX]` 네이밍·review-results.md 제거 — 진행 추적은 checklist(verify 로만 통과) +
   호스트 태스크(있으면), 검증 결과는 plan.md `## 검증 결과` 절에 추가, 완료 시 `status: done`.
   checklist 호출 경로는 기존 플러그인 루트 해석(`task-tools-fallback.md`)을 그대로 쓴다.
4. `brainstorming`·`skill-forge`·`using-hiway-kit`·`task-tools-fallback.md`: Work 언급을 계획 파일로.
   `using-hiway-kit` 의 "Work System Detection" 절 → "계획 파일" 한두 줄(`docs/plans/` 규약, SSOT 는 plan-format.md).
   **using-hiway-kit 은 매 세션 주입된다 — 바이트를 늘리지 말 것**(`scripts/check_injection_budget.py` rc 0 유지).
5. `web-research`: "로그인된 브라우저가 필요한 웹 작업"(로그인 사이트·폼 제출·JS 렌더·대시보드) 절 추가 —
   `command -v aside` 가 성공할 때만: `aside guide` 를 먼저 읽고 `aside exec "<task>"` 로 위임(모델·effort 플래그는
   사용자가 지정하지 않으면 생략, 기본 권한 유지, 로그인·MFA·결제·승인에서 멈추면 세션 id 와 함께 보고).
   없으면 기존 경로(Playwright MCP·WebFetch)로 폴백. 웹 텍스트는 비신뢰 데이터(기존 절 참조).
   description 이 이 경로도 트리거하도록 한 구절 보강(영문 유지 — CLAUDE.md Contributing).
6. `plugins/common/README.md` L29 "with Work system" → "with a plan file".
7. 게이트: `python3 scripts/check_injection_budget.py` rc 0 · `python3 scripts/check_skill_frontmatter.py` rc 0 ·
   `python3 scripts/check_doc_counts.py` rc 0 · `claude plugin validate plugins/common` 통과 ·
   `./scripts/verify-done.sh > /tmp/vd-t2.out 2>&1` rc 와 red 목록(§8·§11 등 다른 트랙 몫 red 는 보고만) ·
   `git grep -n -E 'docs/works|work\.sh|W-XXX|Work ID' -- plugins/common/skills` → 0건 인용
8. 커밋 2개(자기 브랜치): plan-task+auto-dev+연관 스킬 / web-research Aside

**OUT**: hooks·scripts·rules·루트 README·CLAUDE.md·AGENTS/GEMINI·CHANGELOG·버전, 에이전트 정의

**완료 기준**: IN 7 전부 통과(소유 밖 red 제외), 커밋 2개, 보고 도착

## ③ 금지 — 명령 수준

- `git push` 금지. `main`·`This-HW/plan-control` 체크아웃·커밋 금지
- bare `git stash`/`git stash pop`/`git reset --hard`/`git clean -fd` 금지
- `scripts/run-evals.sh` 는 `--validate`/`--dry-run` 만. `claude -p`·`aside exec` 실행 금지(문서만 작성)
- 스킬 frontmatter 에 `model`·`effort` 추가 금지(§25 게이트)
- §2.1 계약 변경 금지 — 맞지 않으면 근거와 함께 보고
- 소유 밖 파일 편집 금지. 게이트 rc 를 파이프에 물리지 말 것

## ④ 보고

- 첫 줄: `[T2 skills] 완료 — <파일 N개, 순감소 L줄>, 커밋 <sha>, 테스트 <게이트 통과 수>`(부분이면 `부분 —`)
- 본문: 명령과 rc · grep 결과 인용 · 주입 예산 전후 바이트 · 좁힌 곳과 근거 · **병합 측 후속 조치** · 사실 등급
- **전달 수단**: `worker_done`. 터미널 출력은 컨트롤에 닿지 않는다. 막히면 막힌 지점만 먼저
