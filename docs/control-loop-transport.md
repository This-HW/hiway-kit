# `control-loop` 운송 부록

이 문서는 공통 규범을 실제 실행 환경에 연결하는 레시피다. 규범의 정본은
[`control-loop`](../plugins/common/skills/control-loop/SKILL.md)와
[`parallel-worktree`](../plugins/common/rules/parallel-worktree.md)다.
외부 오케스트레이션·네이티브 subagent·대규모 병렬·단일 세션 경로를 모두 다룬다.

**하네스와 운송은 별개 축이다.** Claude Code·Codex 등은 실행 하네스이고,
Orca 같은 외부 오케스트레이터는 여러 하네스의 작업 전달·상태·수명주기를 관리한다.
외부 도구 이름은 배포물 `plugins/`에 넣지 않는다(G-D6). 이 문서가 있다고 소비자의
설정이 자동 적용되거나 모든 하네스의 실행이 검증된 것은 아니다.

## 1. 수단 선택과 확인

먼저 사용자의 지정, 현재 작업의 권한 소유자, 실제 제공 기능을 확인한다.
설치 파일이나 CLI 이름의 존재만으로 준비 상태를 판정하지 않는다.

| 경로 | 선택 조건 | 먼저 확인할 것 |
| --- | --- | --- |
| 외부 오케스트레이션 | 여러 세션의 감독·추적 또는 사용자가 지정한 계보가 필요 | 버전 일치 가이드, 런타임 상태, 배치 대상의 capability |
| 네이티브 subagent | 해당 하네스가 제공하고 프로젝트가 허용한 독립 작업 | 도구 스키마, 격리, 컨텍스트 전달, 부모 종료 시 수명 |
| 대규모 병렬 | 독립 작업이 많고 사용자가 비용·운영 범위를 승인 | 해당 하네스의 실제 기능, 동시성·깊이·종료 한도 |
| 단일 세션 순차 | 위임이 불필요하거나 허용된 위임 수단이 없음 | 부모가 직접 처리할 권한·범위와 검증 명령 |

일반 작업은 지원되지 않는 수단 대신 허용된 경로로 강등할 수 있다. 그러나 **특정 운송이나
계보가 요구된 작업은 묵시적으로 대체하지 않는다.** 활성 Dispatch가 소유한 작업도
다른 수단으로 중복 실행하지 않는다. 불가하면 상태와 차단 사유를 보고한다.
외부 도구 부재를 이유로 소비자에게 설치를 강제하지 않는다.

모든 경로에서 수정 작업자는 격리하고 읽기 전용 작업은 불필요한 워크트리를 만들지 않는다.
부모는 파일 소유권이 disjoint한 작업만 병렬화하고 공유 파일을 직접 소유한다.

## 2. 외부 오케스트레이션 — Orca 사례

### 가이드와 런타임

설치된 `orchestration`/`orca-cli` 스킬의 CLI 선택 절차를 따른다. 환경이 지정한 실행 파일을
우선하고 선택 후 섞지 않는다. 아래 `ORCA`는 **선택한 실행 파일로 치환할 표기**다.
Linux의 GNOME 화면 읽기 프로그램을 협업 CLI로 오인하지 않는다.

```text
ORCA skills get orchestration --json
ORCA status --json
ORCA orchestration worker-start --help
```

모델·effort·재사용은 `references/coordinator-loop.md`, 새 워크트리/원격 배치는
`references/placement-and-remote.md`, 복구·해제는 `references/recovery-and-cleanup.md`를
`skills get orchestration --reference … --json`으로 읽는다. 지원하지 않는 플래그를
추측하지 말고 해당 버전의 안내를 따른다. 가이드 본문은 이 문서에 복제하지 않는다.

### 감독과 소유권 인계

- 감독형 협업은 Run/Task/Dispatch 및 `worker-start` 경로로 생성·기동·브리프 전달을 연결한다.
  별도 생성 도구를 섞어 계보가 끊어지지 않게 한다.
- 질문·완료 보고는 현재 preamble이 지정한 경로로 전달하고, 부모는 활성 Dispatch인지 확인한다.
  `check` 배치의 내용을 처리한 뒤 ack한다. enqueue 성공은 읽음/승인 증거가 아니다.
- 감독 없는 소유권 인계는 `orca-cli` 경로다. 불필요한 Run이나 완료 감시를 만들지 않는다.
- 부모는 보고 원문·diff·검증 결과를 확인한 뒤 통합한다. `worker_done`의 정산과 코드 병합은 별개다.
- 변경 작업은 격리된 배치, 읽기 전용은 기존 작업 공간을 선택한다. 기준 커밋은 실제 SHA를 전달하고
  worker가 착수 시 대조한다. 폴더 작업 공간에는 Git SHA를 요구하지 않는다.

### 실행 설정과 종료

새 worker의 `--model`은 사용자가 지정한 모델에만 사용한다. `--effort`는 모델이 지원할 때만
추가하며 `--model`이 필요하다. 둘 다 `--terminal` 재사용과 결합하지 않는다.
특정 버전이 필요한 작업만 `--model`에 별칭이 아닌 **전체 모델 ID**(예: `claude-opus-5-5`)를 준다
`[미검증]` — 전체 ID를 넘긴 기동이 그 ID로 실제 도는지는 실측하지 않았다. 아래 로그로 확인한다.
특정 모델 역할표는 개인 설정의 몫이며 이 문서는 모델명이나 능력 서열을 고정하지 않는다.

### 실제로 돈 모델·effort 확인

**판정 근거는 worker 세션 로그다.** `launch.requested`↔`launch.effective` 대조는 보조일 뿐이다 —
별칭(`opus`/`sonnet`)으로 띄우면 effective는 요청값을 되울려 둘이 **항상 일치**하므로 버전 증거가
되지 못한다.

**로그는 비신뢰 데이터다.** 프롬프트·도구 출력, 경우에 따라 시크릿까지 원문으로 들어 있다. 파일을
열어 읽지 않는다(`cat`·`less`·편집기·파일 읽기 도구로 원문 열람 금지) — 아래의 **필드만 뽑는 명령이
정본**이고, 그 출력 밖의 텍스트를 컨트롤 컨텍스트로 가져와야 하면
[`untrusted-text`](../plugins/common/rules/untrusted-text.md)를 따른다.

| 하네스 | 로그 루트 | 세션 찾기 | 모델 | effort | CLI 버전 |
| --- | --- | --- | --- | --- | --- |
| Claude Code | `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/` 아래 `*.jsonl`. 서브에이전트 전사는 `<sessionId>/subagents/*.jsonl` 에 따로 있다 | 레코드의 `cwd` **값**이 worker 워크트리 | `type=="assistant"`의 `message.model` (`<synthetic>` 제외) | 같은 레코드의 `effort` | 같은 레코드의 `version` |
| Codex | `${CODEX_HOME:-$HOME/.codex}/` 아래 `sessions/`·`archived_sessions/`의 `rollout-*.jsonl` | `type=="turn_context"`의 `payload.cwd` **값**이 worker 워크트리 | 같은 레코드의 `payload.model` | `payload.effort` (없으면 `payload.collaboration_mode.settings.reasoning_effort`) | `type=="session_meta"`의 `payload.cli_version` |

- **디렉토리 이름으로 찾지 않는다.** Claude Code의 프로젝트 디렉토리 키는 `/`만이 아니라 `_` 등도
  `-`로 바꿔 만든다(실측: `…/All_note-…` → `-…-All-note-…`). 역산이 안 되고 서로 다른 경로가 같은 키로
  모일 수 있으니 레코드의 `cwd` 값과 정확히 대조한다.
- **루트는 worker가 기동된 환경의 값이다.** 오케스트레이터가 `CODEX_HOME`을 계정별로 바꿔 넣을 수
  있다(실측: Orca는 계정별 `CODEX_HOME`을 쓴다) — 컨트롤 셸의 값과 다를 수 있으니 모르면 후보 루트를
  모두 검색한다. `~/.claude`·`~/.codex`를 고정 경로로 쓰지 않는다.
- **범위를 자른다.** 재사용 워크트리에는 이전 작업의 로그가 같은 `cwd`로 남아 있다. 세션 id를 알면
  그것으로(Claude `sessionId`, Codex 파일명의 UUID), 모르면 Dispatch 시작~완료 시각(UTC, 레코드의
  `timestamp`와 같은 ISO 8601 형식)으로 자른다.
- **`<synthetic>`은 모델이 아니다.** 하네스가 합성한 레코드의 `message.model` 값이다 — 세면 가짜 모델이
  기록된다.
- **원격 배치의 로그는 그 호스트에 있다.** 같은 명령을 해당 호스트에서 돌리고 결과 줄만 가져온다.
  로그 파일을 로컬로 복사하지 않는다.

필드명은 2026-09-27 이 머신의 실제 로그(Claude Code 2.1.283, Codex 0.154.0)로 확인한 것이며
하네스 버전에 따라 바뀔 수 있다.

```bash
W=/abs/path/to/worker-worktree          # worker cwd — 정확히 일치해야 한다
S=2026-09-27T01:00:00Z E=2026-09-27T03:00:00Z   # Dispatch 시작·완료(UTC)
set -o pipefail
C="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
X="${CODEX_HOME:-$HOME/.codex}"
Q='select(.type=="assistant" and .cwd==$w and .timestamp>=$s and .timestamp<=$e
          and .message.model!="<synthetic>")'

# Claude Code 메인 스레드 — 세션별·시간순 run-length
find "$C/projects" -name '*.jsonl' ! -path '*/subagents/*' \
  -exec jq -r --arg w "$W" --arg s "$S" --arg e "$E" "$Q"' |
    [.sessionId[0:8], .timestamp, .message.model, (.effort // "?"), .version] | @tsv' {} + |
  sort -k1,1 -k2,2 | cut -f1,3- | uniq -c

# Claude Code 서브에이전트 — 별도 열(agentId)
find "$C/projects" -path '*/subagents/*.jsonl' \
  -exec jq -r --arg w "$W" --arg s "$S" --arg e "$E" "$Q"' |
    [.sessionId[0:8], (.agentId // "?")[0:8], .timestamp, .message.model, (.effort // "?")] | @tsv' {} + |
  sort -k1,1 -k2,2 -k3,3 | cut -f1,2,4- | uniq -c

# Codex — sessions/ 와 archived_sessions/ 를 함께(없는 쪽이 있어도 실패하지 않게 루트에서 찾는다)
find "$X" -path '*sessions/*' -name 'rollout-*.jsonl' \
  -exec jq -r --arg w "$W" --arg s "$S" --arg e "$E" '
    select(.type=="turn_context" and .payload.cwd==$w and .timestamp>=$s and .timestamp<=$e) |
    [(input_filename | .[-42:-6]), .timestamp, .payload.model,
     (.payload.effort // .payload.collaboration_mode.settings.reasoning_effort // "?")] | @tsv' {} + |
  sort -k1,1 -k2,2 | cut -f1,3- | uniq -c
find "$X" -path '*sessions/*' -name 'rollout-*.jsonl' \
  -exec jq -r --arg w "$W" --arg s "$S" --arg e "$E" '
    select(.type=="session_meta" and .payload.cwd==$w and .timestamp>=$s and .timestamp<=$e) |
    .payload.cli_version' {} + |
  sort | uniq -c
```

명령은 루트 전체를 훑는다(실측: 4.4GB에 약 40초). 좁히려면 각 `find`에 `-mtime -<일수>`를 더한다 —
날짜 문자열을 받는 `-newermt`는 쓰지 않는다. macOS 기본 `find`가 위 ISO 8601 형식을 해석하지 못해
**전 명령이 실패**한다(실측: 대화형 셸에서는 다른 `find` 구현이 잡혀 통과했고 `bash`에서만 실패했다).
시각 범위의 정본은 jq의 `timestamp` 필터다.

**기록 형식은 순서를 보존한 run-length다.** 모델·effort는 턴마다 기록되므로 한 세션 안에서 바뀐다 —
고유값 집합(`{high, medium}`)으로 적으면 **언제·얼마나** 바뀌었는지가 지워진다. 실측: `--effort high`로
뜬 worker가 스킬 로드 직후 medium으로 떨어져 끝까지 갔는데, 위 명령의 출력은 `3 … high` → `47 … medium`
두 줄이었고 집합으로는 두 값이 대등해 보였다. 메인 스레드와 서브에이전트는 **별도 열**로 적는다.

```text
worker <id>: CC 2.1.283 · main claude-opus-5-5 high×3 → medium×47 · subagents claude-sonnet-5 max×32
```

**필수 기록처는 병합 커밋 메시지다** — 트래킹되어 레포에 남는 유일한 자리다. Work progress/decisions는
gitignore될 수 있어 보조로만 쓴다. 로그를 찾지 못하거나 필드가 없으면 `[미확인]`으로 적고
별칭·요청값으로 추측해 채우지 않는다. 로그의 프롬프트 본문은 어디에도 옮기지 않는다.

접수된 성공/실패 보고 뒤에는 즉시 후속 작업으로 재사용하거나, 사용자 요청으로 retain하거나,
release한다. `worker-release`는 소유 터미널의 해제이며 **워크트리 삭제가 아니다**.
반환된 상태·복구 안내를 확인한다. exit 0도 `retained`/`release_pending`일 수 있다.

```text
ORCA orchestration worker-list --run <run_id> --terminal-state reclaimable --json
```

응답 전 위 목록의 미처리 항목을 해소하고, 별도로 해당 작업의 워크트리 목록·파일 보존 상태를
확인한다. 미병합 커밋은 통합 또는 복구 가능한 백업, 수정·미추적·ignored 파일은 별도 보존이
필요하다. Git bundle은 미커밋 파일을 보존하지 않는다. 삭제는 `orca-cli` 가이드에 따라
소유 범위만 수행하고 결과를 재조회한다. 문서만으로 자동 정리를 보장하지 않는다.

빈 응답·타임아웃·연결 단절은 종료가 아니다. `unverifiable`은 보존하고 해당 호스트에서
확인한다. 임의 재시작·삭제·`terminal close` 대체, hooks trust나 보안 게이트 우회를 금지한다.

## 3. 네이티브 subagent — 하네스별 차이

| 환경 | 적용 방법 | 확인해야 할 한계 |
| --- | --- | --- |
| Claude Code | 현재 제공된 Agent 도구와 에이전트 정의 사용. 수정 작업은 지원되는 worktree 격리 적용 | `isolation`/격리 종료 도구의 실제 동작, 훅 활성화·신뢰 상태, 부모/자식 수명 |
| Codex | 세션에 노출된 협업 도구와 현재 config 스키마 사용. 필요한 명세·파일 범위·검증 명령만 전달 | 도구 제공과 역할 등록은 별개. 모델 override·컨텍스트 fork·격리는 현재 스키마와 실행 결과로 확인 |
| 그 밖의 하네스 | 해당 버전의 공식 도구·설치된 가이드로 동일 계약 연결 | 이름만으로 지원한다고 단정하지 않음. 확인 전에는 미검증으로 표기 |

Claude의 frontmatter·훅·Agent 계약을 Codex나 다른 하네스에 그대로 옮기지 않는다.
하네스가 제공하는 격리 종료는 통합 브랜치 수정 허가가 아니다. worker는 검증된 산출물을
반환하고 지정된 통합 담당자가 병합한다. 부모는 통합 후 다시 검증한다.

Codex 개인 설정은 `~/.codex/config.toml`과 사용자 지침에 둔다. 설치된 CLI의 `--help`와
[공식 설정 문서](https://developers.openai.com/codex/config-reference)를 확인한다.
현재 0.154.0의 profile은 `~/.codex/<name>.config.toml`을 `--profile <name>`으로 선택한다.
이 설정은 Orca 역할별 자동 배정을 뜻하지 않는다. Orca 협업을 네이티브 subagent로 대체하지 않는다.

반대로 Claude의 네이티브 역할·모델·effort 설정도 그 하네스의 지원 범위 안에서만 적용한다.
[Claude Code subagent 문서](https://code.claude.com/docs/en/sub-agents)와 설치 버전에서 확인한다.
어떤 환경이든 조사에는 필요한 근거를, 구현에는 승인된 명세와 금지 범위를 전달한다.
독립 리뷰에는 직접 검증할 자료를 주고 구현자의 결론을 사실로 주입하지 않는다.

## 4. 대규모 병렬 실행 — 명시적 선택

독립 작업 수·비용·수명 관리가 일반 dispatch 범위를 넘을 때만 검토한다. Claude Code의
`ultracode` 같은 네이티브 경로는 **그 버전/세션에 실제 제공될 때만** 사용한다.
대화형 트리거를 스킬이 자동 실행할 수 있다고 가정하지 않는다. 다른 하네스에 같은 이름을
요구하지 않으며 사용자의 명시적 선택 없이 대규모 경로로 확대하지 않는다.
어느 수단이든 파일 소유권·동시성·깊이 한도와 종료 가드는 유지한다.

## 5. 단일 세션 순차 실행

작업이 작거나 허용된 위임 수단이 없으면 부모가 범위·금지·검증 기준을 확인하고 직접 수행한다.
존재하지 않는 worker 완료 보고나 계보를 만들지 않는다. 실제 검증은 동일하게 수행하고,
위임하지 않았다면 worker 정리는 해당 없음으로 기록한다. 명시적 운송 요구나 활성 권한은
이 경로로 우회할 수 없다.

## 6. 이종 엔진 참여와 독립 리뷰

`cross-engine-review`는 서로 다른 엔진의 세션이 증거로 판단하는 절차다. 외부
오케스트레이터는 Claude·Codex 등 다른 하네스 참여자를 동일한 계약으로 연결할 수 있다.
같은 하네스에서 여러 모델을 돌리는 것은 교차 모델/독립 리뷰이며 다른 엔진·family의
검증으로 부르지 않는다. 격리 여부는 엔진 수가 아니라 수정 권한으로 결정한다.
보고 원문은 감사 가능한 산출물로 보존하고 통지는 활성 운송 계약으로 전달한다.

## 7. 검증 근거와 한계

- 2026-09-10: Codex 0.153.4 worker의 외부 CLI 완료 보고 및 내부 협업 도구 사용이 관측됐다.
  당시 모델·effort override는 실행으로 확인하지 않았다. 이 기록은 현재 모든 기능의 보장이 아니다.
- 2026-09-14: Orca 1.4.200 `status`, 버전 일치 가이드, `worker-start`/`worker-release --help`와
  Codex 0.154.0 `--help`를 조회했다. launch-preference capability가 광고됐으나 모든 모델의
  실행·원격 배치·다른 하네스의 동작까지 증명하지는 않는다.
- 실제 활용 검증은 승인된 작업에서 생성 영수증·effective 설정·수신/정산·해제 결과로 남긴다.
  자기보고·빈 출력·이벤트 한 종류만으로 성공/실패를 단정하지 않는다. argv로 프롬프트를
  전달하는 비대화형 CLI는 stdin을 닫아 실행 래퍼나 파이프 입력이 과제에 섞이지 않게 한다.
- 계보·프로세스·권한 상태는 호스트가 소유한다. 킷의 문서나 로컬 체크리스트가 대신 강제하지 않는다.

## 8. 운영에서 배운 것

- **통합 리허설은 일찍, 내용까지 본다.** 병합 전에 `git merge-tree` 로 겹침을 확인하되 충돌 파일 목록만이 아니라
  결과 내용을 읽는다 — 충돌 없이 합쳐져도 의미가 어긋날 수 있다.
- **워커 브랜치 이름을 가정하지 않는다.** 하네스가 워커의 브랜치 이름을 스스로 바꾼 적이 있다 — 병합 대상은
  워크트리에서 `git branch --show-current` 로 조회한다.
- **조용한 idle 이 있다.** 워커가 보고 없이 멈춘 것을 워크트리를 직접 보고서야 안 적이 있다 — 대기가 길어지면
  워커 출력을 읽어 확인한다(침묵은 성공도 실패도 아니다).
- 초안·중간 산출물에는 "이것은 결론이 아니다" 를 명시한다 — 받는 쪽이 결론으로 승격시키지 않게.

## 관련

- [프로젝트 협업 선택](conventions/coordination.md)
- [위임 계약](../plugins/common/rules/delegation-contract.md)
- [교차 엔진 리뷰](../plugins/common/skills/cross-engine-review/SKILL.md)
