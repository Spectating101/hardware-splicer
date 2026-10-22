"""Generate mechanically constrained SolidCraft boss/through-hole features from KiCad.

Scoped intentionally to the frozen SPI flash adapter and a nominal *open*
shell. Geometry is a design candidate, NOT a manufacturer clearance signoff.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .assembly_plan import build_assembly_plan

SCHEMA = "hardware_splicer.pcb_derived_mounting_cad.v1"
BASE_RADIUS_MM = 3.30
SUGGESTED_THROUGH_RADIUS_MM = 1.65  # nominal M3 clearance, not tolerance validated
BASE_Z_MM = 1.8
BOSS_HEIGHT_MM = 3.4
HOLE_BASE_Z_MM = -0.2
HOLE_CUT_HEIGHT_MM = 5.6
EXPECTED_MOUNT_REFS = {"H1", "H2", "H3", "H4"}


def _hash(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def generate_pcb_mounted_shell(*, pcb_path: str | Path, seed_recipe_path: str | Path,
                               output_recipe_path: str | Path,
                               output_manifest_path: str | Path) -> dict[str, Any]:
    board_file, seed_file = Path(pcb_path), Path(seed_recipe_path)
    pcb_bytes, recipe_bytes = board_file.read_bytes(), seed_file.read_bytes()
    plan = build_assembly_plan(pcb_bytes.decode("utf-8"), pcb_sha256=_hash(pcb_bytes))
    source_recipe = json.loads(recipe_bytes)
    commands = source_recipe.get("commands")
    if not isinstance(commands, list) or len(commands) != 8:
        raise ValueError("expected frozen eight-command open-shell seed")
    outline = plan["board"]["outline"]
    if outline["kind"] != "rectangle":
        raise ValueError("mounting boss generator requires rectangular KiCad board")
    bbox = outline["bbox"]
    mid = ((bbox["x0"]+bbox["x1"])/2, (bbox["y0"]+bbox["y1"])/2)
    outer = commands[1]["params"]
    p0, p1 = outer["p0"], outer["p1"]
    if p0 != [0,0] or p1 != [110,70] or commands[4]["params"].get("offset") != 2:
        raise ValueError("CAD seed dimensions changed without mounting geometry review")
    shell_center = (55.0, 35.0)
    mounting = sorted((part for part in plan["parts"] if part["kind"] == "mounting_hole"),
                      key=lambda p: p["ref"])
    if {part["ref"] for part in mounting} != EXPECTED_MOUNT_REFS or len(mounting) != 4:
        raise ValueError("expected exactly four uniquely numbered mounting holes")
    if any("MountingHole_3.2mm_M3" not in p["footprint"] for p in mounting):
        raise ValueError("KiCad anchor hole dimensions differ from expected nominal M3 pattern")
    constraints = []
    derived = [dict(row) for row in commands]
    cavity_limits = {"x_min": 3.0, "x_max": 107.0, "y_min": 3.0, "y_max": 67.0}
    for part in mounting:
        x = round(shell_center[0] + part["x"] - mid[0], 6)
        y = round(shell_center[1] + part["y"] - mid[1], 6)
        if not (cavity_limits["x_min"] + BASE_RADIUS_MM < x < cavity_limits["x_max"] - BASE_RADIUS_MM
                and cavity_limits["y_min"] + BASE_RADIUS_MM < y < cavity_limits["y_max"] - BASE_RADIUS_MM):
            raise ValueError(f"mounting boss {part['ref']} collides with nominal cavity wall")
        derived.extend([
            {"command": "solid.cylinder",
             "params": {"radius": BASE_RADIUS_MM, "height": BOSS_HEIGHT_MM,
                        "base": [x,y,BASE_Z_MM], "operation": "join",
                        "name": f"Boss_{part['ref']}"}},
            {"command": "solid.cylinder",
             "params": {"radius": SUGGESTED_THROUGH_RADIUS_MM,
                        "height": HOLE_CUT_HEIGHT_MM,
                        "base": [x,y,HOLE_BASE_Z_MM], "operation": "cut",
                        "name": f"Hole_{part['ref']}"}},
        ])
        constraints.append({
            "ref": part["ref"],
            "kicad_pcb_xy_mm": [part["x"], part["y"]],
            "cad_shell_center_xy_mm": [x,y],
            "hole_footprint": part["footprint"],
            "nominal_boss_outer_diameter_mm": 2*BASE_RADIUS_MM,
            "pilot_hole_diameter_mm": 2*SUGGESTED_THROUGH_RADIUS_MM,
            "boss_top_z_mm": BASE_Z_MM + BOSS_HEIGHT_MM,
            "board_bottom_nominal_z_mm": 5.2,
            "mounting_screw_length_and_torque_verified": False,
        })
    if any(abs(b["boss_top_z_mm"] - b["board_bottom_nominal_z_mm"]) > 1e-6
           for b in constraints):
        raise ValueError("mounting boss height disagrees with nominal PCB support elevation")
    pattern = sorted((round(c["cad_shell_center_xy_mm"][0], 2),
                      round(c["cad_shell_center_xy_mm"][1], 2)) for c in constraints)
    if pattern != [(14,14),(14,56),(96,14),(96,56)]:
        raise ValueError("unexpected frozen PCB mounting pattern")
    raw_output = (json.dumps({"commands": derived}, indent=2, allow_nan=False)+"\n").encode()
    report = {
        "schema": SCHEMA,
        "input_pcb_sha256": _hash(pcb_bytes),
        "input_shell_seed_sha256": _hash(recipe_bytes),
        "generated_solidcraft_script_sha256": _hash(raw_output),
        "mount_count": 4,
        "mounts": constraints,
        "added_operations": len(derived)-len(commands),
        "fastener_dimensions_verified": False,
        "cad_boolean_results_verified": False,
        "physical_fit_verified": False,
        "mechanical_release_authorized": False,
        "fabrication_authorized": False,
    }
    target, manifest = Path(output_recipe_path), Path(output_manifest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw_output)
    manifest.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return report
