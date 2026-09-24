---
name: using-hiway-kit
description: Session-start meta-skill. Kit workflow chain and Work system rules.
---

# Using hiway-kit

**작업이 스킬의 사용 시점에 해당하면 구현 전에 그 스킬을 먼저 invoke한다.** 같은 규율을 제공하는
플러그인(superpowers 등)이 함께 설치돼 있으면 그쪽을 따라도 된다 — 킷은 그 존재를
가정하지도, 충돌하지도 않는다.

## Workflow Chain

```
brainstorming → plan-task → auto-dev
```

**brainstorming**(설계·스펙) 과 **plan-task**(구조화 계획) 는 HARD-GATE,
**auto-dev** 는 구현 + 검증 파이프라인이다. 게이트·루프·완료 규율은 `rules/` 가 이미
주입했다 — 여기서 다시 쓰지 않는다.

## Work System Detection

`docs/works/` 가 있으면 Work ID 기반 추적, 없으면 파일 없이 파이프라인만 실행(fallback).
