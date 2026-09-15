#!/usr/bin/env python3
"""Check native CAD reports, electrical intent, assembly parity and bound rules."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

from design_checks import (
    RECEIPT_INPUTS, netlist_components, require, validate_bom, validate_drc,
    validate_erc, validate_rules, validate_timing, validate_topology,
)


HERE = Path(__file__).resolve().parent
SCHEMATIC = HERE / "spi_flash_adapter_v1.kicad_sch"
BOARD = HERE / "spi_flash_adapter_v1.kicad_pcb"
MANIFEST = HERE / "design_manifest.json"
OUTPUT = HERE / "verification.json"
AUTHORITY = {
    "modeled_evidence_only": True,
    "human_ee_review_complete": False,
    "fabrication_ready": False,
    "power_on_ready": False,
    "physical_correctness": "UNPROVEN",
    "physical_authority_granted": False,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args: str, allowed_returncodes: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(list(args), check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode not in allowed_returncodes:
        report = ""
        if "-o" in args:
            path = Path(args[args.index("-o") + 1])
            if path.is_file():
                report = "\n" + path.read_text()
        raise ValueError(f"command exit {result.returncode}: {' '.join(args)}\n{result.stdout}{report}")
    return result.stdout


def pad_signature(footprint: pcbnew.FOOTPRINT) -> list[tuple]:
    """Compare actual pad stacks; only non-pad library graphics may drift."""
    return sorted((
        pad.GetNumber(), tuple(pad.GetFPRelativePosition()), tuple(pad.GetSize()),
        pad.GetShape(), pad.GetAttribute(), tuple(pad.GetDrillSize()), pad.GetDrillShape(),
        tuple(pad.GetLayerSet().Seq()), round(pad.GetFPRelativeOrientation().AsDegrees() % 360, 6),
        pad.GetRoundRectRadiusRatio(), pad.GetChamferRectRatio(), pad.GetChamferPositions(),
        pad.GetLocalSolderMaskMargin(), pad.GetLocalSolderPasteMargin(), pad.GetLocalSolderPasteMarginRatio(),
    ) for pad in footprint.Pads())


def compatible_library_footprints(board: pcbnew.BOARD) -> set[str]:
    compatible = set()
    for footprint in board.GetFootprints():
        if ":" not in footprint.GetFPIDAsString():
            continue
        library, name = footprint.GetFPIDAsString().split(":", 1)
        installed = pcbnew.FootprintLoad(f"/usr/share/kicad/footprints/{library}.pretty", name)
        if installed is not None and pad_signature(footprint) == pad_signature(installed):
            compatible.add(footprint.m_Uuid.AsString())
    return compatible


def validate_board_parity(board: pcbnew.BOARD, root: ET.Element, pin_nets: dict) -> None:
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    require(len(footprints) == len(board.GetFootprints()), "duplicate board reference")
    components = netlist_components(root)
    require(set(footprints) == set(components) | {"H1", "H2", "H3", "H4"}, "board component inventory mismatch")
    actual = {}
    for reference, component in components.items():
        footprint = footprints[reference]
        require(footprint.GetValue() == component.findtext("value"), f"board value mismatch: {reference}")
        require(footprint.GetFPIDAsString() == component.findtext("footprint"), f"board footprint mismatch: {reference}")
        require(footprint.IsDNP() == (component.find("property[@name='dnp']") is not None), f"board DNP mismatch: {reference}")
        for field in ("MPN", "Manufacturer"):
            expected = component.findtext(f"fields/field[@name='{field}']", default="")
            require(footprint.GetFieldsText().get(field, "") == expected, f"board {field} mismatch: {reference}")
        for pad in footprint.Pads():
            key = (reference, pad.GetNumber())
            require(key not in actual, f"duplicate physical pad number: {key}")
            actual[key] = pad.GetNetname()
    require(actual == pin_nets, "board pad/net map does not equal exported schematic")


def validate_ground_reference(board: pcbnew.BOARD, manifest: dict) -> dict:
    require(all(isinstance(t, pcbnew.PCB_VIA) or t.GetLayer() == pcbnew.F_Cu or t.GetNetname() == "/GND" for t in board.GetTracks()), "back reference layer contains non-ground tracks")
    zones = list(board.Zones())
    require(len(zones) == 2 and {z.GetLayer() for z in zones} == {pcbnew.F_Cu, pcbnew.B_Cu}, "two ground reference layers required")
    areas = {}
    for zone in zones:
        require(zone.GetNetname() == "/GND" and zone.IsFilled(), "ground reference missing net or fill")
        area = zone.CalculateFilledArea() / 1e12
        require(area > 3000, "ground reference coverage unexpectedly reduced")
        areas[board.GetLayerName(zone.GetLayer())] = round(area, 3)
        if zone.GetLayer() == pcbnew.B_Cu:
            require(zone.GetFilledPolysList(pcbnew.B_Cu).OutlineCount() == 1, "back ground reference split into separate outlines")
    vias = [t for t in board.GetTracks() if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == "/GND"]
    require(len(vias) >= manifest["layout_contract"]["minimum_ground_stitching_vias"], "insufficient ground stitching")
    escapes = {}
    for reference, number in (("U1", "7"), ("U2", "4"), ("U3", "2"), *((f"C{i}", "2") for i in range(1, 7))):
        pad = board.FindFootprintByReference(reference).FindPadByNumber(number)
        require(pad.GetNetname() == "/GND", f"wrong ground pad: {reference}.{number}")
        distance = min(math.dist(tuple(pad.GetPosition()), tuple(v.GetPosition())) / 1e6 for v in vias)
        require(distance <= manifest["layout_contract"]["local_ground_escape_max_mm"], f"local ground escape too long: {reference}")
        escapes[f"{reference}.{number}"] = round(distance, 4)
    return {"ground_zones": len(zones), "ground_stitching_vias": len(vias), "filled_ground_area_mm2": areas, "nearest_ground_via_mm": escapes, "signal_routing_layers": ["F.Cu"]}


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    require(manifest["authority"] == AUTHORITY, "design authority boundary changed unexpectedly")
    require(not (HERE / "spi_flash_adapter_v1.kicad_dru").exists(), "additional custom DRC rules must be explicitly bound before use")
    validate_rules(json.loads((HERE / RECEIPT_INPUTS["project_rules"]).read_text()))
    validate_timing(manifest)
    board = pcbnew.LoadBoard(str(BOARD))
    with tempfile.TemporaryDirectory(prefix="hs-spi-verify-") as temporary:
        erc_report = Path(temporary) / "erc.json"
        drc_report = Path(temporary) / "drc.json"
        netlist = Path(temporary) / "netlist.xml"
        command("kicad-cli", "sch", "export", "netlist", str(SCHEMATIC), "--format", "kicadxml", "-o", str(netlist))
        root = ET.parse(netlist).getroot()
        pin_nets = validate_topology(root)
        with (HERE / "BOM.csv").open() as source:
            validate_bom(root, list(csv.DictReader(source)))
        validate_board_parity(board, root, pin_nets)
        erc_stdout = command("kicad-cli", "sch", "erc", str(SCHEMATIC), "-o", str(erc_report), "--format", "json", "--severity-all", "--exit-code-violations", allowed_returncodes=(0, 5))
        validate_erc(json.loads(erc_report.read_text()), erc_stdout)
        drc_stdout = command("kicad-cli", "pcb", "drc", str(BOARD), "-o", str(drc_report), "--format", "json", "--severity-all", "--schematic-parity", "--exit-code-violations", allowed_returncodes=(0, 5))
        advisories = validate_drc(json.loads(drc_report.read_text()), drc_stdout, compatible_library_footprints(board))
    ground = validate_ground_reference(board, manifest)
    footprints = list(board.GetFootprints())
    receipt = {
        "schema_version": "hardware_splicer.reference_design_verification.v2",
        "design_id": manifest["design_id"], "result": "pass",
        "toolchain": {"kicad_cli": command("kicad-cli", "--version").strip(), "pcbnew": pcbnew.Version(),
                      "router": "Freerouting v2.4.1; routing output accepted only after KiCad checks"},
        "artifact_sha256": {name: sha256(HERE / path) for name, path in RECEIPT_INPUTS.items()},
        "checks": {"erc_errors": 0, "erc_warnings": 0, "drc_actionable_violations": 0,
                   "unconnected_pads": 0, "footprint_errors": 0, "schematic_parity_issues": 0,
                   "required_topology_issues": 0, "bom_parity_issues": 0, "board_identity_issues": 0,
                   "assembly_variant_issues": 0, "ground_reference_issues": 0},
        "advisories": {"library_revision_mismatch_warnings": len(advisories),
                       "policy": "Only footprint-library warnings with independently matching pad stacks are advisory; unknown schemas, severities and count disagreements fail closed.",
                       "reviewed_nonpad_library_differences": advisories},
        "board_inventory": {"footprints_total": len(footprints), "testpoints": sum(f.GetReference().startswith("TP") for f in footprints),
                            "mounting_holes": sum(f.GetReference().startswith("H") for f in footprints),
                            "copper_tracks_and_vias": len(board.GetTracks()), **ground},
        "authority": AUTHORITY,
        "nonclaims": ["CAD/electrical-intent checks do not establish physical correctness.",
                      "Ground fill and nearby vias are geometric checks, not impedance or waveform measurements.",
                      "Host loading, power transitions and current/thermal performance still require physical evidence.",
                      "This receipt does not authorize fabrication or power-on."],
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, ET.ParseError) as exc:
        raise SystemExit(f"verification failed: {exc}") from exc
