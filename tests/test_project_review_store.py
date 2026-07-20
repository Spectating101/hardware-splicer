from __future__ import annotations

import json

import pytest

from hardware_splicer.project_review_store import ProjectReviewStore, ReviewConflict
from hardware_splicer.project_store import ProjectStore, RevisionConflict


def snapshot(purpose: str = "Build a safe inspection robot") -> dict:
    return {
        "projectId": "robot",
        "projectName": "Inspection robot",
        "currentStage": "design",
        "mode": "greenfield",
        "graph": {"nodes": [], "edges": []},
        "machineProject": {
            "project_id": "robot",
            "name": "Inspection robot",
            "purpose": purpose,
        },
    }


def test_rejected_review_never_enters_revision_history(tmp_path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reviews = ProjectReviewStore(store)

    review = reviews.create(
        "robot",
        snapshot("Build a safe autonomous inspection robot"),
        base_revision=1,
        created_by="agent",
        note="Expand autonomy requirement",
    )

    assert review["status"] == "pending"
    assert review["summary"]["project_fields_changed"] == 1
    decided = reviews.decide(
        "robot",
        review["review_id"],
        decision="rejected",
        actor="owner",
        note="Autonomy is out of scope",
    )

    assert decided["status"] == "rejected"
    assert decided["decision"]["accepted_revision"] is None
    assert store.load("robot")["revision"] == 1
    assert not (tmp_path / "robot" / "revisions" / "00000002.json").exists()


def test_accepted_review_becomes_exactly_one_linked_revision(tmp_path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reviews = ProjectReviewStore(store)
    review = reviews.create(
        "robot",
        snapshot("Build a safe autonomous inspection robot"),
        base_revision=1,
        created_by="agent",
    )

    decided = reviews.decide(
        "robot",
        review["review_id"],
        decision="accepted",
        actor="owner",
        note="Approved after architecture review",
    )

    assert decided["status"] == "accepted"
    assert decided["decision"]["accepted_revision"] == 2
    assert [event["decision"] for event in decided["events"]] == ["accepting", "accepted"]
    revision = store.load("robot", revision=2)
    assert revision["snapshot"]["machineProject"]["purpose"].startswith("Build a safe autonomous")
    assert revision["metadata"] == {
        "review_id": review["review_id"],
        "review_decision": "accepted",
        "review_actor": "owner",
    }
    rows = reviews.list_revisions("robot")
    assert rows[0]["revision"] == 2
    assert rows[0]["review_id"] == review["review_id"]


def test_acceptance_can_resume_after_crash_before_revision_write(tmp_path, monkeypatch) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reviews = ProjectReviewStore(store)
    review = reviews.create("robot", snapshot("Candidate purpose"), created_by="agent")
    original_save = store.save

    def fail_before_save(*args, **kwargs):
        raise RuntimeError("simulated crash before revision write")

    monkeypatch.setattr(store, "save", fail_before_save)
    with pytest.raises(RuntimeError, match="before revision write"):
        reviews.decide(
            "robot",
            review["review_id"],
            decision="accepted",
            actor="owner",
        )

    interrupted = reviews.get("robot", review["review_id"])
    assert interrupted["status"] == "accepting"
    assert interrupted["decision"]["accepted_revision"] == 2
    assert store.load("robot")["revision"] == 1

    monkeypatch.setattr(store, "save", original_save)
    completed = reviews.decide(
        "robot",
        review["review_id"],
        decision="accepted",
        actor="owner",
    )
    assert completed["status"] == "accepted"
    assert completed["decision"]["accepted_revision"] == 2
    assert store.load("robot")["revision"] == 2


def test_acceptance_reconciles_after_crash_between_revision_and_completion(tmp_path, monkeypatch) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reviews = ProjectReviewStore(store)
    review = reviews.create("robot", snapshot("Candidate purpose"), created_by="agent")
    original_write_event = reviews._write_event

    def fail_completion(project_id, review_id, sequence, event):
        if sequence == 2:
            raise RuntimeError("simulated crash before completion event")
        return original_write_event(project_id, review_id, sequence, event)

    monkeypatch.setattr(reviews, "_write_event", fail_completion)
    with pytest.raises(RuntimeError, match="before completion event"):
        reviews.decide(
            "robot",
            review["review_id"],
            decision="accepted",
            actor="owner",
        )
    assert store.load("robot")["revision"] == 2

    monkeypatch.setattr(reviews, "_write_event", original_write_event)
    recovered = reviews.get("robot", review["review_id"])
    assert recovered["status"] == "accepted"
    assert recovered["decision"]["accepted_revision"] == 2
    assert recovered["decision"]["recovered"] is True
    assert [event["decision"] for event in recovered["events"]] == ["accepting", "accepted"]


def test_stale_review_cannot_overwrite_newer_revision(tmp_path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reviews = ProjectReviewStore(store)
    review = reviews.create(
        "robot",
        snapshot("Candidate purpose"),
        base_revision=1,
        created_by="agent",
    )
    store.save("robot", snapshot("Concurrent owner edit"), expected_revision=1)

    with pytest.raises(RevisionConflict, match="based on revision 1"):
        reviews.decide(
            "robot",
            review["review_id"],
            decision="accepted",
            actor="owner",
        )

    assert reviews.get("robot", review["review_id"])["status"] == "pending"
    assert store.load("robot")["snapshot"]["machineProject"]["purpose"] == "Concurrent owner edit"


def test_decision_is_append_only_and_cannot_be_repeated(tmp_path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reviews = ProjectReviewStore(store)
    review = reviews.create("robot", snapshot("Candidate purpose"), created_by="agent")
    reviews.decide("robot", review["review_id"], decision="rejected", actor="owner")

    with pytest.raises(ReviewConflict, match="already rejected"):
        reviews.decide("robot", review["review_id"], decision="accepted", actor="owner")

    event_path = tmp_path / "robot" / "reviews" / review["review_id"] / "events" / "00000001.json"
    assert json.loads(event_path.read_text())["decision"] == "rejected"
    assert len(list(event_path.parent.glob("*.json"))) == 1


def test_acceptance_retry_requires_same_actor(tmp_path, monkeypatch) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reviews = ProjectReviewStore(store)
    review = reviews.create("robot", snapshot("Candidate purpose"), created_by="agent")
    original_save = store.save

    monkeypatch.setattr(
        store,
        "save",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("crash")),
    )
    with pytest.raises(RuntimeError):
        reviews.decide("robot", review["review_id"], decision="accepted", actor="owner-a")
    monkeypatch.setattr(store, "save", original_save)

    with pytest.raises(ReviewConflict, match="started by 'owner-a'"):
        reviews.decide("robot", review["review_id"], decision="accepted", actor="owner-b")


def test_non_machine_snapshot_changes_are_visible_and_review_gated(tmp_path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reviews = ProjectReviewStore(store)
    candidate = snapshot()
    candidate["graph"] = {"nodes": [{"id": "motor-driver"}], "edges": []}
    candidate["currentStage"] = "verify"

    review = reviews.create("robot", candidate, created_by="agent")

    assert {change["path"] for change in review["snapshot_changes"]} == {
        "currentStage",
        "graph",
    }
    assert review["summary"]["snapshot_fields_changed"] == 2
    assert review["summary"]["review_required"] is True
    assert {flag["path"] for flag in review["review_flags"]} == {
        "currentStage",
        "graph",
    }


def test_review_requires_matching_identity_machine_project_and_change(tmp_path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reviews = ProjectReviewStore(store)

    with pytest.raises(ValueError, match="canonical machineProject"):
        reviews.create("robot", {"projectId": "robot"}, created_by="agent")
    with pytest.raises(ValueError, match="no reviewable changes"):
        reviews.create("robot", snapshot(), created_by="agent")
    mismatched = snapshot("Candidate")
    mismatched["projectId"] = "other"
    with pytest.raises(ValueError, match="persistent project"):
        reviews.create("robot", mismatched, created_by="agent")
