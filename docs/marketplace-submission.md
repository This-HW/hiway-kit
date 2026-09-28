# Marketplace Submission & Community Listing

Submit at: https://platform.claude.com/plugins/submit

> Note: 외부 제출의 도착지는 **community 카탈로그**(`anthropics/claude-plugins-community`)다.
> 위 웹 폼으로 제출하면 스크리닝 후 community 카탈로그에 등재된다.
> `anthropics/claude-plugins-official`은 Anthropic 자체 큐레이션 전용으로 외부
> PR/신청 경로가 없다 — 이 문서의 "제출"은 전부 community 등재를 향한다.

## 2026-09-28 — `hiway-kit` 을 Claude 디렉토리 포털에 제출 (현재 상태)

2026-09-25 Anthropic 이 디렉토리 제출 포털을 공개했다
([공지](https://claude.com/blog/build-plugins-for-claude) · [문서](https://claude.com/docs/plugins/submit)).
아래 "커뮤니티 카탈로그" 절들은 그 이전 경로의 기록이다.

| 항목 | 값 |
| --- | --- |
| 제출 경로 | claude.ai → Directory → **Submissions** → 새 제출 → 플러그인 번들 (Max 플랜 개인 계정 `thisyj.work@gmail.com`) |
| 소스 | `This-HW/hiway-kit` · 경로 `plugins/common` · 브랜치 `main`(추적) · 제출 시점 `393e124` |
| 포털 검증 | **통과** — 7 checks, 경고 3, 정책 보류 3 |
| 게재 대상 | **Claude Code 만** (Cowork·채팅 앱 해제 — 훅·에이전트·Python 스크립트가 그 표면에서 검증된 적 없음) |
| 데이터 처리 답 | 개인정보 읽기/저장 No · 선언 외 전송 No · 보존 없음 · 18세 미만 대상 No (근거: README "Data handling") |
| 업데이트 | **GitHub push webhook 연결**(hook id `686731192`, ping 200) · 자동 게시 on(첫 버전은 심사자 승인 필요) |
| 상태 | 보안 스캔 → 사람 심사 대기. 결과는 플러그인 페이지·연락 메일로 온다 |

**정책 보류 3건과 판단** (포털 원문 요지):

1. *사용자 머신의 자격증명 사용* — `skills/mcp-builder/SKILL.md` 가 MCP 서버 예시 코드에서 `API_KEY`
   환경변수와 `modelcontextprotocol.io` 링크를 함께 담는다. 스캐폴딩 **설명 예시**다. 문구를 정리하면
   보류가 사라진다(후속 후보).
2. *같은 항목의 교차 판정* — `auto-dev` 의 `checklist pass <id>` 를 비밀번호 도구 `pass` 로, `review` 의
   `$ARGUMENTS` 를 외부 전송으로 읽었다. **오탐.**
3. *검증기가 따라가지 못한 스크립트* — Python 훅 5개. 훅 플러그인의 필연이다. 포털 안내대로 심사자가 읽는다.

경고 "내려받아 바로 실행" 2건(`eval-forge`, `hooks/examples/README.md`)은 `*verify*.sh` 같은 **파일명 패턴
표기**를 오인한 것 — 실제 다운로드·실행 명령은 없다. 경고 "아이콘 없음"은 GitHub 아바타로 대체된다.

**v4.0.4 재스캔(2026-09-28 21:0x KST, `5c9c72d`)** — 보안 스캔 통과, "Version passed, ready to publish", 사람 심사
대기. 남은 발견: 경고 *사용자 머신의 자격증명 사용*(이번엔 `.claude-plugin/plugin.json` 에 귀속 — 플러그인 안에서
환경변수 자격증명을 읽는 코드는 grep 0건이고, 자격증명 이름은 `protect-sensitive` 훅의 탐지 패턴과 그 테스트
픽스처에만 있다), 경고 *내려받아 바로 실행* 2건(위와 같은 오인, 문서 전용이라 포털 안내상 조치 불요), 정보 *훅 사용*,
정보 *이미지 무검사 통과*(4.0.4 의 `assets/icon.png`).

**v5.0.0 재스캔(2026-09-29 00:1x KST, `3f9d191`)** — 보안 스캔 통과, 사람 심사 대기. 남은 발견: 경고 *사용자 머신의
자격증명 사용*(여전히 `.claude-plugin/plugin.json` 귀속 — v5 에서 가짜 키 테스트 픽스처를 배포물 밖 `tests/hooks/` 로
옮겼는데도 남았으므로 **그 픽스처가 원인이 아니었다**), 경고 *내려받아 바로 실행* 1건(2건→1건: `eval-forge` 가 레포 전용으로
빠지며 사라졌고 `hooks/examples/README.md` 만 남음 — 그 문서의 `uv run`·`npm publish`·`docker push` 같은 **명령 이름 표기**
로 보인다. 포털 안내상 문서 전용이면 조치 불요라 추측으로 문구를 바꾸지 않았다), 정보 *훅 사용*·*이미지 무검사 통과*.

**스캔 경고 원인 실측(2026-09-29, v5.0.1~5.0.3)** — 포털의 **Validate**(Submit new → Plugin bundle → 저장소 칸에
`https://github.com/<owner>/<repo>/tree/<branch>/<path>` → Validate, 저장·제출 없이 검사만)를 조사용 브랜치에 돌리면
**근거 파일·문구까지** 나온다(Review 탭은 제목만 보여 준다). 이걸로 이분 탐색했다(브랜치 16개, 끝나고 전부 삭제):
- *내려받아 바로 실행* = `hooks/examples/README.md` 의 단어 `` `eval` `` → 5.0.2 에서 제거, 재검증으로 소멸 확인.
  (5.0.1 의 `uv run` 추정은 틀렸다.)
- *사용자 머신의 자격증명 사용*(정책 보류) = "환경 읽기"+"밖으로 보내기" 두 표면의 결합. 표기를 걷어낼 때마다 근거가 옮겨 가
  최종적으로 `protect-sensitive` 의 **차단 경로 목록**(`~/.ssh`·`~/.aws`) 하나로 양쪽이 성립 → 보안 기능이라 코드 유지.
  배포 README 에 경로를 **글자 그대로** 적으면 근거가 하나 더 생긴다(5.0.2 에서 밟고 5.0.3 에서 되돌림).
  포털 안내("무관하면 제출에 밝혀라")에 따라 2026-09-29 00:40 KST `directory@anthropic.com` 에 근거와 함께 설명 메일.
- *검증기가 따라가지 못한 스크립트*(정책 보류) = Python 훅 5개. 포털 안내상 심사자가 읽는 항목.

**목록 정보는 제출 시점에 고정된다.** Listing 탭이 각 행의 출처를 `plugin.json key:` 로 밝힌다 — `icon`,
`documentationUrl`, `supportUrl`, `privacyPolicyUrl` 이 비어 있어 아이콘은 GitHub 아바타로 대체됐다. 그러나 포털 원문이
*"Newer versions don't update them here"*, 문서가 *"name and short description follow the live version"* 이므로 지금
키를 더해도 이 제출의 목록은 바뀌지 않는다. 게다가 Claude Code 매니페스트 스키마에 없는 키라 `claude plugin validate`
가 경고하고 로드 시 제거한다. **그래서 넣지 않았다** — 공개 후 목록 편집 수단이 생기면 그때 채운다.

**전임 킷 정리(2026-09-28)**: 관리 화면에 `claude-code-kit` 제출 2건(`597867fb-…` needs changes,
`bc35fcf0-…` 검사 통과·미공개)이 남아 있었다. 포털엔 셀프 삭제가 없어(메뉴는 "Contact Anthropic" =
`mailto:directory@anthropic.com` 뿐) **삭제 요청 메일을 보냈다** — 두 제출 철회·삭제, 미공개 건 공개 금지,
구 커뮤니티 카탈로그의 `claude-code-kit` 항목(v2.12.3 `292ba07e` 고정) 제거. 처리 결과는 연락 메일로 온다.

**필수 동의 4개 중 "선언된 구성 밖에서 자격증명 유출·코드 실행 없음"** 은 포털이 스스로 요약에
"Runs code locally: 5 hooks" 로 훅을 선언된 로컬 실행으로 표시하므로, 선언되지 않은 실행·유출에 관한
진술로 판단하고 확인했다(배포 훅 네트워크 호출 0 — grep 확인).

## Status (구 커뮤니티 카탈로그 — 전임 킷 기록)

- **v2.7.0** tagged and ready — 2026-06-14 (core-only consolidation + native foundation + git-subdir distribution)
- Recovery point before consolidation: tag `v2.6.0-with-domains`
- [x] Submit via web form — 2026-06-14
- [x] **등재 확인** — 2026-07-07: `anthropics/claude-plugins-community` 카탈로그
  (당시 2,199개)에 `claude-code-kit` 등재 확인.
- [x] **pin 자동 전진 메커니즘 실측 확정** — 2026-07-07, 카탈로그 레포 커밋 히스토리 분석:
  - 카탈로그는 `bump(<plugin>): old → new` 커밋(자동 PR)으로 기존 항목 pin을 전진시킨다.
    우리 항목 실례: `bump(claude-code-kit): 0a5629e0 → d7f80c92` (2026-07-03T17:58Z, #754).
  - 배치 주기(2026-07 관측): 매일 ~17:00–18:30 UTC (07-02·03·04·06 관측; 07-05 스킵).
    **이 관측은 2026-09-08 재실측에서 무너졌다 — 아래 절 참고.**
  - 버전 무변경 커밋(예: chore)은 bump되지 않는 것으로 관측됨 — 릴리스 체크리스트의
    버전 범프 규율이 카탈로그 전파의 전제.
  - 재제출 불필요. 즉시성이 필요하면 직접 마켓플레이스 경로(당시 `This-HW/claude-code-kit`).

> 확인 방법: 아래 raw 카탈로그에서 `claude-code-kit` 검색.
> https://raw.githubusercontent.com/anthropics/claude-plugins-community/main/.claude-plugin/marketplace.json

## 2026-09-08 재실측 — pin 자동 전진을 **신뢰할 수 없다**

위 2026-07 관측(매일 배치, 재제출 불필요)은 **더 이상 성립하지 않는다.** 전임 킷
`claude-code-kit` 항목을 기준으로 실측했다:

| 관측 | 값 |
| --- | --- |
| 그 항목 마지막 bump | **2026-08-09** — `d0a5752c → 292ba07e` (#1961), 즉 **v2.12.3** |
| 그 이후 미반영 릴리스 | 2.13.0 → **2.20.0** (164 커밋) |
| `marketplace.json` 커밋 **300개** 중 그 항목 bump | **1건**(위 8/9 건) |
| 카탈로그 미러 레포 최종 커밋(경로 무관) | **2026-08-24** — 이후 전체가 조용 |
| 카탈로그 README 의 서술 | 여전히 *"synced nightly"* |

**두 가지가 겹쳐 있다.** 8/9~8/24 사이 카탈로그는 다른 항목(`qodo`·`inkbox` 등)을 bump
하고 있었으므로 **그 구간엔 그 항목만 누락**됐고, 8/24 이후로는 **미러 전체가 멈췄다.**

**근본 원인을 특정했다.** pin 전진 워크플로 `Bump Plugin SHAs` 가
**`disabled_manually`** 이고 **2026-08-13 이후 0회 실행**됐다. 우리 항목은
`freeze-shas.txt` 에 없고 막힌 bump PR 도 없다.

**정지 범위는 카탈로그 전체다** `[researched: GitHub API, n=60 무작위 표본]`:
업스트림이 2026-08-14 이후 움직인 항목 **11건 중 bump 된 것 0건**
(`tavily` 3개월·`email-assistant` 5개월 뒤처짐). 신규 등재도 8/21 이 마지막이고,
`Add referodesign` PR(#2355)이 **8/11부터 열린 채**다. 레포 전체 커밋이 8/24 이후 0건.

**자매 카탈로그는 정상이다** — `claude-plugins-official`·`knowledge-work-plugins` 는
2026-09-04 에도 bump 를 머지했다. **community 카탈로그만 멈췄다.**

왜 멈췄는지는 `[unresolved]` — 정책 변경인지 일시 중단인지 밖에서 구분할 근거가 없다.
전수 근거와 재현 명령: **`docs/research/2026-09-08-plugin-directory-status.md`**

**`hiway-kit` 제출에 대한 함의 — 두 가지.**

1. **제출이 승인돼도 즉시 보이지 않을 수 있다.** 등재 확인을 "제출 다음 날" 로 잡지 마라.
2. **등재 후에도 pin 은 크게 뒤처질 수 있다.** 릴리스 안내에서 카탈로그 경로를 "최신" 이라
   부르지 않는다. 즉시성이 필요한 사용자는 직접 마켓플레이스로 보낸다.

**뜻밖의 부수 관측**: 전임 킷의 pin 이 크게 뒤처져 있던 덕에, 2026-09-07 그 레포의 플러그인
이름이 일시적으로 `hiway-kit` 이었던 구간이 **카탈로그 사용자에게 노출되지 않았다.**
등재명과 실물이 어긋난 상태였는데 아무도 그것을 받지 못했다 — **운이지 설계가 아니다.**
D-54 의 레포 분리는 이 운에 기대지 않기 위한 결정이다.

## Submission Info — 전임 킷 `claude-code-kit` 의 등재 기록

> 아래 표는 **2026-06-14 제출 당시의 고정 기록**이다. 현재 킷(`hiway-kit`)의 제출은
> 맨 아래 "개명 — 재제출" 절이 다룬다. 두 항목은 카탈로그에서 별개 리스팅이다.

| Field | Value |
|---|---|
| Plugin Name | `claude-code-kit` |
| Submitted Version | `2.7.0` (제출 시점 고정 기록 — 현재 버전은 CHANGELOG 참조) |
| Description | Turn any task into production-ready code. Specialized agents automatically handle planning, implementation, code review, and security scanning for any stack. |
| Source Type | `git-subdir` |
| Repository | `This-HW/claude-code-kit` |
| Path | `plugins/common` |
| Ref | `main` (tag: `v2.7.0`) |
| Category | `development` |
| Homepage | https://github.com/This-HW/claude-code-kit |
| License | MIT |
| Author | This-HW (thisyj.work@gmail.com) |

> 참고: `marketplace.json`의 source가 이미 `git-subdir`로 설정되어 있어, 제출 정보와
> 실제 배포 구성이 일치한다.

## Install Commands

`@` 뒤는 마켓플레이스 `name` 필드다(repo 이름이 아니다 — community 카탈로그의 name 은
`claude-community` 로 실측 확인, 2026-07-07).

**현재 킷 `hiway-kit` — 직접 마켓플레이스만 성립한다** (카탈로그 재제출 대기 중):

```bash
/plugin marketplace add This-HW/hiway-kit
/plugin install hiway-kit@hiway-kit
/plugin marketplace update hiway-kit
```

**전임 킷 `claude-code-kit` — 등재돼 있고 v2.21.0 에서 멈춘다** (기록용):

```bash
/plugin marketplace add anthropics/claude-plugins-community
/plugin install claude-code-kit@claude-community
```

## What Gets Installed

`plugins/common` 서브디렉토리 (git-subdir로 sparse-clone):

- **agents** — planning, dev, backend, meta, review 카테고리 (`plugins/common/agents/`)
- **skills** — `plugins/common/skills/` (디렉토리에서 자동 발견 — 매니페스트에 등록부 없음)
- **rules** — `plugins/common/rules/` (session-start 가 티어에 따라 주입)
- **Hooks** (4 events): SessionStart, PreToolUse, PostToolUse, Stop (`hooks/hooks.json`)
- **unit tests** — `pytest` (수치는 CHANGELOG)

> 개수를 여기에 적지 않는다. 이 문서는 `scripts/check_doc_counts.py` 의 검사 대상이
> **아니므로**, 손으로 적은 개수는 조용히 낡는다 — 실제로 그렇게 낡아 있었다
> (16 skills / 13 rules). 검사받지 않는 숫자는 쓰지 않는 것이 유일한 zero-debt 해법이다.

> 단일 core 플러그인. 도메인 플러그인(frontend/infra/ops/data/integration)은 2.7.0에서
> 제거됨 (테스트 0·동결). 필요 시 `v2.6.0-with-domains` 태그에서 복원 가능.

## v2.7.0 Registry Compliance Checklist

- [x] `homepage`, `repository`, `license`, `author.email` in plugin.json
- [x] No forbidden frontmatter fields in any agent
- [x] All skill descriptions in English
- [x] All agents have `model` and `maxTurns` fields
- [x] `hooks/hooks.json` uses exec form (`command` + `args[]`) with `${CLAUDE_PLUGIN_ROOT}` paths
- [x] unit tests passing (v2.7.0 제출 시점 112 — 현재 수치는 CHANGELOG 참조)
- [x] CI validates manifest fields + forbidden fields + pytest (PRs to main + stable)
- [x] CHANGELOG.md documents all changes
- [x] README.md updated (single-plugin, 2-tier)
- [x] `marketplace.json` source = `git-subdir` (remote/versioned distribution)
- [x] `scripts/verify-done.sh` green (definition-of-done gate)

## 개명 — **재제출이 필요하다** (27-6)

> 위 "재제출 불필요"는 **버전 갱신**에 대한 것이다. **이름 변경은 다르다.**

카탈로그 항목은 `claude-code-kit` 이라는 **이름으로 등재**돼 있고, pin 자동 전진은
`bump(<plugin>): old → new` 로 **같은 이름 항목의 커밋만** 옮긴다. 이름이 바뀌면
자동 전진 대상이 아니므로 **새 리스팅으로 제출해야 한다.**

### 사람이 해야 하는 것 (자동화 불가 — 웹 폼)

1. **제출 폼은 둘이고 자격이 다르다** `[researched: code.claude.com/docs/en/plugins, 2026-09-08]`

   | 경로 | URL | 자격 |
   | --- | --- | --- |
   | Console | `platform.claude.com/plugins/submit` | **조직에 속하지 않은 개인 저자** ← 우리 경우 |
   | claude.ai | `claude.ai/admin-settings/directory/submissions/plugins/new` | Team/Enterprise 조직 + 디렉토리 관리 권한 |

   **제출 전 `claude plugin validate ./plugins/common` 을 돌린다** — 공식 문서가
   *"리뷰 파이프라인이 제출마다 같은 검사를 돌린다"* 고 명시한다. 우리는 게이트 §19 가
   `--strict` 로 항상 돌리므로 이미 충족돼 있다.

   `hiway-kit` 으로 **신규 제출**한다:
   - 저장소: `This-HW/hiway-kit` (**새 레포다** — 전임 킷은 `This-HW/claude-code-kit` 에 그대로 남는다)
   - 플러그인 이름: `hiway-kit`
   - 경로: `plugins/common`
2. 구 항목(`claude-code-kit`)은 **지우지 않는다.** 전임 레포에 v2.21.0 최종본이
   그대로 있고 등재명과 플러그인 이름이 일치하므로, 그 리스팅은 계속 유효하다.
   (카탈로그는 읽기 전용 미러라 어차피 직접 PR 로 지울 수 없다 — 직접 PR 은 자동 close 된다.)

### 그때까지의 상태 (정직하게)

- **직접 마켓플레이스**(`This-HW/hiway-kit` → `@hiway-kit`)는 **즉시** 동작한다.
  `main` HEAD 를 반영하므로 재설치하면 v3.0.0 이 온다.
- **커뮤니티 카탈로그**는 구 이름 `claude-code-kit` 을 계속 서빙한다 — 이제 전임 레포의
  **v2.21.0 최종본**이다(껍데기가 아니라 게이트 green 인 유지보수 완료본).
  v2.21.0 은 **버그 하나만** 담은 최종 패치다 — 훅이 최초 설치 판에서 영구 동결되던
  결함(이 킷 v3.8.0 과 같은 것)의 수정. `.private-names` 비공개 이름 가드는
  **이식되지 않았다** — 그건 후속 킷 기능이고 전임 킷은 버그 수정만으로 닫혔다.
  그 경로로 설치한 사용자는 개명을 **자동으로 알 수 없다** — 전임 레포 README 최상단
  배너와 CHANGELOG 의 재설치 절차가 유일한 안내다.
- 이 비대칭은 개명의 **불가피한 비용**이다. 프로브(Q3)가 확인한 대로 `enabledPlugins` 이행이
  수동이므로, 어떤 경로로도 자동 승계는 없다.

### 왜 별칭을 두지 않았나

D-52 참조. 프로브 실측: 구·신 이름이 공존하면 스킬이 **경고 없이 중복 로드**된다.
"기한 있는 폐기 별칭"은 그 중복을 기간만큼 보장하는 것이므로 설계로 성립하지 않는다.
