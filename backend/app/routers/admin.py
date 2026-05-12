"""Admin router – /api/admin/stats, /api/admin/events (secret-gated)."""

from fastapi import APIRouter, Header, HTTPException

from ..config import settings

router = APIRouter(tags=["admin"])


def _verify_admin_token(x_admin_token: str = Header(...)):
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")


@router.get("/stats", dependencies=[])
async def admin_stats(x_admin_token: str = Header(...)):
    """Aggregated counts for /admin page. (Stub.)"""
    _verify_admin_token(x_admin_token)
    return {"detail": "not implemented yet"}


@router.get("/events")
async def admin_events(x_admin_token: str = Header(...)):
    """Last 50 events for /admin page. (Stub.)"""
    _verify_admin_token(x_admin_token)
    return {"detail": "not implemented yet"}
