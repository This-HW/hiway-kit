---
name: code-intel
description: Inspect code structure with AST search, replacement previews, and read-only language-server diagnostics or symbol navigation. Use for structural searches and semantic code questions; use text search for literal strings.
---

# Code intelligence

질문에 맞는 가장 작은 도구를 쓴다. 문자열·파일명은 `rg`, 호출/선언의 모양은 AST,
정의·참조·타입 오류는 언어 서버다. 전체 저장소를 덤프하지 않고 관련 경로부터 좁힌다.

호스트에 해당 AST/LSP 도구가 실제로 있으면 그것을 먼저 쓴다. 도구 이름을 추측하지 않는다.
없으면 아래 일회성 CLI를 쓴다. 도구를 자동 설치하거나 전역 설정을 바꾸지 않는다.

`<kit-root>`는 이 SKILL.md의 두 단계 상위 디렉토리다. 프로젝트 cwd에 킷이 있다고
가정하지 않는다. 탐색 규약: `skills/plan-task/references/task-tools-fallback.md` §A.

## 구조 검색과 변경 미리보기

이미 설치된 `ast-grep` 또는 실제 ast-grep인 `sg`를 사용한다(Linux `sg`는 다른 프로그램일 수 있다).
패턴은 정규식이 아니라 해당 언어로 파싱되는 코드다. 셸에서는 `$A`가 확장되지 않도록 단일 따옴표로 감싼다.

```bash
python3 -B <kit-root>/tools/code_intel.py --root . --lang c --pattern 'puts($A);' src/
python3 -B <kit-root>/tools/code_intel.py --root . --lang c --pattern 'puts($A);' --rewrite 'log($A);' src/
```

변경 명령도 **미리보기만** 반환한다. 파일/일치 수와 replacement를 읽은 뒤 기존 편집 도구로
검토한 범위만 바꾸고 프로젝트 검증을 실행한다. `--limit`은 출력 항목 수만 줄인다. 전체 조회가
너무 크면 경로를 좁힌다. 0건은 잘못된 언어/패턴일 수도 있으므로 알려진 양성 사례와 먼저 대조한다.

## 언어 서버 조회

```bash
python3 -B <kit-root>/tools/lsp_query.py diagnostics --root . --file src/main.c
python3 -B <kit-root>/tools/lsp_query.py definition --root . --file src/main.c --line 12 --column 8
python3 -B <kit-root>/tools/lsp_query.py references --root . --file src/main.c --line 12 --column 8
python3 -B <kit-root>/tools/lsp_query.py symbols --root . --file src/main.c
```

입력 행/열은 1부터 세는 Unicode 문자 위치다. 출력 range는 원래 LSP의 0-based UTF-16 위치다.
자동 탐색은 C/C++·Python·JS/TS·Rust·Go의 설치된 서버만 찾는다. 다른 서버는
`--server <실행파일> --server-arg=<인자>`로 명시한다. 프로젝트의 빌드 설정이 있어야 의미 분석이
정확하다. 서버가 지원하지 않는 요청은 실패로 보고하고 텍스트 검색/프로젝트의 타입 검사로 돌아간다.

진단은 `publishDiagnostics`를 받는 서버를 대상으로 한다. pull-only 서버나 응답하지 않는 서버를
"오류 없음"으로 간주하지 않는다. rename/applyEdit는 수행하지 않는다. 일회성 프로세스이므로
대형 프로젝트의 인덱스 준비 전에 참조가 불완전할 수 있다. 공개 API 변경은 테스트·컴파일로 함께 검증한다.

## 결과 판정

| 종료코드 | 의미 |
| --- | --- |
| 0 | 조회 성공, 진단이면 보고된 오류 없음 |
| 1 | 언어 서버가 오류 진단을 보고함 |
| 2 | 경로/패턴/프로토콜/시간 제한 오류 — 미검증 |
| 3 | 실행 파일 없음 — 미검증, 설치 요청을 반복하지 않는다 |

진단이 비어도 프로그램 동작이 검증된 것은 아니다. 정상 파일과 의도적으로 깨진 파일의
음성 대조를 통해 서버가 실제로 작동하는지 확인한 뒤 프로젝트의 테스트를 실행한다.
