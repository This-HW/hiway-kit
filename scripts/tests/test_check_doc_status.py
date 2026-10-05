"""Unit tests for scripts/check_doc_status.py — 문서 지위 스키마·낡은 토큰·표 열 수.

위반 종류마다 **의도적 위반 픽스처 → red**, **고친 픽스처 → green** 쌍으로 고정한다(되돌려-FAIL).
실제 레포를 건드리지 않는다 — 모듈을 로드한 뒤 `REPO_ROOT`/`NAME_POLICY` 를 임시 레포로 갈아끼운다.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))  # 스크립트가 옆의 git_tracked 를 import 한다

from module_loader import load_module_by_path

OLD_NAME = "fixture-oldkit"


def _fm(status: str = "current", **extra: str) -> str:
    lines = [
        f"status: {status}",
        "as_of: 2026-10-05",
        *(f"{k}: {v}" for k, v in extra.items()),
    ]
    return "---\n" + "\n".join(lines) + "\n---\n"


def _repo(
    tmp_path: Path, files: dict[str, str], name: str = "repo", exclude=("docs/specs/",)
) -> Path:
    root = tmp_path / name
    root.mkdir()
    subprocess.run(["git", "init", "-q", "--template="], cwd=root, check=True)
    (root / "packaging").mkdir()
    (root / "packaging" / "name-targets.json").write_text(
        json.dumps({"previousNames": [OLD_NAME], "oldNameScanExclude": list(exclude)}),
        encoding="utf-8",
    )
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


def _run(root: Path, capsys) -> tuple[int, str]:
    mod = load_module_by_path(SCRIPTS_DIR / "check_doc_status.py", "check_doc_status_t")
    mod.REPO_ROOT = root
    mod.NAME_POLICY = root / "packaging" / "name-targets.json"
    rc = mod.main()
    return rc, capsys.readouterr().out


GOOD = {"docs/a.md": _fm() + "clean prose\n"}


def test_clean_tree_is_green(tmp_path, capsys):
    rc, out = _run(_repo(tmp_path, GOOD), capsys)
    assert rc == 0, out
    assert "지위 스키마 1개" in out


# ── ① 지위 스키마 ────────────────────────────────────────────────────────────


def test_missing_frontmatter_is_red_with_fix(tmp_path, capsys):
    rc, out = _run(_repo(tmp_path, {"docs/a.md": "plain\n"}), capsys)
    assert rc == 1
    assert "docs/a.md" in out
    assert "frontmatter 가 없다" in out
    assert "→" in out


def test_missing_status_and_as_of_are_red(tmp_path, capsys):
    rc, out = _run(_repo(tmp_path, {"docs/a.md": "---\ntitle: x\n---\nbody\n"}), capsys)
    assert rc == 1
    assert "`status` 가 없다" in out
    assert "`as_of` 가 없다" in out


def test_status_outside_schema_is_red(tmp_path, capsys):
    rc, out = _run(_repo(tmp_path, {"docs/a.md": _fm("in-progress")}), capsys)
    assert rc == 1
    assert "스키마 밖" in out


def test_as_of_must_be_a_real_iso_date(tmp_path, capsys):
    for bad in ("2026-13-01", "2026-1-5", "yesterday"):
        doc = f"---\nstatus: current\nas_of: {bad}\n---\n"
        rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}, f"r-{bad}"), capsys)
        assert rc == 1, bad
        assert "YYYY-MM-DD" in out


def test_all_four_statuses_pass_the_schema(tmp_path, capsys):
    files = {
        "docs/new.md": "x\n",
        "docs/c.md": _fm("current"),
        "docs/h.md": _fm("historical"),
        "docs/p.md": _fm("proposal"),
        "docs/s.md": _fm("superseded", superseded_by="docs/new.md"),
    }
    # new.md 는 frontmatter 가 없으니 red — superseded_by 대상으로만 쓰이는 파일도 스키마를 따른다
    rc, out = _run(_repo(tmp_path, files), capsys)
    assert rc == 1
    assert "docs/new.md" in out
    files["docs/new.md"] = _fm("current")
    rc, out = _run(_repo(tmp_path, files, "fixed"), capsys)
    assert rc == 0, out


def test_superseded_requires_a_tracked_in_repo_target(tmp_path, capsys):
    cases = {
        "missing": (_fm("superseded"), "superseded_by` 가 없다"),
        "untracked": (
            _fm("superseded", superseded_by="docs/gone.md"),
            "추적 파일이 아니다",
        ),
        "absolute": (_fm("superseded", superseded_by="/etc/passwd"), "레포 밖"),
        "escape": (_fm("superseded", superseded_by="../outside.md"), "레포 밖"),
        "escape2": (_fm("superseded", superseded_by="docs/../../x.md"), "레포 밖"),
    }
    for name, (doc, expect) in cases.items():
        rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}, f"r-{name}"), capsys)
        assert rc == 1, name
        assert expect in out, (name, out)


def test_superseded_target_is_normalised_once(tmp_path, capsys):
    files = {
        "docs/new.md": _fm(),
        "docs/old.md": _fm("superseded", superseded_by="docs/sub/../new.md"),
    }
    rc, out = _run(_repo(tmp_path, files), capsys)
    assert rc == 0, out


# ── ② 금지 토큰 ──────────────────────────────────────────────────────────────

STALE_LINES = {
    "agents-dir": "see agents/dev/implement-code.md",
    "hooks-script": "run hooks/checklist.py",
    "works": "state lives in docs/works/active",
    "work-sh": "call work.sh new",
    "work-id": "tracked as W-022 in the ledger",
}


def test_each_forbidden_token_is_red_in_a_current_doc(tmp_path, capsys):
    for name, line in STALE_LINES.items():
        rc, out = _run(
            _repo(tmp_path, {"docs/a.md": _fm() + line + "\n"}, f"r-{name}"), capsys
        )
        assert rc == 1, name
        assert "docs/a.md:" in out, name


def test_same_stale_token_is_green_when_historical_or_proposal(tmp_path, capsys):
    """되돌려-FAIL: 지위 하나로 red ↔ green 이 갈린다."""
    for status in ("historical", "proposal"):
        doc = _fm(status) + "docs/works/active\n"
        rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}, f"r-{status}"), capsys)
        assert rc == 0, (status, out)


def test_stale_token_in_fence_still_counts(tmp_path, capsys):
    doc = _fm() + "```bash\nwork.sh new\n```\n"
    rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}), capsys)
    assert rc == 1
    assert "work.sh" in out


def test_frontmatter_is_not_scanned_for_tokens(tmp_path, capsys):
    doc = "---\nstatus: current\nas_of: 2026-10-05\ntitle: W-022 recap\n---\nclean\n"
    rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}), capsys)
    assert rc == 0, out


def test_non_docs_markdown_is_treated_as_live(tmp_path, capsys):
    files = {**GOOD, "README.md": "migrated from W-022\n"}
    rc, out = _run(_repo(tmp_path, files), capsys)
    assert rc == 1
    assert "README.md:1" in out


def test_excluded_files_are_not_scanned(tmp_path, capsys):
    files = {
        **GOOD,
        "CHANGELOG.md": "W-022 docs/works\n",
        "AGENTS.md": "W-022 docs/works\n",
        "GEMINI.md": "work.sh\n",
        "evals/scenarios/x/README.md": "W-022\n",
    }
    rc, out = _run(_repo(tmp_path, files), capsys)
    assert rc == 0, out


def test_old_plugin_name_is_red_unless_policy_excludes_the_path(tmp_path, capsys):
    files = {**GOOD, "README.md": f"install {OLD_NAME}\n"}
    rc, out = _run(_repo(tmp_path, files), capsys)
    assert rc == 1
    assert OLD_NAME in out
    # 같은 이름이 정책 제외 접두사 아래에 있으면(사실로서 인용) 건너뛴다
    files2 = {"docs/specs/h.md": _fm() + f"cites {OLD_NAME} as evidence\n"}
    rc2, out2 = _run(_repo(tmp_path, files2, "again"), capsys)
    assert rc2 == 0, out2


def test_empty_previous_names_is_red(tmp_path, capsys):
    root = _repo(tmp_path, GOOD)
    (root / "packaging" / "name-targets.json").write_text(
        json.dumps({"previousNames": []})
    )
    mod = load_module_by_path(
        SCRIPTS_DIR / "check_doc_status.py", "check_doc_status_t2"
    )
    mod.REPO_ROOT = root
    mod.NAME_POLICY = root / "packaging" / "name-targets.json"
    try:
        mod.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:  # pragma: no cover
        raise AssertionError("빈 previousNames 는 exit 1 이어야 한다")
    assert "previousNames 가 비었다" in capsys.readouterr().out


def test_line_opt_out_marker(tmp_path, capsys):
    doc = _fm() + "docs/works was removed doc-status-ok\nwork.sh here\n"
    rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}), capsys)
    assert rc == 1
    assert "work.sh" in out
    assert "docs/works" not in out


# ── ② 표 열 수 (GFM) ─────────────────────────────────────────────────────────

TABLE_OK = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"


def test_balanced_table_is_green(tmp_path, capsys):
    rc, out = _run(_repo(tmp_path, {"docs/a.md": _fm() + TABLE_OK}), capsys)
    assert rc == 0, out


def test_extra_column_is_red(tmp_path, capsys):
    doc = _fm() + "| a | b |\n| --- | --- |\n| 1 | 2 | 3 |\n"
    rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}), capsys)
    assert rc == 1
    assert "열이 3개인데 헤더는 2개" in out
    assert "docs/a.md:7" in out  # frontmatter 4줄 + 헤더·구분·행 → 7번째 줄


def test_missing_column_is_red_too(tmp_path, capsys):
    doc = _fm() + "| a | b |\n| --- | --- |\n| only |\n"
    rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}), capsys)
    assert rc == 1
    assert "열이 1개인데 헤더는 2개" in out


def test_pipe_inside_code_span_counts_as_a_separator(tmp_path, capsys):
    """GFM: 이스케이프하지 않은 `|` 는 코드 스팬 안에서도 셀을 가른다 — 감사 B-P2-1 의 정체."""
    bad = _fm() + "| a | b |\n| --- | --- |\n| `startup|clear` | 2 |\n"
    rc, out = _run(_repo(tmp_path, {"docs/a.md": bad}), capsys)
    assert rc == 1
    assert "열이 3개인데 헤더는 2개" in out
    good = bad.replace("startup|clear", "startup\\|clear")
    rc2, out2 = _run(_repo(tmp_path, {"docs/a.md": good}, "fixed"), capsys)
    assert rc2 == 0, out2


def test_table_without_outer_pipes_and_aligned_delimiters(tmp_path, capsys):
    doc = _fm() + "a | b\n:-- | --:\n1 | 2\n"
    rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}), capsys)
    assert rc == 0, out


def test_table_inside_fence_is_not_a_table(tmp_path, capsys):
    doc = _fm() + "```\n| a | b |\n| --- | --- |\n| 1 | 2 | 3 |\n```\n"
    rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}), capsys)
    assert rc == 0, out


def test_prose_with_pipes_but_no_delimiter_row_is_not_a_table(tmp_path, capsys):
    doc = _fm() + "use a | b | c in the shell\nand x | y\n"
    rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}), capsys)
    assert rc == 0, out


def test_two_tables_in_one_file_are_each_checked(tmp_path, capsys):
    doc = _fm() + TABLE_OK + "\ntext\n\n| x | y |\n| - | - |\n| 1 |\n"
    rc, out = _run(_repo(tmp_path, {"docs/a.md": doc}), capsys)
    assert rc == 1
    assert "열이 1개인데 헤더는 2개" in out


def test_no_markdown_is_red_not_green(tmp_path, capsys):
    rc, out = _run(_repo(tmp_path, {"scripts/x.py": "x = 1\n"}), capsys)
    assert rc == 1
    assert "0개" in out


def test_unreadable_document_is_tallied_and_red(tmp_path, capsys):
    root = _repo(tmp_path, {**GOOD, "docs/gone.md": _fm()})
    (root / "docs" / "gone.md").unlink()
    rc, out = _run(root, capsys)
    assert rc == 1
    assert "검사하지 못한 파일" in out


def test_real_policy_exempts_marketplace_submission_from_the_old_name_token():
    """전임 킷 등재 기록을 실측 근거로 인용하는 current 문서는 구 이름 토큰에서 빠져야 한다.

    예외의 소유자는 §20(`check_old_names.py`)과 같은 정책 파일이다 — 여기 따로 목록을 두지 않는다.
    """
    mod = load_module_by_path(SCRIPTS_DIR / "check_doc_status.py", "check_doc_status_real")
    names, exclude = mod.load_old_name_policy()
    assert names
    assert "docs/marketplace-submission.md".startswith(exclude)
