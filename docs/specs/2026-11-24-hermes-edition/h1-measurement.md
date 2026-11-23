---
status: current
as_of: 2026-11-24
---

# Hermes H1 격리 실측

[설계 판정](design-verdict.md)의 1단계 기록이다. 킷 기준 커밋은
`6c6b75dbfc6075d31c504a196eda8ec8b49081a2`, 추적 중인 `plugins/common` 트리는
`fde37294e02e6a925e534ebce4f402c826892dd6`다. P0의 디렉터리 복사본은 `diff -qr`로
워크트리 원본과 대조했다(rc 0). P0의 로컬 Git 설치에는 추적 파일만 담았다.
생성판 `tree_sha: 미측정`.

## 환경과 명령 표기

`R=/private/tmp/hermes-h1`. 표의 `sb off`와 `sb install`은 아래 런처로 실행한 명령을 뜻한다.
각 원 로그에는 환경 인자, 실행 파일의 절대경로, 작업 디렉터리, stdout·stderr, rc가 있다.
샌드박스 밖에서 원 로그를 `~/.cache/hiway-research/hermes/h1/`에 복사했다.

```sh
R=/private/tmp/hermes-h1
PROFILE="$PWD/scripts/hermes-sandbox.sb"
sb() {
  mode=$1
  shift
  /usr/bin/env -i HOME="$R/home" HERMES_HOME="$R/hermes-home" TMPDIR="$R/tmp" \
    XDG_CONFIG_HOME="$R/xdg/config" XDG_DATA_HOME="$R/xdg/data" \
    XDG_CACHE_HOME="$R/xdg/cache" XDG_STATE_HOME="$R/xdg/state" \
    XDG_RUNTIME_DIR="$R/xdg/runtime" PIP_CACHE_DIR="$R/pip-cache" \
    PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_INPUT=1 \
    PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 GIT_CONFIG_NOSYSTEM=1 \
    GIT_TERMINAL_PROMPT=0 PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin \
    LC_ALL=en_US.UTF-8 TERM=dumb \
    /usr/bin/sandbox-exec -D "HERMES_NETWORK=$mode" -f "$PROFILE" "$@"
}
H="$R/venv-main-314/bin/hermes"
```

- `/usr/bin/sw_vers`, `/usr/bin/uname -m` (각 rc 0)에서 macOS 27.2.1 (26B131), arm64를 확인했다.
- `/usr/bin/codesign -dv /usr/bin/sandbox-exec` (rc 0)은 `com.apple.sandbox-exec`, Mach-O arm64e를 출력했다.
  `sb off /usr/bin/git --version` (rc 0)은 Apple Git 2.54.0을 출력했다.
- `/opt/homebrew/bin/python3.11 --version` (rc 0)은 3.11.18,
  `sb off /opt/homebrew/bin/python3.14 --version` (rc 0)은 3.14.10이었다.
- `sb install /usr/bin/git clone --depth 1 --no-tags --revision="$sha" https://github.com/NousResearch/hermes-agent.git "$src"`와
  `sb off /usr/bin/git -C "$src" rev-parse HEAD`를 각 소스에 실행했다(각 rc 0).
  main은 `352b249f67fb6a4a7d7904acaca9dd410db229e0`, stable은
  `caafe5389ae585ef77387a962aee05b1bcf17029`와 일치했다.
- `sb off /opt/homebrew/bin/python3.11 -m venv "$venv"`로 별도 venv를 만들어
  두 SHA를 각각 `sb install "$venv/bin/python" -m pip install -e "$src"`로 설치했다(각 명령 rc 0).
  `sb off "$venv/bin/hermes" --version`은 main에서 `Hermes Agent vgit.352b249 (2026.9.24)`,
  stable에서 `Hermes Agent vgit.caafe53 (2026.9.24)`를 출력했다(각 rc 0, 두 환경에서 OpenAI SDK 미설치).
  stable 관측은 설치와 버전 확인까지다.

## 샌드박스 양성 대조

[프로필](../../../scripts/hermes-sandbox.sb)의 `-D HERMES_NETWORK=off`는 측정용,
`-D HERMES_NETWORK=install`은 설치와 GitHub 무ref 대조용이다. 두 모드에서 쓰기 허용 범위와 홈 읽기 거부는 같다.
프로필 SHA-256은 `2dd510170462828e9f82f21c7c883833ad9522aee48e1e97ed49bf08e4c544fc`다.

`/opt/homebrew/bin/python3.11 -B "$R/recheck.py" uv-314` (rc 0)는 두 모드에서
`sb "$mode" /opt/homebrew/bin/python3.11 "$R/probe.py" "uv-314-$mode" "$outside" "$secret_paths"…`를 실행했다.
두 대조의 rc는 각각 0이다. 격리 루트 안에 테스트 파일을 썼고 실제 홈의 새 파일 생성은 `EPERM`으로 거부됐다.
존재하는 비밀 경로 열기 10건도 모두 `EPERM`이었다. 대조 경로에는 실제 `~/.hermes`와 그 안의
`.env`, `auth.json`, `config.yaml`, 그 밖에 `.ssh`, `.config`, `.docker`, `.claude`, `.codex`,
`Library/Keychains`가 포함된다. `off`에서 `127.0.0.1:0` 연결도 `EPERM`이었다.
처음에는 홈 전체를 차단했고 이후 Hermes 비밀 경로를 프로필에 명시해 다시 대조했다.

## 설치 과정

| 명령 | rc | 관측 |
| --- | --- | --- |
| 3.11 venv에서 `sb off "$R/venv-main/bin/hermes" plugins validate "$R/src/main-common" --json` 및 `plugins install "$R/src/main-common" --no-enable` | 각각 1 | 둘 다 CLI 시작 중 `ModuleNotFoundError: No module named 'ruamel'`. 매니페스트 판정 미도달. |
| main 소스에서 3.11 venv의 `sb install "$R/venv-main-311-wheel/bin/python" -m pip install .` | 1 | `RuntimeError: Building wheels or sdists for hermes-agent is not supported.` upstream은 editable 설치를 안내한다. |
| `sb off /opt/homebrew/bin/python3.14 -m venv "$R/venv-main-314"` 및 `sb install "$R/venv-main-314/bin/python" -m pip install -e "$R/src/hermes-main"` | 0, 1 | 3.14 venv는 생성됐다. pip 해석은 `Pillow==13.0.0`과 `browser-harness==0.1.13`이 요구하는 `pillow==12.3.0` 충돌로 `ResolutionImpossible`. |
| main 소스에서 `sb install /opt/homebrew/bin/uv sync --frozen --python /opt/homebrew/bin/python3.14` | 0 | upstream `uv.lock`의 Pillow 13.0.0 override를 그대로 사용했다. `git diff --exit-code HEAD -- uv.lock`은 rc 0. |
| `sb off "$H" --version` | 0 | `Hermes Agent vgit.352b249 (2026.9.24) · stable · local 352b249f67fb`, `Install method: git`, Python 3.14.10, OpenAI SDK 2.54.0. 네트워크 차단으로 안정판 조회에는 실패했다. |

3.11은 upstream의 구형 설치 갱신용이다. `pyproject.toml`은 `ruamel.yaml` 등 런타임 의존성을
`python_version >= '3.14'` 조건에 둔다. 컨트롤러 승인으로 실제 홈 밖의 Homebrew Python 3.14로 전환했다.
uv에는 `UV_PROJECT_ENVIRONMENT=$R/venv-main-314`, `UV_CACHE_DIR=$R/uv-cache`,
`UV_PYTHON_INSTALL_DIR=$R/uv-python`, `UV_TOOL_DIR=$R/uv-tools`, `UV_PYTHON_DOWNLOADS=never`를 넣었다.

### Hermes 관리형 런타임 준비

초기 오프라인 설치가 관리형 Python 다운로드에서 막혔다. 컨트롤러 승인 뒤
`sb install "$H" pm install python uv` (rc 0)를 실행했다. 출력은
`Preparing the isolated Hermes runtime…`, `✓ python`, `✓ uv`였다. 격리 홈의
`$R/hermes-home/tools/facts.json`에 macOS arm64 설치 버전과 아티팩트 해시가 기록됐다.
아래 URL은 고정 커밋의 PM 잠금 파일에 기록된 주소다.

| 설치한 도구 | 버전 | SHA-256 | 잠금 파일 URL |
| --- | --- | --- | --- |
| Python | `3.14.9+20261021` | `226d696642a8a53d03b4d5b255b1c319b1575a6d44bd723a953c9f507755e36a` | [Python 아카이브](https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-3.14.9+20261021-aarch64-apple-darwin-install_only.tar.gz) |
| uv | `0.13.5` | `743f85035a1996ecb350659e01cd9faea9709829be09b1b4b03c73eaf3c9cd73` | [uv 아카이브](https://github.com/astral-sh/uv/releases/download/0.13.5/uv-aarch64-apple-darwin.tar.gz) |

첫 관리형 설치 뒤 고정 SHA 설치는 성공했다. 활성화·비활성화는 관리형 코어 의존성을 내려받으려다
오프라인에서 각각 `pydantic==2.14.1`, `httpcore==1.0.9` 조회가 실패했다.
두 명령은 rc 1이었고 격리 홈의 설정 파일은 계속 부재했다. 활성화 전에 코어를 준비하기 위해
`sb install "$R/venv-main-314/bin/python" -c 'from pm.client import sync_venv; sync_venv(explicit=True)'`를 실행했다.
동기화와 이후 `sb off /usr/bin/git -C "$R/src/hermes-main" diff --exit-code HEAD -- uv.lock pm/lock.json`는 각각 rc 0이었다.

샌드박스 밖에서 `/opt/homebrew/bin/python3.11 -B "$R/local_inventory.py" capture "$snapshot"`을
각 준비 단계 전후에 실행했다. 같은 스크립트의 `compare "$before" "$after"` (rc 0)로 확인한 변경은
모두 `$R` 안에 있었다. 관리형 도구 설치의 추가 항목은 `hermes-home` 2,253개,
`src` 4개, `tmp` 1개였다. 코어 동기화는 `hermes-home`에 21,972개를 추가하고 1개를 수정했으며
`tmp`에 2개를 추가했다. 관리형 도구와 런타임은 `$R/hermes-home/tools`와
`$R/hermes-home/installs` 아래에서 확인했다.

## P0 음성 대조

| 명령 | rc | 관측 |
| --- | --- | --- |
| `sb off "$H" plugins validate "$R/src/main-common" --json` | 1 | `portable manifest` 검사 실패. `plugin.json declares an unsupported or missing Agent Plugins schema`. |
| `sb off "$H" plugins install "$R/src/main-common" --no-enable` | 1 | 절대경로를 GitHub shorthand로 읽어 `https://github.com/private/tmp.git` 복제를 시도했다. 오프라인 DNS에서 실패해 매니페스트 판정에 도달하지 않았다. |
| `sb install "$H" plugins install This-HW/hiway-kit/plugins/common --no-enable` | 1 | HTTPS 복제 후 `Portable plugin manifest validation failed: plugin.json declares an unsupported or missing Agent Plugins schema`. 설치된 항목은 없었다. |
| `sb off "$H" plugins install "file://$R/git/main-common-exact.git" --ref 3a933d931a8a3a2634eb2adaecaa4453b55b14cf --no-enable` | 1 | 정확한 원본 트리를 오프라인에서 복제한 뒤 같은 AP 스키마 오류로 거부했다. |

`git archive --format=tar -o "$R/kit-tree.tar" HEAD:plugins/common` (rc 0)으로 추적 파일을
내보내 임시 Git 저장소에 커밋하고 bare 저장소로 복제했다. 이 저장소의
`git rev-parse HEAD 'HEAD^{tree}'` (rc 0)에서 트리 SHA가 기준 트리와 일치했다.
처음 디렉터리 복사본에 있던 무시 대상 Python 바이트코드 파일 1개는 이 트리에 포함되지 않았다.

main SHA의 `hermes_cli/plugins_cmd.py`에 있는 `_resolve_git_url`은 `file://`를 Git URL로 넘긴다. <!-- doc-ref-ok: 고정 SHA의 외부 Hermes 소스 -->
스킴이 없는 경로는 `owner/repo[/subdir]`로 분석한다. 절대경로의 첫 두 조각은 `private/tmp`이고
`./min-ap`는 `.`을 owner, `min-ap`를 repo로 읽는다.
`hermes_cli/plugins_cmd_git.py`의 `_clone_plugin_repo`가 URL을 `git clone`에 넘긴다. <!-- doc-ref-ok: 고정 SHA의 외부 Hermes 소스 -->
2단계 생성판 디렉터리를 실측하려면 그 트리를 격리 루트에서 Git 커밋으로 만들고, 임시 저장소의
`file://` URL과 40자 `--ref`를 사용한다. URL에 `#subdir`를 붙이는 문법도 소스에 있다.

## 최소 AP 양성 대조와 P5′ 사전조사

최소 패키지의 이름은 `h1-probe`이고 매니페스트의 스키마는
`https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`이다. `h1-only` 스킬 하나를 넣었다.

| 명령 | rc | 관측 |
| --- | --- | --- |
| `sb off "$H" plugins validate "$R/src/min-ap" --json` | 0 | AP v1 파싱, 보안 스캔 `safe`, 격리 판정 `portable`, `host_ready: true`. |
| `sb off "$H" plugins install "$R/src/min-ap" --no-enable` | 1 | P0의 직접 경로 설치와 같은 GitHub shorthand 해석. |
| `sb off /usr/bin/git -C "$R/src/min-ap" init -b main`, `add plugin.json skills/h1-only/SKILL.md`, `commit --no-gpg-sign -m 'Minimal portable plugin'`, `git clone --bare "$R/src/min-ap" "$R/git/hermes-test.git"`, `git -C "$R/git/hermes-test.git" rev-parse HEAD` | 모두 0 | 픽스처 커밋 `4aca0cc473a7f7b6ea00a4b0c9bf5b46178b4796`. |
| `sb off "$H" plugins install "file://$R/git/hermes-test.git" --ref 4aca0cc473a7f7b6ea00a4b0c9bf5b46178b4796 --no-enable` | 첫 시도 1 | 로컬 복제와 매니페스트 판정을 지나 게시 직전 실패. Hermes PM이 관리형 Python 3.14.9를 내려받으려 했고 네트워크가 차단됐다. |
| `sb off /opt/homebrew/bin/python3.11 -B "$R/config_report.py" compare before-install after-failed-install` | 0 | 격리 홈의 config.yaml은 설치 시도 전후 모두 부재. |

관리형 도구와 코어 환경 준비 뒤 다음 순서로 오프라인에서 대조했다.

| 명령 | rc | 관측 |
| --- | --- | --- |
| `sb off "$H" plugins install "file://$R/git/hermes-test.git" --ref 4aca0cc473a7f7b6ea00a4b0c9bf5b46178b4796 --no-enable` | 0 | 플러그인을 설치하고 비활성 상태로 남겼다. 설치 위치에서 `git rev-parse HEAD` (rc 0)로 고정 SHA 일치를 확인했다. |
| `sb off "$H" plugins list` (설치 직후) | 0 | `h1-probe`, `not enabled`, `pinned@4aca0cc4`. |
| `sb off "$H" plugins enable h1-probe` 및 `sb off "$H" plugins list` | 각각 0 | `Plugin h1-probe enabled.` 목록에서 `enabled`로 표시됐다. |
| `sb off "$H" skills list --enabled-only` | 0 | 이 CLI 목록에는 플러그인 스킬이 표시되지 않았다. |
| `sb off "$R/venv-main-314/bin/python" -c 'from tools.skills_tool import skills_list; print(skills_list())'` | 각각 0 | 에이전트의 `skills_list`에서 `h1-probe:h1-only`가 활성화 전 0개, 활성화 후 1개, 비활성화 후 0개였다. |
| `sb off "$H" plugins disable h1-probe` | 0 | `Plugin h1-probe disabled.` 격리 홈에는 실행 중인 게이트웨이가 없었다. |
| `sb off "$H" plugins remove h1-probe` 및 `sb off "$H" plugins list` | 각각 0 | 패키지 디렉터리가 제거됐고 목록에서도 사라졌다. |

격리 홈의 `config.yaml`을 `sb off /opt/homebrew/bin/python3.11 -B "$R/config_report.py" snapshot "$stage"`
(각 rc 0)로 보존했다. 같은 스크립트의 `compare "$before" "$after"`로 확인한 변화다.

| 단계 | 비교 rc | 설정 변화 |
| --- | --- | --- |
| 설치 전 → 설치 후 | 0 | 양쪽 모두 파일 부재. |
| 설치 후 → 활성화 후 | 1 | 파일 생성. `plugins.enabled`에 `h1-probe`를 넣고 `plugins.disabled`를 빈 목록으로 저장했다. |
| 활성화 후 → 비활성화 후 | 1 | `h1-probe`가 `plugins.disabled`로 이동했다. |
| 비활성화 후 → 제거 후 | 1 | 두 목록이 비었고 `_config_version: 54`가 추가됐다. 설정 파일은 남았다. |

## 실제 홈 대조

1차 시도를 중단했다. `/usr/bin/diff -u "$R/logs/home-before.json" "$R/logs/home-after.json"`는
rc 1이었다. 실제 `~/.hermes` 디렉터리의 mtime이 04:07:08에서 04:09:16(한국시각)으로 바뀌었다.
컨트롤러가 실제 게이트웨이(pid 59776)의 상태 파일 갱신을 확인했다. 같은 시도에서 3.11 CLI의 의존성 누락도 확인했다.

재개 후 호스트 셸의 `/opt/homebrew/bin/python3.11 -B "$R/home_inventory.py" capture "$snapshot"`로
파일명과 mtime을 기록하고 같은 스크립트의 `compare "$before" "$after"`로 차이를 분류했다.
`~/.agents`, `~/.config`, `~/.claude/plugins`, 셸 rc의 존재 여부와 mtime은 별도로 대조했다.
실제 Hermes 홈의 `config.yaml`, `.env`, `auth.json`, `plugins/`, `skills/`, `hooks/`,
`profiles/` 아래 변경은 중단 조건이다.

- 컨트롤러가 실제 게이트웨이 상태 및 cron 갱신을 확인한 뒤
  `gateway_state.json`, `channel_directory.json`, `cron/**`, `logs/**`, `cache/**`,
  `*.lock`, `.hermes_history`, `sessions/**`의 데몬 변경을 허용했다.
- 3.11 재시도의 파일 대조는 rc 1로 `kanban.db-shm`, `state/gateway.heartbeat`를 추가로 발견했다.
  워커 대기 중에도 갱신돼 컨트롤러가 두 파일과 `kanban.db-wal`을 데몬 목록에 추가했다.
- 3.14 pip 시도의 대조는 rc 1로 `state.db-wal`을 추가로 발견했다. 대기 중 mtime이 변했고
  `/usr/sbin/lsof -a -p 59776 /Users/hw/.hermes/state.db /Users/hw/.hermes/state.db-shm /Users/hw/.hermes/state.db-wal`
  (rc 0)에서 실제 게이트웨이의 쓰기 가능한 FD 3개를 확인했다. 컨트롤러가 WAL만 목록에 추가했다.
- uv 설치 및 첫 측정 구간의 파일 대조는 rc 0이었다. 승인된 데몬 변경 8건, 보호 대상 및 그 밖의 변경 0건이었다.
- 관리형 런타임 준비부터 최종 측정까지의 파일 대조는 rc 1이었다. 승인된 데몬 변경 9건 외에
  `~/.hermes/state.db-shm`과 `~/.claude/plugins` 디렉터리 mtime이 바뀌었다. 실제 Hermes 설정과
  플러그인 등 보호 대상의 파일 변경은 0건이었다. 컨트롤러의 귀속 확인 뒤 통과로 판정했다.
  원 비교 로그에는 rc 1을 그대로 보존했다.
- 컨트롤러의 `lsof`에서 `state.db-shm`을 연 프로세스는 실 Hermes 59705(21u), 59776(18u),
  83789(20u)였다. 이 파일을 데몬 관리 목록에 추가했다.
- `~/.claude/plugins`의 디렉터리 mtime은 04:19:58(한국시각)으로 바뀌었다. 내부의
  `installed_plugins.json`(02:29), `known_marketplaces.json`(02:48), 캐시(02:29),
  데이터 디렉터리(02:30)의 mtime은 측정 시작 전 시각 그대로였다. 그 시각 컨트롤러가 다른 Claude Code 세션에
  새 작업을 보냈다. 컨트롤러는 이 변화를 동시 실행 세션의 임시 항목으로 귀속했다. 이후 대조에서는
  해당 디렉터리의 파일 목록·mtime·크기를 비교한다.

## 2단계 미측정

- P0: 브라우저형 `tree/hermes/…` URL 거부.
- P1: 생성판의 보안 판정과 파일별 원인.
- P2: 생성판 스킬 15개의 활성화 전후 노출, `<available_skills>` 및 `skill_view`.
- P3: 생성판 설치·활성화·비활성화·제거의 잔여물 및 설정 변화.
- P4: 생성판의 AGENTS.md 가림과 로드.
- P5′: `--force --ref`로 고정 SHA 변경, 활성 상태 유지.
- P6: 생성판 스킬의 도구 경로와 Claude Code 캐시 교차 사용 여부.
- 내장 verify-on-stop, 스킬 생성 및 메모리와의 공존. 생성판 트리 SHA는 2단계에서 기록한다.
