"""EventLogger – append-only analytics writes (no PII)."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import func, select

from ..models.event import Event
from ..models.session import Session as SessionModel
from ..models.workflow import Workflow
from .db import async_session_factory


class EventLogger:
    """Writes analytics events and serves admin aggregates."""

    async def log(
        self,
        session_id: str | uuid.UUID,
        event_type: str,
        *,
        flow_id: str | None = None,
        prompt: str | None = None,
        duration_ms: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        sid = uuid.UUID(str(session_id))
        prompt_hash = None
        if prompt:
            prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        async with async_session_factory() as db:
            db.add(
                Event(
                    session_id=sid,
                    event_type=event_type,
                    flow_id=flow_id,
                    prompt_hash=prompt_hash,
                    duration_ms=duration_ms,
                    meta=meta,
                )
            )
            await db.commit()

    async def get_stats(self) -> dict[str, Any]:
        async with async_session_factory() as db:
            sessions = await db.scalar(select(func.count()).select_from(SessionModel))
            started = await db.scalar(select(func.count()).select_from(Workflow))
            completed = await db.scalar(
                select(func.count())
                .select_from(Workflow)
                .where(Workflow.status == "completed")
            )
            failed = await db.scalar(
                select(func.count())
                .select_from(Workflow)
                .where(Workflow.status == "failed")
            )
            awaiting = await db.scalar(
                select(func.count())
                .select_from(Workflow)
                .where(Workflow.status == "awaiting_human")
            )

        return {
            "sessions": int(sessions or 0),
            "workflowsStarted": int(started or 0),
            "workflowsCompleted": int(completed or 0),
            "workflowsFailed": int(failed or 0),
            "workflowsAwaitingHuman": int(awaiting or 0),
        }

    async def get_recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        async with async_session_factory() as db:
            result = await db.execute(
                select(Event).order_by(Event.created_at.desc()).limit(limit)
            )
            rows = result.scalars().all()

        return [
            {
                "id": row.id,
                "sessionId": str(row.session_id),
                "eventType": row.event_type,
                "flowId": row.flow_id,
                "promptHash": row.prompt_hash,
                "durationMs": row.duration_ms,
                "metadata": row.meta,
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]


event_logger = EventLogger()
