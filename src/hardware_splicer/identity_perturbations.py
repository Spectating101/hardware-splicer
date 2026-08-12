"""Identity-aware perturbations for outer-agent adversarial replay.

A useful invariance test must preserve the engineering evidence it claims to preserve.
Hardware labels are tricky because a human-facing ``name`` may be either cosmetic text or
the only physical identity evidence available. This module classifies and applies a small
set of perturbations without pretending those cases are equivalent.

The outer evaluator may use ``equivalence`` cases to measure semantic/script stability.
``evidence_change`` cases are still valuable, but drift is expected and must not be
reported as model/script instability merely because the evidence changed.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Sequence


SCHEMA_VERSION = "hardware_splicer.identity_perturbation.v1"


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _parts(snapshot: Mapping[str, Any]) -> tuple[str | None, list[Dict[str, Any]]]:
    for key in ("available_parts", "parts", "resources"):
        value = snapshot.get(key)
        if isinstance(value, list):
            return key, [deepcopy(dict(row)) for row in value if isinstance(row, Mapping)]
    return None, []


def _identity_anchor(row: Mapping[str, Any]) -> str | None:
    for key in (
        "module_id",
        "catalog_module_id",
        "catalog_equivalent_id",
        "equivalent_module_id",
        "mpn",
        "part_number",
        "manufacturer_part_number",
        "sku",
        "model",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            return key
    return None


def _result(
    snapshot: Mapping[str, Any],
    *,
    perturbation: str,
    classification: str,
    reason: str,
    changed_paths: Sequence[str],
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "perturbation": perturbation,
        "classification": classification,
        "equivalence_expected": classification == "equivalence",
        "reason": reason,
        "changed_paths": list(changed_paths),
        "snapshot": deepcopy(dict(snapshot)),
        "authority_effect": "none",
    }


def reverse_inventory_order(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    body = deepcopy(dict(snapshot))
    key, rows = _parts(body)
    if key is None:
        return _result(
            body,
            perturbation="reverse_inventory_order",
            classification="no_op",
            reason="Project snapshot contains no inventory collection.",
            changed_paths=[],
        )
    body[key] = list(reversed(rows))
    return _result(
        body,
        perturbation="reverse_inventory_order",
        classification="equivalence",
        reason="Inventory ordering is incidental; stable identities and engineering fields are unchanged.",
        changed_paths=[key],
    )


def rename_bound_part_label(
    snapshot: Mapping[str, Any],
    *,
    component_id: str,
    new_name: str,
) -> Dict[str, Any]:
    """Rename a part label and classify whether the change preserves identity evidence."""
    body = deepcopy(dict(snapshot))
    key, rows = _parts(body)
    if key is None:
        return _result(
            body,
            perturbation="rename_bound_part_label",
            classification="no_op",
            reason="Project snapshot contains no inventory collection.",
            changed_paths=[],
        )

    target_index = None
    for index, row in enumerate(rows):
        stable = str(row.get("component_id") or row.get("instance_id") or "").strip()
        if stable == component_id:
            target_index = index
            break
    if target_index is None:
        return _result(
            body,
            perturbation="rename_bound_part_label",
            classification="no_op",
            reason=f"No inventory row has stable component/instance ID {component_id!r}.",
            changed_paths=[],
        )

    row = rows[target_index]
    old_name = str(row.get("name") or "")
    anchor = _identity_anchor(row)
    row["name"] = str(new_name)
    rows[target_index] = row
    body[key] = rows

    # module_id/equivalent IDs/MPN/etc. preserve physical identity independently of the
    # display label. Without such an anchor, the name itself may be the only identity
    # evidence and a rename is therefore an evidence change, not an invariance test.
    if anchor:
        classification = "equivalence"
        reason = (
            f"Display label changed from {old_name!r} while persisted identity remains anchored by {anchor!r}."
        )
    else:
        classification = "evidence_change"
        reason = (
            f"Part has no persisted identity anchor besides its human-facing name; changing {old_name!r} may change physical identity evidence."
        )
    return _result(
        body,
        perturbation="rename_bound_part_label",
        classification=classification,
        reason=reason,
        changed_paths=[f"{key}[{target_index}].name"],
    )


def rename_donor_block_label(
    snapshot: Mapping[str, Any],
    *,
    block_id: str,
    new_name: str,
) -> Dict[str, Any]:
    """Rename donor display text while preserving stable block identity/capabilities."""
    body = deepcopy(dict(snapshot))
    changed: list[str] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if str(value.get("block_id") or "") == block_id:
                value["name"] = str(new_name)
                changed.append(f"{path}.name")
            for key, child in list(value.items()):
                visit(child, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(body, "snapshot")
    if not changed:
        return _result(
            body,
            perturbation="rename_donor_block_label",
            classification="no_op",
            reason=f"No donor functional block has stable block_id {block_id!r}.",
            changed_paths=[],
        )
    return _result(
        body,
        perturbation="rename_donor_block_label",
        classification="equivalence",
        reason="Donor block_id, function_type, capabilities, connector refs, and evidence remain unchanged; only display text changed.",
        changed_paths=changed,
    )


def remove_identity_field(
    snapshot: Mapping[str, Any],
    *,
    component_id: str,
    field: str,
) -> Dict[str, Any]:
    """Deliberately remove physical identity evidence; always classify as evidence change."""
    allowed = {
        "module_id",
        "catalog_module_id",
        "catalog_equivalent_id",
        "equivalent_module_id",
        "mpn",
        "part_number",
        "manufacturer_part_number",
        "sku",
        "model",
        "name",
    }
    if field not in allowed:
        raise ValueError(f"unsupported identity field for perturbation: {field}")
    body = deepcopy(dict(snapshot))
    key, rows = _parts(body)
    if key is None:
        return _result(
            body,
            perturbation="remove_identity_field",
            classification="no_op",
            reason="Project snapshot contains no inventory collection.",
            changed_paths=[],
        )
    changed: list[str] = []
    for index, row in enumerate(rows):
        stable = str(row.get("component_id") or row.get("instance_id") or "").strip()
        if stable != component_id:
            continue
        if field in row:
            row.pop(field, None)
            rows[index] = row
            changed.append(f"{key}[{index}].{field}")
        break
    body[key] = rows
    return _result(
        body,
        perturbation="remove_identity_field",
        classification="evidence_change" if changed else "no_op",
        reason=(
            "Physical identity evidence was deliberately removed; behavior/output drift must not be scored as equivalence instability."
            if changed
            else f"No matching field {field!r} was present on component {component_id!r}."
        ),
        changed_paths=changed,
    )
