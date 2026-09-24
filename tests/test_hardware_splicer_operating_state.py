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


def test_frontend_closure_is_merged_and_reopen_on_trigger():
    state = load_state()
    priorities = {row["lane"]: row for row in state["priority_stack"]}
    assert priorities["competitive_frontend_closure"]["state"] == "CLOSED_REOPEN_ON_TRIGGER"
    assert priorities["competitive_frontend_closure"]["merged_pr"] == "Spectating101/hardware-splicer#104"
    frontend = state["surface_state"]["competitive_frontend"]
    assert frontend["state"] == "CLOSED_REOPEN_ON_TRIGGER"
    assert set(frontend["reopen_requires_any"]) == {
        "rendered usability deficiency",
        "user or evaluator workflow failure",
        "source-bound native competitor gap",
    }


def test_product_factory_category_is_bounded_not_claimed_as_proven():
    state = load_state()
    priorities = {row["lane"]: row for row in state["priority_stack"]}
    assert priorities["product_factory_empirical_differentiation"]["state"] == "ACTIVE_BOUNDED_EXPERIMENT"
    surface = state["surface_state"]["product_factory_transformation"]
    assert surface["state"] == "ACTIVE_BOUNDED_EXPERIMENT"

    posture = state["competitive_feedback"]["category_posture"]
    assert posture["specialist_tools_may_execute_under_hs"] is True
    assert posture["rebuild_every_external_eda_primitive"] is False
    assert posture["general_transformation_capability_proven"] is False
    assert posture["commercial_moat_proven"] is False


def test_product_factory_paper_economics_cannot_open_physical_or_moat_claims():
    guards = load_state()["authority_guards"]
    assert guards["paper_economics_can_authorize_build"] is False
    assert guards["competitor_gap_can_prove_category_moat"] is False
