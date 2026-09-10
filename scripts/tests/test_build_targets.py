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
from pathlib import Path
from types import ModuleType

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
