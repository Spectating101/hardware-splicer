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


def test_review_requires_machine_project_and_semantic_change(tmp_path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    reviews = ProjectReviewStore(store)

    with pytest.raises(ValueError, match="canonical machineProject"):
        reviews.create("robot", {"projectId": "robot"}, created_by="agent")
    with pytest.raises(ValueError, match="no semantic machine changes"):
        reviews.create("robot", snapshot(), created_by="agent")
