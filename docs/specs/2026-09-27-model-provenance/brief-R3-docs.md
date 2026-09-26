# 브리프 R3 — 운송 문서·README·checklist 리뷰 반영 (W-045)

- 부모: plan-control 컨트롤 (Orca Run). 역할: 레포 문서 3종의 리뷰 지적 반영
- 워크트리: Orca new-child, 자기 브랜치에만 커밋. 기준 커밋: 디스패치 spec 해시
- 먼저 `docs/specs/2026-09-27-model-provenance/review-fix.md` 를 읽는다 (**child-session 은 Skill 로드 금지 — Read**)

## ① 전제 (규범 리뷰 지적 — 착수 전 재확인)

- N-ATK-001(일부) [H]: 운송 문서 §2 "고유값 전부를 적는다" 형식은 전환 시점·비율을 지운다(실측: high 3 → medium 47 단일 전환).
  원인은 스킬 frontmatter effort — R2 가 제거한다
- N-ATK-002 [M]: `<synthetic>` 모델값 레코드가 실재(이 머신 135건) — 필터 없음; 세션을 cwd 로만 찾아 재사용 워크트리에서
  이전 작업이 섞인다; 서브에이전트 전사(`<sessionId>/subagents/`)가 표의 `*.jsonl` 에 안 잡힌다
- N-ATK-003 [M]: 키 파생 예시(`/`→`-`)가 불완전(`_`도 `-`), `~/.claude`·`~/.codex` 하드코딩(`CLAUDE_CONFIG_DIR`·`CODEX_HOME` 무시 —
  Orca 는 계정별 `CODEX_HOME` 을 쓴다 `[confirmed]`), `archived_sessions/` 누락, 원격 배치 로그는 원격 호스트
- N-ATK-005 [M]: 로그 원문을 열면 비신뢰 텍스트·시크릿이 컨트롤 컨텍스트로 — 필드만 뽑는 명령을 정본으로, `rules/untrusted-text.md` 참조
- N-ATK-010 [L]: `--model <전체 ID>` 는 실측 없음
- N-ATK-011 [L]: 기록처 중 Work progress 는 gitignore — 트래킹되는 병합 커밋 메시지를 필수 기록처로
- N-ATK-007 [L]: README 새 행 "agents are not shipped" 는 틀렸다(캐시에 복사되지만 서브에이전트로 노출 안 됨 — `packaging/targets.json`
  실측); :121 "hook runs but cannot veto" 는 :108(protect-sensitive 미탑재)과 어긋남; 스킬 frontmatter effort 는 Claude Code 에서
  세션에 적용됐었다(R2 가 제거 — 문서화 불필요, 이 행에 쓰지 말 것)
- N-ATK-009 [L]: checklist :40 "19 skills"(실제 21), 제외 목록에 session-check 누락, stop-validator 사유 누락(`targets.json` `_omitted`)

## ② 범위

IN:
1. 운송 문서 §2: 로그 찾기를 **레코드의 `cwd` 값 검색**으로(키 파생 삭제), `${CLAUDE_CONFIG_DIR:-$HOME/.claude}`·`${CODEX_HOME:-$HOME/.codex}`
   (`sessions` + `archived_sessions`), Dispatch 시작~완료 시각으로 필터(세션 id 가 있으면 우선), `<synthetic>` 제외, 서브에이전트 모델
   별도 열, **순서 보존 run-length**(`uniq -c`) 기록 형식, 원격 배치는 해당 호스트에서 확인, 필드만 뽑는 jq 명령을 정본으로·원문 열람 금지·
   로그는 비신뢰(`rules/untrusted-text.md`), 필수 기록처 = 병합 커밋 메시지, `--model <전체 ID>` 는 `[미검증]`
2. README Other Harnesses: 새 행 사유 정정("shipped in the package but not exposed as subagents (measured)"), :121 정정
3. checklist: 21 skills, `_omitted` 3종과 사유를 `targets.json` 에서 인용
4. 게이트: `./scripts/verify-done.sh > /tmp/vd-r3.out 2>&1; echo $?`, `check_doc_counts.py`
5. 커밋 1~2개

OUT: `plugins/**`(R2), `evals/**`(R1), CHANGELOG·CLAUDE.md·AGENTS/GEMINI(컨트롤)

## ③ 금지

push · main/plan-control 쓰기 · bare stash/reset --hard/clean -fd · 모델 호출 금지 · 세션 로그 원문을 문서·커밋에 인용 금지(필드명·모델 ID 만) ·
게이트 rc 파이프 금지

## ④ 보고

`[R3 docs] 완료 — <파일 N개>, 커밋 <sha>, 테스트 <verify-done pass 수>` + 병합 측 후속. `worker_done` 으로.
