from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


CASEFILE_SCHEMA_VERSION = "hardware_splicer.casefile.v1"
PROJECT_LOG_SCHEMA_VERSION = "hardware_splicer.project_log.v1"


def build_casefile(
    *,
    spec: Mapping[str, Any],
    engineering: Mapping[str, Any],
    mechanical_authority: Mapping[str, Any],
    robotics_actuation: Mapping[str, Any],
    robotics_simulation: Mapping[str, Any] | None = None,
    mechatronics_authority: Mapping[str, Any],
    robotics_platform_authority: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, str],
    generated_at: str,
    request_id: str,
    out_dir: str | None = None,
    mecha_bundle_dir: str | None = None,
    splicer_url: str | None = None,
    ok: bool = False,
) -> Dict[str, Any]:
    """Build a durable review/evidence casefile for a Hardware-Splicer compile."""

    body = _to_dict(spec)
    engineering_body = _to_dict(engineering)
    mechanical = _to_dict(mechanical_authority)
    robotics = _to_dict(robotics_actuation)
    simulation = _to_dict(robotics_simulation or {})
    robotics_platform = _to_dict(robotics_platform_authority or {})
    mechatronics = _to_dict(mechatronics_authority)
    analysis = _dict(engineering_body.get("analysis"))
    compiled = _dict(engineering_body.get("compiled"))
    machine = _dict(body.get("machine"))
    mechanism_spec = _dict(body.get("mechanism"))
    mechanism_analysis = _dict(analysis.get("mechanism"))
    trace = _dict(mechatronics.get("integration_trace"))
    coverage = _dict(trace.get("coverage_summary"))
    circuit = _dict(_dict(mechatronics.get("subsystems")).get("circuit"))
    packaging = _dict(_dict(mechatronics.get("subsystems")).get("packaging"))
    boards = _list_dicts(machine.get("boards"))
    actuation_profile = _dict(robotics.get("actuation_profile"))
    mechanical_chain = _list_dicts(trace.get("mechanical_chain"))
    open_gaps = _string_list(trace.get("open_gaps"))
    next_actions = _string_list(mechatronics.get("next_engineering_actions")) or open_gaps
    generated_outputs = _generated_outputs(mechanism_analysis, trace)

    dfm_rows = _list_dicts(mechanism_analysis.get("dfm"))
    simulation_rows = _list_dicts(mechanism_analysis.get("simulation"))
    safety_rows = _list_dicts(mechanism_analysis.get("safety"))

    review_matrix = _review_matrix(mechatronics, trace)
    limitations = _limitations(
        circuit=circuit,
        mechanical=mechanical,
        robotics=robotics,
        simulation=simulation,
        mechatronics=mechatronics,
        packaging=packaging,
        open_gaps=open_gaps,
    )

    return {
        "schema_version": CASEFILE_SCHEMA_VERSION,
        "inspiration_patterns": [
            {
                "source": "CNX Software",
                "pattern": "hardware review with overview, setup, benchmark evidence, limits, and final observations",
            },
            {
                "source": "Hackaday.io",
                "pattern": "project state with files, logs, component context, instructions, and discussion-ready history",
            },
            {
                "source": "Hackster.io",
                "pattern": "build package with story, components, schematics/code pointers, and reproduction artifacts",
            },
        ],
        "project": {
            "name": str(body.get("project_name") or machine.get("machine_name") or "hardware_splicer_build"),
            "request_id": request_id,
            "generated_at": generated_at,
            "ok": bool(ok),
            "out_dir": out_dir,
            "splicer_url": splicer_url,
            "mecha_bundle_dir": mecha_bundle_dir,
        },
        "intake": {
            "machine_name": str(machine.get("machine_name") or ""),
            "design_intent": str(machine.get("design_intent") or ""),
            "board_count": len(boards),
            "board_ids": [str(row.get("board_id") or row.get("name") or "") for row in boards],
            "board_design_files": sorted(str(key) for key in _dict(body.get("board_design_files")).keys()),
            "mechanism_primitives": _mechanism_primitives(mechanism_spec),
            "simulation_fidelity": str(body.get("simulation_fidelity") or "starter"),
            "use_3d_splicer": bool(body.get("use_3d_splicer", True)),
            "render_stl": bool(body.get("render_stl", False)),
        },
        "hardware_overview": {
            "boards": _board_overview(boards),
            "mechanisms": mechanical_chain,
            "actuators": _list_dicts(actuation_profile.get("actuators")),
            "springs": _list_dicts(actuation_profile.get("springs")),
            "sensors": _list_dicts(actuation_profile.get("sensors")),
            "generated_outputs": generated_outputs,
        },
        "circuit_evaluation": {
            "readiness": circuit.get("readiness") or _readiness(analysis),
            "authority_level": circuit.get("circuit_authority_level"),
            "authorized_for_integration": bool(circuit.get("authorized_for_integration")),
            "release_ready": bool(circuit.get("release_ready")),
            "board_design_file_count": int(circuit.get("board_design_file_count") or 0),
            "power_summary": _power_summary(analysis),
            "control_coupling": _dict(analysis.get("control_coupling")),
            "interconnects": _dict(analysis.get("interconnects")),
            "warnings": _string_list(circuit.get("warnings")),
            "blockers": _string_list(circuit.get("blockers")) + _string_list(circuit.get("release_blockers")),
        },
        "mechanical_evaluation": {
            "authority_level": mechanical.get("current_authority_level"),
            "authority_score": mechanical.get("authority_score"),
            "production_authorized": bool(mechanical.get("production_authorized")),
            "risk_summary": _dict(mechanical.get("risk_summary")),
            "dfm_counts": _severity_counts(dfm_rows),
            "simulation_counts": _severity_counts(simulation_rows),
            "safety_counts": _severity_counts(safety_rows),
            "claim_boundary": mechanical.get("claim_boundary"),
            "scope_limits": _string_list(mechanical.get("scope_limits")),
        },
        "robotics_evaluation": {
            "authority_level": robotics.get("current_authority_level"),
            "authority_score": robotics.get("authority_score"),
            "production_authorized": bool(robotics.get("production_authorized")),
            "actuation_profile": actuation_profile,
            "drive_requirements": _dict(robotics.get("drive_requirements")),
            "electrical_coupling": _dict(robotics.get("electrical_coupling")),
            "mechanical_load_status": _dict(robotics.get("mechanical_load_status")),
            "motion_bench_status": _dict(robotics.get("motion_bench_status")),
            "claim_boundary": robotics.get("claim_boundary"),
            "scope_limits": _string_list(robotics.get("scope_limits")),
        },
        "robotics_simulation_evaluation": {
            "simulation_ready": bool(simulation.get("simulation_ready")),
            "release_gate": simulation.get("release_gate"),
            "blocking_finding_count": int(simulation.get("blocking_finding_count") or 0),
            "warning_count": int(simulation.get("warning_count") or 0),
            "coverage": _dict(simulation.get("coverage")),
            "power_budget": _dict(simulation.get("power_budget")),
            "runtime_estimate": _dict(simulation.get("runtime_estimate")),
            "drive_kinematics": _dict(simulation.get("drive_kinematics")),
            "servo_load_margins": _dict(simulation.get("servo_load_margins")),
            "safety_envelope": _dict(simulation.get("safety_envelope")),
            "blocking_findings": _list_dicts(simulation.get("blocking_findings")),
            "claim_boundary": simulation.get("claim_boundary"),
        },
        "robotics_project_evaluation": {
            "authority_level": robotics_platform.get("current_authority_level"),
            "authority_score": robotics_platform.get("authority_score"),
            "production_authorized": bool(robotics_platform.get("production_authorized")),
            "project_profile": _dict(robotics_platform.get("project_profile")),
            "platform_topology": _dict(robotics_platform.get("platform_topology")),
            "power_drive_budget": _dict(robotics_platform.get("power_drive_budget")),
            "control_safety_architecture": _dict(robotics_platform.get("control_safety_architecture")),
            "simulation_status": _dict(robotics_platform.get("simulation_status")),
            "validation_status": _dict(robotics_platform.get("validation_status")),
            "claim_boundary": robotics_platform.get("claim_boundary"),
            "scope_limits": _string_list(robotics_platform.get("scope_limits")),
            "next_engineering_actions": _string_list(robotics_platform.get("next_engineering_actions")),
        },
        "packaging_evaluation": {
            "packaging_ready": bool(packaging.get("packaging_ready")),
            "generated_output_count": max(
                int(packaging.get("generated_output_count") or 0),
                int(coverage.get("generated_output_count") or 0),
                len(generated_outputs),
            ),
            "splicer3d_used": bool(packaging.get("splicer3d_used")),
            "mecha_bundle_file": packaging.get("mecha_bundle_file") or mechanism_analysis.get("bundle_file"),
            "splicer3d": _compact_splicer3d(_dict(mechanism_analysis.get("splicer3d"))),
            "warnings": _string_list(packaging.get("warnings")),
            "blockers": _string_list(packaging.get("blockers")),
        },
        "bench_and_release": {
            "hardware_splicer_authority_level": mechatronics.get("current_authority_level"),
            "hardware_splicer_authority_score": mechatronics.get("authority_score"),
            "production_authorized": bool(mechatronics.get("production_authorized")),
            "release_decision": mechatronics.get("release_decision"),
            "trace_quality_band": trace.get("quality_band"),
            "trace_quality_score": trace.get("quality_score"),
            "weakest_open_layer": trace.get("weakest_open_layer"),
            "layer_closure": _dict(trace.get("layer_closure")),
            "coverage_summary": coverage,
            "review_matrix": review_matrix,
            "open_gaps": open_gaps,
            "next_engineering_actions": next_actions,
        },
        "compiled_machine": _dict(compiled.get("machine")),
        "artifact_index": dict(artifacts),
        "limitations": limitations,
    }


def build_project_log(casefile: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a Hackaday-style project log from the casefile state."""

    data = _to_dict(casefile)
    project = _dict(data.get("project"))
    intake = _dict(data.get("intake"))
    circuit = _dict(data.get("circuit_evaluation"))
    mechanical = _dict(data.get("mechanical_evaluation"))
    robotics = _dict(data.get("robotics_evaluation"))
    simulation = _dict(data.get("robotics_simulation_evaluation"))
    robotics_project = _dict(data.get("robotics_project_evaluation"))
    packaging = _dict(data.get("packaging_evaluation"))
    release = _dict(data.get("bench_and_release"))
    gaps = _string_list(release.get("open_gaps"))

    events = [
        {
            "phase": "intake",
            "status": "closed" if intake.get("board_count") and intake.get("mechanism_primitives") else "open",
            "summary": f"Captured {intake.get('board_count') or 0} board(s) and {len(_string_list(intake.get('mechanism_primitives')))} mechanism primitive(s).",
            "evidence": ["machine spec", "mechanism spec"],
            "next": "Attach missing board or mechanism context." if not intake.get("board_count") or not intake.get("mechanism_primitives") else "",
        },
        {
            "phase": "circuit_engineering",
            "status": "closed" if circuit.get("authorized_for_integration") and circuit.get("release_ready") else "open",
            "summary": f"Circuit readiness is {circuit.get('readiness') or 'unknown'} with {circuit.get('board_design_file_count') or 0} design file(s).",
            "evidence": _artifact_names(data, ["mechatronics_authority", "casefile"]),
            "next": "; ".join(_string_list(circuit.get("blockers"))[:3]),
        },
        {
            "phase": "mechanical_generation",
            "status": "closed" if mechanical.get("production_authorized") else "open",
            "summary": f"Mechanical authority is {mechanical.get('authority_level') or 'unknown'} at score {mechanical.get('authority_score') or 0}.",
            "evidence": _artifact_names(data, ["mechanical_authority", "mecha_bundle"]),
            "next": "; ".join(_string_list(mechanical.get("scope_limits"))[:3]),
        },
        {
            "phase": "robotics_actuation",
            "status": "closed" if robotics.get("production_authorized") else "open",
            "summary": f"Robotics authority is {robotics.get('authority_level') or 'unknown'} with {int(_dict(robotics.get('actuation_profile')).get('actuator_count') or 0)} actuator(s).",
            "evidence": _artifact_names(data, ["robotics_actuation"]),
            "next": "; ".join(_string_list(_dict(robotics.get("motion_bench_status")).get("blockers"))[:3]),
        },
        {
            "phase": "robotics_simulation",
            "status": "closed" if simulation.get("simulation_ready") else "open",
            "summary": f"Simulation ready: {bool(simulation.get('simulation_ready'))}; blockers: {simulation.get('blocking_finding_count') or 0}; warnings: {simulation.get('warning_count') or 0}.",
            "evidence": _artifact_names(data, ["robotics_simulation"]),
            "next": "; ".join(str(row.get("message") or "") for row in _list_dicts(simulation.get("blocking_findings"))[:3]),
        },
        {
            "phase": "robotics_project",
            "status": "closed" if robotics_project.get("production_authorized") else "open",
            "summary": f"Robotics project authority is {robotics_project.get('authority_level') or 'unknown'} at score {robotics_project.get('authority_score') or 0}.",
            "evidence": _artifact_names(data, ["robotics_platform_authority"]),
            "next": "; ".join(_string_list(robotics_project.get("next_engineering_actions"))[:3]),
        },
        {
            "phase": "packaging",
            "status": "closed" if packaging.get("packaging_ready") else "open",
            "summary": f"Packaging generated {packaging.get('generated_output_count') or 0} output(s); 3D-Splicer used: {bool(packaging.get('splicer3d_used'))}.",
            "evidence": _artifact_names(data, ["splicer3d_script", "splicer3d_response", "mecha_bundle"]),
            "next": "; ".join(_string_list(packaging.get("blockers"))[:3]),
        },
        {
            "phase": "bench_release",
            "status": "closed" if release.get("production_authorized") else "open",
            "summary": f"Hardware-Splicer authority is {release.get('hardware_splicer_authority_level') or 'unknown'} with trace quality {release.get('trace_quality_band') or 'unknown'}.",
            "evidence": _artifact_names(data, ["mechatronics_authority", "hardware_review", "project_log"]),
            "next": "; ".join(gaps[:5]),
        },
    ]

    return {
        "schema_version": PROJECT_LOG_SCHEMA_VERSION,
        "project_name": project.get("name"),
        "request_id": project.get("request_id"),
        "generated_at": project.get("generated_at"),
        "events": events,
    }


def render_hardware_review(casefile: Mapping[str, Any], project_log: Mapping[str, Any] | None = None) -> str:
    """Render a CNX-style engineering review report for the compiled hardware bundle."""

    data = _to_dict(casefile)
    log = _to_dict(project_log or {})
    project = _dict(data.get("project"))
    intake = _dict(data.get("intake"))
    overview = _dict(data.get("hardware_overview"))
    circuit = _dict(data.get("circuit_evaluation"))
    mechanical = _dict(data.get("mechanical_evaluation"))
    robotics = _dict(data.get("robotics_evaluation"))
    simulation = _dict(data.get("robotics_simulation_evaluation"))
    robotics_project = _dict(data.get("robotics_project_evaluation"))
    packaging = _dict(data.get("packaging_evaluation"))
    release = _dict(data.get("bench_and_release"))
    artifacts = _dict(data.get("artifact_index"))
    limitations = _string_list(data.get("limitations"))
    outputs = _string_list(overview.get("generated_outputs"))
    matrix = _list_dicts(release.get("review_matrix"))
    gaps = _string_list(release.get("open_gaps"))
    actions = _string_list(release.get("next_engineering_actions"))

    lines = [
        f"# Hardware Review: {project.get('name') or 'Hardware-Splicer Build'}",
        "",
        f"- Request ID: `{project.get('request_id') or ''}`",
        f"- Generated: `{project.get('generated_at') or ''}`",
        f"- Compile OK: `{bool(project.get('ok'))}`",
        f"- Hardware-Splicer authority: `{release.get('hardware_splicer_authority_level') or 'unknown'}`",
        f"- Trace quality: `{release.get('trace_quality_band') or 'unknown'}` (`{release.get('trace_quality_score') or 0}`)",
        "",
        "## Hardware Overview",
        f"- Machine: `{intake.get('machine_name') or 'unnamed'}`",
        f"- Design intent: `{intake.get('design_intent') or 'not specified'}`",
        f"- Boards: `{intake.get('board_count') or 0}`",
        f"- Board IDs: `{', '.join(_string_list(intake.get('board_ids'))) or 'none'}`",
        f"- Mechanism primitives: `{', '.join(_string_list(intake.get('mechanism_primitives'))) or 'none'}`",
        f"- Actuators: `{len(_list_dicts(overview.get('actuators')))}`",
        f"- Generated outputs: `{len(outputs)}`",
        "",
        "## Circuit Evaluation",
        f"- Readiness: `{circuit.get('readiness') or 'unknown'}`",
        f"- Authorized for integration: `{bool(circuit.get('authorized_for_integration'))}`",
        f"- Circuit release ready: `{bool(circuit.get('release_ready'))}`",
        f"- Board design files: `{circuit.get('board_design_file_count') or 0}`",
    ]
    lines.extend(_issue_lines("Circuit blockers", _string_list(circuit.get("blockers"))))
    lines.extend(_issue_lines("Circuit warnings", _string_list(circuit.get("warnings"))))

    lines.extend(
        [
            "",
            "## Mechanical Evaluation",
            f"- Authority: `{mechanical.get('authority_level') or 'unknown'}`",
            f"- Authority score: `{mechanical.get('authority_score') or 0}`",
            f"- Production authorized: `{bool(mechanical.get('production_authorized'))}`",
            f"- DFM counts: `{_format_counts(_dict(mechanical.get('dfm_counts')))}`",
            f"- Simulation counts: `{_format_counts(_dict(mechanical.get('simulation_counts')))}`",
            f"- Safety counts: `{_format_counts(_dict(mechanical.get('safety_counts')))}`",
            f"- Claim boundary: `{mechanical.get('claim_boundary') or 'not stated'}`",
            "",
            "## Robotics and Motion",
            f"- Authority: `{robotics.get('authority_level') or 'unknown'}`",
            f"- Authority score: `{robotics.get('authority_score') or 0}`",
            f"- Production authorized: `{bool(robotics.get('production_authorized'))}`",
            f"- Actuators: `{int(_dict(robotics.get('actuation_profile')).get('actuator_count') or 0)}`",
            f"- Springs: `{int(_dict(robotics.get('actuation_profile')).get('spring_count') or 0)}`",
            f"- Sensors: `{int(_dict(robotics.get('actuation_profile')).get('sensor_count') or 0)}`",
            "",
            "## Robotics Simulation",
            f"- Simulation ready: `{bool(simulation.get('simulation_ready'))}`",
            f"- Release gate: `{simulation.get('release_gate') or 'not available'}`",
            f"- Blocking findings: `{simulation.get('blocking_finding_count') or 0}`",
            f"- Warnings: `{simulation.get('warning_count') or 0}`",
            f"- Runtime estimate: `{_dict(simulation.get('runtime_estimate')).get('estimated_runtime_min') or 0}` min",
            f"- Drive speed margin: `{_dict(simulation.get('drive_kinematics')).get('speed_margin') or 0}`",
            f"- Drive force margin: `{_dict(simulation.get('drive_kinematics')).get('force_margin') or 0}`",
            f"- Servo axes checked: `{len(_list_dicts(_dict(simulation.get('servo_load_margins')).get('axes')))}`",
            "",
            "## Robotics Project Authority",
            f"- Authority: `{robotics_project.get('authority_level') or 'unknown'}`",
            f"- Authority score: `{robotics_project.get('authority_score') or 0}`",
            f"- Production authorized: `{bool(robotics_project.get('production_authorized'))}`",
            f"- Robot class: `{_dict(robotics_project.get('project_profile')).get('robot_class') or 'not specified'}`",
            f"- Domains: `{', '.join(_string_list(_dict(robotics_project.get('platform_topology')).get('domains'))) or 'none'}`",
            f"- Claim boundary: `{robotics_project.get('claim_boundary') or 'not stated'}`",
            "",
            "## Packaging and Build Outputs",
            f"- Packaging ready: `{bool(packaging.get('packaging_ready'))}`",
            f"- 3D-Splicer used: `{bool(packaging.get('splicer3d_used'))}`",
            f"- Mecha bundle: `{packaging.get('mecha_bundle_file') or project.get('mecha_bundle_dir') or 'not generated'}`",
        ]
    )
    for output in outputs[:20]:
        lines.append(f"- Output: `{output}`")

    lines.extend(["", "## Benchmark Matrix"])
    if matrix:
        for row in matrix:
            status = "pass" if row.get("passed") else "open"
            lines.append(f"- `{row.get('stage') or row.get('check')}`: `{status}` - {row.get('summary') or ''}")
    else:
        lines.append("- No review matrix was generated.")

    lines.extend(["", "## Issues and Resolutions"])
    if gaps:
        for gap in gaps[:20]:
            lines.append(f"- Open: {gap}")
    else:
        lines.append("- No open integration gaps were recorded for this scoped compile.")
    if actions:
        lines.append("")
        lines.append("Next engineering actions:")
        for action in actions[:12]:
            lines.append(f"- {action}")

    events = _list_dicts(log.get("events"))
    lines.extend(["", "## Project Log"])
    if events:
        for event in events:
            lines.append(f"- `{event.get('phase')}` `{event.get('status')}`: {event.get('summary')}")
    else:
        lines.append("- No project log entries were generated.")

    lines.extend(["", "## Artifact Index"])
    if artifacts:
        for name, path in sorted(artifacts.items()):
            lines.append(f"- `{name}`: `{_artifact_display(path)}`")
    else:
        lines.append("- No artifacts were indexed.")

    lines.extend(["", "## Final Observations"])
    lines.append(
        f"- Current scoped release decision: `{_dict(data.get('bench_and_release')).get('release_decision') or 'unknown'}`"
    )
    lines.append(
        f"- Weakest open layer: `{_dict(data.get('bench_and_release')).get('weakest_open_layer') or 'none'}`"
    )
    if limitations:
        for limit in limitations[:12]:
            lines.append(f"- Limit: {limit}")
    else:
        lines.append("- No additional scope limits were recorded.")

    return "\n".join(lines).rstrip() + "\n"


def _review_matrix(mechatronics: Dict[str, Any], trace: Dict[str, Any]) -> List[Dict[str, Any]]:
    matrix: List[Dict[str, Any]] = []
    for stage in _list_dicts(mechatronics.get("stages")):
        stage_id = str(stage.get("stage_id") or stage.get("id") or stage.get("stage") or "unknown")
        passed = _stage_passed(stage)
        blockers = _string_list(stage.get("blockers"))
        matrix.append(
            {
                "stage": stage_id,
                "passed": passed,
                "summary": "closed" if passed else "; ".join(blockers[:3]) or "evidence still required",
                "next_unlock": stage.get("next_unlock") or stage.get("next_action") or "",
                "blockers": blockers,
            }
        )
    layer_closure = _dict(trace.get("layer_closure"))
    known = {row["stage"] for row in matrix}
    for key, passed in sorted(layer_closure.items()):
        if key not in known:
            matrix.append(
                {
                    "stage": key,
                    "passed": bool(passed),
                    "summary": "closed" if passed else "open in integration trace",
                    "next_unlock": "",
                    "blockers": [],
                }
            )
    return matrix


def _stage_passed(stage: Dict[str, Any]) -> bool:
    status = str(stage.get("status") or stage.get("result") or "").strip().lower()
    return bool(stage.get("passed")) or stage.get("pass") is True or status in {"pass", "passed", "ok", "verified", "accepted", "closed", "true"}


def _limitations(
    *,
    circuit: Dict[str, Any],
    mechanical: Dict[str, Any],
    robotics: Dict[str, Any],
    simulation: Dict[str, Any],
    mechatronics: Dict[str, Any],
    packaging: Dict[str, Any],
    open_gaps: List[str],
) -> List[str]:
    limits: List[str] = []
    limits.extend(_string_list(mechatronics.get("scope_limits")))
    limits.extend(_string_list(mechanical.get("scope_limits")))
    limits.extend(_string_list(robotics.get("scope_limits")))
    limits.extend(str(row.get("message") or "") for row in _list_dicts(simulation.get("blocking_findings")))
    limits.extend(_string_list(circuit.get("warnings")))
    limits.extend(_string_list(packaging.get("warnings")))
    if open_gaps:
        limits.append("Open gaps remain; do not treat this package as broader than the recorded release scope.")
    if not bool(mechatronics.get("production_authorized")):
        limits.append("This is not a production mechatronics release until all authority stages are closed.")
    limits.append("Physical safety, regulatory compliance, and field reliability still require qualified human review.")
    return _dedupe_strings(limits)


def _mechanism_primitives(mechanism_spec: Dict[str, Any]) -> List[str]:
    primitives = []
    for key, value in mechanism_spec.items():
        if key in {"project_name", "mode", "process", "metadata"}:
            continue
        if isinstance(value, Mapping) and value:
            primitives.append(str(key))
    return sorted(primitives)


def _board_overview(boards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for board in boards:
        capabilities = _dict(board.get("capabilities"))
        rows.append(
            {
                "board_id": str(board.get("board_id") or board.get("name") or ""),
                "name": str(board.get("name") or board.get("board_id") or ""),
                "pcb_outline_mm": board.get("pcb_outline_mm"),
                "estimated_current_a": board.get("estimated_current_a"),
                "pwm_channels": capabilities.get("pwm_channels"),
                "stepper_channels": capabilities.get("stepper_channels"),
                "actuation_current_budget_a": capabilities.get("actuation_current_budget_a"),
                "requirements_present": isinstance(board.get("requirements"), Mapping),
            }
        )
    return rows


def _generated_outputs(mechanism_analysis: Dict[str, Any], trace: Dict[str, Any]) -> List[str]:
    outputs = _string_list(mechanism_analysis.get("outputs"))
    for row in _list_dicts(trace.get("mechanical_chain")):
        outputs.extend(_string_list(row.get("generated_outputs")))
    return _dedupe_strings(outputs)


def _power_summary(analysis: Dict[str, Any]) -> Dict[str, Any]:
    power = _dict(analysis.get("power"))
    return {
        "rails": power.get("rails"),
        "sources": power.get("sources"),
        "loads": power.get("loads"),
        "source_currents_a": _dict(power.get("source_currents_a")),
        "issues": _list_dicts(power.get("issues")),
    }


def _compact_splicer3d(splicer3d: Dict[str, Any]) -> Dict[str, Any]:
    if not splicer3d:
        return {}
    return {
        "ok": splicer3d.get("ok"),
        "success": splicer3d.get("success"),
        "mode": splicer3d.get("mode"),
        "script_present": bool(str(splicer3d.get("script") or "").strip()),
        "stl_path": splicer3d.get("stl_path"),
        "error": splicer3d.get("error"),
    }


def _readiness(analysis: Dict[str, Any]) -> str:
    verdict = _dict(analysis.get("verdict"))
    return str(verdict.get("status") or "unknown")


def _artifact_names(casefile: Dict[str, Any], keys: Iterable[str]) -> List[str]:
    artifacts = _dict(casefile.get("artifact_index"))
    names = []
    for key in keys:
        if key == "mecha_bundle":
            bundle = _dict(casefile.get("project")).get("mecha_bundle_dir")
            if bundle:
                names.append("mecha_bundle")
            continue
        if artifacts.get(key):
            names.append(str(key))
    return names


def _artifact_display(path: Any) -> str:
    text = str(path or "")
    if not text:
        return ""
    try:
        return Path(text).name
    except (TypeError, ValueError):
        return text


def _issue_lines(label: str, issues: List[str]) -> List[str]:
    lines: List[str] = [f"- {label}: `{len(issues)}`"]
    for issue in issues[:8]:
        lines.append(f"  - {issue}")
    return lines


def _format_counts(counts: Dict[str, Any]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _severity_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        severity = str(row.get("severity") or "info").strip().lower() or "info"
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def _to_dict(data: Mapping[str, Any] | Any) -> Dict[str, Any]:
    return dict(data) if isinstance(data, Mapping) else {}


def _dict(data: Any) -> Dict[str, Any]:
    return dict(data) if isinstance(data, Mapping) else {}


def _list_dicts(data: Any) -> List[Dict[str, Any]]:
    if not isinstance(data, list):
        return []
    return [dict(row) for row in data if isinstance(row, Mapping)]


def _string_list(data: Any) -> List[str]:
    if data is None:
        return []
    if isinstance(data, str):
        return [data] if data.strip() else []
    if isinstance(data, Mapping):
        return [str(value) for value in data.values() if str(value).strip()]
    if isinstance(data, Iterable):
        out = []
        for row in data:
            text = str(row).strip()
            if text:
                out.append(text)
        return out
    return []


def _dedupe_strings(values: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out
