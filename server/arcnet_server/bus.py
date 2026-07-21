"""In-process signal/threat event bus for SSE subscribers (docs/12)."""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass
from typing import Any


@dataclass
class BusEvent:
    event_id: str
    event: str  # signal | threat | replay_progress | hitl_request
    data: dict[str, Any]


class EventBus:
    def __init__(self) -> None:
        self._seq = itertools.count(1)
        self._subs: list[asyncio.Queue[BusEvent]] = []

    def publish(self, event: str, data: dict[str, Any]) -> BusEvent:
        eid = str(next(self._seq))
        payload = BusEvent(event_id=eid, event=event, data=data)
        dead: list[asyncio.Queue[BusEvent]] = []
        for q in self._subs:
            try:
                q.put_nowait(payload)
            except Exception:  # noqa: BLE001
                dead.append(q)
        for q in dead:
            if q in self._subs:
                self._subs.remove(q)
        return payload

    def subscribe(self) -> asyncio.Queue[BusEvent]:
        q: asyncio.Queue[BusEvent] = asyncio.Queue(maxsize=256)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[BusEvent]) -> None:
        if q in self._subs:
            self._subs.remove(q)


BUS = EventBus()
