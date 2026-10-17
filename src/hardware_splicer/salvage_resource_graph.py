"""Read-only convergence projection over donor truth and server-owned lab capabilities.

The resource graph is intentionally not a persistence layer. Donor facts are
recomputed from project-local donor contracts plus canonical physical evidence by
``mission_donors.read_donors``. Lab resources come from the server-owned
fabrication capability registry. The graph makes those resources comparable by
stable ID without promoting, copying or authorizing anything.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from .donor_capability_families import project_donor_families, project_family_capability
from .fabrication_operator import FabricationValidationError
from .mission_donors import normalize_donors, read_donors
from .project_store import ProjectStore, validate_project_id

_DONOR_GRADES = (None, "agent_assertion", "re_observation", "document", "person_measurement")
_SAFE_CAPABILITY = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")


def build_salvage_resource_graph(
    *,
    project_store: ProjectStore,
    project_id: str,
    donor_references: Sequence[Mapping[str, Any]],
    fabrication_resources: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build the current graph directly from canonical owners; persist nothing."""
    if not isinstance(project_store, ProjectStore):
        raise FabricationValidationError("resource graph requires a project store")
    project = validate_project_id(project_id)
    try:
        references = normalize_donors(list(donor_references))
        donors = read_donors(project_store, project, references)
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError(str(exc)) from exc
    return project_salvage_resource_graph(
        project_id=project,
        donors=donors,
        fabrication_resources=fabrication_resources,
    )


def project_salvage_resource_graph(
    *,
    project_id: str,
    donors: Sequence[Mapping[str, Any]],
    fabrication_resources: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Pure projection helper used by tests and by the canonical API facade."""
    project = validate_project_id(project_id)
    if isinstance(donors, (str, bytes, bytearray)) or not isinstance(donors, Sequence):
        raise FabricationValidationError("donors must be a list")
    if isinstance(fabrication_resources, (str, bytes, bytearray)) or not isinstance(fabrication_resources, Sequence):
        raise FabricationValidationError("fabrication_resources must be a list")

    resources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, donor in enumerate(donors):
        resource = _donor_resource(donor, index=index)
        _append_unique(resources, seen, resource)
    for index, descriptor in enumerate(fabrication_resources):
        resource = _fabrication_resource(descriptor, index=index)
        _append_unique(resources, seen, resource)

    resources.sort(key=lambda row: (str(row["kind"]), str(row["resource_id"])))
    return {
        "schema": "hardware_splicer.salvage_resource_graph.v1",
        "project_id": project,
        "resources": resources,
        "resource_count": len(resources),
        "truth_contract": {
            "projection_only": True,
            "persists_independent_truth": False,
            "donor_truth_owner": "project_donor_contract_plus_canonical_physical_evidence",
            "lab_truth_owner": "server_fabrication_capability_registry",
            "capability_family_policy_is_evidence": False,
            "capability_family_policy_may_promote_evidence": False,
            "model_inference_is_physical_truth": False,
            "availability_grants_physical_authority": False,
        },
    }


def resource_index(graph: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Validate a resource graph enough for deterministic downstream consumption."""
    if not isinstance(graph, Mapping) or graph.get("schema") != "hardware_splicer.salvage_resource_graph.v1":
        raise FabricationValidationError("resource_graph has unsupported schema")
    rows = graph.get("resources")
    if not isinstance(rows, list) or len(rows) > 10000:
        raise FabricationValidationError("resource_graph.resources must be a bounded list")
    result: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise FabricationValidationError(f"resource_graph resource {index} must be an object")
        ident = _id(row.get("resource_id"), f"resource_graph resource {index} resource_id")
        if ident in result:
            raise FabricationValidationError("resource_graph resource ids must be unique")
        kind = row.get("kind")
        if kind not in {"donor", "lab_tool"}:
            raise FabricationValidationError("resource_graph contains unsupported resource kind")
        unresolved = row.get("unresolved_facts")
        if not isinstance(unresolved, list) or len(unresolved) > 10000 or any(not isinstance(value, str) for value in unresolved):
            raise FabricationValidationError("resource_graph unresolved_facts must be a bounded string list")
        if type(row.get("available")) is not bool:
            raise FabricationValidationError("resource_graph resource available must be boolean")
        result[ident] = row
    return result


def _donor_resource(raw: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise FabricationValidationError(f"donor {index} must be an object")
    ident = _id(raw.get("donor_id"), f"donor {index} donor_id")
    label = raw.get("label")
    if not isinstance(label, str) or not label.strip() or len(label) > 200:
        raise FabricationValidationError(f"donor {index} label must be bounded text")
    capabilities = raw.get("capabilities") or []
    if not isinstance(capabilities, list) or len(capabilities) > 128:
        raise FabricationValidationError("donor capabilities must be a bounded list")
    unresolved = raw.get("missing_facts") or []
    if not isinstance(unresolved, list) or len(unresolved) > 10000 or any(not isinstance(value, str) for value in unresolved):
        raise FabricationValidationError("donor missing_facts must be a bounded string list")
    unresolved = sorted(set(unresolved))
    contract_state = raw.get("contract_state")
    if contract_state not in {"unknown", "partial", "verified"}:
        raise FabricationValidationError("donor contract_state is unsupported")

    projected: list[dict[str, Any]] = []
    grades: list[str | None] = []
    for capability_index, capability in enumerate(capabilities):
        if not isinstance(capability, Mapping):
            raise FabricationValidationError("donor capability must be an object")
        role = capability.get("role")
        if not isinstance(role, str) or not role.strip() or len(role) > 200:
            raise FabricationValidationError("donor capability role must be bounded text")
        grade = capability.get("grade")
        if grade not in _DONOR_GRADES:
            raise FabricationValidationError("donor capability has unsupported evidence grade")
        grades.append(grade)
        entry: dict[str, Any] = {
            "capability_id": _semantic_capability_id(role),
            "role": role.strip(),
            "support": {"kind": "donor_evidence", "grade": grade},
        }
        family = project_family_capability(
            role=role,
            evidence_grade=grade,
            contract_state=contract_state,
            unresolved_facts=unresolved,
        )
        if family is not None:
            entry.update(
                family_id=family["family_id"],
                family_qualification=family["qualification"],
                planner_interface=family["planner_interface"],
            )
        projected.append(entry)

    weakest = min(grades, key=_DONOR_GRADES.index) if grades else None
    geometry = raw.get("planner_geometry")
    if geometry is not None and not isinstance(geometry, Mapping):
        raise FabricationValidationError("donor planner_geometry must be an object when present")
    family_projection = project_donor_families(raw)
    return {
        "resource_id": ident,
        "kind": "donor",
        "display_name": label.strip(),
        "capabilities": projected,
        "capability_families": family_projection,
        "support": {"kind": "donor_evidence", "weakest_grade": weakest},
        "contract_state": contract_state,
        "unresolved_facts": unresolved,
        "available": True,
        "usable_for_architecture": bool(projected) and contract_state != "unknown",
        "verified_for_ready": bool(projected) and contract_state == "verified" and not unresolved,
        "planner_geometry": dict(geometry) if geometry is not None else None,
        "source": {"kind": "mission_donor_projection", "donor_id": ident},
        "grants_physical_authority": False,
    }


def _fabrication_resource(raw: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise FabricationValidationError(f"fabrication resource {index} must be an object")
    operator_id = _id(raw.get("operator_id"), f"fabrication resource {index} operator_id")
    display = raw.get("display_name")
    if not isinstance(display, str) or not display.strip() or len(display) > 200:
        raise FabricationValidationError("fabrication resource display_name must be bounded text")
    capabilities = raw.get("capabilities")
    if not isinstance(capabilities, (list, tuple)) or not capabilities or len(capabilities) > 256:
        raise FabricationValidationError("fabrication resource capabilities must be a bounded non-empty list")
    projected = []
    for capability in capabilities:
        projected.append({
            "capability_id": _id(capability, "fabrication capability"),
            "support": {"kind": "server_configuration"},
        })
    available = raw.get("available")
    simulated = raw.get("simulated_only")
    if type(available) is not bool or type(simulated) is not bool:
        raise FabricationValidationError("fabrication resource availability fields must be boolean")
    return {
        "resource_id": f"operator:{operator_id}",
        "kind": "lab_tool",
        "display_name": display.strip(),
        "operator_kind": raw.get("kind"),
        "capabilities": projected,
        "support": {"kind": "server_configuration"},
        "limits": dict(raw.get("limits") or {}),
        "unresolved_facts": [],
        "available": available,
        "simulated_only": simulated,
        "source": {"kind": "fabrication_capability_registry", "operator_id": operator_id},
        "grants_physical_authority": False,
    }


def _append_unique(resources: list[dict[str, Any]], seen: set[str], resource: dict[str, Any]) -> None:
    ident = resource["resource_id"]
    if ident in seen:
        raise FabricationValidationError(f"duplicate convergence resource id: {ident}")
    seen.add(ident)
    resources.append(resource)


def _semantic_capability_id(role: str) -> str:
    candidate = "donor.role:" + role.strip().lower()
    if _SAFE_CAPABILITY.fullmatch(candidate):
        return candidate
    digest = hashlib.sha256(role.strip().encode("utf-8")).hexdigest()[:16]
    return f"donor.role:{digest}"


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned
