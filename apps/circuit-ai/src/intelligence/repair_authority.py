"""Derive repair authority from arbitrary-board evidence.

This module turns visual evidence, measured topology, measurements, hazards,
and outcomes into the repair_authority/evidence_trust records used elsewhere in
the backend. Operator-supplied authority is preserved unless measured evidence
contains a hard safety blocker.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Sequence


SCHEMA_VERSION = "arbitrary_board_repair_authority.v1"

REQUIRED_LOW_RISK_CATEGORIES = {"resistance", "continuity", "voltage", "current", "thermal"}
TRUST_KEYS = ("instrument_id", "instrument_type", "calibration_status", "recorded_at", "operator_id")
TRUSTED_CALIBRATION = {"valid", "verified", "current", "not_required", "not required", "factory_current"}
PASS_STATUSES = {"closed", "pass", "passed", "ok", "verified", "resolved", "normal"}
FAIL_STATUSES = {"failed", "fail", "unsafe", "blocked", "safety_hold"}


def enrich_payload_with_repair_authority(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach derived authority records and enforce hard evidence blockers."""

    body = dict(payload or {})
    had_analysis = isinstance(body.get("analysis"), dict)
    analysis = dict(body.get("analysis") if had_analysis else {})
    supplied_authority = _first_dict(
        analysis.get("repair_authority"),
        body.get("repair_authority"),
    )
    supplied_trust = _first_dict(
        analysis.get("evidence_trust"),
        body.get("evidence_trust"),
    )

    derived = derive_repair_authority(body, analysis=analysis)
    if supplied_authority:
        if derived.get("available"):
            analysis["arbitrary_board_authority"] = derived
            integrity = _authority_integrity(supplied_authority, derived)
            analysis["authority_integrity"] = integrity
            if integrity.get("overrode_supplied_authority"):
                effective = _blocked_effective_authority(supplied_authority, derived["repair_authority"], integrity)
                trust = _blocked_effective_trust(supplied_trust, derived["evidence_trust"], integrity)
                analysis["operator_repair_authority"] = supplied_authority
                analysis["repair_authority"] = effective
                analysis["evidence_trust"] = trust
                body["repair_authority"] = effective
                body["evidence_trust"] = trust
            else:
                analysis["repair_authority"] = supplied_authority
                if supplied_trust:
                    analysis["evidence_trust"] = supplied_trust
                body.setdefault("repair_authority", supplied_authority)
                if supplied_trust:
                    body.setdefault("evidence_trust", supplied_trust)
        else:
            analysis["repair_authority"] = supplied_authority
            if supplied_trust:
                analysis["evidence_trust"] = supplied_trust
            body.setdefault("repair_authority", supplied_authority)
            if supplied_trust:
                body.setdefault("evidence_trust", supplied_trust)
        body["analysis"] = analysis
        return body

    if not derived.get("available"):
        if had_analysis:
            body["analysis"] = analysis
        return body

    analysis["repair_authority"] = derived["repair_authority"]
    if not isinstance(analysis.get("evidence_trust"), dict) or not analysis.get("evidence_trust"):
        analysis["evidence_trust"] = derived["evidence_trust"]
    analysis["arbitrary_board_authority"] = derived
    body["analysis"] = analysis
    body.setdefault("repair_authority", derived["repair_authority"])
    body.setdefault("evidence_trust", derived["evidence_trust"])
    return body


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _authority_integrity(supplied_authority: Dict[str, Any], derived: Dict[str, Any]) -> Dict[str, Any]:
    derived_authority = derived.get("repair_authority") if isinstance(derived.get("repair_authority"), dict) else {}
    derived_trust = derived.get("evidence_trust") if isinstance(derived.get("evidence_trust"), dict) else {}
    supplied_status = str(supplied_authority.get("status") or "unknown")
    derived_status = str(derived_authority.get("status") or "unknown")
    hard_blockers = []
    for lane in derived_authority.get("authority_lanes") or []:
        if not isinstance(lane, dict) or str(lane.get("status") or "") != "fail":
            continue
        hard_blockers.append(f"{lane.get('label')}: {lane.get('reason')}")
    hard_blocked = derived_status == "blocked" or bool(hard_blockers)
    supplied_release_like = supplied_status in {
        "authoritative_low_risk",
        "certified_release",
        "authorized",
        "authority_ready",
        "measurement_backed",
    }
    override = bool(hard_blocked and supplied_release_like)
    status_conflict = supplied_release_like and derived_status not in {"authoritative_low_risk", "unknown"}
    return {
        "schema_version": "authority_integrity.v1",
        "source": "derived_evidence_consistency_check",
        "supplied_authority_status": supplied_status,
        "derived_evidence_status": derived_status,
        "overrode_supplied_authority": override,
        "conflict_detected": override or (hard_blocked and supplied_status not in {"blocked", "safety_hold"}),
        "advisory_mismatch": status_conflict,
        "hard_blocked_by_evidence": hard_blocked,
        "hard_blockers": _dedupe(hard_blockers)[:10],
        "derived_blockers": _dedupe(
            [*(derived_trust.get("blockers") or []), *(derived_authority.get("blocked_decisions") or [])]
        )[:10],
        "policy": {
            "manual_or_llm_authority_cannot_clear_failed_measurements": True,
            "measured_hazards_dominate_supplied_authority": True,
            "operator_authority_preserved_when_no_hard_blocker": True,
        },
    }


def _blocked_effective_authority(
    supplied_authority: Dict[str, Any],
    derived_authority: Dict[str, Any],
    integrity: Dict[str, Any],
) -> Dict[str, Any]:
    effective = dict(derived_authority)
    effective["source"] = "evidence_safety_override"
    effective["status"] = "blocked"
    effective["score"] = min(_safe_float(derived_authority.get("score"), 0.08), 0.24)
    effective["safety_level"] = "blocked"
    effective["summary"] = (
        "Supplied repair authority was overridden because measured evidence contains hard blockers. "
        + str(derived_authority.get("summary") or "")
    ).strip()
    effective["supplied_authority_status"] = supplied_authority.get("status")
    effective["blocked_decisions"] = _dedupe(
        [
            *(derived_authority.get("blocked_decisions") or []),
            *(supplied_authority.get("blocked_decisions") or []),
            "supplied authority cannot override failed measurements or hazardous evidence",
        ]
    )[:12]
    effective["required_measurements"] = _dedupe(
        [
            *(derived_authority.get("required_measurements") or []),
            "Resolve authority conflict by clearing the measured hard blockers.",
        ]
    )[:12]
    effective["authority_integrity"] = integrity
    effective["claim_boundary"] = (
        "Authority is blocked by measured evidence; operator or LLM authority packets are preserved only as audit input."
    )
    return effective


def _blocked_effective_trust(
    supplied_trust: Dict[str, Any],
    derived_trust: Dict[str, Any],
    integrity: Dict[str, Any],
) -> Dict[str, Any]:
    trust = dict(derived_trust)
    trust["source"] = "evidence_safety_override"
    trust["level"] = "blocked"
    trust["score"] = min(_safe_float(derived_trust.get("score"), 0.08), 0.24)
    trust["launch_readiness"] = "blocked_safety_hold"
    trust["blockers"] = _dedupe(
        [
            *(derived_trust.get("blockers") or []),
            *(supplied_trust.get("blockers") or []),
            "Supplied repair authority conflicts with measured hard blockers.",
        ]
    )[:12]
    trust["authority_integrity"] = integrity
    return trust


def derive_repair_authority(payload: Dict[str, Any], *, analysis: Dict[str, Any] | None = None) -> Dict[str, Any]:
    analysis = analysis if isinstance(analysis, dict) else {}
    measurements = _measurement_rows(payload, analysis)
    measurement_summary = _measurement_summary(measurements)
    hazard_profile = _hazard_profile(payload, analysis)
    topology = analysis.get("topology_authority") if isinstance(analysis.get("topology_authority"), dict) else {}
    bridge = analysis.get("topology_evidence_bridge") if isinstance(analysis.get("topology_evidence_bridge"), dict) else {}
    visual_bridge = analysis.get("vision_evidence_bridge") if isinstance(analysis.get("vision_evidence_bridge"), dict) else {}
    has_visual = bool(
        analysis.get("board_evidence")
        or analysis.get("detections")
        or visual_bridge.get("available")
        or payload.get("board_evidence")
    )
    has_topology = bool(topology.get("measurement_backed") or bridge.get("available") or payload.get("topology_evidence"))
    has_any_evidence = has_visual or has_topology or bool(measurements) or bool(hazard_profile.get("hazards"))
    if not has_any_evidence:
        return {"schema_version": SCHEMA_VERSION, "available": False}

    failed = measurement_summary["failed_count"] > 0
    unsupported_hazard = bool(hazard_profile.get("unsupported_for_production_authority"))
    topology_short = bool(topology.get("shorts_detected"))
    passed_categories = set(measurement_summary["passed_categories"])
    trusted_categories = set(measurement_summary["trusted_categories"])
    missing_categories = sorted(REQUIRED_LOW_RISK_CATEGORIES - passed_categories)
    missing_trusted = sorted(REQUIRED_LOW_RISK_CATEGORIES - trusted_categories)
    pinout_known = bool(topology.get("pinout_known"))
    trusted_measurement_count = int(measurement_summary["trusted_count"])
    interface_summary = _interface_summary(payload, analysis)
    outcome_summary = _outcome_summary(payload, analysis)

    if failed or unsupported_hazard or topology_short:
        status = "blocked"
    elif pinout_known and not missing_categories and not missing_trusted and trusted_measurement_count >= 5:
        status = "authoritative_low_risk"
    elif has_topology and passed_categories:
        status = "measurement_backed"
    elif has_topology or measurements:
        status = "needs_measurements"
    elif has_visual:
        status = "visual_only"
    else:
        status = "needs_measurements"

    required_measurements = _required_measurements(status, missing_categories, missing_trusted, has_topology, has_visual)
    blocked_decisions = []
    if status != "authoritative_low_risk":
        blocked_decisions.append("production repair release")
    if status in {"visual_only", "needs_measurements", "blocked"}:
        blocked_decisions.append("first power or physical splice")
    if unsupported_hazard or topology_short or failed:
        blocked_decisions.append("reuse of hazardous or failed-evidence section")

    score = _authority_score(
        status=status,
        has_visual=has_visual,
        has_topology=has_topology,
        passed_categories=passed_categories,
        trusted_categories=trusted_categories,
        failed=failed,
        unsupported_hazard=unsupported_hazard,
        pinout_known=pinout_known,
    )
    lanes = _authority_lanes(
        status=status,
        measurement_summary=measurement_summary,
        topology=topology,
        hazard_profile=hazard_profile,
        interface_summary=interface_summary,
        outcome_summary=outcome_summary,
        failed=failed,
        unsupported_hazard=unsupported_hazard,
        topology_short=topology_short,
        pinout_known=pinout_known,
        has_topology=has_topology,
        has_visual=has_visual,
    )
    unlock_plan = _authority_unlock_plan(lanes, required_measurements)
    gates = _authority_gates(status, missing_categories, missing_trusted, measurement_summary, topology, hazard_profile)
    authority = {
        "schema_version": "repair_authority.v1",
        "source": "derived_from_arbitrary_board_evidence",
        "status": status,
        "score": score,
        "safety_level": "blocked" if status == "blocked" else "low_risk_scope" if status == "authoritative_low_risk" else "caution",
        "summary": _summary(status, has_visual, has_topology, measurement_summary, hazard_profile),
        "supported_decisions": _supported_decisions(status),
        "blocked_decisions": _dedupe(blocked_decisions),
        "required_measurements": required_measurements,
        "measurement_summary": measurement_summary,
        "topology_summary": {
            "pinout_known": pinout_known,
            "measurement_backed": bool(topology.get("measurement_backed") or has_topology),
            "shorts_detected": topology_short,
            "trusted_measurement_count": topology.get("trusted_measurement_count", trusted_measurement_count),
        },
        "interface_summary": interface_summary,
        "outcome_summary": outcome_summary,
        "authority_lanes": lanes,
        "authority_state": _authority_state(status, lanes),
        "unlock_plan": unlock_plan,
        "hazard_summary": hazard_profile,
        "gates": gates,
        "claim_boundary": _claim_boundary(status),
    }
    trust = {
        "schema_version": "evidence_trust.v1",
        "source": "derived_from_arbitrary_board_evidence",
        "score": score,
        "level": _trust_level(score, status),
        "launch_readiness": _launch_readiness(status),
        "blockers": _trust_blockers(status, missing_categories, missing_trusted, hazard_profile, topology_short, failed),
        "required_evidence": required_measurements,
        "authority_lanes": lanes,
        "unlock_plan": unlock_plan,
        "gates": gates,
        "policy": {
            "vision_can_propose": True,
            "measurements_and_topology_determine_authority": True,
            "hazards_cannot_be_cleared_by_llm_text": True,
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "available": True,
        "repair_authority": authority,
        "evidence_trust": trust,
    }


def _measurement_rows(payload: Dict[str, Any], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for root_name, root in [("payload", payload), ("analysis", analysis)]:
        if not isinstance(root, dict):
            continue
        for key in ["measurements", "measurement_history", "bench_measurements", "evidence_measurements"]:
            _extend_measurements(rows, root.get(key), f"{root_name}.{key}")
        evidence = root.get("evidence") if isinstance(root.get("evidence"), dict) else {}
        _extend_measurements(rows, evidence.get("measurements"), f"{root_name}.evidence.measurements")
    return [_normalize_measurement(row, index) for index, row in enumerate(rows)]


def _extend_measurements(rows: List[Dict[str, Any]], value: Any, source: str) -> None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("source", source)
                rows.append(row)
    elif isinstance(value, dict):
        if isinstance(value.get("measurements"), list):
            _extend_measurements(rows, value.get("measurements"), source)
        elif any(key in value for key in ["type", "measurement_type", "target", "value", "status", "notes"]):
            row = dict(value)
            row.setdefault("source", source)
            rows.append(row)


def _normalize_measurement(row: Dict[str, Any], index: int) -> Dict[str, Any]:
    measurement_type = str(row.get("type") or row.get("measurement_type") or row.get("kind") or "measurement")
    target = str(row.get("target") or row.get("net") or row.get("pin") or row.get("node") or "")
    value = row.get("value", row.get("result", row.get("reading")))
    unit = str(row.get("unit") or row.get("units") or "")
    notes = str(row.get("notes") or row.get("summary") or row.get("reason") or "")
    text = " ".join([measurement_type, target, str(value or ""), unit, notes]).lower()
    failed = _failed(row, text)
    passed = False if failed else _passed(row, text)
    categories = _categories(text, unit)
    trusted = passed and all(str(row.get(key) or "").strip() for key in TRUST_KEYS) and str(row.get("calibration_status") or "").strip().lower() in TRUSTED_CALIBRATION
    return {
        "measurement_id": str(row.get("measurement_id") or row.get("id") or f"measurement_{index + 1}"),
        "type": measurement_type,
        "target": target,
        "value": value,
        "unit": unit,
        "notes": notes,
        "passed": passed,
        "failed": failed,
        "categories": sorted(categories),
        "trusted": trusted,
        "instrument_id": row.get("instrument_id"),
        "instrument_type": row.get("instrument_type"),
        "calibration_status": row.get("calibration_status"),
        "recorded_at": row.get("recorded_at"),
        "operator_id": row.get("operator_id"),
        "evidence_uri": row.get("evidence_uri"),
        "text": text,
    }


def _measurement_summary(measurements: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    passed = [row for row in measurements if row.get("passed") and not row.get("failed")]
    trusted = [row for row in passed if row.get("trusted")]
    failed = [row for row in measurements if row.get("failed")]
    lane_categories = sorted(REQUIRED_LOW_RISK_CATEGORIES | {"logic", "load"})
    return {
        "count": len(measurements),
        "passed_count": len(passed),
        "failed_count": len(failed),
        "trusted_count": len(trusted),
        "passed_categories": sorted({cat for row in passed for cat in row.get("categories") or []}),
        "trusted_categories": sorted({cat for row in trusted for cat in row.get("categories") or []}),
        "failed_categories": sorted({cat for row in failed for cat in row.get("categories") or []}),
        "failed_measurement_ids": [row.get("measurement_id") for row in failed],
        "category_coverage": {
            category: {
                "count": len([row for row in measurements if category in (row.get("categories") or [])]),
                "passed_count": len([row for row in passed if category in (row.get("categories") or [])]),
                "trusted_count": len([row for row in trusted if category in (row.get("categories") or [])]),
                "failed_count": len([row for row in failed if category in (row.get("categories") or [])]),
            }
            for category in lane_categories
        },
        "quality": "trusted_bench_recorded" if trusted else "bench_recorded" if passed else "none",
    }


def _hazard_profile(payload: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    hazards: List[Dict[str, Any]] = []
    requirements: List[str] = []
    energy_domain = "unknown"
    for root in [payload, analysis]:
        profile = root.get("hazard_profile") if isinstance(root, dict) and isinstance(root.get("hazard_profile"), dict) else {}
        if not profile:
            continue
        energy_domain = str(profile.get("energy_domain") or energy_domain)
        for hazard in profile.get("hazards") or []:
            if isinstance(hazard, dict):
                hazards.append(hazard)
                req = hazard.get("clearance_requires") or hazard.get("requires")
                if isinstance(req, list):
                    requirements.extend(str(item) for item in req)
                elif req:
                    requirements.append(str(req))
        requirements.extend(str(item) for item in profile.get("clearance_requirements") or [])
    unsupported = any(
        bool(hazard.get("unsupported_for_production_authority"))
        or str(hazard.get("severity") or "").lower() in {"critical", "hard_stop", "unsupported"}
        for hazard in hazards
    )
    return {
        "energy_domain": energy_domain,
        "hazard_count": len(hazards),
        "unsupported_for_production_authority": unsupported,
        "hazards": hazards,
        "clearance_requirements": _dedupe(requirements)[:12],
    }


def _interface_summary(payload: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    types: List[str] = []
    capabilities: List[str] = []
    bridge = analysis.get("topology_evidence_bridge") if isinstance(analysis.get("topology_evidence_bridge"), dict) else {}
    machine = analysis.get("machine_connection_map") if isinstance(analysis.get("machine_connection_map"), dict) else {}
    for root in [bridge, machine]:
        for row in root.get("interfaces") or []:
            if isinstance(row, dict):
                types.append(str(row.get("type") or ""))
    for root in [payload, analysis]:
        for capability in root.get("required_capabilities") or []:
            capabilities.append(str(capability))
        for resource in root.get("available_resources") or []:
            if isinstance(resource, dict):
                capabilities.extend(str(item) for item in resource.get("capabilities") or [])
    capability_types = _interface_types_from_capabilities(capabilities)
    all_types = _dedupe(types + capability_types)
    logic_types = {"uart_serial", "usb2", "usb_serial", "i2c", "sensor_or_adc", "logic"}
    load_types = {"actuator_or_load_output", "actuator_driver", "motor_or_load", "load", "motor"}
    return {
        "types": all_types,
        "capabilities": _dedupe(capabilities),
        "logic_interface_required": any(item in logic_types for item in all_types),
        "load_path_required": any(item in load_types for item in all_types),
        "power_required": any(item in {"power", "usb_power", "power_input"} for item in [*all_types, *capabilities]),
    }


def _interface_types_from_capabilities(capabilities: Sequence[str]) -> List[str]:
    rows = []
    for capability in capabilities:
        raw = str(capability or "").strip().lower()
        if raw in {"usb_serial", "serial", "uart"}:
            rows.append("usb_serial")
        elif raw in {"sensor_or_adc", "i2c", "spi"}:
            rows.append("sensor_or_adc")
        elif raw in {"actuator_driver", "motor_or_load", "motor", "load"}:
            rows.append("motor_or_load")
        elif raw in {"power", "usb_power", "power_input"}:
            rows.append("power")
        elif raw:
            rows.append(raw)
    return rows


def _outcome_summary(payload: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    outcomes: List[Dict[str, Any]] = []
    for root in [payload, analysis]:
        if not isinstance(root, dict):
            continue
        for key in ["outcome_history", "past_outcomes", "prior_outcomes", "outcomes"]:
            value = root.get(key)
            if isinstance(value, list):
                outcomes.extend(item for item in value if isinstance(item, dict))
            elif isinstance(value, dict):
                outcomes.append(value)
        if isinstance(root.get("outcome"), dict):
            outcomes.append(root["outcome"])
    latest = outcomes[-1] if outcomes else {}
    output_verified = _truthy(latest.get("output_function_verified"))
    first_power_passed = _positive(latest.get("first_power_result")) or _positive(latest.get("power_result"))
    thermal_passed = _positive(latest.get("thermal_result")) or _positive(latest.get("thermal_behavior"))
    terminal_success = output_verified and first_power_passed and thermal_passed
    return {
        "available": bool(latest),
        "outcome_count": len(outcomes),
        "decision": latest.get("decision"),
        "output_function_verified": output_verified,
        "first_power_passed": first_power_passed,
        "thermal_passed": thermal_passed,
        "terminal_success": terminal_success,
        "missing_for_release": _dedupe(
            [
                "Record output_function_verified=true." if not output_verified else "",
                "Record first_power_result=pass under current limit." if not first_power_passed else "",
                "Record thermal_result=normal or equivalent." if not thermal_passed else "",
            ]
        ),
    }


def _authority_lanes(
    *,
    status: str,
    measurement_summary: Dict[str, Any],
    topology: Dict[str, Any],
    hazard_profile: Dict[str, Any],
    interface_summary: Dict[str, Any],
    outcome_summary: Dict[str, Any],
    failed: bool,
    unsupported_hazard: bool,
    topology_short: bool,
    pinout_known: bool,
    has_topology: bool,
    has_visual: bool,
) -> List[Dict[str, Any]]:
    passed = set(measurement_summary.get("passed_categories") or [])
    trusted = set(measurement_summary.get("trusted_categories") or [])
    failed_categories = set(measurement_summary.get("failed_categories") or [])
    lanes = [
        _lane(
            "hazard_scope",
            "Hazard scope",
            "fail" if failed or unsupported_hazard or topology_short else "pass",
            "repair_power_release",
            "Resolve failed measurements, shorts, high-energy sections, or unsupported hazards.",
            (
                "Failed measurement, short, or unsupported hazard evidence is attached."
                if failed or unsupported_hazard or topology_short
                else "No failed or unsupported hazard evidence is attached."
            ),
            failed_measurement_count=measurement_summary.get("failed_count"),
            hazard_count=hazard_profile.get("hazard_count"),
        ),
        _lane(
            "measured_pinout",
            "Measured pinout",
            "pass" if pinout_known else "warn",
            "repair_power_release",
            "Attach measured connector pinout/topology evidence with no unknown pins.",
            "Measured pinout is complete.",
            pinout_known=pinout_known,
            has_topology=has_topology,
            has_visual=has_visual,
        ),
        _measurement_lane("no_short", "No-short resistance", "resistance", passed, trusted, failed_categories),
        _measurement_lane("reference_continuity", "Reference continuity", "continuity", passed, trusted, failed_categories),
        _measurement_lane("voltage_domain", "Voltage and polarity", "voltage", passed, trusted, failed_categories),
        _measurement_lane("current_limit", "Current-limited power", "current", passed, trusted, failed_categories),
        _measurement_lane("thermal_behavior", "Thermal behavior", "thermal", passed, trusted, failed_categories),
    ]
    if interface_summary.get("logic_interface_required"):
        lanes.append(_measurement_lane("logic_interface", "Logic interface compatibility", "logic", passed, trusted, failed_categories))
    else:
        lanes.append(
            _lane(
                "logic_interface",
                "Logic interface compatibility",
                "not_applicable",
                "splice_release",
                "Add logic-level or bus evidence when a signal interface is present.",
                "No signal interface is required by the current evidence.",
            )
        )
    if interface_summary.get("load_path_required"):
        load_status = "pass" if {"current", "thermal"} <= trusted else "warn"
        lanes.append(
            _lane(
                "load_path",
                "Load or actuator path",
                load_status,
                "splice_release",
                "Record protected dummy-load or real-load current and thermal behavior.",
                "Load path has current and thermal evidence.",
            )
        )
    else:
        lanes.append(
            _lane(
                "load_path",
                "Load or actuator path",
                "not_applicable",
                "splice_release",
                "Add load-path evidence when a driver, motor, heater, or actuator is present.",
                "No load path is required by the current evidence.",
            )
        )
    lanes.append(
        _lane(
            "terminal_outcome",
            "Terminal outcome",
            "pass" if outcome_summary.get("terminal_success") else "warn",
            "production_release",
            "Record successful first power, thermal behavior, and output_function_verified=true.",
            "Terminal successful outcome is recorded.",
            outcome_count=outcome_summary.get("outcome_count"),
        )
    )
    if status == "blocked":
        for lane in lanes:
            if lane["lane_id"] in {"hazard_scope", "no_short"} and lane["status"] == "warn":
                lane["status"] = "fail"
                lane["reason"] = "Blocked authority requires resolving failed or hazardous electrical evidence."
    return lanes


def _measurement_lane(
    lane_id: str,
    label: str,
    category: str,
    passed: set[str],
    trusted: set[str],
    failed: set[str],
) -> Dict[str, Any]:
    if category in failed:
        status = "fail"
        reason = f"Failed {category} evidence is present."
    elif category in trusted:
        status = "pass"
        reason = f"Trusted {category} evidence is present."
    elif category in passed:
        status = "warn"
        reason = f"{category.capitalize()} evidence passes but lacks complete trusted provenance."
    else:
        status = "warn"
        reason = f"Missing passing {category} evidence."
    return _lane(
        lane_id,
        label,
        status,
        "repair_power_release",
        f"Record passing trusted {category} evidence.",
        reason,
        evidence_category=category,
        passed=category in passed,
        trusted=category in trusted,
    )


def _lane(
    lane_id: str,
    label: str,
    status: str,
    scope: str,
    requirement: str,
    reason: str,
    **extra: Any,
) -> Dict[str, Any]:
    return {
        "lane_id": lane_id,
        "label": label,
        "status": status,
        "scope": scope,
        "requirement": requirement,
        "reason": reason,
        **{key: value for key, value in extra.items() if value not in {None, ""}},
    }


def _authority_unlock_plan(lanes: Sequence[Dict[str, Any]], required_measurements: Sequence[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    priority = 1
    for lane in lanes:
        if lane.get("status") not in {"fail", "warn"}:
            continue
        rows.append(
            {
                "step_id": f"unlock_{lane.get('lane_id')}",
                "priority": priority,
                "lane_id": lane.get("lane_id"),
                "action": lane.get("requirement"),
                "unlocks": lane.get("scope"),
                "reason": lane.get("reason"),
            }
        )
        priority += 1
    for item in required_measurements:
        if any(str(item).lower() == str(row.get("action")).lower() for row in rows):
            continue
        rows.append(
            {
                "step_id": f"unlock_required_{priority}",
                "priority": priority,
                "lane_id": "required_measurement",
                "action": str(item),
                "unlocks": "repair_power_release",
                "reason": "Required by the current repair authority status.",
            }
        )
        priority += 1
    return rows[:12]


def _authority_state(status: str, lanes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    lane_map = {str(lane.get("lane_id")): str(lane.get("status")) for lane in lanes}
    terminal_ready = lane_map.get("terminal_outcome") == "pass"
    if status == "blocked":
        power = "blocked"
        release = "blocked"
    elif status == "authoritative_low_risk":
        power = "allowed_in_measured_low_risk_scope"
        release = "candidate_ready" if terminal_ready else "terminal_outcome_required"
    elif status == "measurement_backed":
        power = "gated_by_remaining_measurements"
        release = "not_ready"
    else:
        power = "blocked_until_topology_and_measurements"
        release = "not_ready"
    return {
        "power_or_splice": power,
        "production_release": release,
        "status": status,
        "lane_statuses": lane_map,
    }


def _required_measurements(
    status: str,
    missing_categories: Sequence[str],
    missing_trusted: Sequence[str],
    has_topology: bool,
    has_visual: bool,
) -> List[str]:
    prompts = []
    category_prompts = {
        "resistance": "Record passing unpowered resistance/no-short evidence between power and ground.",
        "continuity": "Record passing ground/reference continuity and connector continuity evidence.",
        "voltage": "Record passing voltage, polarity, and logic-level evidence under current limit.",
        "current": "Record passing current draw/current-limit evidence during first power.",
        "thermal": "Record passing thermal behavior after first power and output-function test.",
    }
    for category in missing_categories:
        prompts.append(category_prompts.get(category, f"Record passing {category} evidence."))
    for category in missing_trusted:
        if category not in missing_categories:
            prompts.append(f"Attach trusted provenance for {category} measurement evidence.")
    if has_visual and not has_topology:
        prompts.append("Attach measured topology or continuity-backed pinout evidence before first power/splice.")
    if status == "blocked":
        prompts.append("Resolve failed measurements, shorts, or hazardous sections before any repair authority claim.")
    return _dedupe(prompts)[:12]


def _authority_gates(
    status: str,
    missing_categories: Sequence[str],
    missing_trusted: Sequence[str],
    measurement_summary: Dict[str, Any],
    topology: Dict[str, Any],
    hazard_profile: Dict[str, Any],
) -> List[Dict[str, Any]]:
    gates = []
    gates.append(
        {
            "id": "hazard_scope",
            "label": "Hazard scope",
            "status": "fail" if hazard_profile.get("unsupported_for_production_authority") else "pass",
            "score": 0 if hazard_profile.get("unsupported_for_production_authority") else 1,
            "reason": "Unsupported hazard present." if hazard_profile.get("unsupported_for_production_authority") else "No unsupported hazard is attached.",
        }
    )
    gates.append(
        {
            "id": "topology_scope",
            "label": "Measured topology",
            "status": "pass" if topology.get("pinout_known") else "warn",
            "score": 1 if topology.get("pinout_known") else 0.4,
            "reason": "Measured pinout is known." if topology.get("pinout_known") else "Measured pinout/topology is incomplete.",
        }
    )
    gates.append(
        {
            "id": "measurement_presence",
            "label": "Measurement presence",
            "status": "fail" if measurement_summary["failed_count"] else "pass" if not missing_categories else "warn",
            "score": round(len(REQUIRED_LOW_RISK_CATEGORIES - set(missing_categories)) / len(REQUIRED_LOW_RISK_CATEGORIES), 3),
            "reason": "Failed measurement attached." if measurement_summary["failed_count"] else f"Missing categories: {', '.join(missing_categories) or 'none'}.",
        }
    )
    gates.append(
        {
            "id": "measurement_provenance",
            "label": "Measurement provenance",
            "status": "pass" if not missing_trusted else "warn",
            "score": round(len(REQUIRED_LOW_RISK_CATEGORIES - set(missing_trusted)) / len(REQUIRED_LOW_RISK_CATEGORIES), 3),
            "reason": f"Missing trusted categories: {', '.join(missing_trusted) or 'none'}.",
        }
    )
    if status == "blocked":
        gates.append({"id": "authority_block", "label": "Authority block", "status": "fail", "score": 0, "reason": "Failed, shorted, or hazardous evidence blocks authority."})
    return gates


def _authority_score(
    *,
    status: str,
    has_visual: bool,
    has_topology: bool,
    passed_categories: set[str],
    trusted_categories: set[str],
    failed: bool,
    unsupported_hazard: bool,
    pinout_known: bool,
) -> float:
    base = {"blocked": 0.08, "visual_only": 0.34, "needs_measurements": 0.48, "measurement_backed": 0.68, "authoritative_low_risk": 0.9}.get(status, 0.2)
    score = base
    if has_visual:
        score += 0.03
    if has_topology:
        score += 0.06
    if pinout_known:
        score += 0.05
    score += 0.02 * len(passed_categories)
    score += 0.015 * len(trusted_categories)
    if failed:
        score -= 0.25
    if unsupported_hazard:
        score -= 0.25
    return round(max(0.0, min(score, 0.96)), 3)


def _supported_decisions(status: str) -> List[str]:
    if status == "authoritative_low_risk":
        return [
            "low-risk measured first power",
            "controlled external splice within measured pin contract",
            "prototype repair/reuse decision for measured claims",
        ]
    if status == "measurement_backed":
        return ["measurement-backed advisory diagnosis", "prototype planning after remaining gates close"]
    if status in {"needs_measurements", "visual_only"}:
        return ["evidence collection", "candidate identification", "salvage planning"]
    return ["safety hold", "evidence triage"]


def _trust_level(score: float, status: str) -> str:
    if status == "blocked":
        return "blocked"
    if score >= 0.86:
        return "high"
    if score >= 0.62:
        return "medium"
    return "low"


def _launch_readiness(status: str) -> str:
    return {
        "authoritative_low_risk": "experimental_mvp_authority_ready",
        "measurement_backed": "experimental_mvp_candidate",
        "needs_measurements": "evidence_collection_required",
        "visual_only": "vision_only_candidate",
        "blocked": "blocked_safety_hold",
    }.get(status, "unknown")


def _trust_blockers(
    status: str,
    missing_categories: Sequence[str],
    missing_trusted: Sequence[str],
    hazard_profile: Dict[str, Any],
    topology_short: bool,
    failed: bool,
) -> List[str]:
    blockers = []
    if failed:
        blockers.append("Failed measurement evidence is attached.")
    if topology_short:
        blockers.append("Topology evidence reports a short or failed no-short check.")
    if hazard_profile.get("unsupported_for_production_authority"):
        blockers.append("Unsupported hazard scope is present.")
    if missing_categories:
        blockers.append(f"Missing measurement categories: {', '.join(missing_categories)}.")
    if missing_trusted:
        blockers.append(f"Missing trusted measurement provenance: {', '.join(missing_trusted)}.")
    if status == "visual_only":
        blockers.append("Image-only evidence cannot authorize repair, power, or splice.")
    return _dedupe(blockers)[:10]


def _summary(status: str, has_visual: bool, has_topology: bool, measurement_summary: Dict[str, Any], hazard_profile: Dict[str, Any]) -> str:
    pieces = [f"Derived arbitrary-board repair authority is {status}."]
    if has_visual:
        pieces.append("Visual evidence is available.")
    if has_topology:
        pieces.append("Measured topology evidence is available.")
    pieces.append(f"{measurement_summary['passed_count']} passing measurement(s), {measurement_summary['trusted_count']} trusted.")
    if hazard_profile.get("unsupported_for_production_authority"):
        pieces.append("Unsupported hazard scope blocks authority.")
    return " ".join(pieces)


def _claim_boundary(status: str) -> str:
    if status == "authoritative_low_risk":
        return "Authority applies only to measured low-risk topology, selected resources, and attached measurement provenance."
    if status == "blocked":
        return "Authority is blocked; use only for safety triage and evidence collection."
    return "Authority is advisory until measured topology, trusted measurements, and hazards are resolved."


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "yes", "1", "pass", "passed", "ok", "verified"}


def _positive(value: Any) -> bool:
    return str(value or "").strip().lower() in {
        "pass",
        "passed",
        "ok",
        "normal",
        "verified",
        "success",
        "successful",
        "working",
        "within_limit",
        "within limit",
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _failed(row: Dict[str, Any], text: str) -> bool:
    status = str(row.get("status") or row.get("result_status") or "").strip().lower()
    if status in FAIL_STATUSES:
        return True
    return bool(re.search(r"\b(fail|failed|unsafe|short detected|dead short|smoke|burning|overcurrent)\b", text))


def _passed(row: Dict[str, Any], text: str) -> bool:
    status = str(row.get("status") or row.get("result_status") or "").strip().lower()
    value = str(row.get("value", row.get("result", "")) or "").strip().lower()
    if status in PASS_STATUSES or value in PASS_STATUSES:
        return True
    if any(phrase in text for phrase in ["no short", "no-short", "continuity ok", "continuity pass", "idle high", "within limit", "polarity ok", "measured"]):
        return True
    return row.get("value", row.get("result")) not in {None, ""}


def _categories(text: str, unit: str) -> set[str]:
    raw = str(text or "").lower()
    unit = str(unit or "").lower()
    primary = raw.split()[0] if raw.split() else ""
    categories = set()
    voltage_blocked_by_primary = primary in {"resistance", "continuity", "current", "thermal"}
    if (
        not voltage_blocked_by_primary
        and ("voltage" in raw or "polarity" in raw or unit in {"v", "volt", "volts"} or re.search(r"\b\d+(?:\.\d+)?\s*v\b", raw))
    ):
        categories.add("voltage")
    if "resistance" in raw or "ohm" in raw or "no-short" in raw or "no short" in raw or unit in {"ohm", "ohms"}:
        categories.add("resistance")
    if "continuity" in raw or "shared ground" in raw or "connector ground" in raw:
        categories.add("continuity")
    if "current" in raw or "current-limited" in raw or "current limited" in raw or unit in {"a", "ma", "amp", "amps"}:
        categories.add("current")
    if any(token in raw for token in ["thermal", "temperature", "heat", "hot", "normal"]) or unit in {"c", "degc", "celsius"}:
        categories.add("thermal")
    if any(token in raw for token in ["logic", "uart", "serial", "i2c", "spi", "idle", "tx", "rx", "scl", "sda"]):
        categories.add("logic")
    if any(token in raw for token in ["load", "motor", "actuator", "driver", "dummy-load", "dummy load"]):
        categories.add("load")
    return categories


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
