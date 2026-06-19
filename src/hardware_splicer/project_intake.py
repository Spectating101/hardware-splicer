from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .build_compiler import compile_catalog_build, resolve_build_id
from .design_quality import build_design_quality_gate
from .fabrication_inspection import inspect_fabrication_package
from .functional_delivery import build_functional_delivery_score
from .evidence_extractor import _merge_evidence, enrich_intake_with_extracted_evidence
from .build_evidence import compiler_evidence_patch
from .salvage_bridge import build_intake_salvage_package
from .compile_casefile import write_compile_casefile
from .scratch_pipeline import compile_scratch_build
from .scenario_runner import run_hardware_scenario
from .vision_evidence_assistant import enrich_intake_with_vision_assistance


SCHEMA_VERSION = "hardware_splicer.project_intake.v1"
UPGRADE_SCHEMA_VERSION = "hardware_splicer.authority_upgrade_plan.v1"
EVIDENCE_KIT_SCHEMA_VERSION = "hardware_splicer.evidence_capture_kit.v1"

PROJECT_LEVELS = [
    "compile_failed",
    "project_intake",
    "architecture_project_package",
    "control_safety_project_package",
    "simulation_bench_project_package",
    "field_validated_project_package",
    "production_ready_project_package",
]

REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_intake_fixture_refs(value: Any) -> Any:
    """Expand @examples/... JSON file references inside intake payloads."""
    if isinstance(value, str) and value.startswith("@"):
        rel = value[1:].lstrip("/")
        path = (REPO_ROOT / rel).resolve()
        if not path.is_file():
            raise ValueError(f"intake fixture not found: {value} -> {path}")
        return _resolve_intake_fixture_refs(json.loads(path.read_text(encoding="utf-8")))
    if isinstance(value, list):
        return [_resolve_intake_fixture_refs(item) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_intake_fixture_refs(item) for key, item in value.items()}
    return value


def _donor_context_from_intake(body: Mapping[str, Any]) -> Dict[str, Any]:
    context: Dict[str, Any] = {}
    for key in ("analysis", "circuit", "functional_salvage", "donor_boards"):
        if key in body and body.get(key) is not None:
            context[key] = body[key]
    return context


def load_project_intake(path: str | Path) -> Dict[str, Any]:
    source = Path(path).resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("project intake file must contain a JSON object")
    intake = _resolve_intake_fixture_refs(dict(data))
    intake.setdefault("source_file", str(source))
    from .repair_intake import apply_repair_intake_context

    return apply_repair_intake_context(intake)


def plan_project_from_intake(intake: Mapping[str, Any], *, skip_vision: bool = False) -> Dict[str, Any]:
    body = _to_dict(intake, "intake")
    from .vision_inventory import merge_attachment_inventory_into_intake

    body, offline_inventory = merge_attachment_inventory_into_intake(body)
    from .board_vision_salvage import enrich_intake_with_donor_board_vision

    body, donor_board_vision_report = enrich_intake_with_donor_board_vision(body)
    if skip_vision:
        vision_report = {"enabled": False, "skipped": True, "offline_inventory": offline_inventory}
        body, extraction_report = enrich_intake_with_extracted_evidence(body)
    else:
        body, vision_report = enrich_intake_with_vision_assistance(body)
        vision_report = {**vision_report, "offline_inventory": offline_inventory}
        body, extraction_report = enrich_intake_with_extracted_evidence(body)
    project_name = _slug(str(body.get("project_name") or body.get("name") or body.get("goal") or "hardware_splicer_project"))
    goal = str(body.get("goal") or body.get("intent") or body.get("brief") or project_name).strip()
    constraints = _to_dict(body.get("constraints") or {}, "intake.constraints")
    budget = _budget(body)
    parts = _normalized_parts(
        body.get("available_parts") or body.get("parts") or body.get("resources") or [],
        goal=goal,
    )
    from .integrations.qwen_intake_normalize import detect_archetype_llm

    archetype = detect_archetype_llm(goal, parts)
    evidence = _evidence(body)
    base_dir = _source_base_dir(body)
    assumptions = _assumptions(archetype, parts, constraints, budget)
    missing = _missing_info(archetype, parts, constraints, budget, evidence)
    salvage_package = build_intake_salvage_package(
        goal=goal,
        parts=parts,
        constraints=constraints,
        project_name=project_name,
        budget=budget,
        donor_context=_donor_context_from_intake(body),
    )
    if salvage_package.get("recommended_build_id"):
        archetype = _archetype_from_build_id(str(salvage_package["recommended_build_id"]), archetype)
    spec = _compile_spec(
        project_name,
        goal,
        archetype,
        parts,
        constraints,
        budget,
        assumptions,
        evidence,
        base_dir,
        salvage_package=salvage_package,
    )
    scenario = {
        "scenario_name": f"{project_name}_{archetype}",
        "intent": goal,
        "compile_spec": spec,
        "expected": _expected_authority(archetype, body, evidence),
        "acceptance": {
            "allowed_blockers": int(_to_dict(body.get("acceptance") or {}, "intake.acceptance").get("allowed_blockers") or 99),
            "source_blockers_are_next_actions": True,
            "must_have_artifacts": [
                "ROBOTICS_SIMULATION.json",
                "ROBOTICS_PLATFORM_AUTHORITY.json",
                "MECHATRONICS_AUTHORITY.json",
                "CASEFILE.json",
                "PROJECT_LOG.json",
                "HARDWARE_REVIEW.md",
            ],
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "project_name": project_name,
        "goal": goal,
        "archetype": archetype,
        "planning_confidence": max(
            _planning_confidence(archetype, parts, missing),
            float(salvage_package.get("planning_confidence") or 0.0),
        ),
        "budget": budget,
        "normalized_parts": parts,
        "salvage_package": salvage_package,
        "recommended_build_id": salvage_package.get("recommended_build_id"),
        "salvage_verdict": salvage_package.get("verdict"),
        "assumptions": assumptions,
        "vision_evidence_report": vision_report,
        "evidence_extraction_report": extraction_report,
        "donor_board_vision_report": donor_board_vision_report,
        "evidence_summary": _evidence_summary(evidence, base_dir),
        "missing_info": missing,
        "scenario": scenario,
    }


def splice_and_build_from_intake(
    intake: Mapping[str, Any],
    *,
    out_dir: str | Path,
    export_gerber: bool = True,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Plan salvage splice + compile catalog build without full mecha/scenario pipeline."""
    plan = plan_project_from_intake(intake)
    salvage_package = _to_dict(plan.get("salvage_package") or {}, "intake_plan.salvage_package")
    build_id = str(
        salvage_package.get("recommended_build_id")
        or resolve_build_id(archetype=str(plan.get("archetype") or ""))
        or ""
    ).strip()
    if not build_id:
        raise ValueError("intake did not resolve to a catalog build_id")

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    splice_plan_file = out_path / "SPLICE_PLAN.json"
    intake_file = out_path / "PROJECT_INTAKE.json"
    splice_plan_file.write_text(json.dumps(salvage_package, indent=2), encoding="utf-8")
    gap_file = out_path / "SALVAGE_GAP_ANALYSIS.json"
    bringup_json = out_path / "BRINGUP_CARD.json"
    bringup_md = out_path / "BRINGUP_CARD.md"
    bom_file = out_path / "SALVAGE_BOM.json"
    goal = str(plan.get("goal") or intake.get("goal") or "").strip()
    if salvage_package.get("gap_analysis"):
        gap_file.write_text(json.dumps(salvage_package["gap_analysis"], indent=2), encoding="utf-8")
    if salvage_package.get("bringup_card"):
        bringup_json.write_text(json.dumps(salvage_package["bringup_card"], indent=2), encoding="utf-8")
        bringup_md.write_text(str(salvage_package["bringup_card"].get("markdown") or ""), encoding="utf-8")
    if salvage_package.get("bom_estimate"):
        from .salvage_bom_estimate import write_salvage_bom_artifacts

        write_salvage_bom_artifacts(salvage_package["bom_estimate"], out_path)
    if salvage_package.get("firmware_scaffold"):
        from .firmware_scaffold import write_salvage_firmware

        write_salvage_firmware(
            build_id=build_id,
            salvage_package=salvage_package,
            goal=goal,
            out_dir=out_path,
        )
    intake_snapshot = dict(plan)
    for key in ("circuit", "functional_salvage", "evidence_notes", "available_parts", "salvage_mode", "constraints"):
        if key in intake and intake.get(key) is not None:
            intake_snapshot[key] = intake[key]
    intake_file.write_text(json.dumps(intake_snapshot, indent=2), encoding="utf-8")

    graph_input = salvage_package.get("graph_input") or salvage_package.get("splice_package")
    resolved_modules = salvage_package.get("resolved_modules") or []
    scratch_result = None
    if salvage_package.get("graph_mode") == "scratch":
        scratch_result = compile_scratch_build(
            out_dir=str(out_path),
            goal=goal,
            resolved_modules=resolved_modules if isinstance(resolved_modules, list) else None,
            export_gerber=export_gerber,
            constraints=dict(intake.get("constraints") or {}),
            salvage_mode=bool(intake.get("salvage_mode")),
        )
        compile_result = scratch_result.compile_result
        if compile_result is None:
            from .build_compiler import BuildCompileResult

            compile_result = BuildCompileResult(
                ok=False,
                build_id=build_id,
                out_dir=out_path,
                design_quality={"build_ready": False, "circuit_readiness": "compile_failed"},
                build_graph_file=None,
                kicad_pcb_file=None,
                design_quality_file=str(out_path / "build_compilation" / "DESIGN_QUALITY.json"),
                error=scratch_result.error or "scratch compile failed",
            )
        build_id = scratch_result.build_id
    else:
        compile_result = compile_catalog_build(
            build_id,
            out_path,
            export_gerber=export_gerber,
            splice_plan=graph_input if isinstance(graph_input, dict) else None,
            resolved_modules=resolved_modules if isinstance(resolved_modules, list) else None,
        )
    gate = build_design_quality_gate(compile_result.design_quality)
    gate_path = out_path / "build_compilation" / "DESIGN_QUALITY_GATE.json"
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")

    compile_casefile: str | None = None
    if scratch_result and scratch_result.compile_casefile:
        compile_casefile = scratch_result.compile_casefile
    elif not (compile_result.ok and gate.get("build_ready")):
        build_dir = out_path / "build_compilation"
        compile_casefile = write_compile_casefile(
            build_dir,
            build_id=build_id,
            error=compile_result.error or "intake_compile_failed",
            stage="intake_splice",
            quality=compile_result.design_quality,
            splice_plan=graph_input if isinstance(graph_input, dict) else None,
            intake=dict(intake),
        )

    build_dir = out_path / "build_compilation"
    functional_delivery = build_functional_delivery_score(
        build_compilation=compile_result.to_dict(),
        artifacts={
            "splice_plan": str(splice_plan_file),
            "build_graph": compile_result.build_graph_file,
            "build_kicad_pcb": compile_result.kicad_pcb_file,
        },
    )
    functional_delivery_file = out_path / "FUNCTIONAL_DELIVERY.json"
    functional_delivery_file.write_text(json.dumps(functional_delivery, indent=2), encoding="utf-8")
    fabrication_inspection = inspect_fabrication_package(
        build_compilation=compile_result.to_dict(),
        artifacts={
            "splice_plan": str(splice_plan_file),
            "build_graph": compile_result.build_graph_file,
            "build_kicad_pcb": compile_result.kicad_pcb_file,
            "fab_package_zip": str(build_dir / "fab_package.zip") if (build_dir / "fab_package.zip").is_file() else None,
        },
    )
    inspection_file = out_path / "FABRICATION_INSPECTION.json"
    inspection_file.write_text(json.dumps(fabrication_inspection, indent=2), encoding="utf-8")

    scenario = _to_dict(plan.get("scenario"), "plan.scenario")
    compile_spec = _to_dict(scenario.get("compile_spec"), "plan.scenario.compile_spec")
    mechanism = _to_dict(compile_spec.get("mechanism"), "plan.scenario.compile_spec.mechanism")
    compiler_patch = compiler_evidence_patch(compile_result.to_dict(), out_path, mechanism)
    compiler_patch_file = out_path / "COMPILER_EVIDENCE_PATCH.json"
    if compiler_patch:
        compiler_patch_file.write_text(json.dumps(compiler_patch, indent=2), encoding="utf-8")
    post_intake = _to_dict(intake, "intake")
    if compiler_patch:
        evidence = _to_dict(post_intake.get("evidence"), "intake.evidence")
        _merge_evidence(evidence, compiler_patch)
        post_intake["evidence"] = evidence
    post_plan = plan_project_from_intake(post_intake, skip_vision=True) if compiler_patch else plan
    post_metrics_file = out_path / "POST_SPLICE_SCORING.json"
    post_metrics_file.write_text(
        json.dumps(
            {
                "schema_version": "hardware_splicer.post_splice_scoring.v1",
                "compiler_evidence_patch": compiler_patch,
                "planning_confidence": post_plan.get("planning_confidence"),
                "missing_info": post_plan.get("missing_info"),
                "evidence_summary": post_plan.get("evidence_summary"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    from .splice_bench import open_bench_session
    from .bench_capture_bridge import sync_bench_session_template

    bench_session = open_bench_session(out_path)
    template_sync = sync_bench_session_template(out_path)
    bench_session = template_sync.get("session") or bench_session
    bench_capture_template = (template_sync.get("template") or {}).get("template_path")

    vision_report = _to_dict(plan.get("vision_evidence_report") or {}, "intake_plan.vision_evidence_report")
    extraction_report = _to_dict(plan.get("evidence_extraction_report") or {}, "intake_plan.evidence_extraction_report")
    donor_board_vision_report = _to_dict(
        plan.get("donor_board_vision_report") or {},
        "intake_plan.donor_board_vision_report",
    )
    vision_report_file = out_path / "VISION_EVIDENCE_REPORT.json"
    extraction_report_file = out_path / "EVIDENCE_EXTRACTION_REPORT.json"
    donor_vision_file = out_path / "DONOR_BOARD_VISION_REPORT.json"
    vision_report_file.write_text(json.dumps(vision_report, indent=2), encoding="utf-8")
    extraction_report_file.write_text(json.dumps(extraction_report, indent=2), encoding="utf-8")
    donor_vision_file.write_text(json.dumps(donor_board_vision_report, indent=2), encoding="utf-8")

    return {
        "ok": bool(compile_result.ok and gate.get("build_ready")),
        "request_id": request_id or plan.get("project_name"),
        "project_name": plan.get("project_name"),
        "goal": plan.get("goal"),
        "archetype": plan.get("archetype"),
        "build_id": build_id,
        "salvage_verdict": salvage_package.get("verdict"),
        "salvage_package": salvage_package,
        "power_topology": salvage_package.get("power_topology"),
        "planning_confidence": plan.get("planning_confidence"),
        "build_compilation": compile_result.to_dict(),
        "design_quality_gate": gate,
        "functional_delivery": functional_delivery,
        "artifacts": {
            "project_intake": str(intake_file),
            "splice_plan": str(splice_plan_file),
            "design_quality": compile_result.design_quality_file,
            "design_quality_gate": str(gate_path),
            "build_graph": compile_result.build_graph_file,
            "kicad_pcb": compile_result.kicad_pcb_file,
            "gerber_package_dir": compile_result.gerber_package_dir,
            "fab_package_zip": str(build_dir / "fab_package.zip")
            if (build_dir / "fab_package.zip").is_file()
            else None,
            "functional_delivery": str(functional_delivery_file),
            "fabrication_inspection": str(inspection_file),
            "compile_casefile": compile_casefile,
            "compiler_evidence_patch": str(compiler_patch_file) if compiler_patch else None,
            "post_splice_scoring": str(post_metrics_file),
            "bench_session": bench_session.get("session_path"),
            "bench_capture_template": bench_capture_template or "",
            "bringup_card": str(bringup_json) if bringup_json.is_file() else "",
            "bringup_card_md": str(bringup_md) if bringup_md.is_file() else "",
            "vision_evidence_report": str(vision_report_file),
            "evidence_extraction_report": str(extraction_report_file),
            "donor_board_vision_report": str(donor_vision_file),
        },
        "bench_session": {
            "readiness": bench_session.get("readiness"),
            "open_gate_count": bench_session.get("open_gate_count"),
            "critical_open_count": bench_session.get("critical_open_count"),
            "power_on_authorized": bench_session.get("power_on_authorized"),
            "next_actions": bench_session.get("next_actions"),
            "session_path": bench_session.get("session_path"),
            "bench_capture_template": bench_capture_template,
        },
        "vision_evidence_report": vision_report,
        "evidence_extraction_report": extraction_report,
        "donor_board_vision_report": donor_board_vision_report,
        "compiler_evidence_patch": compiler_patch,
        "post_splice_planning": {
            "planning_confidence": post_plan.get("planning_confidence"),
            "missing_info": post_plan.get("missing_info"),
            "evidence_summary": post_plan.get("evidence_summary"),
        },
    }


def run_project_intake(
    intake: Mapping[str, Any],
    *,
    out_dir: str | Path,
    start_splicer: bool = True,
    splicer_port: int = 0,
    request_id: str | None = None,
) -> Dict[str, Any]:
    plan = plan_project_from_intake(intake)
    result = run_hardware_scenario(
        plan["scenario"],
        out_dir=out_dir,
        start_splicer=start_splicer,
        splicer_port=splicer_port,
        request_id=request_id or plan["project_name"],
    )
    out_path = Path(result["out_dir"])
    intake_file = out_path / "PROJECT_INTAKE.json"
    planned_scenario_file = out_path / "PLANNED_SCENARIO.json"
    vision_report = _to_dict(plan.get("vision_evidence_report") or {}, "intake_plan.vision_evidence_report")
    extraction_report = _to_dict(plan.get("evidence_extraction_report") or {}, "intake_plan.evidence_extraction_report")
    upgrade_plan = build_authority_upgrade_plan(plan, result)
    evidence_kit = build_evidence_capture_kit(plan, result, upgrade_plan)
    vision_report_file = out_path / "VISION_EVIDENCE_REPORT.json"
    extraction_report_file = out_path / "EVIDENCE_EXTRACTION_REPORT.json"
    upgrade_plan_file = out_path / "AUTHORITY_UPGRADE_PLAN.json"
    evidence_kit_file = out_path / "EVIDENCE_CAPTURE_KIT.json"
    splice_plan_file = out_path / "SPLICE_PLAN.json"
    gap_file = out_path / "SALVAGE_GAP_ANALYSIS.json"
    bringup_json = out_path / "BRINGUP_CARD.json"
    bringup_md = out_path / "BRINGUP_CARD.md"
    bom_file = out_path / "SALVAGE_BOM.json"
    firmware_meta = out_path / "firmware" / "FIRMWARE_SCAFFOLD.json"
    salvage_package = _to_dict(plan.get("salvage_package") or {}, "intake_plan.salvage_package")
    if salvage_package:
        splice_plan_file.write_text(json.dumps(salvage_package, indent=2), encoding="utf-8")
        gap = salvage_package.get("gap_analysis")
        bringup = salvage_package.get("bringup_card")
        bom = salvage_package.get("bom_estimate")
        fw = salvage_package.get("firmware_scaffold")
        if gap:
            gap_file.write_text(json.dumps(gap, indent=2), encoding="utf-8")
        if bringup:
            bringup_json.write_text(json.dumps(bringup, indent=2), encoding="utf-8")
            bringup_md.write_text(str(bringup.get("markdown") or ""), encoding="utf-8")
        if bom:
            from .salvage_bom_estimate import write_salvage_bom_artifacts

            bom_paths = write_salvage_bom_artifacts(bom, out_path)
            bom_file = Path(bom_paths["salvage_bom_json"])
        if fw:
            from .firmware_scaffold import write_salvage_firmware

            firmware_meta.parent.mkdir(parents=True, exist_ok=True)
            write_salvage_firmware(
                build_id=str(salvage_package.get("recommended_build_id") or "salvage_build"),
                salvage_package=salvage_package,
                goal=str(plan.get("goal") or ""),
                out_dir=out_path,
            )
    intake_file.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    planned_scenario_file.write_text(json.dumps(plan["scenario"], indent=2), encoding="utf-8")
    vision_report_file.write_text(json.dumps(vision_report, indent=2), encoding="utf-8")
    extraction_report_file.write_text(json.dumps(extraction_report, indent=2), encoding="utf-8")
    upgrade_plan_file.write_text(json.dumps(upgrade_plan, indent=2), encoding="utf-8")
    evidence_kit_file.write_text(json.dumps(evidence_kit, indent=2), encoding="utf-8")
    result["intake_plan"] = plan
    result["vision_evidence_report"] = vision_report
    result["evidence_extraction_report"] = extraction_report
    result["authority_upgrade_plan"] = upgrade_plan
    result["evidence_capture_kit"] = evidence_kit
    result["artifacts"] = {
        **result["artifacts"],
        "project_intake": str(intake_file),
        "planned_scenario": str(planned_scenario_file),
        "vision_evidence_report": str(vision_report_file),
        "evidence_extraction_report": str(extraction_report_file),
        "authority_upgrade_plan": str(upgrade_plan_file),
        "evidence_capture_kit": str(evidence_kit_file),
        "splice_plan": str(splice_plan_file) if salvage_package else "",
        "salvage_gap_analysis": str(gap_file) if gap_file.is_file() else "",
        "bringup_card": str(bringup_json) if bringup_json.is_file() else "",
        "bringup_card_md": str(bringup_md) if bringup_md.is_file() else "",
        "salvage_bom": str(bom_file) if bom_file.is_file() else "",
        "salvage_bom_csv": str(out_path / "SALVAGE_BOM.csv") if (out_path / "SALVAGE_BOM.csv").is_file() else "",
        "firmware_scaffold": str(firmware_meta) if firmware_meta.is_file() else "",
    }
    scenario_result_path = result["artifacts"].get("scenario_result")
    if scenario_result_path:
        Path(str(scenario_result_path)).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def build_authority_upgrade_plan(intake_plan: Mapping[str, Any], run_result: Mapping[str, Any]) -> Dict[str, Any]:
    plan = _to_dict(intake_plan, "intake_plan")
    result = _to_dict(run_result, "run_result")
    authority = _to_dict(result.get("project_authority") or {}, "run_result.project_authority")
    current_level = str(authority.get("project_authority_level") or "project_intake")
    next_level = _next_project_level(current_level)
    missing = _string_list(plan.get("missing_info"))
    next_actions = _string_list(authority.get("next_actions"))
    evidence_requests = _evidence_requests(current_level, next_level, missing, plan)
    return {
        "schema_version": UPGRADE_SCHEMA_VERSION,
        "project_name": plan.get("project_name"),
        "archetype": plan.get("archetype"),
        "current_level": current_level,
        "next_level": next_level,
        "target_level": "production_ready_project_package",
        "claimable_current_package": bool(authority.get("claimable")),
        "evidence_requests": evidence_requests,
        "missing_info": missing,
        "engine_next_actions": next_actions[:16],
        "how_to_upgrade": _upgrade_recipe(evidence_requests),
    }


def build_evidence_capture_kit(
    intake_plan: Mapping[str, Any],
    run_result: Mapping[str, Any],
    upgrade_plan: Mapping[str, Any],
) -> Dict[str, Any]:
    plan = _to_dict(intake_plan, "intake_plan")
    result = _to_dict(run_result, "run_result")
    metrics = _to_dict(result.get("production_release_metrics") or {}, "run_result.production_release_metrics")
    upgrade = _to_dict(upgrade_plan, "upgrade_plan")
    gates = _list_dicts(metrics.get("weighted_gates"))
    open_gates = [row for row in gates if not bool(row.get("passed"))]

    capture_requests: List[Dict[str, Any]] = []
    template_patch: Dict[str, Any] = {"evidence": {}}
    for gate in open_gates:
        gate_id = str(gate.get("id") or "").strip()
        templates = _capture_templates_for_gate(gate_id, str(plan.get("archetype") or "generic_mechatronics"))
        evidence_fields = []
        for template in templates:
            field_name = str(template.get("intake_field") or "").strip()
            if field_name:
                evidence_fields.append(field_name)
            _merge_evidence_patch(template_patch["evidence"], _to_dict(template.get("template") or {}, "template"))
            capture_requests.append(
                {
                    "gate_id": gate_id,
                    "gate_label": gate.get("label"),
                    "request_id": template.get("id"),
                    "intake_field": field_name,
                    "label": template.get("label"),
                    "required_items": _string_list(template.get("required_items")),
                    "example": template.get("template"),
                }
            )
        gate["evidence_fields"] = _dedupe_strings(evidence_fields)

    return {
        "schema_version": EVIDENCE_KIT_SCHEMA_VERSION,
        "project_name": plan.get("project_name"),
        "archetype": plan.get("archetype"),
        "current_level": upgrade.get("current_level"),
        "target_level": "production_ready_project_package",
        "production_readiness_score": metrics.get("production_readiness_score"),
        "gates_passed": metrics.get("gates_passed"),
        "gates_total": metrics.get("gates_total"),
        "open_gate_count": len(open_gates),
        "open_gates": [
            {
                "id": row.get("id"),
                "label": row.get("label"),
                "weight": row.get("weight"),
                "score": row.get("score"),
                "observed": row.get("observed"),
                "blockers": _string_list(row.get("blockers")),
                "evidence_fields": _string_list(row.get("evidence_fields")),
            }
            for row in open_gates
        ],
        "capture_requests": _dedupe_capture_requests(capture_requests),
        "template_intake_patch": template_patch,
        "manual_capture_order": [
            "Attach board design files and reviewed circuit scope.",
            "Capture measured geometry, then fit/load simulation tied to those measured interfaces.",
            "Run subsystem bench checks for mechanical fit/load and actuator motion/current.",
            "Run integrated electrical + motion + packaging bench checks.",
            "Record field/mission validation only after subsystem and integrated bench evidence closes.",
            "Attach final scoped release reviews for mechanical, robotics, mechatronics, and project authority.",
        ],
    }


def _capture_templates_for_gate(gate_id: str, archetype: str) -> List[Dict[str, Any]]:
    common_release = {
        "release_review": {
            "scope_statement": _release_scope_example(archetype),
            "artifact_uris": ["evidence://project/release-review"],
            "acceptance_reviewed": True,
        }
    }
    templates = {
        "circuit_release": [
            {
                "id": "board_design_files",
                "label": "Circuit design files",
                "intake_field": "evidence.board_design_files",
                "required_items": ["board_id", "path", "kind"],
                "template": {
                    "board_design_files": [
                        {"board_id": "main_ctrl", "path": "designs/main_ctrl.net", "kind": "netlist"}
                    ]
                },
            },
            {
                "id": "release_review",
                "label": "Reviewed circuit release scope",
                "intake_field": "evidence.release_review",
                "required_items": ["scope_statement", "acceptance_reviewed=true", "artifact_uris"],
                "template": common_release,
            },
        ],
        "mechanical_release": [
            {
                "id": "mechanical_measurement_capture",
                "label": "Measured geometry",
                "intake_field": "evidence.mechanical_measurement_capture",
                "required_items": ["dimensions", "clearances", "materials or tolerances", "artifact_uris"],
                "template": {
                    "mechanical_measurement_capture": {
                        "artifact_uris": ["evidence://mechanical/caliper-log"],
                        "dimensions": [
                            {"target": "controller_case inner width", "value_mm": 95, "status": "verified"},
                            {"target": "pump_mount width", "value_mm": 55, "status": "verified"},
                            {"target": "tube strain relief", "value_mm": 8, "status": "verified"},
                        ],
                        "clearances": [{"target": "cable and tube routing", "clearance_mm": 1.2, "status": "pass"}],
                    }
                },
            },
            {
                "id": "mechanical_simulation_capture",
                "label": "Fit/load simulation",
                "intake_field": "evidence.mechanical_simulation_capture",
                "required_items": ["simulation rows", "primitive targets", "pass/fail statuses", "artifact_uris"],
                "template": {
                    "mechanical_simulation_capture": {
                        "artifact_uris": ["evidence://mechanical/fit-load-sim"],
                        "simulation_verified": True,
                        "simulation": [
                            {"target": "controller_case enclosure clearance", "status": "pass", "message": "Measured envelope clears board, wiring, and lid."},
                            {"target": "pump_mount retained load", "status": "pass", "message": "Mount load stays below printed bracket limit."},
                            {"target": "watering_module tube routing", "status": "pass", "message": "Tube bend radius and strain relief are inside measured envelope."},
                        ],
                    }
                },
            },
            {
                "id": "mechanical_bench_capture",
                "label": "Mechanical bench",
                "intake_field": "evidence.mechanical_bench_capture",
                "required_items": ["fit_checks", "load_tests", "motion_tests", "artifact_uris"],
                "template": {
                    "mechanical_bench_capture": {
                        "artifact_uris": ["evidence://mechanical/fit-load-bench"],
                        "fit_checks": [{"target": "pump_mount printed fit", "status": "pass"}],
                        "load_tests": [{"target": "pump retained under tubing pull", "status": "pass"}],
                        "motion_tests": [{"target": "tube routing during pump vibration", "status": "pass"}],
                    }
                },
            },
            {
                "id": "release_review",
                "label": "Reviewed mechanical release scope",
                "intake_field": "evidence.release_review",
                "required_items": ["scope_statement", "acceptance_reviewed=true", "artifact_uris"],
                "template": common_release,
            },
        ],
        "robotics_actuation_release": [
            {
                "id": "mechanical_simulation_capture",
                "label": "Actuator load simulation",
                "intake_field": "evidence.mechanical_simulation_capture",
                "required_items": ["actuator load target", "measured geometry link", "pass/fail status", "artifact_uris"],
                "template": {
                    "mechanical_simulation_capture": {
                        "artifact_uris": ["evidence://robotics/actuator-load-sim"],
                        "fit_load_verified": True,
                        "load_tests": [
                            {"target": "pump_mount actuator load path", "status": "pass", "message": "Pump vibration and tubing load remain inside mount allowance."}
                        ],
                    }
                },
            },
            {
                "id": "robotics_bench_capture",
                "label": "First-motion/current bench",
                "intake_field": "evidence.robotics_bench_capture",
                "required_items": ["motion_tests", "current_tests", "failsafe or timeout test", "artifact_uris"],
                "template": {
                    "robotics_bench_capture": {
                        "artifact_uris": ["evidence://robotics/motion-current-bench"],
                        "motion_tests": [{"target": "pump first run", "status": "pass"}],
                        "current_tests": [{"target": "pump startup current below limit", "status": "pass"}],
                        "cycle_tests": [{"target": "timeout shutoff", "status": "pass"}],
                    }
                },
            },
            {
                "id": "release_review",
                "label": "Reviewed robotics release scope",
                "intake_field": "evidence.release_review",
                "required_items": ["scope_statement", "acceptance_reviewed=true", "artifact_uris"],
                "template": common_release,
            },
        ],
        "deterministic_simulation": [
            {
                "id": "mechanical_simulation_capture",
                "label": "Measured simulation evidence",
                "intake_field": "evidence.mechanical_simulation_capture",
                "required_items": ["mechanical simulation rows", "no blocking findings", "artifact_uris"],
                "template": {
                    "mechanical_simulation_capture": {
                        "artifact_uris": ["evidence://simulation/measured-envelope"],
                        "simulation_verified": True,
                        "simulation": [
                            {"target": "power, current, fit, and load margins", "status": "pass", "message": "No measured-envelope blocker found."}
                        ],
                    }
                },
            }
        ],
        "integrated_bench": [
            {
                "id": "integrated_bench_capture",
                "label": "Integrated electrical/mechanical bench",
                "intake_field": "evidence.integrated_bench_capture",
                "required_items": ["electrical_tests", "motion_tests", "packaging_tests", "artifact_uris"],
                "template": {
                    "integrated_bench_capture": {
                        "artifact_uris": ["evidence://system/integrated-bench"],
                        "electrical_tests": [{"target": "logic rail during actuator run", "status": "pass"}],
                        "motion_tests": [{"target": "controlled actuator run with timeout", "status": "pass"}],
                        "packaging_tests": [{"target": "wet/dry separation and cable strain relief", "status": "pass"}],
                    }
                },
            }
        ],
        "field_validation": [
            {
                "id": "field_validation",
                "label": "Field or mission validation",
                "intake_field": "evidence.field_validation",
                "required_items": ["mission_tests", "field_tests", "logs/photos/video/telemetry", "artifact_uris"],
                "template": {
                    "field_validation": {
                        "artifact_uris": ["evidence://field/mission-run"],
                        "mission_tests": [{"target": "declared mission run in operating environment", "status": "pass"}],
                        "field_tests": [{"target": "operator-observed safe stop after mission", "status": "pass"}],
                    }
                },
            }
        ],
        "release_review": [
            {
                "id": "release_review",
                "label": "Reviewed project release scope",
                "intake_field": "evidence.release_review",
                "required_items": ["scope_statement", "acceptance_reviewed=true", "artifact_uris"],
                "template": common_release,
            }
        ],
    }
    return templates.get(gate_id, [])


def _release_scope_example(archetype: str) -> str:
    if archetype == "automatic_watering":
        return "Release limited to supervised low-voltage desk plant watering prototype with current limit, timeout, and leak check."
    if archetype == "rover":
        return "Release limited to low-speed indoor rover testing inside a marked supervised boundary."
    if archetype == "airflow_controller":
        return "Release limited to guarded low-voltage fan/airflow prototype operation under supervised bench conditions."
    return "Release limited to the declared low-voltage supervised Hardware-Splicer prototype envelope."


def _merge_evidence_patch(target: Dict[str, Any], patch: Dict[str, Any]) -> None:
    for key, value in patch.items():
        if key not in target:
            target[key] = value
            continue
        if isinstance(target[key], dict) and isinstance(value, Mapping):
            _merge_evidence_patch(target[key], dict(value))
        elif isinstance(target[key], list) and isinstance(value, list):
            target[key].extend(item for item in value if item not in target[key])


def _dedupe_capture_requests(requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for request in requests:
        key = (str(request.get("gate_id") or ""), str(request.get("request_id") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(request)
    return out


def _archetype_from_build_id(build_id: str, fallback: str) -> str:
    mapping = {
        "automatic_plant_watering": "automatic_watering",
        "robot_drive_base": "rover",
        "usb_fume_extractor": "airflow_controller",
        "inspection_motion_fixture": "pan_tilt",
        "low_voltage_motor_test_jig": "gripper",
        "sensor_logger": "generic_mechatronics",
    }
    return mapping.get(build_id, fallback)


def _compile_spec(
    project_name: str,
    goal: str,
    archetype: str,
    parts: List[Dict[str, Any]],
    constraints: Dict[str, Any],
    budget: Dict[str, Any],
    assumptions: List[str],
    evidence: Dict[str, Any],
    base_dir: Path,
    *,
    salvage_package: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    board = _board(project_name, archetype, parts, constraints)
    mechanism = _mechanism(project_name, archetype, parts)
    robotics_project = _robotics_project(goal, archetype, constraints, budget)
    robotics_actuation = _robotics_actuation(archetype, parts)
    control_stack = _control_stack(archetype, parts)
    safety_case = _safety_case(archetype)
    spec = {
        "project_name": project_name,
        "simulation_fidelity": "starter",
        "run_mechanism_sim": True,
        "use_3d_splicer": False,
        "render_stl": False,
        "machine": {
            "machine_name": _camel(project_name),
            "design_intent": goal,
            "boards": [board],
        },
        "mechanism": mechanism,
        "robotics_project": robotics_project,
        "robotics_actuation": robotics_actuation,
        "control_stack": control_stack,
        "safety_case": safety_case,
        "planning_notes": {
            "assumptions": assumptions,
            "evidence_status": "planning_authority_only",
            "release_status": "bench evidence and reviewed release are not attached by intake planning.",
        },
    }
    salvage = dict(salvage_package or {})
    build_id = str(salvage.get("recommended_build_id") or "") or resolve_build_id(archetype=archetype)
    if build_id:
        spec["build_compilation"] = {
            "enabled": True,
            "build_id": build_id,
            "archetype": archetype,
            "source": "project_intake",
            "goal": goal,
            "graph_mode": salvage.get("graph_mode"),
            "constraints": dict(constraints or {}),
            "salvage_mode": bool(salvage.get("graph_mode") == "scratch"),
            "graph_input": salvage.get("graph_input"),
            "resolved_modules": salvage.get("resolved_modules") or [],
            "module_overrides": salvage.get("module_overrides") or {},
            "splice_verdict": salvage.get("verdict"),
        }
        if salvage.get("splice_plan"):
            spec["build_compilation"]["splice_plan"] = salvage["splice_plan"]
        spec["machine"]["build_compilation"] = dict(spec["build_compilation"])
    _apply_evidence(spec, evidence, base_dir)
    return spec


def _evidence(body: Dict[str, Any]) -> Dict[str, Any]:
    evidence = dict(_to_dict(body.get("evidence") or {}, "intake.evidence"))
    aliases = {
        "board_design_files": ["board_design_files", "board_files"],
        "mechanical_measurement_capture": ["mechanical_measurement_capture", "mechanical_measurements", "measurements"],
        "mechanical_simulation_capture": ["mechanical_simulation_capture", "mechanical_simulation", "simulation_capture", "fit_load_simulation"],
        "mechanical_bench_capture": ["mechanical_bench_capture", "mechanical_bench"],
        "robotics_bench_capture": ["robotics_bench_capture", "robotics_bench", "motion_bench"],
        "integrated_bench_capture": ["integrated_bench_capture", "integrated_bench", "bench_evidence"],
        "field_validation": ["field_validation"],
        "release_review": ["release_review", "release"],
        "releases": ["releases"],
    }
    for canonical, names in aliases.items():
        if evidence.get(canonical):
            continue
        for name in names:
            if body.get(name):
                evidence[canonical] = body[name]
                break
    return evidence


def _apply_evidence(spec: Dict[str, Any], evidence: Dict[str, Any], base_dir: Path) -> None:
    board_files = _board_design_files_from_evidence(evidence, base_dir)
    if board_files:
        spec["board_design_files"] = board_files

    for field in [
        "mechanical_measurement_capture",
        "mechanical_simulation_capture",
        "mechanical_bench_capture",
        "robotics_bench_capture",
        "integrated_bench_capture",
        "field_validation",
    ]:
        capture = _capture_from_evidence(evidence.get(field))
        if capture:
            spec[field] = capture

    release_review = _release_from_evidence(evidence)
    if release_review:
        spec["circuit_release"] = _release_scope(release_review, "Circuit release limited to the planned low-voltage controller and actuator interfaces.")
        spec["mechanical_release"] = _release_scope(release_review, "Mechanical release limited to the planned enclosure, mounts, and printed mechanism primitives.")
        spec["robotics_release"] = _release_scope(release_review, "Robotics release limited to the planned actuator/control envelope.")
        spec["mechatronics_release"] = _release_scope(release_review, "Hardware-Splicer release limited to the integrated planned mechatronics package.")
        spec["robotics_project_release"] = _release_scope(release_review, "Robotics project release limited to the declared mission, operating environment, and evidence package.")


def _board_design_files_from_evidence(evidence: Dict[str, Any], base_dir: Path) -> Dict[str, Dict[str, Any]]:
    raw = evidence.get("board_design_files")
    if not raw:
        return {}
    rows: Dict[str, Any]
    if isinstance(raw, Mapping):
        rows = dict(raw)
    elif isinstance(raw, list):
        rows = {}
        for index, row in enumerate(raw):
            if not isinstance(row, Mapping):
                continue
            fallback_id = "main_ctrl" if index == 0 else f"board_{index}"
            board_id = str(row.get("board_id") or row.get("id") or fallback_id)
            rows[board_id] = row
    else:
        return {}
    normalized: Dict[str, Dict[str, Any]] = {}
    for board_id, meta in rows.items():
        if not isinstance(meta, Mapping):
            continue
        path = str(meta.get("path") or meta.get("file") or "").strip()
        if path and not Path(path).is_absolute():
            path = str((base_dir / path).resolve())
        normalized[str(board_id)] = {"path": path, "kind": str(meta.get("kind") or "netlist")}
    return normalized


def _capture_from_evidence(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, list):
        return {"artifact_uris": [str(item) for item in raw if item]}
    if isinstance(raw, str):
        return {"artifact_uris": [raw]}
    return {}


def _release_from_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    releases = _to_dict(evidence.get("releases") or {}, "evidence.releases")
    if releases:
        combined = {}
        for value in releases.values():
            if isinstance(value, Mapping):
                combined.update(dict(value))
        if combined:
            return combined
    release = _to_dict(evidence.get("release_review") or {}, "evidence.release_review")
    if release:
        return release
    return {}


def _release_scope(release: Dict[str, Any], default_scope: str) -> Dict[str, Any]:
    artifact_uris = _string_list(release.get("artifact_uris") or release.get("artifacts") or release.get("evidence_uris"))
    return {
        "scope_statement": str(release.get("scope_statement") or default_scope),
        "artifact_uris": artifact_uris or ["evidence://intake/release-review"],
        "acceptance_reviewed": bool(release.get("acceptance_reviewed")),
    }


def _evidence_summary(evidence: Dict[str, Any], base_dir: Path) -> Dict[str, Any]:
    return {
        "board_design_file_count": len(_board_design_files_from_evidence(evidence, base_dir)),
        "has_measurements": _has_capture(evidence, "mechanical_measurement_capture"),
        "has_mechanical_simulation": _has_capture(evidence, "mechanical_simulation_capture"),
        "has_mechanical_bench": _has_capture(evidence, "mechanical_bench_capture"),
        "has_robotics_bench": _has_capture(evidence, "robotics_bench_capture"),
        "has_integrated_bench": _has_capture(evidence, "integrated_bench_capture"),
        "has_field_validation": _has_capture(evidence, "field_validation"),
        "release_reviewed": _release_closed(evidence),
    }


def _has_capture(evidence: Dict[str, Any], key: str) -> bool:
    capture = _capture_from_evidence(evidence.get(key))
    if not capture:
        return False
    if (
        capture.get("geometry_verified") is True
        or capture.get("motion_verified") is True
        or capture.get("bench_verified") is True
        or capture.get("simulation_verified") is True
        or capture.get("fit_load_verified") is True
    ):
        return True
    for value in capture.values():
        if isinstance(value, list) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def _release_closed(evidence: Dict[str, Any]) -> bool:
    release = _release_from_evidence(evidence)
    return bool(release.get("acceptance_reviewed") and (_string_list(release.get("artifact_uris") or release.get("artifacts") or release.get("evidence_uris")) or release.get("scope_statement")))


def _board(project_name: str, archetype: str, parts: List[Dict[str, Any]], constraints: Dict[str, Any]) -> Dict[str, Any]:
    controller = _first_part(parts, ["esp32", "arduino", "raspberry_pi_pico", "microcontroller"]) or {"name": "controller", "type": "microcontroller"}
    actuators = [part for part in parts if part["class"] == "actuator"]
    sensors = [part for part in parts if part["class"] == "sensor"]
    peak_current = sum(max(_float(part.get("stall_current_a") or part.get("current_a"), 0.0), 0.0) for part in actuators)
    if peak_current <= 0:
        peak_current = 1.5 if archetype == "automatic_watering" else 1.0
    logic_current = _float(constraints.get("logic_current_a"), 0.35)
    actuator_voltage = _dominant_voltage(actuators, 5.0 if archetype in {"automatic_watering", "airflow_controller"} else 6.0)
    return {
        "board_id": "main_ctrl",
        "name": str(controller.get("name") or "main_ctrl"),
        "lane": "project_intake",
        "estimated_current_a": round(logic_current, 3),
        "pcb_outline_mm": [80, 50, 1.6],
        "capabilities": {
            "pwm_channels": max(2, len([part for part in actuators if part.get("drive") in {"servo_pwm", "mosfet_pwm"}])),
            "stepper_channels": len([part for part in actuators if part.get("type") == "stepper"]),
            "actuation_current_budget_a": round(max(peak_current * 1.35, peak_current + 0.5), 3),
        },
        "requirements": {
            "meta": {
                "design_intent": "planning",
                "project_name": f"{project_name}::main_ctrl",
            },
            "deliverables": {
                "schematic": True,
                "pcb_layout": True,
                "bom": True,
                "bringup_notes": True,
            },
            "interfaces": _interfaces(archetype, sensors, actuators),
            "power": {
                "sources": [
                    {"name": "logic_5v", "voltage_v": 5.0, "max_current_a": max(0.8, logic_current + 0.4)},
                    {"name": "actuator_supply", "voltage_v": actuator_voltage, "max_current_a": round(max(peak_current * 1.35, peak_current + 0.5), 3)},
                ],
                "rails": [
                    {"name": "3V3", "voltage_v": 3.3, "max_current_a": 0.6},
                    {"name": "ACT", "voltage_v": actuator_voltage, "max_current_a": round(max(peak_current * 1.35, peak_current + 0.5), 3)},
                ],
                "loads": [
                    {"name": str(controller.get("name") or "controller"), "rail": "3V3", "current_a": logic_current},
                ]
                + [
                    {"name": str(part.get("name") or part.get("type")), "rail": "ACT", "current_a": _float(part.get("current_a"), 0.4)}
                    for part in actuators
                ],
                "protection": {
                    "fuse_or_ptc": "current-limited actuator rail",
                    "reverse_polarity": "keyed connector or diode/MOSFET protection",
                    "inrush_limit": "bench current limit during first actuation",
                },
            },
            "risk_and_validation": {
                "what_good_looks_like": "Controller powers up, sensors read plausible values, actuator commands run within current limit, and failsafe state stops motion/output.",
                "test_plan": "Bench-test logic rail, actuator rail, sensor readout, first actuation under current limit, failsafe stop, and enclosure clearance.",
                "known_risks": [
                    "Planning intake does not replace physical measurement, wiring inspection, or bench validation.",
                    "Actuator current and thermal margins must be verified with the exact salvaged or purchased part.",
                ],
            },
        },
    }


def _mechanism(project_name: str, archetype: str, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    mechanism: Dict[str, Any] = {
        "project_name": f"{project_name}_mech",
        "mode": "prototype",
        "process": "fdm",
        "enclosure": {
            "name": "controller_case",
            "inner_w_mm": 95,
            "inner_d_mm": 70,
            "inner_h_mm": 32,
            "wall_mm": 2.4,
            "floor_mm": 2.0,
            "lid_mm": 2.0,
            "clearance_mm": 0.6,
        },
    }
    if archetype == "automatic_watering":
        mechanism["bracket"] = {"name": "pump_mount", "w_mm": 55, "d_mm": 35, "t_mm": 3.0}
        mechanism["assembly"] = {
            "name": "watering_module",
            "interfaces": ["controller_case", "pump_mount", "tube strain relief"],
        }
    elif archetype == "rover":
        mechanism["drive_base"] = {
            "name": "wheel_drive_base",
            "length_mm": 180,
            "width_mm": 120,
            "thickness_mm": 3,
            "wheel_d_mm": 65,
            "motor_spacing_mm": 96,
        }
    elif archetype == "airflow_controller":
        mechanism["bracket"] = {"name": "fan_mount", "w_mm": 80, "d_mm": 80, "t_mm": 3.0}
    elif archetype == "pan_tilt":
        servo = _first_part(parts, ["servo"]) or {}
        mechanism["pan_tilt"] = {
            "name": "sensor_head",
            "pan_servo": str(servo.get("model") or "sg90"),
            "tilt_servo": str(servo.get("model") or "sg90"),
            "max_payload_n": 0.8,
            "payload_offset_mm": 35,
        }
    elif archetype == "gripper":
        servo = _first_part(parts, ["servo"]) or {}
        mechanism["gripper"] = {
            "name": "servo_gripper",
            "servo_type": str(servo.get("model") or "sg90"),
            "max_payload_n": 4.0,
            "lever_arm_mm": 45.0,
        }
    else:
        mechanism["bracket"] = {"name": "actuator_mount", "w_mm": 60, "d_mm": 40, "t_mm": 3.0}
    return mechanism


def _robotics_project(goal: str, archetype: str, constraints: Dict[str, Any], budget: Dict[str, Any]) -> Dict[str, Any]:
    runtime_default = 20.0 if archetype == "rover" else 30.0 if budget.get("salvage_mode") else 15.0
    runtime_min = _float(constraints.get("runtime_min") or constraints.get("min_runtime_min"), runtime_default)
    battery_voltage_default = 7.4 if archetype == "rover" else 5.0
    platform = {
        "type": "stationary_mechatronics_module",
        "domains": _domains(archetype),
        "degrees_of_freedom": 1,
    }
    if archetype == "rover":
        platform = {
            "type": "differential_drive_rover",
            "domains": ["locomotion", "sensing", "automation"],
            "degrees_of_freedom": 2,
            "mobility": {"type": "differential_drive", "wheel_count": 2, "caster_count": 1, "wheel_d_mm": 65},
        }
    return {
        "robot_class": archetype,
        "mission": [_mission(archetype, goal)],
        "operating_environment": {
            "domain": "indoor bench/prototype",
            "boundaries": ["low-voltage prototype", "supervised first-use", "current-limited bench bring-up"],
            "hazards": _hazards(archetype),
        },
        "constraints": {
            "runtime_min": runtime_min,
            "mission_duty_cycle": _float(constraints.get("mission_duty_cycle"), 0.35 if archetype == "automatic_watering" else 0.65),
            "baseline_current_a": _float(constraints.get("baseline_current_a"), 0.25),
            "payload_kg": _float(constraints.get("payload_kg"), 0.2),
            "mass_kg": _float(constraints.get("mass_kg"), 1.2 if archetype == "rover" else 1.0),
            "max_speed_mps": _float(constraints.get("max_speed_mps"), 0.5 if archetype == "rover" else 0.0),
            "acceleration_mps2": _float(constraints.get("acceleration_mps2"), 0.5 if archetype == "rover" else 0.0),
        },
        "power": {
            "battery": {
                "chemistry": "USB power bank or small DC adapter",
                "nominal_voltage_v": _float(constraints.get("battery_voltage_v"), battery_voltage_default),
                "capacity_mah": _float(constraints.get("battery_capacity_mah"), 2200.0 if archetype == "rover" else 2000.0),
                "usable_fraction": 0.75,
            }
        },
        "platform": platform,
    }


def _robotics_actuation(archetype: str, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    actuators = [part for part in parts if part["class"] == "actuator"]
    if archetype == "automatic_watering" and not actuators:
        actuators = [_part("mini water pump", "pump", "actuator", voltage_v=5.0, current_a=0.8)]
    if archetype == "airflow_controller" and not actuators:
        actuators = [_part("dc fan", "fan", "actuator", voltage_v=5.0, current_a=0.25)]
    if archetype == "rover" and not actuators:
        actuators = [
            _part(
                "left drive motor",
                "dc_motor",
                "actuator",
                voltage_v=6.0,
                current_a=0.45,
                stall_current_a=0.9,
                output_free_speed_rpm=220,
                stall_torque_nm=0.18,
                role="left wheel drive",
            ),
            _part(
                "right drive motor",
                "dc_motor",
                "actuator",
                voltage_v=6.0,
                current_a=0.45,
                stall_current_a=0.9,
                output_free_speed_rpm=220,
                stall_torque_nm=0.18,
                role="right wheel drive",
            ),
        ]
    if archetype == "gripper" and not actuators:
        actuators = [_part("gripper servo", "servo", "actuator", drive="servo_pwm", voltage_v=5.0, current_a=0.3, stall_current_a=0.8, model="sg90")]
    sensors = [part for part in parts if part["class"] == "sensor"]
    if archetype == "automatic_watering" and not sensors:
        sensors = [_part("soil moisture sensor", "soil_moisture", "sensor")]
    if archetype == "rover" and not sensors:
        sensors = [_part("front range sensor", "tof_range", "sensor"), _part("battery current sensor", "current_sensor", "sensor")]
    return {
        "actuators": [_actuator_row(part) for part in actuators],
        "sensors": [_sensor_row(part) for part in sensors],
        "protections": _protections(archetype, actuators),
    }


def _control_stack(archetype: str, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    controller = _first_part(parts, ["esp32", "arduino", "microcontroller"]) or {"name": "main_ctrl"}
    sensors = [part for part in parts if part["class"] == "sensor"] or _default_sensors(archetype)
    return {
        "controllers": [{"id": "main_ctrl", "board_id": "main_ctrl", "firmware": f"{archetype}_controller"}],
        "loops": _control_loops(archetype),
        "sensors": [_sensor_row(part) for part in sensors],
        "comms": [{"type": "rc_link" if archetype == "rover" else "usb_serial", "failsafe": "signal_loss_stop" if archetype == "rover" else "local_stop"}],
        "failsafes": ["current_limit", "watchdog", "manual_power_cutoff", "timeout_stop"] + (["signal_loss_stop", "e_stop"] if archetype == "rover" else []),
        "notes": f"Controller candidate: {controller.get('name') or 'main_ctrl'}.",
    }


def _safety_case(archetype: str) -> Dict[str, Any]:
    return {
        "hazards": [{"id": item, "mitigation": _mitigation(item), "status": "planned"} for item in _hazards(archetype)],
        "mitigations": [
            "current_limit",
            "manual_power_cutoff",
            "timeout_stop",
            "logic_power_isolation",
            "flyback_or_tvs",
            "separate_actuator_supply",
        ],
    }


def _expected_authority(archetype: str, body: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    default_target = "field_validation_authority" if _release_closed(evidence) else "control_safety_architecture"
    target = str(body.get("target_authority_level") or default_target).strip()
    expected = {"minimum_authority_level": target}
    if not _release_closed(evidence) and archetype in {"automatic_watering", "airflow_controller", "pan_tilt", "rover", "gripper", "generic_mechatronics"}:
        expected["robotics_project_release"] = False
    return expected


def _detect_archetype(goal: str, parts: List[Dict[str, Any]]) -> str:
    from .integrations.qwen_intake_normalize import detect_archetype_llm

    return detect_archetype_llm(goal, parts)


def _evidence_requests(current_level: str, next_level: str | None, missing: List[str], plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    archetype = str(plan.get("archetype") or "generic_mechatronics")
    requests: List[Dict[str, Any]] = []
    if "measured dimensions" in missing or current_level in {"compile_failed", "project_intake", "architecture_project_package", "control_safety_project_package"}:
        requests.append(
            {
                "id": "mechanical_measurement_capture",
                "label": "Measured geometry capture",
                "unlocks": "mechanical load and fit authority",
                "intake_field": "evidence.mechanical_measurement_capture",
                "required_items": [
                    "artifact_uris with photos/sketches/caliper notes",
                    "dimensions for enclosure/mount/drive primitive",
                    "clearances for cables, moving parts, and service access",
                ],
            }
        )
    if "mechanical simulation" in missing or current_level in {"project_intake", "architecture_project_package", "control_safety_project_package"}:
        requests.append(
            {
                "id": "mechanical_simulation_capture",
                "label": "Measured-envelope fit/load simulation",
                "unlocks": "fit/load simulation authority",
                "intake_field": "evidence.mechanical_simulation_capture",
                "required_items": [
                    "simulation or load/fit findings tied to mechanism primitives",
                    "pass/fail status for each simulated target",
                    "artifact_uris for CAD, spreadsheet, notebook, solver output, or calculation log",
                ],
            }
        )
    if "bench evidence" in missing or current_level in {"control_safety_project_package", "architecture_project_package"}:
        requests.extend(
            [
                {
                    "id": "mechanical_bench_capture",
                    "label": "Mechanical fit/load bench",
                    "unlocks": "controlled mechanical fit/load evidence",
                    "intake_field": "evidence.mechanical_bench_capture",
                    "required_items": ["fit_checks", "load_tests", "motion_tests where moving parts exist", "artifact_uris"],
                },
                {
                    "id": "robotics_bench_capture",
                    "label": "First-motion/current bench",
                    "unlocks": "controlled robotics motion evidence",
                    "intake_field": "evidence.robotics_bench_capture",
                    "required_items": ["motion_tests", "current_tests", "timeout/failsafe observation", "artifact_uris"],
                },
                {
                    "id": "integrated_bench_capture",
                    "label": "Integrated electrical/mechanical bench",
                    "unlocks": "simulation/bench project authority",
                    "intake_field": "evidence.integrated_bench_capture",
                    "required_items": ["electrical_tests", "motion_tests", "packaging_tests", "logs/photos/video artifact_uris"],
                },
            ]
        )
    if current_level in {"simulation_bench_project_package", "field_validated_project_package"} or "reviewed release scope" in missing:
        requests.append(
            {
                "id": "release_review",
                "label": "Reviewed scoped release",
                "unlocks": "production-ready project package claim",
                "intake_field": "evidence.release_review",
                "required_items": ["scope_statement", "acceptance_reviewed=true", "artifact_uris"],
            }
        )
    if archetype == "rover":
        requests.append(
            {
                "id": "field_validation",
                "label": "Field validation run",
                "unlocks": "field-validated mobile-platform authority",
                "intake_field": "evidence.field_validation",
                "required_items": ["marked-boundary run", "telemetry/current log", "stop/failsafe observation", "artifact_uris"],
            }
        )
    if not requests:
        requests.append(
            {
                "id": "maintain_evidence_bundle",
                "label": "Maintain release evidence bundle",
                "unlocks": next_level or "current authority",
                "intake_field": "evidence",
                "required_items": ["Keep measurements, bench logs, field logs, and release review tied to the project package."],
            }
        )
    return requests


def _upgrade_recipe(requests: List[Dict[str, Any]]) -> List[str]:
    recipe = []
    for request in requests[:8]:
        items = ", ".join(_string_list(request.get("required_items"))[:3])
        recipe.append(f"Provide `{request.get('intake_field')}` for {request.get('label')}: {items}.")
    return recipe


def _next_project_level(current_level: str) -> str | None:
    if current_level not in PROJECT_LEVELS:
        return "control_safety_project_package"
    index = PROJECT_LEVELS.index(current_level)
    if index + 1 >= len(PROJECT_LEVELS):
        return None
    return PROJECT_LEVELS[index + 1]


def _normalized_parts(data: Any, *, goal: str = "") -> List[Dict[str, Any]]:
    if isinstance(data, Mapping):
        rows = data.get("available_parts") or data.get("parts") or []
    else:
        rows = data
    if not isinstance(rows, list):
        rows = [rows]
    parts = []
    for row in rows:
        if isinstance(row, Mapping):
            part = dict(row)
            name = str(part.get("name") or part.get("part") or part.get("type") or "part")
        else:
            name = str(row)
            part = {"name": name}
        normalized = _classify_part(name, part)
        parts.append(normalized)
    if goal:
        from .integrations.qwen_intake_normalize import classify_intake_parts_llm

        parts = classify_intake_parts_llm(goal, parts)
    return parts


def _classify_part(name: str, part: Dict[str, Any]) -> Dict[str, Any]:
    from .integrations.llm_policy import offline_salvage_enabled, qwen_llm_first

    if qwen_llm_first() and not offline_salvage_enabled():
        ptype = str(part.get("type") or "part").strip()
        pclass = str(part.get("class") or part.get("part_class") or "material").strip()
        return _part(name, ptype, pclass, part)

    text = f"{name} {part.get('type') or ''} {part.get('kind') or ''}".lower()
    if any(word in text for word in ["pump", "solenoid"]):
        return _part(name, "pump" if "pump" in text else "solenoid", "actuator", part)
    if any(word in text for word in ["fan", "blower"]):
        return _part(name, "fan", "actuator", part)
    if "servo" in text or re.search(r"\bsg90\b|\bmg996r\b", text):
        return _part(name, "servo", "actuator", part, drive="servo_pwm", voltage_v=5.0, current_a=0.25)
    if any(word in text for word in ["motor", "dc gear", "gear motor"]):
        return _part(name, "dc_motor", "actuator", part, drive="h_bridge", voltage_v=6.0, current_a=0.5)
    if any(word in text for word in ["soil", "moisture"]):
        return _part(name, "soil_moisture", "sensor", part)
    if any(word in text for word in ["tof", "range", "ultrasonic", "limit", "current sensor", "sensor"]):
        return _part(name, "sensor", "sensor", part)
    if any(word in text for word in ["esp32", "arduino", "pico", "microcontroller", "mcu"]):
        return _part(name, "microcontroller", "controller", part)
    return _part(name, str(part.get("type") or "part"), "material", part)


def _part(
    name: str,
    part_type: str,
    part_class: str,
    source: Mapping[str, Any] | None = None,
    **defaults: Any,
) -> Dict[str, Any]:
    row = dict(defaults)
    if source:
        row.update(dict(source))
    row["name"] = str(row.get("name") or name)
    row["type"] = str(row.get("type") or part_type)
    row["class"] = part_class
    if row["class"] == "actuator":
        row.setdefault("voltage_v", 5.0 if row["type"] in {"pump", "fan", "servo"} else 6.0)
        row.setdefault("current_a", 0.8 if row["type"] == "pump" else 0.3)
        row.setdefault("drive", "low_side_mosfet" if row["type"] in {"pump", "solenoid"} else "mosfet_pwm")
    return row


def _actuator_row(part: Dict[str, Any]) -> Dict[str, Any]:
    row = {
        "id": _slug(str(part.get("id") or part.get("name") or part.get("type") or "actuator")),
        "type": part.get("type"),
        "role": part.get("role") or _role(part),
        "drive": part.get("drive"),
        "voltage_v": _float(part.get("voltage_v"), 5.0),
        "current_a": _float(part.get("current_a"), 0.5),
        "run_current_a": _float(part.get("run_current_a") or part.get("current_a"), 0.5),
        "stall_current_a": _float(part.get("stall_current_a"), max(_float(part.get("current_a"), 0.5) * 1.8, 0.8)),
    }
    for key in ["output_free_speed_rpm", "stall_torque_nm", "wheel_d_mm", "model"]:
        if part.get(key) is not None:
            row[key] = part[key]
    return row


def _sensor_row(part: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": _slug(str(part.get("id") or part.get("name") or "sensor")),
        "type": part.get("type") or "sensor",
        "role": part.get("role") or ("feedback" if part.get("type") != "soil_moisture" else "soil moisture threshold"),
    }


def _interfaces(archetype: str, sensors: List[Dict[str, Any]], actuators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    interfaces = [{"name": "programming", "type": "USB/UART", "voltage_v": 5.0}]
    interfaces.extend({"name": str(sensor.get("name")), "type": "sensor", "voltage_v": 3.3} for sensor in sensors)
    interfaces.extend({"name": str(actuator.get("name")), "type": str(actuator.get("drive") or "actuator_driver"), "voltage_v": _float(actuator.get("voltage_v"), 5.0)} for actuator in actuators)
    if archetype == "automatic_watering":
        interfaces.append({"name": "pump output", "type": "low_side_mosfet", "voltage_v": _dominant_voltage(actuators, 5.0)})
    return interfaces


def _default_sensors(archetype: str) -> List[Dict[str, Any]]:
    if archetype == "automatic_watering":
        return [_part("soil moisture sensor", "soil_moisture", "sensor")]
    if archetype == "rover":
        return [_part("front range sensor", "tof_range", "sensor"), _part("battery current sensor", "current_sensor", "sensor")]
    if archetype == "airflow_controller":
        return [_part("temperature sensor", "temperature", "sensor")]
    if archetype in {"pan_tilt", "gripper"}:
        return [_part("limit/current observation", "current_sensor", "sensor")]
    return [_part("operator state sensor", "sensor", "sensor")]


def _control_loops(archetype: str) -> List[Dict[str, Any]]:
    if archetype == "rover":
        return [
            {"name": "drive_pwm", "rate_hz": 100, "status": "planned"},
            {"name": "failsafe_stop", "rate_hz": 20, "status": "planned"},
        ]
    if archetype == "pan_tilt":
        return [{"name": "pan_tilt_pwm", "rate_hz": 50, "status": "planned"}]
    if archetype == "gripper":
        return [{"name": "gripper_servo", "rate_hz": 50, "status": "planned"}]
    if archetype == "automatic_watering":
        return [{"name": "watering_threshold", "rate_hz": 10, "status": "planned"}]
    return [{"name": f"{archetype}_control", "rate_hz": 50, "status": "planned"}]


def _assumptions(archetype: str, parts: List[Dict[str, Any]], constraints: Dict[str, Any], budget: Dict[str, Any]) -> List[str]:
    assumptions = [
        "This is a planning authority package until measured geometry, wiring inspection, bench logs, and release review are attached.",
        "Actuator current values are treated as estimates unless supplied explicitly in available_parts.",
    ]
    if archetype == "automatic_watering":
        assumptions.append("Pump is driven through a low-side MOSFET or relay module with flyback/TVS protection and timeout shutoff.")
    if not any(part["class"] == "controller" for part in parts):
        assumptions.append("A generic ESP32/Arduino-class controller is assumed.")
    if not budget:
        assumptions.append("No explicit budget was supplied; planner chooses common low-cost prototype parts.")
    if not constraints.get("runtime_min"):
        assumptions.append("Default runtime target is used because constraints.runtime_min was not supplied.")
    return assumptions


def _missing_info(archetype: str, parts: List[Dict[str, Any]], constraints: Dict[str, Any], budget: Dict[str, Any], evidence: Dict[str, Any]) -> List[str]:
    missing = []
    if not any(part["class"] == "controller" for part in parts):
        missing.append("controller choice")
    if not any(part["class"] == "actuator" for part in parts):
        missing.append("actuator model/current")
    if archetype == "automatic_watering" and not any(part["class"] == "sensor" for part in parts):
        missing.append("soil/water feedback sensor")
    if not constraints.get("runtime_min"):
        missing.append("runtime target")
    if not budget:
        missing.append("budget limit")
    if not _has_capture(evidence, "mechanical_measurement_capture"):
        missing.append("measured dimensions")
    if not _has_capture(evidence, "mechanical_simulation_capture"):
        missing.append("mechanical simulation")
    if not (_has_capture(evidence, "mechanical_bench_capture") and _has_capture(evidence, "robotics_bench_capture") and _has_capture(evidence, "integrated_bench_capture")):
        missing.append("bench evidence")
    if not _release_closed(evidence):
        missing.append("reviewed release scope")
    return missing


def _planning_confidence(archetype: str, parts: List[Dict[str, Any]], missing: List[str]) -> float:
    base = 0.45 if archetype == "generic_mechatronics" else 0.62
    base += min(len(parts), 5) * 0.04
    production_evidence = {"measured dimensions", "mechanical simulation", "bench evidence", "reviewed release scope"}
    base -= len([item for item in missing if item not in production_evidence]) * 0.06
    return round(max(0.2, min(base, 0.86)), 2)


def _source_base_dir(body: Dict[str, Any]) -> Path:
    source_file = str(body.get("source_file") or "").strip()
    if source_file:
        return Path(source_file).resolve().parent
    return Path.cwd()


def _budget(body: Dict[str, Any]) -> Dict[str, Any]:
    raw = body.get("budget") or body.get("budget_usd") or body.get("budget_twd")
    if isinstance(raw, Mapping):
        budget = dict(raw)
    elif raw is None:
        budget = {}
    else:
        budget = {"amount": raw}
    if body.get("salvage_mode") is not None:
        budget["salvage_mode"] = bool(body.get("salvage_mode"))
    return budget


def _first_part(parts: List[Dict[str, Any]], tokens: List[str]) -> Dict[str, Any] | None:
    for part in parts:
        text = f"{part.get('name')} {part.get('type')} {part.get('model')}".lower()
        if any(token in text for token in tokens):
            return part
    return None


def _protections(archetype: str, actuators: List[Dict[str, Any]]) -> List[str]:
    protections = ["current_limit", "logic_power_isolation", "manual_power_cutoff", "timeout_stop"]
    if any(part.get("type") in {"pump", "solenoid", "dc_motor", "fan"} for part in actuators):
        protections.extend(["flyback_or_tvs", "separate_actuator_supply"])
    if archetype == "automatic_watering":
        protections.extend(["leak_check", "dry_run_timeout"])
    return sorted(set(protections))


def _domains(archetype: str) -> List[str]:
    if archetype == "automatic_watering":
        return ["fluid_handling", "sensing", "automation"]
    if archetype == "airflow_controller":
        return ["airflow", "thermal", "automation"]
    if archetype == "rover":
        return ["locomotion", "sensing", "automation"]
    return ["motion", "sensing", "automation"]


def _hazards(archetype: str) -> List[str]:
    if archetype == "automatic_watering":
        return ["water_near_electronics", "pump_overcurrent", "dry_run", "leak"]
    if archetype == "airflow_controller":
        return ["fan_blade_contact", "startup_current", "thermal_runaway"]
    if archetype == "rover":
        return ["wheel_pinch", "battery_overcurrent", "signal_loss"]
    return ["actuator_pinch", "overcurrent", "unexpected_motion"]


def _mitigation(hazard: str) -> str:
    mapping = {
        "water_near_electronics": "Separate wet path from enclosure, add drip loop, seal cable entry, and test with low voltage only.",
        "pump_overcurrent": "Current-limit actuator rail and stop on timeout or overcurrent.",
        "dry_run": "Use timeout and reservoir/soil feedback before extended operation.",
        "leak": "Bench leak-test before unattended operation.",
        "fan_blade_contact": "Use guard grille and keep fan shroud closed.",
        "startup_current": "Size MOSFET/supply for startup current and add current limit.",
        "thermal_runaway": "Add thermal/current observation during first runs.",
        "wheel_pinch": "Use low-speed boundary and guarded wheels.",
        "battery_overcurrent": "Fuse or current-limit battery output.",
        "signal_loss": "Stop motion on communication loss.",
    }
    return mapping.get(hazard, "Use current limit, manual power cutoff, guarded mechanism, and supervised bench test.")


def _mission(archetype: str, goal: str) -> str:
    if archetype == "automatic_watering":
        return "Read soil moisture and run a small pump for timed watering within a supervised indoor prototype boundary."
    if archetype == "airflow_controller":
        return "Move air based on sensor/control input while staying inside current and guarding limits."
    if archetype == "rover":
        return "Drive a low-speed mobile platform inside a marked test boundary."
    return goal


def _role(part: Dict[str, Any]) -> str:
    part_type = str(part.get("type") or "")
    if part_type == "pump":
        return "water/fluid output"
    if part_type == "fan":
        return "airflow output"
    if part_type == "servo":
        return "positioned motion"
    return part_type or "actuator"


def _dominant_voltage(parts: List[Dict[str, Any]], default: float) -> float:
    voltages = [_float(part.get("voltage_v"), 0.0) for part in parts]
    voltages = [value for value in voltages if value > 0]
    return voltages[0] if voltages else default


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip().lower()).strip("_-.")
    return slug[:80] or "hardware_splicer_project"


def _camel(value: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[^A-Za-z0-9]+", value) if part) or "HardwareSplicerProject"


def _to_dict(data: Any, name: str) -> Dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise ValueError(f"{name} must be an object")
    return dict(data)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _string_list(data: Any) -> List[str]:
    if data is None:
        return []
    if isinstance(data, str):
        return [data] if data.strip() else []
    if isinstance(data, Iterable) and not isinstance(data, (Mapping, bytes)):
        values = []
        for item in data:
            text = str(item).strip()
            if text:
                values.append(text)
        return values
    return [str(data)]


def _list_dicts(data: Any) -> List[Dict[str, Any]]:
    if not isinstance(data, list):
        return []
    return [dict(item) for item in data if isinstance(item, Mapping)]


def _dedupe_strings(rows: Iterable[str]) -> List[str]:
    out = []
    seen = set()
    for row in rows:
        text = str(row).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out
