"""Multirotor propulsion check from a cited motor bench table.

Given the all-up mass, a rotor count, a motor and propeller bench table and the battery and ESC ratings, this works out
hover power and current, hover time, thrust-to-weight, the battery's current limit, ESC and motor margins and, when the
frame is given, whether neighbouring props overlap. It generalises the 3-inch proving-ground calculation
(``examples/drone_proving_ground/hs3g_design.py``) to any rotor count and any table in the same
``hs.drone_proving_ground.thrust_table.v1`` shape.

It never invents bench data: without a table that names its source it refuses. Inside the table's thrust range it
interpolates; below it, it extrapolates with the more pessimistic of a log-log fit and the momentum-theory power law and
says so; above it, the rotor cannot hover. Every number is a calculation from the table and the stated assumptions. Nothing
here was flown or bench tested, and nothing changes any authority flag.

    PYTHONPATH=src python -m hardware_splicer.propulsion_check spec.json [--table thrust.json]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA = "hardware_splicer.propulsion_check.v1"
TABLE_SCHEMA = "hs.drone_proving_ground.thrust_table.v1"
BOUNDARY = ("Calculation from a bench table and stated assumptions. Nothing was flown or bench tested here; hover time, "
            "thrust and current must be measured on the built aircraft, and flight needs the local rules and a safe test site.")

# Stated defaults. Each is reported back as an assumption when the spec does not give it.
DEFAULTS = {
    "nominal_cell_v": (3.7, "LiPo nominal cell voltage."),
    "usable_capacity_fraction": (0.8, "Land at about 3.7 V per cell under load; common LiPo practice."),
    "avionics_power_w": (4.0, "Flight controller, GPS, receiver and camera; not measured."),
    "air_density_kg_m3": (1.225, "ISA sea level. Hot or high sites have thinner air and need more power."),
    "min_tw_ratio": (2.0, "Lower bound for controllable flight with some wind margin; agile craft need far more."),
    "esc_margin": (1.2, "ESC continuous rating over the motor's full-throttle current; a common rule of thumb."),
    "min_tip_gap_mm": (10.0, "Gap between neighbouring prop discs."),
    "bench_voltage_tolerance": (0.10, "Largest relative difference between bench and pack voltage before the table stops applying."),
}
G = 9.80665
# Where bench data may come from. Anything else (a shop listing, a hand transcription, a model's memory) is reported as
# unverified, so the results cannot read as clean.
# maker_data_reseller_copy: the maker's own test table as a dealer reproduces it, when the maker's page cannot be fetched.
BENCH_SOURCE_CLASSES = {"maker_page", "maker_datasheet", "maker_data_reseller_copy", "independent_bench", "own_measurement"}
MAX_FIGURE_OF_MERIT = 0.85  # real small props reach roughly 0.5-0.75; a table implying more is suspect


class PropulsionCheckError(ValueError):
    pass


def _num(value: Any, label: str, *, positive: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PropulsionCheckError(f"{label} must be a finite number")
    if positive and value <= 0:
        raise PropulsionCheckError(f"{label} must be greater than zero")
    return float(value)


def _rows(table: Any, prop: str) -> tuple[list[dict[str, float]], dict[str, Any]]:
    if not isinstance(table, dict):
        raise PropulsionCheckError("thrust_table must be an object")
    if table.get("schema") != TABLE_SCHEMA:
        raise PropulsionCheckError(f"thrust_table.schema must be {TABLE_SCHEMA}")
    source = table.get("source")
    if not isinstance(source, str) or not source.startswith(("http://", "https://")):
        raise PropulsionCheckError("thrust_table.source must be the URL the bench data came from; HS does not size from unsourced tables")
    columns = table.get("columns")
    need = {"thrust_g", "voltage_v", "current_a"}  # throttle_pct is optional: many maker tables step by thrust instead
    if not isinstance(columns, list) or not need <= set(columns):
        raise PropulsionCheckError("thrust_table.columns must include " + ", ".join(sorted(need)))
    props = table.get("props")
    if not isinstance(props, dict) or prop not in props:
        raise PropulsionCheckError(f"thrust_table has no rows for prop {prop!r}; it has {sorted(props) if isinstance(props, dict) else []}")
    rows = []
    for index, raw in enumerate(props[prop]):
        if not isinstance(raw, list) or len(raw) != len(columns):
            raise PropulsionCheckError(f"row {index} for {prop!r} does not match the columns")
        row = {c: _num(v, f"row {index} {c}", positive=c not in {"throttle_pct"}) for c, v in zip(columns, raw) if c in need | {"throttle_pct", "power_w", "rpm"}}
        row.setdefault("power_w", row["voltage_v"] * row["current_a"])
        rows.append(row)
    if len(rows) < 2:
        raise PropulsionCheckError("the table needs at least two rows")
    rows.sort(key=lambda r: r["thrust_g"])
    if any(b["thrust_g"] <= a["thrust_g"] or b["power_w"] <= a["power_w"] for a, b in zip(rows, rows[1:])):
        raise PropulsionCheckError("thrust and power must both rise from row to row")
    meta = {"motor": table.get("motor"), "prop": prop, "source": source, "source_class": table.get("source_class"),
            "accessed": table.get("accessed"), "rows": len(rows)}
    return rows, meta


def _loglog(x0: float, y0: float, x1: float, y1: float, x: float) -> float:
    n = math.log(y1 / y0) / math.log(x1 / x0)
    return y0 * (x / x0) ** n


def _fit(rows: list[dict[str, float]]) -> tuple[float, float]:
    lx = [math.log(r["thrust_g"]) for r in rows]
    ly = [math.log(r["power_w"]) for r in rows]
    mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
    n = sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / sum((a - mx) ** 2 for a in lx)
    return math.exp(my - n * mx), n


def _power_at(rows: list[dict[str, float]], thrust_g: float) -> tuple[float, str, dict[str, Any]]:
    """Electrical power per motor at a thrust, and how it was obtained."""

    low, high = rows[0], rows[-1]
    if thrust_g > high["thrust_g"]:
        raise PropulsionCheckError("above_table")
    if thrust_g >= low["thrust_g"]:
        for a, b in zip(rows, rows[1:]):
            if a["thrust_g"] <= thrust_g <= b["thrust_g"]:
                power = _loglog(a["thrust_g"], a["power_w"], b["thrust_g"], b["power_w"], thrust_g)
                if "throttle_pct" not in a or "throttle_pct" not in b:
                    return power, "interpolated", {}
                throttle = a["throttle_pct"] + (b["throttle_pct"] - a["throttle_pct"]) * (thrust_g - a["thrust_g"]) / (b["thrust_g"] - a["thrust_g"])
                return power, "interpolated", {"throttle_pct": round(throttle, 1)}
    fit_rows = rows[: max(2, len(rows) // 2)]  # the lower half, nearest hover
    k, n = _fit(fit_rows)
    p_fit = k * thrust_g ** n
    p_15 = low["power_w"] * (thrust_g / low["thrust_g"]) ** 1.5
    return max(p_fit, p_15), "extrapolated", {"fit_exponent": round(n, 3), "power_fit_w": round(p_fit, 2), "power_n15_w": round(p_15, 2),
                                              "extrapolation_factor": round(low["thrust_g"] / thrust_g, 2), "upper_bound_power_w": round(min(p_fit, p_15), 2)}


def _value(spec: dict[str, Any], key: str, assumptions: dict[str, Any]) -> float:
    given = spec.get("assumptions", {}).get(key)
    if given is not None:
        assumptions[key] = {"value": _num(given, key), "given": True}
    else:
        value, why = DEFAULTS[key]
        assumptions[key] = {"value": value, "given": False, "why": why}
    return assumptions[key]["value"]


def _mass(spec: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    parts = spec.get("parts")
    if parts is not None:
        if not isinstance(parts, list) or not parts:
            raise PropulsionCheckError("parts must be a non-empty list")
        total = 0.0
        for i, p in enumerate(parts):
            if not isinstance(p, dict):
                raise PropulsionCheckError(f"parts[{i}] must be an object")
            total += _num(p.get("mass_g"), f"parts[{i}].mass_g") * _num(p.get("qty", 1), f"parts[{i}].qty")
        if "all_up_mass_g" in spec and abs(_num(spec["all_up_mass_g"], "all_up_mass_g") - total) > 0.5:
            raise PropulsionCheckError(f"all_up_mass_g {spec['all_up_mass_g']} does not match the parts, which sum to {round(total, 1)} g")
        return total, parts
    return _num(spec.get("all_up_mass_g"), "all_up_mass_g"), []


def check_propulsion(spec: Any, table: Any = None) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise PropulsionCheckError("the spec must be an object")
    table = table if table is not None else spec.get("thrust_table")
    rotors = spec.get("rotors", 4)
    if isinstance(rotors, bool) or not isinstance(rotors, int) or not 3 <= rotors <= 12:
        raise PropulsionCheckError("rotors must be a whole number from 3 to 12")
    rows, meta = _rows(table, str(spec.get("prop", "")))
    auw, _parts = _mass(spec)
    battery = spec.get("battery")
    if not isinstance(battery, dict):
        raise PropulsionCheckError("battery must give cells, capacity_mah and c_continuous")
    cells = battery.get("cells")
    if isinstance(cells, bool) or not isinstance(cells, int) or not 1 <= cells <= 14:
        raise PropulsionCheckError("battery.cells must be a whole number from 1 to 14")
    capacity_ah = _num(battery.get("capacity_mah"), "battery.capacity_mah") / 1000
    c_cont = _num(battery.get("c_continuous"), "battery.c_continuous")
    c_burst = _num(battery["c_burst"], "battery.c_burst") if battery.get("c_burst") is not None else None
    esc_a = _num(spec.get("esc_continuous_a"), "esc_continuous_a")
    motor_a = _num(spec["motor_max_current_a"], "motor_max_current_a") if spec.get("motor_max_current_a") is not None else None
    # The maker's rating, carried by the table from its source. A spec may tighten it but not loosen it: a higher figure typed
    # into the spec would otherwise silence the over-rating check.
    maker_a = _num(table["motor_max_current_a"], "thrust_table.motor_max_current_a") if isinstance(table, dict) and table.get("motor_max_current_a") is not None else None
    rating_raised = motor_a is not None and maker_a is not None and motor_a > maker_a
    if maker_a is not None:
        motor_a = maker_a if motor_a is None else min(motor_a, maker_a)

    assumptions: dict[str, Any] = {}
    v_cell = _value(spec, "nominal_cell_v", assumptions)
    usable = _value(spec, "usable_capacity_fraction", assumptions)
    avionics_w = _value(spec, "avionics_power_w", assumptions)
    rho = _value(spec, "air_density_kg_m3", assumptions)
    min_tw = _value(spec, "min_tw_ratio", assumptions)
    esc_margin_min = _value(spec, "esc_margin", assumptions)
    tip_gap_min = _value(spec, "min_tip_gap_mm", assumptions)
    v_tol = _value(spec, "bench_voltage_tolerance", assumptions)

    findings: list[dict[str, Any]] = []

    def finding(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    accessed = str(meta.get("accessed") or "")
    meta["verified"] = meta.get("source_class") in BENCH_SOURCE_CLASSES and re.fullmatch(r"\d{4}-\d{2}-\d{2}", accessed) is not None
    if not meta["verified"]:
        finding("warning", "table_unverified",
                f"The table's source class is {meta.get('source_class')!r} and its access date {accessed or 'missing'}; only "
                f"{', '.join(sorted(BENCH_SOURCE_CLASSES))} with an ISO access date count as bench data. Every result below inherits "
                "that uncertainty until the table is checked against the maker's chart or measured.")

    v_pack = cells * v_cell
    v_bench = sum(r["voltage_v"] for r in rows) / len(rows)
    if abs(v_bench - v_pack) / v_pack > v_tol:
        finding("error", "bench_voltage_mismatch",
                f"The table was measured at about {v_bench:.1f} V but a {cells}S pack is about {v_pack:.1f} V. Thrust and current do not "
                "carry across voltages; use a table measured on this cell count.")

    hover_g = auw / rotors
    results: dict[str, Any] = {"all_up_mass_g": round(auw, 1), "rotors": rotors, "hover_thrust_per_rotor_g": round(hover_g, 1),
                               "pack_nominal_v": round(v_pack, 2), "bench_voltage_v": round(v_bench, 2)}
    full = rows[-1]
    try:
        p_motor, how, detail = _power_at(rows, hover_g)
    except PropulsionCheckError:
        finding("error", "cannot_hover", f"Each rotor must lift {hover_g:.0f} g but the table tops out at {full['thrust_g']:.0f} g.")
        p_motor, how, detail = None, "above_table", {}
    results["hover_power_method"] = how
    results.update(detail)
    if how == "extrapolated":
        finding("warning", "hover_extrapolated",
                f"Hover needs {hover_g:.0f} g per rotor, below the table's lowest row ({rows[0]['thrust_g']:.0f} g). Hover power is the more "
                "pessimistic of two extrapolations; measure hover current before trusting the hover time.")
    if p_motor is not None:
        diameter = _num(spec["prop_diameter_mm"], "prop_diameter_mm") if spec.get("prop_diameter_mm") is not None else None
        if diameter is not None:
            area = math.pi * (diameter / 2000) ** 2
            p_ideal = (hover_g / 1000 * G) ** 1.5 / math.sqrt(2 * rho * area)
            fom = p_ideal / p_motor
            results["ideal_induced_power_per_rotor_w"] = round(p_ideal, 2)
            results["figure_of_merit_with_motor"] = round(fom, 3)
            if fom > MAX_FIGURE_OF_MERIT:
                finding("error", "implausible_table",
                        f"The table implies a hover figure of merit of {fom:.2f} including motor losses; real small props do not exceed about "
                        f"{MAX_FIGURE_OF_MERIT}. Check the table's units, prop and voltage.")
        i_hover = (rotors * p_motor + avionics_w) / v_pack
        hover_min = capacity_ah * usable / i_hover * 60
        results.update({"hover_power_per_rotor_w": round(p_motor, 2), "hover_current_a": round(i_hover, 2),
                        "hover_time_min": round(hover_min, 1), "hover_c_rate": round(i_hover / capacity_ah, 2)})
        if "upper_bound_power_w" in detail:
            i_up = (rotors * detail["upper_bound_power_w"] + avionics_w) / v_pack
            results["hover_time_upper_bound_min"] = round(capacity_ah * usable / i_up * 60, 1)
        need = spec.get("requirements", {}).get("min_hover_min")
        if need is not None and hover_min < _num(need, "requirements.min_hover_min"):
            finding("error", "hover_time_short", f"Hover time {hover_min:.1f} min is under the required {need} min.")

    i_full = rotors * full["current_a"] + avionics_w / v_pack
    tw = rotors * full["thrust_g"] / auw
    i_cont = c_cont * capacity_ah
    results.update({"max_thrust_total_g": round(rotors * full["thrust_g"], 1), "thrust_to_weight": round(tw, 2),
                    "full_throttle_current_a": round(i_full, 1), "battery_continuous_a": round(i_cont, 1),
                    "motor_full_throttle_current_a": full["current_a"], "esc_margin": round(esc_a / full["current_a"], 2)})
    if i_full > i_cont:
        limit = [r for r in rows if rotors * r["current_a"] + avionics_w / v_pack <= i_cont]
        if limit:
            top = max(limit, key=lambda r: r["thrust_g"])
            results.update({"battery_limited_throttle_pct": top.get("throttle_pct"), "battery_limited_thrust_per_rotor_g": top["thrust_g"],
                            "battery_limited_thrust_to_weight": round(rotors * top["thrust_g"] / auw, 2)})
        burst_note = ""
        if c_burst is not None:
            results["battery_burst_a"] = round(c_burst * capacity_ah, 1)
            burst_note = f" Its burst rating, {c_burst * capacity_ah:.0f} A, {'covers' if i_full <= c_burst * capacity_ah else 'does not cover'} short bursts."
        finding("warning", "battery_current_limited",
                f"Full throttle draws {i_full:.0f} A but the pack is rated {i_cont:.0f} A continuous.{burst_note}")
    effective_tw = results.get("battery_limited_thrust_to_weight", tw)
    if effective_tw < min_tw:
        finding("error", "thrust_to_weight_low", f"Thrust-to-weight {effective_tw:.2f} is under {min_tw}.")
    if esc_a / full["current_a"] < esc_margin_min:
        finding("error", "esc_undersized", f"The ESC's {esc_a:g} A continuous is under {esc_margin_min}x the motor's {full['current_a']:g} A at full throttle.")
    if rating_raised:
        finding("warning", "motor_rating_above_maker", f"The spec rates the motor at {spec['motor_max_current_a']:g} A but the table's source rates it at "
                f"{maker_a:g} A; the check uses the maker's {maker_a:g} A.")
    if motor_a is not None and full["current_a"] > motor_a:
        finding("error", "motor_over_rating", f"The table reaches {full['current_a']:g} A per motor, above the motor's {motor_a:g} A rating.")

    frame = spec.get("frame")
    if isinstance(frame, dict) and frame.get("wheelbase_mm") is not None and spec.get("prop_diameter_mm") is not None:
        wheelbase = _num(frame["wheelbase_mm"], "frame.wheelbase_mm")
        adjacent = wheelbase * math.sin(math.pi / rotors)  # motors evenly spaced on a circle of diameter wheelbase
        gap = adjacent - spec["prop_diameter_mm"]
        results.update({"adjacent_motor_distance_mm": round(adjacent, 1), "prop_tip_gap_mm": round(gap, 1)})
        if gap < tip_gap_min:
            finding("error", "props_overlap" if gap < 0 else "prop_gap_small",
                    f"Neighbouring props are {gap:.0f} mm apart at the tips; at least {tip_gap_min:g} mm is needed.")

    errors = sum(f["severity"] == "error" for f in findings)
    return {"schema_version": SCHEMA, "claim_boundary": BOUNDARY, "status": "CALCULATION_ONLY", "flight_tested": False,
            "flight_authorized": False, "table": meta, "assumptions": assumptions, "results": results, "findings": findings,
            "summary": {"errors": errors, "warnings": sum(f["severity"] == "warning" for f in findings)}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path, help="JSON spec: rotors, prop, all_up_mass_g or parts, battery, esc_continuous_a, ...")
    ap.add_argument("--table", type=Path, help=f"bench table JSON in the {TABLE_SCHEMA} shape, if the spec does not embed one")
    args = ap.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    table = json.loads(args.table.read_text(encoding="utf-8")) if args.table else None
    try:
        report = check_propulsion(spec, table)
    except PropulsionCheckError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
