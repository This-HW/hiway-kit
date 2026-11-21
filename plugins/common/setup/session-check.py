#!/usr/bin/env python3
"""SessionStart hook: 로컬 환경의 실재 결함만 사용자에게 알린다 (rules 주입은 session-start.py 전담).

**소비자 레포에 아무것도 쓰지 않는다.** v5.0.0 전까지 이 훅은 plugin-only 모드에서
`.git/hooks/pre-commit` 을 묻지 않고 설치·갱신했다 — 세션 시작이라는 부수효과 없는
이벤트가 사용자 레포의 실행 파일을 바꾸는 동작이었다. 설치는 이제 `setup.sh` 의
명시적 opt-in 경로뿐이다.

경고는 stderr 가 아니라 `systemMessage` 로 낸다 — SessionStart 훅의 stderr 는 모델도
사용자도 보지 못한다. 대상은 **정상 운영에서 거짓인 조건**뿐이다
(`docs/conventions/warning-signal.md`): 파이썬 하한·낡은 venv·에이전트 이중 로드·킷 이중 설치.
(5.7.2 전에는 setup.sh 사용자에게 전역 ruff.toml·init.templateDir 누락도 알렸다 — 이제 setup.sh 가
앞의 것은 설치하지 않고 뒤의 것은 묻고 나서만 켜므로, 그 조건은 결함이 아니라 사용자의 선택이다.)

`--conflicts <프로젝트 루트>` 로 부르면 훅이 아니라 이름 충돌 목록(JSON)만 출력한다 —
`setup.sh --migrate` 가 같은 판정을 쓰도록 한 곳에 둔다(판정이 둘로 갈라지면 경고는
A 를 말하고 이주는 B 를 옮긴다).
"""

from __future__ import annotations

import json
import os
import pathlib
import re
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


def _frontmatter_name(path: pathlib.Path):
    """파일 첫 frontmatter 블록의 `name:` 값. 없거나 읽을 수 없으면 None.

    yaml 의존 없이 앞 8KB 만 줄 단위로 본다 — 세션 시작 지연을 막고, 깨진 파일 하나가
    검사 전체를 죽이지 않게 한다.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(8192).decode("utf-8", "replace")
    except OSError:
        return None
    lines = head.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"name:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip("'\"") or None
    return None


_SCAN_LIMIT = 500  # 파일 수 상한 — 거대한 에이전트 디렉토리가 세션 시작을 붙들지 않게


def _agent_files(root: pathlib.Path) -> list:
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.md"))[:_SCAN_LIMIT]


def _skill_dirs(root: pathlib.Path) -> list:
    """`<root>/<dir>/SKILL.md` 를 가진 디렉토리."""
    if not root.is_dir():
        return []
    return sorted(d for d in root.iterdir() if (d / "SKILL.md").is_file())[:_SCAN_LIMIT]


def find_name_conflicts(
    project_claude: pathlib.Path, plugin_root: pathlib.Path
) -> list:
    """프로젝트 `.claude/{agents,skills}` 항목 중 플러그인과 **이름이 겹치는 것**.

    반환: `{"kind": "agent"|"skill", "name": 이름, "path": project_claude 기준 상대경로}`
    목록. 스킬의 path 는 SKILL.md 가 아니라 **스킬 디렉토리**다(옮길 단위).
    이름 = frontmatter `name:`, 없으면 파일명 stem(스킬은 디렉토리명). 플러그인 쪽은
    `name:` 이 있는 정의만 센다(README 같은 비정의 파일이 프로젝트의 같은 파일명과
    겹쳐 오탐하지 않게).

    플러그인 루트에 `agents/`·`skills/` 가 모두 없으면(루트를 못 찾은 것) 빈 목록 —
    판정 근거가 없으면 경고하지 않는다(fail-open).
    """
    plugin_agents = plugin_root / "agents"
    plugin_skills = plugin_root / "skills"
    if not (plugin_agents.is_dir() or plugin_skills.is_dir()):
        return []

    agent_names = {n for n in map(_frontmatter_name, _agent_files(plugin_agents)) if n}
    skill_names = {
        _frontmatter_name(d / "SKILL.md") or d.name for d in _skill_dirs(plugin_skills)
    }

    conflicts = []
    agents_dir = project_claude / "agents"
    for f in _agent_files(agents_dir):
        name = _frontmatter_name(f) or f.stem
        if name in agent_names:
            conflicts.append(
                {
                    "kind": "agent",
                    "name": name,
                    "path": f.relative_to(project_claude).as_posix(),
                }
            )
    for d in _skill_dirs(project_claude / "skills"):
        name = _frontmatter_name(d / "SKILL.md") or d.name
        if name in skill_names:
            conflicts.append(
                {
                    "kind": "skill",
                    "name": name,
                    "path": d.relative_to(project_claude).as_posix(),
                }
            )
    return conflicts


def _printable(name: str) -> str:
    """파일에서 읽은 이름은 터미널 이스케이프가 섞일 수 있다 — 제어문자를 걷고 길이를 줄인다."""
    return "".join(c for c in name if c.isprintable())[:60]


def _conflict_warning(conflicts: list) -> str:
    shown = []
    for c in conflicts:
        label = f"{c['kind']} {_printable(c['name'])}"
        if label not in shown:
            shown.append(label)
    head = ", ".join(shown[:3]) + (f" 외 {len(shown) - 3}건" if len(shown) > 3 else "")
    return (
        f".claude/ 의 프로젝트 정의 {len(conflicts)}개가 플러그인과 이름이 겹칩니다 ({head}) — "
        f"그 파일을 지우거나 이름을 바꾸세요. 플러그인 쪽은 `{PLUGIN}:` 네임스페이스로 "
        "이미 로드됩니다"
    )


# ── 이중 설치 ─────────────────────────────────────────────────────────────
#
# 전임 이름도 같은 킷이다 — 개명 전 설치본이 남아 있으면 스킬·훅이 이름만 다른 채 겹친다.
_PREDECESSOR_NAMES = {"claude-code-kit"}  # old-name-ok: 전임 설치 탐지
_SWITCH_DOC = "docs/harnesses.md#keep-one-install"
# 1 MiB — 설정 파일이 비정상적으로 커도 세션 시작을 붙들지 않는다
_JSON_READ_LIMIT = 1 << 20


def _read_json(path: pathlib.Path):
    """작은 JSON 파일을 읽는다. 없거나·크거나·깨졌으면 None (fail-open).

    깊게 중첩된 JSON 은 1 MiB 안에서도 `json.loads` 를 `RecursionError` 로 죽인다(`ValueError` 가
    아니다). 예전에는 그것이 `collect_warnings()` 전체를 끊어 python 하한·낡은 venv·이름 충돌 경고까지
    사라졌다(리뷰 L-005) — 깨진 설정과 같이 None 으로 본다.
    """
    try:
        with open(path, "rb") as fh:
            raw = fh.read(_JSON_READ_LIMIT + 1)
    except OSError:
        return None
    if len(raw) > _JSON_READ_LIMIT:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None


def _same_dir(a, b: pathlib.Path) -> bool:
    try:
        return isinstance(a, str) and os.path.realpath(a) == os.path.realpath(str(b))
    except (OSError, ValueError):
        return False


def _enabled(plugin_id: str, settings: list):
    """가장 구체적인 설정(local → project → user)에서 이 ID 의 `enabledPlugins` 값. 없으면 None."""
    for data in settings:
        flags = data.get("enabledPlugins") if isinstance(data, dict) else None
        if isinstance(flags, dict) and isinstance(flags.get(plugin_id), bool):
            return flags[plugin_id]
    return None


def find_kit_installs(config_dir: pathlib.Path, project_dir: pathlib.Path) -> list:
    """이 프로젝트에서 **켜진 채 적용되는** 킷 설치 ID 목록(정렬). 둘 이상이면 이중 설치다.

    이 검사가 도는 조건(한 문장): Claude Code 설정 디렉토리의 `plugins/installed_plugins.json`
    이 실측한 형식(`version: 2`)이고, 이름이 이 킷(또는 전임)인 서로 다른 설치 ID 가 둘 이상
    이 프로젝트에 적용되는 범위(user, 또는 projectPath 가 이 프로젝트인 project·local)로 설치돼
    가장 구체적인 설정의 `enabledPlugins` 에서 `true` 일 때.

    정상 운영에서 이 조건은 거짓이다 — 채널을 하나만 쓰면 ID 가 하나이고, 같은 ID 를 user·project
    두 범위에 깐 것은 Claude Code 가 한 번만 로드한다(2.1.330 실측: 훅 1회). 그래서 ID 를 센다.

    **플러그인 캐시 디렉토리는 보지 않는다.** `plugin uninstall`·`marketplace remove` 뒤에도
    `plugins/cache/<마켓>/<이름>/<판>/` 이 남는다(2.1.330 실측) — 캐시의 형제 디렉토리로 판정하면
    문서대로 채널을 바꾼 사용자에게 상시 참인 경고가 된다(warning-signal.md §1).

    **훅 2회 실행(세션 마커)도 신호로 쓰지 않는다.** 이름이 같은 두 설치(디렉토리판 + 직접
    마켓)는 Claude Code 가 훅을 한 번만 등록하고(“Skipping duplicate hook registration”),
    이름이 다른 전임 설치는 이 코드를 갖고 있지 않다 — 그 신호는 도달할 수 없다(§검토 4).

    탐지 못 하는 것: 형식이 바뀐 `installed_plugins.json`(침묵한다), 관리형(managed) 설정이
    켜거나 끈 플러그인, `--plugin-dir` 로 띄운 사본, 다른 하네스(Codex·Antigravity)의 설치.
    """
    data = _read_json(config_dir / "plugins" / "installed_plugins.json")
    if not isinstance(data, dict) or data.get("version") != 2:
        return []
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return []
    settings = [
        _read_json(project_dir / ".claude" / "settings.local.json"),
        _read_json(project_dir / ".claude" / "settings.json"),
        _read_json(config_dir / "settings.json"),
    ]
    names = {PLUGIN, *_PREDECESSOR_NAMES}
    found = []
    for plugin_id, entries in plugins.items():
        if not isinstance(plugin_id, str) or plugin_id.rpartition("@")[0] not in names:
            continue
        if not isinstance(entries, list):
            continue
        applies = any(
            isinstance(e, dict)
            and (
                e.get("scope") == "user"
                or (
                    e.get("scope") in ("project", "local")
                    and _same_dir(e.get("projectPath"), project_dir)
                )
            )
            for e in entries
        )
        if applies and _enabled(plugin_id, settings) is True:
            found.append(plugin_id)
    return sorted(found)


def _doc_link() -> str:
    """경고가 가리킬 해결 문서. 소비자 환경엔 docs/ 가 없으므로 매니페스트의 저장소 URL 로 만든다."""
    try:
        manifest = SETUP_DIR.parent / ".claude-plugin" / "plugin.json"
        repo = json.loads(manifest.read_text(encoding="utf-8")).get("repository")
        if isinstance(repo, str) and repo.startswith("https://"):
            path, _, anchor = _SWITCH_DOC.partition("#")
            return f"{repo.rstrip('/')}/blob/main/{path}#{anchor}"
    except Exception:
        pass
    return _SWITCH_DOC


def _dual_install_warning(ids: list) -> str:
    shown = ", ".join(_printable(i) for i in ids[:3]) + (
        f" 외 {len(ids) - 3}개" if len(ids) > 3 else ""
    )
    return (
        f"이 킷이 설치 ID {len(ids)}개로 겹쳐 켜져 있습니다 ({shown}) — 스킬이 중복 로드되고 "
        "훅·에이전트는 어느 한 설치의 판만 쓰여 판이 섞입니다. 하나만 남기세요"
        f"(`claude plugin uninstall <ID>`): {_doc_link()}"
    )


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
    # UP036 예외: 하한 미만 인터프리터를 잡는 것이 이 검사의 목적이다(그 규칙은 하한 이상만 가정한다).
    # f-string 은 3.6+ 이고 이 파일은 `from __future__ import annotations`(3.7+) 로 이미 그 위에 있다.
    if sys.version_info < (3, 9):  # noqa: UP036
        major, minor = sys.version_info[0], sys.version_info[1]
        warnings.append(
            f"python3 {major}.{minor} 감지 — kit 훅은 3.9+ 필요. auto-format·stop-validator 등이 "
            "동작하지 않습니다 (python3 업그레이드 또는 PATH 확인)"
        )

    # 이중 설치 — 조건은 find_kit_installs() docstring. git 저장소가 아니어도 돈다.
    config_dir = pathlib.Path(
        os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    )
    project_dir = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    # 별도 try — 이 검사는 사용자 설정 파일(남이 쓴 JSON)을 읽는다. 여기서 무엇이 터져도 아래 검사들은
    # 돌아야 하고, 터진 사실은 이 검사 이름으로 보여야 한다(조용히 빠지면 "이중 설치 없음"과 구분되지 않는다).
    try:
        installs = find_kit_installs(config_dir, project_dir)
    except Exception as e:
        warnings.append(f"이중 설치 검사 내부 오류(이 검사만 생략): {e!r}")
        installs = []
    if len(installs) > 1:
        warnings.append(_dual_install_warning(installs))

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

    # dual-load — 프로젝트 `.claude/{agents,skills}` 의 정의가 플러그인 정의와 **이름이
    # 겹칠 때만**. 이 검사가 도는 조건: 플러그인 루트(이 파일의 부모)에 agents/ 또는 skills/
    # 가 있고, 프로젝트 정의의 name 이 그 집합과 교집합이 있을 때 — 프로젝트 로컬 에이전트는
    # 킷이 권장하는 2-Tier 구조라 "에이전트가 있다"는 상시 참이고, 그 조건으로 경고하면 죽는다.
    conflicts = find_name_conflicts(repo_root / ".claude", SETUP_DIR.parent)
    if conflicts:
        warnings.append(_conflict_warning(conflicts))
    return warnings


def main() -> None:
    if sys.argv[1:2] == ["--conflicts"]:
        # setup.sh --migrate 용 — 훅 출력 계약(항상 exit 0)과 무관한 CLI 모드.
        project = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else ".")
        print(json.dumps(find_name_conflicts(project / ".claude", SETUP_DIR.parent)))
        sys.exit(0)
    sys.path.insert(0, str(SETUP_DIR.parent / "hooks"))
    try:
        from utils import hook_disabled
    except ImportError:
        hook_disabled = None
    if hook_disabled is not None and hook_disabled("session-check"):
        sys.exit(0)
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
