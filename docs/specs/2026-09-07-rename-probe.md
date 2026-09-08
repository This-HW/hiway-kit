# 마켓플레이스 개명 이행 프로브 (실측) — 2026-09-07

**작성자**: 워커 P1 (27-1) · **기준 커밋**: `c75eb4213f7a1f89911be3ff8c375697b0a2b6f2` (`git rev-parse HEAD`로 착수 전 확인, 일치)
**목적**: D-4가 추측으로 남긴 미결 3문항을 실측(runtime-verified)으로 닫는다. `docs/specs/2026-09-07-hiway-program-design.md`가 SSOT이며, 이 문서는 그 설계가 전제하는
개명 이행 메커니즘의 실제 CLI 동작을 검증한다.

## 방법

- CLI: `claude` 2.1.263 (`claude --version`)
- 이 레포는 건드리지 않았다. `$TMPDIR/rename-probe/` 아래에 스크래치 마켓플레이스
  (`probe-market`)와 가짜 플러그인 2개(`probe-old-name`, `probe-new-name`)를 만들어
  `claude plugin marketplace add` / `install` / `uninstall` / `marketplace remove`로
  실물 왕복했다.
- 정리: 각 단계마다 `~/.claude/settings.json` · `~/.claude/plugins/installed_plugins.json` ·
  `~/.claude/plugins/known_marketplaces.json`을 사전 백업했고, 작업 종료 시
  `claude plugin uninstall`×2 → `claude plugin marketplace remove probe-market` →
  잔존 캐시 디렉터리(`~/.claude/plugins/cache/probe-market/`) 수동 삭제까지 실행해
  실사용자 상태에 `probe-*` 흔적이 0건임을 `diff`/`grep`으로 재확인했다(아래 "정리 검증" 참고).

## Q1. 구 이름 항목을 폐기 표시로 남긴 채 신 이름으로 설치가 되는가?

**실행**:
1. `probe-old-name`을 설치 (`claude plugin install probe-old-name@probe-market -y`) → 성공.
2. 스크래치 `marketplace.json`에서 카탈로그 항목을 `probe-old-name` → `probe-new-name`으로
   교체(같은 소스 디렉터리를 가리킴, 실제 개명 시나리오 그대로) 후
   `claude plugin marketplace update probe-market` 실행.
3. `claude plugin list` 재조회.

**출력**:
```
❯ probe-old-name@probe-market
  Version: 0.1.0
  Scope: user
  Status: ✘ failed to load
  Error: Plugin probe-old-name not found in marketplace probe-market
```
`enabledPlugins`(`settings.json`)에는 여전히 `"probe-old-name@probe-market": true`가
그대로 남아 있었다(변경 없음).

**판정**: **아니다.** 카탈로그에서 구 이름을 빼고 신 이름을 추가하는 것만으로는 "폐기
표시(deprecated)"가 붙지 않는다. 구 이름 설치본은 카탈로그에서 못 찾는 **에러 상태**
(`✘ failed to load`)로 깨진다 — 우아한 이행 마커가 아니라 고장 신호다. 신 이름으로의
설치는 별도의 명시적 `claude plugin install probe-new-name@probe-market` 호출이 필요하며,
자동으로 일어나지 않는다.

`[confirmed: runtime-verified]`

## Q2. 구 이름·신 이름 설치본이 공존할 때 스킬·에이전트가 중복 등록되는가?

두 가지 하위 시나리오를 나눠 실측했다 — 결과가 갈렸기 때문에 하나로 뭉뚱그릴 수 없다.

### 2a. 카탈로그 항목 이름만 다르고 `plugin.json`의 자체 `name` 필드는 동일한 경우

두 카탈로그 항목(`probe-old-name`, `probe-new-name`)이 **같은** `plugin-old/` 소스
디렉터리(내부 `plugin.json.name = "probe-old-name"`)를 가리키게 하고 둘 다 설치·활성화한 뒤
`claude -p ... --debug --debug-file`로 실제 세션을 띄워 디버그 로그를 확인했다.

```
[DEBUG] Skipping duplicate plugin skill 'probe-old-name:probe-skill' —
  .../plugin-old/skills/probe-skill/SKILL.md already loaded as 'probe-old-name:probe-skill'
[DEBUG] Total plugin skills loaded: 34 (1 duplicate/user-owned entries skipped)
```

**판정**: 이 경우는 중복 등록되지 **않는다** — 디둡 키가 `<plugin.json의 name 필드>:<스킬명>`이라서
카탈로그 항목 이름이 달라도 내부 `plugin.json.name`이 같으면 하나로 합쳐진다.

### 2b. `plugin.json`의 자체 `name` 필드도 함께 바뀐 경우(실제 "패키지 개명"에 더 가까운 시나리오)

`probe-new-name`을 별도 디렉터리(`plugin-new/`, 내부 `plugin.json.name = "probe-new-name"`,
동일 내용의 `probe-skill` 포함)로 재설치한 뒤 다시 디버그 세션을 띄웠다.

```
[DEBUG] Loaded 1 skills from plugin probe-old-name default directory
[DEBUG] Loaded 1 skills from plugin probe-new-name default directory
[DEBUG] Total plugin skills loaded: 37 (0 duplicate/user-owned entries skipped)
```

**판정**: **그렇다, 중복 등록된다.** `plugin.json`의 `name` 필드 자체가 바뀌면(진짜 개명)
디둡 키가 달라져 동일 내용·동일 스킬명(`probe-skill`)이 **별개 엔트리 2개**로 로드된다.
경고나 충돌 메시지는 전혀 없었다 — 조용히 중복된다.

**결론(두 하위 시나리오 종합)**: 중복 등록 여부는 **카탈로그 항목 이름이 아니라
`.claude-plugin/plugin.json`의 `name` 필드**로 갈린다. claude-code-kit의 실제 개명(레포명·
마켓플레이스 항목명 변경 + 플러그인 자체 `name` 필드 변경까지 포함하는 경우)에서는 2b가
적용되어, 이행 기간 동안 구·신 설치본이 공존하면 **스킬이 실제로 중복 로드**된다.

`[confirmed: runtime-verified]`

## Q3. `enabledPlugins` 키 이행이 자동인가 수동인가?

Q1 실험 도중 `settings.json.enabledPlugins`를 매 단계 스냅샷했다.

| 단계 | `enabledPlugins`의 probe 관련 키 |
| --- | --- |
| `probe-old-name` 설치 직후 | `{"probe-old-name@probe-market": true}` |
| 카탈로그를 구→신으로 교체 + `marketplace update` (신규 설치 전) | `{"probe-old-name@probe-market": true}` — **불변** |
| `probe-new-name` 설치 후 | `{"probe-old-name@probe-market": true, "probe-new-name@probe-market": true}` — **구 키가 그대로 남고 신 키가 추가만 됨** |

**판정**: **수동이다.** 카탈로그가 개명되어도, 심지어 구 이름 설치본이 "찾을 수 없음"
에러로 깨진 뒤에도 `enabledPlugins`의 구 키는 자동으로 지워지거나 신 키로 rewrite되지
않는다. 신 키는 사용자(또는 이행 스크립트)가 `claude plugin install new-name@market`을
명시적으로 실행해야만 추가된다. 방치하면 깨진 구 키가 `settings.json`에 영구 잔존한다
— `claude plugin uninstall old-name@market -y`로 명시적으로 지워야 한다(별도로 실측:
카탈로그에서 이미 사라진 이름이어도 `installed_plugins.json`에 캐시 기록이 남아 있으면
`uninstall`은 정상 동작했다).

`[confirmed: runtime-verified]`

## 부가 관찰 (질문 범위 밖, 실측 중 우연히 확인됨)

- `claude plugin uninstall`은 캐시 디렉터리를 즉시 삭제하지 않고 `.orphaned_at` 마커
  파일을 남긴다(`~/.claude/plugins/cache/<market>/<plugin>/<version>/.orphaned_at`) —
  실제 삭제는 별도의 GC/prune 경로가 담당하는 것으로 보인다. 개명 이행 스크립트가 있다면
  이 마커를 신뢰해 "이미 정리됨"으로 오판하지 않도록 주의.
- 스크래치 마켓플레이스 조작(`claude plugin marketplace update probe-market`,
  `claude plugin install/list`, `claude -p` 세션 기동) 도중 `claude-code-kit@claude-code-kit`
  마켓플레이스가 `autoUpdate: true`라서 2.18.0 → 2.19.0으로 **자동 갱신**됐다(현재 레포
  HEAD와 `gitCommitSha`가 일치 — 정상적인 백그라운드 자동 업데이트이지 이 프로브가
  유발한 손상이 아니다). 이 변화는 되돌리지 않았다 — 되돌리면 오히려 실사용자 설치본을
  구버전으로 **퇴행**시키는 조작이 되므로, "훼손 금지"의 취지에 어긋난다고 판단했다.

## [unresolved] 확인하지 못한 것

- **에이전트(agent) 중복 등록**은 실측하지 않았다 — 스크래치 플러그인에 스킬만 넣고
  에이전트는 넣지 않았다. 다만 스킬과 마찬가지로 플러그인 매니페스트 로더를 공유할
  가능성이 높아 Q2 결과가 유추적으로는 적용될 것으로 보이나, **에이전트 로더 코드 경로를
  직접 관측하지 않았으므로 단정하지 않는다.**
- **실제 claude-code-kit 레포의 마켓플레이스 카탈로그가 "신 이름"으로 실제 개명될 때
  구체적으로 어떤 필드들이 바뀌는지**(마켓플레이스 항목의 `name`만인지, `plugins/common/
  .claude-plugin/plugin.json`의 `name`도 함께인지)는 이 프로브의 범위가 아니다 — 이는
  `docs/specs/2026-09-07-hiway-program-design.md`가 결정할 설계 사항이며, 위 Q2 결과는
  "만약 후자까지 바뀐다면 중복 로드가 실제로 발생한다"는 사실만 제공한다.
- **정식 마켓플레이스(GitHub 소스, `source: "git-subdir"`)에서의 동일 실험**은 하지
  않았다 — 로컬 `directory` 소스로만 검증했다. `claude plugin marketplace add/update`의
  카탈로그 파싱·설치 로직은 소스 종류와 무관하게 공유되는 것으로 보이나(같은
  `.claude-plugin/marketplace.json` 스키마·같은 `installed_plugins.json`/`enabledPlugins`
  경로), git 소스 특유의 캐싱/버전 고정 차이가 있을 가능성은 배제하지 않는다.

## 정리 검증 (실사용자 상태 훼손 없음 확인)

- `claude plugin marketplace list` — `probe-market` 없음(확인).
- `~/.claude/plugins/cache/` — `probe-market` 없음(확인, 잔존 `.orphaned_at` 디렉터리
  수동 삭제 완료).
- `settings.json` / `installed_plugins.json` / `known_marketplaces.json` —
  사전 백업과 `diff`하여 `probe-*` 관련 키가 0건임을 확인. 위에 기록한 `claude-code-kit`
  자동 업데이트(2.18.0→2.19.0)와 그에 따른 `lastUpdated` 타임스탬프 변화만 차이로
  남았으며, 둘 다 프로브가 아니라 기존에 켜져 있던 `autoUpdate: true`의 정상 동작이다.
