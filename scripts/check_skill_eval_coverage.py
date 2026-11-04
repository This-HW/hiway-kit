"""Structural coverage of deterministic skill CLI contracts (no model/command execution).

Discover every common SKILL.md, subtract the sealed pre-5.6 debt cohort, and
require positive and negative cases backed by concrete pytest functions. This
does not measure natural-language selection or skill-use equivalence. Exit 1
means malformed policy, unsafe paths, or missing/invalid coverage; exit 0 means
the declarations are consistent. verify-done's pytest section executes tests.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import hashlib
import json
import re
from pathlib import Path

# SHA256 of sorted names, each followed by LF, from the fixed tree
# 102853ec8a13c38d6911f7b51b23ef4c2eb4676c:plugins/common/skills.
# Names/reasons live only in policy.json; this seal prevents policy editors from
# grandfathering new skills. Runtime needs neither git history nor a second list.
LEGACY_NAMES_SHA256 = "9b2db9335c1a445a7d1f818926728b726869e665e0607a95578781b6c4ce9824"
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TEST_NODE = re.compile(r"(tests/hooks/test_[a-z0-9_]+\.py)::(test_[a-z0-9_]+)")


class PolicyError(ValueError):
    """Invalid data must fail loudly, including empty inspection targets."""


def _resolve_in_repo(container_root: Path, rel_path: str) -> tuple[Path | None, str | None]:
    """Use the repository containment convention; reuse the resolved result."""
    real = (container_root / rel_path).resolve()
    try:
        real.relative_to(container_root)
    except ValueError:
        return None, f"path escapes allowed root: {rel_path}"
    return real, None


def contained(root: Path, value: str) -> Path:
    real, error = _resolve_in_repo(root, value)
    if real is None:
        raise PolicyError(error)
    return real


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def require_keys(value, keys: set[str], label: str):
    if not isinstance(value, dict) or set(value) != keys:
        raise PolicyError(f"{label}: expected keys {sorted(keys)}")


def nonempty_list(value, label: str) -> list:
    if not isinstance(value, list) or not value:
        raise PolicyError(f"{label}: expected nonempty array")
    return value


def nonempty_text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{label}: expected nonempty string")
    return value


def discover_skills(root: Path) -> set[str]:
    directory = contained(root, "plugins/common/skills")
    skills = set()
    for entry in sorted(directory.iterdir()):
        child = contained(directory, entry.name)
        if not child.is_dir():
            continue
        definition = contained(child, "SKILL.md")
        if not definition.exists():
            continue
        if not definition.is_file() or not NAME.fullmatch(entry.name):
            raise PolicyError(f"invalid skill definition: {entry}")
        skills.add(entry.name)
    if not skills:
        raise PolicyError("discovered zero skills: missing/empty plugins/common/skills")
    return skills


def legacy_exceptions(policy, skills: set[str]) -> set[str]:
    if not isinstance(policy, dict):
        raise PolicyError("policy: expected object")
    section = policy.get("skills")
    require_keys(section, {"schema", "legacyExceptions"}, "policy.skills")
    if type(section["schema"]) is not int or section["schema"] != 1:
        raise PolicyError("policy.skills.schema: expected 1")
    names = set()
    for record in nonempty_list(section["legacyExceptions"], "legacyExceptions"):
        require_keys(record, {"skill", "reason"}, "legacy exception")
        name = nonempty_text(record["skill"], "legacy skill")
        nonempty_text(record["reason"], "legacy reason")
        if name not in skills:
            raise PolicyError(f"unknown legacy skill: {name}")
        if name in names:
            raise PolicyError(f"duplicate legacy skill: {name}")
        names.add(name)
    fingerprint = hashlib.sha256(("\n".join(sorted(names)) + "\n").encode()).hexdigest()
    if fingerprint != LEGACY_NAMES_SHA256:
        raise PolicyError("legacy exceptions differ from sealed pre-5.6 cohort; new skills cannot be exempt")
    return names


def validate_pytest_node(root: Path, node: str):
    match = TEST_NODE.fullmatch(node)
    if match is None:
        raise PolicyError(f"invalid pytest testNode: {node}")
    file, function = match.groups()
    path = contained(root, file)
    # Only plain module-level tests are supported. No imports, pytest plugins,
    # shell strings, parametrization expressions, or decorators are evaluated.
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=file)
    disabled = {"pytestmark", "__test__", function}
    module_marks = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                    and any(isinstance(t, ast.Name) and t.id in disabled
                            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))]
    tests = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function]
    if len(tests) != 1 or tests[0].decorator_list or module_marks:
        raise PolicyError(f"testNode must name one undecorated module-level pytest test: {node}")


def check(root: Path) -> list[str]:
    skills = discover_skills(root)
    exceptions = legacy_exceptions(read_json(contained(root, "evals/policy.json")), skills)
    config = configparser.ConfigParser()
    config.read_string(contained(root, "pytest.ini").read_text(encoding="utf-8"))
    if "tests/hooks" not in config.get("pytest", "testpaths").split():
        raise PolicyError("pytest testpaths must collect tests/hooks CLI contracts")
    directory = contained(root, "evals/skill-scenarios")
    paths = []
    for entry in sorted(directory.iterdir()):
        child = contained(directory, entry.name)
        if not child.is_dir():
            continue
        if entry.name not in skills:
            raise PolicyError(f"unknown scenario skill directory: {entry.name}")
        paths.extend((entry.name, contained(child, file.name)) for file in sorted(child.glob("*.json")))
    if not paths:
        raise PolicyError("skill scenarios: missing/empty scenario files")
    covered: dict[str, set[str]] = {}
    identifiers = set()
    nodes = set()
    for directory_skill, path in paths:
        scenario = read_json(path)
        require_keys(scenario, {"schema", "skill", "cases"}, "scenario")
        skill = nonempty_text(scenario["skill"], "scenario.skill")
        if skill not in skills or directory_skill != skill:
            raise PolicyError(f"unknown/mismatched scenario skill: {skill} ({path})")
        if type(scenario["schema"]) is not int or scenario["schema"] != 1:
            raise PolicyError("scenario.schema: expected 1")
        for case in nonempty_list(scenario["cases"], "scenario.cases"):
            require_keys(case, {"id", "polarity", "testNode", "expectation", "evidence"}, "case")
            identifier = nonempty_text(case["id"], "case.id")
            if not NAME.fullmatch(identifier) or (skill, identifier) in identifiers:
                raise PolicyError(f"invalid/duplicate case id: {skill}/{identifier}")
            identifiers.add((skill, identifier))
            polarity = case["polarity"]
            if polarity not in ("positive", "negative"):
                raise PolicyError("case.polarity: expected positive or negative")
            if case["evidence"] != "synthetic-cli":
                raise PolicyError("case.evidence: expected synthetic-cli (model samples are separate)")
            nonempty_text(case["expectation"], "case.expectation")
            node = nonempty_text(case["testNode"], "case.testNode")
            if node in nodes:
                raise PolicyError(f"duplicate testNode: {node}")
            nodes.add(node)
            validate_pytest_node(root, node)
            covered.setdefault(skill, set()).add(polarity)
    missing = sorted(skill for skill in skills - exceptions
                     if covered.get(skill, set()) != {"positive", "negative"})
    if missing:
        raise PolicyError(f"skills missing positive/negative CLI scenarios: {', '.join(missing)}")
    return [f"skill CLI coverage: {len(skills)} discovered, {len(exceptions)} sealed legacy exceptions, "
            f"{len(skills - exceptions)} required, {len(nodes)} concrete pytest nodes",
            "Structural coverage only; pytest executes CLI contracts; natural-language selection is a separate sample."]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    try:
        for line in check(args.root.resolve()):
            print(line)
    except (PolicyError, OSError, ValueError, TypeError, SyntaxError, configparser.Error) as exc:
        print(f"skill CLI coverage FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
