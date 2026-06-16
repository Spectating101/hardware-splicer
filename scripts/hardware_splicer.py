#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS_DIR = (ROOT / "scripts").resolve()
sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() != SCRIPTS_DIR]

from hardware_splicer import (
    HardwareCompileSpec,
    compile_catalog_build,
    compile_hardware_bundle,
    load_hardware_scenario,
    load_project_intake,
    resolve_build_id,
    run_hardware_scenario,
    run_project_intake,
)
from hardware_splicer.build_compiler import CATALOG_BUILD_IDS
from hardware_splicer.design_quality import build_design_quality_gate
from hardware_splicer.runtime import runtime_status
from hardware_splicer.validation import validate_compile_spec, validation_errors
from hardware_splicer.fabrication_inspection import inspect_fabrication_package
from hardware_splicer.vision_usage_ledger import usage_summary as vision_usage_summary
from hardware_splicer.text_usage_ledger import usage_summary as text_usage_summary
from hardware_splicer.vision_evidence_assistant import _env_key_present, DEFAULT_QWEN_MODEL
from hardware_splicer.project_intake import splice_and_build_from_intake


DEMO_SPEC = ROOT / "examples" / "hardware_splicer_demo.json"


def _load_spec(path: Path) -> HardwareCompileSpec:
    return HardwareCompileSpec.from_json_file(path)


def _with_cli_overrides(spec: HardwareCompileSpec, args: argparse.Namespace) -> HardwareCompileSpec:
    data = spec.to_dict()
    if getattr(args, "no_3d_splicer", False):
        data["use_3d_splicer"] = False
    if getattr(args, "render_stl", False):
        data["render_stl"] = True
    if getattr(args, "simulation_fidelity", None):
        data["simulation_fidelity"] = args.simulation_fidelity
    return HardwareCompileSpec.from_dict(data)


def _run_compile(args: argparse.Namespace) -> int:
    spec = _with_cli_overrides(_load_spec(Path(args.spec)), args)
    result = compile_hardware_bundle(
        spec,
        out_dir=args.out,
        start_splicer=not args.no_start_splicer,
        splicer_port=int(args.port or 0),
        request_id=getattr(args, "request_id", None),
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"ok={result.ok}")
        print(f"request_id={result.request_id}")
        print(f"out_dir={result.out_dir}")
        print(f"bundle_file={result.bundle_file}")
        print(f"summary_file={result.summary_file}")
        print(f"manifest_file={result.manifest_file}")
        print(f"metadata_file={result.metadata_file}")
        print(f"mecha_bundle_dir={result.mecha_bundle_dir or ''}")
    return 0 if result.ok else 1


def _run_validate(args: argparse.Namespace) -> int:
    spec = _with_cli_overrides(_load_spec(Path(args.spec)), args)
    issues = validate_compile_spec(spec)
    errors = validation_errors(issues)
    if args.json:
        print(json.dumps({"ok": not errors, "issue_count": len(issues), "issues": issues}, indent=2))
    elif issues:
        for issue in issues:
            field = f" {issue.get('field')}" if issue.get("field") else ""
            print(f"{issue.get('severity')} {issue.get('code')}{field}: {issue.get('message')}")
    else:
        print("ok=True")
    return 1 if errors else 0


def _run_scenario(args: argparse.Namespace) -> int:
    scenario = load_hardware_scenario(Path(args.scenario))
    result = run_hardware_scenario(
        scenario,
        out_dir=args.out,
        start_splicer=not args.no_start_splicer,
        splicer_port=int(args.port or 0),
        request_id=getattr(args, "request_id", None),
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        authority = result["project_authority"]
        print(f"ok={result['ok']}")
        print(f"compile_ok={result['compile_ok']}")
        print(f"claimable={authority['claimable']}")
        print(f"authority_level={authority['project_authority_level']}")
        print(f"authority_score={authority['authority_score']}")
        print(f"request_id={result['request_id']}")
        print(f"out_dir={result['out_dir']}")
        print(f"project_authority={result['artifacts']['project_authority']}")
        if authority["blockers"]:
            print("blockers=" + " | ".join(authority["blockers"][:5]))
    return 0 if result["ok"] else 1


def _run_intake(args: argparse.Namespace) -> int:
    intake = load_project_intake(Path(args.brief))
    vision_cfg = dict(intake.get("vision_assistance") or {})
    if getattr(args, "vision_assist", False):
        vision_cfg["enabled"] = True
    if getattr(args, "vision_live", False):
        vision_cfg["live"] = True
        vision_cfg["enabled"] = True
    if getattr(args, "vision_apply", False):
        vision_cfg["apply"] = True
        vision_cfg["enabled"] = True
    if getattr(args, "vision_provider", None):
        vision_cfg["provider"] = args.vision_provider
    if getattr(args, "vision_model", None):
        vision_cfg["model"] = args.vision_model
    if vision_cfg:
        intake["vision_assistance"] = vision_cfg
    result = run_project_intake(
        intake,
        out_dir=args.out,
        start_splicer=not args.no_start_splicer,
        splicer_port=int(args.port or 0),
        request_id=getattr(args, "request_id", None),
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        plan = result["intake_plan"]
        authority = result["project_authority"]
        print(f"ok={result['ok']}")
        print(f"compile_ok={result['compile_ok']}")
        print(f"archetype={plan['archetype']}")
        print(f"planning_confidence={plan['planning_confidence']}")
        print(f"claimable={authority['claimable']}")
        print(f"authority_level={authority['project_authority_level']}")
        print(f"authority_score={authority['authority_score']}")
        print(f"request_id={result['request_id']}")
        print(f"out_dir={result['out_dir']}")
        print(f"project_intake={result['artifacts']['project_intake']}")
        print(f"planned_scenario={result['artifacts']['planned_scenario']}")
        print(f"vision_evidence_report={result['artifacts']['vision_evidence_report']}")
        print(f"evidence_extraction_report={result['artifacts']['evidence_extraction_report']}")
        print(f"evidence_capture_kit={result['artifacts']['evidence_capture_kit']}")
        print(f"project_authority={result['artifacts']['project_authority']}")
        if plan["missing_info"]:
            print("missing_info=" + " | ".join(plan["missing_info"][:8]))
        if authority["blockers"]:
            print("blockers=" + " | ".join(authority["blockers"][:5]))
    return 0 if result["compile_ok"] else 1


def _print_electrical_trust(quality: dict) -> None:
    sim = dict(quality.get("electrical_simulation") or {})
    print(f"simulation_pass={sim.get('pass')}")
    if sim.get("estimated_load_a") is not None:
        print(f"estimated_load_a={sim.get('estimated_load_a')}")
    if quality.get("trust_report_path"):
        print(f"trust_report={quality.get('trust_report_path')}")


def _apply_simulate_env(args: argparse.Namespace) -> None:
    if getattr(args, "no_simulate", False):
        os.environ["HARDWARE_SPLICER_SIMULATE"] = "0"


def _run_netlist_compile(args: argparse.Namespace) -> int:
    _apply_simulate_env(args)
    from hardware_splicer.build_compiler import compile_from_netlist
    from hardware_splicer.integrations.circuit_json_import import circuit_json_to_netlist
    from hardware_splicer.netlist.import_kicad import parse_kicad_netlist
    from hardware_splicer.netlist.ir import CircuitNetlist

    source = Path(args.netlist)
    if not source.is_file():
        print(f"error: netlist file not found: {source}", file=sys.stderr)
        return 2

    text = source.read_text(encoding="utf-8")
    if args.kicad_netlist or source.suffix.lower() == ".net":
        netlist = parse_kicad_netlist(text)
    elif args.circuit_json:
        docs = json.loads(text)
        if not isinstance(docs, list):
            print("error: circuit-json input must be a JSON array", file=sys.stderr)
            return 2
        netlist = circuit_json_to_netlist(docs, source=str(source))
    else:
        payload = json.loads(text)
        netlist = CircuitNetlist.from_dict(payload)

    build_id = str(args.build_id or "generic_low_voltage_build").strip()
    result = compile_from_netlist(
        netlist,
        args.out,
        build_id=build_id,
        export_gerber=not args.no_gerber,
    )
    quality = result.design_quality or {}
    payload = {
        **result.to_dict(),
        "netlist_source": str(source),
        "compile_engine": quality.get("compile_engine"),
        "copper_tier": quality.get("copper_tier"),
        "fab_recommendation": quality.get("fab_recommendation"),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"ok={result.ok}")
        print(f"build_id={result.build_id}")
        print(f"compile_engine={quality.get('compile_engine')}")
        print(f"drc_pass={quality.get('drc_pass')}")
        print(f"kicad_drc_errors={quality.get('kicad_drc_errors')}")
        print(f"electrical_safety_pass={quality.get('electrical_safety_pass')}")
        print(f"copper_tier={quality.get('copper_tier')}")
        _print_electrical_trust(quality)
        print(f"out_dir={args.out}")
        if result.error:
            print(f"error={result.error}")
        casefile = Path(args.out) / "build_compilation" / "COMPILE_CASEFILE.json"
        if casefile.is_file():
            print(f"compile_casefile={casefile}")
    return 0 if result.ok else 1


def _run_compose(args: argparse.Namespace) -> int:
    _apply_simulate_env(args)
    if getattr(args, "netlist_json", None):
        return _run_netlist_compile(
            argparse.Namespace(
                netlist=args.netlist_json,
                kicad_netlist=False,
                circuit_json=False,
                build_id=getattr(args, "build_id", None),
                out=args.out,
                no_gerber=args.no_gerber,
                json=args.json,
            )
        )
    if getattr(args, "arbitrary", False) and args.phrase:
        from hardware_splicer import sdk

        sdk.apply_engine_defaults()
        result = sdk.compose_arbitrary(
            args.phrase,
            out_dir=args.out,
            export_gerber=not args.no_gerber,
        )
        quality = (result.get("design_quality") or {}) if isinstance(result, dict) else {}
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"ok={result.get('ok')}")
            print(f"mode={result.get('mode')}")
            print(f"compose_mode={result.get('compose_mode')}")
            print(f"drc_pass={quality.get('drc_pass')}")
            print(f"out_dir={args.out}")
        return 0 if result.get("ok") else 1

    if not args.phrase and not args.modules and not args.canvas_json:
        print("error: provide --phrase, --modules, --canvas-json, or --netlist-json", file=sys.stderr)
        return 2

    from hardware_splicer.compose_dispatch import compose_dispatch

    constraints = {"strategy_mode": args.strategy_mode, "graph_mode": "canvas" if args.canvas_json else "scratch"}
    salvage_mode = bool(args.salvage_mode)
    canvas_nodes = None
    canvas_wires = None
    if args.canvas_json:
        canvas_doc = json.loads(Path(args.canvas_json).read_text(encoding="utf-8"))
        canvas_nodes = canvas_doc.get("nodes") or []
        canvas_wires = canvas_doc.get("wires")

    payload = compose_dispatch(
        out_dir=args.out,
        phrase=args.phrase,
        module_ids=[m.strip() for m in (args.modules or "").split(",") if m.strip()] or None,
        canvas_nodes=canvas_nodes,
        canvas_wires=canvas_wires,
        constraints=constraints,
        salvage_mode=salvage_mode,
        export_gerber=not args.no_gerber,
        allow_llm_first=False,
    )
    quality = payload.get("design_quality") or {}
    ok = bool(payload.get("ok"))
    hints: list[str] = []
    if args.phrase and not args.canvas_json:
        from hardware_splicer.module_picker import pick_modules_for_goal

        hints = pick_modules_for_goal(args.phrase).hints
        payload = {**payload, "phrase": args.phrase, "hints": hints}

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"ok={ok}")
        print(f"mode={payload.get('mode')}")
        if args.canvas_json:
            print(f"material_mode={payload.get('material_mode')}")
        else:
            print(f"modules={', '.join(payload.get('module_ids') or [])}")
            print(f"attempts={len(payload.get('attempts') or [])}")
        print(f"drc_pass={bool(quality.get('drc_pass'))}")
        print(f"kicad_drc_errors={quality.get('kicad_drc_errors')}")
        _print_electrical_trust(quality)
        print(f"out_dir={args.out}")
        if hints:
            print(f"hints={', '.join(hints)}")
        if payload.get("error"):
            print(f"error={payload.get('error')}")
    return 0 if ok else 1


def _run_jarvis_build(args: argparse.Namespace) -> int:
    _apply_simulate_env(args)
    import os
    from hardware_splicer.jarvis_build import jarvis_build

    if getattr(args, "workshop_trace", False):
        os.environ["HARDWARE_SPLICER_LLM_WORKSHOP"] = "1"
    if getattr(args, "workshop_review", False):
        os.environ["HARDWARE_SPLICER_QWEN_WORKSHOP"] = "1"

    parts = None
    if args.parts_json:
        parts = json.loads(Path(args.parts_json).read_text(encoding="utf-8"))
        if isinstance(parts, dict):
            parts = parts.get("available_parts") or parts.get("parts") or []

    result = jarvis_build(
        args.goal,
        parts=parts,
        out_dir=args.out,
        export_gerber=not args.no_gerber,
        allow_qwen=not args.no_qwen,
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        jarvis = result.get("jarvis") or {}
        quality = result.get("design_quality") or {}
        print(f"ok={result.get('ok')}")
        print(f"mode={result.get('mode')}")
        print(f"compose_mode={result.get('compose_mode')}")
        print(f"llm_first={result.get('llm_first')}")
        print(f"build_id={result.get('build_id')}")
        print(f"module_ids={', '.join(result.get('module_ids') or [])}")
        print(f"drc_pass={quality.get('drc_pass')}")
        print(f"simulation_pass={(quality.get('electrical_simulation') or {}).get('pass')}")
        if jarvis.get("headline"):
            print(f"jarvis_headline={jarvis.get('headline')}")
        if jarvis.get("summary"):
            print(f"jarvis_summary={jarvis.get('summary')}")
        if result.get("artifacts", {}).get("trust_report"):
            print(f"trust_report={result['artifacts']['trust_report']}")
        if result.get("workshop_trace"):
            print(f"workshop_trace={args.out}/LLM_WORKSHOP_TRACE.json")
        print(f"out_dir={args.out}")
    return 0 if result.get("ok") else 1


def _run_llm_workshop(args: argparse.Namespace) -> int:
    import os
    from hardware_splicer.integrations.llm_workshop import (
        run_open_workshop,
        run_salvage_workshop,
        write_workshop_trace,
    )
    from hardware_splicer.project_intake import load_project_intake

    if args.workshop_review:
        os.environ["HARDWARE_SPLICER_QWEN_WORKSHOP"] = "1"

    out = Path(args.out)
    if args.intake:
        intake = load_project_intake(args.intake)
        trace = run_salvage_workshop(
            goal=str(intake.get("goal") or ""),
            parts=list(intake.get("available_parts") or []),
            constraints=dict(intake.get("constraints") or {}),
            compile_probe=args.compile_probe,
            out_dir=out if args.compile_probe else None,
        )
    elif args.goal:
        trace = run_open_workshop(goal=args.goal, constraints={})
    else:
        raise SystemExit("llm-workshop requires --goal or --intake")

    path = write_workshop_trace(trace, out)
    if args.json:
        print(json.dumps(trace, indent=2))
    else:
        print(f"recommendation={trace.get('recommendation')}")
        for step in trace.get("steps") or []:
            tag = "Qwen" if step.get("llm_used") else "det"
            print(f"  [{tag}] {step.get('id')}: {step.get('summary')}")
        print(f"trace={path}")
    return 0


def _run_qwen_models(args: argparse.Namespace) -> int:
    from hardware_splicer.integrations.qwen_model_policy import model_studio_summary

    summary = model_studio_summary()
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0
    active = summary.get("active") or {}
    print(summary.get("quota_note", ""))
    print()
    print("Text stages (primary → rotation):")
    for stage, row in (active.get("text_stages") or {}).items():
        rotation = row.get("rotation") or []
        primary = rotation[0] if rotation else row.get("primary")
        print(f"  [{stage}] {primary}")
        for model in rotation[1:4]:
            print(f"    → {model}")
        if len(rotation) > 4:
            print(f"    … +{len(rotation) - 4} more")
    print()
    print("Vision stages:")
    for stage, row in (active.get("vision_stages") or {}).items():
        rotation = row.get("rotation") or []
        primary = rotation[0] if rotation else row.get("primary")
        print(f"  [{stage}] {primary}")
    print()
    print("Global fallback text rotation:", ", ".join(active.get("text_general") or []))
    print()
    print("Catalog tiers:")
    for tier_id, row in (summary.get("catalog_tiers") or {}).items():
        print(f"  [{tier_id}] {row.get('role')}")
        print(f"    models: {row.get('models')}")
    return 0


def _run_audit_scaffolds(args: argparse.Namespace) -> int:
    import subprocess

    script = Path(__file__).resolve().parent / "audit_weak_scaffolds.py"
    cmd = [sys.executable, str(script)]
    if args.out:
        cmd.append(args.out)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if args.json and args.out:
        print(Path(args.out).read_text(encoding="utf-8"))
    elif args.json:
        out = ROOT / "WEAK_SCAFFOLD_AUDIT.json"
        if out.is_file():
            print(out.read_text(encoding="utf-8"))
    return proc.returncode


def _run_salvage_edit(args: argparse.Namespace) -> int:
    intake = load_project_intake(Path(args.brief))
    edits_path = Path(args.edits)
    edits = json.loads(edits_path.read_text(encoding="utf-8"))
    if not isinstance(edits, list):
        raise SystemExit("edits file must be a JSON array of edit ops")

    from hardware_splicer.project_intake import plan_project_from_intake
    from hardware_splicer.salvage_revision import apply_salvage_edits

    plan = plan_project_from_intake(intake, skip_vision=bool(args.skip_vision))
    base = plan.get("salvage_package") or {}
    goal = str(plan.get("goal") or intake.get("goal") or "").strip()
    parts = list(intake.get("available_parts") or intake.get("parts") or [])
    constraints = dict(intake.get("constraints") or {})
    budget = plan.get("budget") or intake.get("budget")
    revision = apply_salvage_edits(
        goal=goal,
        parts=parts,
        constraints=constraints,
        edits=edits,
        project_name=str(intake.get("project_name") or ""),
        base_package=base,
        budget=budget if isinstance(budget, dict) else None,
    )

    out_path = Path(args.out)
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "SALVAGE_REVISION.json").write_text(json.dumps(revision, indent=2), encoding="utf-8")
    pkg = revision.get("package") or {}
    if pkg:
        (out_path / "SPLICE_PLAN.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")
        if pkg.get("gap_analysis"):
            (out_path / "SALVAGE_GAP_ANALYSIS.json").write_text(
                json.dumps(pkg["gap_analysis"], indent=2), encoding="utf-8"
            )
        if pkg.get("bringup_card"):
            (out_path / "BRINGUP_CARD.json").write_text(json.dumps(pkg["bringup_card"], indent=2), encoding="utf-8")
            (out_path / "BRINGUP_CARD.md").write_text(
                str(pkg["bringup_card"].get("markdown") or ""), encoding="utf-8"
            )
        if pkg.get("bom_estimate"):
            from hardware_splicer.salvage_bom_estimate import write_salvage_bom_artifacts

            write_salvage_bom_artifacts(pkg["bom_estimate"], out_path)
        if pkg.get("firmware_scaffold"):
            from hardware_splicer.firmware_scaffold import write_salvage_firmware

            write_salvage_firmware(
                build_id=str(pkg.get("recommended_build_id") or "salvage_build"),
                salvage_package=pkg,
                goal=goal,
                out_dir=out_path,
            )

    if args.json:
        print(json.dumps(revision, indent=2))
    else:
        diff = revision.get("diff") or {}
        print(f"out_dir={out_path}")
        print(f"parts_after={len(revision.get('parts_after') or [])}")
        if diff:
            print(f"modules_added={', '.join(diff.get('modules_added') or [])}")
            print(f"modules_removed={', '.join(diff.get('modules_removed') or [])}")
            print(f"ready_before={diff.get('ready_before')} ready_after={diff.get('ready_after')}")
    return 0


def _run_splice_build(args: argparse.Namespace) -> int:
    _apply_simulate_env(args)
    intake = load_project_intake(Path(args.brief))
    result = splice_and_build_from_intake(
        intake,
        out_dir=args.out,
        export_gerber=not args.no_gerber,
        request_id=getattr(args, "request_id", None),
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        salvage = result.get("salvage_package") or {}
        print(f"ok={result.get('ok')}")
        print(f"build_id={result.get('build_id')}")
        print(f"graph_mode={salvage.get('graph_mode')}")
        print(f"compose_modules={', '.join(salvage.get('compose_module_ids') or [])}")
        quality = (result.get("build_compilation") or {}).get("design_quality") or {}
        print(f"drc_pass={quality.get('drc_pass')}")
        _print_electrical_trust(quality)
        print(f"out_dir={args.out}")
    return 0 if result.get("ok") else 1


def _run_build(args: argparse.Namespace) -> int:
    _apply_simulate_env(args)
    build_id = resolve_build_id(archetype=args.archetype, explicit=args.build_id)
    if not build_id:
        print("error: provide --build-id or --archetype that maps to a catalog build", file=sys.stderr)
        return 2
    result = compile_catalog_build(
        build_id,
        args.out,
        export_gerber=not args.no_gerber,
    )
    gate = build_design_quality_gate(result.design_quality)
    out_path = Path(args.out)
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "DESIGN_QUALITY_GATE.json").write_text(json.dumps(gate, indent=2), encoding="utf-8")
    payload = {
        **result.to_dict(),
        "design_quality_gate": gate,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        quality = result.design_quality
        print(f"ok={result.ok}")
        print(f"build_id={build_id}")
        print(f"out_dir={result.out_dir}")
        print(f"kicad_pcb_file={result.kicad_pcb_file or ''}")
        print(f"design_quality_file={result.design_quality_file}")
        print(f"build_ready={bool(quality.get('build_ready'))}")
        print(f"drc_pass={bool(quality.get('drc_pass'))}")
        print(f"gerber_ready={bool(quality.get('gerber_ready'))}")
        _print_electrical_trust(quality)
        print(f"gerber_package_dir={result.gerber_package_dir or ''}")
        if result.error:
            print(f"error={result.error}")
    return 0 if result.ok and gate.get("build_ready") else 1


def _run_doctor(args: argparse.Namespace) -> int:
    status = runtime_status(splicer_url=args.splicer_url)
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(f"ok={status.get('ok')}")
        print(f"demo_ready={status.get('demo_ready')}")
        print(f"fab_export_ready={status.get('fab_export_ready')}")
        print(f"python={status.get('python')}")
        deps = status.get("dependencies") or {}
        print("dependencies=" + ", ".join(f"{key}:{'ok' if value else 'missing'}" for key, value in sorted(deps.items())))
        roots = status.get("app_roots") or {}
        for name, row in sorted(roots.items()):
            print(f"{name}={row.get('path')} exists={row.get('exists')}")
        if status.get("splicer3d_health"):
            health = status["splicer3d_health"]
            print(f"splicer3d={health.get('url')} ok={health.get('ok')}")
        qwen_ready = _env_key_present("QWEN_API_KEY", "DASHSCOPE_API_KEY")
        usage = vision_usage_summary(provider="qwen")
        print(f"qwen_vision_key={'configured' if qwen_ready else 'missing'} default_model={DEFAULT_QWEN_MODEL}")
        print(f"vision_usage_calls={usage.get('call_count')} vision_usage_tokens={usage.get('total_tokens')}")
        if status.get("testing_mode"):
            print(f"testing_mode=on blocker={status.get('testing_mode_blocker')}")
    return 0 if status.get("ok") else 1


def _run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "hardware_splicer.api:app",
        host=args.host,
        port=int(args.port),
        reload=False,
    )
    return 0


def _run_inspect_fab(args: argparse.Namespace) -> int:
    build_dir = Path(args.build_dir)
    compilation_dir = build_dir / "build_compilation" if (build_dir / "build_compilation").is_dir() else build_dir
    compilation_path = compilation_dir / "BUILD_COMPILATION.json"
    if not compilation_path.is_file():
        compilation_path = build_dir / "BUILD_COMPILATION.json"
    build_compilation = {}
    if compilation_path.is_file():
        build_compilation = json.loads(compilation_path.read_text(encoding="utf-8"))
    pcb_candidates = sorted(compilation_dir.glob("*.kicad_pcb"))
    artifacts = {
        "build_kicad_pcb": str(pcb_candidates[0]) if pcb_candidates else str(compilation_dir / "build.kicad_pcb"),
        "fab_package_zip": str(compilation_dir / "fab_package.zip") if (compilation_dir / "fab_package.zip").is_file() else str(build_dir / "fab_package.zip"),
        "bom": str(compilation_dir / "BOM.json"),
        "out_dir": str(build_dir),
    }
    result = inspect_fabrication_package(build_compilation=build_compilation, artifacts=artifacts)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"inspection_score={result.get('inspection_score')}")
        print(f"honest_fabrication_ready={result.get('honest_fabrication_ready')}")
        print(f"prototype_breakout_only={result.get('prototype_breakout_only')}")
        print(f"summary={result.get('summary')}")
        for row in result.get("checks") or []:
            if not row.get("passed"):
                print(f"FAIL {row.get('id')}: {row.get('label')} (observed={row.get('observed')})")
    return 0 if result.get("honest_fabrication_ready") else 1


def _run_vision_usage(args: argparse.Namespace) -> int:
    summary = vision_usage_summary(provider=args.provider)
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0
    print(f"provider={summary.get('provider')}")
    print(f"ledger={summary.get('ledger_path')}")
    print(f"calls={summary.get('call_count')} total_tokens={summary.get('total_tokens')}")
    print(f"month_tokens={summary.get('month_tokens')} day_tokens={summary.get('day_tokens')}")
    for model, stats in sorted((summary.get("by_model") or {}).items()):
        print(f"{model}: calls={stats.get('calls')} tokens={stats.get('total_tokens')}")
    for model, estimate in sorted((summary.get("free_tier_estimates") or {}).items()):
        remaining = estimate.get("estimated_remaining_tokens")
        if remaining is not None:
            print(
                f"{model}_estimated_remaining={remaining} "
                f"(tracked_consumed={estimate.get('tracked_consumed_tokens')})"
            )
    return 0


def _run_text_usage(args: argparse.Namespace) -> int:
    summary = text_usage_summary(provider=args.provider or None)
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0
    print(f"ledger={summary.get('ledger_path')}")
    print(
        f"calls={summary.get('call_count')} cache_hits={summary.get('cache_hits')} "
        f"total_tokens={summary.get('total_tokens')}"
    )
    print(f"month_tokens={summary.get('month_tokens')} day_tokens={summary.get('day_tokens')}")
    for stage, stats in sorted((summary.get("by_stage") or {}).items()):
        print(
            f"stage={stage} calls={stats.get('calls')} cached={stats.get('cached_calls')} "
            f"tokens={stats.get('total_tokens')}"
        )
    for model, stats in sorted((summary.get("by_model") or {}).items()):
        print(f"{model}: calls={stats.get('calls')} tokens={stats.get('total_tokens')}")
    return 0


def _run_llm_quota(args: argparse.Namespace) -> int:
    import subprocess

    cmd = [sys.executable, str(ROOT / "scripts" / "qwen_quota_audit.py")]
    if args.json:
        cmd.append("--json")
    if args.probe:
        cmd.append("--probe")
    if args.probe_limit:
        cmd.extend(["--probe-limit", str(args.probe_limit)])
    return int(subprocess.call(cmd))


def main() -> int:
    parser = argparse.ArgumentParser(description="Hardware-Splicer compiler CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    compile_parser = sub.add_parser("compile", help="Compile a hardware bundle from a JSON spec.")
    compile_parser.add_argument("--spec", required=True, help="Path to HardwareCompileSpec JSON.")
    compile_parser.add_argument("--out", required=True, help="Output directory.")
    compile_parser.add_argument("--port", type=int, default=0, help="3D-Splicer port. Defaults to a free local port.")
    compile_parser.add_argument("--no-start-splicer", action="store_true", help="Use an already running 3D-Splicer service.")
    compile_parser.add_argument("--no-3d-splicer", action="store_true", help="Skip optional 3D-Splicer calls.")
    compile_parser.add_argument("--render-stl", action="store_true", help="Ask 3D-Splicer for STL output instead of script output.")
    compile_parser.add_argument("--simulation-fidelity", choices=["starter", "high"], default=None)
    compile_parser.add_argument("--request-id", default=None, help="Stable build/request identifier for manifests and API parity.")
    compile_parser.add_argument("--json", action="store_true", help="Print result JSON.")
    compile_parser.set_defaults(func=_run_compile)

    validate_parser = sub.add_parser("validate", help="Validate a compile spec without running Circuit-AI/Mecha-Splicer.")
    validate_parser.add_argument("--spec", required=True, help="Path to HardwareCompileSpec JSON.")
    validate_parser.add_argument("--no-3d-splicer", action="store_true", help="Apply the same 3D override as compile.")
    validate_parser.add_argument("--render-stl", action="store_true", help="Apply the same STL override as compile.")
    validate_parser.add_argument("--simulation-fidelity", choices=["starter", "high"], default=None)
    validate_parser.add_argument("--json", action="store_true", help="Print validation JSON.")
    validate_parser.set_defaults(func=_run_validate)

    scenario_parser = sub.add_parser("scenario", help="Run a Hardware-Splicer scenario and emit project authority artifacts.")
    scenario_parser.add_argument("--scenario", required=True, help="Path to Hardware-Splicer scenario JSON.")
    scenario_parser.add_argument("--out", required=True, help="Output directory.")
    scenario_parser.add_argument("--port", type=int, default=0, help="3D-Splicer port. Defaults to a free local port.")
    scenario_parser.add_argument("--no-start-splicer", action="store_true", help="Use an already running 3D-Splicer service.")
    scenario_parser.add_argument("--request-id", default=None, help="Stable build/request identifier for manifests and API parity.")
    scenario_parser.add_argument("--json", action="store_true", help="Print scenario result JSON.")
    scenario_parser.set_defaults(func=_run_scenario)

    intake_parser = sub.add_parser("intake", help="Plan and run a Hardware-Splicer project from a user-style brief.")
    intake_parser.add_argument("--brief", required=True, help="Path to project intake JSON.")
    intake_parser.add_argument("--out", required=True, help="Output directory.")
    intake_parser.add_argument("--port", type=int, default=0, help="3D-Splicer port. Defaults to a free local port.")
    intake_parser.add_argument("--no-start-splicer", action="store_true", help="Use an already running 3D-Splicer service.")
    intake_parser.add_argument("--request-id", default=None, help="Stable build/request identifier for manifests and API parity.")
    intake_parser.add_argument("--vision-assist", action="store_true", help="Enable vision evidence assistance for image attachments.")
    intake_parser.add_argument("--vision-live", action="store_true", help="Allow live vision model calls. Requires provider credentials.")
    intake_parser.add_argument("--vision-apply", action="store_true", help="Apply candidate vision evidence notes before deterministic extraction.")
    intake_parser.add_argument("--vision-provider", default=None, help="Vision provider id. Default: qwen.")
    intake_parser.add_argument("--vision-model", default=None, help="Vision model id. Default for qwen: qwen3-vl-flash.")
    intake_parser.add_argument("--json", action="store_true", help="Print intake run result JSON.")
    intake_parser.set_defaults(func=_run_intake)

    compose_parser = sub.add_parser(
        "compose",
        help="NL or explicit module list → auto-wired scratch graph → DRC-clean KiCad PCB.",
    )
    compose_parser.add_argument("--phrase", default=None, help="Natural-language goal (module picker).")
    compose_parser.add_argument(
        "--modules",
        default=None,
        help="Comma-separated module ids (e.g. usb-power-5v,esp32-devkit,dht22).",
    )
    compose_parser.add_argument("--strategy-mode", choices=["open", "constrained"], default="open")
    compose_parser.add_argument("--salvage-mode", action="store_true", help="Constrain to inventory + allowed_purchases.")
    compose_parser.add_argument(
        "--canvas-json",
        default=None,
        help="Path to JSON {nodes:[{id,moduleId}], wires?:[...]} for editor/canvas compose.",
    )
    compose_parser.add_argument("--out", required=True, help="Output directory.")
    compose_parser.add_argument("--no-gerber", action="store_true", help="Skip kicad-cli Gerber export when available.")
    compose_parser.add_argument("--no-simulate", action="store_true", help="Skip ngspice power simulation gate.")
    compose_parser.add_argument(
        "--netlist-json",
        default=None,
        help="Compile hardware_splicer.netlist.v1 JSON directly (general engine path).",
    )
    compose_parser.add_argument(
        "--arbitrary",
        action="store_true",
        help="NL → Qwen text netlist IR → compile (requires API key).",
    )
    compose_parser.add_argument("--build-id", default=None, help="Target build id for netlist compile.")
    compose_parser.add_argument("--json", action="store_true", help="Print compose result JSON.")
    compose_parser.set_defaults(func=_run_compose)

    netlist_compile_parser = sub.add_parser(
        "netlist-compile",
        help="Compile netlist IR (JSON, KiCad .net, or circuit-json) → KiCad PCB + DESIGN_QUALITY.",
    )
    netlist_compile_parser.add_argument("--netlist", required=True, help="Path to netlist file.")
    netlist_compile_parser.add_argument("--out", required=True, help="Output directory.")
    netlist_compile_parser.add_argument("--build-id", default="generic_low_voltage_build")
    netlist_compile_parser.add_argument("--kicad-netlist", action="store_true", help="Parse KiCad .net format.")
    netlist_compile_parser.add_argument("--circuit-json", action="store_true", help="Parse circuit-json array.")
    netlist_compile_parser.add_argument("--no-gerber", action="store_true")
    netlist_compile_parser.add_argument("--no-simulate", action="store_true")
    netlist_compile_parser.add_argument("--json", action="store_true")
    netlist_compile_parser.set_defaults(func=_run_netlist_compile)

    splice_build_parser = sub.add_parser(
        "splice-build",
        help="Intake brief → salvage/scratch or catalog graph → DRC-clean PCB (no full mecha scenario).",
    )
    splice_build_parser.add_argument("--brief", required=True, help="Path to project intake JSON.")
    splice_build_parser.add_argument("--out", required=True, help="Output directory.")
    splice_build_parser.add_argument("--no-gerber", action="store_true", help="Skip Gerber export.")
    splice_build_parser.add_argument("--no-simulate", action="store_true", help="Skip ngspice power simulation gate.")
    splice_build_parser.add_argument("--request-id", default=None, help="Stable build/request identifier.")
    splice_build_parser.add_argument("--json", action="store_true", help="Print splice-build result JSON.")
    splice_build_parser.set_defaults(func=_run_splice_build)

    salvage_edit_parser = sub.add_parser(
        "salvage-edit",
        help="Apply incremental salvage edits (add/remove parts or modules) and emit revised artifacts.",
    )
    salvage_edit_parser.add_argument("--brief", required=True, help="Path to project intake JSON.")
    salvage_edit_parser.add_argument("--edits", required=True, help="JSON file: array of edit ops.")
    salvage_edit_parser.add_argument("--out", required=True, help="Output directory.")
    salvage_edit_parser.add_argument("--skip-vision", action="store_true", help="Skip vision API during replan.")
    salvage_edit_parser.add_argument("--json", action="store_true", help="Print revision JSON.")
    salvage_edit_parser.set_defaults(func=_run_salvage_edit)

    jarvis_parser = sub.add_parser(
        "jarvis-build",
        help="LLM-aware electrical build: goal (+ optional parts JSON) → compile → trust → JARVIS narrative.",
    )
    jarvis_parser.add_argument("--goal", required=True, help="Natural-language build goal.")
    jarvis_parser.add_argument("--parts-json", default=None, help="Optional intake/salvage parts JSON file.")
    jarvis_parser.add_argument("--out", required=True, help="Output directory.")
    jarvis_parser.add_argument("--no-gerber", action="store_true", help="Skip Gerber export.")
    jarvis_parser.add_argument("--no-qwen", action="store_true", help="Disable Qwen netlist + JARVIS narrative.")
    jarvis_parser.add_argument("--workshop-trace", action="store_true", help="Write LLM_WORKSHOP_TRACE.json per build step.")
    jarvis_parser.add_argument("--workshop-review", action="store_true", help="Enable Qwen salvage workshop review (HARDWARE_SPLICER_QWEN_WORKSHOP=1).")
    jarvis_parser.add_argument("--no-simulate", action="store_true", help="Skip ngspice power simulation gate.")
    jarvis_parser.add_argument("--json", action="store_true", help="Print full result JSON.")
    jarvis_parser.set_defaults(func=_run_jarvis_build)

    workshop_parser = sub.add_parser(
        "llm-workshop",
        help="Step-by-step probe: where Qwen helps vs heuristics (no full build unless --compile-probe).",
    )
    workshop_parser.add_argument("--goal", default=None, help="Open-mode NL goal.")
    workshop_parser.add_argument("--intake", default=None, help="Salvage intake JSON path.")
    workshop_parser.add_argument("--out", default="/tmp/llm_workshop_probe", help="Output directory.")
    workshop_parser.add_argument("--workshop-review", action="store_true", help="Enable Qwen workshop review step.")
    workshop_parser.add_argument("--compile-probe", action="store_true", help="Run DRC compile probe (salvage).")
    workshop_parser.add_argument("--json", action="store_true", help="Print trace JSON.")
    workshop_parser.set_defaults(func=_run_llm_workshop)

    audit_parser = sub.add_parser(
        "audit-scaffolds",
        help="List regex/keyword weak paths vs LLM-first replacements.",
    )
    audit_parser.add_argument("--out", default=None, help="Write WEAK_SCAFFOLD_AUDIT.json path.")
    audit_parser.add_argument("--json", action="store_true", help="Print full audit JSON.")
    audit_parser.set_defaults(func=_run_audit_scaffolds)

    qwen_models_parser = sub.add_parser(
        "qwen-models",
        help="Show Qwen Model Studio tiers and active text/vision rotation.",
    )
    qwen_models_parser.add_argument("--json", action="store_true", help="Print full catalog JSON.")
    qwen_models_parser.set_defaults(func=_run_qwen_models)

    build_parser = sub.add_parser("build", help="Compile a catalog build to DRC-clean KiCad PCB (+ optional Gerbers).")
    build_parser.add_argument("--build-id", default=None, help=f"Catalog build id. One of: {', '.join(CATALOG_BUILD_IDS[:5])}, ...")
    build_parser.add_argument("--archetype", default=None, help="Intake archetype alias (e.g. automatic_watering, rover).")
    build_parser.add_argument("--out", required=True, help="Output directory.")
    build_parser.add_argument("--no-gerber", action="store_true", help="Skip kicad-cli Gerber export when available.")
    build_parser.add_argument("--no-simulate", action="store_true", help="Skip ngspice power simulation gate.")
    build_parser.add_argument("--json", action="store_true", help="Print compile result JSON.")
    build_parser.set_defaults(func=_run_build)

    demo_parser = sub.add_parser("demo", help="Compile the canonical controller plus pan-tilt demo.")
    demo_parser.add_argument("--out", default="/tmp/hardware_splicer_demo", help="Output directory.")
    demo_parser.add_argument("--port", type=int, default=0, help="3D-Splicer port. Defaults to a free local port.")
    demo_parser.add_argument("--no-start-splicer", action="store_true", help="Use an already running 3D-Splicer service.")
    demo_parser.add_argument("--no-3d-splicer", action="store_true", help="Skip optional 3D-Splicer calls.")
    demo_parser.add_argument("--render-stl", action="store_true", help="Ask 3D-Splicer for STL output instead of script output.")
    demo_parser.add_argument("--simulation-fidelity", choices=["starter", "high"], default=None)
    demo_parser.add_argument("--request-id", default=None, help="Stable build/request identifier for manifests and API parity.")
    demo_parser.add_argument("--json", action="store_true", help="Print result JSON.")
    demo_parser.set_defaults(spec=str(DEMO_SPEC), func=_run_compile)

    doctor_parser = sub.add_parser("doctor", help="Inspect local production readiness for Hardware-Splicer runtime dependencies.")
    doctor_parser.add_argument("--splicer-url", default=None, help="Optional running 3D-Splicer URL to health-check.")
    doctor_parser.add_argument("--json", action="store_true", help="Print full status JSON.")
    doctor_parser.set_defaults(func=_run_doctor)

    serve_parser = sub.add_parser("serve", help="Run the Hardware-Splicer compiler API.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8090)
    serve_parser.set_defaults(func=_run_serve)

    vision_usage_parser = sub.add_parser("vision-usage", help="Show local Qwen/Gemini vision token usage tracked by Hardware-Splicer.")
    vision_usage_parser.add_argument("--provider", default="qwen", choices=["qwen", "gemini"], help="Provider to summarize.")
    vision_usage_parser.add_argument("--json", action="store_true", help="Print usage summary JSON.")
    vision_usage_parser.set_defaults(func=_run_vision_usage)

    text_usage_parser = sub.add_parser("text-usage", help="Show local text LLM usage (Qwen, agy) and cache hits.")
    text_usage_parser.add_argument("--provider", default=None, help="Optional provider filter (qwen, agy).")
    text_usage_parser.add_argument("--json", action="store_true", help="Print usage summary JSON.")
    text_usage_parser.set_defaults(func=_run_text_usage)

    llm_quota_parser = sub.add_parser("llm-quota", help="Audit DashScope pools from local ledgers + optional probe.")
    llm_quota_parser.add_argument("--probe", action="store_true", help="Ping each rotation model (costs a few tokens).")
    llm_quota_parser.add_argument("--probe-limit", type=int, default=0, help="Max models to probe (0 = all).")
    llm_quota_parser.add_argument("--json", action="store_true", help="Print JSON report.")
    llm_quota_parser.set_defaults(func=_run_llm_quota)

    inspect_fab_parser = sub.add_parser(
        "inspect-fab",
        help="Inspect fab outputs on disk (PCB, BOM, Gerbers) — not just whether files exist.",
    )
    inspect_fab_parser.add_argument("--build-dir", required=True, help="Catalog build or splice output directory.")
    inspect_fab_parser.add_argument("--json", action="store_true", help="Print inspection JSON.")
    inspect_fab_parser.set_defaults(func=_run_inspect_fab)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
