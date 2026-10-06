from __future__ import annotations

from pathlib import Path

import pytest

from hardware_splicer.project_events import diff_states, project_state

try:
    import pytest_timeout  # noqa: F401

    pytestmark = pytest.mark.timeout(10)
except ImportError:
    pytestmark = []

from hardware_splicer.project_review_store import ProjectReviewStore
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.project_thread_store import ProjectThreadStore


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


def _empty() -> dict:
    return {"revision": 0, "threads": {}, "reviews": {}, "pins": []}


def test_missing_project_dir_is_empty_state(tmp_path: Path) -> None:
    assert project_state(tmp_path / "missing") == _empty()


def test_state_and_diff_from_real_stores(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    project_dir = tmp_path / "robot"
    assert project_state(project_dir) == _empty()

    store.save("robot", snapshot(), expected_revision=0)
    after_rev1 = project_state(project_dir)
    assert after_rev1["revision"] == 1
    assert after_rev1["threads"] == {}
    assert after_rev1["reviews"] == {}
    assert after_rev1["pins"] == []
    assert diff_states(_empty(), after_rev1) == [
        {"type": "revision.saved", "id": "1", "seq": 1}
    ]

    store.save("robot", snapshot("Build a safer inspection robot"), expected_revision=1)
    after_rev2 = project_state(project_dir)
    assert after_rev2["revision"] == 2
    assert diff_states(after_rev1, after_rev2) == [
        {"type": "revision.saved", "id": "2", "seq": 2}
    ]

    threads = ProjectThreadStore(store)
    first = threads.create_thread(
        "robot",
        {"revision": 2, "object_id": "mcu"},
        {"kind": "human", "id": "owner"},
        "Please review this net.",
    )
    second = threads.create_thread(
        "robot",
        {"revision": 2, "object_id": "power"},
        {"kind": "human", "id": "owner"},
        "Check the rail.",
    )
    after_threads = project_state(project_dir)
    assert after_threads["threads"] == {
        first["thread_id"]: 1,
        second["thread_id"]: 1,
    }
    created = diff_states(after_rev2, after_threads)
    assert [row["type"] for row in created] == ["thread.created", "thread.created"]
    assert [row["id"] for row in created] == sorted(
        [first["thread_id"], second["thread_id"]]
    )
    assert all(row["seq"] is None for row in created)

    threads.append_event(
        "robot",
        first["thread_id"],
        "comment",
        {"kind": "human", "id": "owner"},
        "Follow up.",
    )
    after_reply = project_state(project_dir)
    assert after_reply["threads"][first["thread_id"]] == 2
    assert diff_states(after_threads, after_reply) == [
        {"type": "thread.event", "id": first["thread_id"], "seq": 2}
    ]

    reviews = ProjectReviewStore(store)
    review = reviews.create(
        "robot",
        snapshot("Build a safe autonomous inspection robot"),
        base_revision=2,
        created_by="agent",
        note="Expand autonomy",
    )
    after_open = project_state(project_dir)
    assert after_open["reviews"] == {review["review_id"]: 0}
    assert diff_states(after_reply, after_open) == [
        {"type": "review.opened", "id": review["review_id"], "seq": None}
    ]

    reviews.decide("robot", review["review_id"], decision="rejected", actor="owner")
    after_decision = project_state(project_dir)
    assert after_decision["reviews"][review["review_id"]] == 1
    assert diff_states(after_open, after_decision) == [
        {"type": "review.event", "id": review["review_id"], "seq": 1}
    ]

    pin_dir = project_dir / "artifact_pins"
    pin_dir.mkdir()
    (pin_dir / "00000002.json").write_text("{}\n", encoding="utf-8")
    (pin_dir / "00000001.json").write_text("{}\n", encoding="utf-8")
    after_pins = project_state(project_dir)
    assert after_pins["pins"] == [1, 2]
    assert diff_states(after_decision, after_pins) == [
        {"type": "artifact.pinned", "id": "1", "seq": 1},
        {"type": "artifact.pinned", "id": "2", "seq": 2},
    ]

    combined = diff_states(_empty(), after_pins)
    types = [row["type"] for row in combined]
    assert types == (
        ["revision.saved", "revision.saved"]
        + ["thread.created", "thread.created"]
        + ["thread.event"]
        + ["review.opened", "review.event"]
        + ["artifact.pinned", "artifact.pinned"]
    )
    assert combined[0]["id"] == "1"
    assert combined[1]["id"] == "2"
    thread_created = [row for row in combined if row["type"] == "thread.created"]
    assert [row["id"] for row in thread_created] == sorted(
        [first["thread_id"], second["thread_id"]]
    )


def test_junk_symlinks_and_partial_files_are_ignored(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    project_dir = tmp_path / "robot"
    threads = ProjectThreadStore(store)
    created = threads.create_thread(
        "robot",
        {"revision": 1, "object_id": "mcu"},
        {"kind": "human", "id": "owner"},
        "Keep this.",
    )
    reviews = ProjectReviewStore(store)
    review = reviews.create(
        "robot",
        snapshot("Build a documented inspection robot"),
        base_revision=1,
        created_by="agent",
    )

    revisions = project_dir / "revisions"
    (revisions / "not-a-revision.json").write_text("{}\n", encoding="utf-8")
    (revisions / "00000001.json.tmp").write_text("{}\n", encoding="utf-8")
    (revisions / ".00000009.json.partial.tmp").write_text("{}\n", encoding="utf-8")
    (revisions / "00000002.json").symlink_to(revisions / "00000001.json")

    thread_root = project_dir / "threads"
    (thread_root / "readme.txt").write_text("nope\n", encoding="utf-8")
    (thread_root / "link-thread").symlink_to(thread_root / created["thread_id"])
    events = thread_root / created["thread_id"] / "events"
    (events / "notes.txt").write_text("ignore\n", encoding="utf-8")
    (events / "00000002.json").symlink_to(events / "00000001.json")
    (events / ".00000003.json.tmp").write_text("{}\n", encoding="utf-8")

    review_root = project_dir / "reviews"
    (review_root / "orphan.json").write_text("{}\n", encoding="utf-8")
    (review_root / "link-review").symlink_to(review_root / review["review_id"])
    events_dir = review_root / review["review_id"] / "events"
    events_dir.mkdir()
    (events_dir / "00000001.json").write_text("{}\n", encoding="utf-8")
    (events_dir / "00000002.json").symlink_to(events_dir / "00000001.json")

    pins = project_dir / "artifact_pins"
    pins.mkdir()
    (pins / "pin-notes.txt").write_text("nope\n", encoding="utf-8")
    (pins / "00000001.json").write_text("{}\n", encoding="utf-8")
    (pins / "00000002.json").symlink_to(pins / "00000001.json")
    (pins / ".00000003.json.tmp").write_text("{}\n", encoding="utf-8")

    (project_dir / "threads-link").symlink_to(thread_root)

    state = project_state(project_dir)
    assert state["revision"] == 1
    assert state["threads"] == {created["thread_id"]: 1}
    assert state["reviews"] == {review["review_id"]: 1}
    assert state["pins"] == [1]


def test_identical_states_diff_empty() -> None:
    state = {"revision": 3, "threads": {"thread-a": 2}, "reviews": {"review-a": 1}, "pins": [1, 3]}
    assert diff_states(state, dict(state)) == []
    assert diff_states(state, {"revision": 3, "threads": {"thread-a": 2}, "reviews": {"review-a": 1}, "pins": [3, 1]}) == []
