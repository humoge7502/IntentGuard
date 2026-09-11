"""In-process event bus feeding the live firewall stream (SSE) and dashboards."""
from __future__ import annotations

import queue
import threading


class EventBus:
    def __init__(self, max_queue: int = 1000) -> None:
        self._subscribers: set[queue.Queue] = set()
        self._lock = threading.Lock()
        self._max_queue = max_queue

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=self._max_queue)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, event: dict) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                # drop oldest to keep the stream live rather than blocking enforcement
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (queue.Empty, queue.Full):
                    pass
