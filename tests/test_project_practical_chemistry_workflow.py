from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.mcp_backend_gateway import (
    operation_catalog, dispatch_operation, task_operation_manifest,
)
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.review_packet import verify_review_packet


PROJECT_ID = "console-repair"
PREVIEW = f"/v1/projects/{PROJECT_ID}/chemistry/practical/preview"


def initial_snapshot():
    return {
        "projectId": PROJECT_ID,
        "projectName": "Damaged handheld console",
        "currentStage": "design",
        "repair_intake": {
            "device_hint": "handheld console",
            "symptoms": ["Connector corrosion after liquid exposure"],
            "operator_notes": "Demonstration fixture only, not a real diagnostic inspection",
        },
        "machineProject": {
            "project_id": PROJECT_ID,
            "name": "Damaged handheld console",
            "purpose": "Compare safe and source-backed repair options",
            "subsystems": [
                {"subsystem_id": "system", "name": "System", "domain": "system"},
                {"subsystem_id": "electronics", "name": "Board assembly", "domain": "electrical"},
                {"subsystem_id": "housing", "name": "Housing", "domain": "mechanical"},
            ],
            "components": [
                {"component_id": "main-board", "name": "Main board", "domain": "electrical",
                 "subsystem_id": "electronics", "metadata": {"material_family": "FR4"}},
                {"component_id": "housing-shell", "name": "Plastic enclosure", "domain": "mechanical",
                 "subsystem_id": "housing", "metadata": {"material_family": "PP"}},
            ],
        },
    }


def board_assessment():
    return {
        "task": "clean_flux",
        "primary_material": "FR4",
        "material_identity": "claimed",
        "adjacent_materials": ["unknown"],
        "electrical_state": "off",
        "battery_status": "removed",
        "keepouts_confirmed": True,
    }


def body(revision=1, component="main-board", assessment=None):
    return {
        "expected_revision": revision,
        "component_id": component,
        "assessment": board_assessment() if assessment is None else assessment,
    }


@pytest.fixture
def world(tmp_path):
    store = ProjectStore(tmp_path / "store")
    client = TestClient(create_product_app(store))
    first = client.put(f"/v1/projects/{PROJECT_ID}/snapshot",
                       json={"snapshot": initial_snapshot(), "expected_revision": 0})
    assert first.status_code == 200, first.text
    return client, store


def test_preview_binds_project_and_produces_review_candidate_without_project_mutation(world):
    client, store = world
    before = store.load(PROJECT_ID)["revision"]
    response = client.post(PREVIEW, json=body())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["project_id"] == PROJECT_ID
    assert result["component_id"] == "main-board"
    assert not result["project_store_mutated"]
    assert result["human_review_required"]
    assert not result["review_actor_identity_attested_by_chemistry"]
    assert not result["findings_enforce_global_release_gate"]
    assert not result["release_authorized"]
    assert result["assessment"]["task"] == "clean_flux"
    assert result["assessment"]["decision"] == "research_or_replace"
    assert result["proposed_findings_count"] >= 2
    record = result["candidate_snapshot"]["practicalChemistryAssessments"][0]
    assert record["component_id"] == "main-board"
    assert not record["manufacturer_source_revision_verified"]
    assert not record["material_grade_independently_verified"]
    assert record["report_sha256"].startswith("sha256:")
    assert all(row["producer"] == "practical_chemistry_assessment"
               for row in result["candidate_snapshot"]["engineeringFindings"])
    assert store.load(PROJECT_ID)["revision"] == before


def test_review_packet_persists_chemistry_blockers_only_after_human_project_acceptance(world):
    client, store = world
    preview = client.post(PREVIEW, json=body())
    assert preview.status_code == 200, preview.text
    proposal = preview.json()
    staged = client.post(f"/v1/projects/{PROJECT_ID}/reviews",
                         json=proposal["next_review_request"])
    assert staged.status_code == 201, staged.text
    review = staged.json()["review"]
    assert review["status"] == "pending"
    assert store.load(PROJECT_ID)["revision"] == 1
    before = client.get(f"/v1/projects/{PROJECT_ID}/review-packet")
    assert before.status_code == 200, before.text
    assert before.json()["packet"]["findings"]["total"] == 0
    # The review packet tracks project candidate proposals, while staged
    # full-snapshot reviews are visible through the separate reviews API.
    assert before.json()["packet"]["proposals"]["total"] == 0
    pending = client.get(f"/v1/projects/{PROJECT_ID}/reviews")
    assert pending.status_code == 200
    assert any(row["review_id"] == review["review_id"] and row["status"] == "pending"
               for row in pending.json()["reviews"])
    assert verify_review_packet(before.json()["packet"])

    accepted = client.post(
        f"/v1/projects/{PROJECT_ID}/reviews/{review['review_id']}/decision",
        json={"decision": "accepted", "actor": "test-reviewer",
              "note": "Recording unverified screening for further review, NOT approval"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["review"]["status"] == "accepted"
    after = store.load(PROJECT_ID)
    assert after["revision"] == 2
    assert len(after["snapshot"]["practicalChemistryAssessments"]) == 1

    findings = client.get(f"/v1/projects/{PROJECT_ID}/findings")
    assert findings.status_code == 200, findings.text
    rows = findings.json()["findings"]
    chemical = [
        row for row in rows
        if row["category"] in {"object_blocker", "release_blocker"}
        and row["provenance"]["source_ref"] == proposal["assessment_id"]
    ]
    assert chemical and any(row["category"] == "release_blocker" for row in chemical)
    assert all(row["provenance"]["kind"] == "deterministic"
               and row["provenance"]["authority_ceiling"] == "observed"
               and row["provenance"]["attested"] is False for row in chemical)
    packet = client.get(f"/v1/projects/{PROJECT_ID}/review-packet")
    assert packet.status_code == 200, packet.text
    doc = packet.json()["packet"]
    assert verify_review_packet(doc)
    packet_ids = {row["finding_id"] for row in doc["findings"]["items"]}
    assert {row["finding_id"] for row in chemical}.issubset(packet_ids)
    assert "does not open" in doc["authority"]
    assert "release_authorized" not in after["snapshot"] or not after["snapshot"]["release_authorized"]


def test_repeat_component_and_new_component_do_not_erase_prior_findings(world):
    client, store = world
    first = client.post(PREVIEW, json=body()).json()
    approval = client.post(f"/v1/projects/{PROJECT_ID}/reviews",
                           json=first["next_review_request"]).json()["review"]
    accepted = client.post(
        f"/v1/projects/{PROJECT_ID}/reviews/{approval['review_id']}/decision",
        json={"decision": "accepted", "actor": "demo-reviewer"},
    )
    assert accepted.status_code == 200, accepted.text
    second = client.post(PREVIEW, json=body(
        revision=2, component="housing-shell",
        assessment={
            "task": "bond_joint", "primary_material": "PP",
            "material_identity": "claimed", "battery_status": "none",
            "electrical_state": "off", "exposure": ["moisture"],
        }))
    assert second.status_code == 200, second.text
    result = second.json()
    assert len(result["candidate_snapshot"]["practicalChemistryAssessments"]) == 2
    prior = [r for r in result["candidate_snapshot"]["engineeringFindings"]
             if r["object_id"] == "main-board"]
    newer = [r for r in result["candidate_snapshot"]["engineeringFindings"]
             if r["object_id"] == "housing-shell"]
    assert prior and newer
    assert store.load(PROJECT_ID)["revision"] == 2


def test_stale_revision_and_material_mismatch_fail_closed(world):
    client, store = world
    stale = client.post(PREVIEW, json=body(revision=2))
    assert stale.status_code == 409
    mismatch = client.post(PREVIEW, json=body(
        component="housing-shell",
        assessment={**board_assessment(), "primary_material": "ABS", "task": "bond_joint"}
    ))
    assert mismatch.status_code == 422
    missing = client.post(PREVIEW, json=body(component="invented"))
    assert missing.status_code == 422
    assert store.load(PROJECT_ID)["revision"] == 1


def test_actual_mcp_dispatch_and_task_manifest(world):
    client, _store = world
    path = "/v1/projects/{project_id}/chemistry/practical/preview"
    operation = next(row for row in operation_catalog(client.app)
                     if row["path"] == path)
    manifest = task_operation_manifest("practical_chemistry_repair", client.app)
    assert operation["operation_id"] in manifest["workflow_operation_ids"]
    assert not manifest["authority_contract"]["automatic_execution"]
    result = asyncio.run(dispatch_operation(
        operation["operation_id"], app=client.app,
        path_params={"project_id":PROJECT_ID}, json_body=body(),
    ))
    assert result["status_code"] == 200, result
    assert result["body"]["human_review_required"]
    assert result["body"]["project_store_mutated"] is False



def test_tampered_persisted_chemical_assessment_cannot_be_reused(world):
    client, store = world
    report = client.post(PREVIEW, json=body()).json()
    tampered = report["candidate_snapshot"]
    tampered["practicalChemistryAssessments"][0]["assessment"]["decision"] = "options_for_validation"
    saved = client.put(f"/v1/projects/{PROJECT_ID}/snapshot",
                       json={"snapshot": tampered, "expected_revision": 1})
    assert saved.status_code == 200
    later = client.post(PREVIEW, json=body(revision=2))
    assert later.status_code == 422
    assert "integrity" in later.json()["detail"]["message"]
    assert store.load(PROJECT_ID)["revision"] == 2
