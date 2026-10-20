from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from hardware_splicer.audited_physical_evidence import AuditedPhysicalEvidencePackage
from hardware_splicer.physical_evidence import (
    PhysicalAuthorizationAssessment, PhysicalEvidencePackage, PhysicalOperation
)
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_chemistry_release_gate import (
    block_audited_physical_authorization, evaluate_project_chemistry_gate,
)
from hardware_splicer.project_store import ProjectStore
from test_project_practical_chemistry_workflow import initial_snapshot, PROJECT_ID, body, PREVIEW
from test_project_physical_validation import _record, _build_attested, KEY, CAPTURED_AT


def accepted_fixture(tmp_path):
    store = ProjectStore(tmp_path / "project-store")
    client = TestClient(create_product_app(store))
    assert client.put(f"/v1/projects/{PROJECT_ID}/snapshot",
                      json={"snapshot":initial_snapshot(),"expected_revision":0}).status_code == 200
    proposal = client.post(PREVIEW, json=body()).json()
    stage = client.post(f"/v1/projects/{PROJECT_ID}/reviews",
                        json=proposal["next_review_request"]).json()["review"]
    result = client.post(f"/v1/projects/{PROJECT_ID}/reviews/{stage['review_id']}/decision",
                         json={"decision":"accepted","actor":"test-operator"})
    assert result.status_code == 200, result.text
    return client, store


def test_physical_packet_announces_chemistry_blockers(tmp_path):
    client, _ = accepted_fixture(tmp_path)
    res = client.get(f"/v1/projects/{PROJECT_ID}/engineering/physical-validation/packet")
    assert res.status_code == 200, res.text
    report = res.json()
    assert report["chemistry_release_gate"]["blocked"]
    assert report["physical_operation_clearance_blocked_by_chemistry"] is True
    assert report["physical_authority_granted"] is False
    assert report["physical_validation_packet"]["policy"]["automatic_authorization"] is False


def test_physical_attested_capture_saves_but_chemistry_prevents_authorization(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "chem-test-key")
    client, store = accepted_fixture(tmp_path)
    result = client.get(f"/v1/projects/{PROJECT_ID}/engineering/physical-validation/packet")
    assert result.status_code == 200
    packet = result.json()["physical_validation_packet"]
    gate_id = packet["gates"][0]["gate_id"]
    assert gate_id == "identify-physical-candidate"
    specimen = _record(packet, gate_id, evidence_id="chem-specimen-identity",
                      values={
                         "assembly_id":"fixture-board-1",
                         "assembly_revision":"A",
                         "artifact_hashes":packet["artifact_hashes"],
                      })
    specimen["metadata"]["physical_test_article"] = "fixture-only"
    envelope = _build_attested(client, specimen)
    submitted = client.post(
        f"/v1/projects/{PROJECT_ID}/engineering/physical-validation/evidence",
        json={
            "expected_revision":2,
            "packet_id":packet["packet_id"],
            "envelopes":[envelope],
            "as_of":"2026-10-20T03:00:00+00:00",
        },
    )
    assert submitted.status_code == 200, submitted.text
    returned = submitted.json()
    assert returned["chemistry_release_gate"]["blocked"]
    assert returned["authorization_applicable"] is False
    assert returned["scoped_authorized_operations"] == []
    audit = returned["physical_validation"]["audited_physical_evidence"]
    assert audit["applicable"] is False
    assert audit["physical_package"]["assessment"]["applicable"] is False
    assert audit["physical_package"]["assessment"]["authorized_operations"] == []
    persisted = store.load(PROJECT_ID)
    assert persisted["revision"] == 3
    assert persisted["snapshot"]["practicalChemistryAssessments"]
    assert persisted["snapshot"]["physicalValidation"]["chemistry_release_gate"]["blocked"]
    assert persisted["snapshot"]["physicalValidation"]["scoped_authorized_operations"] == []


def test_audited_model_nested_authorization_revoked_without_destroying_history():
    authorization = PhysicalAuthorizationAssessment.model_construct(
        project_id="test", status="authorized", applicable=True,
        authorized_operations=[PhysicalOperation.BENCH_POWER],
        blockers=[],
    )
    physical = PhysicalEvidencePackage.model_construct(
        project_id="test", assessment=authorization, evidence=[], decision=None)
    audited = AuditedPhysicalEvidencePackage.model_construct(
        physical_package=physical, blockers=[], applicable=True, envelopes=[],
        ledger_entries=[], ledger_assessment=None,
    )
    gate = {"blocked":True,"blockers":[
        {"code":"chemistry_independent_validation_required"},
    ]}
    result = block_audited_physical_authorization(audited, gate)
    assert not result.applicable
    assert not result.physical_package.assessment.applicable
    assert result.physical_package.assessment.authorized_operations == []
    assert result.physical_package.assessment.status == "blocked"
    assert audited.applicable is True
    assert audited.physical_package.assessment.authorized_operations == [PhysicalOperation.BENCH_POWER]


def test_gate_not_affected_by_invented_release_booleans(tmp_path):
    client, store = accepted_fixture(tmp_path)
    dirty = store.load(PROJECT_ID)["snapshot"]
    dirty["release_authorized"] = True
    dirty["power_on_authorized"] = True
    written = client.put(f"/v1/projects/{PROJECT_ID}/snapshot",
                         json={"snapshot":dirty,"expected_revision":2})
    assert written.status_code == 200, written.text
    r = client.get(f"/v1/projects/{PROJECT_ID}/engineering/release-gate",
                   params={"requested_state":"build_ready"})
    assert r.json()["allowed"] is False
    assert r.json()["chemistry_gate"]["blocked"]


def test_no_assessment_does_not_close_unrelated_project_physical_gate(tmp_path):
    store = ProjectStore(tmp_path / "store")
    store.save("separate-device", {
        "name":"No chemistry investigation",
        "mission":"Electronics",
        "machineProject":{
            "project_id":"separate-device","name":"Different device",
            "purpose":"Unassessed separate device"},
    },expected_revision=0)
    client = TestClient(create_product_app(store))
    read = client.get("/v1/projects/separate-device/engineering/physical-validation/packet")
    assert read.status_code == 200
    assert read.json()["chemistry_release_gate"]["status"] == "not_applicable"
    assert not read.json()["physical_operation_clearance_blocked_by_chemistry"]


def test_secondary_engineering_plan_grant_surfaces_are_revoked_together():
    from hardware_splicer.project_chemistry_release_gate import apply_chemistry_hold_to_plan
    raw = {
        "physical_evidence_package": {
            "assessment": {"applicable":True,"authorized_operations":["bench_power"],
                           "status":"authorized","blockers":[]}
        },
        "audited_physical_evidence": {
            "applicable":True,
            "blockers":[],
            "physical_package": {
                "assessment":{"applicable":True,"authorized_operations":["bench_power"],
                              "status":"authorized","blockers":[]}
            }
        },
        "scoped_release_assessment": {
            "allowed":True,"allowed_operations":["bench_power"],
            "status":"authorized","blockers":[]
        },
        "engineering_readiness": {
            "scoped_authorized_operations":["bench_power"],
            "physical_scope_authorized":True
        },
        "engineering_status":{"metadata":{"physical_scope_authorized":True,
                                         "authorized_operations":["bench_power"]}},
    }
    gate = {"blocked":True,
            "blockers":[{"code":"chemistry_independent_validation_required"}]}
    updated = apply_chemistry_hold_to_plan(raw,gate)
    assert updated["physical_evidence_package"]["assessment"]["authorized_operations"] == []
    assert not updated["physical_evidence_package"]["assessment"]["applicable"]
    assert updated["audited_physical_evidence"]["physical_package"]["assessment"]["authorized_operations"] == []
    assert not updated["audited_physical_evidence"]["applicable"]
    assert updated["scoped_release_assessment"]["allowed"] is False
    assert updated["scoped_release_assessment"]["allowed_operations"] == []
    assert updated["engineering_readiness"]["scoped_authorized_operations"] == []
    assert not updated["engineering_status"]["metadata"]["physical_scope_authorized"]
    assert raw["scoped_release_assessment"]["allowed"] is True


def test_nonchemical_plan_is_not_changed_by_chemistry_gate():
    from hardware_splicer.project_chemistry_release_gate import apply_chemistry_hold_to_plan
    raw = {"scoped_release_assessment":{"allowed":True,
                                       "allowed_operations":["bench_power"]}}
    assert apply_chemistry_hold_to_plan(raw,{"blocked":False}) == raw


def test_stale_prechemistry_prior_operation_permission_not_trusted(tmp_path, monkeypatch):
    """Real submission never receives a stale previously-authorized power scope."""
    import hardware_splicer.project_physical_validation_api as physical_api
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "chem-test-key")
    client, store = accepted_fixture(tmp_path)
    snap = store.load(PROJECT_ID)["snapshot"]
    snap["physicalValidation"] = {"scoped_authorized_operations":["bench_power"]}
    assert client.put(f"/v1/projects/{PROJECT_ID}/snapshot",
                      json={"snapshot":snap,"expected_revision":2}).status_code == 200
    packet_result = client.get(f"/v1/projects/{PROJECT_ID}/engineering/physical-validation/packet")
    assert packet_result.status_code == 200
    packet = packet_result.json()["physical_validation_packet"]
    record = _record(
        packet, "identify-physical-candidate", evidence_id="stale-auth-capture",
        values={"assembly_id":"bench-a","assembly_revision":"r0",
                "artifact_hashes":packet["artifact_hashes"]},
    )
    envelope = _build_attested(client,record)
    original_validator = physical_api.validate_packet_evidence
    seen = []

    def assert_no_stale_permission(packet_arg, envelope_arg, *, prior_authorized_operations):
        seen.append(list(prior_authorized_operations))
        return original_validator(
            packet_arg, envelope_arg,
            prior_authorized_operations=prior_authorized_operations,
        )

    monkeypatch.setattr(physical_api, "validate_packet_evidence", assert_no_stale_permission)
    response = client.post(
        f"/v1/projects/{PROJECT_ID}/engineering/physical-validation/evidence",
        json={"expected_revision":3,"packet_id":packet["packet_id"],
              "envelopes":[envelope],
              "as_of":"2026-10-20T03:00:00+00:00"},
    )
    assert response.status_code == 200, response.text
    assert seen == [[]]
    assert response.json()["scoped_authorized_operations"] == []
    assert response.json()["chemistry_release_gate"]["blocked"]
