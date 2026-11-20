"""Reproducible witness fixture screening: actual pinned CSVs, not synthetic assertions.

All tests stay software-only and never connect to or energize electronics.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import measurement_screen as screen

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "evidence" / "fixture-replay-20261120"
P = FIXTURE / "primary" / "samples.csv"
R = FIXTURE / "reference-fixture.csv"
S = FIXTURE / "primary" / "session.json"
REG = FIXTURE / "primary" / "registers.jsonl"


class WitnessDiscriminationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hs-g2-screen-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def mutate_csv(self, source, filename, *, factor=1, drop=None, shift_s=0,
                   change_row=None, change_col=None, change_val=None):
        with source.open(newline="") as f:
            reader = csv.DictReader(f)
            names = reader.fieldnames
            rows = list(reader)
        if factor != 1:
            col = "shunt_voltage_v" if "shunt_voltage_v" in names else "current_a"
            for row in rows:
                row[col] = f"{float(row[col])*factor:.12f}"
        if shift_s:
            for row in rows:
                t = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
                row["timestamp_utc"] = (t + timedelta(seconds=shift_s)).isoformat(timespec="microseconds").replace("+00:00", "Z")
        if drop is not None:
            rows.pop(drop)
        if change_row is not None:
            rows[change_row][change_col] = change_val
        target = self.work / filename
        with target.open("w", newline="") as f:
            writer = csv.DictWriter(f, names)
            writer.writeheader()
            writer.writerows(rows)
        return target

    def call(self, reference=R, primary=P, registers=REG, **kwargs):
        return screen.screen(primary, reference, S, registers, **kwargs)

    def test_control_original_pinned_capture_passes_fixture_only(self):
        x = self.call()
        self.assertEqual(x["decision"], "PASS_FIXTURE_DISCRIMINATION_ONLY")
        self.assertEqual(x["samples_paired"], 183)
        self.assertLess(x["max_observed_sample_offset_ms"], 200)
        self.assertAlmostEqual(x["primary_energy_wh"], .125, delta=.004)
        self.assertFalse(x["physical_ready"])
        self.assertFalse(x["metrological_agreement_proven"])
        self.assertFalse(x["fabrication_allowed"])
        self.assertFalse(x["reference_independence_verified"])

    def test_one_percent_bias_is_detected(self):
        x = self.call(self.mutate_csv(R, "one.csv", factor=1.01))
        self.assertEqual(x["decision"], "FAIL_FIXTURE_DISAGREEMENT")
        self.assertGreater(x["energy_disagreement_primary_denominator_pct"], .9)
        self.assertEqual(x["outlier_count"], 183)

    def test_five_percent_bias_is_detected_not_hidden_by_larger_denominator(self):
        x = self.call(self.mutate_csv(R, "five.csv", factor=1.05))
        self.assertEqual(x["decision"], "FAIL_FIXTURE_DISAGREEMENT")
        self.assertGreater(x["energy_disagreement_primary_denominator_pct"], 4.9)

    def test_ten_percent_bias_is_detected(self):
        x = self.call(self.mutate_csv(R, "ten.csv", factor=1.10))
        self.assertEqual(x["decision"], "FAIL_FIXTURE_DISAGREEMENT")
        self.assertGreater(x["energy_disagreement_primary_denominator_pct"], 9.9)

    def test_whole_reference_clock_shift_500ms_is_rejected(self):
        altered = self.mutate_csv(R, "drift.csv", shift_s=.5)
        with self.assertRaisesRegex(screen.ScreeningError, "clock offset"):
            self.call(altered)

    def test_reference_sample_drop_breaks_continuity(self):
        altered = self.mutate_csv(R, "missing.csv", drop=77)
        with self.assertRaisesRegex(screen.ScreeningError, "Sampling gap"):
            self.call(altered)

    def test_receipted_primary_tampering_is_rejected(self):
        altered = self.mutate_csv(P, "changed-primary.csv", factor=1.05)
        with self.assertRaisesRegex(screen.ScreeningError, "SHA mismatch"):
            self.call(primary=altered)

    def test_tampered_source_registers_are_rejected(self):
        altered = self.work / "registers.jsonl"
        altered.write_bytes(REG.read_bytes() + b"\n")
        with self.assertRaisesRegex(screen.ScreeningError, "SHA mismatch"):
            self.call(registers=altered)

    def test_duplicate_reference_timestamp_is_rejected(self):
        altered = self.mutate_csv(R, "duplicate.csv", change_row=80,
                                  change_col="timestamp_utc",
                                  change_val="2026-11-20T00:01:18.173000Z")
        with self.assertRaisesRegex(screen.ScreeningError, "Non-monotonic"):
            self.call(altered)

    def test_nonfinite_reference_is_rejected(self):
        altered = self.mutate_csv(R, "nan.csv", change_row=55,
                                  change_col="shunt_voltage_v", change_val="nan")
        with self.assertRaisesRegex(screen.ScreeningError, "Nonfinite"):
            self.call(altered)

    def test_negative_reference_is_rejected_for_positive_station(self):
        altered = self.mutate_csv(R, "negative.csv", change_row=55,
                                  change_col="shunt_voltage_v", change_val="-0.002")
        with self.assertRaisesRegex(screen.ScreeningError, "Nonfinite or negative"):
            self.call(altered)

    def test_single_transient_reference_bias_is_flagged(self):
        altered = self.mutate_csv(R, "transient.csv", change_row=80,
                                  change_col="shunt_voltage_v", change_val="0.00545")
        x = self.call(altered)
        self.assertEqual(x["decision"], "FAIL_FIXTURE_DISAGREEMENT")
        self.assertEqual(x["outlier_count"], 1)

    def test_config_invalid_values_fail_closed(self):
        for changes in ({"shunt_ohms": 0}, {"max_pair_offset_ms": -1},
                        {"diagnostic_threshold_pct": float("nan")}):
            with self.subTest(changes=changes), self.assertRaises(screen.ScreeningError):
                self.call(**changes)

    def test_power_envelope_candidate_conservative_and_original_fails(self):
        spec = json.loads((HERE / "station-spec-5v.json").read_text())
        ceiling = spec["maximum_power_w"]
        original = screen.conservative_load_power_bound(5.25, 10, 5, ceiling)
        proposed = screen.conservative_load_power_bound(5.25, 12, 5, ceiling)
        self.assertFalse(original["within_ceiling"])
        self.assertTrue(proposed["within_ceiling"])
        self.assertAlmostEqual(proposed["max_load_power_w_conservative"], 5.25**2/11.4)
        self.assertFalse(proposed["physical_part_selected"])
        self.assertFalse(proposed["physical_fault_protection_proven"])

    def test_12ohm_candidate_fails_with_looser_tolerance(self):
        self.assertFalse(screen.conservative_load_power_bound(5.25,12,10,2.5)["within_ceiling"])

    def test_cli_returns_nonzero_for_discrepancy_and_invalid_input(self):
        def invoke(ref, suffix):
            out = self.work / (suffix + ".json")
            run = subprocess.run([sys.executable, str(HERE / "measurement_screen.py"),
                    "--primary", str(P), "--reference", str(ref),
                    "--primary-session", str(S), "--primary-registers", str(REG),
                    "--out", str(out)], capture_output=True, text=True, timeout=20)
            return run, json.loads(out.read_text())
        ok, report = invoke(R,"pass")
        self.assertEqual(ok.returncode,0,ok.stderr)
        self.assertFalse(report["physical_ready"])
        fail, report = invoke(self.mutate_csv(R, "bias.csv",factor=1.01),"fail")
        self.assertEqual(fail.returncode,2,fail.stderr)
        self.assertEqual(report["decision"],"FAIL_FIXTURE_DISAGREEMENT")
        invalid, report = invoke(self.mutate_csv(R,"time.csv",shift_s=.5),"invalid")
        self.assertEqual(invalid.returncode,2,invalid.stderr)
        self.assertEqual(report["decision"],"INVALID_INPUT_HOLD")


if __name__ == "__main__":
    unittest.main()
