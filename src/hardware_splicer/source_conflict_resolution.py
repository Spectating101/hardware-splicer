"""Explicit review decisions for engineering-source conflicts and revision boundaries."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .engineering_source_graph import (
    ConflictDisposition,
    EngineeringSourceGraph,
    SourceConflict,
)


CONFLICT_REVIEW_SCHEMA = "hardware_splicer.source_conflict_review.v1"


class ConflictReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ConflictDecision(ConflictReviewModel):
    conflict_id: str = Field(min_length=1)
    disposition: ConflictDisposition
    selected_claim_id: str | None = None
    reason: str = Field(min_length=1)
    reviewer: str | None = None
    reviewed_at: str | None = None
    verification_target_ids: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def selected_disposition_requires_claim(self) -> "ConflictDecision":
        if self.disposition == ConflictDisposition.SELECTED and not self.selected_claim_id:
            raise ValueError("selected disposition requires selected_claim_id")
        return self


class RevisionBoundarySelection(ConflictReviewModel):
    selected_source_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)
    reviewer: str | None = None
    reviewed_at: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _blocking(disposition: ConflictDisposition) -> bool:
    return disposition not in {
        ConflictDisposition.SELECTED,
        ConflictDisposition.ACCEPTED_VARIANT,
    }


def apply_conflict_decisions(
    graph: EngineeringSourceGraph,
    decisions: Iterable[ConflictDecision | Mapping[str, Any]],
) -> EngineeringSourceGraph:
    """Apply explicit, audited decisions without upgrading claim authority."""

    rows = {row.conflict_id: row.model_copy(deep=True) for row in graph.conflicts}
    decision_log = list(graph.metadata.get("conflict_decisions") or [])
    for value in decisions:
        decision = value if isinstance(value, ConflictDecision) else ConflictDecision.model_validate(value)
        if decision.conflict_id not in rows:
            raise ValueError(f"unknown conflict_id: {decision.conflict_id}")
        current = rows[decision.conflict_id]
        if decision.selected_claim_id and decision.selected_claim_id not in current.claim_ids:
            raise ValueError(
                f"selected claim {decision.selected_claim_id!r} does not belong to conflict {decision.conflict_id!r}"
            )
        rows[decision.conflict_id] = SourceConflict(
            **{
                **current.model_dump(mode="python"),
                "disposition": decision.disposition,
                "selected_claim_id": decision.selected_claim_id,
                "reason": decision.reason,
                "blocking": _blocking(decision.disposition),
                "verification_target_ids": decision.verification_target_ids or current.verification_target_ids,
                "metadata": {
                    **current.metadata,
                    "reviewer": decision.reviewer,
                    "reviewed_at": decision.reviewed_at,
                    "decision_metadata": decision.metadata,
                    "review_schema": CONFLICT_REVIEW_SCHEMA,
                },
            }
        )
        decision_log.append(decision.model_dump(mode="json"))
    metadata = dict(graph.metadata)
    metadata.update(
        {
            "conflict_decisions": decision_log,
            "blocking_conflict_count": sum(row.blocking for row in rows.values()),
            "conflict_review_schema": CONFLICT_REVIEW_SCHEMA,
        }
    )
    return graph.model_copy(update={"conflicts": list(rows.values()), "metadata": metadata}, deep=True)


def select_revision_boundary(
    graph: EngineeringSourceGraph,
    selection: RevisionBoundarySelection | Mapping[str, Any],
) -> EngineeringSourceGraph:
    """Select a coherent source boundary and auto-resolve only unambiguous conflicts."""

    boundary = selection if isinstance(selection, RevisionBoundarySelection) else RevisionBoundarySelection.model_validate(selection)
    known_sources = {row.source_id for row in graph.sources}
    unknown = sorted(set(boundary.selected_source_ids) - known_sources)
    if unknown:
        raise ValueError(f"unknown source IDs in revision boundary: {unknown}")
    claim_by_id = {row.claim_id: row for row in graph.claims}
    decisions: list[ConflictDecision] = []
    for conflict in graph.conflicts:
        selected_claims = [
            claim_id
            for claim_id in conflict.claim_ids
            if claim_id in claim_by_id
            and claim_by_id[claim_id].source_id in boundary.selected_source_ids
        ]
        if len(selected_claims) == 1:
            decisions.append(
                ConflictDecision(
                    conflict_id=conflict.conflict_id,
                    disposition=ConflictDisposition.SELECTED,
                    selected_claim_id=selected_claims[0],
                    reason=f"Selected by coherent source boundary: {boundary.reason}",
                    reviewer=boundary.reviewer,
                    reviewed_at=boundary.reviewed_at,
                    metadata={"selected_source_ids": boundary.selected_source_ids},
                )
            )
        elif len(selected_claims) > 1:
            decisions.append(
                ConflictDecision(
                    conflict_id=conflict.conflict_id,
                    disposition=ConflictDisposition.BLOCKED_PENDING_REVISION_SELECTION,
                    reason="The selected source boundary still contains multiple conflicting claims.",
                    reviewer=boundary.reviewer,
                    reviewed_at=boundary.reviewed_at,
                    metadata={"selected_source_ids": boundary.selected_source_ids},
                )
            )
        else:
            decisions.append(
                ConflictDecision(
                    conflict_id=conflict.conflict_id,
                    disposition=ConflictDisposition.BLOCKED_PENDING_MEASUREMENT,
                    reason="The selected boundary contains no claim that resolves this conflict.",
                    reviewer=boundary.reviewer,
                    reviewed_at=boundary.reviewed_at,
                    metadata={"selected_source_ids": boundary.selected_source_ids},
                )
            )
    resolved = apply_conflict_decisions(graph, decisions)
    metadata = dict(resolved.metadata)
    metadata["revision_boundary"] = {
        "schema_version": CONFLICT_REVIEW_SCHEMA,
        **boundary.model_dump(mode="json"),
    }
    return resolved.model_copy(update={"metadata": metadata}, deep=True)
