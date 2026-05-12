"""Chat router – POST /api/chat, GET /api/stream/{session_id}."""

from fastapi import APIRouter

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def post_chat():
    """Accept a user message and return a stream URL. (Stub – implemented in later task.)"""
    return {"detail": "not implemented yet"}


@router.get("/stream/{session_id}")
async def stream_events(session_id: str):
    """SSE stream of AgentEvents. (Stub – implemented in later task.)"""
    return {"detail": "not implemented yet"}
