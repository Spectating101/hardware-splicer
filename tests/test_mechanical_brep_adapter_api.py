from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

import hardware_splicer.mechanical_brep_adapter as brep_adapter
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
#3=CARTESIAN_POINT('',(-5.0,-5.0,-5.0));
#4=CARTESIAN_POINT('',(5.0,5.0,5.0));
ENDSEC;
END-ISO-10303-21;
"""


def _hash(content: str = STEP) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _placement(side: str, x: float) -> dict:
    return {
        "placement_id": f"place-{side}",
        "object_id": f"cmp-{side}",
        "model_id": side,
        "target_frame": "assembly",
        "translation_mm": [x, 0.0, 0.0],
        "rotation_deg_xyz": [0.0, 0.0, 0.0],
        "authority": "declared",
    }


def _anchor(side: str, point, normal, *, source_id: str | None = None, content_hash: str | None = None) -> dict:
    return {
        "anchor_id": f"anchor-{side}",
        "interface_id": f"if-{side}",
        "object_id": f"cmp-{side}",
        "source_id": source_id or f"{side}.step",
        "model_id": side,
        "content_hash": content_hash or _hash(),
        "placement_id": f"place-{side}",
        "frame_id": "assembly",
        "anchor_point_mm": point,
        "outward_normal": normal,
        "face_index": 1,
        "face_geom_type": "PLANE",
        "authority": "declared",
        "status": "ready",
        "kernel_surface_snap": True,
        "connector_mating_verified": False,
        "physical_measurement": False,
        "fabrication_authorized": False,
    }


def _inline_request() -> dict:
    return {
        "project_id": "adapter-api",
        "adapter_id": "bridge-a-b",
        "first": {
            "source": {
                "source_id": "left.step",
                "model_id": "left",
                "content_hash": _hash(),
                "content": STEP,
            },
            "placement": _placement("left", 0.0),
            "anchor": _anchor("left", [5.0, 0.0, 0.0], [1.0, 0.0, 0.0]),
        },
        "second": {
            "source": {
                "source_id": "right.step",
                "model_id": "right",
                "content_hash": _hash(),
                "content": STEP,
            },
            "placement": _placement("right", 20.0),
            "anchor": _anchor("right", [15.0, 0.0, 0.0], [-1.0, 0.0, 0.0]),
        },
        "parameters": {"width_mm": 4.0, "thickness_mm": 4.0},
    }


def _stored_project(tmp_path: Path) -> tuple[ProjectStore, dict, dict]:
    project_id = "adapter-stored"
    store = ProjectStore(tmp_path)
    store.save(
        project_id,
        {"projectId": project_id, "projectName": "Stored adapter parents", "engineeringSources": []},
        expected_revision=0,
        metadata={"source": "test"},
    )
    sources = []
    for filename in ("left.step", "right.step"):
        result = ingest_engineering_source(
            EngineeringSourceIngestionRequest(
                project_id=project_id,
                filename=filename,
                content_base64=base64.b64encode(STEP.encode("utf-8")).decode("ascii"),
            ),
            project_root=tmp_path,
        )
        sources.append(result.source_descriptor)
    snapshot = store.load(project_id)["snapshot"]
    snapshot["engineeringSources"] = sources
    store.save(project_id, snapshot, expected_revision=1, metadata={"source": "registered_adapter_sources"})
    return store, sources[0], sources[1]


def test_product_mounts_brep_adapter_routes() -> None:
    client = TestClient(create_product_app())
    paths = set(client.get("/openapi.json").json()["paths"])
    assert "/v1/engineering/mechanical/geometry/brep/adapter/synthesize" in paths
    assert "/v1/engineering/mechanical/geometry/brep/adapter/synthesize/stored" in paths
    assert "/v1/engineering/mechanical/geometry/brep/adapter/schema" in paths

    body = client.get("/v1/engineering/mechanical/geometry/brep/adapter/schema").json()
    assert body["supported_families"] == ["bridge_block_v0"]
    assert body["requires_two_ready_exact_surface_anchors"] is True
    assert body["requires_planar_anchor_faces"] is True
    assert body["generated_step_export"] is True
    assert body["exact_parent_contact_checked"] is True
    assert body["exact_parent_penetration_checked"] is True
    assert body["structural_analysis"] is False
    assert body["fabrication_authorized"] is False


def test_inline_adapter_stays_unknown_without_kernel_and_keeps_authority_closed(monkeypatch) -> None:
    monkeypatch.setattr(brep_adapter, "_cadquery_available", lambda: False)
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/adapter/synthesize",
        json=_inline_request(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kernel_available"] is False
    assert body["exact_adapter_geometry_evaluated"] is False
    assert body["generated_step_available"] is False
    assert body["geometric_candidate_only"] is True
    assert body["fabrication_authorized"] is False
    report = body["brep_adapter_candidate"]
    assert report["status"] == "unknown"
    assert report["generated_step_content"] is None
    assert report["required_evidence"][0]["field"] == "cadquery-isolated"


def test_inline_adapter_rejects_changed_parent_bytes_before_kernel(monkeypatch) -> None:
    monkeypatch.setattr(
        brep_adapter,
        "_cadquery_available",
        lambda: (_ for _ in ()).throw(AssertionError("kernel discovery must not run after hash mismatch")),
    )
    request = _inline_request()
    request["first"]["source"]["content"] = STEP.replace("(5.0,5.0,5.0)", "(6.0,5.0,5.0)")
    response = TestClient(create_product_app()).post(
        "/v1/engineering/mechanical/geometry/brep/adapter/synthesize",
        json=request,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_brep_adapter_request"
    assert "expected canonical content_hash" in detail["message"]


def test_stored_adapter_reopens_both_registered_blobs_without_returning_parent_step(tmp_path: Path, monkeypatch) -> None:
    store, left, right = _stored_project(tmp_path)
    monkeypatch.setattr(brep_adapter, "_cadquery_available", lambda: False)
    request = {
        "project_id": "adapter-stored",
        "adapter_id": "bridge-stored",
        "first": {
            "source": {
                "source_id": left["source_id"],
                "content_hash": left["content_hash"],
                "model_id": "left",
            },
            "placement": _placement("left", 0.0),
            "anchor": _anchor(
                "left",
                [5.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                source_id=left["source_id"],
                content_hash=left["content_hash"],
            ),
        },
        "second": {
            "source": {
                "source_id": right["source_id"],
                "content_hash": right["content_hash"],
                "model_id": "right",
            },
            "placement": _placement("right", 20.0),
            "anchor": _anchor(
                "right",
                [15.0, 0.0, 0.0],
                [-1.0, 0.0, 0.0],
                source_id=right["source_id"],
                content_hash=right["content_hash"],
            ),
        },
        "parameters": {"width_mm": 4.0, "thickness_mm": 4.0},
    }
    response = TestClient(create_product_app(store)).post(
        "/v1/engineering/mechanical/geometry/brep/adapter/synthesize/stored",
        json=request,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["registered_sources_materialized"] is True
    assert body["registered_source_hashes_reverified"] is True
    assert body["raw_registered_parent_bytes_returned"] is False
    report = body["brep_adapter_candidate"]
    assert report["first_content_hash"] == left["content_hash"]
    assert report["second_content_hash"] == right["content_hash"]
    assert report["metadata"]["source_materialization"] == "registered_blobs_hash_reverified_server_side"
    assert STEP not in response.text
