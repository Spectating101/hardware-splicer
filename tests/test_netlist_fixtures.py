"""Netlist fixture suite (Phase A) — KiCad + JSON ingest without FreeRouting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.build_compiler import compile_from_netlist
from hardware_splicer.integrations.circuit_json_import import circuit_json_to_netlist
from hardware_splicer.netlist.import_kicad import parse_kicad_netlist
from hardware_splicer.netlist.ir import CircuitNetlist
from hardware_splicer.netlist.passives import suggest_passives

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "examples" / "netlist_fixtures"
MANIFEST = FIXTURE_ROOT / "manifest.json"


def _load_fixtures():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return list(data.get("fixtures") or [])


@pytest.mark.parametrize("fixture", _load_fixtures(), ids=lambda f: f["id"])
def test_netlist_fixture_compiles_kicad_clean(tmp_path: Path, fixture: dict) -> None:
    fixture_id = fixture["id"]
    rel = fixture["path"]
    path = FIXTURE_ROOT / rel
    assert path.is_file(), f"missing fixture file: {path}"

    if fixture.get("type") == "kicad_netlist":
        netlist = parse_kicad_netlist(path.read_text(encoding="utf-8"))
    else:
        netlist = CircuitNetlist.from_dict(json.loads(path.read_text(encoding="utf-8")))

    result = compile_from_netlist(
        netlist, tmp_path, build_id="generic_low_voltage_build", export_gerber=False
    )
    q = result.design_quality or {}
    assert result.ok, result.error
    assert int(q.get("kicad_drc_errors") or 0) == 0, q
    assert q.get("copper_tier") in {"cosmetic_preview", "placement_only"}
    assert q.get("fab_recommendation") == "review_required_preview_copper"
    assert q.get("kicad_truth_pass") is True


def test_circuit_json_roundtrip_import(tmp_path: Path) -> None:
    fixture = next(f for f in _load_fixtures() if f["id"] == "usb_esp_dht22")
    netlist = CircuitNetlist.from_dict(
        json.loads((FIXTURE_ROOT / fixture["path"]).read_text(encoding="utf-8"))
    )
    from hardware_splicer.integrations.circuit_json_adapter import netlist_to_circuit_json

    docs = netlist_to_circuit_json(netlist, source_build_id="roundtrip")
    imported = circuit_json_to_netlist(docs, source="circuit_json_roundtrip")
    assert len(imported.components) == len(netlist.components)
    assert len(imported.nets) >= 1


def test_passive_suggestions_on_i2c_fixture() -> None:
    fixture = next(f for f in _load_fixtures() if f["id"] == "usb_esp_bme280")
    netlist = CircuitNetlist.from_dict(
        json.loads((FIXTURE_ROOT / fixture["path"]).read_text(encoding="utf-8"))
    )
    suggestions = suggest_passives(netlist)
    kinds = {s.get("kind") for s in suggestions}
    assert "i2c_pullups" in kinds or "decoupling" in kinds
