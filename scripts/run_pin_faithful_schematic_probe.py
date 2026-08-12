#!/usr/bin/env python3
"""Prove that catalog pin identities/types survive into KiCad ERC."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if sys.path and str(Path(sys.path[0]).resolve()) == _SCRIPT_DIR:
    sys.path.pop(0)

from hardware_splicer.electronics_foundation_benchmark import load_electronics_bundle
from hardware_splicer.integrations.schematic_export import write_schematic_for_netlist
from hardware_splicer.netlist import CircuitNetlist
from hardware_splicer.pcb.kicad_cli_erc import run_kicad_cli_erc


def _output_conflict_netlist() -> CircuitNetlist:
    return CircuitNetlist.from_dict(
        {
            "schema_version": "hardware_splicer.netlist.v1",
            "source": "pin_faithful_erc_adversarial_output_conflict",
            "components": [
                {"ref": "J1", "value": "5V source", "footprint": "usb-power-5v", "module_id": "usb-power-5v", "metadata": {}},
                {"ref": "S1", "value": "HC-SR04 A", "footprint": "hc-sr04", "module_id": "hc-sr04", "metadata": {}},
                {"ref": "S2", "value": "HC-SR04 B", "footprint": "hc-sr04", "module_id": "hc-sr04", "metadata": {}},
            ],
            "nets": [
                {"name": "+5V", "pins": [
                    {"component_ref": "J1", "pin": "V+"},
                    {"component_ref": "S1", "pin": "VCC"},
                    {"component_ref": "S2", "pin": "VCC"}
                ]},
                {"name": "GND", "pins": [
                    {"component_ref": "J1", "pin": "GND"},
                    {"component_ref": "S1", "pin": "GND"},
                    {"component_ref": "S2", "pin": "GND"}
                ]},
                {"name": "ECHO_OUTPUT_CONFLICT", "pins": [
                    {"component_ref": "S1", "pin": "ECHO"},
                    {"component_ref": "S2", "pin": "ECHO"}
                ]}
            ],
            "metadata": {"authority_effect": "none"},
        }
    )


def _violation_mentions(violation: Mapping[str, Any], *fragments: str) -> bool:
    descriptions = " ".join(
        str(item.get("description") or "")
        for item in (violation.get("items") or [])
        if isinstance(item, Mapping)
    )
    return all(fragment in descriptions for fragment in fragments)


def _echo_output_conflict_visible(violations: list[Mapping[str, Any]]) -> bool:
    return any(
        str(violation.get("type") or "") == "pin_to_pin"
        and _violation_mentions(violation, "S1 Pin ECHO", "S2 Pin ECHO")
        for violation in violations
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", default="experiments/electronics/esp32_hcsr04_level_shift_gpt56_sol.json")
    parser.add_argument("--out-dir", default="artifacts/pin-faithful-schematic")
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bundle = load_electronics_bundle(args.bundle)
    safe = CircuitNetlist.from_dict(bundle["translated_design"])
    conflict = _output_conflict_netlist()

    safe_path = out / "safe_level_shifted.kicad_sch"
    conflict_path = out / "output_conflict.kicad_sch"
    write_schematic_for_netlist(safe, safe_path, title="HS safe level-shifted module schematic")
    write_schematic_for_netlist(conflict, conflict_path, title="HS adversarial output-output schematic")

    safe_erc = run_kicad_cli_erc(safe_path, out_dir=out / "safe_erc")
    conflict_erc = run_kicad_cli_erc(conflict_path, out_dir=out / "conflict_erc")
    conflict_violations = list(conflict_erc.get("violations") or [])

    checks = {
        "safe_schematic_kicad_erc_executed": not bool(safe_erc.get("skipped")),
        "conflict_schematic_kicad_erc_executed": not bool(conflict_erc.get("skipped")),
        "output_output_conflict_is_visible_to_kicad": _echo_output_conflict_visible(conflict_violations),
        "generated_schematic_contains_real_echo_pin": '(pin "ECHO"' in conflict_path.read_text(encoding="utf-8"),
        "physical_authority_closed": True,
    }
    diagnostic_pass = all(checks.values())
    report = {
        "schema_version": "hardware_splicer.pin_faithful_schematic_probe.v1",
        "benchmark": "catalog_pin_identity_to_kicad_erc",
        "diagnostic_pass": diagnostic_pass,
        "checks": checks,
        "safe": {"path": str(safe_path), "erc": safe_erc},
        "output_conflict": {"path": str(conflict_path), "erc": conflict_erc},
        "interpretation": {
            "numeric_voltage_domain_truth_still_owned_by_hs_contracts": True,
            "kicad_erc_role": "independent electrical-pin-type and schematic-connectivity referee",
            "fabrication_ready": False,
            "authority_effect": "none",
        },
        "fabrication_authorized": False,
        "power_on_authorized": False,
    }
    (out / "PIN_FAITHFUL_SCHEMATIC_PROBE.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "benchmark=catalog_pin_identity_to_kicad_erc",
        f"diagnostic_pass={diagnostic_pass}",
        f"safe_erc_pass={safe_erc.get('pass')}",
        f"safe_erc_errors={safe_erc.get('errors')}",
        f"safe_erc_warnings={safe_erc.get('warnings')}",
        f"safe_erc_violations={len(list(safe_erc.get('violations') or []))}",
        f"conflict_erc_pass={conflict_erc.get('pass')}",
        f"conflict_erc_errors={conflict_erc.get('errors')}",
        f"conflict_erc_warnings={conflict_erc.get('warnings')}",
        f"conflict_erc_violations={len(conflict_violations)}",
    ]
    lines.extend(f"check.{key}={bool(value)}" for key, value in checks.items())
    (out / "PIN_FAITHFUL_SCHEMATIC_SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print((out / "PIN_FAITHFUL_SCHEMATIC_SUMMARY.txt").read_text(encoding="utf-8"), end="")
    return 0 if diagnostic_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
