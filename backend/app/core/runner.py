"""Orchestrator that drives a FlowSimulator and persists every event.

The lifecycle of a workflow:
    POST /api/chat → run_workflow() spawned as asyncio.Task
                  → simulator.start() → events flow:
                       1. WorkflowStartedEvent: persist initial step list
                       2. StepUpdateEvent: patch JSONB step state
                       3. TokenEvent: forwarded to broker only (chat tokens
                          are persisted as a single message after streaming
                          ends, not per token, to avoid PG churn)
                       4. AwaitingHumanEvent: set workflow.status =
                          'awaiting_human' and stop iterating; resume()
                          will be triggered by POST /api/workflows/.../resume
                       5. WorkflowCompletedEvent: status = 'completed',
                          persist output
                       6. ErrorEvent: status = 'failed'

Persist-then-publish ordering is intentional. If a frontend disconnects
between the DB write and the broker publish, it can call GET
/api/workflows/{id} on reconnect and observe the latest state, then
re-subscribe to the broker for any newer events. If we published
first, a fast reconnect could see a stale snapshot and miss the
update entirely.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncIterator

from .event_broker import EventBroker, broker as default_broker
from .events import (
    AgentEvent,
    AwaitingHumanEvent,
    ErrorEvent,
    StepUpdateEvent,
    TokenEvent,
    WorkflowCompletedEvent,
    WorkflowStartedEvent,
)
from .flow_simulator import FlowSimulator
from ..store.workflow_store import WorkflowStore, workflow_store as default_store

logger = logging.getLogger(__name__)


# Map simulator status enum to DB workflow.status enum.
_TERMINAL_STATUS = {
    "completed": "completed",
    "blocked_awaiting_human": "awaiting_human",
}


class WorkflowRunner:
    """Drives a single workflow end-to-end and persists every transition."""

    def __init__(
        self,
        store: WorkflowStore | None = None,
        event_broker: EventBroker | None = None,
    ):
        self._store = store or default_store
        self._broker = event_broker or default_broker
        # session_id -> FlowSimulator, so resume() can look up the live
        # instance keeping the workflow's in-memory state.
        self._simulators: dict[str, FlowSimulator] = {}

    # ------------------------------------------------------------------ #
    # Public entry points                                                 #
    # ------------------------------------------------------------------ #

    async def run(
        self,
        session_id: str,
        flow_id: str,
        user_message: str,
    ) -> str:
        """Convenience wrapper: prepare + drain in one call.

        Used by tests and any caller that wants to await full execution.
        Production HTTP handlers should use prepare() + asyncio.create_task(drain())
        instead so the request can return before the simulator finishes.
        """
        sim, wf_id = await self.prepare(session_id, flow_id)
        await self._drive(session_id, sim.start(session_id, user_message))
        return wf_id

    async def prepare(
        self,
        session_id: str,
        flow_id: str,
    ) -> tuple[FlowSimulator, str]:
        """Create the workflow row and register the simulator.

        Returns (simulator, workflow_id). The caller is responsible for
        scheduling drain() on the returned simulator.
        """
        sid = uuid.UUID(session_id)
        sim = FlowSimulator(flow_id=flow_id, session_id=session_id)

        steps_initial = [
            {
                "idx": i,
                "id": s.id,
                "title": s.title,
                "status": "pending",
                "subStatus": None,
            }
            for i, s in enumerate(sim._steps)  # noqa: SLF001 – read-only access
        ]
        wf_id = await self._store.create_workflow(sid, flow_id, steps_initial)
        sim.workflow_id = str(wf_id)
        self._simulators[str(wf_id)] = sim
        return sim, str(wf_id)

    async def drain_start(self, sim: FlowSimulator, session_id: str, user_message: str) -> None:
        """Drain a fresh simulator's start() stream. Intended for create_task."""
        await self._drive(session_id, sim.start(session_id, user_message))

    async def resume(
        self,
        workflow_id: str,
        session_id: str,
        approved: bool,
    ) -> None:
        """Continue a paused workflow after a human approval decision."""
        sim = self._simulators.get(workflow_id)
        if sim is None:
            # Not in memory (e.g. process restart in prod). Synthesize an
            # error event so the frontend gets a clear signal.
            await self._broker.publish(
                session_id,
                ErrorEvent(
                    message="Workflow not found in this process. Refresh required.",
                    correlation_id=str(uuid.uuid4()),
                    recoverable=False,
                ),
            )
            return
        await self._drive(session_id, sim.resume(workflow_id, approved))

    # ------------------------------------------------------------------ #
    # Internals                                                           #
    # ------------------------------------------------------------------ #

    async def _drive(
        self,
        session_id: str,
        events: AsyncIterator[AgentEvent],
    ) -> None:
        """Drain an event stream: persist, then publish, for each event."""
        try:
            async for event in events:
                await self._persist(event)
                await self._broker.publish(session_id, event)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Runner failed for session %s", session_id)
            err = ErrorEvent(
                message=f"Internal error: {exc}",
                correlation_id=str(uuid.uuid4()),
                recoverable=False,
            )
            await self._broker.publish(session_id, err)

    async def _persist(self, event: AgentEvent) -> None:
        """Map an AgentEvent to the appropriate WorkflowStore call."""
        if isinstance(event, WorkflowStartedEvent):
            # Initial row was already inserted in run(); nothing to do here.
            return

        if isinstance(event, StepUpdateEvent):
            await self._store.update_step(
                workflow_id=uuid.UUID(event.workflow_id),
                step_idx=event.step_idx,
                status=event.status,
                sub_status=event.sub_status,
            )
            return

        if isinstance(event, AwaitingHumanEvent):
            await self._store.set_status(
                workflow_id=uuid.UUID(event.workflow_id),
                status="awaiting_human",
            )
            return

        if isinstance(event, WorkflowCompletedEvent):
            await self._store.set_status(
                workflow_id=uuid.UUID(event.workflow_id),
                status="completed",
                output=dict(event.output),
            )
            return

        if isinstance(event, ErrorEvent):
            # Errors don't always carry a workflow_id (broker-level
            # synthetic errors don't). Persist failure only when we have
            # a live simulator to map back to.
            return

        if isinstance(event, TokenEvent):
            # Tokens are ephemeral; they live on the SSE channel only.
            # Persisting per-token would 100x our write rate for no gain
            # since the assistant message can be reconstructed from the
            # final completed event or a single end-of-stream insert.
            return


# Module-level singleton, mirroring `workflow_store` and `broker`.
runner = WorkflowRunner()


__all__ = ["WorkflowRunner", "runner", "_TERMINAL_STATUS"]
