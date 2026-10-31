"""Assembly-interface evidence gate for a manufacturer-referenced filter study.

Reconciles upstream function/technology/component/CAD evidence and a
documentary accessory catalog. Outputs verified *planning* interfaces and
uncollected measurement requirements, never fit, operating or health authority.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .function_intent_bridge import canonical

SCHEMA = "hardware_splicer.nonpotable_filter_assembly_interfaces.v1"
PARTS = {"155014-43", "158007"}
ACCESSORIES = {"BRACKET_CANDIDATE": "244047",
               "WRENCH_CANDIDATE": "150539", "ORING_CANDIDATE": "151121"}
UNSELECTED = {"UNSELECTED_NPT_CONNECTORS", "UNSELECTED_PRESSURE_TAPS"}
REQS = {"REQ_FLOW", "REQ_PARTICLE", "REQ_LEAK", "REQ_BYPASS",
        "REQ_SERVICE", "REQ_MONITOR", "REQ_NONPOTABLE"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(value: bool, reason: str) -> None:
    if not value:
        raise ValueError("Assembly evidence REFUSED: " + reason)


def load(root: Path, filename: str) -> dict:
    value = json.loads((root / filename).read_text())
    require(isinstance(value, dict), "invalid structured file " + filename)
    return value


def verified_artifact(root: Path, name: str, metadata: Mapping[str, Any]) -> None:
    file = root / name
    require(file.is_file(), "missing actual source file " + name)
    body = file.read_bytes()
    require(metadata.get("sha256") == sha(body) and
            metadata.get("bytes") == len(body),
            "upstream source/evidence artifact altered: " + name)


def _read_real_native_candidate(root: Path) -> tuple[dict, dict, dict, dict]:
    root = Path(root)
    receipt = load(root, "COMPONENT_PACKAGE_RECEIPT.json")
    require(receipt.get("schema_version") ==
            "hardware_splicer.filter_component_package_receipt.v1",
            "unrecognized upstream component package")
    require(set(receipt.get("files", {})) ==
            {"COMPONENT_REFERENCE.json", "COMPONENT_PREFLIGHT.json",
             "COMPONENT_BOM.json", "clearance.scad"},
            "incomplete component package")
    for name, info in receipt["files"].items():
        verified_artifact(root, name, info)
    ref = load(root, "COMPONENT_REFERENCE.json")
    study = load(root, "COMPONENT_PREFLIGHT.json")
    bom = load(root, "COMPONENT_BOM.json")
    native = load(root, "RENDERED_CLEARANCE_EVIDENCE.json")
    require(receipt.get("source_spec_sha256") == study.get("source_spec_sha256")
            == bom.get("source_spec_sha256") == native.get("source_spec_sha256"),
            "upstream function source changed")
    require(receipt.get("component_reference_sha256") ==
            study.get("component_reference_sha256") ==
            native.get("component_reference_sha256") ==
            bom.get("source_component_reference_sha256") == sha(canonical(ref)),
            "component identity does not match native CAD study")
    require(native.get("schema_version") ==
            "hardware_splicer.filter_clearance_native_cad_evidence.v1"
            and native.get("renderer") == "OpenSCAD CLI"
            and native.get("catalog_envelope_dimensions_verified_in_rendered_mesh") is True,
            "missing independently executed native CAD bounds")
    require(native.get("cad_source_sha256") ==
            sha((root / "clearance.scad").read_bytes()),
            "CAD source digest mismatched")
    require(set(native.get("solids", {})) == {"housing", "service"},
            "real housing/service meshes missing")
    expected = {"housing": ([118.0, 118.0, 308.0], [0, 308]),
                "service": ([118.0, 118.0, 150.0], [-150, 0])}
    for name, (size, zs) in expected.items():
        mesh = native["solids"][name]
        require(mesh.get("dimensions_mm") == size and
                mesh.get("z_bounds_mm") == zs and
                mesh.get("watertight") is True and
                mesh.get("winding_consistent") is True,
                "native geometry doesn't meet expected external bounds: " + name)
        verified_artifact(root, mesh["stl_filename"], mesh)
    for key in ("physical_fit_verified", "installation_clearance_verified",
                "pressure_containing_design_generated", "manufacturing_authorized",
                "water_activation_authorized", "human_consumption_authorized"):
        require(native.get(key) is False, "native CAD falsely implies " + key)
    require(study.get("pressure_loss_at_target_flow_psi") is None and
            study.get("measured_treatment_reduction_percent") is None and
            study.get("physical_cartridge_to_housing_fit_validated") is False,
            "upstream hydraulic or filter-performance claim unsupported")
    require(bom.get("full_bom") is False and len(bom.get("items", [])) == 2,
            "upstream incomplete BOM misrepresented as procurement-ready")
    require({r["part_number"] for r in bom["items"]} == PARTS,
            "expected real candidate part numbers missing")
    return receipt, ref, study, native


def verify_assembly(root: Path, source: Mapping[str, Any]) -> tuple[dict, dict]:
    receipt, components, part_report, native = _read_real_native_candidate(root)
    require(source.get("schema_version") == SCHEMA and
            source.get("project_id") == part_report.get("project_id") and
            source.get("reference_parts") ==
            {"housing": "158007", "cartridge": "155014-43"},
            "wrong assembly source identity")
    require(source.get("authority") == "DOCUMENTARY_ASSEMBLY_INVESTIGATION_ONLY",
            "assembly unexpectedly qualified")
    source_refs = source.get("manufacturer_references", [])
    ref_ids = {r.get("id") for r in source_refs}
    require(ref_ids == {"traditional_pdf_2018", "traditional_pdf_2025",
                        "pentair_traditional_current"} and len(source_refs) == 3,
            "missing or inconsistent manufacturer reference catalog")
    urls = {
        "traditional_pdf_2018":
            "https://www.pentair.com/content/dam/extranet/web/nam/pentek/spec-sheets/310050-pentek-traditional-slimline-spec-sheet.pdf",
        "traditional_pdf_2025":
            components["housing"]["source"]["url"],
        "pentair_traditional_current":
            "https://www.pentair.com/en-us/home-water-treatment/filter-housings/traditional-slim-line-series.html",
    }
    revisions = {"traditional_pdf_2018": "310050 REV F JE18",
                 "traditional_pdf_2025": "310050 JL25"}
    for reference in source_refs:
        ident = reference["id"]
        require(reference.get("publisher") == "Pentair"
                and reference.get("url") == urls[ident]
                and reference.get("original_pdf_sha256") is None
                and (ident not in revisions or
                     reference.get("revision") == revisions[ident]),
                "manufacturer source drift or fake frozen source digest")
    extras = source.get("accessories")
    require(isinstance(extras, list) and len(extras) == 3
            and len({row.get("id") for row in extras}) == 3,
            "incomplete accessory candidates")
    accessory_ids = {row.get("part_number") for row in extras}
    require(accessory_ids == set(ACCESSORIES.values()),
            "wrong manufacturer accessory part")
    for row in extras:
        require(row.get("part_number") == ACCESSORIES.get(row.get("id")) and
                row.get("manufacturer") == "Pentair"
                and row.get("source_id") == "traditional_pdf_2018"
                and row.get("listed_by_manufacturer") is True
                and row.get("approval") == "CANDIDATE_ONLY",
                "accessory not tied to actual family source or falsely approved")
        for key in ("sku_specific_fit_confirmed", "drill_template_verified",
                    "weight_load_rating_verified", "required_swing_clearance_measured",
                    "seal_groove_measured"):
            if key in row:
                require(row[key] is False, "fabricated accessory fit/measurement: " + key)
    connections = source.get("interfaces")
    require(isinstance(connections, list) and len(connections) == 6
            and len({i.get("id") for i in connections}) == 6,
            "interface coverage incomplete")
    expected_edges = {
        "IF_CARTRIDGE_SUMP": ("155014-43", "158007"),
        "IF_CAP_BRACKET": ("158007", "244047"),
        "IF_PORT_FITTINGS": ("158007", "UNSELECTED_NPT_CONNECTORS"),
        "IF_SUMP_WRENCH": ("158007", "150539"),
        "IF_ORING_SUMP": ("158007", "151121"),
        "IF_INSTRUMENTS": ("158007", "UNSELECTED_PRESSURE_TAPS"),
    }
    for row in connections:
        expected = expected_edges.get(row.get("id"))
        require(expected == (row.get("from"), row.get("to")),
                "unknown or mismatched physical interface")
        require(row.get("functional_requirements") and
                set(row["functional_requirements"]) <= REQS and
                len(row["functional_requirements"]) ==
                len(set(row["functional_requirements"])),
                "interface missing valid functional requirement")
        require(isinstance(row.get("verification"), str) and
                bool(row["verification"].strip()) and
                isinstance(row.get("unknown_fields"), list) and
                len(row["unknown_fields"]) >= 3 and
                len(row["unknown_fields"]) == len(set(row["unknown_fields"])),
                "interface has no independently testable unresolved conditions")
    require(components["housing"]["inlet_outlet_connection"] == "3/8in_NPT"
            and components["housing"]["part_number"] == "158007",
            "actual housing connection changed")
    fit = source.get("service_envelope", {})
    require(fit.get("housing_max_height_mm") == 308
            and fit.get("illustrative_below_access_mm") == 150
            and fit.get("vertical_reserved_total_mm") == 458
            and fit.get("design_clearance_authority") ==
                "ILLUSTRATIVE_USER_ALLOCATION_NOT_MANUFACTURER_INSTALLATION_CLEARANCE"
            and fit.get("manufacturer_sku_specific_minimum_below_clearance_mm") is None
            and fit.get("housing_boss_pitch_mm") is None
            and fit.get("wrenched_service_sweep_radius_mm") is None
            and fit.get("fit_verified") is False,
            "illustrative clearance promoted to actual service or mounting dimension")
    hydraulic = source.get("hydraulics", {})
    require(hydraulic.get("target_flow_l_min") == part_report.get("target_flow_l_min") == 0.5
            and hydraulic.get("manufacturer_reference_flow_us_gpm") == 5.0
            and hydraulic.get("cartridge_reference_deltap_psi") == 0.2
            and hydraulic.get("housing_reference_deltap_psi") == 2.0
            and hydraulic.get("actual_design_flow_pressure_drop_psi") is None
            and hydraulic.get("inflow_pressure_psi") is None
            and hydraulic.get("actual_wet_test_executed") is False
            and hydraulic.get("process_model_executed") is False,
            "hydraulic design conditions or true evidence were fabricated")
    certificate = source.get("certification_review", {})
    require(certificate.get("source_id") == "traditional_pdf_2018"
            and certificate.get("housing_158007_listed_in_reviewed_nsf_ansi_42_material_structural_sku_list") is False
            and certificate.get("product_certification_conclusion") ==
                "NOT_ESTABLISHED_BY_REVIEWED_2018_MANUFACTURER_LIST"
            and all(certificate.get(field) is False for field in
                    ("certification_for_selected_housing_currently_verified",
                     "certification_for_assembled_unit_verified",
                     "water_quality_performance_certified")),
            "incorrect transfer of component NSF status or water-quality claims")
    expected_roles = {"E_DIMENSIONS", "E_BRACKET", "E_SERVICE", "E_RATINGS",
                      "E_HYDRAULIC", "E_WATER_QUALITY", "E_COMPLIANCE"}
    roles = source.get("required_evidence_roles")
    require(isinstance(roles, list) and {r.get("id") for r in roles} == expected_roles
            and len(roles) == 7 and
            all(r.get("status") == "NOT_COLLECTED" and bool(r.get("scope")) for r in roles),
            "real measurements or certification evidence falsely supplied")
    require(source.get("physical_authority") ==
            {"purchase": False, "drill": False, "build": False,
             "pressure_test": False, "operate": False, "drink": False},
            "physical authorization granted by an unverified assembly proposal")

    candidates = [
        {"part_number": row["part_number"], "accessory_id": row["id"],
         "evidence_tier": "manufacturer_family_listed",
         "exact_sku_fit_tier": "NOT_VERIFIED",
         "not_approved_for_purchase": True}
        for row in extras
    ]
    gates = [
        {"id": interface["id"],
         "endpoints": [interface["from"], interface["to"]],
         "function_requirements": interface["functional_requirements"],
         "open_parameters": interface["unknown_fields"],
         "required_evidence": interface["verification"],
         "review_state": "BLOCKED_PENDING_VENDOR_AND_PHYSICAL_MEASUREMENTS"}
        for interface in connections
    ]
    report = {
        "schema_version": "hardware_splicer.filter_assembly_preflight.v1",
        "project_id": source["project_id"],
        "source_spec_sha256": receipt["source_spec_sha256"],
        "technology_options_sha256": receipt["technology_options_sha256"],
        "component_reference_sha256": receipt["component_reference_sha256"],
        "assembly_source_sha256": sha(canonical(source)),
        "native_cad_evidence_sha256":
            sha((Path(root)/"RENDERED_CLEARANCE_EVIDENCE.json").read_bytes()),
        "component_receipt_sha256":
            sha((Path(root)/"COMPONENT_PACKAGE_RECEIPT.json").read_bytes()),
        "actual_native_clearance_meshes_checked": True,
        "accessory_candidates": candidates,
        "interface_evidence_gates": gates,
        "service_clearance": {
            "illustrative_vertical_allocation_mm": 458,
            "manufacturer_minimum_verified_mm": None,
            "sump_dismounting_work_space_verified": False,
            "bracket_hole_pitch_mm": None,
        },
        "hydraulic_pressure_at_target_flow_psi": None,
        "selected_operating_pressure_psi": None,
        "manufacturer_pressure_limit_is_not_operating_setpoint": True,
        "sku_specific_certification_verified": False,
        "validated_cartridge_housing_seat_fit": False,
        "verified_accessory_fit": False,
        "physical_water_test_executed": False,
        "physical_authority": source["physical_authority"],
        "outcome": "ASSEMBLY_DESIGN_BLOCKED_PENDING_EVIDENCE",
    }
    work = {
        "schema_version": "hardware_splicer.filter_assembly_measurement_plan.v1",
        "source_spec_sha256": report["source_spec_sha256"],
        "assembly_source_sha256": report["assembly_source_sha256"],
        "evidence_requests": [
            {"request_id": role["id"], "description": role["scope"],
             "status": "AWAITING_INDEPENDENT_EVIDENCE",
             "source_artefact": None,
             "measured_value": None,
             "instrument_and_calibration": None,
             "reviewer_approval": None}
            for role in roles
        ],
        "safe_next_step": "Obtain item-specific manufacturer fit/installation diagrams and actual rated bill of materials; no physical operations",
        "engineering_drawing_authorized": False,
        "fabrication_authorized": False,
        "pressurized_testing_authorized": False,
        "drinking_water_safety_established": False,
    }
    return report, work


def package_assembly(parts_root: Path, source_path: Path, out: Path) -> dict:
    source = json.loads(Path(source_path).read_text())
    report, work = verify_assembly(parts_root, source)
    out = Path(out)
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())),
            "refusing to overwrite existing assembly investigation")
    outputs = {
        "ASSEMBLY_SOURCE.json": canonical(source),
        "ASSEMBLY_GATE.json": canonical(report),
        "EVIDENCE_REQUESTS.json": canonical(work),
        "UPSTREAM_COMPONENT_RECEIPT.json":
            (Path(parts_root)/"COMPONENT_PACKAGE_RECEIPT.json").read_bytes(),
        "UPSTREAM_NATIVE_CAD_EVIDENCE.json":
            (Path(parts_root)/"RENDERED_CLEARANCE_EVIDENCE.json").read_bytes(),
    }
    out.mkdir(parents=True, exist_ok=True)
    for name, body in outputs.items():
        (out/name).write_bytes(body)
    receipt = {
        "schema_version": "hardware_splicer.filter_assembly_evidence_receipt.v1",
        "project_id": source["project_id"],
        "source_spec_sha256": report["source_spec_sha256"],
        "assembly_source_sha256": report["assembly_source_sha256"],
        "files": {name: {"sha256": sha(body), "bytes": len(body)}
                  for name, body in sorted(outputs.items())},
        "assembly_ready": False,
        "treatment_verified": False,
        "fabrication_authorized": False,
    }
    (out/"ASSEMBLY_RECEIPT.json").write_bytes(canonical(receipt))
    return receipt
