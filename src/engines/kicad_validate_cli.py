#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.engines.kicad_netlist_compiler import compile_kicad_netlist
from src.engines.kicad_hints import generate_hints_template
from src.engines.power_tree_validator import validate_pcb_power_tree


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a KiCad .net (S-expression) with optional physics hints")
    ap.add_argument("netlist", type=Path, help="Path to KiCad .net")
    ap.add_argument("--hints", type=Path, default=None, help="Optional JSON hints file")
    ap.add_argument("--auto-hints", action="store_true", help="Generate heuristic hints if --hints is not provided")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = ap.parse_args()

    hints = json.loads(args.hints.read_text()) if args.hints else None
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
        print(json.dumps(payload, indent=2, sort_keys=True))
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
