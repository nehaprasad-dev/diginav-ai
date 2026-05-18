"""Incorporation flow – 8 steps per Req 3.1.

Steps: name reservation (RUN) → DIN application → DSC issuance →
MoA/AoA drafting → SPICe+ Part B submission → human review →
PAN/TAN allotment → CIN generation.
"""

from .step import Step


INCORPORATION_FLOW: list[Step] = [
    Step(
        id="name_reserve",
        title="Reserve company name (RUN)",
        duration_range=(4, 8),
        narration_prompt=(
            "We just submitted a Reserve Unique Name (RUN) application to MCA "
            "to lock in the proposed company name. Narrate this in 2-3 sentences."
        ),
    ),
    Step(
        id="din_apply",
        title="Apply for Director Identification Number (DIN)",
        duration_range=(5, 10),
        narration_prompt=(
            "We're applying for DIN for the proposed directors via SPICe+ Part A. "
            "Narrate progress in 2-3 sentences."
        ),
    ),
    Step(
        id="dsc_issue",
        title="Issue Digital Signature Certificate (DSC)",
        duration_range=(4, 8),
        narration_prompt=(
            "Requesting DSCs from a licensed Certifying Authority for each director. "
            "Narrate this step in 2-3 sentences."
        ),
    ),
    Step(
        id="moa_aoa",
        title="Draft Memorandum and Articles of Association",
        duration_range=(5, 10),
        narration_prompt=(
            "Drafting MoA and AoA based on standard Table F clauses for a "
            "private limited company. Narrate in 2-3 sentences."
        ),
    ),
    Step(
        id="spice_b",
        title="Submit SPICe+ Part B application",
        duration_range=(6, 12),
        narration_prompt=(
            "Filing SPICe+ Part B with all incorporation details. "
            "Narrate the submission in 2-3 sentences."
        ),
    ),
    Step(
        id="human_review",
        title="Review and approve submission",
        duration_range=(0, 0),  # paused until human acts
        narration_prompt=(
            "All documents are ready for the founder's review before final "
            "submission to the Registrar. Briefly state what is awaiting approval."
        ),
        requires_human=True,
    ),
    Step(
        id="pan_tan",
        title="Allot PAN and TAN",
        duration_range=(4, 8),
        narration_prompt=(
            "PAN and TAN are being allotted via the integrated CBDT linkage. "
            "Narrate in 2-3 sentences."
        ),
    ),
    Step(
        id="cin_gen",
        title="Generate Corporate Identity Number (CIN)",
        duration_range=(3, 6),
        narration_prompt=(
            "The Registrar has approved incorporation. CIN is being generated. "
            "Narrate the successful completion in 2-3 sentences."
        ),
        final_output_template="CIN: U72900MH2026PTC{rand:06}",
    ),
]
