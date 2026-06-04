#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.engines.physics_orchestrator import validate_high_level_design, validation_output_to_dict


def main() -> int:
    ap = argparse.ArgumentParser(description="Compile + validate a high-level Circuit-AI design JSON")
    ap.add_argument("design", help="Path to design JSON, or - for stdin")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = ap.parse_args()

    design_text = sys.stdin.read() if args.design == "-" else Path(args.design).read_text()
    design = json.loads(design_text)

    out = validate_high_level_design(design)

    if args.json:
        payload = {"design": design} | validation_output_to_dict(out)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    sol = out.results["node_v"]
    vsource_i = out.results["vsource_i"]
    print(f"converged={out.results['converged']} iters={out.results['iterations']}")

    print("\nNode voltages:")
    for k in sorted(sol.keys()):
        print(f"  {k:>12s}: {sol[k]:.4f} V")

    print("\nVoltage source currents (positive from + to -):")
    for k in sorted(vsource_i.keys()):
        print(f"  {k:>12s}: {vsource_i[k]*1000:.2f} mA")

    print(f"\nIssues: {len(out.issues)}")
    for issue in out.issues:
        print(f"[{issue.severity.upper()}] {issue.component}: {issue.issue}")
        print(f"  {issue.explanation}")
        print(f"  Solution: {issue.solution}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
