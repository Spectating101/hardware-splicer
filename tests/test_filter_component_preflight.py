"""Physical-component screening is independent of actual water treatment."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

import pytest
from hardware_splicer.function_intent_bridge import package_intent
from hardware_splicer.function_technology_selection import compile_option_study
from hardware_splicer.filter_component_preflight import (
    package_parts,inspect_components,validate_sources,clearance_scad
)

ROOT=Path(__file__).resolve().parents[1]
BRIEF=ROOT/"examples/functionality/water_filter_nonpotable_bench_001.json"
OPTIONS=ROOT/"examples/functionality/water_filter_technology_options_001.json"
CANDIDATE=ROOT/"examples/functionality/water_filter_component_candidate_001.json"


def fixture(tmp):
    function=tmp/"function"
    study=tmp/"study"
    package_intent(json.loads(BRIEF.read_text()),function)
    compile_option_study(function,OPTIONS,study)
    return function,study,json.loads(CANDIDATE.read_text())


def test_real_manufacturer_pair_remains_bounded_and_not_a_filter_performance_claim(tmp_path):
    function,study,record=fixture(tmp_path)
    brief,decision,handoff=validate_sources(function,study,record)
    report=inspect_components(brief,record)
    assert report["manufacturer_reference_pair"]=={
        "cartridge_part_number":"155014-43","housing_part_number":"158007",
        "fit_status":"catalog_nominal_10in_pair_only"}
    assert report["published_housing_envelope_mm"]=={"diameter":118.0,"height":308.0}
    assert report["published_cartridge_envelope_mm"]=={"diameter":60.5,"height":251.0}
    assert report["intersection_of_published_temperature_ranges_c"]==[4.4,51.7]
    assert report["pressure_loss_at_target_flow_psi"] is None
    assert report["chosen_actual_operating_pressure_psi"] is None
    assert report["measured_treatment_reduction_percent"] is None
    assert not report["water_quality_claim_qualified"]
    assert not report["hydraulic_feasibility_validated"]
    assert not report["native_pressure_containing_part_generated"]
    assert len(report["blockers"])>=5
    assert "module housing_envelope()" in clearance_scad(report)
    assert "module service_clearance()" in clearance_scad(report)
    assert 'housing_d_mm = 118.000' in clearance_scad(report)


def test_nonphysical_package_has_real_source_digests_and_refuses_overwrite(tmp_path):
    function,study,_=fixture(tmp_path)
    p=tmp_path/"parts"
    r=package_parts(function,study,CANDIDATE,p)
    assert r["source_spec_sha256"]==json.loads(
        (function/"PACKAGE_RECEIPT.json").read_text())["source_spec_sha256"]
    assert r["technology_options_sha256"]==json.loads(
        (study/"TECHNOLOGY_STUDY_RECEIPT.json").read_text())["technology_options_sha256"]
    assert len(json.loads((p/"COMPONENT_BOM.json").read_text())["items"])==2
    assert json.loads((p/"COMPONENT_BOM.json").read_text())["full_bom"] is False
    for name,meta in r["files"].items():
        body=(p/name).read_bytes()
        assert meta["sha256"]==hashlib.sha256(body).hexdigest()
        assert meta["bytes"]==len(body)
    assert all(v is False for v in (
        r["actual_treatment_test_executed"],r["fabrication_authorized"],
        r["water_activation_authorized"]))
    with pytest.raises(ValueError,match="replace previous"):
        package_parts(function,study,CANDIDATE,p)


@pytest.mark.parametrize("field,value",[
    ("cartridge.part_number","155015-43"),
    ("housing.part_number","158110"),
    ("cartridge.outer_diameter_mm",62.0),
    ("housing.overall_max_length_mm",298),
    ("housing.maximum_housing_pressure_psi",200),
    ("housing.inlet_outlet_connection","1/2in_NPT"),
    ("cartridge.published_clean_pressure_point.flow_us_gpm",0.5),
])
def test_changed_part_or_published_reference_data_must_be_reviewed(tmp_path,field,value):
    function,study,record=fixture(tmp_path)
    item=record
    keys=field.split(".")
    for key in keys[:-1]: item=item[key]
    item[keys[-1]]=value
    brief,_,_=validate_sources(function,study,record)
    with pytest.raises(ValueError):
        inspect_components(brief,record)


def test_assumed_turbidity_removal_cannot_be_promoted_to_measurement(tmp_path):
    function,study,record=fixture(tmp_path)
    record["design_assumptions"]["turbidity_reduction_observed_percent"]=75
    brief,_,_=validate_sources(function,study,record)
    with pytest.raises(ValueError,match="unverified operating conditions"):
        inspect_components(brief,record)


def test_unsupported_low_flow_hydraulic_curve_or_mounting_claim_blocked(tmp_path):
    function,study,record=fixture(tmp_path)
    record["design_assumptions"]["actual_pressure_curve_at_proposed_flow_available"]=True
    brief,_,_=validate_sources(function,study,record)
    with pytest.raises(ValueError,match="unsupported mechanical or hydraulic"):
        inspect_components(brief,record)
    record["design_assumptions"]["actual_pressure_curve_at_proposed_flow_available"]=False
    record["design_assumptions"]["mounting_boss_positions_known"]=True
    with pytest.raises(ValueError,match="unsupported mechanical or hydraulic"):
        inspect_components(brief,record)


def test_functional_source_tampering_and_wrong_selected_technology_fail(tmp_path):
    function,study,record=fixture(tmp_path)
    options=study/"TECHNOLOGY_DECISION.json"
    original=json.loads(options.read_text())
    original["provisional_preferred_candidate_id"]="active_membrane_cartridge"
    options.write_text(json.dumps(original))
    with pytest.raises(ValueError,match="source technology artifact changed"):
        validate_sources(function,study,record)
    options.write_bytes((study/"TECHNOLOGY_DECISION.json").read_bytes()) # no-op as a reminder
    (function/"FUNCTIONAL_INPUT.json").write_text("{}")
    with pytest.raises(ValueError,match="source artifact changed"):
        validate_sources(function,study,record)


def test_no_manufacturer_document_pdf_hash_or_supplier_price_may_be_invented(tmp_path):
    function,study,record=fixture(tmp_path)
    record["cartridge"]["source"]["document_sha256"]="0"*64
    brief,_,_=validate_sources(function,study,record)
    with pytest.raises(ValueError,match="manufacturer documentary evidence"):
        inspect_components(brief,record)
    record["cartridge"]["source"]["document_sha256"]=None
    record["provenance"]["supplier_stock_and_price_checked"]=True
    with pytest.raises(ValueError,match="misrepresented as physical qualification"):
        inspect_components(brief,record)


def test_service_clearance_remains_explicit_unverified_assumption(tmp_path):
    function,study,record=fixture(tmp_path)
    record["design_assumptions"]["service_removal_clearance_mm"]=0
    brief,_,_=validate_sources(function,study,record)
    with pytest.raises(ValueError,match="unqualified cartridge service"):
        inspect_components(brief,record)
