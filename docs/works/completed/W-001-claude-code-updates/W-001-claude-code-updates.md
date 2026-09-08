---
work_id: "W-001"
title: "Claude Code v2.1.74~v2.1.86 업데이트 적용"
status: completed
current_phase: validation
phases_completed: [idea, planning, development, validation]
size: Medium
priority: P2
tags: [claude-code, hooks, skills, agents, mcp, ci]
created_at: "2026-03-29T00:00:00+09:00"
updated_at: "2026-04-02T04:59:01Z"
started_at: "2026-04-02T04:51:12Z"
completed_at: "2026-04-02T04:59:01Z"
---

# Claude Code v2.1.74~v2.1.86 업데이트 적용

> Work ID: W-001
> Status: planning
> 구현 계획: docs/works/idea/W-001-claude-code-updates/planning-results.md

## 요약

Claude Code v2.1.74~v2.1.86 업데이트 중 적용 가능한 항목 적용.
원본 13개 → Planning 결과 11개 확정 (2개 제거: `if` 필드 미지원, `--bare` CI 방침 불일치).

## 확정 항목 (11개)

### HIGH (3개)

- [ ] H-1: `ExitWorktree` 툴 — worktree 에이전트 5개 frontmatter 추가
- [ ] H-2: Skills에 `effort` frontmatter 추가 (plan-task, auto-dev, web-research)
- [ ] H-3: `/plan` description 인자 문서화 (plan-task/skill.md)

### MEDIUM (5개)

- [ ] M-1: `/loop` 스킬 추가 (ops 도메인 신규)
- [ ] M-2: Computer Use 옵션 문서화 (webapp-testing/skill.md)
- [ ] M-3: `rate_limits` 상태바 설정 (setup.sh)
- [ ] M-4: `autoMemoryDirectory` 설정 (setup.sh)
- [ ] M-5: `source: 'settings'` 경량 설치 옵션 (CLAUDE.md 문서화)

### LOW (3개)

- [ ] L-1: MCP 환경변수 문서화 (mcp-usage.md)
- [ ] L-2: Plugin Freshness 재검토 (조사 위주)
- [ ] L-3: Context Window 최적화 문서화 (mcp-usage.md)

### 신규 (기존 #9 대체)

- [ ] N-1: pre-commit 강화 — JSON + frontmatter 검증 추가

## 다음 단계

`/auto-dev W-001` 으로 Development Phase 시작.
