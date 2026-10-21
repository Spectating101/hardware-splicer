"""Evidence-linked device splicing screen, not a physical build approval."""
from __future__ import annotations

import math
from collections.abc import Mapping

SCHEMA = "hardware_splicer.device_splice_feasibility.v1"
DOMAINS = frozenset({"power", "signal", "mechanical", "firmware", "thermal"})

def _number(row: Mapping, key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"invalid {key} value")
    return float(value)

def _range(row: Mapping, low: str, high: str):
    a, b = _number(row, low), _number(row, high)
    if a is not None and b is not None and a > b:
        raise ValueError("reversed interface voltage range")
    return a, b

def _comparison(domain: str, provided: Mapping, required: Mapping) -> tuple[str, list[str]]:
    if domain == "power":
        amin, amax = _range(provided, "voltage_min_v", "voltage_max_v")
        bmin, bmax = _range(required, "voltage_min_v", "voltage_max_v")
        have = _number(provided, "current_max_a")
        need = _number(required, "current_required_a")
        if None in (amin, amax, bmin, bmax, have, need):
            return "unknown", ["Voltage range or current capability not established"]
        issues = []
        if not (bmin <= amin <= amax <= bmax):
            issues.append("Supply voltage envelope outside consumer input envelope")
        if have < need:
            issues.append("Source current rating below required load")
        return ("blocked", issues) if issues else ("compatible_on_paper", [])
    if domain == "signal":
        a, b = provided.get("protocol"), required.get("protocol")
        av, bv = _number(provided, "logic_voltage_v"), _number(required, "logic_voltage_v")
        if not a or not b or av is None or bv is None:
            return "unknown", ["Signal protocol or logic voltage missing"]
        issues = []
        if a != b:
            issues.append("Signal protocol mismatch")
        if abs(av - bv) > 1e-6:
            issues.append("Signal logic-level mismatch")
        return ("blocked", issues) if issues else ("compatible_on_paper", [])
    if domain == "mechanical":
        form = provided.get("form_factor")
        choices = required.get("accepted_form_factors")
        if not isinstance(form, str) or not isinstance(choices, list) or not choices:
            return "unknown", ["Mechanical form factor or mounting constraints missing"]
        if form not in choices:
            return "blocked", ["Mechanical form factor does not match specified mount"]
        return "compatible_on_paper", []
    if domain == "firmware":
        driver = required.get("driver_available")
        if driver is True:
            return "compatible_on_paper", []
        if driver is False:
            return "blocked", ["Firmware driver absent"]
        return "unknown", ["Firmware driver availability unverified"]
    if domain == "thermal":
        dissipated = _number(provided, "dissipation_w")
        capacity = _number(required, "cooling_capacity_w")
        if dissipated is None or capacity is None:
            return "unknown", ["Heat dissipation or thermal capacity unknown"]
        return ("blocked", ["Estimated heat dissipation exceeds stated cooling capacity"]) if dissipated > capacity else ("compatible_on_paper", [])
    raise ValueError("unknown interface domain")

def _adapter_status(domain, adapter, provided, required, evidence_ids):
    if not isinstance(adapter, Mapping):
        return False
    if not adapter.get("id") or not adapter.get("description") or not adapter.get("evidence_refs"):
        return False
    if any(ref not in evidence_ids for ref in adapter["evidence_refs"]):
        return False
    if domain == "power" and adapter.get("kind") == "voltage_regulator":
        a1, a2 = _range(provided, "voltage_min_v", "voltage_max_v")
        i1, i2 = _range(adapter, "input_voltage_min_v", "input_voltage_max_v")
        o1, o2 = _range(adapter, "output_voltage_min_v", "output_voltage_max_v")
        b1, b2 = _range(required, "voltage_min_v", "voltage_max_v")
        amp = _number(adapter, "output_current_max_a")
        load = _number(required, "current_required_a")
        source_amp = _number(provided, "current_max_a")
        input_amp = _number(adapter, "input_current_required_a")
        efficiency = _number(adapter, "efficiency_fraction")
        if None in (a1, a2, i1, i2, o1, o2, b1, b2, amp, load, source_amp, input_amp, efficiency):
            return False
        return (0 < efficiency <= 1.0 and i1 <= a1 <= a2 <= i2
                and b1 <= o1 <= o2 <= b2 and amp >= load
                and source_amp >= input_amp and a1 * input_amp * efficiency >= b2 * load)
    if domain == "signal" and adapter.get("kind") == "protocol_or_level_adapter":
        return (adapter.get("input_protocol") == provided.get("protocol")
                and adapter.get("output_protocol") == required.get("protocol")
                and _number(adapter, "input_logic_voltage_v") == _number(provided, "logic_voltage_v")
                and _number(adapter, "output_logic_voltage_v") == _number(required, "logic_voltage_v"))
    if domain == "mechanical" and adapter.get("kind") == "mounting_adapter":
        return (adapter.get("input_form_factor") == provided.get("form_factor")
                and adapter.get("output_form_factor") in required.get("accepted_form_factors", []))
    return False

def assess_device_splice(candidate: Mapping) -> dict:
    if not isinstance(candidate, Mapping) or candidate.get("schema") != "hardware_splicer.device_splice_candidate.v1":
        raise ValueError("unsupported device splice candidate")
    if not isinstance(candidate.get("id"), str) or not candidate["id"].strip():
        raise ValueError("candidate id required")
    parts, interfaces, evidence = (candidate.get(k) for k in ("components", "interfaces", "evidence"))
    if (not isinstance(parts, list) or not isinstance(interfaces, list)
            or not isinstance(evidence, list) or len(parts) > 64
            or not 1 <= len(interfaces) <= 64 or len(evidence) > 128):
        raise ValueError("bounded components, interfaces and evidence required")
    part_ids = [p.get("id") for p in parts if isinstance(p, Mapping)]
    if (len(part_ids) != len(parts) or any(not isinstance(p, str) or not p for p in part_ids)
            or len(set(part_ids)) != len(part_ids)):
        raise ValueError("invalid or duplicate component identifiers")
    ev_ids = []
    for row in evidence:
        if (not isinstance(row, Mapping) or not row.get("id") or not row.get("locator")
                or row.get("basis") not in ("user_declared", "source_document", "bench_measurement")):
            raise ValueError("evidence needs id, locator and basis")
        ev_ids.append(row["id"])
    if len(set(ev_ids)) != len(ev_ids):
        raise ValueError("duplicate evidence IDs")
    known = set(ev_ids)
    checks, interface_ids = [], set()
    for item in interfaces:
        if not isinstance(item, Mapping):
            raise ValueError("invalid interface")
        ident, domain = item.get("id"), item.get("domain")
        if (not isinstance(ident, str) or not ident or ident in interface_ids
                or domain not in DOMAINS):
            raise ValueError("duplicate, missing or unknown interface")
        interface_ids.add(ident)
        if item.get("from") not in part_ids or item.get("to") not in part_ids:
            raise ValueError("interface references unknown component")
        provided, required = item.get("provided") or {}, item.get("required") or {}
        if not isinstance(provided, Mapping) or not isinstance(required, Mapping):
            raise ValueError("interface attributes must be objects")
        refs = item.get("evidence_refs") or []
        if not isinstance(refs, list) or any(ref not in known for ref in refs):
            raise ValueError("unresolvable evidence reference")
        status, issues = _comparison(domain, provided, required)
        if not refs:
            status, issues = "unknown", [*issues, "Traceable source evidence absent"]
        elif status == "blocked" and _adapter_status(domain, item.get("adaptation"), provided, required, known):
            status = "adaptable_pending_validation"
            issues = [*issues, "Declared adapter requires independent specification, fit and bench verification"]
        checks.append({"id": ident, "domain": domain, "from": item["from"], "to": item["to"],
                       "status": status, "findings": issues, "evidence_refs": refs,
                       "adaptation_id": item.get("adaptation", {}).get("id") if status == "adaptable_pending_validation" else None,
                       "verification_level": "declared_specification_only"})
    # Rail aggregation requires explicitly declared shared-rail identity.
    rails = {}
    for item in interfaces:
        if item["domain"] != "power":
            continue
        rail = item.get("provided", {}).get("rail_id")
        if rail:
            rails.setdefault((item["from"], str(rail)), []).append(item)
    for (supplier, rail), loads in rails.items():
        if len(loads) < 2:
            continue
        readings = [_number(item["provided"], "current_max_a") for item in loads]
        total = None
        if any(value is None for value in readings) or max(readings) - min(readings) > 1e-6:
            state, notes = "unknown", ["Shared supply current rating absent or inconsistent"]
        else:
            consumed = []
            for item in loads:
                adapter = item.get("adaptation")
                if isinstance(adapter, Mapping):
                    consumed.append(_number(adapter, "input_current_required_a"))
                else:
                    consumed.append(_number(item["required"], "current_required_a"))
            if any(value is None for value in consumed):
                state, notes = "unknown", ["Aggregate rail demand unresolved (adapter input or load current missing)"]
            else:
                total = sum(consumed)
                state = "blocked" if total > readings[0] + 1e-9 else "compatible_on_paper"
                notes = (["Aggregate current demand exceeds declared source rating"]
                         if state == "blocked" else
                         ["Aggregate declared rail current budget within stated rating; bench test required"])
        checks.append({"id": f"rail_budget:{supplier}:{rail}", "domain": "power_aggregate",
                       "from": supplier, "to": ",".join(item["to"] for item in loads),
                       "status": state, "findings": notes,
                       "source_rating_a": readings[0] if readings and readings[0] is not None else None,
                       "aggregate_required_a": total,
                       "evidence_refs": sorted(set(ref for item in loads for ref in item.get("evidence_refs", []))),
                       "adaptation_id": None, "verification_level": "declared_shared_rail_budget"})
    fit = candidate.get("electromechanical_fit")
    if fit is not None:
        if not isinstance(fit, Mapping) or fit.get("schema") != "hardware_splicer.electromechanical_envelope_fit.v1":
            raise ValueError("unsupported electrical/mechanical fit report")
        if fit.get("status") == "envelope_collision_detected" and fit.get("blocker_count", 0) > 0:
            checks.append({"id": "physical_assembly_fit", "domain": "assembly", "status": "blocked",
                           "findings": ["Component-envelope collisions detected"],
                           "evidence_refs": [], "verification_level": "approximate_geometry"})
        elif (fit.get("status") == "envelope_screen_clear_unverified"
              and fit.get("blocker_count") == 0 and fit.get("exact_3d_collision_verified") is False):
            checks.append({"id": "physical_assembly_fit", "domain": "assembly", "status": "compatible_on_paper",
                           "findings": ["Envelope screen clear; exact solid collision and physical fit not verified"],
                           "evidence_refs": [], "verification_level": "approximate_geometry"})
        else:
            raise ValueError("inconsistent fit report")
    required_domains = candidate.get("required_domains", sorted(DOMAINS | {"assembly"}))
    if (not isinstance(required_domains, list) or not required_domains
            or any(not isinstance(domain, str) or domain not in DOMAINS | {"assembly"} for domain in required_domains)
            or len(set(required_domains)) != len(required_domains)):
        raise ValueError("invalid required domain coverage")
    covered = {check["domain"] for check in checks}
    for domain in required_domains:
        if domain not in covered:
            checks.append({"id": f"missing_domain:{domain}", "domain": domain, "status": "unknown",
                           "findings": [f"No {domain} subsystem evidence supplied"],
                           "evidence_refs": [], "verification_level": "missing_scope"})
    states = {row["status"] for row in checks}
    overall = next((status for status in ("blocked", "unknown", "adaptable_pending_validation", "compatible_on_paper")
                    if status in states), "unknown")
    tasks = []
    labels = {"blocked": "Redesign or replace incompatible interface",
              "unknown": "Obtain missing specifications or test evidence",
              "adaptable_pending_validation": "Validate proposed adapter design and bench-test interface"}
    for row in checks:
        if row["status"] == "compatible_on_paper":
            continue
        tasks.append({"interface_id": row["id"], "status": "proposed_not_executed",
                      "action": f"{labels[row['status']]}: {row['id']}",
                      "reason": "; ".join(row["findings"])})
    return {"schema": SCHEMA, "candidate_id": candidate["id"], "overall_status": overall,
            "checks": checks, "required_actions": tasks,
            "source_evidence_authentication_performed": False,
            "electrical_operation_verified": False, "exact_mechanical_assembly_verified": False,
            "fabrication_authorized": False, "power_on_authorized": False, "release_authorized": False}
