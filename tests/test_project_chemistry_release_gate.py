from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.machine_project import ReleaseState
from hardware_splicer.machine_release import assessment_allows
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_chemistry_release_gate import (
    assess_project_release,
    evaluate_project_chemistry_gate,
)
from hardware_splicer.project_store import ProjectStore, RevisionConflict

from test_machine_project import inspection_robot_project
from test_project_practical_chemistry_workflow import initial_snapshot, body, PREVIEW, PROJECT_ID


def project_with_chemistry(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))
    fresh = initial_snapshot()
    complete = inspection_robot_project().model_copy(update={
        "project_id": PROJECT_ID, "name": fresh["projectName"],
        "components": [
            *inspection_robot_project().components,
        ],
    })
    # Machine release test can use a completed separate validated model with
    # the same project identity; actual component remains the original board.
    fresh["machineProject"] = initial_snapshot()["machineProject"]
    created = client.put(f"/v1/projects/{PROJECT_ID}/snapshot",
                         json={"snapshot": fresh, "expected_revision": 0})
    assert created.status_code == 200, created.text
    return store, client, complete


def record_accepted_chemistry(client):
    response = client.post(PREVIEW, json=body())
    assert response.status_code == 200, response.text
    proposal = response.json()
    review = client.post(f"/v1/projects/{PROJECT_ID}/reviews",
                         json=proposal["next_review_request"])
    assert review.status_code == 201, review.text
    review_id = review.json()["review"]["review_id"]
    approval = client.post(f"/v1/projects/{PROJECT_ID}/reviews/{review_id}/decision",
        json={"decision": "accepted", "actor": "synthetic-reviewer"})
    assert approval.status_code == 200, approval.text
    return proposal


def test_project_release_open_without_chemistry_and_blocked_with_screen(tmp_path):
    store, client, machine = project_with_chemistry(tmp_path)
    assert assessment_allows(machine.assess_release(ReleaseState.OPERATIONALLY_AUTHORIZED))
    initial = client.get(f"/v1/projects/{PROJECT_ID}/engineering/release-gate",
                         params={"requested_state":"design_ready"})
    assert initial.status_code == 200, initial.text
    assert initial.json()["chemistry_gate"]["status"] == "not_applicable"
    proposal = record_accepted_chemistry(client)
    snapshot = store.load(PROJECT_ID)["snapshot"]
    model_assessment, chemistry = assess_project_release(
        machine, snapshot, requested=ReleaseState.OPERATIONALLY_AUTHORIZED)
    assert chemistry["blocked"] and not assessment_allows(model_assessment)
    assert model_assessment.achieved_state == ReleaseState.DESIGN_READY
    assert any(b.code == "chemistry_independent_validation_required"
               for b in model_assessment.blockers)
    blocked = client.get(f"/v1/projects/{PROJECT_ID}/engineering/release-gate",
                         params={"requested_state":"build_ready"})
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["allowed"] is False
    assert blocked.json()["chemistry_gate"]["assessment_count"] == 1
    assert not blocked.json()["physical_authority_granted"]


def test_saved_snapshot_cannot_erase_chemistry_record_by_generic_put(tmp_path):
    store, client, _ = project_with_chemistry(tmp_path)
    record_accepted_chemistry(client)
    saved = store.load(PROJECT_ID)
    prior = saved["snapshot"]
    erased = copy.deepcopy(prior)
    erased.pop("practicalChemistryAssessments")
    erased.pop("engineeringFindings")
    attempt = client.put(f"/v1/projects/{PROJECT_ID}/snapshot",
                         json={"snapshot": erased, "expected_revision": 2})
    assert attempt.status_code == 409
    assert "cannot erase" in str(attempt.json()["detail"])
    assert store.load(PROJECT_ID)["revision"] == 2
    assert evaluate_project_chemistry_gate(store.load(PROJECT_ID)["snapshot"],
                                          project_id=PROJECT_ID)["blocked"]


def test_accepted_review_cannot_remove_chemistry_records(tmp_path):
    store, client, _ = project_with_chemistry(tmp_path)
    record_accepted_chemistry(client)
    candidate = copy.deepcopy(store.load(PROJECT_ID)["snapshot"])
    candidate.pop("practicalChemistryAssessments")
    pending = client.post(f"/v1/projects/{PROJECT_ID}/reviews",
                          json={"base_revision":2,"candidate_snapshot":candidate,
                                "created_by":"agent"})
    assert pending.status_code == 201, pending.text
    review = pending.json()["review"]
    outcome = client.post(f"/v1/projects/{PROJECT_ID}/reviews/{review['review_id']}/decision",
                          json={"decision":"accepted", "actor":"synthetic-reviewer"})
    assert outcome.status_code == 409
    assert store.load(PROJECT_ID)["revision"] == 2


def test_tamper_clears_stored_findings_but_gate_stays_blocked(tmp_path):
    store, client, _ = project_with_chemistry(tmp_path)
    record_accepted_chemistry(client)
    dirty = copy.deepcopy(store.load(PROJECT_ID)["snapshot"])
    dirty["engineeringFindings"] = []
    saved = client.put(f"/v1/projects/{PROJECT_ID}/snapshot",
                       json={"snapshot": dirty, "expected_revision":2})
    assert saved.status_code == 200, saved.text
    gate = evaluate_project_chemistry_gate(store.load(PROJECT_ID)["snapshot"],project_id=PROJECT_ID)
    assert gate["blocked"]
    assert "chemistry_release_finding_missing" in {row["code"] for row in gate["blockers"]}


def test_altering_cached_chemistry_decision_does_not_open_gate(tmp_path):
    store, client, _ = project_with_chemistry(tmp_path)
    record_accepted_chemistry(client)
    modified = copy.deepcopy(store.load(PROJECT_ID)["snapshot"])
    modified["practicalChemistryAssessments"][0]["assessment"]["decision"] = "options_for_validation"
    saved = client.put(f"/v1/projects/{PROJECT_ID}/snapshot",
                       json={"snapshot": modified, "expected_revision":2})
    assert saved.status_code == 200
    gate = evaluate_project_chemistry_gate(store.load(PROJECT_ID)["snapshot"],project_id=PROJECT_ID)
    assert gate["blocked"]
    assert "chemistry_integrity_or_authority_failure" in {row["code"] for row in gate["blockers"]}


def test_untrusted_standalone_model_endpoint_is_explicitly_unscoped(tmp_path):
    store, client, machine = project_with_chemistry(tmp_path)
    result = client.post("/v1/machine-projects/assess-release",
                         json={"project":machine.model_dump(mode="json"),
                               "requested_state":"build_ready"})
    assert result.status_code == 200
    assert result.json()["scope"] == "standalone_machine_model_only"
    assert result.json()["persistent_project_chemistry_checked"] is False
    assert result.json()["project_physical_authority_granted"] is False


def test_old_project_revision_cannot_be_used_for_new_authorization(tmp_path):
    store, client, _ = project_with_chemistry(tmp_path)
    record_accepted_chemistry(client)
    response = client.get(f"/v1/projects/{PROJECT_ID}/engineering/release-gate",
                          params={"revision":1,"requested_state":"design_ready"})
    assert response.status_code == 200
    assert response.json()["historical_revision"] is True
    assert response.json()["allowed"] is False
    assert any(e["code"] == "historical_revision_not_authoritative"
               for e in response.json()["assessment"]["blockers"])


def test_orphaned_chemistry_findings_cannot_be_erased_with_project_save(tmp_path):
    store = ProjectStore(tmp_path / "orphan")
    snap = initial_snapshot()
    snap["engineeringFindings"] = [{
        "producer":"practical_chemistry_assessment",
        "category":"release_blocker",
        "text":"Orphaned chemical claim",
    }]
    store.save(PROJECT_ID, snap, expected_revision=0)
    assert evaluate_project_chemistry_gate(snap,project_id=PROJECT_ID)["blocked"]
    clean = initial_snapshot()
    with pytest.raises(RevisionConflict,match="orphaned"):
        store.save(PROJECT_ID,clean,expected_revision=1)


def test_malformed_chemistry_record_cannot_be_erased_with_project_save(tmp_path):
    store = ProjectStore(tmp_path / "invalid")
    snap = initial_snapshot()
    snap["practicalChemistryAssessments"] = {"unexpected":"object"}
    store.save(PROJECT_ID,snap,expected_revision=0)
    assert evaluate_project_chemistry_gate(snap,project_id=PROJECT_ID)["blocked"]
    with pytest.raises(RevisionConflict,match="malformed"):
        store.save(PROJECT_ID,initial_snapshot(),expected_revision=1)


def test_engineering_plan_projection_carries_accepted_chemical_evidence(tmp_path):
    from hardware_splicer.engineering_plan_store import engineering_snapshot
    store, client, _ = project_with_chemistry(tmp_path)
    record_accepted_chemistry(client)
    previous = store.load(PROJECT_ID)["snapshot"]
    plan = {"machine_project":previous["machineProject"],
            "project_name": PROJECT_ID,
            "engineering_readiness":{"scoped_authorized_operations":["bench_power"]}}
    next_snapshot = engineering_snapshot(plan, previous_snapshot=previous)
    assert next_snapshot["practicalChemistryAssessments"] == previous["practicalChemistryAssessments"]
    assert next_snapshot["engineeringFindings"] == previous["engineeringFindings"]
    assert next_snapshot["engineeringReadiness"]["scoped_authorized_operations"] == ["bench_power"]
    # The projection is untrusted, but the shared project gate protects release.
    assert evaluate_project_chemistry_gate(next_snapshot,project_id=PROJECT_ID)["blocked"]


def test_new_replanned_machine_missing_chemical_target_cannot_open_gate(tmp_path):
    from hardware_splicer.engineering_plan_store import engineering_snapshot
    store, client, _ = project_with_chemistry(tmp_path)
    record_accepted_chemistry(client)
    previous = store.load(PROJECT_ID)["snapshot"]
    plan = {
        "machine_project":{"project_id": PROJECT_ID,"name":"Stripped replacement",
                           "purpose":"No component in this new machine"},
        "project_name": PROJECT_ID,
    }
    later = engineering_snapshot(plan, previous_snapshot=previous)
    gate = evaluate_project_chemistry_gate(later,project_id=PROJECT_ID)
    assert gate["blocked"]
    assert any(row["code"] == "chemistry_component_not_in_machine_project"
               for row in gate["blockers"])


def test_actual_replanning_cannot_restore_scoped_physical_authorization(tmp_path):
    from hardware_splicer.engineering_plan_store import save_engineering_plan
    store, client, _ = project_with_chemistry(tmp_path)
    record_accepted_chemistry(client)
    snap = store.load(PROJECT_ID)["snapshot"]
    plan = {
        "schema_version":"hardware_splicer.guided_engineering_plan.v1",
        "project_name":PROJECT_ID,
        "machine_project":snap["machineProject"],
        "engineering_readiness":{
            "scoped_authorized_operations":["bench_power"],
            "physical_scope_authorized":True,
        },
        "scoped_release_assessment":{
            "allowed":True,"allowed_operations":["bench_power"],"status":"authorized",
            "blockers":[],
        },
    }
    saved = save_engineering_plan(store,plan,project_id=PROJECT_ID,expected_revision=2)
    assert saved["revision"] == 3
    new = saved["snapshot"]
    assert new["practicalChemistryAssessments"] == snap["practicalChemistryAssessments"]
    readiness = new["engineeringPlan"]["engineering_readiness"]
    assert readiness["scoped_authorized_operations"] == []
    assert readiness["physical_scope_authorized"] is False
    assert new["engineeringPlan"]["scoped_release_assessment"]["allowed"] is False
    assert evaluate_project_chemistry_gate(new,project_id=PROJECT_ID)["blocked"]
