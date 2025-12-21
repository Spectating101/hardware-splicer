#!/usr/bin/env python3
"""
Convert a design_assistant netlist JSON into a minimal KiCad-compatible netlist XML.
This is a scaffold for fast handoff to EDA; it uses best-effort pin inference.

Usage:
  python scripts/netlist_to_kicad.py --input design.netlist.json --output design.kicad_netlist.xml

Netlist JSON format (from design_assistant):
{
  "components": [{"ref": "U1", "type": "USB-C PD Controller", "value": "STM32G0B1", "notes": "..."}],
  "nets": [{"name": "VUSB", "nodes": ["U1.VIN", "Q1.IN"]}]
}
"""
import argparse
import json
import os
import sys
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring


def infer_ref_pin(node: str):
    """
    Split a node string into (ref, pin). Accepts "U1.VIN" or "U1".
    If no pin is provided, uses "1" as a placeholder.
    """
    if "." in node:
        ref, pin = node.split(".", 1)
        return ref.strip(), pin.strip() or "1"
    return node.strip(), "1"


def to_kicad_netlist(data: dict) -> str:
    export = Element("export")
    comps_el = SubElement(export, "components")
    # Build components
    for comp in data.get("components", []):
        comp_el = SubElement(comps_el, "comp", {"ref": comp.get("ref", "X?")})
        SubElement(comp_el, "value").text = comp.get("value") or comp.get("type") or "VALUE"
        SubElement(comp_el, "footprint").text = comp.get("footprint", "TO_BE_DEFINED")
        if comp.get("notes"):
            SubElement(comp_el, "fields").text = comp["notes"]

    nets_el = SubElement(export, "nets")
    code = 1
    for net in data.get("nets", []):
        net_el = SubElement(nets_el, "net", {"code": str(code), "name": net.get("name", f"Net-{code}")})
        code += 1
        for node in net.get("nodes", []):
            ref, pin = infer_ref_pin(node)
            SubElement(net_el, "node", {"ref": ref, "pin": pin})
    # Pretty-print
    return tostring(export, encoding="unicode")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to design_assistant netlist JSON")
    ap.add_argument("--output", required=True, help="Path to write KiCad netlist XML")
    args = ap.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        raise SystemExit(f"Input netlist not found: {inp}")
    data = json.loads(inp.read_text())
    xml_str = to_kicad_netlist(data)
    Path(args.output).write_text(xml_str)
    print(f"Wrote KiCad netlist -> {args.output}")


if __name__ == "__main__":
    main()
