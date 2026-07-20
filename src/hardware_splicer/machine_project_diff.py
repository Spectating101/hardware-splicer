"""Semantic diffs for canonical machine projects.

The diff is identity-aware rather than line-oriented. It highlights engineering
object additions/removals, field changes, and authority transitions so human or
agent edits can be reviewed before they replace a persisted project revision.
A diff never grants authority; it only reports what changed and which changes
require explicit review.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .machine_project import AuthorityState, MachineProject, RequirementKind


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class ReviewSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    REQUIRED = "required"


class DiffModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldChange(DiffModel):
    path: str
    before: Any = None
    after: Any = None


class ReviewFlag(DiffModel):
    code: str
    message: str
    severity: ReviewSeverity = ReviewSeverity.REQUIRED
    object_id: str | None = None
    path: str | None = None


class ObjectChange(DiffModel):
    collection: str
    object_id: str
    change_type: ChangeType
    field_changes: list[FieldChange] = Field(default_factory=list)
    review_flags: list[ReviewFlag] = Field(default_factory=list)
    before: Dict[str, Any] | None = None
    after: Dict[str, Any] | None = None

    @property
    def review_required(self) -> bool:
        return any(flag.severity == ReviewSeverity.REQUIRED for flag in self.review_flags)


class MachineProjectDiff(DiffModel):
    base_project_id: str
    candidate_project_id: str
    project_changes: list[FieldChange] = Field(default_factory=list)
    object_changes: list[ObjectChange] = Field(default_factory=list)
    review_flags: list[ReviewFlag] = Field(default_factory=list)

    @property
    def review_required(self) -> bool:
        return any(flag.severity == ReviewSeverity.REQUIRED for flag in self.review_flags) or any(
            change.review_required for change in self.object_changes
        )

    def summary(self) -> Dict[str, int | bool]:
        return {
            "added": sum(change.change_type == ChangeType.ADDED for change in self.object_changes),
            "removed": sum(change.change_type == ChangeType.REMOVED for change in self.object_changes),
            "modified": sum(change.change_type == ChangeType.MODIFIED for change in self.object_changes),
            "project_fields_changed": len(self.project_changes),
            "review_required": self.review_required,
        }


_COLLECTION_ID_FIELDS: tuple[tuple[str, str], ...] = (
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

_COLLECTION_LABELS = {
    "requirements": "requirement",
    "functions": "function",
    "subsystems": "subsystem",
    "components": "component",
    "interfaces": "interface",
    "constraints": "constraint",
    "verifications": "verification",
    "evidence": "evidence",
    "artifacts": "artifact",
}

_PROJECT_FIELDS = (
    "name",
    "purpose",
    "lifecycle_state",
    "requested_release_state",
    "discipline_payloads",
)

_AUTHORITY_ORDER = {
    AuthorityState.UNKNOWN.value: 0,
    AuthorityState.PROPOSED.value: 1,
    AuthorityState.DECLARED.value: 2,
    AuthorityState.OBSERVED.value: 3,
    AuthorityState.MEASURED.value: 4,
    AuthorityState.VERIFIED.value: 5,
    AuthorityState.AUTHORIZED.value: 6,
}


def _model_dict(value: Any, *, include_metadata: bool) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        body = value.model_dump(mode="json")
    elif isinstance(value, Mapping):
        body = dict(value)
    else:
        raise TypeError(f"cannot diff object of type {type(value).__name__}")
    if not include_metadata:
        body.pop("metadata", None)
    return body


def _identity_map(rows: Iterable[Any], id_field: str, *, include_metadata: bool) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        body = _model_dict(row, include_metadata=include_metadata)
        object_id = str(body[id_field])
        result[object_id] = body
    return result


def _flatten(value: Any, path: str = "") -> Dict[str, Any]:
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for key in sorted(value):
            child = f"{path}.{key}" if path else str(key)
            result.update(_flatten(value[key], child))
        if not value:
            result[path] = {}
        return result
    if isinstance(value, list):
        result: Dict[str, Any] = {}
        for index, row in enumerate(value):
            child = f"{path}[{index}]"
            result.update(_flatten(row, child))
        if not value:
            result[path] = []
        return result
    return {path: value}


def _field_changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[FieldChange]:
    left = _flatten(before)
    right = _flatten(after)
    changes: list[FieldChange] = []
    for path in sorted(set(left) | set(right)):
        if left.get(path) != right.get(path):
            changes.append(FieldChange(path=path, before=left.get(path), after=right.get(path)))
    return changes


def _authority_transitions(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
    *,
    collection: str,
    object_id: str,
) -> list[ReviewFlag]:
    if before is None or after is None:
        return []
    left = {path: value for path, value in _flatten(before).items() if path.endswith("authority")}
    right = {path: value for path, value in _flatten(after).items() if path.endswith("authority")}
    flags: list[ReviewFlag] = []
    for path in sorted(set(left) | set(right)):
        old = left.get(path)
        new = right.get(path)
        if old == new or old not in _AUTHORITY_ORDER or new not in _AUTHORITY_ORDER:
            continue
        if _AUTHORITY_ORDER[new] > _AUTHORITY_ORDER[old]:
            flags.append(
                ReviewFlag(
                    code="authority_escalation",
                    message=f"{collection} {object_id!r} escalates {path} from {old} to {new}",
                    object_id=object_id,
                    path=path,
                )
            )
        else:
            flags.append(
                ReviewFlag(
                    code="authority_regression",
                    message=f"{collection} {object_id!r} reduces {path} from {old} to {new}",
                    severity=ReviewSeverity.WARNING,
                    object_id=object_id,
                    path=path,
                )
            )
    return flags


def _object_review_flags(
    collection: str,
    object_id: str,
    change_type: ChangeType,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> list[ReviewFlag]:
    flags = _authority_transitions(
        before,
        after,
        collection=collection,
        object_id=object_id,
    )
    label = _COLLECTION_LABELS[collection]
    if change_type == ChangeType.REMOVED:
        if (
            collection == "requirements"
            and before is not None
            and before.get("kind") == RequirementKind.SAFETY.value
        ):
            flags.append(
                ReviewFlag(
                    code="safety_requirement_removed",
                    message=f"safety requirement {object_id!r} was removed",
                    object_id=object_id,
                )
            )
        elif collection in {"evidence", "verifications"}:
            flags.append(
                ReviewFlag(
                    code=f"{label}_removed",
                    message=f"{label} {object_id!r} was removed",
                    object_id=object_id,
                )
            )
    if change_type == ChangeType.ADDED and after is not None:
        authority_values = [
            value
            for path, value in _flatten(after).items()
            if path.endswith("authority") and value in _AUTHORITY_ORDER
        ]
        if any(
            _AUTHORITY_ORDER[value] >= _AUTHORITY_ORDER[AuthorityState.MEASURED.value]
            for value in authority_values
        ):
            flags.append(
                ReviewFlag(
                    code="trusted_object_added",
                    message=f"new {label} {object_id!r} enters with measured-or-higher authority",
                    object_id=object_id,
                )
            )
    return flags


def diff_machine_projects(
    base: MachineProject,
    candidate: MachineProject,
    *,
    include_metadata: bool = False,
) -> MachineProjectDiff:
    """Return an identity-aware semantic diff between two machine projects."""

    project_changes: list[FieldChange] = []
    base_body = base.model_dump(mode="json")
    candidate_body = candidate.model_dump(mode="json")
    for field in _PROJECT_FIELDS:
        if field == "discipline_payloads" and not include_metadata:
            continue
        if base_body.get(field) != candidate_body.get(field):
            project_changes.extend(
                _field_changes(
                    {field: base_body.get(field)},
                    {field: candidate_body.get(field)},
                )
            )

    review_flags: list[ReviewFlag] = []
    if base.requested_release_state != candidate.requested_release_state:
        review_flags.append(
            ReviewFlag(
                code="requested_release_state_changed",
                message=(
                    "requested release state changed from "
                    f"{base.requested_release_state.value} to {candidate.requested_release_state.value}"
                ),
                path="requested_release_state",
            )
        )
    if base.project_id != candidate.project_id:
        review_flags.append(
            ReviewFlag(
                code="project_identity_changed",
                message=f"project identity changed from {base.project_id!r} to {candidate.project_id!r}",
                path="project_id",
            )
        )

    object_changes: list[ObjectChange] = []
    for collection, id_field in _COLLECTION_ID_FIELDS:
        left = _identity_map(
            getattr(base, collection),
            id_field,
            include_metadata=include_metadata,
        )
        right = _identity_map(
            getattr(candidate, collection),
            id_field,
            include_metadata=include_metadata,
        )
        for object_id in sorted(set(left) | set(right)):
            before = left.get(object_id)
            after = right.get(object_id)
            if before is None:
                change_type = ChangeType.ADDED
                changes: list[FieldChange] = []
            elif after is None:
                change_type = ChangeType.REMOVED
                changes = []
            else:
                changes = _field_changes(before, after)
                if not changes:
                    continue
                change_type = ChangeType.MODIFIED
            object_changes.append(
                ObjectChange(
                    collection=collection,
                    object_id=object_id,
                    change_type=change_type,
                    field_changes=changes,
                    review_flags=_object_review_flags(
                        collection,
                        object_id,
                        change_type,
                        before,
                        after,
                    ),
                    before=before,
                    after=after,
                )
            )

    return MachineProjectDiff(
        base_project_id=base.project_id,
        candidate_project_id=candidate.project_id,
        project_changes=project_changes,
        object_changes=object_changes,
        review_flags=review_flags,
    )
