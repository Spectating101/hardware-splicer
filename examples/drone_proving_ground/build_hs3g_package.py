#!/usr/bin/env python3
"""Regenerate the HS-3G drone proving-ground package.

    PYTHONPATH=src <python with cadquery> examples/drone_proving_ground/build_hs3g_package.py

Writes, under examples/drone_proving_ground/:

* generated/hs3g_{bottom,top}_plate.{step,stl,dxf}  - frame CAD (CadQuery)
* generated/results.json                           - every computed number
* README.md                                        - rendered from results.json

``--out DIR`` writes the CAD and results.json to DIR instead and leaves the
committed files alone; ``--check`` exits non-zero if the committed README or
results differ from a fresh regeneration.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import hs3g_audit as audit_corrections  # noqa: E402
import hs3g_design as design  # noqa: E402
import hs3g_frame as frame_mod  # noqa: E402
import hs3g_readme as render_readme  # noqa: E402


def _load(name: str) -> dict[str, Any]:
    return json.loads((HERE / "inputs" / name).read_text())


def _source_stl_info(path: Path) -> dict[str, Any] | None:
    """Cross-check with the repo's own STL reader (drone_product_delivery)."""
    try:
        from hardware_splicer.drone_product_delivery import source_binary_stl_info
    except Exception:  # pragma: no cover - src/ not on PYTHONPATH
        return None
    info = source_binary_stl_info(path)
    return {"triangles": info["triangles"], "dimensions_mm": info["dimensions_mm"]}


def compute(out_dir: Path) -> dict[str, Any]:
    inputs = _load("parts.json")
    table = _load("motor_f1404_3800kv_thrust.json")
    strategies = _load("strategies.json")
    parts = inputs["parts"]
    a = inputs["assumptions"]
    mats = inputs["materials"]
    F = frame_mod.FRAME

    # --- CAD -------------------------------------------------------------
    solids = frame_mod.build(F)
    measured = frame_mod.measure(solids, F)
    files = frame_mod.export(solids, out_dir)
    meshes = {}
    for name in ("bottom_plate", "top_plate"):
        stl = out_dir / files[f"{name}_stl"]
        rep = design.mesh_report(stl)
        cad_v = measured["bottom_volume_mm3" if name == "bottom_plate" else "top_volume_mm3"]
        rep["cad_volume_mm3"] = cad_v
        rep["volume_error_pct"] = round(100.0 * (rep["signed_volume_mm3"] / cad_v - 1.0), 3)
        rep["repo_reader"] = _source_stl_info(stl)
        meshes[name] = rep

    # --- mass ------------------------------------------------------------
    vols = {"bottom": measured["bottom_volume_mm3"], "top": measured["top_volume_mm3"]}
    so_mm3 = frame_mod.standoff_volume_mm3(F)
    mb = design.mass_budget(parts, vols, so_mm3, mats)
    lo, hi = mats["carbon_plate"]["density_range_g_cm3"]
    mb_lo = design.mass_budget(parts, vols, so_mm3, mats, density=lo)
    mb_hi = design.mass_budget(parts, vols, so_mm3, mats, density=hi)
    limit = a["mass_limit_g"]["value"]
    margin = a["mass_design_margin_g"]["value"]
    payload_allow = limit - margin - mb_hi["auw_g"]

    # --- layout, CG and clearances ---------------------------------------
    motors = [tuple(m) for m in measured["motor_centres_mm"]]
    items = design.layout(F, parts, motors)
    disc = design.prop_disc(F, parts)
    rho = mats["carbon_plate"]["density_g_cm3"]
    frame_g = {"bottom": vols["bottom"] * rho / 1000.0, "top": vols["top"] * rho / 1000.0}
    masses = {r["id"]: r["total_g"] for r in mb["rows"]}
    cg = design.centre_of_gravity(
        items, masses, {"bottom": measured["bottom_centroid_mm"][2], "top": measured["top_centroid_mm"][2]},
        frame_g, mb["standoff_each_g"], design.part(parts, "motor")["unit_mass_g"],
        design.part(parts, "prop")["unit_mass_g"] / 4.0, disc, masses["hardware"] + masses["wiring"])
    clear = design.prop_clearance(items, motors, disc, cg["battery_x_mm"])
    slot_x = F["strap_slot_x_mm"] - F["strap_slot_w_mm"] / 2.0
    bat_half = design.part(parts, "battery")["size_mm"][0] / 2.0
    battery_strap_ok = abs(cg["battery_x_mm"]) + slot_x <= bat_half

    # --- propulsion --------------------------------------------------------
    bat = design.part(parts, "battery")
    stack = design.part(parts, "stack")
    motor = design.part(parts, "motor")
    prop = design.part(parts, "prop")
    prop_main = design.propulsion(table, "HQ 3x3x3", mb["auw_g"], bat["cells"], a, bat, stack, motor, prop["diameter_mm"])
    prop_alt = design.propulsion(table, "GF3016", mb["auw_g"], bat["cells"], a, bat, stack, motor, prop["diameter_mm"])
    prop_heavy = design.propulsion(table, "HQ 3x3x3", limit - 1.0, bat["cells"], a, bat, stack, motor, prop["diameter_mm"])

    # --- arm ---------------------------------------------------------------
    tip_g = motor["unit_mass_g"] + prop["unit_mass_g"] / 4.0 + a["tip_mass_extra_g"]["value"]
    g = a["gravity_m_s2"]["value"]
    arm = design.arm_dynamics(F, mats["carbon_plate"]["flexural_modulus_gpa"], rho, tip_g,
                              prop_main["max_thrust_total_g"], prop_main["hover_rpm_est"], prop_main["max_rpm"], 3, g)
    arm_low = design.arm_dynamics(F, mats["carbon_plate"]["modulus_low_gpa"], rho, tip_g,
                                  prop_main["max_thrust_total_g"], prop_main["hover_rpm_est"], prop_main["max_rpm"], 3, g)

    # --- cost --------------------------------------------------------------
    bom = []
    for p in parts:
        bom.append({"id": p["id"], "identity": p["identity"], "qty": p["qty"], "unit_usd": p["unit_price_usd"],
                    "line_usd": round(p["qty"] * p["unit_price_usd"], 2),
                    "price_class": p.get("price_class", p["sources"][0]["class"] if p["sources"] else "assumption"),
                    "url": p["sources"][0]["url"] if p["sources"] else None})
    bom_total = round(sum(r["line_usd"] for r in bom), 2)
    assumed = round(sum(r["line_usd"] for r in bom if r["price_class"] in ("assumption", "lower_bound")), 2)

    # --- audit corrections and strategies ---------------------------------
    corr = audit_corrections.compute(REPO)
    bnf = next(s for s in strategies["strategies"] if s["id"] == "buy_bnf_3in_class_gps")

    checks = {
        "auw_under_limit_with_margin": mb_hi["auw_g"] <= limit - margin,
        "tw_ratio_limited_ge_min": prop_main["tw_ratio_limited"] >= a["min_tw_ratio"]["value"],
        "tw_ratio_at_250g_ge_min": prop_heavy["tw_ratio_limited"] >= a["min_tw_ratio"]["value"],
        "esc_continuous_covers_full_throttle": stack["esc_continuous_a"] >= prop_main["motor_peak_current_table_a"],
        "battery_continuous_covers_limited_throttle": prop_main["throttle_limit_current_a"] <= prop_main["battery_cont_a"],
        "battery_continuous_covers_full_throttle": prop_main["battery_cont_ok_at_full"],
        "battery_burst_covers_full_throttle": prop_main["battery_burst_ok_at_full"],
        "prop_radial_clearance_ok": clear["min_radial_mm"] >= a["min_prop_clearance_mm"]["value"],
        "prop_vertical_gap_ok": (clear["min_vertical_above_mm"] or 99) >= a["min_vertical_gap_mm"]["value"],
        "adjacent_tip_gap_ok": clear["adjacent_tip_gap_mm"] >= a["min_adjacent_tip_gap_mm"]["value"],
        "cg_within_limit": max(abs(cg["cg_mm"][0]), abs(cg["cg_mm"][1])) <= a["max_cg_offset_mm"]["value"],
        "battery_covers_strap_slots": battery_strap_ok,
        "frame_watertight": all(m["watertight"] for m in meshes.values()),
        "frame_single_valid_solids": measured["bottom_is_valid"] and measured["top_is_valid"]
                                     and measured["bottom_solids"] == 1 and measured["top_solids"] == 1,
        "motor_spacing_matches_wheelbase": all(abs(d - F["wheelbase_mm"]) < 0.01 for d in measured["diagonal_motor_spacing_mm"]),
        "both_motor_patterns_present": measured["motor_bolt_pcd_counts"] == {"12": 16, "9": 16},
    }
    return {
        "schema": "hs.drone_proving_ground.results.v1",
        "frame_parameters": F,
        "cad_files": files,
        "cad_measured": measured,
        "mesh": meshes,
        "mass": mb,
        "mass_density_low": {"density": lo, "auw_g": mb_lo["auw_g"], "frame_g": mb_lo["frame_g"]},
        "mass_density_high": {"density": hi, "auw_g": mb_hi["auw_g"], "frame_g": mb_hi["frame_g"]},
        "mass_limit_g": limit,
        "mass_design_margin_g": margin,
        "payload_allowance_g": round(payload_allow, 1),
        "standoff_volume_mm3": round(so_mm3, 2),
        "prop_disc": disc,
        "cg": cg,
        "battery_strap_ok": battery_strap_ok,
        "clearance": clear,
        "propulsion": prop_main,
        "propulsion_gf3016": prop_alt,
        "propulsion_at_249g": prop_heavy,
        "arm": arm,
        "arm_low_modulus": arm_low,
        "bom": bom,
        "bom_total_usd": bom_total,
        "bom_assumed_or_lower_bound_usd": assumed,
        "bnf_compare": {"price": bnf["price"], "price_alt": bnf["price_alt"],
                        "build_minus_bnf_usd": round(bom_total - bnf["price"], 2),
                        "build_minus_bnf_alt_usd": round(bom_total - bnf["price_alt"], 2)},
        "strategies": strategies["strategies"],
        "audit": corr,
        "checks": checks,
        "assumptions": a,
        "materials": mats,
        "parts": parts,
        "regulation_sources": inputs["regulation_sources"],
        "thrust_source": {"url": table["source"], "class": table["source_class"], "note": table["note"]},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=None, help="write CAD + results here instead of generated/")
    ap.add_argument("--check", action="store_true", help="fail if committed README/results differ from a fresh run")
    args = ap.parse_args(argv)
    out = args.out or (HERE / "generated")
    res = compute(out)
    text = json.dumps(res, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    readme = render_readme.render(res)
    (out / "results.json").write_text(text)
    if args.check:
        ok = True
        for path, new in ((HERE / "generated" / "results.json", text), (HERE / "README.md", readme)):
            if not path.exists() or path.read_text() != new:
                print(f"DRIFT: {path.relative_to(REPO)} differs from a fresh regeneration")
                ok = False
        return 0 if ok else 1
    if args.out is None:
        (HERE / "README.md").write_text(readme)
    failed = [k for k, v in res["checks"].items() if not v]
    print(f"AUW {res['mass']['auw_g']} g | T/W {res['propulsion']['tw_ratio_limited']} (limited) | "
          f"hover {res['propulsion']['hover_time_min']} min | BOM {res['bom_total_usd']} USD")
    print("checks failing (expected ones are explained in README):", failed or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
