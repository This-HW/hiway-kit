import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "check_local_traces.py"
POLICY = Path("scripts/local-trace-exceptions.json")
DOC = "새문서.unknown"


def home_path(root, account):
    return str(Path("/") / root / account / "project")


def stage(repo, path, data):
    (repo / path).write_bytes(data)
    subprocess.run(["git", "add", "--", path], cwd=repo, check=True)


def policy(repo, entries):
    stage(repo, POLICY, json.dumps({"exceptions": entries}).encode())


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / POLICY.parent).mkdir()
    policy(root, [])
    return root


def check(repo):
    return subprocess.run(
        [sys.executable, SCRIPT, "--root", repo],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("trace", "kind"),
    [
        (home_path("Users", "sample.person"), "absolute-home"),
        (home_path("home", "runner"), "absolute-home"),
        (home_path("Users", "jan+build"), "absolute-home"),
        ("-".join(("hiway", "kit", "tools")), "tool-cache"),
        ("-".join(("hiway", "research")), "tool-cache"),
        ("-".join(("venv", "pinned")), "tool-cache"),
        (str(Path(".claude", "skills", "archify")), "archify-install"),
        (str(Path(".claude", "rules", "archify.md")), "archify-install"),
        (str(Path("~", ".agents", "skills", "archify")), "archify-install"),
        ("[" + " ".join(("archify", "explainer: on-demand")) + "]", "archify-install"),
        (" ".join(("aside", "repl")), "local-browser"),
        (str(Path("~", ".aside", "u", "0", "uploads")), "local-browser"),
    ],
)
def test_reports_only_location_and_class(repo, trace, kind):
    stage(repo, DOC, f"title\n{trace}\n".encode())
    result = check(repo)
    assert result.returncode == 1
    assert f"{DOC}:2: {kind}" in result.stdout
    assert trace not in result.stdout + result.stderr


def test_scans_tracked_text_and_link_targets(repo):
    trace = home_path("Users", "example")
    (repo / "untracked").write_text(trace)
    stage(repo, DOC, b"<home>/project\n~/.agents/skills\n")
    stage(repo, "image.png", b"\x89PNG\0" + trace.encode())
    assert check(repo).returncode == 0
    (repo / "link").symlink_to(trace)
    subprocess.run(["git", "add", "link"], cwd=repo, check=True)
    result = check(repo)
    assert result.returncode == 1
    assert "link:1: absolute-home" in result.stdout


def test_exception_applies_only_to_reviewed_line(repo):
    line = home_path("home", "runner").encode()
    stage(repo, DOC, line)
    entry = {
        "path": DOC,
        "line": 1,
        "sha256": hashlib.sha256(line).hexdigest(),
        "reason": "Hosted CI checkout example",
    }
    policy(repo, [entry])
    assert check(repo).returncode == 0
    stage(repo, DOC, line + b"\n" + line)
    assert f"{DOC}:2: absolute-home" in check(repo).stdout
    stage(repo, DOC, home_path("home", "another").encode())
    assert f"{DOC}:1: absolute-home" in check(repo).stdout
    stage(repo, DOC, b"clean")
    assert check(repo).returncode == 1  # stale exception
    stage(repo, DOC, line)
    policy(repo, [dict(entry, reason=" ")])
    assert check(repo).returncode == 1


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
def test_scans_bom_encoded_documents(repo, encoding):
    stage(repo, DOC, ("title\n" + home_path("Users", "sample")).encode(encoding))
    assert f"{DOC}:2: absolute-home" in check(repo).stdout


def test_exception_for_link_cannot_suppress_target_file(repo):
    line = home_path("home", "runner").encode()
    stage(repo, DOC, line)
    (repo / "alias").symlink_to(DOC)
    subprocess.run(["git", "add", "alias"], cwd=repo, check=True)
    policy(
        repo,
        [
            {
                "path": "alias",
                "line": 1,
                "sha256": hashlib.sha256(line).hexdigest(),
                "reason": "Only the link was reviewed",
            }
        ],
    )
    assert f"{DOC}:1: absolute-home" in check(repo).stdout


def test_diagnostic_redacts_trace_in_filename(repo):
    name = "docs" + home_path("home", "private-account")
    (repo / name).parent.mkdir(parents=True)
    stage(repo, name, home_path("Users", "sample").encode())
    result = check(repo)
    assert result.returncode == 1
    assert ":1: absolute-home" in result.stdout
    assert "private-account" not in result.stdout + result.stderr


def test_policy_must_be_tracked(repo):
    subprocess.run(["git", "rm", "--cached", str(POLICY)], cwd=repo, check=True)
    assert check(repo).returncode == 1


@pytest.mark.parametrize("escape", ["absolute", "parent", "symlink", "policy-link"])
def test_policy_path_containment(repo, escape):
    outside = repo.parent / "outside"
    outside.write_text('{"exceptions": []}')
    if escape == "policy-link":
        (repo / POLICY).unlink()
        (repo / POLICY).symlink_to(outside)
    else:
        (repo / "link").symlink_to(outside)
        path = {"absolute": str(outside), "parent": "../outside", "symlink": "link"}[
            escape
        ]
        policy(
            repo, [{"path": path, "line": 1, "sha256": "a" * 64, "reason": "fixture"}]
        )
    result = check(repo)
    assert result.returncode == 1
    assert "path" in result.stdout
    assert str(outside) not in result.stdout + result.stderr
