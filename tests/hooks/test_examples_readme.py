"""hooks/examples/README.md — opt-in 훅 안내가 '붙여넣어 실행'을 부르지 않는가 (v5.0.0 A8)."""

import re
from pathlib import Path

README = Path(__file__).resolve().parents[2] / "plugins" / "common" / "hooks" / "examples" / "README.md"


def _shell_blocks(text: str) -> list[str]:
    return re.findall(r"^```(?:bash|sh|shell)\n(.*?)^```", text, re.MULTILINE | re.DOTALL)


def test_no_copy_paste_install_block():
    """설치는 절차 서술로만 — cp/chmod 셸 블록은 읽지 않고 실행하는 경로가 된다."""
    blocks = _shell_blocks(README.read_text(encoding="utf-8"))
    offenders = [b for b in blocks if re.search(r"^\s*(cp|chmod)\b", b, re.MULTILINE)]
    assert not offenders, offenders


def test_test_paths_cited_exist():
    """README 가 인용하는 회귀 테스트 경로가 실재한다(테스트 이동 A9 뒤 낡지 않게)."""
    repo = README.parents[4]
    cited = re.findall(r"`(tests/[\w/]+\.py)`", README.read_text(encoding="utf-8"))
    assert cited
    missing = [c for c in cited if not (repo / c).is_file()]
    assert not missing, missing
