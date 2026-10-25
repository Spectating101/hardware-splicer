"""Fail-closed end-to-end hardware build submission gate.

Checks independent tool execution and artifact completeness. Passing this gate
is NOT physical validation and does not itself authorize fabrication.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


REQUIRED = ("design.kicad_sch", "design.kicad_pcb", "simulation.cir", "bom.csv", "design_origin.json")


def evaluate_build_submission(directory: Path) -> dict:
    directory = Path(directory)
    errors = []
    files = {}
    for name in REQUIRED:
        path = directory / name
        if not path.is_file() or not path.stat().st_size:
            errors.append(f"missing_or_empty:{name}")
        else:
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    origin = {}
    if "design_origin.json" in files:
        try:
            origin = json.loads((directory / "design_origin.json").read_text())
            if origin.get("origin") != "hs_generated":
                errors.append("design_not_declared_hs_generated")
            if origin.get("reference_design_reused") is not False:
                errors.append("reference_reuse_unresolved")
            if not origin.get("generator_run_id"):
                errors.append("missing_generator_run_id")
        except (ValueError, TypeError):
            errors.append("invalid_origin_manifest")

    tool_results = {}
    cli = shutil.which("kicad-cli")
    spice = shutil.which("ngspice")
    if not cli:
        errors.append("kicad_cli_unavailable")
    if not spice:
        errors.append("ngspice_unavailable")

    def run_check(label, args):
        try:
            result = subprocess.run(args, text=True, capture_output=True, timeout=120, check=False)
            tool_results[label] = {"exit_code": result.returncode,
                                   "stdout_tail": result.stdout[-1200:],
                                   "stderr_tail": result.stderr[-1200:]}
            if result.returncode:
                errors.append(f"{label}_failed")
        except (OSError, subprocess.TimeoutExpired) as exc:
            tool_results[label] = {"error": type(exc).__name__}
            errors.append(f"{label}_execution_error")

    if cli and "design.kicad_sch" in files:
        out = directory / "erc.rpt"
        run_check("erc", [cli, "sch", "erc", "-o", str(out), str(directory / "design.kicad_sch")])
        if out.is_file():
            files["erc.rpt"] = hashlib.sha256(out.read_bytes()).hexdigest()
    if cli and "design.kicad_pcb" in files:
        out = directory / "drc.rpt"
        run_check("drc", [cli, "pcb", "drc", "-o", str(out), str(directory / "design.kicad_pcb")])
        if out.is_file():
            files["drc.rpt"] = hashlib.sha256(out.read_bytes()).hexdigest()
    if spice and "simulation.cir" in files:
        run_check("ngspice", [spice, "-b", str(directory / "simulation.cir")])

    if "bom.csv" in files:
        import csv
        with (directory / "bom.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows or not {"reference", "manufacturer_part_number", "quantity"}.issubset(rows[0]):
            errors.append("bom_missing_required_fields_or_rows")
        if any(not row.get("manufacturer_part_number") for row in rows):
            errors.append("unresolved_manufacturer_part_number")

    # Tool return code alone cannot establish model validity, performance,
    # schematic↔PCB parity, manufacturing quality or physical operation.
    return {
        "schema_version": "hardware_splicer.hardware_build_challenge.v1",
        "artifact_sha256": files, "tool_runs": tool_results,
        "errors": errors,
        "automated_submission_checks_pass": not errors,
        "performance_validated": False,
        "schematic_pcb_parity_verified": False,
        "gerber_assembly_package_verified": False,
        "physical_prototype_built": False,
        "physical_measurements_verified": False,
        "fabrication_authorized": False,
    }
