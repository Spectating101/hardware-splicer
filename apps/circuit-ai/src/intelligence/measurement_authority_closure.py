"""Close visual measurement tasks into topology and repair authority.

This artifact connects the operator loop:
visual candidates -> targeted bench capture -> topology evidence -> authority
delta. It does not treat templates or reference pinouts as measurements.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from src.intelligence.authority_ledger import build_authority_ledger
from src.intelligence.bench_topology_capture import (
    bench_capture_to_topology_evidence,
    build_bench_capture_template,
    enrich_payload_with_bench_topology_capture,
    extract_bench_topology_capture,
)
from src.intelligence.board_omniscience_map import build_board_omniscience_map
from src.intelligence.multiview_board_evidence import fuse_board_photo_set
from src.intelligence.production_casefile import build_production_casefile
from src.intelligence.topology_evidence import (
    enrich_payload_with_topology_evidence,
    extract_topology_evidence,
    topology_evidence_bridge,
)
from src.intelligence.topology_netlist_compiler import compile_topology_to_netlist
from src.intelligence.visual_topology_hypothesis import build_visual_topology_hypothesis


SCHEMA_VERSION = "measurement_authority_closure.v1"
TRUST_KEYS = ("instrument_id", "instrument_type", "calibration_status", "recorded_at", "operator_id", "evidence_uri")
PRODUCTION_CATEGORIES = {"resistance", "continuity", "voltage", "current", "thermal"}


def build_measurement_authority_closure(
    payload: Dict[str, Any],
    *,
    include_casefile: bool = True,
    include_omniscience: bool = True,
) -> Dict[str, Any]:
    """Build a before/after authority closure packet for bench measurements."""

    body = _prepare_visual_context(payload or {})
    baseline_payload = _strip_measurement_authority(body)
    before_ledger = build_authority_ledger(baseline_payload)

    capture = extract_bench_topology_capture(body)
    reference = _reference_topology(body)
    board = _board_evidence(body)
    template = build_bench_capture_template(
        reference_topology=reference or None,
        board_evidence=board or None,
    )
    visual_topology = build_visual_topology_hypothesis(body)

    topology = {}
    if capture:
        topology = bench_capture_to_topology_evidence(capture, reference_topology=reference or None)
        enriched = enrich_payload_with_bench_topology_capture(body)
        enriched = enrich_payload_with_topology_evidence(enriched)
    else:
        topology = extract_topology_evidence(body)
        enriched = enrich_payload_with_topology_evidence(body) if topology else body

    bridge = topology_evidence_bridge(topology) if topology else {}
    after_ledger = build_authority_ledger(enriched)
    compiled = compile_topology_to_netlist(enriched) if topology else _empty_netlist_result()
    casefile = build_production_casefile(enriched, live_model_advisory=False) if include_casefile else None
    omniscience = build_board_omniscience_map(enriched, include_evidence_graph=False) if include_omniscience else None
    integrity = _capture_integrity(capture, topology, bridge)
    delta = _authority_delta(before_ledger, after_ledger)
    next_action = _next_action(after_ledger, integrity, compiled, casefile, omniscience)

    return {
        "mode": "measurement_authority_closure",
        "schema_version": SCHEMA_VERSION,
        "available": True,
        "capture_packet": {
            "schema_version": "measurement_authority_capture_packet.v1",
            "bench_topology_capture_template": template,
            "visual_topology_measurement_queue": _list_dicts(visual_topology.get("measurement_queue"))[:60],
            "targeted_measurement_count": len([task for task in _list_dicts(visual_topology.get("measurement_queue")) if task.get("target")]),
            "reference_seed_is_not_evidence": True,
            "expected_submit_schema": "bench_topology_capture.v1",
        },
        "capture_integrity": integrity,
        "topology_evidence": topology,
        "topology_evidence_bridge": bridge,
        "topology_netlist_compilation": compiled,
        "authority_before": _ledger_summary(before_ledger),
        "authority_after": _ledger_summary(after_ledger),
        "authority_delta": delta,
        "production_casefile": casefile,
        "board_omniscience_map": omniscience,
        "next_action": next_action,
        "claim_boundary": (
            "This closure packet reports what measured evidence unlocks. It does not convert reference pinouts, visual "
            "geometry, or model text into physical repair authority."
        ),
    }


def _prepare_visual_context(payload: Dict[str, Any]) -> Dict[str, Any]:
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
    if not isinstance(body.get("visual_topology_hypothesis"), dict):
        visual_topology = build_visual_topology_hypothesis(body)
        if visual_topology.get("available"):
            body["visual_topology_hypothesis"] = visual_topology
    return body


def _strip_measurement_authority(payload: Dict[str, Any]) -> Dict[str, Any]:
    stripped = dict(payload or {})
    for key in [
        "bench_topology_capture",
        "topology_evidence",
        "topology_evidence_bridge",
        "topology_authority",
        "measurements",
        "outcome_history",
        "outcomes",
        "functional_outcome",
        "production_release",
        "release_manifest",
        "repair_authority",
    ]:
        stripped.pop(key, None)
    analysis = stripped.get("analysis") if isinstance(stripped.get("analysis"), dict) else {}
    if analysis:
        analysis = dict(analysis)
        for key in [
            "bench_topology_capture",
            "bench_topology_evidence",
            "topology_evidence",
            "topology_evidence_bridge",
            "topology_authority",
            "functional_outcome",
        ]:
            analysis.pop(key, None)
        stripped["analysis"] = analysis
    return stripped


def _reference_topology(payload: Dict[str, Any]) -> Dict[str, Any]:
    for key in ["reference_topology", "topology_reference"]:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _board_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    candidates = [
        payload.get("board_evidence"),
        (payload.get("multiview_board_reconstruction") or {}).get("board_evidence")
        if isinstance(payload.get("multiview_board_reconstruction"), dict)
        else None,
    ]
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    candidates.extend(
        [
            analysis.get("board_evidence"),
            (analysis.get("multiview_board_reconstruction") or {}).get("board_evidence")
            if isinstance(analysis.get("multiview_board_reconstruction"), dict)
            else None,
        ]
    )
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            return candidate
    return {}


def _capture_integrity(capture: Dict[str, Any], topology: Dict[str, Any], bridge: Dict[str, Any]) -> Dict[str, Any]:
    normalized = bridge.get("topology_evidence") if isinstance(bridge.get("topology_evidence"), dict) else topology if isinstance(topology, dict) else {}
    capture_summary = normalized.get("capture_summary") if isinstance(normalized.get("capture_summary"), dict) else {}
    measurements = _list_dicts(bridge.get("measurement_rows"))
    topology_authority = bridge.get("topology_authority") if isinstance(bridge.get("topology_authority"), dict) else {}

    root_missing = [key for key in TRUST_KEYS if not str(normalized.get(key) or "").strip()]
    categories = _measurement_categories(measurements, require_trusted=False, require_artifact=False)
    trusted = _measurement_categories(measurements, require_trusted=True, require_artifact=False)
    artifact_backed = _measurement_categories(measurements, require_trusted=False, require_artifact=True)
    missing_categories = sorted(PRODUCTION_CATEGORIES - categories)
    missing_trusted = sorted(PRODUCTION_CATEGORIES - trusted)
    missing_artifacts = sorted(PRODUCTION_CATEGORIES - artifact_backed)
    shorts = bool(topology_authority.get("shorts_detected"))
    pinout_known = bool(topology_authority.get("pinout_known"))
    if shorts:
        verdict = "safety_blocked"
    elif not capture and not topology:
        verdict = "measurement_capture_required"
    elif missing_categories or missing_trusted or missing_artifacts or not pinout_known:
        verdict = "measurement_capture_incomplete"
    else:
        verdict = "production_measurement_packet_ready"

    return {
        "schema_version": "measurement_capture_integrity.v1",
        "capture_available": bool(capture),
        "topology_available": bool(bridge.get("available")),
        "actionable_topology": bool(capture_summary.get("observation_count") or capture_summary.get("verified_pin_count") or bridge.get("available")),
        "reference_only": bool(bridge.get("reference_only")),
        "trusted_root_provenance": not root_missing if normalized else False,
        "missing_root_provenance": root_missing,
        "connector_count": topology_authority.get("connector_count", 0),
        "known_pin_count": topology_authority.get("known_pin_count", 0),
        "unknown_pin_count": topology_authority.get("unknown_pin_count", 0),
        "pinout_known": pinout_known,
        "shorts_detected": shorts,
        "measurement_count": len(measurements),
        "trusted_measurement_count": len([row for row in measurements if _trusted(row)]),
        "measurement_categories": sorted(categories),
        "trusted_categories": sorted(trusted),
        "artifact_categories": sorted(artifact_backed),
        "missing_measurement_categories": missing_categories,
        "missing_trusted_categories": missing_trusted,
        "missing_artifact_categories": missing_artifacts,
        "verdict": verdict,
        "claim_boundary": "Integrity covers measurement packet auditability only; functional outcome and release manifest are separate gates.",
    }


def _measurement_categories(
    measurements: Sequence[Dict[str, Any]],
    *,
    require_trusted: bool,
    require_artifact: bool,
) -> set[str]:
    categories: set[str] = set()
    for measurement in measurements:
        if require_trusted and not _trusted(measurement):
            continue
        if require_artifact and not str(measurement.get("evidence_uri") or "").strip():
            continue
        if str(measurement.get("status") or "").lower() not in {"pass", "passed", "ok", "verified", "measured", "normal"}:
            continue
        categories.update(_categories_for_measurement(measurement))
    return categories


def _categories_for_measurement(measurement: Dict[str, Any]) -> List[str]:
    text = " ".join(
        str(measurement.get(key) or "")
        for key in ["type", "category", "target", "notes", "unit"]
    ).lower()
    categories = []
    if "resistance" in text or "ohm" in text or "no-short" in text or "no short" in text or "short" in text:
        categories.append("resistance")
    if "continuity" in text or "ground" in text or "common" in text:
        categories.append("continuity")
    if "voltage" in text or "logic" in text or "polarity" in text or " v" in f" {text}":
        categories.append("voltage")
    if "current" in text or "draw" in text or "amp" in text:
        categories.append("current")
    if "thermal" in text or "temperature" in text or "heat" in text:
        categories.append("thermal")
    return _dedupe(categories)


def _trusted(measurement: Dict[str, Any]) -> bool:
    return all(str(measurement.get(key) or "").strip() for key in TRUST_KEYS)


def _authority_delta(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    before_level = str(before.get("current_authority_level") or "no_authority")
    after_level = str(after.get("current_authority_level") or "no_authority")
    before_score = _safe_float(before.get("authority_score"), 0.0)
    after_score = _safe_float(after.get("authority_score"), 0.0)
    return {
        "schema_version": "authority_delta.v1",
        "before_level": before_level,
        "after_level": after_level,
        "before_score": before_score,
        "after_score": after_score,
        "score_delta": round(after_score - before_score, 3),
        "level_delta": _level_index(after_level) - _level_index(before_level),
        "stage_status_before": _stage_status(before),
        "stage_status_after": _stage_status(after),
        "newly_passed_stages": [
            stage
            for stage, status in _stage_status(after).items()
            if status == "pass" and _stage_status(before).get(stage) != "pass"
        ],
    }


def _ledger_summary(ledger: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "current_authority_level": ledger.get("current_authority_level"),
        "authority_score": ledger.get("authority_score"),
        "can": ledger.get("can") if isinstance(ledger.get("can"), dict) else {},
        "next_unlocks": ledger.get("next_unlocks") or [],
        "stage_status": _stage_status(ledger),
    }


def _next_action(
    ledger: Dict[str, Any],
    integrity: Dict[str, Any],
    compiled: Dict[str, Any],
    casefile: Dict[str, Any] | None,
    omniscience: Dict[str, Any] | None,
) -> Dict[str, Any]:
    can = ledger.get("can") if isinstance(ledger.get("can"), dict) else {}
    if integrity.get("shorts_detected"):
        return _action("resolve_measured_hazard", "Resolve the measured short or hard topology hazard before power, splice, or reuse.", "safety")
    if not integrity.get("capture_available") and not integrity.get("topology_available"):
        return _action("record_bench_topology_capture", "Fill and submit bench_topology_capture.v1 with pinout, no-short, voltage, current, thermal, instrument, operator, timestamp, and artifact URIs.", "measurement")
    if integrity.get("verdict") == "measurement_capture_incomplete":
        missing = _dedupe(
            [
                *[f"measurement:{item}" for item in integrity.get("missing_measurement_categories") or []],
                *[f"trusted:{item}" for item in integrity.get("missing_trusted_categories") or []],
                *[f"artifact:{item}" for item in integrity.get("missing_artifact_categories") or []],
                *[f"root:{item}" for item in integrity.get("missing_root_provenance") or []],
            ]
        )
        return {
            **_action("complete_measurement_capture", "Complete missing measured categories and audit provenance before claiming production authority.", "measurement"),
            "missing": missing[:20],
        }
    if can.get("claim_production_repair_release"):
        return _action("release_ready", "Production repair/reuse authority is closed for the recorded scope.", "release")
    if can.get("claim_controlled_reuse"):
        return _action("attach_release_manifest", "Attach a complete production_release/release_manifest with scoped resource IDs and artifact URIs.", "release")
    if can.get("run_controlled_bench"):
        return _action("record_controlled_bench_outcome", "Run and record the controlled bench outcome: first power, current, thermal, and function proof.", "bench")
    if compiled.get("available"):
        return _action("run_controlled_bench_outcome", "Topology and simulation are available; run the controlled bench outcome under current limits.", "bench")
    if omniscience and isinstance(omniscience.get("summary"), dict) and omniscience["summary"].get("next_best_action_id"):
        return _action(str(omniscience["summary"]["next_best_action_id"]), "Continue the omniscience map next evidence action.", "evidence")
    next_unlocks = ledger.get("next_unlocks") if isinstance(ledger.get("next_unlocks"), list) else []
    if next_unlocks:
        unlock = next_unlocks[0] if isinstance(next_unlocks[0], dict) else {"next_unlock": str(next_unlocks[0])}
        return _action(str(unlock.get("stage_id") or "next_authority_unlock"), str(unlock.get("next_unlock") or unlock), "authority")
    if casefile and isinstance(casefile.get("summary"), dict) and casefile["summary"].get("next_action_id"):
        return _action(str(casefile["summary"]["next_action_id"]), "Continue the production casefile next action.", "casefile")
    return _action("review_closure_packet", "Review the closure packet and attach missing evidence if any gates remain open.", "review")


def _action(action_id: str, prompt: str, category: str) -> Dict[str, Any]:
    return {
        "action_id": action_id,
        "category": category,
        "prompt": prompt,
    }


def _empty_netlist_result() -> Dict[str, Any]:
    return {
        "schema_version": "topology_netlist_compiler.v1",
        "available": False,
        "reason": "No measured topology evidence is available yet.",
    }


def _stage_status(ledger: Dict[str, Any]) -> Dict[str, str]:
    return {
        str(stage.get("stage_id")): str(stage.get("status"))
        for stage in ledger.get("stages") or []
        if isinstance(stage, dict) and stage.get("stage_id")
    }


def _level_index(level: str) -> int:
    levels = [
        "no_authority",
        "visual_candidate",
        "measured_topology",
        "electrical_simulation",
        "controlled_bench",
        "production_repair",
    ]
    if level == "blocked_safety_or_electrical":
        return -1
    try:
        return levels.index(level)
    except ValueError:
        return 0


def _has_photo_observations(body: Dict[str, Any]) -> bool:
    photo_set = body.get("board_photo_set") if isinstance(body.get("board_photo_set"), dict) else {}
    return bool(_list_dicts(photo_set.get("photo_observations")) or _list_dicts(body.get("photo_observations")))


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _dedupe(values: Iterable[Any]) -> List[str]:
    rows: List[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        rows.append(text)
    return rows


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return default
