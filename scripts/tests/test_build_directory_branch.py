"""Unit tests for scripts/build-directory-branch.py.

Claude 디렉토리는 비 Verified 조직에게서 command 훅(2026-11-06), 스크립트 파일과 허용 목록 밖
frontmatter 키(2026-11-21)를 받지 않는다. 디렉토리가 추적할 브랜치가 **디렉토리판**(스크립트·훅·도구
의존 스킬을 빼고 `isolation` 을 지운 트리)인지, 이름이 바뀐 제외 대상과 새 스크립트를 조용히 통과시키지
않는지, 그리고 **실제 레포 HEAD 가 통과하는지**(픽스처만으로는 "동작한다"가 아니다)를 고정한다.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from module_loader import load_module_by_path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build-directory-branch.py"

mod = load_module_by_path(SCRIPT, "build_directory_branch_t")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "-q",
        "-m",
        message,
    )
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@example.com")
    _git(tmp_path, "init", "-q", "-b", "main", "--object-format=sha1")
    root = tmp_path / "plugins" / "common"
    files = {
        ".claude-plugin/plugin.json": json.dumps({"name": "kit", "version": "1.0.0"}),
        "hooks/hooks.json": '{"hooks": {}}',
        "hooks/session-start.py": "print('x')\n",
        "setup/session-check.py": "print('x')\n",
        "setup/pre-commit": "#!/bin/sh\nexit 0\n",
        "tools/checklist.py": "print('x')\n",
        "rules/CHECKSUMS.sha256": "abc  r.md\n",
        "rules/VERSION": "1\n",
        "rules/r.md": "---\ntier: core\n---\nrule\n",
        "skills/a/SKILL.md": "---\nname: a\ndescription: d\n---\n",
        "skills/auto-dev/SKILL.md": "---\nname: auto-dev\ndescription: d\n---\nRun `<kit>/tools/checklist.py`.\n",
        "skills/c/SKILL.md": "---\nname: c\ndescription: d\n---\n\nDispatch implement-code in parallel.\n",
        "skills/code-intel/SKILL.md": "---\nname: code-intel\ndescription: d\n---\n",
        "skills/session-history/SKILL.md": "---\nname: session-history\ndescription: d\n---\n",
        "skills/harness-export/SKILL.md": "---\nname: harness-export\ndescription: d\n---\n",
        "agents/fix.md": AGENT,
        "README.md": "# kit\n\nimplement-code runs in a worktree.\n",
        "evals/.gitignore": "*.json\n",
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    (root / "assets").mkdir()
    (root / "assets" / "icon.png").write_bytes(PNG)
    _commit_all(tmp_path, "init")
    return tmp_path


PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
AGENT = (
    "---\nname: fix\ndescription: |\n  fixes bugs\nmodel: sonnet\n"
    "isolation: worktree\ntools:\n  - Read\n---\n\nisolation: body line stays\n"
)


def _files(repo: Path, rev: str) -> set[str]:
    return set(_git(repo, "ls-tree", "-r", "--name-only", rev).splitlines())


def _check_fails(repo: Path, match: str) -> None:
    with pytest.raises(SystemExit, match=match):
        mod.main(["--check", "--repo", str(repo)])


def test_write_builds_the_directory_edition(repo: Path) -> None:
    src = _git(repo, "rev-parse", "HEAD")
    assert mod.main(["--write", "--repo", str(repo)]) == 0
    files = _files(repo, "directory")
    for gone in (
        "hooks/hooks.json",
        "hooks/session-start.py",
        "setup/pre-commit",
        "tools/checklist.py",
        "rules/CHECKSUMS.sha256",
        "rules/VERSION",
        "skills/code-intel/SKILL.md",
        "skills/session-history/SKILL.md",
        "skills/harness-export/SKILL.md",
    ):
        assert f"plugins/common/{gone}" not in files, gone
    assert {
        "plugins/common/skills/a/SKILL.md",
        "plugins/common/rules/r.md",
        "plugins/common/agents/fix.md",
        "plugins/common/assets/icon.png",
        "plugins/common/evals/.gitignore",
    } <= files
    agent = _git(repo, "show", "directory:plugins/common/agents/fix.md")
    front, rest = agent.split("\n---\n", 1)
    assert "isolation" not in front
    assert "model: sonnet" in front and "  - Read" in front
    # 격리를 지운 에이전트는 frontmatter 바로 뒤에 머리말 — 본문의 같은 글자는 그대로
    assert rest.startswith("\n> **디렉토리판 — worktree 격리 없음.**")
    assert "isolation: body line stays" in rest
    assert _git(repo, "rev-list", "--parents", "-n1", "directory").split()[1:] == [src]
    # 작업 트리·인덱스는 건드리지 않는다
    assert (repo / "plugins/common/hooks/hooks.json").exists()
    assert "isolation: worktree\n" in (repo / "plugins/common/agents/fix.md").read_text()
    assert _git(repo, "status", "--porcelain") == ""


def test_notes_on_documents_that_lean_on_removed_parts(repo: Path) -> None:
    """뺀 도구를 가리키는 문서·격리를 지운 에이전트를 부르는 문서에는 머리말, 아무것도 안 가리키면 그대로."""
    mod.main(["--write", "--repo", str(repo)])
    b = _git(repo, "show", "directory:plugins/common/skills/auto-dev/SKILL.md")
    c = _git(repo, "show", "directory:plugins/common/skills/c/SKILL.md")
    a = _git(repo, "show", "directory:plugins/common/skills/a/SKILL.md")
    readme = _git(repo, "show", "directory:plugins/common/README.md")
    assert "디렉토리판 — 훅·도구 없음" in b and b.startswith("---\nname: auto-dev")
    # 머리말 뒤에는 빈 줄 — 없으면 Markdown 이 다음 문단을 인용 블록에 흡수한다
    assert "\n\nRun `<kit>/tools/checklist.py`." in b
    assert "디렉토리판 — worktree 격리 없음" in c
    assert "디렉토리판" not in a
    assert "디렉토리판" not in readme  # 플러그인 README 는 본문에서 직접 설명한다


def test_strip_keys_only_touches_top_frontmatter() -> None:
    text = "---\na: 1\nisolation: worktree\nb: 2\n---\nisolation: y\n"
    assert mod._strip_keys(text, ("isolation",)) == "---\na: 1\nb: 2\n---\nisolation: y\n"
    assert mod._strip_keys("no frontmatter\nisolation: z\n", ("isolation",)) == "no frontmatter\nisolation: z\n"


@pytest.mark.parametrize(
    "front",
    [
        "isolation:\n  worktree\n",  # 블록 값 — 지우면 옆 키에 값이 붙는다
        "maxTurns: 20\nisolation: worktree\n  more\n",  # 들여쓴 이어짐
        "\"isolation\": worktree\n",  # 따옴표 키
        "  isolation: worktree\n",  # 들여쓴 키
    ],
)
def test_ambiguous_key_forms_stop_the_build(repo: Path, front: str) -> None:
    (repo / "plugins/common/agents/fix.md").write_text("---\nname: fix\n" + front + "---\nbody\n")
    _commit_all(repo, "ambiguous")
    _check_fails(repo, "한 줄짜리|들여쓴")


@pytest.mark.parametrize(
    "raw",
    [
        b"\xef\xbb\xbf---\nname: fix\nisolation: worktree\n---\n",  # BOM
        b"--- \nname: fix\nisolation: worktree\n---\n",  # 여는 줄 뒤 공백
        b"---\r\nname: fix\r\nisolation: worktree\r\n---\r\n",  # CRLF
        b"---\nname: fix\nisolation: worktree\n--- \n\n# T\n\n---\n\nbody\n",  # 닫는 줄 뒤 공백 + 본문 수평선
    ],
)
def test_malformed_frontmatter_stops_the_build(repo: Path, raw: bytes) -> None:
    """정확한 `---` 줄이 아닌 경계는 변환하지 않고 멈춘다 — 머리말이 frontmatter 위나 수평선 뒤에 들어가지 않게."""
    (repo / "plugins/common/agents/fix.md").write_bytes(raw)
    _commit_all(repo, "odd frontmatter")
    _check_fails(repo, "정확히 `---`")


def test_leftover_key_is_found_by_an_independent_scan(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """지우는 변환이 빠져도(회귀) 결과 검사가 지우는 코드와 다른 방법으로 남은 키를 찾는다."""
    monkeypatch.setattr(mod, "_transform", lambda rel, text: text)
    _check_fails(repo, "지운 frontmatter 키가 남았다")


def test_non_ascii_agent_path_is_stripped(repo: Path) -> None:
    (repo / "plugins/common/agents/한글 에이전트.md").write_text(AGENT)
    _commit_all(repo, "korean name")
    mod.main(["--write", "--repo", str(repo)])
    text = _git(repo, "show", "directory:plugins/common/agents/한글 에이전트.md")
    assert "isolation: worktree" not in text.split("\n---\n", 1)[0]


def test_non_utf8_agent_fails_with_a_message(repo: Path) -> None:
    (repo / "plugins/common/agents/latin.md").write_bytes(b"---\nname: x\ndescription: caf\xe9\n---\n")
    _commit_all(repo, "latin-1")
    _check_fails(repo, "UTF-8")


def test_write_is_idempotent_and_fast_forward(repo: Path) -> None:
    mod.main(["--write", "--repo", str(repo)])
    first = _git(repo, "rev-parse", "directory")
    mod.main(["--write", "--repo", str(repo)])
    assert _git(repo, "rev-parse", "directory") == first

    (repo / "plugins/common/skills/a/SKILL.md").write_text(
        "---\nname: a\ndescription: e\n---\n"
    )
    src2 = _commit_all(repo, "change")
    mod.main(["--write", "--repo", str(repo)])
    second = _git(repo, "rev-parse", "directory")
    assert _git(repo, "rev-list", "--parents", "-n1", second).split()[1:] == [
        first,
        src2,
    ]


def test_older_source_does_not_roll_the_branch_back(repo: Path) -> None:
    """CI 작업이 push 순서와 다르게 끝나도(뒤 커밋 먼저) 옛 원본으로 되돌아가지 않는다."""
    old = _git(repo, "rev-parse", "HEAD")
    (repo / "plugins/common/skills/a/SKILL.md").write_text("---\nname: a\ndescription: new\n---\n")
    _commit_all(repo, "newer")
    mod.main(["--write", "--repo", str(repo)])
    tip = _git(repo, "rev-parse", "directory")
    mod.main(["--write", "--source", old, "--repo", str(repo)])
    assert _git(repo, "rev-parse", "directory") == tip


def test_source_other_than_head_with_changed_excluded_files(repo: Path) -> None:
    """`--source` 가 HEAD 와 다르고 그 사이 제외 경로가 바뀌어도 된다 — 임시 인덱스만 고친다."""
    old = _git(repo, "rev-parse", "HEAD")
    (repo / "plugins/common/tools/checklist.py").write_text("print('changed')\n")
    _commit_all(repo, "tool change")
    assert mod.main(["--check", "--source", old, "--repo", str(repo)]) == 0


def test_docs_only_change_makes_no_new_commit(repo: Path) -> None:
    """디렉토리는 추적 브랜치의 새 커밋마다 재스캔하고 심사 중 버전을 대체한다 — 문서만 바뀌면 갱신하지 않는다."""
    mod.main(["--write", "--repo", str(repo)])
    first = _git(repo, "rev-parse", "directory")
    (repo / "docs").mkdir()
    (repo / "docs" / "note.md").write_text("only docs\n")
    _commit_all(repo, "docs")
    mod.main(["--write", "--repo", str(repo)])
    assert _git(repo, "rev-parse", "directory") == first


def test_excluded_only_change_makes_no_new_commit(repo: Path) -> None:
    """디렉토리판에서 빠지는 파일만 바뀌면(훅 스크립트 수정) 디렉토리판 플러그인 폴더는 같다 — 갱신하지 않는다."""
    mod.main(["--write", "--repo", str(repo)])
    first = _git(repo, "rev-parse", "directory")
    (repo / "plugins/common/hooks/session-start.py").write_text("print('y')\n")
    _commit_all(repo, "hook only")
    mod.main(["--write", "--repo", str(repo)])
    assert _git(repo, "rev-parse", "directory") == first


def test_check_does_not_touch_refs(repo: Path) -> None:
    assert mod.main(["--check", "--repo", str(repo)]) == 0
    assert (
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "rev-parse",
                "--verify",
                "--quiet",
                "refs/heads/directory",
            ],
            capture_output=True,
            check=False,
        ).returncode
        != 0
    )


def test_missing_excluded_path_fails(repo: Path) -> None:
    """뺄 경로가 원본에 없으면(이름 변경) 아무것도 빼지 않은 트리를 디렉토리판이라 부르지 않는다."""
    _git(repo, "mv", "plugins/common/tools", "plugins/common/tools2")
    _commit_all(repo, "rename")
    _check_fails(repo, "뺄 경로가 없다")


@pytest.mark.parametrize(
    ("rel", "data"),
    [
        ("skills/a/run.py", b"print(1)\n"),
        ("skills/a/script", b"echo hi\n"),
        ("skills/a/notes.md", b"#!/bin/sh\necho hi\n"),
        ("skills/a/bom.md", b"\xef\xbb\xbf#!/bin/sh\necho hi\n"),
        ("skills/a/style.css", b"a{}\n"),
        ("skills/a/README.py", b"import os\n"),
        ("skills/a/data.json", b"{not json\n"),
        ("skills/a/fake.png", b"not an image"),
        ("skills/a/nul.txt", b"a\0b\n"),
    ],
)
def test_new_file_the_directory_refuses_fails(repo: Path, rel: str, data: bytes) -> None:
    """새 스크립트·허용 형식 밖·내용이 형식과 다른 파일은 조용히 빠지지 않고 빌드를 red 로 만든다."""
    (repo / "plugins/common" / rel).write_bytes(data)
    _commit_all(repo, "new file")
    _check_fails(repo, "받지 않는 파일")


def test_reference_to_removed_path_without_note_fails(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """머리말을 넣는 변환이 빠지면(회귀) 뺀 경로를 가리키는 문서·격리를 지운 에이전트가 그대로 나가지 않는다."""
    monkeypatch.setattr(mod, "_transform", lambda rel, text: mod._strip_keys(text, ("isolation",)) if rel.startswith("agents/") else text)
    _check_fails(repo, "머리말이 있어야 하는데 없는 문서")


@pytest.mark.parametrize(
    "body",
    ["Run `<kit>/tools/new_tool.py`.\n", "Use the `code-intel` skill.\n"],
)
def test_new_document_pointing_at_removed_parts_fails(repo: Path, body: str) -> None:
    """허용 목록 밖의 새 문서가 뺀 도구·스킬을 가리키면 조용히 머리말만 달고 나가지 않는다 — 뺄지 남길지 사람이 정한다."""
    (repo / "plugins/common/skills/new").mkdir()
    (repo / "plugins/common/skills/new/SKILL.md").write_text("---\nname: new\ndescription: d\n---\n" + body)
    _commit_all(repo, "new skill")
    _check_fails(repo, "새 문서")


def test_symlink_or_executable_file_fails(repo: Path) -> None:
    link = repo / "plugins/common/skills/a/link.md"
    link.symlink_to("../../tools/checklist.py")
    _commit_all(repo, "symlink")
    _check_fails(repo, "받지 않는 파일")
    _git(repo, "rm", "-q", "plugins/common/skills/a/link.md")
    exe = repo / "plugins/common/skills/a/run.md"
    exe.write_text("# run\n")
    exe.chmod(0o755)
    _commit_all(repo, "exec bit")
    _check_fails(repo, "받지 않는 파일")


def test_manifest_hooks_field_fails(repo: Path) -> None:
    manifest = repo / "plugins/common/.claude-plugin/plugin.json"
    manifest.write_text(
        json.dumps({"name": "kit", "version": "1.0.0", "hooks": "./hooks/other.json"})
    )
    _commit_all(repo, "inline hooks")
    _check_fails(repo, "hooks 필드")


def test_fixture_tree_golden(repo: Path) -> None:
    source = _git(repo, "rev-parse", "HEAD")
    assert mod.derive_tree(repo, source) == "a6fa60585fba1a326650c63b5cec8f48db0eea9f"


def test_real_repo_plugin_tree_oracle() -> None:
    source = "ab468bf3ff576ac349f1af1de6d21009626d3faa"
    assert mod._rev(REPO_ROOT, source) == source, (
        f"Directory oracle source commit {source} is missing. "
        "Fetch history containing this commit (CI uses fetch-depth: 0)."
    )
    tree = mod.derive_tree(REPO_ROOT, source)
    plugin_tree = _git(REPO_ROOT, "rev-parse", f"{tree}:plugins/common")
    assert plugin_tree == "364f51e6d4ef8ba952ae91301a935a3d5e70689c"


def test_real_repo_head_passes() -> None:
    assert mod.main(["--check", "--repo", str(REPO_ROOT)]) == 0
