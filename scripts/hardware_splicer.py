#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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
from hardware_splicer.vision_usage_ledger import usage_summary
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


def _run_compose(args: argparse.Namespace) -> int:
    from hardware_splicer.module_picker import pick_modules_for_goal
    from hardware_splicer.canvas_compose import compile_canvas_build
    from hardware_splicer.scratch_pipeline import compile_scratch_build

    hints: list[str] = []
    if args.phrase:
        pick = pick_modules_for_goal(args.phrase)
        hints = pick.hints
    elif not args.modules and not args.canvas_json:
        print("error: provide --phrase, --modules, or --canvas-json", file=sys.stderr)
        return 2

    constraints = {"strategy_mode": args.strategy_mode, "graph_mode": "canvas" if args.canvas_json else "scratch"}
    salvage_mode = bool(args.salvage_mode)

    if args.canvas_json:
        canvas_doc = json.loads(Path(args.canvas_json).read_text(encoding="utf-8"))
        canvas = compile_canvas_build(
            out_dir=args.out,
            nodes=canvas_doc.get("nodes") or [],
            wires=canvas_doc.get("wires"),
            constraints=constraints,
            salvage_mode=salvage_mode,
            export_gerber=not args.no_gerber,
        )
        compile_result = canvas.compile_result
        quality = (compile_result.design_quality if compile_result else {}) or {}
        payload = {
            **canvas.to_dict(),
            "drc_pass": bool(quality.get("drc_pass")),
            "build_ready": bool(quality.get("build_ready")),
            "kicad_drc_errors": quality.get("kicad_drc_errors"),
        }
        ok = canvas.ok
    else:
        scratch = compile_scratch_build(
            out_dir=args.out,
            goal=args.phrase,
            module_ids=[m.strip() for m in (args.modules or "").split(",") if m.strip()] or None,
            export_gerber=not args.no_gerber,
            constraints=constraints,
            salvage_mode=salvage_mode,
        )
        compile_result = scratch.compile_result
        quality = (compile_result.design_quality if compile_result else {}) or {}
        payload = {
            **scratch.to_dict(),
            "phrase": args.phrase,
            "hints": hints,
            "drc_pass": bool(quality.get("drc_pass")),
            "build_ready": bool(quality.get("build_ready")),
        }
        ok = scratch.ok

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"ok={ok}")
        if args.canvas_json:
            print(f"mode=canvas material_mode={payload.get('material_mode')}")
        else:
            print(f"modules={', '.join(payload.get('module_ids') or [])}")
            print(f"attempts={len(payload.get('attempts') or [])}")
        print(f"drc_pass={bool(quality.get('drc_pass'))}")
        print(f"kicad_drc_errors={quality.get('kicad_drc_errors')}")
        print(f"out_dir={args.out}")
        if hints:
            print(f"hints={', '.join(hints)}")
        if payload.get("error"):
            print(f"error={payload.get('error')}")
    return 0 if ok else 1


def _run_splice_build(args: argparse.Namespace) -> int:
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
        print(f"drc_pass={((result.get('build_compilation') or {}).get('design_quality') or {}).get('drc_pass')}")
        print(f"out_dir={args.out}")
    return 0 if result.get("ok") else 1


def _run_build(args: argparse.Namespace) -> int:
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
        usage = usage_summary(provider="qwen")
        print(f"qwen_vision_key={'configured' if qwen_ready else 'missing'} default_model={DEFAULT_QWEN_MODEL}")
        print(f"vision_usage_calls={usage.get('call_count')} vision_usage_tokens={usage.get('total_tokens')}")
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
    summary = usage_summary(provider=args.provider)
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
    compose_parser.add_argument("--json", action="store_true", help="Print compose result JSON.")
    compose_parser.set_defaults(func=_run_compose)

    splice_build_parser = sub.add_parser(
        "splice-build",
        help="Intake brief → salvage/scratch or catalog graph → DRC-clean PCB (no full mecha scenario).",
    )
    splice_build_parser.add_argument("--brief", required=True, help="Path to project intake JSON.")
    splice_build_parser.add_argument("--out", required=True, help="Output directory.")
    splice_build_parser.add_argument("--no-gerber", action="store_true", help="Skip Gerber export.")
    splice_build_parser.add_argument("--request-id", default=None, help="Stable build/request identifier.")
    splice_build_parser.add_argument("--json", action="store_true", help="Print splice-build result JSON.")
    splice_build_parser.set_defaults(func=_run_splice_build)

    build_parser = sub.add_parser("build", help="Compile a catalog build to DRC-clean KiCad PCB (+ optional Gerbers).")
    build_parser.add_argument("--build-id", default=None, help=f"Catalog build id. One of: {', '.join(CATALOG_BUILD_IDS[:5])}, ...")
    build_parser.add_argument("--archetype", default=None, help="Intake archetype alias (e.g. automatic_watering, rover).")
    build_parser.add_argument("--out", required=True, help="Output directory.")
    build_parser.add_argument("--no-gerber", action="store_true", help="Skip kicad-cli Gerber export when available.")
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
