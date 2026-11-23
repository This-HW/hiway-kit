"""Unit tests for scripts/build-targets.py (W-019 / S1-S3).

이 테스트는 **실제 레포의 packaging/targets.json이나 plugins/common을 건드리지 않는다**
— `--repo-root`/`--policy`로 전부 임시 픽스처 레포를 가리킨다 (scripts/tests/test_eval_forge.py의
`_fake_repo` 관례를 따름). "타겟 매니페스트 생성 금지"(S1 금지사항, S2는 codex만·S3는 codex+
antigravity만 허용)를 실제 레포 트리 안에서는 절대 어기지 않기 위함이다.

S2에서 스코프 규칙이 바뀌었다(D1 판정, targets.json v1.1.0): `enabled:true`는 이제
"지금 생성 대상"만 의미하고, `gate.requireGeneratedManifestPresent`가 켜지면 enabled인데
미생성인 매니페스트는 드리프트(exit 1)다. 이 픽스처 정책도 그 게이트를 켜서 실제 정책과
같은 조건으로 검사한다.

S3에서 `passthroughFields`가 추가됐다(SSOT에 있으면 싣고 없으면 조용히 생략 — S2 관찰
승인분, targets.json v1.2.0). 픽스처의 "alpha"는 이를 검증하고, "gamma"는 marketplace가
없는 타겟(Antigravity 모양)의 삭제·드리프트 실증을 alpha와 별도로 검증한다 — STAGE3가
"삭제·훼손 실증을 두 타겟 모두에 대해" 요구하기 때문이다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from module_loader import load_module_by_path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    return load_module_by_path(SCRIPTS_DIR / "build-targets.py", "build_targets")


_mod = _load_module()

SSOT = {
    "name": "fixture-kit",
    "version": "1.0.0",
    "description": "fixture plugin for build-targets tests",
    "author": {"name": "Fixture Org"},
}

POLICY = {
    "version": "1.0.0",
    "source": {
        "pluginRoot": "plugins/common",
        "manifest": "plugins/common/.claude-plugin/plugin.json",
        "_meta": {"componentDirs": ["skills", "agents", "rules", "hooks"]},
    },
    "targets": [
        {
            "id": "alpha",
            "enabled": True,
            "manifestPath": "plugins/common/.alpha-plugin/plugin.json",
            "requiredFields": ["name", "version"],
            "optionalFields": ["description"],
            "componentFields": {"skills": "./skills/"},
            "interface": {"displayName": "Alpha Target"},
            "marketplace": {"path": ".agents/plugins/marketplace.json"},
            "passthroughFields": ["author", "license"],
        },
        {
            "id": "beta",
            "enabled": False,
            "_disabledReason": "fixture: intentionally disabled",
            "manifestPath": "plugins/common/beta-plugin.json",
            "requiredFields": ["name"],
        },
        {
            # Antigravity 모양: marketplace 없음, 필수 필드 최소.
            "id": "gamma",
            "enabled": True,
            "manifestPath": "plugins/common/gamma-plugin.json",
            "requiredFields": ["name"],
            "optionalFields": ["description"],
            "schemaUrl": "https://example.com/schemas/gamma.json",
            "marketplace": None,
        },
    ],
    "gate": {"requireGeneratedManifestPresent": True},
}


def _fake_repo(tmp_path: Path, *, with_skills: bool = True) -> Path:
    root = tmp_path / "repo"
    claude_plugin = root / "plugins" / "common" / ".claude-plugin"
    claude_plugin.mkdir(parents=True)
    (claude_plugin / "plugin.json").write_text(json.dumps(SSOT), encoding="utf-8")
    if with_skills:
        (root / "plugins" / "common" / "skills").mkdir(parents=True)
    policy_path = root / "packaging" / "targets.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(json.dumps(POLICY), encoding="utf-8")
    return root


def _run(root: Path, *extra: str) -> int:
    argv = [
        "--repo-root",
        str(root),
        "--policy",
        str(root / "packaging" / "targets.json"),
        *extra,
    ]
    return _mod.main(argv)


def _update_source(root: Path, field: str, value: str) -> None:
    path = root / "packaging" / "targets.json"
    policy = json.loads(path.read_text())
    policy["source"][field] = value
    path.write_text(json.dumps(policy))


@pytest.mark.parametrize(
    "case",
    [
        (mode, field, escape)
        for mode in ("--check", "--write")
        for field in ("manifest", "pluginRoot")
        for escape in ("absolute", "parent", "symlink")
    ],
)
def test_source_paths_cannot_escape(tmp_path, capsys, case):
    mode, field, escape = case
    root = _fake_repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "plugin.json").write_text(json.dumps(SSOT))
    (root / "link").symlink_to(outside, target_is_directory=True)
    base = {"absolute": str(outside), "parent": "../outside", "symlink": "link"}[escape]
    value = base + "/plugin.json" if field == "manifest" else base
    _update_source(root, field, value)
    assert _run(root, mode) == 1
    assert f"source.{field}: 경로 탈출 차단" in capsys.readouterr().err
    assert not (root / "plugins/common/.alpha-plugin").exists()


@pytest.mark.parametrize("mode", ["--check", "--write"])
def test_component_discovery_cannot_follow_external_symlink(tmp_path, capsys, mode):
    root = _fake_repo(tmp_path, with_skills=False)
    outside = tmp_path / "external-skills"
    outside.mkdir()
    (root / "plugins/common/skills").symlink_to(outside, target_is_directory=True)
    assert _run(root, mode) == 1
    assert "source.componentDirs: 경로 탈출 차단" in capsys.readouterr().err


@pytest.mark.parametrize("field", ["manifest", "pluginRoot"])
def test_internal_source_symlink_remains_supported(tmp_path, field):
    root = _fake_repo(tmp_path)
    original = POLICY["source"][field]
    (root / "internal-link").symlink_to(root / original)
    _update_source(root, field, "internal-link")
    assert _run(root, "--write") == 0
    assert _run(root, "--check") == 0


# ── 1. 정상 생성 ─────────────────────────────────────────────────────────────


def test_write_only_creates_expected_manifest(tmp_path):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--write", "--only", "alpha")
    assert rc == 0
    manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["name"] == "fixture-kit"
    assert data["version"] == "1.0.0"
    assert data["description"] == "fixture plugin for build-targets tests"
    assert data["skills"] == "./skills/"
    assert data["interface"] == {"displayName": "Alpha Target"}
    marketplace = root / ".agents" / "plugins" / "marketplace.json"
    assert marketplace.exists()
    mk = json.loads(marketplace.read_text(encoding="utf-8"))
    assert mk["plugins"][0]["name"] == "fixture-kit"


def test_write_omits_component_field_when_dir_absent(tmp_path):
    root = _fake_repo(tmp_path, with_skills=False)
    rc = _run(root, "--write", "--only", "alpha")
    assert rc == 0
    manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert "skills" not in data


def test_passthrough_field_included_when_present_and_omitted_when_absent(tmp_path):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--write", "--only", "alpha")
    assert rc == 0
    manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["author"] == {"name": "Fixture Org"}  # SSOT에 있음 → 실림
    assert "license" not in data  # SSOT에 없음 → 조용히 생략


def _with_interface_from(root: Path, mapping: dict) -> None:
    path = root / "packaging" / "targets.json"
    policy = json.loads(path.read_text())
    policy["targets"][0]["interfaceFrom"] = mapping
    path.write_text(json.dumps(policy))


def test_interface_from_copies_ssot_values_and_follows_ssot_change(tmp_path):
    root = _fake_repo(tmp_path)
    _with_interface_from(root, {"supportURL": "supportUrl", "logo": "icon"})
    ssot_path = root / "plugins/common/.claude-plugin/plugin.json"
    ssot = {**SSOT, "supportUrl": "https://example.com/issues", "icon": "./a.png"}
    ssot_path.write_text(json.dumps(ssot))
    assert _run(root, "--write", "--only", "alpha") == 0
    manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["interface"] == {
        "displayName": "Alpha Target",  # 리터럴은 그대로
        "supportURL": "https://example.com/issues",
        "logo": "./a.png",
    }
    assert "supportUrl" not in data and "icon" not in data  # 목록 필드는 새지 않는다
    ssot_path.write_text(json.dumps({**ssot, "supportUrl": "https://example.com/new"}))
    assert _run(root, "--check", "--only", "alpha") == 1  # SSOT 변경 = 드리프트


def test_interface_from_missing_ssot_field_is_exit_1(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    _with_interface_from(root, {"supportURL": "supportUrl"})
    assert _run(root, "--write", "--only", "alpha") == 1
    assert "원천 SSOT 필드 'supportUrl' 없음" in capsys.readouterr().err


LISTING_FIELDS = (
    "icon",
    "documentationUrl",
    "supportUrl",
    "privacyPolicyUrl",
    "termsOfServiceUrl",
)


def test_real_repo_listing_fields_stay_in_claude_manifest_only():
    """실제 레포: Claude 디렉토리 목록 필드는 SSOT 에만 있고 어떤 타겟 생성물에도
    최상위 키로 새지 않는다(Cursor 스키마는 additionalProperties:false)."""
    repo = SCRIPTS_DIR.parent
    ssot = json.loads(
        (repo / "plugins/common/.claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    assert all(field in ssot for field in LISTING_FIELDS)
    policy = json.loads((repo / "packaging/targets.json").read_text(encoding="utf-8"))
    enabled = [t for t in policy["targets"] if t.get("enabled")]
    assert enabled
    for target in enabled:
        data = json.loads((repo / target["manifestPath"]).read_text(encoding="utf-8"))
        leaked = [field for field in LISTING_FIELDS if field in data]
        assert not leaked, (target["id"], leaked)


def test_second_target_without_marketplace_generates_manifest_only(tmp_path):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--write", "--only", "gamma")
    assert rc == 0
    manifest = root / "plugins" / "common" / "gamma-plugin.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data == {
        "$schema": "https://example.com/schemas/gamma.json",
        "name": "fixture-kit",
        "description": "fixture plugin for build-targets tests",
    }
    # gamma의 marketplace는 null이므로 alpha용 마켓플레이스 파일이 생기면 안 된다.
    assert not (root / ".agents" / "plugins" / "marketplace.json").exists()


# ── 2. --check 드리프트 감지 ──────────────────────────────────────────────────


def test_check_detects_drift_then_clean_after_revert(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    assert _run(root, "--write", "--only", "alpha") == 0
    manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    original = manifest.read_text(encoding="utf-8")

    assert _run(root, "--check", "--only", "alpha") == 0

    # 한 글자 훼손
    manifest.write_text(
        original.replace("fixture-kit", "tampered-kit"), encoding="utf-8"
    )
    rc_dirty = _run(root, "--check", "--only", "alpha")
    out_dirty = capsys.readouterr().out
    assert rc_dirty == 1
    assert "드리프트" in out_dirty

    # 원복
    manifest.write_text(original, encoding="utf-8")
    rc_clean = _run(root, "--check", "--only", "alpha")
    assert rc_clean == 0


# ── 3. enabled:false 건너뜀 ───────────────────────────────────────────────────


def test_disabled_target_skipped_by_write_and_default_check(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--write", "--only", "beta")
    out = capsys.readouterr().out
    assert rc == 0
    assert "건너뜀" in out
    assert not (root / "plugins" / "common" / "beta-plugin.json").exists()

    # 기본 --check(전체 enabled)도 beta를 건드리지 않는다 — 애초에 대상이 아니다.
    # (alpha·gamma는 enabled라서 미생성 상태로 두면 §7 케이스와 겹치므로 여기서는 먼저 채운다.)
    assert _run(root, "--write", "--only", "alpha") == 0
    assert _run(root, "--write", "--only", "gamma") == 0
    rc_check = _run(root, "--check")
    assert rc_check == 0


# ── 4. SSOT 매니페스트 부재 시 명확한 실패 ───────────────────────────────────


def test_missing_ssot_manifest_clean_failure(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    (root / "plugins" / "common" / ".claude-plugin" / "plugin.json").unlink()
    rc = _run(root, "--check")
    err = capsys.readouterr().err
    assert rc == 1
    assert "SSOT" in err
    assert "Traceback" not in err


def test_unknown_only_id_clean_failure(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--check", "--only", "does-not-exist")
    err = capsys.readouterr().err
    assert rc == 1
    assert "does-not-exist" in err
    assert "Traceback" not in err


# ── 5. --check 는 파일을 쓰지 않는다 ─────────────────────────────────────────


def test_check_never_writes(tmp_path):
    root = _fake_repo(tmp_path)
    manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    before = sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())
    assert not manifest.exists()

    # enabled인데 미생성 → 이제 드리프트(exit 1)지만, 그래도 아무것도 쓰지 않는다.
    assert _run(root, "--check", "--only", "alpha") == 1
    assert not manifest.exists()
    after = sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())
    assert before == after

    # 생성 후에도 --check가 mtime을 건드리지 않는다.
    assert _run(root, "--write", "--only", "alpha") == 0
    mtime_before = manifest.stat().st_mtime_ns
    assert _run(root, "--check", "--only", "alpha") == 0
    assert manifest.stat().st_mtime_ns == mtime_before


# ── 6. 기본 --write(no --only)는 enabled 전체를 쓴다 (S2, D1 승인분 반영) ──────


def test_bare_write_writes_all_enabled_targets(tmp_path):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--write")
    assert rc == 0
    alpha_manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    gamma_manifest = root / "plugins" / "common" / "gamma-plugin.json"
    beta_manifest = root / "plugins" / "common" / "beta-plugin.json"
    assert alpha_manifest.exists()  # enabled:true → 기록됨
    assert gamma_manifest.exists()  # enabled:true → 기록됨
    assert not beta_manifest.exists()  # enabled:false → 여전히 건너뜀


# ── 7. 미생성 = 드리프트 (S2, D1 기각분 반영) ─────────────────────────────────


def test_default_check_fails_when_enabled_target_missing(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    rc = _run(root, "--check")
    out = capsys.readouterr().out
    assert rc == 1
    assert "미생성" in out and "드리프트" in out


# ── 8. 삭제 실증 — 생성 후 지우면 드리프트 (STAGE2 완료조건 5와 같은 축) ───────


def test_check_detects_deletion_as_drift(tmp_path):
    root = _fake_repo(tmp_path)
    assert _run(root, "--write", "--only", "alpha") == 0
    manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    assert _run(root, "--check", "--only", "alpha") == 0

    manifest.unlink()
    assert _run(root, "--check", "--only", "alpha") == 1

    assert _run(root, "--write", "--only", "alpha") == 0
    assert _run(root, "--check", "--only", "alpha") == 0


# ── 9. 삭제·훼손 실증 — 두 번째(marketplace 없는) 타겟에도 동일 (STAGE3 완료조건 4) ──


def test_check_detects_drift_and_deletion_for_second_target(tmp_path):
    root = _fake_repo(tmp_path)
    assert _run(root, "--write", "--only", "gamma") == 0
    manifest = root / "plugins" / "common" / "gamma-plugin.json"
    original = manifest.read_text(encoding="utf-8")
    assert _run(root, "--check", "--only", "gamma") == 0

    # 훼손 → drift
    manifest.write_text(original.replace("fixture-kit", "tampered"), encoding="utf-8")
    assert _run(root, "--check", "--only", "gamma") == 1

    # 재생성 → clean
    assert _run(root, "--write", "--only", "gamma") == 0
    assert _run(root, "--check", "--only", "gamma") == 0

    # 삭제 → drift
    manifest.unlink()
    assert _run(root, "--check", "--only", "gamma") == 1

    # 재생성 → clean, 원본과 byte-identical
    assert _run(root, "--write", "--only", "gamma") == 0
    assert _run(root, "--check", "--only", "gamma") == 0
    assert manifest.read_text(encoding="utf-8") == original


# ── 10. 경로 봉쇄 — 레포 밖 3종 탈출 차단 (적대적 리뷰 2026-08-27, High) ────────
#
# 셋 다 `manifestPath`(정책 파일 문자열)가 레포 루트 밖을 가리키게 만든다. 수정 전
# 코드는 `repo_root / rel_path`를 그대로 썼고, pathlib은 rel_path가 절대경로면
# repo_root를 버린다 — 세 벡터 전부 실제로 레포 밖에 파일을 썼다(수정 전 재현 완료,
# STAGE 보고서 참고). `--check`·`--write` 양쪽 다 막혀야 한다(2.14.1은 --check만
# 빠뜨려 구멍이 났다).


def _escape_repo(tmp_path: Path, manifest_path: str) -> Path:
    """alpha 하나만 있는 최소 레포 — manifestPath만 호출자가 지정."""
    root = tmp_path / "repo"
    claude_plugin = root / "plugins" / "common" / ".claude-plugin"
    claude_plugin.mkdir(parents=True)
    (claude_plugin / "plugin.json").write_text(json.dumps(SSOT), encoding="utf-8")
    policy = {
        "source": {
            "pluginRoot": "plugins/common",
            "manifest": "plugins/common/.claude-plugin/plugin.json",
            "_meta": {"componentDirs": ["skills", "agents", "rules", "hooks"]},
        },
        "targets": [
            {
                "id": "evil",
                "enabled": True,
                "manifestPath": manifest_path,
                "requiredFields": ["name"],
            }
        ],
        "gate": {"requireGeneratedManifestPresent": True},
    }
    policy_path = root / "packaging" / "targets.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    return root


def test_write_and_check_block_absolute_path_escape(tmp_path, capsys):
    outside = tmp_path / "outside"
    outside.mkdir()
    target_file = outside / "pwned-abs.json"
    root = _escape_repo(tmp_path, str(target_file))

    rc_write = _run(root, "--write", "--only", "evil")
    out = capsys.readouterr().out
    assert rc_write == 1
    assert "경로 탈출 차단" in out
    assert not target_file.exists()  # 핵심: 레포 밖에 아무것도 안 쓰였다

    rc_check = _run(root, "--check", "--only", "evil")
    assert rc_check == 1
    assert not target_file.exists()


def test_write_and_check_block_dotdot_escape(tmp_path, capsys):
    outside = tmp_path / "outside"
    outside.mkdir()
    target_file = outside / "pwned-dotdot.json"
    # repo는 tmp_path/repo이므로 "../outside/..."면 repo 밖(tmp_path/outside)을 가리킨다.
    root = _escape_repo(tmp_path, "../outside/pwned-dotdot.json")

    rc_write = _run(root, "--write", "--only", "evil")
    out = capsys.readouterr().out
    assert rc_write == 1
    assert "경로 탈출 차단" in out
    assert not target_file.exists()

    rc_check = _run(root, "--check", "--only", "evil")
    assert rc_check == 1
    assert not target_file.exists()


def test_write_and_check_block_symlink_escape(tmp_path, capsys):
    outside = tmp_path / "outside"
    outside.mkdir()
    target_file = outside / "pwned-symlink.json"
    root = _escape_repo(tmp_path, "shared/pwned-symlink.json")
    # "shared"는 겉보기엔 평범한 상대경로 조각이지만, 실제로는 레포 밖을 가리키는
    # 심링크다 — 미리 심어둔 상태를 시뮬레이션(예: 악의적 fixture, 혹은 손상된 체크아웃).
    (root / "shared").symlink_to(outside)

    rc_write = _run(root, "--write", "--only", "evil")
    out = capsys.readouterr().out
    assert rc_write == 1
    assert "경로 탈출 차단" in out
    assert not target_file.exists()

    rc_check = _run(root, "--check", "--only", "evil")
    assert rc_check == 1
    assert not target_file.exists()


def test_resolve_in_repo_shared_adversarial_table(tmp_path):
    """`_resolve_in_repo`가 check_eval_coverage.py와 공유하는 적대적 케이스 표를
    통과하는지 검증한다 (D-15: 구현은 여러 벌, 계약만 하나 —
    scripts/tests/resolve_in_repo_contract.py 참고)."""
    from resolve_in_repo_contract import assert_resolve_in_repo_contract

    assert_resolve_in_repo_contract(_mod._resolve_in_repo, tmp_path)


def test_write_continues_after_one_target_fails_and_reports_both(tmp_path, capsys):
    """Medium 수정: 첫 아티팩트가 경로 탈출로 막혀도 두 번째(alpha)는 시도되고 기록된다."""
    root = tmp_path / "repo"
    claude_plugin = root / "plugins" / "common" / ".claude-plugin"
    claude_plugin.mkdir(parents=True)
    (claude_plugin / "plugin.json").write_text(json.dumps(SSOT), encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    policy = {
        "source": {
            "pluginRoot": "plugins/common",
            "manifest": "plugins/common/.claude-plugin/plugin.json",
            "_meta": {"componentDirs": ["skills", "agents", "rules", "hooks"]},
        },
        "targets": [
            {
                "id": "evil",
                "enabled": True,
                "manifestPath": str(outside / "pwned.json"),
                "requiredFields": ["name"],
            },
            {
                "id": "alpha",
                "enabled": True,
                "manifestPath": "plugins/common/.alpha-plugin/plugin.json",
                "requiredFields": ["name", "version"],
            },
        ],
        "gate": {"requireGeneratedManifestPresent": True},
    }
    policy_path = root / "packaging" / "targets.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    rc = _run(root, "--write")  # 기본 --write = enabled 전체
    out = capsys.readouterr().out
    assert rc == 1  # 실패가 하나라도 있으면 전체 exit 1
    assert "경로 탈출 차단" in out
    alpha_manifest = root / "plugins" / "common" / ".alpha-plugin" / "plugin.json"
    assert alpha_manifest.exists()  # evil이 막혀도 alpha는 계속 시도돼 기록됐다
    assert "기록: plugins/common/.alpha-plugin/plugin.json" in out


# ── 7. 훅 매니페스트 생성 (W9 / Codex) ───────────────────────────────────────
#
# Codex 는 exec form(command+args[])을 로드하지 않고, `${CLAUDE_PLUGIN_ROOT}` 를
# 치환한다 [confirmed: codex-cli 0.153.4 실측, 2026-09-10]. 그래서 훅 매니페스트를
# 타겟별로 **생성**한다 — 손으로 두 벌 유지하면 조용히 갈린다.

_HOOKS_SPEC = {
    "path": "plugins/common/hooks/hooks-delta.json",
    "manifestField": "./hooks/hooks-delta.json",
    "interpreter": "python3",
    "events": {
        "SessionStart": [{"script": "hooks/inject.py", "timeout": 10}],
        "PostToolUse": [{"script": "hooks/fmt.py", "timeout": 30}],
    },
}


def _hooks_repo(tmp_path: Path, *, with_scripts: bool = True) -> Path:
    """alpha 타겟에 훅 스펙을 붙인 픽스처 레포."""
    root = _fake_repo(tmp_path)
    policy = json.loads(
        (root / "packaging" / "targets.json").read_text(encoding="utf-8")
    )
    policy["targets"][0]["hooks"] = _HOOKS_SPEC
    (root / "packaging" / "targets.json").write_text(
        json.dumps(policy), encoding="utf-8"
    )
    hooks_dir = root / "plugins" / "common" / "hooks"
    hooks_dir.mkdir(parents=True)
    if with_scripts:
        (hooks_dir / "inject.py").write_text("", encoding="utf-8")
        (hooks_dir / "fmt.py").write_text("", encoding="utf-8")
    return root


def _set_session_hook(root: Path, script: str, interpreter: str) -> None:
    path = root / "packaging/targets.json"
    policy = json.loads(path.read_text())
    hooks = policy["targets"][0]["hooks"]
    hooks["interpreter"] = interpreter
    hooks["events"]["SessionStart"][0]["script"] = script
    path.write_text(json.dumps(policy))


def _run_generated_hook(root: Path) -> subprocess.CompletedProcess:
    assert _run(root, "--write", "--only", "alpha") == 0
    plugin = root / "plugins/common"
    manifest = json.loads((plugin / "hooks/hooks-delta.json").read_text())
    command = manifest["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    return subprocess.run(
        ["/bin/sh", "-c", command],
        cwd=root,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(plugin)},
        check=True,
    )


@pytest.mark.parametrize(
    "name",
    [
        "space name.py",
        "$(printf PROBE).py",
        "`printf PROBE`.py",
        'quote"name.py',
        "single'name.py",
        "back\\slash.py",
        "semi;name.py",
    ],
)
def test_generated_hook_preserves_literal_script_name(tmp_path, name):
    root = _hooks_repo(tmp_path / "plugin path with spaces")
    relative = "hooks/" + name
    script = root / "plugins/common" / relative
    script.write_text("import sys\nprint(sys.argv[0])\n")
    _set_session_hook(root, relative, sys.executable)
    result = _run_generated_hook(root)
    assert result.stdout.strip() == str(script)


def test_generated_hook_accepts_interpreter_path_with_spaces(tmp_path):
    root = _hooks_repo(tmp_path)
    interpreter = tmp_path / "python with spaces"
    interpreter.symlink_to(sys.executable)
    _set_session_hook(root, "hooks/inject.py", str(interpreter))
    assert _run_generated_hook(root).returncode == 0


@pytest.mark.parametrize(
    "interpreter",
    [
        "python3; printf PROBE",
        "$(printf python3)",
        "`printf python3`",
        "python3\n",
        None,
    ],
)
def test_interpreter_shell_commands_are_rejected(tmp_path, interpreter):
    root = _hooks_repo(tmp_path)
    _set_session_hook(root, "hooks/inject.py", interpreter)
    assert _run(root, "--write", "--only", "alpha") == 1
    assert _run(root, "--check", "--only", "alpha") == 1


def test_hooks_manifest_is_generated_in_string_form(tmp_path):
    root = _hooks_repo(tmp_path)
    assert _run(root, "--write", "--only", "alpha") == 0
    hooks = json.loads(
        (root / "plugins" / "common" / "hooks" / "hooks-delta.json").read_text(
            encoding="utf-8"
        )
    )
    entry = hooks["hooks"]["SessionStart"][0]["hooks"][0]
    # 문자열 하나여야 한다 — args[] 가 있으면 Codex 가 로드하지 않는다.
    assert "args" not in entry
    assert entry["command"] == 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/inject.py"'
    assert entry["timeout"] == 10
    # matcher 는 쓰지 않는다 (Codex 해석 여부 미측정).
    assert "matcher" not in hooks["hooks"]["SessionStart"][0]


def test_manifest_gains_hooks_field_when_hooks_dir_present(tmp_path):
    root = _hooks_repo(tmp_path)
    assert _run(root, "--write", "--only", "alpha") == 0
    manifest = json.loads(
        (root / "plugins" / "common" / ".alpha-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["hooks"] == "./hooks/hooks-delta.json"


def test_no_hooks_field_and_no_artifact_when_hooks_dir_absent(tmp_path):
    """훅 디렉토리가 없으면 필드도 산출물도 없다 — 컴포넌트는 실측으로 판정한다."""
    root = _fake_repo(tmp_path)
    policy = json.loads(
        (root / "packaging" / "targets.json").read_text(encoding="utf-8")
    )
    policy["targets"][0]["hooks"] = _HOOKS_SPEC
    (root / "packaging" / "targets.json").write_text(
        json.dumps(policy), encoding="utf-8"
    )
    assert _run(root, "--write", "--only", "alpha") == 0
    manifest = json.loads(
        (root / "plugins" / "common" / ".alpha-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    assert "hooks" not in manifest
    assert not (root / "plugins" / "common" / "hooks" / "hooks-delta.json").exists()


def test_declared_hook_script_missing_is_exit_1(tmp_path, capsys):
    """없는 스크립트를 가리키는 훅은 소비자 세션에서 매번 조용히 실패한다 — 여기서 막는다."""
    root = _hooks_repo(tmp_path, with_scripts=False)
    assert _run(root, "--write", "--only", "alpha") == 1
    err = capsys.readouterr().err + capsys.readouterr().out
    assert "hooks/inject.py" in err


def test_hook_script_path_escaping_plugin_root_is_exit_1(tmp_path):
    root = _hooks_repo(tmp_path)
    policy = json.loads(
        (root / "packaging" / "targets.json").read_text(encoding="utf-8")
    )
    policy["targets"][0]["hooks"]["events"]["SessionStart"][0]["script"] = (
        "../../../etc/passwd"
    )
    (root / "packaging" / "targets.json").write_text(
        json.dumps(policy), encoding="utf-8"
    )
    assert _run(root, "--write", "--only", "alpha") == 1


def test_check_detects_hooks_manifest_drift_and_deletion(tmp_path):
    root = _hooks_repo(tmp_path)
    assert _run(root, "--write", "--only", "alpha") == 0
    assert _run(root, "--check", "--only", "alpha") == 0
    generated = root / "plugins" / "common" / "hooks" / "hooks-delta.json"
    generated.write_text('{"hooks": {}}\n', encoding="utf-8")
    assert _run(root, "--check", "--only", "alpha") == 1
    assert _run(root, "--write", "--only", "alpha") == 0
    assert _run(root, "--check", "--only", "alpha") == 0
    generated.unlink()
    assert _run(root, "--check", "--only", "alpha") == 1


# ── 훅 인자 (W11) ────────────────────────────────────────────────────────────
#
# 하네스별 동작 차이는 **매니페스트가 인자로 전달**한다 — 런타임에 하네스를 추측하면
# 조용히 틀린다. 인자는 정책 파일에서 와서 셸 명령 문자열에 그대로 이어 붙으므로,
# 경로 봉쇄와 같은 계열의 검증을 건다(`docs/conventions/path-containment.md`).


def _hooks_repo_with_args(tmp_path: Path, args: list) -> Path:
    root = _fake_repo(tmp_path)
    policy = json.loads(
        (root / "packaging" / "targets.json").read_text(encoding="utf-8")
    )
    spec = json.loads(json.dumps(_HOOKS_SPEC))
    spec["events"]["SessionStart"][0]["args"] = args
    policy["targets"][0]["hooks"] = spec
    (root / "packaging" / "targets.json").write_text(
        json.dumps(policy), encoding="utf-8"
    )
    hooks_dir = root / "plugins" / "common" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "inject.py").write_text("", encoding="utf-8")
    (hooks_dir / "fmt.py").write_text("", encoding="utf-8")
    return root


def test_hook_args_are_appended_to_the_command_string(tmp_path):
    root = _hooks_repo_with_args(tmp_path, ["--portable-only"])
    assert _run(root, "--write", "--only", "alpha") == 0
    hooks = json.loads(
        (root / "plugins" / "common" / "hooks" / "hooks-delta.json").read_text(
            encoding="utf-8"
        )
    )
    entry = hooks["hooks"]["SessionStart"][0]["hooks"][0]
    # 여전히 문자열 하나다 — exec form 은 Codex 가 로드하지 않는다.
    assert "args" not in entry
    assert entry["command"] == (
        'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/inject.py" --portable-only'
    )
    # 인자가 없는 훅은 그대로다.
    other = hooks["hooks"]["PostToolUse"][0]["hooks"][0]
    assert other["command"] == 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/fmt.py"'


def test_no_args_key_leaves_command_unchanged(tmp_path):
    root = _hooks_repo(tmp_path)
    assert _run(root, "--write", "--only", "alpha") == 0
    hooks = json.loads(
        (root / "plugins" / "common" / "hooks" / "hooks-delta.json").read_text(
            encoding="utf-8"
        )
    )
    entry = hooks["hooks"]["SessionStart"][0]["hooks"][0]
    assert entry["command"] == 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/inject.py"'


def test_hook_arg_with_shell_metacharacters_is_exit_1(tmp_path):
    """인용을 깨거나 명령을 이어붙일 수 있는 값은 생성 단계에서 막는다."""
    for bad in ('--x"; rm -rf /', "--x $(id)", "--x;y", "--x`id`", "--x|y", "--x&y"):
        root = _hooks_repo_with_args(tmp_path / bad.replace("/", "_"), [bad])
        assert _run(root, "--write", "--only", "alpha") == 1, bad


def test_hook_arg_must_be_a_flag(tmp_path):
    """플래그 형태만 허용한다 — 자유 문자열은 검증 표면을 넓힌다."""
    for bad in ("portable-only", "-p", "--", "-", ""):
        root = _hooks_repo_with_args(tmp_path / f"x{abs(hash(bad))}", [bad])
        assert _run(root, "--write", "--only", "alpha") == 1, bad


# ── 훅 출력 한도 (W13) ───────────────────────────────────────────────────────
#
# Codex 는 훅 출력을 기본 2,500 토큰에서 잘라 머리·꼬리만 모델에 준다. 핸들러 필드
# `additionalContextLimit` 이 그 한도이고 `0` 이면 자르지 않는다 — 정책 값을 생성물로
# **그대로** 옮겨야 한다. `0` 은 falsy 라 `if entry.get(...)` 식 전달이면 조용히
# 사라진다(바로 위 `timeout` 이 그 형태다). 그래서 0 을 명시적으로 검사한다.


def _hooks_repo_with_limit(tmp_path: Path, limit: object) -> Path:
    root = _hooks_repo(tmp_path)
    policy_path = root / "packaging" / "targets.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["targets"][0]["hooks"]["events"]["SessionStart"][0][
        "additionalContextLimit"
    ] = limit
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    return root


def _generated_hooks(root: Path) -> dict:
    return json.loads(
        (root / "plugins" / "common" / "hooks" / "hooks-delta.json").read_text(
            encoding="utf-8"
        )
    )["hooks"]


def test_context_limit_is_passed_through_including_zero(tmp_path):
    for limit in (0, 8000):
        root = _hooks_repo_with_limit(tmp_path / f"l{limit}", limit)
        assert _run(root, "--write", "--only", "alpha") == 0
        hooks = _generated_hooks(root)
        assert hooks["SessionStart"][0]["hooks"][0]["additionalContextLimit"] == limit
        # 필드를 준 엔트리만 — 다른 이벤트로 번지지 않는다.
        assert "additionalContextLimit" not in hooks["PostToolUse"][0]["hooks"][0]


def test_context_limit_absent_emits_no_key(tmp_path):
    """없으면 **키 부재** — 기본값을 지어내 싣지 않는다(상류 기본값의 소유자는 Codex)."""
    root = _hooks_repo(tmp_path)
    assert _run(root, "--write", "--only", "alpha") == 0
    entry = _generated_hooks(root)["SessionStart"][0]["hooks"][0]
    assert "additionalContextLimit" not in entry


def test_context_limit_invalid_is_exit_1(tmp_path, capsys):
    """음수·bool·문자열은 생성 단계에서 막는다 — `True` 는 `int` 의 하위 타입이라 따로 거른다."""
    for i, bad in enumerate((-1, True, "0")):
        root = _hooks_repo_with_limit(tmp_path / f"b{i}", bad)
        assert _run(root, "--write", "--only", "alpha") == 1, bad
        err = capsys.readouterr().err
        assert "additionalContextLimit" in err and "'alpha'" in err, err
        assert "SessionStart" in err and repr(bad) in err, err
        assert not (root / "plugins" / "common" / "hooks" / "hooks-delta.json").exists()


# ── 스킬별 Codex 메타데이터 (agents/openai.yaml, 5.4.0 · C-X1) ────────────────────

_SKILL_IFACE = {
    "path": "agents/openai.yaml",
    "interfaceFrom": {"display_name": "name", "short_description": "description"},
    "firstSentence": ["short_description"],
    "implicitInvocationOffWhen": "disable-model-invocation",
}


def _skill_repo(tmp_path: Path, skills: dict) -> Path:
    """alpha 타겟에 skillInterface 를 붙이고 `skills` = {이름: frontmatter 본문} 을 만든다."""
    root = _fake_repo(tmp_path)
    path = root / "packaging" / "targets.json"
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["targets"][0]["skillInterface"] = _SKILL_IFACE
    path.write_text(json.dumps(policy), encoding="utf-8")
    for name, fm in skills.items():
        d = root / "plugins" / "common" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\n{fm}\n---\n\n# {name}\n", encoding="utf-8")
    return root


def _iface(root: Path, name: str) -> str:
    return (
        root / "plugins" / "common" / "skills" / name / "agents" / "openai.yaml"
    ).read_text(encoding="utf-8")


_TWO_SKILLS = {
    "plain": "name: plain\ndescription: Do the plain thing. Use when plain.",
    "manual": (
        "name: manual\ndescription: Manual only skill. Use when asked.\n"
        "disable-model-invocation: true"
    ),
}


def test_skill_interface_policy_only_when_model_invocation_disabled(tmp_path):
    root = _skill_repo(tmp_path, _TWO_SKILLS)
    assert _run(root, "--write") == 0
    plain = _iface(root, "plain")
    assert 'display_name: "plain"' in plain
    assert 'short_description: "Do the plain thing."' in plain  # 첫 문장만
    # 키가 없는 스킬에는 기본값조차 적지 않는다 — SSOT 에 없는 결정이 생긴다.
    assert "allow_implicit_invocation" not in plain
    assert "policy:" not in plain
    manual = _iface(root, "manual")
    assert "policy:\n  allow_implicit_invocation: false\n" in manual
    assert _run(root, "--check") == 0


def test_skill_interface_deletion_and_edit_are_drift(tmp_path):
    """되돌려-FAIL: 생성물을 지우거나 고치면 --check 가 red 다."""
    root = _skill_repo(tmp_path, _TWO_SKILLS)
    assert _run(root, "--write") == 0
    target = root / "plugins/common/skills/manual/agents/openai.yaml"
    original = target.read_text(encoding="utf-8")
    target.unlink()
    assert _run(root, "--check") == 1
    target.write_text(original.replace("false", "true"), encoding="utf-8")
    assert _run(root, "--check") == 1
    target.write_text(original, encoding="utf-8")
    assert _run(root, "--check") == 0


def test_skill_interface_follows_frontmatter_change(tmp_path):
    root = _skill_repo(tmp_path, _TWO_SKILLS)
    assert _run(root, "--write") == 0
    md = root / "plugins/common/skills/plain/SKILL.md"
    md.write_text(
        md.read_text(encoding="utf-8").replace(
            "Use when plain.", "Use when plain.\ndisable-model-invocation: true"
        ),
        encoding="utf-8",
    )
    assert _run(root, "--check") == 1  # SSOT 가 바뀌었는데 생성물은 그대로 → 드리프트


@pytest.mark.parametrize(
    "fm",
    [
        "name: bad\ndescription: |\n  multi line",  # 블록 스칼라 — 추측하지 않는다
        "name: bad\ndescription:",  # 빈 값
        "name: bad",  # description 없음 → short_description 비어 제출 검사 실패
    ],
)
def test_skill_interface_unreadable_frontmatter_is_exit_1(tmp_path, capsys, fm):
    root = _skill_repo(tmp_path, {"bad": fm})
    assert _run(root, "--write") == 1
    assert not (root / "plugins/common/skills/bad/agents/openai.yaml").exists()


def test_skill_interface_yaml_quotes_special_characters(tmp_path):
    root = _skill_repo(
        tmp_path,
        {"q": 'name: q\ndescription: Say "hi": a #tag — done. Next.'},
    )
    assert _run(root, "--write") == 0
    assert 'short_description: "Say \\"hi\\": a #tag — done."' in _iface(root, "q")


def test_real_repo_skill_interfaces_match_frontmatter():
    """실제 레포: 모든 스킬에 생성물이 있고, `disable-model-invocation: true` 인 스킬만
    `allow_implicit_invocation` 키를 갖는다(읽기 전용 — 실제 트리를 쓰지 않는다)."""
    skills = SCRIPTS_DIR.parent / "plugins" / "common" / "skills"
    assert skills.is_dir()
    seen = 0
    for md in sorted(skills.glob("*/SKILL.md")):
        fm = _mod.read_skill_frontmatter(md)
        text = (md.parent / "agents" / "openai.yaml").read_text(encoding="utf-8")
        off = fm.get("disable-model-invocation", "").lower() == "true"
        assert ("allow_implicit_invocation: false" in text) is off, md.parent.name
        assert ("allow_implicit_invocation" in text) is off, md.parent.name
        seen += 1
    assert seen > 0


# ── edition 배포 타겟(Hermes 판) ─────────────────────────────────────────────
# `delivery: "edition"` 타겟은 main 에 파일을 만들지 않는다. build-targets 는 매니페스트를
# 계산만 해 Agent Plugins v1 정적 제약을 판정한다(enabled 와 무관). 판 트리는 판 빌더가 만든다.
# 판정 상수는 테스트에도 따로 적는다 — 정책·코드와 독립된 오라클이어야 정책 파손을 잡는다.
# 원문: scripts/tests/fixtures/hermes_agent_plugins_352b249.txt (아래 발췌 대조 테스트).

AP_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
FIXTURES = SCRIPTS_DIR / "tests" / "fixtures"
_DROP = object()

EDITION = {
    "id": "epsilon",
    "enabled": False,
    "delivery": "edition",
    "editionBuilder": "scripts/build-epsilon-branch.py",
    "schemaUrl": AP_URL,
    "requiredFields": ["name", "version", "description"],
    "passthroughFields": ["author", "homepage", "repository", "license", "keywords"],
}


def _edit_policy(root: Path, fn) -> None:
    path = root / "packaging" / "targets.json"
    policy = json.loads(path.read_text())
    fn(policy)
    path.write_text(json.dumps(policy))


def _apply(base: dict, overrides: dict) -> dict:
    out = dict(base)
    for key, value in overrides.items():
        if value is _DROP:
            out.pop(key, None)
        else:
            out[key] = value
    return out


def _edition_repo(
    tmp_path: Path, *, ssot: dict | None = None, **overrides: object
) -> Path:
    """기본 픽스처 + edition 타겟 하나. main 생성물(alpha·gamma)은 edition 을 넣기 **전에**
    만들어 둔다 — edition 판정이 실패하면 --write 도 막히므로(정책 결함), 실패 원인을 좁힌다."""
    root = _fake_repo(tmp_path)
    if ssot is not None:
        (root / "plugins/common/.claude-plugin/plugin.json").write_text(
            json.dumps(ssot), encoding="utf-8"
        )
    assert _run(root, "--write") == 0
    _edit_policy(root, lambda p: p["targets"].append(_apply(EDITION, overrides)))
    return root


def _files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def _snapshot(root: Path) -> dict[str, bytes]:
    return {f: (root / f).read_bytes() for f in _files(root)}


def _bad_ssot(**changes: object) -> dict:
    return {**SSOT, **changes}


def test_edition_target_creates_nothing_and_check_passes(tmp_path, capsys):
    plain = _fake_repo(tmp_path / "plain")
    assert _run(plain, "--write") == 0
    expected = _files(plain)

    root = _edition_repo(tmp_path)
    assert _run(root, "--write") == 0
    # 같은 정책 + edition 타겟 하나 — --write 결과 파일 집합이 늘지 않는다
    assert _files(root) == expected
    generated = _files(root) - {"packaging/targets.json"}
    assert not any(AP_URL in (root / f).read_text() for f in generated)
    capsys.readouterr()
    assert _run(root, "--check") == 0
    out = capsys.readouterr().out
    assert "✓ edition 'epsilon' — AP v1 매니페스트 계산 판정 통과" in out


@pytest.mark.parametrize("enabled", [False, True])
def test_edition_verdict_runs_regardless_of_enabled(tmp_path, capsys, enabled):
    root = _edition_repo(tmp_path, enabled=enabled, schemaUrl=AP_URL + "x")
    capsys.readouterr()
    assert _run(root, "--check") == 1
    assert "✗ edition 'epsilon' AP v1 판정 실패 — $schema 가 AP v1 URL 과 다르다" in (
        capsys.readouterr().out
    )


_VERDICT_CASES = [
    # (라벨, SSOT, edition 덮어쓰기, 발화해야 하는 판정 문구)
    (
        "schema-other-version",
        None,
        {"schemaUrl": AP_URL.replace("1.0.0", "1.0.1")},
        "$schema 가 AP v1 URL 과 다르다",
    ),
    (
        "schema-missing",
        None,
        {"schemaUrl": _DROP},
        "$schema 가 AP v1 URL 과 다르다 — None",
    ),
    (
        "disallowed-top-level",
        _bad_ssot(icon="./icon.png"),
        {"passthroughFields": [*EDITION["passthroughFields"], "icon"]},
        "허용하지 않는 최상위 필드 — ['icon']",
    ),
    (
        "component-field",
        None,
        {"componentFields": {"skills": "./skills/"}},
        "허용하지 않는 최상위 필드 — ['skills']",
    ),
    ("name-uppercase", _bad_ssot(name="Fixture-Kit"), {}, "name 이 AP v1 규칙"),
    ("name-double-dash", _bad_ssot(name="fixture--kit"), {}, "name 이 AP v1 규칙"),
    ("name-double-dot", _bad_ssot(name="fixture..kit"), {}, "name 이 AP v1 규칙"),
    ("name-leading-dash", _bad_ssot(name="-kit"), {}, "name 이 AP v1 규칙"),
    ("name-trailing-dot", _bad_ssot(name="kit."), {}, "name 이 AP v1 규칙"),
    ("name-trailing-newline", _bad_ssot(name="kit\n"), {}, "name 이 AP v1 규칙"),
    ("name-65-chars", _bad_ssot(name="a" * 65), {}, "name 이 AP v1 규칙"),
    ("name-empty", _bad_ssot(name=""), {}, "name 이 AP v1 규칙"),
    ("name-not-string", _bad_ssot(name=7), {}, "name 이 AP v1 규칙"),
    (
        "version-not-string",
        _bad_ssot(version=1),
        {},
        "version 는 문자열이어야 한다 — int",
    ),
    (
        "description-not-string",
        _bad_ssot(description=["d"]),
        {},
        "description 는 문자열이어야 한다 — list",
    ),
    (
        "homepage-not-string",
        _bad_ssot(homepage={"u": "x"}),
        {},
        "homepage 는 문자열이어야 한다 — dict",
    ),
    (
        "repository-not-string",
        _bad_ssot(repository={"url": "x"}),
        {},
        "repository 는 문자열이어야 한다 — dict",
    ),
    (
        "license-not-string",
        _bad_ssot(license=None),
        {},
        "license 는 문자열이어야 한다 — NoneType",
    ),
    (
        "keywords-string",
        _bad_ssot(keywords="a,b"),
        {},
        "keywords 는 문자열 배열이어야 한다",
    ),
    (
        "keywords-non-str-item",
        _bad_ssot(keywords=["a", 1]),
        {},
        "keywords 는 문자열 배열이어야 한다",
    ),
    (
        "author-extra-key",
        _bad_ssot(author={"name": "x", "twitter": "y"}),
        {},
        "위반 키 ['twitter']",
    ),
    ("author-non-string", _bad_ssot(author={"name": 1}), {}, "위반 키 ['name']"),
    (
        "author-string",
        _bad_ssot(author="Fixture Org"),
        {},
        "author 는 객체여야 한다 — str",
    ),
]


@pytest.mark.parametrize(("label", "ssot", "overrides", "expect"), _VERDICT_CASES)
def test_edition_ap_v1_verdict_failures(
    tmp_path, capsys, label, ssot, overrides, expect
):
    root = _edition_repo(tmp_path, ssot=ssot, **overrides)
    before = _snapshot(root)
    capsys.readouterr()
    assert _run(root, "--check") == 1, label
    captured = capsys.readouterr()
    assert "✗ edition 'epsilon' AP v1 판정 실패" in captured.out, label
    assert expect in captured.out, (label, captured.out)
    assert "Traceback" not in captured.err
    # --check --only <main 타겟> 도 edition 판정을 돈다 (ATK-003)
    assert _run(root, "--check", "--only", "alpha") == 1, label
    assert expect in capsys.readouterr().out, label
    # --write 는 정책 결함이면 아무것도 쓰지 않는다
    assert _run(root, "--write") == 1, label
    assert "아무것도 기록하지 않았다" in capsys.readouterr().out, label
    assert _snapshot(root) == before, label


@pytest.mark.parametrize("name", ["a", "a" * 64, "fixture-kit", "kit.v2", "0x"])
def test_edition_ap_v1_name_boundaries_pass(tmp_path, name):
    root = _edition_repo(tmp_path, ssot=_bad_ssot(name=name))
    assert _run(root, "--check") == 0


def test_edition_author_with_all_string_fields_passes(tmp_path):
    author = {"name": "x", "email": "x@example.com", "url": "https://example.com"}
    full = _bad_ssot(
        author=author,
        homepage="https://example.com",
        repository="https://example.com/r",
        license="MIT",
        keywords=["a", "b"],
    )
    root = _edition_repo(tmp_path, ssot=full)
    assert _run(root, "--check") == 0


def test_ap_v1_violations_function_direct():
    good = {"$schema": AP_URL, "name": "kit", "version": "1", "description": "d"}
    v = _mod.ap_v1_violations
    assert v(good) == []
    assert v({**good, "extensions": {"com.example": {}}}) == []
    assert v({**good, "keywords": []}) == []
    assert any("최상위 필드 — ['hooks']" in x for x in v({**good, "hooks": "./h.json"}))
    assert any(
        "$schema" in x for x in v({k: x for k, x in good.items() if k != "$schema"})
    )
    assert any("extensions 는 객체여야" in x for x in v({**good, "extensions": []}))
    assert any(
        "네임스페이스 값은 객체" in x
        for x in v({**good, "extensions": {"com.example": 1}})
    )


# ── AP v1 상수 ↔ Hermes 원문 발췌 대조 (ATK-002) ─────────────────────────────

UPSTREAM_SHA = "352b249f67fb6a4a7d7904acaca9dd410db229e0"


def _excerpt(name: str) -> tuple[dict[str, str], list[list[tuple[int, str]]]]:
    """fixture 를 (헤더, 연속 줄 묶음들) 로 읽는다. 줄 번호 연속성은 여기서 단언한다."""
    header: dict[str, str] = {}
    chunks: list[list[tuple[int, str]]] = [[]]
    for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines():
        if line.startswith("#") and not chunks[0]:
            key, sep, value = line[1:].partition(":")
            if sep and key.strip() and " " not in key.strip():
                header.setdefault(key.strip(), value.strip())
        elif line == "...":
            chunks.append([])
        else:
            number, sep, text = line.partition("|")
            assert sep, line
            chunks[-1].append((int(number), text))
    for chunk in chunks:
        numbers = [n for n, _ in chunk]
        assert numbers == list(range(numbers[0], numbers[0] + len(numbers))), name
    ranges = ", ".join(f"{c[0][0]}-{c[-1][0]}" for c in chunks)
    assert header["lines"] == ranges, (header["lines"], ranges)
    assert header["commit"] == UPSTREAM_SHA
    return header, chunks


def _upstream_ast(chunks: list[list[tuple[int, str]]]):
    import ast

    return [ast.parse("\n".join(text for _, text in chunk)) for chunk in chunks]


def test_ap_v1_constants_match_upstream_excerpt():
    import ast

    header, chunks = _excerpt("hermes_agent_plugins_352b249.txt")
    assert header["file"] == "hermes_cli/agent_plugins.py"
    assigned: dict[str, ast.expr] = {}
    validate = None
    for tree in _upstream_ast(chunks):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                assigned[node.targets[0].id] = node.value
            if isinstance(node, ast.FunctionDef) and node.name == "_validate_manifest":
                validate = node
    assert ast.literal_eval(assigned["PLUGIN_SCHEMA_V1"]) == _mod.AP_V1_SCHEMA_URL
    assert ast.literal_eval(assigned["_PLUGIN_FIELDS"]) == set(_mod.AP_V1_TOP_LEVEL)
    assert ast.literal_eval(assigned["_AUTHOR_FIELDS"]) == set(_mod.AP_V1_AUTHOR_FIELDS)
    regex_call = assigned["_PLUGIN_NAME_RE"]
    assert isinstance(regex_call, ast.Call)
    assert ast.literal_eval(regex_call.args[0]) == _mod.AP_V1_NAME_RE.pattern
    assert validate is not None

    # name 길이: `1 <= len(name) <= 64`
    bounds = [
        (ast.literal_eval(n.left), ast.literal_eval(n.comparators[-1]))
        for n in ast.walk(validate)
        if isinstance(n, ast.Compare)
        and isinstance(n.comparators[0], ast.Call)
        and ast.unparse(n.comparators[0]) == "len(name)"
    ]
    assert bounds == [(_mod.AP_V1_NAME_MIN, _mod.AP_V1_NAME_MAX)]
    # 문자열 필드: `for field in (...): ... isinstance(manifest[field], str)`
    loops = [
        ast.literal_eval(n.iter)
        for n in ast.walk(validate)
        if isinstance(n, ast.For)
        and ast.unparse(n.target) == "field"
        and isinstance(n.iter, ast.Tuple)
    ]
    assert loops == [tuple(_mod.AP_V1_STRING_FIELDS)]
    source = ast.unparse(validate)
    # keywords·author·extensions 타입 검사가 원문에 있다 — 판정이 이것을 흡수했다
    assert "isinstance(keywords, list)" in source
    assert "_all_str(keywords)" in source
    assert "isinstance(author, dict)" in source
    assert "set(author) - _AUTHOR_FIELDS or not _all_str(author.values())" in source
    assert (
        "any((not isinstance(value, dict) for value in extensions.values()))" in source
    )


def test_native_manifest_names_match_upstream_excerpt():
    import re as _re

    header, chunks = _excerpt("hermes_plugins_discovery_352b249.txt")
    assert header["file"] == "hermes_cli/plugins_discovery.py"
    text = {n: t for chunk in chunks for n, t in chunk}
    native_line = next(t for t in text.values() if "manifest_file = next(" in t)
    assert tuple(_re.findall(r'child / "([^"]+)"', native_line)) == (
        _mod.HERMES_NATIVE_MANIFESTS
    )
    portable_line = next(t for t in text.values() if "portable_file = " in t)
    assert _re.findall(r'child / "([^"]+)"', portable_line) == [
        _mod.AP_V1_MANIFEST_NAME
    ]


@pytest.mark.parametrize(
    "name",
    ["hermes_agent_plugins_352b249.txt", "hermes_plugins_discovery_352b249.txt"],
)
def test_upstream_excerpt_matches_clone_when_available(name):
    """ATK-R04 (선택): 오프라인에서는 발췌가 원문과 같은지 **탐지할 수 없다**. hermes-agent 클론이
    있으면(`HERMES_AGENT_CLONE`) blob sha 와 줄 내용을 원문과 대조한다. 이 테스트만 skip 할 수 있다."""
    clone = os.environ.get("HERMES_AGENT_CLONE")
    if not clone or not (Path(clone) / ".git").exists():
        pytest.skip(
            "HERMES_AGENT_CLONE 미설정 또는 git 클론 아님 — 원문 대조는 클론이 있어야만 가능하다 "
            "(fixture 헤더의 recheck 절차)"
        )
    header, chunks = _excerpt(name)
    spec = f"{header['commit']}:{header['file']}"

    def git(*args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", clone, *args], capture_output=True, text=True, check=False
        )
        assert proc.returncode == 0, proc.stderr
        return proc.stdout

    assert git("rev-parse", spec).strip() == header["blob"]
    upstream = git("show", spec).split("\n")
    for chunk in chunks:
        for number, text in chunk:
            assert upstream[number - 1] == text, (name, number)


# ── 타겟 id 구조 검증 (ATK-001) ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "mode",
    [
        ("--check",),
        ("--write",),
        ("--check", "--only", "gamma"),
        ("--write", "--only", "alpha"),
    ],
)
def test_duplicate_target_id_is_exit_1(tmp_path, capsys, mode):
    """codex 블록을 복사하며 id 를 그대로 둔 경우 — 앞 타겟 생성물이 사라지는 false green."""
    root = _fake_repo(tmp_path)
    assert _run(root, "--write") == 0
    dup = {
        "id": "gamma",
        "enabled": True,
        "manifestPath": "plugins/common/gamma-copy.json",
        "requiredFields": ["name"],
    }
    _edit_policy(root, lambda p: p["targets"].append(dup))
    # 원래 gamma 생성물을 지워도 통과하면 false green 이다
    (root / "plugins/common/gamma-plugin.json").unlink()
    before = _snapshot(root)
    capsys.readouterr()
    assert _run(root, *mode) == 1
    assert "id 'gamma' 중복 — targets[2] 와 같다" in capsys.readouterr().err
    assert _snapshot(root) == before


@pytest.mark.parametrize(
    "mode",
    [
        ("--check",),
        ("--write",),
        ("--check", "--only", "gamma"),
        ("--check", "--only", "alpha"),
    ],
)
def test_edition_and_main_target_sharing_an_id_is_exit_1(tmp_path, capsys, mode):
    root = _edition_repo(tmp_path, id="gamma")
    before = _snapshot(root)
    capsys.readouterr()
    assert _run(root, *mode) == 1
    assert "targets[3]: id 'gamma' 중복 — targets[2] 와 같다" in capsys.readouterr().err
    assert _snapshot(root) == before


@pytest.mark.parametrize("bad", [_DROP, "", "   ", 7, None, ["alpha"]])
@pytest.mark.parametrize("mode", ["--check", "--write"])
def test_target_id_must_be_nonempty_string(tmp_path, capsys, bad, mode):
    root = _fake_repo(tmp_path)
    _edit_policy(
        root,
        lambda p: p["targets"].__setitem__(1, _apply(p["targets"][1], {"id": bad})),
    )
    assert _run(root, mode) == 1
    err = capsys.readouterr().err
    assert "targets[1]: id 는 비어 있지 않은 문자열이어야 한다" in err
    assert not (root / "plugins/common/.alpha-plugin").exists()


@pytest.mark.parametrize(
    ("targets", "expect"),
    [
        ({"id": "x"}, "targets: 타겟 객체의 목록이 필요하다"),
        (["x"], "targets[0]: 타겟 객체가 필요하다"),
    ],
)
def test_targets_structure_must_be_list_of_objects(tmp_path, capsys, targets, expect):
    root = _fake_repo(tmp_path)
    _edit_policy(root, lambda p: p.__setitem__("targets", targets))
    assert _run(root, "--check") == 1
    assert expect in capsys.readouterr().err


# ── manifestPath·중첩 키 무조건 인덱싱(KeyError) 회귀 (ATK-008) ─────────────


@pytest.mark.parametrize("mode", ["--check", "--write"])
def test_enabled_main_target_without_manifest_path_is_clean_exit_1(
    tmp_path, capsys, mode
):
    root = _fake_repo(tmp_path)
    _edit_policy(root, lambda p: p["targets"][2].pop("manifestPath"))
    assert _run(root, mode) == 1
    err = capsys.readouterr().err
    assert "타겟 'gamma': manifestPath 가 없다" in err


def _drop_hooks_key(key):
    def fn(p):
        p["targets"][0]["hooks"] = {
            k: v for k, v in p["targets"][0]["hooks"].items() if k != key
        }

    return fn


@pytest.mark.parametrize(
    ("label", "repo", "edit", "expect"),
    [
        (
            "marketplace.path",
            "plain",
            lambda p: p["targets"][0].__setitem__("marketplace", {"_meta": "no path"}),
            "타겟 'alpha' marketplace: 필수 키 'path'",
        ),
        (
            "hooks.path",
            "hooks",
            _drop_hooks_key("path"),
            "타겟 'alpha' hooks: 필수 키 'path'",
        ),
        (
            "hooks.manifestField",
            "hooks",
            _drop_hooks_key("manifestField"),
            "타겟 'alpha' hooks: 필수 키 'manifestField'",
        ),
        (
            "hooks.events",
            "hooks",
            _drop_hooks_key("events"),
            "타겟 'alpha' hooks: 필수 키 'events'",
        ),
        (
            "hooks.events[].script",
            "hooks",
            lambda p: p["targets"][0]["hooks"].__setitem__(
                "events", {"SessionStart": [{"timeout": 10}]}
            ),
            "hooks.events.SessionStart[]: 필수 키 'script'",
        ),
        (
            "skillInterface.path",
            "skills",
            lambda p: p["targets"][0]["skillInterface"].pop("path"),
            "타겟 'alpha' skillInterface: 필수 키 'path'",
        ),
        (
            "skillInterface.interfaceFrom",
            "skills",
            lambda p: p["targets"][0]["skillInterface"].pop("interfaceFrom"),
            "skillInterface: 필수 키 'interfaceFrom'",
        ),
        (
            "source._meta.componentDirs",
            "plain",
            lambda p: p["source"]["_meta"].pop("componentDirs"),
            "source._meta: 필수 키 'componentDirs'",
        ),
    ],
)
@pytest.mark.parametrize("mode", ["--check", "--write"])
def test_missing_nested_policy_key_is_clean_exit_1(
    tmp_path, capsys, label, repo, edit, expect, mode
):
    if repo == "hooks":
        root = _hooks_repo(tmp_path)
    elif repo == "skills":
        root = _skill_repo(tmp_path, {"plain": _TWO_SKILLS["plain"]})
    else:
        root = _fake_repo(tmp_path)
    _edit_policy(root, edit)
    before = _snapshot(root)
    assert _run(root, mode) == 1, label
    assert expect in capsys.readouterr().err, label
    assert _snapshot(root) == before, label


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("manifestPath", "plugins/common/epsilon.json"),
        ("marketplace", {"path": ".agents/plugins/e.json"}),
        ("marketplace", None),
        ("skillInterface", {"path": "agents/openai.yaml", "interfaceFrom": {}}),
        ("hooks", {}),
        ("editionBuilder", _DROP),
        ("delivery", "carrier-pigeon"),
    ],
)
def test_edition_policy_contradictions_are_exit_1(tmp_path, capsys, key, value):
    root = _edition_repo(tmp_path, **{key: value})
    before = _snapshot(root)
    capsys.readouterr()
    for mode in ("--check", "--write"):
        assert _run(root, mode) == 1, mode
        err = capsys.readouterr().err
        assert key in err and "epsilon" in err, (mode, err)
    assert _snapshot(root) == before


# ── 출력 경로 충돌(정규화 경로) ──────────────────────────────────────────────

ALPHA_MANIFEST = "plugins/common/.alpha-plugin/plugin.json"


def _collide(tmp_path: Path, gamma_path: str, *, symlink: bool = False) -> Path:
    root = _fake_repo(tmp_path)
    if symlink:
        (root / "plugins/common/.alpha-plugin").mkdir()
        (root / "plugins/common/alias").symlink_to(
            ".alpha-plugin", target_is_directory=True
        )
    _edit_policy(
        root, lambda p: p["targets"][2].__setitem__("manifestPath", gamma_path)
    )
    return root


def _assert_collision_blocks(root: Path, capsys, expect: str, *extra: str) -> None:
    before = _snapshot(root)
    assert _run(root, "--write", *extra) == 1
    out = capsys.readouterr().out
    assert "✗ 출력 경로 충돌" in out and expect in out, out
    assert _snapshot(root) == before  # 생성 전에 멈췄다
    assert _run(root, "--check", *extra) == 1
    out = capsys.readouterr().out
    assert "✗ 출력 경로 충돌" in out and expect in out, out


@pytest.mark.parametrize(
    ("label", "gamma_path", "symlink"),
    [
        ("identical", ALPHA_MANIFEST, False),
        ("dot-slash", "./" + ALPHA_MANIFEST, False),
        ("dot-segment", "plugins/./common/.alpha-plugin/plugin.json", False),
        ("parent-segment", "plugins/common/skills/../.alpha-plugin/plugin.json", False),
        ("symlink-alias", "plugins/common/alias/plugin.json", True),
        ("ancestor-dir", "plugins/common/.alpha-plugin", False),
        ("marketplace", ".agents/plugins/marketplace.json", False),
    ],
)
@pytest.mark.parametrize("only", [None, "gamma"])
def test_output_path_collision_is_exit_1_before_writing(
    tmp_path, capsys, label, gamma_path, symlink, only
):
    root = _collide(tmp_path, gamma_path, symlink=symlink)
    extra = ("--only", only) if only else ()
    _assert_collision_blocks(root, capsys, f"gamma:{gamma_path}", *extra)


@pytest.mark.parametrize(
    "gamma_path", ["./plugins/common/gamma-plugin.json", "plugins/common/alias/g.json"]
)
def test_normalized_distinct_paths_do_not_collide(tmp_path, gamma_path):
    root = _collide(tmp_path, gamma_path, symlink=True)
    assert _run(root, "--write") == 0
    assert _run(root, "--check") == 0


def test_collision_within_one_target_marketplace(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    _edit_policy(
        root,
        lambda p: p["targets"][0]["marketplace"].__setitem__("path", ALPHA_MANIFEST),
    )
    _assert_collision_blocks(
        root, capsys, f"alpha:{ALPHA_MANIFEST} ↔ alpha:{ALPHA_MANIFEST}"
    )


def test_collision_within_one_target_hooks(tmp_path, capsys):
    root = _hooks_repo(tmp_path)
    _edit_policy(
        root, lambda p: p["targets"][0]["hooks"].__setitem__("path", ALPHA_MANIFEST)
    )
    _assert_collision_blocks(
        root, capsys, f"alpha:{ALPHA_MANIFEST} ↔ alpha:{ALPHA_MANIFEST}"
    )


@pytest.mark.parametrize(
    ("label", "repo", "gamma_path", "expect"),
    [
        (
            "ssot",
            "plain",
            "plugins/common/.claude-plugin/plugin.json",
            "입력 source.manifest(SSOT)",
        ),
        (
            "ssot-dir",
            "plain",
            "plugins/common/.claude-plugin",
            "입력 source.manifest(SSOT)",
        ),
        ("policy", "plain", "packaging/targets.json", "입력 정책 파일"),
        ("skill", "skills", "plugins/common/skills/plain/SKILL.md", "입력 스킬 원본"),
        ("skill-dir", "skills", "plugins/common/skills/plain", "입력 스킬 원본"),
        ("hook-script", "hooks", "plugins/common/hooks/inject.py", "입력 훅 스크립트"),
    ],
)
@pytest.mark.parametrize("only", [None, "gamma"])
def test_output_must_not_overlap_read_only_inputs(
    tmp_path, capsys, label, repo, gamma_path, expect, only
):
    if repo == "hooks":
        root = _hooks_repo(tmp_path)
    elif repo == "skills":
        root = _skill_repo(tmp_path, {"plain": _TWO_SKILLS["plain"]})
    else:
        root = _fake_repo(tmp_path)
    _edit_policy(
        root, lambda p: p["targets"][2].__setitem__("manifestPath", gamma_path)
    )
    extra = ("--only", only) if only else ()
    _assert_collision_blocks(root, capsys, expect, *extra)


def test_hardlinked_outputs_collide_via_samefile(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    assert _run(root, "--write") == 0
    os.link(root / ALPHA_MANIFEST, root / "plugins/common/hl.json")
    _edit_policy(
        root,
        lambda p: p["targets"][2].__setitem__("manifestPath", "plugins/common/hl.json"),
    )
    _assert_collision_blocks(root, capsys, "gamma:plugins/common/hl.json")


def test_copied_file_is_not_a_collision(tmp_path):
    """양성 대조: 내용만 같은 다른 파일(하드링크 아님)은 충돌이 아니다."""
    root = _fake_repo(tmp_path)
    assert _run(root, "--write") == 0
    (root / "plugins/common/copy.json").write_bytes(
        (root / ALPHA_MANIFEST).read_bytes()
    )
    _edit_policy(
        root,
        lambda p: p["targets"][2].__setitem__(
            "manifestPath", "plugins/common/copy.json"
        ),
    )
    assert _run(root, "--write") == 0
    assert _run(root, "--check") == 0


HOST_PLATFORMS = ["linux", "darwin", "win32"]


@pytest.mark.parametrize("platform", HOST_PLATFORMS)
def test_case_only_difference_collides_on_every_platform(
    tmp_path, capsys, monkeypatch, platform
):
    """ATK-R01: 판정은 빌드 호스트가 아니라 소비자 FS 기준이다 — 철자만 다른 경로는 어느
    호스트에서 판정해도 같은 파일이다(대소문자를 무시하는 macOS·Windows 소비자)."""
    root = _collide(tmp_path, "plugins/common/.ALPHA-plugin/plugin.json")
    monkeypatch.setattr(sys, "platform", platform)
    before = _snapshot(root)
    assert _run(root, "--write") == 1
    out = capsys.readouterr().out
    assert (
        "✗ 출력 경로 충돌 — alpha:plugins/common/.alpha-plugin/plugin.json ↔ gamma:"
        in out
    )
    assert _snapshot(root) == before


def test_write_only_names_other_failing_target(tmp_path, capsys):
    """ATK-009: --only alpha 가 다른 타겟(gamma) 계산 실패로 막히면 그 사실을 말한다."""
    root = _fake_repo(tmp_path)
    _edit_policy(root, lambda p: p["targets"][2].pop("manifestPath"))
    assert _run(root, "--write", "--only", "alpha") == 1
    err = capsys.readouterr().err
    assert "충돌 검사를 위해 활성 타겟 전체를 계산했다 — 실패 타겟: gamma" in err
    assert _run(root, "--write", "--only", "gamma") == 1
    assert "실패 타겟" not in capsys.readouterr().err


# ── --only <edition> 은 판 빌더로 안내하는 오류 ─────────────────────────────


@pytest.mark.parametrize("mode", ["--check", "--write"])
@pytest.mark.parametrize("enabled", [False, True])
def test_only_edition_target_is_exit_1_pointing_to_builder(
    tmp_path, capsys, mode, enabled
):
    root = _edition_repo(tmp_path, enabled=enabled)
    before = _snapshot(root)
    capsys.readouterr()
    assert _run(root, mode, "--only", "epsilon") == 1
    err = capsys.readouterr().err
    assert "판 빌더(scripts/build-epsilon-branch.py)가 담당한다" in err
    assert _snapshot(root) == before


def test_enabled_edition_target_is_not_generated_on_main(tmp_path):
    root = _edition_repo(tmp_path, enabled=True)
    (root / "scripts").mkdir()
    (root / "scripts/build-epsilon-branch.py").write_text("# builder\n")
    before = _files(root)
    assert _run(root, "--write") == 0
    assert _files(root) == before
    assert _run(root, "--check") == 0


@pytest.mark.parametrize("mode", ["--check", "--write"])
def test_enabled_edition_requires_builder_file(tmp_path, capsys, mode):
    """ATK-R02: enabled:true 는 판 빌더가 판을 쓸 수 있다는 뜻 — 빌더가 없으면 exit 1."""
    root = _edition_repo(tmp_path, enabled=True)
    before = _snapshot(root)
    capsys.readouterr()
    assert _run(root, mode) == 1
    assert (
        "enabled:true 인데 판 빌더 scripts/build-epsilon-branch.py 가 레포에 없다"
        in (capsys.readouterr().out)
    )
    assert _snapshot(root) == before
    (root / "scripts").mkdir()
    (root / "scripts/build-epsilon-branch.py").mkdir()  # 디렉토리는 파일이 아니다
    assert _run(root, mode) == 1


def test_disabled_edition_does_not_require_builder_file(tmp_path):
    root = _edition_repo(tmp_path, enabled=False)
    assert not (root / "scripts/build-epsilon-branch.py").exists()
    assert _run(root, "--check") == 0


def test_enabled_edition_builder_path_cannot_escape(tmp_path, capsys):
    outside = tmp_path / "builder.py"
    outside.write_text("")
    root = _edition_repo(tmp_path, enabled=True, editionBuilder=str(outside))
    assert _run(root, "--check") == 1
    assert "editionBuilder: 경로 탈출 차단" in capsys.readouterr().err


# ── fail-closed 불변식: 디스크 + 계산된 생성물 (ATK-003·007) ─────────────────

ANTIGRAVITY_URL = "https://antigravity.google/schemas/v1/plugin.json"


def _root_manifest_repo(tmp_path: Path) -> Path:
    """gamma 를 Antigravity 모양(`<pluginRoot>/plugin.json`)으로 둔 픽스처, 생성 완료 상태."""
    root = _fake_repo(tmp_path)
    _edit_policy(
        root,
        lambda p: p["targets"][2].update(
            manifestPath="plugins/common/plugin.json", schemaUrl=ANTIGRAVITY_URL
        ),
    )
    assert _run(root, "--write") == 0
    assert _run(root, "--check") == 0
    return root


@pytest.mark.parametrize(
    "argv",
    [
        ("--write", "--only", "gamma"),
        ("--write",),
        ("--check", "--only", "gamma"),
        ("--check", "--only", "alpha"),
        ("--check",),
    ],
)
def test_policy_turning_root_manifest_into_ap_v1_is_blocked(tmp_path, capsys, argv):
    root = _root_manifest_repo(tmp_path)
    _edit_policy(root, lambda p: p["targets"][2].__setitem__("schemaUrl", AP_URL))
    before = _snapshot(root)
    capsys.readouterr()
    assert _run(root, *argv) == 1
    out = capsys.readouterr().out
    assert (
        "fail-closed 불변식 위반 — 생성물 gamma:plugins/common/plugin.json 가 $schema 를 AP v1 URL 로 쓴다"
        in out
    ), out
    assert _snapshot(root) == before  # 디스크 무변경 — AP $schema 가 쓰이지 않았다
    assert AP_URL not in (root / "plugins/common/plugin.json").read_text()


def _set_alpha(key: str, value: object):
    return lambda p: p["targets"][0].__setitem__(key, value)


_NATIVE_SPELLINGS = [
    # (라벨, 픽스처, 정책 편집, 발화해야 하는 문구, 그 문구가 나오는 스트림)
    (
        "yaml",
        "plain",
        lambda p: p["targets"][2].__setitem__(
            "manifestPath", "plugins/common/plugin.yaml"
        ),
        "gamma:plugins/common/plugin.yaml 가 "
        "plugins/common 의 Hermes 네이티브 매니페스트 자리다",
        "out",
    ),
    (
        "yml",
        "plain",
        lambda p: p["targets"][2].__setitem__(
            "manifestPath", "plugins/common/plugin.yml"
        ),
        "Hermes 네이티브 매니페스트 자리",
        "out",
    ),
    (
        "dot-slash",
        "plain",
        lambda p: p["targets"][2].__setitem__(
            "manifestPath", "./plugins/common/plugin.yaml"
        ),
        "Hermes 네이티브 매니페스트 자리",
        "out",
    ),
    (
        "parent-segment-yml",
        "plain",
        lambda p: p["targets"][2].__setitem__(
            "manifestPath", "plugins/common/skills/../plugin.yml"
        ),
        "Hermes 네이티브 매니페스트 자리",
        "out",
    ),
    (
        "upper-case-yaml",
        "plain",
        lambda p: p["targets"][2].__setitem__(
            "manifestPath", "plugins/common/Plugin.YAML"
        ),
        "Hermes 네이티브 매니페스트 자리",
        "out",
    ),
    (
        "parent-segment-json-ap",
        "plain",
        lambda p: p["targets"][2].update(
            manifestPath="plugins/common/skills/../plugin.json", schemaUrl=AP_URL
        ),
        "$schema 를 AP v1 URL 로 쓴다",
        "out",
    ),
    (
        "upper-case-json-ap",
        "plain",
        lambda p: p["targets"][2].update(
            manifestPath="plugins/common/PLUGIN.json", schemaUrl=AP_URL
        ),
        "$schema 를 AP v1 URL 로 쓴다",
        "out",
    ),
    (
        "hooks-path",
        "hooks",
        lambda p: p["targets"][0]["hooks"].__setitem__(
            "path", "plugins/common/plugin.yaml"
        ),
        "alpha:plugins/common/plugin.yaml 가 "
        "plugins/common 의 Hermes 네이티브 매니페스트 자리다",
        "out",
    ),
    # skillInterface.path 는 스킬 디렉토리 안으로 봉쇄된다 — 같은 자리를 가리키면 탈출 차단이다
    (
        "skill-interface-path",
        "skills",
        lambda p: p["targets"][0]["skillInterface"].__setitem__(
            "path", "../../plugin.yaml"
        ),
        "skillInterface.path: 경로 탈출 차단",
        "err",
    ),
]


@pytest.mark.parametrize(
    ("label", "repo", "edit", "expect", "stream"), _NATIVE_SPELLINGS
)
@pytest.mark.parametrize("platform", HOST_PLATFORMS)
def test_generated_artifact_at_native_manifest_path_is_blocked(
    tmp_path, capsys, monkeypatch, label, repo, edit, expect, stream, platform
):
    if repo == "hooks":
        root = _hooks_repo(tmp_path)
    elif repo == "skills":
        root = _skill_repo(tmp_path, {"plain": _TWO_SKILLS["plain"]})
    else:
        root = _fake_repo(tmp_path)
    _edit_policy(root, edit)
    monkeypatch.setattr(sys, "platform", platform)
    before = _snapshot(root)
    for argv in (
        ("--write", "--only", "gamma"),
        ("--write",),
        ("--check", "--only", "alpha"),
    ):
        assert _run(root, *argv) == 1, (label, argv)
        captured = capsys.readouterr()
        assert expect in getattr(captured, stream), (label, argv, captured)
    assert _snapshot(root) == before


@pytest.mark.parametrize(
    ("label", "schema", "expect"),
    [
        ("ap-schema", AP_URL, 1),
        ("other-schema", ANTIGRAVITY_URL, 0),
        ("no-schema", None, 0),
    ],
)
@pytest.mark.parametrize("only", [None, "alpha"])
def test_invariant_root_plugin_json_must_not_declare_ap_schema(
    tmp_path, capsys, label, schema, expect, only
):
    root = _fake_repo(tmp_path)
    assert _run(root, "--write") == 0
    data = {"name": "fixture-kit"}
    if schema is not None:
        data["$schema"] = schema
    (root / "plugins/common/plugin.json").write_text(json.dumps(data))
    extra = ("--only", only) if only else ()
    capsys.readouterr()
    assert _run(root, "--check", *extra) == expect, label
    if expect:
        assert "plugins/common/plugin.json 의 $schema 가 AP v1 URL 이다" in (
            capsys.readouterr().out
        )


def test_invariant_unreadable_root_plugin_json_is_not_passed(tmp_path, capsys):
    root = _fake_repo(tmp_path)
    assert _run(root, "--write") == 0
    (root / "plugins/common/plugin.json").write_text("{not json")
    capsys.readouterr()
    assert _run(root, "--check") == 1
    assert (
        "fail-closed 불변식 판정 불가 — plugins/common/plugin.json 를 읽지 못했다"
        in (capsys.readouterr().out)
    )


def test_invariant_read_cannot_follow_symlink_outside_repo(tmp_path, capsys):
    """ATK-007: 불변식이 읽는 plugin.json 이 레포 밖을 가리키는 심링크면 읽지 않고 exit 1."""
    root = _fake_repo(tmp_path)
    assert _run(root, "--write") == 0
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"$schema": ANTIGRAVITY_URL}))
    (root / "plugins/common/plugin.json").symlink_to(outside)
    capsys.readouterr()
    assert _run(root, "--check") == 1
    assert "fail-closed 불변식: 경로 탈출 차단" in capsys.readouterr().err


def test_invariant_read_follows_internal_symlink(tmp_path):
    """양성 대조: 레포 안을 가리키는 심링크는 따라가 판정한다."""
    root = _fake_repo(tmp_path)
    assert _run(root, "--write") == 0
    (root / "plugins/common/real.json").write_text(
        json.dumps({"$schema": ANTIGRAVITY_URL})
    )
    (root / "plugins/common/plugin.json").symlink_to("real.json")
    assert _run(root, "--check") == 0


@pytest.mark.parametrize("name", ["plugin.yaml", "plugin.yml"])
@pytest.mark.parametrize("dangling_symlink", [False, True])
@pytest.mark.parametrize("only", [None, "alpha"])
def test_invariant_native_manifest_must_be_absent(
    tmp_path, capsys, name, dangling_symlink, only
):
    root = _fake_repo(tmp_path)
    assert _run(root, "--write") == 0
    assert _run(root, "--check") == 0
    target = root / "plugins/common" / name
    if dangling_symlink:
        target.symlink_to("does-not-exist.yaml")
    else:
        target.write_text("name: fixture-kit\n")
    extra = ("--only", only) if only else ()
    capsys.readouterr()
    assert _run(root, "--check", *extra) == 1
    out = capsys.readouterr().out
    assert f"fail-closed 불변식 위반 — plugins/common/{name} 이 있다" in out


@pytest.mark.parametrize(
    ("names", "natives", "manifests"),
    [
        (["plugin.json", "skills"], [], ["plugin.json"]),
        (["PLUGIN.json"], [], ["PLUGIN.json"]),
        (["Plugin.yaml", "README.md"], ["Plugin.yaml"], []),
        (["PLUGIN.YML"], ["PLUGIN.YML"], []),
        (["plugin.json", "Plugin.JSON"], [], ["Plugin.JSON", "plugin.json"]),
        (["plugin.json5", "my-plugin.yaml"], [], []),
    ],
)
def test_root_manifest_names_casefold(names, natives, manifests):
    """ATK-R01: 디스크 판정의 이름 선택은 호스트 FS 와 무관한 casefold 비교다."""
    assert _mod.root_manifest_names(names) == (natives, manifests)


@pytest.mark.parametrize("platform", HOST_PLATFORMS)
@pytest.mark.parametrize(
    ("name", "content", "expect"),
    [
        ("Plugin.yaml", "name: x\n", "plugins/common/Plugin.yaml 이 있다"),
        ("PLUGIN.yml", "name: x\n", "plugins/common/PLUGIN.yml 이 있다"),
        (
            "PLUGIN.json",
            json.dumps({"$schema": AP_URL}),
            "plugins/common/PLUGIN.json 의 $schema 가 AP v1 URL 이다",
        ),
    ],
)
def test_disk_invariant_catches_case_variants(
    tmp_path, capsys, monkeypatch, platform, name, content, expect
):
    root = _fake_repo(tmp_path)
    assert _run(root, "--write") == 0
    (root / "plugins/common" / name).write_text(content)
    monkeypatch.setattr(sys, "platform", platform)
    capsys.readouterr()
    for argv in (("--check",), ("--check", "--only", "alpha"), ("--write",)):
        assert _run(root, *argv) == 1, argv
        assert expect in capsys.readouterr().out, argv


def test_disk_invariant_multiple_manifest_candidates_is_undecidable(
    tmp_path, capsys, monkeypatch
):
    """대소문자를 구분하는 FS 에서만 둘이 공존할 수 있다 — 나열 결과를 바꿔 끼워 재현한다."""
    root = _fake_repo(tmp_path)
    assert _run(root, "--write") == 0
    real = _mod.root_manifest_names
    monkeypatch.setattr(
        _mod,
        "root_manifest_names",
        lambda names: real([*names, "plugin.json", "PLUGIN.json"]),
    )
    capsys.readouterr()
    assert _run(root, "--check") == 1
    assert (
        "fail-closed 불변식 판정 불가 — plugins/common 에 ['PLUGIN.json', 'plugin.json'] 가 함께 있다"
        in (capsys.readouterr().out)
    )


# ── --write 도 디스크 불변식을 본다 (ATK-R06) ───────────────────────────────


@pytest.mark.parametrize("name", ["plugin.yaml", "Plugin.yml"])
def test_write_refuses_on_existing_dangling_native_manifest(tmp_path, capsys, name):
    root = _fake_repo(tmp_path)
    (root / "plugins/common" / name).symlink_to("nowhere.yaml")
    before = _snapshot(root)
    assert _run(root, "--write") == 1
    out = capsys.readouterr().out
    assert f"fail-closed 불변식 위반 — plugins/common/{name} 이 있다" in out
    assert "아무것도 기록하지 않았다" in out
    assert _snapshot(root) == before
    assert not (root / ALPHA_MANIFEST).exists()


def test_write_cannot_fill_dangling_plugin_json_symlink_with_ap_manifest(
    tmp_path, capsys
):
    """`plugin.json -> x.json`(끊어진 링크)을 심고 x.json 을 AP $schema 로 생성하는 우회."""
    root = _fake_repo(tmp_path)
    _edit_policy(
        root,
        lambda p: p["targets"][2].update(
            manifestPath="plugins/common/x.json", schemaUrl=AP_URL
        ),
    )
    (root / "plugins/common/plugin.json").symlink_to("x.json")
    before = _snapshot(root)
    assert _run(root, "--write", "--only", "gamma") == 1
    out = capsys.readouterr().out
    assert "생성물 gamma:plugins/common/x.json 가 $schema 를 AP v1 URL 로 쓴다" in out
    assert _snapshot(root) == before
    assert not (root / "plugins/common/x.json").exists()


def test_write_with_clean_disk_still_writes(tmp_path):
    """양성 대조: 디스크 불변식이 깨끗하면 --write 는 그대로 기록한다."""
    root = _fake_repo(tmp_path)
    assert _run(root, "--write") == 0
    assert (root / ALPHA_MANIFEST).exists()


# ── 남은 traceback 경로 (ATK-R03) ───────────────────────────────────────────


@pytest.mark.parametrize("mode", ["--check", "--write"])
@pytest.mark.parametrize(
    ("label", "mutate", "expect"),
    [
        (
            "policy-top-level-list",
            lambda root: (root / "packaging/targets.json").write_text("[]"),
            "정책 파일 최상위는 JSON 객체여야 한다",
        ),
        (
            "gate-not-object",
            lambda root: _edit_policy(root, lambda p: p.__setitem__("gate", "yes")),
            "정책 파일 gate 는 객체여야 한다",
        ),
        (
            "ssot-not-object",
            lambda root: (
                root / "plugins/common/.claude-plugin/plugin.json"
            ).write_text("[]"),
            "SSOT 매니페스트 최상위는 JSON 객체여야 한다",
        ),
    ],
)
def test_policy_shape_errors_are_clean_exit_1(
    tmp_path, capsys, mode, label, mutate, expect
):
    root = _fake_repo(tmp_path)
    mutate(root)
    assert _run(root, mode) == 1, label
    assert expect in capsys.readouterr().err, label


@pytest.mark.parametrize("mode", ["--check", "--write"])
@pytest.mark.parametrize(
    "entries", [{"script": "hooks/inject.py"}, "hooks/inject.py", None]
)
def test_hook_event_entries_must_be_a_list(tmp_path, capsys, mode, entries):
    root = _hooks_repo(tmp_path)
    _edit_policy(
        root,
        lambda p: p["targets"][0]["hooks"]["events"].__setitem__(
            "SessionStart", entries
        ),
    )
    assert _run(root, mode) == 1
    assert (
        "hooks.events.SessionStart: 엔트리 목록이 필요하다" in capsys.readouterr().err
    )


@pytest.mark.parametrize("mode", ["--check", "--write"])
def test_marketplace_requires_ssot_name(tmp_path, capsys, mode):
    root = _fake_repo(tmp_path)
    ssot = {k: v for k, v in SSOT.items() if k != "name"}
    (root / "plugins/common/.claude-plugin/plugin.json").write_text(json.dumps(ssot))

    def no_name(p):
        for t in p["targets"]:
            t["requiredFields"] = ["version"]

    _edit_policy(root, no_name)
    assert _run(root, mode) == 1
    assert "타겟 'alpha' marketplace 의 SSOT 매니페스트: 필수 키 'name'" in (
        capsys.readouterr().err
    )


# ── 실제 레포(읽기 전용) ────────────────────────────────────────────────────


def _real(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "build-targets.py"), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_real_repo_hermes_policy_and_check():
    policy = json.loads(
        (SCRIPTS_DIR.parent / "packaging/targets.json").read_text(encoding="utf-8")
    )
    hermes = next(t for t in policy["targets"] if t["id"] == "hermes")
    assert hermes["enabled"] is False
    assert hermes["delivery"] == "edition"
    # H1 sandbox round trip (install → list → remove with the real CLI) passed on 2026-11-24, so the
    # target is runtime-verified; it stays disabled until the user approves publishing (H2).
    assert hermes["verificationLevel"] == "runtime-verified"
    assert "_observations20261124" in hermes
    assert hermes["schemaUrl"] == AP_URL
    assert hermes["requiredFields"] == ["name", "version", "description"]
    assert hermes["passthroughFields"] == [
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
    ]
    assert "manifestPath" not in hermes
    assert hermes.get("_disabledReason")
    assert "hermes_agent_plugins_352b249.txt" in hermes["_apV1Source"]

    proc = _real("--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    last = proc.stdout.strip().splitlines()[-1]
    assert "생성물 22개" in last and "edition 1개" in last, last


def test_real_repo_only_hermes_is_exit_1():
    proc = _real("--check", "--only", "hermes")
    assert proc.returncode == 1
    assert "scripts/build-hermes-branch.py" in proc.stderr
