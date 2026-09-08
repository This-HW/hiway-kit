---
title: "시작하기"
description: "hiway-kit 설치부터 핵심 스킬 워크플로우(brainstorming → plan-task → auto-dev, /review, /debug, /test)까지 실제 사용 시나리오."
keywords: ["claude code plugin install", "claude code skill workflow", "auto-dev", "plan-task"]
translationKey: "getting-started"
---

## 설치

두 가지 경로가 있다.

```bash
# 경로 1 — Anthropic 커뮤니티 카탈로그에 등재된 버전
/plugin marketplace add anthropics/claude-plugins-community
/plugin install hiway-kit@claude-community

# 경로 2 — 저장소에서 직접 (최신 커밋 추종)
/plugin marketplace add This-HW/hiway-kit
/plugin install hiway-kit@hiway-kit
```

보안 훅(`protect-sensitive`, `auto-format`, `stop-validator`)과 pre-commit까지
로컬에 설치하려면 저장소를 클론해 `setup.sh`를 실행한다.

```bash
git clone https://github.com/This-HW/hiway-kit
cd hiway-kit
./setup.sh
```

## 핵심 워크플로우: 아이디어 → 배포 가능한 코드

전형적인 흐름은 "브레인스토밍으로 모호성을 없애고 → 계획을 게이트로 확정하고
→ 구현·검증은 루프로 자율 완주"한다.

```
brainstorming  →  /plan-task  →  /auto-dev  →  /review  →  /test
   (발산)          (계획 확정)      (구현 파이프라인)   (병렬 검증)   (회귀 확인)
```

### 1. brainstorming — 아이디어 발산과 모호성 표면화

새 기능이나 리팩토링을 시작하기 전, 요구사항이 덜 굳어 있다면 브레인스토밍부터
한다. 여러 관점(사용자 시나리오, 엣지케이스, 트레이드오프)을 강제로 열거해
"게이트에서 멈춰야 할 지점"을 미리 드러낸다.

### 2. `/plan-task` — 구조화된 태스크 계획

```
/plan-task 사용자 프로필 페이지에 아바타 업로드 기능 추가
```

요구사항의 모호성을 100% 제거하는 것이 목표다(Phase 1 게이트). 여기서
API 시그니처, 파일 위치, 완료 조건이 확정된다 — 다음 단계는 이 산출물을
그대로 구현 계약으로 사용한다.

### 3. `/auto-dev` — 자동화된 개발 파이프라인

```
/auto-dev
```

계획 산출물을 받아 구현 → 통합 → 검증까지 자동으로 진행한다. 파일을 수정하는
에이전트는 격리된 git worktree에서 동작해 병렬 작업 중 충돌을 방지한다.
대규모(10~100+ 파일) 작업은 청크로 쪼개 안내하며, 그보다 더 큰 스케일은
네이티브 `ultracode`(dynamic workflow)를 사용자가 직접 트리거하도록 유도한다.

### 4. `/review` — 코드 리뷰 (ruff + review-code + security-scan)

```
/review
```

린트(ruff), 아키텍처/스타일 리뷰(review-code), 보안 스캔(security-scan)을
병렬로 실행한다(Phase 3 Validation). 더 깊은 논쟁이 필요하면
`/multi-perspective-review`로 10개 페르소나 3라운드 심의를 돌릴 수 있다.

### 5. `/debug` — 4단계 디버그 파이프라인

버그를 재현·격리·수정·검증 4단계로 강제해, "증상만 고치고 원인은 남기는"
패턴을 막는다.

```
/debug 로그인 후 프로필 이미지가 간헐적으로 깨지는 문제
```

### 6. `/test` — 테스트 실행 및 자동 수정

```
/test
```

테스트를 실행하고 실패를 자동으로 고친다. 세션이 편집한 파일 범위로 스코핑되어
있어 전체 스위트를 매번 돌리지 않는다 — 전체 회귀는 CI의 몫이다.

## 그 다음

- 아키텍처 원리가 궁금하면 [소개](/about/)를 읽는다.
- 실제 적용 사례와 의사결정 과정은 [개발 기록](/posts/)에서 확인할 수 있다.
- 코드/이슈는 [GitHub 저장소](https://github.com/This-HW/hiway-kit)에서.
