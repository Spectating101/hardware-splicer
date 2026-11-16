#!/usr/bin/env python3
"""Rebuild the HS-3G-B candidate with native CAD and pinned firmware evidence."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))
import hs3g_design as design
import hs3g_frame as frame


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs():
    base = json.loads((BASE / "inputs/parts.json").read_text())
    cfg = json.loads((HERE / "inputs/candidate.json").read_text())
    table = json.loads((HERE / "inputs/thrust_table.json").read_text())
    parts = copy.deepcopy(base["parts"])
    for p in parts:
        p.update(cfg["part_overrides"].get(p["id"], {}))
    hw = {**base["hardware_spec"], **cfg["hardware_overrides"]}
    return base, cfg, parts, hw, {**frame.FRAME, **cfg["frame_overrides"]}, table


def source_identity():
    paths = [BASE / "inputs/parts.json", BASE / "hs3g_frame.py", BASE / "hs3g_design.py",
             HERE / "build_package.py", HERE / "verify_package.py", *sorted((HERE / "inputs").glob("*.json"))]
    return {str(p.relative_to(BASE)): sha(p) for p in paths}


def analyze(measured, *, frame_parameters=None):
    base, cfg, parts, hw, f, table = inputs()
    if frame_parameters is not None:
        f = dict(frame_parameters)
    mats = copy.deepcopy(base["materials"])
    rho = mats["carbon_plate"]["density_lb_in3"] * 453.59237 / 16.387064
    mats["carbon_plate"]["density_g_cm3"] = rho
    hardware = design.hardware(f, parts, hw)
    mass = design.mass_budget(parts, {"bottom": measured["bottom_volume_mm3"], "top": measured["top_volume_mm3"]},
                              frame.standoff_volume_mm3(f), mats, hardware_g=hardware["total_g"])
    battery, motor, prop, stack = [design.part(parts, k) for k in ("battery", "motor", "prop", "stack")]
    propulsion = design.propulsion(table, "GF3028-3", mass["auw_g"], battery["cells"], base["assumptions"], battery, stack, motor, prop["diameter_mm"])
    full = dict(zip(table["columns"], table["props"]["GF3028-3"][-1]))
    path = cfg["power_path"]
    # Explicit sensitivity assumption, not a measured voltage/current law.
    voltage_factor = max(1.0, battery["cells"] * path["max_cell_charge_v"] / full["voltage_v"]) ** 2
    avionics_a = base["assumptions"]["avionics_power_w"]["value"] / (battery["cells"] * path["min_cell_operating_v"])
    current_bound = 4 * full["current_a"] * voltage_factor + avionics_a
    design_a = current_bound * path["design_current_factor"]
    power = {"bench_total_a": propulsion["max_current_a"], "full_pack_voltage_sensitivity_factor": round(voltage_factor, 5),
             "voltage_adjusted_total_a": round(current_bound, 3), "design_current_a": round(design_a, 3),
             "design_factor": path["design_current_factor"], "battery_continuous_a": propulsion["battery_cont_a"],
             "connector_rated_a": path["rated_current_a"], "esc_per_motor_a": stack["esc_continuous_a"],
             "connector_rating_conditions": path["rating_conditions"], "throttle_limit_relied_on": False}
    motors = [tuple(m) for m in measured["motor_centres_mm"]]
    items = design.layout(f, parts, motors)
    frame_g = {"bottom": measured["bottom_volume_mm3"] * rho / 1000, "top": measured["top_volume_mm3"] * rho / 1000}
    masses = {r["id"]: r["total_g"] for r in mass["rows"]}
    disc = design.prop_disc(f, parts)
    cg = design.centre_of_gravity(items, masses, {"bottom": measured["bottom_centroid_mm"][2], "top": measured["top_centroid_mm"][2]},
        frame_g, mass["standoff_each_g"], motor["unit_mass_g"], prop["unit_mass_g"] / 4, disc, masses["hardware"] + masses["wiring"])
    clearance = design.prop_clearance(items, motors, disc, cg["battery_x_mm"])
    strap = design.battery_strap(f, parts, cg["battery_x_mm"], frame.strap_slot_l_mm(f))
    strap["pack_orientation"] = f"crosswise ({battery['size_mm'][0]:g} mm side along y)"
    strap["specified_length_mm"] = 200
    strap["required_length_mm"] = round(2 * (battery["size_mm"][1] + battery["size_mm"][2] + f["bottom_t_mm"]) + 40, 2)
    arm = {clamp + "_" + str(e): design.arm_dynamics(f, e, rho, motor["unit_mass_g"] + prop["unit_mass_g"] / 4 + 0.8,
        propulsion["max_thrust_total_g"], propulsion["hover_rpm_est"], propulsion["max_rpm"], 3, 9.80665, clamp=clamp)
        for clamp in ["axis", "far_edge"] for e in [40.0, 55.2]}
    bom = [{"id": p["id"], "identity": p["identity"], "qty_to_buy": p["qty"], "unit_usd_snapshot": p["unit_price_usd"],
            "line_usd_snapshot": round(p["qty"] * p["unit_price_usd"], 2), "source": p["sources"][0]["url"] if p["sources"] else "assumption",
            "pricing_basis": "2026-11-16 snapshot" if p["id"] in cfg["part_overrides"] and p["sources"] else "retained baseline snapshot/assumption"} for p in parts]
    mp = cfg["mass_policy"]
    checks = {"nominal_mass_reserve": mass["auw_g"] <= 250 - mp["nominal_reserve_g"],
              "battery_uncertainty_reserve": mass["auw_g"] + mp["battery_uncertainty_g"] <= 250 - mp["reserve_after_battery_uncertainty_g"],
              "battery_continuous_at_design_current": design_a <= propulsion["battery_cont_a"],
              "connector_at_design_current": design_a <= path["rated_current_a"],
              "esc_at_design_current": design_a / 4 <= stack["esc_continuous_a"],
              "tw_at_249g": propulsion["max_thrust_total_g"] / 249 >= base["assumptions"]["min_tw_ratio"]["value"],
              "prop_radial_clearance": clearance["min_radial_mm"] >= base["assumptions"]["min_prop_clearance_mm"]["value"],
              "prop_adjacent_gap": clearance["adjacent_tip_gap_mm"] >= base["assumptions"]["min_adjacent_tip_gap_mm"]["value"],
              "prop_vertical_clearance": clearance["min_vertical_above_mm"] is None or clearance["min_vertical_above_mm"] >= base["assumptions"]["min_vertical_gap_mm"]["value"],
              "strap_wraps_pack": strap["slots_outside_pack"] and strap["pack_spans_strap"] and strap["slot_fits_strap"],
              "strap_clears_stack": strap["strap_clears_stack_spacers"] and strap["strap_fits_under_esc"],
              "strap_length": strap["required_length_mm"] <= strap["specified_length_mm"],
              "arm_roots_filleted": measured["bottom_sharp_concave_corners"] == 0,
              "motor_pattern": measured["motor_bolt_pcd_counts"] == {"9": 16}}
    return {"schema": "hardware_splicer.hs3g_revision_results.v1", "revision": cfg["revision"], "frame_parameters": f,
            "parts": parts, "mass": mass, "mass_policy": mp, "power": power, "propulsion": propulsion,
            "hardware": hardware, "cg": cg, "clearance": clearance, "strap": strap, "arm_sensitivity": arm,
            "bom": bom, "bom_total_usd_snapshot": round(sum(r["line_usd_snapshot"] for r in bom), 2),
            "measured": measured, "checks": checks, "procurement": cfg["procurement"],
            "physical_validation": False, "fabrication_authorized": False, "power_on_authorized": False, "flight_authorized": False}


def _evidence(out, cache):
    if cache is None and (HERE / "reference/firmware").is_dir():
        cache = HERE / "reference/firmware"
    lock = json.loads((HERE / "inputs/firmware-lock.json").read_text())
    records = []
    for item in [*lock["sources"], {**lock["binary"], "path": "inav_9.1.0_SPEEDYBEEF405MINI.hex"}]:
        rel = Path(item["path"])
        target = out / "firmware" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        cached = cache / rel if cache else None
        if cached and cached.is_file():
            body = cached.read_bytes()
        else:
            with urllib.request.urlopen(item["url"], timeout=30) as response:
                body = response.read(4 * 1024 * 1024 + 1)
        if len(body) > 4 * 1024 * 1024 or hashlib.sha256(body).hexdigest() != item["sha256"]:
            raise ValueError(f"Pinned firmware evidence failed identity check: {rel}")
        target.write_bytes(body)
        records.append({**item, "artifact": str(target.relative_to(out))})
    dump(out / "firmware/evidence.json", {**lock, "verified_files": records, "flashed": False,
        "binary_basis": "Official upstream release, hash-checked; HS did not compile or flash it."})


def _drill_sheet(out, parts, f):
    face = min(parts["bottom_plate"].val().Faces(), key=lambda x: x.Center().z)
    paths = []
    for wire in [face.outerWire(), *face.innerWires()]:
        for edge in wire.Edges():
            n = 2 if edge.geomType() == "LINE" else 32
            pts = [edge.positionAt(i / (n - 1)) for i in range(n)]
            paths.append('<path d="M ' + ' L '.join(f'{v.x:.4f} {-v.y:.4f}' for v in pts) + '"/>')
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="220mm" viewBox="0 0 210 220">',
           '<rect width="210" height="220" fill="white"/>',
           '<g font-family="sans-serif" font-size="4" fill="black">',
           '<text x="10" y="12">HS-3G-B post-drill sheet — 1:1 mm</text>',
           '<text x="10" y="19">Print 100%; verify scale. Shop review and motor measurement required.</text></g>',
           '<g transform="translate(105 96)" fill="none" stroke="black" stroke-width="0.2">', *paths, '</g>',
           '<path d="M 20 178 H 120 M 20 175 V 181 M 120 175 V 181" stroke="black" fill="none"/>',
           '<text x="20" y="188" font-family="sans-serif" font-size="4">100 mm calibration — do not scale to fit</text>',
           '<text x="10" y="200" font-family="sans-serif" font-size="3.5">16 red motor holes: 2.2 mm; 9 mm PCD. Black holes belong to the cut blank.</text>', '</svg>']
    # Overlay only the post-drilled holes, separately from the cutter profile.
    overlay = '<g transform="translate(105 96)" fill="none" stroke="#c22" stroke-width="0.25">' + ''.join(
        f'<circle cx="{x:.4f}" cy="{-y:.4f}" r="{d/2:.4f}"/>' for x, y, d in frame.motor_bolt_holes(f)) + '</g>'
    svg.insert(-1, overlay)
    (out / "POST_DRILL_1_TO_1.svg").write_text('\n'.join(svg))
    with (out / "POST_DRILL_COORDINATES.csv").open("w", newline="") as handle:
        w = csv.writer(handle); w.writerow(["hole", "x_mm", "y_mm", "diameter_mm", "process"])
        for i, (x, y, d) in enumerate(frame.motor_bolt_holes(f), 1): w.writerow([i, round(x, 5), round(y, 5), d, "post-drill; excluded from waterjet blank"])


def _assembly(out, solids, result):
    """Editable placement model; vendor components are labelled bounding envelopes."""
    cq = frame.cq
    f = result["frame_parameters"]
    shapes = [solids["bottom_plate"].val(), solids["top_plate"].val().translate((0, 0, f["bottom_t_mm"] + f["standoff_len_mm"]))]
    motors = [tuple(x) for x in result["measured"]["motor_centres_mm"]]
    for item in design.layout(f, result["parts"], motors):
        if item["id"] == "top_plate": continue
        x, y = item["xy"]
        if item["id"] == "battery": x = result["cg"]["battery_x_mm"]
        low, high = item["z"]
        if item["id"] in {"motor", "standoff"}:
            shape = cq.Workplane("XY").circle(item["half"][0]).extrude(high - low).val().translate((x, y, low))
        else:
            shape = cq.Workplane("XY").box(item["half"][0] * 2, item["half"][1] * 2, high - low).val().translate((x, y, (high + low) / 2))
        shapes.append(shape)
    cq.exporters.export(cq.Compound.makeCompound(shapes), str(out / "ASSEMBLY_ENVELOPES.step"))


def _readme(out, r):
    f, p, m, power = r["frame_parameters"], r["propulsion"], r["mass"], r["power"]
    failures = [k for k, v in r["checks"].items() if not v]
    lines = ["# HS-3G-B candidate build package", "",
        "This is a revised digital design for the same GPS/analog-FPV quad. No hardware was built, powered or flown. Purchase, fabrication and flight are not authorized by this package.", "",
        f"Native model checks: {len(r['checks']) - len(failures)}/{len(r['checks'])}; failures: {failures}. Independent acceptance is recorded separately in `verification.json`.", "",
        "## Revised configuration", "",
        f"Four F1404 KV2900 motors, Gemfan PMPC3028-3 1.5 mm props, CNHL 85704G 850 mAh 4S factory-XT60 battery, matching 12AWG supply lead, and the retained SpeedyBee F405 Mini stack. GPS, receiver, camera and analog VTX remain in the BOM.",
        f"The frame has a {f['wheelbase_mm']:g} mm diagonal, {f['bottom_t_mm']:g} mm bottom plate and {f['top_t_mm']:g} mm top plate. Native CAD selection tried: {r['design_iterations']}.", "",
        "## Quantitative result", "",
        f"- Modeled takeoff mass: {m['auw_g']:.2f} g, including a 12 g wiring allowance. Nominal reserve to 250 g: {250 - m['auw_g']:.2f} g. The named +5 g battery uncertainty leaves {250 - m['auw_g'] - 5:.2f} g for other unmodeled mass. Weigh the entire finished aircraft.",
        f"- Manufacturer bench-table full-command current: {power['bench_total_a']:.1f} A total. A square-law voltage sensitivity assumption and 20% design factor give {power['design_current_a']:.2f} A. Pack nameplate continuous rating: {power['battery_continuous_a']:.1f} A; connector rating: {power['connector_rated_a']:.0f} A under its stated 12AWG/temperature-rise test conditions. Verify real sag and temperatures; these calculations are not thermal qualification.",
        f"- Full-command thrust: {p['max_thrust_total_g']:.1f} g; T/W {p['tw_ratio_full']:.2f} at modeled mass. Hover duration estimate: {p['hover_time_min']:.1f} min; extrapolated below the source table, not measured endurance.",
        f"- Static minimum prop radial clearance: {r['clearance']['min_radial_mm']:.2f} mm. Strap: 10 x 200 mm; required modeled wrap including overlap {r['strap']['required_length_mm']:.2f} mm. Battery envelope uses the conservative 62 x 33 x 33 mm interpretation of conflicting maker dimensions.",
        f"- BOM snapshot subtotal: US${r['bom_total_usd_snapshot']:.2f}, including two batteries and two prop packs. Some prices and the cutting allowance are retained estimates, not current quotes; freight, tax, tools, radio and goggles are excluded.", "",
        "## Manufacturing sequence", "",
        "1. Confirm actual motor dimensions and usable M2 thread depth, battery envelope and controller revision/stock before ordering or machining.",
        "2. Obtain a composite shop quote for `cutter_blanks/*.dxf` and the separate post-drilling operation. These blanks omit all 16 M2 motor holes; their minimum holes and webs pass the cited cutting screen.",
        "3. After measurement and shop review, locate the 16 post-drilled 2.2 mm holes using `POST_DRILL_COORDINATES.csv` and the stack-hole datum. The SVG is 1:1 in millimetres; verify its 100 mm calibration line. A printed sheet does not establish machining accuracy.",
        "4. `finished_geometry/*` describes the final drilled parts. It still fails the waterjet-only motor-hole/web rules, intentionally: those small features belong to a separately qualified drilling process. Do not submit that DXF as the cut blank.",
        f"5. Review the computed fastener stack-up in `results.json`: M2x5 motor screws have {r['hardware']['motor_thread_engagement_mm']:.2f} mm nominal engagement; the actual safe thread depth remains unmeasured. Stack screws are M3x{r['hardware']['stack_screw_len_mm']:g}. Use the retained M3x30 standoffs and 5 mm stack spacers.",
        f"6. Place the battery crosswise under the bottom plate at modeled x={r['cg']['battery_x_mm']:.2f} mm, then adjust from actual balance measurements. Install GPS/receiver/FPV equipment, capacitor and strain relief. `ASSEMBLY_ENVELOPES.step` contains the editable frame and component placement envelopes, not detailed vendor solids or verified mounts.", "",
        "## Firmware and wiring", "",
        "`firmware/evidence.json` pins the official INAV 9.1.0 SPEEDYBEEF405MINI HEX, source commit and SHA-256 values. HS verifies the upstream binary; it does not claim to have compiled or flashed it. Upstream source files and licence accompany that evidence.",
        "`firmware/REVIEW_ONLY.cli` is a source-checked partial starting configuration, not a tuned or flight-ready profile. Use `WIRING.csv` to review UART1 receiver/CRSF, UART2 GNSS and I2C compass; UART4 remains reserved for onboard Bluetooth. Confirm VTX protocol before allocating UART3. Complete mixer/motor mapping, receiver/GPS setup, calibration and failsafe with the actual hardware.",
        "No electrical calculation relies on INAV throttle scaling: its mixer can add attitude corrections after scaling, and digital output is mapped to the protocol range. The revised hardware is sized against the full-command table instead.", "",
        "## Remaining acceptance work", "",
        "The thinner laminate and post-drilled pads need shop and structural review. Beam/arm resonance sensitivity is reported in `results.json`; measured vibration and deflection data are still required. Qualify polarity, isolation, current-sensor calibration, supply sag, lead/connector/motor heating and whole-aircraft mass before any authorized powered test. Verify controls, compass/GNSS and failsafe before considering supervised flight.",
        "The maker marks the selected controller discontinued. The input file records a dealer stock lead; actual stock, shipping and board identity must be confirmed. This blocks a ready-to-purchase claim.", "",
        "The retained build-versus-buy study favors a commercial GPS BNF on cash cost. This candidate is chosen to advance the editable engineering/operator objective; it is not a claim to be the cheapest way to acquire a flying drone.", "",
        "## Source trail", ""]
    for part in r["parts"]:
        if part["id"] in {"motor", "prop", "battery", "frame_cut"}:
            for source in part["sources"]: lines.append(f"- {part['id']}: {source['url']} ({source.get('accessed', 'baseline snapshot')})")
    lines += [f"- Connector rating: {inputs()[1]['power_path']['source']}", "- All supporting values, scope limits, source hashes and assumptions: `results.json`, `inputs/` in the revision source, and `verification.json`.", ""]
    (out / "README.md").write_text("\n".join(lines))


def build(out: Path, cache: Path | None = None):
    if out.exists() and any(out.iterdir()):
        raise ValueError("Use a new/empty output directory; stale receipts cannot be reused")
    out.mkdir(parents=True, exist_ok=True)
    base, cfg, parts, hw, f, table = inputs()
    attempts = []
    for wheelbase in cfg["wheelbase_candidates_mm"]:
        trial_frame = {**f, "wheelbase_mm": wheelbase}
        solids = frame.build(trial_frame)
        measured = frame.measure(solids, trial_frame)
        result = analyze(measured, frame_parameters=trial_frame)
        attempts.append({"wheelbase_mm": wheelbase, "measured_mass_g": result["mass"]["auw_g"],
            "min_prop_clearance_mm": result["clearance"]["min_radial_mm"],
            "failed_checks": [k for k, v in result["checks"].items() if not v]})
        if all(result["checks"].values()):
            f = trial_frame
            break
    else:
        raise ValueError("No candidate meets the fixed engineering constraints: " + json.dumps(attempts))
    blank = {"bottom_plate": frame.bottom_plate(f, motor_bolts=False), "top_plate": solids["top_plate"]}
    frame.export(solids, out / "finished_geometry")
    frame.export(blank, out / "cutter_blanks")
    result["design_iterations"] = attempts
    result["manufacturing"] = {"cutter_blank": frame.manufacturability(blank, f, base["cutter_rules"]),
        "finished_geometry_against_cutting_rules": frame.manufacturability(solids, f, base["cutter_rules"]),
        "post_drilled_holes": 16, "cutter_acceptance_obtained": False, "shop_drilling_qualified": False}
    result["checks"]["cutter_blank_rules"] = all(not r["holes_below_rule"] and not r["webs_below_rule"] for r in result["manufacturing"]["cutter_blank"].values())
    result["source_sha256"] = source_identity()
    _drill_sheet(out, blank, f)
    _assembly(out, solids, result)
    _evidence(out, cache)
    (out / "firmware/REVIEW_ONLY.cli").write_text(
        '# HS-3G-B / INAV 9.1.0 SPEEDYBEEF405MINI — review before any hardware use\n'
        '# Partial starting configuration, not a flight-ready or tuned profile. No save/arm commands.\n'
        '# Assign UART1 serial receiver and UART2 GPS in Configurator; reserve UART4 for BLE.\n'
        + ''.join(f'set {k} = {v}\n' for k, v in cfg["firmware_settings"].items()) +
        '# Confirm battery capacity unit, receiver/GPS ports, QUADX mixer, motor order/direction,\n'
        '# compass alignment, failsafe and calibrated current scale before supervised testing.\n'
        '# throttle_scale is not a hard motor-output cap; no power check relies on it.\n')
    with (out / "BOM.csv").open("w", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(result["bom"][0])); w.writeheader(); w.writerows(result["bom"])
    with (out / "WIRING.csv").open("w", newline="") as handle:
        w = csv.writer(handle); w.writerow(["function", "device", "connection", "status"])
        w.writerows([['main power','factory XT60 battery','XT60 / 12AWG matching lead to ESC BAT+ and BAT-','verify polarity, soldering, strain relief and temperature before loading'],
            ['receiver','RadioMaster RP1 V2','TX -> RX1; RX -> TX1; 5V and GND','configure UART1 serial RX / CRSF; check actual pad labels'],
            ['GNSS','BLITZ Mini M10 GPS V2','TX -> RX2; RX -> TX2; approved module supply and GND','configure UART2 GPS; verify module voltage and padout'],
            ['compass','GNSS compass','SDA -> SDA; SCL -> SCL; common GND','I2C1 PB9/PB8; verify orientation and calibration'],
            ['VTX control','HGLRC Zeus Nano','reserve UART3 TX3 for supported control protocol','confirm actual VTX protocol; not preconfigured'],
            ['reserved','onboard Bluetooth','UART4','do not allocate to another peripheral'],
            ['ESC telemetry','ESC connector','UART5 RX','not a spare full-duplex UART']])
    dump(out / "results.json", result)
    _readme(out, result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--out", required=True, type=Path)
    p.add_argument("--evidence-cache", type=Path)
    a = p.parse_args(); r = build(a.out, a.evidence_cache)
    print(json.dumps({"revision": r["revision"], "auw_g": r["mass"]["auw_g"], "checks": r["checks"]}, indent=2))
    return 0 if all(r["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
