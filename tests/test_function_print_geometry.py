"""Real native STEP/STL + function-led optimization, with honest proof levels."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import pytest

from hardware_splicer.function_intent_bridge import parse_intent
from hardware_splicer.function_print_geometry import (
    validate_design,function_intent,run_design,audit_bundle,
)

HERE=Path(__file__).resolve().parents[1]/"examples/print_function_pilot/pcb_service_stand"
def original():
    return json.loads((HERE/"design_request.json").read_text())

def test_real_functional_machineproject_traceability_before_CAD():
    req=validate_design(original())
    model,gate=parse_intent(function_intent(req))
    assert len(model.requirements)==5
    assert len(model.functions)==3
    assert gate["functional_traceability_pass"] is True
    assert gate["status"]=="FUNCTIONAL_CONCEPT_ONLY"
    assert all(not x for x in gate["physical_authority"].values())
    assert all(v.status.value=="planned" for v in model.verifications)
    assert any("shrinkage" in x.lower() for i in model.interfaces for c in i.contracts for x in c.unresolved_fields)

@pytest.mark.parametrize("section,key,value,needle",[
    ("board","dimensions_physically_measured",True,"measurement is unverified"),
    ("safety","ESD_certified",True,"unverified physical authority"),
    ("safety","print_approved",True,"unverified physical authority"),
    ("printer","profile_verified",True,"calibrated printer"),
    ("stability","board_mass_measured",True,"calibrated printer"),
    ("board","nominal_thickness_mm",-1,"board thickness"),
    ("fit","per_side_clearance_mm",0,"per-side slot"),
    ("printer","nozzle_mm",0,"nozzle diameter"),
])
def test_false_physical_authority_or_invalid_input_refused(section,key,value,needle):
    req=original()
    req[section][key]=value
    with pytest.raises(ValueError,match=needle):
        validate_design(req)

def test_stale_topology_or_duplicate_design_refused():
    req=original()
    req["alternatives"][0]["style"]="magic"
    with pytest.raises(ValueError,match="unregistered fabrication"):
        validate_design(req)
    req=original()
    req["alternatives"][1]["id"]=req["alternatives"][0]["id"]
    with pytest.raises(ValueError,match="duplicate"):
        validate_design(req)

def test_native_CAD_search_exports_real_watertight_STEP_and_STL(tmp_path):
    pytest.importorskip("cadquery")
    pytest.importorskip("trimesh")
    req=original()
    result=run_design(req,tmp_path/"trial")
    assert result["selected"]=="ladder_58"
    assert result["ranked_feasible"]==["ladder_58","ladder_64","reinforced_68","solid_plate"]
    assert result["vs_plate_solid_volume_reduction_pct"]==39.9
    assert result["existing_HS_machine_project_traceability"]["status"]=="FUNCTIONAL_CONCEPT_ONLY"
    assert all(not x for x in result["authority"].values())
    assert len(result["alternatives"])==6
    for alt in result["alternatives"]:
        assert alt["checks"]["brep_single_valid_solid"] is True
        assert alt["checks"]["step_volume_roundtrip_0_5pct"] is True
        assert alt["checks"]["stl_watertight"] is True
        assert alt["checks"]["nominal_board_noninterference"] is True
        assert alt["geometry"]["minimum_upright_wall_mm"]>=3
        assert alt["geometry"]["slot_opening_mm"]==pytest.approx(2.2)
        assert alt["actual_slicer_used"] is False
        assert alt["ESD_material_qualified"] is False
    assert result["alternatives"][1]["numeric_feasible"] is False
    assert result["alternatives"][2]["numeric_feasible"] is False
    audit=audit_bundle(req,tmp_path/"trial")
    assert audit["native_shape_count"]==6
    assert audit["selected"]=="ladder_58"
    assert audit["nonfabrication_authority_preserved"]
    assert audit["source_concept_traceability_verified"]
    with pytest.raises(ValueError,match="overwrite"):
        run_design(req,tmp_path/"trial")

def test_higher_declared_lateral_push_changes_selected_design(tmp_path):
    pytest.importorskip("cadquery")
    req=original()
    req["stability"]["hypothetical_lateral_force_n"]=0.16
    result=run_design(req,tmp_path/"higher_push")
    assert result["selected"]=="solid_plate"
    assert result["ranked_feasible"]==["solid_plate"]
    assert result["vs_plate_solid_volume_reduction_pct"]==0
    assert audit_bundle(req,tmp_path/"higher_push")["selected"]=="solid_plate"

def test_source_or_export_tamper_prevents_false_native_evidence(tmp_path):
    pytest.importorskip("cadquery")
    req=original()
    folder=tmp_path/"shapes"
    run_design(req,folder)
    assert audit_bundle(req,folder)["selected"]=="ladder_58"
    obj=folder/"candidates"/"ladder_58"/"ladder_58.stl"
    obj.write_bytes(obj.read_bytes()+b"spoofed output")
    with pytest.raises(ValueError,match="native CAD geometry changed"):
        audit_bundle(req,folder)

def test_documented_example_reimport_against_source_if_present():
    pytest.importorskip("cadquery")
    folder=HERE/"generated"
    if not (folder/"FUNCTION_GEOMETRY_EVALUATION.json").exists():
        pytest.skip("native output not yet published on disk")
    audit=audit_bundle(original(),folder)
    assert audit["native_shape_count"]==6
    assert audit["selected"]=="ladder_58"
