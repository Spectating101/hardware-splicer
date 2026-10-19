"""Source-traceable *conditional* engineering proposals.

Reuses HS's native source graph/topology/change-impact planner, then binds
specific decision claims to immutable claim digests and independently auditable
source metadata. The result is a hypothesis, never a fabricated working robot,
repair, motor rating, measured pinout or fabrication authorization.

A fixture marking source authority=measured does not make the provenance
externally authenticated. In particular evidence:// records are not instrument
logs and cannot authorize physical work.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .engineering_planner import plan_engineering_project

SCHEMA="hardware_splicer.source_bound_candidate_trial.v1"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def _claims(plan: Mapping[str,Any], keys: tuple[str,...]) -> list[dict[str,Any]]:
    """Select only original source statements with literal transparent matches."""
    result=[]
    for claim in plan["engineering_source_graph"]["claims"]:
        if claim["source_id"]=="declared-conflicts":
            continue
        text=str(claim["value"]).lower()
        if any(str(k).lower() in text for k in keys):
            result.append({
                "claim_id":claim["claim_id"],
                "source_id":claim["source_id"],
                "verbatim_claim":claim["value"],
                "original_claim_sha256":_digest(claim),
                "interpretation_ceiling":"SOURCE_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
            })
    return result


def _candidate_decisions(mode: str, intake: Mapping[str,Any], plan: Mapping[str,Any])->list[dict[str,Any]]:
    constraints=intake.get("constraints") or {}
    def decision(name,claim_words,proposed_action,required_evidence,*,required_values=None):
        refs=_claims(plan,tuple(claim_words))
        return {
            "decision_id":name,
            "source_claims":refs,
            "original_input_constraints":{k:constraints[k] for k in (required_values or ()) if k in constraints},
            "candidate_action":proposed_action,
            "support_type":"DECLARED_CLAIM_AND_REQUIREMENT" if refs else "REQUIREMENT_ONLY",
            "acceptance_status":"CONDITIONAL_NOT_PHYSICALLY_VALIDATED",
            "evidence_needed_to_execute":required_evidence,
            "safe_to_execute_now":False,
        }

    if mode=="reconstruct":
        return [
            decision("select_revision_boundary",("legacy mechanical","new mechanical","v1","v3","servo","brushless"),
                     "Produce one coherent candidate revision, never splice servo/PWM and brushless control generations without verifying model and revision.",
                     ["Fetch and pin manufacturer/repository revision-specific BOM, mechanical drawings, controller firmware and actuator driver contracts"]),
            decision("map_actuation_and_control",("Raspberry Pi","PWM","brushless","servo"),
                     "Retain 12 declared degrees of freedom as design requirement; actuator, driver and controller compatibility remain unassigned.",
                     ["Resolve revision-specific actuator IDs, rated voltage/current, controller pinout, rail separation and first-motion interlocks"],
                     required_values=("degrees_of_freedom","leg_count","joints_per_leg")),
        ]
    if mode=="repair":
        return [
            decision("isolate_failed_driver",("burn","driver","rating","thermal"),
                     "Exclude the reported burned driver from any powered reuse proposal; characterize the actual driver replacement and wiring separately.",
                     ["Record actual board/driver markings and damage, manufacturer package ratings, stalled motor current and an independently bounded power path"],
                     required_values=("first_motion_current_limit_a","battery_voltage_v")),
            decision("screen_drive_motor_pair",("matching resistance","one motor differs","identical motors","motor"),
                     "Treat all four proposed motors as unverified until individual identities and safe matching pair are measured; do not assume any particular two are compatible.",
                     ["Identify two actual motors and their individually measured winding, speed/load and current characteristics"],
                     required_values=("mismatched_motor_must_be_rejected_or_derated","maximum_speed_mps")),
        ]
    if mode=="evolve":
        return [
            decision("reassess_payload_stability",("mast","pitch excursion","tip","payload center"),
                     "Prefer investigating a lower or redistributed camera payload, but do not calculate a safe tipping angle without total center of mass, track width and acceleration.",
                     ["Measure revised mass distribution, rover wheelbase/track, physical center of mass, wheel slip and measured dynamic tilt"],
                     required_values=("payload_mass_g","current_payload_height_mm","static_tilt_margin_deg")),
            decision("separate_and_validate_logic_rail",("logic rail drops","reboots","startup"),
                     "Investigate acceleration/camera-startup rail droop and power-path isolation with baseline revision pinned; do not select regulator or claim a stable rail without logged transients.",
                     ["Acquire timestamp-aligned voltage/current logs, actual regulator ratings, ground topology and load-step response"],
                     required_values=("no_logic_rail_brownout","maximum_speed_mps")),
        ]
    if mode=="synthesize":
        stationary_required = constraints.get("stationary_only") is True
        if plan["robot_topology"].get("robot_genre") == "rover" and not stationary_required:
            return [
                decision("dimension_rover_envelope",(),
                         "Propose a two-driven-wheel reference topology with conditional inspection payload clearance; do not claim mechanical fit until actual geometry is verified.",
                         ["Produce measured motor/wheel/frame CAD dimensions and a collision envelope"],
                         required_values=("maximum_width_mm","threshold_height_mm","payload_g")),
                decision("derive_runtime_power_budget",(),
                         "Energy requirement is E_Wh >= runtime_h * average_input_power_W / battery_to_load_efficiency; actual power and efficiency are unknown.",
                         ["Measure average/peak current for drive, computing, sensors and camera; confirm battery chemistry and cutoff limits"],
                         required_values=("runtime_min","battery_voltage_v","maximum_noise_dba")),
            ]
        return [
            decision("decompose_requested_product_into_subsystems",
                     ("scanner","motor","usb","motherboard","board","printer"),
                     "Propose functional blocks for the stated product, but do not substitute a generic rover or infer a compatible electrical design from source names.",
                     ["Confirm actual sensor, control, motion, mechanical and power contracts for every proposed subsystem"]),
            decision("reject_unverified_source_hardware_as_owned_inventory",
                     ("faulty","parts","cut","unverified","interface"),
                     "Keep seller-listed devices as discovery hypotheses; no usable donor component or safe-to-connect interface is known.",
                     ["Identify an actual acquired specimen, record its model/revision, document original functionality, then characterize relevant electrical/mechanical interfaces"]),
        ]
    return []


def build_source_bound_candidate(scenario: Mapping[str,Any], *, plan: Mapping[str,Any] | None=None) ->dict[str,Any]:
    mode=str(scenario.get("mode") or "")
    if mode not in {"reconstruct","repair","evolve","synthesize"}:
        raise ValueError("unknown case mode")
    intake=scenario.get("intake")
    if not isinstance(intake,Mapping):
        raise ValueError("intake must be object")
    source_rows=scenario.get("engineering_sources") or []
    conflicts=scenario.get("declared_conflicts") or []
    if plan is None:
        plan=plan_engineering_project(
            intake,
            engineering_sources=source_rows,
            declared_conflicts=conflicts,
            skip_vision=True,
        )
    graph=plan["engineering_source_graph"]
    source_by_id={s["source_id"]:s for s in graph["sources"]}
    declared_source_checks=[]
    for raw in source_rows:
        sid=raw["source_id"]
        original_version=raw.get("revision") or raw.get("version") or raw.get("commit_sha")
        normalized=source_by_id.get(sid)
        same=bool(
            normalized is not None
            and normalized.get("uri")==raw.get("uri")
            and normalized.get("revision")==original_version
        )
        uri=str(raw.get("uri") or "")
        if uri.startswith("evidence://"):
            authority="UNMOUNTED_FIXTURE_REFERENCE_NOT_PHYSICAL_PROOF"
        elif uri.startswith(("https://","http://")):
            authority="DECLARED_PUBLIC_LINK_NOT_FETCHED_BY_THIS_TRIAL"
        else:
            authority="UNRESOLVED_SOURCE_PROVENANCE"
        declared_source_checks.append({
            "source_id":sid,
            "expected_source_sha256":_digest(raw),
            "expected_uri":uri,
            "expected_version":original_version,
            "retained_source_record":same,
            "source_record_sha256":_digest(normalized) if normalized else None,
            "source_claim_ids":sorted(
                c["claim_id"] for c in graph["claims"] if c["source_id"]==sid
            ),
            "external_attestation_status":authority,
            "source_claims_physical_authority":False,
        })
    topology=plan["robot_topology"]
    ids=plan["engineering_identity_map"]
    constraints=intake.get("constraints") or {}
    native_genre=topology.get("robot_genre")
    stationary_conflict=constraints.get("stationary_only") is True and native_genre in {
        "rover","quadruped","tracked_vehicle","wheeled_robot"
    }
    source_conflicts=[
        {
            "conflict_id":c["conflict_id"],
            "blocking":c["blocking"],
            "disposition":c["disposition"],
            "claim_ids":list(c["claim_ids"]),
            "source_evidence_selected":False,
        }
        for c in graph["conflicts"]
    ]
    decisions=_candidate_decisions(mode,intake,plan)
    missing=[
        "No externally authenticated measurements or direct donor component observations are present in this experiment",
        "A native robot topology is a proposed architecture, not a mechanically built or functionally verified device",
    ]
    if source_conflicts:
        missing.append("At least one declared engineering-source conflict remains blocking and must not be silently selected")
    if stationary_conflict:
        missing.append(
            "NATIVE_TOPOLOGY_REJECTED: source planner invented a mobile architecture despite stationary-only requirement"
        )
    if mode=="repair":
        missing.append("Damaged donor identities and measured-compatible motor pair remain unverified")
    if mode=="evolve":
        missing.append("Baseline release scope does not transfer to changed payload geometry or power network")
    candidate={
        "schema_version":SCHEMA,
        "scenario_id":scenario["scenario_id"],
        "source_scenario_digest":_digest(scenario),
        "mode":mode,
        "goal":str(intake.get("goal") or ""),
        "candidate_class":"CONDITIONAL_EVIDENCE_BOUND_DESIGN",
        "proposal_is_physical_build":False,
        "archetype":"UNRESOLVED_STATIONARY_EQUIPMENT" if stationary_conflict else native_genre,
        "raw_native_planner_archetype":native_genre,
        "architecture_consistency":{
            "stationary_only_required":constraints.get("stationary_only") is True,
            "mobile_topology_mismatch_detected":stationary_conflict,
            "native_topology_usable":not stationary_conflict,
            "engineered_architecture_verified":False,
        },
        "model_generated_or_inferred_topology":True,
        "topology_reference_id":topology.get("topology_id"),
        "topology_joint_count":len(topology.get("joints") or []),
        "topology_actuator_count":len(topology.get("actuators") or []),
        "functional_architecture":plan.get("functional_architecture"),
        "functional_architecture_conditional_only":True,
        "named_component_ids":sorted(ids.get("component_aliases") or {}),
        "source_integrity":declared_source_checks,
        "engineering_source_claim_count":len(graph["claims"]),
        "source_conflicts":source_conflicts,
        "decisions":decisions,
        "baseline_revision":plan.get("baseline_revision"),
        "change_impact_target_ids":list(plan.get("affected_subsystems") or []),
        "mandatory_open_gates":missing,
        "source_trace_complete":all(x["retained_source_record"] for x in declared_source_checks),
        "unresolved_blocking_source_conflicts":sum(bool(x["blocking"]) for x in source_conflicts),
        "engineering_readiness_from_native_planner":plan["engineering_readiness"]["status"],
        "physical_specimen_evidence_authenticated":False,
        "verified_usable_donor_count":0,
        "repair_completed":False,
        "new_product_physically_functional":False,
        "physical_fabrication_or_power_authorized":False,
        "conditional_design_recommendation_only":True,
        "release_decision":"BLOCKED_PENDING_INDEPENDENT_ELECTRICAL_MECHANICAL_AND_FUNCTIONAL_PROOF",
    }
    return candidate
