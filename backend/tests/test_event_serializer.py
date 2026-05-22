"""Verify AgentEvent → wire-format JSON conversion.

These tests pin the contract with the frontend `lib/types.ts` so any
field rename on either side breaks loudly here instead of silently in
production.
"""

from __future__ import annotations

from app.core.event_serializer import event_to_dict
from app.core.events import (
    AwaitingHumanEvent,
    ErrorEvent,
    IntentDetectedEvent,
    StepSummary,
    StepUpdateEvent,
    TokenEvent,
    WorkflowCompletedEvent,
    WorkflowStartedEvent,
)


class TestCamelCaseRenames:
    def test_token_event_uses_message_id_camel(self):
        out = event_to_dict(TokenEvent(text="hi", message_id="abc"))
        assert out == {"type": "token", "text": "hi", "messageId": "abc"}

    def test_step_update_renames_workflow_step_substatus(self):
        out = event_to_dict(
            StepUpdateEvent(
                workflow_id="wf-1",
                step_idx=2,
                status="in_progress",
                sub_status="Validating...",
            )
        )
        assert out == {
            "type": "step_update",
            "workflowId": "wf-1",
            "stepIdx": 2,
            "status": "in_progress",
            "subStatus": "Validating...",
        }

    def test_awaiting_human_includes_approval_id(self):
        out = event_to_dict(
            AwaitingHumanEvent(
                workflow_id="wf-1",
                step_idx=5,
                prompt="Approve filing?",
                approval_id="appr-42",
            )
        )
        assert out["workflowId"] == "wf-1"
        assert out["stepIdx"] == 5
        assert out["approvalId"] == "appr-42"
        assert out["prompt"] == "Approve filing?"

    def test_workflow_completed_keeps_output_dict(self):
        out = event_to_dict(
            WorkflowCompletedEvent(
                workflow_id="wf-1",
                output={"cin": "U72900MH2026PTC123456"},
            )
        )
        assert out["workflowId"] == "wf-1"
        assert out["output"] == {"cin": "U72900MH2026PTC123456"}

    def test_error_event_camelizes_correlation_id(self):
        out = event_to_dict(
            ErrorEvent(
                message="Boom", correlation_id="corr-1", recoverable=True
            )
        )
        assert out == {
            "type": "error",
            "message": "Boom",
            "correlationId": "corr-1",
            "recoverable": True,
        }


class TestNestedSteps:
    def test_workflow_started_steps_use_requires_human_camel(self):
        out = event_to_dict(
            WorkflowStartedEvent(
                workflow_id="wf-1",
                flow="incorporation",
                steps=(
                    StepSummary(idx=0, id="name", title="Reserve name"),
                    StepSummary(idx=1, id="rev", title="Review", requires_human=True),
                ),
            )
        )
        assert out["workflowId"] == "wf-1"
        assert out["flow"] == "incorporation"
        assert out["steps"] == [
            {"idx": 0, "id": "name", "title": "Reserve name", "requiresHuman": False},
            {"idx": 1, "id": "rev", "title": "Review", "requiresHuman": True},
        ]


class TestPassthroughFields:
    def test_intent_detected_has_no_renames(self):
        out = event_to_dict(IntentDetectedEvent(flow="gst_filing", confidence=0.91))
        assert out == {
            "type": "intent_detected",
            "flow": "gst_filing",
            "confidence": 0.91,
        }
