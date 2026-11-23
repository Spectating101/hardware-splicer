"""G1 evidence gate negative controls; generated test bytes are NOT measurements."""
from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import g1_evidence_gate as g1

HERE=Path(__file__).resolve().parent
EMPTY=json.loads((HERE/"G1_BENCH_EVIDENCE_TEMPLATE.json").read_text())


class G1EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="witness-g1-dummy-")
        self.addCleanup(tmp.cleanup)
        self.dir=Path(tmp.name)

    def populate_dummy_packet(self):
        """Create entirely synthetic named files, even if fields look complete."""
        data=copy.deepcopy(EMPTY)
        fields={
            "capture_kind":"DECLARED_BENCH_CAPTURE",
            "run_id":"TEST_ONLY_NOT_PHYSICAL",
            "operator_id":"dummy_a",
            "independent_reviewer_id":"dummy_b",
            "load_mpn":"RE65G12R0C02",
            "source_model":"DUMMY_SOURCE",
            "source_serial":"NOT_A_REAL_SERIAL",
            "source_current_limit_a":.5,
            "fuse_link_mpn":"DUMMY_DC_FUSE_UNVERIFIED",
            "fuse_holder_mpn":"0031.3551",
            "reference_meter_model":"DUMMY_REFERENCE",
            "reference_meter_serial":"NOT_A_REAL_REFERENCE",
            "reference_calibration_valid_until_utc":"2027-01-01T00:00:00Z",
            "primary_sensor_serial":"DUMMY_SENSOR",
            "primary_shunt_measured_ohms":.015,
            "reference_shunt_measured_ohms":.01,
            "reference_capture_clock":"DUMMY_CLOCK",
            "measured_max_clock_offset_ms":100,
            "start_utc":"2026-11-20T00:00:00Z",
            "end_utc":"2026-11-20T00:03:00Z"
        }
        data.update(fields)
        by_role={}
        for item in data["files"]:
            role=item["role"]
            dst=self.dir/(role+".txt")
            if role=="primary_native_capture":
                dst.write_bytes(b"timestamp_utc,voltage_v,current_a\n2026-11-20T00:00:00Z,4.96,0.414\n")
            elif role=="primary_registers":
                dst.write_bytes(b'{"sample":"DUMMY_FAKE_REGISTER_NO_REAL_DEVICE"}\n')
            elif role!="primary_session":
                dst.write_bytes(("TEST_ONLY_UNVERIFIED_"+role+"\n").encode())
            by_role[role]=dst
            item["path"]=dst.name
        primary=by_role["primary_native_capture"]
        registers=by_role["primary_registers"]
        sess={
            "capture_kind":"DECLARED_BENCH_CAPTURE",
            "source_kind":"linux_i2c",
            "status":"COMPLETE",
            "completed_samples":3,
            "files":{
                "samples.csv":{"sha256":g1.sha256(primary),"bytes":primary.stat().st_size},
                "registers.jsonl":{"sha256":g1.sha256(registers),"bytes":registers.stat().st_size}
            }
        }
        by_role["primary_session"].write_text(json.dumps(sess))
        for item in data["files"]:
            item["sha256"]=g1.sha256(by_role[item["role"]])
        return data

    def test_blank_actual_template_is_hold(self):
        r=g1.screen_packet(EMPTY,self.dir)
        self.assertEqual(r["status"],"HOLD_MISSING_OR_CONFLICTED_EVIDENCE")
        self.assertGreater(len(r["structural_problems"]),10)
        self.assertFalse(r["physical_ready"])
        self.assertFalse(r["fabrication_allowed"])

    def test_dummy_structural_completion_cannot_grant_physical_release(self):
        r=g1.screen_packet(self.populate_dummy_packet(),self.dir)
        self.assertEqual(r["status"],"STRUCTURALLY_FILLED_FOR_INDEPENDENT_HUMAN_REVIEW_ONLY")
        self.assertFalse(r["document_custody_proven"])
        self.assertFalse(r["instrument_calibration_proven"])
        self.assertFalse(r["external_clock_synchronized_proven"])
        self.assertFalse(r["energization_authorized"])
        self.assertFalse(r["physical_ready"])
        self.assertFalse(r["fabrication_allowed"])

    def test_original_ina228_fixture_disguised_as_real_is_rejected(self):
        p=self.populate_dummy_packet()
        session=self.dir/"primary_session.txt"
        x=json.loads(session.read_text())
        x["source_kind"]="register_fixture"
        x["capture_kind"]="TEST_FIXTURE"
        session.write_text(json.dumps(x))
        for item in p["files"]:
            if item["role"]=="primary_session":
                item["sha256"]=g1.sha256(session)
        result=g1.screen_packet(p,self.dir)
        self.assertIn("reject TEST_FIXTURE","; ".join(result["structural_problems"]))

    def test_tampered_source_file_is_rejected(self):
        p=self.populate_dummy_packet()
        (self.dir/"source_fault_limit_record.txt").write_text("CHANGE AFTER HASH")
        r=g1.screen_packet(p,self.dir)
        self.assertTrue(any("SHA-256 mismatch" in s for s in r["structural_problems"]))

    def test_outside_repository_file_path_is_rejected(self):
        p=self.populate_dummy_packet()
        p["files"][0]["path"]="../some-other-file.txt"
        r=g1.screen_packet(p,self.dir)
        self.assertTrue(any("unsafe evidence path" in s for s in r["structural_problems"]))

    def test_symlink_to_evidence_file_is_rejected(self):
        p=self.populate_dummy_packet()
        source=self.dir/p["files"][0]["path"]
        alias=self.dir/"evidence_link.txt"
        alias.symlink_to(source)
        p["files"][0]["path"]=alias.name
        r=g1.screen_packet(p,self.dir)
        self.assertIn("unsafe evidence path", " ".join(r["structural_problems"]))

    def test_same_physical_file_for_two_roles_is_rejected(self):
        p=self.populate_dummy_packet()
        p["files"][1]["path"]=p["files"][0]["path"]
        p["files"][1]["sha256"]=p["files"][0]["sha256"]
        r=g1.screen_packet(p,self.dir)
        self.assertTrue(any("reused for independent evidence" in s for s in r["structural_problems"]))

    def test_self_review_and_overlimit_supply_block(self):
        p=self.populate_dummy_packet()
        p["independent_reviewer_id"]=p["operator_id"]
        p["source_current_limit_a"]=.70
        r=g1.screen_packet(p,self.dir)
        self.assertIn("Reviewer cannot be identical", " ".join(r["structural_problems"]))
        self.assertIn("exceeds the candidate", " ".join(r["structural_problems"]))

    def test_expired_certificate_and_invalid_time_order_block(self):
        p=self.populate_dummy_packet()
        p["reference_calibration_valid_until_utc"]="2026-10-01T00:00:00Z"
        r=g1.screen_packet(p,self.dir)
        self.assertIn("validity inconsistent", " ".join(r["structural_problems"]))
        p["start_utc"]="2026-11-21T00:00:00Z"
        r=g1.screen_packet(p,self.dir)
        self.assertIn("Capture time", " ".join(r["structural_problems"]))

    def test_receipt_raw_source_mismatch_is_rejected_even_if_manifest_hash_is_valid(self):
        p=self.populate_dummy_packet()
        x=json.loads((self.dir/"primary_session.txt").read_text())
        x["files"]["samples.csv"]["sha256"]="0"*64
        f=self.dir/"primary_session.txt"
        f.write_text(json.dumps(x))
        for item in p["files"]:
            if item["role"]=="primary_session":
                item["sha256"]=g1.sha256(f)
        r=g1.screen_packet(p,self.dir)
        self.assertIn("raw capture/hash", " ".join(r["structural_problems"]))

    def test_cli_exit_code_two_on_blank_packet(self):
        dst=self.dir/"result.json"
        run=subprocess.run([sys.executable,str(HERE/"g1_evidence_gate.py"),
                            "--packet",str(HERE/"G1_BENCH_EVIDENCE_TEMPLATE.json"),
                            "--out",str(dst),"--fail-if-held"],
                           text=True,capture_output=True,timeout=10)
        self.assertEqual(run.returncode,2,run.stderr)
        val=json.loads(dst.read_text())
        self.assertEqual(val["status"],"HOLD_MISSING_OR_CONFLICTED_EVIDENCE")
        self.assertFalse(val["physical_ready"])
        again=subprocess.run([sys.executable,str(HERE/"g1_evidence_gate.py"),
                              "--packet",str(HERE/"G1_BENCH_EVIDENCE_TEMPLATE.json"),
                              "--out",str(dst)],text=True,capture_output=True,timeout=10)
        self.assertNotEqual(again.returncode,0)


if __name__=="__main__":
    unittest.main()
