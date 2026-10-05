from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.project_review_store import ProjectReviewStore
from hardware_splicer.project_store import InvalidProjectId, ProjectStore
from hardware_splicer.project_thread_store import (
    ProjectThreadError,
    ProjectThreadStore,
    ThreadConflict,
    ThreadNotFound,
    ThreadStateError,
    ThreadValidationError,
)


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


def _threads(tmp_path: Path) -> tuple[ProjectStore, ProjectThreadStore]:
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot(), expected_revision=0)
    return store, ProjectThreadStore(store)


def _anchor(**overrides: object) -> dict:
    value = {"revision": 1, "object_id": "mcu", "finding_ref": None, "artifact": None}
    value.update(overrides)
    return value


def _author(kind: str = "human", author_id: str = "owner") -> dict:
    return {"kind": kind, "id": author_id}


def _hash_tree(root: Path, *, exclude_threads: bool = True) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if exclude_threads and relative.parts and relative.parts[0] == "threads":
            continue
        digest.update(str(relative).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_create_list_get_round_trip_and_first_comment_is_seq_1(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    created = threads.create_thread("robot", _anchor(), _author(), "Please check this net.")

    assert created["schema_version"] == "hardware_splicer.review_thread.v1"
    assert created["status"] == "open"
    assert created["comment_count"] == 1
    assert created["thread_id"].startswith("thread-")
    assert "status" not in json.loads(
        (tmp_path / "robot" / "threads" / created["thread_id"] / "thread.json").read_text()
    )
    assert created["events"][0]["seq"] == 1
    assert created["events"][0]["type"] == "comment"
    assert created["events"][0]["author_verified"] is False
    assert created["events"][0]["body"] == "Please check this net."

    listed = threads.list_threads("robot")
    assert listed[0]["thread_id"] == created["thread_id"]
    assert listed[0]["status"] == "open"
    assert listed[0]["comment_count"] == 1
    assert "events" not in listed[0]

    loaded = threads.get_thread("robot", created["thread_id"])
    assert loaded["events"][0]["seq"] == 1
    assert loaded["status"] == "open"


def test_status_derivation_resolve_reopen_and_invalid_transitions(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    created = threads.create_thread("robot", _anchor(), _author(), "Look at this.")

    with pytest.raises(ThreadStateError):
        threads.append_event("robot", created["thread_id"], "reopen", _author(), "too soon")

    resolved = threads.append_event("robot", created["thread_id"], "resolve", _author(), "done")
    assert resolved["type"] == "resolve"
    assert resolved["author_verified"] is False
    assert threads.get_thread("robot", created["thread_id"])["status"] == "resolved"

    with pytest.raises(ThreadStateError):
        threads.append_event("robot", created["thread_id"], "resolve", _author(), "again")

    reopened = threads.append_event("robot", created["thread_id"], "reopen", _author(), "not done")
    assert reopened["type"] == "reopen"
    assert threads.get_thread("robot", created["thread_id"])["status"] == "open"


def test_expected_event_seq_conflict(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    created = threads.create_thread("robot", _anchor(), _author(), "First comment")
    threads.append_event(
        "robot",
        created["thread_id"],
        "comment",
        _author(),
        "Second comment",
        expected_event_seq=1,
    )
    with pytest.raises(ThreadConflict):
        threads.append_event(
            "robot",
            created["thread_id"],
            "comment",
            _author(),
            "Stale write",
            expected_event_seq=1,
        )


def test_anchor_and_author_validation(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)

    with pytest.raises(ThreadValidationError, match="object_id, finding_ref, or artifact"):
        threads.create_thread(
            "robot",
            {"revision": 1, "object_id": None, "finding_ref": None, "artifact": None},
            _author(),
            "missing target",
        )
    with pytest.raises(ThreadValidationError, match="at least 1"):
        threads.create_thread("robot", _anchor(revision=0), _author(), "rev 0")
    with pytest.raises(ThreadValidationError, match="above latest"):
        threads.create_thread("robot", _anchor(revision=2), _author(), "too new")
    with pytest.raises(ThreadValidationError, match="\\.\\."):
        threads.create_thread(
            "robot",
            _anchor(
                object_id=None,
                artifact={"relative": "../secret.kicad_sch", "kind": "schematic"},
            ),
            _author(),
            "traversal",
        )
    with pytest.raises(ThreadValidationError, match="at most 4000"):
        threads.create_thread("robot", _anchor(), _author(), "x" * 4001)
    with pytest.raises(ThreadValidationError, match="required"):
        threads.create_thread("robot", _anchor(), _author(), "   ")
    with pytest.raises(ThreadValidationError, match="author.kind"):
        threads.create_thread("robot", _anchor(), {"kind": "bot", "id": "x"}, "hello")
    with pytest.raises(ThreadValidationError, match="agent"):
        threads.create_thread("robot", _anchor(), {"kind": "agent", "id": ""}, "hello")
    with pytest.raises(ThreadValidationError, match="author.id"):
        threads.create_thread("robot", _anchor(), {"kind": "agent"}, "hello")


def test_authority_keys_rejected_and_author_verified_is_false(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    with pytest.raises(ThreadValidationError):
        threads.create_thread(
            "robot",
            _anchor(),
            {"kind": "human", "id": "a", "authorized": True},
            "nope",
        )
    with pytest.raises(ThreadValidationError):
        threads.create_thread("robot", {**_anchor(), "release": True}, _author(), "nope")
    with pytest.raises(ThreadValidationError):
        threads.create_thread("robot", _anchor(), _author(), "nope", status="accepted")

    created = threads.create_thread("robot", _anchor(), _author("agent", "gpt-test"), "Mention @owner")
    reply = threads.append_event("robot", created["thread_id"], "comment", _author(), "ack")
    assert created["events"][0]["author_verified"] is False
    assert reply["author_verified"] is False
    for event in threads.get_thread("robot", created["thread_id"])["events"]:
        assert event["author_verified"] is False


def test_path_traversal_ids_rejected_and_do_not_write_outside_root(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    siblings_before = {path.name for path in tmp_path.parent.iterdir()}

    for unsafe in ("../x", "/absolute", ".", "", "robot/child"):
        with pytest.raises(InvalidProjectId):
            threads.create_thread(unsafe, _anchor(), _author(), "hello")
        with pytest.raises(InvalidProjectId):
            threads.list_threads(unsafe)
        with pytest.raises(InvalidProjectId):
            threads.get_thread("robot", unsafe)
        with pytest.raises(InvalidProjectId):
            threads.append_event("robot", unsafe, "comment", _author(), "hello")

    assert {path.name for path in tmp_path.parent.iterdir()} == siblings_before
    assert not (tmp_path.parent / "x").exists()
    assert not (tmp_path / "x").exists()


def test_list_filters_by_object_id_and_status(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    mcu = threads.create_thread("robot", _anchor(object_id="mcu"), _author(), "MCU note")
    motor = threads.create_thread("robot", _anchor(object_id="motor"), _author(), "Motor note")
    threads.append_event("robot", motor["thread_id"], "resolve", _author(), "fixed")

    by_object = threads.list_threads("robot", object_id="mcu")
    assert [row["thread_id"] for row in by_object] == [mcu["thread_id"]]

    open_rows = threads.list_threads("robot", status="open")
    assert [row["thread_id"] for row in open_rows] == [mcu["thread_id"]]
    resolved_rows = threads.list_threads("robot", status="resolved")
    assert [row["thread_id"] for row in resolved_rows] == [motor["thread_id"]]

    listed = threads.list_threads("robot")
    assert [row["thread_id"] for row in listed] == [motor["thread_id"], mcu["thread_id"]]


def test_threads_never_mutate_project_or_review_bytes(tmp_path: Path) -> None:
    store, threads = _threads(tmp_path)
    reviews = ProjectReviewStore(store)
    review = reviews.create(
        "robot",
        snapshot("Build a safe autonomous inspection robot"),
        created_by="agent",
    )
    project_dir = tmp_path / "robot"
    before_hash = _hash_tree(project_dir)
    before_revision = store.load("robot")["revision"]
    before_manifest = (project_dir / "project.json").read_bytes()
    before_revisions = {
        path.name: path.read_bytes()
        for path in (project_dir / "revisions").glob("*.json")
    }
    review_dir = project_dir / "reviews" / review["review_id"]
    before_review = {
        path.relative_to(review_dir).as_posix(): path.read_bytes()
        for path in review_dir.rglob("*")
        if path.is_file()
    }

    created = threads.create_thread("robot", _anchor(), _author(), "Discuss the change")
    threads.append_event("robot", created["thread_id"], "comment", _author(), "Reply")
    threads.append_event("robot", created["thread_id"], "resolve", _author(), "Closed")

    assert store.load("robot")["revision"] == before_revision
    assert (project_dir / "project.json").read_bytes() == before_manifest
    assert {
        path.name: path.read_bytes()
        for path in (project_dir / "revisions").glob("*.json")
    } == before_revisions
    assert {
        path.relative_to(review_dir).as_posix(): path.read_bytes()
        for path in review_dir.rglob("*")
        if path.is_file()
    } == before_review
    assert _hash_tree(project_dir) == before_hash
    assert reviews.get("robot", review["review_id"])["status"] == "pending"


def test_event_files_are_never_rewritten(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    created = threads.create_thread("robot", _anchor(), _author(), "First")
    event_one = tmp_path / "robot" / "threads" / created["thread_id"] / "events" / "00000001.json"
    before_bytes = event_one.read_bytes()
    before_mtime = event_one.stat().st_mtime_ns

    threads.append_event("robot", created["thread_id"], "comment", _author(), "Second")

    assert event_one.read_bytes() == before_bytes
    assert event_one.stat().st_mtime_ns == before_mtime
    event_two = event_one.with_name("00000002.json")
    assert event_two.is_file()
    assert json.loads(event_two.read_text())["seq"] == 2


def test_create_thread_is_crash_safe_when_thread_json_write_fails(tmp_path: Path, monkeypatch) -> None:
    _store, threads = _threads(tmp_path)

    def fail_commit(path: Path, value) -> None:
        raise RuntimeError("simulated crash before thread.json commit")

    monkeypatch.setattr(
        "hardware_splicer.project_thread_store._atomic_write_json",
        fail_commit,
    )
    with pytest.raises(RuntimeError, match="before thread.json commit"):
        threads.create_thread("robot", _anchor(), _author(), "First comment")

    orphan_dirs = [path for path in (tmp_path / "robot" / "threads").iterdir() if path.is_dir()]
    assert orphan_dirs
    orphan_id = orphan_dirs[0].name
    assert (orphan_dirs[0] / "events" / "00000001.json").is_file()
    assert not (orphan_dirs[0] / "thread.json").exists()
    assert threads.list_threads("robot") == []
    with pytest.raises(ThreadNotFound):
        threads.get_thread("robot", orphan_id)

    monkeypatch.undo()
    created = threads.create_thread("robot", _anchor(), _author(), "Recovered create")
    assert created["events"][0]["seq"] == 1
    assert threads.list_threads("robot")[0]["thread_id"] == created["thread_id"]


def test_list_threads_skips_orphans_but_raises_on_corrupt_records(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    orphan = tmp_path / "robot" / "threads" / "thread-orphan00000001"
    (orphan / "events").mkdir(parents=True)
    (orphan / "events" / "00000001.json").write_text("{}\n", encoding="utf-8")
    assert threads.list_threads("robot") == []
    with pytest.raises(ThreadNotFound):
        threads.get_thread("robot", "thread-orphan00000001")

    created = threads.create_thread("robot", _anchor(), _author(), "Visible thread")
    thread_path = tmp_path / "robot" / "threads" / created["thread_id"] / "thread.json"
    thread_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ProjectThreadError):
        threads.list_threads("robot")
    with pytest.raises(ProjectThreadError):
        threads.get_thread("robot", created["thread_id"])

    thread_path.write_text(
        json.dumps(
            {
                "schema_version": "hardware_splicer.review_thread.v1",
                "thread_id": created["thread_id"],
                "project_id": "robot",
                "anchor": {"revision": 1, "object_id": "mcu", "finding_ref": None, "artifact": None},
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    event_path = tmp_path / "robot" / "threads" / created["thread_id"] / "events" / "00000001.json"
    event_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ProjectThreadError):
        threads.list_threads("robot")
    with pytest.raises(ProjectThreadError):
        threads.get_thread("robot", created["thread_id"])


def test_expected_event_seq_requires_int_or_none(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    created = threads.create_thread("robot", _anchor(), _author(), "First")
    for bad in (1.2, "1", True):
        with pytest.raises(ThreadValidationError):
            threads.append_event(
                "robot",
                created["thread_id"],
                "comment",
                _author(),
                "stale type",
                expected_event_seq=bad,
            )
    appended = threads.append_event(
        "robot",
        created["thread_id"],
        "comment",
        _author(),
        "None is allowed",
        expected_event_seq=None,
    )
    assert appended["seq"] == 2


def test_artifact_relative_rejects_windows_and_unc_absolute_paths(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    for relative in (
        r"C:\design\board.kicad_pcb",
        "C:/x",
        r"\\server\share\x",
        "/etc/x",
    ):
        with pytest.raises(ThreadValidationError, match="absolute"):
            threads.create_thread(
                "robot",
                _anchor(
                    object_id=None,
                    artifact={"relative": relative, "kind": "pcb"},
                ),
                _author(),
                "absolute artifact",
            )


def test_body_rejects_control_characters_but_keeps_newlines_and_tabs(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    with pytest.raises(ThreadValidationError):
        threads.create_thread("robot", _anchor(), _author(), "bad\x00null")
    with pytest.raises(ThreadValidationError):
        threads.create_thread("robot", _anchor(), _author(), "bad\x1bescape")
    body = "Please review:\n\t- net A\n\t- net B"
    created = threads.create_thread("robot", _anchor(), _author(), body)
    assert created["events"][0]["body"] == body


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _event_record(seq: int, **overrides: object) -> dict:
    record = {
        "seq": seq,
        "type": "comment",
        "author": {"kind": "human", "id": "owner"},
        "author_verified": False,
        "body": "note",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    record.update(overrides)
    return record


def test_structurally_corrupt_thread_and_event_records_raise(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    created = threads.create_thread("robot", _anchor(), _author(), "Valid start")
    thread_dir = tmp_path / "robot" / "threads" / created["thread_id"]
    thread_path = thread_dir / "thread.json"
    event_one = thread_dir / "events" / "00000001.json"
    valid_thread = json.loads(thread_path.read_text(encoding="utf-8"))
    valid_event = json.loads(event_one.read_text(encoding="utf-8"))

    _write_json(thread_path, {})
    with pytest.raises(ProjectThreadError):
        threads.get_thread("robot", created["thread_id"])
    with pytest.raises(ProjectThreadError):
        threads.list_threads("robot")

    _write_json(thread_path, {**valid_thread, "schema_version": "hardware_splicer.review_thread.v0"})
    with pytest.raises(ProjectThreadError):
        threads.get_thread("robot", created["thread_id"])

    _write_json(thread_path, {**valid_thread, "thread_id": "thread-other00000001"})
    with pytest.raises(ProjectThreadError):
        threads.get_thread("robot", created["thread_id"])

    _write_json(thread_path, valid_thread)
    _write_json(event_one, {})
    with pytest.raises(ProjectThreadError):
        threads.get_thread("robot", created["thread_id"])

    _write_json(event_one, {**valid_event, "seq": 9})
    with pytest.raises(ProjectThreadError):
        threads.get_thread("robot", created["thread_id"])

    _write_json(event_one, valid_event)
    _write_json(thread_dir / "events" / "00000003.json", _event_record(3))
    with pytest.raises(ProjectThreadError):
        threads.get_thread("robot", created["thread_id"])
    (thread_dir / "events" / "00000003.json").unlink()

    _write_json(event_one, {**valid_event, "author_verified": True})
    with pytest.raises(ProjectThreadError):
        threads.get_thread("robot", created["thread_id"])
    with pytest.raises(ProjectThreadError):
        threads.list_threads("robot")


def test_committed_thread_without_event_1_is_corrupt(tmp_path: Path) -> None:
    _store, threads = _threads(tmp_path)
    created = threads.create_thread("robot", _anchor(), _author(), "Committed")
    event_one = tmp_path / "robot" / "threads" / created["thread_id"] / "events" / "00000001.json"
    event_one.unlink()
    with pytest.raises(ProjectThreadError):
        threads.get_thread("robot", created["thread_id"])
    with pytest.raises(ProjectThreadError):
        threads.list_threads("robot")


def test_symlink_boundaries_reject_all_operations_and_do_not_write_targets(tmp_path: Path) -> None:
    planted_id = "thread-aaaaaaaaaaaaaaaa"

    def assert_ops_raise(threads: ProjectThreadStore, thread_id: str, target: Path) -> None:
        before_names = sorted(path.name for path in target.iterdir()) if target.is_dir() else None
        before_bytes = target.read_bytes() if target.is_file() else None
        with pytest.raises(ProjectThreadError):
            threads.create_thread("robot", _anchor(), _author(), "must not escape")
        with pytest.raises(ProjectThreadError):
            threads.list_threads("robot")
        with pytest.raises(ProjectThreadError):
            threads.get_thread("robot", thread_id)
        with pytest.raises(ProjectThreadError):
            threads.append_event("robot", thread_id, "comment", _author(), "must not escape")
        if target.is_dir():
            assert sorted(path.name for path in target.iterdir()) == before_names
            assert list(target.iterdir()) == []
        else:
            assert target.read_bytes() == before_bytes

    _store, threads = _threads(tmp_path)
    outside_threads = tmp_path / "outside-threads"
    outside_threads.mkdir()
    (tmp_path / "robot" / "threads").symlink_to(outside_threads)
    assert_ops_raise(threads, planted_id, outside_threads)

    (tmp_path / "robot" / "threads").unlink()
    (tmp_path / "robot" / "threads").mkdir()
    outside_thread = tmp_path / "outside-thread"
    outside_thread.mkdir()
    (tmp_path / "robot" / "threads" / planted_id).symlink_to(outside_thread)
    assert_ops_raise(threads, planted_id, outside_thread)

    (tmp_path / "robot" / "threads" / planted_id).unlink()
    created = threads.create_thread("robot", _anchor(), _author(), "real thread")
    thread_dir = tmp_path / "robot" / "threads" / created["thread_id"]
    events_dir = thread_dir / "events"
    events_dir.rename(tmp_path / "events-backup")
    outside_events = tmp_path / "outside-events"
    outside_events.mkdir()
    events_dir.symlink_to(outside_events)
    assert_ops_raise(threads, created["thread_id"], outside_events)

    events_dir.unlink()
    (tmp_path / "events-backup").rename(events_dir)
    thread_json = thread_dir / "thread.json"
    backup_json = tmp_path / "thread-json-backup"
    thread_json.rename(backup_json)
    outside_json = tmp_path / "outside-thread.json"
    outside_json.write_text("untouched\n", encoding="utf-8")
    thread_json.symlink_to(outside_json)
    assert_ops_raise(threads, created["thread_id"], outside_json)

    thread_json.unlink()
    backup_json.rename(thread_json)
    event_one = events_dir / "00000001.json"
    backup_event = tmp_path / "event-backup.json"
    event_one.rename(backup_event)
    outside_event = tmp_path / "outside-event.json"
    outside_event.write_text("untouched-event\n", encoding="utf-8")
    event_one.symlink_to(outside_event)
    assert_ops_raise(threads, created["thread_id"], outside_event)
