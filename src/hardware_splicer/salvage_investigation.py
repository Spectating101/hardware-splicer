"""Deterministic, non-authoritative investigation prompts for unresolved donor facts.

This is prioritization of *known gaps*, not an inference engine or a physical
measurement instruction. A model or qualified operator must select the actual
safe observation, and human evidence enters only through canonical gates.
"""
from __future__ import annotations

from typing import Any, Mapping

from .fabrication_operator import FabricationValidationError
from .salvage_resource_graph import resource_index

_SCHEMA = "hardware_splicer.salvage_investigation_queue.v1"
_PRIORITY = {"contract": 0, "identity": 1, "pinout": 2, "voltage": 3,
             "current": 4, "geometry": 5, "function": 6}


def project_investigation_queue(graph: Mapping[str, Any], *, max_items: int = 32) -> dict[str, Any]:
    """Project bounded questions from unresolved donor facts; never authorize actions."""
    if type(max_items) is not int or not 1 <= max_items <= 128:
        raise FabricationValidationError("max_items must be an integer between 1 and 128")
    resources = resource_index(graph)
    items: list[dict[str, Any]] = []
    for identifier in sorted(resources):
        resource = resources[identifier]
        if resource["kind"] != "donor":
            continue
        missing = resource["unresolved_facts"]
        # A missing contract is a discovery gate, not evidence that a donor works.
        if resource.get("contract_state") == "unknown" and "contract" not in missing:
            missing = [*missing, "contract"]
        for fact in sorted(set(missing)):
            if not fact.strip():
                continue
            normalized = fact.strip().lower()
            priority = _PRIORITY.get(normalized, 10)
            items.append({
                "resource_id": identifier,
                "missing_fact": fact,
                "priority": priority,
                "question": f"What trustworthy evidence would resolve '{fact}' for donor '{identifier}'?",
                "status": "unresolved",
                "requires_human_or_canonical_evidence": True,
                "suggested_physical_action": None,
                "verified": False,
                "physical_authority_granted": False,
            })
    items.sort(key=lambda item: (item["priority"], item["resource_id"], item["missing_fact"]))
    return {
        "schema": _SCHEMA,
        "items": items[:max_items],
        "total_unresolved": len(items),
        "truncated": len(items) > max_items,
        "selection_policy": "known_gap_priority_then_stable_identity; no learned information-gain claim",
        "truth_contract": {
            "read_only": True,
            "model_hypotheses_are_evidence": False,
            "suggested_measurements_are_preapproved": False,
            "physical_authority_granted": False,
        },
    }
