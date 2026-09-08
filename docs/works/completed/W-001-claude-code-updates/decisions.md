# Decisions: Claude Code v2.1.74~v2.1.86 업데이트 적용

> Work ID: W-001
> Last Updated: 2026-04-02T13:42:59+09:00

## 의사결정 기록

### DEC-001: Conditional Hooks `if` 필드 항목 삭제
- **결정**: 제거
- **근거**: Claude Code 공식 문서(v2.1.89)에서 `if` 필드 미지원 확인. 최신 hooks.json은 `matcher`(tool 이름 regex)만 지원. 파일 확장자 필터링은 Python 스크립트 내부에서 이미 처리 중.
- **일자**: 2026-04-02

### DEC-002: `--bare` CI 항목 → pre-commit 강화로 대체
- **결정**: Claude 실행 CI 추가 대신 pre-commit에 JSON 검증 + frontmatter 체크 추가
- **근거**: 사용자 방침 — CI는 최소화, 무거운 검증은 commit/push 전 로컬 hook에서 처리
- **일자**: 2026-04-02

### DEC-003: Skills effort 적용 범위
- **결정**: 전체 skills 대신 핵심 5개(review, multi-perspective-review, plan-task, auto-dev, web-research)에만 적용
- **근거**: 메모리 원본 연구에서 명시된 대상 범위. 나머지는 기능 영향 없음
- **일자**: 2026-04-02
