"""Compatibility boundary for durable project envelopes.

The filesystem store deliberately remains small and strict. This module wraps its
envelope validation so schema evolution is explicit, deterministic, and testable
without weakening path, revision, or corruption checks.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .project_store import CorruptProject, PROJECT_STORE_SCHEMA, ProjectStore

LEGACY_UNVERSIONED_SCHEMA = "legacy_unversioned_project_snapshot"


class UnsupportedProjectSchema(ValueError):
    """Raised when a project uses a schema this build cannot safely consume."""

    def __init__(self, schema_version: object) -> None:
        self.schema_version = schema_version
        super().__init__(
            f"unsupported project snapshot schema {schema_version!r}; "
            f"this build supports {PROJECT_STORE_SCHEMA!r} and deterministic "
            "migration from unversioned legacy envelopes"
        )


def migrate_project_envelope(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a current-schema envelope without mutating the input.

    Current v1 envelopes pass through byte-for-byte at the data-model level. The
    only supported legacy form is an otherwise complete envelope that predates the
    top-level ``schema_version`` field. Unknown top-level, snapshot, and metadata
    fields are preserved. Unknown named schemas fail closed rather than being
    treated as corrupt JSON or silently rewritten. Malformed unversioned envelopes
    remain ordinary corruption so the mature revision-recovery path can recover an
    older valid snapshot.
    """

    value = dict(envelope)
    schema_version = value.get("schema_version")
    if schema_version == PROJECT_STORE_SCHEMA:
        return value
    if schema_version not in (None, ""):
        raise UnsupportedProjectSchema(schema_version)

    required = {"project_id", "revision", "snapshot"}
    missing = sorted(field for field in required if field not in value)
    if missing:
        raise CorruptProject(
            "legacy project envelope is missing required fields: " + ", ".join(missing)
        )
    if not isinstance(value.get("snapshot"), Mapping):
        raise CorruptProject("legacy project snapshot must be an object")

    metadata = value.get("metadata")
    if metadata is None:
        migrated_metadata: Dict[str, Any] = {}
    elif isinstance(metadata, Mapping):
        migrated_metadata = dict(metadata)
    else:
        raise CorruptProject("legacy project metadata must be an object")

    migrated_metadata["project_store_migration"] = {
        "source_schema": LEGACY_UNVERSIONED_SCHEMA,
        "target_schema": PROJECT_STORE_SCHEMA,
    }
    value["schema_version"] = PROJECT_STORE_SCHEMA
    value["snapshot"] = dict(value["snapshot"])
    value["metadata"] = migrated_metadata
    return value


class CompatibleProjectStore(ProjectStore):
    """Project store with explicit envelope migration and future-schema refusal."""

    def _validate_envelope(
        self,
        project_id: str,
        revision: int,
        envelope: Dict[str, Any],
    ) -> Dict[str, Any]:
        migrated = migrate_project_envelope(envelope)
        return super()._validate_envelope(project_id, revision, migrated)
