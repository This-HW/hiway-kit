# Agent Evals

핵심 에이전트(`review-code`, `fix-bugs`, `implement-code`)의 **행동 회귀**를
기계로 검증하는 하네스. 에이전트 정의(`.md` frontmatter + 시스템 프롬프트)를
수정했을 때 품질이 후퇴했는지 감지하기 위한 것이다.

`plugins/` 밖(레포 루트)에 둔다 — 플러그인 설치 용량에 영향을 주지 않기 위함.

## 철학

- **Deterministic-first.** 채점은 규칙(정규식/파일 검사/pytest 실행)으로 하며,
  LLM-judge는 opt-in 보조 수단이다. deterministic 검사를 전부 통과한 시나리오만
  judge를 태운다.
- **False-green 금지 (v2.9.3 교훈).** 실행 불가(claude CLI 부재 등)를 성공으로
  위장하지 않는다 — 반드시 별도 exit code(`SKIPPED=2`)로 구분한다.
- **릴리스 전 필수 게이트이지 per-commit CI가 아니다.** 실제 행동 eval은
  `claude -p`를 호출해 API 비용이 든다. 그래서:
  - `--validate`(스키마 오프라인 검증)만 `scripts/verify-done.sh` §10에 편입한다.
  - 전체 행동 eval(`scripts/run-evals.sh`, 인자 없이)은 릴리스 전에 수동/온디맨드로
    실행한다.

## 디렉토리 구조

```
evals/
  run.py                 러너 (stdlib만, 단일 파일)
  scenarios/<agent>/<scenario-id>/
    task.md              에이전트에게 줄 과제 프롬프트
    fixture/             대상 코드 (버그를 심거나 TODO로 비워둔 상태)
    expect.json          채점 기준 (deterministic assertions + opt-in judge rubric)
  baseline/<date>.json    --baseline으로 저장된 기준선 (git 추적)
  reports/<timestamp>.json  매 실행 리포트 (gitignore 대상, 로컬 전용)
```

## 사용법

```bash
# 오프라인 스키마 검증 (API 불필요, verify-done.sh §10과 동일)
./scripts/run-evals.sh --validate

# claude 미호출, 실행 계획만 확인
./scripts/run-evals.sh --dry-run

# 특정 에이전트/시나리오만 실행 (API 비용 발생)
./scripts/run-evals.sh --agent fix-bugs
./scripts/run-evals.sh --agent review-code --scenario sql-injection

# 병렬 실행 (기본 1)
./scripts/run-evals.sh --parallel 4

# 기준선 저장 (릴리스 시점 1회)
./scripts/run-evals.sh --baseline

# 기준선 대비 후퇴 검출 (pass-rate 하락 시 exit 1) — **전량 재실행**한다
./scripts/run-evals.sh --compare evals/baseline/2026-07-07.json

# 이미 실행한 리포트로 비교만 (재실행 없음, API 비용 0)
./scripts/run-evals.sh --compare evals/baseline/2026-07-07.json \
  --report evals/reports/<timestamp>.json
```

환경 변수:

| 변수 | 설명 | 기본값 |
| --- | --- | --- |
| `CKKIT_EVAL_TIMEOUT` | 시나리오당 타임아웃(초) — override 전용 | `evals/policy.json`의 `cost.scenarioTimeoutSeconds` (현재 600) |
| `CKKIT_EVAL_JUDGE` | `1`이면 deterministic 전부 통과 시 LLM-judge 실행 | (미실행) |

## exit code

| code | 의미 |
| --- | --- |
| 0 | 전체 pass (또는 `--validate`/`--dry-run` 정상) |
| 1 | 하나 이상 fail, 또는 `--compare` 시 baseline 대비 후퇴, 또는 스키마 오류 |
| 2 | **SKIPPED** — `claude` CLI를 PATH에서 찾을 수 없어 실행 불가. 절대 0으로 위장하지 않는다 |

## 채점 기준 (`expect.json`)

```json
{
  "assertions": [
    { "type": "output_regex", "pattern": "off-by-one", "flags": "i" },
    { "type": "output_contains_any", "values": ["sql injection", "parameterize"] },
    { "type": "output_not_contains", "values": ["secret-key"] },
    { "type": "pytest_green", "path": "." },
    { "type": "file_contains", "file": "stats.py", "pattern": "range\\(len" },
    { "type": "file_unchanged", "file": "test_stats.py" },
    { "type": "git_log_contains", "pattern": "^fix:", "ref": "main" },
    { "type": "git_branch_exists", "branch": "main" },
    { "type": "git_status_clean" }
  ],
  "judge": {
    "enabled": false,
    "rubric": "채점 기준 서술",
    "threshold": 7
  }
}
```

- `output_contains_any`/`output_not_contains`는 대소문자 무시 부분 문자열 매칭이다
  — 동의어를 넉넉히 나열해 brittleness를 낮춘다.
- **`output_not_contains`의 값은 '판정'이어야 하고 '일반 어구'여서는 안 된다.** 이 가드는
  거짓 green(에이전트가 결함을 못 찾고 "깨끗하다"고 선언하는 것)을 잡으려는 것인데,
  부분 문자열 매칭이라 **일반 어구를 넣으면 정반대 상황에서 발화한다.** 실측 3건:
  - `analyze-dependencies/order-utils-impact` — 두 차례 거짓양성 후 어서션 제거(W-022 R3)
  - `security-scan/shared-tmp-and-hardcoded-token` — Critical 1·High 2·Medium 2·Low 1 을
    보고하고도 **수정안 코드 주석** `# 원자적 rename, 심볼릭 링크 문제 없음` 때문에 fail
    (W-023). 이를 계기로 18개 시나리오에서 `문제 없음`·`문제가 없`·`이상 없음`·
    `looks fine`·`looks good` 5종을 제거했다 — 판정이 아니라 어구다.
  - 남긴 값은 결함 부재를 **선언**하는 형태뿐이다: `취약점 없음`류·`버그 없음`류·
    `no vulnerabilities`·`no issues found`.
  - 판단 기준: **그 문자열이 "여기는 괜찮다"는 부분 서술이나 수정안 설명에 등장할 수
    있는가?** 있으면 넣지 마라. 어차피 진짜 거짓 green 은 positive 어서션이 함께 잡는다
    (이 가드를 가진 모든 시나리오가 positive 어서션을 함께 갖고 있다).
- `pytest_green`은 fixture의 임시 복사본에서 `python3 -m pytest <path>`를 실행해
  exit 0인지 확인한다.
- `file_unchanged`는 실행 후 파일이 **원본 fixture와 바이트 동일**한지 본다 — 에이전트가
  테스트 파일을 고쳐 green을 만드는 우회를 막는다. **`git.json`의 `write` 대상과 겹치면
  안 된다** (실체화가 원본을 덮어써 영구 fail이 된다 — `--validate`가 거부한다).
- **git 상태 어서션 3종** (`git.json`이 있는 시나리오용):
  - `git_log_contains` — `git log --format=%B <ref>` 출력에 정규식 매치. `ref` 기본값은
    `HEAD`이며 그 경우 **조상 전체의 커밋 메시지**를 본다. `git.json`이 만든 커밋 메시지에
    매치하면 에이전트가 아무것도 하지 않아도 통과하므로, **패턴이 `git.json`의 어떤 커밋
    메시지에도 매치하지 않는지 반드시 확인하라** (실제로 밟은 함정이다).
  - `git_branch_exists` — `git branch --list` 결과에 해당 브랜치가 있는가.
  - `git_status_clean` — `git status --porcelain`이 빈 출력인가. 충돌(unmerged) 상태는
    `UU` 항목으로 잡힌다. **한계: detached HEAD는 작업 트리만 깨끗하면 clean으로 판정된다**
    — 브랜치 도달성까지 보려면 `git_branch_exists`와 조합하라.
  - 셋 다 `expect: false`로 부정을 표현한다(별도 `*_not_*` 타입은 없다). 저장소가 아닌
    디렉토리에서는 **명시적 fail**이다(빈 출력을 clean으로 오독하지 않는다).
- `judge`는 opt-in이다. `enabled: true`면 `rubric` 필수. deterministic이 전부
  통과하고 `CKKIT_EVAL_JUDGE=1`일 때만 실행되며, judge 실패는 경고로만 기록된다
  (deterministic 통과 시 최종 판정은 pass 유지).

## `git.json` — 저장소 상태를 가진 시나리오 (선택)

시나리오 디렉토리에 `git.json`을 두면 러너가 실행 직전 temp 작업 디렉토리에 git 저장소를
**실체화**한다(`fixture/` 복사 직후, 에이전트 dispatch 전). 브랜치·커밋 히스토리·충돌
상태를 fixture로 표현할 수 있다.

```json
{
  "version": 1,
  "ops": [
    { "op": "init", "defaultBranch": "main" },
    { "op": "add", "paths": ["."] },
    { "op": "commit", "message": "feat: initial" },
    { "op": "branch", "name": "feature/x" },
    { "op": "checkout", "ref": "feature/x" },
    { "op": "write", "path": "src/app.py", "content": "VALUE = 2\n" },
    { "op": "add", "paths": ["."] },
    { "op": "commit", "message": "feat: change value" },
    { "op": "checkout", "ref": "main" }
  ]
}
```

**허용 연산은 8종뿐이다** — `init` · `write` · `add` · `commit` · `branch` · `checkout` ·
`tag` · `merge`. 화이트리스트이지 블랙리스트가 아니다. `run`/`exec`/`clone`/`fetch`/
`push`/`remote`/`submodule`/`config`는 **의도적으로 없다**.

**왜 이렇게 좁은가.** 러너는 fixture의 임의 코드 실행을 막아 왔고(conftest.py 금지,
모듈 스코프 위험 호출 AST 차단), 실측 실행은 `--permission-bypassPermissions`다. git은
설정 하나로 코드를 실행시킬 수 있어서 — `config` op은 `filter.<n>.clean`으로, `write`는
`.git/config` 직접 쓰기로 각각 임의 코드 실행이 성립함이 **실증됐다**. 그래서:

- `config` op은 존재하지 않는다.
- `write.path`는 `.git/`을 어느 위치에서도 포함할 수 없다(대소문자 무관). 절대경로·`..`도 금지.
- 모든 op의 인자는 `-`로 시작할 수 없다(옵션 주입 차단). `add`/`checkout`은 `--` 종결자를 쓴다.
- 위반은 `--validate`(오프라인)와 실체화(실행) **양쪽에서** 거부된다.

**그 밖에 알아 둘 것**:

- 커밋 작성자·시각은 고정된다 — 실행자의 전역 git 설정이 결과를 바꾸지 않는다.
- 실체화 실패는 시나리오를 `error`로 만들고 어서션 채점에 들어가지 않는다(fail-closed).
- git 명령 하나당 60초 상한이 있다.
- **git 2.28+ 필요** (`init -b`). 그 이전 버전에서는 실체화가 실패한다.
- `git.json`이 있어도 `fixture/`는 여전히 필요하다(빈 디렉토리는 git이 추적하지 않으므로
  최소 1개 파일을 두어라).

## 시나리오 추가 가이드

1. `evals/scenarios/<agent-name>/<scenario-id>/` 디렉토리 생성.
   `<agent-name>`은 `plugins/common/agents/**/<name>.md`에 실재해야 한다.
2. `fixture/`에 대상 코드를 둔다 — review-code는 버그가 심긴 코드, fix-bugs는
   버그 코드 + 실패하는 pytest 테스트, implement-code는 `TODO`/`NotImplementedError`
   상태의 코드 + red 상태 pytest 테스트.
3. `task.md`에 에이전트에게 줄 과제를 한국어로 명확히 서술한다.
4. `expect.json`에 assertions를 정의한다 — 최소 1개 이상, deterministic 우선.
5. `python3 evals/run.py --validate`로 스키마를 확인한다.
6. `python3 evals/run.py --dry-run --agent <name> --scenario <id>`로 계획을
   확인한 뒤, 필요 시 `--agent <name> --scenario <id>`로 실제 1회 실행해 본다
   (API 비용 발생 — 로컬에서 최소 횟수로).

### ⚠ 자기충족 어서션 금지 — 이 가이드에서 가장 자주 틀리는 지점

**어서션은 `task.md` 가 지시하지 않은 것을 검사할 때만 능력을 측정한다.**

`task.md` 에 검사 대상 값·형식을 적어 두고 `expect.json` 에서 그 값을 확인하면,
그 시나리오는 **에이전트의 능력이 아니라 지시 따르기**를 측정한다. 통과해도 아무것도
증명되지 않고, 더 나쁘게는 **"이 에이전트는 안정적"이라는 잘못된 확신**을 준다.

실제로 이 함정에 빠진 적이 있다(W-022 R1). `implement-code` 시나리오의 `task.md` 가
출력 마커 형식을 직접 지시하고 있었고, 그래서 나온 6/6 통과가 "안정 대조군"으로
인용됐다 — 대조군이 아니었다. 이 오독은 폐기 판정의 근거 문서 다섯 곳에 퍼진 뒤에야
발견됐다.

**작성 시 자문할 것**: 이 어서션이 검사하는 값이 `task.md` 안에 (문자 그대로든 바꿔
말한 형태로든) 이미 적혀 있는가? 그렇다면 그것은 능력 측정이 아니다.

의도적으로 지시 이행을 측정하는 시나리오라면 **그렇다고 적어라** —
`expect.json` 의 `_designNote` 에 명시한다(예:
`evals/scenarios/optimize-logic/on-squared-duplicate-finder/expect.json`).
암묵적인 자기충족과 **선언된** 지시-이행 측정은 다르다.

## 릴리스 체크리스트 연동

- `scripts/verify-done.sh` §10이 `--validate`를 자동 실행한다(오프라인, fail-closed).
- 실제 행동 eval(`scripts/run-evals.sh`, 필터 없이 전체)은 릴리스 전 수동 1회
  실행해 `--baseline`으로 기준선을 남기고, 이후 프롬프트 수정 PR에서는
  `--compare`로 후퇴 여부를 확인한다.

## 보안 경계 (적대적 리뷰 B 반영)

- 실측 실행(`run-evals.sh`)은 에이전트를 `--permission-mode bypassPermissions`로
  돌린다 — temp 작업 디렉토리는 **샌드박스가 아니다**. 따라서 **이 레포에 커밋된,
  리뷰를 통과한 시나리오만 실행**하라. 외부 기여 시나리오는 fixture/task.md의
  프롬프트 인젝션 여부를 사람이 검토한 뒤 병합한다.
- fixture 내 `conftest.py`는 금지 — pytest 수집 시 자동 실행되므로 `--validate`가
  fail 처리한다.
- 채점 경로(`path`/`file`)는 fixture 밖 탈출이 차단된다(`_safe_join`).

## 운영 규칙

- **judge는 advisory-only**: 최종 pass/fail에 영향을 주지 않고 리포트에만 기록된다
  (`advisory: true`). 게이트는 deterministic assertions가 전담한다.
- **실패한 런은 baseline이 되지 못한다**: exit≠0이면 `--baseline` 저장을 거부한다.
  같은 날짜 재실행 시 기존 baseline은 `.bak`으로 백업 후 교체된다.
- **커버리지 후퇴도 후퇴다**: `--compare`는 pass_rate 하락뿐 아니라 에이전트/시나리오
  수 감소도 회귀로 판정한다.
- **fix-bugs 게이밍 차단**: `file_unchanged` assertion이 테스트 파일 변조(테스트를
  고쳐서 green 만들기)를 fail 처리한다.

## 추가 주의사항 (재감사 반영)

- **reports/의 민감정보 가능성**: 에이전트(Read/Grep 보유)가 호스트 파일 내용을 출력에
  포함하면 `evals/reports/*.json`에 평문으로 남는다 (로컬 전용·gitignore — 원격 유출
  채널은 없지만 리포트 공유 전 확인하라).
- **baseline 백업은 1세대만**: 같은 날 재실행 시 `.bak`이 덮어써진다 — 보존이 필요하면
  재실행 전에 커밋하라.
- **부분 실행은 baseline이 될 수 없다**: `--agent`/`--scenario` 필터가 걸린 실행에서
  `--baseline`은 저장을 거부한다 (부분 기준선이 커버리지를 침묵 은닉하는 것 차단).
