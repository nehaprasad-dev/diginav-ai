"""In-memory event broker for fan-out from FlowSimulator to SSE consumers.

Why this exists:
    The simulator runs as a long-lived background task and needs to emit
    events for ~30-90 seconds. The SSE endpoint may connect later, drop,
    and reconnect during that lifetime. Decoupling producer and consumer
    via a per-session queue means:
      * POST /api/chat returns immediately while the simulator runs in
        an asyncio.Task.
      * GET /api/stream/{sessionId} can attach at any time and receive
        events from that point onward.
      * Frontend reconnect logic uses GET /api/workflows/{id} for the
        snapshot (covering anything missed) and the broker for the live
        tail. There is no replay buffer here on purpose.

In Week 1 we run one backend instance, so an asyncio.Queue per session
is sufficient. When we go multi-instance we swap the implementation for
Redis pub/sub behind the same `publish` / `subscribe` surface.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import AsyncIterator

from .events import AgentEvent

logger = logging.getLogger(__name__)


# Sentinel pushed into a queue to signal "no more events for this session".
# Using a private object so it can never collide with a real AgentEvent.
_END = object()


class EventBroker:
    """Per-session in-memory event bus."""

    def __init__(self) -> None:
        # session_id -> list of subscriber queues. Multiple queues allow
        # the same session to be observed from more than one place
        # (e.g. a debug panel) without disturbing the main consumer.
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, session_id: str, event: AgentEvent) -> None:
        """Fan an event out to every subscriber attached to this session."""
        queues = self._subscribers.get(session_id, [])
        if not queues:
            # No one is listening yet. The frontend will catch up by
            # calling GET /api/workflows/{id} on reconnect, so dropping
            # is intentional — we don't want unbounded memory growth.
            return
        for queue in queues:
            await queue.put(event)

    async def close(self, session_id: str) -> None:
        """Tell every subscriber for this session that the stream is done."""
        for queue in self._subscribers.get(session_id, []):
            await queue.put(_END)

    async def subscribe(self, session_id: str) -> AsyncIterator[AgentEvent]:
        """Yield events for this session until close() is called.

        Each call to subscribe() gets its own queue; an unsubscribe is
        guaranteed via the `finally` block when the consumer exits.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        try:
            while True:
                item = await queue.get()
                if item is _END:
                    return
                yield item
        finally:
            try:
                self._subscribers[session_id].remove(queue)
            except ValueError:
                pass
            if not self._subscribers[session_id]:
                self._subscribers.pop(session_id, None)


# Module-level singleton: one broker per backend process.
broker = EventBroker()
