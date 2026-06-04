"""Circuit-backed functional salvage contracts.

This module converts a board-level circuit graph into reusable function blocks.
The output is intentionally plain dictionaries because the existing Circuit-AI
API surface is dictionary based, but every payload is versioned so stricter
models can be introduced later without changing the wire shape.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


SCHEMA_VERSION = "functional_salvage.v1"


CAPABILITY_ALIASES = {
    "firmware_controller": "controller",
    "programmable_debuggable": "controller",
    "i2c_expansion": "sensor_or_adc",
    "uart_link": "usb_serial",
    "usb_device_or_bridge": "usb_serial",
    "pwm_actuation": "actuator_driver",
    "power_distribution_or_input": "power",
    "load_or_motor_control": "actuator_driver",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:80] or "functional_block"


def _dedupe(items: Iterable[Any], *, limit: int = 80) -> List[str]:
    kept: List[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        kept.append(text)
        if len(kept) >= limit:
            break
    return kept


def _compact(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _component_capabilities(component: Dict[str, Any]) -> Tuple[Optional[str], List[str], str]:
    category = str(component.get("category") or "").lower()
    value = str(component.get("value") or "").lower()
    text = f"{category} {value}"
    if category == "mcu":
        caps = ["controller"]
        if any(token in text for token in ["esp32", "esp8266", "nrf", "wifi", "ble"]):
            caps.append("wireless")
        return "controller_core", caps, "whole_board_reuse"
    if category == "sensor" or any(token in text for token in ["bme280", "bmp280", "sht", "mpu", "sensor", "ads1115"]):
        return "sensor_interface", ["sensor_or_adc"], "connector_reuse"
    if category == "regulator" or any(token in text for token in ["regulator", "buck", "boost", "ldo", "ams1117", "lm2596"]):
        return "power_regulation", ["power"], "board_section_cut_candidate"
    if category == "motor_driver" or any(token in text for token in ["motor", "drv", "tb6612", "a4988", "mosfet", "relay"]):
        return "actuator_driver", ["actuator_driver", "motor_or_load"], "connector_reuse"
    if category == "radio" or any(token in text for token in ["wifi", "ble", "lora", "radio", "nrf24"]):
        return "wireless_radio", ["wireless", "network_interface"], "whole_board_reuse"
    if category == "transceiver":
        if any(token in text for token in ["ch340", "cp210", "ft232", "uart"]):
            return "usb_serial_bridge", ["usb_serial", "connector"], "whole_board_reuse"
        return "network_interface", ["network_interface", "connector"], "whole_board_reuse"
    if any(token in text for token in ["oled", "lcd", "display", "ssd1306", "led"]):
        return "display_or_ui", ["display_or_ui", "led_or_light"], "connector_reuse"
    return None, [], "not_recommended"


def _capabilities_from_contract(contract: Dict[str, Any]) -> List[str]:
    caps = []
    for cap in contract.get("capabilities") or []:
        caps.append(CAPABILITY_ALIASES.get(str(cap), str(cap)))
    return _dedupe(caps, limit=20)


def _connector_capabilities(connector: Dict[str, Any], primary_role: str) -> List[str]:
    caps = ["connector"]
    roles = {str(pin.get("role") or "") for pin in connector.get("pins") or [] if isinstance(pin, dict)}
    interfaces = {
        str(item.get("interface") or "")
        for item in connector.get("interfaces") or []
        if isinstance(item, dict)
    }
    semantic_role = str(connector.get("semantic_role") or "")
    if connector.get("power_nets"):
        caps.append("power")
    if "i2c" in roles or "i2c" in interfaces:
        caps.append("sensor_or_adc" if primary_role == "sensor_io" else "connector")
    if "spi" in roles or "spi" in interfaces:
        caps.append("sensor_or_adc" if primary_role == "sensor_io" else "connector")
    if "uart" in roles or "uart" in interfaces:
        caps.append("usb_serial")
    if "usb2" in roles or "usb2" in interfaces:
        caps.append("usb_serial")
    if "pwm" in roles or semantic_role == "actuation":
        caps.extend(["actuator_driver", "motor_or_load"])
    if semantic_role == "control_harness":
        caps.append("switch_or_button")
    return _dedupe(caps, limit=12)


def _suggested_uses(caps: Sequence[str]) -> List[str]:
    uses: List[str] = []
    cap_set = set(caps)
    if "controller" in cap_set:
        uses.extend(["automation controller", "sensor logger controller", "smart switch brain"])
    if "wireless" in cap_set:
        uses.extend(["wireless control link", "network status module", "Bluetooth/WiFi bridge"])
    if "sensor_or_adc" in cap_set:
        uses.extend(["sensor input module", "data logger input", "trigger or feedback sensor"])
    if "power" in cap_set:
        uses.extend(["protected power breakout", "known-voltage supply stage", "bench adapter"])
    if "actuator_driver" in cap_set or "motor_or_load" in cap_set:
        uses.extend(["low-voltage load controller", "motor test jig", "motion or fan driver"])
    if "usb_serial" in cap_set:
        uses.extend(["debug adapter", "serial console", "bring-up harness"])
    if "display_or_ui" in cap_set or "led_or_light" in cap_set:
        uses.extend(["status indicator", "task light", "user interface"])
    if "connector" in cap_set:
        uses.extend(["labeled harness", "breakout cable", "safe splice entry point"])
    return _dedupe(uses, limit=8) or ["parts evidence for a future build"]


def _block(
    *,
    board_id: str,
    function_type: str,
    name: str,
    capabilities: Sequence[str],
    source_refs: Sequence[str],
    connector_refs: Sequence[str] = (),
    nets: Sequence[str] = (),
    extraction_class: str,
    confidence: float,
    rationale: str,
) -> Dict[str, Any]:
    caps = _dedupe([str(cap).lower() for cap in capabilities], limit=16)
    refs = _dedupe(source_refs, limit=20)
    connectors = _dedupe(connector_refs, limit=12)
    net_rows = _dedupe(nets, limit=20)
    block_id = _safe_id(f"{board_id}_{function_type}_{'_'.join(refs[:4]) or name}")
    return {
        "schema_version": SCHEMA_VERSION,
        "block_id": block_id,
        "board_id": board_id,
        "name": name,
        "function_type": function_type,
        "capabilities": caps,
        "source": "circuit_functional_salvage",
        "source_refs": refs,
        "connector_refs": connectors,
        "nets": net_rows,
        "confidence": round(max(0.0, min(confidence, 0.98)), 3),
        "extractability": {
            "class": extraction_class,
            "action": _extractability_action(extraction_class, caps),
            "requires_layout_confirmation": extraction_class == "board_section_cut_candidate",
        },
        "suggested_uses": _suggested_uses(caps),
        "rationale": rationale,
    }


def _extractability_action(extraction_class: str, caps: Sequence[str]) -> str:
    cap_set = set(caps)
    if extraction_class == "connector_reuse":
        return "Reuse through labeled connector or harness after pinout, voltage, and ground gates close."
    if extraction_class == "whole_board_reuse":
        return "Reuse the whole board/module where possible; do not assume the IC can be cut out and still work."
    if extraction_class == "board_section_cut_candidate":
        return "Treat as a possible board-section salvage only after layout continuity, isolation, and thermal checks."
    if "battery" in cap_set:
        return "Safety review only; do not reuse damaged or unknown packs."
    return "Recover intact and prove the function before connecting it to another board."


def _gate_relevance(gate: Dict[str, Any], block: Dict[str, Any]) -> int:
    text = _compact(
        " ".join(
            [
                str(gate.get("measurement_id") or ""),
                str(gate.get("gate_id") or ""),
                str(gate.get("target") or ""),
                str(gate.get("prompt") or ""),
                " ".join(str(item) for item in gate.get("evidence") or []),
            ]
        )
    )
    if not text:
        return 0
    score = 0
    for token in [*block.get("source_refs", []), *block.get("connector_refs", []), *block.get("nets", [])]:
        compact = _compact(token)
        if len(compact) < 2:
            continue
        if compact and compact in text:
            score += 2
    matched_block_evidence = score > 0
    if not matched_block_evidence and (block.get("source_refs") or block.get("connector_refs") or block.get("nets")):
        return 0
    caps = set(block.get("capabilities") or [])
    gate_type = str(gate.get("type") or "").lower()
    stage = str(gate.get("stage") or "").lower()
    if "power" in caps and gate_type in {"voltage", "polarity", "current_limit", "load_current"}:
        score += 1
    if "connector" in caps and "connector" in stage:
        score += 1
    if caps & {"sensor_or_adc", "usb_serial", "controller"} and gate_type in {"logic_level", "functional_check"}:
        score += 1
    if caps & {"actuator_driver", "motor_or_load"} and gate_type in {"current_limit", "load_current", "voltage"}:
        score += 1
    return score


def _serialize_gate(gate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "gate_id": gate.get("measurement_id") or gate.get("gate_id"),
        "gate_type": gate.get("type"),
        "stage": gate.get("stage"),
        "target": gate.get("target"),
        "prompt": gate.get("prompt"),
        "acceptance": gate.get("acceptance"),
        "status": gate.get("status", "open"),
        "blocks_before_done": gate.get("blocks_before_done") or [],
    }


def _block_gates(block: Dict[str, Any], measurement_plan: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scored = []
    for gate in measurement_plan:
        if not isinstance(gate, dict):
            continue
        score = _gate_relevance(gate, block)
        if score:
            scored.append((score, gate))
    scored.sort(key=lambda row: (-row[0], str(row[1].get("target") or "")))
    return [_serialize_gate(gate) for _, gate in scored[:8]]


def _block_status(
    block: Dict[str, Any],
    gates: Sequence[Dict[str, Any]],
    risks: Sequence[Dict[str, Any]],
    electrical_viability: Dict[str, Any],
) -> str:
    if any(str(gate.get("status")) == "failed" for gate in gates):
        return "blocked_failed_evidence"
    if electrical_viability.get("verdict") == "overcurrent_blocked" and set(block.get("capabilities") or []) & {
        "power",
        "actuator_driver",
        "motor_or_load",
    }:
        return "electrical_viability_hold"
    if any(str(gate.get("status", "open")) != "closed" and gate.get("blocks_before_done") for gate in gates):
        return "blocked_until_evidence"
    high_risk_refs = _dedupe(
        item
        for risk in risks
        if isinstance(risk, dict) and risk.get("severity") in {"critical", "error", "high"}
        for item in risk.get("evidence") or []
    )
    block_refs = set(block.get("source_refs") or []) | set(block.get("connector_refs") or []) | set(block.get("nets") or [])
    if high_risk_refs and block_refs & set(high_risk_refs):
        return "review_required"
    if block.get("extractability", {}).get("class") == "board_section_cut_candidate":
        return "layout_review_required"
    return "reuse_ready"


def _component_blocks(board_id: str, components: Sequence[Dict[str, Any]], primary_role: str) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for component in components:
        if not isinstance(component, dict):
            continue
        function_type, caps, extraction_class = _component_capabilities(component)
        if not function_type:
            continue
        group = grouped.setdefault(
            function_type,
            {
                "refs": [],
                "values": [],
                "nets": [],
                "caps": [],
                "extraction_class": extraction_class,
                "confidence": 0.66,
            },
        )
        group["refs"].append(component.get("ref"))
        group["values"].append(component.get("value"))
        group["nets"].extend(component.get("nets") or [])
        group["caps"].extend(caps)
        if function_type == "controller_core" and primary_role == "controller":
            group["confidence"] = 0.82
        elif function_type in {"sensor_interface", "power_regulation", "actuator_driver"}:
            group["confidence"] = max(group["confidence"], 0.74)

    blocks = []
    for function_type, group in grouped.items():
        label = function_type.replace("_", " ")
        values = _dedupe(group["values"], limit=4)
        if values:
            label = f"{label}: {', '.join(values)}"
        blocks.append(
            _block(
                board_id=board_id,
                function_type=function_type,
                name=label,
                capabilities=group["caps"],
                source_refs=group["refs"],
                nets=group["nets"],
                extraction_class=group["extraction_class"],
                confidence=group["confidence"],
                rationale="Detected from active component category and connected nets.",
            )
        )
    return blocks


def _connector_blocks(
    board_id: str,
    connectors: Sequence[Dict[str, Any]],
    primary_role: str,
) -> List[Dict[str, Any]]:
    blocks = []
    for connector in connectors:
        if not isinstance(connector, dict):
            continue
        ref = str(connector.get("connector_ref") or "")
        if not ref:
            continue
        caps = _connector_capabilities(connector, primary_role)
        interfaces = _dedupe(
            item.get("interface")
            for item in connector.get("interfaces") or []
            if isinstance(item, dict) and item.get("interface")
        )
        power_nets = connector.get("power_nets") or []
        signal_nets = connector.get("signal_nets") or []
        role = connector.get("splice_role") or connector.get("semantic_role") or "connector"
        name_parts = [ref, str(role).replace("_", " ")]
        if interfaces:
            name_parts.append("/".join(interfaces))
        blocks.append(
            _block(
                board_id=board_id,
                function_type="external_interface",
                name=" ".join(name_parts),
                capabilities=caps,
                source_refs=[ref],
                connector_refs=[ref],
                nets=[*power_nets, *signal_nets],
                extraction_class="connector_reuse",
                confidence=0.72 if connector.get("splice_allowed_after_gates") else 0.55,
                rationale="Detected from connector pin roles, exposed rails, and interface signals.",
            )
        )
    return blocks


def _board_role_block(
    board_id: str,
    primary_role: str,
    capability_contract: Dict[str, Any],
    connectors: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not primary_role or primary_role == "board":
        return None
    caps = _capabilities_from_contract(capability_contract)
    if primary_role == "controller":
        caps.append("controller")
    elif primary_role == "sensor_io":
        caps.append("sensor_or_adc")
    elif primary_role == "power_board":
        caps.append("power")
    elif primary_role == "motor_control":
        caps.extend(["actuator_driver", "motor_or_load"])
    elif primary_role == "interface_board":
        caps.append("connector")
    caps = _dedupe(caps, limit=16)
    if not caps:
        return None
    connector_refs = [
        str(row.get("connector_ref"))
        for row in connectors
        if isinstance(row, dict) and row.get("connector_ref")
    ]
    extraction = "whole_board_reuse" if "controller" in caps or "wireless" in caps else "connector_reuse"
    return _block(
        board_id=board_id,
        function_type=f"{primary_role}_board_function",
        name=f"{primary_role.replace('_', ' ')} board function",
        capabilities=caps,
        source_refs=[primary_role, *connector_refs[:4]],
        connector_refs=connector_refs,
        nets=[],
        extraction_class=extraction,
        confidence=0.68,
        rationale="Detected from board-level role and capability contract.",
    )


def _dedupe_blocks(blocks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for block in blocks:
        caps = tuple(sorted(block.get("capabilities") or []))
        key = (block.get("function_type"), tuple(block.get("source_refs") or []), caps)
        if key in seen:
            continue
        seen.add(key)
        kept.append(block)
    return kept[:40]


def infer_board_functional_salvage(board: Dict[str, Any]) -> Dict[str, Any]:
    """Infer reusable function blocks from a circuit board model."""

    board_id = str(board.get("board_id") or "board")
    primary_role = str(board.get("primary_role") or "")
    components = board.get("components") if isinstance(board.get("components"), list) else []
    connectors = board.get("connector_contracts") if isinstance(board.get("connector_contracts"), list) else []
    measurement_plan = board.get("measurement_plan") if isinstance(board.get("measurement_plan"), list) else []
    risks = board.get("electrical_risks") if isinstance(board.get("electrical_risks"), list) else []
    electrical_viability = board.get("electrical_viability") if isinstance(board.get("electrical_viability"), dict) else {}
    capability_contract = board.get("capability_contract") if isinstance(board.get("capability_contract"), dict) else {}

    blocks = [
        *_component_blocks(board_id, components, primary_role),
        *_connector_blocks(board_id, connectors, primary_role),
    ]
    role_block = _board_role_block(board_id, primary_role, capability_contract, connectors)
    if role_block:
        blocks.append(role_block)

    enriched = []
    all_gates: Dict[str, Dict[str, Any]] = {}
    for block in _dedupe_blocks(blocks):
        gates = _block_gates(block, measurement_plan)
        block["evidence_gates"] = gates
        block["missing_evidence"] = [
            str(gate.get("prompt"))
            for gate in gates
            if str(gate.get("status", "open")) != "closed" and gate.get("prompt")
        ][:8]
        block["status"] = _block_status(block, gates, risks, electrical_viability)
        block["reuse_value_score"] = _reuse_value_score(block)
        for gate in gates:
            if gate.get("gate_id"):
                all_gates[str(gate["gate_id"])] = gate
        enriched.append(block)

    verdict = _functional_verdict(enriched)
    return {
        "mode": "functional_salvage_assessment",
        "schema_version": SCHEMA_VERSION,
        "board_id": board_id,
        "board_role": primary_role,
        "verdict": verdict,
        "reusable_blocks": sorted(enriched, key=lambda row: (-_safe_float(row.get("reuse_value_score")), row.get("block_id") or "")),
        "evidence_gates": list(all_gates.values())[:60],
        "extractability_summary": _extractability_summary(enriched),
        "safety_policy": {
            "reuse_ready_requires": [
                "power and ground gates closed",
                "logic or load compatibility proven",
                "current limit or load current known before interconnect",
                "no high-severity unresolved risk on the reused block",
            ],
            "default_for_unknowns": "blocked_until_evidence",
        },
    }


def _reuse_value_score(block: Dict[str, Any]) -> float:
    cap_weight = {
        "controller": 0.16,
        "wireless": 0.16,
        "sensor_or_adc": 0.13,
        "actuator_driver": 0.13,
        "power": 0.12,
        "usb_serial": 0.10,
        "connector": 0.06,
        "motor_or_load": 0.08,
        "display_or_ui": 0.08,
        "led_or_light": 0.05,
        "network_interface": 0.09,
    }
    score = _safe_float(block.get("confidence"), 0.4)
    for cap in block.get("capabilities") or []:
        score += cap_weight.get(str(cap), 0.02)
    if block.get("connector_refs"):
        score += 0.05
    if block.get("status") == "reuse_ready":
        score += 0.08
    elif block.get("status") in {"blocked_failed_evidence", "electrical_viability_hold"}:
        score -= 0.22
    return round(max(0.0, min(score, 0.99)), 3)


def _functional_verdict(blocks: Sequence[Dict[str, Any]]) -> str:
    if not blocks:
        return "collect_more_evidence"
    statuses = {str(block.get("status") or "") for block in blocks}
    if statuses & {"blocked_failed_evidence", "electrical_viability_hold"}:
        return "failed_evidence_hold"
    if "reuse_ready" in statuses and not (statuses & {"blocked_until_evidence", "layout_review_required", "review_required"}):
        return "reuse_ready"
    if "reuse_ready" in statuses:
        return "partially_reuse_ready"
    if statuses & {"blocked_until_evidence", "layout_review_required", "review_required"}:
        return "blocked_until_evidence"
    return "collect_more_evidence"


def _extractability_summary(blocks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for block in blocks:
        key = str((block.get("extractability") or {}).get("class") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return {
        "counts": dict(sorted(counts.items())),
        "preferred_order": [
            "connector_reuse",
            "whole_board_reuse",
            "desolder_module",
            "board_section_cut_candidate",
            "not_recommended",
            "unsafe_hold",
        ],
    }


def aggregate_functional_salvage(boards: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate board-level functional salvage reports for multi-board work."""

    reports = [
        board.get("functional_salvage")
        for board in boards
        if isinstance(board, dict) and isinstance(board.get("functional_salvage"), dict)
    ]
    blocks = [
        block
        for report in reports
        for block in report.get("reusable_blocks") or []
        if isinstance(block, dict)
    ]
    gates = [
        gate
        for report in reports
        for gate in report.get("evidence_gates") or []
        if isinstance(gate, dict)
    ]
    verdict = _functional_verdict(blocks)
    return {
        "mode": "functional_salvage_portfolio",
        "schema_version": SCHEMA_VERSION,
        "verdict": verdict,
        "board_count": len(reports),
        "reusable_block_count": len(blocks),
        "ready_block_count": len([block for block in blocks if block.get("status") == "reuse_ready"]),
        "blocked_block_count": len([block for block in blocks if str(block.get("status") or "").startswith("blocked")]),
        "top_reusable_blocks": sorted(blocks, key=lambda row: (-_safe_float(row.get("reuse_value_score")), row.get("block_id") or ""))[:12],
        "evidence_gate_count": len(gates),
        "open_gate_count": len([gate for gate in gates if str(gate.get("status", "open")) != "closed"]),
        "boards": [
            {
                "board_id": report.get("board_id"),
                "board_role": report.get("board_role"),
                "verdict": report.get("verdict"),
                "reusable_block_count": len(report.get("reusable_blocks") or []),
            }
            for report in reports
        ],
    }
