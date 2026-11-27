"""HS-BUS-A: the generated schematic still closes its checks, and the committed board passes KiCad DRC with
schematic parity. Routing is not re-run here (FreeRouting takes minutes); the committed board is checked as built."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from hardware_splicer import kicad_component_board as kb

PROJECT = Path(__file__).resolve().parents[1] / "projects" / "hs-bus-a"
needs_kicad = pytest.mark.skipif(shutil.which("kicad-cli") is None or not (kb.symbol_dir() / "Device.kicad_sym").is_file(),
                                 reason="kicad-cli and the KiCad libraries are needed")


def _load(name: str):
    sys.path.insert(0, str(PROJECT))
    try:
        spec = importlib.util.spec_from_file_location(f"hs_bus_a_{name}", PROJECT / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(PROJECT))


@needs_kicad
def test_regenerated_schematic_matches_the_design_and_passes_erc(tmp_path: Path) -> None:
    design = _load("design").DESIGN
    sch = tmp_path / "hs_bus_a.kicad_sch"
    assert kb.pin_coverage(design)["pass"]
    kb.write_schematic(design, sch)
    parity = kb.netlist_parity(design, kb.schematic_netlist(sch))
    assert parity["pass"], parity
    assert kb.run_erc(sch, tmp_path)["errors"] == 0


@needs_kicad
def test_committed_board_passes_drc_with_schematic_parity(tmp_path: Path) -> None:
    for item in (PROJECT / "kicad").iterdir():
        if item.suffix in {".kicad_pcb", ".kicad_sch", ".kicad_pro"} or item.name in {"sym-lib-table", "fp-lib-table"}:
            shutil.copy(item, tmp_path / item.name)
    drc = kb.run_drc(tmp_path / "hs_bus_a.kicad_pcb", tmp_path)
    for group in ("violations", "unconnected_items", "schematic_parity"):
        assert drc[group]["errors"] == 0, (group, drc[group]["items"][:5])


def test_electrical_checks_hold_and_flag_what_they_should() -> None:
    result = _load("checks").run(1.2)
    assert result["logic_levels_pass"]
    reference = next(r for r in result["logic_levels"] if r["link"].startswith("ROBOTIS reference"))
    assert not reference["guaranteed"] and reference["high_margin_v"] < 0  # 3.2 V out against a 3.5 V threshold
    port = result["currents"]["per_port"]
    assert port["fuse_hold_within_connector_rating"] and port["track_rise_c_at_hold"] < 10
    volts = result["voltages"]
    assert volts["servo_window_v"]["common"] == [10.0, 12.0]
    assert volts["supply_at_window_edge"] and not volts["tvs"]["clamps_below_servo_max"]


def test_verification_record_matches_the_fab_files() -> None:
    record = json.loads((PROJECT / "verification.json").read_text())
    for group in ("violations", "unconnected_items", "schematic_parity"):
        assert record["drc"][group]["errors"] == 0
    assert record["schematic"]["erc_errors"] == 0 and record["schematic"]["kicad_readback_matches_design"]
    zip_path = PROJECT / "fab" / "hs_bus_a_gerbers.zip"
    assert hashlib.sha256(zip_path.read_bytes()).hexdigest() == record["fab"]["zip_sha256"]


def test_every_supply_pad_has_a_capacitor_within_five_mm():
    """Copper's layout critique (2026-11-27) found the FT232RL's VCC capacitor 11.3 mm from its pin; the caps now sit beside
    the pins they serve."""
    from hardware_splicer.component_board_pipeline import decoupling_report
    from hardware_splicer.routing_engine import resolve_kicad_python
    import subprocess as _sp
    py = resolve_kicad_python() or "/usr/bin/python3"
    if _sp.run([py, "-c", "import pcbnew"], capture_output=True).returncode:
        import pytest
        pytest.skip("pcbnew not available")
    report = decoupling_report(Path(__file__).resolve().parents[1] / "projects" / "hs-bus-a" / "kicad" / "hs_bus_a.kicad_pcb")
    assert report and report["pads"]
    assert max(r["distance_mm"] for r in report["pads"]) <= 5.0
    assert {(r["ic"], r["pad"]) for r in report["pads"]} >= {("U1", "20"), ("U1", "4"), ("U1", "17"), ("U2", "5"), ("U3", "5")}
