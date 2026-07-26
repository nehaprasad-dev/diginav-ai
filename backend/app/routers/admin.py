"""Admin router – /api/admin/stats, /api/admin/events (secret-gated)."""

from fastapi import APIRouter, Header, HTTPException

from ..config import settings
from ..store.event_logger import event_logger

router = APIRouter(tags=["admin"])


def _verify_admin_token(x_admin_token: str = Header(...)) -> None:
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")


@router.get("/stats")
async def admin_stats(x_admin_token: str = Header(...)):
    """Aggregated counts for the /admin page."""
    _verify_admin_token(x_admin_token)
    return await event_logger.get_stats()


@router.get("/events")
async def admin_events(x_admin_token: str = Header(...)):
    """Last 50 analytics events for the /admin page."""
    _verify_admin_token(x_admin_token)
    return {"events": await event_logger.get_recent_events(limit=50)}
