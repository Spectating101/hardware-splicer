"""Protection/thermal/source preflight negative tests, never physical commissioning."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import protection_preflight as g1

HERE=Path(__file__).resolve().parent
TEMPLATE=json.loads((HERE/"G1_PROTECTION_INPUT_TEMPLATE.json").read_text())

class ProtectionPreflightTests(unittest.TestCase):
    def specimen(self):
        x=copy.deepcopy(TEMPLATE)
        x["source"].update({
            "manufacturer":"SIM_ONLY","model":"SIM_ONLY","serial":"SIM_ONLY",
            "voltage_limit_v":5.25,"measured_sustained_short_current_a":.65,
            "measured_peak_short_current_a":.80,
            "measured_current_limit_response_ms":20,
            "independent_source_limit_test_verified":True,
            "isolation_and_earth_review_verified":True,
            "independent_fault_shutdown_review_verified":True,
        })
        x["fuse"].update({
            "fuse_link_mpn":"SIM_ONLY","nominal_current_a":.5,
            "dc_voltage_rating_v":32,"dc_breaking_current_a":10,
            "time_current_curve_verified":True,
            "clearing_at_measured_sustained_fault_current_verified":True,
            "manufacturer_fuse_link_holder_match_verified":True,
            "holder_thermal_derating_checked":True,
        })
        x["wiring"].update({
            "cable_assembly_mpn":"SIM_ONLY","continuous_current_ampacity_a":1.5,
            "connector_dc_current_rating_a":1.0,
            "independent_short_and_shield_review_verified":True
        })
        x["thermal"].update({
            "mounting_part":"SIM_ONLY","derated_allowable_load_w_at_actual_ambient":3,
            "measured_load_temperature_c":38,
            "independent_thermal_mount_review_verified":True
        })
        x["review"].update({
            "engineering_reviewer":"SIM_REVIEWER","operator":"SIM_OPERATOR",
            "actual_source_and_fuse_identification_confirmed":True,
            "source_characterization_physical":True
        })
        return x

    def test_unselected_source_and_fuse_are_hold(self):
        x=g1.assess(TEMPLATE)
        self.assertEqual(x["structural_status"],"MISSING_PHYSICAL_EVIDENCE_HOLD")
        self.assertGreater(len(x["missing_evidence"]),15)
        self.assertFalse(x["fabrication_allowed"])

    def test_original_1a_fuse_not_proven_to_clear_at_650ma(self):
        x=self.specimen()
        x["fuse"]["nominal_current_a"]=1.0
        r=g1.assess(x)
        self.assertTrue(r["fuse_clearing_cannot_be_relied_on_at_sustained_limit"])
        self.assertIn("cannot be counted on", " ".join(r["contradictions"]))
        self.assertAlmostEqual(r["potential_continuous_source_output_w_if_setpoint_real"],3.4125)

    def test_well_populated_synthetic_dossier_does_not_release(self):
        r=g1.assess(self.specimen())
        self.assertEqual(r["structural_status"],"FILLED_FOR_INDEPENDENT_ENGINEER_REVIEW_ONLY")
        self.assertFalse(r["fabrication_allowed"])
        self.assertFalse(r["energization_authorized"])
        self.assertFalse(r["source_output_isolation_proven"])

    def test_peak_above_dc_interrupt_rating_is_blocked(self):
        x=self.specimen()
        x["fuse"]["dc_breaking_current_a"]=.7
        r=g1.assess(x)
        self.assertIn("interrupt rating lower"," ".join(r["contradictions"]))

    def test_underrated_cable_connector_and_thermal_mount_blocked(self):
        x=self.specimen()
        x["wiring"]["continuous_current_ampacity_a"]=.5
        x["wiring"]["connector_dc_current_rating_a"]=.4
        x["thermal"]["derated_allowable_load_w_at_actual_ambient"]=2
        r=g1.assess(x)
        self.assertEqual(sum("below" in q for q in r["contradictions"]),3)

    def test_measured_sustained_short_exceeds_source_setpoint(self):
        x=self.specimen()
        x["source"]["measured_sustained_short_current_a"]=.70
        r=g1.assess(x)
        self.assertIn("exceeds current-limit"," ".join(r["contradictions"]))

    def test_overvoltage_or_overcurrent_and_peak_less_than_sustained(self):
        x=self.specimen()
        x["source"]["voltage_limit_v"]=6
        x["source"]["set_current_limit_a"]=.9
        x["source"]["measured_peak_short_current_a"]=.60
        r=g1.assess(x)
        self.assertTrue(any("Source voltage limit" in y for y in r["contradictions"]))
        self.assertTrue(any("exceeds 0.65" in y for y in r["contradictions"]))
        self.assertTrue(any("peak current < sustained" in y for y in r["contradictions"]))

    def test_same_reviewer_and_operator_rejected(self):
        x=self.specimen()
        x["review"]["engineering_reviewer"]=x["review"]["operator"]
        r=g1.assess(x)
        self.assertTrue(any("identity are the same" in y for y in r["contradictions"]))

    def test_cold_temperature_is_valid_observation_not_automatic_release(self):
        x=self.specimen()
        x["thermal"]["measured_load_temperature_c"]=-5
        r=g1.assess(x)
        self.assertFalse(any("temperature" in msg for msg in r["missing_evidence"]))
        self.assertFalse(r["fabrication_allowed"])

    def test_nonfinite_nan_data_rejected(self):
        x=self.specimen()
        x["source"]["measured_sustained_short_current_a"]=float("nan")
        r=g1.assess(x)
        self.assertTrue(any("invalid positive" in y for y in r["missing_evidence"]))

    def test_cli_missing_packet_returns_exit_2_and_report(self):
        with tempfile.TemporaryDirectory() as p:
            out=Path(p)/"gate.json"
            completed=subprocess.run([sys.executable,str(HERE/"protection_preflight.py"),
                   "--input",str(HERE/"G1_PROTECTION_INPUT_TEMPLATE.json"),"--out",str(out)],
                   capture_output=True,text=True,timeout=10)
            self.assertEqual(completed.returncode,2,completed.stderr)
            d=json.loads(out.read_text())
            self.assertEqual(d["structural_status"],"MISSING_PHYSICAL_EVIDENCE_HOLD")
            self.assertFalse(d["energization_authorized"])


if __name__=="__main__":
    unittest.main()
