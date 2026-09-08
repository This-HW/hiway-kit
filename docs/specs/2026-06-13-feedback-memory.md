# Feedback Memory Loop 설계 (Spec 3)

**Goal:** validation/review에서 반복적으로 잡히는 결함 패턴을 구조화해 축적하고, 이후 구현 컨텍스트에 자동 주입하여, 같은 실수를 반복하지 않는 학습 루프를 만든다. (Hermes 통찰: 피드백 루프는 부가기능이 아니라 코어)

**Architecture:** 새 저장소나 데몬을 만들지 않는다. **기존 인프라를 재사용**한다 — (1) 캡처는 auto-dev validation 단계(이미 review/security 결과를 가짐), (2) 저장은 Work 시스템 파일(프로젝트 로컬, 플러그인 제어), (3) 주입은 session-start.py(이미 context를 주입함), (4) 적용은 implement-code/rules. 핵심 안티-부채 장치는 **엄격한 상한·중복제거·감쇠**로 ledger가 컨텍스트를 비대화시키지 않게 하는 것이다.

**Version:** 2.4.0 → 2.5.0 (minor bump, 엄격한 하위호환) — Spec 2(2.4.0) 이후

**Depends on:** Spec 1(관측 토대), Spec 2(오케스트레이션) 완료 전제. 단 기능적 결합은 약함 — 독립 동작 가능.

---

## 요구사항

1. auto-dev validation 결과(review-code/security-scan)에서 반복·주목 결함을 구조화 추출한다.
2. 추출 결과를 프로젝트 로컬 feedback ledger에 중복제거하여 누적한다.
3. session-start가 ledger의 고빈도 교훈 digest를 컨텍스트로 주입한다.
4. ledger는 **상한·중복제거·감쇠**로 무한 성장하지 않는다(컨텍스트 비대화 방지).
5. feedback 시스템 부재/비활성도 기존 파이프라인에 영향 없음(fail-open, opt-in).

## 접근 방식

**기존 인프라 재사용 + 엄격한 상한.**
- 캡처: auto-dev T-merge 단계에 추출 로직 추가(별도 에이전트/훅 없음).
- 저장: `docs/works/feedback/ledger.md`(프로젝트 로컬, Work 시스템 일부).
- 주입: session-start.py에 digest 로더 추가(별도 훅 없음).
- 적용: rules + implement-code 참조.

기각된 대안:
- 어시스턴트 글로벌 메모리(`~/.claude/.../memory/`) 직접 기록: 플러그인 제어 밖 + 사용자 메모리 오염 = 부채.
- 별도 feedback store/데몬: 새 인프라 = 부채. 재사용으로 충분.

## 컴포넌트 구조

### 변경 1 — Feedback ledger 포맷
- 신규: `docs/works/feedback/ledger.md`
- 엔트리 구조(구조화·파싱 가능):
  ```
  | id | category | pattern | frequency | last_seen | severity |
  ```
  - category: lint / security / architecture / test / convention
  - pattern: 정규화된 결함 요지(중복제거 키)
  - frequency: 누적 발생 횟수
- **상한**: 최대 N개 엔트리(예: 50). 초과 시 frequency·last_seen 기준 하위 감쇠 제거.

### 변경 2 — auto-dev 캡처 로직
- 대상: `plugins/common/skills/auto-dev/SKILL.md` Step 3 T-merge
- T-merge에서 review-code/security-scan 결과 파싱 → 결함 요지 정규화 → ledger upsert(있으면 frequency++, last_seen 갱신; 없으면 추가)
- 통과(이슈 0) 시에도 "회피된 패턴" 기록은 하지 않음(노이즈 방지) — 실제 발견 결함만

### 변경 3 — session-start digest 주입
- 대상: `plugins/common/hooks/session-start.py`
- ledger 존재 시 → 고빈도 상위 K개(예: frequency 상위 5) 교훈을 `=== LESSONS ===` 섹션으로 주입
- ledger 없으면 무동작(fail-open)
- digest 크기 상한(토큰 예산 보호) — 라인 수/문자 수 cap

### 변경 4 — 적용 지점 명문화
- 대상: `plugins/common/rules/code-quality.md` 또는 신규 `rules/feedback-loop.md`
- implement-code/review-code가 `=== LESSONS ===` 컨텍스트를 구현/리뷰 시 우선 점검하도록 규칙화

### 버전 bump
- `plugins/common/.claude-plugin/plugin.json` → 2.5.0

## 데이터 흐름

```
[캡처]  auto-dev T-merge
          review-code/security-scan 결과 → 정규화 → ledger.md upsert (dedupe, freq++)
                                                        │
[감쇠]  상한 초과 시 freq·last_seen 하위 제거 ──────────┤
                                                        ▼
[주입]  session-start.py → ledger 상위 K → "=== LESSONS ===" context 주입
                                                        │
[적용]  implement-code / review-code → LESSONS 우선 점검 → 같은 결함 사전 차단
                                                        │
            (새 결함 발견 시) ──────────────────────────┘  루프 반복
```

## 에러 처리

- ledger 파싱 실패 → 무시(fail-open), 빈 digest. 세션·파이프라인 무중단.
- ledger 쓰기 실패(권한 등) → T-merge 본 작업에 영향 없음(피드백은 best-effort).
- digest가 토큰 예산 초과 위험 → 라인/문자 cap으로 강제 절단.
- feedback 디렉토리 부재(opt-in 미사용) → 전 구간 무동작.

## 테스트 전략

- ledger upsert 단위 테스트: 신규 추가 / 중복 freq 증가 / 상한 초과 감쇠 제거.
- session-start digest 로더 테스트: ledger 유/무, cap 동작, 파싱 실패 fail-open.
- auto-dev T-merge 캡처: review/security 결과 → ledger 반영 회귀.
- 수동 검증: 의도적 결함 → validation 캡처 → 다음 세션 LESSONS 주입 → 1 루프 확인.

## 범위 외

- 어시스턴트 글로벌 메모리 연동
- 크로스-프로젝트 ledger 공유
- ML 기반 패턴 클러스터링(단순 정규화 dedupe로 충분, 과설계 회피)

## 알려진 가변 지점

ledger 정규화 키(pattern dedupe 기준)의 입도는 구현 중 튜닝 대상 — 너무 세밀하면 중복 폭증, 너무 거칠면 정보 손실. 초기엔 category+요지 해시로 시작하고 수동 검증에서 조정.
