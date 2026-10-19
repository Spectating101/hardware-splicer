"""Discoverable request documentation for the canonical mission handlers.

This is an OpenAPI projection, not another validator or mission store. Structural
examples cannot establish engineering validity: MissionStore remains the owner
of sequence, budget, evidence, donor, readiness and authority checks.
"""
from __future__ import annotations

from typing import Any

from .mission_donors import _METHODS
from .mission_store import (
    TERMINAL_STATES, _AUTHOR_KEYS, _BLOCKED_STATES, _CANDIDATE_KINDS,
    _DIMENSIONAL_QUANTITIES, _EVAL_OPERATIONS, _MAX_AUTHOR_ID, _MAX_LABEL, _MAX_NEED,
    _MAX_RATIONALE, _MAX_REASON, _REQUEST_KINDS, _SLUG_RE,
)


def _text(limit: int) -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": limit}


def _object(properties: dict, required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def _body(schema: dict, examples: dict, description: str) -> dict[str, Any]:
    return {"requestBody": {"required": True, "description": description,
                           "content": {"application/json": {"schema": schema, "examples": examples}}}}


def mission_event_openapi() -> dict[str, Any]:
    """Describe all agent proposal envelopes, using the canonical enum values."""
    slug = {"type": "string", "pattern": _SLUG_RE.pattern}
    spec = {"type": "object", "description": (
        "Unvalidated design proposal, not measured facts. Replace with your draft/design spec. "
        "GET /v1/devices/spec-schema describes the planner's structure; donor IDs require frozen mission context. "
        "Partial specs may be proposed but cannot earn readiness without the canonical checks. "
        "Read spec_diagnostics and donor_coverage in the returned candidate/context: unrecognized keys remain "
        "stored but are not checked by the catalog planner. donors_used is a reference, not proof of wiring.")}
    candidate = _object({
        "id": slug, "kind": {"enum": sorted(_CANDIDATE_KINDS)},
        "label": _text(_MAX_LABEL), "spec": spec, "rationale": _text(_MAX_RATIONALE),
    }, ["id", "kind", "label", "spec", "rationale"])
    citations = {"type": "array", "maxItems": 40, "items": {"type": "integer", "minimum": 1}}
    request = _object({
        "kind": {"enum": sorted(_REQUEST_KINDS)}, "target": _text(200),
        "quantity": _text(32), "signal": _text(120), "instructions": _text(_MAX_NEED),
        "expected": _object({"min": {"type": "number"}, "max": {"type": "number"}, "unit": _text(10)},
                            ["min", "max", "unit"]),
    }, ["kind", "target", "instructions"])
    request["description"] = (
        "A request, never a measurement or approval. Dimensional targets must be library module IDs and quantities "
        "pcb_mm.x/pcb_mm.y/pcb_mm.z/above_board_mm. Electrical/continuity requires a short quantity name; "
        "only those donor-target requests may name signal. boot_log has no quantity. Expected min must not exceed max."
    )
    request["allOf"] = [
        {"if": {"properties": {"kind": {"enum": ["dimensional", "electrical", "continuity"]}}},
         "then": {"required": ["quantity"]}},
        {"if": {"properties": {"kind": {"const": "dimensional"}}},
         "then": {"properties": {"quantity": {"enum": sorted(_DIMENSIONAL_QUANTITIES)}}}},
        {"if": {"properties": {"kind": {"const": "boot_log"}}},
         "then": {"not": {"required": ["quantity"]}}},
        {"if": {"required": ["signal"]},
         "then": {"properties": {"kind": {"enum": ["electrical", "continuity"]},
                                  "target": {"pattern": "^donor:"}}}},
    ]
    finding = _object({
        "donor_id": {"type": "string", "pattern": r"^donor:[a-z0-9][a-z0-9-]{0,63}:[a-z0-9][a-z0-9-]{0,63}$"},
        "signal": {"anyOf": [_text(120), {"type": "null"}]},
        "claim": _text(4000), "method": {"enum": sorted(_METHODS)}, "source": _text(200),
        "artifacts": {"type": "array", "maxItems": 20, "items": _object({
            "name": _text(200), "sha256": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$"},
        }, ["name", "sha256"])},
    }, ["donor_id", "claim", "method", "source", "artifacts"])
    finding["description"] = "Donor must be in this mission intake. All findings remain re_observation; hashes are unverified references."
    events = [
        _object({"type": {"const": "candidate_proposed"}, "candidate": candidate}, ["type", "candidate"]),
        _object({"type": {"const": "repair_proposed"}, "candidate_id": slug,
                 "spec": spec, "rationale": _text(_MAX_RATIONALE)},
                ["type", "candidate_id", "spec", "rationale"]),
        _object({"type": {"const": "evidence_required"}, "blocker": {"enum": sorted(_BLOCKED_STATES)},
                 "need": _text(_MAX_NEED), "candidate_id": slug, "request": request, "cites": citations},
                ["type", "blocker", "need"]),
        _object({"type": {"const": "finding_offered"}, "finding": finding}, ["type", "finding"]),
        _object({"type": {"const": "terminal_proposed"}, "state": {"enum": list(TERMINAL_STATES)},
                 "reason": _text(_MAX_REASON), "candidate_id": slug, "cites": citations},
                ["type", "state", "reason"]),
    ]
    events[2]["description"] = (
        "Persist any concern in the mission, not only in chat. For an unsafe goal use BLOCKED_UNSAFE and explain "
        "the danger/refusal and a separate safer goal if justified. It is an agent_assertion, not an HS safety "
        "finding. Do not disguise an unsafe goal as missing part data or request hazardous powered measurements. "
        "To stop, propose terminal BLOCKED_UNSAFE citing this need's returned sequence. Otherwise leave a "
        "resumable need open and continue only independent, safe, evidence-grounded work.")
    author = _object({"kind": {"enum": ["agent", "human"]}, "id": _text(_MAX_AUTHOR_ID)}, sorted(_AUTHOR_KEYS))
    schema = _object({
        "event": {"oneOf": events, "discriminator": {"propertyName": "type"}},
        "author": author,
        "expected_event_seq": {"type": "integer", "minimum": 0,
                               "description": "Use last_event_seq from a fresh mission context; reload after HTTP 409."},
    }, ["event", "author"])
    schema["description"] = "Structural request contract only. Canonical runtime checks still decide admissibility."
    proposals = {
        "candidate_proposed": {"type": "candidate_proposed", "candidate": {
            "id": "A", "kind": "reclaim_heavy", "label": "Reuse candidate",
            "spec": {}, "rationale": "Replace spec with the actual grounded draft/design before evaluation."}},
        "repair_proposed": {"type": "repair_proposed", "candidate_id": "A", "spec": {},
                            "rationale": "Replace spec with a repair grounded in a failed check or new human evidence."},
        "evidence_required": {"type": "evidence_required", "blocker": "BLOCKED_NEEDS_REVERSE_ENGINEERING",
                              "need": "Resolve the donor interface from trustworthy documentation; no measurement is claimed."},
        "finding_offered": {"type": "finding_offered", "finding": {
            "donor_id": "donor:example:block", "signal": None,
            "claim": "Replace with a bounded observation from the named source.",
            "method": "document", "artifacts": [], "source": "Replace with the actual document locator."}},
        "terminal_proposed": {"type": "terminal_proposed", "state": "READY_FOR_HUMAN_BUILD",
                              "candidate_id": "A", "reason": "Only submit after HS checks establish readiness."},
    }
    examples = {
        name: {"summary": "Template: replace placeholder content and use the current event sequence",
               "value": {"event": event, "author": {"kind": "agent", "id": "salvage-agent"},
                         "expected_event_seq": 0}}
        for name, event in proposals.items()
    }
    return _body(schema, examples, (
        "Propose one event, never an evaluation or authority promotion. Templates are not ready designs. "
        "Use current last_event_seq; human acceptance is required for execution and findings. "
        "A physical-evidence request pauses for a person; do not terminalize a mission you intend to resume."))


def mission_run_openapi() -> dict[str, Any]:
    return _body(
        _object({"operation": {"enum": sorted(_EVAL_OPERATIONS)}}, ["operation"]),
        {operation: {"value": {"operation": operation}} for operation in sorted(_EVAL_OPERATIONS)},
        "Run one software-only check on an accepted mission's stored candidate, spending one operator job. "
        "For intact host-input-device reuse, first read the mission's intact-reuse-spec, then run intact_reuse "
        "to produce/test a software review bundle even while physical evidence is missing; read its run and download "
        "runs/{name}/bundle. This does not count as a device_plan/device_engineering pass or READY. "
        "For catalog readiness, run device_plan first and device_engineering after a clean plan. "
        "Do not claim a prior check is current after repair or new evidence. Read the returned hashed artifact for details.",
    )
