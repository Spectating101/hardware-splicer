"""Build Challenge 001: generate a reviewable, electrical-topology candidate.

This is a design *proposal*, not a complete KiCad schematic or PCB.
Nominal topology is the fixed-5V LM2596 regulator from TI datasheet SNVS124G.
Values/part choices are subject to datasheet sizing, derating and bench review.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

DATASHEET = "https://www.ti.com/lit/ds/symlink/lm2596.pdf"
PART = "LM2596S-5.0/NOPB"

def generate_candidate(output: Path) -> dict:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    topology = {
        "schema_version": "hardware_splicer.design_candidate.v1",
        "candidate": "hs_build_challenge_001_lm2596_fixed5",
        "origin": "hs_generated_topology_proposal",
        "reference_basis": DATASHEET,
        "reference_design_reused": False,
        "target": {"input_nominal_v": 24, "output_v": 5, "load_max_a": 0.5,
                   "source": "isolated current-limited bench supply"},
        "components": [
            {"ref": "U1", "mpn": PART, "role": "fixed 5V buck regulator",
             "pins": {"1": "VIN", "2": "SW", "3": "GND", "4": "VOUT", "5": "GND"}},
            {"ref": "D1", "mpn": None, "role": "catch Schottky diode, ratings TBD"},
            {"ref": "L1", "mpn": None, "role": "output inductor, saturation/ripple/thermal TBD"},
            {"ref": "C1", "mpn": None, "role": "input capacitor, ESR/ripple/voltage TBD"},
            {"ref": "C2", "mpn": None, "role": "output capacitor, ESR/ripple/voltage TBD"},
            {"ref": "J1", "mpn": None, "role": "input connector"},
            {"ref": "J2", "mpn": None, "role": "output connector"},
        ],
        "nets": {
            "VIN": ["J1.1", "U1.1", "C1.+"],
            "SW": ["U1.2", "L1.1", "D1.K"],
            "VOUT": ["L1.2", "C2.+", "J2.1", "U1.4"],
            "GND": ["J1.2", "J2.2", "U1.3", "U1.5", "C1.-", "C2.-", "D1.A"],
        },
        "blockers": [
            "Exact manufacturer diode/inductor/capacitor ratings and footprints unresolved",
            "Native KiCad schematic not generated",
            "No routed PCB, ERC/DRC, verified SPICE model or physical measurements",
            "Electrical startup, feedback topology, protection and thermals not independently approved",
        ],
        "fabrication_authorized": False,
        "physical_design_verified": False,
    }
    payload = json.dumps(topology, indent=2) + "\n"
    (output / "design_candidate.json").write_text(payload)
    return {"path": str(output / "design_candidate.json"),
            "sha256": hashlib.sha256(payload.encode()).hexdigest(),
            "fabrication_authorized": False, "completeness": "topology_only"}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate_candidate(args.out), indent=2))
