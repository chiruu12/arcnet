#!/usr/bin/env python3
"""Product-core import boundary check (docs/02).

sdk/, server/, and hq/ are the product core — they must never import from
agents/ or scripts/ (demo layer). Exits non-zero listing every violation.
Stdlib-only: Python parsed with ast, TypeScript scanned for import/export
specifiers that resolve into a forbidden directory.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY_CORE_DIRS = ("sdk", "server")
FORBIDDEN_ROOTS = {"agents", "arcnet_agents", "scripts"}
FORBIDDEN_DIR_NAMES = ("agents", "scripts")

# Matches `import ... from "x"`, `export ... from "x"`, `import("x")`, `import "x"`.
TS_IMPORT_RE = re.compile(
    r"""\b(?:import|export)\b[^;'"]*?\bfrom\s*["']([^"']+)["']"""
    r"""|\bimport\s*\(\s*["']([^"']+)["']\s*\)"""
    r"""|\bimport\s+["']([^"']+)["']"""
)


def py_violations_in(path: Path, root: Path) -> list[str]:
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
                found.append(f"{path.relative_to(root)}:{node.lineno}: imports {name}")
    return found


def ts_violations_in(path: Path, root: Path) -> list[str]:
    text = path.read_text()
    found: list[str] = []
    for match in TS_IMPORT_RE.finditer(text):
        spec = next(group for group in match.groups() if group)
        if not spec.startswith("."):
            continue  # bare specifiers are npm packages, not repo dirs
        target = (path.parent / spec).resolve()
        for name in FORBIDDEN_DIR_NAMES:
            bad_dir = (root / name).resolve()
            if target == bad_dir or bad_dir in target.parents:
                lineno = text.count("\n", 0, match.start()) + 1
                found.append(f"{path.relative_to(root)}:{lineno}: imports {spec}")
    return found


def scan(root: Path) -> list[str]:
    problems: list[str] = []
    for core in PY_CORE_DIRS:
        for py in (root / core).rglob("*.py"):
            if ".venv" in py.parts or "tests" in py.parts:
                continue
            problems.extend(py_violations_in(py, root))
    for pattern in ("*.ts", "*.tsx"):
        for ts in (root / "hq").rglob(pattern):
            if "node_modules" in ts.parts or "dist" in ts.parts:
                continue
            problems.extend(ts_violations_in(ts, root))
    return problems


def main() -> int:
    problems = scan(ROOT)
    if problems:
        print("import boundary violations (core must not import demo layer):")
        for p in problems:
            print(f"  {p}")
        return 1
    print("import boundaries clean: sdk/ + server/ + hq/ never import agents/ or scripts/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
