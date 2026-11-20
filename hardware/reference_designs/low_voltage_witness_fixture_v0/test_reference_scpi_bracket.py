"""Dual-DMM reference path harness tests; only fake instruments are exercised."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import reference_scpi_bracket as scpi

HERE=Path(__file__).resolve().parent


class Meter(scpi.FakeMeter):
    def __init__(self,name,value,*,response=None,delay_s=0):
        super().__init__(name,value)
        self.response=response
        self.delay_s=delay_s

    def query(self,cmd):
        if cmd.startswith("MEAS:VOLT:DC?") and self.delay_s:
            time.sleep(self.delay_s)
        x=super().query(cmd)
        return self.response if self.response is not None and cmd.startswith("MEAS:VOLT:DC?") else x


class BracketedReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="hs-scpi-mock-")
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)

    def run_pair(self,shunt=None,bus=None,*,kind="TEST_FIXTURE",period=.05):
        return scpi.capture_dual(
            shunt or Meter("SEPARATE_SHUNT",.00414),
            bus or Meter("SEPARATE_BUS",4.96),
            self.path/"run",samples=4,period_s=period,capture_kind=kind
        )

    def test_run_mock_dual_voltmeter_produces_4_sample_raw_provenance(self):
        a,b=Meter("S_A",.00414),Meter("S_B",4.96)
        result=self.run_pair(a,b)
        self.assertEqual(result["samples_captured"],4)
        self.assertEqual(result["status"],"COMPLETE_SOFTWARE_TIMESTAMP_BRACKETED_ONLY")
        self.assertEqual(result["source_kind"],"two_mock_scpi_meters")
        self.assertFalse(result["instrument_aperture_times_verified"])
        self.assertFalse(result["calibration_status_verified"])
        self.assertFalse(result["physical_ready"])
        self.assertFalse(result["fabrication_allowed"])
        self.assertTrue(a.close_called and b.close_called)
        self.assertIn("*IDN?",a.commands)
        self.assertIn(scpi.SHUNT_COMMAND,a.commands)
        self.assertIn(scpi.BUS_COMMAND,b.commands)
        with (self.path/"run/reference-preview.csv").open() as handle:
            csvrows=list(csv.DictReader(handle))
        self.assertEqual(len(csvrows),4)
        self.assertAlmostEqual(float(csvrows[0]["shunt_voltage_v"]),.00414)
        self.assertAlmostEqual(float(csvrows[0]["voltage_v"]),4.96)
        raw=(self.path/"run/reference-query-raw.jsonl").read_text().splitlines()
        self.assertEqual(len(raw),4)
        self.assertFalse(json.loads(raw[0])["true_instrument_aperture_proven"])
        self.assertTrue(all(self.path.joinpath("run",x).is_file() for x in
                            ("reference-preview.csv","reference-query-raw.jsonl","reference-session.json")))
        self.assertEqual(result["files"]["reference-query-raw.jsonl"]["sha256"],
                         scpi.sha256(self.path/"run/reference-query-raw.jsonl"))

    def test_nonfinite_overrange_and_nonscalar_dmm_responses_rejected(self):
        for bad in ("nan","inf","9.9E37","Overload","1.1,2.2",""):
            with self.subTest(value=bad),self.assertRaises(scpi.ReferenceCaptureError):
                scpi.parse_voltage(bad,max_abs_v=.2)

    def test_bad_shunt_voltage_fails_but_preserves_failed_session(self):
        with self.assertRaises(scpi.ReferenceCaptureError):
            self.run_pair(shunt=Meter("A",.00414,response="9.9E37"))
        s=json.loads((self.path/"run/reference-session.json").read_text())
        self.assertEqual(s["status"],"FAILED_RETAINED_PARTIAL")
        self.assertEqual(s["samples_captured"],0)
        self.assertFalse(s["physical_ready"])

    def test_negative_shunt_polarity_rejected(self):
        with self.assertRaises(scpi.ReferenceCaptureError):
            self.run_pair(shunt=Meter("A",-.00414))
        s=json.loads((self.path/"run/reference-session.json").read_text())
        self.assertEqual(s["status"],"FAILED_RETAINED_PARTIAL")

    def test_excessive_bus_voltage_rejected(self):
        with self.assertRaises(scpi.ReferenceCaptureError):
            self.run_pair(bus=Meter("B",5.6))
        s=json.loads((self.path/"run/reference-session.json").read_text())
        self.assertEqual(s["status"],"FAILED_RETAINED_PARTIAL")

    def test_identical_idn_blocks_capture(self):
        with self.assertRaisesRegex(scpi.ReferenceCaptureError,"identical instrument"):
            self.run_pair(Meter("same",.0041),Meter("same",4.96))
        s=json.loads((self.path/"run/reference-session.json").read_text())
        self.assertEqual(s["samples_captured"],0)

    def test_slow_dmm_response_does_not_imply_synchronous_capture(self):
        with self.assertRaises(scpi.ReferenceCaptureError):
            self.run_pair(bus=Meter("B",4.96,delay_s=.82))
        self.assertEqual(json.loads((self.path/"run/reference-session.json").read_text())["status"],
                         "FAILED_RETAINED_PARTIAL")

    def test_sampling_period_missed_aborts_without_inventing_rows(self):
        with self.assertRaises(scpi.ReferenceCaptureError):
            self.run_pair(bus=Meter("B",4.96,delay_s=.13))
        s=json.loads((self.path/"run/reference-session.json").read_text())
        self.assertEqual(s["status"],"FAILED_RETAINED_PARTIAL")
        self.assertLess(s["samples_captured"],4)

    def test_fake_meters_cannot_claim_declared_physical_reference(self):
        with self.assertRaisesRegex(ValueError,"fake meter cannot"):
            self.run_pair(kind="DECLARED_REFERENCE_BRACKETED_UNVERIFIED")

    def test_unknown_capture_kind_and_duplicate_resources_fail_early(self):
        with self.assertRaises(ValueError):
            self.run_pair(kind="ACTUAL_HARDWARE_APPROVED")
        with self.assertRaises(ValueError):
            scpi.capture_dual(Meter("A",.004),Meter("B",5),self.path/"notcreated",
                 samples=3,requested_resource_ids=("USB::A","USB::A"))
        self.assertFalse((self.path/"notcreated").exists())

    def test_cli_fixture_exit_two_and_never_physical(self):
        out=self.path/"fixture"
        r=subprocess.run([sys.executable,str(HERE/"reference_scpi_bracket.py"),
                "--transport","fixture","--samples","3","--period-s","0.05",
                "--out",str(out)],capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,2,r.stderr)
        receipt=json.loads((out/"reference-session.json").read_text())
        self.assertEqual(receipt["capture_kind"],"TEST_FIXTURE")
        self.assertFalse(receipt["physical_ready"])

    def test_cli_visa_wont_open_without_operator_approval(self):
        out=self.path/"not_open"
        r=subprocess.run([sys.executable,str(HERE/"reference_scpi_bracket.py"),
               "--transport","visa","--shunt-resource","USB::A","--bus-resource","USB::B",
               "--samples","3","--out",str(out)],capture_output=True,text=True,timeout=10)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("authorization required",r.stderr)
        self.assertFalse(out.exists())

    def test_cli_visa_wont_open_same_resource_twice(self):
        out=self.path/"not_open"
        r=subprocess.run([sys.executable,str(HERE/"reference_scpi_bracket.py"),
               "--transport","visa","--shunt-resource","USB::A","--bus-resource","USB::A",
               "--physical-read-only-authorized","--samples","3","--out",str(out)],
               capture_output=True,text=True,timeout=10)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("distinct",r.stderr)
        self.assertFalse(out.exists())


if __name__=="__main__":
    unittest.main()
