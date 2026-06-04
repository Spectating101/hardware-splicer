"""Track operator progress while filling measured topology evidence.

This is the practical loop between a visual/topology measurement template and a
submitted bench_topology_capture packet. It reports which required readings are
closed, which are still open, and whether the packet is ready to hand to the
authority closure pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from src.intelligence.bench_topology_capture import extract_bench_topology_capture
from src.intelligence.measurement_authority_closure import build_measurement_authority_closure


SCHEMA_VERSION = "measurement_session_progress.v1"
PASS_STATUSES = {"pass", "passed", "ok", "verified", "measured", "normal"}
FAIL_STATUSES = {"fail", "failed", "unsafe", "short", "shorted", "blocked"}


def build_measurement_session_progress(
    payload: Dict[str, Any],
    *,
    include_authority_closure: bool = True,
) -> Dict[str, Any]:
    """Return progress against the bench topology capture template."""

    body = dict(payload or {})
    closure = build_measurement_authority_closure(
        body,
        include_casefile=False,
        include_omniscience=False,
    )
    packet = closure.get("capture_packet") if isinstance(closure.get("capture_packet"), dict) else {}
    template = packet.get("bench_topology_capture_template") if isinstance(packet.get("bench_topology_capture_template"), dict) else {}
    required = _required_measurements(template)
    capture = extract_bench_topology_capture(body)
    submitted = _submitted_measurements(body, capture)
    matched_keys = set()
    required_status = []

    for index, requirement in enumerate(required, start=1):
        match = _match_requirement(requirement, submitted)
        if match:
            matched_keys.add(_measurement_key(match))
        status = _measurement_status(match)
        required_status.append(
            {
                "requirement_id": f"required_{index}",
                "kind": requirement.get("kind"),
                "target": requirement.get("target"),
                "notes": requirement.get("notes"),
                "unit": requirement.get("unit"),
                "status": status,
                "submitted_measurement_id": match.get("measurement_id") if match else None,
                "submitted_value": match.get("value") if match else None,
                "submitted_unit": match.get("unit") if match else None,
                "evidence_uri": match.get("evidence_uri") if match else None,
            }
        )

    unmatched = [row for row in submitted if _measurement_key(row) not in matched_keys]
    closed = [row for row in required_status if row["status"] in {"pass", "failed", "recorded"}]
    failed = [row for row in required_status if row["status"] == "failed"]
    open_rows = [row for row in required_status if row["status"] == "open"]
    integrity = closure.get("capture_integrity") if isinstance(closure.get("capture_integrity"), dict) else {}
    next_requirement = open_rows[0] if open_rows else {}
    authority_ready = bool(integrity.get("verdict") == "production_measurement_packet_ready")

    progress = {
        "schema_version": "measurement_session_progress_summary.v1",
        "required_count": len(required_status),
        "closed_count": len(closed),
        "open_count": len(open_rows),
        "failed_count": len(failed),
        "submitted_count": len(submitted),
        "unmatched_submitted_count": len(unmatched),
        "progress_score": round(len(closed) / max(len(required_status), 1), 3),
        "capture_verdict": integrity.get("verdict"),
        "authority_packet_ready": authority_ready,
        "template_complete": not open_rows and not failed,
    }
    status = _session_status(progress, integrity)
    next_requirement = {} if authority_ready else next_requirement
    result = {
        "mode": "measurement_session_progress",
        "schema_version": SCHEMA_VERSION,
        "available": True,
        "status": status,
        "progress": progress,
        "next_measurement": _next_measurement(next_requirement, packet),
        "required_measurements": required_status,
        "submitted_measurements": submitted[:80],
        "unmatched_submitted_measurements": unmatched[:24],
        "capture_integrity": integrity,
        "draft_bench_topology_capture": _draft_capture(template, capture, submitted),
        "authority_closure": closure if include_authority_closure else None,
        "claim_boundary": (
            "Session progress means the operator packet is becoming complete. It does not itself authorize power, "
            "splice, or repair; authority comes from measured topology closure and downstream outcome/release gates."
        ),
    }
    return result


def _required_measurements(template: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for index, row in enumerate(_list_dicts(template.get("measurements")), start=1):
        target = str(row.get("target") or "").strip()
        kind = str(row.get("kind") or row.get("type") or "").strip()
        if not target or not kind:
            continue
        rows.append(
            {
                "requirement_id": str(row.get("requirement_id") or f"template_{index}"),
                "kind": kind,
                "target": target,
                "unit": str(row.get("unit") or ""),
                "notes": str(row.get("notes") or ""),
            }
        )
    return _dedupe_rows(rows, key_fields=("kind", "target"))


def _submitted_measurements(body: Dict[str, Any], capture: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    candidates = [
        capture.get("measurements") if isinstance(capture, dict) else None,
        capture.get("observations") if isinstance(capture, dict) else None,
        capture.get("readings") if isinstance(capture, dict) else None,
        capture.get("tests") if isinstance(capture, dict) else None,
        body.get("measurement_updates"),
        body.get("measurements"),
    ]
    for values in candidates:
        for row in _list_dicts(values):
            kind = str(row.get("kind") or row.get("type") or row.get("measurement_type") or "").strip()
            target = str(row.get("target") or row.get("prompt") or row.get("net") or row.get("pin") or "").strip()
            if not target and (row.get("from") or row.get("to")):
                target = f"{row.get('from')} to {row.get('to')}"
            if not kind or not target:
                continue
            rows.append(
                {
                    "measurement_id": str(row.get("measurement_id") or row.get("observation_id") or row.get("id") or f"measurement_{len(rows) + 1}"),
                    "kind": kind,
                    "target": target,
                    "value": row.get("value", row.get("reading", row.get("result", ""))),
                    "unit": str(row.get("unit") or row.get("units") or ""),
                    "status": str(row.get("status") or row.get("result") or ""),
                    "notes": str(row.get("notes") or row.get("summary") or ""),
                    "instrument_id": str(row.get("instrument_id") or row.get("instrument_ref") or ""),
                    "evidence_uri": str(row.get("evidence_uri") or row.get("artifact_uri") or ""),
                }
            )
    return _dedupe_rows(rows, key_fields=("kind", "target", "value", "unit"))


def _match_requirement(requirement: Dict[str, Any], submitted: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    requirement_key = _target_key(requirement)
    exact = [
        row
        for row in submitted
        if _kind_key(row) == _kind_key(requirement) and _target_key(row) == requirement_key
    ]
    if exact:
        return exact[0]
    for row in submitted:
        if _kind_key(row) != _kind_key(requirement):
            continue
        row_target = _target_key(row)
        if row_target and (row_target in requirement_key or requirement_key in row_target):
            return row
    return {}


def _measurement_status(row: Dict[str, Any]) -> str:
    if not row:
        return "open"
    text = " ".join(str(row.get(key) or "") for key in ["status", "value", "notes"]).lower()
    if any(term in text for term in FAIL_STATUSES):
        return "failed"
    if any(term in text for term in PASS_STATUSES):
        return "pass"
    if str(row.get("value") or "").strip():
        return "recorded"
    return "open"


def _next_measurement(row: Dict[str, Any], packet: Dict[str, Any]) -> Dict[str, Any]:
    if not row:
        return {
            "action_id": "submit_authority_closure",
            "prompt": "All template measurements are recorded; submit the packet to authority closure and continue outcome/release gates.",
        }
    visual_queue = _list_dicts(packet.get("visual_topology_measurement_queue"))
    row_key = _target_key(row)
    visual_target = next(
        (
            task.get("target")
            for task in visual_queue
            if isinstance(task.get("target"), dict) and _target_key(task.get("target")) and row_key and _target_key(task.get("target")) in row_key
        ),
        {},
    )
    return {
        "action_id": f"record_{_safe_id(row.get('kind'))}_{_safe_id(row.get('target'))}",
        "kind": row.get("kind"),
        "target": row.get("target"),
        "unit": row.get("unit"),
        "prompt": row.get("notes") or f"Record {row.get('kind')} for {row.get('target')}.",
        "target_geometry": visual_target,
    }


def _draft_capture(template: Dict[str, Any], capture: Dict[str, Any], submitted: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    draft = dict(template or {})
    if capture:
        for key, value in capture.items():
            if value not in (None, "", [], {}):
                draft[key] = value
    draft["schema_version"] = "bench_topology_capture.v1"
    draft["measurements"] = list(submitted) if submitted else _list_dicts(draft.get("measurements"))
    return draft


def _session_status(progress: Dict[str, Any], integrity: Dict[str, Any]) -> str:
    if integrity.get("shorts_detected") or progress.get("failed_count"):
        return "safety_blocked"
    if progress.get("authority_packet_ready"):
        return "authority_packet_ready"
    if progress.get("closed_count"):
        return "measurement_in_progress"
    return "waiting_for_measurements"


def _kind_key(row: Dict[str, Any]) -> str:
    return str(row.get("kind") or row.get("type") or "").strip().lower()


def _target_key(row: Dict[str, Any]) -> str:
    text = " ".join(
        str(row.get(key) or "")
        for key in ["target", "label", "ref", "map_id"]
    ).lower()
    return " ".join("".join(char if char.isalnum() else " " for char in text).split())


def _measurement_key(row: Dict[str, Any]) -> tuple[str, str, str, str]:
    return (_kind_key(row), _target_key(row), str(row.get("value") or ""), str(row.get("unit") or ""))


def _safe_id(value: Any) -> str:
    text = str(value or "measurement").strip().lower()
    chars = [char if char.isalnum() else "_" for char in text]
    return "_".join(part for part in "".join(chars).split("_") if part)[:80] or "measurement"


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _dedupe_rows(rows: Iterable[Dict[str, Any]], *, key_fields: Sequence[str]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = tuple(str(row.get(field) or "").strip().lower() for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept
