"""Explicit authority boundary for deterministic repair proposals.

A repair suggestion may change *how the same declared design is laid out* after a
machine-verifiable DRC failure. It may not select replacement components, alter module
identity, rewrite nets/topology, or open fabrication/power/motion authority.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, Mapping


SCHEMA_VERSION = "hardware_splicer.repair_policy.v1"
ALLOWED_GEOMETRY_FIXUP_KEYS = frozenset(
    {
        "edge_pad_extra_mm",
        "via_clearance_mm",
        "module_gap_extra_mm",
    }
)
REPAIR_MUTABLE_GRAPH_KEYS = frozenset({"drc_fixup"})


def normalize_geometry_fixup_hints(hints: Mapping[str, Any] | None) -> Dict[str, float]:
    """Validate the complete deterministic repair mutation surface.

    Unknown keys are rejected instead of silently becoming future architecture/identity
    mutation channels. Values must be finite, non-negative geometry magnitudes.
    """
    normalized: Dict[str, float] = {}
    for raw_key, raw_value in dict(hints or {}).items():
        key = str(raw_key)
        if key not in ALLOWED_GEOMETRY_FIXUP_KEYS:
            raise ValueError(f"repair fixup key is outside geometry authority: {key}")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"repair fixup value must be numeric: {key}") from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"repair fixup value must be finite and non-negative: {key}")
        normalized[key] = value
    return normalized


def repair_authority_projection(graph: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Project the graph state that repair is forbidden to mutate.

    The only repair-owned top-level field is ``drc_fixup``. Everything else remains part
    of the pre-existing design authority surface, including architecture/build selection,
    component identity, module overrides, nodes, wires/nets, constraints and provenance.
    A deep copy prevents later mutation from invalidating the comparison snapshot.
    """
    body = dict(graph or {})
    return {
        key: copy.deepcopy(value)
        for key, value in body.items()
        if str(key) not in REPAIR_MUTABLE_GRAPH_KEYS
    }


def assert_repair_preserves_authority(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> None:
    """Fail closed if a repair cycle changed anything outside the geometry hint surface."""
    expected = repair_authority_projection(before)
    actual = repair_authority_projection(after)
    if expected == actual:
        return

    changed = sorted(
        {
            str(key)
            for key in set(expected) | set(actual)
            if expected.get(key) != actual.get(key)
        }
    )
    detail = ", ".join(changed) if changed else "nested design state"
    raise ValueError(f"repair changed graph outside geometry authority: {detail}")


def repair_policy_report(hints: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    normalized = normalize_geometry_fixup_hints(hints)
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "deterministic_geometry_repair",
        "repair_proposal_only": True,
        "verified_truth_effect": "none",
        "mutable_graph_keys": sorted(REPAIR_MUTABLE_GRAPH_KEYS),
        "allowed_mutation_surface": [f"drc_fixup.{key}" for key in sorted(ALLOWED_GEOMETRY_FIXUP_KEYS)],
        "effective_fixups": {key: round(value, 4) for key, value in sorted(normalized.items())},
        "component_identity_mutation_allowed": False,
        "module_override_mutation_allowed": False,
        "net_topology_mutation_allowed": False,
        "architecture_selection_allowed": False,
        "electrical_contract_mutation_allowed": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "authority_effect": "none",
    }
