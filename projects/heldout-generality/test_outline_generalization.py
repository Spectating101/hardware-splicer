"""Frozen-source and independently audited STEP generality regression checks."""
from __future__ import annotations
import copy,hashlib,json,sys,unittest
from pathlib import Path
import audit_outline_cad

HERE=Path(__file__).resolve().parent
E=HERE/"outline-generality-evidence"

def read(path):return json.loads(path.read_text())

class GeneralityEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock=read(HERE/"cases.lock.json")
        cls.aggregate=read(E/"result.json")

    def test_frozen_four_nonopportunistic(self):
        clean={r["id"] for r in self.lock["cases"] if r["metadata"]["ref_drv"]==0}
        self.assertEqual(len(clean),4)
        present={p.name for p in E.iterdir() if p.is_dir()}
        self.assertEqual(clean,present)

    def test_two_rounds_same_semantic_result(self):
        a=self.aggregate
        self.assertEqual(a["independently_audited_source_to_STEP"],4)
        self.assertTrue(a["pass_bounded_digital_gate"])
        self.assertTrue(a["same_semantic_findings"])
        self.assertEqual(len(set(a["semantic_hashes"])),1)
        self.assertFalse(a["fabrication_authorized"])

    def test_cutouts_are_not_discarded(self):
        cutouts={p.name:len(read(p/"source-outline.json")["internal_cutouts"])
                 for p in E.iterdir() if p.is_dir()}
        self.assertEqual(sorted(cutouts.values()),[0,0,1,1])

    def test_no_fake_retention_or_power_approval(self):
        for folder in E.iterdir():
            if not folder.is_dir():continue
            source=read(folder/"source-outline.json")
            model=read(folder/"models/design-receipt.json")
            audit=read(folder/"independent-audit.json")
            self.assertFalse(model["fab_authority"])
            self.assertEqual(model["standoff_posts_modeled"],0)
            self.assertEqual(model["source_strategy"],source["strategy"])
            self.assertTrue(model["tray_is_nonretaining"])
            self.assertEqual(audit["status"],"PASS")
            self.assertEqual(audit["nominal_unpopulated_board_tray_overlap_mm3"],0)
            self.assertTrue(all(x["rejected"] for x in audit["negative_controls"].values()))

    def test_independent_reimported_geometry(self):
        for folder in E.iterdir():
            if not folder.is_dir():continue
            source=read(folder/"source-outline.json")
            # Standalone auditor is a separate module and never calls builder.
            native=folder/"original-board.kicad_pcb"
            audited=audit_outline_cad.audit(source,folder/"models",native)
            self.assertEqual(audited["status"],"PASS")

    def test_stale_source_digest_rejected(self):
        sample=next(p for p in E.iterdir() if p.is_dir())
        src=read(sample/"source-outline.json")
        src["original_pcb_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"STALE_PCB_SOURCE"):
            audit_outline_cad.audit(src,sample/"models",sample/"original-board.kicad_pcb")

    def test_forged_geometry_area_rejected(self):
        sample=next(p for p in E.iterdir() if p.is_dir())
        src=read(sample/"source-outline.json")
        src["edge_cut_contour"][0][0]+=50
        src["edge_cut_contour"][0][1]+=30
        with self.assertRaises(ValueError):
            audit_outline_cad.audit(src,sample/"models",sample/"original-board.kicad_pcb")

    def test_source_hashes_and_reproducible_evidence(self):
        original={r["id"]:r for r in self.lock["cases"]}
        for folder in E.iterdir():
            if not folder.is_dir():continue
            digest=hashlib.sha256((folder/"original-board.kicad_pcb").read_bytes()).hexdigest()
            self.assertEqual(digest,original[folder.name]["files_sha256"]["board.kicad_pcb"])

if __name__=="__main__":
    unittest.main(verbosity=2)
