"""Audit whether downstream artifacts launder unresolved identity into concrete modules.

The physical-identity boundary can be correct while a later graph/firmware/mechanical/BOM
stage quietly reintroduces a familiar catalog part. This audit tracks concrete module
references through downstream package payloads and distinguishes:

- execution/firmware/graph references: must have trusted declared/exact/proposed provenance;
- mechanical references: review when a concrete catalog identity appears without provenance;
- BOM/procurement references: may be legitimate future design proposals, but must not be
  interpreted as existing inventory identity.

This is an outer-engineer evidence check, not a component-selection algorithm.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence


SCHEMA_VERSION = "hardware_splicer.identity_propagation_audit.v1"
_ALLOWED_IDENTITY_STATUSES = {"declared", "model_proposed", "proposed_design_component"}
_ALLOWED_IDENTITY_SOURCES = {
    "declared_catalog_identity",
    "model_identity_proposed",
    "donor_functional_salvage_declared",
    "workshop_design_proposal",
}
_REFERENCE_KEYS = {
    "module_id",
    "module_ids",
    "controller_module_id",
    "driver_module_id",
    "sensor_module_id",
    "power_module_id",
    "catalog_module_id",
    "replacement_module_id",
}


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_mapping(row) for row in value if _mapping(row)]


def _trusted_module_ids(package: Mapping[str, Any]) -> set[str]:
    trusted: set[str] = set()
    for row in _rows(package.get("resolved_modules")):
        module_id = str(row.get("module_id") or "").strip()
        if not module_id:
            continue
        status = str(row.get("identity_status") or "").strip()
        source = str(row.get("source") or "").strip()
        if status in _ALLOWED_IDENTITY_STATUSES and source in _ALLOWED_IDENTITY_SOURCES:
            trusted.add(module_id)
    return trusted


def _collect_refs(value: Any, *, path: str) -> list[Dict[str, str]]:
    refs: list[Dict[str, str]] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}" if path else key
            if key in _REFERENCE_KEYS:
                if isinstance(child, str) and child.strip():
                    refs.append({"path": child_path, "module_id": child.strip()})
                elif isinstance(child, Sequence) and not isinstance(child, (str, bytes, bytearray)):
                    for index, item in enumerate(child):
                        token = str(item or "").strip()
                        if token:
                            refs.append({"path": f"{child_path}[{index}]", "module_id": token})
            _collect = _collect_refs(child, path=child_path)
            refs.extend(_collect)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            refs.extend(_collect_refs(child, path=f"{path}[{index}]"))
    return refs


def _surface_report(
    package: Mapping[str, Any],
    *,
    field: str,
    severity: str,
    trusted: set[str],
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    value = package.get(field)
    if value is None:
        return [], []
    references = _collect_refs(value, path=field)
    unbound: list[Dict[str, Any]] = []
    for ref in references:
        if ref["module_id"] in trusted:
            continue
        unbound.append(
            {
                "code": "DOWNSTREAM_MODULE_WITHOUT_PROVENANCE",
                "surface": field,
                "path": ref["path"],
                "module_id": ref["module_id"],
                "severity": severity,
                "message": (
                    "Downstream artifact references a concrete catalog module that is not present in trusted declared/exact/proposed identity rows."
                ),
            }
        )
    return references, unbound


def audit_identity_propagation(package: Mapping[str, Any]) -> Dict[str, Any]:
    """Audit concrete module references downstream of physical-identity resolution."""
    body = dict(package or {})
    trusted = _trusted_module_ids(body)
    all_refs: list[Dict[str, Any]] = []
    findings: list[Dict[str, Any]] = []

    # These surfaces can directly shape execution or firmware and therefore require a
    # provenance-bearing module identity before a concrete catalog ID may appear.
    for field in ("graph_input", "firmware_scaffold", "bringup_card"):
        refs, rows = _surface_report(
            body,
            field=field,
            severity="blocking",
            trusted=trusted,
        )
        all_refs.extend(refs)
        findings.extend(rows)

    # Mechanical projection can remain candidate-only, but an unbound concrete catalog
    # identity should be surfaced for outer review rather than silently treated as fit.
    refs, rows = _surface_report(
        body,
        field="mechanism_pack",
        severity="review",
        trusted=trusted,
    )
    all_refs.extend(refs)
    findings.extend(rows)

    # BOM/procurement may legitimately introduce future proposed components. This is not
    # physical-inventory truth, so unbound IDs are review findings rather than hard failure.
    refs, rows = _surface_report(
        body,
        field="bom_estimate",
        severity="review",
        trusted=trusted,
    )
    all_refs.extend(refs)
    findings.extend(rows)

    blocking = [row for row in findings if row.get("severity") == "blocking"]
    review = [row for row in findings if row.get("severity") == "review"]
    status = "blocked" if blocking else "review" if review else "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "trusted_module_ids": sorted(trusted),
        "downstream_reference_count": len(all_refs),
        "finding_count": len(findings),
        "blocking_finding_count": len(blocking),
        "review_finding_count": len(review),
        "findings": findings,
        "checks": {
            "graph_identity_closed": not any(row.get("surface") == "graph_input" and row.get("severity") == "blocking" for row in findings),
            "firmware_identity_closed": not any(row.get("surface") == "firmware_scaffold" and row.get("severity") == "blocking" for row in findings),
            "bringup_identity_closed": not any(row.get("surface") == "bringup_card" and row.get("severity") == "blocking" for row in findings),
            "bom_proposals_distinguished_from_inventory": True,
            "proposal_correctness_judged": False,
        },
        "authority_effect": "none",
    }
