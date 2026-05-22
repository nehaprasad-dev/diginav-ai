"""Integration test for GET /api/stream/{sessionId} (SSE).

Uses an httpx.AsyncClient against the ASGI app (no real HTTP socket)
and a manually-driven broker so we can publish a known sequence of
events and assert the wire format.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.core import event_broker as broker_module
from app.core.events import (
    StepUpdateEvent,
    TokenEvent,
    WorkflowCompletedEvent,
)
from app.main import app


# sse_starlette uses a module-level Event for graceful shutdown that
# binds to the first event loop it sees. Each pytest-asyncio test gets
# a fresh loop, so we reset that singleton before every test in this
# file. Without this, only the first SSE test passes per session.
@pytest.fixture(autouse=True)
def _reset_sse_starlette_app_status():
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit_event = None


# --------------------------------------------------------------------- #
# Helpers                                                                #
# --------------------------------------------------------------------- #


def _parse_sse(raw: str) -> list[dict[str, Any]]:
    """Parse the SSE byte stream into a list of {event, data} dicts."""
    events: list[dict[str, Any]] = []
    for block in raw.strip().split("\n\n"):
        block = block.strip()
        if not block or block.startswith(":"):
            # Skip pings (`: ping`) and empty separators.
            continue
        record: dict[str, Any] = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                record["event"] = line[len("event:"):].strip()
            elif line.startswith("data:"):
                record["data"] = json.loads(line[len("data:"):].strip())
        if record:
            events.append(record)
    return events


# --------------------------------------------------------------------- #
# Tests                                                                  #
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_stream_emits_published_events_in_order(monkeypatch):
    """A consumer attached before publish receives every event."""
    session_id = "session-stream-1"

    # Use the real broker module-level instance so the endpoint and
    # this test see the same queues. We close it at the end to release
    # the SSE generator.
    broker = broker_module.broker

    async def _producer():
        # Wait long enough for the SSE consumer to subscribe before we
        # publish; otherwise events are dropped (by design — see the
        # broker's docstring).
        await asyncio.sleep(0.05)
        await broker.publish(
            session_id,
            StepUpdateEvent(
                workflow_id="wf-1",
                step_idx=0,
                status="in_progress",
                sub_status="Validating director DIN...",
            ),
        )
        await broker.publish(
            session_id,
            TokenEvent(text="Hello", message_id="msg-1"),
        )
        await broker.publish(
            session_id,
            WorkflowCompletedEvent(
                workflow_id="wf-1",
                output={"cin": "U72900MH2026PTC123456"},
            ),
        )
        await asyncio.sleep(0.05)
        await broker.close(session_id)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        producer_task = asyncio.create_task(_producer())
        response = await client.get(
            f"/api/stream/{session_id}",
            headers={"Accept": "text/event-stream"},
        )
        await producer_task

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(response.text)
    assert len(events) == 3

    assert events[0]["event"] == "step_update"
    assert events[0]["data"]["workflowId"] == "wf-1"
    assert events[0]["data"]["stepIdx"] == 0
    assert events[0]["data"]["subStatus"] == "Validating director DIN..."

    assert events[1]["event"] == "token"
    assert events[1]["data"]["text"] == "Hello"
    assert events[1]["data"]["messageId"] == "msg-1"

    assert events[2]["event"] == "workflow_completed"
    assert events[2]["data"]["output"] == {"cin": "U72900MH2026PTC123456"}

    # The subscribe() generator's `finally` block must have unregistered
    # the queue and removed the empty session entry. This is the cleanup
    # behavior that prevents memory leaks from disconnected clients.
    assert session_id not in broker._subscribers  # noqa: SLF001 – test introspection


@pytest.mark.asyncio
async def test_unknown_session_ids_do_not_leak_into_broker():
    """Subscribing to a session that never publishes anything cleans up cleanly."""
    broker = broker_module.broker
    session_id = "session-stream-no-events"

    async def _close_soon():
        await asyncio.sleep(0.05)
        await broker.close(session_id)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        closer = asyncio.create_task(_close_soon())
        response = await client.get(
            f"/api/stream/{session_id}",
            headers={"Accept": "text/event-stream"},
        )
        await closer

    assert response.status_code == 200
    # Empty stream (apart from any pings) and clean broker state
    parsed = _parse_sse(response.text)
    assert parsed == []
    assert session_id not in broker._subscribers  # noqa: SLF001
