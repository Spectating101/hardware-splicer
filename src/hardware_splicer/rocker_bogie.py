"""Rocker-bogie statics: how a six-wheel rover's weight splits across its wheels, and the step its front wheels climb.

The rocker-bogie (NASA-JPL's Open Source Rover, Apache-2.0, and the Mars rovers) hangs each side on a rocker pivoted
to the body through a differential: the rocker's rear end carries a wheel and its front end carries a bogie, which
carries the front and middle wheels. Geometry is given along the rover's length (x, mm, forward positive):

* ``rocker_pivot_x``: where the rocker meets the body;
* ``rear_wheel_x``: the rear wheel on the rocker;
* ``bogie_pivot_x``: where the bogie hangs from the rocker;
* ``middle_wheel_x`` and ``front_wheel_x``: the bogie's two wheels.

Loads (flat ground, at rest, link masses folded into the body): each side carries half the weight at its rocker pivot
(the differential shares it), split between the rear wheel and the bogie pivot by moments about the rocker pivot, and
the bogie's share split between its wheels by moments about the bogie pivot.

Step climbing (quasi-static, one driven front wheel meeting a step of height h <= wheel radius r): the step edge touches
the wheel at angle theta from the bottom, cos(theta) = (r - h) / r. With the wheel at full traction on the edge
(friction mu times the edge's normal force N), lifting off the ground needs N (cos(theta) + mu sin(theta)) = N_f, the
wheel's share of the weight, and a push from the body P = N (sin(theta) - mu cos(theta)). The other five driven wheels
can supply at most mu (W - N_f). The highest h for which they can is reported. Above one wheel radius the bogie has to
lift the wheel, which this model does not cover; the result says so.

    PYTHONPATH=src python -m hardware_splicer.rocker_bogie spec.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any

SCHEMA = "hardware_splicer.rocker_bogie.v1"
G = 9.80665
BOUNDARY = ("Quasi-static rigid-wheel model with an assumed friction coefficient, link masses folded into the body, no wheel "
            "sinkage or slip dynamics. Climbing above one wheel radius depends on the bogie lifting the wheel and is not modelled. "
            "Test the built rover on a measured step.")


class RockerBogieError(ValueError):
    pass


def wheel_loads(geom: dict[str, float], mass_kg: float) -> dict[str, float]:
    xp, xr, xb, xm, xf = (float(geom[k]) for k in ("rocker_pivot_x", "rear_wheel_x", "bogie_pivot_x", "middle_wheel_x", "front_wheel_x"))
    if not (xr < xp < xb) or not (xm < xb < xf):
        raise RockerBogieError("geometry must run rear wheel < rocker pivot < bogie pivot, and middle wheel < bogie pivot < front wheel")
    side = mass_kg * G / 2
    rear = side * (xb - xp) / (xb - xr)
    bogie = side - rear
    front = bogie * (xb - xm) / (xf - xm)
    middle = bogie - front
    return {"rear_n": rear, "middle_n": middle, "front_n": front}


def step_push(h_mm: float, r_mm: float, n_front: float, mu: float) -> float:
    """Push the body must give the front wheel to lift it onto a step of height h (negative: it climbs on its own)."""
    theta = math.acos(max(-1.0, min(1.0, (r_mm - h_mm) / r_mm)))
    n_edge = n_front / (math.cos(theta) + mu * math.sin(theta))
    return n_edge * (math.sin(theta) - mu * math.cos(theta))


def max_step(r_mm: float, n_front: float, weight_n: float, mu: float) -> float:
    """Highest step (mm, at most the wheel radius) the other five driven wheels can push the front wheel onto."""
    available = mu * (weight_n - n_front)
    lo, hi = 0.0, r_mm
    if step_push(hi, r_mm, n_front, mu) <= available:
        return r_mm
    for _ in range(60):
        mid = (lo + hi) / 2
        if step_push(mid, r_mm, n_front, mu) <= available:
            lo = mid
        else:
            hi = mid
    return lo


def analyse(spec: dict[str, Any]) -> dict[str, Any]:
    try:
        geom, mass, wheel_d = spec["geometry"], float(spec["mass_kg"]), float(spec["wheel_mm"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RockerBogieError("spec needs geometry {rocker_pivot_x, rear_wheel_x, bogie_pivot_x, middle_wheel_x, front_wheel_x}, "
                               "mass_kg and wheel_mm") from exc
    if mass <= 0 or wheel_d <= 0:
        raise RockerBogieError("mass_kg and wheel_mm must be positive")
    loads = wheel_loads(geom, mass)
    weight = mass * G
    mus = spec.get("friction") or [0.5, 0.8]
    r = wheel_d / 2
    climb = {}
    for mu in mus:
        h = max_step(r, loads["front_n"], weight, float(mu))
        theta = math.acos((r - h) / r)
        n_edge = loads["front_n"] / (math.cos(theta) + mu * math.sin(theta))
        climb[str(mu)] = {"max_step_mm": round(h, 1), "limited_by_model": h >= r - 1e-6,
                          "front_wheel_torque_nm": round(mu * n_edge * r / 1000, 3)}
    shares = {k: round(v / (weight / 2), 3) for k, v in loads.items()}
    result = {"schema_version": SCHEMA, "claim_boundary": BOUNDARY, "inputs": {"geometry_mm": geom, "mass_kg": mass, "wheel_mm": wheel_d,
              "friction_assumed": mus}, "wheel_load_n_per_side": {k: round(v, 2) for k, v in loads.items()},
              "share_of_side_weight": shares, "step_climb": climb, "problems": []}
    if min(shares.values()) < 0.15:
        result["problems"].append(f"a wheel carries under 15% of its side's weight ({shares}): it will slip first; move the pivots")
    drive = spec.get("drive")
    if isinstance(drive, dict):
        from . import drive_sizing
        res = drive_sizing.size(mass, wheel_d, 6, float(drive.get("speed_m_s", 0.5)), float(drive.get("slope_deg", 15)))
        need = max(c["front_wheel_torque_nm"] for c in climb.values())
        options = []
        for o in res["passing"]:
            stall = o["slope_torque_share_of_stall"] and res["required"]["torque_per_motor_nm"]["slope"] / o["slope_torque_share_of_stall"]
            o = dict(o, step_torque_share_of_stall=round(need / stall, 3) if stall else None)
            options.append(o)
        # every option already reaches the speed; rank by margin on the step (a lower share of stall), unknown last
        options.sort(key=lambda o: (o["step_torque_share_of_stall"] is None, o["step_torque_share_of_stall"] or 0))
        result["drive"] = {"required": res["required"], "step_torque_needed_nm": need, "options": options[:8],
                           "options_checked": res["options_checked"], "sources": res["sources"]}
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    a = ap.parse_args(argv)
    try:
        out = analyse(json.loads(open(a.spec, encoding="utf-8").read()))
    except RockerBogieError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1))
    return 1 if out["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
