#!/usr/bin/env python3
"""Whole-workflow HS gadget coverage benchmark.

Exercises actual catalog compilers and donor splice engines when requested, plus
cross-domain feasibility, electromechanical envelopes and real-device work
packages. All examples are non-operational; nothing certifies fabrication.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from hardware_splicer.assembly_plan import build_assembly_plan
from hardware_splicer.build_compiler import compile_catalog_build
from hardware_splicer.catalog import CATALOG_BUILD_IDS
from hardware_splicer.device_splice_feasibility import assess_device_splice
from hardware_splicer.electromechanical_fit import screen_board_enclosure_fit
from hardware_splicer.real_device_work_package import compile_work_package
from hardware_splicer.splice_manifest import (
    evaluate_splice_case, get_splice_case, load_splice_manifest, run_splice_case,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "eval" / "device_splice_feasibility"
GADGETS = {
    "sensor_logging_station": "sensor_logger",
    "desk_information_display": "room_display_station",
    "network_status_indicator": "network_status_indicator",
    "plant_watering_controller": "automatic_plant_watering",
    "smart_low_voltage_control": "smart_relay_box",
    "usb_fume_extraction": "usb_fume_extractor",
    "usb_uart_debugging": "usb_uart_debug_adapter",
    "low_voltage_power_adapter": "bench_power_adapter",
    "audio_amplifier_box": "small_audio_amp_box",
    "inspection_pan_tilt": "inspection_motion_fixture",
    "salvaged_rc_drive": "robot_drive_base",
    "printer_plotter_stage": "plotter_motion_stage",
}
DONOR_IDS = ("robot_drive_from_rc_toy", "printer_motion_stage")

def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def _mechanical_fit(height: float = 5.0) -> dict:
    board = {
        "source_mode": "synthetic_declared",
        "board": {"dimensions_mm": {"w": 40, "d": 20, "t": 1.6}},
        "components": [{
            "ref": "J1", "center_xy_mm": [10, 0],
            "size_xyz_mm": [8, 6, height],
            "layer": "F.Cu", "rotation_deg": 0,
        }],
    }
    enclosure = {
        "enclosure": {"inner_dimensions_mm": {"w": 50, "d": 30, "h": 15}, "floor_mm": 2},
        "placements": {"pcb": {"origin_xyz_mm": [0, 0, 6]}},
    }
    return screen_board_enclosure_fit(board, enclosure)

def _candidates():
    steamdeck = _read(FIXTURES / "steamdeck_oled_ssd.json")
    base = _read(FIXTURES / "controller_display_demo.json")
    base["electromechanical_fit"] = _mechanical_fit()
    yield "steamdeck_ssd_replacement_source_lead", steamdeck, "unknown"
    yield "controller_display_regulator_enclosure", base, "adaptable_pending_validation"

    no_regulator = copy.deepcopy(base)
    no_regulator["id"] = "synthetic_display_without_regulator"
    no_regulator["interfaces"][2].pop("adaptation")
    yield "display_with_unresolved_power_conversion", no_regulator, "blocked"

    collision = copy.deepcopy(base)
    collision["id"] = "synthetic_tall_connector_collision"
    collision["electromechanical_fit"] = _mechanical_fit(height=20)
    yield "display_with_enclosure_lid_collision", collision, "blocked"

    missing_firmware = copy.deepcopy(base)
    missing_firmware["id"] = "synthetic_missing_firmware_driver"
    missing_firmware["interfaces"][4]["required"]["driver_available"] = None
    yield "reused_controller_missing_firmware", missing_firmware, "unknown"

    logic_mismatch = copy.deepcopy(base)
    logic_mismatch["id"] = "synthetic_usb_debug_level_mismatch"
    logic_mismatch["interfaces"][1]["provided"]["logic_voltage_v"] = 5
    yield "usb_debug_signal_level_mismatch", logic_mismatch, "blocked"

    overloaded = copy.deepcopy(base)
    overloaded["id"] = "synthetic_overloaded_shared_rail"
    overloaded["interfaces"][0]["required"]["current_required_a"] = 1.9
    yield "shared_rail_overload", overloaded, "blocked"

    sensor_station = copy.deepcopy(base)
    sensor_station["id"] = "synthetic_sensor_station_matched"
    sensor_station["interfaces"][2]["provided"].update({
        "voltage_min_v": 3.3, "voltage_max_v": 3.3,
    })
    sensor_station["interfaces"][2]["provided"].pop("rail_id", None)
    sensor_station["interfaces"][2].pop("adaptation")
    yield "sensor_station_declared_interfaces_only", sensor_station, "compatible_on_paper"

def _run_feasibility() -> list[dict]:
    rows = []
    case = {
        "id": "gadget_capability_acceptance", "device": "synthetic low-voltage demonstrator",
        "kind": "new_build", "deliverables": ["wiring and mechanical interface plan"],
        "acceptance": ["isolated bench validation"],
    }
    review = {"operator_casefile": {
        "build_or_repair_sequence": ["Identify and inspect source components"],
        "critical_technical_unknowns": ["physical testing not performed"],
        "compatible_parts_or_requirements": ["Verified wiring and mounting"],
    }}
    for name, candidate, expected in _candidates():
        try:
            report = assess_device_splice(candidate)
            package = compile_work_package(case, review, splice_candidate=candidate)
            actual = report["overall_status"]
            pass_flag = (actual == expected and
                         package["device_splice_feasibility"]["overall_status"] == actual and
                         package["engineering_readiness"] == "blocked" and
                         not report["power_on_authorized"] and
                         not report["release_authorized"])
            rows.append({
                "gadget": name, "expected": expected, "actual": actual,
                "pass": pass_flag, "interface_checks": len(report["checks"]),
                "required_actions": len(report["required_actions"]),
                "work_package_steps": len(package["work_steps"]),
                "approval": False, "evidence": "synthetic_or_source_lead_only",
            })
        except Exception as exc:
            rows.append({"gadget": name, "expected": expected, "actual": "error",
                         "pass": False, "error": f"{type(exc).__name__}: {exc}"[:400]})
    return rows

def _catalog_assembly(pcb_path: Path, folder: Path) -> dict:
    """Feed the actual generated KiCad layout into HS assembly and fit engines.

    The new enclosure is a *proposed* clearance envelope sized from source
    geometry, not a previously manufactured or physically measured case.
    """
    raw = pcb_path.read_text(encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
    plan = build_assembly_plan(raw, pcb_sha256=digest)
    width, depth = plan["board"]["size_mm"]
    thickness = plan["board"]["thickness_mm"]
    bbox = plan["board"]["outline"]["bbox"]
    center_x = (bbox["x0"] + bbox["x1"]) / 2
    center_y = (bbox["y0"] + bbox["y1"]) / 2
    components = []
    for part in plan["parts"]:
        if part["do_not_populate"] or part["kind"] == "mounting_hole":
            continue
        corners = part["corners"]
        if not corners:
            continue
        xs = [float(p[0]) for p in corners]
        ys = [float(p[1]) for p in corners]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        components.append({
            "ref": part["id"],
            "center_xy_mm": [(min_x + max_x) / 2 - center_x,
                             (min_y + max_y) / 2 - center_y],
            "size_xyz_mm": [max_x - min_x, max_y - min_y, part["height_mm"]],
            "layer": "B.Cu" if part["side"] == "back" else "F.Cu",
            "rotation_deg": 0,
        })
    max_height = max((p["height_mm"] for p in plan["parts"]
                      if not p["do_not_populate"]), default=0)
    # 10 mm XY allowance for access and tolerances; overhead is illustrative.
    inner = {"w": width + 20, "d": depth + 20,
             "h": max(25.0, 17 + max_height)}
    placement = {
        "source_mode": "generated_kicad_courtyard_and_typical_heights",
        "board": {"dimensions_mm": {"w": width, "d": depth, "t": thickness}},
        "components": components,
    }
    assembly = {
        "enclosure": {"inner_dimensions_mm": inner, "floor_mm": 2},
        "placements": {"pcb": {"origin_xyz_mm": [0, 0, 6]}},
    }
    fit = screen_board_enclosure_fit(placement, assembly)
    (folder / "ASSEMBLY_PLAN.json").write_text(
        json.dumps(plan, indent=2, allow_nan=False) + "\\n", encoding="utf-8")
    (folder / "PROPOSED_ENCLOSURE_FIT.json").write_text(
        json.dumps(fit, indent=2, allow_nan=False) + "\\n", encoding="utf-8")
    return {
        "pcb_source_sha256": digest,
        "source_board_size_mm": [width, depth, thickness],
        "source_footprints": plan["counts"]["parts"],
        "assembly_steps": plan["counts"]["steps"],
        "fitted_component_envelopes": len(components),
        "proposed_enclosure_inner_dimensions_mm": inner,
        "enclosure_fit_status": fit["status"],
        "enclosure_fit_blockers": fit["blocker_count"],
        "component_heights_physically_measured": False,
        "exact_3d_collision_verified": False,
        "part_identity_and_connector_mating_verified": False,
    }

def _run_catalog(out_root: Path, all_catalog: bool) -> list[dict]:
    cases = ({name: name for name in CATALOG_BUILD_IDS}
             if all_catalog else GADGETS)
    rows = []
    for family, build_id in cases.items():
        row = {
            "gadget": family, "build_id": build_id, "catalog_declared": build_id in CATALOG_BUILD_IDS,
            "physical_validation_performed": False, "release_authorized": False,
        }
        try:
            result = compile_catalog_build(build_id, out_root / "catalog" / family,
                                           export_gerber=False)
            quality = result.design_quality
            pcb = Path(result.kicad_pcb_file) if result.kicad_pcb_file else None
            board_exists = bool(pcb and pcb.is_file() and
                                pcb.read_text(encoding="utf-8").startswith("(kicad_pcb"))
            assembly_check = (_catalog_assembly(pcb, out_root / "catalog" / family)
                              if board_exists else None)
            row.update({"source_bound_assembly": assembly_check,
                "compile_ok": bool(result.ok), "build_graph_compiled": quality.get("build_graph_compiled"),
                "drc_pass": quality.get("drc_pass"),
                "electrical_safety_pass": quality.get("electrical_safety_pass"),
                "pcb_exported": board_exists,
                "gerber_exported": False,
                "pass": all((result.ok, quality.get("build_graph_compiled"),
                             quality.get("drc_pass"), quality.get("electrical_safety_pass"),
                             board_exists, assembly_check is not None,
                             assembly_check is not None and
                             assembly_check["enclosure_fit_blockers"] == 0)),
                "error": result.error,
            })
        except Exception as exc:
            row.update({"pass": False, "compile_ok": False,
                        "error": f"{type(exc).__name__}: {exc}"[:450]})
        rows.append(row)
        print(f"CATALOG {family}: {'pass' if row['pass'] else 'blocked'}", flush=True)
    return rows

def _run_donors(out_root: Path) -> list[dict]:
    manifest = load_splice_manifest(ROOT / "examples" / "splice" / "manifest.json")
    rows = []
    os.environ.setdefault("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    for case_id in DONOR_IDS:
        case = get_splice_case(manifest, case_id)
        row = {"case_id": case_id, "expected_build_id": case["expected_build_id"],
               "physical_donor_test_performed": False, "release_authorized": False}
        try:
            result = run_splice_case(case, out_dir=out_root / "donors" / case_id,
                                     export_gerber=False)
            verdict = evaluate_splice_case(result, case)
            row.update({"pass": verdict["passed"],
                        "compiler_template": result["build_id"],
                        "circuit_backed_blocks": result["circuit_backed_block_count"],
                        "drc_pass": result["drc_pass"],
                        "evaluation": verdict})
        except Exception as exc:
            row.update({"pass": False, "error": f"{type(exc).__name__}: {exc}"[:450]})
        rows.append(row)
        print(f"DONOR {case_id}: {'pass' if row['pass'] else 'blocked'}", flush=True)
    return rows

def run(out_root: Path, all_catalog: bool, skip_compile: bool, skip_donors: bool) -> dict:
    out_root.mkdir(parents=True, exist_ok=True)
    feasibility = _run_feasibility()
    builds = [] if skip_compile else _run_catalog(out_root, all_catalog)
    donors = [] if skip_donors else _run_donors(out_root)
    total = feasibility + builds + donors
    result = {
        "schema": "hardware_splicer.gadget_capability_acceptance.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "simulation_and_software_compilation_only",
        "catalog_template_count": len(CATALOG_BUILD_IDS),
        "coverage": {
            "feasibility_scenarios": len(feasibility),
            "catalog_compilations": len(builds),
            "donor_splice_cases": len(donors),
            "passed": sum(bool(row["pass"]) for row in total),
            "failed": sum(not row["pass"] for row in total),
        },
        "feasibility": feasibility, "catalog": builds, "donor_splice": donors,
        "physical_assembly_validated": False, "fabrication_authorized": False,
        "device_operation_verified": False, "release_authorized": False,
    }
    (out_root / "GADGET_CAPABILITY_ACCEPTANCE.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--all-catalog", action="store_true")
    parser.add_argument("--skip-compile", action="store_true")
    parser.add_argument("--skip-donors", action="store_true")
    args = parser.parse_args()
    root = args.out or Path(tempfile.mkdtemp(prefix="hs-gadget-acceptance-"))
    report = run(root, args.all_catalog, args.skip_compile, args.skip_donors)
    print(json.dumps({"report": str(root / "GADGET_CAPABILITY_ACCEPTANCE.json"),
                      "coverage": report["coverage"]}, indent=2))
    if report["coverage"]["failed"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
