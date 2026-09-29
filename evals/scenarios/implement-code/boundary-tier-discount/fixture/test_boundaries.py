"""`.importlinter` 의 계약(domain 은 infra 를 import 하지 않는다)을 pytest 안에서 재현하는 검사.

이 환경에는 import-linter 를 설치하지 않으므로 AST 로 같은 규칙을 본다.
"""
import ast
from pathlib import Path

DOMAIN = Path(__file__).parent / "shop" / "domain"


def _imported_modules(path: Path):
    pkg = ["shop", "domain"]
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            base = ".".join(pkg[: len(pkg) - (node.level - 1)]) if node.level else ""
            mod = ".".join(p for p in (base, node.module or "") if p)
            yield mod
            for alias in node.names:
                yield f"{mod}.{alias.name}"


def test_domain_does_not_import_infra():
    offenders = [
        f"{p.name}: {m}"
        for p in DOMAIN.rglob("*.py")
        for m in _imported_modules(p)
        if m == "shop.infra" or m.startswith("shop.infra.")
    ]
    assert not offenders, offenders
