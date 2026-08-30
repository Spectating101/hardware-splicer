from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from hardware_splicer.mechanical_brep_mating import (
    BrepMatingAnchor,
    BrepMatingRequirements,
    BrepMatingStatus,
    evaluate_brep_anchor_mating,
)


def _anchor(
    anchor_id: str,
    object_id: str,
    point: tuple[float, float, float],
    normal: tuple[float, float, float],
    *,
    interface_id: str = "if-display",
    frame_id: str = "assembly",
    hash_char: str = "a",
) -> BrepMatingAnchor:
    return BrepMatingAnchor(
        anchor_id=anchor_id,
        interface_id=interface_id,
        object_id=object_id,
        source_id=f"{object_id}.step",
        model_id=f"model-{object_id}",
        content_hash=f"sha256:{hash_char * 64}",
        placement_id=f"place-{object_id}",
        frame_id=frame_id,
        anchor_point_mm=point,
        outward_normal=normal,
        face_index=2,
        face_geom_type="PLANE",
        authority="declared",
        status="ready",
        kernel_surface_snap=True,
        connector_mating_verified=False,
        physical_measurement=False,
        fabrication_authorized=False,
    )


def test_exact_anchor_pair_passes_declared_geometric_tolerances() -> None:
    report = evaluate_brep_anchor_mating(
        project_id="deck-001",
        mating_id="mate-display",
        first=_anchor("anchor-board", "board", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        second=_anchor("anchor-display", "display", (0.2, 0.1, 0.0), (-1.0, 0.0, 0.0), hash_char="b"),
    )

    assert report.status is BrepMatingStatus.READY
    assert report.geometric_mating_passed is True
    assert report.normal_opposition_error_deg == pytest.approx(0.0)
    assert report.normal_opposition_passed is True
    assert report.signed_axial_offset_mm == pytest.approx(0.2)
    assert report.axial_offset_error_mm == pytest.approx(0.2)
    assert report.axial_offset_passed is True
    assert report.lateral_offset_mm == pytest.approx(0.1)
    assert report.lateral_offset_passed is True
    assert report.mating_axis == pytest.approx((1.0, 0.0, 0.0))
    assert report.mating_axis_source == "first_anchor_normal"
    assert report.coaxiality_evaluated is False
    assert report.metadata["connector_mating_verified"] is False
    assert report.metadata["swept_engagement_collision"] is False
    assert report.metadata["fabrication_authorized"] is False


def test_declared_mating_axis_enables_coaxial_offset_and_axis_alignment() -> None:
    report = evaluate_brep_anchor_mating(
        project_id="deck-001",
        mating_id="mate-axis",
        first=_anchor("a", "one", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        second=_anchor("b", "two", (0.25, 0.2, 0.0), (-1.0, 0.0, 0.0), hash_char="b"),
        requirements=BrepMatingRequirements(
            declared_mating_axis=(10.0, 0.0, 0.0),
            max_lateral_offset_mm=0.25,
            target_axial_offset_mm=0.25,
            axial_offset_tolerance_mm=0.01,
            max_axis_alignment_error_deg=1.0,
        ),
    )

    assert report.status is BrepMatingStatus.READY
    assert report.geometric_mating_passed is True
    assert report.mating_axis == pytest.approx((1.0, 0.0, 0.0))
    assert report.mating_axis_source == "declared"
    assert report.declared_axis_alignment_evaluated is True
    assert report.first_axis_alignment_error_deg == pytest.approx(0.0)
    assert report.second_axis_alignment_error_deg == pytest.approx(0.0)
    assert report.axis_alignment_passed is True
    assert report.coaxiality_evaluated is True
    assert report.coaxial_offset_mm == pytest.approx(0.2)


def test_normal_and_lateral_misalignment_fail_without_promoting_mating_authority() -> None:
    diagonal = 1 / math.sqrt(2)
    report = evaluate_brep_anchor_mating(
        project_id="deck-001",
        mating_id="mate-bad",
        first=_anchor("a", "one", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        second=_anchor("b", "two", (0.0, 2.0, 0.0), (-diagonal, diagonal, 0.0), hash_char="b"),
        requirements=BrepMatingRequirements(
            max_normal_opposition_error_deg=5.0,
            max_lateral_offset_mm=0.5,
        ),
    )

    assert report.status is BrepMatingStatus.READY
    assert report.geometric_mating_passed is False
    assert report.normal_opposition_error_deg == pytest.approx(45.0)
    assert report.normal_opposition_passed is False
    assert report.lateral_offset_mm == pytest.approx(2.0)
    assert report.lateral_offset_passed is False
    assert report.metadata["connector_mating_verified"] is False


def test_required_engagement_without_declared_depth_stays_unknown() -> None:
    report = evaluate_brep_anchor_mating(
        project_id="deck-001",
        mating_id="mate-engagement-unknown",
        first=_anchor("a", "one", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        second=_anchor("b", "two", (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), hash_char="b"),
        requirements=BrepMatingRequirements(required_engagement_depth_mm=4.0),
    )

    assert report.status is BrepMatingStatus.UNKNOWN
    assert report.geometric_mating_passed is None
    assert report.engagement_evaluated is False
    assert report.engagement_passed is None
    assert report.required_evidence == [{
        "field": "declared_engagement_depth_mm",
        "reason": "required_engagement_depth_mm was supplied, but anchor geometry alone cannot infer actual engagement depth",
    }]


def test_declared_engagement_requirement_participates_in_pair_result() -> None:
    passing = evaluate_brep_anchor_mating(
        project_id="deck-001",
        mating_id="mate-engagement-pass",
        first=_anchor("a", "one", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        second=_anchor("b", "two", (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), hash_char="b"),
        requirements=BrepMatingRequirements(
            required_engagement_depth_mm=4.0,
            declared_engagement_depth_mm=4.5,
        ),
    )
    failing = evaluate_brep_anchor_mating(
        project_id="deck-001",
        mating_id="mate-engagement-fail",
        first=_anchor("a", "one", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        second=_anchor("b", "two", (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), hash_char="b"),
        requirements=BrepMatingRequirements(
            required_engagement_depth_mm=4.0,
            declared_engagement_depth_mm=3.5,
        ),
    )

    assert passing.status is BrepMatingStatus.READY
    assert passing.engagement_evaluated is True
    assert passing.engagement_passed is True
    assert passing.geometric_mating_passed is True
    assert failing.status is BrepMatingStatus.READY
    assert failing.engagement_passed is False
    assert failing.geometric_mating_passed is False


def test_frame_mismatch_is_unknown_not_cross_frame_math() -> None:
    report = evaluate_brep_anchor_mating(
        project_id="deck-001",
        mating_id="mate-frame",
        first=_anchor("a", "one", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), frame_id="assembly"),
        second=_anchor("b", "two", (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), frame_id="display-local", hash_char="b"),
    )

    assert report.status is BrepMatingStatus.UNKNOWN
    assert report.geometric_mating_passed is None
    assert report.anchor_separation_mm is None
    assert report.required_evidence[0]["field"] == "common_frame"


def test_pair_identity_and_interface_are_strict() -> None:
    first = _anchor("same", "one", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="distinct anchor identities"):
        evaluate_brep_anchor_mating(
            project_id="deck-001",
            mating_id="mate-same-anchor",
            first=first,
            second=_anchor("same", "two", (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), hash_char="b"),
        )
    with pytest.raises(ValueError, match="same interface_id"):
        evaluate_brep_anchor_mating(
            project_id="deck-001",
            mating_id="mate-interface",
            first=first,
            second=_anchor("other", "two", (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), interface_id="if-power", hash_char="b"),
        )


def test_anchor_contract_rejects_non_unit_kernel_normal() -> None:
    with pytest.raises(ValidationError, match="unit length"):
        _anchor("a", "one", (0.0, 0.0, 0.0), (2.0, 0.0, 0.0))


def test_engagement_value_without_requirement_is_rejected() -> None:
    with pytest.raises(ValidationError, match="only meaningful"):
        BrepMatingRequirements(declared_engagement_depth_mm=2.0)
