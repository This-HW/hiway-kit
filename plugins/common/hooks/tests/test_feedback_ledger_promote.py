"""Tests for feedback_ledger.py's staging→promotion (26-16, D-42·D-43·D-49·D-50)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType

HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "feedback_ledger_promote", HOOKS_DIR / "feedback_ledger.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "t@example.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / "a.txt").write_text("seed")
    _git(["add", "a.txt"], repo)
    _git(["commit", "-q", "-m", "seed"], repo)
    return repo


def _write_fake_registry(tmp_path: Path, body: str) -> Path:
    """`body`는 describe()/record() 동작을 정의하는 파이썬 소스 조각(0-컬럼 기준).

    header와 body를 별개로 dedent한 뒤 이어붙인다 — 하나의 f-string으로 합치면
    본문(body)이 0-컬럼인데 헤더가 함수 들여쓰기를 물고 있어 textwrap.dedent가
    공통 들여쓰기를 0으로 계산해 헤더 쪽만 들여써진 채 남는 실패가 있었다.
    """
    header = textwrap.dedent(
        """\
        #!/usr/bin/env python3
        import json, sys
        calls_log = {!r}
        """
    ).format(str(tmp_path / "calls.jsonl"))
    script = tmp_path / "fake_registry.py"
    script.write_text(header + textwrap.dedent(body).format())
    return script


def _install_pointer(repo: Path, command: list, extra: dict | None = None) -> None:
    common_dir = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    common_dir_path = Path(common_dir)
    if not common_dir_path.is_absolute():
        common_dir_path = (repo / common_dir_path).resolve()
    pointer_dir = common_dir_path / "kit"
    pointer_dir.mkdir(parents=True, exist_ok=True)
    data = {"command": command}
    if extra:
        data.update(extra)
    (pointer_dir / "registry.json").write_text(json.dumps(data))


GOOD_REGISTRY_BODY = """\
def main():
    head = subprocess_head()
    if sys.argv[-1] == "describe":
        print(json.dumps({{
            "verbs": [
                {{"name": "list_open", "args": [], "effect": "read", "idempotent": True}},
                {{"name": "record", "args": ["payload"], "effect": "write", "idempotent": False}},
            ],
            "head": head,
        }}))
        return 0
    if sys.argv[-2] == "record":
        with open(calls_log, "a") as fh:
            fh.write(sys.argv[-1] + "\\n")
        return 0
    return 1

def subprocess_head():
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip()

sys.exit(main())
"""


# ── discover_registry_pointer ────────────────────────────────────────
class TestDiscoverPointer:
    def test_no_pointer_returns_none(self, tmp_path):
        repo = _init_repo(tmp_path)
        assert _mod.discover_registry_pointer(repo) is None

    def test_valid_pointer_returns_data(self, tmp_path):
        repo = _init_repo(tmp_path)
        _install_pointer(repo, ["/bin/true"])
        result = _mod.discover_registry_pointer(repo)
        assert result == {"command": ["/bin/true"]}

    def test_url_pointer_rejected(self, tmp_path):
        repo = _init_repo(tmp_path)
        _install_pointer(repo, ["/bin/true"], extra={"url": "http://localhost"})
        assert _mod.discover_registry_pointer(repo) is None

    def test_malformed_json_rejected(self, tmp_path):
        repo = _init_repo(tmp_path)
        common_dir = Path(
            subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        if not common_dir.is_absolute():
            common_dir = (repo / common_dir).resolve()
        pointer_dir = common_dir / "kit"
        pointer_dir.mkdir(parents=True, exist_ok=True)
        (pointer_dir / "registry.json").write_text("{ broken")
        assert _mod.discover_registry_pointer(repo) is None


# ── promote(): 폴백 경로 ──────────────────────────────────────────────
class TestPromoteFallback:
    def test_no_registry_falls_back(self, tmp_path):
        repo = _init_repo(tmp_path)
        _mod.upsert("lint", "low", "unused import", root=repo)
        result = _mod.promote(repo)
        assert result["mode"] == "fallback"
        assert result["promoted"] is False
        # ledger는 그대로 남는다
        assert len(_mod.parse_ledger(_mod.ledger_path(repo))) == 1

    def test_broken_describe_falls_back(self, tmp_path):
        repo = _init_repo(tmp_path)
        _mod.upsert("lint", "low", "x", root=repo)
        script = tmp_path / "broken.py"
        script.write_text("import sys\nprint('not json')\nsys.exit(0)\n")
        _install_pointer(repo, [sys.executable, str(script)])
        result = _mod.promote(repo)
        assert result["mode"] == "fallback"
        assert len(_mod.parse_ledger(_mod.ledger_path(repo))) == 1


# ── promote(): 정상 승격 ─────────────────────────────────────────────
class TestPromoteSuccess:
    def test_promotes_and_empties_ledger(self, tmp_path):
        repo = _init_repo(tmp_path)
        _mod.upsert("security", "high", "hardcoded secret", root=repo)
        script = _write_fake_registry(tmp_path, GOOD_REGISTRY_BODY)
        _install_pointer(repo, [sys.executable, str(script)])

        result = _mod.promote(repo)
        assert result["mode"] == "promoted"
        assert result["promoted"] is True
        assert result["count"] == 1
        assert _mod.parse_ledger(_mod.ledger_path(repo)) == []

        calls = (tmp_path / "calls.jsonl").read_text().splitlines()
        assert len(calls) == 1
        payload = json.loads(calls[0])
        assert payload["category"] == "security"
        assert payload["pattern"] == "hardcoded secret"

    def test_empty_ledger_promotes_trivially(self, tmp_path):
        repo = _init_repo(tmp_path)
        script = _write_fake_registry(tmp_path, GOOD_REGISTRY_BODY)
        _install_pointer(repo, [sys.executable, str(script)])
        result = _mod.promote(repo)
        assert result == {"promoted": True, "mode": "promoted", "count": 0}

    def test_explicit_promotion_verb_used(self, tmp_path):
        repo = _init_repo(tmp_path)
        _mod.upsert("test", "low", "flaky test", root=repo)
        script = _write_fake_registry(tmp_path, GOOD_REGISTRY_BODY)
        _install_pointer(
            repo, [sys.executable, str(script)], extra={"promotionVerb": "record"}
        )
        result = _mod.promote(repo)
        assert result["mode"] == "promoted"


# ── promote(): 동사 선택 실패 ────────────────────────────────────────
class TestVerbSelection:
    def test_no_write_verb_is_held(self, tmp_path):
        repo = _init_repo(tmp_path)
        _mod.upsert("lint", "low", "x", root=repo)
        body = """\
def main():
    if sys.argv[-1] == "describe":
        print(json.dumps({{"verbs": [{{"name": "list_open", "args": [], "effect": "read"}}]}}))
        return 0
    return 1
sys.exit(main())
"""
        script = _write_fake_registry(tmp_path, body)
        _install_pointer(repo, [sys.executable, str(script)])
        result = _mod.promote(repo)
        assert result["mode"] == "held"
        assert len(_mod.parse_ledger(_mod.ledger_path(repo))) == 1

    def test_ambiguous_write_verbs_is_held(self, tmp_path):
        repo = _init_repo(tmp_path)
        _mod.upsert("lint", "low", "x", root=repo)
        body = """\
def main():
    if sys.argv[-1] == "describe":
        print(json.dumps({{"verbs": [
            {{"name": "a", "args": [], "effect": "write"}},
            {{"name": "b", "args": [], "effect": "write"}},
        ]}}))
        return 0
    return 1
sys.exit(main())
"""
        script = _write_fake_registry(tmp_path, body)
        _install_pointer(repo, [sys.executable, str(script)])
        result = _mod.promote(repo)
        assert result["mode"] == "held"

    def test_unknown_explicit_verb_is_held(self, tmp_path):
        repo = _init_repo(tmp_path)
        _mod.upsert("lint", "low", "x", root=repo)
        script = _write_fake_registry(tmp_path, GOOD_REGISTRY_BODY)
        _install_pointer(
            repo, [sys.executable, str(script)], extra={"promotionVerb": "no_such_verb"}
        )
        result = _mod.promote(repo)
        assert result["mode"] == "held"


# ── promote(): 신선도(D-49·D-50) ─────────────────────────────────────
class TestFreshness:
    def test_head_mismatch_holds_promotion(self, tmp_path):
        repo = _init_repo(tmp_path)
        _mod.upsert("lint", "low", "x", root=repo)
        body = """\
def main():
    if sys.argv[-1] == "describe":
        print(json.dumps({{"verbs": [{{"name": "record", "args": [], "effect": "write"}}], "head": "0" * 40}}))
        return 0
    return 0
sys.exit(main())
"""
        script = _write_fake_registry(tmp_path, body)
        _install_pointer(repo, [sys.executable, str(script)])
        result = _mod.promote(repo)
        assert result["mode"] == "held"
        assert "head" in result["reason"]
        assert len(_mod.parse_ledger(_mod.ledger_path(repo))) == 1

    def test_persistent_mismatch_demotes_to_untrusted(self, tmp_path):
        """되돌려-FAIL 정신: 연속 불일치 임계 초과 시 강등, 이후 폴백으로 고정된다."""
        repo = _init_repo(tmp_path)
        _mod.upsert("lint", "low", "x", root=repo)
        body = """\
def main():
    if sys.argv[-1] == "describe":
        print(json.dumps({{"verbs": [{{"name": "record", "args": [], "effect": "write"}}], "head": "0" * 40}}))
        return 0
    return 0
sys.exit(main())
"""
        script = _write_fake_registry(tmp_path, body)
        _install_pointer(repo, [sys.executable, str(script)])

        results = [_mod.promote(repo) for _ in range(_mod._MISMATCH_DEMOTE_THRESHOLD)]
        assert results[-1]["mode"] == "fallback"
        assert "미신뢰" in results[-1]["reason"]
        # ledger는 강등 전 과정 내내 보존된다
        assert len(_mod.parse_ledger(_mod.ledger_path(repo))) == 1

    def test_undeclared_head_still_promotes(self, tmp_path):
        repo = _init_repo(tmp_path)
        _mod.upsert("lint", "low", "x", root=repo)
        body = """\
def main():
    if sys.argv[-1] == "describe":
        print(json.dumps({{"verbs": [{{"name": "record", "args": [], "effect": "write"}}]}}))
        return 0
    return 0
sys.exit(main())
"""
        script = _write_fake_registry(tmp_path, body)
        _install_pointer(repo, [sys.executable, str(script)])
        result = _mod.promote(repo)
        assert result["mode"] == "promoted"
