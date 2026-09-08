#!/usr/bin/env python3
"""SessionStart hook: 로컬 설정 체크 + 경고 (rules 주입은 session-start.py 전담)"""

import json
import os
import pathlib
import subprocess
import sys

# D-012: __file__ 기반 경로 해결 (cwd 무관, Plugin 캐시 위치 무관)
SETUP_DIR = pathlib.Path(__file__).resolve().parent  # plugins/common/setup/

# 킷이 자기 훅으로 심은 pre-commit 을 식별하는 마커. `setup/pre-commit` 첫 주석과
# 같아야 한다 — 이 문자열이 있으면 "킷이 심은 것"이므로 갱신해도 안전하고, 없으면
# 사용자가 직접 만든 훅이므로 **절대 건드리지 않는다**.
HOOK_MARKER = b"# Auto-installed by session-check.py"


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

warnings = []


def _default_git_hooks_dir(repo_root: pathlib.Path) -> pathlib.Path:
    """저장소의 기본 hooks 디렉토리를 `git rev-parse --git-path hooks` 로 얻는다.

    `repo_root / ".git/hooks"` 로 조립하면 **워크트리에서 깨진다** — 워크트리의
    `.git` 은 디렉토리가 아니라 gitdir 포인터 파일이라 `.git/hooks` 접근이
    ENOTDIR 로 실패하고, 이 킷이 권장하는 운영 형태(isolation: worktree,
    parallel-worktree)에서 **매 세션 경고가 발화**했다 (D-51 위반).

    `--git-path` 는 워크트리에서 공용 hooks 절대경로를, 주 체크아웃에서 상대경로를
    각각 올바르게 돌려준다. 상대경로일 수 있으므로 repo_root 기준으로 resolve 한다.
    """
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=5, check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return (repo_root / r.stdout.strip()).resolve()
    except (OSError, subprocess.TimeoutExpired):
        pass
    # git 조회 실패 시에도 침묵하지 않되, 조립은 하지 않는다 — 판정 불가는 None 이 아니라
    # 기존 관례대로 최선 추정을 쓰되 호출부가 존재 검사를 한다.
    return (repo_root / ".git" / "hooks").resolve()


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


# ── 1. 설정 체크 / 경고 ──────────────────────────────────────────────────────
try:
    # 1z. python floor — 훅은 이 인터프리터로 실행된다. 3.9 미만이면 다른 훅들이
    # import 시점에 죽는데, 훅은 fail-open이라 **아무 메시지 없이 조용히** 사라진다.
    # 침묵 대신 한 줄 경고로 관측 가능하게 만든다 (이 파일 자체는 구버전에서도 로드됨).
    if sys.version_info < (3, 9):
        warnings.append(
            "python3 %d.%d 감지 — kit 훅은 3.9+ 필요. auto-format·stop-validator 등이 "
            "동작하지 않습니다 (python3 업그레이드 또는 PATH 확인)"
            % (sys.version_info[0], sys.version_info[1])
        )

    # ATK-005: Plugin-only 사용자(setup.sh 미실행)에게 경고 피로 방지
    setup_state = pathlib.Path.home() / ".claude/.setup-state.json"
    is_plugin_only = not setup_state.exists()

    # 1a. 전역 설정 누락 경고 (풀 모드 전용)
    ruff_dst = pathlib.Path.home() / ".config/ruff/ruff.toml"
    if not ruff_dst.exists() and not is_plugin_only:
        warnings.append("ruff.toml 미설치 — setup.sh를 다시 실행하세요")

    try:
        tpl_result = subprocess.run(
            ["git", "config", "--global", "--get", "init.templateDir"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if tpl_result.returncode == 1 and not is_plugin_only:
            warnings.append("init.templateDir 미설정 — setup.sh를 다시 실행하세요")
    except subprocess.TimeoutExpired:
        warnings.append("git config 조회 시간 초과 (init.templateDir)")

    # 1b. 현재 repo 로컬 설정
    git_toplevel = ""
    try:
        git_toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout.strip()
    except subprocess.TimeoutExpired:
        warnings.append("git rev-parse 시간 초과")

    if git_toplevel:
        repo_root = pathlib.Path(git_toplevel)

        # D-015: core.hooksPath 확인 (H-1, IM-04)
        raw_hooks_path = ""
        try:
            hooks_path_result = subprocess.run(
                ["git", "config", "core.hooksPath"],
                capture_output=True,
                text=True,
                cwd=git_toplevel,
                timeout=5,
                check=False,
            )
            raw_hooks_path = hooks_path_result.stdout.strip()
            if hooks_path_result.returncode == 0 and raw_hooks_path:
                p = pathlib.Path(raw_hooks_path)
                candidate = (p if p.is_absolute() else (repo_root / p)).resolve()
                # path traversal 방어: repo_root 상위로 탈출 차단
                try:
                    candidate.relative_to(repo_root.resolve())
                    git_hooks_dir = candidate
                except ValueError:
                    # ATK-008: path traversal 감지 시 경고 메시지 추가
                    warnings.append(
                        f"core.hooksPath가 repo 외부를 가리킵니다: {raw_hooks_path!r}. "
                        "기본 .git/hooks를 사용합니다."
                    )
                    git_hooks_dir = _default_git_hooks_dir(repo_root)
            else:
                git_hooks_dir = _default_git_hooks_dir(repo_root)
        except subprocess.TimeoutExpired:
            warnings.append("git config core.hooksPath 시간 초과")
            git_hooks_dir = _default_git_hooks_dir(repo_root)

        # 1c. stale venv 감지 — 프로젝트 디렉토리 이동/복사 후의 침묵 실패 (stale_venv_interp 참고)
        for venv_name in (".venv", "venv"):
            stale_interp = stale_venv_interp(repo_root / venv_name)
            if stale_interp:
                warnings.append(
                    # !r — shebang은 파일에서 읽은 값이다. 터미널 이스케이프가 섞여도
                    # 그대로 렌더되지 않도록 repr로 감싼다(core.hooksPath 경고와 동일 관례).
                    f"{venv_name} 스크립트의 shebang이 프로젝트 밖 python을 가리킵니다 "
                    f"({stale_interp!r}) — 디렉토리 이동/복사 후 stale 상태입니다. "
                    f"재생성: rm -rf {venv_name} && python3 -m venv {venv_name} (의존성 재설치)"
                )
                break

        # D-015: dual-load 감지 (CR-07)
        claude_agents = repo_root / ".claude/agents"
        if claude_agents.exists() and any(claude_agents.rglob("*.md")):
            warnings.append(
                ".claude/agents/ + Plugin 동시 감지! 에이전트 중복 로딩 위험. "
                "'setup.sh --migrate' 실행 권장"
            )

except Exception as e:
    print(f"[{PLUGIN}] session-check warning (설정 체크): {e}", file=sys.stderr)

# ── 2. pre-commit 설치·갱신 (plugin-only 모드) ────────────────────────────────


def _pre_commit_action(hook_dst: pathlib.Path, src_bytes: bytes) -> str:
    """설치/갱신/무동작 중 무엇을 할지 판정한다. 반환: 'install' | 'update' | ''.

    **왜 갱신 경로가 필요한가.** 원래는 `not hook_dst.exists()` 로 없을 때만 설치했다.
    그 결과 훅이 최초 설치 시점 판에서 **영구 동결**됐고, 이후 릴리스에서 추가된 검사가
    기존 사용자에게 영원히 도달하지 않았다 — 실측: `.private-names` 비공개 이름 차단이
    소스에만 있고 어느 저장소에도 설치되지 않은 채 "활성"으로 보고됐다. 배포된 것과
    실행되는 것이 갈리는 이 킷의 대표 결함 클래스다.

    **왜 무조건 덮지 않는가.** 사용자가 직접 만든 pre-commit 을 덮으면 그 사람의 검사가
    조용히 사라진다. 그래서 킷이 심은 것(HOOK_MARKER 보유)만 갱신하고, 마커가 없으면
    남의 것으로 보고 손대지 않는다. 읽을 수 없으면 판정 불가이므로 역시 손대지 않는다.
    """
    if not hook_dst.exists():
        return "install"
    try:
        existing = hook_dst.read_bytes()
    except OSError:
        return ""
    if HOOK_MARKER not in existing:
        return ""  # 사용자 소유 훅 — 건드리지 않는다
    return "update" if existing != src_bytes else ""


def _write_hook(hook_dst: pathlib.Path, src_bytes: bytes) -> None:
    """ATK-001: TOCTOU 방어 — 임시파일에 쓰고 os.replace 로 원자 교체."""
    import tempfile

    hook_dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=hook_dst.parent, delete=False, suffix=".tmp"
    ) as tmp:
        tmp_path = pathlib.Path(tmp.name)
        tmp_path.write_bytes(src_bytes)
    tmp_path.chmod(0o755)
    os.replace(tmp_path, hook_dst)  # atomic


try:
    setup_state = pathlib.Path.home() / ".claude/.setup-state.json"
    is_plugin_only = not setup_state.exists()

    if is_plugin_only and git_toplevel:
        hook_dst = git_hooks_dir / "pre-commit"
        pre_commit_src = SETUP_DIR / "pre-commit"

        if not hook_dst.is_symlink() and pre_commit_src.exists():
            src_bytes = pre_commit_src.read_bytes()
            action = _pre_commit_action(hook_dst, src_bytes)
            if action:
                _write_hook(hook_dst, src_bytes)
            if action == "update":
                # 조용히 덮지 않는다 — 사용자 저장소의 실행 파일이 바뀐 사건이다.
                print(
                    f"[{PLUGIN}] pre-commit 훅을 최신본으로 갱신했습니다 "
                    f"({hook_dst})",
                    file=sys.stderr,
                )

except Exception as e:
    print(
        f"[{PLUGIN}] session-check warning (pre-commit 설치): {e}",
        file=sys.stderr,
    )

# ── 3. 경고 출력 ──────────────────────────────────────────────────────────────
if warnings:
    print(f"[{PLUGIN}] ⚠ {'; '.join(warnings)}", file=sys.stderr)

# ── 4. 출력 — additionalContext는 빈 문자열 (session-start.py가 rules 주입 전담) ──
print(
    json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "",
            }
        }
    )
)

sys.exit(0)  # 항상 허용 (SessionStart = fail-open)
