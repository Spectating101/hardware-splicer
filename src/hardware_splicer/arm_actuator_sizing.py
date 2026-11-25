"""Static joint loads for a serial arm with its own actuators counted, and an actuator pick from cited data.

    python -m hardware_splicer.arm_actuator_sizing --links 80,150,150,60,40,0 --payload-kg 0.5 \
        --safety-factor 1.5 --supply-v 12 --max-stall-share 0.5 [--link-g-per-m 150]

The worst static case is the arm stretched horizontally. The torque at joint i is gravity on everything beyond it:
the payload at the tip, each later actuator at its joint, and (if given) each link's own mass at its middle. The base
yaw joint is counted the same way, which is conservative.

Actuators come from ``data/actuators/cited_servos_*.json`` (each figure quoted from its maker's page). Those pages give
stall torque, which ROBOTIS itself calls "the maximum momentary torque output the servo is capable of", not a holding
rating; so a pick needs a maximum share of stall torque from you (``--max-stall-share``), and the result says it was
assumed. The pick works from the tip back to the base, because a joint's load depends only on what is beyond it, and
takes the lightest actuator that holds the load. Actuators without a published mass cannot be picked: their weight
would be a guess.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

SCHEMA = "hardware_splicer.arm_actuator_sizing.v1"
G = 9.80665
DATA = Path(__file__).resolve().parent / "data" / "actuators"
STALL_NOTE = ("ROBOTIS: 'Stall torque is the maximum momentary torque output the servo is capable of ... The actual real "
              "world performance of the servo will generally be closer to the performance graph measurements, not the rated "
              "stall torque.' (https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/)")


def cited_servo_rows(supply_v: float, path: Path | None = None) -> list[dict[str, Any]]:
    """One row per servo usable at this supply: stall torque at the highest listed voltage not above it."""
    path = path or sorted(DATA.glob("cited_servos_*.json"))[-1]
    rows = []
    for servo in json.loads(path.read_text())["servos"]:
        vin = servo.get("input_voltage_v")
        if vin and not (vin[0] <= supply_v <= vin[1]):
            continue
        points = [p for p in servo.get("stall", []) if p["voltage_v"] <= supply_v + 1e-9]
        if not points:
            continue
        point = max(points, key=lambda p: p["voltage_v"])
        rows.append({"component_id": servo["id"], "stall_torque_nm": point["torque_nm"], "at_voltage_v": point["voltage_v"],
                     "mass_kg": servo["mass_g"] / 1000 if servo.get("mass_g") else None, "source": servo["source"]["url"]})
    return rows


def joint_actuator_rows(supply_v: float, folder: Path | None = None) -> list[dict[str, Any]]:
    """Robot joint actuators (quasi-direct-drive, planetary, harmonic) from the CC BY 4.0 comparison dataset, keyed by
    the maker's rated (continuous) torque; only variants whose voltage is at or below the supply."""
    folder = folder or DATA / "joint_actuator_comparison" / "families"
    rows = []
    for path in sorted(folder.glob("*.json")):
        family = json.loads(path.read_text() or "{}")
        if not isinstance(family, dict):
            continue
        maker = family.get("shared", {}).get("manufacturer_en") or family.get("shared", {}).get("manufacturer")
        for v in family.get("variants", []):
            mech, elec = v.get("mechanical", {}), v.get("electrical", {})
            volts = elec.get("voltage_v")
            if not (mech.get("rated_torque_nm") and mech.get("weight_kg") and volts and volts <= supply_v + 1e-9):
                continue
            rows.append({"component_id": v["id"], "model": f"{maker} {v.get('model')}", "rated_torque_nm": mech["rated_torque_nm"],
                         "peak_torque_nm": mech.get("peak_torque_nm"), "mass_kg": mech["weight_kg"], "at_voltage_v": volts,
                         "source": "Dynamic Robot Joint Actuator Comparison dataset (CC BY 4.0), " + str(v.get("datasheet_url") or "")})
    return rows


def static_loads(links_mm: Sequence[float], payload_kg: float, actuator_kg: Sequence[float | None],
                 link_g_per_m: float | None = None) -> list[dict[str, Any]]:
    """Torque (N m) at each joint with the arm stretched horizontally. Joint k sits at the sum of the links before it."""
    n = len(links_mm)
    at = [sum(links_mm[:k]) / 1000 for k in range(n + 1)]  # joint positions; at[n] is the tip
    loads = []
    for i in range(n):
        parts = {"payload": payload_kg * G * (at[n] - at[i])}
        parts["actuators_beyond"] = sum((actuator_kg[k] or 0.0) * G * (at[k] - at[i]) for k in range(i + 1, n))
        if link_g_per_m:
            parts["links"] = sum(links_mm[k] / 1000 * link_g_per_m / 1000 * G * ((at[k] + at[k + 1]) / 2 - at[i]) for k in range(i, n))
        loads.append({"joint": i, "torque_nm": sum(parts.values()), "parts_nm": {k: round(v, 4) for k, v in parts.items()},
                      "unknown_actuator_mass_beyond": any(actuator_kg[k] is None for k in range(i + 1, n))})
    return loads


def pick(links_mm: Sequence[float], payload_kg: float, safety_factor: float, rows: Sequence[dict[str, Any]],
         max_stall_share: float, link_g_per_m: float | None = None, torque_key: str = "stall_torque_nm") -> dict[str, Any]:
    """``torque_key`` is stall_torque_nm for hobby/smart servos (then max_stall_share is your derating) or rated_torque_nm
    for joint actuators with a continuous rating (then pass a share of 1.0)."""
    usable = sorted((r for r in rows if r.get("mass_kg") and r.get(torque_key)), key=lambda r: (r["mass_kg"], r[torque_key]))
    n = len(links_mm)
    chosen: list[dict[str, Any] | None] = [None] * n
    masses: list[float | None] = [None] * n
    fail_at = None
    for i in reversed(range(n)):
        need = static_loads(links_mm, payload_kg, masses, link_g_per_m)[i]["torque_nm"] * safety_factor
        fit = next((r for r in usable if r[torque_key] * max_stall_share >= need), None)
        chosen[i] = fit
        if fit is None:
            fail_at = i
            break  # nothing beyond this point can be sized honestly
        masses[i] = fit["mass_kg"]
    loads = static_loads(links_mm, payload_kg, masses, link_g_per_m)
    joints = []
    for i in range(n):
        row, need = chosen[i], loads[i]["torque_nm"] * safety_factor
        joints.append({"joint": i, "link_mm": links_mm[i], "required_nm": round(need, 4), "load_parts_nm": loads[i]["parts_nm"],
                       "actuator": row and row["component_id"], "rating_nm": row and row[torque_key],
                       "rating_share": row and round(need / row[torque_key], 3), "mass_kg": row and row["mass_kg"],
                       "status": "picked" if row else ("no_cited_actuator_holds_it" if i == fail_at else "not_reached")})
    payload_only = [payload_kg * G * sum(links_mm[i:]) / 1000 * safety_factor for i in range(n)]
    return {
        "schema_version": SCHEMA, "feasible": all(j["status"] == "picked" for j in joints), "joints": joints,
        "actuator_mass_kg": round(sum(m for m in masses if m), 4),
        "payload_only_required_nm": [round(v, 4) for v in payload_only],
        "inputs": {"links_mm": list(links_mm), "payload_kg": payload_kg, "safety_factor": safety_factor,
                   "torque_rating": torque_key,
                   "max_share_of_rating": ({"value": max_stall_share, "basis": "assumed design rule, not a published rating", "why": STALL_NOTE}
                                           if torque_key == "stall_torque_nm" else {"value": max_stall_share, "basis": "given"}),
                   "link_g_per_m": {"value": link_g_per_m, "basis": "assumed" if link_g_per_m else "not counted"},
                   "actuators_considered": [r["component_id"] for r in rows],
                   "skipped_without_mass": [r["component_id"] for r in rows if not r.get("mass_kg")]},
        "claim_boundary": "Static holding torque, arm stretched horizontally. No acceleration, friction, gear efficiency or "
                          "shock; the brackets, cables and gripper are not counted unless given as link mass or payload.",
    }


def assess(links_mm: Sequence[float], payload_kg: float, actuator_ids: Sequence[str], rows: Sequence[dict[str, Any]],
           safety_factor: float = 1.0, mass_at_joint_kg: Sequence[float] | None = None,
           link_g_per_m: float | None = None) -> dict[str, Any]:
    """Share of stall torque each named actuator needs. ``mass_at_joint_kg`` overrides the actuator masses (e.g. a URDF's
    link masses, which include brackets) when you have better figures."""
    by_id = {r["component_id"]: r for r in rows}
    missing = [a for a in actuator_ids if a not in by_id]
    if missing:
        raise KeyError(f"no cited row for {missing}")
    masses = list(mass_at_joint_kg) if mass_at_joint_kg is not None else [by_id[a]["mass_kg"] for a in actuator_ids]
    loads = static_loads(links_mm, payload_kg, masses, link_g_per_m)
    return {"schema_version": SCHEMA, "joints": [
        {"joint": i, "actuator": a, "required_nm": round(loads[i]["torque_nm"] * safety_factor, 4), "stall_nm": by_id[a]["stall_torque_nm"],
         "stall_share": round(loads[i]["torque_nm"] * safety_factor / by_id[a]["stall_torque_nm"], 3), "load_parts_nm": loads[i]["parts_nm"]}
        for i, a in enumerate(actuator_ids)], "safety_factor": safety_factor, "why_share_matters": STALL_NOTE}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--links", required=True, help="comma-separated link lengths in mm, base to tip")
    parser.add_argument("--payload-kg", type=float, required=True)
    parser.add_argument("--safety-factor", type=float, default=1.0)
    parser.add_argument("--supply-v", type=float, required=True)
    parser.add_argument("--max-stall-share", type=float, required=True)
    parser.add_argument("--link-g-per-m", type=float, default=None)
    args = parser.parse_args(argv)
    links = [float(x) for x in args.links.split(",")]
    result = pick(links, args.payload_kg, args.safety_factor, cited_servo_rows(args.supply_v), args.max_stall_share, args.link_g_per_m)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
