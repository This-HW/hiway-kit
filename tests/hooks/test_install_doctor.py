from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "plugins/common/tools"
sys.path.insert(0, str(TOOLS))
import install_doctor as doctor
import install_doctor_io as io

PLUGIN = "example@sample-market"


def put_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def layout(tmp_path):
    home = tmp_path / "home"
    source = tmp_path / "source"
    installed = home / "plugins/cache/sample-market/example/5.6.0"
    manifest = {"name": "example", "version": "5.6.0", "hooks": "./hooks/hooks-codex.json"}
    hook = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "never executed"}]}]}}
    for root in (installed, source / "plugin"):
        put_json(root / doctor.MANIFEST, manifest)
        put_json(root / "hooks/hooks-codex.json", hook)
    put_json(source / doctor.MARKETPLACE, {"name": "sample-market", "plugins": [
        {"name": "example", "source": {"source": "local", "path": "./plugin"}}
    ]})
    config = home / "config.toml"
    config.write_text(
        '[marketplaces.sample-market]\nsource_type = "local"\n'
        f'source = {json.dumps(str(source))}\n'
        f'[plugins."{PLUGIN}"]\nenabled = true\n'
        f'[hooks.state."{PLUGIN}:hooks/hooks-codex.json:session_start:0:0"]\n'
        'enabled = false\ntrusted_hash = "redacted-fixture-marker"\n', encoding="utf-8")
    return {"home": home, "source": source, "installed": installed, "config": config, "tmp": tmp_path}


def args(layout, *extra):
    return ["--codex-home", str(layout["home"]), "--plugin", PLUGIN, "--codex-bin", sys.executable, *map(str, extra)]


def run(layout, capsys, *extra):
    rc = doctor.main(args(layout, *extra))
    return rc, json.loads(capsys.readouterr().out)


def capture(layout, capsys):
    path = layout["tmp"] / "snapshot.json"
    rc, report = run(layout, capsys, "--capture-snapshot", path)
    assert rc in (0, 1), report
    assert path.is_file()
    return path


def test_match_keeps_hook_disabled_and_trust_firing_unknown(layout, capsys):
    before = {p: p.read_bytes() for p in layout["tmp"].rglob("*") if p.is_file()}
    rc, report = run(layout, capsys)
    assert rc == 0
    assert report["installation"]["status"] == "match"
    assert report["installation"]["installed_version"] == "5.6.0"
    hooks = report["hooks"]
    assert hooks["discovered"]["value"] is True
    assert hooks["enabled"]["value"] is False
    assert hooks["trusted"]["value"] == hooks["fired"]["value"] == "unknown"
    entry = hooks["entries"][0]
    assert entry["configured_trust_hash_present"] is True
    assert entry["trusted"]["value"] == entry["fired"]["value"] == "unknown"
    assert before == {p: p.read_bytes() for p in layout["tmp"].rglob("*") if p.is_file()}
    assert "redacted-fixture-marker" not in json.dumps(report)
    assert "never executed" not in json.dumps(report)


def test_audited_56_vs_55_mismatch_and_capture(layout, capsys):
    path = layout["source"] / "plugin" / doctor.MANIFEST
    value = json.loads(path.read_text())
    value["version"] = "5.5.1"
    put_json(path, value)
    rc, report = run(layout, capsys)
    assert rc == 1
    assert report["installation"] == {"status": "defect", "reason": "installation_source_version_mismatch",
                                       "installed_version": "5.6.0", "source_version": "5.5.1", "source_type": "local"}
    snapshot = capture(layout, capsys)
    assert run(layout, capsys, "--snapshot", snapshot)[0] == 1


def test_no_codex_is_unknown_even_when_files_match(layout, capsys):
    rc, report = run(layout, capsys, "--codex-bin", str(layout["tmp"] / "absent"))
    assert rc == 2 and report["installation"]["reason"] == "codex_executable_unavailable"


def test_no_toml_parser_requires_snapshot(layout, capsys, monkeypatch):
    monkeypatch.setattr(doctor, "tomllib", None)
    rc, report = run(layout, capsys)
    assert rc == 2 and report["installation"]["reason"] == "toml_parser_unavailable_use_snapshot"


def test_snapshot_provenance_selected_fields_and_python39_path(layout, capsys, monkeypatch):
    snapshot = capture(layout, capsys)
    value = json.loads(snapshot.read_text())
    assert value["schema"] == doctor.SNAPSHOT_SCHEMA
    assert value["captured_at"]
    assert value["config"]["path"] == str(layout["config"])
    assert value["config"]["sha256"] == hashlib.sha256(layout["config"].read_bytes()).hexdigest()
    assert all(set(entry) == {"kind", "path", "sha256"} for entry in value["observations"])
    assert "redacted-fixture-marker" not in snapshot.read_text()
    monkeypatch.setattr(doctor, "tomllib", None)
    assert run(layout, capsys, "--snapshot", snapshot)[0] == 0


@pytest.mark.parametrize("target", ["config", "installed", "source", "hooks", "marketplace"])
def test_snapshot_mutation_fails_and_restoration_passes(layout, capsys, monkeypatch, target):
    snapshot = capture(layout, capsys)
    paths = {"config": layout["config"], "installed": layout["installed"] / doctor.MANIFEST,
             "source": layout["source"] / "plugin" / doctor.MANIFEST,
             "hooks": layout["installed"] / "hooks/hooks-codex.json",
             "marketplace": layout["source"] / doctor.MARKETPLACE}
    path = paths[target]
    before = path.read_bytes()
    monkeypatch.setattr(doctor, "tomllib", None)
    path.write_bytes(before + b"\n")
    rc, report = run(layout, capsys, "--snapshot", snapshot)
    assert rc == 2 and report["installation"]["reason"] == "snapshot_stale"
    path.write_bytes(before)
    assert run(layout, capsys, "--snapshot", snapshot)[0] == 0


@pytest.mark.parametrize("mutation,reason", [
    ("future", "snapshot_timestamp_invalid"), ("naive", "snapshot_timestamp_invalid"),
    ("timestamp", "snapshot_invalid"), ("schema", "snapshot_schema_unknown"),
    ("bool_schema", "snapshot_schema_unknown"), ("home", "snapshot_target_mismatch"),
    ("plugin", "snapshot_target_mismatch"), ("origin", "snapshot_config_path_mismatch"),
    ("missing", "snapshot_observations_missing"), ("auth_origin", "snapshot_stale"),
    ("selected", "snapshot_selected_fields_mismatch"),
])
def test_bad_snapshot_unknown_without_opening_supplied_origins(layout, capsys, mutation, reason):
    snapshot = capture(layout, capsys)
    value = json.loads(snapshot.read_text())
    if mutation == "future":
        value["captured_at"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    elif mutation == "naive":
        value["captured_at"] = "2020-01-01T00:00:00"
    elif mutation == "timestamp":
        value["captured_at"] = "invalid"
    elif mutation in ("schema", "bool_schema"):
        value["schema"] = 99 if mutation == "schema" else True
    elif mutation == "home":
        value["codex_home"] = str(layout["tmp"])
    elif mutation == "plugin":
        value["plugin_id"] = "other@sample-market"
    elif mutation == "origin":
        value["config"]["path"] = str(layout["home"] / "auth.json")
    elif mutation == "missing":
        value["observations"] = []
    elif mutation == "auth_origin":
        value["observations"].append({"kind": "config", "path": str(layout["home"] / "auth.json"), "sha256": "untrusted"})
    else:
        value["config"]["selected"]["plugin"]["enabled"] = False
    put_json(snapshot, value)
    rc, report = run(layout, capsys, "--snapshot", snapshot)
    assert rc == 2 and report["installation"]["reason"] == reason


@pytest.mark.parametrize("payload", ["{", "[]", '"secret-looking input must not echo"', "{}"])
def test_bad_json_snapshot(layout, capsys, payload):
    snapshot = layout["tmp"] / "bad.json"
    snapshot.write_text(payload)
    rc, report = run(layout, capsys, "--snapshot", snapshot)
    assert rc == 2
    assert "secret-looking" not in json.dumps(report)


@pytest.mark.parametrize("location", ["cache", "source", "marketplace", "hooks"])
def test_invalid_manifest_is_confirmed_defect(layout, capsys, location):
    path = {"cache": layout["installed"] / doctor.MANIFEST,
            "source": layout["source"] / "plugin" / doctor.MANIFEST,
            "marketplace": layout["source"] / doctor.MARKETPLACE,
            "hooks": layout["installed"] / "hooks/hooks-codex.json"}[location]
    path.write_text('{"sensitive-field": broken')
    rc, report = run(layout, capsys)
    assert rc == 1
    assert "sensitive-field" not in json.dumps(report)


@pytest.mark.parametrize("bad", ["/outside/plugin", "../plugin", "plugin/../../outside", "plugin/auth.json"])
def test_source_plugin_path_contained(layout, capsys, bad):
    path = layout["source"] / doctor.MARKETPLACE
    value = json.loads(path.read_text())
    value["plugins"][0]["source"]["path"] = bad
    put_json(path, value)
    rc, report = run(layout, capsys)
    # R-2: unsupported source paths and forbidden access are unknown evidence.
    assert rc == 2 and report["installation"]["status"] == "unknown"
    assert report["installation"]["reason"] == ("forbidden_file" if bad.endswith("auth.json") else "unsafe_path")


@pytest.mark.parametrize("location", ["plugin", "manifest", "hook", "auth_hook", "cache"])
def test_symlink_escape_and_auth_alias_rejected(layout, capsys, location):
    outside = layout["tmp"] / "outside"
    outside.mkdir()
    if location == "plugin":
        path = layout["source"] / "plugin"
        shutil.rmtree(path)
        path.symlink_to(outside, target_is_directory=True)
    elif location == "cache":
        path = layout["installed"]
        shutil.rmtree(path)
        path.symlink_to(outside, target_is_directory=True)
    else:
        path = layout["installed"] / ("hooks/hooks-codex.json" if location in ("hook", "auth_hook") else doctor.MANIFEST)
        path.unlink()
        path.symlink_to(layout["home"] / "auth.json" if location == "auth_hook" else outside / "data.json")
    rc, report = run(layout, capsys)
    assert rc == (2 if location == "plugin" else 1)
    reason = report["hooks"]["observation_reason"] if location in ("hook", "auth_hook") else report["installation"]["reason"]
    assert reason == ("source_symlink_unsupported" if location == "plugin" else "unsafe_symlink")


@pytest.mark.parametrize("relative", ["../auth.json", "/auth.json", "hooks/auth.json"])
def test_hook_auth_and_unsafe_paths_rejected(layout, capsys, relative):
    path = layout["installed"] / doctor.MANIFEST
    value = json.loads(path.read_text())
    value["hooks"] = relative
    put_json(path, value)
    rc, report = run(layout, capsys)
    # R-2: refusing a requested path does not confirm an installation defect.
    assert rc == 2
    assert report["hooks"]["discovered"]["value"] == "unknown"
    assert report["installation"]["status"] == "match"


def test_multiple_cache_versions_require_explicit_selection(layout, capsys):
    other = layout["installed"].parent / "5.5.1"
    shutil.copytree(layout["installed"], other)
    rc, report = run(layout, capsys)
    assert rc == 2 and report["installation"]["reason"] == "active_cache_ambiguous"
    assert run(layout, capsys, "--installed-path", layout["installed"])[0] == 0
    assert run(layout, capsys, "--installed-path", layout["source"] / "plugin")[0] == 2


@pytest.mark.parametrize("location,field", [("cache", "name"), ("source", "name"), ("source", "id"), ("market", "name")])
def test_identity_must_match(layout, capsys, location, field):
    path = (layout["source"] / doctor.MARKETPLACE if location == "market" else
            (layout["installed"] if location == "cache" else layout["source"] / "plugin") / doctor.MANIFEST)
    value = json.loads(path.read_text())
    value[field] = "another"
    put_json(path, value)
    assert run(layout, capsys)[0] == 1


def git_source(layout, remote="https://example.invalid/sample.git"):
    config = layout["config"]
    text = config.read_text().replace('source_type = "local"', 'source_type = "git"')
    text = text.replace(f'source = {json.dumps(str(layout["source"]))}', 'source = "https://example.invalid/sample.git"')
    config.write_text(text)
    path = layout["source"] / ".git/config"
    path.parent.mkdir()
    path.write_text('[remote "origin"]\n\turl = ' + remote + '\n')
    return path


def test_git_checkout_local_provenance_and_no_fetch(layout, capsys):
    git_source(layout)
    rc, report = run(layout, capsys)
    assert rc == 2 and report["installation"]["reason"] == "source_checkout_unavailable"
    rc, report = run(layout, capsys, "--source-checkout", layout["source"])
    assert rc == 0 and report["installation"]["source_type"] == "git"
    assert report["installation"]["comparison_scope"] == "supplied_checkout"
    assert report["installation"]["remote_freshness"] == "unverified"
    path = layout["tmp"] / "git-snapshot.json"
    assert run(layout, capsys, "--source-checkout", layout["source"], "--capture-snapshot", path)[0] == 0
    assert run(layout, capsys, "--source-checkout", layout["source"], "--snapshot", path)[0] == 0


def test_git_checkout_version_mismatch_is_unverified_with_both_versions(layout, capsys):
    git_source(layout)
    path = layout["source"] / "plugin" / doctor.MANIFEST
    value = json.loads(path.read_text())
    value["version"] = "5.5.1"
    put_json(path, value)
    rc, report = run(layout, capsys, "--source-checkout", layout["source"])
    installation = report["installation"]
    assert rc == 2 and installation["status"] == "unknown"
    assert installation["reason"] == "source_checkout_unverified_version_mismatch"
    assert installation["installed_version"] == "5.6.0"
    assert installation["source_version"] == "5.5.1"
    assert installation["comparison_scope"] == "supplied_checkout"
    assert installation["remote_freshness"] == "unverified"


@pytest.mark.parametrize("location", ["checkout_plugin", "checkout_market", "installed"])
@pytest.mark.parametrize("mutation,reason", [
    ("syntax", "invalid_json"), ("object", "invalid_json_object"),
    ("missing", "plugin_manifest_missing"), ("identity", "plugin_identity_mismatch"),
    ("version", "plugin_version_missing"), ("fifo", "not_regular_file"),
    ("directory", "not_regular_file"),
])
def test_git_checkout_and_installed_manifest_error_classes(layout, capsys, location, mutation, reason):
    git_source(layout)
    if location == "checkout_market":
        path = layout["source"] / doctor.MARKETPLACE
    else:
        root = layout["installed"] if location == "installed" else layout["source"] / "plugin"
        path = root / doctor.MANIFEST
    if mutation == "syntax":
        path.write_text('{"private-marker": broken')
    elif mutation == "object":
        path.write_text("[]")
    elif mutation == "missing":
        path.unlink()
        if location == "checkout_market":
            reason = "file_unavailable"
    elif mutation in ("fifo", "directory"):
        path.unlink()
        if mutation == "fifo":
            os.mkfifo(path)
        else:
            path.mkdir()
    else:
        value = json.loads(path.read_text())
        if location == "checkout_market":
            if mutation == "identity":
                value["name"] = "another"
                reason = "marketplace_identity_mismatch"
            else:
                value["plugins"] = None
                reason = "marketplace_plugins_missing"
        else:
            value["name" if mutation == "identity" else "version"] = "invalid"
        put_json(path, value)
    rc, report = run(layout, capsys, "--source-checkout", layout["source"])
    checkout = location.startswith("checkout")
    assert rc == (2 if checkout else 1)
    assert report["installation"]["status"] == ("unknown" if checkout else "defect")
    assert report["installation"]["reason"] == ("source_checkout_unverified_" if checkout else "") + reason
    assert "private-marker" not in json.dumps(report)


@pytest.mark.parametrize("checkout", ["absent", "mismatch", "invalid"])
@pytest.mark.parametrize("defect,reason", [
    ("installed", "invalid_json"), ("store", "plugin_store_writable_by_others"),
    ("hook", "invalid_json"), ("hook_symlink", "unsafe_symlink"),
])
def test_confirmed_installation_defect_precedes_unknown_checkout(layout, capsys, checkout, defect, reason):
    git_source(layout)
    path = layout["source"] / "plugin" / doctor.MANIFEST
    if checkout == "invalid":
        path.write_text("{")
    elif checkout == "mismatch":
        value = json.loads(path.read_text())
        value["version"] = "5.5.1"
        put_json(path, value)
    if defect == "installed":
        (layout["installed"] / doctor.MANIFEST).write_text("{")
    elif defect == "store":
        (layout["home"] / "plugins").chmod(0o777)
    else:
        hook = layout["installed"] / "hooks/hooks-codex.json"
        if defect == "hook_symlink":
            hook.unlink()
            hook.symlink_to(layout["tmp"] / "unopened-hook.json")
        else:
            hook.write_text("{")
    extra = [] if checkout == "absent" else ["--source-checkout", layout["source"]]
    rc, report = run(layout, capsys, *extra)
    assert rc == 1 and report["installation"]["status"] == "defect"
    assert report["installation"]["reason"] == reason


@pytest.mark.parametrize("failure", [OSError, RuntimeError, ValueError])
@pytest.mark.parametrize("defect", ["hook", "store", None])
def test_source_observation_failure_preserves_confirmed_risks(layout, capsys, monkeypatch, failure, defect):
    git_source(layout)
    if defect == "hook":
        (layout["installed"] / "hooks/hooks-codex.json").write_text("{")

    def fail(reader, *unused):
        if defect == "store":
            reader.store_root.chmod(0o777)
        raise failure("private-source-input-must-not-echo")

    monkeypatch.setattr(doctor, "source_root", fail)
    rc, report = run(layout, capsys)
    assert rc == (2 if defect is None else 1)
    assert report["installation"]["reason"] == {
        "hook": "invalid_json", "store": "plugin_store_writable_by_others", None: "observation_unavailable",
    }[defect]
    assert "private-source-input" not in json.dumps(report)


def test_confirmed_hook_defect_precedes_git_mismatch_with_snapshot(layout, capsys):
    git_source(layout)
    snapshot = layout["tmp"] / "git-snapshot.json"
    extra = ["--source-checkout", layout["source"]]
    assert run(layout, capsys, *extra, "--capture-snapshot", snapshot)[0] == 0
    (layout["installed"] / "hooks/hooks-codex.json").write_text("{")
    path = layout["source"] / "plugin" / doctor.MANIFEST
    value = json.loads(path.read_text())
    value["version"] = "5.5.1"
    put_json(path, value)
    rc, report = run(layout, capsys, *extra, "--snapshot", snapshot)
    assert rc == 1 and report["installation"]["reason"] == "invalid_json"
    assert report["installation"]["source_version"] == "5.5.1"


@pytest.mark.parametrize("kind,rc", [("wrong", 2), ("include", 2), ("duplicate", 2), ("missing", 2)])
def test_unlinked_git_checkout_never_green(layout, capsys, kind, rc):
    path = git_source(layout, "https://example.invalid/wrong.git" if kind == "wrong" else "https://example.invalid/sample.git")
    if kind == "include":
        path.write_text(path.read_text() + '[include]\npath = /outside/config\n')
    elif kind == "duplicate":
        path.write_text(path.read_text() + '\turl = https://example.invalid/other.git\n')
    elif kind == "missing":
        path.unlink()
    assert run(layout, capsys, "--source-checkout", layout["source"])[0] == rc


@pytest.mark.parametrize("enabled", [True, False, None])
def test_explicit_enabled_or_unknown_independent_of_trust(layout, capsys, enabled):
    text = layout["config"].read_text().replace('enabled = false\ntrusted_hash',
                                               (f'enabled = {str(enabled).lower()}\n' if enabled is not None else '') + 'trusted_hash')
    layout["config"].write_text(text)
    rc, report = run(layout, capsys)
    assert rc == 0
    assert report["hooks"]["enabled"]["value"] == ("unknown" if enabled is None else enabled)
    assert report["hooks"]["trusted"]["value"] == report["hooks"]["fired"]["value"] == "unknown"


def test_plugin_disabled_is_preserved(layout, capsys):
    layout["config"].write_text(layout["config"].read_text().replace('enabled = true', 'enabled = false'))
    rc, report = run(layout, capsys)
    assert rc == 0 and report["hooks"]["enabled"]["value"] is False


def test_hooks_absent_is_discovered_false_with_positive_control(layout, capsys):
    assert run(layout, capsys)[1]["hooks"]["discovered"]["value"] is True
    path = layout["installed"] / doctor.MANIFEST
    value = json.loads(path.read_text())
    del value["hooks"]
    put_json(path, value)
    rc, report = run(layout, capsys)
    assert rc == 0 and report["hooks"]["discovered"]["value"] is False
    assert report["hooks"]["fired"]["value"] == "unknown"


@pytest.mark.parametrize("budget", ["file", "total", "directory", "time"])
def test_observation_budgets_are_unknown_with_positive_control(layout, capsys, monkeypatch, budget):
    assert run(layout, capsys)[0] == 0
    if budget == "file":
        monkeypatch.setattr(io, "MAX_FILE_BYTES", 10)
    elif budget == "total":
        monkeypatch.setattr(io, "MAX_TOTAL_BYTES", layout["config"].stat().st_size + 10)
    elif budget == "directory":
        monkeypatch.setattr(io, "MAX_ENTRIES", 0)
    else:
        monkeypatch.setattr(io, "MAX_SECONDS", -1)
    rc, report = run(layout, capsys)
    assert rc == 2 and "budget" in report["installation"]["reason"]


def test_fifo_is_rejected_without_blocking(layout, capsys):
    path = layout["installed"] / doctor.MANIFEST
    path.unlink()
    os.mkfifo(path)
    start = time.monotonic()
    rc, report = run(layout, capsys)
    assert rc == 1 and report["installation"]["reason"] == "not_regular_file"
    assert time.monotonic() - start < 1


def test_explicit_capture_never_overwrites_existing_or_auth_output(layout, capsys):
    snapshot = capture(layout, capsys)
    before = snapshot.read_bytes()
    assert run(layout, capsys, "--capture-snapshot", snapshot)[0] == 2
    assert snapshot.read_bytes() == before
    assert run(layout, capsys, "--capture-snapshot", layout["tmp"] / "auth.json")[0] == 2


def test_executable_is_located_never_started(layout, capsys):
    executable = layout["tmp"] / "codex"
    marker = layout["tmp"] / "executed"
    executable.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 99\n')
    executable.chmod(0o700)
    assert run(layout, capsys, "--codex-bin", executable)[0] == 0
    assert not marker.exists()


def test_real_python39_import_snapshot_cli_and_stale(layout, capsys):
    python39 = shutil.which("python3.9")
    if not python39:
        pytest.skip("Python 3.9 executable unavailable")
    snapshot = capture(layout, capsys)
    command = [python39, "-B", str(TOOLS / "install_doctor.py"), *args(layout, "--snapshot", snapshot)]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["hooks"]["fired"]["value"] == "unknown"
    layout["config"].write_text(layout["config"].read_text() + "\n")
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
    assert result.returncode == 2 and json.loads(result.stdout)["installation"]["reason"] == "snapshot_stale"


def test_explicit_home_required_and_environment_supported(layout, capsys, monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    with pytest.raises(SystemExit) as exc:
        doctor.main(["--plugin", PLUGIN])
    assert exc.value.code == 2
    capsys.readouterr()
    monkeypatch.setenv("CODEX_HOME", str(layout["home"]))
    assert doctor.main(["--plugin", PLUGIN, "--codex-bin", sys.executable]) == 0
    capsys.readouterr()


def test_directory_symlink_swap_between_resolution_and_open_is_not_followed(layout, capsys, monkeypatch):
    outside = layout["tmp"] / "outside"
    outside.mkdir()
    original = io.Reader._open
    swapped = False

    def swap(reader, root, path, directory=False):
        nonlocal swapped
        if not swapped and path == layout["installed"] / doctor.MANIFEST:
            swapped = True
            parent = layout["installed"] / ".codex-plugin"
            parent.rename(layout["installed"] / ".original")
            parent.symlink_to(outside, target_is_directory=True)
        return original(reader, root, path, directory)

    monkeypatch.setattr(io.Reader, "_open", swap)
    rc, report = run(layout, capsys)
    assert swapped and rc == 1
    assert report["installation"]["reason"] == "unsafe_symlink"


def test_file_growth_and_total_read_budget_enforced_during_read(layout, capsys, monkeypatch):
    original = os.read

    def grow(fd, size):
        return b"x" * size

    monkeypatch.setattr(io, "MAX_FILE_BYTES", 1024)
    monkeypatch.setattr(io.os, "read", grow)
    rc, report = run(layout, capsys)
    assert rc == 2 and report["installation"]["reason"] == "read_budget_exceeded"
    monkeypatch.setattr(io.os, "read", original)
    assert run(layout, capsys)[0] == 0


def test_missing_hook_runtime_evidence_does_not_fail_install_comparison(layout, capsys):
    (layout["installed"] / "hooks/hooks-codex.json").unlink()
    rc, report = run(layout, capsys)
    assert rc == 0 and report["installation"]["status"] == "match"
    assert report["hooks"]["discovered"]["value"] == "unknown"
    assert report["hooks"]["trusted"]["value"] == report["hooks"]["fired"]["value"] == "unknown"
    layout["config"].write_text(layout["config"].read_text().replace('enabled = true', 'enabled = false'))
    rc, report = run(layout, capsys)
    assert rc == 0 and report["hooks"]["enabled"]["value"] is False


@pytest.mark.parametrize("reason,expected", [
    ("invalid_json", 1), ("invalid_json_object", 1), ("invalid_hook_manifest", 1),
    ("unsafe_symlink", 1), ("not_regular_file", 1),
    ("plugin_store_not_directory", 1), ("plugin_store_wrong_owner", 1),
    ("plugin_store_writable_by_others", 1),
    ("file_unavailable", 0),
    ("forbidden_file", 2), ("unsafe_path", 2), ("unsafe_hook_path", 2),
    ("hook_path_unsupported", 2), ("hook_schema_unsupported", 2),
    ("safe_file_access_unavailable", 2), ("read_budget_exceeded", 2),
    ("time_budget_exceeded", 2), ("file_changed_during_read", 2),
    ("plugin_store_changed", 2), ("plugin_store_unavailable", 2),
    ("future_observation_error", 2),
])
@pytest.mark.parametrize("error_rc", [0, 1, 2])
def test_hook_observation_returncode_policy(layout, capsys, monkeypatch, reason, expected, error_rc):
    def fail(*unused):
        raise io.ObservationError(reason, error_rc)

    monkeypatch.setattr(doctor, "observe_hooks", fail)
    rc, report = run(layout, capsys)
    assert rc == expected
    assert report["installation"]["status"] == "match"
    assert report["hooks"]["observation_reason"] == reason
    assert report["hooks"]["trusted"]["value"] == report["hooks"]["fired"]["value"] == "unknown"


def test_hook_error_does_not_erase_local_inst001(layout, capsys):
    (layout["installed"] / "hooks/hooks-codex.json").write_text("{")
    path = layout["source"] / "plugin" / doctor.MANIFEST
    value = json.loads(path.read_text())
    value["version"] = "5.5.1"
    put_json(path, value)
    rc, report = run(layout, capsys)
    assert rc == 1 and report["installation"]["reason"] == "installation_source_version_mismatch"


def test_snapshot_auth_origin_is_never_opened(layout, capsys, monkeypatch):
    snapshot = capture(layout, capsys)
    value = json.loads(snapshot.read_text())
    value["observations"].append({"kind": "config", "path": str(layout["home"] / "auth.json"), "sha256": "ignored"})
    put_json(snapshot, value)
    original = os.open
    opened = []

    def checked(path, *args, **kwargs):
        opened.append(str(path))
        if Path(path).name == "auth.json":
            pytest.fail("authentication file was opened")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(io.os, "open", checked)
    rc, report = run(layout, capsys, "--snapshot", snapshot)
    assert rc == 2 and report["installation"]["reason"] == "snapshot_stale"
    assert opened


@pytest.mark.parametrize("filename", ["auth.json", "credentials.json", "token.json"])
def test_explicit_snapshot_input_cannot_read_auth_files(layout, capsys, filename):
    # Do not create or read even a fixture authentication file.
    rc, report = run(layout, capsys, "--snapshot", layout["tmp"] / filename)
    assert rc == 2 and report["installation"]["reason"] == "forbidden_file"


def share_store(layout):
    plugins = layout["home"] / "plugins"
    moved = layout["tmp"] / "shared-plugins"
    plugins.rename(moved)
    plugins.symlink_to(moved, target_is_directory=True)
    return moved


def test_config_disabled_choice_survives_normal_shared_plugin_store(layout, capsys):
    moved = share_store(layout)
    rc, report = run(layout, capsys)
    assert rc == 0 and report["installation"]["status"] == "match"
    assert report["store"] == {"store_root": str(moved), "store_shared": True,
                                "link_source": str(layout["home"] / "plugins")}
    entry = report["hooks"]["entries"][0]
    assert entry["enabled"]["value"] is False
    assert entry["discovered"]["value"] is True
    assert entry["trusted"]["value"] == entry["fired"]["value"] == "unknown"


def test_no_safe_descriptor_flags_is_unknown(layout, capsys, monkeypatch):
    monkeypatch.delattr(io.os, "O_NOFOLLOW")
    rc, report = run(layout, capsys)
    assert rc == 2 and report["installation"]["reason"] == "safe_file_access_unavailable"


def test_source_url_userinfo_is_not_captured_or_echoed(layout, capsys):
    git_source(layout)
    layout["config"].write_text(layout["config"].read_text().replace('https://example.invalid/sample.git', 'https://private-user@example.invalid/sample.git'))
    output = layout["tmp"] / "should-not-exist.json"
    rc, report = run(layout, capsys, "--capture-snapshot", output)
    assert rc == 2 and report["installation"]["reason"] == "source_url_contains_userinfo"
    assert not output.exists()
    assert "private-user" not in json.dumps(report)


def test_private_store_reports_canonical_root(layout, capsys):
    rc, report = run(layout, capsys)
    assert rc == 0
    assert report["store"] == {"store_root": str(layout["home"] / "plugins"),
                                "store_shared": False, "link_source": None}


@pytest.mark.parametrize("mode", [0o777, 0o775])
def test_shared_store_group_or_other_writable_is_defect(layout, capsys, mode):
    moved = share_store(layout)
    assert run(layout, capsys)[0] == 0
    moved.chmod(mode)
    rc, report = run(layout, capsys)
    assert rc == 1 and report["installation"]["reason"] == "plugin_store_writable_by_others"
    moved.chmod(0o755)
    assert run(layout, capsys)[0] == 0


def test_wrong_uid_store_is_defect(layout, capsys, monkeypatch):
    share_store(layout)
    owner = os.getuid()
    monkeypatch.setattr(io.os, "getuid", lambda: owner + 1)
    rc, report = run(layout, capsys)
    assert rc == 1 and report["installation"]["reason"] == "plugin_store_wrong_owner"


@pytest.mark.parametrize("field,reason,rc", [
    ("type", "plugin_store_not_directory", 1),
    (stat.ST_UID, "plugin_store_wrong_owner", 1),
    (stat.ST_MODE, "plugin_store_writable_by_others", 1),
    (stat.ST_INO, "plugin_store_changed", 2),
])
def test_opened_store_fd_is_independently_validated(layout, capsys, monkeypatch, field, reason, rc):
    moved = share_store(layout)
    target = moved.stat()
    original = os.fstat
    changed = False

    def replaced(fd):
        nonlocal changed
        info = original(fd)
        if (info.st_dev, info.st_ino) == (target.st_dev, target.st_ino):
            changed = True
            values = list(info)
            if field == "type":
                values[stat.ST_MODE] = stat.S_IFREG | 0o600
            else:
                values[field] = values[field] | stat.S_IWOTH if field == stat.ST_MODE else values[field] + 1
            return os.stat_result(values)
        return info

    monkeypatch.setattr(io.os, "fstat", replaced)
    code, report = run(layout, capsys)
    assert changed and code == rc and report["installation"]["reason"] == reason


@pytest.mark.parametrize("kind", ["dangling", "loop", "permission"])
def test_unavailable_shared_store_is_unknown(layout, capsys, monkeypatch, kind):
    moved = share_store(layout)
    logical = layout["home"] / "plugins"
    if kind in ("dangling", "loop"):
        logical.unlink()
        logical.symlink_to(layout["tmp"] / "missing" if kind == "dangling" else logical, target_is_directory=True)
    else:
        original = io.Reader._open_absolute

        def denied(reader, root, path, directory=False):
            if root == moved:
                raise PermissionError("fixture permission failure")
            return original(reader, root, path, directory)

        monkeypatch.setattr(io.Reader, "_open_absolute", denied)
    rc, report = run(layout, capsys)
    assert rc == 2 and report["installation"]["reason"] == "plugin_store_unavailable"


def test_store_target_must_be_a_directory(layout, capsys):
    moved = share_store(layout)
    shutil.rmtree(moved)
    moved.write_text("not a directory")
    rc, report = run(layout, capsys)
    assert rc == 1 and report["installation"]["reason"] == "plugin_store_not_directory"


def test_plugin_store_option_pins_canonical_scope_without_resolution(layout, capsys):
    moved = share_store(layout)
    assert run(layout, capsys, "--plugin-store", moved)[0] == 0
    for other in (layout["tmp"] / "other", layout["home"] / "plugins", moved / ".." / moved.name):
        rc, report = run(layout, capsys, "--plugin-store", other)
        assert rc == 2 and report["installation"]["reason"] == "plugin_store_scope_mismatch"


@pytest.mark.parametrize("canonical", [True, False])
def test_explicit_shared_cache_version_accepts_logical_or_canonical_spelling(layout, capsys, canonical):
    moved = share_store(layout)
    given = moved / "cache/sample-market/example/5.6.0" if canonical else layout["installed"]
    assert run(layout, capsys, "--installed-path", given)[0] == 0
    assert run(layout, capsys, "--installed-path", given.parent)[0] == 2
    assert run(layout, capsys, "--installed-path", given / "nested")[0] == 2


@pytest.mark.parametrize("relative", ["cache", "cache/sample-market", "cache/sample-market/example",
                                      "cache/sample-market/example/5.6.0", "cache/sample-market/example/5.6.0/.codex-plugin"])
def test_shared_store_descendant_symlink_is_defect(layout, capsys, relative):
    moved = share_store(layout)
    path = moved / relative
    target = layout["tmp"] / "moved-descendant"
    path.rename(target)
    path.symlink_to(target, target_is_directory=True)
    rc, report = run(layout, capsys)
    assert rc == 1 and report["installation"]["reason"] == "unsafe_symlink"


def test_only_logical_store_is_resolved_once(layout, capsys, monkeypatch):
    moved = share_store(layout)
    logical = layout["home"] / "plugins"
    original = Path.resolve
    count = 0

    def resolve_once(path, *args, **kwargs):
        nonlocal count
        if path == logical:
            count += 1
        if path.is_relative_to(moved):
            pytest.fail("canonical store was resolved again")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_once)
    assert run(layout, capsys)[0] == 0
    assert count == 1


def test_store_replacement_between_stat_and_open_fails_closed(layout, capsys, monkeypatch):
    moved = share_store(layout)
    original = io.Reader._open_absolute
    swapped = False

    def replace(reader, root, path, directory=False):
        nonlocal swapped
        if not swapped and root == path == moved:
            swapped = True
            old = layout["tmp"] / "old-store"
            moved.rename(old)
            shutil.copytree(old, moved)
        return original(reader, root, path, directory)

    monkeypatch.setattr(io.Reader, "_open_absolute", replace)
    rc, report = run(layout, capsys)
    assert swapped and rc == 2 and report["installation"]["reason"] == "plugin_store_changed"
    assert report["installation"]["installed_version"] is None


@pytest.mark.parametrize("swap_link", [False, True])
def test_store_replacement_after_pinning_reads_only_original_fd_and_fails_closed(layout, capsys, monkeypatch, swap_link):
    moved = share_store(layout)
    original = io.Reader._open
    swapped = False

    def replace(reader, root, path, directory=False):
        nonlocal swapped
        if not swapped and path == moved / "cache/sample-market/example/5.6.0" / doctor.MANIFEST:
            swapped = True
            if swap_link:
                new = layout["tmp"] / "new-store"
                shutil.copytree(moved, new)
                logical = layout["home"] / "plugins"
                logical.unlink()
                logical.symlink_to(new, target_is_directory=True)
            else:
                old = layout["tmp"] / "old-store"
                moved.rename(old)
                shutil.copytree(old, moved)
                new = moved
            target = new / "cache/sample-market/example/5.6.0" / doctor.MANIFEST
            value = json.loads(target.read_text())
            value["version"] = "9.9.9"
            put_json(target, value)
        return original(reader, root, path, directory)

    monkeypatch.setattr(io.Reader, "_open", replace)
    rc, report = run(layout, capsys)
    assert swapped and rc == 2 and report["installation"]["reason"] == "plugin_store_changed"
    assert report["installation"]["installed_version"] == "5.6.0", "replacement store was read"


def test_shared_snapshot_records_canonical_origins_and_link_provenance(layout, capsys):
    moved = share_store(layout)
    snapshot = capture(layout, capsys)
    value = json.loads(snapshot.read_text())
    assert value["schema"] == 2
    assert value["store"]["store_root"] == str(moved)
    assert value["store"]["logical_path"] == str(layout["home"] / "plugins")
    assert value["store"]["link"]["target"] == str(moved)
    assert value["store"]["root_identity"]["inode"] == moved.stat().st_ino
    origins = value["observations"]
    relation = next(entry for entry in origins if entry["kind"] == "plugin_store")
    assert relation["path"] == str(layout["home"] / "plugins")
    assert relation["sha256"] == hashlib.sha256(json.dumps(value["store"], sort_keys=True).encode()).hexdigest()
    assert any(entry["path"] == str(moved / "cache/sample-market/example/5.6.0" / doctor.MANIFEST) for entry in origins)
    assert run(layout, capsys, "--snapshot", snapshot)[0] == 0


@pytest.mark.parametrize("change", ["retarget", "replace_link", "snapshot_metadata", "old_schema"])
def test_shared_snapshot_relationship_changes_never_green(layout, capsys, monkeypatch, change):
    moved = share_store(layout)
    snapshot = capture(layout, capsys)
    monkeypatch.setattr(doctor, "tomllib", None)
    logical = layout["home"] / "plugins"
    if change in ("retarget", "replace_link"):
        target = moved
        if change == "retarget":
            target = layout["tmp"] / "new-store"
            shutil.copytree(moved, target)
        logical.unlink()
        logical.symlink_to(target, target_is_directory=True)
    else:
        value = json.loads(snapshot.read_text())
        if change == "old_schema":
            value["schema"] = 1
        else:
            value["store"]["link"]["target"] = "/unrelated/store"
        put_json(snapshot, value)
    rc, report = run(layout, capsys, "--snapshot", snapshot)
    assert rc == 2
    assert report["installation"]["reason"] == ("snapshot_schema_unknown" if change == "old_schema" else "snapshot_store_stale")


def test_real_python39_shared_snapshot(layout, capsys):
    python39 = shutil.which("python3.9")
    if not python39:
        pytest.skip("Python 3.9 executable unavailable")
    moved = share_store(layout)
    snapshot = capture(layout, capsys)
    command = [python39, "-B", str(TOOLS / "install_doctor.py"), *args(layout, "--snapshot", snapshot)]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["store"]["store_shared"] is True
    assert report["hooks"]["enabled"]["value"] is False
    assert report["hooks"]["fired"]["value"] == "unknown"
    new = layout["tmp"] / "new-store"
    shutil.copytree(moved, new)
    logical = layout["home"] / "plugins"
    logical.unlink()
    logical.symlink_to(new, target_is_directory=True)
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
    assert result.returncode == 2 and json.loads(result.stdout)["installation"]["reason"] == "snapshot_store_stale"


def test_store_becoming_writable_after_pinning_is_defect(layout, capsys, monkeypatch):
    moved = share_store(layout)
    original = io.Reader._open
    changed = False

    def chmod(reader, root, path, directory=False):
        nonlocal changed
        if not changed and path == moved / "cache/sample-market/example/5.6.0" / doctor.MANIFEST:
            changed = True
            moved.chmod(0o777)
        return original(reader, root, path, directory)

    monkeypatch.setattr(io.Reader, "_open", chmod)
    rc, report = run(layout, capsys)
    assert changed and rc == 1 and report["installation"]["reason"] == "plugin_store_writable_by_others"


def test_shared_capture_in_store_uses_fixed_root_without_resolving_again(layout, capsys, monkeypatch):
    moved = share_store(layout)
    original = Path.resolve

    def checked(path, *args, **kwargs):
        if path.is_relative_to(moved):
            pytest.fail("capture resolved the fixed root")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", checked)
    output = layout["home"] / "plugins" / "snapshot.json"
    assert run(layout, capsys, "--capture-snapshot", output)[0] == 0
    assert (moved / "snapshot.json").is_file()
    assert run(layout, capsys, "--snapshot", output)[0] == 0


def test_store_descriptors_are_closed_on_success_and_failure(layout, capsys, monkeypatch):
    share_store(layout)
    original_open = os.open
    original_close = os.close
    balance = 0

    def opened(*args, **kwargs):
        nonlocal balance
        fd = original_open(*args, **kwargs)
        balance += 1
        return fd

    original_dup = os.dup

    def duplicated(fd):
        nonlocal balance
        result = original_dup(fd)
        balance += 1
        return result

    def closed(fd):
        nonlocal balance
        original_close(fd)
        balance -= 1

    monkeypatch.setattr(io.os, "open", opened)
    monkeypatch.setattr(io.os, "dup", duplicated)
    monkeypatch.setattr(io.os, "close", closed)
    assert run(layout, capsys)[0] == 0
    assert balance == 0
    monkeypatch.setattr(io, "MAX_SECONDS", -1)
    assert run(layout, capsys)[0] == 2
    assert balance == 0


def test_store_link_retarget_during_explicit_capture_fails_closed(layout, capsys, monkeypatch):
    moved = share_store(layout)
    original = doctor.write_snapshot

    def changed(path, value, reader=None):
        original(path, value, reader)
        new = layout["tmp"] / "new-store"
        shutil.copytree(moved, new)
        logical = layout["home"] / "plugins"
        logical.unlink()
        logical.symlink_to(new, target_is_directory=True)

    monkeypatch.setattr(doctor, "write_snapshot", changed)
    rc, report = run(layout, capsys, "--capture-snapshot", layout["tmp"] / "capture.json")
    assert rc == 2 and report["installation"]["reason"] == "plugin_store_changed"


@pytest.mark.parametrize("kind", ["config", "snapshot"])
@pytest.mark.parametrize("link", ["file", "parent", "ancestor"])
def test_user_evidence_symlinks_are_unknown_without_reading_targets(layout, capsys, monkeypatch, kind, link):
    snapshot = capture(layout, capsys)
    path = layout["config"] if kind == "config" else snapshot
    extra = ["--snapshot", snapshot] if kind == "snapshot" else []
    target_info = path.stat()
    if link == "file":
        target = path.with_name("original-" + path.name)
        path.rename(target)
        path.symlink_to(target)
    elif link == "parent":
        parent = path.parent
        # Snapshot and layout share tmp_path; give snapshots a separate parent.
        if kind == "snapshot":
            parent = layout["tmp"] / "evidence"
            parent.mkdir()
            path.rename(parent / path.name)
            extra = ["--snapshot", parent / path.name]
        target = parent.with_name("original-" + parent.name)
        parent.rename(target)
        parent.symlink_to(target, target_is_directory=True)
    else:
        alias = layout["tmp"] / "alias"
        alias.symlink_to(layout["tmp"], target_is_directory=True)
        extra = (["--codex-home", alias / "home"] if kind == "config" else
                 ["--snapshot", alias / snapshot.name])
    original = os.read

    def checked(fd, size):
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) == (target_info.st_dev, target_info.st_ino):
            pytest.fail("symlinked evidence target was read")
        return original(fd, size)

    monkeypatch.setattr(io.os, "read", checked)
    rc, report = run(layout, capsys, *extra)
    assert rc == 2
    assert report["installation"]["status"] == "unknown"
    assert report["installation"]["reason"] == kind + "_symlink_unsupported"
    assert report["installation"].get("hint") == (None if link == "file" else "pass_canonical_path")
    assert str(path) not in json.dumps(report)


@pytest.mark.parametrize("spelling", ["tmp", "var", "home"])
def test_ancestor_symlink_hint_and_canonical_positive_control(layout, capsys, spelling):
    # Model system ancestor spellings without changing or trusting real system links.
    parent = layout["tmp"] / "spellings"
    parent.mkdir()
    alias = parent / spelling
    alias.symlink_to(layout["tmp"], target_is_directory=True)
    rc, report = run(layout, capsys, "--codex-home", alias / "home")
    assert rc == 2 and report["installation"]["reason"] == "config_symlink_unsupported"
    assert report["installation"]["hint"] == "pass_canonical_path"
    assert str(alias) not in json.dumps(report)
    assert str(layout["home"]) not in json.dumps(report)
    assert run(layout, capsys, "--codex-home", (alias / "home").resolve())[0] == 0


@pytest.mark.parametrize("plugin", ["example", "../example@sample-market", "example@market/child", "@sample-market"])
def test_invalid_plugin_id_is_input_error(layout, capsys, plugin):
    rc, report = run(layout, capsys, "--plugin", plugin)
    assert rc == 2 and report["installation"]["reason"] == "invalid_plugin_id"


@pytest.mark.parametrize("kind", ["outside", "traversal", "parent", "nested"])
def test_invalid_installed_selection_is_input_error(layout, capsys, kind):
    path = {"outside": layout["source"] / "plugin",
            "traversal": layout["installed"] / ".." / "5.6.0",
            "parent": layout["installed"].parent,
            "nested": layout["installed"] / "nested"}[kind]
    rc, report = run(layout, capsys, "--installed-path", path)
    assert rc == 2 and report["installation"]["reason"] == "unsafe_installed_path"


@pytest.mark.parametrize("name", ["tokenizer", "tokenizer-example", "auth-helper", "auth-example", "credential-helper", ".env-example", ".envrc", ".environment"])
def test_normal_names_with_sensitive_prefixes_remain_supported(layout, capsys, name):
    # The identifier grammar independently excludes a leading dot.
    plugin_name = "example" if name.startswith(".") else name
    old_plugin = layout["source"] / "plugin"
    old_plugin.rename(layout["source"] / name)
    market_path = layout["source"] / doctor.MARKETPLACE
    value = json.loads(market_path.read_text())
    value["plugins"][0].update(name=plugin_name, source={"source": "local", "path": name})
    put_json(market_path, value)
    for root in (layout["installed"], layout["source"] / name):
        manifest_path = root / doctor.MANIFEST
        value = json.loads(manifest_path.read_text())
        value["name"] = plugin_name
        put_json(manifest_path, value)
    installed = layout["installed"].parent.parent / plugin_name / layout["installed"].name
    if installed != layout["installed"]:
        installed.parent.mkdir()
        layout["installed"].rename(installed)
    layout["config"].write_text(layout["config"].read_text().replace(PLUGIN, plugin_name + "@sample-market"))
    rc, report = run(layout, capsys, "--plugin", plugin_name + "@sample-market")
    assert rc == 0 and report["installation"]["status"] == "match"
    snapshot = layout["tmp"] / (name + ".json")
    assert run(layout, capsys, "--plugin", plugin_name + "@sample-market", "--capture-snapshot", snapshot)[0] == 0
    assert run(layout, capsys, "--plugin", plugin_name + "@sample-market", "--snapshot", snapshot)[0] == 0


@pytest.mark.parametrize("filename", [
    "auth.json", "AUTH.JSON", "credential.json", "credentials.json", "token.json", "tokens.json",
    ".credentials.json", ".CREDENTIALS.JSON", ".env", ".ENV", ".env.local", ".EnV.production",
])
@pytest.mark.parametrize("access", ["snapshot", "capture", "snapshot_parent", "source", "hook", "source_parent"])
def test_authentication_basenames_are_never_opened(layout, capsys, monkeypatch, filename, access):
    original = os.open
    opened = []

    def checked(path, *values, **kwargs):
        assert all(part.casefold() not in {
            "auth.json", "credential.json", "credentials.json", "token.json", "tokens.json", ".credentials.json", ".env"
        } and not part.casefold().startswith(".env.") for part in Path(path).parts)
        opened.append(str(path))
        return original(path, *values, **kwargs)

    monkeypatch.setattr(io.os, "open", checked)
    extra = []
    if access in ("snapshot", "capture", "snapshot_parent"):
        target = layout["tmp"] / filename
        if access == "snapshot_parent":
            target = target / "evidence.json"
        extra = ["--capture-snapshot" if access == "capture" else "--snapshot", target]
    elif access in ("source", "source_parent"):
        target = layout["tmp"] / filename
        if access == "source_parent":
            target = target / "source"
        layout["config"].write_text(layout["config"].read_text().replace(str(layout["source"]), str(target)))
    else:
        path = layout["installed"] / doctor.MANIFEST
        value = json.loads(path.read_text())
        value["hooks"] = "hooks/" + filename
        put_json(path, value)
    rc, report = run(layout, capsys, *extra)
    assert rc == 2
    assert (report["hooks"].get("observation_reason") if access == "hook" else report["installation"]["reason"]) == (
        "forbidden_output" if access == "capture" else "forbidden_file")
    assert opened


@pytest.mark.parametrize("field,value,reason", [
    ("plugin", {"enabled": "invalid"}, "invalid_plugin_enabled"),
    ("hook_states", [], "invalid_hook_state"),
    ("hook_states", {"key": {"enabled": "invalid"}}, "invalid_hook_state"),
    ("hook_states", {"key": {"enabled": True, "configured_trust_hash": []}}, "invalid_hook_state"),
    ("marketplace", [], "snapshot_fields_missing"),
    ("plugin", [], "snapshot_fields_missing"),
])
@pytest.mark.parametrize("native_parser", [True, False])
def test_invalid_selected_snapshot_fields_are_unknown(layout, capsys, monkeypatch, field, value, reason, native_parser):
    snapshot = capture(layout, capsys)
    evidence = json.loads(snapshot.read_text())
    evidence["config"]["selected"][field] = value
    put_json(snapshot, evidence)
    if not native_parser:
        monkeypatch.setattr(doctor, "tomllib", None)
    rc, report = run(layout, capsys, "--snapshot", snapshot)
    assert rc == 2 and report["installation"]["reason"] == reason


@pytest.mark.parametrize("observations", [[None], [{"kind": [], "path": "ignored", "sha256": "ignored"}], ["invalid"]])
def test_malformed_snapshot_observations_precede_installation_diagnosis(layout, capsys, observations):
    snapshot = capture(layout, capsys)
    evidence = json.loads(snapshot.read_text())
    evidence["observations"] = observations
    put_json(snapshot, evidence)
    (layout["installed"] / doctor.MANIFEST).write_text("{")
    rc, report = run(layout, capsys, "--snapshot", snapshot)
    assert rc == 2 and report["installation"]["reason"] == "snapshot_observations_invalid"


def test_duplicate_snapshot_observations_are_rejected_before_installation_diagnosis(layout, capsys):
    snapshot = capture(layout, capsys)
    evidence = json.loads(snapshot.read_text())
    evidence["observations"].append(evidence["observations"][0].copy())
    put_json(snapshot, evidence)
    (layout["installed"] / doctor.MANIFEST).write_text("{")
    rc, report = run(layout, capsys, "--snapshot", snapshot)
    assert rc == 2 and report["installation"]["reason"] == "snapshot_stale"


@pytest.mark.parametrize("mutation,reason", [
    ("syntax", "invalid_config_toml"),
    ("enabled", "invalid_plugin_enabled"),
    ("hook", "invalid_hook_state"),
])
def test_invalid_configuration_is_unknown(layout, capsys, mutation, reason):
    text = layout["config"].read_text()
    if mutation == "syntax":
        text += "[broken"
    elif mutation == "enabled":
        text = text.replace("enabled = true", "enabled = 42")
    else:
        text = text.replace("enabled = false", "enabled = 42")
    layout["config"].write_text(text)
    rc, report = run(layout, capsys)
    assert rc == 2 and report["installation"]["reason"] == reason


@pytest.mark.parametrize("kind", ["relative", "traversal", "symlink", "parent_symlink"])
@pytest.mark.parametrize("source_type", ["local", "git"])
def test_unsupported_source_root_is_unknown(layout, capsys, kind, source_type):
    if source_type == "git":
        git_source(layout)
    given = layout["source"]
    if kind == "relative":
        given = Path("relative-source")
    elif kind == "traversal":
        given = given / ".." / "source"
    elif kind == "symlink":
        given = layout["tmp"] / "source-alias"
        given.symlink_to(layout["source"], target_is_directory=True)
    else:
        alias = layout["tmp"] / "alias"
        alias.symlink_to(layout["tmp"], target_is_directory=True)
        given = alias / "source"
    extra = []
    if source_type == "local":
        layout["config"].write_text(layout["config"].read_text().replace(str(layout["source"]), str(given)))
    else:
        extra = ["--source-checkout", given]
    rc, report = run(layout, capsys, *extra)
    assert rc == 2
    expected = "source_symlink_unsupported" if "symlink" in kind else "unsafe_source_root"
    if source_type == "git" and kind == "relative":
        expected = "source_root_unavailable"
    assert report["installation"]["reason"] == expected
    if "symlink" in kind:
        assert report["installation"].get("hint") == ("pass_canonical_path" if kind == "parent_symlink" else None)
        assert str(given) not in json.dumps(report)


def test_worktree_git_file_is_reported_without_opening_or_following(layout, capsys, monkeypatch):
    path = git_source(layout)
    path.unlink()
    path.parent.rmdir()
    path.parent.write_text("gitdir: /outside/never-follow-this\n")
    original = os.open

    def checked(path, *values, **kwargs):
        assert Path(path).name != ".git", "worktree gitdir file was opened"
        return original(path, *values, **kwargs)

    monkeypatch.setattr(io.os, "open", checked)
    rc, report = run(layout, capsys, "--source-checkout", layout["source"])
    assert rc == 2
    assert report["installation"]["reason"] == "source_checkout_is_worktree_unsupported"


@pytest.mark.parametrize("kind", ["file", "fifo", "missing"])
@pytest.mark.parametrize("source_type", ["local", "git"])
def test_unavailable_source_root_has_specific_unknown_reason(layout, capsys, kind, source_type):
    if source_type == "git":
        git_source(layout)
    root = layout["source"]
    shutil.rmtree(root)
    if kind == "file":
        root.write_text("unsupported source root")
    elif kind == "fifo":
        os.mkfifo(root)
    extra = ["--source-checkout", root] if source_type == "git" else []
    rc, report = run(layout, capsys, *extra)
    assert rc == 2
    assert report["installation"]["reason"] == ("source_root_unavailable" if kind == "missing" else "source_root_not_directory")


def test_relative_ordinary_git_checkout_remains_supported(layout, capsys, monkeypatch):
    git_source(layout)
    monkeypatch.chdir(layout["tmp"])
    assert run(layout, capsys, "--source-checkout", "source")[0] == 0


@pytest.mark.parametrize("kind", ["fifo", "symlink"])
def test_unsupported_git_metadata_is_not_opened(layout, capsys, monkeypatch, kind):
    path = git_source(layout)
    path.unlink()
    path.parent.rmdir()
    if kind == "fifo":
        os.mkfifo(path.parent)
    else:
        path.parent.symlink_to(layout["tmp"] / "never-read-gitdir")
    original = os.open

    def checked(path, *values, **kwargs):
        assert Path(path).name != ".git"
        return original(path, *values, **kwargs)

    monkeypatch.setattr(io.os, "open", checked)
    rc, report = run(layout, capsys, "--source-checkout", layout["source"])
    assert rc == 2
    assert report["installation"]["reason"] == ("source_checkout_git_layout_unsupported" if kind == "fifo" else "source_symlink_unsupported")


@pytest.mark.parametrize("kind", ["config", "snapshot"])
def test_evidence_parent_swap_after_resolution_is_not_followed(layout, capsys, monkeypatch, kind):
    snapshot = capture(layout, capsys)
    path = layout["config"]
    extra = []
    if kind == "snapshot":
        parent = layout["tmp"] / "evidence"
        parent.mkdir()
        path = parent / "snapshot.json"
        snapshot.rename(path)
        extra = ["--snapshot", path]
    original = io.Reader._open
    swapped = False

    def swap(reader, root, given, directory=False):
        nonlocal swapped
        if not swapped and given == path:
            swapped = True
            target = path.parent.with_name("moved-" + path.parent.name)
            path.parent.rename(target)
            path.parent.symlink_to(target, target_is_directory=True)
        return original(reader, root, given, directory)

    monkeypatch.setattr(io.Reader, "_open", swap)
    rc, report = run(layout, capsys, *extra)
    assert swapped and rc == 2
    assert report["installation"]["reason"] == kind + "_symlink_unsupported"
    assert report["installation"]["hint"] == "pass_canonical_path"
    assert str(path) not in json.dumps(report)


@pytest.mark.parametrize("kind", ["config", "snapshot"])
@pytest.mark.parametrize("file_type", ["fifo", "directory"])
def test_nonregular_user_evidence_is_unknown(layout, capsys, kind, file_type):
    snapshot = capture(layout, capsys)
    path = layout["config"] if kind == "config" else snapshot
    path.unlink()
    if file_type == "fifo":
        os.mkfifo(path)
    else:
        path.mkdir()
    rc, report = run(layout, capsys, *(["--snapshot", snapshot] if kind == "snapshot" else []))
    assert rc == 2 and report["installation"]["reason"] == kind + "_not_regular_file"


@pytest.mark.parametrize("case,expected,reason", [
    ("match", 0, "version_and_identity_match"),
    ("shared", 0, "version_and_identity_match"),
    ("mismatch", 1, "installation_source_version_mismatch"),
    ("store_symlink", 1, "unsafe_symlink"),
    ("invalid_plugin", 2, "invalid_plugin_id"),
    ("installed_path", 2, "unsafe_installed_path"),
    ("config_symlink", 2, "config_symlink_unsupported"),
    ("snapshot_symlink", 2, "snapshot_symlink_unsupported"),
    ("snapshot_parent", 2, "snapshot_symlink_unsupported"),
    ("selected", 2, "invalid_plugin_enabled"),
    ("auth_snapshot", 2, "forbidden_file"),
    ("worktree", 2, "source_checkout_is_worktree_unsupported"),
    ("without_snapshot", 2, "toml_parser_unavailable_use_snapshot"),
])
def test_real_python39_input_and_installation_contract(layout, capsys, case, expected, reason):
    python39 = shutil.which("python3.9")
    if not python39:
        pytest.skip("Python 3.9 executable unavailable")
    if case == "shared":
        share_store(layout)
    elif case == "mismatch":
        path = layout["installed"] / doctor.MANIFEST
        value = json.loads(path.read_text())
        value["version"] = "5.5.1"
        put_json(path, value)
    snapshot = capture(layout, capsys)
    extra = ["--snapshot", snapshot]
    if case in ("config_symlink", "snapshot_symlink"):
        path = layout["config"] if case == "config_symlink" else snapshot
        target = path.with_name("original-" + path.name)
        path.rename(target)
        path.symlink_to(target)
    elif case == "snapshot_parent":
        parent = layout["tmp"] / "evidence"
        parent.mkdir()
        snapshot.rename(parent / snapshot.name)
        alias = layout["tmp"] / "alias"
        alias.symlink_to(parent, target_is_directory=True)
        extra = ["--snapshot", alias / snapshot.name]
    elif case == "invalid_plugin":
        extra += ["--plugin", "invalid"]
    elif case == "installed_path":
        extra += ["--installed-path", layout["source"]]
    elif case == "auth_snapshot":
        extra = ["--snapshot", layout["tmp"] / "auth.json"]
    elif case == "without_snapshot":
        extra = []
    elif case == "store_symlink":
        path = layout["installed"] / ".codex-plugin"
        target = layout["installed"] / "original-manifest"
        path.rename(target)
        path.symlink_to(target, target_is_directory=True)
    elif case in ("selected", "worktree"):
        value = json.loads(snapshot.read_text())
        if case == "selected":
            value["config"]["selected"]["plugin"]["enabled"] = "invalid"
        else:
            git_config = git_source(layout)
            git_config.unlink()
            git_config.parent.rmdir()
            git_config.parent.write_text("gitdir: /outside/not-followed\n")
            value["config"]["sha256"] = hashlib.sha256(layout["config"].read_bytes()).hexdigest()
            value["config"]["selected"] = doctor.select_config(doctor.tomllib.loads(layout["config"].read_text()), PLUGIN, "sample-market")
            extra += ["--source-checkout", layout["source"]]
        put_json(snapshot, value)
    command = [python39, "-B", str(TOOLS / "install_doctor.py"), *args(layout, *extra)]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
    assert result.returncode == expected, result.stdout + result.stderr
    assert json.loads(result.stdout)["installation"]["reason"] == reason


@pytest.mark.parametrize("present,expected,reason", [
    (False, 2, "file_unavailable"), (True, 1, "plugin_manifest_missing"),
])
@pytest.mark.parametrize("shared", [False, True])
def test_selected_installation_directory_absence_is_unknown(layout, capsys, present, expected, reason, shared):
    if shared:
        share_store(layout)
    missing = layout["home"] / "plugins/cache/sample-market/example/9.9.9"
    if present:
        missing.mkdir()
    rc, report = run(layout, capsys, "--installed-path", missing)
    assert (rc, report["installation"]["reason"]) == (expected, reason)
    assert report["decision"] == {"rc": expected, "reason": reason, "layer": "installation"}


@pytest.mark.parametrize("source_type", ["local", "git"])
@pytest.mark.parametrize("mismatch", [False, True])
def test_stale_snapshot_preserves_hook_and_source_observations(layout, capsys, source_type, mismatch):
    extra = []
    if source_type == "git":
        git_source(layout)
        extra = ["--source-checkout", layout["source"]]
    snapshot = layout["tmp"] / "layered-snapshot.json"
    assert run(layout, capsys, *extra, "--capture-snapshot", snapshot)[0] == 0
    (layout["installed"] / "hooks/hooks-codex.json").write_text("{")
    if mismatch:
        path = layout["source"] / "plugin" / doctor.MANIFEST
        value = json.loads(path.read_text())
        value["version"] = "5.5.1"
        put_json(path, value)
    rc, report = run(layout, capsys, *extra, "--snapshot", snapshot)
    assert rc == 1
    observations = {(entry["layer"], entry["rc"], entry["reason"]) for entry in report["observations"]}
    assert ("hooks", 1, "invalid_json") in observations
    assert ("snapshot", 2, "snapshot_stale") in observations
    source_reason = ("source_checkout_unverified_version_mismatch" if source_type == "git"
                     else "installation_source_version_mismatch") if mismatch else "version_and_identity_match"
    source_rc = (2 if source_type == "git" else 1) if mismatch else 0
    assert ("source", source_rc, source_reason) in observations
    assert report["decision"]["rc"] == 1
    expected = "installation_source_version_mismatch" if mismatch and source_type == "local" else "invalid_json"
    assert report["installation"]["reason"] == report["decision"]["reason"] == expected
    if source_type == "git":
        assert report["installation"]["comparison_scope"] == "supplied_checkout"
        assert report["installation"]["remote_freshness"] == "unverified"


@pytest.mark.parametrize("source_type", ["local", "git"])
def test_stale_snapshot_does_not_hide_confirmed_source_defect(layout, capsys, source_type):
    extra = []
    if source_type == "git":
        git_source(layout)
        extra = ["--source-checkout", layout["source"]]
    snapshot = layout["tmp"] / "source-snapshot.json"
    assert run(layout, capsys, *extra, "--capture-snapshot", snapshot)[0] == 0
    path = layout["source"] / "plugin" / doctor.MANIFEST
    value = json.loads(path.read_text())
    value["version"] = "5.5.1"
    put_json(path, value)
    rc, report = run(layout, capsys, *extra, "--snapshot", snapshot)
    assert rc == (2 if source_type == "git" else 1)
    assert any(entry["layer"] == "snapshot" and entry["reason"] == "snapshot_stale" for entry in report["observations"])


@pytest.mark.parametrize("operation", ["open", "stat"])
@pytest.mark.parametrize("error,expected,reason", [
    (errno.ENOENT, 0, "file_unavailable"),
    (errno.EACCES, 2, "file_access_denied"),
    (errno.ENOTDIR, 2, "file_not_directory"),
    (errno.EMFILE, 2, "file_descriptor_limit"),
    (errno.ELOOP, 1, "unsafe_symlink"),
    (errno.EIO, 2, "file_io_error"),
])
def test_hook_walk_io_errors_are_not_absence(layout, capsys, monkeypatch, operation, error, expected, reason):
    original = getattr(io.os, operation)

    def fail(path, *values, **kwargs):
        if not isinstance(path, int) and Path(path).name == "hooks-codex.json":
            raise OSError(error, "private-error-must-not-echo")
        return original(path, *values, **kwargs)

    monkeypatch.setattr(io.os, operation, fail)
    rc, report = run(layout, capsys)
    assert rc == expected
    assert report["hooks"]["observation_reason"] == reason
    assert {"rc": expected, "reason": reason, "layer": "hooks"} in report["observations"]
    assert "private-error" not in json.dumps(report)


@pytest.mark.parametrize("error,reason", [
    (errno.EACCES, "file_access_denied"), (errno.ENOTDIR, "file_not_directory"),
    (errno.EMFILE, "file_descriptor_limit"), (errno.ELOOP, "config_symlink_unsupported"),
])
def test_config_walk_errors_remain_unknown(layout, capsys, monkeypatch, error, reason):
    original = io.os.open

    def fail(path, *values, **kwargs):
        if Path(path).name == "config.toml":
            raise OSError(error, "private-config-error")
        return original(path, *values, **kwargs)

    monkeypatch.setattr(io.os, "open", fail)
    rc, report = run(layout, capsys)
    assert rc == 2 and report["installation"]["reason"] == reason
    assert "hint" not in report["installation"]
    assert "private-config" not in json.dumps(report)


def test_hook_oserror_preserves_local_mismatch_and_json(layout, capsys, monkeypatch):
    path = layout["source"] / "plugin" / doctor.MANIFEST
    value = json.loads(path.read_text())
    value["version"] = "5.5.1"
    put_json(path, value)

    def fail(*unused):
        raise PermissionError(errno.EACCES, "private-hook-error")

    monkeypatch.setattr(doctor, "observe_hooks", fail)
    rc, report = run(layout, capsys)
    assert rc == 1 and report["installation"]["reason"] == "installation_source_version_mismatch"
    assert report["hooks"]["observation_reason"] == "file_access_denied"
    assert "private-hook" not in json.dumps(report)


def test_capture_ancestor_symlink_has_canonical_hint(layout, capsys):
    target = layout["tmp"] / "evidence-directory"
    target.mkdir()
    alias = layout["tmp"] / "evidence-alias"
    alias.symlink_to(target, target_is_directory=True)
    rc, report = run(layout, capsys, "--capture-snapshot", alias / "snapshot.json")
    assert rc == 2 and report["installation"]["reason"] == "snapshot_symlink_unsupported"
    assert report["installation"]["hint"] == "pass_canonical_path"
    assert not (target / "snapshot.json").exists()


@pytest.mark.parametrize("case", ["missing_directory", "git_stale_hook", "local_stale_hook"])
def test_real_python39_review4_contract(layout, capsys, case):
    python39 = shutil.which("python3.9")
    if not python39:
        pytest.skip("Python 3.9 executable unavailable")
    extra = []
    if case == "git_stale_hook":
        git_source(layout)
        extra = ["--source-checkout", layout["source"]]
    snapshot = layout["tmp"] / "python39-snapshot.json"
    assert run(layout, capsys, *extra, "--capture-snapshot", snapshot)[0] == 0
    extra += ["--snapshot", snapshot]
    if case == "missing_directory":
        extra += ["--installed-path", layout["installed"].with_name("9.9.9")]
    else:
        (layout["installed"] / "hooks/hooks-codex.json").write_text("{")
        if case == "local_stale_hook":
            path = layout["source"] / "plugin" / doctor.MANIFEST
            value = json.loads(path.read_text())
            value["version"] = "5.5.1"
            put_json(path, value)
    result = subprocess.run([python39, "-B", str(TOOLS / "install_doctor.py"), *args(layout, *extra)],
                            capture_output=True, text=True, check=False, timeout=10)
    assert result.returncode == (2 if case == "missing_directory" else 1), result.stdout + result.stderr
    report = json.loads(result.stdout)
    expected = {"missing_directory": "file_unavailable", "git_stale_hook": "invalid_json",
                "local_stale_hook": "installation_source_version_mismatch"}[case]
    assert report["installation"]["reason"] == expected
    if case != "missing_directory":
        assert any(entry["reason"] == "snapshot_stale" for entry in report["observations"])
        assert report["hooks"]["observation_reason"] == "invalid_json"
