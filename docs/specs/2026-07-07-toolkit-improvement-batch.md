# Toolkit 개선 배치 — 등재 반영 · Evals · Native Watch · Self-Improve · Portfolio

**Goal:** 커뮤니티 카탈로그 등재를 문서에 반영하고, kit의 두 구조적 갭(에이전트 행동 평가 부재, 네이티브 흡수 대응 비정기화)을 메운 뒤, evals를 안전장치로 하는 self-improve 루프와 포트폴리오 영문 포지셔닝까지 완성한다.

**Architecture:** 5개 Work를 단일 배치(1 릴리스 = v2.10.0)로 순차 실행한다. 의존성은 W-B(evals) → W-D(self-improve) 하나뿐이며, 각 Work 완료 시 적대적 리뷰(review-code), 배치 완료 후 최종 적대적 재감사를 수행한다. 오케스트레이션은 Medium 규모 → 스킬 주도 플랫 위임(CLAUDE.md Spec 2 준수).

## 배경 (확정 사실)

- `anthropics/claude-plugins-community` 카탈로그(2,199개)에 `claude-code-kit` 등재 확인 (2026-07-07 조회, pinned SHA `d7f80c9` = v2.9.3 머지 커밋).
- 제출 기록: 2026-06-14 (v2.7.0, `docs/marketplace-submission.md`) → 등재까지 ≤3주.
- pinned SHA가 제출 시점(v2.7.0)이 아니라 최신 v2.9.3 → **nightly sync가 자동으로 pin을 전진**시킴 = 버전업 전파는 ~1일. 재제출 불필요.
- `claude plugin validate` 로컬 통과. 레포 public 확인.

## 요구사항

1. **W-A 문서 정합화** — "pending review" 등 stale 문구를 등재 완료로 갱신, community 설치 커맨드 추가.
2. **W-B Agent Evals** — 핵심 에이전트의 행동 회귀를 기계로 검증하는 eval 하네스. 프롬프트 수정 시 품질 후퇴를 감지할 수 있어야 한다.
3. **W-C Native Watch** — 네이티브 흡수 감시를 일회성 수동 작업에서 반복 가능한 루틴으로: SSOT 대조표 + 실행 스킬.
4. **W-D Self-Improve 루프** — feedback ledger의 반복 결함을 근원(에이전트/스킬/룰 정의)에 반영하는 제안 루프. evals green + 사람 승인 없이는 적용 불가.
5. **W-E 프로젝트 페이지 강화 (ko+en)** — 레포/사이트는 **프로젝트** 홍보·설명 전용(개인 홍보 콘텐츠 금지). 기술·구현 원리를 잘 설명해 검색 유입을 높이고, 영어 페이지를 추가해 영어권 검색에도 노출. 개인 포트폴리오 초안은 gitignore된 로컬 파일로만 제공(사용자가 링크드인/개인 페이지에 활용).
6. 각 Work 종료 시 적대적 리뷰, 전체 종료 후 최종 적대적 재감사.
7. 릴리스 규율: 단일 배치 = v2.10.0 minor bump + CHANGELOG, `scripts/verify-done.sh` green.

## 접근 방식

검토한 대안:

- **A1 (채택) — 순차 배치 + 스킬 주도 플랫 위임.** W-A→W-B→W-C→W-D→W-E 순서. 근거: Medium 규모(5 Work, 단일 레포), W-B→W-D 의존성, Work 간 파일 겹침(README를 W-A/W-C/W-E가 모두 수정)으로 병렬 머지 비용 > 병렬 이득.
- **A2 — worktree 병렬 (W-A/W-C/W-E 동시).** README 3중 수정 충돌로 기각.
- **A3 — ultracode 대규모 오케스트레이션.** 10~100+ 태스크 규모가 아니므로 기각 (Spec 2 위반).

버전 전략: 배치 시작 시 feature 브랜치에서 v2.10.0 + CHANGELOG 골격을 먼저 커밋 → 이후 모든 커밋이 버전-sync 게이트(§6)를 통과. 최종 머지 1회.

## 컴포넌트 구조

### W-A: 문서 정합화 (docs-only)

- `README.md` — "Official registry: pending review" 블록 → 등재 완료 + `/plugin install claude-code-kit@claude-plugins-community` 병기. 개인 마켓플레이스 경로는 "즉시 업데이트 경로"로 유지 문서화.
- `docs/marketplace-submission.md` — Status를 승인·등재 완료로 갱신(등재 확인일·pinned SHA 갱신 방식 기록).

### W-B: Agent Evals (`evals/` — 레포 루트, 플러그인 페이로드 외부)

플러그인 설치 용량에 영향 없도록 `plugins/` 밖에 둔다.

```
evals/
  scenarios/<agent-name>/<scenario-id>/
    task.md          # 에이전트에 줄 과제
    fixture/         # 대상 코드 (심은 버그 포함)
    expect.json      # 채점 기준 (deterministic assertions + judge rubric)
  run.py             # 러너: claude -p 헤드리스 실행 + 채점 + 리포트
  README.md
scripts/run-evals.sh # 진입점 (에이전트/시나리오 필터 옵션)
```

- **대상(초기 3개):** `review-code`(심은 버그 적발률 — 가장 가치 높음), `fix-bugs`(수정 후 fixture 테스트 green), `implement-code`(요구 충족 + delegation signal 계약).
- **시나리오:** 에이전트당 3~5개, 총 ~12개.
- **채점 2단:** ① deterministic(필수) — 심은 버그 파일:라인 적중, fixture pytest green, DELEGATION_SIGNAL 형식 유효. ② LLM-judge(보조) — rubric 채점, deterministic 통과 시에만 실행.
- **실행 모델:** 러너는 에이전트 `.md`의 frontmatter(model)와 본문(시스템 프롬프트)을 파싱해 `claude -p`(모델·시스템 프롬프트·fixture cwd 지정)로 실행. API 비용이 들므로 **on-demand + 릴리스 전 필수**로 운영하고 per-commit CI에는 넣지 않는다.
- **verify-done 통합(오프라인만):** §9 신설 — `expect.json` 스키마 유효성 + 시나리오-에이전트 참조 무결성 검사(네트워크·API 불필요). 행동 eval 자체는 `run-evals.sh`의 몫.

### W-C: Native Watch

- `docs/native-absorption.md` — SSOT 대조표: kit 컴포넌트 ↔ 대응 네이티브 프리미티브 ↔ 상태(kit-only / native-superseded / delegated). 기존 사례(agent-teams→ultracode, lifecycle→OTel)를 초기 데이터로 역기입.
- `plugins/common/skills/native-watch/SKILL.md` — `/native-watch`: Claude Code 릴리스 노트/문서를 조회(web-research 경유)해 대조표와 diff → "흡수 후보" 리포트 + 대조표 갱신 제안. 주기 실행은 네이티브 `/schedule`에 위임(스킬 내 안내만; 자체 스케줄러 구현 금지 — zero-debt).

### W-D: Self-Improve 루프

> **구현 시 조정됨 — SKILL.md가 SSOT**: digest는 1,200자 절단이라 전수 입력으로
> 부적합해 ledger.md 직접 읽기로 대체됐고, 'addressed 마킹'은 스키마 부재로 직전
> 적용 커밋 대조(멱등성 확인)로 대체됐다. 아래 원설계는 역사 기록.

- `plugins/common/skills/self-improve/SKILL.md` — `/self-improve` 파이프라인:
  1. 입력 수집: `feedback_ledger.py digest`(전체) + 최근 eval 리포트.
  2. 근원 분석: 반복 결함(frequency≥2)을 야기한 에이전트/스킬/룰 정의를 식별.
  3. 수정 제안: 해당 `.md` 정의에 diff 제안 (직접 적용 아님).
  4. **안전 게이트(순서 고정):** 관련 evals 실행 → 후퇴 없음 확인 → diff + eval before/after를 사용자에게 제시 → **사용자 승인 후에만 적용**.
  5. 적용 시 ledger 해당 엔트리에 "addressed" 마킹(재발 시 재부상).
- 자동 커밋·자동 적용 절대 금지. evals 실행 불가 환경(API 키 부재)이면 제안까지만 하고 적용 게이트에서 중단(명시적 SKIPPED, false-green 금지).

### W-E: 프로젝트 페이지 강화 (ko + en)

기존 자산: `site/` Hugo 사이트(GitHub Pages, `pages.yml` 자동 배포, 자체 최소 테마, ko 단일 언어, 기술 포스트 4편).

- **다국어 전환:** `hugo.toml`에 `[languages]` ko(기본) + en 설정. 자체 테마 레이아웃의 다국어 호환(언어 스위처 링크 1개) 확인.
- **핵심 페이지 (ko/en 쌍):**
  - `_index` — 프로젝트가 무엇인지/왜 쓰는지 한 문단 + 최신 글.
  - `about` — 아키텍처·구현 원리 페이지로 승격: 하네스 위 멀티 에이전트 시스템, Harness × Loop Engineering, 결정적 가드레일(훅·DoD 게이트), 모델 티어링, worktree 격리, feedback 루프, (이번 배치의) evals·self-improve. 정량 지표(33 agents·16 skills·13 rules·112+ tests·community 카탈로그 등재) 포함.
  - `getting-started`(신규) — 설치·핵심 스킬 활용법(두 설치 경로: community 카탈로그 / 개인 마켓플레이스).
- **SEO:** 페이지별 description·keywords front matter, sitemap(이미 활성)·robots 확인. 영어 페이지는 번역이 아니라 영어권 검색어(claude code plugin, multi-agent system, agent harness 등)에 맞춰 작성.
- **개인정보 배제 원칙:** 사이트·레포 내 콘텐츠는 프로젝트만 다룬다. 개인 홍보·이력 내용 금지.
- **개인 포트폴리오 초안(비공개):** `docs/personal/portfolio-draft.md` (국·영문 이력서 문구, 링크드인용 요약, 프로젝트 페이지 인용 링크) — `.gitignore`에 `docs/personal/` 추가 후 작성 → 커밋되지 않음.

## 데이터 흐름

```
ledger(결함 누적) ──┐
                    ├─▶ /self-improve → 정의 diff 제안 → evals 게이트 → 사람 승인 → 적용
evals(행동 기준선) ─┘                                        │
        ▲                                                    │
        └── scripts/run-evals.sh ◀── 릴리스 전 필수 ◀────────┘
/native-watch → docs/native-absorption.md 갱신 → 흡수 결정은 별도 Work로
```

## 에러 처리

- **evals:** API 키 부재/네트워크 실패 → 명시적 `SKIPPED` 종료코드(≠0, ≠성공). 결과 부재를 성공으로 위장하지 않는다(기존 false-green 교훈, v2.9.3). judge 불안정 → deterministic만으로 pass/fail 판정 가능해야 함.
- **native-watch:** 웹 조회 실패 → 대조표 기존 상태 유지 + 실패 보고(fail-open이되 보고 필수).
- **self-improve:** ledger 부재 → 무동작(기존 fail-open 규약 준수). eval 후퇴 검출 → 제안 폐기 + 사유 보고.
- **문서 수정:** verify-done §6 카운트/버전-sync 게이트가 스킬 수(14→16) 문서 표기 불일치를 잡는다 — README/CLAUDE.md 카운트 동시 갱신 필수.

## 테스트 전략

- **W-B:** `run.py` 자체에 pytest 단위 테스트(파서·채점기·리포터 — API 호출은 mock). 시나리오 스키마 검증을 verify-done §9로. 실제 행동 eval 1회 전체 실행해 기준선 리포트를 `evals/baseline/`에 기록.
- **W-C/W-D:** 스킬은 마크다운이므로 CI frontmatter 검사 + 시나리오 워크스루(수동 1회) + 적대적 리뷰로 검증. self-improve 안전 게이트는 체크리스트화해 스킬 본문에 HARD-GATE로 명기.
- **각 Work 적대적 리뷰:** review-code 에이전트(4 페르소나) — Work 산출물 diff 대상.
- **최종:** 배치 전체 diff 적대적 재감사 + `scripts/verify-done.sh` + `claude plugin validate` + 전체 evals 1회.

## 범위 외

- 전 33개 에이전트 evals 확대(초기 3개 이후 점진 — 후속 Work).
- self-improve의 자동 적용(사람 게이트 제거) — 명시적으로 하지 않는다.
- 자체 스케줄러/크론 구현 — 네이티브 `/schedule` 사용.
- 도메인 플러그인 복원, 신규 에이전트 추가.
- README 전면 영문화(사이트 en 페이지가 영어권 진입점 역할).
- 레포 내 커밋되는 개인 포트폴리오/이력 문서 — 명시적으로 하지 않는다(개인 레포의 몫).
- 사이트 테마 교체·디자인 리뉴얼(콘텐츠·다국어·SEO만).

## 실행 순서 및 게이트

| 순서 | Work | 산출물 | 게이트 |
|---|---|---|---|
| 0 | 브랜치 + v2.10.0/CHANGELOG 골격 | feature branch | verify-done §6 |
| 1 | W-A 문서 정합화 | README, submission doc | 적대적 리뷰 |
| 2 | W-B Evals | evals/, run-evals.sh, verify-done §9, baseline | 적대적 리뷰 + evals 실행 성공 |
| 3 | W-C Native Watch | native-absorption.md, native-watch 스킬 | 적대적 리뷰 |
| 4 | W-D Self-Improve | self-improve 스킬, ledger 연동 | 적대적 리뷰 + 안전 게이트 워크스루 |
| 5 | W-E 프로젝트 페이지 | site/ ko·en 페이지 + gitignored 개인 초안 | 적대적 리뷰 + hugo 빌드 성공 |
| 6 | 최종 | 재감사 + verify-done + evals + merge | 최종 적대적 재감사 |
