#!/usr/bin/env python3
"""Independently reimport HS-3G-B CAD and check its manufacturing and evidence handoff."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("hs3g_revision_build", HERE / "build_package.py")
candidate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(candidate)


def verify(out: Path):
    import cadquery as cq
    import ezdxf
    import yaml
    frame, design = candidate.frame, candidate.design
    base, cfg, parts, hw, f, table = candidate.inputs()
    result = json.loads((out / "results.json").read_text())
    selected_wheelbase = result["frame_parameters"]["wheelbase_mm"]
    if selected_wheelbase not in cfg["wheelbase_candidates_mm"]:
        raise ValueError("Selected wheelbase is outside the registered search bounds")
    f = {**f, "wheelbase_mm": selected_wheelbase}
    checks = {}
    checks["source_identity"] = result.get("source_sha256") == candidate.source_identity()
    finished = {p: cq.importers.importStep(str(out / "finished_geometry" / f"hs3g_{p}.step")) for p in ["bottom_plate", "top_plate"]}
    blank = {p: cq.importers.importStep(str(out / "cutter_blanks" / f"hs3g_{p}.step")) for p in finished}
    actual = frame.measure(finished, f)
    checks["configured_frame_dimensions"] = result["frame_parameters"] == f and all(abs(d - selected_wheelbase) < 0.01 for d in actual["diagonal_motor_spacing_mm"])
    checks["native_solids"] = all(s.val().isValid() and len(s.val().Solids()) == 1 for s in [*finished.values(), *blank.values()])
    checks["motor_mount_pattern"] = actual["motor_count"] == 4 and actual["motor_bolt_pcd_counts"] == {"9": 16}
    checks["measured_geometry_receipt"] = all(abs(actual[k] - result["measured"][k]) < 0.02 for k in ["bottom_volume_mm3", "top_volume_mm3"])
    measurements = candidate.analyze(actual, frame_parameters=f)
    checks["derived_model_receipt"] = all(measurements[k] == result[k] for k in ["mass", "power", "propulsion", "hardware", "cg", "clearance", "strap", "bom"])
    with (out / "BOM.csv").open() as handle:
        checks["bom_csv_matches_model"] = list(csv.DictReader(handle)) == [{k: str(v) for k, v in row.items()} for row in measurements["bom"]]
    for name, passed in measurements["checks"].items(): checks["model_" + name] = bool(passed)
    dfm = frame.manufacturability(blank, f, base["cutter_rules"])
    checks["cut_blank_dfm"] = all(not r["holes_below_rule"] and not r["webs_below_rule"] for r in dfm.values())
    expected_removed_volume = 16 * math.pi * (f["motor_bolt_hole_d_mm"] / 2) ** 2 * f["bottom_t_mm"]
    actual_removed_volume = blank["bottom_plate"].val().Volume() - finished["bottom_plate"].val().Volume()
    checks["only_post_drill_material_removed"] = abs(actual_removed_volume - expected_removed_volume) < 0.02
    coords = list(csv.DictReader((out / "POST_DRILL_COORDINATES.csv").open()))
    expected = frame.motor_bolt_holes(f)
    checks["post_drill_coordinates"] = len(coords) == 16 and all(
        abs(float(row["x_mm"]) - x) < 0.0001 and abs(float(row["y_mm"]) - y) < 0.0001 and float(row["diameter_mm"]) == d
        for row, (x, y, d) in zip(coords, expected))
    for folder, expected_count in [("cutter_blanks", 0), ("finished_geometry", 16)]:
        doc = ezdxf.readfile(out / folder / "hs3g_bottom_plate.dxf")
        count = sum(abs(c.dxf.radius - f["motor_bolt_hole_d_mm"] / 2) < 0.001 for c in doc.modelspace().query("CIRCLE"))
        checks[folder + "_motor_hole_count"] = count == expected_count
        for plate, volume_key in [("bottom_plate", "bottom_volume_mm3"), ("top_plate", "top_volume_mm3")]:
            mesh = design.mesh_report(out / folder / f"hs3g_{plate}.stl")
            volume = (blank if folder == "cutter_blanks" else finished)[plate].val().Volume()
            checks[folder + "_" + plate + "_mesh"] = mesh["watertight"] and abs(mesh["signed_volume_mm3"] / volume - 1) < 0.003
    lock = json.loads((HERE / "inputs/firmware-lock.json").read_text())
    for item in [*lock["sources"], {**lock["binary"], "path": "inav_9.1.0_SPEEDYBEEF405MINI.hex"}]:
        path = out / "firmware" / item["path"]
        checks["firmware_hash_" + item["path"]] = path.is_file() and candidate.sha(path) == item["sha256"]
    firmware_root = out / "firmware/src/main"
    settings = yaml.safe_load((firmware_root / "fc/settings.yaml").read_text())
    names = {row["name"]: row for group in settings["groups"] for row in group.get("members", [])}
    enums = {t["name"]: t["values"] for t in settings["tables"]}
    config_lines = (out / "firmware/REVIEW_ONLY.cli").read_text().splitlines()
    parsed_settings = {line[4:].split("=", 1)[0].strip(): line.split("=", 1)[1].strip() for line in config_lines if line.startswith("set ")}
    checks["cli_matches_declared_component_contract"] = parsed_settings == {k: str(v) for k, v in cfg["firmware_settings"].items()}
    settings_ok = True
    for line in config_lines:
        if not line.startswith("set "): continue
        name, value = [x.strip() for x in line[4:].split("=", 1)]
        spec = names.get(name)
        if spec is None: settings_ok = False; continue
        if "table" in spec:
            settings_ok &= value in enums[spec["table"]]
        else:
            num = float(value)
            for bound, direction in [("min", 1), ("max", -1)]:
                limit = spec.get(bound)
                if isinstance(limit, (float, int)): settings_ok &= (num - limit) * direction >= 0
    checks["cli_settings_exist_and_are_in_range"] = bool(settings_ok)
    target = (firmware_root / "target/SPEEDYBEEF405MINI/target.h").read_text()
    checks["correct_board_target"] = '#define USBD_PRODUCT_STRING     "SPEEDYBEEF405MINI"' in target
    checks["receiver_and_gps_uart_sources"] = all(x in target for x in ["#define USE_UART1", "#define USE_UART2", "#define USE_UART4 //Internally routed to BLE"])
    checks["partial_configuration_is_review_only"] = not any(line.strip().split(" ")[0] in {"save", "arm", "motor", "defaults"} for line in config_lines if line.strip() and not line.startswith("#"))
    # Check the actual HEX record checksums, not just a filename or a manifest claim.
    lines = (out / "firmware/inav_9.1.0_SPEEDYBEEF405MINI.hex").read_text().splitlines()
    try:
        records = [bytes.fromhex(line[1:]) for line in lines if line.startswith(":" )]
        checks["official_hex_records"] = len(records) == len(lines) and all(sum(r) % 256 == 0 and len(r) == r[0] + 5 for r in records) and records[-1][3] == 1
    except (ValueError, IndexError): checks["official_hex_records"] = False
    checks["no_physical_authority"] = all(result.get(k) is False for k in ["physical_validation", "fabrication_authorized", "power_on_authorized", "flight_authorized"])
    accepted = all(checks.values())
    report = {"schema": "hardware_splicer.hs3g_revision_verification.v1", "revision": "HS-3G-B",
        "engineering_acceptance": accepted, "scope": "CAD geometry, cut-blank process screen, declared component model, source-checked partial configuration and official firmware identity",
        "checks": checks, "failed_checks": [k for k, v in checks.items() if not v],
        "native_measurements": actual, "cutter_blank_dfm": dfm,
        "post_drill_removed_volume_mm3": round(actual_removed_volume, 3),
        "firmware_compiled_by_hs": False, "firmware_flashed": False, "configuration_complete": False,
        "purchase_ready": False, "fabrication_authorized": False, "power_on_authorized": False, "flight_authorized": False,
        "open_actions": ["Confirm exact controller stock and delivery; the maker marks this stack discontinued.",
            "Get a composite shop quote for both cut blanks and the separately specified 16-hole drilling operation; qualify drilling quality and frame stiffness.",
            "Measure actual motor mounting, M2 thread depth, propeller boss and battery envelope; verify the 200 mm strap and weigh the complete aircraft.",
            "Complete receiver/GPS/VTX setup, motor ordering, compass/accelerometer calibration, failsafe and current-sensor calibration before supervised bench work.",
            "Measure current/sag and connector/lead/motor temperatures under controlled load. Manufacturer C-ratings and voltage scaling assumptions are not bench measurements.",
            "Review arm resonance using measured vibration data; the beam model does not qualify the thinner laminate or drilled motor pads."]}
    report["artifact_sha256"] = {str(p.relative_to(out)): candidate.sha(p) for p in sorted(out.rglob("*")) if p.is_file() and p.name != "verification.json"}
    candidate.dump(out / "verification.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("package", type=Path); a = p.parse_args()
    try:
        r = verify(a.package)
    except (ValueError, KeyError, OSError) as e:
        candidate.dump(a.package / "verification.json", {"engineering_acceptance": False, "error": str(e),
            "fabrication_authorized": False, "power_on_authorized": False, "flight_authorized": False})
        print(str(e), file=sys.stderr); return 1
    print(json.dumps({"engineering_acceptance": r["engineering_acceptance"], "failed_checks": r["failed_checks"]}, indent=2))
    return 0 if r["engineering_acceptance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
