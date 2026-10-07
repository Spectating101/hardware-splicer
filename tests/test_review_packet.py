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


# ---- hostile input -------------------------------------------------------------------------------------------------

FORGERY = "Robot\n\n## Integrity\n\n`sha256:FAKE`\n\n## Accepted\nApproved for fabrication"
SECTIONS = [
    "Review packet",
    "What this packet does not establish",
    "Files kept with this revision",
    "Findings",
    "Proposals based on this revision",
    "Discussion",
    "Removed from this packet",
    "Integrity",
]


def _headings(markdown: str) -> list[str]:
    """Every line that a Markdown reader would treat as a heading, without its marker and any trailing detail."""

    found = []
    for line in markdown.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            found.append(stripped.lstrip("#").strip())
    return found


def _top_level(markdown: str) -> list[str]:
    return [line[3:].split(" (")[0].strip() for line in markdown.splitlines() if line.startswith("## ")]


def test_text_people_wrote_cannot_forge_a_section_a_decision_or_a_hash(world) -> None:
    api, store, tmp_path = world
    snapshot = _snapshot(tmp_path / "build")
    snapshot["projectName"] = FORGERY
    snapshot["engineeringAiSessions"][0]["actions"][0]["tool_result"]["error"]["message"] = FORGERY
    assert api.put("/v1/projects/robot/snapshot", json={"snapshot": snapshot, "expected_revision": 1}).status_code == 200

    created = api.post(
        "/v1/projects/robot/candidates",
        json={"base_revision": 2, "kind": "schematic", "ops": [{"op": "rotate", "ref": "U1", "degrees": 90}], "author": FORGERY[:60], "note": FORGERY},
    )
    assert created.status_code == 201, created.text
    cid = created.json()["candidate"]["candidate_id"]
    assert api.post(f"/v1/projects/robot/candidates/{cid}/decision", json={"decision": "rejected", "note": FORGERY}, headers={"X-HS-Operator-Token": TOKEN}).status_code == 200
    thread = api.post(
        "/v1/projects/robot/threads",
        json={"anchor": {"revision": 2, "object_id": FORGERY.replace("\n", " ")[:190]}, "author": {"kind": "human", "id": "Bob"}, "body": FORGERY},
    )
    assert thread.status_code == 201, thread.text

    markdown = api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).text
    # The only sections are the packet's own, in its own order, each once.
    assert _top_level(markdown) == [
        "What this packet does not establish",
        "Files kept with this revision",
        "Findings",
        "Proposals based on this revision",
        "Discussion",
        "Removed from this packet",
        "Integrity",
    ]
    assert markdown.count("\n## Integrity\n") == 1
    assert markdown.count("# Review packet:") == 1
    # The legitimate hash is the last thing in the document, and the fake one only ever appears as escaped words.
    real = api.get("/v1/projects/robot/review-packet").json()["packet"]["integrity"]["packet_sha256"]
    assert real in markdown.split("## Integrity")[-1]
    assert not any(line.startswith(("## Accepted", "# Accepted", "### Accepted")) for line in markdown.splitlines())
    assert "<script" not in markdown.lower()


def test_html_and_links_in_text_are_shown_as_words(world) -> None:
    api, _store, tmp_path = world
    note = '<img src=x onerror=alert(1)> [click](https://evil.example) **bold** `code` | pipe'
    created = api.post(
        "/v1/projects/robot/candidates",
        json={"base_revision": 1, "kind": "schematic", "ops": [{"op": "rotate", "ref": "U1", "degrees": 90}], "author": "Bob", "note": note},
    )
    assert created.status_code == 201, created.text
    text = api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).text
    assert "<img" not in text
    assert "[click](https://evil.example)" not in text
    assert "&lt;img" in text and "\\[click\\]\\(https://evil.example\\)" in text


def test_the_integrity_block_cannot_be_altered_without_failing_verification(world) -> None:
    api, _store, _root = world
    packet = _packet(api)
    assert verify_review_packet(packet)

    forged_algorithm = json.loads(json.dumps(packet))
    forged_algorithm["integrity"]["algorithm"] = "\n\n## Accepted\nApproved for fabrication"
    assert not verify_review_packet(forged_algorithm)

    extra = json.loads(json.dumps(packet))
    extra["integrity"]["note"] = "also trust me"
    assert not verify_review_packet(extra)

    wrong_hash = json.loads(json.dumps(packet))
    wrong_hash["integrity"]["packet_sha256"] = "sha256:" + "0" * 64
    assert not verify_review_packet(wrong_hash)

    missing = json.loads(json.dumps(packet))
    del missing["integrity"]
    assert not verify_review_packet(missing)

    # The rendered document prints the packet's own statement, not whatever a tampered copy carries.
    from hardware_splicer.review_packet import render_review_packet_markdown

    assert "Approved for fabrication" not in render_review_packet_markdown(forged_algorithm)


def test_credentials_and_private_paths_are_removed_and_the_packet_says_how_many(world) -> None:
    api, _store, _root = world
    body = "Authorization: Bearer sk-live-secret-1234567890; key=/home/operator/private.key and api_key=hunter2hunter2 at C:\\Users\\me\\x.txt"
    opened = api.post("/v1/projects/robot/threads", json={"anchor": {"revision": 1, "object_id": "mcu"}, "author": {"kind": "human", "id": "Bob"}, "body": body})
    assert opened.status_code == 201, opened.text
    note = "token=abcdef1234567890 see /var/lib/secret/db"
    created = api.post(
        "/v1/projects/robot/candidates",
        json={"base_revision": 1, "kind": "schematic", "ops": [{"op": "rotate", "ref": "U1", "degrees": 90}], "author": "Bob", "note": note},
    )
    assert created.status_code == 201, created.text

    both = api.get("/v1/projects/robot/review-packet").text + api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).text
    for leaked in ("sk-live-secret", "/home/operator", "private.key", "hunter2hunter2", "C:\\\\Users", "abcdef1234567890", "/var/lib/secret"):
        assert leaked not in both, leaked
    packet = _packet(api)
    assert packet["redactions"]["count"] >= 5
    assert set(packet["redactions"]["by_kind"]) >= {"credential", "path"}
    assert "[redacted credential]" in both and "[redacted path]" in both
    assert "best-effort" in both or "best effort" in both
    # What was removed is part of what the hash covers.
    assert verify_review_packet(packet)


def test_nothing_is_cut_short_without_saying_so(world, monkeypatch: pytest.MonkeyPatch) -> None:
    api, _store, _root = world
    import hardware_splicer.review_packet as rp

    monkeypatch.setattr(rp, "MAX_EVENTS_PER_THREAD", 3)
    monkeypatch.setattr(rp, "MAX_THREADS", 2)
    monkeypatch.setattr(rp, "MAX_OPERATIONS", 2)
    monkeypatch.setattr(rp, "MAX_PROPOSALS", 1)

    for name in ("b", "c"):
        assert api.post("/v1/projects/robot/threads", json={"anchor": {"revision": 1, "object_id": name}, "author": {"kind": "human", "id": "Bob"}, "body": name}).status_code == 201
    # The newest thread is listed first, so the long one is made last.
    first = api.post("/v1/projects/robot/threads", json={"anchor": {"revision": 1, "object_id": "a"}, "author": {"kind": "human", "id": "Bob"}, "body": "one"}).json()["thread"]["thread_id"]
    for index in range(4):
        assert api.post(f"/v1/projects/robot/threads/{first}/events", json={"type": "comment", "body": f"later {index}", "author": {"kind": "human", "id": "Bob"}}).status_code in (200, 201)
    for _ in range(2):
        assert api.post(
            "/v1/projects/robot/candidates",
            json={"base_revision": 1, "kind": "schematic", "ops": [{"op": "rotate", "ref": "U1", "degrees": 90}] * 3, "author": "Bob"},
        ).status_code == 201

    packet = api.get("/v1/projects/robot/review-packet").json()["packet"]
    assert packet["discussion"]["truncated"] and packet["discussion"]["listed"] == 2 and packet["discussion"]["total"] == 3
    long_thread = next(t for t in packet["discussion"]["threads"] if t["events_total"] > 3)
    assert long_thread["events_truncated"] and long_thread["events_listed"] == 3 and long_thread["events_total"] == 5
    assert packet["proposals"]["truncated"] and packet["proposals"]["listed"] == 1 and packet["proposals"]["total"] == 2
    item = packet["proposals"]["items"][0]
    assert item["operations_truncated"] and item["operations_total"] == 3 and len(item["operations"]) == 2

    text = api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).text
    assert "Showing 3 of 5 entries" in text
    assert "Showing 2 of 3 threads" in text
    assert "Showing 1 of 2 proposals" in text
    assert "Showing 2 of 3 operations" in text


def test_a_discussion_too_large_to_read_is_counted_by_name_and_left_out_unread(world, monkeypatch: pytest.MonkeyPatch) -> None:
    api, _store, _root = world
    import hardware_splicer.review_packet as rp
    from hardware_splicer.project_thread_store import ProjectThreadStore

    thread = api.post("/v1/projects/robot/threads", json={"anchor": {"revision": 1, "object_id": "a"}, "author": {"kind": "human", "id": "Bob"}, "body": "one"}).json()["thread"]["thread_id"]
    for index in range(6):
        assert api.post(f"/v1/projects/robot/threads/{thread}/events", json={"type": "comment", "body": f"c{index}", "author": {"kind": "human", "id": "Bob"}}).status_code in (200, 201)

    monkeypatch.setattr(rp, "READ_BUDGET_EVENTS", 5)

    def refuse(*args, **kwargs):
        raise AssertionError("an oversized discussion must not be read")

    monkeypatch.setattr(ProjectThreadStore, "list_threads", refuse)
    monkeypatch.setattr(ProjectThreadStore, "get_thread", refuse)

    packet = api.get("/v1/projects/robot/review-packet").json()["packet"]
    discussion = packet["discussion"]
    assert discussion["status"] == "not_read" and discussion["reason"] == "too large to include"
    assert discussion["total"] == 1 and discussion["total_events"] == 7
    assert discussion["threads"] == []
    text = api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).text
    assert "Not included: the discussion is too large to include (1 thread, 7 events;" in text
    assert verify_review_packet(packet)


@pytest.mark.parametrize(
    ("written", "gone"),
    [
        ('{"password": "hunter2", "api_key": "abcdefgh12345678"}', ["hunter2", "abcdefgh12345678"]),
        ('password="correct horse battery staple"', ["correct horse", "battery staple"]),
        ("passphrase: 'two words here'", ["two words here"]),
        ('{"client_secret":"s3cr3t-value-123","access_token":"tok-abcdef0123456789"}', ["s3cr3t-value-123", "tok-abcdef0123456789"]),
        ('db_password = "has \\"escaped\\" quotes and spaces"', ["escaped\\", "quotes and spaces"]),
        ("PRIVATE_KEY=MIIEvgIBADANBgkq", ["MIIEvgIBADANBgkq"]),
        ("Authorization: Bearer abcdefghijklmnop", ["abcdefghijklmnop"]),
    ],
)
def test_common_ways_of_pasting_a_secret_are_all_removed(world, written, gone) -> None:
    api, _store, _root = world
    assert api.post("/v1/projects/robot/threads", json={"anchor": {"revision": 1, "object_id": "a"}, "author": {"kind": "human", "id": "Bob"}, "body": written}).status_code == 201
    both = api.get("/v1/projects/robot/review-packet").text + api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).text
    for word in gone:
        assert word not in both, word
    assert api.get("/v1/projects/robot/review-packet").json()["packet"]["redactions"]["count"] >= 1


def test_ordinary_words_that_merely_mention_secrets_are_left_alone(world) -> None:
    api, _store, _root = world
    sentence = "The token ring network and the password policy are described in section 4; the secret sauce is the key idea."
    assert api.post("/v1/projects/robot/threads", json={"anchor": {"revision": 1, "object_id": "a"}, "author": {"kind": "human", "id": "Bob"}, "body": sentence}).status_code == 201
    packet = api.get("/v1/projects/robot/review-packet").json()["packet"]
    assert packet["discussion"]["threads"][0]["events"][0]["body"] == sentence
    assert packet["redactions"]["count"] == 0


def test_the_size_of_a_left_out_discussion_does_not_depend_on_the_order_the_filesystem_lists_it(world, monkeypatch: pytest.MonkeyPatch) -> None:
    import contextlib
    import os as real_os

    import hardware_splicer.review_packet as rp

    api, _store, _root = world
    # One big thread listed first or last, and a small one: the answer must be the same either way.
    big = api.post("/v1/projects/robot/threads", json={"anchor": {"revision": 1, "object_id": "big"}, "author": {"kind": "human", "id": "Bob"}, "body": "x"}).json()["thread"]["thread_id"]
    for index in range(5):
        api.post(f"/v1/projects/robot/threads/{big}/events", json={"type": "comment", "body": f"c{index}", "author": {"kind": "human", "id": "Bob"}})
    assert api.post("/v1/projects/robot/threads", json={"anchor": {"revision": 1, "object_id": "small"}, "author": {"kind": "human", "id": "Bob"}, "body": "y"}).status_code == 201
    monkeypatch.setattr(rp, "READ_BUDGET_EVENTS", 3)
    monkeypatch.setattr(rp, "EVENT_COUNT_CEILING", 4)

    forward = api.get("/v1/projects/robot/review-packet").json()["packet"]

    real = real_os.scandir

    @contextlib.contextmanager
    def reversed_scandir(path):
        with real(path) as entries:
            listed = list(entries)
        yield iter(reversed(listed))

    monkeypatch.setattr(rp.os, "scandir", reversed_scandir)
    backward = api.get("/v1/projects/robot/review-packet").json()["packet"]

    assert forward["discussion"] == backward["discussion"]
    assert forward["integrity"]["packet_sha256"] == backward["integrity"]["packet_sha256"]
    # Past the ceiling the packet says "more than", not a number that happened to be reached.
    assert forward["discussion"]["total_events"] is None and forward["discussion"]["total_events_over"] == 4
    assert forward["discussion"]["total"] == 2
    text = api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).text
    assert "more than 4 events" in text and "2 threads" in text


def test_redaction_cost_does_not_grow_with_the_size_of_hostile_input() -> None:
    import time

    from hardware_splicer.review_packet import _Scrub

    scrub = _Scrub()
    started = time.perf_counter()
    for hostile in (
        'password="' * 200_000,
        "token=" * 400_000,
        "Bearer " + "A" * 2_000_000,
        "\\" * 2_000_000,
        "/home/" + "a/" * 1_000_000,
        'secret: "' + 'x\\"' * 500_000,
    ):
        out = scrub.text(hostile)
        assert len(out) <= 500
    assert time.perf_counter() - started < 2.0


def test_a_secret_cut_off_by_the_scan_window_is_removed_not_half_shown() -> None:
    from hardware_splicer.review_packet import _Scrub

    scrub = _Scrub()
    # The closing quote lies beyond the window the scrubber reads. An unclosed quote means the rest is still the secret.
    out = scrub.text('password="' + "A" * 1800 + " LEAKME" + "B" * 300 + '"')
    assert "LEAKME" not in out and "AAAA" not in out
    assert out.startswith("password=[redacted credential]")
    assert scrub.text("api_key='never closed and then LEAKTOO") == "api_key=[redacted credential]"


@pytest.mark.parametrize(
    "legitimate",
    [
        "token_count=128; impedance=50ohm",
        'tokenizer="use BPE for log parsing"',
        "password_policy=strict and token_limit=50",
        "authorization_header=present; secret_count=3",
        "The token ring network and the password policy are in section 4.",
        "keyboard=us; keyboard_layout=dvorak",
        "authorized=true",
    ],
)
def test_engineering_text_that_only_resembles_a_credential_is_left_alone(legitimate) -> None:
    from hardware_splicer.review_packet import _Scrub

    scrub = _Scrub()
    assert scrub.text(legitimate) == legitimate
    assert scrub.summary()["count"] == 0


@pytest.mark.parametrize(
    "secret",
    [
        "access_token: abcd1234efgh",
        "db-password = hunter2",
        'clientSecret="two words"',
        "x_api_key=AKIA0000000000000",
        "secret_key: 'a b c'",
        "PRIVATE-KEY=abc123",
        "API_TOKEN_V2=abc123SECRET",
        "clientAPIKey=abc123SECRET",
        "X-Api-Key: abc123SECRET",
        "AWS_SECRET_ACCESS_KEY=abc123SECRET",
        "refreshToken=abc123SECRET",
    ],
)
def test_names_that_really_are_credentials_still_lose_their_values(secret) -> None:
    from hardware_splicer.review_packet import _Scrub

    scrub = _Scrub()
    out = scrub.text(secret)
    assert "[redacted credential]" in out
    assert "hunter2" not in out and "abcd1234efgh" not in out and "two words" not in out and "a b c" not in out and "abc123SECRET" not in out


def test_an_unsafe_entry_never_changes_what_the_packet_says_about_size_whatever_the_listing_order(world, monkeypatch: pytest.MonkeyPatch) -> None:
    import contextlib
    import os as real_os

    import hardware_splicer.review_packet as rp

    api, store, _root = world
    for name in ("a", "b", "c"):
        assert api.post("/v1/projects/robot/threads", json={"anchor": {"revision": 1, "object_id": name}, "author": {"kind": "human", "id": "Bob"}, "body": name}).status_code == 201
    threads_dir = store.root / "robot" / "threads"
    real_os.symlink(str(threads_dir / "a"), str(threads_dir / "zz-link"))
    monkeypatch.setattr(rp, "THREAD_COUNT_CEILING", 2)   # 3 real directories and 1 symbolic link: over the ceiling

    real = real_os.scandir

    def packet_with(order):
        @contextlib.contextmanager
        def scandir(path):
            with real(path) as entries:
                listed = sorted(entries, key=lambda e: e.name)
            yield iter(listed if order == "forward" else list(reversed(listed)))

        monkeypatch.setattr(rp.os, "scandir", scandir)
        return api.get("/v1/projects/robot/review-packet").json()["packet"]

    forward, backward = packet_with("forward"), packet_with("backward")
    assert forward["discussion"] == backward["discussion"]
    assert forward["integrity"]["packet_sha256"] == backward["integrity"]["packet_sha256"]
    # Over the ceiling is "too large", whatever else was in the listing.
    assert forward["discussion"]["reason"] == "too large to include"

    # Within the ceiling, a symbolic link is what it is: the discussion is not read, in either order.
    monkeypatch.setattr(rp, "THREAD_COUNT_CEILING", 1000)
    forward, backward = packet_with("forward"), packet_with("backward")
    assert forward["discussion"] == backward["discussion"]
    assert forward["discussion"]["reason"] == "unreadable"


def test_an_over_large_events_directory_is_too_large_even_if_it_also_holds_a_symlink(world, monkeypatch: pytest.MonkeyPatch) -> None:
    import contextlib
    import os as real_os

    import hardware_splicer.review_packet as rp

    api, store, _root = world
    thread = api.post("/v1/projects/robot/threads", json={"anchor": {"revision": 1, "object_id": "a"}, "author": {"kind": "human", "id": "Bob"}, "body": "x"}).json()["thread"]["thread_id"]
    for index in range(4):
        api.post(f"/v1/projects/robot/threads/{thread}/events", json={"type": "comment", "body": f"c{index}", "author": {"kind": "human", "id": "Bob"}})
    events_dir = store.root / "robot" / "threads" / thread / "events"
    real_os.symlink(str(events_dir / "00000001.json"), str(events_dir / "zz-link.json"))
    monkeypatch.setattr(rp, "EVENT_COUNT_CEILING", 3)
    real = real_os.scandir

    def packet_with(order):
        @contextlib.contextmanager
        def scandir(path):
            with real(path) as entries:
                listed = sorted(entries, key=lambda e: e.name)
            yield iter(listed if order == "forward" else list(reversed(listed)))

        monkeypatch.setattr(rp.os, "scandir", scandir)
        return api.get("/v1/projects/robot/review-packet").json()["packet"]

    forward, backward = packet_with("forward"), packet_with("backward")
    assert forward["discussion"] == backward["discussion"]
    assert forward["discussion"]["reason"] == "too large to include"
    assert forward["discussion"]["total_events_over"] == 3


def test_a_long_delimited_chain_in_hostile_text_costs_next_to_nothing() -> None:
    """The optional prefix group once made this quadratic: a thousand such fields took about a minute."""

    import time

    from hardware_splicer.review_packet import _Scrub

    scrub = _Scrub()
    started = time.perf_counter()
    for _ in range(1000):
        scrub.text("a-" * 1000)
        scrub.text("ab_" * 650 + "token")
    assert time.perf_counter() - started < 5.0


def test_ordinary_files_in_the_threads_folder_are_not_counted_as_threads(world, monkeypatch: pytest.MonkeyPatch) -> None:
    import hardware_splicer.review_packet as rp

    api, store, _root = world
    folder = store.root / "robot" / "threads"
    folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(rp, "THREAD_COUNT_CEILING", 5)
    for index in range(12):
        (folder / f"notes-{index}.txt").write_text("not a thread", encoding="utf-8")

    discussion = api.get("/v1/projects/robot/review-packet").json()["packet"]["discussion"]
    # Twelve files and no thread: there is nothing to claim "more than five threads" about.
    assert discussion.get("total_over") is None
    assert discussion["status"] in {"listed", "not_read"}
    if discussion["status"] == "not_read":
        assert discussion["total"] == 0 or discussion["total"] is None

    # Only when there really are more directories than the ceiling is it "too large", and it says "more than".
    for index in range(7):
        (folder / f"thread-dir-{index}").mkdir()
    over = api.get("/v1/projects/robot/review-packet").json()["packet"]["discussion"]
    assert over["status"] == "not_read" and over["total"] is None and over["total_over"] == 5


def test_a_folder_with_far_too_many_entries_of_any_kind_is_left_out_without_claiming_a_thread_count(world, monkeypatch: pytest.MonkeyPatch) -> None:
    import hardware_splicer.review_packet as rp

    api, store, _root = world
    folder = store.root / "robot" / "threads"
    folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(rp, "ENTRY_SCAN_CEILING", 10)
    for index in range(15):
        (folder / f"junk-{index}.txt").write_text("x", encoding="utf-8")
    discussion = api.get("/v1/projects/robot/review-packet").json()["packet"]["discussion"]
    assert discussion["status"] == "not_read"
    assert discussion["total"] is None and discussion["total_over"] is None
    text = api.get("/v1/projects/robot/review-packet", params={"format": "markdown"}).text
    assert "Not included: the discussion is too large to include" in text
    assert "more than" not in text.split("## Discussion")[1].split("## Removed")[0]
