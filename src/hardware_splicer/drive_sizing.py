"""Which cited gearmotors can drive a small wheeled rover: speed, torque and current against the maker's limits.

    python -m hardware_splicer.drive_sizing --mass-kg 2.5 --wheel-mm 80 --driven 2 --speed-m-s 0.6 --slope-deg 15

Per driven wheel, the force is the rover's weight along the slope, rolling resistance and acceleration, shared equally:

    F = m g (sin a + Crr cos a) + m acc;   torque per motor = F r / n

Each gearmotor is treated as a linear brushed DC motor between its no-load point and its stall point (the maker's table),
so at torque T it turns at rpm0 (1 - T/Ts) and draws I0 + (Is - I0) T/Ts. A ratio passes when

* cruising on the flat it reaches the target speed, its torque stays within the maker's continuous limit and its current
  within 25 % of stall (Pololu's general recommendation for brushed motors);
* on the slope its torque stays within the maker's instantaneous/intermittent limit and below stall.

Rolling resistance and acceleration are assumptions you can change; each result names its inputs and their basis.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

SCHEMA = "hardware_splicer.drive_sizing.v1"
G = 9.80665
KGCM_TO_NM = 0.0980665
DATA = Path(__file__).resolve().parent / "data" / "drive"
ASSUMED = {"crr": 0.03, "accel_m_s2": 0.3}  # small rubber wheels on floor or pavement; acceleration of a slow rover


def families(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or sorted(DATA.glob("pololu_gearmotors_*.json"))[-1]).read_text())


def size(mass_kg: float, wheel_mm: float, driven: int, speed_m_s: float, slope_deg: float,
         crr: float = ASSUMED["crr"], accel_m_s2: float = ASSUMED["accel_m_s2"], data: dict | None = None) -> dict[str, Any]:
    data = data or families()
    r = wheel_mm / 2000
    a = math.radians(slope_deg)
    flat_n = mass_kg * (G * crr + accel_m_s2)
    slope_n = mass_kg * (G * (math.sin(a) + crr * math.cos(a)) + accel_m_s2)
    flat_t, slope_t = flat_n * r / driven, slope_n * r / driven
    need_rpm = speed_m_s / (math.pi * wheel_mm / 1000) * 60
    options = []
    for fam in data["families"]:
        limits = fam["limits"]
        cont = limits.get("continuous_torque_kg_cm")
        peak = limits.get("intermittent_torque_kg_cm") or limits.get("instantaneous_torque_kg_cm")
        i0, i_s = fam["no_load_current_a"], fam["stall_current_a"]
        for row in fam["ratios"]:
            ts = row["stall_torque_kg_cm"] * KGCM_TO_NM
            rpm_flat = row["no_load_rpm"] * max(0.0, 1 - flat_t / ts)
            i_flat = i0 + (i_s - i0) * min(1.0, flat_t / ts)
            i_slope = i0 + (i_s - i0) * min(1.0, slope_t / ts)
            checks = {
                "reaches_speed": rpm_flat >= need_rpm,
                "flat_torque_within_continuous_limit": cont is None or flat_t <= cont * KGCM_TO_NM,
                "flat_current_within_25pct_stall": i_flat <= 0.25 * i_s,
                "slope_torque_within_peak_limit": peak is None or slope_t <= peak * KGCM_TO_NM,
                "slope_torque_below_stall": slope_t < ts,
            }
            if fam["id"].startswith("pololu-micro") and cont is None:
                checks["flat_torque_within_continuous_limit"] = None  # the page gives only an instantaneous limit
            options.append({"family": fam["id"], "ratio": row["ratio"], "url": fam["url"], "passes": all(v is not False for v in checks.values()),
                            "checks": checks, "rpm_at_cruise": round(rpm_flat), "speed_at_cruise_m_s": round(rpm_flat / 60 * math.pi * wheel_mm / 1000, 3),
                            "current_a": {"cruise_per_motor": round(i_flat, 3), "slope_per_motor": round(i_slope, 3), "stall": i_s},
                            "slope_torque_share_of_stall": round(slope_t / ts, 3)})
    passing = sorted((o for o in options if o["passes"]), key=lambda o: (o["current_a"]["cruise_per_motor"], -o["speed_at_cruise_m_s"]))
    return {
        "schema_version": SCHEMA,
        "required": {"wheel_rpm": round(need_rpm, 1), "torque_per_motor_nm": {"cruise": round(flat_t, 4), "slope": round(slope_t, 4)}},
        "passing": passing, "options_checked": len(options),
        "inputs": {"mass_kg": {"value": mass_kg, "basis": "given"}, "wheel_mm": {"value": wheel_mm, "basis": "given"},
                   "driven_wheels": {"value": driven, "basis": "given"}, "speed_m_s": {"value": speed_m_s, "basis": "given"},
                   "slope_deg": {"value": slope_deg, "basis": "given"},
                   "crr": {"value": crr, "basis": "assumed" if crr == ASSUMED["crr"] else "given"},
                   "accel_m_s2": {"value": accel_m_s2, "basis": "assumed" if accel_m_s2 == ASSUMED["accel_m_s2"] else "given"}},
        "sources": sorted({f["url"] for f in data["families"]}) + [data["current_rule"]["url"]],
        "claim_boundary": "Linear DC-motor model between the maker's no-load and (extrapolated) stall points at nominal voltage; "
                          "Pololu says units stall well before the listed point as they heat. No battery sag, wheel slip or turning losses.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mass-kg", type=float, required=True)
    parser.add_argument("--wheel-mm", type=float, required=True)
    parser.add_argument("--driven", type=int, default=2)
    parser.add_argument("--speed-m-s", type=float, required=True)
    parser.add_argument("--slope-deg", type=float, default=0.0)
    parser.add_argument("--crr", type=float, default=ASSUMED["crr"])
    parser.add_argument("--accel", type=float, default=ASSUMED["accel_m_s2"])
    args = parser.parse_args(argv)
    print(json.dumps(size(args.mass_kg, args.wheel_mm, args.driven, args.speed_m_s, args.slope_deg, args.crr, args.accel), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
