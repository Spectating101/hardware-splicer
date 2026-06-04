"""Canonical backend orchestration for hardware repair/reuse/build planning."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from src.engines.circuit_board_graph import analyze_circuit_design, analyze_circuit_session
from src.intelligence.active_evidence_closure import enrich_payload_with_active_evidence_closure_plan
from src.intelligence.arbitrary_board_workflow import enrich_payload_with_arbitrary_board_workflow
from src.intelligence.bench_topology_capture import enrich_payload_with_bench_topology_capture
from src.intelligence.diy_project_engineer import enrich_payload_with_diy_project_engineering
from src.intelligence.multiview_board_evidence import enrich_payload_with_multiview_board_evidence
from src.intelligence.resource_strategy import ResourceStrategyPlanner
from src.intelligence.repair_authority import enrich_payload_with_repair_authority
from src.intelligence.salvage_splice_planner import SalvageSplicePlanner
from src.intelligence.topology_evidence import enrich_payload_with_topology_evidence
from src.intelligence.vision_board_evidence import enrich_payload_with_board_evidence
from src.intelligence.visual_topology_hypothesis import enrich_payload_with_visual_topology_hypothesis


SCHEMA_VERSION = "hardware_plan.v1"

PRODUCTION_REQUIRED_MEASUREMENT_CATEGORIES = {"resistance", "continuity", "voltage", "current", "thermal"}

PRODUCTION_UNSUPPORTED_HAZARD_IDS = {
    "battery_pack",
    "damaged_battery_pack",
    "damaged_lithium_pack",
    "mains_input",
    "mains_voltage",
    "high_voltage",
    "hv_capacitor",
    "crt_high_voltage",
    "microwave_high_voltage",
    "laser_radiation",
}

PRODUCTION_UNSUPPORTED_CAPABILITIES = {
    "battery",
    "battery_pack",
    "mains",
    "mains_voltage",
    "high_voltage",
    "hv",
    "laser",
}

SPECIALIST_AUTHORITY_ACCEPTED_STATUSES = {"certified_release", "authorized", "authority_ready"}

SPECIALIST_AUTHORITY_REQUIRED_EVIDENCE = {
    "battery_pack_lithium": [
        ("chemistry_verified", ("chemistry_verified", "battery_chemistry_verified"), "Verify battery chemistry and cell type."),
        ("cell_count_verified", ("cell_count_verified", "series_cell_count_verified"), "Verify cell count and pack topology."),
        ("bms_protection_verified", ("bms_protection_verified", "protection_circuit_verified"), "Verify BMS/protection behavior."),
        ("cell_balance_result", ("cell_balance_result", "balance_result"), "Record cell balance result as passing."),
        ("charge_discharge_result", ("charge_discharge_result", "charge_test_result"), "Record charge/discharge result as passing."),
        ("thermal_containment_verified", ("thermal_containment_verified", "containment_result"), "Verify thermal containment."),
        ("enclosure_verified", ("enclosure_verified", "enclosure_result"), "Verify battery enclosure and strain relief."),
    ],
    "mains_high_voltage": [
        ("isolation_result", ("isolation_result", "isolation_test_result"), "Record isolation test result as passing."),
        ("discharge_result", ("discharge_result", "capacitor_discharge_result"), "Record stored-energy discharge result as passing."),
        ("earth_bond_result", ("earth_bond_result", "protective_earth_result"), "Record earth-bond result as passing."),
        ("leakage_current_result", ("leakage_current_result", "leakage_result"), "Record leakage-current result as passing."),
        ("fuse_protection_verified", ("fuse_protection_verified", "overcurrent_protection_verified"), "Verify fuse/protection behavior."),
        ("creepage_clearance_verified", ("creepage_clearance_verified", "clearance_verified"), "Verify creepage and clearance."),
        ("enclosure_verified", ("enclosure_verified", "enclosure_result"), "Verify high-voltage enclosure."),
    ],
    "laser_radiation": [
        ("laser_class_verified", ("laser_class_verified", "laser_class_result"), "Verify laser class."),
        ("optical_containment_verified", ("optical_containment_verified", "beam_containment_verified"), "Verify optical containment."),
        ("interlock_result", ("interlock_result", "laser_interlock_result"), "Record interlock result as passing."),
        ("labeling_verified", ("labeling_verified", "warning_label_verified"), "Verify labeling."),
        ("ppe_controls_verified", ("ppe_controls_verified", "ppe_verified"), "Verify PPE and administrative controls."),
        ("exposure_limit_verified", ("exposure_limit_verified", "mpe_verified"), "Verify exposure limit compliance."),
    ],
}


class HardwarePlanOrchestrator:
    """Connect circuit evidence, salvage planning, resource strategy, and splice planning."""

    def __init__(
        self,
        *,
        salvage_planner: Optional[SalvageSplicePlanner] = None,
        resource_planner: Optional[ResourceStrategyPlanner] = None,
    ):
        self.salvage_planner = salvage_planner or SalvageSplicePlanner()
        self.resource_planner = resource_planner or ResourceStrategyPlanner(self.salvage_planner)

    def plan(self, payload: Dict[str, Any], *, session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = enrich_payload_with_diy_project_engineering(
            enrich_payload_with_active_evidence_closure_plan(
                enrich_payload_with_arbitrary_board_workflow(
                    enrich_payload_with_repair_authority(
                        enrich_payload_with_topology_evidence(
                            enrich_payload_with_bench_topology_capture(
                                enrich_payload_with_visual_topology_hypothesis(
                                    enrich_payload_with_board_evidence(enrich_payload_with_multiview_board_evidence(dict(payload or {})))
                                )
                            )
                        )
                    )
                )
            )
        )
        context = self._context(body, session=session)
        working = dict(body)
        if context.get("analysis"):
            working["analysis"] = context["analysis"]
        if context.get("source_session_id"):
            working["source_session_id"] = context["source_session_id"]
        working["use_llm"] = bool(body.get("use_llm", False))
        working["use_llm_reasoner"] = bool(body.get("use_llm_reasoner", False))

        initial_splice_plan = self.salvage_planner.plan(working)
        strategy_payload = dict(working)
        strategy_payload["salvage_plan"] = initial_splice_plan
        strategy_payload["derive_salvage_plan"] = False
        resource_strategy = self.resource_planner.plan(strategy_payload)

        build_splice_plan = self._selected_resource_splice_plan(working, resource_strategy, initial_splice_plan)
        integrated = self._integrated_plan(
            body,
            context,
            initial_splice_plan,
            resource_strategy,
            build_splice_plan,
        )
        analysis = self._analysis_record(integrated, resource_strategy, build_splice_plan, context)
        session_payload = self._session_payload(body, integrated, analysis)
        include_debug = bool(body.get("include_debug_plans", False))
        response = {
            "mode": "hardware_plan",
            "schema_version": SCHEMA_VERSION,
            "goal": integrated["goal"],
            "strategy_mode": resource_strategy.get("strategy_mode"),
            "context": context,
            "resource_strategy": resource_strategy,
            "initial_salvage_plan": _compact_splice_plan(initial_splice_plan),
            "build_splice_plan": _compact_splice_plan(build_splice_plan),
            "integrated_plan": integrated,
            "analysis": analysis,
            "session_payload": session_payload,
            "pipeline": {
                "steps": [
                    "resolve_session_or_design_context",
                    "infer_salvage_and_functional_reuse_blocks",
                    "score_owned_salvaged_procurable_resources",
                "generate_selected_resource_splice_plan",
                "merge_readiness_evidence_and_next_actions",
                ],
                "connected_subsystems": [
                    "board_sessions",
                    "circuit_graph",
                    "diy_project_engineering",
                    "functional_salvage",
                    "salvage_splice_planner",
                    "resource_strategy",
                    "evidence_gates",
                    "arbitrary_board_workflow",
                    "active_evidence_closure_plan",
                ],
            },
        }
        if include_debug:
            response["debug_plans"] = {
                "initial_salvage_plan": initial_splice_plan,
                "build_splice_plan": build_splice_plan,
            }
        return response

    def _context(self, body: Dict[str, Any], *, session: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        source_session_id = str(
            body.get("session_id")
            or body.get("source_session_id")
            or body.get("board_session_id")
            or (session or {}).get("session_id")
            or ""
        ).strip() or None
        analysis = body.get("analysis") if isinstance(body.get("analysis"), dict) else None
        source = "payload_analysis" if analysis else None
        circuit = body.get("circuit") if isinstance(body.get("circuit"), dict) else None
        if circuit and not analysis:
            analysis = circuit
            source = "payload_circuit"

        error = None
        if analysis is None and _has_design_path(body):
            try:
                design_payload = body.get("design") if isinstance(body.get("design"), dict) else body
                analysis = analyze_circuit_design(design_payload, evidence_session=session)
                source = "payload_design"
            except (FileNotFoundError, ValueError) as exc:
                error = str(exc)

        if analysis is None and session:
            try:
                analysis = analyze_circuit_session(
                    session,
                    design_payload=body.get("design") if isinstance(body.get("design"), dict) else None,
                )
                source = "session_circuit_advance"
            except (FileNotFoundError, ValueError) as exc:
                latest = _latest_session_analysis(session)
                if latest:
                    analysis = latest
                    source = "latest_session_analysis"
                    error = str(exc)
                else:
                    error = str(exc)

        return {
            "source_session_id": source_session_id,
            "analysis_source": source or "none",
            "added_circuit_context": source in {"payload_design", "session_circuit_advance"},
            "analysis_available": isinstance(analysis, dict) and bool(analysis),
            "analysis_mode": analysis.get("mode") if isinstance(analysis, dict) else None,
            "circuit_context_error": error,
            "session_evidence": _session_evidence_summary(session),
            "measurements": _measurement_context(body, session=session, analysis=analysis or {}),
            "authority": _authority_context(body, session=session, analysis=analysis or {}),
            "outcome_memory": _outcome_memory_context(body, session=session),
            "analysis": analysis or {},
        }

    def _selected_resource_splice_plan(
        self,
        base_payload: Dict[str, Any],
        resource_strategy: Dict[str, Any],
        initial_splice_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        selected = resource_strategy.get("selected_resources") if isinstance(resource_strategy.get("selected_resources"), list) else []
        selected_parts = [
            {
                "name": resource.get("name"),
                "capabilities": resource.get("capabilities") or [],
                "quantity": resource.get("quantity", 1),
                "confidence": resource.get("confidence", 0.7),
                "source": resource.get("resource_kind") or resource.get("source") or "selected_resource",
                "status": resource.get("status"),
            }
            for resource in selected
            if isinstance(resource, dict)
        ]
        build_payload = dict(base_payload)
        build_payload["available_parts"] = selected_parts or base_payload.get("available_parts") or base_payload.get("inventory") or []
        build_payload["salvage_plan"] = initial_splice_plan
        build_payload["functional_salvage"] = (
            initial_splice_plan.get("functional_reuse_plan")
            if isinstance(initial_splice_plan.get("functional_reuse_plan"), dict)
            else build_payload.get("functional_salvage")
        )
        build_payload["use_llm"] = False
        build_payload["use_llm_reasoner"] = False
        plan = self.salvage_planner.plan(build_payload)
        plan["resource_strategy_link"] = {
            "selected_resource_ids": [
                str(resource.get("resource_id"))
                for resource in selected
                if isinstance(resource, dict) and resource.get("resource_id")
            ],
            "recommended_path": resource_strategy.get("recommended_path"),
            "build_readiness": (resource_strategy.get("build_readiness") or {}).get("status"),
        }
        return plan

    def _integrated_plan(
        self,
        body: Dict[str, Any],
        context: Dict[str, Any],
        initial_splice_plan: Dict[str, Any],
        resource_strategy: Dict[str, Any],
        build_splice_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        resource_readiness = resource_strategy.get("build_readiness") if isinstance(resource_strategy.get("build_readiness"), dict) else {}
        resource_status = str(resource_readiness.get("status") or "")
        splice_verdict = str(build_splice_plan.get("verdict") or initial_splice_plan.get("verdict") or "")
        authority = context.get("authority") if isinstance(context.get("authority"), dict) else {}
        base_status = _apply_authority_status(
            _combined_status(resource_status, splice_verdict),
            authority,
        )
        evidence_gates = _combined_evidence_gates(resource_strategy, build_splice_plan, context)
        selected = resource_strategy.get("selected_resources") if isinstance(resource_strategy.get("selected_resources"), list) else []
        evidence_gates = _dedupe_gates([*evidence_gates, *_outcome_memory_gates(selected, context)])
        evidence_gates = _apply_measurement_closure(evidence_gates, context)
        procurement = resource_strategy.get("procurement_plan") if isinstance(resource_strategy.get("procurement_plan"), dict) else {}
        safety_blockers = _safety_blockers(resource_strategy, build_splice_plan)
        assurance = _assurance_contract(
            base_status=base_status,
            resource_strategy=resource_strategy,
            build_splice_plan=build_splice_plan,
            evidence_gates=evidence_gates,
            selected_resources=selected,
            procurement=procurement,
            authority=authority,
            safety_blockers=safety_blockers,
        )
        status = assurance["status"]
        repair_brain = _repair_brain_context(context)
        execution_package = _execution_package(
            goal=str(body.get("goal") or body.get("description") or build_splice_plan.get("target", {}).get("requested_goal") or ""),
            resource_strategy=resource_strategy,
            build_splice_plan=build_splice_plan,
            selected_resources=selected,
            procurement=procurement,
            evidence_gates=evidence_gates,
            safety_blockers=safety_blockers,
            assurance=assurance,
            context=context,
            repair_brain=repair_brain,
        )
        completion_contract = _completion_contract(
            assurance=assurance,
            execution_package=execution_package,
            evidence_gates=evidence_gates,
            context=context,
            selected_resources=selected,
            procurement=procurement,
        )
        production_authority = _production_repair_authority_contract(
            assurance=assurance,
            completion_contract=completion_contract,
            evidence_gates=evidence_gates,
            context=context,
            selected_resources=selected,
            resource_strategy=resource_strategy,
            build_splice_plan=build_splice_plan,
            payload=body,
            goal=str(body.get("goal") or body.get("description") or ""),
        )
        next_actions = _dedupe(
            [
                *completion_contract.get("required_before_done", [])[:4],
                *(
                    production_authority.get("requirements", [])[:4]
                    if _production_authority_requested(body)
                    else []
                ),
                *assurance.get("requirements_to_unlock", [])[:4],
                *execution_package.get("next_operator_actions", [])[:4],
                *_list(resource_strategy.get("next_actions")),
                *_first_measurements(evidence_gates, build_splice_plan)[:2],
                *_first_build_steps(build_splice_plan)[:3],
            ]
        )[:10]
        if completion_contract.get("workflow_done") and (
            not _production_authority_requested(body) or production_authority.get("authorized")
        ):
            next_actions = []
        return {
            "status": status,
            "reason": _status_reason(status, resource_readiness, splice_verdict, authority, assurance),
            "assurance": assurance,
            "authority": authority,
            "repair_brain": repair_brain,
            "project_engineering": _compact_diy_project_engineering(body.get("diy_project_engineering_plan")),
            "outcome_memory": context.get("outcome_memory") if isinstance(context.get("outcome_memory"), dict) else {},
            "measurement_evidence": _measurement_evidence_summary(evidence_gates, context),
            "goal": str(body.get("goal") or body.get("description") or build_splice_plan.get("target", {}).get("requested_goal") or ""),
            "recommended_path": resource_strategy.get("recommended_path"),
            "target": build_splice_plan.get("target") if isinstance(build_splice_plan.get("target"), dict) else {},
            "selected_resource_count": len(selected),
            "selected_resource_ids": [
                str(resource.get("resource_id"))
                for resource in selected
                if isinstance(resource, dict) and resource.get("resource_id")
            ],
            "procurement": {
                "estimated_cost_usd": procurement.get("estimated_cost_usd", 0),
                "within_budget": procurement.get("within_budget", True),
                "item_count": len(procurement.get("items") or []),
                "unfilled_capabilities": procurement.get("unfilled_capabilities") or [],
            },
            "coverage": resource_strategy.get("coverage") or {},
            "first_measurements": _first_measurements(evidence_gates, build_splice_plan),
            "first_build_steps": _first_build_steps(build_splice_plan),
            "evidence_gates": evidence_gates,
            "safety_blockers": safety_blockers,
            "execution_package": execution_package,
            "completion_contract": completion_contract,
            "production_repair_authority": production_authority,
            "next_actions": next_actions,
            "dossier_summary": {
                "context_source": context.get("analysis_source"),
                "resource_strategy": resource_strategy.get("strategy_mode"),
                "resource_readiness": resource_status,
                "splice_verdict": splice_verdict,
                "repair_authority_status": authority.get("repair_authority_status"),
                "assurance_level": assurance.get("level"),
                "assurance_score": assurance.get("score"),
                "execution_stage": execution_package.get("current_stage"),
                "completion_state": completion_contract.get("state"),
                "plan_done": completion_contract.get("plan_done"),
                "workflow_done": completion_contract.get("workflow_done"),
                "production_repair_authorized": production_authority.get("authorized"),
                "production_repair_decision": production_authority.get("decision"),
                "production_casefile_status": (production_authority.get("authority_casefile") or {}).get("status"),
                "production_casefile_blocked_claim_count": (production_authority.get("authority_casefile") or {}).get("blocked_claim_count"),
                "board_function": repair_brain.get("board_function", {}).get("primary_function_id"),
                "fault_isolation_state": repair_brain.get("fault_isolation", {}).get("state"),
                "salvage_value_decision": repair_brain.get("salvage_value_decision", {}).get("decision"),
                "grounded_part_count": len(repair_brain.get("part_grounding", {}).get("matched_parts") or []),
                "reuse_splice_readiness": repair_brain.get("reuse_splice_strategy", {}).get("readiness"),
                "arbitrary_board_trust_level": repair_brain.get("arbitrary_board_trust_assessment", {}).get("level"),
                "arbitrary_board_trust_score": repair_brain.get("arbitrary_board_trust_assessment", {}).get("score"),
                "arbitrary_board_production_readiness_score": repair_brain.get("arbitrary_board_trust_assessment", {}).get("production_readiness_score"),
                "open_gate_count": len([gate for gate in evidence_gates if str(gate.get("status", "open")) not in {"closed", "pass"}]),
                "closed_measurement_gate_count": len([gate for gate in evidence_gates if gate.get("type") == "measurement" and str(gate.get("status")) in {"closed", "pass"}]),
                "failed_measurement_gate_count": len([gate for gate in evidence_gates if gate.get("type") == "measurement" and str(gate.get("status")) == "failed"]),
                "claim_boundary": _authority_claim_boundary(authority),
            },
        }

    def _analysis_record(
        self,
        integrated: Dict[str, Any],
        resource_strategy: Dict[str, Any],
        build_splice_plan: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        context_analysis = context.get("analysis") if isinstance(context.get("analysis"), dict) else {}
        context_tasks = [task for task in context_analysis.get("next_evidence_tasks") or [] if isinstance(task, dict)]
        gate_tasks = [
            {
                "type": "measurement" if gate.get("type") in {"measurement", "resource_gap"} else "review",
                "prompt": gate.get("prompt"),
                "priority": 1 if gate.get("type") == "safety" else 2,
                "source": gate.get("source") or "hardware_plan_gate",
            }
            for gate in integrated.get("evidence_gates") or []
            if isinstance(gate, dict) and gate.get("prompt")
            and str(gate.get("status", "open")) not in {"closed", "pass"}
        ]
        tasks = _dedupe_analysis_tasks([*context_tasks, *gate_tasks])
        return {
            "mode": "hardware_plan",
            "schema_version": SCHEMA_VERSION,
            "repair_authority": context_analysis.get("repair_authority") if isinstance(context_analysis.get("repair_authority"), dict) else {},
            "evidence_trust": context_analysis.get("evidence_trust") if isinstance(context_analysis.get("evidence_trust"), dict) else {},
            "arbitrary_board_authority": context_analysis.get("arbitrary_board_authority") if isinstance(context_analysis.get("arbitrary_board_authority"), dict) else {},
            "authority_integrity": context_analysis.get("authority_integrity") if isinstance(context_analysis.get("authority_integrity"), dict) else {},
            "operator_repair_authority": context_analysis.get("operator_repair_authority") if isinstance(context_analysis.get("operator_repair_authority"), dict) else {},
            "diy_project_engineering": context_analysis.get("diy_project_engineering") if isinstance(context_analysis.get("diy_project_engineering"), dict) else {},
            "multiview_board_reconstruction": context_analysis.get("multiview_board_reconstruction") if isinstance(context_analysis.get("multiview_board_reconstruction"), dict) else {},
            "board_evidence": context_analysis.get("board_evidence") if isinstance(context_analysis.get("board_evidence"), dict) else {},
            "vision_evidence_bridge": context_analysis.get("vision_evidence_bridge") if isinstance(context_analysis.get("vision_evidence_bridge"), dict) else {},
            "visual_topology_hypothesis": context_analysis.get("visual_topology_hypothesis") if isinstance(context_analysis.get("visual_topology_hypothesis"), dict) else {},
            "bench_topology_capture": context_analysis.get("bench_topology_capture") if isinstance(context_analysis.get("bench_topology_capture"), dict) else {},
            "bench_topology_evidence": context_analysis.get("bench_topology_evidence") if isinstance(context_analysis.get("bench_topology_evidence"), dict) else {},
            "arbitrary_board_workflow": context_analysis.get("arbitrary_board_workflow") if isinstance(context_analysis.get("arbitrary_board_workflow"), dict) else {},
            "board_function_inference": context_analysis.get("board_function_inference") if isinstance(context_analysis.get("board_function_inference"), dict) else {},
            "measurement_protocol": context_analysis.get("measurement_protocol") if isinstance(context_analysis.get("measurement_protocol"), dict) else {},
            "bench_protocol_pack": context_analysis.get("bench_protocol_pack") if isinstance(context_analysis.get("bench_protocol_pack"), dict) else {},
            "fault_isolation": context_analysis.get("fault_isolation") if isinstance(context_analysis.get("fault_isolation"), dict) else {},
            "salvage_value_decision": context_analysis.get("salvage_value_decision") if isinstance(context_analysis.get("salvage_value_decision"), dict) else {},
            "part_grounding": context_analysis.get("part_grounding") if isinstance(context_analysis.get("part_grounding"), dict) else {},
            "component_salvage_map": context_analysis.get("component_salvage_map") if isinstance(context_analysis.get("component_salvage_map"), dict) else {},
            "layout_reuse_boundaries": context_analysis.get("layout_reuse_boundaries") if isinstance(context_analysis.get("layout_reuse_boundaries"), dict) else {},
            "reuse_splice_strategy": context_analysis.get("reuse_splice_strategy") if isinstance(context_analysis.get("reuse_splice_strategy"), dict) else {},
            "arbitrary_board_trust_assessment": context_analysis.get("arbitrary_board_trust_assessment") if isinstance(context_analysis.get("arbitrary_board_trust_assessment"), dict) else {},
            "active_evidence_closure_plan": context_analysis.get("active_evidence_closure_plan") if isinstance(context_analysis.get("active_evidence_closure_plan"), dict) else {},
            "evidence_contradictions": context_analysis.get("evidence_contradictions") if isinstance(context_analysis.get("evidence_contradictions"), dict) else {},
            "topology_authority": context_analysis.get("topology_authority") if isinstance(context_analysis.get("topology_authority"), dict) else {},
            "hardware_plan_summary": {
                "status": integrated.get("status"),
                "recommended_path": integrated.get("recommended_path"),
                "selected_resource_count": integrated.get("selected_resource_count"),
                "procurement": integrated.get("procurement"),
                "authority": integrated.get("authority"),
                "target": integrated.get("target"),
                "selected_resource_ids": integrated.get("selected_resource_ids") or [],
                "first_measurements": integrated.get("first_measurements") or [],
                "first_build_steps": integrated.get("first_build_steps") or [],
                "assurance": integrated.get("assurance"),
                "execution_package": integrated.get("execution_package"),
                "completion_contract": integrated.get("completion_contract"),
                "production_repair_authority": integrated.get("production_repair_authority"),
                "outcome_memory": integrated.get("outcome_memory"),
                "measurement_evidence": integrated.get("measurement_evidence"),
                "project_engineering": integrated.get("project_engineering"),
                "active_evidence_closure_plan": context_analysis.get("active_evidence_closure_plan") if isinstance(context_analysis.get("active_evidence_closure_plan"), dict) else {},
                "claim_boundary": (integrated.get("dossier_summary") or {}).get("claim_boundary"),
            },
            "resource_strategy": resource_strategy,
            "salvage_splice_plan": _compact_splice_plan(build_splice_plan),
            "machine_connection_map": {
                "splice_plan": build_splice_plan.get("splice_plan") if isinstance(build_splice_plan.get("splice_plan"), dict) else {},
                "topology_authority": context_analysis.get("topology_authority") if isinstance(context_analysis.get("topology_authority"), dict) else {},
            },
            "hardware_plan_gates": [
                {
                    "gate_id": gate.get("gate_id"),
                    "type": gate.get("type"),
                    "status": gate.get("status", "open"),
                    "prompt": gate.get("prompt"),
                    "source": gate.get("source"),
                    "closure": gate.get("closure") if isinstance(gate.get("closure"), dict) else None,
                }
                for gate in integrated.get("evidence_gates") or []
                if isinstance(gate, dict) and gate.get("prompt")
            ],
            "next_evidence_tasks": tasks[:40],
            "certainty_ledger": {
                "overall": {
                    "score": _certainty_score(integrated),
                    "level": "possible" if integrated.get("status") in {"ready_for_build_plan", "prototype_after_evidence"} else "unknown",
                },
                "missing_evidence": [task["prompt"] for task in tasks[:12]],
                "training_queue": {"should_capture": True, "reason": "hardware plan needs resource, measurement, and build outcome evidence"},
                "items": [],
            },
        }

    def _session_payload(
        self,
        body: Dict[str, Any],
        integrated: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        title = str(body.get("title") or integrated.get("target", {}).get("recommended_build") or "Hardware plan")
        return {
            "title": title,
            "description": str(body.get("description") or integrated.get("goal") or title),
            "device_hint": str(body.get("device_hint") or title),
            "symptoms": [integrated.get("status"), integrated.get("recommended_path")],
            "route": "hardware_plan",
            "route_label": "hardware plan",
            "analysis": analysis,
            "summary": {
                "status": integrated.get("status"),
                "recommended_path": integrated.get("recommended_path"),
                "selected_resource_count": integrated.get("selected_resource_count"),
            },
            "source": "hardware_plan",
            "case_file": {
                "kind": "hardware_resource_build_plan",
                "goal": integrated.get("goal"),
                "status": integrated.get("status"),
                "selected_resource_ids": integrated.get("selected_resource_ids") or [],
            },
        }


def _has_design_path(payload: Dict[str, Any]) -> bool:
    candidates = []
    if isinstance(payload.get("design"), dict):
        candidates.append(payload["design"])
    candidates.append(payload)
    for candidate in candidates:
        for key in ["board", "boards"]:
            value = candidate.get(key)
            rows = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
            for row in rows:
                if isinstance(row, dict) and str(row.get("path") or row.get("design_path") or "").strip():
                    return True
    return False


def _latest_session_analysis(session: Dict[str, Any]) -> Dict[str, Any]:
    analyses = session.get("analyses") if isinstance(session.get("analyses"), list) else []
    if not analyses:
        return {}
    latest = analyses[-1] if isinstance(analyses[-1], dict) else {}
    results = latest.get("results")
    return results if isinstance(results, dict) else {}


def _session_evidence_summary(session: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(session, dict):
        return {}
    evidence = session.get("evidence") if isinstance(session.get("evidence"), dict) else {}
    return {
        "capture_count": len(evidence.get("captures") or []),
        "measurement_count": len(evidence.get("measurements") or []),
        "review_count": len(session.get("reviews") or []),
        "outcome_count": len(session.get("outcomes") or []),
    }


def _measurement_context(
    payload: Dict[str, Any],
    *,
    session: Optional[Dict[str, Any]],
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for key in ["measurements", "measurement_history", "bench_measurements", "evidence_measurements"]:
        _extend_measurement_rows(rows, payload.get(key), f"payload.{key}")
    payload_evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    _extend_measurement_rows(rows, payload_evidence.get("measurements"), "payload.evidence.measurements")
    analysis_evidence = analysis.get("evidence") if isinstance(analysis.get("evidence"), dict) else {}
    _extend_measurement_rows(rows, analysis.get("measurements"), "analysis.measurements")
    _extend_measurement_rows(rows, analysis_evidence.get("measurements"), "analysis.evidence.measurements")
    if isinstance(session, dict):
        evidence = session.get("evidence") if isinstance(session.get("evidence"), dict) else {}
        _extend_measurement_rows(rows, evidence.get("measurements"), "session.evidence.measurements")

    normalized: List[Dict[str, Any]] = []
    seen = set()
    for index, row in enumerate(rows):
        measurement = _normalize_measurement(row, index=index)
        key = (
            measurement.get("measurement_id"),
            measurement.get("type"),
            measurement.get("target"),
            str(measurement.get("value")),
            measurement.get("unit"),
            measurement.get("notes"),
        )
        if key in seen:
            continue
        seen.add(key)
        normalized.append(measurement)

    return {
        "schema_version": "hardware_measurement_context.v1",
        "available": bool(normalized),
        "measurement_count": len(normalized),
        "passed_count": len([row for row in normalized if row.get("passed")]),
        "failed_count": len([row for row in normalized if row.get("failed")]),
        "measurements": normalized[-80:],
    }


def _extend_measurement_rows(rows: List[Dict[str, Any]], value: Any, source: str) -> None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                row = dict(item)
                row["_source"] = source
                rows.append(row)
    elif isinstance(value, dict):
        if isinstance(value.get("measurements"), list):
            _extend_measurement_rows(rows, value.get("measurements"), source)
        elif any(key in value for key in ["type", "measurement_type", "target", "value", "result", "notes", "status"]):
            row = dict(value)
            row["_source"] = source
            rows.append(row)


def _normalize_measurement(row: Dict[str, Any], *, index: int) -> Dict[str, Any]:
    value = _measurement_value(row)
    record = {
        "measurement_id": str(row.get("measurement_id") or row.get("id") or f"measurement_{index + 1}"),
        "type": str(row.get("type") or row.get("measurement_type") or row.get("kind") or "measurement"),
        "target": str(row.get("target") or row.get("net") or row.get("pin") or row.get("node") or ""),
        "value": value,
        "unit": str(row.get("unit") or row.get("units") or ""),
        "notes": str(row.get("notes") or row.get("summary") or row.get("reason") or ""),
        "confidence": _safe_float(row.get("confidence"), 1.0),
        "source": str(row.get("_source") or row.get("source") or "measurement"),
        "instrument_id": str(row.get("instrument_id") or row.get("meter_id") or row.get("fixture_id") or "").strip(),
        "instrument_type": str(row.get("instrument_type") or row.get("meter_type") or row.get("fixture_type") or "").strip(),
        "calibration_status": str(row.get("calibration_status") or row.get("calibration") or "").strip(),
        "recorded_at": str(row.get("recorded_at") or row.get("timestamp") or row.get("measured_at") or "").strip(),
        "operator_id": str(row.get("operator_id") or row.get("captured_by") or row.get("technician_id") or "").strip(),
        "evidence_uri": str(row.get("evidence_uri") or row.get("artifact_uri") or row.get("photo_uri") or "").strip(),
    }
    text = _measurement_text(record)
    failed = _measurement_failed(row, text)
    passed = False if failed else _measurement_passed(row, text)
    record["text"] = text
    record["tokens"] = sorted(_tokens_for_match(text))
    record["categories"] = sorted(_measurement_categories(text, unit=record.get("unit")))
    record["failed"] = failed
    record["passed"] = passed
    return record


def _measurement_value(row: Dict[str, Any]) -> Any:
    for key in ["value", "result", "reading", "measured_value"]:
        if key in row:
            return row.get(key)
    return None


def _measurement_text(record: Dict[str, Any]) -> str:
    return " ".join(
        str(record.get(key) or "")
        for key in ["type", "target", "value", "unit", "notes", "source"]
    ).lower()


def _measurement_failed(row: Dict[str, Any], text: str) -> bool:
    status = str(row.get("status") or row.get("result_status") or "").strip().lower()
    if status in {"failed", "fail", "unsafe", "blocked", "safety_hold"}:
        return True
    value_text = str(row.get("value") if "value" in row else row.get("result") or "").strip().lower()
    pass_like = status in {"closed", "pass", "passed", "ok", "verified", "resolved"} or value_text in {
        "pass",
        "passed",
        "ok",
        "good",
        "closed",
        "verified",
        "normal",
    }
    if pass_like and any(phrase in text for phrase in ["not shorted", "not short", "no short", "no-short", "not failed"]):
        return False
    if re.search(r"\b(fail|failed|unsafe|overcurrent|over-current|smoke|smell|burning|burnt|hot)\b", text):
        return True
    fail_phrases = [
        "short detected",
        "dead short",
        "short to ground",
        "shorted",
        "reverse polarity",
        "wrong polarity",
        "thermal runaway",
        "abnormal current",
        "unexpected current",
    ]
    return any(phrase in text for phrase in fail_phrases)


def _measurement_passed(row: Dict[str, Any], text: str) -> bool:
    status = str(row.get("status") or row.get("result_status") or "").strip().lower()
    value = row.get("value") if "value" in row else row.get("result")
    value_text = str(value or "").strip().lower()
    if status in {"closed", "pass", "passed", "ok", "verified", "resolved"}:
        return True
    if value_text in {"pass", "passed", "ok", "good", "closed", "verified", "normal"}:
        return True
    pass_phrases = [
        "no short",
        "no-short",
        "not short",
        "continuity ok",
        "continuity pass",
        "idle high",
        "within limit",
        "polarity ok",
        "current limited",
        "current-limited",
        "verified",
        "measured",
    ]
    if any(phrase in text for phrase in pass_phrases):
        return True
    return value not in {None, ""}


def _apply_measurement_closure(
    evidence_gates: Sequence[Dict[str, Any]],
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    measurement_context = context.get("measurements") if isinstance(context.get("measurements"), dict) else {}
    measurements = [row for row in measurement_context.get("measurements") or [] if isinstance(row, dict)]
    if not measurements:
        return [dict(gate) for gate in evidence_gates]

    closed: List[Dict[str, Any]] = []
    for gate in evidence_gates:
        next_gate = dict(gate)
        status = str(next_gate.get("status", "open"))
        if next_gate.get("type") != "measurement" or status in {"closed", "pass", "blocked"}:
            closed.append(next_gate)
            continue
        match = _matching_measurement_for_gate(next_gate, measurements)
        if not match:
            closed.append(next_gate)
            continue
        next_gate["status"] = "failed" if match.get("failed") else "closed"
        next_gate["result"] = "fail" if match.get("failed") else "pass"
        next_gate["closure"] = {
            "source": "measurement",
            "measurement_id": match.get("measurement_id"),
            "measurement_type": match.get("type"),
            "target": match.get("target"),
            "value": match.get("value"),
            "unit": match.get("unit"),
            "notes": match.get("notes"),
            "confidence": match.get("confidence"),
        }
        closed.append(next_gate)
    return closed


def _matching_measurement_for_gate(gate: Dict[str, Any], measurements: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    scored = []
    for measurement in measurements:
        score = _measurement_match_score(str(gate.get("prompt") or ""), measurement)
        if score > 0:
            scored.append((score, measurement))
    if not scored:
        return None
    scored.sort(
        key=lambda item: (
            bool(item[1].get("failed")),
            item[0],
            _safe_float(item[1].get("confidence"), 0.0),
        ),
        reverse=True,
    )
    best = scored[0][1]
    if best.get("failed") or best.get("passed"):
        return best
    return None


def _measurement_match_score(prompt: str, measurement: Dict[str, Any]) -> int:
    prompt_text = str(prompt or "").lower()
    prompt_categories = _measurement_categories(prompt_text)
    measurement_categories = set(str(item) for item in measurement.get("categories") or [])
    if prompt_categories and not prompt_categories.issubset(measurement_categories):
        return 0
    prompt_tokens = _tokens_for_match(prompt_text)
    measurement_tokens = set(str(item) for item in measurement.get("tokens") or [])
    overlap = prompt_tokens & measurement_tokens
    score = len(overlap) + (2 * len(prompt_categories & measurement_categories))
    if score < max(3, 2 * max(len(prompt_categories), 1)):
        return 0
    if len(overlap) >= 2:
        return score
    signal_tokens = {"logic", "serial", "uart", "i2c", "spi", "idle", "high", "tx", "rx", "scl", "sda"}
    electrical_tokens = {"power", "ground", "short", "resistance", "continuity", "current", "voltage", "polarity"}
    if prompt_categories & {"logic"} and overlap & signal_tokens:
        return score
    if prompt_categories & {"resistance", "continuity", "current", "voltage"} and overlap & electrical_tokens:
        return score
    return 0


def _measurement_categories(text: str, *, unit: Any = "") -> set:
    raw = str(text or "").lower()
    unit_text = str(unit or "").strip().lower()
    categories = set()
    if "voltage" in raw or "polarity" in raw or unit_text in {"v", "volt", "volts"} or re.search(r"\b\d+(?:\.\d+)?\s*v\b", raw):
        categories.add("voltage")
    if "resistance" in raw or "ohm" in raw or unit_text in {"ohm", "ohms"} or "no-short" in raw or "no short" in raw or "short check" in raw:
        categories.add("resistance")
    if "continuity" in raw or "shared ground" in raw:
        categories.add("continuity")
    if "current" in raw or "current-limited" in raw or "current limited" in raw or unit_text in {"a", "ma", "amp", "amps"}:
        categories.add("current")
    if any(token in raw for token in ["thermal", "temperature", "heat", "hot", "warm"]) or unit_text in {"c", "°c", "degc", "celsius"}:
        categories.add("thermal")
    if any(token in raw for token in ["logic", "serial", "uart", "i2c", "spi", "idle", "tx", "rx", "scl", "sda", "mosi", "miso"]):
        categories.add("logic")
    return categories


def _tokens_for_match(value: Any) -> set:
    stop = {
        "the",
        "and",
        "or",
        "to",
        "from",
        "before",
        "after",
        "between",
        "with",
        "without",
        "under",
        "if",
        "is",
        "are",
        "a",
        "an",
        "of",
        "for",
        "in",
        "on",
        "at",
        "by",
        "as",
        "be",
        "must",
        "measure",
        "measurement",
        "measured",
        "confirm",
        "verify",
        "verified",
        "record",
        "reused",
        "requirement",
        "requirements",
        "state",
    }
    return {
        token
        for token in re.split(r"[^a-zA-Z0-9+.\-]+", str(value or "").lower())
        if len(token) >= 2 and token not in stop
    }


def _measurement_evidence_summary(
    evidence_gates: Sequence[Dict[str, Any]],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    measurement_context = context.get("measurements") if isinstance(context.get("measurements"), dict) else {}
    measurement_gates = [gate for gate in evidence_gates if isinstance(gate, dict) and gate.get("type") == "measurement"]
    return {
        "measurement_count": measurement_context.get("measurement_count", 0),
        "passed_measurement_count": measurement_context.get("passed_count", 0),
        "failed_measurement_count": measurement_context.get("failed_count", 0),
        "closed_gate_count": len([gate for gate in measurement_gates if str(gate.get("status")) in {"closed", "pass"}]),
        "failed_gate_count": len([gate for gate in measurement_gates if str(gate.get("status")) == "failed"]),
        "open_measurement_gate_count": len([gate for gate in measurement_gates if str(gate.get("status", "open")) not in {"closed", "pass", "failed"}]),
    }


def _authority_context(
    payload: Dict[str, Any],
    *,
    session: Optional[Dict[str, Any]],
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    authority = _first_dict(
        payload.get("repair_authority"),
        analysis.get("repair_authority") if isinstance(analysis, dict) else None,
    )
    trust = _first_dict(
        payload.get("evidence_trust"),
        analysis.get("evidence_trust") if isinstance(analysis, dict) else None,
    )
    integrity = _first_dict(
        payload.get("authority_integrity"),
        analysis.get("authority_integrity") if isinstance(analysis, dict) else None,
    )
    for prior in reversed(_session_analyses(session)):
        if not authority and isinstance(prior.get("repair_authority"), dict):
            authority = prior["repair_authority"]
        if not trust and isinstance(prior.get("evidence_trust"), dict):
            trust = prior["evidence_trust"]
        if authority and trust:
            break

    measurements = _session_evidence_summary(session).get("measurement_count", 0)
    status = str(authority.get("status") or "unavailable")
    summary = authority.get("measurement_summary") if isinstance(authority.get("measurement_summary"), dict) else {}
    measurement_count = int(summary.get("count") or measurements or 0)
    required_measurements = [str(item) for item in authority.get("required_measurements") or [] if str(item).strip()]
    blocked_decisions = [str(item) for item in authority.get("blocked_decisions") or [] if str(item).strip()]
    blockers = [str(item) for item in trust.get("blockers") or [] if str(item).strip()]
    return {
        "available": bool(authority or trust),
        "repair_authority_status": status,
        "repair_authority_score": authority.get("score"),
        "evidence_trust_level": trust.get("level"),
        "evidence_trust_score": trust.get("score"),
        "launch_readiness": trust.get("launch_readiness"),
        "measurement_count": measurement_count,
        "required_measurements": required_measurements,
        "blocked_decisions": blocked_decisions,
        "blockers": blockers,
        "authority_integrity": integrity,
        "release_authorized": status == "authoritative_low_risk",
        "claim_boundary": _authority_claim_boundary(
            {
                "repair_authority_status": status,
                "available": bool(authority or trust),
            }
        ),
    }


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _session_analyses(session: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(session, dict):
        return []
    rows = []
    for record in session.get("analyses") or []:
        if not isinstance(record, dict):
            continue
        results = record.get("results")
        if isinstance(results, dict):
            rows.append(results)
    return rows


def _outcome_memory_context(payload: Dict[str, Any], *, session: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for key in ["outcome_history", "past_outcomes", "prior_outcomes"]:
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            rows.append(value)
    if isinstance(session, dict):
        rows.extend(item for item in session.get("outcomes") or [] if isinstance(item, dict))
    normalized = [_normalize_outcome(row) for row in rows]
    normalized = [row for row in normalized if row.get("decision") or row.get("resource_ids")]
    negative = [row for row in normalized if row.get("decision") in {"failed", "unsafe_hold", "not_worth_it"}]
    positive = [row for row in normalized if row.get("decision") in {"built", "repaired", "reused", "sold"}]
    return {
        "available": bool(normalized),
        "outcome_count": len(normalized),
        "positive_count": len(positive),
        "negative_count": len(negative),
        "outcomes": normalized[-20:],
        "learning_policy": "negative or unsafe outcomes gate matching selected resources; positive outcomes add context but do not bypass evidence gates",
    }


def _normalize_outcome(row: Dict[str, Any]) -> Dict[str, Any]:
    decision = str(row.get("decision") or row.get("status") or row.get("result") or row.get("aoi_actual_status") or "").strip().lower()
    decision = decision.replace(" ", "_")
    raw_ids = (
        row.get("selected_resource_ids")
        or row.get("selected_resource_ids_used")
        or row.get("resource_ids")
        or row.get("resource_id")
        or []
    )
    if isinstance(raw_ids, str):
        resource_ids = [item.strip() for item in raw_ids.replace(";", ",").split(",") if item.strip()]
    elif isinstance(raw_ids, list):
        resource_ids = [str(item).strip() for item in raw_ids if str(item).strip()]
    else:
        resource_ids = []
    reason = str(row.get("failure_or_stop_reason") or row.get("stop_reason") or row.get("notes") or "").strip()
    return {
        "decision": decision,
        "resource_ids": resource_ids,
        "reason": reason,
        "value_recovered_usd": row.get("value_recovered_usd"),
        "cash_spent_usd": row.get("cash_spent_usd"),
        "time_spent_minutes": row.get("time_spent_minutes"),
        "measurements_recorded": row.get("measurements_recorded"),
        "deviations_from_plan": row.get("deviations_from_plan"),
        "failure_or_stop_reason": row.get("failure_or_stop_reason") or row.get("stop_reason"),
        "output_function_verified": row.get("output_function_verified"),
        "first_power_result": row.get("first_power_result"),
        "thermal_result": row.get("thermal_result"),
        "current_limit_used": row.get("current_limit_used"),
        "operator_id": row.get("operator_id") or row.get("captured_by") or row.get("technician_id"),
        "recorded_at": row.get("recorded_at") or row.get("timestamp") or row.get("completed_at"),
        "evidence_uri": row.get("evidence_uri") or row.get("artifact_uri") or row.get("test_report_uri"),
        "artifact_uri": row.get("artifact_uri"),
        "stall_current_result": row.get("stall_current_result"),
        "mechanical_guarding_verified": row.get("mechanical_guarding_verified"),
        "abnormal_current_stop_verified": row.get("abnormal_current_stop_verified"),
        "battery_chemistry_verified": row.get("battery_chemistry_verified"),
        "cell_count_verified": row.get("cell_count_verified"),
        "bms_protection_verified": row.get("bms_protection_verified"),
        "cell_balance_result": row.get("cell_balance_result"),
        "charge_discharge_result": row.get("charge_discharge_result"),
        "thermal_containment_verified": row.get("thermal_containment_verified"),
        "isolation_result": row.get("isolation_result"),
        "isolation_test_result": row.get("isolation_test_result"),
        "discharge_result": row.get("discharge_result"),
        "leakage_current_result": row.get("leakage_current_result"),
        "earth_bond_result": row.get("earth_bond_result"),
        "fuse_protection_verified": row.get("fuse_protection_verified"),
        "creepage_clearance_verified": row.get("creepage_clearance_verified"),
        "enclosure_verified": row.get("enclosure_verified"),
        "enclosure_result": row.get("enclosure_result"),
        "containment_result": row.get("containment_result"),
        "laser_class_verified": row.get("laser_class_verified"),
        "interlock_result": row.get("interlock_result"),
        "laser_interlock_result": row.get("laser_interlock_result"),
        "optical_containment_verified": row.get("optical_containment_verified"),
        "labeling_verified": row.get("labeling_verified"),
        "ppe_controls_verified": row.get("ppe_controls_verified"),
        "exposure_limit_verified": row.get("exposure_limit_verified"),
        "production_evidence": row.get("production_evidence") if isinstance(row.get("production_evidence"), dict) else {},
        "source": row.get("outcome_id") or row.get("source") or "outcome_history",
    }


def _outcome_memory_gates(
    selected_resources: Sequence[Dict[str, Any]],
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    memory = context.get("outcome_memory") if isinstance(context.get("outcome_memory"), dict) else {}
    if not memory.get("available"):
        return []
    selected_ids = {
        str(resource.get("resource_id") or "")
        for resource in selected_resources
        if isinstance(resource, dict) and resource.get("resource_id")
    }
    gates: List[Dict[str, Any]] = []
    for outcome in memory.get("outcomes") or []:
        if not isinstance(outcome, dict):
            continue
        matched = sorted(selected_ids & set(str(item) for item in outcome.get("resource_ids") or []))
        if not matched:
            continue
        decision = str(outcome.get("decision") or "")
        if decision == "unsafe_hold":
            gates.append(
                {
                    "gate_id": _safe_id(f"outcome_unsafe_{'_'.join(matched)}"),
                    "type": "safety",
                    "status": "blocked",
                    "prompt": f"Prior unsafe outcome exists for selected resource(s) {', '.join(matched)}: {outcome.get('reason') or 'unsafe hold'}.",
                    "source": "outcome_memory",
                }
            )
        elif decision in {"failed", "not_worth_it"}:
            gates.append(
                {
                    "gate_id": _safe_id(f"outcome_review_{'_'.join(matched)}"),
                    "type": "review",
                    "status": "open",
                    "prompt": f"Review prior {decision.replace('_', ' ')} outcome for selected resource(s) {', '.join(matched)} before reuse: {outcome.get('reason') or 'no reason recorded'}.",
                    "source": "outcome_memory",
                }
            )
    return gates[:12]


def _combined_status(resource_status: str, splice_verdict: str) -> str:
    if resource_status == "safety_hold" or splice_verdict == "unsafe_hold":
        return "safety_hold"
    if resource_status in {"blocked_missing_resources", "blocked_over_budget"}:
        return resource_status
    if splice_verdict in {"collect_more_evidence", "inventory_first"} and resource_status not in {"ready_for_build_plan", "prototype_after_evidence"}:
        return "collect_more_evidence"
    if resource_status == "prototype_after_evidence" or splice_verdict == "ready_after_measurements":
        return "prototype_after_evidence"
    if resource_status == "ready_for_build_plan" and splice_verdict in {"reuse_ready", "ready_after_measurements"}:
        return "ready_for_build_plan"
    return resource_status or splice_verdict or "collect_more_evidence"


def _apply_authority_status(status: str, authority: Dict[str, Any]) -> str:
    if not authority.get("available"):
        return status
    authority_status = str(authority.get("repair_authority_status") or "")
    if authority_status == "blocked":
        return "safety_hold"
    if status == "ready_for_build_plan" and authority_status in {"visual_only", "needs_measurements", "measurement_backed"}:
        return "prototype_after_evidence"
    return status


def _status_reason(
    status: str,
    resource_readiness: Dict[str, Any],
    splice_verdict: str,
    authority: Dict[str, Any],
    assurance: Dict[str, Any],
) -> str:
    if assurance.get("blockers"):
        return str(assurance["blockers"][0])
    authority_status = str(authority.get("repair_authority_status") or "")
    if authority_status == "blocked":
        return "Repair authority is blocked; the hardware plan is limited to evidence collection and safety review."
    if status == "prototype_after_evidence" and authority_status in {"visual_only", "needs_measurements", "measurement_backed"}:
        return "A build path exists, but repair/build authority still requires the listed measurements and evidence gates."
    if status == "ready_for_build_plan":
        return "Resource coverage and splice planning are connected; final authority depends on closed evidence gates."
    if status == "prototype_after_evidence":
        return "A build path exists, but measurements or review gates must close before first power or splice."
    if status == "blocked_missing_resources":
        return "The selected strategy cannot cover every required capability yet."
    if status == "blocked_over_budget":
        return "The selected procurement plan exceeds the stated budget."
    if status == "safety_hold":
        return "Safety or failed-evidence blockers prevent using one or more resources."
    return str(resource_readiness.get("reason") or splice_verdict or "More evidence is required.")


def _authority_claim_boundary(authority: Dict[str, Any]) -> str:
    status = str(authority.get("repair_authority_status") or "")
    if status == "authoritative_low_risk":
        return "Hardware plan authority applies only to measured low-risk claims; hidden nets, high-voltage sections, lithium packs, and unmeasured splices remain gated."
    if authority.get("available"):
        return "Hardware plan is advisory until repair authority, resource evidence gates, and first-power measurements close."
    return "Hardware plan is advisory; no repair authority snapshot is attached to this context yet."


def _repair_brain_context(context: Dict[str, Any]) -> Dict[str, Any]:
    analysis = context.get("analysis") if isinstance(context.get("analysis"), dict) else {}
    workflow = analysis.get("arbitrary_board_workflow") if isinstance(analysis.get("arbitrary_board_workflow"), dict) else {}
    board_function = analysis.get("board_function_inference") if isinstance(analysis.get("board_function_inference"), dict) else {}
    contradictions = analysis.get("evidence_contradictions") if isinstance(analysis.get("evidence_contradictions"), dict) else {}
    protocol = analysis.get("measurement_protocol") if isinstance(analysis.get("measurement_protocol"), dict) else {}
    fault = analysis.get("fault_isolation") if isinstance(analysis.get("fault_isolation"), dict) else {}
    value = analysis.get("salvage_value_decision") if isinstance(analysis.get("salvage_value_decision"), dict) else {}
    part_grounding = analysis.get("part_grounding") if isinstance(analysis.get("part_grounding"), dict) else {}
    component_salvage = analysis.get("component_salvage_map") if isinstance(analysis.get("component_salvage_map"), dict) else {}
    layout_boundaries = analysis.get("layout_reuse_boundaries") if isinstance(analysis.get("layout_reuse_boundaries"), dict) else {}
    reuse_splice = analysis.get("reuse_splice_strategy") if isinstance(analysis.get("reuse_splice_strategy"), dict) else {}
    trust_assessment = analysis.get("arbitrary_board_trust_assessment") if isinstance(analysis.get("arbitrary_board_trust_assessment"), dict) else {}
    bench_protocol = analysis.get("bench_protocol_pack") if isinstance(analysis.get("bench_protocol_pack"), dict) else {}
    if not any([workflow, board_function, contradictions, protocol, fault, value, part_grounding, component_salvage, layout_boundaries, reuse_splice, trust_assessment, bench_protocol]):
        return {"available": False}
    protocol_steps = [step for step in protocol.get("steps") or [] if isinstance(step, dict)]
    open_steps = [step for step in protocol_steps if str(step.get("status") or "") in {"open", "blocked"}]
    return {
        "available": True,
        "schema_version": "hardware_plan_repair_brain.v1",
        "board_function": {
            "primary_function_id": board_function.get("primary_function_id"),
            "primary_label": board_function.get("primary_label"),
            "confidence": board_function.get("confidence"),
            "confirmation_required": ((board_function.get("candidates") or [{}])[0] or {}).get("confirmation_required") if board_function.get("candidates") else [],
        },
        "evidence_contradictions": {
            "status": contradictions.get("status"),
            "hard_count": contradictions.get("hard_count", 0),
            "soft_count": contradictions.get("soft_count", 0),
            "items": contradictions.get("items") or [],
        },
        "measurement_protocol": {
            "status": protocol.get("status"),
            "step_count": protocol.get("step_count", len(protocol_steps)),
            "open_step_count": protocol.get("open_step_count", len(open_steps)),
            "next_steps": _repair_brain_next_protocol_steps(protocol_steps),
        },
        "bench_protocol_pack": {
            "schema_version": bench_protocol.get("schema_version"),
            "primary_function_id": bench_protocol.get("primary_function_id"),
            "title": bench_protocol.get("title"),
            "specialist_only": bool(bench_protocol.get("specialist_only")),
            "required_measurement_categories": bench_protocol.get("required_measurement_categories") or [],
            "required_equipment": bench_protocol.get("required_equipment") or [],
            "setup_controls": bench_protocol.get("setup_controls") or [],
            "step_count": bench_protocol.get("step_count", 0),
            "next_steps": _repair_brain_next_bench_steps(bench_protocol.get("steps") or []),
            "pass_fail_criteria": bench_protocol.get("pass_fail_criteria") or {},
            "release_artifacts_required": bench_protocol.get("release_artifacts_required") or [],
            "release_boundary": bench_protocol.get("release_boundary"),
        },
        "fault_isolation": {
            "state": fault.get("state"),
            "top_fault_id": fault.get("top_fault_id"),
            "top_fault": ((fault.get("candidates") or [{}])[0] or {}).get("label") if fault.get("candidates") else None,
            "candidates": fault.get("candidates") or [],
        },
        "salvage_value_decision": {
            "decision": value.get("decision"),
            "confidence": value.get("confidence"),
            "expected_recoverable_value_usd": value.get("expected_recoverable_value_usd"),
            "estimated_cash_to_continue_usd": value.get("estimated_cash_to_continue_usd"),
            "estimated_time_minutes": value.get("estimated_time_minutes"),
            "value_ratio": value.get("value_ratio"),
            "recommended_exit": value.get("recommended_exit"),
        },
        "part_grounding": {
            "available": part_grounding.get("available", False),
            "matched_parts": part_grounding.get("matched_parts") or [],
            "grounded_capabilities": part_grounding.get("grounded_capabilities") or [],
            "function_votes": part_grounding.get("function_votes") or [],
            "grounding_tasks": part_grounding.get("grounding_tasks") or [],
        },
        "component_salvage_map": {
            "salvage_posture": component_salvage.get("salvage_posture"),
            "preferred_reuse_class": component_salvage.get("preferred_reuse_class"),
            "preferred_item_count": component_salvage.get("preferred_item_count", 0),
            "blocked_item_count": component_salvage.get("blocked_item_count", 0),
            "salvage_items": component_salvage.get("salvage_items") or [],
        },
        "layout_reuse_boundaries": {
            "layout_confidence": layout_boundaries.get("layout_confidence"),
            "multiview_evidence": bool(layout_boundaries.get("multiview_evidence")),
            "geometry_item_count": layout_boundaries.get("geometry_item_count", 0),
            "section_salvage_allowed": bool(layout_boundaries.get("section_salvage_allowed")),
            "whole_board_reuse_preferred": bool(layout_boundaries.get("whole_board_reuse_preferred", True)),
            "connector_entry_points": layout_boundaries.get("connector_entry_points") or [],
            "no_cut_zones": layout_boundaries.get("no_cut_zones") or [],
            "missing_layout_evidence": layout_boundaries.get("missing_layout_evidence") or [],
            "prohibited_layout_actions": layout_boundaries.get("prohibited_layout_actions") or [],
        },
        "reuse_splice_strategy": {
            "readiness": reuse_splice.get("readiness"),
            "strategy_summary": reuse_splice.get("strategy_summary"),
            "candidate_entry_points": reuse_splice.get("candidate_entry_points") or [],
            "recipes": reuse_splice.get("recipes") or [],
            "allowed_actions": reuse_splice.get("allowed_actions") or [],
            "prohibited_actions": reuse_splice.get("prohibited_actions") or [],
            "materials_or_mates": reuse_splice.get("materials_or_mates") or [],
            "best_next_checkpoint": reuse_splice.get("best_next_checkpoint"),
        },
        "arbitrary_board_trust_assessment": {
            "level": trust_assessment.get("level"),
            "score": trust_assessment.get("score"),
            "production_readiness_score": trust_assessment.get("production_readiness_score"),
            "trust_dimensions": trust_assessment.get("trust_dimensions") or {},
            "evidence_independence": trust_assessment.get("evidence_independence") or {},
            "blocking_gaps": trust_assessment.get("blocking_gaps") or [],
            "remaining_unknowns": trust_assessment.get("remaining_unknowns") or [],
            "readiness_summary": trust_assessment.get("readiness_summary"),
        },
        "claim_boundary": workflow.get("claim_boundary"),
    }


def _repair_brain_next_bench_steps(steps: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        rows.append(
            {
                "step_id": step.get("step_id"),
                "lane_id": step.get("lane_id"),
                "category": step.get("category"),
                "action": step.get("action"),
                "expected_result": step.get("expected_result"),
                "required_before": step.get("required_before"),
                "evidence_required": step.get("evidence_required") or [],
            }
        )
    return rows[:8]


def _repair_brain_next_protocol_steps(steps: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for step in steps:
        if str(step.get("status") or "") not in {"open", "blocked"}:
            continue
        rows.append(
            {
                "step_id": step.get("step_id"),
                "lane_id": step.get("lane_id"),
                "category": step.get("category"),
                "action": step.get("action"),
                "expected_result": step.get("expected_result"),
                "fail_branch": step.get("fail_branch"),
                "status": step.get("status"),
                "required_before": step.get("required_before"),
            }
        )
    return rows[:8]


def _combined_evidence_gates(
    resource_strategy: Dict[str, Any],
    build_splice_plan: Dict[str, Any],
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    gates: List[Dict[str, Any]] = []
    for gate in resource_strategy.get("evidence_gates") or []:
        if isinstance(gate, dict):
            gates.append({**gate, "source": "resource_strategy"})
    splice = build_splice_plan.get("splice_plan") if isinstance(build_splice_plan.get("splice_plan"), dict) else {}
    for prompt in splice.get("required_measurements") or []:
        gates.append(
            {
                "gate_id": _safe_id(f"splice_{prompt}"),
                "type": "measurement",
                "status": "open",
                "prompt": str(prompt),
                "source": "salvage_splice_plan",
            }
        )
    analysis = context.get("analysis") if isinstance(context.get("analysis"), dict) else {}
    for task in analysis.get("next_evidence_tasks") or []:
        if isinstance(task, dict) and task.get("prompt"):
            gates.append(
                {
                    "gate_id": task.get("task_id") or task.get("measurement_id") or _safe_id(task.get("prompt")),
                    "type": task.get("type") or "evidence",
                    "status": task.get("status", "open"),
                    "prompt": task.get("prompt"),
                    "source": task.get("source") or "circuit_context",
                }
            )
    authority = context.get("authority") if isinstance(context.get("authority"), dict) else {}
    for prompt in authority.get("required_measurements") or []:
        gates.append(
            {
                "gate_id": _safe_id(f"authority_{prompt}"),
                "type": "measurement",
                "status": "open",
                "prompt": str(prompt),
                "source": "repair_authority",
            }
        )
    for blocked in authority.get("blocked_decisions") or []:
        gates.append(
            {
                "gate_id": _safe_id(f"authority_blocked_{blocked}"),
                "type": "review",
                "status": "open",
                "prompt": f"Blocked repair decision: {blocked}",
                "source": "repair_authority",
            }
        )
    return _dedupe_gates(gates)[:40]


def _first_measurements(evidence_gates: Sequence[Dict[str, Any]], build_splice_plan: Dict[str, Any]) -> List[str]:
    closed_prompts = {
        str(gate.get("prompt") or "").strip().lower()
        for gate in evidence_gates
        if isinstance(gate, dict)
        and str(gate.get("status", "open")) in {"closed", "pass"}
        and gate.get("prompt")
    }
    prompts = [
        str(gate.get("prompt"))
        for gate in evidence_gates
        if isinstance(gate, dict) and gate.get("type") in {"measurement", "resource_gap"} and gate.get("prompt")
        and str(gate.get("status", "open")) not in {"closed", "pass"}
    ]
    splice = build_splice_plan.get("splice_plan") if isinstance(build_splice_plan.get("splice_plan"), dict) else {}
    prompts.extend(
        str(item)
        for item in splice.get("required_measurements") or []
        if str(item).strip().lower() not in closed_prompts
    )
    return _dedupe(prompts)[:8]


def _first_build_steps(build_splice_plan: Dict[str, Any]) -> List[str]:
    splice = build_splice_plan.get("splice_plan") if isinstance(build_splice_plan.get("splice_plan"), dict) else {}
    return _dedupe([*map(str, splice.get("wiring_steps") or []), *map(str, splice.get("mechanical_steps") or [])])[:8]


def _pin_contract_actions(pin_contracts: Sequence[Dict[str, Any]]) -> List[str]:
    actions: List[str] = []
    for contract in pin_contracts:
        if not isinstance(contract, dict):
            continue
        actions.extend(str(action) for action in contract.get("pin_actions") or [] if str(action).strip())
        if contract.get("status") != "ready_for_controlled_splice":
            actions.extend(str(item) for item in contract.get("do_not_connect_until") or [] if str(item).strip())
    return _dedupe(actions)[:12]


def _safety_blockers(resource_strategy: Dict[str, Any], build_splice_plan: Dict[str, Any]) -> List[str]:
    blockers = [
        str(resource.get("name") or resource.get("resource_id"))
        for resource in resource_strategy.get("blocked_resources") or []
        if isinstance(resource, dict)
    ]
    blockers.extend(str(item) for item in build_splice_plan.get("stop_conditions") or [])
    return _dedupe(blockers)[:12]


def _assurance_contract(
    *,
    base_status: str,
    resource_strategy: Dict[str, Any],
    build_splice_plan: Dict[str, Any],
    evidence_gates: Sequence[Dict[str, Any]],
    selected_resources: Sequence[Dict[str, Any]],
    procurement: Dict[str, Any],
    authority: Dict[str, Any],
    safety_blockers: Sequence[str],
) -> Dict[str, Any]:
    coverage = resource_strategy.get("coverage") if isinstance(resource_strategy.get("coverage"), dict) else {}
    missing = [str(item) for item in coverage.get("missing_capabilities") or []]
    procurement_unfilled = [str(item) for item in procurement.get("unfilled_capabilities") or []]
    open_gates = [
        gate for gate in evidence_gates
        if isinstance(gate, dict) and str(gate.get("status", "open")) not in {"closed", "pass"}
    ]
    blocked_gates = [
        gate for gate in open_gates
        if str(gate.get("status") or "") == "blocked" or str(gate.get("type") or "") == "safety"
    ]
    failed_gates = [gate for gate in open_gates if str(gate.get("status") or "") == "failed"]
    measurement_gates = [gate for gate in open_gates if str(gate.get("type") or "") == "measurement"]
    review_gates = [gate for gate in open_gates if str(gate.get("type") or "") == "review"]
    resource_gap_gates = [gate for gate in open_gates if str(gate.get("type") or "") == "resource_gap"]
    blockers: List[str] = []
    requirements: List[str] = []

    if failed_gates:
        blockers.append("Failed measurement evidence is attached; do not power, splice, or release this plan.")
        requirements.extend(str(gate.get("prompt")) for gate in failed_gates[:4] if gate.get("prompt"))
    if base_status == "safety_hold" or blocked_gates:
        blockers.append("Safety or repair-authority blockers are present; do not power, splice, or release this plan.")
    if missing or procurement_unfilled:
        blockers.append("Required capabilities are still missing from the selected resource set.")
        requirements.extend(f"Close resource gap: {cap}" for cap in _dedupe([*missing, *procurement_unfilled]))
    if procurement.get("within_budget") is False:
        blockers.append("Procurement estimate exceeds the stated budget.")
        requirements.append("Reduce scope, add owned resources, or increase budget before planning a build.")
    if not selected_resources:
        blockers.append("No usable selected resources are attached to the plan.")
        requirements.append("Provide owned, salvaged, or procurable resources for the required capabilities.")
    if measurement_gates:
        requirements.extend(str(gate.get("prompt")) for gate in measurement_gates[:6] if gate.get("prompt"))
    if review_gates:
        requirements.extend(str(gate.get("prompt")) for gate in review_gates[:4] if gate.get("prompt"))
    if resource_gap_gates:
        requirements.extend(str(gate.get("prompt")) for gate in resource_gap_gates[:4] if gate.get("prompt"))

    if failed_gates or base_status == "safety_hold" or blocked_gates:
        status = "safety_hold"
        level = "blocked"
    elif missing or procurement_unfilled:
        status = "blocked_missing_resources"
        level = "blocked"
    elif procurement.get("within_budget") is False:
        status = "blocked_over_budget"
        level = "blocked"
    elif not selected_resources:
        status = "collect_more_evidence"
        level = "draft"
    elif open_gates:
        status = "prototype_after_evidence"
        level = "prototype_gated"
    else:
        status = "ready_for_build_plan"
        level = "authority_ready" if authority.get("release_authorized") else "build_plan_ready"

    score = _assurance_score(
        level,
        coverage_score=float(coverage.get("coverage_score") or 0.0),
        open_gate_count=len(open_gates),
        blocker_count=len(blockers),
        has_selected=bool(selected_resources),
        authority_ready=bool(authority.get("release_authorized")),
    )
    return {
        "schema_version": "hardware_plan_assurance.v1",
        "status": status,
        "level": level,
        "score": score,
        "base_status": base_status,
        "can_build_now": status == "ready_for_build_plan" and not open_gates,
        "can_power_or_splice": status == "ready_for_build_plan" and not open_gates and bool(authority.get("release_authorized")),
        "open_gate_count": len(open_gates),
        "blocked_gate_count": len(blocked_gates),
        "failed_gate_count": len(failed_gates),
        "measurement_gate_count": len(measurement_gates),
        "review_gate_count": len(review_gates),
        "resource_gap_count": len(resource_gap_gates),
        "selected_resource_count": len(selected_resources),
        "missing_capabilities": _dedupe([*missing, *procurement_unfilled]),
        "safety_blocker_count": len(safety_blockers),
        "repair_authority_status": authority.get("repair_authority_status"),
        "blockers": _dedupe(blockers)[:8],
        "requirements_to_unlock": _dedupe(requirements)[:12],
        "claim_boundary": _authority_claim_boundary(authority),
    }


def _assurance_score(
    level: str,
    *,
    coverage_score: float,
    open_gate_count: int,
    blocker_count: int,
    has_selected: bool,
    authority_ready: bool,
) -> float:
    level_base = {
        "blocked": 0.18,
        "draft": 0.30,
        "prototype_gated": 0.58,
        "build_plan_ready": 0.76,
        "authority_ready": 0.88,
    }.get(level, 0.25)
    score = level_base + 0.12 * max(0.0, min(coverage_score, 1.0))
    if has_selected:
        score += 0.04
    if authority_ready:
        score += 0.04
    score -= 0.015 * min(open_gate_count, 10)
    score -= 0.08 * min(blocker_count, 3)
    return round(max(0.0, min(score, 0.97)), 3)


def _outcome_execution_summary(context: Dict[str, Any]) -> Dict[str, Any]:
    evidence = context.get("session_evidence") if isinstance(context.get("session_evidence"), dict) else {}
    memory = context.get("outcome_memory") if isinstance(context.get("outcome_memory"), dict) else {}
    outcomes = [row for row in memory.get("outcomes") or [] if isinstance(row, dict)]
    latest = outcomes[-1] if outcomes else {}
    successful = {"built", "repaired", "reused", "sold"}
    terminal = successful | {"failed", "unsafe_hold", "not_worth_it"}
    decision = str(latest.get("decision") or "")
    recorded = int(evidence.get("outcome_count") or 0) > 0 or bool(outcomes)
    return {
        "recorded": recorded,
        "decision": decision or None,
        "successful": decision in successful,
        "terminal": decision in terminal,
        "negative": decision in {"failed", "unsafe_hold", "not_worth_it"},
        "latest": latest,
        "outcome_count": max(int(evidence.get("outcome_count") or 0), int(memory.get("outcome_count") or 0)),
        "required_fields_present": _outcome_required_fields_present(latest) if latest else {},
    }


def _outcome_required_fields_present(outcome: Dict[str, Any]) -> Dict[str, bool]:
    return {
        "decision": bool(outcome.get("decision")),
        "selected_resource_ids_used": bool(outcome.get("resource_ids")),
        "measurements_recorded": outcome.get("measurements_recorded") not in {None, "", False},
        "cash_spent_usd": outcome.get("cash_spent_usd") is not None,
        "value_recovered_usd": outcome.get("value_recovered_usd") is not None,
        "time_spent_minutes": outcome.get("time_spent_minutes") is not None,
        "deviations_from_plan": outcome.get("deviations_from_plan") is not None,
        "failure_or_stop_reason": bool(outcome.get("reason") or outcome.get("failure_or_stop_reason") or outcome.get("decision") in {"built", "repaired", "reused", "sold"}),
        "evidence_uri": bool(outcome.get("evidence_uri") or outcome.get("artifact_uri") or outcome.get("test_report_uri")),
    }


def _completion_contract(
    *,
    assurance: Dict[str, Any],
    execution_package: Dict[str, Any],
    evidence_gates: Sequence[Dict[str, Any]],
    context: Dict[str, Any],
    selected_resources: Sequence[Dict[str, Any]],
    procurement: Dict[str, Any],
) -> Dict[str, Any]:
    open_gates = [
        gate for gate in evidence_gates
        if isinstance(gate, dict) and str(gate.get("status", "open")) not in {"closed", "pass"}
    ]
    failed_gates = [gate for gate in open_gates if str(gate.get("status") or "") == "failed"]
    outcome = _outcome_execution_summary(context)
    plan_done = bool(assurance.get("can_power_or_splice")) and not open_gates and bool(selected_resources)
    outcome_fields = outcome.get("required_fields_present") if isinstance(outcome.get("required_fields_present"), dict) else {}
    outcome_contract_complete = bool(outcome.get("recorded")) and all(outcome_fields.values()) if outcome_fields else False
    workflow_done = plan_done and outcome_contract_complete and bool(outcome.get("terminal"))

    required: List[str] = []
    if failed_gates:
        required.append("Resolve failed measurement evidence before any build, splice, release, or completion claim.")
    if assurance.get("level") == "blocked":
        required.extend(str(item) for item in assurance.get("blockers") or [])
    if not selected_resources:
        required.append("Select resources that cover the requested hardware capabilities.")
    if procurement.get("within_budget") is False:
        required.append("Bring procurement inside the stated budget.")
    for gate in open_gates[:8]:
        if gate.get("prompt"):
            required.append(str(gate.get("prompt")))
    if not assurance.get("can_power_or_splice"):
        required.append("Reach authority-ready state before first power or physical splice.")
    if plan_done and not outcome.get("recorded"):
        required.append("Record the build/repair/reuse outcome using the hardware outcome contract.")
    elif outcome.get("recorded") and not outcome_contract_complete:
        missing = [key for key, present in outcome_fields.items() if not present]
        if missing:
            required.append(f"Complete outcome fields: {', '.join(missing)}.")

    if workflow_done:
        state = "workflow_complete"
    elif plan_done:
        state = "plan_complete_awaiting_outcome"
    elif failed_gates or assurance.get("level") == "blocked":
        state = "blocked"
    elif open_gates:
        state = "evidence_required"
    else:
        state = "planning_required"

    return {
        "schema_version": "hardware_plan_completion.v1",
        "state": state,
        "plan_done": plan_done,
        "workflow_done": workflow_done,
        "outcome_recorded": bool(outcome.get("recorded")),
        "outcome_contract_complete": outcome_contract_complete,
        "outcome_decision": outcome.get("decision"),
        "open_gate_count": len(open_gates),
        "failed_gate_count": len(failed_gates),
        "current_stage": execution_package.get("current_stage"),
        "completion_state": execution_package.get("completion_state"),
        "required_before_done": _dedupe(required)[:12],
        "done_definition": {
            "plan_done": "resources selected, required evidence closed, authority permits first power/splice",
            "workflow_done": "plan_done plus terminal build/repair/reuse outcome recorded with the required learning fields",
        },
    }


def _production_repair_authority_contract(
    *,
    assurance: Dict[str, Any],
    completion_contract: Dict[str, Any],
    evidence_gates: Sequence[Dict[str, Any]],
    context: Dict[str, Any],
    selected_resources: Sequence[Dict[str, Any]],
    resource_strategy: Dict[str, Any],
    build_splice_plan: Dict[str, Any],
    payload: Dict[str, Any],
    goal: str,
) -> Dict[str, Any]:
    hazard_profile = _production_hazard_profile(
        payload=payload,
        context=context,
        selected_resources=selected_resources,
        resource_strategy=resource_strategy,
        evidence_gates=evidence_gates,
    )
    measurement_context = context.get("measurements") if isinstance(context.get("measurements"), dict) else {}
    measurements = [row for row in measurement_context.get("measurements") or [] if isinstance(row, dict)]
    passed_categories = {
        str(category)
        for measurement in measurements
        if measurement.get("passed") and not measurement.get("failed")
        for category in measurement.get("categories") or []
    }
    provenance = _production_measurement_provenance(measurements)
    failed_measurements = [measurement for measurement in measurements if measurement.get("failed")]
    failed_gates = [
        gate for gate in evidence_gates
        if isinstance(gate, dict) and str(gate.get("status") or "") == "failed"
    ]
    open_gates = [
        gate for gate in evidence_gates
        if isinstance(gate, dict) and str(gate.get("status", "open")) not in {"closed", "pass"}
    ]
    authority = context.get("authority") if isinstance(context.get("authority"), dict) else {}
    outcome = _outcome_execution_summary(context)
    latest_outcome = outcome.get("latest") if isinstance(outcome.get("latest"), dict) else {}
    missing_measurement_categories = sorted(PRODUCTION_REQUIRED_MEASUREMENT_CATEGORIES - passed_categories)
    missing_provenance_categories = sorted(PRODUCTION_REQUIRED_MEASUREMENT_CATEGORIES - set(provenance.get("trusted_categories") or []))
    domain_authority = _production_domain_authority_matrix(
        payload=payload,
        context=context,
        selected_resources=selected_resources,
        resource_strategy=resource_strategy,
        hazard_profile=hazard_profile,
        completion_contract=completion_contract,
        authority=authority,
        passed_categories=passed_categories,
        trusted_categories=set(provenance.get("trusted_categories") or []),
        latest_outcome=latest_outcome,
        open_gate_count=len(open_gates),
        failed_evidence_count=len(failed_measurements) + len(failed_gates),
    )
    release_manifest = _production_release_manifest(
        payload=payload,
        context=context,
        selected_resources=selected_resources,
        measurements=measurements,
        latest_outcome=latest_outcome,
        domain_authority=domain_authority,
        measurement_provenance=provenance,
    )
    blockers: List[str] = []
    requirements: List[str] = []

    if not selected_resources:
        blockers.append("No selected resources are available for production repair authority.")
    if not assurance.get("can_power_or_splice"):
        blockers.append("The plan is not authority-ready for first power or splice.")
    if not completion_contract.get("workflow_done"):
        blockers.append("A terminal successful outcome is not fully recorded.")
    if str(authority.get("repair_authority_status") or "") != "authoritative_low_risk":
        blockers.append("Repair authority is not authoritative_low_risk.")
    if hazard_profile.get("unsupported_for_production_authority") and not domain_authority.get("global_authorized"):
        blockers.append("The hazard profile is outside production repair authority scope.")
        requirements.extend(hazard_profile.get("clearance_requirements") or [])
    if failed_measurements or failed_gates:
        blockers.append("Failed measurement evidence blocks production repair authority.")
    if open_gates:
        blockers.append("Open evidence gates remain.")
        requirements.extend(str(gate.get("prompt")) for gate in open_gates[:8] if gate.get("prompt"))
    if missing_measurement_categories:
        blockers.append("Required production measurement categories are missing.")
        requirements.extend(f"Record passing {category} evidence." for category in missing_measurement_categories)
    if missing_provenance_categories:
        blockers.append("Required production measurements lack trusted provenance.")
        requirements.extend(f"Attach trusted provenance for {category} measurement evidence." for category in missing_provenance_categories)
    if provenance.get("missing_artifact_categories"):
        blockers.append("Required production measurements lack audit artifacts.")
        requirements.extend(f"Attach evidence_uri/artifact_uri for {category} measurement evidence." for category in provenance.get("missing_artifact_categories") or [])
    if not bool(latest_outcome.get("output_function_verified")):
        blockers.append("Output function is not verified in the terminal outcome.")
        requirements.append("Record output_function_verified=true in the terminal outcome.")
    if not _positive_result(latest_outcome.get("first_power_result")):
        blockers.append("First-power result is not recorded as passing.")
        requirements.append("Record first_power_result=pass under current limit.")
    if not (_positive_result(latest_outcome.get("thermal_result")) or "thermal" in passed_categories):
        blockers.append("Thermal result is not recorded as passing.")
        requirements.append("Record thermal_result=normal or equivalent passing thermal measurement.")
    if not (latest_outcome.get("evidence_uri") or latest_outcome.get("artifact_uri") or latest_outcome.get("test_report_uri")):
        blockers.append("Terminal outcome lacks an audit artifact URI.")
        requirements.append("Attach outcome evidence_uri, artifact_uri, or test_report_uri.")
    if domain_authority.get("blocking_lane_count"):
        blockers.append("One or more production authority lanes are not authorized.")
        requirements.extend(domain_authority.get("requirements") or [])
    if not release_manifest.get("complete"):
        blockers.append("Production release manifest is incomplete.")
        requirements.extend(release_manifest.get("missing_requirements") or [])
    arbitrary_trust = _arbitrary_board_trust_from_context(context)
    if arbitrary_trust and arbitrary_trust.get("level") != "production_release_candidate":
        blockers.append("Arbitrary-board trust assessment is not production_release_candidate.")
        requirements.extend(arbitrary_trust.get("blocking_gaps") or [])

    authorized = not blockers
    authority_casefile = _production_authority_casefile(
        authorized=authorized,
        selected_resources=selected_resources,
        assurance=assurance,
        authority=authority,
        hazard_profile=hazard_profile,
        evidence_gates=evidence_gates,
        open_gates=open_gates,
        failed_gates=failed_gates,
        measurements=measurements,
        failed_measurements=failed_measurements,
        passed_categories=passed_categories,
        missing_measurement_categories=missing_measurement_categories,
        missing_provenance_categories=missing_provenance_categories,
        provenance=provenance,
        completion_contract=completion_contract,
        outcome=outcome,
        latest_outcome=latest_outcome,
        domain_authority=domain_authority,
        release_manifest=release_manifest,
        arbitrary_trust=arbitrary_trust,
        blockers=blockers,
        requirements=requirements,
    )
    decision = _production_authorized_decision(domain_authority) if authorized else (
        "blocked_by_hazard_scope" if hazard_profile.get("unsupported_for_production_authority") else "not_authorized_evidence_required"
    )
    scope = _production_authority_scope(domain_authority) if authorized else "production_repair_authority_candidate"
    return {
        "schema_version": "production_repair_authority.v1",
        "authorized": authorized,
        "decision": decision,
        "level": "production_repair_authority" if authorized else "advisory_or_blocked",
        "scope": scope,
        "goal": goal,
        "hazard_profile": hazard_profile,
        "domain_authority": domain_authority,
        "measurement_requirements": {
            "required_categories": sorted(PRODUCTION_REQUIRED_MEASUREMENT_CATEGORIES),
            "passed_categories": sorted(passed_categories),
            "missing_categories": missing_measurement_categories,
            "failed_measurement_count": len(failed_measurements),
        },
        "measurement_provenance": provenance,
        "release_manifest": release_manifest,
        "authority_casefile": authority_casefile,
        "outcome_requirements": {
            "workflow_done": bool(completion_contract.get("workflow_done")),
            "decision": outcome.get("decision"),
            "output_function_verified": bool(latest_outcome.get("output_function_verified")),
            "first_power_result": latest_outcome.get("first_power_result"),
            "thermal_result": latest_outcome.get("thermal_result"),
            "evidence_uri_present": bool(latest_outcome.get("evidence_uri") or latest_outcome.get("artifact_uri") or latest_outcome.get("test_report_uri")),
        },
        "blockers": _dedupe(blockers)[:12],
        "requirements": _dedupe(requirements)[:14],
        "claim_boundary": (
            "Authorized only for the measured resources, relevant domain lanes, and terminal outcome recorded in this plan."
            if authorized
            else "Not production-authorized; use as advisory planning until every blocker is closed."
        ),
        "model_policy": {
            "llm_can_add_hazard_candidates": True,
            "llm_can_clear_hazards": False,
            "release_decision_is_deterministic": True,
        },
    }


def _production_hazard_profile(
    *,
    payload: Dict[str, Any],
    context: Dict[str, Any],
    selected_resources: Sequence[Dict[str, Any]],
    resource_strategy: Dict[str, Any],
    evidence_gates: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    signals: List[Dict[str, Any]] = []
    clearance_requirements: List[str] = []
    energy_domain = "low_voltage_dc" if selected_resources else "unknown"

    def add_signal(
        hazard_id: str,
        *,
        source: str,
        severity: str = "review",
        unsupported: bool = False,
        evidence: Any = None,
        requirement: Optional[str] = None,
    ) -> None:
        signals.append(
            {
                "hazard_id": _safe_id(hazard_id),
                "source": source,
                "severity": severity,
                "unsupported_for_production_authority": bool(unsupported),
                "evidence": evidence,
            }
        )
        if requirement:
            clearance_requirements.append(requirement)

    for profile in _structured_hazard_profiles(payload, context):
        profile_domain = str(profile.get("energy_domain") or "").strip()
        if profile_domain:
            energy_domain = profile_domain
        for hazard in profile.get("hazards") or profile.get("risk_flags") or []:
            hazard_id = ""
            severity = "review"
            unsupported = False
            requirement = None
            if isinstance(hazard, dict):
                hazard_id = str(hazard.get("hazard_id") or hazard.get("id") or hazard.get("type") or hazard.get("name") or "").strip()
                severity = str(hazard.get("severity") or hazard.get("level") or "review")
                unsupported = bool(
                    hazard.get("unsupported_for_production_authority")
                    or hazard.get("hard_stop")
                    or hazard_id in PRODUCTION_UNSUPPORTED_HAZARD_IDS
                    or severity in {"hard_stop", "critical", "unsupported"}
                )
                requirement = hazard.get("clearance_requires") or hazard.get("requires")
            else:
                hazard_id = str(hazard).strip()
                unsupported = hazard_id in PRODUCTION_UNSUPPORTED_HAZARD_IDS
            if hazard_id:
                add_signal(
                    hazard_id,
                    source="structured_hazard_profile",
                    severity=severity,
                    unsupported=unsupported,
                    evidence=hazard,
                    requirement=", ".join(str(item) for item in requirement) if isinstance(requirement, list) else requirement,
                )

    for resource in selected_resources:
        if not isinstance(resource, dict):
            continue
        caps = {str(cap).lower() for cap in resource.get("capabilities") or []}
        unsupported_caps = sorted(caps & PRODUCTION_UNSUPPORTED_CAPABILITIES)
        if unsupported_caps:
            energy_domain = "unsupported_energy_domain"
            add_signal(
                "unsupported_resource_capability",
                source=f"selected_resource:{resource.get('resource_id')}",
                severity="unsupported",
                unsupported=True,
                evidence={"resource_id": resource.get("resource_id"), "capabilities": unsupported_caps},
                requirement="Move this resource to a separate specialist safety workflow.",
            )
        status = str(resource.get("status") or "").lower()
        if status in {"unsafe_hold", "blocked_failed_evidence"}:
            add_signal(
                "selected_resource_blocked",
                source=f"selected_resource:{resource.get('resource_id')}",
                severity="critical",
                unsupported=True,
                evidence={"resource_id": resource.get("resource_id"), "status": status},
                requirement="Resolve or remove blocked selected resources.",
            )

    for resource in resource_strategy.get("blocked_resources") or []:
        if not isinstance(resource, dict):
            continue
        add_signal(
            "blocked_resource_present",
            source=f"resource_strategy:{resource.get('resource_id')}",
            severity="critical",
            unsupported=True,
            evidence={"resource_id": resource.get("resource_id"), "status": resource.get("status")},
            requirement="Remove blocked resources from production-authority scope.",
        )

    for gate in evidence_gates:
        if not isinstance(gate, dict):
            continue
        if str(gate.get("type") or "") == "safety" or str(gate.get("status") or "") in {"failed", "blocked"}:
            add_signal(
                "open_or_failed_safety_gate",
                source=str(gate.get("source") or "evidence_gate"),
                severity="critical",
                unsupported=True,
                evidence={"gate_id": gate.get("gate_id"), "status": gate.get("status"), "prompt": gate.get("prompt")},
                requirement="Close failed, blocked, or safety gates before production authority.",
            )

    unsupported = any(signal.get("unsupported_for_production_authority") for signal in signals)
    return {
        "schema_version": "hardware_hazard_profile.v1",
        "energy_domain": energy_domain,
        "unsupported_for_production_authority": unsupported,
        "hazards": signals,
        "clearance_requirements": _dedupe(clearance_requirements)[:12],
        "source_policy": {
            "structured_sources": ["resource.capabilities", "resource.status", "resource_strategy.blocked_resources", "evidence_gates", "hazard_profile"],
            "raw_text_release_logic": False,
            "llm_outputs_must_be_structured_hazard_candidates": True,
        },
    }


def _production_measurement_provenance(measurements: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    trusted_categories = set()
    artifact_categories = set()
    calibration_ok = {"valid", "verified", "current", "not_required", "not required", "factory_current"}
    for measurement in measurements:
        if not isinstance(measurement, dict) or not measurement.get("passed") or measurement.get("failed"):
            continue
        categories = sorted(str(item) for item in measurement.get("categories") or [])
        if not categories:
            continue
        has_instrument = bool(measurement.get("instrument_id") or measurement.get("instrument_type"))
        has_calibration = str(measurement.get("calibration_status") or "").strip().lower() in calibration_ok
        has_timestamp = bool(measurement.get("recorded_at"))
        has_operator = bool(measurement.get("operator_id"))
        has_artifact = bool(measurement.get("evidence_uri"))
        trusted = has_instrument and has_calibration and has_timestamp and has_operator
        if trusted:
            trusted_categories.update(categories)
        if trusted and has_artifact:
            artifact_categories.update(categories)
        rows.append(
            {
                "measurement_id": measurement.get("measurement_id"),
                "categories": categories,
                "trusted": trusted,
                "instrument_id_present": bool(measurement.get("instrument_id")),
                "instrument_type_present": bool(measurement.get("instrument_type")),
                "calibration_status": measurement.get("calibration_status"),
                "recorded_at_present": has_timestamp,
                "operator_id_present": has_operator,
                "evidence_uri_present": has_artifact,
            }
        )
    missing_categories = sorted(PRODUCTION_REQUIRED_MEASUREMENT_CATEGORIES - trusted_categories)
    missing_artifact_categories = sorted(PRODUCTION_REQUIRED_MEASUREMENT_CATEGORIES - artifact_categories)
    return {
        "schema_version": "production_measurement_provenance.v1",
        "trusted_categories": sorted(trusted_categories),
        "missing_trusted_categories": missing_categories,
        "artifact_categories": sorted(artifact_categories),
        "missing_artifact_categories": missing_artifact_categories,
        "trusted_measurement_count": len([row for row in rows if row.get("trusted")]),
        "measurement_count": len(rows),
        "requirements": [
            "instrument_id or instrument_type",
            "calibration_status valid/verified/current/not_required",
            "recorded_at timestamp",
            "operator_id or captured_by",
            "evidence_uri or artifact_uri for audit trail",
        ],
        "measurements": rows[:40],
    }


def _production_release_manifest(
    *,
    payload: Dict[str, Any],
    context: Dict[str, Any],
    selected_resources: Sequence[Dict[str, Any]],
    measurements: Sequence[Dict[str, Any]],
    latest_outcome: Dict[str, Any],
    domain_authority: Dict[str, Any],
    measurement_provenance: Dict[str, Any],
) -> Dict[str, Any]:
    manifest = _first_release_manifest(payload, context, latest_outcome)
    selected_ids = [
        str(resource.get("resource_id"))
        for resource in selected_resources
        if isinstance(resource, dict) and resource.get("resource_id")
    ]
    manifest_ids = _list(
        manifest.get("selected_resource_ids")
        or manifest.get("selected_resource_ids_used")
        or manifest.get("resource_ids")
    )
    artifact_uris = _dedupe(
        [
            *_list(manifest.get("artifact_uris")),
            *_list(manifest.get("evidence_uris")),
            *_list(manifest.get("test_report_uris")),
            *([str(manifest.get("test_report_uri"))] if manifest.get("test_report_uri") else []),
            *([str(latest_outcome.get("evidence_uri"))] if latest_outcome.get("evidence_uri") else []),
            *([str(latest_outcome.get("artifact_uri"))] if latest_outcome.get("artifact_uri") else []),
        ]
    )
    measurement_artifact_count = len(
        [
            measurement
            for measurement in measurements
            if isinstance(measurement, dict)
            and measurement.get("passed")
            and not measurement.get("failed")
            and measurement.get("evidence_uri")
        ]
    )
    release_operator = str(
        manifest.get("released_by")
        or manifest.get("approved_by")
        or manifest.get("release_operator_id")
        or manifest.get("operator_id")
        or ""
    ).strip()
    released_at = str(manifest.get("released_at") or manifest.get("approved_at") or manifest.get("recorded_at") or "").strip()
    scope_statement = str(manifest.get("scope_statement") or manifest.get("scope") or manifest.get("claim_scope") or "").strip()
    release_id = str(manifest.get("release_id") or manifest.get("manifest_id") or manifest.get("authority_id") or "").strip()
    acceptance_reviewed = _truthy(
        manifest.get("acceptance_reviewed")
        or manifest.get("acceptance_checklist_complete")
        or manifest.get("release_review_complete")
        or manifest.get("checklist_completed")
    )
    repeatability_count = _safe_int(
        manifest.get("repeatability_count")
        or manifest.get("sample_count")
        or manifest.get("validated_unit_count")
        or 0,
        0,
    )
    missing: List[str] = []
    if not manifest:
        missing.append("Attach production_release or release_manifest.")
    if not release_id:
        missing.append("Assign a release_id or manifest_id.")
    if not release_operator:
        missing.append("Record released_by, approved_by, or release_operator_id.")
    if not released_at:
        missing.append("Record released_at or approved_at timestamp.")
    if not scope_statement:
        missing.append("Record production release scope statement.")
    if not artifact_uris:
        missing.append("Attach release artifact URI or test report URI.")
    if measurement_provenance.get("missing_artifact_categories"):
        missing.append("Attach artifact-backed measurement evidence for every required production category.")
    if measurement_artifact_count < len(PRODUCTION_REQUIRED_MEASUREMENT_CATEGORIES):
        missing.append("Attach enough measurement artifacts to cover resistance, continuity, voltage, current, and thermal evidence.")
    if selected_ids and set(manifest_ids) != set(selected_ids):
        missing.append("Release manifest selected_resource_ids must exactly match selected production resources.")
    if not acceptance_reviewed:
        missing.append("Mark acceptance_reviewed or acceptance_checklist_complete true.")
    if repeatability_count < 1:
        missing.append("Record repeatability_count/sample_count/validated_unit_count >= 1.")

    return {
        "schema_version": "production_release_manifest.v1",
        "available": bool(manifest),
        "complete": bool(manifest) and not missing,
        "release_id": release_id or None,
        "release_operator_present": bool(release_operator),
        "released_at_present": bool(released_at),
        "scope_statement_present": bool(scope_statement),
        "acceptance_reviewed": acceptance_reviewed,
        "repeatability_count": repeatability_count,
        "selected_resource_ids": selected_ids,
        "manifest_resource_ids": manifest_ids,
        "selected_resource_ids_match": set(manifest_ids) == set(selected_ids) if selected_ids else False,
        "artifact_count": len(artifact_uris),
        "measurement_artifact_count": measurement_artifact_count,
        "primary_production_lane": domain_authority.get("primary_lane"),
        "missing_requirements": _dedupe(missing)[:14],
        "claim_boundary": "Release manifest is an audit contract; it does not expand scope beyond measured resources and authorized domain lanes.",
    }


def _arbitrary_board_trust_from_context(context: Dict[str, Any]) -> Dict[str, Any]:
    analysis = context.get("analysis") if isinstance(context.get("analysis"), dict) else {}
    trust = analysis.get("arbitrary_board_trust_assessment")
    return trust if isinstance(trust, dict) and trust else {}


def _production_authority_casefile(
    *,
    authorized: bool,
    selected_resources: Sequence[Dict[str, Any]],
    assurance: Dict[str, Any],
    authority: Dict[str, Any],
    hazard_profile: Dict[str, Any],
    evidence_gates: Sequence[Dict[str, Any]],
    open_gates: Sequence[Dict[str, Any]],
    failed_gates: Sequence[Dict[str, Any]],
    measurements: Sequence[Dict[str, Any]],
    failed_measurements: Sequence[Dict[str, Any]],
    passed_categories: set,
    missing_measurement_categories: Sequence[str],
    missing_provenance_categories: Sequence[str],
    provenance: Dict[str, Any],
    completion_contract: Dict[str, Any],
    outcome: Dict[str, Any],
    latest_outcome: Dict[str, Any],
    domain_authority: Dict[str, Any],
    release_manifest: Dict[str, Any],
    arbitrary_trust: Dict[str, Any],
    blockers: Sequence[str],
    requirements: Sequence[str],
) -> Dict[str, Any]:
    selected_ids = [
        str(resource.get("resource_id"))
        for resource in selected_resources
        if isinstance(resource, dict) and resource.get("resource_id")
    ]
    claims = [
        _production_casefile_claim(
            "selected_resource_scope",
            "Selected resources are explicit and scoped.",
            passed=bool(selected_ids),
            evidence=[f"selected_resource:{resource_id}" for resource_id in selected_ids],
            gaps=[] if selected_ids else ["Select at least one production-scope resource."],
            details={"selected_resource_ids": selected_ids},
        ),
        _production_casefile_claim(
            "safety_authority_low_risk",
            "Safety authority permits first power or splice in the measured low-risk scope.",
            passed=bool(assurance.get("can_power_or_splice"))
            and str(authority.get("repair_authority_status") or "") == "authoritative_low_risk"
            and not hazard_profile.get("unsupported_for_production_authority"),
            evidence=[
                f"assurance_level:{assurance.get('level')}",
                f"repair_authority_status:{authority.get('repair_authority_status')}",
                f"hazard_energy_domain:{hazard_profile.get('energy_domain')}",
            ],
            gaps=_dedupe(
                [
                    *[str(item) for item in assurance.get("blockers") or []],
                    *[str(item) for item in hazard_profile.get("clearance_requirements") or []],
                    "Repair authority must be authoritative_low_risk."
                    if str(authority.get("repair_authority_status") or "") != "authoritative_low_risk"
                    else "",
                    "The plan must permit first power or splice."
                    if not assurance.get("can_power_or_splice")
                    else "",
                ]
            ),
            details={
                "assurance_level": assurance.get("level"),
                "repair_authority_status": authority.get("repair_authority_status"),
                "unsupported_hazard": bool(hazard_profile.get("unsupported_for_production_authority")),
            },
        ),
        _production_casefile_claim(
            "evidence_gates_closed",
            "No open or failed evidence gates remain.",
            passed=not open_gates and not failed_gates,
            evidence=[
                f"evidence_gate_count:{len(evidence_gates)}",
                f"open_gate_count:{len(open_gates)}",
                f"failed_gate_count:{len(failed_gates)}",
            ],
            gaps=[str(gate.get("prompt")) for gate in open_gates[:8] if isinstance(gate, dict) and gate.get("prompt")]
            + [str(gate.get("prompt")) for gate in failed_gates[:8] if isinstance(gate, dict) and gate.get("prompt")],
            details={
                "open_gate_ids": [gate.get("gate_id") for gate in open_gates[:12] if isinstance(gate, dict)],
                "failed_gate_ids": [gate.get("gate_id") for gate in failed_gates[:12] if isinstance(gate, dict)],
            },
        ),
        _production_casefile_claim(
            "required_measurement_coverage",
            "Required production measurement categories are present and passing.",
            passed=not missing_measurement_categories and not failed_measurements,
            evidence=[
                f"passed_category:{category}"
                for category in sorted(passed_categories)
            ],
            gaps=[
                *[f"Record passing {category} evidence." for category in missing_measurement_categories],
                *[f"Resolve failed measurement {measurement.get('measurement_id') or measurement.get('target')}." for measurement in failed_measurements[:8]],
            ],
            details={
                "required_categories": sorted(PRODUCTION_REQUIRED_MEASUREMENT_CATEGORIES),
                "passed_categories": sorted(passed_categories),
                "failed_measurement_count": len(failed_measurements),
            },
        ),
        _production_casefile_claim(
            "measurement_provenance_auditable",
            "Required measurements have trusted operator, instrument, calibration, timestamp, and audit artifacts.",
            passed=not missing_provenance_categories and not provenance.get("missing_artifact_categories"),
            evidence=[
                f"trusted_category:{category}"
                for category in provenance.get("trusted_categories") or []
            ]
            + [
                f"artifact_category:{category}"
                for category in provenance.get("artifact_categories") or []
            ],
            gaps=[
                *[f"Attach trusted provenance for {category}." for category in missing_provenance_categories],
                *[f"Attach artifact URI for {category}." for category in provenance.get("missing_artifact_categories") or []],
            ],
            details={
                "trusted_measurement_count": provenance.get("trusted_measurement_count"),
                "measurement_count": provenance.get("measurement_count"),
                "missing_artifact_categories": provenance.get("missing_artifact_categories") or [],
            },
        ),
        _production_casefile_claim(
            "terminal_outcome_verified",
            "Terminal outcome verifies output function, first power, and thermal behavior.",
            passed=bool(completion_contract.get("workflow_done"))
            and bool(latest_outcome.get("output_function_verified"))
            and _positive_result(latest_outcome.get("first_power_result"))
            and (_positive_result(latest_outcome.get("thermal_result")) or "thermal" in passed_categories)
            and bool(latest_outcome.get("evidence_uri") or latest_outcome.get("artifact_uri") or latest_outcome.get("test_report_uri")),
            evidence=[
                f"completion_state:{completion_contract.get('state')}",
                f"outcome_decision:{outcome.get('decision')}",
                f"output_function_verified:{bool(latest_outcome.get('output_function_verified'))}",
                f"first_power_result:{latest_outcome.get('first_power_result')}",
                f"thermal_result:{latest_outcome.get('thermal_result')}",
                f"outcome_artifact_uri_present:{bool(latest_outcome.get('evidence_uri') or latest_outcome.get('artifact_uri') or latest_outcome.get('test_report_uri'))}",
            ],
            gaps=_dedupe(
                [
                    "Complete workflow outcome contract." if not completion_contract.get("workflow_done") else "",
                    "Record output_function_verified=true." if not bool(latest_outcome.get("output_function_verified")) else "",
                    "Record first_power_result=pass." if not _positive_result(latest_outcome.get("first_power_result")) else "",
                    "Record thermal_result=normal/pass or passing thermal measurement."
                    if not (_positive_result(latest_outcome.get("thermal_result")) or "thermal" in passed_categories)
                    else "",
                    "Attach outcome evidence_uri, artifact_uri, or test_report_uri."
                    if not (latest_outcome.get("evidence_uri") or latest_outcome.get("artifact_uri") or latest_outcome.get("test_report_uri"))
                    else "",
                ]
            ),
            details={"outcome_required_fields_present": outcome.get("required_fields_present") or {}},
        ),
        _production_casefile_claim(
            "domain_authority_authorized",
            "Relevant production authority lane is authorized.",
            passed=not domain_authority.get("blocking_lane_count"),
            evidence=[
                f"{lane.get('lane_id')}:{lane.get('decision')}"
                for lane in domain_authority.get("lanes") or []
                if isinstance(lane, dict) and lane.get("relevant")
            ],
            gaps=domain_authority.get("requirements") or [],
            details={
                "primary_lane": domain_authority.get("primary_lane"),
                "blocking_lane_count": domain_authority.get("blocking_lane_count"),
            },
        ),
        _production_casefile_claim(
            "release_manifest_complete",
            "Production release manifest is complete and matches the selected resources.",
            passed=bool(release_manifest.get("complete")),
            evidence=[
                f"release_id:{release_manifest.get('release_id')}",
                f"resource_ids_match:{release_manifest.get('selected_resource_ids_match')}",
                f"artifact_count:{release_manifest.get('artifact_count')}",
            ],
            gaps=release_manifest.get("missing_requirements") or [],
            details={
                "available": release_manifest.get("available"),
                "selected_resource_ids": release_manifest.get("selected_resource_ids") or [],
                "manifest_resource_ids": release_manifest.get("manifest_resource_ids") or [],
            },
        ),
    ]
    if arbitrary_trust:
        claims.append(
            _production_casefile_claim(
                "arbitrary_board_trust_release_candidate",
                "Arbitrary-board workflow reaches production-release candidate level.",
                passed=arbitrary_trust.get("level") == "production_release_candidate",
                evidence=[
                    f"trust_level:{arbitrary_trust.get('level')}",
                    f"trust_score:{arbitrary_trust.get('score')}",
                    f"production_readiness_score:{arbitrary_trust.get('production_readiness_score')}",
                ],
                gaps=arbitrary_trust.get("blocking_gaps") or [],
                details={
                    "trust_dimensions": arbitrary_trust.get("trust_dimensions") or {},
                    "remaining_unknowns": arbitrary_trust.get("remaining_unknowns") or [],
                },
            )
        )
    blocked_claims = [claim for claim in claims if claim.get("status") == "blocked"]
    passed_claims = [claim for claim in claims if claim.get("status") == "pass"]
    caution_claims = [claim for claim in claims if claim.get("status") == "caution"]
    return {
        "schema_version": "production_authority_casefile.v1",
        "status": "release_ready" if authorized else "evidence_required",
        "claim_count": len(claims),
        "passed_claim_count": len(passed_claims),
        "blocked_claim_count": len(blocked_claims),
        "caution_claim_count": len(caution_claims),
        "claims": claims,
        "top_blockers": _dedupe(blockers)[:8],
        "top_requirements": _dedupe(requirements)[:10],
        "cannot_claim": []
        if authorized
        else [
            "production repair authority",
            "unbounded reuse beyond measured resources",
            "safety clearance outside recorded hazard domain",
        ],
        "reviewer_summary": (
            "Production casefile is release-ready; every required claim has evidence."
            if authorized
            else f"Production casefile has {len(blocked_claims)} blocked claim(s); keep this advisory until gaps are closed."
        ),
        "claim_boundary": "Casefile explains the deterministic release decision; it is not an independent authorization path.",
    }


def _production_casefile_claim(
    claim_id: str,
    statement: str,
    *,
    passed: bool,
    evidence: Sequence[Any],
    gaps: Sequence[Any],
    details: Dict[str, Any],
) -> Dict[str, Any]:
    clean_evidence = _dedupe(str(item) for item in evidence)[:12]
    clean_gaps = _dedupe(str(item) for item in gaps)[:12]
    return {
        "claim_id": claim_id,
        "status": "pass" if passed else "blocked" if clean_gaps else "caution",
        "statement": statement,
        "evidence": clean_evidence,
        "gaps": clean_gaps,
        "details": details,
    }


def _first_release_manifest(
    payload: Dict[str, Any],
    context: Dict[str, Any],
    latest_outcome: Dict[str, Any],
) -> Dict[str, Any]:
    analysis = context.get("analysis") if isinstance(context.get("analysis"), dict) else {}
    outcome_evidence = latest_outcome.get("production_evidence") if isinstance(latest_outcome.get("production_evidence"), dict) else {}
    for root in [payload, analysis, latest_outcome, outcome_evidence]:
        if not isinstance(root, dict):
            continue
        for key in [
            "production_release",
            "production_release_manifest",
            "release_manifest",
            "release_package",
            "production_evidence",
        ]:
            value = root.get(key)
            if isinstance(value, dict) and value:
                return value
    return {}


def _production_domain_authority_matrix(
    *,
    payload: Dict[str, Any],
    context: Dict[str, Any],
    selected_resources: Sequence[Dict[str, Any]],
    resource_strategy: Dict[str, Any],
    hazard_profile: Dict[str, Any],
    completion_contract: Dict[str, Any],
    authority: Dict[str, Any],
    passed_categories: set,
    trusted_categories: set,
    latest_outcome: Dict[str, Any],
    open_gate_count: int,
    failed_evidence_count: int,
) -> Dict[str, Any]:
    evidence = _production_domain_evidence(
        payload=payload,
        context=context,
        selected_resources=selected_resources,
        resource_strategy=resource_strategy,
        hazard_profile=hazard_profile,
    )
    common_ready = (
        bool(completion_contract.get("workflow_done"))
        and str(authority.get("repair_authority_status") or "") == "authoritative_low_risk"
        and open_gate_count == 0
        and failed_evidence_count == 0
        and PRODUCTION_REQUIRED_MEASUREMENT_CATEGORIES.issubset(passed_categories)
        and PRODUCTION_REQUIRED_MEASUREMENT_CATEGORIES.issubset(trusted_categories)
        and bool(latest_outcome.get("output_function_verified"))
        and _positive_result(latest_outcome.get("first_power_result"))
        and (_positive_result(latest_outcome.get("thermal_result")) or "thermal" in passed_categories)
    )
    caps = set(evidence["capabilities"])
    hazard_ids = set(evidence["hazard_ids"])
    lanes: List[Dict[str, Any]] = []
    motor_relevant = bool(caps & {"motor_or_load", "fan_or_pump", "actuator_driver", "mechanical_motion"})
    battery_relevant = bool(caps & {"battery", "battery_pack"} or hazard_ids & {"battery_pack", "damaged_battery_pack", "damaged_lithium_pack"})
    mains_relevant = bool(caps & {"mains", "mains_voltage", "high_voltage", "hv"} or hazard_ids & {"mains_input", "mains_voltage", "high_voltage", "hv_capacitor", "crt_high_voltage", "microwave_high_voltage"})
    laser_relevant = bool(caps & {"laser"} or hazard_ids & {"laser_radiation"})

    low_voltage_relevant = bool(selected_resources) and not bool(
        battery_relevant or mains_relevant or laser_relevant
    )
    lanes.append(
        _production_lane(
            "low_voltage_dc_external",
            relevant=low_voltage_relevant,
            authorized=common_ready and not hazard_profile.get("unsupported_for_production_authority"),
            decision="authorized" if common_ready and not hazard_profile.get("unsupported_for_production_authority") else "evidence_required",
            requirements=[] if common_ready else [
                "Complete workflow outcome.",
                "Close all evidence gates.",
                "Attach trusted resistance, continuity, voltage, current, and thermal measurements.",
                "Record first-power, thermal, and output-function proof.",
            ],
            evidence=evidence,
        )
    )

    motor_ready = (
        common_ready
        and _positive_result(latest_outcome.get("stall_current_result"))
        and bool(latest_outcome.get("mechanical_guarding_verified"))
        and bool(latest_outcome.get("abnormal_current_stop_verified"))
    )
    lanes.append(
        _production_lane(
            "motor_mechanical_load",
            relevant=motor_relevant,
            authorized=motor_ready,
            decision="authorized" if motor_ready else "motor_load_evidence_required",
            requirements=[] if motor_ready else [
                "Record stall_current_result=pass or equivalent.",
                "Record mechanical_guarding_verified=true.",
                "Record abnormal_current_stop_verified=true.",
                "Verify wiring strain relief, load containment, and abnormal-current stop condition.",
            ],
            evidence=evidence,
        )
    )

    battery_specialist = _specialist_authority(payload, context, "battery_pack_lithium")
    battery_report = _specialist_authority_report(battery_specialist, "battery_pack_lithium")
    lanes.append(
        _production_lane(
            "battery_pack_lithium",
            relevant=battery_relevant,
            authorized=battery_relevant and common_ready and battery_report["authorized"],
            decision="authorized_by_specialist" if common_ready and battery_report["authorized"] else "specialist_authority_required",
            requirements=[] if common_ready and battery_report["authorized"] else [
                "Attach battery chemistry, cell count, BMS/protection, balance, charge/discharge, enclosure, and thermal-containment evidence.",
                "Attach specialist battery authority before production release.",
                *battery_report.get("missing_requirements", []),
            ],
            evidence={**evidence, "specialist_authority": battery_report},
        )
    )

    mains_specialist = _specialist_authority(payload, context, "mains_high_voltage")
    mains_report = _specialist_authority_report(mains_specialist, "mains_high_voltage")
    lanes.append(
        _production_lane(
            "mains_high_voltage",
            relevant=mains_relevant,
            authorized=mains_relevant and common_ready and mains_report["authorized"],
            decision="authorized_by_specialist" if common_ready and mains_report["authorized"] else "specialist_authority_required",
            requirements=[] if common_ready and mains_report["authorized"] else [
                "Attach isolation, discharge, earth-bond, leakage-current, fuse/protection, creepage/clearance, enclosure, and hipot/safety-test evidence.",
                "Attach specialist mains/high-voltage authority before production release.",
                *mains_report.get("missing_requirements", []),
            ],
            evidence={**evidence, "specialist_authority": mains_report},
        )
    )

    laser_specialist = _specialist_authority(payload, context, "laser_radiation")
    laser_report = _specialist_authority_report(laser_specialist, "laser_radiation")
    lanes.append(
        _production_lane(
            "laser_radiation",
            relevant=laser_relevant,
            authorized=laser_relevant and common_ready and laser_report["authorized"],
            decision="authorized_by_specialist" if common_ready and laser_report["authorized"] else "specialist_authority_required",
            requirements=[] if common_ready and laser_report["authorized"] else [
                "Attach laser class, optical containment, interlock, labeling, PPE, and exposure-limit evidence.",
                "Attach specialist laser/radiation authority before production release.",
                *laser_report.get("missing_requirements", []),
            ],
            evidence={**evidence, "specialist_authority": laser_report},
        )
    )

    relevant = [lane for lane in lanes if lane["relevant"]]
    blocking = [lane for lane in relevant if not lane["authorized"]]
    return {
        "schema_version": "production_domain_authority_matrix.v1",
        "global_authorized": bool(relevant) and not blocking,
        "primary_lane": _primary_production_lane(relevant),
        "relevant_lane_count": len(relevant),
        "blocking_lane_count": len(blocking),
        "requirements": _dedupe(
            requirement
            for lane in blocking
            for requirement in lane.get("requirements") or []
        )[:18],
        "lanes": lanes,
        "policy": {
            "all_relevant_lanes_must_authorize": True,
            "unsupported_domains_require_specialist_authority": True,
            "classification_uses_structured_semantics_not_regex": True,
        },
    }


def _production_lane(
    lane_id: str,
    *,
    relevant: bool,
    authorized: bool,
    decision: str,
    requirements: Sequence[str],
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "lane_id": lane_id,
        "relevant": bool(relevant),
        "authorized": bool(authorized) if relevant else False,
        "decision": decision if relevant else "not_applicable",
        "requirements": list(requirements) if relevant and not authorized else [],
        "evidence": evidence,
    }


def _production_domain_evidence(
    *,
    payload: Dict[str, Any],
    context: Dict[str, Any],
    selected_resources: Sequence[Dict[str, Any]],
    resource_strategy: Dict[str, Any],
    hazard_profile: Dict[str, Any],
) -> Dict[str, Any]:
    caps = {
        str(cap).lower()
        for resource in selected_resources
        if isinstance(resource, dict)
        for cap in resource.get("capabilities") or []
    }
    for resource in resource_strategy.get("blocked_resources") or []:
        if isinstance(resource, dict):
            caps.update(str(cap).lower() for cap in resource.get("capabilities") or [])
    hazard_ids = {
        str(signal.get("hazard_id") or "").lower()
        for signal in hazard_profile.get("hazards") or []
        if isinstance(signal, dict) and signal.get("hazard_id")
    }
    requested = str(
        payload.get("production_authority_domain")
        or payload.get("authority_domain")
        or payload.get("hardware_domain")
        or ""
    ).strip().lower()
    if requested:
        hazard_ids.add(requested)
    return {
        "capabilities": sorted(caps),
        "hazard_ids": sorted(hazard_ids),
        "energy_domain": hazard_profile.get("energy_domain"),
        "requested_domain": requested or None,
        "analysis_source": context.get("analysis_source"),
    }


def _specialist_authority(payload: Dict[str, Any], context: Dict[str, Any], lane_id: str) -> Dict[str, Any]:
    analysis = context.get("analysis") if isinstance(context.get("analysis"), dict) else {}
    for root in [payload, analysis]:
        value = root.get("specialist_authority") if isinstance(root, dict) else None
        if isinstance(value, dict):
            lane = value.get(lane_id) if isinstance(value.get(lane_id), dict) else None
            if lane:
                return lane
            if str(value.get("lane_id") or "") == lane_id:
                return value
    return {}


def _specialist_authorized(authority: Dict[str, Any]) -> bool:
    return _specialist_authority_report(authority, "").get("authorized") is True


def _specialist_authority_report(authority: Dict[str, Any], lane_id: str) -> Dict[str, Any]:
    status = str(authority.get("status") or "").strip().lower() if isinstance(authority, dict) else ""
    evidence_roots = _specialist_evidence_roots(authority)
    signed_by = str(authority.get("signed_by") or authority.get("authorized_by") or "").strip() if isinstance(authority, dict) else ""
    certificate_id = str(authority.get("certificate_id") or authority.get("authority_id") or "").strip() if isinstance(authority, dict) else ""
    issued_at = str(authority.get("issued_at") or authority.get("authorized_at") or authority.get("recorded_at") or "").strip() if isinstance(authority, dict) else ""
    missing: List[str] = []
    status_ok = status in SPECIALIST_AUTHORITY_ACCEPTED_STATUSES
    if not status_ok:
        missing.append("Attach specialist authority with status certified_release, authorized, or authority_ready.")
    if not signed_by:
        missing.append("Attach specialist authority signed_by or authorized_by.")
    if not certificate_id:
        missing.append("Attach specialist authority certificate_id or authority_id.")
    if not issued_at:
        missing.append("Attach specialist authority issued_at or authorized_at timestamp.")

    evidence_rows: List[Dict[str, Any]] = []
    for evidence_id, aliases, requirement in SPECIALIST_AUTHORITY_REQUIRED_EVIDENCE.get(lane_id, []):
        value = _specialist_evidence_value(evidence_roots, aliases)
        present = value is not None and str(value).strip() != ""
        passed = _positive_result(value)
        evidence_rows.append(
            {
                "evidence_id": evidence_id,
                "present": present,
                "passed": passed,
                "value": value,
            }
        )
        if not passed:
            missing.append(requirement)

    return {
        "lane_id": lane_id or None,
        "authorized": bool(authority) and status_ok and bool(signed_by) and bool(certificate_id) and bool(issued_at) and all(row["passed"] for row in evidence_rows),
        "status": status or None,
        "signed": bool(signed_by),
        "certificate_id_present": bool(certificate_id),
        "issued_at_present": bool(issued_at),
        "missing_requirements": _dedupe(missing)[:12],
        "evidence": evidence_rows,
    }


def _specialist_evidence_roots(authority: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(authority, dict):
        return []
    roots = [authority]
    for key in ["evidence", "evidence_summary", "verification", "test_results", "production_evidence"]:
        value = authority.get(key)
        if isinstance(value, dict):
            roots.append(value)
    return roots


def _specialist_evidence_value(roots: Sequence[Dict[str, Any]], aliases: Sequence[str]) -> Any:
    for root in roots:
        for alias in aliases:
            if alias in root:
                return root.get(alias)
    return None


def _production_authorized_decision(domain_authority: Dict[str, Any]) -> str:
    lane = str(domain_authority.get("primary_lane") or "")
    decisions = {
        "low_voltage_dc_external": "authorized_low_voltage_repair_release",
        "motor_mechanical_load": "authorized_motor_mechanical_load_release",
        "battery_pack_lithium": "authorized_battery_pack_lithium_specialist_release",
        "mains_high_voltage": "authorized_mains_high_voltage_specialist_release",
        "laser_radiation": "authorized_laser_radiation_specialist_release",
    }
    return decisions.get(lane, "authorized_production_repair_release")


def _production_authority_scope(domain_authority: Dict[str, Any]) -> str:
    lane = str(domain_authority.get("primary_lane") or "")
    scopes = {
        "low_voltage_dc_external": "measured_low_voltage_dc_external_module_repair_or_reuse",
        "motor_mechanical_load": "measured_low_voltage_motor_mechanical_load_repair_or_reuse",
        "battery_pack_lithium": "specialist_authorized_battery_pack_lithium_repair_or_reuse",
        "mains_high_voltage": "specialist_authorized_mains_high_voltage_repair_or_reuse",
        "laser_radiation": "specialist_authorized_laser_radiation_repair_or_reuse",
    }
    return scopes.get(lane, "measured_production_repair_or_reuse")


def _primary_production_lane(relevant_lanes: Sequence[Dict[str, Any]]) -> Optional[str]:
    for lane_id in ["mains_high_voltage", "battery_pack_lithium", "laser_radiation", "motor_mechanical_load", "low_voltage_dc_external"]:
        if any(lane.get("lane_id") == lane_id for lane in relevant_lanes):
            return lane_id
    return relevant_lanes[0].get("lane_id") if relevant_lanes else None


def _structured_hazard_profiles(payload: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    analysis = context.get("analysis") if isinstance(context.get("analysis"), dict) else {}
    profiles: List[Dict[str, Any]] = []
    for root in [payload, analysis]:
        if not isinstance(root, dict):
            continue
        for key in ["hazard_profile", "production_hazard_profile", "safety_profile"]:
            value = root.get(key)
            if isinstance(value, dict):
                profiles.append(value)
    return profiles


def _positive_result(value: Any) -> bool:
    if value is True:
        return True
    text = str(value or "").strip().lower()
    return text in {"pass", "passed", "ok", "normal", "verified", "success", "successful", "within_limit", "within limit"}


def _production_authority_requested(payload: Dict[str, Any]) -> bool:
    if payload.get("production_authority_required") is True:
        return True
    raw = str(
        payload.get("target_authority_level")
        or payload.get("authority_level")
        or payload.get("release_target")
        or ""
    ).strip().lower()
    return raw in {"production", "production_repair", "production_repair_authority", "release", "repair_release"}


def _functional_validation_protocol(
    *,
    selected_resources: Sequence[Dict[str, Any]],
    pin_contracts: Sequence[Dict[str, Any]],
    evidence_gates: Sequence[Dict[str, Any]],
    context: Dict[str, Any],
    outcome_summary: Dict[str, Any],
) -> Dict[str, Any]:
    caps = {
        str(cap)
        for resource in selected_resources
        if isinstance(resource, dict)
        for cap in resource.get("capabilities") or []
    }
    measurement_context = context.get("measurements") if isinstance(context.get("measurements"), dict) else {}
    measurements = [row for row in measurement_context.get("measurements") or [] if isinstance(row, dict)]
    latest_outcome = outcome_summary.get("latest") if isinstance(outcome_summary.get("latest"), dict) else {}
    items: List[Dict[str, Any]] = []

    def add(item_id: str, title: str, category: str, required: bool, evidence_terms: Sequence[str], instructions: Sequence[str]) -> None:
        matched_measurements = [
            row for row in measurements if _matches_any_term(_measurement_text(row), evidence_terms)
        ]
        matched_gates = [
            gate
            for gate in evidence_gates
            if isinstance(gate, dict) and _matches_any_term(str(gate.get("prompt") or "").lower(), evidence_terms)
        ]
        failed = any(row.get("failed") for row in matched_measurements) or any(str(gate.get("status") or "") == "failed" for gate in matched_gates)
        passed = any(row.get("passed") for row in matched_measurements) or any(str(gate.get("status") or "") in {"closed", "pass"} for gate in matched_gates)
        status = "failed" if failed else "passed" if passed else "open" if required else "optional"
        items.append(
            {
                "test_id": item_id,
                "title": title,
                "category": category,
                "required": required,
                "status": status,
                "evidence_terms": list(evidence_terms),
                "instructions": list(instructions),
                "matched_measurement_ids": [row.get("measurement_id") for row in matched_measurements[:6]],
                "matched_gate_ids": [gate.get("gate_id") for gate in matched_gates[:6]],
            }
        )

    add(
        "pre_power_no_short",
        "No-short pre-power check",
        "electrical_safety",
        True,
        ["no-short", "no short", "power to ground", "resistance"],
        ["Measure resistance between supply and ground before applying power."],
    )
    add(
        "ground_reference",
        "Ground/reference continuity",
        "electrical_safety",
        True,
        ["ground continuity", "shared ground", "connector ground"],
        ["Verify the connector ground and target ground are the same intended reference before signals."],
    )
    if "power" in caps or _any_contract_role(pin_contracts, {"power"}):
        add(
            "supply_voltage_current_limit",
            "Supply voltage, polarity, and current limit",
            "power",
            True,
            ["voltage", "polarity", "current limit", "current-limited", "current draw"],
            ["Set a current limit, verify polarity, then record idle and loaded current."],
        )
    if caps & {"usb_serial", "controller", "sensor_or_adc"} or _any_contract_role(pin_contracts, {"uart_tx", "uart_rx", "i2c_sda", "i2c_scl"}):
        add(
            "logic_interface",
            "Logic interface compatibility",
            "signal",
            True,
            ["logic", "uart", "serial", "i2c", "spi", "idle", "tx", "rx", "scl", "sda"],
            ["Confirm logic voltage, idle state, and protocol behavior before target connection."],
        )
    if caps & {"motor_or_load", "fan_or_pump", "actuator_driver"} or _any_contract_role(pin_contracts, {"load", "motor", "actuator"}):
        add(
            "load_driver_validation",
            "Load/driver validation",
            "load",
            True,
            ["load", "motor", "startup current", "stall", "driver", "flyback", "dummy load"],
            ["Test with a dummy or current-limited load before using the final motor/load."],
        )
    add(
        "thermal_behavior",
        "Thermal behavior",
        "thermal",
        True,
        ["thermal", "temperature", "heat", "hot", "normal"],
        ["Record temperature/thermal behavior after first power and after the output function runs."],
    )
    add(
        "output_function",
        "Output function verified",
        "functional",
        True,
        ["output function", "function verified", "terminal outcome", "successful output"],
        ["Record the terminal outcome with output_function_verified=true after the build demonstrates its target function."],
    )

    if latest_outcome.get("output_function_verified"):
        for item in items:
            if item["test_id"] == "output_function":
                item["status"] = "passed"
                item["outcome_source"] = latest_outcome.get("source")
    if _positive_result(latest_outcome.get("thermal_result")):
        for item in items:
            if item["test_id"] == "thermal_behavior":
                item["status"] = "passed"
                item["outcome_source"] = latest_outcome.get("source")

    required_items = [item for item in items if item["required"]]
    failed_items = [item for item in required_items if item["status"] == "failed"]
    open_items = [item for item in required_items if item["status"] == "open"]
    readiness = "failed_hold" if failed_items else "validation_required" if open_items else "functionally_validated"
    return {
        "schema_version": "functional_validation_protocol.v1",
        "readiness": readiness,
        "required_count": len(required_items),
        "passed_count": len([item for item in required_items if item["status"] == "passed"]),
        "open_count": len(open_items),
        "failed_count": len(failed_items),
        "test_items": items,
        "required_before_demo": [item["title"] for item in open_items[:8]],
        "failed_blockers": [item["title"] for item in failed_items[:8]],
        "claim_boundary": "Functional validation proves only the selected resources, measured pin contract, and recorded outcome for this plan.",
    }


def _matches_any_term(text: str, terms: Sequence[str]) -> bool:
    lower = str(text or "").lower()
    return any(str(term).lower() in lower for term in terms)


def _any_contract_role(pin_contracts: Sequence[Dict[str, Any]], roles: set[str]) -> bool:
    return any(
        str(wire.get("role") or "") in roles
        for contract in pin_contracts
        if isinstance(contract, dict)
        for wire in contract.get("wire_bom") or []
        if isinstance(wire, dict)
    )


def _execution_package(
    *,
    goal: str,
    resource_strategy: Dict[str, Any],
    build_splice_plan: Dict[str, Any],
    selected_resources: Sequence[Dict[str, Any]],
    procurement: Dict[str, Any],
    evidence_gates: Sequence[Dict[str, Any]],
    safety_blockers: Sequence[str],
    assurance: Dict[str, Any],
    context: Dict[str, Any],
    repair_brain: Dict[str, Any],
) -> Dict[str, Any]:
    splice = build_splice_plan.get("splice_plan") if isinstance(build_splice_plan.get("splice_plan"), dict) else {}
    pin_contracts = splice.get("pin_level_splice_contracts") if isinstance(splice.get("pin_level_splice_contracts"), list) else []
    procurement_items = procurement.get("items") if isinstance(procurement.get("items"), list) else []
    open_gates = [
        gate for gate in evidence_gates
        if isinstance(gate, dict) and str(gate.get("status", "open")) not in {"closed", "pass"}
    ]
    measurement_gates = [gate for gate in open_gates if str(gate.get("type") or "") == "measurement"]
    review_gates = [gate for gate in open_gates if str(gate.get("type") or "") == "review"]
    resource_gap_gates = [gate for gate in open_gates if str(gate.get("type") or "") == "resource_gap"]
    has_procurement = bool(procurement_items)
    outcome_summary = _outcome_execution_summary(context)
    outcome_recorded = bool(outcome_summary.get("recorded"))
    outcome_terminal = bool(outcome_summary.get("terminal"))
    validation_protocol = _functional_validation_protocol(
        selected_resources=selected_resources,
        pin_contracts=pin_contracts,
        evidence_gates=evidence_gates,
        context=context,
        outcome_summary=outcome_summary,
    )

    stages = [
        _execution_stage(
            "safety_authority",
            "blocked" if assurance.get("level") == "blocked" else "ready",
            "Decide whether this plan is allowed to proceed beyond evidence collection.",
            actions=safety_blockers or assurance.get("blockers") or ["Review authority, blocked decisions, and safety stop conditions."],
            exit_criteria=["No safety hold remains.", "Repair/build authority blockers are resolved or accepted as advisory-only."],
            blocked_by=assurance.get("blockers") if assurance.get("level") == "blocked" else [],
        ),
        _execution_stage(
            "resource_coverage",
            "complete" if selected_resources and not assurance.get("missing_capabilities") else "blocked",
            "Map the goal to owned, salvaged, procurable, or designed resources.",
            actions=[
                f"Use {resource.get('name')} for {', '.join(resource.get('matched_capabilities') or resource.get('capabilities') or [])}"
                for resource in selected_resources[:8]
                if isinstance(resource, dict)
            ] or ["Add resources that satisfy the required capabilities."],
            exit_criteria=["Every required capability is covered by a selected resource."],
            blocked_by=[f"Missing capability: {cap}" for cap in assurance.get("missing_capabilities") or []],
        ),
        _execution_stage(
            "procurement_gap_fill",
            "complete" if has_procurement and outcome_recorded else "pending_review" if has_procurement else "not_required",
            "Buy only the resources required to close real gaps.",
            actions=[
                f"Review or procure {item.get('name')} ({item.get('cost_usd', 0)} USD estimate)."
                for item in procurement_items[:8]
                if isinstance(item, dict)
            ] or ["No procurement items selected."],
            exit_criteria=["Procurement items are confirmed within budget.", "Datasheets, ratings, variants, and lead times are reviewed."],
            blocked_by=[] if procurement.get("within_budget", True) else ["Procurement estimate exceeds budget."],
        ),
        _execution_stage(
            "evidence_closure",
            "pending" if open_gates else "complete",
            "Close every measurement, review, and resource gap before physical build authority.",
            actions=[str(gate.get("prompt")) for gate in open_gates[:12] if gate.get("prompt")] or ["No open evidence gates."],
            exit_criteria=["All evidence gates are closed, passed, or explicitly scoped out."],
            blocked_by=[str(gate.get("prompt")) for gate in resource_gap_gates[:6] if gate.get("prompt")],
        ),
        _execution_stage(
            "bench_validation",
            "complete" if outcome_recorded else "pending" if measurement_gates else "ready",
            "Validate power, ground, logic levels, load current, and thermal behavior before assembly.",
            actions=[str(gate.get("prompt")) for gate in measurement_gates[:10] if gate.get("prompt")] or ["Bench validation gates are currently closed."],
            exit_criteria=[
                "No-short resistance is acceptable.",
                "Voltage, polarity, and current limit are recorded.",
                "Logic/load compatibility is proven under current limit.",
            ],
            blocked_by=[str(gate.get("prompt")) for gate in measurement_gates[:6] if gate.get("prompt")],
        ),
        _execution_stage(
            "assembly",
            "complete" if outcome_recorded and assurance.get("can_build_now") else "ready" if assurance.get("can_build_now") else "blocked_until_gates_close",
            "Assemble the selected resources according to the splice/build plan.",
            actions=_dedupe([*_pin_contract_actions(pin_contracts), *_first_build_steps(build_splice_plan)])
            or ["Generate or supply wiring/mechanical assembly steps."],
            exit_criteria=[
                "Wiring matches the selected-resource contract.",
                "Strain relief, insulation, fusing/current limiting, and labels are present.",
                "The build has passed visual inspection before power.",
            ],
            blocked_by=[] if assurance.get("can_build_now") else assurance.get("requirements_to_unlock")[:8],
        ),
        _execution_stage(
            "first_power_or_splice",
            "complete" if outcome_terminal and assurance.get("can_power_or_splice") else "ready" if assurance.get("can_power_or_splice") else "blocked_until_authority",
            "Apply first power or make an external splice only after authority and evidence gates allow it.",
            actions=[
                "Use current-limited supply at the lowest plausible safe voltage.",
                "Record voltage, current, thermal behavior, output function, and stop condition response.",
                "Disconnect immediately on unexpected current, heat, smell, smoke, or unstable behavior.",
            ],
            exit_criteria=[
                "Output function works under current limit.",
                "No abnormal heat/current/smell/noise is observed.",
                "Measured behavior matches the target build assumptions.",
            ],
            blocked_by=[] if assurance.get("can_power_or_splice") else ["Authority or evidence gates do not yet allow first power/splice."],
        ),
        _execution_stage(
            "outcome_capture",
            "complete" if outcome_recorded else "pending",
            "Record whether the repair/reuse/build worked so the engine can improve future planning.",
            actions=[
                "Record decision: built, repaired, reused, sold, unsafe_hold, not_worth_it, or failed.",
                "Record value recovered, cash spent, time spent, measurements, deviations, and photos.",
                "Label which selected resources worked and which were rejected.",
            ],
            exit_criteria=["Outcome is attached to the board session with measurements and operator corrections."],
            blocked_by=[] if outcome_recorded else ["No build/repair/reuse outcome is attached yet."],
        ),
    ]
    current_stage = _current_execution_stage(stages)
    return {
        "schema_version": "hardware_execution_package.v1",
        "goal": goal,
        "current_stage": current_stage,
        "completion_state": "blocked" if any(stage["status"] == "blocked" for stage in stages) else "in_progress" if current_stage != "complete" else "complete",
        "selected_resource_map": [
            {
                "resource_id": resource.get("resource_id"),
                "name": resource.get("name"),
                "kind": resource.get("resource_kind"),
                "capabilities": resource.get("capabilities") or [],
                "status": resource.get("status"),
                "cost_usd": resource.get("cost_usd", 0),
            }
            for resource in selected_resources[:12]
            if isinstance(resource, dict)
        ],
        "procurement_items": [
            {
                "resource_id": item.get("resource_id"),
                "name": item.get("name"),
                "cost_usd": item.get("cost_usd", 0),
                "fills": item.get("fills_capabilities") or item.get("matched_capabilities") or item.get("capabilities") or [],
            }
            for item in procurement_items[:12]
            if isinstance(item, dict)
        ],
        "adapter_contracts": splice.get("adapter_circuits") or [],
        "pin_level_splice_contracts": pin_contracts,
        "repair_brain": repair_brain,
        "measurement_protocol": repair_brain.get("measurement_protocol") if repair_brain.get("available") else {},
        "part_grounding": repair_brain.get("part_grounding") if repair_brain.get("available") else {},
        "reuse_splice_strategy": repair_brain.get("reuse_splice_strategy") if repair_brain.get("available") else {},
        "component_salvage_map": repair_brain.get("component_salvage_map") if repair_brain.get("available") else {},
        "arbitrary_board_trust_assessment": repair_brain.get("arbitrary_board_trust_assessment") if repair_brain.get("available") else {},
        "functional_validation_protocol": validation_protocol,
        "entry_points": splice.get("safest_entry_points") or [],
        "stop_conditions": _dedupe([*map(str, build_splice_plan.get("stop_conditions") or []), *map(str, safety_blockers)])[:12],
        "acceptance_criteria": [
            "All assurance requirements are closed.",
            "Selected resources cover all required capabilities.",
            "Bench measurements prove safe voltage, polarity, current, ground, and logic/load compatibility.",
            "First power succeeds under current limit without abnormal thermal/current behavior.",
            "Outcome is recorded with evidence and corrections.",
        ],
        "outcome_contract": {
            "required_fields": [
                "decision",
                "selected_resource_ids_used",
                "measurements_recorded",
                "cash_spent_usd",
                "value_recovered_usd",
                "time_spent_minutes",
                "deviations_from_plan",
                "failure_or_stop_reason",
                "evidence_uri",
            ],
            "allowed_decisions": ["built", "repaired", "reused", "sold", "unsafe_hold", "not_worth_it", "failed"],
            "learning_use": "Feeds future resource ranking, evidence gates, and build-risk calibration.",
            "recorded": outcome_recorded,
            "latest_decision": outcome_summary.get("decision"),
            "required_fields_present": outcome_summary.get("required_fields_present"),
        },
        "stages": stages,
        "next_operator_actions": _next_execution_actions(stages),
    }


def _execution_stage(
    stage_id: str,
    status: str,
    objective: str,
    *,
    actions: Sequence[str],
    exit_criteria: Sequence[str],
    blocked_by: Sequence[str],
) -> Dict[str, Any]:
    return {
        "stage_id": stage_id,
        "status": status,
        "objective": objective,
        "actions": _dedupe(str(action) for action in actions)[:12],
        "exit_criteria": _dedupe(str(item) for item in exit_criteria)[:8],
        "blocked_by": _dedupe(str(item) for item in blocked_by)[:8],
    }


def _current_execution_stage(stages: Sequence[Dict[str, Any]]) -> str:
    for stage in stages:
        if stage.get("status") in {"blocked", "pending", "pending_review", "blocked_until_gates_close", "blocked_until_authority"}:
            return str(stage.get("stage_id") or "unknown")
    return "complete"


def _next_execution_actions(stages: Sequence[Dict[str, Any]]) -> List[str]:
    actions: List[str] = []
    for stage in stages:
        if stage.get("status") in {"complete", "not_required", "ready"}:
            continue
        actions.extend(str(action) for action in stage.get("actions") or [])
        if actions:
            break
    return _dedupe(actions)[:8]


def _compact_diy_project_engineering(plan: Any) -> Dict[str, Any]:
    if not isinstance(plan, dict) or not plan.get("available"):
        return {}
    intent = plan.get("project_intent") if isinstance(plan.get("project_intent"), dict) else {}
    requirements = plan.get("requirements") if isinstance(plan.get("requirements"), dict) else {}
    resource_plan = plan.get("resource_plan") if isinstance(plan.get("resource_plan"), dict) else {}
    return {
        "schema_version": plan.get("schema_version"),
        "profile_id": intent.get("profile_id"),
        "profile_label": intent.get("profile_label"),
        "mapped_build_id": intent.get("mapped_build_id"),
        "required_capabilities": requirements.get("required_capabilities") or [],
        "resource_coverage": resource_plan.get("coverage") or {},
        "readiness": plan.get("readiness") if isinstance(plan.get("readiness"), dict) else {},
        "architecture_blocks": plan.get("architecture_blocks") or [],
        "build_stages": plan.get("build_stages") or [],
        "next_actions": plan.get("next_actions") or [],
        "claim_boundary": plan.get("claim_boundary"),
    }


def _compact_splice_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    functional = plan.get("functional_reuse_plan") if isinstance(plan.get("functional_reuse_plan"), dict) else {}
    circuit_reasoning = plan.get("circuit_reasoning") if isinstance(plan.get("circuit_reasoning"), dict) else {}
    proof_summary = circuit_reasoning.get("proof_summary") if isinstance(circuit_reasoning.get("proof_summary"), dict) else {}
    compact = {
        "mode": plan.get("mode"),
        "verdict": plan.get("verdict"),
        "confidence": plan.get("confidence"),
        "target": plan.get("target") if isinstance(plan.get("target"), dict) else {},
        "capability_summary": plan.get("capability_summary") if isinstance(plan.get("capability_summary"), dict) else {},
        "build_candidates": [
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "score": row.get("score"),
                "difficulty": row.get("difficulty"),
                "matched_capabilities": row.get("matched_capabilities") or [],
                "missing_capability_groups": row.get("missing_capability_groups") or [],
                "first_build_step": row.get("first_build_step"),
            }
            for row in plan.get("build_candidates") or []
            if isinstance(row, dict)
        ][:8],
        "splice_plan": plan.get("splice_plan") if isinstance(plan.get("splice_plan"), dict) else {},
        "functional_reuse_plan": {
            "mode": functional.get("mode"),
            "verdict": functional.get("verdict"),
            "circuit_backed": functional.get("circuit_backed", False),
            "reusable_block_count": functional.get("reusable_block_count", 0),
            "ready_block_count": functional.get("ready_block_count", 0),
            "blocked_block_count": functional.get("blocked_block_count", 0),
            "splice_readiness": functional.get("splice_readiness"),
            "recommended_first_splice": functional.get("recommended_first_splice") or {},
            "top_blocks": functional.get("top_blocks") or [],
            "ready_blocks": functional.get("ready_blocks") or [],
        },
        "integration_contract": plan.get("integration_contract") if isinstance(plan.get("integration_contract"), dict) else {},
        "evidence_plan": plan.get("evidence_plan") if isinstance(plan.get("evidence_plan"), dict) else {},
        "stop_conditions": plan.get("stop_conditions") or [],
        "resource_strategy_link": plan.get("resource_strategy_link") if isinstance(plan.get("resource_strategy_link"), dict) else {},
        "circuit_reasoning_summary": {
            "verifier_status": (circuit_reasoning.get("verifier") or {}).get("status") if isinstance(circuit_reasoning.get("verifier"), dict) else None,
            "operational_verdict": proof_summary.get("operational_verdict"),
            "recommended_first_action": circuit_reasoning.get("recommended_first_action") or {},
        },
    }
    return compact


def _certainty_score(integrated: Dict[str, Any]) -> float:
    assurance = integrated.get("assurance") if isinstance(integrated.get("assurance"), dict) else {}
    if assurance.get("score") is not None:
        return float(assurance.get("score") or 0.0)
    status = integrated.get("status")
    if status == "ready_for_build_plan":
        return 0.78
    if status == "prototype_after_evidence":
        return 0.62
    if status in {"blocked_missing_resources", "blocked_over_budget"}:
        return 0.44
    if status == "safety_hold":
        return 0.36
    return 0.3


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:90] or "gate"


def _list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and value == 1:
        return True
    text = str(value or "").strip().lower()
    return text in {"true", "yes", "y", "1", "pass", "passed", "complete", "completed", "verified", "ok"}


def _dedupe(items: Iterable[str]) -> List[str]:
    kept: List[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        kept.append(text)
    return kept


def _dedupe_analysis_tasks(tasks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for task in tasks:
        prompt = str(task.get("prompt") or "").strip()
        key = (str(task.get("type") or ""), prompt.lower())
        if not prompt or key in seen:
            continue
        seen.add(key)
        kept.append(dict(task))
    return kept


def _dedupe_gates(gates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for gate in gates:
        key = (str(gate.get("type") or ""), str(gate.get("prompt") or "").strip().lower())
        if not key[1] or key in seen:
            continue
        seen.add(key)
        kept.append(gate)
    return kept
