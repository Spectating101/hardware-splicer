"""The review packet: a deterministic, hash-bound report of what a revision holds. It reports and changes nothing."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.review_packet import NOT_ESTABLISHED, verify_review_packet

REF = Path(__file__).resolve().parents[1] / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
TOKEN = "operator-secret-do-not-leak"


def _snapshot(build: Path) -> dict:
    return {
        "projectId": "robot",
        "projectName": "Robot",
        "currentStage": "design",
        "buildDir": str(build),
        "machineProject": {"project_id": "robot", "name": "Robot", "purpose": "Report what a revision holds"},
        "engineeringAiSessions": [
            {
                "session_id": "session-1",
                "provider": "mock",
                "model": "fixture-v1",
                "actions": [
                    {
                        "action_id": "action-failed-compose",
                        "action_type": "run_compose",
                        "status": "failed",
                        "tool_result": {"status": "failed", "error": {"message": "Compose failed."}},
                    }
                ],
            }
        ],
    }


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_BUILD_FILE_ROOTS", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_KICAD_CLI", raising=False)
    monkeypatch.setenv("PATH", "/var/empty-hs-packet-path")
    monkeypatch.setenv(
        "HARDWARE_SPLICER_OPERATOR_TOKENS",
        json.dumps({hash_operator_token(TOKEN): {"id": "alice", "kind": "human"}}),
    )
    build = tmp_path / "build"
    (build / "build_compilation").mkdir(parents=True)
    for source in REF.glob("spi_flash_adapter_v1.kicad_*"):
        shutil.copy(source, build / "build_compilation" / source.name)
    store = ProjectStore(tmp_path / "store")
    api = TestClient(create_product_app(store))
    assert api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(build), "expected_revision": 0}).status_code == 200
    return api, store, tmp_path


def _packet(api: TestClient, **query) -> dict:
    response = api.get("/v1/projects/robot/review-packet", params=query)
    assert response.status_code == 200, response.text
    return response.json()["packet"]


def _tree(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def _propose(api: TestClient, note: str = "turn it") -> dict:
    created = api.post(
        "/v1/projects/robot/candidates",
        json={"base_revision": 1, "kind": "schematic", "ops": [{"op": "rotate", "ref": "U1", "degrees": 90}], "author": "Bob", "note": note},
    )
    assert created.status_code == 201, created.text
    return created.json()["candidate"]


def test_the_packet_says_what_the_revision_holds_and_what_it_does_not_establish(world) -> None:
    api, _store, _root = world
    packet = _packet(api)

    assert packet["schema_version"] == "hardware_splicer.review_packet.v1"
    assert packet["project"]["project_id"] == "robot" and packet["project"]["revision"] == 1
    assert packet["not_established"] == list(NOT_ESTABLISHED)
    assert "does not open" in packet["authority"]
    # The hashes of the files the revision kept are the hashes it recorded.
    pin = api.get("/v1/projects/robot/revisions/1/artifacts").json()["pin"]["artifacts"]
    assert packet["retained_files"]["status"] == "retained"
    for kind in ("schematic", "pcb"):
        assert packet["retained_files"]["files"][kind]["sha256"] == pin[kind]["sha256"]
    assert verify_review_packet(packet)


def test_the_packet_reports_the_same_findings_as_the_findings_route(world) -> None:
    api, _store, _root = world
    packet = _packet(api)
    served = api.get("/v1/projects/robot/findings").json()["findings"]

    assert packet["findings"]["total"] == len(served) > 0
    assert [item["finding_id"] for item in packet["findings"]["items"]] == [row["finding_id"] for row in served]
    # How each was established travels with it, including that a stored record has not been attested by the server.
    failed = next(item for item in packet["findings"]["items"] if item["category"] == "failed_check")
    assert failed["provenance"]["authority_ceiling"] == "observed"
    assert failed["provenance"]["attested"] is False
    assert packet["findings"]["attested"] == sum(1 for item in packet["findings"]["items"] if item["provenance"]["attested"])


def test_proposals_and_their_decisions_are_in_the_packet_and_only_for_this_revision(world) -> None:
    api, _store, _root = world
    first = _propose(api, "turn it")
    second = _propose(api, "turn it again")
    decided = api.post(
        f"/v1/projects/robot/candidates/{second['candidate_id']}/decision",
        json={"decision": "rejected", "note": "not now"},
        headers={"X-HS-Operator-Token": TOKEN},
    )
    assert decided.status_code == 200, decided.text

    packet = _packet(api)
    by_id = {item["candidate_id"]: item for item in packet["proposals"]["items"]}
    assert set(by_id) == {first["candidate_id"], second["candidate_id"]}
    assert by_id[first["candidate_id"]]["decision"]["status"] == "pending"
    assert by_id[first["candidate_id"]]["created_by_verified"] is False
    assert by_id[second["candidate_id"]]["decision"] == {"status": "rejected", "decided_by": "alice", "note": "not now", "accepted_revision": None, "out_of_date": False}
    assert (packet["proposals"]["pending"], packet["proposals"]["rejected"], packet["proposals"]["accepted"]) == (1, 1, 0)
    assert by_id[first["candidate_id"]]["operations"][0]["op"] == "rotate"


def test_discussion_is_reported_with_who_was_confirmed_and_who_was_not(world) -> None:
    api, _store, _root = world
    opened = api.post(
        "/v1/projects/robot/threads",
        json={"anchor": {"revision": 1, "object_id": "mcu"}, "author": {"kind": "human", "id": "typed-name"}, "body": "Check this net."},
    )
    assert opened.status_code == 201, opened.text
    replied = api.post(
        f"/v1/projects/robot/threads/{opened.json()['thread']['thread_id']}/events",
        json={"type": "comment", "body": "Checked.", "author": {"kind": "human", "id": "alice"}},
        headers={"X-HS-Operator-Token": TOKEN},
    )
    assert replied.status_code in (200, 201), replied.text

    discussion = _packet(api)["discussion"]
    assert (discussion["total"], discussion["open"], discussion["resolved"]) == (1, 1, 0)
    events = discussion["threads"][0]["events"]
    assert [event["author_verified"] for event in events] == [False, True]
    assert events[0]["author"]["id"] == "typed-name"
    assert discussion["threads"][0]["about_this_revision"] is True


def test_the_same_state_gives_the_same_packet_and_a_change_changes_its_hash(world) -> None:
    api, _store, _root = world
    one = api.get("/v1/projects/robot/review-packet").content
    two = api.get("/v1/projects/robot/review-packet").content
    assert one == two
    md_one = api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).content
    assert md_one == api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).content

    before = _packet(api)["integrity"]["packet_sha256"]
    _propose(api)
    after = _packet(api)
    assert after["integrity"]["packet_sha256"] != before
    assert verify_review_packet(after)
    tampered = json.loads(json.dumps(after))
    tampered["proposals"]["pending"] = 99
    assert not verify_review_packet(tampered)


def test_the_markdown_is_readable_and_says_what_it_does_not_prove_and_leaks_no_credential(world) -> None:
    api, _store, _root = world
    second = _propose(api, "turn the translator")
    api.post(f"/v1/projects/robot/candidates/{second['candidate_id']}/decision", json={"decision": "rejected"}, headers={"X-HS-Operator-Token": TOKEN})

    response = api.get("/v1/projects/robot/review-packet", params={"format": "markdown"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert 'filename="robot-r1-review-packet.md"' in response.headers["content-disposition"]
    text = response.text
    assert text.startswith("# Review packet: Robot")
    assert "## What this packet does not establish" in text
    for line in NOT_ESTABLISHED:
        assert line in text
    assert second["candidate_id"] in text and "Rejected by alice" in text
    assert "turn the translator" in text
    # No credential, and nothing that reads as approval.
    assert TOKEN not in text and TOKEN not in response.headers.get("content-disposition", "")
    assert TOKEN not in json.dumps(_packet(api))
    for claim in ("approved for fabrication", "release-ready", "fabrication-ready", "verified correct"):
        assert claim not in text.lower()


def test_building_a_packet_writes_nothing_and_does_not_repair_a_damaged_store(world) -> None:
    api, store, tmp_path = world
    second = tmp_path / "build2"
    (second / "build_compilation").mkdir(parents=True)
    for source in REF.glob("spi_flash_adapter_v1.kicad_*"):
        shutil.copy(source, second / "build_compilation" / source.name)
    assert api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(second), "expected_revision": 1}).status_code == 200
    store._revision_path("robot", 2).write_text("{ damaged", encoding="utf-8")
    before = (_tree(store.root), _tree(tmp_path))

    packet = _packet(api)
    assert packet["project"]["revision"] == 1
    assert api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).status_code == 200

    assert (_tree(store.root), _tree(tmp_path)) == before
    assert not list(store.root.rglob("*.corrupt"))


def test_a_specific_revision_is_asked_for_by_number_and_bad_requests_are_refused(world) -> None:
    api, _store, _root = world
    assert _packet(api, revision=1)["project"]["revision"] == 1
    assert api.get("/v1/projects/robot/review-packet", params={"revision": 9}).status_code == 404
    assert api.get("/v1/projects/robot/review-packet", params={"revision": 0}).status_code == 422
    refused = api.get("/v1/projects/robot/review-packet", params={"format": "pdf"})
    assert refused.status_code == 422 and refused.json()["detail"]["type"] == "invalid_request"
    assert api.get("/v1/projects/nope/review-packet").status_code == 404


def test_a_revision_with_no_retained_files_says_so_instead_of_inventing_hashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    api = TestClient(create_product_app(ProjectStore(tmp_path / "store")))
    snapshot = {"projectId": "robot", "projectName": "Robot", "currentStage": "design", "machineProject": {"project_id": "robot", "name": "Robot", "purpose": "x"}}
    assert api.put("/v1/projects/robot/snapshot", json={"snapshot": snapshot, "expected_revision": 0}).status_code == 200

    packet = _packet(api)
    assert packet["retained_files"]["status"] == "not_retained"
    assert packet["retained_files"]["files"] == {"schematic": None, "pcb": None}
    assert "No KiCad files are retained" in api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).text
