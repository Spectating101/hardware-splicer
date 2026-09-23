from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "hardware" / "reference_designs" / "proofpod_v0"
RUN = ROOT / "experiments" / "product_factory" / "run-001-proofpod.json"


def test_pf001_is_a_real_gated_factory_run() -> None:
    run = json.loads(RUN.read_text())
    states = {stage["id"]: stage["state"] for stage in run["stages"]}
    assert run["run_id"] == "PF-001"
    assert states["DISCOVER"] == "PASS"
    assert states["SELECT"] == "PASS"
    assert states["SPECIFY"] == "PASS"
    assert states["DESIGN_SCHEMATIC"] == "ACTIVE"
    assert states["DESIGN_PCB"] == "BLOCKED_ON_SCHEMATIC"
    assert states["BUILD"] == "BLOCKED_ON_SOURCE_AND_HUMAN_AUTHORITY"
    assert states["SELL"] == "BLOCKED_ON_BENCHMARK_AND_HUMAN_DECISION"


def test_proofpod_architecture_closes_the_current_limit_defect() -> None:
    manifest = json.loads((PILOT / "architecture_manifest.json").read_text())
    power = manifest["target_power_contract"]
    selected = manifest["selected_components"]
    assert selected["target_current_limit_switch"]["mpn"] == "TPS2553DBVR"
    assert power["ilim_resistor_ohm"] == 133000
    assert power["datasheet_max_current_limit_ma_at_1pct_resistor_approx"] < power["contract_max_current_limit_ma"]
    assert power["reverse_voltage_protection_required"] is True
    assert power["default_power_state"] == "OFF"


def test_factory_does_not_convert_design_progress_into_authority() -> None:
    manifest = json.loads((PILOT / "architecture_manifest.json").read_text())
    authority = manifest["authority"]
    assert authority["fabrication_ready"] is False
    assert authority["power_on_ready"] is False
    assert authority["physical_correctness"] == "UNPROVEN"
    assert authority["commercial_superiority"] == "UNPROVEN"
    assert authority["physical_authority_granted"] is False


def test_remaining_commercial_hardware_work_is_explicit() -> None:
    manifest = json.loads((PILOT / "architecture_manifest.json").read_text())
    blockers = " ".join(manifest["remaining_blockers_before_pcb"]).lower()
    assert "usb-c" in blockers
    assert "crystal" in blockers
    assert "esd" in blockers
    assert "independent ee review" in blockers


def test_safety_critical_symbols_are_local_and_reviewable() -> None:
    symbols = (PILOT / "HardwareSplicer.kicad_sym").read_text()
    assert 'symbol "TXU0304PW"' in symbols
    assert 'symbol "TPS2553DBV"' in symbols
    assert 'symbol "INA219DCN"' in symbols
    assert 'symbol "RP2040QFN56"' in symbols
    assert "tps2553.pdf" in symbols
    assert "ina219.pdf" in symbols
