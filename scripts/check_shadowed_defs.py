#!/usr/bin/env python3
"""check_shadowed_defs.py — 같은 모듈에 같은 이름의 최상위 정의가 둘 있는지 검사한다.

## 무엇을 막는가

파일 끝에 헬퍼를 덧붙이면서 **기존 이름을 다시 정의**하면 파이썬은 조용히 나중 것을
쓴다. 앞선 테스트들이 말없이 새 정의를 쓰게 되고 — **테스트는 계속 통과하는데 다른
것을 재고 있다.** 이 레포가 가장 나쁘게 보는 false-green 이다(F-012: 검사 0건을
green 으로 보고하는 것은 정합이 아니라 손상이다).

## 왜 ruff 로 부족한가 (실측 2026-09-09)

`ruff` 의 **F811**(Redefinition of unused name)이 정확히 이 결함이고 `select` 에
켜져 있다. **그런데 밑줄로 시작하는 이름에는 발화하지 않는다** — ruff 가 `_` 접두를
`dummy-variable-rgx` 로 "의도적 미사용"으로 보고 면제하기 때문이다:

    def helper(): ...  → 재정의 시 F811 발화
    def _helper(): ... → 재정의 시 **침묵**

그리고 **밑줄 접두는 이 레포 테스트 헬퍼의 기본 명명 관례**다(`_run_in_repo`,
`_init_repo`, `_fake_plugin_root` …). 면제 범위가 정확히 위험 지대와 겹쳤다.

`dummy-variable-rgx = "^_$"` 로 좁히면 F811 이 잡지만, 그 설정은 F841·B007·RUF059 와
**공유**라 `_scenario`·`_lines` 같은 **서술적 폐기 이름 10곳이 `_` 한 글자로 강등**된다.
버리는 값이 무엇인지 이름으로 말하는 편이 낫다 — 그 가독성을 이 검사 하나와 바꾸지 않는다.

## 검사 조건 (한 문장)

**추적 중인 모든 `.py` 에서, 한 모듈의 최상위 `def`/`class` 이름이 두 번 이상 나오면 fail.**
분기가 없다 — 항상 돈다(`docs/conventions/warning-signal.md` §검토 절차 4).

클래스 메서드는 별개 스코프이므로 최상위만 본다. 정규식이 아니라 **AST** 로 읽는다 —
이름을 자르는 오탐(`test_tier1…`/`test_tier2…`)과 문자열·주석 안 코드를 둘 다 피한다.
"""

from __future__ import annotations

import ast
import collections
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def tracked_python_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(f"[shadowed-defs] git ls-files 실패: {result.stderr.strip()}")
        raise SystemExit(1)
    return [line for line in result.stdout.splitlines() if line]


def shadowed_in(path: Path) -> dict[str, int]:
    """최상위 def/class 중 두 번 이상 나오는 이름 → 등장 횟수."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return {}
    names: collections.Counter[str] = collections.Counter()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names[node.name] += 1
    return {name: count for name, count in names.items() if count > 1}


def main() -> int:
    files = tracked_python_files()
    if not files:
        print("[shadowed-defs] 추적 중인 .py 가 없다 — 검사 대상 0개는 green 이 아니다")
        return 1
    hits = [(rel, shadowed_in(REPO_ROOT / rel)) for rel in files]
    hits = [(rel, dup) for rel, dup in hits if dup]
    if not hits:
        print(f"[shadowed-defs] ✓ 최상위 그림자 정의 0건 ({len(files)}개 파일)")
        return 0
    print(f"[shadowed-defs] ✗ 그림자 정의 {len(hits)}개 파일 — 나중 정의가 앞선 것을 덮는다")
    for rel, dup in hits:
        for name, count in sorted(dup.items()):
            print(f"    {rel}: {name} x{count}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
