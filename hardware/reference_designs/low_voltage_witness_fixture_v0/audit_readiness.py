#!/usr/bin/env python3
"""Independent, non-physical witness metrology and operating-envelope audit.

This audit deliberately does not modify the existing HS verification, frozen
Policy Lab receiver, source schematic or PCB. It tests failure discrimination
using declared TEST_FIXTURE samples and a source-verified low-voltage DC model.
It can *withhold* claims; it cannot authorize assembly, purchase or power-on.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
from datetime import datetime, timedelta

from measurement_screen import (ScreeningError, conservative_load_power_bound,
                                screen as strict_fixture_screen)

HERE = Path(__file__).resolve().parent
R_SERIES = 0.05 + 0.015 + 0.010  # original stated SPICE assumption, NOT measured
FUSE_CANDIDATE_A = 1.0
SOURCE_CURRENT_LIMIT_A = 0.65
POWER_ENVELOPE_W = 2.5


def hashfile(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def corner_arithmetic(volts: float, load_ohms: float) -> dict:
    current = volts / (load_ohms + R_SERIES)
    return {
        "input_voltage_v": volts,
        "assumed_load_ohms": load_ohms,
        "current_a": current,
        "load_power_w": current ** 2 * load_ohms,
        "input_power_w": volts * current,
        "source_limit_engaged_in_ideal_model": current > SOURCE_CURRENT_LIMIT_A,
        "declared_load_power_limit_exceeded": current ** 2 * load_ohms > POWER_ENVELOPE_W,
    }


def corner_spice(volts: float, load_ohms: float) -> dict:
    """Run independent ngspice with the *same declared* fixed resistances."""
    circuit = (
        "Independent low-voltage parameter corner, SIMULATION ONLY\n"
        f"V_SRC plus 0 DC {volts:.9g}\n"
        "R_FUSE plus fused 0.05\n"
        "R_ADA fused between 0.015\n"
        "R_REF between load 0.010\n"
        f"R_LOAD load 0 {load_ohms:.9g}\n"
        ".control\n"
        "set noaskquit\n"
        "op\n"
        "print v(load) i(v_src)\n"
        "quit\n"
        ".endc\n"
        ".end\n"
    )
    result = subprocess.run(
        ["ngspice", "-b"], input=circuit, text=True, capture_output=True, timeout=12
    )
    if result.returncode:
        raise RuntimeError(f"ngspice corner failed: {result.stderr[-250:]}")
    def parse(name):
        found = re.search(r"(?m)^" + re.escape(name) + r"\s*=\s*([-+0-9.eE]+)", result.stdout)
        if found is None:
            raise RuntimeError(f"missing SPICE field: {name}")
        return float(found.group(1))
    measured_current = -parse("i(v_src)")
    output_v = parse("v(load)")
    return {
        "current_a": measured_current,
        "load_voltage_v": output_v,
        "load_power_w": output_v * measured_current,
        "simulation_only": True,
    }


def dmm_shunt_uncertainty_example(
    shunt_voltage_v: float = 0.005,
    instrument_range_v: float = 0.2,
    reading_accuracy_pct: float = 0.015,
    range_accuracy_pct: float = 0.004,
    uncalibrated_shunt_tolerance_pct: float = 1.0,
) -> dict:
    """Manufacturer-range illustrative bound, not a calibrated uncertainty budget."""
    spec_abs_v = (
        reading_accuracy_pct / 100 * shunt_voltage_v
        + range_accuracy_pct / 100 * instrument_range_v
    )
    return {
        "candidate": "Siglent SDM3055 in 200mV DCV range (NOT selected/purchased)",
        "nominal_shunt_voltage_mV": shunt_voltage_v * 1000,
        "nominal_reference_current_a": shunt_voltage_v / .01,
        "manufacturer_dmm_voltage_error_uV": spec_abs_v * 1e6,
        "dmm_error_pct_of_5mV": spec_abs_v / shunt_voltage_v * 100,
        "shunt_uncharacterized_tolerance_pct": uncalibrated_shunt_tolerance_pct,
        "simple_worst_case_pct_at_nominal": spec_abs_v / shunt_voltage_v * 100 + uncalibrated_shunt_tolerance_pct,
        "not_included": [
            "actual DMM calibration state",
            "thermal EMF, lead offsets, resistor temperature, sensor timing",
            "separate 5 V reference voltage channel with synchronized logging",
            "input common-mode/grounding/earthing confirmation and operator procedure",
        ],
        "basis_url": "https://www.siglent.com/in/products-overview/sdm3055/",
        "numeric_range_basis": "SDM3055 manufacturer datasheet 200mV DCV accuracy: ±(0.015% of reading + 0.004% of range), conditional on calibration/warm-up",
        "status": "INSTRUMENT_CANDIDATE_NOT_CALIBRATION",
    }


def rewrite_csv(source: Path, target: Path, *, increase_shunt=0.0, shift_reference_s=0.0, drop_index=None, increase_primary=0.0):
    rows = list(csv.DictReader(io.StringIO(source.read_text(encoding="utf8"))))
    if not rows:
        raise ValueError("No input rows")
    for row in rows:
        if "shunt_voltage_v" in row and increase_shunt:
            row["shunt_voltage_v"] = f"{float(row['shunt_voltage_v']) * (1+increase_shunt):.11f}"
        if "current_a" in row and increase_primary:
            row["current_a"] = f"{float(row['current_a']) * (1+increase_primary):.12f}"
        if shift_reference_s:
            t = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
            t += timedelta(seconds=shift_reference_s)
            row["timestamp_utc"] = t.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if drop_index is not None:
        rows = [r for i,r in enumerate(rows) if i != drop_index]
    with target.open("w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_capture_scenarios(pl_root: Path, prior_run: Path, out: Path) -> list[dict]:
    converter = pl_root / "scripts/equipment/dc_bench_capture.mjs"
    primary = prior_run / "primary/samples.csv"
    reference = prior_run / "reference-fixture.csv"
    config = prior_run / "capture-config.json"
    sidecar = prior_run / "primary/session.json"
    registers = prior_run / "primary/registers.jsonl"
    for f in (converter, primary, reference, config, sidecar, registers):
        if not f.is_file():
            raise FileNotFoundError(str(f))
    paths = {
        "control": {},
        "reference_one_percent_high": {"increase_shunt": .01},
        "reference_five_percent_high": {"increase_shunt": .05},
        "reference_ten_percent_high": {"increase_shunt": .10},
        "reference_time_plus_500ms": {"shift_reference_s": .5},
        "missing_reference_sample": {"drop_index": 77},
        "primary_tampered_against_original_session": {"increase_primary": .05}
    }
    records = []
    for name, mutations in paths.items():
        target = out / "capture_trials" / name
        target.mkdir(parents=True, exist_ok=False)
        ref_path = target / "reference.csv"
        primary_path = primary
        if "increase_primary" in mutations:
            ref_path.write_bytes(reference.read_bytes())
            primary_path = target / "primary.csv"
            rewrite_csv(primary, primary_path, increase_primary=mutations["increase_primary"])
        else:
            rewrite_csv(reference, ref_path, **mutations)
        trial = subprocess.run([
            "node", str(converter),
            "--primary", str(primary_path),
            "--reference", str(ref_path),
            "--config", str(config),
            "--primary-sidecar", str(sidecar),
            "--primary-registers", str(registers),
            "--out", str(target / "policy-lab-intake")],
            cwd=pl_root, capture_output=True, text=True, timeout=40
        )
        # Second, deliberately stricter screen: no physical calibration or
        # independent reference custody may be inferred from its success.
        try:
            strict = strict_fixture_screen(primary_path, ref_path, sidecar, registers)
            strict_decision = strict["decision"]
            strict_energy_pct = strict["energy_disagreement_primary_denominator_pct"]
            strict_error = None
        except (ScreeningError, OSError) as exc:
            strict_decision, strict_energy_pct, strict_error = "INVALID_INPUT_HOLD", None, str(exc)
        record = {
            "strict_screen_decision": strict_decision,
            "strict_screen_disagreement_pct": strict_energy_pct,
            "strict_screen_error": strict_error,
            "name": name, "mutation": mutations, "converter_exit": trial.returncode,
            "error": trial.stderr.strip()[-400:],
            "reference_input_sha256": hashfile(ref_path),
            "test_fixture_only": True
        }
        if trial.returncode == 0:
            receipt = json.loads((target / "policy-lab-intake/intake-receipt.json").read_text())
            row = receipt["channel_diagnostics"]["source_dc"]
            record.update({
                "decision": receipt["decision"],
                "physical_ready": receipt["physical_ready"],
                "reported_disagreement_windows": row["diagnostic_disagreement_windows"],
                "primary_total_wh": row["primary_total_wh"],
                "reference_total_wh": row["reference_total_wh"],
                "abs_percent_reference_larger_denominator":
                    100 * abs(row["reference_total_wh"] - row["primary_total_wh"]) /
                    max(row["reference_total_wh"], row["primary_total_wh"]),
                "warnings": receipt["diagnostic_warnings"]
            })
        records.append(record)
    return records


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pl-root", required=True, type=Path)
    parser.add_argument("--native-replay", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--fail-if-held", action="store_true", help="Use exit 2 when audit finds a HOLD; does not certify future hardware")
    args = parser.parse_args(argv)
    dest = args.out.expanduser().resolve()
    if dest.exists():
        parser.error("output directory already exists")
    dest.mkdir(parents=True)
    spec = json.loads((HERE/"station-spec-5v.json").read_text())
    baseline = json.loads((args.native_replay/"verification.json").read_text())
    if baseline["status"] != "SOFTWARE_DESIGN_VALIDATED_ONLY":
        raise ValueError("Only a software-design source can enter this audit")
    if spec["maximum_power_w"] != POWER_ENVELOPE_W:
        raise ValueError("Audit constants must be reviewed when station spec changes")
    corners = []
    for volts, load in ((5.0, 10.0), (5.25, 10.0), (5.0, 9.5), (5.25, 9.5)):
        arith = corner_arithmetic(volts, load)
        spice = corner_spice(volts, load)
        arith["ngspice"] = spice
        arith["spice_matches_arithmetic"] = (
            math.isclose(arith["current_a"], spice["current_a"], rel_tol=2e-6)
            and math.isclose(arith["load_power_w"], spice["load_power_w"], rel_tol=2e-6)
        )
        if not arith["spice_matches_arithmetic"]:
            raise AssertionError("Corner SPICE and independent arithmetic disagree")
        corners.append(arith)
    cases = test_capture_scenarios(args.pl_root.resolve(), args.native_replay.resolve(), dest)
    by_name = {c["name"]: c for c in cases}
    controls = {
        "original_native_KiCad_ERC_DRC_pass": baseline["native_erc"] == "ZERO_VIOLATIONS" and baseline["native_drc"].startswith("ZERO_VIOLATIONS"),
        "all_corner_SPICE_checks_reproduced": all(x["spice_matches_arithmetic"] for x in corners),
        "nominal_power_within_2_5W": not corners[0]["declared_load_power_limit_exceeded"],
        "source_5_25V_power_envelope_violation_detected": corners[1]["declared_load_power_limit_exceeded"],
        "source_5_25V_minus5pct_load_violation_detected": corners[3]["declared_load_power_limit_exceeded"],
        "reference_5pct_bias_not_reported_as_failing_intake": by_name["reference_five_percent_high"]["converter_exit"] == 0 and by_name["reference_five_percent_high"]["reported_disagreement_windows"] == 0,
        "reference_10pct_bias_warning_present": by_name["reference_ten_percent_high"]["converter_exit"] == 0 and by_name["reference_ten_percent_high"]["reported_disagreement_windows"] > 0,
        "clock_500ms_offset_not_independently_proven": by_name["reference_time_plus_500ms"]["converter_exit"] == 0,
        "missing_reference_samples_blocked": by_name["missing_reference_sample"]["converter_exit"] != 0,
        "tampered_primary_against_sidecar_blocked": by_name["primary_tampered_against_original_session"]["converter_exit"] != 0,
        "all_captures_remain_nonphysical": all(c.get("physical_ready") is False for c in cases if c["converter_exit"] == 0),
        "strict_control_fixture_passes_without_physical_claim": by_name["control"]["strict_screen_decision"] == "PASS_FIXTURE_DISCRIMINATION_ONLY",
        "strict_screen_detects_1pct_reference_bias": by_name["reference_one_percent_high"]["strict_screen_decision"] == "FAIL_FIXTURE_DISAGREEMENT",
        "strict_screen_detects_5pct_reference_bias": by_name["reference_five_percent_high"]["strict_screen_decision"] == "FAIL_FIXTURE_DISAGREEMENT",
        "strict_screen_detects_reference_clock_shift": by_name["reference_time_plus_500ms"]["strict_screen_decision"] == "INVALID_INPUT_HOLD",
        "strict_screen_detects_sample_dropout": by_name["missing_reference_sample"]["strict_screen_decision"] == "INVALID_INPUT_HOLD",
        "strict_screen_rejects_primary_receipt_tamper": by_name["primary_tampered_against_original_session"]["strict_screen_decision"] == "INVALID_INPUT_HOLD",
    }
    if not all(controls.values()):
        raise AssertionError("Adversarial matrix behavior changed; inspect output rather than claiming pass")
    dmm = dmm_shunt_uncertainty_example()
    original_envelope = conservative_load_power_bound(spec["maximum_bus_voltage_v"], 10.0, 5.0, spec["maximum_power_w"])
    proposed_envelope = conservative_load_power_bound(spec["maximum_bus_voltage_v"], 12.0, 5.0, spec["maximum_power_w"])
    if original_envelope["within_ceiling"] or not proposed_envelope["within_ceiling"]:
        raise AssertionError("Conservative G0 option needs new independent review")
    report = {
        "schema": "hardware_splicer.witness_metrology_readiness_audit.v1",
        "source_baseline_git": "Witness fixture PR #356 source files (verify branch revision independently)",
        "source_design_sha256": hashfile(HERE / "station-spec-5v.json"),
        "original_native_replay_sha256": hashfile(args.native_replay/"verification.json"),
        "physical_instrument_connected": False,
        "physical_assembly_verified": False,
        "fabrication_allowed": False,
        "metrological_agreement_proven": False,
        "status": "HOLD_PHYSICAL_INSTRUMENT_AND_ENVELOPE_RECONCILIATION",
        "checks": controls,
        "corner_cases": corners,
        "conservative_unselected_load_option": {
            "original_10ohm_minus5pct": original_envelope,
            "candidate_12ohm_minus5pct": proposed_envelope,
            "canonical_v0_unchanged": True,
            "phy10_hold_still_open": True,
        },
        "capture_cases": cases,
        "reference_instrument_candidate": dmm,
        "fuse_candidate_issue": {
            "proposed_fuse_nominal_current_a": FUSE_CANDIDATE_A,
            "current_limited_supply_candidate_a": SOURCE_CURRENT_LIMIT_A,
            "clearing_while_current_limited_guaranteed": False,
            "reason": "No selected fuse time/current characteristic or source prospective fault-current/interrupt rating; 1 A is only a candidate."
        },
        "unclosed_evidence": [
            "Select and verify actual isolated supply and reference instrument(s), including high-side input and earthing",
            "Resolve 2.5 W declared ceiling against 5.25 V and load-resistance variation; modify specification or controlled test limits only after engineering review",
            "Choose a DC-rated fuse link and inspect source-limited fault clearing/cable protection",
            "Verify actual shunt values, 4-terminal geometry, INA228 carrier revision, bus and timestamps",
            "Select and characterize voltage/current acquisition and a second independent operator",
            "Perform approved physical fit, assembly, commissioning and comparative measurements; none occurred here",
        ],
        "economic_value_proven": False,
        "current_scope": "Independent digital replay and fault discrimination; no physical testing or procurement"
    }
    (dest / "report.json").write_text(json.dumps(report,indent=2)+"\n")
    rows = [
        "# Independent witness station readiness and fault-discrimination audit",
        "",
        "Status: **HOLD**. No actual independent reference instrument or built witness board.",
        "",
        "## Bounded operating corners (ngspice and independent arithmetic)",
        "",
        "| Source V | Load Ω | Modeled current A | Load W | Over declared 2.5 W? |",
        "|---:|---:|---:|---:|---|",
    ]
    rows += [
        f"| {x['input_voltage_v']:.2f} | {x['assumed_load_ohms']:.1f} | "
        f"{x['current_a']:.6f} | {x['load_power_w']:.6f} | "
        f"{'YES' if x['declared_load_power_limit_exceeded'] else 'No'} |"
        for x in corners
    ]
    rows += [
        "", "## Conservative normal-load option (not physically selected)", "",
        f"Original 10 ohm nominal / -5% hypothetical load at 5.25 V: {original_envelope['max_load_power_w_conservative']:.4f} W (FAIL).",
        f"Unselected 12 ohm nominal / -5% candidate at 5.25 V: {proposed_envelope['max_load_power_w_conservative']:.4f} W (within 2.5 W).",
        "These bounds do not establish fuse, source, wire, thermal or actual part suitability. Canonical 10 ohm v0 SPICE and PHY-10 HOLD are unchanged.",
        "", "## Injected fixture faults and Policy Lab outcome","",
        "| Input alteration | PL bridge exit | PL energy disagreement | PL discrepancy windows | Strict fixture screen |",
        "|---|---:|---:|---:|---|",
    ]
    rows += [
        f"| {c['name']} | {c['converter_exit']} | "
        f"{c['abs_percent_reference_larger_denominator']:.3f}% | {c['reported_disagreement_windows']} | {c['strict_screen_decision']} |"
        if c["converter_exit"] == 0 else
        f"| {c['name']} | {c['converter_exit']} (rejected) | — | — | {c['strict_screen_decision']} |"
        for c in cases
    ]
    rows += [
        "",
        "Policy Lab's frozen receiving interface is **structural and non-metrological**. A 5% reference-side increase is ~4.76% relative to the larger reading; it stays below a 5% warning rule. Even a diagnostic warning does not promote a capture into physical validation. Timebase synchronization remains unverified by matching CSV timestamps.",
        "",
        "## Hypothetical independent reference DMM",
        "",
        f"The proposed Siglent SDM3055 200 mV range example produces ±{dmm['manufacturer_dmm_voltage_error_uV']:.2f} µV at a 5 mV shunt signal (±{dmm['dmm_error_pct_of_5mV']:.3f}% of signal), *before* ±1% nominal shunt tolerance. This is a manufacturer-spec example subject to the stated warm-up/calibration conditions, **not a physically characterized uncertainty budget**.",
        "",
        "## Release conditions",
        "",
    ]
    rows += ["- "+item for item in report["unclosed_evidence"]]
    rows += [
        "", "**No purchase, fabrication, physical commissioning or independent operator validation occurred.**",
        "",
    ]
    (dest/"report.md").write_text("\n".join(rows))
    print(json.dumps({
        "status": report["status"],
        "controls_passed": sum(controls.values()),
        "controls_total": len(controls),
        "power_ceiling_failed_corners": sum(x["declared_load_power_limit_exceeded"] for x in corners),
        "out": str(dest)
    },indent=2))
    return 2 if args.fail_if_held else 0


if __name__ == "__main__":
    raise SystemExit(main())
