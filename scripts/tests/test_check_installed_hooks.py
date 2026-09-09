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
