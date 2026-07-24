"""In-process signal/threat event bus for SSE subscribers (docs/12)."""

from __future__ import annotations

import itertools
import queue
import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class BusEvent:
    event_id: str
    event: str  # signal | threat | replay_progress | hitl_request
    data: dict[str, Any]


class EventBus:
    """Thread-safe fan-out with bounded per-subscriber queues (drop-oldest on overflow)."""

    def __init__(self, *, maxsize: int = 256) -> None:
        self._seq = itertools.count(1)
        self._subs: list[queue.Queue[BusEvent]] = []
        self._lock = threading.Lock()
        self._maxsize = maxsize

    def _offer(self, q: queue.Queue[BusEvent], payload: BusEvent) -> None:
        try:
            q.put_nowait(payload)
        except queue.Full:
            try:
                q.get_nowait()  # drop oldest, keep newest
            except queue.Empty:
                pass
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass

    def publish(self, event: str, data: dict[str, Any]) -> BusEvent:
        eid = str(next(self._seq))
        payload = BusEvent(event_id=eid, event=event, data=data)
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            self._offer(q, payload)
        return payload

    def subscribe(self) -> queue.Queue[BusEvent]:
        q: queue.Queue[BusEvent] = queue.Queue(maxsize=self._maxsize)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[BusEvent]) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)


BUS = EventBus()
