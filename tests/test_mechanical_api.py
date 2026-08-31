from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.machine_project import MachineProject
from hardware_splicer.product_api import create_product_app
from hardware_splicer.step_geometry import build_mechanical_geometry_report, parse_step_model


STEP = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('fixture','Fixture','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(0.0,0.0,0.0));
#4=CARTESIAN_POINT('',(100.0,50.0,10.0));
ENDSEC;
END-ISO-10303-21;
"""


def _geometry() -> dict:
    models = [
        parse_step_model(STEP, source_id="left.step", model_id="left"),
        parse_step_model(STEP, source_id="right.step", model_id="right"),
    ]
    mounts = [
        {
            "interface_id": "left-mount",
            "part_id": "left-part",
            "cad_model_id": "left",
            "mount_type": "flat_flange",
            "mates_with": "right-mount",
            "datum_frame": "assembly",
            "origin_mm": [10.0, 10.0, 5.0],
            "normal": [0.0, 0.0, 1.0],
            "fastener_spec": "M3",
        },
        {
            "interface_id": "right-mount",
            "part_id": "right-part",
            "cad_model_id": "right",
            "mount_type": "flat_flange",
            "mates_with": "left-mount",
            "datum_frame": "assembly",
            "origin_mm": [10.0, 10.0, 5.0],
            "normal": [0.0, 0.0, -1.0],
            "fastener_spec": "M3",
        },
    ]
    return build_mechanical_geometry_report(
        project_id="mechanical-api",
        models=models,
        mounts=mounts,
    ).model_dump(mode="json")


def _plan() -> dict:
    project = MachineProject.model_validate(
        {
            "project_id": "mechanical-api",
            "name": "Mechanical API",
            "purpose": "Exercise bounded fit APIs.",
        }
    )
    return {
        "machine_project": project.model_dump(mode="json"),
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "robot_topology": {"topology_id": "generic", "unresolved": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {
            "schema_version": "hardware_splicer.manufacturing_closure.v1",
            "project_id": "mechanical-api",
            "checks": [],
            "identity_matrix": {},
            "required_evidence": [],
            "metadata": {},
        },
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "candidate"},
        "scenario": {"compile_spec": {}},
    }


def test_product_mounts_bounded_mechanical_routes() -> None:
    paths = set(create_product_app().openapi()["paths"])

    assert "/v1/engineering/mechanical/schema" in paths
    assert "/v1/engineering/mechanical/geometry/parse" in paths
    assert "/v1/engineering/mechanical/geometry/place" in paths
    assert "/v1/engineering/mechanical/interfaces/access-envelope" in paths
    assert "/v1/engineering/mechanical/geometry/apply" in paths
    assert "/v1/engineering/mechanical/fit/check" in paths
    assert "/v1/engineering/mechanical/fit/apply" in paths


def test_geometry_parse_builds_declared_step_envelope_without_authority() -> None:
    client = TestClient(create_product_app())
    response = client.post(
        "/v1/engineering/mechanical/geometry/parse",
        json={
            "project_id": "mechanical-api",
            "sources": [
                {
                    "source_id": "fixture.step",
                    "model_id": "fixture-mainboard",
                    "content": STEP,
                }
            ],
            "mounts": [],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model_count"] == 1
    assert body["step_point_envelope_only"] is True
    assert body["full_brep_collision"] is False
    assert body["mass_properties_verified"] is False
    assert body["fabrication_authorized"] is False
    model = body["mechanical_geometry"]["models"][0]
    assert model["model_id"] == "fixture-mainboard"
    assert model["authority"] == "declared"
    assert model["bounding_box"]["size"] == [100.0, 50.0, 10.0]
    assert model["bounding_box"]["units"] == "mm"
    assert model["content_hash"].startswith("sha256:")


def test_geometry_parse_rejects_non_step_source() -> None:
    client = TestClient(create_product_app())
    response = client.post(
        "/v1/engineering/mechanical/geometry/parse",
        json={
            "project_id": "mechanical-api",
            "sources": [{"source_id": "bad.step", "content": "not a STEP file"}],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_step_geometry"


def test_geometry_place_rotates_step_envelope_into_explicit_common_frame_without_authority() -> None:
    client = TestClient(create_product_app())
    response = client.post(
        "/v1/engineering/mechanical/geometry/place",
        json={
            "geometry": _geometry(),
            "placements": [
                {
                    "placement_id": "place-left",
                    "object_id": "left-part",
                    "model_id": "left",
                    "target_frame": "assembly",
                    "translation_mm": [10.0, 20.0, 30.0],
                    "rotation_deg_xyz": [0.0, 0.0, 90.0],
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["placement_count"] == 1
    assert body["declared_rigid_placement_only"] is True
    assert body["aabb_only"] is True
    assert body["full_brep_collision"] is False
    assert body["physical_measurement"] is False
    assert body["fabrication_authorized"] is False
    box = body["clearance_boxes"][0]
    assert box["object_id"] == "left-part"
    assert box["frame_id"] == "assembly"
    assert box["state"] == "declared_placement"
    assert box["source_model_id"] == "left"
    assert box["minimum_mm"] == [-40.0, 20.0, 30.0]
    assert box["maximum_mm"][0] == 10.0
    assert box["maximum_mm"][1] == 120.0
    assert box["maximum_mm"][2] == 40.0
    assert box["metadata"]["rotation_convention"] == "Rz*Ry*Rx; canonical STEP XYZ"
    assert box["metadata"]["physical_measurement"] is False


def test_geometry_place_rejects_unknown_model_and_authority_promotion() -> None:
    client = TestClient(create_product_app())
    unknown = client.post(
        "/v1/engineering/mechanical/geometry/place",
        json={
            "geometry": _geometry(),
            "placements": [
                {
                    "placement_id": "missing",
                    "object_id": "missing-part",
                    "model_id": "does-not-exist",
                }
            ],
        },
    )
    assert unknown.status_code == 422
    assert unknown.json()["detail"]["type"] == "invalid_mechanical_placement"

    promoted = client.post(
        "/v1/engineering/mechanical/geometry/place",
        json={
            "geometry": _geometry(),
            "placements": [
                {
                    "placement_id": "promoted",
                    "object_id": "left-part",
                    "model_id": "left",
                    "authority": "verified",
                }
            ],
        },
    )
    assert promoted.status_code == 422


def test_declared_interface_access_builds_outward_keepout_and_can_be_fit_checked() -> None:
    client = TestClient(create_product_app())
    access = client.post(
        "/v1/engineering/mechanical/interfaces/access-envelope",
        json={
            "object_box": {
                "object_id": "left-part",
                "frame_id": "assembly",
                "minimum_mm": [0.0, 0.0, 0.0],
                "maximum_mm": [100.0, 50.0, 10.0],
                "source_model_id": "left",
                "state": "declared_placement",
                "metadata": {"placement_id": "place-left", "placement_authority": "declared"},
            },
            "access": {
                "access_id": "display-egress",
                "interface_id": "if-display",
                "object_id": "left-part",
                "frame_id": "assembly",
                "face": "+x",
                "width_mm": 20.0,
                "height_mm": 10.0,
                "depth_mm": 30.0,
            },
        },
    )

    assert access.status_code == 200, access.text
    body = access.json()
    assert body["declared_interface_access_only"] is True
    assert body["aabb_only"] is True
    assert body["connector_mating_verified"] is False
    assert body["cable_routing_verified"] is False
    assert body["fabrication_authorized"] is False
    box = body["access_box"]
    assert box["object_id"] == "access:display-egress"
    assert box["state"] == "declared_access_envelope"
    assert box["minimum_mm"] == [100.0, 15.0, 0.0]
    assert box["maximum_mm"] == [130.0, 35.0, 10.0]
    assert box["metadata"]["interface_id"] == "if-display"
    assert box["metadata"]["anchor_point_mm"] == [100.0, 25.0, 5.0]
    assert box["metadata"]["outward_normal"] == [1.0, 0.0, 0.0]

    checked = client.post(
        "/v1/engineering/mechanical/fit/check",
        json={
            "geometry": _geometry(),
            "clearance_boxes": [
                box,
                {
                    "object_id": "blocking-display",
                    "frame_id": "assembly",
                    "minimum_mm": [125.0, 20.0, 2.0],
                    "maximum_mm": [150.0, 30.0, 8.0],
                    "state": "declared_placement",
                },
            ],
            "clearance_requirements": [
                {
                    "requirement_id": "display-egress-clear",
                    "first_object_id": "access:display-egress",
                    "second_object_id": "blocking-display",
                    "minimum_clearance_mm": 0.0,
                }
            ],
        },
    )
    assert checked.status_code == 200, checked.text
    fit = checked.json()["mechanical_fit"]
    clearance = next(row for row in fit["checks"] if row["category"] == "aabb_clearance")
    assert clearance["status"] == "fail"
    assert clearance["metadata"]["overlap"] is True
    assert clearance["metadata"]["clearance_mm"] < 0.0
    assert checked.json()["fabrication_authorized"] is False


def test_interface_access_rejects_fixture_geometry_and_authority_promotion() -> None:
    client = TestClient(create_product_app())
    fixture = client.post(
        "/v1/engineering/mechanical/interfaces/access-envelope",
        json={
            "object_box": {
                "object_id": "left-part",
                "frame_id": "assembly",
                "minimum_mm": [0.0, 0.0, 0.0],
                "maximum_mm": [100.0, 50.0, 10.0],
                "state": "fixture",
            },
            "access": {
                "access_id": "fixture-access",
                "interface_id": "if-display",
                "object_id": "left-part",
                "frame_id": "assembly",
                "face": "+x",
                "width_mm": 20.0,
                "height_mm": 10.0,
                "depth_mm": 20.0,
            },
        },
    )
    assert fixture.status_code == 422
    assert fixture.json()["detail"]["type"] == "invalid_interface_access"

    promoted = client.post(
        "/v1/engineering/mechanical/interfaces/access-envelope",
        json={
            "object_box": {
                "object_id": "left-part",
                "frame_id": "assembly",
                "minimum_mm": [0.0, 0.0, 0.0],
                "maximum_mm": [100.0, 50.0, 10.0],
                "state": "declared_placement",
            },
            "access": {
                "access_id": "promoted-access",
                "interface_id": "if-display",
                "object_id": "left-part",
                "frame_id": "assembly",
                "face": "+x",
                "width_mm": 20.0,
                "height_mm": 10.0,
                "depth_mm": 20.0,
                "authority": "verified",
            },
        },
    )
    assert promoted.status_code == 422


def test_fit_check_and_apply_block_clearance_without_authority() -> None:
    client = TestClient(create_product_app())
    checked = client.post(
        "/v1/engineering/mechanical/fit/check",
        json={
            "geometry": _geometry(),
            "clearance_boxes": [
                {
                    "object_id": "arm",
                    "frame_id": "assembly",
                    "minimum_mm": [0.0, 0.0, 0.0],
                    "maximum_mm": [10.0, 10.0, 10.0],
                },
                {
                    "object_id": "enclosure",
                    "frame_id": "assembly",
                    "minimum_mm": [8.0, 2.0, 2.0],
                    "maximum_mm": [20.0, 20.0, 20.0],
                },
            ],
            "clearance_requirements": [
                {
                    "requirement_id": "arm-enclosure",
                    "first_object_id": "arm",
                    "second_object_id": "enclosure",
                    "minimum_clearance_mm": 1.0,
                }
            ],
        },
    )

    assert checked.status_code == 200, checked.text
    check_body = checked.json()
    assert check_body["blocking_check_count"] == 1
    assert check_body["mechanical_fit"]["status"] == "blocked"
    assert check_body["full_brep_collision"] is False
    assert check_body["fabrication_authorized"] is False

    applied = client.post(
        "/v1/engineering/mechanical/fit/apply",
        json={"plan": _plan(), "report": check_body["mechanical_fit"]},
    )

    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["engineering_status"]["current_phase"] == "manufacturing"
    assert body["engineering_status"]["next_actions"][0]["category"] == "manufacturing"
    assert body["engineering_readiness"]["mechanical_fit_blocker_count"] == 1
    assert body["fabrication_authorized"] is False
    assert body["motion_authorized"] is False
