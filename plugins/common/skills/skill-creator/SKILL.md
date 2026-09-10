---
name: skill-creator
description: Create new Claude Code skills. Applies standard templates and best practices to scaffold a skill file automatically.
model: sonnet
effort: medium
---

# Skill Creator

> Claude Code 스킬을 빠르고 정확하게 생성

베스트 프랙티스를 적용한 스킬을 자동 생성합니다.

---

## 사용법

### 신규 스킬 생성

```
/skill-creator "데이터 분석" data-analysis
/skill-creator "API 모니터링" api-monitor
/skill-creator "보안 검사" security-audit
```

---

## 생성 워크플로우

### 1. 요구사항 수집

다음 정보를 확인합니다:

- 스킬 이름 (kebab-case)
- 스킬 설명
- 사용 시점 (when to use)
- 필요한 도구
- 모델 (opus/sonnet/haiku)

### 2. Frontmatter 생성

```yaml
---
name: skill-name
description: What it does + when to use
model: sonnet | opus | haiku
effort: low | medium | high | max
---
```

### 3. 본문 작성

**구조:**

1. 개요
2. 사용법
3. 워크플로우
4. 예시
5. 관련 도구

---

## 스킬 위치

`plugins/{domain}/skills/{name}/SKILL.md` 경로에 파일을 생성한다.
**manifest(`plugin.json`)에는 skill 레지스트리가 없다** — 디렉토리에서 자동 발견되므로
등록 단계가 없다.

---

## 스킬 템플릿

### 기본 템플릿

```markdown
---
name: skill-name
description: Brief description. Use when [scenario].
model: sonnet
effort: medium
---

# Skill Title

> One-line tagline

Brief overview of what this skill does.

---

## 사용법

/skill-name [arguments]
/skill-name "specific task"

---

## 워크플로우

### 1. Step One

Description...

### 2. Step Two

Description...

---

## 예시

/skill-name example-input

**Result:** Description of result

---

## 관련 도구

- **related-agent**: Description
```

---

## 위임 수단이 없는 하네스 — 강등 경로 (이 스킬의 **모든** 위임 블록에 적용)

아래 단계들은 `Task tool 사용:` / `subagent_type:` 형태로 전용 에이전트에게 위임한다.
**그 위임은 계약을 실행하는 한 가지 운송 수단일 뿐이고, 불변식은 각 블록의 `prompt:`
본문에 적힌 계약이다** — 페르소나·검사 항목·출력 형식·완료 선언이 그것이다.

운송은 **사다리**다. 위에서부터 쓸 수 있는 것을 쓰고, **한 칸씩 내려간다 — 건너뛰지 않는다.**
쓸 수 있는 수단은 호스트에 직접 확인한다 — 이 문서는 위임이 가능하다고 보증하지 않는다.

**1단 — 네이티브 서브에이전트.** 아래 블록을 그대로 쓴다. **격리 있음.**

**2단 — 호스트가 제공하는 위임 수단.** 네이티브 서브에이전트가 없어도, **격리된 별도
작업을 띄우는 수단을 호스트가 제공할 수 있다.** 있으면 그것을 쓴다 — 수단의 이름은
하네스마다 다르므로 여기 적지 않는다(배포물이 특정 하네스를 전제하면 다른 하네스에서
그 지시가 죽는다). 넘기는 방법이 이 단의 전부다:

- 지시문은 **에이전트 정의 파일의 본문을 그대로** 넘긴다 — 설치본의
  `<플러그인 루트>/agents/<카테고리>/<이름>.md`. `$CLAUDE_PLUGIN_ROOT` 가 설정돼
  있으면 그것이 플러그인 루트지만 **빈 값일 수 있으니 파일 존재를 확인하고**, 없으면
  플러그인 캐시에서 같은 상대경로를 찾는다.
- **요약해서 넘기지 마라.** 페르소나·검사 항목·출력 형식·완료 선언이 그 본문에 있고,
  요약하면 그 계약이 손실된다 — 그러면 2단은 운송이 아니라 다른 작업이 된다.
- 정의 본문 **뒤에** 이 블록의 `prompt:` 를 붙여 대상·범위를 준다.
- **회신은 자기보고다.** 위임 수단이 "했다"고 돌려준 요약이 아니라 **계약이 요구하는
  산출물 자체**(리포트 본문·완료 선언·파일)로 판정하라.
- **격리는 유지된다** — 별도 컨텍스트에서 돌므로 사각지대 분리 효과가 살아 있다.
  따라서 아래 3단의 강등 표시를 붙이지 않는다.

**3단 — 이 세션에서 직접 수행.** 1·2단이 **모두** 없을 때만 여기로 내려온다.
**서브에이전트 위임 수단이 없는 하네스에서는 같은 계약을 이 세션에서 직접 수행한다.**
각 블록의 `prompt:` 를 자기 지시로 읽고, 같은 항목을 같은 형식으로 산출한다.
**수단이 없다고 단계를 건너뛰지 마라. 하지 않은 위임을 했다고 보고하지도 마라.**

> **3단(직접 수행)의 대가 — 격리 이점은 사라진다.** 직접 수행은 이 세션의 컨텍스트를
> 공유하므로 별도 에이전트의 **사각지대 분리** 효과가 없다. 생성될 스킬의 설계를 같은 세션이 검토하게 되어 템플릿 적합성 판단이 자기확인이 된다. 상쇄책: 생성 후 산출물을 **파일에서 다시 읽어** frontmatter·필수 절 존재를 확인하라.
> 없는 이점을 있다고 쓰지 않기 위해 명시한다.

### Task 에이전트 호출 템플릿

**생성되는 스킬에도 강등 경로를 함께 넣어라.** 위임 지시만 넣고 폴백을 빼면, 그 스킬은
에이전트를 노출하지 않는 하네스에서 **없는 도구를 쓰라고 지시**하게 된다 — 생성기가
결함을 복제하는 자리다.

```markdown
---
name: skill-name
description: Orchestrates agents for [purpose].
model: sonnet
effort: high
---

# Skill Title

## 워크플로우

> 이 단계는 `[agent-name]` 에게 위임한다. 운송은 사다리다 — ① 네이티브 서브에이전트,
> ② 없으면 **호스트가 제공하는 위임 수단**에 에이전트 정의 파일
> (`<플러그인 루트>/agents/<카테고리>/[agent-name].md`) **본문을 그대로** 지시문으로
> 넘긴다(요약 금지 — 계약이 손실된다). 격리는 유지된다. ③ 그마저 없으면,
> **위임 수단이 없는 하네스에서는 아래 계약을
> 이 세션에서 직접 수행한다** — 페르소나·출력 형식·완료 선언은 **동일하다.** 수단이
> 없다고 단계를 건너뛰지 마라. ③에서만 **사각지대 분리(격리) 이점이 사라진다.**

Task tool 사용:
subagent_type: [agent-name]
model: [model]
prompt: |
[프롬프트 내용]
```

---

## 모델 선택 가이드

| 작업 유형           | 권장 모델 | 이유             |
| ------------------- | --------- | ---------------- |
| 전략/분석/리뷰      | `opus`    | 복잡한 추론 필요 |
| 코드 구현/수정      | `sonnet`  | 균형잡힌 성능    |
| 탐색/검증/빠른 작업 | `haiku`   | 빠른 실행        |

---

## effort 선택 가이드

| effort   | 사용 시점                |
| -------- | ------------------------ |
| `low`    | Bash/MCP 단순 실행       |
| `medium` | 단일 에이전트 호출       |
| `high`   | 복수 에이전트 파이프라인 |
| `max`    | 전체 라운드 협업 (30분+) |

---

## 베스트 프랙티스

### $ARGUMENTS 활용

```markdown
에러 정보: $ARGUMENTS
대상: $ARGUMENTS (없으면 전체)
```

### 검증 체크리스트

스킬 생성 후 확인:

- [ ] Frontmatter 완전함 (name, description, model, effort)
- [ ] 설명이 명확함 (what + when to use)
- [ ] 사용법 예시 포함
- [ ] 워크플로우 단계별 설명
- [ ] `plugins/{domain}/skills/{name}/SKILL.md` 경로 준수
