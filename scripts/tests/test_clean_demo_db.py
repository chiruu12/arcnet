"""Hermetic tests for scripts/clean_demo_db.py — always uses temp databases."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "clean_demo_db.py"
FIXTURE = ROOT / "fixtures" / "heroes.json"


def _run_clean(db: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--db", str(db), *extra],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_demo(db: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_demo.py"), "--db", str(db), "--sessions", "1"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def _seed_heroes(db: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_heroes.py"), "--db", str(db)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def _insert_orphan_threats(conn: sqlite3.Connection, session_id: str, n: int = 4) -> None:
    for i in range(n):
        conn.execute(
            """INSERT INTO threats
               (threat_id, session_id, agent_id, checkpoint, action, category, subcategory)
               VALUES (?,?,?,?,?,?,?)""",
            (
                f"thr_orphan_{session_id}_{i}",
                session_id,
                "agent_j",
                "input",
                "block",
                "injection",
                "ignore_previous",
            ),
        )
    conn.commit()


class CleanDemoDbTests(unittest.TestCase):
    def _make_db_with_orphans(self, tmp: str) -> Path:
        db = Path(tmp) / "demo.db"
        _seed_demo(db)
        _seed_heroes(db)
        conn = sqlite3.connect(db)
        _insert_orphan_threats(conn, "s_replay_steer", 3)
        _insert_orphan_threats(conn, "s_synthetic_leak", 2)
        conn.close()
        return db

    def test_dry_run_does_not_modify_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db_with_orphans(tmp)
            before = db.read_bytes()
            proc = _run_clean(db)
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            self.assertIn("DRY RUN", proc.stdout)
            self.assertIn("s_replay_steer", proc.stdout)
            self.assertEqual(db.read_bytes(), before)

    def test_apply_removes_orphans_preserves_heroes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = self._make_db_with_orphans(tmp)
            conn = sqlite3.connect(db)
            hero_thr_before = conn.execute(
                "SELECT COUNT(*) FROM threats WHERE session_id='s_ecfdb55d'"
            ).fetchone()[0]
            conn.close()

            applied = _run_clean(db, "--apply")
            self.assertEqual(applied.returncode, 0, applied.stderr or applied.stdout)
            self.assertIn("backup written:", applied.stdout)
            self.assertIn("Hero integrity: OK", applied.stdout)

            conn = sqlite3.connect(db)
            orphan_n = conn.execute(
                """SELECT COUNT(*) FROM threats
                   WHERE session_id IS NOT NULL
                     AND session_id NOT IN (SELECT session_id FROM sessions)"""
            ).fetchone()[0]
            hero_thr_after = conn.execute(
                "SELECT COUNT(*) FROM threats WHERE session_id='s_ecfdb55d'"
            ).fetchone()[0]
            hero_sess = conn.execute(
                "SELECT session_id FROM sessions WHERE session_id='s_ecfdb55d'"
            ).fetchone()
            worms_sess = conn.execute(
                "SELECT session_id FROM sessions WHERE session_id='s_2af44726'"
            ).fetchone()
            conn.close()

            self.assertEqual(orphan_n, 0)
            self.assertEqual(hero_thr_after, hero_thr_before)
            self.assertIsNotNone(hero_sess)
            self.assertIsNotNone(worms_sess)

    def test_heroes_fixture_lists_protected_ids(self) -> None:
        data = json.loads(FIXTURE.read_text())
        for hero in ("s_ecfdb55d", "s_2af44726"):
            self.assertIn(hero, data.get("session_ids", []))


if __name__ == "__main__":
    unittest.main()
