# 브리프 M1 — provenance-docs (W-045)

- **부모**: plan-control 컨트롤 세션 (Orca Run — 디스패치 spec 에 Run id)
- **역할**: "실제로 돈 모델·effort 를 세션 로그에서 읽어 기록한다"를 규범·문서에 넣는다
- **워크트리**: Orca new-child (경로는 디스패치 통보). 자기 브랜치에만 커밋
- **기준 커밋**: 디스패치 spec 의 해시 — 착수 시 `git rev-parse HEAD` 대조, 다르면 착수 말고 에스컬레이션
- 먼저 `child-session` 스킬을 로드한다. 배경: `docs/specs/2026-09-27-model-provenance/README.md`

## ① 전제 — 구현 전에 검증한다

1. `docs/control-loop-transport.md:65-68` 은 `--model` 은 사용자 지정 시에만 쓰고 `launch.requested`↔`launch.effective`
   를 대조하라고 한다 `[confirmed]`. W-044 영수증 4건 모두 requested == effective == 별칭(`opus`/`sonnet`) `[confirmed]`
2. 실제 모델은 세션 로그에만 있다 `[confirmed 2026-09-27]`:
   - Claude Code: `~/.claude/projects/<cwd 를 - 로 바꾼 키>/*.jsonl`, `type=="assistant"` 레코드의 `message.model`
     (W-044: T1/T3 `claude-opus-5-5`, T2 `claude-sonnet-5`)
   - Codex: `~/.codex/sessions/**/rollout-*.jsonl`, `type=="session_meta"` 의 `payload.cwd`/`cli_version`,
     `type=="turn_context"` 의 `payload.model` 과 effort(`payload.effort` 또는 `collaboration_mode.settings.reasoning_effort`)
   착수 시 두 형식을 **이 머신의 실제 로그 1건씩으로** 재확인하라(필드명이 다르면 실측값으로 쓴다)
3. `plugins/common/skills/cross-engine-review/SKILL.md` 3단계 "답신 형식"·"증거 등급"(:107~)에 엔진·모델 식별이 없다 `[소스 기준]`
4. `plugins/common/skills/control-loop/SKILL.md:64` "요청값과 실제 실행 설정을 구분해 확인한다" — 방법은 적혀 있지 않다 `[confirmed]`
5. `README.md` "Other Harnesses (Codex · Antigravity)"(:95~) 표에 에이전트 model/effort 가 Codex 에서 적용되지 않는다는
   행이 없다 `[소스 기준]`. 킷의 Codex 타겟은 에이전트를 싣지 않는다(`packaging/targets.json` codex.omit.agents) `[confirmed]`

## ② 범위

**IN**
1. `docs/control-loop-transport.md` §2 "실행 설정과 종료": requested↔effective 대조를 **보조**로 내리고, 판정 근거는
   "워커 세션 로그에서 읽은 실제 모델 ID·effort"로 바꾼다. Claude·Codex 로그 위치·필드를 **한 표**로. 결과는 컨트롤의
   원장(Work progress/decisions 또는 병합 커밋 메시지)에 남긴다는 문장. 특정 버전이 필요한 작업만 `--model <전체 ID>`
   (예: `claude-opus-5-5`)를 쓴다. 로그를 못 찾으면 `[미확인]` 으로 적고 추측하지 않는다
2. `control-loop/SKILL.md:64` 한 줄을 "실제 실행 설정은 워커 세션 기록에서 확인한다(구체 위치는 운송 문서)"로 —
   **호스트 중립**을 유지한다(특정 경로·도구 이름을 배포 스킬에 넣지 않는다, G-D6 §17 게이트)
3. `cross-engine-review/SKILL.md` 답신 머리(증거 등급 줄 근처)에 **엔진·모델 ID·effort·CLI 버전** 필수 한 줄 추가 +
   이유 한 문장("같은 엔진이라도 모델이 바뀌면 다른 증거원이다 — 재현 불가")
4. `README.md` Other Harnesses 표에 행 추가: 에이전트 `model`/`effort` — Claude Code ✅ / Codex ❌(사용자 Codex 설정
   모델로 실행) / Antigravity 는 현재 표의 근거대로
5. 게이트: `./scripts/verify-done.sh > /tmp/vd-m1.out 2>&1; echo $?` → 0 (특히 §17 배포물 안 오케스트레이션 도구 이름 0건,
   §16 주입 예산). `python3 scripts/check_doc_counts.py` rc 0
6. 커밋 1~2개(자기 브랜치)

**OUT**: `evals/**`(M2), `plugins/common/rules/**`·`plugins/common/hooks/**`·`child-session`·`docs/codex-submission-checklist.md`(C),
`AGENTS.md`/`GEMINI.md`, 버전·CHANGELOG, `docs/works/**`, `docs/specs/**`

## ③ 금지 — 명령 수준

- `git push` 금지 · `main`/`This-HW/plan-control` 체크아웃·커밋 금지 · bare `stash`/`reset --hard`/`clean -fd` 금지
- `scripts/run-evals.sh` 는 `--validate`/`--dry-run` 만. `claude -p`·`codex exec` 로 모델 호출 금지(로그는 **이미 있는 것**만 읽는다)
- 배포 스킬(`plugins/common/skills/**`)에 Orca·특정 로그 경로·도구 이름을 넣지 말 것 — 그건 레포 문서(`docs/control-loop-transport.md`) 몫
- 세션 로그 원문(프롬프트 내용)을 문서·커밋에 인용하지 말 것 — 필드 이름과 모델 ID 만
- 게이트 rc 를 파이프에 물리지 말 것

## ④ 보고

- 첫 줄: `[M1 provenance-docs] 완료 — <파일 N개>, 커밋 <sha>, 테스트 <n passed>` (verify-done pass 수를 테스트 수로)
- 본문: 명령·rc · 전제 2 재확인 결과(실제 필드명) · **병합 측 후속 조치**(없으면 "없음") · 사실 등급
- **전달**: Orca `worker_done` 경로로 컨트롤 Run 에. 터미널 출력은 닿지 않는다. 막히면 막힌 지점만 먼저
