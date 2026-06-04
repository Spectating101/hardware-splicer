"""Arbitrary-board omniscience map.

This is not literal omniscience. It is the highest-value operator view we can
build from the current engine: fused hypotheses, grounded facts, unknowns, and
the next evidence batch that would reduce uncertainty fastest.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from src.intelligence.arbitrary_board_workflow import build_arbitrary_board_workflow
from src.intelligence.authority_ledger import build_authority_ledger
from src.intelligence.board_evidence_graph import BoardEvidenceGraphBuilder
from src.intelligence.field_operator_agent import build_field_operator_next_action
from src.intelligence.hardware_plan import HardwarePlanOrchestrator


SCHEMA_VERSION = "board_omniscience_map.v1"


def build_board_omniscience_map(payload: Dict[str, Any], *, include_evidence_graph: bool = True) -> Dict[str, Any]:
    """Build a single operator-facing map for an arbitrary board."""

    body = dict(payload or {})
    plan = HardwarePlanOrchestrator().plan(body)
    analysis = plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {}
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    ledger = build_authority_ledger({**body, "hardware_plan": plan})
    field = build_field_operator_next_action({**body, "hardware_plan": plan})
    closure = _first_dict(analysis.get("active_evidence_closure_plan"))
    workflow = _first_dict(analysis.get("arbitrary_board_workflow"))
    if not workflow:
        fallback_workflow = build_arbitrary_board_workflow(
            {**body, "enable_arbitrary_board_workflow": True},
            analysis=analysis,
        )
        workflow = fallback_workflow if fallback_workflow.get("available") else {}
    function = _first_dict(analysis.get("board_function_inference"), workflow.get("board_function_inference"))
    visual_topology = _first_dict(analysis.get("visual_topology_hypothesis"))
    reconstruction = _first_dict(analysis.get("multiview_board_reconstruction"))
    board = _first_dict(analysis.get("board_evidence"), body.get("board_evidence"))
    part_grounding = _first_dict(analysis.get("part_grounding"), workflow.get("part_grounding"))
    trust = _first_dict(analysis.get("arbitrary_board_trust_assessment"), workflow.get("arbitrary_board_trust_assessment"))
    dimensions = _omniscience_dimensions(
        board=board,
        reconstruction=reconstruction,
        function=function,
        visual_topology=visual_topology,
        ledger=ledger,
        closure=closure,
        part_grounding=part_grounding,
        trust=trust,
    )
    score = _weighted_score(dimensions)
    can = ledger.get("can") if isinstance(ledger.get("can"), dict) else {}
    if can.get("claim_production_repair_release"):
        score = max(score, _safe_float(ledger.get("authority_score"), 0.0))
    elif ledger.get("current_authority_level") in {"measured_topology", "electrical_simulation", "controlled_bench"}:
        score = max(score, round(0.8 * _safe_float(ledger.get("authority_score"), 0.0), 3))
    level = _omniscience_level(ledger, dimensions, score)
    unknowns = _unknowns(
        board=board,
        reconstruction=reconstruction,
        visual_topology=visual_topology,
        closure=closure,
        ledger=ledger,
        trust=trust,
    )
    next_batch = _next_evidence_batch(closure, workflow, field, unknowns)
    if can.get("claim_production_repair_release"):
        next_batch = []
    evidence_graph = _evidence_graph(body, analysis, next_batch) if include_evidence_graph else {}

    return {
        "mode": "board_omniscience_map",
        "schema_version": SCHEMA_VERSION,
        "available": bool(board or reconstruction or function or visual_topology or ledger.get("available")),
        "summary": {
            "omniscience_level": level,
            "omniscience_score": score,
            "authority_level": ledger.get("current_authority_level"),
            "authority_score": ledger.get("authority_score"),
            "production_authorized": bool((ledger.get("can") or {}).get("claim_production_repair_release")),
            "primary_function": function.get("primary_function_id") or "unknown",
            "primary_function_confidence": function.get("confidence"),
            "next_best_action_id": (next_batch[0] or {}).get("action_id") if next_batch else None,
            "unknown_count": len(unknowns),
        },
        "dimensions": dimensions,
        "hypothesis_lattice": _hypothesis_lattice(function, part_grounding, visual_topology),
        "known_facts": _known_facts(
            board=board,
            reconstruction=reconstruction,
            visual_topology=visual_topology,
            ledger=ledger,
            workflow=workflow,
            integrated=integrated,
        ),
        "unknowns": unknowns,
        "next_evidence_batch": next_batch,
        "operator_playbook": _operator_playbook(level, ledger, next_batch),
        "claim_control": {
            "can": ledger.get("can") if isinstance(ledger.get("can"), dict) else {},
            "cannot_claim_yet": _cannot_claim_yet(ledger, unknowns),
            "claim_boundary": (
                "This map can rank hypotheses and evidence. It cannot infer hidden nets, safe power, or repair release "
                "from images alone. Authority still comes from measured topology, simulation, controlled outcome, and release artifacts."
            ),
        },
        "model_routes": _model_routes(reconstruction, visual_topology, next_batch),
        "ceiling_projection": _ceiling_projection(closure, ledger, score),
        "evidence_graph": evidence_graph,
        "hardware_plan_summary": {
            "status": integrated.get("status"),
            "recommended_path": integrated.get("recommended_path"),
            "open_gate_count": (integrated.get("assurance") or {}).get("open_gate_count")
            if isinstance(integrated.get("assurance"), dict)
            else None,
            "can_power_or_splice": (integrated.get("assurance") or {}).get("can_power_or_splice")
            if isinstance(integrated.get("assurance"), dict)
            else None,
        },
        "source_modules": {
            "hardware_plan": bool(plan),
            "multiview_board_reconstruction": bool(reconstruction),
            "visual_topology_hypothesis": bool(visual_topology.get("available")),
            "arbitrary_board_workflow": bool(workflow),
            "authority_ledger": bool(ledger),
            "active_evidence_closure_plan": bool(closure),
        },
    }


def _omniscience_dimensions(
    *,
    board: Dict[str, Any],
    reconstruction: Dict[str, Any],
    function: Dict[str, Any],
    visual_topology: Dict[str, Any],
    ledger: Dict[str, Any],
    closure: Dict[str, Any],
    part_grounding: Dict[str, Any],
    trust: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    capture = reconstruction.get("capture_coverage") if isinstance(reconstruction.get("capture_coverage"), dict) else {}
    stages = {stage.get("stage_id"): stage.get("status") for stage in ledger.get("stages") or [] if isinstance(stage, dict)}
    trust_dimensions = trust.get("trust_dimensions") if isinstance(trust.get("trust_dimensions"), dict) else {}
    dimensions = {
        "visual_observability": _dimension(
            _max_float(capture.get("score"), 0.72 if board else 0.0),
            _status_from_score(_max_float(capture.get("score"), 0.72 if board else 0.0)),
            "Photos and visual evidence are enough to create candidate inventory.",
            [
                f"{len(_list_dicts(board.get('components')))} component candidate(s)",
                f"{len(_list_dicts(board.get('connectors')))} connector candidate(s)",
                f"{len(_list_dicts(board.get('markings')))} marking candidate(s)",
            ],
        ),
        "part_identity": _dimension(
            _max_float(trust_dimensions.get("part_grounding"), function.get("confidence"), 0.0),
            _status_from_score(_max_float(trust_dimensions.get("part_grounding"), function.get("confidence"), 0.0)),
            "Component/marking identity confidence.",
            [str(row.get("canonical_part") or row.get("family")) for row in _list_dicts(part_grounding.get("matched_parts"))[:6]],
        ),
        "function_hypothesis": _dimension(
            _safe_float(function.get("confidence"), 0.0),
            _status_from_score(_safe_float(function.get("confidence"), 0.0)),
            "Likely board purpose inferred from markings, connectors, capabilities, and topology.",
            [str(row.get("function_id")) for row in _list_dicts(function.get("candidates"))[:5]],
        ),
        "visual_topology": _dimension(
            _safe_float(visual_topology.get("confidence"), 0.0),
            "pass" if visual_topology.get("available") else "open",
            "Candidate component/connector/trace topology from layout evidence.",
            [
                f"{len(_list_dicts(visual_topology.get('component_instances')))} component anchors",
                f"{len(_list_dicts(visual_topology.get('connector_hypotheses')))} connector hypotheses",
                f"{len(_list_dicts(visual_topology.get('connection_hypotheses')))} connection hypotheses",
            ],
        ),
        "measured_topology": _dimension(
            1.0 if stages.get("measured_topology") == "pass" else 0.0,
            str(stages.get("measured_topology") or "open"),
            "Measured pinout/topology authority.",
            _stage_evidence(ledger, "measured_topology"),
        ),
        "simulation": _dimension(
            1.0 if stages.get("electrical_simulation") == "pass" else 0.0,
            str(stages.get("electrical_simulation") or "open"),
            "Deterministic low-voltage simulation or bounded source/load envelope.",
            _stage_evidence(ledger, "electrical_simulation"),
        ),
        "bench_outcome": _dimension(
            1.0 if stages.get("controlled_bench") == "pass" else 0.0,
            str(stages.get("controlled_bench") or "open"),
            "Controlled first-power/function outcome.",
            _stage_evidence(ledger, "controlled_bench"),
        ),
        "release_authority": _dimension(
            1.0 if stages.get("production_repair") == "pass" else 0.0,
            str(stages.get("production_repair") or "open"),
            "Scoped production repair/reuse release authority.",
            _stage_evidence(ledger, "production_repair"),
        ),
        "active_closure": _dimension(
            _safe_float(closure.get("observability_score"), 0.0),
            "pass" if not _list_dicts(closure.get("next_best_tasks")) and closure.get("available") else "open",
            "Whether the engine has a concrete route to collapse unknowns.",
            [str(task.get("task_id") or task.get("category")) for task in _list_dicts(closure.get("next_best_tasks"))[:8]],
        ),
    }
    return dimensions


def _hypothesis_lattice(
    function: Dict[str, Any],
    part_grounding: Dict[str, Any],
    visual_topology: Dict[str, Any],
) -> Dict[str, Any]:
    candidates = []
    for row in _list_dicts(function.get("candidates")):
        candidates.append(
            {
                "hypothesis_id": str(row.get("function_id") or row.get("label") or "function"),
                "label": row.get("label"),
                "confidence": row.get("confidence"),
                "evidence": row.get("evidence") or [],
                "capabilities": row.get("capabilities") or [],
                "confirmation_required": row.get("confirmation_required") or [],
                "status": "leading" if row.get("function_id") == function.get("primary_function_id") else "alternate",
            }
        )
    return {
        "primary": function.get("primary_function_id") or "unknown",
        "candidates": candidates[:8],
        "grounded_parts": _list_dicts(part_grounding.get("matched_parts"))[:12],
        "visual_topology_candidates": {
            "available": bool(visual_topology.get("available")),
            "connector_hypotheses": _list_dicts(visual_topology.get("connector_hypotheses"))[:12],
            "connection_hypotheses": _list_dicts(visual_topology.get("connection_hypotheses"))[:12],
        },
    }


def _known_facts(
    *,
    board: Dict[str, Any],
    reconstruction: Dict[str, Any],
    visual_topology: Dict[str, Any],
    ledger: Dict[str, Any],
    workflow: Dict[str, Any],
    integrated: Dict[str, Any],
) -> List[Dict[str, Any]]:
    facts = []
    for key, label in [
        ("components", "component candidates"),
        ("connectors", "connector candidates"),
        ("markings", "marking candidates"),
        ("damage", "damage observations"),
    ]:
        rows = _list_dicts(board.get(key))
        if rows:
            facts.append(_fact(f"visual_{key}", label, "visual_candidate", f"{len(rows)} item(s)", rows[:10]))
    if reconstruction:
        facts.append(
            _fact(
                "multiview_reconstruction",
                "multi-photo reconstruction",
                "visual_candidate",
                f"{reconstruction.get('usable_observation_count', 0)} usable observation(s)",
                reconstruction.get("reconstruction_summary") or {},
            )
        )
    if visual_topology.get("available"):
        facts.append(
            _fact(
                "visual_topology",
                "visual topology hypothesis",
                "candidate_only",
                f"{len(_list_dicts(visual_topology.get('measurement_queue')))} measurement task(s)",
                visual_topology.get("readiness") or {},
            )
        )
    for stage in ledger.get("stages") or []:
        if isinstance(stage, dict) and stage.get("status") == "pass":
            facts.append(_fact(f"authority_{stage.get('stage_id')}", stage.get("title"), "authority", "pass", stage.get("evidence") or []))
    value = workflow.get("salvage_value_decision") if isinstance(workflow.get("salvage_value_decision"), dict) else {}
    if value:
        facts.append(_fact("salvage_value_decision", "reuse/salvage value decision", "economic", value.get("decision"), value))
    if integrated:
        facts.append(_fact("hardware_plan_status", "hardware plan status", "planning", integrated.get("status"), integrated.get("reason") or ""))
    return facts[:32]


def _unknowns(
    *,
    board: Dict[str, Any],
    reconstruction: Dict[str, Any],
    visual_topology: Dict[str, Any],
    closure: Dict[str, Any],
    ledger: Dict[str, Any],
    trust: Dict[str, Any],
) -> List[Dict[str, Any]]:
    unknowns: List[Dict[str, Any]] = []
    can = ledger.get("can") if isinstance(ledger.get("can"), dict) else {}
    if can.get("claim_production_repair_release"):
        return []
    capture = reconstruction.get("capture_coverage") if isinstance(reconstruction.get("capture_coverage"), dict) else {}
    for lane in capture.get("open_required_lanes") or []:
        unknowns.append(_unknown(f"capture_{lane}", "visual_coverage", f"Missing required capture lane: {lane}", "Add a targeted photo observation.", "multiview_reconstruction"))
    if not board:
        unknowns.append(_unknown("board_visual_evidence", "visual_coverage", "No normalized board_evidence.v1 is attached.", "Provide Qwen/local/manual board evidence.", "visual_inventory"))
    if board and not _list_dicts(board.get("markings")):
        unknowns.append(_unknown("marking_identity", "identity", "No readable component markings are grounded.", "Capture marking closeups or enter observed markings.", "part_grounding"))
    if board and not _list_dicts(board.get("connectors")):
        unknowns.append(_unknown("connector_inventory", "topology", "No connector inventory is grounded.", "Capture connector closeups and label candidate entry points.", "bench_template"))
    for task in _list_dicts(visual_topology.get("measurement_queue"))[:12]:
        unknowns.append(
            _unknown(
                str(task.get("task_id") or task.get("category") or "visual_topology_task"),
                "visual_topology",
                str(task.get("prompt") or task.get("summary") or "Visual topology candidate needs measurement."),
                "Measure or annotate the named topology candidate.",
                "measured_topology",
                evidence_type=task.get("type") or "measurement",
            )
        )
    for stage in ledger.get("stages") or []:
        if not isinstance(stage, dict) or stage.get("status") == "pass":
            continue
        for blocker in stage.get("blockers") or []:
            unknowns.append(_unknown(f"authority_{stage.get('stage_id')}", str(stage.get("stage_id")), str(blocker), str(stage.get("next_unlock") or ""), "authority_ledger"))
    measurement = trust.get("measurement_provenance") if isinstance(trust.get("measurement_provenance"), dict) else {}
    for category in measurement.get("missing_trusted_categories") or []:
        unknowns.append(_unknown(f"missing_measurement_{category}", "measurement", f"Missing trusted {category} measurement.", "Record trusted instrument/operator/timestamp/artifact evidence.", "production_authority"))
    for task in _list_dicts(closure.get("next_best_tasks"))[:16]:
        prompt = str(task.get("prompt") or "")
        if prompt:
            unknowns.append(
                _unknown(
                    str(task.get("task_id") or task.get("category") or "closure_task"),
                    str(task.get("category") or task.get("type") or "closure"),
                    prompt,
                    str(task.get("unlocks") or "evidence closure"),
                    "active_evidence_closure",
                    priority=_safe_float(task.get("priority"), 0.0),
                    evidence_type=task.get("type"),
                )
            )
    return _dedupe_unknowns(unknowns)[:48]


def _next_evidence_batch(
    closure: Dict[str, Any],
    workflow: Dict[str, Any],
    field: Dict[str, Any],
    unknowns: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    call = field.get("operational_call") if isinstance(field.get("operational_call"), dict) else {}
    if call:
        prompt = str(call.get("summary") or "")
        if prompt.lower().startswith(("measurement gate:", "review gate:", "outcome gate:")):
            prompt = str(call.get("why") or prompt)
        rows.append(
            {
                "action_id": call.get("action_id"),
                "source": "field_operator",
                "type": call.get("action_type"),
                "category": "operator_next_action",
                "priority": -4,
                "prompt": prompt,
                "why": call.get("why"),
                "procedure": call.get("procedure") or [],
                "unlocks": "next authority gate",
            }
        )
    for task in _list_dicts(closure.get("next_best_tasks"))[:18]:
        rows.append(_task_from_row(task, source="active_evidence_closure", base_priority=-2))
    protocol = workflow.get("measurement_protocol") if isinstance(workflow.get("measurement_protocol"), dict) else {}
    for step in _list_dicts(protocol.get("steps")):
        if step.get("status") not in {"open", "blocked"}:
            continue
        rows.append(
            {
                "action_id": step.get("step_id") or step.get("lane_id"),
                "source": "measurement_protocol",
                "type": "measurement" if step.get("category") not in {"review", "outcome"} else step.get("category"),
                "category": step.get("category"),
                "priority": -1 if step.get("status") == "blocked" else 1,
                "prompt": step.get("action"),
                "why": step.get("expected_result"),
                "procedure": [],
                "unlocks": step.get("required_before"),
            }
        )
    for unknown in unknowns[:12]:
        rows.append(
            {
                "action_id": f"resolve_{unknown.get('unknown_id')}",
                "source": "unknown_map",
                "type": unknown.get("evidence_type") or "evidence",
                "category": unknown.get("category"),
                "priority": _safe_float(unknown.get("priority"), 3.0) + 2,
                "prompt": unknown.get("resolution"),
                "why": unknown.get("summary"),
                "procedure": [],
                "unlocks": unknown.get("unlocks"),
            }
        )
    return _dedupe_tasks(rows)[:20]


def _operator_playbook(level: str, ledger: Dict[str, Any], next_batch: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    can = ledger.get("can") if isinstance(ledger.get("can"), dict) else {}
    return {
        "now": [str(task.get("prompt") or task.get("action_id")) for task in next_batch[:5] if task.get("prompt") or task.get("action_id")],
        "hold_until": _cannot_claim_yet(ledger, [])[:8],
        "safe_posture": (
            "production_release"
            if can.get("claim_production_repair_release")
            else "controlled_bench_only"
            if can.get("run_controlled_bench")
            else "measurement_capture_only"
            if can.get("use_visual_candidates")
            else "intake_only"
        ),
        "level": level,
    }


def _model_routes(
    reconstruction: Dict[str, Any],
    visual_topology: Dict[str, Any],
    next_batch: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    capture_prompts = []
    for request in _list_dicts(reconstruction.get("next_capture_requests"))[:6]:
        prompt = str(request.get("prompt") or request.get("request") or request.get("action") or "")
        if prompt:
            capture_prompts.append(prompt)
    measurement_prompts = [
        str(task.get("prompt"))
        for task in next_batch
        if str(task.get("type") or "") == "measurement" and task.get("prompt")
    ][:8]
    return {
        "qwen_vision": {
            "use_for": ["photo parsing", "marking closeups", "connector candidate extraction", "damage observation"],
            "next_prompts": capture_prompts,
            "never_treat_as": ["measured pinout", "safe power authorization", "production repair authority"],
        },
        "deepseek_or_text_reasoner": {
            "use_for": ["field advisory", "measurement ordering", "contradiction review", "project/use-case planning"],
            "next_prompts": measurement_prompts,
            "never_treat_as": ["instrument measurement", "terminal outcome"],
        },
        "deterministic_engine": {
            "use_for": ["topology-to-netlist", "simulation gate", "authority ledger", "release gating"],
            "visual_topology_available": bool(visual_topology.get("available")),
        },
    }


def _ceiling_projection(closure: Dict[str, Any], ledger: Dict[str, Any], score: float) -> Dict[str, Any]:
    next_unlocks = ledger.get("next_unlocks") if isinstance(ledger.get("next_unlocks"), list) else []
    return {
        "current_authority_level": ledger.get("current_authority_level"),
        "authority_ceiling_if_next_batch_closes": closure.get("authority_ceiling_if_next_batch_closes") or _fallback_ceiling(ledger),
        "score_if_next_batch_closes_estimate": round(min(0.96, score + 0.16 + 0.05 * min(len(next_unlocks), 3)), 3),
        "blocking_unlocks": next_unlocks[:6],
    }


def _evidence_graph(body: Dict[str, Any], analysis: Dict[str, Any], tasks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    session = {
        "session_id": str(body.get("session_id") or body.get("casefile_id") or "omniscience-map"),
        "title": body.get("goal") or body.get("description") or "arbitrary board",
        "evidence": {
            "captures": _capture_rows(body),
            "measurements": _measurement_rows(body, analysis),
        },
        "outcomes": _list_dicts(body.get("outcome_history") or body.get("outcomes")),
        "evidence_tasks": [
            {
                "task_id": task.get("action_id"),
                "type": task.get("type"),
                "status": "open",
                "priority": task.get("priority"),
                "prompt": task.get("prompt"),
            }
            for task in tasks
            if isinstance(task, dict)
        ],
        "analyses": [{"results": analysis}],
    }
    graph = BoardEvidenceGraphBuilder().build(session)
    return {
        "summary": graph.get("summary"),
        "grounded_claims": graph.get("grounded_claims", [])[:8],
        "weak_claims": graph.get("weak_claims", [])[:8],
        "next_grounding_actions": graph.get("next_grounding_actions", [])[:8],
        "claim_boundary": graph.get("claim_boundary"),
    }


def _weighted_score(dimensions: Dict[str, Dict[str, Any]]) -> float:
    weights = {
        "visual_observability": 0.10,
        "part_identity": 0.12,
        "function_hypothesis": 0.13,
        "visual_topology": 0.10,
        "measured_topology": 0.16,
        "simulation": 0.12,
        "bench_outcome": 0.12,
        "release_authority": 0.10,
        "active_closure": 0.05,
    }
    total = 0.0
    for key, weight in weights.items():
        total += weight * _safe_float((dimensions.get(key) or {}).get("score"), 0.0)
    return round(min(total, 1.0), 3)


def _omniscience_level(ledger: Dict[str, Any], dimensions: Dict[str, Dict[str, Any]], score: float) -> str:
    level = str(ledger.get("current_authority_level") or "no_authority")
    if level == "production_repair":
        return "scoped_production_repair_map"
    if level == "controlled_bench":
        return "bench_validated_board_map"
    if level == "electrical_simulation":
        return "simulation_backed_topology_map"
    if level == "measured_topology":
        return "measured_pinout_topology_map"
    if (dimensions.get("visual_topology") or {}).get("score", 0.0) >= 0.45:
        return "visual_topology_candidate_map"
    if (dimensions.get("function_hypothesis") or {}).get("score", 0.0) >= 0.45:
        return "function_identity_candidate_map"
    if score > 0.0:
        return "visual_intake_map"
    return "intake_required"


def _cannot_claim_yet(ledger: Dict[str, Any], unknowns: Sequence[Dict[str, Any]]) -> List[str]:
    rows = []
    can = ledger.get("can") if isinstance(ledger.get("can"), dict) else {}
    if not can.get("use_measured_pinout"):
        rows.append("measured pinout/topology")
    if not can.get("use_electrical_simulation"):
        rows.append("simulation-backed electrical behavior")
    if not can.get("claim_controlled_reuse"):
        rows.append("controlled reuse or bench-proven function")
    if not can.get("claim_production_repair_release"):
        rows.append("production repair/reuse release")
    rows.extend(str(row.get("summary")) for row in unknowns[:4] if row.get("summary"))
    return _dedupe(rows)[:10]


def _fallback_ceiling(ledger: Dict[str, Any]) -> str:
    current = str(ledger.get("current_authority_level") or "no_authority")
    order = ["no_authority", "visual_candidate", "measured_topology", "electrical_simulation", "controlled_bench", "production_repair"]
    try:
        index = order.index(current)
    except ValueError:
        index = 0
    return order[min(index + 1, len(order) - 1)]


def _dimension(score: float, status: str, summary: str, evidence: Sequence[Any]) -> Dict[str, Any]:
    score = round(max(0.0, min(float(score), 1.0)), 3)
    return {
        "score": score,
        "status": status,
        "summary": summary,
        "evidence": [str(item) for item in evidence if str(item or "").strip()][:10],
    }


def _fact(fact_id: str, label: Any, authority: str, value: Any, evidence: Any) -> Dict[str, Any]:
    return {
        "fact_id": fact_id,
        "label": str(label or fact_id),
        "authority": authority,
        "value": value,
        "evidence": evidence,
    }


def _unknown(
    unknown_id: str,
    category: str,
    summary: str,
    resolution: str,
    unlocks: str,
    *,
    priority: float = 0.0,
    evidence_type: Any = None,
) -> Dict[str, Any]:
    return {
        "unknown_id": unknown_id,
        "category": category,
        "summary": summary,
        "resolution": resolution,
        "unlocks": unlocks,
        "priority": priority,
        "evidence_type": evidence_type,
    }


def _task_from_row(task: Dict[str, Any], *, source: str, base_priority: float) -> Dict[str, Any]:
    return {
        "action_id": task.get("task_id") or task.get("action_id") or task.get("category"),
        "source": source,
        "type": task.get("type"),
        "category": task.get("category"),
        "priority": base_priority + _safe_float(task.get("priority"), 0.0),
        "prompt": task.get("prompt") or task.get("summary") or task.get("action"),
        "why": task.get("why") or task.get("reason"),
        "procedure": task.get("procedure") or [],
        "unlocks": task.get("unlocks"),
    }


def _stage_evidence(ledger: Dict[str, Any], stage_id: str) -> List[str]:
    for stage in ledger.get("stages") or []:
        if isinstance(stage, dict) and stage.get("stage_id") == stage_id:
            return [*(stage.get("evidence") or []), *(stage.get("blockers") or [])]
    return []


def _capture_rows(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    photo_set = body.get("board_photo_set") if isinstance(body.get("board_photo_set"), dict) else {}
    for row in _list_dicts(photo_set.get("photo_observations")):
        rows.append(
            {
                "capture_id": row.get("photo_id") or row.get("capture_id") or row.get("id"),
                "kind": row.get("view_hint") or row.get("label") or "photo",
                "filename": row.get("filename"),
                "notes": row.get("notes"),
            }
        )
    return rows[:40]


def _measurement_rows(body: Dict[str, Any], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for value in [
        body.get("measurements"),
        body.get("bench_measurements"),
        analysis.get("measurements"),
        (analysis.get("topology_evidence_bridge") or {}).get("measurement_rows") if isinstance(analysis.get("topology_evidence_bridge"), dict) else None,
    ]:
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    return rows[:80]


def _dedupe_tasks(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        prompt = str(row.get("prompt") or row.get("action_id") or "").strip()
        if not prompt:
            continue
        key = (str(row.get("type") or ""), str(row.get("category") or ""), prompt.lower())
        if key in seen:
            continue
        seen.add(key)
        kept.append(dict(row))
    kept.sort(key=lambda row: (_safe_float(row.get("priority"), 99.0), str(row.get("source") or "")))
    return kept


def _dedupe_unknowns(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept = []
    seen = set()
    for row in rows:
        key = (str(row.get("unknown_id") or ""), str(row.get("summary") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        kept.append(dict(row))
    kept.sort(key=lambda row: (_safe_float(row.get("priority"), 99.0), str(row.get("category") or "")))
    return kept


def _status_from_score(score: float) -> str:
    if score >= 0.82:
        return "pass"
    if score >= 0.45:
        return "candidate"
    if score > 0:
        return "weak"
    return "open"


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _max_float(*values: Any) -> float:
    return max(_safe_float(value, 0.0) for value in values)


def _dedupe(values: Iterable[Any]) -> List[str]:
    rows = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        rows.append(text)
    return rows
