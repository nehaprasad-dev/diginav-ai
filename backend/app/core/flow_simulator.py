"""FlowSimulator – Week 1 implementation of the AgentRuntime Protocol.

Walks a declarative flow definition step-by-step, emits AgentEvents over
an async iterator, and pauses on `requires_human` steps until `resume()`
is called with an approval decision.

This is the only AgentRuntime implementation in Week 1. In Week 2 it will
be replaced by `LangGraphAgent` without changes to the routers or
frontend, since both depend only on the Protocol + AgentEvent contract.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from typing import AsyncIterator

from .events import (
    AgentEvent,
    AwaitingHumanEvent,
    ErrorEvent,
    StepSummary,
    StepUpdateEvent,
    TokenEvent,
    WorkflowCompletedEvent,
    WorkflowStartedEvent,
)
from .flows import FLOWS, Step
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class FlowSimulator:
    """Drives a single workflow from start to completion.

    A new instance is created per workflow. The instance owns:
    - the flow definition (immutable list of `Step`)
    - the workflow id
    - an `asyncio.Event` used to gate execution at human-approval steps
    - the latest approval decision (set just before `_resume_event.set()`)
    """

    def __init__(
        self,
        flow_id: str,
        workflow_id: str | None = None,
        session_id: str = "",
        llm: LLMClient | None = None,
    ):
        if flow_id not in FLOWS:
            raise ValueError(f"Unknown flow_id: {flow_id}")

        self.flow_id = flow_id
        self.workflow_id = workflow_id or str(uuid.uuid4())
        self.session_id = session_id
        self._steps: list[Step] = FLOWS[flow_id]
        self._llm = llm or LLMClient()

        # Human-in-the-loop gating: tracks the latest approval decision.
        # `None` means "the gating step has emitted awaiting_human and the
        # iterator has stopped; waiting for resume()".
        self._approved: bool | None = None

        # Track current step index for resume / state queries
        self._current_idx = 0

    # ------------------------------------------------------------------ #
    # AgentRuntime Protocol                                              #
    # ------------------------------------------------------------------ #

    async def start(
        self, session_id: str = "", user_message: str = ""
    ) -> AsyncIterator[AgentEvent]:
        """Run the flow from step 0 to terminal.

        Yields the initial `workflow_started` followed by an interleaved
        sequence of `step_update`, `token`, `awaiting_human`, and finally
        either `workflow_completed` or `error`.
        """
        if session_id:
            self.session_id = session_id

        # Announce the plan up front so the dashboard can render all steps
        yield WorkflowStartedEvent(
            workflow_id=self.workflow_id,
            flow=self.flow_id,
            steps=tuple(
                StepSummary(
                    idx=i,
                    id=s.id,
                    title=s.title,
                    requires_human=s.requires_human,
                )
                for i, s in enumerate(self._steps)
            ),
        )

        async for event in self._run_from(0):
            yield event

    async def resume(
        self, workflow_id: str, approval: bool
    ) -> AsyncIterator[AgentEvent]:
        """Continue execution after a human approval decision.

        On approve: advance past the human step and continue.
        On reject: emit a final `error` event and mark the workflow failed.
        """
        if workflow_id != self.workflow_id:
            yield ErrorEvent(
                message=f"Unknown workflow_id {workflow_id}",
                correlation_id=str(uuid.uuid4()),
                recoverable=False,
            )
            return

        self._approved = approval

        if not approval:
            # Mark the gating step as blocked-rejected and stop
            yield StepUpdateEvent(
                workflow_id=self.workflow_id,
                step_idx=self._current_idx,
                status="blocked_awaiting_human",
                sub_status="Rejected by user",
            )
            yield ErrorEvent(
                message="Workflow cancelled by user",
                correlation_id=str(uuid.uuid4()),
                recoverable=False,
            )
            return

        # Approved: complete the gating step and continue from the next one
        yield StepUpdateEvent(
            workflow_id=self.workflow_id,
            step_idx=self._current_idx,
            status="completed",
        )
        async for event in self._run_from(self._current_idx + 1):
            yield event

    async def get_state(self, workflow_id: str):
        """Stub – the real WorkflowStore handles snapshot reads in task 4.3."""
        raise NotImplementedError("get_state is provided by WorkflowStore, not the simulator")

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #

    async def _run_from(self, start_idx: int) -> AsyncIterator[AgentEvent]:
        """Run steps[start_idx:] until done, awaiting_human, or error."""
        for idx in range(start_idx, len(self._steps)):
            self._current_idx = idx
            step = self._steps[idx]

            try:
                async for event in self._execute_step(idx, step):
                    yield event
            except Exception as exc:  # noqa: BLE001 – surface any error to client
                logger.exception("Step %d (%s) failed", idx, step.id)
                yield ErrorEvent(
                    message=f"Step '{step.title}' failed: {exc}",
                    correlation_id=str(uuid.uuid4()),
                    recoverable=False,
                )
                return

            # If step required human approval and we returned without
            # advancing (waiting on resume), stop the iterator. resume()
            # will continue execution from idx + 1.
            if step.requires_human and self._approved is None:
                return

        # All steps complete – emit workflow_completed with the final output
        yield self._build_completed_event()

    async def _execute_step(
        self, idx: int, step: Step
    ) -> AsyncIterator[AgentEvent]:
        """Execute a single step, emitting step_update + token events."""
        # --- begin step ---
        yield StepUpdateEvent(
            workflow_id=self.workflow_id,
            step_idx=idx,
            status="in_progress",
            sub_status=None,
        )

        if step.requires_human:
            # Stream a brief narration for context, then pause for approval.
            # We emit awaiting_human and return — start()'s iterator ends here.
            # resume() will pick up from idx + 1 on its own iterator.
            message_id = str(uuid.uuid4())
            async for token in self._llm.stream_narration(
                step.narration_prompt, step_id=step.id
            ):
                yield TokenEvent(text=token, message_id=message_id)

            yield StepUpdateEvent(
                workflow_id=self.workflow_id,
                step_idx=idx,
                status="blocked_awaiting_human",
            )
            yield AwaitingHumanEvent(
                workflow_id=self.workflow_id,
                step_idx=idx,
                prompt=step.title,
                approval_id=str(uuid.uuid4()),
            )
            # Reset gating state. _run_from will detect _approved is None
            # and stop iteration cleanly so the SSE channel is freed.
            self._approved = None
            return

        # Normal step: stream narration concurrently with simulated work
        message_id = str(uuid.uuid4())
        async for token in self._llm.stream_narration(
            step.narration_prompt, step_id=step.id
        ):
            yield TokenEvent(text=token, message_id=message_id)

        # Sleep a randomized duration in [lo, hi] (Req 3.4: 3-15s real time)
        lo, hi = step.duration_range
        if hi > 0:
            await asyncio.sleep(random.uniform(lo, hi))

        yield StepUpdateEvent(
            workflow_id=self.workflow_id,
            step_idx=idx,
            status="completed",
        )

    def _build_completed_event(self) -> WorkflowCompletedEvent:
        """Generate the final WorkflowCompletedEvent with simulated output."""
        terminal = self._steps[-1]
        output: dict[str, str] = {}
        if terminal.final_output_template:
            rand = random.randint(100_000, 999_999_999)
            rendered = terminal.final_output_template.format(rand=rand)
            # Templates are "<KEY>: <value>" – split for structured output
            if ": " in rendered:
                key, value = rendered.split(": ", 1)
                output[_to_snake(key)] = value
            else:
                output["result"] = rendered

        return WorkflowCompletedEvent(
            workflow_id=self.workflow_id,
            output=output,
        )


def _to_snake(label: str) -> str:
    """Convert a human label like 'SE License' to a JSON key 'se_license'."""
    return "_".join(label.lower().split())
