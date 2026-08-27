#!/usr/bin/env python3
"""Lower the frozen safe electronics proposal through HS and independent KiCad CLI checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if sys.path and str(Path(sys.path[0]).resolve()) == _SCRIPT_DIR:
    sys.path.pop(0)

from hardware_splicer.electronics_foundation_benchmark import (
    load_electronics_bundle,
    strict_signal_voltage_audit,
    translated_hcsr04_contract_audit,
    validate_catalog_identity_and_pins,
)
from hardware_splicer.netlist import CircuitNetlist, run_erc
from hardware_splicer.netlist.compile import compile_netlist_to_artifacts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal-bundle", default="experiments/electronics/esp32_hcsr04_level_shift_gpt56_sol.json")
    parser.add_argument("--out-dir", default="artifacts/electronics-kicad-probe")
    args = parser.parse_args()

    bundle = load_electronics_bundle(args.proposal_bundle)
    netlist = CircuitNetlist.from_dict(bundle["translated_design"])
    identity = validate_catalog_identity_and_pins(netlist)
    hs_erc = run_erc(netlist)
    strict = strict_signal_voltage_audit(netlist)
    topology = translated_hcsr04_contract_audit(netlist)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    compiled = compile_netlist_to_artifacts(
        netlist,
        "esp32_hcsr04_level_shift_probe",
        out,
        notes=[
            "External GPT-5.6 Sol module-level proposal; physical authority remains closed.",
            "This probe evaluates lowering and tool acceptance, not fabrication readiness.",
        ],
    )
    quality = dict(compiled.get("quality") or {})
    paths = dict(compiled.get("paths") or {})
    sch_erc = dict(compiled.get("sch_erc") or {})

    pcb_path = Path(str(paths.get("kicad_pcb") or paths.get("pcb") or ""))
    sch_path = Path(str(paths.get("kicad_sch") or ""))
    kicad_drc_ready = bool(quality.get("kicad_drc_ready")) and not bool(quality.get("kicad_drc_skipped"))
    kicad_erc_ready = not bool(sch_erc.get("skipped"))

    execution_checks = {
        "catalog_identity_pass": identity["pass"],
        "hs_erc_pass": bool(hs_erc.get("pass")),
        "strict_signal_audit_pass": strict["pass"],
        "translator_topology_pass": topology["pass"],
        "kicad_schematic_emitted": sch_path.is_file(),
        "kicad_pcb_emitted": pcb_path.is_file(),
        "kicad_cli_schematic_probe_executed": kicad_erc_ready,
        "kicad_cli_pcb_drc_executed": kicad_drc_ready,
        "physical_authority_closed": True,
    }
    diagnostic_pass = all(execution_checks.values())

    schematic_status = (
        "erc_clean" if sch_erc.get("pass") is True
        else "erc_violations" if kicad_erc_ready
        else "tool_or_format_unavailable"
    )
    pcb_status = (
        "drc_clean" if quality.get("kicad_drc_pass") is True
        else "drc_violations" if kicad_drc_ready
        else "tool_or_format_unavailable"
    )

    report = {
        "schema_version": "hardware_splicer.electronics_kicad_probe.v1",
        "benchmark": "esp32_hcsr04_level_shift_kicad_lowering",
        "diagnostic_pass": diagnostic_pass,
        "execution_checks": execution_checks,
        "electrical_truth": {
            "identity": identity,
            "hs_erc": hs_erc,
            "strict_signal_audit": strict,
            "translator_contract": topology,
        },
        "lowering": {
            "compile_ok": bool(compiled.get("ok")),
            "paths": paths,
            "quality": quality,
            "kicad_schematic_erc": sch_erc,
            "schematic_status": schematic_status,
            "pcb_status": pcb_status,
        },
        "interpretation": {
            "schematic_pin_fidelity_known_gap": True,
            "schematic_pin_fidelity_reason": "Current generic schematic exporter collapses module connectivity to generic block pins; KiCad ERC outcome is therefore a structural/lowering probe, not yet independent proof of the original per-pin netlist.",
            "pcb_copper_authority": "preview_only_not_fabrication_routing",
            "translator_internal_electrical_behavior_verified": False,
            "fabrication_ready": False,
            "power_on_ready": False,
            "authority_effect": "none",
        },
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "release_authorized": False,
    }
    report_path = out / "ELECTRONICS_KICAD_PROBE.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "benchmark=esp32_hcsr04_level_shift_kicad_lowering",
        f"diagnostic_pass={diagnostic_pass}",
        f"compile_ok={bool(compiled.get('ok'))}",
        f"schematic_status={schematic_status}",
        f"kicad_erc_pass={sch_erc.get('pass')}",
        f"kicad_erc_errors={sch_erc.get('errors')}",
        f"kicad_erc_warnings={sch_erc.get('warnings')}",
        f"pcb_status={pcb_status}",
        f"kicad_drc_pass={quality.get('kicad_drc_pass')}",
        f"kicad_drc_errors={quality.get('kicad_drc_errors')}",
        f"kicad_drc_warnings={quality.get('kicad_drc_warnings')}",
        f"kicad_version={quality.get('kicad_version') or sch_erc.get('kicad_version')}",
        "fabrication_authorized=False",
        "power_on_authorized=False",
    ]
    lines.extend(f"check.{key}={bool(value)}" for key, value in execution_checks.items())
    (out / "ELECTRONICS_KICAD_SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print((out / "ELECTRONICS_KICAD_SUMMARY.txt").read_text(encoding="utf-8"), end="")
    return 0 if diagnostic_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
