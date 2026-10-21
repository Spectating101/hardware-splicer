"""Source-bound PCB assembly and enclosure qualification (non-authorizing).

Builds a reproducible electromechanical handoff from an actual KiCad PCB file.
Part envelope heights are estimates from the assembly planner, NOT a measured
vendor 3D model. Generated checklists are instructions, never observed tests.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .assembly_plan import build_assembly_plan
from .electromechanical_fit import screen_board_enclosure_fit

SCHEMA = "hardware_splicer.reference_assembly_qualification.v1"


def _positive(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be positive and finite")
    return float(value)


def qualify_source_board(
    source_pcb: str | Path,
    *,
    inner_dimensions_mm: Mapping[str, float],
    floor_mm: float = 2.0,
    standoff_mm: float = 6.0,
) -> dict:
    """Qualify declared geometry. Caller must label proposed vs measured cavity."""
    path = Path(source_pcb).expanduser().resolve(strict=True)
    if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("KiCad source must be a bounded regular file")
    raw = path.read_bytes()
    source_sha256 = hashlib.sha256(raw).hexdigest()
    plan = build_assembly_plan(raw.decode("utf-8"), pcb_sha256="sha256:" + source_sha256)
    if not isinstance(inner_dimensions_mm, Mapping):
        raise ValueError("enclosure interior dimensions required")
    width = _positive(inner_dimensions_mm.get("w"), "inner width")
    depth = _positive(inner_dimensions_mm.get("d"), "inner depth")
    height = _positive(inner_dimensions_mm.get("h"), "inner height")
    floor = _positive(floor_mm, "floor thickness")
    standoff = _positive(standoff_mm, "standoff clearance")
    board = plan["board"]
    bw, bd = board["size_mm"]
    thickness = _positive(board["thickness_mm"], "board thickness")
    bbox = board["outline"]["bbox"]
    cx = (bbox["x0"] + bbox["x1"]) / 2
    cy = (bbox["y0"] + bbox["y1"]) / 2
    parts = []
    height_sources = {}
    identities_without_mpn = []
    for part in plan["parts"]:
        if part["do_not_populate"]:
            continue
        if not part["identity"]["mpn"]:
            identities_without_mpn.append(part["id"])
        height_sources[part["height_basis"]] = height_sources.get(part["height_basis"], 0) + 1
        if part["kind"] == "mounting_hole":
            continue
        corners = part["corners"]
        if len(corners) < 1:
            raise ValueError("fitted part has no placement envelope")
        xs = [corner[0] for corner in corners]
        ys = [corner[1] for corner in corners]
        lx, ux = min(xs), max(xs)
        ly, uy = min(ys), max(ys)
        parts.append({
            "ref": part["id"],
            "center_xy_mm": [(lx + ux) / 2 - cx, (ly + uy) / 2 - cy],
            "size_xyz_mm": [ux - lx, uy - ly, part["height_mm"]],
            "rotation_deg": 0,
            "layer": "B.Cu" if part["side"] == "back" else "F.Cu",
        })
    geometry_input = {
        "source_mode": "existing_kicad_footprint_courtyards_with_estimated_heights",
        "board": {"dimensions_mm": {"w": bw, "d": bd, "t": thickness}},
        "components": parts,
    }
    assembly_input = {
        "enclosure": {
            "inner_dimensions_mm": {"w": width, "d": depth, "h": height},
            "floor_mm": floor,
        },
        "placements": {
            "pcb": {"origin_xyz_mm": [0, 0, floor + standoff + thickness / 2]},
        },
    }
    fit = screen_board_enclosure_fit(geometry_input, assembly_input)
    actions = [
        "Confirm all fitted component manufacturer identities, pad pinouts and actual package heights.",
        "Measure the intended enclosure internal dimensions and verify standoff/mounting-hole geometry.",
        "Inspect fasteners, cable routing, port access, connector orientation and assembly accessibility.",
        "Perform an exact 3D collision/tolerance check against source CAD or a prototype.",
        "Inspect nets and PCB connectivity, then perform de-energized continuity and isolation checks.",
        "Use appropriately current-limited bench power only after qualified engineering approval.",
        "Record firmware/protocol operation and end-to-end functional measurements before release.",
    ]
    if fit["blocker_count"]:
        actions.insert(0, "Redesign the stated enclosure or board assembly: source-derived envelopes show interferences.")
    if identities_without_mpn:
        actions.insert(0, "Resolve missing manufacturer part numbers against the actual BOM and purchased parts.")
    return {
        "schema": SCHEMA,
        "source_board_sha256": "sha256:" + source_sha256,
        "pcb_source_kind": "existing_kicad_design",
        "board_dimensions_mm": [bw, bd, thickness],
        "board_outline_kind": board["outline"]["kind"],
        "footprints_total": plan["counts"]["parts"],
        "footprints_fitted": plan["counts"]["fitted"],
        "footprints_not_fitted": len(plan["not_fitted"]),
        "assembly_step_count": plan["counts"]["steps"],
        "component_envelope_count": len(parts),
        "height_basis_counts": height_sources,
        "fitted_parts_missing_mpn_count": len(identities_without_mpn),
        "fitted_parts_missing_mpn": identities_without_mpn,
        "declared_cavity_mm": {"w": width, "d": depth, "h": height},
        "declared_standoff_mm": standoff,
        "declared_floor_mm": floor,
        "fit_status": fit["status"],
        "fit_blocker_count": fit["blocker_count"],
        "assembly": plan,
        "electromechanical_fit": fit,
        "required_actions": actions,
        "cavity_dimensions_physically_measured": False,
        "component_heights_source_authenticated": False,
        "exact_3d_collision_verified": False,
        "electrical_function_verified": False,
        "physical_build_completed": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "release_authorized": False,
    }


def write_reference_qualification(report: Mapping[str, Any], out_dir: str | Path) -> dict[str, str]:
    """Persist bounded evidence and handoff; do not overwrite existing outputs."""
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    named = {
        "SOURCE_ASSEMBLY_PLAN.json": report["assembly"],
        "SOURCE_ELECTROMECHANICAL_FIT.json": report["electromechanical_fit"],
        "REFERENCE_QUALIFICATION.json": {k: v for k, v in report.items() if k not in ("assembly", "electromechanical_fit")},
    }
    paths = {}
    for filename, data in named.items():
        target = root / filename
        with target.open("x", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        paths[filename] = str(target)
    text = [
        "# Reference PCB — controlled assembly and bench qualification",
        "",
        f"Source SHA-256: \`{report['source_board_sha256']}\`",
        f"Board: {report['board_dimensions_mm']} mm; fitted: {report['footprints_fitted']}; not fitted: {report['footprints_not_fitted']}",
        f"Declared enclosure screening: **{report['fit_status']}**; envelope blockers: {report['fit_blocker_count']}",
        "",
        "**No physical measurement, build or operation has been performed by this software.**",
        "**These checks require an authorized qualified human operator.**",
        "",
        "## Required verification steps (all open)",
    ]
    text += [f"- [ ] {step}" for step in report["required_actions"]]
    target = root / "BUILD_VALIDATION_CHECKLIST.md"
    with target.open("x", encoding="utf-8") as handle:
        handle.write("\n".join(text) + "\n")
    paths["BUILD_VALIDATION_CHECKLIST.md"] = str(target)
    return paths
