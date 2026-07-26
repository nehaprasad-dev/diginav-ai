"""Unit tests for workflow GET and resume endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core import runner as runner_module
from app.routers import workflows as workflows_router
from app.store import workflow_store as ws_module


class _FakeWorkflow:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.session_id = uuid.uuid4()
        self.flow_id = "incorporation"
        self.status = "awaiting_human"
        self.current_step_idx = 5
        self.steps = {
            "steps": [
                {
                    "idx": 0,
                    "id": "name_reserve",
                    "title": "Reserve name",
                    "status": "completed",
                    "subStatus": None,
                },
                {
                    "idx": 5,
                    "id": "human_review",
                    "title": "Review documents",
                    "status": "blocked_awaiting_human",
                    "subStatus": None,
                },
            ]
        }
        self.output = None
        self.started_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.completed_at = None


class _StubStore:
    def __init__(self, wf: _FakeWorkflow | None = None) -> None:
        self.wf = wf

    async def get_workflow(self, workflow_id: uuid.UUID):
        if self.wf and self.wf.id == workflow_id:
            return self.wf
        return None


class _StubRunner:
    def __init__(self) -> None:
        self.processed: set[str] = set()
        self.resume_calls: list[dict[str, Any]] = []
        self._has_sim = True

    def has_simulator(self, workflow_id: str) -> bool:
        return self._has_sim

    def was_approval_processed(self, workflow_id: str, approval_id: str) -> bool:
        return f"{workflow_id}:{approval_id}" in self.processed

    def mark_approval_processed(self, workflow_id: str, approval_id: str) -> None:
        self.processed.add(f"{workflow_id}:{approval_id}")

    async def resume(self, workflow_id: str, session_id: str, approved: bool) -> None:
        self.resume_calls.append(
            {
                "workflow_id": workflow_id,
                "session_id": session_id,
                "approved": approved,
            }
        )


@pytest.fixture
def fake_wf():
    return _FakeWorkflow()


@pytest.fixture
def client(fake_wf):
    store = _StubStore(fake_wf)
    stub_runner = _StubRunner()

    with patch.object(workflows_router, "workflow_store", store), \
         patch.object(workflows_router, "runner", stub_runner), \
         patch.object(ws_module, "workflow_store", store), \
         patch.object(runner_module, "runner", stub_runner):
        with TestClient(app) as test_client:
            test_client.fake_wf = fake_wf  # type: ignore[attr-defined]
            test_client.stub_runner = stub_runner  # type: ignore[attr-defined]
            yield test_client


def test_get_workflow_snapshot(client, fake_wf):
    response = client.get(f"/api/workflows/{fake_wf.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["workflowId"] == str(fake_wf.id)
    assert data["flowId"] == "incorporation"
    assert data["status"] == "awaiting_human"
    assert len(data["steps"]) == 2


def test_get_workflow_not_found(client):
    response = client.get(f"/api/workflows/{uuid.uuid4()}")
    assert response.status_code == 404


def test_resume_approved(client, fake_wf):
    response = client.post(
        f"/api/workflows/{fake_wf.id}/resume",
        json={"approved": True, "approvalId": "appr-1"},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["accepted"] is True
    assert data["workflowId"] == str(fake_wf.id)
    assert client.stub_runner.was_approval_processed(str(fake_wf.id), "appr-1")


def test_resume_idempotent(client, fake_wf):
    first = client.post(
        f"/api/workflows/{fake_wf.id}/resume",
        json={"approved": True, "approvalId": "appr-dup"},
    )
    second = client.post(
        f"/api/workflows/{fake_wf.id}/resume",
        json={"approved": True, "approvalId": "appr-dup"},
    )
    assert first.status_code == 202
    assert second.status_code == 202
    # Second call short-circuits before scheduling resume again.
    assert client.stub_runner.was_approval_processed(str(fake_wf.id), "appr-dup")


def test_resume_conflict_when_not_awaiting(client, fake_wf):
    fake_wf.status = "running"
    response = client.post(
        f"/api/workflows/{fake_wf.id}/resume",
        json={"approved": True},
    )
    assert response.status_code == 409
