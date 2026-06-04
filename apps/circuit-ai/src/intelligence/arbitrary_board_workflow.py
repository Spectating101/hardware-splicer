"""Arbitrary-board diagnostic workflow enrichment.

This layer sits above evidence authority. Authority decides what is safe; this
module decides what the board is probably useful for, what contradicts that
story, what measurements to run next, and whether repair, reuse, salvage, or
scrap is the best posture.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from src.intelligence.bench_protocols import build_bench_protocol_pack


SCHEMA_VERSION = "arbitrary_board_workflow.v1"

KNOWN_PARTS = [
    {
        "part_id": "ch340_usb_uart",
        "patterns": ("CH340", "CH340C", "CH340G", "CH340N"),
        "family": "USB/UART bridge",
        "capabilities": ("usb_serial", "connector"),
        "function_id": "usb_serial_debug_bridge",
        "key_specs": {"interface": "USB to UART", "logic_voltage": "3.3V or 5V board-dependent", "typical_use": "serial debug adapter"},
        "verification_required": ("measured pinout", "logic voltage", "shared ground", "loopback or safe serial capture"),
        "common_faults": ("USB connector damage", "ESD damage", "wrong logic-voltage connection", "driver or boot-mode issue"),
        "replacement_parts": ("CP2102", "FT232RL"),
    },
    {
        "part_id": "cp210x_usb_uart",
        "patterns": ("CP2102", "CP2104", "CP210X"),
        "family": "USB/UART bridge",
        "capabilities": ("usb_serial", "connector"),
        "function_id": "usb_serial_debug_bridge",
        "key_specs": {"interface": "USB to UART", "logic_voltage": "3.3V typical", "typical_use": "serial debug adapter"},
        "verification_required": ("measured pinout", "logic voltage", "shared ground", "loopback or safe serial capture"),
        "common_faults": ("ESD damage", "USB connector damage", "wrong logic-voltage connection"),
        "replacement_parts": ("CH340C", "FT232RL"),
    },
    {
        "part_id": "ft232_usb_uart",
        "patterns": ("FT232", "FT232R", "FT232RL"),
        "family": "USB/UART bridge",
        "capabilities": ("usb_serial", "connector"),
        "function_id": "usb_serial_debug_bridge",
        "key_specs": {"interface": "USB to UART", "logic_voltage": "configurable by board", "typical_use": "serial debug adapter"},
        "verification_required": ("measured pinout", "logic voltage", "shared ground", "loopback or safe serial capture"),
        "common_faults": ("USB connector damage", "counterfeit/driver mismatch", "wrong logic-voltage connection"),
        "replacement_parts": ("CH340C", "CP2102"),
    },
    {
        "part_id": "ams1117_ldo",
        "patterns": ("AMS1117", "AMS1117-3.3", "AMS1117 3.3", "AMS1117-5.0", "LM1117", "LD1117"),
        "family": "linear regulator",
        "capabilities": ("power", "protection"),
        "function_id": "power_distribution_or_regulator",
        "key_specs": {"type": "LDO regulator", "output_current": "about 1A package/thermal dependent", "dropout": "high dropout; needs input headroom"},
        "verification_required": ("input voltage", "output voltage", "load current", "thermal behavior"),
        "common_faults": ("overheating", "insufficient input headroom", "shorted output capacitor or load"),
        "replacement_parts": ("LD1117", "LM1117", "AP2112 for lower-current 3.3V rails"),
    },
    {
        "part_id": "lm2596_buck",
        "patterns": ("LM2596", "MP1584", "XL4015", "XL4016"),
        "family": "buck regulator",
        "capabilities": ("power", "protection"),
        "function_id": "power_distribution_or_regulator",
        "key_specs": {"type": "switching buck regulator", "requires": "inductor, diode/switch path, feedback divider", "typical_use": "step-down supply"},
        "verification_required": ("no-short", "output voltage", "load current", "ripple/thermal behavior"),
        "common_faults": ("shorted diode/switch", "wrong feedback value", "overheated inductor or regulator"),
        "replacement_parts": ("MP1584 module", "LM2596 module"),
    },
    {
        "part_id": "bme_bmp_sensor",
        "patterns": ("BME280", "BMP280", "SHT31", "SHT30", "AHT20", "MPU6050", "ADS1115"),
        "family": "sensor or ADC",
        "capabilities": ("sensor_or_adc", "connector"),
        "function_id": "sensor_or_adc_module",
        "key_specs": {"interface": "I2C/SPI or analog depending on part", "typical_use": "sensor input or data logging"},
        "verification_required": ("supply voltage", "bus pullups", "bus scan", "stable reading"),
        "common_faults": ("wrong voltage domain", "missing/stuck pullups", "address conflict", "damaged sensor front-end"),
        "replacement_parts": ("BME280 breakout", "ADS1115 breakout", "SHT31 breakout"),
    },
    {
        "part_id": "motor_driver_family",
        "patterns": ("DRV8833", "TB6612", "L298N", "A4988", "DRV8825", "ULN2003"),
        "family": "motor or load driver",
        "capabilities": ("actuator_driver", "motor_or_load", "power"),
        "function_id": "load_or_motor_driver",
        "key_specs": {"type": "protected load or motor driver", "requires": "supply current limit and load validation"},
        "verification_required": ("no-short", "dummy-load output", "load current", "flyback/protection", "thermal behavior"),
        "common_faults": ("shorted output switch", "overheated driver", "missing flyback path", "wrong motor supply"),
        "replacement_parts": ("DRV8833", "TB6612", "logic-level MOSFET driver"),
    },
    {
        "part_id": "esp_wireless_controller",
        "patterns": ("ESP32", "ESP8266"),
        "family": "wireless controller",
        "capabilities": ("controller", "wireless", "connector"),
        "function_id": "controller_module",
        "key_specs": {"type": "WiFi/BLE MCU module", "requires": "3.3V rail and boot/current validation", "firmware_state": "unknown until observed"},
        "verification_required": ("3.3V rail", "boot/current behavior", "serial console or scan", "I/O voltage domain"),
        "common_faults": ("bad regulator", "unknown firmware output", "damaged RF path", "boot-mode issue"),
        "replacement_parts": ("ESP32 dev board", "ESP8266 module", "RP2040 plus radio module"),
    },
    {
        "part_id": "controller_family",
        "patterns": ("ATMEGA328", "ATMEGA328P", "STM32", "RP2040", "PIC16", "PIC18"),
        "family": "controller or embedded compute",
        "capabilities": ("controller", "connector"),
        "function_id": "controller_module",
        "key_specs": {"type": "MCU/controller", "requires": "power rail and I/O voltage confirmation", "firmware_state": "unknown until observed"},
        "verification_required": ("power rails", "boot/current behavior", "reset state", "I/O voltage domain"),
        "common_faults": ("unknown firmware output", "damaged I/O", "bad regulator", "boot-mode issue"),
        "replacement_parts": ("ESP32 dev board", "RP2040 board", "Arduino-compatible MCU board"),
    },
    {
        "part_id": "single_board_computer_family",
        "patterns": ("RASPBERRY PI", "RASPBERRYPI", "BCM2711", "BCM2837", "SINGLE BOARD COMPUTER", "SBC"),
        "family": "single-board computer",
        "capabilities": ("controller", "network_interface", "display_or_ui", "connector", "power"),
        "function_id": "single_board_computer_module",
        "key_specs": {"type": "Linux-capable embedded compute board", "requires": "known power input, boot evidence, connector map, and storage state"},
        "verification_required": ("power input voltage/current", "boot/current behavior", "GPIO voltage domain", "connector map", "storage/media state"),
        "common_faults": ("damaged power connector", "corrupt storage", "shorted GPIO", "overheated SoC", "unknown firmware or data state"),
        "replacement_parts": ("Raspberry Pi board", "RP2040/ESP32 board for simpler controller use"),
    },
    {
        "part_id": "display_ui_family",
        "patterns": ("SSD1306", "SH1106", "ILI9341", "ST7735", "TM1637", "MAX7219"),
        "family": "display or UI",
        "capabilities": ("display_or_ui", "connector"),
        "function_id": "display_or_ui_module",
        "key_specs": {"interface": "I2C/SPI/parallel varies by module", "typical_use": "display, indicator, or input panel"},
        "verification_required": ("pin map", "current limiting", "interface voltage", "protected I/O test"),
        "common_faults": ("wrong voltage domain", "missing series resistance", "damaged flex/connector"),
        "replacement_parts": ("SSD1306 OLED module", "SPI TFT module"),
    },
    {
        "part_id": "audio_alert_family",
        "patterns": ("PAM8403", "LM386", "BUZZER", "MAX98357"),
        "family": "audio or alert",
        "capabilities": ("speaker_or_audio", "connector"),
        "function_id": "audio_or_alert_module",
        "key_specs": {"type": "audio amplifier or alert output", "requires": "load impedance and supply-current check"},
        "verification_required": ("load impedance", "idle current", "low-level output", "thermal behavior"),
        "common_faults": ("shorted speaker/load", "overheated amplifier", "wrong supply voltage"),
        "replacement_parts": ("PAM8403 module", "MAX98357 module"),
    },
    {
        "part_id": "charger_battery_family",
        "patterns": ("TP4056", "DW01A", "FS8205", "BMS", "LIPO", "LI-ION"),
        "family": "battery charger or protection",
        "capabilities": ("battery", "power"),
        "function_id": "battery_or_charger",
        "key_specs": {"type": "battery charge/protection path", "scope": "specialist safety workflow required"},
        "verification_required": ("chemistry", "cell count", "BMS/protection", "charge path isolation", "thermal containment"),
        "common_faults": ("unsafe cell state", "bypassed protection", "overheated charger", "swollen pack"),
        "replacement_parts": ("protected charger module", "new certified pack"),
    },
    {
        "part_id": "can_transceiver_family",
        "patterns": ("MCP2551", "MCP2562", "TJA1050", "SN65HVD230", "CANH", "CANL"),
        "family": "CAN or differential network transceiver",
        "capabilities": ("network_interface", "connector"),
        "function_id": "wireless_or_rf_module",
        "key_specs": {"interface": "CAN/differential field bus", "requires": "bus termination and common reference checks"},
        "verification_required": ("pin map", "bus termination", "logic voltage", "common ground/reference", "protected bus capture"),
        "common_faults": ("wrong termination", "ESD-damaged bus pins", "ground offset", "wrong logic-voltage domain"),
        "replacement_parts": ("MCP2562 module", "SN65HVD230 module"),
    },
    {
        "part_id": "rs485_transceiver_family",
        "patterns": ("MAX485", "SP3485", "SN75176", "ADM485", "RS485"),
        "family": "RS-485 differential transceiver",
        "capabilities": ("network_interface", "connector"),
        "function_id": "wireless_or_rf_module",
        "key_specs": {"interface": "RS-485 half/full duplex varies by board", "requires": "termination, bias, and direction-control validation"},
        "verification_required": ("pin map", "termination/bias", "logic voltage", "direction control", "protected bus capture"),
        "common_faults": ("missing bias resistors", "bus pin ESD damage", "wrong A/B polarity", "ground offset"),
        "replacement_parts": ("MAX485 module", "SP3485 module"),
    },
    {
        "part_id": "relay_driver_family",
        "patterns": ("SRD-05VDC", "SRD-12VDC", "RELAY", "SONGLE", "G5LE", "JQC-3F"),
        "family": "relay or isolated load switch",
        "capabilities": ("actuator_driver", "motor_or_load", "power"),
        "function_id": "load_or_motor_driver",
        "key_specs": {"type": "relay/load switch", "requires": "coil voltage and contact rating validation"},
        "verification_required": ("coil voltage", "contact rating", "flyback/protection", "dummy-load switching", "thermal behavior"),
        "common_faults": ("welded contacts", "burned relay contacts", "missing flyback diode", "wrong coil voltage"),
        "replacement_parts": ("relay module", "logic-level MOSFET driver", "solid-state relay module"),
    },
    {
        "part_id": "opto_isolator_family",
        "patterns": ("PC817", "EL817", "TLP521", "TLP281", "4N25", "MOC302"),
        "family": "opto-isolator or isolated interface",
        "capabilities": ("protection", "connector"),
        "function_id": "load_or_motor_driver",
        "key_specs": {"type": "isolated signal or load-control interface", "requires": "isolation-domain and current-limit validation"},
        "verification_required": ("input current limit", "output pullup/domain", "isolation boundary", "protected low-current function test"),
        "common_faults": ("open opto LED", "wrong output pullup voltage", "damaged isolation boundary", "mains-adjacent unsafe layout"),
        "replacement_parts": ("PC817 module", "digital isolator module", "opto-triac module with specialist review"),
    },
    {
        "part_id": "mosfet_load_switch_family",
        "patterns": ("AO3400", "AO3401", "IRLZ44", "FQP30N06", "AOD4184", "IRFZ44", "MOSFET"),
        "family": "MOSFET load switch or power transistor",
        "capabilities": ("actuator_driver", "motor_or_load", "power"),
        "function_id": "load_or_motor_driver",
        "key_specs": {"type": "low-side/high-side switch depends on topology", "requires": "dummy-load and gate-drive validation"},
        "verification_required": ("drain-source short check", "gate voltage", "dummy-load switching", "current limit", "thermal behavior"),
        "common_faults": ("shorted MOSFET", "gate oxide damage", "missing flyback path", "overheated package"),
        "replacement_parts": ("logic-level MOSFET module", "protected load-driver module"),
    },
    {
        "part_id": "usb_pd_power_family",
        "patterns": ("CH224K", "IP2721", "FUSB302", "STUSB4500", "USB-C PD", "TYPE-C"),
        "family": "USB-C/USB-PD power negotiation or Type-C interface",
        "capabilities": ("power", "protection", "connector"),
        "function_id": "power_distribution_or_regulator",
        "key_specs": {"type": "USB-C/PD trigger or controller", "requires": "negotiated voltage and current-limit validation"},
        "verification_required": ("CC/power role", "negotiated voltage", "current limit", "load test", "thermal behavior"),
        "common_faults": ("wrong advertised voltage", "damaged connector", "overheated protection path", "missing e-marker/current limit"),
        "replacement_parts": ("USB-C PD trigger module", "protected USB-C power module"),
    },
    {
        "part_id": "memory_storage_family",
        "patterns": ("W25Q", "W25Q32", "W25Q64", "MX25", "AT24C", "24LC", "EEPROM", "FLASH"),
        "family": "serial flash or EEPROM",
        "capabilities": ("controller", "connector"),
        "function_id": "controller_module",
        "key_specs": {"type": "SPI/I2C nonvolatile memory", "typical_use": "firmware, configuration, calibration, logs"},
        "verification_required": ("voltage domain", "bus pins", "chip-select/address", "read-only dump before writes"),
        "common_faults": ("corrupt firmware/config", "wrong voltage domain", "bus contention", "write-protect issue"),
        "replacement_parts": ("same-family SPI flash", "same-family I2C EEPROM"),
    },
]


def enrich_payload_with_arbitrary_board_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach board-function, diagnostic, protocol, and value workflow records."""

    body = dict(payload or {})
    had_analysis = isinstance(body.get("analysis"), dict)
    analysis = dict(body.get("analysis") if had_analysis else {})
    if not _has_workflow_input(body, analysis):
        if had_analysis:
            body["analysis"] = analysis
        return body

    workflow = build_arbitrary_board_workflow(body, analysis=analysis)
    analysis["arbitrary_board_workflow"] = workflow
    analysis["board_function_inference"] = workflow["board_function_inference"]
    analysis["evidence_contradictions"] = workflow["evidence_contradictions"]
    analysis["measurement_protocol"] = workflow["measurement_protocol"]
    analysis["fault_isolation"] = workflow["fault_isolation"]
    analysis["salvage_value_decision"] = workflow["salvage_value_decision"]
    analysis["part_grounding"] = workflow["part_grounding"]
    analysis["component_salvage_map"] = workflow["component_salvage_map"]
    analysis["layout_reuse_boundaries"] = workflow["layout_reuse_boundaries"]
    analysis["reuse_splice_strategy"] = workflow["reuse_splice_strategy"]
    analysis["arbitrary_board_trust_assessment"] = workflow["arbitrary_board_trust_assessment"]
    analysis["bench_protocol_pack"] = workflow["bench_protocol_pack"]
    analysis["next_evidence_tasks"] = _dedupe_tasks(
        [*(analysis.get("next_evidence_tasks") or []), *workflow["next_evidence_tasks"]]
    )
    body["analysis"] = analysis
    return body


def build_arbitrary_board_workflow(payload: Dict[str, Any], *, analysis: Dict[str, Any] | None = None) -> Dict[str, Any]:
    analysis = analysis if isinstance(analysis, dict) else {}
    facts = _facts(payload, analysis)
    part_grounding = facts["part_grounding"]
    board_function = _board_function_inference(facts)
    contradictions = _evidence_contradictions(facts, board_function)
    protocol = _measurement_protocol(facts, board_function, contradictions)
    bench_protocol = _bench_protocol_pack(facts, board_function)
    fault_isolation = _fault_isolation(facts, board_function, protocol, contradictions)
    value_decision = _salvage_value_decision(facts, board_function, contradictions, fault_isolation)
    component_salvage = _component_salvage_map(facts, board_function, contradictions)
    layout_boundaries = _layout_reuse_boundaries(facts, board_function, component_salvage)
    reuse_splice = _reuse_splice_strategy(facts, board_function, protocol, value_decision, component_salvage)
    trust_assessment = _arbitrary_board_trust_assessment(
        facts,
        board_function,
        contradictions,
        protocol,
        fault_isolation,
        value_decision,
        reuse_splice,
    )
    tasks = _next_evidence_tasks(
        protocol,
        contradictions,
        fault_isolation,
        value_decision,
        reuse_splice,
        part_grounding,
        bench_protocol,
        {}
        if facts.get("has_topology")
        else facts.get("visual_topology_hypothesis")
        if isinstance(facts.get("visual_topology_hypothesis"), dict)
        else {},
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "available": True,
        "board_function_inference": board_function,
        "evidence_contradictions": contradictions,
        "measurement_protocol": protocol,
        "bench_protocol_pack": bench_protocol,
        "fault_isolation": fault_isolation,
        "salvage_value_decision": value_decision,
        "part_grounding": part_grounding,
        "component_salvage_map": component_salvage,
        "layout_reuse_boundaries": layout_boundaries,
        "reuse_splice_strategy": reuse_splice,
        "arbitrary_board_trust_assessment": trust_assessment,
        "next_evidence_tasks": tasks,
        "claim_boundary": (
            "Workflow recommendations are diagnostic and economic guidance; repair authority and production release "
            "still require the authority lanes, trusted measurements, and terminal outcome to pass."
        ),
    }


def _has_workflow_input(payload: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
    return bool(
        payload.get("enable_arbitrary_board_workflow")
        or payload.get("board_evidence")
        or payload.get("topology_evidence")
        or payload.get("topology_evidence_bridge")
        or payload.get("vision_evidence_bridge")
        or payload.get("visual_topology_hypothesis")
        or analysis.get("board_evidence")
        or analysis.get("vision_evidence_bridge")
        or analysis.get("visual_topology_hypothesis")
        or analysis.get("topology_evidence_bridge")
        or (analysis.get("authority_integrity") and (analysis.get("authority_integrity") or {}).get("conflict_detected"))
        or analysis.get("measurement_protocol")
    )


def _facts(payload: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    board_evidence = _first_dict(analysis.get("board_evidence"), payload.get("board_evidence"))
    topology_bridge = _first_dict(analysis.get("topology_evidence_bridge"), payload.get("topology_evidence_bridge"))
    topology_authority = _first_dict(analysis.get("topology_authority"))
    repair_authority = _first_dict(analysis.get("repair_authority"), payload.get("repair_authority"))
    arbitrary_authority = _first_dict(analysis.get("arbitrary_board_authority"))
    derived_repair_authority = _first_dict(arbitrary_authority.get("repair_authority"))
    evidence_trust = _first_dict(analysis.get("evidence_trust"), payload.get("evidence_trust"))
    authority_integrity = _first_dict(analysis.get("authority_integrity"))
    hazard_profile = _first_dict(payload.get("hazard_profile"), analysis.get("hazard_profile"), repair_authority.get("hazard_summary"))
    multiview_reconstruction = _first_dict(analysis.get("multiview_board_reconstruction"), payload.get("multiview_board_reconstruction"))
    capture_coverage = _first_dict(multiview_reconstruction.get("capture_coverage"))
    visual_topology = _first_dict(analysis.get("visual_topology_hypothesis"), payload.get("visual_topology_hypothesis"))
    machine = _first_dict(analysis.get("machine_connection_map"))
    resource_strategy = _first_dict(analysis.get("resource_strategy"))
    splice = _first_dict(machine.get("splice_plan"))
    resources = _list_dicts(payload.get("available_resources"))
    resources.extend(_list_dicts(analysis.get("available_resources")))
    resources.extend(_list_dicts(resource_strategy.get("selected_resources")))
    components = _list_dicts(board_evidence.get("components"))
    connectors = _list_dicts(board_evidence.get("connectors"))
    markings = _list_dicts(board_evidence.get("markings"))
    damage = _list_dicts(board_evidence.get("damage"))
    detections = _list_dicts(analysis.get("detections"))
    part_grounding = _part_grounding(components=components, connectors=connectors, markings=markings, detections=detections)
    measurements = _measurement_rows(payload, analysis)
    outcomes = _outcome_rows(payload, analysis)
    production_release = _first_release_manifest(payload, analysis, outcomes[-1] if outcomes else {})
    required_capabilities = _dedupe(
        [*(payload.get("required_capabilities") or []), *(analysis.get("required_capabilities") or [])]
    )
    capabilities = _dedupe(
        [
            *required_capabilities,
            *[cap for row in resources for cap in (row.get("capabilities") or [])],
            *[cap for row in part_grounding.get("matched_parts") or [] for cap in (row.get("capabilities") or [])],
        ]
    )
    interfaces = _list_dicts(topology_bridge.get("interfaces")) + _list_dicts(machine.get("interfaces"))
    connector_maps = _list_dicts(topology_bridge.get("connector_maps")) + _list_dicts(machine.get("connector_maps"))
    authority_lanes = _list_dicts(repair_authority.get("authority_lanes")) or _list_dicts(
        derived_repair_authority.get("authority_lanes")
    )
    symptoms = _dedupe(
        [
            *(payload.get("symptoms") or []),
            *(analysis.get("symptoms") or []),
            payload.get("goal"),
            payload.get("description"),
            payload.get("device_hint"),
        ]
    )
    text = " ".join(
        str(item)
        for item in [
            *symptoms,
            *required_capabilities,
            *capabilities,
            *[row.get("label") or row.get("kind") for row in components],
            *[row.get("marking") or row.get("visible_text") or row.get("label") for row in markings],
            *[row.get("matched_text") or row.get("canonical_part") or row.get("family") for row in part_grounding.get("matched_parts") or []],
            *[row.get("label") or row.get("kind") for row in connectors],
            *[row.get("label") or row.get("kind") for row in visual_topology.get("connector_hypotheses") or [] if isinstance(row, dict)],
            *[role for row in visual_topology.get("connector_hypotheses") or [] if isinstance(row, dict) for role in (row.get("likely_roles") or [])],
            *[row.get("type") for row in visual_topology.get("connection_hypotheses") or [] if isinstance(row, dict)],
            *[row.get("class_name") or row.get("label") for row in detections],
            *[row.get("type") for row in interfaces],
            *[row.get("notes") for row in damage],
        ]
    ).lower()
    return {
        "payload": payload,
        "analysis": analysis,
        "text": text,
        "board_evidence": board_evidence,
        "topology_bridge": topology_bridge,
        "topology_authority": topology_authority,
        "repair_authority": repair_authority,
        "derived_repair_authority": derived_repair_authority,
        "evidence_trust": evidence_trust,
        "authority_integrity": authority_integrity,
        "hazard_profile": hazard_profile,
        "multiview_board_reconstruction": multiview_reconstruction,
        "capture_coverage": capture_coverage,
        "visual_topology_hypothesis": visual_topology,
        "machine_connection_map": machine,
        "splice_plan": splice,
        "resources": _dedupe_rows(resources, key_fields=("resource_id", "name")),
        "required_capabilities": required_capabilities,
        "capabilities": capabilities,
        "part_grounding": part_grounding,
        "components": components,
        "connectors": connectors,
        "markings": markings,
        "damage": damage,
        "detections": detections,
        "measurements": measurements,
        "outcomes": outcomes,
        "production_release": production_release,
        "interfaces": _dedupe_rows(interfaces, key_fields=("type", "connector_ref", "net")),
        "connector_maps": _dedupe_rows(connector_maps, key_fields=("connector_id", "connector_ref")),
        "authority_lanes": authority_lanes,
        "symptoms": symptoms,
        "has_visual": bool(board_evidence or detections),
        "has_visual_topology": bool(visual_topology.get("available")),
        "has_reference_topology": bool(topology_bridge.get("reference_only") or topology_authority.get("reference_backed")),
        "has_topology": bool(
            (topology_bridge.get("available") and not topology_bridge.get("reference_only"))
            or topology_authority.get("measurement_backed")
        ),
        "pinout_known": bool(topology_authority.get("pinout_known")),
        "authority_status": str(repair_authority.get("status") or "unavailable"),
    }


def _part_grounding(
    *,
    components: Sequence[Dict[str, Any]],
    connectors: Sequence[Dict[str, Any]],
    markings: Sequence[Dict[str, Any]],
    detections: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    observations = _part_observations(components, connectors, markings, detections)
    matches: List[Dict[str, Any]] = []
    for observation in observations:
        compact = _compact_part_text(observation.get("text"))
        if not compact:
            continue
        for spec in KNOWN_PARTS:
            matched_pattern = _matched_part_pattern(compact, spec.get("patterns") or ())
            if not matched_pattern:
                continue
            matches.append(_part_match_record(spec, observation, matched_pattern))
    matches = _dedupe_part_matches(matches)
    function_votes: Dict[str, float] = {}
    for match in matches:
        function_id = str(match.get("function_id") or "")
        if not function_id:
            continue
        function_votes[function_id] = round(function_votes.get(function_id, 0.0) + _safe_float(match.get("confidence"), 0.0), 3)
    ranked = sorted(function_votes.items(), key=lambda item: item[1], reverse=True)
    return {
        "schema_version": "part_grounding.v1",
        "available": bool(matches),
        "source": "visible_marking_and_known_part_catalog",
        "matched_parts": matches[:12],
        "observed_text_count": len(observations),
        "grounded_capabilities": _dedupe(cap for match in matches for cap in (match.get("capabilities") or []))[:16],
        "function_votes": [{"function_id": function_id, "score": score} for function_id, score in ranked[:8]],
        "grounding_tasks": _part_grounding_tasks(matches),
        "claim_boundary": (
            "Part markings and catalog knowledge can ground likely function and tests, but they do not prove wiring, "
            "pinout, board variant, or safe power without measurements."
        ),
    }


def _part_observations(
    components: Sequence[Dict[str, Any]],
    connectors: Sequence[Dict[str, Any]],
    markings: Sequence[Dict[str, Any]],
    detections: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for source, items in [
        ("component", components),
        ("connector", connectors),
        ("marking", markings),
        ("detection", detections),
    ]:
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            text = " ".join(
                str(value or "")
                for value in [
                    item.get("marking"),
                    item.get("visible_text"),
                    item.get("label"),
                    item.get("name"),
                    item.get("kind"),
                    item.get("class_name"),
                    item.get("notes"),
                ]
            ).strip()
            if not text:
                continue
            rows.append(
                {
                    "source": source,
                    "source_ref": str(item.get("id") or item.get("ref") or item.get("label") or f"{source}_{index}"),
                    "text": text,
                    "confidence": _safe_float(item.get("confidence"), 0.62),
                }
            )
    return rows


def _part_match_record(spec: Dict[str, Any], observation: Dict[str, Any], matched_pattern: str) -> Dict[str, Any]:
    confidence = min(0.94, max(0.45, _safe_float(observation.get("confidence"), 0.62)) + (0.14 if observation.get("source") == "marking" else 0.08))
    return {
        "part_id": spec.get("part_id"),
        "canonical_part": matched_pattern,
        "family": spec.get("family"),
        "function_id": spec.get("function_id"),
        "capabilities": list(spec.get("capabilities") or []),
        "confidence": round(confidence, 3),
        "matched_text": observation.get("text"),
        "source": observation.get("source"),
        "source_ref": observation.get("source_ref"),
        "key_specs": spec.get("key_specs") or {},
        "verification_required": list(spec.get("verification_required") or []),
        "common_faults": list(spec.get("common_faults") or []),
        "replacement_parts": list(spec.get("replacement_parts") or []),
    }


def _matched_part_pattern(compact_text: str, patterns: Sequence[Any]) -> str:
    for pattern in patterns:
        compact_pattern = _compact_part_text(pattern)
        if compact_pattern and compact_pattern in compact_text:
            return str(pattern)
    return ""


def _compact_part_text(value: Any) -> str:
    return "".join(ch.upper() for ch in str(value or "") if ch.isalnum())


def _dedupe_part_matches(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = (
            str(row.get("part_id") or ""),
            str(row.get("canonical_part") or ""),
            _compact_part_text(row.get("matched_text")),
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    kept.sort(key=lambda item: (_safe_float(item.get("confidence"), 0.0), str(item.get("part_id") or "")), reverse=True)
    return kept


def _part_grounding_tasks(matches: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for match in matches[:6]:
        part = str(match.get("canonical_part") or match.get("family") or "matched part")
        specs = match.get("key_specs") if isinstance(match.get("key_specs"), dict) else {}
        tasks.append(
            {
                "task_id": f"ground_{_safe_id(part)}",
                "type": "review",
                "status": "open",
                "priority": 2,
                "prompt": f"Verify {part} marking, package/pinout, and board variant before relying on catalog specs: {', '.join(str(key) for key in specs.keys())}.",
                "source": "part_grounding",
                "usable_for": ["repair", "reuse", "datasheet_grounding", "training"],
            }
        )
    return _dedupe_tasks(tasks)[:8]


def _board_function_inference(facts: Dict[str, Any]) -> Dict[str, Any]:
    candidates = []
    text = str(facts.get("text") or "")
    caps = {str(cap).lower() for cap in facts.get("capabilities") or []}
    interfaces = {str(row.get("type") or "").lower() for row in facts.get("interfaces") or []}
    grounded_matches = [
        row for row in (facts.get("part_grounding") or {}).get("matched_parts") or []
        if isinstance(row, dict)
    ]
    grounded_by_function: Dict[str, List[Dict[str, Any]]] = {}
    for match in grounded_matches:
        grounded_by_function.setdefault(str(match.get("function_id") or ""), []).append(match)

    def add(function_id: str, label: str, base: float, evidence: Sequence[str], capabilities: Sequence[str]) -> None:
        grounded = grounded_by_function.get(function_id) or []
        grounding_evidence = [
            f"grounded marking: {row.get('canonical_part')} ({row.get('family')})"
            for row in grounded[:4]
        ]
        score = base + 0.08 * len(evidence) + 0.11 * len(grounded)
        if set(capabilities) & caps:
            score += 0.12
        candidates.append(
            {
                "function_id": function_id,
                "label": label,
                "confidence": round(min(score, 0.96), 3),
                "evidence": _dedupe([*evidence, *grounding_evidence])[:8],
                "capabilities": _dedupe(capabilities),
                "confirmation_required": _confirmation_required(function_id),
                "grounded_part_ids": _dedupe(row.get("part_id") for row in grounded)[:6],
            }
        )

    if (
        {"controller", "network_interface", "display_or_ui"} <= caps
        or _has_any(text, ["raspberry pi", "single board computer", "sbc", "bcm2711", "bcm2837"])
        or (_has_any(text, ["cpu", "processor", "soc", "ram"]) and _has_any(text, ["gpio", "ethernet", "hdmi"]))
    ):
        add(
            "single_board_computer_module",
            "Single-board embedded compute module",
            0.36,
            _hits(text, ["raspberry pi", "single board computer", "sbc", "bcm2711", "bcm2837", "cpu", "processor", "soc", "ram", "gpio", "ethernet", "hdmi"]),
            ["controller", "network_interface", "display_or_ui", "connector", "power"],
        )
    if {"usb_serial", "uart_serial", "usb2"} & (caps | interfaces) or _has_any(text, ["ch340", "cp210", "ft232", "uart", "serial", "usb"]):
        add(
            "usb_serial_debug_bridge",
            "USB/UART debug or bridge module",
            0.34,
            _hits(text, ["usb", "uart", "serial", "ch340", "cp210", "ft232"]) + _interface_hits(interfaces, ["uart_serial", "usb2"]),
            ["usb_serial", "connector"],
        )
    if {"sensor_or_adc", "i2c"} & (caps | interfaces) or _has_any(text, ["sensor", "bme", "bmp", "sht", "i2c", "spi"]):
        add(
            "sensor_or_adc_module",
            "Sensor or ADC module",
            0.3,
            _hits(text, ["sensor", "adc", "i2c", "spi", "bme", "bmp", "sht"]) + _interface_hits(interfaces, ["i2c"]),
            ["sensor_or_adc", "connector"],
        )
    if {"actuator_driver", "motor_or_load", "motor_or_servo"} & caps or _has_any(text, ["motor", "load", "driver", "relay", "mosfet", "actuator"]):
        add(
            "load_or_motor_driver",
            "Load, relay, or motor driver board",
            0.32,
            _hits(text, ["motor", "load", "driver", "relay", "mosfet", "actuator"]),
            ["actuator_driver", "motor_or_load", "power"],
        )
    if "power" in caps or _has_any(text, ["power", "regulator", "buck", "boost", "ldo", "5v", "3v3"]):
        add(
            "power_distribution_or_regulator",
            "Power distribution or regulator stage",
            0.28,
            _hits(text, ["power", "regulator", "buck", "boost", "ldo", "5v", "3v3"]),
            ["power"],
        )
    if "controller" in caps or _has_any(text, ["mcu", "microcontroller", "esp32", "arduino", "controller", "boot"]):
        add(
            "controller_module",
            "Controller or embedded compute module",
            0.28,
            _hits(text, ["mcu", "microcontroller", "esp32", "arduino", "controller", "boot"]),
            ["controller", "connector"],
        )
    if "battery" in caps or _has_any(text, ["battery", "charger", "bms", "lipo", "li-ion"]):
        add(
            "battery_or_charger",
            "Battery, BMS, or charging path",
            0.26,
            _hits(text, ["battery", "charger", "bms", "lipo", "li-ion"]),
            ["battery", "power"],
        )
    if {"wireless", "network_interface"} & caps or _has_any(text, ["antenna", "wifi", "ble", "bluetooth", "rf", "lora", "zigbee"]):
        add(
            "wireless_or_rf_module",
            "Wireless, RF, or network module",
            0.27,
            _hits(text, ["antenna", "wifi", "ble", "bluetooth", "rf", "lora", "zigbee"]),
            ["wireless", "network_interface", "connector"],
        )
    if {"display_or_ui", "led_or_light", "switch_or_button"} & caps or _has_any(text, ["display", "oled", "lcd", "led", "button", "switch", "keypad"]):
        add(
            "display_or_ui_module",
            "Display, indicator, or user-interface board",
            0.26,
            _hits(text, ["display", "oled", "lcd", "led", "button", "switch", "keypad"]),
            ["display_or_ui", "led_or_light", "switch_or_button", "connector"],
        )
    if {"speaker_or_audio", "audio"} & caps or _has_any(text, ["audio", "speaker", "amplifier", "amp", "buzzer", "microphone"]):
        add(
            "audio_or_alert_module",
            "Audio, buzzer, microphone, or alert board",
            0.25,
            _hits(text, ["audio", "speaker", "amplifier", "amp", "buzzer", "microphone"]),
            ["speaker_or_audio", "connector"],
        )
    if not candidates:
        add(
            "unknown_low_voltage_module",
            "Unknown low-voltage electronic module",
            0.22,
            ["insufficient board function evidence"],
            ["connector"],
        )

    candidates.sort(key=lambda row: row.get("confidence", 0), reverse=True)
    primary = candidates[0]
    return {
        "schema_version": "board_function_inference.v1",
        "primary_function_id": primary["function_id"],
        "primary_label": primary["label"],
        "confidence": primary["confidence"],
        "candidates": candidates[:6],
        "source_policy": {
            "vision_is_candidate_only": True,
            "topology_and_measurements_raise_confidence": True,
            "function_inference_does_not_authorize_power": True,
        },
    }


def _evidence_contradictions(facts: Dict[str, Any], board_function: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    authority_status = facts.get("authority_status")
    if (facts.get("authority_integrity") or {}).get("conflict_detected"):
        rows.append(
            _contradiction(
                "authority_conflict",
                "hard",
                "Supplied repair authority conflicts with measured evidence.",
                (facts.get("authority_integrity") or {}).get("hard_blockers") or [],
                "Keep safety hold until the hard blockers are cleared by new measurements.",
            )
        )
    if facts.get("has_visual") and not facts.get("has_topology"):
        rows.append(
            _contradiction(
                "vision_without_topology",
                "soft",
                "Visual board candidates exist without measured topology.",
                ["Vision evidence can propose components and connectors but cannot prove pinout."],
                "Capture measured connector pinout, no-short, ground, and voltage evidence.",
            )
        )
    if authority_status == "authoritative_low_risk" and not facts.get("pinout_known"):
        rows.append(
            _contradiction(
                "authority_without_pinout",
                "hard",
                "Authority claims low-risk status but measured pinout is not complete.",
                ["pinout_known=false"],
                "Attach measured topology or downgrade authority.",
            )
        )
    if authority_status == "blocked":
        blockers = (facts.get("evidence_trust") or {}).get("blockers") or []
        rows.append(
            _contradiction(
                "authority_blocked",
                "hard",
                "Repair authority is blocked by evidence.",
                blockers[:6],
                "Use only safety triage and evidence collection until blockers clear.",
            )
        )
    primary = str(board_function.get("primary_function_id") or "")
    interface_types = {str(row.get("type") or "") for row in facts.get("interfaces") or []}
    if primary == "usb_serial_debug_bridge" and facts.get("has_topology") and not (interface_types & {"uart_serial", "usb2"}):
        rows.append(
            _contradiction(
                "usb_claim_without_data_interface",
                "soft",
                "USB/UART function is likely, but measured topology does not expose a serial or USB interface yet.",
                sorted(interface_types),
                "Measure candidate data pins and logic levels before using as a debug bridge.",
            )
        )
    hard = [row for row in rows if row["severity"] == "hard"]
    soft = [row for row in rows if row["severity"] == "soft"]
    return {
        "schema_version": "evidence_contradictions.v1",
        "status": "hard_conflict" if hard else "soft_gaps" if soft else "clear",
        "hard_count": len(hard),
        "soft_count": len(soft),
        "items": rows[:12],
    }


def _measurement_protocol(
    facts: Dict[str, Any],
    board_function: Dict[str, Any],
    contradictions: Dict[str, Any],
) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    lanes = {str(row.get("lane_id")): row for row in facts.get("authority_lanes") or []}
    authority_for_protocol = facts.get("repair_authority") or {}
    if not (authority_for_protocol.get("unlock_plan") or []):
        authority_for_protocol = facts.get("derived_repair_authority") or authority_for_protocol
    for step in authority_for_protocol.get("unlock_plan") or []:
        if not isinstance(step, dict):
            continue
        lane = lanes.get(str(step.get("lane_id"))) or {}
        steps.append(
            _protocol_step(
                lane_id=str(step.get("lane_id") or "authority"),
                category=_category_for_lane(step.get("lane_id")),
                action=str(step.get("action") or step.get("reason") or ""),
                expected_result=_expected_for_lane(step.get("lane_id")),
                fail_branch=str(step.get("reason") or "Keep authority gated."),
                status=_lane_to_status(lane.get("status")),
                source="authority_unlock_plan",
                required_before=str(step.get("unlocks") or "repair_power_release"),
            )
        )
    for contradiction in contradictions.get("items") or []:
        if not isinstance(contradiction, dict) or contradiction.get("severity") != "hard":
            continue
        steps.append(
            _protocol_step(
                lane_id=f"contradiction_{contradiction.get('id')}",
                category="review",
                action=str(contradiction.get("resolution") or "Resolve hard evidence contradiction."),
                expected_result="Contradiction is cleared by structured evidence.",
                fail_branch="Keep safety hold.",
                status="blocked",
                source="evidence_contradictions",
                required_before="repair_power_release",
            )
        )
    primary = str(board_function.get("primary_function_id") or "")
    steps.extend(_function_protocol_steps(primary, lanes))
    steps.extend(_visual_topology_protocol_steps(facts))
    steps = _dedupe_protocol_steps(steps)
    for index, step in enumerate(steps, start=1):
        step["step_id"] = f"protocol_{index}"
        step["sequence"] = index
    open_steps = [step for step in steps if step.get("status") in {"open", "blocked"}]
    return {
        "schema_version": "measurement_protocol.v1",
        "status": "blocked" if any(step.get("status") == "blocked" for step in steps) else "open" if open_steps else "passed",
        "primary_function_id": primary,
        "step_count": len(steps),
        "open_step_count": len(open_steps),
        "steps": steps[:24],
    }


def _bench_protocol_pack(facts: Dict[str, Any], board_function: Dict[str, Any]) -> Dict[str, Any]:
    return build_bench_protocol_pack(
        primary_function_id=str(board_function.get("primary_function_id") or "unknown_low_voltage_module"),
        capabilities=facts.get("capabilities") or [],
        matched_parts=(facts.get("part_grounding") or {}).get("matched_parts") or [],
        authority_status=str(facts.get("authority_status") or "unavailable"),
    )


def _function_protocol_steps(primary: str, lanes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = [
        _protocol_step(
            lane_id="no_short",
            category="resistance",
            action="Measure unpowered resistance between every power rail and ground.",
            expected_result="No rail reads as a dead short unless the design explicitly expects it.",
            fail_branch="Stop; isolate the shorted rail before power.",
            status=_lane_to_status((lanes.get("no_short") or {}).get("status")),
            source="function_protocol",
            required_before="first_power",
        ),
        _protocol_step(
            lane_id="voltage_domain",
            category="voltage",
            action="Power through a current limit and record input voltage, rail voltage, and polarity.",
            expected_result="Rails match the measured or expected low-voltage domain.",
            fail_branch="Stop; inspect regulator/input protection path.",
            status=_lane_to_status((lanes.get("voltage_domain") or {}).get("status")),
            source="function_protocol",
            required_before="splice_release",
        ),
        _protocol_step(
            lane_id="thermal_behavior",
            category="thermal",
            action="Record thermal behavior during first-power and function test.",
            expected_result="No abnormal hot spot, smoke, odor, or thermal runaway.",
            fail_branch="Stop; isolate load, regulator, or shorted component.",
            status=_lane_to_status((lanes.get("thermal_behavior") or {}).get("status")),
            source="function_protocol",
            required_before="demo_or_release",
        ),
    ]
    if primary == "usb_serial_debug_bridge":
        rows.append(
            _protocol_step(
                lane_id="logic_interface",
                category="logic",
                action="Measure UART/USB logic level, share ground, and run loopback or safe serial capture before target connection.",
                expected_result="Logic level is compatible and serial activity is stable.",
                fail_branch="Do not connect target; isolate bridge, connector, or boot path.",
                status=_lane_to_status((lanes.get("logic_interface") or {}).get("status")),
                source="function_protocol",
                required_before="external_target_connection",
            )
        )
    elif primary == "sensor_or_adc_module":
        rows.append(
            _protocol_step(
                lane_id="logic_interface",
                category="logic",
                action="Verify I2C/SPI pullups, voltage domain, and low-speed bus scan with current limit.",
                expected_result="Bus responds without excessive current or stuck lines.",
                fail_branch="Check pullups, address conflicts, and damaged sensor front-end.",
                status=_lane_to_status((lanes.get("logic_interface") or {}).get("status")),
                source="function_protocol",
                required_before="reuse_as_sensor",
            )
        )
    elif primary == "load_or_motor_driver":
        rows.append(
            _protocol_step(
                lane_id="load_path",
                category="load",
                action="Test driver output with dummy load, fuse/current limit, and thermal observation before real load.",
                expected_result="Output switches correctly, current stays within limit, protection is present.",
                fail_branch="Do not attach real load; isolate driver, flyback, or load fault.",
                status=_lane_to_status((lanes.get("load_path") or {}).get("status")),
                source="function_protocol",
                required_before="real_load_connection",
            )
        )
    elif primary == "power_distribution_or_regulator":
        rows.extend(
            [
                _protocol_step(
                    lane_id="regulator_output",
                    category="voltage",
                    action="Measure regulator/input stage output voltage, polarity, ripple symptom, and dropout behavior under a small dummy load.",
                    expected_result="Output voltage is stable, correctly polarized, and within expected low-voltage tolerance.",
                    fail_branch="Do not reuse the rail; isolate input protection, regulator, feedback, or load-side short.",
                    status=_lane_to_status((lanes.get("regulator_output") or {}).get("status")),
                    source="function_protocol",
                    required_before="power_stage_reuse",
                ),
                _protocol_step(
                    lane_id="protected_load_test",
                    category="load",
                    action="Load-test the power stage with a current-limited dummy load before powering another board.",
                    expected_result="Voltage stays in range and current/thermal behavior remains stable.",
                    fail_branch="Retire the power stage or repair before downstream connection.",
                    status=_lane_to_status((lanes.get("protected_load_test") or {}).get("status")),
                    source="function_protocol",
                    required_before="downstream_power_connection",
                ),
            ]
        )
    elif primary == "controller_module":
        rows.append(
            _protocol_step(
                lane_id="boot_and_io",
                category="logic",
                action="Verify power rails, boot/current behavior, reset state, and safe I/O voltage before using controller pins.",
                expected_result="Controller boots or idles predictably and I/O voltage matches the target interface.",
                fail_branch="Do not connect external targets; isolate firmware state, boot mode, regulator, or damaged I/O.",
                status=_lane_to_status((lanes.get("boot_and_io") or {}).get("status")),
                source="function_protocol",
                required_before="controller_io_connection",
            )
        )
    elif primary == "battery_or_charger":
        rows.append(
            _protocol_step(
                lane_id="battery_specialist_review",
                category="safety",
                action="Verify chemistry, cell count, BMS/protection, enclosure, charge path, and thermal containment before any reuse.",
                expected_result="Battery-specific authority is explicitly recorded by a qualified workflow.",
                fail_branch="Do not charge, load, puncture, or reuse; safe disposal or specialist handling only.",
                status=_lane_to_status((lanes.get("battery_specialist_review") or {}).get("status")),
                source="function_protocol",
                required_before="specialist_authority",
            )
        )
    elif primary == "wireless_or_rf_module":
        rows.append(
            _protocol_step(
                lane_id="rf_module_bringup",
                category="logic",
                action="Verify supply current, antenna connection, interface voltage, and a low-power communication scan before integration.",
                expected_result="Module communicates or advertises without overcurrent or abnormal heat.",
                fail_branch="Do not integrate RF module; isolate antenna, firmware, regulator, or interface fault.",
                status=_lane_to_status((lanes.get("rf_module_bringup") or {}).get("status")),
                source="function_protocol",
                required_before="network_or_rf_integration",
            )
        )
    elif primary == "display_or_ui_module":
        rows.append(
            _protocol_step(
                lane_id="ui_signal_map",
                category="logic",
                action="Map button/display/LED pins, verify current limiting, and drive the UI through a protected test harness.",
                expected_result="Inputs/outputs respond predictably without overcurrent or stuck lines.",
                fail_branch="Do not connect to a controller until signal map and current limits are corrected.",
                status=_lane_to_status((lanes.get("ui_signal_map") or {}).get("status")),
                source="function_protocol",
                required_before="ui_harness_connection",
            )
        )
    elif primary == "audio_or_alert_module":
        rows.append(
            _protocol_step(
                lane_id="audio_path_test",
                category="load",
                action="Verify speaker/load impedance, amplifier supply voltage, idle current, and low-level audio/alert output first.",
                expected_result="Audio path responds at low level without overcurrent, clipping into a short, or abnormal heat.",
                fail_branch="Do not connect final speaker/load; isolate amplifier, connector, or protection path.",
                status=_lane_to_status((lanes.get("audio_path_test") or {}).get("status")),
                source="function_protocol",
                required_before="audio_load_connection",
            )
        )
    return rows


def _visual_topology_protocol_steps(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    hypothesis = facts.get("visual_topology_hypothesis") if isinstance(facts.get("visual_topology_hypothesis"), dict) else {}
    if not hypothesis.get("available") or facts.get("has_topology"):
        return []
    rows: List[Dict[str, Any]] = []
    for task in hypothesis.get("measurement_queue") or []:
        if not isinstance(task, dict):
            continue
        category = str(task.get("category") or task.get("type") or "measurement")
        if category in {"layout", "capture"}:
            continue
        prompt = str(task.get("prompt") or "")
        if not prompt:
            continue
        rows.append(
            _protocol_step(
                lane_id=f"visual_topology_{_safe_id(task.get('task_id') or category)}",
                category=category,
                action=prompt,
                expected_result="Measured topology_evidence.v1 row is attached, or a negative result is recorded explicitly.",
                fail_branch="Keep the candidate visual topology outside the splice/power trust boundary.",
                status="open",
                source="visual_topology_hypothesis",
                required_before=_visual_topology_required_before(category),
            )
        )
    return rows[:12]


def _visual_topology_required_before(category: str) -> str:
    if category in {"pinout", "logic", "continuity"}:
        return "external_target_connection"
    if category in {"voltage", "resistance"}:
        return "first_power"
    if category in {"current", "thermal", "load"}:
        return "demo_or_release"
    return "splice_release"


def _fault_isolation(
    facts: Dict[str, Any],
    board_function: Dict[str, Any],
    protocol: Dict[str, Any],
    contradictions: Dict[str, Any],
) -> Dict[str, Any]:
    candidates = []
    primary = str(board_function.get("primary_function_id") or "")
    text = str(facts.get("text") or "")
    if facts.get("authority_status") == "blocked" or contradictions.get("hard_count"):
        candidates.append(
            _fault_candidate(
                "safety_or_short_blocker",
                "Safety blocker, failed no-short, or hazardous section",
                0.92,
                ["authority is blocked", "hard contradiction present"],
                ["Resolve hard blockers before normal diagnostics."],
            )
        )
    if _has_any(text, ["no power", "won't turn on", "will not turn on", "dead", "not charging"]) or primary in {
        "power_distribution_or_regulator",
        "battery_or_charger",
    }:
        candidates.append(
            _fault_candidate(
                "input_or_regulator_path_fault",
                "Input protection, shorted rail, or regulator fault",
                0.66,
                _hits(text, ["no power", "dead", "not charging", "regulator", "power"]),
                ["Run no-short, input voltage, regulator output, current-limit, and thermal steps."],
            )
        )
    if primary == "usb_serial_debug_bridge" or _has_any(text, ["usb", "serial", "uart", "upload", "recognized"]):
        candidates.append(
            _fault_candidate(
                "usb_serial_or_connector_fault",
                "USB/serial bridge, connector, boot, or logic-level fault",
                0.64,
                _hits(text, ["usb", "serial", "uart", "upload", "recognized"]),
                ["Run logic-level, shared-ground, loopback, and safe serial-capture steps."],
            )
        )
    if primary == "load_or_motor_driver" or _has_any(text, ["motor", "load", "relay", "driver", "actuator"]):
        candidates.append(
            _fault_candidate(
                "driver_or_load_path_fault",
                "Driver stage, protection, or load path fault",
                0.62,
                _hits(text, ["motor", "load", "relay", "driver", "actuator"]),
                ["Run dummy-load, current, flyback/protection, and thermal steps."],
            )
        )
    if primary == "sensor_or_adc_module" or _has_any(text, ["sensor", "reading", "i2c", "spi"]):
        candidates.append(
            _fault_candidate(
                "sensor_bus_or_frontend_fault",
                "Sensor front-end, bus, pullup, or connector fault",
                0.58,
                _hits(text, ["sensor", "reading", "i2c", "spi"]),
                ["Verify supply, pullups, bus idle, low-speed scan, and connector continuity."],
            )
        )
    if primary == "wireless_or_rf_module" or _has_any(text, ["wifi", "ble", "bluetooth", "rf", "lora", "antenna"]):
        candidates.append(
            _fault_candidate(
                "rf_power_interface_or_antenna_fault",
                "RF module supply, host interface, firmware, or antenna fault",
                0.56,
                _hits(text, ["wifi", "ble", "bluetooth", "rf", "lora", "antenna"]),
                ["Verify supply current, host interface voltage, antenna path, and low-power scan/advertisement."],
            )
        )
    if primary == "display_or_ui_module" or _has_any(text, ["display", "oled", "lcd", "led", "button", "switch"]):
        candidates.append(
            _fault_candidate(
                "ui_pinmap_or_current_limit_fault",
                "Display/UI pin map, current limit, or connector fault",
                0.54,
                _hits(text, ["display", "oled", "lcd", "led", "button", "switch"]),
                ["Map pins, verify current limits, and test through protected controller I/O."],
            )
        )
    if primary == "audio_or_alert_module" or _has_any(text, ["audio", "speaker", "amp", "buzzer", "microphone"]):
        candidates.append(
            _fault_candidate(
                "audio_load_or_amplifier_fault",
                "Audio load, amplifier, connector, or protection fault",
                0.52,
                _hits(text, ["audio", "speaker", "amp", "buzzer", "microphone"]),
                ["Verify load impedance, idle current, low-level output, and thermal behavior."],
            )
        )
    if not candidates:
        candidates.append(
            _fault_candidate(
                "unknown_board_fault",
                "Unknown board fault requiring baseline measurements",
                0.34,
                ["no strong symptom or function evidence"],
                ["Run baseline no-short, ground, voltage, current, and thermal protocol."],
            )
        )
    candidates.sort(key=lambda row: row.get("likelihood", 0), reverse=True)
    return {
        "schema_version": "fault_isolation.v1",
        "state": (
            "blocked_safety_hold"
            if facts.get("authority_status") == "blocked" or contradictions.get("hard_count")
            else "diagnostic_ready"
            if facts.get("authority_status") in {"measurement_backed", "authoritative_low_risk"}
            else "needs_measurements"
        ),
        "top_fault_id": candidates[0]["fault_id"],
        "candidates": candidates[:6],
        "protocol_step_ids": [step.get("step_id") for step in protocol.get("steps") or []][:12],
    }


def _salvage_value_decision(
    facts: Dict[str, Any],
    board_function: Dict[str, Any],
    contradictions: Dict[str, Any],
    fault_isolation: Dict[str, Any],
) -> Dict[str, Any]:
    authority = str(facts.get("authority_status") or "unavailable")
    primary = str(board_function.get("primary_function_id") or "unknown")
    hard = int(contradictions.get("hard_count") or 0)
    if authority == "blocked" or hard:
        decision = "safety_hold_or_salvage_only"
        confidence = 0.9
        rationale = "Hard blockers exist; do not repair, reuse, or splice until isolated."
    elif authority == "authoritative_low_risk":
        decision = "controlled_reuse_or_repair_trial"
        confidence = 0.82
        rationale = "Measured authority lanes permit low-risk controlled use in the measured scope."
    elif authority == "measurement_backed":
        decision = "finish_measurements_then_reuse_or_repair"
        confidence = 0.68
        rationale = "Some measurements exist, but remaining authority lanes still gate use."
    elif authority == "visual_only":
        decision = "identify_and_measure_before_value_decision"
        confidence = 0.54
        rationale = "Visual evidence can identify candidates, but value depends on measured function."
    else:
        decision = "collect_baseline_evidence"
        confidence = 0.42
        rationale = "Insufficient evidence for value posture."
    recoverable = _recoverable_value(primary, authority)
    cost = _estimated_cost(authority, hard)
    return {
        "schema_version": "salvage_value_decision.v1",
        "decision": decision,
        "confidence": confidence,
        "primary_function_id": primary,
        "expected_recoverable_value_usd": recoverable,
        "estimated_cash_to_continue_usd": cost,
        "estimated_time_minutes": _estimated_time(authority, primary, hard),
        "value_ratio": round(recoverable / max(cost, 1.0), 2),
        "rationale": rationale,
        "recommended_exit": _recommended_exit(decision, fault_isolation),
        "claim_boundary": "Economic estimate is heuristic until a successful function outcome is recorded.",
    }


def _component_salvage_map(
    facts: Dict[str, Any],
    board_function: Dict[str, Any],
    contradictions: Dict[str, Any],
) -> Dict[str, Any]:
    primary = str(board_function.get("primary_function_id") or "unknown")
    hard_hold = bool(contradictions.get("hard_count") or facts.get("authority_status") == "blocked")
    rows: List[Dict[str, Any]] = []
    for item in [*(facts.get("components") or []), *(facts.get("connectors") or [])]:
        if not isinstance(item, dict):
            continue
        salvage = _salvage_item(item, primary, hard_hold)
        if salvage:
            rows.append(salvage)
    for match in (facts.get("part_grounding") or {}).get("matched_parts") or []:
        if isinstance(match, dict):
            rows.append(_grounded_part_salvage_item(match, hard_hold))
    if not rows:
        rows.append(_function_default_salvage_item(primary, hard_hold))
    rows = _dedupe_salvage_items(rows)
    blocked = [row for row in rows if row.get("status") in {"safety_hold", "specialist_only"}]
    preferred = [row for row in rows if row.get("status") in {"prefer_whole_board_reuse", "candidate_after_measurements", "ready_after_protocol"}]
    return {
        "schema_version": "component_salvage_map.v1",
        "primary_function_id": primary,
        "salvage_posture": "safety_hold" if hard_hold else "map_then_reuse_or_harvest",
        "preferred_reuse_class": _preferred_reuse_class(primary, hard_hold),
        "salvage_items": rows[:16],
        "preferred_item_count": len(preferred),
        "blocked_item_count": len(blocked),
        "safe_harvest_policy": {
            "prefer_whole_board_reuse": primary not in {"battery_or_charger", "unknown_low_voltage_module"},
            "cutting_requires_layout_confirmation": True,
            "desoldering_requires_depowered_no_energy_state": True,
            "battery_or_mains_sections_require_specialist_handling": True,
        },
    }


def _layout_reuse_boundaries(
    facts: Dict[str, Any],
    board_function: Dict[str, Any],
    component_salvage: Dict[str, Any],
) -> Dict[str, Any]:
    board = facts.get("board_evidence") if isinstance(facts.get("board_evidence"), dict) else {}
    primary = str(board_function.get("primary_function_id") or "unknown_low_voltage_module")
    multiview = _has_multiview_visuals(board)
    geometry_items = _layout_geometry_items(facts)
    connector_entries = _layout_connector_entries(facts)
    no_cut_zones = _layout_no_cut_zones(facts, primary)
    visual_topology = facts.get("visual_topology_hypothesis") if isinstance(facts.get("visual_topology_hypothesis"), dict) else {}
    has_geometry = bool(geometry_items)
    topology_known = bool(facts.get("has_topology") and facts.get("pinout_known"))
    confidence = 0.0
    if facts.get("has_visual"):
        confidence += 0.18
    if multiview:
        confidence += 0.24
    if has_geometry:
        confidence += min(0.28, 0.07 * len(geometry_items))
    if connector_entries:
        confidence += min(0.16, 0.04 * len(connector_entries))
    if visual_topology.get("available"):
        confidence += min(0.08, 0.03 + 0.01 * len(visual_topology.get("connection_hypotheses") or []))
    if topology_known:
        confidence += 0.18
    hard_hold = component_salvage.get("salvage_posture") == "safety_hold"
    section_salvage_allowed = bool(confidence >= 0.74 and topology_known and not hard_hold and not no_cut_zones)
    missing = []
    if not facts.get("has_visual"):
        missing.append("Attach front-side board photo with connector/component references.")
    if not multiview:
        missing.append("Attach additional angle/side/closeup photos before any section salvage or trace-cut claim.")
    if not has_geometry:
        missing.append("Attach component/connector geometry or annotated regions for layout-aware salvage.")
    if not topology_known:
        missing.append("Attach measured pinout/topology before section salvage or external splice.")
    if no_cut_zones:
        missing.append("Keep no-cut zones isolated or prove a specialist-safe boundary before cutting/desoldering.")
    return {
        "schema_version": "layout_reuse_boundaries.v1",
        "primary_function_id": primary,
        "layout_confidence": round(_clamp(confidence), 3),
        "multiview_evidence": multiview,
        "geometry_item_count": len(geometry_items),
        "connector_entry_points": connector_entries[:12],
        "visual_topology_hypothesis_count": len(visual_topology.get("connection_hypotheses") or []),
        "no_cut_zones": no_cut_zones[:12],
        "section_salvage_allowed": section_salvage_allowed,
        "whole_board_reuse_preferred": not section_salvage_allowed,
        "allowed_layout_actions": _layout_allowed_actions(section_salvage_allowed, connector_entries),
        "prohibited_layout_actions": _layout_prohibited_actions(section_salvage_allowed, no_cut_zones),
        "missing_layout_evidence": _dedupe(missing)[:10],
        "claim_boundary": (
            "Layout boundaries are conservative. Without front/back geometry and measured topology, the engine may recommend "
            "whole-board or connector reuse, but not board-section cutting or hidden-trace salvage."
        ),
    }


def _layout_geometry_items(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for source, items in [
        ("component", facts.get("components") or []),
        ("connector", facts.get("connectors") or []),
        ("damage", facts.get("damage") or []),
    ]:
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            geometry = _first_dict(item.get("bbox"), item.get("bounding_box"), item.get("polygon"), item.get("region"))
            if not geometry and not item.get("side") and not item.get("location"):
                continue
            rows.append(
                {
                    "item_id": str(item.get("id") or item.get("ref") or f"{source}_{index}"),
                    "source": source,
                    "label": item.get("label") or item.get("kind") or item.get("notes"),
                    "side": item.get("side") or item.get("view"),
                    "geometry": geometry or item.get("location"),
                }
            )
    return rows


def _layout_connector_entries(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for connector in facts.get("connectors") or []:
        if not isinstance(connector, dict):
            continue
        rows.append(
            {
                "entry_id": _safe_id(str(connector.get("id") or connector.get("ref") or connector.get("label") or "connector")),
                "connector_ref": connector.get("id") or connector.get("ref") or connector.get("label"),
                "label": connector.get("label") or connector.get("kind"),
                "confidence": _safe_float(connector.get("confidence"), 0.55),
                "layout_status": "measured_entry" if facts.get("pinout_known") else "visual_entry_candidate",
                "required_before_use": ["measured pinout", "ground reference", "voltage/current domain"],
            }
        )
    for port in _splice_ports(facts):
        rows.append(
            {
                "entry_id": str(port.get("port_id") or _safe_id(port.get("connector_ref"))),
                "connector_ref": port.get("connector_ref"),
                "label": port.get("interface_type"),
                "confidence": port.get("confidence"),
                "layout_status": "measured_entry" if facts.get("pinout_known") else "candidate_entry",
                "required_before_use": port.get("required_verifications") or [],
            }
        )
    return _dedupe_rows(rows, key_fields=("entry_id",))


def _layout_no_cut_zones(facts: Dict[str, Any], primary: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for source, items in [
        ("component", facts.get("components") or []),
        ("connector", facts.get("connectors") or []),
        ("damage", facts.get("damage") or []),
        ("marking", facts.get("markings") or []),
    ]:
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            text = " ".join(
                str(value or "")
                for value in [
                    item.get("label"),
                    item.get("kind"),
                    item.get("type"),
                    item.get("marking"),
                    item.get("notes"),
                ]
            ).lower()
            reason = ""
            if _has_any(text, ["battery", "lipo", "li-ion", "bms", "cell"]):
                reason = "battery_or_energy_storage"
            elif _has_any(text, ["mains", "ac input", "high voltage", "hv", "transformer", "crt", "capacitor bank"]):
                reason = "mains_or_high_voltage"
            elif source == "damage":
                reason = "visible_damage_boundary"
            elif primary in {"power_distribution_or_regulator", "load_or_motor_driver"} and _has_any(text, ["inductor", "diode", "mosfet", "relay", "driver", "regulator"]):
                reason = "power_or_load_path_integrity"
            if reason:
                rows.append(
                    {
                        "zone_id": _safe_id(str(item.get("id") or item.get("ref") or f"{source}_{index}")),
                        "source": source,
                        "label": item.get("label") or item.get("marking") or item.get("kind"),
                        "reason": reason,
                        "required_clearance": "specialist review" if reason in {"battery_or_energy_storage", "mains_or_high_voltage"} else "layout and topology proof",
                    }
                )
    return _dedupe_rows(rows, key_fields=("zone_id", "reason"))


def _layout_allowed_actions(section_salvage_allowed: bool, connector_entries: Sequence[Dict[str, Any]]) -> List[str]:
    actions = ["whole-board reuse after authority gates close", "connector-based harness reuse after measured pinout"]
    if connector_entries:
        actions.append("label and fixture known connector entry points")
    if section_salvage_allowed:
        actions.append("bounded section salvage inside measured/annotated layout region")
    return _dedupe(actions)


def _layout_prohibited_actions(section_salvage_allowed: bool, no_cut_zones: Sequence[Dict[str, Any]]) -> List[str]:
    actions = []
    if not section_salvage_allowed:
        actions.append("board-section cutting from visual evidence alone")
        actions.append("hidden-trace splice or copper cut without backside/topology proof")
    if no_cut_zones:
        actions.append("cutting, charging, loading, or desoldering through no-cut zones before clearance")
    return _dedupe(actions)


def _reuse_splice_strategy(
    facts: Dict[str, Any],
    board_function: Dict[str, Any],
    protocol: Dict[str, Any],
    value_decision: Dict[str, Any],
    component_salvage: Dict[str, Any],
) -> Dict[str, Any]:
    primary = str(board_function.get("primary_function_id") or "unknown")
    authority = str(facts.get("authority_status") or "unavailable")
    hard_hold = bool(component_salvage.get("salvage_posture") == "safety_hold")
    readiness = _reuse_readiness(authority, hard_hold, protocol)
    ports = _splice_ports(facts)
    recipes = _reuse_recipes(primary, readiness)
    allowed, prohibited = _reuse_action_policy(authority, readiness, primary)
    return {
        "schema_version": "reuse_splice_strategy.v1",
        "primary_function_id": primary,
        "readiness": readiness,
        "decision": value_decision.get("decision"),
        "strategy_summary": _strategy_summary(primary, readiness),
        "candidate_entry_points": ports[:10],
        "recipes": recipes[:4],
        "allowed_actions": allowed,
        "prohibited_actions": prohibited,
        "materials_or_mates": _materials_for_primary(primary),
        "best_next_checkpoint": _best_next_checkpoint(protocol, readiness),
        "component_salvage_link": {
            "preferred_reuse_class": component_salvage.get("preferred_reuse_class"),
            "preferred_item_count": component_salvage.get("preferred_item_count"),
            "blocked_item_count": component_salvage.get("blocked_item_count"),
        },
        "claim_boundary": "Splice recipes are templates until connector pinout, voltage/current limits, and terminal outcome evidence are recorded.",
    }


def _arbitrary_board_trust_assessment(
    facts: Dict[str, Any],
    board_function: Dict[str, Any],
    contradictions: Dict[str, Any],
    protocol: Dict[str, Any],
    fault_isolation: Dict[str, Any],
    value_decision: Dict[str, Any],
    reuse_splice: Dict[str, Any],
) -> Dict[str, Any]:
    measurement_metrics = _measurement_metrics(facts)
    outcome_metrics = _outcome_metrics(facts)
    release_metrics = _release_manifest_metrics(facts.get("production_release") or {})
    dimensions = {
        "visual_coverage": _visual_coverage_dimension(facts),
        "part_grounding": _part_grounding_dimension(facts, board_function),
        "topology_confidence": _topology_confidence_dimension(facts),
        "measurement_provenance": measurement_metrics["score"],
        "safety_authority": _safety_authority_dimension(facts, contradictions, fault_isolation),
        "functional_outcome": outcome_metrics["score"],
        "release_package": release_metrics["score"],
        "evidence_independence": _evidence_independence(facts, measurement_metrics, outcome_metrics, release_metrics)["score"],
    }
    hard_blocked = (
        str(facts.get("authority_status") or "") == "blocked"
        or int(contradictions.get("hard_count") or 0) > 0
        or str(fault_isolation.get("state") or "") == "blocked_safety_hold"
    )
    if hard_blocked:
        score = 0.0
    else:
        score = _weighted_score(
            dimensions,
            {
                "visual_coverage": 0.10,
                "part_grounding": 0.14,
                "topology_confidence": 0.18,
                "measurement_provenance": 0.18,
                "safety_authority": 0.16,
                "functional_outcome": 0.14,
                "release_package": 0.06,
                "evidence_independence": 0.04,
            },
        )
    production_readiness = 0.0 if hard_blocked else _weighted_score(
        dimensions,
        {
            "part_grounding": 0.05,
            "topology_confidence": 0.20,
            "measurement_provenance": 0.25,
            "safety_authority": 0.20,
            "functional_outcome": 0.20,
            "release_package": 0.10,
        },
    )
    level = _trust_level_for_arbitrary_board(
        hard_blocked=hard_blocked,
        dimensions=dimensions,
        facts=facts,
        outcome_metrics=outcome_metrics,
        release_metrics=release_metrics,
        reuse_splice=reuse_splice,
    )
    gaps = _trust_blocking_gaps(
        facts=facts,
        hard_blocked=hard_blocked,
        dimensions=dimensions,
        measurement_metrics=measurement_metrics,
        outcome_metrics=outcome_metrics,
        release_metrics=release_metrics,
        contradictions=contradictions,
        protocol=protocol,
    )
    independence = _evidence_independence(facts, measurement_metrics, outcome_metrics, release_metrics)
    return {
        "schema_version": "arbitrary_board_trust_assessment.v1",
        "available": True,
        "score": score,
        "level": level,
        "production_readiness_score": production_readiness,
        "trust_dimensions": dimensions,
        "evidence_independence": independence,
        "measurement_provenance": {
            "passed_categories": sorted(measurement_metrics["passed_categories"]),
            "trusted_categories": sorted(measurement_metrics["trusted_categories"]),
            "missing_trusted_categories": measurement_metrics["missing_trusted_categories"],
            "trusted_measurement_count": measurement_metrics["trusted_count"],
        },
        "functional_outcome": {
            "available": outcome_metrics["available"],
            "terminal_success": outcome_metrics["terminal_success"],
            "missing_requirements": outcome_metrics["missing_requirements"],
        },
        "release_package": {
            "available": release_metrics["available"],
            "complete": release_metrics["complete"],
            "missing_requirements": release_metrics["missing_requirements"],
        },
        "blocking_gaps": gaps,
        "remaining_unknowns": _trust_remaining_unknowns(facts, measurement_metrics, outcome_metrics),
        "readiness_summary": _trust_readiness_summary(level, score, production_readiness, value_decision, reuse_splice),
        "claim_boundary": (
            "Trust assessment is a readiness and gap report for arbitrary boards. It does not authorize power, "
            "splicing, sale, or production release; those remain gated by repair_authority and production_repair_authority."
        ),
    }


def _visual_coverage_dimension(facts: Dict[str, Any]) -> float:
    board = facts.get("board_evidence") if isinstance(facts.get("board_evidence"), dict) else {}
    if not board and not facts.get("detections"):
        return 0.0
    capture_coverage = facts.get("capture_coverage") if isinstance(facts.get("capture_coverage"), dict) else {}
    board_reconstruction = board.get("multiview_reconstruction") if isinstance(board.get("multiview_reconstruction"), dict) else {}
    capture_score = _safe_float(capture_coverage.get("score") or board_reconstruction.get("capture_coverage_score"), 0.0)
    score = 0.12
    components = facts.get("components") or []
    connectors = facts.get("connectors") or []
    markings = facts.get("markings") or []
    damage_declared = "damage" in board
    if components:
        score += min(0.22, 0.10 + 0.03 * len(components))
    if connectors:
        score += min(0.18, 0.08 + 0.03 * len(connectors))
    if markings:
        score += min(0.18, 0.09 + 0.03 * len(markings))
    if damage_declared:
        score += 0.12
    if _has_multiview_visuals(board):
        score += 0.18
    elif board.get("images") or board.get("photos") or board.get("image_uri"):
        score += 0.08
    if facts.get("detections"):
        score += 0.08
    if capture_score:
        score += min(0.12, capture_score * 0.12)
    return _clamp(score)


def _part_grounding_dimension(facts: Dict[str, Any], board_function: Dict[str, Any]) -> float:
    grounding = facts.get("part_grounding") if isinstance(facts.get("part_grounding"), dict) else {}
    matches = [row for row in grounding.get("matched_parts") or [] if isinstance(row, dict)]
    if not matches:
        return 0.18 if board_function.get("primary_function_id") != "unknown_low_voltage_module" else 0.04
    avg_confidence = sum(_safe_float(row.get("confidence"), 0.0) for row in matches) / max(len(matches), 1)
    score = 0.34 + min(0.36, 0.12 * len(matches)) + min(0.24, avg_confidence * 0.25)
    if grounding.get("grounded_capabilities"):
        score += 0.06
    return _clamp(score)


def _topology_confidence_dimension(facts: Dict[str, Any]) -> float:
    topology = facts.get("topology_authority") if isinstance(facts.get("topology_authority"), dict) else {}
    if facts.get("has_reference_topology") and not facts.get("has_topology"):
        return 0.30 if topology.get("pinout_known") else 0.18
    if not facts.get("has_topology") and not topology:
        visual_topology = facts.get("visual_topology_hypothesis") if isinstance(facts.get("visual_topology_hypothesis"), dict) else {}
        if not visual_topology.get("available"):
            return 0.0
        readiness = visual_topology.get("readiness") if isinstance(visual_topology.get("readiness"), dict) else {}
        return _clamp(
            min(
                0.30,
                0.08
                + 0.06 * min(int(readiness.get("connector_hypothesis_count") or 0), 2)
                + 0.05 * min(int(readiness.get("connection_hypothesis_count") or 0), 2)
                + 0.04 * (1 if readiness.get("multi_view_evidence") else 0),
            )
        )
    if topology.get("shorts_detected"):
        return 0.0
    score = 0.18
    if topology.get("measurement_backed") or facts.get("has_topology"):
        score += 0.22
    if topology.get("pinout_known"):
        score += 0.32
    trusted_count = int(topology.get("trusted_measurement_count") or 0)
    measurement_count = int(topology.get("measurement_count") or 0)
    score += min(0.18, trusted_count * 0.04)
    score += min(0.10, measurement_count * 0.015)
    if int(topology.get("unknown_pin_count") or 0) == 0 and measurement_count:
        score += 0.05
    return _clamp(score)


def _safety_authority_dimension(
    facts: Dict[str, Any],
    contradictions: Dict[str, Any],
    fault_isolation: Dict[str, Any],
) -> float:
    status = str(facts.get("authority_status") or "unavailable")
    if status == "blocked" or int(contradictions.get("hard_count") or 0) > 0:
        return 0.0
    if str(fault_isolation.get("state") or "") == "blocked_safety_hold":
        return 0.0
    mapping = {
        "authoritative_low_risk": 0.95,
        "measurement_backed": 0.62,
        "needs_measurements": 0.34,
        "visual_only": 0.26,
        "unavailable": 0.12,
    }
    score = mapping.get(status, 0.16)
    if int(contradictions.get("soft_count") or 0) > 0:
        score -= 0.08
    return _clamp(score)


def _measurement_metrics(facts: Dict[str, Any]) -> Dict[str, Any]:
    authority = facts.get("repair_authority") if isinstance(facts.get("repair_authority"), dict) else {}
    summary = authority.get("measurement_summary") if isinstance(authority.get("measurement_summary"), dict) else {}
    passed_categories = set(summary.get("passed_categories") or [])
    trusted_categories = set(summary.get("trusted_categories") or [])
    trusted_count = int(summary.get("trusted_count") or 0)
    if not passed_categories and not trusted_categories:
        rows = [row for row in facts.get("measurements") or [] if isinstance(row, dict)]
        passed_rows = [row for row in rows if _measurement_passed(row) and not _measurement_failed(row)]
        trusted_rows = [row for row in passed_rows if _measurement_trusted(row)]
        passed_categories = {
            category
            for row in passed_rows
            for category in _measurement_categories(row)
        }
        trusted_categories = {
            category
            for row in trusted_rows
            for category in _measurement_categories(row)
        }
        trusted_count = len(trusted_rows)
    required = {"resistance", "continuity", "voltage", "current", "thermal"}
    passed_coverage = len(required & passed_categories) / len(required)
    trusted_coverage = len(required & trusted_categories) / len(required)
    return {
        "passed_categories": passed_categories,
        "trusted_categories": trusted_categories,
        "missing_trusted_categories": sorted(required - trusted_categories),
        "trusted_count": trusted_count,
        "score": _clamp((0.35 * passed_coverage) + (0.65 * trusted_coverage)),
    }


def _outcome_metrics(facts: Dict[str, Any]) -> Dict[str, Any]:
    outcomes = [row for row in facts.get("outcomes") or [] if isinstance(row, dict)]
    latest = outcomes[-1] if outcomes else {}
    if not latest:
        return {
            "available": False,
            "score": 0.0,
            "terminal_success": False,
            "missing_requirements": ["Record terminal build/repair/reuse outcome."],
        }
    decision = str(latest.get("decision") or "").replace(" ", "_").lower()
    positive_decision = decision in {"built", "repaired", "reused", "sold", "pass", "passed", "success"}
    output_verified = _truthy(latest.get("output_function_verified"))
    first_power = _positive_result(latest.get("first_power_result") or latest.get("power_result"))
    thermal = _positive_result(latest.get("thermal_result") or latest.get("thermal_behavior"))
    measurements = latest.get("measurements_recorded") not in {None, "", False}
    evidence = bool(latest.get("evidence_uri") or latest.get("artifact_uri") or latest.get("test_report_uri"))
    checks = {
        "positive_decision": positive_decision,
        "output_function_verified": output_verified,
        "first_power_result": first_power,
        "thermal_result": thermal,
        "measurements_recorded": measurements,
        "outcome_artifact": evidence,
    }
    return {
        "available": True,
        "score": _clamp(sum(1 for passed in checks.values() if passed) / len(checks)),
        "terminal_success": positive_decision and output_verified and first_power and thermal,
        "missing_requirements": _dedupe(
            label
            for label, passed in [
                ("Record a positive terminal decision.", positive_decision),
                ("Record output_function_verified=true.", output_verified),
                ("Record first_power_result=pass.", first_power),
                ("Record thermal_result=normal or pass.", thermal),
                ("Record measurements_recorded=true.", measurements),
                ("Attach outcome evidence_uri or artifact_uri.", evidence),
            ]
            if not passed
        ),
    }


def _release_manifest_metrics(manifest: Dict[str, Any]) -> Dict[str, Any]:
    if not manifest:
        return {
            "available": False,
            "score": 0.0,
            "complete": False,
            "missing_requirements": ["Attach production_release or release_manifest."],
        }
    resource_ids = manifest.get("selected_resource_ids") or manifest.get("resource_ids") or manifest.get("selected_resource_ids_used")
    if isinstance(resource_ids, str):
        has_resource_ids = bool(resource_ids.strip())
    else:
        has_resource_ids = bool(resource_ids)
    operator = manifest.get("released_by") or manifest.get("approved_by") or manifest.get("release_operator_id")
    artifact_uris = _dedupe(
        [
            *(_list_strings(manifest.get("artifact_uris"))),
            *(_list_strings(manifest.get("evidence_uris"))),
            *(_list_strings(manifest.get("test_report_uris"))),
            manifest.get("artifact_uri"),
            manifest.get("evidence_uri"),
            manifest.get("test_report_uri"),
        ]
    )
    sample_count = _safe_int(
        manifest.get("repeatability_sample_count")
        or manifest.get("repeatability_count")
        or manifest.get("sample_count")
        or manifest.get("validated_unit_count"),
        0,
    )
    checks = {
        "release_id": bool(manifest.get("release_id")),
        "selected_resource_ids": has_resource_ids,
        "released_by_or_approved_by": bool(operator),
        "released_at": bool(manifest.get("released_at")),
        "scope_statement": bool(manifest.get("scope_statement")),
        "artifact_uri": bool(artifact_uris),
        "acceptance_reviewed": _truthy(manifest.get("acceptance_reviewed") or manifest.get("accepted")),
        "repeatability_sample_count": sample_count >= 1,
    }
    missing = [
        label
        for label, passed in [
            ("Add release_id.", checks["release_id"]),
            ("List selected_resource_ids.", checks["selected_resource_ids"]),
            ("Record released_by/approved_by/release_operator_id.", checks["released_by_or_approved_by"]),
            ("Record released_at.", checks["released_at"]),
            ("Add scope_statement.", checks["scope_statement"]),
            ("Attach artifact_uri/evidence_uri/test_report_uri.", checks["artifact_uri"]),
            ("Mark acceptance_reviewed=true.", checks["acceptance_reviewed"]),
            ("Record repeatability_sample_count >= 1.", checks["repeatability_sample_count"]),
        ]
        if not passed
    ]
    score = _clamp(sum(1 for passed in checks.values() if passed) / len(checks))
    return {
        "available": True,
        "score": score,
        "complete": score >= 1.0,
        "missing_requirements": missing,
    }


def _evidence_independence(
    facts: Dict[str, Any],
    measurement_metrics: Dict[str, Any],
    outcome_metrics: Dict[str, Any],
    release_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    source_types = []
    if facts.get("has_visual"):
        source_types.append("visual_board_evidence")
    if (facts.get("part_grounding") or {}).get("available"):
        source_types.append("visible_marking_catalog_grounding")
    if facts.get("has_topology"):
        source_types.append("measured_topology")
    if measurement_metrics.get("trusted_categories"):
        source_types.append("trusted_bench_measurements")
    if outcome_metrics.get("available"):
        source_types.append("terminal_outcome")
    if release_metrics.get("available"):
        source_types.append("production_release_manifest")
    operators = _dedupe(
        [
            *[row.get("operator_id") for row in facts.get("measurements") or [] if isinstance(row, dict)],
            *[row.get("operator_id") or row.get("captured_by") or row.get("technician_id") for row in facts.get("outcomes") or [] if isinstance(row, dict)],
            (facts.get("production_release") or {}).get("released_by"),
            (facts.get("production_release") or {}).get("approved_by"),
            (facts.get("production_release") or {}).get("release_operator_id"),
        ]
    )
    instruments = _dedupe(row.get("instrument_id") for row in facts.get("measurements") or [] if isinstance(row, dict))
    artifacts = _dedupe(
        [
            *[row.get("evidence_uri") or row.get("artifact_uri") or row.get("test_report_uri") for row in facts.get("measurements") or [] if isinstance(row, dict)],
            *[row.get("evidence_uri") or row.get("artifact_uri") or row.get("test_report_uri") for row in facts.get("outcomes") or [] if isinstance(row, dict)],
            (facts.get("production_release") or {}).get("artifact_uri"),
            (facts.get("production_release") or {}).get("evidence_uri"),
            (facts.get("production_release") or {}).get("test_report_uri"),
        ]
    )
    score = min(
        1.0,
        (len(set(source_types)) / 6.0)
        + min(len(operators), 2) * 0.07
        + min(len(instruments), 2) * 0.04
        + min(len(artifacts), 2) * 0.05,
    )
    return {
        "score": round(score, 3),
        "source_types": _dedupe(source_types),
        "independent_source_count": len(set(source_types)),
        "operator_ids": operators[:6],
        "instrument_ids": instruments[:6],
        "artifact_uris": artifacts[:8],
    }


def _trust_level_for_arbitrary_board(
    *,
    hard_blocked: bool,
    dimensions: Dict[str, float],
    facts: Dict[str, Any],
    outcome_metrics: Dict[str, Any],
    release_metrics: Dict[str, Any],
    reuse_splice: Dict[str, Any],
) -> str:
    if hard_blocked:
        return "blocked_safety_hold"
    if (
        outcome_metrics.get("terminal_success")
        and release_metrics.get("complete")
        and dimensions.get("measurement_provenance", 0.0) >= 0.9
        and dimensions.get("safety_authority", 0.0) >= 0.9
        and dimensions.get("topology_confidence", 0.0) >= 0.72
    ):
        return "production_release_candidate"
    if (
        reuse_splice.get("readiness") == "controlled_splice_ready"
        and dimensions.get("safety_authority", 0.0) >= 0.8
        and dimensions.get("topology_confidence", 0.0) >= 0.7
    ):
        return "controlled_reuse_ready"
    if facts.get("has_topology") or str(facts.get("authority_status") or "") == "measurement_backed":
        return "measured_diagnostic"
    board = facts.get("board_evidence") if isinstance(facts.get("board_evidence"), dict) else {}
    if facts.get("has_visual_topology") and _has_multiview_visuals(board):
        return "multi_view_visual_topology_candidate"
    if _has_multiview_visuals(board) and ((facts.get("part_grounding") or {}).get("available") or dimensions.get("part_grounding", 0.0) >= 0.35):
        return "multi_view_grounded_visual_candidate"
    if _has_multiview_visuals(board):
        return "multi_view_visual_candidate"
    if (facts.get("part_grounding") or {}).get("available") or dimensions.get("part_grounding", 0.0) >= 0.35:
        return "grounded_visual_candidate"
    if facts.get("has_visual_topology"):
        return "visual_topology_candidate"
    if facts.get("has_visual"):
        return "visual_candidate"
    return "baseline_evidence_required"


def _trust_blocking_gaps(
    *,
    facts: Dict[str, Any],
    hard_blocked: bool,
    dimensions: Dict[str, float],
    measurement_metrics: Dict[str, Any],
    outcome_metrics: Dict[str, Any],
    release_metrics: Dict[str, Any],
    contradictions: Dict[str, Any],
    protocol: Dict[str, Any],
) -> List[str]:
    gaps: List[str] = []
    if hard_blocked:
        gaps.extend(str(item.get("summary") or item.get("resolution") or "") for item in contradictions.get("items") or [] if isinstance(item, dict))
    topology = facts.get("topology_authority") if isinstance(facts.get("topology_authority"), dict) else {}
    if not facts.get("has_topology"):
        if facts.get("has_reference_topology"):
            gaps.append("Confirm public reference topology on the physical board with measured pinout, no-short, voltage, current, and thermal evidence.")
        elif facts.get("has_visual_topology"):
            gaps.append("Attach measured topology evidence for connector pinout, no-short, voltage, current, and thermal lanes by running the visual topology measurement queue.")
        else:
            gaps.append("Attach measured topology evidence for connector pinout, no-short, voltage, current, and thermal lanes.")
    elif not topology.get("pinout_known"):
        gaps.append("Complete measured connector pinout; unknown pins remain outside the trust boundary.")
    if not facts.get("has_topology") and dimensions.get("part_grounding", 0.0) < 0.35:
        gaps.append("Ground visible markings or identify key IC/package families before relying on board function claims.")
    missing_categories = measurement_metrics.get("missing_trusted_categories") or []
    if missing_categories:
        gaps.append(f"Attach trusted measurement artifacts for: {', '.join(missing_categories)}.")
    if not outcome_metrics.get("terminal_success"):
        gaps.extend(outcome_metrics.get("missing_requirements") or [])
    if not release_metrics.get("complete"):
        gaps.extend(release_metrics.get("missing_requirements") or [])
    for step in protocol.get("steps") or []:
        if not isinstance(step, dict) or step.get("status") not in {"open", "blocked"}:
            continue
        if step.get("required_before") in {"repair_power_release", "first_power", "splice_release", "demo_or_release"}:
            gaps.append(str(step.get("action") or "Close open authority protocol step."))
    return _dedupe(gaps)[:16]


def _trust_remaining_unknowns(
    facts: Dict[str, Any],
    measurement_metrics: Dict[str, Any],
    outcome_metrics: Dict[str, Any],
) -> List[str]:
    unknowns: List[str] = []
    topology = facts.get("topology_authority") if isinstance(facts.get("topology_authority"), dict) else {}
    if not facts.get("has_visual"):
        unknowns.append("No visual packet is attached for markings, component placement, connector orientation, or damage review.")
    if not _has_multiview_visuals(facts.get("board_evidence") if isinstance(facts.get("board_evidence"), dict) else {}):
        unknowns.append("Multi-photo evidence is not explicit enough to cross-check markings, connectors, placement, and damage.")
    capture_coverage = facts.get("capture_coverage") if isinstance(facts.get("capture_coverage"), dict) else {}
    open_lanes = capture_coverage.get("open_required_lanes") if isinstance(capture_coverage.get("open_required_lanes"), list) else []
    if open_lanes:
        unknowns.append(f"Photo capture coverage still lacks: {', '.join(str(lane) for lane in open_lanes[:6])}.")
    if int(topology.get("unknown_pin_count") or 0) > 0:
        unknowns.append(f"{topology.get('unknown_pin_count')} connector pin(s) still have unknown role.")
    if not measurement_metrics.get("trusted_categories"):
        unknowns.append("No fully trusted measurement categories are recorded.")
    if not outcome_metrics.get("available"):
        unknowns.append("No terminal outcome is recorded.")
    return _dedupe(unknowns)[:10]


def _trust_readiness_summary(
    level: str,
    score: float,
    production_readiness: float,
    value_decision: Dict[str, Any],
    reuse_splice: Dict[str, Any],
) -> str:
    return (
        f"level={level}; trust_score={score:.2f}; production_readiness={production_readiness:.2f}; "
        f"value_decision={value_decision.get('decision')}; reuse_readiness={reuse_splice.get('readiness')}"
    )


def _next_evidence_tasks(
    protocol: Dict[str, Any],
    contradictions: Dict[str, Any],
    fault_isolation: Dict[str, Any],
    value_decision: Dict[str, Any],
    reuse_splice: Dict[str, Any],
    part_grounding: Dict[str, Any],
    bench_protocol: Dict[str, Any],
    visual_topology: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    visual_tasks: List[Dict[str, Any]] = []
    if isinstance(visual_topology, dict) and visual_topology.get("available"):
        for task in visual_topology.get("measurement_queue") or []:
            if not isinstance(task, dict):
                continue
            row = dict(task)
            row.setdefault("source", "visual_topology_hypothesis")
            row.setdefault("usable_for", ["repair", "reuse", "splice", "portfolio_demo"])
            visual_tasks.append(row)
    for contradiction in contradictions.get("items") or []:
        if not isinstance(contradiction, dict):
            continue
        tasks.append(
            {
                "task_id": f"contradiction_{contradiction.get('id')}",
                "type": "review" if contradiction.get("severity") == "soft" else "measurement",
                "status": "open",
                "priority": 0 if contradiction.get("severity") == "hard" else 2,
                "prompt": contradiction.get("resolution"),
                "source": "arbitrary_board_contradiction",
                "usable_for": ["repair", "safety", "salvage", "training"],
            }
        )
    if bench_protocol.get("step_count") and reuse_splice.get("readiness") != "controlled_splice_ready":
        tasks.append(
            {
                "task_id": "bench_protocol_pack",
                "type": "measurement",
                "status": "open",
                "priority": -1,
                "prompt": (
                    f"Run the {bench_protocol.get('title')} bench protocol and attach artifacts for: "
                    f"{', '.join(bench_protocol.get('required_measurement_categories') or [])}."
                ),
                "source": "bench_protocol_pack",
                "usable_for": ["repair", "reuse", "splice", "production_release", "portfolio_demo"],
            }
        )
    for step in protocol.get("steps") or []:
        if not isinstance(step, dict) or step.get("status") == "pass":
            continue
        if step.get("required_before") not in {
            "repair_power_release",
            "first_power",
            "splice_release",
            "external_target_connection",
            "real_load_connection",
            "reuse_as_sensor",
            "power_stage_reuse",
            "downstream_power_connection",
            "controller_io_connection",
            "specialist_authority",
            "network_or_rf_integration",
            "ui_harness_connection",
            "audio_load_connection",
        }:
            continue
        tasks.append(
            {
                "task_id": f"protocol_{step.get('step_id')}",
                "type": "measurement" if step.get("category") != "review" else "review",
                "status": "open",
                "priority": 0 if step.get("status") == "blocked" else 1,
                "prompt": step.get("action"),
                "source": step.get("source") if step.get("source") == "visual_topology_hypothesis" else "arbitrary_board_measurement_protocol",
                "usable_for": ["repair", "bringup", "salvage", "training"],
            }
        )
    tasks.extend(visual_tasks[:8])
    checkpoint = str(reuse_splice.get("best_next_checkpoint") or "")
    if checkpoint and reuse_splice.get("readiness") != "controlled_splice_ready":
        tasks.append(
            {
                "task_id": "reuse_splice_checkpoint",
                "type": "measurement" if reuse_splice.get("readiness") not in {"blocked_safety_hold", "visual_mapping_only"} else "review",
                "status": "open",
                "priority": 1 if reuse_splice.get("readiness") == "blocked_safety_hold" else 2,
                "prompt": checkpoint,
                "source": "reuse_splice_strategy",
                "usable_for": ["repair", "reuse", "splice", "portfolio_demo"],
            }
        )
    if reuse_splice.get("readiness") in {"visual_mapping_only", "baseline_evidence_required"}:
        tasks.extend(
            task
            for task in part_grounding.get("grounding_tasks") or []
            if isinstance(task, dict)
        )
    return _dedupe_tasks(tasks)[:20]


def _salvage_item(item: Dict[str, Any], primary: str, hard_hold: bool) -> Dict[str, Any]:
    label = str(item.get("label") or item.get("name") or item.get("kind") or item.get("id") or "board item")
    kind = str(item.get("kind") or item.get("class_name") or item.get("type") or "").lower()
    text = f"{label} {kind}".lower()
    base = {
        "item_id": _safe_id(str(item.get("id") or item.get("ref") or label)),
        "label": label,
        "observed_kind": kind or "unknown",
        "evidence_confidence": _safe_float(item.get("confidence"), 0.58),
    }
    if _has_any(text, ["battery", "lipo", "li-ion", "bms"]):
        return {
            **base,
            "salvage_class": "battery_or_energy_storage",
            "status": "specialist_only",
            "capabilities": ["battery", "power"],
            "recommended_handling": "Do not charge, load, puncture, or splice without battery-specific authority.",
            "suggested_uses": [],
            "verification_required": ["chemistry", "cell count", "BMS protection", "thermal containment"],
            "estimated_recoverable_value_usd": 0.0,
        }
    if _has_any(text, ["ch340", "cp210", "ft232", "uart", "usb serial"]):
        return _salvage_candidate(
            base,
            "usb_serial_bridge",
            ["usb_serial", "connector"],
            ["debug adapter", "serial console", "bring-up harness"],
            "Reuse the whole bridge board through measured header pins; do not desolder the IC first.",
            ["measured pinout", "logic voltage", "loopback or safe serial capture"],
            8.0,
            hard_hold,
        )
    if _has_any(text, ["sensor", "bme", "bmp", "sht", "imu", "adc", "microphone"]):
        return _salvage_candidate(
            base,
            "sensor_frontend",
            ["sensor_or_adc", "connector"],
            ["sensor input module", "data logger input", "feedback sensor"],
            "Reuse through the connector or breakout pads after bus and voltage checks.",
            ["supply voltage", "pullups", "bus scan"],
            6.0,
            hard_hold,
        )
    if _has_any(text, ["relay", "mosfet", "motor", "driver", "triac", "load"]):
        return _salvage_candidate(
            base,
            "load_driver_stage",
            ["actuator_driver", "motor_or_load"],
            ["low-voltage load controller", "motor test jig", "fan or pump driver"],
            "Reuse only with dummy-load testing, current limiting, and thermal observation.",
            ["dummy load", "current limit", "flyback/protection", "thermal behavior"],
            10.0,
            hard_hold,
        )
    if _has_any(text, ["regulator", "buck", "boost", "ldo", "ams1117", "lm2596", "power"]):
        return _salvage_candidate(
            base,
            "power_stage",
            ["power", "protection"],
            ["bench adapter", "known-voltage supply stage", "protected power breakout"],
            "Reuse as a power stage only after no-short, voltage, load-current, and thermal checks.",
            ["no-short", "output voltage", "load current", "thermal behavior"],
            5.0,
            hard_hold,
        )
    if _has_any(text, ["mcu", "microcontroller", "esp32", "esp8266", "arduino", "controller"]):
        return _salvage_candidate(
            base,
            "controller_module",
            ["controller", "connector"],
            ["automation controller", "sensor logger controller", "smart switch brain"],
            "Reuse as a whole controller module; unknown firmware and I/O states remain gated.",
            ["power rails", "boot behavior", "I/O voltage domain"],
            9.0,
            hard_hold,
        )
    if _has_any(text, ["antenna", "wifi", "ble", "bluetooth", "rf", "lora", "zigbee"]):
        return _salvage_candidate(
            base,
            "wireless_module",
            ["wireless", "network_interface", "connector"],
            ["wireless control link", "network status module", "telemetry bridge"],
            "Reuse as a whole RF module after supply, antenna, and interface checks.",
            ["supply current", "antenna path", "interface voltage", "communication scan"],
            7.0,
            hard_hold,
        )
    if _has_any(text, ["display", "oled", "lcd", "led", "button", "switch", "keypad"]):
        return _salvage_candidate(
            base,
            "display_or_ui",
            ["display_or_ui", "led_or_light", "switch_or_button", "connector"],
            ["status indicator", "input panel", "simple user interface"],
            "Reuse through mapped pins with current limits and protected controller I/O.",
            ["pin map", "current limiting", "protected I/O test"],
            4.0,
            hard_hold,
        )
    if _has_any(text, ["audio", "speaker", "amp", "amplifier", "buzzer"]):
        return _salvage_candidate(
            base,
            "audio_or_alert",
            ["speaker_or_audio", "connector"],
            ["alert output", "small audio module", "status buzzer"],
            "Reuse only after impedance, idle-current, and low-level output checks.",
            ["load impedance", "idle current", "low-level output"],
            4.0,
            hard_hold,
        )
    if _has_any(text, ["connector", "header", "terminal", "usb", "jst", "jack"]) or kind in {"connector", "header"}:
        return _salvage_candidate(
            base,
            "connector_or_harness",
            ["connector"],
            ["labeled harness", "breakout cable", "safe splice entry point"],
            "Harvest or reuse as an entry point after continuity and pin-label confirmation.",
            ["continuity", "pin labels", "strain relief"],
            2.0,
            hard_hold,
        )
    if primary == "unknown_low_voltage_module":
        return {}
    return _salvage_candidate(
        base,
        "supporting_component",
        ["parts"],
        ["parts evidence for a future build"],
        "Treat as supporting inventory; value depends on board-level function proof.",
        ["component ID", "continuity", "board function outcome"],
        1.0,
        hard_hold,
    )


def _grounded_part_salvage_item(match: Dict[str, Any], hard_hold: bool) -> Dict[str, Any]:
    function_id = str(match.get("function_id") or "")
    label = f"{match.get('canonical_part') or match.get('family')} grounded by visible marking"
    value = _recoverable_value(function_id, "measurement_backed")
    return _salvage_candidate(
        {
            "item_id": _safe_id(str(match.get("part_id") or match.get("canonical_part") or label)),
            "label": label,
            "observed_kind": str(match.get("family") or "grounded_part"),
            "evidence_confidence": _safe_float(match.get("confidence"), 0.7),
        },
        _salvage_class_for_function(function_id),
        match.get("capabilities") or [],
        _suggested_uses_for_function(function_id),
        f"Use catalog grounding for {match.get('family')}; verify board-specific pinout, package, and measurements before reuse.",
        match.get("verification_required") or _confirmation_required(function_id),
        value,
        hard_hold,
    )


def _salvage_candidate(
    base: Dict[str, Any],
    salvage_class: str,
    capabilities: Sequence[str],
    suggested_uses: Sequence[str],
    handling: str,
    verification: Sequence[str],
    value: float,
    hard_hold: bool,
) -> Dict[str, Any]:
    return {
        **base,
        "salvage_class": salvage_class,
        "status": "safety_hold" if hard_hold else "candidate_after_measurements",
        "capabilities": _dedupe(capabilities),
        "recommended_handling": "Hold until hard safety evidence is resolved. " + handling if hard_hold else handling,
        "suggested_uses": _dedupe(suggested_uses),
        "verification_required": _dedupe(verification),
        "estimated_recoverable_value_usd": round(value * (0.25 if hard_hold else 1.0), 2),
    }


def _salvage_class_for_function(function_id: str) -> str:
    mapping = {
        "usb_serial_debug_bridge": "usb_serial_bridge",
        "sensor_or_adc_module": "sensor_frontend",
        "load_or_motor_driver": "load_driver_stage",
        "power_distribution_or_regulator": "power_stage",
        "controller_module": "controller_module",
        "battery_or_charger": "battery_or_energy_storage",
        "wireless_or_rf_module": "wireless_module",
        "display_or_ui_module": "display_or_ui",
        "audio_or_alert_module": "audio_or_alert",
    }
    return mapping.get(function_id, "grounded_part")


def _suggested_uses_for_function(function_id: str) -> List[str]:
    mapping = {
        "usb_serial_debug_bridge": ["debug adapter", "serial console", "bring-up harness"],
        "sensor_or_adc_module": ["sensor input module", "data logger input", "feedback sensor"],
        "load_or_motor_driver": ["low-voltage load controller", "motor test jig", "fan or pump driver"],
        "power_distribution_or_regulator": ["bench adapter", "known-voltage supply stage", "protected power breakout"],
        "controller_module": ["automation controller", "sensor logger controller", "smart switch brain"],
        "battery_or_charger": [],
        "wireless_or_rf_module": ["wireless control link", "network status module", "telemetry bridge"],
        "display_or_ui_module": ["status indicator", "input panel", "simple user interface"],
        "audio_or_alert_module": ["alert output", "small audio module", "status buzzer"],
    }
    return mapping.get(function_id, ["parts evidence for a future build"])


def _function_default_salvage_item(primary: str, hard_hold: bool) -> Dict[str, Any]:
    defaults = {
        "usb_serial_debug_bridge": ("USB/UART debug bridge board", "usb_serial_bridge", ["usb_serial", "connector"], ["debug adapter", "serial console"], 8.0),
        "sensor_or_adc_module": ("Sensor or ADC board", "sensor_frontend", ["sensor_or_adc", "connector"], ["sensor input module"], 6.0),
        "load_or_motor_driver": ("Load or motor driver board", "load_driver_stage", ["actuator_driver", "motor_or_load"], ["low-voltage load controller"], 10.0),
        "power_distribution_or_regulator": ("Power/regulator board", "power_stage", ["power", "protection"], ["bench adapter", "known-voltage supply stage"], 5.0),
        "controller_module": ("Controller board", "controller_module", ["controller", "connector"], ["automation controller"], 9.0),
        "battery_or_charger": ("Battery or charger path", "battery_or_energy_storage", ["battery", "power"], [], 0.0),
        "wireless_or_rf_module": ("Wireless/RF module", "wireless_module", ["wireless", "network_interface"], ["wireless control link"], 7.0),
        "display_or_ui_module": ("Display/UI module", "display_or_ui", ["display_or_ui", "connector"], ["status indicator", "input panel"], 4.0),
        "audio_or_alert_module": ("Audio/alert module", "audio_or_alert", ["speaker_or_audio", "connector"], ["alert output"], 4.0),
    }
    label, salvage_class, caps, uses, value = defaults.get(
        primary,
        ("Unknown low-voltage board", "unknown_board", ["connector"], ["parts evidence for a future build"], 3.0),
    )
    return _salvage_candidate(
        {"item_id": _safe_id(primary), "label": label, "observed_kind": "inferred_function", "evidence_confidence": 0.4},
        salvage_class,
        caps,
        uses,
        "Use the whole board first; component harvest comes after baseline measurements and function proof.",
        _confirmation_required(primary),
        value,
        hard_hold,
    )


def _preferred_reuse_class(primary: str, hard_hold: bool) -> str:
    if hard_hold:
        return "safety_hold_before_reuse"
    mapping = {
        "battery_or_charger": "specialist_only",
        "power_distribution_or_regulator": "controlled_power_stage_reuse",
        "load_or_motor_driver": "protected_load_driver_reuse",
        "usb_serial_debug_bridge": "whole_board_debug_adapter_reuse",
        "sensor_or_adc_module": "connector_based_sensor_reuse",
        "controller_module": "whole_board_controller_reuse",
        "wireless_or_rf_module": "whole_board_rf_module_reuse",
        "display_or_ui_module": "mapped_ui_harness_reuse",
        "audio_or_alert_module": "protected_audio_alert_reuse",
    }
    return mapping.get(primary, "baseline_measure_then_decide")


def _reuse_readiness(authority: str, hard_hold: bool, protocol: Dict[str, Any]) -> str:
    if hard_hold or authority == "blocked":
        return "blocked_safety_hold"
    if authority == "authoritative_low_risk" and protocol.get("status") in {"open", "passed"}:
        return "controlled_splice_ready"
    if authority == "measurement_backed":
        return "diagnostic_splice_candidate"
    if authority == "visual_only":
        return "visual_mapping_only"
    return "baseline_evidence_required"


def _splice_ports(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for interface in facts.get("interfaces") or []:
        if not isinstance(interface, dict):
            continue
        rows.append(
            {
                "port_id": _safe_id(f"{interface.get('type')}_{interface.get('connector_ref') or interface.get('net')}"),
                "connector_ref": interface.get("connector_ref"),
                "interface_type": interface.get("type"),
                "net": interface.get("net"),
                "confidence": _safe_float(interface.get("confidence"), 0.7),
                "pin_roles": _dedupe(
                    pin.get("role")
                    for pin in interface.get("pins") or []
                    if isinstance(pin, dict)
                )[:12],
                "required_verifications": _dedupe(interface.get("validation") or ["pinout", "voltage/current domain", "ground reference"]),
            }
        )
    if rows:
        return _dedupe_rows(rows, key_fields=("port_id",))
    for connector in facts.get("connectors") or []:
        if not isinstance(connector, dict):
            continue
        rows.append(
            {
                "port_id": _safe_id(str(connector.get("id") or connector.get("ref") or connector.get("label") or "connector")),
                "connector_ref": connector.get("id") or connector.get("ref") or connector.get("label"),
                "interface_type": "visual_candidate_connector",
                "net": None,
                "confidence": _safe_float(connector.get("confidence"), 0.55),
                "pin_roles": [],
                "required_verifications": ["measured pinout", "ground reference", "voltage/current domain"],
            }
        )
    return _dedupe_rows(rows, key_fields=("port_id",))


def _reuse_recipes(primary: str, readiness: str) -> List[Dict[str, Any]]:
    blocked = readiness == "blocked_safety_hold"
    templates = {
        "usb_serial_debug_bridge": [
            _recipe(
                "debug_bridge_reuse",
                "Reuse as a USB/UART debug adapter",
                ["usb_serial", "connector"],
                ["Identify GND, TX, RX, and logic voltage.", "Run loopback or safe serial capture.", "Connect target only after shared ground and voltage compatibility are proven."],
                ["stable serial loopback or target console", "no abnormal current or heat"],
                ["Do not connect TX/RX before logic voltage is known."],
            )
        ],
        "sensor_or_adc_module": [
            _recipe(
                "sensor_breakout_reuse",
                "Reuse as a sensor or ADC module",
                ["sensor_or_adc", "connector", "power"],
                ["Verify supply voltage and ground.", "Verify I2C/SPI pullups and idle bus state.", "Run a low-speed bus scan under current limit."],
                ["sensor address or signal is observed", "bus lines are not stuck", "current remains low"],
                ["Do not attach to a controller with mismatched voltage domains."],
            )
        ],
        "load_or_motor_driver": [
            _recipe(
                "protected_load_driver_reuse",
                "Reuse as a protected low-voltage load driver",
                ["actuator_driver", "motor_or_load", "power"],
                ["Use a dummy load first.", "Add fuse/current limit and verify flyback/protection.", "Observe thermal behavior before the real load."],
                ["output switches correctly", "current stays within configured limit", "no thermal runaway"],
                ["Do not attach the real motor/load before dummy-load proof."],
            )
        ],
        "power_distribution_or_regulator": [
            _recipe(
                "regulated_power_stage_reuse",
                "Reuse as a known-voltage power stage",
                ["power", "protection", "connector"],
                ["Measure no-short and polarity.", "Power with current limit.", "Load-test output before downstream connection."],
                ["voltage stays in range under dummy load", "current and temperature remain stable"],
                ["Do not power another board from an untested regulator."],
            )
        ],
        "controller_module": [
            _recipe(
                "controller_io_module_reuse",
                "Reuse as a controller or I/O brain",
                ["controller", "connector", "power"],
                ["Verify rails and boot behavior.", "Map safe I/O voltage.", "Keep external targets disconnected until firmware state is understood."],
                ["controller boots or idles predictably", "I/O voltage matches target interface"],
                ["Do not trust unknown firmware outputs around loads or safety hardware."],
            )
        ],
        "wireless_or_rf_module": [
            _recipe(
                "rf_module_reuse",
                "Reuse as a wireless or telemetry module",
                ["wireless", "network_interface", "connector"],
                ["Verify supply current and antenna path.", "Confirm host interface voltage.", "Run a low-power advertisement, scan, or link test."],
                ["communication event is observed", "current and heat remain normal"],
                ["Do not transmit at full power with unknown antenna or supply state."],
            )
        ],
        "display_or_ui_module": [
            _recipe(
                "ui_harness_reuse",
                "Reuse as a display, indicator, or input panel",
                ["display_or_ui", "switch_or_button", "led_or_light", "connector"],
                ["Map pins and polarity.", "Verify current limiting.", "Drive inputs/outputs through protected I/O."],
                ["inputs/outputs respond predictably", "no stuck lines or overcurrent"],
                ["Do not connect raw LEDs/buttons without current and pin-role checks."],
            )
        ],
        "audio_or_alert_module": [
            _recipe(
                "audio_alert_reuse",
                "Reuse as an audio or alert output",
                ["speaker_or_audio", "connector", "power"],
                ["Verify load impedance.", "Measure idle current.", "Run low-level output before full volume/load."],
                ["audio/alert output responds at low level", "amplifier current and heat remain normal"],
                ["Do not connect final speaker/load before impedance and current checks."],
            )
        ],
        "battery_or_charger": [
            _recipe(
                "battery_safety_triage",
                "Do not splice battery path without specialist authority",
                ["battery", "power"],
                ["Identify chemistry and cell count.", "Verify BMS/protection and enclosure.", "Use safe disposal if unknown or damaged."],
                ["battery-specific authority is recorded"],
                ["Do not charge, load, puncture, bypass BMS, or splice unknown packs."],
            )
        ],
    }
    rows = templates.get(
        primary,
        [
            _recipe(
                "baseline_board_reuse",
                "Measure first, then decide reuse versus harvest",
                ["connector"],
                ["Capture connector pinout.", "Run no-short, voltage, current, and thermal checks.", "Record a terminal function outcome."],
                ["function is identified and measured", "no hard safety blocker remains"],
                ["Do not power or splice unknown boards from visual evidence alone."],
            )
        ],
    )
    if blocked:
        for row in rows:
            row["status"] = "blocked_until_safety_hold_clears"
    return rows


def _recipe(
    recipe_id: str,
    title: str,
    required_capabilities: Sequence[str],
    steps: Sequence[str],
    acceptance: Sequence[str],
    prohibitions: Sequence[str],
) -> Dict[str, Any]:
    return {
        "recipe_id": recipe_id,
        "title": title,
        "status": "template",
        "required_capabilities": _dedupe(required_capabilities),
        "splice_steps": _dedupe(steps),
        "acceptance": _dedupe(acceptance),
        "prohibitions": _dedupe(prohibitions),
    }


def _reuse_action_policy(authority: str, readiness: str, primary: str) -> tuple[List[str], List[str]]:
    if readiness == "blocked_safety_hold":
        return (
            ["Photograph, label, isolate, and document the board without applying power.", "Harvest only passive/mechanical value after depowered hazard review."],
            ["first power", "external splice", "charging/loading energy storage", "claiming repair success"],
        )
    if readiness == "visual_mapping_only":
        return (
            ["Capture markings, connector close-ups, and baseline continuity/no-short measurements.", "Prepare candidate splice recipes but keep them gated."],
            ["first power from visual evidence", "connecting to a target system", "production repair release"],
        )
    if authority == "authoritative_low_risk":
        return (
            ["Run controlled first-power or splice within the measured low-risk scope.", "Record terminal function outcome and thermal/current evidence."],
            ["expanding beyond measured pins/rails", "connecting hazardous or unknown sections"],
        )
    return (
        ["Close open protocol measurements.", "Use current limits and dummy loads before external connection."],
        ["production release before all authority lanes close", "unbounded power or load testing"],
    )


def _materials_for_primary(primary: str) -> List[str]:
    mapping = {
        "usb_serial_debug_bridge": ["current-limited USB source", "logic-level reference", "jumper leads", "known-good target or loopback fixture"],
        "sensor_or_adc_module": ["current-limited supply", "pullup-aware controller", "logic analyzer or bus scanner", "jumper leads"],
        "load_or_motor_driver": ["current-limited supply", "dummy load", "fuse or resettable protection", "thermal observation"],
        "power_distribution_or_regulator": ["current-limited supply", "dummy load resistor/module", "DMM", "thermal observation"],
        "controller_module": ["current-limited supply", "logic analyzer or serial console", "known-safe I/O harness"],
        "battery_or_charger": ["battery-safe containment", "chemistry/cell-count reference", "specialist review workflow"],
        "wireless_or_rf_module": ["current-limited supply", "known antenna/load", "host interface", "scan/advertisement tool"],
        "display_or_ui_module": ["current-limited supply", "series resistors/protected I/O", "pinout harness"],
        "audio_or_alert_module": ["current-limited supply", "dummy speaker/load", "low-level signal source"],
    }
    return mapping.get(primary, ["DMM", "current-limited supply", "connector pinout notes", "thermal observation"])


def _best_next_checkpoint(protocol: Dict[str, Any], readiness: str) -> str:
    if readiness == "blocked_safety_hold":
        return "Resolve the hard safety/authority blocker before any power, splice, or normal reuse work."
    for step in protocol.get("steps") or []:
        if isinstance(step, dict) and str(step.get("status") or "") in {"open", "blocked"} and step.get("action"):
            return str(step.get("action"))
    if readiness == "controlled_splice_ready":
        return "Run and record terminal outcome under current limit, including current, voltage, and thermal behavior."
    return "Capture baseline no-short, pinout, voltage/current, and thermal evidence before deciding reuse."


def _strategy_summary(primary: str, readiness: str) -> str:
    labels = {
        "usb_serial_debug_bridge": "treat the board as a candidate debug/bring-up adapter",
        "sensor_or_adc_module": "treat the board as a candidate sensor front-end",
        "load_or_motor_driver": "treat the board as a protected load-driver candidate",
        "power_distribution_or_regulator": "treat the board as a power-stage candidate",
        "controller_module": "treat the board as a whole controller module candidate",
        "battery_or_charger": "treat the board as a battery/charger safety workflow, not normal salvage",
        "wireless_or_rf_module": "treat the board as a whole RF/network module candidate",
        "display_or_ui_module": "treat the board as a mapped UI harness candidate",
        "audio_or_alert_module": "treat the board as a protected audio/alert output candidate",
    }
    return f"{labels.get(primary, 'treat the board as unknown until measured')}; readiness={readiness}"


def _protocol_step(
    *,
    lane_id: str,
    category: str,
    action: str,
    expected_result: str,
    fail_branch: str,
    status: str,
    source: str,
    required_before: str,
) -> Dict[str, Any]:
    return {
        "lane_id": lane_id,
        "category": category,
        "action": action,
        "expected_result": expected_result,
        "fail_branch": fail_branch,
        "status": status,
        "source": source,
        "required_before": required_before,
    }


def _contradiction(
    contradiction_id: str,
    severity: str,
    summary: str,
    evidence: Sequence[Any],
    resolution: str,
) -> Dict[str, Any]:
    return {
        "id": contradiction_id,
        "severity": severity,
        "summary": summary,
        "evidence": _dedupe(evidence)[:8],
        "resolution": resolution,
    }


def _fault_candidate(
    fault_id: str,
    label: str,
    likelihood: float,
    evidence: Sequence[Any],
    diagnostic_actions: Sequence[str],
) -> Dict[str, Any]:
    return {
        "fault_id": fault_id,
        "label": label,
        "likelihood": round(min(max(likelihood, 0.0), 0.98), 3),
        "evidence": _dedupe(evidence)[:8],
        "diagnostic_actions": _dedupe(diagnostic_actions)[:8],
    }


def _lane_to_status(status: Any) -> str:
    raw = str(status or "").strip()
    if raw == "pass":
        return "pass"
    if raw == "fail":
        return "blocked"
    return "open"


def _category_for_lane(lane_id: Any) -> str:
    text = str(lane_id or "")
    mapping = {
        "hazard_scope": "safety",
        "measured_pinout": "topology",
        "no_short": "resistance",
        "reference_continuity": "continuity",
        "voltage_domain": "voltage",
        "current_limit": "current",
        "thermal_behavior": "thermal",
        "logic_interface": "logic",
        "load_path": "load",
        "terminal_outcome": "outcome",
    }
    return mapping.get(text, "measurement")


def _expected_for_lane(lane_id: Any) -> str:
    category = _category_for_lane(lane_id)
    expectations = {
        "safety": "No hard blocker remains.",
        "topology": "Every used connector pin has a measured role and voltage/domain where relevant.",
        "resistance": "No power rail reads as a dead short to ground.",
        "continuity": "Ground/reference continuity is stable.",
        "voltage": "Voltage and polarity match the measured low-voltage domain.",
        "current": "Current draw remains within the configured current limit.",
        "thermal": "Thermal behavior remains normal through the function test.",
        "logic": "Logic levels and bus/serial behavior are compatible.",
        "load": "Load path switches correctly under protected test load.",
        "outcome": "Successful output function, first power, and thermal outcome are recorded.",
    }
    return expectations.get(category, "Evidence passes and is recorded with provenance.")


def _dedupe_protocol_steps(steps: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for step in steps:
        action = str(step.get("action") or "").strip()
        key = (str(step.get("lane_id") or ""), action.lower())
        if not action or key in seen:
            continue
        seen.add(key)
        kept.append(dict(step))
    return kept


def _confirmation_required(function_id: str) -> List[str]:
    mapping = {
        "usb_serial_debug_bridge": ["measured pinout", "logic voltage", "loopback or safe serial capture"],
        "sensor_or_adc_module": ["supply voltage", "bus pullups", "low-speed bus scan"],
        "load_or_motor_driver": ["dummy-load test", "current limit", "thermal behavior"],
        "power_distribution_or_regulator": ["no-short", "output voltage", "load current", "thermal behavior"],
        "controller_module": ["power rails", "boot/current behavior", "I/O voltage domain"],
        "battery_or_charger": ["specialist battery safety checks", "charge path isolation", "thermal containment"],
        "wireless_or_rf_module": ["supply current", "antenna path", "interface voltage", "communication scan"],
        "display_or_ui_module": ["pin map", "current limiting", "protected I/O test"],
        "audio_or_alert_module": ["load impedance", "idle current", "low-level output test"],
    }
    return mapping.get(function_id, ["baseline no-short", "pinout", "voltage/current/thermal measurements"])


def _recoverable_value(primary: str, authority: str) -> float:
    base = {
        "usb_serial_debug_bridge": 8.0,
        "sensor_or_adc_module": 6.0,
        "load_or_motor_driver": 10.0,
        "power_distribution_or_regulator": 5.0,
        "controller_module": 9.0,
        "battery_or_charger": 2.0,
        "wireless_or_rf_module": 7.0,
        "display_or_ui_module": 4.0,
        "audio_or_alert_module": 4.0,
    }.get(primary, 3.0)
    if authority == "authoritative_low_risk":
        return round(base * 1.2, 2)
    if authority == "blocked":
        return round(base * 0.25, 2)
    if authority == "visual_only":
        return round(base * 0.5, 2)
    return base


def _estimated_cost(authority: str, hard_count: int) -> float:
    if authority == "blocked" or hard_count:
        return 2.0
    if authority == "authoritative_low_risk":
        return 0.5
    if authority == "visual_only":
        return 1.0
    return 0.75


def _estimated_time(authority: str, primary: str, hard_count: int) -> int:
    if authority == "blocked" or hard_count:
        return 35
    if authority == "authoritative_low_risk":
        return 15
    if primary == "unknown_low_voltage_module":
        return 45
    return 25


def _recommended_exit(decision: str, fault_isolation: Dict[str, Any]) -> str:
    if decision == "safety_hold_or_salvage_only":
        return "Stop normal repair; isolate hazard or harvest only safe passive/mechanical value after review."
    if decision == "controlled_reuse_or_repair_trial":
        return "Run terminal outcome and preserve board session evidence for portfolio/demo proof."
    if decision == "finish_measurements_then_reuse_or_repair":
        return "Close open authority lanes before deciding repair versus reuse."
    if fault_isolation.get("state") == "needs_measurements":
        return "Collect baseline measurements before spending parts or time."
    return "Continue only while value ratio and evidence improve."


def _measurement_rows(payload: Dict[str, Any], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for root in [payload, analysis]:
        if not isinstance(root, dict):
            continue
        for key in ["measurements", "measurement_history", "bench_measurements", "evidence_measurements"]:
            rows.extend(_list_dicts(root.get(key)))
        evidence = root.get("evidence") if isinstance(root.get("evidence"), dict) else {}
        rows.extend(_list_dicts(evidence.get("measurements")))
    return _dedupe_measurement_rows(rows)


def _outcome_rows(payload: Dict[str, Any], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for root in [payload, analysis]:
        if not isinstance(root, dict):
            continue
        for key in ["outcome_history", "past_outcomes", "prior_outcomes", "outcomes"]:
            rows.extend(_list_dicts(root.get(key)))
        rows.extend(_list_dicts(root.get("outcome")))
    return rows[-20:]


def _first_release_manifest(payload: Dict[str, Any], analysis: Dict[str, Any], latest_outcome: Dict[str, Any]) -> Dict[str, Any]:
    outcome_evidence = latest_outcome.get("production_evidence") if isinstance(latest_outcome.get("production_evidence"), dict) else {}
    for root in [payload, analysis, latest_outcome, outcome_evidence]:
        if not isinstance(root, dict):
            continue
        for key in ["production_release", "production_release_manifest", "release_manifest"]:
            value = root.get(key)
            if isinstance(value, dict) and value:
                return value
    return {}


def _dedupe_measurement_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        key = (
            str(row.get("measurement_id") or row.get("id") or index),
            str(row.get("type") or row.get("measurement_type") or ""),
            str(row.get("target") or ""),
            str(row.get("value") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def _measurement_passed(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("result") or row.get("value") or "").strip().lower()
    if row.get("passed") is True:
        return True
    return status in {"pass", "passed", "ok", "verified", "normal", "closed", "within_limit", "stable"}


def _measurement_failed(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("result") or row.get("value") or "").strip().lower()
    if row.get("failed") is True:
        return True
    return status in {"fail", "failed", "unsafe", "short", "shorted", "blocked", "open_unexpected"}


def _measurement_trusted(row: Dict[str, Any]) -> bool:
    if row.get("trusted") is True:
        return True
    required = ["instrument_id", "instrument_type", "calibration_status", "recorded_at", "operator_id"]
    return _measurement_passed(row) and all(str(row.get(key) or "").strip() for key in required)


def _measurement_categories(row: Dict[str, Any]) -> List[str]:
    raw_categories = row.get("categories")
    categories = _dedupe(raw_categories if isinstance(raw_categories, list) else [])
    if categories:
        return categories
    text = " ".join(
        str(value or "")
        for value in [
            row.get("type"),
            row.get("measurement_type"),
            row.get("target"),
            row.get("notes"),
            row.get("label"),
        ]
    ).lower()
    mapping = {
        "resistance": ["resistance", "ohm", "no-short", "short"],
        "continuity": ["continuity", "ground", "reference"],
        "voltage": ["voltage", "volt", "polarity", "vout", "logic high"],
        "current": ["current", "amp", "draw", "limit"],
        "thermal": ["thermal", "temperature", "heat", "hot"],
        "logic": ["logic", "uart", "serial", "i2c", "spi", "bus"],
        "load": ["load", "motor", "driver", "dummy"],
    }
    return [category for category, terms in mapping.items() if _has_any(text, terms)]


def _has_multiview_visuals(board: Dict[str, Any]) -> bool:
    photo_ids = set()
    for key in ["components", "markings", "connectors", "damage", "regions", "test_points", "salvage_candidates"]:
        for item in board.get(key) or []:
            if not isinstance(item, dict):
                continue
            for ref in item.get("source_refs") or []:
                if isinstance(ref, dict) and ref.get("photo_id"):
                    photo_ids.add(str(ref.get("photo_id")))
    if len(photo_ids) >= 2:
        return True
    reconstruction = board.get("multiview_reconstruction") if isinstance(board.get("multiview_reconstruction"), dict) else {}
    if int(reconstruction.get("usable_observation_count") or 0) >= 2:
        return True
    views = board.get("views")
    photos = board.get("photos") or board.get("images")
    labels: List[str] = []
    if isinstance(views, list):
        labels.extend(str(item.get("view") or item.get("label") or item) for item in views if isinstance(item, (dict, str)))
    if isinstance(photos, list):
        labels.extend(str(item.get("view") or item.get("label") or item) for item in photos if isinstance(item, (dict, str)))
    labels.extend(str(board.get(key) or "") for key in ["front_image_uri", "back_image_uri", "backside_image_uri"])
    joined = " ".join(labels).lower()
    has_front = any(term in joined for term in ["front", "top", "component"])
    has_back = any(term in joined for term in ["back", "bottom", "solder", "backside"])
    return has_front and has_back


def _weighted_score(values: Dict[str, float], weights: Dict[str, float]) -> float:
    total = sum(float(weight) for weight in weights.values()) or 1.0
    score = sum(_clamp(values.get(key, 0.0)) * float(weight) for key, weight in weights.items()) / total
    return round(_clamp(score), 3)


def _positive_result(value: Any) -> bool:
    if value is True:
        return True
    raw = str(value or "").strip().lower()
    return raw in {"pass", "passed", "ok", "normal", "success", "successful", "verified", "within_limit", "stable"}


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "pass", "passed", "verified", "accepted"}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = low
    return round(min(max(number, low), high), 3)


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:80] or "item"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dedupe_salvage_items(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = (
            str(row.get("item_id") or "").lower(),
            str(row.get("salvage_class") or "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def _hits(text: str, terms: Sequence[str]) -> List[str]:
    return [f"text hit: {term}" for term in terms if _term_present(text, term)]


def _interface_hits(interfaces: Iterable[str], wanted: Sequence[str]) -> List[str]:
    values = {str(item) for item in interfaces}
    return [f"measured interface: {item}" for item in wanted if item in values]


def _has_any(text: str, terms: Sequence[str]) -> bool:
    return any(_term_present(text, term) for term in terms)


def _term_present(text: str, term: Any) -> bool:
    tokens = _word_tokens(text)
    term_tokens = _word_tokens(str(term or ""))
    if not term_tokens:
        return False
    if len(term_tokens) == 1:
        return term_tokens[0] in tokens
    width = len(term_tokens)
    return any(tokens[index : index + width] == term_tokens for index in range(0, max(len(tokens) - width + 1, 0)))


def _word_tokens(value: Any) -> List[str]:
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


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _list_strings(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
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


def _dedupe_rows(rows: Sequence[Dict[str, Any]], *, key_fields: Sequence[str]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = tuple(str(row.get(field) or "").lower() for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def _dedupe_tasks(tasks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for task in tasks:
        if not isinstance(task, dict):
            continue
        prompt = str(task.get("prompt") or "").strip()
        key = (str(task.get("type") or ""), prompt.lower())
        if not prompt or key in seen:
            continue
        seen.add(key)
        kept.append(task)
    return kept
