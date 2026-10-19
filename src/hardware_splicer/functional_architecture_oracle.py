"""Independent requirements-to-function contract checks.

These tests derive hard constraints from source input rather than trusting
either the planner's native genre or the functional plan's self-reports.
They verify semantics for a bounded set of declared requirement types only.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA="hardware_splicer.functional_architecture_oracle.v1"


def verify_functional_architecture(intake:Mapping[str,Any], proposal:Mapping[str,Any])->dict[str,Any]:
    issues=[]
    c=intake.get("constraints") or {}
    stationary=c.get("stationary_only") is True
    mobile=c.get("requires_mobile_platform") is True
    domain=proposal.get("functional_domain")
    contradictory=stationary and mobile
    goal=str(intake.get("goal") or "").lower()
    barcode_needed=any(x in goal for x in ("barcode","bar code","label indexing","label feeder"))
    indexing_needed=any(x in goal for x in ("index","feed","conveyor","transport"))
    fluid_needed=any(x in goal for x in ("pump","fluid flow","circulation","liquid transfer"))
    if contradictory:
        if domain!="UNRESOLVED_CONTRADICTORY_MOBILITY_REQUIREMENTS":
            issues.append("contradictory_mobility_hidden")
        if proposal.get("functional_decomposition_supported") is not False:
            issues.append("contradiction_marked_supported")
    elif stationary:
        expected_domain=(
            "stationary_processing_cell" if barcode_needed and indexing_needed
            else "stationary_fluid_handling_cell" if fluid_needed
            else "UNRESOLVED_STATIONARY_FUNCTION"
        )
        if domain!=expected_domain:
            issues.append("stationary_machine_misclassified")
    elif mobile:
        if domain not in {"mobile_robot_platform","legged_robot_platform"}:
            issues.append("mobile_platform_misclassified")
    if proposal.get("selection_basis",{}).get("stationary_only") is not stationary:
        issues.append("stationary_requirement_not_traceable")
    if proposal.get("selection_basis",{}).get("requires_mobile_platform") is not mobile:
        issues.append("mobility_requirement_not_traceable")
    if proposal.get("selection_basis",{}).get("input_goal")!=intake.get("goal"):
        issues.append("goal_origin_not_traceable")
    blocks=proposal.get("functional_blocks")
    if not isinstance(blocks,list) or not blocks:
        issues.append("missing_function_decomposition")
        blocks=[]
    ids=[b.get("functional_id") for b in blocks if isinstance(b,Mapping)]
    roles={b.get("role") for b in blocks if isinstance(b,Mapping)}
    if len(ids)!=len(set(ids)):
        issues.append("duplicated_function_identity")
    if domain=="stationary_processing_cell" and not contradictory:
        required={"item_identification","local_decision_and_logging","material_indexing",
                  "independent_motion_inhibition","rated_power_and_protection"}
        if not required.issubset(roles):
            issues.append("missing_stationary_machine_function")
    if domain=="stationary_fluid_handling_cell":
        required_fluid={"controlled_fluid_transfer","flow_and_pressure_feedback",
                        "independent_flow_inhibition"}
        if not required_fluid.issubset(roles):
            issues.append("missing_fluid_system_function")
    for block in blocks:
        if not isinstance(block,Mapping):
            issues.append("malformed_function")
            continue
        if not block.get("evidence_required_to_allocate_hardware"):
            issues.append("ungated_hardware_allocation")
        if (block.get("source_component_assignment_verified") is not False
            or block.get("physical_interface_contract_verified") is not False):
            issues.append("unobserved_component_marked_compatible")
    for edge in proposal.get("functional_edges") or []:
        if edge.get("from") not in ids or edge.get("to") not in ids:
            issues.append("functional_edge_references_missing_block")
        if edge.get("electrical_interface_verified") is not False:
            issues.append("untested_wire_contract_promoted")
    for key in ("candidate_parts_observed","physical_connectivity_proven",
                "mechanical_geometry_proven","physical_design_release_authorized"):
        if proposal.get(key) is not False:
            issues.append("physical_evidence_promoted:"+key)
    if domain in {"stationary_processing_cell","stationary_fluid_handling_cell",
                  "mobile_robot_platform","legged_robot_platform"}:
        if proposal.get("functional_decomposition_supported") is not True:
            issues.append("known_domain_self_reported_unresolved")
    return {
        "schema_version":SCHEMA,
        "passes_bounded_requirement_check":not issues,
        "failures":sorted(set(issues)),
        "functional_blocks_checked":len(blocks),
        "physical_validity_demonstrated":False,
        "release_authorized":False,
    }
