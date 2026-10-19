"""Read-only evidence-aware candidate interface graph for novel splicing.

The candidate inventory is a *hypothesis ledger*: independent physical proof,
ownership, and pin/power measurements must arrive through canonical capture.
Exact function tags avoid misleading generic keyword or part-name matches.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

SCHEMA = "hardware_splicer.multi_donor_compatibility.v1"
_CLASSES = {"seller_claim", "manufacturer_family_documentation", "engineering_hypothesis"}
_INTERFACE_FIELDS = {"protocol", "connector", "voltage_v"}
_CANDIDATE_FIELDS = {
    "candidate_id", "source_ref", "name", "function_tags", "partial_function_tags",
    "evidence_class", "evidence_url", "interface", "missing_facts",
}
_CONNECTION_FIELDS = {"connection_id", "from_candidate", "to_candidate", "purpose"}
MATERIAL_FIELDS = {"component_hypotheses", "proposed_connections"}


def _as_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise ValueError(f"{field} must be nonempty bounded string")
    return value.strip()


def _unique_tags(value: Any, *, name: str, allowed: set[str], max_size: int = 32) -> list[str]:
    if not isinstance(value, list) or len(value) > max_size:
        raise ValueError(f"{name} must be a list of <= {max_size} valid strings")
    tags = [_as_text(s, name) for s in value]
    if len(tags) != len(set(tags)) or not set(tags) <= allowed:
        raise ValueError(f"{name} has duplicates or entries not in required_functions")
    return tags


def _interface(value: Any, key: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) - _INTERFACE_FIELDS:
        raise ValueError(f"{key} requires an interface object with only protocol/connector/voltage_v")
    normalized = {}
    for field in ("protocol", "connector"):
        val = value.get(field)
        if val is not None:
            val = _as_text(val, f"{key}.{field}")
        normalized[field] = val
    voltage = value.get("voltage_v")
    if voltage is not None and (
        isinstance(voltage, bool) or not isinstance(voltage, (int, float))
        or not 0 < voltage <= 1000 or not float("-inf") < voltage < float("inf")
    ):
        raise ValueError(f"{key}.voltage_v is invalid")
    normalized["voltage_v"] = voltage
    return normalized


def _sources(mission: Mapping[str, Any]) -> set[str]:
    if mission.get("type") != "novel_splice":
        raise ValueError("multi-donor compatibility only applies to novel_splice missions")
    return set(mission["source_refs"])


def evaluate_multi_donor_compatibility(
    mission: Mapping[str, Any],
    materials: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate claimed coverage and unverified interfaces, NOT build feasibility.

    Input evidence_class means *claimed type*, never externally authenticated.
    Even perfectly matching declarative interfaces remain candidate_only.
    """
    sources = _sources(mission)
    functions = list(mission["required_functions"])
    if materials is None:
        materials = {}
    if not isinstance(materials, Mapping) or set(materials) - MATERIAL_FIELDS:
        raise ValueError("engineering_materials must only contain component_hypotheses and proposed_connections")
    candidates = materials.get("component_hypotheses") or []
    connections = materials.get("proposed_connections") or []
    if not isinstance(candidates, list) or len(candidates) > 128:
        raise ValueError("component_hypotheses must be a bounded list")
    if not isinstance(connections, list) or len(connections) > 128:
        raise ValueError("proposed_connections must be a bounded list")
    ids: dict[str, dict[str, Any]] = {}
    for raw in candidates:
        if not isinstance(raw, Mapping) or set(raw) - _CANDIDATE_FIELDS:
            raise ValueError("unrecognized candidate field or candidate is not object")
        candidate_id = _as_text(raw.get("candidate_id"), "candidate_id")
        source_ref = _as_text(raw.get("source_ref"), "source_ref")
        if candidate_id in ids:
            raise ValueError(f"duplicate candidate_id: {candidate_id}")
        if source_ref not in sources:
            raise ValueError(f"candidate from non-mission source: {source_ref}")
        evidence_class = raw.get("evidence_class")
        if evidence_class not in _CLASSES:
            raise ValueError("unsupported evidence_class")
        url = raw.get("evidence_url")
        if url is not None and (
            not isinstance(url, str) or not url.startswith("https://") or len(url) > 2048
        ):
            raise ValueError("evidence_url must be an https URL")
        tags = _unique_tags(raw.get("function_tags", []),name="function_tags",allowed=set(functions))
        partial = _unique_tags(raw.get("partial_function_tags", []),name="partial_function_tags",allowed=set(functions))
        if set(tags) & set(partial):
            raise ValueError("function cannot be both fully and partially claimed")
        missing = raw.get("missing_facts")
        if not isinstance(missing, list) or not 1 <= len(missing) <= 32:
            raise ValueError("unverified candidate must state missing_facts")
        missing = [_as_text(x, "missing_facts") for x in missing]
        ids[candidate_id] = {
            "candidate_id": candidate_id,
            "source_ref": source_ref,
            "component_hypothesis": _as_text(raw.get("name"), "name"),
            "claimed_function_tags": tags,
            "partial_function_tags": partial,
            "evidence_class_claimed": evidence_class,
            "source_document_or_listing_url": url,
            "declared_interface_not_measured": _interface(raw.get("interface") or {},candidate_id),
            "missing_facts": missing,
            "physical_component_verified": False,
            "pinout_or_voltage_measured": False,
            "authorized_for_design_binding": False,
        }
    links = []
    seen_links = set()
    for raw in connections:
        if not isinstance(raw, Mapping) or set(raw) - _CONNECTION_FIELDS:
            raise ValueError("invalid proposed connection fields")
        link_id = _as_text(raw.get("connection_id"), "connection_id")
        if link_id in seen_links:
            raise ValueError("duplicate connection id")
        seen_links.add(link_id)
        first = _as_text(raw.get("from_candidate"), "from_candidate")
        second = _as_text(raw.get("to_candidate"), "to_candidate")
        if first not in ids or second not in ids or first == second:
            raise ValueError("connection must reference two distinct known candidates")
        a = ids[first]["declared_interface_not_measured"]
        b = ids[second]["declared_interface_not_measured"]
        mismatches = [
            key for key in ("protocol", "voltage_v")
            if a[key] is not None and b[key] is not None and a[key] != b[key]
        ]
        unknowns = [
            f"{side}.{key}" for side, contract in (("from",a),("to",b))
            for key in _INTERFACE_FIELDS if contract[key] is None
        ]
        status = ("DECLARED_MISMATCH_NEEDS_ENGINEER" if mismatches
                  else "BLOCKED_UNKNOWN_INTERFACE" if unknowns
                  else "PAPER_ONLY_MATCH_UNVERIFIED")
        links.append({
            "connection_id": link_id,
            "source_ref_from": ids[first]["source_ref"],
            "source_ref_to": ids[second]["source_ref"],
            "from_candidate": first,
            "to_candidate": second,
            "intended_purpose": _as_text(raw.get("purpose"),"purpose"),
            "comparison_status": status,
            "declared_mismatch_fields": mismatches,
            "missing_interface_facts": sorted(unknowns),
            "electrical_connection_proven": False,
            "safe_to_wire": False,
        })
    coverage = []
    for fn in functions:
        full = [x["candidate_id"] for x in ids.values() if fn in x["claimed_function_tags"]]
        partial = [x["candidate_id"] for x in ids.values() if fn in x["partial_function_tags"]]
        coverage.append({
            "required_function": fn,
            "candidate_hypotheses": full,
            "partial_candidate_hypotheses": partial,
            "coverage_status": "HYPOTHESIZED_NOT_VERIFIED" if full else
                               "PARTIAL_CLAIM_GAP" if partial else "UNMAPPED_GAP",
            "verified_functional_coverage": False,
        })
    represented_sources = sorted({x["source_ref"] for x in ids.values()})
    return {
        "schema_version": SCHEMA,
        "candidate_count": len(ids),
        "source_refs_in_mission": list(mission["source_refs"]),
        "source_refs_with_hypotheses": represented_sources,
        "distinct_source_hypotheses": len(represented_sources),
        "verified_distinct_physical_donors": 0,
        "minimum_distinct_donors_required": mission["minimum_distinct_donors"],
        "components": list(ids.values()),
        "function_coverage": coverage,
        "proposed_interfaces": links,
        "all_proposed_links_physically_blocked": True,
        "can_claim_new_product": False,
        "unresolved_required_functions": [x["required_function"] for x in coverage],
        "data_policy": "unverified hypotheses and documents only; no electrical authority, no measurements or custody evidence",
    }
