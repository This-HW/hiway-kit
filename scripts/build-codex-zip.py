#!/usr/bin/env python3
"""build-codex-zip.py — OpenAI 플러그인 디렉토리(Skills only) 제출 ZIP 을 만들고 포털 규칙으로 검사한다.

## 왜 있는가

Claude 디렉토리는 GitHub webhook 으로 `main` push 를 스캔하지만, OpenAI 포털은 **버전마다
ZIP 을 손으로 올린다.** 올린 뒤에야 오류를 보면 한 번에 한 개씩 고치게 된다. 이 스크립트는
포털의 문서화된 오류 코드(developers.openai.com/plugins/deploy/submission-errors)를 로컬에서
먼저 대조한다.

실측 계기 `[confirmed 2026-09-28]`: 생성된 `.codex-plugin/plugin.json` 의 `interface.category`
가 `"Coding"` 이었다 — 포털 허용 목록에 없는 값이라 업로드하면 `plugin_category_unknown` 으로
막혔을 것이다. 로컬 Codex 설치(`codex plugin add`)는 이 값을 검사하지 않아 아무도 몰랐다.

## 무엇을 만드는가

`git ls-files` 가 추적하는 플러그인 루트(`packaging/targets.json` 의 `source.pluginRoot`)의
파일을 `<name>/` 한 폴더 아래에 담는다(`plugin_root_has_siblings` 회피). **루트 `plugin.json`
은 뺀다** — Antigravity 매니페스트라 `version`·`author` 가 없고, 포털은 루트 `plugin.json`
을 `.codex-plugin/plugin.json` 과 나란히 매니페스트 후보로 읽는다(어느 쪽을 우선하는지
문서에 없다). 모르는 우선순위에 맡기지 않는다.

## 검사 조건 (한 문장)

**ZIP 을 만들 때마다(`--check` 포함) 포털 오류 코드 중 로컬에서 판정 가능한 것 전부를 대조하고,
하나라도 걸리면 exit 1.** 판정하지 못한 것(예: 블록 스칼라 description)도 오류로 센다 —
검사하지 못한 것을 통과로 세지 않는다. 포털 서버측 검사(스킬 안전 스캔 등)는 여기서
볼 수 없다.

사용:
  scripts/build-codex-zip.py --check             # 작업 트리 기준으로 만들어 검사만(파일을 남기지 않음)
  scripts/build-codex-zip.py --out <path.zip>    # 제출용 ZIP 기록(플러그인 루트가 깨끗해야 함)
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: 포털이 받는 `interface.category` 값 (submission-errors 의 `plugin_category_unknown`).
PORTAL_CATEGORIES = frozenset(
    {
        "Productivity",
        "Creativity",
        "Developer Tools",
        "Business & Operations",
        "Data & Analytics",
        "Communication",
        "Education & Research",
        "Security",
        "Finance",
        "Healthcare",
        "Travel",
        "Entertainment",
        "Other",
    }
)

#: 제출 ZIP 에서 빼는 플러그인 루트 기준 경로와 사유.
EXCLUDED = {
    "plugin.json": "Antigravity 매니페스트 — version·author 가 없고 포털이 매니페스트 후보로 읽는다",
}
#: 제출 ZIP 에서 **디렉토리째** 빼는 플러그인 루트 기준 접두사와 사유.
#:
#: 2026-09-30 실측: 포털 메타데이터 검사가 "Plugins containing hooks cannot be submitted" 로
#: 막았다. 훅 **선언**(json 두 개·매니페스트 `hooks`)만 빼도 막혔고, `hooks/` 디렉토리를
#: 통째로 빼야 통과했다 — 포털은 디렉토리의 존재를 훅으로 본다. 그래서 스킬이 부르는
#: 도구(checklist·feedback_ledger·export_harness)는 v5.2.0 에 `tools/` 로 옮겼고, 제출본은
#: `hooks/` 를 전부 뺀다. Codex 로컬 설치(마켓플레이스)는 훅을 그대로 받는다.
EXCLUDED_DIRS = {
    "hooks/": "훅 디렉토리 — 디렉토리 제출 금지(포털 메타데이터 검사가 존재 자체를 거부)",
    "evals/": "`claude plugin eval` 스위트(Claude Code 전용) — 제출본 크기·심사 표면에 싣지 않는다",
}
#: 제출본 매니페스트에서 빼는 필드와 사유 — EXCLUDED_DIRS 와 같은 이유(훅 선언).
MANIFEST_DROPPED = {"hooks": "훅 선언 — 디렉토리 제출 금지"}

MAX_ENTRIES = 5000
MAX_UNCOMPRESSED = 512 * 2**20
MAX_DEPTH = 20
FINAL_LISTING_LIMIT = 30  # displayName·shortDescription 최종 제출 한도
LONG_DESCRIPTION_LIMIT = 4000  # interface.longDescription (plugin_long_description_too_long)
SKILL_DESCRIPTION_LIMIT = 1024
SKILL_IDENTITY_LIMIT = 64  # `<plugin>:<skill>`
EXCLUDED_CONFIG = frozenset({".mcp.json", "mcp.json", ".app.json"})

_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")


def _load_build_targets():
    """경로 봉쇄·정책 로딩은 build-targets.py 의 것을 그대로 쓴다(관례를 새로 만들지 않는다)."""
    spec = importlib.util.spec_from_file_location(
        "_ckkit_build_targets", REPO_ROOT / "scripts" / "build-targets.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(spec.name, None)
    return mod


def plugin_root(repo_root: Path) -> tuple[Path, str]:
    """정책의 pluginRoot 를 레포 안으로 봉쇄해 (절대경로, 레포 기준 상대경로) 로 돌려준다."""
    bt = _load_build_targets()
    policy = bt.load_policy(repo_root / "packaging" / "targets.json")
    rel = policy["source"]["pluginRoot"]
    resolved, error = bt._resolve_in_repo(repo_root, rel)
    if error:
        raise SystemExit(f"[build-codex-zip] ✗ pluginRoot {error}")
    return resolved, resolved.relative_to(repo_root.resolve()).as_posix()


def tracked_plugin_files(repo_root: Path, root_rel: str) -> list[str]:
    """플러그인 루트 기준 추적 파일 목록. git 실패는 exit 1(빈 목록으로 위장하지 않는다)."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", root_rel],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"[build-codex-zip] ✗ git ls-files 실패: {proc.stderr.decode(errors='replace').strip()}"
        )
    prefix = root_rel.rstrip("/") + "/"
    return sorted(
        p[len(prefix) :]
        for p in proc.stdout.decode().split("\0")
        if p.startswith(prefix)
    )


def build_zip(repo_root: Path, out: Path) -> str:
    """ZIP 을 `out` 에 기록하고 최상위 폴더 이름을 돌려준다."""
    root, root_rel = plugin_root(repo_root)
    manifest = json.loads(
        (root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    top = manifest["name"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in tracked_plugin_files(repo_root, root_rel):
            if rel in EXCLUDED or rel.startswith(tuple(EXCLUDED_DIRS)):
                continue
            if rel == ".codex-plugin/plugin.json":
                submitted = {k: v for k, v in manifest.items() if k not in MANIFEST_DROPPED}
                zf.writestr(f"{top}/{rel}", json.dumps(submitted, indent=2, ensure_ascii=False) + "\n")
                continue
            src = root / rel
            if src.is_symlink() or not src.is_file():
                raise SystemExit(
                    f"[build-codex-zip] ✗ 일반 파일이 아니다(포털은 거부한다): {rel}"
                )
            zf.write(src, f"{top}/{rel}")
    return top


def _frontmatter(text: str) -> dict[str, str] | None:
    """최상위 `key: 값` 만 읽는다. 블록 스칼라(`|`, `>`)·여러 줄 값은 '판정 불가' 표식을 남긴다."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        m = _KEY_RE.match(line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if value[:1] in ("|", ">") or value == "":
                out[key] = "\0unparsed"
            elif len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                out[key] = value[1:-1]
            else:
                out[key] = value
        elif line[:1] in (" ", "\t") and out:
            out[list(out)[-1]] = "\0unparsed"
    return None


def validate(zip_bytes: bytes) -> tuple[list[str], list[str]]:
    """ZIP 을 포털 규칙으로 대조해 (errors, warnings) 를 돌려준다."""
    errors: list[str] = []
    warnings: list[str] = []
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    infos = zf.infolist()
    names = [i.filename for i in infos]
    if not names:
        return ["archive_empty"], warnings
    if len(names) > MAX_ENTRIES:
        errors.append("archive_too_many_entries")
    if sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
        errors.append("archive_uncompressed_too_large")

    seen: set[str] = set()
    for info in infos:
        n = info.filename
        key = unicodedata.normalize("NFC", n).lower()
        if key in seen:
            errors.append(f"archive_member_path_normalization_collision: {n}")
        seen.add(key)
        segs = n.rstrip("/").split("/")
        if len(segs) > MAX_DEPTH:
            errors.append(f"archive_member_path_too_deep: {n}")
        if "\\" in n or n.startswith("/") or ".." in segs or "" in segs:
            errors.append(f"archive_member_path_unsafe: {n}")
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            errors.append(f"archive_member_type_unsupported: {n}")

    tops = {n.split("/")[0] for n in names}
    if len(tops) != 1 or any("/" not in n for n in names if not n.endswith("/")):
        return [*errors, f"plugin_root_has_siblings: {sorted(tops)[:5]}"], warnings
    root = f"{tops.pop()}/"
    files = {n[len(root) :]: n for n in names if not n.endswith("/")}

    if "plugin.json" in files:
        errors.append("root plugin.json present — portal may read it as the manifest")
    if ".codex-plugin/plugin.json" not in files:
        return [*errors, "plugin_manifest_missing: .codex-plugin/plugin.json"], warnings
    try:
        m = json.loads(zf.read(files[".codex-plugin/plugin.json"]))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [*errors, f"plugin_manifest_json_malformed: {exc}"], warnings
    for field in ("name", "version", "description"):
        if not m.get(field):
            errors.append(f"plugin_{field}_missing")
    if not (m.get("author") or {}).get("name"):
        errors.append("plugin_developer_missing: author.name")
    if len(m.get("description", "")) > 1024:
        errors.append("plugin_description_too_long")
    if m.get("mcpServers") or m.get("apps"):
        errors.append("mcp_configuration_excluded/app_configuration_excluded")
    if m.get("hooks"):
        errors.append("plugin_hooks_not_allowed: manifest declares hooks")

    iface = m.get("interface") or {}
    for field in ("displayName", "shortDescription"):
        value = iface.get(field, "")
        if not value:
            errors.append(f"interface.{field} missing")
        elif len(value) > FINAL_LISTING_LIMIT:
            errors.append(
                f"interface.{field} > {FINAL_LISTING_LIMIT} chars (final submission)"
            )
    # 2026-09-30 실측: 포털이 이것 하나로 업로드를 거부했다("Invalid plugin package
    # `interface.longDescription` is required …"). 오류 목록에 있던 코드인데 이 검사가 빠져 있었다.
    long_description = iface.get("longDescription", "")
    if not isinstance(long_description, str) or not long_description.strip():
        errors.append("plugin_long_description_empty: interface.longDescription")
    elif len(long_description) > LONG_DESCRIPTION_LIMIT:
        errors.append(f"plugin_long_description_too_long (> {LONG_DESCRIPTION_LIMIT})")
    # 2026-09-30 실측: 포털 메타데이터 검사가 "Make sure your privacy policy website is accessible" 로 막았다.
    # 여기서는 형식(https URL)만 본다 — 실제로 열리는지는 포털이 판정한다.
    privacy = iface.get("privacyPolicyURL", "")
    if not isinstance(privacy, str) or not privacy.startswith("https://"):
        errors.append("plugin_privacy_policy_url: interface.privacyPolicyURL must be an https URL")
    if not iface.get("developerName"):
        errors.append("plugin_developer_name_empty")
    elif iface["developerName"] != (m.get("author") or {}).get("name"):
        warnings.append(
            "developer_name_defaulted: author.name != interface.developerName"
        )
    if iface.get("category") and iface["category"] not in PORTAL_CATEGORIES:
        errors.append(f"plugin_category_unknown: {iface['category']!r}")
    for cap in iface.get("capabilities", []):
        if not cap or len(cap) > 120:
            errors.append(f"plugin_capability_invalid: {cap!r}")
    if iface.get("screenshots"):
        errors.append("screenshot_configuration_excluded")
    for field in ("logo", "composerIcon"):
        value = iface.get(field)
        if not value:
            warnings.append(
                f"interface.{field} absent — the portal form must supply the icon"
            )
        elif not value.startswith("./"):
            errors.append(f"branding_asset_path_missing_root_prefix: {field}")
        elif value[2:] not in files:
            errors.append(f"declared_asset_file_missing: {field} → {value}")

    for rel in files:
        if rel in EXCLUDED_CONFIG:
            errors.append(f"excluded config present: {rel}")
        if rel.startswith(tuple(EXCLUDED_DIRS)):
            errors.append(f"plugin_hooks_not_allowed: {rel}")

    skills: set[str] = set()
    for rel, full in sorted(files.items()):
        parts = rel.split("/")
        if parts[0] != "skills" or len(parts) < 2:
            continue
        if len(parts) == 2:
            warnings.append(f"skill_file_ignored: {rel}")
            continue
        if parts[-1] != "SKILL.md" or len(parts) != 3:
            continue
        if parts[1].startswith("."):
            errors.append(f"skill_directory_hidden: {rel}")
        try:
            text = zf.read(full).decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"skill_manifest_invalid_utf8: {rel}")
            continue
        fm = _frontmatter(text)
        if fm is None:
            errors.append(f"skill_frontmatter_missing/unclosed: {rel}")
            continue
        name, desc = fm.get("name", ""), fm.get("description", "")
        for field, value in (("name", name), ("description", desc)):
            if value == "\0unparsed":
                errors.append(
                    f"skill_{field} not checkable locally (block/multi-line scalar): {rel}"
                )
            elif not value:
                errors.append(f"skill_{field}_missing: {rel}")
        if desc != "\0unparsed" and len(desc) > SKILL_DESCRIPTION_LIMIT:
            errors.append(f"skill_description_too_long ({len(desc)}): {rel}")
        if name and name != "\0unparsed":
            if len(f"{m.get('name', '')}:{name}") > SKILL_IDENTITY_LIMIT:
                errors.append(f"skill_identity_too_long: {name}")
            if name in skills:
                errors.append(f"skill_identity_duplicate: {name}")
            skills.add(name)
        if not text.split("---", 2)[-1].strip():
            errors.append(f"skill_body_empty: {rel}")
    if not skills:
        errors.append("plugin_runtime_surface_missing")
    return errors, warnings


def _plugin_root_dirty(repo_root: Path, root_rel: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain", "--", root_rel],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"[build-codex-zip] ✗ git status 실패: {proc.stderr.strip()}")
    return bool(proc.stdout.strip())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="만들어 검사만 한다(작업 트리 기준, 파일을 남기지 않음)",
    )
    mode.add_argument("--out", type=Path, help="제출용 ZIP 경로")
    ap.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = ap.parse_args(argv)
    repo_root = args.repo_root.resolve()

    if args.out:
        _, root_rel = plugin_root(repo_root)
        if _plugin_root_dirty(repo_root, root_rel):
            print(
                f"[build-codex-zip] ✗ {root_rel} 에 커밋되지 않은 변경이 있다 — 제출 ZIP 은 커밋된 상태로만 만든다",
                file=sys.stderr,
            )
            return 1
        out = args.out
    else:
        out = Path(tempfile.mkdtemp()) / "codex-check.zip"

    build_zip(repo_root, out)
    errors, warnings = validate(out.read_bytes())
    for w in warnings:
        print(f"[build-codex-zip] ⚠ {w}")
    for e in errors:
        print(f"[build-codex-zip] ✗ {e}", file=sys.stderr)
    if args.check:
        out.unlink()
        out.parent.rmdir()
    if errors:
        if args.out:
            out.unlink()
        return 1
    print(f"[build-codex-zip] ✓ {'검사 통과' if args.check else f'기록: {out}'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
