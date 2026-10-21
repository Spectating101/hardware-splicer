"""Reference-PCB assembly dossier, tied to the actual KiCad source bytes.

This is a documentation and traceability check. It is *not* a real-world
component certification or validation of a fabricated board.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .assembly_plan import build_assembly_plan
from .electromechanical_fit import screen_board_enclosure_fit

SCHEMA = "hardware_splicer.reference_device_dossier.v1"


def build_reference_device_dossier(pcb_path: str | Path, *,
                                   output_dir: str | Path,
                                   declared_internal_enclosure_mm: dict[str, float] | None = None) -> dict[str, Any]:
    """Reconcile footprint placements, assembly sequence and packaging limitations."""
    source = Path(pcb_path)
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    plan = build_assembly_plan(raw.decode("utf-8"), pcb_sha256="sha256:" + digest)
    board = plan["board"]
    width, depth = board["size_mm"]
    thick = board["thickness_mm"]
    bbox = board["outline"]["bbox"]
    cx = (bbox["x0"] + bbox["x1"]) / 2
    cy = (bbox["y0"] + bbox["y1"]) / 2
    footprints = []
    unknowns = []
    for part in plan["parts"]:
        if part["do_not_populate"]:
            continue
        if part["kind"] == "mounting_hole":
            continue
        coords = part["corners"]
        xs, ys = [float(pt[0]) for pt in coords], [float(pt[1]) for pt in coords]
        ww, hh = max(xs) - min(xs), max(ys) - min(ys)
        footprints.append({
            "ref": part["id"],
            "center_xy_mm": [(max(xs) + min(xs)) / 2 - cx,
                             (max(ys) + min(ys)) / 2 - cy],
            "size_xyz_mm": [ww, hh, part["height_mm"]],
            "layer": "B.Cu" if part["side"] == "back" else "F.Cu",
            "rotation_deg": 0,
        })
        if not part["identity"].get("mpn"):
            unknowns.append({"ref": part["id"], "gap": "manufacturer_part_number_unverified"})
        if part["height_basis"] != "source_measured":
            unknowns.append({"ref": part["id"], "gap": "physical_component_height_unverified",
                             "estimate_basis": part["height_basis"]})
        if part["outline_basis"] != "manufacturer_3d_cad":
            unknowns.append({"ref": part["id"], "gap": "physical_component_outline_unverified",
                             "estimate_basis": part["outline_basis"]})

    fit = None
    if declared_internal_enclosure_mm is not None:
        # XY is centered in the declared interior; board rests above a
        # nominal 2 mm floor, with 4 mm clearance underneath.
        assembly = {
            "enclosure": {"inner_dimensions_mm": declared_internal_enclosure_mm,
                          "floor_mm": 2.0},
            "placements": {"pcb": {"origin_xyz_mm": [0, 0, 6]}},
        }
        fit = screen_board_enclosure_fit({
            "source_mode": "actual_pcb_courtyard_with_estimated_heights",
            "board": {"dimensions_mm": {"w": width, "d": depth, "t": thick}},
            "components": footprints,
        }, assembly)

    blockers = [
        {"type": "physical_material_gap", "description": "Manufacturer source identity, package heights and actual footprint geometry not verified"},
        {"type": "electrical_gap", "description": "No independent measured power/continuity/functional bring-up results"},
        {"type": "mechanical_gap", "description": "No confirmed enclosure, connector mating, access, tolerance or fastener stack"},
    ]
    if fit is not None and fit["blocker_count"]:
        blockers.append({"type": "enclosure_interference",
                         "description": f"Envelope screen found {fit['blocker_count']} overlaps"})
    dossier = {
        "schema": SCHEMA,
        "source": {"sha256": "sha256:" + digest, "bytes": len(raw), "filename": source.name},
        "board_size_mm": [width, depth, thick],
        "footprints": plan["counts"]["parts"],
        "fitted": plan["counts"]["fitted"],
        "assembly_steps": plan["counts"]["steps"],
        "unverified_geometry_findings": unknowns,
        "unresolved_gates": blockers,
        "electromechanical_fit": fit,
        "source_manufacturer_specs_authenticated": False,
        "physical_assembly_complete": False,
        "bench_operation_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    for name, payload in [
        ("REFERENCE_ASSEMBLY_PLAN.json", plan),
        ("REFERENCE_DEVICE_DOSSIER.json", dossier),
    ]:
        (target / name).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return dossier
