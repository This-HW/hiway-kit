# Decisions: Task-Work 통합 고도화

> Work ID: W-003
> Last Updated: 2026-04-05T00:00:00Z

---

## 의사결정 기록

### DEC-001: 구현 접근법

- **날짜**: 2026-04-05
- **질문**: 스킬 강화만 / SessionStart hook 추가 / 새 오케스트레이터 스킬
- **결정**: Option 2 — 스킬 강화 + SessionStart hook
- **근거**: A+B+C 전부 달성 가능, Option 3 대비 구현 비용 적정, 추후 Option 3으로 확장 가능
- **영향**: plan-task, auto-dev 스킬 수정 + session-start.py hook 신규 작성

### DEC-002: Task 재생성 데이터 소스

- **날짜**: 2026-04-05
- **질문**: Work 파일만 / 소스코드도 함께 참조
- **결정**: Work 파일 우선, 최초 생성 시 소스코드 탐색 병행
- **근거**: Resume 속도 최적화 + 최초 생성 정확도 확보
- **영향**: progress.md에 Task 단위 추적 구조 추가 필요

### DEC-003: progress.md 구조 변경

- **날짜**: 2026-04-05
- **질문**: Phase 체크리스트 유지 / Task 단위 맵으로 전환
- **결정**: Task 맵으로 전환 (blockedBy 포함)
- **근거**: Phase 단위로는 Task 재생성 불가, Task ID + 상태 + 의존성이 필요
- **영향**: work-system.md, plan-task, auto-dev 스킬의 progress.md 포맷 업데이트
