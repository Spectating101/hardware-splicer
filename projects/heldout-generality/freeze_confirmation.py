"""Precommit a second, untouched electrical cohort AFTER fixing legacy KiCad UUIDs.

This excludes every repository from the prior HS original cohort and from
the first *failed-repeatability* post-tuning electrical holdout.
Selection is metadata-only with a new deterministic seed.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess
from pathlib import Path
import freeze

SEED="hs-confirmatory-after-uuid-fix-20261120-v2"
def sha(data):return hashlib.sha256(data).hexdigest()

def select(manifest,original,first):
    exclude={c["metadata"]["repo"] for c in original["cases"]}
    exclude|={c["origin_repo"] for c in first["cases"]}
    possible=[row for row in manifest
              if row["repo"] not in exclude and row["ref_drv"]==0 and row["ref_open"]==0
              and row["copper_layers"] in (2,4) and row["parts"]>=5
              and row["pads"]<=360 and row["segments"]<=700]
    result=[]
    for copper_layers in (2,4):
        choices=sorted([r for r in possible if r["copper_layers"]==copper_layers],
                       key=lambda r:sha((SEED+"|"+r["id"]).encode()))
        for row in choices:
            if row["repo"] in exclude:continue
            result.append(row)
            exclude.add(row["repo"])
            if sum(p["copper_layers"]==copper_layers for p in result)==3:break
        if sum(p["copper_layers"]==copper_layers for p in result)!=3:
            raise ValueError("six independent confirmatory boards unavailable")
    return result

def freeze_cohort(corpus,old_path,first_path,out):
    if out.exists():raise FileExistsError("confirmation already registered")
    old=json.loads(old_path.read_text())
    first=json.loads(first_path.read_text())
    revision=subprocess.check_output(
        ["git","-C",str(corpus),"rev-parse","HEAD"],text=True).strip()
    if revision!=old["corpus_commit"] or revision!=first["corpus_git_commit"]:
        raise ValueError("upstream corpus mismatch")
    manifest_bytes=freeze.blob(corpus,"manifest.json")
    if sha(manifest_bytes)!=old["manifest_sha256"]:
        raise ValueError("source manifest mismatch")
    cases=[]
    for row in select(json.loads(manifest_bytes),old,first):
        prefix="boards/"+row["id"]+"/"
        names=subprocess.check_output(
            ["git","-C",str(corpus),"ls-tree","-r","--name-only",revision,"--",prefix],text=True).splitlines()
        required=("board.kicad_pcb","board.kicad_pro","SOURCE.json")
        files=[x for x in (*required,"board.kicad_dru") if prefix+x in names]
        if not all(n in files for n in required):raise ValueError("incomplete source")
        source=json.loads(freeze.blob(corpus,prefix+"SOURCE.json"))
        if source["repo"]!=row["repo"] or source["commit"]!=row["commit"]:
            raise ValueError("upstream source record mismatch")
        lic=source.get("licence_file")
        if lic and prefix+lic in names:files.append(lic)
        cases.append({"id":row["id"],"metadata":row,"origin_repo":row["repo"],
                      "origin_commit":row["commit"],"source":source,
                      "sha256":{n:sha(freeze.blob(corpus,prefix+n)) for n in files}})
    value={
        "schema":"hs.postfix_electrical_confirmatory_v2",
        "board_count":6,
        "original_corpus_commit":revision,
        "corpus_git_commit":revision,
        "corpus_manifest_sha256":sha(manifest_bytes),
        "prior_training_cohort_sha256":sha(old_path.read_bytes()),
        "initial_holdout_cohort_sha256":sha(first_path.read_bytes()),
        "selection_seed":SEED,
        "method":"SHA256-seeded first 3 clean boards from independent repos per 2/4 copper layers, max 360 pads/700 segments, exclude both previous cohorts and all original source repos",
        "locked_before_running_confirmation":True,
        "cases":cases,
        "physical_validation":False
    }
    out.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")
    return value

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--corpus",type=Path,required=True)
    p.add_argument("--old",type=Path,default=Path(__file__).with_name("cases.lock.json"))
    p.add_argument("--first",type=Path,default=Path(__file__).with_name("posttuning-cases.lock.json"))
    p.add_argument("--out",type=Path,default=Path(__file__).with_name("postfix-confirmation.lock.json"))
    a=p.parse_args()
    r=freeze_cohort(a.corpus,a.old,a.first,a.out)
    print(json.dumps({"cases":[c["id"] for c in r["cases"]],
                      "source_repositories":[c["origin_repo"] for c in r["cases"]],
                      "seed":r["selection_seed"]},indent=2))
