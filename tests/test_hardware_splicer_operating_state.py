from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "docs" / "HARDWARE_SPLICER_OPERATING_STATE.json"


def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))


def test_hs_remains_flagship_and_physical_proof_is_p0():
    state = load_state()
    assert state["project"] == "hardware-splicer"
    assert state["portfolio_role"] == "flagship_selectively_active"
    priorities = {row["lane"]: row for row in state["priority_stack"]}
    assert priorities["physical_proof"]["priority"] == "P0"
    assert priorities["physical_proof"]["state"] == "ACTIVE"


def test_competition_can_improve_hs_without_automatic_core_or_authority_change():
    feedback = load_state()["competitive_feedback"]
    assert feedback["policy"] == "competition_is_input_to_improvement_not_automatic_scope_reduction"
    assert feedback["automatic_core_change_authorized"] is False
    assert feedback["automatic_physical_authority_authorized"] is False
    assert feedback["response_classes"] == {
        "presentation": "IMPROVE_HS_SHELL",
        "workflow": "IMPROVE_HS_WORKFLOW_IF_CURRENT_SEMANTICS_SUPPORT_IT",
        "integration": "INTEGRATE_NOT_REBUILD",
        "truth_model": "REQUIRE_EXACT_HS_DEFECT_BEFORE_CORE_INVESTIGATION",
    }


def test_route_reallocation_does_not_reduce_hs_capability():
    posture = load_state()["route_posture"]
    assert posture["portfolio_reallocation_allowed"] is True
    assert posture["route_reallocation_reduces_hs_capability"] is False
    assert posture["reclaimable_when_future_fit_changes"] is True


def test_generic_feature_expansion_is_off_but_native_improvement_is_allowed():
    surfaces = load_state()["surface_state"]
    assert surfaces["generic_feature_expansion"]["state"] == "OFF_BY_DEFAULT"
    assert surfaces["competitor_driven_improvement"]["state"] == "ALLOWED_AND_EXPECTED"
    assert surfaces["route_specific_integrations"]["state"] == "ALLOWED"


def test_program_scope_is_not_changed_by_competitor_count_or_temporary_pessimism():
    repricing = load_state()["repricing_events"]
    assert repricing["competitor_count_alone_is_negative_evidence"] is False
    assert repricing["temporary_pessimism_changes_program_scope"] is False


def test_physical_authority_stays_fail_closed():
    guards = load_state()["authority_guards"]
    assert all(
        guards[key] is False
        for key in (
            "competitor_signal_can_authorize_fabrication",
            "provider_quote_can_authorize_fabrication",
            "software_check_can_authorize_power_on",
            "model_result_can_authorize_release",
        )
    )
    assert guards["physical_evidence_requires_explicit_real_state"] is True
