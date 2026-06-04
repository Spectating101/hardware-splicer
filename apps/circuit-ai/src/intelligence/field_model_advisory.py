"""Live model advisory for field/operator hardware actions.

This layer gives an LLM a narrow job: turn the selected field action, Qwen
candidate evidence, and deterministic gates into a measurement priority plan.
It does not authorize power, splice, repair, or release.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from src.intelligence.circuit_ai_reasoner import CircuitAIReasoner, circuit_ai_model_status
from src.intelligence.field_operator_agent import build_field_operator_next_action


SCHEMA_VERSION = "field_model_advisory.v1"


def build_field_model_advisory(payload: Dict[str, Any], *, live: bool = False) -> Dict[str, Any]:
    """Return dry-run or live model guidance for the current field action."""

    body = dict(payload or {})
    field = _field_operator(body)
    call = field.get("operational_call") if isinstance(field.get("operational_call"), dict) else {}
    context = _advisory_context(body, field)
    prompt = _advisory_prompt(context)
    status = circuit_ai_model_status()
    base = {
        "mode": "field_model_advisory",
        "schema_version": SCHEMA_VERSION,
        "live_requested": bool(live),
        "provider_status": _provider_status_summary(status),
        "field_action_id": call.get("action_id"),
        "field_action_type": call.get("action_type"),
        "field_authority": call.get("authority"),
        "context_summary": context.get("summary"),
        "claim_boundary": _claim_boundary(),
    }
    if not live:
        return {
            **base,
            "mode": "dry_run",
            "ready_for_live_model": bool(status.get("ready_for_live_model")),
            "prompt_preview": prompt,
            "advisory": _empty_advisory(reason="live flag was not set"),
            "field_operator": field,
        }
    if not status.get("ready_for_live_model"):
        return {
            **base,
            "mode": "blocked_provider",
            "ready_for_live_model": False,
            "blockers": status.get("blockers") or ["live model provider is not ready"],
            "advisory": _empty_advisory(reason="live model provider is not ready"),
            "field_operator": field,
        }

    try:
        text, model = CircuitAIReasoner(enable_llm=True, max_tokens=1800)._call_llm(prompt)
    except Exception as exc:
        return {
            **base,
            "mode": "live_error",
            "ready_for_live_model": False,
            "error": str(exc),
            "advisory": _empty_advisory(reason="live model call failed"),
            "field_operator": field,
        }

    parsed = _extract_json_object(text)
    advisory = _normalize_advisory(parsed, call)
    verifier = _verify_advisory(advisory)
    return {
        **base,
        "mode": "live",
        "ready_for_live_model": True,
        "model": model,
        "raw_response_parsed": bool(parsed),
        "parse_diagnostics": {
            "json_valid": bool(parsed),
            "content_length": len(str(text or "")),
            "raw_response_excerpt": str(text or "")[:2000],
        },
        "advisory": advisory,
        "verifier": verifier,
        "field_operator": field,
    }


def _field_operator(body: Dict[str, Any]) -> Dict[str, Any]:
    value = body.get("field_operator") or body.get("field_action")
    if isinstance(value, dict) and value.get("schema_version") == "hardware_field_operator_next_action.v1":
        return value
    return build_field_operator_next_action(body)


def _advisory_context(body: Dict[str, Any], field: Dict[str, Any]) -> Dict[str, Any]:
    call = field.get("operational_call") if isinstance(field.get("operational_call"), dict) else {}
    evidence = _board_evidence(body)
    visual_topology = _visual_topology(body)
    measurement_queue = [
        _compact_dict(row, keys=["task_id", "target", "measurement_type", "prompt", "priority", "connector_ref", "component_ref", "required_evidence"])
        for row in (visual_topology.get("measurement_queue") or [])[:10]
        if isinstance(row, dict)
    ]
    release = _release_gate(body, field)
    labels = _evidence_labels(evidence)
    return {
        "summary": {
            "connector_count": len(evidence.get("connectors") or []),
            "component_count": len(evidence.get("components") or []),
            "marking_count": len(evidence.get("markings") or []),
            "measurement_task_count": len(visual_topology.get("measurement_queue") or []),
            "release_decision": release.get("decision"),
            "field_action_id": call.get("action_id"),
        },
        "goal": str(body.get("goal") or body.get("diy_project") or "hardware field measurement planning"),
        "field_call": _compact_dict(
            call,
            keys=["action_id", "action_type", "authority", "summary", "why", "procedure", "pass_fail_thresholds", "expected_input_schema"],
        ),
        "qwen_or_visual_labels": labels,
        "visual_topology_readiness": visual_topology.get("readiness") if isinstance(visual_topology.get("readiness"), dict) else {},
        "measurement_queue": measurement_queue,
        "release_gate": release,
        "decision_inputs": field.get("decision_inputs") if isinstance(field.get("decision_inputs"), dict) else {},
    }


def _advisory_prompt(context: Dict[str, Any]) -> str:
    return "\n".join(
        [
            "You are Circuit-AI's live field advisory model.",
            "Return ONLY one compact JSON object.",
            "Top-level keys: schema_version, field_call_alignment, measurement_priorities, qwen_evidence_uses, warnings, operator_prompt, structured_measurement_template, forbidden_claims.",
            f"schema_version must be {SCHEMA_VERSION}.",
            "Your job is to prioritize the next measurements for the selected field action.",
            "Keep the answer compact: at most 6 measurement_priorities, 5 qwen_evidence_uses, 5 warnings, and 6 forbidden_claims.",
            "Keep every string under 150 characters.",
            "Use only labels, connectors, components, and tasks present in the context.",
            "Do not invent pinouts, voltages, board revisions, exact part identities, safety clearance, or splice authority.",
            "Do not say the board is safe, ready, powered, reusable, repair-cleared, or splice-ready.",
            "If a connector/pin/rail is uncertain, label it candidate_only and require measurement.",
            "measurement_priorities rows must include: priority, target, action, why, expected_evidence, stop_condition.",
            "qwen_evidence_uses rows must include: evidence_label, use, limitation.",
            "structured_measurement_template must be a JSON object the operator can fill in.",
            "forbidden_claims must list claims the model refuses to make from current evidence.",
            "Context:",
            json.dumps(context, separators=(",", ":"), ensure_ascii=True),
        ]
    )


def _board_evidence(body: Dict[str, Any]) -> Dict[str, Any]:
    for key in ["board_evidence", "qwen_board_evidence"]:
        value = body.get(key)
        if isinstance(value, dict):
            return value
    qwen = body.get("qwen_board_vision") if isinstance(body.get("qwen_board_vision"), dict) else {}
    if isinstance(qwen.get("board_evidence"), dict):
        return qwen["board_evidence"]
    fused = body.get("multiview_board_reconstruction") if isinstance(body.get("multiview_board_reconstruction"), dict) else {}
    if isinstance(fused.get("board_evidence"), dict):
        return fused["board_evidence"]
    analysis = body.get("analysis") if isinstance(body.get("analysis"), dict) else {}
    fused = analysis.get("multiview_board_reconstruction") if isinstance(analysis.get("multiview_board_reconstruction"), dict) else {}
    if isinstance(fused.get("board_evidence"), dict):
        return fused["board_evidence"]
    photo_set = body.get("board_photo_set") if isinstance(body.get("board_photo_set"), dict) else {}
    for obs in photo_set.get("photo_observations") or []:
        if isinstance(obs, dict) and isinstance(obs.get("board_evidence"), dict):
            return obs["board_evidence"]
    return {}


def _visual_topology(body: Dict[str, Any]) -> Dict[str, Any]:
    for container in [body, body.get("analysis") if isinstance(body.get("analysis"), dict) else {}]:
        value = container.get("visual_topology_hypothesis") if isinstance(container, dict) else None
        if isinstance(value, dict):
            return value
    plan = body.get("hardware_plan") if isinstance(body.get("hardware_plan"), dict) else {}
    analysis = plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {}
    value = analysis.get("visual_topology_hypothesis")
    return value if isinstance(value, dict) else {}


def _release_gate(body: Dict[str, Any], field: Dict[str, Any]) -> Dict[str, Any]:
    for container in [
        body.get("design_test_kit") if isinstance(body.get("design_test_kit"), dict) else {},
        body.get("test_kit") if isinstance(body.get("test_kit"), dict) else {},
    ]:
        release = container.get("release_gate") if isinstance(container, dict) else None
        if isinstance(release, dict):
            return release
    decision = field.get("decision_inputs") if isinstance(field.get("decision_inputs"), dict) else {}
    return {"decision": decision.get("release_decision"), "reason": decision.get("release_reason")}


def _evidence_labels(evidence: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        key: [
            _compact_dict(row, keys=["id", "label", "kind", "confidence", "missing_evidence", "warnings"])
            for row in (evidence.get(key) or [])[:12]
            if isinstance(row, dict)
        ]
        for key in ["components", "connectors", "markings", "damage", "test_points", "salvage_candidates"]
    }


def _normalize_advisory(parsed: Dict[str, Any], call: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": str(parsed.get("schema_version") or SCHEMA_VERSION),
        "field_call_alignment": str(parsed.get("field_call_alignment") or call.get("action_id") or "unknown"),
        "measurement_priorities": _dict_rows(parsed.get("measurement_priorities"), limit=12),
        "qwen_evidence_uses": _dict_rows(parsed.get("qwen_evidence_uses"), limit=12),
        "warnings": _string_rows(parsed.get("warnings"), limit=12),
        "operator_prompt": str(parsed.get("operator_prompt") or ""),
        "structured_measurement_template": parsed.get("structured_measurement_template")
        if isinstance(parsed.get("structured_measurement_template"), dict)
        else {},
        "forbidden_claims": _string_rows(parsed.get("forbidden_claims"), limit=12),
    }


def _verify_advisory(advisory: Dict[str, Any]) -> Dict[str, Any]:
    scannable = {
        key: value
        for key, value in advisory.items()
        if key not in {"forbidden_claims", "schema_version"}
    }
    text = json.dumps(scannable, ensure_ascii=True).lower()
    forbidden_terms = [
        "safe to power",
        "safe to splice",
        "splice-ready",
        "reuse-ready",
        "repair-cleared",
        "production release",
    ]
    blocked = [term for term in forbidden_terms if term in text]
    return {
        "status": "blocked_for_authority_language" if blocked else "advisory_only",
        "blocked_terms": blocked,
        "model_claims_are_advisory": True,
        "power_or_splice_authorized": False,
    }


def _provider_status_summary(status: Dict[str, Any]) -> Dict[str, Any]:
    selected = status.get("selected") if isinstance(status.get("selected"), dict) else {}
    return {
        "status": status.get("status"),
        "ready_for_live_model": bool(status.get("ready_for_live_model")),
        "provider": selected.get("provider"),
        "model": selected.get("model"),
        "blockers": status.get("blockers") or [],
    }


def _empty_advisory(*, reason: str) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "field_call_alignment": reason,
        "measurement_priorities": [],
        "qwen_evidence_uses": [],
        "warnings": [reason],
        "operator_prompt": "",
        "structured_measurement_template": {},
        "forbidden_claims": [],
    }


def _compact_dict(row: Dict[str, Any], *, keys: Sequence[str]) -> Dict[str, Any]:
    return {key: row.get(key) for key in keys if key in row and row.get(key) not in (None, "", [], {})}


def _dict_rows(value: Any, *, limit: int) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value[:limit] if isinstance(row, dict)]


def _string_rows(value: Any, *, limit: int) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(row) for row in value[:limit] if str(row).strip()]


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(raw, strict=False)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start:end], strict=False)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _claim_boundary() -> str:
    return (
        "Live model advisory can prioritize and format field measurements only. "
        "It cannot verify power, no-short, pinout, current, thermal behavior, splice safety, repair authority, or production release."
    )
