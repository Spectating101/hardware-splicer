"""Frozen four-board native contour + source-derived STEP generality evaluation.

No editing PCB, no fabricated claim, no selected-case replacement. The same
four originally DRC-clean cases from PR #361/366 are executed twice.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
import freeze
from run import verify_lock
from outline_source import extract

HERE=Path(__file__).resolve().parent
def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(",",":"))
def command(args,folder,label):
    r=subprocess.run(args,cwd=folder,capture_output=True,timeout=100,check=False)
    (folder/(label+".stdout")).write_bytes(r.stdout)
    (folder/(label+".stderr")).write_bytes(r.stderr)
    if r.returncode:
        raise RuntimeError(label+" failed: "+r.stderr.decode(errors="replace")[-300:])

def main(corpus:Path,out:Path,cad_python:str):
    locked=json.loads((HERE/"cases.lock.json").read_text())
    verify_lock(corpus,locked)
    clean=[c for c in locked["cases"] if c["metadata"]["ref_drv"]==0]
    if len(clean)!=4 or len({c["metadata"]["repo"] for c in clean})!=4:
        raise ValueError("ORIGINAL_FROZEN_SAMPLE_NOT_4_DISTINCT_REPOS")
    out.mkdir(parents=True,exist_ok=False)
    rounds=[]
    for i in (1,2):
        directory=out/("round-"+str(i));directory.mkdir()
        rows=[]
        for case in clean:
            id=case["id"]
            cwd=directory/id;cwd.mkdir()
            original=cwd/"original";original.mkdir()
            for name,expected in case["files_sha256"].items():
                data=freeze.blob(corpus,"boards/"+id+"/"+name)
                if digest(data)!=expected:raise ValueError("INPUT_BYTES_DIFFER_FROM_LOCK")
                (original/name).write_bytes(data)
            board=original/"board.kicad_pcb"
            print("ROUND",i,id,flush=True)
            try:
                source=extract(board)
                (cwd/"source-outline.json").write_text(json.dumps(source,sort_keys=True,indent=2)+"\n")
                model_dir=cwd/"models"
                command([cad_python,str(HERE/"outline_cad.py"),
                         "--outline",str(cwd/"source-outline.json"),
                         "--board",str(board),"--out",str(model_dir)],cwd,"build")
                command([cad_python,str(HERE/"audit_outline_cad.py"),
                         "--source",str(cwd/"source-outline.json"),
                         "--models",str(model_dir),"--board",str(board),
                         "--out",str(cwd/"independent-audit.json")],cwd,"audit")
                receipt=json.loads((model_dir/"design-receipt.json").read_text())
                audit=json.loads((cwd/"independent-audit.json").read_text())
                if audit["status"]!="PASS" or not all(
                    q["rejected"] for q in audit["negative_controls"].values()):
                    raise ValueError("INDEPENDENT_VERIFICATION_FAILED")
                result={"source_id":id,"status":"SOURCE_CONTOUR_AND_STEP_AUDITED",
                        "original_board_sha256":source["original_pcb_sha256"],
                        "vertices":len(source["edge_cut_contour"]),
                        "cutouts":len(source["internal_cutouts"]),
                        "mounts":len(source["mounting_holes"]),
                        "strategy":source["strategy"],
                        "source_area_mm2":audit["planar_polygon_area_mm2"],
                        "nominal_collision_mm3":audit["nominal_unpopulated_board_tray_overlap_mm3"],
                        "adversarial_controls_rejected":len(audit["negative_controls"]),
                        "fabrication_authorized":False}
            except (ValueError,RuntimeError) as error:
                result={"source_id":id,"status":"BLOCKED",
                        "reason":str(error),"fabrication_authorized":False}
            (cwd/"case-verdict.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
            rows.append(result)
        (directory/"summary.json").write_text(json.dumps(rows,indent=2,sort_keys=True)+"\n")
        rounds.append(rows)
    hashes=[digest(canonical(row).encode()) for row in rounds]
    count=sum(r["status"]=="SOURCE_CONTOUR_AND_STEP_AUDITED" for r in rounds[0])
    result={"schema":"hs.heldout_outline_generality.v1",
            "source_cohort_lock_sha256":digest((HERE/"cases.lock.json").read_bytes()),
            "source_corpus_revision":locked["corpus_commit"],
            "total_frozen_clean_boards":4,
            "distinct_original_repositories":4,
            "independently_audited_source_to_STEP":count,
            "blocked":4-count,"rounds":2,"semantic_hashes":hashes,
            "same_semantic_findings":hashes[0]==hashes[1],
            "third_party_source_board_modification":"NONE_FOR_THIS_OUTLINE_TRAY_EXPERIMENT",
            "prior_m3_edit_evidence":"SEPARATE_PR_366",
            "generalized_electrical_routing":"NOT_DEMONSTRATED",
            "physical_validation":"NOT_PERFORMED",
            "fabrication_authorized":False}
    result["pass_bounded_digital_gate"]=count==4 and hashes[0]==hashes[1]
    (out/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--corpus",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--cad-python",default="/home/phyrexian/.local/share/hardware-splicer/cad-venv/bin/python")
    a=p.parse_args()
    r=main(a.corpus,a.out,a.cad_python)
    raise SystemExit(0 if r["pass_bounded_digital_gate"] else 2)
