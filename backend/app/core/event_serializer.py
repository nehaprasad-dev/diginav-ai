"""Serialize AgentEvent dataclasses to the wire format expected by the UI.

The frontend's TypeScript `AgentEvent` discriminated union (see
`frontend/lib/types.ts`) uses camelCase keys. Internally we use Python
snake_case dataclasses. This module is the single boundary that
performs the rename so neither side has to know about the other's
naming convention.

We keep the converter table-driven instead of using a generic
`snake_to_camel` helper so adding fields is an explicit, reviewable
change — silent renames are a frequent source of frontend/backend
drift.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .events import (
    AgentEvent,
    AwaitingHumanEvent,
    ErrorEvent,
    StepUpdateEvent,
    TokenEvent,
    WorkflowCompletedEvent,
    WorkflowStartedEvent,
)


# Per-event-type, snake_case → camelCase rename maps. Kept explicit so
# any future field rename has to touch this file.
_FIELD_RENAMES: dict[type, dict[str, str]] = {
    TokenEvent: {"message_id": "messageId"},
    WorkflowStartedEvent: {"workflow_id": "workflowId"},
    StepUpdateEvent: {
        "workflow_id": "workflowId",
        "step_idx": "stepIdx",
        "sub_status": "subStatus",
    },
    AwaitingHumanEvent: {
        "workflow_id": "workflowId",
        "step_idx": "stepIdx",
        "approval_id": "approvalId",
    },
    WorkflowCompletedEvent: {"workflow_id": "workflowId"},
    ErrorEvent: {"correlation_id": "correlationId"},
}


def event_to_dict(event: AgentEvent) -> dict[str, Any]:
    """Convert an AgentEvent dataclass instance to a JSON-serializable dict."""
    raw = asdict(event)

    # Special-case: WorkflowStartedEvent's nested `steps` list also
    # carries a snake_case field (`requires_human`) the UI expects as
    # `requiresHuman`.
    if isinstance(event, WorkflowStartedEvent):
        raw["steps"] = [
            {
                "idx": s["idx"],
                "id": s["id"],
                "title": s["title"],
                "requiresHuman": s["requires_human"],
            }
            for s in raw.get("steps", ())
        ]

    renames = _FIELD_RENAMES.get(type(event), {})
    return {renames.get(k, k): v for k, v in raw.items()}
