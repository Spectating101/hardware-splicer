"""Evidence-first rover motor power review.

This is a project-package evidence gate, not a supply synthesizer, motor
controller designer, physical measurement or power-on authorization. Only a
measured and independently reviewed bench session can authorize physical work.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.rover_power_evidence.v1"
L298_VENDOR = "https://www.st.com/en/motor-drivers/l298.html"


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    if not (number > 0 and number < 1_000_000):
        return None
    return number


def _part_quantity(part: Mapping[str, Any]) -> int:
    number = _positive_number(part.get("quantity", part.get("qty", 1)))
    return int(number) if number is not None and number.is_integer() else 0


def evaluate_rover_power(
    *,
    intake: Mapping[str, Any] | None,
    graph: Mapping[str, Any] | None,
    project_build_id: str = "",
) -> dict[str, Any]:
    """Report what the input actually establishes about a proposed motor path.

    Intentionally does not infer battery chemistry, battery peak current,
    voltage regulators, wiring, heat dissipation, enable-jumper positions,
    charge state, or physical measurements from an algorithmic design.
    """
    intake = dict(intake or {})
    nodes = [n for n in (graph or {}).get("nodes", []) if isinstance(n, Mapping)]
    mids = [str(n.get("moduleId") or n.get("module_id") or "") for n in nodes]
    motor_ids = {"dc_motor_3v_6v", "dc_geared_motor_12v"}
    drivers = {"l298n", "drv8833-motor", "l9110-motor", "tb6612fng-motor", "bts7960-motor"}
    if project_build_id != "robot_drive_base":
        return {"schema_version": SCHEMA_VERSION, "status": "not_applicable", "blockers": [], "next_actions": []}

    parts = intake.get("available_parts") or intake.get("normalized_parts") or []
    if not isinstance(parts, list):
        parts = []
    motor_parts = [
        p for p in parts if isinstance(p, Mapping) and (
            str(p.get("type") or p.get("part_class") or "").lower() in {"dc_motor", "geared_motor", "motor"}
            or "motor" in str(p.get("name") or "").lower()
        )
    ]
    # Do not interpret the donor controller board or generic motor driver as a motor.
    motor_parts = [p for p in motor_parts if "board" not in str(p.get("type") or p.get("name") or "").lower()
                   and "driver" not in str(p.get("type") or p.get("name") or "").lower()]
    motor_count = sum(_part_quantity(part) for part in motor_parts)
    constraints = dict(intake.get("constraints") or {})
    battery_v = _positive_number(constraints.get("battery_voltage_v"))
    battery_mah = _positive_number(constraints.get("battery_capacity_mah"))
    rated = [_positive_number(p.get("voltage_v")) for p in motor_parts]
    stall = [_positive_number(p.get("stall_current_a")) for p in motor_parts]
    stall_known = bool(motor_parts) and all(x is not None for x in stall) and all(_part_quantity(p) for p in motor_parts)
    simultaneous_stall_a = (
        round(sum(float(amps) * _part_quantity(part) for amps, part in zip(stall, motor_parts) if amps is not None), 3)
        if stall_known else None
    )
    power_source_ids = {"dc-barrel-12v", "usb-power-5v", "buck-mp1584"}
    source_nodes = sorted(set(mids).intersection(power_source_ids))
    active_drivers = sorted(set(mids).intersection(drivers))
    missing: list[dict[str, str]] = []
    def require(code: str, message: str, action: str) -> None:
        missing.append({"code": code, "message": message, "next_action": action})
    if not motor_count or not any(mid in motor_ids for mid in mids):
        require("motor_load_missing", "Motor hardware is not fully represented in the compiled graph.",
                "Reconcile source motor instances with graph and BOM.")
    if battery_v is None:
        require("battery_voltage_undeclared", "Battery nominal voltage is not declared.",
                "Identify the intended battery and its nominal/range voltage.")
    else:
        require("battery_supply_unverified",
                "Battery voltage is declared, not an identified or measured wired VMOTOR/MCU supply.",
                "Identify battery chemistry, measured loaded voltage range, source protection, connector polarity and allowable current.")
    if battery_mah is not None:
        # mAh is capacity, not discharge-current capability.
        require("battery_discharge_limit_unknown",
                "Declared battery mAh does not establish allowable continuous/peak discharge current.",
                "Obtain rated discharge specifications and verify source wiring, fusing and connector limits.")
    if any(v is None for v in rated):
        require("motor_voltage_unknown", "At least one motor lacks a declared rated voltage.",
                "Read motor markings/datasheet or characterize rated voltage conservatively.")
    elif battery_v is not None and any(battery_v > v for v in rated if v is not None):
        require("motor_rail_not_derived",
                "Declared battery nominal voltage exceeds at least one motor rating; no regulated or validated motor-terminal rail is established.",
                "Verify motor-terminal voltage under normal and transient operation and the driver drop/regulation strategy.")
    if not stall_known:
        require("motor_stall_current_unknown", "Motor stall current is missing for one or more declared motors.",
                "Obtain motor stall-current rating or independently characterize with protected measurement equipment.")
    require("driver_current_thermal_unverified",
            "Driver current/voltage-drop and thermal margins are not verified for the actual motor load.",
            "Check manufacturer data for the actual driver/package/heatsink, then measure driver drop and heating under a controlled load.")
    if "l298n" in active_drivers:
        require("l298_enable_and_logic_supply_unverified",
                "L298 uses separate motor and logic supplies and two enable controls; the catalog pin map does not prove real board ENA/ENB jumpers, current sensing or logic level margins.",
                "Inspect the exact driver board, verify ENA/ENB, logic VSS, motor VS, sense connections and ESP32-level compatibility.")
    elif not active_drivers:
        require("motor_driver_unresolved", "No supported motor-driver identity is represented in the graph.",
                "Identify or select an actual compatible driver, with provenance and operating ratings.")
    require("controller_power_unverified", "ESP32 rail/regulation and ground reference have not been physically established.",
            "Measure controller and motor rails and document common-reference routing before any energization.")
    require("physical_bench_authorization_missing",
            "An inferred graph and declared specifications are not a signed, independent bench verification.",
            "Resolve bench gates and attach physical measurements with instrument identity, timestamp and review.")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked",
        "authority": "declared_inputs_and_catalog_topology_only",
        "power_on_authorized": False,
        "sources": {
            "l298_manufacturer": L298_VENDOR,
            "l298_datasheet": "https://www.st.com/resource/en/datasheet/l298.pdf",
            "l298_datasheet_revision": "DS0218 Rev 5, October 2023, tables 3 and 4",
        },
        "driver_options": compare_motor_driver_options(
            battery_nominal_v=battery_v,
            motor_stall_current_a=stall,
            motor_count=motor_count,
        ),
        "manufacturer_reference": {
            "applicable_only_if_actual_driver_is_l298": True,
            "logic_supply_v_range": [4.5, 7.0],
            "enable_inputs": 2,
            "total_bridge_drop_at_1a_test_v": {"min": 1.8, "max": 3.2},
            "drop_test_conditions": "L298 datasheet table 4: VS=42V, VSS=5V, Tj=25C; load current=1A. NOT a measured value or prediction for this 0.9A motor.",
            "thermal_and_board_limits": "not characterized for the user's module or heatsink",
        } if "l298n" in active_drivers else None,
        "declared": {
            "battery_nominal_v": battery_v,
            "battery_capacity_mah": battery_mah,
            "motor_count": motor_count,
            "motor_rated_v": rated,
            "motor_stall_current_a": stall,
            "simultaneous_stall_current_a": simultaneous_stall_a,
            "current_interpretation": "sum of individually declared stall currents, not measured pack current or a safe operating point",
        },
        "compiled": {
            "motor_nodes": sum(mid in motor_ids for mid in mids),
            "driver_ids": active_drivers,
            "source_module_ids": source_nodes,
        },
        "measured": {
            "motor_rail_v": None, "controller_rail_v": None,
            "driver_drop_v": None, "driver_temperature_c": None,
            "battery_discharge_limit_a": None,
            "note": "No bench telemetry is independently authenticated by this report.",
        },
        "blockers": missing,
        "next_actions": [x["next_action"] for x in missing],
    }



def compare_motor_driver_options(
    *,
    battery_nominal_v: float | None,
    motor_stall_current_a: list[float | None],
    motor_count: int,
) -> dict[str, Any]:
    """Manufacturer-spec decision aid, never an automatic component substitution.

    Stall current is a transient worst-case declaration, not a continuous
    load. Do NOT compare stall amps to continuous ratings as a firm pass/fail.
    Ratings for DRV8833 are package- AND thermal- AND supply-dependent.
    """
    data = [
        {
            "id": "l298n_existing",
            "manufacturer": "ST",
            "part": "L298 dual full-bridge (existing graph)",
            "reference_url": "https://www.st.com/resource/en/datasheet/l298.pdf",
            "bridge_count": 2,
            "supply_nominal_within_spec": None,
            "max_current_continuous_a_at_reference": 2.0,
            "reference_conditions": "L298 datasheet; chip-level limits depend on heatsink, package, supply and junction temperature.",
            "loss_reference": "At 1 A, ST specifies 1.8–3.2 V total saturation drop, at VS=42 V, VSS=5 V, Tj=25 C.",
            "reference_driver_loss_w_at_1a": [1.8, 3.2],
            "reuse": "Only if the exact donor driver is independently identified as an L298; an unknown H-bridge is not an L298.",
            "tradeoff": "Potential salvage reuse, but comparatively high bipolar bridge drop and heat at load.",
            "selection": "conditional_incumbent",
        },
        {
            "id": "ti_drv8833_pwp_rty",
            "manufacturer": "Texas Instruments",
            "part": "DRV8833 PWP/RTY (HTSSOP or WQFN)",
            "reference_url": "https://www.ti.com/lit/ds/symlink/drv8833.pdf",
            "bridge_count": 2,
            "supply_nominal_within_spec": (2.7 <= battery_nominal_v <= 10.8) if battery_nominal_v is not None else None,
            "max_current_continuous_a_at_reference": 1.5,
            "current_peak_a_at_reference": 2.0,
            "reference_conditions": "VM=5 V, 25 C, PWP/RTY with adequate thermal design; NOT independently established at this battery, duty or board.",
            "loss_reference": "TI lists 360 mΩ high-side plus low-side on-resistance; 0.36 W at 1 A is an idealized R*I² reference only, not measured heat.",
            "reference_driver_loss_w_at_1a": [0.36, 0.36],
            "reuse": "New candidate purchase; not an automatic drop-in replacement for an L298N daughterboard.",
            "tradeoff": "Strong lower-loss FET bridge candidate; verify peak-duration, PCB/heatsink, VM range, logic, nSLEEP/current-limit and motor rail.",
            "selection": "candidate_for_validation",
        },
        {
            "id": "ti_drv8833_pw",
            "manufacturer": "Texas Instruments",
            "part": "DRV8833 PW (TSSOP)",
            "reference_url": "https://www.ti.com/lit/ds/symlink/drv8833.pdf",
            "bridge_count": 2,
            "supply_nominal_within_spec": (2.7 <= battery_nominal_v <= 10.8) if battery_nominal_v is not None else None,
            "max_current_continuous_a_at_reference": 0.5,
            "current_peak_a_at_reference": 2.0,
            "reference_conditions": "VM=5 V, 25 C; PW derated to 0.5 A RMS/DC continuous per bridge. Peak duration and thermal limits unproven.",
            "loss_reference": "Same die-class FET path, but lower continuous thermal allowance in PW packaging.",
            "reference_driver_loss_w_at_1a": None,
            "reuse": "New candidate purchase with restrictive continuous-current rating.",
            "tradeoff": "Do not select while actual motor running current, PWM duty and thermal behavior are unknown.",
            "selection": "needs_continuous_load_evidence",
        },
    ]
    stalls = [v for v in motor_stall_current_a if v is not None]
    peak_max_a = max(stalls) if stalls and len(stalls) == len(motor_stall_current_a) and motor_count > 0 else None
    for item in data:
        max_peak = item.get("current_peak_a_at_reference")
        item["declared_peak_below_manufacturer_peak_ref"] = (
            peak_max_a <= max_peak if peak_max_a is not None and max_peak is not None else None
        )
        item["usable_without_physical_checks"] = False
        item["motor_terminal_voltage_derived"] = False
    return {
        "status": "requires_physical_evidence",
        "scenario": {
            "battery_nominal_declared_v": battery_nominal_v,
            "motor_count": motor_count,
            "max_declared_motor_stall_a": peak_max_a,
            "continuous_motor_current_a": None,
            "actual_battery_voltage_range_v": None,
            "note": "Nominal VM compatibility is not battery full-charge compatibility or proof of acceptable 6-V motor-terminal voltage.",
        },
        "options": data,
        "recommended_next_evaluation": (
            "Compare a specifically identified donor L298 module against a DRV8833 PWP/RTY implementation "
            "on measured motor running/stall currents, loaded terminal voltage, heat, control and incremental cost. "
            "No candidate is selected for build."
        ),
        "competitive_value": "Explicit package-specific alternatives and conditional calculations replace a single unexamined catalog driver recipe.",
    }


def apply_rover_power_evidence_gate(
    package: Mapping[str, Any],
    *,
    intake: Mapping[str, Any] | None,
    graph: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Apply new rover-specific conditions to the current package verdict only."""
    result = copy.deepcopy(dict(package))
    build_id = str((result.get("info") or {}).get("build_id") or
                   (intake or {}).get("recommended_build_id") or "")
    report = evaluate_rover_power(intake=intake, graph=graph, project_build_id=build_id)
    result["rover_power_evidence"] = report
    if report["status"] != "blocked":
        return result

    gates = dict(result.get("gates") or {})
    gates["rover_power_evidence_status"] = "blocked"
    gates["verdict"] = "BLOCKED"
    gates["package_ready"] = False
    gates["build_ready"] = False
    gates["fabrication_ready"] = False
    # Historical bench observations remain untouched. The *current package*
    # cannot authorize powering hardware if its source/driver path is incomplete.
    gates["power_on_authorized"] = False
    blockers = list(gates.get("blockers") or [])
    for row in report["blockers"]:
        description = str(row["message"])
        if description not in blockers:
            blockers.append(description)
    gates["blockers"] = blockers[:60]
    next_actions = list(gates.get("next_actions") or [])
    for action in report["next_actions"]:
        if action not in next_actions:
            next_actions.append(action)
    gates["next_actions"] = next_actions[:25]
    result["gates"] = gates
    return result
