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
WROOM = "ESP32-WROOM-32E datasheet v2.1"
WROOM_URL = "https://documentation.espressif.com/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf"
LAYOUT_URL = "https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32/pcb-layout-design.html"
BME280_URL = "https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf"

# Sourced figures, each with where it is.
SOURCED = {
    "i2c_tr_max_ns": (1000, "ns", f"{UM10204}, Table 10, Standard-mode tr maximum", UM10204_URL),
    "i2c_vol_max_v": (0.4, "V", f"{UM10204}, Table 10, VOL1 maximum at 3 mA sink", UM10204_URL),
    "i2c_iol_ma": (3.0, "mA", f"{UM10204}, Table 10, IOL minimum at VOL = 0.4 V", UM10204_URL),
    "i2c_cb_max_pf": (400, "pF", f"{UM10204}, Table 10, Cb maximum", UM10204_URL),
    "i2c_ci_max_pf": (10, "pF", f"{UM10204}, Table 10, Ci maximum per I/O pin", UM10204_URL),
    "i2c_rise_factor": (0.8473, "", f"{UM10204}, section 7.1, t2 - t1 = 0.8473 x RC", UM10204_URL),
    "esp32_supply_min_a": (0.5, "A", f"{WROOM}, Table 14, current delivered by the external supply, minimum", WROOM_URL),
    "esp32_wifi_tx_peak_ma": (379, "mA", f"{WROOM}, Table 16, 802.11b 20 MHz 1 Mbps at 19.5 dBm, peak, 3.3 V, 100 % duty", WROOM_URL),
    "esp32_wifi_tx_avg_ma": (239, "mA", f"{WROOM}, Table 16, same row, average", WROOM_URL),
    "esp32_wifi_rx_ma": (112, "mA", f"{WROOM}, Table 16, 802.11b/g/n 20 MHz receive", WROOM_URL),
    "esp32_max_ambient_c": (85, "C", f"{WROOM}, Table 14, operating ambient temperature, 85 C version", WROOM_URL),
    "bme280_max_ambient_c": (85, "C", "Bosch BME280 datasheet, operating range -40 to +85 C", BME280_URL),
    "antenna_housing_clearance_mm": (
        15, "mm", "Espressif ESP32 hardware design guidelines, PCB layout, module placement: "
        "\"A clearance of at least 15 mm is recommended in all directions\" for the antenna inside a housing", LAYOUT_URL),
}
BME280_NOTE = (
    "Bosch BME280 datasheet, note to the temperature figures: the value \"depends on the PCB temperature, sensor element "
    "self-heating and ambient temperature and is typically above ambient temperature\""
)
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
TEMPERATURE_SENSING = {"adafruit-bme280-stemma-qt": BME280_NOTE}
SOURCED_LIMIT_C = {"esp32-devkitc-v4": "esp32_max_ambient_c", "adafruit-bme280-stemma-qt": "bme280_max_ambient_c"}
PEAK_CURRENT_MA = {"esp32-devkitc-v4": "esp32_wifi_tx_peak_ma"}
KNOWN_PULLUP = re.compile(r"(\d+)\s*k(?:Ω|ohm|Ohm)", re.IGNORECASE)


def _src(key: str) -> dict[str, Any]:
    value, unit, basis, url = SOURCED[key]
    return {"name": key, "value": value, "unit": unit, "basis": "sourced", "source": basis, "url": url}


def _asm(key: str) -> dict[str, Any]:
    value, unit, basis = ASSUMED[key]
    return {"name": key, "value": list(value) if isinstance(value, tuple) else value, "unit": unit, "basis": "assumed", "source": basis}


def _check(check_id: str, title: str, status: str, summary: str, quantities: dict[str, Any], inputs: list[dict[str, Any]],
           limits: list[str] | None = None) -> dict[str, Any]:
    return {"id": check_id, "title": title, "status": status, "summary": summary, "quantities": quantities, "inputs": inputs,
            "limits": limits or []}


def _r(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def _far_x(module: dict[str, Any]) -> float:
    """The module's +x extent including an antenna that overhangs its board, as the plan's own antenna finding measures it."""

    return module["box"]["x1"] + module.get("overhang_mm", {}).get("antenna_end", 0.0)


def _roles(plan: dict[str, Any]) -> dict[tuple[str, str], list[str]]:
    return {(m["id"], p["id"]): p["roles"] for m in plan["modules"] for p in m["pins"]}


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
    i2c_modules = sorted({w[end]["module"] for line in lines.values() for w in line for end in ("from", "to")}
                         - {m["id"] for m in plan["modules"] if m["kind"] == "mcu_board"})
    by_id = {m["id"]: library[m["module"]] for m in plan["modules"]}
    known, unknown = [], []
    for ref in i2c_modules:
        electrical = by_id[ref].get("electrical", {})
        match = KNOWN_PULLUP.search(electrical.get("pullups_note", "")) if electrical.get("onboard_pullups") else None
        (known if match else unknown).append((ref, int(match.group(1)) * 1000 if match else None))
    wire_m = {line: sum(w["curve_mm"] for w in wires) / 1000 for line, wires in lines.items()}
    ci = SOURCED["i2c_ci_max_pf"][0]
    pins_on_line = len(i2c_modules) + 1  # each module plus the controller
    low, high = ASSUMED["wire_pf_per_m"][0]
    tr = SOURCED["i2c_tr_max_ns"][0] * 1e-9
    k = SOURCED["i2c_rise_factor"][0]
    vdd = next(m for m in plan["modules"] if m["kind"] == "mcu_board")
    vdd_v = library[vdd["module"]]["electrical"]["io_v"]
    rp_min = (vdd_v - SOURCED["i2c_vol_max_v"][0]) / (SOURCED["i2c_iol_ma"][0] / 1000)
    cb = {line: (_r(wire_m[line] * low + pins_on_line * ci, 1), _r(wire_m[line] * high + pins_on_line * ci, 1)) for line in lines}
    worst = max(cb[line][1] for line in lines)
    best = max(cb[line][0] for line in lines)
    inputs = [_src(key) for key in ("i2c_tr_max_ns", "i2c_vol_max_v", "i2c_iol_ma", "i2c_cb_max_pf", "i2c_ci_max_pf", "i2c_rise_factor")]
    inputs += [_asm("wire_pf_per_m"), {"name": "io_v", "value": vdd_v, "unit": "V", "basis": "sourced", "source": "module library, ESP32-DevKitC V4 electrical.io_v"}]
    quantities: dict[str, Any] = {
        "wire_length_m": {line: _r(wire_m[line], 3) for line in lines},
        "bus_capacitance_pf_estimate": {"low": _r(best, 1), "high": _r(worst, 1), "limit": SOURCED["i2c_cb_max_pf"][0]},
        "rp_min_ohm": _r(rp_min, 0),
        "pullups_known": [{"module": ref, "ohm": ohm} for ref, ohm in known],
        "pullups_unknown": [ref for ref, _ in unknown],
    }
    if not known:
        return _check("i2c_bus", "I2C bus loading", NOT_ASSESSED,
                      f"No module on this bus states its pull-up value, so the rise time cannot be checked. Estimated bus capacitance is {best:g} to {worst:g} pF "
                      f"against the {SOURCED['i2c_cb_max_pf'][0]} pF limit.", quantities, inputs,
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
        status, text = EXCEEDS, f"The stated pull-ups in parallel are {rp_eff:.0f} ohm, below the {rp_min:.0f} ohm a device can sink at {SOURCED['i2c_vol_max_v'][0]} V."
    elif tolerated < best:
        status, text = EXCEEDS, f"The bus can carry {tolerated:.0f} pF at {rp_eff:.0f} ohm, but even the low estimate is {best:g} pF."
    elif tolerated < worst:
        status, text = ADVISORY, f"The bus can carry {tolerated:.0f} pF at {rp_eff:.0f} ohm; the estimate runs {best:g} to {worst:g} pF, so wire capacitance decides."
    else:
        status, text = WITHIN, f"At {rp_eff:.0f} ohm the bus can carry {tolerated:.0f} pF; the estimate is {best:g} to {worst:g} pF."
    return _check("i2c_bus", "I2C bus loading", status, text + " At 100 kHz (the rise time limit of Standard-mode).", quantities, inputs, limits)


def _supply(plan: dict[str, Any], library: dict[str, Any]) -> dict[str, Any]:
    known, unknown = [], []
    for module in plan["modules"]:
        key = PEAK_CURRENT_MA.get(module["module"])
        (known if key else unknown).append((module["id"], key))
    peak = sum(SOURCED[key][0] for _, key in known if key)
    budget = ASSUMED["usb_port_budget_ma"][0]
    headroom = budget - peak
    vin = ASSUMED["usb_input_v"][0]
    quantities = {
        "sourced_peak_ma": peak,
        "usb_budget_ma": budget,
        "headroom_for_unsourced_loads_ma": headroom,
        "modules_without_a_sourced_current": [ref for ref, _ in unknown],
        "if_linear_regulator_dissipation_w": _r((vin - 3.3) * peak / 1000, 2),
    }
    summary = (
        f"The only sourced load is the ESP32 module's Wi-Fi transmit peak, {peak} mA. A {budget} mA port leaves {headroom} mA for everything "
        f"without a sourced current ({', '.join(ref for ref, _ in unknown) or 'none'}), the USB bridge and the regulator's own draw."
    )
    limits = [
        "The module library holds no supply current for the display or the sensors, so they are not in the total.",
        "The DevKitC user guide does not say whether its 3.3 V regulator is linear. If it is, it dissipates (5.0 - 3.3) V x the load current; the figure above is that case.",
    ]
    return _check("supply_current", "USB supply current", ADVISORY, summary, quantities,
                  [_src("esp32_supply_min_a"), _src("esp32_wifi_tx_peak_ma"), _asm("usb_port_budget_ma"), _asm("usb_input_v")], limits)


# --- thermal ----------------------------------------------------------------------------------------------------------

def _thermal(plan: dict[str, Any], library: dict[str, Any]) -> list[dict[str, Any]]:
    outer = plan["case"]["outer_mm"]
    x, y, z = outer["x"], outer["y"], outer["z"]
    # Five faces: the bottom rests on a surface and is not counted. top (x*z) + four sides (2*(x*y) + 2*(z*y)).
    area_m2 = (x * z + 2 * x * y + 2 * z * y) / 1e6
    h_low, h_high = ASSUMED["convection_w_per_m2k"][0]
    r_best, r_worst = 1 / (h_high * area_m2), 1 / (h_low * area_m2)
    vin = ASSUMED["usb_input_v"][0]
    scenarios = {
        "wifi_receive_continuous": SOURCED["esp32_wifi_rx_ma"][0],
        "wifi_transmit_continuous_peak": SOURCED["esp32_wifi_tx_peak_ma"][0],
    }
    watts = {name: _r(vin * ma / 1000, 2) for name, ma in scenarios.items()}
    rises = {name: {"best_k": _r(w * r_best, 1), "worst_k": _r(w * r_worst, 1)} for name, w in watts.items()}
    limits_c = []
    for module in plan["modules"]:
        key = SOURCED_LIMIT_C.get(module["module"])
        if key:
            limits_c.append((module["id"], SOURCED[key][0]))
    lowest = min(limit for _, limit in limits_c)
    hot = ASSUMED["ambient_c"][0][1]
    worst_floor = hot + rises["wifi_transmit_continuous_peak"]["worst_k"]
    quantities = {
        "case_surface_area_m2": _r(area_m2, 4),
        "case_to_ambient_k_per_w": {"best": _r(r_best, 1), "worst": _r(r_worst, 1)},
        "input_power_w": watts, "case_surface_rise_k": rises,
        "lowest_sourced_operating_limit_c": lowest,
        "limits_by_module": [{"module": ref, "max_c": limit} for ref, limit in limits_c],
        "worst_case_surface_floor_c": _r(worst_floor, 1),
    }
    status = EXCEEDS if worst_floor >= lowest else ADVISORY
    text = (
        f"If every watt the board draws ends up inside this sealed case, its surface runs {rises['wifi_receive_continuous']['best_k']:g} to "
        f"{rises['wifi_receive_continuous']['worst_k']:g} K above the room while receiving and {rises['wifi_transmit_continuous_peak']['best_k']:g} to "
        f"{rises['wifi_transmit_continuous_peak']['worst_k']:g} K at the transmit peak. At {hot:g} C ambient that is a surface of at least "
        f"{worst_floor:.0f} C against the lowest sourced limit of {lowest} C."
    )
    limits = ["This is the outside surface only. The air and the parts inside are hotter by an internal resistance this does not estimate, so a surface under the limit does not show the parts are.",
              "Input power is taken as heat in the case; a little leaves as radio, so this slightly overstates.",
              "The input current is taken to equal the 3.3 V load current, as for a linear regulator. The DevKitC user guide does not say what its regulator is; a switching one would draw less.",
              "The display and sensors are not in the power figure (no sourced current)."]
    checks = [_check("enclosure_temperature", "Sealed-case temperature", status, text, quantities,
                     [_asm("convection_w_per_m2k"), _asm("ambient_c"), _asm("usb_input_v"), _src("esp32_wifi_rx_ma"), _src("esp32_wifi_tx_peak_ma"),
                      _src("esp32_max_ambient_c")], limits)]
    mcu = next(m for m in plan["modules"] if m["kind"] == "mcu_board")
    for module in plan["modules"]:
        note = TEMPERATURE_SENSING.get(module["module"])
        if not note:
            continue
        box, other = module["box"], mcu["box"]
        gap_x = max(other["x0"] - box["x1"], box["x0"] - other["x1"], 0)
        gap_z = max(other["z0"] - box["z1"], box["z0"] - other["z1"], 0)
        gap = (gap_x ** 2 + gap_z ** 2) ** 0.5
        checks.append(_check(
            f"temperature_bias_{module['id']}", f"Temperature reading of {module['id']}", ADVISORY,
            f"This sensor sits {gap:.1f} mm from the controller board inside a closed case, so its temperature reading will be above the room's; "
            "the datasheet says as much for any mounting. Separate it, vent the case, or correct the reading against a reference.",
            {"gap_to_controller_board_mm": _r(gap, 1)}, [{"name": "bosch_note", "basis": "sourced", "source": note, "url": BME280_URL}],
            ["No numeric offset is given: it depends on the load, the airflow and the layout."]))
    return checks


# --- RF, mechanics and printing -----------------------------------------------------------------------------------------

def _antenna(plan: dict[str, Any], library: dict[str, Any]) -> dict[str, Any]:
    mcu = next(m for m in plan["modules"] if m["kind"] == "mcu_board")
    keep = [k for k in library[mcu["module"]].get("keep_clear", []) if k["id"] == "antenna"]
    if not keep:
        return _check("antenna_clearance", "Antenna clearance", NOT_ASSESSED, "This controller lists no antenna keepout.", {}, [])
    inner_x = plan["case"]["inner_mm"]["x"]
    wall_gap = inner_x / 2 - _far_x(mcu)
    need = SOURCED["antenna_housing_clearance_mm"][0]
    others = [m for m in plan["modules"] if m is not mcu]
    nearest = min((_far_x(mcu) - _far_x(m) for m in others), default=None)
    quantities = {"gap_to_case_wall_mm": _r(wall_gap, 2), "recommended_clearance_mm": need,
                  "extra_case_length_needed_mm": _r(max(0.0, need - wall_gap), 2),
                  "antenna_end_to_nearest_other_module_mm": None if nearest is None else _r(nearest, 2)}
    status = EXCEEDS if wall_gap < need else WITHIN
    text = (f"The antenna end of the board is {wall_gap:g} mm from the inside of the case wall; Espressif recommends at least {need} mm in all directions. "
            + (f"Lengthening the case by about {need - wall_gap:g} mm at that end would meet it." if wall_gap < need else "")).strip()
    return _check("antenna_clearance", "Antenna clearance inside the case", status, text, quantities, [_src("antenna_housing_clearance_mm")],
                  ["It is a recommendation, not a pass/fail rule, and it does not say how a plastic wall detunes the antenna. The guidelines advise testing range on the finished product.",
                   "Clearance to the other modules is reported, not judged: the guidelines give no distance for them."])


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
        travel = hx - _far_x(mcu)        # distance the board can be pushed away from the cable
        checks.append(_check(
            "usb_insertion_support", "What holds the board when a cable is plugged in", ADVISORY,
            f"The exported case has no board stops. Pushing the plug in moves the board toward the far wall: it can travel {travel:.1f} mm before the antenna end meets the wall, "
            "and that wall would then take the push through the antenna end.",
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
        "not_assessed": _not_assessed(),
    }
