#!/usr/bin/env python3
"""Regenerate the HS-3G drone proving-ground package.

    PYTHONPATH=src <python with cadquery> examples/drone_proving_ground/build_hs3g_package.py

Writes, under examples/drone_proving_ground/:

* generated/hs3g_{bottom,top}_plate.{step,stl,dxf}  - frame CAD (CadQuery)
* generated/results.json                           - every computed number
* README.md                                        - rendered from results.json

``--out DIR`` writes the CAD, results.json and README.md to DIR instead and
leaves the committed files alone. ``--check`` regenerates into a temporary
directory, never writes into the package, and exits 1 if the committed
README.md, generated/results.json or either STL differs from the fresh run
(STEP and DXF carry export timestamps, so they are regenerated but not
byte-compared).

Both modes need ``PYTHONPATH=src`` (the STLs are cross-checked with the repo's
own reader) and CadQuery; without either the script exits 2 with a message
saying which is missing, rather than reporting drift.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
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


class SetupError(RuntimeError):
    """The build cannot run in this environment (missing PYTHONPATH=src or CadQuery)."""


PYTHONPATH_MESSAGE = (
    "hardware_splicer is not importable, so the STL cross-check with the repo's own reader cannot run. "
    "Run from the repository root with PYTHONPATH=src, e.g.\n"
    "    PYTHONPATH=src python examples/drone_proving_ground/build_hs3g_package.py --check")
CADQUERY_MESSAGE = ("CadQuery is not importable; the frame CAD cannot be regenerated. "
                    "Use a Python environment with cadquery installed.")


def require_environment() -> None:
    """Fail with a clear message instead of producing results that would read as drift."""
    try:
        import hardware_splicer.drone_product_delivery  # noqa: F401
    except ModuleNotFoundError as exc:
        if (exc.name or "").split(".")[0] in {"hardware_splicer", "mecha_splicer"}:
            raise SetupError(PYTHONPATH_MESSAGE) from exc
        raise
    if frame_mod.cq is None:
        raise SetupError(CADQUERY_MESSAGE)


def _source_stl_info(path: Path) -> dict[str, Any]:
    """Cross-check with the repo's own STL reader (drone_product_delivery)."""
    from hardware_splicer.drone_product_delivery import source_binary_stl_info
    info = source_binary_stl_info(path)
    return {"triangles": info["triangles"], "dimensions_mm": info["dimensions_mm"]}


CAD_KEYS = ("frame_parameters", "cad_files", "cad_measured", "manufacturability", "mesh")


def cad_stage(out_dir: Path) -> dict[str, Any]:
    """Build, measure and export the frame; the only stage that needs CadQuery."""
    require_environment()
    inputs = _load("parts.json")
    F = frame_mod.FRAME
    solids = frame_mod.build(F)
    measured = frame_mod.measure(solids, F)
    dfm = frame_mod.manufacturability(solids, F, inputs["cutter_rules"])
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
    return {"frame_parameters": F, "cad_files": files, "cad_measured": measured,
            "manufacturability": dfm, "mesh": meshes}


def compute(out_dir: Path) -> dict[str, Any]:
    return derive(cad_stage(out_dir))


def derive(cad: dict[str, Any]) -> dict[str, Any]:
    """Every number that follows from the CAD measurements and the cited inputs.

    Pure Python: the tests rerun it on the committed CAD measurements without CadQuery.
    """
    inputs = _load("parts.json")
    table = _load("motor_f1404_3800kv_thrust.json")
    strategies = _load("strategies.json")
    review = _load("review_2026_11_14.json")
    parts = inputs["parts"]
    a = inputs["assumptions"]
    mats = inputs["materials"]
    cp = mats["carbon_plate"]
    # cutter's stated density, converted: 1 lb = 453.59237 g, 1 in^3 = 16.387064 cm^3
    rho = round(cp["density_lb_in3"] * 453.59237 / 16.387064, 4)
    mats = json.loads(json.dumps(mats))
    mats["carbon_plate"]["density_g_cm3"] = rho
    F = cad["frame_parameters"]
    measured, dfm, files, meshes = cad["cad_measured"], cad["manufacturability"], cad["cad_files"], cad["mesh"]
    hw = design.hardware(F, parts, inputs["hardware_spec"])

    # --- mass ------------------------------------------------------------
    vols = {"bottom": measured["bottom_volume_mm3"], "top": measured["top_volume_mm3"]}
    so_mm3 = frame_mod.standoff_volume_mm3(F)
    mb = design.mass_budget(parts, vols, so_mm3, mats, hardware_g=hw["total_g"])
    lo, hi = mats["carbon_plate"]["density_range_g_cm3"]
    mb_lo = design.mass_budget(parts, vols, so_mm3, mats, density=lo, hardware_g=hw["total_g"])
    mb_hi = design.mass_budget(parts, vols, so_mm3, mats, density=hi, hardware_g=hw["total_g"])
    heavy_auw = max(mb["auw_g"], mb_hi["auw_g"])
    limit = a["mass_limit_g"]["value"]
    margin = a["mass_design_margin_g"]["value"]
    payload_allow = limit - margin - heavy_auw

    # --- layout, CG and clearances ---------------------------------------
    motors = [tuple(m) for m in measured["motor_centres_mm"]]
    items = design.layout(F, parts, motors)
    disc = design.prop_disc(F, parts)
    frame_g = {"bottom": vols["bottom"] * rho / 1000.0, "top": vols["top"] * rho / 1000.0}
    masses = {r["id"]: r["total_g"] for r in mb["rows"]}
    cg = design.centre_of_gravity(
        items, masses, {"bottom": measured["bottom_centroid_mm"][2], "top": measured["top_centroid_mm"][2]},
        frame_g, mb["standoff_each_g"], design.part(parts, "motor")["unit_mass_g"],
        design.part(parts, "prop")["unit_mass_g"] / 4.0, disc, masses["hardware"] + masses["wiring"])
    clear = design.prop_clearance(items, motors, disc, cg["battery_x_mm"])
    strap = design.battery_strap(F, parts, cg["battery_x_mm"], frame_mod.strap_slot_l_mm(F))

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
    e_on = cp["flexural_modulus_gpa"]
    e_low = cp["modulus_low_gpa"]
    e_bias = round(design.bias_modulus_gpa(e_on, e_on, cp["shear_modulus_g12_gpa"], cp["poisson_nu12"], 45.0), 2)

    def _arm(e: float, clamp: str) -> dict[str, Any]:
        return design.arm_dynamics(F, e, rho, tip_g, prop_main["max_thrust_total_g"], prop_main["hover_rpm_est"],
                                   prop_main["max_rpm"], 3, g, clamp=clamp)

    arm = _arm(e_on, "axis")
    arm_low = _arm(e_low, "axis")
    arm_cases = {
        "on_axis_clamp_axis": arm,
        "on_axis_clamp_far_edge": _arm(e_on, "far_edge"),
        "low_e_clamp_far_edge": _arm(e_low, "far_edge"),
        "bias_clamp_axis": _arm(e_bias, "axis"),
        "bias_clamp_far_edge": _arm(e_bias, "far_edge"),
    }
    f1s = [c["f1_hz"] for c in arm_cases.values()]
    arm_range = {"f1_min_hz": min(f1s), "f1_max_hz": max(f1s), "e_bias_gpa": e_bias,
                 "all_inside_rotor_band": all(c["f1_inside_rotor_band"] for c in arm_cases.values())}

    # --- cost --------------------------------------------------------------
    bom = []
    for p in parts:
        bom.append({"id": p["id"], "identity": p["identity"], "qty": p["qty"], "unit_usd": p["unit_price_usd"],
                    "line_usd": round(p["qty"] * p["unit_price_usd"], 2),
                    "price_class": p.get("price_class", p["sources"][0]["class"] if p["sources"] else "assumption"),
                    "url": p["sources"][0]["url"] if p["sources"] else None,
                    "accessed": (p["sources"][0].get("accessed") or inputs["accessed"]) if p["sources"] else None})
    for r, p in zip(bom, parts):
        r["order_stage"] = p["order_stage"]
    bom_total = round(sum(r["line_usd"] for r in bom), 2)
    stage_usd = {str(k): round(sum(r["line_usd"] for r in bom if r["order_stage"] == k), 2) for k in (1, 2)}
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
        "battery_strap_wraps_pack": strap["slots_outside_pack"] and strap["pack_spans_strap"] and strap["slot_fits_strap"],
        "battery_strap_clears_stack": strap["strap_clears_stack_spacers"] and strap["strap_fits_under_esc"],
        "arm_root_and_pad_junctions_filleted": measured["bottom_sharp_concave_corners"] == 0,
        "cutter_rules_met_away_from_motor_pads": all(
            all(k.startswith("motor_") or "-motor_" in k for k in d["holes_below_rule"] + d["webs_below_rule"])
            for d in dfm.values()),
        "cutter_rules_met_everywhere": not any(d["holes_below_rule"] or d["webs_below_rule"] for d in dfm.values()),
        "frame_watertight": all(m["watertight"] for m in meshes.values()),
        "frame_single_valid_solids": measured["bottom_is_valid"] and measured["top_is_valid"]
                                     and measured["bottom_solids"] == 1 and measured["top_solids"] == 1,
        "motor_spacing_matches_wheelbase": all(abs(d - F["wheelbase_mm"]) < 0.01 for d in measured["diagonal_motor_spacing_mm"]),
        "single_motor_pattern_as_specified": measured["motor_bolt_pcd_counts"] == {f"{F['motor_pcd_mm']:g}": 16},
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
        "carbon_density_g_cm3": rho,
        "auw_heavy_case_g": heavy_auw,
        "hardware": hw,
        "manufacturability": dfm,
        "cutter_rules": inputs["cutter_rules"],
        "battery_strap": strap,
        "arm_cases": arm_cases,
        "arm_range": arm_range,
        "payload_allowance_g": round(payload_allow, 1),
        "standoff_volume_mm3": round(so_mm3, 2),
        "prop_disc": disc,
        "cg": cg,
        "clearance": clear,
        "propulsion": prop_main,
        "propulsion_gf3016": prop_alt,
        "propulsion_at_249g": prop_heavy,
        "arm": arm,
        "arm_low_modulus": arm_low,
        "bom": bom,
        "bom_total_usd": bom_total,
        "bom_stage_usd": stage_usd,
        "review": review,
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
        "hardware_spec": inputs["hardware_spec"],
        "thrust_source": {"url": table["source"], "class": table["source_class"], "note": table["note"]},
    }


COMPARED = ("results.json", "hs3g_bottom_plate.stl", "hs3g_top_plate.stl")


def write_package(out: Path) -> dict[str, Any]:
    """Regenerate CAD, results.json and README.md into ``out``."""
    out.mkdir(parents=True, exist_ok=True)
    res = compute(out)
    (out / "results.json").write_text(json.dumps(res, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    (out / "README.md").write_text(render_readme.render(res))
    return res


def check(pkg: Path = HERE) -> list[str]:
    """Regenerate into a temporary directory and list committed files that differ.

    Reads ``pkg/README.md`` and ``pkg/generated/*``; writes nothing under ``pkg``.
    """
    drift: list[str] = []
    with tempfile.TemporaryDirectory(prefix="hs3g_check_") as tmp:
        fresh = Path(tmp)
        write_package(fresh)
        pairs = [(pkg / "README.md", fresh / "README.md")]
        pairs += [(pkg / "generated" / n, fresh / n) for n in COMPARED]
        for committed, new in pairs:
            if not committed.exists() or committed.read_bytes() != new.read_bytes():
                drift.append(str(committed.relative_to(pkg)))
    return drift


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=None, help="write CAD, results and README here instead")
    ap.add_argument("--check", action="store_true",
                    help="regenerate into a temp dir; exit 1 if committed README/results/STL differ")
    ap.add_argument("--pkg", type=Path, default=HERE, help=argparse.SUPPRESS)  # used by the tests
    args = ap.parse_args(argv)
    try:
        require_environment()
    except SetupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.check:
        drift = check(args.pkg)
        for d in drift:
            print(f"DRIFT: {d} differs from a fresh regeneration")
        if not drift:
            print("OK: README.md, generated/results.json and STL files match a fresh regeneration")
        return 1 if drift else 0
    if args.out is not None:
        res = write_package(args.out)
    else:
        with tempfile.TemporaryDirectory(prefix="hs3g_build_") as tmp:
            res = write_package(Path(tmp))
            gen = HERE / "generated"
            gen.mkdir(exist_ok=True)
            for f in Path(tmp).iterdir():
                shutil.copyfile(f, HERE / "README.md" if f.name == "README.md" else gen / f.name)
    failed = [k for k, v in res["checks"].items() if not v]
    print(f"AUW {res['mass']['auw_g']} g | T/W {res['propulsion']['tw_ratio_limited']} (limited) | "
          f"hover {res['propulsion']['hover_time_min']} min | BOM {res['bom_total_usd']} USD")
    print("checks failing (expected ones are explained in README):", failed or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
