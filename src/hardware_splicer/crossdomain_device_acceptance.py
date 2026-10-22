"""Cross-domain software-level acceptance: verified KiCad PCB + native CAD shell.

This checks *actual source-derived* electronic board envelopes against a
SolidCraft STEP independently measured by FreeCAD. It is an open-shell
prototype, not a production enclosure. No output grants physical authority.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .reference_device_dossier import build_reference_device_dossier

SCHEMA = "hardware_splicer.crossdomain_device_acceptance.v1"
ENGINE_SCHEMA = "hardware_splicer.external_engine_execution.v1"
MAX_EVIDENCE = 32_000_000


def _read(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or symlinked engineering source: {path.name}")
    size = path.stat().st_size
    if not 0 < size <= MAX_EVIDENCE:
        raise ValueError(f"engineering evidence size invalid: {path.name}")
    return path.read_bytes()


def _json(path: Path) -> dict:
    data = json.loads(_read(path))
    if not isinstance(data, dict):
        raise ValueError(f"engineering source is not an object: {path.name}")
    return data


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("CAD dimensions must be finite numbers")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("CAD dimensions must be finite numbers")
    return result


def _point(value: Any) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("CAD profile points must be two-dimensional")
    return _number(value[0]), _number(value[1])


def _source_shell_geometry(recipe: Mapping[str, Any]) -> dict:
    """Accept only the explicit two-profile subtractive enclosure source.

    Validate CAD *intent* independently of the native STEP: hashes alone do
    not protect against a source that creates a filled block rather than an
    internal cavity.
    """
    commands = recipe.get("commands")
    if not isinstance(commands, list) or len(commands) != 8:
        raise ValueError("expected eight-command native open-shell recipe")
    names = [row.get("command") if isinstance(row, Mapping) else None for row in commands]
    if names != [
        "sketch.create", "sketch.rectangle.two_point", "sketch.finish",
        "solid.extrude", "sketch.create", "sketch.rectangle.two_point",
        "sketch.finish", "solid.extrude",
    ]:
        raise ValueError("unrecognized native CAD feature history")
    def p(i: int) -> dict:
        obj = commands[i].get("params")
        if not isinstance(obj, dict):
            raise ValueError("malformed native CAD command")
        return obj
    if p(0).get("plane") != "XY" or p(4).get("plane") != "XY":
        raise ValueError("CAD profiles must share XY orientation")
    if p(2) != {} or p(6) != {}:
        raise ValueError("CAD sketch completion was modified")
    base_offset = _number(p(4).get("offset"))
    outer_low, outer_high = _point(p(1).get("p0")), _point(p(1).get("p1"))
    inner_low, inner_high = _point(p(5).get("p0")), _point(p(5).get("p1"))
    height = _number(p(3).get("distance"))
    cut_height = _number(p(7).get("distance"))
    if p(3).get("operation") != "new" or p(7).get("operation") != "cut":
        raise ValueError("CAD source must explicitly subtract internal cavity")
    if (p(3).get("name") != "OuterShell" or p(7).get("name") != "OpenCavity"):
        raise ValueError("unrecognized CAD design operations")
    ow, od = outer_high[0] - outer_low[0], outer_high[1] - outer_low[1]
    iw, idep = inner_high[0] - inner_low[0], inner_high[1] - inner_low[1]
    if (min(ow, od, iw, idep, base_offset, height, cut_height) <= 0
            or cut_height != height - base_offset
            or not (outer_low[0] < inner_low[0] < inner_high[0] < outer_high[0])
            or not (outer_low[1] < inner_low[1] < inner_high[1] < outer_high[1])):
        raise ValueError("CAD cavity must be open at top and bounded by walls and floor")
    if abs((inner_low[0]+inner_high[0])-(outer_low[0]+outer_high[0])) > 1e-6:
        raise ValueError("off-center CAD cavity in X not supported")
    if abs((inner_low[1]+inner_high[1])-(outer_low[1]+outer_high[1])) > 1e-6:
        raise ValueError("off-center CAD cavity in Y not supported")
    return {
        "outer_dimensions_mm": [ow, od, height],
        "nominal_cavity_dimensions_mm": [iw, idep, cut_height],
        "wall_thickness_mm": [(ow-iw)/2, (od-idep)/2],
        "floor_thickness_mm": base_offset,
        "nominal_shell_material_volume_mm3": ow*od*height-iw*idep*cut_height,
        "cavity_geometry_basis": "native_script_extrude_subtract_to_open_top",
    }


def assess_crossdomain_reference(*, pcb_path: str | Path,
                                  receipt_path: str | Path,
                                  cad_recipe_path: str | Path,
                                  engine_output_dir: str | Path,
                                  output_dir: str | Path) -> dict:
    pcb_path, receipt_path = Path(pcb_path), Path(receipt_path)
    recipe_path, run_root = Path(cad_recipe_path), Path(engine_output_dir)
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError("cross-domain output directory must be empty")
    pcb_bytes = _read(pcb_path)
    receipt = _json(receipt_path)
    recipe_bytes = _read(recipe_path)
    geometry = _source_shell_geometry(json.loads(recipe_bytes))
    run = _json(run_root / "ENGINE_ORCHESTRATION_REPORT.json")

    if run.get("schema") != ENGINE_SCHEMA or run.get("blocked") != 0 or run.get("completed") != 2:
        raise ValueError("native cross-domain engine report did not complete both CAD stages")
    tasks = run.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 2 or [
        (row.get("id"), row.get("engine"), row.get("status"))
        for row in tasks if isinstance(row, Mapping)
    ] != [
        ("shell_cad", "solidcraft", "tool_passed_artifact_observed"),
        ("shell_inspection", "freecad", "tool_passed_artifact_observed"),
    ]:
        raise ValueError("incorrect native CAD provider task identity or state")
    if (tasks[0].get("source_sha256") != _sha(recipe_bytes)
            or any(tasks[i].get(k) is True for i in (0,1) for k in
                   ("fabrication_authorized","release_authorized","physical_validation_performed"))):
        raise ValueError("native source recipe lineage or authority mismatch")
    if any(run.get(key) is True for key in
           ("fabrication_authorized","power_on_authorized","release_authorized")):
        raise ValueError("external run claims physical authority")

    step = _read(run_root / "shell_cad" / "model.step")
    proof = _read(run_root / "shell_inspection" / "step_inspection.json")
    if not step.lstrip().startswith(b"ISO-10303-21;"):
        raise ValueError("native SolidCraft did not export a STEP model")
    expected_step_sha = _sha(step)
    expected_proof_sha = _sha(proof)
    def artifact_match(row: dict, sha: str) -> bool:
        return any(isinstance(a, Mapping) and a.get("sha256") == sha
                   for a in (row.get("artifacts") or []))
    if not artifact_match(tasks[0], expected_step_sha) or not artifact_match(tasks[1], expected_proof_sha):
        raise ValueError("native CAD artifacts do not match reported hashes")
    if tasks[1].get("source_sha256") != expected_step_sha:
        raise ValueError("FreeCAD input STEP is not SolidCraft's artifact")
    measured = json.loads(proof)
    if not isinstance(measured, dict) or measured.get("shape_valid") is not True:
        raise ValueError("FreeCAD did not report a valid shell")
    if type(measured.get("solid_count")) is not int or measured["solid_count"] != 1:
        raise ValueError("FreeCAD source needs exactly one physical shell solid")
    measured_box = measured.get("bbox_mm")
    if not isinstance(measured_box, list) or len(measured_box) != 3:
        raise ValueError("FreeCAD bounding box absent")
    if any(abs(_number(a)-b)>0.02 for a,b in zip(
        measured_box, geometry["outer_dimensions_mm"])):
        raise ValueError("native CAD bounding box contradicts source shell")
    if abs(_number(measured.get("volume_mm3")) -
           geometry["nominal_shell_material_volume_mm3"]) > 0.05:
        raise ValueError("native CAD does not contain modeled cavity volume")

    # A STEP with the right volume and bounds can still put the void in the
    # wrong place. Native FreeCAD point-in-solid probes prove that this *one*
    # generated shell has material in the floor/walls and emptiness at the
    # PCB cavity and open top, without claiming exact PCB-to-shell collision.
    topopath = run_root / "SHELL_TOPOLOGY.json"
    probe_bytes = _read(topopath)
    probe = json.loads(probe_bytes)
    expected_points = [
        ("floor_center_material", [55,35,1], True),
        ("left_wall_material", [1,35,12], True),
        ("rear_wall_material", [55,69,12], True),
        ("pcb_cavity_void", [55,35,12], False),
        ("top_opening_void", [55,35,24], False),
        ("outside_void", [125,80,12], False),
    ]
    if (not isinstance(probe, dict) or
            probe.get("schema") != "hardware_splicer.native_shell_topology.v1" or
            probe.get("source_step_sha256") != expected_step_sha or
            probe.get("engine") != "FreeCAD Part.Shape.isInside" or
            probe.get("shape_valid") is not True or
            probe.get("solid_count") != 1 or
            probe.get("all_samples_match") is not True or
            not isinstance(probe.get("samples"), list) or
            len(probe["samples"]) != len(expected_points)):
        raise ValueError("native cavity topology proof missing or invalid")
    for sample, (name, coords, expected) in zip(probe["samples"], expected_points):
        if (not isinstance(sample, Mapping) or
                sample.get("id") != name or sample.get("point_mm") != coords or
                sample.get("expected_material") is not expected or
                sample.get("actual_material") is not expected or
                sample.get("pass") is not True):
            raise ValueError("native cavity floor/wall/void probe failed")

    if receipt.get("result") != "pass" or receipt.get("authority",{}).get("fabrication_ready") is not False:
        raise ValueError("source KiCad verification receipt cannot support the device")
    if receipt.get("artifact_sha256", {}).get("pcb") != hashlib.sha256(pcb_bytes).hexdigest():
        raise ValueError("electrical KiCad PCB changed after original native verification")

    output.mkdir(parents=True, exist_ok=True)
    dossier = build_reference_device_dossier(
        pcb_path, output_dir=output / "electrical",
        declared_internal_enclosure_mm=dict(
            zip(("w","d","h"), geometry["nominal_cavity_dimensions_mm"])),
    )
    # Screen is in cavity-centered XY, board center at 0, and the physical
    # board is located above nominal 2 mm floor. Not a collision proof.
    # Translate the actual KiCad board into requirements for the next
    # mechanical revision. Hole geometry and connector positions are NOT
    # fixtures already present in this open shell.
    assembly_plan = _json(output / "electrical" / "REFERENCE_ASSEMBLY_PLAN.json")
    bounds = assembly_plan["board"]["outline"]["bbox"]
    center_x = (bounds["x0"] + bounds["x1"]) / 2
    center_y = (bounds["y0"] + bounds["y1"]) / 2
    mount_features = []
    access_features = []
    for item in assembly_plan["parts"]:
        if item["kind"] not in ("mounting_hole", "connector"):
            continue
        record = {
            "ref": item["ref"],
            "center_relative_to_pcb_mm": [
                round(item["x"] - center_x, 3),
                round(item["y"] - center_y, 3),
            ],
            "pcb_side": item["side"],
            "footprint": item["footprint"],
            "outline_source": item["outline_basis"],
        }
        if item["kind"] == "mounting_hole":
            record["fastener_sizing_verified"] = False
            record["aligned_shell_boss_present"] = False
            mount_features.append(record)
        elif not item["do_not_populate"]:
            record["connector_mating_direction_verified"] = False
            record["shell_cutout_present"] = False
            access_features.append(record)
    fit = dossier["electromechanical_fit"]
    if fit is None:
        raise ValueError("physical envelope screen unavailable")
    status = ("source_linked_envelope_clear_unverified"
              if fit["blocker_count"] == 0 else "blocked_interface_envelope")
    result = {
        "schema": SCHEMA,
        "device": "spi_flash_adapter_v1_with_open_shell",
        "status": status,
        "electrical": {
            "source_pcb_sha256": _sha(pcb_bytes),
            "historical_kicad_native_verification_bound": True,
            "native_erc_drc_reexecuted_in_this_run": False,
            "board_size_mm": dossier["board_size_mm"],
            "physical_component_candidate_footprints": 16,
            "nominal_power_domains_v": [3.3,1.8],
        },
        "mechanical": {
            "cad_recipe_sha256": _sha(recipe_bytes),
            "native_step_sha256": expected_step_sha,
            "freecad_report_sha256": expected_proof_sha,
            "native_freecad_geometry": measured,
            "native_shell_topology": {
                "source_step_sha256": probe["source_step_sha256"],
                "topology_report_sha256": _sha(probe_bytes),
                "point_samples_passed": len(expected_points),
                "engine": probe["engine"],
                "geometry_sampling_authority": "source_cavity_review_only",
            },
            "source_shell_model": geometry,
            "exact_connector_openings_verified": False,
            "mechanical_mounting_points_verified": False,
            "exact_3d_part_collision_verified": False,
        },
        "interface_screen": fit,
        "mechanical_feature_requirements": {
            "mounting_holes": mount_features,
            "fitted_connectors": access_features,
            "shell_bosses_generated": False,
            "connector_access_cutouts_generated": False,
            "positions_basis": "actual_kicad_board_relative_to_board_bbox_center",
        },
        "external_orchestration_plan_sha256": run.get("plan_sha256"),
        "open_gates": [
            "Open shell has no PCB mounting bosses, fasteners, connector cutouts, lid or strain relief",
            "Part heights are typical estimates, not manufacturer-authenticated 3D CAD",
            "Board placement, wall thickness and floor are modeled; physical enclosure dimensions unmeasured",
            "Connector accessibility, assembly sequence and all cabling remain unverified",
            "Independent EE review, revised manufacturer documentation and real continuity/rail/JEDEC-ID test outstanding",
        ],
        "engineering_package_authority": "candidate_for_independent_review_only",
        "physical_board_tested": False,
        "electrical_operation_verified": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "release_authorized": False,
    }
    (output / "MECHANICAL_FEATURE_REQUIREMENTS.json").write_text(
        json.dumps(result["mechanical_feature_requirements"], indent=2) + "\\n",
        encoding="utf-8",
    )
    (output / "CROSS_DOMAIN_DEVICE_ASSESSMENT.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8",
    )
    return result
