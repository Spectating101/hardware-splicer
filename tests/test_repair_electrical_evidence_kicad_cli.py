"""Optional independent KiCad CLI source-export oracle.

Run only when genuine KiCad is available; no hand-authored file can
substitute for an actual schematic export from KiCad itself.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from hardware_splicer.netlist.import_kicad import parse_kicad_netlist
from hardware_splicer.repair_electrical_evidence import capture_repair_evidence

ROOT = Path(__file__).resolve().parents[1]
SCHEMATIC = ROOT / "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch"


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="independent KiCad CLI unavailable")
def test_real_kicad_cli_export_preserves_36_components_19_nets_79_pins(tmp_path: Path) -> None:
    """The upstream exporter, not HS or a hand-written fixture, is the oracle."""
    net_file = tmp_path / "reference.net"
    proc = subprocess.run(
        ["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
         "--output", str(net_file), str(SCHEMATIC)],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, text=True, timeout=80,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    ir = parse_kicad_netlist(net_file.read_text(encoding="utf-8"))
    assert len(ir.components) == 36
    assert len(ir.nets) == 19
    assert sum(len(net.pins) for net in ir.nets) == 79
    refs = {c.ref for c in ir.components}
    assert all(p.component_ref in refs for net in ir.nets for p in net.pins)
    by_net = {net.name: {p.key() for p in net.pins} for net in ir.nets}
    assert "C2.1" in by_net["/1V8"]
    # Synthetic numbers are exclusively testing ID reconciliation; neither
    # the KiCad source nor this test measures the physical device.
    obs = tmp_path / "SYNTHETIC_measurements.csv"
    with obs.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "observation_id","observed_at","component_ref","pin",
            "measurement_kind","value","unit","instrument_id","operator_id","condition"
        ])
        writer.writerow([
            "SYNTH1","2026-10-01T09:00:00+08:00","C2","1",
            "dc_voltage","1.8","V","SYNTH_ONLY","SYNTH_ONLY","idle"
        ])
    result = capture_repair_evidence(net_file, obs)
    assert result["netlist"]["components"] == 36
    assert result["netlist"]["nets"] == 19
    assert result["netlist"]["pins_mapped"] == 79
    assert result["observations"][0]["net"] == "/1V8"
    assert result["physical_repair_verified"] is False
    assert result["failed_component_identified"] is False
    assert result["power_on_authorized"] is False
