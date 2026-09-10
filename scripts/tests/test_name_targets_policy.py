"""`packaging/name-targets.json` 이 **이름이 박힐 수 있는 곳 전부**를 대상으로 삼는가.

`test_derive_name.py` 는 픽스처 레포로 파생 *메커니즘*을 검사한다. 이 파일은 다르다 —
**실물 정책이 실물 레포를 덮는가**를 본다. 픽스처에서 초록인 도구가 실물에 닿기 전에는
검증되지 않았다는 것이 `docs/conventions/warning-signal.md` §측정 1 의 교훈이다.

## 왜 setup 훅인가 (검사 조건 한 문장 — §검토 절차 4)

**`plugins/common/setup/` 아래 킷이 배포하는 훅 스크립트가 SSOT 제품명을 리터럴로
담고 있는데 파생 대상이 아니면 red.**

실측(2026-09-10): `git-hooks/pre-push:154` 의 사용자 대면 차단 메시지가
`"… (hiway-kit git 훅)"` 였는데 정책의 `files` 에 없었다 — 개명하면 사람이 읽는 바로
그 줄만 구 이름으로 남는다. 같은 파일이 마커에 대해서는 *"제품명을 넣지 않는다"* 고
이미 규정하고 있었으므로 같은 클래스의 누락이다.

인스턴스만 고치지 않았다. 클래스를 물었더니 **sibling 훅 둘에 같은 형태가 있었다** —
`reference-transaction:76` 은 글자 그대로 같은 차단 메시지, `pre-commit:2` 는 헤더
주석. 셋 다 등재했고, 이 테스트가 넷째를 막는다.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
POLICY_PATH = REPO_ROOT / "packaging" / "name-targets.json"
SETUP_DIR = REPO_ROOT / "plugins" / "common" / "setup"

# 훅이 아닌 것만 제외한다 — 대상을 나열하면 새 훅이 조용히 커버리지 밖이 된다
# (`warning-signal.md` §검토 절차 5: 대상이 아니라 제외를 나열한다).
NON_HOOK_SUFFIXES = (".md", ".sample", ".bak", ".orig", ".rej", "~", ".pyc")


def _policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _ssot_name() -> str:
    src = _policy()["source"]
    manifest = json.loads((REPO_ROOT / src["manifest"]).read_text(encoding="utf-8"))
    return manifest[src["field"]]


def _setup_hook_sources() -> list[Path]:
    return sorted(
        p
        for p in SETUP_DIR.rglob("*")
        if p.is_file()
        and not p.name.endswith(NON_HOOK_SUFFIXES)
        and not p.name.startswith(".")
        and "__pycache__" not in p.parts
    )


def test_every_setup_hook_hardcoding_the_name_is_a_derivation_target():
    """**핵심 회귀**: 제품명을 리터럴로 담은 setup 훅은 예외 없이 파생 대상이다."""
    name = _ssot_name()
    targets = set(_policy().get("files", []))
    missing = []
    for src in _setup_hook_sources():
        rel = src.relative_to(REPO_ROOT).as_posix()
        try:
            body = src.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # 바이너리는 리터럴 치환 대상이 아니다
        if name in body and rel not in targets:
            missing.append(rel)
    assert not missing, (
        "제품명이 박혔는데 파생 대상이 아닌 setup 훅 — 개명하면 이 파일만 구 이름으로 "
        f"남는다: {missing}\n  → packaging/name-targets.json 의 files 에 등재하라."
    )


def test_the_known_instances_are_registered():
    """클래스 검사가 무언가를 잘못 세도 이 셋은 반드시 등재돼 있어야 한다."""
    targets = set(_policy().get("files", []))
    for rel in (
        "plugins/common/setup/git-hooks/pre-push",
        "plugins/common/setup/git-hooks/reference-transaction",
        "plugins/common/setup/pre-commit",
    ):
        assert rel in targets, f"{rel} 이 파생 대상에서 빠졌다"


def test_the_class_scan_actually_sees_files():
    """음성 결과는 '도달했다'를 따로 증명한다 (`warning-signal.md` §측정 3).

    스캔이 0건이면 `test_every_setup_hook…` 은 아무것도 검사하지 않고 초록이 된다.
    """
    srcs = _setup_hook_sources()
    assert len(srcs) >= 3, f"setup 훅 스캔이 도달하지 않았다: {srcs}"
    name = _ssot_name()
    hits = [p for p in srcs if name in p.read_text(encoding="utf-8", errors="ignore")]
    assert hits, "제품명을 담은 훅을 하나도 못 찾았다 — 스캔이 실제로 돌지 않았다"


def test_every_declared_target_exists():
    """존재하지 않는 대상은 `derive-name --check` 에서 red 다 — 여기서 먼저 말한다."""
    missing = [
        rel for rel in _policy().get("files", []) if not (REPO_ROOT / rel).is_file()
    ]
    assert not missing, f"정책이 없는 파일을 대상으로 선언했다: {missing}"
