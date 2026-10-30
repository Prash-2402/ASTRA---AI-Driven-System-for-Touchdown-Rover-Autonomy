"""In-process pub/sub bridging simulation threads to asyncio websocket consumers."""
from __future__ import annotations

import asyncio
import threading
from collections import defaultdict

CHANNELS = ("telemetry", "events", "faults", "controller", "experiments")


class EventBus:
    def __init__(self):
        self._subs: dict[str, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = defaultdict(set)
        self._lock = threading.Lock()

    def subscribe(self, channel: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subs[channel].add((asyncio.get_running_loop(), q))
        return q

    def unsubscribe(self, channel: str, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs[channel] = {s for s in self._subs[channel] if s[1] is not q}

    def publish(self, channel: str, message: dict) -> None:
        with self._lock:
            subs = list(self._subs[channel])
        for loop, q in subs:
            def _put(q=q):
                if q.full():
                    try:
                        q.get_nowait()          # drop oldest: telemetry is a stream, not a log
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(message)
            try:
                loop.call_soon_threadsafe(_put)
            except RuntimeError:
                pass


bus = EventBus()
