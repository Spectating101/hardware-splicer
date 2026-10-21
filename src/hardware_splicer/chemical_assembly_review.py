"""Joint material/electrical/mechanical enclosure screening with no release authority.

Inputs are explicitly declared engineering models. Underlying analyzers are
recomputed and their asserted status/check rows are not trusted from callers.
This is a feasibility screen, not CAD/BREP, thermal, EMC or certification proof.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .chemical_engineering import NON_AUTHORITY
from .electrical_design import ElectricalDesign, electrical_rule_check
from .machine_project import MachineProject
from .material_evidence import compare_material_candidates
from .mechanical_fit import (
    ClearanceBox, ClearanceRequirement, FastenerStack, build_mechanical_fit_report,
)
from .step_geometry import MechanicalGeometryReport, build_mechanical_geometry_report

SCHEMA_VERSION = "hardware_splicer.chemical_assembly_review.v1"


def _finding(code: str, *, layer: str, detail: str, blocking: bool = True) -> dict[str, Any]:
    return {"code": code, "layer": layer, "detail": detail, "blocking": blocking}


def review_enclosure_assembly(
    *,
    project: MachineProject,
    candidate_ids: list[str],
    selected_enclosure_id: str,
    electrical_component_id: str,
    electrical_design: ElectricalDesign,
    mechanical_geometry: MechanicalGeometryReport,
    clearance_boxes: Sequence[ClearanceBox | Mapping[str, Any]],
    clearance_requirements: Sequence[ClearanceRequirement | Mapping[str, Any]],
    fastener_stacks: Sequence[FastenerStack | Mapping[str, Any]] = (),
) -> dict[str, Any]:
    if not 2 <= len(candidate_ids) <= 20 or len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("Supply two to twenty distinct candidate IDs")
    if selected_enclosure_id not in candidate_ids:
        raise ValueError("Selected enclosure must be one of candidate IDs")
    components = {row.component_id: row for row in project.components}
    if selected_enclosure_id not in components or electrical_component_id not in components:
        raise ValueError("Selected enclosure and electrical component must exist in MachineProject")
    if components[selected_enclosure_id].domain.value != "mechanical":
        raise ValueError("Selected enclosure must be a mechanical MachineProject component")
    if components[electrical_component_id].domain.value != "electrical":
        raise ValueError("Board component must have electrical MachineProject domain")
    if electrical_component_id == selected_enclosure_id:
        raise ValueError("Enclosure and electrical component identities must differ")
    if mechanical_geometry.project_id != project.project_id or electrical_design.project_id != project.project_id:
        raise ValueError("All engineering models must refer to the canonical MachineProject identity")
    if not 1 <= len(clearance_boxes) <= 100 or not 1 <= len(clearance_requirements) <= 100:
        raise ValueError("At least one bounded clearance box/requirement required")
    if len(fastener_stacks) > 100:
        raise ValueError("Fastener stack request too large")

    # Untrusted, human-declared float geometry is not permitted to smuggle NaN
    # into comparisons where NaN can otherwise cause false pass results.
    for box in clearance_boxes:
        row = box if isinstance(box, ClearanceBox) else ClearanceBox.model_validate(box)
        if not all(math.isfinite(v) for v in (*row.minimum_mm, *row.maximum_mm)):
            raise ValueError("Nonfinite mechanical clearance envelope")
    for item in mechanical_geometry.models:
        envelope = item.bounding_box
        if envelope is not None and not all(
            math.isfinite(v) for v in (*envelope.minimum, *envelope.maximum, *envelope.size)
        ):
            raise ValueError("Nonfinite STEP point envelope")
    for constraint in clearance_requirements:
        row = (constraint if isinstance(constraint, ClearanceRequirement)
               else ClearanceRequirement.model_validate(constraint))
        if not math.isfinite(row.minimum_clearance_mm):
            raise ValueError("Nonfinite mechanical clearance criterion")
    for pin in electrical_design.pins:
        values = (pin.voltage_min_v, pin.voltage_max_v, pin.max_current_a)
        if any(value is not None and not math.isfinite(value) for value in values):
            raise ValueError("Nonfinite electrical pin specification")
    for net in electrical_design.nets:
        values = (net.voltage_min_v, net.voltage_max_v, net.peak_current_a)
        if any(value is not None and not math.isfinite(value) for value in values):
            raise ValueError("Nonfinite electrical net specification")
    material_report = compare_material_candidates(project, candidate_ids)
    geometry = build_mechanical_geometry_report(
        project_id=project.project_id,
        models=mechanical_geometry.models,
        mounts=mechanical_geometry.mounts,
    )
    fit = build_mechanical_fit_report(
        geometry,
        clearance_boxes=clearance_boxes,
        clearance_requirements=clearance_requirements,
        fastener_stacks=fastener_stacks,
    )
    electrical_issues = electrical_rule_check(electrical_design)
    findings: list[dict[str, Any]] = []
    selected = next(row for row in material_report["summary"]
                    if row["component_id"] == selected_enclosure_id)
    if not material_report["comparable_numeric_criteria"]:
        findings.append(_finding(
            "incomparable_candidate_criteria", layer="material",
            detail="Materials are not constrained by equivalent tests and limits",
        ))
    if selected["blockers"]:
        findings.append(_finding(
            "material_candidate_blocked", layer="material",
            detail=";".join(selected["blockers"]),
        ))
    if geometry.status != "candidate" or not geometry.checks:
        findings.append(_finding(
            "mechanical_geometry_unresolved", layer="mechanical",
            detail=f"Computed geometry status is {geometry.status}; requires valid STEP identity and declared interfaces",
        ))

    model_part_ids = {row.part_id for row in geometry.mounts}
    if selected_enclosure_id not in model_part_ids or electrical_component_id not in model_part_ids:
        findings.append(_finding(
            "mechanical_part_identity_missing", layer="mechanical",
            detail="STEP mount declarations must reference selected enclosure AND canonical board part IDs",
        ))
    enclosure_mounts = [
        row for row in geometry.mounts if row.part_id == selected_enclosure_id
    ]
    board_mount_ids = {
        row.interface_id for row in geometry.mounts
        if row.part_id == electrical_component_id
    }
    if not any(row.mates_with in board_mount_ids for row in enclosure_mounts):
        findings.append(_finding(
            "board_enclosure_mount_pair_missing", layer="mechanical",
            detail="No declared enclosure mount mates with a mount owned by the canonical board",
        ))
    reqs = fit.clearance_requirements
    attached_requirements = [
        row for row in reqs
        if {row.first_object_id, row.second_object_id}
        == {selected_enclosure_id, electrical_component_id}
    ]
    if not attached_requirements:
        findings.append(_finding(
            "board_enclosure_clearance_coverage_missing", layer="mechanical",
            detail="No explicit assembly clearance requirement connects selected enclosure and board",
        ))
    if fit.status != "candidate" or not fit.checks:
        findings.append(_finding(
            "mechanical_fit_blocked", layer="mechanical",
            detail="Computed fit checks failed or remain unresolved",
        ))

    if not any(row.component_id == electrical_component_id
               for row in electrical_design.components):
        findings.append(_finding(
            "board_electrical_identity_missing", layer="electrical",
            detail="Canonical board component not found in provided electrical design",
        ))
    untracked = sorted({
        row.component_id for row in electrical_design.components
        if row.component_id not in components
        or components[row.component_id].domain.value != "electrical"
    })
    if untracked:
        findings.append(_finding(
            "electrical_component_identity_unmapped", layer="electrical",
            detail="Unmapped MachineProject electrical component IDs: " + ", ".join(untracked),
        ))
    if (not electrical_design.pins or not electrical_design.nets
            or not any(len(row.pin_ids) >= 2 for row in electrical_design.nets)):
        findings.append(_finding(
            "electrical_network_coverage_missing", layer="electrical",
            detail="Electrical design lacks populated pins and a multi-pin net",
        ))
    electrical_errors = [issue for issue in electrical_issues if issue.severity == "error"]
    if electrical_errors:
        findings.append(_finding(
            "electrical_rule_errors", layer="electrical",
            detail=";".join(sorted({issue.code for issue in electrical_errors})),
        ))

    warnings = [
        _finding("electrical_rule_warning", layer="electrical", detail=issue.message,
                 blocking=False)
        for issue in electrical_issues if issue.severity != "error"
    ]
    # A pass only means this *declared* set of checks was completed without
    # contradiction. No real-world material, geometry, thermal or electrical safety
    # proof is granted by that result.
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project.project_id,
        "selected_enclosure_id": selected_enclosure_id,
        "electrical_component_id": electrical_component_id,
        "material": {
            "selected_screen": selected,
            "candidate_screens": material_report["summary"],
            "comparability_blockers": material_report["comparison_blockers"],
        },
        "mechanical": {
            "geometry_status": geometry.status,
            "geometry_computed_check_count": len(geometry.checks),
            "geometry_failed_check_ids": [
                row.check_id for row in geometry.blocking_checks
            ],
            "fit_status": fit.status,
            "fit_computed_check_count": len(fit.checks),
            "fit_failed_check_ids": [row.check_id for row in fit.blocking_checks],
            "clearance_covered": bool(attached_requirements),
            "point_envelope_only": True,
            "full_brep_collision": False,
        },
        "electrical": {
            "erc_error_count": len(electrical_errors),
            "erc_warning_count": len(electrical_issues) - len(electrical_errors),
            "erc_error_codes": sorted({issue.code for issue in electrical_errors}),
            "real_power_dissipation_verified": False,
            "thermal_field_simulation_verified": False,
        },
        "blocking_findings": findings,
        "warnings": warnings,
        "result": (
            "bounded_assembly_screen_consistent_but_unverified"
            if not findings else "assembly_screen_blocked"
        ),
        "required_next_validation": [
            {"id": "verify_material_sources", "discipline": "chemical",
             "action": "Authenticate supplier/specimen identity, source versions and relevant standard conditions"},
            {"id": "measure_operating_thermal_field", "discipline": "electrical_mechanical",
             "action": "Measure PCB, enclosure and ambient temperatures under representative operating load"},
            {"id": "validate_full_cad_and_fit", "discipline": "mechanical",
             "action": "Check full solid geometry, mounting tolerances and physical enclosure fit"},
            {"id": "validate_electrical_insulation", "discipline": "electrical",
             "action": "Independently verify insulation, creepage, clearance and application-specific electrical standards"},
            {"id": "assess_manufacturing_process", "discipline": "materials_manufacturing",
             "action": "Qualify actual printed part, process parameters, service exposure and mechanical behavior"},
        ],
        "thermal_safety_evaluated": False,
        "full_brep_collision_evaluated": False,
        "electrical_insulation_evaluated": False,
        "physical_verification_required": True,
        "build_readiness_authorized": False,
        "project_modified": False,
        "limitations": [
            "Mechanical STEP inspection uses Cartesian point envelopes, not solid/BREP collision geometry.",
            "Declared clearance boxes and tests are not a validated enclosure or PCB fit.",
            "Electrical ERC is a logical design check, not measured insulation, thermal or EMC proof.",
            "Manufacturer material properties at ISO75 test loads are not continuous service-temperature ratings.",
            "Independent evidence, fabrication, hardware testing and safety approvals remain necessary.",
        ],
        **NON_AUTHORITY,
    }
