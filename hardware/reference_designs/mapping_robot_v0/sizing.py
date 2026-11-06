#!/usr/bin/env python3
"""Size the mapping robot with HS's own robotics simulation, from sourced part facts only.

``run_sizing`` turns the chosen parts (one per role) into the payload ``hardware_splicer.robotics_simulation`` reads,
runs it, and judges the result against the design's targets: 60 minutes of continuous mapping at 0.2 m/s with a speed
margin of at least 1.5. It adds the checks HS does not make: peak current from the pack and from the 5 V converter,
and the torque to climb a door threshold.

HS fills in defaults when a figure is missing (a DC motor at 6 V and 0.5 A, a robot of payload + 1 kg, a 0.25 A
baseline). Those would be silent guesses, so this script refuses to size a part that lacks a figure it needs, checks
the unit of every figure it reads, and always passes mass and baseline current explicitly. Every non-part figure comes
from ``assumptions`` with its basis. Worst cases are used throughout: where sources conflict, the lowest speed, torque,
capacity or voltage and the highest current; speed, torque and pack current are evaluated at the pack's minimum
operating voltage, energy at its nominal voltage.

The result is arithmetic over published and typical figures, not a measurement of a robot.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.robot_parts import load_parts  # noqa: E402
from hardware_splicer.robotics_simulation import build_robotics_simulation_packet  # noqa: E402

HERE = Path(__file__).resolve().parent
TARGETS = {"speed_mps": 0.2, "runtime_min": 60, "duty_cycle": 1.0, "min_speed_margin": 1.5}
ROLES = ("drive_motor", "wheel", "lidar", "battery_pack", "dc_dc_converter", "compute_board")
MASS_ROLES = {"drive_motor": 2, "wheel": 2, "lidar": 1, "battery_pack": 1, "compute_board": 1}
CONVERTER_MARGIN_A = 0.5  # REQUIREMENTS.md: 5 V rail rated above compute peak + LiDAR + 0.5 A
G = 9.81
LOWEST = {"output_free_speed_rpm", "stall_torque", "capacity", "nominal_voltage", "outer_diameter",
          "max_discharge_current", "max_output_current"}
HIGHEST = {"rated_current", "run_current", "stall_current", "no_load_current", "supply_current", "startup_current",
           "typical_current", "peak_current", "max_load_current", "supply_voltage", "full_voltage", "mass"}
UNITS = {"rated_voltage": "V", "output_free_speed_rpm": "rpm", "rated_current": "A", "run_current": "A",
         "stall_current": "A", "stall_torque": "N·m", "no_load_current": "A", "mass": "g", "outer_diameter": "mm",
         "supply_voltage": "V", "supply_current": "A", "startup_current": "A", "nominal_voltage": "V",
         "full_voltage": "V", "capacity": "mAh", "max_discharge_current": "A", "typical_current": "A",
         "peak_current": "A", "max_load_current": "A", "max_output_current": "A"}


class SizingError(ValueError):
    """A figure the sizing needs is not sourced, or is in the wrong unit, so sizing would rest on a guess."""


def _has(parts: dict[str, dict], role: str, name: str) -> bool:
    return name in parts.get(role, {}).get("facts", {})


def _value(parts: dict[str, dict], role: str, name: str) -> float:
    part = parts.get(role)
    if part is None:
        raise SizingError(f"no part selected for role {role}")
    fact = part.get("facts", {}).get(name)
    if fact is None:
        raise SizingError(f"{role} {part.get('id')}: {name} is not sourced; HS would substitute a default, so sizing stops")
    if name in UNITS and fact.get("unit") != UNITS[name]:
        raise SizingError(f"{role} {part.get('id')}: {name} is in {fact.get('unit')!r}, sizing reads it as {UNITS[name]}")
    if "alternatives" in fact:
        values = [float(a["value"]) for a in fact["alternatives"]]
        return max(values) if name in HIGHEST else min(values)
    return float(fact["value"])


def _assumed(assumptions: dict, name: str) -> float:
    if name not in assumptions:
        raise SizingError(f"assumption {name} is missing")
    return float(assumptions[name]["value"])


def load_selection(path: Path = HERE / "selection.json") -> dict[str, dict]:
    """The chosen part for each role, resolved through the part library."""
    chosen = json.loads(Path(path).read_text(encoding="utf-8"))
    library = {p["id"]: p for p in load_parts()}
    missing = [pid for pid in chosen.values() if pid not in library]
    if missing:
        raise SizingError(f"selection names parts that are not in the library: {missing}")
    return {role: library[pid] for role, pid in chosen.items()}


def build_payload(parts: dict[str, dict], assumptions: dict) -> tuple[dict, dict]:
    """HS robotics payload plus the effective figures it was built from."""
    pack_v = _value(parts, "battery_pack", "nominal_voltage")
    v_min = _assumed(assumptions, "min_operating_voltage")
    motor_v = _value(parts, "drive_motor", "rated_voltage")
    scale, scale_min = min(1.0, pack_v / motor_v), min(1.0, v_min / motor_v)  # DC motor speed and torque scale with voltage
    free_rpm = _value(parts, "drive_motor", "output_free_speed_rpm")
    stall_torque = _value(parts, "drive_motor", "stall_torque")
    run_fact = "run_current" if _has(parts, "drive_motor", "run_current") else "rated_current"
    eff = {
        "pack_nominal_voltage_v": pack_v, "pack_min_voltage_v": v_min, "motor_rated_voltage_v": motor_v,
        "motor_voltage_scale": scale, "motor_voltage_scale_at_min": scale_min,
        "motor_free_speed_rpm": free_rpm * scale, "motor_free_speed_rpm_at_min_voltage": free_rpm * scale_min,
        "motor_stall_torque_nm": stall_torque * scale, "motor_stall_torque_nm_at_min_voltage": stall_torque * scale_min,
        "motor_run_current_a": _value(parts, "drive_motor", run_fact),
        "motor_stall_current_a": _value(parts, "drive_motor", "stall_current"),
        "wheel_diameter_mm": _value(parts, "wheel", "outer_diameter"),
        "pack_capacity_mah": _value(parts, "battery_pack", "capacity"),
    }
    eff["motor_peak_current_a"] = min(eff["motor_stall_current_a"], _assumed(assumptions, "motor_current_limit_a"))

    lidar_v, compute_v = _value(parts, "lidar", "supply_voltage"), _value(parts, "compute_board", "supply_voltage")
    mcu_w = _assumed(assumptions, "mcu_power_w")
    electronics_w = (lidar_v * _value(parts, "lidar", "supply_current")
                     + compute_v * _value(parts, "compute_board", "typical_current") + mcu_w)
    lidar_peak = _value(parts, "lidar", "startup_current" if _has(parts, "lidar", "startup_current") else "supply_current")
    compute_peak = _value(parts, "compute_board",
                          "max_load_current" if _has(parts, "compute_board", "max_load_current") else "peak_current")
    eff["electronics_power_w"] = electronics_w
    eff["electronics_peak_power_w"] = lidar_v * lidar_peak + compute_v * compute_peak + mcu_w
    converter_eff = _assumed(assumptions, "converter_efficiency")
    eff["baseline_current_a"] = electronics_w / pack_v / converter_eff
    eff["converter_peak_current_a"] = compute_peak + lidar_peak + CONVERTER_MARGIN_A
    eff["pack_peak_current_a"] = 2 * eff["motor_peak_current_a"] + eff["electronics_peak_power_w"] / v_min / converter_eff
    grams = sum(_value(parts, role, "mass") * n for role, n in MASS_ROLES.items())
    eff["mass_kg"] = grams / 1000.0 + _assumed(assumptions, "chassis_mass_kg")

    def motor(side: str) -> dict:
        return {"id": f"{side}_drive", "name": f"{side} drive motor", "type": "dc_motor", "role": "drive",
                "free_speed_rpm": eff["motor_free_speed_rpm_at_min_voltage"],
                "stall_torque_nm": eff["motor_stall_torque_nm_at_min_voltage"],
                "current_a": eff["motor_run_current_a"], "stall_current_a": eff["motor_stall_current_a"],
                "voltage_v": pack_v}

    mobility = {"wheel_diameter_mm": eff["wheel_diameter_mm"]}
    payload = {
        "robotics_project": {
            "robot_class": "rover",
            "constraints": {"target_speed_mps": TARGETS["speed_mps"], "min_runtime_min": TARGETS["runtime_min"],
                            "mission_duty_cycle": TARGETS["duty_cycle"], "mass_kg": eff["mass_kg"],
                            "baseline_current_a": eff["baseline_current_a"]},
            "battery": {"nominal_voltage_v": pack_v, "capacity_mah": eff["pack_capacity_mah"],
                        "usable_fraction": _assumed(assumptions, "usable_fraction")},
            "mobility": mobility,
            "platform": {"type": "rover", "domains": ["locomotion"], "mobility": mobility},
        },
        "robotics_actuation": {"actuators": [motor("left"), motor("right")]},
    }
    return payload, eff


def _step_torque(parts: dict[str, dict], assumptions: dict, eff: dict) -> tuple[float, float]:
    """Torque per motor to climb the design's door threshold, and what the motor gives within its current limit."""
    r = eff["wheel_diameter_mm"] / 2000.0
    h = _assumed(assumptions, "step_height_mm") / 1000.0
    if not 0 < h < r:
        raise SizingError(f"step height {h * 1000} mm must be below the wheel radius {r * 1000} mm")
    push_per_load = math.sqrt(h * (2 * r - h)) / (r - h)  # horizontal force / vertical load to roll a wheel over a step
    load_n = eff["mass_kg"] * G * _assumed(assumptions, "drive_wheel_load_fraction")
    required = load_n * push_per_load * r / 2.0 * _assumed(assumptions, "step_torque_margin")
    no_load = _value(parts, "drive_motor", "no_load_current")
    kt = _value(parts, "drive_motor", "stall_torque") / (eff["motor_stall_current_a"] - no_load)
    available = min(eff["motor_stall_torque_nm_at_min_voltage"], kt * (eff["motor_peak_current_a"] - no_load))
    return required, available


def run_sizing(parts: dict[str, dict], assumptions: dict) -> dict:
    payload, eff = build_payload(parts, assumptions)
    step_required, step_available = _step_torque(parts, assumptions, eff)
    packet = build_robotics_simulation_packet(payload)
    runtime, drive = packet["runtime_estimate"], packet["drive_kinematics"]
    reasons, warnings = [], []
    if eff["pack_nominal_voltage_v"] > eff["motor_rated_voltage_v"]:
        reasons.append(f"pack nominal voltage {eff['pack_nominal_voltage_v']} V exceeds the motor rating "
                       f"{eff['motor_rated_voltage_v']} V")
    if _has(parts, "battery_pack", "full_voltage"):
        full = _value(parts, "battery_pack", "full_voltage")
        if full > eff["motor_rated_voltage_v"]:
            warnings.append(f"full charge {full} V is above the motor's {eff['motor_rated_voltage_v']} V rating; "
                            "limit PWM duty or accept slightly over-volted motors when the pack is full")
    if runtime.get("estimated_runtime_min", 0) < TARGETS["runtime_min"]:
        reasons.append(f"runtime {runtime.get('estimated_runtime_min')} min is below {TARGETS['runtime_min']} min")
    if drive.get("speed_margin", 0) < TARGETS["min_speed_margin"]:
        reasons.append(f"speed margin {drive.get('speed_margin')} at {eff['pack_min_voltage_v']} V is below "
                       f"{TARGETS['min_speed_margin']}")
    if drive.get("force_margin", 0) < 1.0:
        reasons.append(f"force margin {drive.get('force_margin')} is below 1")
    pack_limit = _value(parts, "battery_pack", "max_discharge_current")
    if eff["pack_peak_current_a"] > pack_limit:
        reasons.append(f"pack peak current {eff['pack_peak_current_a']:.2f} A exceeds its maximum discharge {pack_limit} A")
    converter_limit = _value(parts, "dc_dc_converter", "max_output_current")
    if eff["converter_peak_current_a"] > converter_limit:
        reasons.append(f"5 V converter peak {eff['converter_peak_current_a']:.2f} A exceeds its rating {converter_limit} A")
    if step_available < step_required:
        reasons.append(f"door threshold needs {step_required:.3f} N·m per motor; the motor gives {step_available:.3f} N·m "
                       "within its current limit")
    return {
        "runtime_min": runtime.get("estimated_runtime_min"), "runtime_margin": runtime.get("runtime_margin"),
        "average_power_w": runtime.get("average_power_w"), "required_wheel_rpm": drive.get("required_wheel_rpm"),
        "speed_margin": drive.get("speed_margin"), "required_force_n": drive.get("required_force_n"),
        "force_margin": drive.get("force_margin"), "mass_kg": eff["mass_kg"],
        "baseline_current_a": eff["baseline_current_a"], "pack_peak_current_a": eff["pack_peak_current_a"],
        "pack_max_discharge_a": pack_limit, "converter_peak_current_a": eff["converter_peak_current_a"],
        "converter_rating_a": converter_limit, "step_torque_required_nm": step_required,
        "step_torque_available_nm": step_available, "effective": eff, "assumptions": assumptions, "targets": TARGETS,
        "passed": not reasons, "reasons": reasons, "warnings": warnings, "hs_packet": packet,
    }


def minimum_requirements(result: dict) -> dict:
    """What a part must at least provide for the targets, derived from one sizing result."""
    usable = float(result["assumptions"]["usable_fraction"]["value"])
    wheel_r_m = result["effective"]["wheel_diameter_mm"] / 2000.0
    return {
        "min_motor_free_speed_rpm_at_pack_voltage": result["required_wheel_rpm"] * TARGETS["min_speed_margin"],
        "min_stall_torque_nm_per_motor": result["required_force_n"] * wheel_r_m / 2.0,
        "min_pack_energy_wh": result["average_power_w"] * TARGETS["runtime_min"] / 60.0 / usable,
    }


def main() -> int:
    assumptions = json.loads((HERE / "assumptions.json").read_text(encoding="utf-8"))
    chosen = load_selection()
    result = run_sizing({role: part for role, part in chosen.items() if role in ROLES}, assumptions)
    print(json.dumps({k: v for k, v in result.items() if k != "hs_packet"}, indent=1, default=str))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
