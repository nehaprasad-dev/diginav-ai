"""Verify declarative flow definitions match Requirements 3.1, 3.2, 3.3."""

import pytest

from app.core.flows import (
    FLOWS,
    INCORPORATION_FLOW,
    GST_FILING_FLOW,
    SE_LICENSE_FLOW,
    Step,
)


class TestIncorporationFlow:
    """Req 3.1: at least 8 steps including specific RoC milestones."""

    def test_has_at_least_8_steps(self):
        assert len(INCORPORATION_FLOW) >= 8

    def test_includes_required_steps(self):
        ids = {s.id for s in INCORPORATION_FLOW}
        required = {
            "name_reserve",  # RUN
            "din_apply",
            "dsc_issue",
            "moa_aoa",
            "spice_b",
            "pan_tan",
            "cin_gen",
        }
        assert required.issubset(ids), f"missing steps: {required - ids}"

    def test_has_human_review_step(self):
        assert any(s.requires_human for s in INCORPORATION_FLOW)

    def test_final_step_has_output_template(self):
        assert INCORPORATION_FLOW[-1].final_output_template is not None
        assert "CIN" in INCORPORATION_FLOW[-1].final_output_template


class TestGSTFilingFlow:
    """Req 3.2: at least 6 steps with human approval and ARN output."""

    def test_has_at_least_6_steps(self):
        assert len(GST_FILING_FLOW) >= 6

    def test_has_human_approval_step(self):
        assert any(s.requires_human for s in GST_FILING_FLOW)

    def test_final_step_outputs_arn(self):
        assert GST_FILING_FLOW[-1].final_output_template is not None
        assert "ARN" in GST_FILING_FLOW[-1].final_output_template


class TestSELicenseFlow:
    """Req 3.3: at least 5 steps with human approval and license number."""

    def test_has_at_least_5_steps(self):
        assert len(SE_LICENSE_FLOW) >= 5

    def test_has_human_approval_step(self):
        assert any(s.requires_human for s in SE_LICENSE_FLOW)

    def test_final_step_outputs_license_number(self):
        assert SE_LICENSE_FLOW[-1].final_output_template is not None
        assert "License" in SE_LICENSE_FLOW[-1].final_output_template


class TestFlowsRegistry:
    """The FLOWS dict exposes all 3 flows by their canonical IDs."""

    def test_all_three_flows_registered(self):
        assert set(FLOWS.keys()) == {"incorporation", "gst_filing", "se_license"}

    @pytest.mark.parametrize("flow_id", ["incorporation", "gst_filing", "se_license"])
    def test_each_flow_is_a_list_of_steps(self, flow_id):
        flow = FLOWS[flow_id]
        assert isinstance(flow, list)
        assert all(isinstance(s, Step) for s in flow)

    @pytest.mark.parametrize("flow_id", ["incorporation", "gst_filing", "se_license"])
    def test_step_ids_unique_within_flow(self, flow_id):
        flow = FLOWS[flow_id]
        ids = [s.id for s in flow]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize("flow_id", ["incorporation", "gst_filing", "se_license"])
    def test_non_human_steps_have_3_to_15s_duration(self, flow_id):
        """Req 3.4: each non-human step takes between 3 and 15 seconds."""
        for step in FLOWS[flow_id]:
            if step.requires_human:
                continue
            lo, hi = step.duration_range
            assert 3 <= lo <= hi <= 15, (
                f"{flow_id}/{step.id} duration_range {step.duration_range} "
                "violates Req 3.4 (3-15s)"
            )

    @pytest.mark.parametrize("flow_id", ["incorporation", "gst_filing", "se_license"])
    def test_only_terminal_step_has_output_template(self, flow_id):
        """Output templates belong on the last step only."""
        flow = FLOWS[flow_id]
        for step in flow[:-1]:
            assert step.final_output_template is None, (
                f"non-terminal step {step.id} has final_output_template"
            )
