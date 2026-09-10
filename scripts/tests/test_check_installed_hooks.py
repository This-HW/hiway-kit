"""Unit tests for scripts/check_installed_hooks.py — 나열→파생 회귀 방지.

이 게이트의 대상 목록은 원래 **손으로 나열**돼 있었고, 그 옆에 *"훅은 소수이고 각각
미설치 의미가 달라 제외 방식이 맞지 않는다"* 는 정당화까지 적혀 있었다. **바로 다음에
추가된 훅(`pre-push`)이 그 나열에서 빠졌고**, 등록되지 않은 훅의 드리프트는 영원히
잡히지 않는 상태였다 — `warning-signal.md` §검토 절차 5 가 예측한 그대로다.

그래서 여기 걸어 두는 것은 "지금 훅 3종이 검사된다"가 아니라 **"새 훅이 디렉토리에
놓이는 것만으로 대상이 되는가"** 다. 앞엣것은 훅을 추가할 때마다 낡지만, 뒤엣것은
낡지 않는다 — 이 파일이 막으려는 결함이 정확히 그 차이다.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from module_loader import load_module_by_path

MARKED = "#!/bin/bash\n# kit-managed-hook\necho guard\n"
AUTO_MARKED = "#!/bin/bash\n# Auto-installed by session-check.py\necho lint\n"


def _mod(tmp_path: Path, *, installed: dict[str, str] | None = None):
    """가짜 레포 루트 + 가짜 `.git/hooks` 로 모듈을 조립한다."""
    mod = load_module_by_path(
        SCRIPTS_DIR / "check_installed_hooks.py", "check_installed_hooks_t"
    )
    root = tmp_path / "repo"
    (root / "plugins" / "common" / "setup" / "git-hooks").mkdir(parents=True)
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    for name, body in (installed or {}).items():
        (hooks / name).write_text(body, encoding="utf-8")
    mod.REPO_ROOT = root
    mod.hooks_dir = lambda: hooks
    return mod, root, hooks


def _opt_in(root: Path) -> Path:
    return root / "plugins" / "common" / "setup" / "git-hooks"


def test_new_hook_is_discovered_without_registration(tmp_path):
    """★핵심 회귀: 디렉토리에 놓기만 해도 대상이 된다 (나열이면 여기서 실패한다)."""
    mod, root, _ = _mod(tmp_path)
    (_opt_in(root) / "brand-new-hook").write_text(MARKED, encoding="utf-8")

    targets, unmarked = mod.discover_hooks()

    assert unmarked == []
    assert [name for _, name, _, _ in targets] == ["brand-new-hook"]


def test_opt_in_location_derives_silent_missing(tmp_path):
    """미설치 의미는 **위치에서 파생**된다 — git-hooks/ 는 안 켠 것이 정상이다."""
    mod, root, _ = _mod(tmp_path)
    (_opt_in(root) / "some-hook").write_text(MARKED, encoding="utf-8")

    targets, _ = mod.discover_hooks()
    assert [(name, notify) for _, name, _, notify in targets] == [("some-hook", False)]


def test_auto_installed_location_derives_notify(tmp_path):
    """`setup/pre-commit` 은 자동 설치 대상이라 없으면 알린다."""
    mod, root, _ = _mod(tmp_path)
    (root / "plugins" / "common" / "setup" / "pre-commit").write_text(
        AUTO_MARKED, encoding="utf-8"
    )

    targets, _ = mod.discover_hooks()
    assert [(name, notify) for _, name, _, notify in targets] == [("pre-commit", True)]


def test_unmarked_source_is_red_not_skipped(tmp_path, capsys):
    """마커 없는 킷 훅은 **조용히 건너뛰지 않는다** — 대조 수단이 없으면 그건 결함이다."""
    mod, root, _ = _mod(tmp_path)
    (_opt_in(root) / "no-marker").write_text("#!/bin/bash\necho hi\n", encoding="utf-8")

    assert mod.main() == 1
    assert "드리프트 마커가 없다" in capsys.readouterr().out


def test_zero_targets_is_red(tmp_path, capsys):
    """0 건은 통과가 아니다 — 파생 경로가 깨졌다는 뜻이다(이 레포의 false-green 정책)."""
    mod, _, _ = _mod(tmp_path)

    assert mod.main() == 1
    assert "하나도 찾지 못했다" in capsys.readouterr().out


def test_installed_drift_is_yellow_not_red(tmp_path, capsys):
    """훅 소스를 고치는 중에는 repo 가 앞선 것이 정상이라 red 로 두지 않는다."""
    mod, root, _ = _mod(tmp_path, installed={"some-hook": MARKED + "# drifted\n"})
    (_opt_in(root) / "some-hook").write_text(MARKED, encoding="utf-8")

    assert mod.main() == 0
    assert "repo 정본과 다르다" in capsys.readouterr().out


def test_consumer_owned_hook_is_left_alone(tmp_path, capsys):
    """마커 없는 **설치본**은 소비자 소유다 — 손대지도 대조하지도 않는다."""
    mod, root, _ = _mod(tmp_path, installed={"some-hook": "#!/bin/bash\nmine\n"})
    (_opt_in(root) / "some-hook").write_text(MARKED, encoding="utf-8")

    assert mod.main() == 0
    assert "킷 소유가 아니다" in capsys.readouterr().out


# ── hooks 경로는 저장소당 한 번 구한다 (L-9) ─────────────────────────────


def test_hooks_dir_is_resolved_once_per_run(tmp_path):
    """`check_one` 이 훅마다 `git rev-parse` 를 다시 부르지 않는다.

    결과는 이 저장소에서 불변이므로 비용이 문제가 아니다 — 읽는 사람에게 **"훅마다
    hooks 경로가 다를 수 있다"는 잘못된 인상**을 주는 것이 문제다. 게이트는 읽기
    쉬워야 신뢰된다(`docs/conventions/no-gate-integration.md`).
    """
    mod, root, _hooks = _mod(tmp_path, installed={"a-hook": MARKED, "b-hook": MARKED})
    for name in ("a-hook", "b-hook", "c-hook"):
        (_opt_in(root) / name).write_text(MARKED, encoding="utf-8")

    calls = []
    real = mod.hooks_dir

    def counting():
        calls.append(1)
        return real()

    mod.hooks_dir = counting
    mod.main()
    assert len(calls) == 1, (
        f"훅 3종에 대해 hooks_dir() 를 {len(calls)}회 불렀다 — 저장소당 1회여야 한다"
    )


def test_check_one_takes_hooks_as_a_parameter(tmp_path):
    """의존성은 주입된다 — `check_one` 이 내부에서 경로를 조회하면 시그니처가 다르다."""
    import inspect

    mod, _, _ = _mod(tmp_path)
    params = list(inspect.signature(mod.check_one).parameters)
    assert params[0] == "hooks", f"check_one 이 hooks 를 인자로 받지 않는다: {params}"


def test_unavailable_hooks_dir_reports_once_not_per_hook(tmp_path, capsys):
    """경로를 못 얻으면 훅마다 같은 줄을 반복하지 않고 한 번 말한다 — 그리고 통과가 아니다."""
    mod, root, _ = _mod(tmp_path)
    for name in ("a-hook", "b-hook", "c-hook"):
        (_opt_in(root) / name).write_text(MARKED, encoding="utf-8")
    mod.hooks_dir = lambda: None
    mod.main()
    out = capsys.readouterr().out
    assert out.count("git hooks 경로를 얻지 못했다") == 1, out
    assert "통과가 아니다" in out, "검사하지 못한 것을 초록처럼 보이게 두지 않는다"
