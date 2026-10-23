"""Execute genuine KiCad 9 hierarchical demo exports and strict HS interchange.

Requires KiCad CLI 9.x and the optional kicad-demos distribution. Does NOT
redistribute demo files or claim finished PCB/fabrication validity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.integrations.circuit_json_import import circuit_json_to_netlist
from hardware_splicer.integrations.kicad_circuit_json_recovery import recover_connected_source_circuit_json
from hardware_splicer.netlist.import_kicad import parse_kicad_netlist
from hardware_splicer.product_api import create_product_app

PROJECTS = (
    ("complex_hierarchy", "complex_hierarchy.kicad_sch", (68,52,164,50,162,3,0)),
    ("flat_hierarchy", "flat_hierarchy.kicad_sch", (64,117,238,34,161,3,6)),
    ("multichannel", "multichannel_mixer.kicad_sch", (114,80,280,79,279,5,0)),
)


def run(source_root: Path) -> dict:
    cli = shutil.which("kicad-cli")
    if not cli:
        raise RuntimeError("kicad-cli is required to validate genuine source exports")
    output = {}
    with tempfile.TemporaryDirectory(prefix="hs-kicad-hierarchy-") as scratch, TestClient(create_product_app()) as client:
        for directory, schematic_name, expected in PROJECTS:
            schematic = source_root / directory / schematic_name
            if not schematic.is_file():
                raise FileNotFoundError(f"Install kicad-demos: missing {schematic}")
            exported = Path(scratch) / f"{directory}.net"
            cmd = [cli, "sch", "export", "netlist", "--format", "kicadsexpr",
                   "--output", str(exported), str(schematic)]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if p.returncode != 0 or not exported.exists():
                raise RuntimeError(f"{directory}: KiCad export failed: {p.stderr[-500:]}")
            netbytes = exported.read_bytes()
            source = parse_kicad_netlist(netbytes.decode("utf-8"))
            converted = recover_connected_source_circuit_json(netbytes.decode("utf-8"))
            ir = circuit_json_to_netlist(converted["documents"])
            receipt = converted["receipt"]
            actual = (
                receipt["components"], receipt["source_nets"],
                receipt["source_pin_memberships"],
                receipt["connected_multi_pin_nets"],
                receipt["imported_multi_pin_memberships"],
                receipt["hierarchy"]["sheet_count"],
                len(receipt["source_unnumbered_no_connect_nets"]),
            )
            if actual != expected:
                raise AssertionError(f"{directory}: expected {expected}, got {actual}")
            if not receipt["topology_exact_multi_pin_match"] or not receipt["hierarchy"]["source_sheet_scopes_preserved"]:
                raise AssertionError(f"{directory}: topology or sheet instance scope lost")
            if {i.ref for i in ir.components} != {i.ref for i in source.components}:
                raise AssertionError(f"{directory}: component identities changed")
            response = client.post("/v1/interchange/circuit-json/inspect",
                json={"documents": converted["documents"], "source_label": directory})
            review = response.json()
            if response.status_code != 200 or review.get("compilable") is not True or review["summary"]["net_count"] != expected[3]:
                raise AssertionError(f"{directory}: source interchange API did not retain expected net connectivity")
            output[directory] = {
                "source_file": f"kicad-demos/{directory}/{schematic_name}",
                "schematic_sha256": hashlib.sha256(schematic.read_bytes()).hexdigest(),
                "export_sha256": hashlib.sha256(netbytes).hexdigest(),
                "source_components": actual[0],
                "source_nets": actual[1],
                "source_numbered_pin_memberships": actual[2],
                "connected_multi_pin_nets": actual[3],
                "imported_connected_pin_memberships": actual[4],
                "instanced_sheets": actual[5],
                "unnumbered_disconnected_contacts": actual[6],
                "interchange_endpoint_http": response.status_code,
                "interchange_endpoint_status": review.get("status"),
                "interchange_only_compilable": review.get("compilable"),
                "source_topology_exact_match": True,
                "sheet_instance_identity_preserved": True,
                "physical_build_authorized": False,
            }
    return {
        "benchmark": "hs_kicad_hierarchy_official_demos_20261024",
        "source": "KiCad 9 official kicad-demos installed from OS package",
        "KiCad_CLI_version": subprocess.run([cli,"version"],capture_output=True,text=True).stdout.strip(),
        "projects": output,
        "project_count": len(output),
        "external_converter_geometry_reconciled": False,
        "source_interchange_only": True,
        "fabrication_authorized": False,
        "physical_repair_verified": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-root",type=Path,default=Path("/usr/share/kicad/demos"))
    parser.add_argument("--out",type=Path)
    args = parser.parse_args()
    report = run(args.demo_root)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
