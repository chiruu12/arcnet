# ArcNet hardening (P11)

## Concurrency & resilience

Packet P11-B stress-tests the shared SQLite connection, in-process SSE bus, Griffin
worker cache, replay orchestration, and lifespan teardown under concurrent load.

| Race / hazard | Verdict | Fix |
|---------------|---------|-----|
| Module-global `get_conn()` shared across FastAPI threadpool + Griffin TabFM daemon | **Risk** — sqlite3 connections are not thread-safe; concurrent `execute`/`commit` can interleave; `fetchone()` after `execute()` outside the lock reads torn cursor state | `_ThreadSafeConnection` proxy serializes `execute`/`commit`/`rollback`; SELECT cursors hold the lock until `fetchone`/`fetchall`; `PRAGMA busy_timeout=5000` (with existing WAL) |
| `get_conn()` lazy init from multiple threads | **Risk** — double init / torn connection | Double-checked lock (`_conn_init_lock`) around first `connect()` + `init_db()` |
| WAL / busy_timeout not configured | **OK (WAL)** / **Gap (timeout)** | `connect()` already sets `journal_mode=WAL`; P11-B adds `busy_timeout=5000` |
| `EventBus.publish` from sync routes + Griffin thread into `asyncio.Queue` | **Risk** — asyncio queues are not thread-safe; full queue removed subscriber | Switched to bounded `queue.Queue` (max 256); **drop-oldest** on overflow (newest retained); `threading.Lock` on subscriber list; SSE reads via `run_in_executor` |
| SSE subscriber starvation under fan-out | **OK** after bus fix | All subscribers receive each event when queues are not saturated; saturated queues drop oldest, not newest |
| Unsubscribe during `publish` | **Risk** — list mutation during iteration | Snapshot subscriber list under lock before fan-out; unsubscribe is lock-guarded |
| Connect/disconnect subscriber leak | **OK** | `unsubscribe` removes queue; tests assert `_subs` empty after 50 cycles |
| Griffin `_CACHE` mutated by `griffin_loop` / TabFM thread while HTTP reads `cache_snapshot` | **Risk** — readers could observe torn dict updates | `threading.RLock` around cache writes and `copy.deepcopy` snapshot reads |
| Two concurrent `POST /api/replay` for one session | **OK** — each call allocates its own `replay_id` and persists separate verdict rows | No code change; tests mock `execute_replay` and assert distinct `replay_id` / verdict / DB rows |
| Lifespan exit leaves Griffin task or TabFM daemon running | **Gap** — griffin cancelled but TabFM loop had no shutdown signal | `shutdown_background_workers(reason="lifespan_shutdown")` sets TabFM `degraded`; griffin task awaited after `cancel()` |

### Test suite

`server/tests/test_concurrency.py` — deterministic threading/async tests for each row above.

Run (3× for flake check):

```bash
uv sync --all-packages --all-groups && uv pip install pytest
.venv/bin/python -m pytest server/tests/test_concurrency.py -q
```

Full server suite:

```bash
.venv/bin/python -m pytest server/tests -q
```
