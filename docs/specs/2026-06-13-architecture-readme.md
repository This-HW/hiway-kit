# Architecture README 설계 (Spec 4)

**Goal:** README에 "claude-code-kit이 어떤 로직·개념을 어떻게 융합하는가"를 설명하는 아키텍처 섹션을 추가하여, 사용자/기여자가 프로젝트의 설계 철학과 구성 원리를 한눈에 이해하게 한다.

**Architecture:** SSOT 원칙 준수 — CLAUDE.md/스펙의 세부 내용을 복사하지 않고 개념적 융합 narrative + 다이어그램만 제공하고 세부는 링크한다. 설명 대상은 네 갈래의 융합: (1) Claude Code 네이티브 프리미티브, (2) superpowers 규율 방법론, (3) Hermes 피드백 루프, (4) 자체 Work 시스템.

**Version:** 2.5.0 → 2.5.1 (patch bump — 문서 전용) 또는 Spec 1~3과 함께 minor에 흡수

**Depends on:** Spec 1~3 설계 확정(완료). 기능 결합 없음 — 순수 문서.

---

## 요구사항

1. README에 "Architecture & Concepts" 섹션 추가.
2. 네 갈래 융합(네이티브 / superpowers 규율 / Hermes 피드백 / Work 시스템)을 narrative로 설명.
3. 핵심 설계 원칙("네이티브 우선, 자체 = 의견 레이어, zero-debt") 명시.
4. 개념 다이어그램(workflow 체인 + 스케일별 오케스트레이션 + 피드백 루프).
5. SSOT 준수 — 세부는 CLAUDE.md/specs로 링크, 복사 금지.

## 접근 방식

**개념 narrative + 다이어그램 + 링크.**
README 상단부(설치 이후)에 섹션을 삽입. 기존 구조/스킬 표는 유지하고 그 위에 "왜/어떻게"를 설명하는 레이어를 얹는다.

## 컴포넌트 구조

### 변경 1 — README "Architecture & Concepts" 섹션
- 대상: `README.md`
- 하위 구성:
  1. **설계 철학**: 네이티브 프리미티브 우선, kit의 가치 = 의견이 담긴 에이전트/스킬/규율 레이어, zero-debt 원칙
  2. **네 갈래 융합**:
     - Claude Code 네이티브: agents/skills/hooks/dynamic workflows/OTEL/memory
     - superpowers 규율: brainstorming→plan→execute, phase gate, TDD, verification-before-completion
     - Hermes 피드백 루프: validation 결과 → 학습 메모리 → 구현 컨텍스트
     - Work 시스템: 파일 기반 감사 가능 추적
  3. **결합 방식 다이어그램**: 워크플로우 체인 + 스케일별 오케스트레이션 + 피드백 루프
  4. **세부 링크**: CLAUDE.md, docs/specs, rules

### 변경 2 — 한국어/영어 정합
- 기존 README 언어 컨벤션 확인 후 일관 유지

## 데이터 흐름

```
README 독자
  → "설계 철학"으로 WHY 이해
  → "네 갈래 융합"으로 WHAT 이해
  → "다이어그램"으로 HOW(결합) 이해
  → 링크로 세부(CLAUDE.md/specs) 심화
```

## 에러 처리

- 해당 없음(정적 문서). 링크 무결성만 확인.

## 테스트 전략

- 마크다운 렌더 확인, 링크 유효성, 다이어그램 표시.
- CLAUDE.md와 중복 서술 없는지 검토(SSOT).

## 범위 외

- 기능 변경 없음.
- 다국어 전체 번역(기존 컨벤션만 따름).

## 알려진 가변 지점

다이어그램 표현(ASCII vs mermaid)은 기존 README 컨벤션에 맞춤. 융합 narrative는 Spec 1~3 구현 후 실제 동작과 정합되게 최종 조정(구현 완료 시점에 1회 검토).
