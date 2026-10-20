"""Material-constraint evidence reconciliation against canonical MachineProject.

This read-only report never upgrades MachineProject authority, invents materials
facts, or treats a caller-supplied source pointer as independently verified.
"""
from __future__ import annotations

import math
import re
import json
from typing import Any

from .chemical_engineering import NON_AUTHORITY, SCHEMA_VERSION
from .machine_project import MachineProject


_PROPERTY_UNITS = {
    "density": "kg/m3",
    "youngs_modulus": "Pa",
    "thermal_conductivity": "W/(m*K)",
    "electrical_resistivity": "ohm*m",
    "max_service_temperature": "K",
    "specific_heat_capacity": "J/(kg*K)",
    "heat_deflection_temperature": "K",
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def evaluate_material_evidence(
    project: MachineProject, component_id: str,
) -> dict[str, Any]:
    """Compare source-linked candidate values to declared numeric constraints.

    Evidence must explicitly support both the component and constraint, refer to
    the same material ID and use the exact canonical property unit. No converting,
    interpolating, extrapolating or deducing material identities is permitted.
    """
    component = next((item for item in project.components if item.component_id == component_id), None)
    if component is None:
        raise ValueError("component_id does not exist in the canonical MachineProject")

    material_id = str(component.metadata.get("material_id") or "").strip()
    relevant_constraints = [
        item for item in project.constraints
        if component_id in item.applies_to and "material_property" in item.metadata
    ]
    if len(relevant_constraints) > 100 or len(project.evidence) > 1000:
        raise ValueError("Material evidence review exceeds bounded row limits")

    checks: list[dict[str, Any]] = []
    for constraint in relevant_constraints:
        meta = constraint.metadata
        prop = str(meta.get("material_property") or "").strip()
        unit = _PROPERTY_UNITS.get(prop)
        low = _number(meta.get("min_value"))
        high = _number(meta.get("max_value"))
        reasons: list[str] = []

        if not material_id:
            reasons.append("component_material_identity_missing")
        if unit is None:
            reasons.append("unsupported_material_property")
        if unit and meta.get("unit") != unit:
            reasons.append("constraint_unit_mismatch")
        if low is None and high is None:
            reasons.append("no_finite_numeric_limit")
        if low is not None and high is not None and low > high:
            reasons.append("invalid_constraint_range")
        # HDT is not a generic continuous service-temperature rating.
        # Test load and method are both parts of the measured property identity.
        is_hdt = prop == "heat_deflection_temperature"
        conditions = meta.get("measurement_conditions")
        declared_test_load = None
        if is_hdt:
            if meta.get("test_method") != "ISO 75":
                reasons.append("unsupported_or_missing_test_method")
            if not isinstance(conditions, dict) or set(conditions) != {"test_load_mpa"}:
                reasons.append("test_load_condition_required")
            else:
                declared_test_load = _number(conditions["test_load_mpa"])
                if declared_test_load not in {0.45, 1.8}:
                    reasons.append("unsupported_test_load")

        evidence_rows: list[dict[str, Any]] = []
        seen_evidence: set[str] = set()
        for evidence in project.evidence:
            if not {component_id, constraint.constraint_id}.issubset(set(evidence.supports)):
                continue
            if evidence.evidence_id in seen_evidence:
                continue
            seen_evidence.add(evidence.evidence_id)
            evidence_meta = evidence.metadata
            if str(evidence_meta.get("material_id") or "") != material_id:
                reasons.append("evidence_material_identity_mismatch")
                continue
            if evidence_meta.get("material_property") != prop:
                continue
            if evidence_meta.get("unit") != unit:
                reasons.append("evidence_unit_mismatch")
                continue
            if not evidence.ref or not evidence.ref.strip():
                reasons.append("source_reference_missing")
                continue
            if is_hdt:
                if evidence_meta.get("test_method") != "ISO 75":
                    reasons.append("test_method_mismatch")
                    continue
                stated_conditions = evidence_meta.get("measurement_conditions")
                if (not isinstance(stated_conditions, dict)
                        or set(stated_conditions) != {"test_load_mpa"}
                        or _number(stated_conditions.get("test_load_mpa")) != declared_test_load):
                    reasons.append("test_condition_mismatch")
                    continue
                digest = evidence_meta.get("source_sha256")
                page = evidence_meta.get("source_page_number")
                if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
                    reasons.append("source_digest_missing_or_invalid")
                    continue
                if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= 10000:
                    reasons.append("source_page_missing_or_invalid")
                    continue
            number = _number(evidence_meta.get("value"))
            if number is None:
                reasons.append("evidence_numeric_value_invalid")
                continue
            evidence_rows.append({
                "evidence_id": evidence.evidence_id,
                "source_ref": evidence.ref,
                "value": number,
                "claimed_authority": evidence.authority.value,
                "simulated": evidence.simulated,
                "test_method": evidence_meta.get("test_method"),
                "measurement_conditions": evidence_meta.get("measurement_conditions"),
                "source_sha256": evidence_meta.get("source_sha256"),
                "source_page_number": evidence_meta.get("source_page_number"),
            })

        if not evidence_rows:
            reasons.append("no_applicable_source_linked_value")
        # Disagreement among sources is material, even when every value happens to
        # fit a broad tolerance. Do not resolve conflicts using authority labels.
        if len(evidence_rows) > 1:
            values = [row["value"] for row in evidence_rows]
            if not math.isclose(min(values), max(values), rel_tol=1e-8, abs_tol=1e-12):
                reasons.append("unreconciled_source_disagreement")
        bounds_met = False
        if evidence_rows and not reasons:
            bounds_met = all(
                (low is None or row["value"] >= low)
                and (high is None or row["value"] <= high)
                for row in evidence_rows
            )
            if not bounds_met:
                reasons.append("declared_numeric_limit_not_met")

        checks.append({
            "constraint_id": constraint.constraint_id,
            "constraint_domain": constraint.domain.value,
            "property": prop,
            "unit": unit,
            "min_value": low,
            "max_value": high,
            "source_linked_values": evidence_rows,
            "numerically_within_declared_limits": bounds_met,
            "status": "consistent_but_unverified" if not reasons else "blocked",
            "blockers": sorted(set(reasons)),
        })

    blockers = sorted({
        reason for check in checks for reason in check["blockers"]
    })
    if not checks:
        blockers.append("no_material_constraints_for_component")
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project.project_id,
        "component_id": component_id,
        "component_domain": component.domain.value,
        "material_id": material_id or None,
        "checks": checks,
        "blockers": blockers,
        "result": (
            "blocked" if blockers else "numerically_consistent_but_unverified"
        ),
        "review_required": True,
        "numerical_screening_only": True,
        "project_modified": False,
        "limitations": [
            "Caller-supplied source references, units and measurements are not independently authenticated.",
            "Agreement with numeric limits is not evidence of material compatibility or safety.",
            "Service conditions, degradation, uncertainty and processing history require separate analysis.",
        ],
        **NON_AUTHORITY,
    }


def compare_material_candidates(
    project: MachineProject, component_ids: list[str],
) -> dict[str, Any]:
    """Read-only cross-candidate screening; never calls material suitability verified."""
    if not 2 <= len(component_ids) <= 20 or len(component_ids) != len(set(component_ids)):
        raise ValueError("Provide two to twenty distinct candidate component IDs")
    reports = [evaluate_material_evidence(project, component_id) for component_id in component_ids]
    # A candidate with fewer/different requirements must not silently outrank
    # another merely because its own smaller checklist passes.
    criterion_sets: list[set[str]] = []
    for component_id in component_ids:
        relevant = [
            constraint for constraint in project.constraints
            if component_id in constraint.applies_to and "material_property" in constraint.metadata
        ]
        criterion_sets.append({
            json.dumps({
                "domain": constraint.domain.value,
                "property": constraint.metadata.get("material_property"),
                "unit": constraint.metadata.get("unit"),
                "lower": constraint.metadata.get("min_value"),
                "upper": constraint.metadata.get("max_value"),
                "test_method": constraint.metadata.get("test_method"),
                "conditions": constraint.metadata.get("measurement_conditions"),
            }, sort_keys=True, default=str)
            for constraint in relevant
        })
    comparable = bool(criterion_sets[0]) and all(
        rows == criterion_sets[0] for rows in criterion_sets[1:]
    )
    comparison_blockers = [] if comparable else ["cross_candidate_criteria_not_equivalent"]
    summary = [
        {
            "component_id": report["component_id"],
            "material_id": report["material_id"],
            "screening_status": (
                "numerically_consistent_but_unverified"
                if not report["blockers"] else "blocked"
            ),
            "checked_constraint_count": len(report["checks"]),
            "passed_numeric_criteria": sum(
                row["numerically_within_declared_limits"] for row in report["checks"]
            ),
            "blockers": report["blockers"],
        }
        for report in reports
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project.project_id,
        "candidates": reports,
        "summary": summary,
        "candidates_requiring_investigation": [
            row["component_id"] for row in summary if comparable and not row["blockers"]
        ],
        "comparable_numeric_criteria": comparable,
        "comparison_blockers": comparison_blockers,
        "selection_authorized": False,
        "comparison_is_a_screening_only": True,
        "limitations": [
            "Screening pass only means that declared numeric tests match their stated criteria.",
            "A screening pass is not manufacturing, material, electrical insulation or thermal safety clearance.",
            "Cross-candidate selection requires complete comparable requirements, manufacturing viability and review.",
        ],
        **NON_AUTHORITY,
    }
