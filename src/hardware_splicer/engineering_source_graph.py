"""Canonical source, claim, and conflict graph for source-agnostic engineering.

Public repositories, CAD, documents, media, measurements, telemetry, and operator
observations all enter the same graph.  The graph preserves provenance and authority
ceilings; it never upgrades a source claim merely because several sources repeat it.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .machine_project import AuthorityState


ENGINEERING_SOURCE_GRAPH_SCHEMA = "hardware_splicer.engineering_source_graph.v1"


class SourceType(str, Enum):
    REPOSITORY = "repository"
    RELEASE = "release"
    CAD = "cad"
    DRAWING = "drawing"
    SCHEMATIC = "schematic"
    PCB = "pcb"
    BOM = "bom"
    DATASHEET = "datasheet"
    MANUAL = "manual"
    PAPER = "paper"
    SERVICE_NOTE = "service_note"
    ISSUE = "issue"
    VIDEO = "video"
    PHOTO = "photo"
    MEASUREMENT = "measurement"
    TELEMETRY = "telemetry"
    TEST_LOG = "test_log"
    PROJECT_SNAPSHOT = "project_snapshot"
    OPERATOR_OBSERVATION = "operator_observation"
    USER_REQUIREMENT = "user_requirement"
    DONOR_INVENTORY = "donor_inventory"
    OTHER = "other"


class ConflictDisposition(str, Enum):
    UNRESOLVED = "unresolved"
    SELECTED = "selected"
    REJECTED = "rejected"
    BLOCKED_PENDING_MEASUREMENT = "blocked_pending_measurement"
    BLOCKED_PENDING_REVISION_SELECTION = "blocked_pending_revision_selection"
    ACCEPTED_VARIANT = "accepted_variant"


class SourceGraphModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SourceClaim(SourceGraphModel):
    claim_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: Any
    units: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    authority: AuthorityState = AuthorityState.DECLARED
    evidence_locator: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EngineeringSource(SourceGraphModel):
    source_id: str = Field(min_length=1)
    source_type: SourceType = SourceType.OTHER
    uri: str | None = None
    revision: str | None = None
    content_hash: str | None = None
    retrieved_at: str | None = None
    authority_ceiling: AuthorityState = AuthorityState.DECLARED
    claim_ids: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SourceConflict(SourceGraphModel):
    conflict_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    claim_ids: list[str] = Field(min_length=2)
    disposition: ConflictDisposition = ConflictDisposition.UNRESOLVED
    selected_claim_id: str | None = None
    reason: str = ""
    blocking: bool = True
    verification_target_ids: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def selected_claim_must_belong_to_conflict(self) -> "SourceConflict":
        if self.selected_claim_id and self.selected_claim_id not in self.claim_ids:
            raise ValueError("selected_claim_id must reference one of claim_ids")
        if self.disposition == ConflictDisposition.SELECTED and not self.selected_claim_id:
            raise ValueError("selected conflicts require selected_claim_id")
        return self


class EngineeringSourceGraph(SourceGraphModel):
    schema_version: str = ENGINEERING_SOURCE_GRAPH_SCHEMA
    sources: list[EngineeringSource] = Field(default_factory=list)
    claims: list[SourceClaim] = Field(default_factory=list)
    conflicts: list[SourceConflict] = Field(default_factory=list)
    unresolved_source_ids: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph_references(self) -> "EngineeringSourceGraph":
        source_ids = [row.source_id for row in self.sources]
        claim_ids = [row.claim_id for row in self.claims]
        conflict_ids = [row.conflict_id for row in self.conflicts]
        for label, values in (
            ("source", source_ids),
            ("claim", claim_ids),
            ("conflict", conflict_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} identifier")
        source_set = set(source_ids)
        claim_set = set(claim_ids)
        for claim in self.claims:
            if claim.source_id not in source_set:
                raise ValueError(f"claim {claim.claim_id!r} references unknown source {claim.source_id!r}")
            source = next(row for row in self.sources if row.source_id == claim.source_id)
            if _authority_rank(claim.authority) > _authority_rank(source.authority_ceiling):
                raise ValueError(
                    f"claim {claim.claim_id!r} exceeds source authority ceiling {source.authority_ceiling.value}"
                )
        for source in self.sources:
            missing = sorted(set(source.claim_ids) - claim_set)
            if missing:
                raise ValueError(f"source {source.source_id!r} references unknown claims: {missing}")
        for conflict in self.conflicts:
            missing = sorted(set(conflict.claim_ids) - claim_set)
            if missing:
                raise ValueError(f"conflict {conflict.conflict_id!r} references unknown claims: {missing}")
        return self

    @property
    def blocking_conflicts(self) -> list[SourceConflict]:
        return [row for row in self.conflicts if row.blocking]

    @property
    def source_provenance_complete(self) -> bool:
        return all(
            row.revision or row.content_hash or row.retrieved_at
            for row in self.sources
        )


_AUTHORITY_ORDER = {
    AuthorityState.UNKNOWN: 0,
    AuthorityState.PROPOSED: 1,
    AuthorityState.DECLARED: 2,
    AuthorityState.OBSERVED: 3,
    AuthorityState.MEASURED: 4,
    AuthorityState.VERIFIED: 5,
    AuthorityState.AUTHORIZED: 6,
}


def _authority_rank(value: AuthorityState) -> int:
    return _AUTHORITY_ORDER[value]


def _slug(value: str, fallback: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-._").lower()
    return result[:96] or fallback


def _stable_id(prefix: str, *values: Any) -> str:
    rendered = json.dumps(values, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _source_type(value: Any) -> SourceType:
    token = str(value or "other").strip().lower().replace("-", "_")
    aliases = {
        "repository_readme": SourceType.REPOSITORY,
        "github": SourceType.REPOSITORY,
        "repo": SourceType.REPOSITORY,
        "stl": SourceType.CAD,
        "step": SourceType.CAD,
        "urdf": SourceType.CAD,
        "datasheets": SourceType.DATASHEET,
        "logs": SourceType.TEST_LOG,
        "field_log": SourceType.TEST_LOG,
        "field_logs": SourceType.TEST_LOG,
        "observation": SourceType.OPERATOR_OBSERVATION,
    }
    if token in aliases:
        return aliases[token]
    try:
        return SourceType(token)
    except ValueError:
        return SourceType.OTHER


def _authority(value: Any, default: AuthorityState = AuthorityState.DECLARED) -> AuthorityState:
    try:
        return AuthorityState(str(value or default.value).strip().lower())
    except ValueError:
        return default


def _claim_from_value(
    source_id: str,
    value: Any,
    index: int,
    authority: AuthorityState,
) -> SourceClaim:
    if isinstance(value, Mapping):
        row = dict(value)
        subject_id = str(row.get("subject_id") or row.get("subject") or "machine")
        predicate = str(row.get("predicate") or row.get("field") or row.get("name") or "claim")
        claim_value = row.get("value", row.get("statement", row.get("claim")))
        claim_id = str(row.get("claim_id") or _stable_id("claim", source_id, subject_id, predicate, claim_value))
        requested_authority = _authority(row.get("authority"), authority)
        bounded_authority = requested_authority if _authority_rank(requested_authority) <= _authority_rank(authority) else authority
        locator = dict(row.get("evidence_locator") or {})
        for key in ("page", "line", "timestamp_start", "timestamp_end", "figure", "path"):
            if row.get(key) is not None:
                locator[key] = row[key]
        return SourceClaim(
            claim_id=claim_id,
            source_id=source_id,
            subject_id=subject_id,
            predicate=predicate,
            value=claim_value,
            units=row.get("units"),
            confidence=row.get("confidence"),
            authority=bounded_authority,
            evidence_locator=locator,
            metadata=dict(row.get("metadata") or {}),
        )
    statement = str(value)
    return SourceClaim(
        claim_id=_stable_id("claim", source_id, index, statement),
        source_id=source_id,
        subject_id="machine",
        predicate="statement",
        value=statement,
        authority=authority,
    )


def _source_from_mapping(row: Mapping[str, Any], index: int) -> tuple[EngineeringSource, list[SourceClaim]]:
    raw = dict(row)
    source_id = _slug(
        str(raw.get("source_id") or raw.get("id") or raw.get("name") or f"source-{index + 1}"),
        f"source-{index + 1}",
    )
    ceiling = _authority(raw.get("authority_ceiling"), AuthorityState.DECLARED)
    claims = [
        _claim_from_value(source_id, claim, claim_index, ceiling)
        for claim_index, claim in enumerate(raw.get("claims") or [])
    ]
    source = EngineeringSource(
        source_id=source_id,
        source_type=_source_type(raw.get("source_type") or raw.get("type")),
        uri=str(raw.get("uri") or raw.get("url") or raw.get("ref") or "").strip() or None,
        revision=str(raw.get("revision") or raw.get("version") or raw.get("commit_sha") or "").strip() or None,
        content_hash=str(raw.get("content_hash") or raw.get("checksum") or "").strip() or None,
        retrieved_at=str(raw.get("retrieved_at") or "").strip() or None,
        authority_ceiling=ceiling,
        claim_ids=[claim.claim_id for claim in claims],
        metadata={
            key: value
            for key, value in raw.items()
            if key
            not in {
                "source_id",
                "id",
                "name",
                "source_type",
                "type",
                "uri",
                "url",
                "ref",
                "revision",
                "version",
                "commit_sha",
                "content_hash",
                "checksum",
                "retrieved_at",
                "authority_ceiling",
                "claims",
            }
        },
    )
    return source, claims


def _declared_conflict(
    row: Mapping[str, Any],
    claims: list[SourceClaim],
    index: int,
) -> SourceConflict:
    raw = dict(row)
    conflict_id = _slug(str(raw.get("conflict_id") or raw.get("id") or f"conflict-{index + 1}"), f"conflict-{index + 1}")
    claim_ids = [str(value) for value in raw.get("claim_ids") or [] if value]
    synthetic: list[SourceClaim] = []
    if len(claim_ids) < 2:
        values = [raw.get("claim_a"), raw.get("claim_b")]
        for side, value in zip(("a", "b"), values):
            if value is None:
                continue
            claim = SourceClaim(
                claim_id=_stable_id("claim", "declared-conflict", conflict_id, side, value),
                source_id="declared-conflicts",
                subject_id=str(raw.get("subject_id") or "machine"),
                predicate=str(raw.get("predicate") or conflict_id),
                value=value,
                authority=AuthorityState.DECLARED,
                metadata={"synthetic_from_declared_conflict": True},
            )
            synthetic.append(claim)
            claim_ids.append(claim.claim_id)
        claims.extend(synthetic)
    selected = raw.get("selected_claim_id")
    disposition_value = str(raw.get("disposition") or "").strip().lower()
    if disposition_value:
        try:
            disposition = ConflictDisposition(disposition_value)
        except ValueError:
            disposition = ConflictDisposition.UNRESOLVED
    elif selected:
        disposition = ConflictDisposition.SELECTED
    else:
        disposition = ConflictDisposition.BLOCKED_PENDING_REVISION_SELECTION
    return SourceConflict(
        conflict_id=conflict_id,
        subject_id=str(raw.get("subject_id") or "machine"),
        predicate=str(raw.get("predicate") or conflict_id),
        claim_ids=claim_ids,
        disposition=disposition,
        selected_claim_id=str(selected) if selected else None,
        reason=str(raw.get("reason") or "Conflicting engineering claims require explicit disposition."),
        blocking=bool(raw.get("blocking", disposition not in {ConflictDisposition.SELECTED, ConflictDisposition.ACCEPTED_VARIANT})),
        verification_target_ids=[str(value) for value in raw.get("verification_target_ids") or []],
        metadata={key: value for key, value in raw.items() if key not in {"conflict_id", "id", "subject_id", "predicate", "claim_ids", "claim_a", "claim_b", "disposition", "selected_claim_id", "reason", "blocking", "verification_target_ids"}},
    )


def _auto_conflicts(claims: Sequence[SourceClaim]) -> list[SourceConflict]:
    grouped: dict[tuple[str, str], list[SourceClaim]] = {}
    for claim in claims:
        if claim.predicate == "statement":
            continue
        grouped.setdefault((claim.subject_id, claim.predicate), []).append(claim)
    conflicts: list[SourceConflict] = []
    for (subject_id, predicate), rows in grouped.items():
        rendered = {json.dumps(row.value, sort_keys=True, default=str) for row in rows}
        if len(rows) < 2 or len(rendered) < 2:
            continue
        conflicts.append(
            SourceConflict(
                conflict_id=_stable_id("conflict", subject_id, predicate, sorted(rendered)),
                subject_id=subject_id,
                predicate=predicate,
                claim_ids=[row.claim_id for row in rows],
                disposition=ConflictDisposition.BLOCKED_PENDING_MEASUREMENT,
                reason="Structured source claims disagree and require selection or measurement.",
                blocking=True,
            )
        )
    return conflicts


def build_engineering_source_graph(
    sources: Iterable[Mapping[str, Any] | str] | None,
    *,
    declared_conflicts: Iterable[Mapping[str, Any]] | None = None,
    unresolved_source_ids: Iterable[str] | None = None,
) -> EngineeringSourceGraph:
    source_rows: list[EngineeringSource] = []
    claims: list[SourceClaim] = []
    unresolved = [str(value) for value in unresolved_source_ids or [] if value]
    for index, value in enumerate(sources or []):
        if isinstance(value, Mapping):
            source, source_claims = _source_from_mapping(value, index)
            source_rows.append(source)
            claims.extend(source_claims)
        else:
            unresolved.append(str(value))

    if declared_conflicts:
        if not any(row.source_id == "declared-conflicts" for row in source_rows):
            source_rows.append(
                EngineeringSource(
                    source_id="declared-conflicts",
                    source_type=SourceType.USER_REQUIREMENT,
                    authority_ceiling=AuthorityState.DECLARED,
                    metadata={"purpose": "Conflict declarations supplied with engineering intake."},
                )
            )
        conflicts = [
            _declared_conflict(row, claims, index)
            for index, row in enumerate(declared_conflicts)
        ]
        declared_source = next(row for row in source_rows if row.source_id == "declared-conflicts")
        declared_source.claim_ids = [
            claim.claim_id for claim in claims if claim.source_id == "declared-conflicts"
        ]
    else:
        conflicts = []
    existing_conflict_claims = {claim_id for conflict in conflicts for claim_id in conflict.claim_ids}
    conflicts.extend(
        conflict
        for conflict in _auto_conflicts(claims)
        if not set(conflict.claim_ids).issubset(existing_conflict_claims)
    )
    return EngineeringSourceGraph(
        sources=source_rows,
        claims=claims,
        conflicts=conflicts,
        unresolved_source_ids=sorted(set(unresolved)),
        metadata={
            "authority_preserved_without_upgrade": True,
            "source_count": len(source_rows),
            "claim_count": len(claims),
            "blocking_conflict_count": sum(conflict.blocking for conflict in conflicts),
        },
    )
