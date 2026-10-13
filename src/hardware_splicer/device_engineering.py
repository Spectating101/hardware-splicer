"""A quantified engineering review of a device plan: electrical, power, thermal, RF, mechanical and printing.

The plan says what goes where. This asks what that layout implies and puts numbers on it, with the rules the rest of this
project follows:

* every figure is either **sourced** (a datasheet table or a standard, named below) or an **assumption** that is listed with
  its range and can be changed, never a silent guess;
* a check can say a limit is exceeded or that something needs attention. It never says a design works. A number under a limit
  is reported as "within the limit under the stated assumptions", and where the number is only a floor it says so;
* what was not assessed is listed beside what was.

It reads the plan only. It changes no wiring and approves no building, powering or release.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .device_plan import DevicePlanError, build_device_plan, module_library

SCHEMA = "hardware_splicer.device_engineering_review.v1"
AUTHORITY = (
    "An estimate from catalogued figures and stated assumptions. It reports limits that are exceeded and things that need "
    "checking. It does not show that a design works, and it approves no building, powering or release."
)

# Statuses. Deliberately no "pass".
EXCEEDS = "exceeds_limit"
WITHIN = "within_limit_under_assumptions"
ADVISORY = "advisory"
NOT_ASSESSED = "not_assessed"

UM10204 = "NXP UM10204, I2C-bus specification and user manual"
UM10204_URL = "https://www.nxp.com/docs/en/user-guide/UM10204.pdf"

# Facts about standards, not about any part. Facts about parts live in the module library (``engineering`` and
# ``i2c.pullups``), each with the page or table it came from, so adding a part adds data and no code here.
STANDARDS = {
    "i2c_tr_max_ns": (1000, "ns", f"{UM10204}, Table 10, Standard-mode tr maximum", UM10204_URL),
    "i2c_vol_max_v": (0.4, "V", f"{UM10204}, Table 10, VOL1 maximum at 3 mA sink", UM10204_URL),
    "i2c_iol_ma": (3.0, "mA", f"{UM10204}, Table 10, IOL minimum at VOL = 0.4 V", UM10204_URL),
    "i2c_cb_max_pf": (400, "pF", f"{UM10204}, Table 10, Cb maximum", UM10204_URL),
    "i2c_ci_max_pf": (10, "pF", f"{UM10204}, Table 10, Ci maximum per I/O pin", UM10204_URL),
    "i2c_rise_factor": (0.8473, "", f"{UM10204}, section 7.1, t2 - t1 = 0.8473 x RC", UM10204_URL),
}
GENERAL = "general practice, not from a datasheet"

# Assumptions, with a range where the true value varies. All can be questioned and none is a measurement.
ASSUMED = {
    "wire_pf_per_m": ((30.0, 100.0), "pF/m", f"capacitance of a loose jumper wire; {GENERAL}"),
    "usb_input_v": (5.0, "V", "nominal USB bus voltage"),
    "convection_w_per_m2k": ((5.0, 10.0), "W/m2K", f"natural convection from a small box in still air; {GENERAL}"),
    "ambient_c": ((25.0, 40.0), "C", "a room and a warm room or a car in summer; change to your use"),
    "usb_port_budget_ma": (500, "mA", f"a standard USB 2.0 port; {GENERAL}"),
    "print_tolerance_mm": (0.3, "mm", f"dimensional accuracy of a desktop FDM printer, each way; {GENERAL}"),
    "nozzle_mm": (0.4, "mm", "the most common nozzle"),
    "bridge_limit_mm": (20.0, "mm", f"a span that prints cleanly without support on a tuned printer; {GENERAL}"),
    "pla_density_g_cm3": (1.24, "g/cm3", f"PLA; {GENERAL}"),
}
SOURCED = STANDARDS  # kept so callers and tests can still list the fixed, sourced constants


def _src(key: str) -> dict[str, Any]:
    value, unit, basis, url = STANDARDS[key]
    return {"name": key, "value": value, "unit": unit, "basis": "sourced", "source": basis, "url": url}


def _asm(key: str) -> dict[str, Any]:
    value, unit, basis = ASSUMED[key]
    return {"name": key, "value": list(value) if isinstance(value, tuple) else value, "unit": unit, "basis": "assumed", "source": basis}


def _fact(module: dict[str, Any], name: str, value: Any, unit: str, locator: str, url: str) -> dict[str, Any]:
    """A figure read from a module's library entry, with where in which document it was read."""
    return {"name": f"{module['id']}.{name}", "value": value, "unit": unit, "basis": "sourced", "source": f"{module['name']}: {locator}", "url": url}


def _check(check_id: str, title: str, status: str, summary: str, quantities: dict[str, Any], inputs: list[dict[str, Any]],
           limits: list[str] | None = None) -> dict[str, Any]:
    return {"id": check_id, "title": title, "status": status, "summary": summary, "quantities": quantities, "inputs": inputs,
            "limits": limits or []}


def _r(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def _far_x(module: dict[str, Any], key: str = "antenna_end") -> float:
    """The module's +x extent including an end that overhangs its board, as the plan's own antenna finding measures it."""

    return module["box"]["x1"] + module.get("overhang_mm", {}).get(key, 0.0)


def _roles(plan: dict[str, Any]) -> dict[tuple[str, str], list[str]]:
    return {(m["id"], p["id"]): p["roles"] for m in plan["modules"] for p in m["pins"]}


def _entries(plan: dict[str, Any], library: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Each placed module with its library entry."""
    return [(m, library[m["module"]]) for m in plan["modules"]]


# --- electrical -------------------------------------------------------------------------------------------------------

def _i2c_bus(plan: dict[str, Any], library: dict[str, Any]) -> dict[str, Any]:
    roles = _roles(plan)
    lines: dict[str, list[dict[str, Any]]] = {"sda": [], "scl": []}
    for wire in plan["wires"]:
        for line in lines:
            ends = [roles[(wire[end]["module"], wire[end]["pin_id"])] for end in ("from", "to")]
            if any(role.endswith(line) or role.endswith(line + "_default") for role_list in ends for role in role_list):
                lines[line].append(wire)
    if not lines["sda"] or not lines["scl"]:
        return _check("i2c_bus", "I2C bus loading", NOT_ASSESSED, "No wired I2C bus in this plan.", {}, [])
    mcu_ids = {m["id"] for m in plan["modules"] if m["kind"] == "mcu_board"}
    i2c_modules = sorted({w[end]["module"] for line in lines.values() for w in line for end in ("from", "to")} - mcu_ids)
    by_id = {m["id"]: library[m["module"]] for m in plan["modules"]}
    known, unknown, facts = [], [], []
    for ref in i2c_modules:
        pullups = by_id[ref].get("i2c", {}).get("pullups")
        if pullups:
            known.append((ref, int(pullups["ohm"])))
            facts.append({"name": f"{ref}.pullups", "value": pullups["ohm"], "unit": "ohm", "basis": "sourced",
                          "source": f"{by_id[ref]['name']}: \"{pullups['quote']}\"", "url": pullups["source"]})
        else:
            unknown.append(ref)
    wire_m = {line: sum(w["curve_mm"] for w in wires) / 1000 for line, wires in lines.items()}
    ci = STANDARDS["i2c_ci_max_pf"][0]
    pins_on_line = len(i2c_modules) + 1  # each module plus the controller
    low, high = ASSUMED["wire_pf_per_m"][0]
    tr = STANDARDS["i2c_tr_max_ns"][0] * 1e-9
    k = STANDARDS["i2c_rise_factor"][0]
    mcu = next(m for m in plan["modules"] if m["kind"] == "mcu_board")
    vdd_v = library[mcu["module"]]["electrical"]["io_v"]
    rp_min = (vdd_v - STANDARDS["i2c_vol_max_v"][0]) / (STANDARDS["i2c_iol_ma"][0] / 1000)
    cb = {line: (_r(wire_m[line] * low + pins_on_line * ci, 1), _r(wire_m[line] * high + pins_on_line * ci, 1)) for line in lines}
    worst = max(cb[line][1] for line in lines)
    best = max(cb[line][0] for line in lines)
    inputs = [_src(key) for key in ("i2c_tr_max_ns", "i2c_vol_max_v", "i2c_iol_ma", "i2c_cb_max_pf", "i2c_ci_max_pf", "i2c_rise_factor")]
    inputs += [_asm("wire_pf_per_m"), {"name": "io_v", "value": vdd_v, "unit": "V", "basis": "sourced", "source": "module library, the controller's electrical.io_v"}, *facts]
    quantities: dict[str, Any] = {
        "wire_length_m": {line: _r(wire_m[line], 3) for line in lines},
        "bus_capacitance_pf_estimate": {"low": _r(best, 1), "high": _r(worst, 1), "limit": STANDARDS["i2c_cb_max_pf"][0]},
        "rp_min_ohm": _r(rp_min, 0),
        "pullups_known": [{"module": ref, "ohm": ohm} for ref, ohm in known],
        "pullups_unknown": unknown,
    }
    if not known:
        return _check("i2c_bus", "I2C bus loading", NOT_ASSESSED,
                      f"No module on this bus states its pull-up value, so the rise time cannot be checked. Estimated bus capacitance is {best:g} to {worst:g} pF "
                      f"against the {STANDARDS['i2c_cb_max_pf'][0]} pF limit.", quantities, inputs,
                      ["Pull-ups on the modules that do not state them are unknown, and an unknown pull-up is not a pass."])
    rp_eff = 1 / sum(1 / ohm for _, ohm in known)
    tolerated = tr / (k * rp_eff) * 1e12
    rp_max_low, rp_max_high = tr / (k * best * 1e-12), tr / (k * worst * 1e-12)
    quantities.update({"rp_effective_ohm": _r(rp_eff, 0), "bus_capacitance_tolerated_pf": _r(tolerated, 1),
                       "rp_max_ohm": {"at_low_capacitance": _r(rp_max_low, 0), "at_high_capacitance": _r(rp_max_high, 0)}})
    limits = ["Wire capacitance is assumed. Measure or shorten the wires if the margin is thin.",
              "Pull-ups on the modules that do not state a value are not included, so the real resistance is lower than shown."
              if unknown else "Only the stated pull-ups are counted; the controller's own are ignored."]
    if rp_eff < rp_min:
        status, text = EXCEEDS, f"The stated pull-ups in parallel are {rp_eff:.0f} ohm, below the {rp_min:.0f} ohm a device can sink at {STANDARDS['i2c_vol_max_v'][0]} V."
    elif tolerated < best:
        status, text = EXCEEDS, f"The bus can carry {tolerated:.0f} pF at {rp_eff:.0f} ohm, but even the low estimate is {best:g} pF."
    elif tolerated < worst:
        status, text = ADVISORY, f"The bus can carry {tolerated:.0f} pF at {rp_eff:.0f} ohm; the estimate runs {best:g} to {worst:g} pF, so wire capacitance decides."
    else:
        status, text = WITHIN, f"At {rp_eff:.0f} ohm the bus can carry {tolerated:.0f} pF; the estimate is {best:g} to {worst:g} pF."
    return _check("i2c_bus", "I2C bus loading", status, text + " At 100 kHz (the rise time limit of Standard-mode).", quantities, inputs, limits)


def _loads(plan: dict[str, Any], library: dict[str, Any]) -> dict[str, Any]:
    """Currents from the rows the library sources. Sustained and peak mA are an upper bound on what a USB port supplies (every
    row counted at 1:1, as a linear regulator would draw it); the watts are a floor on the heat (each row at the rail it was
    measured on, with no conversion loss)."""

    totals = {"sustained_ma": 0.0, "peak_ma": 0.0, "sustained_w": 0.0, "peak_w": 0.0}
    missing: list[str] = []
    facts: list[dict[str, Any]] = []
    for module, entry in _entries(plan, library):
        rows = entry.get("engineering", {}).get("loads", [])
        if not rows:
            missing.append(module["id"])
            continue
        sus = [r for r in rows if r["kind"] == "sustained"]
        if sus:
            top = max(sus, key=lambda r: r["typical_ma"])
            totals["sustained_ma"] += top["typical_ma"]
            totals["sustained_w"] += top["typical_ma"] * top["rail_v"] / 1000
        hi = max(rows, key=lambda r: r.get("max_ma", r["typical_ma"]) * r["rail_v"])
        totals["peak_ma"] += max(r.get("max_ma", r["typical_ma"]) for r in rows)
        totals["peak_w"] += hi.get("max_ma", hi["typical_ma"]) * hi["rail_v"] / 1000
        for row in rows:
            facts.append(_fact(entry, f"load.{row['kind']}", row.get("max_ma", row["typical_ma"]), "mA",
                               f"{row['mode']} at {row['rail_v']:g} V ({row['locator']}; {row['conditions']})", row["source"]))
    return {**totals, "missing": missing, "facts": facts}


def _power_stage(plan: dict[str, Any], library: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    mcu_entry = next(en for m, en in _entries(plan, library) if m["kind"] == "mcu_board")
    return mcu_entry.get("engineering", {}).get("power_stage"), mcu_entry


def _supply(plan: dict[str, Any], library: dict[str, Any]) -> dict[str, Any]:
    load = _loads(plan, library)
    peak, missing = load["peak_ma"], load["missing"]
    budget = ASSUMED["usb_port_budget_ma"][0]
    stage, mcu_entry = _power_stage(plan, library)
    needs = mcu_entry.get("engineering", {}).get("supply_min_a")
    inputs = [_asm("usb_port_budget_ma"), *load["facts"]]
    if needs:
        inputs.append(_fact(mcu_entry, "supply_min_a", needs["value"], "A", needs["locator"], needs["source"]))
    if stage:
        inputs.append(_fact(mcu_entry, "power_stage", stage["kind"], "", f"{stage['note']} ({stage['locator']})", stage["source"]))
    quantities: dict[str, Any] = {
        "sourced_peak_ma_upper_bound": _r(peak, 3), "sourced_sustained_ma_upper_bound": _r(load["sustained_ma"], 3), "usb_budget_ma": budget,
        "headroom_for_unsourced_loads_ma_at_least": _r(budget - peak, 3),
        "modules_without_a_sourced_current": missing,
        "regulator": stage["kind"] if stage else "not stated",
    }
    if needs:
        quantities["controller_requires_supply_a"] = needs["value"]
    summary = (
        f"The sourced loads total at most {peak:g} mA at the USB port at their peak. A {budget} mA port leaves at least {budget - peak:g} mA for everything without a sourced current "
        f"({', '.join(missing) or 'none'}), the USB bridge and the regulator's own draw."
    )
    limits = [
        "Each current is counted as it would be through a linear regulator, which is the most a port can be asked for; a switching regulator draws less.",
        "Modules with no sourced supply current are not in the total; the module library says why under their data gaps.",
        ("The controller board's regulator is switching (" + stage["note"] + ").") if stage and stage["kind"] == "switching"
        else ("The controller board's regulator is linear (" + stage["note"] + ").") if stage
        else "The controller board's regulator is not stated by its sources, so its losses are not modelled.",
    ]
    status = ADVISORY
    if needs and needs["value"] * 1000 > budget:
        status = EXCEEDS
        summary = f"The controller needs a supply that can deliver {needs['value']:g} A and a standard port is assumed to give {budget} mA. " + summary
    return _check("supply_current", "USB supply current", status, summary, quantities, inputs, limits)


# --- thermal ----------------------------------------------------------------------------------------------------------

def _thermal(plan: dict[str, Any], library: dict[str, Any]) -> list[dict[str, Any]]:
    outer = plan["case"]["outer_mm"]
    x, y, z = outer["x"], outer["y"], outer["z"]
    # Five faces: the bottom rests on a surface and is not counted. top (x*z) + four sides (2*(x*y) + 2*(z*y)).
    area_m2 = (x * z + 2 * x * y + 2 * z * y) / 1e6
    h_low, h_high = ASSUMED["convection_w_per_m2k"][0]
    r_best, r_worst = 1 / (h_high * area_m2), 1 / (h_low * area_m2)
    vin = ASSUMED["usb_input_v"][0]
    load = _loads(plan, library)
    missing, load_facts = load["missing"], load["facts"]
    stage, mcu_entry = _power_stage(plan, library)
    io_v = mcu_entry["electrical"]["io_v"]
    limits_c, limit_facts, unknown_limit = [], [], []
    for module, entry in _entries(plan, library):
        row = entry.get("engineering", {}).get("operating_temp_c")
        if row:
            limits_c.append((module["id"], row["max"], row["kind"]))
            limit_facts.append(_fact(entry, "operating_temp_max", row["max"], "C", row["locator"], row["source"]))
        else:
            unknown_limit.append(module["id"])
    if not load_facts or not limits_c:
        return [_check("enclosure_temperature", "Sealed-case temperature", NOT_ASSESSED,
                       "Needs a sourced supply current and a sourced operating temperature for at least one module; the library has " + ("no current" if not load_facts else "no temperature limit") + " for this plan.",
                       {"modules_without_a_sourced_current": missing, "modules_without_a_sourced_limit": unknown_limit}, [])]
    # A floor: each current at the rail it was measured on. A known linear regulator adds its own drop; a switching or unstated one adds a loss that is not modelled.
    linear_extra = {name: ((vin - io_v) * ma / 1000 if stage and stage["kind"] == "linear" else 0.0)
                    for name, ma in (("sustained_load", load["sustained_ma"]), ("peak_load", load["peak_ma"]))}
    watts = {"sustained_load": _r(load["sustained_w"] + linear_extra["sustained_load"], 3),
             "peak_load": _r(load["peak_w"] + linear_extra["peak_load"], 3)}
    rises = {name: {"best_k": _r(w * r_best, 1), "worst_k": _r(w * r_worst, 1)} for name, w in watts.items()}
    lowest = min(limit for _, limit, _ in limits_c)
    hot = ASSUMED["ambient_c"][0][1]
    worst_floor = hot + rises["peak_load"]["worst_k"]
    quantities = {
        "case_surface_area_m2": _r(area_m2, 4),
        "case_to_ambient_k_per_w": {"best": _r(r_best, 1), "worst": _r(r_worst, 1)},
        "load_ma": {"sustained": _r(load["sustained_ma"], 3), "peak": _r(load["peak_ma"], 3)},
        "heat_floor_w": watts, "case_surface_rise_k": rises,
        "lowest_sourced_operating_limit_c": lowest,
        "limits_by_module": [{"module": ref, "max_c": limit, "kind": kind} for ref, limit, kind in limits_c],
        "modules_without_a_sourced_limit": unknown_limit, "modules_without_a_sourced_current": missing,
        "worst_case_surface_floor_c": _r(worst_floor, 1),
    }
    status = EXCEEDS if worst_floor >= lowest else ADVISORY
    text = (
        f"If every watt the sourced loads consume, at the rail each was measured on, ends up inside this sealed case, its surface runs {rises['sustained_load']['best_k']:g} to "
        f"{rises['sustained_load']['worst_k']:g} K above the room at the sourced sustained load and {rises['peak_load']['best_k']:g} to "
        f"{rises['peak_load']['worst_k']:g} K at the sourced peak. At {hot:g} C ambient that is a surface of at least "
        f"{worst_floor:.0f} C against the lowest sourced limit of {lowest} C."
    )
    limits = ["This is the outside surface only. The air and the parts inside are hotter by an internal resistance this does not estimate, so a surface under the limit does not show the parts are.",
              "Input power is taken as heat in the case; a little leaves as radio, so this slightly overstates.",
              "The input current is taken to equal the load current, as for a linear regulator; a switching regulator would draw less.",
              ("Modules with no sourced current are not in the power figure: " + ", ".join(missing) + ".") if missing else "Every module has a sourced current.",
              ("Modules with no sourced temperature limit are not in the comparison: " + ", ".join(unknown_limit) + ".") if unknown_limit else "Every module has a sourced temperature limit."]
    checks = [_check("enclosure_temperature", "Sealed-case temperature", status, text, quantities,
                     [_asm("convection_w_per_m2k"), _asm("ambient_c"), _asm("usb_input_v"), *load_facts, *limit_facts], limits)]
    mcu = next(m for m in plan["modules"] if m["kind"] == "mcu_board")
    for module, entry in _entries(plan, library):
        sensing = entry.get("engineering", {}).get("temperature_sensing")
        if not sensing or module is mcu:
            continue
        box, other = module["box"], mcu["box"]
        gap_x = max(other["x0"] - box["x1"], box["x0"] - other["x1"], 0)
        gap_z = max(other["z0"] - box["z1"], box["z0"] - other["z1"], 0)
        gap = (gap_x ** 2 + gap_z ** 2) ** 0.5
        checks.append(_check(
            f"temperature_bias_{module['id']}", f"Temperature reading of {module['id']}", ADVISORY,
            f"This sensor sits {gap:.1f} mm from the controller board inside a closed case, so its temperature reading will be above the room's; "
            "its datasheet says as much for any mounting. Separate it, vent the case, or correct the reading against a reference.",
            {"gap_to_controller_board_mm": _r(gap, 1)},
            [_fact(entry, "temperature_sensing", sensing["quote"], "", sensing["locator"], sensing["source"])],
            ["No numeric offset is given: it depends on the load, the airflow and the layout."]))
    return checks


# --- radio, mechanics and printing ------------------------------------------------------------------------------------

def _antenna(plan: dict[str, Any], library: dict[str, Any]) -> dict[str, Any]:
    found = [(m, e, e["engineering"]["antenna"]) for m, e in _entries(plan, library) if e.get("engineering", {}).get("antenna")]
    if not found:
        return _check("antenna_clearance", "Antenna clearance", NOT_ASSESSED, "No module in this plan lists an antenna clearance.", {}, [])
    module, entry, antenna = found[0]
    inner_x = plan["case"]["inner_mm"]["x"]
    wall_gap = inner_x / 2 - _far_x(module, antenna["end"])
    need = antenna["clearance_mm"]
    others = [m for m in plan["modules"] if m is not module]
    nearest = min((_far_x(module, antenna["end"]) - _far_x(m, antenna["end"]) for m in others), default=None)
    quantities = {"gap_to_case_wall_mm": _r(wall_gap, 2), "recommended_clearance_mm": need,
                  "extra_case_length_needed_mm": _r(max(0.0, need - wall_gap), 2),
                  "antenna_end_to_nearest_other_module_mm": None if nearest is None else _r(nearest, 2)}
    status = EXCEEDS if wall_gap + 0.01 < need else WITHIN
    text = (f"The antenna end of {module['id']} is {wall_gap:g} mm from the inside of the case wall; its source recommends at least {need:g} mm in all directions. "
            + (f"Lengthening the case by about {need - wall_gap:g} mm at that end would meet it." if wall_gap + 0.01 < need else "")).strip()
    return _check("antenna_clearance", "Antenna clearance inside the case", status, text, quantities,
                  [_fact(entry, "antenna_clearance", antenna["clearance_mm"], "mm", f"\"{antenna['quote']}\" ({antenna['locator']})", antenna["source"])],
                  ["It is a recommendation, not a pass/fail rule, and it does not say how a plastic wall detunes the antenna. The guidelines advise testing range on the finished product.",
                   "Clearance to the other modules is reported, not judged: the guidelines give no distance for them.",
                   "The plan lays the board lengthwise with the antenna end at +x; this measures along that axis only."])


def _fit(plan: dict[str, Any], library: dict[str, Any]) -> list[dict[str, Any]]:
    case = plan["case"]
    hx, hz = case["inner_mm"]["x"] / 2, case["inner_mm"]["z"] / 2
    tol = ASSUMED["print_tolerance_mm"][0]
    gaps = []
    for m in plan["modules"]:
        b = m["box"]
        for side, value in (("-x", b["x0"] + hx), ("+x", hx - _far_x(m)), ("-z", b["z0"] + hz), ("+z", hz - b["z1"])):
            gaps.append({"module": m["id"], "side": side, "gap_mm": _r(value, 2)})
    tight = [g for g in gaps if g["gap_mm"] <= tol]
    smallest = min(gaps, key=lambda g: g["gap_mm"])
    checks = [_check(
        "module_to_wall_gaps", "Gaps between modules and the case walls", EXCEEDS if smallest["gap_mm"] < 0 else (ADVISORY if tight else WITHIN),
        f"The smallest gap from a module to an inside wall is {smallest['gap_mm']:g} mm ({smallest['module']}, {smallest['side']} wall), against a printer tolerance of "
        f"about {tol:g} mm each way." + (" Gaps at or below that tolerance may not assemble." if tight else ""),
        {"smallest": smallest, "at_or_below_print_tolerance": tight, "all": gaps}, [_asm("print_tolerance_mm")],
        ["The gaps use the plan's module outlines, which are typical dimensions the plan tells you to measure."])]
    mcu = next(m for m in plan["modules"] if m["kind"] == "mcu_board")
    usb = case.get("usb_cutout")
    if usb:
        toward_cable = mcu["box"]["x0"] + hx  # gap on the USB side
        has_antenna = mcu.get("overhang_mm", {}).get("antenna_end", 0.0) > 0
        end = "antenna end" if has_antenna else "far end"
        stops = case.get("board_stops")
        if stops:
            gap = stops["gap_mm"]
            checks.append(_check(
                "usb_insertion_support", "What holds the board when a cable is plugged in", WITHIN,
                f"Stop blocks sit {gap:g} mm beyond the last header pin of each row, so a plug pushed in moves the board at most {gap:g} mm before its pins meet them. "
                f"The push no longer goes through the {end}.",
                {"board_travel_mm": gap, "stop_count": len(stops["boxes"]), "gap_on_cable_side_mm": _r(toward_cable, 2)}, [],
                ["Insertion force is not estimated (no connector force figure was sourced) and the stops' strength is not assessed: they are small printed blocks.",
                 "Pulling the plug out drags the board toward the USB wall, which stops it; the board is otherwise held only by resting on its pins."]))
        else:
            travel = hx - _far_x(mcu)        # distance the board can be pushed away from the cable
            checks.append(_check(
                "usb_insertion_support", "What holds the board when a cable is plugged in", ADVISORY,
                f"This case has no board stops. Pushing the plug in moves the board toward the far wall: it can travel {travel:.1f} mm before its {end} meets the wall, "
                f"and that wall would then take the push through the {end}.",
                {"board_travel_mm": _r(travel, 2), "gap_on_cable_side_mm": _r(toward_cable, 2)}, [],
                ["Insertion force is not estimated: no connector force figure was sourced. Add stops or standoffs and retest."]))
    return checks


def _printing(plan: dict[str, Any], library: dict[str, Any]) -> list[dict[str, Any]]:
    case = plan["case"]
    wall, usb, window = case["wall_mm"], case.get("usb_cutout"), case.get("window")
    nozzle = ASSUMED["nozzle_mm"][0]
    checks = [_check("wall_thickness", "Wall thickness for the nozzle", WITHIN if wall >= 4 * nozzle else ADVISORY,
                     f"A {wall:g} mm wall is {wall / nozzle:.1f} extrusion widths of a {nozzle:g} mm nozzle.",
                     {"wall_mm": wall, "extrusion_widths": _r(wall / nozzle, 1)}, [_asm("nozzle_mm")],
                     ["The lid's lip is 1.0 mm thick, about 2.5 widths: slicers may print it as two thin lines."])]
    if usb:
        span = usb["width_mm"]
        limit = ASSUMED["bridge_limit_mm"][0]
        checks.append(_check("usb_opening_bridge", "Bridge over the USB opening", WITHIN if span <= limit else ADVISORY,
                             f"With the base standing on its floor, the top of the {span:g} mm USB opening is printed as a bridge over air.",
                             {"span_mm": span, "limit_mm": limit}, [_asm("bridge_limit_mm")], ["Print a test first; cooling and filament change what bridges."]))
    if window:
        checks.append(_check("lid_orientation", "Lid orientation and the display window", WITHIN,
                             "The lid is exported plate-down, so the window is a vertical hole with no bridge, and the lip points up.", {}, []))
    return checks


# --- assembly ---------------------------------------------------------------------------------------------------------

def _not_assessed() -> list[dict[str, str]]:
    return [
        {"domain": "EMC and radio regulation", "why": "The module is certified; the finished product still needs its own assessment. Nothing here estimates emissions."},
        {"domain": "ESD and surge", "why": "No protection circuit is described for the USB connector or the exposed headers."},
        {"domain": "Vibration, shock and drop", "why": "No loads or mounting stiffness are defined, and no material properties were sourced."},
        {"domain": "Ingress protection and condensation", "why": "The case is not sealed; its openings are not rated."},
        {"domain": "Mechanical strength", "why": "No stress analysis: wall and lip strength depend on the filament, the print and the infill."},
        {"domain": "Long-term reliability", "why": "No lifetime, cycling or creep data was sourced."},
        {"domain": "Display and sensor current, and the internal temperature of the parts", "why": "No sourced figure in the module library; see the supply and thermal checks."},
    ]


def _coverage(plan: dict[str, Any], library: dict[str, Any]) -> list[dict[str, Any]]:
    """For each placed module, which of the figures the review reads are in the library and which are missing, with the reason."""

    rows = []
    for module, entry in _entries(plan, library):
        eng = entry.get("engineering", {})
        have = [name for name, present in (
            ("operating_temp_c", "operating_temp_c" in eng), ("supply_current", bool(eng.get("loads"))),
            ("i2c_pullups", bool(entry.get("i2c", {}).get("pullups"))), ("antenna_clearance", "antenna" in eng),
            ("temperature_sensing_note", "temperature_sensing" in eng)) if present]
        rows.append({"module": module["id"], "library_id": entry["id"], "sourced": have, "gaps": eng.get("gaps", [])})
    return rows


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode()


def build_engineering_review(spec: Any) -> dict[str, Any]:
    """Recompute the plan from the spec and review it; a caller's own plan or findings are never used."""

    plan = build_device_plan(spec)
    if plan["counts"]["errors"]:
        raise DevicePlanError("Resolve the plan's errors before an engineering review.")
    library = {m["id"]: m for m in module_library()["modules"]}
    domains = [
        {"id": "electrical", "title": "Electrical", "checks": [_i2c_bus(plan, library)]},
        {"id": "power", "title": "Power", "checks": [_supply(plan, library)]},
        {"id": "thermal", "title": "Thermal", "checks": _thermal(plan, library)},
        {"id": "rf", "title": "Radio", "checks": [_antenna(plan, library)]},
        {"id": "mechanical", "title": "Mechanical fit", "checks": _fit(plan, library)},
        {"id": "printing", "title": "Printing", "checks": _printing(plan, library)},
    ]
    checks = [c for d in domains for c in d["checks"]]
    counts = {status: sum(1 for c in checks if c["status"] == status) for status in (EXCEEDS, ADVISORY, WITHIN, NOT_ASSESSED)}
    used = {i["name"]: i for c in checks for i in c["inputs"]}
    return {
        "schema_version": SCHEMA, "authority": AUTHORITY,
        "physical_correctness": "UNPROVEN", "firmware_authorized": False, "power_on_authorized": False,
        "plan_sha256": hashlib.sha256(_json(plan)).hexdigest(),
        "domains": domains, "counts": counts,
        "sourced_inputs": sorted((i for i in used.values() if i["basis"] == "sourced"), key=lambda i: i["name"]),
        "assumptions": sorted((i for i in used.values() if i["basis"] == "assumed"), key=lambda i: i["name"]),
        "coverage": _coverage(plan, library),
        "not_assessed": _not_assessed(),
    }
