from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional


def _print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _cmd_validate_kicad(args: argparse.Namespace) -> int:
    from src.engines.kicad_hints import generate_hints_template
    from src.engines.kicad_netlist_compiler import compile_kicad_netlist
    from src.engines.power_tree_validator import validate_pcb_power_tree

    hints = None
    if args.hints is not None:
        hints = json.loads(Path(args.hints).read_text())
    if hints is None and args.auto_hints:
        hints = generate_hints_template(str(args.netlist))["hints"]

    compiled = compile_kicad_netlist(str(args.netlist), hints=hints)
    results, issues = validate_pcb_power_tree(compiled.netlist, constraints=compiled.constraints)

    if args.json:
        payload = {
            "results": {
                "converged": results["converged"],
                "iterations": results["iterations"],
                "node_v": results["solution"].node_v,
                "vsource_i": results["solution"].vsource_i,
            },
            "issues": [i.__dict__ for i in issues],
        }
        _print_json(payload)
        return 0

    sol = results["solution"]
    print(f"converged={results['converged']} iters={results['iterations']}")
    print("\nNode voltages:")
    for k in sorted(sol.node_v.keys()):
        print(f"  {k:>12s}: {sol.node_v[k]:.4f} V")
    print("\nVoltage source currents (positive from + to -):")
    for k in sorted(sol.vsource_i.keys()):
        print(f"  {k:>12s}: {sol.vsource_i[k]*1000:.2f} mA")
    print(f"\nIssues: {len(issues)}")
    for issue in issues:
        print(f"[{issue.severity.upper()}] {issue.component}: {issue.issue}")
        print(f"  {issue.explanation}")
        print(f"  Solution: {issue.solution}")
    return 0 if not issues else 1


def _cmd_validate_design(args: argparse.Namespace) -> int:
    from src.engines.physics_orchestrator import validate_high_level_design, validation_output_to_dict

    design = json.loads(Path(args.design).read_text())
    out = validate_high_level_design(design)
    payload = validation_output_to_dict(out)
    if args.json:
        _print_json(payload)
        return 0

    print(f"converged={payload['results'].get('converged')} iters={payload['results'].get('iterations')}")
    print(f"issues={len(payload.get('issues') or [])}")
    return 0 if not payload.get("issues") else 1


def _cmd_analyze_image(args: argparse.Namespace) -> int:
    import numpy as np
    from PIL import Image

    from src.core.ingest import CircuitAnalyzer

    img = Image.open(args.image)
    image_np = np.array(img)
    analyzer = CircuitAnalyzer()

    results = analyzer.analyze_pcb(image_np, backend=args.backend, enable_ocr=(not args.no_ocr))
    summary = analyzer.get_analysis_summary(results)

    if args.json:
        _print_json({"results": results, "summary": summary})
        return 0

    print(summary.get("summary_text", ""))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="circuit-ai-cli", description="Circuit-AI command line interface")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-kicad", help="Validate a KiCad .net (S-expression) with optional physics hints")
    p.add_argument("netlist", type=Path, help="Path to KiCad .net")
    p.add_argument("--hints", type=Path, default=None, help="Optional JSON hints file")
    p.add_argument("--auto-hints", action="store_true", help="Generate heuristic hints if --hints is not provided")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p.set_defaults(func=_cmd_validate_kicad)

    p = sub.add_parser("validate-design", help="Validate a high-level design JSON via the physics engine")
    p.add_argument("design", type=Path, help="Path to a design JSON file")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p.set_defaults(func=_cmd_validate_design)

    p = sub.add_parser("analyze-image", help="Run vision+OCR analysis on a PCB image")
    p.add_argument("--image", type=Path, required=True, help="Path to an image")
    p.add_argument("--backend", type=str, default=None, help="Detector backend override (e.g. yolo)")
    p.add_argument("--no-ocr", action="store_true", help="Disable OCR")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p.set_defaults(func=_cmd_analyze_image)

    return ap


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

