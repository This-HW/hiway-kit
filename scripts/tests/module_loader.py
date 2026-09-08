"""scripts/tests/ 전체가 공유하는 `spec_from_file_location` 로더 (D-14 / 25-8).

scripts/ 에 __init__.py 가 없어 일반 import 가 안 되므로, 하이픈 파일명
(`build-targets.py` 등)을 포함해 스크립트를 경로 기반으로 로드한다. 파일명은
개명하지 않는다 (D-14 — 약 40개 파일이 그 이름을 참조하고 다수가 불변 기록이다).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_module_by_path(path: Path, name: str) -> ModuleType:
    """`path` 의 파이썬 파일을 `name` 모듈로 로드해 반환한다.

    exec 전에 sys.modules 에 등록한다 — 로드 대상에 `@dataclass` 가 있으면 그
    클래스가 소속 모듈을 sys.modules 에서 찾는데, 미등록 상태면 3.10+ 에서
    AttributeError 로 죽는다 (check_eval_coverage.py 의 `_ckkit_eval_run` 로더와
    동일 사유). 로드 후에는 제거해 다른 테스트 모듈과 이름이 섞이지 않게 한다.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod
