"""Production-readiness casefile orchestration for Circuit-AI.

This module assembles the backend production workflow into one reusable artifact:
visual intake, measurement capture, topology/simulation, field action, authority
ledger, closure plan, and release report.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence

from src.intelligence.active_evidence_closure import build_active_evidence_closure_plan
from src.intelligence.authority_ledger import build_authority_ledger
from src.intelligence.bench_topology_capture import (
    build_bench_capture_template,
    enrich_payload_with_bench_topology_capture,
)
from src.intelligence.design_test_kit import build_design_test_kit
from src.intelligence.field_model_advisory import build_field_model_advisory
from src.intelligence.field_operator_agent import build_field_operator_next_action
from src.intelligence.hardware_plan import HardwarePlanOrchestrator
from src.intelligence.multiview_board_evidence import fuse_board_photo_set
from src.intelligence.topology_evidence import enrich_payload_with_topology_evidence
from src.intelligence.topology_netlist_compiler import compile_topology_to_netlist


SCHEMA_VERSION = "production_casefile.v1"


def build_production_casefile(payload: Dict[str, Any], *, live_model_advisory: bool = False) -> Dict[str, Any]:
    """Build the full backend casefile for one board/reuse/repair workflow."""

    original = dict(payload or {})
    prepared = _prepare_payload(original)
    plan = HardwarePlanOrchestrator().plan(prepared)
    analysis = plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {}
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    board_evidence = _board_evidence(prepared, analysis)
    template = build_bench_capture_template(
        reference_topology=_first_dict(prepared.get("reference_topology"), prepared.get("topology_evidence")) or None,
        board_evidence=board_evidence or None,
    )
    compiled = compile_topology_to_netlist(prepared)
    test_kit = build_design_test_kit({**prepared, "hardware_plan": plan})
    field = build_field_operator_next_action(
        {
            **prepared,
            "hardware_plan": plan,
            "design_test_kit": test_kit,
            "multiview_board_reconstruction": _first_dict(
                prepared.get("multiview_board_reconstruction"),
                analysis.get("multiview_board_reconstruction"),
            ),
        }
    )
    advisory = build_field_model_advisory(
        {
            **prepared,
            "hardware_plan": plan,
            "design_test_kit": test_kit,
            "field_operator": field,
        },
        live=live_model_advisory,
    )
    ledger = build_authority_ledger({**prepared, "hardware_plan": plan, "design_test_kit": test_kit})
    closure = build_active_evidence_closure_plan(prepared, analysis=analysis)
    report = _release_report(
        payload=prepared,
        plan=plan,
        test_kit=test_kit,
        field=field,
        ledger=ledger,
        closure=closure,
    )
    production_authorized = bool((ledger.get("can") or {}).get("claim_production_repair_release"))
    return {
        "mode": "production_casefile",
        "schema_version": SCHEMA_VERSION,
        "casefile_id": str(original.get("casefile_id") or original.get("case_id") or _default_casefile_id(original)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prepared_payload": prepared,
        "visual_intake": _visual_intake(prepared, analysis, board_evidence),
        "measurement_capture_packet": _measurement_capture_packet(template, closure),
        "topology_netlist_compilation": compiled,
        "design_test_kit": test_kit,
        "field_operator": field,
        "field_model_advisory": advisory,
        "hardware_plan": plan,
        "authority_ledger": ledger,
        "active_evidence_closure_plan": closure,
        "release_report": report,
        "summary": {
            "current_authority_level": ledger.get("current_authority_level"),
            "authority_score": ledger.get("authority_score"),
            "production_authorized": production_authorized,
            "next_action_id": None
            if production_authorized
            else ((field.get("operational_call") or {}).get("action_id") if isinstance(field.get("operational_call"), dict) else None),
            "closure_stage": closure.get("current_stage"),
            "release_decision": report.get("decision"),
        },
        "claim_boundary": (
            "This casefile assembles evidence and authority state. It does not turn model output into repair authority; "
            "production release requires measured evidence, terminal outcome, and a passing authority ledger."
        ),
    }


def _prepare_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    body = dict(payload or {})
    qwen = body.get("qwen_board_vision") if isinstance(body.get("qwen_board_vision"), dict) else {}
    if isinstance(qwen.get("board_evidence"), dict) and not isinstance(body.get("board_evidence"), dict):
        body["board_evidence"] = qwen["board_evidence"]
    if _has_photo_observations(body) and not isinstance(body.get("multiview_board_reconstruction"), dict):
        reconstruction = fuse_board_photo_set(body)
        body["multiview_board_reconstruction"] = reconstruction
        if isinstance(reconstruction.get("board_evidence"), dict):
            body["board_evidence"] = reconstruction["board_evidence"]
        if isinstance(reconstruction.get("vision_evidence_bridge"), dict):
            body["vision_evidence_bridge"] = reconstruction["vision_evidence_bridge"]
    body = enrich_payload_with_bench_topology_capture(body)
    body = enrich_payload_with_topology_evidence(body)
    return body


def _visual_intake(prepared: Dict[str, Any], analysis: Dict[str, Any], board_evidence: Dict[str, Any]) -> Dict[str, Any]:
    reconstruction = _first_dict(prepared.get("multiview_board_reconstruction"), analysis.get("multiview_board_reconstruction"))
    qwen = prepared.get("qwen_board_vision") if isinstance(prepared.get("qwen_board_vision"), dict) else {}
    return {
        "schema_version": "production_casefile_visual_intake.v1",
        "available": bool(board_evidence or reconstruction or qwen),
        "providers": _visual_providers(prepared, qwen),
        "counts": {
            "components": len(_list_dicts(board_evidence.get("components"))),
            "connectors": len(_list_dicts(board_evidence.get("connectors"))),
            "markings": len(_list_dicts(board_evidence.get("markings"))),
            "damage": len(_list_dicts(board_evidence.get("damage"))),
            "salvage_candidates": len(_list_dicts(board_evidence.get("salvage_candidates"))),
            "usable_photo_observations": int(reconstruction.get("usable_observation_count") or 0),
        },
        "qwen_parse_diagnostics": qwen.get("parse_diagnostics") if isinstance(qwen.get("parse_diagnostics"), dict) else {},
        "capture_coverage": reconstruction.get("capture_coverage") if isinstance(reconstruction.get("capture_coverage"), dict) else {},
        "claim_boundary": "Visual intake creates candidates and measurement targets only.",
    }


def _measurement_capture_packet(template: Dict[str, Any], closure: Dict[str, Any]) -> Dict[str, Any]:
    next_measurements = closure.get("next_measurement_set") if isinstance(closure.get("next_measurement_set"), list) else []
    return {
        "schema_version": "production_measurement_capture_packet.v1",
        "bench_topology_capture_template": template,
        "next_measurement_set": next_measurements[:20],
        "required_provenance": [
            "instrument_id",
            "instrument_type",
            "calibration_status",
            "recorded_at",
            "operator_id",
            "evidence_uri",
        ],
        "expected_output_schema": "bench_topology_capture.v1 -> topology_evidence.v1",
        "operator_rules": [
            "Reference/vision seeded pins stay needs_measurement until verified on the physical board.",
            "Record no-short before voltage/current tests.",
            "Use current-limited power for first-power measurements.",
            "Attach photo/log artifact URIs for production authority.",
        ],
    }


def _release_report(
    *,
    payload: Dict[str, Any],
    plan: Dict[str, Any],
    test_kit: Dict[str, Any],
    field: Dict[str, Any],
    ledger: Dict[str, Any],
    closure: Dict[str, Any],
) -> Dict[str, Any]:
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    production = integrated.get("production_repair_authority") if isinstance(integrated.get("production_repair_authority"), dict) else {}
    release = test_kit.get("release_gate") if isinstance(test_kit.get("release_gate"), dict) else {}
    can = ledger.get("can") if isinstance(ledger.get("can"), dict) else {}
    authorized = bool(can.get("claim_production_repair_release"))
    if authorized:
        decision = "production_repair_authorized"
    elif can.get("run_controlled_bench"):
        decision = "bench_ready_evidence_required"
    elif can.get("use_measured_pinout"):
        decision = "simulation_or_bench_evidence_required"
    elif can.get("use_visual_candidates"):
        decision = "measurement_capture_required"
    else:
        decision = "intake_required"
    next_unlock = ledger.get("next_unlocks")[0] if isinstance(ledger.get("next_unlocks"), list) and ledger.get("next_unlocks") else {}
    return {
        "schema_version": "production_casefile_release_report.v1",
        "decision": decision,
        "authorized": authorized,
        "authority_level": ledger.get("current_authority_level"),
        "authority_score": ledger.get("authority_score"),
        "scope": _scope_statement(payload, production),
        "can": can,
        "next_unlock": next_unlock,
        "test_kit_decision": release.get("decision"),
        "test_kit_effective_decision": "covered_by_production_repair_casefile" if authorized else release.get("decision"),
        "test_kit_scope_note": (
            "Design-test-kit fixture gaps are non-blocking for this scoped claim because the production repair authority "
            "casefile already carries trusted measurements, terminal outcome proof, and release artifacts."
            if authorized
            else "Design-test-kit gates remain blocking until the authority ledger reaches production repair."
        ),
        "production_decision": production.get("decision"),
        "closure_current_stage": closure.get("current_stage"),
        "remaining_tasks": closure.get("next_best_tasks")[:12] if isinstance(closure.get("next_best_tasks"), list) else [],
        "field_next_action": {}
        if authorized
        else field.get("operational_call") if isinstance(field.get("operational_call"), dict) else {},
        "authority_stages": [
            {
                "stage_id": stage.get("stage_id"),
                "status": stage.get("status"),
                "blockers": stage.get("blockers") or [],
                "next_unlock": stage.get("next_unlock"),
            }
            for stage in ledger.get("stages") or []
            if isinstance(stage, dict)
        ],
        "release_artifacts_required": _release_artifacts_required(authorized),
    }


def _release_artifacts_required(authorized: bool) -> List[str]:
    if authorized:
        return []
    return [
        "measured topology evidence or bench_topology_capture.v1",
        "trusted resistance/continuity/voltage/current/thermal measurements",
        "terminal outcome record with function proof",
        "production_release/release_manifest with scope and artifact URIs",
    ]


def _scope_statement(payload: Dict[str, Any], production: Dict[str, Any]) -> str:
    release = _first_dict(payload.get("production_release"), payload.get("release_manifest"))
    if release.get("scope_statement"):
        return str(release["scope_statement"])
    if production.get("scope"):
        return str(production["scope"])
    return str(payload.get("goal") or payload.get("diy_project") or "scoped board repair/reuse case")


def _board_evidence(prepared: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    for value in [
        prepared.get("board_evidence"),
        analysis.get("board_evidence"),
        (prepared.get("multiview_board_reconstruction") or {}).get("board_evidence")
        if isinstance(prepared.get("multiview_board_reconstruction"), dict)
        else None,
        (analysis.get("multiview_board_reconstruction") or {}).get("board_evidence")
        if isinstance(analysis.get("multiview_board_reconstruction"), dict)
        else None,
    ]:
        if isinstance(value, dict) and value:
            return value
    return {}


def _visual_providers(prepared: Dict[str, Any], qwen: Dict[str, Any]) -> List[str]:
    providers = []
    if qwen:
        providers.append("qwen")
    photo_set = prepared.get("board_photo_set") if isinstance(prepared.get("board_photo_set"), dict) else {}
    for obs in _list_dicts(photo_set.get("photo_observations")):
        provider = str(obs.get("provider") or "").strip()
        if provider:
            providers.append(provider)
    if prepared.get("board_evidence"):
        providers.append("manual_or_imported_board_evidence")
    return _dedupe(providers)


def _has_photo_observations(body: Dict[str, Any]) -> bool:
    photo_set = body.get("board_photo_set") if isinstance(body.get("board_photo_set"), dict) else {}
    return bool(_list_dicts(photo_set.get("photo_observations")) or _list_dicts(body.get("photo_observations")))


def _default_casefile_id(payload: Dict[str, Any]) -> str:
    text = str(payload.get("goal") or payload.get("diy_project") or "production_casefile")
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in text).strip("_")
    return safe[:80] or "production_casefile"


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _dedupe(values: Iterable[Any]) -> List[str]:
    rows: List[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        rows.append(text)
    return rows
