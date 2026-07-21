"""Boundary-check scanner: Python core and TypeScript HQ (docs/02)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_import_boundaries import scan  # noqa: E402


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class BoundaryScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_clean_tree_has_no_violations(self) -> None:
        write(self.root, "sdk/arcnet/core.py", "import json\n")
        write(self.root, "server/arcnet_server/main.py", "from arcnet import core\n")
        write(
            self.root,
            "hq/src/api.ts",
            'import type { Row } from "./types";\nimport { useState } from "react";\n',
        )
        self.assertEqual(scan(self.root), [])

    def test_python_core_importing_demo_layer_is_flagged(self) -> None:
        write(self.root, "sdk/arcnet/bad.py", "from agents.worms import run\n")
        write(self.root, "server/arcnet_server/bad.py", "import scripts.seed\n")
        problems = scan(self.root)
        self.assertEqual(len(problems), 2)
        self.assertTrue(any("agents.worms" in p for p in problems))
        self.assertTrue(any("scripts.seed" in p for p in problems))

    def test_hq_relative_import_into_demo_layer_is_flagged(self) -> None:
        write(self.root, "hq/src/bad.tsx", 'import { fixture } from "../../agents/fixture";\n')
        write(self.root, "hq/src/also_bad.ts", 'export * from "../../scripts/helpers";\n')
        write(self.root, "hq/src/dynamic.ts", 'const m = await import("../../agents/demo");\n')
        problems = scan(self.root)
        self.assertEqual(len(problems), 3)

    def test_hq_vite_glob_into_demo_layer_is_flagged(self) -> None:
        write(
            self.root,
            "hq/src/glob_bad.ts",
            'const demos = import.meta.glob("../../agents/**/*.ts");\n',
        )
        write(
            self.root,
            "hq/src/glob_ok.ts",
            'const views = import.meta.glob(["./views/*.tsx", "/src/panels/*.tsx"]);\n',
        )
        problems = scan(self.root)
        self.assertEqual(len(problems), 1)
        self.assertIn("glob_bad.ts", problems[0])

    def test_hq_bare_and_internal_specifiers_are_allowed(self) -> None:
        write(
            self.root,
            "hq/src/ok.ts",
            'import React from "react";\nimport { api } from "./api";\nimport { A } from "../views/a";\n',
        )
        write(self.root, "hq/node_modules/pkg/index.ts", 'import x from "../../agents/x";\n')
        self.assertEqual(scan(self.root), [])


if __name__ == "__main__":
    unittest.main()
