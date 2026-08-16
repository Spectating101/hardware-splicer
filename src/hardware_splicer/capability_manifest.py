"""Revisioned capability manifests for measured platform reuse.

A capability manifest freezes the dependency identities that make a validated
hardware/software capability what it is. Comparing a baseline and candidate
manifest produces an explicit change set for the evidence-impact engine.

The diff is intentionally syntactic over canonical persisted dependency payloads.
It does not ask an LLM whether two parts are 'basically equivalent'. If callers
want to preserve evidence across a replacement they must represent the stable
contract explicitly and separately from the changed implementation identity.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

CAPABILITY_MANIFEST_SCHEMA = "hardware_splicer.capability_manifest.v1"
CAPABILITY_DIFF_SCHEMA = "hardware_splicer.capability_manifest_diff.v1"


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
        },
    }
