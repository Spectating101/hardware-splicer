from __future__ import annotations

import csv
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
SPEC = importlib.util.spec_from_file_location("spi_design_checks", DESIGN / "design_checks.py")
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reference_design_authority_remains_bounded() -> None:
    manifest = json.loads((DESIGN / "design_manifest.json").read_text())

    assert manifest["result_status"] == "bounded_pre_fabrication_result"
    assert manifest["authority"] == {
        "modeled_evidence_only": True,
        "human_ee_review_complete": False,
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
    }
    assert manifest["target"]["first_transaction"] == "read-only JEDEC ID command 0x9F"
    assert manifest["target"]["initial_spi_clock_hz"] == 5_000_000
    assert len(manifest["remaining_blockers"]) >= 6


def test_reference_design_binds_exact_parts_and_bringup_controls() -> None:
    rows = list(csv.DictReader((DESIGN / "BOM.csv").open()))
    part_numbers = {row["Manufacturer Part Number"] for row in rows}

    assert {
        "TXU0304PWR",
        "W25Q128JWSIQ",
        "TLV75518PDBVR",
        "TSW-106-07-T-S",
    }.issubset(part_numbers)

    schematic = (DESIGN / "spi_flash_adapter_v1.kicad_sch").read_text()
    board = (DESIGN / "spi_flash_adapter_v1.kicad_pcb").read_text()
    for token in ("TXU0304PWR", "W25Q128JWSIQ", "TLV75518PDBVR", "DUT_1V8", "R4", "TP15", "TRANSLATOR_OE", "JP1", "R5", "R6", "R7"):
        assert token in schematic
        assert token in board
    assert "MODELED - NOT POWER AUTHORIZED" in board


def test_reference_design_verification_receipt_matches_canonical_files() -> None:
    receipt = json.loads((DESIGN / "verification.json").read_text())

    assert receipt["result"] == "pass"
    assert set(receipt["checks"].values()) == {0}
    assert receipt["board_inventory"]["testpoints"] == 18
    assert receipt["board_inventory"]["mounting_holes"] == 4
    assert receipt["board_inventory"]["ground_zones"] == 2
    assert receipt["board_inventory"]["ground_stitching_vias"] >= 20
    expected_paths = {name: DESIGN / filename for name, filename in CHECKS.RECEIPT_INPUTS.items()}
    assert set(receipt["artifact_sha256"]) == set(expected_paths)
    for name, path in expected_paths.items():
        assert receipt["artifact_sha256"][name] == _sha256(path)


def clean_drc() -> dict:
    return {"$schema": "https://schemas.kicad.org/drc.v1.json", "source": "spi_flash_adapter_v1.kicad_pcb",
            "violations": [], "unconnected_items": [], "schematic_parity": []}


CLEAN_DRC_STDOUT = "Found 0 violations\nFound 0 unconnected items\nFound 0 schematic parity issues\n"


@pytest.mark.parametrize("key", ["$schema", "violations", "unconnected_items", "schematic_parity"])
def test_drc_rejects_incomplete_report(key: str) -> None:
    report = clean_drc()
    del report[key]
    with pytest.raises(ValueError):
        CHECKS.validate_drc(report, CLEAN_DRC_STDOUT, set())


def test_drc_rejects_unparsed_summary_violation() -> None:
    with pytest.raises(ValueError, match="disagree"):
        CHECKS.validate_drc(clean_drc(), CLEAN_DRC_STDOUT.replace("0 violations", "1 violations"), set())


def test_kicad_first_run_notice_can_prefix_summary() -> None:
    stdout = "footprint-library first-run notice. Found 0 violations\n"
    assert CHECKS.reported_count(stdout, "violations") == 0


@pytest.mark.parametrize("violation", ["clearance", "new_unknown_violation", "lib_footprint_mismatch"])
def test_drc_never_blanket_waives_violation_classes(violation: str) -> None:
    report = clean_drc()
    report["violations"] = [{"type": violation, "severity": "warning", "description": "test violation", "items": [{"uuid": "unreviewed"}]}]
    with pytest.raises(ValueError, match="actionable"):
        CHECKS.validate_drc(report, CLEAN_DRC_STDOUT.replace("0 violations", "1 violations"), {"different-footprint"})


def test_library_advisory_requires_independently_checked_pad_geometry() -> None:
    report = clean_drc()
    report["violations"] = [{"type": "lib_footprint_mismatch", "severity": "warning", "description": "nonpad library graphics drift", "items": [{"uuid": "pad-geometry-checked"}]}]
    assert len(CHECKS.validate_drc(report, CLEAN_DRC_STDOUT.replace("0 violations", "1 violations"), {"pad-geometry-checked"})) == 1
    report["violations"][0]["severity"] = "exclusion"
    with pytest.raises(ValueError, match="severity"):
        CHECKS.validate_drc(report, CLEAN_DRC_STDOUT.replace("0 violations", "1 violations"), {"pad-geometry-checked"})


def test_project_cannot_disable_clearance_checks() -> None:
    project = json.loads((DESIGN / "spi_flash_adapter_v1.kicad_pro").read_text())
    CHECKS.validate_rules(project)
    project["board"]["design_settings"]["rule_severities"]["clearance"] = "ignore"
    with pytest.raises(ValueError, match="critical DRC"):
        CHECKS.validate_rules(project)


def test_read_return_budget_includes_outward_clock() -> None:
    manifest = json.loads((DESIGN / "design_manifest.json").read_text())
    CHECKS.validate_timing(manifest)
    assert manifest["timing_budget"]["known_read_return_residual_ns"] == 60
    manifest["timing_budget"]["known_read_return_residual_ns"] = 79
    with pytest.raises(ValueError, match="path segment"):
        CHECKS.validate_timing(manifest)


@pytest.fixture(scope="module")
def exported_netlist(tmp_path_factory) -> ET.Element:
    if not shutil.which("kicad-cli"):
        pytest.skip("native netlist regression checks require KiCad 9")
    output = tmp_path_factory.mktemp("spi-contract") / "netlist.xml"
    subprocess.run(["kicad-cli", "sch", "export", "netlist", str(DESIGN / "spi_flash_adapter_v1.kicad_sch"),
                    "--format", "kicadxml", "-o", str(output)], check=True, capture_output=True, text=True)
    return ET.parse(output).getroot()


def test_actual_netlist_has_safe_defaults_and_complete_bom(exported_netlist: ET.Element) -> None:
    CHECKS.validate_topology(exported_netlist)
    CHECKS.validate_bom(exported_netlist, list(csv.DictReader((DESIGN / "BOM.csv").open())))


@pytest.mark.parametrize("reference,pin", [("U1", "8"), ("R5", "2"), ("R6", "2"), ("R7", "2"), ("U2", "8")])
def test_topology_rejects_enable_bias_and_domain_regressions(exported_netlist: ET.Element, reference: str, pin: str) -> None:
    root = copy.deepcopy(exported_netlist)
    for net in root.findall("./nets/net"):
        if net.find(f"node[@ref='{reference}'][@pin='{pin}']") is not None:
            net.set("name", "/BROKEN")
            break
    with pytest.raises(ValueError, match="required topology"):
        CHECKS.validate_topology(root)


def test_initial_variant_rejects_fitted_rail_link(exported_netlist: ET.Element) -> None:
    root = copy.deepcopy(exported_netlist)
    resistor = root.find("./components/comp[@ref='R4']")
    resistor.remove(resistor.find("property[@name='dnp']"))
    with pytest.raises(ValueError, match="initial assembly"):
        CHECKS.validate_topology(root)


@pytest.mark.parametrize("column,value", [("Quantity", "99"), ("Manufacturer Part Number", "wrong-part"), ("Footprint", "wrong-footprint"), ("Initial Assembly", "DNP")])
def test_bom_rejects_quantity_identity_and_assembly_drift(exported_netlist: ET.Element, column: str, value: str) -> None:
    rows = list(csv.DictReader((DESIGN / "BOM.csv").open()))
    rows[0][column] = value
    with pytest.raises(ValueError, match="BOM"):
        CHECKS.validate_bom(exported_netlist, rows)


def test_bom_rejects_omitted_passive(exported_netlist: ET.Element) -> None:
    rows = list(csv.DictReader((DESIGN / "BOM.csv").open()))
    rows = [row for row in rows if row["References"] != "C2"]
    with pytest.raises(ValueError, match="missing BOM"):
        CHECKS.validate_bom(exported_netlist, rows)
