"""Bounded 3D connector/service insertion-volume screen for SPI housing.

This does NOT claim a selected female cable harness exists. Manufacturer facts
describe the BOM's two *male headers*. A separately proposed female receptacle
is used only as a conservative geometric investigation scenario. Never promote
this result to an approved physical mating interface.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .assembly_plan import build_assembly_plan
from .connector_access_plan import inspect_connector_access

SCHEMA = "hardware_splicer.connector_mating_volume.v1"
MALE_PARTS = {
    "J1": {
        "manufacturer": "Samtec", "mpn": "TSW-106-07-T-S", "positions": 6,
        "mating_post_length_mm": 5.84, "insulation_height_mm": 2.54,
        "pitch_mm": 2.54,
        "source": "https://www.samtec.com/products/tsw-106-07-t-s",
    },
    "JP1": {
        "manufacturer": "Samtec", "mpn": "TSW-102-07-T-S", "positions": 2,
        "mating_post_length_mm": 5.84, "insulation_height_mm": 2.54,
        "pitch_mm": 2.54,
        "source": "https://www.samtec.com/products/tsw-102-07-t-s",
    },
}
PROPOSED_RECEPTACLES = {
    "J1": {
        "mpn": "SSW-106-02-T-S", "positions": 6, "height_mm": 8.51,
        "source": "https://www.digikey.com/en/products/detail/samtec-inc/SSW-106-02-T-S/1112794",
    },
    "JP1": {
        "mpn": "SSW-102-02-T-S", "positions": 2, "height_mm": 8.51,
        "source": "https://www.digikey.com/en/products/detail/samtec-inc/SSW-102-02-T-S/1112798",
    },
}
PCB_BOTTOM_Z_MM = 5.2
SHELL_TOP_Z_MM = 25.0
CAVITY = (3.0, 107.0, 3.0, 67.0)
BOSS_RADIUS_MM = 3.3
BOSS_Z = (1.8, 5.2)
INSERTION_EXTRA_ABOVE_RIM_MM = 10.0


def _sha(blob: bytes) -> str:
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def _finite(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("non-numeric insertion allowance")
    x = float(value)
    if not math.isfinite(x):
        raise ValueError("non-finite insertion allowance")
    return x


def _overlap(box: dict, other: dict) -> bool:
    return all(box["min_"+axis] < other["max_"+axis]
               and other["min_"+axis] < box["max_"+axis] for axis in ("x", "y", "z"))


def inspect_mating_volume(*, pcb_path: str | Path, bom_path: str | Path,
                          mounting_manifest_path: str | Path,
                          output_path: str | Path | None = None,
                          radial_allowance_mm: float = 2.0) -> dict:
    allowance = _finite(radial_allowance_mm)
    if allowance < 0 or allowance > 12:
        raise ValueError("insertion-envelope allowance must be 0..12 mm")
    pcb = Path(pcb_path).read_bytes()
    bom = Path(bom_path).read_bytes()
    mounts_raw = Path(mounting_manifest_path).read_bytes()
    board = build_assembly_plan(pcb.decode("utf-8"), pcb_sha256=_sha(pcb))
    mounting = json.loads(mounts_raw)
    if mounting.get("input_pcb_sha256") != _sha(pcb):
        raise ValueError("mount source does not match electrical PCB")
    if len(mounting.get("mounts", [])) != 4:
        raise ValueError("four KiCad-sourced mounting points required")
    rows = list(csv.DictReader(bom.decode("utf-8-sig").splitlines()))
    assigned = {ref: row for row in rows for ref in (row.get("References") or "").split()}
    if not set(MALE_PARTS) <= set(assigned):
        raise ValueError("source BOM missing exact male connectors")
    byref = {p["ref"]: p for p in board["parts"]}
    access = inspect_connector_access(
        pcb_path=pcb_path, mounting_manifest_path=mounting_manifest_path,
        side_margin_mm=allowance,
    )
    traces = {x["ref"]: x for x in access["connectors"]}
    pcb_top = PCB_BOTTOM_Z_MM + board["board"]["thickness_mm"]
    findings = []
    for ref, part in MALE_PARTS.items():
        bom_row = assigned[ref]
        if (bom_row["Manufacturer"] != part["manufacturer"]
                or bom_row["Manufacturer Part Number"] != part["mpn"]
                or bom_row.get("Initial Assembly") != "FIT"):
            raise ValueError(f"{ref}: qualified header MPN/assembly source changed")
        if len(traces[ref]["pcb_relative_pin_positions"]) != part["positions"]:
            raise ValueError("mating connector pin count disagrees with KiCad")
        exposed_pin_top = pcb_top + part["insulation_height_mm"] + part["mating_post_length_mm"]
        upper_receptacle = pcb_top + part["insulation_height_mm"] + PROPOSED_RECEPTACLES[ref]["height_mm"]
        keepout = traces[ref]["nominal_courtyard_plus_margin_mm"]
        approach = {
            "min_x": keepout["x_min"], "max_x": keepout["x_max"],
            "min_y": keepout["y_min"], "max_y": keepout["y_max"],
            "min_z": round(pcb_top+part["insulation_height_mm"],3),
            "max_z": SHELL_TOP_Z_MM + INSERTION_EXTRA_ABOVE_RIM_MM,
        }
        xwall = approach["min_x"] >= CAVITY[0] and approach["max_x"] <= CAVITY[1]
        ywall = approach["min_y"] >= CAVITY[2] and approach["max_y"] <= CAVITY[3]
        with_bosses = []
        for mount in mounting["mounts"]:
            mx, my = map(_finite, mount["cad_shell_center_xy_mm"])
            boss = {"min_x":mx-BOSS_RADIUS_MM,"max_x":mx+BOSS_RADIUS_MM,
                    "min_y":my-BOSS_RADIUS_MM,"max_y":my+BOSS_RADIUS_MM,
                    "min_z": BOSS_Z[0], "max_z": BOSS_Z[1]}
            with_bosses.append({"ref": mount["ref"], "3d_box_overlap":_overlap(approach,boss),
                                "geometry_basis":"bounding_box_overapprox_of_cylindrical_boss"})
        others = []
        box_board = board["board"]["outline"]["bbox"]
        mid=((box_board["x0"]+box_board["x1"])/2,(box_board["y0"]+box_board["y1"])/2)
        for p in board["parts"]:
            if p["ref"] == ref or p["do_not_populate"] or p["kind"] in ("mounting_hole","testpoint"):
                continue
            coords=p.get("corners") or []
            if len(coords)!=4:
                continue
            other = {
                "min_x":min(x[0] for x in coords) - mid[0] + 55,
                "max_x":max(x[0] for x in coords) - mid[0] + 55,
                "min_y":min(x[1] for x in coords) - mid[1] + 35,
                "max_y":max(x[1] for x in coords) - mid[1] + 35,
                "min_z":pcb_top,
                "max_z":pcb_top + _finite(p["height_mm"]),
            }
            if _overlap(approach,other):
                others.append({"ref":p["ref"],"height_basis":p["height_basis"],
                               "courtyard_volume_overlap":True})
        nominal_blockers = []
        if not xwall or not ywall:
            nominal_blockers.append("insertion_keepout_overlaps_open_shell_walls")
        if any(p["3d_box_overlap"] for p in with_bosses):
            nominal_blockers.append("insertion_keepout_overlaps_mounting_boss")
        if others:
            nominal_blockers.append("insertion_keepout_overlaps_approximate_board_component_volume")
        findings.append({
            "ref":ref,"source_male_header":part,"male_header_footprint":bom_row["Footprint"],
            "proposed_female_receptacle_NOT_SELECTED_OR_WIRED":PROPOSED_RECEPTACLES[ref],
            "service_mode":"no_mate_for_jp1_initial_assembly" if ref=="JP1" else "provisional_receptacle_insertion",
            "source_pcb_top_z_mm":pcb_top,"source_male_pin_tip_z_mm":round(exposed_pin_top,3),
            "provisional_receptacle_upper_z_mm":round(upper_receptacle,3),
            "recess_from_shell_top_to_pin_tip_mm":round(SHELL_TOP_Z_MM-exposed_pin_top,3),
            "recess_from_shell_top_to_provisional_receptacle_top_mm":round(SHELL_TOP_Z_MM-upper_receptacle,3),
            "3d_insertion_sweep_aabb_mm":approach,
            "open_top_xy_in_shell":xwall and ywall,
            "boss_intersections":with_bosses,
            "component_intersections":others,
            "nominal_3d_blockers":nominal_blockers,
            "mating_housing_body_width_mm_authenticated":False,
            "mating_housing_body_length_mm_authenticated":False,
            "mating_receptacle_wiring_solution_selected":False,
            "cable_bend_radius_and_strain_relief_authenticated":False,
            "cable_or_jumper_operation_tested":False,
        })
    geometric_blockers = [r["ref"] for r in findings if r["nominal_3d_blockers"]]
    output = {
        "schema":SCHEMA,
        "status": ("blocked_nominal_3d_insertion_geometry" if geometric_blockers
                   else "blocked_unqualified_mating_hardware_despite_nominal_3d_clearance"),
        "source_pcb_sha256":_sha(pcb),"source_bom_sha256":_sha(bom),
        "source_mount_manifest_sha256":_sha(mounts_raw),
        "examined_connector_count":len(findings),
        "nominal_geometry_blocked_references":geometric_blockers,
        "header_geometry_source":"Samtec and distributor part-specific specifications",
        "3d_insertion_method":"axis_aligned_approximation_not_exact_mating_shape",
        "open_top_service_allowance_above_rim_mm":INSERTION_EXTRA_ABOVE_RIM_MM,
        "radial_clearance_assumption_mm":allowance,
        "connectors":findings,
        "exact_counterpart_harness_selected":False,
        "physical_access_verified":False,
        "qualified_mating_geometry_verified":False,
        "fabrication_authorized":False,
        "power_on_authorized":False,
        "release_authorized":False,
    }
    if output_path is not None:
        dest=Path(output_path)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(output,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return output
