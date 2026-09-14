#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Executing a script from this directory puts ``scripts/`` first on sys.path, where the
# legacy ``scripts/hardware_splicer.py`` would otherwise shadow the real package. Bind the
# documented CLI to this checkout's source tree before importing Hardware Splicer modules.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
sys.path.insert(0, str(_SRC_ROOT))

from hardware_splicer.spi_behavioral_oracle import transact
from hardware_splicer.spi_derived_verilog_runner import run_derived_verilog_oracle
from hardware_splicer.spi_surrogate_repair_benchmark import run_repair_benchmark
from hardware_splicer.spi_surrogate_sensitivity import run_sensitivity_sweep
from hardware_splicer.spi_virtual_lab_benchmark import run_benchmark
from hardware_splicer.spi_virtual_lab_report import build_virtual_lab_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the zero-Astra SPI derived virtual lab")
    parser.add_argument("--full", action="store_true", help="include per-case rows")
    parser.add_argument("--run-verilog", action="store_true", help="attempt the derived Icarus-Verilog oracle")
    args = parser.parse_args()

    benchmark = run_benchmark()
    repair = run_repair_benchmark()
    sensitivity = run_sensitivity_sweep()
    protocol = transact(0x9F)
    aggregate_report = build_virtual_lab_report()
    verilog = None
    if args.run_verilog:
        verilog = run_derived_verilog_oracle(repo_root=_REPO_ROOT)

    if not args.full:
        benchmark = {k: v for k, v in benchmark.items() if k != "rows"}
        repair = {k: v for k, v in repair.items() if k != "rows"}
        sensitivity = {k: v for k, v in sensitivity.items() if k != "rows"}

    print(
        json.dumps(
            {
                "aggregate_report": aggregate_report,
                "benchmark": benchmark,
                "repair": repair,
                "sensitivity": sensitivity,
                "protocol_oracle": protocol,
                "derived_verilog": verilog,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
