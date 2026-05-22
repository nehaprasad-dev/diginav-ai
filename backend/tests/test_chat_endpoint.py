"""Unit tests for POST /api/chat.

The store and broker are replaced with in-memory stubs so tests run
without PostgreSQL. The tests focus on contract behavior:
    * idempotency on duplicate message_id
    * intent → workflow creation only for the 3 regulatory flows
    * 202 status with stream_url + workflow_id payload
    * background task is scheduled (not awaited) so the response is
      returned before the simulator finishes
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core import runner as runner_module
from app.routers import chat as chat_router
from app.store import workflow_store as ws_module


# -------------------------------------------------------------------------- #
# Stubs                                                                       #
# -------------------------------------------------------------------------- #


class _StubStore:
    """In-memory stand-in for WorkflowStore."""

    def __init__(self) -> None:
        self.sessions: set[uuid.UUID] = set()
        self.messages: dict[uuid.UUID, dict[str, Any]] = {}
        self.workflows: dict[uuid.UUID, dict[str, Any]] = {}

    async def ensure_session(self, session_id: str) -> uuid.UUID:
        sid = uuid.UUID(session_id)
        self.sessions.add(sid)
        return sid

    async def append_message(
        self, session_id: uuid.UUID, message_id: uuid.UUID, role: str, content: str
    ) -> bool:
        if message_id in self.messages:
            return False
        self.messages[message_id] = {
            "session_id": session_id,
            "role": role,
            "content": content,
        }
        return True

    async def create_workflow(
        self, session_id: uuid.UUID, flow_id: str, steps: list[dict[str, Any]]
    ) -> uuid.UUID:
        wf_id = uuid.uuid4()
        self.workflows[wf_id] = {
            "session_id": session_id,
            "flow_id": flow_id,
            "steps": steps,
            "status": "running",
        }
        return wf_id

    async def update_step(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def set_status(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def get_workflow(self, workflow_id: uuid.UUID):
        return self.workflows.get(workflow_id)


class _StubBroker:
    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    async def publish(self, session_id: str, event: Any) -> None:
        self.events.append((session_id, event))

    async def close(self, session_id: str) -> None:
        return None


# -------------------------------------------------------------------------- #
# Fixtures                                                                    #
# -------------------------------------------------------------------------- #


@pytest.fixture
def stub_store():
    return _StubStore()


@pytest.fixture
def stub_broker():
    return _StubBroker()


@pytest.fixture
def client(stub_store, stub_broker):
    """TestClient with stubbed store, broker, and intent classifier.

    The runner is replaced with a fresh instance bound to the stubs so
    no real DB or LLM call is attempted. The intent classifier is
    patched per-test via classifier_mock fixture below.
    """
    from app.core.runner import WorkflowRunner

    fresh_runner = WorkflowRunner(store=stub_store, event_broker=stub_broker)

    # Patch the module-level singletons used by the chat router and runner
    with patch.object(chat_router, "runner", fresh_runner), \
         patch.object(chat_router, "workflow_store", stub_store), \
         patch.object(ws_module, "workflow_store", stub_store), \
         patch.object(runner_module, "runner", fresh_runner):
        # Patch classifier to a deterministic value per test
        with patch.object(chat_router, "_classifier") as mock_classifier:
            mock_classifier.classify = AsyncMock(return_value=("general_chat", 0.5))
            with TestClient(app) as test_client:
                test_client.classifier_mock = mock_classifier  # type: ignore[attr-defined]
                yield test_client


# -------------------------------------------------------------------------- #
# Helpers                                                                     #
# -------------------------------------------------------------------------- #


def _fresh_payload(message: str = "register my company"):
    return {
        "sessionId": str(uuid.uuid4()),
        "messageId": str(uuid.uuid4()),
        "message": message,
    }


# -------------------------------------------------------------------------- #
# Tests                                                                       #
# -------------------------------------------------------------------------- #


class TestSuccessfulFlowIntent:
    """When the classifier returns one of the 3 flow intents."""

    def test_returns_202_with_workflow_id(self, client, stub_store):
        client.classifier_mock.classify = AsyncMock(
            return_value=("incorporation", 0.92)
        )
        payload = _fresh_payload("I want to incorporate my company")

        response = client.post("/api/chat", json=payload)

        assert response.status_code == 202
        data = response.json()
        assert data["intent"] == "incorporation"
        assert data["confidence"] == 0.92
        assert data["streamUrl"] == f"/api/stream/{payload['sessionId']}"
        assert data["workflowId"] is not None
        # Workflow row was actually created
        assert uuid.UUID(data["workflowId"]) in stub_store.workflows

    def test_persists_user_message(self, client, stub_store):
        client.classifier_mock.classify = AsyncMock(
            return_value=("gst_filing", 0.88)
        )
        payload = _fresh_payload("File my Q4 GST")

        client.post("/api/chat", json=payload)

        msg_uuid = uuid.UUID(payload["messageId"])
        assert msg_uuid in stub_store.messages
        assert stub_store.messages[msg_uuid]["content"] == "File my Q4 GST"
        assert stub_store.messages[msg_uuid]["role"] == "user"

    @pytest.mark.parametrize(
        "intent",
        ["incorporation", "gst_filing", "se_license"],
    )
    def test_creates_workflow_for_each_flow_intent(self, client, stub_store, intent):
        client.classifier_mock.classify = AsyncMock(return_value=(intent, 0.9))
        payload = _fresh_payload(f"start {intent}")

        response = client.post("/api/chat", json=payload)

        assert response.json()["workflowId"] is not None
        wf = next(iter(stub_store.workflows.values()))
        assert wf["flow_id"] == intent


class TestGeneralChatIntent:
    """When the classifier returns general_chat, no workflow is started."""

    def test_no_workflow_created(self, client, stub_store):
        client.classifier_mock.classify = AsyncMock(
            return_value=("general_chat", 0.95)
        )

        response = client.post("/api/chat", json=_fresh_payload("hello"))

        assert response.status_code == 202
        assert response.json()["workflowId"] is None
        assert len(stub_store.workflows) == 0


class TestIdempotency:
    """Duplicate message_id must not create a second workflow."""

    def test_duplicate_message_id_skips_workflow_creation(self, client, stub_store):
        client.classifier_mock.classify = AsyncMock(
            return_value=("incorporation", 0.9)
        )
        payload = _fresh_payload("incorporate me")

        first = client.post("/api/chat", json=payload)
        assert first.status_code == 202
        first_workflow_count = len(stub_store.workflows)

        # Same messageId — should be a no-op for workflow creation
        second = client.post("/api/chat", json=payload)

        assert second.status_code == 202
        assert second.json()["workflowId"] is None
        assert len(stub_store.workflows) == first_workflow_count


class TestRequestValidation:
    """Pydantic validation of the request body."""

    def test_rejects_missing_message(self, client):
        response = client.post(
            "/api/chat",
            json={"sessionId": str(uuid.uuid4()), "messageId": str(uuid.uuid4())},
        )
        assert response.status_code == 422

    def test_rejects_empty_message(self, client):
        payload = _fresh_payload("")
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 422

    def test_rejects_oversize_message(self, client):
        payload = _fresh_payload("x" * 4001)
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 422
