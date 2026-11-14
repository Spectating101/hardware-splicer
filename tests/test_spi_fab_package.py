"""Guard the actual first-article upload set, variant, and source freshness."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

DESIGN = Path(__file__).resolve().parents[1] / "hardware/reference_designs/spi_flash_adapter_v1"
FAB = DESIGN / "fab"
NAME = "spi_flash_adapter_v1"
FUNCTIONS = {
    "GTL": "Copper,L1,Top", "GBL": "Copper,L2,Bot",
    "GTS": "Soldermask,Top", "GBS": "Soldermask,Bot",
    "GTO": "Legend,Top", "GBO": "Legend,Bot", "GKO": "Profile,NP",
    "GTP": "Paste,Top", "GBP": "Paste,Bot",
}


def rows(path: Path) -> list[dict]:
    with path.open() as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_spi_fab_complete_layers_drills_and_upload_zip() -> None:
    expected = {f"{NAME}.{extension}" for extension in FUNCTIONS}
    expected |= {f"{NAME}-{kind}.XLN" for kind in ("PTH", "NPTH")}
    assert {p.name for p in (FAB / "gerbers").iterdir()} == expected
    for extension, function in FUNCTIONS.items():
        text = (FAB / "gerbers" / f"{NAME}.{extension}").read_text()
        assert f"%TF.FileFunction,{function}*%" in text
        assert "%MOMM*%" in text and "%FSLAX46Y46*%" in text
        assert text.rstrip().endswith("M02*")
    for kind, count, function in (("PTH", 28, "Plated"), ("NPTH", 4, "NonPlated")):
        text = (FAB / "gerbers" / f"{NAME}-{kind}.XLN").read_text()
        assert text.startswith("M48\n") and text.rstrip().endswith("M30")
        assert "METRIC" in text and f"TF.FileFunction,{function},1,2,{kind}" in text
        assert len(re.findall(r"^X[-\d.]+Y[-\d.]+$", text, re.MULTILINE)) == count
    with zipfile.ZipFile(FAB / f"{NAME}-jlcpcb-gerbers.zip") as archive:
        assert set(archive.namelist()) == expected
        assert archive.testzip() is None
        for filename in expected:
            assert archive.read(filename) == (FAB / "gerbers" / filename).read_bytes()
    outline = (FAB / "gerbers" / f"{NAME}.GKO").read_text()
    corners = {(int(x), int(y)) for x, y in re.findall(r"X(-?\d+)Y(-?\d+)D0[12]\*", outline)}
    assert corners == {(100_000_000, -60_000_000), (190_000_000, -60_000_000),
                       (100_000_000, -110_000_000), (190_000_000, -110_000_000)}


def test_spi_fab_hashes_and_canonical_sources_are_current() -> None:
    manifest = json.loads((FAB / "manifest.json").read_text())
    assert manifest["source_sha256"]
    for name, digest in manifest["source_sha256"].items():
        assert sha256(DESIGN / name) == digest, f"Regenerate fab after changing {name}"
    recorded = {}
    for line in (FAB / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ", 1)
        recorded[name] = digest
        assert sha256(FAB / name) == digest
    assert set(recorded) == {p.relative_to(FAB).as_posix() for p in FAB.rglob("*")
                             if p.is_file() and p.name != "SHA256SUMS.txt"}


def test_spi_fab_procurement_covers_all_parts_and_safe_variant() -> None:
    procurement = rows(DESIGN / "BOM.csv")
    all_refs = {ref for row in procurement for ref in row["References"].split()}
    assert len(all_refs) == sum(int(row["Quantity"]) for row in procurement) == 18
    assembled = {}
    hand = set()
    for row in procurement:
        refs = set(row["References"].split())
        assert row["Checked Date"] == "2026-11-15" and row["Stock"]
        assert row["Procurement"] in {"hand-solder", "JLCPCB"}
        if row["Procurement"] == "hand-solder":
            hand |= refs
            assert row["Sourcing Notes"]
        else:
            assert row["Initial Assembly"] == "FIT"
            assert re.fullmatch(r"C\d+", row["LCSC Part #"])
            assert row["Source URL"].startswith("https://www.lcsc.com/")
            assembled.update({ref: row for ref in refs})
    assert hand == {"J1", "JP1", "C2", "R1", "R4"}
    assert {ref for row in rows(FAB / "HAND_SOLDER.csv") for ref in row["References"].split()} == hand
    bom = rows(FAB / "JLCPCB_BOM.csv")
    assert list(bom[0]) == ["Comment", "Designator", "Footprint", "LCSC Part #"]
    uploaded = [ref for row in bom for ref in row["Designator"].split(",")]
    assert len(uploaded) == len(set(uploaded)) == 13
    assert set(uploaded) == set(assembled)
    for row in bom:
        for ref in row["Designator"].split(","):
            assert row["Comment"] == assembled[ref]["Manufacturer Part Number"]
            assert row["LCSC Part #"] == assembled[ref]["LCSC Part #"]
    cpl = rows(FAB / "JLCPCB_CPL.csv")
    assert list(cpl[0]) == ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]
    assert len(cpl) == len({row["Designator"] for row in cpl}) == 13
    assert {row["Designator"] for row in cpl} == set(uploaded)
    native = {row["Ref"]: row for row in rows(FAB / "kicad-positions.csv")}
    for row in cpl:
        original = native[row["Designator"]]
        assert row["Layer"] == "Top" and original["Side"] == "top"
        assert float(row["Mid X"].removesuffix("mm")) == float(original["PosX"])
        assert float(row["Mid Y"].removesuffix("mm")) == float(original["PosY"])
        assert float(row["Rotation"]) == float(original["Rot"]) % 360


@pytest.mark.skipif(not shutil.which("kicad-cli"), reason="KiCad 9 required for native regeneration")
def test_spi_fab_regenerates_from_canonical_board(tmp_path: Path) -> None:
    # Actual CLI export, not a mocked file-existence test. Also guards deterministic ZIPs.
    result = subprocess.run(["/usr/bin/python3", str(DESIGN / "export_fab.py"), "--output", str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = {p.relative_to(FAB) for p in FAB.rglob("*") if p.is_file()}
    assert {p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file()} == expected
    for relative in expected:
        assert (tmp_path / relative).read_bytes() == (FAB / relative).read_bytes(), str(relative)
