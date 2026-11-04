from __future__ import annotations

import hashlib
import json
import os
import shutil
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
    assert value["schema"] == 1
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
    assert rc == 1 and report["installation"]["status"] == "defect"


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
    assert rc == 1
    assert "unsafe" in json.dumps(report)


@pytest.mark.parametrize("relative", ["../auth.json", "/auth.json", "hooks/auth.json"])
def test_hook_auth_and_unsafe_paths_rejected(layout, capsys, relative):
    path = layout["installed"] / doctor.MANIFEST
    value = json.loads(path.read_text())
    value["hooks"] = relative
    put_json(path, value)
    rc, report = run(layout, capsys)
    assert rc == 1
    assert report["hooks"]["discovered"]["value"] == "unknown"
    assert report["installation"]["status"] == "match"


def test_multiple_cache_versions_require_explicit_selection(layout, capsys):
    other = layout["installed"].parent / "5.5.1"
    shutil.copytree(layout["installed"], other)
    rc, report = run(layout, capsys)
    assert rc == 2 and report["installation"]["reason"] == "active_cache_ambiguous"
    assert run(layout, capsys, "--installed-path", layout["installed"])[0] == 0
    assert run(layout, capsys, "--installed-path", layout["source"] / "plugin")[0] == 1


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
    path = layout["tmp"] / "git-snapshot.json"
    assert run(layout, capsys, "--source-checkout", layout["source"], "--capture-snapshot", path)[0] == 0
    assert run(layout, capsys, "--source-checkout", layout["source"], "--snapshot", path)[0] == 0


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
    assert run(layout, capsys, "--capture-snapshot", layout["tmp"] / "auth.json")[0] == 1


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
    assert swapped and rc == 2
    assert report["installation"]["reason"] == "file_unavailable"


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
    assert rc == 1 and report["installation"]["reason"] == "forbidden_file"


def test_config_disabled_choice_survives_unsafe_shared_plugin_store(layout, capsys):
    plugins = layout["home"] / "plugins"
    moved = layout["tmp"] / "shared-plugins"
    plugins.rename(moved)
    plugins.symlink_to(moved, target_is_directory=True)
    rc, report = run(layout, capsys)
    assert rc == 1 and report["installation"]["reason"] == "unsafe_symlink"
    entry = report["hooks"]["entries"][0]
    assert entry["enabled"]["value"] is False
    assert entry["discovered"]["value"] == entry["trusted"]["value"] == entry["fired"]["value"] == "unknown"


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
