"""Execute the next HS held-out PCB->functional drill revision->STEP fixture trial.

Runs all FOUR pre-frozen originally clean boards, including unsupported cases.
No new case selection, no physical authority, no modification of active HS.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
import freeze,mount_variant

HERE=Path(__file__).resolve().parent
CAD_DEFAULT="/home/phyrexian/.local/share/hardware-splicer/cad-venv/bin/python"

def sha(data):return hashlib.sha256(data).hexdigest()
def canon(data):return json.dumps(data,sort_keys=True,separators=(",",":"))
def launch(cmd,out,stem,timeout=120):
    result=subprocess.run(cmd,capture_output=True,timeout=timeout,check=False)
    (out/(stem+".stdout.txt")).write_bytes(result.stdout)
    (out/(stem+".stderr.txt")).write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError("CHECK_PROCESS_FAILED:"+stem+" rc="+str(result.returncode)+
                           " stderr="+result.stderr.decode(errors="replace")[-400:])
    return result

def run(corpus:Path,output:Path,cad_python:str,rounds:int=2):
    cohort=json.loads((HERE/"cases.lock.json").read_text())
    if rounds!=2:raise ValueError("full acceptance requires exactly two rounds")
    original_sha=sha((HERE/"cases.lock.json").read_bytes())
    head=subprocess.check_output(["git","-C",str(corpus),"rev-parse","HEAD"],text=True).strip()
    if head!=cohort["corpus_commit"]:raise ValueError("CORPUS_WRONG_COMMIT")
    if sha(freeze.blob(corpus,"manifest.json"))!=cohort["manifest_sha256"]:
        raise ValueError("CORPUS_MANIFEST_HASH_MISMATCH")
    eligible=[c for c in cohort["cases"] if c["metadata"]["ref_drv"]==0]
    if len(eligible)!=4 or len({c["metadata"]["repo"] for c in eligible})!=4:
        raise ValueError("PREDECLARED_CLEAN_COHORT_NOT_FOUR_PROJECTS")
    output.mkdir(parents=True,exist_ok=False)
    round_data=[]
    for n in range(1,3):
        d=output/("round-"+str(n));d.mkdir()
        records=[]
        for c in eligible:
            tag=c["id"];specdir=d/tag;specdir.mkdir()
            source=specdir/"source";source.mkdir()
            files={}
            for name,expected_hash in sorted(c["files_sha256"].items()):
                data=freeze.blob(corpus,"boards/"+tag+"/"+name)
                if sha(data)!=expected_hash:raise ValueError("ORIGINAL_BYTES_CHANGED:"+tag+"/"+name)
                (source/name).write_bytes(data)
                files[name]=expected_hash
            print("ROUND",n,"SOURCE",tag,flush=True)
            new=specdir/"revision"
            try:
                edit=mount_variant.execute(source,new)
            except ValueError as exc:
                verdict={"id":tag,"status":"BLOCKED_UNSUPPORTED_SOURCE",
                         "reason":str(exc),"source_file_sha256":files["board.kicad_pcb"],
                         "fabrication_authorized":False}
            else:
                models=specdir/"cad"
                launch([cad_python,str(HERE/"build_mount_fixture.py"),
                        "--edit-receipt",str(new/"edit-receipt.json"),
                        "--edited-pcb",str(new/"board.kicad_pcb"),
                        "--out",str(models)],specdir,"cad")
                launch(["/usr/bin/python3",str(HERE/"audit_native_mount.py"),
                        "--source",str(source/"board.kicad_pcb"),
                        "--edited",str(new/"board.kicad_pcb"),
                        "--receipt",str(new/"edit-receipt.json"),
                        "--out",str(new/"native-independent-audit.json")],specdir,"audit-native")
                launch([cad_python,str(HERE/"audit_mount_step.py"),
                        "--models",str(models),
                        "--native-audit",str(new/"native-independent-audit.json"),
                        "--edit-receipt",str(new/"edit-receipt.json"),
                        "--out",str(models/"independent-step-audit.json")],specdir,"audit-step")
                native=json.loads((new/"native-independent-audit.json").read_text())
                step=json.loads((models/"independent-step-audit.json").read_text())
                if native["status"]!="PASS" or step["status"]!="PASS":
                    raise ValueError("INDEPENDENT_DIGITAL_AUDIT_NOT_PASS")
                verdict={"id":tag,"status":"SOURCE_BOUND_DIGITAL_DESIGN",
                         "source_file_sha256":files["board.kicad_pcb"],
                         "revised_board_sha256":edit["edited_sha256"],
                         "revised_m3_holes":len(edit["revised_holes"]),
                         "original_pad_and_copper_preserved":True,
                         "native_drc_errors":edit["native_drc_error_count"],
                         "native_drc_warnings":edit["native_drc_warning_count"],
                         "native_drc_added_footprint_warnings":"REVIEW_HOLD",
                         "step_hole_audit":step["status"],
                         "negative_controls":{k:v["rejected"] for k,v in step["negative_controls"].items()},
                         "shape_semantics":step["source_dimension_mm"],
                         "fabrication_authorized":False}
            (specdir/"case-verdict.json").write_text(json.dumps(verdict,indent=2,sort_keys=True)+"\n")
            records.append(verdict)
        (d/"summary.json").write_text(json.dumps(records,indent=2,sort_keys=True)+"\n")
        round_data.append(records)
    identical=canon(round_data[0])==canon(round_data[1])
    success=[r for r in round_data[0] if r["status"]=="SOURCE_BOUND_DIGITAL_DESIGN"]
    blocked=[r for r in round_data[0] if r["status"]=="BLOCKED_UNSUPPORTED_SOURCE"]
    result={"schema":"hs.heldout_functional_mount_study.v1",
            "corpus_revision":cohort["corpus_commit"],
            "cohort_lock_sha256":original_sha,
            "originally_clean_cases_attempted":len(eligible),
            "successful_source_to_verified_STEP":len(success),
            "explicitly_blocked_unsupported":len(blocked),
            "successful_source_ids":[x["id"] for x in success],
            "blocked_source_ids":[x["id"] for x in blocked],
            "rounds":2,"semantic_round_hashes":[sha(canon(x).encode()) for x in round_data],
            "exact_semantic_replay":identical,
            "source_footprint_library_mismatch_hold":True,
            "real_hardware_measurement":"NOT_PERFORMED",
            "general_board_editing_proven":False,
            "fabrication_authorized":False}
    result["pilot_pass"]=identical and len(success)>=1 and len(blocked)+len(success)==len(eligible)
    (output/"study-result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--corpus-repo",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--cad-python",default=CAD_DEFAULT)
    a=p.parse_args()
    r=run(a.corpus_repo,a.out,a.cad_python)
    raise SystemExit(0 if r["pilot_pass"] else 2)
