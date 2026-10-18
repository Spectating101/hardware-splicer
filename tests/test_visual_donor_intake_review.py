from __future__ import annotations

import pytest

from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.visual_donor_intake import _review_decisions, _validate_fact_value


def _facts():
    return {
        "outline-1": {
            "fact_id": "outline-1",
            "kind": "board_outline",
            "value": {"width_mm": 80.0, "length_mm": 50.0, "thickness_mm": 1.6},
            "confidence": 0.82,
            "source": {
                "inspection_artifact_id": "inspection-1",
                "inspection_artifact_sha256": "a" * 64,
                "observation_id": "observation-1",
                "observation_sha256": "b" * 64,
            },
        },
        "marking-1": {
            "fact_id": "marking-1",
            "kind": "marking",
            "value": {"ref": "J1", "text": "5V GND RX TX"},
            "confidence": 0.67,
            "source": {
                "inspection_artifact_id": "inspection-1",
                "inspection_artifact_sha256": "a" * 64,
                "observation_id": "observation-1",
                "observation_sha256": "b" * 64,
            },
        },
    }


def test_confirmation_requires_explicit_decision_for_every_inferred_fact():
    with pytest.raises(FabricationValidationError, match="every draft fact"):
        _review_decisions(
            [{"fact_id": "outline-1", "decision": "confirm"}],
            _facts(),
        )


def test_reviewed_fact_keeps_model_value_confidence_and_source_for_audit():
    reviewed = _review_decisions(
        [
            {"fact_id": "outline-1", "decision": "confirm"},
            {"fact_id": "marking-1", "decision": "reject", "note": "glare obscures the final characters"},
        ],
        _facts(),
    )
    outline = reviewed[0]
    assert outline["kind"] == "board_outline"
    assert outline["model_value"]["width_mm"] == 80.0
    assert outline["model_confidence"] == 0.82
    assert outline["source"]["observation_sha256"] == "b" * 64
    assert outline["measured"] is False
    assert reviewed[1]["state"] == "human_rejected"


def test_visual_board_thickness_is_bounded_but_still_not_measurement():
    _validate_fact_value(
        "board_outline",
        {"width_mm": 80.0, "length_mm": 50.0, "thickness_mm": 1.6},
        index=0,
    )
    with pytest.raises(FabricationValidationError, match="thickness_mm is out of bounds"):
        _validate_fact_value(
            "board_outline",
            {"width_mm": 80.0, "length_mm": 50.0, "thickness_mm": 500.0},
            index=0,
        )
