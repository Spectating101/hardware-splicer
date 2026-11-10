"""Hinge pin C-ring and real swept-wire geometry, no false physical claims."""
from __future__ import annotations
import copy,hashlib,json,shutil
from pathlib import Path
import pytest

from hardware_splicer.functional_hinge_retention import (
    checked_sources,make_retainer,inspect_pin,evaluate_routes,_cable_samples,
    make_cable_envelope,extra_function_intent,audit,
)
from hardware_splicer.function_intent_bridge import parse_intent
from hardware_splicer.function_print_geometry import canonical
HERE=Path(__file__).resolve().parents[1]/"examples/functional_hinge_retention"
PARENT=HERE.parent/"functional_hinge_cyberdeck"/"reference_spec.json"
def specimen():
    return json.loads((HERE/"spec.json").read_text()),json.loads(PARENT.read_text())
def receipt():
    return json.loads((HERE/"generated/RETENTION_AND_CABLE_TRIAL.json").read_text())

def test_original_hinge_intent_extended_in_existing_machine_project():
    req,base=specimen()
    model,gate=parse_intent(extra_function_intent(req,base))
    assert len(model.requirements)==9
    assert len(model.functions)==5
    assert gate["functional_traceability_pass"]
    assert gate["status"]=="FUNCTIONAL_CONCEPT_ONLY"
    assert not any(gate["physical_authority"].values())
    assert "R_RETAINER" in [r.requirement_id for r in model.requirements]
    assert "R_WIRE_PATH" in [r.requirement_id for r in model.requirements]
    assert model.project_id=="dual_panel_cyberdeck_hinge_reference_v1"

def test_fixed_source_and_nominal_pin_retaining_geometry():
    req,base=specimen()
    checked_sources(req,base)
    record=receipt()
    assert record["source_spec_sha256"]==hashlib.sha256(canonical(req)).hexdigest()
    pin=record["nominal_retainer_geometry"]
    assert pin["nominal_cad_checks_pass"] is True
    assert pin["nominal_total_axial_float_mm"]==3.7
    assert pin["nominal_clip_axial_stop_to_barrel_mm"]==1.85
    assert pin["minimum_swept_clip_to_leaf_mm"]==1.85
    assert pin["minimum_swept_shaft_to_leaf_mm"]==.25
    assert all(pin["checks"].values())
    assert len(pin["motion_samples"])==37
    assert all(not pin[k] for k in (
       "spring_clip_installable_verified","clip_strength_or_axial_load_verified",
       "real_machined_pin_or_ring_available","continuous_angle_clearance_certified"
    ))

def test_real_C_clips_are_open_and_groove_is_actual_BREP():
    pytest.importorskip("cadquery")
    req,base=specimen()
    shapes=make_retainer(req,base)
    assert set(shapes)=={"shaft","ring_left","ring_right"}
    assert all(x.isValid() for x in shapes.values())
    assert shapes["ring_left"].Volume()<18
    assert shapes["ring_right"].Volume()<18
    assert 660<shapes["shaft"].Volume()<680
    eval_=inspect_pin(req,base,angles=(0,90,180))
    assert eval_["nominal_cad_checks_pass"] is True
    assert eval_["minimum_swept_clip_to_leaf_mm"]>=.65

def test_four_route_candidates_avoid_unsupported_success_claim():
    req,base=specimen()
    report=receipt()
    rows=report["wire_routing_sweep"]
    assert rows["selected_virtual_route"]=="roomy_bend_relief"
    assert rows["original_empty_keepout_insufficient_for_actual_nominal_route"] is True
    assert rows["all_route_endpoints_unattached"] is True
    assert rows["routing_is_not_an_electrical_connection"] is True
    failures={x["id"]:x for x in rows["route_candidates"]}
    assert len(failures)==4
    assert failures["compact_low_bend"]["minimum_bend_radius_mm"]<2
    assert failures["compact_low_bend"]["nominal_virtual_route_feasible"] is False
    assert failures["medium_low_bend"]["route_solved"] is False
    assert failures["tall_bend_relief"]["packed_envelope_height_including_cable_mm"]>20
    chosen=failures["roomy_bend_relief"]
    assert chosen["nominal_virtual_route_feasible"] is True
    assert chosen["minimum_bend_radius_mm"]>2
    assert chosen["nominal_overall_cable_width_mm"]<165
    assert 18<chosen["packed_envelope_height_including_cable_mm"]<20
    assert chosen["within_former_13p5mm_printed_only_limit"] is False
    assert chosen["old_reserved_cable_corridor_contains_route"] is False
    assert chosen["minimum_free_wire_self_separation_mm"]>1.10
    assert not chosen["physical_strain_relief_or_anchors_verified"]
    assert not chosen["physical_cable_connected"]

def test_finer_181_pose_route_has_same_selected_nominal_option():
    req,base=specimen()
    data=receipt()
    fine=data["selected_nominal_wire_fine_181_pose_sweep"]
    assert fine["selected_virtual_route"]=="roomy_bend_relief"
    assert all(not a.get("continuous_angle_clearance_certified",False)
               for a in [data["nominal_retainer_geometry"]])
    chosen=next(x for x in fine["route_candidates"] if x["id"]=="roomy_bend_relief")
    assert chosen["sample_count"]==181
    assert [x["angle_deg"] for x in chosen["poses"]]==list(range(181))
    assert chosen["nominal_virtual_route_feasible"]
    assert min(x["minimum_discrete_centerline_bend_radius_mm"]
               for x in chosen["poses"])>=2

def test_source_unauthorized_promotions_rejected():
    req,base=specimen()
    forged=copy.deepcopy(req)
    forged["authority"]["retainer_installation_tested"]=True
    with pytest.raises(ValueError,match="cannot claim"):
        checked_sources(forged,base)
    forged=copy.deepcopy(req)
    forged["pin_retention"]["groove_minor_diameter_mm"]=1.8
    with pytest.raises(ValueError,match="retainer geometry differs"):
        checked_sources(forged,base)
    forged=copy.deepcopy(req)
    forged["cable_route"]["actual_electrical_connectivity_verified"]=True
    with pytest.raises(ValueError,match="fabricated cable"):
        checked_sources(forged,base)

def test_reimport_real_six_part_hinge_wire_and_metal_reference_STEPS():
    pytest.importorskip("cadquery")
    from cadquery import importers
    for name in ("shaft","ring_left","ring_right"):
        original=importers.importStep(str(HERE/"generated"/(name+".step")))
        assert len(original.solids().vals())==1
        assert original.val().isValid()
    for phase in ("open_0","half_90","folded_180"):
        compound=importers.importStep(str(HERE/"generated"/("assembled_with_virtual_wire_"+phase+".step")))
        assert len(compound.solids().vals())==6
        tube=importers.importStep(str(HERE/"generated"/("cable_envelope_"+phase+".step")))
        assert len(tube.solids().vals())==1
        assert tube.val().Volume()>0

def test_full_native_reconstruction_against_committed_generated_sources():
    pytest.importorskip("cadquery")
    req,base=specimen()
    a=audit(req,base,out=HERE/"generated")
    assert a["actual_imported_reference_metal_solids"]==3
    assert a["actual_reimported_six_part_pose_STEPS"]==3
    assert a["actual_reimported_cable_tubes"]==3
    assert a["nominal_retainer_geometry"]["nominal_cad_checks_pass"] if "nominal_retainer_geometry" in a else a["retention_grooved_shaft_source_consistent"]
    assert a["original_reserved_space_fails_to_contain_route"]
    assert a["cable_anchored_to_verified_hardware"] is False
    assert a["physical_assembly_certified"] is False

def test_tampered_retainer_step_rejected(tmp_path):
    pytest.importorskip("cadquery")
    req,base=specimen()
    folder=tmp_path/"forged"
    shutil.copytree(HERE/"generated",folder)
    bad=folder/"ring_left.step"
    bad.write_bytes(bad.read_bytes()+b"tampered CAD")
    with pytest.raises(ValueError,match="altered"):
        audit(req,base,out=folder)

def test_thickness_source_and_cable_anchor_claims_remain_distinct():
    data=receipt()
    assert not any(data["authority"].values())
    assert "printed-only" in " ".join(data["validation_limitations"])
    assert data["wire_routing_sweep"]["routing_is_not_an_electrical_connection"]
    assert data["nominal_retainer_geometry"]["real_machined_pin_or_ring_available"] is False
    assert data["cable_sweep_and_six_solid_assembly"]["folded_180"]["virtual_cable_connected_to_actual_device"] is False
