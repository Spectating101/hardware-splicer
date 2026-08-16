"""Revisioned capability manifests for measured platform reuse.

A capability manifest freezes the dependency identities that make a validated
hardware/software capability what it is. Comparing a baseline and candidate
manifest produces an explicit change set for the evidence-impact engine.

The diff is intentionally syntactic over canonical persisted dependency payloads.
It does not ask an LLM whether two parts are 'basically equivalent'. If callers
want to preserve evidence across a replacement they must represent the stable
contract explicitly and separately from the changed implementation identity.

Where a Hardware-Splicer ``MachineProject`` already exists, use
``project_capability_manifest`` so the manifest is a revision-bound projection of
canonical project objects rather than a second independently edited truth store.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .machine_project import MachineProject

CAPABILITY_MANIFEST_SCHEMA = "hardware_splicer.capability_manifest.v1"
CAPABILITY_DIFF_SCHEMA = "hardware_splicer.capability_manifest_diff.v1"

_PROJECT_COLLECTIONS: tuple[tuple[str, str], ...] = (
    ("requirements", "requirement_id"),
    ("functions", "function_id"),
    ("subsystems", "subsystem_id"),
    ("components", "component_id"),
    ("interfaces", "interface_id"),
    ("constraints", "constraint_id"),
    ("verifications", "verification_id"),
    ("evidence", "evidence_id"),
    ("artifacts", "artifact_id"),
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _dependency_rows(manifest: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    rows = manifest.get("dependencies")
    if not isinstance(rows, list):
        return {}, ["dependencies_must_be_list"]

    by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            errors.append(f"dependency_{index}_must_be_mapping")
            continue
        row = deepcopy(dict(raw))
        dependency_id = str(row.get("dependency_id") or "").strip()
        if not dependency_id:
            errors.append(f"dependency_{index}_missing_id")
            continue
        if dependency_id in by_id:
            errors.append(f"duplicate_dependency_id:{dependency_id}")
            continue
        resolved = row.get("resolved") is not False
        row["dependency_id"] = dependency_id
        row["resolved"] = resolved
        # These fields describe record bookkeeping rather than the engineering
        # dependency itself and therefore do not change its semantic fingerprint.
        semantic = {
            key: value
            for key, value in row.items()
            if key not in {"dependency_id", "notes", "captured_at", "source_refs"}
        }
        row["semantic_fingerprint"] = _fingerprint(semantic)
        by_id[dependency_id] = row
    return by_id, errors


def _project_object_index(project: MachineProject) -> dict[str, tuple[str, Any]]:
    index: dict[str, tuple[str, Any]] = {project.project_id: ("project", project)}
    for collection_name, field_name in _PROJECT_COLLECTIONS:
        for row in getattr(project, collection_name):
            index[str(getattr(row, field_name))] = (collection_name, row)
    return index


def _project_artifact_hashes(project: MachineProject) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for artifact in project.artifacts:
        content_hash = artifact.metadata.get("content_hash")
        if content_hash:
            hashes[artifact.artifact_id] = str(content_hash)
    return hashes


def project_capability_manifest(
    project: MachineProject,
    *,
    capability_id: str,
    revision: str,
    project_revision: str,
    dependency_specs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Project explicit canonical MachineProject objects into a capability manifest.

    ``dependency_specs`` deliberately requires callers to select the source object
    and declare whether dependency coverage is resolved. The adapter copies the
    engineering value from MachineProject; it does not infer semantic equivalence,
    choose hidden dependencies, or upgrade authority.
    """

    if not str(capability_id).strip():
        raise ValueError("capability_id is required")
    if not str(revision).strip():
        raise ValueError("revision is required")
    if not str(project_revision).strip():
        raise ValueError("project_revision is required")

    index = _project_object_index(project)
    dependencies: list[dict[str, Any]] = []
    selected_object_ids: list[str] = []
    seen_dependency_ids: set[str] = set()

    for position, raw_spec in enumerate(dependency_specs):
        spec = dict(raw_spec)
        object_id = str(spec.get("object_id") or "").strip()
        if not object_id:
            raise ValueError(f"dependency_specs[{position}] has no object_id")
        if object_id not in index:
            raise ValueError(f"dependency_specs[{position}] references unknown MachineProject object {object_id!r}")
        dependency_id = str(spec.get("dependency_id") or f"machine:{object_id}").strip()
        if dependency_id in seen_dependency_ids:
            raise ValueError(f"duplicate dependency_id {dependency_id!r}")
        seen_dependency_ids.add(dependency_id)

        collection_name, source_object = index[object_id]
        source_payload = source_object.model_dump(mode="json")
        authority = source_payload.get("authority")
        dependencies.append(
            {
                "dependency_id": dependency_id,
                "kind": str(spec.get("kind") or f"machine_project:{collection_name}"),
                "resolved": spec.get("resolved") is True,
                "authority": authority,
                "value": source_payload,
                "source_object_id": object_id,
                "source_collection": collection_name,
                "source_refs": [
                    f"machine_project:{project.project_id}@{project_revision}:{object_id}"
                ],
                "notes": spec.get("notes"),
            }
        )
        selected_object_ids.append(object_id)

    return {
        "schema_version": CAPABILITY_MANIFEST_SCHEMA,
        "capability_id": str(capability_id),
        "revision": str(revision),
        "status": "machine_project_projection",
        "source_boundary": {
            "project_id": project.project_id,
            "project_revision": str(project_revision),
            "machine_project_schema": project.schema_version,
            "lifecycle_state": project.lifecycle_state.value,
            "requested_release_state": project.requested_release_state.value,
            "selected_object_ids": selected_object_ids,
            "project_artifact_hashes": _project_artifact_hashes(project),
        },
        "dependencies": dependencies,
        "metadata": {
            "alternate_engineering_truth_store": False,
            "projection_only": True,
            "semantic_equivalence_inferred": False,
        },
    }


def validate_capability_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the minimum identity/revision/dependency contract."""

    errors: list[str] = []
    if manifest.get("schema_version") != CAPABILITY_MANIFEST_SCHEMA:
        errors.append("unsupported_schema_version")
    capability_id = str(manifest.get("capability_id") or "").strip()
    revision = str(manifest.get("revision") or "").strip()
    if not capability_id:
        errors.append("missing_capability_id")
    if not revision:
        errors.append("missing_revision")
    dependencies, dependency_errors = _dependency_rows(manifest)
    errors.extend(dependency_errors)
    return {
        "valid": not errors,
        "validation_errors": errors,
        "capability_id": capability_id,
        "revision": revision,
        "dependency_count": len(dependencies),
        "source_boundary_present": isinstance(manifest.get("source_boundary"), Mapping),
        "unresolved_dependency_ids": sorted(
            dependency_id
            for dependency_id, row in dependencies.items()
            if not row["resolved"]
        ),
    }


def diff_capability_manifests(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare two frozen capability manifests without equivalence guessing."""

    baseline_check = validate_capability_manifest(baseline)
    candidate_check = validate_capability_manifest(candidate)
    errors = [
        *(f"baseline:{value}" for value in baseline_check["validation_errors"]),
        *(f"candidate:{value}" for value in candidate_check["validation_errors"]),
    ]
    if (
        baseline_check["capability_id"]
        and candidate_check["capability_id"]
        and baseline_check["capability_id"] != candidate_check["capability_id"]
    ):
        errors.append("capability_id_mismatch")

    baseline_rows, _ = _dependency_rows(baseline)
    candidate_rows, _ = _dependency_rows(candidate)
    baseline_ids = set(baseline_rows)
    candidate_ids = set(candidate_rows)

    added = sorted(candidate_ids - baseline_ids)
    removed = sorted(baseline_ids - candidate_ids)
    common = sorted(baseline_ids & candidate_ids)
    changed: list[str] = []
    unchanged: list[str] = []
    unresolved: list[str] = []

    for dependency_id in common:
        candidate_row = candidate_rows[dependency_id]
        if not candidate_row["resolved"]:
            unresolved.append(dependency_id)
            continue
        baseline_row = baseline_rows[dependency_id]
        if not baseline_row["resolved"]:
            # A previously unresolved dependency becoming resolved is still a
            # dependency-state change and cannot inherit old validation by default.
            changed.append(dependency_id)
        elif baseline_row["semantic_fingerprint"] != candidate_row["semantic_fingerprint"]:
            changed.append(dependency_id)
        else:
            unchanged.append(dependency_id)

    unresolved.extend(
        dependency_id
        for dependency_id in added
        if not candidate_rows[dependency_id]["resolved"]
    )
    added_resolved = sorted(set(added) - set(unresolved))

    # Removed dependencies invalidate anything that depended on them. Added
    # resolved dependencies are changes in capability state, though inherited
    # evidence will only be affected when it explicitly depends on those ids.
    changed_dependency_ids = sorted(set(changed) | set(removed) | set(added_resolved))
    unresolved_dependency_ids = sorted(set(unresolved))

    return {
        "schema_version": CAPABILITY_DIFF_SCHEMA,
        "status": "invalid" if errors else "evaluated",
        "validation_errors": errors,
        "capability_id": baseline_check["capability_id"] or candidate_check["capability_id"],
        "baseline_revision": baseline_check["revision"],
        "candidate_revision": candidate_check["revision"],
        "changed_dependency_ids": changed_dependency_ids,
        "unresolved_dependency_ids": unresolved_dependency_ids,
        "added_dependency_ids": added,
        "removed_dependency_ids": removed,
        "changed_common_dependency_ids": sorted(changed),
        "unchanged_dependency_ids": unchanged,
        "metadata": {
            "semantic_equivalence_inferred": False,
            "identity_or_contract_change_requires_explicit_representation": True,
            "baseline_source_boundary_present": baseline_check["source_boundary_present"],
            "candidate_source_boundary_present": candidate_check["source_boundary_present"],
        },
    }
