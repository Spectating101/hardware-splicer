#!/usr/bin/env python3
"""Run fail-closed KiCad checks and seal a machine-readable verification receipt."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

import pcbnew


HERE = Path(__file__).resolve().parent
SCHEMATIC = HERE / "spi_flash_adapter_v1.kicad_sch"
BOARD = HERE / "spi_flash_adapter_v1.kicad_pcb"
MANIFEST = HERE / "design_manifest.json"
OUTPUT = HERE / "verification.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command(*args: str, allowed_returncodes: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(
        list(args),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode not in allowed_returncodes:
        rendered = " ".join(args)
        report = ""
        if "-o" in args:
            report_path = Path(args[args.index("-o") + 1])
            if report_path.is_file():
                report = f"\n--- report: {report_path.name} ---\n{report_path.read_text()}"
        raise SystemExit(
            f"command failed with exit {result.returncode}: {rendered}\n"
            f"{result.stdout}{report}"
        )
    return result.stdout


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    authority = manifest["authority"]
    if authority != {
        "modeled_evidence_only": True,
        "human_ee_review_complete": False,
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
    }:
        raise SystemExit("design authority boundary changed unexpectedly")

    with tempfile.TemporaryDirectory(prefix="hs-spi-verify-") as temporary:
        erc_report = Path(temporary) / "erc.rpt"
        drc_report = Path(temporary) / "drc.rpt"
        erc_stdout = command(
            "kicad-cli",
            "sch",
            "erc",
            str(SCHEMATIC),
            "-o",
            str(erc_report),
            "--exit-code-violations",
        )
        drc_stdout = command(
            "kicad-cli",
            "pcb",
            "drc",
            str(BOARD),
            "-o",
            str(drc_report),
            "--severity-all",
            "--schematic-parity",
            "--exit-code-violations",
            allowed_returncodes=(0, 5),
        )
        erc_text = erc_report.read_text()
        drc_text = drc_report.read_text()

    if "ERC messages: 0  Errors 0  Warnings 0" not in erc_text:
        raise SystemExit(f"ERC receipt was not clean:\n{erc_text}")
    violation_codes = re.findall(r"^\[([^]]+)\]:", drc_text, flags=re.MULTILINE)
    allowed_advisories = {"lib_footprint_mismatch"}
    actionable_violations = [
        code for code in violation_codes if code not in allowed_advisories
    ]
    if actionable_violations:
        raise SystemExit(
            "PCB receipt contained actionable violations "
            f"{actionable_violations!r}:\n{drc_text}"
        )
    for required in ("Found 0 unconnected pads", "Found 0 Footprint errors"):
        if required not in drc_text:
            raise SystemExit(f"PCB receipt missing {required!r}:\n{drc_text}")
    if "Found 0 schematic parity issues" not in drc_stdout:
        raise SystemExit(f"schematic parity was not clean:\n{drc_stdout}")

    board = pcbnew.LoadBoard(str(BOARD))
    footprints = list(board.GetFootprints())
    tracks = list(board.GetTracks())
    receipt = {
        "schema_version": "hardware_splicer.reference_design_verification.v1",
        "design_id": manifest["design_id"],
        "result": "pass",
        "toolchain": {
            "kicad_cli": command("kicad-cli", "--version").strip(),
            "pcbnew": pcbnew.Version(),
            "router": "Freerouting v2.4.1; routing output accepted only after KiCad checks",
            "freerouting_linux_x64_archive_sha256": "3ad5a956ab474b12f331d24195feadac90e8344b8e013c6a4ab26e203ce51519",
        },
        "artifact_sha256": {
            "schematic": sha256(SCHEMATIC),
            "pcb": sha256(BOARD),
            "bom": sha256(HERE / "BOM.csv"),
            "design_manifest": sha256(MANIFEST),
        },
        "checks": {
            "erc_errors": 0,
            "erc_warnings": 0,
            "drc_actionable_violations": 0,
            "unconnected_pads": 0,
            "footprint_errors": 0,
            "schematic_parity_issues": 0,
        },
        "advisories": {
            "library_revision_mismatch_warnings": violation_codes.count(
                "lib_footprint_mismatch"
            ),
            "policy": (
                "Only KiCad lib_footprint_mismatch warnings are advisory. The PCB "
                "embeds the routed footprint geometry; all other DRC classes fail closed."
            ),
        },
        "board_inventory": {
            "footprints_total": len(footprints),
            "testpoints": sum(fp.GetReference().startswith("TP") for fp in footprints),
            "mounting_holes": sum(fp.GetReference().startswith("H") for fp in footprints),
            "copper_tracks_and_vias": len(tracks),
        },
        "authority": authority,
        "nonclaims": [
            "ERC and DRC establish internal CAD consistency, not physical correctness.",
            "The routing engine's completion report is not accepted without KiCad DRC and parity checks.",
            "This receipt does not authorize fabrication or power-on.",
        ],
        "diagnostic_stdout": {
            "erc_clean": "Found 0 violations" in erc_stdout,
            "drc_actionable_clean": not actionable_violations,
            "footprint_library_revision_match": not violation_codes,
        },
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
