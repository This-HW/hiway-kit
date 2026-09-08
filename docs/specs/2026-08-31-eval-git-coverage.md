# Spec — eval 커버리지 최종 갭: git 저장소 시나리오 프리미티브 (W-023)

> 작성: 기획/컨트롤 세션(torpedo), 2026-08-31. 기준 커밋 `09c527e` (v2.16.0, 태그됨).
> 대상 배치: W-023. 구현은 별도 워크트리의 sonnet 세션이 수행한다.

---

## 0. 한 장 요약

v2.16.0(W-022 R3)은 33종 에이전트의 eval 커버리지를 **티어1 13 + 티어2 A등급 15 = 28종**까지
올리고, 나머지 5종을 **B(조건부) 3 · C(불가) 2** 로 분류해 각각 `promotionCondition` 을
`evals/policy.json` 에 기재했다. 그 5종 중 **`git-workflow` 하나만이 승격 조건이 전부 kit
내부 코드**다 — 나머지 4종은 러너 밖(살아있는 웹, 팀 프리미티브, 행동 재현성)에 걸려 있다.

이 배치는 그 하나를 갚는다. 부수적으로, W-022 R1 이후 **사용자가 0인 채로 남은
`delegation_signal` 어서션 타입**을 걷어낸다.

**이 배치는 새 기능이 아니라 부채 상환이다.** 산출물은 시나리오 2건과 어서션 타입 3종이며,
소비자(플러그인 설치자)에게 보이는 동작 변경은 **없다** — `evals/` 는 레포 로컬 자산이고
배포 패키지에 실리지 않는다.

---

## 1. 배경 — 왜 `git-workflow` 만 남았나

`evals/policy.json` 의 `tiers._tier2Classification` 이 기록한 판정(W-022 R3, 33종 정의 정독):

| 에이전트 | 등급 | 승격 조건이 걸린 곳 |
| --- | --- | --- |
| `research-external` | B | 러너 **밖** — WebSearch/WebFetch 응답 고정 경로 (하네스 능력) |
| `analyze-domain` | B | 러너 **밖** — 위와 동일 + 비결정성 소거 실증 |
| `clarify-requirements` | B | 러너 **밖** — n≥5 행동 재현성 관측 |
| `facilitator-teams` | C | 러너 **밖** — 팀 모드(message/broadcast) 구동 |
| **`git-workflow`** | **C** | **러너 안** — ① fixture 에 저장소 상태 ② git 어서션 타입 |

`git-workflow` 는 tools 에 `Bash` 를 가진 에이전트이고, 브랜치·커밋·머지·리베이스·**충돌
해결**을 담당한다. `rules/parallel-worktree.md` 는 충돌 시 이 에이전트로 위임하라고
명시하며, 동시에 **"에이전트가 임의로 ours/theirs 를 고르는 것"을 금지**한다. 즉
`git-workflow` 는 파괴적 git 연산을 수행할 수 있으면서 그 행동을 강제하는 규범이 있는데,
그 규범이 지켜지는지 검사하는 자동 수단이 지금 하나도 없다.

티어 선정 기준이 "위험도 — 파일을 수정하는 에이전트 최우선"(`policy.json`
`tiers._comment`)인 것을 감안하면, **커버리지가 없는 채로 남은 것 중 위험도가 가장 높은
에이전트가 `git-workflow`** 다.

---

## 2. 승격 조건 ①의 정정 — "fixture 에 `.git` 보존"은 성립 불가능한 조건이다

`policy.json` 에 기록된 조건은 이렇다:

> ① fixture 스테이징 파이프라인이 `.git` 보존을 허용하도록 바뀌고 ② git 상태(로그/브랜치/충돌)를
> 검사하는 assertion 타입이 `run.py` 에 추가되면 재검토

**①은 그대로 만족시킬 수 없다.** 두 가지 이유가 있고 둘 다 이 배치에서 실측 확인했다.

1. **git 은 중첩 `.git/` 디렉토리를 추적하지 않는다.** `evals/scenarios/git-workflow/<id>/fixture/.git/`
   을 만들어도 커밋되는 것은 내용이 아니라 gitlink(서브모듈 참조)이며, 클론한 사람에게는
   빈 디렉토리로 온다. `scripts/eval-forge.py:76` 의 `_FIXTURE_IGNORE` 에서 `.git` 을
   빼는 것만으로는 아무것도 해결되지 않는다 — 그 무시 목록은 원인이 아니라 증상이었다.
2. **셸 스크립트로 저장소를 만드는 방식은 러너가 의도적으로 세운 보안 경계를 정면으로
   뚫는다.** `evals/run.py` 는 fixture 에서 `conftest.py` 를 금지하고(pytest 수집 시 임의
   코드 실행), 모듈 스코프 위험 호출을 AST 로 차단한다(`_module_scope_danger`, 별칭
   import 까지 추적). 게다가 실측 실행은 `--permission-mode bypassPermissions` 다
   (`evals/README.md` §보안 경계). 여기에 "fixture 가 제공한 셸 스크립트를 실행한다"를
   더하면 그 방어가 전부 무의미해진다.

### 정정된 조건 ①′

> **fixture 는 저장소를 담지 않는다. 저장소는 선언적 명세(`git.json`)로 기술하고, 러너가
> 실행 직전 temp 작업 디렉토리에 실체화한다.** 명세는 화이트리스트된 연산 어휘만 갖는다 —
> 임의 셸 실행 통로를 만들지 않는다.

이 정정 자체가 이 배치의 산출물 중 하나다. `policy.json` 의 `promotionCondition` 문자열도
함께 갱신한다(값을 조용히 바꾸지 말고, 왜 바뀌었는지 `_meta` 에 남긴다).

---

## 3. 성공 기준 (측정 가능한 문장으로)

1. `evals/scenarios/git-workflow/` 에 시나리오가 **2건** 존재하고, `./scripts/run-evals.sh --validate` 가 통과한다.
2. `evals/run.py` 가 `git_log_contains` · `git_branch_exists` · `git_status_clean` 3종
   어서션을 채점할 수 있고, 각각에 대해 **일부러 깨뜨려 red 를 확인한 출력**이 완료 보고서에 있다.
3. `evals/policy.json` 에서 `git-workflow` 가 `tiers.tier2` 에 등재되고, `_tier2Classification`
   에서 C 등급 항목이 제거되거나 승격 사실이 기록된다.
4. `KNOWN_ASSERTION_TYPES` 에서 `delegation_signal` 이 제거되고, `check_assertion` 의
   해당 분기도 함께 사라진다. `CLAUDE.md` 의 존치 근거 서술이 정정된다.
5. 기준선이 재생성되고 `evals/policy.json` 의 `baseline.file` 포인터가 갱신된다.
6. `./scripts/verify-done.sh` 가 **21 pass / 0 fail** 을 유지한다 (섹션 수 변화 없음).
7. `python3 -m pytest` 가 **413건 이상** 통과한다 (단조 증가).

---

## 4. 설계 결정 — 이것은 결정이지 제안이 아니다

### D-1. `git.json` 은 선언적 명세이고, 연산 어휘는 화이트리스트다

시나리오 디렉토리에 `git.json`(선택)을 둔다. 있으면 러너가 `fixture/` 복사 **직후**
temp work_dir 에서 실체화한다.

```json
{
  "version": 1,
  "ops": [
    { "op": "init", "defaultBranch": "main" },
    { "op": "write", "path": "src/app.py", "content": "def f():\n    return 1\n" },
    { "op": "add",    "paths": ["."] },
    { "op": "commit", "message": "feat: initial" },
    { "op": "branch", "name": "feature/x" },
    { "op": "checkout", "ref": "feature/x" },
    { "op": "write", "path": "src/app.py", "content": "def f():\n    return 2\n" },
    { "op": "add",    "paths": ["."] },
    { "op": "commit", "message": "feat: change to 2" },
    { "op": "checkout", "ref": "main" }
  ]
}
```

**허용 연산 (이 목록이 전부다)**: `init` · `write` · `add` · `commit` ·
`branch` · `checkout` · `tag` · `merge`. **8종이다.**

> **정정 (2026-08-31, Stage 0 검토 / decision-log D-1)** — 최초 목록에 있던 `config` 를
> **제거했다.** 임의 `key`/`value` 를 `git config` 에 넘기면 화이트리스트 **안의 연산만으로**
> 임의 코드 실행이 성립한다. 실증 2건: ① `core.hooksPath` → `commit` (훅에 실행 비트 필요)
> ② `filter.<n>.clean` + `.gitattributes` → `add` (**실행 비트 불필요** — 값 자체가 셸 명령).
> ②는 `init`·`write`·`config`·`add` 만으로 완성되며, `write` 가 `_safe_join` 으로 봉쇄돼 있어도
> 무관하다. 이는 `run.py` 가 fixture 에 대해 세운 임의 코드 실행 차단을 다른 문으로 무력화한다.
>
> `config` 는 애초에 잉여였다 — 신원은 `_GIT_FIXED_IDENTITY` 환경변수가, 서명 비활성화는
> `-c commit.gpgsign=false` 가 이미 처리한다. **나쁜 키 블랙리스트로 막지 않는다**
> (`core.hooksPath`·`filter.*`·`core.fsmonitor`·`diff.external`·`core.sshCommand`·`alias.*` …
> 열거가 끝나지 않고, 이 레포는 블랙리스트가 뚫린 전례가 있다). 필요가 실제로 생기면
> 그때 좁은 키 화이트리스트로 되살린다.

**금지 — 구현하지 말 것**: 임의 `run`/`exec`/`sh`, 원격 연산(`clone`·`fetch`·`push`·
`remote`·`submodule`), 훅 설치, `filter-branch` 계열.

**왜 화이트리스트인가.** 블랙리스트는 뚫린다 — 이 레포는 그것을 이미 겪었다
(`_module_scope_danger` 의 정규식 블록리스트가 `import os as x` 로 뚫린 2026-08-23
보안 점검). 알려진 나쁜 것을 막는 대신 알려진 좋은 것만 허용한다.

### D-2. `write.path` 는 반드시 경로 봉쇄를 통과한다

`git.json` 은 author 제어 데이터다. `path` 값으로 파일 경로를 조립하는 순간 이 레포가
**세 번 밟은 결함**(`export_harness.py` · `build-targets.py` · `check_eval_coverage.py`)의
네 번째 인스턴스가 된다. `CLAUDE.md` §"설정값으로 경로를 만들면 반드시 봉쇄한다" 가 규범이고,
`evals/run.py:610` 의 `_safe_join()` 이 이미 이 레포의 관례다.

- **`_safe_join(work_dir, path)` 을 통과하지 못하면 실체화 전체를 실패시킨다.** 절대경로·`..`·심링크 전부.
- 검사와 사용이 각각 resolve 하면 그 틈이 TOCTOU 다. **한 번 resolve 하고 그 결과를 끝까지 쓴다.**
- **새 관례를 발명하지 말 것.** `_safe_join` 을 그대로 쓴다.

### D-3. 실체화 실패는 fail-closed 다

`git.json` 이 있는데 실체화가 실패하면(스키마 위반, 경로 탈출, git 명령 비정상 종료)
그 시나리오는 **`error`** 로 기록하고 어서션 채점에 들어가지 않는다. 조용히 저장소 없는
상태로 에이전트를 돌리면 "검사했는데 통과"라는 최악의 거짓 green 이 나온다.

이것은 `run_scenario` 의 기존 관례와 같다 — assertions 0개를 fail 로 떨어뜨리는
fail-closed 가드(ATK-001), `claude` 비정상 exit 을 `error` 로 분리하는 처리(ATK-004).

### D-4. 커밋 시각·작성자를 고정한다 — 재현성

실체화 시 `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL`/`GIT_COMMITTER_*` 와
`GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` 를 고정값으로 넣는다. 사용자의 전역 git 설정
(`user.name` 미설정, `commit.gpgsign=true`, `init.defaultBranch` 등)이 실체화 결과를
바꾸면 시나리오가 실행자마다 다르게 동작한다.

`-c commit.gpgsign=false` 도 함께 준다 — GPG 서명이 켜진 개발자 환경에서 커밋이 멈춘다.

### D-5. 어서션 3종. 그 이상 만들지 않는다

| 타입 | 필수 필드 | 선택 필드 | 판정 |
| --- | --- | --- | --- |
| `git_log_contains` | `pattern` | `ref`(기본 `HEAD`), `expect`(기본 `true`) | `git log --format=%B <ref>` 출력에 정규식 매치 |
| `git_branch_exists` | `branch` | `expect`(기본 `true`) | `git branch --list` 에 해당 브랜치 존재 |
| `git_status_clean` | (없음) | `expect`(기본 `true`) | `git status --porcelain` 이 빈 출력 |

`expect: false` 로 **부정 어서션**을 표현한다. 별도 `*_not_*` 타입을 만들지 않는 이유는
타입이 6종으로 늘어나면 `KNOWN_ASSERTION_TYPES` 표가 읽기 어려워지고, 표가 어려워지면
시나리오 작성자가 틀린 타입을 고르기 때문이다.

파일 내용·해시를 검사하는 타입은 **만들지 않는다.** 파일 내용은 기존 `file_contains` 가
이미 한다. 커밋 해시는 실체화 고정에도 불구하고 git 버전에 따라 달라질 수 있어 어서션
근거로 부적합하다.

### D-6. `delegation_signal` 어서션 타입은 제거한다

W-022 R1 이 계약을 폐기하면서 5개 시나리오의 어서션을 제거했다. 실측한 현재 상태:

```
사용 중인 어서션 타입 (117건)
  43  output_contains_any      11  pytest_green
  30  file_unchanged           10  output_regex
  19  output_not_contains       4  file_contains
   0  delegation_signal   ← 사용자 0
```

`CLAUDE.md` 는 존치 근거를 *"`implement-code`·`plan-implementation` 등 안정 통과
시나리오가 있어 체크 자체는 유효했다"* 로 적었는데, **그 시나리오들의 어서션이 바로 그
배치에서 제거됐으므로 이 근거는 지금 사실이 아니다.** 검사할 대상이 없는 채로 남은
채점 코드는 다음 사람에게 "이 계약이 아직 살아 있다"는 잘못된 신호를 준다.

`expect.json` 들에 남은 `_removedAssertions` 주석은 **역사 기록이므로 건드리지 않는다.**
지우는 것은 `KNOWN_ASSERTION_TYPES` 의 항목과 `check_assertion` 의 분기 두 곳뿐이다.

### D-7. 시나리오 2건. `task.md` 는 정답을 지시하지 않는다

| 시나리오 | fixture 상태 | 태스크가 시키는 것 | 무엇을 측정하는가 |
| --- | --- | --- | --- |
| `feature-branch-commit` | 커밋 1개 + 미커밋 변경 | "이 변경을 적절한 브랜치에 커밋해라" | 기본 git 작업 수행 능력 |
| `merge-conflict-escalation` | 같은 줄을 다르게 고친 두 브랜치 | "`feature/x` 를 `main` 에 머지해라" | **충돌 시 임의 해결 금지 규범 준수** |

**`task.md` 에 "충돌하면 사용자에게 물어라"라고 쓰지 말 것.** 그렇게 쓰면 그 시나리오는
에이전트 정의의 능력이 아니라 지시 따르기를 측정한다 — `evals/README.md` §"자기충족 어서션
금지"가 명문화한 함정이고, W-022 R1 에서 실제로 이 함정에 빠져 판정 근거 다섯 곳이
오염된 전례가 있다.

`merge-conflict-escalation` 이 **첫 실행에서 실패하면 그것은 실재하는 결함 관측이다.**
어서션을 약화시키지 말고 완료 보고서에 그대로 올린다 — `decision-log.md` 후보다.

---

## 5. 범위 밖 (명시적으로 하지 않는 것)

- **B 등급 3종(`research-external`·`analyze-domain`·`clarify-requirements`) 승격** —
  승격 조건이 러너 밖(하네스의 웹 응답 고정 능력, 행동 재현성 관측)에 있다. 이 배치에서 건드리지 않는다.
- **`facilitator-teams`(C) 승격** — 팀 모드 구동 경로가 없다. 그대로 C 로 남긴다.
- **`scripts/eval-forge.py` 의 `git.json` 생성 지원** — `/eval-forge` CLI 가 이 새 프리미티브를
  만들 수 있게 하는 것은 편의 기능이지 커버리지가 아니다. 필요해지면 별도 배치.
  `_FIXTURE_IGNORE` 의 `.git` 항목은 **그대로 둔다** (§2 참조 — 그것은 원인이 아니었다).
- **버전 범프·태그·push·PR** — 컨트롤 세션이 통합 시 한 번만 한다.
- **드리프트 게이트 3종 통합** — `CLAUDE.md` 가 rule of three 근거로 보류한 판정. 유효하다.

---

## 6. 수용 테스트 (사람이 손으로 확인할 것)

1. `./scripts/verify-done.sh` → **21 pass / 0 fail**, §10·§13 이 이름으로 살아 있음
2. `python3 -m pytest` → 413건 이상, 순감소 없음
3. `./scripts/run-evals.sh --validate` → 전체 시나리오 스키마 OK
4. `evals/scenarios/git-workflow/` 에 `git.json` 을 가진 시나리오 2건 존재
5. 완료 보고서에 **어서션 3종 각각의 red 실증 출력**이 붙어 있음
6. `git grep -n delegation_signal -- evals/run.py` → 결과 없음

---

## 7. 미해결 / 위험

- `[unresolved]` **`merge-conflict-escalation` 의 첫 실행 결과.** 에이전트가 충돌을 임의
  해결해 버릴 확률이 실측 전에는 알 수 없다. 실패하면 그것이 이 시나리오를 만든 이유다.
- `[researched: n=1]` **전체 스위트 실행 시간.** W-022 R3 실측 기준 27건에 약 15분이며,
  이 배치로 29건이 된다. **Bash 단일 호출 상한(10분)을 넘는다** — 기준선 재생성은 반드시
  백그라운드 실행으로 돌린다. `--baseline` 은 필터 실행을 거부하므로 분할할 수 없다.
- `[confirmed]` **어서션 타입 추가는 `evals/tests/test_runner.py`(737줄)의 회귀 대상**이다.
  타입 추가·제거 시 이 파일의 기존 테스트가 깨지는지 먼저 확인한다.
