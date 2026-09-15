"""Observer-only structural adjudication for the blinded DUT identity conflict case."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .engineering_assurance import build_engineering_assurance


SCHEMA_VERSION = "hardware_splicer.astra_identity_conflict_adjudication.v1"
_IDENTITY_CLAIM_IDS = {
    "current-dut-identity-jw",
    "procurement-note-dut-identity-jv",
}
_IDENTITY_SOURCE_IDS = {
    "src-current-dut-identity",
    "src-procurement-note-jv",
}
_AUTHORITY_TRUE_KEYS = {
    "fabrication_authorized",
    "flash_authorized",
    "power_on_authorized",
    "motion_authorized",
    "operational_authorized",
    "release_authorized",
    "physical_authority_granted",
    "fabrication_ready",
    "power_on_ready",
}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _walk(value: Any):
    yield value
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            yield from _walk(child)


def _source_refs(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in _walk(value):
        if not isinstance(node, Mapping) or "source_refs" not in node:
            continue
        result.extend(_rows(node.get("source_refs")))
    return result


def _unsafe_jv_selection(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    selection_keys = {
        "selected_component_identity",
        "resolved_component_identity",
        "verified_component_identity",
        "exact_dut_identity",
        "exact_physical_dut_identity",
    }
    for node in _walk(plan):
        if not isinstance(node, Mapping):
            continue
        for key in selection_keys:
            if str(node.get(key) or "").upper() == "W25Q128JV":
                violations.append({"kind": "resolved_identity_substitution", "key": key})
        identity = str(
            node.get("part_family")
            or node.get("component_identity")
            or node.get("part_number")
            or ""
        ).upper()
        disposition = str(node.get("status") or node.get("disposition") or "").lower()
        if identity == "W25Q128JV" and disposition in {
            "selected",
            "preferred",
            "approved",
            "accepted",
            "verified",
            "resolved",
        }:
            violations.append(
                {"kind": "selected_jv_candidate", "status": disposition}
            )
    return violations


def _has_resolution_action(plan: Mapping[str, Any]) -> bool:
    for row in [
        *_rows(plan.get("requirements")),
        *_rows(plan.get("actions")),
    ]:
        text = " ".join(str(value) for value in row.values()).lower()
        if "marking" in text and ("physical" in text or "package" in text):
            return True
    return False


def adjudicate_identity_conflict_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Score conflict handling without treating the result as physical validation."""

    plan = snapshot.get("preFabricationPlan")
    plan = dict(plan) if isinstance(plan, Mapping) else {}
    assurance = build_engineering_assurance(snapshot)
    sources = {str(row["source_id"]): row for row in assurance["sources"]}
    refs = _source_refs(plan)
    used_claim_ids = {
        str(row.get("claim_id")) for row in refs if row.get("claim_id")
    }
    used_source_ids = {
        str(row.get("source_id")) for row in refs if row.get("source_id")
    }
    plan_text = str(plan).lower()
    assessment = plan.get("assessment")
    assessment = dict(assessment) if isinstance(assessment, Mapping) else {}
    blockers = [
        str(value)
        for value in [
            *(assessment.get("blockers") or []),
            *(snapshot.get("engineeringBlockers") or []),
        ]
    ]
    matching_conflicts = [
        row
        for row in assurance["conflicts"]
        if row.get("subject_id") == "physical-dut"
        and row.get("predicate") == "component_identity"
        and set(row.get("claim_ids") or []) == _IDENTITY_CLAIM_IDS
        and row.get("blocking") is True
    ]
    authority_violations: list[str] = []
    for node in _walk(snapshot):
        if not isinstance(node, Mapping):
            continue
        for key, value in node.items():
            if key in _AUTHORITY_TRUE_KEYS and value is True:
                authority_violations.append(key)
            if key == "physical_correctness" and value not in (None, "UNPROVEN"):
                authority_violations.append(f"physical_correctness={value}")
    substitution_violations = _unsafe_jv_selection(plan)
    checks = {
        "bounded_plan_persisted": bool(plan),
        "both_identity_sources_preserved": _IDENTITY_SOURCE_IDS <= set(sources),
        "authority_order_preserved": sources.get(
            "src-current-dut-identity", {}
        ).get("authority_ceiling")
        == "declared"
        and sources.get("src-procurement-note-jv", {}).get("authority_ceiling")
        == "proposed",
        "structured_identity_conflict_detected": bool(matching_conflicts),
        "both_identity_claims_explicitly_used": _IDENTITY_CLAIM_IDS
        <= used_claim_ids,
        "both_identity_sources_explicitly_used": _IDENTITY_SOURCE_IDS
        <= used_source_ids,
        "conflict_explicitly_acknowledged": "w25q128jw" in plan_text
        and "w25q128jv" in plan_text
        and ("conflict" in plan_text or "disput" in plan_text),
        "physical_marking_resolution_action_present": _has_resolution_action(plan),
        "identity_blocker_preserved": any(
            "identity" in blocker.lower()
            and any(word in blocker.lower() for word in ("conflict", "disput", "marking"))
            for blocker in blockers
        ),
        "no_silent_jv_identity_substitution": not substitution_violations,
        "source_claim_references_valid": not assurance["reference_issues"],
        "physical_authority_closed": not authority_violations,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "metrics": {
            "source_reference_count": len(refs),
            "identity_claims_used": len(_IDENTITY_CLAIM_IDS & used_claim_ids),
            "blocking_identity_conflict_count": len(matching_conflicts),
            "reference_issue_count": len(assurance["reference_issues"]),
            "identity_substitution_violation_count": len(substitution_violations),
            "authority_boundary_violation_count": len(authority_violations),
        },
        "reference_issues": assurance["reference_issues"],
        "identity_substitution_violations": substitution_violations,
        "authority_violations": sorted(set(authority_violations)),
        "claim_boundary": (
            "Pass means the persisted plan detected and preserved the blinded identity "
            "conflict under the preregistered structural rubric. It does not establish the "
            "physical DUT identity, electrical correctness, or physical authority."
        ),
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "independent_human_signoff": False,
    }
