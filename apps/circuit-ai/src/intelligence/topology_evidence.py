"""Bridge measured topology evidence into hardware planning inputs.

This adapter is intentionally structured-input first. Vision can propose parts;
topology evidence comes from continuity, voltage, pinout, and net observations.
It can close matching measurement gates when the evidence is explicit, but it
cannot clear hazards produced by other evidence sources.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence


SCHEMA_VERSION = "topology_evidence_bridge.v1"

PASS_STATUSES = {"pass", "passed", "ok", "closed", "verified", "measured", "normal"}
FAIL_STATUSES = {"fail", "failed", "unsafe", "short", "shorted", "blocked", "open_unexpected"}
TRUST_KEYS = ("instrument_id", "instrument_type", "calibration_status", "recorded_at", "operator_id", "evidence_uri")


def enrich_payload_with_topology_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of payload with measured topology evidence bridged in."""

    body = dict(payload or {})
    evidence = extract_topology_evidence(body)
    if not evidence:
        return body

    bridge = topology_evidence_bridge(evidence)
    if not bridge.get("available"):
        return body

    analysis = dict(body.get("analysis") if isinstance(body.get("analysis"), dict) else {})
    analysis.setdefault("mode", "topology_evidence")
    analysis["topology_evidence"] = bridge["topology_evidence"]
    analysis["topology_evidence_bridge"] = bridge
    analysis["topology_authority"] = bridge["topology_authority"]

    machine = dict(analysis.get("machine_connection_map") if isinstance(analysis.get("machine_connection_map"), dict) else {})
    machine["mode"] = "machine_connection_map"
    machine["connector_maps"] = _dedupe_rows(
        _list_dicts(machine.get("connector_maps")) + bridge["connector_maps"],
        key_fields=("connector_id",),
    )
    machine["connector_count"] = max(int(machine.get("connector_count") or 0), len(machine["connector_maps"]))
    machine["interfaces"] = _dedupe_rows(
        _list_dicts(machine.get("interfaces")) + bridge["interfaces"],
        key_fields=("type", "connector_ref", "net"),
    )
    raw_splice = dict(machine.get("splice_plan") if isinstance(machine.get("splice_plan"), dict) else {})
    raw_splice["safest_entry_points"] = _dedupe(
        _string_list(raw_splice.get("safest_entry_points")) + bridge["safest_entry_points"]
    )[:12]
    raw_splice["required_measurements"] = _dedupe(
        _string_list(raw_splice.get("required_measurements")) + bridge["required_measurements"]
    )[:18]
    raw_splice["topology_authority"] = {
        "pinout_known": bridge["topology_authority"].get("pinout_known"),
        "shorts_detected": bridge["topology_authority"].get("shorts_detected"),
        "measurement_backed": bridge["topology_authority"].get("measurement_backed"),
    }
    raw_splice["pin_level_splice_contracts"] = bridge.get("pin_level_splice_contracts") or []
    machine["splice_plan"] = raw_splice
    machine["limitations"] = _dedupe(
        _string_list(machine.get("limitations"))
        + [
            "Measured topology closes only matching gates; hidden nets and unmeasured pins remain gated.",
            "Do not override safety holds from visual damage, batteries, mains, high voltage, or failed continuity.",
        ]
    )[:8]
    analysis["machine_connection_map"] = machine

    body["analysis"] = analysis
    body["available_resources"] = _dedupe_rows(
        _list_dicts(body.get("available_resources")) + bridge["resource_candidates"],
        key_fields=("resource_id",),
    )
    body["measurements"] = _dedupe_rows(
        _list_dicts(body.get("measurements")) + bridge["measurement_rows"],
        key_fields=("measurement_id", "type", "target", "value"),
    )
    body["hazard_profile"] = _merge_hazard_profiles(
        body.get("hazard_profile") if isinstance(body.get("hazard_profile"), dict) else {},
        bridge["hazard_profile"],
    )
    body["topology_evidence_bridge"] = bridge
    return body


def extract_topology_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Find a topology_evidence.v1-style object in common payload shapes."""

    for root in _candidate_roots(payload):
        if not isinstance(root, dict):
            continue
        evidence = root.get("topology_evidence")
        if isinstance(evidence, dict):
            return evidence
        if str(root.get("schema_version") or "") == "topology_evidence.v1":
            return root
        continuity_map = root.get("continuity_map")
        if isinstance(continuity_map, dict):
            return {"schema_version": "topology_evidence.v1", **continuity_map}
        pinout = root.get("pinout_evidence")
        if isinstance(pinout, dict):
            return {"schema_version": "topology_evidence.v1", "connectors": [pinout]}
    return {}


def topology_evidence_bridge(topology_evidence: Dict[str, Any]) -> Dict[str, Any]:
    evidence = _normalize_topology_evidence(topology_evidence)
    reference_only = _reference_only(evidence)
    connectors = evidence.get("connectors") or []
    nets = _derived_nets(evidence)
    continuity = evidence.get("continuity") or []
    resistance = evidence.get("resistance") or []
    voltage = evidence.get("voltage") or []
    current = evidence.get("current") or []
    thermal = evidence.get("thermal") or []
    hazards = _hazard_candidates(evidence, connectors, nets, continuity, resistance, voltage)
    connector_maps = _connector_maps(connectors)
    interfaces = _interfaces(connectors, nets, voltage)
    measurements = [] if reference_only else _measurement_rows(evidence, connectors, continuity, resistance, voltage, current, thermal)
    resources = _resource_candidates(connectors, interfaces, hazards, reference_only=reference_only)
    pin_contracts = [] if reference_only else _pin_level_splice_contracts(connectors, interfaces, hazards)
    authority = _topology_authority(connectors, nets, measurements, hazards, reference_only=reference_only)
    return {
        "schema_version": SCHEMA_VERSION,
        "available": bool(connectors or nets or continuity or resistance or voltage),
        "source": "public_reference_topology" if reference_only else "measured_topology_evidence",
        "reference_only": reference_only,
        "topology_evidence": {**evidence, "nets": nets, "hazards": hazards},
        "connector_maps": connector_maps,
        "interfaces": interfaces,
        "pin_level_splice_contracts": pin_contracts,
        "safest_entry_points": [
            row["connector_id"]
            for row in connector_maps
            if not reference_only
            and row.get("confidence", 0.0) >= 0.65
            and "unknown_external_interface" not in row.get("likely_roles", [])
        ][:8],
        "required_measurements": _required_measurements(connectors, interfaces, hazards),
        "measurement_rows": measurements,
        "resource_candidates": resources,
        "hazard_profile": {
            "schema_version": "hardware_hazard_profile.v1",
            "energy_domain": _energy_domain(hazards, connectors, voltage),
            "hazards": hazards,
            "clearance_requirements": _dedupe(
                hazard.get("clearance_requires")
                for hazard in hazards
                if hazard.get("clearance_requires")
            )[:12],
            "source_policy": {
                "structured_sources": ["topology_evidence.v1"],
                "raw_text_release_logic": False,
                "topology_can_close_measurement_gates": True,
                "topology_cannot_clear_external_hazards": True,
            },
        },
        "topology_authority": authority,
        "policy": {
            "structured_topology_is_measurement_evidence": True,
            "public_reference_topology_requires_bench_confirmation": reference_only,
            "failed_topology_blocks_power_or_splice": True,
            "unmeasured_pins_remain_gated": True,
            "release_decision_remains_in_hardware_plan_authority": True,
        },
    }


def _candidate_roots(payload: Dict[str, Any]) -> List[Any]:
    roots: List[Any] = [payload]
    for key in ["analysis", "results", "circuit", "topology", "machine_connection_map"]:
        value = payload.get(key)
        if isinstance(value, dict):
            roots.append(value)
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    for key in ["topology", "machine_connection_map"]:
        value = analysis.get(key)
        if isinstance(value, dict):
            roots.append(value)
    return roots


def _normalize_topology_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    root_provenance = _provenance(evidence, {})
    connectors = [
        _normalize_connector(item, index, root_provenance)
        for index, item in enumerate(_rows(evidence.get("connectors")), start=1)
    ]
    nets = [_normalize_net(item, index, root_provenance) for index, item in enumerate(_rows(evidence.get("nets")), start=1)]
    continuity = [
        _normalize_observation(item, "continuity", index, root_provenance)
        for index, item in enumerate(_rows(evidence.get("continuity") or evidence.get("continuity_tests")), start=1)
    ]
    resistance = [
        _normalize_observation(item, "resistance", index, root_provenance)
        for index, item in enumerate(_rows(evidence.get("resistance") or evidence.get("resistance_tests")), start=1)
    ]
    voltage = [
        _normalize_observation(item, "voltage", index, root_provenance)
        for index, item in enumerate(_rows(evidence.get("voltage") or evidence.get("voltage_tests")), start=1)
    ]
    current = [
        _normalize_observation(item, "current", index, root_provenance)
        for index, item in enumerate(_rows(evidence.get("current") or evidence.get("current_tests")), start=1)
    ]
    thermal = [
        _normalize_observation(item, "thermal", index, root_provenance)
        for index, item in enumerate(_rows(evidence.get("thermal") or evidence.get("thermal_tests")), start=1)
    ]
    return {
        "schema_version": "topology_evidence.v1",
        "connectors": connectors,
        "nets": nets,
        "continuity": continuity,
        "resistance": resistance,
        "voltage": voltage,
        "current": current,
        "thermal": thermal,
        "source": str(evidence.get("source") or "topology_evidence.v1"),
        "source_type": str(evidence.get("source_type") or evidence.get("evidence_type") or ""),
        "reference_uri": str(evidence.get("reference_uri") or evidence.get("source_uri") or ""),
        "provenance": root_provenance,
    }


def _reference_only(evidence: Dict[str, Any]) -> bool:
    text = " ".join(
        str(value or "")
        for value in [
            evidence.get("source"),
            evidence.get("source_type"),
            evidence.get("reference_uri"),
            (evidence.get("provenance") or {}).get("evidence_uri") if isinstance(evidence.get("provenance"), dict) else "",
        ]
    ).lower()
    return any(term in text for term in ["public_reference", "reference_topology", "public schematic", "datasheet", "official_pinout"])


def _normalize_connector(item: Any, index: int, root_provenance: Dict[str, Any]) -> Dict[str, Any]:
    row = item if isinstance(item, dict) else {"ref": f"J{index}", "label": str(item)}
    ref = str(row.get("ref") or row.get("id") or row.get("connector_id") or f"J{index}").strip()
    pins = [
        _normalize_pin(pin, pin_index, ref, _provenance(pin if isinstance(pin, dict) else {}, _provenance(row, root_provenance)))
        for pin_index, pin in enumerate(_pin_rows(row), start=1)
    ]
    return {
        "ref": ref,
        "connector_id": _safe_id(f"topology_{ref}"),
        "label": str(row.get("label") or row.get("name") or ref),
        "kind": str(row.get("kind") or row.get("type") or "connector"),
        "pin_count": _safe_int(row.get("pin_count"), len(pins)),
        "pins": pins,
        "status": _status(row),
        "confidence": round(max(0.35, min(_safe_float(row.get("confidence"), 0.82 if pins else 0.58), 0.96)), 3),
        "provenance": _provenance(row, root_provenance),
    }


def _pin_rows(connector: Dict[str, Any]) -> List[Any]:
    value = connector.get("pins") or connector.get("pinout") or connector.get("pin_map")
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        rows = []
        for pin, raw in value.items():
            if isinstance(raw, dict):
                rows.append({"pin": pin, **raw})
            else:
                rows.append({"pin": pin, "net": raw})
        return rows
    return []


def _normalize_pin(item: Any, index: int, connector_ref: str, provenance: Dict[str, Any]) -> Dict[str, Any]:
    row = item if isinstance(item, dict) else {"pin": index, "label": str(item)}
    pin = str(row.get("pin") or row.get("number") or row.get("pin_number") or index)
    net = str(row.get("net") or row.get("net_id") or row.get("node") or row.get("label") or "").strip()
    role = _role(row.get("role") or row.get("function") or row.get("kind") or net or row.get("label"))
    voltage = _first_number(row.get("voltage") or row.get("nominal_v") or row.get("measured_voltage"))
    logic_voltage = _first_number(row.get("logic_voltage") or row.get("idle_voltage") or row.get("measured_logic_voltage"))
    return {
        "endpoint": _endpoint(connector_ref, pin),
        "connector_ref": connector_ref,
        "pin": pin,
        "label": str(row.get("label") or net or pin),
        "net": net,
        "role": role,
        "voltage": voltage,
        "logic_voltage": logic_voltage,
        "status": _status(row),
        "confidence": round(max(0.35, min(_safe_float(row.get("confidence"), 0.82), 0.97)), 3),
        "provenance": provenance,
    }


def _normalize_net(item: Any, index: int, root_provenance: Dict[str, Any]) -> Dict[str, Any]:
    row = item if isinstance(item, dict) else {"net": str(item)}
    net = str(row.get("net") or row.get("net_id") or row.get("name") or f"NET_{index}").strip()
    nodes = _string_list(row.get("nodes") or row.get("endpoints"))
    role = _role(row.get("role") or row.get("kind") or net)
    return {
        "net": net,
        "role": role,
        "nodes": nodes,
        "nominal_v": _first_number(row.get("nominal_v") or row.get("voltage")),
        "status": _status(row),
        "provenance": _provenance(row, root_provenance),
    }


def _normalize_observation(item: Any, kind: str, index: int, root_provenance: Dict[str, Any]) -> Dict[str, Any]:
    row = item if isinstance(item, dict) else {"target": str(item), "result": "pass"}
    result = str(row.get("result") or row.get("status") or row.get("value") or "").strip().lower()
    value = row.get("value", row.get("reading", row.get("result")))
    passed = _truthy(row.get("passed")) or result in PASS_STATUSES
    failed = _truthy(row.get("failed")) or result in FAIL_STATUSES
    return {
        "observation_id": str(row.get("observation_id") or row.get("measurement_id") or row.get("id") or f"{kind}_{index}"),
        "kind": kind,
        "from": str(row.get("from") or row.get("a") or row.get("node_a") or "").strip(),
        "to": str(row.get("to") or row.get("b") or row.get("node_b") or "").strip(),
        "target": str(row.get("target") or row.get("net") or row.get("pin") or "").strip(),
        "value": value,
        "unit": str(row.get("unit") or row.get("units") or _default_unit(kind)),
        "notes": str(row.get("notes") or row.get("summary") or row.get("purpose") or ""),
        "passed": bool(passed and not failed),
        "failed": bool(failed),
        "provenance": _provenance(row, root_provenance),
    }


def _derived_nets(evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
    nets = list(evidence.get("nets") or [])
    by_name = {str(row.get("net") or "").lower(): row for row in nets if row.get("net")}
    for connector in evidence.get("connectors") or []:
        for pin in connector.get("pins") or []:
            net_name = str(pin.get("net") or "").strip()
            if not net_name:
                continue
            key = net_name.lower()
            node = pin.get("endpoint")
            if key not in by_name:
                by_name[key] = {
                    "net": net_name,
                    "role": pin.get("role") or _role(net_name),
                    "nodes": [node] if node else [],
                    "nominal_v": pin.get("voltage") or pin.get("logic_voltage"),
                    "status": pin.get("status"),
                    "provenance": pin.get("provenance") or {},
                }
                nets.append(by_name[key])
            elif node and node not in by_name[key].setdefault("nodes", []):
                by_name[key]["nodes"].append(node)
    return nets


def _connector_maps(connectors: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for connector in connectors:
        pins = connector.get("pins") or []
        roles = sorted({pin.get("role") for pin in pins if pin.get("role")})
        unknown = len([pin for pin in pins if pin.get("role") in {"unknown", ""}])
        rows.append(
            {
                "connector_id": connector.get("connector_id"),
                "connector_ref": connector.get("ref"),
                "class_name": connector.get("kind") or "connector",
                "estimated_pin_count": connector.get("pin_count") or len(pins),
                "labels": _dedupe([pin.get("label") or pin.get("net") or pin.get("pin") for pin in pins])[:16],
                "pin_map": [
                    {
                        "pin": pin.get("pin"),
                        "net": pin.get("net"),
                        "role": pin.get("role"),
                        "voltage": pin.get("voltage"),
                        "logic_voltage": pin.get("logic_voltage"),
                        "status": pin.get("status"),
                    }
                    for pin in pins
                ],
                "likely_roles": _likely_connector_roles(pins),
                "candidate_pin_groups": _pin_groups(pins),
                "unknown_pin_count": unknown,
                "confidence": connector.get("confidence", 0.0),
                "recommended_next_photo": "connector pinout close-up" if unknown else "first-power setup photo",
            }
        )
    return rows


def _interfaces(connectors: Sequence[Dict[str, Any]], nets: Sequence[Dict[str, Any]], voltage: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for connector in connectors:
        pins = connector.get("pins") or []
        roles = {pin.get("role") for pin in pins}
        ref = connector.get("ref")
        if {"power", "ground"} <= roles:
            rows.append(_interface("power", ref, pins, ["confirm current limit", "verify polarity"]))
        if {"uart_tx", "uart_rx"} & roles:
            rows.append(_interface("uart_serial", ref, pins, ["confirm logic voltage", "cross TX/RX correctly", "share ground"]))
        if {"i2c_sda", "i2c_scl"} <= roles:
            rows.append(_interface("i2c", ref, pins, ["verify pullups", "confirm voltage domain"]))
        if {"spi_mosi", "spi_miso", "spi_sck"} <= roles or {"spi_mosi", "spi_sck", "spi_cs"} <= roles:
            rows.append(_interface("spi", ref, pins, ["verify chip select", "confirm voltage domain"]))
        if {"usb_dp", "usb_dm"} <= roles:
            rows.append(_interface("usb2", ref, pins, ["verify ESD/protection path", "confirm cable orientation"]))
        if roles & {"load", "motor", "actuator", "logic_input", "logic_io", "enable_control", "fault_output"}:
            rows.append(_interface("actuator_or_load_output", ref, pins, ["load-test output", "confirm flyback/protection"]))
    for net in nets:
        if net.get("role") in {"power", "ground"}:
            rows.append(
                {
                    "type": str(net.get("role")),
                    "net": net.get("net"),
                    "connector_ref": None,
                    "confidence": 0.72 if net.get("status") in PASS_STATUSES else 0.58,
                    "validation": ["verify continuity and voltage under current limit"],
                }
            )
    return _dedupe_rows(rows, key_fields=("type", "connector_ref", "net"))


def _pin_level_splice_contracts(
    connectors: Sequence[Dict[str, Any]],
    interfaces: Sequence[Dict[str, Any]],
    hazards: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows = []
    hard_hazard = any(hazard.get("severity") in {"critical", "hard_stop", "unsupported"} for hazard in hazards)
    for connector in connectors:
        pins = connector.get("pins") or []
        if not pins:
            continue
        wire_rows = [_wire_row(pin) for pin in pins if _wire_row(pin)]
        unknown_pins = [pin for pin in pins if pin.get("role") in {"unknown", ""}]
        has_ground = any(pin.get("role") == "ground" for pin in pins)
        has_power = any(pin.get("role") == "power" for pin in pins)
        blockers = []
        if hard_hazard:
            blockers.extend(str(hazard.get("clearance_requires") or hazard.get("hazard_id")) for hazard in hazards)
        if unknown_pins:
            blockers.append("Resolve unmeasured connector pins before using the full harness.")
        if not has_ground:
            blockers.append("Identify connector ground before making any signal or power splice.")
        if has_power and not any(pin.get("role") == "power" and pin.get("voltage") is not None for pin in pins):
            blockers.append("Measure supply voltage and polarity before joining the power pin.")
        status = "blocked_by_hazard" if hard_hazard else "blocked_until_pinout_complete" if blockers else "ready_for_controlled_splice"
        rows.append(
            {
                "schema_version": "pin_level_splice_contract.v1",
                "contract_id": f"{connector.get('connector_id')}_breakout",
                "source": "topology_evidence.v1",
                "status": status,
                "connector_id": connector.get("connector_id"),
                "connector_ref": connector.get("ref"),
                "label": connector.get("label"),
                "scope": "measured connector breakout and external splice only",
                "pin_count": len(pins),
                "interfaces": [
                    row.get("type")
                    for row in interfaces
                    if row.get("connector_ref") == connector.get("ref")
                ],
                "wire_bom": wire_rows,
                "pin_actions": _pin_actions(wire_rows),
                "validation_gates": _contract_validation_gates(wire_rows, pins),
                "do_not_connect_until": _dedupe(blockers + _contract_do_not_connect(wire_rows))[:10],
                "safety_policy": {
                    "current_limited_first_power": True,
                    "connect_ground_before_signals": True,
                    "power_pin_requires_voltage_and_polarity": has_power,
                    "unknown_pins_are_no_connect": True,
                    "scope_excludes_unmeasured_board_nets": True,
                },
                "claim_boundary": "This contract is generated from measured topology only; it does not certify hidden board nets or external target compatibility.",
            }
        )
    return rows


def _wire_row(pin: Dict[str, Any]) -> Dict[str, Any]:
    role = str(pin.get("role") or "unknown")
    if role == "unknown":
        return {
            "pin": pin.get("pin"),
            "net": pin.get("net"),
            "role": role,
            "function": "NO_CONNECT_UNTIL_IDENTIFIED",
            "color": "gray",
            "from": {"endpoint": pin.get("endpoint"), "pin": pin.get("pin"), "net": pin.get("net")},
            "to": {"endpoint": "do_not_connect", "role": "unknown"},
            "join": "do_not_connect",
            "requirement": "Identify this pin by continuity or datasheet before using it.",
        }
    mapping = {
        "ground": ("GND", "black", "target common ground", "common_reference", "Connect ground/common reference first."),
        "power": ("supply", "red", "current-limited supply positive", "power", "Connect only after voltage and polarity are verified."),
        "uart_tx": ("UART_TX_to_target_RX", "yellow", "target RX", "cross_signal", "Cross TX to target RX after voltage compatibility is confirmed."),
        "uart_rx": ("UART_RX_to_target_TX", "green", "target TX", "cross_signal", "Cross RX to target TX after voltage compatibility is confirmed."),
        "i2c_sda": ("I2C_SDA", "green", "target SDA", "same_signal_bus", "Join SDA only on a compatible voltage domain with pullups checked."),
        "i2c_scl": ("I2C_SCL", "yellow", "target SCL", "same_signal_bus", "Join SCL only on a compatible voltage domain with pullups checked."),
        "spi_mosi": ("SPI_MOSI", "green", "target MOSI", "same_signal_bus", "Join MOSI only on a compatible voltage domain."),
        "spi_miso": ("SPI_MISO", "yellow", "target MISO", "same_signal_bus", "Join MISO only on a compatible voltage domain."),
        "spi_sck": ("SPI_SCK", "blue", "target SCK", "same_signal_bus", "Join SCK only on a compatible voltage domain."),
        "spi_cs": ("SPI_CS", "purple", "target chip select", "same_signal_bus", "Join CS only on a compatible voltage domain."),
        "usb_dp": ("USB_D+", "green", "USB D+", "differential_pair", "Keep USB D+ and D- short, paired, and protected."),
        "usb_dm": ("USB_D-", "white", "USB D-", "differential_pair", "Keep USB D+ and D- short, paired, and protected."),
        "uart_dtr": ("UART_DTR", "blue", "target reset/DTR", "control_signal", "Use DTR only after reset polarity and target compatibility are verified."),
        "uart_rts": ("UART_RTS", "purple", "target RTS", "control_signal", "Use RTS only after flow-control or boot-mode compatibility is verified."),
        "uart_cts": ("UART_CTS", "orange", "target CTS", "control_signal", "Use CTS only after flow-control compatibility is verified."),
        "logic_input": ("LOGIC_INPUT", "orange", "protected logic drive", "control_signal", "Drive only after logic voltage compatibility is verified."),
        "logic_io": ("LOGIC_IO", "orange", "protected bidirectional logic signal", "control_signal", "Connect only after direction, voltage, and current limits are verified."),
        "enable_control": ("ENABLE", "orange", "protected enable control", "control_signal", "Drive only after enable polarity and voltage are verified."),
        "fault_output": ("FAULT", "purple", "target fault input", "control_signal", "Treat open-drain/fault pins according to required pullup voltage."),
        "load": ("LOAD_OUTPUT", "blue", "protected load or dummy load", "load_output", "Use fuse/current limit and verify driver rating."),
        "motor": ("MOTOR_OUTPUT", "blue", "protected motor/load", "load_output", "Use fuse/current limit and verify stall current."),
        "actuator": ("ACTUATOR_OUTPUT", "blue", "protected actuator/load", "load_output", "Use fuse/current limit and verify flyback/protection."),
    }
    function, color, target, join, requirement = mapping.get(
        role,
        (
            f"SIGNAL_{role.upper()}",
            "gray",
            "protected target signal",
            "control_signal",
            "Verify function, voltage domain, and direction before connecting this signal.",
        ),
    )
    if role == "power" and pin.get("voltage") is not None:
        function = f"rail:{pin.get('voltage')}V"
    if role in {"uart_tx", "uart_rx", "i2c_sda", "i2c_scl", "spi_mosi", "spi_miso", "spi_sck", "spi_cs"} and pin.get("logic_voltage") is not None:
        requirement = f"{requirement} Measured logic high: {pin.get('logic_voltage')} V."
    return {
        "pin": pin.get("pin"),
        "net": pin.get("net"),
        "role": role,
        "function": function,
        "color": color,
        "from": {"endpoint": pin.get("endpoint"), "pin": pin.get("pin"), "net": pin.get("net")},
        "to": {"endpoint": target, "role": role},
        "join": join,
        "voltage": pin.get("voltage"),
        "logic_voltage": pin.get("logic_voltage"),
        "requirement": requirement,
    }


def _pin_actions(wires: Sequence[Dict[str, Any]]) -> List[str]:
    actions = []
    for wire in wires:
        if wire.get("join") == "do_not_connect":
            actions.append(f"Leave pin {wire.get('pin')} unconnected until identified.")
        else:
            actions.append(
                f"{wire.get('color')} wire: {wire.get('from', {}).get('endpoint')} -> {wire.get('to', {}).get('endpoint')} ({wire.get('function')})."
            )
    return actions[:16]


def _contract_validation_gates(wires: Sequence[Dict[str, Any]], pins: Sequence[Dict[str, Any]]) -> List[str]:
    gates = ["Verify no-short resistance before wiring.", "Verify shared ground continuity before signals."]
    if any(pin.get("role") == "power" for pin in pins):
        gates.append("Verify supply voltage, polarity, and current limit before joining power.")
    if any(pin.get("role") in {"uart_tx", "uart_rx", "uart_dtr", "uart_rts", "uart_cts"} for pin in pins):
        gates.extend(["Verify UART logic voltage compatibility.", "Run UART loopback or known-safe serial capture before target connection."])
    if any(pin.get("role") in {"i2c_sda", "i2c_scl"} for pin in pins):
        gates.extend(["Verify I2C pullups and voltage domain.", "Scan bus at low speed before normal operation."])
    if any(pin.get("role") in {"spi_mosi", "spi_miso", "spi_sck", "spi_cs"} for pin in pins):
        gates.extend(["Verify SPI voltage domain and chip-select behavior.", "Probe SPI idle state before normal operation."])
    if any(wire.get("join") == "load_output" for wire in wires):
        gates.extend(["Test with dummy load before the real load.", "Record load current and thermal behavior."])
    return _dedupe(gates)[:10]


def _contract_do_not_connect(wires: Sequence[Dict[str, Any]]) -> List[str]:
    items = ["Do not join to an external target until voltage domain and shared ground are compatible."]
    if any(wire.get("join") == "do_not_connect" for wire in wires):
        items.append("Unknown pins must stay isolated and labeled no-connect.")
    if any(wire.get("role") == "power" for wire in wires):
        items.append("Do not connect the power pin without current limiting and polarity confirmation.")
    if any(wire.get("join") == "differential_pair" for wire in wires):
        items.append("Do not splice USB differential wires with long loose jumpers for production use.")
    return items


def _interface(kind: str, ref: Any, pins: Sequence[Dict[str, Any]], validation: Sequence[str]) -> Dict[str, Any]:
    relevant = [pin for pin in pins if _role_matches_interface(pin.get("role"), kind)]
    return {
        "type": kind,
        "connector_ref": ref,
        "labels": _dedupe(pin.get("label") or pin.get("net") or pin.get("pin") for pin in relevant)[:12],
        "pins": [pin.get("pin") for pin in relevant],
        "confidence": 0.82 if relevant else 0.62,
        "validation": list(validation),
    }


def _role_matches_interface(role: Any, kind: str) -> bool:
    role = str(role or "")
    if kind == "power":
        return role in {"power", "ground"}
    if kind == "uart_serial":
        return role in {"uart_tx", "uart_rx", "uart_dtr", "uart_rts", "uart_cts", "ground", "power"}
    if kind == "i2c":
        return role in {"i2c_sda", "i2c_scl", "ground", "power"}
    if kind == "spi":
        return role in {"spi_mosi", "spi_miso", "spi_sck", "spi_cs", "ground", "power"}
    if kind == "usb2":
        return role in {"usb_dp", "usb_dm", "ground", "power"}
    if kind == "actuator_or_load_output":
        return role in {"load", "motor", "actuator", "logic_input", "logic_io", "enable_control", "fault_output", "ground", "power"}
    return False


def _measurement_rows(
    evidence: Dict[str, Any],
    connectors: Sequence[Dict[str, Any]],
    continuity: Sequence[Dict[str, Any]],
    resistance: Sequence[Dict[str, Any]],
    voltage: Sequence[Dict[str, Any]],
    current: Sequence[Dict[str, Any]],
    thermal: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    index = 1

    def add(kind: str, target: str, value: Any, unit: str, notes: str, source: Dict[str, Any], passed: bool = True, failed: bool = False) -> None:
        nonlocal index
        rows.append(
            {
                "measurement_id": f"topology_{kind}_{index}",
                "type": kind,
                "target": target,
                "value": "fail" if failed else value,
                "unit": unit,
                "notes": notes,
                "status": "failed" if failed else "pass" if passed else "open",
                **_provenance(source.get("provenance") if isinstance(source, dict) else {}, evidence.get("provenance") or {}),
            }
        )
        index += 1

    for row in continuity:
        target = _continuity_target(row)
        failed = bool(row.get("failed"))
        passed = bool(row.get("passed")) and not failed
        kind = "resistance" if _power_ground_pair(row.get("from"), row.get("to")) or "short" in str(row.get("notes") or "").lower() else "continuity"
        add(kind, target, "pass" if passed else row.get("value"), row.get("unit") or "ohm", row.get("notes") or target, row, passed=passed, failed=failed)
    for row in resistance:
        target = _observation_target(row, "power to ground no-short")
        failed = bool(row.get("failed"))
        passed = bool(row.get("passed")) and not failed
        add("resistance", target, "pass" if passed else row.get("value"), row.get("unit") or "ohm", row.get("notes") or target, row, passed=passed, failed=failed)

    for connector in connectors:
        for pin in connector.get("pins") or []:
            if pin.get("role") == "ground" and pin.get("status") in PASS_STATUSES:
                add(
                    "continuity",
                    "connector ground to exposed ground",
                    "pass",
                    "ohm",
                    f"{pin.get('endpoint')} is mapped to ground by measured topology.",
                    pin,
                )
            if pin.get("role") == "power" and pin.get("voltage") is not None and pin.get("status") in PASS_STATUSES:
                add(
                    "voltage",
                    "input voltage and polarity",
                    pin.get("voltage"),
                    "V",
                    f"{pin.get('endpoint')} power pin voltage and polarity verified.",
                    pin,
                )
            if pin.get("role") in {"uart_tx", "uart_rx", "i2c_sda", "i2c_scl", "spi_mosi", "spi_miso", "spi_sck", "spi_cs", "usb_dp", "usb_dm", "logic_io"} and pin.get("logic_voltage") is not None:
                add(
                    "voltage",
                    "logic high voltage",
                    pin.get("logic_voltage"),
                    "V",
                    f"{pin.get('endpoint')} logic high voltage measured.",
                    pin,
                )

    for row in voltage:
        add("voltage", _observation_target(row, "logic high voltage"), row.get("value"), row.get("unit") or "V", row.get("notes") or "topology voltage observation", row, passed=bool(row.get("passed")), failed=bool(row.get("failed")))
    for row in current:
        add("current", _observation_target(row, "current draw under current-limited supply"), row.get("value"), row.get("unit") or "A", row.get("notes") or "topology current observation", row, passed=bool(row.get("passed")), failed=bool(row.get("failed")))
    for row in thermal:
        add("thermal", _observation_target(row, "thermal behavior after first power"), row.get("value"), row.get("unit") or "C", row.get("notes") or "topology thermal observation", row, passed=bool(row.get("passed")), failed=bool(row.get("failed")))

    if _has_power_and_ground(connectors) and not resistance and not any(_power_ground_pair(row.get("from"), row.get("to")) and row.get("failed") for row in continuity):
        source = continuity[0] if continuity else evidence
        add("resistance", "power to ground no-short", "pass", "ohm", "Measured topology does not report a power-to-ground short.", source)
    if any(_has_role(connector, {"ground"}) for connector in connectors):
        source = connectors[0] if connectors else evidence
        add("continuity", "shared ground continuity", "pass", "ohm", "Measured topology includes a shared ground reference.", source)
    if any(_has_role(connector, {"uart_tx", "uart_rx", "i2c_sda", "i2c_scl", "spi_mosi", "spi_miso", "spi_sck", "spi_cs", "logic_input", "logic_io", "enable_control", "fault_output"}) for connector in connectors):
        source = connectors[0] if connectors else evidence
        add("logic_level", "serial/I2C/SPI idle state if reused", "pass", "", "Measured topology identifies low-voltage signal pins; idle state still belongs in first-power outcome.", source)

    return _dedupe_rows(rows, key_fields=("type", "target", "value", "unit"))


def _resource_candidates(
    connectors: Sequence[Dict[str, Any]],
    interfaces: Sequence[Dict[str, Any]],
    hazards: Sequence[Dict[str, Any]],
    *,
    reference_only: bool = False,
) -> List[Dict[str, Any]]:
    rows = []
    hard_hazard = any(hazard.get("severity") in {"critical", "hard_stop", "unsupported"} for hazard in hazards)
    for connector in connectors:
        caps = _capabilities_for_connector(connector, interfaces)
        required = _connector_required_tests(connector, caps)
        if reference_only:
            required = _dedupe(
                [
                    *required,
                    "Confirm public reference topology on the physical board with continuity and pinout measurements.",
                    "Record no-short, voltage, current, and thermal bench evidence before power or splice.",
                ]
            )
        status = "needs_evidence" if required or hard_hazard or reference_only else "measurement_backed"
        rows.append(
            {
                "resource_id": connector.get("connector_id"),
                "name": f"{'reference' if reference_only else 'measured'} {connector.get('label') or connector.get('ref')} topology",
                "resource_kind": "salvaged",
                "source": "topology_evidence.v1",
                "capabilities": caps,
                "quantity": 1,
                "confidence": 0.88 if status == "measurement_backed" else connector.get("confidence", 0.68),
                "evidence_status": status,
                "source_refs": [str(connector.get("ref"))],
                "missing_evidence": required,
                "required_tests": required,
                "notes": (
                    "Public reference topology candidate; confirm on the bench before use."
                    if reference_only
                    else "Measured topology candidate; usable only inside the measured connector/pinout scope."
                ),
            }
        )
    return _dedupe_rows(rows, key_fields=("resource_id",))


def _capabilities_for_connector(connector: Dict[str, Any], interfaces: Sequence[Dict[str, Any]]) -> List[str]:
    roles = {pin.get("role") for pin in connector.get("pins") or []}
    ref = connector.get("ref")
    interface_types = {row.get("type") for row in interfaces if row.get("connector_ref") == ref}
    caps = ["connector"]
    if "power" in roles or "power" in interface_types:
        caps.append("power")
    if roles & {"uart_tx", "uart_rx", "uart_dtr", "uart_rts", "uart_cts"} or "uart_serial" in interface_types or "usb2" in interface_types:
        caps.append("usb_serial")
    if roles & {"i2c_sda", "i2c_scl", "spi_mosi", "spi_miso", "spi_sck", "spi_cs"} or {"i2c", "spi"} & interface_types:
        caps.append("sensor_or_adc")
    if roles & {"logic_io"}:
        caps.append("controller")
    if roles & {"load", "motor", "actuator", "logic_input", "enable_control", "fault_output"}:
        caps.extend(["actuator_driver", "motor_or_load"])
    return _dedupe(caps)


def _connector_required_tests(connector: Dict[str, Any], caps: Sequence[str]) -> List[str]:
    pins = connector.get("pins") or []
    required = []
    if not pins:
        required.append(f"Map pinout and continuity for {connector.get('label') or connector.get('ref')}.")
    if not any(pin.get("role") == "ground" for pin in pins):
        required.append("Identify connector ground with continuity before any splice.")
    if "power" in caps and not any(pin.get("role") == "power" and pin.get("voltage") is not None for pin in pins):
        required.append("Measure connector supply voltage and polarity before power.")
    if "usb_serial" in caps and not any(pin.get("logic_voltage") is not None for pin in pins if pin.get("role") in {"uart_tx", "uart_rx"}):
        required.append("Confirm UART voltage level, shared ground, TX/RX continuity, and loopback before target connection.")
    unknown = [pin for pin in pins if pin.get("role") in {"unknown", ""}]
    if unknown:
        required.append("Resolve unmeasured connector pins before using the full harness.")
    return _dedupe(required)[:8]


def _hazard_candidates(
    evidence: Dict[str, Any],
    connectors: Sequence[Dict[str, Any]],
    nets: Sequence[Dict[str, Any]],
    continuity: Sequence[Dict[str, Any]],
    resistance: Sequence[Dict[str, Any]],
    voltage: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    hazards: List[Dict[str, Any]] = []
    for row in continuity:
        text = f"{row.get('from')} {row.get('to')} {row.get('target')} {row.get('notes')}".lower()
        if row.get("failed") and ("short" in text or _power_ground_pair(row.get("from"), row.get("to"))):
            hazards.append(_hazard("power_ground_short", "critical", row, "Resolve the power-to-ground short or failed no-short check before any power or splice."))
        if row.get("passed") and _power_ground_pair(row.get("from"), row.get("to")):
            hazards.append(_hazard("power_ground_short", "critical", row, "Resolve the power-to-ground short before any power or splice."))
    for row in resistance:
        text = f"{row.get('from')} {row.get('to')} {row.get('target')} {row.get('notes')}".lower()
        if row.get("failed") and ("short" in text or _power_ground_pair(row.get("from"), row.get("to"))):
            hazards.append(_hazard("power_ground_short", "critical", row, "Resolve the failed no-short resistance check before any power or splice."))
    for row in list(voltage) + [pin for connector in connectors for pin in connector.get("pins") or []]:
        value = _first_number(row.get("value") if isinstance(row, dict) else None)
        value = value if value is not None else _first_number(row.get("voltage") if isinstance(row, dict) else None)
        if value is not None and abs(value) > 60:
            hazards.append(_hazard("high_voltage", "critical", row, "Move high-voltage topology evidence into specialist safety workflow before production release."))
    for net in nets:
        nodes = " ".join(_string_list(net.get("nodes"))).lower()
        if net.get("role") == "power" and any(token in nodes for token in ["gnd", "ground", "0v"]):
            hazards.append(_hazard("power_ground_short", "critical", net, "Resolve net evidence that ties power and ground together before any power or splice."))
    return _dedupe_hazards(hazards)


def _hazard(hazard_id: str, severity: str, evidence: Dict[str, Any], requirement: str) -> Dict[str, Any]:
    return {
        "hazard_id": hazard_id,
        "source": f"topology_evidence.v1:{evidence.get('observation_id') or evidence.get('net') or evidence.get('endpoint') or hazard_id}",
        "severity": severity,
        "unsupported_for_production_authority": severity in {"critical", "unsupported"},
        "evidence": evidence,
        "clearance_requires": requirement,
    }


def _topology_authority(
    connectors: Sequence[Dict[str, Any]],
    nets: Sequence[Dict[str, Any]],
    measurements: Sequence[Dict[str, Any]],
    hazards: Sequence[Dict[str, Any]],
    *,
    reference_only: bool = False,
) -> Dict[str, Any]:
    trusted = [row for row in measurements if all(str(row.get(key) or "").strip() for key in TRUST_KEYS[:5])]
    known_pins = [
        pin
        for connector in connectors
        for pin in connector.get("pins") or []
        if pin.get("role") not in {"unknown", ""}
    ]
    all_pins = [pin for connector in connectors for pin in connector.get("pins") or []]
    return {
        "schema_version": "topology_authority.v1",
        "pinout_known": bool(all_pins) and len(known_pins) == len(all_pins),
        "measurement_backed": bool(measurements) and not reference_only,
        "reference_backed": bool(reference_only),
        "connector_count": len(connectors),
        "net_count": len(nets),
        "known_pin_count": len(known_pins),
        "unknown_pin_count": max(0, len(all_pins) - len(known_pins)),
        "measurement_count": len(measurements),
        "trusted_measurement_count": len(trusted),
        "shorts_detected": any(hazard.get("hazard_id") == "power_ground_short" for hazard in hazards),
        "hazard_count": len(hazards),
        "claim_boundary": (
            "Public reference topology can guide tests but does not prove this physical board."
            if reference_only
            else "Topology authority covers only explicit measured endpoints, nets, and connector pins."
        ),
    }


def _required_measurements(connectors: Sequence[Dict[str, Any]], interfaces: Sequence[Dict[str, Any]], hazards: Sequence[Dict[str, Any]]) -> List[str]:
    if hazards:
        return _dedupe(hazard.get("clearance_requires") for hazard in hazards)[:8]
    prompts: List[str] = []
    if connectors:
        prompts.extend(["unpowered resistance between power and ground", "continuity from connector ground to exposed ground"])
    if any(row.get("type") == "power" for row in interfaces):
        prompts.extend(["input voltage and polarity", "current draw under current-limited supply"])
    if any(row.get("type") in {"uart_serial", "i2c", "spi", "usb2"} for row in interfaces):
        prompts.extend(["logic high voltage", "shared ground continuity", "serial/I2C/SPI idle state if reused"])
    for connector in connectors:
        prompts.extend(_connector_required_tests(connector, _capabilities_for_connector(connector, interfaces)))
    return _dedupe(prompts)[:12]


def _energy_domain(hazards: Sequence[Dict[str, Any]], connectors: Sequence[Dict[str, Any]], voltage: Sequence[Dict[str, Any]]) -> str:
    if any(hazard.get("hazard_id") == "high_voltage" for hazard in hazards):
        return "high_voltage_candidate"
    values = []
    values.extend(_first_number(row.get("value")) for row in voltage if isinstance(row, dict))
    values.extend(
        _first_number(pin.get("voltage"))
        for connector in connectors
        for pin in connector.get("pins") or []
    )
    values = [value for value in values if value is not None]
    if values and max(abs(value) for value in values) <= 24:
        return "measured_low_voltage_dc"
    if values:
        return "measured_unknown_or_high_voltage"
    return "unknown_topology"


def _merge_hazard_profiles(existing: Dict[str, Any], generated: Dict[str, Any]) -> Dict[str, Any]:
    if not existing:
        return generated
    merged = dict(existing)
    merged["hazards"] = _dedupe_hazards((existing.get("hazards") or []) + (generated.get("hazards") or []))
    merged["clearance_requirements"] = _dedupe(
        (existing.get("clearance_requirements") or []) + (generated.get("clearance_requirements") or [])
    )[:12]
    merged.setdefault("schema_version", "hardware_hazard_profile.v1")
    policy = dict(generated.get("source_policy") or {})
    policy.update(existing.get("source_policy") if isinstance(existing.get("source_policy"), dict) else {})
    merged["source_policy"] = policy
    if generated.get("energy_domain") and not merged.get("energy_domain"):
        merged["energy_domain"] = generated["energy_domain"]
    return merged


def _continuity_target(row: Dict[str, Any]) -> str:
    text = f"{row.get('from')} {row.get('to')} {row.get('target')} {row.get('notes')}".lower()
    if _power_ground_pair(row.get("from"), row.get("to")) or "no-short" in text or "no short" in text:
        return "power to ground no-short"
    if "ground" in text or "gnd" in text:
        return "connector ground to exposed ground"
    return str(row.get("target") or f"{row.get('from')} to {row.get('to')} continuity").strip()


def _observation_target(row: Dict[str, Any], default: str) -> str:
    text = str(row.get("target") or row.get("notes") or "").strip()
    return text or default


def _likely_connector_roles(pins: Sequence[Dict[str, Any]]) -> List[str]:
    roles = {pin.get("role") for pin in pins}
    likely = []
    if roles & {"power", "ground"}:
        likely.append("power_or_ground")
    if roles & {"uart_tx", "uart_rx", "uart_dtr", "uart_rts", "uart_cts", "i2c_sda", "i2c_scl", "spi_mosi", "spi_miso", "spi_sck", "spi_cs", "usb_dp", "usb_dm"}:
        likely.append("data_or_programming")
    if roles & {"load", "motor", "actuator", "logic_input", "logic_io", "enable_control", "fault_output"}:
        likely.append("load_output")
    return likely or ["unknown_external_interface"]


def _pin_groups(pins: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups = [
        ("power", {"power", "ground"}),
        ("uart", {"uart_tx", "uart_rx"}),
        ("serial_control", {"uart_dtr", "uart_rts", "uart_cts"}),
        ("i2c", {"i2c_sda", "i2c_scl"}),
        ("spi", {"spi_mosi", "spi_miso", "spi_sck", "spi_cs"}),
        ("usb2", {"usb_dp", "usb_dm"}),
        ("load", {"load", "motor", "actuator", "logic_input", "logic_io", "enable_control", "fault_output"}),
    ]
    rows = []
    for group, roles in groups:
        matched = [pin for pin in pins if pin.get("role") in roles]
        if matched:
            rows.append({"type": group, "pins": [pin.get("pin") for pin in matched], "labels": _dedupe(pin.get("label") or pin.get("net") for pin in matched)})
    return rows


def _role(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    compact = text.replace("+", "").replace("/", "_")
    aliases = {
        "gnd": "ground",
        "ground": "ground",
        "0v": "ground",
        "vcc": "power",
        "vdd": "power",
        "vin": "power",
        "vbus": "power",
        "power": "power",
        "supply": "power",
        "5v": "power",
        "3v3": "power",
        "3.3v": "power",
        "tx": "uart_tx",
        "txo": "uart_tx",
        "uart_tx": "uart_tx",
        "rxd": "uart_rx",
        "rx": "uart_rx",
        "rxi": "uart_rx",
        "uart_rx": "uart_rx",
        "dtr": "uart_dtr",
        "rts": "uart_rts",
        "cts": "uart_cts",
        "sda": "i2c_sda",
        "scl": "i2c_scl",
        "i2c_sda": "i2c_sda",
        "i2c_scl": "i2c_scl",
        "mosi": "spi_mosi",
        "sdi": "spi_mosi",
        "miso": "spi_miso",
        "sdo": "spi_miso",
        "sck": "spi_sck",
        "sclk": "spi_sck",
        "spi_sck": "spi_sck",
        "spi_mosi": "spi_mosi",
        "spi_miso": "spi_miso",
        "cs": "spi_cs",
        "chip_select": "spi_cs",
        "d+": "usb_dp",
        "dp": "usb_dp",
        "usb_dp": "usb_dp",
        "d_": "usb_dm",
        "dm": "usb_dm",
        "usb_dm": "usb_dm",
        "gpio": "logic_io",
        "digital_io": "logic_io",
        "logic_io": "logic_io",
        "io": "logic_io",
        "slp": "enable_control",
        "sleep": "enable_control",
        "enable": "enable_control",
        "fault": "fault_output",
        "flt": "fault_output",
        "ain1": "logic_input",
        "ain2": "logic_input",
        "bin1": "logic_input",
        "bin2": "logic_input",
        "aout1": "motor",
        "aout2": "motor",
        "bout1": "motor",
        "bout2": "motor",
        "out": "load",
        "out1": "load",
        "out2": "load",
        "motor": "motor",
        "load": "load",
        "actuator": "actuator",
    }
    if compact in aliases:
        return aliases[compact]
    if compact.startswith("3v") or compact.startswith("5v") or compact.startswith("12v") or compact.startswith("24v"):
        return "power"
    if "ground" in compact or compact == "gnd":
        return "ground"
    if "tx" == compact or compact.endswith("_tx"):
        return "uart_tx"
    if "rx" == compact or compact.endswith("_rx"):
        return "uart_rx"
    if compact.startswith("ain") or compact.startswith("bin"):
        return "logic_input"
    if compact.startswith("aout") or compact.startswith("bout"):
        return "motor"
    if compact.startswith("gpio"):
        return "logic_io"
    return "unknown"


def _power_ground_pair(left: Any, right: Any) -> bool:
    return {_role(left), _role(right)} == {"power", "ground"}


def _has_power_and_ground(connectors: Sequence[Dict[str, Any]]) -> bool:
    roles = {pin.get("role") for connector in connectors for pin in connector.get("pins") or []}
    return {"power", "ground"} <= roles


def _has_role(connector: Dict[str, Any], roles: set[str]) -> bool:
    return any(pin.get("role") in roles for pin in connector.get("pins") or [])


def _status(row: Dict[str, Any]) -> str:
    raw = str(row.get("status") or row.get("evidence_status") or row.get("result") or "").strip().lower()
    if raw in PASS_STATUSES:
        return raw
    if raw in FAIL_STATUSES:
        return "failed"
    return raw or "measured"


def _provenance(row: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    source = row if isinstance(row, dict) else {}
    nested = source.get("provenance") if isinstance(source.get("provenance"), dict) else {}
    base = fallback if isinstance(fallback, dict) else {}
    result = {}
    for key in TRUST_KEYS:
        result[key] = source.get(key) or nested.get(key) or base.get(key) or ""
    return result


def _endpoint(ref: Any, pin: Any) -> str:
    return f"{ref}:{pin}"


def _default_unit(kind: str) -> str:
    return {"continuity": "ohm", "resistance": "ohm", "voltage": "V", "current": "A", "thermal": "C"}.get(kind, "")


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "yes", "1", "pass", "passed", "ok"}


def _rows(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str) and value.strip():
        return [{"target": value.strip()}]
    return []


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first_number(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        text = str(value)
        chars = []
        started = False
        for ch in text:
            if ch.isdigit() or ch in {".", "-", "+"}:
                chars.append(ch)
                started = True
            elif started:
                break
        try:
            return float("".join(chars)) if chars else None
        except ValueError:
            return None


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:90] or "topology_candidate"


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


def _dedupe_hazards(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("hazard_id") or ""), str(row.get("source") or ""))
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept
