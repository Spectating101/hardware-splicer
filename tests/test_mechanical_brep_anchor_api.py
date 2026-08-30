from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

import hardware_splicer.mechanical_brep_anchor as brep_anchor
from hardware_splicer.engineering_source_ingestion import (
    EngineeringSourceIngestionRequest,
    ingest_engineering_source,
)
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('fixture','Fixture','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(-5.0,-4.0,-3.0));
#4=CARTESIAN_POINT('',(5.0,4.0,3.0));
ENDSEC;
END-ISO-10303-21;
"""


def _hash(content: str = STEP) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _placement() -> dict:
    return {
        "placement_id": "place-fixture",
        "object_id": "cmp-fixture",
        "model_id": "fixture",
        "target_frame": "assembly",
        "translation_mm": [20.0, 0.0, 0.0],
        "rotation_deg_xyz": [0.0, 0.0, 0.0],
        "authority": "declared",
    }


def _request() -> dict:
    return {
        "project_id": "anchor-api",
        "anchor_id": "anchor-usb",
        "interface_id": "if-usb",
        "source": {
            "source_id": "fixture.step",
            "model_id": "fixture",
            "content_hash": _hash(),
            "content": STEP,
        },
        "placement": _placement(),
        "probe_point_mm": [25.1, 0.0, 0.0],
        "max_snap_distance_mm": 1.0,
    }


def _stored_project(tmp_path: Path) -> tuple[ProjectStore, dict]:
    project_id = "anchor-stored"
    store = ProjectStore(tmp_path)
    store.save(
        project_id,
        {"projectId": project_id, "projectName": "Stored STEP anchor", "engineeringSources": []},
        expected_revision=0,
        metadata={"source": "test"},
    )
    result = ingest_engineering_source(
        EngineeringSourceIngestionRequest(
            project_id=project_id,
            filename="fixture.step",
            content_base64=base64.b64encode(STEP.encode("utf-8")).decode("ascii"),
        ),
        project_root=tmp_path,
    )
    source = result.source_descriptor
    snapshot = store.load(project_id)["snapshot"]
    snapshot["engineeringSources"] = [source]
    store.save(project_id, snapshot, expected_revision=1, metadata={"source": "registered_step_source"})
    return store, source


def test_product_mounts_brep_surface_anchor_routes() -> None:
    client = TestClient(create_product_app())
    paths = set(client.get("/openapi.json").json()["paths"])
    assert "/v1/engineering/mechanical/geometry/brep/anchor" in paths
    assert "/v1/engineering/mechanical/geometry/brep/anchor/stored" in paths
    assert "/v1/engineering/mechanical/geometry/brep/anchor/schema" in paths

    body = client.get("/v1/engineering/mechanical/geometry/brep/anchor/schema").json()
    assert body["optional_kernel"] == "cadquery-isolated"
    assert body["hash_bound_source_required"] is True
    assert body["declared_placement_required"] is True
    assert body["kernel_surface_snap"] is True
    assert body["interface_binding_declared"] is True
    assert body["connector_mating_verified"] is False
    assert body["physical_measurement"] is False
    assert body["fabrication_authorized"] is False


def test_inline_anchor_stays_unknown_without_kernel_and_never_invents_surface(monkeypatch) -> None:
    monkeypatch.setattr(brep_anchor, "_cadquery_available", lambda: False)
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/anchor",
        json=_request(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kernel_available"] is False
    assert body["exact_brep_surface_anchor_evaluated"] is False
    assert body["interface_binding_declared"] is True
    assert body["connector_mating_verified"] is False
    report = body["brep_surface_anchor"]
    assert report["status"] == "unknown"
    assert report["anchor_point_mm"] is None
    assert report["outward_normal"] is None
    assert report["interface_id"] == "if-usb"
    assert report["placement_id"] == "place-fixture"


def test_inline_anchor_rejects_changed_bytes_against_hash_before_kernel(monkeypatch) -> None:
    monkeypatch.setattr(
        brep_anchor,
        "_cadquery_available",
        lambda: (_ for _ in ()).throw(AssertionError("kernel discovery must not run after hash mismatch")),
    )
    request = _request()
    request["source"]["content"] = STEP.replace("(5.0,4.0,3.0)", "(6.0,4.0,3.0)")
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/anchor",
        json=request,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_brep_surface_anchor_request"
    assert "expected canonical content_hash" in response.json()["detail"]["message"]


def test_stored_anchor_reopens_registered_blob_and_reverifies_hash(tmp_path: Path, monkeypatch) -> None:
    store, source = _stored_project(tmp_path)
    monkeypatch.setattr(brep_anchor, "_cadquery_available", lambda: False)
    request = {
        "project_id": "anchor-stored",
        "anchor_id": "anchor-usb",
        "interface_id": "if-usb",
        "source": {
            "source_id": source["source_id"],
            "content_hash": source["content_hash"],
            "model_id": "fixture",
        },
        "placement": _placement(),
        "probe_point_mm": [25.1, 0.0, 0.0],
        "max_snap_distance_mm": 1.0,
    }
    response = TestClient(create_product_app(store)).post(
        "/v1/engineering/mechanical/geometry/brep/anchor/stored",
        json=request,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["registered_source_materialized"] is True
    assert body["registered_source_hash_reverified"] is True
    assert body["raw_registered_source_bytes_returned"] is False
    report = body["brep_surface_anchor"]
    assert report["content_hash"] == source["content_hash"]
    assert report["metadata"]["source_materialization"] == "registered_blob_hash_reverified_server_side"
    assert STEP not in response.text


def test_stored_anchor_rejects_tampered_blob_before_kernel_discovery(tmp_path: Path, monkeypatch) -> None:
    store, source = _stored_project(tmp_path)
    monkeypatch.setattr(
        brep_anchor,
        "_cadquery_available",
        lambda: (_ for _ in ()).throw(AssertionError("kernel discovery must not run after blob tamper")),
    )
    blob = tmp_path / "anchor-stored" / source["metadata"]["blob_ref"]
    blob.write_bytes(b"tampered")
    request = {
        "project_id": "anchor-stored",
        "anchor_id": "anchor-usb",
        "interface_id": "if-usb",
        "source": {
            "source_id": source["source_id"],
            "content_hash": source["content_hash"],
            "model_id": "fixture",
        },
        "placement": _placement(),
        "probe_point_mm": [25.1, 0.0, 0.0],
        "max_snap_distance_mm": 1.0,
    }
    response = TestClient(create_product_app(store)).post(
        "/v1/engineering/mechanical/geometry/brep/anchor/stored",
        json=request,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_stored_brep_surface_anchor_request"
    assert "no longer matches its content_hash" in detail["message"]
