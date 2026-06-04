"""Derive visual topology hypotheses from board photos.

This layer sits between vision evidence and measured topology. It turns
multi-photo board observations into candidate connector roles, likely
component-to-connector paths, and a measurement queue. It never marks pinout,
voltage, nets, or splice authority as verified.
"""

from __future__ import annotations

from math import sqrt
from typing import Any, Dict, Iterable, List, Sequence


SCHEMA_VERSION = "visual_topology_hypothesis.v1"


def enrich_payload_with_visual_topology_hypothesis(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach visual topology hypotheses and evidence tasks to a payload."""

    body = dict(payload or {})
    analysis = dict(body.get("analysis") if isinstance(body.get("analysis"), dict) else {})
    hypothesis = build_visual_topology_hypothesis(body, analysis=analysis)
    if not hypothesis.get("available"):
        return body

    analysis["visual_topology_hypothesis"] = hypothesis
    body["analysis"] = analysis
    body["visual_topology_hypothesis"] = hypothesis
    return body


def build_visual_topology_hypothesis(
    payload: Dict[str, Any],
    *,
    analysis: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build candidate topology questions from visual board evidence."""

    body = payload or {}
    context = analysis if isinstance(analysis, dict) else body.get("analysis") if isinstance(body.get("analysis"), dict) else {}
    reconstruction = _first_dict(context.get("multiview_board_reconstruction"), body.get("multiview_board_reconstruction"))
    board = _first_dict(
        context.get("board_evidence"),
        body.get("board_evidence"),
        reconstruction.get("board_evidence") if isinstance(reconstruction, dict) else {},
    )
    if not board and _looks_like_photo_set(body):
        try:
            from src.intelligence.multiview_board_evidence import fuse_board_photo_set

            fused = fuse_board_photo_set(body)
        except Exception:
            fused = {}
        if isinstance(fused, dict) and fused.get("available"):
            reconstruction = fused
            board = _first_dict(fused.get("board_evidence"))
    canonical_map = _first_dict(
        context.get("canonical_board_map"),
        body.get("canonical_board_map"),
        reconstruction.get("canonical_board_map") if isinstance(reconstruction, dict) else {},
    )
    if not _has_visual_topology_input(board, canonical_map):
        return {
            "schema_version": SCHEMA_VERSION,
            "available": False,
            "reason": "No visual board evidence or canonical board map was supplied.",
        }

    components = _list_dicts(board.get("components"))
    connectors = _list_dicts(board.get("connectors"))
    test_points = _list_dicts(board.get("test_points"))
    markings = _list_dicts(board.get("markings"))
    component_anchors = _component_anchors(components, markings, canonical_map)
    connector_hypotheses = _connector_hypotheses(connectors, test_points, canonical_map)
    connection_hypotheses = _connection_hypotheses(component_anchors, connector_hypotheses)
    measurement_queue = _measurement_queue(component_anchors, connector_hypotheses, connection_hypotheses, canonical_map)
    readiness = _readiness(
        board=board,
        reconstruction=reconstruction,
        canonical_map=canonical_map,
        component_anchors=component_anchors,
        connector_hypotheses=connector_hypotheses,
        connection_hypotheses=connection_hypotheses,
        measurement_queue=measurement_queue,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "available": bool(component_anchors or connector_hypotheses or connection_hypotheses),
        "source": "visual_board_evidence",
        "readiness": readiness,
        "component_anchors": component_anchors[:24],
        "connector_hypotheses": connector_hypotheses[:24],
        "connection_hypotheses": connection_hypotheses[:32],
        "measurement_queue": measurement_queue[:40],
        "blocked_claims": _blocked_claims(),
        "topology_contract": {
            "required_schema": "topology_evidence.v1",
            "required_before_power_or_splice": [
                "measured connector pinout",
                "power-to-ground no-short result",
                "measured voltage and polarity",
                "logic/interface validation for external targets",
                "current-limited first-power and thermal observation",
            ],
            "visual_hypotheses_can_seed_measurements": True,
            "visual_hypotheses_do_not_close_measurement_gates": True,
        },
        "policy": {
            "visual_topology_is_candidate_only": True,
            "do_not_emit_measured_topology_from_photos": True,
            "photo_geometry_is_not_netlist": True,
            "pin_level_splice_requires_topology_evidence": True,
        },
    }


def _has_visual_topology_input(board: Dict[str, Any], canonical_map: Dict[str, Any]) -> bool:
    return bool(
        _list_dicts(board.get("components"))
        or _list_dicts(board.get("connectors"))
        or _list_dicts(board.get("test_points"))
        or _list_dicts(canonical_map.get("items"))
    )


def _looks_like_photo_set(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if any(key in payload for key in ["board_photo_set", "photo_set", "photo_observations", "board_photos", "visual_observations", "photos", "views", "captures", "images"]):
        return True
    return False


def _component_anchors(
    components: Sequence[Dict[str, Any]],
    markings: Sequence[Dict[str, Any]],
    canonical_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    marking_by_id = {str(row.get("id") or ""): row for row in markings if row.get("id")}
    rows: List[Dict[str, Any]] = []
    for index, component in enumerate(components, start=1):
        ref = str(component.get("id") or component.get("ref") or f"component_{index}")
        text = _component_text(component, marking_by_id)
        capabilities = _capabilities_from_text(text)
        geometry = _geometry_record(component, "components", canonical_map)
        bbox = geometry.get("normalized_bbox")
        rows.append(
            {
                "anchor_id": f"component_{_safe_id(ref)}",
                "component_ref": ref,
                "label": component.get("label") or component.get("kind") or ref,
                "kind": component.get("kind") or "component",
                "identity_text": text,
                "candidate_capabilities": capabilities,
                "likely_roles": _component_roles(capabilities, text),
                "confidence": _visual_confidence(component, bbox),
                "normalized_bbox": geometry.get("normalized_bbox"),
                "board_zone": geometry.get("board_zone"),
                "geometry_status": geometry.get("geometry_status"),
                "map_id": geometry.get("map_id"),
                "geometry": geometry,
                "source_photo_ids": _source_photo_ids(component),
                "support_count": int(component.get("support_count") or len(_source_photo_ids(component)) or 1),
                "source_policy": "Component identity is visual/catalog grounding only; connectivity must be measured.",
            }
        )
    return sorted(rows, key=lambda row: row.get("confidence", 0.0), reverse=True)


def _component_text(component: Dict[str, Any], marking_by_id: Dict[str, Dict[str, Any]]) -> str:
    parts = [
        component.get("label"),
        component.get("kind"),
        component.get("function"),
        component.get("notes"),
        component.get("visible_text"),
        component.get("marking"),
    ]
    for resolved in _list_dicts(component.get("resolved_markings")):
        parts.append(resolved.get("marking"))
        marking = marking_by_id.get(str(resolved.get("marking_id") or ""))
        if marking:
            parts.extend([marking.get("marking"), marking.get("visible_text"), marking.get("label")])
    return " ".join(str(part or "") for part in parts).strip()


def _connector_hypotheses(
    connectors: Sequence[Dict[str, Any]],
    test_points: Sequence[Dict[str, Any]],
    canonical_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    inputs = [(row, "connectors") for row in connectors] + [(row, "test_points") for row in test_points]
    for index, (connector, source_type) in enumerate(inputs, start=1):
        ref = str(connector.get("id") or connector.get("ref") or connector.get("label") or f"connector_{index}")
        text = _item_text(connector)
        roles = _connector_roles(text)
        capabilities = _connector_capabilities(roles, text)
        pin_count = _pin_count(connector, text)
        geometry = _geometry_record(connector, source_type, canonical_map)
        bbox = geometry.get("normalized_bbox")
        confidence = _visual_confidence(connector, bbox)
        if roles != ["unknown_external_interface"]:
            confidence = min(0.88, confidence + 0.08)
        rows.append(
            {
                "hypothesis_id": f"visual_connector_{_safe_id(ref)}",
                "connector_ref": ref,
                "source_type": source_type.rstrip("s"),
                "label": connector.get("label") or connector.get("kind") or ref,
                "kind": connector.get("kind") or source_type.rstrip("s"),
                "likely_roles": roles,
                "candidate_capabilities": capabilities,
                "pin_count_status": "explicit_visual_pin_count" if pin_count else "pin_count_unknown",
                "estimated_pin_count": pin_count,
                "confidence": round(confidence, 3),
                "normalized_bbox": geometry.get("normalized_bbox"),
                "board_zone": geometry.get("board_zone"),
                "geometry_status": geometry.get("geometry_status"),
                "map_id": geometry.get("map_id"),
                "geometry": geometry,
                "source_photo_ids": _source_photo_ids(connector),
                "support_count": int(connector.get("support_count") or len(_source_photo_ids(connector)) or 1),
                "required_measurements": _connector_required_measurements(roles),
                "blocked_until": [
                    "measured pinout",
                    "ground reference",
                    "power-to-ground no-short",
                    "voltage and logic-domain confirmation",
                ],
                "can_power_or_splice": False,
                "status": "visual_candidate_measurement_required",
            }
        )
    return sorted(rows, key=lambda row: row.get("confidence", 0.0), reverse=True)


def _connection_hypotheses(
    component_anchors: Sequence[Dict[str, Any]],
    connector_hypotheses: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for component in component_anchors:
        for connector in connector_hypotheses:
            relationship, relationship_reasons = _relationship(component, connector)
            distance = _geometry_distance(component.get("geometry"), connector.get("geometry"))
            shared_photo_ids = sorted(set(component.get("source_photo_ids") or []) & set(connector.get("source_photo_ids") or []))
            aligned = relationship != "candidate_component_connector_path"
            near = distance is not None and distance <= 0.48
            if not (aligned or near or shared_photo_ids):
                continue
            proximity = 0.0 if distance is None else max(0.0, 1.0 - (distance / 0.55))
            confidence = (
                0.28
                + 0.24 * ((_safe_float(component.get("confidence"), 0.5) + _safe_float(connector.get("confidence"), 0.5)) / 2)
                + 0.18 * proximity
                + (0.10 if shared_photo_ids else 0.0)
                + (0.14 if aligned else 0.0)
            )
            rows.append(
                {
                    "hypothesis_id": f"visual_path_{_safe_id(component.get('component_ref'))}_{_safe_id(connector.get('connector_ref'))}",
                    "type": relationship,
                    "from": {
                        "source_type": "component",
                        "ref": component.get("component_ref"),
                        "label": component.get("label"),
                        "geometry": component.get("geometry"),
                    },
                    "to": {
                        "source_type": connector.get("source_type") or "connector",
                        "ref": connector.get("connector_ref"),
                        "label": connector.get("label"),
                        "geometry": connector.get("geometry"),
                    },
                    "confidence": round(min(0.88, confidence), 3),
                    "visual_distance": None if distance is None else round(distance, 4),
                    "source_photo_ids": _dedupe(shared_photo_ids or component.get("source_photo_ids") or connector.get("source_photo_ids") or []),
                    "evidence": _dedupe(
                        [
                            *relationship_reasons,
                            "nearby on canonical board map" if near else "",
                            "same photo observation" if shared_photo_ids else "",
                        ]
                    )[:8],
                    "required_measurements": _connection_required_measurements(relationship),
                    "status": "needs_continuity_and_pinout",
                    "claim_boundary": "Visual adjacency suggests what to test; it does not prove a net, pinout, or safe splice.",
                }
            )
    rows.sort(key=lambda row: row.get("confidence", 0.0), reverse=True)
    return _dedupe_rows(rows, key_fields=("hypothesis_id",))[:32]


def _measurement_queue(
    component_anchors: Sequence[Dict[str, Any]],
    connector_hypotheses: Sequence[Dict[str, Any]],
    connection_hypotheses: Sequence[Dict[str, Any]],
    canonical_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    if connector_hypotheses:
        tasks.append(
            _task(
                "visual_topology_record",
                "measurement",
                "topology",
                0,
                "Create a topology_evidence.v1 record from measured connector pinout, continuity, no-short, voltage, current, and thermal observations.",
                "topology_evidence.v1",
                ["production_release", "splice", "repair", "portfolio_demo"],
            )
        )
    if canonical_map.get("unmapped_item_count"):
        tasks.append(
            _task(
                "visual_topology_layout_reference",
                "capture",
                "layout",
                2,
                "Add an overview or annotated photo that maps unmapped connector/component evidence into normalized board coordinates.",
                "layout_grounding",
                ["repair", "salvage", "training"],
            )
        )
    for connector in connector_hypotheses[:10]:
        ref = str(connector.get("connector_ref") or connector.get("label") or "connector")
        label = str(connector.get("label") or ref)
        roles = set(str(role) for role in connector.get("likely_roles") or [])
        target = _target_record(connector)
        tasks.append(
            _task(
                f"pinout_{_safe_id(ref)}",
                "measurement",
                "pinout",
                0,
                f"Map {label}: pin count, pin-1/orientation, ground, supply pins, signal pins, and no-connect pins by continuity or datasheet.",
                "topology_evidence.v1.connectors",
                ["repair", "reuse", "splice", "production_release"],
                target=target,
            )
        )
        tasks.append(
            _task(
                f"short_{_safe_id(ref)}",
                "measurement",
                "resistance",
                0,
                f"Measure unpowered resistance/no-short between every candidate supply pin and ground on {label}.",
                "topology_evidence.v1.resistance",
                ["safety", "repair", "reuse", "splice"],
                target=target,
            )
        )
        if roles & {"power_input_or_rail", "usb2_connector", "uart_serial_header", "debug_or_gpio_header", "i2c_bus_header"}:
            tasks.append(
                _task(
                    f"voltage_{_safe_id(ref)}",
                    "measurement",
                    "voltage",
                    0,
                    f"Power through a current limit and record voltage, polarity, and logic domain for {label} before any external connection.",
                    "topology_evidence.v1.voltage",
                    ["safety", "repair", "reuse", "splice", "production_release"],
                    target=target,
                )
            )
        if "usb2_connector" in roles:
            tasks.append(
                _task(
                    f"usb_path_{_safe_id(ref)}",
                    "measurement",
                    "continuity",
                    1,
                    f"Continuity-test USB D+ and D- path from {label} to the candidate USB bridge/protection network; keep polarity and pair orientation recorded.",
                    "topology_evidence.v1.continuity",
                    ["repair", "reuse", "splice"],
                    target=target,
                )
            )
        if "uart_serial_header" in roles:
            tasks.append(
                _task(
                    f"uart_logic_{_safe_id(ref)}",
                    "measurement",
                    "logic",
                    1,
                    f"Identify TX, RX, GND, and VCC on {label}; measure idle logic high and run loopback or safe serial capture before target connection.",
                    "topology_evidence.v1.connectors",
                    ["repair", "reuse", "splice", "portfolio_demo"],
                    target=target,
                )
            )
        if "i2c_bus_header" in roles:
            tasks.append(
                _task(
                    f"i2c_bus_{_safe_id(ref)}",
                    "measurement",
                    "logic",
                    1,
                    f"Verify SDA/SCL, pullups, ground, and voltage domain on {label} before an I2C scan or target connection.",
                    "topology_evidence.v1.connectors",
                    ["repair", "reuse", "splice"],
                    target=target,
                )
            )
        if "load_or_motor_output" in roles:
            tasks.append(
                _task(
                    f"load_test_{_safe_id(ref)}",
                    "measurement",
                    "load",
                    1,
                    f"Test {label} with a fused dummy load and thermal observation before connecting a real load.",
                    "topology_evidence.v1.current",
                    ["safety", "repair", "reuse"],
                    target=target,
                )
            )
    for component in component_anchors[:8]:
        roles = set(str(role) for role in component.get("likely_roles") or [])
        target = _target_record(component)
        if "usb_uart_bridge" in roles:
            label = str(component.get("label") or component.get("component_ref"))
            tasks.append(
                _task(
                    f"bridge_{_safe_id(component.get('component_ref'))}",
                    "measurement",
                    "continuity",
                    1,
                    f"For {label}, measure continuity from USB pins to the USB connector and from UART pins to candidate headers before treating it as a USB serial adapter.",
                    "topology_evidence.v1.continuity",
                    ["repair", "reuse", "splice", "portfolio_demo"],
                    target=target,
                )
            )
        if "power_regulator" in roles:
            label = str(component.get("label") or component.get("component_ref"))
            tasks.append(
                _task(
                    f"regulator_{_safe_id(component.get('component_ref'))}",
                    "measurement",
                    "voltage",
                    1,
                    f"For {label}, identify input, output, and ground, then measure no-short, output voltage, load current, and thermal behavior.",
                    "topology_evidence.v1.voltage",
                    ["safety", "repair", "reuse", "splice"],
                    target=target,
                )
            )
    for link in connection_hypotheses[:12]:
        source = link.get("from") if isinstance(link.get("from"), dict) else {}
        target = link.get("to") if isinstance(link.get("to"), dict) else {}
        label = f"{source.get('label') or source.get('ref')} to {target.get('label') or target.get('ref')}"
        link_target = {
            "relationship": link.get("type"),
            "from": _target_record(source),
            "to": _target_record(target),
            "visual_distance": link.get("visual_distance"),
            "source_photo_ids": link.get("source_photo_ids") or [],
        }
        tasks.append(
            _task(
                f"path_{_safe_id(link.get('hypothesis_id'))}",
                "measurement",
                "continuity",
                1,
                f"Continuity-test the visual candidate path {label}; record both positive and negative results as topology_evidence.v1.",
                "topology_evidence.v1.continuity",
                ["repair", "reuse", "splice", "training"],
                target=link_target,
            )
        )
    return _dedupe_tasks(tasks)[:40]


def _readiness(
    *,
    board: Dict[str, Any],
    reconstruction: Dict[str, Any],
    canonical_map: Dict[str, Any],
    component_anchors: Sequence[Dict[str, Any]],
    connector_hypotheses: Sequence[Dict[str, Any]],
    connection_hypotheses: Sequence[Dict[str, Any]],
    measurement_queue: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    multi_view = _has_multiview(board, reconstruction)
    layout_confidence = _safe_float(canonical_map.get("layout_confidence"), 0.0)
    score = 0.08
    if multi_view:
        score += 0.18
    if component_anchors:
        score += min(0.20, 0.06 + 0.04 * len(component_anchors))
    if connector_hypotheses:
        score += min(0.20, 0.08 + 0.04 * len(connector_hypotheses))
    if connection_hypotheses:
        score += min(0.22, 0.08 + 0.035 * len(connection_hypotheses))
    score += min(0.12, layout_confidence * 0.12)
    if multi_view and component_anchors and connector_hypotheses and connection_hypotheses and layout_confidence >= 0.45:
        level = "layout_grounded_visual_topology_candidate"
    elif component_anchors and connector_hypotheses and connection_hypotheses:
        level = "visual_component_connector_topology_candidate"
    elif connector_hypotheses:
        level = "visual_connector_topology_candidate"
    else:
        level = "visual_evidence_needs_connector_context"
    return {
        "level": level,
        "score": round(min(score, 0.72), 3),
        "multi_view_evidence": multi_view,
        "layout_confidence": layout_confidence,
        "component_anchor_count": len(component_anchors),
        "connector_hypothesis_count": len(connector_hypotheses),
        "connection_hypothesis_count": len(connection_hypotheses),
        "measurement_task_count": len(measurement_queue),
        "can_power_or_splice": False,
        "measured_topology_available": False,
        "next_unlock": "Attach measured topology_evidence.v1 generated from the visual measurement queue.",
    }


def _blocked_claims() -> List[Dict[str, Any]]:
    return [
        {
            "claim": "pinout_known",
            "status": "blocked",
            "reason": "Photos can suggest connector identity but cannot prove each pin role.",
            "required_evidence": "Measured connector pinout with continuity or trusted datasheet grounding.",
        },
        {
            "claim": "netlist_or_trace_topology",
            "status": "blocked",
            "reason": "Visible adjacency and approximate boxes do not prove hidden copper, vias, inner layers, or backside routing.",
            "required_evidence": "Continuity map, schematic/CAD source, or inspected trace proof.",
        },
        {
            "claim": "safe_power_or_splice",
            "status": "blocked",
            "reason": "Voltage, polarity, current draw, shorts, and thermal behavior are not visual facts.",
            "required_evidence": "No-short, voltage, current-limited first-power, and thermal measurements.",
        },
    ]


def _relationship(component: Dict[str, Any], connector: Dict[str, Any]) -> tuple[str, List[str]]:
    component_roles = set(str(role) for role in component.get("likely_roles") or [])
    connector_roles = set(str(role) for role in connector.get("likely_roles") or [])
    reasons: List[str] = []
    if "usb_uart_bridge" in component_roles and "usb2_connector" in connector_roles:
        reasons.extend(["USB bridge component", "USB connector candidate"])
        return "candidate_usb_data_path", reasons
    if "usb_uart_bridge" in component_roles and "uart_serial_header" in connector_roles:
        reasons.extend(["USB/UART bridge component", "UART header candidate"])
        return "candidate_uart_serial_path", reasons
    if "power_regulator" in component_roles and connector_roles & {"power_input_or_rail", "usb2_connector"}:
        reasons.extend(["regulator/power component", "power-capable connector candidate"])
        return "candidate_power_path", reasons
    if "controller" in component_roles and connector_roles & {"debug_or_gpio_header", "uart_serial_header", "i2c_bus_header", "spi_bus_header"}:
        reasons.extend(["controller component", "logic/debug connector candidate"])
        return "candidate_logic_io_path", reasons
    if "sensor_or_adc" in component_roles and connector_roles & {"i2c_bus_header", "spi_bus_header", "debug_or_gpio_header"}:
        reasons.extend(["sensor/ADC component", "bus connector candidate"])
        return "candidate_sensor_bus_path", reasons
    if "load_driver" in component_roles and "load_or_motor_output" in connector_roles:
        reasons.extend(["load driver component", "load output connector candidate"])
        return "candidate_load_output_path", reasons
    return "candidate_component_connector_path", reasons


def _connection_required_measurements(relationship: str) -> List[str]:
    mapping = {
        "candidate_usb_data_path": [
            "Continuity-test D+/D- from connector to USB bridge/protection.",
            "Verify USB ground/shield/reference continuity.",
        ],
        "candidate_uart_serial_path": [
            "Identify TX/RX/GND/VCC pins by continuity or datasheet.",
            "Measure UART idle logic level and run safe serial capture.",
        ],
        "candidate_power_path": [
            "Measure input/output rails, polarity, no-short, load current, and thermal behavior.",
        ],
        "candidate_logic_io_path": [
            "Map each header pin to controller/debug nets and verify voltage domain.",
        ],
        "candidate_sensor_bus_path": [
            "Verify bus pins, pullups, address/CS behavior, and voltage domain.",
        ],
        "candidate_load_output_path": [
            "Continuity-test output path and validate with dummy load/current limit.",
        ],
    }
    return mapping.get(relationship, ["Continuity-test the candidate path and record positive or negative result."])


def _connector_required_measurements(roles: Sequence[str]) -> List[str]:
    tasks = [
        "Confirm pin count and orientation.",
        "Find ground/reference by continuity.",
        "Measure no-short between candidate supply pins and ground.",
        "Measure voltage and polarity before external connection.",
    ]
    role_set = set(str(role) for role in roles)
    if "usb2_connector" in role_set:
        tasks.append("Map USB D+/D- continuity and ESD/protection path.")
    if "uart_serial_header" in role_set:
        tasks.append("Identify TX/RX and measure logic high voltage.")
    if "i2c_bus_header" in role_set:
        tasks.append("Identify SDA/SCL, pullups, and voltage domain.")
    if "spi_bus_header" in role_set:
        tasks.append("Identify SCLK/MOSI/MISO/CS and voltage domain.")
    if "load_or_motor_output" in role_set:
        tasks.append("Validate with dummy load, current limit, and thermal observation.")
    return _dedupe(tasks)


def _component_roles(capabilities: Sequence[str], text: str) -> List[str]:
    caps = set(str(cap) for cap in capabilities)
    roles = []
    if "usb_serial" in caps:
        roles.append("usb_uart_bridge")
    if "power" in caps:
        roles.append("power_regulator")
    if "controller" in caps:
        roles.append("controller")
    if "sensor_or_adc" in caps:
        roles.append("sensor_or_adc")
    if "network_interface" in caps:
        roles.append("network_interface")
    if _has_any(text, ["mosfet", "relay", "driver", "motor", "load", "uln2003", "l298"]):
        roles.append("load_driver")
    return roles or ["unknown_component_anchor"]


def _connector_roles(text: str) -> List[str]:
    lower = str(text or "").lower()
    roles = []
    if _has_any(lower, ["usb-c", "usb c", "micro usb", "mini usb", "usb connector", "usb port", "usb"]):
        roles.append("usb2_connector")
    if _has_any(lower, ["uart", "ttl", "serial", "tx", "rx"]):
        roles.append("uart_serial_header")
    if _has_any(lower, ["gpio", "debug", "swd", "jtag", "program", "isp", "header"]):
        roles.append("debug_or_gpio_header")
    if _has_any(lower, ["i2c", "sda", "scl", "stemma", "qwiic"]):
        roles.append("i2c_bus_header")
    if _has_any(lower, ["spi", "miso", "mosi", "sclk", "cs"]):
        roles.append("spi_bus_header")
    if _has_any(lower, ["vcc", "vin", "5v", "3v3", "3.3v", "gnd", "power", "battery", "jst", "barrel"]):
        roles.append("power_input_or_rail")
    if _has_any(lower, ["motor", "load", "terminal", "relay", "output", "speaker"]):
        roles.append("load_or_motor_output")
    if _has_any(lower, ["rj45", "ethernet", "rs485", "canh", "canl", "can bus"]):
        roles.append("network_or_fieldbus")
    if _has_any(lower, ["hdmi", "display", "lcd", "oled", "screen"]):
        roles.append("display_or_ui")
    return _dedupe(roles) or ["unknown_external_interface"]


def _connector_capabilities(roles: Sequence[str], text: str) -> List[str]:
    caps = set(_capabilities_from_text(text))
    role_caps = {
        "usb2_connector": ["connector", "usb"],
        "uart_serial_header": ["connector", "usb_serial"],
        "debug_or_gpio_header": ["connector", "controller"],
        "i2c_bus_header": ["connector", "sensor_or_adc"],
        "spi_bus_header": ["connector", "sensor_or_adc"],
        "power_input_or_rail": ["connector", "power"],
        "load_or_motor_output": ["connector", "actuator_or_load"],
        "network_or_fieldbus": ["connector", "network_interface"],
        "display_or_ui": ["connector", "display_or_ui"],
    }
    for role in roles:
        caps.update(role_caps.get(str(role), ["connector"]))
    return sorted(caps or {"connector"})


def _capabilities_from_text(text: Any) -> List[str]:
    lower = str(text or "").lower()
    mapping = [
        (("ch340", "cp210", "ft232", "uart", "usb bridge", "usb serial"), "usb_serial"),
        (("usb", "header", "connector", "port", "gpio", "jst", "terminal", "socket"), "connector"),
        (("regulator", "buck", "boost", "ldo", "ams1117", "1117", "lm2596", "mp1584", "5v", "3.3v", "power"), "power"),
        (("esp32", "stm32", "rp2040", "atmega", "mcu", "processor", "cpu", "controller"), "controller"),
        (("bme", "bmp", "sht", "sensor", "adc", "i2c", "spi"), "sensor_or_adc"),
        (("ethernet", "rs485", "canh", "canl", "max485", "rj45"), "network_interface"),
        (("hdmi", "display", "oled", "lcd"), "display_or_ui"),
        (("motor", "relay", "mosfet", "driver", "load", "speaker"), "actuator_or_load"),
    ]
    return _dedupe(cap for terms, cap in mapping if any(term in lower for term in terms))


def _pin_count(connector: Dict[str, Any], text: str) -> int | None:
    raw = connector.get("pin_count") or connector.get("pins") or connector.get("pin_count_estimate")
    value = _safe_int(raw)
    if value:
        return value
    tokens = _tokens(text)
    for index, token in enumerate(tokens[:-1]):
        number = _safe_int(token)
        if number and tokens[index + 1] in {"pin", "pins", "p"}:
            return number
    for token in tokens:
        if token.endswith("pin"):
            number = _safe_int(token[:-3])
            if number:
                return number
    return None


def _geometry_record(item: Dict[str, Any], source_type: str, canonical_map: Dict[str, Any]) -> Dict[str, Any]:
    bbox = _normalized_bbox(item, source_type, canonical_map)
    map_item = _map_item(item, source_type, canonical_map)
    return {
        "normalized_bbox": bbox,
        "board_zone": (map_item or {}).get("board_zone") or _board_zone(bbox),
        "geometry_status": (item.get("geometry") or {}).get("status")
        if isinstance(item.get("geometry"), dict)
        else (map_item or {}).get("geometry_status") or ("normalized_visual" if bbox else "unmapped"),
        "map_id": (map_item or {}).get("map_id"),
    }


def _normalized_bbox(item: Dict[str, Any], source_type: str, canonical_map: Dict[str, Any]) -> List[float] | None:
    geometry = item.get("geometry") if isinstance(item.get("geometry"), dict) else {}
    bbox = geometry.get("normalized_bbox")
    if _is_bbox(bbox):
        return [round(float(value), 4) for value in bbox]
    raw = item.get("bbox") or item.get("bounding_box")
    if _is_bbox(raw) and max(float(value) for value in raw) <= 1.0:
        return [round(float(value), 4) for value in raw]
    map_item = _map_item(item, source_type, canonical_map)
    mapped = map_item.get("normalized_bbox") if isinstance(map_item, dict) else None
    if _is_bbox(mapped):
        return [round(float(value), 4) for value in mapped]
    return None


def _map_item(item: Dict[str, Any], source_type: str, canonical_map: Dict[str, Any]) -> Dict[str, Any]:
    item_ref = str(item.get("id") or item.get("ref") or item.get("label") or "")
    if not item_ref:
        return {}
    wanted = f"{source_type}:{item_ref}"
    for row in _list_dicts(canonical_map.get("items")):
        if row.get("map_id") == wanted:
            return row
    label = str(item.get("label") or "").lower()
    for row in _list_dicts(canonical_map.get("items")):
        if str(row.get("evidence_type") or "") != source_type:
            continue
        if label and label == str(row.get("label") or "").lower():
            return row
    return {}


def _geometry_distance(a: Any, b: Any) -> float | None:
    a_bbox = a.get("normalized_bbox") if isinstance(a, dict) else None
    b_bbox = b.get("normalized_bbox") if isinstance(b, dict) else None
    if not (_is_bbox(a_bbox) and _is_bbox(b_bbox)):
        return None
    ax, ay = _center(a_bbox)
    bx, by = _center(b_bbox)
    return sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def _center(bbox: Sequence[float]) -> tuple[float, float]:
    return ((float(bbox[0]) + float(bbox[2])) / 2, (float(bbox[1]) + float(bbox[3])) / 2)


def _board_zone(bbox: Any) -> str:
    if not _is_bbox(bbox):
        return "unmapped"
    x1, y1, x2, y2 = [float(value) for value in bbox]
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    vertical = "top" if cy < 0.33 else "bottom" if cy > 0.67 else "middle"
    horizontal = "left" if cx < 0.33 else "right" if cx > 0.67 else "center"
    return f"{vertical}_{horizontal}" if vertical != "middle" or horizontal != "center" else "center"


def _visual_confidence(item: Dict[str, Any], bbox: Sequence[float] | None) -> float:
    confidence = max(0.35, min(_safe_float(item.get("confidence"), 0.58), 0.84))
    support_count = int(item.get("support_count") or len(_source_photo_ids(item)) or 1)
    confidence += min(0.08, 0.03 * max(support_count - 1, 0))
    if bbox:
        confidence += 0.04
    if item.get("identity_status") == "marking_linked_candidate":
        confidence += 0.06
    return round(min(0.9, confidence), 3)


def _has_multiview(board: Dict[str, Any], reconstruction: Dict[str, Any]) -> bool:
    mv = board.get("multiview_reconstruction") if isinstance(board.get("multiview_reconstruction"), dict) else {}
    return bool(
        int(reconstruction.get("usable_observation_count") or 0) >= 2
        or int(mv.get("usable_observation_count") or 0) >= 2
        or str((reconstruction.get("reconstruction_summary") or {}).get("level") or "").startswith("multi_view")
    )


def _task(
    task_id: str,
    task_type: str,
    category: str,
    priority: int,
    prompt: str,
    unlocks: str,
    usable_for: Sequence[str],
    *,
    target: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    row = {
        "task_id": task_id,
        "type": task_type,
        "category": category,
        "status": "open",
        "priority": priority,
        "prompt": prompt,
        "source": "visual_topology_hypothesis",
        "unlocks": unlocks,
        "usable_for": list(usable_for),
    }
    if target:
        row["target"] = target
    return row


def _target_record(item: Dict[str, Any]) -> Dict[str, Any]:
    geometry = item.get("geometry") if isinstance(item.get("geometry"), dict) else {}
    return {
        "ref": item.get("component_ref") or item.get("connector_ref") or item.get("ref"),
        "label": item.get("label"),
        "source_type": item.get("source_type"),
        "normalized_bbox": item.get("normalized_bbox") or geometry.get("normalized_bbox"),
        "board_zone": item.get("board_zone") or geometry.get("board_zone"),
        "geometry_status": item.get("geometry_status") or geometry.get("geometry_status"),
        "map_id": item.get("map_id") or geometry.get("map_id"),
    }


def _item_text(item: Dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ["label", "kind", "type", "function", "notes", "visible_text", "marking"]
    ).strip()


def _source_photo_ids(item: Dict[str, Any]) -> List[str]:
    return _dedupe(
        ref.get("photo_id")
        for ref in item.get("source_refs") or []
        if isinstance(ref, dict) and ref.get("photo_id")
    )


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _dedupe(values: Iterable[Any]) -> List[Any]:
    rows = []
    seen = set()
    for value in values:
        if value in (None, ""):
            continue
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        rows.append(value)
    return rows


def _dedupe_rows(rows: Sequence[Dict[str, Any]], *, key_fields: Sequence[str]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = tuple(str(row.get(field) or "") for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def _dedupe_tasks(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("type") or ""), str(row.get("prompt") or "").strip().lower())
        if not key[1] or key in seen:
            continue
        seen.add(key)
        kept.append(dict(row))
    return kept


def _safe_id(value: Any) -> str:
    text = str(value or "item").strip().lower()
    chars = [char if char.isalnum() else "_" for char in text]
    compact = "_".join(part for part in "".join(chars).split("_") if part)
    return compact or "item"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _tokens(value: Any) -> List[str]:
    tokens: List[str] = []
    current: List[str] = []
    for char in str(value or "").lower():
        if char.isalnum() or char == ".":
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _has_any(text: Any, terms: Sequence[str]) -> bool:
    lower = str(text or "").lower()
    return any(term in lower for term in terms)


def _is_bbox(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    try:
        numbers = [float(item) for item in value]
    except (TypeError, ValueError):
        return False
    return numbers[2] > numbers[0] and numbers[3] > numbers[1]
