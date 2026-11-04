---
status: current
as_of: 2026-11-04
---

# OMO 기능 감사와 hiway-kit 통합

2026-10-30. 대상: OMO 5.1.48, hiway-kit 5.5.1 → 5.6.0. 설치본의 27개 스킬 설명/진입점,
16개 컴포넌트 계약과 관련 구현을 확인했다. 전체 의존성의 모든 코드를 줄 단위 감사했다는 뜻은 아니다.
필요한 기능을 조건부로 제공하는 것이 선택 기준이다. 새 스킬의 description은 발견 목록에
추가되므로 상시 프롬프트 비용이 전혀 없다는 뜻은 아니다.

**11월 2일 독립 감사와 11월 4일 설계 합의를 반영한 정정:** 아래는 완전 대체 목록이 아니다.
정적 계약 감사는 실행 동등성이나 성능 우위를 증명하지 않는다. 5.6.0은 기존 초안의 오류 수정과
설치 진단까지이며 상주 LSP·rename·브라우저 QA 등은 후속 설계 대상이다.

## 근거와 범위

- [고정 OMO 소스](https://github.com/code-yeongyu/lazycodex/tree/75b017473c71d669dd9aed0a10e950e70724b283/plugins/omo)
- [스킬 원문](https://github.com/code-yeongyu/lazycodex/tree/75b017473c71d669dd9aed0a10e950e70724b283/plugins/omo/skills)
- [컴포넌트 원문](https://github.com/code-yeongyu/lazycodex/tree/75b017473c71d669dd9aed0a10e950e70724b283/plugins/omo/components)
- 로컬 사전 비교: 동일 모델/effort, 2개 C 과제 × 4조건 × 2반복. 기본/hiway/OMO/동시 사용은
  모두 과제 4/4, 조건당 4,370개 검사 통과. OMO의 평균 입력은 기본의 2.32배, 비캐시 입력은
  3.06배, 시간은 1.15배였다. 작은 과제 표본이므로 복잡한 개발 작업 전체의 품질이나 비용을 일반화하지 않는다.
- 이번 통합은 아래 기능·경계 검증이다. 통합판의 토큰 절감률을 새로 측정했다고 주장하지 않는다.

## 스킬 대응표

| OMO 스킬 | 감사 분류 | 실제 제공 범위와 남은 차이 |
| --- | --- | --- |
| ast-grep | 부분구현 | AST 검색·replacement preview 구현. 적용·YAML 규칙·규칙 테스트/scaffold는 미구현. 수동 편집은 codemod 적용과 동등하지 않다. |
| lsp | 부분구현 | 일회성 diagnostics/symbols/definition/references 구현. 데몬·인덱스 재사용·workspace symbols·prepareRename/rename·format은 미구현. pull 진단은 감사 후 보강. |
| lsp-setup | 부분구현 | 설치된 서버 탐색과 명시적 명령 지원. 프로젝트 설정 탐색·전체 status·설정 진단 CLI는 미구현. 자동 설치는 의도적으로 제외. |
| coding-agent-sessions | 부분구현 | Codex/Claude JSONL 텍스트 검색. 다른 호스트 DB·전체 transcript/tool payload·자식 관계·시간/모델 필터는 미구현. |
| debugging | 부분구현 | 기존 재현/격리/수정/검증과 가설 지침. DAP 클라이언트·언어별 attach/cleanup 도구는 미구현. |
| review-work | 부분구현 | 기존 review와 실제 사용면 증거 지침. evidence receipt 자동 집행·실행 순서의 동등성은 미검증. |
| visual-qa | 지침만반영 | 조건부 시각 점검 지침. image diff·TUI grid·capture manifest·freshness/전체 페이지 게이트는 미구현. |
| programming | 지침만반영 | 버전·타입·경계·실패 가능한 테스트 원칙. 언어별 전체 규약은 미이식. 강제 최신 버전 정책 제외. |
| refactor | 지침만반영 | 동작 보존·호출자 범위·회귀 지침. semantic rename·AST apply·dependency map은 미구현. |
| remove-ai-slops | 지침만반영 | 검증된 중복/죽은 코드 정리 지침. 전용 단계와 smell 목록은 미이식. 취향에 따른 전면 재작성 제외. |
| init-deep | 지침만반영 | 진입점·규약·검증 소유권 탐색. 계층형 지식베이스 생성·scoring/code map은 미구현. |
| ulw-research | 부분구현 | 기존 다중 출처 조사와 증거 지침. claim/fact/source/outcome CLI와 산출물 검증 게이트는 미구현. |
| browser | 외부도구의존 | 제공된 호스트 브라우저 활용. 자체 browser library·network/trace/download·adapter conformance는 미구현. 외부 도구의 존재만으로 대체를 보장하지 않는다. |
| ultimate-browsing | 외부도구의존 | 호스트 검색/fetch/브라우저 활용. fetch chain·content validator·surrogate provenance는 미구현. |
| frontend | 지침만반영 | 프로젝트 디자인 규약과 조건부 visual QA. 전용 디자인 참조·draft lint·Lighthouse 도구는 미이식. |
| data-scientist | 외부도구의존 | 프로젝트 분석 도구 활용. 연결 재사용·DuckDB/Polars adapter·quick query는 미구현. OMO도 영속 커널 자체는 호스트 의존. |
| git-master | 외부도구의존 | git-workflow는 Claude 에이전트이며 호스트 git을 활용한다. 다른 하네스에서 같은 제공을 보장하지 않으며 bisect/history recipe 동등성 미검증. |
| teammode | 외부도구의존 | control-loop/child-session과 호스트 협업. roster·runtime binding·재시작 reconciliation 엔진은 미구현. checklist는 계획 진행 저장이다. |
| ulw-plan | 부분구현 | brainstorming/plan-task의 계획·승인 흐름. OMO scaffold 산출물과 정확한 gate routing은 미이식. |
| ulw-execute | 부분구현 | auto-dev와 실행 검증 기반 checklist. Boulder binding·evidence ledger·동일 continuation 런타임은 미구현. |
| ulw-loop | 부분구현 | 완료/무진전/실패 가드와 계획 재개. 세션 goal API·checkpoint transaction·steering reconciliation은 미구현. |
| ultrawork | 부분구현 | 작업 규모·계획/checklist·완료 규율. prompt-trigger/goal/notepad 런타임은 미구현. 모델·성격 강제 제외. |
| rules | 부분구현 | 규범 주입·정적 export·드리프트 검사는 구현됨. 여러 규칙 소스 매칭·편집별 dedupe·post-compact 예산 엔진은 다르다. |
| comment-checker | 지침만반영 | 리뷰 판단 지침만 제공. 자동 parser/binary/feedback 훅은 미구현이며 일괄 주석 차단 정책은 제외. |
| lcx-doctor | 제품전용 | OMO 전용 진단은 제외. 설치 상태와 출처를 대조하는 아이디어만 hiway 진단 보강에 채택. |
| lcx-report-bug | 제품전용 | OMO 이슈 라우팅 제외. 증거 중심 보고 형식은 기존 debug에서 사용. |
| lcx-contribute-bug-fix | 제품전용 | OMO 제품 배포 절차 제외. hiway 릴리스 규약 사용. |

분류는 스킬 전체의 계약 기준이다. 좁은 기능이 구현됐어도 해당 스킬 전체가 구현됐다는 뜻은 아니다.
`제품전용` 세 항목은 제품 고유 동작을 제외한다는 뜻이며, 나머지 미구현 기능의 유용성이 없다는
뜻이 아니다. OMO 공개 LSP 도구에서도 hover/code actions 호출 구현은 찾지 못했으므로 이를
이미 존재했던 기능의 누락으로 세지 않는다.

## 후속 설계 대상

- 상주 LSP·workspace symbols·안전한 rename: 네이티브 호스트 LSP를 우선하고, 없는 하네스에서만
  프로젝트/세션 범위의 opt-in 런타임을 검토한다. 수명·고아 정리·stale hash·실패 복원 검증이 선행한다.
- 브라우저 QA: 개인 도구 설치를 가정하지 않는다. 설치된 Playwright와 일반 호스트 capability를
  대상으로 네트워크·trace·download·로그인 인계의 실제 계약을 검증한다. 자동 의존성 설치는 제외한다.
- AST 적용/YAML, 시각 증거·연구 claim 게이트, 협업 lifecycle 검증, 세션 reader·데이터·DAP는
  별도 사용 사례와 실행 가능한 완료 조건을 작성한 뒤 채택 여부를 결정한다. 현재는 완료 항목이 아니다.

## 컴포넌트 대응표

| OMO 컴포넌트 | 처리 |
| --- | --- |
| git-bash / git-bash-mcp | 호스트 셸/git 도구 사용, 런타임 미번들 |
| lsp / lsp-daemon / lsp-tools-mcp | 읽기 전용 일회성 stdio 클라이언트로 독립 구현; MCP/상주 데몬 미번들 |
| bootstrap | 자동 다운로드·업데이트·전역 설정 변경 제외 |
| ultrawork | 전역 프롬프트/모델 오버라이드 제외 |
| ulw-loop / ulw-execute-continuation | 기존 계획/체크리스트/재개 규율 사용 |
| lazycodex-executor-verify | review 조건부 증거 대조 및 프로젝트 검증 명령 사용 |
| teammode | 기존 호스트 협업과 hiway control-loop 사용 |
| comment-checker | 편집마다 실행되는 검사 제외 |
| lcx | OMO 전용 관리 도구 미번들 |
| rules | 기존 hiway 규범 주입/정적 export 사용 |
| telemetry | 미번들, 수집 없음 |
| test-support | 새 구현 자체 경계/실제 도구 테스트로 대체 |

## 소비자 계약과 한계

새 두 스킬은 필요할 때 읽는다. 기본 훅/전역 룰은 늘리지 않는다. Python 3.9 이상과 기존
실행 파일만 사용하며 인증·전역 설정·캐시 안 파일을 도구가 수정하지 않는다(`python3 -B`).
LSP 서버 자체의 캐시/빌드 실행 정책은 서버에 달려 있으므로 비신뢰 프로젝트는 호스트 sandbox로
쓰기 권한을 제한한다. 읽기 전용 요청은 서버 프로세스에 대한 OS 쓰기 차단과 같지 않다.

현재 도구 경계 구현은 POSIX용이다. LSP는 stdio와 UTF-16을 사용하고 pull 완료와 잠정 push를
구별한다. 빈 push는 clean으로 판정하지 않는다. 프로젝트 전체 인덱스 완료와 rename은 보장하지
않는다. 응답 없음/잘못된 응답/실행 파일 또는 안전한 파일 읽기 기능 부재는 미검증이다.
세션 기록은 비신뢰 데이터이며 스트리밍 탐색의 파일·디렉터리·항목·읽기·시간 예산에 걸리면
truncation 이유를 표시한다. 정책 상수는 도구가 소유하며 검색 결과 0건은 전수 검색 증명이 아니다.

## 출처와 라이선스

OMO의 방법론/기능 구성을 참고했으며 Python 도구와 한국어 참조는 hiway에서 독립 구현했다.
OMO 런타임·바이너리·에이전트 프롬프트를 복사하거나 재배포하지 않는다.
상류는 [MIT License, Copyright (c) 2026 Yeongyu Kim](https://github.com/code-yeongyu/lazycodex/blob/75b017473c71d669dd9aed0a10e950e70724b283/LICENSE)이다.

로컬 마이그레이션의 백업·실행 결과는 계획 문서의 검증 결과에 기록한다. 공개 릴리스는 별도다.
