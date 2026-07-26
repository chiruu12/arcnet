"""P11-B — concurrency & resilience under load (deterministic where possible)."""

from __future__ import annotations

import asyncio
import json
import os
import queue
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import AsyncMock, patch

from arcnet_server.bus import BUS, EventBus
from arcnet_server.db import connect, init_db
from arcnet_server import repository


def _seed_series(path: Path, n: int = 40) -> None:
    pts = [{"t": float(i), "v": 100.0 + 0.2 * i} for i in range(n)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"arcnet.tokens.total|agent_j": pts}))


class DbConcurrencyTests(unittest.TestCase):
    def test_wal_and_busy_timeout_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(Path(tmp) / "pragma.db")
            init_db(conn)
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            self.assertEqual(str(journal).lower(), "wal")
            self.assertGreaterEqual(int(busy), 5000)

    def test_concurrent_writers_succeed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "writers.db"
            os.environ["ARCNET_DB_PATH"] = str(db_path)
            import arcnet_server.main as m

            m.reset_connections_for_tests()
            conn = m.get_conn()
            ts = 1_700_000_000_000
            conn.execute(
                "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?)",
                ("agent_j", "J", "ops", "internal", "legacy-baseline-v1", ts, ts),
            )
            conn.commit()
            errors: list[str] = []
            lock = threading.Lock()

            def writer(i: int) -> None:
                try:
                    c = m.get_conn()
                    repository.insert_signal(
                        c,
                        f"sig_c_{i}",
                        {
                            "agent_id": "agent_j",
                            "kind": "note",
                            "severity": "info",
                            "reason": f"concurrent-{i}",
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    with lock:
                        errors.append(f"{type(exc).__name__}: {exc}")

            with ThreadPoolExecutor(max_workers=16) as pool:
                list(pool.map(writer, range(80)))

            self.assertEqual(errors, [], f"writer errors: {errors[:5]}")
            count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            self.assertEqual(int(count), 80)
            m.reset_connections_for_tests()


class EventBusConcurrencyTests(unittest.TestCase):
    def test_drop_oldest_not_newest_on_full_queue(self) -> None:
        bus = EventBus(maxsize=4)
        q = bus.subscribe()
        for i in range(6):
            bus.publish("signal", {"n": i})
        items = []
        while True:
            try:
                items.append(q.get_nowait())
            except queue.Empty:
                break
        self.assertEqual(len(items), 4)
        nums = [ev.data["n"] for ev in items]
        self.assertEqual(nums, [2, 3, 4, 5])

    def test_many_subscribers_receive_all_events(self) -> None:
        bus = EventBus(maxsize=64)
        subs = [bus.subscribe() for _ in range(8)]
        for i in range(32):
            bus.publish("threat", {"seq": i})
        for q in subs:
            seen = []
            while True:
                try:
                    seen.append(q.get_nowait().data["seq"])
                except queue.Empty:
                    break
            self.assertEqual(seen, list(range(32)), "subscriber starved or dropped")

    def test_unsubscribe_during_publish_does_not_crash(self) -> None:
        bus = EventBus(maxsize=16)
        victim = bus.subscribe()
        keep = bus.subscribe()
        errors: list[str] = []

        def publisher() -> None:
            try:
                for i in range(200):
                    bus.publish("signal", {"i": i})
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

        def unsub() -> None:
            for _ in range(50):
                bus.unsubscribe(victim)

        t_pub = threading.Thread(target=publisher)
        t_un = threading.Thread(target=unsub)
        t_pub.start()
        t_un.start()
        t_pub.join(timeout=5)
        t_un.join(timeout=5)
        self.assertEqual(errors, [])
        items = []
        while True:
            try:
                items.append(keep.get_nowait())
            except queue.Empty:
                break
        self.assertGreater(len(items), 0)
        self.assertEqual(items[-1].data["i"], 199)

    def test_connect_disconnect_no_subscriber_leak(self) -> None:
        bus = EventBus(maxsize=8)
        for _ in range(50):
            q = bus.subscribe()
            bus.publish("ping", {})
            bus.unsubscribe(q)
        self.assertEqual(len(bus._subs), 0)  # noqa: SLF001


class GriffinCacheConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        import arcnet_server.griffin as g

        g.reset_tabfm_state_for_tests()
        with g._CACHE_LOCK:  # noqa: SLF001
            g._CACHE.clear()
            g._CACHE.update(
                {
                    "model": "mad",
                    "estimator": "mad",
                    "status": "cold",
                    "series": {},
                    "proxy_series": {},
                    "series_source": None,
                    "last_cycle_ms": None,
                    "last_evaluate_ms": None,
                    "last_anomaly": None,
                    "anomalies": [],
                }
            )

    def test_cache_snapshot_always_well_formed_under_contention(self) -> None:
        import arcnet_server.griffin as g
        import arcnet_server.main as m

        with tempfile.TemporaryDirectory() as tmp:
            series_path = Path(tmp) / "griffin_series.json"
            os.environ["ARCNET_DB_PATH"] = str(Path(tmp) / "g.db")
            os.environ["ARCNET_GRIFFIN_SERIES"] = str(series_path)
            _seed_series(series_path)
            m.reset_connections_for_tests()

            errors: list[str] = []
            lock = threading.Lock()

            def reader() -> None:
                for _ in range(40):
                    snap = g.cache_snapshot()
                    if not isinstance(snap.get("series"), dict):
                        with lock:
                            errors.append("series not dict")
                    if snap.get("status") not in ("cold", "warming", "ready"):
                        with lock:
                            errors.append(f"bad status {snap.get('status')}")

            def writer() -> None:
                for _ in range(20):
                    g.evaluate_series(m.get_conn, series_id="arcnet.tokens.total|agent_j")

            threads = [threading.Thread(target=reader) for _ in range(6)]
            threads += [threading.Thread(target=writer) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
            self.assertEqual(errors, [])
            m.reset_connections_for_tests()


class ReplayConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        os.environ["ARCNET_DB_PATH"] = os.path.join(cls._tmp, "replay_cc.db")
        import arcnet_server.main as m

        m.reset_connections_for_tests()
        cls.m = m
        from fastapi.testclient import TestClient

        cls.client = TestClient(m.app)
        conn = m.get_conn()
        ts = 1_700_000_000_000
        transcript = {
            "scenario": "S4",
            "steps": [{"type": "model_turn", "content": "hello"}],
            "final_output": "done",
        }
        conn.execute(
            "INSERT INTO agents (agent_id, name, role, exposure, model, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?)",
            ("agent_j", "J", "ops", "internal", "legacy-baseline-v1", ts, ts),
        )
        conn.execute(
            """INSERT INTO sessions (session_id, agent_id, scenario, goal, model, temperature,
               status, outcome, usage, transcript, started_at, ended_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "s_replay_cc",
                "agent_j",
                "S4",
                "goal",
                "legacy-baseline-v1",
                0.0,
                "completed",
                json.dumps({"goal_reached": "partial", "steps": 3}),
                json.dumps({"cost_usd": 0.01, "input_tokens": 100, "output_tokens": 50}),
                json.dumps(transcript),
                ts,
                ts,
            ),
        )
        conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.m.reset_connections_for_tests()

    def test_parallel_replays_do_not_cross_contaminate_verdicts(self) -> None:
        calls: list[str] = []

        async def fake_execute_replay(*, replay_id: str, **kwargs):  # noqa: ANN003
            order = len(calls)
            calls.append(replay_id)
            await asyncio.sleep(0.05)
            run = {
                "model": "gpt-4o",
                "goal_reached": "clean" if order == 0 else "partial",
                "steps": 2,
                "tool_errors": 0,
                "cost_usd": 0.01,
                "latency_ms": 1000,
                "tokens": 100,
            }
            verdict = {
                "replay_id": replay_id,
                "session_id": "s_replay_cc",
                "verdict": "improved" if order == 0 else "inconclusive",
                "confidence": "3/3 runs",
            }
            return [run, run, run], verdict, 120

        with patch(
            "arcnet_server.main.execute_replay",
            new=AsyncMock(side_effect=fake_execute_replay),
        ):
            import httpx

            async def post_one(tag: str) -> dict:
                transport = httpx.ASGITransport(app=self.m.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
                    res = await ac.post(
                        "/api/replay",
                        json={"session_id": "s_replay_cc", "candidate_model": f"gpt-4o-{tag}"},
                    )
                    res.raise_for_status()
                    return res.json()

            async def run_pair() -> tuple[dict, dict]:
                return await asyncio.gather(post_one("a"), post_one("b"))

            v_a, v_b = asyncio.run(run_pair())

        self.assertEqual(len(calls), 2)
        self.assertNotEqual(v_a["replay_id"], v_b["replay_id"])
        verdict_names = {v_a["verdict"], v_b["verdict"]}
        self.assertEqual(verdict_names, {"improved", "inconclusive"})
        rows = self.m.get_conn().execute(
            "SELECT replay_id, verdict FROM replays WHERE session_id=? ORDER BY replay_id",
            ("s_replay_cc",),
        ).fetchall()
        self.assertEqual(len(rows), 2)
        stored = {json.loads(r[1])["verdict"] for r in rows}
        self.assertEqual(stored, {"improved", "inconclusive"})


class GracefulShutdownTests(unittest.TestCase):
    def test_lifespan_cancels_griffin_and_degrades_tabfm(self) -> None:
        import arcnet_server.griffin as g
        import arcnet_server.main as m

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["ARCNET_DB_PATH"] = str(Path(tmp) / "shut.db")
            os.environ["ARCNET_TABFM"] = "1"
            os.environ["ARCNET_TABFM_CADENCE_S"] = "3600"
            m.reset_connections_for_tests()
            g.reset_tabfm_state_for_tests()
            from fastapi.testclient import TestClient

            with TestClient(m.app) as client:
                self.assertEqual(client.get("/health").status_code, 200)
                self.assertIsNotNone(m._griffin_task)
            self.assertTrue(m._griffin_task.done())
            self.assertTrue(g._TABFM_STATE["degraded"])  # noqa: SLF001
            self.assertEqual(g._TABFM_STATE["degrade_reason"], "lifespan_shutdown")  # noqa: SLF001
            os.environ.pop("ARCNET_TABFM", None)
            m.reset_connections_for_tests()
            g.reset_tabfm_state_for_tests()


class GlobalBusIntegrationTests(unittest.TestCase):
    def test_bus_publish_from_worker_thread(self) -> None:
        q = BUS.subscribe()
        seen: list[str] = []

        def pub() -> None:
            BUS.publish("signal", {"agent_id": "agent_j", "reason": "from-thread"})

        threading.Thread(target=pub).start()
        ev = q.get(timeout=2.0)
        seen.append(ev.data["reason"])
        BUS.unsubscribe(q)
        self.assertEqual(seen, ["from-thread"])


if __name__ == "__main__":
    unittest.main()
