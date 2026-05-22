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
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from ..core.intent_classifier import IntentClassifier
from ..core.runner import runner
from ..store.workflow_store import workflow_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

# Single shared classifier; safe because it's stateless between calls.
_classifier = IntentClassifier()

# Set of regulatory flow IDs that should kick off a workflow. Anything
# else (general_chat) is answered by a one-shot LLM token stream and
# does not create a workflow row.
_FLOW_INTENTS: set[str] = {"incorporation", "gst_filing", "se_license"}


# --------------------------------------------------------------------- #
# Schemas                                                                #
# --------------------------------------------------------------------- #


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


# --------------------------------------------------------------------- #
# Endpoints                                                              #
# --------------------------------------------------------------------- #


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_chat(body: ChatRequest) -> ChatResponse:
    """Accept a user message and (optionally) start a workflow.

    Flow:
        1. Ensure the session row exists.
        2. Persist the user message; bail out idempotently on duplicate.
        3. Classify intent.
        4. If a regulatory flow is detected, spawn the runner as a
           background task and return the workflow_id immediately.
        5. Otherwise, return a stream URL and let the caller pull a
           general-chat token response (handled by GET /api/stream).
    """
    session_uuid = await workflow_store.ensure_session(body.session_id)
    msg_uuid = uuid.UUID(body.message_id)

    inserted = await workflow_store.append_message(
        session_id=session_uuid,
        message_id=msg_uuid,
        role="user",
        content=body.message,
    )
    if not inserted:
        # Same messageId seen before — this is a retry. Don't classify
        # again or start a duplicate workflow; just hand back the stream
        # URL so the client can re-attach.
        logger.info("Duplicate message_id %s on session %s", body.message_id, body.session_id)
        return ChatResponse(
            stream_url=f"/api/stream/{body.session_id}",
            workflow_id=None,
            intent="general_chat",
            confidence=0.0,
        )

    intent, confidence = await _classifier.classify(body.message)

    workflow_id: str | None = None
    if intent in _FLOW_INTENTS:
        # Synchronously create the workflow row + register simulator,
        # then schedule the long-running drain as a background task so
        # POST /api/chat returns in tens of milliseconds even though
        # the workflow itself runs for 30-90 seconds.
        sim, workflow_id = await runner.prepare(
            session_id=body.session_id,
            flow_id=intent,
        )
        asyncio.create_task(
            runner.drain_start(sim, body.session_id, body.message)
        )

    return ChatResponse(
        stream_url=f"/api/stream/{body.session_id}",
        workflow_id=workflow_id,
        intent=intent,  # type: ignore[arg-type]
        confidence=confidence,
    )


@router.get("/stream/{session_id}")
async def stream_events(session_id: str):
    """SSE stream of AgentEvents – implemented in task 4.2."""
    return {"detail": "not implemented yet"}
