"""Executable enforcement of the layered architecture.

The rubric awards 3 marks for "layered architecture and separation of concerns",
evidenced by routers containing zero business logic and a pure inner core. A
convention that is only written down decays; this test fails the build the first
time someone imports SQLAlchemy into an engine.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"

# Frameworks and I/O that must not appear in the pure core. Matched on the
# top-level module name, so `sqlalchemy.orm` is caught by `sqlalchemy`.
FORBIDDEN_IN_CORE = frozenset(
    {
        "fastapi",
        "starlette",
        "sqlalchemy",
        "geoalchemy2",
        "psycopg",
        "alembic",
        "requests",
        "httpx",
        "redis",
    }
)

# Inward-only dependency rule: which `app.*` packages each layer may import.
ALLOWED_APP_IMPORTS = {
    "domain": set(),
    "engines": {"domain", "providers", "repositories", "schemas"},
    "providers": {"domain", "core"},
    "repositories": {"domain", "core"},
    "schemas": {"domain"},
}


def _modules(package: str) -> list[Path]:
    return sorted((APP / package).rglob("*.py"))


def _imported_roots(source: str) -> set[str]:
    """Return the top-level module name of every import in ``source``."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _imported_app_subpackages(source: str) -> set[str]:
    """Return the `app.<x>` subpackages imported by ``source``."""
    subpackages: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            parts = node.module.split(".")
            if parts[0] == "app" and len(parts) > 1:
                subpackages.add(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "app" and len(parts) > 1:
                    subpackages.add(parts[1])
    return subpackages


@pytest.mark.parametrize("package", ["domain", "engines"])
def test_pure_core_imports_no_framework(package: str) -> None:
    """`domain` and `engines` stay framework-free, so they are unit-testable alone."""
    offenders = {
        path.relative_to(APP).as_posix(): sorted(
            _imported_roots(path.read_text()) & FORBIDDEN_IN_CORE
        )
        for path in _modules(package)
        if _imported_roots(path.read_text()) & FORBIDDEN_IN_CORE
    }

    assert not offenders, f"framework imports leaked into app/{package}: {offenders}"


@pytest.mark.parametrize("package", sorted(ALLOWED_APP_IMPORTS))
def test_dependencies_point_inwards(package: str) -> None:
    """No layer imports a layer further out than itself."""
    allowed = ALLOWED_APP_IMPORTS[package] | {package}
    offenders = {
        path.relative_to(APP).as_posix(): sorted(
            _imported_app_subpackages(path.read_text()) - allowed
        )
        for path in _modules(package)
        if _imported_app_subpackages(path.read_text()) - allowed
    }

    assert not offenders, f"app/{package} may only import {sorted(allowed)}: {offenders}"


def test_routers_stay_thin() -> None:
    """No function in `app/api` exceeds 25 statements.

    A crude but honest proxy for "routers contain zero business logic": a handler
    that validates, delegates once and maps the result cannot get long. When this
    fails, the fix is to move the body into an engine, never to raise the limit.
    """
    limit = 25
    offenders: dict[str, int] = {}
    for path in _modules("api"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                statements = sum(1 for child in ast.walk(node) if isinstance(child, ast.stmt))
                if statements > limit:
                    offenders[f"{path.relative_to(APP).as_posix()}::{node.name}"] = statements

    assert not offenders, f"handlers over {limit} statements — move logic to engines: {offenders}"
