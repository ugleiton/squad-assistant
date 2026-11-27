"""Enforces the Clean Architecture dependency rule:

    interfaces -> infrastructure -> application -> domain

- domain imports only the standard library (and other domain modules)
- application imports only domain and the standard library (no FastAPI, SQLModel, httpx...)
- infrastructure never imports interfaces
"""

import ast
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
STDLIB = set(sys.stdlib_module_names)


def imports_of(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    pkg = path.relative_to(APP.parent).with_suffix("").parts[:-1]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = list(pkg[: len(pkg) - node.level + 1])
                found.append(".".join(base + ([node.module] if node.module else [])))
            else:
                found.append(node.module or "")
    return found


def layer_violations(layer: str, allowed_internal: set[str], allow_third_party: bool):
    bad = []
    for path in (APP / layer).rglob("*.py"):
        for mod in imports_of(path):
            top = mod.split(".")[0]
            if top == "app":
                inner = mod.split(".")[1] if "." in mod else ""
                if inner not in allowed_internal:
                    bad.append(f"{path.relative_to(APP)} imports {mod}")
            elif not allow_third_party and top not in STDLIB:
                bad.append(f"{path.relative_to(APP)} imports {mod}")
    return bad


def test_domain_is_pure():
    assert layer_violations("domain", {"domain"}, allow_third_party=False) == []


def test_application_depends_only_on_domain():
    assert layer_violations("application", {"domain", "application"}, allow_third_party=False) == []


def test_infrastructure_does_not_depend_on_interfaces():
    allowed = {"domain", "application", "infrastructure"}
    assert layer_violations("infrastructure", allowed, allow_third_party=True) == []
