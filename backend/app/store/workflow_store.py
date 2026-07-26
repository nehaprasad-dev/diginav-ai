"""WorkflowStore — single owner of read/write logic for workflows + chat.

Why this exists:
    Routers should not run SQL. They translate HTTP into store calls.
    This makes idempotency, transaction boundaries, and JSONB shape
    consistent in one place — and makes Week 2 swap to a different
    persistence layer trivial.

Concurrency note:
    Each call opens its own short-lived async session. The simulator
    runs as a long background task and may persist many step updates;
    keeping each write to its own transaction avoids holding a
    connection across multi-second narration streaming.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..models.chat_message import ChatMessage
from ..models.session import Session as SessionModel
from ..models.workflow import Workflow
from .db import async_session_factory


class WorkflowStore:
    """Read/write API for sessions, chat messages, and workflows."""

    # ------------------------------------------------------------------ #
    # Sessions                                                            #
    # ------------------------------------------------------------------ #

    async def ensure_session(self, session_id: str) -> uuid.UUID:
        """Insert the session row if missing, return its UUID.

        Frontends generate session_id client-side (UUIDv4); we only
        persist it the first time we see it. Subsequent calls update
        last_seen_at via ON CONFLICT.
        """
        sid = uuid.UUID(session_id)
        async with async_session_factory() as db:
            stmt = (
                pg_insert(SessionModel)
                .values(id=sid)
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={"last_seen_at": datetime.now(timezone.utc)},
                )
            )
            await db.execute(stmt)
            await db.commit()
        return sid

    # ------------------------------------------------------------------ #
    # Chat messages                                                       #
    # ------------------------------------------------------------------ #

    async def append_message(
        self,
        session_id: uuid.UUID,
        message_id: uuid.UUID,
        role: str,
        content: str,
    ) -> bool:
        """Insert a chat message, ignoring duplicates by primary key.

        Returns True if a new row was inserted, False if message_id was
        already seen (idempotency for retried POST /api/chat calls).
        """
        async with async_session_factory() as db:
            stmt = (
                pg_insert(ChatMessage)
                .values(
                    id=message_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                )
                .on_conflict_do_nothing(index_elements=["id"])
                .returning(ChatMessage.id)
            )
            result = await db.execute(stmt)
            inserted = result.scalar_one_or_none() is not None
            await db.commit()
        return inserted

    # ------------------------------------------------------------------ #
    # Workflows                                                           #
    # ------------------------------------------------------------------ #

    async def create_workflow(
        self,
        session_id: uuid.UUID,
        flow_id: str,
        steps: list[dict[str, Any]],
    ) -> uuid.UUID:
        """Create a new workflow row in 'running' state."""
        wf_id = uuid.uuid4()
        async with async_session_factory() as db:
            db.add(
                Workflow(
                    id=wf_id,
                    session_id=session_id,
                    flow_id=flow_id,
                    status="running",
                    current_step_idx=0,
                    steps={"steps": steps},
                    output=None,
                )
            )
            await db.commit()
        return wf_id

    async def update_step(
        self,
        workflow_id: uuid.UUID,
        step_idx: int,
        status: str,
        sub_status: str | None = None,
    ) -> None:
        """Patch a single step inside the JSONB list and bump current_step_idx."""
        async with async_session_factory() as db:
            wf = await db.get(Workflow, workflow_id)
            if wf is None:
                return
            steps = list(wf.steps.get("steps", []))
            if 0 <= step_idx < len(steps):
                steps[step_idx] = {
                    **steps[step_idx],
                    "status": status,
                    "subStatus": sub_status,
                }
                if status == "in_progress":
                    steps[step_idx]["startedAt"] = datetime.now(timezone.utc).isoformat()
                if status in ("completed", "blocked_awaiting_human"):
                    steps[step_idx]["endedAt"] = datetime.now(timezone.utc).isoformat()
            wf.steps = {"steps": steps}
            wf.current_step_idx = step_idx
            wf.updated_at = datetime.now(timezone.utc)
            await db.commit()

    async def set_status(
        self,
        workflow_id: uuid.UUID,
        status: str,
        output: dict[str, Any] | None = None,
    ) -> None:
        """Mark the workflow as awaiting_human, completed, or failed."""
        async with async_session_factory() as db:
            wf = await db.get(Workflow, workflow_id)
            if wf is None:
                return
            wf.status = status
            if output is not None:
                wf.output = output
            wf.updated_at = datetime.now(timezone.utc)
            if status == "completed":
                wf.completed_at = datetime.now(timezone.utc)
            await db.commit()

    async def get_workflow(self, workflow_id: uuid.UUID) -> Workflow | None:
        """Load a workflow and detach field values before the session closes."""
        async with async_session_factory() as db:
            wf = await db.get(Workflow, workflow_id)
            if wf is None:
                return None
            # Touch attributes while the session is open so callers can
            # safely read them after this method returns.
            _ = (
                wf.id,
                wf.session_id,
                wf.flow_id,
                wf.status,
                wf.current_step_idx,
                wf.steps,
                wf.output,
                wf.started_at,
                wf.updated_at,
                wf.completed_at,
            )
            db.expunge(wf)
            return wf


# Module-level singleton; routers import this.
workflow_store = WorkflowStore()
