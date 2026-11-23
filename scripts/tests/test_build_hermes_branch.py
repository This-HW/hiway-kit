"""Unit tests for scripts/build-hermes-branch.py — Hermes 판(Agent Plugins v1 축소판) 빌더.

판 변환(빼기·루트 매니페스트·`using-hiway-kit` description·Hermes 머리말·판 README)과 결과 트리
판정(AP v1·스킬 frontmatter·스킬 수·심링크·서브모듈·`plugin.yaml` 부재)을 **양성·음성 쌍**으로 고정한다.
그리고 **실레포 HEAD 가 통과하는지**를 병합 전에 pytest 로 돌린다 — 픽스처만으로는 "동작한다"가 아니다.
근거: docs/specs/2026-11-24-hermes-edition/design-verdict.md D1·D2·D3("H1 전 — 빌더").
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from module_loader import load_module_by_path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build-hermes-branch.py"
P = "plugins/common"

with pytest.MonkeyPatch.context() as _mp:
    _mp.syspath_prepend(str(SCRIPT.parent))
    mod = load_module_by_path(SCRIPT, "build_hermes_branch_t")
    dirmod = load_module_by_path(
        REPO_ROOT / "scripts" / "build-directory-branch.py",
        "build_directory_branch_for_hermes_t",
    )
    bt = load_module_by_path(
        REPO_ROOT / "scripts" / "build-targets.py", "build_targets_for_hermes_t"
    )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--no-verify", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


#: 판에 남는 스킬 15종(실레포와 같은 이름) + 빼는 2종.
KEPT_SKILLS = (
    "agent-creator",
    "auto-dev",
    "brainstorming",
    "child-session",
    "code-intel",
    "control-loop",
    "cross-engine-review",
    "debug",
    "multi-perspective-review",
    "plan-task",
    "review",
    "session-history",
    "test",
    "using-hiway-kit",
    "web-research",
)
FOUR = ("implement-code", "fix-bugs", "write-tests", "sync-docs")

#: 픽스처의 머리말 허용 목록 — 실레포 상수 대신 이것으로 바꿔 끼운다.
FIX_MISSING_DOCS = frozenset({"skills/auto-dev/SKILL.md", "rules/chain.md"})
FIX_ISOLATION_DOCS = frozenset(
    {
        *(f"agents/{a}.md" for a in FOUR),
        "skills/test/SKILL.md",
        "skills/auto-dev/SKILL.md",
    }
)


def _skill(name: str, extra: str = "", body: str = "") -> str:
    return f"---\nname: {name}\ndescription: Does {name} things.\n{extra}---\n\n# {name}\n{body}"


def _policy(enabled: bool = False) -> dict:
    real = json.loads((REPO_ROOT / "packaging" / "targets.json").read_text())
    hermes = next(t for t in real["targets"] if t["id"] == "hermes")
    target = {k: v for k, v in hermes.items() if not k.startswith("_")}
    target["enabled"] = enabled
    target["_disabledReason"] = "researched-only — fixture"
    return {"source": real["source"], "targets": [target]}


SSOT = {
    "name": "hiway-kit",
    "version": "9.9.9",
    "description": "Fixture kit.",
    "author": {"name": "t", "url": "https://example.com"},
    "homepage": "https://example.com/",
    "repository": "https://example.com/r",
    "license": "MIT",
    "keywords": ["a", "b"],
    "icon": "./assets/icon.png",
}


@pytest.fixture(autouse=True)
def _fixture_allowlists(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    if "real_repo" in request.node.name:
        return
    monkeypatch.setattr(mod, "MISSING_PATHS_DOCS", FIX_MISSING_DOCS)
    monkeypatch.setattr(mod, "ISOLATION_NOTE_DOCS", FIX_ISOLATION_DOCS)
    monkeypatch.setattr(mod, "MISSING_PATHS_EXEMPT", {})


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    for key in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{key}_NAME", "t")
        monkeypatch.setenv(f"GIT_{key}_EMAIL", "t@example.com")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main", "--object-format=sha1")
    files = {
        "packaging/targets.json": json.dumps(_policy(), indent=2),
        f"{P}/.claude-plugin/plugin.json": json.dumps(SSOT, indent=2),
        f"{P}/plugin.json": json.dumps(
            {
                "$schema": "https://antigravity.google/schemas/v1/plugin.json",
                "name": "hiway-kit",
            }
        ),
        f"{P}/README.md": "# kit\n\nRun harness-export. implement-code runs in a worktree.\n",
        f"{P}/hooks/hooks.json": '{"hooks": {}}',
        f"{P}/hooks/session-start.py": "print('x')\n",
        f"{P}/setup/pre-commit": "#!/bin/sh\nexit 0\n",
        f"{P}/tools/export_harness.py": "print('x')\n",
        f"{P}/rules/CHECKSUMS.sha256": "abc  r.md\n",
        f"{P}/rules/VERSION": "1\n",
        f"{P}/rules/r.md": "---\ntier: core\n---\nrule\n",
        f"{P}/rules/chain.md": "---\ntier: reference\n---\nSee `hooks/session-start.py`.\n",
        f"{P}/skills/harness-export/SKILL.md": _skill("harness-export"),
        f"{P}/skills/skill-forge/SKILL.md": _skill("skill-forge"),
        f"{P}/.codex-plugin/plugin.json": json.dumps({"hooks": "./hooks/hooks-codex.json"}),
        f"{P}/.cursor-plugin/plugin.json": json.dumps({"name": "hiway-kit"}),
        f"{P}/skills/review/agents/openai.yaml": "interface:\n  short_description: x\n",
        f"{P}/skills/using-hiway-kit/agents/openai.yaml": "interface:\n  short_description: hook-injected\n",
        f"{P}/assets/icon.png": "png",
        f"{P}/evals/debug/case.yaml": "prompt: x\n",
        f"{P}/agents/review-code.md": "---\nname: review-code\nmodel: opus\n---\n\nReview.\n",
    }
    for name in KEPT_SKILLS:
        files[f"{P}/skills/{name}/SKILL.md"] = _skill(name)
    files[f"{P}/skills/using-hiway-kit/SKILL.md"] = (
        f"---\nname: using-hiway-kit\ndescription: {mod.EXPECTED_USING_DESCRIPTION}\n"
        "disable-model-invocation: true\n---\n\n# Using hiway-kit\n"
    )
    files[f"{P}/skills/auto-dev/SKILL.md"] = _skill(
        "auto-dev", body="Read `hooks/session-start.py`. Dispatch implement-code.\n"
    )
    files[f"{P}/skills/test/SKILL.md"] = _skill(
        "test", body="On failure call fix-bugs.\n"
    )
    files[f"{P}/skills/plan-task/references/x.md"] = "Plain reference.\n"
    for a in FOUR:
        files[f"{P}/agents/{a}.md"] = (
            f"---\nname: {a}\nmodel: sonnet\nisolation: worktree\n---\n\n{a} commits in its worktree.\n"
        )
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    for exe in (f"{P}/setup/pre-commit", f"{P}/tools/export_harness.py"):
        (root / exe).chmod(0o700)
    _commit_all(root, "init")
    return root


def _write(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text)


def _check_fails(repo: Path, match: str) -> None:
    with pytest.raises(SystemExit, match=match):
        mod.main(["--check", "--repo", str(repo)])


def _tree(repo: Path) -> str:
    return mod.derive_tree(repo, _git(repo, "rev-parse", "HEAD"))


def _show(repo: Path, tree: str, rel: str) -> str:
    return _git(repo, "cat-file", "-p", f"{tree}:{P}/{rel}")


def _files(repo: Path, tree: str) -> set[str]:
    return set(_git(repo, "ls-tree", "-r", "--name-only", tree, "--", P).splitlines())


# --- 판 변환: 양성 -------------------------------------------------------------------------------


def test_check_builds_the_hermes_edition(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert mod.main(["--check", "--repo", str(repo)]) == 0
    out = capsys.readouterr().out.splitlines()
    head = _git(repo, "rev-parse", "HEAD")
    first = next(line for line in out if "판 트리" in line)
    m = re.fullmatch(
        r"\[hermes-edition\] ✓ 판 트리 ([0-9a-f]{40}) \(원본 ([0-9a-f]{7})\)", first
    )
    assert m and m.group(2) == head[:7]
    tree = m.group(1)
    plugin = [line for line in out if "plugin tree:" in line]
    # 디렉토리 빌더와 같은 형식 계약 — `[<label>] plugin tree: <40자 sha>` 한 줄
    assert plugin == [
        f"[hermes-edition] plugin tree: {_git(repo, 'rev-parse', f'{tree}:{P}')}"
    ]
    assert "[hermes-edition] skills: 15" in out
    files = _files(repo, tree)
    for gone in (
        "hooks/hooks.json",
        "hooks/session-start.py",
        "setup/pre-commit",
        "rules/CHECKSUMS.sha256",
        "evals/debug/case.yaml",
        "skills/harness-export/SKILL.md",
        "skills/skill-forge/SKILL.md",
        ".codex-plugin/plugin.json",
        ".cursor-plugin/plugin.json",
        "skills/review/agents/openai.yaml",
        "skills/using-hiway-kit/agents/openai.yaml",
    ):
        assert f"{P}/{gone}" not in files, gone
    for kept in (
        ".claude-plugin/plugin.json",
        "tools/export_harness.py",
        "rules/r.md",
        "rules/VERSION",  # tools/export_harness.py 가 필수로 읽는다(H1 P4 실측 결함)
        "plugin.json",
    ):
        assert f"{P}/{kept}" in files, kept
    # 작업 트리·인덱스·ref 는 건드리지 않는다
    assert _git(repo, "status", "--porcelain") == ""
    assert _git(repo, "branch", "--list", "hermes") == ""


def test_root_manifest_is_the_build_targets_ap_v1_manifest(repo: Path) -> None:
    tree = _tree(repo)
    raw = _show(repo, tree, "plugin.json") + "\n"
    policy = _policy()
    expected = bt.build_manifest(
        SSOT, policy["targets"][0], {"skills", "agents", "rules"}
    )
    assert raw == bt._dumps(expected)  # 같은 매핑·같은 직렬화 — 두 벌이 아니다
    assert json.loads(raw)["$schema"] == bt.AP_V1_SCHEMA_URL
    assert bt.ap_v1_violations(json.loads(raw)) == []
    assert "icon" not in json.loads(raw)


def test_using_description_is_replaced_and_key_kept(repo: Path) -> None:
    text = _show(repo, _tree(repo), "skills/using-hiway-kit/SKILL.md")
    assert f"description: {mod.HERMES_USING_DESCRIPTION}\n" in text
    assert "hook-injected" not in mod.HERMES_USING_DESCRIPTION
    assert "session-start" not in mod.HERMES_USING_DESCRIPTION.lower()
    assert "disable-model-invocation: true\n" in text
    assert mod.EXPECTED_USING_DESCRIPTION not in text


def test_hermes_notes_are_placed_exactly(repo: Path) -> None:
    tree = _tree(repo)
    agent_m = mod._note_marker(mod.HERMES_AGENT_NOTE)
    iso_m = mod._note_marker(mod.HERMES_ISOLATION_NOTE)
    miss_m = mod._note_marker(mod.HERMES_MISSING_PATHS_NOTE)
    for a in FOUR:
        t = _show(repo, tree, f"agents/{a}.md")
        assert agent_m in t and iso_m in t and miss_m not in t
        assert t.startswith(f"---\nname: {a}\n")
        assert (
            "isolation: worktree" in t
        )  # Hermes 판은 키를 지우지 않는다(집행되지 않음을 머리말로 알린다)
    rc = _show(repo, tree, "agents/review-code.md")
    assert agent_m in rc and iso_m not in rc
    auto = _show(repo, tree, "skills/auto-dev/SKILL.md")
    assert iso_m in auto and miss_m in auto and agent_m not in auto
    assert miss_m in _show(repo, tree, "rules/chain.md")
    assert iso_m in _show(repo, tree, "skills/test/SKILL.md")
    for plain in (
        "skills/brainstorming/SKILL.md",
        "rules/r.md",
        "skills/plan-task/references/x.md",
    ):
        t = _show(repo, tree, plain)
        assert "Hermes 판" not in t, plain


def test_hermes_notes_carry_the_required_content() -> None:
    a, i, m = (
        mod.HERMES_AGENT_NOTE,
        mod.HERMES_ISOLATION_NOTE,
        mod.HERMES_MISSING_PATHS_NOTE,
    )
    assert "delegate_task" in a and all(
        k in a for k in ("`model`", "`tools`", "`isolation`")
    )
    assert (
        "delegation.worktree_isolation" in i
        and "공유 CWD" in i
        and "기준 커밋" in i
        and "순차" in i
    )
    assert "export_harness.py --plugin-root" in m and "--entrypoints AGENTS.md" in m
    assert "~/.claude/plugins/cache" in m
    for note in (a, i, m):
        assert note.startswith("> **Hermes 판")
    # 디렉토리판 문구를 재사용하지 않는다 — 표지(첫 줄 40자)도 서로 달라야 한다
    markers = {
        mod._note_marker(n)
        for n in (a, i, m, dirmod.ISOLATION_NOTE, dirmod.MISSING_PATHS_NOTE)
    }
    assert len(markers) == 5
    assert dirmod.ISOLATION_NOTE not in (a, i, m) and dirmod.MISSING_PATHS_NOTE not in (
        a,
        i,
        m,
    )


def test_readme_is_the_hermes_edition_readme(repo: Path) -> None:
    text = _show(repo, _tree(repo), "README.md") + "\n"
    assert text == mod.HERMES_README
    for needle in (
        "Hermes",
        "**15 skills**",
        "hiway-kit:",
        "No hooks",
        "No agent loader",
        "No MCP servers",
        '--ref "$SHA" --force --no-enable',
        "hermes plugins enable hiway-kit",
        "--ref <new 40-char sha> --force",
        "**caution**",
        "critical 0",
        "Use --force to override.",
        "agents/review-code.md",
        "skills/auto-dev/SKILL.md",
        "no automatic update",
        "disable-model-invocation",
        ".hermes.md",
        "Not measured",
        "verify-on-stop",
        "behavioral evals",
        "docs/harnesses.md#hermes-agent",
    ):
        assert needle in text, needle
    # 스캐너 규칙에 걸리는 원문을 README 로 옮기지 않는다(판 README 가 새 high 를 만들지 않게)
    for raw in ("rm -rf", "/etc/passwd", "os.environ"):
        assert raw not in text, raw
    # 원인 문서는 줄 번호 없이 — 본문이 바뀌면 낡는다
    assert re.search(r"(review-code\.md|SKILL\.md):\d", text) is None


# --- 판 변환: 음성 -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "gone",
    [
        "hooks",
        "setup",
        "skills/harness-export",
        "skills/skill-forge",
        "rules/CHECKSUMS.sha256",
        ".codex-plugin",
        ".cursor-plugin",
        "evals",
        "skills/review/agents/openai.yaml skills/using-hiway-kit/agents/openai.yaml",
    ],
)
def test_missing_excluded_path_stops(repo: Path, gone: str) -> None:
    for one in gone.split():
        subprocess.run(["rm", "-rf", str(repo / P / one)], check=True)
    _commit_all(repo, "rename")
    _check_fails(repo, "뺄 경로가 없다")


def test_using_description_drift_stops(repo: Path) -> None:
    path = repo / P / "skills/using-hiway-kit/SKILL.md"
    path.write_text(path.read_text().replace("(hook-injected)", "(injected)"))
    _commit_all(repo, "drift")
    _check_fails(repo, "EXPECTED_USING_DESCRIPTION")


def test_unlisted_doc_pointing_at_removed_path_stops(repo: Path) -> None:
    _write(
        repo,
        f"{P}/skills/review/SKILL.md",
        _skill("review", body="Run `setup/pre-commit`.\n"),
    )
    _commit_all(repo, "new ref")
    _check_fails(repo, "MISSING_PATHS_DOCS")


def test_removed_skill_name_counts_as_removed_path(repo: Path) -> None:
    _write(
        repo,
        f"{P}/skills/review/SKILL.md",
        _skill("review", body="Then run skill-forge.\n"),
    )
    _commit_all(repo, "new ref")
    _check_fails(repo, "MISSING_PATHS_DOCS")


def test_stale_missing_paths_allowlist_stops(repo: Path) -> None:
    _write(
        repo,
        f"{P}/rules/chain.md",
        "---\ntier: reference\n---\nNothing removed here.\n",
    )
    _commit_all(repo, "stale")
    _check_fails(repo, "낡은")


def test_unlisted_isolation_caller_stops(repo: Path) -> None:
    _write(
        repo,
        f"{P}/skills/debug/SKILL.md",
        _skill("debug", body="Hand off to write-tests.\n"),
    )
    _commit_all(repo, "caller")
    _check_fails(repo, "ISOLATION_NOTE_DOCS")


def test_stale_isolation_allowlist_stops(repo: Path) -> None:
    _write(repo, f"{P}/skills/test/SKILL.md", _skill("test", body="No delegation.\n"))
    _commit_all(repo, "stale")
    _check_fails(repo, "낡은")


def test_missing_note_is_caught_by_the_independent_scan(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """변환이 머리말을 빠뜨려도(회귀) 결과 판정이 원본을 따로 스캔해 잡는다."""
    real = mod._transform

    def drop(rel: str, text: str) -> str:
        out = real(rel, text)
        return text if rel == "skills/test/SKILL.md" else out

    monkeypatch.setattr(mod, "_transform", drop)
    _check_fails(repo, "머리말")


def test_unexpected_note_is_caught(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = mod._transform

    def extra(rel: str, text: str) -> str:
        out = real(rel, text)
        if rel == "rules/r.md":
            out = mod._with_note(
                out, mod.HERMES_ISOLATION_NOTE, rel, label=mod._LOG_LABEL
            )
        return out

    monkeypatch.setattr(mod, "_transform", extra)
    _check_fails(repo, "머리말")


def test_description_not_replaced_is_caught(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "_replace_using_description", lambda text, rel: text)
    _check_fails(repo, "description")


# --- 결과 판정: 매니페스트·구조 -------------------------------------------------------------------


def test_ap_v1_violation_in_manifest_stops(repo: Path) -> None:
    bad = dict(SSOT, name="Hiway_Kit")
    _write(repo, f"{P}/.claude-plugin/plugin.json", json.dumps(bad))
    _commit_all(repo, "bad name")
    _check_fails(repo, "AP v1")


@pytest.mark.parametrize("name", ["plugin.yaml", "plugin.yml"])
def test_native_manifest_present_stops(repo: Path, name: str) -> None:
    _write(repo, f"{P}/{name}", "name: x\n")
    _commit_all(repo, "native")
    _check_fails(repo, "plugin.y")


def test_claude_manifest_required(repo: Path) -> None:
    policy = _policy()
    policy["source"]["manifest"] = "packaging/ssot.json"
    _write(repo, "packaging/targets.json", json.dumps(policy))
    _write(repo, "packaging/ssot.json", json.dumps(SSOT))
    (repo / P / ".claude-plugin/plugin.json").unlink()
    _commit_all(repo, "no claude manifest")
    _check_fails(repo, ".claude-plugin/plugin.json")


def test_missing_root_plugin_json_stops(repo: Path) -> None:
    (repo / P / "plugin.json").unlink()
    _commit_all(repo, "no root manifest")
    _check_fails(repo, "plugin.json")


@pytest.mark.parametrize("delta", [-1, 1])
def test_skill_count_must_be_exactly_15(repo: Path, delta: int) -> None:
    if delta < 0:
        subprocess.run(["rm", "-rf", str(repo / P / "skills/review")], check=True)
    else:
        _write(repo, f"{P}/skills/extra/SKILL.md", _skill("extra"))
    _commit_all(repo, "count")
    _check_fails(repo, "15")


def test_skill_dir_without_skill_md_stops(repo: Path) -> None:
    (repo / P / "skills/review/SKILL.md").unlink()
    _write(repo, f"{P}/skills/review/README.md", "x\n")
    _commit_all(repo, "no SKILL.md")
    _check_fails(repo, "SKILL.md")


def test_symlink_stops(repo: Path) -> None:
    os.symlink("rules/r.md", repo / P / "link.md")
    _commit_all(repo, "symlink")
    _check_fails(repo, "심링크")


def test_submodule_stops(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-index", "--add", "--cacheinfo", f"160000,{head},{P}/vendor")
    _git(repo, "commit", "-q", "--no-verify", "-m", "gitlink")
    _check_fails(repo, "서브모듈")


# --- 결과 판정: 스킬 frontmatter(AP 제약) — 양성·음성 쌍 -------------------------------------------

OK_FRONT = [
    'license: MIT\ncompatibility: "Requires git."\nallowed-tools: Read Grep\nmetadata:\n  owner: kit\n  tier: "1"\n',
    "license: 'MIT'\n",
    "# comment line\nmetadata:\n  internal: 'true'\n",
]
BAD_FRONT = [
    ("license: 1\n", "license"),
    ("license: true\n", "license"),
    ("compatibility: " + "x" * 501 + "\n", "compatibility"),
    ("allowed-tools:\n  - Read\n", "allowed-tools"),
    ("metadata: x\n", "metadata"),
    ("metadata:\n  internal: true\n", "metadata"),
    ("metadata:\n  n: 3\n", "metadata"),
    ("metadata:\n  a:\n    b: c\n", "metadata"),
    ("license: |\n  MIT\n", "읽을 수 없는"),
    ("license: MIT # c: d\n", "읽을 수 없는"),
    ("license: MIT\nlicense: Apache\n", "중복"),
]


@pytest.mark.parametrize("extra", OK_FRONT)
def test_valid_skill_frontmatter_passes(repo: Path, extra: str) -> None:
    _write(repo, f"{P}/skills/review/SKILL.md", _skill("review", extra))
    _commit_all(repo, "ok")
    assert mod.main(["--check", "--repo", str(repo)]) == 0


@pytest.mark.parametrize(("extra", "match"), BAD_FRONT)
def test_invalid_skill_frontmatter_stops(repo: Path, extra: str, match: str) -> None:
    _write(repo, f"{P}/skills/review/SKILL.md", _skill("review", extra))
    _commit_all(repo, "bad")
    _check_fails(repo, match)


@pytest.mark.parametrize(
    ("front", "match"),
    [
        ("---\nname: other\ndescription: d\n---\n", "name"),
        ("---\nname: Review\ndescription: d\n---\n", "name"),
        ("---\ndescription: d\n---\n", "name"),
        ("---\nname: review\ndescription: ''\n---\n", "description"),
        ("---\nname: review\n---\n", "description"),
        ("---\nname: review\ndescription: " + "x" * 1025 + "\n---\n", "description"),
        ("---\nname: review\ndescription: 12\n---\n", "description"),
        ("# no frontmatter\n", "frontmatter"),
    ],
)
def test_skill_name_and_description_rules(repo: Path, front: str, match: str) -> None:
    _write(repo, f"{P}/skills/review/SKILL.md", front)
    _commit_all(repo, "bad")
    _check_fails(repo, match)


def test_skill_name_regex_rejects_double_hyphen(repo: Path) -> None:
    subprocess.run(
        ["mv", str(repo / P / "skills/review"), str(repo / P / "skills/re--view")],
        check=True,
    )
    _write(repo, f"{P}/skills/re--view/SKILL.md", _skill("re--view"))
    _commit_all(repo, "double hyphen")
    _check_fails(repo, "name")


def test_description_at_limit_passes(repo: Path) -> None:
    _write(
        repo,
        f"{P}/skills/review/SKILL.md",
        "---\nname: review\ndescription: " + "x" * 1024 + "\n---\n",
    )
    _commit_all(repo, "limit")
    assert mod.main(["--check", "--repo", str(repo)]) == 0


# --- CLI: --write ---------------------------------------------------------------------------------


def test_write_refused_when_disabled(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert mod.main(["--write", "--repo", str(repo)]) == 1
    out = capsys.readouterr().out
    assert "enabled" in out and "researched-only — fixture" in out
    assert _git(repo, "branch", "--list", "hermes") == ""


def test_write_when_enabled_updates_the_branch(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(repo, "packaging/targets.json", json.dumps(_policy(enabled=True)))
    src = _commit_all(repo, "enable")
    assert mod.main(["--write", "--repo", str(repo)]) == 0
    tip = _git(repo, "rev-parse", "refs/heads/hermes")
    assert _git(repo, "rev-list", "--parents", "-n1", tip).split()[1:] == [src]
    assert _git(repo, "rev-parse", f"{tip}^{{tree}}") == _tree(repo)
    assert "hermes: v9.9.9" in _git(repo, "log", "-1", "--format=%s", tip)
    # 같은 플러그인 폴더면 새 커밋을 만들지 않는다(공용 배관)
    assert mod.main(["--write", "--repo", str(repo)]) == 0
    assert _git(repo, "rev-parse", "refs/heads/hermes") == tip


# --- CLI: --out -----------------------------------------------------------------------------------


def test_out_exports_the_plugin_tree(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "out"
    assert mod.main(["--out", str(out_dir), "--repo", str(repo)]) == 0
    tree = _tree(repo)
    expected = {f[len(P) + 1 :] for f in _files(repo, tree)}
    got = {str(p.relative_to(out_dir)) for p in out_dir.rglob("*") if p.is_file()}
    assert got == expected
    assert os.access(out_dir / "tools/export_harness.py", os.X_OK)
    assert not os.access(out_dir / "rules/r.md", os.X_OK)
    assert (out_dir / "plugin.json").read_text() == _show(
        repo, tree, "plugin.json"
    ) + "\n"
    text = capsys.readouterr().out
    plugin_tree = _git(repo, "rev-parse", f"{tree}:{P}")
    assert f"파일 {len(expected)}개" in text and plugin_tree in text


def test_out_accepts_existing_empty_dir(repo: Path, tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    assert mod.main(["--out", str(tmp_path / "empty"), "--repo", str(repo)]) == 0


def test_out_refuses_non_empty_dir(repo: Path, tmp_path: Path) -> None:
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / ".keep").write_text("")
    with pytest.raises(SystemExit, match="비어 있지 않다"):
        mod.main(["--out", str(tmp_path / "full"), "--repo", str(repo)])
    assert [p.name for p in (tmp_path / "full").iterdir()] == [".keep"]


@pytest.mark.parametrize("rel", ["inside", ".", "../repo/x", ".git/out"])
def test_out_refuses_paths_in_the_repo(repo: Path, rel: str) -> None:
    with pytest.raises(SystemExit, match="레포 안"):
        mod.main(["--out", str(repo / rel), "--repo", str(repo)])
    assert not (repo / "inside").exists()


def test_out_refuses_symlink_into_the_repo(repo: Path, tmp_path: Path) -> None:
    os.symlink(repo, tmp_path / "alias")
    with pytest.raises(SystemExit, match="레포 안"):
        mod.main(["--out", str(tmp_path / "alias" / "x"), "--repo", str(repo)])


def test_out_self_check_catches_divergence(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """내보낸 파일 집합이 트리와 다르면(회귀) 스스로 대조해 실패한다."""
    real = mod._export_files

    def lossy(repo_: Path, entries: list, dest: Path) -> None:
        real(repo_, entries[1:], dest)

    monkeypatch.setattr(mod, "_export_files", lossy)
    with pytest.raises(SystemExit, match="대조"):
        mod.main(["--out", str(tmp_path / "o"), "--repo", str(repo)])


# --- 실레포 -----------------------------------------------------------------------------------------


def test_real_repo_head_check_passes() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--source", "HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = proc.stdout.splitlines()
    assert any(
        re.fullmatch(
            r"\[hermes-edition\] ✓ 판 트리 [0-9a-f]{40} \(원본 [0-9a-f]{7}\)", x
        )
        for x in lines
    )
    assert any(
        re.fullmatch(r"\[hermes-edition\] plugin tree: [0-9a-f]{40}", x) for x in lines
    )
    assert "[hermes-edition] skills: 15" in lines


def test_real_repo_using_description_matches_constant() -> None:
    text = (REPO_ROOT / P / "skills/using-hiway-kit/SKILL.md").read_text()
    assert f"\ndescription: {mod.EXPECTED_USING_DESCRIPTION}\n" in text


# --- 판의 도구가 판 안에서 실제로 돈다 (H1 P4 실측 결함의 클래스 회귀) ----------------------------------
#
# 판에서 파일을 뺄 때 "훅만 읽는다"는 분류가 틀리면(rules/VERSION — export_harness.py 가 필수로 읽는다)
# 판의 유일한 규칙 내보내기 경로가 죽는다. 정적 판정은 도구가 여는 경로를 문자열로 다 찾아내지 못하므로
# (경로가 `plugin_root / "rules" / "VERSION"` 처럼 조립된다) **실레포 판을 --out 으로 내보내 실제로 돌린다**.


def _tool_env() -> dict[str, str]:
    # 셸에 남은 다른 설치의 플러그인 루트를 집지 않게 — --plugin-root 만으로 돌아야 한다
    return {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}


@pytest.fixture(scope="module")
def real_repo_out(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("hermes-out") / "edition"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out), "--source", "HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return out


def test_real_repo_edition_export_harness_runs(real_repo_out: Path, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    proc = subprocess.run(
        [
            sys.executable,
            str(real_repo_out / "tools" / "export_harness.py"),
            "--plugin-root",
            str(real_repo_out),
            "--target",
            str(project),
            "--entrypoints",
            "AGENTS.md",
        ],
        capture_output=True,
        text=True,
        cwd=project,
        env=_tool_env(),
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    agents = (project / "AGENTS.md").read_text()
    version = (real_repo_out / "rules" / "VERSION").read_text().strip()
    assert re.search(
        rf"(?m)^<!-- kit:begin rules-v{re.escape(version)} sha256:[0-9a-f]{{64}} -->$", agents
    ), agents[:400]
    assert re.search(r"(?m)^<!-- kit:end -->$", agents)


def test_real_repo_edition_checklist_runs(real_repo_out: Path, tmp_path: Path) -> None:
    tool = str(real_repo_out / "tools" / "checklist.py")
    plan = tmp_path / "plan"
    plan.mkdir()
    item = '[{"id": "a", "description": "d", "acceptance": "x", "verify": "true"}]'
    for args in (["init", str(plan), item], ["show", str(plan)]):
        proc = subprocess.run(
            [sys.executable, tool, *args],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            env=_tool_env(),
            check=False,
        )
        assert proc.returncode == 0, (args[0], proc.stdout + proc.stderr)
    assert (plan / "checklist.json").is_file()


# --- 리뷰 수정 2 (ATK-002..010) -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        "Look in `hooks/` first.\n",  # 슬래시 뒤 백틱
        "The hooks/ folder is gone.\n",  # 슬래시 뒤 공백
        "The session-start 훅 reads plans.\n",  # 훅 stem 만
        "자식 스킬이 쓰고, 훅 예시가 읽는다.\n",  # "훅 예시"
        "훅(auto-format·stop-validator)과 같은 조건이다.\n",
        "Run pre-commit.\n",
        "Verify CHECKSUMS before injecting.\n",
    ],
)
def test_wide_scan_catches_common_spellings(repo: Path, body: str) -> None:
    """변환 정규식이 놓치는 흔한 표기를 판정의 넓은 스캔이 잡는다(ATK-002)."""
    _write(repo, f"{P}/skills/review/SKILL.md", _skill("review", body=body))
    _commit_all(repo, "spelling")
    _check_fails(repo, "MISSING_PATHS_DOCS")


def test_exempt_doc_passes_with_a_reason(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(repo, f"{P}/skills/review/SKILL.md", _skill("review", body="Run pre-commit.\n"))
    _commit_all(repo, "exempt")
    monkeypatch.setattr(mod, "MISSING_PATHS_EXEMPT", {"skills/review/SKILL.md": "소비자 자기 설정"})
    assert mod.main(["--check", "--repo", str(repo)]) == 0
    tree = _tree(repo)
    assert "Hermes 판" not in _show(repo, tree, "skills/review/SKILL.md")


def test_stale_exemption_stops(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "MISSING_PATHS_EXEMPT", {"skills/review/SKILL.md": "x"})
    _check_fails(repo, "MISSING_PATHS_EXEMPT 가 낡은")


def test_path_reference_cannot_be_exempted(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(repo, f"{P}/skills/review/SKILL.md", _skill("review", body="Run `setup/pre-commit`.\n"))
    _commit_all(repo, "exempt path")
    monkeypatch.setattr(mod, "MISSING_PATHS_EXEMPT", {"skills/review/SKILL.md": "x"})
    _check_fails(repo, "제외할 수 없다")


def test_wide_scan_allowlisted_doc_gets_the_note(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(repo, f"{P}/skills/review/SKILL.md", _skill("review", body="The session-start 훅 reads plans.\n"))
    _commit_all(repo, "listed")
    monkeypatch.setattr(mod, "MISSING_PATHS_DOCS", FIX_MISSING_DOCS | {"skills/review/SKILL.md"})
    tree = _tree(repo)
    assert mod._note_marker(mod.HERMES_MISSING_PATHS_NOTE) in _show(repo, tree, "skills/review/SKILL.md")


@pytest.mark.parametrize("name", ["Plugin.yaml", "PLUGIN.YML", "plugin.YAML"])
def test_native_manifest_case_variants_stop(repo: Path, name: str) -> None:
    _git(repo, "update-index", "--add", "--cacheinfo",
         f"100644,{_git(repo, 'hash-object', '-w', str(repo / P / 'rules/r.md'))},{P}/{name}")
    _git(repo, "commit", "-q", "--no-verify", "-m", "native variant")
    _check_fails(repo, "네이티브")


def test_second_plugin_json_candidate_stops(repo: Path) -> None:
    blob = _git(repo, "hash-object", "-w", str(repo / P / "plugin.json"))
    _git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{P}/Plugin.json")
    _git(repo, "commit", "-q", "--no-verify", "-m", "two manifests")
    _check_fails(repo, "정확히 하나")


def test_manifest_pointing_at_missing_path_stops(repo: Path) -> None:
    (repo / P / "assets/icon.png").unlink()
    _commit_all(repo, "icon gone")
    _check_fails(repo, "판에 없는 경로")


def test_out_refuses_case_variant_of_the_repo(repo: Path) -> None:
    variant = repo.parent / repo.name.upper()
    if not variant.exists():
        pytest.skip("대소문자를 구분하는 파일시스템 — 변형 경로가 같은 디렉토리가 아니다")
    with pytest.raises(SystemExit, match="레포 안"):
        mod.main(["--out", str(variant / "x"), "--repo", str(repo)])
    assert not (repo / "x").exists()


def test_out_refuses_other_worktrees(repo: Path, tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "--detach", str(wt))
    with pytest.raises(SystemExit, match="레포 안"):
        mod.main(["--out", str(wt / "x"), "--repo", str(repo)])
    assert not (wt / "x").exists()


def test_out_does_not_overwrite_a_dir_filled_after_the_check(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """검사 뒤·쓰기 전에 누가 디렉토리를 채우면 rename 이 실패하고 그 내용을 건드리지 않는다(ATK-010)."""
    dest = tmp_path / "late"
    dest.mkdir()
    real = mod._export_files

    def fill_then_export(repo_: Path, entries: list, out: Path) -> None:
        (dest / "theirs.txt").write_text("keep")
        real(repo_, entries, out)

    monkeypatch.setattr(mod, "_export_files", fill_then_export)
    with pytest.raises(SystemExit, match="비어 있지 않다"):
        mod.main(["--out", str(dest), "--repo", str(repo)])
    assert [p.name for p in dest.iterdir()] == ["theirs.txt"]
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".late.")] == []


@pytest.mark.parametrize(
    ("extra", "match"),
    [
        ("license:\tMIT\n", "읽을 수 없는"),  # 키 뒤 탭
        ("license: a:\tb\n", "읽을 수 없는"),  # 값 안 `:\t`
        ("metadata:\n\towner: kit\n", "탭 들여쓰기"),
        ("metadata:\n  \towner: kit\n", "탭 들여쓰기"),
    ],
)
def test_tabs_in_frontmatter_stop(repo: Path, extra: str, match: str) -> None:
    _write(repo, f"{P}/skills/review/SKILL.md", _skill("review", extra))
    _commit_all(repo, "tabs")
    _check_fails(repo, match)


@pytest.mark.parametrize(("length", "ok"), [(64, True), (65, False)])
def test_skill_name_length_cap(repo: Path, length: int, ok: bool) -> None:
    name = "r" * length
    subprocess.run(["mv", str(repo / P / "skills/review"), str(repo / P / f"skills/{name}")], check=True)
    _write(repo, f"{P}/skills/{name}/SKILL.md", _skill(name))
    _commit_all(repo, "long name")
    if ok:
        assert mod.main(["--check", "--repo", str(repo)]) == 0
    else:
        _check_fails(repo, "64자")


def test_disable_model_invocation_compared_explicitly() -> None:
    assert mod._same_scalar(mod._NonStr("true"), mod._NonStr("true"))
    assert not mod._same_scalar(mod._NonStr("true"), mod._NonStr("True"))
    assert not mod._same_scalar(mod._NonStr("true"), "true")
    assert not mod._same_scalar("1", mod._NonStr("1"))
    # repr 이 같아도 타입이 다르면 다르다 — str()/repr 비교는 이것을 같다고 본다(ATK-010)
    assert not mod._same_scalar(repr(mod._NonStr("true")), mod._NonStr("true"))


def test_disable_model_invocation_value_change_stops(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = mod._transform

    def flip(rel: str, text: str) -> str:
        out = real(rel, text)
        return out.replace("disable-model-invocation: true", "disable-model-invocation: false")

    monkeypatch.setattr(mod, "_transform", flip)
    _check_fails(repo, "disable-model-invocation")


def test_write_refuses_other_branches(repo: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        mod.main(["--write", "--branch", "main", "--repo", str(repo)])
    assert exc.value.code == 2


def test_write_refuses_source_outside_main(repo: Path) -> None:
    _write(repo, "packaging/targets.json", json.dumps(_policy(enabled=True)))
    _commit_all(repo, "enable")
    _git(repo, "checkout", "-q", "-b", "side")
    _write(repo, f"{P}/rules/r.md", "---\ntier: core\n---\nside\n")
    side = _commit_all(repo, "side")
    _git(repo, "checkout", "-q", "main")
    with pytest.raises(SystemExit, match="조상"):
        mod.main(["--write", "--source", side, "--repo", str(repo)])
    assert _git(repo, "branch", "--list", "hermes") == ""


def test_isolation_note_states_precedence() -> None:
    assert "이 머리말이 아래 본문의 worktree·커밋 지시보다 우선한다" in mod.HERMES_ISOLATION_NOTE


# --- 수정 4: evals/ 제외와 H1 실측 README ---------------------------------------------------------


def test_h1_facts_are_constants_in_the_readme() -> None:
    """실측에 묶인 사실(caution·--force·15)은 상수 — README 가 그 값을 그대로 담는다. 실측이 바뀌면 사람이 고친다."""
    assert mod.H1_SCAN_VERDICT == "caution"
    assert mod.H1_FORCE_FLAG == "--force"
    assert mod.EXPECTED_SKILL_COUNT == 15
    assert mod.H1_BLOCK_MESSAGE == "Use --force to override."
    for fact in (
        f"**{mod.H1_SCAN_VERDICT}**",
        mod.H1_BLOCK_MESSAGE,
        f'--ref "$SHA" {mod.H1_FORCE_FLAG}',
        f"**{mod.EXPECTED_SKILL_COUNT} skills**",
        mod.H1_REPLACE_MESSAGE,
        mod.H1_INSTALL_ROOT,
        *mod.H1_SCAN_CAUSES,
    ):
        assert fact in mod.HERMES_README, fact


def test_readme_losing_an_h1_fact_stops(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "HERMES_README", mod.HERMES_README.replace(" --force --no-enable\nhermes", " --no-enable\nhermes"))
    _check_fails(repo, "H1 실측 사실이 빠졌다")


def test_readme_scan_cause_doc_check(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "H1_SCAN_CAUSES", ("agents/review-code.md", "skills/gone/SKILL.md"))
    monkeypatch.setattr(
        mod, "HERMES_README", mod.HERMES_README + "\nskills/gone/SKILL.md\n"
    )
    _check_fails(repo, "스캐너 원인으로 적은 문서가 판에 없다")


def test_real_repo_edition_has_no_evals(real_repo_out: Path) -> None:
    assert not (real_repo_out / "evals").exists()
    assert (real_repo_out / "agents/review-code.md").is_file()
    assert (real_repo_out / "skills/auto-dev/SKILL.md").is_file()
