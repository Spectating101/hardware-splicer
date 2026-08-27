from __future__ import annotations

from copy import deepcopy

from hardware_splicer.derivative_reuse import (
    adjudicate_derivative_reuse,
    predict_derivative_reuse,
)


def _manifest(revision: str, camera: str) -> dict:
    return {
        "schema_version": "hardware_splicer.capability_manifest.v1",
        "capability_id": "vision-core",
        "revision": revision,
        "dependencies": [
            {
                "dependency_id": "component:camera:sensor_identity",
                "kind": "component_identity",
                "resolved": True,
                "value": camera,
            },
            {
                "dependency_id": "interface:wifi:config_api:v1",
                "kind": "interface_contract",
                "resolved": True,
                "value": "vision-config-v1",
            },
        ],
    }


def _evidence() -> list[dict]:
    return [
        {
            "evidence_id": "ev-camera",
            "depends_on": ["component:camera:sensor_identity"],
            "dependencies_complete": True,
        },
        {
            "evidence_id": "ev-optics",
            "depends_on": ["ev-camera", "condition:lighting:v1"],
            "dependencies_complete": True,
        },
        {
            "evidence_id": "ev-wifi",
            "depends_on": ["interface:wifi:config_api:v1"],
            "dependencies_complete": True,
        },
    ]


def test_prediction_is_hashed_before_adjudication() -> None:
    prediction = predict_derivative_reuse(
        _manifest("a", "camera-A"),
        _manifest("b", "camera-B"),
        _evidence(),
    )

    assert prediction["status"] == "predicted"
    assert prediction["prediction_hash"].startswith("sha256:")
    statuses = {
        row["evidence_id"]: row["status"]
        for row in prediction["impact_report"]["results"]
    }
    assert statuses == {
        "ev-camera": "invalidated",
        "ev-optics": "invalidated",
        "ev-wifi": "retained",
    }


def test_outer_adjudication_scores_original_frozen_prediction() -> None:
    prediction = predict_derivative_reuse(
        _manifest("a", "camera-A"),
        _manifest("b", "camera-B"),
        _evidence(),
    )
    result = adjudicate_derivative_reuse(
        prediction,
        expected_invalidated_evidence_ids=["ev-camera", "ev-optics"],
        adjudicator="outer-test-evaluator",
        adjudication_basis="fixture dependency truth",
    )

    assert result["status"] == "adjudicated"
    assert result["prediction_hash"] == prediction["prediction_hash"]
    assert result["score"]["correctly_invalidated_count"] == 2
    assert result["score"]["unnecessarily_invalidated_count"] == 0
    assert result["score"]["missed_invalidation_count"] == 0


def test_mutating_prediction_after_freeze_breaks_adjudication_chain() -> None:
    prediction = predict_derivative_reuse(
        _manifest("a", "camera-A"),
        _manifest("b", "camera-B"),
        _evidence(),
    )
    tampered = deepcopy(prediction)
    tampered["impact_report"]["results"][0]["status"] = "retained"

    result = adjudicate_derivative_reuse(
        tampered,
        expected_invalidated_evidence_ids=["ev-camera", "ev-optics"],
        adjudicator="outer-test-evaluator",
        adjudication_basis="fixture dependency truth",
    )

    assert result["status"] == "invalid"
    assert "prediction_hash_mismatch" in result["validation_errors"]


def test_unresolved_candidate_identity_produces_blocked_prediction_not_invalidation() -> None:
    candidate = _manifest("b", "camera-A")
    camera = candidate["dependencies"][0]
    camera["resolved"] = False
    camera["value"] = None

    prediction = predict_derivative_reuse(
        _manifest("a", "camera-A"),
        candidate,
        _evidence(),
    )
    statuses = {
        row["evidence_id"]: row["status"]
        for row in prediction["impact_report"]["results"]
    }

    assert prediction["status"] == "predicted"
    assert statuses["ev-camera"] == "blocked"
    assert statuses["ev-optics"] == "blocked"
    assert statuses["ev-wifi"] == "retained"
