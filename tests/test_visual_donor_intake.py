"""Visual donor drafts stay model inference until a person reviews every fact.

The vision inspection producer is not part of this tree, so the retained
inspection artifact is written by hand here in the shape the intake service
validates. Nothing in these tests measures a board or identifies a part.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from hardware_splicer.donor_errors import DonorValidationError
from hardware_splicer.engineering_artifact_store import EngineeringArtifactStore
from hardware_splicer.visual_donor_intake import VisualDonorIntakeService

OBSERVATION_SHA = hashlib.sha256(b"router-board-photo").hexdigest()


def _runtime(tmp_path):
    artifacts = EngineeringArtifactStore(tmp_path / "artifacts")
    payload = {
        "schema": "hardware_splicer.visual_inspection_inference.v1",
        "observation_id": "obs-router-top",
        "observation_sha256": OBSERVATION_SHA,
        "task_id": "donor_intake",
        "model_id": "donor-vision",
        "model_version": "1.0",
        "claims": [],
        "claim_count": 0,
        "evidence_class": "model_inference",
        "hypothesis_only": True,
        "physical_correctness": "UNPROVEN",
    }
    artifacts.put(
        artifact_id="router-top-inspection",
        kind="inspection_document",
        content=(json.dumps(payload, sort_keys=True) + "\n").encode(),
        media_type="application/json",
        producer="vision_inspection",
    )
    return artifacts, VisualDonorIntakeService(artifacts=artifacts)


def _draft(service, **extra):
    return service.create_draft(
        donor_id="donor:router:front-board",
        label="Router front board",
        inspection_artifact_ids=["router-top-inspection"],
        facts=extra.pop("facts", _facts()),
        output_artifact_id=extra.pop("output_artifact_id", "router-donor-draft"),
    )


def _facts():
    return [
        {
            "fact_id": "outline-1",
            "kind": "board_outline",
            "inspection_artifact_id": "router-top-inspection",
            "confidence": 0.82,
            "value": {"width_mm": 80.0, "length_mm": 50.0, "thickness_mm": 1.6},
        },
        {
            "fact_id": "connector-j1",
            "kind": "connector",
            "inspection_artifact_id": "router-top-inspection",
            "confidence": 0.71,
            "value": {"ref": "J1", "package": "pin header", "x_mm": 10.0, "y_mm": 20.0, "side": "front"},
        },
        {
            "fact_id": "marking-j1",
            "kind": "marking",
            "inspection_artifact_id": "router-top-inspection",
            "confidence": 0.67,
            "value": {"ref": "J1", "text": "J1 5V GND RX TX"},
        },
        {
            "fact_id": "screw-a",
            "kind": "screw_location",
            "inspection_artifact_id": "router-top-inspection",
            "confidence": 0.79,
            "value": {"x_mm": 5.0, "y_mm": 5.0, "diameter_mm": 3.0},
        },
    ]


def _capture():
    return {
        "schema_version": "hardware_splicer.donor_capture.v1",
        "name": "Router front board",
        "board": {"width_mm": 80.0, "length_mm": 50.0, "thickness_mm": 1.6},
        "parts": [
            {
                "ref": "J1",
                "kind": "connector",
                "package": "pin header",
                "x_mm": 10.0,
                "y_mm": 20.0,
                "side": "front",
                "marking": "J1 5V GND RX TX",
            }
        ],
    }


def test_visual_donor_draft_binds_every_fact_to_retained_image_and_stays_inference(tmp_path):
    artifacts, service = _runtime(tmp_path)
    draft = _draft(service)["draft"]
    assert draft["schema"] == "hardware_splicer.visual_donor_draft.v1"
    assert draft["capture_prefill_ready"] is False
    assert draft["requires_human_confirmation"] is True
    assert draft["geometry_measured"] is False
    assert draft["markings_establish_identity"] is False
    assert draft["may_auto_promote_donor_contract"] is False
    assert draft["capture_prefill"]["board"]["width_mm"] == 80.0
    assert draft["capture_prefill"]["parts"][0]["marking"] == "J1 5V GND RX TX"
    for fact in draft["facts"]:
        assert fact["state"] == "model_inference"
        assert fact["measured"] is False
        assert fact["human_confirmed"] is False
        assert fact["establishes_part_identity"] is False
        assert fact["source"]["observation_id"] == "obs-router-top"
        assert fact["source"]["observation_sha256"] == OBSERVATION_SHA
        assert fact["source"]["inspection_artifact_id"] == "router-top-inspection"
    stored = artifacts.describe("router-donor-draft")
    assert stored.producer == "visual_donor_intake"
    assert stored.executable is False
    assert stored.physical_correctness == "UNPROVEN"


def test_draft_from_a_missing_or_foreign_inspection_artifact_is_refused(tmp_path):
    artifacts, service = _runtime(tmp_path)
    with pytest.raises(DonorValidationError):
        service.create_draft(
            donor_id="donor:router:front-board", label="x",
            inspection_artifact_ids=["no-such-inspection"], facts=_facts(),
            output_artifact_id="d1",
        )
    artifacts.put(
        artifact_id="not-an-inspection", kind="inspection_document",
        content=b'{"schema":"hardware_splicer.visual_inspection_inference.v1"}',
        media_type="application/json", producer="someone_else",
    )
    with pytest.raises(DonorValidationError, match="incompatible kind or producer"):
        service.create_draft(
            donor_id="donor:router:front-board", label="x",
            inspection_artifact_ids=["not-an-inspection"], facts=_facts(),
            output_artifact_id="d2",
        )


def test_marking_transcription_cannot_smuggle_identity_claim(tmp_path):
    _artifacts, service = _runtime(tmp_path)
    facts = _facts()
    facts[2] = {**facts[2], "value": {"ref": "U1", "text": "AMS1117", "mpn": "AMS1117-3.3"}}
    with pytest.raises(DonorValidationError, match="must not claim part identity"):
        _draft(service, facts=facts, output_artifact_id="bad-identity-draft")


def test_confirmation_is_a_separate_derivative_and_not_a_measurement(tmp_path):
    _artifacts, service = _runtime(tmp_path)
    _draft(service)
    decisions = [
        {"fact_id": "outline-1", "decision": "confirm"},
        {"fact_id": "connector-j1", "decision": "correct", "corrected_value": {
            "ref": "J1", "package": "pin header", "x_mm": 10.0, "y_mm": 20.0, "side": "front"}},
        {"fact_id": "marking-j1", "decision": "confirm"},
        {"fact_id": "screw-a", "decision": "reject", "note": "not a mounting hole"},
    ]
    confirmed = service.confirm_capture(
        draft_artifact_id="router-donor-draft", output_artifact_id="router-donor-confirmed",
        human_id="bench-lead", capture=_capture(), decisions=decisions,
    )["confirmed"]
    assert confirmed["ready_for_donor_capture"] is True
    assert confirmed["reviewed_by"] == {"kind": "human", "id": "bench-lead"}
    assert confirmed["evidence_class"] == "human_confirmation"
    assert confirmed["geometry_measured"] is False
    assert confirmed["measurement_claims_require_separate_physical_evidence"] is True
    assert confirmed["markings_establish_identity"] is False
    assert confirmed["may_auto_promote_physical_evidence"] is False
    assert confirmed["physical_correctness"] == "UNPROVEN"
    assert confirmed["donor_capture"] == _capture()
    assert {row["state"] for row in confirmed["decisions"]} == {"human_confirmed", "human_rejected"}


def test_confirmation_needs_a_decision_for_every_draft_fact(tmp_path):
    _artifacts, service = _runtime(tmp_path)
    _draft(service)
    with pytest.raises(DonorValidationError, match="every draft fact"):
        service.confirm_capture(
            draft_artifact_id="router-donor-draft", output_artifact_id="partial",
            human_id="bench-lead", capture=_capture(),
            decisions=[{"fact_id": "outline-1", "decision": "confirm"}],
        )
