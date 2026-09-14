"""Optional Icarus-Verilog execution for the derived SPI oracle.

This runner is a development/reference check only. Passing it never counts as vendor-model,
measured, or physical evidence.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "hardware_splicer.spi_derived_verilog_run.v1"


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_derived_verilog_oracle(*, repo_root: str | Path, timeout_s: int = 30) -> dict[str, Any]:
    root = Path(repo_root)
    source = root / "examples/spi_virtual_lab/w25q_readonly_oracle.v"
    tb = root / "examples/spi_virtual_lab/w25q_readonly_oracle_tb.v"
    if not source.is_file() or not tb.is_file():
        raise FileNotFoundError("derived Verilog oracle source/testbench missing")

    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    base = {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": "derived_surrogate_only",
        "eligible_for_vendor_model_campaign_credit": False,
        "source_sha256": _sha(source),
        "testbench_sha256": _sha(tb),
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
    if not iverilog or not vvp:
        return {**base, "status": "tool_unavailable", "compile_exit_code": None, "run_exit_code": None}

    with tempfile.TemporaryDirectory(prefix="hs-derived-verilog-") as tmp:
        out = Path(tmp) / "oracle.vvp"
        compile_run = subprocess.run(
            [iverilog, "-g2012", "-s", "hs_w25q_readonly_oracle_tb", "-o", str(out), str(source), str(tb)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            check=False,
        )
        if compile_run.returncode != 0:
            return {
                **base,
                "status": "compile_failed",
                "compile_exit_code": compile_run.returncode,
                "run_exit_code": None,
                "compile_output_sha256": "sha256:" + hashlib.sha256(compile_run.stdout + compile_run.stderr).hexdigest(),
            }
        sim_run = subprocess.run(
            [vvp, str(out)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            check=False,
        )
    raw = sim_run.stdout + sim_run.stderr
    return {
        **base,
        "status": "passed_derived_oracle" if sim_run.returncode == 0 and b"pass jedec=ef6018" in raw.lower() else "run_failed",
        "compile_exit_code": compile_run.returncode,
        "run_exit_code": sim_run.returncode,
        "raw_output_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "oracle_expected_jedec_hex": "EF6018",
    }
