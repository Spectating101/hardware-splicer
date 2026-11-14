#!/usr/bin/env python3
"""Export the initial assembly variant for JLCPCB with KiCad 9.

Run with /usr/bin/python3 for pcbnew. No network or supplier substitutions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
NAME = "spi_flash_adapter_v1"
BOARD = HERE / f"{NAME}.kicad_pcb"
# JLCPCB's documented Protel names; exactly one outline, no duplicate GM1.
LAYERS = {
    "F.Cu": "GTL", "B.Cu": "GBL", "F.Mask": "GTS", "B.Mask": "GBS",
    "F.Silkscreen": "GTO", "B.Silkscreen": "GBO", "Edge.Cuts": "GKO",
    "F.Paste": "GTP", "B.Paste": "GBP",
}
BOM_FIELDS = ["Comment", "Designator", "Footprint", "LCSC Part #"]
CPL_FIELDS = ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]
INPUTS = [f"{NAME}.kicad_pcb", f"{NAME}.kicad_sch", f"{NAME}.kicad_pro",
          "BOM.csv", "export_fab.py", "ORDER_GUIDE.md", "BRING_UP_TEST.md"]


def run(*args: str) -> str:
    return subprocess.run(args, cwd=HERE, check=True, capture_output=True, text=True).stdout.strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize(text: str) -> str:
    # Fixed export epoch for reproducible Gerbers/drills, not a stock-check date.
    return re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:?\d{2}|Z)?",
                  "2026-11-15T00:00:00Z", text)


def export(output: Path) -> None:
    version = run("kicad-cli", "--version")
    if not version.startswith("9."):
        raise ValueError("KiCad 9 required; requalify exporter before using another major version")
    # Keep temporary exports inside this design directory; no machine paths in outputs.
    with tempfile.TemporaryDirectory(prefix=".fab-", dir=HERE) as temporary:
        temp = Path(temporary)
        raw = temp / "raw"
        raw.mkdir()
        run("kicad-cli", "pcb", "export", "gerbers", str(BOARD), "--layers",
            ",".join(LAYERS), "--precision", "6", "--subtract-soldermask", "-o", str(raw))
        run("kicad-cli", "pcb", "export", "drill", str(BOARD), "--format", "excellon",
            "--drill-origin", "absolute", "--excellon-units", "mm",
            "--excellon-zeros-format", "decimal", "--excellon-separate-th", "-o", str(raw))
        run("kicad-cli", "pcb", "export", "pos", str(BOARD), "--format", "csv",
            "--units", "mm", "--side", "both", "--exclude-dnp", "--exclude-fp-th",
            "-o", str(raw / "positions.csv"))
        payloads = {}
        for layer, extension in LAYERS.items():
            source_extension = "gm1" if layer == "Edge.Cuts" else extension.lower()
            matches = list(raw.glob(f"*.{source_extension}"))
            if len(matches) != 1:
                raise ValueError(f"Expected exactly one {layer} Gerber")
            payloads[f"{NAME}.{extension}"] = normalize(matches[0].read_text()).encode()
        for kind in ("PTH", "NPTH"):
            source = raw / f"{NAME}-{kind}.drl"
            payloads[f"{NAME}-{kind}.XLN"] = normalize(source.read_text()).encode()

        rows = list(csv.DictReader((HERE / "BOM.csv").open()))
        board = pcbnew.LoadBoard(str(BOARD))
        placements = {r["Ref"]: r for r in csv.DictReader(io.StringIO((raw / "positions.csv").read_text()))}
        bom, cpl, hand = [], [], []
        for row in rows:
            refs = row["References"].split()
            for ref in refs:
                fp = board.FindFootprintByReference(ref)
                if fp is None or fp.IsDNP() != (row["Initial Assembly"] == "DNP"):
                    raise ValueError(f"Assembly variant mismatch: {ref}")
                if fp.GetFPIDAsString() != row["Footprint"] or fp.GetFieldsText().get("MPN") != row["Manufacturer Part Number"]:
                    raise ValueError(f"BOM/board identity mismatch: {ref}")
            if row["Procurement"] == "hand-solder":
                hand.append(row)
                continue
            if row["Procurement"] != "JLCPCB" or row["Initial Assembly"] != "FIT":
                raise ValueError("Invalid procurement/assembly state")
            if not re.fullmatch(r"C\d+", row["LCSC Part #"]) or not row["Source URL"].startswith("https://") or not row["Stock"] or not row["Checked Date"]:
                raise ValueError("Missing checked public source")
            bom.append({"Comment": row["Manufacturer Part Number"], "Designator": ",".join(refs),
                        "Footprint": row["Footprint"].split(":")[-1], "LCSC Part #": row["LCSC Part #"]})
            for ref in refs:
                position = placements[ref]
                if position["Side"] != "top":
                    raise ValueError("Only top assembly has been qualified")
                # KiCad absolute export already flips Y into Gerber's +up frame.
                # Preserve it, including its negative sign. No arbitrary translation.
                cpl.append({"Designator": ref, "Mid X": f'{float(position["PosX"]):.4f}mm',
                            "Mid Y": f'{float(position["PosY"]):.4f}mm', "Layer": "Top",
                            "Rotation": f'{float(position["Rot"]) % 360:.2f}'})
        output.mkdir(parents=True, exist_ok=True)
        gerbers = output / "gerbers"
        gerbers.mkdir(exist_ok=True)
        expected = set(payloads)
        if any(p.is_file() and p.name not in expected for p in gerbers.iterdir()):
            raise ValueError("Unexpected old Gerber files; use a clean output directory")
        for name, payload in payloads.items():
            (gerbers / name).write_bytes(payload)
        with zipfile.ZipFile(output / f"{NAME}-jlcpcb-gerbers.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in sorted(payloads.items()):
                info = zipfile.ZipInfo(name, (2026, 11, 15, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, payload)
        write_csv(output / "JLCPCB_BOM.csv", BOM_FIELDS, bom)
        write_csv(output / "JLCPCB_CPL.csv", CPL_FIELDS, cpl)
        write_csv(output / "HAND_SOLDER.csv", list(rows[0]), hand)
        # Native position output is useful when reconciling an assembly preview.
        (output / "kicad-positions.csv").write_text((raw / "positions.csv").read_text())
        metadata = {"schema_version": 1, "kicad_cli": version, "variant": "R1/R4 DNP; JP1 no shunt",
                    "layer_files": {layer: f"{NAME}.{ext}" for layer, ext in LAYERS.items()},
                    "drill_files": [f"{NAME}-{kind}.XLN" for kind in ("PTH", "NPTH")],
                    "source_sha256": {name: digest(HERE / name) for name in INPUTS}}
        (output / "manifest.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        files = sorted(p for p in output.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt")
        (output / "SHA256SUMS.txt").write_text("".join(f"{digest(p)}  {p.relative_to(output).as_posix()}\n" for p in files))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "fab")
    args = parser.parse_args()
    export(args.output.resolve())
    print("Exported JLCPCB fabrication, partial assembly and hand-solder files.")
