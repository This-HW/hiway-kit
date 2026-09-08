# Progress: Rules Injection 최적화

> Work ID: W-004
> Last Updated: 2026-04-09T12:00:00Z

---

## Task Map

### Phase 1: Rule 파일 재작성 (LLM instruction 형식)

| Task ID | 제목                             | 설명                                                         | 상태 | blockedBy |
| ------- | -------------------------------- | ------------------------------------------------------------ | ---- | --------- |
| T-1     | agent-system.md 재작성           | 에이전트 선택·위임·3-tier·disallowedTools → instruction 형식 | ✅   | -         |
| T-2     | agent-delegation-chain.md 재작성 | 위임 신호 감지·자동 체인 → instruction 형식                  | ✅   | -         |
| T-3     | planning-protocol.md 재작성      | P0~P3 분류·협업 규칙 → instruction 형식                      | ✅   | -         |
| T-4     | planning-check.md 재작성         | 추측 금지·기획 확인 워크플로우 → instruction 형식            | ✅   | -         |
| T-5     | code-quality.md 재작성           | 코드 품질 기준 → instruction 형식                            | ✅   | -         |
| T-6     | ssot.md 재작성                   | SSOT 원칙 → instruction 형식                                 | ✅   | -         |
| T-7     | mcp-usage.md 재작성              | MCP 선택 가이드 → instruction 형식                           | ✅   | -         |
| T-8     | task-resume.md 재작성            | Task 재생성 알고리즘 → instruction 형식                      | ✅   | -         |
| T-9     | tool-usage-priority.md 재작성    | 전용 도구 우선 → instruction 형식 (이미 작음)                | ✅   | -         |

### Phase 2: Human 문서 작성

| Task ID | 제목                                                     | 설명                                         | 상태 | blockedBy |
| ------- | -------------------------------------------------------- | -------------------------------------------- | ---- | --------- |
| T-10    | docs/architecture/rules/ 디렉토리 + agent-system 문서    | 에이전트 시스템 human doc (표·예시 풍부)     | ✅   | -         |
| T-11    | planning 관련 human 문서 2개                             | planning-protocol, planning-check human docs | ✅   | -         |
| T-12    | agent-delegation-chain + code-quality + ssot human 문서  | 3개 human docs                               | ✅   | -         |
| T-13    | mcp-usage + task-resume + tool-usage-priority human 문서 | 3개 human docs                               | ✅   | -         |

### Phase 3: session-start.py 확장

| Task ID | 제목                                  | 설명                                                   | 상태 | blockedBy                           |
| ------- | ------------------------------------- | ------------------------------------------------------ | ---- | ----------------------------------- |
| T-14    | session-start.py rules 주입 로직 추가 | 규칙 파일 읽기 + 조건부 주입 + Active Work와 합산 출력 | ✅   | T-1,T-2,T-3,T-4,T-5,T-6,T-7,T-8,T-9 |
| T-15    | 통합 검증                             | /context에서 Rules 로드 확인, 토큰 카운트 측정         | ✅   | T-14                                |

## Task 업데이트 로그

- 2026-04-09T00:00:00Z: W-004 생성, planning 완료
- 2026-04-09T12:00:00Z: W-004 통합 검증 완료 (T-15)
  - Phase 1 (T-1~T-9): 전체 9개 rule 파일 재작성 완료
    - 총 chars: 14,213 / 추정 tokens: ~3,553 (목표 3,000 초과이나 검증 통과)
  - Phase 2 (T-10~T-13): docs/architecture/rules/ 인간 문서 9개 작성 완료
  - Phase 3 (T-14): session-start.py rules 주입 로직 구현 완료
    - 실행 검증: 오류 없음, JSON 유효, `=== RULES ===` 블록 포함 확인
  - installed cache 업데이트 완료:
    - rules/\*.md (9개) → /home/hw/.claude/plugins/cache/claude-code-kit/claude-code-kit/1.0.0/rules/
    - session-start.py → /home/hw/.claude/plugins/cache/claude-code-kit/claude-code-kit/1.0.0/hooks/
