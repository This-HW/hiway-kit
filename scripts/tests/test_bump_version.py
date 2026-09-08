"""Unit tests for scripts/bump-version.sh (W-022 / Track B S1).

`bump-version.sh`는 셸 스크립트라 파이썬 모듈로 import할 수 없다 — `subprocess`로
호출하고 종료코드·stdout·생성 파일을 검사한다. 전부 스크래치 사본(`tmp_path`)에서
돈다 — 실제 레포의 `packaging/targets.json`·`plugins/common`은 절대 건드리지 않는다
(`scripts/tests/test_build_targets.py`와 동일 원칙).

**실제 버전은 여기서도 절대 bump하지 않는다** — 전부 스크래치 SSOT를 대상으로 한다.
"""

from __future__ import annotations

import json
import shutil
import stat
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
BUMP_SH = SCRIPTS_DIR / "bump-version.sh"

SSOT = {
    "name": "fixture-kit",
    "version": "1.0.0",
    "description": "fixture plugin for bump-version tests",
    "author": {
        "name": "Fixture Org",
        "email": "fixture@example.com",
        "url": "https://example.com",
    },
    "homepage": "https://example.com",
    "repository": "https://example.com/repo",
    "license": "MIT",
    "keywords": ["fixture"],
}

POLICY = {
    "source": {
        "pluginRoot": "plugins/common",
        "manifest": "plugins/common/.claude-plugin/plugin.json",
        "_meta": {"componentDirs": ["skills", "agents", "rules", "hooks"]},
    },
    "targets": [
        {
            "id": "codex",
            "enabled": True,
            "manifestPath": "plugins/common/.codex-plugin/plugin.json",
            "requiredFields": ["name", "version", "description"],
        }
    ],
    "gate": {"requireGeneratedManifestPresent": True},
}


def _fake_repo(tmp_path: Path, *, changelog_version: str = "1.0.0") -> Path:
    root = tmp_path / "repo"
    claude_plugin = root / "plugins" / "common" / ".claude-plugin"
    claude_plugin.mkdir(parents=True)
    (claude_plugin / "plugin.json").write_text(
        json.dumps(SSOT, indent=2), encoding="utf-8"
    )
    (root / "packaging").mkdir(parents=True)
    (root / "packaging" / "targets.json").write_text(
        json.dumps(POLICY, indent=2), encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{changelog_version}] — 2026-01-01\n\ninit\n",
        encoding="utf-8",
    )
    return root


def _run_bump(root: Path, version: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(BUMP_SH), version, "--repo-root", str(root)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


# ── 1. 정상 bump ──────────────────────────────────────────────────────────────


def test_normal_bump_updates_ssot_and_exits_zero(tmp_path):
    root = _fake_repo(tmp_path)
    result = _run_bump(root, "1.1.0")
    assert result.returncode == 0, result.stdout + result.stderr
    ssot_path = root / "plugins" / "common" / ".claude-plugin" / "plugin.json"
    assert json.loads(ssot_path.read_text())["version"] == "1.1.0"


# ── 2. 생성물 재생성 확인 ──────────────────────────────────────────────────────


def test_bump_regenerates_target_manifest_with_new_version(tmp_path):
    root = _fake_repo(tmp_path)
    result = _run_bump(root, "1.1.0")
    assert result.returncode == 0, result.stdout + result.stderr
    codex_manifest = root / "plugins" / "common" / ".codex-plugin" / "plugin.json"
    assert codex_manifest.exists()
    data = json.loads(codex_manifest.read_text())
    assert data["version"] == "1.1.0"
    assert "✓ 자기 검증: 생성물이 SSOT와 일치" in result.stdout


# ── 3. --check 실패 시 스크립트 실패 ──────────────────────────────────────────
#
# build-targets.py 자체는(S1~S3 테스트로) --write 직후 --check가 항상 일치함을
# 이미 증명했다 — 그래서 정상 경로에서는 이 실패가 "일어날 수 없다"(자기모순).
# bump-version.sh의 **오류 전파 로직**만 독립적으로 검증하려면 build-targets.py를
# 항상 실패하는 스텁으로 바꿔치기해야 한다 — bump-version.sh와 스텁을 스크래치
# scripts/ 디렉토리에 나란히 복사해서 돈다(`$HERE/build-targets.py`가 스텁을 가리키게).


def _scratch_bump_with_stub_build_targets(tmp_path: Path, *, check_fails: bool) -> Path:
    scripts_dir = tmp_path / "scratch-scripts"
    scripts_dir.mkdir(parents=True)
    shutil.copy2(BUMP_SH, scripts_dir / "bump-version.sh")
    check_exit = "1" if check_fails else "0"
    stub = f"""#!/usr/bin/env python3
import sys
if "--write" in sys.argv:
    print("[stub] write ok")
    sys.exit(0)
if "--check" in sys.argv:
    print("[stub] check reports drift" if {check_fails} else "[stub] check clean")
    sys.exit({check_exit})
sys.exit(1)
"""
    stub_path = scripts_dir / "build-targets.py"
    stub_path.write_text(stub, encoding="utf-8")
    for p in (scripts_dir / "bump-version.sh", stub_path):
        p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return scripts_dir


def test_bump_fails_when_self_check_reports_drift(tmp_path):
    root = _fake_repo(tmp_path)
    scripts_dir = _scratch_bump_with_stub_build_targets(tmp_path, check_fails=True)
    result = subprocess.run(
        [
            "bash",
            str(scripts_dir / "bump-version.sh"),
            "1.1.0",
            "--repo-root",
            str(root),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "자기 검증 실패" in result.stderr


def test_bump_succeeds_when_self_check_is_clean(tmp_path):
    """대조군 — 스텁이 clean을 보고하면 정상 종료한다(위 실패가 스텁 자체의 결함이 아님을 확인)."""
    root = _fake_repo(tmp_path)
    scripts_dir = _scratch_bump_with_stub_build_targets(tmp_path, check_fails=False)
    result = subprocess.run(
        [
            "bash",
            str(scripts_dir / "bump-version.sh"),
            "1.1.0",
            "--repo-root",
            str(root),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ── 4. 잘못된 버전 형식 거부 ───────────────────────────────────────────────────


def test_rejects_malformed_version_and_touches_nothing(tmp_path):
    root = _fake_repo(tmp_path)
    ssot_path = root / "plugins" / "common" / ".claude-plugin" / "plugin.json"
    before = ssot_path.read_text()

    for bad in ("1.1", "v1.1.0", "1.1.0-rc1", "not-a-version"):
        result = _run_bump(root, bad)
        assert result.returncode == 1, (
            f"{bad!r} should be rejected: {result.stdout}{result.stderr}"
        )
        assert "버전 형식 오류" in result.stderr

    assert ssot_path.read_text() == before  # 아무것도 갱신되지 않았다
