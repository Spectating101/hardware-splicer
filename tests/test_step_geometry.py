from __future__ import annotations

import pytest

from hardware_splicer.step_geometry import (
    DeclaredMountInterface,
    build_mechanical_geometry_report,
    parse_step_model,
)


STEP = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('bounded fixture'),'2;1');
FILE_NAME('fixture.step','2026-08-04T00:00:00',('operator'),('lab'),'','','');
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('fixture','Fixture bracket','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(0.0,0.0,0.0));
#4=CARTESIAN_POINT('',(100.0,50.0,10.0));
#5=CARTESIAN_POINT('',(20.0,25.0,5.0));
ENDSEC;
END-ISO-10303-21;
"""


def _models():
    return [
        parse_step_model(STEP, source_id="step-left", model_id="left-model"),
        parse_step_model(STEP, source_id="step-right", model_id="right-model"),
    ]


def _mounts(*, right_spacing_x: float = 40.0):
    pattern_left = {
        "count": 4,
        "spacing_x_mm": 40.0,
        "spacing_y_mm": 20.0,
        "hole_diameter_mm": 3.2,
        "positional_tolerance_mm": 0.1,
        "diameter_tolerance_mm": 0.1,
        "pattern_kind": "rectangular",
    }
    pattern_right = {
        **pattern_left,
        "spacing_x_mm": right_spacing_x,
    }
    return [
        {
            "interface_id": "mount-left",
            "part_id": "left-bracket",
            "cad_model_id": "left-model",
            "mount_type": "flat_flange",
            "mates_with": "mount-right",
            "datum_frame": "left-mount-frame",
            "origin_mm": [20.0, 25.0, 5.0],
            "normal": [0.0, 0.0, 1.0],
            "hole_pattern": pattern_left,
            "fastener_spec": "M3",
            "thickness_mm": 4.0,
        },
        {
            "interface_id": "mount-right",
            "part_id": "right-bracket",
            "cad_model_id": "right-model",
            "mount_type": "flat_flange",
            "mates_with": "mount-left",
            "datum_frame": "right-mount-frame",
            "origin_mm": [20.0, 25.0, 5.0],
            "normal": [0.0, 0.0, -1.0],
            "hole_pattern": pattern_right,
            "fastener_spec": "M3",
            "thickness_mm": 4.0,
        },
    ]


def test_step_parser_preserves_hash_schema_products_units_and_point_envelope() -> None:
    model = parse_step_model(STEP, source_id="fixture-step", model_id="fixture-model")

    assert model.source_id == "fixture-step"
    assert model.model_id == "fixture-model"
    assert model.content_hash.startswith("sha256:")
    assert model.file_schema == ["AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF"]
    assert model.products == ["fixture", "Fixture bracket"]
    assert model.units == "mm"
    assert model.entity_count == 5
    assert model.cartesian_point_count == 3
    assert model.bounding_box is not None
    assert model.bounding_box.minimum == [0.0, 0.0, 0.0]
    assert model.bounding_box.maximum == [100.0, 50.0, 10.0]
    assert model.bounding_box.size == [100.0, 50.0, 10.0]
    assert model.unresolved == []
    assert model.metadata["full_brep_validation"] is False
    assert model.metadata["collision_analysis"] is False
    assert model.metadata["fabrication_authorized"] is False


def test_matching_declared_mount_pair_is_candidate_not_authorized() -> None:
    report = build_mechanical_geometry_report(
        project_id="mechanical-fixture",
        models=_models(),
        mounts=_mounts(),
    )

    assert report.status == "candidate"
    assert report.blocking_checks == []
    assert all(row.status.value == "pass" for row in report.checks)
    pair = next(row for row in report.checks if row.check_id.endswith("hole-pattern"))
    assert pair.metadata["comparisons"]["count"] is True
    assert pair.metadata["comparisons"]["spacing_x_mm"] is True
    assert report.metadata["step_point_envelope_only"] is True
    assert report.metadata["full_brep_validation"] is False
    assert report.metadata["fabrication_authorized"] is False
    assert report.metadata["release_authorized"] is False


def test_hole_pattern_outside_declared_tolerance_blocks_mount_pair() -> None:
    report = build_mechanical_geometry_report(
        project_id="mechanical-fixture",
        models=_models(),
        mounts=_mounts(right_spacing_x=41.0),
    )

    check = next(row for row in report.checks if row.check_id.endswith("hole-pattern"))
    assert check.status.value == "fail"
    assert check.blocking is True
    assert "spacing_x_mm" in check.message
    assert report.status == "blocked"
    assert any(row["check_id"] == check.check_id for row in report.required_evidence)


def test_unknown_model_outside_origin_and_missing_mate_remain_explicit() -> None:
    mounts = _mounts()
    mounts[0]["origin_mm"] = [500.0, 500.0, 500.0]
    mounts[1]["cad_model_id"] = "missing-model"
    mounts[1]["mates_with"] = "missing-mount"

    report = build_mechanical_geometry_report(
        project_id="mechanical-fixture",
        models=_models(),
        mounts=mounts,
    )
    by_id = {row.check_id: row for row in report.checks}

    assert by_id["mount-origin-mount-left"].status.value == "fail"
    assert by_id["mount-model-mount-right"].status.value == "fail"
    assert by_id["mount-mate-mount-right"].status.value == "fail"
    assert report.status == "blocked"


def test_duplicate_model_and_mount_identities_are_blocking() -> None:
    models = _models()
    models.append(models[0].model_copy(deep=True))
    mounts = _mounts()
    mounts.append(dict(mounts[0]))

    report = build_mechanical_geometry_report(
        project_id="mechanical-fixture",
        models=models,
        mounts=mounts,
    )

    collision_ids = {
        row.check_id for row in report.checks if row.category == "identity_collision"
    }
    assert "step-model-identity-left-model" in collision_ids
    assert "mount-identity-mount-left" in collision_ids
    assert report.status == "blocked"


def test_step_parser_rejects_binary_invalid_and_oversized_payloads() -> None:
    with pytest.raises(ValueError, match="binary STEP"):
        parse_step_model(b"ISO-10303-21;\x00END-ISO-10303-21;", source_id="binary")
    with pytest.raises(ValueError, match="ISO-10303-21 boundaries"):
        parse_step_model("not a STEP file", source_id="invalid")
    with pytest.raises(ValueError, match="byte limit"):
        parse_step_model(
            b"ISO-10303-21;" + b" " * (20 * 1024 * 1024) + b"END-ISO-10303-21;",
            source_id="oversized",
        )


def test_imported_mount_cannot_claim_verified_authority() -> None:
    with pytest.raises(ValueError, match="cannot be verified or authorized"):
        DeclaredMountInterface(
            interface_id="mount",
            part_id="part",
            cad_model_id="model",
            mount_type="flat",
            datum_frame="frame",
            authority="verified",
        )
