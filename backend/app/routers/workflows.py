"""Workflow router – GET /api/workflows/{id}, POST /api/workflows/{id}/resume."""

from fastapi import APIRouter

router = APIRouter(tags=["workflows"])


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Fetch full workflow snapshot for rehydration. (Stub.)"""
    return {"detail": "not implemented yet"}


@router.post("/workflows/{workflow_id}/resume")
async def resume_workflow(workflow_id: str):
    """Approve or reject a blocked step. (Stub.)"""
    return {"detail": "not implemented yet"}
