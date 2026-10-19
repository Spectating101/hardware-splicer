"""Bounded functional system decomposition, independent of robot archetype.

A mobile robot is not the fallback for every mechanical project. Derive
the necessary *functions* from declared constraints/intent first, then
attach hypothetical donor capabilities without inventing electrical
interface facts. This is not unrestricted natural-language understanding.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import hashlib
import json

SCHEMA="hardware_splicer.functional_architecture.v1"


def _stable_id(prefix:str, value:str)->str:
    return prefix+"_"+hashlib.sha256(value.encode()).hexdigest()[:12]


def _tokens(intake:Mapping[str,Any])->str:
    goal=str(intake.get("goal") or "").lower()
    parts=" ".join(str(p.get("name") or "") for p in intake.get("available_parts",[]) if isinstance(p,Mapping)).lower()
    return goal+" "+parts


def derive_functional_architecture(intake:Mapping[str,Any])->dict[str,Any]:
    """Produce candidate functional blocks, not a physical topology."""
    if not isinstance(intake,Mapping):
        raise ValueError("intake must be a mapping")
    constraints=intake.get("constraints") or {}
    if not isinstance(constraints,Mapping):
        raise ValueError("constraints must be a mapping")
    goal=str(intake.get("goal") or "").strip()
    if not goal:
        raise ValueError("goal is required")
    stationary=constraints.get("stationary_only") is True
    mobile=constraints.get("requires_mobile_platform") is True
    legged=(constraints.get("leg_count")==4 and constraints.get("joints_per_leg")==3)
    text=_tokens(intake)
    movement_terms=("rover","robot chassis","four-wheel","four wheel","driving")
    speed_req=(
        any(k in constraints for k in ("maximum_speed_mps","maximum_turn_rate_rps"))
        and any(token in text for token in movement_terms)
    )
    barcode_job=any(x in goal.lower() for x in ("barcode", "bar code", "label indexing", "label feeder"))
    indexing_job=any(x in goal.lower() for x in ("index", "feed", "conveyor", "transport"))
    fluid_job=any(x in goal.lower() for x in ("pump", "fluid flow", "circulation", "liquid transfer"))
    conflict=stationary and mobile
    if conflict:
        domain="UNRESOLVED_CONTRADICTORY_MOBILITY_REQUIREMENTS"
        status="BLOCKED_CONTRADICTORY_REQUIREMENTS"
    elif stationary and barcode_job and indexing_job:
        domain="stationary_processing_cell"
        status="CONDITIONAL_FUNCTIONAL_DECOMPOSITION"
    elif stationary and fluid_job:
        domain="stationary_fluid_handling_cell"
        status="CONDITIONAL_FUNCTIONAL_DECOMPOSITION"
    elif stationary:
        domain="UNRESOLVED_STATIONARY_FUNCTION"
        status="NEEDS_FUNCTIONAL_REQUIREMENT_CLASSIFICATION"
    elif legged:
        domain="legged_robot_platform"
        status="CONDITIONAL_FUNCTIONAL_DECOMPOSITION"
    elif mobile or speed_req:
        domain="mobile_robot_platform"
        status="CONDITIONAL_FUNCTIONAL_DECOMPOSITION"
    else:
        domain="UNRESOLVED_MACHINE_DOMAIN"
        status="NEEDS_FUNCTIONAL_REQUIREMENT_CLASSIFICATION"

    blocks=[]
    edges=[]
    def add(role:str, required_for:str, evidence:list[str]):
        bid=_stable_id("function",role)
        blocks.append({
            "functional_id":bid,
            "role":role,
            "declared_requirement_trace":required_for,
            "evidence_required_to_allocate_hardware":evidence,
            "source_component_assignment_verified":False,
            "physical_interface_contract_verified":False,
            "provisional_only":True,
        })
        return bid

    if domain=="stationary_processing_cell":
        read=add("item_identification","goal: stationary barcode/label processing",
                 ["sensor data protocol, actual original-function reading and scanner identity"])
        decide=add("local_decision_and_logging","goal: indexing and logging",
                   ["host OS and peripheral compatibility; genuine controller run"])
        index=add("material_indexing","goal: move label/material in controlled increments",
                  ["verified motor type, travel and force, limits, driver and mechanism"])
        safety=add("independent_motion_inhibition","constraints: independently stoppable machine",
                   ["independent electrical safety-rated stop/interlock and fault behavior"])
        power=add("rated_power_and_protection","requirement: verified supply and protection",
                  ["rated supply, current, isolation and inductive protection"])
        edges=[
            {"from":read,"to":decide,"interaction":"digital observation","electrical_interface_verified":False},
            {"from":decide,"to":index,"interaction":"motion request","electrical_interface_verified":False},
            {"from":safety,"to":index,"interaction":"independent inhibit","electrical_interface_verified":False},
            {"from":power,"to":index,"interaction":"protected energy","electrical_interface_verified":False},
        ]
    elif domain=="stationary_fluid_handling_cell":
        fluid=add("controlled_fluid_transfer","goal: stationary pump/flow system",
                  ["actual fluid, flow, pressure, leakage and pump specifications"])
        monitor=add("flow_and_pressure_feedback","goal: bounded fluid transfer",
                    ["sensor calibration, actual limits, tubing/pump material compatibility"])
        safety=add("independent_flow_inhibition","requirement: stop on unsafe flow or loss of containment",
                   ["independent pump power interruption, leak containment and pressure relief as applicable"])
        edges=[
            {"from":monitor,"to":fluid,"interaction":"flow control feedback","electrical_interface_verified":False},
            {"from":safety,"to":fluid,"interaction":"independent pump inhibit","electrical_interface_verified":False},
        ]
    elif domain in {"legged_robot_platform","mobile_robot_platform"}:
        locomotion=add("controlled_locomotion","constraints: platform movement",
                       ["drive actuator type, mechanics, power, feedback and current limits"])
        supervise=add("feedback_and_motion_control","goal: controlled travel",
                      ["sensor I/O, control loop and actual feedback observation"])
        safety=add("independent_motion_inhibition","constraints: emergency stop",
                   ["separately rated stop and power interruption"])
        edges=[
            {"from":supervise,"to":locomotion,"interaction":"motion request","electrical_interface_verified":False},
            {"from":safety,"to":locomotion,"interaction":"independent inhibit","electrical_interface_verified":False},
        ]
    else:
        add("unresolved_primary_transformation","goal: "+goal[:150],
            ["define the essential input-to-output transformation and product class"])

    return {
        "schema_version":SCHEMA,
        "functional_domain":domain,
        "domain_selection_status":status,
        "selection_basis":{
            "stationary_only":stationary,
            "requires_mobile_platform":mobile,
            "four_leg_three_joint_requirement":legged,
            "explicit_motion_context":speed_req,
            "input_goal":goal,
        },
        "functional_blocks":blocks,
        "functional_edges":edges,
        "architecture_is_a_robot":domain in {"legged_robot_platform","mobile_robot_platform"},
        "functional_decomposition_supported":status=="CONDITIONAL_FUNCTIONAL_DECOMPOSITION",
        "source_couplings_verified":False,
        "candidate_parts_observed":False,
        "physical_connectivity_proven":False,
        "mechanical_geometry_proven":False,
        "physical_design_release_authorized":False,
    }
