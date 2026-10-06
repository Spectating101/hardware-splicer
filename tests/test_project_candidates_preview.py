"""Previewing a draft: the result of the edits without keeping anything."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

REF = Path(__file__).resolve().parents[1] / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
ROTATE = [{"op": "rotate", "ref": "U1", "degrees": 90}]


def _snapshot(build: Path) -> dict:
    return {
        "projectId": "robot",
        "projectName": "Robot",
        "currentStage": "design",
        "buildDir": str(build),
        "machineProject": {"project_id": "robot", "name": "Robot", "purpose": "Preview drafts"},
    }


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_BUILD_FILE_ROOTS", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_KICAD_CLI", raising=False)
    monkeypatch.setenv("PATH", "/var/empty-hs-preview-path")
    build = tmp_path / "build1"
    (build / "build_compilation").mkdir(parents=True)
    for source in REF.glob("spi_flash_adapter_v1.kicad_*"):
        shutil.copy(source, build / "build_compilation" / source.name)
    store = ProjectStore(tmp_path / "store")
    api = TestClient(create_product_app(store))
    assert api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(build), "expected_revision": 0}).status_code == 200
    return api, store, tmp_path


def _tree(root: Path) -> dict[str, str]:
    """Every file under ``root`` with its content hash, so 'nothing was written' can be asserted exactly."""

    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _preview(api: TestClient, **overrides):
    body = {"base_revision": 1, "kind": "schematic", "ops": ROTATE}
    body.update(overrides)
    return api.post("/v1/projects/robot/candidates/preview", json=body)


def test_a_preview_equals_what_a_proposal_of_the_same_edits_would_hold(world) -> None:
    api, _store, _root = world
    previewed = _preview(api)
    assert previewed.status_code == 200, previewed.text
    preview = previewed.json()["preview"]

    proposed = api.post(
        "/v1/projects/robot/candidates",
        json={"base_revision": 1, "kind": "schematic", "ops": ROTATE, "author": "Bob"},
    ).json()["candidate"]
    stored = api.get(f"/v1/projects/robot/candidates/{proposed['candidate_id']}/files/schematic").content.decode("utf-8")

    assert preview["text"] == stored
    assert preview["diff"]["summary"] == proposed["diff"]["summary"]
    assert preview["applied"] == proposed["applied"]
    assert preview["base_revision"] == 1 and preview["kind"] == "schematic"


def test_a_preview_writes_nothing_at_all(world) -> None:
    api, store, tmp_path = world
    before_store, before_output = _tree(store.root), _tree(tmp_path)

    for _ in range(3):
        assert _preview(api).status_code == 200
    assert _preview(api, kind="pcb", ops=[{"op": "rotate", "ref": "R3", "degrees": 90}]).status_code == 200

    assert _tree(store.root) == before_store
    assert _tree(tmp_path) == before_output
    assert api.get("/v1/projects/robot/candidates").json()["candidates"] == []
    assert api.get("/v1/projects/robot/reviews").json()["reviews"] == []
    assert int(store.load("robot")["revision"]) == 1


def test_previews_never_count_toward_the_proposal_cap(world) -> None:
    api, _store, _root = world
    for _ in range(60):
        assert _preview(api).status_code == 200
    created = api.post("/v1/projects/robot/candidates", json={"base_revision": 1, "kind": "schematic", "ops": ROTATE, "author": "Bob"})
    assert created.status_code == 201


@pytest.mark.parametrize(
    ("overrides", "status", "kind"),
    [
        ({"ops": [{"op": "rotate", "ref": "NOPE", "degrees": 90}]}, 422, "invalid_edit"),
        ({"ops": [{"op": "rotate", "ref": "U1", "degrees": 0}]}, 422, "no_effective_change"),
        ({"ops": []}, 422, "invalid_request"),
        ({"kind": "plan"}, 422, "invalid_request"),
        ({"base_revision": 99}, 404, None),
    ],
)
def test_a_preview_refuses_what_a_proposal_would_refuse(world, overrides, status, kind) -> None:
    api, store, tmp_path = world
    before = _tree(store.root), _tree(tmp_path)
    response = _preview(api, **overrides)
    assert response.status_code == status, response.text
    if kind:
        assert response.json()["detail"]["type"] == kind
    assert (_tree(store.root), _tree(tmp_path)) == before


def test_a_preview_needs_a_retained_file_like_a_proposal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    store = ProjectStore(tmp_path / "store")
    api = TestClient(create_product_app(store))
    snapshot = {**_snapshot(tmp_path / "missing-build")}
    assert api.put("/v1/projects/robot/snapshot", json={"snapshot": snapshot, "expected_revision": 0}).status_code == 200
    response = _preview(api)
    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "artifact_not_retained"


def test_a_preview_or_a_list_never_repairs_a_damaged_store(world) -> None:
    """Recovery renames damaged revisions and rewrites the manifest. A read route must not do that for anyone."""

    api, store, tmp_path = world
    second = tmp_path / "build2"
    (second / "build_compilation").mkdir(parents=True)
    for source in REF.glob("spi_flash_adapter_v1.kicad_*"):
        shutil.copy(source, second / "build_compilation" / source.name)
    saved = api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(second), "expected_revision": 1})
    assert saved.status_code == 200, saved.text
    store._revision_path("robot", 2).write_text("{ this revision is damaged", encoding="utf-8")
    before = _tree(store.root), _tree(tmp_path)

    # No base revision given: the latest one is damaged, so the newest valid one is used, and nothing is repaired.
    previewed = _preview(api, base_revision=None)
    assert previewed.status_code == 200, previewed.text
    assert previewed.json()["preview"]["base_revision"] == 1
    assert api.get("/v1/projects/robot/candidates").status_code == 200
    assert api.get("/v1/projects/robot/candidates/cand-0123456789ab").status_code == 404

    assert (_tree(store.root), _tree(tmp_path)) == before
    assert not list(store.root.rglob("*.corrupt"))
