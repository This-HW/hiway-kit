#!/usr/bin/env python3
"""SessionStart hook: 로컬 환경의 실재 결함만 사용자에게 알린다 (rules 주입은 session-start.py 전담).

**소비자 레포에 아무것도 쓰지 않는다.** v5.0.0 전까지 이 훅은 plugin-only 모드에서
`.git/hooks/pre-commit` 을 묻지 않고 설치·갱신했다 — 세션 시작이라는 부수효과 없는
이벤트가 사용자 레포의 실행 파일을 바꾸는 동작이었다. 설치는 이제 `setup.sh` 의
명시적 opt-in 경로뿐이다.

경고는 stderr 가 아니라 `systemMessage` 로 낸다 — SessionStart 훅의 stderr 는 모델도
사용자도 보지 못한다. 대상은 **정상 운영에서 거짓인 조건**뿐이다
(`docs/conventions/warning-signal.md`): 파이썬 하한·낡은 venv·에이전트 이중 로드,
그리고 setup.sh 를 실행한 사용자에게만 해당하는 전역 설정 누락.
"""

import json
import os
import pathlib
import subprocess
import sys

# D-012: __file__ 기반 경로 해결 (cwd 무관, Plugin 캐시 위치 무관)
SETUP_DIR = pathlib.Path(__file__).resolve().parent  # plugins/common/setup/


def _plugin_name() -> str:
    """로그 프리픽스에 쓸 플러그인 이름을 매니페스트(SSOT)에서 파생한다.

    하드코딩하지 않는다 — 개명 때 프리픽스만 옛 이름으로 남아 사용자에게 **존재하지
    않는 플러그인 이름**을 출력했다(D-3: 이름은 SSOT 에서 파생한다). 매니페스트를
    못 읽으면 디렉토리명으로 물러선다(fail-open — 로그 프리픽스가 세션을 막으면 안 된다).
    """
    try:
        manifest = SETUP_DIR.parent / ".claude-plugin" / "plugin.json"
        name = json.loads(manifest.read_text(encoding="utf-8")).get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    except Exception:
        pass
    return SETUP_DIR.parent.name


PLUGIN = _plugin_name()


def stale_venv_interp(venv_dir):
    """venv 콘솔 스크립트의 shebang이 이 venv 밖 python을 가리키면 그 경로를 반환한다.

    venv 스크립트(pytest·pip·ruff …)에는 생성 시점의 **절대경로** shebang이 구워진다.
    프로젝트 디렉토리를 옮기거나 복사하면 그 경로가 이전 위치에 고정된 채 남는데,
    `bin/python`은 진짜 바이너리(shebang 없음)라 계속 동작한다. 그래서 증상이
    "python은 되는데 pytest만 bad interpreter"로 쪼개져 원인 파악이 오래 걸리고,
    옛 경로가 아직 살아 있으면 **옛 venv의 site-packages로 조용히** 실행된다.

    판정 불가(절대경로 python shebang이 하나도 없는 relocatable venv 등)면 None —
    오탐 경고는 노이즈가 되어 전체 경고를 안 읽게 만든다. 침묵이 낫다.
    스캔은 bin 앞쪽 40개로 제한한다(SessionStart 지연 방지).
    """
    bindir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    if not bindir.is_dir():
        return None
    try:
        bindir_real = os.path.realpath(bindir)
        entries = sorted(bindir.iterdir())[:40]
    except OSError:
        return None
    for entry in entries:
        try:
            with open(entry, "rb") as fh:
                first = fh.readline(512)
        except OSError:
            continue  # 디렉토리·깨진 심링크·권한 — 다음 후보로
        if not first.startswith(b"#!"):
            continue  # 바이너리(bin/python 본체 포함) 또는 shebang 없는 파일
        tokens = first[2:].decode("utf-8", "replace").strip().split()
        if not tokens:
            continue
        interp = tokens[0]
        if not os.path.isabs(interp):
            continue  # `#!/usr/bin/env python` 류 — venv 귀속을 판정할 수 없다
        if not os.path.basename(interp).startswith("python"):
            continue  # `#!/bin/sh` 래퍼(uv --relocatable 등)
        # 링크를 **따라가지 않고** 디렉토리 기준으로 비교한다. venv의 `bin/python`은
        # 보통 시스템 python으로 가는 심링크라, shebang 경로 자체를 resolve()하면
        # 멀쩡한 venv도 전부 "밖을 가리킨다"로 오탐한다.
        # ValueError도 잡는다: NUL이 박힌 경로에서 realpath는 OSError가 아니라
        # ValueError를 낸다. 이게 새어나가면 **같은 try 안의 후속 검사(dual-load)가
        # 통째로 사라진다** — 침묵 실패를 막으려던 코드가 새 침묵 실패를 만드는 셈.
        try:
            if os.path.realpath(os.path.dirname(interp)) != bindir_real:
                return interp
        except (OSError, ValueError):
            continue
        return None  # 정상 shebang 확인 — 더 볼 필요 없다
    return None


def _run_git(args: list) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, timeout=5, check=False
    )


def collect_warnings() -> list:
    """관측 가능해야 할 실재 결함 목록. 각 검사가 도는 조건은 주석에 한 문장으로 적는다."""
    warnings = []

    # python floor — 훅은 이 인터프리터로 실행된다. 3.9 미만이면 다른 훅들이
    # import 시점에 죽는데, 훅은 fail-open이라 **아무 메시지 없이 조용히** 사라진다.
    # (이 파일 자체는 구버전에서도 로드되도록 3.10 문법을 쓰지 않는다.)
    if sys.version_info < (3, 9):
        warnings.append(
            "python3 %d.%d 감지 — kit 훅은 3.9+ 필요. auto-format·stop-validator 등이 "
            "동작하지 않습니다 (python3 업그레이드 또는 PATH 확인)"
            % (sys.version_info[0], sys.version_info[1])
        )

    # setup.sh 를 실행한 사용자(`~/.claude/.setup-state.json` 존재)에게만 도는 검사.
    # plugin-only 사용자에게는 이 조건이 **항상 참**이라 경고가 죽는다(ATK-005) —
    # 그래서 억제가 아니라 **조회 자체를 하지 않는다**.
    if (pathlib.Path.home() / ".claude/.setup-state.json").exists():
        if not (pathlib.Path.home() / ".config/ruff/ruff.toml").exists():
            warnings.append("ruff.toml 미설치 — setup.sh를 다시 실행하세요")
        try:
            if (
                _run_git(["config", "--global", "--get", "init.templateDir"]).returncode
                == 1
            ):
                warnings.append("init.templateDir 미설정 — setup.sh를 다시 실행하세요")
        except (OSError, subprocess.TimeoutExpired):
            pass  # 판정 불가 — 경고하지 않는다(오탐은 전체 경고를 안 읽게 만든다)

    # 아래는 git 저장소 안에서만 도는 검사.
    try:
        git_toplevel = _run_git(["rev-parse", "--show-toplevel"]).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        git_toplevel = ""
    if not git_toplevel:
        return warnings
    repo_root = pathlib.Path(git_toplevel)

    # stale venv — 프로젝트 디렉토리 이동/복사 후의 침묵 실패 (stale_venv_interp 참고)
    for venv_name in (".venv", "venv"):
        stale_interp = stale_venv_interp(repo_root / venv_name)
        if stale_interp:
            warnings.append(
                # !r — shebang은 파일에서 읽은 값이다. 터미널 이스케이프가 섞여도
                # 그대로 렌더되지 않도록 repr로 감싼다.
                f"{venv_name} 스크립트의 shebang이 프로젝트 밖 python을 가리킵니다 "
                f"({stale_interp!r}) — 디렉토리 이동/복사 후 stale 상태입니다. "
                f"재생성: rm -rf {venv_name} && python3 -m venv {venv_name} (의존성 재설치)"
            )
            break

    # dual-load — 프로젝트 `.claude/agents/` 에 에이전트 정의가 있을 때만 (CR-07)
    claude_agents = repo_root / ".claude/agents"
    if claude_agents.exists() and any(claude_agents.rglob("*.md")):
        warnings.append(
            ".claude/agents/ + Plugin 동시 감지! 에이전트 중복 로딩 위험. "
            "'setup.sh --migrate' 실행 권장"
        )
    return warnings


def main() -> None:
    try:
        warnings = collect_warnings()
    except Exception as e:
        # 검사 자체의 결함도 **보이게** 남긴다 — stderr 는 아무도 읽지 않는다.
        warnings = [f"session-check 내부 오류(설정 체크 생략): {e!r}"]

    output = {
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ""}
    }
    if warnings:
        output["systemMessage"] = f"[{PLUGIN}] ⚠ " + "; ".join(warnings)
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(0)  # 항상 허용 (SessionStart = fail-open)


main()
