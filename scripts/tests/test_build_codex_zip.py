"""Unit tests for scripts/build-codex-zip.py.

OpenAI 포털은 버전마다 ZIP 을 손으로 올린다. 올리기 전에 문서화된 오류 코드를 로컬에서
잡는지, 그리고 **실제 레포 패키지가 통과하는지**(픽스처만으로는 "동작한다"가 아니다)를 고정한다.
계기: `interface.category: "Coding"` 이 포털 허용 목록 밖이었다 [confirmed 2026-09-28].
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from module_loader import load_module_by_path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build-codex-zip.py"

GOOD_MANIFEST = {
    "name": "kit",
    "version": "1.0.0",
    "description": "d",
    "author": {"name": "Dev"},
    "skills": "./skills/",
    "interface": {
        "displayName": "kit",
        "shortDescription": "short",
        "longDescription": "What the plugin does, in full.",
        "developerName": "Dev",
        "category": "Developer Tools",
        "logo": "./assets/icon.png",
        "composerIcon": "./assets/icon.png",
    },
}
GOOD_SKILL = "---\nname: a\ndescription: does a\n---\n\n# body\n"


@pytest.fixture(scope="module")
def mod():
    return load_module_by_path(SCRIPT, "build_codex_zip_t")


def _zip(entries: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _package(manifest: dict | None = None, **overrides: str | bytes | None) -> bytes:
    entries: dict[str, str | bytes | None] = {
        "kit/.codex-plugin/plugin.json": json.dumps(manifest or GOOD_MANIFEST),
        "kit/skills/a/SKILL.md": GOOD_SKILL,
        "kit/assets/icon.png": b"png",
        **{k.replace("__", "/"): v for k, v in overrides.items()},
    }
    return _zip({k: v for k, v in entries.items() if v is not None})


def test_real_repo_package_passes(mod, tmp_path):
    """픽스처가 아니라 실물 — 레포의 플러그인 루트로 실제 ZIP 을 만들어 검사한다."""
    out = tmp_path / "real.zip"
    top = mod.build_zip(REPO_ROOT, out)
    errors, _ = mod.validate(out.read_bytes())
    assert errors == []
    names = zipfile.ZipFile(out).namelist()
    assert all(n.startswith(f"{top}/") for n in names)
    assert f"{top}/plugin.json" not in names, (
        "Antigravity 루트 매니페스트는 제출 ZIP 에서 빠져야 한다"
    )


def test_good_fixture_passes(mod):
    assert mod.validate(_package()) == ([], [])


def test_unknown_category_is_error(mod):
    """되돌려-FAIL 의 단위판 — 실제로 밟은 값("Coding")을 그대로 넣는다."""
    manifest = json.loads(json.dumps(GOOD_MANIFEST))
    manifest["interface"]["category"] = "Coding"
    errors, _ = mod.validate(_package(manifest))
    assert any("plugin_category_unknown" in e for e in errors)


def test_root_plugin_json_is_error(mod):
    errors, _ = mod.validate(
        _package(kit__plugin__json=None, **{"kit/plugin.json": "{}"})
    )
    assert any("root plugin.json" in e for e in errors)


def test_sibling_at_archive_root_is_error(mod):
    errors, _ = mod.validate(_package(**{"README.md": "x"}))
    assert any("plugin_root_has_siblings" in e for e in errors)


def test_listing_text_over_30_chars_is_error(mod):
    manifest = json.loads(json.dumps(GOOD_MANIFEST))
    manifest["interface"]["shortDescription"] = "x" * 31
    errors, _ = mod.validate(_package(manifest))
    assert any("shortDescription" in e for e in errors)


def test_missing_declared_icon_is_error(mod):
    errors, _ = mod.validate(_package(**{"kit/assets/icon.png": None}))
    assert any("declared_asset_file_missing" in e for e in errors)


def test_block_scalar_description_is_not_counted_as_pass(mod):
    """검사하지 못한 것을 통과로 세지 않는다."""
    skill = "---\nname: a\ndescription: |\n  long text\n---\n\n# body\n"
    errors, _ = mod.validate(_package(**{"kit/skills/a/SKILL.md": skill}))
    assert any("not checkable locally" in e for e in errors)


def test_no_skill_is_error(mod):
    errors, _ = mod.validate(_package(**{"kit/skills/a/SKILL.md": None}))
    assert "plugin_runtime_surface_missing" in errors


def test_mcp_config_is_error(mod):
    errors, _ = mod.validate(_package(**{"kit/.mcp.json": "{}"}))
    assert any("excluded config present" in e for e in errors)


def test_duplicate_skill_name_is_error(mod):
    errors, _ = mod.validate(_package(**{"kit/skills/b/SKILL.md": GOOD_SKILL}))
    assert any("skill_identity_duplicate" in e for e in errors)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_or_blank_long_description_is_error(mod, value):
    """되돌려-FAIL 의 단위판 — 포털이 실제로 이것 하나로 업로드를 거부했다(2026-09-30)."""
    manifest = json.loads(json.dumps(GOOD_MANIFEST))
    if value is None:
        del manifest["interface"]["longDescription"]
    else:
        manifest["interface"]["longDescription"] = value
    errors, _ = mod.validate(_package(manifest))
    assert any("plugin_long_description_empty" in e for e in errors)


def test_long_description_over_limit_is_error(mod):
    manifest = json.loads(json.dumps(GOOD_MANIFEST))
    manifest["interface"]["longDescription"] = "x" * 4001
    errors, _ = mod.validate(_package(manifest))
    assert any("plugin_long_description_too_long" in e for e in errors)
