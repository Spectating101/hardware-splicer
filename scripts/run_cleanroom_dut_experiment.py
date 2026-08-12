#!/usr/bin/env python3
"""Run the semiconductor DUT dual-agent cleanroom experiment and persist evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

# This repository already contains scripts/hardware_splicer.py. When any script inside
# this directory imports ``hardware_splicer``, Python otherwise resolves that sibling
# file before the installed ``src/hardware_splicer`` package and creates a circular
# import. Remove the scripts directory from import search before importing the package.
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path = [
    entry
    for entry in sys.path
    if Path(entry or ".").resolve() != _SCRIPT_DIR
]

from hardware_splicer.cleanroom_extended_dut_experiment import (  # noqa: E402
    run_extended_deterministic_dut_experiment,
    run_extended_live_dut_experiment,
)


def _write(path: Path, body: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(body), indent=2, ensure_ascii=False), encoding="utf-8")


def _summary(result: Mapping[str, Any]) -> str:
    mode = str(result.get("mode") or "unknown")
    lines = [f"mode={mode}"]
    if mode == "deterministic_extended_evaluator_probe":
        checks = dict(result.get("checks") or {})
        lines.append(f"pass={bool(result.get('pass'))}")
        lines.append(f"case_count={int(result.get('case_count') or 0)}")
        lines.append(f"challenge_kinds={json.dumps(result.get('challenge_kinds') or [])}")
        for key, value in checks.items():
            lines.append(f"{key}={bool(value)}")
        return "\n".join(lines) + "\n"

    replay = dict(result.get("replay") or {})
    retrospective = dict(result.get("retrospective") or {})
    metrics = dict(retrospective.get("metrics") or {})
    lines.extend(
        [
            f"provider_configured={bool(result.get('provider_configured'))}",
            f"contract_pass={bool(result.get('contract_pass'))}",
            f"case_count={int(result.get('case_count') or 0)}",
            f"challenge_kinds={json.dumps(result.get('challenge_kinds') or [])}",
            f"hard_failure_count={int(replay.get('hard_failure_count') or 0)}",
            f"taxonomy_counts={json.dumps(retrospective.get('failure_taxonomy_counts') or {}, sort_keys=True)}",
            f"truth_metrics={json.dumps(metrics.get('truth') or {}, sort_keys=True)}",
            f"agentic_metrics={json.dumps(metrics.get('agentic_competence') or {}, sort_keys=True)}",
            f"anti_script_metrics={json.dumps(metrics.get('anti_script') or {}, sort_keys=True)}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("deterministic", "live"), default="deterministic")
    parser.add_argument("--model", default=None)
    parser.add_argument("--out-dir", default="artifacts/cleanroom-dut")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "deterministic":
        result = run_extended_deterministic_dut_experiment()
        report_path = out_dir / "DETERMINISTIC_DUT_EXPERIMENT.json"
        summary_path = out_dir / "DETERMINISTIC_SUMMARY.txt"
        _write(report_path, result)
        summary_path.write_text(_summary(result), encoding="utf-8")
        print(summary_path.read_text(encoding="utf-8"), end="")
        return 0 if result.get("pass") else 2

    result = run_extended_live_dut_experiment(model=args.model)
    report_path = out_dir / "LIVE_DUT_EXPERIMENT.json"
    summary_path = out_dir / "LIVE_SUMMARY.txt"
    _write(report_path, result)
    summary_path.write_text(_summary(result), encoding="utf-8")
    print(summary_path.read_text(encoding="utf-8"), end="")

    if not result.get("provider_configured"):
        return 3
    if not result.get("contract_pass"):
        return 4
    replay = dict(result.get("replay") or {})
    provider_failures = [
        row
        for row in list(replay.get("results") or [])
        if isinstance(row, Mapping) and row.get("failure_class") == "provider_or_runtime"
    ]
    return 5 if provider_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
