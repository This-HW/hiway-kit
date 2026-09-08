#!/usr/bin/env python3
"""가짜 레지스트리 파사드 — check_registry_describe.py를 실제 컨트롤 레지스트리
없이 테스트하기 위한 픽스처(26-17). `FAKE_REGISTRY_MODE` 환경변수로 동작을
바꾼다. 마지막 인자가 `describe`가 아니면 미지원 동사로 취급해 실패한다.

모드:
  good            — 스키마 정상, 모든 effect 명시, head = 실제 현재 git HEAD
  missing_args    — 한 동사의 'args' 필드 누락(스키마 위반)
  undeclared_effect — 한 동사의 'effect' 미선언(fail-closed 분류 대상, 실패 아님)
  bad_json        — 유효하지 않은 JSON 출력
  nonzero_exit    — 종료코드 1
  head_mismatch   — head를 실제와 다른 값으로 고정 보고
  static_head:<sha> — head를 주어진 고정값으로 보고(기동 커밋 패턴 테스트용)
"""

from __future__ import annotations

import json
import subprocess
import sys


def _actual_head() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    return r.stdout.strip()


def main() -> int:
    import os

    mode = os.environ.get("FAKE_REGISTRY_MODE", "good")

    if not sys.argv[1:] or sys.argv[-1] != "describe":
        print("unsupported verb", file=sys.stderr)
        return 1

    if mode == "bad_json":
        print("{ not valid json")
        return 0

    if mode == "nonzero_exit":
        print("boom", file=sys.stderr)
        return 1

    verbs = [
        {"name": "list_open", "args": [], "effect": "read", "idempotent": True},
        {
            "name": "register_defect",
            "args": ["category", "pattern"],
            "effect": "write",
            "idempotent": False,
        },
    ]
    head = _actual_head()

    if mode == "missing_args":
        verbs.append({"name": "broken_verb", "effect": "read"})
    elif mode == "undeclared_effect":
        verbs.append({"name": "mystery_verb", "args": []})
    elif mode == "head_mismatch":
        head = "0" * 40
    elif mode.startswith("static_head:"):
        head = mode.split(":", 1)[1]

    response = {"verbs": verbs, "head": head}
    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    sys.exit(main())
