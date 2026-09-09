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


# ── ATK-001: promote()가 도는 동안 추가된 항목은 사라지지 않는다 ─────
class TestPromoteConcurrentWrite:
    """불변식: promote 가 도는 동안 원장에 추가된 항목은 **절대 사라지지 않는다.**

    초판은 `_ledger_lock` 을 **잡은 채** 항목마다 승격 subprocess 를 돌리고, 끝나면
    `_write_ledger(path, [])` 로 파일 전체를 비웠다. `_LOCK_TIMEOUT_SECONDS`(5초)는
    **의도된 fail-open** 이라 그 사이 다른 프로세스의 upsert 는 **무락으로** 원장에
    쓴다 — 그 항목은 승격도 보존도 되지 않고 소멸했다(ATK-001, 배포 차단).

    스레드로는 이 창을 결정적으로 못 벌린다. 그래서 **승격 호출 자체**가 원장에
    쓰게 만든다 — 락 밖 무락 쓰기와 관측적으로 동일하고, 결정적이다.
    """

    @staticmethod
    def _racing_registry(tmp_path: Path, ledger: Path, row: str) -> Path:
        script = tmp_path / "racing_registry.py"
        script.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import json, sys
                LEDGER = {ledger!r}
                ROW = {row!r}
                def main():
                    if sys.argv[-1] == "describe":
                        print(json.dumps({{"verbs": [
                            {{"name": "record", "args": ["payload"], "effect": "write"}}
                        ]}}))
                        return 0
                    # 승격 호출이 도는 **동안** 다른 프로세스가 원장에 쓴다.
                    with open(LEDGER, "a", encoding="utf-8") as fh:
                        fh.write(ROW)
                    return 0
                sys.exit(main())
                """
            ).format(ledger=str(ledger), row=row)
        )
        return script

    def test_entry_added_during_promotion_is_not_lost(self, tmp_path):
        repo = _init_repo(tmp_path)
        _mod.upsert("security", "high", "claimed before promote", root=repo)
        ledger = _mod.ledger_path(repo)
        script = self._racing_registry(
            tmp_path,
            ledger,
            "| F-900 | lint | arrived during promote | 1 | 2026-01-01 | low |\n",
        )
        _install_pointer(repo, [sys.executable, str(script)])

        result = _mod.promote(repo)
        assert result["mode"] == "promoted"
        assert result["count"] == 1

        patterns = [e["pattern"] for e in _mod.parse_ledger(ledger)]
        assert "arrived during promote" in patterns, (
            "승격 중 추가된 항목이 사라졌다 — promote 가 원장을 통째로 비웠다(ATK-001)"
        )
        # 승격에 성공한 것은 정확히 제거된다(전체 비우기가 아니라 차집합).
        assert "claimed before promote" not in patterns

    def test_lock_is_not_held_across_promotion_subprocess(self, tmp_path):
        """락을 잡은 채 subprocess 를 돌리지 않는다 — 구조 자체를 검사한다.

        결과만 보는 위 테스트는 "비우지 않는다"로도 통과할 수 있다. 이 테스트는
        원인(락 보유 중 외부 호출)을 직접 잡는다.
        """
        repo = _init_repo(tmp_path)
        _mod.upsert("lint", "low", "x", root=repo)
        script = _write_fake_registry(tmp_path, GOOD_REGISTRY_BODY)
        _install_pointer(repo, [sys.executable, str(script)])

        held = {"depth": 0}
        real_lock = _mod._ledger_lock
        real_run = _mod.subprocess.run

        @_mod.contextmanager
        def counting_lock(path):
            held["depth"] += 1
            try:
                with real_lock(path):
                    yield
            finally:
                held["depth"] -= 1

        calls_under_lock = []

        def watching_run(cmd, **kw):
            if held["depth"] > 0 and isinstance(cmd, list) and "record" in cmd:
                calls_under_lock.append(cmd)
            return real_run(cmd, **kw)

        _mod._ledger_lock = counting_lock
        _mod.subprocess.run = watching_run
        try:
            assert _mod.promote(repo)["mode"] == "promoted"
        finally:
            _mod._ledger_lock = real_lock
            _mod.subprocess.run = real_run

        assert calls_under_lock == [], (
            f"락을 잡은 채 승격 subprocess 를 호출했다: {calls_under_lock}"
        )


# ── ATK-001: 차집합 계산 단위 테스트 ─────────────────────────────────
class TestRemainingAfterPromotion:
    @staticmethod
    def _row(pattern, freq, category="lint"):
        return {
            "id": "F-001",
            "category": category,
            "pattern": pattern,
            "frequency": freq,
            "last_seen": "2026-01-01",
            "severity": "low",
        }

    def test_promoted_entry_is_removed(self):
        claimed = [self._row("a", 1)]
        assert _mod._remaining_after_promotion(list(claimed), claimed) == []

    def test_new_entry_survives(self):
        claimed = [self._row("a", 1)]
        current = [*claimed, self._row("b", 1)]
        kept = _mod._remaining_after_promotion(current, claimed)
        assert [e["pattern"] for e in kept] == ["b"]

    def test_frequency_increment_during_promotion_survives(self):
        """승격 중 같은 패턴이 다시 관측돼 freq 가 올랐으면 그 증분은 남아야 한다."""
        claimed = [self._row("a", 2)]
        current = [self._row("a", 5)]
        kept = _mod._remaining_after_promotion(current, claimed)
        assert len(kept) == 1 and kept[0]["frequency"] == 3
