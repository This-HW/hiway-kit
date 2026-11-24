#!/usr/bin/env python3
"""Check tracked Archify diagrams and SVG image locations with Python and Git."""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterator
from functools import lru_cache
from html import unescape
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from check_doc_refs import CODE_SPAN_RE, diagram_line_problems, scan_lines
from git_tracked import tracked_files

REPO_ROOT = Path(__file__).resolve().parent.parent
LABEL = "check-archify-diagrams"
DIAGRAM_ROOT = PurePosixPath("docs/architecture/diagrams")
MANIFEST = "ARTIFACTS.sha256"
HASH_RE = re.compile(r"([0-9a-f]{64})  (\S+)")
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SVG_NS = "{http://www.w3.org/2000/svg}"
# Native layouts use internal identifiers, file paths, enums and geometry.
# Everything else is reader text, including fields added by future renderers.
STRUCTURE_KEYS = frozenset(
    {
        "id",
        "from",
        "to",
        "parent",
        "focus",
        "mainPath",
        "lane",
        "kind",
        "type",
        "role",
        "variant",
        "route",
        "fromSide",
        "toSide",
        "mode",
        "direction",
        "diagram_type",
        "quality_profile",
        "locale",
        "animation",
        "visual_preset",
        "path",
        "output",
        "href",
        "parentHref",
        "url",
        "revision",
        "base_revision",
        "provider",
        "link_mode",
        "sha256",
    }
)
FREE_TEXT_KEYS = frozenset({"translations", "payload"})
NODE_FIELDS = ("id", "label", "sublabel")
EDGE_FIELDS = ("id", "from", "to", "label")
# Tree parents are the edge declaration. Workflow and Sequence author explicit edges.
COLLECTIONS = {
    "workflow": ("nodes", "edges"),
    "sequence": ("participants", "messages"),
    "tree": ("nodes", None),
}
DESTINATION = r"<([^>\r\n]+)>|([^\s<>]+)"
IMAGE_ALT = r"(?<!\\)!\[((?:\\.|[^\]\\\n])*)\]"
INLINE_IMAGE_RE = re.compile(
    IMAGE_ALT
    + r"""\(\s*(?:<([^>\r\n]+)>|((?:[^\s<>()]+|\([^()\n]*\))+))(?:[ \t]+(?:"[^"\n]*"|'[^'\n]*'|\([^()\n]*\)))?\s*\)"""
)
REFERENCE_IMAGE_RE = re.compile(IMAGE_ALT + r"(?:[ \t]*\[([^\]\n]*)\])?(?!\()")
DEFINITION_RE = re.compile(rf"(?m)^ {{0,3}}\[([^\]\n]+)\]:[ \t]*(?:{DESTINATION})")


def json_strings(
    value: object, location: str = "", free_text: bool = False
) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield location, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from json_strings(item, f"{location}[{index}]", free_text)
    elif isinstance(value, dict):
        for key, item in value.items():
            if free_text or key not in STRUCTURE_KEYS:
                path = f"{location}.{key}" if location else key
                yield from json_strings(item, path, free_text or key in FREE_TEXT_KEYS)


def source_lists(value: object, location: str = "") -> Iterator[tuple[str, object]]:
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{location}.{key}" if location else key
            if key == "sources":
                yield path, item
            elif key not in FREE_TEXT_KEYS:
                yield from source_lists(item, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from source_lists(item, f"{location}[{index}]")


def read_inside_repo(root: Path, rel: PurePosixPath) -> bytes:
    resolved = (root / rel).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"레포 루트 밖을 가리킨다 → {resolved}")
    if not resolved.is_file():
        raise ValueError("일반 파일이 필요하다")
    return resolved.read_bytes()


@lru_cache(maxsize=256)
def source_length(root: Path, rel: PurePosixPath) -> int:
    # Expat and Git count LF as a line break; a trailing newline is not a new line.
    data = read_inside_repo(root, rel)
    return data.count(b"\n") + bool(data and not data.endswith(b"\n"))


def validate_source(root: Path, entry: object, files: set[str]) -> None:
    path = entry.get("path") if isinstance(entry, dict) else None
    if not isinstance(path, str) or not path:
        raise ValueError("근거에는 파일 path 문자열이 필요하다")
    rel = PurePosixPath(path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"레포 상대 경로가 필요하다 → {path}")
    if rel.as_posix() not in files:
        raise ValueError(f"Git 추적 근거 파일이 필요하다 → {path}")
    length = source_length(root, rel)
    if "line" in entry or "end_line" in entry:
        start = entry.get("line")
        end = entry.get("end_line", start)
        if (
            type(start) is not int
            or type(end) is not int
            or not 1 <= start <= end <= length
        ):
            raise ValueError(
                f"줄 범위 {start!r}-{end!r}가 파일 범위 밖이다 → {path} (파일 {length}줄)"
            )


def read_manifest(data: bytes, artifacts: tuple[str, ...]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for line in data.decode("utf-8").splitlines():
        match = HASH_RE.fullmatch(line)
        if not match or match[2] not in artifacts or match[2] in hashes:
            raise ValueError("SHA-256 뒤에 해당 도식의 파일명을 한 번씩 적어라")
        hashes[match[2]] = match[1]
    if hashes.keys() != set(artifacts):
        raise ValueError("정본·SVG의 SHA-256이 모두 필요하다")
    return hashes


def text_problems(
    path: PurePosixPath, text: Iterator[tuple[str, str]], files: set[str]
) -> Iterator[str]:
    for location, value in text:
        for line in value.splitlines():
            for kind, ref, hint in diagram_line_problems(line, files):
                yield f"{path}:{location} [{kind}] {ref} → {hint}"


def svg_text(svg: ET.Element) -> Iterator[tuple[str, str]]:
    for element in svg.iter():
        tag = element.tag.removeprefix(SVG_NS)
        if tag in {"text", "title"}:
            yield f"<{tag}>", "".join(element.itertext())
        for name, value in element.attrib.items():
            if name in {"data-node-label", "data-node-sublabel"} or name.startswith(
                "data-edge-"
            ):
                yield f"<{tag}> @{name}", value


def records(spec: dict, key: str) -> list[dict]:
    entries = spec.get(key)
    if not isinstance(entries, list) or any(
        not isinstance(entry, dict) for entry in entries
    ):
        raise ValueError(f"{key}에 JSON 객체 배열이 필요하다")
    return entries


def metadata(entry: dict, prefix: str, fields: tuple[str, ...]) -> tuple[str, ...]:
    values = []
    for field in fields:
        value = entry.get(prefix + field, "")
        if not isinstance(value, str):
            raise ValueError(f"{prefix}{field}에 문자열이 필요하다")
        values.append(value if value.strip() else "")
    return tuple(values)


def compare_metadata(spec: dict, svg: ET.Element) -> Iterator[str]:
    kind = spec.get("diagram_type")
    if not isinstance(kind, str) or kind not in COLLECTIONS:
        raise ValueError(f"SVG 메타데이터 대조를 지원하지 않는 diagram_type → {kind!r}")
    node_key, edge_key = COLLECTIONS[kind]
    nodes = records(spec, node_key)
    if not nodes or any(not node.get("id") or not node.get("label") for node in nodes):
        raise ValueError(f"{node_key}에 ID와 라벨을 가진 노드가 필요하다")
    edges = (
        records(spec, edge_key)
        if edge_key
        else [
            {"from": node["parent"], "to": node["id"]}
            for node in nodes
            if "parent" in node
        ]
    )
    expected_nodes = Counter(metadata(node, "", NODE_FIELDS) for node in nodes)
    expected_edges = Counter(metadata(edge, "", EDGE_FIELDS) for edge in edges)
    rendered_nodes = Counter(
        metadata(element.attrib, "data-node-", NODE_FIELDS)
        for element in svg.iter()
        if "data-node-id" in element.attrib
    )
    # A workflow edge can have both a path and a label group with the same key.
    # Keep distinct parallel edges and detect disagreement between these copies.
    rendered_edge_parts = {
        (
            element.get("data-edge-key"),
            metadata(element.attrib, "data-edge-", EDGE_FIELDS),
        )
        for element in svg.iter()
        if any(
            "data-edge-" + field in element.attrib for field in ("key", *EDGE_FIELDS)
        )
    }
    rendered_edges = Counter(properties for _, properties in rendered_edge_parts)
    if rendered_nodes != expected_nodes:
        yield "노드 메타데이터 불일치 (id·label·sublabel) → 정본에서 SVG를 다시 생성하라"
    if rendered_edges != expected_edges:
        yield "엣지 메타데이터 불일치 (id·from·to·label) → 정본에서 SVG를 다시 생성하라"


def candidate_problems(
    root: Path, path: PurePosixPath, spec: dict, files: set[str]
) -> Iterator[str]:
    yield from text_problems(path, json_strings(spec), files)
    for location, entries in source_lists(spec):
        if not isinstance(entries, list):
            yield f"{path}:{location}: 근거는 JSON 배열이어야 한다"
            continue
        for index, entry in enumerate(entries):
            try:
                validate_source(root, entry, files)
            except (OSError, RuntimeError, ValueError) as err:
                yield f"{path}:{location}[{index}]: {err}"


class SvgTreeBuilder(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise ValueError("SVG에 DTD를 허용하지 않는다")


def diagram_problems(
    root: Path, slug: str, entries: set[str], files: set[str]
) -> list[str]:
    if not SLUG_RE.fullmatch(slug):
        return [f"{slug!r}: 도식 디렉토리에는 소문자·숫자·하이픈을 사용하라"]
    folder = DIAGRAM_ROOT / slug
    artifacts = ("candidate.json", f"{slug}.svg")
    expected = {*artifacts, MANIFEST}
    problems = [
        f"{folder / entry}: 예상 밖 추적 파일 → 도식 디렉토리에는 정본·SVG·매니페스트만 둬라"
        for entry in sorted(entries - expected)
    ]
    data: dict[str, bytes] = {}
    for name in (*artifacts, MANIFEST):
        rel = folder / name
        try:
            if name not in entries:
                raise ValueError("Git 추적 파일이 필요하다")
            data[name] = read_inside_repo(root, rel)
        except (OSError, RuntimeError, ValueError) as err:
            problems.append(f"{rel}: {err}")

    if MANIFEST in data:
        try:
            hashes = read_manifest(data[MANIFEST], artifacts)
        except ValueError as err:
            problems.append(f"{folder / MANIFEST}: {err}")
        else:
            for name in artifacts:
                if (
                    name in data
                    and hashlib.sha256(data[name]).hexdigest() != hashes[name]
                ):
                    problems.append(
                        f"{folder / name}: SHA-256 불일치 → 정본에서 SVG를 다시 생성한 뒤 해시를 기록하라"
                    )

    spec = svg = None
    candidate = folder / "candidate.json"
    if "candidate.json" in data:
        try:
            parsed = json.loads(data["candidate.json"].decode("utf-8"))
            if not isinstance(parsed, dict) or not parsed:
                raise ValueError("비어 있지 않은 JSON 객체가 필요하다")
        except (ValueError, RecursionError) as err:
            problems.append(f"{candidate}: 정본 JSON 읽기 실패 → {err}")
        else:
            spec = parsed
            problems.extend(candidate_problems(root, candidate, spec, files))

    svg_name = f"{slug}.svg"
    svg_path = folder / svg_name
    if svg_name in data:
        try:
            parser = ET.XMLParser(target=SvgTreeBuilder())  # noqa: S314 — rejects DTDs
            parsed_svg = ET.fromstring(data[svg_name], parser=parser)  # noqa: S314 — rejects DTDs
            if parsed_svg.tag not in {SVG_NS + "svg", "svg"}:
                raise ValueError("루트 요소는 svg여야 한다")
        except (ET.ParseError, LookupError, ValueError) as err:
            problems.append(f"{svg_path}: SVG 파싱 실패 → {err}")
        else:
            svg = parsed_svg
            problems.extend(text_problems(svg_path, svg_text(svg), files))

    if spec is not None and svg is not None:
        try:
            problems.extend(
                f"{svg_path}: {problem}" for problem in compare_metadata(spec, svg)
            )
        except ValueError as err:
            problems.append(f"{candidate}: {err}")
    return problems


class HtmlImages(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[tuple[int, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag not in {"img", "source"}:
            return
        line = self.getpos()[0]
        for attr, value in attrs:
            if attr == "src" and tag == "img" and value:
                self.targets.append((line, value))
            if attr == "srcset" and value:
                for candidate in value.split(","):
                    if parts := candidate.split():
                        self.targets.append((line, parts[0]))


def ref_key(label: str) -> str:
    return " ".join(label.split()).casefold()


def image_targets(text: str) -> Iterator[tuple[int, str]]:
    # Keep original line numbers for raw HTML and skip fenced/inline code examples.
    lines = [""] * len(text.splitlines())
    for number, line, lang in scan_lines(text):
        if lang is None:
            lines[number - 1] = CODE_SPAN_RE.sub("", line)
    prose = re.sub(
        r"<!--.*?(?:-->|\Z)",
        lambda match: "\n" * match[0].count("\n"),
        "\n".join(lines),
        flags=re.DOTALL,
    )
    definitions = {}
    for ref in DEFINITION_RE.finditer(prose):
        definitions.setdefault(ref_key(ref[1]), ref[2] or ref[3])
    for number, line in enumerate(prose.splitlines(), 1):
        for match in INLINE_IMAGE_RE.finditer(line):
            yield number, match[2] or match[3]
        for match in REFERENCE_IMAGE_RE.finditer(line):
            target = definitions.get(ref_key(match[2] or match[1]))
            if target:
                yield number, target
    html = HtmlImages()
    html.feed(prose)
    html.close()
    yield from html.targets


def markdown_problems(root: Path, files: set[str]) -> Iterator[str]:
    for rel in sorted(path for path in files if path.endswith(".md")):
        doc = PurePosixPath(rel)
        try:
            text = read_inside_repo(root, doc).decode("utf-8")
        except (OSError, RuntimeError, ValueError) as err:
            yield f"{doc}: Markdown 이미지 검사 실패 → {err}"
            continue
        for line, target in image_targets(text):
            try:
                url = urlsplit(unescape(target))
            except ValueError:
                if ".svg" in target.lower():
                    yield f"{doc}:{line}: SVG 이미지 주소가 올바르지 않다 → {target}"
                continue
            path = unquote(url.path)
            if not path.lower().endswith(".svg"):
                continue
            path = path.lstrip("/") if path.startswith("/") else str(doc.parent / path)
            image = PurePosixPath(posixpath.normpath(path))
            if url.scheme or url.netloc or not image.is_relative_to(DIAGRAM_ROOT):
                yield f"{doc}:{line}: 도식 루트 밖 SVG → {target}"
            elif str(image) not in files:
                yield f"{doc}:{line}: SVG 이미지에 Git 추적 파일이 필요하다 → {target}"


def main(root: Path = REPO_ROOT) -> int:
    files = set(tracked_files(root, label=LABEL))
    source_length.cache_clear()
    diagrams: dict[str, set[str]] = {}
    for rel in files:
        path = PurePosixPath(rel)
        if path.is_relative_to(DIAGRAM_ROOT):
            parts = path.relative_to(DIAGRAM_ROOT).parts
            if len(parts) >= 2:
                diagrams.setdefault(parts[0], set()).add("/".join(parts[1:]))
    problems = list(markdown_problems(root, files))
    if not diagrams:
        problems.append(f"{DIAGRAM_ROOT}에 Git 추적 도식이 없다")
    for slug, entries in sorted(diagrams.items()):
        problems.extend(diagram_problems(root, slug, entries, files))
    if problems:
        print(f"[{LABEL}] ✗ 도식 {len(diagrams)}개 검사 중 위반 {len(problems)}건")
        for problem in problems:
            print(f"    {problem}")
        return 1
    print(
        f"[{LABEL}] ✓ 도식 {len(diagrams)}개의 표시 텍스트·근거·SVG 메타데이터 및 SHA-256 확인"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
