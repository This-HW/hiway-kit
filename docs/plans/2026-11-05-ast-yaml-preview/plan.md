---
title: "JSON 형식 AST 규칙 preview와 snapshot 없는 rule-test"
status: current
execution_status: in-progress
as_of: 2026-11-05
created: 2026-11-05
size: medium
---

## 요구사항

[confirmed: 사용자 위임 + plan-control A/B/C 수용·채택 합의, 2026-11-05]
남은 OMO 후보 중 문맥 AST 규칙을 먼저 도입한다. 기존 code-intel에 JSON 형식으로 명시한 AST 규칙의
preview와 rule-test를 추가한다. 소비자 원본을 적용·수정하지 않으며 OMO runtime/helper를
가져오지 않는다. 작업공간 sgconfig 자동 로딩·커스텀 parser·규칙 자동 발견을 하지 않는다.
고정점 반복 횟수와 미수렴을 보고하고 snapshot 생성/갱신을 사용하지 않는다.
검토 후 편집은 기존 편집 도구로 수행하며 프로젝트의 실행/테스트가 필요하다고 안내한다.
외부 apply 도구는 실패 종료에도 부분 수정이 남을 수 있음을 설명한다.

[researched: 후속 합성 Python/TypeScript fixture의 worker + 부모 재현, n=2]
단순 치환에는 문법 오류·이름 가림 오탐이 있었고 YAML 문맥 가드가 이를 줄였다.
고정점은 의미적 정답을 뜻하지 않으며 import를 바꾼 뒤 조건이 소실되는 규칙은 잘못된 결과로
수렴할 수 있다. 증거 식별자: followup-2026-11-05/parent-serial-20261105T052352Z.
모델 토큰 절감·실프로젝트 전체 품질 개선은 미측정이다.

[researched: 현재 tools/code_intel.py·bounded_process.py·intel_runtime.py, n=1 트리]
기존 pattern CLI는 명시적 빈 설정·중립 cwd·고정 실행파일·필터 환경·공유 프로세스 예산을
쓴다. 기존 CLI 출력/종료 계약을 보존하며 새 모드만 확장한다. Python 소비자 하한을 유지한다.

공식 근거: [CLI 설정 탐색](https://ast-grep.github.io/reference/cli.html),
[scan](https://ast-grep.github.io/reference/cli/scan),
[test와 snapshot 생략](https://ast-grep.github.io/reference/cli/test),
[JSON replacement 출력](https://ast-grep.github.io/guide/tools/json).
웹 문서는 현재 계약 참고이며 설치 엔진의 실제 CLI 검증을 대신하지 않는다.

### 사용자 여정·범위

1. 신뢰한 프로젝트에서 inline JSON 규칙과 대상 파일/디렉터리를 명시한다.
2. snippet 양성/음성 rule-test를 실행한 뒤 preview를 요청한다.
3. 최종 diff·반복/수렴·잘림·원본 해시를 검토한다. no-match도 양성 사례로 도달 확인한다.
4. 별도 편집 도구로 필요한 변경만 적용하고 프로젝트 테스트/실행으로 의미 보존을 확인한다.

권한: omo_test 내 개발·로컬 synthetic 시험과 plan-control 검수는 승인됨.
실 홈 설정·인증 변경, 설치/다운로드, 소비자 프로젝트 원본 쓰기는 범위 밖이다.
main merge/tag/push는 plan-control의 검수·배포 절차에서만 수행한다.
Medium 확장으로 별도 Large brainstorming은 생략한다. Task API가 없어 계획 원문과
개발 checklist를 추적 수단으로 사용한다.
문서 지위는 저장소 스키마의 `status: current`, 실행 상태는 기존 계획 관례의
`execution_status: in-progress`로 구분한다. 완료 판정 전에는 실행 상태를 바꾸지 않는다.

## 결정

### 확정 CLI·결과 계약 (plan-control D1–D5)

- 기존 `--lang --pattern [--rewrite] paths...` 경로는 그대로 유지한다.
- 새 `--rule-json '<JSON>' [--max-passes N] paths...` 모드는 원본 무쓰기 preview다.
  object 또는 비어 있지 않은 object array만 받는다. `--rule-json -`는 bounded non-TTY
  stdin에서 같은 형식을 받는다. YAML 원문·규칙 파일 경로·프로젝트 config는 받지 않는다.
  기존 pattern/lang/rewrite와 혼용하면 입력 오류다. 미출시 `--rule-yaml` 별칭은 만들지 않는다.
- stdlib JSON 파서는 object_pairs_hook으로 중복 키를, parse_constant로 NaN/Infinity를
  거부한다. id는 비어 있지 않은 문자열이며 안전 문자셋 전체 일치, 중복 id는 rc2다.
  각 object를 canonical json.dumps로 직렬화하고 `\n---\n`으로 연결해
  `--inline-rules=<생성한 문서 스트림>`으로 전달한다. 배열을 native에 직접 넘기지 않는다.
- 최상위 키 허용목록: `id`, `language`, `rule`, `constraints`, `fix`, `message`,
  `severity`, `note`, `metadata`. 나머지는 rc2 `unsupported_key`다. `utils`, `transform`,
  `rewriters`, `files`, `ignores` 등은 검증과 함께 후속 확장한다. native 의미 검증은 별도로
  수행하며 JSON 구조 검사가 그것을 대신하지 않는다. inspect ID 교차확인은 제품에 넣지 않는다.
- fix는 문자열 또는 `{template: 문자열}`만 지원한다. expandStart/expandEnd는 입력 단계에서
  rc2 `unsupported_fix_expansion`으로 거부한다. no-fix 규칙은 매치 목록을 보고하며
  바이트 변경이 없으면 changed_passes=0, rc0이다. 선언된 fix가 있는데 replacement 또는
  replacementOffsets가 없으면 `schema_mismatch`이고, no-fix일 때만 그 필드 부재를 허용한다.
- 새 `--rule-json '<JSON>' --rule-tests-json '<JSON>'`은 rule-test다.
  테스트 JSON은 `[{"id":"rule-id","valid":["..."],"invalid":["..."]}]`이며 정해진 키·문자열
  목록만 받는다. 각 항목에 양성·음성 사례가 있어야 한다. ID를 경로로 사용하지 않는다.
  대상 경로·max-passes와 혼용하지 않는다. JSON에서 확정한 모든 rule id와 테스트 id가
  정확히 대응해야 한다. 빠진 규칙은 rc2 `untested_rule`, 알 수 없는 테스트 id도 rc2다.
  중복 id·빈 사례·실제로 실행된 사례 없음은 통과로 처리하지 않는다.
- rule-test는 임시 고정 이름의 규칙/사례 파일과 생성 config만 사용한다.
  `--skip-snapshot-tests --include-off`를 항상 지정하고 `--update-all/-U/--interactive`를
  전달하지 않는다. 출력의 id별 PASS/FAIL·사례 수를 입력과 대조한다.
  `Configuration not found!`, SKIP, 0 tests, 형식 불명은 rc2다.
  native test pass는 매치/비매치 계약이며 치환 출력·실행 결과의 검증이 아니다.
- 새 모드의 JSON에는 기존 notice/environment 외에 mode, engine_version,
  tested_version, source_sha256, files_copied, iterations, changed_passes, converged,
  stop_reason, truncated를 둔다. engine_version이 tested_version과 다르면 버전 차이 notice를
  한 줄 추가하되 버전 차이만으로 거부하지 않는다.
  preview에는 최종 diff와 파일별 변경 요약, rule-test에는 실행·성공·실패 사례 수를 둔다.
  모드에 해당하지 않는 필드는 생략한다. 원본 내용·규칙 메시지는 비신뢰 데이터다.
- 새 모드 rc: 0=preview 계산 수렴 또는 실행된 rule-test 전부 일치;
  1=실행된 rule-test 기대 불일치; 2=입력/경로/엔진 오류·예산 초과·미수렴·판정 불가;
  3=설치 엔진 부재/새 모드의 최소 지원 버전 미만. 기존 pattern 모드 분류는 유지한다.
  실행 중 사용자 대기를 만들지 않고 종료 시 모든 자식을 정리한다.

### 모의 반복·입력 경계

- 원본을 bounded FD 기반으로 읽어 private temp 안에 상대 경로 구조를 복제한다. 상위 루트
  FD를 고정하고 하위 심링크·비정규 파일·경계 이탈을 거부한다. 디렉터리 열거·파일 읽기 모두
  예산 적용, 원본/복사본 해시 대조와 종료 시 원본 변경 검출을 한다. 원본이 외부에서 바뀌면
  rc2 `source_changed`이며 다른 프로세스의 변경을 복원하지 않는다.
- `scan -c <neutral> --inline-rules=<생성 문서> --json=compact`에 caller id마다
  별도 argv `--hint=<id>`를 반복하고 경로 앞에 `--`를 넣는다. 모든 사용자 규칙을 hint로
  활성화해 error/off severity가 preview rc·대상 집합을 바꾸지 않게 한다. 인자 없는
  `--hint`는 내장 suppression 규칙까지 활성화하므로 사용하지 않는다.
  임시 사본만 스캔하며 engine apply 플래그도 사용하지 않는다. 사본 scan은
  `--no-ignore hidden --no-ignore dot --no-ignore vcs --no-ignore parent
  --no-ignore global --no-ignore exclude`를 사용하여 복사 집합과 조회 대상 집합을 일치시킨다. 엔진 JSON의 replacement와
  replacementOffsets를 검증해 사본 바이트만 재구성한다. UTF-8 경계·범위·파일 대응·현재
  바이트 해시를 검증한다. 매치마다 `bytes[range.byteOffset] == text.encode(UTF-8)`를
  확인하고 replacementOffsets가 그 범위 안이며 UTF-8 경계인지 검사한다. 필드 누락/형식
  이탈은 rc2 `schema_mismatch`다. 엄격 중첩은 규칙이 같든 다르든 바깥 우선으로 선택하고
  안쪽은 다음 pass에서 처리한다. 파일별 replacementOffsets를 start 오름차순·end 내림차순으로
  정렬한 뒤 비겹침 편집을 선택한다. 다른 규칙이 동일 범위를 바꾸면 native 승자를 추측하지 않고
  rc2로 거부한다. 부분 교차 범위 등 AST 기대 형태를 벗어난 결과도 schema_mismatch다.
  모든 scan 결과의 ruleId는 caller id 집합에 속해야 하며 밖이면 rc2 `schema_mismatch`다.
  내장 규칙과 caller id의 동일명 충돌은 실측하며, 출력이 어느 규칙인지 구분할 수 없으면
  rc2 `reserved_rule_id`로 입력 단계에서 거부한다. 예약 이름 목록은 테스트한 엔진 버전의
  근거와 함께 둔다. 작업자 ast-grep 0.51.0 실측에서 `no-suppress-all`과
  `unused-suppression`이 같은 ruleId로 사용자/내장 결과를 함께 출력해, 두 이름을 예약한다.
  부모 통합 검증에서 해당 회귀를 재실행한다. 내장 결과 행을 이름 목록으로 걸러 성공 처리하지 않는다.
  집합 검사는 미래 내장 규칙의 집합 밖 혼입은 거부하지만, 미래의 새 내장 이름이 caller id와
  같은 경우까지 구분을 보장하지 못한다. 이 한계를 검증 버전 안내와 함께 유지한다.
  매치 수를 출력 limit으로 자른 뒤 교체 계산하지 않는다.
- 전체 대상의 현재 바이트 상태가 바뀌지 않을 때만 고정점이다. 결과 해시가 과거 상태로
  돌아오면 cycle, 제한 도달은 pass_limit으로 rc2를 반환한다. 이때 stop_reason·iterations·마지막 pass 변경 파일 목록은 남기지만
  성공 diff는 내지 않는다. iterations는 scan 횟수,
  changed_passes는 실제 바이트가 바뀐 횟수로 구분한다. no-match/동일 치환은 changed_passes=0.
  수정 없는 확인 scan도 예산에 포함하며 한도 마지막 변경 직후를 수렴이라고 하지 않는다.
- JSON 형식 규칙은 native parser로 의미 검증하며 OMO 정규식 휴리스틱을 도입하지 않는다. 임시 config는
  코드가 정한 ruleDirs/testConfigs만 포함한다. caller 규칙을 config로 해석하지 않는다.
  workspace/상위/임시 부모 sgconfig·사용자 설정·커스텀 native parser를 로딩하지 않는다.
- 사본 바이트에서 `ast-grep-ignore` 문자열이 발생하는 파일 수를 notice로 보고한다.
  파일 무시 설정을 꺼도 소스 주석에 의한 매치 억제는 남으므로 no-match 해석에 반영한다.
- 격리는 사용자 호스트의 책임이라는 기존 설명을 유지한다. preview 무쓰기는 helper의
  원본 파일 처리 계약이며 신뢰한 엔진 자체에 대한 OS sandbox 보증이 아니다.

### 정책값 SSOT (승인됨)

| 키 | 값 | 근거 |
|---|---|---|
| minimum_rule_engine / tested_version | >=0.51.0 / 0.51.0 | [confirmed: plan-control R1]; 최신 버전은 매치별 의미·스키마 검증으로 지원 |
| python_floor | 3.9 | [confirmed: 저장소 소비자 계약] |
| max_passes_default / max | 8 / 32 | [confirmed: plan-control 정책값 승인, 구현 상수화] |
| max_files / max_source_bytes | 200 / 8MiB | [confirmed: plan-control 정책값 승인] |
| max_file_bytes / max_rule_bytes / max_cases_bytes | 1MiB / 64KiB / 256KiB | [confirmed: plan-control 정책값 승인] |
| max_directory_entries / max_depth | 20,000 / 64 | [inferred: 구현 P3 자원 방어값]; 빈 디렉터리 열거와 FD 소진도 실패로 제한, 문서에 명시 |
| timeout / probe / combined_output | 기존 QUERY_TIMEOUT / PROBE_TIMEOUT / MAX_OUTPUT_BYTES 재사용 | [confirmed: 현재 ProcessBudget 상수] |
| rule_id_charset | `[A-Za-z0-9][A-Za-z0-9_.-]*` 전체 일치 | [confirmed: D1 안전 문자셋 요구; P3 ASCII 식별자 구체화, 길이는 rule byte budget 적용] |
| display_limit | 기존 --limit 계약 재사용 | [confirmed: 현재 CLI] |
| product_version | 5.7.0 | [researched: release-process의 신규 기능 minor 규칙, n=1 문서]; 출시 시 상류 대조 |

모든 pass와 probe는 하나의 ProcessBudget 절대 deadline을 공유한다. pass마다 시간을
초기화하지 않으며 전체 deadline 초과는 rc2 `budget`이다. stdin에도 max_rule_bytes를 적용한다.
예산은 입력·중간 사본·출력에 적용한다. 초과 시 일부 결과를 성공으로 돌려주지 않는다.
정책 상수는 규칙 모듈이 소유하고 기존 예산을 복제하지 않는다.

### 모호함 탐색·승인 포인트

- 상태 전이: no-match/고정점/주기/한도/출력 잘림/원본 동시 변경을 분리했다.
- 충돌: 엄격 중첩은 규칙 무관 바깥 우선, 다른 규칙 동일 범위는 거부한다. test pass와
  변환 결과 검증을 합치지 않는다.
- 경계 등호: byte/file/pass 상한 자체는 허용하되 추가 필요 시 rc2, 최종 확인 scan 포함.
- 실패 복원: 원본 쓰기 없음. 임시 사본 폐기만 하며 원본 외부 변경은 되돌리지 않는다.
- P0 경계는 원본 무쓰기·설정 자동 발견 금지로 이미 합의됨. 위 CLI·모의 반복·정책값은
  plan-control R1–R5·S1–S3와 실측 후 D1–D5 결정으로 확정했다.
  native 중첩과 rule-id 대응 메커니즘은 조사 산출물 및 부모 재현으로 확인했다. 범위 축소나 보안 경계 변경은 재합의 없이 하지 않는다.

### 사전 조사 수용·확정 근거

[researched: native-contract worker 독립 재현 및 부모 fresh, n=3]
동일/다른 규칙의 엄격 중첩을 포함한 fixture에서 바깥 우선 시뮬레이션은 native 적용과
pass별·최종 바이트가 일치했다. 원래 Python v1/v2는 모두 성공 차분 대상이고,
v1의 의미적 실행 실패는 고정점/차분 성공과 구별한다. 다른 규칙 동일 범위는 거부 대조군이다.
expand fix는 replacementOffsets가 range 밖이므로 이번 지원 대상에서 제외했다.
native ID 전량 목록은 비구조화 inspect 출력으로 얻지만 안정된 JSON 스키마가 아니어서
제품에서는 사용하지 않는다. strict JSON 입력으로 ID를 정확히 얻고, 엔진에는 문서별 JSON을
직렬화해 전달하는 방식이 실제로 동작했다. native test가 여러 누락을 rc0으로 끝내므로
입력 집합·출력 사례 수 검증과 include-off를 필수로 확정했다.
부모 experiment/verify/selftest rc0, 검증 179/179와 결함 주입 대조는 별도 원기록에 보존한다.
하네스 auto-format의 ruff 실행 관측은 원기록에 보존했다. 이후 plan-control은 킷 자체 훅이
킷 코드에 ruff/pytest를 실행하는 것은 정상 개발 경로이며 안전 예외가 아니라고 수용 기준을 정정했다. 프로젝트 밖 proof .py에도
훅이 동작한다는 관측은 이번 범위 밖 후속 메모이며 소비자 영향은 아직 판정하지 않았다.
후속 worker 파일 작성은 heredoc/patch 방식, lint 실행은 명시적 sandbox를 쓰고 훅 설정은 바꾸지 않는다.
구현 worker는 수정 전 설치 Stop 훅의 격리 밖 테스트 실행 가능성을 발견했다. 이를 피하기 위해
기준 커밋의 proof 사본에서만 구현·검증하고 원래 worker 워크트리는 clean을 유지한다.
검증한 사본에서 패치·파일 해시를 반환받아 부모가 통합·재검증한다. 제품 계약은 동일하다.

### 독립 검수 후 보강 결정 (2026-11-05)

[confirmed: plan-control 독립 검수 협의]
초기 코드 리뷰 ACCEPT(C0/H0/M3/L6), 보안 검토 C0/H0/M0/L3를 받았으나,
부모 재현으로 확인한 계약 결함을 릴리스 전에 보강한다. 검수 보고는 정적 판단과 실측을
구분한다. 이모지·DEL·U+2028 직렬화 거부 가설은 ast-grep 0.51.0의 preview/test에서
모두 rc0으로 반증했으므로, 그 가설만으로 직렬화를 변경하지 않고 실제 엔진 회귀를 추가한다.

- 최종 diff도 동일한 절대 deadline·누적 출력 예산 안에서 계산한다. `sys.executable`
  `-I -S -B`와 `__file__` 기준 플러그인 helper를 사용하며 stdlib만 불러온다.
  한도 검증된 private 사본을 입력으로, stdin DEVNULL·neutral cwd·같은 ProcessBudget으로
  실행한다. 실패는 rc2 budget이며 일부 diff를 성공처럼 반환하지 않는다. 새 줄수 상한은 없다.
  diff 행은 LF로만 나누고 No newline 표시는 실제 마지막 행에만 붙인다.
- 사본 쓰기도 사본 루트 FD 고정·하위 디렉터리별 NOFOLLOW openat·최초 dev/ino 대조로
  보호한다. 파일은 openat으로 쓰고 같은 FD에서 즉시 readback 해시를 대조한다.
  pass 사이 하위 디렉터리를 원본 심링크로 교체해도 원본 sha 불변·rc2여야 한다.
- 순회 및 명시 경로에서 strict UTF-8 파일명 실패는 rc2 unsupported_file_name으로
  거부하고 이름은 ascii()로 표현한다. 출력 인코딩 실패도 rc2 internal_error JSON이다.
  실제 비 UTF-8 파일명은 APFS에서 생성 불가였으므로 Linux CI의 필수 회귀로 검증한다.
- 규칙 scan의 빈 stdout은 schema_mismatch다. 실제 JSON 빈 배열만 no-match로 인정한다.
- 단일 argv의 플랫폼 한도는 입력 한도와 별개일 수 있다. 직렬화 변경은 실제 엔진 근거가
  있을 때만 선택하고, 한도 오류를 설치/엔진 문제로 오분류하지 않는다.

독립 검수의 나머지 LOW/Info는 재현·조치 여부를 최종 결과에 명시한다. 작성자와 검수자는
별도 세션이지만 구현 및 최종 검수 모델 계열이 같다는 한계는 유지한다.

### 후속으로 이월 (이번 구현 제외)

- 네이티브 LSP 우선 안내는 별도 작은 변경으로, 상주 daemon 설계 전에 일회성
  background-index + 실제 `$/progress end` 대기를 실측한다. daemon ping은 readiness가 아니다.
  clangd의 소비자 `.cache/clangd/index` 쓰기를 고려해 사용자 캐시/opt-in 정책부터 설계한다.
- 기존 설치 Playwright만 사용하는 P2 browser, 코드로 캡처 freshness 확인,
  listener+DOM assertion+diffRatio/hotspot. similarityScore·CLS 단독 게이트 금지, trace 선택.
- rename 자동 적용은 snapshot/rollback·충돌 검사·적용 후 빌드 설계 전 보류.
- OMO daemon·omowright 재도입 없음. MCP proxy/PostToolUse, 다운로드, 대형 프로젝트·idle,
  실사용 로그인 사이트는 미검증을 유지한다.

## 구현 계획

1. 사전 native 계약 조사·부모 재현·D1–D5 plan diff는 plan-control 확인 및 구현 착수
   승인을 받았다. 추가 경계 변경은 재합의한다.
2. `tools/code_intel.py`에 상호 배타적 모드 분기, `tools/code_intel_rules.py`에 JSON 형식 규칙 실행,
   bounded snapshot·모의 반복·test 입력/출력 검증을 구현한다. 기존 ProcessBudget와
   실행파일/PATH/environment 경계를 재사용하고 기존 pattern 동작은 바꾸지 않는다.
   파일/모듈 규모가 판정 범위를 넘으면 재설계 검수한다.
3. `tests/hooks/test_code_intel_rules.py` 및 필요한 기존 CLI 회귀에 테스트를 추가한다.
   synthetic engine으로 경계/실패를, 설치된 실제 엔진으로 규칙 의미·고정점·rule-test를 확인한다.
   실 엔진 미설치/하한 미달은 실제 검증을 skip-green으로 보고하지 않는다.
   같은 Python/TypeScript v1·v2 fixture에 대해 테스트 임시 사본에서만 native `scan -U`를
   고정점까지 실행하고 시뮬레이션의 최종 바이트와 차분 일치를 필수 검사한다. 중첩 호출의
   pass별 결과도 기록한다. native와 동일한 잘못된 결과도 의미 검증 성공으로 포장하지 않는다.
4. code-intel SKILL에 예시·반복 의미·rule-test 한계·실행 검증·부분 수정 경고를 추가한다.
   신규 skill은 만들지 않는다. 기존 skill CLI eval에 양성/음성 계약 노드를 추가한다.
   description 변경이 필요하면 선택 eval 범위를 plan-control과 확정한다.
5. 독립 review-code/security-scan·되돌려-FAIL·소비자 임시 설치 확인 후
   `scripts/bump-version.sh`로 정책표 버전을 반영하고 CHANGELOG를 작성한다.
   행동 변경 커밋은 버전 bump와 함께 하며 매니페스트 생성물을 손으로 편집하지 않는다.
6. fresh 완료 게이트 및 행동 eval 결과를 frozen HEAD와 함께 plan-control로 보낸다.
   조사용 브랜치로 Claude 디렉토리 Validate를 먼저 돌려 새 도구 귀속 보류가 없는지 확인한다.
   현재 진행 중인 이전 릴리스 심사는 main 재스캔으로 대체될 수 있으므로 main push 시점은
   그 판정 상태를 보고 plan-control이 정한다. 구현·검수는 기다리지 않고 진행한다.
   검수본과 배포 plugins 트리 동일성·fresh gate를 확인한 뒤 plan-control이 배포를 진행한다.
   docs/marketplace-submission.md는 건드리지 않는다.

## 완료 조건

사전 조사와 작업자 구현을 수용했다. 부모 통합·검증 및 독립 리뷰를 진행 중이며 아래 신규 노드를 제공한다.
서드파티/피시험 코드(OMO 등)의 실측은 읽기/쓰기/네트워크 격리한 synthetic proof에서
수행한다. 킷 자체 Stop/auto-format 훅의 킷 코드 대상 ruff/pytest는 정상 개발 경로다.
개발 중 sandbox 결과는 보조 증거이며 환경 실패를 최종 통과로 대체하지 않는다. 통합 후
frozen HEAD에서 일반 환경의 fresh 전체 완료 게이트 rc0를 최종 수용 근거로 쓴다.
실 auth 파일은 복사·이동·심링크하지 않는다. git 훅은 우회하지 않고 커밋도 허용된
워크트리와 git metadata에만 쓰도록 sandbox에서 수행한다.

| 검증 | 실행 명령·판정 |
|---|---|
| 기능·기존 회귀 | `python3 -B -m pytest tests/hooks/test_code_intel_rules.py tests/hooks/test_code_intel.py tests/hooks/test_skill_cli_contracts.py -q` → rc0 |
| 실제 native 기능 (engine 필수, skip 금지) | `HIWAY_REQUIRE_AST_GREP=1 python3 -B -m pytest tests/hooks/test_code_intel_rules.py -k real_engine -q` → rc0; 선택 노드 수와 skip0 확인 |
| 안전 경계 | `python3 -B -m pytest tests/hooks/test_code_intel_rules.py -k boundaries -q` → rc0; 원본/플러그인 트리 무쓰기, 설정 미로딩, 경로/교체범위/자원/프로세스 계약 |
| rule-test 양성/음성·빈 실행 | `python3 -B -m pytest tests/hooks/test_code_intel_rules.py -k rule_tests -q` → rc0; 의도 불일치 rc1, 형식 오류/0case rc2 |
| Python 소비자 하한 | 설치된 Python3.9와 3.12에서 문서화된 `python -B <kit-root>/tools/code_intel.py …`를 동일한 제한 환경으로 실행해 CLI 계약·py v2 native 차분·동일범위 거부·사본 심링크 교체·diff budget의 rc/JSON을 비교한다. pytest 설치 없이 계약 함수를 호출하며 원문 보존. CI `python39-compat` green은 별도 모듈 load smoke로만 판정한다 |
| 스킬 계약·기존 gate 불변 | `python3 scripts/check_skill_eval_coverage.py` → rc0; agent coverage 게이트와 통합하지 않음 |
| 문법/스타일 | `ruff check plugins/common/tools/code_intel.py plugins/common/tools/code_intel_rules.py tests/hooks/test_code_intel_rules.py` → rc0 |
| 릴리스 완료 | 통합 frozen HEAD에서 일반 환경 `scripts/verify-done.sh` → fresh 전체 rc0(bounded_process 포함), 출력 원문 보존; gate는 checklist 항목에 넣지 않음 |
| 행동 회귀 | `scripts/run-evals.sh` → rc0; 실행 불가·시간 초과를 통과로 해석하지 않음 |

회귀 필수: 양성 no-match 대조, strict JSON/허용 키/언어 오류, 동명 member/comment/string 보호,
Python/TS 실행 결과 fixture, 수렴·cycle·한도·원본 동시 변경, UTF-8 교체범위,
동일·교차 규칙 엄격 중첩 성공과 다른 규칙 동일 범위 거부, 경로 심링크/교체/탈출·FIFO, 작업공간 PATH 실행 거부,
sgconfig/custom parser marker 실행 없음, snapshot 생성/갱신 없음, ignore 주석 notice,
error/off severity와 zero/unknown test 거짓 성공 거부, caller별 `--hint=<id>`의 실 엔진
매치 파일 집합 동일성(전 규칙 활성 대조 포함), 경로 소비 방지, 내장 규칙 혼입·예약 ID 충돌,
중간 결과 폭증/시간 초과/자식 잔존 없음. 되돌려-FAIL은 scratch에서 생산 변경만 base로
되돌려 새 양성/음성 계약이 실패함을 보존하며 실제 작업 브랜치는 되돌리지 않는다.

독립 검수·소비자 probe·수동 항목은 구현 뒤 `검증 결과`에 명령/rc/증거 경로로 기록한다.
수동 attest: 모든 요구사항·문서·미검증 이월·자원 정리·배포 트리 대조.

## 검증 진행 기록

[confirmed: 부모 일반 환경 실행, 2026-11-05]
- 최초 패치 해시·기준 파일·모드와 적용 가능성을 대조한 뒤 기능·기존 CLI 208개 통과.
- 독립 코드/보안 검수의 재현 가능한 지적을 반영한 delta도 해시·적용 검증 후 통합했다.
  부모 D1: 244 passed / 1 skipped(APFS 비 UTF-8 파일명), D2: 실제 엔진 25 passed / skip0,
  D3: 스킬 계약 13개 노드 등록 검사 rc0. ruff는 변경 Python 파일 전부 rc0.
- 작업자 결함 되돌림 대조는 새 노드 29개 실패. 부모 subprocess CLI 대조는 최초 구현을
  되돌리면 신규 계약 3개 모두 실패했다. 합성 결과와 실제 엔진 차분 근거는 분리한다.
- 실제0.51.0에서 이모지/DEL/U+2028 규칙·snippet은 동작했다. 직렬화 오류 추론을 반증해
  직렬화 자체는 변경하지 않고 실제 엔진 회귀를 추가했다.
- 아직 미결: 수정 delta 독립 재검수, frozen HEAD fresh 전체 게이트, 행동 eval, 소비자
  패키지 probe, Linux 파일명·argv 분기 CI 및 Python3.9 CI. python39-compat job은 모듈
  로드 smoke이며 pytest3.9 전체 실행과 구분한다. main/태그/push와 디렉토리 검수도 미실행이다.

증거 묶음 식별자: ast-yaml-2026-11-05/parent-integration 및 implementation/review-fix-deliver.
계획은 in-progress를 유지하며 기계 게이트·독립 판정·배포 절차 완료를 미리 주장하지 않는다.

### 수정 delta 독립 재검수

[confirmed: 별도 세션 정적 검수 보고, 2026-11-05]
코드 리뷰 ACCEPT(C0/H0, 신규 LOW5), 보안 검수 C0/H0/M0, 신규 LOW1. 이전 출력 인코딩,
사본 쓰기, diff deadline, LF 분할, 빈 출력, argv 한도 지적은 조치됨으로 판정했다.
코드 실행·Linux 분기·3.9 런타임·배포물 대조를 검수 보고만으로 검증됐다고 하지 않는다.

비차단 잔여는 별도 후속으로 유지한다: (1) LF/제어문자 파일명의 diff 헤더 인용 미지원,
(2) 내부 diff JSON의 ASCII escape가 비ASCII 데이터에서 예산을 더 소비함,
(3) 사본 IO 오류의 copy_changed 분류가 원인을 넓게 묶음, (4) _passes 인자/책임 정리,
(5) 신규 옵션만 단독으로 준 경우 기존 argparse의 필수 옵션 메시지가 먼저 나옴.
원본 하드링크·사후 검증 사이 일시 변경·미래 내장 rule id 충돌·출력 표시 위치 대조의
한계도 기존 기록대로 유지한다. 자동 apply는 제공하지 않으며 최종 diff만으로 의미적
정답을 주장하지 않는다. 이번 수정 후 새 기능이나 정책 완화를 추가하지 않는다.

Python3.9 검증은 load smoke만으로 닫는다는 이전 판정을 정정했다. 문서화된 호출
(`-B`, `-I` 없음)과 비운 환경·가짜 HOME·제한 PATH로 두 버전을 대조했다.
`-I` 직접 실행의 sibling import 실패는 문서화된 호출이 아니므로 제품 결함으로 분류하지 않는다.

### Python 런타임 대조와 최종 게이트 보정

[confirmed: 부모 실측 및 plan-control 합의, 2026-11-05]
Python3.9.25/3.12.13에서 D3 13함수·19 CLI 호출, native v2 차분, 동일 범위 거부,
사본 심링크 교체 거부, 30초 diff 예산 모두 기대 rc·원본 해시·자식 정리에 일치했다.
이것은 pytest3.9 전체 실행이나 Linux 분기 검증을 대체하지 않는다.
첫 ordered 비교는 matches 순서만 달라 실패했다(원기록 보존). 같은 버전 반복에서도
8회 모두 순서가 달랐고 중복을 보존한 multiset 비교는 일치해 런타임 호환 근거로 수용했다.
표시 부분집합이 달라지는 결함은 이번 릴리스에서 수정한다: 검증된 matches를 상대경로
UTF-8 바이트·시작/끝 byteOffset·ruleId 순으로 정렬한 뒤 limit를 적용한다.
합성 엔진의 반전·회전 순서와 실제 엔진 3회 반복을 회귀로 고정한다.
기존 pattern 모드 순서는 이번 변경 밖이며 비결정성 여부를 후속 확인한다.

첫 일반 환경 fresh gate는 pytest 2376 passed지만 문서 검사 두 곳에서 rc1이었다.
새 TypeScript fixture로 활성화된 기존 소비자 예시 3개만 정확한 문서·경로 쌍 예외로
등록하고, 같은 문서의 다른 경로와 다른 문서의 같은 경로는 계속 실패함을 확인한다.
문서 지위와 실행 상태는 기존 계획 관례대로 분리한다. 검사기 스키마는 바꾸지 않는다.
아직 배포하지 않은 초안 커밋은 로컬 증거 ref로 보존하고 5.7.0 단일 행동 변경 커밋으로
amend하기로 합의했다. 새 frozen HEAD의 fresh 전체 게이트·행동 eval·독립 최종 판정은
이 변경 뒤 다시 수행하며, 통과하기 전 완료나 릴리스 준비를 주장하지 않는다.
