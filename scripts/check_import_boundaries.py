#!/usr/bin/env python3
"""Product-core import boundary check (docs/02).

sdk/, server/, and hq/ are the product core — they must never import from
agents/ or scripts/ (demo layer). Exits non-zero listing every violation.
Stdlib-only: parses with ast, no third-party deps.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_DIRS = ("sdk", "server")
FORBIDDEN_ROOTS = {"agents", "arcnet_agents", "scripts"}


def violations_in(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as exc:
        return [f"{path}: syntax error: {exc}"]
    found: list[str] = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        for name in names:
            if name.split(".", 1)[0] in FORBIDDEN_ROOTS:
                found.append(f"{path.relative_to(ROOT)}:{node.lineno}: imports {name}")
    return found


def main() -> int:
    problems: list[str] = []
    for core in CORE_DIRS:
        for py in (ROOT / core).rglob("*.py"):
            if ".venv" in py.parts or "tests" in py.parts:
                continue
            problems.extend(violations_in(py))
    # hq/ is TypeScript; the equivalent rule is that it only talks to the
    # server over HTTP — nothing to import-scan.
    if problems:
        print("import boundary violations (core must not import demo layer):")
        for p in problems:
            print(f"  {p}")
        return 1
    print("import boundaries clean: sdk/ + server/ never import agents/ or scripts/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
