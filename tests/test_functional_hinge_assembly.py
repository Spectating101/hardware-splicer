"""Hinge assembly function, real solid motion and physically gated printing."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from hardware_splicer.functional_hinge_assembly import (
    validate,machine_function_intent,make_parts,evaluate_motion,spin
)
from hardware_splicer.functional_hinge_audit import audit,fine_selected
from hardware_splicer.function_intent_bridge import parse_intent
from hardware_splicer.function_print_geometry import canonical

HERE=Path(__file__).resolve().parents[1]/"examples/functional_hinge_cyberdeck"
GENERATED=HERE/"generated"

def req():
    return json.loads((HERE/"reference_spec.json").read_text())

def data():
    return json.loads((GENERATED/"HINGE_EVALUATION.json").read_text())

def test_hinge_function_contract_is_owned_by_existing_HS_machine_project():
    model,gate=parse_intent(machine_function_intent(validate(req())))
    assert len(model.requirements)==6
    assert len(model.functions)==3
    assert gate["functional_traceability_pass"]
    assert gate["status"]=="FUNCTIONAL_CONCEPT_ONLY"
    assert all(v is False for v in gate["physical_authority"].values())
    assert model.project_id=="dual_panel_cyberdeck_hinge_reference_v1"
    assert any("wear" in str(x).lower() for x in model.interfaces)
    assert not req()["source_authority"]["physical_fit_verified"]

def test_seven_modelled_alternatives_rejected_for_real_functional_reasons():
    report=data()
    assert report["schema"]=="hs.cyberdeck_mating_hinge_cad.v1"
    assert report["reference_spec_sha256"]==hashlib.sha256(canonical(req())).hexdigest()
    assert report["selected"]=="balanced_60"
    assert report["feasible_order"]==["balanced_60","reinforced_64"]
    assert [x["id"] for x in report["candidates"]]==[x["id"] for x in req()["alternatives"]]
    failed={x["id"]:[key for key,passed in x["checks"].items() if not passed]
            for x in report["candidates"]}
    assert "screen_mockups_no_sweep_intersection" in failed["slim_43"]
    assert "screen_mockups_keep_min_nominal_gap" in failed["compact_51"]
    assert "external_cable_corridor_avoids_printed_solids" in failed["crowded_cable_60"]
    assert "minimum_hinge_radial_wall_mm" in failed["thin_wall_60"]
    assert "folded_printed_shell_thickness_within_limit" in failed["tall_73"]
    assert not failed["balanced_60"] and not failed["reinforced_64"]
    assert not any(report["authority"].values())
    assert report["source_uncertainties"]
    assert len(report["candidates"])==7

def test_native_shape_audit_and_external_pin_are_real_objects():
    pytest.importorskip("cadquery")
    pytest.importorskip("trimesh")
    result=audit(req(),GENERATED)
    assert result["original_real_printed_parts"]==14
    assert result["source_ranked_winner"]=="balanced_60"
    assert result["all_original_BRep_and_mesh_exports_verified"]
    assert result["physical_dimensions_fabrication_verified"] is False
    from cadquery import importers
    for name in ("assembly_open_0.step","assembly_half_90.step",
                 "assembly_folded_180.step"):
        comp=importers.importStep(str(GENERATED/"selected"/name))
        assert len(comp.solids().vals())==3
    for name in ("lower_leaf","upper_leaf"):
        mesh=GENERATED/"selected"/(name+".stl")
        assert mesh.exists() and mesh.stat().st_size>15000

def test_one_degree_report_is_finer_than_original_motion_evidence():
    record=json.loads((GENERATED/"ONE_DEGREE_SWEEP.json").read_text())
    assert record["schema"]=="hs.cyberdeck_hinge_fine_motion_v1"
    assert record["source_spec_sha256"]==hashlib.sha256(canonical(req())).hexdigest()
    assert record["selected"]=="balanced_60" and record["angle_count"]==181
    assert record["step_deg"]==1
    assert record["all_nominal_gates_pass"] is True
    assert record["minimum_mock_screen_gap_mm"]==2.6
    assert record["minimum_printed_clearance_mm"]==1.1814
    assert record["continuous_geometry_collision_proven"] is False
    assert record["actual_cable_bend_fatigue_verified"] is False
    assert [x["angle_deg"] for x in record["checked_intersections_by_angle"]]==list(range(181))
    assert all(x["shell_interference_mm3"]==0
               and x["screen_interference_mm3"]==0
               and x["screen_to_other_leaf_interference_mm3"]==0
               for x in record["checked_intersections_by_angle"])

@pytest.mark.parametrize("section,field",[
    ("source_authority","screen_dimensions_measured"),
    ("source_authority","cable_spec_verified"),
    ("source_authority","physical_fit_verified"),
    ("source_authority","production_release_authorized"),
])
def test_cannot_invent_physical_authority(section,field):
    example=req()
    example[section][field]=True
    with pytest.raises(ValueError,match="NOT verified"):
        validate(example)

def test_cable_nonexistent_is_always_declared_unverified():
    source=req()
    assert source["cable"]["actual_cable_geometry_routed"] is False
    assert source["cable"]["flex_life_tested"] is False
    altered=copy.deepcopy(source)
    altered["cable"]["actual_cable_geometry_routed"]=True
    with pytest.raises(ValueError,match="cable bend envelope"):
        validate(altered)

def test_rejects_unreal_kinematic_rotation_range():
    original=req()
    original["mechanical"]["angle_end_deg"]=360
    with pytest.raises(ValueError,match="mechanical acceptance"):
        validate(original)

def test_actual_pair_and_screen_keepout_collision_for_known_bad_variant():
    pytest.importorskip("cadquery")
    original=req()
    slim=original["alternatives"][0]
    shapes=make_parts(original,slim)
    measured=evaluate_motion(original,slim,shapes,step_deg=15)
    assert measured["nominal_mechanism_feasible"] is False
    assert measured["checks"]["screen_mockups_no_sweep_intersection"] is False
    assert measured["geometry"]["min_modelled_screen_gap_mm"]==0
    assert any(x["screen_interference_mm3"]>0 for x in measured["discrete_sweep"])
    assert measured["checks"]["moving_shells_no_BRep_intersections"] is True

def test_real_good_candidate_mates_and_has_cable_reservation_not_cable():
    pytest.importorskip("cadquery")
    original=req()
    balanced=next(x for x in original["alternatives"] if x["id"]=="balanced_60")
    parts=make_parts(original,balanced)
    result=evaluate_motion(original,balanced,parts,step_deg=15)
    assert result["nominal_mechanism_feasible"]
    assert result["geometry"]["min_modelled_screen_gap_mm"]==2.6
    assert result["geometry"]["min_reserved_cable_corridor_separation_mm"]==2.5
    assert result["geometry"]["folded_solid_height_mm"]==12.0
    assert result["actual_cable_routed"] is False
    assert result["continuous_angle_collision_certified"] is False
    assert not result["physical_screen_or_cable_test_completed"]
    # actual 3mm nominal metal shaft has a 0.5mm diametral bore clearance
    assert result["geometry"]["pin_bore_diametral_clearance_mm"]==.5

def test_source_or_STL_mutation_is_detected(tmp_path):
    pytest.importorskip("cadquery")
    pytest.importorskip("trimesh")
    dest=tmp_path/"mod"
    shutil.copytree(GENERATED,dest)
    t=dest/"candidates"/"balanced_60"/"lower_leaf.stl"
    t.write_bytes(t.read_bytes()+b"unauthorized")
    with pytest.raises(ValueError,match="tampered"):
        audit(req(),dest)
