#!/usr/bin/env python3
"""Persist the module-level electronics truth benchmark before KiCad lowering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if sys.path and str(Path(sys.path[0]).resolve()) == _SCRIPT_DIR:
    sys.path.pop(0)

from hardware_splicer.electronics_foundation_benchmark import (
    load_electronics_bundle,
    run_electronics_foundation_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--proposal-bundle",
        default="experiments/electronics/esp32_hcsr04_level_shift_gpt56_sol.json",
    )
    parser.add_argument("--out-dir", default="artifacts/electronics-foundation")
    args = parser.parse_args()

    bundle = load_electronics_bundle(args.proposal_bundle)
    report = run_electronics_foundation_benchmark(bundle)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "ELECTRONICS_FOUNDATION_BENCHMARK.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    checks = dict(report.get("checks") or {})
    unsafe = dict(report.get("unsafe_direct_design") or {})
    historical = dict(unsafe.get("historical_erc") or {})
    strict = dict(unsafe.get("strict_signal_audit") or {})
    lines = [
        "benchmark=esp32_hcsr04_logic_domain_truth",
        f"diagnostic_pass={bool(report.get('diagnostic_pass'))}",
        f"historical_unsafe_erc_pass={historical.get('pass')}",
        f"strict_unsafe_erc_pass={strict.get('pass')}",
        f"strict_unsafe_errors={strict.get('errors')}",
        f"system_diagnosis={(report.get('system_diagnosis') or {}).get('classification')}",
        "fabrication_authorized=False",
        "power_on_authorized=False",
    ]
    for key, value in checks.items():
        lines.append(f"check.{key}={bool(value)}")
    summary = out / "ELECTRONICS_FOUNDATION_SUMMARY.txt"
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary.read_text(encoding="utf-8"), end="")
    return 0 if report.get("diagnostic_pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
