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

- 지정 Claude의 1차 독립 검수는 `1b095ca`에 CONDITIONAL이다. 기존 ATK-001~005 수정과 doctor·커버리지 회귀는 독립 재현됐으나, 아래 추가 결함을 수정하고 새 HEAD로 2차 검수를 받아야 한다. execution_status는 in-progress로 유지한다.
- Claude 기존 에이전트 행동 평가는 plan-control이 기존 로그인에서 인증 복사 없이 실행해 13개 에이전트 25/25 pass, rc=0을 확인했다(대상 `1b095ca`). 신규 스킬 자연어 선택·토큰·품질 비교를 입증하지는 않는다. Codex 자연어 E2E는 사용자 본인의 전용 홈 로그인 전까지 미검증이다.
- 5.7 이후 상주 LSP·안전한 rename·브라우저 QA는 별도 Large 설계로 이어간다. 이번 5.6 초안에 구현됐다고 주장하지 않는다.
- main 병합·tag·push·실 홈 변경은 수행하지 않았다.

## 검수 1차 후 수정 계약

- doctor: config/snapshot 심링크는 rc=2로 보고하고 읽지 않는다. plugin store 하위 위험 링크는 rc=1을 유지한다. 잘못된 인자·미지원 레이아웃을 설치 결함과 구별하고, 인증 파일 금지는 정확한 basename으로 제한한다. git worktree 소스는 지원하지 않는다는 구체 사유를 반환한다.
- history: home·하네스 홈의 자체뿐 아니라 상위 루트도 거부한다. 결과 id/cwd 메타데이터를 각 512문자로 제한하고 잘림을 표시한다.
- code-intel/LSP: 알려진 서버 basename 외에는 명시적 custom-server 선택을 요구하며 상대 실행 경로를 거부한다. LSP 누적 수신을 16MiB로 제한하고 비진단 알림 본문을 저장하지 않는다. LF/CRLF/CR 위치와 Unicode 구분자를 구별한다.
- AST: ast-grep 이름만 자동 탐지하고 중립 cwd에서 실행한다. 현재 검증된 0.51.0 외에는 pattern_validated=false, 0건은 unverified로 보고한다. AST/LSP 결과에 비신뢰 알림을 붙이고 자식 환경변수를 최소 허용 목록으로 제한한다.
- 문서: read-only는 클라이언트의 편집 요청·preview 계약이며 언어서버의 프로젝트 코드 실행·파일쓰기·통신까지 차단하지 않음을 명시한다. 신뢰한 작업 공간만 사용하고 광범위한 실행 허용 규칙을 피하도록 안내한다. 공개 계획의 개인 절대경로를 제거한다.
- 검증: 변경별 before FAIL/after PASS, 양성 대조와 Python 3.9 검사를 남긴다. 커버리지 CLI 실행에서 skip=0을 확인하고 legacy 예외는 기존 테스트 부재가 아닌 새 게이트 미연결 부채로 정확히 기술한다. 별도 G-1 경로 길이 의존 게이트는 이번 수정 범위 밖이다.
- 수정은 세 격리 worker의 doctor/코드 분석/history와 부모의 문서·커버리지로 나누며, 통합 후 fresh 전체 게이트와 plan-control 2차 검수를 수행한다.
- 통합 기록: history `d608816`(worker `12883b3`, 부모 90 passed), skip=0·legacy 사유 `e7b159a`(54 passed 및 runtime skip을 이전 검사가 놓치고 새 검사가 거부하는 대조), 공개 문서 `34f6eb9`, doctor `0f3d197`(worker `0afff84`, 부모 198 passed), 코드 분석 `881e454`(worker `b99c96c`, 부모 샌드박스 165 passed와 별도 stdlib 프로세스 검사 4 passed). doctor 수정 전 동일 회귀는 94 failed/104 passed였고 수정 후 198 passed다. 코드 분석의 새 행동 회귀 30개도 수정 전 실패하고 수정 후 통과했다.
- Python 3.9 실제 CLI 회귀는 history 21개, doctor 15개, 코드 분석 두 설치본 각각 16개이며 3.9 전체 pytest 결과가 아니다. 부모의 첫 코드 분석 재검증은 샌드박스에서 ps 실행이 막혀 4 failed/165 passed였으며, 해당 4개는 외부 엔진 없는 stdlib 검사로 분리하고 남은 샌드박스 검사도 정확한 선택 조건으로 다시 실행해 두 범위 모두 rc=0을 확인했다. 이 환경 실패와 재실행 원문도 보존했다.

## 검수 2차 후 수정 계약

- 대상 `e786fd9`의 부모 전체 게이트는 rc=0, 1851 passed, 37 pass/0 fail이며 격리 소비자 설치·재설치도 통과했다. plan-control의 독립 재실행은 1851 passed, 36 pass/0 fail(원격 태그 생략)이다. 독립 판정은 아래 추가 결함 때문에 CONDITIONAL이다.
- history: 선택 루트의 고정 FD와 보호 루트·조상의 `(st_dev, st_ino)`를 비교해 대소문자 비구분 파일시스템의 표기 우회를 막는다. `CLAUDE_CONFIG_DIR`도 보호하고 빈 하네스 홈 환경값은 무시한다. 정상 하위 sessions/projects는 허용한다.
- 코드 분석 환경: 툴체인 설정을 보존하되 비밀·로더 변수 이름은 먼저 거부한다. CPATH 삭제로 정상 코드가 header 오류로 오판된 재현을 양성 대조로 고정하고 결과에 environment=filtered를 표시한다.
- 서버 선택: 알려진 basename만으로 신뢰하지 않는다. 절대경로는 PATH에서 찾은 같은 이름의 실제 경로와 일치해야 하며, 작업 공간 내부 실행 파일 또는 상대 which 결과는 명시적 custom 선택이 필요하다. AST 상대 which 결과는 실행 전 거부한다. 보관하지 않는 알림은 바이트 예산으로 제한하고 개수 상한은 보관하는 진단에만 적용한다.
- doctor N-5 해석은 plan-control과 확정했다. Git 설치본과 제공 checkout이 일치하면 rc=0을 유지하되 comparison_scope=supplied_checkout와 remote_freshness=unverified를 표시한다. checkout 쪽 manifest/identity/버전 문제는 source_checkout_unverified 사유의 rc=2, 버전 불일치는 두 버전을 표시한다. 설치본/store 자체 결함과 local 설정 원본 불일치는 rc=1을 유지한다.
- doctor 권장 수정: 시스템 조상 링크를 자동 허용하지 않고 canonical path 힌트를 제공한다. `.env.*`·`.credentials.json`을 파일 금지 범위에 포함하되 비슷한 정상 이름은 허용한다. 훅 오류의 종료코드 정책을 한곳에서 분류한다.
- 스킬 선택용 description·생성 short description·README·CLAUDE 표도 신뢰 작업 공간과 서버의 코드 실행 가능성을 명시한다. 생성물은 SSOT에서 재생성한다.
- plan-control의 `e786fd9` 행동 eval 전체 실행은 24/25, 나머지 1건은 실행 오류였다. 해당 시나리오 단독 재실행은 1/1 통과했으며 plan-control은 일시 실행 오류로 판단했다(원인 미확정). 이 결과는 기존 에이전트 회귀 증거이며 신규 스킬 선택·품질 증거는 아니다.
- 새 수정도 e786fd9 기준 세 격리 worker와 부모 문서 작업으로 진행한다. 통합 후 항목별 커밋·테스트 노드·수정 전후 증거와 fresh 전체 게이트를 묶어 검수 3차를 요청한다. Codex 자연어 E2E와 공개 배포는 미완료로 유지한다.
- review3 최초 worker 세 기는 Codex bootstrap의 workspace routing discovery timeout으로 구현 전에 종료됐다. 세 트리는 기준 HEAD에서 clean이며 새 구현 증거는 없다. plan-control과 복구를 합의해 프로세스 부재를 재확인한 뒤 guarded stop으로 정산했다. 비대화 로그인 상태 확인은 쓰기 거부 경계에서 rc=0이며, 이것만으로 TUI bootstrap 성공을 주장하지 않는다. 한 기의 bootstrap을 먼저 확인한 뒤 나머지를 재시도한다. 같은 오류가 재발하면 동시 재기동 없이 엔진 전환을 협의한다.
- 검수 3차 증거표에는 수정 엔진을 명시한다. Claude로 전환할 경우에도 기존 브리프·N-5 계약·실 홈 및 공개 배포 금지를 유지하며 인증 만료는 별도 실행 차단으로 보고한다.
- N-1/N-6 history 수정은 Codex worker `b603ca6`에서 부모 `bf4b796`으로 통합했다. 부모가 diff와 증거를 검토하고 격리된 두 모듈 테스트를 직접 실행해 rc=0을 확인했다. worker의 커밋 후 검증은 CLI 계약 포함 122 passed/1 FS 조건 skip, Python 3.9 실제 import·CLI는 33/33이다. case-sensitive 파일시스템의 반대 방향 양성 대조는 이 APFS 볼륨에서 실행할 수 없어 skip이며 해당 한계를 유지한다.
- history worker의 task outcome은 failed로 보존한다. 커밋 시 기존 pre-commit이 Ruff를 명시적 격리 밖에서 자동 실행한 절차 예외가 있었으며, 실제 홈 접근의 전체 추적 증거는 없다. 부모의 코드 통합 판정은 이후 격리 검증과 diff에 근거하며 과거 실행의 격리 준수를 소급 주장하지 않는다. 예외는 plan-control에 전달했고 3차 검수 자료에도 포함한다. 부모 cherry-pick은 저장소·git 메타데이터·임시 경로 외 쓰기를 거부한 상태에서 rc=0이다. 전체 통합 게이트와 독립 검수는 아직 남아 있다.
- plan-control은 history 산출물의 통합 브랜치 수용에 동의했고 최종 판단은 3차 검수로 남겼다. 남은 worker의 커밋에도 sandbox를 적용하는 선택지 (a)를 채택했다. 설치된 훅에는 자동 수정 후 재스테이징 분기가 있으므로 clean 상태만으로 자동 수정 부재를 단정하지 않는다. 훅 우회 없이 커밋 결과와 검증한 내용을 대조하고, 변경됐다면 최종 커밋 기준으로 재검증한다.
- doctor N-4/N-5/N-7/N-9는 Codex worker `60c3b85`를 부모 `acc5cac`으로 통합했다. 부모가 diff를 검토하고 동일 격리 경계에서 368개 테스트를 직접 실행해 전부 pass/rc=0을 확인했다. worker의 Python 3.9 실제 CLI 18건과 native snapshot 캡처 등을 합친 35건은 각각 기대한 rc를 확인했으며, 3.9 전체 pytest는 미설치로 실행하지 않았다. 상세 증거 커밋은 배포 브랜치에 넣지 않고 migration 증거 디렉터리에도 복사해 보존했다. 뒤늦게 도착한 커밋 격리 지침에 대한 doctor 후속 task가 진행 중이므로 해당 실행 경계의 최종 판정은 그 보고와 함께 기록한다.
- doctor와 intel 후속 보고에서 기존 커밋의 동일 격리 위반을 확인했다. 두 후속 task는 failed로 정정했고 원 보고서와 정정·커밋 후 격리 재검증·해시 증거를 함께 보존했다. plan-control은 세 예외를 명시하는 조건으로 동일한 산출물 수용 기준에 동의했다. 과거 훅의 no-fix나 실홈 쓰기 부재를 보증하지 않는다. 오래된 설치 훅 사본은 이번 범위에서 수정하지 않았으며 최종 보고 사항이다.
- intel N-2/N-3/N-8/N-10/N-11은 Codex worker `e8efd0c`에서 부모 `48dfbff`로 통합했다. 부모는 격리 검사 191개와 별도 stdlib 프로세스 정리 4개를 직접 실행해 rc=0을 확인했다. 첫 부모 명령은 실행 파일 인덱스 오류로 테스트 시작 전 rc=64였고, 올바른 명령의 별도 로그를 보존했다. worker의 실제 Python 3.9.6 검사는 7개 import 포함 31건이며 3.9 전체 pytest는 미설치다. 검증 중 재현된 macOS zombie-group EPERM은 종료된 leader를 reap하고 group signal을 재시도해 해결했다. 부모 리뷰에서는 기존 close 테스트에서 옮겨져 중복된 assertion을 원래 테스트로 복원했다.
- 릴리스 전 추가 조건: plan-control이 공유한 디렉토리 정책 재판정에 따라 probe 브랜치 Validate 결과를 확인한다. 해당 공유는 아직 부모가 독립 검증하지 않은 외부 판정이며, 조사 브랜치 push와 main/tag/릴리스 공개는 사용자 확인 뒤에만 수행한다. 이번 로컬 수정 검증을 디렉토리 승인으로 표현하지 않는다.

## 검수 3차 및 4차 수정 계획

- `783b90d`의 부모 fresh gate는 rc=0, 37 pass / 0 fail, pytest 2,071 passed이며 소비자 설치·재설치 probe도 rc=0이다. plan-control도 동일 delta와 fresh gate를 확인했으나 판정은 CONDITIONAL이다. 기존 N-1~N-11 수정의 되돌려-FAIL을 확인했으며 추가 P-1~P-9가 남아 있다.
- 스킬 발화 표본은 HEAD/base 각각 2케이스×3회 전부 통과했고 기존 스킬 발화 스위트는 6/6이다. 이는 제한된 선택 회귀 증거이며 품질·토큰 개선의 증거가 아니다. plan-control의 3차 에이전트 eval은 기존 로그인으로 실행해 13종·25/25 pass, rc0이다. 인증을 복사하지 않았으며 이 결과도 P-1~P-9 CONDITIONAL 판정을 해소하지 않는다.
- P-1/P-8: AST·LSP 공용 실행 경로 검사와 자식 PATH 정제. 명시적 custom-server opt-in 없이는 빈·상대·작업공간 하위 PATH를 자식에게 넘기지 않으며 AST의 작업공간 실행 파일은 probe 전 거부한다.
- P-2/P-3/P-4: Go 변수 정확 목록과 자격증명·Cargo 실행 wrapper 거부, 고정 executable과 원래 argv0 분리, 추가 서버 인자 opt-in 및 알려진 명시 서버 기본 인자를 적용한다.
- P-5/P-6: 없는 설치 버전 디렉터리는 rc2, 존재하는 설치본 manifest 결함은 rc1. 층별 관측 사유를 보존하고 최종 판정 우선순위는 rc1 > rc2 > rc0이다(숫자 최댓값이 아니다).
- P-7: history 디렉터리 하강 때 열린 FD의 identity를 보호 집합과 비교한다. 실제 홈 탐색 대신 임시 픽스처로 검증하고 firmlink 실측은 stat으로 한정한다. P-9와 관련 문서 한계도 함께 정정한다.
- plan-control은 위 계약에 동의했다. 수정은 `783b90d` 기준 세 영역으로 나누되 worker의 git commit을 금지하고 검증된 패치를 반환받는다. 부모가 검증·통합 커밋을 sandbox 안에서 수행한다. 이전 격리 예외 3건은 기록을 유지한다.
- 세 Codex worker가 기준 HEAD에서 패치를 반환했고 부모가 diff·패치 해시·원본 검증 로그를 대조했다. 부모 재실행은 intel 134개, doctor 401개, history 132개 통과(파일시스템 조건 skip 1개)이며 쓰기 거부 경계에서 실행했다. worker는 커밋하지 않았고 패치·비공개 증거를 보존한 뒤 터미널을 해제했다.
- intel 인접 검사의 기존 Ruff fixture는 명시 서버 기본 인자와 중복되던 `--server-arg=server`를 제거했다. worker의 sandbox에서 `ps`가 차단된 기존 프로세스 정리 4건은 통합 게이트에서 확인한다. 부모는 진단 개수 제한의 두 경로를 모두 미검증 결과로 통일하고 회귀 검사를 추가했다.
- 스킬 본문 변경은 code-intel과 session-history 두 파일이다. 실행 경로·환경 변수·상한·보호 경로 건너뛰기와 도구의 한계를 문서화했으며 description은 바꾸지 않았다. 최종 완료는 새 frozen HEAD의 재현·fresh gate·4차 독립 검수 후 판단한다. 실행 상태는 in-progress다.
- 첫 통합 게이트는 pytest 실패로 rc1(36 pass / 1 fail)이었다. 기존 PATH 원문 보존 단언과 작업공간 내부의 AST 양성 fixture가 새 계약과 충돌했고 후자의 실패가 CLI 커버리지 실행 검사에 전파됐다. 외부 엔진 양성 fixture와 정제 PATH 기대값으로 수정한 뒤 실패 노드 3개를 직접 재실행해 모두 통과했다. 게이트 정책·등록 노드·기존 행동 검증은 유지했으며 전체 최종 게이트는 새 커밋 기준으로 실행한다.

## 검수 4차 및 5차 수정

- `cd79331`의 최종 게이트는 rc0, 37 pass / 0 fail, pytest 2,161 passed, 소비자 probe rc0이다. plan-control은 같은 delta·게이트와 P-1~P-9 되돌려-FAIL을 확인했으나 Q-1~Q-3로 CONDITIONAL 판정을 유지했다. code-intel 표본과 기존 발화 스위트는 각각 6/6이며 에이전트 eval은 아직 결과 대기다.
- Q-1: 실행 파일과 PATH 항목의 조상들을 한 번 얻은 작업 공간 identity와 비교한다. 같은 identity를 실행 파일 선택과 자식 환경 구성에 공유하며 검사할 수 없는 PATH 항목은 제거한다. 실제 대소문자 alias의 node·AST·clangd 실행과 모든 파일시스템에서 동작하는 identity 양성/음성 대조를 추가한다.
- Q-2: passwd KeyError·빈/상대 pw_dir와 빈/상대 HOME은 무시하고 유효한 절대 홈 보호를 유지한다. 둘 다 없으면 JSON 오류다. POSIX 확인 뒤에 pwd를 import한다. Q-3: doctor help에서 진단의 읽기와 명시적 snapshot 쓰기를 구분한다.
- 부모가 쓰기 거부 sandbox에서 수정 전 회귀 15개 중 12개 FAIL을 확인했고 수정 후 같은 15개가 통과했다. 실행 상태는 in-progress이며 새 frozen HEAD의 전체 게이트와 5차 독립 검수 전 완료를 주장하지 않는다.
- 합의한 경계와 잔여: 작업 공간 경계는 명시적 root이며 상위 저장소 자동 확장·다음 PATH 후보 자동 선택은 하지 않는다. 환경은 신뢰 입력이고 이름 필터는 값의 비밀정보·툴체인 실행을 차단하는 sandbox가 아니다. history identity는 백업 복사본을 구분하지 못한다. doctor 초기 snapshot 검증의 조기 종료/상세 reason 귀속·capture 관측, LSP close 오류의 출력 리팩터는 이번 필수 Q 수정과 분리해 후속으로 남긴다.
- 최종 Q 회귀는 20개이며 관련 격리 검사 전체는 768 passed / 1 FS skip이다. 생산 5파일만 기준 HEAD로 되돌린 scratch에서는 16 FAIL / 4 PASS이고, Q-1~Q-3 각각 실제 행동 실패가 있다(공유 identity 헬퍼 부재 검사는 별도 구조적 실패). 실제 Python 3.9.25에서 모듈 5개 import·case alias 차단·passwd fallback·홈 불명 JSON·doctor help를 확인했다. 기존 서버 선택 단위 fixture 네 곳은 존재하는 root identity를 검사할 수 있도록 빈 workspace 디렉터리 생성을 추가했고 기존 단언은 유지했다.

## 코드 검수 수용 — 배포 전 관문 유지

- plan-control은 `3ae8f51405168e767144b4306ed1c529b0add0b5`에 **ACCEPT**를 판정했다. delta 바이트 일치, 독립 fresh gate rc0 / pytest 2,181 passed, Q 회귀 되돌려-FAIL 16/20, Q-1 실행 3종 차단과 외부 엔진 양성, Q-2 홈 조합 9종과 보호 유지, Q-3 help를 직접 확인했다. 독립 review-code는 ACCEPT(H0/M1/L6), code-intel 선택 표본은 2케이스×3회 6/6이다.
- 부모의 같은 HEAD fresh gate는 rc0 / 37 pass / 0 fail / pytest 2,181 passed이며 소비자 probe rc0, 스킬 17개 발견, 설치·재설치 후 플러그인 해시 불변이다. 이 결과는 토큰·성능·전체 결과 품질 개선의 증거가 아니다.
- 표현 확정: 실행 파일 선택과 자식 환경 구성 사이에 공유하는 것은 **root identity**다. 선택은 아직 부모 PATH의 첫 후보를 사용하고, 자식 PATH는 별도로 정제한다. 첫 후보를 거부하면 뒤의 후보를 자동 선택하지 않는다. 고정 FD 기반 root identity, identity/root 일치 검증, AST 공유 검사의 보강 등 권장은 후속 항목으로 남긴다.
- 이번 판정은 코드 검수 수용이며 릴리스 승인이 아니다. 4차 에이전트 eval 최종 결과는 대기 중, Codex 자연어 E2E는 격리 홈 미로그인으로 미검증, 실 홈 설치는 미실시다. 따라서 전체 실행 상태는 in-progress로 유지한다.
- main merge·tag·push와 probe 브랜치 push는 사용자 확인 대상이다. 릴리스 전 Claude 디렉토리 probe Validate가 필요하며, 코드 ACCEPT를 해당 정책 검증이나 공개 승인으로 대신하지 않는다. 상주 LSP·rename·browser는 별도 Large 설계 범위로 남는다.
