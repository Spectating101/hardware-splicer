"""Vendor source proof-screen tests; none indicate power-on authorization."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import source_suitability as src

HERE=Path(__file__).resolve().parent
CAT=json.loads(src.CATALOG.read_text())


class SourceSelectionTests(unittest.TestCase):
    def test_rigol_documented_ovp_ocp_is_borrow_candidate_only(self):
        report=src.catalogue_review(CAT)
        self.assertEqual(report["preferred_borrow_candidate"],"rigol_dp832a_ch1")
        options={o["id"]:o for o in report["candidate_comparison"]}
        rigol=options["rigol_dp832a_ch1"]
        self.assertTrue(rigol["supplier_specification_fit_for_borrow_review"])
        self.assertFalse(rigol["physical_ovp_trip_observed"])
        self.assertFalse(report["physical_ready"])
        self.assertFalse(report["energization_authorized"])

    def test_siglent_spd3303xe_missing_ovp_is_rejected_for_strict_ceiling(self):
        report=src.catalogue_review(CAT)
        s=next(o for o in report["candidate_comparison"] if o["id"]=="siglent_spd3303xe_ch1")
        self.assertFalse(s["configured_ovp_capability_documented"])
        self.assertFalse(s["supplier_specification_fit_for_borrow_review"])
        self.assertIn("FAIL strict ceiling",s["review"])

    def test_spd4000x_family_without_selected_model_does_not_pass(self):
        r=src.catalogue_review(CAT)
        v=next(o for o in r["candidate_comparison"] if o["id"]=="siglent_spd4000x_family")
        self.assertTrue(v["configured_ovp_capability_documented"])
        self.assertFalse(v["exact_channel_reviewed"])
        self.assertFalse(v["supplier_specification_fit_for_borrow_review"])

    def test_unknown_or_duplicated_models_fail_closed(self):
        c=copy.deepcopy(CAT)
        c["source_candidates"].append(copy.deepcopy(c["source_candidates"][0]))
        with self.assertRaises(ValueError): src.catalogue_review(c)
        c=copy.deepcopy(CAT)
        c["source_candidates"][0]["id"]="unreviewed_source"
        with self.assertRaises(ValueError): src.catalogue_review(c)

    def test_vendor_ovp_fact_cannot_be_flipped_in_catalogue(self):
        c=copy.deepcopy(CAT)
        c["source_candidates"][1]["programmable_ovp"]=True
        with self.assertRaisesRegex(ValueError,"Vendor/OCP/OVP"):
            src.catalogue_review(c)

    def test_operating_limit_cannot_be_relaxed(self):
        for key,value in (
            ("max_j2_v",5.6),
            ("source_ovp_candidate_v",5.3),
            ("source_ocp_candidate_a",.7),
            ("min_worst_case_load_ohms",10),
            ("nominal_source_set_v",5.24),
            ("nominal_source_set_v",4.0),
        ):
            x=copy.deepcopy(CAT)
            x[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                src.catalogue_review(x)

    def test_1a_fuse_not_magically_cleared_by_catalogue(self):
        x=copy.deepcopy(CAT)
        x["fuse"]["can_clear_source_limited_sustained_0_65a"]=True
        with self.assertRaisesRegex(ValueError,"Fuse-link"):
            src.catalogue_review(x)

    def test_exact_fuse_link_mpn_has_not_been_selected(self):
        r=src.catalogue_review(CAT)
        self.assertFalse(r["dc_fuse_link_selected"])
        self.assertIn("NO CREDIT",r["fuse_role"])

    def test_incomplete_two_path_uncertainty_exceeds_software_threshold(self):
        m=src.metrology_bound(CAT)
        self.assertAlmostEqual(m["nominal_current_a_simulated"],5/12.075)
        self.assertGreater(m["incomplete_simple_additive_worst_case_pct"],2.2)
        self.assertGreater(m["hypothetical_shunt_dmm_fraction_pct"],.2)
        self.assertFalse(m["physical_0_75pct_discrimination_justified"])

    def test_missing_reference_calibration_remains_unproven(self):
        m=src.metrology_bound(CAT)
        self.assertFalse(m["one_percent_physical_agreement_justified"])
        self.assertTrue(any("certificates" in s for s in m["omissions"]))

    def test_cli_writes_a_new_nonphysical_report_exits_2(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/"report.json"
            proc=subprocess.run([sys.executable,str(HERE/"source_suitability.py"),
                                 "--out",str(out)],capture_output=True,text=True,timeout=10)
            self.assertEqual(proc.returncode,2,proc.stderr)
            report=json.loads(out.read_text())
            self.assertEqual(report["research_scope"],"VENDOR_DOCUMENTS_NOT_SOURCE_PROOF")
            self.assertFalse(report["fabrication_allowed"])
            self.assertEqual(report["catalogue_sha256"],src.sha(src.CATALOG))
            again=subprocess.run([sys.executable,str(HERE/"source_suitability.py"),
                                 "--out",str(out)],capture_output=True,text=True,timeout=10)
            self.assertNotEqual(again.returncode,0)

    def test_cli_tampered_supplier_flags_still_exit_2_and_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            cat=Path(folder)/"edited.json"
            x=copy.deepcopy(CAT)
            x["source_candidates"][1]["programmable_ovp"]=True
            cat.write_text(json.dumps(x))
            report=Path(folder)/"out.json"
            r=subprocess.run([sys.executable,str(HERE/"source_suitability.py"),
                              "--catalogue",str(cat),"--out",str(report)],
                             text=True,capture_output=True,timeout=10)
            self.assertEqual(r.returncode,2)
            j=json.loads(report.read_text())
            self.assertEqual(j["research_scope"],"INVALID_OR_CHANGED_INPUT_HOLD")


if __name__=="__main__":
    unittest.main()
