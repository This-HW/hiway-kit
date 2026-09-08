"""Unit tests for scripts/derive-name.py (D-3 / W-027 27-2).

`scripts/tests/test_build_targets.py` 와 같은 관례를 따른다 — 실제 레포의
`packaging/name-targets.json`이나 `plugins/common`을 건드리지 않고, `--repo-root`/
`--policy`로 전부 임시 픽스처 레포를 가리킨다.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

from module_loader import load_module_by_path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    return load_module_by_path(SCRIPTS_DIR / "derive-name.py", "derive_name")


_mod = _load_module()

SSOT = {"name": "fixture-kit", "version": "1.0.0"}


def _fake_repo(tmp_path: Path, *, last_applied: str = "fixture-kit") -> Path:
    root = tmp_path / "repo"
    claude_plugin = root / "plugins" / "common" / ".claude-plugin"
    claude_plugin.mkdir(parents=True)
    (claude_plugin / "plugin.json").write_text(json.dumps(SSOT), encoding="utf-8")

    (root / "README.md").write_text(
        "# fixture-kit\n\ninstall: fixture-kit@fixture-community\n", encoding="utf-8"
    )
    plugins_common = root / "plugins" / "common"
    plugins_common.mkdir(parents=True, exist_ok=True)
    (plugins_common / "README.md").write_text(
        "fixture-kit common readme\n", encoding="utf-8"
    )
    (root / "CLAUDE.md").write_text("# fixture-kit conventions\n", encoding="utf-8")

    content = root / "site" / "content"
    content.mkdir(parents=True)
    (content / "_index.md").write_text("welcome to fixture-kit\n", encoding="utf-8")
    posts = content / "posts"
    posts.mkdir()
    (posts / "post-1.md").write_text("fixture-kit shipped a thing\n", encoding="utf-8")
    # 이름을 언급하지 않는 문서도 있을 수 있다 — check가 이걸로 false-fail하면 안 된다.
    (posts / "post-2.md").write_text("no product name here\n", encoding="utf-8")

    policy = {
        "source": {
            "manifest": "plugins/common/.claude-plugin/plugin.json",
            "field": "name",
        },
        "lastAppliedName": last_applied,
        "files": ["README.md", "plugins/common/README.md", "CLAUDE.md"],
        "directories": ["site/content"],
    }
    policy_path = root / "packaging" / "name-targets.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    return root


def _run(root: Path, *extra: str) -> int:
    argv = [
        "--repo-root",
        str(root),
        "--policy",
        str(root / "packaging" / "name-targets.json"),
        *extra,
    ]
    return _mod.main(argv)


# ── 1. discover_targets — files + directories 실측, 손으로 나열하지 않음 ────────


def test_discover_targets_includes_files_and_recursive_md(tmp_path):
    root = _fake_repo(tmp_path)
    targets = _mod.discover_targets(
        root, json.loads((root / "packaging" / "name-targets.json").read_text())
    )
    rels = sorted(str(t.relative_to(root.resolve())) for t in targets)
    assert rels == [
        "CLAUDE.md",
        "README.md",
        "plugins/common/README.md",
        "site/content/_index.md",
        "site/content/posts/post-1.md",
        "site/content/posts/post-2.md",
    ]


# ── 2. --check clean when lastAppliedName already matches SSOT ─────────────────


def test_check_green_when_name_unchanged(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--check")
    out = capsys.readouterr().out
    assert rc == 0
    assert "정합" in out


# ── 3. --write is a no-op when SSOT name hasn't moved ───────────────────────────


def test_write_is_noop_when_name_unchanged(tmp_path):
    root = _fake_repo(tmp_path)
    readme = root / "README.md"
    before = readme.read_text(encoding="utf-8")
    rc = _run(root, "--write")
    assert rc == 0
    assert readme.read_text(encoding="utf-8") == before


# ── 4. drift: SSOT renamed, --write not run yet → --check fails ────────────────


def test_check_fails_when_ssot_renamed_and_stale_name_remains(tmp_path, capsys):
    root = _fake_repo(tmp_path, last_applied="old-kit")
    rc = _run(root, "--check")
    out = capsys.readouterr().out
    assert rc == 1
    assert "lastAppliedName" in out or "≠" in out


# ── 5. rename propagation: --write replaces the literal old name everywhere ────


def test_write_propagates_rename_across_all_targets(tmp_path):
    root = _fake_repo(tmp_path, last_applied="old-kit")
    # 파일들은 실제로 옛 이름을 담고 있어야 치환 대상이 된다.
    for rel in ["README.md", "plugins/common/README.md", "CLAUDE.md"]:
        p = root / rel
        p.write_text(
            p.read_text(encoding="utf-8").replace("fixture-kit", "old-kit"),
            encoding="utf-8",
        )
    idx = root / "site" / "content" / "_index.md"
    idx.write_text(
        idx.read_text(encoding="utf-8").replace("fixture-kit", "old-kit"),
        encoding="utf-8",
    )

    rc_write = _mod.main(
        [
            "--repo-root",
            str(root),
            "--policy",
            str(root / "packaging" / "name-targets.json"),
            "--write",
        ]
    )
    assert rc_write == 0
    assert "fixture-kit" in (root / "README.md").read_text(encoding="utf-8")
    assert "old-kit" not in (root / "README.md").read_text(encoding="utf-8")
    assert "fixture-kit" in idx.read_text(encoding="utf-8")

    policy = json.loads((root / "packaging" / "name-targets.json").read_text())
    assert policy["lastAppliedName"] == "fixture-kit"

    rc_check = _mod.main(
        [
            "--repo-root",
            str(root),
            "--policy",
            str(root / "packaging" / "name-targets.json"),
            "--check",
        ]
    )
    assert rc_check == 0


# ── 6. missing target file → --check fails ──────────────────────────────────────


def test_check_fails_when_target_file_missing(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    (root / "CLAUDE.md").unlink()
    rc = _run(root, "--check")
    out = capsys.readouterr().out
    assert rc == 1
    assert "없음" in out


# ── 7. missing SSOT manifest → clean failure, no traceback ─────────────────────


def test_missing_ssot_manifest_clean_failure(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    (root / "plugins" / "common" / ".claude-plugin" / "plugin.json").unlink()
    rc = _run(root, "--check")
    err = capsys.readouterr().err
    assert rc == 1
    assert "SSOT" in err
    assert "Traceback" not in err


# ── 8. path containment — shared adversarial table (D-15) ──────────────────────


def test_resolve_in_repo_shared_adversarial_table(tmp_path):
    from resolve_in_repo_contract import assert_resolve_in_repo_contract

    assert_resolve_in_repo_contract(_mod._resolve_in_repo, tmp_path)


def test_directory_escape_via_policy_is_blocked(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    policy_path = root / "packaging" / "name-targets.json"
    policy = json.loads(policy_path.read_text())
    policy["directories"] = ["../outside"]
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    outside = root.parent / "outside"
    outside.mkdir()
    (outside / "evil.md").write_text("fixture-kit\n", encoding="utf-8")

    rc = _run(root, "--check")
    err = capsys.readouterr().err
    assert rc == 1
    assert "레포 루트 밖" in err


# ── 9. previousNames — 잔존 검사는 lastAppliedName 일치와 **무관하게** 돈다 ──────
#
# 회귀 대상: 잔존 검사가 `last != ssot` 분기 안에 있던 시절, `--write` 직후에는
# 그 분기가 거짓이라 검사가 한 번도 실행되지 않았다. 그래서 파생 대상 목록에
# 뒤늦게 추가된 파일(과거 치환을 받은 적 없는 파일)의 구 이름을 영원히 놓쳤다.
# 실제로 site/hugo.toml 이 그 구멍으로 남았다.


def _seed_previous(root: Path, names: list[str]) -> None:
    pp = root / "packaging" / "name-targets.json"
    policy = json.loads(pp.read_text(encoding="utf-8"))
    policy["previousNames"] = names
    pp.write_text(json.dumps(policy), encoding="utf-8")


def test_check_fails_on_previous_name_even_when_last_applied_matches(tmp_path, capsys):
    root = _fake_repo(tmp_path)  # lastAppliedName == SSOT == "fixture-kit"
    _seed_previous(root, ["old-kit"])
    # 뒤늦게 대상에 추가된 파일처럼, 과거 이름이 남아 있다.
    (root / "CLAUDE.md").write_text("# old-kit conventions\n", encoding="utf-8")

    assert _run(root, "--check") == 1
    out = capsys.readouterr().out
    assert "과거 이름 'old-kit' 잔존" in out
    assert "CLAUDE.md" in out


def test_write_replaces_every_previous_name_not_just_the_last(tmp_path):
    root = _fake_repo(tmp_path, last_applied="mid-kit")
    _seed_previous(root, ["ancient-kit"])
    (root / "CLAUDE.md").write_text(
        "# ancient-kit and mid-kit both appear\n", encoding="utf-8"
    )

    assert _run(root, "--write") == 0
    text = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "ancient-kit" not in text
    assert "mid-kit" not in text
    assert text.count("fixture-kit") == 2

    policy = json.loads((root / "packaging" / "name-targets.json").read_text())
    assert policy["lastAppliedName"] == "fixture-kit"
    # 개명 시 직전 이름이 previousNames 로 누적된다.
    assert policy["previousNames"] == ["ancient-kit", "mid-kit"]

    assert _run(root, "--check") == 0


def test_current_name_is_never_reported_as_stale(tmp_path):
    """개명을 되돌리면 과거 이름이 곧 현재 이름이다 — 그걸 잔재로 신고하면 상시 red."""
    root = _fake_repo(tmp_path)
    _seed_previous(root, ["fixture-kit", "old-kit"])
    assert _mod._stale_names(
        json.loads((root / "packaging" / "name-targets.json").read_text()),
        "fixture-kit",
        "fixture-kit",
    ) == ["old-kit"]
    assert _run(root, "--check") == 0


def test_allowlisted_file_may_mention_a_previous_name(tmp_path):
    """마이그레이션 안내는 구 이름을 불러야 한다 — 그것까지 red면 게이트가 죽는다."""
    root = _fake_repo(tmp_path)
    pp = root / "packaging" / "name-targets.json"
    policy = json.loads(pp.read_text(encoding="utf-8"))
    policy["previousNames"] = ["old-kit"]
    policy["previousNameAllowlist"] = {"README.md": "마이그레이션 안내"}
    pp.write_text(json.dumps(policy), encoding="utf-8")
    (root / "README.md").write_text(
        "# fixture-kit\n\n전임 킷 old-kit 에서 옮겨오려면...\n", encoding="utf-8"
    )

    assert _run(root, "--check") == 0
    # 허용된 파일은 --write 의 치환에서도 제외된다 — 안내문이 자기 자신을 지우면 안 된다.
    assert _run(root, "--write") == 0
    assert "old-kit" in (root / "README.md").read_text(encoding="utf-8")


def test_allowlist_does_not_leak_to_other_files(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    pp = root / "packaging" / "name-targets.json"
    policy = json.loads(pp.read_text(encoding="utf-8"))
    policy["previousNames"] = ["old-kit"]
    policy["previousNameAllowlist"] = {"README.md": "마이그레이션 안내"}
    pp.write_text(json.dumps(policy), encoding="utf-8")
    (root / "README.md").write_text("# fixture-kit\nold-kit 에서 이관\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# old-kit conventions\n", encoding="utf-8")

    assert _run(root, "--check") == 1
    out = capsys.readouterr().out
    assert "CLAUDE.md" in out
    assert "README.md" not in out
