"""Real reference board/BOM/source-receipt handoff, including negative mutations."""
from __future__ import annotations
import csv
import json
import shutil
from pathlib import Path

from hardware_splicer.spi_reference_handoff import (
    RECEIPT_FILES, build_spi_reference_handoff,
)

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "hardware" / "reference_designs" / "spi_flash_adapter_v1"


def test_canonical_reference_yields_reconciled_picklist_not_fabrication_authority(tmp_path):
    report = build_spi_reference_handoff(CANON, output_dir=tmp_path)
    assert report["audit_status"] == "source_consistent_historical_receipt_only", report["issues"]
    assert not report["issues"]
    assert report["historical_native_receipt_hash_bound"] is True
    assert len(report["source_receipt_bindings"]) == 9
    assert all(r["hash_matches_frozen_receipt"] for r in report["source_receipt_bindings"].values())
    assert report["bom_total_positions"] == 18
    assert report["bom_to_fit"] == 16
    assert report["bom_dnp"] == 2
    assert report["test_pad_footprints_not_purchase_parts"] == 18
    assert report["mounting_hole_footprints_not_purchase_parts"] == 4
    assert report["assembly_plan_fitted_footprints_including_board_features"] == 38
    assert report["native_kicad_erc_drc_reexecuted"] is False
    assert not report["fabrication_authorized"] and not report["release_authorized"]
    assert not report["vendor_stock_or_price_verified"]
    with (tmp_path / "REFERENCE_ASSEMBLY_PICKLIST.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 18
    assert {row["ref"] for row in rows if row["assembly"] == "DNP"} == {"R1", "R4"}
    assert {row["ref"] for row in rows if row["assembly"] == "FIT"}.issuperset({"J1", "JP1", "U1", "U2", "U3"})
    assert all(not row["ref"].startswith("TP") for row in rows)
    review = (tmp_path / "REFERENCE_PREBUILD_REVIEW.md").read_text()
    assert "NO enable shunt" in review and "R1 and R4" in review


def _source_copy(tmp_path):
    src = tmp_path / "input"
    src.mkdir()
    for filename in set(RECEIPT_FILES.values()) | {"verification.json"}:
        shutil.copy2(CANON / filename, src / filename)
    return src


def test_post_receipt_bom_edit_must_block(tmp_path):
    source = _source_copy(tmp_path)
    p = source / "BOM.csv"
    p.write_text(p.read_text().replace("W25Q128JWSIQ", "FAKEFLASH"), encoding="utf-8")
    result = build_spi_reference_handoff(source, output_dir=tmp_path / "output")
    assert result["audit_status"] == "blocked_source_inconsistency"
    assert any("receipt does not match current bom" in issue for issue in result["issues"])
    assert not result["fabrication_authorized"]


def test_post_receipt_board_mutation_must_block(tmp_path):
    source = _source_copy(tmp_path)
    p = source / "spi_flash_adapter_v1.kicad_pcb"
    p.write_text(p.read_text() + "\n", encoding="utf-8")
    result = build_spi_reference_handoff(source, output_dir=tmp_path / "output")
    assert result["audit_status"] == "blocked_source_inconsistency"
    assert any("receipt does not match current pcb" in issue for issue in result["issues"])


def test_bom_missing_device_changes_parity_and_qty(tmp_path):
    source = _source_copy(tmp_path)
    path = source / "BOM.csv"
    path.write_text("\n".join(line for line in path.read_text().splitlines()
                              if not line.startswith("U2,")) + "\n")
    result = build_spi_reference_handoff(source, output_dir=tmp_path / "output")
    assert result["audit_status"] == "blocked_source_inconsistency"
    assert any("U2" in issue for issue in result["issues"])


def test_enclosure_only_changes_screening_not_authority(tmp_path):
    small = build_spi_reference_handoff(
        CANON, output_dir=tmp_path / "small",
        enclosure_inner_mm={"w": 50, "d": 40, "h": 9}
    )
    large = build_spi_reference_handoff(
        CANON, output_dir=tmp_path / "large",
        enclosure_inner_mm={"w": 125, "d": 85, "h": 60}
    )
    assert small["audit_status"] == large["audit_status"] == "source_consistent_historical_receipt_only"
    a = json.loads((tmp_path / "small" / "REFERENCE_DEVICE_DOSSIER.json").read_text())
    b = json.loads((tmp_path / "large" / "REFERENCE_DEVICE_DOSSIER.json").read_text())
    assert a["electromechanical_fit"]["status"] == "envelope_collision_detected"
    assert b["electromechanical_fit"]["status"] == "envelope_screen_clear_unverified"
    assert not small["release_authorized"] and not large["release_authorized"]
