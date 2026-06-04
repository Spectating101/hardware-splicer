from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.engines.evidence_extractor import is_ground_net, is_power_net
from src.engines.circuit_physics import CircuitPhysicsEngine
from src.engines.netlist import CircuitNetlist, ConstantCurrentLoad, LDO, VoltageConstraint, VoltageSource
from src.engines.power_tree_validator import PowerTreeConstraints, SourceCurrentLimit, validate_pcb_power_tree
from src.engines.system_structure_extractor import (
    _canonical_signal_aliases,
    _component_category,
    _infer_nominal_voltage,
    _is_source_like_power_net,
    _load_components_pinmap_and_nets,
    _normalize_net,
    extract_board_structure,
    synthesize_machine_topology,
)
from src.intelligence.functional_salvage import aggregate_functional_salvage, infer_board_functional_salvage
from src.intelligence.pinout_database import PinType, pinout_database


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _dedupe_text(items: Iterable[Any], *, limit: int = 40) -> List[str]:
    kept: List[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            kept.append(text)
        if len(kept) >= limit:
            break
    return kept


def _norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9+.\-_/]+", " ", str(value or "").lower()).strip()


def _compact_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _text_tokens(value: Any) -> List[str]:
    return [
        token
        for token in re.split(r"[^a-zA-Z0-9+.\-_/]+", str(value or ""))
        if token and len(token) >= 2
    ]


def _extract_first_number(value: Any) -> Optional[float]:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return None
    return _safe_float(match.group(0), 0.0)


def _board_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload.get("boards"), list):
        return [row for row in payload.get("boards") or [] if isinstance(row, dict)]
    if isinstance(payload.get("board"), dict):
        return [dict(payload["board"])]
    return [payload]


def _net_kind(net: str) -> str:
    if is_ground_net(net):
        return "ground"
    if is_power_net(net) or _is_source_like_power_net(net):
        return "power"
    return "signal"


def _pin_role(net: str) -> str:
    kind = _net_kind(net)
    if kind != "signal":
        return kind
    aliases = _canonical_signal_aliases(net)
    if aliases & {"SCL", "SDA"}:
        return "i2c"
    if aliases & {"SCLK", "MOSI", "MISO", "CS"}:
        return "spi"
    if aliases & {"TX", "RX"}:
        return "uart"
    if aliases & {"D+", "D-"}:
        return "usb2"
    if aliases & {"SWDIO", "SWCLK"}:
        return "debug"
    upper = str(net or "").upper()
    if "PWM" in upper or "SERVO" in upper:
        return "pwm"
    if "EN" in upper or "RST" in upper or "BOOT" in upper:
        return "control"
    return "signal"


def _node_id(board_id: str, kind: str, name: str) -> str:
    safe = str(name or "").replace(" ", "_").replace("/", "_")
    return f"{kind}:{board_id}:{safe}"


def _component_records(
    components: Dict[str, Any],
    pinmap: Dict[str, Dict[str, str]],
    category_by_ref: Dict[str, str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for ref, raw_meta in sorted((components or {}).items()):
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        pins = pinmap.get(ref) or {}
        rows.append(
            {
                "ref": ref,
                "category": category_by_ref.get(ref, "other"),
                "value": meta.get("value") or "",
                "footprint": meta.get("footprint") or "",
                "pin_count": len(pins),
                "nets": sorted({_normalize_net(net) for net in pins.values() if _normalize_net(net)}),
            }
        )
    return rows


def _net_records(
    nets: Dict[str, Dict[str, Any]],
    category_by_ref: Dict[str, str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for raw_name, net_data in sorted((nets or {}).items(), key=lambda item: _normalize_net(str(item[0]))):
        net = _normalize_net(str(raw_name))
        if not net:
            continue
        nodes = [node for node in (net_data.get("nodes") or []) if isinstance(node, dict)]
        component_refs = sorted({str(node.get("ref")) for node in nodes if node.get("ref")})
        connector_refs = sorted(ref for ref in component_refs if category_by_ref.get(ref) == "connector")
        rows.append(
            {
                "net": net,
                "kind": _net_kind(net),
                "nominal_v": _infer_nominal_voltage(net),
                "aliases": sorted(_canonical_signal_aliases(net)),
                "pin_count": len(nodes),
                "component_refs": component_refs,
                "connector_refs": connector_refs,
                "load_refs": [
                    ref
                    for ref in component_refs
                    if category_by_ref.get(ref) not in {"connector", "resistor", "capacitor", "inductor", "diode", None}
                ],
            }
        )
    return rows


def _pinout_for_value(value: Any) -> Any:
    text = str(value or "").strip()
    if not text:
        return None
    candidates = [text]
    candidates.extend(token for token in re.split(r"[^A-Za-z0-9_.+-]+", text) if token)
    candidates.extend(token for token in re.split(r"[-_/ ]+", text) if token)
    for candidate in _dedupe_text(candidates, limit=12):
        pinout = pinout_database.get_pinout(candidate) or pinout_database.search_by_component_name(candidate)
        if pinout:
            return pinout
    return None


def _serialize_pin(pin: Any) -> Dict[str, Any]:
    return {
        "pin_number": pin.pin_number,
        "pin_name": pin.pin_name,
        "pin_type": pin.pin_type.value if hasattr(pin.pin_type, "value") else str(pin.pin_type),
        "typical_voltage": pin.typical_voltage,
        "max_current_ma": pin.max_current_ma,
        "critical": bool(pin.critical),
        "alternate_functions": pin.alternate_functions[:8],
        "typical_connections": pin.typical_connections[:8],
        "description": pin.description,
    }


def _serialize_pinout(pinout: Any) -> Dict[str, Any]:
    return {
        "part_number": pinout.part_number,
        "manufacturer": pinout.manufacturer,
        "description": pinout.description,
        "package": pinout.package.value if hasattr(pinout.package, "value") else str(pinout.package),
        "pin_count": pinout.pin_count,
        "datasheet_url": pinout.datasheet_url,
        "notes": pinout.notes,
        "critical_pins": [_serialize_pin(pin) for pin in pinout.pins if pin.critical][:20],
        "power_pins": [_serialize_pin(pin) for pin in pinout.pins if pin.pin_type == PinType.POWER][:20],
        "ground_pins": [_serialize_pin(pin) for pin in pinout.pins if pin.pin_type == PinType.GROUND][:20],
        "programming_or_boot_pins": [
            _serialize_pin(pin)
            for pin in pinout.pins
            if pin.pin_type == PinType.PROGRAMMING
            or any(token in pin.pin_name.upper() for token in ["TX", "RX", "SWD", "BOOT", "GPIO0", "EN", "RST", "RESET"])
        ][:20],
    }


def _pin_voltage_compatible(pin: Any, net: str) -> bool:
    nominal = _infer_nominal_voltage(net)
    if nominal is None or pin.typical_voltage is None:
        return True
    tolerance = max(0.25, float(pin.typical_voltage) * 0.15)
    return abs(float(nominal) - float(pin.typical_voltage)) <= tolerance


def _pin_mapping_findings(ref: str, pin: Any, net: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    pin_type = pin.pin_type
    if pin_type == PinType.GROUND and not is_ground_net(net):
        findings.append(
            _risk(
                "high",
                "pinout_ground_mismatch",
                f"{ref} pin {pin.pin_number} ({pin.pin_name}) is expected ground but maps to {net}.",
                "Confirm the symbol/package pinout or correct the net mapping before powering.",
                evidence=[ref, str(pin.pin_number), net],
            )
        )
    if pin_type == PinType.POWER and not (is_power_net(net) or _is_source_like_power_net(net)):
        findings.append(
            _risk(
                "high",
                "pinout_power_mismatch",
                f"{ref} pin {pin.pin_number} ({pin.pin_name}) is expected power but maps to {net}.",
                "Confirm the symbol/package pinout or correct the net mapping before powering.",
                evidence=[ref, str(pin.pin_number), net],
            )
        )
    if pin_type not in {PinType.POWER, PinType.GROUND} and (_infer_nominal_voltage(net) or 0.0) > 5.1:
        findings.append(
            _risk(
                "high",
                "signal_pin_overvoltage_risk",
                f"{ref} pin {pin.pin_number} ({pin.pin_name}) appears tied to high-voltage net {net}.",
                "Do not power until the net function and voltage tolerance are verified against the datasheet.",
                evidence=[ref, str(pin.pin_number), net],
            )
        )
    if not _pin_voltage_compatible(pin, net):
        findings.append(
            _risk(
                "medium",
                "pinout_voltage_expectation",
                f"{ref} pin {pin.pin_number} ({pin.pin_name}) typical voltage does not match {net}.",
                "Measure the pin and verify the exact package variant/datasheet.",
                evidence=[ref, str(pin.pin_number), net],
            )
        )
    return findings


def _component_pinout_intelligence(
    components: Dict[str, Any],
    pinmap: Dict[str, Dict[str, str]],
    category_by_ref: Dict[str, str],
    *,
    physical_pinmap: bool = True,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    known_count = 0
    unresolved_active: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []
    mapped_pin_count = 0
    known_mapped_pin_count = 0
    for ref, raw_meta in sorted((components or {}).items()):
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        category = category_by_ref.get(ref, "other")
        if category in {"connector", "resistor", "capacitor", "inductor", "diode", "other"}:
            continue
        value = str(meta.get("value") or "")
        pins = pinmap.get(ref) or {}
        mapped_pin_count += len(pins)
        pinout = _pinout_for_value(value)
        if not pinout:
            unresolved_active.append(
                {
                    "ref": ref,
                    "value": value,
                    "category": category,
                    "pin_count": len(pins),
                    "action": "Resolve exact datasheet/pinout before making pin-level repair or splice instructions.",
                }
            )
            rows.append(
                {
                    "ref": ref,
                    "value": value,
                    "category": category,
                    "resolution": "unresolved_pinout",
                    "pin_count": len(pins),
                    "next_actions": ["capture marking/package", "resolve datasheet", "confirm symbol pin mapping"],
                }
            )
            continue

        known_count += 1
        if not physical_pinmap:
            rows.append(
                {
                    "ref": ref,
                    "value": value,
                    "category": category,
                    "resolution": "known_pinout_without_physical_pinmap",
                    "pinout": _serialize_pinout(pinout),
                    "mapped_pin_count": len(pins),
                    "known_mapped_pin_count": 0,
                    "critical_mapped_pins": [],
                    "pin_maps": [],
                    "next_actions": ["reload original design pinmap or verify physical package before pin-level claims"],
                }
            )
            continue
        pin_by_number = {str(pin.pin_number): pin for pin in pinout.pins}
        pin_maps = []
        critical_mapped = []
        for pin_number, raw_net in sorted(pins.items(), key=lambda item: str(item[0])):
            net = _normalize_net(str(raw_net))
            pin_def = pin_by_number.get(str(pin_number))
            if not pin_def:
                pin_maps.append(
                    {
                        "pin": str(pin_number),
                        "net": net,
                        "status": "pin_not_in_known_pinout",
                        "action": "Confirm symbol/package variant.",
                    }
                )
                continue
            known_mapped_pin_count += 1
            if pin_def.critical:
                critical_mapped.append(str(pin_number))
            pin_findings = _pin_mapping_findings(ref, pin_def, net)
            findings.extend(pin_findings)
            pin_maps.append(
                {
                    "pin": str(pin_number),
                    "net": net,
                    "pin_name": pin_def.pin_name,
                    "pin_type": pin_def.pin_type.value,
                    "typical_voltage": pin_def.typical_voltage,
                    "critical": bool(pin_def.critical),
                    "status": "matched" if not pin_findings else "needs_review",
                    "findings": pin_findings,
                }
            )
        rows.append(
            {
                "ref": ref,
                "value": value,
                "category": category,
                "resolution": "known_pinout",
                "pinout": _serialize_pinout(pinout),
                "mapped_pin_count": len(pin_maps),
                "known_mapped_pin_count": len([row for row in pin_maps if row.get("pin_name")]),
                "critical_mapped_pins": critical_mapped,
                "pin_maps": pin_maps,
            }
        )

    return {
        "mode": "component_pinout_intelligence",
        "known_pinout_count": known_count,
        "unresolved_active_count": len(unresolved_active),
        "mapped_pin_count": mapped_pin_count,
        "known_mapped_pin_count": known_mapped_pin_count,
        "unresolved_active_components": unresolved_active,
        "components": rows,
        "findings": findings[:80],
        "next_actions": _dedupe_text(
            [
                item["action"]
                for item in unresolved_active
            ]
            + [finding.get("action") for finding in findings],
            limit=20,
        ),
    }


def _graph_records(
    board_id: str,
    components: Dict[str, Any],
    pinmap: Dict[str, Dict[str, str]],
    nets: Dict[str, Dict[str, Any]],
    category_by_ref: Dict[str, str],
) -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = [
        {"id": _node_id(board_id, "board", board_id), "kind": "board", "label": board_id}
    ]
    edges: List[Dict[str, Any]] = []
    seen_nodes = {nodes[0]["id"]}

    for row in _component_records(components, pinmap, category_by_ref):
        node = {
            "id": _node_id(board_id, "component", row["ref"]),
            "kind": "component",
            "label": row["ref"],
            "category": row["category"],
            "value": row["value"],
            "footprint": row["footprint"],
            "pin_count": row["pin_count"],
        }
        nodes.append(node)
        seen_nodes.add(node["id"])
        edges.append(
            {
                "source": _node_id(board_id, "board", board_id),
                "target": node["id"],
                "kind": "has_component",
                "ref": row["ref"],
            }
        )

    for row in _net_records(nets, category_by_ref):
        node = {
            "id": _node_id(board_id, "net", row["net"]),
            "kind": "net",
            "label": row["net"],
            "net_kind": row["kind"],
            "nominal_v": row["nominal_v"],
            "pin_count": row["pin_count"],
            "aliases": row["aliases"],
        }
        nodes.append(node)
        seen_nodes.add(node["id"])

    for ref, pins in sorted((pinmap or {}).items()):
        comp_id = _node_id(board_id, "component", ref)
        if comp_id not in seen_nodes:
            continue
        for pin, raw_net in sorted((pins or {}).items(), key=lambda item: str(item[0])):
            net = _normalize_net(str(raw_net))
            if not net:
                continue
            net_id = _node_id(board_id, "net", net)
            if net_id not in seen_nodes:
                continue
            edges.append(
                {
                    "source": comp_id,
                    "target": net_id,
                    "kind": "pin",
                    "ref": ref,
                    "pin": str(pin),
                    "net": net,
                    "pin_role": _pin_role(net),
                }
            )

    component_count = len([node for node in nodes if node.get("kind") == "component"])
    net_count = len([node for node in nodes if node.get("kind") == "net"])
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "component_count": component_count,
            "net_count": net_count,
            "edge_count": len(edges),
            "power_net_count": len([node for node in nodes if node.get("kind") == "net" and node.get("net_kind") == "power"]),
            "ground_net_count": len([node for node in nodes if node.get("kind") == "net" and node.get("net_kind") == "ground"]),
        },
    }


def _connector_contracts(structure: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for connector in structure.get("connectors") or []:
        if not isinstance(connector, dict):
            continue
        pin_nets = connector.get("pin_nets") if isinstance(connector.get("pin_nets"), dict) else {}
        pins = []
        power_nets = set()
        signal_nets = set()
        ground_pins = []
        for pin, raw_net in sorted(pin_nets.items(), key=lambda item: str(item[0])):
            net = _normalize_net(str(raw_net))
            role = _pin_role(net)
            if role == "power":
                power_nets.add(net)
            elif role == "ground":
                ground_pins.append(str(pin))
            else:
                signal_nets.add(net)
            pins.append(
                {
                    "pin": str(pin),
                    "net": net,
                    "role": role,
                    "nominal_v": _infer_nominal_voltage(net),
                    "aliases": sorted(_canonical_signal_aliases(net)),
                }
            )
        semantic_role = str(connector.get("semantic_role") or "generic")
        if semantic_role == "power_input":
            splice_role = "power_entry"
        elif semantic_role in {"debug_link", "board_link"}:
            splice_role = "logic_entry"
        elif semantic_role in {"actuation", "control_harness"}:
            splice_role = "load_or_control_entry"
        elif power_nets:
            splice_role = "power_or_board_link"
        else:
            splice_role = "unclassified"
        rows.append(
            {
                "connector_ref": connector.get("ref"),
                "value": connector.get("value") or "",
                "footprint": connector.get("footprint") or "",
                "semantic_role": semantic_role,
                "splice_role": splice_role,
                "pins": pins,
                "power_nets": sorted(power_nets),
                "signal_nets": sorted(signal_nets),
                "ground_pins": ground_pins,
                "interfaces": connector.get("interfaces") or [],
                "splice_allowed_after_gates": bool(pins) and bool(ground_pins or power_nets or signal_nets),
            }
        )
    return rows


def _risk(severity: str, topic: str, message: str, action: str, evidence: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "severity": severity,
        "topic": topic,
        "message": message,
        "action": action,
        "evidence": evidence or [],
    }


def _risk_records(
    structure: Dict[str, Any],
    connector_contracts: List[Dict[str, Any]],
    component_intelligence: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    risks: List[Dict[str, Any]] = []
    if isinstance(component_intelligence, dict):
        risks.extend(
            finding
            for finding in component_intelligence.get("findings") or []
            if isinstance(finding, dict)
        )
    power_control = structure.get("power_control_analysis") if isinstance(structure.get("power_control_analysis"), dict) else {}
    for finding in power_control.get("risk_findings") or []:
        if not isinstance(finding, dict):
            continue
        risks.append(
            _risk(
                str(finding.get("severity") or "medium"),
                str(finding.get("topic") or "power_control"),
                str(finding.get("message") or "Power/control risk found."),
                str(finding.get("fix") or "Review extracted power/control evidence before powering or splicing."),
                evidence=[str(finding.get("ref") or finding.get("net") or "")],
            )
        )

    if not ((structure.get("power") or {}).get("rails") or []):
        risks.append(
            _risk(
                "high",
                "power_model",
                "No power rail model is available.",
                "Extract a design netlist or record rail measurements before any powered splice.",
            )
        )
    runtime = structure.get("controller_runtime") if isinstance(structure.get("controller_runtime"), dict) else {}
    if runtime.get("controllers") and not runtime.get("programming_paths"):
        risks.append(
            _risk(
                "high",
                "programming_path",
                "Controller exists but no programming/debug path was recovered.",
                "Identify USB, UART, SWD, JTAG, or module-native programming access before firmware bring-up.",
            )
        )

    for connector in connector_contracts:
        power_nets = connector.get("power_nets") or []
        signal_nets = connector.get("signal_nets") or []
        ground_pins = connector.get("ground_pins") or []
        ref = str(connector.get("connector_ref") or "")
        if power_nets and not ground_pins:
            risks.append(
                _risk(
                    "high",
                    "connector_return_path",
                    f"{ref} exposes power but no ground pin was mapped.",
                    "Find the return path before using this connector as a splice entry.",
                    evidence=[ref],
                )
            )
        if signal_nets and not ground_pins:
            risks.append(
                _risk(
                    "medium",
                    "signal_reference",
                    f"{ref} exposes signal nets without an explicit ground reference.",
                    "Confirm common ground or isolation requirements before cross-board wiring.",
                    evidence=[ref],
                )
            )
        high_power = [
            net
            for net in power_nets
            if (_infer_nominal_voltage(net) or 0.0) >= 9.0 or _is_source_like_power_net(net)
        ]
        if high_power and signal_nets:
            risks.append(
                _risk(
                    "high",
                    "mixed_voltage_connector",
                    f"{ref} mixes source/high-voltage power with logic/control signals.",
                    "Use current limiting, keyed wiring, and logic-level verification before connecting external circuitry.",
                    evidence=[ref, *high_power],
                )
            )
        servo_like = any("SERVO" in str(net).upper() or "PWM" in str(net).upper() for net in signal_nets + power_nets)
        if servo_like:
            risks.append(
                _risk(
                    "medium",
                    "actuation_splice",
                    f"{ref} looks like an actuation or servo splice point.",
                    "Verify external load supply, common ground, and PWM logic level before attaching a load.",
                    evidence=[ref],
                )
            )
    return risks[:80]


def _measurement(
    measurement_id: str,
    stage: str,
    measurement_type: str,
    target: str,
    prompt: str,
    expected: str,
    *,
    priority: int = 3,
    blocks: Optional[List[str]] = None,
    evidence: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "measurement_id": measurement_id,
        "stage": stage,
        "type": measurement_type,
        "target": target,
        "prompt": prompt,
        "expected": expected,
        "priority": priority,
        "blocks_before_done": blocks or [],
        "evidence": evidence or [],
    }


def _measurement_plan(
    structure: Dict[str, Any],
    connector_contracts: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    ground = str(structure.get("ground_net") or "0")
    rails = (structure.get("power") or {}).get("rails") or []
    seen = set()

    def add(row: Dict[str, Any]) -> None:
        key = (row["type"], row["target"], row["prompt"])
        if key in seen:
            return
        seen.add(key)
        plan.append(row)

    for rail in rails:
        if not isinstance(rail, dict):
            continue
        net = str(rail.get("net") or "")
        if not net:
            continue
        nominal = rail.get("nominal_v")
        expected = f"{nominal:g} V nominal" if isinstance(nominal, (int, float)) else "stable expected rail voltage"
        priority = 1 if rail.get("is_input_root") or _is_source_like_power_net(net) else 2
        add(
            _measurement(
                f"rail_voltage_{len(plan) + 1}",
                "power_baseline",
                "voltage",
                net,
                f"Measure {net} to {ground} before connecting external circuitry.",
                expected,
                priority=priority,
                blocks=["power_application", "splicing"],
                evidence=[net],
            )
        )
        if rail.get("is_input_root") or _is_source_like_power_net(net):
            add(
                _measurement(
                    f"rail_polarity_{len(plan) + 1}",
                    "power_baseline",
                    "polarity",
                    net,
                    f"Confirm polarity and current-limited source behavior on {net}.",
                    "Polarity matches board marking/netlist and current limit is set before energizing.",
                    priority=1,
                    blocks=["power_application", "splicing"],
                    evidence=[net],
                )
            )

    for connector in connector_contracts:
        ref = str(connector.get("connector_ref") or "connector")
        if connector.get("ground_pins"):
            add(
                _measurement(
                    f"connector_ground_{len(plan) + 1}",
                    "connector_mapping",
                    "continuity",
                    ref,
                    f"Confirm {ref} ground pin(s) have continuity to board ground.",
                    "Continuity to board ground is present and low resistance.",
                    priority=1,
                    blocks=["splicing"],
                    evidence=[ref],
                )
            )
        for net in connector.get("power_nets") or []:
            add(
                _measurement(
                    f"connector_power_{len(plan) + 1}",
                    "connector_mapping",
                    "voltage",
                    f"{ref}:{net}",
                    f"Measure {ref} power net {net} to ground at the connector.",
                    "Voltage and polarity match the splice contract.",
                    priority=1,
                    blocks=["splicing"],
                    evidence=[ref, net],
                )
            )
        signal_roles = sorted({str(pin.get("role") or "") for pin in connector.get("pins") or [] if pin.get("role") not in {"ground", "power"}})
        if signal_roles:
            add(
                _measurement(
                    f"connector_logic_{len(plan) + 1}",
                    "logic_baseline",
                    "logic_level",
                    ref,
                    f"Measure idle/high logic level for {ref} signal pins before cross-board wiring.",
                    "Logic high is compatible with the target board or an adapter is specified.",
                    priority=2,
                    blocks=["splicing", "firmware_io"],
                    evidence=[ref],
                )
            )

    runtime = structure.get("controller_runtime") if isinstance(structure.get("controller_runtime"), dict) else {}
    for path in (runtime.get("programming_paths") or [])[:4]:
        if not isinstance(path, dict):
            continue
        label = str(path.get("type") or path.get("connector_ref") or "programming path")
        add(
            _measurement(
                f"programming_path_{len(plan) + 1}",
                "controller_bringup",
                "functional_check",
                label,
                f"Verify programming/debug access through {label}.",
                "Controller can enumerate, enter boot mode, or expose logs without unsafe heating/current.",
                priority=2,
                blocks=["firmware_bringup"],
                evidence=[label],
            )
        )

    for risk in risks:
        topic = str(risk.get("topic") or "")
        evidence = risk.get("evidence") or []
        target = str(evidence[0] if evidence else topic or "risk")
        if topic == "source_limit_missing":
            add(
                _measurement(
                    f"source_limit_{len(plan) + 1}",
                    "power_baseline",
                    "current_limit",
                    target,
                    str(risk.get("action") or f"Record source current limit or supply capability for {target}."),
                    "Supply capability/current limit is recorded in amps and exceeds estimated load.",
                    priority=1,
                    blocks=["power_application", "splicing"],
                    evidence=evidence,
                )
            )
            continue
        if topic == "rail_overcurrent":
            add(
                _measurement(
                    f"rail_budget_{len(plan) + 1}",
                    "risk_closure",
                    "review",
                    target,
                    str(risk.get("action") or f"Resolve overcurrent budget on {target}."),
                    "Rail budget is corrected by a higher-current source, lower load, or accepted design change.",
                    priority=1,
                    blocks=["power_application", "splicing"],
                    evidence=evidence,
                )
            )
            continue
        if topic == "load_unknown":
            add(
                _measurement(
                    f"load_current_{len(plan) + 1}",
                    "power_baseline",
                    "load_current",
                    target,
                    str(risk.get("action") or f"Measure or identify load current for {target}."),
                    "Load current is measured or identified from the exact part/datasheet.",
                    priority=2,
                    blocks=["splicing"],
                    evidence=evidence,
                )
            )
            continue
        if risk.get("severity") not in {"critical", "error", "high"}:
            continue
        add(
            _measurement(
                f"risk_gate_{len(plan) + 1}",
                "risk_closure",
                "review",
                str(risk.get("topic") or "risk"),
                str(risk.get("action") or "Resolve high-severity circuit risk."),
                "Risk is closed by measurement, review, or accepted hold.",
                priority=1,
                blocks=["splicing", "power_application"],
                evidence=risk.get("evidence") or [],
            )
        )
    return plan[:80]


def _session_measurement_records(session: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(session, dict):
        return []
    evidence = session.get("evidence") if isinstance(session.get("evidence"), dict) else {}
    rows: List[Dict[str, Any]] = []
    for measurement in evidence.get("measurements") or []:
        if not isinstance(measurement, dict):
            continue
        text = " ".join(
            str(measurement.get(key) or "")
            for key in ["type", "target", "value", "unit", "notes"]
        )
        rows.append(
            {
                "evidence_id": str(measurement.get("measurement_id") or f"measurement_{len(rows) + 1}"),
                "kind": "measurement",
                "type": str(measurement.get("type") or measurement.get("measurement_type") or "measurement"),
                "target": str(measurement.get("target") or ""),
                "value": measurement.get("value"),
                "unit": str(measurement.get("unit") or measurement.get("units") or ""),
                "notes": str(measurement.get("notes") or ""),
                "confidence": measurement.get("confidence", 1.0),
                "text": text,
            }
        )
    return rows


def _session_review_records(session: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(session, dict):
        return []
    rows: List[Dict[str, Any]] = []
    for review in session.get("reviews") or []:
        if not isinstance(review, dict):
            continue
        payload = review.get("payload") if isinstance(review.get("payload"), dict) else {}
        text = " ".join(
            str(value or "")
            for value in [
                review.get("task_id"),
                review.get("task_type"),
                review.get("action"),
                payload.get("notes"),
                payload.get("corrected_label"),
            ]
        )
        rows.append(
            {
                "evidence_id": str(review.get("review_id") or f"review_{len(rows) + 1}"),
                "kind": "review",
                "action": str(review.get("action") or payload.get("action") or "reviewed"),
                "task_id": str(review.get("task_id") or payload.get("task_id") or ""),
                "text": text,
            }
        )
    for task in session.get("evidence_tasks") or []:
        if not isinstance(task, dict) or str(task.get("status") or "") != "resolved":
            continue
        review = task.get("review") if isinstance(task.get("review"), dict) else {}
        text = " ".join(
            str(value or "")
            for value in [
                task.get("task_id"),
                task.get("type"),
                task.get("prompt"),
                task.get("source"),
                task.get("claim_id"),
                review.get("notes"),
                review.get("action"),
            ]
        )
        rows.append(
            {
                "evidence_id": str(task.get("task_id") or f"resolved_task_{len(rows) + 1}"),
                "kind": "resolved_task",
                "action": str(review.get("action") or "resolved"),
                "task_id": str(task.get("task_id") or ""),
                "claim_id": str(task.get("claim_id") or ""),
                "text": text,
            }
        )
    return rows


def _session_outcome_records(session: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(session, dict):
        return []
    rows = []
    for outcome in session.get("outcomes") or []:
        if not isinstance(outcome, dict):
            continue
        rows.append(
            {
                "evidence_id": str(outcome.get("outcome_id") or f"outcome_{len(rows) + 1}"),
                "kind": "outcome",
                "decision": str(outcome.get("decision") or outcome.get("aoi_actual_status") or ""),
                "text": " ".join(str(outcome.get(key) or "") for key in ["decision", "aoi_actual_status", "notes"]),
            }
        )
    return rows


def _measurement_type_compatible(gate_type: str, evidence_type: str) -> bool:
    gate = _norm_text(gate_type)
    evidence = _norm_text(evidence_type)
    if not gate or gate == "measurement":
        return True
    groups = {
        "voltage": {"voltage", "volt", "logic level", "logic_level", "polarity"},
        "polarity": {"polarity", "voltage", "volt"},
        "continuity": {"continuity", "resistance", "ohm", "ground"},
        "current_limit": {"current_limit", "current limit", "current", "amps", "amp", "supply limit"},
        "load_current": {"load_current", "load current", "current", "amps", "amp"},
        "logic_level": {"logic_level", "logic level", "voltage", "volt", "level"},
        "functional_check": {"functional_check", "functional", "programming", "usb", "uart", "boot", "logs", "enumeration"},
        "review": {"review", "accepted", "corrected", "resolved"},
    }
    allowed = groups.get(gate, {gate})
    return any(token in evidence for token in allowed)


def _gate_text_match(gate: Dict[str, Any], evidence: Dict[str, Any]) -> bool:
    gate_target = str(gate.get("target") or "")
    evidence_target = str(evidence.get("target") or "")
    gate_compact = _compact_text(gate_target)
    evidence_compact = _compact_text(evidence_target)
    evidence_blob = _compact_text(evidence.get("text") or evidence_target)
    gate_refs = {token.upper() for token in re.findall(r"\b(?:J|P|X|CN)\d+\b", gate_target, re.I)}
    evidence_refs = {token.upper() for token in re.findall(r"\b(?:J|P|X|CN)\d+\b", evidence_target, re.I)}
    if gate_refs and evidence_refs and not (gate_refs & evidence_refs):
        return False
    if gate_compact and (gate_compact in evidence_blob or evidence_compact in gate_compact):
        return True
    target_tokens = [_compact_text(token) for token in _text_tokens(gate_target) if len(_compact_text(token)) >= 2]
    if gate_refs and target_tokens:
        return all(token in evidence_blob for token in target_tokens)
    if len(target_tokens) > 1 and ":" in gate_target:
        return all(token in evidence_blob for token in target_tokens)
    if target_tokens and any(token in evidence_blob for token in target_tokens):
        return True
    for token in gate.get("evidence") or []:
        compact = _compact_text(token)
        if len(compact) >= 2 and compact in evidence_blob:
            return True
    return False


def _measurement_pass_status(gate: Dict[str, Any], evidence: Dict[str, Any]) -> Tuple[str, str]:
    gate_type = str(gate.get("type") or "")
    value = evidence.get("value")
    value_text = _norm_text(f"{value} {evidence.get('unit') or ''} {evidence.get('notes') or ''}")
    if any(term in value_text for term in ["fail", "failed", "open", "short", "reversed", "wrong", "bad", "no continuity"]):
        return "failed", "evidence explicitly reports a failed condition"
    if gate_type == "voltage":
        expected_v = _extract_first_number(gate.get("expected"))
        measured_v = _extract_first_number(value)
        if expected_v is not None and measured_v is not None:
            tolerance = max(0.2, expected_v * 0.12)
            if abs(measured_v - expected_v) <= tolerance:
                return "closed", f"measured {measured_v:g} V within expected range"
            return "failed", f"measured {measured_v:g} V outside expected {expected_v:g} V range"
    if gate_type in {"polarity", "continuity", "logic_level", "functional_check", "review"}:
        if any(term in value_text for term in ["pass", "ok", "good", "correct", "positive", "enumerated", "flashed", "reviewed", "accepted"]):
            return "closed", "evidence reports a passing condition"
    if gate_type in {"current_limit", "load_current"}:
        measured_a = _amps_from_measurement(value, evidence.get("unit"))
        if measured_a is not None and measured_a > 0:
            return "closed", f"recorded {measured_a:g} A"
        if value is not None:
            return "failed", "current measurement is not a positive numeric value"
    if value is not None or evidence.get("notes"):
        return "closed", "matching evidence was recorded"
    return "open", "matching evidence is incomplete"


def _matching_evidence_for_gate(
    gate: Dict[str, Any],
    measurements: List[Dict[str, Any]],
    reviews: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    gate_type = str(gate.get("type") or "measurement")
    matched = []
    if gate_type == "review":
        for review in reviews:
            text = _compact_text(review.get("text") or "")
            gate_id = _compact_text(gate.get("measurement_id") or "")
            target = _compact_text(gate.get("target") or "")
            prompt = _compact_text(gate.get("prompt") or "")
            if (gate_id and gate_id in text) or (target and target in text) or (prompt and prompt[:40] in text):
                matched.append(review)
        return matched

    for measurement in measurements:
        if not _measurement_type_compatible(gate_type, str(measurement.get("type") or "")):
            continue
        if gate_type == "logic_level":
            blob = _norm_text(measurement.get("text") or "")
            if not any(term in blob for term in ["logic", "signal", "idle", "high", "gpio", "tx", "rx", "scl", "sda", "pwm"]):
                continue
        if _gate_text_match(gate, measurement):
            matched.append(measurement)
    return matched


def _apply_session_evidence(
    measurement_plan: List[Dict[str, Any]],
    session: Optional[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    measurements = _session_measurement_records(session)
    reviews = _session_review_records(session)
    outcomes = _session_outcome_records(session)
    closed = 0
    failed = 0
    open_count = 0
    enriched: List[Dict[str, Any]] = []
    for gate in measurement_plan:
        row = dict(gate)
        matches = _matching_evidence_for_gate(row, measurements, reviews)
        status = "open"
        reason = "no matching session evidence recorded"
        support = []
        if matches:
            statuses = []
            for match in matches:
                if match.get("kind") == "measurement":
                    next_status, next_reason = _measurement_pass_status(row, match)
                else:
                    next_status, next_reason = "closed", "resolved by operator review"
                statuses.append((next_status, next_reason, match))
            failed_match = next((item for item in statuses if item[0] == "failed"), None)
            closed_match = next((item for item in statuses if item[0] == "closed"), None)
            chosen = failed_match or closed_match or statuses[0]
            status = chosen[0]
            reason = chosen[1]
            support = [
                {
                    "evidence_id": match.get("evidence_id"),
                    "kind": match.get("kind"),
                    "type": match.get("type") or match.get("action"),
                    "target": match.get("target"),
                    "value": match.get("value"),
                    "unit": match.get("unit"),
                }
                for _, _, match in statuses
            ]
        row["status"] = status
        row["closure_reason"] = reason
        row["supporting_evidence"] = support[:6]
        if status == "closed":
            closed += 1
        elif status == "failed":
            failed += 1
        else:
            open_count += 1
        enriched.append(row)
    blocking_open = [
        row
        for row in enriched
        if row.get("status") != "closed" and row.get("blocks_before_done")
    ]
    summary = {
        "measurement_count": len(measurements),
        "review_count": len(reviews),
        "outcome_count": len(outcomes),
        "gate_count": len(enriched),
        "closed_gate_count": closed,
        "open_gate_count": open_count,
        "failed_gate_count": failed,
        "blocking_open_count": len(blocking_open),
        "closed_ratio": round(closed / max(len(enriched), 1), 3),
        "blocking_open_measurements": [
            {
                "measurement_id": row.get("measurement_id"),
                "prompt": row.get("prompt"),
                "status": row.get("status"),
                "priority": row.get("priority"),
            }
            for row in blocking_open[:20]
        ],
    }
    return enriched, summary


def _adapter_requirements(connector_contracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    adapters: List[Dict[str, Any]] = []
    seen = set()

    def add(name: str, reason: str, requirements: List[str], connector_ref: str) -> None:
        key = (name, connector_ref)
        if key in seen:
            return
        seen.add(key)
        adapters.append(
            {
                "name": name,
                "connector_ref": connector_ref,
                "reason": reason,
                "requirements": requirements,
            }
        )

    for connector in connector_contracts:
        ref = str(connector.get("connector_ref") or "")
        power_nets = connector.get("power_nets") or []
        signal_nets = connector.get("signal_nets") or []
        roles = {str(pin.get("role") or "") for pin in connector.get("pins") or []}
        if power_nets:
            add(
                "power-entry protection",
                "Connector exposes board or external power.",
                [
                    "current-limited supply during first power",
                    "polarity confirmation",
                    "fuse or resettable protection for external harness use",
                    "reverse/backfeed prevention if another board can drive the same rail",
                ],
                ref,
            )
        if signal_nets:
            add(
                "logic-level interface",
                "Connector exposes logic/control nets for another board.",
                [
                    "common ground or isolation decision",
                    "logic-high voltage measurement",
                    "series resistance or level shifting if target logic differs",
                ],
                ref,
            )
        if roles & {"uart"}:
            add(
                "uart crossover",
                "UART-like signal pair was recovered.",
                ["TX-to-RX crossover", "RX-to-TX crossover", "shared ground", "baud/log verification"],
                ref,
            )
        if roles & {"i2c"}:
            add(
                "i2c bus compatibility",
                "I2C-like signal pair was recovered.",
                ["single pull-up domain decision", "SCL/SDA continuity", "target voltage compatibility"],
                ref,
            )
        if roles & {"pwm"} or any("SERVO" in str(net).upper() for net in power_nets + signal_nets):
            add(
                "actuation/load interface",
                "PWM or servo/load nets are exposed.",
                ["external load supply measurement", "common ground", "do not power load from MCU rail", "current draw check"],
                ref,
            )
    return adapters[:30]


def _splice_contract(
    structure: Dict[str, Any],
    connector_contracts: List[Dict[str, Any]],
    measurement_plan: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    entry_points = [
        {
            "connector_ref": row.get("connector_ref"),
            "splice_role": row.get("splice_role"),
            "semantic_role": row.get("semantic_role"),
            "interfaces": [item.get("interface") for item in (row.get("interfaces") or []) if isinstance(item, dict)],
            "power_nets": row.get("power_nets") or [],
            "signal_nets": row.get("signal_nets") or [],
        }
        for row in connector_contracts
        if row.get("splice_allowed_after_gates")
    ]
    required_rows = [
        row
        for row in measurement_plan
        if "splicing" in (row.get("blocks_before_done") or []) and row.get("status", "open") != "closed"
    ]
    required = [row.get("prompt") for row in required_rows]
    high_risk_actions = [
        row.get("action")
        for row in risks
        if row.get("severity") in {"critical", "error", "high"} and row.get("action")
    ]
    closed_risk_targets = {
        str(row.get("target") or "")
        for row in measurement_plan
        if row.get("stage") == "risk_closure" and row.get("status") == "closed"
    }
    high_risk_actions = [
        row.get("action")
        for row in risks
        if row.get("severity") in {"critical", "error", "high"}
        and row.get("action")
        and str(row.get("topic") or "") not in closed_risk_targets
    ]
    wiring_contracts = []
    for connector in connector_contracts:
        ref = str(connector.get("connector_ref") or "")
        for interface in connector.get("interfaces") or []:
            if not isinstance(interface, dict):
                continue
            name = str(interface.get("interface") or "")
            if not name:
                continue
            if name == "power":
                rule = "connect matching ground first, then current-limited power after polarity and voltage checks"
            elif name == "uart":
                rule = "cross TX/RX, share ground, and verify logic level before enabling firmware traffic"
            elif name == "i2c":
                rule = "connect SDA/SCL with one compatible pull-up domain and shared ground"
            elif name == "usb2":
                rule = "preserve D+/D- pairing, do not backfeed VBUS, and current-limit first attach"
            else:
                rule = f"match {name} signals by function and verify voltage/reference before use"
            wiring_contracts.append(
                {
                    "connector_ref": ref,
                    "interface": name,
                    "signals": interface.get("signals") or [],
                    "rule": rule,
                }
            )

    return {
        "mode": "circuit_board_splice_contract",
        "verdict": "blocked_until_measurements" if required or high_risk_actions else "ready_for_splice_review",
        "entry_points": entry_points,
        "adapter_requirements": _adapter_requirements(connector_contracts),
        "wiring_contracts": wiring_contracts,
        "do_not_connect_until": _dedupe_text([*required, *high_risk_actions], limit=30),
        "open_blocking_gate_count": len(required_rows) + len(high_risk_actions),
        "stop_conditions": [
            "unknown or reversed polarity on any power entry",
            "short or low resistance between a power rail and ground",
            "logic high voltage exceeds the receiving device tolerance",
            "load current is unknown or above connector/regulator capability",
            "battery, mains, inverter, or high-voltage section is not isolated",
        ],
        "scope": "electrical board-to-board or board-to-harness splicing only",
    }


def _power_tree(structure: Dict[str, Any]) -> Dict[str, Any]:
    rails = (structure.get("power") or {}).get("rails") or []
    regulators = (structure.get("power") or {}).get("regulators") or []
    edges = []
    for reg in regulators:
        if not isinstance(reg, dict):
            continue
        vin = _normalize_net(str(reg.get("vin_net") or ""))
        vout = _normalize_net(str(reg.get("vout_net") or ""))
        if vin and vout:
            edges.append(
                {
                    "source_net": vin,
                    "target_net": vout,
                    "via": reg.get("ref"),
                    "kind": reg.get("kind") or "regulator",
                    "confidence": reg.get("confidence"),
                }
            )
    root_rails = [
        row.get("net")
        for row in rails
        if isinstance(row, dict) and (row.get("is_input_root") or _is_source_like_power_net(str(row.get("net") or "")))
    ]
    generated_rails = [edge["target_net"] for edge in edges]
    return {
        "rails": rails,
        "regulators": regulators,
        "edges": edges,
        "root_rails": _dedupe_text(root_rails),
        "generated_rails": _dedupe_text(generated_rails),
        "unknown_source_rails": [
            row.get("net")
            for row in rails
            if isinstance(row, dict)
            and row.get("net")
            and row.get("net") not in root_rails
            and row.get("net") not in generated_rails
            and not is_ground_net(str(row.get("net")))
        ],
    }


def _capability_contract(structure: Dict[str, Any], connector_contracts: List[Dict[str, Any]]) -> Dict[str, Any]:
    runtime = structure.get("controller_runtime") if isinstance(structure.get("controller_runtime"), dict) else {}
    power_control = structure.get("power_control_analysis") if isinstance(structure.get("power_control_analysis"), dict) else {}
    capabilities: List[str] = []
    if runtime.get("controllers"):
        capabilities.append("firmware_controller")
    if runtime.get("programming_paths"):
        capabilities.append("programmable_debuggable")
    for connector in connector_contracts:
        roles = {str(pin.get("role") or "") for pin in connector.get("pins") or []}
        if "i2c" in roles:
            capabilities.append("i2c_expansion")
        if "uart" in roles:
            capabilities.append("uart_link")
        if "usb2" in roles:
            capabilities.append("usb_device_or_bridge")
        if "pwm" in roles:
            capabilities.append("pwm_actuation")
        if connector.get("power_nets"):
            capabilities.append("power_distribution_or_input")
    summary = power_control.get("summary") if isinstance(power_control.get("summary"), dict) else {}
    if _safe_int(summary.get("motor_driver_count"), 0) or _safe_int(summary.get("actuation_connector_count"), 0):
        capabilities.append("load_or_motor_control")
    return {
        "primary_role": structure.get("primary_role"),
        "capabilities": _dedupe_text(capabilities, limit=20),
        "firmware_surface": runtime.get("firmware_surface") or {},
        "usable_ports": [
            {
                "connector_ref": row.get("connector_ref"),
                "splice_role": row.get("splice_role"),
                "interfaces": [item.get("interface") for item in row.get("interfaces") or [] if isinstance(item, dict)],
                "power_nets": row.get("power_nets") or [],
                "signal_nets": row.get("signal_nets") or [],
            }
            for row in connector_contracts
        ],
    }


def _physics_component_id(value: Any, category: str = "") -> Optional[str]:
    text = str(value or "").lower()
    blob = f"{text} {category.lower()}"
    if "esp32" in blob:
        return "esp32"
    if "arduino" in blob or "atmega328" in blob:
        return "arduino_uno"
    if "bme280" in blob or "bmp280" in blob:
        return "bme280"
    if "oled" in blob or "ssd1306" in blob:
        return "oled_ssd1306"
    if "servo" in blob or "sg90" in blob:
        return "servo_sg90"
    if "hc-sr04" in blob or "hcsr04" in blob:
        return "hc_sr04"
    return None


def _default_source_limit_for_connector(connector: Dict[str, Any], rail: str) -> Optional[float]:
    text = f"{connector.get('connector_ref') or ''} {connector.get('value') or ''} {connector.get('footprint') or ''} {rail}".upper()
    if "USB" in text or rail.upper() in {"VBUS", "VUSB", "USB_5V"}:
        return 0.5
    if "SERVO" in text or "MOTOR" in text or "LOAD" in text:
        return None
    if "JST" in text or "VIN" in text or "BAT" in text:
        return None
    return None


def _connector_is_source_candidate(connector: Dict[str, Any], rail: str) -> bool:
    text = f"{connector.get('value') or ''} {connector.get('footprint') or ''} {rail}".upper()
    if str(connector.get("splice_role") or "") == "power_entry":
        return True
    return any(token in text for token in ["_IN", " IN", "VIN", "VBUS", "USB", "BAT", "POWER", "PWR", "SUPPLY"])


def _amps_from_measurement(value: Any, unit: Any) -> Optional[float]:
    number = _extract_first_number(value)
    if number is None:
        return None
    unit_text = str(unit or "").strip().lower()
    if unit_text in {"ma", "milliamp", "milliamps", "milliamperes"}:
        return number / 1000.0
    return number


def _session_source_limits(session: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    limits = []
    for measurement in _session_measurement_records(session):
        text = _norm_text(measurement.get("text") or "")
        mtype = _norm_text(measurement.get("type") or "")
        if "current" not in mtype and "current limit" not in text and "supply limit" not in text:
            continue
        amps = _amps_from_measurement(measurement.get("value"), measurement.get("unit"))
        if amps is None or amps <= 0:
            continue
        limits.append(
            {
                "target": str(measurement.get("target") or ""),
                "target_compact": _compact_text(measurement.get("target") or ""),
                "available_current_a": amps,
                "source": measurement.get("evidence_id"),
                "notes": measurement.get("notes"),
            }
        )
    return limits


def _source_limit_for_target(target: str, session_limits: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    target_compact = _compact_text(target)
    if not target_compact:
        return None
    for limit in session_limits:
        limit_target = str(limit.get("target_compact") or "")
        if limit_target and (target_compact in limit_target or limit_target in target_compact):
            return limit
    for token in _text_tokens(target):
        compact = _compact_text(token)
        if len(compact) < 2:
            continue
        for limit in session_limits:
            if compact in str(limit.get("target_compact") or ""):
                return limit
    return None


def _component_load_estimates(
    components: Dict[str, Any],
    pinmap: Dict[str, Dict[str, str]],
    category_by_ref: Dict[str, str],
    component_intelligence: Dict[str, Any],
) -> List[Dict[str, Any]]:
    engine = CircuitPhysicsEngine()
    loads: List[Dict[str, Any]] = []
    known_by_ref = {
        str(row.get("ref")): row
        for row in component_intelligence.get("components") or []
        if isinstance(row, dict)
    }
    for ref, raw_meta in sorted((components or {}).items()):
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        category = category_by_ref.get(ref, "other")
        if category in {"connector", "resistor", "capacitor", "inductor", "diode", "regulator", "other"}:
            continue
        value = str(meta.get("value") or "")
        physics_id = _physics_component_id(value, category)
        current_a = None
        typical_a = None
        operating_voltage = None
        if physics_id and physics_id in engine.component_specs:
            spec = engine.component_specs[physics_id].electrical
            current_a = float(spec.max_current)
            typical_a = float(spec.typical_current)
            operating_voltage = float(spec.operating_voltage)
        elif "CP210" in value.upper() or "CH340" in value.upper() or "FT232" in value.upper():
            physics_id = "usb_uart_bridge"
            current_a = 0.10
            typical_a = 0.03
            operating_voltage = 3.3

        pinout_row = known_by_ref.get(ref) or {}
        candidate_rails = []
        for pin_row in pinout_row.get("pin_maps") or []:
            if not isinstance(pin_row, dict):
                continue
            if pin_row.get("pin_type") == "power" and pin_row.get("net"):
                candidate_rails.append(str(pin_row["net"]))
        if not candidate_rails:
            candidate_rails = [
                _normalize_net(net)
                for net in (pinmap.get(ref) or {}).values()
                if _net_kind(_normalize_net(net)) == "power"
            ]
        candidate_rails = _dedupe_text(candidate_rails, limit=4)
        if not candidate_rails:
            continue
        target_rail = candidate_rails[0]
        if operating_voltage is not None:
            matching = [
                rail
                for rail in candidate_rails
                if (_infer_nominal_voltage(rail) is not None and abs((_infer_nominal_voltage(rail) or 0.0) - operating_voltage) <= 0.4)
            ]
            if matching:
                target_rail = matching[0]
        loads.append(
            {
                "load_id": ref,
                "kind": "component",
                "ref": ref,
                "value": value,
                "physics_id": physics_id,
                "rail": target_rail,
                "nominal_v": _infer_nominal_voltage(target_rail) or operating_voltage,
                "typical_current_a": typical_a,
                "max_current_a": current_a,
                "confidence": 0.78 if current_a is not None else 0.35,
                "source": "component_spec" if current_a is not None else "pinout_power_pin",
            }
        )
    return loads


def _external_connector_load_estimates(connector_contracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    loads: List[Dict[str, Any]] = []
    seen = set()
    for connector in connector_contracts:
        ref = str(connector.get("connector_ref") or "")
        power_nets = connector.get("power_nets") or []
        signal_nets = connector.get("signal_nets") or []
        roles = {str(pin.get("role") or "") for pin in connector.get("pins") or []}
        text = f"{connector.get('value') or ''} {' '.join(power_nets)} {' '.join(signal_nets)}".upper()
        if not power_nets:
            continue
        if not signal_nets and any(_connector_is_source_candidate(connector, rail) for rail in power_nets):
            continue
        candidate = None
        if "SERVO" in text or "PWM" in text or "pwm" in roles:
            candidate = {
                "physics_id": "servo_sg90",
                "label": "external servo/load candidate",
                "typical_current_a": 0.10,
                "max_current_a": 0.65,
            }
        elif str(connector.get("semantic_role") or "") == "actuation":
            candidate = {
                "physics_id": "external_actuator",
                "label": "external actuator/load candidate",
                "typical_current_a": None,
                "max_current_a": None,
            }
        if not candidate:
            continue
        for rail in power_nets:
            key = (ref, rail, candidate["physics_id"])
            if key in seen:
                continue
            seen.add(key)
            loads.append(
                {
                    "load_id": f"{ref}:{candidate['physics_id']}",
                    "kind": "external_splice_load",
                    "ref": ref,
                    "value": candidate["label"],
                    "physics_id": candidate["physics_id"],
                    "rail": rail,
                    "nominal_v": _infer_nominal_voltage(rail),
                    "typical_current_a": candidate["typical_current_a"],
                    "max_current_a": candidate["max_current_a"],
                    "confidence": 0.62 if candidate["max_current_a"] is not None else 0.35,
                    "source": "connector_role",
                    "requires_source_limit_evidence": True,
                }
            )
    return loads


def _source_estimates(
    power_tree: Dict[str, Any],
    connector_contracts: List[Dict[str, Any]],
    component_intelligence: Dict[str, Any],
    session: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    session_limits = _session_source_limits(session)
    sources: List[Dict[str, Any]] = []
    seen = set()

    def add(rail: str, source_id: str, kind: str, nominal_v: Optional[float], current_a: Optional[float], confidence: float, evidence: List[str]) -> None:
        key = (rail, source_id)
        if not rail or key in seen:
            return
        seen.add(key)
        sources.append(
            {
                "source_id": source_id,
                "kind": kind,
                "rail": rail,
                "nominal_v": nominal_v,
                "available_current_a": current_a,
                "confidence": confidence,
                "evidence": evidence,
            }
        )

    for connector in connector_contracts:
        for rail in connector.get("power_nets") or []:
            if not _connector_is_source_candidate(connector, rail):
                continue
            target = f"{connector.get('connector_ref') or ''} {connector.get('value') or ''} {rail}"
            measured = _source_limit_for_target(target, session_limits)
            default_limit = _default_source_limit_for_connector(connector, rail)
            add(
                rail,
                f"{connector.get('connector_ref') or 'connector'}:{rail}",
                "connector_power_entry",
                _infer_nominal_voltage(rail),
                float(measured["available_current_a"]) if measured else default_limit,
                0.88 if measured else 0.62 if default_limit is not None else 0.42,
                [str(connector.get("connector_ref") or ""), str(measured.get("source") if measured else "connector_contract")],
            )

    pinout_by_ref = {
        str(row.get("ref")): row
        for row in component_intelligence.get("components") or []
        if isinstance(row, dict)
    }
    for reg in power_tree.get("regulators") or []:
        if not isinstance(reg, dict):
            continue
        vout = _normalize_net(str(reg.get("vout_net") or ""))
        if not vout:
            continue
        current_a = None
        ref = str(reg.get("ref") or "")
        pinout = (pinout_by_ref.get(ref) or {}).get("pinout") or {}
        power_pins = pinout.get("power_pins") if isinstance(pinout, dict) else []
        candidates = [
            _safe_float(pin.get("max_current_ma"), 0.0) / 1000.0
            for pin in (power_pins or [])
            if isinstance(pin, dict) and pin.get("max_current_ma")
        ]
        if candidates:
            current_a = max(candidates)
        elif "1117" in ref.upper() or "AMS1117" in str(reg.get("note") or "").upper():
            current_a = 1.0
        elif reg.get("kind"):
            current_a = 0.5
        add(
            vout,
            f"{ref or 'regulator'}:{vout}",
            "regulator_output",
            reg.get("vout_nominal_v") or _infer_nominal_voltage(vout),
            current_a,
            0.7 if current_a is not None else 0.45,
            [ref, str(reg.get("kind") or "regulator")],
        )
    return sources


def _rail_load_rollup(loads: List[Dict[str, Any]], power_tree: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    by_rail: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for load in loads:
        rail = _normalize_net(str(load.get("rail") or ""))
        if rail:
            by_rail[rail].append(load)
    for reg in power_tree.get("regulators") or []:
        if not isinstance(reg, dict):
            continue
        vin = _normalize_net(str(reg.get("vin_net") or ""))
        vout = _normalize_net(str(reg.get("vout_net") or ""))
        if not vin or not vout:
            continue
        downstream = by_rail.get(vout) or []
        max_current = sum(float(load.get("max_current_a") or 0.0) for load in downstream if load.get("max_current_a") is not None)
        typical_current = sum(float(load.get("typical_current_a") or 0.0) for load in downstream if load.get("typical_current_a") is not None)
        if max_current <= 0 and typical_current <= 0:
            continue
        vin_v = _infer_nominal_voltage(vin)
        vout_v = reg.get("vout_nominal_v") or _infer_nominal_voltage(vout)
        current_scale = 1.0
        if vin_v and vout_v and vin_v > 0:
            current_scale = min(1.2, max(0.1, float(vout_v) / float(vin_v)))
        by_rail[vin].append(
            {
                "load_id": f"regulator_input:{reg.get('ref') or vout}",
                "kind": "regulator_input_equivalent",
                "ref": reg.get("ref"),
                "value": f"input current for {vout}",
                "rail": vin,
                "nominal_v": vin_v,
                "typical_current_a": typical_current * current_scale if typical_current else None,
                "max_current_a": max_current * current_scale if max_current else None,
                "confidence": 0.58,
                "source": "regulator_downstream_rollup",
            }
        )
    return by_rail


def _simulation_issue_dict(issue: Any) -> Dict[str, Any]:
    return {
        "severity": getattr(issue, "severity", "warning"),
        "component": getattr(issue, "component", ""),
        "issue": getattr(issue, "issue", ""),
        "explanation": getattr(issue, "explanation", ""),
        "physics_data": getattr(issue, "physics_data", {}) or {},
        "solution": getattr(issue, "solution", ""),
    }


def _solver_model(
    sources: List[Dict[str, Any]],
    loads_by_rail: Dict[str, List[Dict[str, Any]]],
    power_tree: Dict[str, Any],
) -> Dict[str, Any]:
    net = CircuitNetlist()
    constraints = PowerTreeConstraints(
        source_limits=[
            SourceCurrentLimit(
                source_name=f"SRC::{source['rail']}",
                max_current_a=float(source["available_current_a"]),
            )
            for source in sources
            if source.get("available_current_a") is not None and source.get("kind") != "regulator_output"
        ],
        max_trace_drop_v=0.25,
    )
    source_rails = {
        str(source.get("rail"))
        for source in sources
        if source.get("available_current_a") is not None and source.get("kind") != "regulator_output"
    }
    generated_rails = set()

    for source in sources:
        if source.get("kind") == "regulator_output":
            continue
        rail = str(source.get("rail") or "")
        volts = source.get("nominal_v")
        if not rail or volts is None or source.get("available_current_a") is None:
            continue
        net.voltage_sources.append(VoltageSource(name=f"SRC::{rail}", n_plus=rail, n_minus="0", volts=float(volts)))

    for reg in power_tree.get("regulators") or []:
        if not isinstance(reg, dict):
            continue
        vin = _normalize_net(str(reg.get("vin_net") or ""))
        vout = _normalize_net(str(reg.get("vout_net") or ""))
        if not vin or not vout or vin not in source_rails:
            continue
        generated_rails.add(vout)
        net.ldos.append(
            LDO(
                name=str(reg.get("ref") or f"LDO_{vout}"),
                vin=vin,
                vout=vout,
                gnd=str(reg.get("gnd_net") or "0"),
                vout_nom_v=float(reg.get("vout_nominal_v") or _infer_nominal_voltage(vout) or 3.3),
                dropout_v=0.3,
                max_current_a=1.0,
                quiescent_current_a=0.002,
                r_theta_ja_c_per_w=60.0,
            )
        )

    included_rails = set(source_rails) | generated_rails
    omitted_loads = []
    for rail, loads in loads_by_rail.items():
        if rail not in included_rails:
            omitted_loads.extend(loads)
            continue
        for load in loads:
            if load.get("kind") == "regulator_input_equivalent":
                continue
            amps = load.get("max_current_a")
            if amps is None:
                omitted_loads.append(load)
                continue
            net.loads_cc.append(
                ConstantCurrentLoad(
                    name=str(load.get("load_id") or f"load_{len(net.loads_cc) + 1}"),
                    node=rail,
                    amps=float(amps),
                    gnd="0",
                )
            )
        nominal = _infer_nominal_voltage(rail)
        if nominal is not None:
            net.voltage_constraints.append(
                VoltageConstraint(
                    name=f"RAIL::{rail}",
                    node=rail,
                    gnd="0",
                    min_v=max(0.0, nominal * 0.9),
                    max_v=nominal * 1.1,
                )
            )

    if not net.voltage_sources:
        return {
            "available": False,
            "reason": "no rails have known source voltage and current limit",
            "omitted_load_count": len(omitted_loads),
        }
    try:
        results, issues = validate_pcb_power_tree(net, constraints=constraints)
    except Exception as exc:
        return {
            "available": False,
            "reason": f"solver_failed: {exc}",
            "included_source_count": len(net.voltage_sources),
            "included_load_count": len(net.loads_cc),
            "omitted_load_count": len(omitted_loads),
        }
    solution = results.get("solution")
    return {
        "available": True,
        "included_source_count": len(net.voltage_sources),
        "included_ldo_count": len(net.ldos),
        "included_load_count": len(net.loads_cc),
        "omitted_load_count": len(omitted_loads),
        "included_rails": sorted(included_rails),
        "converged": bool(results.get("converged")),
        "node_voltages": dict(getattr(solution, "node_v", {}) or {}),
        "source_currents": dict(getattr(solution, "vsource_i", {}) or {}),
        "power_report": results.get("power_report") or {},
        "issues": [_simulation_issue_dict(issue) for issue in issues],
    }


def _electrical_viability(
    power_tree: Dict[str, Any],
    connector_contracts: List[Dict[str, Any]],
    component_intelligence: Dict[str, Any],
    components: Dict[str, Any],
    pinmap: Dict[str, Dict[str, str]],
    category_by_ref: Dict[str, str],
    session: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    component_loads = _component_load_estimates(components, pinmap, category_by_ref, component_intelligence)
    external_loads = _external_connector_load_estimates(connector_contracts)
    loads = component_loads + external_loads
    sources = _source_estimates(power_tree, connector_contracts, component_intelligence, session)
    loads_by_rail = _rail_load_rollup(loads, power_tree)
    sources_by_rail: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for source in sources:
        sources_by_rail[str(source.get("rail") or "")].append(source)

    rail_names = sorted(set(loads_by_rail.keys()) | set(sources_by_rail.keys()) | {str(row.get("net")) for row in power_tree.get("rails") or [] if isinstance(row, dict)})
    rail_budgets = []
    issues: List[Dict[str, Any]] = []
    for rail in rail_names:
        rail_loads = loads_by_rail.get(rail) or []
        rail_sources = sources_by_rail.get(rail) or []
        known_load_a = sum(float(load.get("max_current_a") or 0.0) for load in rail_loads if load.get("max_current_a") is not None)
        unknown_loads = [load for load in rail_loads if load.get("max_current_a") is None]
        known_source_a = sum(float(source.get("available_current_a") or 0.0) for source in rail_sources if source.get("available_current_a") is not None)
        unknown_sources = [source for source in rail_sources if source.get("available_current_a") is None]
        if known_load_a > 0 and known_source_a <= 0:
            status = "missing_source_limit"
            issues.append(
                _risk(
                    "high",
                    "source_limit_missing",
                    f"{rail} has {known_load_a:.3f} A estimated load but no confirmed source current limit.",
                    f"Record source current limit or supply capability for {rail} before splice/power-up.",
                    evidence=[rail],
                )
            )
        elif known_source_a > 0 and known_load_a > known_source_a:
            status = "overcurrent"
            issues.append(
                _risk(
                    "critical",
                    "rail_overcurrent",
                    f"{rail} estimated load {known_load_a:.3f} A exceeds available {known_source_a:.3f} A.",
                    "Use a higher-current source, reduce load, or split the rail before powering.",
                    evidence=[rail],
                )
            )
        elif unknown_loads:
            status = "unknown_load"
            issues.append(
                _risk(
                    "medium",
                    "load_unknown",
                    f"{rail} has load(s) without current estimates.",
                    f"Measure or identify load current for {rail}.",
                    evidence=[rail],
                )
            )
        elif unknown_sources and known_load_a > 0:
            status = "source_limit_unconfirmed"
        elif known_load_a > 0:
            status = "ok"
        else:
            status = "no_estimated_load"
        margin = known_source_a - known_load_a if known_source_a > 0 else None
        rail_budgets.append(
            {
                "rail": rail,
                "nominal_v": _infer_nominal_voltage(rail),
                "status": status,
                "estimated_load_a": round(known_load_a, 4),
                "available_current_a": round(known_source_a, 4) if known_source_a > 0 else None,
                "margin_a": round(margin, 4) if margin is not None else None,
                "source_count": len(rail_sources),
                "unknown_source_count": len(unknown_sources),
                "load_count": len(rail_loads),
                "unknown_load_count": len(unknown_loads),
                "sources": rail_sources,
                "loads": rail_loads,
            }
        )

    solver = _solver_model(sources, loads_by_rail, power_tree)
    if any(issue.get("severity") == "critical" for issue in issues):
        verdict = "overcurrent_blocked"
    elif any(row.get("status") == "missing_source_limit" for row in rail_budgets):
        verdict = "blocked_missing_source_limits"
    elif any(row.get("status") in {"unknown_load", "source_limit_unconfirmed"} for row in rail_budgets):
        verdict = "needs_measurements"
    elif solver.get("issues"):
        verdict = "solver_issues"
    else:
        verdict = "viable_under_current_assumptions"
    return {
        "mode": "circuit_electrical_viability",
        "verdict": verdict,
        "rail_budgets": rail_budgets,
        "load_estimates": loads,
        "source_estimates": sources,
        "issues": issues,
        "solver_model": solver,
        "assumptions": [
            "component currents are estimated from known library specs where available",
            "external servo/load current is inferred from connector naming and must be measured or confirmed",
            "source limits come from USB defaults or explicit session current-limit measurements",
            "solver output is advisory unless source limits, load current, and rail measurements are grounded",
        ],
    }


def _next_tasks(
    measurement_plan: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
    component_intelligence: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    seen = set()

    def add(task_type: str, prompt: str, priority: int, source: str, gate_id: str = "") -> None:
        text = str(prompt or "").strip()
        key = (task_type, text.lower())
        if not text or key in seen:
            return
        seen.add(key)
        tasks.append(
            {
                "task_type": task_type,
                "prompt": text,
                "priority": priority,
                "source": source,
                "gate_id": gate_id,
                "usable_for": ["circuit_graph", "bringup", "repair", "splicing", "training"],
            }
        )

    for row in measurement_plan[:20]:
        if row.get("status") == "closed":
            continue
        add("measurement" if row.get("type") != "review" else "review", str(row.get("prompt") or ""), _safe_int(row.get("priority"), 3), "circuit_graph_measurement", str(row.get("measurement_id") or ""))
    for risk in risks:
        if risk.get("severity") in {"critical", "error", "high"}:
            add("review", str(risk.get("action") or risk.get("message") or ""), 1, f"circuit_graph_risk:{risk.get('topic')}")
    if isinstance(component_intelligence, dict):
        for item in component_intelligence.get("unresolved_active_components") or []:
            if not isinstance(item, dict):
                continue
            ref = str(item.get("ref") or "component")
            value = str(item.get("value") or "")
            add(
                "reference",
                f"Resolve datasheet/pinout for {ref} {value} before pin-level repair or splice instructions.",
                2,
                "circuit_graph_pinout",
                ref,
            )
    return tasks[:30]


def _certainty_ledger(graph: Dict[str, Any], risks: List[Dict[str, Any]], measurement_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = graph.get("summary") or {}
    gates = [
        ("components", _safe_int(summary.get("component_count"), 0) > 0, "component inventory exists"),
        ("nets", _safe_int(summary.get("net_count"), 0) > 0, "net graph exists"),
        ("power", _safe_int(summary.get("power_net_count"), 0) > 0, "power nets exist"),
        ("ground", _safe_int(summary.get("ground_net_count"), 0) > 0, "ground net exists"),
    ]
    high_risks = [risk for risk in risks if risk.get("severity") in {"critical", "error", "high"}]
    open_blockers = [
        row
        for row in measurement_plan
        if row.get("status", "open") != "closed" and row.get("blocks_before_done")
    ]
    score = (sum(1 for _, passed, _ in gates if passed) / max(len(gates), 1)) * 0.72
    if not high_risks or not open_blockers:
        score += 0.18
    if measurement_plan and not open_blockers:
        score += 0.1
    score = round(max(0.0, min(score, 0.98)), 3)
    if score >= 0.82 and not high_risks:
        level = "likely"
    elif score >= 0.55:
        level = "possible"
    else:
        level = "unknown"
    missing = []
    for gate_id, passed, label in gates:
        if not passed:
            missing.append(f"missing {label}")
    missing.extend(str(row.get("prompt") or "") for row in open_blockers[:12])
    items = [
        {
            "item_id": f"circuit_gate_{gate_id}",
            "claim_type": "circuit_graph_gate",
            "claim": label,
            "certainty": "likely" if passed else "unknown",
            "score": 1.0 if passed else 0.0,
            "next_actions": [] if passed else [f"provide evidence so {label}"],
            "usable_for": ["circuit_graph", "bringup", "repair", "splicing"],
        }
        for gate_id, passed, label in gates
    ]
    return {
        "overall": {
            "score": score,
            "level": level,
            "summary": "Circuit graph is measurement-gated; splice decisions remain blocked until required probes are closed.",
        },
        "counts": {
            "total": len(items),
            "likely": len([item for item in items if item["certainty"] == "likely"]),
            "unknown": len([item for item in items if item["certainty"] == "unknown"]),
        },
        "missing_evidence": _dedupe_text(missing, limit=20),
        "items": items,
        "training_queue": {
            "should_capture": bool(missing),
            "candidate_labels": [item["claim"] for item in items if item["certainty"] == "unknown"],
        },
    }


def _workflow_state(
    readiness: str,
    measurement_plan: List[Dict[str, Any]],
    splice_contract: Dict[str, Any],
    measurement_closure: Dict[str, Any],
) -> Dict[str, Any]:
    failed = [row for row in measurement_plan if row.get("status") == "failed"]
    open_blockers = [
        row
        for row in measurement_plan
        if row.get("status") != "closed" and row.get("blocks_before_done")
    ]
    open_optional = [
        row
        for row in measurement_plan
        if row.get("status") != "closed" and not row.get("blocks_before_done")
    ]
    if failed:
        stage = "fault_hold"
        next_action = str(failed[0].get("prompt") or "Investigate failed measurement before continuing.")
        allowed = ["inspect", "measure", "review"]
        forbidden = ["power_application", "splicing", "firmware_bringup"]
    elif readiness == "electrical_viability_hold":
        stage = "electrical_viability_hold"
        next_action = "Resolve the rail current budget before applying power or making the splice."
        allowed = ["inspect", "measure", "review", "revise_power_contract"]
        forbidden = ["power_application", "splicing", "firmware_bringup"]
    elif open_blockers:
        stage = "measurement_closure"
        next_action = str(open_blockers[0].get("prompt") or "Close the highest-priority blocking measurement.")
        allowed = ["inspect", "measure", "review"]
        forbidden = sorted({item for row in open_blockers for item in (row.get("blocks_before_done") or [])})
    elif splice_contract.get("verdict") == "ready_for_splice_review":
        stage = "splice_review"
        next_action = "Review wiring contracts, adapter requirements, and stop conditions before making the splice."
        allowed = ["review_wiring_contract", "prepare_adapter", "current_limited_powerup"]
        forbidden = []
    elif open_optional:
        stage = "bringup_measurement"
        next_action = str(open_optional[0].get("prompt") or "Close remaining bring-up measurement.")
        allowed = ["measure", "firmware_bringup", "review"]
        forbidden = []
    elif readiness == "calibrated_circuit_case":
        stage = "calibrated"
        next_action = "Record reusable learnings or export the reviewed case for training."
        allowed = ["training_export", "reuse_case", "close_session"]
        forbidden = []
    else:
        stage = "circuit_review"
        next_action = "Review the circuit graph and connector contract before external wiring."
        allowed = ["review", "measure"]
        forbidden = ["unreviewed_splicing"]
    return {
        "stage": stage,
        "readiness": readiness,
        "next_action": next_action,
        "allowed_actions": allowed,
        "forbidden_actions": forbidden,
        "progress": {
            "closed_gate_count": measurement_closure.get("closed_gate_count", 0),
            "gate_count": measurement_closure.get("gate_count", 0),
            "closed_ratio": measurement_closure.get("closed_ratio", 0.0),
            "blocking_open_count": measurement_closure.get("blocking_open_count", 0),
            "failed_gate_count": measurement_closure.get("failed_gate_count", 0),
        },
    }


def _connector_lookup(board: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(connector.get("connector_ref") or ""): connector
        for connector in board.get("connector_contracts") or []
        if isinstance(connector, dict) and connector.get("connector_ref")
    }


def _connector_pin(connector: Dict[str, Any], *, net: str = "", alias: str = "", role: str = "") -> Optional[Dict[str, Any]]:
    target_net = _normalize_net(net)
    target_alias = str(alias or "").upper()
    target_role = str(role or "").lower()
    for pin in connector.get("pins") or []:
        if not isinstance(pin, dict):
            continue
        pin_net = _normalize_net(str(pin.get("net") or ""))
        pin_role = str(pin.get("role") or "").lower()
        aliases = {str(item or "").upper() for item in pin.get("aliases") or []}
        if target_net and pin_net == target_net:
            return pin
        if target_alias and (target_alias == pin_net.upper() or target_alias in aliases):
            return pin
        if target_role and pin_role == target_role:
            return pin
    return None


def _pin_endpoint(board: Dict[str, Any], connector: Dict[str, Any], pin: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "board_id": board.get("board_id"),
        "connector_ref": connector.get("connector_ref"),
        "pin": str(pin.get("pin") or ""),
        "net": pin.get("net"),
        "role": pin.get("role"),
        "nominal_v": pin.get("nominal_v"),
        "aliases": pin.get("aliases") or [],
    }


def _signal_pair_specs(interface: str, signals: List[str]) -> List[Tuple[str, str, str, str]]:
    upper_signals = {str(signal or "").upper() for signal in signals}
    if interface == "uart" and {"TX", "RX"} <= upper_signals:
        return [("TX_TO_RX", "TX", "RX", "uart_cross"), ("RX_TO_TX", "RX", "TX", "uart_cross")]
    pairs = []
    for signal in sorted(upper_signals):
        pairs.append((signal, signal, signal, "same_signal"))
    return pairs


def _add_pin_pair(plan: Dict[str, Any], pair: Dict[str, Any]) -> None:
    key = (
        str((pair.get("from") or {}).get("board_id")),
        str((pair.get("from") or {}).get("connector_ref")),
        str((pair.get("from") or {}).get("pin")),
        str((pair.get("to") or {}).get("board_id")),
        str((pair.get("to") or {}).get("connector_ref")),
        str((pair.get("to") or {}).get("pin")),
        str(pair.get("function") or ""),
    )
    existing = {
        (
            str((row.get("from") or {}).get("board_id")),
            str((row.get("from") or {}).get("connector_ref")),
            str((row.get("from") or {}).get("pin")),
            str((row.get("to") or {}).get("board_id")),
            str((row.get("to") or {}).get("connector_ref")),
            str((row.get("to") or {}).get("pin")),
            str(row.get("function") or ""),
        )
        for row in plan.get("pin_pairs") or []
        if isinstance(row, dict)
    }
    if key not in existing:
        plan.setdefault("pin_pairs", []).append(pair)


def _pin_pair_terms(pair: Dict[str, Any]) -> List[str]:
    terms = []
    for side in ["from", "to"]:
        endpoint = pair.get(side) if isinstance(pair.get(side), dict) else {}
        terms.extend(_endpoint_terms(endpoint))
    return _dedupe_text(terms, limit=40)


def _endpoint_terms(endpoint: Dict[str, Any]) -> List[str]:
    net = _normalize_net(str(endpoint.get("net") or ""))
    terms = [endpoint.get("board_id"), endpoint.get("connector_ref")]
    if net and not is_ground_net(net):
        terms.append(net)
        terms.extend(
            alias
            for alias in endpoint.get("aliases") or []
            if not str(alias).upper().startswith("POWER::")
        )
    return _dedupe_text(terms, limit=20)


def _text_mentions_any(value: Any, terms: Iterable[Any]) -> bool:
    blob = _compact_text(value)
    if not blob:
        return False
    token_compacts = {_compact_text(token) for token in _text_tokens(value)}
    for term in terms:
        compact = _compact_text(term)
        if len(compact) < 2:
            continue
        if len(compact) <= 3:
            if compact in token_compacts:
                return True
            continue
        if compact in blob:
            return True
    return False


def _rail_budget_for_board(board: Dict[str, Any], rail: str) -> Optional[Dict[str, Any]]:
    target = _normalize_net(rail)
    for row in ((board.get("electrical_viability") or {}).get("rail_budgets") or []):
        if isinstance(row, dict) and _normalize_net(str(row.get("rail") or "")) == target:
            return row
    return None


def _system_power_viability(boards: List[Dict[str, Any]], topology: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    topology = topology if isinstance(topology, dict) else {}
    boards_by_id = {str(board.get("board_id") or ""): board for board in boards}
    links = []
    for row in topology.get("candidate_power_tree") or []:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "")
        if ":" not in source:
            continue
        source_board_id, source_rail = source.split(":", 1)
        sink_board_id = str(row.get("board_id") or "")
        sink_rail = str(row.get("rail") or "")
        source_board = boards_by_id.get(source_board_id)
        sink_board = boards_by_id.get(sink_board_id)
        source_budget = _rail_budget_for_board(source_board or {}, source_rail)
        sink_budget = _rail_budget_for_board(sink_board or {}, sink_rail)
        source_available_a = _safe_float((source_budget or {}).get("available_current_a"), 0.0)
        source_existing_load_a = _safe_float((source_budget or {}).get("estimated_load_a"), 0.0)
        source_margin_a = (
            _safe_float((source_budget or {}).get("margin_a"), source_available_a - source_existing_load_a)
            if source_available_a > 0
            else None
        )
        sink_load_a = _safe_float((sink_budget or {}).get("estimated_load_a"), 0.0)
        if not source_budget or not sink_budget:
            status = "missing_budget"
            action = "Resolve source and sink rail budgets before using this power link."
        elif source_available_a <= 0:
            status = "missing_source_limit"
            action = f"Record source current limit for {source} before powering {sink_board_id}:{sink_rail}."
        elif str(source_budget.get("status") or "") == "overcurrent":
            status = "source_already_overcurrent"
            action = f"Resolve existing overcurrent on {source} before adding {sink_board_id}:{sink_rail}."
        elif str(sink_budget.get("status") or "") == "unknown_load":
            status = "sink_load_unknown"
            action = f"Resolve load current on {sink_board_id}:{sink_rail} before joining the rail."
        elif source_margin_a is not None and sink_load_a > source_margin_a:
            status = "overcurrent"
            action = f"{source} margin is insufficient for {sink_board_id}:{sink_rail}; use another source or reduce load."
        else:
            status = "ok"
            action = f"{source} has enough estimated margin for {sink_board_id}:{sink_rail} under current assumptions."
        margin_after_link = source_margin_a - sink_load_a if source_margin_a is not None else None
        links.append(
            {
                "source": source,
                "source_board": source_board_id,
                "source_rail": source_rail,
                "sink_board": sink_board_id,
                "sink_rail": sink_rail,
                "nominal_v": row.get("voltage_v"),
                "status": status,
                "source_available_a": round(source_available_a, 4) if source_available_a > 0 else None,
                "source_existing_load_a": round(source_existing_load_a, 4),
                "source_margin_a": round(source_margin_a, 4) if source_margin_a is not None else None,
                "sink_estimated_load_a": round(sink_load_a, 4),
                "margin_after_link_a": round(margin_after_link, 4) if margin_after_link is not None else None,
                "confidence": row.get("confidence"),
                "action": action,
            }
        )
    if any(link["status"] in {"overcurrent", "source_already_overcurrent"} for link in links):
        verdict = "blocked_overcurrent"
    elif any(link["status"] in {"missing_budget", "missing_source_limit", "sink_load_unknown"} for link in links):
        verdict = "blocked_pending_power_evidence"
    elif links:
        verdict = "power_links_viable_under_current_assumptions"
    else:
        verdict = "no_cross_board_power_links"
    return {
        "mode": "system_power_viability",
        "verdict": verdict,
        "links": links,
    }


def _system_power_link_clears_source_limit(power_links: List[Dict[str, Any]], board_id: str, text: Any) -> bool:
    for link in power_links:
        if link.get("status") != "ok":
            continue
        if str(link.get("sink_board") or "") != str(board_id or ""):
            continue
        if _text_mentions_any(text, [link.get("sink_rail"), link.get("source_rail")]):
            return True
    return False


def _plan_blockers(
    plan: Dict[str, Any],
    boards: List[Dict[str, Any]],
    power_rows: List[Dict[str, Any]],
    power_links: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    terms: List[str] = []
    terms_by_board: Dict[str, List[str]] = defaultdict(list)
    for pair in plan.get("pin_pairs") or []:
        if isinstance(pair, dict):
            terms.extend(_pin_pair_terms(pair))
            for side in ["from", "to"]:
                endpoint = pair.get(side) if isinstance(pair.get(side), dict) else {}
                board_id = str(endpoint.get("board_id") or "")
                if board_id:
                    terms_by_board[board_id].extend(_endpoint_terms(endpoint))
    terms.extend([plan.get("from_connector"), plan.get("to_connector"), plan.get("from_board"), plan.get("to_board")])
    terms = _dedupe_text(terms, limit=80)
    blockers: List[Dict[str, Any]] = []
    seen = set()

    def add(kind: str, prompt: str, source: str, priority: int = 2, evidence: Optional[List[str]] = None) -> None:
        text = str(prompt or "").strip()
        key = (kind, text.lower())
        if not text or key in seen:
            return
        seen.add(key)
        blockers.append(
            {
                "kind": kind,
                "prompt": text,
                "source": source,
                "priority": priority,
                "evidence": evidence or [],
            }
        )

    for board in boards:
        board_id = str(board.get("board_id") or "")
        scoped_terms = _dedupe_text(terms_by_board.get(board_id) or [], limit=80)
        if not scoped_terms:
            continue
        for row in board.get("measurement_plan") or []:
            if not isinstance(row, dict) or row.get("status") == "closed":
                continue
            if "splicing" not in (row.get("blocks_before_done") or []):
                continue
            text = " ".join(str(row.get(key) or "") for key in ["target", "prompt", "expected", "measurement_id"])
            text = f"{text} {' '.join(str(item) for item in row.get('evidence') or [])}"
            if row.get("type") == "current_limit" and _system_power_link_clears_source_limit(power_links, str(board.get("board_id") or ""), text):
                continue
            if _text_mentions_any(text, scoped_terms):
                add(
                    "measurement_gate",
                    str(row.get("prompt") or ""),
                    f"{board.get('board_id')}:{row.get('measurement_id')}",
                    _safe_int(row.get("priority"), 3),
                    [str(item) for item in row.get("evidence") or []],
                )
        for risk in board.get("electrical_risks") or []:
            if not isinstance(risk, dict) or risk.get("severity") not in {"critical", "error", "high"}:
                continue
            text = " ".join(str(risk.get(key) or "") for key in ["topic", "message", "action"])
            text = f"{text} {' '.join(str(item) for item in risk.get('evidence') or [])}"
            if risk.get("topic") == "source_limit_missing" and _system_power_link_clears_source_limit(power_links, str(board.get("board_id") or ""), text):
                continue
            if _text_mentions_any(text, scoped_terms):
                add(
                    "risk_gate",
                    str(risk.get("action") or risk.get("message") or ""),
                    f"{board.get('board_id')}:risk:{risk.get('topic')}",
                    1,
                    [str(item) for item in risk.get("evidence") or []],
                )

    plan_board_ids = {str(plan.get("from_board") or ""), str(plan.get("to_board") or "")}
    plan_rails = {
        _normalize_net(str((pair.get("from") or {}).get("net") or ""))
        for pair in plan.get("pin_pairs") or []
        if isinstance(pair, dict) and pair.get("category") == "power"
    } | {
        _normalize_net(str((pair.get("to") or {}).get("net") or ""))
        for pair in plan.get("pin_pairs") or []
        if isinstance(pair, dict) and pair.get("category") == "power"
    }
    for row in power_rows:
        if not isinstance(row, dict):
            continue
        source_board = str(row.get("source") or "").split(":", 1)[0]
        sink_board = str(row.get("board_id") or "")
        rail = _normalize_net(str(row.get("rail") or ""))
        if source_board in plan_board_ids and sink_board in plan_board_ids and rail in plan_rails:
            add(
                "power_source_contract",
                f"Confirm {row.get('source')} can safely source {row.get('rail')} on {row.get('board_id')} before joining power rails.",
                "system_power_tree",
                1,
                [str(row.get("source") or ""), str(row.get("rail") or ""), str(row.get("board_id") or "")],
            )

    for link in power_links:
        source_board = str(link.get("source_board") or "")
        sink_board = str(link.get("sink_board") or "")
        sink_rail = _normalize_net(str(link.get("sink_rail") or ""))
        if source_board in plan_board_ids and sink_board in plan_board_ids and sink_rail in plan_rails and link.get("status") != "ok":
            add(
                "system_power_viability",
                str(link.get("action") or "Resolve system power viability before joining the rail."),
                "system_power_viability",
                1,
                [str(link.get("source") or ""), str(link.get("sink_rail") or ""), str(link.get("sink_board") or "")],
            )

    return sorted(blockers, key=lambda row: (_safe_int(row.get("priority"), 3), str(row.get("source") or "")))[:30]


def _pin_level_splice_plans(
    boards: List[Dict[str, Any]],
    topology: Optional[Dict[str, Any]],
    power_viability: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    topology = topology if isinstance(topology, dict) else {}
    power_links = [
        link
        for link in ((power_viability or {}).get("links") or [])
        if isinstance(link, dict)
    ]
    boards_by_id = {str(board.get("board_id") or ""): board for board in boards}
    connectors_by_board = {board_id: _connector_lookup(board) for board_id, board in boards_by_id.items()}
    plans: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}

    def get_plan(from_board_id: str, to_board_id: str, from_ref: str, to_ref: str) -> Dict[str, Any]:
        key = (from_board_id, to_board_id, from_ref, to_ref)
        if key not in plans:
            plans[key] = {
                "plan_id": f"{from_board_id}:{from_ref}->{to_board_id}:{to_ref}",
                "from_board": from_board_id,
                "to_board": to_board_id,
                "from_connector": from_ref,
                "to_connector": to_ref,
                "interfaces": [],
                "pin_pairs": [],
                "issues": [],
            }
        return plans[key]

    for row in topology.get("candidate_interconnects") or []:
        if not isinstance(row, dict):
            continue
        from_board_id = str(row.get("from_board") or "")
        to_board_id = str(row.get("to_board") or "")
        from_ref = str(row.get("from_connector") or "")
        to_ref = str(row.get("to_connector") or "")
        interface = str(row.get("interface") or "")
        from_board = boards_by_id.get(from_board_id)
        to_board = boards_by_id.get(to_board_id)
        from_connector = (connectors_by_board.get(from_board_id) or {}).get(from_ref)
        to_connector = (connectors_by_board.get(to_board_id) or {}).get(to_ref)
        if not from_board or not to_board or not from_connector or not to_connector:
            continue
        plan = get_plan(from_board_id, to_board_id, from_ref, to_ref)
        if interface and interface not in plan["interfaces"]:
            plan["interfaces"].append(interface)

        from_ground = _connector_pin(from_connector, role="ground")
        to_ground = _connector_pin(to_connector, role="ground")
        if from_ground and to_ground:
            _add_pin_pair(
                plan,
                {
                    "category": "ground",
                    "function": "GND",
                    "join": "common_reference",
                    "from": _pin_endpoint(from_board, from_connector, from_ground),
                    "to": _pin_endpoint(to_board, to_connector, to_ground),
                    "rule": "common reference must be connected before signal validation",
                },
            )
        else:
            plan["issues"].append(
                {
                    "severity": "high",
                    "topic": "missing_common_ground_pin",
                    "message": "Candidate connector pair does not expose ground on both ends.",
                }
            )

        for function, from_alias, to_alias, join in _signal_pair_specs(interface, row.get("signals") or []):
            from_pin = _connector_pin(from_connector, alias=from_alias)
            to_pin = _connector_pin(to_connector, alias=to_alias)
            if not from_pin or not to_pin:
                plan["issues"].append(
                    {
                        "severity": "medium",
                        "topic": "missing_signal_pin",
                        "message": f"Could not map {function} on {from_ref}->{to_ref}.",
                        "evidence": [from_alias, to_alias],
                    }
                )
                continue
            _add_pin_pair(
                plan,
                {
                    "category": "signal",
                    "function": function,
                    "interface": interface,
                    "join": join,
                    "from": _pin_endpoint(from_board, from_connector, from_pin),
                    "to": _pin_endpoint(to_board, to_connector, to_pin),
                    "rule": "verify idle/high level and common ground before enabling traffic",
                },
            )

    power_rows = [row for row in topology.get("candidate_power_tree") or [] if isinstance(row, dict)]
    for row in power_rows:
        source = str(row.get("source") or "")
        if ":" not in source:
            continue
        source_board_id, source_rail = source.split(":", 1)
        sink_board_id = str(row.get("board_id") or "")
        sink_rail = str(row.get("rail") or "")
        for plan in plans.values():
            board_ids = {str(plan.get("from_board") or ""), str(plan.get("to_board") or "")}
            if {source_board_id, sink_board_id} != board_ids:
                continue
            source_is_from = str(plan.get("from_board") or "") == source_board_id
            source_board = boards_by_id.get(source_board_id)
            sink_board = boards_by_id.get(sink_board_id)
            if not source_board or not sink_board:
                continue
            source_connector = (connectors_by_board.get(source_board_id) or {}).get(str(plan.get("from_connector" if source_is_from else "to_connector") or ""))
            sink_connector = (connectors_by_board.get(sink_board_id) or {}).get(str(plan.get("to_connector" if source_is_from else "from_connector") or ""))
            if not source_connector or not sink_connector:
                continue
            source_pin = _connector_pin(source_connector, net=source_rail)
            sink_pin = _connector_pin(sink_connector, net=sink_rail)
            if not source_pin or not sink_pin:
                continue
            link_budget = next(
                (
                    link
                    for link in power_links
                    if str(link.get("source_board") or "") == source_board_id
                    and str(link.get("sink_board") or "") == sink_board_id
                    and _normalize_net(str(link.get("sink_rail") or "")) == _normalize_net(sink_rail)
                ),
                {},
            )
            _add_pin_pair(
                plan,
                {
                    "category": "power",
                    "function": f"rail:{sink_rail}",
                    "join": "source_to_sink",
                    "from": _pin_endpoint(source_board, source_connector, source_pin),
                    "to": _pin_endpoint(sink_board, sink_connector, sink_pin),
                    "nominal_v": row.get("voltage_v"),
                    "rule": "join only after source capability, polarity, and load budget are confirmed",
                    "confidence": row.get("confidence"),
                    "budget_status": link_budget.get("status"),
                    "source_margin_a": link_budget.get("source_margin_a"),
                    "sink_estimated_load_a": link_budget.get("sink_estimated_load_a"),
                    "margin_after_link_a": link_budget.get("margin_after_link_a"),
                },
            )

    finalized = []
    for plan in plans.values():
        blockers = _plan_blockers(plan, boards, power_rows, power_links)
        high_issues = [issue for issue in plan.get("issues") or [] if issue.get("severity") in {"critical", "error", "high"}]
        plan["interfaces"] = sorted(plan.get("interfaces") or [])
        plan["blockers"] = blockers
        plan["status"] = "blocked_missing_pin_mapping" if high_issues else "blocked_until_evidence" if blockers else "ready_for_splice_review"
        plan["wire_bom"] = _wire_bom(plan)
        plan["execution_sequence"] = _execution_sequence(plan)
        plan["summary"] = {
            "pin_pair_count": len(plan.get("pin_pairs") or []),
            "wire_count": len(plan.get("wire_bom") or []),
            "blocker_count": len(blockers),
            "issue_count": len(plan.get("issues") or []),
        }
        finalized.append(plan)
    return sorted(finalized, key=lambda row: str(row.get("plan_id") or ""))[:50]


def _wire_color(pair: Dict[str, Any]) -> str:
    function = str(pair.get("function") or "").upper()
    category = str(pair.get("category") or "")
    if category == "ground" or function == "GND":
        return "black"
    if category == "power":
        nominal = pair.get("nominal_v")
        if nominal is not None and _safe_float(nominal, 0.0) <= 3.6:
            return "orange"
        return "red"
    if "SCL" in function:
        return "yellow"
    if "SDA" in function:
        return "green"
    if "TX" in function:
        return "blue"
    if "RX" in function:
        return "white"
    if "PWM" in function or "SERVO" in function:
        return "purple"
    return "gray"


def _wire_bom(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for index, pair in enumerate(plan.get("pin_pairs") or [], start=1):
        if not isinstance(pair, dict):
            continue
        from_ep = pair.get("from") if isinstance(pair.get("from"), dict) else {}
        to_ep = pair.get("to") if isinstance(pair.get("to"), dict) else {}
        rows.append(
            {
                "wire_id": f"W{index}",
                "function": pair.get("function"),
                "category": pair.get("category"),
                "color": _wire_color(pair),
                "from": from_ep,
                "to": to_ep,
                "label": f"{from_ep.get('board_id')}:{from_ep.get('connector_ref')}.{from_ep.get('pin')} -> {to_ep.get('board_id')}:{to_ep.get('connector_ref')}.{to_ep.get('pin')}",
                "handling": pair.get("rule"),
            }
        )
    return rows


def _execution_sequence(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    blockers = plan.get("blockers") or []
    if blockers:
        steps.append(
            {
                "step": "close_blockers",
                "status": "blocked",
                "action": "Close plan-specific measurement, risk, and power-source blockers.",
                "blocking_count": len(blockers),
            }
        )
    categories = [
        ("ground", "connect_reference", "Connect common reference/ground first."),
        ("power", "connect_power", "Connect power rails under current limit after polarity/source checks."),
        ("signal", "connect_signals", "Connect signal wires after common ground and logic-level checks."),
    ]
    for category, step_name, action in categories:
        wires = [
            wire.get("wire_id")
            for wire in plan.get("wire_bom") or []
            if wire.get("category") == category
        ]
        if not wires:
            continue
        steps.append(
            {
                "step": step_name,
                "status": "pending" if blockers else "ready",
                "action": action,
                "wire_ids": wires,
            }
        )
    steps.append(
        {
            "step": "functional_bringup",
            "status": "pending" if blockers else "ready",
            "action": "Power up under current limit and verify interface traffic or device enumeration.",
            "wire_ids": [wire.get("wire_id") for wire in plan.get("wire_bom") or []],
        }
    )
    return steps


def _lightweight_components_from_structure(structure: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Dict[str, str]], Dict[str, Dict[str, Any]]]:
    components: Dict[str, Any] = {}
    pinmap: Dict[str, Dict[str, str]] = {}
    nets: Dict[str, Dict[str, Any]] = {}

    def add_pin(ref: str, pin: str, net: str) -> None:
        normalized = _normalize_net(net)
        if not ref or not pin or not normalized:
            return
        pinmap.setdefault(ref, {})[str(pin)] = normalized
        nets.setdefault(normalized, {"code": str(len(nets) + 1), "nodes": []})
        nets[normalized]["nodes"].append({"ref": ref, "pin": str(pin)})

    for connector in structure.get("connectors") or []:
        if not isinstance(connector, dict):
            continue
        ref = str(connector.get("ref") or f"J{len(components) + 1}")
        components[ref] = {"value": connector.get("value") or "connector", "footprint": connector.get("footprint") or "connector"}
        for pin, net in (connector.get("pin_nets") or {}).items():
            add_pin(ref, str(pin), str(net))

    for component in structure.get("active_components") or []:
        if not isinstance(component, dict):
            continue
        ref = str(component.get("ref") or f"U{len(components) + 1}")
        components[ref] = {"value": component.get("value") or component.get("category") or "active", "footprint": component.get("footprint") or ""}
        for index, net in enumerate(component.get("nets") or [], start=1):
            add_pin(ref, str(index), str(net))

    for reg in (structure.get("power") or {}).get("regulators") or []:
        if not isinstance(reg, dict):
            continue
        ref = str(reg.get("ref") or f"REG{len(components) + 1}")
        components.setdefault(ref, {"value": reg.get("kind") or "regulator", "footprint": ""})
        for pin, key in [("VIN", "vin_net"), ("VOUT", "vout_net"), ("GND", "gnd_net")]:
            if reg.get(key):
                add_pin(ref, pin, str(reg[key]))

    return components, pinmap, nets


def build_circuit_board_model(
    design_path: str,
    *,
    board_id: Optional[str] = None,
    board_name: Optional[str] = None,
    kind: Optional[str] = None,
    evidence_session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    path = Path(design_path)
    structure = extract_board_structure(str(path), board_id=board_id, board_name=board_name, kind=kind)
    components, pinmap, nets = _load_components_pinmap_and_nets(path, kind=kind)
    return build_circuit_board_model_from_structure(
        structure,
        components=components,
        pinmap=pinmap,
        nets=nets,
        evidence_session=evidence_session,
    )


def build_circuit_board_model_from_structure(
    structure: Dict[str, Any],
    *,
    components: Optional[Dict[str, Any]] = None,
    pinmap: Optional[Dict[str, Dict[str, str]]] = None,
    nets: Optional[Dict[str, Dict[str, Any]]] = None,
    evidence_session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    board_id = str(structure.get("board_id") or "board")
    if components is None or pinmap is None or nets is None:
        physical_pinmap = False
        components, pinmap, nets = _lightweight_components_from_structure(structure)
    else:
        physical_pinmap = True
    category_by_ref = {
        ref: _component_category(ref, meta if isinstance(meta, dict) else {})
        for ref, meta in (components or {}).items()
    }
    graph = _graph_records(board_id, components or {}, pinmap or {}, nets or {}, category_by_ref)
    components_rows = _component_records(components or {}, pinmap or {}, category_by_ref)
    net_rows = _net_records(nets or {}, category_by_ref)
    connector_contracts = _connector_contracts(structure)
    component_intelligence = _component_pinout_intelligence(
        components or {},
        pinmap or {},
        category_by_ref,
        physical_pinmap=physical_pinmap,
    )
    power_tree = _power_tree(structure)
    electrical_viability = _electrical_viability(
        power_tree,
        connector_contracts,
        component_intelligence,
        components or {},
        pinmap or {},
        category_by_ref,
        evidence_session,
    )
    risks = [
        *_risk_records(structure, connector_contracts, component_intelligence),
        *[issue for issue in electrical_viability.get("issues") or [] if isinstance(issue, dict)],
    ]
    measurement_plan, measurement_closure = _apply_session_evidence(
        _measurement_plan(structure, connector_contracts, risks),
        evidence_session,
    )
    splice_contract = _splice_contract(structure, connector_contracts, measurement_plan, risks)
    capability_contract = _capability_contract(structure, connector_contracts)
    next_tasks = _next_tasks(measurement_plan, risks, component_intelligence)
    certainty = _certainty_ledger(graph, risks, measurement_plan)
    high_risk_count = len([risk for risk in risks if risk.get("severity") in {"critical", "error", "high"}])
    open_blockers = [
        row
        for row in measurement_plan
        if row.get("status") != "closed" and row.get("blocks_before_done")
    ]
    outcome_count = _safe_int(measurement_closure.get("outcome_count"), 0)
    if not graph["summary"]["net_count"]:
        readiness = "insufficient_circuit_evidence"
    elif any(row.get("status") == "failed" for row in measurement_plan):
        readiness = "failed_measurement_hold"
    elif electrical_viability.get("verdict") == "overcurrent_blocked":
        readiness = "electrical_viability_hold"
    elif open_blockers:
        readiness = "blocked_until_measurements"
    elif outcome_count:
        readiness = "calibrated_circuit_case"
    elif high_risk_count:
        readiness = "splice_review_ready"
    elif measurement_plan:
        readiness = "measurement_ready"
    else:
        readiness = "circuit_review_ready"
    workflow_state = _workflow_state(readiness, measurement_plan, splice_contract, measurement_closure)
    board_model = {
        "board_id": board_id,
        "board_name": structure.get("board_name") or board_id,
        "source": structure.get("source") or {},
        "primary_role": structure.get("primary_role"),
        "readiness": readiness,
        "workflow_state": workflow_state,
        "graph": graph,
        "components": components_rows,
        "nets": net_rows,
        "power_tree": power_tree,
        "connector_contracts": connector_contracts,
        "component_intelligence": component_intelligence,
        "capability_contract": capability_contract,
        "electrical_viability": electrical_viability,
        "electrical_risks": risks,
        "measurement_plan": measurement_plan,
        "measurement_closure": measurement_closure,
        "splice_contract": splice_contract,
        "next_evidence_tasks": next_tasks,
        "certainty_ledger": certainty,
        "raw_structure": structure,
    }
    board_model["functional_salvage"] = infer_board_functional_salvage(board_model)
    return board_model


def _system_contract(boards: List[Dict[str, Any]], topology: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    topology = topology if isinstance(topology, dict) else {}
    interconnects = topology.get("candidate_interconnects") or []
    power_tree = topology.get("candidate_power_tree") or []
    power_viability = _system_power_viability(boards, topology)
    pin_plans = _pin_level_splice_plans(boards, topology, power_viability)
    do_not_connect = []
    for board in boards:
        do_not_connect.extend((board.get("splice_contract") or {}).get("do_not_connect_until") or [])
    for row in power_tree:
        if not isinstance(row, dict):
            continue
        source = row.get("source")
        sink = row.get("board_id")
        rail = row.get("rail")
        do_not_connect.append(f"Confirm {source} can safely source {rail} on {sink} before joining power rails.")
    wiring_contracts = []
    for row in interconnects:
        if not isinstance(row, dict):
            continue
        interface = str(row.get("interface") or "")
        wiring_contracts.append(
            {
                "from_board": row.get("from_board"),
                "to_board": row.get("to_board"),
                "from_connector": row.get("from_connector"),
                "to_connector": row.get("to_connector"),
                "interface": interface,
                "signals": row.get("signals") or [],
                "rule": "match by signal function, verify common ground, and verify voltage compatibility before connection",
                "confidence": row.get("confidence"),
            }
        )
    return {
        "mode": "circuit_system_splice_contract",
        "candidate_interconnects": interconnects,
        "candidate_power_tree": power_tree,
        "system_power_viability": power_viability,
        "wiring_contracts": wiring_contracts,
        "pin_level_splice_plans": pin_plans,
        "do_not_connect_until": _dedupe_text(do_not_connect, limit=50),
        "questions": topology.get("questions") or [],
        "scope": "electrical inter-board wiring and power contract",
    }


def _overall_readiness(boards: List[Dict[str, Any]]) -> str:
    levels = {str(board.get("readiness") or "") for board in boards}
    if "insufficient_circuit_evidence" in levels:
        return "insufficient_circuit_evidence"
    if "failed_measurement_hold" in levels:
        return "failed_measurement_hold"
    if "electrical_viability_hold" in levels:
        return "electrical_viability_hold"
    if "blocked_until_measurements" in levels:
        return "blocked_until_measurements"
    if "calibrated_circuit_case" in levels and len(levels) == 1:
        return "calibrated_circuit_case"
    if "splice_review_ready" in levels:
        return "splice_review_ready"
    if "measurement_ready" in levels:
        return "measurement_ready"
    return "circuit_review_ready"


def _aggregate_tasks(boards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    seen = set()
    for board in boards:
        for task in board.get("next_evidence_tasks") or []:
            if not isinstance(task, dict):
                continue
            prompt = str(task.get("prompt") or "")
            key = (str(task.get("task_type") or ""), prompt.lower())
            if not prompt or key in seen:
                continue
            seen.add(key)
            tasks.append({**task, "board_id": board.get("board_id")})
    return sorted(tasks, key=lambda row: (_safe_int(row.get("priority"), 3), str(row.get("board_id") or "")))[:50]


def _aggregate_certainty(boards: List[Dict[str, Any]]) -> Dict[str, Any]:
    scores = [
        _safe_float(((board.get("certainty_ledger") or {}).get("overall") or {}).get("score"), 0.0)
        for board in boards
    ]
    score = round(sum(scores) / len(scores), 3) if scores else 0.0
    missing = []
    items = []
    for board in boards:
        ledger = board.get("certainty_ledger") if isinstance(board.get("certainty_ledger"), dict) else {}
        missing.extend(ledger.get("missing_evidence") or [])
        for item in ledger.get("items") or []:
            if isinstance(item, dict):
                items.append({**item, "board_id": board.get("board_id")})
    return {
        "overall": {
            "score": score,
            "level": "likely" if score >= 0.82 else "possible" if score >= 0.55 else "unknown",
            "summary": "Aggregate circuit graph certainty across analyzed board(s).",
        },
        "missing_evidence": _dedupe_text(missing, limit=40),
        "items": items[:100],
        "training_queue": {
            "should_capture": bool(missing),
            "candidate_labels": _dedupe_text([item.get("claim") for item in items if item.get("certainty") == "unknown"], limit=20),
        },
    }


def _aggregate_workflow_state(boards: List[Dict[str, Any]]) -> Dict[str, Any]:
    states = [board.get("workflow_state") for board in boards if isinstance(board.get("workflow_state"), dict)]
    if not states:
        return {
            "stage": "no_circuit_workflow",
            "next_action": "Provide circuit design or board-structure evidence.",
            "board_count": 0,
        }
    priority = {
        "fault_hold": 0,
        "electrical_viability_hold": 1,
        "measurement_closure": 2,
        "splice_review": 3,
        "bringup_measurement": 4,
        "circuit_review": 5,
        "calibrated": 6,
    }
    selected = sorted(states, key=lambda row: priority.get(str(row.get("stage") or ""), 9))[0]
    return {
        "stage": selected.get("stage"),
        "next_action": selected.get("next_action"),
        "board_count": len(boards),
        "boards": [
            {
                "board_id": board.get("board_id"),
                "stage": (board.get("workflow_state") or {}).get("stage"),
                "readiness": board.get("readiness"),
                "next_action": (board.get("workflow_state") or {}).get("next_action"),
            }
            for board in boards
        ],
    }


def analyze_circuit_design(payload: Dict[str, Any], *, evidence_session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    boards: List[Dict[str, Any]] = []
    raw_structures: List[Dict[str, Any]] = []
    for index, row in enumerate(_board_rows(payload), start=1):
        path = str(row.get("path") or row.get("design_path") or "").strip()
        if not path:
            raise ValueError(f"boards[{index - 1}].path is required")
        board_id = str(row.get("board_id") or Path(path).stem or f"board_{index}").strip() or f"board_{index}"
        board_name = str(row.get("board_name") or row.get("name") or board_id).strip() or board_id
        kind = str(row.get("kind") or "").strip().lower() or None
        board = build_circuit_board_model(
            path,
            board_id=board_id,
            board_name=board_name,
            kind=kind,
            evidence_session=evidence_session,
        )
        boards.append(board)
        raw_structures.append(board["raw_structure"])
    topology = None
    if len(raw_structures) > 1 or payload.get("machine_name"):
        topology = synthesize_machine_topology(
            raw_structures,
            machine_name=str(payload.get("machine_name") or "circuit_graph_machine"),
        )
    return {
        "mode": "circuit_ai_circuit_graph",
        "scope": "circuit_only",
        "overall_readiness": _overall_readiness(boards),
        "workflow_state": _aggregate_workflow_state(boards),
        "board_count": len(boards),
        "boards": boards,
        "system_contract": _system_contract(boards, topology),
        "functional_salvage": aggregate_functional_salvage(boards),
        "machine_topology": topology,
        "next_evidence_tasks": _aggregate_tasks(boards),
        "certainty_ledger": _aggregate_certainty(boards),
    }


def _latest_analysis(session: Dict[str, Any]) -> Dict[str, Any]:
    analyses = session.get("analyses") if isinstance(session.get("analyses"), list) else []
    if not analyses:
        return {}
    latest = analyses[-1] if isinstance(analyses[-1], dict) else {}
    results = latest.get("results")
    return results if isinstance(results, dict) else {}


def _structures_from_analysis(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(analysis, dict):
        return []
    if analysis.get("mode") == "circuit_ai_circuit_graph":
        structures = []
        for board in analysis.get("boards") or []:
            if isinstance(board, dict) and isinstance(board.get("raw_structure"), dict):
                structures.append(board["raw_structure"])
        return structures
    structures = []
    for board in analysis.get("boards") or []:
        if not isinstance(board, dict):
            continue
        raw = board.get("raw_structure")
        if isinstance(raw, dict):
            structures.append(raw)
    raw = analysis.get("raw_structure")
    if isinstance(raw, dict):
        structures.append(raw)
    return structures


def analyze_circuit_session(
    session: Dict[str, Any],
    *,
    design_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(session, dict):
        raise ValueError("session must be an object")
    if isinstance(design_payload, dict) and any(str(row.get("path") or row.get("design_path") or "").strip() for row in _board_rows(design_payload)):
        result = analyze_circuit_design(design_payload, evidence_session=session)
    else:
        structures = _structures_from_analysis(_latest_analysis(session))
        if not structures:
            raise ValueError("session has no circuit design or board-structure analysis to advance")
        boards = [
            build_circuit_board_model_from_structure(structure, evidence_session=session)
            for structure in structures
        ]
        topology = synthesize_machine_topology(structures, machine_name=str(session.get("title") or "circuit_session")) if len(structures) > 1 else None
        result = {
            "mode": "circuit_ai_circuit_graph",
            "scope": "circuit_only",
            "overall_readiness": _overall_readiness(boards),
            "workflow_state": _aggregate_workflow_state(boards),
            "board_count": len(boards),
            "boards": boards,
            "system_contract": _system_contract(boards, topology),
            "functional_salvage": aggregate_functional_salvage(boards),
            "machine_topology": topology,
            "next_evidence_tasks": _aggregate_tasks(boards),
            "certainty_ledger": _aggregate_certainty(boards),
        }
    evidence = session.get("evidence") if isinstance(session.get("evidence"), dict) else {}
    result["session_context"] = {
        "session_id": session.get("session_id"),
        "title": session.get("title"),
        "route": session.get("route"),
        "capture_count": len(evidence.get("captures") or []),
        "measurement_count": len(evidence.get("measurements") or []),
        "review_count": len(session.get("reviews") or []),
        "outcome_count": len(session.get("outcomes") or []),
    }
    return result
