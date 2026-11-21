"""Consumer footprint — what the kit may change in a project it is installed into.

Policy: docs/conventions/consumer-footprint.md. Each case builds a real fixture repository, runs a
shipped hook or tool as a real process (HOME and the git config isolated), and asserts that the
working tree and index did not change where the project never asked for it. Fake `ruff`/`prettier`
binaries stand in for the real tools so the cases do not depend on what the machine has installed.

Origin (2026-11-09): an external install review, then two independent consultants (Claude Opus,
Codex), found the kit reshaping projects on its own — renaming a tracked file at session start,
creating `docs/works/` outside git, rewriting files with formatters the project never chose,
re-staging a partially staged file, and following a symlink out of the plan directory.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "common"
HOOKS = PLUGIN / "hooks"
TOOLS = PLUGIN / "tools"
PRE_COMMIT = PLUGIN / "setup" / "pre-commit"


def _env(tmp: Path, **extra: str) -> dict:
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CEILING_DIRECTORIES": str(tmp),
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    env.update(extra)
    return env


def _git(repo: Path, env: dict, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, env=env, check=True,
                          capture_output=True, text=True).stdout


def _repo(tmp: Path, env: dict) -> Path:
    repo = tmp / "proj"
    repo.mkdir()
    _git(repo, env, "init", "-q", "-b", "main")
    return repo


def _snapshot(repo: Path, env: dict) -> tuple:
    status = _git(repo, env, "status", "--porcelain", "--ignored", "-uall")
    files = sorted(
        (str(p.relative_to(repo)), p.read_bytes() if p.is_file() and not p.is_symlink() else b"")
        for p in repo.rglob("*") if ".git" not in p.relative_to(repo).parts
    )
    return status, files


def _fake_bin(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return path


# ── 세션 이벤트는 작업 트리를 바꾸지 않는다 ─────────────────────────────


def test_session_start_does_not_rename_a_tracked_legacy_ledger(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    legacy = repo / "docs" / "works" / "feedback" / "ledger.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        "| ID | Category | Pattern | Frequency | Last Seen | Severity |\n"
        "|----|----------|---------|-----------|-----------|----------|\n"
        "| F-001 | test | 옛 원장 항목 | 2 | 2026-01-01 | high |\n",
        encoding="utf-8",
    )
    _git(repo, env, "add", "-A")
    _git(repo, env, "commit", "-q", "-m", "init")
    before = _snapshot(repo, env)
    run = subprocess.run([sys.executable, str(HOOKS / "session-start.py")], input="{}",
                         capture_output=True, text=True, cwd=repo, timeout=60,
                         env={**env, "CLAUDE_PROJECT_DIR": str(repo)}, check=False)
    assert run.returncode == 0, run.stderr
    assert _snapshot(repo, env) == before
    # 읽기 호환은 남는다 — 옛 원장의 학습은 그대로 주입된다
    assert "옛 원장 항목" in json.loads(run.stdout)["hookSpecificOutput"]["additionalContext"]


def test_ledger_write_outside_git_creates_nothing_in_the_tree(tmp_path):
    env = _env(tmp_path)
    project = tmp_path / "plain"
    project.mkdir()
    run = subprocess.run([sys.executable, str(TOOLS / "feedback_ledger.py"), "upsert",
                          "test", "high", "비-git 에서 배운 것"],
                         capture_output=True, text=True, cwd=project, timeout=60,
                         env={**env, "CLAUDE_PROJECT_DIR": str(project)}, check=False)
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "skipped"  # 상위 디렉토리의 git 이 끼어들지 않았다는 확인
    assert list(project.iterdir()) == []


# ── 포맷터는 프로젝트가 고른 도구만 ─────────────────────────────────


def _format_payload(target: Path) -> str:
    return json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(target)}})


def test_local_prettier_binary_without_config_leaves_files_alone(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _fake_bin(repo / "node_modules" / ".bin", "prettier",
              'for a in "$@"; do f="$a"; done\nprintf "reformatted\\n" > "$f"\n')
    doc = repo / "README.md"
    doc.write_text("# Title\n")
    subprocess.run([sys.executable, str(HOOKS / "auto-format.py")], input=_format_payload(doc),
                   capture_output=True, text=True, cwd=repo, timeout=60,
                   env={**env, "CLAUDE_PROJECT_DIR": str(repo)}, check=False)
    assert doc.read_text() == "# Title\n"
    # 양성 대조 — 프로젝트가 prettier 설정을 두면 포맷한다
    (repo / ".prettierrc").write_text("{}\n")
    subprocess.run([sys.executable, str(HOOKS / "auto-format.py")], input=_format_payload(doc),
                   capture_output=True, text=True, cwd=repo, timeout=60,
                   env={**env, "CLAUDE_PROJECT_DIR": str(repo)}, check=False)
    assert doc.read_text() == "reformatted\n"


# ── git pre-commit: 동의 없는 수정·재스테이징 금지 ───────────────────


def _pre_commit_fixture(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    bin_dir = tmp_path / "bin"
    # 가짜 ruff: `check ... --fix FILE` 이면 파일 끝에 한 줄을 덧붙인다(수정 흉내).
    _fake_bin(bin_dir, "ruff",
              'fix=0\nfor a in "$@"; do [ "$a" = "--fix" ] && fix=1; f="$a"; done\n'
              '[ "$fix" = 1 ] && printf "# fixed\\n" >> "$f"\nexit 0\n')
    env = {**env, "PATH": f"{bin_dir}:{env['PATH']}"}
    src = repo / "job.py"
    src.write_text("x = 1\n")
    _git(repo, env, "add", "job.py")
    _git(repo, env, "commit", "-q", "-m", "init")
    return env, repo, src


def _staged_blob(repo: Path, env: dict, path: str) -> str:
    return _git(repo, env, "show", f":{path}")


def _run_pre_commit(repo: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(PRE_COMMIT)], cwd=repo, env=env,
                          capture_output=True, text=True, timeout=60, check=False)


def test_pre_commit_does_not_touch_a_project_without_ruff_config(tmp_path):
    env, repo, src = _pre_commit_fixture(tmp_path)
    src.write_text("x = 1\ny = 2\n")
    _git(repo, env, "add", "job.py")
    _run_pre_commit(repo, env)
    assert src.read_text() == "x = 1\ny = 2\n"
    assert _staged_blob(repo, env, "job.py") == "x = 1\ny = 2\n"


def test_pre_commit_never_restages_a_partially_staged_file(tmp_path):
    env, repo, src = _pre_commit_fixture(tmp_path)
    (repo / "ruff.toml").write_text("")
    src.write_text("x = 1\ny = 2\n")
    _git(repo, env, "add", "job.py")
    src.write_text("x = 1\ny = 2\nnot_ready = 3\n")  # 일부러 스테이징하지 않은 줄
    _run_pre_commit(repo, env)
    assert _staged_blob(repo, env, "job.py") == "x = 1\ny = 2\n"
    assert src.read_text() == "x = 1\ny = 2\nnot_ready = 3\n"


def test_pre_commit_still_fixes_a_fully_staged_file_in_a_ruff_project(tmp_path):
    """양성 대조 — ruff 를 쓰는 프로젝트에서 통째로 스테이징한 파일은 예전처럼 고쳐 재스테이징한다."""
    env, repo, src = _pre_commit_fixture(tmp_path)
    (repo / "ruff.toml").write_text("")
    src.write_text("x = 1\ny = 2\n")
    _git(repo, env, "add", "job.py")
    _run_pre_commit(repo, env)
    assert _staged_blob(repo, env, "job.py") == "x = 1\ny = 2\n# fixed\n"


# ── 상태 파일은 정해진 자리 밖으로 나가지 않는다 ─────────────────────


def test_checklist_refuses_a_symlink_out_of_the_plan_directory(tmp_path):
    project = tmp_path / "proj"
    plan = project / "docs" / "plans" / "2026-11-09-x"
    plan.mkdir(parents=True)
    manifest = project / "package.json"
    manifest.write_text('{"name": "consumer"}\n')
    (plan / "checklist.json").symlink_to(Path("../../../package.json"))
    items = json.dumps([{"id": "a", "description": "d", "acceptance": "ok",
                         "verify": "true", "passes": False}])
    run = subprocess.run([sys.executable, str(TOOLS / "checklist.py"), "init", str(plan), items],
                         capture_output=True, text=True, cwd=project, timeout=60,
                         env=_env(tmp_path), check=False)
    assert run.returncode != 0
    assert manifest.read_text() == '{"name": "consumer"}\n'


def test_pre_commit_handles_a_non_ascii_directory_in_a_ruff_project(tmp_path):
    """git 은 기본(core.quotePath=true)으로 비-ASCII 경로를 따옴표로 감싸 내보낸다 — 그 이름은 `.py` 로
    끝나지 않아 필터를 못 넘고, ruff 프로젝트에서도 조용히 빠졌다. 설정 탐색도 반드시 끝나야 한다(리뷰 ATK-001)."""
    env, repo, _ = _pre_commit_fixture(tmp_path)
    (repo / "ruff.toml").write_text("")
    nested = repo / "작업" / "src"
    nested.mkdir(parents=True)
    target = nested / "job.py"
    target.write_text("x = 1\n")
    _git(repo, env, "add", "-A")
    run = _run_pre_commit(repo, env)  # 끝나지 않으면 subprocess 타임아웃(60s)으로 깨진다
    assert run.returncode == 0, run.stdout + run.stderr
    assert _staged_blob(repo, env, "작업/src/job.py") == "x = 1\n# fixed\n"


def _checklist_init(plan: Path, cwd: Path, tmp_path: Path) -> subprocess.CompletedProcess:
    items = json.dumps([{"id": "a", "description": "d", "acceptance": "ok", "verify": "true", "passes": False}])
    return subprocess.run([sys.executable, str(TOOLS / "checklist.py"), "init", str(plan), items],
                          capture_output=True, text=True, cwd=cwd, timeout=60, env=_env(tmp_path), check=False)


def test_checklist_refuses_a_symlink_inside_the_plan_directory(tmp_path):
    """같은 폴더 안의 링크(checklist.json → plan.md)도 따라가면 plan.md 를 JSON 으로 덮는다(리뷰 ATK-006)."""
    plan = tmp_path / "proj" / "docs" / "plans" / "2026-11-09-x"
    plan.mkdir(parents=True)
    (plan / "plan.md").write_text("# plan\n")
    (plan / "checklist.json").symlink_to("plan.md")
    assert _checklist_init(plan, tmp_path / "proj", tmp_path).returncode != 0
    assert (plan / "plan.md").read_text() == "# plan\n"


def test_checklist_refuses_a_plan_directory_that_resolves_outside_the_repo(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (repo / "docs" / "plans").mkdir(parents=True)
    (repo / "docs" / "plans" / "2026-11-09-x").symlink_to(outside)
    assert _checklist_init(repo / "docs" / "plans" / "2026-11-09-x", repo, tmp_path).returncode != 0
    assert list(outside.iterdir()) == []



def _bashes() -> list:
    """PATH 의 bash 와 셔뱅이 가리키는 /bin/bash(macOS 3.2) — 둘이 다르면 둘 다 돌린다."""
    found = [b for b in ("bash", "/bin/bash") if shutil.which(b)]
    return sorted(set(found), key=found.index)


@pytest.mark.parametrize("bash", _bashes())
def test_pre_commit_lets_jsonc_files_through_but_still_blocks_broken_json(tmp_path, bash):
    """`tsc --init`·VS Code 가 만드는 주석 달린 JSONC 는 엄격한 JSON 검사로 커밋을 막지 않는다 — 알려진
    이름은 검사하지 않고, 그 밖의 파일은 주석이 있을 때만 주석·끝 쉼표를 걷어 다시 읽는다.
    양성 대조: 주석 없는 끝 쉼표·주석 있어도 깨진 JSON 은 여전히 막는다."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    jsonc = '{\n  // tsc --init 이 남기는 주석\n  "compilerOptions": {"strict": true,},\n}\n'
    for rel in ("tsconfig.json", "web/tsconfig.app.json", "tsconfig-base.json", "jsconfig.json",
                ".vscode/launch.json", ".devcontainer/devcontainer.json", ".devcontainer.json"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(jsonc)
    # 이름 목록 밖이지만 주석이 있는 JSONC — 문자열 속 "//" 는 주석이 아니다.
    (repo / ".eslintrc.json").write_text(
        '{\n  /* 팀 규칙 */\n  "rules": {"no-console": "off"},  // 로그 허용\n'
        '  "url": "https://example.com/a//b",\n}\n')
    _git(repo, env, "add", "-A")
    ok = subprocess.run([bash, str(PRE_COMMIT)], cwd=repo, env=env, capture_output=True,
                        text=True, timeout=60, check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "eslintrc.json: 주석 있는 JSONC" in ok.stdout

    for name, body in (("package.json", '{"name": "x",}\n'),
                       ("biome.json", '{\n  // 주석은 있지만\n  "a": ,\n}\n')):
        (repo / name).write_text(body)
        _git(repo, env, "add", name)
        blocked = subprocess.run([bash, str(PRE_COMMIT)], cwd=repo, env=env, capture_output=True,
                                 text=True, timeout=60, check=False)
        assert blocked.returncode == 1, name
        assert f"Invalid JSON: {name}" in blocked.stdout
        _git(repo, env, "rm", "-q", "--cached", name)


SETUP_SH = PLUGIN.parents[1] / "setup.sh"


def _setup_env(tmp: Path) -> dict:
    """setup.sh 를 격리해 돌린다 — 가짜 `claude`, 빈 HOME·전역 git 설정, codex·ruff 없는 PATH."""
    fake = tmp / "fakebin"
    _fake_bin(fake, "claude", "exit 0\n")
    return _env(tmp, PATH=f"{fake}:/usr/bin:/bin")


def _run_setup(cwd: Path, env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SETUP_SH), *args], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=120, check=False)


def test_setup_sh_changes_nothing_global_without_asking(tmp_path):
    """5.7.2 — 비대화형 setup.sh 는 전역 ruff.toml·init.templateDir·settings.json 을 쓰지 않고, 실행한
    레포에만 pre-commit 을 넣는다."""
    env = _setup_env(tmp_path)
    repo = _repo(tmp_path, env)
    result = _run_setup(repo, env)
    assert result.returncode == 0, result.stdout + result.stderr
    home = Path(env["HOME"])
    assert not (home / ".config" / "ruff").exists()
    assert not (home / ".claude" / "settings.json").exists()
    assert subprocess.run(["git", "config", "--global", "--get", "init.templateDir"], env=env,
                          capture_output=True, check=False).returncode == 1
    assert (repo / ".git" / "hooks" / "pre-commit").read_bytes() == PRE_COMMIT.read_bytes()


def test_setup_sh_installs_into_the_common_hooks_dir_from_a_linked_worktree(tmp_path):
    """워크트리에서 `--git-dir` 은 worktrees/<이름> 이라 hooks/ 가 없다 — 예전엔 cp 가 실패해 중단됐다."""
    env = _setup_env(tmp_path)
    repo = _repo(tmp_path, env)
    (repo / "a.txt").write_text("a\n")
    _git(repo, env, "add", "a.txt")
    _git(repo, env, "commit", "-qm", "init")
    _git(repo, env, "worktree", "add", "-q", str(tmp_path / "wt"))
    result = _run_setup(tmp_path / "wt", env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / ".git" / "hooks" / "pre-commit").read_bytes() == PRE_COMMIT.read_bytes()


def test_setup_sh_does_not_pretend_to_install_under_core_hooks_path(tmp_path):
    env = _setup_env(tmp_path)
    repo = _repo(tmp_path, env)
    _git(repo, env, "config", "core.hooksPath", ".husky")
    result = _run_setup(repo, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()
    assert not (repo / ".husky").exists()
    assert "core.hooksPath(.husky)" in result.stdout


def test_setup_sh_reports_and_refreshes_a_stale_template_copy(tmp_path):
    """예전 판이 켠 템플릿의 낡은 사본은 알리고, `--force` 에서만 갱신한다."""
    env = _setup_env(tmp_path)
    repo = _repo(tmp_path, env)
    tpl = Path(env["HOME"]) / ".claude" / "git-templates"
    (tpl / "hooks").mkdir(parents=True)
    stale = "#!/bin/bash\n# 개명 전 판 — 설정 없이 ruff --fix\n"
    (tpl / "hooks" / "pre-commit").write_text(stale)
    _git(repo, env, "config", "--global", "init.templateDir", str(tpl))
    plain = _run_setup(repo, env)
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert "낡은 사본" in plain.stdout
    assert (tpl / "hooks" / "pre-commit").read_text() == stale
    forced = _run_setup(repo, env, "--force")
    assert forced.returncode == 0, forced.stdout + forced.stderr
    assert (tpl / "hooks" / "pre-commit").read_bytes() == PRE_COMMIT.read_bytes()


# ── setup.sh --uninstall: 쓴 것만, 쓴 그대로일 때만 되돌린다 (5.9.0) ─────────────


def _uninstall_env(tmp: Path) -> dict:
    """_setup_env 와 같되 가짜 `claude` 가 받은 인자를 기록한다 — 플러그인을 지우려 했는지 본다."""
    fake = tmp / "fakebin"
    _fake_bin(fake, "claude", 'printf "%s\\n" "$*" >> "$HOME/claude-calls.log"\nexit 0\n')
    return _env(tmp, PATH=f"{fake}:/usr/bin:/bin")


def _claude_calls(env: dict) -> list:
    log = Path(env["HOME"]) / "claude-calls.log"
    return log.read_text().splitlines() if log.exists() else []


def _global_template_dir(env: dict) -> str:
    r = subprocess.run(["git", "config", "--global", "--get", "init.templateDir"], env=env,
                       capture_output=True, text=True, check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def _accept_template(env: dict) -> Path:
    """대화형 y 응답으로 setup.sh 가 만드는 상태를 그대로 재현한다(비대화형 테스트는 물을 수 없다)."""
    tpl = Path(env["HOME"]) / ".claude" / "git-templates"
    (tpl / "hooks").mkdir(parents=True)
    shutil.copy(PRE_COMMIT, tpl / "hooks" / "pre-commit")
    subprocess.run(["git", "config", "--global", "init.templateDir", str(tpl)], env=env, check=True)
    return tpl


def test_setup_sh_uninstall_round_trip_reverts_what_setup_wrote(tmp_path):
    env = _uninstall_env(tmp_path)
    repo = _repo(tmp_path, env)
    installed = _run_setup(repo, env)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    hook = repo / ".git" / "hooks" / "pre-commit"
    state = Path(env["HOME"]) / ".claude" / ".setup-state.json"
    assert hook.exists() and state.exists()
    tpl = _accept_template(env)
    calls_before = _claude_calls(env)

    removed = _run_setup(repo, env, "--uninstall")
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert not hook.exists()
    assert not state.exists()
    assert _global_template_dir(env) == ""
    assert not tpl.exists()
    # 플러그인은 지우지 않고 명령만 안내한다
    assert _claude_calls(env) == calls_before
    assert "claude plugin uninstall hiway-kit@hiway-kit" in removed.stdout
    assert "남긴 항목" not in removed.stdout
    # templateDir 로 다른 레포에 심긴 사본은 찾을 수 없다 — 그렇다고 적고 각 레포에서 할 일을 안내한다
    assert "찾을 수 없어" in removed.stdout and "--uninstall" in removed.stdout


def test_setup_sh_uninstall_keeps_a_modified_pre_commit(tmp_path):
    env = _uninstall_env(tmp_path)
    repo = _repo(tmp_path, env)
    assert _run_setup(repo, env).returncode == 0
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(PRE_COMMIT.read_text() + "\n# 내 프로젝트 전용 검사\n")
    tpl = _accept_template(env)
    (tpl / "hooks" / "pre-commit").write_text("#!/bin/sh\n# 예전 판 사본\n")

    removed = _run_setup(repo, env, "--uninstall")
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert hook.read_text().endswith("# 내 프로젝트 전용 검사\n")
    assert (tpl / "hooks" / "pre-commit").read_text() == "#!/bin/sh\n# 예전 판 사본\n"
    # 사본을 남기면 설정도 남긴다 — 설정만 풀면 남긴 사본이 아무 데도 연결되지 않은 채 "보존"된다(리뷰 L-004)
    assert _global_template_dir(env) == str(tpl)
    assert "남겨 둡니다" in removed.stdout
    assert "남긴 항목 2개" in removed.stdout


def test_setup_sh_uninstall_leaves_a_foreign_template_dir_and_symlinked_hook(tmp_path):
    env = _uninstall_env(tmp_path)
    repo = _repo(tmp_path, env)
    mine = tmp_path / "my-templates"
    mine.mkdir()
    subprocess.run(["git", "config", "--global", "init.templateDir", str(mine)], env=env, check=True)
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "pre-commit").symlink_to(PRE_COMMIT)  # 내용은 같아도 링크는 사용자가 만든 것

    removed = _run_setup(repo, env, "--uninstall")
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert _global_template_dir(env) == str(mine)
    assert (hooks / "pre-commit").is_symlink()
    assert PRE_COMMIT.exists()


def test_setup_sh_uninstall_dry_run_changes_nothing(tmp_path):
    env = _uninstall_env(tmp_path)
    repo = _repo(tmp_path, env)
    assert _run_setup(repo, env).returncode == 0
    tpl = _accept_template(env)
    home = Path(env["HOME"])
    before = sorted((str(p), p.read_bytes() if p.is_file() else b"") for p in home.rglob("*"))
    hook_before = (repo / ".git" / "hooks" / "pre-commit").read_bytes()

    dry = _run_setup(repo, env, "--uninstall", "--dry-run")
    assert dry.returncode == 0, dry.stdout + dry.stderr
    assert "(dry-run)" in dry.stdout and "pre-commit 삭제" in dry.stdout
    assert sorted((str(p), p.read_bytes() if p.is_file() else b"") for p in home.rglob("*")) == before
    assert (repo / ".git" / "hooks" / "pre-commit").read_bytes() == hook_before
    assert _global_template_dir(env) == str(tpl)


def test_setup_sh_uninstall_under_core_hooks_path_touches_nothing(tmp_path):
    env = _uninstall_env(tmp_path)
    repo = _repo(tmp_path, env)
    _git(repo, env, "config", "core.hooksPath", ".husky")
    (repo / ".husky").mkdir()
    shutil.copy(PRE_COMMIT, repo / ".husky" / "pre-commit")  # 사용자가 훅 관리자에 직접 넣은 사본
    removed = _run_setup(repo, env, "--uninstall")
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert (repo / ".husky" / "pre-commit").exists()


def test_setup_sh_uninstall_keeps_template_dir_holding_user_files(tmp_path):
    """보안 L-4·리뷰 L-004 — 템플릿 디렉토리에 사용자 파일이 있으면 해제하지 않는다(그 파일의 복사가 끊긴다)."""
    env = _uninstall_env(tmp_path)
    repo = _repo(tmp_path, env)
    assert _run_setup(repo, env).returncode == 0
    tpl = _accept_template(env)
    (tpl / "hooks" / "commit-msg").write_text("#!/bin/sh\n# 내 훅\n")
    (tpl / "description").write_text("mine\n")

    removed = _run_setup(repo, env, "--uninstall")
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert _global_template_dir(env) == str(tpl)
    assert (tpl / "hooks" / "pre-commit").exists()  # 연결된 채로 남는다
    assert (tpl / "hooks" / "commit-msg").exists() and (tpl / "description").exists()
    assert "setup.sh 가 넣지 않은 파일" in removed.stdout
    assert "commit-msg" in removed.stdout


def test_setup_sh_uninstall_continues_when_unset_fails(tmp_path):
    """리뷰 L-003 — `git config --unset` 실패가 set -e 로 스크립트를 조용히 멈추지 않는다."""
    env = _uninstall_env(tmp_path)
    cfg_dir = tmp_path / "ro-config"
    cfg_dir.mkdir()
    env["GIT_CONFIG_GLOBAL"] = str(cfg_dir / ".gitconfig")
    repo = _repo(tmp_path, env)
    assert _run_setup(repo, env).returncode == 0
    tpl = _accept_template(env)
    state = Path(env["HOME"]) / ".claude" / ".setup-state.json"
    assert state.exists()
    cfg_dir.chmod(0o555)  # 락 파일을 만들 수 없다 → unset 실패
    try:
        removed = _run_setup(repo, env, "--uninstall")
    finally:
        cfg_dir.chmod(0o755)
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert "해제에 실패" in removed.stdout
    assert "--fixed-value --unset-all init.templateDir" in removed.stdout
    assert (tpl / "hooks" / "pre-commit").exists()  # 설정이 아직 가리키므로 사본도 둔다
    assert not state.exists()  # 뒤 단계까지 진행했다
    assert "제거 끝" in removed.stdout


def test_setup_sh_uninstall_quotes_paths_in_the_manual_command(tmp_path):
    """보안 L-5 — 안내하는 명령의 경로는 셸에 그대로 붙여 넣어도 경로 하나로 읽혀야 한다(`%q`)."""
    env = _uninstall_env(tmp_path)
    home = tmp_path / "my home $x"
    home.mkdir()
    env["HOME"] = str(home)
    env["GIT_CONFIG_GLOBAL"] = str(home / ".gitconfig")
    repo = _repo(tmp_path, env)
    assert _run_setup(repo, env).returncode == 0
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(PRE_COMMIT.read_text() + "\n# 수정\n")
    tpl = _accept_template(env)
    (tpl / "hooks" / "pre-commit").write_text("#!/bin/sh\n# 고친 사본\n")

    removed = _run_setup(repo, env, "--uninstall")
    assert removed.returncode == 0, removed.stdout + removed.stderr
    lines = removed.stdout.splitlines()
    rm_line = next(ln for ln in lines if "rm -- " in ln).split("직접 지우세요: ", 1)[1]
    assert shlex.split(rm_line) == ["rm", "--", ".git/hooks/pre-commit"]
    check_line = next(ln for ln in lines if "직접 확인: " in ln).split("직접 확인: ", 1)[1]
    assert shlex.split(check_line) == [str(tpl / "hooks" / "pre-commit")]


def test_setup_sh_uninstall_under_core_hooks_path_points_at_a_leftover_copy(tmp_path):
    """리뷰 L-012 — hooksPath 레포에서 '지울 것도 없다'고 단정하지 않는다. 남은 .git/hooks 사본을 알린다."""
    env = _uninstall_env(tmp_path)
    repo = _repo(tmp_path, env)
    assert _run_setup(repo, env).returncode == 0  # hooksPath 를 켜기 전에 깐 사본
    _git(repo, env, "config", "core.hooksPath", ".husky")
    removed = _run_setup(repo, env, "--uninstall")
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert "지울 것도 없습니다" not in removed.stdout
    assert "쓰이지 않는 .git/hooks/pre-commit" in removed.stdout
    assert (repo / ".git" / "hooks" / "pre-commit").exists()  # 지우지 않고 알린다


@pytest.mark.parametrize("args", [("--dry-run",), ("--uninstall", "--force"), ("--uninstall", "--migrate")])
def test_setup_sh_rejects_ambiguous_uninstall_flags(tmp_path, args):
    env = _uninstall_env(tmp_path)
    repo = _repo(tmp_path, env)
    r = _run_setup(repo, env, *args)
    assert r.returncode == 1
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()  # 설치로 넘어가지 않았다
    assert _claude_calls(env) == []
