"""DIY project engineering planner for hardware builds.

This layer turns "I want to build X" into an engineering work package:
functional requirements, resource strategy, architecture blocks, build stages,
and authority gates. It does not authorize wiring, power, or release by itself.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from src.intelligence.resource_strategy import ResourceStrategyPlanner


SCHEMA_VERSION = "diy_project_engineering_plan.v1"

DIY_TRIGGER_KEYS = {
    "diy_project",
    "project_brief",
    "build_goal",
    "target_build",
    "target_device",
    "desired_device",
}

BUILD_VERBS = {
    "build",
    "make",
    "create",
    "assemble",
    "prototype",
    "engineer",
    "design",
    "diy",
}

NON_BUILD_INTENT_WORDS = {
    "inspect",
    "identify",
    "understand",
    "photographed",
    "photo",
    "reuse",
    "repair",
    "release",
    "salvage",
}

CAPABILITY_ORDER = [
    "controller",
    "wireless",
    "sensor_or_adc",
    "camera_or_vision",
    "display_or_ui",
    "switch_or_button",
    "actuator_driver",
    "motor_or_load",
    "fan_or_pump",
    "led_or_light",
    "power",
    "connector",
    "protection",
    "mechanical_motion",
    "enclosure_candidate",
    "usb_serial",
    "speaker_or_audio",
]

PROFILE_LIBRARY = [
    {
        "profile_id": "automatic_plant_watering",
        "label": "automatic plant watering system",
        "terms": {"plant", "plants", "herb", "herbs", "watering", "waters", "water", "irrigation", "irrigate", "irrigator", "soil", "moisture", "pump"},
        "phrases": ["plant watering", "soil moisture", "automatic watering", "automatic irrigator"],
        "required_capabilities": [
            "controller",
            "sensor_or_adc",
            "actuator_driver",
            "motor_or_load",
            "fan_or_pump",
            "power",
            "connector",
            "protection",
        ],
        "optional_capabilities": ["wireless", "display_or_ui", "switch_or_button", "enclosure_candidate"],
        "mapped_build_id": "smart_relay_box",
        "blocks": [
            ("controller", "Control timing, threshold logic, and dry-run lockout.", ["controller"]),
            ("soil_sensor", "Measure soil moisture or tank/plant state.", ["sensor_or_adc"]),
            ("pump_driver", "Switch the pump without loading the controller pin.", ["actuator_driver", "protection"]),
            ("pump_load", "Move water through tube or valve.", ["motor_or_load", "fan_or_pump"]),
            ("power", "Supply controller and pump with separated current budget.", ["power", "connector"]),
            ("wet_boundary", "Keep water, strain relief, and electronics physically separated.", ["enclosure_candidate"]),
        ],
        "project_gates": [
            ("measurement", "Measure pump startup current and steady current from the selected supply."),
            ("measurement", "Verify driver flyback/protection path and thermal behavior while the pump runs."),
            ("review", "Keep sensor leads, pump wiring, and controller electronics strain-relieved and away from water paths."),
            ("outcome", "Record a watering-cycle test with dry threshold, pump activation, stop condition, and no leak/overheat result."),
        ],
    },
    {
        "profile_id": "sensor_logger",
        "label": "sensor logger",
        "terms": {"sensor", "logger", "monitor", "telemetry", "temperature", "humidity", "pressure"},
        "phrases": ["sensor logger", "data logger", "environmental monitor"],
        "required_capabilities": ["controller", "sensor_or_adc", "power", "connector"],
        "optional_capabilities": ["wireless", "display_or_ui", "enclosure_candidate"],
        "mapped_build_id": "sensor_logger",
        "blocks": [
            ("controller", "Read the sensor and timestamp or transmit samples.", ["controller"]),
            ("sensor", "Capture the measured environment or signal.", ["sensor_or_adc"]),
            ("power", "Provide stable low-voltage power.", ["power"]),
            ("io", "Expose service/programming and sensor wiring.", ["connector", "usb_serial"]),
        ],
        "project_gates": [
            ("measurement", "Confirm sensor supply voltage, logic voltage, and shared ground before connection."),
            ("outcome", "Record sample output that proves the logger reads the intended signal."),
        ],
    },
    {
        "profile_id": "usb_uart_debug_adapter",
        "label": "USB UART debug adapter",
        "terms": {"usb", "uart", "serial", "debug", "adapter", "ttl", "console"},
        "phrases": ["usb uart", "uart debug", "serial debug", "usb serial", "debug adapter"],
        "required_capabilities": ["usb_serial", "connector"],
        "optional_capabilities": ["power", "protection", "switch_or_button", "display_or_ui", "enclosure_candidate"],
        "mapped_build_id": "usb_uart_debug_adapter",
        "blocks": [
            ("usb_serial_bridge", "Bridge USB to the target UART logic level.", ["usb_serial"]),
            ("uart_header", "Expose measured TX, RX, GND, and optional VCC pins.", ["connector"]),
            ("logic_level_contract", "Keep UART logic voltage, shared ground, and idle state compatible.", ["connector", "usb_serial"]),
            ("protection", "Limit accidental backfeed, shorts, and reversed connector use.", ["protection"]),
            ("service_ui", "Optionally show link/power status or add a reset/boot control.", ["switch_or_button", "display_or_ui"]),
        ],
        "project_gates": [
            ("measurement", "Confirm UART pinout, shared ground, logic voltage, and idle state before connection."),
            ("measurement", "Verify USB-side current draw and no backfeed into the target board."),
            ("outcome", "Record a loopback or target-console session proving TX/RX communication."),
        ],
    },
    {
        "profile_id": "bench_power_adapter",
        "label": "bench power adapter",
        "terms": {"bench", "power", "supply", "adapter", "breakout", "regulator"},
        "phrases": ["bench power", "power adapter", "power supply", "power breakout"],
        "required_capabilities": ["power", "connector", "protection"],
        "optional_capabilities": ["display_or_ui", "switch_or_button", "enclosure_candidate"],
        "mapped_build_id": "bench_power_adapter",
        "blocks": [
            ("input_power", "Accept a known source or module.", ["power"]),
            ("output_connector", "Expose labeled low-voltage outputs.", ["connector"]),
            ("protection", "Limit fault current and reverse-polarity mistakes.", ["protection"]),
            ("ui", "Optionally show voltage/current and enable output.", ["display_or_ui", "switch_or_button"]),
        ],
        "project_gates": [
            ("measurement", "Measure no-load and loaded output voltage at the final connector."),
            ("measurement", "Verify current limit, fuse, or protection behavior before powering another board."),
            ("outcome", "Record a load test with voltage sag and thermal result."),
        ],
    },
    {
        "profile_id": "task_light_or_indicator",
        "label": "low-voltage task light or indicator",
        "terms": {"led", "light", "lamp", "indicator", "blink", "strip", "status"},
        "phrases": ["task light", "desk light", "indicator light", "led strip"],
        "required_capabilities": ["led_or_light", "power", "switch_or_button", "connector"],
        "optional_capabilities": ["controller", "display_or_ui", "enclosure_candidate"],
        "mapped_build_id": "indicator_or_task_light",
        "blocks": [
            ("light_load", "Produce the visible output.", ["led_or_light"]),
            ("power", "Supply LEDs at the correct voltage/current.", ["power", "connector"]),
            ("control", "Switch, dim, or indicate state.", ["switch_or_button", "controller"]),
            ("housing", "Mount the light, diffuser, and wiring safely.", ["enclosure_candidate"]),
        ],
        "project_gates": [
            ("measurement", "Measure LED current, voltage drop, and thermal behavior at intended brightness."),
            ("outcome", "Record visible output proof and thermal result after a sustained run."),
        ],
    },
    {
        "profile_id": "fume_extractor_or_fan",
        "label": "USB fan or fume extractor",
        "terms": {"fume", "extractor", "fan", "fans", "airflow", "cooling", "hot", "vent"},
        "phrases": ["fume extractor", "bench fan", "cooling fan"],
        "required_capabilities": ["power", "motor_or_load", "fan_or_pump", "switch_or_button", "connector"],
        "optional_capabilities": ["enclosure_candidate", "protection"],
        "mapped_build_id": "usb_fume_extractor",
        "blocks": [
            ("fan_load", "Move air through the fixture.", ["motor_or_load", "fan_or_pump"]),
            ("power", "Supply the fan at the correct voltage/current.", ["power"]),
            ("control", "Switch or modulate fan power.", ["switch_or_button", "actuator_driver"]),
            ("housing", "Hold fan, filter, and guards.", ["enclosure_candidate"]),
        ],
        "project_gates": [
            ("measurement", "Measure fan startup current and loaded current."),
            ("review", "Add guard/filter clearance so the fan cannot pull loose wires into the blades."),
            ("outcome", "Record an airflow and thermal run result."),
        ],
    },
    {
        "profile_id": "robot_drive_base",
        "label": "small robot drive base",
        "terms": {"robot", "drive", "wheel", "wheels", "mobile", "rover"},
        "phrases": ["robot drive", "drive base", "mobile robot"],
        "required_capabilities": ["controller", "actuator_driver", "motor_or_load", "power", "connector"],
        "optional_capabilities": ["wireless", "sensor_or_adc", "mechanical_motion", "enclosure_candidate"],
        "mapped_build_id": "robot_drive_base",
        "blocks": [
            ("controller", "Generate motor commands and behavior logic.", ["controller"]),
            ("motor_driver", "Drive motors with protected outputs.", ["actuator_driver", "protection"]),
            ("drive_load", "Provide wheels, motors, and drivetrain.", ["motor_or_load", "mechanical_motion"]),
            ("power", "Separate motor current from logic rail where needed.", ["power", "connector"]),
        ],
        "project_gates": [
            ("measurement", "Measure stall/startup current and verify driver thermal margin."),
            ("measurement", "Verify shared ground and logic voltage before connecting controller to driver."),
            ("outcome", "Record a controlled movement test with current limit and stop behavior."),
        ],
    },
    {
        "profile_id": "camera_trigger_or_capture_rig",
        "label": "camera trigger or capture rig",
        "terms": {"camera", "trigger", "capture", "photo", "image", "timelapse", "shutter"},
        "phrases": ["camera trigger", "capture rig", "timelapse rig", "photo trigger"],
        "required_capabilities": ["controller", "camera_or_vision", "switch_or_button", "power", "connector"],
        "optional_capabilities": ["led_or_light", "mechanical_motion", "enclosure_candidate"],
        "mapped_build_id": "camera_ir_light_or_sensor_mount",
        "blocks": [
            ("controller", "Trigger capture or coordinate capture timing.", ["controller"]),
            ("camera_or_trigger", "Capture images or expose a camera trigger interface.", ["camera_or_vision", "connector"]),
            ("operator_input", "Start, stop, or mark capture cycles.", ["switch_or_button"]),
            ("power", "Supply controller and camera/trigger interface safely.", ["power"]),
            ("mount", "Hold camera, target, or trigger wiring repeatably.", ["mechanical_motion", "enclosure_candidate"]),
        ],
        "project_gates": [
            ("measurement", "Confirm camera/trigger voltage, connector pinout, and idle state before connection."),
            ("outcome", "Record repeated capture or trigger proof with no missed/false triggers."),
        ],
    },
    {
        "profile_id": "inspection_fixture",
        "label": "inspection light or motion fixture",
        "terms": {"inspection", "camera", "fixture", "slider", "motion", "scan", "scanner", "rail"},
        "phrases": ["inspection fixture", "camera slider", "motion fixture"],
        "required_capabilities": ["power", "connector", "mechanical_motion", "led_or_light"],
        "optional_capabilities": ["controller", "sensor_or_adc", "camera_or_vision", "switch_or_button"],
        "mapped_build_id": "inspection_motion_fixture",
        "blocks": [
            ("structure", "Hold the board/object, light, or camera repeatedly.", ["mechanical_motion", "enclosure_candidate"]),
            ("lighting", "Provide stable inspection illumination.", ["led_or_light", "power"]),
            ("control", "Optionally move or trigger capture.", ["controller", "sensor_or_adc"]),
            ("io", "Route power and control wiring with strain relief.", ["connector"]),
        ],
        "project_gates": [
            ("review", "Confirm travel limits and cable strain relief before powered motion."),
            ("measurement", "Measure LED/load current and thermal behavior during a full inspection run."),
            ("outcome", "Record repeatable inspection output from at least two positions or cycles."),
        ],
    },
    {
        "profile_id": "load_controller",
        "label": "low-voltage load controller",
        "terms": {"relay", "mosfet", "load", "switching", "controller", "valve", "solenoid"},
        "phrases": ["load controller", "smart relay", "relay box", "mosfet controller"],
        "required_capabilities": ["controller", "actuator_driver", "power", "connector", "protection"],
        "optional_capabilities": ["wireless", "switch_or_button", "enclosure_candidate"],
        "mapped_build_id": "smart_relay_box",
        "blocks": [
            ("controller", "Decide when to switch the load.", ["controller"]),
            ("driver", "Switch load current with isolation/protection.", ["actuator_driver", "protection"]),
            ("power", "Power logic and load within ratings.", ["power", "connector"]),
            ("operator_io", "Expose manual enable/status where useful.", ["switch_or_button", "display_or_ui"]),
        ],
        "project_gates": [
            ("measurement", "Measure load current and driver voltage drop under the intended duty cycle."),
            ("measurement", "Verify off-state leakage and flyback/protection behavior."),
            ("outcome", "Record a repeated on/off cycle test with no thermal or reset fault."),
        ],
    },
    {
        "profile_id": "input_panel",
        "label": "input panel or macro pad",
        "terms": {"button", "keyboard", "macro", "input", "panel", "keypad", "switch"},
        "phrases": ["macro pad", "input panel", "button panel"],
        "required_capabilities": ["controller", "switch_or_button", "connector", "power"],
        "optional_capabilities": ["usb_serial", "display_or_ui", "enclosure_candidate"],
        "mapped_build_id": "salvaged_input_panel",
        "blocks": [
            ("input_matrix", "Collect switch/button states.", ["switch_or_button", "connector"]),
            ("controller", "Debounce, scan, and expose events.", ["controller", "usb_serial"]),
            ("power", "Power the controller safely.", ["power"]),
            ("case", "Hold the input panel ergonomically.", ["enclosure_candidate"]),
        ],
        "project_gates": [
            ("measurement", "Map switch matrix continuity and confirm no stuck/shorted inputs."),
            ("outcome", "Record all inputs triggering the expected output events."),
        ],
    },
    {
        "profile_id": "network_status_indicator",
        "label": "network status indicator",
        "terms": {"wifi", "network", "internet", "router", "status", "indicator", "led", "blink", "online"},
        "phrases": ["network status", "wifi status", "internet status", "status indicator"],
        "required_capabilities": ["controller", "wireless", "led_or_light", "power", "connector"],
        "optional_capabilities": ["display_or_ui", "enclosure_candidate", "switch_or_button"],
        "mapped_build_id": "network_status_indicator",
        "blocks": [
            ("controller", "Poll, receive, or infer status and drive the indicator state.", ["controller", "wireless"]),
            ("indicator", "Show online/offline/degraded state.", ["led_or_light", "display_or_ui"]),
            ("power", "Provide stable low-voltage power.", ["power"]),
            ("case_io", "Expose power and service access.", ["connector", "enclosure_candidate"]),
        ],
        "project_gates": [
            ("review", "Define online, degraded, and offline behavior before wiring indicators."),
            ("outcome", "Record state-change proof for at least two network states."),
        ],
    },
    {
        "profile_id": "audio_alert_box",
        "label": "audio alert box",
        "terms": {"audio", "speaker", "buzzer", "sound", "alert", "beep", "amp", "amplifier"},
        "phrases": ["audio alert", "speaker box", "buzzer box", "alert box"],
        "required_capabilities": ["speaker_or_audio", "power", "connector", "switch_or_button"],
        "optional_capabilities": ["controller", "enclosure_candidate", "display_or_ui"],
        "mapped_build_id": "small_audio_amp_box",
        "blocks": [
            ("audio_load", "Generate audible feedback or playback.", ["speaker_or_audio"]),
            ("power", "Supply the audio module within voltage/current rating.", ["power"]),
            ("operator_input", "Enable, silence, or test the alert.", ["switch_or_button"]),
            ("case_io", "Hold the speaker, control, and wiring.", ["connector", "enclosure_candidate"]),
        ],
        "project_gates": [
            ("measurement", "Measure audio module supply current and verify speaker impedance/rating."),
            ("outcome", "Record audible output proof at the intended volume with no overheating."),
        ],
    },
    {
        "profile_id": "generic_low_voltage_build",
        "label": "generic low-voltage hardware build",
        "terms": set(),
        "phrases": [],
        "required_capabilities": ["controller", "power", "connector"],
        "optional_capabilities": ["sensor_or_adc", "actuator_driver", "switch_or_button", "enclosure_candidate"],
        "mapped_build_id": "",
        "blocks": [
            ("controller_or_logic", "Implement the behavior or state machine.", ["controller"]),
            ("power", "Provide safe low-voltage power.", ["power"]),
            ("interfaces", "Expose wiring, programming, or load connections.", ["connector"]),
            ("application_io", "Add the sensor, actuator, display, or controls demanded by the goal.", ["sensor_or_adc", "actuator_driver", "display_or_ui", "switch_or_button"]),
        ],
        "project_gates": [
            ("review", "Write explicit pass/fail behavior before choosing parts."),
            ("measurement", "Measure no-short resistance, voltage, polarity, and current limit before first power."),
            ("outcome", "Record terminal output-function proof with photos or test report."),
        ],
    },
]

CAPABILITY_HINTS = [
    ({"automatic", "automated", "timer", "schedule", "threshold", "logic"}, ["controller"]),
    ({"wifi", "wireless", "bluetooth", "ble", "remote", "phone"}, ["wireless", "controller"]),
    ({"sensor", "sense", "detect", "measure", "moisture", "temperature", "humidity", "pressure", "current", "voltage"}, ["sensor_or_adc"]),
    ({"camera", "vision", "image", "photo"}, ["camera_or_vision", "sensor_or_adc"]),
    ({"display", "screen", "oled", "lcd", "status"}, ["display_or_ui"]),
    ({"button", "switch", "manual", "enable", "keypad"}, ["switch_or_button"]),
    ({"motor", "pump", "fan", "solenoid", "valve", "relay", "load"}, ["actuator_driver", "motor_or_load", "power"]),
    ({"pump", "fan"}, ["fan_or_pump"]),
    ({"led", "light", "lamp", "indicator"}, ["led_or_light", "power"]),
    ({"battery", "usb", "power", "supply", "5v", "12v", "regulator", "buck", "boost"}, ["power"]),
    ({"wire", "cable", "header", "jst", "connector", "plug", "terminal"}, ["connector"]),
    ({"fuse", "protect", "protection", "flyback", "diode", "reverse"}, ["protection"]),
    ({"motion", "rail", "slider", "servo", "stepper", "gear", "wheel"}, ["mechanical_motion"]),
    ({"case", "box", "mount", "bracket", "housing", "enclosure"}, ["enclosure_candidate"]),
    ({"serial", "uart", "usb"}, ["usb_serial", "connector"]),
    ({"audio", "speaker", "buzzer", "amp"}, ["speaker_or_audio"]),
]

HAZARD_RULES = [
    (
        "mains_high_voltage",
        {
            "mains",
            "120v",
            "240v",
            "110v",
            "220v",
            "ac line",
            "line voltage",
            "wall outlet",
            "ac outlet",
            "ac mains",
            "ac lamp",
            "ac load",
            "ac motor",
            "ac heater",
            "ac relay",
            "triac",
            "dimmer",
        },
        "Mains/high-voltage work needs a separate specialist isolation, enclosure, fuse, creepage, and leakage-current authority path.",
    ),
    (
        "battery_pack_lithium",
        {"lithium", "liion", "lipo", "li-poly", "18650"},
        "Lithium pack design/reuse needs chemistry, cell count, BMS, balance, containment, and charge/discharge proof.",
    ),
    (
        "high_current_heat",
        {"heater", "heating", "welder", "spot", "kilowatt", "highcurrent"},
        "High-current or heating builds need thermal, overcurrent, enclosure, and fire-risk authority before build/release.",
    ),
    (
        "laser_radiation",
        {"laser", "diode", "optical"},
        "Laser builds need class, containment, interlock, labeling, and exposure-limit proof.",
    ),
]


def build_diy_project_engineering_plan(
    payload: Dict[str, Any],
    *,
    resource_planner: Optional[ResourceStrategyPlanner] = None,
) -> Dict[str, Any]:
    """Build a deterministic engineering plan for an operator-requested DIY project."""

    body = payload or {}
    text = _case_text(body)
    if not _looks_like_diy_project(body, text):
        return {
            "mode": "diy_project_engineering",
            "schema_version": SCHEMA_VERSION,
            "available": False,
            "reason": "No explicit DIY/build project intent was detected.",
        }

    profile = _select_profile(text)
    explicit_required = _normalise_capabilities(
        body.get("required_capabilities")
        or body.get("capabilities_required")
        or ((body.get("constraints") or {}).get("required_capabilities") if isinstance(body.get("constraints"), dict) else None)
    )
    inferred_required = _requirements_for_profile(profile, text)
    required = explicit_required or inferred_required
    optional = _dedupe_caps([*profile.get("optional_capabilities", []), *_optional_hints(text)])
    safety = _safety_profile(text, required, body)

    strategy_payload = dict(body)
    constraints = dict(strategy_payload.get("constraints") or {}) if isinstance(strategy_payload.get("constraints"), dict) else {}
    if not any(key in constraints for key in ["budget_usd", "max_budget_usd", "budget"]) and not any(
        key in strategy_payload for key in ["budget_usd", "max_budget_usd"]
    ):
        inferred_budget = _extract_budget_usd(text)
        if inferred_budget is not None:
            constraints["budget_usd"] = inferred_budget
            strategy_payload["constraints"] = constraints
    strategy_payload["required_capabilities"] = required
    strategy_payload.setdefault("target_build_id", profile.get("mapped_build_id") or "")
    strategy_payload.setdefault("goal", _goal_text(body, default=profile.get("label") or "DIY hardware build"))
    planner = resource_planner or ResourceStrategyPlanner()
    resource_strategy = planner.plan(strategy_payload)

    architecture = _architecture_blocks(profile, required, resource_strategy, safety)
    gates = _engineering_gates(profile, required, safety, resource_strategy)
    stages = _build_stages(resource_strategy, gates, safety)
    readiness = _readiness(resource_strategy, gates, safety)
    next_actions = _next_actions(resource_strategy, gates, safety, readiness)

    return {
        "mode": "diy_project_engineering",
        "schema_version": SCHEMA_VERSION,
        "available": True,
        "project_intent": {
            "goal": _goal_text(body, default=profile.get("label") or ""),
            "profile_id": profile.get("profile_id"),
            "profile_label": profile.get("label"),
            "mapped_build_id": profile.get("mapped_build_id") or None,
            "strategy_mode": resource_strategy.get("strategy_mode"),
            "input_difference_not_engine_difference": {
                "constrained_or_junk": "Treat available boards/modules as a premade puzzle and prove what can be reused.",
                "open_procurement": "Treat missing functions as buy/design gaps and select reliable modules.",
                "hybrid": "Reuse proven resources and buy/design only the real gaps.",
            },
        },
        "requirements": {
            "required_capabilities": required,
            "optional_capabilities": optional,
            "explicit_required_capabilities": bool(explicit_required),
            "functional_requirements": _functional_requirements(profile, required, text),
            "constraints": resource_strategy.get("constraints") or {},
        },
        "architecture_blocks": architecture,
        "resource_plan": _resource_plan_summary(resource_strategy),
        "build_stages": stages,
        "engineering_gates": gates,
        "readiness": readiness,
        "handoff_to_hardware_plan": {
            "next_engine": "hardware_plan",
            "suggested_payload_patch": {
                "goal": _goal_text(body, default=profile.get("label") or ""),
                "required_capabilities": required,
                "target_build_id": profile.get("mapped_build_id") or "",
                "strategy_mode": resource_strategy.get("strategy_mode"),
            },
            "selected_resource_ids": [
                str(row.get("resource_id"))
                for row in resource_strategy.get("selected_resources") or []
                if isinstance(row, dict) and row.get("resource_id")
            ],
        },
        "next_actions": next_actions,
        "next_evidence_tasks": _next_evidence_tasks(gates),
        "claim_boundary": (
            "This is an engineering planner. It can produce architecture, resource selection, and test gates; "
            "it cannot turn unmeasured resources into safe wiring, power, splice, sale, or production-release authority."
        ),
    }


def enrich_payload_with_diy_project_engineering(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach DIY project engineering analysis and infer capabilities when safe."""

    body = dict(payload or {})
    plan = build_diy_project_engineering_plan(body)
    if not plan.get("available"):
        return body

    analysis = dict(body.get("analysis") if isinstance(body.get("analysis"), dict) else {})
    analysis["diy_project_engineering"] = plan

    should_inject = _should_inject_plan_into_hardware_payload(body, plan)
    if should_inject:
        body["required_capabilities"] = plan.get("requirements", {}).get("required_capabilities") or []
        mapped = (plan.get("project_intent") or {}).get("mapped_build_id")
        if mapped and not body.get("target_build_id"):
            body["target_build_id"] = mapped
        existing_tasks = [task for task in analysis.get("next_evidence_tasks") or [] if isinstance(task, dict)]
        analysis["next_evidence_tasks"] = _dedupe_tasks([*existing_tasks, *plan.get("next_evidence_tasks", [])])

    body["analysis"] = analysis
    body["diy_project_engineering_plan"] = plan
    return body


def _looks_like_diy_project(payload: Dict[str, Any], text: str) -> bool:
    if any(payload.get(key) for key in DIY_TRIGGER_KEYS):
        return True
    tokens = _tokens(text)
    if not tokens:
        return False
    if tokens & BUILD_VERBS:
        return True
    if {"want", "need"} & tokens and {"thing", "device", "system", "tool", "gadget", "project"} & tokens:
        return True
    if tokens & NON_BUILD_INTENT_WORDS and not (tokens & BUILD_VERBS):
        return False
    return False


def _should_inject_plan_into_hardware_payload(payload: Dict[str, Any], plan: Dict[str, Any]) -> bool:
    if payload.get("required_capabilities") or payload.get("capabilities_required"):
        return False
    if any(payload.get(key) for key in DIY_TRIGGER_KEYS):
        return True
    text = _case_text(payload)
    tokens = _tokens(text)
    return bool(tokens & BUILD_VERBS and plan.get("available"))


def _case_text(payload: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in [
        "diy_project",
        "project_brief",
        "build_goal",
        "target_build",
        "target_device",
        "desired_device",
        "goal",
        "description",
        "title",
        "device_hint",
    ]:
        value = payload.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            parts.extend(str(value.get(k) or "") for k in ["goal", "name", "description", "summary"])
    constraints = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else {}
    parts.extend(str(constraints.get(k) or "") for k in ["environment", "safety_level", "notes"])
    return " ".join(part for part in parts if part).strip()


def _extract_budget_usd(text: str) -> Optional[float]:
    cleaned = str(text or "").lower()
    patterns = [
        r"\$\s*(\d+(?:\.\d+)?)",
        r"\b(\d+(?:\.\d+)?)\s*(?:usd|dollars?|bucks?)\b",
        r"\b(?:budget|max|under|below|around|about|only|spend|ceiling|limit)\b(?:\s+\w+){0,4}?\s+(\d+(?:\.\d+)?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except (TypeError, ValueError):
            continue
        if 0 < value < 100000:
            return round(value, 2)
    return None


def _goal_text(payload: Dict[str, Any], *, default: str = "") -> str:
    for key in ["diy_project", "project_brief", "build_goal", "target_build", "goal", "description", "title"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested in ["goal", "name", "description", "summary"]:
                text = str(value.get(nested) or "").strip()
                if text:
                    return text
    return default


def _select_profile(text: str) -> Dict[str, Any]:
    tokens = _tokens(text)
    lower = text.lower()
    best = None
    best_score = -1.0
    for profile in PROFILE_LIBRARY:
        score = 0.0
        terms = set(profile.get("terms") or set())
        if terms:
            score += len(tokens & terms) * 2.0
        for phrase in profile.get("phrases") or []:
            if phrase in lower:
                score += 5.0
        if score > best_score:
            best = profile
            best_score = score
    if best_score <= 0:
        return dict(PROFILE_LIBRARY[-1])
    return dict(best or PROFILE_LIBRARY[-1])


def _requirements_for_profile(profile: Dict[str, Any], text: str) -> List[str]:
    caps = list(profile.get("required_capabilities") or [])
    tokens = _tokens(text)
    for hint_terms, hinted_caps in CAPABILITY_HINTS:
        if tokens & hint_terms:
            caps.extend(hinted_caps)
    if caps and "connector" not in caps:
        caps.append("connector")
    return _dedupe_caps(caps)


def _optional_hints(text: str) -> List[str]:
    tokens = _tokens(text)
    optional: List[str] = []
    if {"portable", "outdoor", "wet", "water", "plant"} & tokens:
        optional.append("enclosure_candidate")
    if {"status", "debug", "log", "monitor"} & tokens:
        optional.extend(["display_or_ui", "usb_serial"])
    return _dedupe_caps(optional)


def _functional_requirements(profile: Dict[str, Any], required: Sequence[str], text: str) -> List[Dict[str, Any]]:
    rows = [
        {
            "requirement_id": "output_function",
            "description": f"Produce the target output for: {_short_goal(text, profile.get('label') or 'DIY build')}.",
            "capabilities": list(required),
            "evidence_needed": "terminal output-function proof",
        },
        {
            "requirement_id": "safe_low_voltage_bringup",
            "description": "Use current-limited first power, no-short checks, known polarity, and thermal observation.",
            "capabilities": ["power", "protection"],
            "evidence_needed": "bench measurement record",
        },
    ]
    if "controller" in required:
        rows.append(
            {
                "requirement_id": "control_logic",
                "description": "Define the state machine, thresholds, fail-safe state, and manual override behavior.",
                "capabilities": ["controller", "switch_or_button"],
                "evidence_needed": "functional test log",
            }
        )
    if "sensor_or_adc" in required:
        rows.append(
            {
                "requirement_id": "input_truth",
                "description": "Prove the sensor range, wiring, and logic voltage before using it for decisions.",
                "capabilities": ["sensor_or_adc"],
                "evidence_needed": "sensor reading capture",
            }
        )
    if {"actuator_driver", "motor_or_load"} & set(required):
        rows.append(
            {
                "requirement_id": "load_control",
                "description": "Drive the load through a rated driver with protection and measured current/thermal margin.",
                "capabilities": ["actuator_driver", "motor_or_load", "protection"],
                "evidence_needed": "current and thermal run",
            }
        )
    return rows


def _architecture_blocks(
    profile: Dict[str, Any],
    required: Sequence[str],
    resource_strategy: Dict[str, Any],
    safety: Dict[str, Any],
) -> List[Dict[str, Any]]:
    selected = [row for row in resource_strategy.get("selected_resources") or [] if isinstance(row, dict)]
    missing = set((resource_strategy.get("coverage") or {}).get("missing_capabilities") or [])
    rows = []
    for block_id, role, caps in profile.get("blocks") or []:
        block_caps = [cap for cap in caps if cap in set(required) or cap in set(profile.get("optional_capabilities") or [])]
        candidates = _resources_for_caps(selected, block_caps)
        if safety.get("hard_block"):
            status = "blocked_until_specialist_authority"
        elif any(cap in missing for cap in block_caps):
            status = "missing_resource"
        elif candidates:
            status = "resource_selected_evidence_gated"
        else:
            status = "optional_or_design_detail"
        rows.append(
            {
                "block_id": block_id,
                "role": role,
                "required_capabilities": block_caps,
                "candidate_resource_ids": [str(row.get("resource_id")) for row in candidates if row.get("resource_id")],
                "status": status,
            }
        )
    covered = {cap for row in rows for cap in row.get("required_capabilities") or []}
    for cap in required:
        if cap in covered:
            continue
        rows.append(
            {
                "block_id": cap,
                "role": f"Provide capability: {cap}.",
                "required_capabilities": [cap],
                "candidate_resource_ids": [str(row.get("resource_id")) for row in _resources_for_caps(selected, [cap]) if row.get("resource_id")],
                "status": "missing_resource" if cap in missing else "resource_selected_evidence_gated",
            }
        )
    return rows[:16]


def _engineering_gates(
    profile: Dict[str, Any],
    required: Sequence[str],
    safety: Dict[str, Any],
    resource_strategy: Dict[str, Any],
) -> List[Dict[str, Any]]:
    gates = [
        _gate("review", "project_contract", "Write the target output function, pass/fail behavior, operating voltage, and stop conditions."),
        _gate("review", "block_diagram", "Draw or record the controller, power, input, output, and connector boundaries."),
        _gate("measurement", "power_no_short", "Measure no-short resistance between every power rail and ground before first power."),
        _gate("measurement", "power_voltage_current", "Measure source voltage, polarity, and current limit before connecting resources together."),
    ]
    cap_set = set(required)
    if cap_set & {"controller", "sensor_or_adc", "usb_serial", "wireless"}:
        gates.append(_gate("measurement", "logic_ground", "Verify shared ground, logic voltage, and idle bus state before signal wiring."))
    if cap_set & {"actuator_driver", "motor_or_load", "fan_or_pump"}:
        gates.append(_gate("measurement", "load_current_thermal", "Measure load startup current, steady current, and thermal behavior under duty cycle."))
    if "mechanical_motion" in cap_set:
        gates.append(_gate("review", "mechanical_limits", "Confirm travel limits, clearance, mounting, and wire strain relief before powered motion."))
    if "enclosure_candidate" in cap_set or "water" in _tokens((profile.get("label") or "")):
        gates.append(_gate("review", "enclosure_boundary", "Confirm enclosure, strain relief, wet/dry boundary, and service access."))

    for index, (gate_type, prompt) in enumerate(profile.get("project_gates") or []):
        gates.append(_gate(gate_type, f"profile_{profile.get('profile_id')}_{index + 1}", prompt))

    for hazard in safety.get("hazards") or []:
        hard_hazard = bool(hazard.get("unsupported_for_direct_diy_authority") and hazard.get("severity") == "critical")
        gates.append(
            {
                "gate_id": f"safety_{hazard.get('hazard_id')}",
                "type": "safety" if hard_hazard else "review",
                "status": "blocked" if hard_hazard else "open",
                "prompt": hazard.get("required_authority"),
                "source": "diy_project_engineering",
            }
        )

    for gate in resource_strategy.get("evidence_gates") or []:
        if not isinstance(gate, dict) or not gate.get("prompt"):
            continue
        gates.append(
            {
                "gate_id": gate.get("gate_id") or _safe_id(gate.get("prompt")),
                "resource_id": gate.get("resource_id"),
                "type": gate.get("type") or "measurement",
                "status": gate.get("status", "open"),
                "prompt": gate.get("prompt"),
                "source": "resource_strategy",
            }
        )
    gates.append(_gate("outcome", "terminal_output_proof", "Record terminal outcome with resources used, first-power result, thermal result, output proof, cost, value, time, deviations, and evidence URI."))
    return _dedupe_gates(gates)[:32]


def _build_stages(
    resource_strategy: Dict[str, Any],
    gates: Sequence[Dict[str, Any]],
    safety: Dict[str, Any],
) -> List[Dict[str, Any]]:
    missing = (resource_strategy.get("coverage") or {}).get("missing_capabilities") or []
    open_measurements = [gate for gate in gates if gate.get("type") == "measurement" and gate.get("status", "open") not in {"closed", "pass"}]
    blocked = safety.get("hard_block")
    return [
        {
            "stage_id": "scope_contract",
            "status": "ready" if not blocked else "blocked_until_specialist_authority",
            "exit_criteria": "goal, pass/fail behavior, constraints, and hazards are explicit",
        },
        {
            "stage_id": "resource_selection",
            "status": "blocked_missing_resources" if missing else "ready_after_review",
            "exit_criteria": "required capabilities are covered by owned, salvaged, procurable, or designed resources",
            "missing_capabilities": missing,
        },
        {
            "stage_id": "bench_proof",
            "status": "blocked_until_measurements" if open_measurements or blocked else "ready",
            "exit_criteria": "no-short, voltage, current, logic, load, and thermal gates are closed",
        },
        {
            "stage_id": "integration_build",
            "status": "blocked_until_bench_proof" if open_measurements or missing or blocked else "ready",
            "exit_criteria": "wiring, mounting, strain relief, and first-power are performed under current limit",
        },
        {
            "stage_id": "functional_validation",
            "status": "blocked_until_integrated",
            "exit_criteria": "target output function passes repeatable test",
        },
        {
            "stage_id": "release_or_portfolio_demo",
            "status": "blocked_until_outcome_artifact",
            "exit_criteria": "terminal outcome, photos/test report, and claim boundary are recorded",
        },
    ]


def _safety_profile(text: str, required: Sequence[str], payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _compact_text(text)
    tokens = _tokens(text)
    hazards = []
    for hazard_id, terms, authority in HAZARD_RULES:
        if _hazard_terms_match(text, tokens, normalized, terms):
            hazards.append(
                {
                    "hazard_id": hazard_id,
                    "severity": "critical",
                    "required_authority": authority,
                    "unsupported_for_direct_diy_authority": True,
                }
            )
    if {"battery", "pack"} <= tokens or {"battery", "packs"} <= tokens:
        hazards.append(
            {
                "hazard_id": "battery_pack_lithium",
                "severity": "critical",
                "required_authority": "Battery pack design/reuse needs chemistry, cell count, BMS, balance, containment, and charge/discharge proof.",
                "unsupported_for_direct_diy_authority": True,
            }
        )
    if {"water", "watering", "irrigation"} & tokens and {"power", "connector"} & set(required):
        hazards.append(
            {
                "hazard_id": "water_near_electronics",
                "severity": "moderate",
                "required_authority": "Wet/dry boundary, strain relief, drip loop, and low-voltage isolation must be proven before unattended use.",
                "unsupported_for_direct_diy_authority": False,
            }
        )
    resources_text = " ".join(
        str(row.get("name") or row.get("notes") or "")
        for key in ["available_resources", "resources", "owned_resources", "inventory", "modules", "available_parts", "salvaged_resources"]
        for row in _rows(payload.get(key))
        if isinstance(row, dict)
    )
    resource_tokens = _tokens(resources_text)
    if {"swollen", "punctured", "leaking"} & resource_tokens:
        hazards.append(
            {
                "hazard_id": "damaged_energy_storage",
                "severity": "critical",
                "required_authority": "Damaged batteries or energy-storage parts are excluded until a separate safety process clears disposal or specialist handling.",
                "unsupported_for_direct_diy_authority": True,
            }
        )
    hazards = _dedupe_hazards(hazards)
    hard = any(h.get("unsupported_for_direct_diy_authority") and h.get("severity") == "critical" for h in hazards)
    return {
        "safety_class": "specialist_authority_required" if hard else "low_voltage_project_with_gates",
        "hard_block": hard,
        "hazards": hazards,
        "policy": {
            "low_voltage_current_limited_first_power": True,
            "unattended_or_wet_use_requires_extra_outcome_testing": bool(any(h.get("hazard_id") == "water_near_electronics" for h in hazards)),
            "mains_battery_laser_high_current_require_specialist_lane": True,
        },
    }


def _readiness(resource_strategy: Dict[str, Any], gates: Sequence[Dict[str, Any]], safety: Dict[str, Any]) -> Dict[str, Any]:
    coverage = resource_strategy.get("coverage") if isinstance(resource_strategy.get("coverage"), dict) else {}
    score = float(coverage.get("coverage_score") or 0.0)
    open_gates = [gate for gate in gates if gate.get("status", "open") not in {"closed", "pass"}]
    blocked_gates = [gate for gate in open_gates if gate.get("type") == "safety" or gate.get("status") == "blocked"]
    missing = coverage.get("missing_capabilities") or []
    if safety.get("hard_block"):
        level = "blocked_specialist_required"
        can_build = False
    elif missing:
        level = "resource_gap"
        can_build = False
    elif blocked_gates:
        level = "blocked_safety_gate"
        can_build = False
    elif open_gates:
        level = "prototype_after_evidence"
        can_build = False
    else:
        level = "build_plan_ready"
        can_build = True
    authority_score = score
    if open_gates:
        authority_score = min(authority_score, 0.72)
    if missing:
        authority_score = min(authority_score, 0.48)
    if safety.get("hard_block"):
        authority_score = min(authority_score, 0.25)
    return {
        "level": level,
        "score": round(authority_score, 3),
        "resource_coverage_score": round(score, 3),
        "can_start_design_now": not safety.get("hard_block"),
        "can_build_or_power_now": can_build,
        "open_gate_count": len(open_gates),
        "blocked_gate_count": len(blocked_gates),
        "missing_capabilities": missing,
        "status_reason": _readiness_reason(level),
    }


def _readiness_reason(level: str) -> str:
    return {
        "blocked_specialist_required": "A hard hazard is present; use a specialist authority lane before build/power/release.",
        "resource_gap": "The target function is defined, but required capabilities are not covered yet.",
        "blocked_safety_gate": "Safety gates are open; do not power or integrate until they close.",
        "prototype_after_evidence": "The architecture and resources are plausible, but bench evidence must close before wiring/power.",
        "build_plan_ready": "Resources and gates are closed enough to proceed to controlled build execution.",
    }.get(level, "Project needs more definition.")


def _next_actions(
    resource_strategy: Dict[str, Any],
    gates: Sequence[Dict[str, Any]],
    safety: Dict[str, Any],
    readiness: Dict[str, Any],
) -> List[str]:
    actions: List[str] = []
    if safety.get("hard_block"):
        actions.append("Stop direct DIY execution and route the hazardous part of the build to a specialist authority lane.")
    missing = readiness.get("missing_capabilities") or []
    if missing:
        actions.append("Close missing capabilities by adding inventory, buying modules, or changing project scope.")
    procurement = resource_strategy.get("procurement_plan") if isinstance(resource_strategy.get("procurement_plan"), dict) else {}
    if procurement.get("items"):
        actions.append("Review selected buy-list modules against voltage/current ratings and budget before ordering.")
    first_gate = next((gate for gate in gates if gate.get("type") in {"measurement", "safety"} and gate.get("status", "open") not in {"closed", "pass"}), None)
    if first_gate and first_gate.get("prompt"):
        actions.append(str(first_gate.get("prompt")))
    actions.append("Turn the selected resources into a wiring/build packet only after the listed gates are closed.")
    return _dedupe_text(actions)[:8]


def _resource_plan_summary(resource_strategy: Dict[str, Any]) -> Dict[str, Any]:
    procurement = resource_strategy.get("procurement_plan") if isinstance(resource_strategy.get("procurement_plan"), dict) else {}
    return {
        "strategy_mode": resource_strategy.get("strategy_mode"),
        "recommended_path": resource_strategy.get("recommended_path"),
        "build_readiness": resource_strategy.get("build_readiness") or {},
        "coverage": resource_strategy.get("coverage") or {},
        "selected_resources": resource_strategy.get("selected_resources") or [],
        "procurement": {
            "estimated_cost_usd": procurement.get("estimated_cost_usd", 0),
            "budget_usd": procurement.get("budget_usd"),
            "within_budget": procurement.get("within_budget", True),
            "items": procurement.get("items") or [],
            "unfilled_capabilities": procurement.get("unfilled_capabilities") or [],
        },
        "value_summary": resource_strategy.get("value_summary") or {},
    }


def _next_evidence_tasks(gates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tasks = []
    for gate in gates:
        if not isinstance(gate, dict) or not gate.get("prompt"):
            continue
        if str(gate.get("status", "open")) in {"closed", "pass"}:
            continue
        tasks.append(
            {
                "task_id": gate.get("gate_id") or _safe_id(gate.get("prompt")),
                "type": gate.get("type") or "review",
                "status": gate.get("status", "open"),
                "priority": 1 if gate.get("type") == "safety" else 2,
                "prompt": gate.get("prompt"),
                "source": "diy_project_engineering",
            }
        )
    return _dedupe_tasks(tasks)[:24]


def _resources_for_caps(resources: Sequence[Dict[str, Any]], caps: Sequence[str]) -> List[Dict[str, Any]]:
    cap_set = set(caps)
    if not cap_set:
        return []
    return [
        row for row in resources
        if isinstance(row, dict) and cap_set & set(row.get("capabilities") or [])
    ][:6]


def _gate(gate_type: str, gate_id: str, prompt: str) -> Dict[str, Any]:
    return {
        "gate_id": gate_id,
        "type": gate_type,
        "status": "open",
        "prompt": prompt,
        "source": "diy_project_engineering",
    }


def _normalise_capabilities(value: Any) -> List[str]:
    aliases = {
        "mcu": "controller",
        "microcontroller": "controller",
        "sensor": "sensor_or_adc",
        "adc": "sensor_or_adc",
        "motor_driver": "actuator_driver",
        "relay": "actuator_driver",
        "mosfet": "actuator_driver",
        "motor": "motor_or_load",
        "pump": "fan_or_pump",
        "fan": "fan_or_pump",
        "wire": "connector",
        "cable": "connector",
        "wiring": "connector",
        "fuse": "protection",
        "case": "enclosure_candidate",
        "enclosure": "enclosure_candidate",
    }
    caps: List[str] = []
    for item in _rows(value):
        if isinstance(item, dict):
            item = item.get("capability") or item.get("name") or item.get("id")
        raw = str(item or "").strip().lower().replace("-", "_").replace(" ", "_")
        if raw:
            caps.append(aliases.get(raw, raw))
    return _dedupe_caps(caps)


def _dedupe_caps(caps: Iterable[Any]) -> List[str]:
    seen: Set[str] = set()
    kept: List[str] = []
    rank = {cap: index for index, cap in enumerate(CAPABILITY_ORDER)}
    for cap in caps:
        text = str(cap or "").strip().lower().replace("-", "_").replace(" ", "_")
        if not text or text in seen:
            continue
        seen.add(text)
        kept.append(text)
    return sorted(kept, key=lambda cap: (rank.get(cap, 999), cap))


def _dedupe_text(items: Iterable[Any]) -> List[str]:
    seen = set()
    kept = []
    for item in items:
        text = str(item or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        kept.append(text)
    return kept


def _dedupe_gates(gates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    kept = []
    for gate in gates:
        key = (str(gate.get("gate_id") or "").lower(), str(gate.get("prompt") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        kept.append(gate)
    return kept


def _dedupe_tasks(tasks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    kept = []
    for task in tasks:
        key = (str(task.get("type") or ""), str(task.get("prompt") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        kept.append(task)
    return kept


def _rows(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        return [item.strip() for item in value.replace(";", "\n").splitlines() if item.strip()]
    return [value]


def _tokens(text: str) -> Set[str]:
    tokens: Set[str] = set()
    current: List[str] = []
    for ch in str(text or "").lower():
        if ch.isalnum():
            current.append(ch)
        else:
            if current:
                tokens.add("".join(current))
                current = []
    if current:
        tokens.add("".join(current))
    return tokens


def _compact_text(text: str) -> str:
    return "".join(ch.lower() for ch in str(text or "") if ch.isalnum())


def _hazard_terms_match(text: str, tokens: Set[str], normalized_text: str, terms: Iterable[str]) -> bool:
    lower = str(text or "").lower()
    for raw_term in terms:
        term = str(raw_term or "").lower()
        if not term:
            continue
        if _term_is_negated(lower, term):
            continue
        if term in tokens:
            return True
        term_tokens = _tokens(term)
        if len(term_tokens) > 1 and term_tokens <= tokens:
            return True
        compact = _compact_text(term)
        if len(compact) >= 8 and compact in normalized_text:
            return True
    return False


def _term_is_negated(lower_text: str, term: str) -> bool:
    term_pattern = re.escape(term).replace(r"\ ", r"\s+")
    return bool(
        re.search(
            rf"\b(?:no|not|without|avoid|excluding|exclude|never)\b(?:\s+\w+){{0,4}}\s+{term_pattern}\b",
            lower_text,
        )
    )


def _dedupe_hazards(hazards: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    kept: List[Dict[str, Any]] = []
    for hazard in hazards:
        hazard_id = str(hazard.get("hazard_id") or "")
        if not hazard_id or hazard_id in seen:
            continue
        seen.add(hazard_id)
        kept.append(hazard)
    return kept


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:90] or "item"


def _short_goal(text: str, fallback: str) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return fallback
    return cleaned[:140]
