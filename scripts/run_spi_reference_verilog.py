#!/usr/bin/env python3
"""Compile and run the derived read-only SPI Verilog reference with Icarus Verilog."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

SCHEMA_VERSION = "hardware_splicer.spi_derived_verilog_reference_run.v1"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _authority_envelope() -> dict[str, object]:
    return {
        "evidence_class": "derived_surrogate_only",
        "vendor_model_campaign_credit_eligible": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def run(model: Path, testbench: Path) -> dict[str, object]:
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "tool_unavailable",
            "simulation_pass": False,
            "tooling": {"iverilog": iverilog, "vvp": vvp},
            "model_sha256": _sha256(model),
            "testbench_sha256": _sha256(testbench),
            **_authority_envelope(),
        }

    with tempfile.TemporaryDirectory(prefix="hs-derived-verilog-") as tmp:
        output = Path(tmp) / "simv"
        compile_run = subprocess.run(
            [iverilog, "-g2012", "-Wall", "-o", str(output), str(model), str(testbench)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=30,
        )
        if compile_run.returncode != 0:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "compile_failed",
                "simulation_pass": False,
                "compile_exit_code": compile_run.returncode,
                "compile_stdout": compile_run.stdout,
                "compile_stderr": compile_run.stderr,
                "model_sha256": _sha256(model),
                "testbench_sha256": _sha256(testbench),
                **_authority_envelope(),
            }

        simulate = subprocess.run(
            [vvp, str(output)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=30,
        )

    stdout = simulate.stdout
    jedec_ok = "HS_JEDEC_ID=EF6018" in stdout
    mutating_rejected = "HS_MUTATING_REJECTED=1" in stdout
    passed = simulate.returncode == 0 and jedec_ok and mutating_rejected
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed_derived_reference" if passed else "failed_derived_reference",
        "simulation_pass": passed,
        "compile_exit_code": compile_run.returncode,
        "simulation_exit_code": simulate.returncode,
        "model_sha256": _sha256(model),
        "testbench_sha256": _sha256(testbench),
        "checks": {
            "jedec_id_reference": jedec_ok,
            "mutating_command_rejected": mutating_rejected,
        },
        "stdout": stdout,
        "stderr": simulate.stderr,
        "tooling": {
            "iverilog": iverilog,
            "vvp": vvp,
        },
        **_authority_envelope(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("examples/derived_virtual_lab/w25q_readonly_reference.v"),
    )
    parser.add_argument(
        "--testbench",
        type=Path,
        default=Path("examples/derived_virtual_lab/tb_w25q_readonly_reference.v"),
    )
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()

    report = run(args.model, args.testbench)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(rendered, encoding="utf-8")
    return 0 if report["simulation_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
