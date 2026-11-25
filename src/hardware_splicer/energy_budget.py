"""Energy budget for a battery and inverter system: loads, runtime, surge, DC current and the fuse window.

It adds up what the loads draw over a session, converts AC loads back through the inverter's efficiency and idle draw,
and compares the result with the battery's usable energy. It checks the inverter's continuous and surge ratings against the
loads, works out the DC current the inverter can pull at the battery's low voltage, and from that the smallest fuse and
the current the battery's BMS and cables must carry.

It sizes; it does not approve. Mains (AC) wiring can kill: anything with an AC side needs a certified inverter, residual
current protection and earthing done by a qualified electrician under local rules. HS has no cited cable ampacity table,
so it reports the current a cable must carry and leaves the cable choice to the cable maker's rating. Nothing here was
built or measured, and nothing changes any authority flag.

    PYTHONPATH=src python -m hardware_splicer.energy_budget spec.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

SCHEMA = "hardware_splicer.energy_budget.v1"
BOUNDARY = ("Sizing calculation from stated loads and ratings. Nothing was built or measured. Runtime and surge must be tested "
            "with the real loads, and AC wiring, residual current protection and earthing need a qualified electrician.")

# Usable fraction of rated capacity by chemistry, and the low voltage per nominal volt at which the battery is near empty.
CHEMISTRY = {
    "lifepo4": {"usable_fraction": 0.9, "low_v_ratio": 0.94, "why": "LiFePO4 is commonly cycled to about 90 % depth of discharge; about 12.0 V on a 12.8 V pack."},
    "li_ion": {"usable_fraction": 0.85, "low_v_ratio": 0.86, "why": "Li-ion NMC packs are commonly cycled to about 85 %; about 3.2 V per 3.7 V cell."},
    "lead_acid": {"usable_fraction": 0.5, "low_v_ratio": 0.96, "why": "Lead-acid and AGM lose cycle life fast below 50 % depth of discharge; about 11.5 V on 12 V."},
}
DEFAULTS = {
    "inverter_efficiency": (0.88, "Typical pure sine inverter efficiency near rated load; it is lower at light load."),
    "inverter_idle_w": (10.0, "No-load draw of a small inverter; read the real figure from its datasheet."),
    "fuse_factor": (1.25, "Fuse at least 125 % of the continuous current, the usual allowance for a continuous load."),
    "reserve_fraction": (0.1, "Energy kept in hand for cold, ageing and a longer night than planned."),
}


class EnergyBudgetError(ValueError):
    pass


def _num(value: Any, label: str, *, positive: bool = True, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise EnergyBudgetError(f"{label} must be a finite number")
    if positive and (value < 0 or (value == 0 and not allow_zero)):
        raise EnergyBudgetError(f"{label} must be greater than zero")
    return float(value)


def _value(spec: dict[str, Any], key: str, assumptions: dict[str, Any]) -> float:
    given = spec.get("assumptions", {}).get(key)
    if given is not None:
        assumptions[key] = {"value": _num(given, key, allow_zero=True), "given": True}
    else:
        value, why = DEFAULTS[key]
        assumptions[key] = {"value": value, "given": False, "why": why}
    return assumptions[key]["value"]


def check_energy(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise EnergyBudgetError("the spec must be an object")
    loads = spec.get("loads")
    if not isinstance(loads, list) or not loads:
        raise EnergyBudgetError("loads must be a non-empty list of {name, watts, hours, quantity, surge_watts, ac}")
    session_h = _num(spec.get("session_hours"), "session_hours")
    battery = spec.get("battery")
    if not isinstance(battery, dict):
        raise EnergyBudgetError("battery must give chemistry, nominal_v and capacity_ah")
    chem = battery.get("chemistry")
    if chem not in CHEMISTRY:
        raise EnergyBudgetError(f"battery.chemistry must be one of {sorted(CHEMISTRY)}")
    nominal_v = _num(battery.get("nominal_v"), "battery.nominal_v")
    capacity_ah = _num(battery.get("capacity_ah"), "battery.capacity_ah")
    bms_a = _num(battery["max_continuous_a"], "battery.max_continuous_a") if battery.get("max_continuous_a") is not None else None

    assumptions: dict[str, Any] = {}
    if battery.get("usable_fraction") is not None:
        usable = _num(battery["usable_fraction"], "battery.usable_fraction")
        assumptions["usable_fraction"] = {"value": usable, "given": True}
    else:
        usable = CHEMISTRY[chem]["usable_fraction"]
        assumptions["usable_fraction"] = {"value": usable, "given": False, "why": CHEMISTRY[chem]["why"]}
    low_v = nominal_v * CHEMISTRY[chem]["low_v_ratio"]
    assumptions["low_voltage_v"] = {"value": round(low_v, 2), "given": False, "why": CHEMISTRY[chem]["why"]}
    fuse_factor = _value(spec, "fuse_factor", assumptions)
    reserve = _value(spec, "reserve_fraction", assumptions)

    findings: list[dict[str, Any]] = []

    def finding(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    rows = []
    ac_wh = dc_wh = ac_peak = dc_peak = 0.0
    largest_start = (0.0, None)
    for i, load in enumerate(loads):
        if not isinstance(load, dict) or not isinstance(load.get("name"), str):
            raise EnergyBudgetError(f"loads[{i}] needs a name")
        watts = _num(load.get("watts"), f"loads[{i}].watts")
        hours = _num(load.get("hours"), f"loads[{i}].hours", allow_zero=True)
        qty = _num(load.get("quantity", 1), f"loads[{i}].quantity")
        if hours > session_h:
            raise EnergyBudgetError(f"loads[{i}] ({load['name']}) runs {hours:g} h, longer than the {session_h:g} h session")
        surge = _num(load["surge_watts"], f"loads[{i}].surge_watts") if load.get("surge_watts") is not None else watts
        if surge < watts:
            raise EnergyBudgetError(f"loads[{i}].surge_watts must be at least its running watts")
        ac = bool(load.get("ac", True))
        wh = watts * hours * qty
        if ac:
            ac_wh += wh
            ac_peak += watts * qty
            extra = surge - watts
            if extra > largest_start[0]:
                largest_start = (extra, load["name"])
        else:
            dc_wh += wh
            dc_peak += watts * qty
        rows.append({"name": load["name"], "ac": ac, "watts": watts, "quantity": qty, "hours": hours, "wh": round(wh, 1), "surge_watts": surge})

    results: dict[str, Any] = {"loads": rows, "ac_energy_wh": round(ac_wh, 1), "dc_energy_wh": round(dc_wh, 1),
                               "average_load_w": round((ac_wh + dc_wh) / session_h, 1)}
    inverter = spec.get("inverter")
    has_ac = ac_wh > 0 or ac_peak > 0
    battery_wh = dc_wh
    dc_current = dc_peak / low_v
    if has_ac:
        if not isinstance(inverter, dict):
            raise EnergyBudgetError("AC loads need an inverter with continuous_w and surge_w")
        inv_cont = _num(inverter.get("continuous_w"), "inverter.continuous_w")
        inv_surge = _num(inverter.get("surge_w"), "inverter.surge_w")
        if inverter.get("efficiency") is not None:
            eff = _num(inverter["efficiency"], "inverter.efficiency")
            assumptions["inverter_efficiency"] = {"value": eff, "given": True}
        else:
            eff = _value(spec, "inverter_efficiency", assumptions)
        if inverter.get("idle_w") is not None:
            idle = _num(inverter["idle_w"], "inverter.idle_w", allow_zero=True)
            assumptions["inverter_idle_w"] = {"value": idle, "given": True}
        else:
            idle = _value(spec, "inverter_idle_w", assumptions)
        if not 0 < eff <= 1:
            raise EnergyBudgetError("inverter efficiency must be between 0 and 1")
        battery_wh += ac_wh / eff + idle * session_h
        surge_need = ac_peak + largest_start[0]
        # The inverter can pull its full rating whatever the planned loads are, so the DC side is sized for that.
        inverter_dc_a = inv_cont / (low_v * eff)
        dc_current += inverter_dc_a
        results.update({"ac_peak_w": round(ac_peak, 1), "ac_surge_w": round(surge_need, 1), "largest_starting_load": largest_start[1],
                        "inverter_dc_current_at_rating_a": round(inverter_dc_a, 1)})
        if ac_peak > inv_cont:
            finding("error", "inverter_continuous_low", f"AC loads together draw {ac_peak:.0f} W but the inverter is rated {inv_cont:.0f} W continuous.")
        if surge_need > inv_surge:
            finding("error", "inverter_surge_low",
                    f"With every AC load on, starting {largest_start[1]} needs {surge_need:.0f} W; the inverter's surge rating is {inv_surge:.0f} W.")
        finding("error" if not inverter.get("certified") else "warning", "mains_safety",
                "The AC side is mains voltage and can kill. Use a certified inverter, add residual current protection and earthing, and have a "
                "qualified electrician wire and check it." + ("" if inverter.get("certified") else " The spec does not say the inverter is certified."))
    usable_wh = nominal_v * capacity_ah * usable
    needed_wh = battery_wh * (1 + reserve)
    fuse_min = dc_current * fuse_factor
    results.update({"battery_energy_needed_wh": round(battery_wh, 1), "battery_energy_with_reserve_wh": round(needed_wh, 1),
                    "battery_usable_wh": round(usable_wh, 1), "energy_margin_wh": round(usable_wh - needed_wh, 1),
                    "runtime_at_average_load_h": round(usable_wh / (battery_wh / session_h), 1) if battery_wh else None,
                    "max_dc_current_a": round(dc_current, 1), "fuse_min_a": round(fuse_min, 1),
                    "cable_must_carry_a": round(fuse_min, 1)})
    if needed_wh > usable_wh:
        finding("error", "battery_too_small", f"The session needs {needed_wh:.0f} Wh with reserve; the battery gives {usable_wh:.0f} Wh usable.")
    if bms_a is not None:
        results["battery_max_continuous_a"] = bms_a
        if dc_current > bms_a:
            finding("error", "bms_current_low", f"The DC side can draw {dc_current:.0f} A but the battery's BMS allows {bms_a:.0f} A continuous.")
    fuse = spec.get("fuse_a")
    if fuse is not None:
        fuse = _num(fuse, "fuse_a")
        if fuse < fuse_min:
            finding("error", "fuse_too_small", f"A {fuse:g} A fuse is under {fuse_min:.0f} A ({fuse_factor:g} x {dc_current:.0f} A) and will blow in normal use.")
        if bms_a is not None and fuse > bms_a * 2:
            finding("warning", "fuse_large", f"A {fuse:g} A fuse is more than twice the BMS's {bms_a:g} A; check the BMS's own short-circuit limit.")
    finding("info", "cable_choice", f"Choose battery cables the maker rates for at least {fuse_min:.0f} A at your length and temperature; HS has no cited ampacity table.")
    errors = sum(f["severity"] == "error" for f in findings)
    return {"schema_version": SCHEMA, "claim_boundary": BOUNDARY, "status": "CALCULATION_ONLY", "built": False, "build_ready": False,
            "assumptions": assumptions, "results": results, "findings": findings,
            "summary": {"errors": errors, "warnings": sum(f["severity"] == "warning" for f in findings)}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path, help="JSON spec: session_hours, loads, battery, inverter, fuse_a")
    args = ap.parse_args(argv)
    try:
        report = check_energy(json.loads(args.spec.read_text(encoding="utf-8")))
    except EnergyBudgetError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
