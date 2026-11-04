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
- 착수 시 HEAD는 `2600cf63f40e12c5f7bdb29abe80cb7a43614967`, 브랜치는 `omo_test`였다. 기존 staged 초안을 보존한 뒤 아래 통합 기록대로 진행했다.
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
- 설치/소비자 검증: 레포 밖 로컬 migration 증거 디렉터리의 consumer-remediation-probe.py에 이 체크아웃의 절대 경로를 인자로 전달한다. 격리 설치·재설치·실제 CLI·스킬 탐지는 확인했으며, 자연어 E2E는 인증 부재로 미검증이다. 이전 로그로 대체하지 않는다.
- 지정 Claude의 독립 리뷰, 모든 채택 기능의 실제 검증과 미구현 목록 공개가 완료되어야 execution_status를 done으로 바꾼다.
- Python 3.9 실측, 신규 스킬 eval 분류/커버리지, 공개 텍스트 위생, SessionStart 예산과 스킬 수 동기화를 검증한다. hooks는 discovered/trusted/enabled/fired를 따로 보고한다.

## 검증 결과

- 착수 당시: 원본 도구와 감사 자료 존재, 현재 브랜치 및 staged 초안을 확인했다. 그 시점에는 수정 후 게이트를 실행하지 않았다.
- 지정 Claude 세션에 설계안 전달: Orca receipt `c9b3b67f-d6d0-499c-b43f-0a508837a65f`, `turn_started` 확인. `improvement-decision-2026-11-04.md` 판정을 수신했고 위 결정에 반영했다. 사용자의 직접 위임에 따라 합의를 승인 근거로 사용한다.
- 기존 초안과 정정 계획을 커밋한 뒤 `origin/main`의 `102853ec8a13c38d6911f7b51b23ef4c2eb4676c` 위로 rebase했다.
- AST `0b50fd0`, 세션 로그 `38264b6`, LSP `9238a7a`를 통합했다. 각 worker의 diff와 before/after 증거를 읽고 부모가 관련 테스트를 다시 실행해 각각 42/61/73 passed, rc=0을 확인했다. 그 시점에는 통합 전체 게이트와 독립 최종 리뷰가 미실행이었다.
- 각 worker는 Python 3.9에서 실제 CLI·자원/프로토콜 또는 경로 경계 검사를 실행했다. 3.9에 pytest는 없으므로 전체 pytest 통과를 주장하지 않는다. 증거 원본은 migration 디렉터리의 `fix-ast-evidence`, `fix-history-evidence`, `fix-lsp-evidence`에 보존했다.
- Claude의 검수 기준 구체화에 합의: 스킬 커버리지는 모든 스킬을 대상으로 하되 기존 스킬은 사유가 있는 명시적 예외만 허용한다. 기존 agent 게이트와 통합하지 않는다. 자연어 스킬 선택 E2E는 별도 표본 검증이다.
- 설치 doctor는 Python 3.11 이상에서 tomllib, 그 미만에서는 출처 파일의 현재 SHA256과 대조한 JSON snapshot을 사용한다. stale/증거 부재/CLI 부재는 unknown(rc=2), 확인된 불일치는 rc=1, 일치는 rc=0이다. fired는 실행 증거 없으면 unknown이며 config 원문·인증 파일은 출력/수집하지 않는다.
- 스킬 커버리지 `423a294`, doctor `d03b1cb` 및 공유 store 보정 `28b6e8d`를 통합했다. 부모의 관련 검사도 각각 84/109 passed, rc=0이다. 정상 공유 링크와 위험한 하위 링크를 구별하며, 고정한 루트 FD의 메타데이터를 재검증한다. 증거는 `fix-skill-coverage-evidence`, `fix-install-doctor-evidence`에 보존했다.
- 통합 코드와 README·CLAUDE·CHANGELOG 변경을 포함한 fresh `scripts/verify-done.sh`: rc=0, 1674 pytest passed, 36 pass / 0 fail. 원문은 migration 디렉터리의 `verify-remediation.log`에 보존했다. 원격 태그 조회는 실패하여 기존 게이트 정책에 따라 생략됐으며, 로컬 태그 검사는 통과했다. 이 기계 검사 결과는 모델 평가나 독립 리뷰를 대체하지 않는다.
- 격리 소비자 실측: OS 쓰기 거부 양성 대조, 지속 local source의 설치·재설치, 실제 AST C/Python/Go 각 2회, clangd 진단·심볼·정의·참조, 로그 존재/부재 대조, doctor 일치 판정, 네이티브 스킬 17개 탐지를 확인했다. 플러그인 트리는 바뀌지 않았다. 빈 push 진단은 rc=2/잠정, 오류 진단은 rc=1로 구별됐다. 레포 밖 증거는 consumer-final/report.json과 개별 stdout/stderr다.
- 격리 훅은 2개 탐지됐고 enabled=true/trustStatus=untrusted였다. 승인하거나 실행하지 않았으므로 fired는 unknown이다. 실제 홈의 기존 5.5.1·source·enabled 선택을 수정하지 않았다.
- 자연어 Codex E2E는 최초 1회 시도에서 90초 시간 초과했다. 이후 격리 홈의 로그인 부재를 확인하여 재시도하지 않았다. 초기 시도의 모델 출력은 보존되지 않았으므로 발동 증거가 없다. full `scripts/run-evals.sh`도 rc=1, 25개 모두 실행 오류였으며 별도 최소 호출이 `Not logged in`을 반환했다. 인증 파일을 복사하지 않았으며 이 결과는 품질 0점이 아니라 평가 불가다. 관련 원문은 `consumer-final`에 보존했다.
- 신규 description은 각 영어 2문장 이내이며 스킬 수 17개가 문서와 일치한다. SessionStart 출력은 빈 환경 6822B / 최악 21148B로 기존 값과 같다. CLI 지연 표본은 모델 토큰·결과 품질 개선의 증거가 아니다.
- 공개 텍스트 추가 점검에서 기존 web-research의 개인 브라우저 CLI 지정이 남아 있음을 발견해 호스트 capability 확인으로 바꿨다. 공개 페이지 폴백은 로그인 접근 증거로 취급하지 않는다. 비공개 이름 사전 파일은 없으므로 그 사전 검사를 통과했다고 주장하지 않는다.

## 미결 및 다음 단계

- 지정 Claude의 diff 직접 검수·독립 review-code·security-scan·재현 재실행 판정 대기. 기계 검사가 green이어도 execution_status는 in-progress로 유지한다.
- 인증이 필요한 자연어 스킬 선택 E2E, 모델 eval 및 동일 조건 토큰·품질 비교는 미검증이다. 인증 우회 없이 지정 Claude와 처리 방식을 합의한다.
- 5.7 이후 상주 LSP·안전한 rename·브라우저 QA는 별도 Large 설계로 이어간다. 이번 5.6 초안에 구현됐다고 주장하지 않는다.
- main 병합·tag·push·실 홈 변경은 수행하지 않았다.
