# dryforge 채택 검토 — 전언 검증과 실체 조사 (2026-09-15)

> **왜 조사했나.** 사용자가 *"superpowers 를 없애고 `prekuter/dryforge` 를 쓸까 고민중이다.
> dryforge 는 **다른 거 안 붙이고 원본으로 쓰는 게 진짜 좋다**고 들었다"* 고 물었다.
> 이 질문에는 검증되지 않은 전제가 둘 있다 — ① dryforge 가 단독 사용을 요구한다,
> ② hiway-kit 이 superpowers 에 의존하므로 "없앤다"가 성립한다. **둘 다 실측 대상이다.**
>
> 값에는 `[confirmed]` / `[researched: 출처, n=표본]` / `[미확인]` / `[판정 불가]` 를 붙인다.
> 추측으로 채우지 않는다.

## 결론 세 줄

1. **전언은 틀렸다.** dryforge 문서는 정반대를 명시하고, 그것이 빌드 게이트로 강제된다.
2. **"superpowers 를 없앤다"는 이 레포의 작업이 아니다.** 하드 의존 0건 — 주입 소유자는 전역 설정이다.
3. **채택할 이유를 찾지 못했다.** dryforge 는 훅·CI·eval·에이전트가 전부 0이고, 별 230개에
   비해 **실사용 흔적이 없다**. 다만 `ready` 의 기획 정련 깊이는 우리보다 앞선다 — 도구가
   아니라 **설계를 흡수**할 대상이다.

---

## 0. 조사 방법

격리 워크트리 4기에 **disjoint 한 조사 축**을 병렬 위임했다(기준 커밋 `0eda7fe`). 조사와
구현을 섞지 않았다 — 전 워커가 읽기 전용, 파일 수정 금지였다.

| 워커 | 축 |
| --- | --- |
| 1 | dryforge 아키텍처 실측 (집행 기계가 있는가) |
| 2 | 성숙도·채택 신호 (지금 써도 되는가) |
| 3 | "원본으로만" 주장 검증 (전언에 근거가 있는가) |
| 4 | superpowers 제거 비용 (교체가 성립하는가) |

**워커 보고는 결론이 아니라 검증의 입력으로 다뤘다.** 결정을 좌우하는 주장은 컨트롤이
직접 재현했다(§1 플래그·빌드 가드, §2 grep·§17 본문, §3 구조 카운트, §4 GitHub API 수치).
아래 `[confirmed]` 는 그 재현을 거친 것만 붙였다.

---

## 1. "원본으로만 써라" — `[근거 없음 — 전언]`

dryforge 문서 어디에도 단독 사용 요구가 **없다.**

검색 대상은 `README.md` · `README_ko.md` · `CHANGELOG.md` · `claude/` · `codex/` · `src/` ·
`platform/` · `build/` · `.claude-plugin/` · `.agents/` 전량(clone `--depth 50`, HEAD `c950599`).
검색어 19종 결과: `other plugin` 0 · `superpowers` 0 · `uninstall` 0 · `vanilla` 0 ·
`단독` 0 · `원본` 0 · `다른 플러그인` 0 · `병행` 0 · `비활성` 0.
위키는 clone 시 **Repository not found**(빈 위키), Discussions 0건, Issues 1건(무관).

**오히려 공식 FAQ 가 반대를 명시한다** `[researched: dryforge.dev/ko, WebFetch 경유]`:

> **Q: 쓰던 환경이 바뀌나요?**
> A: 바뀌지 않습니다. **기존 Claude Code나 Codex 위에 플러그인으로 붙습니다.**
>
> **Q: 언제 실행되나요?**
> A: `/ready`, `/go`, `/migration`을 직접 입력했을 때만 움직입니다.
> **평소 대화나 다른 작업에 끼어들지 않습니다.**

### 1.1 그 "끼어들지 않는다"는 기계로 강제된다 `[confirmed]`

스킬 3종(`go`·`ready`·`migration`) 전부 frontmatter 에 자동 발동 차단 플래그가 있고,
빌드 스크립트가 그것이 빠지면 **출고를 거부**한다.

```
claude/skills/{go,ready,migration}/SKILL.md
    disable-model-invocation: true

build/build.sh:70-71
    grep -q '^disable-model-invocation: true$' "$f" && grep -q '^allowed-tools: ' "$f" \
      || { echo "✗ frontmatter 주입 실패: $s — 자동실행 방지 플래그 없이 출고 불가"; exit 1; }
```

즉 dryforge 는 **남과 부딪히지 않도록 설계된 물건**이다. "원본으로만 써야 한다"는 이 설계의
정반대 해석이다.

**전언의 씨앗으로 보이는 유일한 문장** — `claude/skills/ready/SKILL.md:6` frontmatter 의
*"replacing third-party brainstorming + planning in one skill"*. 이것은 **기능 중복 선언**이지
단독 사용 요구가 아니다. 다만 겹침 자체는 실재한다(§5).

---

## 2. hiway-kit ↔ superpowers 결합도 `[confirmed]`

`git grep -n -i superpowers` 전량 140건 / 35파일을 분류했다.

| 부류 | 건수 | 내용 |
| --- | --- | --- |
| **하드 의존** | **0** | 런타임 코드에서 호출·탐지·요구하는 경로 없음 |
| 조건부 활용(fail-open) | 4 | `using-hiway-kit/SKILL.md:8,9,36`(규율 양보) · `skill-forge/SKILL.md:58`(있으면 대조, 없으면 건너뜀) |
| 단순 언급 | 136 | 문서·주석·출처 표기·역사 기록 |

`plugins/common/rules/` **0건**, `AGENTS.md` **0건**, `GEMINI.md` **0건**.
런타임 파일 히트는 전부 주석 또는 조사 근거 인용이다(`export_harness.py:209`,
`bump-version.sh:8,10,22`, `verify-done.sh:605`, `packaging/targets.json` 의 `_specSummary`).

### 2.1 주입 소유자는 전역 설정이다 `[confirmed]`

- 우리 훅에 참조 0건: `grep -rn -i superpower plugins/common/hooks/ plugins/common/setup/`
  → 히트는 `export_harness.py:209` 주석 1건뿐(기능 무관).
- `session-start.py` 의 `_workflow_skill_path()` 는 `plugin_root/skills/using-{name}/SKILL.md`
  로 **자기 플러그인 안에서만** 찾는다.
- superpowers 는 `~/.claude/settings.json` 의 `enabledPlugins` 로 켜져 있고
  **자기 SessionStart 훅**으로 주입한다.

> **따라서 "superpowers 를 없앤다"는 커밋이 아니라 사용자 설정 조작이고, dryforge 채택과
> 인과가 없다.** 이 레포에서 superpowers 를 참조 대상으로 걷어내더라도 **기능은 아무것도
> 깨지지 않는다**(하드 의존 0) — 비용은 전부 산문이다: 실질 재작성 1파일
> (`using-hiway-kit`), 1줄 편집 5파일, README 섹션 1개.

### 2.2 부수 관찰 — §17 은 이 클래스를 보지 않는다 `[confirmed]`

`verify-done.sh` §17 은 `plugins/` 안 **소문자 `orca` 리터럴 하나**만 검사한다
(헤더: "배포물 안 오케스트레이션 도구 이름 0건"). 배포물 안 superpowers 11건은 **대상 밖**이라
지금 green 이고, 같은 이유로 **`superpowers` 를 `dryforge` 로 바꿔 넣어도 침묵한다.**

`warning-signal.md §검토 절차 5`("대상을 나열하는 검사는 목록 밖을 결코 red 로 만들지
못한다")가 가리키는 형태다. **본 조사에서 고치지 않았다** — 별건이므로 현안으로 남긴다.

---

## 3. dryforge 의 실체 `[confirmed]`

레포 전량 재현 확인(clone `--depth 5`, HEAD `c950599` 2026-09-01):

```
훅 등록(SessionStart|PreToolUse|PostToolUse|hooks.json)   0건
실행 퍼미션 파일                                            0개
.py 0  |  .sh 1  |  .md 96
src/skills/                                    go · migration · ready (3종)
.github/                                       없음 (CI 없음)
```

| | dryforge | hiway-kit |
| --- | --- | --- |
| 훅 | **0** | 5 |
| 실행 코드 | `.sh` 1개(118줄, **빌드 타임 전용**) · `.py` 0 | 17 스크립트 + 게이트 779줄 |
| CI | **없음** | validate 7스텝 + python39-compat |
| 스킬 | 3 | 21 |
| 에이전트 | **0** | 32 |
| 상시 주입 규범 | **0** | 15 rules / 10,055B(상한 10,240B, 게이트 강제) |
| eval·회귀 검증 | **0** | 38 시나리오 + 기준선 |
| 문서 | `.md` 96개 / 310 KB | — |

### 3.1 집행 기계 판정 — 산문이다

런타임에 하네스가 실제로 집행하는 것은 **frontmatter 플래그 2종**이 전부다
(`disable-model-invocation` / `policy.allow_implicit_invocation`). `allowed-tools` 는 명목상
allowlist 이나 `Bash` 와 `Agent` 를 포함해 실질 경계가 아니다.

나머지 "게이트"는 전부 자연어다. 예: `src/skills/go/SKILL.md:305-347` 의 completion gate 는
*"exit 0 로 캡처된 명령과 종료코드를 보여라"*, *"평가 불가한 검사는 fail 이다"* 를 요구하지만
**확인하는 코드가 없다.** `SKILL.md:136-147` 의 graph validation 도 *"YAML 을 파싱해 비순환·
dangling 을 확인하라"* 는 지시이고 파서는 제공되지 않는다.

> **이 레포의 기존 판정을 그대로 적용하면**: 계약을 산문으로 선언하고 그 준수를 모델 판단에
> 맡기며 파서가 없는 구조는, 우리가 W-021/W-022 에서 *"비결정적 보조 경로는 없는 것보다
> 나쁘다"* 며 폐기한 `---DELEGATION_SIGNAL---` 과 **같은 형태**다. 차이는 dryforge 가 그것을
> 부수적 마커가 아니라 **제품의 핵심 주장**으로 세운다는 점이다.

유일한 결정론적 코드 `build/build.sh` 의 가드 4종은 **패키징 무결성만** 본다(공유 reference
바이트 동일성 / frontmatter 주입 사후검증 / 스킬 동적 발견 / 4개 plugin.json ↔ CHANGELOG 버전
일치). 우리 §14·§6 과 같은 계열이되 118줄 하나다.

### 3.2 컨텍스트 예산에 상한이 없다 `[researched: 레포 실측]`

세션 시작 상시 주입은 스킬 프론트매터 **≈1.4 KB** 뿐(훅이 없으므로). 그러나 `go` 를 한 번
호출하면 `SKILL.md`(29 KB) + force-load reference `orchestration.md`(25 KB) 등
**≈54 KB 를 작업 시작 전에 적재**한다. `orchestration.md:197-208` 의 "Context budget" 은
*"temp-load 는 항목별 상한은 있으나 총량 상한이 없다"* 고 **산문으로** 적는다 — 측정도 집행도
없다. 우리 10,240B 상한은 `check_injection_budget.py` 가 CI·게이트 양쪽에서 exit 1 을 낸다.

---

## 4. 성숙도·채택 `[confirmed]`

| 지표 | 값 | 조회 |
| --- | --- | --- |
| 총 커밋 / 기여자 | **17 / 1명**(`prekuter` 16) + 외부 문서 PR 1건 | `contributors`, `commits?per_page=100` |
| 태그 9개(v0.2.0~v1.1.1) | **전부 2026-06-01 ~ 06-12** | `repos/.../tags` |
| GitHub Releases | **0건**(태그만, 릴리스 노트 없음) | `releases` → `[]` |
| **스킬 로직 마지막 변경** | **2026-06-12 → 95일 경과** | `commits?path=src/skills` |
| 마지막 커밋(2026-08-31) | 소유자 개명 **문자열 치환**(12파일 +38/−32), 코드 무변경 | `commits/HEAD --jq .files` |
| 이슈(open+closed 전체) | **0건 — 한 번도 열린 적 없음** | GraphQL `issues.totalCount` |
| Discussions / Wiki / watchers | 0 / 비어 있음 / **1** | GraphQL, `curl` 302 |
| stars / forks | 230 / 23 | `repos/...` |
| **독자 커밋이 있는 fork** | **0개** (표본 확인: ahead_by 전부 0) | `compare/main...{fork}:main` |
| Anthropic community 카탈로그 | **미등재** (2,282항목 중 0회) | `marketplace.json` 전문 검색 |

**제품 전량이 12일(2026-05-31 ~ 06-12) 안에 만들어졌고, 이후 3개월간 코드 변경이 없다.**
채널 3종(이슈·디스커션·위키)이 전부 열려 있는데 전부 0건이다.

### 4.1 외부 자료 — 2026-08 이후 0건 `[researched: 7개 쿼리 + HN/GeekNews API]`

| # | 출처 | 게시일 | 성격 |
| --- | --- | --- | --- |
| 1 | `dryforge.dev` (`/ko`) | 날짜 표기 없음 | 공식 랜딩 |
| 2 | dbhyeong.github.io 리뷰 | **2026-06-25** | **저자가 "직접 실행하지 않았다"고 명시.** 1차 출처만 확인 |
| 3 | brunch.co.kr/@little-books/577 | 2026-07-15 | #2 의 같은 저자 재게시 |
| 4 | skillsllm.com 등재 | scan 2026-06-22 | 디렉터리 자동 등재(stars 141 스냅샷) |
| 5 | awesome-harness-engineering | 2026-09-14 | 자동 집계. **개명 미반영으로 같은 레포를 2줄로 중복 등재** |

- **Hacker News 0건** — `hn.algolia.com` 히트 66건 전량이 퍼지 매치(drumforge/docforge/dimforge).
  **양성 대조**: `query=claude code plugin` → 1,388건(API 정상).
- **GeekNews 0건.**
- **Reddit / X `[판정 불가]`** — 도메인 접근 차단, 양성 대조 불가. **"없다"고 적지 않는다.**

> **핵심**: 별 230개는 관측이고, *"그러므로 검증된 도구다"* 는 그 위에 얹힌 **미검증 추론**이다
> (`warning-signal.md §측정 9`). 실사용 후기·벤치마크·비판적 리뷰는 확인된 범위에서 **0건**이며,
> 유일한 서술형 자료조차 저자가 실행하지 않았다고 밝혔다.

### 4.2 소유자 이력 `[confirmed]`

`fn-opt` → `precisecutter` → `prekuter` 는 **동일 계정 id `98894019`** 의 개명이다.
근거: 커밋 이메일이 전부 `98894019+fn-opt@users.noreply.github.com` · 구 핸들 조회 404 ·
`github.com/fn-opt/dryforge` → 301 리다이렉트. 계정 생성 2022-02-02, public repo **2개**,
followers 4. 외부 기여자 `dalsoop`(id `264407566`)은 별개 계정이다.

**사실 기록이지 인신 평가가 아니다.** 1인 프로젝트라는 것 자체는 결함이 아니며, 위 §4 의
활동 지표와 함께 읽어야 한다.

### 4.3 라이선스·설치 부작용 `[confirmed]`

MIT. **설치 시 실행되는 스크립트 없음** — 배포물(`claude/`)은 `plugin.json` + `LICENSE` +
마크다운뿐이고 `hooks`/`postinstall` 키가 없다. 서드파티 의존성 0(lockfile 없음).
전역 설정(`~/.claude/*`) 접근 문구 0건.

단 **프로젝트 내 파일 발자국은 크다**: `.dryforge/` 와 **`CLAUDE.md` / `AGENTS.md` / `docs/`** 를
생성·덮어쓴다. 스킬 3종 모두 `Requires git`.

---

## 5. 충돌 지점 — 사실상 없다, 하나 빼고 `[confirmed]`

| 지점 | 판정 |
| --- | --- |
| 스킬·에이전트 **이름 충돌** | **∅** — `go`·`ready`·`migration` 은 킷 21종·superpowers 14종 어느 쪽과도 안 겹침(`comm -12`) |
| 훅 등록 경쟁 | **없음** — dryforge 는 훅을 배포하지 않는다 |
| 자동 발동 경쟁 | **없음** — `disable-model-invocation: true` + 빌드 게이트 |
| 설치 경로 | **없음** — 캐시 키가 `{marketplace}/{plugin}/{version}` 로 분리 |
| `~/.claude/settings.json` 쓰기 | **없음** — dryforge 에 훅·인스톨러 자체가 없다 |
| `CLAUDE.md` 쓰기 | **없음** — 우리 `harness-export` 는 `CLAUDE.md` 를 의도적으로 제외한다 |
| **`AGENTS.md` 쓰기** | **충돌 실재** — 아래 |

### 5.1 유일한 실재 위험 — `migration` 이 `AGENTS.md` 를 덮는다

`go/references/harness-format.md:108` 은 *"Two files, **identical content** … write both
together, byte-for-byte the same"* 를, `migration/SKILL.md:127-129` 는 *"기존 **CLAUDE.md** 가
있으면 `.dryforge/backup/` 으로 백업"* 을 규정한다 — **백업 대상에 `AGENTS.md` 가 없다.**

우리 `harness-export` 는 `AGENTS.md` 안 마커 블록을 소유한다
(`AGENTS.md:7` `<!-- kit:begin rules-v1.4.0 sha256:e524e279… -->`, `:344` `<!-- kit:end -->`).
CLAUDE.md 사본을 AGENTS.md 에 통째로 쓰면 그 블록이 사라지고 `export_harness.py --check` 가
red 가 된다.

**완화**: `migration` 의 ELICIT 단계가 기존 파일 처분을 사용자 승인에 붙인다 — 조용한
덮어쓰기는 아니다. **그럼에도 이 레포에서 `migration` 을 실행하지 않는다.**

### 5.2 이름 충돌은 치명적이지 않다 — 양성 대조 있음 `[confirmed]`

킷 ∩ superpowers 에 `brainstorming` **1건**이 겹치는데, 이 세션에 두 플러그인이 동시
로드돼 있고 호스트가 `hiway-kit:brainstorming` / `superpowers:brainstorming` 으로
네임스페이스해 **둘 다 살아 있다.**

---

## 6. 권고

1. **superpowers 는 그대로 둔다.** 빼는 것이 dryforge 와 무관하고, 빼도 기능이 바뀌지 않는다.
2. **dryforge 를 이 레포에 붙이지 않는다.** 충돌은 거의 없지만 얻는 것이 없다 — 우리가 가진
   축(훅 집행·게이트·eval·에이전트·보안)이 저쪽에 전부 없고, 저쪽의 핵심 주장은 검사되지 않는
   산문이다.
3. **`ready` 의 기획 정련 설계는 흡수 대상이다.** 18KB elicitation + 근거 3필터 +
   intent-completeness 독립 검증은 우리 `clarify-requirements`(P0 질문 목록 수준)보다 앞선다.
   **도구를 채택하지 말고 설계를 가져온다** — `native-watch`/`self-improve` 가 그 경로다.
4. 체감이 필요하면 **버리는 레포에서 `ready` 만** 돌린다. 이 레포에서는 안 된다(§5.1).

---

## 7. `[미확인]` · `[판정 불가]`

- `[판정 불가]` Reddit · X 언급 유무 — 도메인 접근 차단, 양성 대조 불가.
- `[미확인]` 스타 획득 시점 분포 — REST/GraphQL stargazer 조회가 이 환경에서 전면 불가.
  **양성 대조로 환경 제약임을 확인**(대형 레포에도 동일 실패). 제3자 스냅샷(141 → 214 → 230)만 있다.
- `[미확인]` `subscribers_count: 1` 의 정체(소유자 본인 여부) — 목록 조회 불가.
- `[미확인]` dryforge 스킬의 **런타임 실동작** — 전 과정 읽기 전용이었고 설치·실행하지 않았다.
  §3·§5 의 파일 발자국은 SKILL.md 텍스트 기준이다.
- `[미확인]` Claude Code 가 `disable-model-invocation: true` 스킬의 description 을 세션 시작
  로스터에 적재하는지 — 적재하면 1.4 KB, 아니면 0 에 가깝다. §3.2 수치는 **상한**이다.
- `[미확인]` 개명 커밋이 기존 설치본에 전파되는지(마켓플레이스 재-add 동작 미검증).
- `[미확인]` 세 플러그인 **동시 설치 실측** — §5 는 정적 문서·구조 대조다. 유일한 실행 증거는
  킷 ↔ superpowers 동시 로드(§5.2).

## 관련

- `docs/conventions/warning-signal.md` — §측정 9(관측 위에 얹힌 추론을 따로 센다)가 §4 판정의 틀
- `docs/research/2026-08-27-superpowers-distribution.md` — superpowers 배포 구조 선행 조사
- `docs/research/2026-09-08-plugin-directory-status.md` — 카탈로그 상류 정지(§4 미등재 해석의 배경)
