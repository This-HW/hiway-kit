# Planning 결과: Claude Code v2.1.74~v2.1.86 업데이트 적용

> Work ID: W-001
> Last Updated: 2026-04-02T13:46:43+09:00

## 규모 판단

**Medium** — 11개 항목, 변경 파일 ~20개, 항목당 복잡도 낮음~중간

## 요구사항 명확화

### 확정 항목 (11개) — 원본 13개에서 2개 제거

| 제거 항목 | 이유 |
|-----------|------|
| #1 Conditional Hooks `if` 필드 | 공식 문서(v2.1.89) 미지원. 내부 파일 확장자 필터링이 이미 올바른 구현 |
| #9 `--bare` CI 통합 | CI 최소화 방침과 불일치. pre-commit 강화로 대체(N-1) |

### 스킬 파일 현황 확인

| 스킬 | 경로 | 상태 |
|------|------|------|
| plan-task | `plugins/common/skills/plan-task/skill.md` | ✅ 존재 |
| auto-dev | `plugins/common/skills/auto-dev/skill.md` | ✅ 존재 |
| web-research | `plugins/common/skills/SKILL.md` | ✅ 존재 (루트 SKILL.md) |
| review | 외부 (superpowers plugin) | ❌ 이 프로젝트 파일 아님 |
| multi-perspective-review | 외부 (superpowers plugin) | ❌ 이 프로젝트 파일 아님 |

## 구현 계획

### 개발 Task 구조 (모두 독립 → 전부 병렬 실행 가능)

```
T-dev-1: [W-001][Dev] 에이전트 frontmatter 업데이트 (H-1)
T-dev-2: [W-001][Dev] 스킬 frontmatter + /plan 문서화 (H-2, H-3)
T-dev-3: [W-001][Dev] 문서 업데이트 (M-2, L-1, L-3)
T-dev-4: [W-001][Dev] /loop 스킬 신규 생성 (M-1)
T-dev-5: [W-001][Dev] setup.sh 강화 (M-3, M-4, M-5)
T-dev-6: [W-001][Dev] pre-commit 강화 (N-1)
T-dev-7: [W-001][Dev] Plugin Freshness 검토 (L-2)
```

Validation (T-dev-1~7 완료 후 병렬):
```
T-review:   [W-001][Validation/A] 코드 리뷰
T-security: [W-001][Validation/B] 보안 스캔
T-merge:    [W-001][Validation] 결과 통합   ← blockedBy T-review, T-security
```

---

### T-dev-1: 에이전트 frontmatter 업데이트 (H-1 ExitWorktree)

**변경 파일 (5개):**

| 파일 | 현재 tools | 변경 |
|------|-----------|------|
| `plugins/common/agents/dev/implement-code/implement-code.md` | Read, Write, Edit, Glob, Grep, Bash | + ExitWorktree |
| `plugins/common/agents/dev/fix-bugs.md` | Read, Edit, Bash, Glob, Grep | + ExitWorktree |
| `plugins/common/agents/dev/write-tests.md` | Read, Write, Edit, Glob, Grep, Bash | + ExitWorktree |
| `plugins/common/agents/backend/write-api-tests.md` | Read, Write, Edit, Bash, Glob, Grep | + ExitWorktree |
| `plugins/frontend/agents/write-ui-tests.md` | Read, Write, Edit, Bash, Glob, Grep | + ExitWorktree |

---

### T-dev-2: 스킬 frontmatter + /plan 문서화 (H-2, H-3)

**변경 파일 (3개):**

| 파일 | 변경 내용 |
|------|---------|
| `plugins/common/skills/plan-task/skill.md` | frontmatter에 `effort: max` 추가 + 사용법 섹션에 `/plan-task [description]` 형식 문서화 |
| `plugins/common/skills/auto-dev/skill.md` | frontmatter에 `effort: high` 추가 |
| `plugins/common/skills/SKILL.md` (web-research) | frontmatter에 `effort: medium` 추가 |

---

### T-dev-3: 문서 업데이트 (M-2 Computer Use, L-1 MCP 환경변수, L-3 Context Window)

**변경 파일 (2개):**

| 파일 | 변경 내용 |
|------|---------|
| `plugins/frontend/skills/webapp-testing/skill.md` | Computer Use 섹션 추가 — Playwright MCP 대신 Computer Use를 fallback으로 사용하는 방법 |
| `plugins/common/rules/mcp-usage.md` | 환경변수 섹션 추가 (TAVILY_API_KEY, EXA_API_KEY 등) + Context Window 최적화 섹션 (disallowedTools로 MCP 비활성화) |

---

### T-dev-4: /loop 스킬 신규 생성 (M-1)

**변경 파일 (2개):**

| 파일 | 변경 내용 |
|------|---------|
| `plugins/ops/skills/loop/skill.md` (신규) | CronCreate/CronList/CronDelete 기반 반복 실행 스킬. `/loop 5m /monitor`, `/loop 1h /security-scan` 패턴 |
| `plugins/ops/.claude-plugin/plugin.json` | skills 배열에 loop 추가 |

---

### T-dev-5: setup.sh 강화 (M-3 rate_limits, M-4 autoMemoryDirectory, M-5 source:settings)

**변경 파일 (1개):**

`setup.sh`에 새 섹션 추가 — `~/.claude/settings.json`에 아래 설정 주입 (python3 JSON merge):

```json
{
  "statusline": { "rate_limits": true },
  "autoMemoryDirectory": "~/.claude/projects/{project-hash}/memory/"
}
```

M-5 (`source: 'settings'`): CLAUDE.md에 설치 방법 문서 추가 (settings.json 직접 등록 방법)

---

### T-dev-6: pre-commit 강화 (N-1)

**변경 파일 (1개):**

`plugins/common/setup/pre-commit`에 추가:
1. staged `.json` 파일 (plugin.json, marketplace.json) → `python3 -m json.tool` 검증
2. staged `.md` 파일 중 `plugins/` 하위 → frontmatter `name:`, `description:` 필수값 확인

---

### T-dev-7: Plugin Freshness 검토 (L-2)

**변경 파일:** 조사 결과에 따라 최소 (0~1개)

`@stable` ref-tracked 플러그인이 매 로드 시 re-clone 되는 v2.1.81 변경사항 검토.
현재 plugin.json version 전략이 의도대로 동작하는지 확인. 변경 필요 시 plugin.json 업데이트.
