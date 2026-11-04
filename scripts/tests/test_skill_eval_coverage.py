"""Exercise skill coverage with isolated repositories, never live gate assets."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from module_loader import load_module_by_path

ROOT = Path(__file__).resolve().parents[2]
checker = load_module_by_path(ROOT / "scripts/check_skill_eval_coverage.py", "skill_eval_coverage")


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "evals").mkdir(parents=True)
    shutil.copy2(ROOT / "evals/policy.json", root / "evals/policy.json")
    shutil.copytree(ROOT / "evals/skill-scenarios", root / "evals/skill-scenarios")
    for path in (ROOT / "plugins/common/skills").glob("*/SKILL.md"):
        target = root / path.relative_to(ROOT)
        target.parent.mkdir(parents=True)
        target.write_text("# Fixture skill\n", encoding="utf-8")
    (root / "tests/hooks").mkdir(parents=True)
    shutil.copy2(ROOT / "tests/hooks/test_skill_cli_contracts.py", root / "tests/hooks/test_skill_cli_contracts.py")
    shutil.copy2(ROOT / "pytest.ini", root / "pytest.ini")
    return root


def run(root):
    return checker.main(["--root", str(root)])


def update_policy(root, mutate):
    path = root / "evals/policy.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    write_json(path, data)


def update_scenario(root, mutate):
    path = root / "evals/skill-scenarios/code-intel/cli-contracts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    write_json(path, data)


def test_complete_cli_coverage_passes(repo):
    assert run(repo) == 0


def test_new_skill_is_discovered_and_fails_without_scenarios(repo):
    path = repo / "plugins/common/skills/future-skill/SKILL.md"
    path.parent.mkdir()
    path.write_text("# New skill", encoding="utf-8")
    assert run(repo) == 1


def test_new_skill_passes_when_both_cli_polarities_are_registered(repo):
    path = repo / "plugins/common/skills/future-skill/SKILL.md"
    path.parent.mkdir()
    path.write_text("# New skill", encoding="utf-8")
    test = repo / "tests/hooks/test_future_contracts.py"
    test.write_text("def test_positive():\n    assert True\ndef test_negative():\n    assert True\n", encoding="utf-8")
    scenario = repo / "evals/skill-scenarios/future-skill/cli-contracts.json"
    scenario.parent.mkdir()
    write_json(scenario, {"schema": 1, "skill": "future-skill", "cases": [
        {"id": polarity, "polarity": polarity, "testNode": f"tests/hooks/test_future_contracts.py::test_{polarity}",
         "expectation": "fixture for structural coverage", "evidence": "synthetic-cli"}
        for polarity in ("positive", "negative")]})
    assert run(repo) == 0


@pytest.mark.parametrize("mode", ["append", "replace"])
def test_new_skill_cannot_be_grandfathered(repo, mode):
    path = repo / "plugins/common/skills/future-skill/SKILL.md"
    path.parent.mkdir()
    path.write_text("# New skill", encoding="utf-8")

    def mutate(policy):
        exceptions = policy["skills"]["legacyExceptions"]
        if mode == "replace":
            exceptions.pop()
        exceptions.append({"skill": "future-skill", "reason": "attempted bypass"})

    update_policy(repo, mutate)
    assert run(repo) == 1


@pytest.mark.parametrize("skill", ["code-intel", "session-history"])
def test_current_new_skills_cannot_be_exempt(repo, skill):
    update_policy(repo, lambda p: p["skills"]["legacyExceptions"].append({"skill": skill, "reason": "attempted bypass"}))
    assert run(repo) == 1


@pytest.mark.parametrize("section", [None, {}, [], {"schema": 1, "legacyExceptions": []},
                                     {"schema": 1, "legacyExceptions": {}},
                                     {"schema": True, "legacyExceptions": ["bad"]}])
def test_missing_empty_or_malformed_policy_section_fails(repo, section):
    update_policy(repo, lambda p: p.update(skills=section))
    assert run(repo) == 1


def test_absent_policy_section_fails(repo):
    update_policy(repo, lambda p: p.pop("skills"))
    assert run(repo) == 1


@pytest.mark.parametrize("mutation", ["duplicate", "unknown", "empty-reason", "wrong-record"])
def test_invalid_exceptions_fail(repo, mutation):
    def mutate(policy):
        rows = policy["skills"]["legacyExceptions"]
        if mutation == "duplicate":
            rows.append(rows[0])
        elif mutation == "unknown":
            rows[0]["skill"] = "unknown-skill"
        elif mutation == "empty-reason":
            rows[0]["reason"] = " "
        else:
            rows[0] = "agent-creator"
    update_policy(repo, mutate)
    assert run(repo) == 1


@pytest.mark.parametrize("mutation", ["missing-file", "empty-list", "wrong-array", "duplicate-case",
                                     "duplicate-node", "unknown-skill", "wrong-directory", "only-negative",
                                     "fake-node", "fake-file", "shell-command", "bad-json"])
def test_invalid_scenarios_fail(repo, mutation):
    path = repo / "evals/skill-scenarios/code-intel/cli-contracts.json"
    if mutation == "missing-file":
        path.unlink()
    elif mutation == "bad-json":
        path.write_text("{", encoding="utf-8")
    else:
        def mutate(data):
            rows = data["cases"]
            if mutation == "empty-list":
                data["cases"] = []
            elif mutation == "wrong-array":
                data["cases"] = {}
            elif mutation == "duplicate-case":
                rows.append(rows[0])
            elif mutation == "duplicate-node":
                rows[1]["testNode"] = rows[0]["testNode"]
            elif mutation == "unknown-skill":
                data["skill"] = "unknown-skill"
            elif mutation == "wrong-directory":
                data["skill"] = "session-history"
            elif mutation == "only-negative":
                for row in rows:
                    row["polarity"] = "negative"
            elif mutation == "fake-node":
                rows[0]["testNode"] = "tests/hooks/test_skill_cli_contracts.py::test_does_not_exist"
            elif mutation == "fake-file":
                rows[0]["testNode"] = "tests/hooks/test_missing.py::test_missing"
            else:
                rows[0]["command"] = "touch should-never-run"
        update_scenario(repo, mutate)
    assert run(repo) == 1
    assert not (repo / "should-never-run").exists()


@pytest.mark.parametrize("kind", ["absolute", "parent", "symlink", "policy", "scenario", "skill",
                                 "scenario-directory", "skill-directory"])
def test_path_escapes_fail(repo, tmp_path, kind):
    outside = tmp_path / "outside"
    outside.mkdir()
    if kind in {"absolute", "parent", "symlink"}:
        target = repo / "tests/hooks/test_skill_cli_contracts.py"
        shutil.copy2(target, outside / target.name)
        if kind == "symlink":
            target.unlink()
            target.symlink_to(outside / target.name)
        else:
            prefix = str(outside) if kind == "absolute" else "../outside"
            update_scenario(repo, lambda p: p["cases"][0].update(testNode=prefix + "/test_skill_cli_contracts.py::test_ast_metavariables_and_preview_preserve_source"))
    elif kind.endswith("-directory"):
        target = repo / ("plugins/common/skills/code-intel" if kind == "skill-directory"
                         else "evals/skill-scenarios/code-intel")
        shutil.rmtree(target)
        target.symlink_to(outside, target_is_directory=True)
    else:
        relatives = {"policy": "evals/policy.json",
                     "scenario": "evals/skill-scenarios/code-intel/cli-contracts.json",
                     "skill": "plugins/common/skills/code-intel/SKILL.md"}
        target = repo / relatives[kind]
        shutil.copy2(target, outside / target.name)
        target.unlink()
        target.symlink_to(outside / target.name)
    assert run(repo) == 1


@pytest.mark.parametrize("kind", ["skills", "scenarios"])
def test_empty_discovery_fails(repo, kind):
    directory = repo / ("plugins/common/skills" if kind == "skills" else "evals/skill-scenarios")
    shutil.rmtree(directory)
    directory.mkdir()
    assert run(repo) == 1


def test_duplicate_json_keys_fail(repo):
    (repo / "evals/policy.json").write_text('{"skills": {}, "skills": {}}', encoding="utf-8")
    assert run(repo) == 1


def test_skipped_test_node_is_not_coverage(repo):
    path = repo / "tests/hooks/test_skill_cli_contracts.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace("def test_ast_metavariables", "@pytest.mark.skip\ndef test_ast_metavariables")
    path.write_text(text, encoding="utf-8")
    assert run(repo) == 1


@pytest.mark.parametrize("assignment", ["__test__ = False", "pytestmark: list = []",
                                       "test_ast_metavariables_and_preview_preserve_source = None"])
def test_disabled_or_reassigned_node_is_not_coverage(repo, assignment):
    path = repo / "tests/hooks/test_skill_cli_contracts.py"
    path.write_text(path.read_text(encoding="utf-8") + "\n" + assignment, encoding="utf-8")
    assert run(repo) == 1


def test_pytest_gate_must_collect_cli_tests(repo):
    path = repo / "pytest.ini"
    path.write_text(path.read_text(encoding="utf-8").replace("    tests/hooks\n", ""), encoding="utf-8")
    assert run(repo) == 1


def assert_cli_execution(report, nodes):
    """A collected or runtime-skipped contract is not execution evidence."""
    # Only this test's pytest process writes the report in its fresh tmp_path;
    # no downloaded or user-supplied XML is accepted.
    cases = ET.parse(report).findall(".//testcase")  # noqa: S314
    expected = {(file.removesuffix(".py").replace("/", "."), name)
                for file, name in (node.split("::") for node in nodes)}
    observed = [(case.get("classname"), case.get("name")) for case in cases]
    assert len(observed) == len(expected) and set(observed) == expected
    for case in cases:
        assert not any(case.find(tag) is not None for tag in ("skipped", "failure", "error")), ET.tostring(case)


def test_registered_nodes_are_actually_collected(tmp_path):
    nodes = []
    for path in (ROOT / "evals/skill-scenarios").glob("*/*.json"):
        for case in json.loads(path.read_text(encoding="utf-8"))["cases"]:
            nodes.append(case["testNode"])
    report = tmp_path / "cli-results.xml"
    process = subprocess.run([sys.executable, "-m", "pytest", "-q", "-o", "addopts=",
                              "--junitxml", str(report), *nodes], cwd=ROOT,
                             capture_output=True, text=True, check=False, timeout=45)
    assert process.returncode == 0, process.stdout + process.stderr
    assert_cli_execution(report, nodes)


@pytest.mark.parametrize("behavior", ["pass", "skip", "xfail", "fail", "deselected"])
def test_cli_execution_requires_pass_not_runtime_skip(tmp_path, behavior):
    directory = tmp_path / "tests/hooks"
    directory.mkdir(parents=True)
    body = {"pass": "assert True", "skip": "pytest.skip('runtime')",
            "xfail": "pytest.xfail('runtime')", "fail": "assert False", "deselected": "assert True"}[behavior]
    (directory / "test_runtime.py").write_text(f"import pytest\ndef test_contract():\n    {body}\n")
    report = tmp_path / "results.xml"
    nodes = ["tests/hooks/test_runtime.py::test_contract"]
    process = subprocess.run([sys.executable, "-m", "pytest", "-q", "-o", "addopts=",
                              "--junitxml", str(report), *nodes,
                              *(["-k", "absent"] if behavior == "deselected" else [])],
                             cwd=tmp_path, capture_output=True, text=True, check=False, timeout=30)
    if behavior == "pass":
        assert process.returncode == 0
        assert_cli_execution(report, nodes)
    else:
        if behavior in ("skip", "xfail"):
            assert process.returncode == 0  # pytest alone would falsely satisfy the gate.
        with pytest.raises(AssertionError):
            assert_cli_execution(report, nodes)


@pytest.mark.parametrize("missing", [False, True])
def test_section_29_invokes_independent_checker_and_preserves_failure(repo, missing):
    scripts = repo / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts/check_skill_eval_coverage.py", scripts)
    if missing:
        (repo / "evals/skill-scenarios/code-intel/cli-contracts.json").unlink()
    gate = (ROOT / "scripts/verify-done.sh").read_text(encoding="utf-8")
    section = 'hdr "29.' + gate.split('hdr "29.', 1)[1].split('\nhdr ', 1)[0]
    harness = ('failed=0\nhdr() { :; }\ngreen() { echo GREEN; }\n'
               'red() { echo RED; failed=1; }\n' + section + '\nexit "$failed"\n')
    process = subprocess.run(["bash", "-c", harness], cwd=repo,
                             capture_output=True, text=True, check=False, timeout=30)
    assert process.returncode == int(missing), process.stdout + process.stderr
    assert ("RED" if missing else "GREEN") in process.stdout
