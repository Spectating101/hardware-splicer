"""Mechanics → Mecha Splicer/Hardware Splicer operator bridge.

A fast advisory is always available. Expensive 3D curved contact FEM runs only
on explicitly requested, bounded, local bracket projects. Numerical evidence
never promotes production authority and is not a material-strength rating.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

STRUCTURAL_BRIDGE_SCHEMA = "hardware_splicer.mechanical_workflow_bridge.v1"

def _fingerprint(value: Mapping[str, Any]) -> str:
    data=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    return "sha256:"+hashlib.sha256(data.encode("utf-8")).hexdigest()

def structural_capability_for_design(project: Mapping[str, Any]) -> dict[str, Any]:
    """Pure, dependency-free structural capability and routing result."""
    if not isinstance(project, Mapping):
        raise ValueError("Mecha design must be an object")
    bracket = project.get("bracket")
    kinds = [
        kind for kind in (
            "bracket","enclosure","servo_mount","linear_axis","leadscrew_axis",
            "rotary_joint","belt_reduction","gripper","pan_tilt","assembly"
        ) if project.get(kind) is not None
    ]
    if not kinds:
        return {
            "schema_version":STRUCTURAL_BRIDGE_SCHEMA,
            "status":"not_applicable",
            "supported_for_contact":False,
            "candidate_kinds":[],
            "claim":"No mechanical component in this project.",
            "fabrication_authorized":False,
            "release_authorized":False,
        }
    if isinstance(bracket, Mapping):
        from .mechanical_bracket_screening import _check_bracket_spec
        try:
            values=_check_bracket_spec(bracket)
        except (ValueError,TypeError) as exc:
            return {
                "schema_version":STRUCTURAL_BRIDGE_SCHEMA,
                "status":"unsupported_bracket_geometry",
                "supported_for_contact":False,
                "candidate_kinds":kinds,
                "blockers":["unsupported_or_invalid_two_hole_plate_geometry"],
                "notes":str(exc)[:200],
                "next_action":"Fix plate/through-hole dimensions before FEM, or request a different structural model.",
                "fabrication_authorized":False,
                "release_authorized":False,
            }
        return {
            "schema_version":STRUCTURAL_BRIDGE_SCHEMA,
            "status":"available_not_run",
            "supported_for_contact":True,
            "candidate_kinds":kinds,
            "mechanical_scope":"two-cylindrical-through-hole_plate_rigid_pin",
            "bracket_spec_sha256":_fingerprint(bracket),
            "dimensions_mm":values,
            "blockers":[
                "contact_fem_not_executed_for_this_design",
                "physical_material_and_fixture_validation_required",
            ],
            "next_action":"Request structural_screening='run' with an output folder to produce a local evidence review.",
            "structural_safety_verified":False,
            "fabrication_authorized":False,
            "release_authorized":False,
        }
    practical_actions=[]
    if 'enclosure' in kinds:
        practical_actions.extend(['Confirm donor/component envelope measurements, including PCB, ports and keep-outs.',
                                  'Produce and inspect complete CAD assembly for collisions and assembly access.',
                                  'Confirm printing orientation, wall thickness, clearances and fastening access.'])
    if any(kind in kinds for kind in ('servo_mount','rotary_joint','pan_tilt','linear_axis','leadscrew_axis','belt_reduction','gripper')):
        practical_actions.extend(['Verify actuator travel, load envelope and hard-stop clearance.',
                                  'Check fastener retention, interference and accessible assembly order.'])
    if 'assembly' in kinds:
        practical_actions.append('Run a multi-part fit/collision and assembly-sequence check.')
    if not practical_actions:
        practical_actions.append('Measure physical interfaces and generate CAD/DFM evidence before selecting a load model.')
    return {
        "schema_version":STRUCTURAL_BRIDGE_SCHEMA,
        "status":"unsupported_mechanical_topology",
        "supported_for_contact":False,
        "candidate_kinds":kinds,
        "blockers":["no_validated_contact_case_for_these_mechanical_parts"],
        "practical_next_checks":practical_actions,
        "mechanical_build_ready":False,
        "next_action":"Use CAD/DFM prototype tools; implement a matched load case before attempting structural FEM.",
        "structural_safety_verified":False,
        "fabrication_authorized":False,
        "release_authorized":False,
    }


def screen_mecha_project(
    project: Mapping[str, Any], *,
    out_dir: str | Path,
    mode: str = "advisory",
    mesh_sizes_mm: tuple[float, ...] = (8,6,5),
    pin_drive_mm: float = .02,
    clearance_mm: float = .005,
) -> dict[str, Any]:
    """Produce advisor or run finite-element investigation for valid plate.

    A solver failure produces an explicit blocked *result*, never a pass.
    No arbitrary HTTP file access; this function is for local, trusted tools.
    """
    if mode not in {"off","advisory","run"}:
        raise ValueError("structural_screening mode must be off/advisory/run")
    advisory = structural_capability_for_design(project)
    if mode == "off":
        return {
            "schema_version":STRUCTURAL_BRIDGE_SCHEMA,
            "status":"disabled_by_request",
            "supported_for_contact":advisory["supported_for_contact"],
            "fabrication_authorized":False,
            "release_authorized":False,
        }
    if mode == "advisory" or advisory["status"]!="available_not_run":
        return advisory
    if out_dir is None:
        raise ValueError("explicit run requires a local output directory")
    root=Path(out_dir).expanduser().resolve()
    target=root/"STRUCTURAL_SCREENING"
    # Never modify a previously generated evidence bundle.
    if target.exists():
        raise ValueError("structural evidence folder already exists; choose a new output directory")
    bracket = project["bracket"]
    spec = {"bracket":dict(bracket)}
    root.mkdir(parents=True,exist_ok=True)
    source = root/"STRUCTURAL_SPEC.json"
    if source.exists():
        raise ValueError("structural source spec file already exists; choose an empty output directory")
    source.write_text(json.dumps(spec,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    try:
        from .mechanical_contact_workbench import run_contact_workbench
        result=run_contact_workbench(
            spec_file=source,
            outdir=target,
            mesh_sizes_mm=mesh_sizes_mm,
            pin_drive_mm=pin_drive_mm,
            clearance_mm=clearance_mm,
        )
    except (ImportError,RuntimeError,ValueError,ArithmeticError,OSError) as exc:
        return {
            **advisory,
            "status":"solver_blocked",
            "blockers":["structural_contact_solver_failed_or_unavailable"],
            "failure_class":type(exc).__name__,
            "failure_detail":str(exc)[:350],
            "next_action":"Inspect local FEM dependencies/geometry and rerun; no numerical evidence is available.",
            "fabrication_authorized":False,
            "release_authorized":False,
        }
    numeric = result["contact_audit"]
    review = result["operator_review"]
    return {
        "schema_version":STRUCTURAL_BRIDGE_SCHEMA,
        "status":"screened_inconclusive" if review["primary_blockers"] else "numerical_screening_only",
        "supported_for_contact":True,
        "candidate_kinds":advisory["candidate_kinds"],
        "mechanical_scope":advisory["mechanical_scope"],
        "bracket_spec_sha256":advisory["bracket_spec_sha256"],
        "source_cad_sha256":numeric["source_step_sha256"],
        "mesh_levels_mm":[row["mesh_target_mm"] for row in numeric["mesh_levels"]],
        "computed_force_n":[row["transmitted_force_scale_n"] for row in numeric["mesh_levels"]],
        "numerical_status":numeric["status"],
        "blockers":review["primary_blockers"],
        "artifacts":{
            "source_spec":str(source),
            "generated_step":str(target/"bracket.step"),
            "evidence_json":str(target/"evidence.json"),
            "review_html":str(target/"review.html"),
            "predicted_load_curve_csv":str(target/"predicted_load_curve.csv"),
            "remaining_actions":str(target/"remaining_actions.txt"),
        },
        "numerical_complementarity_checked":True,
        "physical_material_and_fixture_validation_required":True,
        "structural_safety_verified":False,
        "fabrication_authorized":False,
        "release_authorized":False,
        "claim_boundary":"Numerically investigated, not verified structural strength or physical safety.",
    }
