"""Architecture guard: the admin domain & ports layers must stay framework-free.

Per backend/ARCHITECTURE.md the domain depends only on ports (Protocols) and pure
Python; it imports nothing from infrastructure and no framework packages. Ports may
reference domain types but never infrastructure/ORM. This test statically parses every
module in those packages (including TYPE_CHECKING-only imports) and fails on a violation.
"""

from __future__ import annotations

import ast
from pathlib import Path

import hiresense.admin.domain as domain_pkg
import hiresense.admin.ports as ports_pkg

_FORBIDDEN_PREFIXES = (
    "sqlalchemy",
    "langchain",
    "httpx",
    "fastapi",
    "hiresense.admin.infrastructure",
    "hiresense.adapters",
    "hiresense.infrastructure",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def _py_files(package) -> list[Path]:
    root = Path(package.__file__).parent
    return sorted(p for p in root.glob("*.py"))


def _assert_no_forbidden_imports(package) -> None:
    violations: list[str] = []
    for path in _py_files(package):
        for module in _imported_modules(path):
            if any(module == p or module.startswith(p + ".") for p in _FORBIDDEN_PREFIXES):
                violations.append(f"{path.name} imports {module}")
    assert not violations, "forbidden imports in admin layer:\n" + "\n".join(violations)


def test_domain_has_no_infrastructure_or_framework_imports() -> None:
    _assert_no_forbidden_imports(domain_pkg)


def test_ports_reference_no_infrastructure_or_framework() -> None:
    _assert_no_forbidden_imports(ports_pkg)
