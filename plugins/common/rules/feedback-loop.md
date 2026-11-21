---
tier: conditional
activates: 과거 결함 digest를 얻을 수 있을 때 (주입되었거나 직접 조회 가능)
portable: true
portable_reason: 저장은 파일, 읽기는 CLI — 훅이 없는 하네스도 직접 조회하면 성립한다
---

> **디렉토리판 — 훅·도구 없음.** 이 설치에는 킷의 `hooks/`·`setup/`·`tools/` 와 `code-intel`·`session-history`·`harness-export` 스킬이 없다. 아래에서 그 파일을 실행하거나 켜라는 단계, 그 스킬을 쓰라는 단계는 **건너뛰고**(없음으로 처리), 다른 설치나 플러그인 캐시에서 같은 이름의 파일을 찾아 쓰지 않는다 — 버전이 다른 도구다. 그 기능이 필요하면 전체판(이 레포를 마켓플레이스로 설치)을 안내한다.

# Feedback Loop Rule

validation·review에서 반복 발견된 결함을 학습해 같은 실수를 반복하지 않는다.

- **digest 확보**: 훅이 있으면 `=== LESSONS ===`로 자동 주입된다. 없으면 직접 조회한다 —
  `python3 <킷 루트>/tools/feedback_ledger.py digest`(API 성 호출이면 호출자가 조회해 싣는다).
  경로를 못 찾으면 무동작이다(fail-open).
- **적용**: 구현·리뷰 전에 그 패턴을 우선 점검한다.
- **누적**: 검증에서 **실제로 발견된** 결함만 `feedback_ledger.py upsert`로 넣는다(통과
  패턴·추측은 노이즈). 상한·중복제거·감쇠는 헬퍼가 보장한다 — 테이블을 직접 편집하지 않는다.
