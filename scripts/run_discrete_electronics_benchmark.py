#!/usr/bin/env python3
"""Run the datasheet-backed discrete electronics benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if sys.path and str(Path(sys.path[0]).resolve()) == _SCRIPT_DIR:
    sys.path.pop(0)

from hardware_splicer.discrete_electronics_truth import load_json_object, run_discrete_electronics_benchmark


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", default="experiments/electronics/discrete_uart_3v3_1v8_gpt56_sol.json")
    parser.add_argument("--evidence", default="experiments/electronics/discrete_uart_3v3_1v8_evidence.json")
    parser.add_argument("--out-dir", default="artifacts/discrete-electronics")
    args = parser.parse_args()

    report = run_discrete_electronics_benchmark(load_json_object(args.proposal), load_json_object(args.evidence))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "DISCRETE_ELECTRONICS_BENCHMARK.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    lines = [
        "benchmark=datasheet_backed_5v_to_3v3_full_duplex_3v3_1v8_uart",
        f"diagnostic_pass={bool(report.get('diagnostic_pass'))}",
        f"design_ready={bool(report.get('design_ready'))}",
        f"fabrication_ready={bool(report.get('fabrication_ready'))}",
        f"power_on_ready={bool(report.get('power_on_ready'))}",
        f"unresolved_footprints={len((report.get('footprint_closure') or {}).get('unresolved') or [])}",
    ]
    lines.extend(f"check.{key}={bool(value)}" for key, value in (report.get("checks") or {}).items())
    (out / "DISCRETE_ELECTRONICS_SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print((out / "DISCRETE_ELECTRONICS_SUMMARY.txt").read_text(encoding="utf-8"), end="")
    return 0 if report.get("diagnostic_pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
