"""Source-bound physical-component feasibility for non-potable water study.

Catalog values transcribed from identified manufacturer product publications;
documentation is not pinned as PDF bytes and actual revisions are not checked
on parts. Only external *clearance volumes* are created in OpenSCAD. No wetted
or load-bearing/pressure-containing geometry is fabricated or designed here.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .function_intent_bridge import canonical
from .function_technology_selection import read_bound_function_package

SCHEMA="hardware_splicer.nonpotable_filter_component_reference.v1"
DESIGN_SCHEMA="hardware_splicer.nonpotable_filter_component_preflight.v1"


def sha(blob:bytes)->str:
    return hashlib.sha256(blob).hexdigest()


def require(condition:bool,reason:str)->None:
    if not condition:
        raise ValueError("Filter component study refused: "+reason)


def _read_file(directory:Path,name:str)->dict:
    obj=json.loads((directory/name).read_text())
    require(isinstance(obj,dict),"missing structured "+name)
    return obj


def validate_sources(function_package:Path, study_package:Path, components:Mapping[str,Any])->tuple[dict,dict,dict]:
    brief,machine,gate,work=read_bound_function_package(function_package)
    receipt=_read_file(study_package,"TECHNOLOGY_STUDY_RECEIPT.json")
    require(receipt.get("schema_version")=="hardware_splicer.technology_study_receipt.v1",
            "missing technology study receipt")
    for name,meta in receipt.get("files",{}).items():
        p=Path(study_package)/name
        require(p.is_file(),"missing source technology file "+name)
        blob=p.read_bytes()
        require(meta.get("sha256")==sha(blob) and meta.get("bytes")==len(blob),
                "source technology artifact changed: "+name)
    decision=_read_file(study_package,"TECHNOLOGY_DECISION.json")
    handoff=_read_file(study_package,"PROVISIONAL_ARCHITECTURE_HANDOFF.json")
    require(decision.get("schema_version")=="hardware_splicer.technology_study_decision.v1",
            "technology decision schema mismatch")
    require(decision.get("source_spec_sha256")==gate["source_spec_sha256"]==
            handoff.get("source_spec_sha256")==receipt.get("source_spec_sha256"),
            "function source or technology study revision mismatch")
    options=_read_file(study_package,"TECHNOLOGY_OPTIONS.json")
    require(sha(canonical(options))==decision.get("technology_options_sha256")==
            handoff.get("technology_options_sha256")==receipt.get("technology_options_sha256"),
            "option study source mismatch")
    require(decision.get("selection_state")=="PROVISIONAL_FOR_DESIGN_STUDY_ONLY"
            and decision.get("provisional_preferred_candidate_id")=="passive_replaceable_depth_media"
            and handoff.get("preferred_study_candidate_id")=="passive_replaceable_depth_media",
            "reference part candidate does not match chosen study mechanism")
    require(len(handoff.get("discipline_assignments",[]))==5 and
            handoff.get("physical_authority_granted") is False,
            "incorrect engineering handoff or physical authorization")
    require(components.get("schema_version")==SCHEMA and
            components.get("project_id")==brief["project_id"] and
            components.get("technology_candidate_id")=="passive_replaceable_depth_media",
            "unknown product selection identity")
    require(components.get("reference_use")=="non_potable_laboratory_concept_only"
            and components.get("component_pair_status")==
                "manufacturer_documented_product_family_candidate_not_measured_fit",
            "component pair falsely designated fitted/certified")
    return brief,decision,handoff


def _exact_numeric(part:Mapping[str,Any],name:str,value:float)->None:
    v=part.get(name)
    require(type(v) in (int,float) and math.isfinite(v) and
            math.isclose(v,value,rel_tol=0,abs_tol=0.00001),
            "reviewed manufacturer datum changed: "+name)


def inspect_components(brief:Mapping[str,Any],components:Mapping[str,Any])->dict[str,Any]:
    cartridge=components["cartridge"]
    housing=components["housing"]
    a=components["design_assumptions"]
    prov=components["provenance"]
    require(cartridge.get("manufacturer")=="Pentair" and cartridge.get("brand")=="Pentek"
            and cartridge.get("part_number")=="155014-43" and cartridge.get("model")=="P5",
            "wrong 10-inch media part")
    require(housing.get("manufacturer")=="Pentair" and housing.get("brand")=="Pentek"
            and housing.get("part_number")=="158007",
            "wrong reviewed 10-inch housing")
    require(cartridge.get("format")=="nominal_10in_DOE_standard_sediment_cartridge"
            and housing.get("format")=="nominal_10in_DOE_standard_filter_housing",
            "form factors not a documented candidate match")
    for part,values in (
        (cartridge,{"outer_diameter_mm":60.5,"length_mm":251.0,
                    "nominal_micron_rating":5.0,"temperature_min_c":4.4,
                    "temperature_max_c":62.8}),
        (housing,{"overall_max_diameter_mm":118.0,"overall_max_length_mm":308.0,
                  "maximum_housing_pressure_psi":125.0,
                  "temperature_min_c":4.4,"temperature_max_c":51.7}),
    ):
        for name,value in values.items():
            _exact_numeric(part,name,value)
    require(housing.get("inlet_outlet_connection")=="3/8in_NPT"
            and housing.get("pressure_relief_present") is True,
            "housing connection or relief revision differs")
    require(cartridge.get("filter_medium")=="spun_bonded_polypropylene"
            and housing.get("sump_material")=="styrene_acrylonitrile_SAN_clear"
            and housing.get("oring_material")=="EPDM",
            "unsupported material/revision claims")
    for part,delta in ((cartridge,0.2),(housing,2.0)):
        point=part["published_clean_pressure_point"]
        _exact_numeric(point,"flow_us_gpm",5.0)
        _exact_numeric(point,"delta_p_psi",delta)
        citation=part["source"]
        require(citation.get("publisher")=="Pentair"
                and citation.get("page")==2 and citation.get("document_sha256") is None
                and citation.get("independent_part_authentication") is False
                and citation.get("url","").startswith("https://www.pentair.com/")
                and bool(citation.get("revision")),
                "manufacturer documentary evidence missing or spuriously pinned")
    require(a.get("mounting_boss_positions_known") is False
            and a.get("media_cartridge_housing_fit_physically_checked") is False
            and a.get("rated_connectors_and_hoses_selected") is False
            and a.get("actual_pressure_curve_at_proposed_flow_available") is False
            and a.get("effective_pore_distribution_verified") is False,
            "unsupported mechanical or hydraulic physical evidence")
    require(a.get("inlet_feed_pressure_psi") is None and
            a.get("temperature_operating_c") is None and
            a.get("raw_test_water_particles") is None and
            a.get("turbidity_reduction_observed_percent") is None,
            "input has unverified operating conditions or water-quality result")
    clearance=a.get("service_removal_clearance_mm")
    require(type(clearance) in (int,float) and math.isfinite(clearance) and
            80 <= clearance <= 350
            and a.get("service_clearance_basis")==
                "illustrative_external_access_allocation_not_vendor_instruction_or_measured_sump_removal",
            "unqualified cartridge service area dimension")
    target=next(r for r in brief["requirements"] if r["id"]=="REQ_FLOW")
    target_lpm=target["target"]["minimum_flow_l_min"]
    require(target_lpm==a.get("proposed_flow_l_min")==0.5,
            "function flow demand changed relative to vendor selected parts")
    particle=next(r for r in brief["requirements"] if r["id"]=="REQ_PARTICLE")
    require(particle["target"]["minimum_turbidity_reduction_percent"]==70,
            "particle challenge changed, review candidate again")
    require(prov.get("claims_transcribed_from_manufacturer_publications") is True
            and prov.get("manufacturer_documents_cryptographically_snapshotted") is False
            and prov.get("product_revision_on_purchased_part_measured") is False
            and prov.get("supplier_stock_and_price_checked") is False,
            "component sources misrepresented as physical qualification")
    require(all(v is False for v in components.get("authority",{}).values())
            and len(components.get("authority",{}))==5,
            "physical actions or drinking water unexpectedly authorized")
    # Manufacturer gives a single high-flow reference point for each part:
    # NO extrapolation, curve fitting, pressure head estimate or treatment claim.
    return {
        "schema_version":DESIGN_SCHEMA,
        "project_id":brief["project_id"],
        "manufacturer_reference_pair":{"cartridge_part_number":"155014-43",
            "housing_part_number":"158007","fit_status":"catalog_nominal_10in_pair_only"},
        "published_cartridge_envelope_mm":{
            "diameter":60.5,"height":251.0},
        "published_housing_envelope_mm":{
            "diameter":118.0,"height":308.0},
        "conceptual_service_corridor_mm":{
            "diameter":118.0,"height":float(clearance),
            "source":"illustrative_project_assumption_not_factory_installation_clearance"},
        "published_reference_pressure_drops_at_five_us_gpm_psi":{
            "housing_only":2.0,"cartridge_only":0.2},
        "pressure_loss_at_target_flow_psi":None,
        "target_flow_l_min":0.5,
        "treatment_reduction_target_percent":70,
        "measured_treatment_reduction_percent":None,
        "intersection_of_published_temperature_ranges_c":[4.4,51.7],
        "housing_max_rated_pressure_psi":125.0,
        "chosen_actual_operating_pressure_psi":None,
        "temperature_of_actual_bench_test_c":None,
        "candidate_interface":"3/8in_NPT",
        "physical_cartridge_to_housing_fit_validated":False,
        "mounting_boss_pitch_verified":False,
        "hydraulic_feasibility_validated":False,
        "pressure_activation_authorized":False,
        "human_consumption_authorized":False,
        "water_quality_claim_qualified":False,
        "native_pressure_containing_part_generated":False,
        "manufacturer_source_documents_snapshotted":False,
        "part_source_urls":[cartridge["source"]["url"],housing["source"]["url"]],
        "blockers":[
            "Housing internal bore and end-cap cartridge seating dimensions not published in selected evidence",
            "Nominal 5-micron classification is not 70-percent turbidity reduction under specified raw water",
            "No low-flow differential-pressure curve, feed head or fouled media performance",
            "Manufacturer maximum housing pressure is not selected operating or test pressure",
            "Inlet/outlet hoses, 3/8in NPT adapters, pressure taps and sealing fittings unselected",
            "No authentic purchased-part inspection, pressure-hold leak test or media replacement proof",
            "Manufacturer PDFs identified by URL/revision but original bytes not frozen in receipt",
        ],
    }


def clearance_scad(report:Mapping[str,Any])->str:
    d=report["published_housing_envelope_mm"]["diameter"]
    h=report["published_housing_envelope_mm"]["height"]
    corridor=report["conceptual_service_corridor_mm"]["height"]
    return (
        "// REFERENCE CLEARANCE VOLUMES ONLY. NOT WETTED, PRINTABLE OR PRESSURE-RATED.\n"
        "// Cylindrical overbound of actual housing, not manufacturer's 3D CAD.\n"
        "// No threaded port, bracket hole or boss pitch is represented.\n"
        "$fn = 160;\n"
        f"housing_d_mm = {d:.3f};\n"
        f"housing_h_mm = {h:.3f};\n"
        f"service_h_mm = {corridor:.3f};\n"
        "part = \"housing\";\n"
        "module housing_envelope() { cylinder(d=housing_d_mm,h=housing_h_mm,center=false); }\n"
        "module service_clearance() { translate([0,0,-service_h_mm]) "
        "cylinder(d=housing_d_mm,h=service_h_mm,center=false); }\n"
        "if(part == \"housing\") housing_envelope();\n"
        "else if(part == \"service\") service_clearance();\n"
        "else assert(false, \"unsupported non-physical geometry component\");\n"
    )


def package_parts(function_root:Path,study_root:Path,components_path:Path,out:Path)->dict:
    candidate_raw=Path(components_path).read_bytes()
    candidate=json.loads(candidate_raw)
    brief,decision,handoff=validate_sources(function_root,study_root,candidate)
    report=inspect_components(brief,candidate)
    report["source_spec_sha256"]=decision["source_spec_sha256"]
    report["technology_options_sha256"]=decision["technology_options_sha256"]
    report["component_reference_sha256"]=sha(canonical(candidate))
    report["technology_study_receipt_sha256"]=sha(
        (Path(study_root)/"TECHNOLOGY_STUDY_RECEIPT.json").read_bytes())
    out=Path(out)
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())),
            "refusing to replace previous component evidence")
    out.mkdir(parents=True,exist_ok=True)
    inventory={
        "schema_version":"hardware_splicer.nonpotable_component_bom.v1",
        "source_spec_sha256":report["source_spec_sha256"],
        "source_component_reference_sha256":report["component_reference_sha256"],
        "items":[
            {"reference":"MEDIA-1","part_number":candidate["cartridge"]["part_number"],
             "manufacturer":"Pentair","quantity":1,"source_url":candidate["cartridge"]["source"]["url"],
             "procurement_status":"NOT_PURCHASED_OR_INDEPENDENTLY_QUALIFIED"},
            {"reference":"HOUSING-1","part_number":candidate["housing"]["part_number"],
             "manufacturer":"Pentair","quantity":1,"source_url":candidate["housing"]["source"]["url"],
             "procurement_status":"NOT_PURCHASED_OR_INDEPENDENTLY_QUALIFIED"},
        ],
        "missing_components":["rated_tubing","NPT_fittings","pressure_instruments","bench_flow_instrument",
                              "turbidity_challenge_and_reference","service_bracket_with_verified_boss_spacing"],
        "full_bom":False,"purchase_authorized":False,"fabrication_authorized":False,
    }
    outputs={
        "COMPONENT_REFERENCE.json":canonical(candidate),
        "COMPONENT_PREFLIGHT.json":canonical(report),
        "COMPONENT_BOM.json":canonical(inventory),
        "clearance.scad":clearance_scad(report).encode(),
    }
    for name,blob in outputs.items():
        (out/name).write_bytes(blob)
    receipt={
        "schema_version":"hardware_splicer.filter_component_package_receipt.v1",
        "source_spec_sha256":report["source_spec_sha256"],
        "technology_options_sha256":report["technology_options_sha256"],
        "component_reference_sha256":report["component_reference_sha256"],
        "files":{name:{"sha256":sha(blob),"bytes":len(blob)}
                 for name,blob in sorted(outputs.items())},
        "actual_treatment_test_executed":False,
        "fabrication_authorized":False,
        "water_activation_authorized":False,
    }
    (out/"COMPONENT_PACKAGE_RECEIPT.json").write_bytes(canonical(receipt))
    return receipt
