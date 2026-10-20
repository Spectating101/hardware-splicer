"""Transfer the bounded curved FEM workflow to Mecha-Splicer's plate-bracket spec.

Geometry mirrors mecha_splicer's 'bracket.scad' rectangular plate with
two cylindrical through-holes. This is an independent OCC reconstruction,
not a formal OpenSCAD-to-STEP CAD equivalence proof.

The assumed x_min rigid clamp and x_max end traction do *not* represent
bolt contacts: support assumptions are deliberately reported as unverified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


BRACKET_KEYS = (
    "w_mm", "d_mm", "t_mm", "hole_d_mm", "hole_spacing_mm",
)


def _check_bracket_spec(spec: Mapping[str, Any]) -> dict[str, float]:
    if not isinstance(spec, Mapping):
        raise ValueError("bracket spec must be a mapping")
    params: dict[str, float] = {}
    for key in BRACKET_KEYS:
        if key not in spec or isinstance(spec[key], bool):
            raise ValueError(f"missing or invalid bracket field: {key}")
        try:
            value = float(spec[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid numeric bracket field: {key}") from exc
        if not math.isfinite(value) or not .5 <= value <= 200:
            raise ValueError(f"{key} must be finite and in [0.5,200] mm")
        params[key] = value

    w, d, t, hole, spacing = (
        params[k] for k in BRACKET_KEYS
    )
    if (
        hole >= d * .75
        or hole >= t * 4
        or spacing + hole >= w - 2
        or spacing <= hole + 2
    ):
        raise ValueError(
            "bracket hole spacing/diameter leaves insufficient clearance "
            "for this bounded reference fixture"
        )
    return params


def generate_bracket_reference_step(
    spec: Mapping[str, Any], step_path: str | Path,
) -> dict[str, Any]:
    """Create STEP geometry matching Mecha's *parametric* double-hole plate.

    Never implicitly edits existing CAD. Only BREP plate primitives generated;
    no actual printed-part orientation, tolerance or feature equivalence test.
    """
    try:
        import gmsh
    except ImportError as exc:
        raise RuntimeError("optional gmsh is required for bracket BREP") from exc

    params = _check_bracket_spec(spec)
    path = Path(step_path)
    if path.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("bracket export path must end in STEP/STP")
    if path.exists():
        raise ValueError("bracket export refuses to overwrite existing STEP")
    path.parent.mkdir(parents=True, exist_ok=True)

    w = params["w_mm"]
    depth = params["d_mm"]
    t = params["t_mm"]
    hole_r = params["hole_d_mm"] / 2
    spacing = params["hole_spacing_mm"]
    hole_centers = [
        [(w - spacing) / 2, depth / 2],
        [(w + spacing) / 2, depth / 2],
    ]
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("hs-mecha-bracket-structural-reference")
        block = gmsh.model.occ.addBox(0, 0, 0, w, depth, t)
        drills = [
            (3, gmsh.model.occ.addCylinder(
                center[0], center[1], -1, 0, 0, t + 2, hole_r
            ))
            for center in hole_centers
        ]
        result, _ = gmsh.model.occ.cut(
            [(3, block)], drills,
            removeObject=True, removeTool=True,
        )
        gmsh.model.occ.synchronize()
        if (
            len(result) != 1
            or result[0][0] != 3
            or len(gmsh.model.getEntities(3)) != 1
        ):
            raise ValueError("expected exactly one bracket solid")
        gmsh.write(str(path))
        if not path.exists() or path.stat().st_size == 0:
            raise ValueError("Gmsh failed to create bracket STEP")
    finally:
        gmsh.finalize()
    return {
        "generator": "OpenCASCADE-derived-from-Mecha-bracket-spec",
        "step_path": str(path),
        "step_sha256": "sha256:" + hashlib.sha256(
            path.read_bytes()
        ).hexdigest(),
        "template_or_source_name": str(spec.get("name", "bracket")),
        "geometry_dimensions_mm": params,
        "cylindrical_through_hole_centers_xy_mm": hole_centers,
        "brep_to_openscad_geometric_equivalence_verified": False,
    }


def run_bracket_transfer_screening(
    *,
    spec: Mapping[str, Any],
    step_path: str | Path,
    mesh_targets_mm: Sequence[float] = (8, 6, 5),
    applied_edge_force_n: float = 30,
    assumed_youngs_pa: float = 2e9,
    assumed_poisson: float = .25,
    hotspot_location_tolerance_mm: float = 5.0,
) -> dict[str, Any]:
    """Screen *assumed* clamp/traction behavior; NO bolt contact model.

    Validates the bracket's actual parametric geometry shape, not the
    manufacturing strength of FDM-printed or fastened components.
    """
    if (
        not math.isfinite(applied_edge_force_n)
        or not 0 < applied_edge_force_n <= 1000
    ):
        raise ValueError("assumed applied force must be in (0,1000] N")
    params = _check_bracket_spec(spec)
    canonical = json.dumps(
        {
            "type": "mecha_splicer_bracket",
            "name": str(spec.get("name", "bracket")),
            "dimensions_mm": params,
        },
        sort_keys=True, separators=(",", ":"),
    )
    spec_hash = "sha256:" + hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    # Validate preconditions before generating any output geometry.
    targets = tuple(float(t) for t in mesh_targets_mm)
    if (
        len(targets) not in (3, 4)
        or not all(math.isfinite(t) and 1 <= t <= 30 for t in targets)
        or not all(a > b for a, b in zip(targets, targets[1:]))
    ):
        raise ValueError("bracket screen requires 3–4 decreasing mesh targets [1,30] mm")

    geometry = generate_bracket_reference_step(spec, step_path)
    from .mechanical_quadratic_fem import run_curved_stress_sensitivity

    study = run_curved_stress_sensitivity(
        step_path, mesh_targets_mm=targets,
        fixed_plane="x_min", loaded_plane="x_max",
        total_force_n=[applied_edge_force_n, 0, 0],
        youngs_modulus_pa=assumed_youngs_pa,
        poisson_ratio=assumed_poisson,
        hotspot_location_tolerance_mm=hotspot_location_tolerance_mm,
    )
    return {
        "schema_version": "hardware_splicer.mecha_bracket_transfer.v1",
        "status": (
            "inconclusive_bracket_transfer"
            if study["blockers"]
            else "numerically_stable_idealized_bracket_screening"
        ),
        "mecha_spec_sha256": spec_hash,
        "geometry": geometry,
        "load_case": {
            "fixed_surface": "entire x_min planar end",
            "loaded_surface": "entire x_max planar end",
            "loaded_force_n": [applied_edge_force_n, 0, 0],
            "assumed_youngs_modulus_pa": assumed_youngs_pa,
            "assumed_poisson_ratio": assumed_poisson,
            "screw_hole_walls_are_realistically_constrained": False,
            "fastener_bearing_contact_modeled": False,
            "load_case_matches_an_actual_assembled_product": False,
            "printed_polymer_anisotropy_calibrated": False,
        },
        "curved_fem_study": study,
        "kirsch_reference_applies_directly": False,
        "real_mounting_conditions_validated": False,
        "real_material_properties_validated": False,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
        "claim_boundary": (
            "Mecha-Splicer double-hole plate under hypothetical edge clamp "
            "and axial traction. The Kirsch 2D exact solution does not "
            "validate this 3D finite double-hole geometry and fixture."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Generate bounded Mecha double-hole plate STEP and numerical report"
    )
    p.add_argument("--spec-json", required=True, type=Path)
    p.add_argument("--step-out", required=True, type=Path)
    p.add_argument("--report-out", required=True, type=Path)
    p.add_argument("--mesh-study-mm", nargs="+", type=float, default=[8, 6, 5])
    p.add_argument("--edge-force-n", type=float, default=30.0)
    args = p.parse_args(argv)
    input_spec = json.loads(args.spec_json.read_text("utf-8"))
    if isinstance(input_spec, dict) and "bracket" in input_spec:
        input_spec = input_spec["bracket"]
    report = run_bracket_transfer_screening(
        spec=input_spec,
        step_path=args.step_out,
        mesh_targets_mm=args.mesh_study_mm,
        applied_edge_force_n=args.edge_force_n,
    )
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Bracket transfer status: {report['status']}; output={args.report_out}")
    return 0 if not report["curved_fem_study"]["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
