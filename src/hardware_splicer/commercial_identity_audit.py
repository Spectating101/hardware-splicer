"""Check source-claimed equipment attributes before committing hardware capital.

This is an identity discrepancy detector, NOT a fraud detector. Source assertions
require independent confirmation and a board-level inspection to establish SKU.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "hardware_splicer.commercial_identity_claims.v1"


def reconcile_identity_claims(raw: Mapping[str, Any]) -> dict[str, Any]:
    if raw.get("schema_version") != SCHEMA:
        raise ValueError("unsupported identity claims")
    cid = str(raw.get("candidate_id") or "")
    if not cid:
        raise ValueError("missing candidate id")
    source_groups = raw.get("source_groups")
    if not isinstance(source_groups, list) or len(source_groups) < 2:
        raise ValueError("requires independent source groups")
    baseline: dict[str, dict[str, Any]] = {}
    observed: dict[str, dict[str, Any]] = {}
    for group in source_groups:
        if not isinstance(group, Mapping):
            raise ValueError("malformed source group")
        kind = group.get("source_role")
        if kind not in {"manufacturer_spec", "seller_listing", "physical_observation"}:
            raise ValueError("unrecognized identity source role")
        ref = group.get("source_url")
        if not isinstance(ref, str) or not ref.startswith("https://"):
            raise ValueError("source reference required")
        for item in group.get("claims") or []:
            if not isinstance(item, Mapping):
                raise ValueError("malformed source claim")
            attribute = str(item.get("attribute") or "")
            value = str(item.get("value") or "")
            if not attribute or not value:
                raise ValueError("missing attribute or claimed value")
            claim = {"value": value.casefold().strip(), "source_url": ref,
                     "claimed_value": value, "role": kind}
            target = baseline if kind == "manufacturer_spec" else observed
            if attribute in target and target[attribute]["value"] != claim["value"]:
                raise ValueError("conflicting same-role or non-manufacturer claims")
            target[attribute] = claim
    conflicts = []
    for name, reported in observed.items():
        correct = baseline.get(name)
        if correct is not None and reported["value"] != correct["value"]:
            conflicts.append({
                "attribute": name,
                "seller_claim": reported["claimed_value"],
                "manufacturer_claim": correct["claimed_value"],
                "seller_source": reported["source_url"],
                "manufacturer_source": correct["source_url"],
                "explanation": "SOURCE_ATTRIBUTE_CONFLICT_NEEDS_PHYSICAL_MODEL_VERIFICATION",
            })
    return {
        "schema_version": "hardware_splicer.commercial_identity_audit.v1",
        "candidate_id": cid,
        "status": "HOLD_IDENTITY_CONFLICT" if conflicts else "NO_CONTRADICTION_FOUND",
        "conflicts": conflicts,
        "physical_identity_verified": False,
        "machine_identified_from_listings": False,
        "cannot_auto_identify_listing": True,
        "purchase_authorized": False,
    }
