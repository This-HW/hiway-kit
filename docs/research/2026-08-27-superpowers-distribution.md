# 레퍼런스 조사 — superpowers의 다중 플랫폼 배포 (obra/superpowers)

- 조사일 2026-08-27 · 조사자: 기획 세션 · 방법: 로컬 설치본 해부 + `gh api` 로 원본 저장소 직접 조회
- 목적: CCK의 다중 타겟 패키징(W-019)과 AGENTS.md 단일 소스(W-020)의 선행 사례 확보

## 1. 배포 타겟 — 플러그인 9종 + npm + 컨텍스트 파일 3종

`[confirmed: gh api repos/obra/superpowers/contents, 2026-08-27]`

| 타겟 디렉토리/파일 | 대상 |
| --- | --- |
| `.claude-plugin/` (plugin.json + marketplace.json) | Claude Code |
| `.codex-plugin/plugin.json` | Codex |
| `.agents/plugins/` | Codex 표준 마켓플레이스 경로 |
| `.cursor-plugin/plugin.json` | Cursor |
| `.devin-plugin/plugin.json` | Devin |
| `.kimi-plugin/plugin.json` | Kimi |
| `.hermes-plugin/` (**plugin.yaml + `__init__.py`**) | Hermes — 유일하게 YAML + Python 규격 |
| `.opencode/` (INSTALL.md + plugins/) | OpenCode — JS/TS 실행 코드 |
| `.pi/extensions/` | Pi |
| `gemini-extension.json` | Gemini/Antigravity 확장 |
| `package.json` | npm |

→ **CCK는 현재 2종(Codex·Antigravity). superpowers는 9종 + npm.**

## 2. 컨텍스트 파일 — 심링크 방향이 통념과 반대다

`[confirmed: git tree API 의 file mode]`

```
AGENTS.md    mode=120000  SYMLINK  size=9   → "CLAUDE.md"
CLAUDE.md    mode=100644  실체 파일 8,873 B   ← **단일 소스**
GEMINI.md    mode=100644  실체 파일 92 B      ← 심링크 아님. 별도 얇은 파일
```

**`CLAUDE.md` 가 원본이고 `AGENTS.md` 가 그것을 가리키는 심링크다.** Anthropic 공식 문서가 예시로 드는
`ln -s AGENTS.md CLAUDE.md`(AGENTS.md가 원본)와 **방향이 반대**다. 둘 다 POSIX에서 동작하므로
어느 쪽을 실체로 둘지는 선택의 문제이고, superpowers는 `CLAUDE.md` 를 택했다.

**`GEMINI.md` 는 심링크가 아니라 92바이트짜리 별도 파일이고 내용이 다르다:**

```
@./skills/using-superpowers/SKILL.md
@./skills/using-superpowers/references/gemini-tools.md
```

즉 Gemini에는 **전문을 복제하지 않고 부트스트랩 import 두 줄만** 준다. 그리고
`gemini-extension.json` 이 `"contextFileName": "GEMINI.md"` 로 어느 파일을 읽을지 지정한다.

> **시사점**: "모든 하네스에 같은 파일을 링크"가 아니라 **하네스별로 필요한 만큼만 준다.**
> 링크가 맞는 곳(AGENTS.md)과 얇은 별도 파일이 맞는 곳(GEMINI.md)이 갈린다.

## 3. 버전 팬아웃 — `.version-bump.json`

`[confirmed: 파일 원문]`

```json
{
  "files": [
    { "path": "package.json",                 "field": "version" },
    { "path": ".claude-plugin/plugin.json",   "field": "version" },
    { "path": ".cursor-plugin/plugin.json",   "field": "version" },
    { "path": ".codex-plugin/plugin.json",    "field": "version" },
    { "path": ".claude-plugin/marketplace.json", "field": "plugins.0.version" },
    { "path": "gemini-extension.json",        "field": "version" }
  ],
  "audit": { "exclude": ["CHANGELOG.md", "RELEASE-NOTES.md", "node_modules", ".git", ...] }
}
```

**버전을 올리면 모든 타겟 매니페스트로 전파하는 선언적 매니페스트** + `scripts/bump-version.sh`.
`audit.exclude` 가 있다는 건 **레포 전체에서 낡은 버전 문자열을 훑는 감사 기능**이 있다는 뜻이다.

> **시사점**: CCK는 v2.15.0 릴리스에서 **정확히 이 문제를 밟았다.** `.claude-plugin/plugin.json` 만
> 올리고 생성물을 재생성하지 않아 §14가 드리프트로 잡았다. 우리는 게이트로 사후 탐지했고,
> superpowers는 팬아웃으로 사전 예방한다. **탐지보다 예방이 낫다.**
> (다만 우리 쪽은 매니페스트가 *생성물*이라 팬아웃 대신 재생성이 정답 — 자동 재생성을 bump에 묶는 것)

## 4. 배포 경로 — Codex는 별도 마켓플레이스 저장소로 PR

`scripts/` = `bump-version.sh`, `lint-shell.sh`, `sync-to-codex-plugin.sh`, `package-codex-plugin.sh`

`sync-to-codex-plugin.sh` 원문 요지 `[confirmed]`:
- 대상: **`prime-radiant-inc/openai-codex-plugins` 포크**로 rsync → 커밋 → 브랜치 push → **PR 생성**
- "OpenAI-owned marketplace metadata already in the destination" 는 **보존**
- **결정적(deterministic)**: 같은 upstream SHA로 두 번 돌리면 동일한 diff의 PR이 나온다 — 도구 자체를 검증 가능
- `--bootstrap` 모드로 대상에 플러그인 디렉토리가 없을 때 생성

> **시사점**: Codex 공개 배포는 매니페스트만 만든다고 끝이 아니라 **마켓플레이스 저장소에 PR**을 넣는
> 절차가 실재한다. 우리 `docs/codex-submission-checklist.md` 의 `[unresolved]` 중 일부가 이걸로 좁혀진다.

## 5. 그 밖에 눈여겨볼 것

- `.github/ISSUE_TEMPLATE/platform_support.md` — **플랫폼 지원을 1급 이슈 카테고리로** 둔다
- 기여 가이드가 새 하네스 지원 PR에 **수용 테스트**를 요구한다: 깨끗한 세션에서
  `Let's make a react todo list` 를 보내 `brainstorming` 스킬이 **자동 발동**하는 트랜스크립트 첨부.
  "스킬 파일 수동 복사", "런타임 shim", "세션마다 opt-in" 은 진짜 통합이 아니라고 명시
- 스킬 행동 evals는 별도 저장소(`superpowers-evals`)에서 **실제 tmux 세션**(Claude Code/Codex/Gemini CLI)을
  구동하고 LLM 검증자로 준수를 판정한다 — 우리 evals가 에이전트 단위인 것과 대비되는 설계

## 6. CCK가 가져올 것 / 안 가져올 것

| 가져온다 | 이유 |
| --- | --- |
| 버전 팬아웃(우리는 **재생성 자동화**) | v2.15.0에서 실제로 밟은 함정. 탐지보다 예방 |
| 하네스별 컨텍스트 파일 전략(링크 vs 얇은 파일) | W-020의 설계 근거. 통념(AGENTS.md 원본)이 유일한 답이 아니다 |
| 타겟 확장 후보 목록 | Cursor·OpenCode·Devin·Kimi·Hermes·Pi·Gemini extension |
| 플랫폼 지원 이슈 템플릿 | 저비용, 기여 경로 명확화 |
| **새 하네스 지원의 수용 테스트 개념** | "매니페스트가 있다"와 "실제로 동작한다"는 다르다 — 우리도 실물 CLI 검증을 했지만 성문화는 안 됐다 |

| 안 가져온다 | 이유 |
| --- | --- |
| npm 배포 | CCK는 npm 패키지가 아니다. 배포 채널을 늘리는 것 자체가 목적이 될 수 없다 |
| 별도 evals 저장소 + tmux 하네스 | 우리 evals는 에이전트 단위로 이미 동작한다. 스킬 행동 evals는 별도 문제 |
| 마켓플레이스 포크 PR 자동화 | **자격 미확보**(공개 게시는 사람의 행위). 다만 절차를 문서에 반영한다 |


---

## 부록 — `project_doc_max_bytes` 의미 확정 (2026-08-27, 기획 세션 추가 조사)

W-022 §4.2(컨텍스트 SSOT) 설계가 이 값에 걸려 있어 별도로 확인했다.

**결론: 파일당이 아니라 병합 총량이다. 그리고 초과분은 조용히 사라진다.**

- 공식 문서 원문 `[confirmed: learn.chatgpt.com/docs/agent-configuration/agents-md, 2026-08-27]`:
  > "Codex skips empty files and stops adding files once the combined size reaches the limit
  > defined by `project_doc_max_bytes` (32 KiB by default)."
- 병합 순서는 **글로벌 → git root → cwd** 로 내려가며 이어붙이고, 상한에 닿으면 **더 이상 추가하지 않는다**.
  즉 **cwd에 가까운(나중에 붙는) 파일이 먼저 잘려나간다**
- 경고·로그·TUI 표시가 **없다** — 조용히 잘린다
  `[researched: openai/codex issues #7138, #13386, n=2 — 독립 이슈 두 건이 같은 증상 보고]`

### 설계에 미치는 영향 (중요)

1. **"하위 디렉토리 `AGENTS.md` 로 분할"은 우회로가 되지 못한다.** 총량 상한이고, 깊은 파일이
   먼저 버려지므로 오버플로를 아래로 밀어내면 그게 바로 잘리는 부분이 된다
2. **우리 파일만으로 예산을 다 쓰면 안 된다.** 상한은 소비자의 `~/.codex/AGENTS.md`(글로벌)까지
   합산한 값이다. 소비자가 이미 큰 글로벌 지침을 두고 있으면 우리 몫은 그만큼 줄어든다
   → **여유를 두는 것이 예의가 아니라 요구사항이다**
3. 조용히 잘리므로 **우리 쪽 게이트가 유일한 방어선**이다. 소비자는 잘린 사실조차 모른다

### 상충 기록
2차 자료 일부는 "farthest-from-cwd 가 먼저 잘린다"고 서술해 공식 문서와 **반대**다
`[unresolved — 자료 간 상충]`. 공식 문서의 "stops adding files"(root부터 붙이므로 깊은 것이 누락)를
채택하되, **어느 쪽이든 '총량이고 조용히 사라진다'는 결론은 같으므로** 설계 판단에는 영향이 없다.


---

## 부록 2 — 타겟별 매니페스트·훅 실물 (2026-08-27, `gh api` 직접 조회)

W-022의 R5(Codex 훅 문자열 변환)와 R9(타겟 규격 조사)에 쓸 **1차 자료**다.
전부 `[confirmed: gh api repos/obra/superpowers/contents/<path>, 2026-08-27]`.

### 타겟별 매니페스트 필드

| 타겟 | 파일 | 특징적인 필드 |
| --- | --- | --- |
| Cursor | `.cursor-plugin/plugin.json` | `skills: "./skills/"` + **`hooks: "./hooks/hooks-cursor.json"`** — 훅을 **타겟 전용 파일**로 분리 |
| Kimi | `.kimi-plugin/plugin.json` | `skills` + **`sessionStart: {skill: "using-superpowers"}`** (부트스트랩 선언) + **`skillInstructions`**(툴 매핑 산문) |
| Devin | `.devin-plugin/plugin.json` | **메타데이터만.** 컴포넌트 필드 없음 → 규약으로 발견하는 듯 |
| Hermes | `.hermes-plugin/plugin.yaml` | **YAML.** `provides_hooks: [pre_llm_call]` — 훅 모델 자체가 다르다 |
| Pi | `.pi/extensions/superpowers.ts` | **TypeScript 모듈** |
| Codex 카탈로그 | `.agents/plugins/marketplace.json` | 우리와 동일 경로 |

### ⭐ 훅 — 우리 R5의 답이 여기 있다

**superpowers는 Claude Code용에도 exec form을 쓰지 않는다. 문자열 커맨드를 쓰고 경로를 직접 인용한다.**

```jsonc
// hooks/hooks.json  (Claude Code)
{ "type": "command",
  "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd\" session-start",
  "shell": "bash", "async": false }

// hooks/hooks-cursor.json  (Cursor)
{ "version": 1,
  "hooks": { "sessionStart": [ { "command": "./hooks/run-hook.cmd session-start" } ] } }
```

세 가지가 드러난다:

1. **인용 문제의 해법은 "경로를 문자열 안에서 따옴표로 감싸는 것"** 이다. `${CLAUDE_PLUGIN_ROOT}` 는
   호스트가 치환하지만, **치환 결과가 따옴표 안에 들어가므로** 공백이 있어도 깨지지 않는다.
   → CCK의 R5(Codex용 문자열 변환)는 `"python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/x.py\""` 형태가 답이다
2. **타겟마다 훅 스키마가 다르다** — 이벤트 이름 대소문자(`SessionStart` vs `sessionStart`),
   `matcher` 유무, `version` 필드, 경로 표기(절대 치환 vs 상대). **타겟별 파일 분리가 필수**다
3. **폴리글롯 래퍼** `hooks/run-hook.cmd` — 한 파일이 Windows(cmd 배치)와 Unix(bash) 양쪽에서 동작한다.
   훅 스크립트를 **확장자 없이** 두는 이유가 원문에 적혀 있다:
   > "Hook scripts use extensionless filenames … so Claude Code's Windows auto-detection —
   > which prepends 'bash' to any command containing .sh — doesn't interfere."

### CCK에 대한 시사점

- **R5는 실현 가능하다.** 인용 방식이 이미 실증된 패턴이다
- CCK의 `hooks.json` 이 exec form인 이유는 `CLAUDE.md` 에 *"`${CLAUDE_PLUGIN_ROOT}` 경로에 셸 인용이
  필요 없도록"* 이라고 적혀 있다. superpowers는 반대 선택(문자열 + 명시 인용)을 하고 **이식성**을 얻었다.
  **트레이드오프이지 우열이 아니다** — 다만 다중 하네스를 노린다면 문자열 쪽이 유리하다.
  CCK의 Claude Code용 `hooks.json` 변경은 **이번 배치 범위 밖**이다(회귀 위험). 사실만 기록한다
- Windows 지원은 CCK가 한 번도 실측하지 않은 영역이다 — `[unresolved]`. 폴리글롯 래퍼는 그 문제의
  기존 해법이 있다는 증거이며, 필요해지면 참고 대상이다


---

## 부록 3 — R9용 타겟 공식 규격 (기획 세션 선행 조사, 2026-08-27)

Track B S4가 조사부터 시작하지 않도록 미리 모은다. **superpowers 실물과 공식 문서를 구분해 태그했다.**

### Cursor — 우리 컴포넌트 전부를 1급 지원하는 유일한 타겟
- 공식 문서 실재: `cursor.com/docs/plugins`, `cursor.com/docs/reference/plugins`,
  공식 스펙·플러그인 저장소 `github.com/cursor/plugins` `[researched: 검색 결과, n=3 이상 독립 출처]`
- 매니페스트: `.cursor-plugin/plugin.json` (필수). 다중 플러그인 저장소는 `.cursor-plugin/marketplace.json`
- **컴포넌트 타입: `skills`, `agents`, `rules`, `hooks`, `commands`, `mcpServers`**
  → Codex(skills만)·Antigravity(skills·rules, agents 비지원)와 달리 **우리 33 에이전트 + 13 rules를
  전부 실을 수 있는 유일한 후보**다
- 검증이 엄격하다: `additionalProperties: false`, kebab-case 패턴, URI·email 포맷 검사
- superpowers 실물과 일치 `[confirmed: .cursor-plugin/plugin.json 원문]` —
  `skills`·`hooks: "./hooks/hooks-cursor.json"` 사용

### Pi — TypeScript 모듈. 매니페스트 방식이 아니다
- 확장은 **TypeScript 모듈**이며 `ExtensionAPI` 를 받는 default factory를 export한다
- 설치 위치 `~/.pi/agent/extensions`. 배포는 npm/git 패키지(`pi install`)
  `[researched: pi.dev/docs/latest/extensions + 커뮤니티 저장소 다수, n=3]`
- superpowers도 `.pi/extensions/superpowers.ts` **TS 파일**이다 `[confirmed]`
- → **선언적 매니페스트 생성으로는 도달 불가.** 코드를 써야 한다. 우리 생성기 모델과 이질적

### 정리 — 활성화 판단의 기준을 하나 더 둔다

이 조사로 **검증 수준이 세 단계**라는 게 분명해졌다. `targets.json` 에 이 구분을 기록해라:

| 수준 | 의미 | 해당 |
| --- | --- | --- |
| `runtime-verified` | 실물 CLI로 install→list→remove 왕복 확인 | codex, antigravity |
| `spec-verified` | 공식 스키마·문서로 **산출물**은 검증되나 런타임 미확인 | cursor (스키마 공개) |
| `researched-only` | 규격만 조사됨 | pi, opencode, devin, kimi, hermes |

**그럼에도 활성화 기준은 `runtime-verified` 로 유지한다.** 근거: Antigravity `agents/` 사건에서
**매니페스트는 유효했지만 컴포넌트 발견이 실패**했다. 스키마 검증은 그 실패를 잡지 못한다.
`spec-verified` 는 "만들면 형식은 맞다"까지만 보증하며, **"동작한다"는 별개의 주장**이다.

→ Cursor는 **가장 유망한 다음 타겟**이지만 이번 배치에서 활성화하지 않는다.
   `_enableWhen`: *"cursor CLI로 왕복 검증이 가능해지거나, 사용자가 수용 테스트 트랜스크립트를
   제공하면"* (superpowers의 새 하네스 지원 기준과 같은 바)


---

## 부록 4 — R4(Antigravity 훅) 선행 실측 (기획 세션, 2026-08-27)

### 사실
```
plugins/common (우리 구조: hooks/hooks.json)   → hooks : skipped (not found)
같은 내용을 루트 hooks.json 으로 복사한 사본    → hooks : 1 processed
```
`[confirmed: agy 1.1.20 실행, 스크래치 사본]`

즉 **Antigravity는 루트 `hooks.json` 을 본다.** 우리는 `hooks/hooks.json` 이라 경로가 다르다.
그리고 **exec form 내용 그대로도 `1 processed`** 가 나왔다.

### ⚠ 그런데 이 결과로 "동작한다"고 결론 내면 안 된다
`agy plugin validate` 는 **파일 존재를 세는 도구이지 내용 검증기가 아니다.** 근거가 이제 셋이다:

| 컴포넌트 | validate 결과 | 실제 |
| --- | --- | --- |
| skills | `21 processed` | 실제 스킬은 **19**. `README.md`·`references/`(SKILL.md 없음)를 함께 셌다 |
| agents | `4 processed` | 실제 에이전트는 **33**. 카테고리 디렉토리 4개를 셌고 **인식은 0** |
| hooks | `1 processed` | 파일 **1개**를 찾았다는 뜻. 이벤트 4종을 이해했다는 근거는 **없다** |

**세 번 모두 같은 패턴이다: validate는 "찾았다"만 말하고 "이해했다"는 말하지 않는다.**
Antigravity `agents/` 사건에서 우리가 배운 것이 바로 이것이고, 훅은 그 **세 번째 확인**이다.

### 판정 (기획): **Antigravity 훅은 이번 배치에서 싣지 않는다**
- 경로는 맞출 수 있다(루트 `hooks.json` 생성). 그러나 **형식이 이해되는지 검증할 수단이 없다**
- 우리에겐 Antigravity 런타임에서 훅이 실제로 발화하는지 확인할 경로가 없다
- 2.12.1의 "훅 4종이 3.9에서 침묵 사망"이 정확히 이 유형이다 — **로드되는 것처럼 보이지만 안 도는 것**
- `_enableWhen`: *"Antigravity 세션에서 훅이 실제 발화함을 마커 파일 등으로 확인하면"*

> **부수 소득**: `agy plugin validate` 를 **게이트로 신뢰해서는 안 된다**는 것이 확정됐다.
> W-019에서 이걸 "green으로 전환됐다"는 성과로 적었는데, 그 green은 **"파일이 있다"** 이상을
> 의미하지 않는다. README·스펙의 서술을 이 수준에 맞춰야 한다.

---

## 부록 5 — R5(Codex 훅 문자열 형식) 실측 완결 (2026-08-27, trackB)

기획 세션(torpedo-c4)의 1차 시도가 `codex exec` 5분 타임아웃으로 결론을 못 냈다. trackB가
원인을 특정하고 재실측해 완결했다.

### 결과: 따옴표 문자열 형식은 된다

스크래치 플러그인의 `hooks/hooks.json`에 SessionStart 훅을 아래처럼 설치:

```jsonc
{ "type": "command",
  "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/mark.sh\"",
  "async": false }
```

`mark.sh`는 자신의 `$0`과 `$CLAUDE_PLUGIN_ROOT` 환경변수를 마커 파일에 적는다. `codex exec`로
SessionStart를 유발한 결과, 마커 파일:

```
fired argv0=/Users/hw/.codex/plugins/cache/hookprobe-marketplace/hookprobe/0.0.1/hooks/mark.sh
CLAUDE_PLUGIN_ROOT_env=/Users/hw/.codex/plugins/cache/hookprobe-marketplace/hookprobe/0.0.1
```

`${CLAUDE_PLUGIN_ROOT}`가 따옴표 문자열 안에서 **실제 설치 경로로 치환**되고, 같은 값이
**하위 프로세스 환경변수로도 노출**된다 — 두 메커니즘 다 확인 [confirmed: codex-cli 0.147.0
실측, 2026-08-27]. superpowers의 인용 패턴(`"\"${CLAUDE_PLUGIN_ROOT}/...\""`)이 Codex에서도
그대로 성립한다.

### 재현 절차 (다음 사람을 위해 — torpedo-c4의 1차 시도 실패 원인 포함)

1. `codex exec`에 **`--dangerously-bypass-hook-trust`를 반드시 포함**한다. 이게 빠지면 훅 신뢰
   확인이 비대화형 `exec`에서 응답을 못 받아 무한 대기한다 — **torpedo-c4의 1차 시도가 5분
   타임아웃으로 막힌 원인으로 추정된다**(확정은 아니다 — 그쪽 실행 로그가 없어 대조 불가).
2. macOS에는 `timeout` 명령이 없다. `codex exec ... &`로 백그라운드 실행 후 마커 파일을
   폴링하고, 일정 시간(예: 45초) 지나면 무조건 kill한다.
3. 정리(`codex plugin remove` / `codex plugin marketplace remove`)를 **성공 경로에만 두지
   마라**. `trap cleanup EXIT`로 모든 종료 경로(성공·실패·강제 kill)에서 실행되게 하라 —
   torpedo-c4의 1차 시도는 이게 없어 `~/.codex`에 플러그인이 남았다(수동으로 치웠다).
4. `codex plugin remove`는 `~/.codex/plugins/cache/<marketplace-name>/`에 빈 디렉토리를
   남길 수 있다(CLI 자체의 불완전 정리) — 정리 스크립트에 `rmdir`(빈 경우만) 단계를 넣어라.
5. 정리 후 `~/.codex/config.toml`을 사전 스냅샷과 diff해 완전 원복을 확인하라.

### 그러나 형식 변환 ≠ 기능 이식

`packaging/targets.json`의 codex 타겟 `omit.hooks`에 훅별(5개) 근거를 전문 기록했다 — kit의
실제 훅은 전부 Claude Code의 이벤트 모델(툴 이름 매처, `PreToolUse`/`PostToolUse`의
`tool_name`/`tool_input` stdin JSON, `SessionStart`의 `hookSpecificOutput.additionalContext`
출력 계약, `Stop`의 `decision:block`+재개 프로토콜)에 의존한다. 형식만 바꿔 Codex가
실행하게 만들어도 이 계약을 Codex가 이해한다는 근거가 없다 — 특히 `protect-sensitive.py`·
`auto-format.py`는 매처가 전부 실패해 **조용히 no-op**(차단이 꺼진 채 켜져 있다는 착각)되는
쪽이라 위험하다. → **이 배치에서는 hooks 필드를 넣지 않는다.** 자세한 훅별 근거는
`packaging/targets.json`이 SSOT.
