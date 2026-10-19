"""Tight source and inventory honesty checks for SolidCraft -> PartCAD."""
from __future__ import annotations

import json
from pathlib import Path
from hashlib import sha256

import pytest

from hardware_splicer.partcad_assembly_bridge import build_partcad_assembly_package

STEP=Path(__file__).resolve().parents[1]/"examples/solidcraft/native_trial/SOLIDCRAFT_CONCEPT.step"
DIMS={"width":120,"depth":80,"height":25}


def test_package_written_with_provenance_not_ownership(tmp_path):
    out=tmp_path/"conceptual"
    x=build_partcad_assembly_package(
        solidcraft_step=STEP,destination=out,declared_envelope_mm=DIMS,
    )
    assert x["partcad_source_step_sha256"]==sha256(STEP.read_bytes()).hexdigest()
    assert sha256((out/"source.step").read_bytes()).hexdigest()==x["solidcraft_step_source_sha256"]
    package=(out/"partcad.yaml").read_text()
    assy=(out/"assembly.assy").read_text()
    assert "  concept_envelope:\n    type: step" in package
    assert "  conceptual_station:\n    type: assy" in package
    assert "  - part: concept_envelope" in assy
    assert x["usable_quantity"]==0
    assert x["physical_specimen_id"] is None
    assert x["inventree_stock_item_id"] is None
    assert not x["source_is_measured_salvage"]
    assert not x["physical_fabrication_authorized"]
    assert not x["mechanical_fit_verified"]


@pytest.mark.parametrize("bad",["real_salvage","physical_verified","observed","production"])
def test_unsupported_physical_evidence_promotion_rejected(bad,tmp_path):
    with pytest.raises(ValueError,match="authenticated physical"):
        build_partcad_assembly_package(
            solidcraft_step=STEP,destination=tmp_path,source_kind=bad,
            declared_envelope_mm=DIMS,
        )


@pytest.mark.parametrize("bad",["STEP-INJECT\\nother: yes","-bad", "X"*80, ""])
def test_invalid_part_id_rejected(bad,tmp_path):
    with pytest.raises(ValueError):
        build_partcad_assembly_package(
            solidcraft_step=STEP,destination=tmp_path,part_id=bad,
            declared_envelope_mm=DIMS,
        )


def test_missing_declared_dims_blocks_package(tmp_path):
    with pytest.raises(ValueError):
        build_partcad_assembly_package(
            solidcraft_step=STEP,destination=tmp_path,declared_envelope_mm=None,
        )


@pytest.mark.parametrize("value",[0,-1,2300,True,None,float("nan"),float("inf")])
def test_nonphysical_dimension_rejected(value,tmp_path):
    dims={**DIMS,"width":value}
    with pytest.raises(ValueError):
        build_partcad_assembly_package(
            solidcraft_step=STEP,destination=tmp_path,declared_envelope_mm=dims,
        )


def test_no_source_clobber_on_second_run(tmp_path):
    build_partcad_assembly_package(
        solidcraft_step=STEP,destination=tmp_path,declared_envelope_mm=DIMS,
    )
    with pytest.raises(FileExistsError):
        build_partcad_assembly_package(
            solidcraft_step=STEP,destination=tmp_path,declared_envelope_mm=DIMS,
        )


def test_corrupt_step_header_rejected(tmp_path):
    bogus=tmp_path/"bogus.step"
    bogus.write_bytes(b"NOT_STEP"*200)
    with pytest.raises(ValueError,match="STEP header"):
        build_partcad_assembly_package(
            solidcraft_step=bogus,destination=tmp_path/"package",
            declared_envelope_mm=DIMS,
        )


def test_independent_native_geometry_oracle_accepts_actual_export():
    from hardware_splicer.partcad_assembly_bridge import verify_native_solidcraft_roundtrip
    import json
    artifact=Path(__file__).resolve().parents[1]/"docs/evaluations/SOLIDCRAFT_PARTCAD_NATIVE_ROUNDTRIP_2026-10-20.json"
    actual=json.loads(artifact.read_text())["partcad_exported_body_properties"]
    report=verify_native_solidcraft_roundtrip({"bodies":[actual]},DIMS)
    assert report["geometry_checked"]
    assert not report["physical_part_dimensions_authenticated"]


@pytest.mark.parametrize("field,value",[
    ("volume_mm3",120000.0),
    ("area_mm2",5000.0),
    ("faces",5),
    ("edges",11),
    ("center_of_mass",[0,0,0]),
    ("bbox",{"min":[0,0,0],"max":[120,80,250]}),
])
def test_independent_oracle_rejects_wrong_native_geometry(field,value):
    from hardware_splicer.partcad_assembly_bridge import verify_native_solidcraft_roundtrip
    import json
    artifact=Path(__file__).resolve().parents[1]/"docs/evaluations/SOLIDCRAFT_PARTCAD_NATIVE_ROUNDTRIP_2026-10-20.json"
    body=json.loads(artifact.read_text())["partcad_exported_body_properties"]
    changed={**body,field:value}
    result=verify_native_solidcraft_roundtrip({"bodies":[changed]},DIMS)
    assert not result["geometry_checked"]
    assert result["failed_checks"]
