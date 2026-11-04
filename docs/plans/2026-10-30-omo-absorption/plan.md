---
title: "OMO의 유용한 기능을 hiway-kit에 선택적으로 통합하고 로컬 OMO 제거"
status: superseded
superseded_by: docs/plans/2026-11-04-omo-audit-remediation/plan.md
as_of: 2026-11-04
execution_status: superseded-after-audit
created: 2026-10-30
size: large
---

## 요구사항

> **2026-11-04 정정:** 아래 구현·검증 기록은 10월 30일 당시의 기록이며 현재 완료 상태가 아니다.
> 11월 2일 독립 감사에서 정상 AST 패턴 오거부, LSP 거짓 성공, 응답 검증·파일 읽기·자원 한도 결함과
> 설치 버전 회귀가 확인됐다. 현재 설치는 5.5.1이며 활성 계정 훅은 이전부터 disabled였다.
> 따라서 “훅 승인만 남음”, “기존 기능에 흡수”와 마지막 수동 attest를 현재 결론으로 사용하지 않는다.
> 후속 작업은 [감사 결함 수정 계획](../2026-11-04-omo-audit-remediation/plan.md)에서 추적한다.

- OMO 기능 전체를 확인해 유용한 요소를 hiway에 통합한 뒤 OMO를 제거한다. `[confirmed: 사용자]`
- 상시 지침 증가 없이 필요한 작업에서만 도구와 참조를 읽는다. `[researched: 로컬 16회 비교, n=16; OMO 입력 평균 2.32배, 정확도 동일]`
- 기존 Claude/Codex 동작, Python 3.9 floor, MCP 미설치 환경과 설치 캐시의 읽기 전용 사용을 유지한다. `[confirmed: CLAUDE.md]`
- 사용자 모델/인증/다른 플러그인/직접 작성한 에이전트는 보존한다. OMO가 소유한 설정과 설치물만 백업 후 제거한다. `[confirmed: 제거 요청의 범위]`

## 결정

- 사용자가 조사·통합·제거까지 실행을 요청했다. 설계 확인을 다시 요청하지 않고 채택 근거를 기록하며 진행한다.
- 기준은 `2600cf6`의 hiway-kit 5.5.1, 감사 대상은 설치·실측한 OMO 5.1.48의 고정 소스다. 통합 버전은 5.6.0이다.
- 채택: AST 구조 검색/변경 미리보기, 필요 시 실행하는 읽기 전용 LSP 조회, 명시적 로컬 세션 검색, 반증 가능한 가설·실제 사용면 검증·출처/증거 기록.
- 기존 기능에 흡수: 계획/진행/재개/리뷰/리서치/브라우저 경로. 호스트 기능과 기존 hiway 도구를 우선한다.
- 제외: 전역 모델/성격 지침, 자동 설치·업데이트·텔레메트리, 무제한 실행/강제 팀 생성, 모든 주석의 차단, 누락 LSP마다 설치 질문/전역 결정 기록, 고정 도구 의존.
- 언어 서버는 이미 설치된 실행 파일 또는 명시한 명령만 쓴다. 상시 데몬/MCP 서버를 번들하지 않는다. 언어 서버가 없거나 응답이 없으면 미검증으로 보고한다.
- AST 도구는 조회와 미리보기만 제공한다. 실제 변경은 사용자가 검토 가능한 diff와 기존 편집 도구를 이용한다.
- 세션 검색은 명시된 로그 루트 안의 JSONL만 읽고, 내용은 비신뢰 데이터로 출력한다. 인증 파일·상태 DB·전체 홈 검색은 하지 않는다.
- 설정 및 패키징 변경은 메인 세션이 수행한다. 현재 사용자 작업에는 활성 Orca Dispatch가 없으므로 과거 감독 작업의 권한/식별자를 재사용하지 않는다.
- 제거는 hiway 소비자 경로 테스트와 전체 게이트 이후 실행한다. 기존 Claude 에이전트 행동 eval은 독립적으로 계속 실행한다. 실패 시 백업을 보존하고 실패 범위를 보고한다.

## 구현 계획

1. OMO 스킬/컴포넌트 채택·중복·제외 전체 대응표와 라이선스 출처를 기록한다.
2. `code-intel` 스킬과 AST 조회 도구, 일회성 LSP 클라이언트를 구현하고 경로·프로세스·응답 경계 테스트를 추가한다.
3. `session-history` 스킬과 한정된 JSONL 검색 도구, 형식/심링크/깨진 레코드/크기 제한 테스트를 추가한다.
4. 기존 debug/review/web-research/plan-task에 필요한 시점의 짧은 참조를 연결한다. 전역 룰과 기본 훅은 늘리지 않는다.
5. 버전/CHANGELOG/문서를 갱신하고 소비자 임시 디렉토리에서 실제 AST·clangd·세션 검색을 검증한다.
6. 전체 완료 게이트와 행동 eval을 실행하고, 사용자 설정의 새 스냅샷을 백업한 뒤 hiway 갱신 및 OMO 소유 설치물을 제거한다.
7. 새 Codex 런타임에서 hiway 로드·OMO 미등록·훅 승인 상태 및 사용자 설정 보존을 확인하고 결과를 기록한다.

## 완료 조건

- `python3 -m pytest tests/hooks/test_code_intel.py tests/hooks/test_lsp_query.py tests/hooks/test_session_history.py -q` (exit 0)
- `ruff check plugins/common/tools tests/hooks` (exit 0)
- `bash scripts/verify-done.sh` (fresh run, exit 0)
- `bash scripts/run-evals.sh` (exit 0, 실행 환경 미충족 시 실제 오류와 미검증 범위를 기록)
- 별도 임시 소비자에서 ast-grep 조회/미리보기, clangd diagnostics/definition/references/symbols, 합성 세션 검색의 실제 출력 및 종료코드로 판정한다.
- 백업/제거 점검기는 OMO 플러그인·마켓플레이스·관리 역할 잔존 시 nonzero, 원래 사용자 설정의 변경 시 nonzero로 종료한다.

## 검증 결과

- 새 도구 경계/실제 바이너리 검사: 20 tests passed. 잘못된 AST 패턴, 경로 탈출, 서버 부재/타임아웃/잘못된 JSON-RPC,
  서버 편집 요청 거부, 깨진 JSONL/심링크/이름 있는 파이프/크기 한도와 실제 clangd 양성·음성 사례 포함.
- `bash scripts/verify-done.sh`: 최종 fresh run 36 pass / 0 fail, rc=0, 전체 pytest 1,352 passed.
  백업 폴더의 `verify-done.log`에 전체 출력을 보존했다.
- 소비자: 임시 CODEX_HOME에 네이티브 marketplace/add + plugin/add. ast-grep 검색/미리보기,
  clangd 네 가지 요청 및 잘못된 C 진단, JSONL 검색 모두 성공. 플러그인 트리 전후 파일 해시 동일.
  OS sandbox는 임시 디렉터리 밖 쓰기를 거부하는 음성 대조로 검증했다.
- 소비자 증거: 당시 임시 소비자 환경의 report.json(로컬 migration 증거에 보존).
- OMO 공식 Node 전용 제거기를 격리 실행해 절대경로 에이전트 등록 13개가 남음을 확인했다.
  실제 제거는 배포 원문과 바이트가 같은 에이전트만 식별하고, 두 config의 비관련 TOML 값이 동일함을 검사하는 방식으로 수행했다.
- 실제 마이그레이션: 두 홈에서 각각 관리 역할 13개 등록 해제, 소유 경로 42개 및 신뢰 기록/데몬 상태 3개를 백업으로 이동.
  OMO 전용 LSP 프로세스 3개 종료. 모델/인증/다른 플러그인 설정 보존. 인증 파일은 수정하거나 복사하지 않았다.
- 백업 및 복원 매핑: 사용자 로컬 데이터 디렉터리의 hiway-kit migration 기록(2026-10-30-omo).
  `manifest.json`·`moved.json`·`auxiliary.json`과 각 홈의 config.before/config.after가 실제 변경을 기록한다.
- 새 app-server 두 개에서 각각 hiway 5.6.0 스킬 17개, OMO 스킬/훅 0개 확인.
  현재 세션은 이미 로드한 도구/지침을 메모리에 유지할 수 있어 재시작이 필요하다.
- **남은 사용자 조치:** 새 버전의 hiway 훅 2개는 Codex `trustStatus: modified`다.
  이전 버전의 승인을 새 파일 내용에 자동 전용하지 않았다. 사용자의 네이티브 훅 승인이 필요하며, 승인 전 실제 세션 훅 실행 정상은 미검증이다.
- 자체 적대적 검토에서 잘못된 응답의 거짓 성공과 특수 파일 대기를 찾아 수정했다. 독립 리뷰는 수행하지 않았다.
- 별도 CODEX_HOME에서도 기본 설정 루트는 검색하지 못하도록 보강했다. 합성 HOME 대조에서 보강 전은 rc=0,
  보강 후 설치본은 rc=2로 거부한다. 백업 `log-root-before-after.json`·`log-root-negative.json`에 기록했다.
- 설치 파일 115개는 검토한 소스 스냅샷 및 현재 플러그인 소스와 해시가 같고, 두 홈의 비관련 설정 보존/OMO 런타임 부재도
  `final-audit.json`으로 확인했다. OMO 설치 질문 기록도 백업으로 옮겼다.
- 기본 훅/전역 규칙의 내용은 그대로다. 세션 시작 주입은 빈 소비자 6,822B, 최악 21,148B로 기존 예산 이내다.
- 공개 배포·push·main 병합은 하지 않았다. `omo_test`, 기준 HEAD `2600cf63f40e12c5f7bdb29abe80cb7a43614967` 위의 로컬 변경이다.
- 전체 행동 eval: `bash scripts/run-evals.sh` rc=0, 13개 에이전트의 25/25 시나리오 통과.
  `evals/reports/20261029T195407102890Z.json`과 백업 폴더 `agent-evals.json`에 원본을 보존한다.
- 수동 attest: 채택/중복/제외 대응표, 구현 범위, 문서/CHANGELOG, 버전/생성물, 소비자 동작,
  OMO 소유권 식별/백업/제거/설정 보존은 검증했다. 현재 남은 항목은 사용자 훅 승인과 승인 후 실행 확인뿐이다.
  문서 지위 `status: current`는 저장소 문서 스키마를 따르고, 실행 상태는 `execution_status`로 구분했다.
