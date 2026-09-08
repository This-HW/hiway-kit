# Planning 결과: Common Skills 마이그레이션 및 Phase Gate 아키텍처 정비

> Work ID: W-002
> Last Updated: 2026-04-05T07:10:00Z

---

## 규모 판단

**Large** — 20+ 파일, 3개 이상 모듈(common/skills, docs/architecture, hooks), 다수 업그레이드 포함

---

## 요구사항 명확화

### 현황 분석

| 항목                     | claude_setting | claude-code-kit         | 상태                               |
| ------------------------ | -------------- | ----------------------- | ---------------------------------- |
| review                   | ✅             | ❌                      | 누락                               |
| multi-perspective-review | ✅             | ❌                      | 누락                               |
| doc-coauthoring          | ✅             | ❌                      | 누락                               |
| debug                    | ✅             | ❌                      | 누락                               |
| test                     | ✅             | ❌                      | 누락                               |
| web-research             | ✅             | ⚠️ SKILL.md (구조 오류) | 이동 필요                          |
| agent-creator            | ✅             | ❌                      | 누락                               |
| skill-creator            | ✅             | ❌                      | 누락                               |
| mcp-builder              | ✅             | ❌                      | 누락                               |
| agent-teams              | ✅             | ❌                      | 누락 (experimental)                |
| phase-gates              | ✅ skill       | ❌                      | → Stop hook + 아키텍처 문서로 대체 |
| phase-gate-pattern.md    | ✅ docs/       | ❌                      | 문서 추가 필요                     |

### P0 결정사항

**DEC-001**: phase-gates를 스킬로 마이그레이션하지 않는다.

- 이유: Phase Gate는 메인 Claude의 판단 기준이지 명시적 호출 스킬이 아님 (아키텍처 문서 확인)
- 대신: Stop hook(prompt type)으로 자동 품질 검증 구현 + docs/architecture/phase-gate-pattern.md 추가

**DEC-002**: 각 스킬은 최신 Claude Code 기능으로 업그레이드하면서 마이그레이션한다.

- `effort` 필드 추가 (low/medium/high/max)
- `argument-hint` 필드 추가 (사용자 힌트)
- `allowed-tools` 최적화 (불필요한 도구 제거)
- 파일명 소문자 `skill.md`로 통일 (기존 `SKILL.md` → `skill.md`)

**DEC-003**: agent-teams는 experimental 표기를 명확히 한다.

- 환경변수 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 필요 명시

---

## 구현 계획

### 전체 작업 순서

```
Phase A (기반): web-research 구조 이동
Phase B (P0 스킬): review, multi-perspective-review + references, doc-coauthoring, debug, test
Phase C (P1 스킬): agent-creator, skill-creator, mcp-builder, agent-teams
Phase D (아키텍처): phase-gate-pattern.md, agent-system.md 보강, Stop hook
Phase E (문서): README.md, CLAUDE.md 카운트 업데이트, commit & push
```

---

### Phase A: web-research 구조 이동

**목표**: `SKILL.md` → `web-research/skill.md` (컨벤션 통일)

```
변경 전: plugins/common/skills/SKILL.md
변경 후: plugins/common/skills/web-research/skill.md
```

**작업**:

1. `mkdir plugins/common/skills/web-research/`
2. `mv plugins/common/skills/SKILL.md plugins/common/skills/web-research/skill.md`
3. 파일 내 frontmatter 확인 — name: web-research, effort: medium 이미 있음

---

### Phase B: P0 스킬 마이그레이션 (5개)

#### B-1: review

**소스**: `claude_setting/skills/common/review/SKILL.md`
**목적지**: `plugins/common/skills/review/skill.md`

**업그레이드 사항**:

- `effort: high` 추가 (review-code + security-scan 에이전트 두 개 실행)
- `argument-hint: [파일경로 | --quick | 빈칸(git diff 자동)]` 추가
- `allowed-tools: Read, Glob, Grep, Bash, Task` (기존과 동일)
- `model: opus` (기존과 동일)
- `disable-model-invocation: true` 추가 — 명시적 호출 스킬이므로

**보존 기능**:

- 0단계: ruff 정적 분석 (Python 파일 시)
- 1.5단계: Auto-Scope 판정 (보안파일 → adversarial, trivial → quick)
- 2단계: review-code Task 호출
- 3단계: security-scan 조건부 실행
- 4단계: 결과 요약

#### B-2: multi-perspective-review

**소스**: `claude_setting/skills/common/multi-perspective-review/SKILL.md` + `references/`
**목적지**: `plugins/common/skills/multi-perspective-review/skill.md` + `references/`

**업그레이드 사항**:

- `effort: max` 추가 (최장 30분, 최대 에이전트 동원)
- `argument-hint: [문서경로 | Work ID | 빈칸(현재 변경사항)]` 추가
- `model: opus` (기존과 동일)
- `allowed-tools: Read, Glob, Grep, Task, Write, AskUserQuestion`
- Agent Teams 환경변수 체크 로직 명시

**references/ 파일 4개 마이그레이션**:

- `deliberation-pattern.md` — 3-Round 패턴 상세
- `perspectives-guide.md` — 10개 관점 가이드
- `conflict-resolution.md` — 충돌 해결 전략
- `examples.md` — 실제 리뷰 예시

**보존 기능**: 전체 3-Round Deliberation 플로우, Agent Teams CALC-001 자동 전환, 폴백 전략, 토큰 한도 POL-002

#### B-3: doc-coauthoring

**소스**: `claude_setting/skills/common/doc-coauthoring/SKILL.md`
**목적지**: `plugins/common/skills/doc-coauthoring/skill.md`

**업그레이드 사항**:

- `effort: medium` 추가
- `argument-hint: [작업설명] [파일경로]` 추가
- `allowed-tools: Read, Write, Edit, Glob, Grep`
- `model: opus` (기존과 동일)
- `disable-model-invocation: true` 추가

**보존 기능**: 문서 유형별 워크플로우 (API/아키텍처/사용자가이드/README), 품질 체크, 자동 업데이트 트리거, ADR 템플릿

#### B-4: debug

**소스**: `claude_setting/skills/common/debug/SKILL.md`
**목적지**: `plugins/common/skills/debug/skill.md`

**업그레이드 사항**:

- `effort: high` 추가 (diagnose(opus) + fix-bugs(sonnet) + verify-code(haiku))
- `argument-hint: [에러메시지 또는 설명]` (기존 있음, 확인)
- `allowed-tools: Read, Edit, Bash, Glob, Grep, Task, WebSearch`
- `model: sonnet` (오케스트레이션은 sonnet으로)
- `disable-model-invocation: true` 추가

**보존 기능**: 4-Phase 파이프라인 (Reproduce → Isolate → Fix → Verify), diagnose/fix-bugs/verify-code 에이전트 연계

#### B-5: test

**소스**: `claude_setting/skills/common/test/SKILL.md`
**목적지**: `plugins/common/skills/test/skill.md`

**업그레이드 사항**:

- `effort: medium` 추가
- `argument-hint: [테스트경로 | 빈칸(전체)]` (기존 있음, 확인)
- `allowed-tools: Read, Bash, Glob, Grep, Task`
- `model: sonnet`
- `disable-model-invocation: true` 추가

**보존 기능**: 프로젝트 타입 자동 감지 (pytest/npm/go/cargo), verify-code → fix-bugs 루프

---

### Phase C: P1 스킬 마이그레이션 (4개)

#### C-1: agent-creator

**소스**: `claude_setting/skills/common/agent-creator/SKILL.md`
**목적지**: `plugins/common/skills/agent-creator/skill.md`

**업그레이드 사항**:

- `effort: medium` 추가
- `argument-hint: [에이전트 설명]` 추가
- `allowed-tools: Write, Read, Glob`
- `model: sonnet`
- 파일 생성 위치 `plugins/{domain}/agents/` 기준으로 업데이트 (기존 `.claude/agents/` → plugin 구조)

#### C-2: skill-creator

**소스**: `claude_setting/skills/common/skill-creator/SKILL.md`
**목적지**: `plugins/common/skills/skill-creator/skill.md`

**업그레이드 사항**:

- `effort: medium` 추가
- `argument-hint: [스킬설명] [스킬이름]` 추가
- `allowed-tools: Write, Read, Glob`
- `model: sonnet`
- 파일 생성 위치 `plugins/{domain}/skills/` 기준으로 업데이트

#### C-3: mcp-builder

**소스**: `claude_setting/skills/common/mcp-builder/SKILL.md`
**목적지**: `plugins/common/skills/mcp-builder/skill.md`

**업그레이드 사항**:

- `effort: medium` 추가
- `argument-hint: [서버설명] [서버이름]` 추가
- `allowed-tools: Write, Read, Bash, Glob`
- `model: sonnet`

#### C-4: agent-teams

**소스**: `claude_setting/skills/common/agent-teams/SKILL.md`
**목적지**: `plugins/common/skills/agent-teams/skill.md`

**업그레이드 사항**:

- `effort: high` 추가
- `argument-hint: [작업설명]` 추가
- `allowed-tools: Read, Glob, Task`
- `model: opus` (Opus 4.6 필수)
- 실험적 기능 경고 헤더 명시

---

### Phase D: 아키텍처 정비 (phase-gates 대체)

#### D-1: phase-gate-pattern.md 추가

**소스**: `claude_setting/docs/architecture/phase-gate-pattern.md`
**목적지**: `docs/architecture/phase-gate-pattern.md`

내용 그대로 이식. claude-code-kit 맥락에 맞게 경로 참조 업데이트.

#### D-2: agent-system.md 규칙 보강

`plugins/common/rules/agent-system.md`의 "Phase Gate 패턴" 섹션을 확장:

```markdown
## Phase Gate 패턴

Phase Gate = 메인 Claude의 판단 기준 (자동 시스템 아님)
상세 문서: docs/architecture/phase-gate-pattern.md

### Exit Gate 판단 기준

**Planning → Dev:**

- P0 모호함 = 0
- 핵심 비즈니스 규칙 정의됨
- 데이터 모델 정의됨

**Dev → Validation:**

- 빌드 성공 (verify-code 통과)
- 핵심 로직 테스트 존재
- 린트/타입 통과

**Validation → Complete:**

- review-code Must Fix = 0
- Critical 보안 이슈 = 0
- 통합 테스트 통과
```

#### D-3: Stop hook 추가 (hooks.json)

최신 Claude Code `Stop` hook(prompt type)을 활용한 자동 품질 검증:

```json
"Stop": [
  {
    "hooks": [
      {
        "type": "prompt",
        "prompt": "개발 작업이 완료된 경우: 1) 빌드/테스트가 통과했는가? 2) 리뷰가 완료되었는가? 3) 미완성 작업이 있는가? 미완성이라면 {\"ok\": false, \"reason\": \"남은 작업 설명\"}으로 응답하고, 완료되었다면 {\"ok\": true}로 응답하세요. 개발 작업이 아닌 경우 {\"ok\": true}로 응답하세요.",
        "timeout": 30
      }
    ]
  }
]
```

이렇게 하면 phase-gates 로직이 Claude가 멈추려 할 때 자동으로 품질을 검증하므로 명시적 스킬 호출 없이 Phase Gate 동작.

---

### Phase E: 문서 업데이트

**README.md 업데이트**:

- common skills 카운트: 3 → 13
- 총 skills 카운트: 13 → 23
- 총 합계 헤더: "66 agents + 13 skills" → "66 agents + 23 skills"
- Key Skills 테이블 신규 스킬 추가
- Common Domain Key Skills 섹션 업데이트

**CLAUDE.md 업데이트**:

- Structure 섹션 common skills 카운트 업데이트
- Key Skills 테이블 업데이트

---

## 파일 목록 (전체)

### 신규 생성 (20개)

```
plugins/common/skills/web-research/skill.md           (이동)
plugins/common/skills/review/skill.md
plugins/common/skills/multi-perspective-review/skill.md
plugins/common/skills/multi-perspective-review/references/deliberation-pattern.md
plugins/common/skills/multi-perspective-review/references/perspectives-guide.md
plugins/common/skills/multi-perspective-review/references/conflict-resolution.md
plugins/common/skills/multi-perspective-review/references/examples.md
plugins/common/skills/doc-coauthoring/skill.md
plugins/common/skills/debug/skill.md
plugins/common/skills/test/skill.md
plugins/common/skills/agent-creator/skill.md
plugins/common/skills/skill-creator/skill.md
plugins/common/skills/mcp-builder/skill.md
plugins/common/skills/agent-teams/skill.md
docs/architecture/phase-gate-pattern.md
```

### 수정 (5개)

```
plugins/common/rules/agent-system.md         (Phase Gate 섹션 보강)
plugins/common/hooks/hooks.json              (Stop hook 추가)
plugins/common/setup/session-check.py        (Stop hook 관련 체크 추가 여부 검토)
README.md                                    (카운트 업데이트)
CLAUDE.md                                    (카운트 업데이트)
```

### 삭제 (1개)

```
plugins/common/skills/SKILL.md               (→ web-research/skill.md로 이동)
```

---

## 업그레이드 요약 (최신 Claude Code 기능 반영)

| 기능                             | 적용 대상                            | 효과                                     |
| -------------------------------- | ------------------------------------ | ---------------------------------------- |
| `effort` 필드                    | 전 스킬                              | 사용자에게 예상 비용/시간 힌트           |
| `argument-hint` 필드             | 전 스킬                              | `/skill-name` 입력 시 파라미터 힌트 표시 |
| `disable-model-invocation: true` | review, doc-coauthoring, debug, test | 명시적 호출만 허용, 자동 트리거 방지     |
| Stop hook (prompt type)          | hooks.json                           | phase-gates 자동화, 명시적 호출 불필요   |
| `skill.md` 소문자 통일           | 전 스킬                              | 컨벤션 일관성                            |
| Agent Teams 명시                 | agent-teams                          | 실험적 기능 명확화                       |

---

## 체크포인트

| #   | 항목                                               | 완료 |
| --- | -------------------------------------------------- | ---- |
| A   | web-research 구조 이동                             | [x]  |
| B-1 | review 마이그레이션 + 업그레이드                   | [x]  |
| B-2 | multi-perspective-review + references 마이그레이션 | [x]  |
| B-3 | doc-coauthoring 마이그레이션                       | [x]  |
| B-4 | debug 마이그레이션                                 | [x]  |
| B-5 | test 마이그레이션                                  | [x]  |
| C-1 | agent-creator 마이그레이션                         | [x]  |
| C-2 | skill-creator 마이그레이션                         | [x]  |
| C-3 | mcp-builder 마이그레이션                           | [x]  |
| C-4 | agent-teams 마이그레이션                           | [x]  |
| D-1 | phase-gate-pattern.md 추가                         | [x]  |
| D-2 | agent-system.md 보강                               | [x]  |
| D-3 | Stop hook 추가                                     | [x]  |
| E   | README.md, CLAUDE.md 업데이트                      | [x]  |
| F   | commit & push                                      | [ ]  |
