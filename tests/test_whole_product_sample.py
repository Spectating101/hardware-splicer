"""Product-level acceptance: actual device composition, function, usability and scope."""
from __future__ import annotations
import copy,hashlib,json
from pathlib import Path
import pytest
from hardware_splicer.whole_product_sample import validate_product,check_flow_graph,scad

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"examples/products/clearbench_s1_product.json"
def spec():return json.loads(SRC.read_text())
def upstream():return {"project_id":"water_filter_nonpotable_bench_001"}

def test_integrated_device_has_clear_function_user_and_complete_roles():
    data=spec()
    output=validate_product(data,upstream())
    assert output["symbolic_inlet_to_sample_connected"]
    assert output["every_symbolic_sample_path_traverses_filter"]
    assert not output["actual_hydraulic_connectivity_assembled"]
    assert [x["stage"] for x in data["operator_workflow"]]==[
        "SETUP","CONNECT","MONITOR","SAMPLE","MAINTAIN"]
    assert data["platform_envelope_mm"]=={"width":450,"depth":260,"height":740}
    assert len(data["product_bom"])==11
    assert all(x["engineering_status"]!="QUALIFIED" for x in data["product_bom"])
    assert len(data["product_acceptance"])==6
    assert not any(data["physical_authority"].values())

def test_entire_product_scene_not_just_component_envelopes():
    source=scad(spec())
    assert "module product_scene()" in source
    assert "module flow_lines()" in source
    assert "module product_tray()" in source
    assert "module back_panel()" in source
    assert "module sampling_cup()" in source
    assert "module dial(pos)" in source
    assert "NON-POTABLE" in source
    for p in ('part=="assembly"','part=="housing"','part=="service"','part=="sample"'):
        assert p in source

def test_refuse_any_fluid_bypass():
    v=spec()
    v["functional_flow_graph"]["edges"][1]=[
       "inlet_pressure_observation","outlet_pressure_observation"]
    with pytest.raises(ValueError,match="bypass"):
        validate_product(v,upstream())

def test_refuse_commercial_release_and_false_functioning_device():
    v=spec()
    v["physical_authority"]["wet_operation"]=True
    with pytest.raises(ValueError,match="physical product authority"):
        validate_product(v,upstream())
    v=spec()
    v["functional_target"]["demonstrated"]=True
    with pytest.raises(ValueError,match="function targets"):
        validate_product(v,upstream())

def test_wrong_vendor_housing_or_unapproved_bracket_detected():
    v=spec()
    v["source_integrity"]["housing_part"]="158110"
    with pytest.raises(ValueError,match="source does not match"):
        validate_product(v,upstream())
    v=spec()
    v["layout"]["mounting"]["boss_pitch_mm"]=45
    with pytest.raises(ValueError,match="mounting was falsely"):
        validate_product(v,upstream())

def test_incomplete_total_product_bom_and_false_prices_rejected():
    v=spec()
    v["product_bom"]=[x for x in v["product_bom"] if x["ref"]!="V1"]
    with pytest.raises(ValueError,match="bill of materials missing"):
        validate_product(v,upstream())
    v=spec()
    next(x for x in v["product_bom"] if x["ref"]=="P1")["part_number"]="UNVERIFIED-001"
    with pytest.raises(ValueError,match="(?:unsourced fittings|manufacturer product variants changed)"):
        validate_product(v,upstream())

def test_service_volume_cannot_intersect_tray_or_be_claimed_qualified():
    v=spec()
    v["layout"]["service_region"]["bottom_z_mm"]=5
    with pytest.raises(ValueError,match="service corridor promoted"):
        validate_product(v,upstream())
    v=spec()
    v["layout"]["service_region"]["qualified"]=True
    with pytest.raises(ValueError,match="service corridor promoted"):
        validate_product(v,upstream())

def test_operator_cannot_claim_completed_wet_testing():
    v=spec()
    v["operator_workflow"][2]["state"]="TESTED"
    with pytest.raises(ValueError,match="operator workflow"):
        validate_product(v,upstream())
    v=spec()
    v["product_acceptance"][-1]["status"]="PASS"
    with pytest.raises(ValueError,match="physical acceptance"):
        validate_product(v,upstream())

def test_product_assembly_cannot_be_assigned_to_different_function():
    with pytest.raises(ValueError,match="functional purpose"):
        validate_product(spec(),{"project_id":"water_purification_drinking_001"})
