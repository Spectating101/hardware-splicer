"""Regression: actual printed cable mounts cannot make unqualified wire a display FFC."""
from __future__ import annotations
import copy,hashlib,json,math,shutil
from pathlib import Path
import pytest
from hardware_splicer.function_intent_bridge import parse_intent
from hardware_splicer.function_print_geometry import canonical
from hardware_splicer.functional_hinge_cable_anchors import (
    validate,make_anchors,machine_function_intent,score_route,route_pose,
    cable_against_mounts,printed_mount_clearance,audit,
)

ROOT=Path(__file__).resolve().parents[1]/"examples/functional_hinge_cable_anchors"
PARENT=ROOT.parent/"functional_hinge_cyberdeck"/"reference_spec.json"
RETAINER=ROOT.parent/"functional_hinge_retention"/"spec.json"
OUT=ROOT/"generated"
def sources():
    return json.loads((ROOT/"spec.json").read_text()),json.loads(PARENT.read_text()),json.loads(RETAINER.read_text())
def experiment():
    return json.loads((OUT/"ANCHORED_CABLE_TRIAL.json").read_text())

def test_original_HS_function_intent_extends_existing_assembly_not_duplicate_registry():
    src,hinge,ret=sources()
    validate(src,hinge,ret)
    project,gate=parse_intent(machine_function_intent(src,hinge,ret))
    assert len(project.requirements)==12
    assert len(project.functions)==7
    assert gate["status"]=="FUNCTIONAL_CONCEPT_ONLY"
    assert gate["functional_traceability_pass"] is True
    assert not any(gate["physical_authority"].values())
    assert any(x.requirement_id=="R_DISPLAY_CABLE" for x in project.requirements)

def test_4_real_source_CAD_parts_are_printable_geometry_but_not_qualified_assemblies():
    pytest.importorskip("cadquery");pytest.importorskip("trimesh")
    from cadquery import importers
    import trimesh
    src,hinge,ret=sources()
    report=experiment()
    assert report["schema"]=="hs.cyberdeck_cable_anchor_mechanical_trial.v1"
    assert report["source_spec_sha256"]==hashlib.sha256(canonical(src)).hexdigest()
    assert report["build_gate"]=="BLOCKED_BY_CABLE_AND_CONNECTOR_MISMATCH"
    assert len(report["native_printed_mount_parts"])==4
    for name,record in report["native_printed_mount_parts"].items():
        b=importers.importStep(str(OUT/(name+".step")))
        m=trimesh.load(str(OUT/(name+".stl")),force="mesh")
        assert len(b.solids().vals())==1
        assert b.val().isValid()
        assert m.is_watertight and m.volume>0
        assert math.isclose(b.val().Volume(),record["original_volume_mm3"],abs_tol=.2)
        assert record["actual_watertight_STL"] is True
        assert record["qualified_for_3D_printing"] is False
        assert record["actual_M2_hardware_installed"] is False

def test_new_pair_of_saddles_remain_separated_at_sampled_folds():
    record=experiment()["cross_leaf_full_hinge_motion"]
    assert record["schema"]=="hs.nominal_anchor_added_geometry_clearance.v1"
    assert record["added_mounts_not_colliding_with_each_other"] is True
    assert record["all_cross_interactions_with_original_leaf_reverified"] is False
    assert record["sampled_min_mount_bound_mm"]>1
    assert [r["angle_deg"] for r in record["poses"]]==list(range(0,181,15))
    assert not record["elastic_or_physical_cable_clamp_tested"]

def test_actual_virtual_wire_collides_with_real_printed_guide_solids():
    report=experiment()
    assert len(report["native_cable_tube_against_printed_guides"])==1
    case=report["native_cable_tube_against_printed_guides"][0]
    assert case["mode"]=="medium_44"
    assert case["nominal_round_wire_clear_of_all_printed_guide_solids"] is False
    assert case["sampled_angles_deg"]==[0,90,180]
    volumes=[x["sampled_printed_interference_mm3"] for x in case["per_angle"]]
    assert all(v>1 for v in volumes)
    assert volumes[1]>10
    assert case["actual_wire_strain_relief_proven"] is False

def test_all_4_nominal_paths_fail_bend_plus_folding_requirements():
    src,hinge,ret=sources()
    result=experiment()
    assert len(result["source_bounded_wire_routes"])==4
    by={x["id"]:x for x in result["source_bounded_wire_routes"]}
    assert all(not row["nominal_geometry_screen_pass"] for row in by.values())
    assert all(not row["checks"]["generic_flexible_cable_5x_d_screen"] for row in by.values())
    assert by["medium_44"]["minimum_bend_radius_mm"]<2
    assert by["medium_44"]["folded_cable_height_mm"]<20
    assert by["relaxed_52"]["minimum_bend_radius_mm"]>2
    assert by["relaxed_52"]["folded_cable_height_mm"]>20
    assert result["selected_physically_promotable_design"] is None
    assert result["cable_scenarios_satisfying_all_nominal_geometry_screens"]==[]
    assert all(x["actual_cable_material_verified"] is False for x in by.values())

def test_unsourced_round_wire_cannot_be_marked_molex_display_compatible():
    src,hinge,ret=sources()
    assert src["wire"]["display_data_cable_compatible"] is False
    assert src["wire"]["selected_manufacturer_part"] is None
    assert src["wire"]["datasheet_dynamic_bend_verified"] is False
    altered=copy.deepcopy(src)
    altered["wire"]["display_data_cable_compatible"]=True
    with pytest.raises(ValueError,match="screen data cable"):
        validate(altered,hinge,ret)
    altered=copy.deepcopy(src)
    altered["authority"]["electrical_continuity_verified"]=True
    with pytest.raises(ValueError,match="physical"):
        validate(altered,hinge,ret)

def test_source_material_and_cutout_assumptions_cannot_change_undetected():
    src,hinge,ret=sources()
    altered=copy.deepcopy(src)
    altered["mount"]["channel_nominal_radius_mm"]=.6
    with pytest.raises(ValueError,match="mount"):
        validate(altered,hinge,ret)
    altered=copy.deepcopy(src)
    altered["routes"][1]["free_length_mm"]=47
    with pytest.raises(ValueError,match="route candidates"):
        validate(altered,hinge,ret)

def test_native_full_result_source_and_printed_models_independently_auditable():
    pytest.importorskip("cadquery");pytest.importorskip("trimesh")
    src,hinge,ret=sources()
    result=audit(src,hinge,ret,OUT)
    assert result["reimported_printable_CAD_parts"]==4
    assert result["actual_wire_screens_recomputed"]==4
    assert result["native_source_integrity_pass"]
    assert not result["physical_fabrication_authorized"]
    assert not result["real_display_connection_proven"]

def test_forged_STL_does_not_pass_independent_authority_gate(tmp_path):
    pytest.importorskip("cadquery");pytest.importorskip("trimesh")
    src,hinge,ret=sources()
    where=tmp_path/"forged";shutil.copytree(OUT,where)
    file=where/"upper_removable_saddle_cap.stl"
    file.write_bytes(file.read_bytes()+b"mismatched")
    with pytest.raises(ValueError,match="original print candidate"):
        audit(src,hinge,ret,where)

def test_fake_success_not_accepted_even_with_real_printed_solids(tmp_path):
    pytest.importorskip("cadquery");pytest.importorskip("trimesh")
    src,hinge,ret=sources()
    where=tmp_path/"forged";shutil.copytree(OUT,where)
    p=where/"ANCHORED_CABLE_TRIAL.json"
    data=json.loads(p.read_text());data["selected_physically_promotable_design"]="medium_44"
    data["build_gate"]="READY_TO_BUILD"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="invalid promotion"):
        audit(src,hinge,ret,where)
