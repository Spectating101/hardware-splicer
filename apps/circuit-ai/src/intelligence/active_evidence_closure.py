"""Plan the next evidence campaign for arbitrary board authority.

This layer is the active loop above visual reconstruction, topology hypotheses,
bench protocols, and trust scoring. It does not create authority. It ranks the
next photos, measurements, outcome records, and release artifacts that would
collapse current unknowns toward a scoped repair/reuse release.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from src.intelligence.bench_topology_capture import build_bench_capture_template


SCHEMA_VERSION = "active_evidence_closure_plan.v1"


def enrich_payload_with_active_evidence_closure_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach an active evidence closure plan to payload analysis."""

    body = dict(payload or {})
    analysis = dict(body.get("analysis") if isinstance(body.get("analysis"), dict) else {})
    plan = build_active_evidence_closure_plan(body, analysis=analysis)
    if not plan.get("available"):
        return body

    analysis["active_evidence_closure_plan"] = plan
    analysis["active_next_evidence_tasks"] = plan.get("next_best_tasks", [])
    body["analysis"] = analysis
    body["active_evidence_closure_plan"] = plan
    return body


def build_active_evidence_closure_plan(
    payload: Dict[str, Any],
    *,
    analysis: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a deterministic campaign for reducing board uncertainty."""

    body = payload or {}
    ctx = analysis if isinstance(analysis, dict) else body.get("analysis") if isinstance(body.get("analysis"), dict) else {}
    board = _first_dict(ctx.get("board_evidence"), body.get("board_evidence"))
    reconstruction = _first_dict(ctx.get("multiview_board_reconstruction"), body.get("multiview_board_reconstruction"))
    visual_topology = _first_dict(ctx.get("visual_topology_hypothesis"), body.get("visual_topology_hypothesis"))
    trust = _first_dict(ctx.get("arbitrary_board_trust_assessment"), body.get("arbitrary_board_trust_assessment"))
    bench_protocol = _first_dict(ctx.get("bench_protocol_pack"), body.get("bench_protocol_pack"))
    topology_authority = _first_dict(ctx.get("topology_authority"), body.get("topology_authority"))
    part_grounding = _first_dict(ctx.get("part_grounding"), body.get("part_grounding"))
    production_release = _first_dict(body.get("production_release"), body.get("release_manifest"))
    outcome_history = _list_dicts(body.get("outcome_history") or body.get("outcomes"))

    if not any([board, reconstruction, visual_topology, trust, bench_protocol, topology_authority]):
        return {"schema_version": SCHEMA_VERSION, "available": False, "reason": "No board evidence workflow state is available."}

    template = build_bench_capture_template(
        reference_topology=_first_dict(body.get("reference_topology"), body.get("topology_reference")) or None,
        board_evidence=board or None,
    )
    state = _evidence_state(
        board=board,
        reconstruction=reconstruction,
        visual_topology=visual_topology,
        trust=trust,
        topology_authority=topology_authority,
        part_grounding=part_grounding,
        production_release=production_release,
        outcome_history=outcome_history,
        template=template,
    )
    lanes = _closure_lanes(
        state=state,
        reconstruction=reconstruction,
        visual_topology=visual_topology,
        trust=trust,
        bench_protocol=bench_protocol,
        part_grounding=part_grounding,
        template=template,
    )
    tasks = _rank_tasks(_dedupe_tasks([task for lane in lanes for task in lane.get("tasks", [])]))
    next_capture = [task for task in tasks if task.get("type") == "capture"][:8]
    next_measurement = [task for task in tasks if task.get("type") == "measurement"][:20]
    blocked_claims = _blocked_claims(visual_topology, trust, state)
    return {
        "schema_version": SCHEMA_VERSION,
        "available": True,
        "current_stage": _current_stage(state),
        "observability_score": _observability_score(state),
        "authority_ceiling_if_next_batch_closes": _authority_ceiling(state),
        "evidence_state": state,
        "closure_lanes": lanes,
        "next_best_tasks": tasks[:32],
        "next_capture_set": next_capture,
        "next_measurement_set": next_measurement,
        "bench_capture_template_preview": {
            "schema_version": template.get("schema_version"),
            "connector_count": len(template.get("connectors") or []),
            "measurement_count": len(template.get("measurements") or []),
            "connector_refs": [
                {
                    "ref": connector.get("ref"),
                    "label": connector.get("label"),
                    "pin_count": connector.get("pin_count"),
                    "reference_seed": bool(connector.get("reference_seed")),
                    "reference_note": connector.get("reference_note") or "",
                }
                for connector in _list_dicts(template.get("connectors"))[:12]
            ],
            "first_measurements": template.get("measurements", [])[:10],
        },
        "unlock_sequence": _unlock_sequence(state),
        "can_claim_now": _can_claim_now(state),
        "cannot_claim_yet": blocked_claims,
        "claim_boundary": (
            "This plan ranks evidence to collect next. It does not authorize power, repair, splice, sale, "
            "or production release until measured topology, trusted measurements, terminal outcome, and release artifacts pass."
        ),
        "policy": {
            "active_loop_can_request_photos": True,
            "active_loop_can_seed_bench_templates": True,
            "active_loop_cannot_turn_reference_or_vision_into_measurement": True,
            "production_authority_remains_external_gate": True,
        },
    }


def _evidence_state(
    *,
    board: Dict[str, Any],
    reconstruction: Dict[str, Any],
    visual_topology: Dict[str, Any],
    trust: Dict[str, Any],
    topology_authority: Dict[str, Any],
    part_grounding: Dict[str, Any],
    production_release: Dict[str, Any],
    outcome_history: Sequence[Dict[str, Any]],
    template: Dict[str, Any],
) -> Dict[str, Any]:
    trust_dimensions = trust.get("trust_dimensions") if isinstance(trust.get("trust_dimensions"), dict) else {}
    measurement = trust.get("measurement_provenance") if isinstance(trust.get("measurement_provenance"), dict) else {}
    functional = trust.get("functional_outcome") if isinstance(trust.get("functional_outcome"), dict) else {}
    release = trust.get("release_package") if isinstance(trust.get("release_package"), dict) else {}
    components = _list_dicts(board.get("components"))
    connectors = _list_dicts(board.get("connectors"))
    markings = _list_dicts(board.get("markings"))
    damage = _list_dicts(board.get("damage"))
    capture_coverage = reconstruction.get("capture_coverage") if isinstance(reconstruction.get("capture_coverage"), dict) else {}
    if not capture_coverage:
        board_reconstruction = board.get("multiview_reconstruction") if isinstance(board.get("multiview_reconstruction"), dict) else {}
        capture_coverage = {
            "score": board_reconstruction.get("capture_coverage_score"),
            "required_complete": board_reconstruction.get("capture_coverage_complete"),
            "open_required_lanes": [],
            "recommended_open_lanes": [],
        }
    usable_photos = int(
        reconstruction.get("usable_observation_count")
        or ((board.get("multiview_reconstruction") or {}).get("usable_observation_count") if isinstance(board.get("multiview_reconstruction"), dict) else 0)
        or (1 if board else 0)
    )
    trusted_categories = set(str(item) for item in measurement.get("trusted_categories") or [])
    missing_categories = measurement.get("missing_trusted_categories")
    if not isinstance(missing_categories, list):
        missing_categories = sorted({"resistance", "continuity", "voltage", "current", "thermal"} - trusted_categories)
    outcome_contract = _outcome_contract_state(functional, outcome_history)
    return {
        "photo_observation_count": usable_photos,
        "component_count": len(components),
        "connector_count": len(connectors),
        "marking_count": len(markings),
        "damage_item_count": len(damage),
        "visual_coverage_score": _safe_float(capture_coverage.get("score"), 0.0),
        "visual_coverage_complete": bool(capture_coverage.get("required_complete")),
        "open_visual_coverage_lanes": [str(item) for item in capture_coverage.get("open_required_lanes") or []],
        "recommended_visual_coverage_lanes": [str(item) for item in capture_coverage.get("recommended_open_lanes") or []],
        "visual_topology_available": bool(visual_topology.get("available")),
        "visual_measurement_task_count": len(visual_topology.get("measurement_queue") or []),
        "bench_template_connector_count": len(template.get("connectors") or []),
        "bench_template_measurement_count": len(template.get("measurements") or []),
        "topology_measurement_backed": bool(topology_authority.get("measurement_backed")),
        "pinout_known": bool(topology_authority.get("pinout_known")),
        "shorts_detected": bool(topology_authority.get("shorts_detected")),
        "unknown_pin_count": int(topology_authority.get("unknown_pin_count") or 0),
        "trusted_measurement_count": int(measurement.get("trusted_measurement_count") or topology_authority.get("trusted_measurement_count") or 0),
        "trusted_measurement_categories": sorted(trusted_categories),
        "missing_trusted_measurement_categories": missing_categories,
        "terminal_outcome_recorded": bool(functional.get("available") or outcome_contract.get("recorded")),
        "terminal_function_success": bool(functional.get("terminal_success") or outcome_contract.get("successful")),
        "terminal_outcome_contract_complete": bool(outcome_contract.get("complete")),
        "missing_outcome_contract_fields": outcome_contract.get("missing_fields") or [],
        "terminal_success": bool((functional.get("terminal_success") or outcome_contract.get("successful")) and outcome_contract.get("complete")),
        "release_package_complete": bool(release.get("complete") or _release_complete(production_release)),
        "part_grounding_available": bool(part_grounding.get("available") or part_grounding.get("matched_parts") or trust_dimensions.get("part_grounding", 0.0) >= 0.35),
        "trust_level": trust.get("level") or "unknown",
        "trust_score": _safe_float(trust.get("score"), 0.0),
        "production_readiness_score": _safe_float(trust.get("production_readiness_score"), 0.0),
        "trust_dimensions": trust_dimensions,
    }


def _closure_lanes(
    *,
    state: Dict[str, Any],
    reconstruction: Dict[str, Any],
    visual_topology: Dict[str, Any],
    trust: Dict[str, Any],
    bench_protocol: Dict[str, Any],
    part_grounding: Dict[str, Any],
    template: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [
        _visual_lane(state, reconstruction),
        _identity_lane(state, part_grounding),
        _topology_lane(state, visual_topology, template),
        _bench_authority_lane(state, bench_protocol, trust, template),
        _outcome_lane(state, trust),
        _release_lane(state, trust),
    ]


def _visual_lane(state: Dict[str, Any], reconstruction: Dict[str, Any]) -> Dict[str, Any]:
    complete = (
        bool(state.get("visual_coverage_complete"))
        or (
            state.get("visual_coverage_score", 0.0) >= 0.82
            and state.get("component_count", 0) > 0
            and state.get("connector_count", 0) > 0
            and state.get("marking_count", 0) > 0
        )
        or _scoped_measured_release_evidence_exists(state)
    )
    tasks = []
    if not complete:
        requests = _list_dicts(reconstruction.get("next_capture_requests"))
        if requests:
            for index, request in enumerate(requests[:8], start=1):
                prompt = str(request.get("prompt") or request.get("request") or request.get("action") or request.get("summary") or "").strip()
                if prompt:
                    tasks.append(_task(f"closure_capture_{index}", "capture", "visual_coverage", 0, prompt, "multiview_reconstruction"))
        tasks.extend(_default_capture_tasks(state))
    return _lane(
        "visual_coverage",
        "Cross-view visual coverage",
        "complete" if complete else "open",
        "Get enough non-rigid photo observations to cross-check markings, connectors, damage, and placement.",
        tasks,
    )


def _identity_lane(state: Dict[str, Any], part_grounding: Dict[str, Any]) -> Dict[str, Any]:
    complete = bool(state.get("part_grounding_available") or _scoped_measured_release_evidence_exists(state))
    tasks = []
    if not complete:
        for task in _list_dicts(part_grounding.get("grounding_tasks"))[:8]:
            prompt = str(task.get("prompt") or task.get("action") or "").strip()
            if prompt:
                tasks.append({**task, "source": task.get("source") or "active_evidence_closure"})
        tasks.append(
            _task(
                "closure_identity_markings",
                "capture",
                "identity_grounding",
                1,
                "Capture readable close-ups of every IC marking, connector label, regulator marking, crystal, and silkscreen model text.",
                "visible_marking_catalog_grounding",
            )
        )
        tasks.append(
            _task(
                "closure_identity_catalog",
                "review",
                "identity_grounding",
                2,
                "Resolve visible markings against public datasheets or product pinouts before relying on function claims.",
                "part_grounding",
            )
        )
    return _lane(
        "identity_grounding",
        "Part and product identity",
        "complete" if complete else "open",
        "Ground board function claims in visible markings, known packages, public pinouts, or datasheets.",
        tasks,
    )


def _topology_lane(state: Dict[str, Any], visual_topology: Dict[str, Any], template: Dict[str, Any]) -> Dict[str, Any]:
    complete = bool(state.get("topology_measurement_backed") and state.get("pinout_known") and not state.get("shorts_detected"))
    tasks: List[Dict[str, Any]] = []
    if not complete:
        for task in _list_dicts(visual_topology.get("measurement_queue"))[:12]:
            row = dict(task)
            row.setdefault("source", "visual_topology_hypothesis")
            row.setdefault("usable_for", ["repair", "reuse", "splice", "training"])
            tasks.append(row)
        for index, measurement in enumerate(_list_dicts(template.get("measurements"))[:16], start=1):
            target = str(measurement.get("target") or "").strip()
            notes = str(measurement.get("notes") or "").strip()
            if not target:
                continue
            tasks.append(
                _task(
                    f"closure_template_measurement_{index}",
                    "measurement",
                    str(measurement.get("kind") or "topology"),
                    0 if index <= 6 else 1,
                    f"Record {target}. {notes}".strip(),
                    "bench_topology_capture.v1",
                )
            )
    return _lane(
        "measured_topology",
        "Measured topology and pinout",
        "complete" if complete else "open",
        "Turn visual/reference topology into measured connector, pinout, continuity, no-short, voltage, and thermal evidence.",
        tasks,
    )


def _bench_authority_lane(
    state: Dict[str, Any],
    bench_protocol: Dict[str, Any],
    trust: Dict[str, Any],
    template: Dict[str, Any],
) -> Dict[str, Any]:
    missing = set(str(item) for item in state.get("missing_trusted_measurement_categories") or [])
    complete = not missing and state.get("trusted_measurement_count", 0) > 0
    tasks: List[Dict[str, Any]] = []
    if not complete and bench_protocol.get("step_count"):
        title = str(bench_protocol.get("title") or "bench protocol")
        categories = ", ".join(bench_protocol.get("required_measurement_categories") or [])
        tasks.append(
            _task(
                "closure_run_bench_protocol",
                "measurement",
                "bench_protocol",
                -1,
                f"Run the {title} and attach trusted artifacts for: {categories}.",
                "bench_protocol_pack",
            )
        )
        for step in _list_dicts(bench_protocol.get("steps"))[:8]:
            action = str(step.get("action") or step.get("prompt") or step.get("description") or "").strip()
            if action:
                tasks.append(
                    _task(
                        f"closure_protocol_{_safe_id(step.get('step_id') or action)}",
                        "measurement" if str(step.get("category") or "") != "review" else "review",
                        str(step.get("category") or "bench"),
                        0 if str(step.get("category") or "") in missing else 1,
                        action,
                        "trusted_measurement_artifact",
                    )
                )
    if not complete:
        for category in sorted(missing):
            tasks.append(
                _task(
                    f"closure_missing_{_safe_id(category)}",
                    "measurement",
                    category,
                    0,
                    f"Attach trusted {category} evidence with instrument id, calibration status, operator, timestamp, and artifact URI.",
                    "trusted_measurement_provenance",
                )
            )
        for gap in _string_list(trust.get("blocking_gaps"))[:10]:
            if "measurement" in gap.lower() or "evidence" in gap.lower():
                tasks.append(_task(f"closure_gap_{_safe_id(gap)[:32]}", "measurement", "authority_gap", 1, gap, "trust_gap_closure"))
    return _lane(
        "trusted_bench_evidence",
        "Trusted bench evidence",
        "complete" if complete else "open",
        "Record trusted measurements with provenance so authority lanes can actually close.",
        tasks,
    )


def _outcome_lane(state: Dict[str, Any], trust: Dict[str, Any]) -> Dict[str, Any]:
    complete = bool(state.get("terminal_success") and state.get("terminal_outcome_contract_complete"))
    tasks = []
    if not complete:
        functional = trust.get("functional_outcome") if isinstance(trust.get("functional_outcome"), dict) else {}
        for prompt in _string_list(functional.get("missing_requirements")):
            tasks.append(_task(f"closure_outcome_{_safe_id(prompt)}", "outcome", "terminal_outcome", 1, prompt, "outcome_history"))
        missing_fields = [str(field) for field in state.get("missing_outcome_contract_fields") or [] if str(field).strip()]
        if missing_fields:
            tasks.append(
                _task(
                    "closure_complete_outcome_contract",
                    "outcome",
                    "terminal_outcome",
                    0,
                    f"Complete outcome fields: {', '.join(missing_fields)}.",
                    "hardware_outcome_contract",
                )
            )
        tasks.append(
            _task(
                "closure_terminal_outcome",
                "outcome",
                "terminal_outcome",
                1,
                "Record terminal outcome with selected resources used, first-power result, thermal result, output_function_verified, evidence URI, cost, value, time, and deviations.",
                "outcome_history",
            )
        )
    return _lane(
        "terminal_outcome",
        "Terminal functional outcome",
        "complete" if complete else "open",
        "Prove the scoped reused function worked after the evidence-gated build or repair trial.",
        tasks,
    )


def _release_lane(state: Dict[str, Any], trust: Dict[str, Any]) -> Dict[str, Any]:
    complete = bool(state.get("release_package_complete"))
    tasks = []
    if not complete:
        release = trust.get("release_package") if isinstance(trust.get("release_package"), dict) else {}
        for prompt in _string_list(release.get("missing_requirements")):
            tasks.append(_task(f"closure_release_{_safe_id(prompt)}", "release", "release_manifest", 2, prompt, "production_release"))
        tasks.append(
            _task(
                "closure_release_manifest",
                "release",
                "release_manifest",
                2,
                "Attach production_release with release_id, selected_resource_ids, released_by, released_at, scope_statement, artifacts, acceptance_reviewed, and repeatability_count.",
                "production_release",
            )
        )
    return _lane(
        "release_package",
        "Release package",
        "complete" if complete else "open",
        "Package the scoped claim so the project can show exactly what is proven and what remains excluded.",
        tasks,
    )


def _default_capture_tasks(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    if state.get("photo_observation_count", 0) < 3:
        tasks.append(
            _task(
                "closure_capture_overview",
                "capture",
                "visual_coverage",
                0,
                "Capture several non-identical board observations: whole-board overview with scale, angled view, connector edge, and any backside/hidden area that exists.",
                "multiview_reconstruction",
            )
        )
    if state.get("connector_count", 0) == 0:
        tasks.append(
            _task(
                "closure_capture_connectors",
                "capture",
                "visual_coverage",
                0,
                "Capture close-ups of every connector, header, pad row, test pad cluster, and cable entry with orientation visible.",
                "connector_hypotheses",
            )
        )
    if state.get("marking_count", 0) == 0:
        tasks.append(
            _task(
                "closure_capture_markings",
                "capture",
                "visual_coverage",
                1,
                "Capture readable markings and silkscreen text for ICs, regulators, oscillators, connectors, jumpers, and board model labels.",
                "part_grounding",
            )
        )
    if state.get("damage_item_count", 0) == 0:
        tasks.append(
            _task(
                "closure_capture_damage_review",
                "capture",
                "visual_coverage",
                2,
                "Capture a damage and safety review pass: battery areas, hot spots, corrosion, burns, cracked parts, bodge wires, and power input path.",
                "hazard_profile",
            )
        )
    return tasks


def _lane(lane_id: str, title: str, status: str, objective: str, tasks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    ranked = _rank_tasks(_dedupe_tasks(tasks))
    return {
        "lane_id": lane_id,
        "title": title,
        "status": status,
        "objective": objective,
        "task_count": len(ranked),
        "tasks": ranked[:32],
    }


def _task(
    task_id: str,
    task_type: str,
    category: str,
    priority: int,
    prompt: str,
    unlocks: str,
) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "type": task_type,
        "category": category,
        "status": "open",
        "priority": priority,
        "prompt": prompt,
        "source": "active_evidence_closure_plan",
        "unlocks": unlocks,
        "usable_for": ["repair", "reuse", "splice", "production_release", "portfolio_demo", "training"],
    }


def _rank_tasks(tasks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rank = {
        "capture": 0,
        "measurement": 1,
        "review": 2,
        "outcome": 3,
        "release": 4,
    }
    rows = [dict(task) for task in tasks if isinstance(task, dict) and str(task.get("prompt") or "").strip()]
    rows.sort(key=lambda task: (int(task.get("priority") or 0), rank.get(str(task.get("type") or ""), 9), str(task.get("prompt") or "")))
    return rows


def _blocked_claims(visual_topology: Dict[str, Any], trust: Dict[str, Any], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for claim in _list_dicts(visual_topology.get("blocked_claims")):
        claim_name = str(claim.get("claim") or "visual_topology_claim")
        if claim_name == "pinout_known" and state.get("pinout_known"):
            continue
        if claim_name == "safe_power_or_splice" and _scoped_measured_release_evidence_exists(state):
            continue
        if claim_name == "netlist_or_trace_topology" and state.get("topology_measurement_backed"):
            rows.append(
                {
                    "claim": "full_hidden_board_netlist_or_trace_topology",
                    "status": "outside_current_scope",
                    "reason": "Measured topology covers the captured connector/reuse scope, not every hidden board net, via, inner layer, or backside route.",
                    "required_evidence": "Full schematic/CAD source, exhaustive continuity map, or explicit inspection of the additional scope.",
                }
            )
            continue
        rows.append(
            {
                "claim": claim_name,
                "status": claim.get("status") or "blocked",
                "reason": claim.get("reason") or claim.get("required_evidence") or "Evidence is not closed.",
                "required_evidence": claim.get("required_evidence") or "Measured topology and trusted bench evidence.",
            }
        )
    for gap in _string_list(trust.get("blocking_gaps")):
        rows.append(
            {
                "claim": "production_or_splice_authority",
                "status": "blocked",
                "reason": gap,
                "required_evidence": "Close the active evidence closure plan lanes.",
            }
        )
    if not rows and not state.get("release_package_complete"):
        rows.append(
            {
                "claim": "production_release",
                "status": "blocked",
                "reason": "Release package is not complete.",
                "required_evidence": "Terminal outcome and production_release manifest.",
            }
        )
    return _dedupe_claims(rows)[:16]


def _unlock_sequence(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "step": "capture_coverage",
            "unlocks": "cross-view board identity, connector candidates, damage review",
            "status": "done" if state.get("visual_coverage_complete") else "open",
        },
        {
            "step": "identity_grounding",
            "unlocks": "credible board/function hypotheses and public pinout candidates",
            "status": "done" if state.get("part_grounding_available") else "open",
        },
        {
            "step": "measured_topology",
            "unlocks": "pin-level splice contracts and controlled first-power path",
            "status": "done" if state.get("topology_measurement_backed") and state.get("pinout_known") else "open",
        },
        {
            "step": "trusted_bench_evidence",
            "unlocks": "repair authority lanes for resistance, continuity, voltage, current, and thermal checks",
            "status": "done" if not state.get("missing_trusted_measurement_categories") and state.get("trusted_measurement_count", 0) else "open",
        },
        {
            "step": "terminal_outcome",
            "unlocks": "real value proof that the reused/repaired function worked",
            "status": "done" if state.get("terminal_success") and state.get("terminal_outcome_contract_complete") else "open",
        },
        {
            "step": "release_package",
            "unlocks": "portfolio/demo release claim with explicit scope and artifacts",
            "status": "done" if state.get("release_package_complete") else "open",
        },
    ]


def _can_claim_now(state: Dict[str, Any]) -> List[str]:
    claims = []
    if state.get("component_count") or state.get("connector_count"):
        claims.append("visible board candidate inventory")
    if state.get("visual_topology_available"):
        claims.append("visual topology measurement plan")
    if state.get("topology_measurement_backed") and state.get("pinout_known"):
        claims.append("measured connector topology for captured scope")
    if state.get("terminal_success") and state.get("terminal_outcome_contract_complete"):
        claims.append("terminal function outcome for selected resources")
    if state.get("release_package_complete"):
        claims.append("release package metadata is complete")
    return claims or ["baseline evidence intake required"]


def _current_stage(state: Dict[str, Any]) -> str:
    if state.get("release_package_complete") and state.get("terminal_success") and not state.get("missing_trusted_measurement_categories"):
        return "release_closure"
    if state.get("terminal_function_success") or state.get("terminal_outcome_recorded"):
        return "release_packaging"
    if state.get("topology_measurement_backed") and state.get("pinout_known"):
        return "functional_outcome_capture"
    if state.get("visual_topology_available") or state.get("bench_template_measurement_count"):
        return "active_topology_closure"
    if state.get("photo_observation_count"):
        return "visual_capture_closure"
    return "baseline_intake"


def _observability_score(state: Dict[str, Any]) -> float:
    dims = state.get("trust_dimensions") if isinstance(state.get("trust_dimensions"), dict) else {}
    if dims:
        return round(
            _clamp(
                0.35 * _safe_float(dims.get("visual_coverage"), 0.0)
                + 0.22 * _safe_float(dims.get("part_grounding"), 0.0)
                + 0.28 * _safe_float(dims.get("topology_confidence"), 0.0)
                + 0.15 * _safe_float(dims.get("evidence_independence"), 0.0)
            ),
            3,
        )
    score = 0.0
    score += min(0.18, 0.18 * state.get("visual_coverage_score", 0.0))
    score += min(0.25, 0.08 * state.get("photo_observation_count", 0))
    score += min(0.20, 0.04 * state.get("component_count", 0))
    score += min(0.20, 0.05 * state.get("connector_count", 0))
    score += 0.15 if state.get("part_grounding_available") else 0.0
    score += 0.20 if state.get("visual_topology_available") else 0.0
    return round(_clamp(score), 3)


def _authority_ceiling(state: Dict[str, Any]) -> float:
    if state.get("release_package_complete") and state.get("terminal_success") and not state.get("missing_trusted_measurement_categories"):
        return 1.0
    ceiling = 0.35
    if state.get("photo_observation_count", 0) >= 3:
        ceiling += 0.08
    if state.get("part_grounding_available"):
        ceiling += 0.10
    if state.get("bench_template_measurement_count"):
        ceiling += 0.10
    if state.get("topology_measurement_backed") and state.get("pinout_known"):
        ceiling += 0.20
    if not state.get("missing_trusted_measurement_categories"):
        ceiling += 0.12
    if state.get("terminal_outcome_recorded"):
        ceiling += 0.08
    if state.get("release_package_complete"):
        ceiling += 0.07
    return round(_clamp(ceiling), 3)


def _release_complete(release: Dict[str, Any]) -> bool:
    if not release:
        return False
    return all(
        [
            release.get("release_id"),
            release.get("selected_resource_ids"),
            release.get("released_by") or release.get("approved_by"),
            release.get("released_at"),
            release.get("scope_statement"),
            release.get("artifact_uris") or release.get("artifact_uri") or release.get("evidence_uri"),
            release.get("acceptance_reviewed") is True,
            _safe_int(release.get("repeatability_count") or release.get("sample_count") or release.get("validated_unit_count"), 0) >= 1,
        ]
    )


def _outcome_contract_state(functional: Dict[str, Any], outcome_history: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    latest = _latest_outcome(outcome_history)
    if not latest:
        functional_missing = _string_list(functional.get("missing_requirements"))
        return {
            "recorded": bool(functional.get("available")),
            "successful": bool(functional.get("terminal_success")),
            "complete": bool(functional.get("available") and functional.get("terminal_success") and not functional_missing),
            "missing_fields": [],
        }
    decision = str(latest.get("decision") or latest.get("status") or latest.get("result") or "").strip().lower().replace(" ", "_")
    successful = decision in {"built", "repaired", "reused", "sold"}
    fields = {
        "decision": bool(decision),
        "selected_resource_ids_used": bool(
            latest.get("selected_resource_ids")
            or latest.get("selected_resource_ids_used")
            or latest.get("resource_ids")
            or latest.get("resource_id")
        ),
        "measurements_recorded": latest.get("measurements_recorded") not in {None, "", False},
        "cash_spent_usd": latest.get("cash_spent_usd") is not None,
        "value_recovered_usd": latest.get("value_recovered_usd") is not None,
        "time_spent_minutes": latest.get("time_spent_minutes") is not None,
        "deviations_from_plan": latest.get("deviations_from_plan") is not None,
        "failure_or_stop_reason": bool(
            latest.get("failure_or_stop_reason")
            or latest.get("reason")
            or latest.get("stop_reason")
            or successful
        ),
        "output_function_verified": latest.get("output_function_verified") is True,
        "first_power_result": str(latest.get("first_power_result") or "").strip().lower() in {"pass", "passed", "ok", "normal", "success", "true"},
        "thermal_result": str(latest.get("thermal_result") or "").strip().lower() in {"pass", "passed", "ok", "normal", "stable", "success", "true"},
        "evidence_uri": bool(latest.get("evidence_uri") or latest.get("artifact_uri") or latest.get("test_report_uri")),
    }
    missing = [field for field, present in fields.items() if not present]
    return {
        "recorded": True,
        "successful": successful,
        "complete": not missing,
        "missing_fields": missing,
    }


def _latest_outcome(outcome_history: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [row for row in outcome_history if isinstance(row, dict)]
    return rows[-1] if rows else {}


def _scoped_measured_release_evidence_exists(state: Dict[str, Any]) -> bool:
    return bool(
        state.get("topology_measurement_backed")
        and state.get("pinout_known")
        and state.get("trusted_measurement_count", 0) > 0
        and not state.get("missing_trusted_measurement_categories")
    )


def _dedupe_tasks(tasks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for task in tasks:
        if not isinstance(task, dict):
            continue
        prompt = str(task.get("prompt") or "").strip()
        key = (str(task.get("type") or ""), prompt.lower())
        if not prompt or key in seen:
            continue
        seen.add(key)
        kept.append(dict(task))
    return kept


def _dedupe_claims(claims: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for claim in claims:
        key = (str(claim.get("claim") or ""), str(claim.get("reason") or ""))
        if key in seen:
            continue
        seen.add(key)
        kept.append(claim)
    return kept


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dedupe(values: Iterable[Any]) -> List[Any]:
    rows = []
    seen = set()
    for value in values:
        if value in (None, ""):
            continue
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        rows.append(value)
    return rows


def _safe_id(value: Any) -> str:
    text = str(value or "item").strip().lower()
    chars = [char if char.isalnum() else "_" for char in text]
    return "_".join(part for part in "".join(chars).split("_") if part) or "item"


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


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
