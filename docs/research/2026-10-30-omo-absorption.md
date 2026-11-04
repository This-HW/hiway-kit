---
status: current
as_of: 2026-10-30
---

# OMO 기능 감사와 hiway-kit 통합

2026-10-30. 대상: OMO 5.1.48, hiway-kit 5.5.1 → 5.6.0. 설치본의 27개 스킬 설명/진입점,
16개 컴포넌트 계약과 관련 구현을 확인했다. 전체 의존성의 모든 코드를 줄 단위 감사했다는 뜻은 아니다.
상시 프롬프트·프로세스 증가 없이 실제로 필요한 기능을 유지하는 것이 선택 기준이다.

## 근거와 범위

- [고정 OMO 소스](https://github.com/code-yeongyu/lazycodex/tree/75b017473c71d669dd9aed0a10e950e70724b283/plugins/omo)
- [스킬 원문](https://github.com/code-yeongyu/lazycodex/tree/75b017473c71d669dd9aed0a10e950e70724b283/plugins/omo/skills)
- [컴포넌트 원문](https://github.com/code-yeongyu/lazycodex/tree/75b017473c71d669dd9aed0a10e950e70724b283/plugins/omo/components)
- 로컬 사전 비교: 동일 모델/effort, 2개 C 과제 × 4조건 × 2반복. 기본/hiway/OMO/동시 사용은
  모두 과제 4/4, 조건당 4,370개 검사 통과. OMO의 평균 입력은 기본의 2.32배, 비캐시 입력은
  3.06배, 시간은 1.15배였다. 작은 과제 표본이므로 복잡한 개발 작업 전체의 품질이나 비용을 일반화하지 않는다.
- 이번 통합은 아래 기능·경계 검증이다. 통합판의 토큰 절감률을 새로 측정했다고 주장하지 않는다.

## 스킬 대응표

| OMO 스킬 | hiway 처리와 이유 |
| --- | --- |
| ast-grep | 새 `code-intel`: AST 검색과 변경 미리보기. 변경 적용은 기존 편집 도구로 검토한다. |
| lsp | 새 `code-intel`: 일회성 diagnostics/symbols/definition/references. |
| lsp-setup | 설치된 서버 탐색과 명시적 명령만 채택. 자동 설치·반복 승인 질문 제외. |
| coding-agent-sessions | 새 `session-history`: 명시적 Codex/Claude JSONL 루트, 제한된 결과. 다른 호스트 DB 리더는 미이식. |
| debugging | 기존 debug에 반증 가능한 가설·양성/음성 대조 참조 추가. |
| review-work | 기존 review에 실제 사용면·증거·현재 소스 대조 참조 추가. |
| visual-qa | review의 UI/PDF 조건부 참조: 크기/테마/넘침/접근성/실제 렌더 확인. |
| programming | review 참조에 프로젝트 버전·타입·에러 처리·실패 가능한 테스트를 반영. 언어 버전 강제 제외. |
| refactor | review 참조에 동작 보존·호출자 범위·회귀 검증 반영. 별도 중복 스킬 제외. |
| remove-ai-slops | review 참조에 검증된 중복/죽은 코드만 정리하도록 반영. 취향 기반 전면 재작성 제외. |
| init-deep | plan-task 탐색 참조에 진입점/규약/검증 소유권 확인 반영. AGENTS.md 대량 생성 제외. |
| ulw-research | web-research에 주장별 출처/반례/표본/측정 조건 참조 추가. 강제 다중 에이전트 제외. |
| browser | 기존 web-research의 호스트 브라우저/Aside 경로 사용. omowright 런타임 미번들. |
| ultimate-browsing | 기존 웹 도구 폴백·접근 불가 명시 사용. 우회 브라우저/로그인 자동화 미번들. |
| frontend | 기존 구현/리뷰 + 조건부 visual QA. 제품 디자인은 해당 프로젝트 규약 사용. |
| data-scientist | 기존 Python/프로젝트 분석 도구 사용. 전용 상주 커널 미번들. |
| git-master | 기존 git-workflow와 프로젝트 브랜치 규율 사용. 기본 조작마다 긴 지침 주입 제외. |
| teammode | 기존 control-loop/child-session 및 호스트 협업 수단. 별도 팀 상태 저장소 제외. |
| ulw-plan | 기존 brainstorming/plan-task. 중복 승인·계획 체인 제외. |
| ulw-execute | 기존 auto-dev/checklist 및 실제 검증 명령. Boulder 상태 저장소 제외. |
| ulw-loop | 기존 loop-engineering의 완료/무진전/실패 가드. 무제한 자동 재진입 제외. |
| ultrawork | 기존 작업 규모 판단·완료 게이트. 전역 성격/모델/노력 수준 강제 제외. |
| rules | 기존 rules/export-harness의 정본/드리프트 검사. 두 번째 룰 주입기 제외. |
| comment-checker | 리뷰에서 필요 없는 주석 판단. 모든 편집의 주석 경고/차단 제외. |
| lcx-doctor | OMO 제품 전용 진단은 제외. hiway verify-done 및 실제 설치 프로브 사용. |
| lcx-report-bug | OMO 제품 이슈 라우팅은 제외. 기존 debug 근거를 해당 소유 저장소에 사용. |
| lcx-contribute-bug-fix | OMO 제품 배포 절차 제외. hiway 릴리스 규약 유지. |

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

LSP는 stdio와 UTF-16, publishDiagnostics를 대상으로 한다. 프로젝트 전체 인덱스 완료,
rename, pull-only 진단은 제공하지 않는다. 응답 없음/잘못된 응답/없는 실행 파일은 미검증이다.
세션 기록은 비신뢰 데이터이며 200파일·파일당16MiB·행당256KiB·세션당5개 발췌로 제한한다.

## 출처와 라이선스

OMO의 방법론/기능 구성을 참고했으며 Python 도구와 한국어 참조는 hiway에서 독립 구현했다.
OMO 런타임·바이너리·에이전트 프롬프트를 복사하거나 재배포하지 않는다.
상류는 [MIT License, Copyright (c) 2026 Yeongyu Kim](https://github.com/code-yeongyu/lazycodex/blob/75b017473c71d669dd9aed0a10e950e70724b283/LICENSE)이다.

로컬 마이그레이션의 백업·실행 결과는 계획 문서의 검증 결과에 기록한다. 공개 릴리스는 별도다.
