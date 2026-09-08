# 커뮤니티 플러그인 카탈로그 실태 조사 (2026-09-08)

> **왜 조사했나.** 사용자가 *"직접 마켓플레이스 경로는 의미 없다 — 다른 사람들은 앤트로픽
> 커뮤니티 카탈로그만 본다"* 고 지적했다. 그 전제로 배포 경로를 전수 실측했더니, 우리
> 항목이 **v2.12.3(2026-08-09)** 에 멈춰 있었다. 원인이 우리에게 있는지 판정하는 것이
> 이 조사의 목적이다.
>
> 값에는 `[confirmed]` / `[researched: 출처, n=표본]` / `[unresolved]` 를 붙인다.
> 추측으로 채우지 않는다.

## 결론 세 줄

1. **우리 결함이 아니다.** pin 전진을 수행하는 상류 워크플로가 **꺼져 있다**.
2. **카탈로ג 운영 전체가 멈춰 있다** — bump·신규 등재·PR 머지 전부. 자매 카탈로그는 정상이다.
3. **등재 절차가 실제로 바뀌었다** — 제출 폼이 둘로 갈렸고, 우리 문서는 한쪽만 알고 있었다.

---

## 1. pin 이 멈춘 기전 `[confirmed]`

카탈로그의 pin 전진은 `anthropics/claude-plugins-community` 의 워크플로
**`Bump Plugin SHAs`** 가 수행한다(`.github/workflows/bump-plugin-shas.yml`, 매일
07:23 UTC cron). 그 워크플로는 커밋을 직접 하지 않고 **플러그인마다 PR 을 연다**
(`pr-mode: per-entry`) — 사람이 머지해야 반영된다.

| 확인 | 값 | 근거 |
| --- | --- | --- |
| 워크플로 상태 | **`disabled_manually`** | `gh api repos/anthropics/claude-plugins-community/actions/workflows` |
| 마지막 실행 | **2026-08-13** (이후 0회) | `gh run list -w bump-plugin-shas.yml` |
| 우리 항목이 `freeze-shas.txt` 에 있나 | **없다** | `.github/freeze-shas.txt` 전문 확인 (49개 slug) |
| 막힌 bump PR | **없다** | 열린 PR 11건 중 `code-kit` 0건 |

**8/24 에 `bump(qodo)` 가 머지된 것이 모순처럼 보이지만 아니다** — 8/13 실행이 만든 PR 들을
사람이 며칠에 걸쳐 머지했고 그 마지막이 8/24 다. 이후로는 새로 열리는 PR 이 없다.

## 2. 정지 범위 — 카탈로그 전체다 `[confirmed]`

### 2.1 기존 항목 pin `[researched: GitHub API, n=60 무작위 표본]`

핀된 2,274개 항목 중 60개를 무작위 표본(seed 고정)으로 업스트림 HEAD 와 대조했다.

| 구분 | 건수 |
| --- | --- |
| 핀 = 업스트림 HEAD | 44 |
| 뒤처짐 | 15 |
| 조회 불가(레포 삭제·비공개 추정) | 1 |

**"핀=HEAD 44건" 을 "정상 작동" 으로 읽으면 오독이다** — 그 항목들은 업스트림 자체가 몇
달째 움직이지 않은 휴면 레포다. 따라갈 것이 없어서 최신인 것이다.

뒤처진 15건을 **업스트림 마지막 커밋 날짜**로 가르면 판정이 나온다:

- **11건: 업스트림이 2026-08-14 이후에도 움직였는데 전부 미반영.**
  스윕이 살아 있었다면 잡혔어야 할 것들이다. `tavily`(핀 06-04 → HEAD 09-04),
  `apollo-mcp`(08-10 → 09-07), `wordpress-mcp`(06-09 → 08-26),
  `email-assistant`(03-16 → 08-25), `teamcity-cli`, `epic-harness` 등.
- 4건: 업스트림 마지막 커밋이 8/13 이전 — 스윕 중단 **이전부터** 이미 뒤처져 있었다
  (그중 `mumo` 는 실제로 `freeze-shas.txt` 동결 목록에 있다).

**업스트림이 8/13 이후 움직인 항목 11건 중 bump 된 것은 0건이다.**
우리가 164커밋 뒤처진 것은 특별히 나쁜 축도 아니다 — `email-assistant` 는 5개월,
`tavily` 는 3개월 뒤처져 있다.

### 2.2 신규 등재 `[confirmed: marketplace.json 커밋 800건 전수]`

`marketplace.json` 커밋 800건(2026-07-29 ~ 08-24)을 전수 분류했다. 793건이 `bump`,
나머지가 등재·정리다. 등재 이력:

```
2026-07-30   Add 25 community plugins (일괄 배치)
2026-08-06   Add prismatic-skills
2026-08-07   Add credible / cala / meticulous / xsolla-ai-kit   ← 파이프라인 일괄 등재 마지막
2026-08-21   Add eli5                                          ← 신규 등재 마지막(기여자 PR 수동 머지)
그 이후      없음
```

### 2.3 사람 손 `[confirmed]`

- 레포 전체 최종 커밋: **2026-08-24** (경로 무관). 이후 15일째 0건.
- 열린 PR **11건**, 마지막 머지는 **2026-08-24**(#2373).
- 그중 **#2355 `Add referodesign` 이 2026-08-11부터 열린 채**다 — 신규 등재 요청이
  한 달 가까이 처리되지 않고 있다는 가장 분명한 신호.

### 2.4 자매 카탈로그는 정상이다 — 조직 전체 중단이 아니다 `[confirmed]`

| 레포 | 최종 커밋 | 상태 |
| --- | --- | --- |
| `anthropics/claude-plugins-community` | **2026-08-24** | 정지 |
| `anthropics/claude-plugins-official` | 2026-09-04 (`bump/rill`·`bump/resend` 머지) | **정상** |
| `anthropics/knowledge-work-plugins` | 2026-09-04 (`bump/unity`·`bump/figma` 머지) | **정상** |

**community 카탈로그만 멈췄다.** 원인은 레포 밖에서 판정할 수 없다 `[unresolved]` —
내부 파이프라인 정책 변경인지, 일시 중단인지, 스크리닝 개편 중인지 구분할 근거가 없다.
**관측되지 않은 것을 추측으로 채우지 않는다**(`docs/conventions/warning-signal.md`).

## 3. 등재 절차의 실제 변경 `[researched: code.claude.com/docs/en/plugins, n=1 공식 문서]`

### 3.1 제출 폼이 **둘로 갈렸다** — 우리 문서는 한쪽만 알고 있었다

| 경로 | URL | 자격 |
| --- | --- | --- |
| claude.ai | `claude.ai/admin-settings/directory/submissions/plugins/new` | **Team/Enterprise 조직 + 디렉토리 관리 권한**(조직 Owner 기본 보유) |
| Console | `platform.claude.com/plugins/submit` | **조직에 속하지 않은 개인 저자** |

우리 문서는 Console URL 만 적고 있었다. 개인 저자에게는 그쪽이 맞으므로 **결과적으로
틀리지 않았지만**, 자격 조건이 문서에 없어 Team/Enterprise 사용자가 이 문서를 따라오면
잘못된 경로를 쓴다.

### 3.2 공식 문서가 제출 전 `claude plugin validate` 를 **지시한다**

> *"Run `claude plugin validate ./your-plugin` locally before you submit. **The review
> pipeline runs the same check on every submission**, along with automated safety
> screening. Warnings don't fail validation; add `--strict` to treat them as errors."*

**이것이 §19 게이트의 근거를 공식화한다.** 우리가 추론으로 세운 것("bump 가 이 검사를
돌리므로 미리 걸어야 한다")이 문서에 명시돼 있었다. 경고는 실패가 아니라는 점도 확인됐다 —
그래서 우리가 `--strict` 로 도는 것은 **상류보다 엄격한 선택**이지 요구사항이 아니다.
그대로 유지한다: 소비자보다 느슨할 이유가 없다.

### 3.3 문서는 여전히 자동 전진·nightly 를 단언한다 `[상충 기록]`

> *"CI bumps the pin automatically as you push new commits to your repository. The
> public catalog syncs nightly from the review pipeline."*

**§1·§2 의 실측과 정면으로 상충한다.** 상충을 한쪽으로 정리하지 않고 **상충 자체를
기록한다** — 문서는 설계 의도를, 실측은 현재 상태를 말한다. 둘 다 참일 수 있다(의도는
살아 있고 실행만 멈춘 상태). 우리 문서에는 **실측**을 적는다.

## 4. 부수 발견 — `claude plugin details` 의 always-on 추정은 에이전트를 세지 않는다

`claude plugin details <name>` 이 컴포넌트 인벤토리와 **projected token cost** 를 낸다.
우리 플러그인(2.19.0 설치본)에 돌린 결과:

```
Component inventory
  Skills (21)  ...
  Agents (0)          ← 실제로는 33종
Projected token cost
  Always-on:   ~1,518 tok
```

- **`Agents (0)`** — 우리 에이전트는 `agents/<category>/<name>.md` 로 **중첩**돼 있다.
  실제 로드는 정상이다(`claude-code-kit:dev:explore-codebase` 형태로 호출 가능,
  `claude plugin validate agents/` 도 통과). 즉 **집계만 0** 이다 `[confirmed]`.
- 따라서 **always-on 추정치가 에이전트 설명을 포함하지 않는다.** 실측: 33종의
  frontmatter `description` 합계 **7,745B ≈ 1,936 tok** — 보고된 always-on 전체(1,518 tok)
  보다 크다.

**함의**: 우리 §16 주입 예산(core 규범 + WORKFLOW = 10,240B)은 **에이전트 설명을 세지
않는다.** 그 축이 실제로는 비슷한 크기로 존재한다. 예산 재설계 시 반영할 것.
`[unresolved]` — 중첩 레이아웃이 집계 0 의 원인인지는 평평한 레이아웃으로 대조해야
확정되고, 그 실험은 아직 하지 않았다.

## 5. 우리가 취한 조치

| 조치 | 위치 |
| --- | --- |
| `marketplace.json` 미지 필드 `repository` 제거 | 두 레포 (v3.6.0 / cck 2.20.0 이후 커밋) |
| `claude plugin validate --strict` 를 게이트 §19 + CI 로 | 두 레포 |
| "nightly 전파" 서술 제거, 실측으로 교체 | 두 레포 `CLAUDE.md`·`README.md`·`marketplace-submission.md` |
| 제출 폼 2종·자격 조건 기록 | `docs/marketplace-submission.md` |

**우리가 통제할 수 있는 것은 "재개되는 순간 green 인가" 뿐이다.** pin 을 움직일 방법은
없고, 재제출은 신규 등재 경로이지 기존 항목의 pin 을 옮기지 않는다.

## 재현 방법

```bash
gh api repos/anthropics/claude-plugins-community/actions/workflows \
  --jq '.workflows[] | "\(.state)\t\(.name)"'
gh run list -R anthropics/claude-plugins-community -w bump-plugin-shas.yml -L 5
gh api repos/anthropics/claude-plugins-community/contents/.github/freeze-shas.txt \
  --jq '.content' | base64 -d
gh pr list -R anthropics/claude-plugins-community --state open --limit 20
curl -s https://raw.githubusercontent.com/anthropics/claude-plugins-community/main/.claude-plugin/marketplace.json
```
