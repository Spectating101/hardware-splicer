"""Independent source-netlist parity and failure-closed converter recovery tests."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hardware_splicer.integrations.circuit_json_import import circuit_json_to_netlist
from hardware_splicer.integrations.kicad_circuit_json_recovery import (
    recover_connected_source_circuit_json,
)
from hardware_splicer.netlist.import_kicad import parse_kicad_netlist

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/main_ctrl_esp32_servo.net"
SCRIPT = ROOT / "examples/integrations/kicad-circuit-json/recover_connections.py"
SCHEMATIC = ROOT / "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch"


def _topology(nets):
    return {net.name: sorted(p.key() for p in net.pins) for net in nets if len(net.pins) >= 2}


def _unconnected_geometry_only():
    return [
        {"type": "source_component", "source_component_id": "c0", "name": "UnknownChip"},
        {"type": "source_port", "source_port_id": "p0", "source_component_id": "c0", "pin_number": 1},
        {"type": "source_net", "source_net_id": "n0", "name": "POWER", "member_source_group_ids": []},
        {"type": "schematic_trace", "schematic_trace_id": "t0",
         "edges": [{"from": {"x": 0, "y": 0}, "to": {"x": 5, "y": 2}}], "junctions": []},
    ]


def test_upstream_geometry_cannot_claim_connected_circuit_by_itself():
    raw = circuit_json_to_netlist(_unconnected_geometry_only())
    assert len(raw.components) == 1
    assert len(raw.nets) == 0
    assert raw.metadata["circuit_json"]["source_trace_count"] == 0
    assert raw.metadata["circuit_json"]["legacy_schematic_trace_count"] == 1


def test_kicad_reference_export_roundtrips_exact_14_nets_and_40_pins():
    text=FIXTURE.read_text(encoding="utf-8")
    source=parse_kicad_netlist(text)
    out=recover_connected_source_circuit_json(text,external_converter_docs=_unconnected_geometry_only())
    imported=circuit_json_to_netlist(out["documents"])
    assert _topology(imported.nets)==_topology(source.nets)
    receipt=out["receipt"]
    assert (receipt["components"],receipt["source_nets"],receipt["source_pin_memberships"])==(9,14,40)
    assert receipt["imported_multi_pin_memberships"]==40
    assert receipt["topology_exact_multi_pin_match"]
    assert receipt["source_single_pin_nets"]=={}
    assert not receipt["external_converter"]["geometry_and_component_identity_reconciled"]
    assert not receipt["external_converter"]["original_converter_topology_approved"]
    assert not receipt["manufacturing_authorized"]


@pytest.mark.parametrize("net_text",[
    '(export (components (comp (ref "U1") (value "IC"))) (nets (net (code "1") (name "A") (node (ref "NOPE") (pin "1")) (node (ref "U1") (pin "1")))))',
    '(export (components (comp (ref "U1") (value "IC"))) (nets (net (code "1") (name "A") (node (ref "U1") (pin "1")) (node (ref "U1") (pin "2"))) (net (code "2") (name "B") (node (ref "U1") (pin "2")) (node (ref "U1") (pin "3")))))',
    '(export (components (comp (ref "U1") (value "IC"))) (nets (net (code "1") (name "NC") (node (ref "U1") (pin "1")))))',
    '(export (components) (nets))',
])
def test_unsafe_or_unsupported_source_connectivity_must_fail_closed(net_text):
    with pytest.raises(ValueError):
        recover_connected_source_circuit_json(net_text)


def test_existing_fixture_recovery_cli_writes_strict_receipt(tmp_path):
    docs=tmp_path/"geometry.json"
    docs.write_text(json.dumps(_unconnected_geometry_only()),encoding="utf-8")
    out=tmp_path/"source.json"
    receipt=tmp_path/"receipt.json"
    proc=subprocess.run([
        sys.executable,str(SCRIPT),"--netlist-export",str(FIXTURE),
        "--converter-json",str(docs),"--out",str(out),"--receipt",str(receipt),
    ],check=True,capture_output=True,text=True,timeout=20)
    stdout=json.loads(proc.stdout)
    assert stdout["connected_nets"]==14
    assert stdout["connected_pin_memberships"]==40
    assert stdout["converter_geometry_merged"] is False
    imported=circuit_json_to_netlist(json.loads(out.read_text(encoding="utf-8")))
    assert len(imported.nets)==14
    data=json.loads(receipt.read_text())
    assert data["source_sha256"]==hashlib.sha256(FIXTURE.read_bytes()).hexdigest()


@pytest.mark.skipif(shutil.which("kicad-cli") is None,reason="official KiCad CLI not installed")
def test_actual_kicad_export_has_36_components_16_connected_nets_76_connected_pins(tmp_path):
    exported=tmp_path/"official.net"
    proc=subprocess.run(
        ["kicad-cli","sch","export","netlist","--format","kicadsexpr",
         "--output",str(exported),str(SCHEMATIC)],
        capture_output=True,text=True,timeout=90,
    )
    assert proc.returncode==0,proc.stderr
    source=parse_kicad_netlist(exported.read_text())
    recovered=recover_connected_source_circuit_json(exported.read_text())
    expected={name:pins for name,pins in _topology(source.nets).items()}
    ir=circuit_json_to_netlist(recovered["documents"])
    assert _topology(ir.nets)==expected
    report=recovered["receipt"]
    assert (report["components"],report["source_nets"],report["source_pin_memberships"])==(36,19,79)
    assert (report["connected_multi_pin_nets"],report["imported_multi_pin_memberships"])==(16,76)
    assert sorted(report["source_single_pin_nets"]) == [
        "unconnected-(U1-NC-Pad6)","unconnected-(U1-NC-Pad9)","unconnected-(U3-NC-Pad4)"
    ]
    assert report["topology_exact_multi_pin_match"]
    assert not report["pcb_erc_or_drc_certified"]


def test_source_connected_circuit_json_is_accepted_only_as_interchange_not_fabrication():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from hardware_splicer.product_api import create_product_app
    docs=recover_connected_source_circuit_json(FIXTURE.read_text())["documents"]
    with TestClient(create_product_app()) as client:
        response=client.post(
            "/v1/interchange/circuit-json/inspect",
            json={"documents":docs,"source_label":"official_kicad_export"}
        )
    assert response.status_code==200
    body=response.json()
    assert body["compilable"] is True
    assert body["summary"]["component_count"]==9
    assert body["summary"]["net_count"]==14
    # API "ready" is source interchange readiness ONLY, never physical signoff.
    assert body["authority"]=="proposed"
    assert "fabrication_authorized" not in body
