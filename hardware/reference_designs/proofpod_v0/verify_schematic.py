#!/usr/bin/env python3
"""Fail-closed schematic gate for ProofPod v0 / Product Factory PF-001."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCHEMATIC = HERE / "proofpod_v0.kicad_sch"
MANIFEST = HERE / "architecture_manifest.json"
OUTPUT = HERE / "schematic_verification.json"

GEN_SPEC = importlib.util.spec_from_file_location("proofpod_generator_contract", HERE / "generate_schematic.py")
GEN = importlib.util.module_from_spec(GEN_SPEC)
GEN_SPEC.loader.exec_module(GEN)

REQUIRED = {
    ("U8", "1"): "TARGET_SOURCE",
    ("U8", "2"): "GND",
    ("U8", "3"): "TARGET_POWER_EN",
    ("U8", "4"): "TARGET_FAULT_N",
    ("U8", "5"): "ILIM_SET",
    ("U8", "6"): "TARGET_SWITCHED",
    ("R5", "1"): "ILIM_SET",
    ("R5", "2"): "GND",
    ("R6", "1"): "TARGET_SWITCHED",
    ("R6", "2"): "VTARGET",
    ("U5", "1"): "TARGET_SWITCHED",
    ("U5", "2"): "VTARGET",
    ("U3", "8"): "SPI_OE",
    ("U3", "14"): "VTARGET",
    ("R7", "1"): "SPI_OE",
    ("R7", "2"): "GND",
    ("R14", "1"): "TARGET_POWER_EN",
    ("R14", "2"): "GND",
    ("SW1", "1"): "1V8",
    ("SW1", "2"): "TARGET_SOURCE",
    ("SW1", "3"): "3V3",
    ("SW2", "1"): "3V3",
    ("SW2", "2"): "WRITE_ARM",
    ("R13", "1"): "WRITE_ARM",
    ("R13", "2"): "GND",
    ("U4", "2"): "3V3",
    ("U4", "7"): "VTARGET",
    ("J2", "1"): "VTARGET",
    ("J2", "2"): "GND",
}


def fail(message: str) -> None:
    raise SystemExit(f"ProofPod schematic gate failed: {message}")


def run(*args: str, allowed: tuple[int, ...] = (0,)) -> str:
    environment = dict(os.environ)
    environment.setdefault("KICAD_ENABLE_WXTRACE", "1")
    environment.setdefault("WXTRACE", "KICAD_SCH_PLUGIN")
    environment.setdefault("KICAD_TRACE", "all")
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, env=environment)
    if result.returncode not in allowed:
        fail(f"command exit {result.returncode}: {' '.join(args)}\n{result.stdout}")
    return result.stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component_map(root: ET.Element) -> dict[str, ET.Element]:
    components = root.findall("./components/comp")
    mapped = {item.attrib["ref"]: item for item in components}
    if len(mapped) != len(components):
        fail("duplicate schematic references")
    return mapped


def actual_pin_nets(root: ET.Element) -> dict[tuple[str, str], str]:
    actual: dict[tuple[str, str], str] = {}
    for net in root.findall("./nets/net"):
        name = net.attrib["name"].lstrip("/")
        for node in net.findall("node"):
            key = (node.attrib["ref"], node.attrib["pin"])
            if key in actual:
                fail(f"duplicate net assignment: {key}")
            actual[key] = name
    return actual


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if manifest["authority"]["fabrication_ready"] is not False:
        fail("fabrication authority opened before schematic proof")
    if manifest["authority"]["physical_correctness"] != "UNPROVEN":
        fail("physical correctness boundary changed")
    if manifest["target_power_contract"]["datasheet_max_current_limit_ma_at_1pct_resistor_approx"] >= 250:
        fail("current-limit contract no longer leaves headroom below 250 mA")
    if not SCHEMATIC.exists():
        fail("generated schematic missing")

    with tempfile.TemporaryDirectory(prefix="proofpod-verify-") as temporary:
        root_dir = Path(temporary)
        netlist = root_dir / "netlist.xml"
        erc = root_dir / "erc.json"

        run("kicad-cli", "sch", "export", "netlist", str(SCHEMATIC), "--format", "kicadxml", "-o", str(netlist))
        root = ET.parse(netlist).getroot()
        components = component_map(root)
        actual = actual_pin_nets(root)

        # Verify the complete generator pin/net contract, not only a safety subset.
        # This catches geometric wire/label accidents that can silently merge rails.
        expected_pin_nets = {
            (reference, pin): net
            for reference, pins in GEN.PIN_NETS.items()
            if not reference.startswith("#FLG")
            for pin, net in pins.items()
        }
        for key, expected in expected_pin_nets.items():
            if actual.get(key) != expected:
                if key[0] == "J1":
                    j1_actual = {
                        pin: actual.get(("J1", pin))
                        for pin in sorted(GEN.PIN_NETS["J1"])
                    }
                    fail(
                        f"pin/net contract violated: {key[0]}.{key[1]} expected {expected}, "
                        f"got {actual.get(key)}; resolved J1 nets={j1_actual}"
                    )
                fail(f"pin/net contract violated: {key[0]}.{key[1]} expected {expected}, got {actual.get(key)}")

        for key, expected in REQUIRED.items():
            if actual.get(key) != expected:
                fail(f"required topology violated: {key[0]}.{key[1]} expected {expected}, got {actual.get(key)}")

        values = {ref: comp.findtext("value") for ref, comp in components.items()}
        expected_values = {
            "U1": "RP2040",
            "U3": "TXU0304PWR",
            "U4": "PCA9306DCTR",
            "U5": "INA219AIDCNR",
            "U8": "TPS2553DBVR",
            "R5": "133k",
            "R6": "0.1R 1%",
            "R7": "10k",
            "R13": "100k",
            "R14": "100k",
        }
        for ref, expected in expected_values.items():
            if values.get(ref) != expected:
                fail(f"component identity drift: {ref} expected {expected}, got {values.get(ref)}")

        stdout = run(
            "kicad-cli", "sch", "erc", str(SCHEMATIC), "-o", str(erc),
            "--format", "json", "--severity-all", "--exit-code-violations",
            allowed=(0, 5),
        )
        report = json.loads(erc.read_text())
        if report.get("$schema") != "https://schemas.kicad.org/erc.v1.json":
            fail("unsupported KiCad ERC schema")
        sheets = report.get("sheets")
        if not isinstance(sheets, list) or len(sheets) != 1:
            fail("expected exactly one ERC sheet")
        violations = sheets[0].get("violations")
        if not isinstance(violations, list):
            fail("ERC violations array missing")
        if violations:
            fail(f"ERC not clean ({len(violations)} violations): {violations[:5]}")

        receipt = {
            "schema": "hardware_splicer.product_factory.schematic_verification.v1",
            "run_id": "PF-001",
            "product_id": "proofpod-v0",
            "result": "PASS",
            "checks": {
                "complete_pin_net_contract_issues": 0,
                "required_topology_issues": 0,
                "component_identity_issues": 0,
                "erc_violations": 0,
                "current_limit_contract_below_250ma": True,
            },
            "toolchain": {"kicad_cli": run("kicad-cli", "--version").strip()},
            "artifact_sha256": {
                "schematic": sha256(SCHEMATIC),
                "generator": sha256(HERE / "generate_schematic.py"),
                "architecture_manifest": sha256(MANIFEST),
                "local_symbol_library": sha256(HERE / "HardwareSplicer.kicad_sym"),
            },
            "authority": {
                "schematic_candidate_verified": True,
                "pcb_complete": False,
                "fabrication_ready": False,
                "power_on_ready": False,
                "physical_correctness": "UNPROVEN",
                "commercial_superiority": "UNPROVEN",
            },
            "nonclaims": [
                "Clean ERC and required-net checks do not establish PCB correctness.",
                "External-target reverse behavior remains subject to independent EE review.",
                "USB-C connector, crystal loading, ESD protection and layout are not closed by this receipt.",
                "This receipt authorizes continued design work only.",
            ],
            "erc_stdout": stdout.strip(),
        }
        OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
