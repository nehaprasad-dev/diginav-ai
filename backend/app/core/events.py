"""Typed event dataclasses matching the AgentEvent discriminated union."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class TokenEvent:
    type: Literal["token"] = field(default="token", init=False)
    text: str = ""
    message_id: str = ""


@dataclass(frozen=True, slots=True)
class IntentDetectedEvent:
    type: Literal["intent_detected"] = field(default="intent_detected", init=False)
    flow: str = ""
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class StepSummary:
    idx: int = 0
    id: str = ""
    title: str = ""
    requires_human: bool = False


@dataclass(frozen=True, slots=True)
class WorkflowStartedEvent:
    type: Literal["workflow_started"] = field(default="workflow_started", init=False)
    workflow_id: str = ""
    flow: str = ""
    steps: tuple[StepSummary, ...] = ()


@dataclass(frozen=True, slots=True)
class StepUpdateEvent:
    type: Literal["step_update"] = field(default="step_update", init=False)
    workflow_id: str = ""
    step_idx: int = 0
    status: str = "pending"
    sub_status: str | None = None


@dataclass(frozen=True, slots=True)
class AwaitingHumanEvent:
    type: Literal["awaiting_human"] = field(default="awaiting_human", init=False)
    workflow_id: str = ""
    step_idx: int = 0
    prompt: str = ""
    approval_id: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowCompletedEvent:
    type: Literal["workflow_completed"] = field(default="workflow_completed", init=False)
    workflow_id: str = ""
    output: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    type: Literal["error"] = field(default="error", init=False)
    message: str = ""
    correlation_id: str = ""
    recoverable: bool = True


# Union type for type-checking convenience
AgentEvent = (
    TokenEvent
    | IntentDetectedEvent
    | WorkflowStartedEvent
    | StepUpdateEvent
    | AwaitingHumanEvent
    | WorkflowCompletedEvent
    | ErrorEvent
)
