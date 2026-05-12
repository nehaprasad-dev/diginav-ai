"""AgentRuntime Protocol – the single seam for future LangGraph integration.

Week 1: FlowSimulator implements this.
Week 2+: LangGraphAgent implements this.
Routers depend only on this Protocol.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol

from .events import AgentEvent


class WorkflowSnapshot:
    """Minimal snapshot type returned by get_state.

    Full implementation lives in models/workflow.py once the DB layer is wired.
    """

    workflow_id: str
    session_id: str
    flow_id: str
    status: str
    current_step_idx: int
    steps: list[dict]
    output: dict | None
    started_at: str
    updated_at: str
    completed_at: str | None


class AgentRuntime(Protocol):
    """Interface that all agent implementations must satisfy."""

    async def start(
        self, session_id: str, user_message: str
    ) -> AsyncIterator[AgentEvent]: ...

    async def resume(
        self, workflow_id: str, approval: bool
    ) -> AsyncIterator[AgentEvent]: ...

    async def get_state(self, workflow_id: str) -> WorkflowSnapshot: ...
