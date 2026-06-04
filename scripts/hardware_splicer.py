#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) in sys.path:
    sys.path.remove(str(SRC))
sys.path.insert(0, str(SRC))

from hardware_splicer import HardwareCompileSpec, compile_hardware_bundle, load_hardware_scenario, run_hardware_scenario
from hardware_splicer.runtime import runtime_status
from hardware_splicer.validation import validate_compile_spec, validation_errors


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


def _run_doctor(args: argparse.Namespace) -> int:
    status = runtime_status(splicer_url=args.splicer_url)
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(f"ok={status.get('ok')}")
        print(f"python={status.get('python')}")
        deps = status.get("dependencies") or {}
        print("dependencies=" + ", ".join(f"{key}:{'ok' if value else 'missing'}" for key, value in sorted(deps.items())))
        roots = status.get("app_roots") or {}
        for name, row in sorted(roots.items()):
            print(f"{name}={row.get('path')} exists={row.get('exists')}")
        if status.get("splicer3d_health"):
            health = status["splicer3d_health"]
            print(f"splicer3d={health.get('url')} ok={health.get('ok')}")
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

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
