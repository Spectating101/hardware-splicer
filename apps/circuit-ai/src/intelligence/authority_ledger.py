"""Unified authority ledger for board repair/reuse/splice claims.

Models can create candidate evidence; measurements and deterministic gates grant
authority. This module exposes that ladder as one compact auditable record.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.intelligence.design_test_kit import build_design_test_kit
from src.intelligence.hardware_plan import HardwarePlanOrchestrator


SCHEMA_VERSION = "hardware_authority_ledger.v1"

LEVELS = [
    "no_authority",
    "visual_candidate",
    "measured_topology",
    "electrical_simulation",
    "controlled_bench",
    "production_repair",
]


def build_authority_ledger(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build a one-page authority ledger for a board/design/reuse claim."""

    body = dict(payload or {})
    plan = _hardware_plan(body)
    analysis = plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {}
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    test_kit = _design_test_kit(body)

    visual = _visual_state(body, analysis)
    topology = _topology_state(body, analysis)
    simulation = _simulation_state(test_kit)
    simulation = _gate_simulation_by_topology(simulation, topology)
    bench = _bench_state(body, analysis)
    production = _production_state(integrated, body, analysis)

    stages = [
        _stage(
            "visual_candidate",
            "Visual Candidate Authority",
            visual["status"],
            visual["evidence"],
            visual["blockers"],
            visual["next_unlock"],
            allowed=[
                "candidate component/resource inventory",
                "candidate connector list",
                "salvage opportunity shortlist",
                "measurement queue generation",
            ],
            blocked=["pinout claims", "first power", "physical splice", "production repair release"],
        ),
        _stage(
            "measured_topology",
            "Measured Pinout/Topology Authority",
            topology["status"],
            topology["evidence"],
            topology["blockers"],
            topology["next_unlock"],
            allowed=["pin-level map for measured pins", "source/load evidence input", "topology-to-netlist compilation"],
            blocked=["unmeasured pins", "hidden nets", "production repair release"],
        ),
        _stage(
            "electrical_simulation",
            "Electrical Simulation Authority",
            simulation["status"],
            simulation["evidence"],
            simulation["blockers"],
            simulation["next_unlock"],
            allowed=["controlled bench setup planning", "source/load budget decision"],
            blocked=["unstated loads", "unmeasured thermal behavior", "production repair release"],
        ),
        _stage(
            "controlled_bench",
            "Controlled Bench Authority",
            bench["status"],
            bench["evidence"],
            bench["blockers"],
            bench["next_unlock"],
            allowed=["scoped function demonstrated under recorded conditions"],
            blocked=["repeatable release claim without release packet", "unsupported hazard scope"],
        ),
        _stage(
            "production_repair",
            "Production Repair Authority",
            production["status"],
            production["evidence"],
            production["blockers"],
            production["next_unlock"],
            allowed=["portfolio/demo release packet", "repeatable low-risk repair/reuse instruction"],
            blocked=["claims outside recorded scope", "hidden high-risk domains"],
        ),
    ]
    stages = _apply_production_casefile_coverage(stages)

    current_level = _current_level(stages)
    stage_status = {stage["stage_id"]: stage["status"] for stage in stages}
    claims = _claims(body, analysis, stages)
    next_unlocks = _next_unlocks(stages)
    release = test_kit.get("release_gate") if isinstance(test_kit.get("release_gate"), dict) else {}
    return {
        "mode": "hardware_authority_ledger",
        "schema_version": SCHEMA_VERSION,
        "available": any(stage["status"] in {"pass", "blocked", "open"} for stage in stages),
        "current_authority_level": current_level,
        "authority_score": _authority_score(stages),
        "can": {
            "use_visual_candidates": stage_status.get("visual_candidate") == "pass",
            "use_measured_pinout": stage_status.get("measured_topology") == "pass",
            "use_electrical_simulation": stage_status.get("electrical_simulation") == "pass",
            "run_controlled_bench": stage_status.get("measured_topology") == "pass"
            and stage_status.get("electrical_simulation") == "pass",
            "claim_controlled_reuse": stage_status.get("controlled_bench") == "pass",
            "claim_production_repair_release": stage_status.get("production_repair") == "pass",
            "power_or_splice_now": (
                bool(release.get("can_power_or_splice")) and stage_status.get("measured_topology") == "pass"
            )
            or stage_status.get("production_repair") == "pass",
        },
        "stages": stages,
        "claims": claims,
        "next_unlocks": next_unlocks,
        "evidence_summary": {
            "visual": visual["summary"],
            "topology": topology["summary"],
            "simulation": simulation["summary"],
            "bench": bench["summary"],
            "production": production["summary"],
        },
        "source_authority": {
            "repair_authority": _repair_authority_summary(body, analysis, integrated),
            "trust_assessment": _trust_summary(body, analysis),
            "test_kit_release_gate": release,
            "production_repair_authority": integrated.get("production_repair_authority")
            if isinstance(integrated.get("production_repair_authority"), dict)
            else {},
        },
        "claim_boundary": (
            "Authority is stage-scoped. Qwen/LLM evidence can create visual candidates and measurement tasks, "
            "but only measured topology, deterministic simulation, controlled bench outcome, and release artifacts can "
            "advance power, splice, or production repair claims."
        ),
    }


def _hardware_plan(body: Dict[str, Any]) -> Dict[str, Any]:
    plan = body.get("hardware_plan") if isinstance(body.get("hardware_plan"), dict) else {}
    if plan.get("analysis") or plan.get("integrated_plan"):
        return plan
    return HardwarePlanOrchestrator().plan(body)


def _design_test_kit(body: Dict[str, Any]) -> Dict[str, Any]:
    for key in ["design_test_kit", "hardware_design_test_kit", "test_kit"]:
        value = body.get(key)
        if isinstance(value, dict) and value.get("mode") == "hardware_design_test_kit":
            return value
    return build_design_test_kit(body)


def _visual_state(body: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    evidence = _board_evidence(body, analysis)
    reconstruction = _first_dict(body.get("multiview_board_reconstruction"), analysis.get("multiview_board_reconstruction"))
    bridge = _first_dict(body.get("vision_evidence_bridge"), analysis.get("vision_evidence_bridge"))
    topology = _first_dict(body.get("topology_evidence"), analysis.get("topology_evidence"))
    topology_reference_only = _reference_topology_only(topology, _first_dict(body.get("topology_evidence_bridge"), analysis.get("topology_evidence_bridge")), {})
    counts = {
        "components": len(_list_dicts(evidence.get("components"))),
        "connectors": len(_list_dicts(evidence.get("connectors"))),
        "markings": len(_list_dicts(evidence.get("markings"))),
        "damage": len(_list_dicts(evidence.get("damage"))),
        "salvage_candidates": len(_list_dicts(evidence.get("salvage_candidates"))),
        "photo_observations": int(reconstruction.get("usable_observation_count") or 0),
    }
    available = bool(evidence or bridge.get("available") or counts["photo_observations"] or topology)
    blockers = []
    if not available:
        blockers.append("No usable board visual evidence is attached.")
    if counts["damage"]:
        blockers.append("Visible damage exists; route damage through hazard/measurement clearance before authority.")
    next_unlock = (
        "Run Qwen/local vision over whole-board, connector close-up, marking close-up, and damage close-up photos."
        if not available
        else "Convert candidate connectors/components into measured topology_evidence.v1."
    )
    return {
        "status": "pass" if available else "open",
        "summary": counts,
        "evidence": [
            f"{counts['components']} component candidates",
            f"{counts['connectors']} connector candidates",
            f"{counts['markings']} marking candidates",
            f"{counts['salvage_candidates']} salvage candidates",
            "public reference topology attached" if topology and topology_reference_only else "",
            "measured topology evidence attached" if topology and not topology_reference_only else "",
        ],
        "blockers": blockers,
        "next_unlock": next_unlock,
    }


def _topology_state(body: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    authority = _first_dict(analysis.get("topology_authority"), body.get("topology_authority"))
    bridge = _first_dict(analysis.get("topology_evidence_bridge"), body.get("topology_evidence_bridge"))
    topology_evidence = _first_dict(body.get("topology_evidence"), analysis.get("topology_evidence"))
    reference_only = _reference_topology_only(topology_evidence, bridge, authority)
    measurement_backed = bool(
        authority.get("measurement_backed")
        or (bridge.get("available") and not reference_only)
        or (topology_evidence and not reference_only)
    )
    pinout_known = bool(authority.get("pinout_known"))
    shorts = bool(authority.get("shorts_detected"))
    unknown_pin_count = int(authority.get("unknown_pin_count") or 0)
    blockers = []
    if shorts:
        blockers.append("Measured topology reports a short or failed no-short lane.")
    if reference_only:
        blockers.append("Public reference topology is planning evidence only; confirm it with bench measurements.")
    elif not measurement_backed:
        blockers.append("No measured topology_evidence.v1 is attached.")
    elif not pinout_known:
        blockers.append("Pinout is not fully known for the measured connector scope.")
    if unknown_pin_count:
        blockers.append(f"{unknown_pin_count} pins remain unknown.")
    if shorts:
        status = "blocked"
    elif measurement_backed and pinout_known:
        status = "pass"
    elif measurement_backed:
        status = "open"
    else:
        status = "open"
    return {
        "status": status,
        "summary": {
            "measurement_backed": measurement_backed,
            "pinout_known": pinout_known,
            "shorts_detected": shorts,
            "unknown_pin_count": unknown_pin_count,
            "source": bridge.get("source")
            or topology_evidence.get("source_type")
            or topology_evidence.get("source")
            or ("topology_evidence.v1" if topology_evidence else "unavailable"),
            "reference_only": reference_only,
        },
        "evidence": _dedupe(
            [
                f"topology source: {bridge.get('source')}" if bridge.get("source") else "",
                "public reference topology attached" if reference_only else "",
                "measured connector/pin evidence attached" if measurement_backed else "",
                "pinout known" if pinout_known else "",
            ]
        ),
        "blockers": blockers,
        "next_unlock": (
            "Resolve the measured short before power, splice, or reuse."
            if shorts
            else "Confirm the public reference pinout with no-short, ground, voltage, current, thermal, and logic observations."
            if reference_only
            else "Measure ground, no-short resistance, voltage, current, thermal, and unknown pins into topology_evidence.v1."
            if status != "pass"
            else "Compile measured topology into a simulation netlist and run the design test kit."
        ),
    }


def _simulation_state(test_kit: Dict[str, Any]) -> Dict[str, Any]:
    simulation = test_kit.get("simulation") if isinstance(test_kit.get("simulation"), dict) else {}
    release = test_kit.get("release_gate") if isinstance(test_kit.get("release_gate"), dict) else {}
    decision = str(release.get("decision") or "")
    issues = _list_dicts(simulation.get("issues"))
    hard_issues = [
        str(issue.get("issue") or issue.get("summary") or issue)
        for issue in issues
        if str(issue.get("severity") or "").lower() in {"critical", "error"}
    ]
    available = bool(simulation.get("available"))
    if decision == "blocked_by_simulation_failure" or hard_issues:
        status = "blocked"
    elif available and not hard_issues:
        status = "pass"
    else:
        status = "open"
    blockers = []
    if not available:
        blockers.append("No deterministic simulation model has run.")
    blockers.extend(hard_issues)
    return {
        "status": status,
        "summary": {
            "available": available,
            "decision": decision or None,
            "issue_count": len(issues),
            "simulation_model_source": ((test_kit.get("design_model") or {}).get("simulation_model_source") if isinstance(test_kit.get("design_model"), dict) else None),
        },
        "evidence": _dedupe(
            [
                f"release decision: {decision}" if decision else "",
                "deterministic power-tree simulation available" if available else "",
                "no hard simulation issues" if available and not hard_issues else "",
            ]
        ),
        "blockers": blockers,
        "next_unlock": (
            "Fix the failing power-tree/current/voltage condition and rerun the design test kit."
            if status == "blocked"
            else "Supply measured topology/netlist with source limits and load current."
            if status == "open"
            else "Run controlled bench outcome under the simulated source/load constraints."
        ),
    }


def _gate_simulation_by_topology(simulation: Dict[str, Any], topology: Dict[str, Any]) -> Dict[str, Any]:
    if simulation.get("status") != "pass" or topology.get("status") == "pass":
        return simulation
    return {
        **simulation,
        "status": "open",
        "evidence": _dedupe(
            [
                *(simulation.get("evidence") or []),
                "simulation/planning model available but not authority-granting without measured topology",
            ]
        ),
        "blockers": _dedupe(
            [
                *(simulation.get("blockers") or []),
                "Measured topology authority must pass before electrical simulation can grant repair authority.",
            ]
        ),
        "next_unlock": (
            "Attach measured topology evidence, then rerun deterministic simulation against the measured "
            "connector/source/load scope."
        ),
    }


def _bench_state(body: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    outcomes = _list_dicts(body.get("outcome_history") or body.get("outcomes"))
    functional = _first_dict(analysis.get("functional_outcome"), body.get("functional_outcome"))
    terminal = any(_outcome_passed(row) for row in outcomes) or bool(functional.get("terminal_success"))
    blockers = []
    if not terminal:
        blockers.append("No terminal controlled bench outcome proves the target function.")
    status = "pass" if terminal else "open"
    evidence = []
    for row in outcomes[:3]:
        evidence.append(str(row.get("evidence_uri") or row.get("decision") or "outcome record"))
    if functional.get("terminal_success"):
        evidence.append("functional outcome marked terminal_success")
    return {
        "status": status,
        "summary": {
            "outcome_count": len(outcomes),
            "terminal_success": terminal,
            "current_limit_used": any(bool(row.get("current_limit_used")) for row in outcomes),
            "thermal_normal": any(str(row.get("thermal_result") or "").lower() == "normal" for row in outcomes),
        },
        "evidence": _dedupe(evidence),
        "blockers": blockers,
        "next_unlock": (
            "Record current-limited first power, voltage/current logs, thermal result, and target function proof."
            if status != "pass"
            else "Attach a complete production_release/release_manifest with artifacts and scope."
        ),
    }


def _production_state(integrated: Dict[str, Any], body: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    production = integrated.get("production_repair_authority") if isinstance(integrated.get("production_repair_authority"), dict) else {}
    release = _first_dict(body.get("production_release"), body.get("release_manifest"))
    authorized = bool(production.get("authorized"))
    blockers = _dedupe(
        [str(item) for item in production.get("blockers") or [] if str(item).strip()]
        + (
            []
            if authorized
            else ["Production repair authority is not authorized by the casefile."]
        )
    )
    casefile = production.get("authority_casefile") if isinstance(production.get("authority_casefile"), dict) else {}
    status = "pass" if authorized else "open"
    if production.get("decision") in {"blocked_safety_hold", "specialist_authority_required"}:
        status = "blocked"
    return {
        "status": status,
        "summary": {
            "authorized": authorized,
            "decision": production.get("decision"),
            "casefile_status": casefile.get("status"),
            "blocked_claim_count": casefile.get("blocked_claim_count"),
            "release_manifest_attached": bool(release),
        },
        "evidence": _dedupe(
            [
                f"casefile: {casefile.get('status')}" if casefile.get("status") else "",
                f"decision: {production.get('decision')}" if production.get("decision") else "",
                "release manifest attached" if release else "",
            ]
        ),
        "blockers": blockers,
        "next_unlock": (
            "Resolve safety/specialist blockers before any production repair claim."
            if status == "blocked"
            else "Close measurement provenance, terminal outcome, release manifest, and authority casefile claims."
            if status != "pass"
            else "Authority is release-ready for the scoped low-risk claim."
        ),
    }


def _claims(body: Dict[str, Any], analysis: Dict[str, Any], stages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    stage_by_id = {stage["stage_id"]: stage for stage in stages}
    visual_level = "visual_candidate" if stage_by_id["visual_candidate"]["status"] == "pass" else "no_authority"
    topology_level = "measured_topology" if stage_by_id["measured_topology"]["status"] == "pass" else visual_level
    simulation_level = "electrical_simulation" if stage_by_id["electrical_simulation"]["status"] == "pass" else topology_level
    bench_level = "controlled_bench" if stage_by_id["controlled_bench"]["status"] == "pass" else simulation_level
    production_level = "production_repair" if stage_by_id["production_repair"]["status"] == "pass" else bench_level
    claims = [
        _claim(
            "board_visual_inventory",
            "board_understanding",
            "Visible board objects and salvage candidates",
            visual_level,
            evidence_stage="visual_candidate",
            stages=stage_by_id,
        ),
        _claim(
            "connector_pinout_topology",
            "pinout_topology",
            "Measured connector pinout and net topology",
            topology_level,
            evidence_stage="measured_topology",
            stages=stage_by_id,
        ),
        _claim(
            "power_path_electrical_model",
            "electrical_simulation",
            "Measured power path passes deterministic source/load checks",
            simulation_level,
            evidence_stage="electrical_simulation",
            stages=stage_by_id,
        ),
        _claim(
            "controlled_functional_reuse",
            "bench_outcome",
            "Target function works under controlled bench conditions",
            bench_level,
            evidence_stage="controlled_bench",
            stages=stage_by_id,
        ),
        _claim(
            "production_repair_release",
            "production_repair",
            "Scoped repair/reuse/splice path is repeatable and release-ready",
            production_level,
            evidence_stage="production_repair",
            stages=stage_by_id,
        ),
    ]
    evidence = _board_evidence(body, analysis)
    for item in _list_dicts(evidence.get("salvage_candidates"))[:8]:
        label = str(item.get("label") or item.get("function") or item.get("id") or "salvage candidate")
        claims.append(
            _claim(
                f"salvage_candidate_{_safe_id(label)}",
                "salvage_candidate",
                label,
                visual_level,
                evidence_stage="visual_candidate",
                stages=stage_by_id,
            )
        )
    return claims


def _claim(
    claim_id: str,
    claim_type: str,
    label: str,
    current_level: str,
    *,
    evidence_stage: str,
    stages: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    stage = stages[evidence_stage]
    status = "blocked" if stage["status"] == "blocked" else "authority_granted" if stage["status"] == "pass" else "evidence_required"
    return {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "label": label,
        "current_authority_level": current_level,
        "status": status,
        "evidence_stage": evidence_stage,
        "evidence": stage.get("evidence") or [],
        "blockers": stage.get("blockers") or [],
        "next_unlock": stage.get("next_unlock"),
        "allowed_actions": stage.get("allowed_actions") if stage["status"] == "pass" else [],
        "blocked_actions": stage.get("blocked_actions") or [],
    }


def _current_level(stages: Sequence[Dict[str, Any]]) -> str:
    if any(stage["status"] == "blocked" for stage in stages[:3]):
        return "blocked_safety_or_electrical"
    current = "no_authority"
    for stage in stages:
        if stage["status"] == "pass":
            current = stage["stage_id"]
        else:
            break
    return current


def _authority_score(stages: Sequence[Dict[str, Any]]) -> float:
    if any(stage["stage_id"] == "production_repair" and stage["status"] == "pass" for stage in stages):
        return 1.0
    weights = {
        "visual_candidate": 0.18,
        "measured_topology": 0.24,
        "electrical_simulation": 0.2,
        "controlled_bench": 0.18,
        "production_repair": 0.2,
    }
    score = 0.0
    for stage in stages:
        if stage["status"] == "blocked":
            return round(min(score, 0.24), 3)
        if stage["status"] == "pass":
            score += weights.get(stage["stage_id"], 0.0)
    return round(min(score, 1.0), 3)


def _next_unlocks(stages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if any(stage["stage_id"] == "production_repair" and stage["status"] == "pass" for stage in stages):
        return []
    rows = []
    for stage in stages:
        if stage["status"] != "pass":
            rows.append(
                {
                    "stage_id": stage["stage_id"],
                    "title": stage["title"],
                    "status": stage["status"],
                    "next_unlock": stage["next_unlock"],
                    "blockers": stage["blockers"],
                }
            )
    return rows[:5]


def _apply_production_casefile_coverage(stages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    production_passed = any(stage["stage_id"] == "production_repair" and stage["status"] == "pass" for stage in stages)
    lower_blocked = any(stage["stage_id"] != "production_repair" and stage["status"] == "blocked" for stage in stages)
    if not production_passed or lower_blocked:
        return stages
    covered = []
    for stage in stages:
        if stage["stage_id"] != "production_repair" and stage["status"] in {"open", "pass"}:
            stage = {
                **stage,
                "status": "pass",
                "evidence": _dedupe([*(stage.get("evidence") or []), "covered by authorized production repair casefile for this scoped claim"]),
                "blockers": [],
                "next_unlock": "Covered by the production repair authority casefile for this scoped claim.",
            }
        covered.append(stage)
    return covered


def _stage(
    stage_id: str,
    title: str,
    status: str,
    evidence: Sequence[str],
    blockers: Sequence[str],
    next_unlock: str,
    *,
    allowed: Sequence[str],
    blocked: Sequence[str],
) -> Dict[str, Any]:
    return {
        "stage_id": stage_id,
        "title": title,
        "status": status,
        "evidence": _dedupe(evidence),
        "blockers": _dedupe(blockers),
        "next_unlock": next_unlock,
        "allowed_actions": list(allowed),
        "blocked_actions": list(blocked),
    }


def _board_evidence(body: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    for value in [
        body.get("board_evidence"),
        analysis.get("board_evidence"),
        (body.get("qwen_board_vision") or {}).get("board_evidence") if isinstance(body.get("qwen_board_vision"), dict) else None,
        (body.get("multiview_board_reconstruction") or {}).get("board_evidence") if isinstance(body.get("multiview_board_reconstruction"), dict) else None,
        (analysis.get("multiview_board_reconstruction") or {}).get("board_evidence") if isinstance(analysis.get("multiview_board_reconstruction"), dict) else None,
    ]:
        if isinstance(value, dict) and value:
            return value
    photo_set = body.get("board_photo_set") if isinstance(body.get("board_photo_set"), dict) else {}
    for obs in _list_dicts(photo_set.get("photo_observations")):
        evidence = obs.get("board_evidence")
        if isinstance(evidence, dict) and evidence:
            return evidence
    return {}


def _repair_authority_summary(body: Dict[str, Any], analysis: Dict[str, Any], integrated: Dict[str, Any]) -> Dict[str, Any]:
    authority = _first_dict(body.get("repair_authority"), analysis.get("repair_authority"))
    context = integrated.get("authority") if isinstance(integrated.get("authority"), dict) else {}
    return {
        "status": authority.get("status") or context.get("repair_authority_status"),
        "score": authority.get("score") or context.get("repair_authority_score"),
        "blocked_decisions": authority.get("blocked_decisions") or context.get("blocked_decisions") or [],
        "required_measurements": authority.get("required_measurements") or context.get("required_measurements") or [],
    }


def _trust_summary(body: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    trust = _first_dict(body.get("arbitrary_board_trust_assessment"), analysis.get("arbitrary_board_trust_assessment"))
    return {
        "level": trust.get("level"),
        "score": trust.get("score"),
        "production_readiness_score": trust.get("production_readiness_score"),
        "blocking_gap_count": len(trust.get("blocking_gaps") or []),
    }


def _reference_topology_only(
    topology_evidence: Dict[str, Any], bridge: Dict[str, Any], authority: Dict[str, Any]
) -> bool:
    if bridge.get("reference_only") or str(bridge.get("source") or "").lower() == "public_reference_topology":
        return True
    if authority.get("reference_backed") and not authority.get("measurement_backed"):
        return True
    text = " ".join(
        str(value or "")
        for value in [
            topology_evidence.get("source"),
            topology_evidence.get("source_type"),
            topology_evidence.get("evidence_type"),
            topology_evidence.get("reference_uri"),
            topology_evidence.get("source_uri"),
        ]
    ).lower()
    return any(term in text for term in ["public_reference", "reference_topology", "public schematic", "datasheet", "official_pinout"])


def _outcome_passed(row: Dict[str, Any]) -> bool:
    return bool(
        row.get("output_function_verified")
        and str(row.get("first_power_result") or "").lower() in {"pass", "passed", "ok"}
        and str(row.get("thermal_result") or "").lower() in {"normal", "pass", "passed", "ok"}
    )


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _dedupe(items: Iterable[Any]) -> List[str]:
    rows: List[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        rows.append(text)
    return rows


def _safe_id(value: Any) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "claim"))
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")[:80] or "claim"
