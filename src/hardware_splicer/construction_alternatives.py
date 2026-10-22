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
        connector["revision_pinned"] = False
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
            chemical_checks[label] = "missing_material_record"
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
        panel_blockers.extend(("external_connector_revision_unpinned",
                               "connector_files_not_validated_or_installed"))
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
        lines.append("")
    lines.extend([
        "## Before selecting a method",
        "- Measure actual sheet and fastener dimensions; check purchased hardware first.",
        "- Confirm service temperature, cooling, electrical/fire safety and chemical exposures.",
        "- Confirm material datasheets or physical measurement source for every property.",
        "- Verify joints and connector pull-through with the intended load and orientation.",
        "- Compare actual printer slicing, panel nesting, sourcing, assembly time and prices.",
        "",
    ])
    return "\n".join(lines)
