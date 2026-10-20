"""Deterministic ISO75 PDF claim -> proposed MachineProject evidence candidate.

This does not fetch files, authenticate references, save a project, grant release,
or adjudicate whether the test method really applies to the material specimen.
It only converts previously source-anchored document-claim content into a
machine-readable proposed evidence object and checks quoted numbers agree.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

from .machine_project import AuthorityState, EvidenceRef

_HDT_QUOTE = re.compile(
    r"Heat\s+Deflection\s+Temperature\s*\(\s*(0[.]45|1[.]80)\s*MPa\s*\)"
    r"\s*\[\s*°C\s*\]\s*(\d+(?:[.]\d+)?)\s+ISO\s+75\b",
    re.IGNORECASE,
)


def draft_iso75_evidence(
    claim: Mapping[str, Any], *, component_id: str,
    constraint_id: str, material_id: str,
) -> dict[str, Any]:
    if not all(isinstance(x, str) and 0 < len(x.strip()) <= 128
               for x in (component_id, constraint_id, material_id)):
        raise ValueError("Component, constraint, and material IDs are required")
    if claim.get("authority") != "proposed":
        raise ValueError("Expected unreviewed proposed canonical document claim")
    if claim.get("predicate") != "heat_deflection_temperature":
        raise ValueError("Only heat-deflection-temperature document claims are supported")
    if claim.get("units") != "°C":
        raise ValueError("Document claim must report degrees Celsius")
    claim_value = claim.get("value")
    if isinstance(claim_value, bool) or not isinstance(claim_value, (int, float)):
        raise ValueError("Claim value must be a numeric Celsius reading")
    if not math.isfinite(float(claim_value)) or not -100 <= float(claim_value) <= 400:
        raise ValueError("Nonfinite or out-of-scope HDT temperature")
    if claim.get("subject_id") != material_id:
        raise ValueError("Canonical claim subject does not match selected material identity")
    source_id = str(claim.get("source_id") or "").strip()
    claim_id = str(claim.get("claim_id") or "").strip()
    locator = claim.get("evidence_locator") or {}
    metadata = claim.get("metadata") or {}
    if not isinstance(locator, Mapping) or not isinstance(metadata, Mapping):
        raise ValueError("Canonical locator and claim metadata required")
    supporting_text = str(metadata.get("supporting_text") or "").strip()
    quote_match = _HDT_QUOTE.search(supporting_text)
    if not quote_match:
        raise ValueError("Supporting quote has no exact ISO 75 HDT measurement")
    load_mpa = float(quote_match.group(1))
    value_c = float(quote_match.group(2))
    if not -100 <= value_c <= 400 or abs(value_c - float(claim_value)) > 1e-9:
        raise ValueError("Document claim value disagrees with anchored source quotation")
    source_content_hash = str(locator.get("source_content_hash") or "")
    if re.fullmatch(r"sha256:[a-f0-9]{64}", source_content_hash) is None:
        raise ValueError("Canonical source SHA256 is missing")
    page = locator.get("page")
    if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= 10000:
        raise ValueError("Source page locator is missing")
    if not source_id or not claim_id:
        raise ValueError("Canonical source and claim IDs required")
    if metadata.get("independent_review_state") != "unreviewed":
        raise ValueError("Expected unreviewed canonical document claim")
    candidate = EvidenceRef(
        evidence_id=f"chemical-hdt:{claim_id}",
        kind="iso75_hdt_document_claim",
        basis="source_anchored_claim_proposal",
        ref=f"registered-document:{source_id}:page:{page}:claim:{claim_id}",
        supports=[component_id, constraint_id],
        authority=AuthorityState.PROPOSED,
        simulated=False,
        metadata={
            "material_id": material_id,
            "material_property": "heat_deflection_temperature",
            "unit": "K",
            "value": value_c + 273.15,
            "test_method": "ISO 75",
            "measurement_conditions": {"test_load_mpa": load_mpa},
            "source_sha256": source_content_hash.removeprefix("sha256:"),
            "source_page_number": page,
            "canonical_source_id": source_id,
            "canonical_claim_id": claim_id,
            "independent_review_state": "unreviewed",
            "source_claim_authority": "proposed",
        },
    )
    return {
        "schema_version": "hardware_splicer.chemical_source_bridge.v1",
        "evidence_candidate": candidate.model_dump(mode="json"),
        "requires_human_review": True,
        "persisted": False,
        "source_quote_value_matches_claim": True,
        "document_source_hash_rechecked_by_bridge": False,
        "physical_authority_upgraded": False,
        "note": "Source bytes must be checked by canonical HS document read; this converter only validates locator shape and quote/number agreement.",
    }
