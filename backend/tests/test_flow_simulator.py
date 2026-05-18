"""Unit tests for FlowSimulator.

Verifies the full AgentEvent sequence for each of the 3 flows, plus
human-approval pause/resume semantics. The LLM client is mocked so
tests are fast and deterministic.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.events import (
    AwaitingHumanEvent,
    ErrorEvent,
    StepUpdateEvent,
    TokenEvent,
    WorkflowCompletedEvent,
    WorkflowStartedEvent,
)
from app.core.flow_simulator import FlowSimulator
from app.core.flows import FLOWS


# -------------------------------------------------------------------------- #
# Fixtures                                                                    #
# -------------------------------------------------------------------------- #


class _FakeLLM:
    """Stub LLM client that yields a single fixed token per call.

    Sufficient for verifying that token events are emitted in the right
    place; no network or retry logic is involved.
    """

    async def stream_narration(self, prompt: str, step_id: str = ""):
        yield "ok"


@pytest.fixture
def fake_llm():
    return _FakeLLM()


@pytest.fixture(autouse=True)
def _no_sleep():
    """Patch asyncio.sleep so duration_range delays don't slow tests down."""
    async def _instant(*_args, **_kwargs):
        return None

    with patch("app.core.flow_simulator.asyncio.sleep", _instant):
        yield


async def _collect(aiter):
    """Drain an async iterator into a list."""
    return [event async for event in aiter]


# -------------------------------------------------------------------------- #
# Helpers                                                                     #
# -------------------------------------------------------------------------- #


def _expected_human_idx(flow_id: str) -> int:
    """Return the idx of the first human-approval step for the flow."""
    return next(
        i for i, step in enumerate(FLOWS[flow_id]) if step.requires_human
    )


# -------------------------------------------------------------------------- #
# start() event-sequence tests, parametrised across all 3 flows               #
# -------------------------------------------------------------------------- #


@pytest.mark.parametrize("flow_id", ["incorporation", "gst_filing", "se_license"])
@pytest.mark.asyncio
async def test_start_emits_workflow_started_first(flow_id, fake_llm):
    sim = FlowSimulator(flow_id, llm=fake_llm)
    events = await _collect(sim.start(session_id="sess-1"))

    assert isinstance(events[0], WorkflowStartedEvent)
    assert events[0].workflow_id == sim.workflow_id
    assert events[0].flow == flow_id
    assert len(events[0].steps) == len(FLOWS[flow_id])


@pytest.mark.parametrize("flow_id", ["incorporation", "gst_filing", "se_license"])
@pytest.mark.asyncio
async def test_start_runs_until_first_human_step(flow_id, fake_llm):
    """start() should pause exactly at the first awaiting_human event."""
    sim = FlowSimulator(flow_id, llm=fake_llm)
    events = await _collect(sim.start(session_id="sess-1"))

    awaiting = [e for e in events if isinstance(e, AwaitingHumanEvent)]
    assert len(awaiting) == 1, f"expected exactly one awaiting_human, got {len(awaiting)}"
    assert awaiting[0].step_idx == _expected_human_idx(flow_id)

    # No workflow_completed should have been emitted yet
    assert not any(isinstance(e, WorkflowCompletedEvent) for e in events)


@pytest.mark.parametrize("flow_id", ["incorporation", "gst_filing", "se_license"])
@pytest.mark.asyncio
async def test_each_pre_human_step_emits_in_progress_then_completed(flow_id, fake_llm):
    """For every step before the human gate we expect in_progress → completed."""
    sim = FlowSimulator(flow_id, llm=fake_llm)
    events = await _collect(sim.start(session_id="sess-1"))

    human_idx = _expected_human_idx(flow_id)
    updates = [e for e in events if isinstance(e, StepUpdateEvent)]

    for idx in range(human_idx):
        idx_updates = [u for u in updates if u.step_idx == idx]
        statuses = [u.status for u in idx_updates]
        assert statuses == ["in_progress", "completed"], (
            f"step {idx} statuses={statuses}"
        )


@pytest.mark.parametrize("flow_id", ["incorporation", "gst_filing", "se_license"])
@pytest.mark.asyncio
async def test_token_events_appear_for_each_executed_step(flow_id, fake_llm):
    sim = FlowSimulator(flow_id, llm=fake_llm)
    events = await _collect(sim.start(session_id="sess-1"))

    tokens = [e for e in events if isinstance(e, TokenEvent)]
    # Each step before-and-including the human gate streams narration
    expected_min_tokens = _expected_human_idx(flow_id) + 1
    assert len(tokens) >= expected_min_tokens


# -------------------------------------------------------------------------- #
# resume() with approve/reject                                                #
# -------------------------------------------------------------------------- #


@pytest.mark.parametrize("flow_id", ["incorporation", "gst_filing", "se_license"])
@pytest.mark.asyncio
async def test_full_flow_completes_after_approval(flow_id, fake_llm):
    """start() → human gate → resume(approved=True) → workflow_completed."""
    sim = FlowSimulator(flow_id, llm=fake_llm)

    pre = await _collect(sim.start(session_id="sess-1"))
    assert any(isinstance(e, AwaitingHumanEvent) for e in pre)

    post = await _collect(sim.resume(sim.workflow_id, approval=True))

    completed = [e for e in post if isinstance(e, WorkflowCompletedEvent)]
    assert len(completed) == 1
    assert completed[0].workflow_id == sim.workflow_id
    assert completed[0].output  # non-empty output dict


@pytest.mark.asyncio
async def test_incorporation_completed_event_contains_cin(fake_llm):
    sim = FlowSimulator("incorporation", llm=fake_llm)
    await _collect(sim.start(session_id="s"))
    post = await _collect(sim.resume(sim.workflow_id, approval=True))

    completed = next(e for e in post if isinstance(e, WorkflowCompletedEvent))
    assert "cin" in completed.output
    assert completed.output["cin"].startswith("U72900MH2026PTC")


@pytest.mark.asyncio
async def test_gst_completed_event_contains_arn(fake_llm):
    sim = FlowSimulator("gst_filing", llm=fake_llm)
    await _collect(sim.start(session_id="s"))
    post = await _collect(sim.resume(sim.workflow_id, approval=True))

    completed = next(e for e in post if isinstance(e, WorkflowCompletedEvent))
    assert "arn" in completed.output
    assert completed.output["arn"].startswith("AA")


@pytest.mark.asyncio
async def test_se_license_completed_event_contains_license(fake_llm):
    sim = FlowSimulator("se_license", llm=fake_llm)
    await _collect(sim.start(session_id="s"))
    post = await _collect(sim.resume(sim.workflow_id, approval=True))

    completed = next(e for e in post if isinstance(e, WorkflowCompletedEvent))
    assert "se_license" in completed.output
    assert completed.output["se_license"].startswith("SE/")


@pytest.mark.asyncio
async def test_resume_with_rejection_emits_error_and_no_completion(fake_llm):
    sim = FlowSimulator("incorporation", llm=fake_llm)
    await _collect(sim.start(session_id="s"))

    post = await _collect(sim.resume(sim.workflow_id, approval=False))
    assert any(isinstance(e, ErrorEvent) for e in post)
    assert not any(isinstance(e, WorkflowCompletedEvent) for e in post)


@pytest.mark.asyncio
async def test_resume_with_unknown_workflow_id_emits_error(fake_llm):
    sim = FlowSimulator("incorporation", llm=fake_llm)
    post = await _collect(sim.resume("not-the-real-id", approval=True))
    assert len(post) == 1
    assert isinstance(post[0], ErrorEvent)
    assert post[0].recoverable is False


# -------------------------------------------------------------------------- #
# Construction guards                                                         #
# -------------------------------------------------------------------------- #


def test_unknown_flow_id_raises():
    with pytest.raises(ValueError, match="Unknown flow_id"):
        FlowSimulator("not_a_real_flow")
