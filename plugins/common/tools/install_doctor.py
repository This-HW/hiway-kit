"""Read-only Codex installation/source comparison; never invokes Codex or git.

Exit 0 confirms only installation/source version and identity agreement, 1 a
confirmed defect, 2 missing/unknown/stale evidence. Hook state is independent.
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
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

# The CLI's default diagnostic must not even create a dependency bytecode cache.
sys.dont_write_bytecode = True

from install_doctor_io import (  # noqa: E402
    ObservationError,
    Reader,
    _resolve_in_repo,
    write_snapshot,
)

try:
    import tomllib
except ImportError:
    tomllib = None

SCHEMA = 1
MANIFEST = ".codex-plugin/plugin.json"
MARKETPLACE = ".agents/plugins/marketplace.json"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
VERSION = re.compile(r"[0-9][A-Za-z0-9.+_-]{0,63}\Z")
EVENTS = {"SessionStart": "session_start", "PostToolUse": "post_tool_use",
          "PreToolUse": "pre_tool_use", "Stop": "stop", "UserPromptSubmit": "user_prompt_submit"}


def state(value="unknown", reason="not_observed") -> dict:
    return {"value": value, "reason": reason}


def initial_report(plugin_id: str) -> dict:
    return {"schema": SCHEMA, "plugin_id": plugin_id,
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
            raise ObservationError("invalid_config_fields", 1)
        hooks = config.get("hooks", {}).get("state", {})
        if not isinstance(hooks, dict):
            raise ObservationError("invalid_hook_state", 1)
        selected = {}
        for key, value in hooks.items():
            if isinstance(key, str) and key.startswith(plugin_id + ":"):
                if not isinstance(value, dict):
                    raise ObservationError("invalid_hook_state", 1)
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
            raise ObservationError("invalid_plugin_enabled", 1)
        if not isinstance(value["hook_states"], dict):
            raise ObservationError("invalid_hook_state", 1)
        for key, entry in value["hook_states"].items():
            if not isinstance(key, str) or not isinstance(entry, dict) or type(entry.get("enabled")) not in (bool, type(None)):
                raise ObservationError("invalid_hook_state", 1)
        if source["source_type"] == "git":
            url = urlsplit(source["source"])
            if url.scheme not in ("https", "ssh") or not url.hostname or url.password or url.query or url.fragment:
                raise ObservationError("unsupported_source_url")
            if url.username and not (url.scheme == "ssh" and url.username == "git"):
                raise ObservationError("source_url_contains_userinfo")
    except (KeyError, TypeError, ValueError) as exc:
        raise ObservationError("snapshot_fields_missing") from exc


def snapshot_config(reader: Reader, path: Path, home: Path, plugin_id: str, raw: bytes) -> tuple[dict, dict]:
    try:
        snapshot = reader.json(path.parent.resolve(), path.name, "snapshot")
        # The input snapshot is not an original observation.
        reader.origins.pop()
        if type(snapshot["schema"]) is not int or snapshot["schema"] != SCHEMA:
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
        if not isinstance(snapshot["observations"], list) or not snapshot["observations"]:
            raise ObservationError("snapshot_observations_missing")
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
        selected, snapshot = snapshot_config(reader, Path(args.snapshot).absolute(), home, plugin_id, raw)
        # On a parser-capable host, also detect edited selected snapshot fields.
        if tomllib is not None:
            try:
                actual = select_config(tomllib.loads(raw.decode("utf-8")), plugin_id, marketplace)
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise ObservationError("invalid_config_toml", 1) from exc
            if selected != actual:
                raise ObservationError("snapshot_selected_fields_mismatch")
        return selected, snapshot
    if tomllib is None:
        raise ObservationError("toml_parser_unavailable_use_snapshot")
    try:
        return select_config(tomllib.loads(raw.decode("utf-8")), plugin_id, marketplace), None
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ObservationError("invalid_config_toml", 1) from exc


def installed_root(reader: Reader, args, home: Path, name: str, marketplace: str) -> Path:
    base = f"plugins/cache/{marketplace}/{name}"
    if args.installed_path:
        given = Path(args.installed_path).absolute()
        try:
            relative = str(given.relative_to(home))
        except ValueError as exc:
            raise ObservationError("unsafe_installed_path", 1) from exc
        root = _resolve_in_repo(home, relative)
        if root.parent != home / base:
            raise ObservationError("unsafe_installed_path", 1)
        return root
    versions = reader.directories(home, base)
    if not versions:
        raise ObservationError("installation_missing", 1)
    if len(versions) != 1:
        raise ObservationError("active_cache_ambiguous")
    return _resolve_in_repo(home, f"{base}/{versions[0]}")


def manifest(reader: Reader, root: Path, name: str, marketplace: str) -> dict:
    value = reader.json(root, MANIFEST, "plugin_manifest")
    if value.get("name") != name or value.get("id", f"{name}@{marketplace}") != f"{name}@{marketplace}":
        raise ObservationError("plugin_identity_mismatch", 1)
    if not isinstance(value.get("version"), str) or not VERSION.fullmatch(value["version"]):
        raise ObservationError("plugin_version_missing", 1)
    return value


def source_root(reader: Reader, args, selected: dict, name: str, marketplace: str) -> Path:
    source = selected["marketplace"]
    if source["source_type"] == "local":
        given = Path(source["source"])
        if not given.is_absolute() or ".." in given.parts or given.is_symlink():
            raise ObservationError("unsafe_source_root", 1)
        root = given.resolve()
    else:
        if not args.source_checkout:
            raise ObservationError("source_checkout_unavailable")
        given = Path(args.source_checkout).absolute()
        if given.is_symlink():
            raise ObservationError("unsafe_source_root", 1)
        root = given.resolve()
        # Narrow, offline provenance: an ordinary checkout's local origin URL.
        # Worktrees, includes, and ambiguous origin declarations remain unknown.
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
    rel = Path(relative)
    if not rel.parts or rel.parts[0] != "hooks" or rel.suffix != ".json":
        raise ObservationError("unsafe_hook_path", 1)
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
    try:
        expected = {(entry["kind"], entry["path"], entry["sha256"]) for entry in snapshot["observations"]}
        actual = {(entry["kind"], entry["path"], entry["sha256"]) for entry in origins}
    except (KeyError, TypeError) as exc:
        raise ObservationError("snapshot_observations_invalid") from exc
    if expected != actual or len(expected) != len(snapshot["observations"]):
        raise ObservationError("snapshot_stale")


def diagnose(args) -> tuple[dict, int]:
    report = initial_report(args.plugin)
    reader = Reader()
    try:
        parts = args.plugin.split("@")
        if len(parts) != 2 or not all(IDENTIFIER.fullmatch(part) for part in parts):
            raise ObservationError("invalid_plugin_id", 1)
        name, marketplace = parts
        if not shutil.which(args.codex_bin):
            raise ObservationError("codex_executable_unavailable")
        home = Path(args.codex_home).resolve(strict=True)
        selected, snapshot = load_config(reader, args, home, args.plugin, marketplace)
        report["hooks"] = configured_hooks(selected, args.plugin)
        root = installed_root(reader, args, home, name, marketplace)
        installed = manifest(reader, root, name, marketplace)
        report["installation"]["installed_version"] = installed["version"]
        # Hook observation errors must not erase a confirmed version mismatch.
        hook_error = None
        try:
            report["hooks"] = observe_hooks(reader, root, installed, selected, args.plugin)
        except ObservationError as exc:
            hook_error = exc
            report["hooks"]["discovered"] = state(reason=exc.reason)
        source = source_root(reader, args, selected, name, marketplace)
        configured = manifest(reader, source, name, marketplace)
        report["installation"]["source_version"] = configured["version"]
        report["installation"]["source_type"] = selected["marketplace"]["source_type"]
        if snapshot is not None:
            verify_snapshot(snapshot, reader.origins)
        if args.capture_snapshot:
            if tomllib is None or args.snapshot:
                raise ObservationError("capture_requires_native_toml_parser")
            config_origin = reader.origins[0]
            output = {"schema": SCHEMA, "captured_at": datetime.now(timezone.utc).isoformat(),
                      "plugin_id": args.plugin, "codex_home": str(home),
                      "config": {"path": config_origin["path"], "sha256": config_origin["sha256"], "selected": selected},
                      "observations": reader.origins}
            write_snapshot(Path(args.capture_snapshot).absolute(), output)
        if installed["version"] != configured["version"]:
            raise ObservationError("installation_source_version_mismatch", 1)
        report["installation"].update(status="match", reason="version_and_identity_match")
        if hook_error is not None:
            report["hooks"]["observation_reason"] = hook_error.reason
            # Missing hook runtime evidence does not invalidate an installation
            # comparison. A confirmed unsafe/invalid hook file is still a defect.
            return report, 1 if hook_error.rc == 1 else 0
        return report, 0
    except ObservationError as exc:
        report["installation"].update(status="defect" if exc.rc == 1 else "unknown", reason=exc.reason)
        return report, exc.rc
    except (OSError, RuntimeError, ValueError) as exc:
        # Never echo exception text: it can contain config or credential values.
        del exc
        report["installation"].update(status="unknown", reason="observation_unavailable")
        return report, 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME"), help="Explicit home (or CODEX_HOME); no implicit user home")
    parser.add_argument("--plugin", required=True, help="Plugin name@marketplace")
    parser.add_argument("--source-checkout", help="Existing ordinary git checkout; origin must exactly match configured source URL")
    parser.add_argument("--installed-path", help="Explicit cache version directory when several versions exist")
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
