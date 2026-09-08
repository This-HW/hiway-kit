# 02 — Stage 분해 (층 3): 구현 LLM 지시서

> 기준 커밋 **`3f85f47`**. 값은 `01-policy.json`, 게이트 명령은 `03-gate-spec.md`,
> 진입점은 `04-handoff.md`. **이 파일은 "이번 턴에 무엇을 하는가"만 봉인한다.**
>
> **분해 기준은 작업 항목 개수가 아니라 "한 Stage 가 구현 LLM 컨텍스트 한 번에 들어가는가"** 다.
> 각 Stage 머리에 **읽기 집합(read set)** 과 그 크기를 실측으로 적었다 — 그것이 분해의 근거다.
> 읽기 집합이 60KB를 넘거나 파일이 12개를 넘으면 쪼갰다.
>
> 각 Stage 는 4블록: **전제(변경 금지) / 이번 범위 / 금지사항 / 완료 조건**.
> **금지사항의 첫 항목은 항상 `01-policy.json` 의 `absoluteProhibitions` 전체다** — 매 Stage 에 복사된다.

---

## 0. 의존 그래프 (위반하면 게이트가 red)

> **Q1 답신으로 구조가 바뀌었다.** 게이트 신설은 더 이상 별도 Stage 가 아니라
> **검사 대상을 고치는 Stage 안에, 같은 커밋으로** 들어간다.

```
W-025
  S0  환경위생(A)            ── 독립. 다른 어떤 Stage 와도 순서 관계 없음

  ┌─ C 트랙 (v2.18.0) ──────────────────────────────────────────────────┐
  │  S1 참조정합 + §17 게이트 ⟨같은 커밋⟩ ──┐                            │
  │  S2 스킬정리 ───────────────────────────┤                            │
  │  S3 에이전트 ───────────────────────────┼──► S7 릴리스(v2.18.0)      │
  │  S4 티어선언(골격) ──► S5 규범삭제·중립화 ──► S24 untrusted-text 신설 │
  │                                             └──► S6 축약 + §16 ⟨같은 커밋⟩
  └─────────────────────────────────────────────────────────────────────┘
                          │ (S10 만 C 트랙 완료가 전제 — 아래 주 참고)
                          ▼
  ┌─ B 트랙 (버전 무변경) ────────────────────────────────────┐
  │  S10 카운트 탐지전환(warn-first)  ← S2·S5·S24 완료가 전제  │
  │  S11 eval 인프라      (순서 자유)                          │
  │  S12 문서구조         S12a → S12b 내부 순서만              │
  └───────────────────────────────────────────────────────────┘

  ⟨퇴역 번호⟩ S8 · S9 — 각각 S6 · S1 에 흡수됐다. 번호는 재사용하지 않는다.

  ⟨의존 정정 2026-09-07⟩ 위 블록 화살표는 **S10 에만** 걸린다.
  S11·S12 의 「전제」 블록에는 Stage 의존이 없고 설계 제약(D-12·D-14·D-15·D-16·D-29)만 있다.
  그림이 블록 단위 화살표로 그려져 **B 트랙 전체가 v2.18.0 릴리스 뒤로 직렬화되는 것처럼**
  읽혔다 — 실제로는 S11·S12 를 릴리스 없이 먼저 돌릴 수 있다.
  판정 근거: 각 Stage 의 「전제」가 그래프보다 **구체적이므로 우선한다.**

W-026  (W-025 전부 완료 후 — §5: "W-025 를 지금 방식으로 먼저 돌리는 것이 26-1 의 입력이다")
  S13 하네스심 ──► S14 control-loop 본문 ──► S15 운송부록(docs/) + G-D6
                                    ├──► S16 agent-teams 폐기예고
                                    └──► S25 work-system.md 재작성
                                                    └──► S17 릴리스(v2.19.0)

W-027
  S18 프로브 ──┬──► S20 게이트판정 ──┐
  S19 생성기 ──┴─────────────────────┼──► S21 파리티문장 ──► S22 개명(v3.0.0) ──► S23 카탈로그
                                     └── S22 는 S18·S19 완료 전 착수 금지 (되돌림 불가)
```

### Q1 이 이 그래프를 어떻게 바꿨나

검수는 **warn-first 정책 플래그**(O1·O2 해소)를 권고했고 컨트롤은 **기각**했다. 근거는
W-024 선례다 — `tier2CoverageEnforceFail` 을 도입 즉시 fail 로 놓으며 이렇게 적었다:

> 이 배치가 유일한 갭을 같은 배치에서 메우므로 승격 직후 16/16 green 이다. …
> **영구 노란 경고는 아무도 보지 않는다.**

지금이 정확히 같은 상황이다. 그래서:

| 게이트 | 원안 | 확정 | 이유 |
| --- | --- | --- | --- |
| §17 참조 실재(25-16) | B 트랙 별도 Stage(S9) | **S1 에 흡수, C 트랙, `enforceFail=true`** | 검사 대상(dangling 8종)을 같은 커밋에서 고친다 |
| §16 주입 예산(25-14) | B 트랙 별도 Stage(S8) | **S6 에 흡수, C 트랙, `enforceFail=true`** | 예산을 맞추는 축약이 같은 커밋에 있다 |
| 카운트 탐지(25-17) | B 트랙 | **B 트랙 유지, `enforceFail=false` + 승격 조건** | 제외 경로 규칙의 정확도가 미지수다(E8). **근거가 다르므로 취급도 다르다** |

**"같은 커밋" 이 O1·O2 를 해소하는 방식**: 게이트와 그 대상이 한 커밋에 있으면 중간에
red 인 상태가 **존재하지 않는다.** 플래그로 미루면 승격을 잊을 자유가 생긴다 —
그것이 W-024 의 문장이 경계한 것이다.

**B 트랙이 여전히 C 뒤인 이유**는 S10(카운트 탐지) 하나 때문이다. 규범 수·스킬 수를
바꾸는 C 가 먼저 끝나야 탐지 결과가 안정된다.

---

# W-025 — 위생 · 구조 정비

## S0 — 환경 위생 (A 트랙 · 컨트롤 전용 · 커밋 없음)

> **읽기 집합**: 없음(레포 파일을 읽지 않는다). 대상은 `~/.claude/` 전역 설정.
> **담당**: 컨트롤. 워커에게 위임하지 않는다 — 4블록 브리프를 쓸 레포 대상이 없고(§5),
> 되돌림 자산이 존재하지 않는다.

### 전제 (변경 금지)
- `~/.claude/settings.json` 의 **orca 훅 shim 12벌**(파일의 79%) — 남의 생성물. 손대지 않는다(§6).
- `~/.claude/projects/` 1.4GB — 메모리·`self-improve` 의 원천 자산. 보존 기준 확정 전 삭제 금지(§6).
- 레포 파일 일체.

### 이번 범위
1. **착수 전 스냅샷**(신설 — `00-REVIEW.md` 위험 완화책):
   `permissions.allow` 42개 원문과 `~/.claude.json` 의 projects 키 목록을 **배치 보고서 본문에**
   기록한다. 커밋이 없으므로 **보고서가 유일한 되돌림 자산**이다.
2. `25-1` 경로가 실재하지 않는 projects 항목 정리.
   **주의**: 건수가 §1.4(26건)와 D-10/25-1(28건)로 갈린다 — 착수 시 재실측하고 실측값을 보고서에 남긴다.
3. `25-3` 플러그인 캐시 잔재(temp 클론 4 · `cck-probe-marketplace` · 킷 구버전 캐시 2).
4. `25-4` 유령 플러그인 설치 기록 8건.
5. `25-6` `permissions.allow` 최소화(D-11). **프로젝트 전용(`Bash(<project>:*)`) 먼저**, 광범위 쓰기
   (`curl`·`ssh`·`scp`·`source`·`chmod`) 나중 — 오작동 시 영향이 국소적인 쪽부터.
6. `25-5` 설정 백업 4개 정리. **A 트랙의 마지막**으로 옮긴다 — 1~5 후 최소 1세션 정상 동작 확인 뒤.

### 금지사항
- `01-policy.json` `absoluteProhibitions` 전체.
- **`settings.json` 의 orca 훅 shim 블록을 건드리는 것.**
- 스냅샷 기록 전 어떤 항목이든 삭제하는 것.
- `~/.claude/projects/` 트랜스크립트 삭제.

### 완료 조건
- `03-gate-spec.md` **G1** green (경로 없는 projects 항목 0건).
- 스냅샷이 보고서에 존재하고, 제거한 allowlist 항목의 before/after 목록이 명시됨.
- **수용 테스트 4는 이 Stage 의 완료 조건이 아니다** — `00-REVIEW.md` X3/R2 참조.
  판정 불가 서술이므로 "bypass off 1세션 실행 로그"를 산출물로 남기는 것으로 대체한다.

---

## S1 — 상호 참조 정합 **+ §17 게이트 신설** (C 트랙 · 워커) 【같은 커밋】

> **읽기 집합**: 에이전트 8종 + CLAUDE.md 해당 절 + `verify-done.sh` §7 인접부
> ≈ **13 파일**. 8종의 frontmatter 와 해당 줄만 보면 되므로 실제 읽기는 훨씬 작다.
> **분해 근거**: 이 Stage 를 S3(에이전트 축약)과 합치면 33개 에이전트 전문이 읽기 집합에
> 들어와 한 컨텍스트를 넘긴다. `references:` 정합 + 그 게이트만 떼어낸다.
>
> **【Q1 답신】 구 S9(§17 게이트)를 이 Stage 에 흡수했다.** 게이트와 그 검사 대상을
> **같은 커밋**에 넣어야 중간 red 상태가 존재하지 않는다. `enforceFail` 플래그는 두지 않는다 —
> W-024 선례: *"영구 노란 경고는 아무도 보지 않는다."*

### 전제 (변경 금지)
- 에이전트 **파일명**은 안정 식별자다. 개명 금지(D-14 와 같은 판단).
- `plugins/common/skills/multi-perspective-review/` 의 4개 참고 문서 — **이것이 SSOT** 이고
  S2 가 `skills/references/` 의 중복 사본을 지운다. 메타 에이전트의 새 참조 대상은 **이쪽**이다.
- `rules/parallel-worktree.md` 본문 — S3 의 대상이지 이 Stage 가 아니다.

### 이번 범위
1. `25-21` **미완 실행 잔재 5종**(D-28):
   - `dev/generate-boilerplate.md:44-46` 폐기된 `DELEGATE_TO`/`TASK_COMPLETE` 템플릿 제거
   - `planning/define-business-logic.md` · `planning/design-user-journey.md` 에 `isolation: worktree` 추가
   - 메타 에이전트 5종의 "Agent Teams 듀얼 모드" 절 → **이 Stage 가 아니라 S16**(D-7 과 동시)
   - `plugins/common/README.md:56` 훅 서술 정정 (루트 README 문구와 일치시킨다)
   - `evals/README.md:3-5` 커버리지 과소 서술 정정 → **B 트랙(S11)** 로 이동(배포물 아님)
   - CLAUDE.md "Delegation Signal — 어디까지 걷어냈나" 목록에 `generate-boilerplate.md` 추가
2. **【검수 추가 · E3】 dangling `references:` 8종 10경로 전부 정리**:
   - `dev/implement-code.md` · `dev/plan-implementation.md` · `dev/review-code.md` — `references:`
     **필드 제거**(내용이 본문에 이미 인라인, 기능 손실 없음). `implement-code.md:115` 의 잘못된
     SSOT 주석 경로(`agents/common/dev/...`)도 정정.
   - `meta/facilitator.md` · `synthesizer.md` · `consensus-builder.md` · `devils-advocate.md` ·
     `facilitator-teams.md` — 경로를 `../../../skills/multi-perspective-review/<file>.md` 로 정정
     (**주의**: `skills/common/` 세그먼트가 오류의 원인이다. 존재한 적 없다).
   - **`facilitator-teams.md` 는 S16 에서 폐기 대상**이므로 그때 파일째 사라질 수 있다 —
     이 Stage 에서는 정정하고, S16 에서 D-7 결론에 따라 처리한다.
3. **【검수 추가 · E5】** `dev/analyze-tech-debt.md:95` 의 `대상: claude_setting` → `대상: [프로젝트명]`.
4. **【검수 추가 · E6】** `dev/manage-api-versions.md:54-61, :159-176` 의 `agents/**/index.json` ·
   frontmatter `version:` 서술 삭제 또는 "이 킷은 에이전트별 버전을 관리하지 않는다"로 교체.
5. **【검수 추가 · L10】** `isolation` 규약 위반 전수 재확인. 실측 4건 중 `facilitator`·`synthesizer`는
   **고치지 않는다** — 산출물을 메인 세션이 즉시 읽어야 하므로 격리하면 다관점 리뷰가 끊긴다.
   대신 `rules/parallel-worktree.md` 에 **예외 사유 1줄**을 기록한다.
   (이 예외 판단은 컨트롤 승인 항목 — 답신이 다루지 않았으므로 `[unresolved]` 로 두고 보고한다.)
6. **`25-16` §17 상호 참조 실재 게이트 신설 — 위 1~5 와 같은 커밋.**
   - 다음 빈 번호는 **17**. **§12 는 영구 결번**이다(W-022 R1 — 스펙·decision-log 47곳 이상이
     번호로 게이트를 참조한다).
   - 검사 ①`references:` 경로 실재(**문자열 리스트·`path:` 매핑 두 형태 모두 파싱**)
     ②산문이 지목하는 에이전트명 실재 ③스킬이 지시하는 레포 내 경로 실재.
   - **검사 ④(도구명 허용 집합)는 이대로 구현하지 마라** — `00-REVIEW.md` L6/R1.
     외부 표면의 손-유지 열거라 D-23·D-32 2행과 정면 모순이고 대상은 실측 1건(`LSP`)뿐이다.
     대안: 금지 패턴(`mcp__*`) + **레포 내 유일 출현 토큰** 탐지. 답신이 이 건을 다루지
     않았으므로 원문대로 갈지는 컨트롤 확인 사항이며, 확인 전에는 ①②③만 구현한다.
   - **`enforceFail` 플래그를 두지 않는다** — 처음부터 fail(Q1 답신).
   - **§7 과 부분 중복**이다(§7 이 이미 `hooks.json` 의 `.py`, rules/agents 산문의
     `scripts/*.sh` 실재를 검사한다). 대상 분할을 **코드 주석 1문장**으로 기록한다 —
     설계 §0 기준 2("같은 질문에 답하는 컴포넌트를 둘 두지 않는다").

### 금지사항
- `absoluteProhibitions` 전체.
- **에이전트 파일명 변경.**
- **`skills/references/` 의 파일을 참조 대상으로 지정하는 것** — S2 가 삭제한다.
- `dev/enforce-structure.md` 수정 — S3 의 몫이다.
- 메타 에이전트의 "듀얼 모드" 절 수정 — S16 의 몫이다.
- 새 에이전트 생성(`design-database` 등 phantom 대상을 "만들어서" 참조를 성립시키지 마라 —
  §6 의 구조 변경 금지와 D-22 의 취지에 반한다. **참조를 지우는 것이 처방이다**).
- **§12 번호 사용.**
- **게이트만 만들고 대상 정리를 다음 커밋으로 미루는 것** — 그 순간 red 상태가 생기고,
  Q1 답신이 막으려 한 것이 정확히 그것이다.

### 완료 조건
- **G22** green(되돌려-FAIL — 검사 ①②③ **각각 1회씩**): 존재하지 않는 참조를 심으면 §17 이
  실제로 red, 되돌리면 green.
- **G17-1** green: `references:` 실재 검사가 0 MISSING (현재 실측 **10경로 / 8파일**).
- **G27** 실행 결과가 예외 목록(`facilitator`·`synthesizer`)과 정확히 일치.
- `grep -rn "design-database\|explore-infrastructure\|plan-infrastructure" plugins/common/` → 0건.
- `grep -rn "claude_setting" plugins/` → 0건.
- `verify-done.sh` **전 게이트 green** (§17 포함 — 이 커밋에서 처음부터 fail 모드다).

---

## S2 — 스킬 디렉토리 정리 (C 트랙 · 워커)

> **읽기 집합**: `skills/README.md`(약 330행) + `references/` 10종 + `mcp-builder/SKILL.md` +
> 루트 `README.md:71` ≈ **13 파일**. `references/` 8종은 삭제 대상이라 정독 불필요(존재 확인만).

### 전제 (변경 금지)
- `references/task-tools-fallback.md` — `brainstorming`·`plan-task`·`auto-dev` 3곳이 실제 인용하는
  **활성 SSOT**(2026-08-28 갱신). 내용 수정 금지.
- `multi-perspective-review/` 안의 4개 문서 — SSOT. 삭제 대상은 `references/` 쪽 사본이다.
- `agent-teams/SKILL.md` — S16 의 몫.

### 이번 범위
1. `25-23` **`plugins/common/skills/README.md` 삭제**(D-31). 스킬은 디렉토리에서 자동 발견되므로
   손으로 유지하는 색인은 드리프트 원천이다(D-23 과 같은 논리).
2. `25-23` 루트 `README.md:71` 의 21-vs-19 설명 정정.
3. `25-18` **`references/` 8종 삭제**(D-24 + §11.2(b)):
   - DUP 4: `conflict-resolution` · `deliberation-pattern` · `examples` · `perspectives-guide`
   - 순수 고아 4: `available-tools` · `model-selection` · **`phase-guides`** · `work-integration`
   - **`phase-guides.md` 는 삭제한다.** D-24 본문이 "활성 참조" 로도 적었으나 T3 §4.4 실측은
     참조 0건이다(`00-REVIEW.md` L4). §11.2(b) 의 "순수 고아 4종 → 삭제" 가 유효하다.
4. **【검수 L5 · Q3 답신으로 확정】 잔존 2종 이관** — `task-tools-fallback.md` · `work-system.md` 를
   **`plugins/common/skills/plan-task/references/`** 로 옮기고 인용 3~5곳의 상대경로를 갱신한다.
   Q3 답신이 *"① L5 결정대로 `plan-task/references/` 로 이관"* 으로 못박았다.
   **이관하지 않으면 `references/` 디렉토리가 남아 최상위 진입이 20 이 되고, 수용 테스트 28 이
   실패하며 `targets.json` 의 "해소됨" 갱신이 거짓 기록이 된다.**
5. **【E4 · Q3 답신】 `work-system.md` 는 이 배치에서 재작성하지 않는다.**
   상단에 **구세대 경고 배너**만 넣는다(현재 Phase 0-6 모델이 `plan-task` 의 Step 0-4 와 다름을 명시).
   **전면 재작성은 W-026 의 S25 로 신설됐다.**
   Q3 답신의 근거: *"전면 재작성을 W-025 에 넣지 않는다. 이미 크고, 이 파일은 활성 참조 2곳이라
   잘못 고치면 스킬 둘이 깨진다."* 그리고 **배너가 '영구 노란 경고' 가 되지 않는 이유는
   추적 항목(S25)이 함께 생기기 때문**이다 — 항목 없는 배너였다면 기각됐을 것이다.
6. `25-25` `mcp-builder/SKILL.md:134, :223` 의 존재하지 않는 CLI(`claude mcp restart` ·
   `claude mcp status`) 제거 → `claude mcp --help` 실행 지시로 대체(D-32 2행).
   **복제하지 않으면 낡을 수 없다** 가 이 처방의 전부다 — 다른 명령으로 바꿔 적지 마라.

### 금지사항
- `absoluteProhibitions` 전체.
- **`task-tools-fallback.md` 의 내용 수정.**
- `agent-creator`·`skill-creator` 본문 수정 — 그쪽은 S11(픽스처 테스트)이 다룬다.
- 스킬 **개수** 변경(19 유지). `agent-teams` 제거는 v3.0.0(S22)이다.
- `mcp-builder` 에 다른 CLI 사용법을 새로 적는 것.

### 완료 조건
- **G28** green: `ls plugins/common/skills | wc -l` == `find … -iname SKILL.md | wc -l` == 19.
  (4번 이관을 하지 않았다면 이 게이트는 20 vs 19 로 **fail** 한다 — 그것이 정상 신호다.)
- **G30** green: `mcp-builder/SKILL.md` 에 하드코딩된 `claude mcp <subcommand>` 문자열 0건.
- **G24** green: `references/` 잔존 파일 전부가 어떤 SKILL.md 에서 참조된다.
- `verify-done.sh` §6(문서 카운트) green — 스킬 19 유지.

---

## S3 — 에이전트 본문 축약 · 폴백 (C 트랙 · 워커)

> **읽기 집합**: 에이전트 8종의 worktree 절 + `enforce-structure.md` 전문 +
> `rules/parallel-worktree.md` ≈ **10 파일**. 부분 읽기 가능.

### 전제 (변경 금지)
- `rules/parallel-worktree.md` **본문** — 이것이 SSOT 다. 에이전트를 축약한다고 규범을 늘리지 마라.
- 에이전트 8종의 **다른 절** — worktree 복귀 프로토콜 4줄만 대상이다.
- S1 이 끝나 있어야 한다(같은 파일을 만진다 — 8종 중 다수가 겹친다).

### 이번 범위
1. `25-20` worktree 복귀 프로토콜 4줄 → **한 줄 참조로 축약**(D-27). 대상 8종:
   `backend/implement-api` · `backend/optimize-logic` · `backend/write-api-tests` ·
   `dev/fix-bugs` · `dev/write-tests` · `dev/sync-docs` · `dev/implement-code` ·
   `dev/generate-boilerplate`.
   **8종 전부 이미 `(규칙: rules/parallel-worktree.md)` 한 줄 포인터를 갖고 있다** —
   4줄을 지우면 포인터만 남는다.
2. `25-27` `dev/enforce-structure.md` **우아한 폴백**(D-32 4행):
   `project-structure.yaml` · `governance-check.py` 가 없으면 **그 사실을 보고하고 건너뛴다**.
   소비자 프로젝트의 파일이므로 존재 검사가 답이 아니다(북극성 직결).
   "Hook 연동" 절은 실재하지 않는 훅을 서술하므로 삭제한다.

### 금지사항
- `absoluteProhibitions` 전체.
- **`rules/parallel-worktree.md` 수정** — S1 의 예외 사유 1줄 외에는 이 배치에서 손대지 않는다.
- 축약 대상 8종에 `isolation: worktree` 를 추가·삭제하는 것(S1 의 몫).
- `enforce-structure` 에 새 파일 컨벤션을 발명해 넣는 것.

### 완료 조건
- **G-D27** green: 8종에서 4줄 프로토콜 문자열 0건 ∧ 포인터 한 줄은 8종 전부에 존재.
- **G31-a**(결정적 절반) green: `enforce-structure.md` 에 폴백 문장이 존재하고
  "반드시 읽기" 류의 필수 입력 서술이 0건.
- `verify-done.sh` §2·§7 green.

> **⚠ 이 Stage 의 알려진 한계** — D-27 축약 후 에이전트는 복귀 프로토콜을
> `rules/parallel-worktree.md` **경로 문자열**로만 안다. 그 경로는 소비자 프로젝트의 cwd 에서
> 해석되지 않고, D-21 이 이 규범을 `conditional` 로 내리므로 서브에이전트 컨텍스트에
> 주입되지도 않는다. **이 포인터는 축약 이전부터 존재했으므로 회귀는 아니지만**, 축약으로
> 인해 "포인터가 유일한 전달 수단" 이 된다. 컨트롤에 보고할 사항이며,
> 해소하려면 포인터를 `${CLAUDE_PLUGIN_ROOT}/rules/parallel-worktree.md` 로 절대화해야 한다.

---

## S4 — 규범 티어 선언 (C 트랙 · 워커) 【골격 Stage — 최소 검증 필수】

> **읽기 집합**: `rules/*.md` 13종 frontmatter + `session-start.py` 의 `load_rules`/
> `load_workflow_skill` ≈ **15 파일 / 약 45KB**. 규범 본문은 이 Stage 에서 읽지 않는다
> (frontmatter 만 추가하고 내용은 S5·S6 의 몫).
>
> **골격 Stage 다.** 스키마·설정·실행 구조라 테스트가 붙기 어렵고 그냥 넘어가기 쉽다.
> 여기서 결함이 나면 S5~S8 을 전부 되돌린다. 그래서 **최소 검증을 완료 조건에 못박았다.**

### 전제 (변경 금지)
- 규범 파일의 **본문** — 이 Stage 는 frontmatter 만 추가한다. 한 글자도 지우지 않는다.
- `rules/tool-usage-priority.md` — 삭제는 S5 다. 이 Stage 에서는 `tier: deleted` 를 쓰지 말고
  **현행 배정대로 frontmatter 를 붙인 뒤 S5 가 파일째 지운다**(중간 상태에서 게이트가 일관되게).
- `load_workflow_skill()` 의 frontmatter 제거 로직(`session-start.py:277-289`) — **참고 구현**이다.

### 이번 범위
1. `25-11` 규범 13종에 frontmatter 추가. 배정은 `01-policy.json` `ruleTiers.assignments` 그대로:
   ```yaml
   ---
   tier: core | conditional | reference
   activates: <conditional 인 경우 감지 신호>
   ---
   ```
2. `session-start.py` 의 **`ALWAYS_RULES` 하드코딩 리스트 제거**. 훅이 `rules/` 를 스캔해
   frontmatter 의 `tier` 를 읽어 core 를 주입하고, `conditional` 은 신호가 있을 때만 주입하며,
   `reference` 는 주입하지 않고 **색인 한 줄**만 남긴다.
3. **【검수 추가 · O3】 `load_rules()` 에 frontmatter 제거를 추가한다.**
   현재 `load_rules` 는 파일을 통째로 읽는다(`session-start.py:230`). 제거하지 않으면
   12종 × 약 40B ≈ **480B 가 예산 걸린 페이로드에 순증**한다.
4. **같은 커밋에서** `rules/CHECKSUMS.sha256` 과 `docs/architecture/rules/MIRROR.sha256` 재생성.
   frontmatter 추가로 13개 sha256 이 전부 바뀐다.
5. `reference` 티어의 색인 한 줄을 **어디에 둘지** 결정하고 구현한다.
   손으로 쓴 목록이면 D-23 의 "열거 금지"에 걸리므로, **frontmatter 의 한 필드
   (예: `indexLine:`)에서 생성**하는 것을 권고한다.

### 금지사항
- `absoluteProhibitions` 전체.
- **규범 본문 수정·삭제** — 축약(S6)·삭제(S5)는 다른 Stage 다.
- `CHECKSUMS.sha256` / `MIRROR.sha256` 를 **다음 커밋으로 미루는 것** — 그 커밋이 §7 red 다.
- `reference` 색인 줄을 손으로 유지하는 목록으로 만드는 것.
- 예산 게이트(§16) 신설 — S8 이다.

### 완료 조건 (골격 최소 검증 — 전부 필수)
- **G19** green(되돌려-FAIL): 규범 파일 하나를 임시로 추가하고 `tier` 를 빼면 검사가 fail 하고,
  되돌리면 pass 한다. **아직 §16 이 없으므로 스탠드얼론 검사 스크립트로 실증한다.**
- **G21** green: `conditional` 규범이 신호 없는 세션에서 주입되지 않고, 신호 있는 세션에서
  주입된다 — `load_rules()` 를 두 조건으로 직접 호출해 바이트 수 차이로 실증.
- **G-INJ** 측정 기록: 이 Stage 직후의 core 총합·WORKFLOW 바이트를 **보고서에 남긴다**.
  S6 축약의 before 값이 된다. frontmatter 순증이 0 임을 이 수치로 증명한다.
- `verify-done.sh` §7 green (CHECKSUMS 집합 동등 + 미러 동기).
- `pytest` green — `session-start.py` 테스트가 `ALWAYS_RULES` 제거로 깨지지 않는지 확인
  (실측: `grep -rn ALWAYS_RULES --include=*.py .` → 훅 파일 2곳뿐, 테스트 참조 0건).

---

## S5 — 규범 삭제 · 소비자 중립화 (C 트랙 · 워커)

> **읽기 집합**: `tool-usage-priority.md`(정본+미러) · `agent-system.md`(정본+미러) ·
> `ssot.md`(정본+미러) · `mcp-usage.md`(정본+미러) · `docs/conventions/rules-mirror.md` ·
> `AGENTS.md` 해당 블록 ≈ **10 파일 / 약 50KB**.

### 전제 (변경 금지)
- S4 가 끝나 있어야 한다(frontmatter 가 있어야 티어 기반 주입이 성립).
- `AGENTS.md` 는 **생성물**이다. 직접 편집 금지 — `scripts/export-harness.sh` 로 재생성한다.
- 미러(`docs/architecture/rules/`)는 정본을 **설명**할 뿐 재정의하지 않는다. 이 원칙 유지.

### 이번 범위
1. `25-12` **`plugins/common/rules/tool-usage-priority.md` 삭제**(D-18, 573B).
   호스트 bypass 모드의 시스템 프롬프트가 정반대를 지시한다(§9.2(a) 실측).
2. **【검수 추가 · E9-1】 `docs/architecture/rules/tool-usage-priority.md` 도 삭제.**
   정본만 지우면 `sync-rule-mirror.sh` 가 짝 없는 미러를 만나 §7 red 다.
3. `25-12` `rules/agent-system.md` 의 "Agent Selection by Keyword" 표 제거(D-18).
   미러 `docs/architecture/rules/agent-system.md:65-85` 의 "3. 에이전트 키워드 매핑" 도 함께
   (미러가 정본을 재정의하는 사례 — T1 F5 권고).
4. `25-12` `using-claude-code-kit/SKILL.md` 의 "Skill Trigger Map"(L28-43) ·
   "Agent Selection"(L45-55) 두 표 제거. 킷 고유 체인과 Work 시스템 규약은 유지.
   **주의**: 두 표를 지워도 WORKFLOW 는 4,816B 로 예산 2,048B 의 2.35배다(`00-REVIEW.md` E2) —
   컨트롤 Q2 답신에 따라 추가 조치가 필요하다.
5. `25-13` **소비자 중립화**(D-19):
   - `rules/ssot.md` — TypeScript 경로·import 예시를 언어 중립 원칙으로 축약(정본 + 미러)
   - `rules/mcp-usage.md` — `## NotebookLM Rules` 절 제거(정본 :65-71 + 미러 :157-170).
     같은 파일 6줄 위의 "never assume a server is present" 와 자기모순이었다
6. **【검수 추가 · E9-2】 `docs/conventions/rules-mirror.md:1-3` 의 숫자 갱신**:
   `(13)` → `(12)`, `(9)` → `(8)`, "remaining four" 는 유지(4종 그대로).
7. **【검수 신규 발견 — Q2 의 파생】 `export_harness.py` 의 분류표에서 제거한다.**
   `tool-usage-priority` 는 `PORTABLE`(`plugins/common/hooks/export_harness.py:266`)에 등재돼 있다.
   **파일만 지우면 `ghosts` 에 잡혀 `ClassificationError` 를 raise 하고 §11 이 red 다**
   (`export_harness.py:404-406, :504-510` — 에러 메시지 자신이 처방을 말한다:
   *"삭제·개명된 룰이다. PORTABLE / NOT_PORTABLE에서 제거하라"*).
   **설계문서 §9.4 의 연쇄 영향 목록에 이 파일이 없다.**
8. **연쇄 재생성**(§9.4 + 검수 E9 + 위 7번) — **같은 커밋에서**:
   - `rules/CHECKSUMS.sha256`
   - `docs/architecture/rules/MIRROR.sha256` (`scripts/sync-rule-mirror.sh --regenerate`)
   - `AGENTS.md` **두 블록 모두** (`cck:` rules + **`cck2:` conventions** — 6번이 conventions 를
     바꿨으므로 두 번째 블록도 대상이다)
   - `packaging/targets.json` 컴포넌트 실측
   - **카운트 주장 문서는 이 Stage 에서 고치지 마라** — 아래 주의 참조

### ⚠ 규범 수는 13 → 12 → **13** 이다 (Q2 답신의 파생)

설계문서 §9.4 는 *"규범 수가 13 → 12 로 바뀌므로"* 를 전제로 연쇄 영향을 나열했다.
**Q2 답신이 `untrusted-text.md` 를 신설(S24)하므로 최종 개수는 13 으로 되돌아온다.**

- 이 Stage 직후는 **중간 상태 12** 다. 이 상태로 카운트 주장 문서를 12 로 고치면
  S24 이후 다시 틀린다.
- **카운트 주장(`rules (13)`)은 건드리지 않는다** — 최종값이 같기 때문이다.
- 다만 `docs/conventions/rules-mirror.md` 는 **세 숫자 중 둘이 바뀐다**:
  `(13)` 유지 · `(9)` → `(8)` · `remaining four` → **`five`**
  (미러 없는 규범이 4 → 5. `untrusted-text` 는 미러를 만들지 않는다).
- S5 와 S24 는 **같은 릴리스(v2.18.0) 안에** 있어야 한다. 중간 상태로 릴리스하면
  문서 카운트 게이트가 red 다.

### 금지사항
- `absoluteProhibitions` 전체.
- **`AGENTS.md` 직접 편집** — 생성물이다.
- 규범 **축약**(D-21 의 `abridge: true` 대상) — S6 이다. 이 Stage 는 **삭제와 중립화**만.
- `sync-rule-mirror.sh --regenerate` 를 돌리고 미러 내용은 손대지 않는 것 —
  체크섬은 형식 동기화이지 **사실 정확성이 아니다**(D-32 3행).

### 완료 조건
- `ls plugins/common/rules/*.md | wc -l` == **12**(중간 상태) ∧ `ls docs/architecture/rules/*.md | wc -l` == 8.
- `grep -rn "NotebookLM" plugins/common/rules docs/architecture/rules` → 0건.
- **G13** green: `ssot.md` 정본·미러에 언어 종속 토큰(`.ts`·`import {`·`@/config`·`src/infrastructure`) 0건.
- `grep -n "tool-usage-priority" plugins/common/hooks/export_harness.py` → **0건**(분류표에서 제거됨).
- `scripts/export-harness.sh --check` green (두 블록 모두) — 분류표를 안 고쳤으면 여기서 raise 한다.
- `verify-done.sh` §7·§11 green.
- **§6(문서 카운트)은 이 Stage 단독으로는 green 이 아닐 수 있다** — 최종값 13 은 S24 가 만든다.
  S5+S24 를 합친 뒤 green 인지로 판정한다.

---

## S24 — `untrusted-text.md` 규범 신설 + interop 조건부화 (C 트랙 · 워커) 【Q2 답신 · 신설】

> **읽기 집합**: `using-claude-code-kit/SKILL.md`(111행) + `export_harness.py` 분류표 +
> `docs/conventions/rules-mirror.md` ≈ **5 파일**. 작다.
> **분해 근거**: S5(삭제·중립화)와 성격이 반대다 — 저쪽은 걷어내고 이쪽은 옮겨 심는다.
> 되돌림 단위가 달라야 하므로 별도 커밋.
>
> **왜 이 Stage 가 생겼나.** 검수는 WORKFLOW 예산 2,048B 가 처방으로 도달 불가함을 보이고
> (실측 4,816B) `비신뢰 텍스트 취급` 절을 **reference 티어로 내리는 안**을 권고했다.
> 컨트롤은 이를 **기각**하고 (d)를 냈다 — *"이 절은 애초에 WORKFLOW 에 있으면 안 되는 것이다.
> 자기 제목이 호스트 무관 공통 규율이라고 말한다."* **core 로 올린다.**
> 검수가 우려한 보안 현저성 하락은 **발생하지 않는다**(core 는 상시 주입).

### 전제 (변경 금지)
- S4(티어 선언)·S5(삭제·중립화) 완료가 전제. 새 규범 파일도 `tier` frontmatter 를 갖는다.
- **절의 내용을 다시 쓰지 않는다.** 이 Stage 는 **이동**이지 재작성이 아니다.
  내용을 손대면 되돌림 단위가 흐려지고, 축약은 S6 의 몫이다.
- `load_rules()` 의 frontmatter 제거 로직(S4 에서 추가)이 이미 있어야 한다.

### 이번 범위
1. `using-claude-code-kit/SKILL.md` 의 `## 비신뢰 텍스트 취급 (untrusted text)` 절
   (**2,152B**, 헤딩 포함 실측)을 **`plugins/common/rules/untrusted-text.md`** 로 옮긴다.
   frontmatter: `tier: core`.
2. **【검수 신규 발견】 `export_harness.py` 의 `PORTABLE` 에 사유와 함께 추가한다.**
   어느 분류표에도 없는 규범은 `unknown` 에 잡혀 `ClassificationError` 를 raise 하고
   §11 이 red 다(`export_harness.py:397-404, :496-503`).
   `PORTABLE` 이 맞는 이유는 절 자신이 선언한다 — *"이 절은 툴 중립이다.
   Claude Code·Codex·Antigravity 등 어떤 호스트에서도 동일하게 적용한다."*
3. interop 2절을 **conditional 티어**로 옮긴다:
   `## 메모리 MCP와 함께 쓸 때`(921B) · `## superpowers와 함께 쓸 때`(638B).
   각 절의 `activates` 신호를 frontmatter 에 선언한다(메모리 MCP 도구 감지 / superpowers 설치 감지).
4. **연쇄 재생성** — 같은 커밋: `rules/CHECKSUMS.sha256` ·
   `docs/architecture/rules/MIRROR.sha256` · `AGENTS.md`(`cck:` rules 블록 — 새 PORTABLE 규범이
   들어간다) · `packaging/targets.json` 컴포넌트 실측.
5. `docs/conventions/rules-mirror.md` 의 세 숫자 정정: `(13)` 유지 · `(9)`→`(8)` ·
   `remaining four`→`five`. (conventions 가 바뀌므로 `AGENTS.md` `cck2:` 블록도 재생성.)
6. `plugins/common/rules/VERSION`(현재 `1.4.0`) 을 올릴지 판단한다.
   이 값이 AGENTS.md 마커 줄 `rules-v1.4.0` 에 직접 들어간다(`export_harness.py:410-429`).
   **게이트가 강제하지 않으므로** 올리지 않기로 하면 그 근거를 커밋 메시지에 남긴다.

### 금지사항
- `absoluteProhibitions` 전체.
- **옮기는 절의 내용 수정** — 이동만. 축약은 S6.
- `untrusted-text.md` 의 해설본 미러 생성 — 미러 없는 규범 4종의 선례를 따른다(이제 5종).
- `export_harness.py` 의 분류표를 안 고치고 커밋하는 것 — §11 이 raise 한다.
- 남은 WORKFLOW 절(체인·Work 감지·preamble)을 건드리는 것.

### 완료 조건 (골격 성격 — 최소 검증 필수)
- `ls plugins/common/rules/*.md | wc -l` == **13** (12 + 신설 1).
- **G19** green: 새 파일이 `tier: core` 를 선언한다.
- **G-UT** green: `grep -c "비신뢰 텍스트" plugins/common/skills/using-claude-code-kit/SKILL.md` → 0
  ∧ `plugins/common/rules/untrusted-text.md` 존재.
- **G21** green(interop): 신호 없는 세션에서 interop 절이 주입되지 않는다.
- `scripts/export-harness.sh --check` green — 분류표 누락이면 여기서 raise 한다.
- **WORKFLOW 잔여 측정 기록**: 예상 **1,107B**(preamble 627 + Workflow Chain 319 +
  Work System Detection 161). 보고서에 실측값을 남긴다 — S6 의 예산 계산 입력이다.
- `verify-done.sh` §6·§7·§11 green (규범 13 복귀로 카운트가 맞는다).

---

## S6 — 규범 축약 **+ §16 예산 게이트 신설** (C 트랙 · **컨트롤 판단 + 워커 실행**) 【같은 커밋】

> **읽기 집합**: core 6종 정본(13,282B) + 미러 6종 + `verify-done.sh` §15 인접부
> ≈ **14 파일 / 약 62KB**. 상한에 가깝다.
> **분해 근거**: S5·S24 와 합치면 미러·AGENTS.md·conventions 까지 읽기 집합에 들어와 넘친다.
> 축약은 **판단 작업**이라 되돌림이 파일 복원이 아니라 판단의 재수행이므로 반드시 별도 커밋.
>
> **【Q1 답신】 구 S8(§16 게이트)을 이 Stage 에 흡수했다.** 예산을 맞추는 축약과
> 그 예산을 검사하는 게이트가 **같은 커밋**에 있어야 중간 red 가 없다.

### 전제 (변경 금지)
- 축약해도 **규범의 규범성**은 유지된다. 게이트를 가리키는 문장(`definition-of-done` →
  `verify-done.sh`)은 남는다.
- 미러(`docs/architecture/rules/`)는 **축약 대상이 아니다** — 정본이 짧아지고 해설본이 긴 것이
  이 레포의 설계다. **축약 전 원문의 보존처가 미러다**(위험 완화책).
- S4·S5 완료가 전제.

### 이번 범위
1. `25-15` core 배정 6종 중 `abridge: true` 4종 축약:
   `definition-of-done`(3,648B) · `loop-engineering`(3,029B) · `code-quality`(1,835B) ·
   `ssot`(1,306B, S5 에서 중립화 완료분).
   **목표: core 6종 총합 13,282 → 5,857B 이하** (현재의 44.1%).

   > **주의 — 컨트롤 스케치보다 287B 타이트하다.** Q2 답신은 예산 9,216B 의 구성을
   > *"core 6종 축약 6,144 + 비신뢰 2,071 + WORKFLOW 잔여 ~1,000"* 으로 스케치했다.
   > 검수 실측으로 다시 풀면:
   > ```
   > 9,216 − untrusted-text 2,152 − (WORKFLOW 1,107 + 래퍼 38) − (core 래퍼·구분자 62) = 5,857
   > ```
   > 총량 상한이므로 배분은 유연하다 — 다른 항목을 더 줄이면 core 여유가 늘어난다.
   > 그러나 **다른 항목을 줄이지 않는 한 core 6종의 실질 여유는 5,857B 다.**
2. `25-14` **§16 주입 예산 게이트 신설 — 위 1번과 같은 커밋.**
   - 다음 빈 번호는 **16**. **§12 는 영구 결번.**
   - **예산은 총량 하나**다(Q2 답신): `alwaysInjectedMaxBytes = 9216`.
     **core/WORKFLOW 로 나누지 않는다** — 절이 파일 사이를 옮겨다니면 개별 상한은
     **이동만으로 통과시킬 수 있다**(게이밍). 검수가 제안한 `perRuleMaxBytes`(X1)도
     같은 이유로 기각됐다.
   - 함께 검사: **모든 규범 파일이 `tier` 를 선언했는가**(누락 = fail) — §9.3 결함 1 봉쇄.
   - **예산 수치를 셸에 하드코딩하지 마라** — 데이터에서 읽는다(`evals/policy.json` 의
     `_comment`: *"산문에 티어 목록이나 숫자를 중복 기재하지 말 것"*).
   - **`enforceFail` 플래그를 두지 않는다** — 처음부터 fail(Q1 답신).
3. `25-15` **【D-25】 `AskUserQuestion` 하드코딩 4종을 역할 서술로 치환**:
   `agent-delegation-chain.md:45` · `loop-engineering.md:40` · `planning-protocol.md:16,37` ·
   `planning-check.md:17` (+ 미러 5곳: `agent-delegation-chain.md:97` ·
   `planning-protocol.md:67,81,83` · `planning-check.md:110`).
   치환 문구는 **툴이 아니라 역할**: *"사용자에게 선택지를 제시하고 답을 받는다
   (호스트가 제공하는 수단으로)"*. 헤드리스·비대화형 호스트(Codex `exec`, 워커 디스패치,
   `-p` eval)에는 그 툴이 없다 — 이 검수 세션 자체가 실측 사례다.
4. 축약 후 **연쇄 재생성**: CHECKSUMS · MIRROR · AGENTS.md `cck:` 블록.

### 금지사항
- `absoluteProhibitions` 전체.
- **미러(`docs/architecture/rules/`)를 함께 축약하는 것** — 원문 보존처가 사라진다.
- **개별 파일 상한을 게이트에 넣는 것** — Q2 답신이 명시적으로 제거를 지시했다(게이밍 가능).
  다만 **판단 지침으로는** 어떤 core 규범도 현재 크기의 30% 미만으로 줄이지 마라(검수 권고 하한).
  게이트가 아니라 컨트롤의 판단 기준이다.
- **`untrusted-text.md` 축약** — S24 가 방금 옮긴 것이다. 축약 대상은 core **6종**이다.
  (총량 상한이라 여기를 깎아도 통과하지만, 그러면 Q2 의 결정 근거인 '보안 현저성 유지' 가 무너진다.)
- **eval 재실행 없이 완료 선언** — 아래 완료 조건 참조.
- **§12 번호 사용.**
- **게이트만 만들고 축약을 다음 커밋으로 미루는 것** — Q1 답신이 막으려 한 상태다.

### 완료 조건
- **G18** green(되돌려-FAIL): `alwaysInjected` 총량 ≤ **9,216B** 이고,
  규범 하나에 더미 2KB 를 붙이면 §16 이 실제로 red, 되돌리면 green.
- **G19** green(되돌려-FAIL): `tier` 선언을 빼면 fail.
- **G25-b** green: `grep -rn "AskUserQuestion" plugins/common/rules docs/architecture/rules AGENTS.md` → 0건.
- **G-EVAL** green(**이 Stage 의 유일한 실증 안전망**): eval 전량 1회 실행 + 기준선 대비 회귀 0.
  예산 게이트는 **크기만 보고 행동은 보지 않는다.** 규범 축약은 시나리오 추가보다 행동 영향이
  크므로 `evals/policy.json` 의 `regenerationCadence` 관례를 그대로 적용한다.
- `verify-done.sh` 전 게이트 green.

---

## S7 — v2.18.0 릴리스 (C 트랙 · 컨트롤)

> **읽기 집합**: `plugin.json` · `CHANGELOG.md` 상단 · `packaging/targets.json` ≈ **4 파일**.

### 전제 (변경 금지)
- S1~S6 전부 완료. **하나라도 미완이면 릴리스하지 않는다** — 배포물이 중간 상태로 나간다.
- 버전은 `scripts/bump-version.sh <version>` 으로 올린다. **수동으로 SSOT 를 직접 고치지 마라**
  (`docs/conventions/release-process.md:9` — v2.15.0 에서 실제로 밟은 실수를 막는 스크립트).

### 이번 범위
1. `bump-version.sh 2.18.0` — SSOT + 타겟 매니페스트 재생성이 한 번에.
2. `CHANGELOG.md` 에 `## [2.18.0]` 항목.
3. `packaging/targets.json` 의 `_skillsCountNote` — **S2 의 이관을 실제로 했을 때만**
   "해소됨" 으로 갱신한다. 안 했으면 21→20 만 기록하고 해소 주장을 쓰지 마라
   (`00-REVIEW.md` L5 — 실측 기록 필드에 실측되지 않은 주장을 넣지 않는다).
   **주의**: §10.4 는 이 갱신을 27-4 시점으로 배정했다. 이 Stage 에서 하면 그 배정과 어긋나므로
   컨트롤이 어느 쪽인지 명시해야 한다.
4. 태그: `git tag -a v2.18.0 <commit> -m "v2.18.0"`. **푸시는 컨트롤 승인 후.**

### 금지사항
- `absoluteProhibitions` 전체 (특히 `git push` · `git push --tags`).
- `plugin.json` 의 `version` 을 손으로 편집하는 것.
- `build-targets.py --write` 를 빠뜨리는 것 — v2.15.0 에서 실제로 밟았고 §14 가 잡았다.

### 완료 조건
- `verify-done.sh` **전 게이트 green** (§6 이 plugin.json ↔ CHANGELOG 일치와 태그 존재를 검사).
- `python3 scripts/build-targets.py --check` green.

---

## S8 · S9 — **퇴역 번호** (Q1 답신으로 각각 S6 · S1 에 흡수)

> 이 두 번호는 **재사용하지 않는다.** `verify-done.sh` 의 §12 를 비워 두는 것과 같은 규약이다 —
> `03-gate-spec.md` · `04-handoff.md` 가 Stage 번호로 작업을 참조하므로, 번호를 재할당하면
> 그 참조가 조용히 다른 작업을 가리킨다. 새 작업은 다음 빈 번호(S24 · S25)를 쓴다.

| 구 Stage | 어디로 갔나 | 왜 |
| --- | --- | --- |
| **S8** §16 주입 예산 게이트 | **S6** 에 흡수 (C 트랙, 같은 커밋) | 예산을 맞추는 축약과 그 예산을 검사하는 게이트가 갈라져 있으면 중간에 red 인 상태가 생긴다 |
| **S9** §17 상호 참조 게이트 | **S1** 에 흡수 (C 트랙, 같은 커밋) | 검사 대상(dangling 8종)을 고치는 커밋과 같아야 승격 직후 green 이다 |

**근거는 W-024 선례다** — `tier2CoverageEnforceFail` 을 도입 즉시 fail 로 놓으며
*"이 배치가 유일한 갭을 같은 배치에서 메우므로 승격 직후 green 이다 …
**영구 노란 경고는 아무도 보지 않는다**"* 라고 적었다. 검수는 warn-first 정책 플래그를
권고했고 컨트롤이 이 선례를 근거로 기각했다. 플래그를 두면 **승격을 잊을 자유**가 생긴다.

**예외 하나**: 탐지식 카운트 검사(25-17, S10)만 warn-first 로 남는다 —
제외 경로 규칙의 정확도가 미지수이기 때문이며(E8), **근거가 다르므로 취급도 다르다.**
그 대신 승격 조건이 `01-policy.json` 에 명시돼 있다.

---


## S10 — 카운트 주장 탐지식 검사 전환 (B 트랙 · 워커) 【warn-first — Q1 의 유일한 예외】

> **읽기 집합**: `check_doc_counts.py` + site 4종 + `docs/conventions/rules-mirror.md`
> ≈ **7 파일**.
> **전제 순서**: S2·S5·**S24** 완료(카운트를 바꾸는 항목. S24 가 규범 수를 13 으로 되돌린다).
>
> **【Q1 답신 — 예외】** §16·§17 은 처음부터 fail 이지만 **이것만 `enforceFail=false`** 다.
> 이유: 동결 기록(`site/content/posts/**` 등)을 빼는 **제외 경로 규칙의 정확도가 미지수**이기
> 때문이다(E8). *"근거가 다르므로 취급도 다르다."*
> **단, 승격 조건을 명시해야 한다** — 조건 없는 warn 은 컨트롤이 기각한 "영구 노란 경고" 자체다.

### 전제 (변경 금지)
- **동결 기록은 고치지 않는다**(D-29, 감사 수용 기준 5). `site/content/posts/**` 의
  "169개 유닛 테스트"(현재 455) 같은 값은 **발행 시점 스냅샷**이다.
- 열거를 다시 만들지 않는다(D-23) — 제외는 **파일 목록이 아니라 경로 규칙**으로.

### 이번 범위
1. `25-17` 카운트 주장을 **패턴으로 탐지**하고, 탐지됐는데 검사되지 않는 주장이 있으면 fail.
2. **【검수 추가 · E8】 스코프를 규칙으로 명시**:
   - 포함: `plugins/**/*.md` · `site/content/*.md`(최상위 파일만) · `README.md` ·
     `plugins/common/README.md` · `CLAUDE.md` · `docs/conventions/*.md`
   - 제외(경로 규칙 한 줄): **날짜가 박힌 기록 디렉토리는 동결** —
     `site/content/posts/**` · `docs/specs/**` · `docs/works/**` · `CHANGELOG.md`
   - 이러면 `about.md`/`about.en.md` 가 **등록 없이** 들어온다(T5 F-16/17 이 게이트 밖이었던 이유).
3. **【검수 추가 · E7】 탐지 전환과 같은 커밋에서 기존 오기재를 전부 정정**한다.
   현재 최소 8곳 — `01-policy.json` `gates.countClaimDetection.knownStaleClaims` 참조.
   **주의**: `docs/conventions/rules-mirror.md` 의 세 숫자는 **S24 가 이미 고쳤다**.
   여기서 다시 고치지 말고 값이 맞는지만 확인한다(rules **13** 유지 · mirrors 8 · remaining **five**).
4. **`enforceFail=false` + 승격 조건 명시**(Q1 답신). 조건은 `01-policy.json`
   `gates.countClaimDetection.promotionCondition` 에 있다 —
   *"제외 경로 규칙이 한 릴리스 동안 동결 기록에 대한 오탐 0건으로 관측되면 true 로 올린다.
   코드 변경 불필요 — 데이터 플래그만 바꾼다."*
   플래그와 조건을 **함께** 넣어라. 조건 없는 플래그는 기각 사유다.

### 금지사항
- `absoluteProhibitions` 전체.
- **제외 대상을 파일 목록으로 관리하는 것.**
- `site/content/posts/**` 의 숫자를 "고치는" 것.
- 탐지만 만들고 기존 오기재를 남기는 것 — 그 상태로는 게이트가 green 이 될 수 없다.

### 완료 조건
- **G23** green: 새 문서에 카운트 주장을 추가하면 목록 수정 없이 검사 대상에 포함된다(되돌려-FAIL).
- **G23-b** green: 탐지 결과 미검사 주장 0건.
- `grep -rn "16 스킬\|16 Skills" site/` → 0건.
- `verify-done.sh` §6 green.

---

## S11 — eval · 스크립트 인프라 정비 (B 트랙 · 워커)

> **읽기 집합**: `evals/run.py` 관련부 + `check_eval_coverage.py` + 로더 보일러플레이트 12곳 +
> 경로 헬퍼 4곳 + `evals/README.md` ≈ **12 파일**. 상한 근처.
> **분해 여지**: 컨텍스트가 빡빡하면 S11a(어서션 레지스트리 + 로더 헬퍼) / S11b(경로 헬퍼 +
> check_eval_coverage 목록화 + 픽스처 테스트)로 쪼갠다. 서로 독립이다.

### 전제 (변경 금지)
- **`evals/run.py` 전체를 모듈로 쪼개지 않는다**(D-12) — 결합도 0 이 이 코드베이스의 최대 자산.
- **하이픈 파일명을 개명하지 않는다**(D-14) — 약 40개 파일이 참조하고 다수가 불변 기록.
- **경로 봉쇄 헬퍼를 공용 라이브러리로 통합하지 않는다**(D-15) — 훅은 디렉토리를 넘는 import 가
  불가능하다. 구현은 4벌, **계약만 하나**.
- **`hooks/utils.py` 공유를 키우지 않는다**(D-16) — 2.12.1 의 "훅 4종이 조용히 죽어 있었다" 사고.

### 이번 범위
1. `25-7` **어서션 계약 레지스트리 통합**(D-13 + §11.2(a) 확정): `{타입: (필수필드, 채점함수)}`
   딕셔너리 하나를 두고 스키마 검증과 디스패치가 같은 표를 읽는다. 동기화 테스트가 아니라
   **레지스트리** — zero-debt 는 "한 곳뿐" 이다. 대상 9종.
2. `25-8` `spec_from_file_location` 보일러플레이트 **12벌 → 1벌**(D-14).
   `load_module_by_path(path)` 헬퍼. `check_eval_coverage.py` 의 3.10 dataclass /
   `sys.modules` 주의사항도 그 헬퍼 한 곳에만.
3. `25-9` 경로 봉쇄 헬퍼 **이름을 `_resolve_in_repo` 로 통일**(현재 3가지 이름 4벌) +
   **공유 적대 케이스 표**(절대경로 · `..` · 심링크 · TOCTOU) 검증 데이터(D-15).
4. `25-10` `check_eval_coverage.py` 의 체크 4종을 **목록화**(F6).
5. `25-2` **eval 회귀 가드**(D-10): 전체 실행 전후의 `~/.claude.json` projects 수 비교,
   증가 시 경고. 추가 API 비용 0, 약 10줄.
6. `25-24` **`agent-creator`·`skill-creator` 템플릿 픽스처 테스트**(D-32 1행).
   **【검수 추가 · L7】** `verify-done.sh` §2 는 인라인 heredoc 이고 경로가 하드코딩돼 있으며
   `/skills/` 를 명시적으로 건너뛴다 — **"그대로 돌린다" 가 불가능하다.**
   처방: §2 의 frontmatter 검사 본문을 `scripts/check_agent_frontmatter.py` 로 **추출**해
   경로를 인자로 받게 하고, `verify-done §2` · CI · 픽스처 테스트 셋이 **같은 스크립트**를 호출한다.
   (`scripts/lint-shell.sh` 가 게이트와 CI 에 공유되는 것과 같은 관례라 정합적이다.)
   그리고 두 스킬 본문의 잘못된 계약도 함께 고친다 — 금지 필드 `permissionMode` 유도,
   존재하지 않는 `plugin.json` 의 `agents`/`skills` 필드 등록 지시, `plugins/{domain}` 전제,
   예제 frontmatter 의 `maxTurns` 누락, `argument-hint`/`allowed-tools` 미사용 필드.
7. `evals/README.md:3-5` 커버리지 과소 서술 정정(D-28 5행 — 배포물이 아니므로 B 트랙).

### 금지사항
- `absoluteProhibitions` 전체 (특히 **기준선 파일 덮어쓰기**).
- `evals/run.py` 를 모듈로 분할하는 것.
- 훅·스크립트 **파일명 변경**.
- 경로 헬퍼를 공용 모듈로 합치는 것.
- 픽스처를 `plugins/**` 아래에 두는 것 — 가짜 에이전트가 소비자에게 배포되고
  에이전트 수 33 이 깨진다.
- **하네스 심 추출** — S13(W-026)이다.

### 완료 조건
- **G13-a** green: 어서션 타입을 하나 추가할 때 **한 곳만** 고치면 스키마 검증과 채점이 함께 반영됨(실증).
- **G14** green: `grep -rn "spec_from_file_location" . | wc -l` == 1.
- **G15** green: 네 헬퍼가 동일한 적대 케이스 표를 통과하고 이름이 전부 `_resolve_in_repo`.
- **G29** green(되돌려-FAIL): `agent-creator` 템플릿으로 생성한 에이전트가 frontmatter 검사를 통과.
  템플릿을 일부러 깨면 fail.
- **G2** green(되돌려-FAIL): projects 수를 인위적으로 증가시키면 경고가 실제로 출력됨.
- `pytest` green · `verify-done.sh` 전 게이트 green.

---

## S12 — 문서 구조 정리 (B 트랙 · 컨트롤 + 워커)

> **읽기 집합**: `CLAUDE.md`(494행) + `docs/conventions/*.md` 7종 + `docs/superpowers/` 2종 +
> `scripts/work.sh` ≈ **12 파일**.
> **내부 순서**: S12a → S12b (같은 파일을 만진다).

### 전제 (변경 금지)
- **과거 Work 문서(W-001~W-004)의 상태 줄을 고치지 않는다**(D-29). 역사 기록이다.
- `docs/superpowers/` 2종의 **내용**은 완료 이력이다. 재배치만 하고 수정하지 않는다.
- `AGENTS.md` 는 생성물 — `cck2:` conventions 블록이 `docs/conventions/*.md` 를 임베드한다.

### 이번 범위 — S12a (컨트롤)
1. `25-19` **CLAUDE.md 인라인 6절 → `@docs/conventions/<file>.md` import 치환**(D-26).
   현재 `grep -n "@docs/conventions" CLAUDE.md` → 0건이고, `docs/conventions/README.md:5` 와
   `CHANGELOG.md`(W-022 R7)가 명시한 설계와 실물이 다르다.
   대상: `path-containment` · `no-gate-integration` · `lint-single-ruleset` · `rules-mirror` ·
   `shell-lint` · `release-process`. 그리고 `reference-vs-judgment.md` 참조를 **추가**한다
   (CLAUDE.md 에 내용이 전혀 없다 — 완전 누락).
   **드리프트 검사는 신설하지 않는다** — import 는 참조이지 사본이 아니다.
   이것이 네 번째 드리프트 게이트를 만들지 않는 올바른 해법이다.
2. `25-19` Release Checklist 를 `@docs/conventions/release-process.md` import 로 치환.
   이것으로 `bump-version.sh` 이전 수동 절차 지시가 자동 해소된다(T1 F8).
3. `25-19` Key Skills 표에 `brainstorming` 행 추가(T1 F9).

### 이번 범위 — S12b
4. `25-26` **【검수 O5 · Q4 답신으로 확정】** 미러 체크섬의 보장 범위를
   **`docs/conventions/rules-mirror.md` 에** 명문화한다(D-32 3행).
   *"체크섬은 형식 동기화이지 내용의 사실 정확성이 아니다."*
   Q4 답신: *"D-26 의 논리와 정확히 맞는다 — 내용은 `conventions/` 가 갖고 `CLAUDE.md` 는
   import 만 한다. CLAUDE.md 에 쓰면 25-19 가 지운다는 네 지적이 맞다."*
   import 를 통해 CLAUDE.md 에 반영되고 `AGENTS.md` `cck2:` 블록으로 전 하네스에 전파된다.
5. `25-26` 해설본 **사실성 1회 스윕**. **【검수 X8】 범위를 기계 확인 가능한 주장으로 한정**한다:
   카운트 · 경로 · 존재하는 구조명. 대표 대상은 `docs/architecture/rules/agent-system.md:7-29`
   의 "3-Tier Architecture"(v2.7.0 `284c801` 에 삭제된 5개 도메인 플러그인을 현재형으로 서술,
   스킬 수 "16"). 자연어 사실성 전반은 **대상 밖임을 명시**한다 — 무한하다.
6. `25-28` `docs/superpowers/` 2종을 `docs/specs/2026-04-21-superpowers-upgrade-{plan,design}.md`
   로 재배치(§11.2(c)). `YYYY-MM-DD-*` 규약과 맞고 **디렉토리가 사라지므로 오인 원천 자체가
   없어진다**. README 경고는 오인을 설명할 뿐 없애지 못한다.
7. `25-22` `scripts/work.sh complete <id>` 가 본문 `> Status:` 인라인 줄을 frontmatter 와
   동기화하게 한다(D-29). **다음부터 발생하지 않게** 하는 것이 목적이고 과거 4건은 그대로 둔다.
8. `AGENTS.md` 재생성(`cck2:` 블록 — conventions 가 바뀌었다).

### 금지사항
- `absoluteProhibitions` 전체.
- **W-001~W-004 문서 수정.**
- `docs/superpowers/` 파일 **내용** 수정.
- CLAUDE.md 에 미러 체크섬 caveat 를 쓰는 것(S12a 가 지운다 — Q4 답신 전이면 보류).
- import 치환용 **드리프트 게이트 신설**.

### 완료 조건
- **G25** green: CLAUDE.md 에 `docs/conventions/` 와 중복 선언된 절 0개.
- `grep -c "@docs/conventions" CLAUDE.md` ≥ 6 ∧ `grep -c "reference-vs-judgment" CLAUDE.md` ≥ 1.
- `ls docs/superpowers 2>/dev/null` → 없음.
- `grep -rn "3-Tier Architecture" docs/architecture/` → 0건.
- `scripts/export-harness.sh --check` green · `verify-done.sh` 전 게이트 green.

---

# W-026 — `control-loop` 스킬 (v2.19.0 권고 · `01-policy.json` 참조)

> **착수 전제**: W-025 전부 완료. §5 가 *"W-025 를 지금 방식으로 먼저 돌리는 것이 26-1 의
> 입력이다"* 라고 명시한다 — 프로토콜을 한 번 더 실사용 관측하고 그 관측을 재료로 쓴다.
> **스킬을 먼저 쓰고 나중에 맞추지 않는다.**

## S13 — 하네스 호출 심 추출 (워커)

> **읽기 집합**: `evals/run.py` 의 3개 결합점 인접부 + 테스트 ≈ **4 파일**.
> **분해 근거**: run.py 는 1,520행이지만 이 Stage 는 3개 지점만 만진다. 전문 정독 불필요.

### 전제 (변경 금지)
- **run.py 전체를 모듈로 쪼개지 않는다**(D-12). 나머지 7개 책임은 함께 변하는 것들이다.
- **Codex·Antigravity 구현을 이번에 만들지 않는다**(D-12) — 심만 판다.
- 어서션 채점 로직(S11 의 레지스트리) — 이 Stage 의 대상이 아니다.

### 이번 범위
1. `26-6` `Harness` 프로토콜 + `ClaudeCodeHarness` 단일 구현.
2. **【검수 L2 — 대상 확대】 결합점은 1곳이 아니라 3곳이다.** 전부 옮긴다:

   | 위치 | 내용 | 프로토콜 메서드(권고) |
   | --- | --- | --- |
   | `evals/run.py:1077` | `build_claude_command` | `run_scenario_cmd(agent, task)` |
   | `evals/run.py:1049` | LLM judge subprocess (`--model sonnet` 하드코딩) | `judge_cmd(prompt)` |
   | `evals/run.py:1304` | `shutil.which("claude")` 가용성 게이트 | `is_available()` |

   하나만 옮기면 "eval 은 Claude Code 만 구동한다" 는 자기모순이 그대로 남고,
   그 위에서 S21 이 README 에 파리티 문장을 쓰게 된다.

### 금지사항
- `absoluteProhibitions` 전체 (특히 **기준선 덮어쓰기**).
- run.py 모듈 분할.
- Codex/Antigravity 구현체 추가.
- **`--dry-run` diff 증명 없이 완료 선언.**

### 완료 조건
- **G16-b**(되돌려-FAIL 대체 증명): 추출 **전후로 전 시나리오 `--dry-run` 을 돌려 조립된
  명령 문자열의 diff 가 공집합**임을 증명한다. `evals/run.py:1383` 이 이미 `--dry-run` 을 지원한다.
- **G16** green: `claude` **CLI 호출·존재 검사**가 `ClaudeCodeHarness` 밖에 0건
  (문자열 스캔이 아니다 — `00-REVIEW.md` L2 / `03-gate-spec.md` G16 참조).
- 기준선 재생성 여부를 컨트롤이 판단(`regenerationCadence` 관례).
- `pytest` green · `verify-done.sh` 전 게이트 green.

---

## S14 — `control-loop` 규범 본문 (워커)

> **읽기 집합**: `rules/loop-engineering.md` + `docs/native-absorption.md` +
> W-025 실사용 관측 기록 + §4.2 시퀀스 ≈ **6 파일**. 새 파일을 쓰는 Stage 다.

### 전제 (변경 금지)
- **규범 본문은 운송을 모른다**(D-6). 프로토콜(역할 경계 · 4블록 계약 · 검증 · 통합)만 소유한다.
- **4블록 브리프에 기계 게이트를 두지 않는다**(D-9). 폐기된 `DELEGATION_SIGNAL` 과 다른 점은
  **소비자가 있다는 것** — 워커가 실제로 읽고 수행하며, 누락 시 에스컬레이션한다.
  소비자가 있는 계약은 게이트 없이도 산다.
- 스킬을 기획용·컨트롤용으로 나누지 않는다(D-5). 축은 *기획 대 컨트롤*이 아니라 **결정 대 조사**다.

### 이번 범위
1. `26-1` `plugins/common/skills/control-loop/SKILL.md` — 3페이즈 규범 본문:
   - **P1 조사·설계** — 위임 가능. *"없다 / 신설" 은 실측 뒤에만*
   - **P2 결정·브리프** — 컨트롤 전용. 4블록을 못 쓰면 P1 으로 되돌린다
   - **P3 디스패치·수신·통합** — 컨트롤 전용. **보고를 믿지 않고 게이트를 직접 실행**한다.
     main 병합은 컨트롤만
2. `26-7` **【D-30】 기준 커밋 고정·검증을 P3 규범 본문에 편입**한다. **운송 부록이 아니라 본문**이다 —
   어떤 운송을 쓰든 성립해야 하기 때문:
   - 컨트롤은 디스패치 전 기준 ref 의 **실제 커밋 해시**를 확인하고 브리프에 적는다
   - 워커는 착수 시 자기 HEAD 가 그 해시인지 확인하고, 아니면 **즉시 에스컬레이션**한다
   - 브랜치 이름(`main`)은 기준으로 쓰지 않는다 — 로컬 브랜치는 낡을 수 있다
3. P0 에스컬레이션 서술은 **툴 이름이 아니라 역할**로(D-25 와 같은 규율).

### 금지사항
- `absoluteProhibitions` 전체.
- **SKILL.md 본문에 `orca` 문자열을 쓰는 것** — 수용 테스트 5.
- 특정 운송(orca · ultracode · Task)의 명령·플래그를 본문에 적는 것.
- 4블록 브리프의 형식을 파싱하는 스크립트·게이트를 만드는 것(D-9).
- `agent-teams/SKILL.md` 수정 — S16 이다.

### 완료 조건
- **G5** green: `grep -c orca plugins/common/skills/control-loop/SKILL.md` → 0.
- **G26** green: 기준 커밋 고정·검증 문구가 **`SKILL.md` 본문**에 존재(부록 파일이 아니라).
- `verify-done.sh` §2 green (스킬 frontmatter · description 영문).

---

## S15 — 운송 부록 (워커) 【위치 확정: `docs/` — Q5 답신】

> **읽기 집합**: `control-loop/SKILL.md` + `agent-teams/SKILL.md` + §4.3 감지 사다리 ≈ **4 파일**.

### 전제 (변경 금지)
- **부록은 비규범이다.** 낡아도 스킬이 계속 동작해야 한다(D-6).
- 감지 사다리는 **전부 실패해도 `SQ`(단일 세션 순차)로 끝나 fail-open** 한다(§4.3).
- 규범은 `P` 하나다 — 어떤 운송이든 **4블록 브리프 · 병합 전 게이트 · main 은 컨트롤만**.

### 이번 범위
1. `26-2` 운송별 실행 레시피. 각 항목은 **감지 명령 + 최소 레시피**만 담는다.
   사다리: `orca CLI` → 네이티브 서브에이전트(`isolation: worktree`) → `ultracode` 안내 →
   단일 세션 순차.
2. **【검수 R4 · Q5 답신으로 확정】 부록은 `docs/` 에 둔다. 배포물(`plugins/`) 밖이다.**
   Q5 답신의 근거 셋: ① D-6 의 *"배포물 안 `orca` 0건"* 불변식 유지(실측 확인:
   `grep -rn orca plugins/ | wc -l` → **0**) ② 부록은 비규범이라 배포물에 실릴 이유가 없다
   ③ 소비자 대부분은 orca 를 쓰지 않으므로 배포물 크기만 늘린다.
   *"규범 본문이 '호스트가 제공하는 수단으로 위임하라' 로 자급하므로 부록 부재가 기능을 깨지 않는다."*
   `SKILL.md` 에는 **"운송 레시피는 레포 문서 참조" 한 줄**만 둔다.
3. **`G-D6` 을 결정적 게이트로 신설한다**(Q5 답신 — *"결정적 게이트로 채택한다"*).
   배포물 전체에 `orca` 0건. 수용 테스트 5 는 `SKILL.md` **한 파일만** 검사하므로
   부록이 `plugins/` 로 새어 들어가는 것을 못 잡는다 — `G-D6` 이 그 구멍을 막는다.
   현재 실측 0건이므로 **신설 즉시 green** 이다.

### 금지사항
- `absoluteProhibitions` 전체.
- **부록을 `plugins/` 아래 두는 것** — D-6 의 근거 불변식이 깨지고 `G-D6` 이 red 다.
- 부록의 내용을 **규범 본문으로 승격**시키는 것.
- 특정 운송의 존재를 전제하는 서술(감지 명령 없이 "orca 로 디스패치한다" 류).

### 완료 조건
- **G5** 재확인: `control-loop/SKILL.md` 의 `orca` 0건 유지.
- **G-D6** green(되돌려-FAIL): `grep -ril orca plugins/ | wc -l` → 0.
  `plugins/` 아무 파일에 `orca` 를 넣으면 red, 지우면 green.
- 부록의 각 항목이 **감지 명령**을 갖는다(레시피만 있는 항목 0건).
- 감지 사다리가 전부 실패해도 `SQ`(단일 세션 순차)로 끝나 **fail-open** 한다(§4.3).

---

## S16 — `agent-teams` 폐기 예고 + 메타 5종 정리 (워커)

> **읽기 집합**: `agent-teams/SKILL.md` + 메타 에이전트 5종의 듀얼 모드 절 +
> `multi-perspective-review/SKILL.md` ≈ **8 파일**.

### 전제 (변경 금지)
- **v2.19.0 에서는 예고만.** 제거는 v3.0.0(S22)이다 — 스킬 삭제는 `/agent-teams` 를 치던
  사용자에게 파괴적 변경이다(D-7).
- 스킬 수 **19 유지**.
- `multi-perspective-review` 의 **서브에이전트 모드**(기본 경로)는 계속 동작해야 한다.

### 이번 범위
1. `26-3` `agent-teams/SKILL.md` 본문을 **폐기 예고로 교체**. 내용은 흡수됐고 `control-loop` 를
   가리킨다(D-7 1단계).
2. `26-8` **메타 에이전트 5종의 "듀얼 모드 지원(W-032)" 절 동시 정리**(D-28 연동).
   대상: `consensus-builder:483-507` · `devils-advocate:450-457` · `synthesizer:418-442` ·
   `facilitator:312-346` · `facilitator-teams.md`(파일 전체).
   **스킬만 폐기하면 에이전트 정의가 죽은 참조로 남는다.**
   - `facilitator.md:321-327` 의 "모드 자동 선택(CALC-001)" 점수식은 상시 자동 분기처럼 보이게
     하므로 제거한다
   - `facilitator-teams.md` 는 파일 전체가 폐기 예정 시스템(`spawnTeam`/`message`/`broadcast`)
     위에 설계돼 있다 — v2.19.0 에서는 **폐기 예고 각주**만, 제거는 S22
   - `facilitator-teams.md:243` 의 `explore-infrastructure`(존재하지 않는 에이전트)는 S1 이
     처리했어야 한다. 남아 있으면 여기서 제거
3. `multi-perspective-review/SKILL.md:42` 의 `design-database` — S1 이 처리. 미처리면 여기서.

### 금지사항
- `absoluteProhibitions` 전체.
- **`agent-teams` 스킬 파일 삭제** — v3.0.0 이다.
- 스킬 개수 변경.
- 메타 에이전트의 **서브에이전트 모드 서술** 삭제(그것이 기본 경로다).

### 완료 조건
- **G7** green: `agent-teams/SKILL.md` 에 폐기 예고 문구 ∧ `control-loop` 참조 존재.
- `grep -rn "spawnTeam\|broadcast" plugins/common/agents/meta/` 가 폐기 예고 문맥 밖에서 0건.
- **G8** green: 문서 카운트 게이트 — 스킬 19 유지.
- `verify-done.sh` 전 게이트 green.

---

## S25 — `references/work-system.md` 재작성 (워커) 【Q3 답신 · W-026 신설 항목】

> **읽기 집합**: `work-system.md`(509행) + `plan-task/SKILL.md` + `auto-dev/SKILL.md`
> ≈ **4 파일 / 약 60KB**. 상한에 가깝다 — 509행 전문을 읽어야 한다.
> **왜 W-025 가 아니라 W-026 인가**: Q3 답신 — *"전면 재작성을 W-025 에 넣지 않는다.
> 이미 크고, 이 파일은 **활성 참조 2곳**이라 잘못 고치면 스킬 둘이 깨진다."*
>
> S2 가 이 파일을 `plan-task/references/` 로 **이관**하고 **구세대 배너**를 달아 두었다.
> 이 Stage 가 그 배너를 걷어낸다. **배너가 "영구 노란 경고" 가 되지 않는 이유가
> 바로 이 Stage 의 존재다** — 추적 항목 없는 배너였다면 Q3 에서 기각됐을 것이다.

### 전제 (변경 금지)
- **인용하는 두 스킬의 링크가 계속 살아 있어야 한다**: `plan-task/SKILL.md:200` ·
  `auto-dev/SKILL.md:386`(S2 이관으로 경로는 갱신된 상태). 파일을 지우거나 옮기지 마라.
- **현재 `plan-task` 의 모델은 Step 0-4** 다. Phase 0-6 이 아니다.
- 다관점 리뷰는 `multi-perspective-review` 스킬이 별도로 담당하며,
  `auto-dev` Step 3 의 `review-results.md` 는 **Validation 단계**(Dev 이후)에서
  review-code/security-scan 결과를 담는 파일이다 — `work-system.md` 가 말하는
  "Phase 6, Planning 중 다관점 리뷰" 가 **아니다**(T3 F5 실측).

### 이번 범위
1. Phase 0-6 번호 체계를 제거하고 현재 **Step 0-4** 서술로 재작성한다.
   대상 줄(T3 F5 실측): `:39-40, 148, 162, 170, 176, 182, 188, 193, 339`.
2. `review-results.md` 의 생성 시점 서술을 실제 동작(Validation 단계)에 맞춘다.
3. S2 가 달아 둔 **구세대 경고 배너를 제거**한다 — 이 Stage 의 완료 신호다.

### 금지사항
- `absoluteProhibitions` 전체.
- **파일 삭제·이동** — 활성 참조 2곳이 깨진다.
- 인용하는 두 스킬의 본문 수정(이 Stage 는 참조 대상만 고친다).
- 배너만 떼고 내용을 그대로 두는 것 — 그러면 문제가 **보이지 않게** 될 뿐이다.

### 완료 조건
- `grep -cE "Phase [0-6]" plugins/common/skills/plan-task/references/work-system.md` → 0.
- 구세대 배너 문자열 0건.
- `plan-task/SKILL.md` · `auto-dev/SKILL.md` 의 링크가 실재 경로를 가리킨다(**G22 ③** 재확인).
- `verify-done.sh` 전 게이트 green.

---

## S17 — `policy.json` C등급 등재 + v2.19.0 릴리스 (컨트롤)

### 전제 (변경 금지)
- `_tier2Classification` 은 **에이전트 33종 분류의 SSOT** 다. 스킬을 추가해도
  `check_classification_complete` 는 `all_agents - covered` 단방향이라 깨지지 않는다(실측 확인).
- 회계 문장(`_tier2Rationale`)의 33종 합계 — 스킬 등재가 이 합계를 바꾸는지 명시해야 한다.

### 이번 범위
1. `26-4` `control-loop` 을 등급 **C** + 사유 + **승격 조건**과 함께 등재(D-8).
   **【검수 L1】 D-8 의 "게이트가 강제한다" 는 사실이 아니다** — 그 검사는 스킬을 보지 않는다.
   등재는 **기록으로서** 가치가 있으므로 수행하되, D-8 본문의 강제 장치 주장은 컨트롤이 정정한다.
   **【검수】 승격 조건 문장이 설계문서에 없다** — 기존 B등급 항목들과 같은 형식으로 작성해야 한다
   (예: *"러너가 다중 턴 세션 트랜스크립트를 채점 입력으로 받는 경로를 지원하면 재평가"*).
2. `26-5` `bump-version.sh 2.19.0` + CHANGELOG + 문서 카운트 + 태그.

### 금지사항
- `absoluteProhibitions` 전체.
- `plugin.json` 손 편집.
- 승격 조건을 `null` 로 두고 등재하는 것.

### 완료 조건
- **G6** green: `python3 scripts/check_eval_coverage.py` 가 경고 없이 통과.
  **주의**: 이 게이트는 `control-loop` 등재 여부와 **무관하게** 통과한다(L1) —
  green 을 등재의 증거로 쓰지 마라. 등재 확인은 `policy.json` 직접 grep 이다.
- `verify-done.sh` 전 게이트 green · `build-targets.py --check` green.

---

# W-027 — 이름 SSOT화 + v3.0.0

## S18 — 마켓플레이스 이행 프로브 (워커)

### 전제 (변경 금지)
- **프로브는 실측이다.** 문서로 답을 추정해 채우지 마라 — 이 레포의 기준은 `runtime-verified` 다.
- W-019 의 `cck-probe-marketplace` 와 **동일 기법**(그 잔재가 캐시에 남아 있었다).
- 프로브 결과가 나오기 전에는 README·공지에 이행 경로를 **쓰지 않는다**(§11.3).

### 이번 범위
`27-1` D-4 의 세 질문에 `runtime-verified` 답을 남긴다:
1. 구 이름 항목을 폐기 표시로 남긴 채 신 이름으로 설치가 되는가
2. 구 이름 설치본과 신 이름 설치본이 공존할 때 스킬·에이전트가 **중복 등록**되는가
3. `enabledPlugins` 키 이행이 자동인가 수동인가

### 금지사항
- `absoluteProhibitions` 전체 (특히 실제 마켓플레이스 항목 생성·수정).
- 스크래치 설치본을 정리하지 않고 남기는 것 — W-019 의 잔재가 §1.5 의 청소 대상이 됐다.
- 답을 추정으로 채우는 것. 모르면 `[unresolved]`.

### 완료 조건
- **G9** green: 세 질문 전부에 실행 로그가 붙은 답이 존재.
- 프로브 잔재(스크래치 마켓플레이스·설치본) 정리 완료.
- **D-33 의 별칭 기한 재확인**: 질문 2가 "중복 등록된다" 이면 기한을 **줄여야** 한다.

---

## S19 — 이름 SSOT 파생 생성기 + 드리프트 검사 (워커)

### 전제 (변경 금지)
- SSOT 는 `plugins/common/.claude-plugin/plugin.json` 의 `name` 이다.
- `packaging/targets.json` 의 `source._meta.authority` 불변식: *"어떤 타겟 생성물도 이 값을
  재정의하지 않는다."*
- **드리프트 게이트 3종을 통합하지 않는다** — 통합 여부 판정은 S20 이다.
- `build-targets.py` 의 **경로 봉쇄 관례**를 그대로 따른다(CLAUDE.md — 같은 결함이 세 번 반복됐다):
  설정에서 온 경로는 한 번만 resolve, 레포 밖이면 exit 1, **읽기 경로도 봉쇄**, `--check` 에도 같은 봉쇄.

### 이번 범위
`27-2` 이름 파생 생성기 + 드리프트 검사. 적용 대상: `README.md` · `plugins/common/README.md` ·
`site/` 콘텐츠 · `CLAUDE.md` · 스킬 본문(D-3).
개명 비용을 **파일 수 비례 → 상수**로 바꾼다(현재 `git grep -l "claude-code-kit"` → 59파일).

### 금지사항
- `absoluteProhibitions` 전체.
- **실제 개명 수행** — S22 다. 이 Stage 는 생성기만 만든다.
- 경로 봉쇄 관례를 새로 발명하는 것.
- 기존 드리프트 게이트 §11·§13·§14 수정.

### 완료 조건
- **G10** green(되돌려-FAIL): `plugin.json` 의 `name` 만 바꾸고 생성기를 돌리면 문서·사이트
  이름이 전부 따라온다. **그리고 되돌리면 원상복귀한다.**
- **G-PATH** green: 생성기에 절대경로·`..`·심링크를 먹이면 exit 1(읽기 경로 포함, `--check` 포함).
- `verify-done.sh` 전 게이트 green.

---

## S20 — 네 번째 드리프트 게이트 통합 여부 판정 (컨트롤)

### 전제 (변경 금지)
- **판단 기준은 D-26 이 이미 제공했다**: **사본이면 게이트 필요, 참조면 불필요.**
- CLAUDE.md 의 기존 판정: 셋을 통합하지 않는 이유는 *"입력·판정 기준·실패 메시지가 전부 다르고,
  추상이 세 케이스를 감당하지 못해 게이트 코드가 어려워진다 — 아무도 이해하지 못하는 게이트는
  red 가 떴을 때 무시된다"*. **이 근거를 직접 반박하지 않는 한 통합하지 않는다.**

### 이번 범위
`27-3` S19 의 구현 형태(사본 생성 vs 참조)를 확인하고 판정한다.
**묶지 않기로 결론 나면 그 근거를 CLAUDE.md 에 기록한다**(D-3 명시).

### 금지사항
- `absoluteProhibitions` 전체.
- 판정 없이 S21·S22 로 진행하는 것.
- CLAUDE.md 의 기존 판정을 근거 반박 없이 뒤집는 것.

### 완료 조건
- 판정과 근거가 CLAUDE.md(또는 `docs/conventions/no-gate-integration.md`)에 기록됨.
- `verify-done.sh` 전 게이트 green.

---

## S21 — 파리티 계약 문장 반영 (워커)

### 전제 (변경 금지)
- 약속 문장(D-2): *"규범과 절차(L0·L1)는 모든 하네스 공통. 전용 실행자와 자동 강제(L2·L3)는
  Claude Code 심화 기능."*
- **한계를 숨기지 않는 것이 D-2 계약의 요체다**(§4.5 노드 H).

### 이번 범위
`27-4` README · 매니페스트 `description` 에 파리티 문장 반영. **함께 명시해야 하는 한계 4종**
(`01-policy.json` `parityContract.requiredDisclosures`):
1. 행동 eval 은 현재 Claude Code 만 구동한다(D-12, 수용 17)
2. 에이전트·훅은 Codex·Antigravity 에 없다
3. 다중 하네스 지원은 생성 + 1회 실측 검증까지이고 상시 사용이 아니다
4. **【검수 추가】** 비-Claude-Code 하네스의 L0 는 소비자가 `/harness-export` 를 직접 실행해야
   성립한다 — `AGENTS.md` 는 레포 루트에 있고 배포 패키지(`plugins/common`)에 포함되지 않는다.
   자동이 아니라 **opt-in 이며 그 시점의 스냅샷**이다.
   (실측: `.claude-plugin/marketplace.json` 의 `source.path` = `plugins/common`,
   `ls plugins/common` 에 `AGENTS.md` 없음. 동작 자체는 `export_harness.py:339-383` 의
   자동 탐색으로 소비자 환경에서도 성립한다.)

`packaging/targets.json` 의 `_skillsCountNote` 갱신도 여기서(§10.4 배정) — **S2 의 이관을
실제로 수행했을 때만** "해소됨" 으로 쓴다.

### 금지사항
- `absoluteProhibitions` 전체.
- 한계 4종 중 하나라도 생략하는 것 — 설계 §0 기준 1("약속과 실물의 일치") 위반.
- 실측되지 않은 "해소됨" 기록.

### 완료 조건
- **G17** green: README 파리티 문장에 *"행동 eval 은 Claude Code 만 구동한다"* 존재.
- **G12** — **원리적으로 게이트 불가**(자연어 동치). `03-gate-spec.md` G12 의 대체 검증
  (마커 문자열 동일성) 적용.
- `verify-done.sh` §6·§14 green.

---

## S22 — `hiway-kit` 개명 + `agent-teams` 제거 + v3.0.0 (컨트롤)

> **되돌리기 비용이 이 프로그램에서 가장 크다.** 마켓플레이스 리스팅 · 커뮤니티 카탈로그
> **새 리스팅**(D-4: 이름 변경 = 재제출) · 소비자의 `enabledPlugins` 키 — **어느 것도 이 레포의
> 커밋으로 되돌아가지 않는다.** 카탈로그는 익일 동기화라 잘못 나간 이름이 최소 하루 살아 있다.

### 전제 (변경 금지 · 착수 게이트)
- **S18(프로브) 완료** — 세 질문 전부 `runtime-verified`. 미완이면 착수 금지.
- **S19(생성기) 되돌려-FAIL 통과** — 미완이면 59파일 수작업이 된다.
- **S20(게이트 판정) 기록 완료.**
- `hiway-kit` — `hw` 는 하드웨어와 충돌해 탈락, `hiway-code-kit` 은 이득이 절반(D-4).
- **dual-name 을 채택하지 않는다**(D-1). 기능 충돌 · 불변식 파괴 · 영구 분기.

### 이번 범위
1. `27-5` `plugin.json` 의 `name` 변경 → 생성기 실행 → 전 문서·사이트 반영.
2. `27-5` `agent-teams` 스킬 **제거**(D-7 2단계). 스킬 19 → 18.
   `check_doc_counts.py` 대상 문서 전부 갱신. `facilitator-teams.md` 도 이 시점에 처리.
3. `27-5` `bump-version.sh 3.0.0` + CHANGELOG + 태그.
4. D-33 의 폐기 별칭 — **S18 결과에 따라 기한 확정 후** 마켓플레이스에 폐기 표시로 유지.

### 금지사항
- `absoluteProhibitions` 전체.
- **S18·S19·S20 미완 상태에서의 착수.**
- 프로브 결과가 "중복 등록된다" 인데 기한을 **늘리는** 것 — 공존 자체가 해롭다(D-33).
- 개명 커밋과 태그를 분리하는 것(CLAUDE.md — 과거 20개 릴리스가 태그 없이 나갔다).

### 완료 조건
- **G11** green: `build-targets.py --check` — 세 매니페스트의 `name` 이 SSOT 와 일치.
- `git grep -l "claude-code-kit"` 이 **역사 기록(CHANGELOG · docs/specs · docs/works)** 밖에서 0건.
- 스킬 18 · 문서 카운트 게이트 green.
- `verify-done.sh` 전 게이트 green · 태그 존재.

---

## S23 — 커뮤니티 카탈로그 재제출 (컨트롤)

### 전제 (변경 금지)
- **이름 변경 = 새 리스팅**이다(D-4). 버전 갱신과 달리 재제출이 필요하다.
- 카탈로그는 **읽기 전용 미러 · 나이틀리 동기**. 직접 PR 은 자동 닫힌다.
- 일회성 리스팅 경로: `clau.de/plugin-directory-submission`.

### 이번 범위
`27-6` 재제출. 그리고 **직접 마켓플레이스는 즉시, 카탈로그는 익일**이라는 전파 차이를
공지에 명시한다.

### 금지사항
- `absoluteProhibitions` 전체.
- 카탈로그 저장소에 직접 PR.
- 재제출 전 구 리스팅 제거(D-33 기한이 살아 있다).

### 완료 조건
- 제출 완료 기록 + 반영 확인 일자.
- D-33 기한 타이머의 시작일이 기록됨.

---

## 부록 — Stage 별 트랙·버전·담당 요약

| Stage | 항목 | 트랙 | 버전 | 담당 | 선행 |
| --- | --- | --- | --- | --- | --- |
| S0 | 25-1·3·4·5·6 | A | 없음 | 컨트롤 | — |
| **S1** | 25-21 **+ 25-16(§17)** + E3·E5·E6·L10 | C | 2.18.0 | 워커 | — |
| S2 | 25-18·23·25 + L5 + E4(배너) | C | 2.18.0 | 워커 | — |
| S3 | 25-20·27 | C | 2.18.0 | 워커 | S1 |
| S4 | 25-11 (골격) | C | 2.18.0 | 워커 | — |
| S5 | 25-12·13 + E9 + export_harness 분류표 | C | 2.18.0 | 워커 | S4 |
| **S24** | **비신뢰 텍스트 → core 규범 신설 + interop conditional** | C | 2.18.0 | 워커 | S4·S5 |
| **S6** | 25-15 **+ 25-14(§16)** + D-25 | C | 2.18.0 | 컨트롤+워커 | S4·S5·S24 |
| S7 | 릴리스 | C | 2.18.0 | 컨트롤 | S1~S6·S24 |
| ~~S8~~ | **퇴역** — S6 에 흡수 | — | — | — | — |
| ~~S9~~ | **퇴역** — S1 에 흡수 | — | — | — | — |
| S10 | 25-17 + E7 **(warn-first)** | B | 없음 | 워커 | S2·S5·S24 |
| S11 | 25-2·7·8·9·10·24 | B | 없음 | 워커 | — |
| S12 | 25-19·22·26·28 | B | 없음 | 컨트롤+워커 | S12a→S12b |
| S13 | 26-6 | — | 2.19.0 | 워커 | W-025 전부 |
| S14 | 26-1·7 | — | 2.19.0 | 워커 | S13 |
| S15 | 26-2 **(docs/) + G-D6** | — | 2.19.0 | 워커 | S14 |
| S16 | 26-3·8 | — | 2.19.0 | 워커 | S14 |
| **S25** | **work-system.md 재작성** | — | 2.19.0 | 워커 | S2 |
| S17 | 26-4·5 | — | 2.19.0 | 컨트롤 | S13~S16·S25 |
| S18 | 27-1 | — | — | 워커 | — |
| S19 | 27-2 | — | — | 워커 | — |
| S20 | 27-3 | — | — | 컨트롤 | S19 |
| S21 | 27-4 | — | — | 워커 | S13 |
| S22 | 27-5 | — | 3.0.0 | 컨트롤 | S18·S19·S20·S21 |
| S23 | 27-6 | — | — | 컨트롤 | S22 |

**Q1~Q5 반영으로 바뀐 행**: S1(§17 흡수) · S6(§16 흡수) · S8·S9(퇴역) · S10(warn-first 명시) ·
S15(위치 확정 + G-D6) · **S24 신설**(Q2) · **S25 신설**(Q3) · S5(분류표 항목 추가).

**【검수 L9 해소】** 설계문서 §11.2(f) 는 W-025 **22개 항목**만 트랙에 배정했고 §11.4 가 추가한
25-23~25-28 여섯은 미배정이었다. 위 표가 전부 배정한다 — 25-23·25(S2) · 25-27(S3) · 25-24(S11) ·
25-26·28(S12). 그중 **25-23·25-25·25-27 은 `plugins/**` 를 건드리므로 C 트랙(v2.18.0)** 이다.
방치하면 "배포물 변경인데 버전 무변경" 사고가 난다 — CLAUDE.md 가 CRITICAL 로 못박은 실수다.

**【검수 O4·O6·O7 해소】** 순서 제약은 각 Stage 의 *전제/금지사항* 에 들어갔다 —
O4(탐지 전환은 S2·S5·S24 뒤) · O6(메타 `references:` 는 삭제될 `skills/references/` 가 아니라
`multi-perspective-review/` 를 가리킨다) · O7(S22 는 S19 되돌려-FAIL 통과 전 착수 금지).
매핑 전문은 `05-coverage.md` 참조.

> **W-026 의 버전(2.19.0)은 `01-policy.json` 에서 여전히 `[unresolved]` 다** — 답신이 이 건을
> 다루지 않았다. 설계문서가 §5:455·D-7(2.18.0)과 §11.2(f)·수용32(2.19.0) 두 값을 말한다.
> 위 표는 정정 의도인 2.19.0 을 썼으나, **컨트롤이 설계문서를 고치기 전에는 S17 에서
> 버전을 확정하지 마라.**
