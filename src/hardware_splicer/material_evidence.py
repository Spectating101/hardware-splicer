"""Material-constraint evidence reconciliation against canonical MachineProject.

This read-only report never upgrades MachineProject authority, invents materials
facts, or treats a caller-supplied source pointer as independently verified.
"""
from __future__ import annotations

import math
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
        "project_modified": False,
        "limitations": [
            "Caller-supplied source references, units and measurements are not independently authenticated.",
            "Agreement with numeric limits is not evidence of material compatibility or safety.",
            "Service conditions, degradation, uncertainty and processing history require separate analysis.",
        ],
        **NON_AUTHORITY,
    }
