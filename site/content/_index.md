---
title: "hiway-kit"
description: "Claude Code용 유니버설 툴킷 — 32개 전문 에이전트, 21개 스킬, 15개 거버넌스 룰로 멀티 에이전트 개발 파이프라인을 구축한다."
keywords: ["claude code", "claude code plugin", "멀티 에이전트", "AI 코딩 에이전트", "harness engineering", "loop engineering"]
---

**hiway-kit**은 [Claude Code](https://claude.com/claude-code) 위에서 동작하는
유니버설 개발 툴킷이다. 하나의 하네스(harness) 위에 계획(Planning) · 구현(Development) ·
검증(Validation) 3단계 파이프라인을 멀티 에이전트로 구성해, "빠르게 만드는 것"이 아니라
**끝까지 검증된 상태로 완주하는 것**을 목표로 한다.

<div class="callout">
<strong>핵심 지표</strong>

- 전문 에이전트 **32개** (계획·구현·리뷰·리팩토링 전 단계)
- 스킬 **21개** (`/plan-task`, `/auto-dev`, `/review`, `/debug`, `/test` 등)
- 거버넌스 룰 **15개** (병렬 worktree, 위임 체인, 완료 정의 등)
- 유닛 테스트 **220개 이상**
- Agent Behavior Evals **11개 시나리오** (deterministic-first 채점)
- 기계 게이트(machine gate) **8개 이상** (`verify-done.sh`)
</div>

## 설치

```bash
# 경로 1 — Anthropic 커뮤니티 카탈로그
/plugin marketplace add anthropics/claude-plugins-community
/plugin install hiway-kit@claude-community

# 경로 2 — 저장소 직접 등록
/plugin marketplace add This-HW/hiway-kit
/plugin install hiway-kit@hiway-kit
```

전체 훅(보안 스캔·자동 포맷·pre-commit)까지 포함한 완전 설치는
[`README`](https://github.com/This-HW/hiway-kit#installation)를 참고한다.

더 알아보기: [시작하기](/getting-started/) · [소개(아키텍처)](/about/) · [개발 기록](/posts/)
