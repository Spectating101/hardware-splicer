"""Engine benchmark: varied engineering briefs run through HS's tools, scored from the project record.

An engine is proven by many different objectives going through the same machinery, not by one product built many
times. Each brief names the engineering checks a competent engineer would make for it; ``coverage()`` says which of
those HS has a tool for, so the missing features are ranked by how many briefs need them. ``score(project_id)`` reads an
objective project's ledger and status and scores how far the engine carried the brief, whoever or whatever drove it.

    python -m hardware_splicer.engine_benchmark coverage
    python -m hardware_splicer.engine_benchmark score <project_id>
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any

# engineering check -> HS toolbelt tool that makes it (None: no tool yet)
CHECKS: dict[str, str | None] = {
    "prior_art": "hs_prior_art_search",
    "junk_donors": "hs_junk_lookup",
    "parts_cost": "hs_bom_check",
    "board_parts_price": "hs_price_parts",
    "energy_runtime": "hs_energy_budget",
    "wheeled_drive_catalogue": "hs_size_rover_drive",
    "arm_joint_torque": "hs_size_arm_actuators",
    "arm_reach_collisions": "hs_motion_sweep",
    "multirotor_propulsion": "hs_check_propulsion",
    "rover_chassis_cad": "hs_rover_chassis",
    "custom_board": "hs_component_board",
    "schematic_review": "hs_review_kicad_schematic",
    # not yet in the toolbelt
    "salvaged_motor_sizing": None,       # size a drive from a donor motor's measured resistance, speeds and currents
    "enclosure_fit_cad": None,           # generic enclosure around given modules (not rover-specific)
    "printed_part_strength": None,       # stress/deflection of a printed link, bracket or frame
    "thermal": None,                     # heat from a compute module or regulator in a closed case
    "arm_urdf_from_design": None,        # turn an arm design into the URDF the motion sweep reads
    "arm_kinematics_firmware": None,     # inverse kinematics and joint firmware
    "buoyancy_trim": None,               # displacement, weight, centre of buoyancy vs gravity
    "underwater_thrust": None,           # thruster thrust vs drag at a target speed
    "pressure_housing": None,            # wall thickness and seals for a depth
    "tether_comms": None,                # tethered video/control link over a length
    "linear_axis_sizing": None,          # stepper, lead screw or belt axis speed and force
    "pump_flow": None,                   # pump head and flow for a lift and pipe
    "battery_pack_from_cells": None,     # series/parallel pack from tested salvaged cells, with protection
    "rf_antenna_placement": None,
    "structural_frame": None,            # drone or cart frame under load
}

BRIEFS: list[dict[str, Any]] = [
    {"id": "camera-rover", "objective": "A pet or home camera rover that streams video, built from junk where it can be",
     "market_query": "wheeled pet camera robot", "checks": ["prior_art", "junk_donors", "parts_cost", "energy_runtime",
     "salvaged_motor_sizing", "enclosure_fit_cad"]},
    {"id": "desk-arm", "objective": "A desktop robot arm that picks and places 200 g objects within 30 cm",
     "market_query": "desktop robot arm kit", "checks": ["prior_art", "junk_donors", "parts_cost", "arm_joint_torque",
     "arm_reach_collisions", "arm_urdf_from_design", "arm_kinematics_firmware", "custom_board", "energy_runtime",
     "printed_part_strength"]},
    {"id": "fielddeck", "objective": "A handheld field computer (Linux, keyboard, screen, battery) for outdoor work",
     "market_query": "rugged handheld linux computer", "checks": ["prior_art", "junk_donors", "parts_cost", "energy_runtime",
     "enclosure_fit_cad", "thermal", "custom_board", "battery_pack_from_cells", "rf_antenna_placement"]},
    {"id": "underwater-drone", "objective": "A tethered underwater camera drone for 10 m depth (ponds, harbours, hulls)",
     "market_query": "underwater ROV drone camera", "checks": ["prior_art", "junk_donors", "parts_cost", "energy_runtime",
     "buoyancy_trim", "underwater_thrust", "pressure_housing", "tether_comms", "enclosure_fit_cad"]},
    {"id": "pen-plotter", "objective": "A pen plotter or drawing machine from printer and scanner parts",
     "market_query": "pen plotter", "checks": ["prior_art", "junk_donors", "parts_cost", "linear_axis_sizing",
     "printed_part_strength"]},
    {"id": "plant-waterer", "objective": "An automatic plant watering controller with soil sensing",
     "market_query": "automatic plant watering system", "checks": ["prior_art", "junk_donors", "parts_cost", "pump_flow",
     "energy_runtime", "enclosure_fit_cad"]},
    {"id": "cargo-cart", "objective": "A workshop cargo cart carrying 30 kg, from a broken hoverboard",
     "market_query": "electric cargo cart", "checks": ["prior_art", "junk_donors", "parts_cost", "salvaged_motor_sizing",
     "energy_runtime", "structural_frame"]},
    {"id": "small-drone", "objective": "A small camera drone from obtainable parts",
     "market_query": "camera drone", "checks": ["prior_art", "junk_donors", "parts_cost", "multirotor_propulsion",
     "energy_runtime", "structural_frame"]},
    {"id": "power-bank", "objective": "A power bank or tool battery from salvaged laptop cells",
     "market_query": "18650 power bank", "checks": ["prior_art", "junk_donors", "parts_cost", "battery_pack_from_cells",
     "enclosure_fit_cad", "thermal"]},
    {"id": "controller-board", "objective": "A custom controller board for two pumps, two fans and four temperature sensors",
     "market_query": "hydronic heating controller board", "checks": ["prior_art", "parts_cost", "board_parts_price",
     "custom_board", "schematic_review"]},
]


def coverage() -> dict[str, Any]:
    rows, missing = [], Counter()
    for b in BRIEFS:
        have = [c for c in b["checks"] if CHECKS.get(c)]
        lack = [c for c in b["checks"] if not CHECKS.get(c)]
        missing.update(lack)
        rows.append({"brief": b["id"], "checks": len(b["checks"]), "have_tool": len(have), "missing": lack,
                     "share": round(len(have) / len(b["checks"]), 2)})
    return {"briefs": rows, "missing_features_by_need": missing.most_common(),
            "overall_share": round(sum(r["have_tool"] for r in rows) / sum(r["checks"] for r in rows), 2)}


def score(project_id: str) -> dict[str, Any]:
    """How far the engine carried one brief, read from the project's record."""
    from .objective_project import ObjectiveProject
    p = ObjectiveProject.load(project_id)
    steps, st = p.steps(), p.status()
    tools = [s for s in steps if s["kind"] == "tool"]
    used = {s["title"] for s in tools}
    gaps = [s for s in steps if s["kind"] == "note" and str(s["title"]).lower().startswith("gap")]
    bom = [s for s in tools if s["title"] == "hs_bom_check"]
    parts = {
        "prior_art": "hs_prior_art_search" in used,
        "junk_plan": "hs_junk_lookup" in used,
        "decisions_with_reasons": len(st["decisions"]),
        "checks_passed": len(st["software_checked"]),
        "open": len(st["open"]),
        "bom_cited_and_checked": bool(bom) and bool(bom[-1].get("ok")),
        "physical_required_listed": len(st["physical_required"]),
        "deliverables": len(st["deliverables"]),
        "gaps_recorded": [g["title"] for g in gaps],
    }
    points = (parts["prior_art"] + parts["junk_plan"] + min(parts["decisions_with_reasons"], 3) / 3
              + min(parts["checks_passed"], 4) / 4 + parts["bom_cited_and_checked"] + min(parts["deliverables"], 2) / 2)
    return {"project_id": project_id, "objective": st["objective"], "score_of_6": round(points, 2), **parts}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["coverage"]:
        print(json.dumps(coverage(), indent=1))
    elif argv[:1] == ["score"] and len(argv) > 1:
        print(json.dumps(score(argv[1]), indent=1))
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
