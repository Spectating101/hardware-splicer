import json
import struct
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer import project_scene_api


ROOT = Path(__file__).resolve().parents[1]
FIELDDECK = "cyberdeck-real-trial-20261020"
PLOTTER = "ender3-penplotter-digital"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(project_scene_api.project_scene_router)
    return TestClient(app)


def test_list_and_read_scene_manifests(client):
    expected = {
        FIELDDECK: ("available", ["7", "5"]),
        PLOTTER: ("available", ["v1"]),
        "drone-build": ("unavailable", ["v1"]),
    }
    response = client.get("/v1/scenes")
    assert response.status_code == 200
    rows = {row["project_id"]: row for row in response.json()}
    for project_id, (status, revisions) in expected.items():
        manifest = json.loads((ROOT / "projects" / project_id / "scene.json").read_text())
        response = client.get(f"/v1/scenes/{project_id}")
        assert response.status_code == 200
        assert response.json() == manifest
        assert rows[project_id] == {
            "project_id": project_id, "title": manifest["title"],
            "geometry_status": status, "revisions": revisions,
        }
    assert client.get("/v1/scenes/missing").status_code == 404


def test_unavailable_drone_geometry_surfaces_source_verbatim(client):
    source = json.loads((ROOT / "projects/drone-build/geometry-source.json").read_text())
    url = "/v1/scenes/drone-build"
    manifest = client.get(url).json()
    assert manifest["geometry_status"] == "unavailable"
    assert manifest["geometry_note"] == source["source_status"] + "\n" + source["next_required_action"]
    assert any(row.get("sha256") == source["sha256"] for row in manifest["sources"])
    assert manifest["revisions"][0]["parts"] is None
    assert manifest["revisions"][0]["glb"] is None
    revision = manifest["revisions"][0]["id"]
    for asset in ("parts", "model"):
        assert client.get(f"{url}/{revision}/{asset}").status_code == 404


def test_fielddeck_alias_serves_the_same_assets(client, tmp_path, monkeypatch):
    relative = Path("projects") / FIELDDECK
    project = tmp_path / relative
    manifest = json.loads((ROOT / relative / "scene.json").read_text())
    project.mkdir(parents=True)
    (project / "scene.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(project_scene_api, "_REPO_ROOT", tmp_path)

    gltf = b'{"asset":{"version":"2.0"}} '
    model = struct.pack("<4sIII4s", b"glTF", 2, 20 + len(gltf), len(gltf), b"JSON") + gltf
    for row in manifest["revisions"]:
        revision = row["id"]
        parts = Path(row["parts"])
        for asset, content in ((parts, json.dumps({"revision": revision}).encode()), (Path(row["glb"]), model)):
            (tmp_path / asset).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / asset).write_bytes(content)
        base = f"/v1/scenes/{FIELDDECK}/{revision}"
        alias = f"/v1/scenes/fielddeck/{revision}"
        for path, legacy, content_type in (
            (f"{base}/parts", alias, "application/json"),
            (f"{base}/model", f"{alias}/model", "model/gltf-binary"),
        ):
            canonical = client.get(path)
            response = client.get(legacy)
            assert canonical.status_code == response.status_code == 200
            assert canonical.headers["content-type"] == response.headers["content-type"] == content_type
            assert canonical.content == response.content


def test_scene_asset_paths_are_confined_to_the_project(client, tmp_path, monkeypatch):
    project = tmp_path / "projects/test-project"
    project.mkdir(parents=True)
    outside = project.parent / "outside.json"
    outside.write_text("{}")
    (project / "link.json").symlink_to(outside)
    (project / "unlisted.json").write_text("{}")
    revisions = [
        {"id": "parent", "parts": "projects/test-project/../outside.json"},
        {"id": "sibling", "parts": "projects/outside.json"},
        {"id": "absolute", "parts": str(outside)},
        {"id": "symlink", "parts": "projects/test-project/link.json"},
        {"id": "missing", "parts": "projects/test-project/missing.json"},
    ]
    (project / "scene.json").write_text(json.dumps({
        "schema": "hardware_splicer.scene_manifest.v1", "project_id": project.name, "revisions": revisions,
    }))
    monkeypatch.setattr(project_scene_api, "_REPO_ROOT", tmp_path)
    base = "/v1/scenes/test-project"
    for revision in [row["id"] for row in revisions] + ["unlisted.json", "%2e%2e%2foutside.json"]:
        assert client.get(f"{base}/{revision}/parts").status_code == 404
    assert client.get("/v1/scenes/%2e%2e%2ftest-project").status_code == 404
