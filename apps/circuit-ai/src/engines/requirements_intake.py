#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


LANES: Dict[str, str] = {
    "generic": "Generic PCB design / respin-prevention",
    "power": "Power / SMPS / high-current",
    "rf": "RF / antenna / impedance-controlled",
    "automotive": "Automotive constraints intake",
    "compliance": "Safety / compliance driven",
}

DESIGN_INTENTS: Dict[str, str] = {
    "prototype": "Prototype / functional-first (aesthetics optional)",
    "professional": "Production / polished (enclosure, DFM polish, presentation)",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _missing_fields(req: Dict[str, Any], required_paths: List[str]) -> List[str]:
    missing: List[str] = []
    for dotted in required_paths:
        cur: Any = req
        ok = True
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur and cur[part] not in (None, "", [], {}):
                cur = cur[part]
                continue
            ok = False
            break
        if not ok:
            missing.append(dotted)
    return missing


def evaluate_requirements(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate how "ready" a requirements object is for downstream work.

    Returns:
    - readiness_level: draft|reviewable|manufacturable
    - blockers: list[str] (items that prevent claiming higher readiness)
    - completeness_score: 0-100 (heuristic)
    """
    meta = req.get("meta") or {}
    manufacturing = req.get("manufacturing") or {}
    board = req.get("board") or {}
    intent = (meta.get("design_intent") or "prototype").strip()
    lane = (meta.get("lane") or "generic").strip()

    must_for_reviewable = [
        "meta.project_name",
        "manufacturing.fab.name",
        "board.layers",
    ]
    must_for_manufacturable = [
        "risk_and_validation.what_good_looks_like",
        "manufacturing.dnp_policy",
    ]

    # Lane-specific “to confidently validate” fields (still not a hard block to generate files).
    if lane == "power":
        must_for_manufacturable += [
            "power.sources",
            "power.rails",
            "power.loads",
        ]
    if lane == "rf":
        # Require explicit impedance/stackup notes to claim anything beyond draft.
        must_for_reviewable += ["board.stackup.notes"]

    blockers_reviewable = _missing_fields(req, must_for_reviewable)
    blockers_manufacturable = _missing_fields(req, must_for_manufacturable)

    # Additional lane-specific “don’t guess” gating. These are expressed as pseudo-paths.
    if lane == "power":
        power = req.get("power") or {}
        loads = power.get("loads") or []
        rails = power.get("rails") or []

        missing_load_currents = any(
            isinstance(load, dict) and load.get("current_a") in (None, "", 0) for load in loads
        )
        missing_load_rails = any(
            isinstance(load, dict) and not (load.get("rail") or "").strip() for load in loads
        )
        missing_rail_limits = any(
            isinstance(rail, dict) and rail.get("max_current_a") in (None, "", 0) for rail in rails
        )

        if missing_load_rails:
            blockers_manufacturable.append("power.loads[].rail")
        if missing_load_currents:
            blockers_manufacturable.append("power.loads[].current_a")
        if missing_rail_limits:
            blockers_manufacturable.append("power.rails[].max_current_a")

    # Professional intent expects enclosure/presentation constraints to be at least discussed.
    if intent == "professional":
        # Not hard-required, but we count it against score.
        pass

    # Simple scoring model based on filled “signal” fields.
    signal_fields = [
        ("meta.project_name", 10),
        ("manufacturing.fab.name", 10),
        ("board.layers", 10),
        ("board.constraints.min_trace_mm", 6),
        ("board.constraints.min_space_mm", 6),
        ("board.constraints.via_min_drill_mm", 4),
        ("board.constraints.copper_weight_oz", 4),
        ("risk_and_validation.what_good_looks_like", 10),
        ("risk_and_validation.test_plan", 6),
        ("manufacturing.dnp_policy", 4),
        ("manufacturing.preferred_part_source", 4),
        ("power.sources", 6),
        ("power.rails", 6),
        ("power.loads", 6),
        ("board.stackup.manufacturer", 4),
        ("board.stackup.notes", 4),
        ("board.environment.ambient_c", 2),
        ("power.protection", 2),
    ]
    score = 0
    for dotted, pts in signal_fields:
        if dotted not in _missing_fields(req, [dotted]):
            score += pts
    score = max(0, min(100, score))

    if blockers_reviewable:
        level = "draft"
        blockers = blockers_reviewable
    elif blockers_manufacturable:
        level = "reviewable"
        blockers = blockers_manufacturable
    else:
        level = "manufacturable"
        blockers = []

    return {
        "readiness_level": level,
        "blockers": blockers,
        "completeness_score": score,
        "lane": lane,
        "design_intent": intent,
    }


def run_lane_checks(req: Dict[str, Any]) -> Dict[str, Any]:
    meta = req.get("meta") or {}
    lane = (meta.get("lane") or "generic").strip()
    intent = (meta.get("design_intent") or "prototype").strip()

    checks: Dict[str, Any] = {}
    checks["power_budget"] = _check_power_budget(req, intent=intent)
    checks["protection"] = _check_protection(req, intent=intent)
    checks["regulators"] = _check_regulators(req, intent=intent)
    checks["derating"] = _check_derating(req, intent=intent)
    checks["interfaces"] = _check_interfaces(req, intent=intent)
    checks["decoupling"] = _check_decoupling(req, intent=intent)
    checks["grounding_layout"] = _check_grounding_layout(req, intent=intent)
    checks["connectors_esd"] = _check_connectors_esd(req, intent=intent)

    overall_status = "ok"
    issues: List[Dict[str, Any]] = []
    missing_inputs: List[str] = []
    for check in checks.values():
        if isinstance(check, dict):
            overall_status = _rollup_status(overall_status, check.get("status"))
            issues.extend(check.get("issues") or [])
            missing_inputs.extend(check.get("missing_inputs") or [])

    readiness = evaluate_requirements(req)
    quality = compute_ee_quality_grade(readiness=readiness, checks=checks)

    return {
        "lane": lane,
        "design_intent": intent,
        "status": overall_status,
        "issues": issues,
        "missing_inputs": sorted(set(missing_inputs)),
        "checks": checks,
        "quality": quality,
        "generated_at": _utc_now(),
    }


def build_capability_matrix(req: Dict[str, Any], readiness: Dict[str, Any], lane_checks: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a bounded “what we can reliably do” matrix.

    This is intentionally conservative: if critical inputs are missing we return `needs_input`
    rather than claiming the capability is reliable.
    """
    readiness_level = (readiness or {}).get("readiness_level") or "draft"
    blockers = list((readiness or {}).get("blockers") or [])

    def cap(status: str, notes: str = "", cap_blockers: Optional[List[str]] = None) -> Dict[str, Any]:
        return {"status": status, "notes": notes, "blockers": cap_blockers or []}

    capabilities: Dict[str, Any] = {}
    capabilities["intake_scoping"] = cap("reliable", "Constraints intake + questions + SOW generation.")

    if readiness_level == "draft":
        capabilities["review_package"] = cap("needs_input", "Need minimum constraints to avoid guessing.", blockers)
    else:
        capabilities["review_package"] = cap("reliable", "Can generate review-grade artifacts and highlight blockers.")

    if readiness_level != "manufacturable":
        capabilities["manufacturing_package"] = cap(
            "needs_input",
            "Refuses to claim manufacturing-ready until critical constraints are provided.",
            blockers,
        )
    else:
        capabilities["manufacturing_package"] = cap("reliable", "Can produce manufacturing-ready package (strict).")

    power_budget_status = ((lane_checks or {}).get("checks") or {}).get("power_budget", {}).get("status")
    if power_budget_status in ("ok", "issues_found"):
        capabilities["power_budget_check"] = cap(
            "reliable" if power_budget_status == "ok" else "reliable",
            "Computes per-rail current totals and flags over-limit conditions.",
        )
    else:
        missing = ((lane_checks or {}).get("checks") or {}).get("power_budget", {}).get("missing_inputs") or []
        capabilities["power_budget_check"] = cap("needs_input", "Needs per-load currents and rail limits.", list(missing))

    protection_status = ((lane_checks or {}).get("checks") or {}).get("protection", {}).get("status")
    if protection_status == "ok":
        capabilities["protection_checklist"] = cap("reliable", "Generates protection checklist tailored to intent/lane.")
    else:
        missing = ((lane_checks or {}).get("checks") or {}).get("protection", {}).get("missing_inputs") or []
        capabilities["protection_checklist"] = cap("needs_input", "Needs environment + input transient details.", list(missing))

    regulators_status = ((lane_checks or {}).get("checks") or {}).get("regulators", {}).get("status")
    if regulators_status in ("ok", "issues_found"):
        capabilities["regulator_sanity_check"] = cap(
            "reliable",
            "Checks basic headroom/dropout and crude thermal margin (requires regulator inputs).",
        )
    else:
        missing = ((lane_checks or {}).get("checks") or {}).get("regulators", {}).get("missing_inputs") or []
        capabilities["regulator_sanity_check"] = cap("needs_input", "Needs regulator VIN/VOUT/current/thermal inputs.", list(missing))

    derating_status = ((lane_checks or {}).get("checks") or {}).get("derating", {}).get("status")
    if derating_status in ("ok", "issues_found"):
        capabilities["component_derating_check"] = cap(
            "reliable",
            "Flags obvious rating/derating risks for parts with provided operating vs rating numbers.",
        )
    else:
        missing = ((lane_checks or {}).get("checks") or {}).get("derating", {}).get("missing_inputs") or []
        capabilities["component_derating_check"] = cap("needs_input", "Needs BOM items with ratings and operating conditions.", list(missing))

    interfaces_status = ((lane_checks or {}).get("checks") or {}).get("interfaces", {}).get("status")
    if interfaces_status in ("ok", "issues_found"):
        capabilities["interface_sanity_check"] = cap("reliable", "Checks common interface pitfalls (levels, terminations, pullups).")
    else:
        missing = ((lane_checks or {}).get("checks") or {}).get("interfaces", {}).get("missing_inputs") or []
        capabilities["interface_sanity_check"] = cap("needs_input", "Needs interface list with voltage/speed/cable details.", list(missing))

    decoupling_status = ((lane_checks or {}).get("checks") or {}).get("decoupling", {}).get("status")
    if decoupling_status in ("ok", "issues_found"):
        capabilities["decoupling_checklist"] = cap("reliable", "Generates decoupling/bulk capacitor checklist per rail/load.")
    else:
        missing = ((lane_checks or {}).get("checks") or {}).get("decoupling", {}).get("missing_inputs") or []
        capabilities["decoupling_checklist"] = cap("needs_input", "Needs power rails/loads and confirmation of decoupling approach.", list(missing))

    layout_status = ((lane_checks or {}).get("checks") or {}).get("grounding_layout", {}).get("status")
    if layout_status in ("ok", "issues_found"):
        capabilities["grounding_layout_checklist"] = cap("reliable", "Generates grounding/return-path/layout checklist based on lane.")
    else:
        missing = ((lane_checks or {}).get("checks") or {}).get("grounding_layout", {}).get("missing_inputs") or []
        capabilities["grounding_layout_checklist"] = cap("needs_input", "Needs lane + key constraints (stackup, return path, current loops).", list(missing))

    esd_status = ((lane_checks or {}).get("checks") or {}).get("connectors_esd", {}).get("status")
    if esd_status in ("ok", "issues_found"):
        capabilities["connector_esd_checklist"] = cap("reliable", "Generates connector/ESD/hotplug protection checklist.")
    else:
        missing = ((lane_checks or {}).get("checks") or {}).get("connectors_esd", {}).get("missing_inputs") or []
        capabilities["connector_esd_checklist"] = cap("needs_input", "Needs connector/external IO list and environment.", list(missing))

    return {
        "readiness_level": readiness_level,
        "capabilities": capabilities,
        "generated_at": _utc_now(),
    }


def _rollup_status(current: str, next_status: Optional[str]) -> str:
    order = {"ok": 0, "needs_input": 1, "issues_found": 2}
    cur = order.get(current or "ok", 0)
    nxt = order.get((next_status or "ok"), 0)
    inv = {0: "ok", 1: "needs_input", 2: "issues_found"}
    return inv[max(cur, nxt)]


def _check_power_budget(req: Dict[str, Any], intent: str) -> Dict[str, Any]:
    power = req.get("power") or {}
    rails = power.get("rails") or []
    loads = power.get("loads") or []

    rails_by_name: Dict[str, Dict[str, Any]] = {}
    for rail in rails:
        if not isinstance(rail, dict):
            continue
        rail_name = (rail.get("name") or "").strip()
        if not rail_name:
            continue
        rails_by_name[rail_name] = rail

    missing_inputs: List[str] = []
    if not rails_by_name:
        missing_inputs.append("power.rails")

    totals_by_rail: Dict[str, float] = {}
    for load in loads:
        if not isinstance(load, dict):
            continue
        rail_name = (load.get("rail") or "").strip()
        if not rail_name:
            missing_inputs.append("power.loads[].rail")
            continue
        current_a = load.get("current_a")
        if current_a in (None, "", 0):
            missing_inputs.append("power.loads[].current_a")
            continue
        try:
            current_f = float(current_a)
        except Exception:
            missing_inputs.append("power.loads[].current_a")
            continue
        totals_by_rail[rail_name] = totals_by_rail.get(rail_name, 0.0) + current_f

    per_rail: Dict[str, Any] = {}
    issues: List[Dict[str, Any]] = []
    status = "ok"

    for rail_name, total_load_a in sorted(totals_by_rail.items()):
        rail = rails_by_name.get(rail_name) or {}
        limit_a = rail.get("max_current_a")
        if limit_a in (None, "", 0):
            status = _rollup_status(status, "needs_input")
            missing_inputs.append("power.rails[].max_current_a")
            per_rail[rail_name] = {
                "total_load_a": total_load_a,
                "limit_a": None,
                "status": "unknown_limit",
            }
            continue
        try:
            limit_f = float(limit_a)
        except Exception:
            status = _rollup_status(status, "needs_input")
            missing_inputs.append("power.rails[].max_current_a")
            per_rail[rail_name] = {
                "total_load_a": total_load_a,
                "limit_a": None,
                "status": "unknown_limit",
            }
            continue

        if total_load_a > limit_f:
            status = _rollup_status(status, "issues_found")
            issue = {
                "type": "power_budget_over_limit",
                "rail": rail_name,
                "total_load_a": total_load_a,
                "limit_a": limit_f,
                "notes": "Total expected rail load exceeds declared rail max current.",
            }
            issues.append(issue)
            per_rail[rail_name] = {"total_load_a": total_load_a, "limit_a": limit_f, "status": "over_limit"}
        else:
            per_rail[rail_name] = {"total_load_a": total_load_a, "limit_a": limit_f, "status": "ok"}

    if missing_inputs and status == "ok":
        status = "needs_input"

    notes = "Prototype intent: accept rough estimates; production intent: require per-load max current and rail headroom."
    if intent == "professional":
        notes = "Production intent: require per-load max current, rail headroom, and thermal/derating notes."

    return {
        "status": status,
        "missing_inputs": sorted(set(missing_inputs)),
        "issues": issues,
        "rails": per_rail,
        "notes": notes,
    }


def _check_protection(req: Dict[str, Any], intent: str) -> Dict[str, Any]:
    meta = req.get("meta") or {}
    lane = (meta.get("lane") or "generic").strip()
    board = req.get("board") or {}
    environment = (board.get("environment") or {}) if isinstance(board.get("environment"), dict) else {}

    missing_inputs: List[str] = []
    if not environment:
        missing_inputs.append("board.environment")
    if lane in ("power", "automotive"):
        missing_inputs.append("power.input_transients")

    recommendations: List[Dict[str, Any]] = [
        {"item": "Reverse polarity protection", "why": "Prevents damage from miswiring or connector reversal."},
        {"item": "Input fuse / PTC", "why": "Limits fault current and reduces catastrophic failures."},
        {"item": "TVS diode (ESD/transient)", "why": "Clamps ESD and fast transients at connectors."},
    ]
    if lane in ("power", "automotive"):
        recommendations.append({"item": "Inrush limiting", "why": "Reduces connector arcing and brownouts on hot-plug."})
        recommendations.append({"item": "Load dump / surge strategy", "why": "Automotive/power inputs may see large surges."})

    status = "ok" if not missing_inputs else "needs_input"
    notes = "This is a checklist generator; final protection choices depend on environment and connector/transient specs."
    if intent == "professional":
        notes = "Production intent: require explicit transient/environment specs and component selection notes."

    return {
        "status": status,
        "missing_inputs": sorted(set(missing_inputs)),
        "issues": [],
        "recommendations": recommendations,
        "notes": notes,
    }


def _check_regulators(req: Dict[str, Any], intent: str) -> Dict[str, Any]:
    power = req.get("power") or {}
    regs = power.get("regulators") or []
    board = req.get("board") or {}
    environment = board.get("environment") or {}

    missing_inputs: List[str] = []
    if not regs:
        missing_inputs.append("power.regulators")

    ambient_c = environment.get("ambient_c") if isinstance(environment, dict) else None
    try:
        ambient_f = float(ambient_c) if ambient_c not in (None, "") else None
    except Exception:
        ambient_f = None
        missing_inputs.append("board.environment.ambient_c")

    issues: List[Dict[str, Any]] = []
    per_reg: List[Dict[str, Any]] = []
    status = "ok"

    for reg in regs:
        if not isinstance(reg, dict):
            continue
        name = (reg.get("name") or "regulator").strip()
        reg_type = (reg.get("type") or "").strip().upper() or "LDO"

        def f(key: str) -> Optional[float]:
            val = reg.get(key)
            if val in (None, ""):
                return None
            try:
                return float(val)
            except Exception:
                return None

        vin_min = f("vin_min_v")
        vin_max = f("vin_max_v")
        vout = f("vout_v")
        iout_max = f("iout_max_a")
        iout_est = f("iout_est_a")
        dropout = f("dropout_v")
        eff = f("efficiency_est")
        theta = f("theta_ja_c_per_w")
        max_j = f("max_junction_c") or 125.0

        reg_missing: List[str] = []
        if vin_min is None:
            reg_missing.append("power.regulators[].vin_min_v")
        if vout is None:
            reg_missing.append("power.regulators[].vout_v")
        if reg_type == "LDO" and dropout is None:
            reg_missing.append("power.regulators[].dropout_v")
        if iout_est is None and iout_max is None:
            reg_missing.append("power.regulators[].iout_est_a")
        if theta is None:
            reg_missing.append("power.regulators[].theta_ja_c_per_w")
        if ambient_f is None:
            reg_missing.append("board.environment.ambient_c")

        if reg_missing:
            status = _rollup_status(status, "needs_input")
            missing_inputs.extend(reg_missing)
            per_reg.append({"name": name, "type": reg_type, "status": "needs_input", "missing": sorted(set(reg_missing))})
            continue

        headroom_v = (vin_min or 0.0) - (vout or 0.0)
        margin_v = 0.2 if intent == "professional" else 0.1
        if reg_type == "LDO":
            required_headroom = (dropout or 0.0) + margin_v
            if headroom_v < required_headroom:
                status = _rollup_status(status, "issues_found")
                issues.append(
                    {
                        "type": "regulator_headroom",
                        "severity": "warning" if intent != "professional" else "error",
                        "regulator": name,
                        "message": "Insufficient LDO headroom vs dropout + margin.",
                        "details": {
                            "vin_min_v": vin_min,
                            "vout_v": vout,
                            "dropout_v": dropout,
                            "headroom_v": headroom_v,
                            "required_headroom_v": required_headroom,
                        },
                    }
                )

        i_used = iout_est if iout_est is not None else (iout_max or 0.0)
        p_diss_w: Optional[float] = None
        if reg_type == "LDO":
            p_diss_w = max(0.0, ((vin_max or vin_min or 0.0) - (vout or 0.0)) * i_used)
        else:
            eff_used = eff if eff is not None else (0.85 if reg_type in ("BUCK", "BOOST") else 0.8)
            p_out = (vout or 0.0) * i_used
            if eff_used > 0:
                p_in = p_out / eff_used
                p_diss_w = max(0.0, p_in - p_out)

        tj_est_c = None
        if p_diss_w is not None and theta is not None and ambient_f is not None:
            tj_est_c = ambient_f + (p_diss_w * theta)
            if tj_est_c > max_j:
                status = _rollup_status(status, "issues_found")
                issues.append(
                    {
                        "type": "regulator_thermal",
                        "severity": "warning" if intent != "professional" else "error",
                        "regulator": name,
                        "message": "Estimated junction temperature exceeds max_junction_c.",
                        "details": {
                            "ambient_c": ambient_f,
                            "theta_ja_c_per_w": theta,
                            "p_diss_w": p_diss_w,
                            "tj_est_c": tj_est_c,
                            "max_junction_c": max_j,
                        },
                    }
                )

        per_reg.append(
            {
                "name": name,
                "type": reg_type,
                "status": "ok",
                "headroom_v": headroom_v,
                "p_diss_w": p_diss_w,
                "tj_est_c": tj_est_c,
            }
        )

    if missing_inputs and status == "ok":
        status = "needs_input"

    return {
        "status": status,
        "missing_inputs": sorted(set(missing_inputs)),
        "issues": issues,
        "regulators": per_reg,
        "notes": "Coarse checks only. Final regulator validation requires datasheet curves, layout, and operating envelope confirmation.",
    }


def _check_derating(req: Dict[str, Any], intent: str) -> Dict[str, Any]:
    bom = req.get("bom") or []
    missing_inputs: List[str] = []
    if not bom:
        missing_inputs.append("bom")

    issues: List[Dict[str, Any]] = []
    status = "ok"

    resistor_util_limit = 0.6 if intent != "professional" else 0.5
    cap_util_limit = 0.7 if intent != "professional" else 0.5

    def f(item: Dict[str, Any], key: str) -> Optional[float]:
        val = item.get(key)
        if val in (None, ""):
            return None
        try:
            return float(val)
        except Exception:
            return None

    for item in bom:
        if not isinstance(item, dict):
            continue
        part_type = (item.get("type") or item.get("category") or "").strip().lower()
        ref = (item.get("ref") or item.get("designator") or item.get("refs") or "").strip() or "?"
        name = (item.get("name") or item.get("mpn") or "").strip()

        if part_type == "resistor":
            rating_w = f(item, "power_rating_w")
            used_w = f(item, "power_diss_w")
            if rating_w is None or used_w is None:
                status = _rollup_status(status, "needs_input")
                missing_inputs.extend(["bom[].power_rating_w", "bom[].power_diss_w"])
            else:
                util = (used_w / rating_w) if rating_w > 0 else None
                if util is not None and util > resistor_util_limit:
                    status = _rollup_status(status, "issues_found")
                    issues.append(
                        {
                            "type": "derating_resistor_power",
                            "severity": "warning" if intent != "professional" else "error",
                            "ref": ref,
                            "name": name,
                            "message": "Resistor dissipation exceeds conservative derating target.",
                            "details": {"power_diss_w": used_w, "power_rating_w": rating_w, "utilization": util},
                        }
                    )

        if part_type in ("cap", "capacitor"):
            v_rating = f(item, "voltage_rating_v")
            v_oper = f(item, "voltage_operating_v")
            if v_rating is None or v_oper is None:
                status = _rollup_status(status, "needs_input")
                missing_inputs.extend(["bom[].voltage_rating_v", "bom[].voltage_operating_v"])
            else:
                util = (v_oper / v_rating) if v_rating > 0 else None
                if util is not None and util > cap_util_limit:
                    status = _rollup_status(status, "issues_found")
                    issues.append(
                        {
                            "type": "derating_cap_voltage",
                            "severity": "warning" if intent != "professional" else "error",
                            "ref": ref,
                            "name": name,
                            "message": "Capacitor voltage utilization exceeds conservative derating target.",
                            "details": {"voltage_operating_v": v_oper, "voltage_rating_v": v_rating, "utilization": util},
                        }
                    )

    if missing_inputs and status == "ok":
        status = "needs_input"

    return {
        "status": status,
        "missing_inputs": sorted(set(missing_inputs)),
        "issues": issues,
        "notes": "Derating checks apply only when operating vs rating numbers are provided; otherwise the system will request them.",
    }


def _check_interfaces(req: Dict[str, Any], intent: str) -> Dict[str, Any]:
    """
    Conservative interface sanity checks.

    This is not schematic-level verification; it’s a checklist + “don’t guess” gating
    for common integration failures (levels, pullups, termination, impedance).
    """
    meta = req.get("meta") or {}
    lane = (meta.get("lane") or "generic").strip()
    interfaces = req.get("interfaces") or []

    missing_inputs: List[str] = []
    if not interfaces:
        missing_inputs.append("interfaces")

    issues: List[Dict[str, Any]] = []
    status = "ok"

    for iface in interfaces:
        if not isinstance(iface, dict):
            continue
        name = (iface.get("name") or "interface").strip()
        itype = (iface.get("type") or "").strip().upper()
        v = iface.get("voltage_v")
        speed = iface.get("speed_hz") or iface.get("baud") or iface.get("bitrate_bps")
        cable_cm = iface.get("cable_length_cm")

        # Generic gating
        if itype in ("I2C", "SPI", "UART", "CAN", "USB", "ETH", "GPIO", "PWM"):
            if v in (None, ""):
                status = _rollup_status(status, "needs_input")
                missing_inputs.append("interfaces[].voltage_v")

        # I2C: pullups & bus length
        if itype == "I2C":
            pullups = iface.get("pullups_present")
            evidence = req.get("evidence") if isinstance(req.get("evidence"), dict) else {}
            findings = evidence.get("findings") if isinstance(evidence.get("findings"), dict) else {}
            pullup_by_net = ((findings.get("pullups") or {}).get("by_net") or {}) if isinstance(findings.get("pullups"), dict) else {}

            def evidence_has_i2c_pullups() -> bool:
                if pullup_by_net:
                    # If caller provided explicit nets for this interface, match against them.
                    nets = iface.get("nets") if isinstance(iface.get("nets"), list) else []
                    net_names = [str(n).upper() for n in nets if str(n).strip()]
                    if net_names:
                        for nn in net_names:
                            if nn in (str(k).upper() for k in pullup_by_net.keys()):
                                return True
                    # Otherwise, use common signal net name heuristics.
                    for k in pullup_by_net.keys():
                        ku = str(k).upper()
                        if "SDA" in ku or "SCL" in ku:
                            return True
                    # Fallback: any pullups exist (better than hard-failing).
                    return True
                return False

            if pullups is None:
                if evidence_has_i2c_pullups():
                    pullups = True
                else:
                    status = _rollup_status(status, "needs_input")
                    missing_inputs.append("interfaces[].pullups_present")
            elif pullups is False:
                status = _rollup_status(status, "issues_found")
                issues.append(
                    {
                        "type": "i2c_pullups_missing",
                        "severity": "warning" if intent != "professional" else "error",
                        "interface": name,
                        "message": "I2C interface indicates no pullups; bus likely will not function.",
                    }
                )
            if cable_cm not in (None, ""):
                try:
                    if float(cable_cm) > 30:
                        status = _rollup_status(status, "issues_found")
                        issues.append(
                            {
                                "type": "i2c_cable_length_risk",
                                "severity": "warning",
                                "interface": name,
                                "message": "Long I2C cable length increases susceptibility to noise; consider lower speed/buffers.",
                                "details": {"cable_length_cm": float(cable_cm)},
                            }
                        )
                except Exception:
                    status = _rollup_status(status, "needs_input")
                    missing_inputs.append("interfaces[].cable_length_cm")

        # CAN: termination + transceiver
        if itype == "CAN":
            term = iface.get("termination_ohms")
            transceiver = iface.get("transceiver_present")
            if transceiver is None:
                status = _rollup_status(status, "needs_input")
                missing_inputs.append("interfaces[].transceiver_present")
            elif transceiver is False:
                status = _rollup_status(status, "issues_found")
                issues.append(
                    {
                        "type": "can_transceiver_missing",
                        "severity": "error",
                        "interface": name,
                        "message": "CAN requires a transceiver; MCU pins alone are not CAN physical layer.",
                    }
                )
            if term is None:
                status = _rollup_status(status, "needs_input")
                missing_inputs.append("interfaces[].termination_ohms")
            else:
                try:
                    term_f = float(term)
                    # Not always required if node is not at bus end, so warning not error.
                    if term_f not in (60, 120):
                        status = _rollup_status(status, "issues_found")
                        issues.append(
                            {
                                "type": "can_termination_suspicious",
                                "severity": "warning",
                                "interface": name,
                                "message": "CAN termination value looks unusual; confirm bus topology (end node vs mid).",
                                "details": {"termination_ohms": term_f},
                            }
                        )
                except Exception:
                    status = _rollup_status(status, "needs_input")
                    missing_inputs.append("interfaces[].termination_ohms")

        # USB: ESD + controlled impedance note (esp for HS)
        if itype == "USB":
            esd = iface.get("esd_protection_present")
            if esd is None:
                status = _rollup_status(status, "needs_input")
                missing_inputs.append("interfaces[].esd_protection_present")
            if speed is None:
                status = _rollup_status(status, "needs_input")
                missing_inputs.append("interfaces[].speed_hz")
            else:
                # If speed suggests HS (480Mbps) require impedance/length matching acknowledgement.
                try:
                    speed_f = float(speed)
                    if speed_f >= 10_000_000:
                        ack = iface.get("diff_pair_impedance_controlled")
                        if ack is None:
                            status = _rollup_status(status, "needs_input")
                            missing_inputs.append("interfaces[].diff_pair_impedance_controlled")
                        elif ack is False:
                            status = _rollup_status(status, "issues_found")
                            issues.append(
                                {
                                    "type": "usb_impedance_not_controlled",
                                    "severity": "warning" if intent != "professional" else "error",
                                    "interface": name,
                                    "message": "High-speed USB typically needs controlled impedance + length matching.",
                                }
                            )
                except Exception:
                    status = _rollup_status(status, "needs_input")
                    missing_inputs.append("interfaces[].speed_hz")

        # RF: impedance targets must be explicit
        if itype == "RF" or lane == "rf":
            targets = iface.get("targets") if isinstance(iface.get("targets"), dict) else {}
            if not targets or targets.get("impedance_ohms") in (None, ""):
                status = _rollup_status(status, "needs_input")
                missing_inputs.append("interfaces[].targets.impedance_ohms")

    if missing_inputs and status == "ok":
        status = "needs_input"

    return {
        "status": status,
        "missing_inputs": sorted(set(missing_inputs)),
        "issues": issues,
        "notes": "Interface checks are conservative. They surface common integration failures and request missing interface constraints.",
    }


def _check_decoupling(req: Dict[str, Any], intent: str) -> Dict[str, Any]:
    power = req.get("power") or {}
    rails = power.get("rails") or []
    loads = power.get("loads") or []
    dec = power.get("decoupling") or {}

    missing_inputs: List[str] = []
    if not rails:
        missing_inputs.append("power.rails")
    if not loads:
        missing_inputs.append("power.loads")
    if not isinstance(dec, dict) or dec.get("confirmed") is None:
        missing_inputs.append("power.decoupling.confirmed")

    recs: List[Dict[str, Any]] = []
    # Generic decoupling guidance; not a guarantee without schematic/layout.
    recs.append({"item": "0.1uF ceramic at each IC VDD pin", "why": "Reduces local supply impedance at high frequency."})
    recs.append({"item": "1–10uF bulk per rail near load cluster", "why": "Handles transient current demand and reduces droop."})
    recs.append({"item": "Place caps close with short loop (cap->pin->ground)", "why": "Loop inductance dominates at high frequency."})
    if intent == "professional":
        recs.append({"item": "Document decoupling per IC and per rail", "why": "Makes review/manufacturing iterations safer."})

    status = "ok" if not missing_inputs else "needs_input"
    evidence = req.get("evidence") if isinstance(req.get("evidence"), dict) else {}
    findings = evidence.get("findings") if isinstance(evidence.get("findings"), dict) else {}
    dec_found = (findings.get("decoupling") or {}).get("by_rail") if isinstance(findings.get("decoupling"), dict) else None
    return {
        "status": status,
        "missing_inputs": sorted(set(missing_inputs)),
        "issues": [],
        "recommendations": recs,
        "observed": {"decoupling_caps_by_rail": dec_found} if isinstance(dec_found, dict) else {},
        "notes": "This is a checklist. Confirmed=true means the project explicitly reviewed/accepted the decoupling plan.",
    }


def _check_grounding_layout(req: Dict[str, Any], intent: str) -> Dict[str, Any]:
    meta = req.get("meta") or {}
    lane = (meta.get("lane") or "generic").strip()
    board = req.get("board") or {}
    stackup = board.get("stackup") or {}

    missing_inputs: List[str] = []
    if lane in ("rf", "power") and not (isinstance(stackup, dict) and (stackup.get("notes") or "").strip()):
        missing_inputs.append("board.stackup.notes")

    recs: List[Dict[str, Any]] = []
    recs.append({"item": "Continuous return path under high-speed signals", "why": "Reduces EMI and signal integrity issues."})
    recs.append({"item": "Minimize loop area for switching/high-current paths", "why": "Reduces radiated EMI and voltage spikes."})
    recs.append({"item": "Star/segmented grounds only when necessary; otherwise solid ground plane", "why": "Accidental splits create return discontinuities."})
    if lane == "rf":
        recs.append({"item": "Keep RF path short; avoid stubs; ground stitching vias", "why": "Controls impedance and reduces coupling."})
    if lane == "power":
        recs.append({"item": "Separate noisy switch node from sensitive analog/RF", "why": "Switching noise coupling is a common failure mode."})

    status = "ok" if not missing_inputs else "needs_input"
    return {
        "status": status,
        "missing_inputs": sorted(set(missing_inputs)),
        "issues": [],
        "recommendations": recs,
        "notes": "Layout/grounding is context dependent; these are high-signal heuristics and required confirmations.",
    }


def _check_connectors_esd(req: Dict[str, Any], intent: str) -> Dict[str, Any]:
    connectors = req.get("connectors") or []
    board = req.get("board") or {}
    environment = board.get("environment") or {}

    missing_inputs: List[str] = []
    if not connectors:
        missing_inputs.append("connectors")
    if not isinstance(environment, dict) or not environment:
        missing_inputs.append("board.environment")

    issues: List[Dict[str, Any]] = []
    status = "ok"
    for conn in connectors:
        if not isinstance(conn, dict):
            continue
        name = (conn.get("name") or "connector").strip()
        external = conn.get("external")
        hotplug = conn.get("hotplug")
        if external is None:
            status = _rollup_status(status, "needs_input")
            missing_inputs.append("connectors[].external")
        if hotplug is None:
            status = _rollup_status(status, "needs_input")
            missing_inputs.append("connectors[].hotplug")
        if external is True:
            esd = conn.get("esd_protection_present")
            if esd is None:
                status = _rollup_status(status, "needs_input")
                missing_inputs.append("connectors[].esd_protection_present")
            elif esd is False:
                status = _rollup_status(status, "issues_found")
                issues.append(
                    {
                        "type": "connector_esd_missing",
                        "severity": "warning" if intent != "professional" else "error",
                        "connector": name,
                        "message": "External connector without stated ESD protection; high risk for field failures.",
                    }
                )
        if hotplug is True:
            inrush = conn.get("inrush_mitigation_present")
            if inrush is None:
                status = _rollup_status(status, "needs_input")
                missing_inputs.append("connectors[].inrush_mitigation_present")

    if missing_inputs and status == "ok":
        status = "needs_input"

    return {
        "status": status,
        "missing_inputs": sorted(set(missing_inputs)),
        "issues": issues,
        "notes": "Connector/ESD checklist: final choices depend on environment class and connector spec; missing fields are explicitly requested.",
    }


def compute_ee_quality_grade(readiness: Dict[str, Any], checks: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a conservative “EE quality grade” signal.

    This is NOT a certification and is intentionally biased toward asking for missing inputs.
    """
    readiness_level = (readiness or {}).get("readiness_level") or "draft"
    completeness = (readiness or {}).get("completeness_score")
    try:
        completeness_f = float(completeness) if completeness is not None else None
    except Exception:
        completeness_f = None

    score = 100.0
    reasons: List[str] = []

    # Readiness caps
    if readiness_level == "draft":
        score = min(score, 60.0)
        reasons.append("Readiness is draft (critical constraints missing).")
    elif readiness_level == "reviewable":
        score = min(score, 85.0)
        reasons.append("Readiness is reviewable (some constraints missing).")

    # Penalize missing inputs and issues
    missing: List[str] = []
    issue_penalty = 0.0
    for name, chk in (checks or {}).items():
        if not isinstance(chk, dict):
            continue
        for m in (chk.get("missing_inputs") or []):
            missing.append(str(m))
        for issue in (chk.get("issues") or []):
            sev = (issue.get("severity") or "warning").lower()
            if sev == "error":
                issue_penalty += 20.0
            else:
                issue_penalty += 10.0
    uniq_missing = sorted(set(missing))
    score -= min(25.0, 2.0 * len(uniq_missing))
    score -= min(40.0, issue_penalty)
    score = max(0.0, min(100.0, score))

    if uniq_missing:
        reasons.append(f"Missing inputs: {len(uniq_missing)} fields.")
    if issue_penalty:
        reasons.append("One or more checks reported issues.")

    # Confidence is dominated by completeness.
    confidence = 0.5
    if completeness_f is not None:
        confidence = max(0.1, min(0.95, 0.2 + (completeness_f / 100.0) * 0.75))
    if readiness_level == "draft":
        confidence = min(confidence, 0.4)

    grade = "F"
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    elif score >= 50:
        grade = "E"

    return {
        "score": round(score, 1),
        "grade": grade,
        "confidence": round(float(confidence), 2),
        "reasons": reasons[:10],
        "readiness_level": readiness_level,
    }


def template_for_lane(lane: str) -> Dict[str, Any]:
    lane = (lane or "").strip() or "generic"
    base: Dict[str, Any] = {
        "meta": {
            "lane": lane,
            "design_intent": "prototype",
            "generated_at": _utc_now(),
            "client_name": "",
            "project_name": "",
            "timezone": "",
        },
        "deliverables": {
            "schematic": True,
            "pcb_layout": True,
            "bom": True,
            "pnp": True,
            "gerbers": True,
            "dfm_memo": True,
            "bringup_notes": False,
        },
        "board": {
            "layers": None,
            "dimensions_mm": {"x": None, "y": None},
            "stackup": {"manufacturer": "", "notes": ""},
            "environment": {"ambient_c": None, "max_c": None, "notes": ""},
            "constraints": {
                "min_trace_mm": None,
                "min_space_mm": None,
                "via_min_drill_mm": None,
                "copper_weight_oz": None,
            },
        },
        "interfaces": [],
        "connectors": [],
        "bom": [],
        "power": {
            "rails": [],
            "sources": [],
            "loads": [],
            "regulators": [],
            "decoupling": {
                "strategy": "",
                "confirmed": None,
                "notes": "",
            },
            "protection": {
                "reverse_polarity": None,
                "fuse_or_ptc": None,
                "tvs": None,
                "inrush_limit": None,
                "notes": "",
            },
        },
        "manufacturing": {
            "fab": {"name": "", "url": "", "notes": ""},
            "assembly": {"name": "", "notes": ""},
            "dnp_policy": "explicit",
            "preferred_part_source": "",
        },
        "risk_and_validation": {
            "what_good_looks_like": "",
            "test_plan": "",
            "known_risks": [],
            "explicit_exclusions": [],
        },
    }

    if lane == "power":
        base["power"]["rails"] = [
            {"name": "VIN", "voltage_v": None, "max_current_a": None, "notes": ""},
            {"name": "3V3", "voltage_v": 3.3, "max_current_a": None, "notes": "Target rail"},
        ]
        base["power"]["regulators"] = [
            {
                "name": "U?",
                "type": "LDO",
                "vin_min_v": None,
                "vin_max_v": None,
                "vout_v": 3.3,
                "iout_max_a": None,
                "iout_est_a": None,
                "dropout_v": None,
                "efficiency_est": None,
                "theta_ja_c_per_w": None,
                "max_junction_c": 125,
                "notes": "",
            }
        ]
        base["risk_and_validation"]["explicit_exclusions"] = [
            "No conducted/radiated EMI compliance testing (needs lab).",
            "No thermal chamber validation unless provided by client.",
        ]
    elif lane == "rf":
        base["board"]["stackup"]["notes"] = "Provide impedance targets + fab stackup (dielectric, Er, copper thickness) for controlled impedance."
        base["interfaces"] = [{"name": "RF path", "type": "RF", "targets": {"impedance_ohms": 50}, "notes": ""}]
        base["connectors"] = [{"name": "RF connector", "type": "SMA/U.FL", "external": True, "hotplug": True, "notes": ""}]
        base["risk_and_validation"]["explicit_exclusions"] = [
            "No antenna matching/tuning without measurements (VNA) or hard reference constraints.",
            "No RF certification / regulatory signoff.",
        ]
    elif lane == "automotive":
        base["power"]["rails"] = [
            {"name": "VBAT", "voltage_v": 12.0, "max_current_a": None, "notes": "Define load dump/cold crank specs."},
            {"name": "5V", "voltage_v": 5.0, "max_current_a": None, "notes": ""},
            {"name": "3V3", "voltage_v": 3.3, "max_current_a": None, "notes": ""},
        ]
        base["risk_and_validation"]["explicit_exclusions"] = [
            "No ISO 26262 process compliance unless explicitly contracted.",
            "No EMC/ESD certification testing (lab).",
        ]
    elif lane == "compliance":
        base["risk_and_validation"]["explicit_exclusions"] = [
            "No formal certification issuance; certification requires accredited lab testing.",
        ]

    return base


def compile_to_circuit_ai_hints(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert intake requirements into Circuit-AI 'hints' (best-effort).

    Circuit-AI currently supports hints such as `sources`, `loads_cc`, and `voltage_constraints`
    for the KiCad validation workflow.
    """
    rails = (req.get("power") or {}).get("rails") or []
    sources = (req.get("power") or {}).get("sources") or []
    loads = (req.get("power") or {}).get("loads") or []

    hint_sources: List[Dict[str, Any]] = []
    for s in sources:
        if isinstance(s, dict):
            hint_sources.append(
                {
                    "name": s.get("name") or "source",
                    "voltage_v": s.get("voltage_v"),
                    "max_current_a": s.get("max_current_a"),
                    "notes": s.get("notes") or "",
                }
            )

    loads_cc: List[Dict[str, Any]] = []
    for l in loads:
        if isinstance(l, dict):
            loads_cc.append(
                {
                    "name": l.get("name") or "load",
                    "rail": l.get("rail") or "",
                    "current_a": l.get("current_a"),
                    "notes": l.get("notes") or "",
                }
            )

    v_constraints: List[Dict[str, Any]] = []
    for r in rails:
        if isinstance(r, dict) and r.get("name") and r.get("voltage_v") is not None:
            v_constraints.append(
                {
                    "rail": r.get("name"),
                    "nominal_v": r.get("voltage_v"),
                    "min_v": r.get("min_v"),
                    "max_v": r.get("max_v"),
                    "notes": r.get("notes") or "",
                }
            )

    return {
        "sources": hint_sources,
        "loads_cc": loads_cc,
        "voltage_constraints": v_constraints,
    }


def build_questions_and_assumptions(req: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    lane = ((req.get("meta") or {}).get("lane") or "generic").strip()
    intent = ((req.get("meta") or {}).get("design_intent") or "prototype").strip()
    required = [
        "meta.project_name",
        "manufacturing.fab.name",
        "risk_and_validation.what_good_looks_like",
    ]
    if lane in ("rf", "compliance", "automotive", "power"):
        required += ["board.layers"]

    missing = _missing_fields(req, required)
    questions: List[str] = []
    assumptions: List[str] = []
    risks: List[str] = []

    for m in missing:
        questions.append(f"Please provide `{m}` (required to avoid guessing).")

    questions += [
        "What is the target PCB manufacturer (or at least their min trace/space/via rules)?",
        "Any mechanical constraints (enclosure, connectors placement, keepouts)?",
        "Is this a single-pass deliverable or an iterative revision loop?",
    ]

    if intent == "professional":
        questions += [
            "Are there any presentation/aesthetic requirements (board outline, silkscreen quality, labels, testpoints)?",
            "Do you have an enclosure/3D model and mounting hole requirements?",
        ]
    else:
        questions += [
            "Is this explicitly a prototype (OK if placement is utilitarian as long as it works)?",
            "Any constraints about reusing parts/wiring (flying leads, off-board components, tall parts allowed)?",
        ]

    if lane == "rf":
        questions += [
            "What impedance targets are required (50 ohm single-ended, 90/100 ohm diff)?",
            "Do you have the exact fab stackup (dielectric thickness, Er, copper thickness)?",
            "Do you have measurement capability (VNA), or should RF be treated as 'layout toward reference only'?",
        ]
        risks += [
            "RF performance cannot be guaranteed without constraints + measurements; treat as 'best-effort to reference design' unless VNA/targets are provided.",
        ]
    if lane == "power":
        questions += [
            "Provide max current per rail + transient requirements (startup, inrush, load step).",
            "Any thermal limits (ambient temp, enclosure, airflow)?",
            "Any EMI constraints (sensitive radios, conducted emissions target)?",
        ]
        risks += [
            "SMPS stability/EMI/thermal may require iteration and/or lab validation; scope accordingly.",
        ]
    if lane == "automotive":
        questions += [
            "Define input transients: load dump, cold crank, reverse battery, jump start specs.",
            "Define ESD/EMC targets (OEM requirements / ISO standards) if any.",
        ]
        risks += [
            "Automotive-grade robustness depends on transient specs; avoid implicit liability without explicit requirements.",
        ]
    if lane == "compliance":
        questions += [
            "What compliance targets apply (UL/IEC standard, CE directives, creepage/clearance requirements)?",
            "What is the working voltage category/pollution degree/environment?",
        ]
        risks += [
            "Compliance is a process; layout can be prepared toward targets but certification requires lab testing.",
        ]

    assumptions += [
        "Work proceeds iteratively: deliver Draft-1 quickly, collect client corrections, then converge to manufacturing package.",
        "Anything not provided as a requirement is treated as an open question and will be flagged, not silently assumed.",
    ]

    return questions, assumptions, risks


def render_sow(req: Dict[str, Any], questions: List[str], assumptions: List[str], risks: List[str]) -> str:
    meta = req.get("meta") or {}
    proj = meta.get("project_name") or "PROJECT"
    lane = meta.get("lane") or "generic"
    intent = meta.get("design_intent") or "prototype"
    excl = ((req.get("risk_and_validation") or {}).get("explicit_exclusions") or []) if isinstance(req.get("risk_and_validation"), dict) else []
    deliver = req.get("deliverables") or {}

    def yn(v: Any) -> str:
        return "yes" if bool(v) else "no"

    lines: List[str] = []
    lines.append(f"# SOW — {proj}")
    lines.append("")
    lines.append(f"- Lane: `{lane}`")
    lines.append(f"- Design intent: `{intent}`")
    lines.append(f"- Generated: `{_utc_now()}` (UTC)")
    lines.append("")
    lines.append("## Deliverables")
    lines.append(f"- Schematic: `{yn(deliver.get('schematic'))}`")
    lines.append(f"- PCB layout: `{yn(deliver.get('pcb_layout'))}`")
    lines.append(f"- BOM: `{yn(deliver.get('bom'))}`")
    lines.append(f"- Pick-and-place: `{yn(deliver.get('pnp'))}`")
    lines.append(f"- Gerbers: `{yn(deliver.get('gerbers'))}`")
    lines.append(f"- DFM memo: `{yn(deliver.get('dfm_memo'))}`")
    lines.append(f"- Bring-up notes: `{yn(deliver.get('bringup_notes'))}`")
    lines.append("")
    lines.append("## Open Questions (must answer to avoid guessing)")
    if questions:
        for q in questions[:60]:
            lines.append(f"- {q}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Assumptions")
    for a in assumptions:
        lines.append(f"- {a}")
    lines.append("")
    lines.append("## Risks / Validation Notes")
    for r in risks:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## Exclusions (explicit)")
    if excl:
        for e in excl:
            lines.append(f"- {e}")
    else:
        lines.append("- None listed")
    lines.append("")
    lines.append("## Acceptance Criteria (practical)")
    lines.append("- Deliverables package generated and reproducible (BOM/PnP/Gerbers/DFM memo).")
    lines.append("- Critical issues enumerated with proposed fixes; client confirms priorities for trade-offs.")
    lines.append("- Missing constraints are explicitly documented (no silent assumptions).")
    return "\n".join(lines).rstrip() + "\n"
