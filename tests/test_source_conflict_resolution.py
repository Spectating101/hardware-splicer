from __future__ import annotations

import pytest

from hardware_splicer.engineering_source_graph import (
    ConflictDisposition,
    build_engineering_source_graph,
)
from hardware_splicer.source_conflict_resolution import (
    ConflictDecision,
    apply_conflict_decisions,
    select_revision_boundary,
)


def _graph():
    return build_engineering_source_graph(
        [
            {
                "source_id": "legacy-model",
                "source_type": "cad",
                "revision": "v1",
                "claims": [
                    {
                        "claim_id": "legacy-voltage",
                        "subject_id": "main-battery",
                        "predicate": "nominal_voltage_v",
                        "value": 12,
                    }
                ],
            },
            {
                "source_id": "new-model",
                "source_type": "cad",
                "revision": "v2",
                "claims": [
                    {
                        "claim_id": "new-voltage",
                        "subject_id": "main-battery",
                        "predicate": "nominal_voltage_v",
                        "value": 24,
                    }
                ],
            },
        ]
    )


def test_explicit_claim_selection_closes_conflict_without_authority_upgrade() -> None:
    graph = _graph()
    conflict_id = graph.conflicts[0].conflict_id

    reviewed = apply_conflict_decisions(
        graph,
        [
            ConflictDecision(
                conflict_id=conflict_id,
                disposition=ConflictDisposition.SELECTED,
                selected_claim_id="new-voltage",
                reason="The v2 CAD and measured harness both use the 24 V architecture.",
                reviewer="integration-reviewer",
                reviewed_at="2026-08-04T01:30:00+08:00",
            )
        ],
    )

    assert reviewed.blocking_conflicts == []
    conflict = reviewed.conflicts[0]
    assert conflict.selected_claim_id == "new-voltage"
    assert conflict.blocking is False
    assert conflict.metadata["reviewer"] == "integration-reviewer"
    assert next(row for row in reviewed.claims if row.claim_id == "new-voltage").authority.value == "declared"
    assert reviewed.metadata["blocking_conflict_count"] == 0


def test_selected_claim_must_belong_to_conflict() -> None:
    graph = _graph()
    with pytest.raises(ValueError, match="does not belong"):
        apply_conflict_decisions(
            graph,
            [
                {
                    "conflict_id": graph.conflicts[0].conflict_id,
                    "disposition": "selected",
                    "selected_claim_id": "not-a-claim",
                    "reason": "invalid test decision",
                }
            ],
        )


def test_revision_boundary_resolves_only_unambiguous_selected_source() -> None:
    graph = _graph()

    selected = select_revision_boundary(
        graph,
        {
            "selected_source_ids": ["new-model"],
            "reason": "Use the complete v2 electrical and mechanical revision.",
            "reviewer": "system-engineer",
        },
    )

    assert selected.blocking_conflicts == []
    assert selected.conflicts[0].selected_claim_id == "new-voltage"
    assert selected.metadata["revision_boundary"]["selected_source_ids"] == ["new-model"]

    ambiguous = select_revision_boundary(
        graph,
        {
            "selected_source_ids": ["legacy-model", "new-model"],
            "reason": "Attempt to combine both revisions.",
        },
    )
    assert len(ambiguous.blocking_conflicts) == 1
    assert ambiguous.conflicts[0].disposition == ConflictDisposition.BLOCKED_PENDING_REVISION_SELECTION


def test_revision_boundary_rejects_unknown_sources() -> None:
    with pytest.raises(ValueError, match="unknown source"):
        select_revision_boundary(
            _graph(),
            {
                "selected_source_ids": ["missing-source"],
                "reason": "invalid boundary",
            },
        )
