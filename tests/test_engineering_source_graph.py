from __future__ import annotations

import pytest

from hardware_splicer.engineering_source_graph import (
    ConflictDisposition,
    build_engineering_source_graph,
)
from hardware_splicer.machine_project import AuthorityState


def test_structured_claim_disagreement_becomes_blocking_conflict() -> None:
    graph = build_engineering_source_graph(
        [
            {
                "source_id": "manual-v1",
                "source_type": "manual",
                "uri": "docs://robot/v1",
                "revision": "v1",
                "authority_ceiling": "declared",
                "claims": [
                    {
                        "subject_id": "main-battery",
                        "predicate": "nominal_voltage_v",
                        "value": 12.0,
                    }
                ],
            },
            {
                "source_id": "schematic-v2",
                "source_type": "schematic",
                "uri": "design://robot/v2.kicad_sch",
                "content_hash": "sha256:abc",
                "authority_ceiling": "declared",
                "claims": [
                    {
                        "subject_id": "main-battery",
                        "predicate": "nominal_voltage_v",
                        "value": 24.0,
                    }
                ],
            },
        ]
    )

    assert graph.source_provenance_complete is True
    assert len(graph.sources) == 2
    assert len(graph.claims) == 2
    assert len(graph.blocking_conflicts) == 1
    conflict = graph.blocking_conflicts[0]
    assert conflict.subject_id == "main-battery"
    assert conflict.predicate == "nominal_voltage_v"
    assert conflict.disposition == ConflictDisposition.BLOCKED_PENDING_MEASUREMENT


def test_claim_authority_is_capped_by_source_ceiling() -> None:
    graph = build_engineering_source_graph(
        [
            {
                "source_id": "assembly-video",
                "source_type": "video",
                "revision": "video-id-123",
                "authority_ceiling": "observed",
                "claims": [
                    {
                        "claim_id": "visible-servo-orientation",
                        "subject_id": "front-left-knee-actuator",
                        "predicate": "output_shaft_orientation",
                        "value": "inward",
                        "authority": "verified",
                        "timestamp_start": 521.0,
                        "timestamp_end": 537.0,
                    }
                ],
            }
        ]
    )

    claim = graph.claims[0]
    assert claim.authority == AuthorityState.OBSERVED
    assert claim.evidence_locator["timestamp_start"] == 521.0
    assert claim.evidence_locator["timestamp_end"] == 537.0


def test_declared_conflicts_get_explicit_blocked_disposition() -> None:
    graph = build_engineering_source_graph(
        [
            {
                "source_id": "legacy-repo",
                "source_type": "repository",
                "revision": "legacy",
                "authority_ceiling": "declared",
                "claims": ["PWM servo actuation"],
            },
            {
                "source_id": "new-announcement",
                "source_type": "release",
                "revision": "v3-preview",
                "authority_ceiling": "declared",
                "claims": ["brushless actuation"],
            },
        ],
        declared_conflicts=[
            {
                "conflict_id": "actuator-family",
                "claim_a": "PWM servo",
                "claim_b": "brushless motor controller",
            }
        ],
    )

    assert len(graph.conflicts) == 1
    conflict = graph.conflicts[0]
    assert conflict.conflict_id == "actuator-family"
    assert conflict.blocking is True
    assert conflict.disposition == ConflictDisposition.BLOCKED_PENDING_REVISION_SELECTION
    assert len(conflict.claim_ids) == 2
    assert all(claim.source_id == "declared-conflicts" for claim in graph.claims if claim.claim_id in conflict.claim_ids)


def test_selected_conflict_must_reference_member_claim() -> None:
    with pytest.raises(ValueError, match="selected_claim_id"):
        build_engineering_source_graph(
            [
                {
                    "source_id": "source-a",
                    "source_type": "manual",
                    "revision": "v1",
                    "claims": [
                        {
                            "claim_id": "claim-a",
                            "subject_id": "motor",
                            "predicate": "model",
                            "value": "A",
                        }
                    ],
                },
                {
                    "source_id": "source-b",
                    "source_type": "manual",
                    "revision": "v2",
                    "claims": [
                        {
                            "claim_id": "claim-b",
                            "subject_id": "motor",
                            "predicate": "model",
                            "value": "B",
                        }
                    ],
                },
            ],
            declared_conflicts=[
                {
                    "conflict_id": "motor-model",
                    "claim_ids": ["claim-a", "claim-b"],
                    "disposition": "selected",
                    "selected_claim_id": "claim-c",
                }
            ],
        )
