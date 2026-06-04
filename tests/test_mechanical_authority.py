from __future__ import annotations

import pytest

from hardware_splicer import build_mechanical_authority
from hardware_splicer.api import create_app


def _spec(**extra):
    payload = {
        "project_name": "mechanical_authority_unit",
        "machine": {
            "machine_name": "MechanicalAuthorityUnit",
            "boards": [{"board_id": "main_ctrl", "requirements": {}}],
        },
        "mechanism": {
            "project_name": "mechanical_authority_mech",
            "pan_tilt": {"name": "pt", "pan_servo": "sg90", "tilt_servo": "sg90"},
        },
        "use_3d_splicer": False,
    }
    payload.update(extra)
    return payload


def _engineering():
    return {
        "analysis": {
            "mechanism": {
                "ok": True,
                "outputs": ["pt_base.scad", "pt_bracket.scad", "pt_platform.scad"],
                "dfm": [{"severity": "info", "message": "No block-level DFM issue."}],
                "simulation": [
                    {
                        "severity": "info",
                        "domain": "pan_tilt",
                        "model": "high",
                        "message": "Tilt torque safety factor is acceptable.",
                        "metrics": {"tilt_torque_safety_factor_x": 2.4},
                    }
                ],
                "safety": [{"severity": "info", "message": "Motion subsystem present; add startup interlock."}],
            }
        }
    }


def _measurement_capture():
    return {
        "artifact_uris": ["session://mech/measurement-log"],
        "dimensions": [
            {"target": "servo pocket width", "value_mm": 23.2, "status": "verified"},
            {"target": "bracket wall", "value_mm": 6.1, "status": "verified"},
        ],
        "clearances": [{"target": "servo body clearance", "clearance_mm": 0.55, "status": "pass"}],
        "materials": [{"target": "printed bracket", "material": "PETG", "status": "verified"}],
    }


def _bench_capture():
    return {
        "artifact_uris": ["session://mech/bench-video", "session://mech/load-log"],
        "fit_checks": [{"target": "servo insertion", "status": "pass"}],
        "load_tests": [{"target": "camera payload static hold", "status": "pass"}],
        "motion_tests": [{"target": "pan tilt sweep", "status": "pass"}],
    }


def _release():
    return {
        "scope_statement": "Release is limited to the measured SG90 pan-tilt camera bracket under 0.4 kg payload.",
        "artifact_uris": ["session://mech/release-pack"],
        "acceptance_reviewed": True,
    }


def test_mechanical_authority_blocks_release_without_measured_geometry():
    authority = build_mechanical_authority(_spec(), engineering=_engineering())

    assert authority["current_authority_level"] == "reference_geometry"
    assert authority["authority_score"] == 0.34
    assert authority["production_authorized"] is False
    assert authority["next_action_id"] == "close_measured_geometry"
    assert authority["can"]["print_reference_prototype"] is True
    assert authority["can"]["claim_production_mechanical_release"] is False


def test_mechanical_authority_authorizes_scoped_release_with_closed_evidence():
    authority = build_mechanical_authority(
        _spec(
            mechanical_measurement_capture=_measurement_capture(),
            mechanical_bench_capture=_bench_capture(),
            mechanical_release=_release(),
        ),
        engineering=_engineering(),
    )

    assert authority["current_authority_level"] == "production_mechanical_release"
    assert authority["authority_score"] == 1.0
    assert authority["production_authorized"] is True
    assert authority["can"]["use_measured_interfaces"] is True
    assert authority["can"]["claim_production_mechanical_release"] is True
    assert all(stage["status"] == "pass" for stage in authority["stages"])


def test_mechanical_authority_api_returns_authority_packet():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.post(
        "/v1/mechanical-authority",
        json={
            "spec": _spec(
                mechanical_measurement_capture=_measurement_capture(),
                mechanical_bench_capture=_bench_capture(),
                mechanical_release=_release(),
            ),
            "engineering": _engineering(),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "hardware_splicer.mechanical_authority.v1"
    assert data["production_authorized"] is True
