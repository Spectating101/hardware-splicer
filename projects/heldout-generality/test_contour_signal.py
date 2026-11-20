"""Offline reproducibility/authority and actual STEP reimport tests of v3 package."""
from __future__ import annotations
import copy,hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
import audit_contour_step,audit_probe_guide

HERE=Path(__file__).resolve().parent
ZIP=HERE/"hs-heldout-contour-and-signal-v3.zip"
ROOT=HERE/"contour-routing-evidence"
def read(p):return json.loads(p.read_text())
def sha(b):return hashlib.sha256(b).hexdigest()

class NativeContourSignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort=read(HERE/"cases.lock.json")
        cls.contour=read(ROOT/"reports/contour-study-result.json")
        cls.signal=read(ROOT/"reports/signal-study-result.json")
        cls.manifest=read(ROOT/"MANIFEST.json")
        cls.temp=tempfile.TemporaryDirectory(prefix="hs-v3-package-audit-")
        with zipfile.ZipFile(ZIP) as z:
            z.extractall(cls.temp.name)
        cls.package=Path(cls.temp.name)/"contour-routing-evidence"

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_original_cohort_not_replaced(self):
        cases={x["id"] for x in self.cohort["cases"] if x["metadata"]["ref_drv"]==0}
        self.assertEqual(len(cases),4)
        a=read(ROOT/"reports/contour-round-1-verdicts.json")
        self.assertEqual({x["id"] for x in a[:4]},cases)
        self.assertTrue(all(x["independent_step_audit"]=="PASS" for x in a))

    def test_general_shapes_and_mounts(self):
        expected={
            "dnlbauer__corax-keyboard__keyboard_5db1e9":(85,1,0,"non-clamping-edge-nest"),
            "justbuchanan__oasis__pcb":(39,1,1,"non-clamping-edge-nest"),
            "rniwase__sdtv2csi__sdtv2csi":(40,0,0,"non-clamping-edge-nest"),
            "protolux-electronics__trellis_core__trellis_core":(64,0,4,"source-hole-registration")
        }
        for case,(vertices,holes,mounts,strategy) in expected.items():
            d=read(self.package/"cases"/case/"independent-step-audit.json")
            self.assertEqual((d["source_outline_vertices"],d["source_internal_cutouts_preserved"],
                              d["source_mounts_preserved"],d["mount_strategy"]),
                             (vertices,holes,mounts,strategy))
            self.assertEqual(d["nominal_board_symmetric_difference_mm3"],[0.0,0.0])
            self.assertEqual(d["nominal_pocket_interference_mm3"],0.0)

    def test_contour_two_round_replay(self):
        self.assertEqual(self.contour["original_sources_source_to_step_pass"],4)
        self.assertTrue(self.contour["derived_revision_source_to_step_pass"])
        self.assertEqual(self.contour["source_revisions_tested"],5)
        self.assertTrue(self.contour["fresh_replay_identical"])
        self.assertEqual(len(set(self.contour["two_round_semantic_sha256"])),1)
        self.assertEqual(read(ROOT/"reports/contour-round-1-verdicts.json"),
                         read(ROOT/"reports/contour-round-2-verdicts.json"))

    def test_revised_source_bore_propagation(self):
        a=read(self.package/"cases/protolux-electronics__trellis_core__trellis_core/independent-native-audit.json")
        b=read(self.package/"cases/protolux-M3-derived-revision/independent-native-audit.json")
        self.assertEqual([m["drill_mm"] for m in a["source_mounts"]],[2.7]*4)
        self.assertEqual([m["drill_mm"] for m in b["source_mounts"]],[3.2]*4)
        self.assertEqual(a["source_outer_exact_xy"],b["source_outer_exact_xy"])

    def test_actual_reopened_source_contour_steps(self):
        for cid in ("dnlbauer__corax-keyboard__keyboard_5db1e9",
                    "protolux-M3-derived-revision"):
            folder=self.package/"cases"/cid
            result=audit_contour_step.audit(
                read(folder/"independent-native-audit.json"),
                read(folder/"cad-receipt.json"),folder/"models")
            self.assertEqual(result["status"],"PASS")
            self.assertFalse(result["fabrication_authorized"])

    def test_signal_changed_actual_board_and_preserved_copper(self):
        self.assertTrue(self.signal["pilot_pass"])
        self.assertTrue(self.signal["same_revision_board_sha256"])
        self.assertEqual(len(set(self.signal["two_round_semantic_digest"])),1)
        track=read(self.package/"signal-oasis/reports/independent-track-audit.json")
        self.assertEqual(track["original_copper_items_preserved"],263)
        self.assertEqual(track["original_pad_identities_preserved"],173)
        self.assertEqual(track["new_signal_branch_count"],1)
        self.assertEqual(track["new_exposed_testpoints"],1)
        self.assertEqual(sha((self.package/"signal-oasis/pcb/board.kicad_pcb").read_bytes()),
                         track["revised_sha256"])

    def test_wrong_net_injection_is_rejected(self):
        drc=read(self.package/"signal-oasis/reports/negative-wrong-net-drc.json")
        self.assertTrue(drc["violations"] or drc["unconnected_items"])
        self.assertTrue(self.signal["wrong_net_negative_rejected"])

    def test_probed_aperture_geometry_is_source_bound(self):
        path=self.package/"signal-oasis"
        t=read(path/"reports/native-routing-receipt.json")
        n=read(path/"reports/independent-track-audit.json")
        l=read(path/"reports/source-contour.json")
        model=read(path/"probe-access-cad/probe-plate-receipt.json")
        answer=audit_probe_guide.inspect(l,n["revised_sha256"],t,n,model,path/"probe-access-cad")
        self.assertEqual(answer["status"],"PASS")
        self.assertEqual(answer["source_cutouts_preserved"],1)
        self.assertEqual(answer["actual_step_symmetric_difference_mm3"],[0.,0.])

    def test_reject_stale_probe_source_revision(self):
        path=self.package/"signal-oasis"
        t=read(path/"reports/native-routing-receipt.json")
        n=read(path/"reports/independent-track-audit.json")
        l=read(path/"reports/source-contour.json")
        model=read(path/"probe-access-cad/probe-plate-receipt.json")
        bad=copy.deepcopy(model)
        bad["source_edited_pcb_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"CAD_SOURCE_REVISION_STALE"):
            audit_probe_guide.inspect(l,n["revised_sha256"],t,n,bad,path/"probe-access-cad")

    def test_source_licenses_present(self):
        for child in (self.package/"cases").iterdir():
            self.assertTrue((child/"attribution/SOURCE.json").is_file(),child)
            self.assertTrue(any(f.name.startswith("LICENSE") for f in (child/"attribution").iterdir()),child)
        self.assertTrue((self.package/"signal-oasis/attribution/LICENSE").is_file())

    def test_archive_bytes_and_authority_boundaries(self):
        with zipfile.ZipFile(ZIP) as z:
            for name,digest in self.manifest["content_sha256"].items():
                self.assertEqual(sha(z.read("contour-routing-evidence/"+name)),digest,name)
        for result in (self.contour,self.signal):
            self.assertFalse(result["physical_measurement"] if "physical_measurement" in result
                             else result["physical_test_performed"])
            self.assertFalse(result["fabrication_authorized"])
        self.assertTrue(self.signal["selection_note"].find("not an untouched")>=0)

if __name__=="__main__":
    unittest.main(verbosity=2)
