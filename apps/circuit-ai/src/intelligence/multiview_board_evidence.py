"""Fuse multiple board-photo observations into one candidate board dossier.

This is intentionally not tied to fixed capture slots such as top/bottom. A
photo set is a bag of visual observations: wide shots, closeups, angles,
connector crops, marking crops, or model outputs from different providers.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

from src.intelligence.vision_board_evidence import board_evidence_bridge, extract_board_evidence


SCHEMA_VERSION = "multiview_board_reconstruction.v1"
ARRAY_KEYS = ["components", "markings", "regions", "damage", "connectors", "test_points", "salvage_candidates"]


def enrich_payload_with_multiview_board_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach fused multi-photo evidence before the normal board-evidence bridge."""

    body = dict(payload or {})
    reconstruction = fuse_board_photo_set(body)
    if not reconstruction.get("available"):
        return body

    analysis = dict(body.get("analysis") if isinstance(body.get("analysis"), dict) else {})
    analysis["multiview_board_reconstruction"] = reconstruction
    analysis["board_evidence"] = reconstruction["board_evidence"]
    body["analysis"] = analysis
    body["board_evidence"] = reconstruction["board_evidence"]
    body["multiview_board_reconstruction"] = reconstruction
    return body


def fuse_board_photo_set(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Fuse many visual observations into a single board_evidence.v1 object."""

    observations = _observation_rows(payload)
    groups: Dict[Tuple[str, str], Dict[str, Any]] = {}
    parse_rows: List[Dict[str, Any]] = []
    usable_observations = 0

    for index, observation in enumerate(observations, start=1):
        if not isinstance(observation, dict):
            continue
        photo_id = _photo_id(observation, index)
        evidence = extract_board_evidence(observation)
        if not evidence:
            continue
        usable_observations += 1
        parse_rows.append(_parse_summary(photo_id, observation))
        normalized = board_evidence_bridge(evidence).get("board_evidence") or {}
        for array_key in ARRAY_KEYS:
            for item in normalized.get(array_key) or []:
                if not isinstance(item, dict):
                    continue
                group_key = (array_key, _item_key(array_key, item))
                aggregate = groups.setdefault(group_key, _new_group(array_key, item))
                _merge_item(aggregate, item, photo_id=photo_id, observation=observation)

    board_evidence = _fused_board_evidence(groups)
    identity_links = _identity_links(board_evidence)
    _apply_identity_links(board_evidence, identity_links)
    canonical_map = _canonical_board_map(board_evidence, observations)
    capture_coverage = _capture_coverage(observations, board_evidence, canonical_map, identity_links)
    board_evidence["multiview_reconstruction"] = {
        "schema_version": SCHEMA_VERSION,
        "usable_observation_count": usable_observations,
        "photo_ids": [row["photo_id"] for row in parse_rows if row.get("photo_id")],
        "identity_link_count": len(identity_links),
        "layout_confidence": canonical_map.get("layout_confidence"),
        "capture_coverage_score": capture_coverage.get("score"),
        "capture_coverage_complete": capture_coverage.get("required_complete"),
    }
    bridge = board_evidence_bridge(board_evidence) if any(board_evidence.get(key) for key in ARRAY_KEYS) else {}
    reconstruction = {
        "schema_version": SCHEMA_VERSION,
        "available": bool(usable_observations and bridge.get("available")),
        "input_observation_count": len(observations),
        "usable_observation_count": usable_observations,
        "photo_evidence": parse_rows,
        "board_evidence": board_evidence,
        "vision_evidence_bridge": bridge,
        "canonical_board_map": canonical_map,
        "capture_coverage": capture_coverage,
        "identity_links": identity_links,
        "reconstruction_summary": _reconstruction_summary(board_evidence, observations, usable_observations, canonical_map, identity_links, capture_coverage),
        "contradictions": _contradictions(groups),
        "next_capture_requests": _next_capture_requests(board_evidence, len(observations), usable_observations, canonical_map, identity_links, capture_coverage),
        "policy": {
            "fixed_view_slots_required": False,
            "photos_are_observations": True,
            "fusion_is_candidate_only": True,
            "measurements_still_required_for_power_or_splice": True,
        },
    }
    return reconstruction


def _observation_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    roots = [payload.get("board_photo_set"), payload.get("photo_set"), payload]
    for root in roots:
        if isinstance(root, list):
            rows.extend(item for item in root if isinstance(item, dict))
            continue
        if not isinstance(root, dict):
            continue
        for key in ["photo_observations", "board_photos", "visual_observations", "observations", "photos", "views", "captures", "images"]:
            value = root.get(key)
            if isinstance(value, list):
                rows.extend(item for item in value if isinstance(item, dict))
        if extract_board_evidence(root):
            rows.append(root)
    return _dedupe_observations(rows)


def _dedupe_observations(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for index, row in enumerate(rows, start=1):
        key = str(row.get("photo_id") or row.get("view_id") or row.get("capture_id") or row.get("image_id") or row.get("id") or index)
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept[:48]


def _photo_id(observation: Dict[str, Any], index: int) -> str:
    return _safe_id(
        observation.get("photo_id")
        or observation.get("view_id")
        or observation.get("capture_id")
        or observation.get("image_id")
        or observation.get("id")
        or f"photo_{index}"
    )


def _parse_summary(photo_id: str, observation: Dict[str, Any]) -> Dict[str, Any]:
    qwen_board_vision = observation.get("qwen_board_vision") if isinstance(observation.get("qwen_board_vision"), dict) else {}
    qwen = observation.get("qwen") if isinstance(observation.get("qwen"), dict) else {}
    diagnostics = (
        observation.get("parse_diagnostics")
        or qwen_board_vision.get("parse_diagnostics")
        or qwen.get("parse_diagnostics")
        or {}
    )
    return {
        "photo_id": photo_id,
        "label": observation.get("label") or observation.get("filename") or observation.get("view_hint"),
        "view_hint": observation.get("view_hint") or observation.get("notes"),
        "provider": observation.get("provider") or qwen_board_vision.get("provider"),
        "json_valid": diagnostics.get("json_valid") if isinstance(diagnostics, dict) else None,
        "truncated": diagnostics.get("truncated") if isinstance(diagnostics, dict) else None,
    }


def _new_group(array_key: str, item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "array_key": array_key,
        "labels": [],
        "kinds": [],
        "warnings": [],
        "missing_evidence": [],
        "confidences": [],
        "source_refs": [],
        "best_item": dict(item),
    }


def _merge_item(aggregate: Dict[str, Any], item: Dict[str, Any], *, photo_id: str, observation: Dict[str, Any]) -> None:
    label = str(item.get("label") or item.get("kind") or aggregate["array_key"]).strip()
    kind = str(item.get("kind") or aggregate["array_key"]).strip()
    confidence = _safe_float(item.get("confidence"), 0.62)
    aggregate["labels"].append(label)
    aggregate["kinds"].append(kind)
    aggregate["warnings"].extend(_string_list(item.get("warnings")))
    aggregate["missing_evidence"].extend(_string_list(item.get("missing_evidence")))
    aggregate["confidences"].append(confidence)
    aggregate["source_refs"].append(
        {
            "photo_id": photo_id,
            "item_id": item.get("id"),
            "label": label,
            "bbox": item.get("bbox") or [],
            "bbox_role": _bbox_role(item.get("bbox") or []),
            "view_hint": observation.get("view_hint") or observation.get("notes"),
        }
    )
    best_conf = max(aggregate["confidences"] or [0.0])
    if confidence >= best_conf:
        aggregate["best_item"] = dict(item)


def _fused_board_evidence(groups: Dict[Tuple[str, str], Dict[str, Any]]) -> Dict[str, Any]:
    fused = {"schema_version": "board_evidence.v1", **{key: [] for key in ARRAY_KEYS}}
    pixel_frames = _pixel_bbox_frames(groups)
    for (array_key, key), aggregate in sorted(groups.items(), key=lambda row: (row[0][0], row[0][1])):
        best = dict(aggregate["best_item"])
        source_refs = _dedupe_source_refs(aggregate.get("source_refs") or [])
        support_count = len({ref.get("photo_id") for ref in source_refs if ref.get("photo_id")})
        labels = _dedupe(aggregate.get("labels") or [])
        kinds = _dedupe(aggregate.get("kinds") or [])
        confidence = min(0.95, max(aggregate.get("confidences") or [0.62]) + 0.05 * max(support_count - 1, 0))
        best.update(
            {
                "id": str(best.get("id") or f"{array_key}_{len(fused[array_key]) + 1}"),
                "label": labels[0] if labels else str(best.get("label") or array_key),
                "kind": kinds[0] if kinds else str(best.get("kind") or array_key),
                "confidence": round(confidence, 3),
                "source_refs": source_refs,
                "support_count": support_count,
                "cross_view": {
                    "item_key": key,
                    "supporting_photo_ids": [ref.get("photo_id") for ref in source_refs if ref.get("photo_id")],
                    "alternate_labels": labels[1:8],
                },
                "geometry": _geometry_consensus(source_refs, pixel_frames=pixel_frames),
                "warnings": _dedupe([*(_string_list(best.get("warnings"))), *(aggregate.get("warnings") or [])])[:10],
                "missing_evidence": _dedupe(
                    [*(_string_list(best.get("missing_evidence"))), *(aggregate.get("missing_evidence") or [])]
                )[:10],
            }
        )
        fused[array_key].append(best)
    return fused


def _identity_links(board_evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    components = [row for row in board_evidence.get("components") or [] if isinstance(row, dict)]
    markings = [row for row in board_evidence.get("markings") or [] if isinstance(row, dict)]
    for marking in markings:
        marking_text = " ".join(str(marking.get(key) or "") for key in ["marking", "visible_text", "label"]).strip()
        if not marking_text:
            continue
        best = None
        best_score = 0.0
        best_reasons: List[str] = []
        for component in components:
            score, reasons = _marking_component_link_score(marking_text, marking, component)
            if score > best_score:
                best = component
                best_score = score
                best_reasons = reasons
        if best and best_score >= 0.42:
            links.append(
                {
                    "link_id": f"identity_{_safe_id(marking.get('id'))}_{_safe_id(best.get('id'))}",
                    "type": "marking_resolves_component",
                    "confidence": round(min(best_score, 0.95), 3),
                    "marking_id": marking.get("id"),
                    "marking": marking_text,
                    "component_id": best.get("id"),
                    "component_label": best.get("label"),
                    "evidence": best_reasons[:6],
                    "source_photo_ids": _dedupe(
                        [
                            *[ref.get("photo_id") for ref in marking.get("source_refs") or [] if isinstance(ref, dict)],
                            *[ref.get("photo_id") for ref in best.get("source_refs") or [] if isinstance(ref, dict)],
                        ]
                    ),
                }
            )
    return links[:24]


def _apply_identity_links(board_evidence: Dict[str, Any], links: Sequence[Dict[str, Any]]) -> None:
    components = {
        str(row.get("id") or ""): row
        for row in board_evidence.get("components") or []
        if isinstance(row, dict)
    }
    for link in links:
        component = components.get(str(link.get("component_id") or ""))
        if not component:
            continue
        resolved = component.setdefault("resolved_markings", [])
        if isinstance(resolved, list):
            resolved.append(
                {
                    "marking": link.get("marking"),
                    "marking_id": link.get("marking_id"),
                    "confidence": link.get("confidence"),
                    "source_photo_ids": link.get("source_photo_ids") or [],
                }
            )
        component["identity_status"] = "marking_linked_candidate"


def _marking_component_link_score(marking_text: str, marking: Dict[str, Any], component: Dict[str, Any]) -> tuple[float, List[str]]:
    component_text = " ".join(
        str(component.get(key) or "")
        for key in ["label", "kind", "function", "notes", "visible_text"]
    )
    marking_tokens = set(_tokens(marking_text))
    component_tokens = set(_tokens(component_text))
    score = 0.0
    reasons: List[str] = []
    if marking_tokens & component_tokens:
        score += 0.24
        reasons.append("marking/component text overlap")
    marking_caps = set(_capabilities_from_text(marking_text))
    component_caps = set(_capabilities_from_text(component_text))
    if marking_caps & component_caps:
        score += 0.34
        reasons.append(f"capability agreement: {', '.join(sorted(marking_caps & component_caps))}")
    shared_photos = set(_source_photo_ids(marking)) & set(_source_photo_ids(component))
    if shared_photos:
        score += 0.16
        reasons.append(f"same photo observation: {', '.join(sorted(shared_photos)[:3])}")
    if _bbox_iou(_best_normalized_bbox(marking), _best_normalized_bbox(component)) >= 0.12:
        score += 0.26
        reasons.append("overlapping normalized geometry")
    if len([row for row in component.get("source_refs") or [] if isinstance(row, dict)]) == 1 and len(component_tokens) <= 4:
        score += 0.08
        reasons.append("single unresolved nearby component candidate")
    return score, reasons


def _canonical_board_map(
    board_evidence: Dict[str, Any],
    observations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for array_key in ARRAY_KEYS:
        for item in board_evidence.get(array_key) or []:
            if not isinstance(item, dict):
                continue
            geometry = item.get("geometry") if isinstance(item.get("geometry"), dict) else _geometry_consensus(item.get("source_refs") or [])
            source_photo_ids = _dedupe(ref.get("photo_id") for ref in item.get("source_refs") or [] if isinstance(ref, dict))
            items.append(
                {
                    "map_id": f"{array_key}:{item.get('id') or len(items) + 1}",
                    "evidence_type": array_key,
                    "label": item.get("label"),
                    "kind": item.get("kind"),
                    "confidence": item.get("confidence"),
                    "normalized_bbox": geometry.get("normalized_bbox"),
                    "pixel_bbox": geometry.get("pixel_bbox"),
                    "board_zone": _board_zone(geometry.get("normalized_bbox")),
                    "geometry_status": geometry.get("status"),
                    "source_photo_ids": source_photo_ids,
                    "support_count": item.get("support_count", len(source_photo_ids)),
                }
            )
    mapped = [item for item in items if item.get("normalized_bbox")]
    unmapped = [item for item in items if not item.get("normalized_bbox")]
    zone_counts: Dict[str, int] = {}
    for item in mapped:
        zone = str(item.get("board_zone") or "unknown")
        zone_counts[zone] = zone_counts.get(zone, 0) + 1
    return {
        "schema_version": "canonical_board_map.v1",
        "map_type": "evidence_map_not_metric_cad",
        "photo_count": len(observations),
        "item_count": len(items),
        "mapped_item_count": len(mapped),
        "unmapped_item_count": len(unmapped),
        "zone_counts": zone_counts,
        "items": sorted(items, key=lambda row: (str(row.get("evidence_type")), str(row.get("label"))))[:120],
        "layout_confidence": _layout_confidence(items, observations),
        "claim_boundary": "Canonical map is a visual evidence index, not CAD, photogrammetry, netlist, or safe cut geometry.",
    }


def _reconstruction_summary(
    board_evidence: Dict[str, Any],
    observations: Sequence[Dict[str, Any]],
    usable: int,
    canonical_map: Dict[str, Any],
    identity_links: Sequence[Dict[str, Any]],
    capture_coverage: Dict[str, Any],
) -> Dict[str, Any]:
    counts = {key: len(board_evidence.get(key) or []) for key in ARRAY_KEYS}
    evidence_count = sum(counts.values())
    layout_confidence = _safe_float(canonical_map.get("layout_confidence"), 0.0)
    coverage_score = _safe_float(capture_coverage.get("score"), 0.0)
    coverage_complete = bool(capture_coverage.get("required_complete"))
    if coverage_complete and counts["components"] and counts["connectors"] and counts["markings"] and identity_links and layout_confidence >= 0.45:
        level = "multi_view_reconstructed_visual_dossier"
    elif coverage_score >= 0.65 and counts["components"] and counts["connectors"] and counts["markings"]:
        level = "multi_view_grounded_visual_candidate"
    elif usable >= 2 and evidence_count:
        level = "multi_view_visual_candidate"
    elif evidence_count:
        level = "single_view_visual_candidate"
    else:
        level = "insufficient_visual_evidence"
    return {
        "level": level,
        "photo_count": len(observations),
        "usable_photo_count": usable,
        "counts": counts,
        "evidence_item_count": evidence_count,
        "identity_link_count": len(identity_links),
        "layout_confidence": layout_confidence,
        "capture_coverage_score": coverage_score,
        "capture_coverage_complete": coverage_complete,
        "open_capture_lanes": capture_coverage.get("open_required_lanes") or [],
        "mapped_item_count": canonical_map.get("mapped_item_count"),
        "unmapped_item_count": canonical_map.get("unmapped_item_count"),
        "source_policy": "Repeated visual observations raise candidate confidence but do not prove pinout, nets, voltage, or safe reuse.",
    }


def _contradictions(groups: Dict[Tuple[str, str], Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for (_array_key, key), aggregate in groups.items():
        labels = _dedupe(aggregate.get("labels") or [])
        kinds = _dedupe(aggregate.get("kinds") or [])
        if len(kinds) > 1 and len(labels) > 1:
            rows.append(
                {
                    "contradiction_id": f"kind_label_drift_{key}",
                    "severity": "soft",
                    "summary": "Multiple photos support a similar item but disagree on label or kind.",
                    "labels": labels[:8],
                    "kinds": kinds[:8],
                    "source_refs": aggregate.get("source_refs") or [],
                }
            )
    return {
        "status": "soft_gaps" if rows else "clear",
        "items": rows[:12],
    }


def _next_capture_requests(
    board_evidence: Dict[str, Any],
    photo_count: int,
    usable: int,
    canonical_map: Dict[str, Any],
    identity_links: Sequence[Dict[str, Any]],
    capture_coverage: Dict[str, Any],
) -> List[Dict[str, Any]]:
    requests: List[Dict[str, Any]] = []
    for lane in capture_coverage.get("lanes") or []:
        if not isinstance(lane, dict) or lane.get("status") == "complete":
            continue
        if lane.get("request_prompt"):
            requests.append(_capture_request(str(lane.get("lane_id") or "capture_gap"), str(lane["request_prompt"]), str(lane.get("purpose") or "capture_coverage")))
    if photo_count < 2:
        requests.append(_capture_request("more_angles", "Add more board photos from different distances or angles.", "capture"))
    if usable == 0:
        requests.append(_capture_request("usable_board_evidence", "Add at least one parseable board photo or model evidence object.", "capture"))
    if not board_evidence.get("markings"):
        requests.append(_capture_request("marking_closeups", "Capture closeups of readable IC/package markings and printed board labels.", "ocr"))
    if not board_evidence.get("connectors"):
        requests.append(_capture_request("connector_closeups", "Capture connector, pad, header, and terminal areas closely enough to map labels.", "connector_map"))
    if not board_evidence.get("components"):
        requests.append(_capture_request("component_overview", "Capture a wider board view that shows component placement and regions.", "layout"))
    if board_evidence.get("components") and board_evidence.get("markings") and not identity_links:
        requests.append(_capture_request("marking_to_component_context", "Capture a wider photo that includes readable markings and their surrounding component context.", "identity_link"))
    if canonical_map.get("unmapped_item_count"):
        requests.append(_capture_request("layout_reference_photo", "Add an overview photo or annotated crop with normalized boxes for unmapped evidence items.", "layout"))
    weak = [
        item
        for item in canonical_map.get("items") or []
        if isinstance(item, dict) and int(item.get("support_count") or 0) <= 1
    ]
    if len(weak) >= 3:
        requests.append(_capture_request("cross_view_confirmation", "Recapture the main components/connectors from another angle so single-photo claims can be cross-checked.", "confidence"))
    return _dedupe_capture_requests(requests)[:10]


def _capture_coverage(
    observations: Sequence[Dict[str, Any]],
    board_evidence: Dict[str, Any],
    canonical_map: Dict[str, Any],
    identity_links: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    evidence_rows = [extract_board_evidence(row) for row in observations if isinstance(row, dict)]
    evidence_rows = [row for row in evidence_rows if isinstance(row, dict) and row]
    lanes = [
        _coverage_lane(
            "whole_board_context",
            "Whole-board context",
            _has_overview_context(observations, canonical_map),
            _matching_photo_ids(observations, ["overview", "wide", "whole", "full", "front", "top", "angled", "context"]),
            "Capture a whole-board context photo with orientation, connector edges, and major regions visible.",
            0.20,
            "layout",
        ),
        _coverage_lane(
            "connector_detail",
            "Connector and entry-point detail",
            bool(board_evidence.get("connectors")) and (_items_have_source_refs(board_evidence.get("connectors")) or _has_observation_terms(observations, ["connector", "header", "pad", "port", "terminal", "edge"])),
            _item_photo_ids(board_evidence.get("connectors")) or _matching_photo_ids(observations, ["connector", "header", "pad", "port", "terminal", "edge"]),
            "Capture close-ups of every connector, header, pad row, test pad cluster, and cable entry with orientation visible.",
            0.20,
            "connector_map",
        ),
        _coverage_lane(
            "marking_identity_detail",
            "Marking and identity detail",
            bool(board_evidence.get("markings")) and (bool(identity_links) or _has_observation_terms(observations, ["marking", "text", "label", "silkscreen", "ocr", "closeup", "close-up"])),
            _item_photo_ids(board_evidence.get("markings")) or _matching_photo_ids(observations, ["marking", "text", "label", "silkscreen", "ocr", "closeup", "close-up"]),
            "Capture readable close-ups of every IC marking, connector label, regulator marking, crystal, and silkscreen model text.",
            0.18,
            "identity",
        ),
        _coverage_lane(
            "safety_damage_pass",
            "Safety and damage pass",
            _damage_state_declared(evidence_rows) or _has_observation_terms(observations, ["damage", "safety", "corrosion", "burn", "crack", "hot", "battery", "power input"]),
            _matching_photo_ids(observations, ["damage", "safety", "corrosion", "burn", "crack", "hot", "battery", "power input"]),
            "Capture a damage and safety review pass: battery areas, hot spots, corrosion, burns, cracked parts, bodge wires, and power input path.",
            0.16,
            "hazard_review",
        ),
        _coverage_lane(
            "layout_geometry",
            "Layout geometry anchors",
            _safe_float(canonical_map.get("layout_confidence"), 0.0) >= 0.45 and int(canonical_map.get("mapped_item_count") or 0) >= 2,
            _item_photo_ids(board_evidence.get("components")) + _item_photo_ids(board_evidence.get("connectors")),
            "Add an overview photo or annotated crop with normalized boxes for unmapped evidence items.",
            0.16,
            "layout",
        ),
        _coverage_lane(
            "cross_view_confirmation",
            "Cross-view confirmation",
            _cross_view_confirmed(board_evidence) or len(observations) >= 3,
            _cross_view_photo_ids(board_evidence),
            "Recapture the main components/connectors from another angle so single-photo claims can be cross-checked.",
            0.0,
            "confidence",
            required=False,
        ),
    ]
    recommended = _coverage_lane(
        "hidden_side_context",
        "Backside or hidden-area context",
        _has_observation_terms(observations, ["back", "backside", "bottom", "underside", "solder side", "rear", "hidden"]),
        _matching_photo_ids(observations, ["back", "backside", "bottom", "underside", "solder side", "rear", "hidden"]),
        "If accessible, capture the backside, solder side, cable underside, or hidden area so hidden routes and damage are not silently assumed.",
        0.0,
        "hidden_area",
        required=False,
    )
    lanes.append(recommended)
    required = [lane for lane in lanes if lane.get("required")]
    total_weight = sum(float(lane.get("weight") or 0.0) for lane in required)
    score = round(
        sum(float(lane.get("weight") or 0.0) for lane in required if lane.get("status") == "complete")
        / (total_weight if total_weight > 0 else 1.0),
        3,
    )
    open_required = [str(lane["lane_id"]) for lane in required if lane.get("status") != "complete"]
    recommended_open = [str(lane["lane_id"]) for lane in lanes if not lane.get("required") and lane.get("status") != "complete"]
    return {
        "schema_version": "capture_coverage.v1",
        "score": score,
        "required_complete": not open_required,
        "required_lane_count": len(required),
        "complete_required_lane_count": len(required) - len(open_required),
        "open_required_lanes": open_required,
        "recommended_open_lanes": recommended_open,
        "lanes": lanes,
        "claim_boundary": "Capture coverage grades visual observability only; it cannot prove pinout, nets, voltage, or safe reuse.",
    }


def _coverage_lane(
    lane_id: str,
    title: str,
    complete: bool,
    photo_ids: Sequence[Any],
    request_prompt: str,
    weight: float,
    purpose: str,
    *,
    required: bool = True,
) -> Dict[str, Any]:
    return {
        "lane_id": lane_id,
        "title": title,
        "status": "complete" if complete else "open",
        "required": required,
        "weight": weight,
        "purpose": purpose,
        "evidence_photo_ids": _dedupe(photo_ids),
        "request_prompt": "" if complete else request_prompt,
    }


def _capture_request(request_id: str, prompt: str, purpose: str) -> Dict[str, Any]:
    return {
        "request_id": request_id,
        "type": "photo",
        "status": "open",
        "purpose": purpose,
        "prompt": prompt,
    }


def _dedupe_capture_requests(requests: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for request in requests:
        if not isinstance(request, dict):
            continue
        key = str(request.get("request_id") or request.get("prompt") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        kept.append(request)
    return kept


def _has_overview_context(observations: Sequence[Dict[str, Any]], canonical_map: Dict[str, Any]) -> bool:
    return bool(
        _has_observation_terms(observations, ["overview", "wide", "whole", "full", "front", "top", "angled", "context"])
        or (_safe_float(canonical_map.get("layout_confidence"), 0.0) >= 0.45 and int(canonical_map.get("mapped_item_count") or 0) >= 3)
    )


def _has_observation_terms(observations: Sequence[Dict[str, Any]], terms: Sequence[str]) -> bool:
    return bool(_matching_photo_ids(observations, terms))


def _matching_photo_ids(observations: Sequence[Dict[str, Any]], terms: Sequence[str]) -> List[str]:
    matches: List[str] = []
    lower_terms = [str(term).lower() for term in terms]
    for index, observation in enumerate(observations, start=1):
        if not isinstance(observation, dict):
            continue
        text = _observation_text(observation)
        if any(term in text for term in lower_terms):
            matches.append(_photo_id(observation, index))
    return _dedupe(matches)


def _observation_text(observation: Dict[str, Any]) -> str:
    fields = [
        observation.get("photo_id"),
        observation.get("view_id"),
        observation.get("capture_id"),
        observation.get("image_id"),
        observation.get("id"),
        observation.get("label"),
        observation.get("filename"),
        observation.get("view_hint"),
        observation.get("notes"),
        observation.get("purpose"),
        observation.get("capture_role"),
    ]
    evidence = extract_board_evidence(observation)
    if isinstance(evidence, dict):
        fields.extend(
            [
                evidence.get("view"),
                evidence.get("side"),
                evidence.get("photo_type"),
                evidence.get("notes"),
                evidence.get("capture_role"),
            ]
        )
    return " ".join(str(field or "") for field in fields).lower()


def _items_have_source_refs(items: Any) -> bool:
    return any(
        isinstance(item, dict) and any(isinstance(ref, dict) and ref.get("photo_id") for ref in item.get("source_refs") or [])
        for item in (items or [])
    )


def _item_photo_ids(items: Any) -> List[str]:
    return _dedupe(
        ref.get("photo_id")
        for item in (items or [])
        if isinstance(item, dict)
        for ref in item.get("source_refs") or []
        if isinstance(ref, dict) and ref.get("photo_id")
    )


def _damage_state_declared(evidence_rows: Sequence[Dict[str, Any]]) -> bool:
    return any(isinstance(row, dict) and "damage" in row for row in evidence_rows)


def _cross_view_confirmed(board_evidence: Dict[str, Any]) -> bool:
    for key in ARRAY_KEYS:
        for item in board_evidence.get(key) or []:
            if isinstance(item, dict) and int(item.get("support_count") or 0) >= 2:
                return True
    return False


def _cross_view_photo_ids(board_evidence: Dict[str, Any]) -> List[str]:
    ids: List[Any] = []
    for key in ARRAY_KEYS:
        for item in board_evidence.get(key) or []:
            if isinstance(item, dict) and int(item.get("support_count") or 0) >= 2:
                ids.extend(_item_photo_ids([item]))
    return _dedupe(ids)


def _pixel_bbox_frames(groups: Dict[Tuple[str, str], Dict[str, Any]]) -> Dict[str, List[float]]:
    frames: Dict[str, List[float]] = {}
    for aggregate in groups.values():
        for ref in aggregate.get("source_refs") or []:
            if not isinstance(ref, dict):
                continue
            photo_id = str(ref.get("photo_id") or "")
            if not photo_id:
                continue
            _norm, pixel = _bbox_variants(ref.get("bbox"))
            if not pixel:
                continue
            x_max, y_max = frames.get(photo_id, [0.0, 0.0])
            frames[photo_id] = [max(x_max, pixel[2]), max(y_max, pixel[3])]
    return {
        photo_id: [max(frame[0], 1.0), max(frame[1], 1.0)]
        for photo_id, frame in frames.items()
        if frame[0] > 1.0 and frame[1] > 1.0
    }


def _geometry_consensus(source_refs: Sequence[Dict[str, Any]], *, pixel_frames: Dict[str, List[float]] | None = None) -> Dict[str, Any]:
    normalized: List[List[float]] = []
    pixels: List[List[float]] = []
    inferred_normalized = 0
    frames = pixel_frames or {}
    for ref in source_refs:
        if not isinstance(ref, dict):
            continue
        bbox = ref.get("bbox")
        norm, pixel = _bbox_variants(bbox)
        if norm:
            normalized.append(norm)
        if pixel:
            pixels.append(pixel)
            frame = frames.get(str(ref.get("photo_id") or ""))
            inferred = _normalize_pixel_bbox(pixel, frame)
            if inferred:
                normalized.append(inferred)
                inferred_normalized += 1
    if normalized:
        consensus = [
            round(sum(row[index] for row in normalized) / len(normalized), 4)
            for index in range(4)
        ]
        status = "normalized_consensus" if len(normalized) > 1 else "normalized_single_observation"
        if inferred_normalized and inferred_normalized == len(normalized):
            status = "provider_pixel_normalized_consensus" if len(normalized) > 1 else "provider_pixel_normalized_single"
        return {
            "status": status,
            "normalized_bbox": consensus,
            "pixel_bbox": pixels[0] if pixels else None,
            "geometry_support_count": len(normalized),
            "provider_pixel_normalized_count": inferred_normalized,
        }
    if pixels:
        return {
            "status": "pixel_only",
            "normalized_bbox": None,
            "pixel_bbox": pixels[0],
            "geometry_support_count": len(pixels),
        }
    return {
        "status": "unmapped",
        "normalized_bbox": None,
        "pixel_bbox": None,
        "geometry_support_count": 0,
    }


def _bbox_variants(value: Any) -> tuple[List[float] | None, List[float] | None]:
    if not isinstance(value, list) or len(value) != 4:
        return None, None
    try:
        raw = [float(item) for item in value]
    except (TypeError, ValueError):
        return None, None
    if max(raw) <= 1.0 and min(raw) >= 0.0:
        x1, y1, x2, y2 = raw
        if x2 <= x1 or y2 <= y1:
            x2 = min(1.0, x1 + max(0.0, raw[2]))
            y2 = min(1.0, y1 + max(0.0, raw[3]))
        return [round(x1, 4), round(y1, 4), round(x2, 4), round(y2, 4)], None
    return None, [round(item, 2) for item in raw]


def _normalize_pixel_bbox(pixel: Sequence[float], frame: Sequence[float] | None) -> List[float] | None:
    if not frame or len(frame) != 2:
        return None
    try:
        width = float(frame[0])
        height = float(frame[1])
        x1, y1, x2, y2 = [float(value) for value in pixel]
    except (TypeError, ValueError):
        return None
    if width <= 1.0 or height <= 1.0 or x2 <= x1 or y2 <= y1:
        return None
    norm = [
        max(0.0, min(1.0, x1 / width)),
        max(0.0, min(1.0, y1 / height)),
        max(0.0, min(1.0, x2 / width)),
        max(0.0, min(1.0, y2 / height)),
    ]
    if norm[2] <= norm[0] or norm[3] <= norm[1]:
        return None
    return [round(value, 4) for value in norm]


def _bbox_role(value: Any) -> str:
    norm, pixel = _bbox_variants(value)
    if norm:
        return "normalized"
    if pixel:
        return "pixel"
    return "missing"


def _best_normalized_bbox(item: Dict[str, Any]) -> List[float] | None:
    geometry = item.get("geometry") if isinstance(item.get("geometry"), dict) else {}
    bbox = geometry.get("normalized_bbox")
    if isinstance(bbox, list) and len(bbox) == 4:
        return [float(value) for value in bbox]
    for ref in item.get("source_refs") or []:
        if not isinstance(ref, dict):
            continue
        norm, _pixel = _bbox_variants(ref.get("bbox"))
        if norm:
            return norm
    return None


def _bbox_iou(a: Sequence[float] | None, b: Sequence[float] | None) -> float:
    if not a or not b or len(a) != 4 or len(b) != 4:
        return 0.0
    ax1, ay1, ax2, ay2 = [float(value) for value in a]
    bx1, by1, bx2, by2 = [float(value) for value in b]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return 0.0 if union <= 0 else inter / union


def _board_zone(bbox: Any) -> str:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return "unmapped"
    x1, y1, x2, y2 = [float(value) for value in bbox]
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    vertical = "top" if cy < 0.33 else "bottom" if cy > 0.67 else "middle"
    horizontal = "left" if cx < 0.33 else "right" if cx > 0.67 else "center"
    return f"{vertical}_{horizontal}" if vertical != "middle" or horizontal != "center" else "center"


def _layout_confidence(items: Sequence[Dict[str, Any]], observations: Sequence[Dict[str, Any]]) -> float:
    if not items:
        return 0.0
    mapped = len([item for item in items if item.get("normalized_bbox")])
    multi_supported = len([item for item in items if len(item.get("source_photo_ids") or []) >= 2])
    type_count = len({str(item.get("evidence_type") or "") for item in items})
    return round(
        min(
            1.0,
            0.10
            + 0.42 * (mapped / max(len(items), 1))
            + 0.16 * min(len(observations), 4) / 4
            + 0.18 * min(type_count, 4) / 4
            + 0.14 * (multi_supported / max(len(items), 1)),
        ),
        3,
    )


def _capabilities_from_text(text: Any) -> List[str]:
    lower = str(text or "").lower()
    mapping = [
        (("ch340", "cp210", "ft232", "uart", "usb bridge", "usb serial"), "usb_serial"),
        (("usb", "header", "connector", "port", "gpio", "jst"), "connector"),
        (("regulator", "buck", "boost", "ldo", "ams1117", "5v", "3.3v", "power"), "power"),
        (("esp32", "stm32", "rp2040", "atmega", "mcu", "processor", "cpu", "controller"), "controller"),
        (("bme", "bmp", "sht", "sensor", "adc", "i2c", "spi"), "sensor_or_adc"),
        (("ethernet", "rs485", "canh", "canl", "max485"), "network_interface"),
        (("hdmi", "display", "oled", "lcd"), "display_or_ui"),
    ]
    return _dedupe(cap for terms, cap in mapping if any(term in lower for term in terms))


def _source_photo_ids(item: Dict[str, Any]) -> List[str]:
    return _dedupe(ref.get("photo_id") for ref in item.get("source_refs") or [] if isinstance(ref, dict))


def _tokens(value: Any) -> List[str]:
    tokens: List[str] = []
    current: List[str] = []
    for char in str(value or "").lower():
        if char.isalnum():
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _item_key(array_key: str, item: Dict[str, Any]) -> str:
    text = " ".join(
        str(item.get(key) or "")
        for key in ["marking", "visible_text", "label", "name", "kind", "type", "function"]
    )
    compact = _compact(text)
    if compact:
        return compact[:80]
    return _safe_id(f"{array_key}_{item.get('id') or len(str(item))}")


def _compact(value: Any) -> str:
    text = str(value or "").lower()
    kept = []
    for char in text:
        if char.isalnum():
            kept.append(char)
        elif kept and kept[-1] != "_":
            kept.append("_")
    return "".join(kept).strip("_")


def _safe_id(value: Any) -> str:
    return _compact(value)[:90] or "photo"


def _string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dedupe(items: Iterable[Any]) -> List[str]:
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


def _dedupe_source_refs(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = (row.get("photo_id"), row.get("item_id"), row.get("label"))
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept[:16]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
