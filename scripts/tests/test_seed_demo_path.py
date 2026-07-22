"""seed_demo.py honors ARCNET_DB_PATH (verify-reinforce)."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SeedDemoPathTests(unittest.TestCase):
    def test_env_db_path_initializes_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "fresh.db"
            env = {**os.environ, "ARCNET_DB_PATH": str(db)}
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "seed_demo.py"), "--sessions", "1"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            self.assertTrue(db.exists(), proc.stdout)
            conn = sqlite3.connect(db)
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertIn("agents", tables)
            self.assertIn("sessions", tables)
            self.assertGreaterEqual(
                conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0], 2
            )


if __name__ == "__main__":
    unittest.main()
