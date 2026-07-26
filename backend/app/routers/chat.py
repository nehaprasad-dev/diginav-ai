"""Chat router – POST /api/chat, GET /api/stream/{session_id}.

POST /api/chat
    Accepts a chat message, classifies intent, and (if a regulatory flow
    is detected) starts a background workflow. Returns immediately with
    a stream URL so the frontend can attach SSE.

The endpoint is idempotent on `messageId` so retried requests from a
flaky mobile network don't double-create workflows.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from ..core.event_broker import broker
from ..core.events import IntentDetectedEvent, TokenEvent
from ..core.intent_classifier import IntentClassifier
from ..core.llm_client import LLMClient
from ..core.runner import runner
from ..store.event_logger import event_logger
from ..store.workflow_store import workflow_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

_classifier = IntentClassifier()
_llm = LLMClient()

_FLOW_INTENTS: set[str] = {"incorporation", "gst_filing", "se_license"}


class ChatRequest(BaseModel):
    """Body for POST /api/chat."""

    session_id: str = Field(
        ...,
        alias="sessionId",
        description="Client-generated UUIDv4 identifying the browser session.",
    )
    message: str = Field(..., min_length=1, max_length=4000)
    message_id: str = Field(
        ...,
        alias="messageId",
        description="Client-generated UUID for idempotent retries.",
    )

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    """Response from POST /api/chat."""

    stream_url: str = Field(..., alias="streamUrl")
    workflow_id: str | None = Field(default=None, alias="workflowId")
    intent: Literal["incorporation", "gst_filing", "se_license", "general_chat"]
    confidence: float = Field(..., ge=0.0, le=1.0)

    model_config = {"populate_by_name": True}


async def _stream_general_chat(session_id: str, user_message: str) -> None:
    """Publish a one-shot assistant reply for non-workflow questions."""
    assistant_message_id = str(uuid.uuid4())
    prompt = (
        "Answer this founder question about Indian business compliance "
        f"in 2-4 short sentences:\n\n{user_message}"
    )
    try:
        async for token in _llm.stream_narration(prompt, step_id="general_chat"):
            await broker.publish(
                session_id,
                TokenEvent(text=token, message_id=assistant_message_id),
            )
    except Exception:  # noqa: BLE001
        logger.exception("General chat stream failed for session %s", session_id)


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_chat(body: ChatRequest) -> ChatResponse:
    """Accept a user message and (optionally) start a workflow."""
    session_uuid = await workflow_store.ensure_session(body.session_id)
    msg_uuid = uuid.UUID(body.message_id)

    inserted = await workflow_store.append_message(
        session_id=session_uuid,
        message_id=msg_uuid,
        role="user",
        content=body.message,
    )
    if not inserted:
        logger.info(
            "Duplicate message_id %s on session %s",
            body.message_id,
            body.session_id,
        )
        return ChatResponse(
            stream_url=f"/api/stream/{body.session_id}",
            workflow_id=None,
            intent="general_chat",
            confidence=0.0,
        )

    intent, confidence = await _classifier.classify(body.message)

    try:
        await event_logger.log(
            body.session_id,
            "message_sent",
            flow_id=intent if intent in _FLOW_INTENTS else None,
            prompt=body.message,
            meta={"confidence": confidence},
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to log message_sent analytics event")

    workflow_id: str | None = None
    if intent in _FLOW_INTENTS:
        await broker.publish(
            body.session_id,
            IntentDetectedEvent(flow=intent, confidence=confidence),
        )
        sim, workflow_id = await runner.prepare(
            session_id=body.session_id,
            flow_id=intent,
        )
        try:
            await event_logger.log(
                body.session_id,
                "workflow_started",
                flow_id=intent,
                meta={"workflowId": workflow_id},
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to log workflow_started analytics event")
        asyncio.create_task(
            runner.drain_start(sim, body.session_id, body.message)
        )
    else:
        asyncio.create_task(_stream_general_chat(body.session_id, body.message))

    return ChatResponse(
        stream_url=f"/api/stream/{body.session_id}",
        workflow_id=workflow_id,
        intent=intent,  # type: ignore[arg-type]
        confidence=confidence,
    )


@router.get("/stream/{session_id}")
async def stream_events(session_id: str):
    """SSE stream of `AgentEvent`s for the given session."""
    from sse_starlette.sse import EventSourceResponse

    from ..core.event_serializer import event_to_dict

    async def event_generator():
        async for event in broker.subscribe(session_id):
            yield {
                "event": event.type,
                "data": json.dumps(event_to_dict(event)),
            }

    return EventSourceResponse(event_generator(), ping=15, sep="\n")
