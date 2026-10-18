from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.engineering_artifact_store import EngineeringArtifactStore
from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.fabricator_intelligence_manifest import fabricator_intelligence_manifest
from hardware_splicer.fabricator_intelligence_workbench import FabricatorIntelligenceWorkbench
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.physical_observation_store import PhysicalObservationStore
from hardware_splicer.product_api import create_product_app
from hardware_splicer.vision_inspection import VisionClaim, VisionInspectionService
from hardware_splicer.visual_donor_intake import VisualDonorIntakeService

HUMAN_TOKEN = "human-visual-token-" + "h" * 40
AGENT_TOKEN = "agent-visual-token-" + "a" * 40


class DonorVisionProvider:
    model_id = "donor-vision"
    model_version = "1.0"

    def infer(self, *, image: bytes, media_type: str, task_id: str):
        assert image == b"router-board-photo"
        assert media_type == "image/jpeg"
        assert task_id == "donor_intake"
        return [
            VisionClaim(
                label="board_outline_candidate",
                confidence=0.88,
                description="Rectangular PCB outline is visible against the reference mat.",
                region=(0.05, 0.05, 0.95, 0.9),
            ),
            VisionClaim(
                label="connector_candidate",
                confidence=0.74,
                description="A four-pin header appears near the left edge.",
                region=(0.08, 0.3, 0.18, 0.55),
            ),
        ]


def _runtime(tmp_path):
    observations = PhysicalObservationStore(tmp_path / "observations")
    observation = observations.put(
        kind="image",
        source_id="bench-camera",
        media_type="image/jpeg",
        data=b"router-board-photo",
    )
    artifacts = EngineeringArtifactStore(tmp_path / "artifacts")
    vision = VisionInspectionService(
        observations=observations,
        artifacts=artifacts,
        provider=DonorVisionProvider(),
    )
    workbench = FabricatorIntelligenceWorkbench(vision=vision)
    inspection = workbench.inspect_image(
        observation_id=observation.observation_id,
        task_id="donor_intake",
        output_artifact_id="router-top-inspection",
    )
    return observation, artifacts, workbench, inspection


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
    observation, artifacts, workbench, inspection = _runtime(tmp_path)
    result = workbench.draft_donor_from_inspections(
        donor_id="donor:router:front-board",
        label="Router front board",
        inspection_artifact_ids=[inspection["artifact"]["artifact_id"]],
        facts=_facts(),
        output_artifact_id="router-donor-draft",
    )
    draft = result["draft"]
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
        assert fact["source"]["observation_id"] == observation.observation_id
        assert fact["source"]["observation_sha256"] == observation.sha256
        assert fact["source"]["inspection_artifact_id"] == "router-top-inspection"
    stored = artifacts.describe("router-donor-draft")
    assert stored.producer == "visual_donor_intake"
    assert stored.executable is False
    assert stored.physical_correctness == "UNPROVEN"


def test_marking_transcription_cannot_smuggle_identity_claim(tmp_path):
    _observation, artifacts, _workbench, inspection = _runtime(tmp_path)
    service = VisualDonorIntakeService(artifacts=artifacts)
    facts = _facts()
    facts[2] = {
        **facts[2],
        "value": {"ref": "U1", "text": "AMS1117", "mpn": "AMS1117-3.3"},
    }
    with pytest.raises(FabricationValidationError, match="must not claim part identity"):
        service.create_draft(
            donor_id="donor:router:front-board",
            label="Router front board",
            inspection_artifact_ids=[inspection["artifact"]["artifact_id"]],
            facts=facts,
            output_artifact_id="bad-identity-draft",
        )


def test_human_confirmation_is_separate_authenticated_derivative_not_measurement(tmp_path, monkeypatch):
    _observation, _artifacts, workbench, inspection = _runtime(tmp_path)
    monkeypatch.setenv(
        "HARDWARE_SPLICER_OPERATOR_TOKENS",
        "{" +
        f'"{hash_operator_token(HUMAN_TOKEN)}":{{"id":"bench-lead","kind":"human"}},' +
        f'"{hash_operator_token(AGENT_TOKEN)}":{{"id":"vision-agent","kind":"agent"}}' +
        "}",
    )
    draft = workbench.draft_donor_from_inspections(
        donor_id="donor:router:front-board",
        label="Router front board",
        inspection_artifact_ids=[inspection["artifact"]["artifact_id"]],
        facts=_facts(),
        output_artifact_id="router-donor-draft",
    )
    assert draft["draft"]["capture_prefill_ready"] is False
    client = TestClient(create_product_app(fabricator_intelligence_workbench=workbench))
    body = {
        "output_artifact_id": "router-donor-confirmed",
        "capture": _capture(),
        "decisions": [
            {"fact_id": "outline-1", "decision": "confirm"},
            {"fact_id": "connector-j1", "decision": "correct", "corrected_value": {"ref": "J1", "package": "pin header", "x_mm": 10.0, "y_mm": 20.0, "side": "front"}},
            {"fact_id": "marking-j1", "decision": "confirm"},
            {"fact_id": "screw-a", "decision": "reject", "note": "not a mounting hole"},
        ],
    }
    path = "/v1/fabricator/intelligence/vision/donor-drafts/router-donor-draft/confirm"
    assert client.post(path, json=body).status_code == 403
    assert client.post(path, json=body, headers={"X-HS-Operator-Token": AGENT_TOKEN}).status_code == 403
    response = client.post(path, json=body, headers={"X-HS-Operator-Token": HUMAN_TOKEN})
    assert response.status_code == 201, response.text
    confirmed = response.json()["confirmed"]
    assert confirmed["ready_for_donor_capture"] is True
    assert confirmed["reviewed_by"] == {"kind": "human", "id": "bench-lead"}
    assert confirmed["evidence_class"] == "human_confirmation"
    assert confirmed["geometry_measured"] is False
    assert confirmed["measurement_claims_require_separate_physical_evidence"] is True
    assert confirmed["markings_establish_identity"] is False
    assert confirmed["donor_capture"] == _capture()
    assert {row["state"] for row in confirmed["decisions"]} == {"human_confirmed", "human_rejected"}


def test_agent_manifest_exposes_prefill_but_not_human_confirmation(tmp_path):
    _observation, _artifacts, workbench, _inspection = _runtime(tmp_path)
    app = create_product_app(fabricator_intelligence_workbench=workbench)
    manifest = fabricator_intelligence_manifest(app)
    offered = {(row["method"], row["path"]) for row in manifest["operations"]}
    assert ("POST", "/v1/fabricator/intelligence/vision/donor-drafts") in offered
    assert ("POST", "/v1/fabricator/intelligence/vision/donor-drafts/{draft_artifact_id}/confirm") not in offered
    assert manifest["authority_contract"]["visual_draft_is_donor_contract_truth"] is False
    assert manifest["authority_contract"]["visual_draft_geometry_is_measured"] is False
    assert manifest["authority_contract"]["marking_text_establishes_part_identity"] is False
    assert manifest["authority_contract"]["agent_can_confirm_visual_donor_draft"] is False
