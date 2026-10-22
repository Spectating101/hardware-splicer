"""Hybrid sheet/print construction proposals through the actual HS Mecha path."""

from __future__ import annotations

import json
import math

import pytest

from hardware_splicer.construction_alternatives import (
    CONNECTOR_SOURCES, evaluate_construction_alternatives, render_construction_plan,
    summarize_fabrication_benchmark,
    verify_git_blob_asset, inspect_local_connector_assets,
)


def _project():
    return {
        "project_name": "low-waste-sensor-box",
        "enclosure": {
            "inner_w_mm": 100, "inner_d_mm": 80, "inner_h_mm": 30,
            "wall_mm": 2, "floor_mm": 2, "lid_mm": 2,
        },
        "construction": {
            "preference": "auto",
            "operating_temp_c": 35,
            "chemical_exposures": ["humidity"],
            "panel_thickness_mm": 3,
            "connector_family": "moduframe",
            "connector_count": 4,
            "connector_print_volume_cm3": .6,
            "filament_material": {
                "material_id": "supplied-petg",
                "evidence_kind": "datasheet",
                "source_uri": "https://example.com/real-measurement-replaced-by-user",
                "density_kg_m3": 1250,
                "max_service_temp_c": 65,
                "cost_per_kg": 25,
                "chemical_compatibility": {"humidity": "compatible"},
            },
            "panel_material": {
                "material_id": "supplier-plywood",
                "evidence_kind": "datasheet",
                "source_uri": "https://example.com/real-measurement-replaced-by-user",
                "density_kg_m3": 550,
                "max_service_temp_c": 50,
                "cost_per_m2": 12,
                "chemical_compatibility": {"humidity": "unknown"},
            },
        },
    }


def _hybrid(result):
    return next(row for row in result["alternatives"]
                if row["method"] == "sheet_hybrid")


def test_no_implicit_construction_substitution():
    r=evaluate_construction_alternatives({"enclosure": _project()["enclosure"]})
    assert r["status"] == "not_requested"
    assert r["fabrication_authorized"] is False


def test_sourced_material_mass_cost_geometry_and_thermochemistry():
    result=evaluate_construction_alternatives(_project())
    assert result["status"] == "comparison_produced_research_only"
    assert result["enclosure_outer_dimensions_mm"] == [104,84,34]
    assert result["selected_manufacturing_method"] is None
    assert len(result["alternatives"]) == 3
    full=result["alternatives"][0]
    hybrid=_hybrid(result)
    assert full["estimated_solid_envelope_mm3"] == pytest.approx(57024)
    assert full["estimated_printed_mass_g"] == pytest.approx(71.28)
    assert hybrid["panel_area_mm2_unoptimized"] == pytest.approx(30256)
    assert hybrid["panel_mass_g"] == pytest.approx(49.9224,abs=.001)
    assert hybrid["connector_printed_mass_g"] == pytest.approx(3)
    assert hybrid["combined_estimated_mass_g"] == pytest.approx(52.922,abs=.002)
    assert result["hypothetical_full_print_minus_hybrid_mass_g"] == pytest.approx(18.358,abs=.002)
    assert result["hypothetical_material_cost_difference"] is not None
    assert result["thermal_screen"]["panel"] == "below_reported_limit_not_validated"
    assert result["material_property_evidence"]["panel"]["density_kg_m3"] == 550
    assert result["material_property_evidence"]["panel"]["conductivity_used_in_thermal_solver"] is False
    assert result["material_property_evidence"]["panel"]["modulus_used_in_assembly_stress_solver"] is False
    assert result["chemical_screen"]["panel"] == {"humidity":"unknown"}
    assert "chemical_compatibility_unverified" in hybrid["blockers"]
    assert "external_connector_revision_unpinned" in hybrid["blockers"]
    assert hybrid["connector_source"]["local_asset_validated"] is False
    assert result["full_enclosure_thermal_simulation_performed"] is False
    assert result["structural_safety_verified"] is False
    assert result["release_authorized"] is False


def test_heat_limit_and_solvent_incompatibility_block_hybrid():
    project=_project()
    project["construction"]["operating_temp_c"] = 80
    project["construction"]["chemical_exposures"] = ["acetone"]
    project["construction"]["panel_material"]["chemical_compatibility"] = {
        "acetone": "incompatible"
    }
    report=evaluate_construction_alternatives(project)
    assert report["thermal_screen"]["panel"]=="above_reported_service_limit"
    assert report["thermal_screen"]["filament"]=="above_reported_service_limit"
    b=_hybrid(report)["blockers"]
    assert "panel_temperature_limit_exceeded" in b
    assert "filament_temperature_limit_exceeded" in b
    assert "panel_chemical_incompatibility" in b
    assert report["selected_manufacturing_method"] is None


def test_connector_nominal_size_mismatch_rejected():
    project=_project()
    project["construction"]["connector_family"]="clip_os"
    r=evaluate_construction_alternatives(project)
    assert "connector_nominal_thickness_mismatch" in _hybrid(r)["blockers"]
    assert r["selected_manufacturing_method"] is None


def test_missing_properties_do_not_create_imaginary_savings():
    project=_project()
    project["construction"]["filament_material"] = None
    project["construction"]["panel_material"] = None
    project["construction"]["connector_print_volume_cm3"] = None
    r=evaluate_construction_alternatives(project)
    assert r["hypothetical_full_print_minus_hybrid_mass_g"] is None
    assert r["hypothetical_material_cost_difference"] is None
    assert r["economic_preference"] == "cost_comparison_unavailable"
    assert "sheet_material_or_measured_thickness_missing" in _hybrid(r)["blockers"]


def test_external_sources_are_catalog_only_not_downloaded():
    assert {"clip_os","moduframe","bosl2","boxes_py"} <= set(CONNECTOR_SOURCES)
    r=evaluate_construction_alternatives(_project())
    assert r["selected_manufacturing_method"] is None
    h=_hybrid(r)
    assert h["connector_source"]["requires_external_asset"] is True
    assert h["connector_source"]["revision_pinned"] is False
    text=render_construction_plan(r)
    assert "No manufacturing method has been auto-selected" in text
    assert "ModuFrame" in text
    assert "Preliminary panel cut rectangles" in text
    assert "thermal" in text.lower() or "temperature" in text.lower()


@pytest.mark.parametrize("key,value", [
    ("panel_thickness_mm",-1),
    ("connector_count",-1),
    ("connector_print_volume_cm3",-1),
    ("printed_material_fraction",1.2),
    ("operating_temp_c",math.inf),
    ("connector_family","invented"),
])
def test_invalid_input_is_rejected(key,value):
    p=_project()
    p["construction"][key]=value
    with pytest.raises(ValueError):
        evaluate_construction_alternatives(p)


def test_unscoped_geometry_does_not_get_fake_cut_plan():
    p=_project()
    p.pop("enclosure")
    r=evaluate_construction_alternatives(p)
    assert r["status"]=="unsupported_non_enclosure"
    assert r["alternatives"] == []


def test_mecha_runner_integrates_risk_recipe_and_keeps_original_cad(tmp_path):
    from hardware_splicer.mechanism_bridge import _ensure_mecha_on_path
    if not _ensure_mecha_on_path():
        pytest.skip("Mecha-Splicer is not installed in this CI environment")
    from mecha_splicer.runner import run
    bundle=run(_project(),out_dir=tmp_path)
    assert bundle["construction_alternatives"]["status"] == "comparison_produced_research_only"
    assert bundle["structural_screening"]["status"]=="unsupported_mechanical_topology"
    assert (tmp_path/"enclosure.scad").exists()
    assert not (tmp_path/"panel_connector.scad").exists()
    assert (tmp_path/"CONSTRUCTION_ALTERNATIVES.json").exists()
    assert (tmp_path/"CONSTRUCTION_PLAN.md").exists()
    assert "ModuFrame" in (tmp_path/"CONSTRUCTION_PLAN.md").read_text()
    assert "chemical_compatibility_unverified" in (tmp_path/"RISK_REGISTER.md").read_text()
    assert "CONSTRUCTION_PLAN.md" in (tmp_path/"BUILD_RECIPE.md").read_text()
    assert "Construction alternatives" in (tmp_path/"MECH_CHECK.md").read_text() or (
        "Construction and Material Alternatives" in (tmp_path/"MECH_CHECK.md").read_text()
    )
    saved=json.loads((tmp_path/"mecha_splicer.bundle.json").read_text())
    assert saved["construction_alternatives"]["selected_manufacturing_method"] is None
    sim=json.loads((tmp_path/"SIM_RESULTS.json").read_text())
    assert sim["construction_alternatives"]["fabrication_authorized"] is False
    assert bundle["construction_alternatives"]["release_authorized"] is False


def test_typed_construction_spec_rejects_negative_geometry():
    from hardware_splicer.mechanism_bridge import _ensure_mecha_on_path
    if not _ensure_mecha_on_path():
        pytest.skip("Mecha-Splicer unavailable")
    from mecha_splicer.spec import ProjectSpec
    with pytest.raises(ValueError):
        ProjectSpec.model_validate({
            **_project(),
            "construction": {
                **_project()["construction"],
                "panel_thickness_mm": -2,
            },
        })


def test_hs_mechanism_pack_propagates_requested_construction(tmp_path):
    from hardware_splicer.mechanism_bridge import run_mechanism_pack
    record = run_mechanism_pack(
        project_name="salvaged-sensor",
        build_id="sensor_logger",
        out_dir=tmp_path,
        construction=_project()["construction"],
    )
    assert record["status"] == "ok"
    assert record["project_spec"]["construction"]["connector_family"] == "moduframe"
    construction = record["construction_alternatives"]
    assert construction["status"] == "comparison_produced_research_only"
    assert construction["selected_manufacturing_method"] is None
    assert construction["release_authorized"] is False
    assert (tmp_path/"mecha_bundle"/"CONSTRUCTION_PLAN.md").exists()


def test_pinned_real_clip_os_assets_reference_actual_git_blobs():
    p = _project()
    p["construction"]["connector_family"] = "clip_os"
    p["construction"]["panel_thickness_mm"] = 1.6
    report = evaluate_construction_alternatives(p)
    hybrid = _hybrid(report)
    connector = hybrid["connector_source"]
    assert connector["revision_pinned"] is True
    assert connector["local_asset_validated"] is False
    assert connector["pinned_revision"] == "348bad8ba0553be79f24d5ac12a7d4081d7759c8"
    assert {x["git_blob_sha1"] for x in connector["verified_repository_assets"]} == {
        "eda0c9041d229c050296a313af5e4bd1a07892ea",
        "fab8122d82c96237fa819429a50dc2cbcc99291f",
    }
    assert "external_connector_revision_unpinned" not in hybrid["blockers"]
    assert "connector_files_not_validated_or_installed" in hybrid["blockers"]
    assert connector["recommended_hole_center_from_edge_mm"] == 12.7
    assert "Pinned Git revision" in render_construction_plan(report)


def _trial(method, cost, mass, kind="synthetic_fixture"):
    return {
        "specimen_id": "fixture-" + method,
        "method": method,
        "record_uri": "fixture://" + method,
        "evidence_kind": kind,
        "finished_mass_g": mass,
        "printing_minutes": 25 if method != "off_the_shelf" else 0,
        "cutting_minutes": 12 if method == "sheet_hybrid" else 0,
        "assembly_minutes": 8,
        "consumed_material_cost": cost,
        "purchased_hardware_cost": 0,
        "energy_cost": 0,
        "labor_cost": 0,
        "fit_passed": True,
        "attachment_test_passed": True,
        "thermal_check_passed": True,
    }


def test_no_measured_specimens_refuses_economic_ranking():
    report = summarize_fabrication_benchmark([])
    assert report["sample_count"] == 0
    assert report["observed_cost_order"] == []
    assert report["construction_method_selected"] is None


def test_synthetic_fixture_never_ranked_as_real_evidence():
    items = [
        _trial("full_print",10,70),
        _trial("sheet_hybrid",4,50),
        _trial("off_the_shelf",12,90),
    ]
    report = summarize_fabrication_benchmark(items)
    assert report["sample_count"] == 3
    assert report["status"] == "partial_or_synthetic_measurement_inventory"
    assert report["observed_cost_order"] == []
    assert report["physical_results_authenticated"] is False
    assert report["release_authorized"] is False


def test_operator_reported_complete_observations_can_be_ordered_not_certified():
    items = [
        _trial("full_print",10,70,kind="operator_reported"),
        _trial("sheet_hybrid",4,50,kind="operator_reported"),
        _trial("off_the_shelf",12,90,kind="operator_reported"),
    ]
    report = summarize_fabrication_benchmark(items)
    assert report["status"] == "operator_reported_multi_variant_comparison_not_independently_verified"
    assert report["observed_cost_order"] == [
        "sheet_hybrid", "full_print", "off_the_shelf"
    ]
    assert report["construction_method_selected"] is None
    assert report["physical_results_authenticated"] is False
    assert report["statistical_reliability_proven"] is False
    assert report["release_authorized"] is False


def test_incomplete_cost_or_failed_joint_test_disables_ordering():
    items = [
        _trial("full_print",10,70,kind="operator_reported"),
        _trial("sheet_hybrid",4,50,kind="operator_reported"),
        _trial("off_the_shelf",12,90,kind="operator_reported"),
    ]
    items[1]["labor_cost"] = None
    assert summarize_fabrication_benchmark(items)["observed_cost_order"] == []
    items[1]["labor_cost"] = 0
    items[1]["attachment_test_passed"] = False
    assert summarize_fabrication_benchmark(items)["observed_cost_order"] == []


def test_repeated_or_untraceable_trials_refused():
    items = [_trial("full_print",8,65)]
    items.append({**items[0]})
    with pytest.raises(ValueError, match="specimen"):
        summarize_fabrication_benchmark(items)
    items = [_trial("full_print",8,65)]
    items[0]["record_uri"] = ""
    with pytest.raises(ValueError, match="URI"):
        summarize_fabrication_benchmark(items)


def test_evaluator_carries_operator_record_inventory_into_mecha_plan():
    p = _project()
    p["construction"]["benchmark_trials"] = [
        _trial("full_print",10,70),
        _trial("sheet_hybrid",4,50),
        _trial("off_the_shelf",12,90),
    ]
    r = evaluate_construction_alternatives(p)
    assert r["fabrication_benchmark"]["sample_count"] == 3
    assert r["fabrication_benchmark"]["observed_cost_order"] == []
    assert "Reported fabrication benchmark" in render_construction_plan(r)


def test_exact_three_build_comparison_print_cardstock_clip_os_plywood_moduframe():
    baseline = _trial("full_print", 10, 70, kind="operator_reported")
    card = _trial("sheet_hybrid", 4, 53, kind="operator_reported")
    card["specimen_id"] = "card-01"
    card["variant_id"] = "cardboard_clip_os"
    plywood = _trial("sheet_hybrid", 6, 63, kind="operator_reported")
    plywood["specimen_id"] = "wood-01"
    plywood["variant_id"] = "plywood_moduframe"
    b = summarize_fabrication_benchmark([baseline,card,plywood])
    assert b["status"] == "operator_reported_multi_variant_comparison_not_independently_verified"
    assert b["observed_cost_order"] == [
        "sheet_hybrid:cardboard_clip_os",
        "sheet_hybrid:plywood_moduframe",
        "full_print",
    ]
    assert {m["variant_key"] for m in b["method_results"]} == {
        "full_print", "sheet_hybrid:cardboard_clip_os",
        "sheet_hybrid:plywood_moduframe",
    }
    assert b["construction_method_selected"] is None
    assert b["release_authorized"] is False


def test_git_blob_identity_matches_gits_actual_object_header():
    import hashlib
    payload = b"STL coupon for deterministic unit test"
    header = b"blob " + str(len(payload)).encode("ascii") + bytes([0])
    expected = hashlib.sha1(header + payload).hexdigest()
    assert verify_git_blob_asset(payload,expected) is True
    assert verify_git_blob_asset(payload+b"!",expected) is False
    assert verify_git_blob_asset(b"bad",expected) is False


def test_known_filename_local_connector_asset_staging_is_strict(tmp_path,monkeypatch):
    import hashlib
    from hardware_splicer import construction_alternatives as module
    fixture=b"mock binary connector coupon"
    expected=hashlib.sha1(
        b"blob " + str(len(fixture)).encode("ascii") + bytes([0]) + fixture
    ).hexdigest()
    reference={
        "name":"test-controlled",
        "pinned_revision":"a"*40,
        "verified_repository_assets":[{
            "name":"clip-o_90_moreflexy.stl",
            "git_blob_sha1":expected,
            "revision_url":"https://example.org/revision-pin",
        }],
    }
    monkeypatch.setitem(module.CONNECTOR_SOURCES,"clip_os",reference)
    source=tmp_path/"SOURCE_ASSETS"
    source.mkdir()
    target=source/"clip-o_90_moreflexy.stl"
    target.write_bytes(b"incorrect downloaded STL")
    invalid=inspect_local_connector_assets({"connector_family":"clip_os"},tmp_path)
    assert invalid["assets"][0]["status"]=="source_hash_mismatch"
    assert invalid["assets_usable_for_manufacturing"] is False
    target.write_bytes(fixture)
    verified=inspect_local_connector_assets({"connector_family":"clip_os"},tmp_path)
    assert verified["assets"][0]["status"]=="exact_git_blob_match"
    assert verified["assets"][0]["geometry_and_fit_verified"] is False
    assert verified["assets_usable_for_manufacturing"] is False


def test_symlink_is_not_followed_for_local_asset_provenance(tmp_path):
    source=tmp_path/"SOURCE_ASSETS"
    source.mkdir()
    outside=tmp_path/"arbitrary_private_file"
    outside.write_text("do not inspect")
    (source/"clip-o_90_moreflexy.stl").symlink_to(outside)
    inspected=inspect_local_connector_assets({"connector_family":"clip_os"},tmp_path)
    assert inspected["assets"][0]["status"]=="refused_symlink"
    assert inspected["assets_usable_for_manufacturing"] is False


def test_symlinked_external_asset_directory_is_not_read(tmp_path):
    directory=tmp_path/"other"
    directory.mkdir()
    (tmp_path/"SOURCE_ASSETS").symlink_to(directory,target_is_directory=True)
    r=inspect_local_connector_assets({"connector_family":"clip_os"},tmp_path)
    assert r["status"]=="refused_symlink_asset_directory"
    assert r["assets_usable_for_manufacturing"] is False
