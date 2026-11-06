#!/usr/bin/env python3
"""Size the mapping robot with HS's own robotics simulation, from sourced part facts only.

``run_sizing`` turns the chosen parts (one per role) into the payload ``hardware_splicer.robotics_simulation`` reads,
runs it, and judges the result against the design's targets: 60 minutes of continuous mapping at 0.2 m/s with a speed
margin of at least 1.5.

HS fills in defaults when a figure is missing (a DC motor at 6 V and 0.5 A, a robot of payload + 1 kg, a 0.25 A
baseline). Those would be silent guesses, so this script refuses to size a part that lacks a figure it needs, and
always passes mass and baseline current explicitly. Every non-part figure comes from ``assumptions`` with its basis.
Where sources conflict, the worst case is used: the lowest speed, torque, capacity or voltage, the highest current.

The result is arithmetic over published figures, not a measurement of a robot.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.robot_parts import load_parts  # noqa: E402
from hardware_splicer.robotics_simulation import build_robotics_simulation_packet  # noqa: E402

HERE = Path(__file__).resolve().parent
TARGETS = {"speed_mps": 0.2, "runtime_min": 60, "duty_cycle": 1.0, "min_speed_margin": 1.5}
ROLES = ("drive_motor", "wheel", "lidar", "battery_pack", "dc_dc_converter", "compute_board")
MASS_ROLES = {"drive_motor": 2, "wheel": 2, "lidar": 1, "battery_pack": 1, "compute_board": 1}
LOWEST = {"output_free_speed_rpm", "stall_torque", "capacity", "nominal_voltage", "outer_diameter"}
HIGHEST = {"rated_current", "run_current", "stall_current", "supply_current", "typical_current", "mass"}


class SizingError(ValueError):
    """A figure the sizing needs is not sourced, so sizing would rest on a guess."""


def _value(parts: dict[str, dict], role: str, name: str) -> float:
    part = parts.get(role)
    if part is None:
        raise SizingError(f"no part selected for role {role}")
    fact = part.get("facts", {}).get(name)
    if fact is None:
        raise SizingError(f"{role} {part.get('id')}: {name} is not sourced; HS would substitute a default, so sizing stops")
    if "alternatives" in fact:
        values = [float(a["value"]) for a in fact["alternatives"]]
        return min(values) if name in LOWEST else max(values) if name in HIGHEST else min(values)
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
    motor_v = _value(parts, "drive_motor", "rated_voltage")
    scale = min(1.0, pack_v / motor_v)  # a DC motor's speed and torque scale with its supply voltage
    eff = {
        "pack_nominal_voltage_v": pack_v, "motor_rated_voltage_v": motor_v, "motor_voltage_scale": scale,
        "motor_free_speed_rpm": _value(parts, "drive_motor", "output_free_speed_rpm") * scale,
        "motor_stall_torque_nm": _value(parts, "drive_motor", "stall_torque") * scale,
        # current at the mapping load when a source or derivation gives it; otherwise the rated-load current
        "motor_run_current_a": _value(parts, "drive_motor",
                                      "run_current" if "run_current" in parts["drive_motor"].get("facts", {}) else "rated_current"),
        "motor_stall_current_a": _value(parts, "drive_motor", "stall_current"),
        "wheel_diameter_mm": _value(parts, "wheel", "outer_diameter"),
        "pack_capacity_mah": _value(parts, "battery_pack", "capacity"),
    }
    electronics_w = (_value(parts, "lidar", "supply_voltage") * _value(parts, "lidar", "supply_current")
                     + _value(parts, "compute_board", "supply_voltage") * _value(parts, "compute_board", "typical_current")
                     + _assumed(assumptions, "mcu_power_w"))
    eff["electronics_power_w"] = electronics_w
    eff["baseline_current_a"] = electronics_w / pack_v / _assumed(assumptions, "converter_efficiency")
    grams = sum(_value(parts, role, "mass") * n for role, n in MASS_ROLES.items())
    eff["mass_kg"] = grams / 1000.0 + _assumed(assumptions, "chassis_mass_kg")

    def motor(side: str) -> dict:
        return {"id": f"{side}_drive", "name": f"{side} drive motor", "type": "dc_motor", "role": "drive",
                "free_speed_rpm": eff["motor_free_speed_rpm"], "stall_torque_nm": eff["motor_stall_torque_nm"],
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


def run_sizing(parts: dict[str, dict], assumptions: dict) -> dict:
    payload, eff = build_payload(parts, assumptions)
    packet = build_robotics_simulation_packet(payload)
    runtime, drive = packet["runtime_estimate"], packet["drive_kinematics"]
    reasons = []
    if eff["pack_nominal_voltage_v"] > eff["motor_rated_voltage_v"]:
        reasons.append(f"pack nominal voltage {eff['pack_nominal_voltage_v']} V exceeds the motor rating "
                       f"{eff['motor_rated_voltage_v']} V")
    if runtime.get("estimated_runtime_min", 0) < TARGETS["runtime_min"]:
        reasons.append(f"runtime {runtime.get('estimated_runtime_min')} min is below {TARGETS['runtime_min']} min")
    if drive.get("speed_margin", 0) < TARGETS["min_speed_margin"]:
        reasons.append(f"speed margin {drive.get('speed_margin')} is below {TARGETS['min_speed_margin']}")
    if drive.get("force_margin", 0) < 1.0:
        reasons.append(f"force margin {drive.get('force_margin')} is below 1")
    return {
        "runtime_min": runtime.get("estimated_runtime_min"), "runtime_margin": runtime.get("runtime_margin"),
        "average_power_w": runtime.get("average_power_w"), "required_wheel_rpm": drive.get("required_wheel_rpm"),
        "speed_margin": drive.get("speed_margin"), "required_force_n": drive.get("required_force_n"),
        "force_margin": drive.get("force_margin"), "mass_kg": eff["mass_kg"],
        "baseline_current_a": eff["baseline_current_a"], "effective": eff, "assumptions": assumptions,
        "targets": TARGETS, "passed": not reasons, "reasons": reasons, "hs_packet": packet,
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
    result = run_sizing(load_selection(), assumptions)
    print(json.dumps({k: v for k, v in result.items() if k != "hs_packet"}, indent=1, default=str))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
