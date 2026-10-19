"""Autonomous software feasibility pass using the real bounded electrical planner.

Separates verified *software behavior under injected events* from unknown
motor, scanner, stop-circuit, power and mechanical interface evidence.
No operational GPIO outputs or physical donor claims.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .virtual_splice_reference_cell import run_virtual_reference_cases, audit_bounded_sequences
from .sdk import plan_motor_driver_circuit

SCHEMA="hardware_splicer.autonomous_splice_feasibility.v1"


def evaluate_splice_feasibility(research: Mapping[str,Any])->dict[str,Any]:
    # Support the reproducible, minimized archived source reports created
    # by the previous real investigation, as well as a live MCP result.
    if research.get("schema_version")=="hardware_splicer.autonomous_public_evidence_archive.v1":
        research={
            "schema_version":"hardware_splicer.autonomous_evidence_controller.v1",
            "physical_operations_executed":research.get("physical_operations_executed"),
            "repair":research.get("repair_analysis"),
            "splicing":research.get("splicing_analysis"),
            "proposed_engineering_revision":research.get("proposed_engineering_revision"),
        }
    if research.get("schema_version")!="hardware_splicer.autonomous_evidence_controller.v1":
        raise ValueError("unexpected prior source investigation schema")
    if research.get("physical_operations_executed") != 0:
        raise ValueError("controller only accepts public-source software-only observations")
    repair=research.get("repair") or {}
    splice=research.get("splicing") or {}
    revised=research.get("proposed_engineering_revision") or {}
    if repair.get("mission_success") is not False or splice.get("mission_success") is not False:
        raise ValueError("claimed completed hardware mission cannot enter paper feasibility evaluator")
    machine=revised.get("new_product_revision") or {}
    if machine.get("donor_measured_or_integrated") is not False or machine.get("complete_system_demonstrated") is not False:
        raise ValueError("physical integration claims cannot come from market source research")
    source_rows=splice.get("candidate_source_audit") or []
    by_id={r["candidate_id"]:r for r in source_rows}
    if len(by_id)!=len(source_rows):
        raise ValueError("duplicate component IDs")
    if "epson_paper_motion" not in by_id:
        raise ValueError("missing actual donor motion-source hypothesis")
    # Use existing HS motor planner with unknown real attributes.
    # DC motor is an explicitly speculative planning branch, NOT a claim
    # that the Epson mechanism really has such a motor (it could be stepper).
    conditional_intent={
        "goal":"Conditional low-voltage DC motion reference for Epson donor indexing; actual motor type unknown",
        "load_requirements":[{"name":"hypothetical Epsonic carriage motor (uncharacterized)","type":"dc_motor"}],
        "signal_requirements":[{"name":"controller output, no assumed logic level","type":"pwm"}],
        "supply_rails":[],
        "allowed_modules":["esp32-devkit","l298n"],
        "required_evidence":[],
    }
    motor=plan_motor_driver_circuit(conditional_intent)
    # A model-family spec or seller listing must never upgrade an unknown
    # motor to an electrically reviewable candidate.
    blockers=list(motor.get("missing_evidence") or [])
    if motor.get("result")!="blocked" or not blockers:
        raise ValueError("uncharacterized motion element falsely declared design-ready")
    virtual=run_virtual_reference_cases()
    audit=audit_bounded_sequences(max_depth=4)
    if not audit["passed"]:
        raise ValueError("software state audit violation")
    if not virtual["software_reference_logic_passed"]:
        raise ValueError("virtual inspection behavior failed; cannot declare software reference validated")
    # This is an *engineering* outcome: one software validation gate
    # closes, while component-level evidence gates stay open.
    resolved_software=[{
        "gate":"barcode-indexing reference controller response to synthetic events",
        "status":"SOFTWARE_BEHAVIOR_VALIDATED_WITH_SYNTHETIC_EVENTS",
        "cases_passed":virtual["passed"],"cases_total":virtual["total"],
        "physical_hardware_implication":"NONE",
    }]
    unresolved=[
        {"gate":"donor scanner original-function and exact cable/host interface",
         "status":"BLOCKED","why":"no physically tested barcode decoder and host interface"},
        {"gate":"motor identity and dynamics","status":"BLOCKED",
         "why":"Epson mechanism not inspected; drive type, stall/run current, travel and limit switching unknown"},
        {"gate":"power and motor driver","status":"BLOCKED","why":"structured HS motor-driver planner rejected absent electrical contracts",
         "motor_planner_missing_evidence":blockers},
        {"gate":"host computer and software/hardware IO","status":"BLOCKED",
         "why":"QNAP source is board-only with unknown power and software; use Linux host only for virtual logic"},
        {"gate":"independent safety stop","status":"BLOCKED",
         "why":"ordinary salvaged mouse button is not a safety-rated stop"},
        {"gate":"cross-donor physical/mechanical integration","status":"BLOCKED",
         "why":"no acquired donors, dimensions, wiring, physical tests or finished machine"},
    ]
    actions=[
        {"round":1,"selected_action":"evaluate_motion_driver_against_real_HS_electrical_truth",
         "tool":"hardware_splicer.sdk.plan_motor_driver_circuit",
         "outcome":"BLOCKED_WITH_EXPLICIT_MISSING_CONTRACTS","physical_claim_advanced":False},
        {"round":2,"selected_action":"run_virtual_reference_controller_fault_injection",
         "tool":"virtual_splice_reference_cell.run_virtual_reference_cases",
         "outcome":"SOFTWARE_BEHAVIOR_VALIDATED_WITH_SYNTHETIC_EVENTS","physical_claim_advanced":False},
        {"round":3,"selected_action":"reconcile_function_coverage_and_remaining_hardware_gates",
         "tool":"autonomous_splice_feasibility.evaluate_splice_feasibility",
         "outcome":"SOFTWARE_SUBGOAL_CLOSED; PHYSICAL_PRODUCT_NOT_VALIDATED",
         "physical_claim_advanced":False},
    ]
    return {
        "schema_version":SCHEMA,
        "mission":"novel_splice",
        "goal":splice.get("new_product"),
        "source_research_basis":research.get("schema_version"),
        "method":"finite autonomous planning and synthetic software checks without physical components",
        "steps":actions,
        "conditional_motor_driver_plan":{
            "topology_hypothesis":"DC motor driver path ONLY if future evidence establishes a DC motor; stepper path otherwise requires separate design",
            "planner_result":motor["result"],
            "missing_evidence":blockers,
            "constraints":[{"id":x["constraint_id"],"status":x["status"]} for x in motor.get("constraints",[])],
            "physical_driver_selected":False,
            "motor_type_measured":False,
        },
        "virtual_control_software":virtual,
        "bounded_software_state_audit":audit,
        "software_gates_closed":resolved_software,
        "hardware_gates_open":unresolved,
        "software_validation_count":len(resolved_software),
        "physical_gate_count_open":len(unresolved),
        "selected_noncritical_compute_path":"existing authorized Linux host for software-only simulation; QNAP bare board excluded from critical path",
        "automatically_identified_architecture_changes":[
            "Do not assign GPIO or specify motor driver before actual donor motor type/current/protection evidence",
            "Separate software stop-state behavior from missing independent safety-rated hardware stop",
            "Retain QNAP motherboard as noncritical candidate, not prerequisite for software testing",
            "Keep scanner decoding and genuine barcode I/O external to synthetic software test",
        ],
        "virtual_software_behaves_as_expected":True,
        "physical_barcode_reader_verified":False,
        "actual_motor_actuated":False,
        "physical_safety_system_verified":False,
        "novel_product_functionally_proven":False,
        "repair_original_function_proven":False,
        "physical_actions_authorized":False,
        "next_step":"instrumented donor intake under independent physical safety controls OR additional bounded documentation search; not a manual user check request",
        "stop_reason":"Remaining mission closure gates require physical component evidence not available in this machine/session",
    }
