from __future__ import annotations

import hashlib
import os
import shutil
import struct
import subprocess
import threading
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.artifact_retention import retain_revision_artifacts
from hardware_splicer.model3d import capability_probe, model_cache_paths, options_fingerprint
from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_artifact_api import create_project_artifact_router
from hardware_splicer.project_model3d_api import create_project_model3d_router
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.project_thread_api import create_project_thread_router
from hardware_splicer.project_thread_store import ProjectThreadStore

REPO = Path(__file__).resolve().parents[1]
REF = REPO / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
SCH = REF / "spi_flash_adapter_v1.kicad_sch"
PCB = REF / "spi_flash_adapter_v1.kicad_pcb"


def _require_kicad() -> None:
    probe = capability_probe()
    if not probe["available"]:
        pytest.skip(probe["reason"] or "kicad-cli missing")


def _snapshot(build_dir: Path | None = None) -> dict:
    body = {
        "projectId": "robot",
        "projectName": "Robot",
        "currentStage": "design",
        "machineProject": {
            "project_id": "robot",
            "name": "Robot",
            "purpose": "Build an inspection robot",
        },
    }
    if build_dir is not None:
        body["buildDir"] = str(build_dir)
    return body


def _copy_reference(build: Path) -> Path:
    comp = build / "build_compilation"
    comp.mkdir(parents=True, exist_ok=True)
    shutil.copy(SCH, comp / SCH.name)
    shutil.copy(PCB, comp / PCB.name)
    return comp


def _client(tmp_path: Path) -> tuple[TestClient, ProjectStore]:
    store = ProjectStore(tmp_path)
    app = FastAPI()
    app.include_router(create_project_router(store))
    app.include_router(create_project_artifact_router(store))
    app.include_router(create_project_model3d_router(store))
    app.include_router(create_project_thread_router(ProjectThreadStore(store)))
    return TestClient(app), store


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] == "models":
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _minimal_glb(*, size: int = 16) -> bytes:
    return b"glTF" + struct.pack("<II", 2, size) + (b"\x00" * (size - 12))


def _retain_reference(tmp_path: Path) -> tuple[TestClient, ProjectStore]:
    build = tmp_path / "build"
    _copy_reference(build)
    api, store = _client(tmp_path / "store")
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert saved.status_code == 200
    if saved.json()["artifact_retention"]["status"] != "retained":
        pin = retain_revision_artifacts(store, "robot", 1, basis="at_save")
        assert pin is not None
    return api, store


def test_model3d_from_retained_reference_pcb(tmp_path: Path) -> None:
    _require_kicad()
    api, _store = _retain_reference(tmp_path)
    meta = api.get("/v1/projects/robot/revisions/1/model3d")
    assert meta.status_code == 200
    body = meta.json()
    assert body["ok"] is True
    assert body["available"] is True
    assert body["revision"] == 1
    model = body["model"]
    assert model["format"] == "glb"
    assert model["url"] == "/v1/projects/robot/revisions/1/model3d/glb"
    assert model["generated_with"].startswith("kicad-cli ")
    assert model["sha256"].startswith("sha256:")
    assert model["pcb_sha256"].startswith("sha256:")
    assert model["size_bytes"] > 12

    binary = api.get("/v1/projects/robot/revisions/1/model3d/glb")
    assert binary.status_code == 200
    assert binary.headers["content-type"].startswith("model/gltf-binary")
    assert binary.headers["etag"] == f'"{model["sha256"]}"'
    assert binary.headers["cache-control"] == "private, max-age=3600"
    data = binary.content
    assert data[:4] == b"glTF"
    _version, length = struct.unpack_from("<II", data, 4)
    assert _version == 2
    assert length == len(data)
    assert hashlib.sha256(data).hexdigest() == model["sha256"].split(":", 1)[1]


def test_no_pin_is_available_false(tmp_path: Path) -> None:
    api, _store = _client(tmp_path)
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(), "expected_revision": 0})
    response = api.get("/v1/projects/robot/revisions/1/model3d")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["available"] is False
    assert body["reason"] == "no retained pcb"
    missing = api.get("/v1/projects/robot/revisions/1/model3d/glb")
    assert missing.status_code == 404
    assert missing.json()["detail"]["type"] == "not_found"


def test_missing_kicad_is_available_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    api, _store = _retain_reference(tmp_path)
    monkeypatch.delenv("HARDWARE_SPLICER_KICAD_CLI", raising=False)
    monkeypatch.setenv("PATH", "/var/empty-hs-model3d-path")
    response = api.get("/v1/projects/robot/revisions/1/model3d")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["available"] is False
    assert body["reason"]
    missing = api.get("/v1/projects/robot/revisions/1/model3d/glb")
    assert missing.status_code == 404
    assert missing.json()["detail"]["type"] == "not_found"


def test_if_none_match_is_304(tmp_path: Path) -> None:
    _require_kicad()
    api, _store = _retain_reference(tmp_path)
    first = api.get("/v1/projects/robot/revisions/1/model3d/glb")
    assert first.status_code == 200
    etag = first.headers["etag"]
    cached = api.get(
        "/v1/projects/robot/revisions/1/model3d/glb",
        headers={"If-None-Match": etag},
    )
    assert cached.status_code == 304
    assert cached.headers["etag"] == etag


def test_missing_project_and_revision_are_404(tmp_path: Path) -> None:
    api, _store = _client(tmp_path)
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(), "expected_revision": 0})
    missing_rev = api.get("/v1/projects/robot/revisions/9/model3d")
    assert missing_rev.status_code == 404
    assert missing_rev.json()["detail"]["type"] == "not_found"
    missing_proj = api.get("/v1/projects/ghost/revisions/1/model3d")
    assert missing_proj.status_code == 404
    assert missing_proj.json()["detail"]["type"] == "not_found"


class _FakePopen:
    def __init__(self, cmd, *, handler, **_kwargs) -> None:
        self.args = list(cmd)
        self.pid = 2_000_000_017
        self.returncode: int | None = None
        self._handler = handler
        self._done = False
        self._stdout = b""
        self._stderr = b""

    def communicate(self, timeout=None):
        if self._done:
            return self._stdout, self._stderr
        if "--version" in self.args:
            self._done = True
            self.returncode = 0
            self._stdout, self._stderr = b"9.0.2\n", b""
            return self._stdout, self._stderr
        result = self._handler(self.args, timeout)
        if result is None:
            result = subprocess.CompletedProcess(self.args, 0, b"", b"")
        self._done = True
        self.returncode = result.returncode
        self._stdout = result.stdout or b""
        self._stderr = result.stderr or b""
        return self._stdout, self._stderr


def test_concurrent_requests_spawn_kicad_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    api, _store = _retain_reference(tmp_path)
    capability_probe()
    calls: list[int] = []
    started = threading.Event()
    release = threading.Event()

    def handler(cmd, _timeout):
        if isinstance(cmd, (list, tuple)) and "export" in cmd:
            calls.append(1)
            started.set()
            release.wait(2.0)
            output = Path(cmd[cmd.index("--output") + 1])
            output.write_bytes(_minimal_glb())
        return subprocess.CompletedProcess(list(cmd), 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(
        "hardware_splicer.model3d.subprocess.Popen",
        lambda cmd, *args, **kwargs: _FakePopen(cmd, handler=handler, **kwargs),
    )
    results: list[int] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            response = api.get("/v1/projects/robot/revisions/1/model3d")
            results.append(response.status_code)
        except BaseException as exc:  # noqa: BLE001 — collect for the main thread
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    assert started.wait(2.0)
    release.set()
    for thread in threads:
        thread.join(2.0)
    assert errors == []
    assert results == [200] * 6
    assert calls == [1]


def test_sidecar_install_failure_does_not_break_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api, store = _retain_reference(tmp_path)
    writes = {"n": 0}

    def handler(cmd, _timeout):
        writes["n"] += 1
        output = Path(cmd[cmd.index("--output") + 1])
        output.write_bytes(_minimal_glb(size=20 + writes["n"]))
        return subprocess.CompletedProcess(list(cmd), 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(
        "hardware_splicer.model3d.subprocess.Popen",
        lambda cmd, *args, **kwargs: _FakePopen(cmd, handler=handler, **kwargs),
    )
    first = api.get("/v1/projects/robot/revisions/1/model3d")
    assert first.status_code == 200
    assert first.json()["available"] is True
    pin = api.get("/v1/projects/robot/revisions/1/artifacts").json()["pin"]
    pcb_hex = pin["artifacts"]["pcb"]["sha256"].split(":", 1)[1]
    glb_path, _sidecar = model_cache_paths(store, "robot", pcb_hex)
    glb_path.write_bytes(glb_path.read_bytes() + b"tamper")

    real_replace = os.replace
    calls = {"n": 0}

    def flaky_replace(src, dst, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("sidecar install failed")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr("hardware_splicer.model3d.os.replace", flaky_replace)
    recovered = api.get("/v1/projects/robot/revisions/1/model3d")
    assert recovered.status_code == 200
    assert recovered.json()["available"] is True
    assert "model" in recovered.json()
    monkeypatch.setattr("hardware_splicer.model3d.os.replace", real_replace)
    later = api.get("/v1/projects/robot/revisions/1/model3d")
    assert later.status_code == 200
    assert later.json()["available"] is True
    binary = api.get("/v1/projects/robot/revisions/1/model3d/glb")
    assert binary.status_code == 200
    assert binary.content[:4] == b"glTF"


def test_generation_does_not_change_revision_or_pin_bytes(tmp_path: Path) -> None:
    _require_kicad()
    api, store = _retain_reference(tmp_path)
    created = api.post(
        "/v1/projects/robot/reviews",
        json={
            "base_revision": 1,
            "candidate_snapshot": _snapshot(),
            "created_by": "agent",
        },
    )
    assert created.status_code == 201
    opened = api.post(
        "/v1/projects/robot/threads",
        json={
            "anchor": {"revision": 1, "object_id": "mcu"},
            "author": {"kind": "human", "id": "owner"},
            "body": "3D view is a rendered model only.",
        },
    )
    assert opened.status_code == 201
    project_dir = store.root / "robot"
    before = _hash_tree(project_dir)
    rev_bytes = (project_dir / "revisions" / "00000001.json").read_bytes()
    manifest_bytes = (project_dir / "project.json").read_bytes()
    pin_bytes = (project_dir / "artifact_pins" / "00000001.json").read_bytes()
    response = api.get("/v1/projects/robot/revisions/1/model3d")
    assert response.status_code == 200
    assert response.json()["available"] is True
    assert (project_dir / "revisions" / "00000001.json").read_bytes() == rev_bytes
    assert (project_dir / "project.json").read_bytes() == manifest_bytes
    assert (project_dir / "artifact_pins" / "00000001.json").read_bytes() == pin_bytes
    assert _hash_tree(project_dir) == before
    assert options_fingerprint()
    assert any((project_dir / "models").rglob("*.glb"))
