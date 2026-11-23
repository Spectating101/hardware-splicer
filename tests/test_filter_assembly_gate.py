"""Adversarial contract tests; synthetic STLs exercise evidence-validator only.

True OpenSCAD geometry is rendered and checked in the upstream CI job. Tests
here intentionally use fabricated *fixture bytes*, never as engineering proof.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.function_intent_bridge import package_intent, canonical
from hardware_splicer.function_technology_selection import compile_option_study
from hardware_splicer.filter_component_preflight import package_parts
from hardware_splicer.filter_assembly_gate import verify_assembly,package_assembly

ROOT=Path(__file__).resolve().parents[1]
EX=ROOT/"examples/functionality"


def setup(tmp_path):
    fn=tmp_path/"fn"
    tech=tmp_path/"tech"
    parts=tmp_path/"parts"
    package_intent(json.loads((EX/"water_filter_nonpotable_bench_001.json").read_text()),fn)
    compile_option_study(fn,EX/"water_filter_technology_options_001.json",tech)
    package_parts(fn,tech,EX/"water_filter_component_candidate_001.json",parts)
    receipt=json.loads((parts/"COMPONENT_PACKAGE_RECEIPT.json").read_text())
    # Only our *unit* fixture uses placeholder data in place of a native STL.
    solids={}
    for id_, dims, bounds in [
        ("housing",[118.0,118.0,308.0],[0.0,308.0]),
        ("service",[118.0,118.0,150.0],[-150.0,0.0]),
    ]:
        name="clearance_"+id_+".stl"
        blob=("synthetic-test-fixture-"+id_).encode()
        (parts/name).write_bytes(blob)
        solids[id_]={
            "stl_filename":name,
            "sha256":hashlib.sha256(blob).hexdigest(),
            "bytes":len(blob),
            "dimensions_mm":dims,"z_bounds_mm":bounds,
            "watertight":True,"winding_consistent":True,
        }
    native={
      "schema_version":"hardware_splicer.filter_clearance_native_cad_evidence.v1",
      "source_spec_sha256":receipt["source_spec_sha256"],
      "component_reference_sha256":receipt["component_reference_sha256"],
      "renderer":"OpenSCAD CLI",
      "catalog_envelope_dimensions_verified_in_rendered_mesh":True,
      "cad_source_sha256":hashlib.sha256((parts/"clearance.scad").read_bytes()).hexdigest(),
      "solids":solids,
      "physical_fit_verified":False,"installation_clearance_verified":False,
      "pressure_containing_design_generated":False,"manufacturing_authorized":False,
      "water_activation_authorized":False,"human_consumption_authorized":False,
    }
    (parts/"RENDERED_CLEARANCE_EVIDENCE.json").write_bytes(canonical(native))
    return parts,json.loads((EX/"water_filter_assembly_interfaces_001.json").read_text())


def test_interface_graph_yields_all_seven_uncollected_measurement_gates(tmp_path):
    parts,source=setup(tmp_path)
    report,requests=verify_assembly(parts,source)
    assert report["actual_native_clearance_meshes_checked"]
    assert report["outcome"]=="ASSEMBLY_DESIGN_BLOCKED_PENDING_EVIDENCE"
    assert len(report["interface_evidence_gates"])==6
    assert len(report["accessory_candidates"])==3
    assert report["service_clearance"]["illustrative_vertical_allocation_mm"]==458
    assert report["service_clearance"]["manufacturer_minimum_verified_mm"] is None
    assert report["hydraulic_pressure_at_target_flow_psi"] is None
    assert report["sku_specific_certification_verified"] is False
    assert not any(report["physical_authority"].values())
    assert len(requests["evidence_requests"])==7
    assert all(r["status"]=="AWAITING_INDEPENDENT_EVIDENCE" and r["measured_value"] is None
               for r in requests["evidence_requests"])
    assert not requests["fabrication_authorized"]
    assert not requests["pressurized_testing_authorized"]


def test_full_receipt_contains_provenance_and_refuses_overwrite(tmp_path):
    parts,source=setup(tmp_path)
    p=tmp_path/"handoff"
    src=tmp_path/"assembly.json"
    src.write_bytes(canonical(source))
    receipt=package_assembly(parts,src,p)
    assert receipt["source_spec_sha256"]==json.loads(
        (parts/"COMPONENT_PACKAGE_RECEIPT.json").read_text())["source_spec_sha256"]
    for name,item in receipt["files"].items():
        blob=(p/name).read_bytes()
        assert len(blob)==item["bytes"] and hashlib.sha256(blob).hexdigest()==item["sha256"]
    assert receipt["fabrication_authorized"] is False
    with pytest.raises(ValueError,match="overwrite"):
        package_assembly(parts,src,p)


@pytest.mark.parametrize("field,new_value,expected_error",[
    ("BRACKET_CANDIDATE.sku_specific_fit_confirmed",True,"fabricated accessory fit"),
    ("BRACKET_CANDIDATE.drill_template_verified",True,"fabricated accessory fit"),
    ("ORING_CANDIDATE.seal_groove_measured",True,"fabricated accessory fit"),
    ("WRENCH_CANDIDATE.required_swing_clearance_measured",True,"fabricated accessory fit"),
    ("WRENCH_CANDIDATE.part_number","WRONG","wrong manufacturer accessory"),
])
def test_accessory_cannot_be_marked_fitted_from_family_listing(tmp_path,field,new_value,expected_error):
    parts,source=setup(tmp_path)
    id_,prop=field.split(".")
    next(a for a in source["accessories"] if a["id"]==id_)[prop]=new_value
    with pytest.raises(ValueError,match=expected_error):
        verify_assembly(parts,source)


def test_unmeasured_service_clearance_and_undocumented_boss_pitch_fail(tmp_path):
    parts,source=setup(tmp_path)
    source["service_envelope"]["manufacturer_sku_specific_minimum_below_clearance_mm"]=150
    with pytest.raises(ValueError,match="illustrative clearance promoted"):
        verify_assembly(parts,source)
    parts,source=setup(tmp_path/"next")
    source["service_envelope"]["housing_boss_pitch_mm"]=48
    with pytest.raises(ValueError,match="illustrative clearance promoted"):
        verify_assembly(parts,source)


def test_pressure_curve_cannot_be_fabricated_from_reference_point(tmp_path):
    parts,source=setup(tmp_path)
    source["hydraulics"]["actual_design_flow_pressure_drop_psi"]=0.08
    with pytest.raises(ValueError,match="hydraulic design conditions"):
        verify_assembly(parts,source)


def test_selecting_certification_not_covered_by_reviewed_sku_list_is_rejected(tmp_path):
    parts,source=setup(tmp_path)
    source["certification_review"]["certification_for_selected_housing_currently_verified"]=True
    with pytest.raises(ValueError,match="certification"):
        verify_assembly(parts,source)


def test_upstream_native_mesh_tamper_fails_even_when_shapes_look_documented(tmp_path):
    parts,source=setup(tmp_path)
    (parts/"clearance_housing.stl").write_bytes(b"modified mesh")
    with pytest.raises(ValueError,match="upstream source/evidence artifact altered"):
        verify_assembly(parts,source)


def test_source_project_and_port_identity_tamper_rejected(tmp_path):
    parts,source=setup(tmp_path)
    source["reference_parts"]["housing"]="158195"
    with pytest.raises(ValueError,match="wrong assembly source"):
        verify_assembly(parts,source)
    parts,source=setup(tmp_path/"next")
    source["interfaces"][2]["to"]="SOME_OTHER_FITTING"
    with pytest.raises(ValueError,match="mismatched physical interface"):
        verify_assembly(parts,source)


def test_forged_real_wet_test_or_mounting_permission_rejected(tmp_path):
    parts,source=setup(tmp_path)
    source["hydraulics"]["actual_wet_test_executed"]=True
    with pytest.raises(ValueError,match="hydraulic design conditions"):
        verify_assembly(parts,source)
    parts,source=setup(tmp_path/"next")
    source["physical_authority"]["drill"]=True
    with pytest.raises(ValueError,match="physical authorization"):
        verify_assembly(parts,source)


def test_missing_instrument_calibration_request_rejected(tmp_path):
    parts,source=setup(tmp_path)
    source["required_evidence_roles"]=[
       x for x in source["required_evidence_roles"] if x["id"]!="E_HYDRAULIC"]
    with pytest.raises(ValueError,match="real measurements or certification evidence"):
        verify_assembly(parts,source)
