"""공유 적대적 케이스 표 — `_resolve_in_repo`류 경로 봉쇄 헬퍼의 계약 (D-15).

`scripts/check_eval_coverage.py::_resolve_in_repo`와 `scripts/build-targets.py::
_resolve_in_repo`는 이름과 시그니처(`(container_root: Path, rel_path: str) ->
tuple[Path | None, str | None]`)를 공유하지만 **구현은 합치지 않는다** — D-15
("구현은 여러 벌, 계약만 하나"). 대신 이 모듈이 계약을 검증하는 적대적 케이스를
한 곳에 모아 두고, 두 구현의 테스트 파일이 각자 이 표로 자신의 구현을 검증한다.

이름이 `test_*.py`가 아니므로 pytest가 이 파일 자체를 테스트로 수집하지 않는다
(테스트가 아니라 두 테스트 파일이 import하는 헬퍼 모듈이다). `scripts/tests/`에는
`__init__.py`가 없어 pytest의 기본 import-mode(prepend)가 이 디렉토리를 sys.path에
얹는다 — `test_eval_coverage.py`/`test_build_targets.py`와 동일한 관례로
`import resolve_in_repo_contract`가 그대로 동작한다.

케이스 4종:
- 절대경로 탈출
- `..` 상대경로 순회 탈출
- 심링크 탈출
- (대조군) 컨테이너 안의 정상 상대경로 — 과도한 봉쇄로 인한 false-red 방지
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

ResolveFn = Callable[[Path, str], "tuple[Path | None, str | None]"]


class ResolveCase(NamedTuple):
    name: str
    # container_root(아직 존재하지 않을 수 있음)를 받아 실물 파일/심링크를 심고
    # `_resolve_in_repo`에 넘길 rel_path 문자열을 반환한다.
    setup: Callable[[Path], str]
    should_escape: bool  # True면 (None, error) 기대, False면 (Path, None) 기대


def _absolute_path_escape(container_root: Path) -> str:
    outside = container_root.parent / "outside-abs.txt"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("x", encoding="utf-8")
    return str(outside)


def _dotdot_traversal_escape(container_root: Path) -> str:
    container_root.mkdir(parents=True, exist_ok=True)
    outside = container_root.parent / "outside-dotdot.txt"
    outside.write_text("x", encoding="utf-8")
    # container_root가 실물 디렉토리로 존재해야 '..' 순회가 실제로 일어난다 —
    # 없으면 "탈출이 막혀서"가 아니라 "애초에 순회가 안 돼서" 통과하는 가짜
    # 테스트가 된다(test_eval_coverage.py의 동일 관찰 참고).
    return os.path.join("..", outside.name)


def _symlink_escape(container_root: Path) -> str:
    container_root.mkdir(parents=True, exist_ok=True)
    outside = container_root.parent / "outside-symlink.txt"
    outside.write_text("x", encoding="utf-8")
    link = container_root / "linked.txt"
    link.symlink_to(outside)
    return "linked.txt"


def _valid_relative_path_within_container(container_root: Path) -> str:
    container_root.mkdir(parents=True, exist_ok=True)
    (container_root / "inside.txt").write_text("x", encoding="utf-8")
    return "inside.txt"


CASES: list[ResolveCase] = [
    ResolveCase("absolute_path_escape", _absolute_path_escape, True),
    ResolveCase("dotdot_traversal_escape", _dotdot_traversal_escape, True),
    ResolveCase("symlink_escape", _symlink_escape, True),
    ResolveCase(
        "valid_relative_path_within_container",
        _valid_relative_path_within_container,
        False,
    ),
]


def assert_resolve_in_repo_contract(resolve_fn: ResolveFn, tmp_path: Path) -> None:
    """`resolve_fn`이 `CASES` 전체에 대해 봉쇄 계약을 지키는지 검증한다.

    케이스마다 독립된 `container_root`(tmp_path 하위 전용 디렉토리)를 써서 서로
    간섭하지 않게 한다. `resolve_fn`을 케이스당 정확히 한 번만 호출한다 — 호출자가
    반환값을 재사용해야 한다는 TOCTOU 방지 계약(모듈 docstring)과 같은 원칙이다.
    """
    for case in CASES:
        container_root = tmp_path / case.name / "container"
        rel_path = case.setup(container_root)
        result_path, error = resolve_fn(container_root, rel_path)
        if case.should_escape:
            assert result_path is None, (
                f"{case.name}: 탈출이 차단되지 않음 → {result_path}"
            )
            assert error, f"{case.name}: 차단됐는데 에러 메시지가 없음"
        else:
            assert result_path is not None, f"{case.name}: 정상 경로가 차단됨 — {error}"
            assert error is None, f"{case.name}: 정상 경로인데 에러 반환 — {error}"
