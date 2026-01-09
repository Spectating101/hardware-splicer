#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.engines.netlist_io import netlist_from_json, netlist_to_dict
from src.engines.power_tree_validator import PowerTreeConstraints, SourceCurrentLimit, validate_pcb_power_tree


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a PCB power-tree netlist (DC operating point)")
    ap.add_argument("netlist", help="Path to netlist JSON, or - for stdin")
    ap.add_argument("--usb-limit-a", type=float, default=0.5, help="USB/source current limit (A) for VUSB")
    ap.add_argument("--source-name", type=str, default="VUSB", help="Name of the upstream voltage source")
    ap.add_argument("--max-trace-drop-v", type=float, default=0.25, help="Warn if any trace drop exceeds this (V)")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = ap.parse_args()

    net_text = sys.stdin.read() if args.netlist == "-" else Path(args.netlist).read_text()
    net = netlist_from_json(net_text)

    results, issues = validate_pcb_power_tree(
        net,
        constraints=PowerTreeConstraints(
            source_limits=[SourceCurrentLimit(source_name=args.source_name, max_current_a=args.usb_limit_a)],
            max_trace_drop_v=args.max_trace_drop_v,
        ),
    )

    if args.json:
        out = {
            "netlist": netlist_to_dict(net),
            "results": {
                "converged": results["converged"],
                "iterations": results["iterations"],
                "node_v": results["solution"].node_v,
                "vsource_i": results["solution"].vsource_i,
            },
            "issues": [i.__dict__ for i in issues],
        }
        print(json.dumps(out, indent=2, sort_keys=True))
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
