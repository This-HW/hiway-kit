"""Codex installation/source comparison; explicit snapshot capture writes a new file.

Diagnosis only reads files and never invokes Codex or git.
Exit 0 confirms only installation/source version and identity agreement (for git,
only the supplied checkout; remote freshness is unverified), 1 a confirmed
installed/store defect or local source mismatch, 2 missing/unknown/stale evidence.
Hook state is independent; a confirmed unsafe/invalid hook file also returns 1.
Python 3.11+ captures selected TOML fields; 3.9+ can reuse a verified snapshot.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

# The CLI's default diagnostic must not even create a dependency bytecode cache.
sys.dont_write_bytecode = True

from install_doctor_io import (  # noqa: E402
    ObservationError,
    Reader,
    _relative_path,
    _resolve_in_repo,
    observation_oserror,
    write_snapshot,
)

try:
    import tomllib
except ImportError:
    tomllib = None

SCHEMA = 1
SNAPSHOT_SCHEMA = 2
MANIFEST = ".codex-plugin/plugin.json"
MARKETPLACE = ".agents/plugins/marketplace.json"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
VERSION = re.compile(r"[0-9][A-Za-z0-9.+_-]{0,63}\Z")
EVENTS = {"SessionStart": "session_start", "PostToolUse": "post_tool_use",
          "PreToolUse": "pre_tool_use", "Stop": "stop", "UserPromptSubmit": "user_prompt_submit"}
HOOK_DEFECT_REASONS = frozenset({
    "invalid_json", "invalid_json_object", "invalid_hook_manifest", "unsafe_symlink", "not_regular_file",
    "plugin_store_not_directory", "plugin_store_wrong_owner", "plugin_store_writable_by_others",
})
# Missing hook evidence does not invalidate a successful source comparison.
# Every other unsupported, interrupted, or newly introduced observation is rc2.
HOOK_COMPARISON_INDEPENDENT_REASONS = frozenset({"file_unavailable"})
SOURCE_CHECKOUT_UNVERIFIED_REASONS = frozenset({
    "invalid_json", "invalid_json_object", "not_regular_file", "file_unavailable", "plugin_manifest_missing",
    "plugin_identity_mismatch", "plugin_version_missing", "marketplace_identity_mismatch",
    "marketplace_plugins_missing", "marketplace_plugin_ambiguous",
})


def hook_observation_rc(error: ObservationError) -> int:
    """Classify by observed reason; an unknown reason always falls back to rc2."""
    if error.reason in HOOK_DEFECT_REASONS:
        return 1
    if error.reason in HOOK_COMPARISON_INDEPENDENT_REASONS:
        return 0
    return 2


def state(value="unknown", reason="not_observed") -> dict:
    return {"value": value, "reason": reason}


def initial_report(plugin_id: str) -> dict:
    return {"schema": SCHEMA, "plugin_id": plugin_id,
            "store": {"store_root": None, "store_shared": None, "link_source": None},
            "installation": {"status": "unknown", "reason": "not_observed",
                             "installed_version": None, "source_version": None},
            "hooks": {"discovered": state(), "trusted": state(), "enabled": state(),
                      "fired": state(reason="no_execution_evidence"), "entries": []}}


def configured_hooks(selected: dict, plugin_id: str) -> dict:
    """Retain explicit choices even if discovering the installed cache is unsafe."""
    hooks = initial_report(plugin_id)["hooks"]
    if selected["plugin"]["enabled"] is False:
        hooks["enabled"] = state(False, "plugin_disabled_in_config")
    for key, value in selected["hook_states"].items():
        parts = key.rsplit(":", 3)
        if len(parts) != 4 or not parts[0].startswith(plugin_id + ":hooks/") or parts[1] not in EVENTS.values():
            continue
        if not all(part.isascii() and part.isdecimal() and len(part) < 7 for part in parts[2:]):
            continue
        enabled = value.get("enabled")
        choice = state(enabled, "hook_enabled_in_config") if type(enabled) is bool else state(reason="hook_enabled_not_explicit")
        if selected["plugin"]["enabled"] is False:
            choice = state(False, "plugin_disabled_in_config")
        hooks["entries"].append({"event": next(event for event, native in EVENTS.items() if native == parts[1]),
                                 "group": int(parts[2]), "index": int(parts[3]),
                                 "discovered": state(reason="config_entry_only"),
                                 "trusted": state(reason="native_content_trust_not_verified"),
                                 "enabled": choice, "fired": state(reason="no_execution_evidence"),
                                 "configured_trust_hash_present": value.get("configured_trust_hash") is True})
    return hooks


def select_config(config: dict, plugin_id: str, marketplace: str) -> dict:
    """Allowlist fields only: never retain config text, credentials or trust hashes."""
    try:
        source = config["marketplaces"][marketplace]
        plugin = config["plugins"][plugin_id]
        if not isinstance(source, dict) or not isinstance(plugin, dict):
            raise ObservationError("invalid_config_fields")
        hooks = config.get("hooks", {}).get("state", {})
        if not isinstance(hooks, dict):
            raise ObservationError("invalid_hook_state")
        selected = {}
        for key, value in hooks.items():
            if isinstance(key, str) and key.startswith(plugin_id + ":"):
                if not isinstance(value, dict):
                    raise ObservationError("invalid_hook_state")
                selected[key] = {"enabled": value.get("enabled"),
                                 "configured_trust_hash": bool(value.get("trusted_hash") or value.get("trusted_content_hash"))}
        result = {"marketplace": {"source_type": source.get("source_type"), "source": source.get("source")},
                  "plugin": {"enabled": plugin.get("enabled")}, "hook_states": selected}
        validate_selected(result)
        return result
    except (KeyError, TypeError, AttributeError) as exc:
        raise ObservationError("config_fields_missing") from exc


def validate_selected(value: dict):
    try:
        source = value["marketplace"]
        if source["source_type"] not in ("local", "git") or not isinstance(source["source"], str) or not source["source"]:
            raise ObservationError("source_not_supported")
        if type(value["plugin"]["enabled"]) not in (bool, type(None)):
            raise ObservationError("invalid_plugin_enabled")
        if not isinstance(value["hook_states"], dict):
            raise ObservationError("invalid_hook_state")
        for key, entry in value["hook_states"].items():
            if not isinstance(key, str) or not isinstance(entry, dict) or type(entry.get("enabled")) not in (bool, type(None)):
                raise ObservationError("invalid_hook_state")
            if type(entry.get("configured_trust_hash")) is not bool:
                raise ObservationError("invalid_hook_state")
        if source["source_type"] == "git":
            url = urlsplit(source["source"])
            if url.scheme not in ("https", "ssh") or not url.hostname or url.password or url.query or url.fragment:
                raise ObservationError("unsupported_source_url")
            if url.username and not (url.scheme == "ssh" and url.username == "git"):
                raise ObservationError("source_url_contains_userinfo")
    except (KeyError, TypeError, ValueError) as exc:
        raise ObservationError("snapshot_fields_missing") from exc


def snapshot_observations(snapshot: dict) -> set[tuple[str, str, str]]:
    observations = snapshot.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ObservationError("snapshot_observations_missing")
    if any(not isinstance(entry, dict) or
           any(not isinstance(entry.get(key), str) for key in ("kind", "path", "sha256")) for entry in observations):
        raise ObservationError("snapshot_observations_invalid")
    result = {(entry["kind"], entry["path"], entry["sha256"]) for entry in observations}
    if len(result) != len(observations):
        raise ObservationError("snapshot_stale")
    return result


def snapshot_config(reader: Reader, path: Path, home: Path, plugin_id: str, raw: bytes) -> tuple[dict, dict]:
    try:
        root, relative = reader.user_path(path)
        snapshot = reader.json(root, relative, "snapshot")
        # The input snapshot is not an original observation.
        reader.origins.pop()
        if type(snapshot["schema"]) is not int or snapshot["schema"] != SNAPSHOT_SCHEMA:
            raise ObservationError("snapshot_schema_unknown")
        captured = datetime.fromisoformat(snapshot["captured_at"].replace("Z", "+00:00"))
        if captured.tzinfo is None or captured > datetime.now(timezone.utc):
            raise ObservationError("snapshot_timestamp_invalid")
        if snapshot["plugin_id"] != plugin_id or snapshot["codex_home"] != str(home):
            raise ObservationError("snapshot_target_mismatch")
        origin = snapshot["config"]
        if origin["path"] != str(home / "config.toml"):
            raise ObservationError("snapshot_config_path_mismatch")
        if origin["sha256"] != hashlib.sha256(raw).hexdigest():
            raise ObservationError("snapshot_stale")
        selected = origin["selected"]
        validate_selected(selected)
        snapshot_observations(snapshot)
        return selected, snapshot
    except ObservationError as exc:
        # Malformed user evidence is an inability to diagnose the installation.
        if exc.rc == 1 and exc.reason.startswith("invalid_json"):
            raise ObservationError("snapshot_invalid_json") from exc
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ObservationError("snapshot_invalid") from exc


def load_config(reader: Reader, args, home: Path, plugin_id: str, marketplace: str) -> tuple[dict, dict | None]:
    raw = reader.read(home, "config.toml", "config")
    if args.snapshot:
        reader.bind_store(home, args.plugin_store)
        selected, snapshot = snapshot_config(reader, Path(args.snapshot).absolute(), home, plugin_id, raw)
        # On a parser-capable host, also detect edited selected snapshot fields.
        if tomllib is not None:
            try:
                actual = select_config(tomllib.loads(raw.decode("utf-8")), plugin_id, marketplace)
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise ObservationError("invalid_config_toml") from exc
            if selected != actual:
                raise ObservationError("snapshot_selected_fields_mismatch")
        return selected, snapshot
    if tomllib is None:
        raise ObservationError("toml_parser_unavailable_use_snapshot")
    try:
        return select_config(tomllib.loads(raw.decode("utf-8")), plugin_id, marketplace), None
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ObservationError("invalid_config_toml") from exc


def installed_root(reader: Reader, args, home: Path, name: str, marketplace: str) -> Path:
    store = reader.store_root
    base = f"cache/{marketplace}/{name}"
    if args.installed_path:
        given = Path(args.installed_path).absolute()
        if ".." in given.parts:
            raise ObservationError("unsafe_installed_path")
        # Accept either HOME/plugins/cache/... or the canonical STORE/cache/...
        # spelling, mapping both lexically to the pinned descriptor boundary.
        if given.is_relative_to(home / "plugins"):
            relative = given.relative_to(home / "plugins")
        elif given.is_relative_to(store):
            relative = given.relative_to(store)
        else:
            raise ObservationError("unsafe_installed_path")
        root = reader.path(store, str(relative))
        if root.parent != store / base:
            raise ObservationError("unsafe_installed_path")
        if not stat.S_ISDIR(reader.mode(store, str(relative))):
            raise ObservationError("installed_path_not_directory", 1)
        return root
    versions = reader.directories(store, base)
    if not versions:
        raise ObservationError("installation_missing", 1)
    if len(versions) != 1:
        raise ObservationError("active_cache_ambiguous")
    return reader.path(store, f"{base}/{versions[0]}")


def manifest(reader: Reader, root: Path, name: str, marketplace: str) -> dict:
    try:
        value = reader.json(root, MANIFEST, "plugin_manifest")
    except ObservationError as exc:
        if exc.reason == "file_unavailable" and isinstance(exc.__cause__, FileNotFoundError):
            raise ObservationError("plugin_manifest_missing", 1) from exc
        raise
    if value.get("name") != name or value.get("id", f"{name}@{marketplace}") != f"{name}@{marketplace}":
        raise ObservationError("plugin_identity_mismatch", 1)
    if not isinstance(value.get("version"), str) or not VERSION.fullmatch(value["version"]):
        raise ObservationError("plugin_version_missing", 1)
    return value


def source_root(reader: Reader, args, selected: dict, name: str, marketplace: str) -> Path:
    source = selected["marketplace"]
    if source["source_type"] == "local":
        given = Path(source["source"])
    else:
        if not args.source_checkout:
            raise ObservationError("source_checkout_unavailable")
        given = Path(args.source_checkout).absolute()
    if not given.is_absolute() or ".." in given.parts or not given.name:
        raise ObservationError("unsafe_source_root")
    root = given
    try:
        root_mode = reader.mode(root.parent, root.name)
    except ObservationError as exc:
        if exc.reason == "file_unavailable":
            raise ObservationError("source_root_unavailable") from exc
        raise
    if not stat.S_ISDIR(root_mode):
        raise ObservationError("source_root_not_directory")
    if source["source_type"] == "git":
        # Narrow, offline provenance: an ordinary checkout's local origin URL.
        # Worktrees, includes, and ambiguous origin declarations remain unknown.
        mode = reader.mode(root, ".git")
        if stat.S_ISREG(mode):
            raise ObservationError("source_checkout_is_worktree_unsupported")
        if not stat.S_ISDIR(mode):
            raise ObservationError("source_checkout_git_layout_unsupported")
        raw = reader.read(root, ".git/config", "git_config")
        parser = configparser.RawConfigParser(interpolation=None, strict=True)
        try:
            parser.read_string(raw.decode("utf-8"))
            if any(section.casefold().startswith("include") for section in parser.sections()):
                raise ObservationError("git_provenance_unsupported")
            remote = parser.get('remote "origin"', "url", raw=True)
        except (configparser.Error, UnicodeError) as exc:
            raise ObservationError("git_provenance_unavailable") from exc
        if remote != source["source"]:
            raise ObservationError("git_remote_not_linked_to_source")
    market = reader.json(root, MARKETPLACE, "marketplace_manifest")
    if market.get("name") != marketplace:
        raise ObservationError("marketplace_identity_mismatch", 1)
    plugins = market.get("plugins")
    if not isinstance(plugins, list):
        raise ObservationError("marketplace_plugins_missing", 1)
    entries = [entry for entry in plugins if isinstance(entry, dict) and entry.get("name") == name]
    if len(entries) != 1:
        raise ObservationError("marketplace_plugin_ambiguous")
    entry = entries[0]
    if entry.get("id", f"{name}@{marketplace}") != f"{name}@{marketplace}":
        raise ObservationError("plugin_identity_mismatch", 1)
    descriptor = entry.get("source")
    if not isinstance(descriptor, dict) or descriptor.get("source") != "local" or not isinstance(descriptor.get("path"), str):
        raise ObservationError("marketplace_source_unsupported")
    return _resolve_in_repo(root, descriptor["path"])


def observe_hooks(reader: Reader, root: Path, installed: dict, selected: dict, plugin_id: str) -> dict:
    hooks = initial_report(plugin_id)["hooks"]
    hooks["trusted"] = state(reason="native_content_trust_not_verified")
    if selected["plugin"]["enabled"] is False:
        hooks["enabled"] = state(False, "plugin_disabled_in_config")
    relative = installed.get("hooks")
    if relative is None:
        hooks["discovered"] = state(False, "no_hook_manifest_declared")
        return hooks
    if not isinstance(relative, str):
        raise ObservationError("hook_path_unsupported")
    rel = _relative_path(relative)
    if not rel.parts or rel.parts[0] != "hooks" or rel.suffix != ".json":
        raise ObservationError("unsafe_hook_path")
    data = reader.json(root, relative, "hook_manifest")
    events = data.get("hooks")
    if not isinstance(events, dict):
        raise ObservationError("invalid_hook_manifest", 1)
    for event, groups in events.items():
        if event not in EVENTS or not isinstance(groups, list):
            raise ObservationError("hook_schema_unsupported")
        for group_index, group in enumerate(groups):
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ObservationError("invalid_hook_manifest", 1)
            for index, command in enumerate(group["hooks"]):
                if not isinstance(command, dict) or command.get("type") != "command" or not isinstance(command.get("command"), str) or not command["command"]:
                    raise ObservationError("invalid_hook_manifest", 1)
                key = f"{plugin_id}:{rel.as_posix()}:{EVENTS[event]}:{group_index}:{index}"
                configured = selected["hook_states"].get(key, {})
                enabled = configured.get("enabled")
                enabled_state = state(enabled, "hook_enabled_in_config") if type(enabled) is bool else state(reason="hook_enabled_not_explicit")
                if selected["plugin"]["enabled"] is False:
                    enabled_state = state(False, "plugin_disabled_in_config")
                hooks["entries"].append({"event": event, "group": group_index, "index": index,
                                         "discovered": state(True, "hook_manifest_entry"),
                                         "trusted": state(reason="native_content_trust_not_verified"),
                                         "enabled": enabled_state,
                                         "fired": state(reason="no_execution_evidence"),
                                         "configured_trust_hash_present": configured.get("configured_trust_hash") is True})
    hooks["discovered"] = state(bool(hooks["entries"]), "hook_manifest_entries")
    enabled_values = {entry["enabled"]["value"] for entry in hooks["entries"]}
    if len(enabled_values) == 1 and "unknown" not in enabled_values:
        hooks["enabled"] = state(enabled_values.pop(), "all_hook_entries_explicit")
    return hooks


def verify_snapshot(snapshot: dict, origins: list[dict]):
    # Never open paths supplied by a snapshot. Compare against independently
    # derived allowed files already read through the descriptor-based reader.
    expected = snapshot_observations(snapshot)
    actual = {(entry["kind"], entry["path"], entry["sha256"]) for entry in origins}
    if expected != actual:
        raise ObservationError("snapshot_stale")


def diagnose(args) -> tuple[dict, int]:
    report = initial_report(args.plugin)
    observations = report["observations"] = []
    reader = Reader()
    layer = "config"

    def observe(error: ObservationError, observed_layer: str):
        entry = {"rc": error.rc, "reason": error.reason, "layer": observed_layer}
        if error.hint is not None:
            entry["hint"] = error.hint
        observations.append(entry)

    try:
        parts = args.plugin.split("@")
        if len(parts) != 2 or not all(IDENTIFIER.fullmatch(part) for part in parts):
            raise ObservationError("invalid_plugin_id")
        name, marketplace = parts
        if not shutil.which(args.codex_bin):
            raise ObservationError("codex_executable_unavailable")
        home = Path(args.codex_home).absolute()
        if ".." in home.parts:
            raise ObservationError("unsafe_codex_home")
        selected, snapshot = load_config(reader, args, home, args.plugin, marketplace)
        report["hooks"] = configured_hooks(selected, args.plugin)
        layer = "store"
        store = reader.store or reader.bind_store(home, args.plugin_store)
        if snapshot is not None and snapshot.get("store") != store:
            raise ObservationError("snapshot_store_stale")
        layer = "installation"
        root = installed_root(reader, args, home, name, marketplace)
        installed = manifest(reader, root, name, marketplace)
        report["installation"]["installed_version"] = installed["version"]
        source_type = selected["marketplace"]["source_type"]
        report["installation"]["source_type"] = source_type
        if source_type == "git":
            report["installation"].update(comparison_scope="supplied_checkout", remote_freshness="unverified")
        # Collect independent layers before making a single final decision.
        try:
            report["hooks"] = observe_hooks(reader, root, installed, selected, args.plugin)
        except (ObservationError, OSError) as exc:
            if isinstance(exc, OSError):
                exc = observation_oserror(exc)
            observe(ObservationError(exc.reason, hook_observation_rc(exc)), "hooks")
            report["hooks"]["discovered"] = state(reason=exc.reason)
            report["hooks"]["observation_reason"] = exc.reason
        source_error = None
        try:
            source = source_root(reader, args, selected, name, marketplace)
            configured = manifest(reader, source, name, marketplace)
        except ObservationError as exc:
            if exc.reason == "unsafe_symlink":
                source_error = ObservationError("source_symlink_unsupported", hint=exc.hint)
            elif source_type == "git" and exc.reason in SOURCE_CHECKOUT_UNVERIFIED_REASONS:
                source_error = ObservationError("source_checkout_unverified_" + exc.reason)
            else:
                source_error = exc
        except (OSError, RuntimeError, ValueError):
            # Preserve confirmed installed risks without echoing source inputs.
            source_error = ObservationError("observation_unavailable")
        else:
            report["installation"]["source_version"] = configured["version"]
            if installed["version"] != configured["version"]:
                source_error = (ObservationError("source_checkout_unverified_version_mismatch") if source_type == "git"
                                else ObservationError("installation_source_version_mismatch", 1))
        if source_error is not None:
            observe(source_error, "source")
        else:
            observe(ObservationError("version_and_identity_match", 0), "source")
        # Recheck installed/store risks even when source evidence is unavailable.
        layer = "store"
        reader.verify_store()
        if snapshot is not None:
            try:
                verify_snapshot(snapshot, reader.origins)
            except ObservationError as exc:
                observe(exc, "snapshot")
        if args.capture_snapshot and (source_error is None or source_error.reason == "installation_source_version_mismatch"):
            layer = "snapshot"
            if tomllib is None or args.snapshot:
                raise ObservationError("capture_requires_native_toml_parser")
            config_origin = reader.origins[0]
            output = {"schema": SNAPSHOT_SCHEMA, "captured_at": datetime.now(timezone.utc).isoformat(),
                      "plugin_id": args.plugin, "codex_home": str(home),
                      "config": {"path": config_origin["path"], "sha256": config_origin["sha256"], "selected": selected},
                      "store": store, "observations": reader.origins}
            write_snapshot(Path(args.capture_snapshot).absolute(), output, reader)
            layer = "store"
            reader.verify_store()
    except ObservationError as exc:
        observe(exc, layer)
    except (OSError, RuntimeError, ValueError) as exc:
        # Never echo exception text: it can contain config or credential values.
        del exc
        observe(ObservationError("observation_unavailable"), layer)
    finally:
        if reader.store is not None:
            report["store"] = {key: reader.store[key] for key in ("store_root", "store_shared", "link_source")}
        reader.close()
    # Confirmed defects outrank unknown evidence, which outranks a match.
    # At the same severity, keep the installation/source diagnosis ahead of hooks.
    priority = {1: 0, 2: 1, 0: 2}
    winner = min(observations, key=lambda entry: (priority[entry["rc"]], entry["layer"] == "hooks"))
    report["decision"] = {key: winner[key] for key in ("rc", "reason", "layer")}
    installation = [entry for entry in observations if entry["layer"] != "hooks"]
    summary = min(installation, key=lambda entry: priority[entry["rc"]])
    # Keep the established match+independent-hook status; promote confirmed hook
    # defects when the installation/source evidence would otherwise be unknown.
    if summary["rc"] == 2 and winner["rc"] == 1:
        summary = winner
    report["installation"].update(status={0: "match", 1: "defect", 2: "unknown"}[summary["rc"]], reason=summary["reason"])
    if "hint" in summary:
        report["installation"]["hint"] = summary["hint"]
    return report, winner["rc"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME"), help="Explicit home (or CODEX_HOME); no implicit user home")
    parser.add_argument("--plugin", required=True, help="Plugin name@marketplace")
    parser.add_argument("--source-checkout", help="Existing ordinary git checkout; origin must exactly match configured source URL")
    parser.add_argument("--plugin-store", help="Require this canonical store root to equal the one resolved from CODEX_HOME/plugins")
    parser.add_argument("--installed-path", help="Explicit direct cache version directory under logical HOME/plugins or canonical store root")
    parser.add_argument("--codex-bin", default="codex", help="Executable to locate, never executed")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--snapshot", help="Verified JSON config snapshot (required for Python 3.9/3.10)")
    output.add_argument("--capture-snapshot", help="Explicit new JSON output file (Python 3.11+)")
    args = parser.parse_args(argv)
    if not args.codex_home:
        parser.error("--codex-home or CODEX_HOME is required")
    result, rc = diagnose(args)
    print(json.dumps(result, ensure_ascii=True))
    return rc


if __name__ == "__main__":
    sys.exit(main())
