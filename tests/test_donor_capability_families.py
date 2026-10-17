from __future__ import annotations

from hardware_splicer.donor_capability_families import (
    list_capability_families,
    match_capability_family,
    project_family_capability,
)
from hardware_splicer.salvage_resource_graph import project_salvage_resource_graph


def test_dc_motor_family_declares_investigation_planner_and_refusal_policy():
    family = match_capability_family("dc_motor")
    assert family["family_id"] == "salvage.dc_motor"
    assert "winding continuity/resistance" in family["minimum_evidence"]
    assert family["planner_interface"]["kind"] == "rotary_actuator"
    assert family["planner_interface"]["requires_driver"] == "h_bridge_or_equivalent_for_bidirectional_control"
    assert any(row["request_id"] == "motor-terminal-resistance" for row in family["investigation_requests"])
    assert "direct GPIO drive" in family["refusal_conditions"]


def test_family_policy_does_not_promote_partial_donor_evidence():
    projected = project_family_capability(
        role="brushed_motor",
        evidence_grade="document",
        contract_state="partial",
        unresolved_facts=["signals.MOTOR.voltage_max_v", "geometry.shaft"],
    )
    assert projected["family_id"] == "salvage.dc_motor"
    assert projected["qualification"]["state"] == "bounded_partial"
    assert projected["qualification"]["architecture_usable"] is True
    assert projected["qualification"]["ready_for_execution"] is False
    assert projected["recommended_investigation"]
    assert projected["truth_contract"]["family_policy_is_evidence"] is False
    assert projected["truth_contract"]["role_match_establishes_physical_capability"] is False


def test_only_verified_person_measurement_projection_can_be_ready():
    verified = project_family_capability(
        role="momentary_button",
        evidence_grade="person_measurement",
        contract_state="verified",
        unresolved_facts=[],
    )
    assert verified["family_id"] == "salvage.passive_switch"
    assert verified["qualification"]["state"] == "verified"
    assert verified["qualification"]["ready_for_execution"] is True
    assert verified["recommended_investigation"] == []

    documented = project_family_capability(
        role="momentary_button",
        evidence_grade="document",
        contract_state="verified",
        unresolved_facts=[],
    )
    assert documented["qualification"]["state"] == "bounded_partial"
    assert documented["qualification"]["ready_for_execution"] is False


def test_role_matching_is_conservative_and_does_not_turn_driver_into_motor():
    assert match_capability_family("motor_driver") is None
    assert match_capability_family("H bridge motor driver") is None
    assert match_capability_family("DC gearmotor")["family_id"] == "salvage.dc_motor"
    assert match_capability_family("cooling_fan")["family_id"] == "salvage.fan"
    assert match_capability_family("limit-switch")["family_id"] == "salvage.passive_switch"


def test_resource_graph_exposes_family_policy_without_changing_raw_capability_id():
    graph = project_salvage_resource_graph(
        project_id="family-test",
        donors=[
            {
                "donor_id": "donor:printer:motor",
                "label": "Printer carriage motor",
                "contract_state": "partial",
                "capabilities": [{"role": "dc_motor", "grade": "document"}],
                "missing_facts": ["signals.MOTOR.voltage_max_v"],
            }
        ],
    )
    donor = graph["resources"][0]
    assert donor["capabilities"][0]["capability_id"] == "donor.role:dc_motor"
    assert donor["capabilities"][0]["family_id"] == "salvage.dc_motor"
    assert donor["capabilities"][0]["family_qualification"]["ready_for_execution"] is False
    assert donor["capability_families"][0]["family_id"] == "salvage.dc_motor"
    assert donor["capability_families"][0]["recommended_investigation"]
    assert graph["truth_contract"]["capability_family_policy_is_evidence"] is False


def test_initial_family_set_covers_first_salvage_priority_lanes_without_catalog_explosion():
    ids = {row["family_id"] for row in list_capability_families()}
    assert ids == {
        "salvage.passive_switch",
        "salvage.led_indicator",
        "salvage.buzzer",
        "salvage.dc_motor",
        "salvage.fan",
        "salvage.stepper_motor",
    }
