"""Recompute the 2026-11-13 drone-PR audit corrections from committed repo files.

The audit (an independent review of PRs #230, #231, #276 and #291) found that
the arithmetic in those PRs was right but several inputs were the wrong thing:
a spare rotor bell priced as a motor, a canopy priced as a camera, an O4/3-in-1
board priced as the analog 5-in-1, and a 27 mm battery length for a 67.3 mm
pack. This module re-derives each corrected number from the files those PRs
committed, so the correction is reproducible rather than copied.

The source files are left unchanged: their committed STL/SCAD hashes and the
#291 evidence snapshot are records of what was done on those dates.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

# Title rules that separate whole parts from accessories in the #291 Ruten snapshot.
LINE_RULES: dict[str, dict[str, str]] = {
    "motors": {"exclude": r"配件|外轉子帶磁鐵"},             # spare bell "配件 一體化外轉子帶磁鐵"
    "fc_esc": {"require": r"五合一", "exclude": r"O4|三合"},   # analog build needs the 5-in-1 with VTX
    "camera": {"exclude": r"頂蓋"},                           # canopies for C02/C03 quads
}

# Facts the audit sourced outside the repo (BETAFPV pages via search extract; vsergeev README at 13cf8c29).
EXTERNAL = {
    "betafpv_bt20_300mah_pack_mm": [67.3, 11.8, 6.1],
    "betafpv_bt20_300mah_pack_g": 8.28,
    "vsergeev_65mm_build_without_battery_g": 24.4,
    "vsergeev_65mm_frame_asa_g": 4.8,
    "betafpv_air65_pp_frame_g": 2.67,
    "matrix1s_v1_esc_cont_a": 5.0,
    "matrix1s_ii_esc_cont_a": 12.0,
    "vsergeev_prop_cage_d_for_31mm_mm": 33.0,
    "pybullet_cf2x_mass_g": 27.0,
}
EXTERNAL_SOURCES = {
    "betafpv_bt20_300mah_pack_mm": "BETAFPV BT2.0 300 mAh 1S product page via search extract, matching GetFPV and fpv24 (audit 276-13)",
    "vsergeev_65mm_build_without_battery_g": "https://github.com/vsergeev/3d-parametric-whoop README at commit 13cf8c29 (audit 276-2, 276-30)",
    "betafpv_air65_pp_frame_g": "BETAFPV Air65 frame product page: 2.67 g, PP (audit 276-29)",
    "matrix1s_ii_esc_cont_a": "BETAFPV Matrix 1S 5IN1 II page via search extract (audit 276-6, 291-16)",
    "vsergeev_prop_cage_d_for_31mm_mm": "vsergeev whoop.scad: 33 mm cage for 31 mm props (audit 276-17)",
    "pybullet_cf2x_mass_g": "gym-pybullet-drones CF2X model used by #276's flight_lab.py (audit 276-44)",
}


def _keep(title: str, rule: dict[str, str]) -> bool:
    if "require" in rule and not re.search(rule["require"], title):
        return False
    if "exclude" in rule and re.search(rule["exclude"], title):
        return False
    return True


def corrected_whoop_bom(evidence: dict[str, Any]) -> dict[str, Any]:
    lines = {l["id"]: l for l in evidence["lines"]}
    out_lines = []
    total_orig = 0
    total_corr = 0
    for lid, l in lines.items():
        if l.get("role") != "build" or lid in ("charger", "radio"):
            continue
        qty = l["qty"]
        if l.get("fixed_price_twd") is not None:
            orig = corr = l["fixed_price_twd"]
            orig_title = corr_title = l.get("fixed_price_basis", "")
        else:
            cheapest = l["cheapest"]
            orig = cheapest[0]["unit_price_twd"]
            orig_title = cheapest[0]["title"]
            rule = LINE_RULES.get(lid)
            pick = next(c for c in cheapest if _keep(c["title"], rule)) if rule else cheapest[0]
            corr, corr_title = pick["unit_price_twd"], pick["title"]
        total_orig += qty * orig
        total_corr += qty * corr
        out_lines.append({"id": lid, "qty": qty, "pr291_unit_twd": orig, "corrected_unit_twd": corr,
                          "changed": orig != corr, "pr291_title": orig_title, "corrected_title": corr_title})
    fc = next(x for x in out_lines if x["id"] == "fc_esc")
    alt_if_fc_is_5in1 = total_corr - fc["corrected_unit_twd"] + fc["pr291_unit_twd"]
    buy = {a["id"]: a["unit_price_twd"]["min"] for a in evidence["buy_alternatives"]}
    cheapest_bnf = min(buy.items(), key=lambda kv: kv[1])
    charger = next(l for l in evidence["lines"] if l["id"] == "charger")["unit_price_twd"]
    return {
        "lines": out_lines,
        "pr291_build_min_twd": int(total_orig),
        "pr291_committed_build_min_twd": evidence["comparison"]["build_min_twd"],
        "corrected_build_min_twd": int(total_corr),
        "corrected_if_1900_board_is_5in1_twd": int(alt_if_fc_is_5in1),
        "cheapest_bnf": {"id": cheapest_bnf[0], "min_twd": int(cheapest_bnf[1])},
        "build_over_cheapest_bnf_pct": round(100.0 * (total_corr / cheapest_bnf[1] - 1.0), 1),
        "charger_shared_figure_used_twd": evidence["comparison"]["shared_lines_excluded_from_both_sides"]["charger"],
        "charger_p25_twd": charger["p25"],
        "charger_median_twd": charger["median"],
    }


def whoop_geometry(request: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    d = request["dimensions"]
    frame = audit["STL"]["aerial_frame.stl"]
    cradle = audit["STL"]["battery_cradle.stl"]
    frame_g = frame["volume_cm3"] * request["print_density_g_cm3"]
    cradle_g = cradle["volume_cm3"] * request["print_density_g_cm3"]
    channel_l = max(16.0, d["battery_l_mm"] - 4.0)  # as in #276's cradle generator
    pack_l = EXTERNAL["betafpv_bt20_300mah_pack_mm"][0]
    c = d["wheelbase_mm"] / (2.0 * math.sqrt(2.0))
    duct_r_in = d["prop_diameter_mm"] / 2.0 + d["prop_radial_clearance_mm"]
    duct_r_out = duct_r_in + d["duct_wall_mm"]
    rib_end = duct_r_in + 0.75 * d["duct_wall_mm"] + d["strut_width_mm"] / 2.0
    dry = EXTERNAL["vsergeev_65mm_build_without_battery_g"] - EXTERNAL["vsergeev_65mm_frame_asa_g"] + frame_g + cradle_g
    auw = dry + EXTERNAL["betafpv_bt20_300mah_pack_g"]
    ref_auw = EXTERNAL["vsergeev_65mm_build_without_battery_g"] + EXTERNAL["betafpv_bt20_300mah_pack_g"]
    cage_radial = (EXTERNAL["vsergeev_prop_cage_d_for_31mm_mm"] - d["prop_diameter_mm"]) / 2.0
    esc_v1 = EXTERNAL["matrix1s_v1_esc_cont_a"]
    esc_ii = EXTERNAL["matrix1s_ii_esc_cont_a"]
    motor_a = request["motor"]["max_current_a"]
    return {
        "battery_l_used_mm": d["battery_l_mm"],
        "battery_l_real_mm": pack_l,
        "cradle_channel_l_mm": channel_l,
        "pack_overhang_mm": round(pack_l - channel_l, 1),
        "frame_g": round(frame_g, 3),
        "cradle_g": round(cradle_g, 3),
        "frame_vs_vsergeev_x": round(frame_g / EXTERNAL["vsergeev_65mm_frame_asa_g"], 2),
        "frame_vs_air65_x": round(frame_g / EXTERNAL["betafpv_air65_pp_frame_g"], 2),
        "dry_g": round(dry, 1),
        "auw_g": round(auw, 1),
        "reference_auw_g": round(ref_auw, 1),
        "auw_increase_pct": round(100.0 * (auw / ref_auw - 1.0), 1),
        "hover_thrust_per_motor_g": round(auw / 4.0, 2),
        "thrust_per_motor_for_2to1_g": round(auw / 2.0, 1),
        "motor_offset_mm": round(c, 3),
        "duct_outer_r_mm": round(duct_r_out, 3),
        "rib_end_r_mm": round(rib_end, 3),
        "rib_protrusion_mm": round(rib_end - duct_r_out, 3),
        "bbox_from_ribs_mm": round(2.0 * (c + rib_end), 3),
        "bbox_committed_mm": frame["bbox_mm"][0],
        "prop_clearance_used_mm": d["prop_radial_clearance_mm"],
        "prop_clearance_vsergeev_mm": cage_radial,
        "esc_headroom_v1_pct": round(100.0 * (1.0 - motor_a / esc_v1), 1),
        "esc_headroom_ii_pct": round(100.0 * (1.0 - motor_a / esc_ii), 1),
        "motor_max_a": motor_a,
        "gemfan_source_field": request["propeller"]["source"],
        "fc_pitch_mm": d["fc_mount_pitch_mm"],
        "motor_bolts": request["motor_mount"]["bolt_count"],
        "motor_bolt": request["motor_mount"]["bolt_size"],
        "motor_pcd_mm": request["motor_mount"]["bolt_pcd_mm"],
        "prop_d_mm": d["prop_diameter_mm"],
    }


def compute(repo: Path) -> dict[str, Any]:
    ev = json.loads((repo / "examples/arbitrage_lab/build_vs_buy/evidence/drone_whoop65_20261106.json").read_text())
    req = json.loads((repo / "examples/drone_lab/design_requests/hs_native_65mm.json").read_text())
    audit = json.loads((repo / "examples/drone_lab/fabrication/20261105/GEOMETRY_AUDIT.json").read_text())
    return {"bom": corrected_whoop_bom(ev), "geometry": whoop_geometry(req, audit),
            "external_inputs": EXTERNAL, "external_sources": EXTERNAL_SOURCES}
