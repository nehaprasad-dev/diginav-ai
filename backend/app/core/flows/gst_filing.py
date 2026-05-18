"""GST Filing flow – 6 steps per Req 3.2.

Steps: fetch sales data → compute tax liability → reconcile GSTR-2B →
generate GSTR-3B → human approval → submission confirmation with ARN.
"""

from .step import Step


GST_FILING_FLOW: list[Step] = [
    Step(
        id="gst_fetch_sales",
        title="Fetch sales data for the period",
        duration_range=(3, 7),
        narration_prompt=(
            "Pulling sales invoices and CDN entries from the user's accounting "
            "system for the filing period. Narrate in 2-3 sentences."
        ),
    ),
    Step(
        id="gst_compute_liability",
        title="Compute tax liability",
        duration_range=(4, 8),
        narration_prompt=(
            "Calculating output tax, ITC available and net GST liability. "
            "Narrate the calculation in 2-3 sentences."
        ),
    ),
    Step(
        id="gst_reconcile_2b",
        title="Reconcile against GSTR-2B",
        duration_range=(5, 10),
        narration_prompt=(
            "Matching purchase invoices to GSTR-2B from the GSTN portal "
            "to identify mismatches. Narrate in 2-3 sentences."
        ),
    ),
    Step(
        id="gst_generate_3b",
        title="Generate GSTR-3B return",
        duration_range=(4, 8),
        narration_prompt=(
            "Compiling the GSTR-3B with all sections filled in. "
            "Narrate generation in 2-3 sentences."
        ),
    ),
    Step(
        id="gst_human_review",
        title="Review and approve return",
        duration_range=(0, 0),
        narration_prompt=(
            "GSTR-3B is ready for the user's review before submission. "
            "Briefly state what is awaiting approval."
        ),
        requires_human=True,
    ),
    Step(
        id="gst_submit_arn",
        title="Submit return and receive ARN",
        duration_range=(5, 10),
        narration_prompt=(
            "Filing the GSTR-3B with the GSTN portal. Acknowledgment "
            "Reference Number is being generated. Narrate completion in 2-3 sentences."
        ),
        final_output_template="ARN: AA{rand:010}",
    ),
]
