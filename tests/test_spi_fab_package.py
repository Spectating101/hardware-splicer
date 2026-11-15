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
# Only these complete header records carry an exporter-version value. Keep all
# other bytes, including the fixed CreationDate/comment dates, byte-exact.
KICAD_VERSION = rb"9\.\d+\.\d+(?:[-+~.][0-9A-Za-z.+~_-]+)?"
VERSION_HEADERS = (
    rb"^(%TF\.GenerationSoftware,KiCad,Pcbnew,)" + KICAD_VERSION + rb"(\*%)$",
    rb"^(G04 Created by KiCad \(PCBNEW )" + KICAD_VERSION + rb"(\) date [^\r\n]*\*)$",
    rb"^(; #@! TF\.GenerationSoftware,Kicad,Pcbnew,)" + KICAD_VERSION + rb"()$",
    rb"^(; DRILL file \{KiCad )" + KICAD_VERSION + rb"(\} date [^\r\n]*)$",
)


def without_kicad_version_metadata(payload: bytes) -> bytes:
    for pattern in VERSION_HEADERS:
        payload = re.sub(pattern, rb"\g<1><KiCad 9 version>\g<2>", payload, flags=re.MULTILINE)
    return payload


def require_kicad9() -> str:
    executable = shutil.which("kicad-cli")
    if executable is None:
        pytest.skip("Native fab regeneration requires KiCad 9; kicad-cli is absent")
    result = subprocess.run([executable, "--version"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    version = result.stdout.strip()
    assert re.match(r"\d+\.", version), f"Unrecognized kicad-cli version: {version!r}"
    if not version.startswith("9."):
        pytest.skip(f"Native fab regeneration requires KiCad major 9; found {version}; requalification required")
    return version


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


def assert_fab_hashes_current(directory: Path) -> None:
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["source_sha256"]
    for name, digest in manifest["source_sha256"].items():
        assert sha256(DESIGN / name) == digest, f"Regenerate fab after changing {name}"
    recorded = {}
    for line in (directory / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert name not in recorded
        recorded[name] = digest
        assert sha256(directory / name) == digest, name
    assert set(recorded) == {p.relative_to(directory).as_posix() for p in directory.rglob("*")
                            if p.is_file() and p.name != "SHA256SUMS.txt"}


def test_spi_fab_hashes_and_canonical_sources_are_current() -> None:
    assert_fab_hashes_current(FAB)


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
    # U2/U3 stay out of factory placement until an exact-part rotation is proven.
    assert hand == {"J1", "JP1", "C2", "R1", "R4", "U2", "U3"}
    assert {ref for row in rows(FAB / "HAND_SOLDER.csv") for ref in row["References"].split()} == hand
    bom = rows(FAB / "JLCPCB_BOM.csv")
    assert list(bom[0]) == ["Comment", "Designator", "Footprint", "LCSC Part #"]
    uploaded = [ref for row in bom for ref in row["Designator"].split(",")]
    assert len(bom) == 4
    assert len(uploaded) == len(set(uploaded)) == 11
    assert set(uploaded) == set(assembled)
    for row in bom:
        for ref in row["Designator"].split(","):
            assert row["Comment"] == assembled[ref]["Manufacturer Part Number"]
            assert row["LCSC Part #"] == assembled[ref]["LCSC Part #"]
    cpl = rows(FAB / "JLCPCB_CPL.csv")
    assert list(cpl[0]) == ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]
    assert len(cpl) == len({row["Designator"] for row in cpl}) == 11
    assert {row["Designator"] for row in cpl} == set(uploaded)
    native = {row["Ref"]: row for row in rows(FAB / "kicad-positions.csv")}
    for row in cpl:
        original = native[row["Designator"]]
        assert row["Layer"] == "Top" and original["Side"] == "top"
        assert float(row["Mid X"].removesuffix("mm")) == float(original["PosX"])
        assert float(row["Mid Y"].removesuffix("mm")) == float(original["PosY"])
        assert float(row["Rotation"]) == float(original["Rot"]) % 360


def test_spi_fab_top_legend_meets_published_limits() -> None:
    # JLCPCB: stroke >= 0.15 mm, text height >= 1.0 mm, pad-to-silk >= 0.15 mm.
    legend = (FAB / "gerbers" / f"{NAME}.GTO").read_text()
    apertures = {code: float(diameter) for code, diameter in re.findall(r"%ADD(\d+)C,([\d.]+)\*%", legend)}
    drawn, current = set(), None
    for line in legend.splitlines():
        selected = re.fullmatch(r"D(\d{2,})\*", line)
        if selected:
            current = selected[1]
        elif line.endswith("D01*"):
            drawn.add(current)
    assert drawn and drawn <= set(apertures), "legend strokes must use round apertures"
    assert min(apertures[code] for code in drawn) >= 0.15
    board = (DESIGN / f"{NAME}.kicad_pcb").read_text()
    text = (r'\(%s "[^"]*"\s*\(at [^)]*\)\s*\(layer "F\.SilkS"\)\s*\(uuid "[^"]*"\)\s*\(effects\s*'
            r'\(font\s*\(size ([\d.]+) ([\d.]+)\)\s*\(thickness ([\d.]+)\)')
    labels = re.findall(text % "gr_text", board)
    references = re.findall(text % 'property "Reference"', board)
    assert len(labels) == 5 and len(references) == 36  # H1-H4 references are hidden
    for height, width, thickness in labels + references:
        assert float(height) >= 1.0 and float(width) >= 1.0 and float(thickness) >= 0.15
    testpoints = re.findall(
        r'\(fp_circle\s*\(center 0 0\)\s*\(end ([\d.]+) 0\)\s*\(stroke\s*\(width ([\d.]+)\)'
        r'\s*\(type solid\)\s*\)\s*\(fill \w+\)\s*\(layer "F\.SilkS"\)', board)
    assert len(testpoints) == 18
    for radius, width in testpoints:
        # Circle inner edge to the 0.75 mm radius pad.
        assert float(radius) - float(width) / 2 - 0.75 >= 0.15


def test_spi_fab_regenerates_from_canonical_board(tmp_path: Path) -> None:
    version = require_kicad9()
    # Actual CLI export. Different KiCad 9 builds may identify themselves differently
    # without changing any artwork. Never normalize apertures, coordinates or drills.
    result = subprocess.run(["/usr/bin/python3", str(DESIGN / "export_fab.py"), "--output", str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert_fab_hashes_current(FAB)
    assert_fab_hashes_current(tmp_path)
    assert json.loads((tmp_path / "manifest.json").read_text())["kicad_cli"] == version
    expected = {p.relative_to(FAB) for p in FAB.rglob("*") if p.is_file()}
    assert {p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file()} == expected
    for relative in expected:
        actual = (tmp_path / relative).read_bytes()
        recorded = (FAB / relative).read_bytes()
        if relative.parts[0] == "gerbers":
            actual = without_kicad_version_metadata(actual)
            recorded = without_kicad_version_metadata(recorded)
        elif relative.name == "manifest.json":
            # Only kicad_cli varies; source hashes and all other manifest bytes stay exact.
            pattern = rb'^(  "kicad_cli": ")' + KICAD_VERSION + rb'(",)$'
            actual = re.sub(pattern, rb"\g<1><KiCad 9 version>\g<2>", actual, flags=re.MULTILINE)
            recorded = re.sub(pattern, rb"\g<1><KiCad 9 version>\g<2>", recorded, flags=re.MULTILINE)
        elif relative.suffix == ".zip":
            # CRCs, lengths and compressed bytes depend on version-bearing contents.
            # Check container metadata, CRC integrity and every uncompressed member.
            with zipfile.ZipFile(tmp_path / relative) as fresh, zipfile.ZipFile(FAB / relative) as saved:
                assert fresh.namelist() == saved.namelist()
                assert fresh.comment == saved.comment
                assert fresh.testzip() is None
                for filename in saved.namelist():
                    for attribute in ("date_time", "compress_type", "comment", "extra", "flag_bits",
                                      "create_system", "create_version", "extract_version",
                                      "internal_attr", "external_attr", "reserved", "volume"):
                        actual_attribute = getattr(fresh.getinfo(filename), attribute)
                        recorded_attribute = getattr(saved.getinfo(filename), attribute)
                        assert actual_attribute == recorded_attribute, (filename, attribute)
                    assert fresh.read(filename) == (tmp_path / "gerbers" / filename).read_bytes()
                    actual_member = without_kicad_version_metadata(fresh.read(filename))
                    recorded_member = without_kicad_version_metadata(saved.read(filename))
                    assert actual_member == recorded_member, filename
            continue
        elif relative.name == "SHA256SUMS.txt":
            # Each package's hashes bind its actual bytes, including version metadata
            # and ZIP compression, and were verified above. Only digest fields can
            # differ here; still compare filenames, ordering and whitespace exactly.
            pattern = rb"^[0-9a-f]{64}(  )"
            actual = re.sub(pattern, rb"<verified SHA-256>\g<1>", actual, flags=re.MULTILINE)
            recorded = re.sub(pattern, rb"<verified SHA-256>\g<1>", recorded, flags=re.MULTILINE)
        assert actual == recorded, str(relative)


@pytest.mark.parametrize("suffix", [f".{ext}" for ext in FUNCTIONS] + ["-PTH.XLN", "-NPTH.XLN"])
def test_spi_fab_comparison_allows_only_documented_version_headers(suffix: str) -> None:
    payload = (FAB / "gerbers" / f"{NAME}{suffix}").read_bytes()
    # Reproduce the CI 9.0.8 vs checked-in 9.0.2 metadata mismatch on every layer/drill.
    changed = re.sub(KICAD_VERSION, b"9.0.8+ci-test-build", payload)
    assert changed != payload
    assert without_kicad_version_metadata(changed) == without_kicad_version_metadata(payload)


@pytest.mark.parametrize("suffix,before,after", [
    (".GBS", b"%ADD10R,1.700000X1.700000*%", b"%ADD10R,1.800000X1.700000*%"),
    (".GBS", b"X147000000Y-98000000D03*", b"X147000001Y-98000000D03*"),
    ("-PTH.XLN", b"T1C0.300", b"T1C0.301"),
    ("-PTH.XLN", b"X110.0Y-70.0", b"X110.1Y-70.0"),
    (".GBS", b"%TF.FileFunction,Soldermask,Bot*%", b"%TF.FileFunction,Soldermask,Top*%"),
    (".GBS", b"2026-11-15T00:00:00Z", b"2026-11-16T00:00:00Z"),
    ("-PTH.XLN", b"2026-11-15T00:00:00Z", b"2026-11-16T00:00:00Z"),
    (".GBS", b"9.0.2+dfsg-1", b"10.0.2+dfsg-1"),
])
def test_spi_fab_comparison_preserves_geometry_drills_and_other_metadata(
    suffix: str, before: bytes, after: bytes,
) -> None:
    payload = (FAB / "gerbers" / f"{NAME}{suffix}").read_bytes()
    assert before in payload
    assert without_kicad_version_metadata(payload.replace(before, after)) != without_kicad_version_metadata(payload)


@pytest.mark.parametrize("version", [None, "8.0.9", "10.0.0"])
def test_spi_fab_regeneration_skips_unsupported_toolchain(monkeypatch, version: str | None) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "kicad-cli" if version else None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, version, ""))
    reason = "kicad-cli is absent" if version is None else f"found {version}; requalification required"
    with pytest.raises(pytest.skip.Exception, match=reason):
        require_kicad9()
