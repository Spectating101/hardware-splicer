"""Engineering checks for the HS-3G sub-250 g 3-inch quad.

Pure functions over the cited inputs in ``inputs/``. Nothing here reads the
network; every number traces back to ``inputs/*.json``, to the generated CAD
solid, or to a named assumption in ``inputs/parts.json``.
"""
from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Mass roll-up and layout
# ---------------------------------------------------------------------------


def part(parts: list[dict[str, Any]], pid: str) -> dict[str, Any]:
    for p in parts:
        if p["id"] == pid:
            return p
    raise KeyError(pid)


def layout(frame: dict[str, float], parts: list[dict[str, Any]], motors: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """Component placement (x forward, z up, bottom-plate underside at z=0).

    Footprints are plan rectangles (cx, cy, half_x, half_y) and z ranges, used
    for both the centre of gravity and the prop-clearance check.
    """
    t = frame["bottom_t_mm"]
    stack = part(parts, "stack")
    motor = part(parts, "motor")
    cam = part(parts, "camera")
    gps = part(parts, "gps")
    bat = part(parts, "battery")
    top_z = t + frame["standoff_len_mm"]
    stack_z0 = t + frame["stack_spacer_len_mm"]  # ESC sits on nylon spacers; the strap passes under it
    items: list[dict[str, Any]] = [
        {"id": "stack", "xy": (0.0, 0.0), "half": (stack["footprint_mm"][0] / 2, stack["footprint_mm"][1] / 2),
         "z": (stack_z0, stack_z0 + stack["height_mm"])},
        {"id": "vtx", "xy": (0.0, 0.0), "half": (10.0, 10.0),
         "z": (stack_z0 + stack["height_mm"], stack_z0 + stack["height_mm"] + 4.0)},
        {"id": "camera", "xy": (frame["standoff_x_mm"] + 6.0, 0.0), "half": (cam["size_mm"][0] / 2, cam["size_mm"][1] / 2),
         "z": (t + 2.0, t + 2.0 + cam["size_mm"][2])},
        {"id": "receiver", "xy": (-frame["standoff_x_mm"] + 6.0, 0.0), "half": (6.5, 5.5), "z": (t, t + 3.0)},
        {"id": "top_plate", "xy": (0.0, 0.0), "half": (frame["top_l_mm"] / 2, frame["top_w_mm"] / 2),
         "z": (top_z, top_z + frame["top_t_mm"])},
        {"id": "gps", "xy": (-14.0, 0.0), "half": (gps["size_mm"][0] / 2, gps["size_mm"][1] / 2),
         "z": (top_z + frame["top_t_mm"], top_z + frame["top_t_mm"] + gps["size_mm"][2])},
        # crosswise: the pack's long side runs along y, so the strap wraps its 30 mm width
        {"id": "battery", "xy": (0.0, 0.0), "half": (bat["size_mm"][1] / 2, bat["size_mm"][0] / 2),
         "z": (-bat["size_mm"][2], 0.0)},
    ]
    for sx in (-1, 1):
        for sy in (-1, 1):
            r = frame["standoff_af_mm"] / math.sqrt(3)  # hex circumradius
            items.append({"id": "standoff", "xy": (sx * frame["standoff_x_mm"], sy * frame["standoff_y_mm"]),
                          "half": (r, r), "round_r": r, "z": (t, top_z)})
    for (mx, my) in motors:
        items.append({"id": "motor", "xy": (mx, my), "half": (motor["body_diameter_mm"] / 2,) * 2,
                      "z": (t, t + motor["body_height_mm"])})
    return items


def battery_strap(frame: dict[str, float], parts: list[dict[str, Any]], battery_x: float,
                  slot_l_mm: float) -> dict[str, Any]:
    """Does the strap, as drawn, wrap the pack and clear the stack?

    The strap runs along x: up through one slot, over the plate top under the
    ESC, down through the other slot and round the underside of the pack. That
    works only if (1) both slots lie outside the pack's x extent, so the strap
    can pass down the pack's sides; (2) the strap's top run, |y| <= w/2, clears
    the stack's M3 spacers at y = +-pitch/2; (3) the spacer height leaves room
    for the strap under the ESC; (4) the slots are at least as long as the strap
    is wide.
    """
    bat = part(parts, "battery")
    half_x = bat["size_mm"][1] / 2.0  # crosswise
    slot_inner = frame["strap_slot_x_mm"] - frame["strap_slot_w_mm"] / 2.0
    pack_x = (battery_x - half_x, battery_x + half_x)
    spacer_r = frame["stack_spacer_af_mm"] / math.sqrt(3)  # hex circumradius
    side_gap = frame["stack_pitch_mm"] / 2.0 - spacer_r - frame["strap_w_mm"] / 2.0
    under_gap = frame["stack_spacer_len_mm"] - frame["strap_t_mm"]
    slot_y_end = slot_l_mm / 2.0
    return {
        "pack_orientation": "crosswise (58 mm side along y)",
        "pack_x_extent_mm": [round(v, 2) for v in pack_x],
        "slot_inner_edges_x_mm": [round(-slot_inner, 2), round(slot_inner, 2)],
        "pack_side_to_slot_mm": [round(pack_x[0] + slot_inner, 2), round(slot_inner - pack_x[1], 2)],
        "strap_w_mm": frame["strap_w_mm"],
        "slot_y_end_mm": round(slot_y_end, 2),
        "strap_side_gap_to_stack_spacer_mm": round(side_gap, 2),
        "strap_gap_under_esc_mm": round(under_gap, 2),
        "slots_outside_pack": -slot_inner <= pack_x[0] and pack_x[1] <= slot_inner,
        "strap_clears_stack_spacers": side_gap > 0,
        "strap_fits_under_esc": under_gap > 0,
        "slot_fits_strap": slot_l_mm >= frame["strap_w_mm"],
        "pack_spans_strap": bat["size_mm"][0] >= frame["strap_w_mm"],
    }


def screw_mass_g(d_mm: float, length_mm: float, head_d_mm: float, head_h_mm: float, rho: float) -> float:
    """Shank as a full-diameter cylinder plus the head as a cylinder: an upper bound."""
    v = math.pi / 4 * d_mm ** 2 * length_mm + math.pi / 4 * head_d_mm ** 2 * head_h_mm
    return v * rho / 1000.0


def hardware(frame: dict[str, float], parts: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    """Itemised fasteners with lengths chosen from the stack-up, and their mass."""
    stack = part(parts, "stack")
    rho = {k: v["density_g_cm3"] for k, v in spec["materials"].items()}
    t = frame["bottom_t_mm"]
    heads = spec["button_heads_iso7380"]
    std = spec["standard_lengths_mm"]
    # stack screw: from under the plate through plate, spacer, the stack, and a nylon lock nut
    need_stack = t + frame["stack_spacer_len_mm"] + stack["height_mm"] + spec["m3_nylon_locknut_h_mm"]
    stack_len = min(L for L in std["M3"] if L >= need_stack)
    motor_len = spec["motor_screw_len_mm"]
    engagement = motor_len - t
    items = [
        {"id": "motor_screw", "what": f"M2 x {motor_len:g} button head, steel", "qty": 16,
         "unit_g": screw_mass_g(2.0, motor_len, *heads["M2"], rho["steel"])},
        {"id": "stack_screw", "what": f"M3 x {stack_len:g} button head, titanium", "qty": 4,
         "unit_g": screw_mass_g(3.0, stack_len, *heads["M3"], rho["titanium"])},
        {"id": "standoff_screw", "what": "M3 x 6 button head, titanium", "qty": 8,
         "unit_g": screw_mass_g(3.0, 6.0, *heads["M3"], rho["titanium"])},
        {"id": "stack_spacer", "what": f"M3 x {frame['stack_spacer_len_mm']:g} nylon hex spacer, {frame['stack_spacer_af_mm']:g} mm AF",
         "qty": 4, "unit_g": (math.sqrt(3) / 2 * frame["stack_spacer_af_mm"] ** 2 - math.pi / 4 * 3.2 ** 2)
         * frame["stack_spacer_len_mm"] * rho["nylon"] / 1000.0},
        {"id": "stack_nut", "what": "M3 nylon lock nut", "qty": 4, "unit_g": spec["m3_nylon_locknut_g"]},
        {"id": "strap", "what": f"{frame['strap_w_mm']:g} mm battery strap", "qty": 1, "unit_g": spec["strap_g"]},
    ]
    for it in items:
        it["unit_g"] = round(it["unit_g"], 3)
        it["total_g"] = round(it["unit_g"] * it["qty"], 3)
    return {
        "items": items,
        "total_g": round(sum(it["total_g"] for it in items), 2),
        "stack_screw_needed_mm": round(need_stack, 2),
        "stack_screw_len_mm": stack_len,
        "motor_screw_len_mm": motor_len,
        "motor_thread_engagement_mm": round(engagement, 2),
        "motor_thread_engagement_x_d": round(engagement / 2.0, 2),
        "motor_thread_depth_verified": False,
    }


def prop_disc(frame: dict[str, float], parts: list[dict[str, Any]]) -> dict[str, float]:
    motor, prop = part(parts, "motor"), part(parts, "prop")
    z0 = frame["bottom_t_mm"] + motor["body_height_mm"]
    return {"r": prop["diameter_mm"] / 2.0, "z0": z0, "z1": z0 + prop["hub_height_mm"]}


def mass_budget(parts: list[dict[str, Any]], frame_volumes_mm3: dict[str, float], standoff_mm3: float,
                materials: dict[str, Any], density: float | None = None,
                hardware_g: float | None = None) -> dict[str, Any]:
    rho_cf = materials["carbon_plate"]["density_g_cm3"] if density is None else density
    rho_al = materials["aluminium_7075"]["density_g_cm3"]
    rows: list[dict[str, Any]] = []
    frame_g = (frame_volumes_mm3["bottom"] + frame_volumes_mm3["top"]) * rho_cf / 1000.0
    standoff_g = standoff_mm3 * rho_al / 1000.0
    for p in parts:
        if "component_masses_g" in p:
            m, n = sum(p["component_masses_g"].values()), p["qty"]
        elif p["id"] == "frame_cut":
            m, n = frame_g, 1
        elif p["id"] == "standoff":
            m, n = standoff_g, p["qty"]
        elif p["id"] == "hardware" and hardware_g is not None:
            m, n = hardware_g, 1
        elif p["id"] == "battery":
            m, n = p["unit_mass_g"], p["on_aircraft"]
        elif p["id"] == "prop":
            m, n = p["unit_mass_g"], p["on_aircraft_packs"]
        else:
            m, n = p["unit_mass_g"], p["qty"]
        rows.append({"id": p["id"], "unit_g": round(m, 3), "n": n, "total_g": round(m * n, 3)})
    total = sum(r["total_g"] for r in rows)
    bat = next(r for r in rows if r["id"] == "battery")["total_g"]
    return {"rows": rows, "auw_g": round(total, 2), "dry_g": round(total - bat, 2),
            "frame_g": round(frame_g, 3), "standoff_each_g": round(standoff_g, 3)}


def centre_of_gravity(items: list[dict[str, Any]], masses: dict[str, float], frame_centroid_z: dict[str, float],
                      frame_g: dict[str, float], standoff_each_g: float, motor_g: float, prop_g_each: float,
                      disc: dict[str, float], spread_g: float) -> dict[str, Any]:
    """CG with the battery placed to zero the x offset (within the strap slots)."""
    pts: list[tuple[float, float, float, float]] = []  # m, x, y, z
    for it in items:
        cx, cy = it["xy"]
        zc = (it["z"][0] + it["z"][1]) / 2.0
        if it["id"] == "standoff":
            pts.append((standoff_each_g, cx, cy, zc))
        elif it["id"] == "motor":
            pts.append((motor_g, cx, cy, zc))
            pts.append((prop_g_each, cx, cy, (disc["z0"] + disc["z1"]) / 2.0))
        elif it["id"] == "top_plate":
            pts.append((frame_g["top"], cx, cy, it["z"][0] + frame_centroid_z["top"]))
        elif it["id"] in masses and it["id"] != "battery":
            pts.append((masses[it["id"]], cx, cy, zc))
    pts.append((frame_g["bottom"], 0.0, 0.0, frame_centroid_z["bottom"]))
    pts.append((spread_g, 0.0, 0.0, 8.0))  # wiring + hardware spread over the body
    m_other = sum(p[0] for p in pts)
    mx_other = sum(p[0] * p[1] for p in pts)
    bat = next(it for it in items if it["id"] == "battery")
    m_b = masses["battery"]
    x_b = -mx_other / m_b
    total = m_other + m_b
    zb = (bat["z"][0] + bat["z"][1]) / 2.0
    cg = (
        (mx_other + m_b * x_b) / total,
        (sum(p[0] * p[2] for p in pts) + m_b * bat["xy"][1]) / total,
        (sum(p[0] * p[3] for p in pts) + m_b * zb) / total,
    )
    return {"battery_x_mm": round(x_b, 2), "cg_mm": [round(v, 2) for v in cg], "mass_g": round(total, 2),
            "cg_z_below_prop_plane_mm": round(disc["z0"] - cg[2], 2)}


def _rect_dist(px: float, py: float, it: dict[str, Any]) -> float:
    cx, cy = it["xy"]
    if "round_r" in it:
        return max(0.0, math.hypot(px - cx, py - cy) - it["round_r"])
    hx, hy = it["half"]
    dx = max(abs(px - cx) - hx, 0.0)
    dy = max(abs(py - cy) - hy, 0.0)
    return math.hypot(dx, dy)


def prop_clearance(items: list[dict[str, Any]], motors: list[tuple[float, float]], disc: dict[str, float],
                   battery_x: float) -> dict[str, Any]:
    """Radial clearance for parts that reach the prop plane; vertical gap for parts above it."""
    radial: list[dict[str, Any]] = []
    vertical: list[dict[str, Any]] = []
    for it in items:
        if it["id"] == "motor":
            continue
        it = dict(it)
        if it["id"] == "battery":
            it["xy"] = (battery_x, it["xy"][1])
        d = min(_rect_dist(mx, my, it) for mx, my in motors)
        overlaps_z = it["z"][1] > disc["z0"] and it["z"][0] < disc["z1"]
        if overlaps_z:
            radial.append({"id": it["id"], "clearance_mm": round(d - disc["r"], 2)})
        elif it["z"][0] >= disc["z1"] and d < disc["r"]:
            vertical.append({"id": it["id"], "gap_mm": round(it["z"][0] - disc["z1"], 2)})
        elif it["z"][1] <= disc["z0"] and d < disc["r"]:
            vertical.append({"id": it["id"], "gap_mm": round(disc["z0"] - it["z"][1], 2), "below": True})
    adj = min(math.hypot(motors[i][0] - motors[(i + 1) % 4][0], motors[i][1] - motors[(i + 1) % 4][1])
              for i in range(4))
    return {"radial": radial, "vertical": vertical, "adjacent_tip_gap_mm": round(adj - 2 * disc["r"], 2),
            "min_radial_mm": min(r["clearance_mm"] for r in radial) if radial else None,
            "min_vertical_above_mm": min((v["gap_mm"] for v in vertical if not v.get("below")), default=None)}


# ---------------------------------------------------------------------------
# Propulsion
# ---------------------------------------------------------------------------


def _fit_loglog(xs: list[float], ys: list[float]) -> tuple[float, float]:
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    n = len(xs)
    mx, my = sum(lx) / n, sum(ly) / n
    b = sum((a - mx) * (c - my) for a, c in zip(lx, ly)) / sum((a - mx) ** 2 for a in lx)
    return math.exp(my - b * mx), b


def propulsion(table: dict[str, Any], prop_name: str, auw_g: float, cells: int, a: dict[str, Any],
               battery: dict[str, Any], esc: dict[str, Any], motor: dict[str, Any], prop_d_mm: float) -> dict[str, Any]:
    cols = table["columns"]
    rows = [dict(zip(cols, r)) for r in table["props"][prop_name]]
    low = [r for r in rows if r["throttle_pct"] <= 70]
    k, n = _fit_loglog([r["thrust_g"] for r in low], [r["power_w"] for r in low])
    hover_g = auw_g / 4.0
    p_fit = k * hover_g ** n
    p_15 = rows[0]["power_w"] * (hover_g / rows[0]["thrust_g"]) ** 1.5
    p_motor = max(p_fit, p_15)  # use the more pessimistic extrapolation
    rpm_hover = rows[0]["rpm"] * math.sqrt(hover_g / rows[0]["thrust_g"])
    rho, g = a["air_density_kg_m3"]["value"], a["gravity_m_s2"]["value"]
    area = math.pi * (prop_d_mm / 2000.0) ** 2
    t_n = hover_g / 1000.0 * g
    p_ideal = t_n ** 1.5 / math.sqrt(2 * rho * area)
    v_nom = cells * a["nominal_cell_v"]["value"]
    p_total = 4 * p_motor + a["avionics_power_w"]["value"]
    i_hover = p_total / v_nom
    usable_ah = battery["capacity_mah"] / 1000.0 * a["usable_capacity_fraction"]["value"]
    t_hover_min = usable_ah / i_hover * 60.0
    # the optimistic branch, quoted only as an upper bound
    i_hover_fit = (4 * min(p_fit, p_15) + a["avionics_power_w"]["value"]) / v_nom
    t_hover_fit_min = usable_ah / i_hover_fit * 60.0

    full = rows[-1]
    max_thrust = 4 * full["thrust_g"]
    i_max = 4 * full["current_a"] + a["avionics_power_w"]["value"] / v_nom
    cap_ah = battery["capacity_mah"] / 1000.0
    i_cont = battery["c_continuous"] * cap_ah
    i_burst = battery["c_burst"] * cap_ah
    limit = max((r for r in rows if 4 * r["current_a"] + a["avionics_power_w"]["value"] / v_nom <= i_cont),
                key=lambda r: r["throttle_pct"])
    i_lim = 4 * limit["current_a"] + a["avionics_power_w"]["value"] / v_nom
    tip_speed = math.pi * prop_d_mm / 1000.0 * full["rpm"] / 60.0
    return {
        "prop": prop_name,
        "bench_voltage_v": round(sum(r["voltage_v"] for r in rows) / len(rows), 1),
        "hover_thrust_per_motor_g": round(hover_g, 2),
        "table_min_thrust_g": rows[0]["thrust_g"],
        "fit_rows_throttle_pct": [r["throttle_pct"] for r in low],
        "fit_exponent": round(n, 3),
        "hover_power_per_motor_fit_w": round(p_fit, 2),
        "hover_power_per_motor_n15_w": round(p_15, 2),
        "hover_power_per_motor_used_w": round(p_motor, 2),
        "hover_rpm_est": round(rpm_hover),
        "ideal_induced_power_per_motor_w": round(p_ideal, 3),
        "overall_efficiency_hover": round(p_ideal / p_motor, 3),
        "hover_current_a": round(i_hover, 2),
        "hover_time_min": round(t_hover_min, 1),
        "hover_time_upper_bound_min": round(t_hover_fit_min, 1),
        "hover_extrapolation_x": round(rows[0]["thrust_g"] / hover_g, 2),
        "max_thrust_total_g": round(max_thrust, 1),
        "tw_ratio_full": round(max_thrust / auw_g, 2),
        "max_current_a": round(i_max, 1),
        "battery_cont_a": round(i_cont, 1),
        "battery_burst_a": round(i_burst, 1),
        "battery_cont_ok_at_full": i_max <= i_cont,
        "battery_burst_ok_at_full": i_max <= i_burst,
        "throttle_limit_pct": limit["throttle_pct"],
        "throttle_limit_current_a": round(i_lim, 1),
        "throttle_limit_thrust_total_g": round(4 * limit["thrust_g"], 1),
        "tw_ratio_limited": round(4 * limit["thrust_g"] / auw_g, 2),
        "c_rate_hover": round(i_hover / cap_ah, 2),
        "esc_margin_full": round(esc["esc_continuous_a"] / full["current_a"], 2),
        "motor_peak_current_table_a": full["current_a"],
        "motor_peak_rating_a": motor["peak_current_60s_a"],
        "max_rpm": full["rpm"],
        "tip_speed_m_s": round(tip_speed, 1),
        "tip_mach": round(tip_speed / 343.0, 3),
    }


# ---------------------------------------------------------------------------
# Arm stiffness and first bending mode
# ---------------------------------------------------------------------------


def arm_root_radius(frame: dict[str, float], clamp: str = "axis") -> float:
    """Distance from the frame centre, along the 45-degree arm axis, of the clamp.

    ``axis``: where the arm's centre line leaves the body rectangle (stiffest
    reasonable clamp). ``far_edge``: where the arm's leading edge leaves the
    body, i.e. the whole arm width is free beyond this point (most flexible).
    """
    hx, hy = frame["body_l_mm"] / 2.0, frame["body_w_mm"] / 2.0
    c = math.sqrt(0.5)
    if clamp == "axis":
        return min(hx, hy) / c
    h = frame["arm_w_mm"] / 2.0
    # edge line: (c(s - h), c(s + h)); it leaves through y = hy or x = hx
    return min(hy / c - h, hx / c + h)


def bias_modulus_gpa(e1_gpa: float, e2_gpa: float, g12_gpa: float, nu12: float, theta_deg: float) -> float:
    """Off-axis Young's modulus of an orthotropic ply (classical lamination theory)."""
    c, s = math.cos(math.radians(theta_deg)), math.sin(math.radians(theta_deg))
    inv = c ** 4 / e1_gpa + s ** 4 / e2_gpa + (1.0 / g12_gpa - 2.0 * nu12 / e1_gpa) * s * s * c * c
    return 1.0 / inv


def arm_dynamics(frame: dict[str, float], e_gpa: float, rho_g_cm3: float, tip_g: float,
                 max_thrust_g: float, hover_rpm: float, max_rpm: float, blades: int, g: float,
                 clamp: str = "axis") -> dict[str, Any]:
    L = frame["wheelbase_mm"] / 2.0 - arm_root_radius(frame, clamp)  # mm
    b, h = frame["arm_w_mm"], frame["bottom_t_mm"]
    I = b * h ** 3 / 12.0  # mm^4, bending out of plane (thrust direction)
    E = e_gpa * 1000.0  # N/mm^2
    k = 3 * E * I / L ** 3  # N/mm
    arm_g = b * h * L * rho_g_cm3 / 1000.0
    m_eff = (tip_g + 0.2357 * arm_g) / 1000.0  # kg (Rayleigh tip-mass beam)
    f1 = math.sqrt(k * 1000.0 / m_eff) / (2 * math.pi)
    F = max_thrust_g / 4.0 / 1000.0 * g
    defl = F / k
    stress = F * L * (h / 2.0) / I
    f_rot_hover, f_rot_max = hover_rpm / 60.0, max_rpm / 60.0
    in_band = f_rot_hover <= f1 <= f_rot_max
    crossing_rpm = f1 * 60.0
    return {
        "clamp": clamp,
        "e_gpa": round(e_gpa, 2),
        "free_length_mm": round(L, 2),
        "section_mm": [b, h],
        "I_mm4": round(I, 2),
        "stiffness_n_per_mm": round(k, 2),
        "tip_mass_g": round(tip_g, 2),
        "arm_mass_g": round(arm_g, 3),
        "f1_hz": round(f1, 1),
        "rotor_freq_hover_hz": round(f_rot_hover, 1),
        "rotor_freq_max_hz": round(f_rot_max, 1),
        "blade_pass_hover_hz": round(blades * f_rot_hover, 1),
        "f1_inside_rotor_band": in_band,
        "f1_crossing_rpm": round(crossing_rpm),
        "tip_deflection_full_thrust_mm": round(defl, 4),
        "root_stress_full_thrust_mpa": round(stress, 2),
    }


# ---------------------------------------------------------------------------
# Mesh checks (pure Python, no mesh library)
# ---------------------------------------------------------------------------


def read_binary_stl(path: Path) -> list[tuple[tuple[float, float, float], ...]]:
    data = path.read_bytes()
    n = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + 50 * n:
        raise ValueError(f"not a binary STL: {path}")
    tris = []
    for i in range(n):
        off = 84 + 50 * i + 12
        v = struct.unpack_from("<9f", data, off)
        tris.append(((v[0], v[1], v[2]), (v[3], v[4], v[5]), (v[6], v[7], v[8])))
    return tris


def mesh_report(path: Path, q: float = 1e-4) -> dict[str, Any]:
    tris = read_binary_stl(path)
    key = lambda p: (round(p[0] / q), round(p[1] / q), round(p[2] / q))  # noqa: E731
    directed: dict[tuple, int] = {}
    vol = 0.0
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    degenerate = 0
    for a, b, c in tris:
        ka, kb, kc = key(a), key(b), key(c)
        if ka == kb or kb == kc or ka == kc:
            degenerate += 1
            continue
        for e in ((ka, kb), (kb, kc), (kc, ka)):
            directed[e] = directed.get(e, 0) + 1
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
        for p in (a, b, c):
            for i in range(3):
                lo[i] = min(lo[i], p[i])
                hi[i] = max(hi[i], p[i])
    undirected: dict[tuple, int] = {}
    for (u, v), cnt in directed.items():
        k = (u, v) if u < v else (v, u)
        undirected[k] = undirected.get(k, 0) + cnt
    non_manifold = sum(1 for c in undirected.values() if c != 2)
    misoriented = sum(1 for (u, v), c in directed.items() if c != 1 or directed.get((v, u), 0) != 1)
    return {
        "file": path.name,
        "triangles": len(tris),
        "degenerate_triangles": degenerate,
        "edges": len(undirected),
        "non_manifold_edges": non_manifold,
        "inconsistently_oriented_edges": misoriented,
        "watertight": non_manifold == 0 and misoriented == 0,
        "signed_volume_mm3": round(vol, 2),
        "bbox_mm": [round(hi[i] - lo[i], 3) for i in range(3)],
    }
