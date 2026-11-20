"""Native G0 candidate tests; no physical hardware and no part approval."""
from __future__ import annotations

import copy
import json
import math
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import bench_candidate_replay as g0

HERE = Path(__file__).resolve().parent
MATRIX = json.loads(g0.DEFAULT_MATRIX.read_text())


class ModelUnitTests(unittest.TestCase):
    def test_economy_part_fails_with_full_tcr_temperature_bound(self):
        c=g0.load_bound(MATRIX["candidates"][0],MATRIX)
        self.assertEqual(c["mpn"],"SQP10AJB-12R")
        self.assertAlmostEqual(c["maximum_normal_load_power_w"],2.515882578,places=6)
        self.assertFalse(c["power_ceiling_math_satisfied"])
        self.assertFalse(c["physical_derating_thermal_mount_verified"])

    def test_precision_part_passes_only_the_resistance_power_math(self):
        c=g0.load_bound(MATRIX["candidates"][1],MATRIX)
        self.assertEqual(c["mpn"],"RE65G12R0C02")
        self.assertAlmostEqual(c["maximum_normal_load_power_w"],2.330563292,places=6)
        self.assertTrue(c["power_ceiling_math_satisfied"])
        self.assertFalse(c["safety_approval"])

    def test_12r_minus5pct_at_25c_is_within_limit_but_not_over_full_temp(self):
        row=copy.deepcopy(MATRIX["candidates"][0])
        row["operating_temperature_c"]={"min":24,"max":26}
        c=g0.load_bound(row,MATRIX)
        self.assertLess(c["maximum_normal_load_power_w"],2.5)
        self.assertGreater(c["maximum_normal_load_power_w"],2.41)

    def test_reducing_tcr_changes_conservative_bound(self):
        x=copy.deepcopy(MATRIX["candidates"][0])
        before=g0.load_bound(x,MATRIX)["maximum_normal_load_power_w"]
        x["tcr_absolute_ppm_per_c"]=20
        after=g0.load_bound(x,MATRIX)["maximum_normal_load_power_w"]
        self.assertGreater(before,after)
        self.assertLess(after,2.5)

    def test_zero_resistance_nonfinite_values_fail_closed(self):
        for bad in (0,-1,float("nan"),float("inf")):
            row=copy.deepcopy(MATRIX["candidates"][1])
            row["value_ohms"]=bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                g0.load_bound(row,MATRIX)

    def test_invalid_temp_or_tcr_fails_closed(self):
        for field, bad in (("tolerance_percent",100),("tcr_absolute_ppm_per_c",500000)):
            row=copy.deepcopy(MATRIX["candidates"][1])
            row[field]=bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                g0.load_bound(row,MATRIX)
        row=copy.deepcopy(MATRIX["candidates"][1])
        row["operating_temperature_c"]={"min":25,"max":250}
        with self.assertRaises(ValueError):
            g0.load_bound(row,MATRIX)

    def test_spice_independent_arithmetic_both_models(self):
        for load,series,source in ((10,.075,5),(12,.075,5),(11.82654,0,5.25)):
            with self.subTest(load=load,series=series):
                x=g0.run_spice(source,load,series)
                self.assertTrue(x["spice_matched_independent_arithmetic"])
                self.assertAlmostEqual(x["load_power_w"],source**2*load/(load+series)**2,places=5)

    def test_12r_lower_power_shunt_signal(self):
        v0=g0.run_spice(5,10,.075)
        newer=g0.run_spice(5,12,.075)
        self.assertLess(newer["load_power_w"],v0["load_power_w"])
        self.assertLess(newer["load_current_a"],v0["load_current_a"])
        self.assertAlmostEqual(newer["load_current_a"]*.01, .00414,delta=.0001)


@unittest.skipUnless(shutil.which("ngspice"),"Requires ngspice for candidate SPICE fixture")
class IntegratedReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="witness-candidate-e2e-")
        cls.out=Path(cls.tmp.name)/"run"
        cls.pl=Path.home()/"chatgpt-work/pl-witness-freeze-20261120"
        cls.pl_available=(cls.pl/"scripts/equipment/dc_bench_capture.mjs").is_file()
        cls.cmd=[
            sys.executable,str(HERE/"bench_candidate_replay.py"),
            "--out",str(cls.out),
            "--baseline-verification",
            str(HERE/"evidence/fixture-replay-20261120/verification.json"),
            "--fail-if-held"
        ]
        if cls.pl_available:
            cls.cmd.extend(["--pl-root",str(cls.pl)])
        cls.replay_proc=subprocess.run(cls.cmd,text=True,capture_output=True,timeout=75)
        if cls.replay_proc.returncode!=2:
            raise AssertionError("Expected physical hold exit 2\n"+cls.replay_proc.stdout+"\n"+cls.replay_proc.stderr)
        cls.report=json.loads((cls.out/"report.json").read_text())

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,"tmp"):
            cls.tmp.cleanup()

    def test_release_hold_and_nonphysical_provenance(self):
        self.assertEqual(self.replay_proc.returncode,2)
        self.assertEqual(self.report["status"],"HOLD_NO_PHYSICAL_SELECTION_OR_QUALIFICATION")
        for f in ("fabrication_allowed","physical_ready","source_purchased",
                  "fuse_coordination_verified","reference_calibration_verified",
                  "thermal_mount_verified","external_timebase_verified",
                  "human_operator_signed_off"):
            self.assertIs(self.report[f],False,f)

    def test_full_new_model_12ohm_energy_and_reduced_load(self):
        x=self.report["revision_12ohm_nominal_model"]
        self.assertAlmostEqual(x["load_power_w"],2.05753536258,delta=.0005)
        self.assertAlmostEqual(self.report["revision_3min_model_wh"],x["load_power_w"]*.05,places=9)
        self.assertLess(x["load_current_a"],.65)

    def test_183_real_decoder_fixture_not_a_synthetic_csv_alone(self):
        self.assertEqual(self.report["new_fixture"]["primary_samples"],183)
        self.assertEqual(self.report["new_fixture"]["strict_screen_decision"],
                         "PASS_FIXTURE_DISCRIMINATION_ONLY")
        session=json.loads((self.out/"primary/session.json").read_text())
        self.assertEqual(session["source_kind"],"register_fixture")
        self.assertEqual(session["capture_kind"],"TEST_FIXTURE")
        self.assertEqual(session["completed_samples"],183)

    def test_original_and_new_sources_independently_bound(self):
        import hashlib
        checks=[
            ("matrix_sha256",g0.DEFAULT_MATRIX),
            ("original_pcb_sha256",HERE/"low_voltage_witness_fixture_v0.kicad_pcb"),
            ("original_schematic_sha256",HERE/"low_voltage_witness_fixture_v0.kicad_sch"),
        ]
        for name,p in checks:
            self.assertEqual(self.report["provenance"][name],hashlib.sha256(p.read_bytes()).hexdigest())

    def test_frozen_policy_lab_remains_nonphysical(self):
        if not self.pl_available:
            self.assertEqual(self.report["policy_lab_decision"],"NOT_RUN")
            self.skipTest("Separate Policy Lab PLRS-6 checkout not available")
        self.assertEqual(self.report["policy_lab_decision"],
                         "TEST_FIXTURE_STRUCTURALLY_INGESTED_NO_PHYSICAL_CLAIMS")
        receipt=json.loads((self.out/"policy-lab-intake/intake-receipt.json").read_text())
        self.assertFalse(receipt["physical_ready"])
        self.assertFalse(receipt["spk_issuance_allowed"])

    def test_uncertainty_floor_prevents_1_percent_physical_claim(self):
        b=self.report["provisional_reference_uncertainty_floor"]
        self.assertGreater(b["optimistic_simple_worst_case_pct"],1.2)
        self.assertGreater(b["nominal_shunt_signal_mv"],4)
        self.assertFalse(b["one_percent_comparison_supported"])

    def test_replay_evidence_is_write_once(self):
        r=subprocess.run(self.cmd,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("FileExistsError",r.stderr)

    def test_catalog_mutations_require_independent_review(self):
        matrix=copy.deepcopy(MATRIX)
        matrix["candidates"][1]["mpn"]="SOME_UNREVIEWED_PART"
        altered=Path(self.tmp.name)/"wrong.json"
        altered.write_text(json.dumps(matrix))
        r=subprocess.run([sys.executable,str(HERE/"bench_candidate_replay.py"),
                          "--matrix",str(altered),"--out",str(Path(self.tmp.name)/"wrong-output")],
                         capture_output=True,text=True,timeout=8)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("independent datasheet review",r.stderr)

    def test_new_replay_did_not_modify_original_spec_or_spice(self):
        self.assertEqual(json.loads((HERE/"station-spec-5v.json").read_text())["maximum_power_w"],2.5)
        self.assertIn("R_LOAD LOAD_PLUS 0 10",(HERE/"spice_low_voltage_witness.cir").read_text())
        self.assertFalse(self.report["reference_independence_verified"])


if __name__=="__main__":
    unittest.main()
