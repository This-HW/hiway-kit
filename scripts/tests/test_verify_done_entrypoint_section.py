"""verify-done.sh §11 이 `export-harness --check` 의 종료코드를 **구분해서** 보고하는가.

`export_harness.py` 는 종료코드 셋을 의미 있게 나눈다:

- `0` 최신 · `2` 규범 소스 미탐지(SKIPPED)
- `3` **부분 성공** — 규범 블록(첫 번째)은 기록·검사했고 conventions 블록만 건너뜀
- `1` 그 외(드리프트 · 분류 미등재 · 마커 손상 · 본문 변조 …)

§11 이 `3` 을 `else` 로 뭉개면 red 인 것 자체는 맞아도 *"진입점 검사 실패"* 로 인쇄돼,
읽는 사람이 규범 블록까지 드리프트한 줄 알고 재생성을 돌린다 — 그리고 재생성은 이
상태를 고치지 못한다(원인이 conventions 소스 쪽이다). 게이트는 읽기 쉬워야 신뢰된다
(`docs/conventions/no-gate-integration.md`).

이 테스트는 §11 블록을 **원문 그대로 추출**해 스텁 환경에서 실행한다 — 게이트 전체를
돌리지 않으면서도 실제 분기 코드를 검사한다.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = REPO_ROOT / "scripts" / "verify-done.sh"

# `if [ -f scripts/export-harness.sh ] ...` 부터 짝 맞는 `fi` 까지.
_BLOCK_RE = re.compile(
    r"^if \[ -f scripts/export-harness\.sh \].*?^fi$", re.DOTALL | re.MULTILINE
)


def _section_11() -> str:
    m = _BLOCK_RE.search(GATE.read_text(encoding="utf-8"))
    assert m, "§11 진입점 블록을 찾지 못했다 — 게이트 구조가 바뀌었다(테스트를 갱신하라)"
    return m.group(0)


def _run(tmp_path: Path, rc: int) -> str:
    """스텁 `export-harness.sh` 가 `rc` 로 끝나는 환경에서 §11 블록만 실행한다."""
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "plugins" / "common" / "hooks").mkdir(parents=True)
    (tmp_path / "plugins" / "common" / "hooks" / "export_harness.py").write_text("")
    stub = tmp_path / "scripts" / "export-harness.sh"
    stub.write_text(f"#!/bin/sh\necho '스텁 출력 한 줄'\nexit {rc}\n", encoding="utf-8")
    stub.chmod(0o755)

    tmpd = tmp_path / "tmpd"
    tmpd.mkdir()
    harness = (
        'green() { printf "GREEN %s\\n" "$1"; }\n'
        'red()   { printf "RED %s\\n" "$1"; }\n'
        f'TMPD="{tmpd}"\n'
    ) + _section_11() + "\n"
    script = tmp_path / "run.sh"
    script.write_text(harness, encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(script)], cwd=str(tmp_path),
        capture_output=True, text=True, check=False, timeout=30,
    )
    return proc.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell 전용")
def test_rc3_reports_conventions_only_not_generic_failure(tmp_path):
    """**핵심 회귀**: 3은 고유 메시지를 갖는다 — 일반 실패 문구로 뭉개지 않는다."""
    out = _run(tmp_path, 3)
    assert out.startswith("RED "), f"3은 red 여야 한다: {out!r}"
    assert "conventions" in out, f"무엇이 red 인지 말하지 않았다: {out!r}"
    assert "진입점 검사 실패" not in out, (
        f"부분 성공(3)을 일반 실패로 뭉갰다 — 재생성으로 안 고쳐지는데 재생성을 시킨다: {out!r}"
    )


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell 전용")
def test_rc0_is_green(tmp_path):
    assert _run(tmp_path, 0).startswith("GREEN ")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell 전용")
def test_rc2_is_skipped_message(tmp_path):
    out = _run(tmp_path, 2)
    assert out.startswith("RED ") and "SKIPPED" in out


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell 전용")
def test_rc1_keeps_the_generic_failure_message(tmp_path):
    """대칭 확인 — 1은 여전히 일반 실패다(3 분기가 1까지 삼키지 않았다)."""
    out = _run(tmp_path, 1)
    assert out.startswith("RED ") and "진입점 검사 실패" in out


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell 전용")
def test_every_documented_exit_code_has_its_own_message(tmp_path):
    """0·1·2·3 이 서로 다른 줄을 낸다 — 하나라도 겹치면 읽는 사람이 원인을 못 가른다."""
    firsts = {rc: _run(tmp_path / f"rc{rc}", rc).splitlines()[0] for rc in (0, 1, 2, 3)}
    assert len(set(firsts.values())) == 4, f"종료코드 메시지가 겹친다: {firsts}"
