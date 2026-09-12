"""Preregistered adjudication for the blinded raw-document Astra case."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .cleanroom_primary_source_spi_flash_experiment import (
    primary_source_case_definition,
)
from .document_evidence import (
    DOCUMENT_EXTRACTION_IMPLEMENTATION,
    extract_registered_pdf,
    normalize_supporting_text,
    supporting_text_is_present,
    text_sha256,
)
from .engineering_assurance import build_engineering_assurance


SCHEMA_VERSION = "hardware_splicer.astra_raw_document_adjudication.v1"
EXACT_MAPPING_POLICY = "exact_v1"
DATASHEET_FUNCTION_ALIAS_POLICY = "datasheet_function_aliases_v1"

_DUT_SIGNAL_ALIASES = {
    "CLK": "CLK",
    "/CS": "/CS",
    "DI": "DI_IO0",
    "DI(IO0)": "DI_IO0",
    "DI_IO0": "DI_IO0",
    "DO": "DO_IO1",
    "DO(IO1)": "DO_IO1",
    "DO_IO1": "DO_IO1",
}

_SEMANTIC_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    "dut-operating-supply": (("1.7",), ("1.95",)),
    "dut-pin-absolute-maximum": (
        ("-0.6", "−0.6", "–0.6"),
        ("vcc+0.4", "vcc + 0.4", "vcc plus 0.4"),
    ),
    "dut-standard-spi-directions": (
        ("di", "data input"),
        ("do", "data output"),
        ("input",),
        ("output",),
    ),
    "dut-package-dependent-pinout": (("package",), ("pin",)),
    "txu-fixed-direction-map": (
        ("a1",),
        ("a2",),
        ("a3",),
        ("a4y",),
        ("b1y",),
        ("b2y",),
        ("b3y",),
        ("b4",),
        ("input",),
        ("output",),
    ),
    "txu-supply-range": (("1.08",), ("5.5",)),
    "txu-output-disable": (("oe", "output enable"), ("high-impedance",)),
    "txu-spi-example-not-component-spec": (
        ("not part of the ti component specification",),
        ("validating and testing", "validate and test"),
    ),
    "axc-direction-grouping": (
        ("1dir",),
        ("2dir",),
        ("1a1",),
        ("1a2",),
        ("2a1",),
        ("2a2",),
    ),
    "axc-supply-range": (("0.65",), ("3.6",)),
    "axc-function-table": (
        ("each 2-bit section",),
        ("b data to a bus",),
        ("a data to b bus",),
        ("isolation",),
    ),
}

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
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for child in value:
            yield from _walk(child)


def _expected_claims() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for document in primary_source_case_definition()["documents"]:
        offset = 1 if document["source_id"] == "src-dut-datasheet" else 0
        for claim in document["claims"]:
            declared_pages = (
                [claim["page"]]
                if claim.get("page") is not None
                else list(claim.get("pages") or [])
            )
            result[str(claim["claim_id"])] = {
                "source_id": str(document["source_id"]),
                "pdf_page_numbers": {
                    int(page) + offset for page in declared_pages
                },
                "semantic_groups": _SEMANTIC_GROUPS[str(claim["claim_id"])],
            }
    return result


def _candidate_text(row: Mapping[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in (
            "candidate_id",
            "candidate_kind",
            "component_family",
            "manufacturer_part_number",
            "description",
            "rationale",
            "status",
        )
    ).casefold()


def _find_candidate(
    candidates: Sequence[Mapping[str, Any]], *needles: str
) -> dict[str, Any]:
    for candidate in candidates:
        text = _candidate_text(candidate)
        if any(needle.casefold() in text for needle in needles):
            return dict(candidate)
    return {}


def _disposition(candidate: Mapping[str, Any]) -> str:
    return str(candidate.get("status") or candidate.get("disposition") or "").casefold()


def _mapped_signal_pairs(
    mapping: Sequence[Mapping[str, Any]], *, alias_policy: str
) -> set[tuple[str, str]]:
    if alias_policy not in {EXACT_MAPPING_POLICY, DATASHEET_FUNCTION_ALIAS_POLICY}:
        raise ValueError(f"unknown mapping alias policy: {alias_policy!r}")
    pairs = {
        (str(row.get("host")), str(row.get("dut")))
        for row in mapping
    }
    if alias_policy == EXACT_MAPPING_POLICY:
        return pairs
    return {
        (host, _DUT_SIGNAL_ALIASES.get(dut.replace(" ", "").upper(), dut))
        for host, dut in pairs
    }


def _semantic_claim_pass(
    claim: Mapping[str, Any], groups: Sequence[Sequence[str]]
) -> bool:
    metadata = claim.get("metadata")
    support = metadata.get("supporting_text") if isinstance(metadata, Mapping) else ""
    text = normalize_supporting_text(
        json.dumps(claim.get("value"), ensure_ascii=False, sort_keys=True)
        + " "
        + str(support or "")
    ).casefold()
    return all(any(alternative.casefold() in text for alternative in group) for group in groups)


def adjudicate_raw_document_snapshot(
    snapshot: Mapping[str, Any],
    *,
    project_id: str,
    project_root: str | Path,
    mapping_alias_policy: str = EXACT_MAPPING_POLICY,
) -> dict[str, Any]:
    """Verify document extraction anchors and the resulting bounded design state."""

    expected = _expected_claims()
    sources = {
        str(row.get("source_id") or ""): row
        for row in _rows(snapshot.get("engineeringSources"))
    }
    documents = {
        source_id: extract_registered_pdf(
            project_id,
            source,
            project_root=project_root,
        )
        for source_id, source in sources.items()
        if source_id in {row["source_id"] for row in expected.values()}
    }
    claims: dict[str, dict[str, Any]] = {}
    duplicate_claim_ids: set[str] = set()
    for source in sources.values():
        for claim in _rows(source.get("claims")):
            claim_id = str(claim.get("claim_id") or "")
            if not claim_id:
                continue
            if claim_id in claims:
                duplicate_claim_ids.add(claim_id)
            claims[claim_id] = claim

    claim_checks: dict[str, dict[str, bool]] = {}
    claim_issues: list[dict[str, Any]] = []
    for claim_id, rule in expected.items():
        claim = claims.get(claim_id, {})
        source_id = str(rule["source_id"])
        locator = (
            dict(claim.get("evidence_locator") or {})
            if isinstance(claim, Mapping)
            else {}
        )
        metadata = (
            dict(claim.get("metadata") or {})
            if isinstance(claim, Mapping)
            else {}
        )
        page_number = locator.get("page")
        page_valid = (
            isinstance(page_number, int)
            and not isinstance(page_number, bool)
            and page_number in rule["pdf_page_numbers"]
            and source_id in documents
            and page_number <= len(documents[source_id].pages)
        )
        page_text = documents[source_id].pages[page_number - 1] if page_valid else ""
        supporting_text = str(metadata.get("supporting_text") or "")
        checks = {
            "present_once": bool(claim) and claim_id not in duplicate_claim_ids,
            "source_id_exact": claim.get("source_id") == source_id if claim else False,
            "authority_proposed": claim.get("authority") == "proposed" if claim else False,
            "machine_proposal_origin": metadata.get("claim_origin")
            == "model_proposed_from_hash_bound_document_text",
            "independent_review_pending": metadata.get("independent_review_state")
            == "unreviewed",
            "expected_pdf_page": page_valid,
            "source_hash_exact": locator.get("source_content_hash")
            == documents[source_id].content_hash
            if source_id in documents
            else False,
            "page_text_hash_exact": page_valid
            and locator.get("page_text_sha256") == text_sha256(page_text),
            "supporting_text_hash_exact": bool(supporting_text)
            and locator.get("supporting_text_sha256")
            == text_sha256(normalize_supporting_text(supporting_text)),
            "supporting_text_present_on_page": page_valid
            and supporting_text_is_present(page_text, supporting_text),
            "semantic_target_satisfied": bool(claim)
            and _semantic_claim_pass(claim, rule["semantic_groups"]),
            "extraction_identity_exact": locator.get("extraction_implementation")
            == DOCUMENT_EXTRACTION_IMPLEMENTATION,
        }
        claim_checks[claim_id] = checks
        for check, passed in checks.items():
            if not passed:
                claim_issues.append({"claim_id": claim_id, "check": check})

    plan = snapshot.get("preFabricationPlan")
    plan = dict(plan) if isinstance(plan, Mapping) else {}
    references = [
        reference
        for node in _walk(plan)
        if isinstance(node, Mapping) and "source_refs" in node
        for reference in _rows(node.get("source_refs"))
    ]
    used_claim_ids = {
        str(reference.get("claim_id") or "") for reference in references
    }
    candidates = _rows(plan.get("architecture_candidates"))
    direct = _find_candidate(candidates, "direct")
    txu = _find_candidate(candidates, "txu0304")
    axc = _find_candidate(candidates, "sn74axc4t245", "axc4t245")
    mapping = _rows(txu.get("proposed_logical_mapping") or txu.get("logical_mapping"))
    mapped_pairs = _mapped_signal_pairs(mapping, alias_policy=mapping_alias_policy)
    expected_pairs = {
        ("SCLK", "CLK"),
        ("CS#", "/CS"),
        ("MOSI_IO0", "DI_IO0"),
        ("MISO_IO1", "DO_IO1"),
    }
    assessment = plan.get("assessment")
    assessment = dict(assessment) if isinstance(assessment, Mapping) else {}
    required_blockers = set(
        primary_source_case_definition()["adjudication"][
            "required_unresolved_facts"
        ]
    )
    plan_blockers = {
        str(row)
        for row in assessment.get("blockers")
        or assessment.get("unresolved_facts")
        or []
    }
    authority_violations: list[str] = []
    for node in _walk(snapshot):
        if not isinstance(node, Mapping):
            continue
        for key, value in node.items():
            if key in _AUTHORITY_TRUE_KEYS and value is True:
                authority_violations.append(key)
            if key == "physical_correctness" and value not in (None, "UNPROVEN"):
                authority_violations.append(f"physical_correctness={value}")

    assurance = build_engineering_assurance(snapshot)
    checks = {
        "all_11_claims_hash_and_page_anchored": not claim_issues
        and len(claim_checks) == 11,
        "all_11_extracted_claims_used": set(expected).issubset(used_claim_ids),
        "all_plan_source_references_valid": not assurance["reference_issues"],
        "bounded_plan_persisted": bool(plan),
        "direct_connection_rejected": _disposition(direct).startswith("rejected"),
        "txu0304_preferred_as_family_only": _disposition(txu)
        in {"preferred_family_candidate", "conditionally_preferred"},
        "txu0304_four_signal_mapping_complete": mapped_pairs == expected_pairs,
        "single_axc_device_rejected_for_3_plus_1": _disposition(axc).startswith(
            "rejected"
        )
        and "direction" in _candidate_text(axc),
        "all_required_blockers_in_plan": required_blockers <= plan_blockers,
        "independent_signoff_still_pending": assessment.get("independent_signoff")
        is False,
        "physical_authority_closed": not authority_violations,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "mapping_alias_policy": mapping_alias_policy,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "claim_checks": claim_checks,
        "claim_issues": claim_issues,
        "metrics": {
            "required_claim_count": len(expected),
            "persisted_target_claim_count": sum(
                claim_id in claims for claim_id in expected
            ),
            "fully_anchored_claim_count": sum(
                all(row.values()) for row in claim_checks.values()
            ),
            "used_target_claim_count": len(set(expected).intersection(used_claim_ids)),
            "source_reference_count": len(references),
            "reference_issue_count": len(assurance["reference_issues"]),
            "authority_boundary_violation_count": len(authority_violations),
        },
        "reference_issues": assurance["reference_issues"],
        "authority_violations": sorted(set(authority_violations)),
        "claim_boundary": (
            "Pass proves that Astra extracted all preregistered targets from frozen, "
            "hash-reverified PDF page text; persisted page-anchored unreviewed proposals; "
            "and used them in the bounded structural decision. It does not prove visual "
            "PDF comprehension, independent review, electrical correctness, physical "
            "identity, or physical authority."
        ),
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "independent_human_signoff": False,
    }
