"""Combined release interlock: even forged-complete packets cannot authorize power."""
from __future__ import annotations

import copy
import csv
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import g1_commissioning_gate as gate
import reference_scpi_bracket as scpi

HERE=Path(__file__).resolve().parent


class G1CommissioningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="g1-commissioning-mock-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.reference=self.root/"reference"
        scpi.capture_dual(scpi.FakeMeter("SHUNT",.00414),
                          scpi.FakeMeter("BUS",4.96),
                          self.reference,samples=3,period_s=.05)
        self.session=self.reference/"reference-session.json"

    def read(self):
        return json.loads(self.session.read_text())

    def write_session(self,d):
        self.session.write_text(json.dumps(d,sort_keys=True,indent=2)+"\n")

    def forge_structurally_coherent_trace(self):
        """Fabricated complete 3-minute values: proves hashes != physical authenticity."""
        sess=self.read()
        trace=json.loads((self.reference/"reference-query-raw.jsonl").read_text().splitlines()[0])
        start=datetime(2026,11,20,0,0,0,tzinfo=timezone.utc)
        raw=[]
        csvout=[]
        for index in range(183):
            t=start+timedelta(seconds=index)
            s=t.isoformat(timespec="microseconds").replace("+00:00","Z")
            before=(t-timedelta(milliseconds=100)).isoformat(timespec="microseconds").replace("+00:00","Z")
            after=(t+timedelta(milliseconds=100)).isoformat(timespec="microseconds").replace("+00:00","Z")
            item=copy.deepcopy(trace)
            item["index"]=index
            item["host_reference_midpoint_utc"]=s
            item["host_query_center_skew_ms"]=0
            for role in ("shunt","bus"):
                item[role]["query_start_utc"]=before
                item[role]["query_end_utc"]=after
                item[role]["query_latency_ms"]=200
                item[role]["query_start_mono_s"]=float(index)
                item[role]["query_end_mono_s"]=float(index)+.2
            raw.append(item)
            csvout.append((s,4.96,.00414))
        path=self.reference/"reference-preview.csv"
        with path.open("w",newline="") as output:
            writer=csv.writer(output)
            writer.writerow(("timestamp_utc","voltage_v","shunt_voltage_v"))
            writer.writerows(csvout)
        path=self.reference/"reference-query-raw.jsonl"
        path.write_text("".join(json.dumps(item)+"\n" for item in raw))
        sess.update({"source_kind":"dual_scpi_meters",
                     "capture_kind":"DECLARED_REFERENCE_BRACKETED_UNVERIFIED",
                     "status":"COMPLETE_SOFTWARE_TIMESTAMP_BRACKETED_ONLY",
                     "reference_meter_paths_distinct":True,
                     "samples_captured":183})
        sess["identifiers"]={"shunt_idn":"SIGLENT,SDM3055,FAKE_AUTHENTICATED_BY_NONE,1",
                             "bus_idn":"SIGLENT,SDM3055,SECOND_SN,1",
                             "resource_names_claimed":["USB::RESOURCE_A","USB::RESOURCE_B"],
                             "identity_authenticity_verified":False}
        # Prove absence of identity authority despite strings that resemble real IDs.
        sess["identifiers"]["shunt_idn"]="SIGLENT,SDM3055,UNVERIFIED_SERIAL_A,1"
        for name in ("reference-query-raw.jsonl","reference-preview.csv"):
            path=self.reference/name
            sess["files"][name]={"bytes":path.stat().st_size,"sha256":gate.sha256(path)}
        self.write_session(sess)
        return sess

    def test_testfixture_capture_cannot_enter_g1(self):
        r=gate.check_reference(self.session)
        self.assertEqual(r["structural_status"],"REFERENCE_TRACE_HOLD")
        self.assertTrue(any("TEST_FIXTURE" in q for q in r["problems"]))
        self.assertFalse(r["physical_ready"])

    def test_hash_modified_query_trace_is_rejected(self):
        self.forge_structurally_coherent_trace()
        (self.reference/"reference-query-raw.jsonl").write_text("TAMPER")
        r=gate.check_reference(self.session)
        self.assertTrue(any("Mismatched" in q for q in r["problems"]))

    def test_plausible_synthetic_forged_trace_still_only_structural(self):
        self.forge_structurally_coherent_trace()
        r=gate.check_reference(self.session)
        self.assertEqual(r["structural_status"],"TRACE_STRUCTURALLY_INTACT_NOT_TIMING_PROVEN",r["problems"])
        self.assertFalse(r["instrument_aperture_time_proven"])
        self.assertFalse(r["reference_source_physically_authenticated"])
        self.assertFalse(r["external_timebase_proven"])

    def test_impossible_aperture_verified_assertion_rejected(self):
        sess=self.forge_structurally_coherent_trace()
        sess["instrument_aperture_times_verified"]=True
        self.write_session(sess)
        r=gate.check_reference(self.session)
        self.assertTrue(any("Unsupported assertion" in s for s in r["problems"]))

    def test_bad_normalized_value_fails_even_with_matching_file_hash(self):
        sess=self.forge_structurally_coherent_trace()
        path=self.reference/"reference-preview.csv"
        body=path.read_text().replace("4.96,0.00414","5.00,0.00414",1)
        path.write_text(body)
        sess["files"]["reference-preview.csv"]={"bytes":path.stat().st_size,"sha256":gate.sha256(path)}
        self.write_session(sess)
        result=gate.check_reference(self.session)
        self.assertTrue(any("CSV value" in q for q in result["problems"]))

    def test_bad_clock_midpoint_detected(self):
        sess=self.forge_structurally_coherent_trace()
        path=self.reference/"reference-query-raw.jsonl"
        records=[json.loads(s) for s in path.read_text().splitlines()]
        records[42]["shunt"]["query_start_utc"]="2026-11-20T00:04:00.000000Z"
        path.write_text("".join(json.dumps(x)+"\n" for x in records))
        sess["files"]["reference-query-raw.jsonl"]={"bytes":path.stat().st_size,"sha256":gate.sha256(path)}
        self.write_session(sess)
        r=gate.check_reference(self.session)
        self.assertTrue(any("not bracketed" in p or "sample 42" in p for p in r["problems"]))

    def test_1hz_183_sample_duration_not_3_sample_filler(self):
        sess=self.forge_structurally_coherent_trace()
        sess["samples_captured"]=3
        self.write_session(sess)
        r=gate.check_reference(self.session)
        self.assertTrue(any("Insufficient" in q for q in r["problems"]))

    def test_combined_blank_g1_and_protection_are_hold(self):
        result=gate.evaluate(HERE/"G1_BENCH_EVIDENCE_TEMPLATE.json",
                             HERE/"G1_PROTECTION_INPUT_TEMPLATE.json",
                             self.session)
        self.assertEqual(result["status"],"STRUCTURAL_CONFLICTS_HOLD")
        self.assertFalse(result["energization_authorized"])
        self.assertFalse(result["fabrication_allowed"])
        self.assertFalse(result["metrological_agreement_proven"])
        self.assertGreaterEqual(len(result["reasons"]),3)

    def test_even_three_optimistically_filled_structures_cannot_grant_release(self):
        self.forge_structurally_coherent_trace()
        with patch.object(gate.bench,"screen_packet",
                          return_value={"status":"STRUCTURALLY_FILLED_FOR_INDEPENDENT_HUMAN_REVIEW_ONLY",
                                        "structural_problems":[]}), \
             patch.object(gate.protect,"assess",
                          return_value={"structural_status":"FILLED_FOR_INDEPENDENT_ENGINEER_REVIEW_ONLY",
                                        "missing_evidence":[],"contradictions":[]}):
            result=gate.evaluate(HERE/"G1_BENCH_EVIDENCE_TEMPLATE.json",
                                 HERE/"G1_PROTECTION_INPUT_TEMPLATE.json",
                                 self.session)
        self.assertEqual(result["status"],"THREE_STRUCTURAL_CHECKS_ONLY_HUMAN_REVIEW_REQUIRED")
        self.assertFalse(result["energization_authorized"])
        self.assertFalse(result["fabrication_allowed"])
        self.assertFalse(result["physical_ready"])

    def test_cli_with_blank_packets_exit_two(self):
        out=self.root/"screen.json"
        completed=subprocess.run([sys.executable,str(HERE/"g1_commissioning_gate.py"),
            "--g1-packet",str(HERE/"G1_BENCH_EVIDENCE_TEMPLATE.json"),
            "--protection-input",str(HERE/"G1_PROTECTION_INPUT_TEMPLATE.json"),
            "--reference-session",str(self.session),"--out",str(out)],
            capture_output=True,text=True,timeout=10)
        self.assertEqual(completed.returncode,2,completed.stderr)
        self.assertFalse(json.loads(out.read_text())["physical_ready"])
        attempted=subprocess.run([sys.executable,str(HERE/"g1_commissioning_gate.py"),
            "--g1-packet",str(HERE/"G1_BENCH_EVIDENCE_TEMPLATE.json"),
            "--protection-input",str(HERE/"G1_PROTECTION_INPUT_TEMPLATE.json"),
            "--reference-session",str(self.session),"--out",str(out)],
            capture_output=True,text=True,timeout=10)
        self.assertNotEqual(attempted.returncode,0)


if __name__=="__main__":
    unittest.main()
