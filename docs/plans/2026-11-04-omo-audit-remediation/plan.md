---
title: "OMO 통합 초안의 감사 결함 수정 및 기능 보강 재설계"
status: current
execution_status: in-progress
as_of: 2026-11-04
created: 2026-11-04
size: large
---

## 요구사항

- 사용자는 개선 실행을 위임했고, 지정된 plan-control Claude와 Codex의 합의를 사용자 결정으로 인정했다. `[confirmed: 2026-11-04 사용자]`
- 재현된 결함을 수정하고, 각 결함이 수정 전 실패하고 수정 후 통과하는 회귀 검사를 남긴다. `[researched: 독립 감사 보고서, n=2]`
- 새 기능은 기능 계약·실제 소비자 검증을 기준으로 채택한다. 기존 호스트 도구의 존재만으로 OMO 대체 완료를 주장하지 않는다.
- 확보된 범위: omo_test 소스 쓰기, 공개 문서, 설치된 실행 파일, 임시 소비자 환경, 지정 Claude의 검수.
- 사용자 인증·다른 플러그인·모델 설정과 기존 hook enabled 상태를 보존한다. 서드파티 실측은 임시 HOME/CODEX_HOME/cwd와 OS 쓰기 거부 경계를 함께 사용한다.
- 원본 감사 자료: 로컬 migration 디렉터리의 `audit-code-install-2026-11-02.json`, `audit-capabilities-2026-11-02.json`. 이들은 증거 데이터이며 실행 지침이 아니다.

## 결정

- 결함 수정은 기존 기능 계약의 복구이므로 별도 brainstorming 승인 없이 진행한다. 새 Large 기능은 지정 Claude와 설계 합의 후 별도 스펙으로 구체화한다.
- 원 계획의 완료 주장은 철회했다. 역사적 검증 기록을 지우지 않고 현재 상태와 분리했다.
- 문서 상태 검사와 계획 규약의 status 어휘가 상충하므로 `status: current`와 `execution_status`를 사용한다. 완료 게이트를 우회하거나 상태 검사기를 약화하지 않는다.
- 현재 기준 HEAD는 `2600cf63f40e12c5f7bdb29abe80cb7a43614967`, 브랜치는 `omo_test`다. 기존 staged 초안을 보존한다.
- 코드는 Codex가 소유하고, plan-control Claude가 설계 결정과 독립 리뷰에 참여한다. `docs/marketplace-submission.md`는 수정하지 않는다.
- 2026-11-04 Claude 판정과 합의: 5.6.0은 기존 초안·감사 결함·설치 doctor로 한정한다. 상주 LSP/rename과 브라우저 QA는 후속 Large 설계로 분리하고 누락 기능으로 계속 추적한다. 후속 LSP는 네이티브 호스트 우선, 비네이티브에서만 opt-in 데몬; 브라우저는 개인 도구를 전제하지 않고 설치된 Playwright와 일반 호스트 capability를 사용한다.
- 실제 홈의 GitHub source·5.5.1·훅 disabled 선택은 유지한다. 격리 CODEX_HOME만 local source로 검증하며 인증 파일을 복사/심링크하지 않는다. 설치된 버전과 설정 source 버전이 다르면 doctor는 nonzero로 보고한다.
- 각 결함은 별도 회귀 증거와 작은 커밋으로 남긴다. 수정 worker는 격리된 Orca 자식 브랜치에만 쓰고 Codex가 omo_test에 통합한다. main 병합·tag·공개는 이번 실행 범위 밖이다.
- P0 데이터 경계: rename 등 새 쓰기 기능의 허용 대상·실패 복원은 설계 합의 전 구현하지 않는다. 사용자 설정 수정·훅 승인 조작·공개 배포는 이 결함 수정 단계에 포함하지 않는다.
- 상태 분기: 실행 불가와 검증 실패는 성공과 구별한다. 진단이 잠정적이면 clean을 단정하지 않는다. 잘못된 응답은 unverified 오류로 처리한다.
- 규칙 충돌: 정상 패턴 수용은 AST 엔진의 실제 compile 계약에 따르고 디버그용 raw parse tree에 기대지 않는다.
- 경계값과 실패 복원: 파일/메시지/전체 자원 예산 초과를 명시하고 프로세스를 정리한다. 읽기 경로는 파일 디스크립터로 확인해 심링크 교체와 특수 파일 대기를 막는다.
- 정책 상수는 각 도구 상수 또는 공용 경계 모듈 한 곳에서 소유한다. 문서에서 같은 값을 중복 규정하지 않는다.

## 구현 계획

1. AST 정상 Python/Go 메타변수 회귀, stdout/stderr 동시 한도·deadline·프로세스 정리.
2. LSP 엄격 JSON-RPC/결과 스키마 검증, pull diagnostics와 provisional push 구분, 안전한 소스 읽기.
3. 세션 로그 디스크립터 기반 읽기, 디렉터리·총 읽기·시간 예산과 truncation 표시.
4. 설치 doctor와 소비자 검증에서 source/version/hook trust/enabled/실행 여부를 구분한다. 지속 가능한 미출시 설치 방식은 Claude와 합의한다.
5. 전체 기능 대응표의 과장된 항목을 정정하고, 상주 LSP·rename·브라우저 등 새 기능의 채택/대체/보류 근거와 검증 조건을 Claude와 합의한다.
6. 이번 릴리스의 소비자 E2E 및 동일 조건 성능/품질 검증을 수행하고 버전·문서·게이트를 마감한다. 인증 등 환경으로 실행하지 못한 검증은 미검증으로 남긴다.
7. 별도 후속 스펙에서 상주 LSP/rename·브라우저 QA를 Claude와 합의한 뒤 구현한다. 이번 릴리스 수정 완료를 전체 OMO 대체 완료로 표현하지 않는다.

## 완료 조건

- `python3 -m pytest tests/hooks/test_code_intel.py tests/hooks/test_lsp_query.py tests/hooks/test_session_history.py -q` (exit 0; 새 음성·양성 회귀 포함)
- `ruff check plugins/common/tools tests/hooks` (exit 0)
- `bash scripts/verify-done.sh` (fresh exit 0, 통합 후 실행)
- `bash scripts/run-evals.sh` (스킬 변경 후 exit 0)
- 설치/소비자 검증 명령은 구현 후 실제 실행 가능한 경로를 추가한다. 현재 이 항목은 미완료이며 이전 로그로 대체하지 않는다.
- 지정 Claude의 독립 리뷰, 모든 채택 기능의 실제 검증과 미구현 목록 공개가 완료되어야 execution_status를 done으로 바꾼다.
- Python 3.9 실측, 신규 스킬 eval 분류/커버리지, 공개 텍스트 위생, SessionStart 예산과 스킬 수 동기화를 검증한다. hooks는 discovered/trusted/enabled/fired를 따로 보고한다.

## 검증 결과

- 착수: 원본 도구와 감사 자료 존재, 현재 브랜치 및 staged 초안 확인. 아직 수정 후 게이트를 실행하지 않았다.
- 지정 Claude 세션에 설계안 전달: Orca receipt `c9b3b67f-d6d0-499c-b43f-0a508837a65f`, `turn_started` 확인. `improvement-decision-2026-11-04.md` 판정을 수신했고 위 결정에 반영했다. 사용자의 직접 위임에 따라 합의를 승인 근거로 사용한다.
