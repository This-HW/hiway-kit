# Spec — 다중 하네스 공식 패키지 런칭 (Codex · Antigravity) (W-019)

- **작성일**: 2026-08-26
- **작성**: 기획 세션(torpedo-c4). 구현은 별도 세션에 인계
- **상태**: 승인됨 (구조: 같은 레포 다중 타겟 빌드 / 범위: 규범+스킬 문서 중심 — 사용자 결정 2026-08-26)
- **연관**: `docs/specs/2026-08-22-ade-benchmark-absorption.md` (P1 이식성 구멍의 확장),
  `docs/native-absorption.md` (하네스 중립 규범 배포 행), `plugins/common/skills/harness-export/`
- **목표 버전**: 2.15.0 (W-018과 동일 릴리스 또는 2.16.0 — S4에서 판정)

---

## 1. 배경 — `/harness-export`가 절반만 푼 문제

2.14.0의 `/harness-export`는 kit의 규범을 `AGENTS.md`로 내보내 **다른 하네스도 규율을 읽게** 만들었다.
그러나 `AGENTS.md`는 **배포 단위가 아니라 자유 형식 컨텍스트 파일**이다
`[confirmed: https://agents.md, 2026-08-26 — "AGENTS.md is just standard Markdown"]`.
사용자가 Codex나 Antigravity에서 kit를 쓰려면 여전히 **수동으로 파일을 복사**해야 한다.
"설치할 수 있는 패키지"가 없다.

동시에, 조사 결과 **두 플랫폼 모두 우리와 거의 같은 형태의 공식 플러그인 규격을 갖고 있다.**

## 2. 확인된 사실 (전부 1차 자료 재검증 완료)

### 2.1 Codex

- 공식 배포 단위 = **Codex Plugin**. 필수 매니페스트 `.codex-plugin/plugin.json`
  (필수 필드 `name`/`version`/`description`) `[confirmed: developers.openai.com/codex/plugins/build, 2026-08-26]`
- 레이아웃: 플러그인 루트에 `skills/`, `hooks/hooks.json`, `.mcp.json`, `.app.json`, `assets/`.
  원문: *"Only plugin.json belongs in .codex-plugin/"* `[confirmed: 동일 출처]`
- 마켓플레이스 카탈로그: `$REPO_ROOT/.agents/plugins/marketplace.json`, `~/.agents/plugins/marketplace.json`,
  **그리고 legacy로 `$REPO_ROOT/.claude-plugin/marketplace.json`** `[confirmed: 동일 출처]`
- 훅 환경변수: 원문 *"Codex also sets `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` for compatibility with
  existing plugin hooks."* `[confirmed: learn.chatgpt.com/docs/hooks, 2026-08-26]`
- 훅 이벤트 이름이 Claude Code와 동일 (`SessionStart`/`PreToolUse`/`PostToolUse`/`Stop` 등) `[confirmed: 동일 출처]`
- **⚠ 결함 발견 (조사 보고에 없던 것, 기획 세션이 1차 자료에서 확인)**: Codex 훅의 `command` 필드는
  **문자열 형식만 문서화**되어 있다 (`"command": "python3 ~/.codex/hooks/session_start.py"`). 우리 `hooks.json`은
  **exec form**(`"command": "python3", "args": [...]`)이다. → **그대로는 안 붙을 가능성이 높다.**
  `[confirmed: learn.chatgpt.com/docs/hooks, 2026-08-26 — "The documentation does not specify an alternative exec array format"]`
- 공개 게시: submission portal 승인제 → ChatGPT·Codex 공용 universal directory `[confirmed: 동일 출처]`.
  심사 기준·SLA는 `[unresolved]`
- 로컬 CLI 실재: `codex plugin add|list|marketplace|remove` `[confirmed: codex-cli 0.147.0 실행, 2026-08-26]`

### 2.2 Antigravity

- 공식 배포 단위 = **Antigravity Plugin**. 매니페스트 `plugin.json` (**루트**, 필수 필드는 `name` 하나)
  `[confirmed: antigravity.google/docs/cli/plugins/, 2026-08-26]`
- 인식 디렉토리: `mcp_config.json`, `hooks.json`, `skills/`, `agents/`, `rules/` `[confirmed: 동일 출처]`
- CLI: `agy plugin list|import|install|uninstall|enable|disable|validate|link` `[confirmed: agy 1.1.20 실행]`
- **`agy plugin import` 가 "Import plugins from gemini or claude" 를 명시** — Claude 생태계 플러그인의
  네이티브 임포터가 존재한다 `[confirmed: agy plugin --help 실행, 2026-08-26]`
- **`agy plugin validate <path>` 가 기계 검증기로 실재** — 우리 `plugins/common` 에 실행 시
  `Error: missing plugin.json` 수신 `[confirmed: 실행, 2026-08-26]`
- 공개 레지스트리·심사 절차: **공식 문서에 없음** `[unresolved]`. 로컬/워크스페이스 배치만 공식 확인
- 설치 경로가 공식 문서 간 상충 (`~/.gemini/config/plugins/` vs `~/.gemini/antigravity-cli/plugins/<name>/`)
  `[unresolved]` → **실물은 후자**로 확인됨 `[confirmed: 로컬 디렉토리 실측, 2026-08-26]`

### 2.3 레퍼런스 구현 (실물)

`~/.gemini/antigravity-cli/plugins/superpowers/` 가 **한 플러그인 루트에 타겟별 매니페스트를 병존**시킨
실동작 사례다 `[confirmed: 실물 해부, 2026-08-26]`:

```
superpowers/
├── .claude-plugin/{plugin.json, marketplace.json}
├── .codex-plugin/plugin.json          # + "skills": "./skills/", "interface": {...}
├── .cursor-plugin/plugin.json         # + "hooks": "./hooks/hooks-cursor.json"  ← 훅은 타겟별 분리 파일
├── .opencode/{INSTALL.md, plugins/}
└── .gemini-extension-install.json
```

**두 가지를 이 실물이 증명한다**: (a) 다중 타겟 병존은 가설이 아니라 현행 관행이다,
(b) **훅은 타겟마다 별도 파일로 분리**된다(`hooks-cursor.json`) — 우리 exec-form 문제와 같은 결론.

## 3. 문제 정의

- **P1**: kit를 Codex/Antigravity에서 쓰려면 설치 경로가 없다. 규범만 `AGENTS.md`로 새어 나갈 뿐,
  **스킬·에이전트·규칙 번들**은 Claude Code 사용자에게만 닿는다.
- **P2**: 두 플랫폼의 규격이 우리 구조와 거의 1:1인데도 그 사실이 어디에도 기록돼 있지 않아,
  매번 "이식이 가능한가"부터 다시 조사하게 된다.
- **P3**: 타겟 매니페스트를 손으로 만들면 버전·설명·컴포넌트 목록이 **반드시 드리프트**한다
  (이 레포가 doc-count·CHECKSUMS·MIRROR·AGENTS.md 게이트를 만든 이유와 동일한 실패 유형).

## 4. 성공 기준 (측정 가능)

| ID | 기준 | 측정 방법 |
| --- | --- | --- |
| S1 | `agy plugin validate plugins/common` 가 **green** | 명령 출력 (현재는 `missing plugin.json` 로 fail) |
| S2 | Codex가 우리 마켓플레이스를 **실제로 읽는다** | `codex plugin marketplace add <로컬경로>` → `codex plugin list` 에 kit가 보임 |
| S3 | 타겟 매니페스트가 **SSOT에서 생성**되고 손으로 고치면 게이트가 exit 1 | `verify-done.sh` 신설 § — 생성물 훼손 → red 실증 |
| S4 | 버전·설명·컴포넌트 목록이 **세 매니페스트에서 동일** | 생성기가 단일 소스에서 뽑음 + 게이트가 대조 |
| S5 | Claude Code 기존 설치가 **깨지지 않음** | `verify-done.sh` 전 항목 green 유지 |
| S6 | 각 플랫폼 설치 절차가 문서화됨 | README + 스킬 문서, **미확보 자격(공개 게시)은 미확보로 명시** |

## 5. 아키텍처 (결정. 선택지를 남기지 않는다)

### 5.1 플러그인 루트는 `plugins/common/` 하나다

**왜**: 이미 `.claude-plugin/plugin.json` 이 거기 있고, `skills/`·`agents/`·`rules/`·`hooks/` 가 그 아래 있다.
레퍼런스 구현(superpowers)과 같은 형태다. 루트를 옮기면 기존 설치가 전부 깨진다.

```
plugins/common/                         ← 플러그인 루트 (변경 없음)
├── .claude-plugin/plugin.json          ← 기존. **버전의 SSOT**
├── .codex-plugin/plugin.json           ← 신규 (생성물)
├── plugin.json                         ← 신규 (생성물, Antigravity 필수 매니페스트)
├── skills/ agents/ rules/ hooks/       ← 기존. 세 타겟이 공유
└── setup/
```

### 5.2 타겟 매니페스트는 전부 **생성물**이다. 손으로 쓰지 않는다

- 생성기: `scripts/build-targets.py` (**repo-local**. 소비자 환경에서 돌 필요가 없으므로 `plugins/` 에 두지 않는다
  — `export_harness.py` 가 플러그인 안에 있는 이유와 정반대의 이유로 밖에 둔다)
- 정책: `packaging/targets.json` — 타겟 목록·필드 매핑·`interface` 문구. **산문에 값이 남으면 미완성**
- 입력(SSOT): `plugins/common/.claude-plugin/plugin.json` (name·version·description·author·license…)
  + 컴포넌트 디렉토리 실측(`skills/`·`agents/`·`rules/` 존재 여부)
- 드리프트 게이트: `verify-done.sh` 신설 § — **재생성 후 `git diff` 가 비어야 한다**. CI도 동일 검사

### 5.3 훅은 이번 배치에서 **싣지 않는다** — 실측 후 별도 판정

**왜**: Codex 문서는 `command`를 문자열로만 기술하고, 우리는 exec form이다. 레퍼런스 구현도 훅만은
타겟별 파일(`hooks-cursor.json`)로 분리했다. **검증 없이 실으면 소비자 환경에서 조용히 죽는다** —
이 레포가 2.12.1에서 "훅 4종이 3.9에서 침묵 사망"으로 이미 겪은 실패 유형이다.

- S1~S3: 타겟 매니페스트에 `hooks` 필드를 **넣지 않는다**
- S4: `codex` CLI로 **실측**한다. exec form이 로드되면 그대로, 아니면 `hooks/hooks-codex.json`(문자열 형식)을
  생성물로 추가. **어느 쪽이든 실행 증거를 보고서에 남긴다**
- 실측 결과와 무관하게 `stop-validator`/`auto-format` 등 훅의 **동작 자체**는 이번 범위가 아니다

### 5.4 마켓플레이스는 두 벌 만든다

- 기존 `.claude-plugin/marketplace.json` (레포 루트) — Claude Code용. **변경하지 않는다.**
  Codex가 이것을 legacy 경로로도 읽는다 `[confirmed]`
- 신규 `.agents/plugins/marketplace.json` (레포 루트) — Codex 표준 경로. 생성물
- Antigravity: **공식 공개 레지스트리가 [unresolved]** 이므로 카탈로그를 만들지 않는다.
  `agy plugin install <로컬경로>` 절차만 문서화한다

### 5.5 이식 범위 = 규범 + 스킬 + 에이전트 정의. 실행 레이어는 이식하지 않는다

`[confirmed: 사용자 결정, 2026-08-26]`

| 컴포넌트 | Codex | Antigravity | 근거 |
| --- | --- | --- | --- |
| `skills/` (19) | ✅ `"skills": "./skills/"` | ✅ `skills/` 인식 (주1) | 양쪽 공식 필드. SKILL.md는 agentskills.io 개방 표준 |
| `rules/` (13) | ⚠ 전용 필드 없음 → **`AGENTS.md` 경로 유지**(`/harness-export`) | ✅ `rules/` 인식 | Antigravity만 1급 지원 |
| `agents/` (33) | ⚠ 전용 필드 없음 | ❌ **비지원** (주2) | 양쪽 모두 1급 미지원 — Codex는 필드 부재, Antigravity는 재귀 미지원으로 **실측 확정** (S4) |
| `hooks/` | ❌ exec form 미로드로 **실측 확정**, 편입 안 함 (주3) | 보류 (S4는 Codex만 실측) | |
| MCP | ❌ 이번 배치 없음 | ❌ 이번 배치 없음 | kit는 MCP를 번들하지 않는다 (rules/mcp-usage.md) |

**Codex에서 rules·agents가 1급으로 안 실리는 것은 결함이 아니라 플랫폼 사실이다.** 문서에 그대로 적는다.
**Antigravity의 agents 비지원도 마찬가지다** — `agy plugin validate`가 `agents/`를 재귀하지 않아
카테고리 하위로 중첩된 kit의 33개 에이전트를 인식하지 못한다. 공식 문서·스키마 어디에도 우회 설정이 없다.
**깨진 컴포넌트를 실은 채 "지원한다"고 광고하지 않는다.**

> **이 표는 2026-08-26 초안에서 한 번 틀렸다.** 초안은 Antigravity를 "rules·agents까지 1급 지원하는
> 유일한 타겟"으로 적었으나 실측이 그 주장을 지지하지 않았다. 조사·문서만으로 쓴 능력 주장은
> 실측 전까지 잠정이다.

- **주1**: `agy plugin validate` 는 `skills/` 를 19가 아니라 **21로 오집계**한다 (`references/`·`README.md`가
  함께 잡힘 — SKILL.md 존재 여부를 검증하지 않는 agy 자체 한계). 실제 19개 스킬은 정상 동작(S3 install
  실증) — **카운트 표시만 부정확하다.** kit 구조 결함이 아니다.
- **주2**: 통제 실측으로 확정 — **빈 카테고리 디렉토리만 있어도 `agents:1`** 로 집계된다. 즉 top-level
  항목을 재귀 없이 개수만 센다. kit의 `agents/` 는 4개 카테고리 아래 33개 파일이 중첩돼 있어 **실제
  인식은 0개**다. `$schema` URL 자체가 404라 스키마로도 확인 불가.
- **주3**: Codex 훅 런타임은 `command`+`args`(exec form)를 **지원하지 않는다** — `args` 가 조용히 무시되고
  `command` 만 리터럴 문자열로 실행된다. 3단계 실측으로 확정: (1) `python3`+args → Completed인데 부작용
  없음(무해 no-op) (2) `touch`+args → **명시적 Failed**(인자 없는 touch 에러 = args 미전달의 결정적 증거)
  (3) 공식 단일 문자열 command → Completed + 마커 생성(positive control). kit는 exec form이므로 편입하지
  않는다. 문자열 형식 변환은 별도 배치.

### 5.6 소비자 우선 원칙은 그대로다

새 타겟이 생겨도 **Claude Code 설치 경로가 1순위**다. 어떤 생성물도 `.claude-plugin/plugin.json` 이나
기존 디렉토리 구조를 바꾸지 않는다. `plugins/common/plugin.json`(Antigravity용)이 Claude Code 로딩에
영향을 주는지는 **S3에서 실측 확인**한다 — 영향이 있으면 그 타겟을 포기하고 사실을 기록한다.

## 6. 수용 테스트 (사람이 손으로 확인)

1. `agy plugin validate plugins/common` → green
2. `agy plugin install <레포경로>` → `agy plugin list` 에 kit 표시 → `uninstall` 로 복구
3. `codex plugin marketplace add <레포경로>` → `codex plugin list` 에 kit 표시 → `remove` 로 복구
4. `plugins/common/.codex-plugin/plugin.json` 의 version을 손으로 고친 뒤 `verify-done.sh` → **fail**
5. Claude Code에서 kit가 여전히 정상 로드 (`verify-done.sh` green + 세션 훅 정상)
6. README만 읽고 세 플랫폼 각각의 설치 절차를 따라할 수 있는가

## 7. 비목표 (명시적 배제)

- **공개 게시·제출** — OpenAI submission portal 제출은 사람의 행위. 자격 미확보(자격 인벤토리)
- Cursor / OpenCode / Copilot 타겟 — 후속. Cursor 마켓플레이스는 큐레이션 파트너 한정이라 제출 불가
- IDE Extension(VS Code·JetBrains) — 완전히 다른 배포 채널이자 **앱 레이어**.
  ADE 배치에서 이미 명시적 비목표로 확정됨
- 훅 로직의 플랫폼별 재구현 — 형식 변환까지만(§5.3), 동작 이식은 별도
- `rules/` 원문 변경 (0개), 에이전트 정의 변경 (0개)
- 멀티 프로바이더 실행 오케스트레이션 — Orca/Paseo의 영역

## 8. 단계 (의존성 순서)

| Stage | 내용 | 산출물 |
| --- | --- | --- |
| **S1 골격** | `packaging/targets.json` + `scripts/build-targets.py` + 드리프트 게이트 + CI | 생성물 훼손 → **게이트 red 실증** |
| **S2 Codex** | `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json` 생성 → `codex` CLI로 실증 | 수용 테스트 3 통과 증거 |
| **S3 Antigravity** | 루트 `plugin.json` 생성 → `agy plugin validate` green → install/uninstall 실증 + **Claude Code 무영향 확인** | 수용 테스트 1·2·5 통과 증거 |
| **S4 훅 판정 + 출하** | 훅 형식 실측 판정 → 문서(README·스킬)·CHANGELOG·버전 | 릴리스 준비 완료 |

**S1의 골격 함정 대비**: 생성기를 만들고 "돌았다"로 넘어가지 않는다. **생성물을 손으로 훼손해 게이트가
red가 되는지 확인**하는 것이 S1의 완료 조건이다.

## 9. 리스크

| 리스크 | 완화 |
| --- | --- |
| 루트 `plugin.json` 추가가 Claude Code 로딩을 깨뜨림 | S3에서 실측. 깨지면 **타겟 포기**하고 사실 기록 (소비자 우선이 상위 원칙) |
| Codex 훅 형식 비호환 | §5.3 — 검증 전까지 싣지 않는다. 이것이 이 스펙의 최대 미지수 |
| Antigravity 공식 배포 채널 부재 | 로컬 설치만 지원 + `[unresolved]` 로 문서화. **없는 것을 있는 것처럼 쓰지 않는다** |
| 레포 표면적 증가 | 신규 최상위 디렉토리는 `packaging/` 하나. 생성물은 전부 기존 플러그인 루트 안 |
| 플랫폼 규격이 바뀜 | 생성기 + 게이트 구조라 매니페스트 재생성으로 대응. 확인일을 문서에 박아 신선도를 드러냄 |
