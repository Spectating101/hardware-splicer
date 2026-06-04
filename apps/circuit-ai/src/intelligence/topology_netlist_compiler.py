"""Compile measured topology evidence into deterministic simulation netlists.

The compiler is intentionally conservative. It only emits the current
`netlist_io` DC power-tree schema when topology evidence contains enough
low-voltage rail information to make a deterministic model. It records every
assumption and refuses hard-hazard topology instead of inventing a safe model.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.engines.netlist_io import netlist_from_dict
from src.intelligence.bench_topology_capture import bench_capture_to_topology_evidence, extract_bench_topology_capture
from src.intelligence.topology_evidence import extract_topology_evidence, topology_evidence_bridge


SCHEMA_VERSION = "topology_netlist_compiler.v1"
NETLIST_VERSION = 1
HARD_HAZARDS = {"power_ground_short", "high_voltage"}


def compile_topology_to_netlist(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Compile topology/bench evidence into a versioned DC power-tree netlist."""

    body = dict(payload or {})
    topology = _topology_from_payload(body)
    if not topology:
        return _unavailable("No topology_evidence.v1 or bench_topology_capture.v1 packet was supplied.")

    bridge = topology_evidence_bridge(topology)
    if not bridge.get("available"):
        return _unavailable("Topology evidence was present but did not contain connectors, nets, continuity, resistance, or voltage evidence.")

    normalized = bridge.get("topology_evidence") if isinstance(bridge.get("topology_evidence"), dict) else {}
    hazards = _hard_hazards(bridge)
    issues: List[Dict[str, Any]] = []
    if hazards:
        issues.extend(
            _issue(
                "critical",
                "topology_hazard",
                f"Topology hazard blocks netlist compilation: {hazard.get('hazard_id')}",
                str(hazard.get("clearance_requires") or "Resolve topology hazard before simulation or power."),
                source=str(hazard.get("source") or "topology_evidence.v1"),
            )
            for hazard in hazards
        )
        return _result(
            available=False,
            topology=normalized,
            bridge=bridge,
            netlist=None,
            constraints={},
            issues=issues,
            source="blocked_topology_hazard",
            coverage=_coverage(False, False, False, False),
            load_envelope=_empty_load_envelope("Topology hazard blocks load-envelope generation."),
        )

    power_pins, ground_pins = _power_and_ground_pins(normalized)
    if not ground_pins:
        issues.append(
            _issue(
                "error",
                "ground_reference_missing",
                "No measured or referenced ground pin was available for the DC model.",
                "Measure connector ground continuity before compiling a simulation netlist.",
                source="topology_evidence.v1",
            )
        )
    if not power_pins:
        issues.append(
            _issue(
                "error",
                "power_rail_missing",
                "No power pin with a voltage was available for the DC model.",
                "Measure or supply a low-voltage rail before compiling a simulation netlist.",
                source="topology_evidence.v1",
            )
        )

    voltage_sources = _voltage_sources(power_pins)
    voltage_constraints = _voltage_constraints(power_pins)
    loads_cc, load_issues = _constant_current_loads(body, normalized, power_pins)
    issues.extend(load_issues)
    traces, trace_issues = _traces(body, normalized)
    issues.extend(trace_issues)
    ldos, ldo_issues = _ldos(body, normalized)
    issues.extend(ldo_issues)

    netlist = _empty_netlist()
    netlist["voltage_sources"] = voltage_sources
    netlist["voltage_constraints"] = voltage_constraints
    netlist["loads_cc"] = loads_cc
    netlist["traces"] = traces
    netlist["ldos"] = ldos

    constraints = _constraints(body, normalized, voltage_sources)
    load_envelope = _load_envelope(body, power_pins, voltage_sources, constraints, loads_cc)

    available = bool(voltage_sources and ground_pins and not any(issue["severity"] in {"critical", "error"} for issue in issues if issue["issue_id"] != "load_model_missing"))
    simulation_ready = bool(available and loads_cc)
    if available:
        try:
            netlist_from_dict(netlist)
        except Exception as exc:
            issues.append(
                _issue(
                    "error",
                    "compiled_netlist_invalid",
                    "Compiled netlist did not pass schema validation.",
                    str(exc),
                    source="topology_netlist_compiler",
                )
            )
            available = False
            simulation_ready = False

    coverage = _coverage(bool(power_pins), bool(ground_pins), bool(loads_cc), bool(voltage_constraints))
    return _result(
        available=available,
        topology=normalized,
        bridge=bridge,
        netlist=netlist if available else None,
        constraints=constraints,
        issues=issues,
        source="measured_topology" if not bridge.get("reference_only") else "reference_topology",
        coverage={**coverage, "simulation_ready": simulation_ready, "bounded_envelope_ready": bool(load_envelope.get("available"))},
        load_envelope=load_envelope,
    )


def _topology_from_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    topology = extract_topology_evidence(body)
    if topology:
        return topology
    capture = extract_bench_topology_capture(body)
    if capture:
        reference = body.get("reference_topology") if isinstance(body.get("reference_topology"), dict) else None
        return bench_capture_to_topology_evidence(capture, reference_topology=reference)
    analysis = body.get("analysis") if isinstance(body.get("analysis"), dict) else {}
    capture = extract_bench_topology_capture(analysis)
    if capture:
        reference = analysis.get("reference_topology") if isinstance(analysis.get("reference_topology"), dict) else None
        return bench_capture_to_topology_evidence(capture, reference_topology=reference)
    return {}


def _hard_hazards(bridge: Dict[str, Any]) -> List[Dict[str, Any]]:
    hazard_profile = bridge.get("hazard_profile") if isinstance(bridge.get("hazard_profile"), dict) else {}
    hazards = [row for row in hazard_profile.get("hazards") or [] if isinstance(row, dict)]
    return [
        hazard
        for hazard in hazards
        if str(hazard.get("hazard_id") or "") in HARD_HAZARDS
        or str(hazard.get("severity") or "").lower() in {"critical", "hard_stop", "unsupported"}
    ]


def _power_and_ground_pins(topology: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    power = []
    ground = []
    for connector in topology.get("connectors") or []:
        if not isinstance(connector, dict):
            continue
        for pin in connector.get("pins") or []:
            if not isinstance(pin, dict):
                continue
            role = str(pin.get("role") or "")
            if role == "ground":
                ground.append(pin)
            elif role == "power" and _first_number(pin.get("voltage")) is not None:
                power.append(pin)
    return power, ground


def _voltage_sources(power_pins: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_node: Dict[str, Dict[str, Any]] = {}
    for pin in power_pins:
        volts = _first_number(pin.get("voltage"))
        if volts is None:
            continue
        node = _node(pin.get("net") or pin.get("label") or pin.get("endpoint") or "VBUS")
        if abs(volts) > 60:
            continue
        current = by_node.get(node)
        if current is None or _pin_confidence(pin) > current["_confidence"]:
            by_node[node] = {
                "name": f"VS_{_safe_id(node).upper()}",
                "n_plus": node,
                "n_minus": "0",
                "volts": round(float(volts), 6),
                "_confidence": _pin_confidence(pin),
            }
    rows = []
    for row in by_node.values():
        rows.append({key: value for key, value in row.items() if not key.startswith("_")})
    return sorted(rows, key=lambda row: row["name"])[:8]


def _voltage_constraints(power_pins: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    seen = set()
    for pin in power_pins:
        nominal = _first_number(pin.get("voltage"))
        if nominal is None or abs(nominal) > 60:
            continue
        node = _node(pin.get("net") or pin.get("label") or pin.get("endpoint") or "VBUS")
        key = (node, round(float(nominal), 3))
        if key in seen:
            continue
        seen.add(key)
        min_v, max_v = _voltage_window(float(nominal))
        rows.append(
            {
                "name": f"{_safe_id(node)}_voltage_window",
                "node": node,
                "gnd": "0",
                "min_v": min_v,
                "max_v": max_v,
                "severity": "error",
            }
        )
    return rows[:12]


def _constant_current_loads(
    body: Dict[str, Any],
    topology: Dict[str, Any],
    power_pins: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    primary_node = _primary_power_node(power_pins)
    rows: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []

    for index, item in enumerate(_rows(body.get("load_models") or body.get("loads") or body.get("simulation_loads")), start=1):
        if not isinstance(item, dict):
            continue
        amps = _current_a(item.get("amps"), item.get("current_a"), item.get("ma"), unit=item.get("unit"))
        if amps is None:
            continue
        rows.append(
            {
                "name": _safe_id(item.get("name") or item.get("load_id") or f"explicit_load_{index}"),
                "node": _node(item.get("node") or item.get("net") or primary_node),
                "amps": round(amps, 6),
                "gnd": _node(item.get("gnd") or item.get("ground") or "0"),
                "min_v_off": _first_number(item.get("min_v_off")) or _default_min_v_off(_first_number(item.get("nominal_v"))),
            }
        )

    for index, row in enumerate(topology.get("current") or [], start=1):
        if not isinstance(row, dict) or row.get("failed"):
            continue
        amps = _current_a(row.get("value"), unit=row.get("unit"))
        if amps is None or amps <= 0:
            continue
        rows.append(
            {
                "name": _safe_id(row.get("target") or row.get("observation_id") or f"measured_current_{index}"),
                "node": _current_target_node(row, primary_node),
                "amps": round(amps, 6),
                "gnd": "0",
                "min_v_off": _default_min_v_off(_primary_power_voltage(power_pins)),
            }
        )

    for index, resource in enumerate(_resource_rows(body), start=1):
        ratings = resource.get("ratings") if isinstance(resource.get("ratings"), dict) else {}
        amps = _current_a(
            ratings.get("current_a"),
            ratings.get("steady_current_a"),
            ratings.get("max_current_a"),
            resource.get("current_a"),
            unit=ratings.get("unit"),
        )
        caps = set(resource.get("capabilities") or [])
        if amps is None or not (caps & {"motor_or_load", "fan_or_pump", "led_or_light", "speaker_or_audio", "display_or_ui"}):
            continue
        rows.append(
            {
                "name": _safe_id(resource.get("resource_id") or resource.get("name") or f"resource_load_{index}"),
                "node": primary_node,
                "amps": round(amps, 6),
                "gnd": "0",
                "min_v_off": _default_min_v_off(_first_number(ratings.get("voltage_v")) or _primary_power_voltage(power_pins)),
            }
        )

    rows = _dedupe_rows(rows, key_fields=("name", "node", "amps"))
    if not rows:
        issues.append(
            _issue(
                "warning",
                "load_model_missing",
                "No numeric load-current model was found.",
                "The compiler emitted rail constraints, but source-current and loaded voltage behavior need measured current or explicit load models.",
                source="topology_netlist_compiler",
            )
        )
    return rows[:12], issues


def _traces(body: Dict[str, Any], topology: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    candidates: List[Any] = []
    for key in ["traces", "interconnects", "connections"]:
        candidates.extend(_rows(body.get(key)))
        candidates.extend(_rows(topology.get(key)))
    design = body.get("design") if isinstance(body.get("design"), dict) else {}
    for key in ["traces", "interconnects", "connections"]:
        candidates.extend(_rows(design.get(key)))

    for index, item in enumerate(candidates, start=1):
        if not isinstance(item, dict):
            continue
        length = _first_number(item.get("length_m"), item.get("trace_length_m"))
        width = _first_number(item.get("width_m"), item.get("trace_width_m"))
        if length is None or width is None:
            continue
        if length <= 0 or width <= 0:
            issues.append(
                _issue(
                    "warning",
                    "trace_geometry_invalid",
                    "Trace geometry was ignored because length/width was not positive.",
                    str(item),
                    source="topology_netlist_compiler",
                )
            )
            continue
        rows.append(
            {
                "name": _safe_id(item.get("name") or item.get("trace_id") or f"trace_{index}"),
                "n1": _node(item.get("n1") or item.get("from") or item.get("node_a") or item.get("a") or "VBUS"),
                "n2": _node(item.get("n2") or item.get("to") or item.get("node_b") or item.get("b") or "LOAD"),
                "spec": {
                    "length_m": float(length),
                    "width_m": float(width),
                    "copper_oz": _first_number(item.get("copper_oz")) or 1.0,
                },
            }
        )
    return _dedupe_rows(rows, key_fields=("name", "n1", "n2"))[:16], issues


def _ldos(body: Dict[str, Any], topology: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    candidates: List[Any] = []
    for key in ["ldos", "regulators", "voltage_regulators"]:
        candidates.extend(_rows(body.get(key)))
        candidates.extend(_rows(topology.get(key)))
    design = body.get("design") if isinstance(body.get("design"), dict) else {}
    for key in ["ldos", "regulators", "voltage_regulators"]:
        candidates.extend(_rows(design.get(key)))

    for index, item in enumerate(candidates, start=1):
        if not isinstance(item, dict):
            continue
        vout = _first_number(item.get("vout_nom_v"), item.get("output_v"), item.get("vout"))
        vin_node = item.get("vin") or item.get("vin_node") or item.get("input_node")
        vout_node = item.get("vout_node") or item.get("output_node")
        if vout is None or not vin_node or not vout_node:
            continue
        rows.append(
            {
                "name": _safe_id(item.get("name") or item.get("id") or f"ldo_{index}"),
                "vin": _node(vin_node),
                "vout": _node(vout_node),
                "gnd": _node(item.get("gnd") or item.get("ground") or "0"),
                "vout_nom_v": float(vout),
                "dropout_v": _first_number(item.get("dropout_v")) or 0.3,
                "max_current_a": _first_number(item.get("max_current_a")) or 1.0,
                "quiescent_current_a": _first_number(item.get("quiescent_current_a")) or 0.001,
                "r_theta_ja_c_per_w": _first_number(item.get("r_theta_ja_c_per_w")) or 50.0,
                "tj_max_c": _first_number(item.get("tj_max_c")) or 125.0,
                "ambient_c": _first_number(item.get("ambient_c")) or 25.0,
            }
        )
    return _dedupe_rows(rows, key_fields=("name", "vin", "vout"))[:8], issues


def _constraints(body: Dict[str, Any], topology: Dict[str, Any], voltage_sources: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    raw = {}
    for key in ["simulation_constraints", "test_constraints", "power_tree_constraints", "constraints"]:
        if isinstance(body.get(key), dict):
            raw.update(body[key])
    source_limits = []
    for row in _rows(raw.get("source_limits") or raw.get("source_current_limits")):
        if isinstance(row, dict):
            name = row.get("source_name") or row.get("name") or row.get("source")
            amps = _current_a(row.get("max_current_a"), row.get("current_limit_a"), row.get("amps"), unit=row.get("unit"))
            if name and amps is not None:
                source_limits.append({"source_name": str(name), "max_current_a": round(amps, 6)})

    if not source_limits:
        limit = _explicit_current_limit(body, topology)
        if limit is not None:
            for source in voltage_sources[:4]:
                source_limits.append({"source_name": source["name"], "max_current_a": round(limit, 6)})

    constraints = {
        "source_limits": _dedupe_rows(source_limits, key_fields=("source_name",)),
        "max_trace_drop_v": _first_number(raw.get("max_trace_drop_v"), raw.get("trace_drop_limit_v")) or 0.25,
    }
    return constraints


def _load_envelope(
    body: Dict[str, Any],
    power_pins: Sequence[Dict[str, Any]],
    voltage_sources: Sequence[Dict[str, Any]],
    constraints: Dict[str, Any],
    loads_cc: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if loads_cc:
        measured_total = round(sum(float(row.get("amps") or 0.0) for row in loads_cc), 6)
        return {
            "available": True,
            "mode": "measured_load_model",
            "status": "measured_load_available",
            "measured_total_load_a": measured_total,
            "reason": "Numeric load current is already modeled; no provisional envelope is needed.",
            "scenarios": [],
            "pass_condition": "Use measured load simulation and source-limit checks.",
            "measurement_required": False,
        }

    source_limits = [row for row in constraints.get("source_limits") or [] if isinstance(row, dict)]
    if not source_limits:
        return _empty_load_envelope(
            "No source current limit was supplied, so the compiler cannot derive a bounded load envelope without guessing."
        )
    if not voltage_sources:
        return _empty_load_envelope("No voltage source was compiled, so a load envelope cannot be attached to a rail.")

    primary_source = voltage_sources[0]
    primary_limit = next(
        (row for row in source_limits if str(row.get("source_name") or "") == str(primary_source.get("name") or "")),
        source_limits[0],
    )
    max_current_a = _current_a(primary_limit.get("max_current_a"), primary_limit.get("current_limit_a"), primary_limit.get("amps"))
    nominal_v = _first_number(primary_source.get("volts")) or _primary_power_voltage(power_pins)
    if max_current_a is None or max_current_a <= 0:
        return _empty_load_envelope("The supplied source current limit was not numeric or positive.")

    recommended_current_a = round(max_current_a * 0.8, 6)
    node = _node(primary_source.get("n_plus") or _primary_power_node(power_pins))
    scenario_specs = [
        ("no_load", 0.0, "rail idle/no-load check"),
        ("quarter_budget", recommended_current_a * 0.25, "light provisional load"),
        ("half_budget", recommended_current_a * 0.5, "mid provisional load"),
        ("recommended_budget", recommended_current_a, "recommended maximum before measuring the real load"),
        ("absolute_limit", max_current_a, "absolute source limit; design should stay below this"),
    ]
    scenarios = [
        {
            "scenario_id": scenario_id,
            "node": node,
            "load_current_a": round(current_a, 6),
            "nominal_power_w": round((nominal_v or 0.0) * current_a, 6) if nominal_v is not None else None,
            "status": "informational" if current_a == 0 else "bounded_probe",
            "purpose": purpose,
        }
        for scenario_id, current_a, purpose in scenario_specs
    ]
    return {
        "available": True,
        "mode": "bounded_unknown_load",
        "status": "load_current_measurement_required",
        "source_name": primary_source.get("name"),
        "node": node,
        "nominal_voltage_v": nominal_v,
        "absolute_source_limit_a": round(max_current_a, 6),
        "recommended_max_load_a": recommended_current_a,
        "recommended_max_power_w": round((nominal_v or 0.0) * recommended_current_a, 6) if nominal_v is not None else None,
        "scenarios": scenarios,
        "pass_condition": (
            f"Measure the real load current and keep steady current <= {recommended_current_a}A "
            f"and startup/current-limit behavior <= {round(max_current_a, 6)}A on {primary_source.get('name')}."
        ),
        "measurement_required": True,
        "measurement_prompt": "Measure steady current and startup/inrush current with a current-limited supply before treating this topology-derived netlist as loaded proof.",
        "claim_boundary": "This envelope is a bounded capacity check, not evidence that the unknown real load is safe.",
    }


def _empty_load_envelope(reason: str) -> Dict[str, Any]:
    return {
        "available": False,
        "mode": "unavailable",
        "status": "not_available",
        "reason": reason,
        "scenarios": [],
        "measurement_required": True,
    }


def _explicit_current_limit(body: Dict[str, Any], topology: Dict[str, Any]) -> Optional[float]:
    for source in [body, body.get("constraints") if isinstance(body.get("constraints"), dict) else {}]:
        limit = _current_a(
            source.get("current_limit_a") if isinstance(source, dict) else None,
            source.get("source_current_limit_a") if isinstance(source, dict) else None,
            source.get("max_current_a") if isinstance(source, dict) else None,
            unit=source.get("unit") if isinstance(source, dict) else None,
        )
        if limit is not None:
            return limit
    for row in topology.get("current") or []:
        if not isinstance(row, dict):
            continue
        limit = _current_a(row.get("current_limit_a"), row.get("limit_a"), row.get("max_current_a"), unit=row.get("unit"))
        if limit is not None:
            return limit
    return None


def _coverage(has_power: bool, has_ground: bool, has_load: bool, has_constraints: bool) -> Dict[str, Any]:
    dimensions = {
        "power_rail": has_power,
        "ground_reference": has_ground,
        "load_model": has_load,
        "voltage_constraints": has_constraints,
    }
    score = sum(1 for value in dimensions.values() if value) / len(dimensions)
    return {
        "score": round(score, 3),
        "dimensions": dimensions,
    }


def _result(
    *,
    available: bool,
    topology: Dict[str, Any],
    bridge: Dict[str, Any],
    netlist: Optional[Dict[str, Any]],
    constraints: Dict[str, Any],
    issues: Sequence[Dict[str, Any]],
    source: str,
    coverage: Dict[str, Any],
    load_envelope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    authority = bridge.get("topology_authority") if isinstance(bridge.get("topology_authority"), dict) else {}
    return {
        "mode": "topology_netlist_compiler",
        "schema_version": SCHEMA_VERSION,
        "available": bool(available),
        "source": source,
        "reference_only": bool(bridge.get("reference_only")),
        "netlist": netlist or {},
        "constraints": constraints or {},
        "coverage": coverage,
        "load_envelope": load_envelope or _empty_load_envelope("Load envelope was not generated."),
        "issues": list(issues),
        "measurements_used": _measurements_used(bridge),
        "topology_authority": authority,
        "claim_boundary": (
            "Compiled netlists cover low-voltage measured rails, explicit load models, optional trace/regulator models, and voltage constraints only. "
            "Hidden nets, high-speed behavior, batteries, mains, and unmeasured loads remain outside this deterministic DC model."
        ),
    }


def _unavailable(reason: str) -> Dict[str, Any]:
    return {
        "mode": "topology_netlist_compiler",
        "schema_version": SCHEMA_VERSION,
        "available": False,
        "source": "unavailable",
        "reference_only": False,
        "netlist": {},
        "constraints": {},
        "coverage": _coverage(False, False, False, False),
        "load_envelope": _empty_load_envelope(reason),
        "issues": [_issue("info", "topology_unavailable", "Topology netlist compiler did not run.", reason, source="topology_netlist_compiler")],
        "measurements_used": [],
        "topology_authority": {},
        "claim_boundary": "No simulation model was compiled because no usable topology evidence was supplied.",
    }


def _measurements_used(bridge: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for row in bridge.get("measurement_rows") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "measurement_id": row.get("measurement_id"),
                "type": row.get("type"),
                "target": row.get("target"),
                "value": row.get("value"),
                "unit": row.get("unit"),
                "status": row.get("status"),
            }
        )
    return rows[:24]


def _empty_netlist() -> Dict[str, Any]:
    return {
        "version": NETLIST_VERSION,
        "resistors": [],
        "current_sources": [],
        "voltage_sources": [],
        "traces": [],
        "ldos": [],
        "loads_cc": [],
        "loads_cp": [],
        "voltage_constraints": [],
    }


def _issue(severity: str, issue_id: str, summary: str, detail: str, *, source: str) -> Dict[str, Any]:
    return {
        "severity": severity,
        "issue_id": issue_id,
        "summary": summary,
        "detail": detail,
        "source": source,
    }


def _primary_power_node(power_pins: Sequence[Dict[str, Any]]) -> str:
    if not power_pins:
        return "VBUS"
    pin = sorted(power_pins, key=lambda item: (_pin_confidence(item), _first_number(item.get("voltage")) or 0.0), reverse=True)[0]
    return _node(pin.get("net") or pin.get("label") or pin.get("endpoint") or "VBUS")


def _primary_power_voltage(power_pins: Sequence[Dict[str, Any]]) -> Optional[float]:
    if not power_pins:
        return None
    pin = sorted(power_pins, key=lambda item: (_pin_confidence(item), _first_number(item.get("voltage")) or 0.0), reverse=True)[0]
    return _first_number(pin.get("voltage"))


def _current_target_node(row: Dict[str, Any], fallback: str) -> str:
    text = " ".join(str(row.get(key) or "") for key in ["target", "from", "to", "notes"]).upper()
    for token in ["VBUS", "VCC", "VIN", "5V", "3V3", "3.3V", "12V", "24V"]:
        if token in text:
            return _node(token)
    return fallback


def _voltage_window(nominal: float) -> Tuple[float, float]:
    value = abs(float(nominal))
    if 3.0 <= value <= 3.6:
        return 3.0, 3.6
    if 4.5 <= value <= 5.5:
        return 4.5, 5.5
    if 10.5 <= value <= 13.5:
        return 10.8, 13.2
    if 22 <= value <= 26:
        return 21.6, 26.4
    tolerance = max(0.25, value * 0.10)
    return round(value - tolerance, 6), round(value + tolerance, 6)


def _default_min_v_off(nominal: Optional[float]) -> Optional[float]:
    if nominal is None:
        return None
    if nominal <= 3.6:
        return 2.7
    if nominal <= 5.5:
        return 3.0
    return round(float(nominal) * 0.7, 6)


def _resource_rows(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for key in ["available_resources", "resources", "owned_resources", "inventory", "modules", "available_parts"]:
        for row in _rows(body.get(key)):
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _pin_confidence(pin: Dict[str, Any]) -> float:
    return _first_number(pin.get("confidence")) or 0.5


def _node(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "NET"
    upper = text.upper().replace("+", "P").replace("-", "M")
    if upper in {"GND", "GROUND", "0V", "0"}:
        return "0"
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in upper).strip("_")
    aliases = {"3_3V": "3V3", "3V3": "3V3", "3_3": "3V3", "5V": "VBUS", "VCC": "VCC", "VBUS": "VBUS", "VIN": "VIN"}
    return aliases.get(cleaned, cleaned or "NET")


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:90] or "item"


def _rows(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return [value]
    return [value]


def _first_number(*values: Any) -> Optional[float]:
    for value in values:
        if value is None or value == "":
            continue
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        try:
            return float(text)
        except ValueError:
            chars = []
            started = False
            for ch in text:
                if ch.isdigit() or ch in {".", "-", "+"}:
                    chars.append(ch)
                    started = True
                elif started:
                    break
            if chars:
                try:
                    return float("".join(chars))
                except ValueError:
                    continue
    return None


def _current_a(*values: Any, unit: Any = None) -> Optional[float]:
    value = _first_number(*values)
    if value is None:
        return None
    unit_text = str(unit or " ".join(str(item or "") for item in values)).lower()
    if "ua" in unit_text or "microamp" in unit_text:
        return value / 1_000_000
    if "ma" in unit_text or "milliamp" in unit_text:
        return value / 1000
    if "amp" in unit_text or unit_text.strip() == "a":
        return value
    if value > 10:
        return value / 1000
    return value


def _dedupe_rows(rows: Sequence[Dict[str, Any]], *, key_fields: Sequence[str]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = tuple(str(row.get(field) or "").lower() for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept
