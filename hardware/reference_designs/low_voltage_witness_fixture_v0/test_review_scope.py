"""Consolidation scope contract; rejects missing stages and changed evidence."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import review_scope as scope

HERE = Path(__file__).resolve().parent


class ConsolidationScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hs-consolidation-scope-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.report_path = self.root / "review.json"
        rows = []
        for name, code, relative in scope.EXPECTED_STAGES:
            entry = {"stage": name, "exit_code": code,
                     "expected_exit_code": code, "passed_expected_behavior": True}
            if relative:
                artifact = self.root / relative
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text('{"fabrication_allowed":false,"physical_ready":false}\n')
                entry.update(artifact_path=str(artifact),
                             artifact_sha256=scope.digest(artifact))
            else:
                entry["completed_tests"] = 120
            rows.append(entry)
        self.report = {
            "schema": "hardware_splicer.consolidated_witness_software_review.v1",
            "overall": "SOFTWARE_INTEGRATION_VERIFIED_PHYSICAL_HOLD",
            "repo": {"git_head": "0"*40, "working_tree_clean_before": True,
                     "working_tree_clean_after": True},
            "dependencies": {"expected_policy_lab_commit": "1"*40,
                             "policy_lab_commit": "1"*40,
                             "policy_lab_worktree_clean": True},
            "steps": rows,
            **{k:False for k in scope.MUST_FALSE}
        }
        self.save()

    def save(self):
        self.report_path.write_text(json.dumps(self.report,indent=2)+"\n")

    def check(self):
        self.save()
        return scope.validate(self.report_path)

    def test_complete_nine_stage_scope_only(self):
        x = self.check()
        self.assertEqual(x["status"],"SCOPE_REPRODUCED_WITH_PHYSICAL_HOLD",x["issues"])
        self.assertEqual(x["executed_stage_count"],9)
        self.assertEqual(x["test_count"],120)
        self.assertEqual(len(x["artifact_hashes_rechecked"]),8)
        self.assertFalse(x["physical_ready"])

    def test_unimplemented_13ohm_and_g0g4_explicitly_outside(self):
        x = self.check()
        outside = {e["pr"] for e in x["explicitly_outside_this_review"]}
        self.assertEqual(outside,{359,365,369})
        self.assertTrue(all(e["stage_present"] is False for e in x["explicitly_outside_this_review"]))

    def test_missing_stage_never_accepted(self):
        self.report["steps"].pop(3)
        self.assertTrue(self.check()["issues"])

    def test_reordered_stage_does_not_meet_contract(self):
        self.report["steps"][4],self.report["steps"][5] = self.report["steps"][5],self.report["steps"][4]
        self.assertTrue(any("identity/order" in s for s in self.check()["issues"]))

    def test_fabrication_flag_mutation_is_rejected(self):
        self.report["fabrication_allowed"] = True
        self.assertTrue(any("physical release flag" in s for s in self.check()["issues"]))

    def test_reported_success_but_corrupted_artifact_rejected(self):
        path=self.root/"native/verification.json"
        path.write_text('{"fabrication_allowed":true}')
        self.assertTrue(any("SHA mismatch" in s for s in self.check()["issues"]))

    def test_external_artifact_path_is_rejected(self):
        self.report["steps"][1]["artifact_path"] = "/tmp/not-our-verified-evidence.json"
        self.assertTrue(any("Output path escaped" in s for s in self.check()["issues"]))

    def test_missing_dependent_policy_lab_commit_rejected(self):
        self.report["dependencies"]["policy_lab_commit"]="deadbeef"
        self.assertTrue(any("Policy Lab receiver commit" in s for s in self.check()["issues"]))

    def test_underreported_test_count_rejected(self):
        self.report["steps"][0]["completed_tests"]=119
        self.assertTrue(any("120" in s for s in self.check()["issues"]))

    def test_cli_exit_codes_and_write_once(self):
        out=self.root/"scope.json"
        command=[sys.executable,str(HERE/"review_scope.py"),
                 "--review",str(self.report_path),"--out",str(out)]
        r=subprocess.run(command,capture_output=True,text=True,timeout=12)
        self.assertEqual(r.returncode,2,r.stderr)
        self.assertFalse(json.loads(out.read_text())["physical_ready"])
        r=subprocess.run(command,capture_output=True,text=True,timeout=12)
        self.assertNotEqual(r.returncode,0)
        self.assertIn("already exists",r.stderr)

    def test_bad_report_with_new_output_exits_one(self):
        self.report["overall"]="SOFTWARE_REVIEW_FAILED_OR_INCOMPLETE_HOLD"
        self.save()
        out=self.root/"bad-scope.json"
        r=subprocess.run([sys.executable,str(HERE/"review_scope.py"),
                          "--review",str(self.report_path),"--out",str(out)],
                         capture_output=True,text=True,timeout=12)
        self.assertEqual(r.returncode,1)
        self.assertFalse(json.loads(out.read_text())["fabrication_allowed"])


if __name__=="__main__":
    unittest.main()
