"""Shops & Establishment License flow – 5 steps per Req 3.3.

Steps: detect state → fetch state-specific form → pre-fill from profile →
human approval → license number issuance.
"""

from .step import Step


SE_LICENSE_FLOW: list[Step] = [
    Step(
        id="se_detect_state",
        title="Detect business state",
        duration_range=(3, 6),
        narration_prompt=(
            "Identifying the user's state to apply the correct Shops & "
            "Establishments Act variant. Narrate in 2-3 sentences."
        ),
    ),
    Step(
        id="se_fetch_form",
        title="Fetch state-specific application form",
        duration_range=(4, 8),
        narration_prompt=(
            "Retrieving the latest state-specific Shops & Establishment "
            "registration form. Narrate in 2-3 sentences."
        ),
    ),
    Step(
        id="se_prefill",
        title="Pre-fill form from business profile",
        duration_range=(4, 8),
        narration_prompt=(
            "Pre-filling the application using the saved business profile "
            "(name, address, employee count). Narrate in 2-3 sentences."
        ),
    ),
    Step(
        id="se_human_review",
        title="Review and approve application",
        duration_range=(0, 0),
        narration_prompt=(
            "The pre-filled application is ready for the user to review "
            "and approve. Briefly state what is awaiting approval."
        ),
        requires_human=True,
    ),
    Step(
        id="se_issue_license",
        title="Submit application and receive license number",
        duration_range=(5, 10),
        narration_prompt=(
            "Submitting to the local labour department portal. "
            "License number is being issued. Narrate completion in 2-3 sentences."
        ),
        final_output_template="SE License: SE/{rand:08}",
    ),
]
