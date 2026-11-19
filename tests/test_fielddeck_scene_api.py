import json
import struct

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer import fielddeck_scene_api, project_scene_api


@pytest.fixture
def client(tmp_path, monkeypatch):
    project = "projects/cyberdeck-real-trial-20261020"
    root = tmp_path / project
    root.mkdir(parents=True)
    (root / "scene.json").write_text(json.dumps({
        "schema": "hardware_splicer.scene_manifest.v1",
        "project_id": root.name,
        "revisions": [
            {"id": "7", "parts": f"{project}/digital_v1/cad/parts.json",
             "glb": f"{project}/digital_v1/cad/FIELDDECK_7.glb"},
            {"id": "5", "parts": f"{project}/display_swap/parts.json",
             "glb": f"{project}/display_swap/cad/FIELDDECK_5.glb"},
        ],
    }))
    monkeypatch.setattr(project_scene_api, "_REPO_ROOT", tmp_path)
    app = FastAPI()
    app.include_router(fielddeck_scene_api.fielddeck_router)
    with TestClient(app) as client:
        yield client, root


@pytest.mark.parametrize(("revision", "sidecar_path", "model_path"), [
    ("7", "digital_v1/cad/parts.json", "digital_v1/cad/FIELDDECK_7.glb"),
    ("5", "display_swap/parts.json", "display_swap/cad/FIELDDECK_5.glb"),
])
def test_fielddeck_serves_fixed_assets(client, revision, sidecar_path, model_path):
    api, root = client
    sidecar = {"revision": revision, "units": "mm"}
    sidecar_file = root / sidecar_path
    sidecar_file.parent.mkdir(parents=True)
    sidecar_file.write_text(json.dumps(sidecar))
    chunk = json.dumps({"asset": {"version": "2.0"}, "extras": {"revision": revision}}).encode()
    chunk += b" " * (-len(chunk) % 4)
    glb = struct.pack("<4sIII4s", b"glTF", 2, 20 + len(chunk), len(chunk), b"JSON") + chunk
    model_file = root / model_path
    model_file.parent.mkdir(parents=True, exist_ok=True)
    model_file.write_bytes(glb)

    scene_url = f"/v1/scenes/fielddeck/{revision}"
    response = api.get(scene_url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == sidecar
    response = api.get(f"{scene_url}/model")
    assert response.status_code == 200
    assert response.headers["content-type"] == "model/gltf-binary"
    assert response.content == glb


@pytest.mark.parametrize("revision", ["6", "05", "FIELDDECK_7.glb"])
def test_fielddeck_rejects_other_revisions(client, revision):
    api, _ = client
    for suffix in ("", "/model"):
        response = api.get(f"/v1/scenes/fielddeck/{revision}{suffix}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Fielddeck revision not found"


def test_fielddeck_missing_model_returns_404(client):
    api, _ = client
    response = api.get("/v1/scenes/fielddeck/5/model")
    assert response.status_code == 404
    assert response.json()["detail"] == "Fielddeck scene asset not found"
