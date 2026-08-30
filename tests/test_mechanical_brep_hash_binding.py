from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

import hardware_splicer.mechanical_brep as mechanical_brep
from hardware_splicer.product_api import create_product_app


STEP_LEFT = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('left','Left','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(0.0,0.0,0.0));
#4=CARTESIAN_POINT('',(10.0,10.0,10.0));
ENDSEC;
END-ISO-10303-21;
"""
STEP_RIGHT = STEP_LEFT.replace("'left','Left'", "'right','Right'")


def _hash(content: str) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _placement(placement_id: str, object_id: str, model_id: str, x: float) -> dict:
    return {
        "placement_id": placement_id,
        "object_id": object_id,
        "model_id": model_id,
        "target_frame": "assembly",
        "translation_mm": [x, 0.0, 0.0],
        "rotation_deg_xyz": [0.0, 0.0, 0.0],
        "authority": "declared",
    }


def _request() -> dict:
    return {
        "project_id": "inline-hash-bind",
        "first_source": {
            "source_id": "left.step",
            "model_id": "left",
            "content_hash": _hash(STEP_LEFT),
            "content": STEP_LEFT,
        },
        "second_source": {
            "source_id": "right.step",
            "model_id": "right",
            "content_hash": _hash(STEP_RIGHT),
            "content": STEP_RIGHT,
        },
        "first_placement": _placement("place-left", "left-object", "left", 0.0),
        "second_placement": _placement("place-right", "right-object", "right", 20.0),
        "minimum_clearance_mm": 5.0,
    }


def test_inline_brep_accepts_parser_issued_hash_identity_when_bytes_match(monkeypatch) -> None:
    monkeypatch.setattr(mechanical_brep, "_cadquery_available", lambda: False)
    client = TestClient(create_product_app())

    response = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference",
        json=_request(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["brep_interference"]["first_content_hash"] == _hash(STEP_LEFT)
    assert body["brep_interference"]["second_content_hash"] == _hash(STEP_RIGHT)
    assert body["exact_pair_interference_evaluated"] is False
    assert body["aabb_fallback_used"] is False


def test_inline_brep_rejects_changed_bytes_against_parser_issued_hash_before_exact_claim(monkeypatch) -> None:
    monkeypatch.setattr(mechanical_brep, "_cadquery_available", lambda: False)
    client = TestClient(create_product_app())
    request = _request()
    request["first_source"]["content"] = STEP_LEFT.replace("(10.0,10.0,10.0)", "(11.0,10.0,10.0)")

    response = client.post(
        "/v1/engineering/mechanical/geometry/brep/interference",
        json=request,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["type"] == "invalid_brep_interference_request"
    assert detail["message"] == "first inline STEP content no longer matches its expected canonical content_hash"
