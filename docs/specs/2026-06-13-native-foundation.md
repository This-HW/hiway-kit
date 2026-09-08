# Native Foundation 설계 (Spec 1)

**Goal:** Claude Code 네이티브 프리미티브를 최대 활용하고 중복되는 자체 재구현을 제거하여, 기술부채 없이 더 높은 성능의 토대를 만든다.

**Architecture:** claude-code-kit의 가치는 "의견이 담긴 에이전트/스킬/규율 레이어"이지 인프라가 아니다. 인프라(관측·위임·훅 실행)는 네이티브에 위임하고, 손으로 만든 대체물은 삭제한다. Spec 1은 이 원칙을 토대 계층(매니페스트·훅)에 적용하는 첫 단계로, 전부 하위호환이며 이후 Spec 2(오케스트레이션)·Spec 3(피드백 메모리)의 깨끗한 바닥을 만든다.

**Version:** 2.2.0 → 2.3.0 (minor bump, 엄격한 하위호환)

---

## 요구사항

1. 도메인 플러그인의 common 의존성을 네이티브가 강제하도록 매니페스트에 선언한다.
2. 훅 실행을 네이티브 정식 형식(exec form)으로 전환해 경로 인용/공백 잠재 버그를 제거한다.
3. `stop-validator`의 비공식 exit-2 차단을 네이티브 구조화 출력(`continueOnBlock`)으로 교체해, 검증 실패 시 Claude가 자동 수정 턴을 이어가게 한다.
4. 순수 로깅만 하는 `agent-lifecycle.py`를 삭제하고 관측을 네이티브 OTEL에 위임한다.
5. 위 모든 변경은 기존 Work 시스템·스킬 동작을 바꾸지 않으며, 미지원 구버전 CC에서 graceful degradation 한다.

## 접근 방식

**Approach A — Verify-then-convert (채택).**
각 항목을 구현 직전 현재 CC 스키마(context7 / plugin docs)로 검증한 뒤 전환한다. 매니페스트에 agents/skills를 수동 열거하지 않는다(열거 desync = 부채). 네이티브가 실제로 제공하는 기능(의존성 강제)만 선언한다.

기각된 대안:
- Approach B (검증 없이 전체 열거): 새 에이전트마다 목록 갱신 필요 → desync 부채, 버전 위험.
- Approach C (continueOnBlock + 삭제만): 매니페스트/exec form 부채 잔존.

## 컴포넌트 구조

### 변경 1 — 매니페스트 의존성 선언
- 대상: `plugins/{frontend,infra,ops,data,integration}/.claude-plugin/plugin.json`
- 추가: `dependencies: ["claude-code-kit"]` (정확한 키/값 포맷은 구현 직전 현재 CC docs로 검증)
- agents/skills/hooks 열거하지 않음 — 자동 디스커버리 유지
- `defaultEnabled`는 현행 유지(검토 후 변경 불필요로 판단되면 무변경)

### 변경 2 — 훅 exec form 전환
- 대상: `plugins/common/hooks/hooks.json` 전체 훅 엔트리
- 변경: `"command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/x.py\""` → `"args": ["python3", "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"]`
- 인자 전달 훅(`agent-lifecycle.py start` 등)은 변경 4로 제거되므로 잔존 훅만 대상
- `async`/`timeout`/`matcher` 등 다른 필드는 보존

### 변경 3 — stop-validator continueOnBlock
- 대상: `plugins/common/hooks/stop-validator.py`의 `block()` 함수
- 변경: `sys.exit(2)` + stdout JSON → 네이티브 `hookSpecificOutput`(`decision: "block"`, `reason`, `continueOnBlock: true`)
- `MAX_RETRIES=2` 무한루프 가드, lint 자동수정 로직, VALIDATED_MARKER 스킵 로직 전부 유지
- 정확한 Stop 훅 출력 스키마는 구현 직전 검증 — 미지원 시 exit-2 fallback 분기 유지

### 변경 4 — agent-lifecycle.py 삭제
- 삭제: `plugins/common/hooks/agent-lifecycle.py`
- `hooks.json`에서 SubagentStart / SubagentStop / PreCompact 3개 등록 제거
- `plugins/common/hooks/tests/`에 agent-lifecycle 의존 테스트가 있으면 함께 제거
- 관측은 네이티브 OTEL(`agent_id`/`parent_agent_id` 스팬, `/usage` 분해)로 대체 — README/CLAUDE.md 훅 섹션 갱신

### 버전 bump
- `plugins/common/.claude-plugin/plugin.json` → 2.3.0
- 변경된 도메인 plugin.json도 버전 동기 bump (변경 1 대상 5종)

## 데이터 흐름

```
SessionStart  → session-check.py + session-start.py (exec form, 무변경 동작)
PreToolUse    → protect-sensitive.py (exec form)
PostToolUse   → auto-format.py (exec form)
Stop          → stop-validator.py (exec form)
                  ├─ 통과 → allow (exit 0)
                  ├─ lint 실패 → auto-fix → 통과 시 allow / 잔존 시 block(continueOnBlock)
                  └─ test 실패 → block(continueOnBlock) → Claude 자동 수정 턴 → MAX_RETRIES 가드
(삭제됨) SubagentStart/Stop/PreCompact → 네이티브 OTEL이 대체
```

## 에러 처리

- 모든 훅 fail-open 유지: 훅 오류가 세션을 차단하지 않는다.
- continueOnBlock/exec form 미지원 구버전 CC: 기존 동작(exit-2 / command form 동등 동작)으로 자연 degradation.
- 의존성 선언 포맷 오류 위험: 구현 직전 현재 CC docs로 검증하고, CI `validate.yml`의 JSON 유효성 검사로 1차 차단.

## 테스트 전략

- `plugins/common/hooks/tests/` pytest 갱신:
  - stop-validator 출력 스키마 변경(continueOnBlock) 반영
  - agent-lifecycle 테스트 제거
- 매니페스트 5종 JSON 유효성 — CI `validate.yml`이 검사
- 수동 검증:
  1. 도메인 플러그인 활성화 시 common 자동 강제 활성화 확인
  2. test 실패 → continueOnBlock 자동 수정 1 사이클 → MAX_RETRIES 가드 동작 확인
  3. exec form 훅 정상 실행 확인

## 범위 외

- 통제된 2-tier 오케스트레이션, delegation-signal → 네이티브 구조화 위임, agent-teams → native dynamic workflow 래퍼 → **Spec 2**
- Hermes식 validation/review 피드백 메모리 학습 루프 → **Spec 3**
- superpowers 스킬 리포 분리, OpenClaw cron 자율성 → 채택하지 않음(설치 복잡도/스코프 부채)
