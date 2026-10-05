"""Unit tests for scripts/check_doc_refs.py — 문서 참조 실재성 게이트.

각 위반 종류마다 **의도적 위반 픽스처 → red**, **고친 픽스처 → green** 쌍으로 고정한다
(되돌려-FAIL). 실제 레포를 건드리지 않는다 — 모듈을 로드한 뒤 `REPO_ROOT` 를 임시 git 레포로
갈아끼운다(`test_check_old_names.py` 관례).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))  # 스크립트가 옆의 git_tracked 를 import 한다

from module_loader import load_module_by_path


def _repo(tmp_path: Path, files: dict[str, str], name: str = "repo") -> Path:
    root = tmp_path / name
    root.mkdir()
    subprocess.run(["git", "init", "-q", "--template="], cwd=root, check=True)
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root  # 커밋은 필요 없다 — ls-files 는 인덱스를 본다


def _run(root: Path, capsys, **patch) -> tuple[int, str]:
    mod = load_module_by_path(SCRIPTS_DIR / "check_doc_refs.py", "check_doc_refs_t")
    mod.REPO_ROOT = root
    mod.ALLOWED_REFS = {}  # 실제 레포의 예외 목록이 픽스처에 섞이지 않게 한다
    for key, value in patch.items():
        setattr(mod, key, value)
    rc = mod.main()
    return rc, capsys.readouterr().out


BASE = {
    "scripts/tool.py": "def real_helper():\n    pass\n",
    "scripts/run.sh": "#!/bin/sh\nshell_helper() { :; }\n",
    "docs/other.md": "other\n",
    "plugins/common/rules/r.md": "rule\n",
}


def test_all_reference_kinds_that_exist_are_green(tmp_path, capsys):
    doc = (
        "---\nstatus: current\nas_of: 2026-10-05\n---\n"
        "[link](other.md#anchor) and `scripts/tool.py` and `run.sh` and `real_helper()`\n"
        "and `def real_helper` and `shell_helper()` and `rules/r.md` (플러그인 루트 기준)\n"
        "@docs/other.md\n"
    )
    root = _repo(tmp_path, {**BASE, "docs/a.md": doc})
    rc, out = _run(root, capsys)
    assert rc == 0, out
    assert "참조 실재" in out


def test_missing_link_is_red_with_fix_hint(tmp_path, capsys):
    root = _repo(tmp_path, {**BASE, "docs/a.md": "[x](gone.md)\n"})
    rc, out = _run(root, capsys)
    assert rc == 1
    assert "docs/a.md:1  [링크] gone.md" in out
    assert "→" in out  # 고치는 법이 붙는다(C-M3)


def test_missing_backtick_path_is_red(tmp_path, capsys):
    root = _repo(tmp_path, {**BASE, "docs/a.md": "see `scripts/old/tool.py`\n"})
    rc, out = _run(root, capsys)
    assert rc == 1
    assert "[경로] scripts/old/tool.py" in out


def test_missing_bare_filename_is_red(tmp_path, capsys):
    root = _repo(tmp_path, {**BASE, "docs/a.md": "run `dead-tunnel.sh` first\n"})
    rc, out = _run(root, capsys)
    assert rc == 1
    assert "[파일명] dead-tunnel.sh" in out


def test_missing_function_is_red_and_existing_is_green(tmp_path, capsys):
    root = _repo(
        tmp_path,
        {**BASE, "docs/a.md": "call `_vanished_helper()` and `real_helper()`\n"},
    )
    rc, out = _run(root, capsys)
    assert rc == 1
    assert "[함수] _vanished_helper()" in out
    assert "[함수] real_helper" not in out  # 존재하는 쪽은 안 걸린다


def test_missing_def_reference_is_red(tmp_path, capsys):
    root = _repo(tmp_path, {**BASE, "docs/a.md": "see `def _gone_helper`\n"})
    rc, out = _run(root, capsys)
    assert rc == 1
    assert "[정의] def _gone_helper" in out


def test_missing_import_is_red(tmp_path, capsys):
    root = _repo(tmp_path, {**BASE, "docs/a.md": "@docs/missing.md\n"})
    rc, out = _run(root, capsys)
    assert rc == 1
    assert "[@import] docs/missing.md" in out


def test_dead_script_inside_fence_is_red_but_consumer_example_is_not(tmp_path, capsys):
    """B-P0-4: 트리 그림 안의 죽은 스크립트는 잡혀야 한다. 소비자 예시(`src/`·`docs/api/`)는 아니다."""
    doc = (
        "```\n"
        "(반드시 dead-tunnel.sh start 먼저)\n"
        "edit src/app/main.py and docs/api/users.md\n"
        "```\n"
    )
    root = _repo(tmp_path, {**BASE, "docs/a.md": doc})
    rc, out = _run(root, capsys)
    assert rc == 1
    assert "dead-tunnel.sh" in out
    assert "src/app" not in out
    assert "docs/api" not in out


def test_fence_path_under_own_root_is_checked(tmp_path, capsys):
    doc = "```\nbash scripts/gone.sh\n```\n"
    root = _repo(tmp_path, {**BASE, "docs/a.md": doc})
    rc, out = _run(root, capsys)
    assert rc == 1
    assert "scripts/gone.sh" in out


def test_historical_status_skips_and_current_does_not(tmp_path, capsys):
    """되돌려-FAIL: 같은 본문이 historical 이면 green, current 면 red."""
    body = "`scripts/old/tool.py`\n"
    hist = "---\nstatus: historical\nas_of: 2026-10-05\n---\n" + body
    root = _repo(tmp_path, {**BASE, "docs/a.md": hist})
    rc, out = _run(root, capsys)
    assert rc == 0, out
    assert "지위로 제외" in out

    root2 = _repo(
        tmp_path, {**BASE, "docs/a.md": hist.replace("historical", "current")}, "again"
    )
    rc2, out2 = _run(root2, capsys)
    assert rc2 == 1
    assert "scripts/old/tool.py" in out2


def test_superseded_status_also_skips(tmp_path, capsys):
    doc = "---\nstatus: superseded\nas_of: 2026-10-05\n---\n`scripts/old/tool.py`\n"
    root = _repo(tmp_path, {**BASE, "docs/a.md": doc})
    rc, _ = _run(root, capsys)
    assert rc == 0


def test_changelog_and_eval_fixtures_are_excluded(tmp_path, capsys):
    files = {
        **BASE,
        "CHANGELOG.md": "`scripts/old/tool.py`\n",
        "evals/scenarios/x/README.md": "`scripts/old/tool.py`\n",
    }
    rc, out = _run(_repo(tmp_path, files), capsys)
    assert rc == 0, out


def test_placeholders_urls_and_consumer_paths_are_not_checked(tmp_path, capsys):
    doc = (
        "`docs/plans/<날짜>-<slug>/plan.md` `scripts/*.py` `${CLAUDE_PLUGIN_ROOT}/x/y.md`\n"
        "`.claude/skills/x/SKILL.md` `~/.claude/x.md` `/abs/path/x.md` `path/to/file.ts`\n"
        "[u](https://example.com/x.md) [a](#anchor) [m](mailto:a@b.c) `src/app.ts`\n"
    )
    rc, out = _run(_repo(tmp_path, {**BASE, "docs/a.md": doc}), capsys)
    assert rc == 0, out


def test_gitignored_build_output_is_not_a_missing_reference(tmp_path, capsys):
    files = {
        **BASE,
        ".gitignore": "/build/\n",
        "docs/a.md": "output goes to `build/out/`\n",
    }
    rc, out = _run(_repo(tmp_path, files), capsys)
    assert rc == 0, out


def test_line_opt_out_marker(tmp_path, capsys):
    doc = "`scripts/old/tool.py` doc-ref-ok\n`scripts/old/other.py`\n"
    rc, out = _run(_repo(tmp_path, {**BASE, "docs/a.md": doc}), capsys)
    assert rc == 1
    assert "other.py" in out
    assert "scripts/old/tool.py" not in out


def test_allowed_pair_is_accepted_and_unused_pair_is_noted(tmp_path, capsys):
    root = _repo(tmp_path, {**BASE, "docs/a.md": "`scripts/old/tool.py`\n"})
    allowed = {
        ("docs/a.md", "scripts/old/tool.py"): "이유",
        ("docs/a.md", "never/used.py"): "이유",
    }
    rc, out = _run(root, capsys, ALLOWED_REFS=allowed)
    assert rc == 0, out
    assert "쓰이지 않는 예외" in out
    assert "never/used.py" in out


def test_no_documents_is_red_not_green(tmp_path, capsys):
    root = _repo(tmp_path, {"scripts/tool.py": "x = 1\n"})
    rc, out = _run(root, capsys)
    assert rc == 1
    assert "0개" in out


def test_unreadable_document_is_tallied_and_red(tmp_path, capsys):
    root = _repo(tmp_path, {**BASE, "docs/gone.md": "x\n", "docs/ok.md": "fine\n"})
    (root / "docs" / "gone.md").unlink()  # 추적 중이지만 워킹트리에 없다
    rc, out = _run(root, capsys)
    assert rc == 1
    assert "검사하지 못한 파일" in out
    assert "gone.md" in out
