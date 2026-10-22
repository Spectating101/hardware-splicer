"""Sourced, fail-closed construction alternatives for Mecha-Splicer.

Never treats a public STL as a tested fastener or substitutes an
illustrative thermal/material calculation for product certification.
This module is pure Python: no CAD, dependency downloads or network.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

SCHEMA = "hardware_splicer.construction_alternatives.v1"

# Reference/catalog only. Do not redistribute assets, infer installed status
# or claim an unpinned upstream project is geometrically verified.
CONNECTOR_SOURCES: dict[str, dict[str, Any]] = {
    "clip_os": {
        "name": "Clip-Os",
        "url": "https://github.com/zakqwy/Clip-Os",
        "interface": "downloaded sheet-stock connector",
        "nominal_panel_thickness_mm": 1.6,
        "license": "CC-BY-SA-4.0",
        "requires_external_asset": True,
        "pinned_revision": "348bad8ba0553be79f24d5ac12a7d4081d7759c8",
        "verified_repository_assets": [
            {
                "name": "clip-o_90_moreflexy.stl",
                "repository_path": "fab/clip-o_90_moreflexy.stl",
                "git_blob_sha1": "eda0c9041d229c050296a313af5e4bd1a07892ea",
                "revision_url": "https://github.com/zakqwy/Clip-Os/blob/348bad8ba0553be79f24d5ac12a7d4081d7759c8/fab/clip-o_90_moreflexy.stl",
                "local_file_installed": False,
                "mesh_validated_in_hs": False,
            },
            {
                "name": "clip-o_180_moreflexy.stl",
                "repository_path": "fab/clip-o_180_moreflexy.stl",
                "git_blob_sha1": "fab8122d82c96237fa819429a50dc2cbcc99291f",
                "revision_url": "https://github.com/zakqwy/Clip-Os/blob/348bad8ba0553be79f24d5ac12a7d4081d7759c8/fab/clip-o_180_moreflexy.stl",
                "local_file_installed": False,
                "mesh_validated_in_hs": False,
            },
        ],
        "recommended_hole_center_from_edge_mm": 12.7,
        "hole_diameter_mm": None,
        "nominal_sheet_fit_physically_verified_by_hs": False,
    },
    "moduframe": {
        "name": "ModuFrame",
        "url": "https://www.printables.com/model/1834996-moduframe-modular-connectors-for-3mm-plywood-sheet",
        "interface": "downloaded plywood connector",
        "nominal_panel_thickness_mm": 3.0,
        "license": "verify_item_license_before_redistribution",
        "requires_external_asset": True,
    },
    "bosl2": {
        "name": "BOSL2",
        "url": "https://github.com/BelfrySCAD/BOSL2",
        "interface": "external OpenSCAD parametric primitives",
        "nominal_panel_thickness_mm": None,
        "license": "BSD-2-Clause",
        "requires_external_asset": True,
    },
    "modular_clip": {
        "name": "Modular Clip",
        "url": "https://github.com/jmylchreest/openscad-models",
        "interface": "external parametric clip/dovetail",
        "nominal_panel_thickness_mm": None,
        "license": "verify_source_and_revision",
        "requires_external_asset": True,
    },
    "boxkit": {
        "name": "BoxKit",
        "url": "https://github.com/zef/BoxKit",
        "interface": "external parametric sheet-box corners, pinned hinges and latches",
        "nominal_panel_thickness_mm": None,
        "license": "license_not_verified; link_only_do_not_redistribute",
        "requires_external_asset": True,
        "pinned_revision": "63fb6bee6d81962456ed2403538fe4d83644b122",
        "verified_repository_assets": [
            {
                "name": "BoxKit.scad",
                "repository_path": "BoxKit.scad",
                "git_blob_sha1": "650d587d10570b17ef13f9dae990290ebfccee72",
                "revision_url": "https://github.com/zef/BoxKit/blob/63fb6bee6d81962456ed2403538fe4d83644b122/BoxKit.scad",
                "local_file_installed": False,
                "mesh_validated_in_hs": False,
            }
        ],
        "source_dependencies": [
            "revarbat/BOSL (original, not BOSL2)",
            "Irev-Dev/Round-Anything"
        ],
        "source_license_review_required": True,
    },
    "boxes_py": {
        "name": "Boxes.py",
        "url": "https://github.com/florianfesti/boxes",
        "interface": "external sheet-cutting pattern tool",
        "nominal_panel_thickness_mm": None,
        "license": "GPL-3.0-or-later",
        "requires_external_asset": True,
    },
}


def _valid_positive(number: Any, label: str, *, permit_zero: bool = False) -> float:
    try:
        result = float(number)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(result) or result < 0 or (result == 0 and not permit_zero):
        raise ValueError(f"{label} must be finite and {'nonnegative' if permit_zero else 'positive'}")
    return result


def _material(record: Any, role: str) -> dict[str, Any] | None:
    if record is None:
        return None
    if not isinstance(record, Mapping):
        raise ValueError(f"{role} must be a material object")
    result = dict(record)
    for key in ("density_kg_m3", "max_service_temp_c", "cost_per_kg",
                "cost_per_m2", "elastic_modulus_mpa", "thermal_conductivity_w_mk"):
        value = result.get(key)
        if value is None:
            continue
        if key == "max_service_temp_c":
            if not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError("max_service_temp_c must be finite")
        else:
            _valid_positive(value, f"{role}.{key}", permit_zero=key.startswith("cost_"))
    if result.get("evidence_kind") == "datasheet" and not str(
        result.get("source_uri") or ""
    ).startswith("https://"):
        raise ValueError(f"{role}: datasheet evidence needs an HTTPS source URI")
    if result.get("evidence_kind") not in ("assumed", "datasheet", "measured"):
        raise ValueError(f"{role} evidence_kind must be assumed, datasheet or measured")
    return result


def _mass_g(volume_mm3: float, density_kg_m3: float | None) -> float | None:
    if density_kg_m3 is None:
        return None
    return round(volume_mm3 * 1e-6 * density_kg_m3, 3)


def verify_git_blob_asset(data: bytes, expected_sha1: str) -> bool:
    """Compare exact Git blob SHA-1 against a pinned public source object."""
    import hashlib

    if not isinstance(data, bytes) or len(data) > 4_000_000:
        return False
    if not isinstance(expected_sha1, str) or len(expected_sha1) != 40:
        return False
    actual = hashlib.sha1(
        ("blob " + str(len(data)) + "\0").encode("ascii") + data
    ).hexdigest()
    return actual == expected_sha1


def inspect_local_connector_assets(
    construction: Mapping[str, Any],
    output_dir: str | Any,
) -> dict[str, Any]:
    """Read ONLY allowlisted filenames under this build's SOURCE_ASSETS folder.

    Never follows symlinks or user supplied file paths. This is provenance
    validation, not a geometry, print quality or load-bearing test.
    """
    from pathlib import Path

    source = CONNECTOR_SOURCES.get(construction.get("connector_family"))
    root = Path(output_dir) / "SOURCE_ASSETS"
    if root.is_symlink():
        return {
            "status": "refused_symlink_asset_directory",
            "assets": [],
            "assets_usable_for_manufacturing": False,
        }
    if not source or not source.get("verified_repository_assets"):
        return {
            "status": "no_pinned_source_assets",
            "assets": [],
            "assets_usable_for_manufacturing": False,
        }
    results = []
    for item in source["verified_repository_assets"]:
        local = root / item["name"]
        if local.is_symlink():
            status = "refused_symlink"
        elif not local.is_file():
            status = "not_supplied"
        else:
            try:
                if local.stat().st_size > 4_000_000:
                    status = "refused_oversized_file"
                else:
                    status = (
                        "exact_git_blob_match"
                        if verify_git_blob_asset(local.read_bytes(),item["git_blob_sha1"])
                        else "source_hash_mismatch"
                    )
            except OSError:
                status = "file_read_error"
        results.append({
            "filename":item["name"],
            "expected_git_blob_sha1":item["git_blob_sha1"],
            "status":status,
            "relative_path":"SOURCE_ASSETS/" + item["name"],
            "source_revision_url":item["revision_url"],
            "geometry_and_fit_verified":False,
        })
    return {
        "status": (
            "source_bytes_verified_not_fit_tested"
            if any(x["status"] == "exact_git_blob_match" for x in results)
            else "source_assets_missing_or_invalid"
        ),
        "assets":results,
        "assets_usable_for_manufacturing":False,
        "all_asset_fit_and_strength_tests_passed":False,
    }


def summarize_fabrication_benchmark(trials: Any) -> dict[str, Any]:
    """Summarize user-provided observations, never invent shop measurements.

    Costs use the operator's consistent currency; energy and labor must be
    recorded explicitly before a complete total can be compared.
    """
    from statistics import median

    if trials is None or trials == []:
        return {
            "status": "awaiting_real_measurements",
            "sample_count": 0,
            "method_results": [],
            "observed_cost_order": [],
            "physical_results_authenticated": False,
            "construction_method_selected": None,
        }
    if not isinstance(trials, list) or len(trials) > 60:
        raise ValueError("benchmark_trials must be a bounded list")
    valid_methods = ("full_print", "sheet_hybrid", "off_the_shelf")
    required = ("finished_mass_g", "printing_minutes", "cutting_minutes",
                "assembly_minutes", "consumed_material_cost",
                "purchased_hardware_cost")
    grouped: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for trial in trials:
        if not isinstance(trial, Mapping):
            raise ValueError("benchmark trial must be an object")
        method = trial.get("method")
        specimen = str(trial.get("specimen_id") or "").strip()
        if method not in valid_methods or not specimen or specimen in seen:
            raise ValueError("benchmark method or distinct specimen ID invalid")
        seen.add(specimen)
        variant = trial.get("variant_id")
        if variant is not None and (
            not isinstance(variant,str) or not variant.strip() or len(variant)>80 or
            any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in variant)
        ):
            raise ValueError("variant_id must be a short safe slug")
        variant = variant.strip() if variant is not None else None
        group_key = method + (":" + variant if variant else "")
        uri = trial.get("record_uri")
        if not isinstance(uri,str) or not uri.strip() or len(uri)>500:
            raise ValueError("benchmark evidence record URI required")
        evidence = trial.get("evidence_kind")
        if evidence not in ("operator_reported", "synthetic_fixture"):
            raise ValueError("benchmark must declare synthetic or operator reported evidence")
        for key in required:
            _valid_positive(trial.get(key), key, permit_zero=(key!="finished_mass_g"))
        if trial.get("panel_scrap_mass_g") is not None:
            _valid_positive(trial["panel_scrap_mass_g"], "scrap mass", permit_zero=True)
        energy = trial.get("energy_cost")
        labor = trial.get("labor_cost")
        for key,value in (("energy_cost",energy),("labor_cost",labor)):
            if value is not None:
                _valid_positive(value,key,permit_zero=True)
        total_cost = (
            round(sum(float(trial[key]) for key in
                      ("consumed_material_cost","purchased_hardware_cost"))+
                  float(energy)+float(labor),3)
            if energy is not None and labor is not None else None
        )
        grouped.setdefault(group_key, []).append({
            "specimen_id": specimen,
            "variant_id": variant,
            "method": method,
            "record_uri": uri,
            "evidence_kind": evidence,
            "finished_mass_g": float(trial["finished_mass_g"]),
            "fabrication_minutes": round(
                sum(float(trial[key]) for key in
                    ("printing_minutes","cutting_minutes","assembly_minutes")),2
            ),
            "reported_total_cost": total_cost,
            "panel_scrap_mass_g": trial.get("panel_scrap_mass_g"),
            "fit_passed": trial.get("fit_passed"),
            "attachment_test_passed": trial.get("attachment_test_passed"),
            "thermal_check_passed": trial.get("thermal_check_passed"),
        })
    method_results = []
    for variant_key,records in grouped.items():
        if not records:
            continue
        method = records[0]["method"]
        complete_cost = all(x["reported_total_cost"] is not None for x in records)
        method_results.append({
            "method":method,
            "variant_key":variant_key,
            "specimen_count":len(records),
            "specimens":records,
            "median_finished_mass_g":round(median(x["finished_mass_g"] for x in records),3),
            "median_fabrication_minutes":round(median(x["fabrication_minutes"] for x in records),3),
            "median_reported_total_cost":(
                round(median(x["reported_total_cost"] for x in records),3)
                if complete_cost else None
            ),
            "evidence_only_operator_reports":all(
                x["evidence_kind"]=="operator_reported" for x in records
            ),
            "all_declared_check_results_pass":all(
                x["fit_passed"] is True and
                x["attachment_test_passed"] is True and
                x["thermal_check_passed"] is True for x in records
            ),
        })
    complete = (
        len(method_results)>=3 and
        any(x["method"] == "full_print" for x in method_results) and
        all(x["median_reported_total_cost"] is not None and
            x["evidence_only_operator_reports"] and
            x["all_declared_check_results_pass"]
            for x in method_results)
    )
    order = (
        [x["variant_key"] for x in sorted(
            method_results,key=lambda x:x["median_reported_total_cost"]
        )] if complete else []
    )
    return {
        "status": "operator_reported_multi_variant_comparison_not_independently_verified" if complete
                  else "partial_or_synthetic_measurement_inventory",
        "sample_count":len(seen),
        "method_results":method_results,
        "observed_cost_order":order,
        "physical_results_authenticated":False,
        "statistical_reliability_proven":False,
        "construction_method_selected":None,
        "release_authorized":False,
        "disclosure":"Provided values are operator-reported or synthetic, not authenticated test evidence. Reported pass flags are not engineering approval.",
    }


def evaluate_construction_alternatives(
    project: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate print vs sheet hybrid, using ONLY supplied material properties.

    This is a concept-stage estimator. No slicer mass, structural strength,
    electronics fire safety, interface fit or thermal simulation is inferred.
    """
    construction = project.get("construction")
    if construction is None:
        return {
            "schema_version": SCHEMA,
            "status": "not_requested",
            "alternatives": [],
            "fabrication_authorized": False,
        }
    if not isinstance(construction, Mapping):
        raise ValueError("construction must be an object")
    preference = construction.get("preference", "auto")
    if preference not in ("auto", "full_print", "sheet_hybrid", "off_the_shelf"):
        raise ValueError("unsupported construction preference")
    enclosure = project.get("enclosure")
    if not isinstance(enclosure, Mapping):
        return {
            "schema_version": SCHEMA,
            "status": "unsupported_non_enclosure",
            "reason": "hybrid panel calculations require a rectangular enclosure",
            "alternatives": [],
            "fabrication_authorized": False,
        }
    iw = _valid_positive(enclosure.get("inner_w_mm"), "inner width")
    idepth = _valid_positive(enclosure.get("inner_d_mm"), "inner depth")
    ih = _valid_positive(enclosure.get("inner_h_mm"), "inner height")
    wall = _valid_positive(enclosure.get("wall_mm", 2.4), "wall")
    floor = _valid_positive(enclosure.get("floor_mm", 2.0), "floor")
    lid = _valid_positive(enclosure.get("lid_mm", 2.0), "lid")
    outer = (iw + 2*wall, idepth + 2*wall, ih + floor + lid)
    ow, od, oh = outer
    # Solid shell envelope plus lid, excluding standoffs, cutouts and
    # actual slicer toolpaths; NOT filament consumption.
    base_h = ih + floor
    base_envelope_mm3 = (ow*od*base_h - iw*idepth*ih)
    lid_envelope_mm3 = ow*od*lid
    shell_envelope_mm3 = base_envelope_mm3 + lid_envelope_mm3
    sheet_area_mm2 = 2*(ow*od + ow*oh + od*oh)
    print_record = _material(construction.get("filament_material"), "filament_material")
    panel_record = _material(construction.get("panel_material"), "panel_material")
    thickness = construction.get("panel_thickness_mm")
    if thickness is not None:
        thickness = _valid_positive(thickness,"panel_thickness_mm")
    fill = construction.get("printed_material_fraction")
    if fill is not None:
        fill = _valid_positive(fill,"printed_material_fraction")
        if fill > 1:
            raise ValueError("printed_material_fraction must be <=1")
    connector_count = construction.get("connector_count",8)
    if not isinstance(connector_count,int) or not 0 <= connector_count <= 100:
        raise ValueError("connector_count must be integer in [0,100]")
    connector_volume_cm3 = construction.get("connector_print_volume_cm3")
    if connector_volume_cm3 is not None:
        connector_volume_cm3 = _valid_positive(
            connector_volume_cm3,"connector_print_volume_cm3", permit_zero=True
        )
    connector_key = construction.get("connector_family", "unselected")
    if connector_key not in (*CONNECTOR_SOURCES, "unselected"):
        raise ValueError("unknown connector library")
    connector = dict(CONNECTOR_SOURCES[connector_key]) if connector_key!="unselected" else None
    if connector is not None:
        connector["id"] = connector_key
        connector["revision_pinned"] = bool(connector.get("pinned_revision"))
        connector["local_asset_validated"] = False
        connector["fit_physically_verified"] = False
    temp = construction.get("operating_temp_c")
    if temp is not None:
        if not isinstance(temp,(int,float)) or not math.isfinite(temp):
            raise ValueError("operating temperature must be finite")
    exposures = construction.get("chemical_exposures") or []
    if not isinstance(exposures,list) or any(not isinstance(x,str) for x in exposures):
        raise ValueError("chemical_exposures must be a string list")
    if len(exposures)>20 or any(not x or len(x)>60 for x in exposures):
        raise ValueError("chemical exposures must be short named conditions")
    warnings_common = [
        "not_slicer_measured_print_mass",
        "joint_strength_and_panel_stiffness_not_verified",
        "fire_and_electrical_enclosure_compliance_unverified",
        "cooling_airflow_and_thermal_simulation_not_performed",
    ]
    thermal_checks: dict[str, Any] = {}
    chemical_checks: dict[str, Any] = {}
    for label,record in (("filament",print_record),("panel",panel_record)):
        if record is None:
            thermal_checks[label] = "missing_material_record"
            # Keep the chemical status a mapping even when the record is absent.
            # Missing evidence means unknown, never a compatible result.
            chemical_checks[label] = {exposure: "unknown" for exposure in exposures}
            continue
        if temp is None or record.get("max_service_temp_c") is None:
            thermal_checks[label] = "unknown"
        else:
            thermal_checks[label] = (
                "above_reported_service_limit"
                if temp >= record["max_service_temp_c"] else "below_reported_limit_not_validated"
            )
        matrix = record.get("chemical_compatibility") or {}
        if not isinstance(matrix,Mapping):
            raise ValueError("chemical compatibility must be an exposure map")
        if any(v not in ("compatible","incompatible","unknown") for v in matrix.values()):
            raise ValueError("chemical compatibilities must be compatible/incompatible/unknown")
        chemical_checks[label] = {
            exposure: matrix.get(exposure,"unknown") for exposure in exposures
        }
    panel_blockers = []
    if panel_record is None or thickness is None:
        panel_blockers.append("sheet_material_or_measured_thickness_missing")
    if connector is None:
        panel_blockers.append("no_external_connector_selected")
    elif connector["nominal_panel_thickness_mm"] is not None:
        nominal = connector["nominal_panel_thickness_mm"]
        if thickness is None:
            panel_blockers.append("connector_fit_requires_measured_thickness")
        elif abs(thickness - nominal)>0.1:
            panel_blockers.append("connector_nominal_thickness_mismatch")
    if connector_count and connector_volume_cm3 is None:
        panel_blockers.append("connector_volume_not_measured")
    for role in ("filament","panel"):
        if thermal_checks[role] == "above_reported_service_limit":
            panel_blockers.append(f"{role}_temperature_limit_exceeded")
        if "incompatible" in (chemical_checks.get(role) or {}).values():
            panel_blockers.append(f"{role}_chemical_incompatibility")
    if temp is None:
        panel_blockers.append("operating_temperature_unknown")
    if exposures and any(
        "unknown" in (chemical_checks.get(role) or {}).values()
        for role in ("panel","filament")
    ):
        panel_blockers.append("chemical_compatibility_unverified")
    if panel_record and panel_record.get("evidence_kind") == "assumed":
        panel_blockers.append("panel_material_properties_assumed")
    if print_record and print_record.get("evidence_kind") == "assumed":
        panel_blockers.append("filament_material_properties_assumed")
    if connector:
        if not connector["revision_pinned"]:
            panel_blockers.append("external_connector_revision_unpinned")
        if connector.get("source_license_review_required"):
            panel_blockers.append("external_connector_license_not_verified")
        panel_blockers.append("connector_files_not_validated_or_installed")
    print_mass_g = _mass_g(
        shell_envelope_mm3 * fill if fill is not None else shell_envelope_mm3,
        print_record.get("density_kg_m3") if print_record else None,
    )
    sheet_mass_g = _mass_g(
        sheet_area_mm2*thickness if thickness is not None else 0,
        panel_record.get("density_kg_m3") if panel_record and thickness is not None else None,
    )
    connector_mass_g = _mass_g(
        (connector_volume_cm3 or 0)*1000 * connector_count,
        print_record.get("density_kg_m3") if print_record and connector_volume_cm3 is not None else None,
    )
    mass_hybrid = (
        round(sheet_mass_g+connector_mass_g,3)
        if sheet_mass_g is not None and connector_mass_g is not None else None
    )
    # Cost is evaluated only when supplied by the user/sourcing record.
    print_cost = (
        round(print_mass_g/1000*print_record["cost_per_kg"],3)
        if print_mass_g is not None and print_record and print_record.get("cost_per_kg") is not None
        else None
    )
    hybrid_cost = (
        round(sheet_area_mm2*1e-6*panel_record["cost_per_m2"]+
              connector_mass_g/1000*print_record["cost_per_kg"],3)
        if (panel_record and print_record and connector_mass_g is not None
            and panel_record.get("cost_per_m2") is not None
            and print_record.get("cost_per_kg") is not None)
        else None
    )
    delta_mass = round(print_mass_g - mass_hybrid,3) if (
        print_mass_g is not None and mass_hybrid is not None) else None
    delta_cost = round(print_cost - hybrid_cost,3) if (
        print_cost is not None and hybrid_cost is not None) else None
    alternatives = [
        {
            "method": "full_print",
            "status": "existing_geometry_retained",
            "estimated_solid_envelope_mm3": round(shell_envelope_mm3,2),
            "estimated_printed_mass_g": print_mass_g,
            "material_cost_only": print_cost,
            "mass_basis": ("user_assumed_occupancy" if fill is not None
                           else "solid_shell_envelope_upper_bound"),
            "blockers": warnings_common + (
                ["filament_material_unprovided"] if print_record is None else []
            ),
        },
        {
            "method": "sheet_hybrid",
            "status": "candidate_for_manual_validation" if not panel_blockers else "blocked_pending_evidence",
            "panel_area_mm2_unoptimized": round(sheet_area_mm2,2),
            "panel_cuts": [
                {"size_mm":[ow,od],"quantity":2},
                {"size_mm":[ow,oh],"quantity":2},
                {"size_mm":[od,oh],"quantity":2},
            ],
            "panel_mass_g": sheet_mass_g,
            "connector_printed_mass_g": connector_mass_g,
            "combined_estimated_mass_g": mass_hybrid,
            "material_cost_only": hybrid_cost,
            "connector_source": connector,
            "blockers": sorted(set(panel_blockers+warnings_common)),
        },
        {
            "method": "off_the_shelf",
            "status": "requires_sourcing",
            "material_cost_only": None,
            "blockers":["no_purchased_assembly_quote_or_dimensional_match"],
        },
    ]
    return {
        "schema_version": SCHEMA,
        "status": "comparison_produced_research_only",
        "fabrication_benchmark": summarize_fabrication_benchmark(
            construction.get("benchmark_trials")
        ),
        "requested_preference": preference,
        "enclosure_outer_dimensions_mm": list(outer),
        "materials": {
            "panel_id": panel_record.get("material_id") if panel_record else None,
            "filament_id": print_record.get("material_id") if print_record else None,
            "panel_evidence": panel_record.get("evidence_kind") if panel_record else None,
            "filament_evidence": print_record.get("evidence_kind") if print_record else None,
            "panel_source_uri": panel_record.get("source_uri") if panel_record else None,
            "filament_source_uri": print_record.get("source_uri") if print_record else None,
        },
        "thermal_screen": thermal_checks,
        "chemical_screen": chemical_checks,
        "material_property_evidence": {
            role: (
                {
                    "material_id": record.get("material_id"),
                    "source_uri": record.get("source_uri"),
                    "evidence_kind": record.get("evidence_kind"),
                    "density_kg_m3": record.get("density_kg_m3"),
                    "elastic_modulus_mpa": record.get("elastic_modulus_mpa"),
                    "thermal_conductivity_w_mk": record.get("thermal_conductivity_w_mk"),
                    "max_service_temp_c": record.get("max_service_temp_c"),
                    "conductivity_used_in_thermal_solver": False,
                    "modulus_used_in_assembly_stress_solver": False,
                } if record else None
            )
            for role,record in (("filament",print_record),("panel",panel_record))
        },
        "alternatives": alternatives,
        "hypothetical_full_print_minus_hybrid_mass_g": delta_mass,
        "hypothetical_material_cost_difference": delta_cost,
        "economic_preference": (
            "hybrid_lower_estimated_material_cost"
            if delta_cost is not None and delta_cost>0 else
            "full_print_lower_estimated_material_cost"
            if delta_cost is not None and delta_cost<0 else
            "material_cost_tie" if delta_cost==0 else "cost_comparison_unavailable"
        ),
        "selected_manufacturing_method": None,
        "no_unverified_automatic_substitution": True,
        "physical_panel_joint_testing_required": True,
        "full_enclosure_thermal_simulation_performed": False,
        "chemical_compatibility_verified_by_experiment": False,
        "structural_safety_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }


def render_construction_plan(report: Mapping[str, Any]) -> str:
    """Human-readable concepts, measurement gaps and upstream attribution."""
    if report.get("status") == "not_requested":
        return "# Construction alternatives\n\nNot requested.\n"
    lines = [
        "# Construction alternatives (research screening only)",
        "",
        "No manufacturing method has been auto-selected or approved.",
        f"- Status: {report.get('status')}",
        f"- Preference: {report.get('requested_preference', 'n/a')}",
        "- The existing fully printed CAD remains unchanged.",
        "- All mass and cost numbers are estimates, not slicer or shop measurements.",
        "",
    ]
    for a in report.get("alternatives") or []:
        lines.extend([
            f"## {a['method']}",
            f"- Status: {a['status']}",
            f"- Estimated material-only cost (provided input units): {a.get('material_cost_only')}",
            f"- Blockers: {', '.join(a.get('blockers') or []) or 'none recorded'}",
        ])
        if a["method"] == "sheet_hybrid":
            lines.append("- Preliminary panel cut rectangles, without kerf, joints or nesting:")
            for part in a.get("panel_cuts") or []:
                lines.append(f"  - {part['quantity']} x {part['size_mm'][0]} x {part['size_mm'][1]} mm")
            source = a.get("connector_source")
            if source:
                lines.extend([
                    f"- External connector: {source['name']}",
                    f"- Official source: {source['url']}",
                    f"- Upstream license/notice: {source['license']}",
                    "- Verify exact revision, download licensing, fit and real attachment strength.",
                ])
                if source.get("pinned_revision"):
                    lines.append("- Pinned Git revision: " + str(source["pinned_revision"]))
                    for asset in source.get("verified_repository_assets") or []:
                        lines.append(
                            "- Upstream STL (not downloaded): " +
                            asset["name"] + " — " + asset["revision_url"] +
                            " (Git blob " + asset["git_blob_sha1"] + ")"
                        )
                if source.get("recommended_hole_center_from_edge_mm"):
                    lines.append(
                        "- Upstream recommended mounting hole center inset: " +
                        str(source["recommended_hole_center_from_edge_mm"]) +
                        " mm; hole diameter must be verified from the original instructions/tools."
                    )
        lines.append("")
    integrity = report.get("external_asset_integrity") or {}
    if integrity:
        lines.append("## Supplied external connector asset integrity")
        lines.append("- " + str(integrity.get("status")))
        for file in integrity.get("assets") or []:
            lines.append(
                "- " + file["relative_path"] + ": " + file["status"] +
                "; physical connector fit not verified."
            )
        lines.append("")
    benchmark = report.get("fabrication_benchmark") or {}
    lines.extend([
        "## Reported fabrication benchmark",
        "- Status: " + str(benchmark.get("status", "not requested")),
        "- Measured specimen entries: " + str(benchmark.get("sample_count",0)),
        "- No measurements are authenticated or allowed to certify production.",
    ])
    for sample in benchmark.get("method_results") or []:
        lines.append(
            "- " + sample["variant_key"] + ": " + str(sample["specimen_count"]) +
            " specimens, median finished mass " +
            str(sample["median_finished_mass_g"]) + " g; reported total cost " +
            str(sample["median_reported_total_cost"]) +
            " (currency as supplied; may be incomplete)"
        )
    if benchmark.get("observed_cost_order"):
        lines.append(
            "- Conditional reported cost order (not a build recommendation): " +
            ", ".join(benchmark["observed_cost_order"])
        )
    lines.extend(["",
        "## Before selecting a method",
        "- Measure actual sheet and fastener dimensions; check purchased hardware first.",
        "- Confirm service temperature, cooling, electrical/fire safety and chemical exposures.",
        "- Confirm material datasheets or physical measurement source for every property.",
        "- Verify joints and connector pull-through with the intended load and orientation.",
        "- Compare actual printer slicing, panel nesting, sourcing, assembly time and prices.",
        "",
    ])
    return "\n".join(lines)
