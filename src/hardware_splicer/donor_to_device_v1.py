"""Donor-to-device decision compiler over HS's existing splice and build engines.

This does NOT re-run donor AI, design circuits, select a supplier, or authorize
hardware. It joins *existing* RC toy salvage, an actual intake, and optional
KiCad splice outputs into one conservative source-bound build decision.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .device_splice_feasibility import assess_device_splice
from .donor_characterization_v1 import (
    create_donor_capture_template, evaluate_donor_capture,
)
from .real_device_work_package import compile_work_package

SCHEMA = "hardware_splicer.donor_to_device_review.v1"
MAX_BYTES = 3_000_000
ROVER_CASE = "robot_drive_from_rc_toy"
EXPECTED_BUILD = "robot_drive_base"


def _json_file(path: str | Path) -> tuple[dict, str]:
    file = Path(path)
    if not file.is_file() or file.is_symlink() or file.stat().st_size > MAX_BYTES:
        raise ValueError("missing, symlinked or oversized source: " + file.name)
    blob = file.read_bytes()
    if not blob:
        raise ValueError("empty source")
    data = json.loads(blob)
    if not isinstance(data, dict):
        raise ValueError("source JSON must be an object")
    return data, "sha256:" + hashlib.sha256(blob).hexdigest()


def _number(value: Any, *, name: str, allow_zero: bool = False) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero)):
        raise ValueError(f"{name} must be finite positive")
    return float(value)


def _source_evidence(source_name: str, sha: str) -> dict:
    # Fixture + intake are claims, not authenticated independent measurements.
    return {"id": source_name, "locator": sha,
            "basis": "user_declared"}


def _splice_compilation(result_path: str | Path | None, *, expected_case: str,
                        expected_build: str) -> dict:
    if result_path is None:
        return {
            "status": "not_run_in_this_review", "carrier_drc_pass": False,
            "carrier_artifact_sha256": None,
            "physically_built": False,
        }
    result, receipt_hash = _json_file(result_path)
    metrics, evaluation = result.get("metrics"), result.get("evaluation")
    if (result.get("schema_version") != "hardware_splicer.splice_demo_result.v1"
            or result.get("case_id") != expected_case
            or not isinstance(metrics, dict) or not isinstance(evaluation, dict)
            or metrics.get("build_id") != expected_build):
        raise ValueError("splice result not bound to selected donor case/build")
    # The splice demonstration may have other status flags. Treat the evaluator
    # result and DRC receipt as minimum requirements, never infer field proof.
    if not evaluation.get("passed") or not metrics.get("drc_pass"):
        return {"status": "blocked_compile_or_drc", "receipt_sha256": receipt_hash,
                "carrier_drc_pass": False, "carrier_artifact_sha256": None,
                "physically_built": False}
    # Bind the carrier PCB to this exact run if its demo output still exists.
    # This is a local source fingerprint, NOT an independent KiCad DRC rerun.
    artifacts = metrics.get("artifacts")
    board_location = artifacts.get("kicad_pcb") if isinstance(artifacts, dict) else None
    board_sha = None
    if isinstance(board_location, str) and board_location.endswith(".kicad_pcb"):
        root = Path(result_path).resolve().parent
        candidate = Path(board_location)
        candidate = (candidate if candidate.is_absolute() else root / candidate).resolve()
        if candidate.is_relative_to(root) and candidate.is_file() and not candidate.is_symlink():
            if 0 < candidate.stat().st_size <= 32_000_000:
                blob = candidate.read_bytes()
                if blob.lstrip().startswith(b"(kicad_pcb"):
                    board_sha = "sha256:" + hashlib.sha256(blob).hexdigest()
    # Reuse firmware/mechanical/bring-up artifacts already produced by HS.
    # Their identities are evidence of emitted candidate files, not validation
    # that they will work on an uncharacterized RC donor.
    emitted = {}
    if isinstance(artifacts, dict):
        root = Path(result_path).resolve().parent
        for name in ("firmware_scaffold", "mechanism_pack", "mechatronics_pack",
                     "mechatronics_authority", "bringup_card", "build_graph",
                     "bench_capture_template"):
            location = artifacts.get(name)
            if not isinstance(location, str) or not location.endswith(".json"):
                continue
            file = Path(location)
            file = (file if file.is_absolute() else root / file).resolve()
            if file.is_relative_to(root) and file.is_file() and not file.is_symlink():
                if 0 < file.stat().st_size <= MAX_BYTES:
                    emitted[name] = {
                        "sha256": "sha256:" + hashlib.sha256(file.read_bytes()).hexdigest(),
                        "validated_against_physical_donor": False,
                    }
    return {"status": ("source_bound_carrier_drc_reported" if board_sha
                       else "demo_drc_reported_artifact_unbound"),
            "receipt_sha256": receipt_hash,
            "carrier_drc_pass": True, "carrier_artifact_sha256": board_sha,
            "subsystem_artifacts": emitted,
            "native_kicad_receipt_independently_rechecked": False,
            "physically_built": False}


def build_donor_to_device_review(*, intake_path: str | Path,
                                 donor_fixture_path: str | Path,
                                 splice_result_path: str | Path | None = None,
                                 donor_capture_path: str | Path | None = None,
                                 output_dir: str | Path | None = None) -> dict:
    intake, intake_sha = _json_file(intake_path)
    donor, donor_sha = _json_file(donor_fixture_path)
    if (intake.get("salvage_mode") is not True
            or intake.get("circuit", {}).get("mode") != "circuit_board_system"):
        raise ValueError("expected donor-based circuit-splice intake")
    boards = intake["circuit"].get("boards") or []
    if (len(boards) != 1 or boards[0].get("board_id") != donor.get("board_id")
            or donor.get("schema_version") != "functional_salvage.v1"):
        raise ValueError("donor fixture identity differs from intake board")
    inventory = intake.get("available_parts")
    if not isinstance(inventory, list) or not inventory:
        raise ValueError("nonempty donor inventory required")
    motors = [p for p in inventory if p.get("type") == "dc_motor"]
    controllers = [p for p in inventory if p.get("type") == "microcontroller"]
    if len(motors) != 2 or len(controllers) != 1:
        raise ValueError("this reference case needs two identified motors and one controller")
    voltage = _number(intake["constraints"]["battery_voltage_v"], name="declared_battery_voltage")
    capacity = _number(intake["constraints"]["battery_capacity_mah"], name="declared_battery_capacity")
    left, right = motors
    ratings = []
    for i, row in enumerate(motors):
        running = _number(row.get("current_a"), name="declared_motor_running_current")
        stall = _number(row.get("stall_current_a"), name="declared_motor_stall_current")
        rated = _number(row.get("voltage_v"), name="declared_motor_voltage")
        if stall < running:
            raise ValueError("declared motor stall current below normal running current")
        ratings.append({"id":f"motor_{i+1}", "rated_v": rated,
                        "running_a": running, "stall_a": stall})
    blocks = donor.get("reusable_blocks") or []
    unique_ids = [r.get("block_id") for r in blocks if isinstance(r, Mapping)]
    if len(unique_ids) != len(blocks) or len(set(unique_ids)) != len(unique_ids):
        raise ValueError("ambiguous donor functional block identities")
    kinds = {r.get("function_type"): r for r in blocks}
    for needed in ("actuator_driver", "mechanical_motion", "power_regulation"):
        if needed not in kinds:
            raise ValueError("donor fixture missing a required functional group")
    driver = kinds["actuator_driver"]
    if driver.get("extractability", {}).get("class") != "connector_reuse":
        raise ValueError("unsafe or unverified donor drive extraction method")
    if kinds["power_regulation"].get("extractability", {}).get("class") != "board_section_cut_candidate":
        raise ValueError("donor power section incorrectly presented as a qualified reuse")
    if any(g.get("status") == "closed" for g in donor.get("evidence_gates", [])):
        raise ValueError("fixtures must not claim physical measurements are completed")
    if len(driver.get("connector_refs") or []) < 2:
        raise ValueError("motor driver harness identity not traceable")

    evidence = [_source_evidence("intake_claims", intake_sha),
                _source_evidence("donor_functional_fixture_claims", donor_sha)]
    component_ids = ["battery", "donor_driver", "left_motor", "right_motor",
                     "controller", "frame", "sensor"]
    splice = {
        "schema":"hardware_splicer.device_splice_candidate.v1",
        "id": ROVER_CASE, "components":[{"id":x} for x in component_ids],
        "evidence": evidence,
        "required_domains":["power", "signal", "mechanical", "firmware", "thermal", "assembly"],
        "interfaces":[
            # Only the voltage claim is known for battery supply. Continuous and
            # peak driver input ratings, safe regulator and chemistry are NOT known.
            {"id":"battery_driver_power","domain":"power","from":"battery","to":"donor_driver",
             "provided":{"voltage_min_v":voltage,"voltage_max_v":voltage},
             "required":{},"evidence_refs":["intake_claims","donor_functional_fixture_claims"]},
            *[
                {"id":name+"_motor_power","domain":"power","from":"donor_driver","to":name+"_motor",
                 "provided":{},
                 "required":{"voltage_min_v":entry["rated_v"],
                             "voltage_max_v":entry["rated_v"],
                             "current_required_a":entry["stall_a"]},
                 "evidence_refs":["intake_claims","donor_functional_fixture_claims"]}
                for name,entry in zip(("left","right"),ratings)
            ],
            {"id":"esp32_driver_control","domain":"signal","from":"controller","to":"donor_driver",
             "provided":{"logic_voltage_v":3.3},"required":{},
             "evidence_refs":["intake_claims","donor_functional_fixture_claims"]},
            {"id":"drivetrain_mount","domain":"mechanical","from":"left_motor","to":"frame",
             "provided":{},"required":{},"evidence_refs":["intake_claims"]},
            {"id":"motor_control_firmware","domain":"firmware","from":"controller","to":"donor_driver",
             "provided":{},"required":{"driver_available":None},"evidence_refs":["intake_claims"]},
            {"id":"driver_cooling","domain":"thermal","from":"donor_driver","to":"frame",
             "provided":{},"required":{},"evidence_refs":["donor_functional_fixture_claims"]},
        ],
    }
    feasible = assess_device_splice(splice)
    # The source's motor current is an intake claim, not a measurement; it is
    # dangerous to call it proof of motor-driver compatibility or battery sizing.
    aggregate = sum(x["stall_a"] for x in ratings)
    running_total = sum(x["running_a"] for x in ratings)
    running_w = sum(x["running_a"] * x["rated_v"] for x in ratings)
    direct_voltage_violation = any(voltage > x["rated_v"] + 1e-9 for x in ratings)
    reuse = [
        {"source_block_id": driver["block_id"], "action":"conditional_harness_reuse",
         "authority":"fixture_claim_not_bench_validated",
         "gate":"Measure driver supply/current ratings and full pinout; retain intact harness"},
        {"source_block_id": kinds["mechanical_motion"]["block_id"],
         "action":"conditional_motor_reuse",
         "authority":"intake_motor_ratings_are_unverified",
         "gate":"Measure both motor resistances, no-load current, stall current and shaft size"},
        {"source_block_id": kinds["power_regulation"]["block_id"],
         "action":"do_not_cut_or_reuse_yet",
         "authority":"layout_and_power_chemistry_unknown",
         "gate":"Independently validate fuse, reverse polarity, isolation and rail continuity"},
    ]
    bench_gates = [
        {"id":"donor_rail","kind":"measurement","state":"open",
         "criterion":"Instrument-confirm donor supply voltage, current limit, battery chemistry and polarity"},
        {"id":"motor_pair","kind":"measurement","state":"open",
         "criterion":"Measure each motor's voltage, no-load and stall current; check winding resistance and gearbox condition"},
        {"id":"driver_thermal","kind":"source_and_bench","state":"open",
         "criterion":"Identify H-bridge part/revision; prove two-channel peak/continuous limits, logic voltage and thermal margin"},
        {"id":"regulation","kind":"engineering","state":"open",
         "criterion":"Design a documented protected motor rail; NEVER connect declared 7.4 V directly to unverified 6 V motors"},
        {"id":"mechanical","kind":"caliper_and_cad","state":"open",
         "criterion":"Measure wheel diameter, axle spacing, gearbox mounts and chassis dimensions; native CAD test-fit required"},
        {"id":"firmware","kind":"software_and_supervised_bench","state":"open",
         "criterion":"Verify driver pin map, isolated ESP32 programming, safe startup, E-stop and command timeout"},
        {"id":"system","kind":"physical_bench","state":"open",
         "criterion":"Only after earlier gates: current-limited restrained-wheel spin, directional test and controlled low-speed trial"},
    ]
    missing = [
        {"category":"protected_motor_rail","specification":"rated motor rail, fuse and protective conversion/limits",
         "verified_mpn":None, "unit_price_ntd":None},
        {"category":"power_distribution","specification":"separate regulated 3.3 V logic and motor grounds",
         "verified_mpn":None, "unit_price_ntd":None},
        {"category":"controller_harness","specification":"known pinmap and independently authenticated compatible connectors",
         "verified_mpn":None, "unit_price_ntd":None},
        {"category":"mounting_and_chassis","specification":"geometry measured from donor and source-derived mounting fittings",
         "verified_mpn":None, "unit_price_ntd":None},
        {"category":"safety_control","specification":"physical enable/e-stop and bounded motor commands",
         "verified_mpn":None, "unit_price_ntd":None},
    ]
    characterization = (
        evaluate_donor_capture(
            capture_path=donor_capture_path, intake_sha256=intake_sha,
            fixture_sha256=donor_sha, board_id=donor["board_id"],
            declared_motor_rated_v={
                "left":ratings[0]["rated_v"], "right":ratings[1]["rated_v"],
            },
        ) if donor_capture_path is not None else None
    )
    capture_template = create_donor_capture_template(
        intake_sha256=intake_sha, fixture_sha256=donor_sha,
        donor_board_id=donor["board_id"],
    )
    compile_evidence = _splice_compilation(splice_result_path, expected_case=ROVER_CASE,
                                            expected_build=EXPECTED_BUILD)
    case = {
        "id":ROVER_CASE,"device":"RC donor to supervised low-speed rover",
        "kind":"new_build",
        "deliverables":["donor reuse decision", "carrier schematic and KiCad DRC",
                        "motor and driver power calculation", "measured geometry and CAD",
                        "firmware safety contract", "priced source-backed BOM", "bench records"],
        "acceptance":[g["criterion"] for g in bench_gates],
    }
    review = {"operator_casefile":{
        "build_or_repair_sequence":[
            "Photograph and document donor hardware; preserve intact motor harness",
            "Complete donor and interface measurements before modifying power paths",
            "Verify the existing HS robot_drive_from_rc_toy splice/carrier build independently",
            "Produce measured-dimension mounts with SolidCraft/FreeCAD, not invented dimensions",
            "Independently approve protection, firmware and wiring before supervised motor motion",
        ],
        "critical_technical_unknowns":[g["criterion"] for g in bench_gates],
        "compatible_parts_or_requirements":[x["specification"] for x in missing],
    }}
    handoff = compile_work_package(case, review, splice_candidate=splice)
    if characterization is not None:
        handoff["physical_donor_evidence"] = {
            "review_status": characterization["status"],
            "capture_sha256": characterization["source_capture_sha256"],
            "specific_donor_id": characterization["physical_donor_id"],
            "operator_reported_readings": characterization["input_fields_observed"],
            "unqualified_readings": characterization["unqualified_readings"],
            "identified_conflicts": characterization["conflicts"],
            "independently_authenticated": False,
            "build_authorized": False,
        }
        for conflict in characterization["conflicts"]:
            description = conflict["action"]
            handoff["work_steps"].append({
                "id":f"step-{len(handoff['work_steps'])+1:02d}",
                "instruction":description,
                "status":"proposed_not_executed",
                "evidence_refs":[characterization["source_capture_sha256"]],
                "source_domain":"donor_characterization",
            })
            handoff["critical_unknowns"].append({
                "id":f"gap-{len(handoff['critical_unknowns'])+1:02d}",
                "description":f"Review reported physical donor conflict: {conflict['id']}",
                "status":"open","resolution_evidence":None,
            })
    report = {
        "schema":SCHEMA, "case_id":ROVER_CASE,"target_build_id":EXPECTED_BUILD,
        "status":"blocked_until_donor_characterization",
        "source": {"intake_sha256":intake_sha,"donor_fixture_sha256":donor_sha,
                   "fixture_is_measured_physical_donor":False},
        "donor_inventory_count":len(inventory),
        "reuse_actions":reuse,
        "electrical": {
            "driver_design_requirements_from_unverified_intake": {
                "required_motor_channels": 2,
                "declared_motor_rail_target_v": max(x["rated_v"] for x in ratings),
                "declared_per_channel_stall_current_min_a": max(x["stall_a"] for x in ratings),
                "declared_combined_stall_current_min_a": round(aggregate, 5),
                "minimum_actual_component_rating_verified": False,
                "needs_confirmed_peak_surge_thermal_margin": True,
                "needs_safe_logic_level_and_braking_protocol": True,
            },
            "nominal_battery_claim_v":voltage,"battery_capacity_claim_mah":capacity,
            "two_motor_running_current_claim_a":round(running_total,5),
            "two_motor_stall_current_claim_a":round(aggregate,5),
            "two_motor_running_electrical_load_claim_w":round(running_w,5),
            "direct_battery_to_motor_voltage_mismatch":direct_voltage_violation,
            "hbridge_peak_current_rating_known":False,
            "motor_drive_rail_verified":False,
            "logic_signal_compatibility_verified":False,
            "aggregated_motor_stall_rating_authentic":False,
        },
        "splice_feasibility":feasible,
        "carrier_compilation":compile_evidence,
        "physical_donor_characterization":characterization,
        "physical_capture_template_schema":"bench_topology_capture.v1",
        "engineering_modules": {
            "electrical":"existing_circuit_ai_salvage_and_kicad_carrier_compile",
            "mechanical":"solidcraft_freecad_requires_actual_donor_dimensions",
            "firmware":"unimplemented_pinmap_and_safety_evidence",
            "economic":"cost_model_requires_real_quotes_and_validated_yield",
        },
        "mechanical_inputs":{
            "wheel_diameter_mm":None, "axle_spacing_mm":None,
            "motor_shaft_and_mount_mm":None,"chassis_envelope_mm":None,
            "operator_reported_geometry":({
                key: dict(item)
                for key,item in characterization["accepted_readings"].items()
                if item["domain"] == "mechanical"
            } if characterization else {}),
            "cad_model_generated":False,
        },
        "missing_components_and_sourcing":missing,
        "estimated_replacement_cost_ntd":None,
        "estimated_resale_value_ntd":None,
        "profitability_verdict":"cannot_evaluate_without_verified_costs_and_yield",
        "acceptance_gates":bench_gates,
        "device_work_package":handoff,
        "physical_build_complete":False,"power_on_authorized":False,
        "motor_motion_authorized":False,"fabrication_authorized":False,
        "release_authorized":False,
    }
    if output_dir is not None:
        out = Path(output_dir)
        if out.exists() and any(out.iterdir()):
            raise ValueError("output directory must be empty")
        out.mkdir(parents=True,exist_ok=True)
        for name,data in (
            ("DONOR_DEVICE_REVIEW.json",report),
            ("DONOR_DEVICE_WORK_PACKAGE.json",handoff),
            ("DONOR_EVIDENCE_GATES.json",{"gates":bench_gates,"all_closed":False}),
            ("DONOR_CAPTURE_TEMPLATE.json",capture_template),
            *(([("DONOR_CAPTURE_AUDIT.json",characterization)]
               if characterization is not None else [])),
        ):
            (out/name).write_text(json.dumps(data,indent=2,allow_nan=False)+"\n",encoding="utf-8")
        summary = [
            "# RC toy → rover | source-bound donor-to-device review",
            "",
            "**Engineering status: BLOCKED until donor measurements and qualified components.**",
            "",
            f"Intake SHA-256: `{intake_sha}`",
            f"Donor fixture SHA-256: `{donor_sha}`",
            "",
            "## Existing HS subsystem reuse",
            "- Circuit-AI functional block extraction is retained; candidate H-bridge/motor harness must be measured.",
            "- HS already has a robot_drive_base carrier demonstration; do not confuse DRC with hardware acceptance.",
            "- Native SolidCraft/FreeCAD are available as optional specialist tools only when real dimensions exist.",
            "",
            "## Declared intake figures, NOT independently measured",
            f"- Battery: {voltage:g} V nominal claim; capacity: {capacity:g} mAh claim.",
            f"- Two motors: {running_total:g} A combined nominal current; {aggregate:g} A combined declared stall current.",
            f"- Direct battery-to-6V motor wiring mismatch: {direct_voltage_violation}.",
            "",
            "## Stop rules",
            *[f"- {x['criterion']}" for x in bench_gates],
            "",
            "## Current artifact status",
            f"- Carrier compile: {compile_evidence['status']}",
            "- Native CAD: blocked for missing true donor dimensions.",
            "- Pricing/market value: not estimated; missing qualified MPN/quotes.",
            "- Real physical assembly: not performed.",
            "- Physical donor capture: " + (
                characterization["status"] if characterization else "not_supplied"
            ),
            "- Operator-provided readings remain review-only and do not close independent physical gates.",
        ]
        (out/"DONOR_DEVICE_README.md").write_text("\n".join(summary)+"\n",encoding="utf-8")
    return report
