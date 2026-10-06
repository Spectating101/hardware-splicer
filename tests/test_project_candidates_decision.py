"""Deciding a proposal: a verified operator accepts or rejects it, through the existing review store.

Runs against the real product app so that accepting pins the proposed bytes the way production does.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.artifact_retention import read_pinned_artifact
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

REF = Path(__file__).resolve().parents[1] / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
TOKEN = "operator-secret"
ROTATE = [{"op": "rotate", "ref": "U1", "degrees": 90}]


def _snapshot(build: Path) -> dict:
    return {
        "projectId": "robot",
        "projectName": "Robot",
        "currentStage": "design",
        "buildDir": str(build),
        "machineProject": {"project_id": "robot", "name": "Robot", "purpose": "Decide proposals"},
    }


def _build(tmp_path: Path, name: str) -> Path:
    build = tmp_path / name
    (build / "build_compilation").mkdir(parents=True)
    for source in REF.glob("spi_flash_adapter_v1.kicad_*"):
        shutil.copy(source, build / "build_compilation" / source.name)
    return build


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_BUILD_FILE_ROOTS", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_KICAD_CLI", raising=False)
    monkeypatch.setenv("PATH", "/var/empty-hs-decision-path")
    monkeypatch.setenv(
        "HARDWARE_SPLICER_OPERATOR_TOKENS",
        json.dumps({hash_operator_token(TOKEN): {"id": "alice", "kind": "human"}}),
    )
    store = ProjectStore(tmp_path / "store")
    api = TestClient(create_product_app(store))
    saved = api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(_build(tmp_path, "build1")), "expected_revision": 0})
    assert saved.status_code == 200, saved.text
    return api, store, tmp_path


def _propose(api: TestClient, **overrides) -> dict:
    body = {"base_revision": 1, "kind": "schematic", "ops": ROTATE, "author": "Bob", "note": "turn it"}
    body.update(overrides)
    response = api.post("/v1/projects/robot/candidates", json=body)
    assert response.status_code == 201, response.text
    return response.json()["candidate"]


def _decide(api: TestClient, candidate_id: str, decision: str, *, token: str | None = TOKEN, **extra):
    headers = {"X-HS-Operator-Token": token} if token else {}
    return api.post(f"/v1/projects/robot/candidates/{candidate_id}/decision", json={"decision": decision, **extra}, headers=headers)


def _revision_count(store: ProjectStore) -> int:
    return int(store.load("robot")["revision"])


def test_a_proposal_keeps_the_reason_its_author_gave(world) -> None:
    api, _store, _root = world
    candidate = _propose(api, note="Pin 3 is wired to the wrong rail")
    assert candidate["note"] == "Pin 3 is wired to the wrong rail"
    listed = api.get("/v1/projects/robot/candidates").json()["candidates"]
    assert listed[0]["note"] == "Pin 3 is wired to the wrong rail"
    assert _propose(api, note="")["note"] == ""


def test_a_new_proposal_reports_a_pending_review_that_is_not_stale(world) -> None:
    api, _store, _root = world
    candidate = _propose(api)

    one = api.get(f"/v1/projects/robot/candidates/{candidate['candidate_id']}").json()
    assert one["review_state"] == {"status": "pending", "decided_by": None, "decided_at": None, "note": None, "accepted_revision": None, "stale": False}
    listed = api.get("/v1/projects/robot/candidates").json()["candidates"]
    assert listed[0]["review_state"]["status"] == "pending"


@pytest.mark.parametrize("token", [None, "", "not-a-token"])
def test_deciding_needs_a_server_verified_identity(world, token) -> None:
    api, store, _root = world
    candidate = _propose(api)

    response = _decide(api, candidate["candidate_id"], "accepted", token=token, actor="mallory")

    assert response.status_code == 401
    expected = "operator_token_invalid" if token == "not-a-token" else "operator_token_required"
    assert response.json()["detail"]["type"] == expected
    assert _revision_count(store) == 1
    assert api.get(f"/v1/projects/robot/candidates/{candidate['candidate_id']}").json()["review_state"]["status"] == "pending"


def test_rejecting_records_the_verified_operator_and_changes_nothing_else(world) -> None:
    api, store, tmp_path = world
    candidate = _propose(api)
    record_path = store.root / "robot" / "candidates" / f"{candidate['candidate_id']}.json"
    record_before = record_path.read_bytes()

    # A typed actor in the body never names who decided; the token does.
    response = _decide(api, candidate["candidate_id"], "rejected", note="not now", actor="mallory")

    assert response.status_code == 200, response.text
    state = response.json()["review_state"]
    assert state["status"] == "rejected"
    assert state["decided_by"] == "alice"
    assert state["note"] == "not now"
    assert state["accepted_revision"] is None
    assert _revision_count(store) == 1
    assert record_path.read_bytes() == record_before
    assert (tmp_path / "candidates" / "robot" / candidate["candidate_id"]).is_dir()


def test_accepting_makes_the_next_revision_with_the_proposed_bytes_and_no_extra_authority(world) -> None:
    api, store, _root = world
    candidate = _propose(api)
    proposed = api.get(f"/v1/projects/robot/candidates/{candidate['candidate_id']}/files/schematic").content.decode("utf-8")
    before = store.load("robot", revision=1)

    response = _decide(api, candidate["candidate_id"], "accepted", note="looks right")

    assert response.status_code == 200, response.text
    state = response.json()["review_state"]
    assert state["status"] == "accepted"
    assert state["decided_by"] == "alice"
    assert state["accepted_revision"] == 2
    assert _revision_count(store) == 2
    assert store.load("robot", revision=1) == before
    pinned = read_pinned_artifact(store, "robot", 2, "schematic")
    assert pinned is not None and pinned[0] == proposed
    # The proposal stays a proposal; accepting it grants nothing beyond being the next revision.
    assert response.json()["candidate"]["authority"]["state"] == "proposal"
    text = json.dumps(response.json()).lower()
    for claim in ("fabrication-ready", "release-ready", "passed", "approved"):
        assert claim not in text.replace("does not mark anything verified, fabrication-ready or release-ready", "")


def test_a_proposal_goes_stale_when_a_newer_revision_lands_and_cannot_be_accepted(world) -> None:
    api, store, tmp_path = world
    candidate = _propose(api)
    newer = api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(_build(tmp_path, "build2")), "expected_revision": 1})
    assert newer.status_code == 200, newer.text

    state = api.get(f"/v1/projects/robot/candidates/{candidate['candidate_id']}").json()["review_state"]
    assert state["status"] == "pending" and state["stale"] is True

    refused = _decide(api, candidate["candidate_id"], "accepted")
    assert refused.status_code == 409
    assert _revision_count(store) == 2


def test_a_decision_can_only_be_made_once_and_must_be_a_valid_word(world) -> None:
    api, _store, _root = world
    candidate = _propose(api)

    assert _decide(api, candidate["candidate_id"], "maybe").status_code == 422
    assert _decide(api, candidate["candidate_id"], "rejected").status_code == 200
    again = _decide(api, candidate["candidate_id"], "accepted")
    assert again.status_code == 409
    assert again.json()["detail"]["type"] == "review_conflict"


def test_deciding_an_unknown_proposal_is_not_found(world) -> None:
    api, _store, _root = world
    response = _decide(api, "cand-0123456789ab", "rejected")
    assert response.status_code == 404
