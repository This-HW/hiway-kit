---
work_id: "W-004"
title: "Rules Injection 최적화"
status: completed
current_phase: validation
phases_completed: [planning, development, validation]
size: Medium
priority: P1
tags: [rules, session-start, llm-instructions, context-injection, docs]
created_at: "2026-04-09T00:00:00Z"
updated_at: "2026-04-09T00:00:00Z"
---

# Rules Injection 최적화

> Work ID: W-004
> Status: planning → development

---

## 요구사항

현재 `plugins/common/rules/` 파일들이 Claude Code plugin 시스템에 로드되지 않는다.
SessionStart hook을 통해 규칙을 주입하되, 토큰 효율이 높은 LLM instruction 형식으로 전환한다.
동시에 사람이 이해하기 쉬운 human-readable 문서를 `docs/architecture/rules/`에 신규 작성한다.

### 핵심 목표

**A. Rule 파일을 LLM instruction 형식으로 재작성**

- 현재: 문서 스타일 (표, 예시코드, 배경 설명) — ~6,384 tokens
- 목표: 명령형 instruction 스타일 (DO/DON'T, bullet list) — ~3,000 tokens 이하
- 9개 파일 전체 재작성

**B. Human-readable 문서 신규 작성**

- `docs/architecture/rules/` 하위에 9개 문서
- 표, 예시코드, 설명 풍부하게 — 사람이 읽기 쉽게
- rule 파일과 동일 주제, 다른 형식

**C. session-start.py에 rules 주입 로직 추가**

- 모든 rule 파일 읽어 `additionalContext`로 주입
- `task-resume.md`는 Active Work 있을 때만 주입 (조건부)
- Active Work 컨텍스트와 단일 `additionalContext`로 합산 출력

---

## Planning 결과

### LLM Instruction 형식 스펙

```
# [규칙명]

ALWAYS/NEVER/DO/DON'T 로 시작하는 명령문
배경 설명 없음. 예시는 코드 1개까지만.
줄글 설명 제거. 테이블은 2열 bullet list로 압축.
```

예시 변환:

```
❌ 기존 (문서 스타일):
## 도구 매핑표
| 작업 | ❌ Bash | ✅ 전용 도구 |
| 파일 읽기 | cat, head | Read |

✅ 신규 (instruction 스타일):
NEVER use cat/head/tail — use Read.
NEVER use grep/rg — use Grep.
NEVER use find — use Glob.
```

### 조건부 주입 규칙

| 파일                      | 주입 조건             |
| ------------------------- | --------------------- |
| agent-system.md           | 항상                  |
| tool-usage-priority.md    | 항상                  |
| planning-protocol.md      | 항상                  |
| planning-check.md         | 항상                  |
| agent-delegation-chain.md | 항상                  |
| code-quality.md           | 항상                  |
| ssot.md                   | 항상                  |
| mcp-usage.md              | 항상                  |
| task-resume.md            | Active Work 있을 때만 |

### session-start.py 출력 구조

```
=== ACTIVE WORK ===        ← Active Work 있을 때만
[work summaries]
=== END ACTIVE WORK ===

=== RULES ===
[agent-system content]
---
[tool-usage-priority content]
---
...
=== END RULES ===
```

모든 내용이 단일 `additionalContext` 값으로 출력됨.
