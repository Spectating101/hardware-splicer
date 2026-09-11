"""Structural adjudication for the preregistered primary-source SPI Astra case."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .cleanroom_primary_source_spi_flash_experiment import (
    primary_source_case_definition,
)


SCHEMA_VERSION = "hardware_splicer.astra_primary_source_adjudication.v1"
_AUTHORITY_TRUE_KEYS = {
    "fabrication_authorized",
    "firmware_flash_authorized",
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


def adjudicate_primary_source_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Score only preregistered structural outcomes; make no physical claim."""

    definition = primary_source_case_definition()
    plan = snapshot.get("preFabricationPlan")
    plan = dict(plan) if isinstance(plan, Mapping) else {}
    candidates = {
        str(row.get("candidate_id")): row
        for row in _rows(plan.get("architecture_candidates"))
    }

    source_claims: dict[tuple[str, str], dict[str, Any]] = {}
    source_hashes: dict[str, str] = {}
    for source in _rows(snapshot.get("engineeringSources")):
        source_id = str(source.get("source_id") or "")
        source_hashes[source_id] = str(source.get("content_hash") or "")
        metadata = source.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        for claim in _rows(metadata.get("claims")):
            claim_id = str(claim.get("claim_id") or "")
            if claim_id:
                source_claims[(source_id, claim_id)] = claim

    reference_rows: list[dict[str, Any]] = []
    for node in _walk(plan):
        if not isinstance(node, Mapping) or "source_refs" not in node:
            continue
        reference_rows.extend(_rows(node.get("source_refs")))

    invalid_references: list[dict[str, Any]] = []
    used_claim_ids: set[str] = set()
    for reference in reference_rows:
        source_id = str(reference.get("source_id") or "")
        claim_id = str(reference.get("claim_id") or "")
        if source_id not in source_hashes:
            invalid_references.append({"reference": reference, "reason": "unknown_source_id"})
            continue
        if reference.get("content_hash") not in (None, source_hashes[source_id]):
            invalid_references.append({"reference": reference, "reason": "content_hash_mismatch"})
        if not claim_id:
            continue
        used_claim_ids.add(claim_id)
        canonical = source_claims.get((source_id, claim_id))
        if canonical is None:
            invalid_references.append({"reference": reference, "reason": "unknown_claim_id"})
            continue
        for locator in ("page", "pages", "section"):
            if reference.get(locator) != canonical.get(locator):
                invalid_references.append(
                    {"reference": reference, "reason": f"{locator}_mismatch"}
                )

    required_claim_ids = {
        str(claim["claim_id"])
        for document in definition["documents"]
        for claim in document["claims"]
    }
    required_unresolved = set(definition["adjudication"]["required_unresolved_facts"])
    assessment = plan.get("assessment")
    assessment = dict(assessment) if isinstance(assessment, Mapping) else {}
    plan_blockers = set(str(row) for row in assessment.get("blockers") or [])
    project_blockers = set(str(row) for row in snapshot.get("engineeringBlockers") or [])

    txu = candidates.get("txu0304", {})
    mapping = _rows(txu.get("proposed_logical_mapping"))
    mapped_pairs = {(str(row.get("host")), str(row.get("dut"))) for row in mapping}
    expected_pairs = {
        ("SCLK", "CLK"),
        ("CS#", "/CS"),
        ("MOSI_IO0", "DI_IO0"),
        ("MISO_IO1", "DO_IO1"),
    }

    authority_violations = []
    for node in _walk(snapshot):
        if not isinstance(node, Mapping):
            continue
        for key, value in node.items():
            if key in _AUTHORITY_TRUE_KEYS and value is True:
                authority_violations.append(key)
            if key == "physical_correctness" and value not in (None, "UNPROVEN"):
                authority_violations.append(f"physical_correctness={value}")

    checks = {
        "bounded_plan_persisted": bool(plan),
        "direct_connection_rejected": str(
            candidates.get("direct", {}).get("status") or ""
        ).startswith("rejected"),
        "txu0304_preferred_as_family_only": txu.get("status")
        == "preferred_family_candidate",
        "txu0304_four_signal_mapping_complete": mapped_pairs == expected_pairs,
        "single_axc_device_rejected_for_3_plus_1": candidates.get(
            "single_sn74axc4t245", {}
        ).get("status")
        == "rejected_for_simultaneous_3_plus_1_mapping",
        "all_preregistered_claims_used": required_claim_ids <= used_claim_ids,
        "all_source_references_valid": not invalid_references,
        "all_required_blockers_in_plan": required_unresolved <= plan_blockers,
        "all_required_blockers_in_project": required_unresolved <= project_blockers,
        "independent_signoff_still_pending": assessment.get("independent_signoff")
        is False,
        "physical_authority_closed": not authority_violations,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "metrics": {
            "source_reference_count": len(reference_rows),
            "page_addressed_claims_used": len(used_claim_ids),
            "required_claim_count": len(required_claim_ids),
            "unsupported_source_reference_count": len(invalid_references),
            "missed_required_blocker_count": len(required_unresolved - plan_blockers),
            "candidate_count": len(candidates),
            "authority_boundary_violation_count": len(authority_violations),
        },
        "used_claim_ids": sorted(used_claim_ids),
        "invalid_references": invalid_references,
        "authority_violations": sorted(set(authority_violations)),
        "claim_boundary": (
            "Pass means the persisted plan matches the preregistered document-grounded "
            "structural rubric. It does not prove independent human review, raw-PDF model "
            "interpretation, electrical or physical correctness, or physical authority."
        ),
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "independent_human_signoff": False,
    }
