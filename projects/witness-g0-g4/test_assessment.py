"""G0–G4 source-integrity, envelope and non-promotion adversarial controls."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from assessment import Hold, build, evaluate, validate, verify

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE / "campaign.json"


def input_case():
    return json.loads(CAMPAIGN.read_text(encoding="utf-8"))


class G0G4Tests(unittest.TestCase):
    def test_candidate_tradeoffs_hold_original_power_limit(self):
        data = build(input_case())
        rows = {row["id"]: row for row in data["candidates"]}
        self.assertFalse(rows["original_10R_5pct"]["checks"]["under_original_power_ceiling"])
        self.assertFalse(rows["12R_5pct"]["checks"]["has_required_design_reserve"])
        self.assertTrue(rows["12R_5pct"]["checks"]["under_original_power_ceiling"])
        self.assertTrue(rows["13R_5pct"]["digital_pass"])
        self.assertTrue(rows["13R_1pct_TE355013RFT"]["digital_pass"])
        self.assertFalse(rows["15R_5pct"]["checks"]["above_test_reference_current_floor"])
        self.assertFalse(any(row["physical_part_qualified"] for row in rows.values()))

    def test_selected_candidate_has_reserve_but_is_not_physically_qualified(self):
        receipt = build(input_case())
        selected = next(c for c in receipt["candidates"] if c["id"] == receipt["digital_candidate"])
        self.assertLess(selected["worst_normal_load_power_w"], 2.25)
        self.assertGreater(selected["minimum_normal_current_a"], 0.34)
        self.assertLess(selected["worst_normal_current_a"], 0.65)
        self.assertEqual(receipt["gates"]["G0"]["status"], "DIGITAL_MODEL_PASS_PHYSICAL_BUILD_HOLD")
        self.assertFalse(receipt["build_authorized"])
        self.assertFalse(receipt["power_on_authorized"])

    def test_uncalibrated_dmm_and_shunt_cannot_prove_075_percent(self):
        d = build(input_case())["reference_sensitivity_screen"]
        self.assertGreater(d["simple_sum_percent_not_a_traceable_uncertainty"], 1.2)
        self.assertGreater(d["simple_sum_percent_not_a_traceable_uncertainty"], d["fixture_only_sensitivity_threshold_pct"])
        self.assertFalse(d["g2_physical_agreement_verified"])

    def test_all_later_gates_held_with_no_physical_capture(self):
        d = build(input_case())
        self.assertEqual(d["gates"]["G1"]["status"], "HOLD_NO_PHYSICAL_EVIDENCE")
        self.assertEqual(d["gates"]["G2"]["status"], "HOLD_UNCALIBRATED_REFERENCE")
        self.assertEqual(d["gates"]["G3"]["status"], "SOFTWARE_FIXTURE_ONLY")
        self.assertEqual(d["gates"]["G4"]["status"], "NOT_ASSESSED")
        self.assertFalse(d["policy_lab_financial_claim_authorized"])

    def test_injected_self_assertions_of_device_or_calibration_fail_closed(self):
        keys = ("original_board_fabricated", "load_thermal_mounting_verified",
                "fuse_dc_interruption_coordination_verified", "external_second_operator_verified",
                "reference_shunt_calibration_verified", "supply_selected_or_bench_verified")
        for name in keys:
            with self.subTest(name=name):
                p = input_case()
                p["engineering_provenance"][name] = True
                with self.assertRaisesRegex(Hold, "unauthenticated"):
                    build(p)

    def test_forged_measurement_and_economics_not_accepted(self):
        p = input_case()
        p["measurement_protocol"]["acquisition_class"] = "PHYSICAL_MEASUREMENT"
        with self.assertRaises(Hold):
            build(p)
        p = input_case()
        p["economics"]["verified_revenue_available"] = True
        with self.assertRaises(Hold):
            build(p)

    def test_changing_station_contract_or_digest_fails(self):
        p = input_case()
        p["source"]["sha256"] = "0"*64
        with self.assertRaisesRegex(Hold, "digest mismatch"):
            build(p)
        p = input_case()
        p["criteria"]["bus_max_v"] = 6
        with self.assertRaisesRegex(Hold, "original station contract"):
            build(p)

    def test_changed_design_reserve_recomputes_not_silently_forged(self):
        p = input_case()
        p["criteria"]["design_reserve_fraction"] = 0.2
        result = build(p)
        chosen = next(c for c in result["candidates"] if c["id"] == result["digital_candidate"])
        self.assertFalse(chosen["digital_pass"])
        self.assertEqual(result["gates"]["G0"]["status"], "DESIGN_REJECTED")
        self.assertFalse(result["power_on_authorized"])

    def test_source_candidate_boundaries_and_invalid_input(self):
        for change in [
            lambda d: d["candidates"][0].update(ohms=-1),
            lambda d: d["candidates"][0].update(tolerance_pct=100),
            lambda d: d["candidates"][0].update(ohms="13"),
            lambda d: d["candidates"][0].update(ohms=float("nan")),
            lambda d: d["source"].update(station_spec="../outside.json"),
            lambda d: d.update(selected_for_digital_screen="not-in-candidates"),
            lambda d: d["criteria"].update(bus_max_v=999),
            lambda d: d.update(physical_authority_granted=True)
        ]:
            p = input_case()
            change(p)
            with self.assertRaises((Hold, ValueError, OSError)):
                build(p)

    def test_receipt_reproduces_and_mutation_is_rejected(self):
        p = input_case()
        r = build(p)
        self.assertTrue(verify(p, r)["verified"])
        altered = copy.deepcopy(r)
        altered["candidates"][0]["worst_normal_load_power_w"] = 0
        with self.assertRaisesRegex(Hold, "does not replay"):
            verify(p, altered)
        altered = copy.deepcopy(r)
        altered["power_on_authorized"] = True
        with self.assertRaisesRegex(Hold, "does not replay"):
            verify(p, altered)

    def test_published_receipt_replays_without_drift(self):
        pinned = json.loads((HERE / 'evidence' / 'digital-gate-assessment.v1.json').read_text(encoding='utf-8'))
        self.assertEqual(pinned, build(input_case()))
        self.assertTrue(verify(input_case(), pinned)['verified'])

    def test_duplicate_or_nonfinite_campaign_json_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "duplicate.json"
            dest.write_text('{"schema":"a","schema":"b"}',encoding="utf-8")
            run = subprocess.run([sys.executable, str(HERE/"assessment.py"), "--campaign", str(dest)],
                                 capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0)
            self.assertIn("duplicate JSON key",run.stderr)
            dest.write_text('{"schema":NaN}',encoding="utf-8")
            run = subprocess.run([sys.executable, str(HERE/"assessment.py"), "--campaign", str(dest)],
                                 capture_output=True,text=True)
            self.assertNotEqual(run.returncode,0)
            self.assertIn("nonfinite JSON",run.stderr)

    def test_cli_build_and_verify_with_replay_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/"receipt.json"
            first = subprocess.run([sys.executable,str(HERE/"assessment.py"),"--out",str(target)],capture_output=True,text=True)
            self.assertEqual(first.returncode,0,first.stderr)
            second = subprocess.run([sys.executable,str(HERE/"assessment.py"),"--verify",str(target)],capture_output=True,text=True)
            self.assertEqual(second.returncode,0,second.stderr)
            self.assertTrue(json.loads(second.stdout)["verified"])
            third = subprocess.run([sys.executable,str(HERE/"assessment.py"),"--out",str(target)],capture_output=True,text=True)
            self.assertNotEqual(third.returncode,0)
            self.assertIn("cannot overwrite",third.stderr)


if __name__ == "__main__":
    unittest.main()
