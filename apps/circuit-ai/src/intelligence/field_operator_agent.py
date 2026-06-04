"""Operational next-action engine for bench/field hardware work.

This module makes the current backend outputs usable one step at a time. It can
assign advisory work to Qwen/DeepSeek-style models, but deterministic gates keep
final power/splice/release authority.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from src.intelligence.design_test_kit import build_design_test_kit


SCHEMA_VERSION = "hardware_field_operator_next_action.v1"


def build_field_operator_next_action(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return the next practical operator/model action for a hardware plan."""

    body = dict(payload or {})
    kit = _design_test_kit(body)
    call = _select_operational_call(body, kit)
    candidates = _candidate_actions(body, kit, call)
    assignments = _model_assignments(call, body, kit)
    return {
        "mode": "hardware_field_operator",
        "schema_version": SCHEMA_VERSION,
        "available": bool(kit.get("available")) or bool(call),
        "operational_call": call,
        "candidate_actions": candidates,
        "model_assignments": assignments,
        "decision_inputs": _decision_inputs(kit),
        "capture_packet": _capture_packet(call),
        "claim_boundary": (
            "The field operator can choose photos, measurements, stop calls, and redesign tasks. "
            "Qwen/DeepSeek outputs are advisory field observations until measured evidence and deterministic gates confirm them. "
            "The field operator cannot independently authorize high-risk power, splice, or production release."
        ),
    }


def _design_test_kit(body: Dict[str, Any]) -> Dict[str, Any]:
    for key in ["design_test_kit", "hardware_design_test_kit", "test_kit"]:
        value = body.get(key)
        if isinstance(value, dict) and value.get("mode") == "hardware_design_test_kit":
            return value
    return build_design_test_kit(body)


def _select_operational_call(body: Dict[str, Any], kit: Dict[str, Any]) -> Dict[str, Any]:
    release = kit.get("release_gate") if isinstance(kit.get("release_gate"), dict) else {}
    simulation = kit.get("simulation") if isinstance(kit.get("simulation"), dict) else {}
    compiled = _compiled(kit)
    decision = str(release.get("decision") or "")

    blocked = _first_test(kit, statuses={"blocked"})
    if decision == "blocked_by_safety_or_specialist_authority" or blocked:
        return _hazard_stop_call(blocked, compiled, release)

    error_issue = _first_sim_issue(simulation, severities={"critical", "error"})
    if decision == "blocked_by_simulation_failure" or error_issue:
        return _simulation_failure_call(error_issue, release)

    envelope = simulation.get("load_envelope") if isinstance(simulation.get("load_envelope"), dict) else {}
    if decision == "bounded_load_envelope_measurement_required" or envelope.get("available"):
        return _measure_load_envelope_call(envelope, release)

    if decision == "simulation_model_incomplete_load_model_required":
        return _missing_load_model_call(compiled, release)

    if decision == "test_fixture_required":
        return _topology_or_netlist_call(body, kit, release)

    if decision == "blocked_by_design_contract" and _has_visual_context(body) and not _has_measured_topology_or_netlist(body, kit):
        return _topology_or_netlist_call(body, kit, release)

    pending_measurement = _first_test(kit, statuses={"pending"}, layers={"evidence", "power_simulation"})
    if pending_measurement:
        return _close_evidence_gate_call(pending_measurement, release)

    if decision in {"simulation_passed_bench_evidence_required", "design_test_suite_passed_bench_release_required"}:
        return _terminal_outcome_call(kit, release)

    return _define_project_call(kit, release)


def _hazard_stop_call(blocked: Optional[Dict[str, Any]], compiled: Dict[str, Any], release: Dict[str, Any]) -> Dict[str, Any]:
    issue = _first_compile_issue(compiled, severities={"critical", "error"})
    summary = (
        issue.get("summary")
        if issue
        else blocked.get("check") if blocked
        else "Hard safety/specialist-authority gate is active."
    )
    detail = (
        issue.get("detail")
        if issue
        else blocked.get("rationale") if blocked
        else str(release.get("reason") or "Stop direct bench work.")
    )
    return _call(
        action_id="stop_hazard_clearance",
        action_type="stop",
        priority=0,
        authority="hard_stop",
        summary=str(summary),
        why=str(detail),
        tools=["camera for hazard documentation", "DMM for unpowered confirmation only", "isolation bag/bin if damaged energy storage is suspected"],
        procedure=[
            "Do not power, splice, load-test, or connect this board/module to another target.",
            "Document the hazard evidence with a close-up photo and measurement note.",
            "If the hazard is a short, confirm with unpowered resistance/continuity only.",
            "Route the case to the required specialist or repair-clearance lane before rerunning the test kit.",
        ],
        pass_fail_thresholds={"power_allowed": False, "model_override_allowed": False},
        expected_input_schema={
            "hazard_clearance_record": {
                "hazard_id": "string",
                "clearance_authority": "string",
                "evidence_uri": "string",
                "status": "cleared|still_blocked",
            }
        },
        on_pass="Attach hazard clearance evidence and rerun the field operator/test kit.",
        on_fail="Keep the case blocked and do not power or splice.",
    )


def _simulation_failure_call(issue: Optional[Dict[str, Any]], release: Dict[str, Any]) -> Dict[str, Any]:
    issue = issue or {}
    physics = issue.get("physics_data") if isinstance(issue.get("physics_data"), dict) else {}
    return _call(
        action_id="resolve_power_budget_failure",
        action_type="redesign_or_reduce_load",
        priority=1,
        authority="operational_block",
        summary=str(issue.get("issue") or "Simulation failure blocks the next bench step."),
        why=str(issue.get("explanation") or release.get("reason") or "The deterministic simulation found a hard failure."),
        tools=["datasheet or label photo", "current-limited supply", "USB power meter or inline ammeter"],
        procedure=[
            "Do not run the current source/load combination as-is.",
            "Identify whether the source limit, load current, trace drop, or regulator limit caused the failure.",
            "Reduce load, choose a higher-current source, change regulator/driver, or split the rail.",
            "Update the measured/current model and rerun the topology compiler plus test kit.",
        ],
        pass_fail_thresholds={
            "measured_current_a": physics.get("current_a"),
            "limit_a": physics.get("limit_a"),
            "over_a": physics.get("over_a"),
            "must_be_below_limit": True,
        },
        expected_input_schema={
            "updated_power_model": {
                "source_name": "string",
                "max_current_a": "number",
                "load_current_a": "number",
                "source_or_load_change": "string",
            }
        },
        on_pass="Rerun design test kit; advance only if source-limit and rail checks pass.",
        on_fail="Keep design blocked; pick a different source/load/driver path.",
    )


def _measure_load_envelope_call(envelope: Dict[str, Any], release: Dict[str, Any]) -> Dict[str, Any]:
    return _call(
        action_id="measure_unknown_load_current",
        action_type="measurement",
        priority=1,
        authority="operational_measurement",
        summary="Measure the real load current against the bounded envelope.",
        why=str(release.get("reason") or envelope.get("pass_condition") or "Load current is unknown, but a source-limit envelope exists."),
        tools=["current-limited bench supply", "USB power meter or inline ammeter", "thermal probe or touch-safe thermal camera"],
        procedure=[
            "Set the supply/source current limit to the envelope absolute limit before connecting the load.",
            "Power the load briefly and record startup/inrush current.",
            "Record steady current after the load stabilizes.",
            "Stop immediately if current hits the source limit, voltage collapses, or abnormal heat appears.",
            "Attach the measurement as topology current evidence and rerun the compiler/test kit.",
        ],
        pass_fail_thresholds={
            "steady_current_a_max": envelope.get("recommended_max_load_a"),
            "startup_current_a_max": envelope.get("absolute_source_limit_a"),
            "recommended_power_w_max": envelope.get("recommended_max_power_w"),
            "rail_node": envelope.get("node"),
        },
        expected_input_schema={
            "topology_evidence.current[]": {
                "kind": "current",
                "target": "current draw under current-limited supply",
                "value": "number",
                "unit": "A|mA",
                "status": "pass|failed",
                "instrument_id": "string",
                "recorded_at": "ISO timestamp",
                "operator_id": "string",
                "evidence_uri": "string",
            }
        },
        on_pass="Use the measured current as the load model and rerun topology compiler/test kit.",
        on_fail="Reduce load, choose a higher-current source, or redesign the driver/power path.",
    )


def _missing_load_model_call(compiled: Dict[str, Any], release: Dict[str, Any]) -> Dict[str, Any]:
    envelope = compiled.get("load_envelope") if isinstance(compiled.get("load_envelope"), dict) else {}
    return _call(
        action_id="establish_source_limit_and_load_model",
        action_type="measurement",
        priority=1,
        authority="operational_measurement",
        summary="Establish source current limit and load current before loaded proof.",
        why=str(envelope.get("reason") or release.get("reason") or "The topology rail is known, but load behavior is not bounded."),
        tools=["current-limited supply", "USB power meter or inline ammeter", "DMM"],
        procedure=[
            "Record the actual source current limit or choose a current-limited supply setting.",
            "Measure steady and startup load current.",
            "Add both the source limit and measured current to the topology evidence.",
            "Rerun compiler/test kit to turn the incomplete rail model into a loaded simulation.",
        ],
        pass_fail_thresholds={"source_current_limit_a_required": True, "load_current_a_required": True},
        expected_input_schema={
            "constraints": {"current_limit_a": "number"},
            "topology_evidence.current[]": {"value": "number", "unit": "A|mA", "status": "pass|failed"},
        },
        on_pass="Rerun topology compiler. If an envelope is available, compare measured current to the envelope.",
        on_fail="Do not use the rail as loaded proof.",
    )


def _topology_or_netlist_call(body: Dict[str, Any], kit: Dict[str, Any], release: Dict[str, Any]) -> Dict[str, Any]:
    has_visual = _has_visual_context(body)
    return _call(
        action_id="capture_topology_or_supply_netlist",
        action_type="capture_or_measurement",
        priority=2,
        authority="operational_advisory",
        summary="Capture measured topology or supply a versioned simulation netlist.",
        why=str(release.get("reason") or "The test kit cannot simulate without topology/netlist evidence."),
        tools=["Qwen vision pass for connector candidates", "DMM continuity mode", "current-limited supply", "close-up camera"],
        procedure=[
            "Use Qwen/vision to identify candidate connectors, rails, labels, and likely pin groups." if has_visual else "Capture whole-board and connector close-up photos first.",
            "Measure ground continuity and power-to-ground no-short.",
            "Measure rail voltage and polarity under current limit.",
            "Measure load/source current when safe.",
            "Submit topology_evidence.v1 or a versioned netlist and rerun the field operator.",
        ],
        pass_fail_thresholds={"minimum_required": ["ground", "power rail voltage", "no-short", "source/load current or source limit"]},
        expected_input_schema={
            "topology_evidence": {
                "connectors": [{"ref": "string", "pins": [{"pin": "string", "net": "string", "role": "power|ground|signal", "voltage": "number|null"}]}],
                "resistance": [{"target": "power to ground no-short", "value": "pass|fail"}],
                "current": [{"target": "current draw under current-limited supply", "value": "number", "unit": "A|mA"}],
            }
        },
        on_pass="Compiler should emit a netlist or bounded envelope.",
        on_fail="Continue topology capture; do not power/splice without measured topology.",
    )


def _close_evidence_gate_call(test: Dict[str, Any], release: Dict[str, Any]) -> Dict[str, Any]:
    return _call(
        action_id=f"close_{test.get('test_id')}",
        action_type="measurement" if "measurement" in " ".join(test.get("evidence_required") or []).lower() else "review",
        priority=2,
        authority="operational_measurement",
        summary=str(test.get("check") or "Close the next evidence gate."),
        why=str(test.get("rationale") or release.get("reason") or "A test-kit evidence gate is still open."),
        tools=["DMM", "current-limited supply", "photo/log artifact"],
        procedure=[
            "Run the named gate exactly once under current limit where applicable.",
            "Record instrument, operator, timestamp, value, units, and artifact URI.",
            "Attach the result to topology evidence or outcome history.",
            "Rerun field operator/test kit.",
        ],
        pass_fail_thresholds={"gate_status_required": "pass|closed", "evidence_required": test.get("evidence_required") or []},
        expected_input_schema={"measurement_or_review_record": {"target": "string", "value": "string|number", "status": "pass|failed"}},
        on_pass="Advance to the next open gate.",
        on_fail="Keep design gated and route to redesign/repair.",
    )


def _terminal_outcome_call(kit: Dict[str, Any], release: Dict[str, Any]) -> Dict[str, Any]:
    return _call(
        action_id="record_terminal_outcome",
        action_type="outcome_record",
        priority=3,
        authority="operational_measurement",
        summary="Record terminal functional outcome proof.",
        why=str(release.get("reason") or "Simulation passed hard checks, but outcome evidence is still needed."),
        tools=["camera/video", "measurement log", "thermal probe"],
        procedure=[
            "Run the target function under the validated power setup.",
            "Record output proof, current, voltage, thermal result, deviations, and stop condition.",
            "Attach photos/video/log artifacts.",
            "Only then prepare a scoped demo/release packet.",
        ],
        pass_fail_thresholds={"output_function_verified": True, "thermal_result": "normal", "first_power_result": "pass"},
        expected_input_schema={
            "outcome_history[]": {
                "decision": "built|failed|stopped",
                "output_function_verified": "boolean",
                "first_power_result": "pass|failed",
                "thermal_result": "normal|failed",
                "evidence_uri": "string",
            }
        },
        on_pass="Move to scoped release/demo package.",
        on_fail="Use failure details to pick redesign or fault-isolation call.",
    )


def _define_project_call(kit: Dict[str, Any], release: Dict[str, Any]) -> Dict[str, Any]:
    return _call(
        action_id="define_testable_project_contract",
        action_type="intake",
        priority=4,
        authority="operational_advisory",
        summary="Define the target function and test contract.",
        why=str(release.get("reason") or "The field operator needs a testable project/design contract."),
        tools=["DeepSeek text reasoner", "operator chat"],
        procedure=[
            "Write the target output function.",
            "State pass/fail behavior and stop conditions.",
            "List available resources and constraints.",
            "Rerun planner/test kit.",
        ],
        pass_fail_thresholds={"target_function_required": True},
        expected_input_schema={"diy_project": "string", "available_resources": "array", "constraints": "object"},
        on_pass="Generate design test kit and field operator action.",
        on_fail="Keep intake open.",
    )


def _candidate_actions(body: Dict[str, Any], kit: Dict[str, Any], selected: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions = [selected]
    for action in kit.get("next_actions") or []:
        if not str(action or "").strip():
            continue
        actions.append(
            {
                "action_id": f"kit_next_{len(actions)}",
                "action_type": "followup",
                "priority": 5 + len(actions),
                "summary": str(action),
                "authority": "operational_advisory",
            }
        )
    return _dedupe_actions(actions)[:8]


def _model_assignments(call: Dict[str, Any], body: Dict[str, Any], kit: Dict[str, Any]) -> List[Dict[str, Any]]:
    action_type = str(call.get("action_type") or "")
    assignments = []
    if action_type in {"capture_or_measurement", "stop", "redesign_or_reduce_load"} or _has_visual_context(body):
        assignments.append(
            {
                "model": "qwen_vision",
                "role": "field_visual_candidate",
                "call": _qwen_call_for_action(action_type),
                "input_needed": ["whole board photo", "connector close-up", "markings/source/load label photo"],
                "output_schema": {
                    "candidate_connectors": [],
                    "candidate_power_ground_pins": [],
                    "candidate_markings": [],
                    "measurement_targets": [],
                    "confidence": "candidate_only",
                },
                "authority_boundary": "Qwen can propose where to probe; it cannot verify voltage, current, no-short, or safety.",
            }
        )
    assignments.append(
        {
            "model": "deepseek_reasoner",
            "role": "field_reasoning_assistant",
            "call": _deepseek_call_for_action(action_type),
            "input_needed": ["current field call", "test-kit decision", "operator notes", "measurement results"],
            "output_schema": {
                "plain_language_steps": [],
                "risk_explanation": "string",
                "candidate_redesigns": [],
                "structured_measurement_update": {},
            },
            "authority_boundary": "DeepSeek can structure notes, explain failures, and suggest next measurements; deterministic gates decide trust.",
        }
    )
    assignments.append(
        {
            "model": "backend_validator",
            "role": "deterministic_gatekeeper",
            "call": "rerun topology compiler, power-tree simulation, and design test kit after new evidence",
            "authority_boundary": "Only measured evidence plus deterministic gates can advance power/splice/release state.",
        }
    )
    return assignments


def _capture_packet(call: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "packet_id": f"field_packet_{call.get('action_id')}",
        "action_id": call.get("action_id"),
        "expected_input_schema": call.get("expected_input_schema") or {},
        "pass_fail_thresholds": call.get("pass_fail_thresholds") or {},
        "on_pass": call.get("on_pass"),
        "on_fail": call.get("on_fail"),
        "artifact_required": True,
    }


def _decision_inputs(kit: Dict[str, Any]) -> Dict[str, Any]:
    release = kit.get("release_gate") if isinstance(kit.get("release_gate"), dict) else {}
    suite = kit.get("test_suite") if isinstance(kit.get("test_suite"), dict) else {}
    simulation = kit.get("simulation") if isinstance(kit.get("simulation"), dict) else {}
    compiled = _compiled(kit)
    coverage = compiled.get("coverage") if isinstance(compiled.get("coverage"), dict) else {}
    return {
        "release_decision": release.get("decision"),
        "release_reason": release.get("reason"),
        "test_score": suite.get("score"),
        "fail_count": suite.get("fail_count"),
        "blocked_count": suite.get("blocked_count"),
        "pending_count": suite.get("pending_count"),
        "simulation_available": bool(simulation.get("available")),
        "simulation_issue_count": len(simulation.get("issues") or []),
        "compiled_topology_available": bool(compiled.get("available")),
        "compiled_coverage": coverage,
    }


def _call(
    *,
    action_id: str,
    action_type: str,
    priority: int,
    authority: str,
    summary: str,
    why: str,
    tools: Sequence[str],
    procedure: Sequence[str],
    pass_fail_thresholds: Dict[str, Any],
    expected_input_schema: Dict[str, Any],
    on_pass: str,
    on_fail: str,
) -> Dict[str, Any]:
    return {
        "action_id": action_id,
        "action_type": action_type,
        "priority": priority,
        "authority": authority,
        "summary": summary,
        "why": why,
        "tools": list(tools),
        "procedure": list(procedure),
        "pass_fail_thresholds": pass_fail_thresholds,
        "expected_input_schema": expected_input_schema,
        "on_pass": on_pass,
        "on_fail": on_fail,
    }


def _compiled(kit: Dict[str, Any]) -> Dict[str, Any]:
    design = kit.get("design_model") if isinstance(kit.get("design_model"), dict) else {}
    compiled = design.get("compiled_topology_netlist")
    return compiled if isinstance(compiled, dict) else {}


def _first_compile_issue(compiled: Dict[str, Any], *, severities: set[str]) -> Optional[Dict[str, Any]]:
    for issue in compiled.get("issues") or []:
        if isinstance(issue, dict) and str(issue.get("severity") or "").lower() in severities:
            return issue
    return None


def _first_sim_issue(simulation: Dict[str, Any], *, severities: set[str]) -> Optional[Dict[str, Any]]:
    for issue in simulation.get("issues") or []:
        if isinstance(issue, dict) and str(issue.get("severity") or "").lower() in severities:
            return issue
    envelope = simulation.get("load_envelope") if isinstance(simulation.get("load_envelope"), dict) else {}
    for scenario in envelope.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        for issue in scenario.get("issues") or []:
            if isinstance(issue, dict) and str(issue.get("severity") or "").lower() in severities:
                return issue
    return None


def _first_test(
    kit: Dict[str, Any],
    *,
    statuses: set[str],
    layers: Optional[set[str]] = None,
) -> Optional[Dict[str, Any]]:
    suite = kit.get("test_suite") if isinstance(kit.get("test_suite"), dict) else {}
    for test in suite.get("tests") or []:
        if not isinstance(test, dict):
            continue
        if layers and str(test.get("layer") or "") not in layers:
            continue
        if str(test.get("status") or "") in statuses:
            return test
    return None


def _qwen_call_for_action(action_type: str) -> str:
    return {
        "stop": "document visible hazard evidence and candidate affected regions",
        "redesign_or_reduce_load": "read source/load markings and identify connector/rail labels",
        "measurement": "identify where the operator should place probes and what labels are visible",
        "capture_or_measurement": "extract candidate topology from board and connector photos",
    }.get(action_type, "extract candidate visual evidence for the current field action")


def _deepseek_call_for_action(action_type: str) -> str:
    return {
        "stop": "turn hazard evidence into a clearance checklist",
        "redesign_or_reduce_load": "explain the power-budget failure and propose safe redesign candidates",
        "measurement": "turn the field call into a concise bench procedure and parse results into schema",
        "capture_or_measurement": "prioritize measurements needed to convert candidates into topology evidence",
        "outcome_record": "structure outcome notes into release-ready evidence fields",
    }.get(action_type, "structure operator notes into the next evidence update")


def _has_visual_context(body: Dict[str, Any]) -> bool:
    visual_keys = [
        "qwen_board_vision",
        "qwen_advisory",
        "visual_topology_hypothesis",
        "multiview_board_reconstruction",
        "board_evidence",
        "board_photo_set",
        "photo_observations",
        "images",
        "image_paths",
    ]
    if any(isinstance(body.get(key), dict) or isinstance(body.get(key), list) for key in visual_keys):
        return True
    analysis = body.get("analysis") if isinstance(body.get("analysis"), dict) else {}
    return any(
        isinstance(analysis.get(key), dict) or isinstance(analysis.get(key), list)
        for key in ["visual_topology_hypothesis", "multiview_board_reconstruction", "board_evidence"]
    )


def _has_measured_topology_or_netlist(body: Dict[str, Any], kit: Dict[str, Any]) -> bool:
    if any(isinstance(body.get(key), dict) for key in ["topology_evidence", "netlist", "simulation_netlist", "design_netlist", "power_tree_netlist"]):
        return True
    compiled = _compiled(kit)
    if compiled.get("available") and not compiled.get("reference_only"):
        return True
    analysis = body.get("analysis") if isinstance(body.get("analysis"), dict) else {}
    authority = analysis.get("topology_authority") if isinstance(analysis.get("topology_authority"), dict) else {}
    return bool(authority.get("measurement_backed"))


def _dedupe_actions(actions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept = []
    seen = set()
    for action in actions:
        key = str(action.get("action_id") or action.get("summary") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        kept.append(action)
    return kept
