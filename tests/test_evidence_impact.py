from __future__ import annotations

from hardware_splicer.evidence_impact import (
    BLOCKED,
    INVALIDATED,
    RETAINED,
    evaluate_evidence_impact,
    score_evidence_invalidation,
)


def _vision_camera_case() -> dict:
    return {
        "schema_version": "hardware_splicer.evidence_impact_case.v1",
        "changed_dependency_ids": [
            "component:camera:sensor_identity",
            "interface:camera:sensor_configuration",
        ],
        "unresolved_dependency_ids": [],
        "evidence_items": [
            {
                "evidence_id": "ev-camera-identity",
                "depends_on": ["component:camera:sensor_identity"],
                "dependencies_complete": True,
            },
            {
                "evidence_id": "ev-camera-driver-config",
                "depends_on": [
                    "ev-camera-identity",
                    "interface:camera:sensor_configuration",
                ],
                "dependencies_complete": True,
            },
            {
                "evidence_id": "ev-optical-benchmark",
                "depends_on": [
                    "ev-camera-driver-config",
                    "condition:lighting:baseline",
                    "condition:lens_mount:baseline",
                ],
                "dependencies_complete": True,
            },
            {
                "evidence_id": "ev-model-accuracy",
                "depends_on": ["ev-optical-benchmark", "dataset:vision-a:v1"],
                "dependencies_complete": True,
            },
            {
                "evidence_id": "ev-wifi-api-contract",
                "depends_on": ["interface:wifi:config_api:v1"],
                "dependencies_complete": True,
            },
            {
                "evidence_id": "ev-enclosure-base",
                "depends_on": ["mechanical:base:mount_pattern:v1"],
                "dependencies_complete": True,
            },
        ],
    }


def _status_map(report: dict) -> dict[str, str]:
    return {row["evidence_id"]: row["status"] for row in report["results"]}


def test_camera_change_invalidates_only_dependent_evidence_transitively() -> None:
    report = evaluate_evidence_impact(_vision_camera_case())
    status = _status_map(report)

    assert report["status"] == "evaluated"
    assert status["ev-camera-identity"] == INVALIDATED
    assert status["ev-camera-driver-config"] == INVALIDATED
    assert status["ev-optical-benchmark"] == INVALIDATED
    assert status["ev-model-accuracy"] == INVALIDATED
    assert status["ev-wifi-api-contract"] == RETAINED
    assert status["ev-enclosure-base"] == RETAINED
    assert report["summary"] == {"retained": 2, "invalidated": 4, "blocked": 0}


def test_unresolved_dependency_blocks_reuse_and_propagates_without_claiming_invalidation() -> None:
    case = _vision_camera_case()
    case["changed_dependency_ids"] = []
    case["unresolved_dependency_ids"] = ["condition:lighting:baseline"]

    report = evaluate_evidence_impact(case)
    status = _status_map(report)

    assert status["ev-camera-identity"] == RETAINED
    assert status["ev-camera-driver-config"] == RETAINED
    assert status["ev-optical-benchmark"] == BLOCKED
    assert status["ev-model-accuracy"] == BLOCKED
    assert report["metadata"]["unknown_dependency_coverage_blocks_reuse"] is True


def test_incomplete_dependency_coverage_blocks_evidence_even_without_known_change() -> None:
    case = _vision_camera_case()
    case["changed_dependency_ids"] = []
    target = next(row for row in case["evidence_items"] if row["evidence_id"] == "ev-wifi-api-contract")
    target["dependencies_complete"] = False

    report = evaluate_evidence_impact(case)

    assert _status_map(report)["ev-wifi-api-contract"] == BLOCKED


def test_known_invalidation_dominates_an_unresolved_secondary_dependency() -> None:
    case = _vision_camera_case()
    case["unresolved_dependency_ids"] = ["condition:lighting:baseline"]

    report = evaluate_evidence_impact(case)

    assert _status_map(report)["ev-optical-benchmark"] == INVALIDATED


def test_dependency_cycles_are_invalid_instead_of_arbitrarily_resolved() -> None:
    case = {
        "schema_version": "hardware_splicer.evidence_impact_case.v1",
        "changed_dependency_ids": [],
        "unresolved_dependency_ids": [],
        "evidence_items": [
            {"evidence_id": "ev-a", "depends_on": ["ev-b"], "dependencies_complete": True},
            {"evidence_id": "ev-b", "depends_on": ["ev-a"], "dependencies_complete": True},
        ],
    }

    report = evaluate_evidence_impact(case)

    assert report["status"] == "invalid"
    assert any(value.startswith("evidence_dependency_cycle:") for value in report["validation_errors"])


def test_outer_adjudication_scores_false_positive_and_false_negative() -> None:
    report = evaluate_evidence_impact(_vision_camera_case())

    score = score_evidence_invalidation(
        report,
        expected_invalidated_evidence_ids={
            "ev-camera-identity",
            "ev-camera-driver-config",
            "ev-optical-benchmark",
            "ev-enclosure-base",
        },
    )

    assert score["status"] == "scored"
    assert score["correctly_invalidated_count"] == 3
    assert score["unnecessarily_invalidated_count"] == 1
    assert score["missed_invalidation_count"] == 1
    assert score["false_positive_ids"] == ["ev-model-accuracy"]
    assert score["false_negative_ids"] == ["ev-enclosure-base"]


def test_unknown_adjudication_id_is_invalid() -> None:
    report = evaluate_evidence_impact(_vision_camera_case())

    score = score_evidence_invalidation(
        report,
        expected_invalidated_evidence_ids=[],
        adjudicated_evidence_ids=["ev-wifi-api-contract", "ev-does-not-exist"],
    )

    assert score["status"] == "invalid"
    assert score["validation_errors"] == ["adjudicated_unknown_evidence_ids:ev-does-not-exist"]


def test_unknown_expected_invalidation_is_invalid_instead_of_silently_dropped() -> None:
    report = evaluate_evidence_impact(_vision_camera_case())

    score = score_evidence_invalidation(
        report,
        expected_invalidated_evidence_ids=["ev-camera-identity", "ev-does-not-exist"],
    )

    assert score["status"] == "invalid"
    assert score["validation_errors"] == ["expected_unknown_evidence_ids:ev-does-not-exist"]


def test_expected_invalidation_outside_explicit_adjudication_scope_is_invalid() -> None:
    report = evaluate_evidence_impact(_vision_camera_case())

    score = score_evidence_invalidation(
        report,
        expected_invalidated_evidence_ids=["ev-camera-identity", "ev-optical-benchmark"],
        adjudicated_evidence_ids=["ev-camera-identity", "ev-wifi-api-contract"],
    )

    assert score["status"] == "invalid"
    assert score["validation_errors"] == [
        "expected_evidence_outside_adjudicated_scope:ev-optical-benchmark"
    ]
