"""verify-done.sh §8 이 **활성 계획**의 checklist 만 검사하는가 (W-046).

활성 = 같은 디렉토리 `plan.md` 의 `status` 가 `done` 이 아님. done 계획의 checklist 는
과거 기록이라 미완 항목이 남아 있어도 red 가 아니다. 반대로 done 이라고 **확정할 수
없으면**(plan.md 부재·frontmatter 손상) 검사한다 — 조용한 skip 은 false-green 이다.

§8 블록을 **원문 그대로 추출**해 스텁 레포에서 실행한다(§11 테스트와 같은 방식) —
게이트 전체를 돌리지 않으면서 실제 분기 코드를 검사한다. status 판정은 실물
session-start 파서를 쓰므로 hooks 파일을 스텁 레포에 복사한다.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = REPO_ROOT / "scripts" / "verify-done.sh"
HOOKS = REPO_ROOT / "plugins" / "common" / "hooks"
TOOLS = REPO_ROOT / "plugins" / "common" / "tools"

# `CL_HELPER=` 부터 §8 의 마지막 줄(`[ "$CL_FOUND" -eq 0 ] && green ...`)까지.
_BLOCK_RE = re.compile(
    r'^CL_HELPER=.*?^\[ "\$CL_FOUND" -eq 0 \] && green .*?$', re.DOTALL | re.MULTILINE
)

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell 전용")


def _section_8() -> str:
    m = _BLOCK_RE.search(GATE.read_text(encoding="utf-8"))
    assert m, (
        "§8 checklist 블록을 찾지 못했다 — 게이트 구조가 바뀌었다(테스트를 갱신하라)"
    )
    return m.group(0)


def _plan(root: Path, name: str, status: str | None, passes: list[bool]) -> None:
    d = root / "docs" / "plans" / name
    d.mkdir(parents=True)
    if status is not None:
        (d / "plan.md").write_text(
            f'---\ntitle: "{name}"\nstatus: {status}\n---\n', encoding="utf-8"
        )
    items = [
        {
            "id": f"i{i}",
            "description": "d",
            "acceptance": "a",
            "verify": "true",
            "passes": p,
        }
        for i, p in enumerate(passes)
    ]
    (d / "checklist.json").write_text(json.dumps(items), encoding="utf-8")


def _run(root: Path) -> list[str]:
    hooks = root / "plugins" / "common" / "hooks"
    hooks.mkdir(parents=True)
    for name in ("session-start.py", "utils.py"):
        shutil.copy2(HOOKS / name, hooks / name)
    tools = root / "plugins" / "common" / "tools"
    tools.mkdir(parents=True)
    shutil.copy2(TOOLS / "checklist.py", tools / "checklist.py")
    tmpd = root / "tmpd"
    tmpd.mkdir()
    script = root / "run.sh"
    script.write_text(
        'green() { printf "GREEN %s\\n" "$1"; }\n'
        'red()   { printf "RED %s\\n" "$1"; }\n'
        f'TMPD="{tmpd}"\n' + _section_8() + "\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return proc.stdout.splitlines()


def test_active_plan_with_pending_item_is_red(tmp_path):
    _plan(tmp_path, "2026-09-28-a", "in-progress", [True, False])
    out = _run(tmp_path)
    assert any(ln.startswith("RED checklist 미완/손상: 2026-09-28-a") for ln in out), (
        out
    )


def test_done_plan_checklist_is_history_not_red(tmp_path):
    _plan(tmp_path, "2026-09-01-old", "done", [False])
    _plan(tmp_path, "2026-09-02-old", "done   # planning | in-progress | done", [False])
    out = _run(tmp_path)
    assert not any(ln.startswith("RED") for ln in out), out
    assert any("done 계획 2개는 과거 기록" in ln for ln in out), out


def test_active_plan_all_pass_is_green(tmp_path):
    _plan(tmp_path, "2026-09-28-a", "planning", [True, True])
    out = _run(tmp_path)
    assert out == ["GREEN checklist 전항목 pass: 2026-09-28-a"], out


@pytest.mark.parametrize("status", [None, "broken"])
def test_undeterminable_status_is_checked_not_skipped(tmp_path, status):
    """plan.md 가 없거나 frontmatter 가 손상되면 done 으로 확정할 수 없다 → 검사한다."""
    _plan(tmp_path, "2026-09-28-x", None, [False])
    plan = tmp_path / "docs" / "plans" / "2026-09-28-x" / "plan.md"
    if status == "broken":
        plan.write_text("---\nstatus: done\n(닫는 --- 없음)\n", encoding="utf-8")
    out = _run(tmp_path)
    assert any(ln.startswith("RED checklist 미완/손상: 2026-09-28-x") for ln in out), (
        out
    )


def test_legacy_works_checklist_not_scanned(tmp_path):
    d = tmp_path / "docs" / "works" / "active" / "W-001-x"
    d.mkdir(parents=True)
    (d / "checklist.json").write_text("[]", encoding="utf-8")
    out = _run(tmp_path)
    assert not any(ln.startswith("RED") for ln in out), out
