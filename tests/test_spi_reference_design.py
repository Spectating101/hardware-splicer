from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "hardware" / "reference_designs" / "spi_flash_adapter_v1"


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
    for token in ("TXU0304PWR", "W25Q128JWSIQ", "TLV75518PDBVR", "DUT_1V8", "R4", "TP15"):
        assert token in schematic
        assert token in board
    assert "MODELED - NOT POWER AUTHORIZED" in board


def test_reference_design_verification_receipt_matches_canonical_files() -> None:
    receipt = json.loads((DESIGN / "verification.json").read_text())

    assert receipt["result"] == "pass"
    assert set(receipt["checks"].values()) == {0}
    assert receipt["board_inventory"]["testpoints"] == 15
    assert receipt["board_inventory"]["mounting_holes"] == 4
    expected_paths = {
        "schematic": DESIGN / "spi_flash_adapter_v1.kicad_sch",
        "pcb": DESIGN / "spi_flash_adapter_v1.kicad_pcb",
        "bom": DESIGN / "BOM.csv",
        "design_manifest": DESIGN / "design_manifest.json",
    }
    for name, path in expected_paths.items():
        assert receipt["artifact_sha256"][name] == _sha256(path)
