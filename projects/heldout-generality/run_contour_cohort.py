"""Frozen 4-source + one revision held-out KiCad contour -> STEP pilot.

Two fresh runs. Records unsupported/failures, does not change HS live project
store or authorize fabrication. Original corpus source blobs are NOT committed.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
import freeze

HERE=Path(__file__).resolve().parent
REVISION=HERE/"functional-mount-evidence/pcb"
M3_SHA="f80212680c43319b987b3a0a5ab8332612eec2bf4361f2f5e0ba4a309b3939f3"
CAD_DEFAULT="/home/phyrexian/.local/share/hardware-splicer/cad-venv/bin/python"

def sha(data:bytes):return hashlib.sha256(data).hexdigest()
def canon(data):return json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=True)
def require(path):return json.loads(path.read_text())
def call(args,where,stem,limit=120):
    p=subprocess.run(args,cwd=where,capture_output=True,timeout=limit)
    (where/(stem+".stdout")).write_bytes(p.stdout)
    (where/(stem+".stderr")).write_bytes(p.stderr)
    if p.returncode!=0:
        raise RuntimeError(stem+" failed rc "+str(p.returncode)+" stderr="+p.stderr.decode(errors="replace")[-700:])

def snapshot(corpus:Path,case:dict,folder:Path):
    folder.mkdir(parents=True)
    for name,expected in case["files_sha256"].items():
        bytes_=freeze.blob(corpus,"boards/"+case["id"]+"/"+name)
        if sha(bytes_)!=expected:raise ValueError("CORPUS_SOURCE_CHANGED:"+name)
        (folder/name).write_bytes(bytes_)

def evaluate(board_folder:Path,case_dir:Path,cad_python:str,source:dict):
    src=board_folder/"board.kicad_pcb"
    log=case_dir/"commands";log.mkdir()
    drc=case_dir/"native-drc.json"
    call(["kicad-cli","pcb","drc","--severity-error","--format","json",
          "--exit-code-violations","-o",str(drc),str(src)],log,"drc")
    d=require(drc)
    if d["violations"] or d["unconnected_items"]:
        raise ValueError("SOURCE_PCB_DRC_HAS_ERRORS_OR_UNCONNECTED")
    layout=case_dir/"native-layout.json"
    call(["/usr/bin/python3",str(HERE/"source_contour.py"),"--source",str(src),
          "--out",str(layout)],log,"extract")
    native=case_dir/"independent-native-audit.json"
    call(["/usr/bin/python3",str(HERE/"audit_contour_native.py"),"--source",str(src),
          "--layout",str(layout),"--out",str(native)],log,"source-audit")
    models=case_dir/"model"
    call([cad_python,str(HERE/"contour_cad.py"),"--layout",str(layout),
          "--source",str(src),"--out",str(models)],log,"cad",limit=150)
    step=case_dir/"independent-step-audit.json"
    call([cad_python,str(HERE/"audit_contour_step.py"),"--native",str(native),
          "--study",str(models/"cad-receipt.json"),"--models",str(models),
          "--out",str(step)],log,"step-audit",limit=150)
    geo=require(step);lay=require(layout);cad=require(models/"cad-receipt.json")
    if geo["status"]!="PASS" or cad["fabrication_authorized"]:
        raise ValueError("INDEPENDENT_CAD_CLAIM_INVALID")
    return {"id":source["id"],"source_family":source["repo"],
            "source_board_sha256":sha(src.read_bytes()),
            "source_outline_vertices":lay["source_outline_vertices"],
            "source_cutouts":lay["native_internal_edgecuts_cutouts"],
            "source_mounts":len(lay["source_mounts"]),
            "mount_strategy":lay["mounting_strategy"],
            "source_polygon_area_mm2":lay["native_board_polygon_area_mm2"],
            "cad_nominal_board_volume_mm3":cad["cad"]["nominal-unpopulated-PCB"]["volume_mm3"],
            "nominal_pocket_interference_mm3":geo["nominal_pocket_interference_mm3"],
            "native_drc_errors":len(d["violations"]),
            "independent_source_audit":"PASS",
            "independent_step_audit":"PASS",
            "negative_controls_pass":all(v["rejected"] for v in geo["negative_controls"].values()),
            "fabrication_authorized":False,"physical_measurement":False}

def run(corpus:Path,out:Path,cad_python:str):
    lock=require(HERE/"cases.lock.json")
    if lock["corpus_commit"]!=freeze.CORPUS_REV:raise ValueError("COHORT_REVISION_MISMATCH")
    if sha(freeze.blob(corpus,"manifest.json"))!=lock["manifest_sha256"]:
        raise ValueError("SOURCE_MANIFEST_MISMATCH")
    if subprocess.check_output(["git","-C",str(corpus),"rev-parse","HEAD"],text=True).strip()!=freeze.CORPUS_REV:
        raise ValueError("CORPUS_WRONG_CHECKOUT")
    cohort=[case for case in lock["cases"] if case["metadata"]["ref_drv"]==0]
    if len(cohort)!=4:raise ValueError("EXPECTED_FOUR_FIXED_CLEAN_SOURCES")
    if sha((REVISION/"board.kicad_pcb").read_bytes())!=M3_SHA:
        raise ValueError("STORED_M3_REVISION_CHANGED")
    out.mkdir(parents=True,exist_ok=False)
    all_results=[]
    for n in (1,2):
        round_dir=out/("round-"+str(n));round_dir.mkdir()
        result=[]
        for case in cohort:
            print("ROUND",n,"SOURCE",case["id"],flush=True)
            path=round_dir/case["id"];path.mkdir()
            src=path/"source"
            snapshot(corpus,case,src)
            try:
                current=evaluate(src,path,cad_python,
                  {"id":case["id"],"repo":case["metadata"]["repo"]})
                current["status"]="PASS_DIGITAL_ONLY"
            except Exception as exc:
                current={"id":case["id"],"status":"BLOCKED_DIGITAL",
                         "reason":str(exc),"fabrication_authorized":False}
            result.append(current)
        # Extra derivative: a *revision of an already frozen source*, not
        # replacement of a difficult original case.
        path=round_dir/"protolux-M3-derived-revision";path.mkdir()
        snap=path/"source";snap.mkdir()
        for name in ("board.kicad_pcb","board.kicad_pro"):
            (snap/name).write_bytes((REVISION/name).read_bytes())
        try:
            current=evaluate(snap,path,cad_python,
                             {"id":"protolux-M3-derived-revision",
                              "repo":"protolux-electronics/trellis_core"})
            current["status"]="PASS_DIGITAL_ONLY"
        except Exception as exc:
            current={"id":"protolux-M3-derived-revision","status":"BLOCKED_DIGITAL",
                     "reason":str(exc),"fabrication_authorized":False}
        result.append(current)
        (round_dir/"verdicts.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        all_results.append(result)
    first=all_results[0]
    original=next(c for c in first if c["id"]=="protolux-electronics__trellis_core__trellis_core")
    updated=next(c for c in first if c["id"]=="protolux-M3-derived-revision")
    revision_link=(original.get("source_outline_vertices")==updated.get("source_outline_vertices")
                   and original.get("source_polygon_area_mm2")==updated.get("source_polygon_area_mm2")
                   and original.get("source_mounts")==4 and updated.get("source_mounts")==4
                   and original.get("source_board_sha256")!=updated.get("source_board_sha256")
                   and original.get("cad_nominal_board_volume_mm3")!=updated.get("cad_nominal_board_volume_mm3"))
    aggregate={
        "schema":"hs.heldout_contour_generalization.v1",
        "frozen_original_board_count":len(cohort),
        "source_revisions_tested":len(first),
        "original_sources_source_to_step_pass":sum(c["status"]=="PASS_DIGITAL_ONLY" for c in first[:4]),
        "derived_revision_source_to_step_pass":updated["status"]=="PASS_DIGITAL_ONLY",
        "invalid_or_blocked_results":[{"id":r["id"],"reason":r["reason"]}
                                     for r in first if r["status"]!="PASS_DIGITAL_ONLY"],
        "two_round_semantic_sha256":[sha(canon(x).encode()) for x in all_results],
        "fresh_replay_identical":canon(all_results[0])==canon(all_results[1]),
        "revised_mounting_geometry_propagates":revision_link,
        "independent_physical_fit_validation":False,
        "physical_measurement":False,"fabrication_authorized":False,
    }
    aggregate["pilot_pass"]=(aggregate["original_sources_source_to_step_pass"]==4 and
                             aggregate["derived_revision_source_to_step_pass"] and
                             aggregate["fresh_replay_identical"] and
                             aggregate["revised_mounting_geometry_propagates"])
    (out/"study-result.json").write_text(json.dumps(aggregate,sort_keys=True,indent=2)+"\n")
    print(json.dumps(aggregate,indent=2))
    return aggregate

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--corpus-repo",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--cad-python",default=CAD_DEFAULT)
    a=p.parse_args()
    result=run(a.corpus_repo,a.out,a.cad_python)
    raise SystemExit(0 if result["pilot_pass"] else 2)
