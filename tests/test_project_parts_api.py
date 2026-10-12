from __future__ import annotations

import hashlib
import shutil
import socket
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_artifact_api import create_project_artifact_router
from hardware_splicer.project_parts_api import create_project_parts_router
from hardware_splicer.project_store import ProjectStore

REPO = Path(__file__).resolve().parents[1]
REF = REPO / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
SCH = REF / "spi_flash_adapter_v1.kicad_sch"
PCB = REF / "spi_flash_adapter_v1.kicad_pcb"


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(self: socket.socket, *args: Any, **kwargs: Any) -> None:
        raise OSError("network disabled in parts intelligence tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)


def _snapshot(build_dir: Path | None = None) -> dict:
    body = {"projectId": "robot", "projectName": "Robot", "currentStage": "design"}
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
    app.include_router(create_project_parts_router(store))
    return TestClient(app), store


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in {"artifacts", "artifact_pins"}:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_available_false_when_no_pin(tmp_path: Path) -> None:
    api, _store = _client(tmp_path)
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(), "expected_revision": 0})
    response = api.get("/v1/projects/robot/revisions/1/parts")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["available"] is False
    assert body["project_id"] == "robot"
    assert body["revision"] == 1
    assert "retained schematic" in body["reason"].lower() or "no retained" in body["reason"].lower()
    assert body["enrichment"]["requested"] is False
    assert body["enrichment"]["performed"] is False


def test_parts_from_retained_reference_schematic(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, store = _client(tmp_path / "store")
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert saved.json()["artifact_retention"]["status"] == "retained"
    project_dir = store.root / "robot"
    before = _hash_tree(project_dir)
    response = api.get("/v1/projects/robot/revisions/1/parts", params={"enrich": False})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["available"] is True
    assert body["summary"]["components"] == 40
    refs = [row["ref"] for row in body["components"]]
    assert "U1" in refs and "R2" in refs and "TP1" in refs
    u1 = next(row for row in body["components"] if row["ref"] == "U1")
    assert u1["value"] == "TXU0304PWR"
    assert u1["footprint"] == "Package_SO:TSSOP-14_4.4x5mm_P0.65mm"
    assert u1["mpn"] == "TXU0304PWR"
    assert body["source"]["relative"].endswith(".kicad_sch")
    assert str(body["source"]["sha256"]).startswith("sha256:")
    assert body["source"]["retention_basis"] == "at_save"
    assert body["enrichment"]["requested"] is False
    assert body["enrichment"]["performed"] is False
    assert _hash_tree(project_dir) == before


def test_enrich_false_never_calls_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, _store = _client(tmp_path / "store")
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(build), "expected_revision": 0})

    class Spy:
        name = "spy"
        calls = 0

        def lookup(self, query: dict[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
            type(self).calls += 1
            raise AssertionError("provider must not be called when enrich=false")

    Spy.calls = 0
    monkeypatch.setattr(
        "hardware_splicer.project_parts_api.parts_providers_from_env",
        lambda: [Spy()],
    )
    response = api.get("/v1/projects/robot/revisions/1/parts", params={"enrich": False})
    assert response.status_code == 200
    assert Spy.calls == 0
    assert response.json()["enrichment"]["performed"] is False


def test_enrich_true_without_providers_does_not_perform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, _store = _client(tmp_path / "store")
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(build), "expected_revision": 0})
    monkeypatch.setattr("hardware_splicer.project_parts_api.parts_providers_from_env", lambda: [])
    response = api.get("/v1/projects/robot/revisions/1/parts", params={"enrich": True})
    assert response.status_code == 200
    body = response.json()
    assert body["enrichment"]["requested"] is True
    assert body["enrichment"]["performed"] is False
    assert body["enrichment"]["providers"] == []
    assert "reason" in body["enrichment"] or "provider" in str(body["enrichment"]).lower()


def test_enrich_true_runs_provider_off_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, _store = _client(tmp_path / "store")
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(build), "expected_revision": 0})

    class Ok:
        name = "ok"

        def lookup(self, query: dict[str, Any], *, timeout_s: float) -> dict[str, Any] | None:
            mpn = query.get("mpn")
            if not mpn:
                return None
            return {
                "source": "ok",
                "as_of": "2026-10-06T00:00:00+00:00",
                "lifecycle": "active",
                "stock": 3,
                "price_breaks": None,
                "datasheet_url": None,
                "alternates": [],
                "package": None,
            }

    monkeypatch.setattr(
        "hardware_splicer.project_parts_api.parts_providers_from_env",
        lambda: [Ok()],
    )
    response = api.get("/v1/projects/robot/revisions/1/parts", params={"enrich": True})
    assert response.status_code == 200
    body = response.json()
    assert body["enrichment"]["requested"] is True
    assert body["enrichment"]["performed"] is True
    assert body["enrichment"]["providers"] == ["ok"]
    u1_group = next(group for group in body["bom_groups"] if group.get("mpn") == "TXU0304PWR")
    assert u1_group["availability"]["status"] == "checked"
    assert u1_group["availability"]["records"][0]["as_of"] == "2026-10-06T00:00:00+00:00"


def test_enrich_true_offline_only_never_uses_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_JLC_ENRICH", raising=False)
    build = tmp_path / "build"
    _copy_reference(build)
    api, _store = _client(tmp_path / "store")
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(build), "expected_revision": 0})
    response = api.get("/v1/projects/robot/revisions/1/parts", params={"enrich": True})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["available"] is True
    assert body["enrichment"]["requested"] is True
    assert body["enrichment"]["performed"] is True
    assert body["enrichment"]["providers"] == ["hardware-splicer-catalog"]
    assert all("jlc" not in str(name).lower() for name in body["enrichment"]["providers"])


def test_garbage_schematic_is_422(tmp_path: Path) -> None:
    build = tmp_path / "build"
    comp = build / "build_compilation"
    comp.mkdir(parents=True, exist_ok=True)
    (comp / "board.kicad_sch").write_text("this is not a kicad schematic", encoding="utf-8")
    (comp / "board.kicad_pcb").write_text("(kicad_pcb (version 20240108) (generator pcbnew))\n", encoding="utf-8")
    api, _store = _client(tmp_path / "store")
    saved = api.put(
        "/v1/projects/robot/snapshot",
        json={"snapshot": _snapshot(build), "expected_revision": 0},
    )
    assert saved.json()["artifact_retention"]["status"] == "retained"
    response = api.get("/v1/projects/robot/revisions/1/parts")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "parts_extract_error"


def test_parts_does_not_change_project_bytes(tmp_path: Path) -> None:
    build = tmp_path / "build"
    _copy_reference(build)
    api, store = _client(tmp_path / "store")
    api.put("/v1/projects/robot/snapshot", json={"snapshot": _snapshot(build), "expected_revision": 0})
    project_dir = store.root / "robot"
    before = _hash_tree(project_dir)
    first = api.get("/v1/projects/robot/revisions/1/parts")
    second = api.get("/v1/projects/robot/revisions/1/parts", params={"enrich": False})
    assert first.status_code == 200 and second.status_code == 200
    assert _hash_tree(project_dir) == before
