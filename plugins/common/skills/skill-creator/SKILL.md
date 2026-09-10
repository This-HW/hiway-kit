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

**서브에이전트 위임 수단이 없는 하네스에서는 같은 계약을 이 세션에서 직접 수행한다.**
각 블록의 `prompt:` 를 자기 지시로 읽고, 같은 항목을 같은 형식으로 산출한다.
**수단이 없다고 단계를 건너뛰지 마라. 하지 않은 위임을 했다고 보고하지도 마라.**
쓸 수 있는 수단은 호스트에 직접 확인한다 — 이 문서는 위임이 가능하다고 보증하지 않는다.

> **직접 수행의 대가 — 격리 이점은 사라진다.** 직접 수행은 이 세션의 컨텍스트를
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

> 이 단계는 `[agent-name]` 에게 위임한다. **위임 수단이 없는 하네스에서는 아래 계약을
> 이 세션에서 직접 수행한다** — 페르소나·출력 형식·완료 선언은 **동일하다.** 수단이
> 없다고 단계를 건너뛰지 마라. 직접 수행하면 **사각지대 분리(격리) 이점은 사라진다.**

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
