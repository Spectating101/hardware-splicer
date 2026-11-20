"""Revision- and source-bound real electrical branch + nominal probe fixture.

Oasis source was chosen for development after earlier experiments: this is
a reproducible *pilot*, NOT an untouched post-selection holdout evaluation.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess
from pathlib import Path
import freeze
from run_contour_cohort import call,sha,canon
HERE=Path(__file__).resolve().parent
CASE_ID="justbuchanan__oasis__pcb"
CAD_DEFAULT="/home/phyrexian/.local/share/hardware-splicer/cad-venv/bin/python"

def load(p):return json.loads(p.read_text())

def execute(corpus:Path,out:Path,cad_python:str):
    lock=load(HERE/"cases.lock.json")
    source=next(c for c in lock["cases"] if c["id"]==CASE_ID)
    if source["metadata"]["ref_drv"]!=0:raise ValueError("SOURCE_NOT_PREVIOUSLY_DRC_CLEAN")
    if subprocess.check_output(["git","-C",str(corpus),"rev-parse","HEAD"],text=True).strip()!=lock["corpus_commit"]:
        raise ValueError("CORPUS_REVISION_MISMATCH")
    if sha(freeze.blob(corpus,"manifest.json"))!=lock["manifest_sha256"]:
        raise ValueError("CORPUS_SOURCE_MANIFEST_MISMATCH")
    out.mkdir(parents=True,exist_ok=False)
    rounds=[]
    for index in (1,2):
        root=out/("round-"+str(index));root.mkdir()
        logs=root/"logs";logs.mkdir()
        src=root/"source";src.mkdir()
        for name,digest in source["files_sha256"].items():
            data=freeze.blob(corpus,"boards/"+CASE_ID+"/"+name)
            if sha(data)!=digest:raise ValueError("SOURCE_LOCK_CHANGED:"+name)
            (src/name).write_bytes(data)
        print("SIGNAL-ACCESS ROUND",index,flush=True)
        revision=root/"revised"
        call(["/usr/bin/python3",str(HERE/"track_tap.py"),
              "--source-dir",str(src),"--out",str(revision),
              "--limit","45"],logs,"track-tap",limit=180)
        tap=load(revision/"result.json")
        edited=revision/("trial-"+str(tap["candidate_attempts"]).zfill(3))/"board.kicad_pcb"
        tap_audit=root/"independent-track-audit.json"
        call(["/usr/bin/python3",str(HERE/"audit_track_tap.py"),
              "--source",str(src/"board.kicad_pcb"),
              "--revised",str(edited),
              "--receipt",str(revision/"result.json"),
              "--negative",str(root/"wrong-net-negative"),
              "--out",str(tap_audit)],logs,"track-audit")
        if load(tap_audit)["status"]!="PASS":raise ValueError("TRACK_AUDIT_NOT_PASS")
        layout=root/"source-contour.json"
        call(["/usr/bin/python3",str(HERE/"source_contour.py"),
              "--source",str(edited),"--out",str(layout)],logs,"source-contour")
        native=root/"independent-contour-native.json"
        call(["/usr/bin/python3",str(HERE/"audit_contour_native.py"),
              "--source",str(edited),"--layout",str(layout),
              "--out",str(native)],logs,"contour-native")
        models=root/"contour-cad"
        call([cad_python,str(HERE/"contour_cad.py"),
              "--source",str(edited),"--layout",str(layout),
              "--out",str(models)],logs,"contour-cad")
        contour_audit=root/"independent-contour-step.json"
        call([cad_python,str(HERE/"audit_contour_step.py"),
              "--native",str(native),"--study",str(models/"cad-receipt.json"),
              "--models",str(models),"--out",str(contour_audit)],logs,"contour-step")
        guide=root/"probe-access-cad"
        call([cad_python,str(HERE/"probe_guide_cad.py"),
              "--layout",str(layout),
              "--tap-receipt",str(revision/"result.json"),
              "--tap-audit",str(tap_audit),
              "--revised-pcb",str(edited),
              "--out",str(guide)],logs,"probe-cad")
        guide_audit=root/"independent-probe-cad.json"
        call([cad_python,str(HERE/"audit_probe_guide.py"),
              "--layout",str(layout),"--tap",str(revision/"result.json"),
              "--tap-audit",str(tap_audit),"--model",str(guide),
              "--revised-pcb",str(edited),
              "--out",str(guide_audit)],logs,"probe-audit")
        independent=load(guide_audit)
        if independent["status"]!="PASS":raise ValueError("INDEPENDENT_PROBE_AUDIT_FAILED")
        r={
            "source_id":CASE_ID,
            "source_sha256":tap["original_source_sha256"],
            "revised_sha256":tap["edited_sha256"],
            "new_net":tap["source_anchor_net"],
            "added_signal_testpoint":tap["new_testpoint"],
            "new_branch_start_mm":tap["branch_start_mm"],
            "new_branch_end_mm":tap["branch_end_mm"],
            "native_drc_errors":tap["native_drc"]["errors"],
            "native_drc_unconnected":tap["native_drc"]["unconnected"],
            "source_copper_preserved":load(tap_audit)["original_copper_items_preserved"],
            "one_new_branch_and_pad_verified":True,
            "wrong_net_negative_rejected":load(tap_audit)["wrong_net_negative"]["rejected"],
            "actual_source_cutouts":load(layout)["native_internal_edgecuts_cutouts"],
            "source_native_contour_audit":load(native)["status"],
            "native_source_to_step_audit":load(contour_audit)["status"],
            "new_probe_guide_step_audit":independent["status"],
            "new_probe_guide_local_mm":independent["model_hole_centre_mm"],
            "probe_plate_symmetric_difference_mm3":independent["actual_step_symmetric_difference_mm3"],
            "adversarial_checks":{k:v["rejected"] for k,v in independent["adversarial_controls"].items()},
            "physical_test_performed":False,
            "fabrication_authorized":False,
        }
        (root/"case-receipt.json").write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
        rounds.append(r)
    result={
        "schema":"hs.native_source_signal_access_proof.v1",
        "cohort_commit":lock["corpus_commit"],
        "selection_note":"Oasis board was chosen after seeing pilot performance; not an untouched post-tuning holdout",
        "original_source_frozen":True,
        "replay_runs":2,
        "same_revision_board_sha256":rounds[0]["revised_sha256"]==rounds[1]["revised_sha256"],
        "same_semantic_checks":canon(rounds[0])==canon(rounds[1]),
        "two_round_semantic_digest":[sha(canon(x).encode()) for x in rounds],
        "new_source_bound_electrical_route":all(x["one_new_branch_and_pad_verified"] for x in rounds),
        "independent_new_probe_cad_checks":all(x["new_probe_guide_step_audit"]=="PASS" for x in rounds),
        "wrong_net_negative_rejected":all(x["wrong_net_negative_rejected"] for x in rounds),
        "fabrication_authorized":False,"physical_test_performed":False,
    }
    result["pilot_pass"]=(result["same_revision_board_sha256"] and
        result["same_semantic_checks"] and result["new_source_bound_electrical_route"] and
        result["independent_new_probe_cad_checks"] and result["wrong_net_negative_rejected"])
    (out/"study-result.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,sort_keys=True,indent=2))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--corpus-repo",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--cad-python",default=CAD_DEFAULT)
    a=p.parse_args()
    result=execute(a.corpus_repo,a.out,a.cad_python)
    raise SystemExit(0 if result["pilot_pass"] else 2)
