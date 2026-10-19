"""Independent functional requirement and real CAD protocol contract tests."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from hardware_splicer.functional_architecture import derive_functional_architecture
from hardware_splicer.functional_architecture_oracle import verify_functional_architecture
from hardware_splicer.solidcraft_workspace_bridge import build_solidcraft_workspace_handoff
from hardware_splicer.engineering_planner import plan_engineering_project

ROOT=Path(__file__).resolve().parents[1]
HOLDOUT=ROOT/"examples/source_bound_holdout/unfamiliar_tabletop_label_feeder_20261020.json"
CAD_DEMO=ROOT/"examples/solidcraft/declared_conceptual_envelope.json"


@pytest.fixture(scope="module")
def stationary():
    return json.loads(HOLDOUT.read_text())["intake"]


@pytest.fixture(scope="module")
def declared_envelope():
    return json.loads(CAD_DEMO.read_text())["intake"]


def test_stationary_machine_no_longer_released_as_rover(stationary):
    case=json.loads(HOLDOUT.read_text())
    p=plan_engineering_project(stationary,engineering_sources=case["engineering_sources"],
                               declared_conflicts=case["declared_conflicts"],skip_vision=True)
    assert p["native_robot_genre"]=="rover"  # Existing legacy proposal still visible for audit
    assert p["native_robot_topology_rejected"] is True
    assert p["archetype"]=="generic_mechatronics"
    assert p["engineering_readiness"]["status"]=="blocked"
    assert p["functional_architecture"]["functional_domain"]=="stationary_processing_cell"
    assert "robotics_project" not in p["scenario"]["compile_spec"]
    assert p["scenario"]["compile_spec"]["rejected_native_topology"]["physical_build_authorized"] is False


def test_function_decomposition_contains_requested_stationary_subsystems(stationary):
    plan=derive_functional_architecture(stationary)
    assert plan["functional_domain"]=="stationary_processing_cell"
    assert plan["functional_decomposition_supported"]
    assert {row["role"] for row in plan["functional_blocks"]} == {
        "item_identification","local_decision_and_logging","material_indexing",
        "independent_motion_inhibition","rated_power_and_protection",
    }
    assert len(plan["functional_edges"])==4
    assert verify_functional_architecture(stationary,plan)["passes_bounded_requirement_check"]
    assert not any(x["physical_interface_contract_verified"] for x in plan["functional_blocks"])


def test_explicit_mobile_not_confused_with_stationary():
    intake={"goal":"Movable survey platform","constraints":{"requires_mobile_platform":True}}
    p=derive_functional_architecture(intake)
    assert p["functional_domain"]=="mobile_robot_platform"
    assert verify_functional_architecture(intake,p)["passes_bounded_requirement_check"]


def test_explicit_leg_configuration_is_not_a_generic_rover():
    intake={"goal":"Four leg experiment","constraints":{"leg_count":4,"joints_per_leg":3}}
    p=derive_functional_architecture(intake)
    assert p["functional_domain"]=="legged_robot_platform"
    assert not p["physical_design_release_authorized"]


def test_unknown_domain_not_guessed_from_generic_goal():
    intake={"goal":"Create a better machine","constraints":{}}
    p=derive_functional_architecture(intake)
    assert p["functional_domain"]=="UNRESOLVED_MACHINE_DOMAIN"
    assert not p["functional_decomposition_supported"]


def test_contradictory_mobility_declared_is_blocked():
    intake={"goal":"Something both stationary and mobile","constraints":{"stationary_only":True,"requires_mobile_platform":True}}
    p=derive_functional_architecture(intake)
    assert p["domain_selection_status"]=="BLOCKED_CONTRADICTORY_REQUIREMENTS"
    assert not p["functional_decomposition_supported"]
    assert verify_functional_architecture(intake,p)["passes_bounded_requirement_check"]


@pytest.mark.parametrize("mutation",[
    lambda p:p.update({"functional_domain":"mobile_robot_platform"}),
    lambda p:p["functional_blocks"][0].update({"physical_interface_contract_verified":True}),
    lambda p:p["functional_edges"][0].update({"electrical_interface_verified":True}),
    lambda p:p.update({"physical_design_release_authorized":True}),
    lambda p:p["functional_blocks"].pop(),
])
def test_independent_oracle_catches_forged_or_missing_functional_contract(stationary,mutation):
    p=derive_functional_architecture(stationary)
    mutation(p)
    assert not verify_functional_architecture(stationary,p)["passes_bounded_requirement_check"]


def test_no_donor_dimensions_no_cad_script(stationary):
    p=derive_functional_architecture(stationary)
    handoff=build_solidcraft_workspace_handoff(stationary,p)
    assert handoff["script_ready"] is False
    assert handoff["command_script"] is None
    assert handoff["materialized_cad_model_exists"] is False
    assert "Missing explicitly declared" in handoff["blocker"]


def test_declared_concept_envelope_matches_native_solidcraft_json_protocol(declared_envelope):
    p=derive_functional_architecture(declared_envelope)
    handoff=build_solidcraft_workspace_handoff(declared_envelope,p)
    assert handoff["script_ready"]
    assert handoff["geometry_source"]=="EXPLICIT_USER_OR_TEST_FIXTURE_CONCEPT_ENVELOPE"
    assert handoff["expected_envelope_volume_mm3"]==240000
    commands=handoff["command_script"]["commands"]
    assert [r["command"] for r in commands]==[
        "sketch.create","sketch.rectangle.two_point","sketch.finish","solid.extrude"
    ]
    assert commands[1]["params"]["p1"]==[120,80]
    assert commands[3]["params"]["distance"]==25
    assert not handoff["mechanical_dimensions_measured"]
    assert not handoff["power_or_fabrication_authorized"]


@pytest.mark.parametrize("value",[0,-10,2500,"100",True,None,float("nan"),float("inf")])
def test_invalid_or_unbounded_geometry_does_not_generate_cad(declared_envelope,value):
    intake=deepcopy(declared_envelope)
    intake["concept_envelope_mm"]["width"]=value
    with pytest.raises(ValueError):
        build_solidcraft_workspace_handoff(intake,derive_functional_architecture(intake))


def test_cad_no_invented_dimensions_when_only_max_width_given():
    intake={"goal":"Stationary label machine","constraints":{"stationary_only":True,"maximum_width_mm":220}}
    p=derive_functional_architecture(intake)
    handoff=build_solidcraft_workspace_handoff(intake,p)
    assert not handoff["script_ready"]


def test_cad_rejects_domain_contradiction_even_when_dimensions_given(declared_envelope):
    intake=deepcopy(declared_envelope)
    intake["constraints"]["requires_mobile_platform"]=True
    plan=derive_functional_architecture(intake)
    assert not plan["functional_decomposition_supported"]
    assert not build_solidcraft_workspace_handoff(intake,plan)["script_ready"]


def test_stationary_pump_does_not_become_label_feeder():
    intake={"goal":"Design a stationary pump for controlled water circulation",
            "constraints":{"stationary_only":True}}
    p=derive_functional_architecture(intake)
    assert p["functional_domain"]=="stationary_fluid_handling_cell"
    roles={r["role"] for r in p["functional_blocks"]}
    assert "controlled_fluid_transfer" in roles
    assert "item_identification" not in roles
    assert "material_indexing" not in roles
    assert verify_functional_architecture(intake,p)["passes_bounded_requirement_check"]


def test_unclassified_stationary_machine_not_fitted_with_barcode_parts():
    intake={"goal":"Design a stationary laboratory apparatus",
            "constraints":{"stationary_only":True}}
    p=derive_functional_architecture(intake)
    assert p["functional_domain"]=="UNRESOLVED_STATIONARY_FUNCTION"
    assert not p["functional_decomposition_supported"]
    assert all(b["role"]!="item_identification" for b in p["functional_blocks"])
    assert verify_functional_architecture(intake,p)["passes_bounded_requirement_check"]


def test_sdk_mcp_solidcraft_workspace_returns_bounded_editable_command_script(declared_envelope):
    import asyncio
    from hardware_splicer import sdk,mcp_server
    scenario=json.loads(CAD_DEMO.read_text())
    result=sdk.prepare_solidcraft_workspace(scenario=scenario)
    assert result["cad_handoff"]["script_ready"]
    assert not result["fabrication_authorized"]
    assert result["cad_handoff"]["command_script"]["commands"][0]["command"]=="sketch.create"
    tools=asyncio.run(mcp_server.list_tools())
    assert any(x.name=="hs_prepare_solidcraft_workspace" for x in tools)
    result_mcp=asyncio.run(mcp_server.call_tool("hs_prepare_solidcraft_workspace",{"scenario":scenario}))
    data=json.loads(result_mcp[0].text)
    assert data["cad_handoff"]["script_ready"]
    assert data["cad_interactions_via_solidcraft_mcp_possible"]
    assert not data["physical_assembly_proven"]


def test_sdk_unmeasured_marketplace_holdout_cannot_output_invented_cad(stationary):
    from hardware_splicer import sdk
    scenario=json.loads(HOLDOUT.read_text())
    result=sdk.prepare_solidcraft_workspace(scenario=scenario)
    assert result["functional_architecture"]["functional_domain"]=="stationary_processing_cell"
    assert result["cad_handoff"]["script_ready"] is False
    assert result["cad_handoff"]["command_script"] is None
    assert result["native_robot_topology_accepted"] is False


def test_unspecified_machine_does_not_get_positive_candidate_acceptance():
    from hardware_splicer import sdk
    scenario={
        "scenario_id":"unknown_laboratory_machine",
        "mode":"synthesize",
        "intake":{"goal":"Make a laboratory device","constraints":{"stationary_only":True}},
        "engineering_sources":[],
    }
    r=sdk.plan_source_bound_design(scenario=scenario)
    assert r["candidate"]["functional_architecture"]["functional_domain"]=="UNRESOLVED_STATIONARY_FUNCTION"
    assert r["independent_evidence_audit"]["passes_independent_evidence_integrity"]
    assert not r["conditional_architecture_accepted"]
    assert not r["physical_build_authorized"]
