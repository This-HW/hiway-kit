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

## 파싱하지 못한 파일은 red 다

`ast.parse` 가 실패한 파일을 `return {}` 로 삼키면 *"그림자 정의 0건"* 과 *"이 파일을
읽지도 못했다"* 가 출력에서 같아진다 — 이 게이트가 막으려는 바로 그 false-green 이다.
`git_tracked.SkipTally` 로 집계해 개수·비율·경로를 인쇄하고, `.py` 는 전부 파싱돼야
정상이므로 **읽기 실패도 문법 오류도 red** 로 둔다.

`({len(files)}개 파일)` 이라는 성공 줄도 고쳤다 — 그것은 **시도한 수**였지 실제로
파싱한 수가 아니었다. 전부 못 읽어도 그 줄은 그대로 초록으로 나왔다.
"""

from __future__ import annotations

import ast
import collections
import sys
from pathlib import Path

from git_tracked import SkipTally, tracked_files

REPO_ROOT = Path(__file__).resolve().parent.parent
LABEL = "shadowed-defs"

# `.py` 는 전부 파싱돼야 정상이다 — 못 읽은 파일은 예외 없이 사각지대다(위 독스트링).
# 그래서 **노랑 예외가 하나도 없다**. 기본이 red 이므로 이 빈 집합이 곧 "전부 red" 다
# (git_tracked.SkipTally.report 참고 — 예전의 치명 화이트리스트는 새 사유를 놓쳤다).
NONFATAL_SKIP_REASONS: frozenset = frozenset()


def tracked_python_files() -> list[str]:
    return tracked_files(REPO_ROOT, ("*.py",), label=LABEL)


def shadowed_in(path: Path, rel: str, skipped: SkipTally) -> dict[str, int]:
    """최상위 def/class 중 두 번 이상 나오는 이름 → 등장 횟수.

    읽거나 파싱하지 못하면 `skipped` 에 사유를 기록한다 — 조용히 `{}` 를 돌려주면
    "검사했는데 없음"과 구분되지 않는다.
    """
    skipped.attempted += 1
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as err:
        skipped.add(rel, "읽기실패", str(err))
        return {}
    except UnicodeDecodeError as err:
        skipped.add(rel, "디코딩실패", str(err))
        return {}
    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        skipped.add(rel, "문법오류", f"line {err.lineno}: {err.msg}")
        return {}
    names: collections.Counter[str] = collections.Counter()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names[node.name] += 1
    return {name: count for name, count in names.items() if count > 1}


def main() -> int:
    files = tracked_python_files()
    if not files:
        print(f"[{LABEL}] ✗ 추적 중인 .py 가 없다 — 검사 대상 0개는 green 이 아니다")
        return 1
    skipped = SkipTally(LABEL)
    hits = [(rel, shadowed_in(REPO_ROOT / rel, rel, skipped)) for rel in files]
    hits = [(rel, dup) for rel, dup in hits if dup]
    rc = skipped.report(NONFATAL_SKIP_REASONS)
    if hits:
        print(f"[{LABEL}] ✗ 그림자 정의 {len(hits)}개 파일 — 나중 정의가 앞선 것을 덮는다")
        for rel, dup in hits:
            for name, count in sorted(dup.items()):
                print(f"    {rel}: {name} x{count}")
        return 1
    print(
        f"[{LABEL}] {'✗' if rc else '✓'} 최상위 그림자 정의 0건 "
        f"({skipped.parsed}개 파일 파싱 / 시도 {skipped.attempted}개)"
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())
