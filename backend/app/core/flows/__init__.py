"""Declarative flow definitions for the Week 1 FlowSimulator.

Each flow is a list of `Step` objects describing the user-facing
title, expected duration range, narration prompt, and (for the
final step) a template for the simulated output identifier.

Flow definitions are deliberately data-only so adding flows in
future weeks is configuration, not code.
"""

from .step import Step
from .incorporation import INCORPORATION_FLOW
from .gst_filing import GST_FILING_FLOW
from .se_license import SE_LICENSE_FLOW

FLOWS: dict[str, list[Step]] = {
    "incorporation": INCORPORATION_FLOW,
    "gst_filing": GST_FILING_FLOW,
    "se_license": SE_LICENSE_FLOW,
}

__all__ = [
    "Step",
    "FLOWS",
    "INCORPORATION_FLOW",
    "GST_FILING_FLOW",
    "SE_LICENSE_FLOW",
]
