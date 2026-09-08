# opt-in 훅 예시

이 디렉토리의 훅은 **`hooks.json`에 등록돼 있지 않다.** 킷의 훅은 설치 즉시 모든
소비자에게 활성이므로, 여기 실린 것처럼 `git push`를 조건부로 막는 훅이 기본 배포에
들어가면 정당한 사용(소비자가 자기 목적으로 자식 세션을 띄우고 실제로 push가
필요한 경우)을 깨뜨린다. 그래서 **문서화된 opt-in 경로**로만 제공한다 — 프로젝트가
직접 켜고 끈다.

## 수록된 훅

| 파일 | 막는 것 |
| --- | --- |
| `child-git-guard.py` | 다중 세션 개발에서 위험한 git 명령 (D-36) |
| `verify-mutate-split.py` | 검증과 상태 변경을 한 Bash 호출에 잇는 형태 |

### git 훅은 별도 위치에 있다

위 표는 **Claude Code 훅**(`PreToolUse` 등)이다. 하네스가 바뀌면 안 돈다.

`setup/git-hooks/` 에는 **git 훅**이 있다 — 누가 명령을 실행하든 똑같이 돌므로
**하네스 중립 집행**이다. Claude Code·Codex·Gemini·플레인 터미널에서 동일하게 작동한다.

| 파일 | 막는 것 | 이유 |
| --- | --- | --- |
| `setup/git-hooks/reference-transaction` | 태그 없는 `git stash` | stash 스택은 저장소의 모든 워크트리·동시 세션이 **공유**한다. 태그가 없으면 `pop` 이 남의 항목을 꺼내고 꺼낸 쪽은 모른다 |

```bash
H="$(git rev-parse --git-path hooks)"
cp "<플러그인 루트>/setup/git-hooks/reference-transaction" "$H/reference-transaction"
chmod +x "$H/reference-transaction"
```

`--git-path` 를 쓰는 이유는 워크트리에서 `.git/hooks` 조립이 깨지기 때문이다
(이 킷이 워크트리 운영을 권장한다). 해제는 그 파일을 지우면 된다. git 2.28+ 필요.

> **복사본이 낡는 것은 이 킷이 실제로 밟은 결함이다.** 그래서 훅에 중립 마커
> `# kit-managed-hook` 을 넣어 뒀고, `verify-done.sh §21` 이 **설치본과 정본을 대조**한다.
> 켜지 않았으면 침묵하고(opt-in 이므로 정상), 켰는데 낡았으면 노란 줄로 알린다.
> 마커가 없으면 소비자 소유 훅으로 보고 손대지도 대조하지도 않는다.
>
> 레포에 정본을 두고 설치기·드리프트 가드로 관리하는 방식이라면 마커를 **그대로 유지**하라 —
> 마커가 판정 근거다.

**차단해도 작업은 보존된다** — ref 갱신이 abort 되면 작업트리 리셋이 일어나지 않는다
`[confirmed]`. 회귀 테스트가 이 계약을 고정한다(`tests/test_git_stash_guard.py`).

## 설치 방법

프로젝트의 `.claude/settings.json`(또는 `settings.local.json`)에 `PreToolUse` 항목으로
추가한다:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": [
              "${CLAUDE_PLUGIN_ROOT}/hooks/examples/child-git-guard.py"
            ],
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

끄려면 이 항목을 지운다. 코드 변경은 필요 없다 — 순수 설정 토글이다.

## 이 훅이 하는 일

`child-git-guard.py`는 `Bash` 도구 호출의 명령 문자열을 검사해 다음을 차단한다:

| 패턴 | 차단 조건 | 근거 |
| --- | --- | --- |
| bare `git stash` / `git stash pop` | 항상 | stash 스택은 워크트리 간 공유 — CLAUDE.md 최상위 안전 규율과 동일 |
| `git reset --hard` | 항상 | 커밋 안 된 변경을 되돌릴 수 없이 파괴 |
| `git clean` (force+directory 조합) | 항상 | 추적 안 된 파일을 되돌릴 수 없이 삭제 |
| `git push` | **자식 세션에서만** | main 병합·푸시는 부모(컨트롤) 세션의 몫 — D-36 |

`git push` 차단은 **자식 세션 판별에 의존**한다. 판별 방법은 아래를 반드시 읽는다 —
이 훅에는 실측된 한계가 있다.

## 자식 세션 판별 — 마커 파일, 그리고 그 한계

판별은 워크트리 로컬 마커 `$(git rev-parse --git-dir)/kit/child.json`의 **존재**로
한다. `CLAUDE_CODE_CHILD_SESSION` 환경변수는 쓰지 않는다 — 부모·자식·네이티브
서브에이전트 세션 전부에서 값이 `1`로 동일함이 실측됐고(`env -u`로 지워도 Claude
Code가 다시 설정한다), 이 변수로 분기하면 **컨트롤 세션 자신의 `push`까지 막힌다**
(설계 §13.5).

판별 규칙:

1. **주 체크아웃은 마커가 있어도 자식이 아니다** — `git rev-parse --git-dir` ==
   `git rev-parse --git-common-dir`인 곳(리포지토리의 원 체크아웃)에서는 이 마커를
   신뢰하지 않는다. 마커는 자식임을 **확인**하는 데 쓰이지, 부모를 자식으로
   **승격**시키는 데 쓰이지 않는다.
2. 워크트리에서 위 두 경로가 다르고, 그 워크트리의 gitdir 아래 `kit/child.json`이
   존재하며 유효한 JSON이면 — 자식으로 판정한다.
3. 마커가 없으면 — **자식이 아닌 것으로 간주한다(fail-open).** `git push` 차단이
   걸리지 않는다.

**한계를 정직하게 적는다**: 마커는 자식 세션 스킬이 로드될 때 생긴다. 스킬을 로드하지
않고 시작된 세션(수동 실행, 다른 진입 경로 등)은 이 훅으로 보호되지 않는다. **없는
보호를 있다고 믿지 마라** — 이 훅이 켜져 있어도 마커가 없으면 `git push`는 그냥
통과한다.

## 하네스 범위 — Claude Code 전용

이 훅은 `PreToolUse` 이벤트에 의존하며, 그 메커니즘은 **Claude Code 전용**이다
(파리티 계약의 L3 = 강제). Codex·Antigravity에서 자식 세션 규율은 규범(L0) +
자식 세션 스킬(L1) 서술로만 성립하고, 여기서 하는 것과 같은 **자동 차단은 없다**.
그 사실을 자식 세션 스킬 본문에도 적어야 한다 — 없는 보호를 있다고 믿게 하지
않는다는 원칙은 이 훅에도, 그 스킬에도 동일하게 적용된다.

## 왜 완전한 셸 파서가 아닌가

`child-git-guard.py`의 명령 파싱은 따옴표 경계 밖에서 `&&`·`||`·`;`·`|`로 나누고
`shlex.split`으로 토큰화하는 수준이다. 난독화(변수 치환, `eval`, 배열 확장 등)를
뚫는 적대적 우회 방지가 목적이 아니라 — 사람과 에이전트가 실제로 타이핑하는 흔한
형태를 잡는 것이 목적이다. 이 opt-in 예시는 방어 심층화의 한 겹이지, 유일한
방어선이 아니다(최종 방어선은 여전히 부모의 재검증과 `git reflog`/`stash list`
복구 경로다).


---

# `verify-mutate-split.py`

## 이 훅이 하는 일

`Bash` 명령 문자열을 세그먼트로 나눠, **검증 뒤에 상태 변경이 오는 형태**를 차단한다.

    출력은 읽어야 게이트가 된다. 읽기 전에 다음 명령이 실행되면 그건 게이트가
    아니라 로그다.

판정은 검증의 종류에 따라 갈린다 — **이 구분이 이 훅의 핵심이다.**

| 검증 종류 | 예 | 판정 |
| --- | --- | --- |
| **종료코드 검증** | `pytest`·`ruff`·`*verify*.sh` | `&&` 면 **통과**(진짜 게이트), `;`·개행·`&` 면 차단 |
| **출력 검증** | `gh pr view`·`gh pr checks`·`gh run list`·`gh api` | 구분자와 **무관하게 차단** — CI 가 빨개도 exit 0 이다 |

차단 대상 상태 변경: `git push`·`git merge`·`gh pr merge`·`gh release create`·
`gh workflow run`·`npm/pnpm/yarn/cargo publish`·`twine upload`·`docker push`·
`kubectl apply`·`terraform apply`.

## 왜 `git status` 는 목록에 없나

`git status && git push` 는 흔하고 무해한 관용구다. CI 판정을 담지 않는 단순 조회까지
막으면 이 훅이 상시 발동하고, **상시 참인 경고는 옆의 진짜 경고까지 죽인다**
(`docs/conventions/warning-signal.md`). 그래서 `git status`·`git diff`·`git log` 는
의도적으로 뺐다.

## 검증기 이름을 못 알아보는 경우 (직접 추가해야 한다)

`EXIT_CODE_VERIFIER_RE` 는 파일명이 `verify`·`check`·`validate`·`lint`·`test` 로 **시작**할
때만 검증기로 알아본다. `audit_*` 처럼 다른 이름이면 상수에 직접 추가해야 한다.

**어느 목록에 넣을지는 종료코드로 가른다** — 실사용에서 같은 레포의 같은 접두어 스크립트
둘이 서로 다른 축으로 갈린 사례가 있다:

| 스크립트 | 위반 시 | 목록 |
| --- | --- | --- |
| 위반이면 비-0 으로 종료 | 종료코드가 판정 | `EXIT_CODE_VERIFIERS` |
| 후보만 출력하고 항상 exit 0 | **출력이 판정** | `OUTPUT_VERIFIERS` |

인터프리터 경유(`python scripts/audit_x.py`)까지 잡으려면 **2토큰 패턴**으로 넣어라 —
`toks[0]` 이 `python` 이라 1토큰 패턴에는 걸리지 않는다(`uv run`·`poetry run` 은 3토큰).

## 이 훅이 판정하지 않는 것

**"직전 턴에 CI 결과를 읽었는가"는 판정하지 않는다.** 훅은 한 번의 도구 호출만 본다.
막는 것은 정확히 하나 — 한 호출 안에서 검증 뒤에 상태 변경이 오는 형태다. 나머지는
규범(`rules/definition-of-done.md`)과 `control-loop` 스킬의 서술로 성립한다.
**없는 보호를 있다고 믿지 마라.**

## 근거 (실측 n=2, 서로 독립, 같은 날 다른 두 세션)

1. PR 상태 4축 검증이 `FAILURE`/`UNSTABLE` 을 **출력했는데**, 같은 Bash 블록 다음 줄의
   `gh pr merge` 가 조건 없이 실행돼 CI 실패 상태로 main 머지
2. `pytest`/`ruff` 뒤에 `commit`·`push` 를 `;` 로 체인 — 린트 오류가 main 에 올라감

n=2 면 개인 부주의가 아니라 **도구가 유도하는 형태**로 본다.
