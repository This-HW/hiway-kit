"""The gate rejects drift and invalid reader-facing claims in a tracked diagram."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from module_loader import load_module_by_path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
DIAGRAM = "docs/architecture/diagrams/example"
ARTIFACTS = ("candidate.json", "example.svg")


def record_hashes(folder):
    lines = [
        f"{hashlib.sha256((folder / name).read_bytes()).hexdigest()}  {name}\n"
        for name in ARTIFACTS
    ]
    (folder / "ARTIFACTS.sha256").write_text("".join(lines), encoding="utf-8")


@pytest.fixture
def diagram(tmp_path):
    root = (tmp_path / "repo").resolve()
    folder = root / DIAGRAM
    folder.mkdir(parents=True)
    skill = root / "plugins/common/skills/plan-task/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("Plan task", encoding="utf-8")
    (root / "docs/source.md").write_text("First line\nSecond line\n", encoding="utf-8")
    data = {
        "diagram_type": "workflow",
        "nodes": [
            {
                "id": "plan",
                "label": "/plan-task",
                "sources": [{"path": "docs/source.md", "line": 1, "end_line": 2}],
            },
            {"id": "done", "label": "Done"},
        ],
        "edges": [{"id": "proceed", "from": "plan", "to": "done", "label": "passes"}],
    }
    (folder / "candidate.json").write_text(json.dumps(data), encoding="utf-8")
    (folder / "example.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g data-node-id="plan" data-node-label="/plan-task"><text>/plan-task</text></g>'
        '<g data-node-id="done" data-node-label="Done"><text>Done</text></g>'
        '<path data-edge-key="0" data-edge-id="proceed" data-edge-from="plan" data-edge-to="done" data-edge-label="passes"/>'
        '<g data-edge-key="0" data-edge-id="proceed" data-edge-from="plan" data-edge-to="done" data-edge-label="passes"><text>passes</text></g>'
        "</svg>",
        encoding="utf-8",
    )
    record_hashes(folder)
    subprocess.run(["git", "init", "-q", "--template="], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root, folder


def run_gate(root, capsys):
    gate = load_module_by_path(
        SCRIPTS / "check_archify_diagrams.py", "archify_gate_test"
    )
    rc = gate.main(root)
    return rc, capsys.readouterr().out


def test_missing_skill_in_label_fails_even_with_matching_hashes(diagram, capsys):
    root, folder = diagram
    rc, out = run_gate(root, capsys)
    assert rc == 0, out
    (folder / "candidate.json").write_text(
        '{"nodes":[{"label":"/missing-archify-fixture-skill"}]}', encoding="utf-8"
    )
    record_hashes(folder)
    rc, out = run_gate(root, capsys)
    assert rc == 1, out
    assert "nodes[0].label" in out
    assert "/missing-archify-fixture-skill" in out


@pytest.mark.parametrize("name", ("example.svg", "candidate.json"))
def test_one_byte_drift_fails(diagram, capsys, name):
    root, folder = diagram
    rc, out = run_gate(root, capsys)
    assert rc == 0, out
    file = folder / name
    file.write_bytes(file.read_bytes() + b" ")
    rc, out = run_gate(root, capsys)
    assert rc == 1, out
    assert f"{name}: SHA-256" in out


def test_counts_in_explanations_and_card_items_fail(diagram, capsys):
    root, folder = diagram
    (folder / "candidate.json").write_text(
        '{"nodes":[{"explanation":"3 hooks"}],'
        '"pages":[{"title":"도구", "items":["5개 스킬"]}]}',
        encoding="utf-8",
    )
    record_hashes(folder)
    rc, out = run_gate(root, capsys)
    assert rc == 1, out
    assert "nodes[0].explanation" in out
    assert "pages[0].items[0]" in out


def test_artifact_symlink_cannot_read_outside_repo(diagram, capsys, tmp_path):
    root, folder = diagram
    svg = folder / "example.svg"
    outside = tmp_path / svg.name
    svg.rename(outside)
    svg.symlink_to(outside)
    rc, out = run_gate(root, capsys)
    assert rc == 1, out
    assert "레포 루트 밖" in out


def test_manifest_cannot_name_other_paths(diagram, capsys):
    root, folder = diagram
    manifest = folder / "ARTIFACTS.sha256"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "example.svg", "../../example.svg"
        ),
        encoding="utf-8",
    )
    rc, out = run_gate(root, capsys)
    assert rc == 1, out
    assert "ARTIFACTS.sha256" in out


def edit_candidate(folder, change):
    path = folder / "candidate.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    change(content)
    path.write_text(json.dumps(content), encoding="utf-8")
    record_hashes(folder)


def assert_red(root, capsys, text):
    rc, out = run_gate(root, capsys)
    assert rc == 1, out
    assert text in out


@pytest.mark.parametrize(
    "field,value", [("label", "Changed"), ("sublabel", "New detail"), ("id", "other")]
)
def test_rehashed_candidate_node_must_match_rendered_node(
    diagram, capsys, field, value
):
    root, folder = diagram
    edit_candidate(folder, lambda spec: spec["nodes"][0].update({field: value}))
    assert_red(root, capsys, "노드 메타데이터 불일치")


@pytest.mark.parametrize(
    "field,value", [("id", "renamed"), ("label", "approval"), ("to", "other")]
)
def test_rehashed_candidate_edge_must_match_rendered_edge(
    diagram, capsys, field, value
):
    root, folder = diagram
    edit_candidate(folder, lambda spec: spec["edges"][0].update({field: value}))
    assert_red(root, capsys, "엣지 메타데이터 불일치")


@pytest.mark.parametrize(
    "fragment,diagnostic",
    [
        ("<text>/missing-svg-skill</text>", "/missing-svg-skill"),
        ("<text><tspan>5 </tspan><tspan>hooks</tspan></text>", "5 hooks"),
        ("<title>/missing-title-skill</title>", "/missing-title-skill"),
        ('<g data-node-sublabel="4 agents"/>', "4 agents"),
        ('<path data-edge-future="/missing-edge-skill"/>', "/missing-edge-skill"),
    ],
)
def test_rehashed_svg_text_and_attributes_are_checked(
    diagram, capsys, fragment, diagnostic
):
    root, folder = diagram
    svg = folder / "example.svg"
    svg.write_text(
        svg.read_text(encoding="utf-8").replace("</svg>", f"{fragment}</svg>"),
        encoding="utf-8",
    )
    record_hashes(folder)
    assert_red(root, capsys, diagnostic)


def test_rehashed_invalid_svg_is_red(diagram, capsys):
    root, folder = diagram
    (folder / "example.svg").write_text("<svg>", encoding="utf-8")
    record_hashes(folder)
    assert_red(root, capsys, "SVG 파싱 실패")


@pytest.mark.parametrize(
    "source,diagnostic",
    [
        ({"path": "docs/missing.md", "line": 1}, "Git 추적"),
        ({"path": "/absolute/source.md", "line": 1}, "레포 상대"),
        ({"path": "../source.md", "line": 1}, "레포 상대"),
        ({"path": "docs/source.md", "line": 0}, "줄 범위"),
        ({"path": "docs/source.md", "line": 1, "end_line": 3}, "줄 범위"),
        ({"path": "docs/source.md", "line": 2, "end_line": 1}, "줄 범위"),
        ({"path": "docs/source.md", "end_line": 2}, "줄 범위"),
        ({"path": "docs/source.md", "line": True}, "줄 범위"),
    ],
)
def test_invalid_source_reference(diagram, capsys, source, diagnostic):
    root, folder = diagram
    edit_candidate(folder, lambda spec: spec["nodes"][0].update(sources=[source]))
    assert_red(root, capsys, diagnostic)


def test_source_symlink_cannot_read_outside_repo(diagram, tmp_path, capsys):
    root, _ = diagram
    source = root / "docs/source.md"
    outside = tmp_path / "outside.md"
    source.rename(outside)
    source.symlink_to(outside)
    assert_red(root, capsys, "레포 루트 밖")


@pytest.mark.parametrize(
    "field",
    ("brand", "short", "step", "service", "classification", "at", "futureField"),
)
def test_candidate_reader_text_defaults_to_checked(diagram, capsys, field):
    root, folder = diagram
    edit_candidate(
        folder, lambda spec: spec["nodes"][0].update({field: "/missing-field-skill"})
    )
    assert_red(root, capsys, f"nodes[0].{field}")


@pytest.mark.parametrize("field", ("translations", "payload"))
def test_translation_and_payload_keys_do_not_hide_text(diagram, capsys, field):
    root, folder = diagram
    edit_candidate(
        folder, lambda spec: spec.update({field: {"id": {"path": "3 agents"}}})
    )
    assert_red(root, capsys, f"{field}.id.path")


@pytest.mark.parametrize(
    "name", ("notes.txt", "nested/notes.txt", "example.extra.svg", "example.html")
)
def test_unexpected_tracked_entry_inside_slug(diagram, capsys, name):
    root, folder = diagram
    extra = folder / name
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_text("Unexpected", encoding="utf-8")
    subprocess.run(["git", "add", str(extra)], cwd=root, check=True)
    assert_red(root, capsys, "예상 밖 추적 파일")


@pytest.mark.parametrize(
    "image",
    [
        "![alternate](docs/free.svg)",
        '![alternate](<docs/free space.SVG> "Title")',
        "![Image][svg-label]\n\n[svg-label]: docs/free.svg",
        "![image][]\n\n[image]: docs/free.svg",
        "![image]\n\n[image]: docs/free.svg",
        "<img\n src=docs/free.svg alt=example>",
        "![](https://example.invalid/free.svg)",
        "![](docs/architecture/diagrams/../../free.svg)",
    ],
)
def test_tracked_markdown_svg_images_are_confined_to_diagram_root(
    diagram, capsys, image
):
    root, _ = diagram
    readme = root / "README.md"
    readme.write_text(image + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
    assert_red(root, capsys, "도식 루트 밖 SVG")


def test_in_scope_svg_and_image_code_examples_are_green(diagram, capsys):
    root, _ = diagram
    readme = root / "README.md"
    readme.write_text(
        f"![Example]({DIAGRAM}/example.svg)\n"
        "&#33;[Sample](foo.svg)\n"
        "Use \x60![sample](foo.svg)\x60 in documentation.\n"
        "\x60\x60\x60md\n![sample](foo.svg)\n\x60\x60\x60\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
    rc, out = run_gate(root, capsys)
    assert rc == 0, out


def test_invalid_candidate_json(diagram, capsys):
    root, folder = diagram
    (folder / "candidate.json").write_text("{", encoding="utf-8")
    record_hashes(folder)
    assert_red(root, capsys, "정본 JSON 읽기 실패")


def test_manifest_is_required(diagram, capsys):
    root, folder = diagram
    path = folder / "ARTIFACTS.sha256"
    path.unlink()
    subprocess.run(["git", "add", "-u"], cwd=root, check=True)
    assert_red(root, capsys, "ARTIFACTS.sha256: Git 추적")


def test_zero_diagrams_fails(tmp_path, capsys):
    subprocess.run(["git", "init", "-q", "--template="], cwd=tmp_path, check=True)
    assert_red(tmp_path.resolve(), capsys, "Git 추적 도식이 없다")


@pytest.mark.parametrize("slug", ("Example", "invalid_slug", "invalid--slug"))
def test_slug_must_be_valid(diagram, capsys, slug):
    root, folder = diagram
    temp_folder = folder.with_name("renaming")
    subprocess.run(["git", "mv", str(folder), str(temp_folder)], cwd=root, check=True)
    subprocess.run(
        ["git", "mv", str(temp_folder), str(folder.with_name(slug))],
        cwd=root,
        check=True,
    )
    assert_red(root, capsys, "소문자·숫자·하이픈")


@pytest.mark.parametrize("mutation", ("absolute", "duplicate"))
def test_manifest_rejects_absolute_paths_and_duplicate_entries(
    diagram, capsys, mutation
):
    root, folder = diagram
    manifest = folder / "ARTIFACTS.sha256"
    text = manifest.read_text(encoding="utf-8")
    if mutation == "absolute":
        text = text.replace("example.svg", str(folder / "example.svg"))
    else:
        text += text.splitlines(keepends=True)[-1]
    manifest.write_text(text, encoding="utf-8")
    assert_red(root, capsys, "ARTIFACTS.sha256")
