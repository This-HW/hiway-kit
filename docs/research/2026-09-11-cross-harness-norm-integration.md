# 조사 — 하네스 간 규범·룰 통합 패턴 비교

**조사일**: 2026-09-11  
**대상**: Hermes Agent, Cursor, Continue, aider, OpenHands, Copilot 및 AGENTS.md 표준  
**방법**: 공식 문서·저장소·기존 연구 자료 조사

---

## 요약

이 레포(hiway-kit)의 규범 배포는 **"단일 소스 + 훅 주입 + 폴백 생성 + 드리프트 게이트"** 4단 설계다.
다른 도구들은 유사하나, **드리프트 게이트(생성물이 소스와 갈리면 빌드 실패)** 를 명시적으로 강제하는 곳은
찾지 못했다. 그 대신 다른 가치들(버전 팬아웃 자동화, 하네스별 선택적 배포)을 본다.

---

## 1. 우리 접근 방식 (hiway-kit) — 기준선

`[confirmed: 레포 CLAUDE.md, plugins/common/hooks/export_harness.py, scripts/verify-done.sh]`

| 항목 | 구현 |
| --- | --- |
| **단일 소스** | `plugins/common/rules/*.md` (frontmatter 포함 `portable: true\|false`) |
| **주 배포 경로** | SessionStart 훅 → `session-start.py` 읽기 + 주입 (Claude Code / Codex) |
| **폴백 경로** | `export_harness.py` → `AGENTS.md`, `GEMINI.md` 생성 (훅 미지원 하네스) |
| **이식성 선언** | `portable: true` = 모든 하네스 / `false` = Claude 전용만 배포 |
| **사용자 콘텐츠 보호** | 마커 블록(줄 앵커 + sha256) — 밖은 불가침, 손상 시 exit 1 |
| **드리프트 게이트** | `verify-done.sh` §7·§11 — 생성물 ≠ 소스 면 exit 1 |

**핵심 설계 결정**: 폴백 생성물의 sha256을 **렌더 결과가 아니라 입력**의 해시로 정한다.
→ 마커 밖의 사용자 편집이 게이트를 통과해도, 내용이 바뀌면 다음 export가 그것을 감지하고 제자리 교체한다.

---

## 2. AGENTS.md 표준 — 다중 하네스 사실상 규격

`[confirmed: docs/research/2026-08-27-superpowers-distribution.md; researched: 여러 도구 문서]`

**AGENTS.md** 는 Codex · OpenCode · Copilot · Cursor 의 **공통 사실상 표준** (de facto standard).
- 파일 위치: 프로젝트 루트
- 용도: 에이전트·스킬·규칙·지시문 등을 텍스트로 정의
- 마커: `<!-- kit:begin ... --> ... <!-- kit:end -->` (또는 구 토큰 `cck`)

**의의**: 이 하네스들이 `AGENTS.md` 를 읽기로 설계했으므로, 우리는 파일 하나를 다중 하네스로 배포할 수 있다.
더 이상 "환경별 CLAUDE.md vs AGENTS.md 선택"이 아니라, **가장 유명한 단일 진입점이 됐다**.

---

## 3. 다른 도구들의 접근

### 3.1 superpowers (Anthropic 공식 플러그인)

`[confirmed: github.com/obra/superpowers + docs/research/2026-08-27-superpowers-distribution.md]`

**배포 대상**: 9가지 (Claude Code · Codex · Cursor · Devin · Kimi · Hermes · OpenCode · Pi · Gemini/Antigravity + npm)

| 측면 | 우리 | superpowers |
| --- | --- | --- |
| **버전 관리** | `scripts/build-targets.py` 에 재생성 바인딩 | `.version-bump.json` + `scripts/bump-version.sh` — **버전을 올리면 모든 타겟 매니페스트로 자동 전파** |
| **훅 형식** | Codex 용 exec form (omitted for now) | Claude Code: exec form, **Codex는 별도 문자열 형식** (`hooks/hooks-cursor.json` 타겟별 파일) |
| **컨텍스트 파일 전략** | 하네스별 개별 AGENTS.md·GEMINI.md 생성 | 심링크(`AGENTS.md` → `CLAUDE.md`) + 얇은 별도 파일(`GEMINI.md` 92B 부트스트랩) |
| **마켓플레이스 배포** | (비활성) | Codex PR 자동화(`sync-to-codex-plugin.sh` → poitne-radiant-inc 포크 PR) |

**시사점** (우리가 배울 점):
- v2.15.0에서 우리가 밟은 버전 미동기화 문제를 superpowers는 `bump-version.json` 으로 예방한다.
  우리는 게이트로 사후 탐지하고, 그들은 팬아웃으로 사전 예방한다. **탐지보다 예방이 낫다.**
- 하네스별 컨텍스트 파일을 "모두 링크"가 아니라 "필요한 만큼만"으로 한다.
  CLAUDE.md 원본, AGENTS.md 심링크, GEMINI.md 얇은 부트스트랩 — 통념과 다르지만 효율적이다.

### 3.2 Cursor

`[confirmed: cursor.com/docs/plugins 공식 문서, docs/research/2026-08-27-superpowers-distribution.md]`

- **매니페스트**: `.cursor-plugin/plugin.json`
- **컴포넌트**: `skills`, `agents`, `rules`, `hooks`, `commands`, `mcpServers` — **우리 전 요소 1급 지원**
- **검증**: 엄격한 스키마 (`additionalProperties: false`, kebab-case, URI 포맷 검사)
- **마켓플레이스**: 카탈로그 + 프라이빗 저장소 모두 지원

**의의**: 우리를 가장 완전히 지원할 수 있는 타겟이나, 런타임 검증(실물 Cursor CLI 확인)이 아직 안 됨.
`docs/research/2026-08-27-superpowers-distribution.md` 가 "spec-verified (매니페스트는 맞으나 런타임 미확인)"
으로 분류한 이유.

### 3.3 Hermes Agent

`[researched: docs/native-absorption.md, CHANGELOG entries]`

- **언어**: YAML 플러그인 + Python 정의 (`.hermes-plugin/plugin.yaml` + `__init__.py`)
- **특징**: **성공 trajectory → 자동 스킬 생성** (우리 `/skill-forge` 의 영감)
- **메모리**: 세션 넘는 영속 메모리 + agentskills.io 표준 개방

**의의**: 스킬 자동 승격 개념의 선행 사례이나, **외부 하네스의 기능**이지 Claude Code 네이티브가 아니다.
우리가 참고할 만한 사례이지만, Hermes 규범을 우리가 배포해야 할 대상은 아니다 (Hermes는 자기 생태 보유).

### 3.4 Continue IDE

`[researched: continue.dev 공식 문서 검색 결과]`

- **규칙 파일**: `~/.continue/config.json` 의 `customInstructions` 필드
- **범위**: 커스텀 지시문과 프롬프트 템플릿
- **배포**: 파일 기반 (매니페스트 아님)

**의의**: AGENTS.md 표준의 반대편 극단 — **환경 변수로 지시문을 주입**하는 방식.
단일 소스 개념이 약하고, 각자 로컬 config를 편집해야 함.

### 3.5 aider

`[researched: aider.chat 공식 문서, GitHub 저장소]`

- **규칙**: `.aider*` 패밀리 파일 (`.aider.conf.json`, `.aider.rules`)
- **배포 타겟**: 프로젝트 루트, gitignore 예제 제공
- **범위**: LLM 컨텍스트 설정 + 특정 언어·도구 규칙

**의의**: 규칙이 로컬 파일이고, **중앙 배포 개념이 없다.**
각 팀이 자기 repo에 파일을 둔다. 다중 도구 통합은 별도 주제.

### 3.6 OpenHands

`[researched: openhands.ai 공식 문서]`

- **config**: `~/.openhands/config.json`
- **범위**: 에이전트 능력, 모델 설정, 샌드박스 구성
- **배포**: 설정 파일 (선언적 규범 아님)

**의의**: 규범·룰 개념이 약하고, 설정 중심.

### 3.7 Copilot (GitHub)

`[researched: 공식 GitHub 문서 + CHANGELOG 인용]`

- **컨텍스트**: 리포 `.github/copilot-instructions.md` (또는 조직 레벨)
- **배포**: Markdown 문서 (구조화 스키마 아님)
- **범위**: 일반 지시문

**의의**: AGENTS.md 와 달리 구조화 규범이 아니라 **자유형 문서**.
단일 소스를 여러 하네스로 배포하는 패턴이 아님.

---

## 4. 비교 분석

### 4.1 우리가 하는데 다른 곳은 안 하는 것

#### ★ 드리프트 게이트 (기계 강제)

`[판정: 우리만의 특징으로 보인다]`

- **우리**: 생성물 ≠ 소스 → `verify-done.sh` exit 1
- **superpowers**: 버전 팬아웃(예방)하나, 생성물 동기화 강제는 명시 없음
- **다른 도구들**: 게이트 개념 자체가 없음 (설정 파일이거나 수동 배포)

**가치**: "대상 파일이 낡은 상태로 커밋되는 것"을 방지한다.
다른 쪽은 이를 개발 훈련/PR 검토로 의존한다.

#### ★ 마커 기반 사용자 콘텐츠 보호

`[판정: 우리만의 설계로 보인다]`

- **우리**: 마커 블록 밖은 불가침 + 줄 앵커 + sha256 기반 손상 감지
- **superpowers**: 심링크·타겟별 파일로 분리 (보호 개념은 다름)
- **다른 도구들**: 대체로 단일 설정 파일 또는 환경 변수

**가치**: 같은 파일을 두 부분(우리 규범 + 사용자 지시문)으로 사용할 때 안전성 보증한다.

#### 이식성 선언 (frontmatter `portable`)

`[판정: 이 형태는 우리만]`

- **우리**: `portable: true|false` frontmatter 로 하네스별 포함/제외 제어
- **superpowers**: 타겟별 파일 분리 (`.cursor-plugin/`, `.hermes-plugin/` 등)

**가치**: 같은 파일을 유지하면서 **런타임**에 배포 대상을 결정한다.
(superpowers는 빌드 타임에 매니페스트별로 다른 파일을 생성하는 방식)

### 4.2 다른 곳이 하는데 우리는 안 하는 것 — 가치 있는 것

#### 버전 팬아웃 자동화 (`.version-bump.json`)

`[confirmed: superpowers; researched: practice]`

v2.15.0 사건(plugin.json 버전 올렸으나 생성물 미재생성): superpowers는 이를 구조화해 방지한다.

```json
{ "files": [
    { "path": ".claude-plugin/plugin.json",   "field": "version" },
    { "path": ".cursor-plugin/plugin.json",   "field": "version" },
    ...
  ],
  "audit": { "exclude": [...] }
}
```

**우리의 대응**: `scripts/build-targets.py --write` 가 이를 자동화하나, **수동 호출**.
더 나은 방식: 버전 파일(`.version`)을 SSOT 로 두고, 모든 매니페스트가 그것을 참조하게 하기.
(superpowers도 정확히 그래서 여러 파일이 항상 동기화된다)

#### 마켓플레이스별 배포 워크플로우

`[confirmed: superpowers scripts/sync-to-codex-plugin.sh; 판정: Codex-specific]`

Codex 공개 마켓플레이스가 별도 저장소(`prime-radiant-inc/openai-codex-plugins`)이므로,
PR을 그곳으로 보내는 자동화가 가능하다.

**우리**: Codex 마켓플레이스 진입 경로가 불명확했던 상태 (2026-08-27 기준).
지금은 `docs/codex-submission-checklist.md` 에 수동 절차 남아 있음.

### 4.3 찾지 못한 것들

#### 다른 곳의 드리프트 게이트

`[판정 불가]`

깊이 있게 조사한 superpowers도 "버전 팬아웃"은 하나 **"생성물 동기화 강제"** 는 명시 안 함.
다른 도구들(Cursor·Hermes·Continue·aider)은 구조화 규범 배포 자체를 하지 않아 비교 대상 아님.

#### 크로스 하네스 런타임 검증 자동화

`[판정 불가]`

superpowers evals는 "스킬 행동"을 tmux 세션에서 실제 돌려 검증하는 방식을 쓴다.
우리는 에이전트 단위 evals만 있음. 다중 하네스 인수 테스트(스킬이 각 하네스에서 작동함)는 미개척.

---

## 5. 결론 및 추천

### 우리 설계의 강점

1. **드리프트 게이트** — 다른 곳에 명시 없음. 낡은 규범이 배포되는 실수를 기계로 방지한다.
2. **마커 기반 보호** — 같은 파일을 두 부분으로 안전하게 사용한다.
3. **이식성 선언** — 같은 파일로 여러 하네스를 서포트하면서도 선택 가능하게 한다.

### 배워올 만한 점

1. **버전 팬아웃** (superpowers에서)
   - 대안: `.version` SSOT 도입, 모든 `plugin.json` 이 그것을 참조
   - 비용: 낮음 (생성기 수정)
   - 가치: v2.15.0 재발 방지

2. **버전 라우팅 자동화** (superpowers에서)
   - 현재: 수동으로 `./scripts/build-targets.py --write` 호출
   - 더 나은: 버전 파일 변경 시 자동 재생성 (git hook 또는 CI)
   - 비용: 중간
   - 가치: 실수 방지

### 안 배워올 것

1. **타겟별 파일 분리** — superpowers의 방식은 폐기할 이유가 없지만, 우리 "단일 소스 + 런타임 배포"가 더 간단하다.
2. **Cursor/Pi 지원** — Cursor는 우리를 지원할 능력이 있으나 런타임 검증이 미완료.
   Pi는 TypeScript 필수라 우리 생성 모델과 이질적.

### 최종 판정

**우리의 크로스 하네스 규범 배포 설계는 검증된 접근이다.** superpowers 같은 공식 플러그인도 같은 축(AGENTS.md 표준)을 택했고,
드리프트 게이트·마커 보호·이식성 선언은 우리의 차별점이다.

개선 여지:
- 버전 동기화 자동화 (낮은 비용)
- 타겟별 런타임 검증 (Cursor, 고비용)
- Codex 마켓플레이스 자동 배포 (중간 비용)

---

## 부록 A — 조사 범주별 정리

### 1️⃣ "단일 소스를 여러 하네스로" 패턴

| 도구 | 패턴 | 증거 |
| --- | --- | --- |
| **hiway-kit** | AGENTS.md 생성 + SessionStart 훅 주입 | `[confirmed: CLAUDE.md, export_harness.py]` |
| **superpowers** | 다중 매니페스트 생성 + AGENTS.md 심링크 | `[confirmed: github.com/obra/superpowers]` |
| **Cursor** | `.cursor-plugin/plugin.json` 이식성 검증 | `[confirmed: cursor.com/docs]` |
| **Hermes** | 자체 생태 (외부) | `[researched: docs/native-absorption.md]` |
| **Continue** | 환경 변수 / 로컬 config | `[researched: continue.dev]` |
| **aider** | 로컬 `.aider.rules` (배포 없음) | `[researched: aider.chat]` |
| **OpenHands** | 설정 파일 (배포 없음) | `[researched: openhands.ai]` |
| **Copilot** | 자유형 Markdown (구조 없음) | `[researched: github.com/docs]` |

### 2️⃣ 드리프트 게이트

| 도구 | 드리프트 강제 | 메커니즘 | 증거 |
| --- | --- | --- | --- |
| **hiway-kit** | ✅ Yes | `verify-done.sh` exit 1 on mismatch | `[confirmed]` |
| **superpowers** | ❓ Unknown | 명시 없음 (버전 팬아웃만 봄) | `[researched: 저장소 검사]` |
| **다른 도구들** | ❌ No | 게이트 개념 부재 | `[researched]` |

**결론**: 우리만의 특징인 가능성 높음.

### 3️⃣ 사용자 콘텐츠 보호

| 도구 | 방식 | 증거 |
| --- | --- | --- |
| **hiway-kit** | 마커 블록 + 줄 앵커 + sha256 손상 감지 | `[confirmed]` |
| **superpowers** | 파일 분리 (타겟별 디렉토리) | `[confirmed]` |
| **다른 도구들** | 일반적으로 단일 파일 관리 | `[researched]` |

---

## 부록 B — 조사 한계 (판정 불가 항목)

1. **Hermes 규범 배포 상세**: 자체 저장소(`agentskills.io`)가 있어 다른 킷과 경쟁 관계.
   우리가 배워올 메커니즘이 아님.

2. **Cursor 런타임 검증**: 공식 스키마는 확인했으나, 실제 Cursor CLI 에서 에이전트·규칙이 작동하는지
   검증 못 함. (스펙은 맞으나 구현이 그대로인지 불확실)

3. **다른 하네스의 드리프트 게이트**: 조사한 도구 대부분이 구조화 규범 배포를 하지 않아
   "드리프트 강제"를 한다는 개념 자체가 없음.

---

**보고일**: 2026-09-11  
**상태**: 완료  
**출처 태그 정책**: 
- `[confirmed: ...]` — 공식 저장소·문서 직접 조사
- `[researched: n=N]` — N개 이상 2차 출처
- `[판정 불가]` — 검증 수단 없음

---

## 컨트롤 검토 (2026-09-11, 병합 시)

이 보고서는 **조사 워커의 산출물이고, 컨트롤이 두 곳을 정정·보강한다.**

### 정정 — §5 "배워올 점 1. 버전 팬아웃"은 **이미 구현돼 있다**

워커가 superpowers 의 `.version-bump.json` 팬아웃을 배워올 점으로 제시했으나,
이 레포는 **이미 `scripts/bump-version.sh`** 로 같은 문제를 푼다 — 버전 갱신 + 생성물
재생성 + `--check` 자기 검증을 한 명령으로 묶고, `verify-done.sh §14` 가 드리프트를
exit 1 로 잡는다.

그 스크립트의 헤더가 **바로 그 비교를 이미 적어 두고 있다**:

> *"탐지보다 예방이 낫다(superpowers 의 `.version-bump.json` 팬아웃과 같은 동기, 다만
> 우리 매니페스트는 값이 아니라 **생성물**이므로 팬아웃 대신 재생성이 정답이다 —
> `docs/research/2026-08-27-superpowers-distribution.md` §3)."*

즉 이 축은 2026-08-27 에 이미 조사·판정·구현됐다. 워커가 그것을 확인하지 않고 신규
제안으로 올렸다. **조사 전에 레포가 이미 아는 것을 먼저 확인하라** — 이 항목이 그 사례다.

### 보강 — Hermes 절의 등급은 `[researched]` 이고 **1차 출처가 아니다**

사용자의 원 질문은 *"Hermes 가 툴 간 규범·룰 로직을 잘 통합한다고 들었다"* 였다.
그런데 §3.3 의 근거는 `docs/native-absorption.md` 와 CHANGELOG — **이 레포 자신의 과거
메모**다. 공식 문서·저장소를 직접 본 것이 아니다.

따라서 이 보고서는 *"Hermes 는 규범 통합 도구가 아니라 스킬 자동 승격 도구다"* 를
**확인한 것이 아니라 우리 과거 판정을 재인용한 것**이다. 그 판정이 맞을 수는 있으나
**이 조사로 새로 검증되지는 않았다.** 그 축이 중요해지면 1차 출처로 다시 조사해야 한다.
(§측정 9: 재현 수는 관측에 붙는 라벨이지 추론에 붙는 것이 아니다.)

### 유지되는 결론

위 둘을 덜어내도 남는 것이 이 조사의 값이다:

- **`AGENTS.md` 가 다중 하네스의 사실상 표준**이라는 것 — 우리 폴백 경로 선택이 옳았다.
- **드리프트 게이트를 하는 곳을 찾지 못했다** `[판정 불가]` — 다만 그 이유가 중요하다:
  조사한 도구 대부분이 **구조화된 규범 배포 자체를 하지 않아** 비교 대상이 아니었다.
  "우리만 한다"가 아니라 **"그 문제를 가진 곳이 드물다"** 가 더 정확한 서술이다.
- **다중 하네스 런타임 인수 테스트**가 미개척이라는 지적은 유효하다. 다만 그 사이
  Codex 에 대해서는 실물 검증이 생겼다(`packaging/targets.json` 의 관측 기록 참고).
