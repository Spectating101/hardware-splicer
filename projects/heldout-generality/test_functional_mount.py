"""Regression tests using committed held-out original-source lock and actual STEP output.

Run with a Python that can import CadQuery. No physical operation or EDA mutation.
"""
from __future__ import annotations
import copy,hashlib,json,shutil,tempfile,unittest
from pathlib import Path
import audit_mount_step

ROOT=Path(__file__).resolve().parent
E=ROOT/"functional-mount-evidence"
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class FunctionalMountEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock=read(ROOT/"cases.lock.json")
        cls.report=read(E/"reports/study-result.json")
        cls.orig=read(E/"reports/native-independent-audit.json")
        cls.edit=read(E/"reports/edit-receipt.json")
        cls.cad=read(E/"cad/fixture-receipt.json")
        cls.guide=read(E/"cad/independent-step-audit.json")

    def test_predeclared_four_cases_not_cherry_picked(self):
        expected=[c for c in self.lock["cases"] if c["metadata"]["ref_drv"]==0]
        self.assertEqual(len(expected),4)
        self.assertEqual(self.report["originally_clean_cases_attempted"],4)
        ids={c["id"] for c in expected}
        self.assertEqual(ids,set(self.report["successful_source_ids"]+
                                  self.report["blocked_source_ids"]))

    def test_actual_success_denominator_is_one_of_four(self):
        self.assertEqual(self.report["successful_source_to_verified_STEP"],1)
        self.assertEqual(self.report["explicitly_blocked_unsupported"],3)
        self.assertFalse(self.report["general_board_editing_proven"])

    def test_two_run_semantic_replay_is_identical(self):
        self.assertEqual(len(self.report["semantic_round_hashes"]),2)
        self.assertEqual(len(set(self.report["semantic_round_hashes"])),1)
        self.assertTrue(self.report["exact_semantic_replay"])
        self.assertEqual(read(E/"reports/round-1-summary.json"),
                         read(E/"reports/round-2-summary.json"))

    def test_original_third_party_license_and_file_digests(self):
        source=next(c for c in self.lock["cases"]
                    if c["id"]=="protolux-electronics__trellis_core__trellis_core")
        self.assertEqual(source["metadata"]["licence"],"CERN-OHL-P-2.0")
        self.assertEqual(sha(E/"source/LICENSE"),source["files_sha256"]["LICENSE"])
        self.assertEqual(sha(E/"source/SOURCE.json"),source["files_sha256"]["SOURCE.json"])
        self.assertEqual(sha(E/"pcb/board.kicad_pcb"),self.edit["edited_sha256"])
        self.assertNotEqual(self.edit["source_sha256"],self.edit["edited_sha256"])

    def test_independent_source_native_audit_retains_original_copper(self):
        self.assertEqual(self.orig["source_tracks_preserved"],620)
        self.assertEqual(self.orig["source_nets_and_pads_preserved"],342)
        self.assertTrue(self.orig["all_four_hole_positions_preserved"])
        self.assertEqual(self.edit["native_drc_error_count"],0)
        self.assertEqual(self.edit["native_drc_unconnected"],0)

    def test_actual_reopened_step_geometry_source_correlation(self):
        receipt=audit_mount_step.audit(E/"cad",self.orig,self.edit,self.cad)
        self.assertEqual(receipt["status"],"PASS")
        self.assertEqual(receipt["reopened_source_mapped_holes"],4)

    def test_stale_original_revision_refused(self):
        bad=copy.deepcopy(self.orig)
        bad["revised_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"REVISED_PCB_REVISION_MISMATCH"):
            audit_mount_step.audit(E/"cad",bad,self.edit,self.cad)

    def test_forged_contact_geometry_refused(self):
        bad=copy.deepcopy(self.cad)
        bad["model_hole_centres_mm"][0][0]+=.8
        with self.assertRaisesRegex(ValueError,"CLAIMED_MODEL_HOLES"):
            audit_mount_step.audit(E/"cad",self.orig,self.edit,bad)

    def test_fabrication_promotion_refused(self):
        bad=copy.deepcopy(self.cad)
        bad["fabrication_authorized"]=True
        with self.assertRaisesRegex(ValueError,"FALSE_FABRICATION_AUTHORITY"):
            audit_mount_step.audit(E/"cad",self.orig,self.edit,bad)

    def test_source_to_step_hold_not_hidden(self):
        self.assertEqual(self.edit["native_drc_warning_count"],97)
        self.assertTrue(self.cad["source_library_footprints_not_updated"])
        self.assertFalse(self.report["fabrication_authorized"])
        self.assertEqual(self.guide["source_footprint_library_alignment"],"REVIEW_HOLD")
        self.assertEqual(self.guide["mechanical_contact_or_fit_measurement"],"NOT_PERFORMED")

    def test_unsupported_failed_edits_preserved(self):
        r=read(E/"reports/failed_edit_attempts.json")
        self.assertEqual([x["candidates_tried"] for x in r["failures"]],[60,65,18,100])
        self.assertTrue(all(x["zero_error_candidates"]==0 for x in r["failures"]))

if __name__=="__main__":
    unittest.main(verbosity=2)
