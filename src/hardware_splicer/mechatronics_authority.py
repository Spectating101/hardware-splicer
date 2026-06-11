from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .mechanical_authority import build_mechanical_authority
from .robotics_actuation import build_robotics_actuation_packet


SCHEMA_VERSION = "hardware_splicer.mechatronics_authority.v1"

STAGE_SCORES = {
    "system_intake": 0.14,
    "electrical_circuit_authority": 0.34,
    "mechanical_robotics_authority": 0.58,
    "packaging_authority": 0.76,
    "integrated_bench_authority": 0.91,
    "production_mechatronics_release": 1.00,
}

MECHANISM_KEYS = [
    "enclosure",
    "bracket",
    "servo_mount",
    "linear_axis",
    "leadscrew_axis",
    "rotary_joint",
    "belt_reduction",
    "drive_base",
    "gripper",
    "pan_tilt",
    "assembly",
]


def build_mechatronics_authority(
    payload: Mapping[str, Any] | Any,
    *,
    engineering: Mapping[str, Any] | None = None,
    mechanical_authority: Mapping[str, Any] | None = None,
    robotics_actuation: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Aggregate subsystem evidence into Hardware-Splicer's final product authority."""

    body = _to_dict(payload)
    engineering_body = _to_dict(engineering or {})
    mechanical = _to_dict(mechanical_authority or build_mechanical_authority(body, engineering=engineering_body))
    robotics = _to_dict(robotics_actuation or build_robotics_actuation_packet(body, engineering=engineering_body))
    electrical = _electrical_status(body, engineering_body)
    packaging = _packaging_status(body, engineering_body)
    release = _release_status(body)
    bench = _integrated_bench_status(body, mechanical, robotics)
    integration_trace = _integration_trace(body, engineering_body, mechanical, robotics, electrical, packaging, bench, release)

    stages = _stages(
        body=body,
        electrical=electrical,
        mechanical=mechanical,
        robotics=robotics,
        packaging=packaging,
        bench=bench,
        release=release,
        integration_trace=integration_trace,
    )
    current_level = _current_level(stages)
    score = STAGE_SCORES.get(current_level, 0.0) if current_level else 0.0
    production_authorized = current_level == "production_mechatronics_release"

    return {
        "schema_version": SCHEMA_VERSION,
        "current_authority_level": current_level or "no_mechatronics_authority",
        "authority_score": round(score, 2),
        "production_authorized": production_authorized,
        "release_decision": "authorized_scoped_mechatronics_release" if production_authorized else "evidence_required_before_system_release",
        "next_action_id": _next_action_id(stages),
        "stages": stages,
        "subsystems": {
            "circuit": electrical,
            "mechanical": _subsystem_summary(mechanical),
            "robotics": _subsystem_summary(robotics),
            "packaging": packaging,
        },
        "integration_trace": integration_trace,
        "can": _capabilities(stages),
        "claim_boundary": _claim_boundary(current_level),
        "scope_limits": _scope_limits(body, release, mechanical, robotics),
        "release_status": release,
        "next_engineering_actions": _next_engineering_actions(stages, electrical, packaging, mechanical, robotics),
    }


def _stages(
    *,
    body: Dict[str, Any],
    electrical: Dict[str, Any],
    mechanical: Dict[str, Any],
    robotics: Dict[str, Any],
    packaging: Dict[str, Any],
    bench: Dict[str, Any],
    release: Dict[str, Any],
    integration_trace: Dict[str, Any],
) -> List[Dict[str, Any]]:
    stages: List[Dict[str, Any]] = []

    has_machine = bool(_list_dicts(_dict(body.get("machine")).get("boards")))
    has_mechanism = bool(_dict(body.get("mechanism")))
    _stage(
        stages,
        "system_intake",
        has_machine and has_mechanism,
        [] if has_machine and has_mechanism else ["Hardware-Splicer needs both machine/circuit context and mechanism/package context."],
        "Close electrical circuit authority from Circuit-AI and system simulation.",
    )

    _stage(
        stages,
        "electrical_circuit_authority",
        _passed(stages, "system_intake") and electrical["authorized_for_integration"],
        electrical["blockers"],
        "Close mechanical, robotics, load, and motion authority.",
    )

    mechanical_ready = _authority_at_least(mechanical, "controlled_bench_fit", mechanical_order=True)
    robotics_needed = int((robotics.get("actuation_profile") or {}).get("actuator_count") or 0) > 0 or int((robotics.get("actuation_profile") or {}).get("spring_count") or 0) > 0
    robotics_ready = (not robotics_needed) or _authority_at_least(robotics, "controlled_motion_verified", robotics_order=True)
    mech_robotics_blockers: List[str] = []
    if not mechanical_ready:
        mech_robotics_blockers.append(f"Mechanical authority is only {mechanical.get('current_authority_level')}.")
    if not robotics_ready:
        mech_robotics_blockers.append(f"Robotics actuation authority is only {robotics.get('current_authority_level')}.")
    _stage(
        stages,
        "mechanical_robotics_authority",
        _passed(stages, "electrical_circuit_authority") and mechanical_ready and robotics_ready,
        mech_robotics_blockers,
        "Close packaging/casing authority through Mecha-Splicer and 3D-Splicer artifacts.",
    )

    _stage(
        stages,
        "packaging_authority",
        _passed(stages, "mechanical_robotics_authority") and packaging["packaging_ready"],
        packaging["blockers"],
        "Run integrated electrical + mechanical + packaging bench evidence.",
    )

    _stage(
        stages,
        "integrated_bench_authority",
        _passed(stages, "packaging_authority") and bench["integrated_bench_ready"],
        bench["blockers"],
        "Attach reviewed Hardware-Splicer release scope and artifact bundle.",
    )

    trace_gaps = _string_list(integration_trace.get("open_gaps"))
    _stage(
        stages,
        "production_mechatronics_release",
        _passed(stages, "integrated_bench_authority") and release["release_ready"] and electrical["release_ready"] and not trace_gaps,
        release["blockers"]
        + ([] if electrical["release_ready"] else ["Circuit/electrical subsystem release is not closed."])
        + trace_gaps,
        "No remaining action for this scoped Hardware-Splicer release.",
    )
    return stages


def _electrical_status(body: Dict[str, Any], engineering: Dict[str, Any]) -> Dict[str, Any]:
    machine = _dict(body.get("machine"))
    boards = _list_dicts(machine.get("boards"))
    board_design_files = _dict(body.get("board_design_files"))
    circuit_authority = _dict(body.get("circuit_authority"))
    circuit_release = _first_dict(body.get("circuit_release"), body.get("electrical_release"))
    analysis = _dict(engineering.get("analysis"))
    compiled = _dict(engineering.get("compiled"))

    blockers: List[str] = []
    warnings: List[str] = []
    for section in ["power", "interconnects", "control_coupling"]:
        for issue in _list_dicts(_dict(analysis.get(section)).get("issues")):
            severity = str(issue.get("severity") or "").lower()
            message = str(issue.get("message") or issue.get("topic") or f"{section} issue")
            if severity in {"error", "block", "critical"}:
                blockers.append(message)
            elif severity in {"warning", "warn"}:
                warnings.append(message)

    if not boards:
        blockers.append("No machine boards are defined.")
    missing_requirements = [str(row.get("board_id") or index) for index, row in enumerate(boards) if not isinstance(row.get("requirements"), dict)]
    if missing_requirements:
        warnings.append(f"Board requirements are missing for: {', '.join(missing_requirements)}.")
    if not board_design_files:
        warnings.append("No board design files are attached; Circuit-AI evidence is structural/spec-level only.")

    compiled_machine = _dict(compiled.get("machine"))
    readiness = str(compiled_machine.get("readiness_level") or "").lower()
    if readiness in {"draft", ""}:
        warnings.append("Circuit compile readiness is draft/reviewable, not manufacturable.")

    build_compilation = _dict(engineering.get("build_compilation"))
    compiler_quality = _dict(build_compilation.get("design_quality"))
    compiler_verified = bool(
        compiler_quality.get("fabrication_ready")
        or (compiler_quality.get("build_ready") and compiler_quality.get("drc_pass"))
    )

    release_blockers = []
    if circuit_authority.get("production_authorized") is True:
        release_ready = True
    elif compiler_verified and board_design_files and not blockers:
        release_ready = True
    elif circuit_release and circuit_release.get("compiler_verified") and not blockers:
        release_ready = True
    else:
        if not circuit_release:
            release_blockers.append("Attach circuit_release or Circuit-AI production authority evidence.")
        if circuit_release and not str(circuit_release.get("scope_statement") or "").strip():
            release_blockers.append("Circuit release needs a scope_statement.")
        if circuit_release and not bool(circuit_release.get("acceptance_reviewed")):
            release_blockers.append("Circuit release acceptance must be reviewed.")
        if circuit_release and _artifact_count(circuit_release) < 1:
            release_blockers.append("Circuit release needs artifact_uris or equivalent Circuit-AI evidence references.")
        release_ready = bool(circuit_release and not release_blockers)

    return {
        "authorized_for_integration": bool(boards) and not blockers,
        "release_ready": release_ready,
        "release_blockers": release_blockers,
        "board_count": len(boards),
        "board_design_file_count": len(board_design_files),
        "circuit_authority_level": circuit_authority.get("current_authority_level"),
        "readiness": readiness or "unknown",
        "blockers": _dedupe_strings(blockers),
        "warnings": _dedupe_strings(warnings),
    }


def _packaging_status(body: Dict[str, Any], engineering: Dict[str, Any]) -> Dict[str, Any]:
    mechanism = _dict(_dict(engineering.get("analysis")).get("mechanism"))
    mechanism_spec = _dict(body.get("mechanism"))
    mechanism_bundle = _load_mecha_bundle(mechanism)
    physical_assembly = _dict(mechanism.get("physical_assembly"))
    kicad_step_assembly = _dict(mechanism.get("kicad_step_assembly"))
    blockers: List[str] = []
    warnings: List[str] = []

    bundle_file = str(mechanism.get("bundle_file") or "").strip()
    if not bundle_file:
        blockers.append("Mecha-Splicer bundle_file is missing.")

    outputs = _string_list(mechanism.get("outputs")) or _string_list(mechanism_bundle.get("outputs"))
    if not outputs:
        warnings.append("No generated packaging/mechanical output list was returned.")

    if bool(body.get("use_3d_splicer", True)) and mechanism_spec:
        splicer3d = _dict(mechanism.get("splicer3d"))
        if not (
            splicer3d.get("ok") is True
            or splicer3d.get("success") is True
            or str(splicer3d.get("script") or "").strip()
            or str(splicer3d.get("stl_path") or "").strip()
        ):
            blockers.append("3D-Splicer did not return a usable script/STL packaging artifact.")

    for issue in _list_dicts(mechanism.get("dfm")) or _list_dicts(mechanism_bundle.get("dfm")):
        if str(issue.get("severity") or "").lower() in {"block", "error", "critical"}:
            blockers.append(str(issue.get("message") or "Packaging DFM blocker."))

    physical_ready = bool(physical_assembly.get("assembly_ready"))
    physical_blockers = _string_list(physical_assembly.get("blockers"))
    if mechanism_spec and physical_assembly and not physical_ready:
        blockers.extend("Physical assembly: " + row for row in physical_blockers)
    if mechanism_spec and not physical_assembly:
        warnings.append("No physical assembly map was generated for board/package/mechanism spatial integration.")

    kicad_step_ready = bool(kicad_step_assembly.get("assembly_ready"))
    kicad_step_blockers = _string_list(kicad_step_assembly.get("blockers"))
    kicad_step_warnings = _string_list(kicad_step_assembly.get("warnings"))
    if mechanism_spec and kicad_step_assembly and not kicad_step_ready:
        blockers.extend("KiCad/STEP assembly: " + row for row in kicad_step_blockers)
    if mechanism_spec and kicad_step_assembly:
        warnings.extend("KiCad/STEP assembly: " + row for row in kicad_step_warnings)
    if mechanism_spec and not kicad_step_assembly:
        warnings.append("No KiCad/STEP-level assembly package was generated for board/package/mechanism fit review.")

    return {
        "packaging_ready": not blockers and bool(bundle_file),
        "mecha_bundle_file": bundle_file,
        "generated_output_count": len(outputs),
        "splicer3d_used": bool(body.get("use_3d_splicer", True)) and bool(mechanism_spec),
        "physical_assembly_ready": physical_ready,
        "physical_assembly_artifact_count": _artifact_count(physical_assembly),
        "physical_assembly_check_count": len(_list_dicts(physical_assembly.get("clearance_checks"))),
        "kicad_step_assembly_ready": kicad_step_ready,
        "kicad_step_assembly_mode": kicad_step_assembly.get("mode"),
        "kicad_step_assembly_source_precision": kicad_step_assembly.get("source_precision"),
        "kicad_step_assembly_artifact_count": _artifact_count(kicad_step_assembly),
        "kicad_step_assembly_check_count": len(_list_dicts(kicad_step_assembly.get("checks"))),
        "blockers": _dedupe_strings(blockers),
        "warnings": _dedupe_strings(warnings),
    }


def _integrated_bench_status(body: Dict[str, Any], mechanical: Dict[str, Any], robotics: Dict[str, Any]) -> Dict[str, Any]:
    capture = _first_dict(body.get("integrated_bench_capture"), body.get("hardware_bench_capture"), body.get("system_bench_capture"))
    rows = []
    for key in ["tests", "electrical_tests", "motion_tests", "packaging_tests", "thermal_tests", "cycle_tests"]:
        rows.extend(_list_dicts(capture.get(key)))
    passed = [row for row in rows if _row_passed(row)]
    failed = [row for row in rows if _row_failed(row)]
    artifacts = _artifact_count(capture)
    explicit = bool(capture.get("integrated_bench_ready") is True or capture.get("system_verified") is True)

    blockers: List[str] = []
    if not capture:
        blockers.append("Run integrated bench evidence across circuit power, actuation motion, and packaging fit.")
    if failed:
        blockers.extend(str(row.get("message") or row.get("target") or "integrated bench failure") for row in failed)
    if len(passed) < 3 and not explicit:
        blockers.append("Record at least three passing integrated electrical, motion, packaging, thermal, or cycle checks.")
    if artifacts < 1 and not explicit:
        blockers.append("Attach integrated bench artifacts, logs, photos, or videos.")

    mechanical_release = mechanical.get("production_authorized") is True
    robotics_release = robotics.get("production_authorized") is True or int((robotics.get("actuation_profile") or {}).get("actuator_count") or 0) == 0
    if not mechanical_release:
        blockers.append("Mechanical subsystem release is not closed.")
    if not robotics_release:
        blockers.append("Robotics actuation subsystem release is not closed.")

    return {
        "available": bool(capture),
        "passed_test_count": len(passed),
        "failed_test_count": len(failed),
        "artifact_count": artifacts,
        "integrated_bench_ready": bool((explicit or (len(passed) >= 3 and artifacts >= 1 and not failed)) and mechanical_release and robotics_release),
        "blockers": _dedupe_strings(blockers),
    }


def _release_status(body: Dict[str, Any]) -> Dict[str, Any]:
    release = _first_dict(body.get("mechatronics_release"), body.get("hardware_release"), body.get("system_release"))
    blockers = []
    if not release:
        blockers.append("Attach mechatronics_release with Hardware-Splicer scope, artifact URIs, and acceptance review.")
    if release and not str(release.get("scope_statement") or "").strip():
        blockers.append("Hardware-Splicer release needs a scope_statement.")
    if release and not bool(release.get("acceptance_reviewed")):
        blockers.append("Hardware-Splicer release acceptance must be reviewed.")
    if release and _artifact_count(release) < 1:
        blockers.append("Hardware-Splicer release needs artifact_uris or equivalent evidence references.")
    return {
        "available": bool(release),
        "release_ready": bool(release and not blockers),
        "scope_statement": str(release.get("scope_statement") or "").strip(),
        "blockers": blockers,
    }


def _integration_trace(
    body: Dict[str, Any],
    engineering: Dict[str, Any],
    mechanical: Dict[str, Any],
    robotics: Dict[str, Any],
    electrical: Dict[str, Any],
    packaging: Dict[str, Any],
    bench: Dict[str, Any],
    release: Dict[str, Any],
) -> Dict[str, Any]:
    analysis = _dict(engineering.get("analysis"))
    mechanism_analysis = _dict(analysis.get("mechanism"))
    mechanism_spec = _dict(body.get("mechanism"))
    mechanism_bundle = _load_mecha_bundle(mechanism_analysis)
    outputs = _string_list(mechanism_analysis.get("outputs")) or _string_list(mechanism_bundle.get("outputs"))
    dfm_rows = _list_dicts(mechanism_analysis.get("dfm")) or _list_dicts(mechanism_bundle.get("dfm"))
    simulation_rows = (_list_dicts(mechanism_analysis.get("simulation")) or _list_dicts(mechanism_bundle.get("simulation"))) + _simulation_rows_from_body(body)
    safety_rows = _list_dicts(mechanism_analysis.get("safety")) or _list_dicts(mechanism_bundle.get("safety"))
    parts = _list_dicts(mechanism_bundle.get("parts")) + _list_dicts(mechanism_analysis.get("parts"))
    control = _dict(analysis.get("control_coupling"))
    power = _dict(analysis.get("power"))
    actuation_profile = _dict(robotics.get("actuation_profile"))
    actuators = _list_dicts(actuation_profile.get("actuators"))
    springs = _list_dicts(actuation_profile.get("springs"))
    sensors = _list_dicts(actuation_profile.get("sensors"))
    drive_requirements = _dict(robotics.get("drive_requirements"))

    primitive_rows = _mechanism_chain_rows(
        mechanism_spec=mechanism_spec,
        outputs=outputs,
        parts=parts,
        simulation_rows=simulation_rows,
        dfm_rows=dfm_rows,
        safety_rows=safety_rows,
        actuators=actuators,
        springs=springs,
        sensors=sensors,
        body=body,
    )
    orphan_actuators = _orphan_actuators(actuators, primitive_rows)
    layer_closure = {
        "system_intake_ready": bool(_list_dicts(_dict(body.get("machine")).get("boards")) and mechanism_spec),
        "electrical_integration_ready": bool(electrical.get("authorized_for_integration")),
        "circuit_release_ready": bool(electrical.get("release_ready")),
        "mechanical_release_ready": bool(mechanical.get("production_authorized")),
        "robotics_release_ready": bool(robotics.get("production_authorized")) or not bool(actuators or springs),
        "packaging_ready": bool(packaging.get("packaging_ready")),
        "integrated_bench_ready": bool(bench.get("integrated_bench_ready")),
        "mechatronics_release_ready": bool(release.get("release_ready")),
    }
    closed_layers = [key for key, value in layer_closure.items() if value]
    quality_score = round(len(closed_layers) / max(len(layer_closure), 1), 2)

    return {
        "schema_version": "hardware_splicer.integration_trace.v1",
        "quality_score": quality_score,
        "quality_band": _quality_band(quality_score),
        "weakest_open_layer": _weakest_open_layer(layer_closure),
        "layer_closure": layer_closure,
        "mechanical_chain": primitive_rows,
        "orphan_actuators": orphan_actuators,
        "coverage_summary": {
            "mechanism_primitive_count": len(primitive_rows),
            "generated_output_count": len(outputs),
            "part_metadata_count": len(parts),
            "simulation_finding_count": len(simulation_rows),
            "dfm_finding_count": len(dfm_rows),
            "safety_finding_count": len(safety_rows),
            "actuator_count": len(actuators),
            "spring_count": len(springs),
            "sensor_count": len(sensors),
            "bench_pass_count": int(bench.get("passed_test_count") or 0),
            "bench_artifact_count": int(bench.get("artifact_count") or 0),
        },
        "cross_layer_requirements": {
            "control_board_id": control.get("control_board_id"),
            "control_requirements": _dict(control.get("requirements")),
            "drive_channels": _dict(drive_requirements.get("channels")),
            "drive_types": _string_list(drive_requirements.get("drive_types")),
            "rail_peak_currents_a": _dict(drive_requirements.get("rail_peak_currents_a")),
            "power_source_currents_a": _dict(power.get("source_currents_a")),
            "required_protections": _string_list(drive_requirements.get("required_protections")),
        },
        "open_gaps": _integration_gaps(layer_closure, primitive_rows, orphan_actuators, electrical, packaging, mechanical, robotics, bench, release),
    }


def _mechanism_chain_rows(
    *,
    mechanism_spec: Dict[str, Any],
    outputs: List[str],
    parts: List[Dict[str, Any]],
    simulation_rows: List[Dict[str, Any]],
    dfm_rows: List[Dict[str, Any]],
    safety_rows: List[Dict[str, Any]],
    actuators: List[Dict[str, Any]],
    springs: List[Dict[str, Any]],
    sensors: List[Dict[str, Any]],
    body: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in MECHANISM_KEYS:
        spec = _dict(mechanism_spec.get(key))
        if not spec:
            continue
        tokens = _primitive_tokens(key, spec)
        matched_outputs = _matching_part_outputs(parts, key, tokens) or _matching_strings(outputs, tokens)
        matched_sim = _matching_rows(simulation_rows, tokens)
        matched_dfm = _matching_rows(dfm_rows, tokens)
        if not matched_dfm and matched_outputs and len(dfm_rows) <= 3:
            matched_dfm = dfm_rows
        matched_safety = _matching_rows(safety_rows, tokens)
        matched_actuators = _matching_actuators(actuators, tokens)
        matched_springs = _matching_actuators(springs, tokens)
        matched_sensors = _matching_actuators(sensors, tokens)
        measurement_covered = _capture_covers(body, "mechanical_measurement_capture", tokens)
        mechanical_bench_covered = _capture_covers(body, "mechanical_bench_capture", tokens)
        robotics_bench_covered = _capture_covers(body, "robotics_bench_capture", tokens)
        integrated_bench_covered = _capture_covers(body, "integrated_bench_capture", tokens)

        blockers: List[str] = []
        if key != "assembly" and not matched_outputs:
            blockers.append("No generated CAD/packaging output matched this mechanism primitive.")
        if key not in {"enclosure", "bracket", "assembly"} and not matched_sim:
            blockers.append("No simulation/load evidence matched this moving mechanism primitive.")
        if _has_blocking_row(matched_dfm):
            blockers.append("DFM has blocking findings for this primitive.")
        if _has_blocking_row(matched_sim):
            blockers.append("Simulation has blocking findings for this primitive.")
        if not measurement_covered:
            blockers.append("No measured geometry evidence was matched to this primitive.")
        if not (mechanical_bench_covered or robotics_bench_covered or integrated_bench_covered):
            blockers.append("No bench evidence was matched to this primitive.")

        rows.append(
            {
                "primitive_id": key,
                "name": str(spec.get("name") or key),
                "generated_outputs": matched_outputs[:12],
                "simulation_findings": len(matched_sim),
                "dfm_findings": len(matched_dfm),
                "safety_findings": len(matched_safety),
                "max_severity": _max_severity(matched_dfm + matched_sim + matched_safety),
                "actuators": [_compact_actuator(row) for row in matched_actuators],
                "springs": [_compact_actuator(row) for row in matched_springs],
                "sensors": [_compact_actuator(row) for row in matched_sensors],
                "bench_coverage": {
                    "measurement": measurement_covered,
                    "mechanical_bench": mechanical_bench_covered,
                    "robotics_bench": robotics_bench_covered,
                    "integrated_bench": integrated_bench_covered,
                },
                "integration_status": "closed" if not blockers else "open",
                "blockers": blockers[:10],
            }
        )
    return rows


def _primitive_tokens(key: str, spec: Dict[str, Any]) -> List[str]:
    tokens = {key, key.replace("_", " ")}
    name = str(spec.get("name") or "").strip().lower()
    if name:
        tokens.add(name)
        tokens.add(name.replace("_", " "))
        tokens.update(part for part in re.split(r"[^a-z0-9]+", name) if len(part) > 2)
    for value in _primitive_text_values(spec):
        text = value.strip().lower()
        if not text:
            continue
        tokens.add(text)
        tokens.add(text.replace("_", " "))
        tokens.update(part for part in re.split(r"[^a-z0-9]+", text) if len(part) > 2)
    if key == "pan_tilt":
        tokens.update(["pan", "tilt", "servo", "pt"])
    elif key == "linear_axis":
        tokens.update(["linear", "axis", "stepper", "endstop"])
    elif key == "leadscrew_axis":
        tokens.update(["leadscrew", "lead screw", "stepper", "axis"])
    elif key == "belt_reduction":
        tokens.update(["belt", "reduction", "pulley"])
    elif key == "drive_base":
        tokens.update(["drive", "wheel", "wheels", "motor", "motors", "chassis", "rover", "differential"])
    elif key == "gripper":
        tokens.update(["gripper", "jaw"])
    elif key == "servo_mount":
        tokens.update(["servo", "mount"])
    elif key == "rotary_joint":
        tokens.update(["rotary", "joint", "bearing"])
    elif key == "enclosure":
        tokens.update(["enclosure", "case", "lid", "standoff"])
    elif key == "assembly":
        tokens.update(["assembly", "drive", "wheel", "wheels", "motor", "motors", "chassis", "rover", "differential"])
    return sorted(token for token in tokens if token)


def _primitive_text_values(spec: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for key in ["interfaces", "mounts", "joints", "links", "notes", "role"]:
        value = spec.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(str(item) for item in value if item)
    return values


def _simulation_rows_from_body(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    capture = _first_dict(
        body.get("mechanical_simulation_capture"),
        body.get("fit_load_simulation_capture"),
        body.get("mechanical_simulation"),
    )
    if not capture:
        return []
    rows: List[Dict[str, Any]] = []
    for key in [
        "simulation",
        "simulations",
        "simulation_findings",
        "findings",
        "tests",
        "fit_checks",
        "load_tests",
        "motion_tests",
        "thermal_tests",
        "stress_tests",
    ]:
        rows.extend(_list_dicts(capture.get(key)))
    explicit = bool(capture.get("simulation_verified") is True or capture.get("fit_load_verified") is True)
    if explicit and not any(_row_passed(row) for row in rows):
        rows.append(
            {
                "id": "mechanical_simulation_capture",
                "target": "integrated measured fit/load envelope",
                "status": "pass",
                "message": "Intake evidence explicitly verifies the integrated measured fit/load envelope.",
            }
        )
    return rows


def _matching_strings(values: List[str], tokens: List[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        text = value.lower().replace("_", " ")
        if any(token in text for token in tokens):
            out.append(value)
    return _dedupe_strings(out)


def _matching_part_outputs(parts: List[Dict[str, Any]], primitive_key: str, tokens: List[str]) -> List[str]:
    out: List[str] = []
    for part in parts:
        kind = str(part.get("kind") or "").strip().lower()
        file_name = str(part.get("file") or part.get("name") or "").strip()
        text = " ".join(str(part.get(key) or "") for key in ("file", "module", "kind", "notes")).lower().replace("_", " ")
        if kind == primitive_key or any(token in text for token in tokens):
            if file_name:
                out.append(file_name)
    return _dedupe_strings(out)


def _matching_rows(rows: List[Dict[str, Any]], tokens: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        text = " ".join(str(row.get(key) or "") for key in ("domain", "topic", "message", "target", "name", "id")).lower().replace("_", " ")
        if any(token in text for token in tokens):
            out.append(row)
    return out


def _matching_actuators(rows: List[Dict[str, Any]], tokens: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        text = " ".join(str(row.get(key) or "") for key in ("id", "name", "role", "type", "model")).lower().replace("_", " ")
        if any(token in text for token in tokens):
            out.append(row)
    return out


def _capture_covers(body: Dict[str, Any], capture_key: str, tokens: List[str]) -> bool:
    capture = _dict(body.get(capture_key))
    if not capture:
        return False
    if capture.get("geometry_verified") is True or capture.get("bench_verified") is True or capture.get("motion_verified") is True or capture.get("integrated_bench_ready") is True:
        return True
    rows: List[Dict[str, Any]] = []
    for key in ["measurements", "dimensions", "clearances", "interfaces", "materials", "tests", "fit_checks", "load_tests", "motion_tests", "electrical_tests", "packaging_tests", "thermal_tests", "cycle_tests", "current_tests"]:
        rows.extend(_list_dicts(capture.get(key)))
    return bool(_matching_rows(rows, tokens))


def _compact_actuator(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id") or row.get("name"),
        "type": row.get("type"),
        "drive": row.get("drive"),
        "voltage_v": row.get("voltage_v"),
        "run_current_a": row.get("run_current_a"),
        "stall_current_a": row.get("stall_current_a"),
    }


def _orphan_actuators(actuators: List[Dict[str, Any]], primitive_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matched = {
        str(actuator.get("id") or actuator.get("name") or "")
        for row in primitive_rows
        for actuator in row.get("actuators", [])
        if isinstance(actuator, dict)
    }
    return [_compact_actuator(row) for row in actuators if str(row.get("id") or row.get("name") or "") not in matched]


def _integration_gaps(
    layer_closure: Dict[str, bool],
    primitive_rows: List[Dict[str, Any]],
    orphan_actuators: List[Dict[str, Any]],
    electrical: Dict[str, Any],
    packaging: Dict[str, Any],
    mechanical: Dict[str, Any],
    robotics: Dict[str, Any],
    bench: Dict[str, Any],
    release: Dict[str, Any],
) -> List[str]:
    gaps: List[str] = []
    for key, closed in layer_closure.items():
        if not closed:
            gaps.append(f"Layer not closed: {key}.")
    for row in primitive_rows:
        if row.get("integration_status") != "closed":
            gaps.extend(f"{row.get('primitive_id')}: {item}" for item in (row.get("blockers") or [])[:4])
    if orphan_actuators:
        gaps.append("Some actuators are not mapped to a mechanism primitive: " + ", ".join(str(row.get("id") or row.get("type")) for row in orphan_actuators[:8]) + ".")
    gaps.extend(electrical.get("blockers") or [])
    gaps.extend(packaging.get("blockers") or [])
    gaps.extend(mechanical.get("next_engineering_actions") or [])
    gaps.extend(robotics.get("next_engineering_actions") or [])
    gaps.extend(bench.get("blockers") or [])
    gaps.extend(release.get("blockers") or [])
    return _dedupe_strings(gaps)[:24]


def _quality_band(score: float) -> str:
    if score >= 1.0:
        return "closed_release"
    if score >= 0.85:
        return "bench_ready"
    if score >= 0.65:
        return "integration_ready"
    if score >= 0.4:
        return "prototype_ready"
    return "early_candidate"


def _weakest_open_layer(layer_closure: Dict[str, bool]) -> str | None:
    for key, closed in layer_closure.items():
        if not closed:
            return key
    return None


def _has_blocking_row(rows: List[Dict[str, Any]]) -> bool:
    return any(str(row.get("severity") or row.get("status") or "").lower() in {"block", "error", "critical", "fail", "failed", "unsafe"} or row.get("pass") is False for row in rows)


def _max_severity(rows: List[Dict[str, Any]]) -> str:
    order = {"info": 0, "warning": 1, "warn": 1, "block": 2, "error": 3, "critical": 4}
    current = "none"
    score = -1
    for row in rows:
        severity = str(row.get("severity") or row.get("status") or "info").lower()
        value = order.get(severity, 0)
        if value > score:
            score = value
            current = severity
    return current


def _load_mecha_bundle(mechanism_analysis: Dict[str, Any]) -> Dict[str, Any]:
    bundle = _dict(mechanism_analysis.get("bundle"))
    if bundle:
        return bundle
    bundle_file = str(mechanism_analysis.get("bundle_file") or "").strip()
    if not bundle_file:
        return {}
    try:
        path = Path(bundle_file)
        if path.exists() and path.is_file() and path.stat().st_size <= 20 * 1024 * 1024:
            return _dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return {}
    return {}


def _subsystem_summary(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "authority_level": packet.get("current_authority_level"),
        "authority_score": packet.get("authority_score"),
        "production_authorized": bool(packet.get("production_authorized")),
        "next_action_id": packet.get("next_action_id"),
    }


def _stage(stages: List[Dict[str, Any]], stage_id: str, passed: bool, blockers: List[str], next_unlock: str) -> None:
    stages.append(
        {
            "stage_id": stage_id,
            "status": "pass" if passed else "open",
            "score_if_current": STAGE_SCORES[stage_id],
            "blockers": blockers[:14] if not passed else [],
            "next_unlock": next_unlock,
        }
    )


def _capabilities(stages: List[Dict[str, Any]]) -> Dict[str, bool]:
    return {
        "compile_integrated_mechatronics_bundle": _passed(stages, "system_intake"),
        "run_integrated_power_motion_packaging_bench": _passed(stages, "packaging_authority"),
        "ship_portfolio_demo": _passed(stages, "integrated_bench_authority"),
        "claim_production_mechatronics_release": _passed(stages, "production_mechatronics_release"),
    }


def _authority_at_least(packet: Dict[str, Any], required: str, *, mechanical_order: bool = False, robotics_order: bool = False) -> bool:
    if mechanical_order:
        order = [
            "mechanical_candidate",
            "reference_geometry",
            "measured_geometry",
            "fit_load_simulation",
            "controlled_bench_fit",
            "production_mechanical_release",
        ]
    elif robotics_order:
        order = [
            "actuation_candidate",
            "actuator_model",
            "electrical_drive_matched",
            "mechanical_load_verified",
            "controlled_motion_verified",
            "production_robotics_release",
        ]
    else:
        return False
    level = str(packet.get("current_authority_level") or "")
    return level in order and required in order and order.index(level) >= order.index(required)


def _claim_boundary(level: str | None) -> str:
    if level == "production_mechatronics_release":
        return "Hardware-Splicer can claim a scoped integrated mechatronics release across circuit, motion, and packaging evidence."
    if level == "integrated_bench_authority":
        return "Integrated bench proof exists; final Hardware-Splicer release scope is not closed."
    if level == "packaging_authority":
        return "Electrical/mechanical/packaging artifacts are ready for integrated bench validation."
    if level == "mechanical_robotics_authority":
        return "Circuit and motion subsystems are ready, but packaging/casing artifacts still gate final product authority."
    if level == "electrical_circuit_authority":
        return "Circuit/system checks are usable for integration, but mechanical/robotics/packaging authority remains open."
    if level == "system_intake":
        return "The system is an integrated mechatronics candidate, not yet electrically or mechanically authoritative."
    return "No Hardware-Splicer final product authority is available."


def _scope_limits(body: Dict[str, Any], release: Dict[str, Any], mechanical: Dict[str, Any], robotics: Dict[str, Any]) -> List[str]:
    limits: List[str] = []
    if release.get("scope_statement"):
        limits.append(str(release["scope_statement"]))
    project = str(body.get("project_name") or "").strip()
    if project:
        limits.append(f"Scope is limited to Hardware-Splicer project `{project}` and its generated artifacts.")
    limits.extend(str(item) for item in (mechanical.get("scope_limits") or [])[:3])
    limits.extend(str(item) for item in (robotics.get("scope_limits") or [])[:3])
    limits.append("No certification, human-load, road-vehicle, medical, pressure, or regulatory safety claim is implied.")
    return _dedupe_strings(limits)


def _next_engineering_actions(
    stages: List[Dict[str, Any]],
    electrical: Dict[str, Any],
    packaging: Dict[str, Any],
    mechanical: Dict[str, Any],
    robotics: Dict[str, Any],
) -> List[str]:
    actions: List[str] = []
    for stage in stages:
        if stage.get("status") != "pass":
            actions.extend(str(item) for item in stage.get("blockers") or [])
            break
    actions.extend(electrical.get("warnings") or [])
    actions.extend(packaging.get("warnings") or [])
    if mechanical.get("next_action_id"):
        actions.append(f"Mechanical next action: {mechanical.get('next_action_id')}.")
    if robotics.get("next_action_id"):
        actions.append(f"Robotics next action: {robotics.get('next_action_id')}.")
    return _dedupe_strings(actions)[:14]


def _current_level(stages: List[Dict[str, Any]]) -> str | None:
    current = None
    for stage in stages:
        if stage.get("status") == "pass":
            current = str(stage.get("stage_id") or "")
        else:
            break
    return current


def _next_action_id(stages: List[Dict[str, Any]]) -> str | None:
    for stage in stages:
        if stage.get("status") != "pass":
            return f"close_{stage.get('stage_id')}"
    return None


def _passed(stages: List[Dict[str, Any]], stage_id: str) -> bool:
    return any(stage.get("stage_id") == stage_id and stage.get("status") == "pass" for stage in stages)


def _row_passed(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("result") or row.get("decision") or "").strip().lower()
    return status in {"pass", "passed", "ok", "verified", "accepted", "closed", "true"} or row.get("pass") is True


def _row_failed(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("result") or row.get("decision") or "").strip().lower()
    return status in {"fail", "failed", "block", "blocked", "error", "critical", "unsafe", "rejected"} or row.get("pass") is False


def _artifact_count(capture: Dict[str, Any]) -> int:
    count = 0
    for key in ["artifact_uris", "artifacts", "evidence_uris", "logs", "photos", "videos"]:
        value = capture.get(key)
        if isinstance(value, list):
            count += len([item for item in value if item])
        elif isinstance(value, str) and value.strip():
            count += 1
    return count


def _to_dict(value: Mapping[str, Any] | Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        try:
            return _dict(value.to_dict())
        except Exception:
            return {}
    return _dict(value)


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, Mapping) and value:
            return dict(value)
    return {}


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe_strings(rows: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for row in rows:
        text = str(row).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out
