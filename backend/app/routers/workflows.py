"""Workflow router – GET /api/workflows/{id}, POST /api/workflows/{id}/resume."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..core.runner import runner
from ..store.workflow_store import workflow_store

router = APIRouter(tags=["workflows"])


class ResumeRequest(BaseModel):
    """Body for POST /api/workflows/{id}/resume."""

    approved: bool
    approval_id: str | None = Field(default=None, alias="approvalId")

    model_config = {"populate_by_name": True}


class ResumeResponse(BaseModel):
    workflow_id: str = Field(..., alias="workflowId")
    status: str
    accepted: bool = True

    model_config = {"populate_by_name": True}


def _to_snapshot(wf: Any) -> dict[str, Any]:
    """Convert a Workflow ORM row into the frontend WorkflowSnapshot shape."""
    steps_raw = wf.steps.get("steps", []) if isinstance(wf.steps, dict) else []
    steps = []
    for step in steps_raw:
        steps.append(
            {
                "idx": step.get("idx", 0),
                "id": step.get("id", ""),
                "title": step.get("title", ""),
                "status": step.get("status", "pending"),
                "subStatus": step.get("subStatus"),
                "startedAt": step.get("startedAt"),
                "endedAt": step.get("endedAt"),
            }
        )

    return {
        "workflowId": str(wf.id),
        "sessionId": str(wf.session_id),
        "flowId": wf.flow_id,
        "status": wf.status,
        "currentStepIdx": wf.current_step_idx,
        "steps": steps,
        "output": wf.output,
        "startedAt": wf.started_at.isoformat() if wf.started_at else "",
        "updatedAt": wf.updated_at.isoformat() if wf.updated_at else "",
        "completedAt": wf.completed_at.isoformat() if wf.completed_at else None,
    }


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Fetch full workflow snapshot for UI rehydration after refresh/reconnect."""
    try:
        wf_uuid = uuid.UUID(workflow_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workflowId",
        ) from exc

    wf = await workflow_store.get_workflow(wf_uuid)
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    return _to_snapshot(wf)


@router.post(
    "/workflows/{workflow_id}/resume",
    response_model=ResumeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resume_workflow(workflow_id: str, body: ResumeRequest) -> ResumeResponse:
    """Approve or reject a blocked human-approval step.

    Idempotent on approvalId: a retried request with the same approvalId
    returns success without re-driving the simulator.
    """
    try:
        wf_uuid = uuid.UUID(workflow_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workflowId",
        ) from exc

    wf = await workflow_store.get_workflow(wf_uuid)
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    if wf.status != "awaiting_human":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow is '{wf.status}', expected 'awaiting_human'",
        )

    # Idempotent retry: same approvalId already processed.
    if body.approval_id and runner.was_approval_processed(workflow_id, body.approval_id):
        return ResumeResponse(
            workflow_id=workflow_id,
            status=wf.status,
            accepted=True,
        )

    if not runner.has_simulator(workflow_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Workflow is not active in this process. "
                "Refresh the page and start a new flow."
            ),
        )

    if body.approval_id:
        runner.mark_approval_processed(workflow_id, body.approval_id)

    session_id = str(wf.session_id)
    asyncio.create_task(
        runner.resume(
            workflow_id=workflow_id,
            session_id=session_id,
            approved=body.approved,
        )
    )

    return ResumeResponse(
        workflow_id=workflow_id,
        status="running" if body.approved else "failed",
        accepted=True,
    )
