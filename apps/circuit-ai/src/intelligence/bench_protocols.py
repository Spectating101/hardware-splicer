"""Authority-grade bench protocol templates for arbitrary board reuse.

The arbitrary-board workflow can infer a likely function from vision, topology,
inventory, or part markings. This module turns that inferred function into a
structured bench contract: equipment, steps, pass criteria, stop conditions, and
release artifacts. It is intentionally deterministic; model output may request a
protocol pack, but it cannot weaken the pack or clear its checks.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence


SCHEMA_VERSION = "bench_protocol_pack.v1"

BASELINE_EQUIPMENT = [
    "current-limited bench supply or protected USB source",
    "calibrated DMM",
    "thermal probe or thermal camera",
    "magnification and board photos",
    "ESD-safe leads or fixture harness",
]

BASELINE_CONTROLS = [
    "Keep unknown boards unpowered until no-short and polarity checks pass.",
    "Use current limits for every first-power or load test.",
    "Record instrument, operator, timestamp, and artifact URI for each passing measurement.",
    "Stop on smoke, odor, abnormal heat, unexpected current, shorted rail, or unstable output.",
]

BASELINE_CATEGORIES = ["resistance", "continuity", "voltage", "current", "thermal"]


FUNCTION_PROTOCOLS: Dict[str, Dict[str, Any]] = {
    "usb_serial_debug_bridge": {
        "title": "USB/UART debug bridge reuse",
        "equipment": ["logic analyzer or known-good UART target", "loopback jumper", "USB current monitor"],
        "steps": [
            ("no_short", "resistance", "Measure VCC/GND and USB VBUS/GND unpowered resistance.", "No dead short."),
            ("pinout", "continuity", "Map GND, VCC, TX, RX, DTR/RTS if present.", "Used pins have explicit roles."),
            ("logic_voltage", "voltage", "Measure idle TX/RX voltage under current-limited power.", "Logic voltage matches target domain."),
            ("loopback", "logic", "Run loopback or safe serial capture before target connection.", "Stable serial activity is observed."),
            ("thermal", "thermal", "Observe bridge IC and regulator during serial activity.", "No abnormal hot spot."),
        ],
        "acceptance": [
            "GND, TX, RX, and logic voltage are measured.",
            "Loopback or safe serial capture passes.",
            "Current and thermal behavior remain normal.",
        ],
        "stop_conditions": ["unknown logic voltage", "unstable USB enumeration", "overcurrent", "abnormal bridge/regulator heat"],
        "release_artifacts": ["pinout photo", "loopback/capture log", "current/thermal measurement artifacts"],
    },
    "sensor_or_adc_module": {
        "title": "Sensor or ADC module reuse",
        "equipment": ["pullup-aware host controller", "logic analyzer or bus scanner", "known reference stimulus if applicable"],
        "steps": [
            ("no_short", "resistance", "Measure supply-to-ground and bus-line shorts unpowered.", "No dead short or stuck bus line."),
            ("pinout", "continuity", "Map power, ground, SDA/SCL or SPI pins, address/select pins.", "Connector map is explicit."),
            ("supply", "voltage", "Power at the measured voltage domain through a current limit.", "Supply is stable and in range."),
            ("bus_scan", "logic", "Run low-speed I2C/SPI scan or read-only probe.", "Device responds without excessive current."),
            ("reading", "functional", "Record a stable reading or known stimulus response.", "Output is plausible and repeatable."),
        ],
        "acceptance": [
            "Supply and bus voltage domain are known.",
            "Bus scan or read-only probe passes.",
            "A stable reading or stimulus response is recorded.",
        ],
        "stop_conditions": ["stuck bus line", "wrong voltage domain", "excessive current", "unstable sensor output"],
        "release_artifacts": ["connector map", "bus scan log", "sample reading log"],
    },
    "load_or_motor_driver": {
        "title": "Protected load or motor driver reuse",
        "equipment": ["dummy load", "fuse or resettable protection", "bench supply sized for load", "thermal probe"],
        "steps": [
            ("no_short", "resistance", "Check supply rails and output switches for shorts.", "No rail or output switch is shorted."),
            ("pinout", "continuity", "Map supply, ground, input controls, and load terminals.", "Load path and control pins are explicit."),
            ("gate_drive", "voltage", "Measure input/control voltage domain before driving outputs.", "Control voltage is compatible."),
            ("dummy_load", "load", "Switch a dummy load under current limit before the real load.", "Output switches correctly within limit."),
            ("thermal", "thermal", "Observe driver and protection parts under dummy load.", "Thermal behavior is normal."),
        ],
        "acceptance": [
            "Output is proven with dummy load before real load.",
            "Flyback/protection path is identified or external protection is added.",
            "Current and thermal behavior pass under expected load envelope.",
        ],
        "stop_conditions": ["shorted output", "missing load protection", "unexpected current", "driver hot spot"],
        "release_artifacts": ["dummy-load test log", "load-current measurement", "thermal artifact", "protection note"],
    },
    "power_distribution_or_regulator": {
        "title": "Power stage reuse",
        "equipment": ["programmable or current-limited supply", "dummy load", "DMM", "thermal probe"],
        "steps": [
            ("no_short", "resistance", "Measure input/output rail-to-ground resistance.", "No rail is a dead short."),
            ("polarity", "continuity", "Confirm input polarity, output polarity, and ground reference.", "Polarity and reference are explicit."),
            ("output_voltage", "voltage", "Power through a current limit and measure output voltage.", "Output voltage is stable and expected."),
            ("load_test", "current", "Apply dummy load in steps and record current/voltage sag.", "Voltage remains within usable range."),
            ("thermal", "thermal", "Observe regulator, diode/switch, and inductor/caps during load.", "No abnormal heat."),
        ],
        "acceptance": [
            "Output voltage and polarity are measured.",
            "Dummy-load current test passes.",
            "Thermal behavior remains normal.",
        ],
        "stop_conditions": ["wrong output voltage", "large voltage sag", "overcurrent", "regulator/inductor hot spot"],
        "release_artifacts": ["voltage/current sweep", "thermal artifact", "output pinout photo"],
    },
    "controller_module": {
        "title": "Controller or embedded compute reuse",
        "equipment": ["current-limited supply", "serial console or debugger", "logic analyzer", "known-safe I/O harness"],
        "steps": [
            ("no_short", "resistance", "Measure rails and exposed I/O against ground before power.", "No dead short."),
            ("rails", "voltage", "Power through current limit and measure rails.", "Rails match expected domain."),
            ("boot", "current", "Record boot/current behavior and reset state.", "Boot or idle state is stable."),
            ("io_domain", "logic", "Measure I/O voltage before attaching external devices.", "I/O voltage matches planned interface."),
            ("safe_io", "functional", "Exercise one protected input/output or console action.", "Known-safe interaction works."),
        ],
        "acceptance": [
            "Rails and boot/current behavior are stable.",
            "I/O voltage is measured.",
            "Unknown firmware behavior is bounded before driving loads.",
        ],
        "stop_conditions": ["boot overcurrent", "unknown high-side drive to external load", "wrong I/O voltage", "hot MCU/regulator"],
        "release_artifacts": ["rail/current log", "console/debug log", "I/O voltage table"],
    },
    "wireless_or_rf_module": {
        "title": "Wireless, RF, CAN, or differential network interface reuse",
        "equipment": ["current-limited supply", "host interface", "known antenna or bus termination", "logic analyzer or bus adapter"],
        "steps": [
            ("no_short", "resistance", "Measure supply, RF/bus pins, and shield/reference paths unpowered.", "No dead short."),
            ("pinout", "continuity", "Map host interface, bus pair, antenna/reference, and ground.", "Entry points are explicit."),
            ("supply", "voltage", "Power through a current limit and measure host/bus voltage domain.", "Supply and logic domain are compatible."),
            ("termination", "continuity", "Verify CAN/RS-485 termination/bias or RF antenna/load path when applicable.", "Bus/RF path is bounded."),
            ("link_test", "logic", "Run low-power scan, advertisement, bus capture, or loopback.", "Communication evidence is observed."),
        ],
        "acceptance": [
            "Host voltage and bus/RF path are measured.",
            "Termination, bias, or antenna/load condition is recorded.",
            "A scan, capture, loopback, or advertisement artifact exists.",
        ],
        "stop_conditions": ["ground offset risk", "wrong termination", "missing antenna/load", "overcurrent", "hot transceiver"],
        "release_artifacts": ["bus/RF pinout", "termination/bias note", "capture or scan log"],
    },
    "display_or_ui_module": {
        "title": "Display, indicator, or UI harness reuse",
        "equipment": ["current-limited supply", "protected controller I/O", "series resistors", "logic analyzer if bus-driven"],
        "steps": [
            ("no_short", "resistance", "Measure supply and UI signal lines for shorts.", "No dead short."),
            ("pinout", "continuity", "Map power, ground, LEDs/buttons/display bus pins.", "Pin roles are explicit."),
            ("current_limit", "current", "Verify current limiting for LEDs/backlight/inputs.", "Current stays inside safe limits."),
            ("drive_test", "logic", "Drive through protected I/O or bus at low speed.", "UI responds predictably."),
            ("thermal", "thermal", "Observe LEDs/backlight/driver IC during test.", "No abnormal heat."),
        ],
        "acceptance": [
            "Pin map and current limits are recorded.",
            "Protected I/O or bus test passes.",
            "No stuck line, overcurrent, or hot spot remains.",
        ],
        "stop_conditions": ["unknown LED current path", "wrong display voltage", "stuck bus", "backlight overcurrent"],
        "release_artifacts": ["pin map", "protected-drive test log", "current-limit evidence"],
    },
    "audio_or_alert_module": {
        "title": "Audio or alert output reuse",
        "equipment": ["dummy speaker/load", "current-limited supply", "low-level signal source", "thermal probe"],
        "steps": [
            ("no_short", "resistance", "Measure supply and output load path for shorts.", "No dead short."),
            ("load_impedance", "resistance", "Measure speaker/load impedance before connecting amplifier.", "Load impedance is safe."),
            ("idle_current", "current", "Power through current limit and measure idle current.", "Idle current is normal."),
            ("low_level_output", "load", "Run low-level audio/alert output into dummy load.", "Output works without overcurrent."),
            ("thermal", "thermal", "Observe amplifier and load path during output.", "No abnormal heat."),
        ],
        "acceptance": [
            "Load impedance and idle current are measured.",
            "Low-level output passes on dummy load.",
            "Thermal behavior remains normal.",
        ],
        "stop_conditions": ["shorted speaker/load", "amplifier overcurrent", "wrong supply", "thermal runaway"],
        "release_artifacts": ["impedance/current log", "output test artifact", "thermal artifact"],
    },
    "battery_or_charger": {
        "title": "Battery or charger safety triage",
        "equipment": ["battery-safe containment", "chemistry/cell-count reference", "specialist battery workflow"],
        "steps": [
            ("identity", "review", "Identify chemistry, cell count, pack topology, and protection path.", "Battery identity is explicit."),
            ("protection", "review", "Verify BMS/protection and charge/discharge boundary.", "Protection is documented."),
            ("containment", "thermal", "Verify enclosure, strain relief, and thermal containment.", "Containment is acceptable."),
        ],
        "acceptance": ["Specialist authority is attached before charge, load, or splice."],
        "stop_conditions": ["swollen/damaged cell", "unknown chemistry", "bypassed BMS", "missing containment"],
        "release_artifacts": ["specialist authority record", "chemistry/cell-count evidence", "containment evidence"],
        "specialist_only": True,
    },
}


def build_bench_protocol_pack(
    *,
    primary_function_id: str,
    capabilities: Sequence[Any] | None = None,
    matched_parts: Sequence[Dict[str, Any]] | None = None,
    authority_status: str = "unavailable",
) -> Dict[str, Any]:
    """Build a deterministic protocol pack for the inferred board function."""

    primary = str(primary_function_id or "unknown_low_voltage_module")
    template = FUNCTION_PROTOCOLS.get(primary) or _unknown_template()
    capabilities_list = _dedupe(str(cap) for cap in capabilities or [])
    matched = [row for row in matched_parts or [] if isinstance(row, dict)]
    steps = _protocol_steps(primary, template)
    required_categories = _required_categories(steps)
    specialist_only = bool(template.get("specialist_only"))
    return {
        "schema_version": SCHEMA_VERSION,
        "primary_function_id": primary,
        "title": str(template.get("title") or "Arbitrary board bench protocol"),
        "authority_status": authority_status,
        "specialist_only": specialist_only,
        "required_equipment": _dedupe([*BASELINE_EQUIPMENT, *(template.get("equipment") or [])])[:16],
        "setup_controls": _dedupe([*BASELINE_CONTROLS, *_part_specific_controls(matched)])[:16],
        "required_measurement_categories": required_categories,
        "step_count": len(steps),
        "steps": steps,
        "pass_fail_criteria": {
            "acceptance": _dedupe(template.get("acceptance") or [])[:12],
            "stop_conditions": _dedupe(template.get("stop_conditions") or [])[:12],
        },
        "release_artifacts_required": _dedupe(
            [
                *(template.get("release_artifacts") or []),
                "measurement artifacts with instrument/operator/timestamp provenance",
                "terminal outcome record",
                "production release manifest for any release claim",
            ]
        )[:14],
        "measurement_record_template": _measurement_record_template(required_categories),
        "outcome_record_template": {
            "decision": "reused|repaired|built|failed|unsafe_hold",
            "output_function_verified": True,
            "first_power_result": "pass",
            "thermal_result": "normal",
            "measurements_recorded": True,
            "selected_resource_ids_used": [],
            "evidence_uri": "session://...",
        },
        "matched_part_refs": [
            {
                "part_id": row.get("part_id"),
                "canonical_part": row.get("canonical_part"),
                "family": row.get("family"),
                "verification_required": row.get("verification_required") or [],
            }
            for row in matched[:8]
        ],
        "capabilities": capabilities_list,
        "release_boundary": (
            "This pack defines what must be proven for a scoped low-voltage release. It cannot authorize "
            "battery, mains, high-voltage, laser, or unbounded reuse without a separate specialist authority."
            if not specialist_only
            else "Specialist-only pack: normal production repair authority must stay blocked until specialist evidence is attached."
        ),
        "model_policy": {
            "llm_can_request_additional_steps": True,
            "llm_can_clear_required_steps": False,
            "deterministic_authority_gates_remain_final": True,
        },
    }


def _protocol_steps(primary: str, template: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for index, raw in enumerate(template.get("steps") or [], start=1):
        step_id, category, action, expected = raw
        rows.append(
            {
                "step_id": f"bench_{index}",
                "lane_id": str(step_id),
                "category": str(category),
                "action": str(action),
                "expected_result": str(expected),
                "evidence_required": [
                    f"{category} measurement record" if category not in {"review", "functional"} else f"{category} evidence record",
                    "instrument/operator/timestamp metadata",
                    "artifact_uri or evidence_uri",
                ],
                "required_before": _required_before(primary, str(category)),
                "source": "bench_protocol_pack",
            }
        )
    return rows


def _required_before(primary: str, category: str) -> str:
    if primary == "battery_or_charger":
        return "specialist_authority"
    if category in {"resistance", "continuity", "review"}:
        return "first_power"
    if category in {"voltage", "current", "thermal"}:
        return "splice_release"
    if category in {"logic", "load", "functional"}:
        return "terminal_outcome"
    return "demo_or_release"


def _required_categories(steps: Sequence[Dict[str, Any]]) -> List[str]:
    categories = _dedupe([*BASELINE_CATEGORIES, *(step.get("category") for step in steps)])
    return categories[:12]


def _measurement_record_template(categories: Sequence[str]) -> List[Dict[str, Any]]:
    return [
        {
            "type": category,
            "target": "<rail|pin|load|interface>",
            "value": "<measured value or pass/fail>",
            "unit": "<unit when numeric>",
            "status": "pass",
            "instrument_id": "<instrument id>",
            "instrument_type": "<instrument type>",
            "calibration_status": "valid",
            "recorded_at": "<ISO-8601 timestamp>",
            "operator_id": "<operator id>",
            "evidence_uri": "session://...",
        }
        for category in categories
    ]


def _part_specific_controls(matched_parts: Sequence[Dict[str, Any]]) -> List[str]:
    controls: List[str] = []
    for row in matched_parts[:6]:
        part = str(row.get("canonical_part") or row.get("family") or "").strip()
        verification = _dedupe(row.get("verification_required") or [])
        if part and verification:
            controls.append(f"For {part}, explicitly verify: {', '.join(verification[:4])}.")
    return controls


def _unknown_template() -> Dict[str, Any]:
    return {
        "title": "Unknown low-voltage board baseline protocol",
        "equipment": ["continuity tester", "current-limited supply", "labeling tape"],
        "steps": [
            ("visual_identity", "review", "Photograph front/back, labels, connectors, and damage before testing.", "Visual record is complete."),
            ("no_short", "resistance", "Measure every obvious power rail or connector power pin to ground.", "No dead short."),
            ("pinout", "continuity", "Map connector ground/reference and likely power pins.", "Baseline connector roles are known."),
            ("first_power", "voltage", "Power only through a current limit after no-short passes.", "Voltage/current behavior is bounded."),
            ("thermal", "thermal", "Observe thermal behavior during first-power.", "No abnormal hot spot."),
        ],
        "acceptance": [
            "Board identity is narrowed to a reusable function.",
            "No-short, pinout, voltage/current, and thermal evidence pass.",
            "Terminal function outcome is recorded before release.",
        ],
        "stop_conditions": ["unknown energy storage", "mains/high-voltage signs", "dead short", "abnormal current or heat"],
        "release_artifacts": ["front/back photos", "connector map", "baseline measurement log"],
    }


def _dedupe(items: Iterable[Any]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out
