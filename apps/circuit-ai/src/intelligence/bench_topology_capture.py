"""Convert operator bench captures into topology evidence.

Public pinouts and schematics are useful for planning a measurement session, but
they are not evidence that the board in hand matches that reference. This module
keeps that boundary explicit: templates may be seeded from references, while
bench captures must carry operator/instrument/artifact provenance before they can
close production measurement gates downstream.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence


SCHEMA_VERSION = "bench_topology_capture.v1"
TOPOLOGY_SCHEMA_VERSION = "topology_evidence.v1"
TRUST_KEYS = ("instrument_id", "instrument_type", "calibration_status", "recorded_at", "operator_id", "evidence_uri")
PASS_STATUSES = {"pass", "passed", "ok", "closed", "verified", "measured", "normal"}
OBSERVATION_KINDS = {"continuity", "resistance", "voltage", "current", "thermal"}


def enrich_payload_with_bench_topology_capture(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach topology_evidence converted from a bench_topology_capture packet."""

    body = dict(payload or {})
    capture = extract_bench_topology_capture(body)
    if not capture:
        return body

    reference = _reference_topology(body)
    topology = bench_capture_to_topology_evidence(capture, reference_topology=reference)
    if not _has_actionable_topology(topology):
        analysis = dict(body.get("analysis") if isinstance(body.get("analysis"), dict) else {})
        analysis["bench_topology_capture"] = _capture_summary(capture, topology)
        body["analysis"] = analysis
        return body

    existing_topology = body.get("topology_evidence")
    if _topology_is_reference_only(existing_topology):
        body.setdefault("reference_topology", existing_topology)
        body["topology_evidence"] = topology
    else:
        body["topology_evidence"] = _merge_topology_evidence(existing_topology, topology)
    analysis = dict(body.get("analysis") if isinstance(body.get("analysis"), dict) else {})
    analysis["bench_topology_capture"] = _capture_summary(capture, topology)
    analysis["bench_topology_evidence"] = topology
    body["analysis"] = analysis
    return body


def extract_bench_topology_capture(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Find a bench_topology_capture.v1 packet in common request shapes."""

    for root in _candidate_roots(payload):
        if not isinstance(root, dict):
            continue
        capture = root.get("bench_topology_capture")
        if isinstance(capture, dict):
            return capture
        if str(root.get("schema_version") or "") == SCHEMA_VERSION:
            return root
    return {}


def bench_capture_to_topology_evidence(
    capture: Dict[str, Any],
    *,
    reference_topology: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Convert an operator capture into topology_evidence.v1."""

    if not isinstance(capture, dict):
        return {"schema_version": TOPOLOGY_SCHEMA_VERSION, "connectors": []}

    artifacts = _artifacts(capture)
    instruments = _instruments(capture)
    root_provenance = _root_provenance(capture, instruments, artifacts)
    connectors = _connectors(capture, root_provenance)
    if not connectors and isinstance(reference_topology, dict):
        connectors = _reference_seed_connectors(reference_topology, root_provenance)

    observations = _observations(capture, root_provenance, instruments)
    grouped = {kind: [] for kind in OBSERVATION_KINDS}
    for row in observations:
        kind = str(row.get("kind") or "")
        if kind in grouped:
            grouped[kind].append(row)

    measured = bool(observations or _has_verified_pin(connectors))
    source_type = "bench_measurement_capture" if measured else "bench_capture_template"
    return {
        "schema_version": TOPOLOGY_SCHEMA_VERSION,
        "source": SCHEMA_VERSION,
        "source_type": source_type,
        "capture_id": str(capture.get("capture_id") or capture.get("id") or ""),
        "reference_uri": _reference_uri(capture, reference_topology),
        **root_provenance,
        "connectors": connectors,
        "continuity": grouped["continuity"],
        "resistance": grouped["resistance"],
        "voltage": grouped["voltage"],
        "current": grouped["current"],
        "thermal": grouped["thermal"],
        "artifacts": artifacts,
        "instruments": instruments,
        "capture_summary": {
            "connector_count": len(connectors),
            "observation_count": len(observations),
            "verified_pin_count": _verified_pin_count(connectors),
            "trusted_root_provenance": all(str(root_provenance.get(key) or "").strip() for key in TRUST_KEYS),
            "claim_boundary": "Bench evidence covers only captured pins, observations, instruments, and attached artifacts.",
        },
    }


def build_bench_capture_template(
    *,
    reference_topology: Dict[str, Any] | None = None,
    board_evidence: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build an operator-facing capture skeleton for real board measurements."""

    root_provenance = {key: "" for key in TRUST_KEYS}
    connectors = _reference_seed_connectors(reference_topology or {}, root_provenance)
    if not connectors:
        connectors = _connectors_from_board_evidence(board_evidence or {}, root_provenance)

    required = _required_observations(connectors)
    return {
        "schema_version": SCHEMA_VERSION,
        "capture_id": "",
        "operator_id": "",
        "recorded_at": "",
        "instruments": [
            {
                "instrument_id": "",
                "instrument_type": "calibrated_dmm",
                "calibration_status": "valid",
            },
            {
                "instrument_id": "",
                "instrument_type": "current_limited_supply",
                "calibration_status": "valid",
            },
            {
                "instrument_id": "",
                "instrument_type": "thermal_probe",
                "calibration_status": "valid",
            },
        ],
        "connectors": connectors,
        "measurements": required,
        "artifacts": [
            {"kind": "photo", "uri": "", "notes": "Pinout close-up with pin 1 marked."},
            {"kind": "measurement_log", "uri": "", "notes": "DMM/supply/thermal readings used for this capture."},
        ],
        "policy": {
            "reference_seed_is_not_evidence": True,
            "set_pin_status_verified_only_after_continuity_or_voltage_confirmation": True,
            "production_requires_instrument_operator_timestamp_and_artifact": True,
        },
    }


def _candidate_roots(payload: Dict[str, Any]) -> List[Any]:
    roots: List[Any] = [payload]
    for key in ["analysis", "results", "evidence", "topology"]:
        value = payload.get(key)
        if isinstance(value, dict):
            roots.append(value)
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    for key in ["bench", "topology"]:
        value = analysis.get(key)
        if isinstance(value, dict):
            roots.append(value)
    return roots


def _reference_topology(payload: Dict[str, Any]) -> Dict[str, Any]:
    candidates = [
        payload.get("reference_topology"),
        payload.get("topology_reference"),
        payload.get("topology_evidence"),
    ]
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    candidates.extend([analysis.get("reference_topology"), analysis.get("topology_evidence")])
    for candidate in candidates:
        if isinstance(candidate, dict) and (
            candidate.get("connectors") or str(candidate.get("schema_version") or "") == TOPOLOGY_SCHEMA_VERSION
        ):
            return candidate
    return {}


def _root_provenance(
    capture: Dict[str, Any],
    instruments: Sequence[Dict[str, Any]],
    artifacts: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    primary = instruments[0] if instruments else {}
    return {
        "instrument_id": str(capture.get("instrument_id") or primary.get("instrument_id") or ""),
        "instrument_type": str(capture.get("instrument_type") or primary.get("instrument_type") or ""),
        "calibration_status": str(capture.get("calibration_status") or primary.get("calibration_status") or ""),
        "recorded_at": str(capture.get("recorded_at") or capture.get("captured_at") or capture.get("timestamp") or ""),
        "operator_id": str(capture.get("operator_id") or capture.get("captured_by") or capture.get("user_id") or ""),
        "evidence_uri": str(capture.get("evidence_uri") or _first_artifact_uri(artifacts) or ""),
    }


def _instruments(capture: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for index, item in enumerate(_rows(capture.get("instruments") or capture.get("equipment")), start=1):
        row = item if isinstance(item, dict) else {"instrument_type": item}
        rows.append(
            {
                "instrument_id": str(row.get("instrument_id") or row.get("id") or row.get("serial") or f"instrument_{index}"),
                "instrument_type": str(row.get("instrument_type") or row.get("type") or row.get("kind") or ""),
                "calibration_status": str(row.get("calibration_status") or row.get("calibration") or ""),
            }
        )
    if not rows and any(capture.get(key) for key in ["instrument_id", "instrument_type", "calibration_status"]):
        rows.append(
            {
                "instrument_id": str(capture.get("instrument_id") or "instrument_1"),
                "instrument_type": str(capture.get("instrument_type") or ""),
                "calibration_status": str(capture.get("calibration_status") or ""),
            }
        )
    return rows


def _artifacts(capture: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    values = capture.get("artifacts") or capture.get("artifact_uris") or capture.get("evidence_artifacts")
    for index, item in enumerate(_rows(values), start=1):
        if isinstance(item, dict):
            uri = str(item.get("uri") or item.get("artifact_uri") or item.get("url") or "")
            kind = str(item.get("kind") or item.get("type") or "artifact")
            notes = str(item.get("notes") or item.get("description") or "")
        else:
            uri = str(item)
            kind = "artifact"
            notes = ""
        rows.append({"artifact_id": f"artifact_{index}", "kind": kind, "uri": uri, "notes": notes})
    if capture.get("evidence_uri") and not rows:
        rows.append({"artifact_id": "artifact_1", "kind": "measurement_log", "uri": str(capture.get("evidence_uri")), "notes": ""})
    return rows


def _connectors(capture: Dict[str, Any], root_provenance: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for index, item in enumerate(_rows(capture.get("connectors") or capture.get("pinout") or capture.get("headers")), start=1):
        row = item if isinstance(item, dict) else {"label": item}
        ref = str(row.get("ref") or row.get("id") or row.get("connector_id") or f"J{index}")
        connector_provenance = _provenance(row, root_provenance)
        pins = [
            _pin(pin, pin_index, connector_provenance)
            for pin_index, pin in enumerate(_pin_rows(row), start=1)
        ]
        rows.append(
            {
                "ref": ref,
                "label": str(row.get("label") or row.get("name") or ref),
                "kind": str(row.get("kind") or row.get("type") or "connector"),
                "pin_count": _safe_int(row.get("pin_count"), len(pins)),
                "status": str(row.get("status") or row.get("evidence_status") or ("verified" if _has_verified_pin([{"pins": pins}]) else "")),
                "source_capture_id": str(capture.get("capture_id") or capture.get("id") or ""),
                "provenance": connector_provenance,
                "pins": pins,
            }
        )
    return rows


def _reference_seed_connectors(reference_topology: Dict[str, Any], root_provenance: Dict[str, Any]) -> List[Dict[str, Any]]:
    connectors = []
    for index, item in enumerate(_rows((reference_topology or {}).get("connectors")), start=1):
        if not isinstance(item, dict):
            continue
        ref = str(item.get("ref") or item.get("id") or item.get("connector_id") or f"J{index}")
        pins = []
        for pin_index, raw_pin in enumerate(_pin_rows(item), start=1):
            pin = _pin(raw_pin, pin_index, root_provenance)
            pin["status"] = "needs_measurement"
            pin["reference_seed"] = True
            pins.append(pin)
        connectors.append(
            {
                "ref": ref,
                "label": str(item.get("label") or item.get("name") or ref),
                "kind": str(item.get("kind") or item.get("type") or "connector"),
                "pin_count": _safe_int(item.get("pin_count"), len(pins)),
                "status": "needs_measurement",
                "reference_seed": True,
                "reference_uri": _reference_uri({}, reference_topology),
                "provenance": root_provenance,
                "pins": pins,
            }
        )
    return connectors


def _connectors_from_board_evidence(board_evidence: Dict[str, Any], root_provenance: Dict[str, Any]) -> List[Dict[str, Any]]:
    connectors = []
    board_text = _board_identity_text(board_evidence)
    for index, item in enumerate(_rows(board_evidence.get("connectors") or board_evidence.get("headers")), start=1):
        row = item if isinstance(item, dict) else {"label": item}
        ref = str(row.get("ref") or row.get("id") or f"J{index}")
        pin_count = _safe_int(row.get("pin_count") or row.get("estimated_pin_count"), 0)
        seeded_pins = _visual_connector_seed_pins(row, board_text, root_provenance)
        pins = seeded_pins or [
            {
                "pin": str(pin),
                "label": str(pin),
                "net": "",
                "role": "",
                "status": "needs_measurement",
                "provenance": root_provenance,
            }
            for pin in range(1, pin_count + 1)
        ]
        connectors.append(
            {
                "ref": ref,
                "label": str(row.get("label") or row.get("name") or ref),
                "kind": str(row.get("kind") or row.get("type") or "connector"),
                "pin_count": pin_count or len(pins),
                "status": "needs_measurement",
                "vision_seed": True,
                "reference_seed": bool(seeded_pins),
                "reference_note": _visual_connector_reference_note(row, board_text) if seeded_pins else "",
                "provenance": root_provenance,
                "pins": pins,
            }
        )
    return connectors


def _visual_connector_seed_pins(row: Dict[str, Any], board_text: str, provenance: Dict[str, Any]) -> List[Dict[str, Any]]:
    text = _connector_text(row)
    if "gpio" in text and "raspberry pi" in board_text:
        return _pin_seed_rows(_raspberry_pi_gpio_40_pin_seed(), provenance)
    if "usb_c" in text or "usb-c" in text or "type_c" in text:
        return _pin_seed_rows(
            [
                ("VBUS", "VBUS", "power", 5.0, None, "USB-C VBUS logical power pin; confirm negotiated role/current before use."),
                ("GND", "GND", "ground", None, None, "USB-C ground logical pin."),
                ("D+", "USB_DP", "usb_dp", None, None, "USB 2.0 D+ logical signal; do not splice without impedance-aware harness."),
                ("D-", "USB_DM", "usb_dm", None, None, "USB 2.0 D- logical signal; do not splice without impedance-aware harness."),
                ("CC1", "CC1", "", None, None, "USB-C configuration channel; identify orientation and role before use."),
                ("CC2", "CC2", "", None, None, "USB-C configuration channel; identify orientation and role before use."),
            ],
            provenance,
        )
    if "usb" in text and ("port" in text or "connector" in text or "type_a" in text or "usb_a" in text):
        return _pin_seed_rows(
            [
                ("1", "VBUS", "power", 5.0, None, "USB VBUS; confirm source/sink direction and current limit."),
                ("2", "D-", "usb_dm", None, None, "USB D- differential signal."),
                ("3", "D+", "usb_dp", None, None, "USB D+ differential signal."),
                ("4", "GND", "ground", None, None, "USB ground."),
            ],
            provenance,
        )
    if "ethernet" in text or "rj45" in text:
        return _pin_seed_rows(
            [
                ("1", "BI_DA+", "", None, None, "RJ45 pair A positive; transformer/magnetics path must be confirmed."),
                ("2", "BI_DA-", "", None, None, "RJ45 pair A negative; transformer/magnetics path must be confirmed."),
                ("3", "BI_DB+", "", None, None, "RJ45 pair B positive; transformer/magnetics path must be confirmed."),
                ("4", "BI_DC+", "", None, None, "RJ45 pair C positive on gigabit interfaces."),
                ("5", "BI_DC-", "", None, None, "RJ45 pair C negative on gigabit interfaces."),
                ("6", "BI_DB-", "", None, None, "RJ45 pair B negative; transformer/magnetics path must be confirmed."),
                ("7", "BI_DD+", "", None, None, "RJ45 pair D positive on gigabit interfaces."),
                ("8", "BI_DD-", "", None, None, "RJ45 pair D negative on gigabit interfaces."),
            ],
            provenance,
        )
    if "hdmi" in text:
        return _pin_seed_rows(
            [
                ("1", "TMDS2+", "", None, None, "HDMI high-speed pair; use reference only."),
                ("2", "TMDS2_SHIELD", "", None, None, "HDMI shield/reference; use reference only."),
                ("3", "TMDS2-", "", None, None, "HDMI high-speed pair; use reference only."),
                ("4", "TMDS1+", "", None, None, "HDMI high-speed pair; use reference only."),
                ("5", "TMDS1_SHIELD", "", None, None, "HDMI shield/reference; use reference only."),
                ("6", "TMDS1-", "", None, None, "HDMI high-speed pair; use reference only."),
                ("7", "TMDS0+", "", None, None, "HDMI high-speed pair; use reference only."),
                ("8", "TMDS0_SHIELD", "", None, None, "HDMI shield/reference; use reference only."),
                ("9", "TMDS0-", "", None, None, "HDMI high-speed pair; use reference only."),
                ("10", "TMDS_CLK+", "", None, None, "HDMI high-speed clock pair; use reference only."),
                ("11", "TMDS_CLK_SHIELD", "", None, None, "HDMI shield/reference; use reference only."),
                ("12", "TMDS_CLK-", "", None, None, "HDMI high-speed clock pair; use reference only."),
                ("13", "CEC", "", None, None, "HDMI CEC signal; confirm before use."),
                ("14", "UTILITY", "", None, None, "Reserved/utility pin varies by implementation."),
                ("15", "SCL", "i2c_scl", None, 5.0, "HDMI DDC clock; confirm level and protection."),
                ("16", "SDA", "i2c_sda", None, 5.0, "HDMI DDC data; confirm level and protection."),
                ("17", "DDC_GND", "ground", None, None, "HDMI DDC/CEC ground."),
                ("18", "+5V", "power", 5.0, None, "HDMI +5V; do not use as project power without measurement."),
                ("19", "HPD", "", None, None, "HDMI hot-plug detect; confirm before use."),
            ],
            provenance,
        )
    return []


def _pin_seed_rows(seed: Sequence[tuple[str, str, str, float | None, float | None, str]], provenance: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for pin, net, role, voltage, logic_voltage, note in seed:
        rows.append(
            {
                "pin": str(pin),
                "label": str(net),
                "net": str(net),
                "role": str(role),
                "voltage": voltage,
                "logic_voltage": logic_voltage,
                "status": "needs_measurement",
                "reference_seed": True,
                "notes": note,
                "provenance": provenance,
            }
        )
    return rows


def _raspberry_pi_gpio_40_pin_seed() -> List[tuple[str, str, str, float | None, float | None, str]]:
    labels = [
        ("1", "3V3", "power", 3.3, None),
        ("2", "5V", "power", 5.0, None),
        ("3", "GPIO2_SDA1", "i2c_sda", None, 3.3),
        ("4", "5V", "power", 5.0, None),
        ("5", "GPIO3_SCL1", "i2c_scl", None, 3.3),
        ("6", "GND", "ground", None, None),
        ("7", "GPIO4", "logic_io", None, 3.3),
        ("8", "GPIO14_TXD0", "uart_tx", None, 3.3),
        ("9", "GND", "ground", None, None),
        ("10", "GPIO15_RXD0", "uart_rx", None, 3.3),
        ("11", "GPIO17", "logic_io", None, 3.3),
        ("12", "GPIO18_PWM0", "logic_io", None, 3.3),
        ("13", "GPIO27", "logic_io", None, 3.3),
        ("14", "GND", "ground", None, None),
        ("15", "GPIO22", "logic_io", None, 3.3),
        ("16", "GPIO23", "logic_io", None, 3.3),
        ("17", "3V3", "power", 3.3, None),
        ("18", "GPIO24", "logic_io", None, 3.3),
        ("19", "GPIO10_MOSI", "spi_mosi", None, 3.3),
        ("20", "GND", "ground", None, None),
        ("21", "GPIO9_MISO", "spi_miso", None, 3.3),
        ("22", "GPIO25", "logic_io", None, 3.3),
        ("23", "GPIO11_SCLK", "spi_sck", None, 3.3),
        ("24", "GPIO8_CE0", "spi_cs", None, 3.3),
        ("25", "GND", "ground", None, None),
        ("26", "GPIO7_CE1", "spi_cs", None, 3.3),
        ("27", "GPIO0_ID_SD", "i2c_sda", None, 3.3),
        ("28", "GPIO1_ID_SC", "i2c_scl", None, 3.3),
        ("29", "GPIO5", "logic_io", None, 3.3),
        ("30", "GND", "ground", None, None),
        ("31", "GPIO6", "logic_io", None, 3.3),
        ("32", "GPIO12_PWM0", "logic_io", None, 3.3),
        ("33", "GPIO13_PWM1", "logic_io", None, 3.3),
        ("34", "GND", "ground", None, None),
        ("35", "GPIO19_PCM_FS", "logic_io", None, 3.3),
        ("36", "GPIO16", "logic_io", None, 3.3),
        ("37", "GPIO26", "logic_io", None, 3.3),
        ("38", "GPIO20_PCM_DIN", "logic_io", None, 3.3),
        ("39", "GND", "ground", None, None),
        ("40", "GPIO21_PCM_DOUT", "logic_io", None, 3.3),
    ]
    return [(pin, net, role, voltage, logic, "Raspberry Pi 40-pin GPIO reference seed; confirm physical orientation and voltage before use.") for pin, net, role, voltage, logic in labels]


def _visual_connector_reference_note(row: Dict[str, Any], board_text: str) -> str:
    text = _connector_text(row)
    if "gpio" in text and "raspberry pi" in board_text:
        return "Raspberry Pi 40-pin GPIO reference seed; visual/reference only until measured."
    if "usb" in text:
        return "Common USB logical pin reference seed; visual/reference only until measured."
    if "ethernet" in text or "rj45" in text:
        return "Common RJ45 logical pair reference seed; visual/reference only until measured."
    if "hdmi" in text:
        return "Common HDMI pin reference seed; visual/reference only until measured."
    return "Visual connector reference seed; confirm on the physical board before use."


def _connector_text(row: Dict[str, Any]) -> str:
    return " ".join(str(row.get(key) or "") for key in ["ref", "id", "label", "name", "kind", "type"]).lower().replace(" ", "_")


def _board_identity_text(board_evidence: Dict[str, Any]) -> str:
    chunks: List[str] = []
    for key in ["components", "markings", "regions"]:
        for row in _rows(board_evidence.get(key)):
            if not isinstance(row, dict):
                chunks.append(str(row))
                continue
            chunks.extend(str(row.get(field) or "") for field in ["label", "name", "marking", "text", "visible_text", "kind"])
            chunks.extend(str(item) for item in row.get("markings") or [] if str(item).strip())
    return " ".join(chunks).lower()


def _pin(item: Any, index: int, provenance: Dict[str, Any]) -> Dict[str, Any]:
    row = item if isinstance(item, dict) else {"pin": index, "label": item}
    return {
        "pin": str(row.get("pin") or row.get("number") or row.get("pin_number") or index),
        "label": str(row.get("label") or row.get("name") or row.get("net") or row.get("pin") or index),
        "net": str(row.get("net") or row.get("net_id") or row.get("node") or row.get("label") or ""),
        "role": str(row.get("role") or row.get("function") or row.get("kind") or ""),
        "voltage": row.get("voltage", row.get("nominal_v", row.get("measured_voltage"))),
        "logic_voltage": row.get("logic_voltage", row.get("idle_voltage", row.get("measured_logic_voltage"))),
        "status": str(row.get("status") or row.get("evidence_status") or ""),
        "provenance": _provenance(row, provenance),
    }


def _observations(
    capture: Dict[str, Any],
    root_provenance: Dict[str, Any],
    instruments: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    raw_rows: List[Any] = []
    for key in ["measurements", "observations", "readings", "tests"]:
        raw_rows.extend(_rows(capture.get(key)))
    evidence = capture.get("evidence") if isinstance(capture.get("evidence"), dict) else {}
    raw_rows.extend(_rows(evidence.get("measurements") or evidence.get("observations")))

    rows = []
    for index, item in enumerate(raw_rows, start=1):
        source = item if isinstance(item, dict) else {"value": item}
        if not _has_recorded_observation(source):
            continue
        kind = _measurement_kind(source)
        if kind not in OBSERVATION_KINDS:
            continue
        provenance = _observation_provenance(source, root_provenance, instruments)
        target = str(source.get("target") or source.get("prompt") or source.get("net") or source.get("pin") or "").strip()
        if not target and (source.get("from") or source.get("to")):
            target = f"{source.get('from')} to {source.get('to')}"
        rows.append(
            {
                "observation_id": str(source.get("observation_id") or source.get("measurement_id") or source.get("id") or f"{kind}_{index}"),
                "kind": kind,
                "target": target,
                "from": str(source.get("from") or source.get("a") or source.get("node_a") or ""),
                "to": str(source.get("to") or source.get("b") or source.get("node_b") or ""),
                "value": source.get("value", source.get("reading", source.get("result", ""))),
                "unit": str(source.get("unit") or source.get("units") or _default_unit(kind)),
                "status": str(source.get("status") or source.get("result") or ""),
                "notes": str(source.get("notes") or source.get("summary") or source.get("purpose") or ""),
                **provenance,
            }
        )
    return rows


def _observation_provenance(
    row: Dict[str, Any],
    root_provenance: Dict[str, Any],
    instruments: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    instrument_ref = str(row.get("instrument_id") or row.get("instrument_ref") or "").strip()
    instrument = next((item for item in instruments if item.get("instrument_id") == instrument_ref), {})
    base = {
        **root_provenance,
        "instrument_id": instrument_ref or root_provenance.get("instrument_id", ""),
        "instrument_type": instrument.get("instrument_type") or root_provenance.get("instrument_type", ""),
        "calibration_status": instrument.get("calibration_status") or root_provenance.get("calibration_status", ""),
    }
    return _provenance(row, base)


def _measurement_kind(row: Dict[str, Any]) -> str:
    text = " ".join(
        str(row.get(key) or "")
        for key in ["kind", "type", "measurement_type", "target", "prompt", "notes"]
    ).lower()
    if any(term in text for term in ["thermal", "temperature", "heat"]):
        return "thermal"
    if any(term in text for term in ["current", "draw", "ma", "amp"]):
        return "current"
    if any(term in text for term in ["voltage", "logic", "polarity", "vcc", "rail"]):
        return "voltage"
    if any(term in text for term in ["resistance", "ohm", "no-short", "no short", "short"]):
        return "resistance"
    if any(term in text for term in ["continuity", "ground", "shared common"]):
        return "continuity"
    return str(row.get("kind") or row.get("type") or "").strip().lower()


def _has_recorded_observation(row: Dict[str, Any]) -> bool:
    return any(
        str(row.get(key) or "").strip()
        for key in ["value", "reading", "result", "status", "passed", "failed"]
    )


def _merge_topology_evidence(existing: Any, generated: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(existing, dict) or not existing:
        return generated

    merged = dict(existing)
    for key, value in generated.items():
        if key in {"connectors", "continuity", "resistance", "voltage", "current", "thermal"}:
            continue
        if value not in (None, "", [], {}):
            merged[key] = value
    merged["schema_version"] = TOPOLOGY_SCHEMA_VERSION
    merged["source"] = generated.get("source") or existing.get("source") or SCHEMA_VERSION
    merged["source_type"] = generated.get("source_type") or existing.get("source_type") or "bench_measurement_capture"
    for key in ["connectors", "continuity", "resistance", "voltage", "current", "thermal"]:
        merged[key] = _dedupe_rows(
            _rows(existing.get(key)) + _rows(generated.get(key)),
            key_fields=_topology_key_fields(key),
        )
    return merged


def _topology_is_reference_only(value: Any) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    text = " ".join(
        str(item or "")
        for item in [
            value.get("source"),
            value.get("source_type"),
            value.get("evidence_type"),
            value.get("reference_uri"),
            value.get("source_uri"),
        ]
    ).lower()
    return any(term in text for term in ["public_reference", "reference_topology", "public schematic", "datasheet", "official_pinout"])


def _capture_summary(capture: Dict[str, Any], topology: Dict[str, Any]) -> Dict[str, Any]:
    summary = topology.get("capture_summary") if isinstance(topology.get("capture_summary"), dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "capture_id": str(capture.get("capture_id") or capture.get("id") or ""),
        "source_type": topology.get("source_type"),
        "connector_count": summary.get("connector_count", 0),
        "observation_count": summary.get("observation_count", 0),
        "verified_pin_count": summary.get("verified_pin_count", 0),
        "trusted_root_provenance": bool(summary.get("trusted_root_provenance")),
        "actionable_topology": _has_actionable_topology(topology),
    }


def _has_actionable_topology(topology: Dict[str, Any]) -> bool:
    if topology.get("source_type") != "bench_measurement_capture":
        return False
    return bool(
        _has_verified_pin(_rows(topology.get("connectors")))
        or any(_rows(topology.get(key)) for key in ["continuity", "resistance", "voltage", "current", "thermal"])
    )


def _has_verified_pin(connectors: Sequence[Dict[str, Any]]) -> bool:
    return _verified_pin_count(connectors) > 0


def _verified_pin_count(connectors: Sequence[Dict[str, Any]]) -> int:
    return len(
        [
            pin
            for connector in connectors
            if isinstance(connector, dict)
            for pin in _rows(connector.get("pins"))
            if str(pin.get("status") or "").strip().lower() in PASS_STATUSES
        ]
    )


def _required_observations(connectors: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    roles = {
        _semantic_pin_role(pin)
        for connector in connectors
        if isinstance(connector, dict)
        for pin in connector.get("pins") or []
    }
    rows = [
        _measurement_template("resistance", "power to ground no-short", "Unpowered resistance check between supply and ground."),
        _measurement_template("continuity", "connector ground to exposed ground", "Confirm common ground reference."),
        _measurement_template("voltage", "input voltage and polarity", "Measure supply rail voltage and polarity under current limit."),
        _measurement_template("current", "current draw under current-limited supply", "Record first-power current at a safe current limit."),
        _measurement_template("thermal", "thermal behavior after first power", "Record no abnormal heating after first power."),
    ]
    if roles & {"uart_tx", "uart_rx", "i2c_sda", "i2c_scl", "spi_mosi", "spi_miso", "spi_sck", "spi_cs", "logic_io"}:
        rows.append(_measurement_template("voltage", "logic high voltage", "Measure the reused signal voltage domain."))
    rows.extend(_connector_specific_observation_templates(connectors))
    return _dedupe_rows(rows, key_fields=("kind", "target"))


def _connector_specific_observation_templates(connectors: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for connector in connectors:
        if not isinstance(connector, dict):
            continue
        pins = [pin for pin in _rows(connector.get("pins")) if isinstance(pin, dict)]
        if not pins:
            continue
        ref = str(connector.get("ref") or connector.get("id") or connector.get("label") or "connector")
        label = str(connector.get("label") or ref)
        name = f"{label} ({ref})"
        connector_text = _connector_text(connector)
        usb_connector = "usb" in connector_text or "type_c" in connector_text
        power = [pin for pin in pins if _semantic_pin_role(pin) == "power"]
        ground = [pin for pin in pins if _semantic_pin_role(pin) == "ground"]
        logic = [
            pin
            for pin in pins
            if _semantic_pin_role(pin)
            in {"uart_tx", "uart_rx", "uart_dtr", "uart_cts", "i2c_sda", "i2c_scl", "spi_mosi", "spi_miso", "spi_sck", "spi_cs", "logic_io"}
        ]
        usb = [
            pin
            for pin in pins
            if usb_connector and (_semantic_pin_role(pin) in {"usb_dp", "usb_dm"} or "usb" in _pin_text(pin))
        ]
        high_speed = [pin for pin in pins if any(term in _pin_text(pin) for term in ["tmds", "bi_d", "usb_dp", "usb_dm", "d+", "d-"])]

        if connector.get("reference_seed") or connector.get("vision_seed"):
            rows.append(
                _measurement_template(
                    "continuity",
                    f"{name} pin-1/orientation confirmation",
                    "Mark physical pin 1/orientation in a close-up photo before trusting any seeded pin label.",
                )
            )
        if power and ground:
            rows.append(
                _measurement_template(
                    "resistance",
                    f"{name} supply-to-ground no-short: {_pin_summary(power)} vs {_pin_summary(ground)}",
                    "Unpowered check from each candidate supply pin to confirmed ground before first power.",
                )
            )
            rows.append(
                _measurement_template(
                    "voltage",
                    f"{name} supply voltage and polarity: {_pin_summary(power)}",
                    "Measure supply pins under current limit and confirm source/sink direction before reuse.",
                )
            )
        if ground:
            rows.append(
                _measurement_template(
                    "continuity",
                    f"{name} ground reference continuity: {_pin_summary(ground)}",
                    "Confirm seeded ground pins to exposed ground, connector shell where applicable, and target common reference.",
                )
            )
        if logic:
            rows.append(
                _measurement_template(
                    "voltage",
                    f"{name} logic voltage domain: {_pin_summary(logic, max_count=10)}",
                    "Measure idle/high logic level before connecting to another controller or adapter.",
                )
            )
            rows.append(
                _measurement_template(
                    "continuity",
                    f"{name} signal pin continuity map: {_pin_summary(logic, max_count=10)}",
                    "Map each reusable signal to a labeled pad, connector, or target net before splicing.",
                )
            )
        if usb:
            rows.append(
                _measurement_template(
                    "continuity",
                    f"{name} USB data pair protection/path confirmation: {_pin_summary(usb)}",
                    "Confirm D+/D- routing through protection/connector path; do not hand-wire high-speed USB casually.",
                )
            )
        if high_speed:
            rows.append(
                _measurement_template(
                    "continuity",
                    f"{name} high-speed/shield reference check: {_pin_summary(high_speed)}",
                    "Treat high-speed pairs as reference-only unless connector, shield, and protection path are confirmed.",
                )
            )
    return rows


def _semantic_pin_role(pin: Dict[str, Any]) -> str:
    text = _pin_text(pin)
    role = str(pin.get("role") or "").strip().lower()
    if any(term in text for term in ["gnd", "ground", "ddc_gnd"]):
        return "ground"
    if any(term in text for term in ["vbus", "vcc", "+5v", "5v", "3v3", "3.3v", "supply", "power"]):
        return "power"
    if any(term in text for term in ["uart_tx", "txo", "txd"]):
        return "uart_tx"
    if any(term in text for term in ["uart_rx", "rxi", "rxd"]):
        return "uart_rx"
    if any(term in text for term in ["dtr"]):
        return "uart_dtr"
    if any(term in text for term in ["cts"]):
        return "uart_cts"
    if any(term in text for term in ["i2c_sda", "sda"]):
        return "i2c_sda"
    if any(term in text for term in ["i2c_scl", "scl"]):
        return "i2c_scl"
    if any(term in text for term in ["spi_mosi", "mosi"]):
        return "spi_mosi"
    if any(term in text for term in ["spi_miso", "miso"]):
        return "spi_miso"
    if any(term in text for term in ["spi_sck", "sclk"]):
        return "spi_sck"
    if any(term in text for term in ["spi_cs", "ce0", "ce1"]):
        return "spi_cs"
    if any(term in text for term in ["usb_dp", "d+"]):
        return "usb_dp"
    if any(term in text for term in ["usb_dm", "d-"]):
        return "usb_dm"
    if any(term in text for term in ["gpio", "logic_io", "digital_io"]):
        return "logic_io"
    return role


def _pin_text(pin: Dict[str, Any]) -> str:
    return " ".join(str(pin.get(key) or "") for key in ["pin", "label", "net", "role", "notes"]).strip().lower()


def _pin_summary(pins: Sequence[Dict[str, Any]], *, max_count: int = 8) -> str:
    tokens = []
    for pin in pins[:max_count]:
        pin_number = str(pin.get("pin") or "?")
        name = str(pin.get("net") or pin.get("label") or "").strip()
        tokens.append(f"{pin_number}:{name}" if name else pin_number)
    if len(pins) > max_count:
        tokens.append(f"+{len(pins) - max_count} more")
    return ", ".join(tokens)


def _measurement_template(kind: str, target: str, notes: str) -> Dict[str, Any]:
    return {
        "kind": kind,
        "target": target,
        "value": "",
        "unit": _default_unit(kind),
        "status": "",
        "notes": notes,
        "instrument_id": "",
        "evidence_uri": "",
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


def _reference_uri(capture: Dict[str, Any], reference_topology: Dict[str, Any] | None) -> str:
    if capture.get("reference_uri"):
        return str(capture.get("reference_uri"))
    if isinstance(reference_topology, dict):
        return str(reference_topology.get("reference_uri") or reference_topology.get("source_uri") or "")
    return ""


def _first_artifact_uri(artifacts: Sequence[Dict[str, Any]]) -> str:
    for artifact in artifacts:
        uri = str(artifact.get("uri") or artifact.get("artifact_uri") or "")
        if uri:
            return uri
    return ""


def _provenance(row: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    nested = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    result = {}
    for key in TRUST_KEYS:
        result[key] = row.get(key) or nested.get(key) or fallback.get(key) or ""
    return result


def _default_unit(kind: str) -> str:
    return {"continuity": "ohm", "resistance": "ohm", "voltage": "V", "current": "A", "thermal": "C"}.get(kind, "")


def _rows(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _topology_key_fields(kind: str) -> Sequence[str]:
    if kind == "connectors":
        return ("ref", "label")
    return ("observation_id", "target", "value", "unit")


def _dedupe_rows(rows: Iterable[Any], *, key_fields: Sequence[str]) -> List[Dict[str, Any]]:
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
