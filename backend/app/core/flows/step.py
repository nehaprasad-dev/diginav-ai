"""Step dataclass shared by all flow definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Step:
    """A single declarative step in a flow.

    Attributes:
        id: Stable identifier (used for scripted-fallback narration lookup).
        title: User-facing label shown on the dashboard StepCard.
        duration_range: (min, max) seconds the simulator sleeps to mimic real work.
            Per Req 3.4 each step takes 3-15s.
        narration_prompt: Prompt sent to the LLM to generate the chat narration
            for this step.
        requires_human: When True the simulator emits `awaiting_human` and pauses
            until `resume()` is called.
        final_output_template: For the terminal step, a Python format string
            (e.g. "CIN: U72900MH2026PTC{rand:06}") that produces the simulated
            output identifier returned in `workflow_completed.output`.
    """

    id: str
    title: str
    duration_range: tuple[int, int] = (4, 8)
    narration_prompt: str = ""
    requires_human: bool = False
    final_output_template: str | None = None
