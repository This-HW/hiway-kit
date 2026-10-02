"""Unit tests for scripts/build-site-redirects.py (v5.2.2).

두 층을 본다.

1. **실물 표**(`site/redirects.json`)가 스펙이 요구한 매핑을 실제로 담는가 — 픽스처로
   초록인 생성기가 실물 표에 닿기 전에는 검증되지 않았다(`docs/conventions/warning-signal.md`
   §측정 1). 그래서 실물 표를 직접 읽는다.
2. **생성기**가 적대적 표를 거부하는가 — 절대경로·`..`·심링크·중복·다른 호스트로 가는 `to`.
   픽스처 표는 전부 tmp 아래에 만들고 실물 `site/public` 은 건드리지 않는다.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from module_loader import load_module_by_path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
SCRIPT = SCRIPTS_DIR / "build-site-redirects.py"
NEW_SITE = "https://hiway.thishw.com"


def _load_module() -> ModuleType:
    return load_module_by_path(SCRIPT, "build_site_redirects")


_mod = _load_module()


def _real_table() -> dict:
    return _mod.load_table(REPO_ROOT / "site" / "redirects.json")


def _page_map() -> dict[str, str]:
    return {e["from"]: e["to"] for e in _real_table()["pages"]}


def _minimal_table() -> dict:
    return {
        "newSite": NEW_SITE,
        "pages": [{"from": "/a/", "to": "/ko/a/", "lang": "ko"}],
        "feeds": [{"from": "/index.xml", "to": "/ko/blog/index.xml", "lang": "ko"}],
        "notFound": {"to": "/"},
        "static": {"robots.txt": "User-agent: *\n"},
        "retired": [{"from": "/sitemap.xml", "reason": "x"}],
    }


def _fake_repo(tmp_path: Path, table: dict) -> Path:
    root = tmp_path / "repo"
    (root / "site").mkdir(parents=True)
    (root / "site" / "redirects.json").write_text(json.dumps(table), encoding="utf-8")
    return root


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ── 실물 표 ────────────────────────────────────────────────────────────────


def test_real_table_is_valid_and_renders():
    files = _mod.render(_real_table())
    assert "404.html" in files and "index.html" in files and "robots.txt" in files


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("/", "/ko/"),
        ("/en/", "/"),
        ("/getting-started/", "/ko/docs/getting-started/"),
        ("/en/getting-started/", "/docs/getting-started/"),
        ("/about/", "/ko/docs/concepts/"),
        ("/en/about/", "/docs/concepts/"),
        ("/posts/", "/ko/blog/"),
        (
            "/posts/2026-07-02-harness-engineering-in-practice/",
            "/ko/blog/harness-engineering-in-practice/",
        ),
        (
            "/posts/2026-07-03-auditing-your-own-gates/",
            "/ko/blog/auditing-your-own-gates/",
        ),
        (
            "/posts/2026-07-03-durable-executor-machine-gate/",
            "/ko/blog/durable-executor-machine-gate/",
        ),
        (
            "/posts/2026-07-07-the-last-task-never-closes/",
            "/ko/blog/the-last-task-never-closes/",
        ),
        # 내린 글 — 시점에 묶인 리서치라 이관하지 않았다. 목록으로 보낸다.
        ("/posts/2026-07-02-harness-loop-engineering-landscape/", "/ko/blog/"),
    ],
)
def test_real_table_maps_spec_paths(old: str, new: str):
    assert _page_map()[old] == new


def test_every_stub_points_at_the_new_site_and_is_noindex():
    table = _real_table()
    files = _mod.render(table)
    for entry in table["pages"]:
        rel = entry["from"].lstrip("/") + "index.html"
        body = files[rel]
        target = NEW_SITE + entry["to"]
        assert f'<link rel="canonical" href="{target}">' in body, entry
        assert f'content="0; url={target}"' in body, entry
        assert 'name="robots" content="noindex"' in body, entry
        assert f'<a href="{target}">' in body, entry
    assert f'href="{NEW_SITE}/"' in files["404.html"]


def test_render_is_deterministic():
    assert _mod.render(_real_table()) == _mod.render(_real_table())


def test_feeds_are_minimal_rss_pointing_at_the_new_feed():
    table = _real_table()
    files = _mod.render(table)
    for entry in table["feeds"]:
        body = files[entry["from"].lstrip("/")]
        assert body.startswith('<?xml version="1.0" encoding="utf-8"?>')
        assert f"{NEW_SITE}{entry['to']}" in body, entry


# ── 경로 봉쇄 계약 (D-15) ───────────────────────────────────────────────────


def test_resolve_in_repo_satisfies_shared_contract(tmp_path: Path):
    from resolve_in_repo_contract import assert_resolve_in_repo_contract

    assert_resolve_in_repo_contract(_mod._resolve_in_repo, tmp_path)


# ── 적대적 표 ──────────────────────────────────────────────────────────────


def _bad(mutate) -> dict:
    table = _minimal_table()
    mutate(table)
    return table


ADVERSARIAL = {
    "absolute_from": lambda t: t["pages"].__setitem__(
        0, {"from": "//etc/x/", "to": "/a/", "lang": "ko"}
    ),
    "dotdot_from": lambda t: t["pages"].__setitem__(
        0, {"from": "/../../x/", "to": "/a/", "lang": "ko"}
    ),
    "no_leading_slash_from": lambda t: t["pages"].__setitem__(
        0, {"from": "a/", "to": "/a/", "lang": "ko"}
    ),
    "external_host_to": lambda t: t["pages"].__setitem__(
        0, {"from": "/a/", "to": "//evil.example/", "lang": "ko"}
    ),
    "absolute_url_to": lambda t: t["pages"].__setitem__(
        0, {"from": "/a/", "to": "https://evil.example/", "lang": "ko"}
    ),
    "quote_in_to": lambda t: t["pages"].__setitem__(
        0, {"from": "/a/", "to": '/a/"onload="x/', "lang": "ko"}
    ),
    "bad_lang": lambda t: t["pages"].__setitem__(
        0, {"from": "/a/", "to": "/a/", "lang": "fr"}
    ),
    "feed_to_not_feed": lambda t: t["feeds"].__setitem__(
        0, {"from": "/index.xml", "to": "/ko/blog/", "lang": "ko"}
    ),
    "duplicate_page": lambda t: t["pages"].append(
        {"from": "/a/", "to": "/b/", "lang": "ko"}
    ),
    "page_collides_with_static": lambda t: t["static"].__setitem__("a/index.html", "x"),
    "retired_but_generated": lambda t: t["retired"].append(
        {"from": "/a/index.html", "reason": "x"}
    ),
    "file_is_also_directory": lambda t: t["static"].__setitem__("a", "x"),
    "new_site_with_path": lambda t: t.__setitem__("newSite", NEW_SITE + "/sub"),
}


@pytest.mark.parametrize("case", sorted(ADVERSARIAL))
def test_adversarial_tables_are_rejected_by_check(tmp_path: Path, case: str):
    root = _fake_repo(tmp_path, _bad(ADVERSARIAL[case]))
    result = _run(root, "--check")
    assert result.returncode == 1, (case, result.stdout, result.stderr)
    assert "✗" in result.stderr


def test_minimal_table_control_passes(tmp_path: Path):
    """대조군 — 위 거부가 과도한 봉쇄가 아니라 각 변형 때문임을 보인다."""
    root = _fake_repo(tmp_path, _minimal_table())
    result = _run(root, "--check")
    assert result.returncode == 0, result.stderr


def test_check_does_not_write_and_write_does(tmp_path: Path):
    root = _fake_repo(tmp_path, _minimal_table())
    assert _run(root, "--check").returncode == 0
    assert not (root / "site" / "public").exists()
    assert _run(root, "--write").returncode == 0
    out = root / "site" / "public"
    assert (out / "a" / "index.html").is_file()
    assert (out / "index.xml").is_file()
    assert (out / "404.html").is_file()
    assert (out / "robots.txt").read_text(encoding="utf-8") == "User-agent: *\n"
    assert not (out / "sitemap.xml").exists()  # retired 는 만들지 않는다


def test_symlink_inside_out_dir_cannot_redirect_writes_outside(tmp_path: Path):
    """산출 디렉토리 안의 심링크로 레포 밖에 쓰는 길 — check·write 둘 다 막는다."""
    root = _fake_repo(tmp_path, _minimal_table())
    outside = tmp_path / "outside"
    outside.mkdir()
    out = root / "site" / "public"
    out.mkdir()
    (out / "a").symlink_to(outside, target_is_directory=True)
    for mode in ("--check", "--write"):
        result = _run(root, mode)
        assert result.returncode == 1, (mode, result.stdout, result.stderr)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("flag", ["--out", "--table"])
def test_cli_paths_outside_repo_are_rejected(tmp_path: Path, flag: str):
    root = _fake_repo(tmp_path, _minimal_table())
    result = _run(root, "--check", flag, str(tmp_path / "elsewhere"))
    assert result.returncode == 1
    assert "레포 루트 밖" in result.stderr


def test_special_characters_never_reach_html_attributes_raw():
    """`&` 는 URL 에서 퍼센트 인코딩되고(속성 안에 날것으로 못 간다), 남는 특수문자는 이스케이프된다."""
    table = _minimal_table()
    table["pages"][0]["to"] = "/a&b/"
    body = _mod.render(table)["a/index.html"]
    assert "a%26b" in body and "a&b" not in body
