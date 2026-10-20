"""Independent parameter and mesh audits of two-bore nodal contact.

The validation stops at *numerical screening*. Hard-contact validity at
finite-element nodes is distinct from continuum contact stress convergence
and from strength of a printed/bolted assembly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


def audit_two_pin_contact(
    step_path: str | Path,
    *,
    mesh_sizes_mm: Sequence[float] = (8., 6., 5.),
    centers_xy_mm: Sequence[Sequence[float]] = ((10.,10.), (50.,10.)),
    hole_d_mm: float = 3.2,
    thickness_mm: float = 4.,
    right_pin_drive_mm: float = .02,
    radial_clearance_mm: float = .005,
    force_tolerance: float = .04,
    local_peak_tolerance: float = .10,
    local_rms_tolerance: float = .06,
    numerical_gauge_values_n_m: Sequence[float] = (.001,.01,.1),
    activation_values_n_m: Sequence[float] = (1e6,1e7,1e8),
) -> dict[str, Any]:
    from .mechanical_two_pin_contact import solve_two_pin_contact

    sizes = [float(x) for x in mesh_sizes_mm]
    if (
        len(sizes) not in (3,4)
        or not all(math.isfinite(x) and 1 <= x <= 15 for x in sizes)
        or not all(a > b for a,b in zip(sizes,sizes[1:]))
    ):
        raise ValueError("provide 3–4 strictly decreasing finite mesh sizes")
    for name,tol in [
        ("force_tolerance", force_tolerance),
        ("local_peak_tolerance", local_peak_tolerance),
        ("local_rms_tolerance", local_rms_tolerance),
    ]:
        if not math.isfinite(tol) or not 0 < tol <= .25:
            raise ValueError(f"{name} must be finite in (0,0.25]")
    for name,values in [
        ("numerical_gauge_values_n_m",numerical_gauge_values_n_m),
        ("activation_values_n_m",activation_values_n_m),
    ]:
        if len(values)!=3 or not all(
            math.isfinite(float(x)) and x > 0 for x in values
        ) or not all(a < b for a,b in zip(values,values[1:])):
            raise ValueError(f"{name} requires 3 increasing positive values")

    base_args = dict(
        centers_xy_mm=centers_xy_mm,
        hole_d_mm=hole_d_mm,
        thickness_mm=thickness_mm,
        right_pin_drive_mm=right_pin_drive_mm,
        radial_clearance_mm=radial_clearance_mm,
    )
    levels=[]
    for size in sizes:
        levels.append(solve_two_pin_contact(
            step_path, mesh_target_mm=size,
            numerical_gauge_n_per_m=numerical_gauge_values_n_m[1],
            active_selection_n_per_m=activation_values_n_m[1],
            **base_args,
        ))
    if len({x["source_step_sha256"] for x in levels}) != 1:
        raise ValueError("STEP changed during two-bore study")
    comparisons=[]
    blockers=[]
    for coarse,fine in zip(levels,levels[1:]):
        force_error=abs(
            fine["transmitted_force_scale_n"]-coarse["transmitted_force_scale_n"]
        )/max(fine["transmitted_force_scale_n"],coarse["transmitted_force_scale_n"],1e-8)
        if force_error > force_tolerance:
            blockers.append("pin_force_mesh_sensitive")
        if fine["quadratic_dof_count"] / coarse["quadratic_dof_count"] < 1.08:
            blockers.append("insufficient_quadratic_refinement")
        holecomparisons=[]
        for left,right in zip(coarse["per_hole_stress"],fine["per_hole_stress"]):
            peak=abs(
                right["peak_sampled_von_mises_pa"]-left["peak_sampled_von_mises_pa"]
            )/max(right["peak_sampled_von_mises_pa"],left["peak_sampled_von_mises_pa"],1e-6)
            rms=abs(
                right["weighted_rms_von_mises_pa"]-left["weighted_rms_von_mises_pa"]
            )/max(right["weighted_rms_von_mises_pa"],left["weighted_rms_von_mises_pa"],1e-6)
            idx=left["hole_index"]
            if peak > local_peak_tolerance:
                blockers.append(f"hole_{idx}_peak_stress_not_converged")
            if rms > local_rms_tolerance:
                blockers.append(f"hole_{idx}_rms_stress_not_converged")
            holecomparisons.append({
                "hole_index":idx,
                "peak_stress_relative_change":peak,
                "rms_stress_relative_change":rms,
            })
        comparisons.append({
            "coarse_mm":coarse["mesh_target_mm"],
            "fine_mm":fine["mesh_target_mm"],
            "force_relative_change":force_error,
            "per_hole":holecomparisons,
        })
    # Stage two: numerical gauge is NOT contact penalty and should not
    # materially contribute force to this nominally unrestrained joint.
    gauge_results=[]
    for g in numerical_gauge_values_n_m:
        r=solve_two_pin_contact(
            step_path,mesh_target_mm=sizes[0],
            numerical_gauge_n_per_m=float(g),
            active_selection_n_per_m=activation_values_n_m[1],
            **base_args,
        )
        gauge_results.append({
            "gauge_n_per_m":g,
            "transmitted_force_n":r["transmitted_force_scale_n"],
            "relative_gauge_reaction":r["relative_gauge_reaction"],
        })
    activation_results=[]
    for value in activation_values_n_m:
        r=solve_two_pin_contact(
            step_path,mesh_target_mm=sizes[0],
            numerical_gauge_n_per_m=numerical_gauge_values_n_m[1],
            active_selection_n_per_m=float(value),
            **base_args,
        )
        activation_results.append({
            "active_set_selection_n_per_m":value,
            "transmitted_force_n":r["transmitted_force_scale_n"],
            "contact_iterations":r["contact_iterations"],
        })
    if max(x["relative_gauge_reaction"] for x in gauge_results) > .001:
        blockers.append("numerical_gauge_reaction_not_negligible")
    if max(x["transmitted_force_n"] for x in gauge_results) / max(
        min(x["transmitted_force_n"] for x in gauge_results),1e-8
    ) - 1 > .005:
        blockers.append("contact_force_sensitive_to_numerical_gauge")
    if max(x["transmitted_force_n"] for x in activation_results) / max(
        min(x["transmitted_force_n"] for x in activation_results),1e-8
    ) - 1 > .005:
        blockers.append("contact_solution_sensitive_to_active_set_selector")

    blockers=sorted(set(blockers))
    return {
        "schema_version":"hardware_splicer.two_pin_contact_audit.v1",
        "status":(
            "numerically_bounded_two_pin_screening_only" if not blockers
            else "inconclusive_two_pin_contact_stress"
        ),
        "source_step_sha256":levels[0]["source_step_sha256"],
        "mesh_levels":levels,
        "adjacent_mesh_comparisons":comparisons,
        "numerical_gauge_sensitivity":gauge_results,
        "active_set_selection_sensitivity":activation_results,
        "mesh_force_tolerance":force_tolerance,
        "local_peak_stress_tolerance":local_peak_tolerance,
        "local_rms_stress_tolerance":local_rms_tolerance,
        "blockers":blockers,
        "selected_nodal_nonpenetration_verified":True,
        "continuous_contact_surface_verified":False,
        "nodal_contact_penalty_parameter_needed":False,
        "true_assembly_strength_verified":False,
        "physical_validation_required":True,
        "structural_safety_verified":False,
        "fabrication_authorized":False,
        "release_authorized":False,
        "claim_boundary":(
            "Both pin surfaces use frictionless nodal KKT contact constraints "
            "with a weak measured numerical rigid-mode gauge. The continuum "
            "pressure field, real bolts and printed material remain unvalidated."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    from .mechanical_bracket_screening import generate_bracket_reference_step

    p=argparse.ArgumentParser(
        description="Audit two-bore nodal complementarity contact on Mecha STEP"
    )
    p.add_argument("--spec-json",type=Path,required=True)
    p.add_argument("--step-out",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--mesh-study-mm",type=float,nargs="+",default=[8,6,5])
    p.add_argument("--drive-mm",type=float,default=.02)
    p.add_argument("--clearance-mm",type=float,default=.005)
    a=p.parse_args(argv)
    source=json.loads(a.spec_json.read_text(encoding="utf-8"))
    spec=source.get("bracket",source)
    geometry=generate_bracket_reference_step(spec,a.step_out)
    dimensions=geometry["geometry_dimensions_mm"]
    report=audit_two_pin_contact(
        a.step_out,mesh_sizes_mm=a.mesh_study_mm,
        centers_xy_mm=geometry["cylindrical_through_hole_centers_xy_mm"],
        hole_d_mm=dimensions["hole_d_mm"],
        thickness_mm=dimensions["t_mm"],
        right_pin_drive_mm=a.drive_mm,
        radial_clearance_mm=a.clearance_mm,
    )
    report["generated_step_provenance"]=geometry
    report["source_spec_sha256"]="sha256:"+hashlib.sha256(
        json.dumps(spec,sort_keys=True,separators=(",",":")).encode()
    ).hexdigest()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(f"Two-pin nodal contact: {report['status']}, blockers={report['blockers']}")
    return 2 if report["blockers"] else 0

if __name__=="__main__":
    raise SystemExit(main())
