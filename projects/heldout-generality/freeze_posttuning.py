"""Freeze an *untouched after-tuning* electrical rework evaluation cohort.

Selection uses metadata only, no execution results, and excludes all original
source repositories used in PRs #361/#366/#371. Never reselect after testing.
"""
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path
import freeze

SEED="hs-post-tuning-20261120-independent-v1"
PER_LAYER=3
MAX_PADS=360
MAX_SEGMENTS=700

def hash_bytes(b):return hashlib.sha256(b).hexdigest()
def choose(manifest,prior):
    excluded={c["metadata"]["repo"] for c in prior["cases"]}
    eligible=[m for m in manifest if m["repo"] not in excluded
              and m["ref_drv"]==0 and m["ref_open"]==0
              and m["copper_layers"] in (2,4)
              and 5<=m["parts"] and m["pads"]<=MAX_PADS
              and m["segments"]<=MAX_SEGMENTS]
    selected=[];reps=set(excluded)
    for layer in (2,4):
        choices=sorted((m for m in eligible if m["copper_layers"]==layer),
                       key=lambda m:hash_bytes((SEED+"|"+m["id"]).encode()))
        count=0
        for m in choices:
            if m["repo"] in reps:continue
            selected.append(m)
            reps.add(m["repo"])
            count+=1
            if count==PER_LAYER:break
        if count!=PER_LAYER:raise ValueError("stratum unavailable")
    return selected

def lock(corpus:Path,prior_lock:Path,target:Path):
    if target.exists():raise FileExistsError("refusing to overwrite frozen cohort")
    prior=json.loads(prior_lock.read_text())
    head=subprocess.check_output(
        ["git","-C",str(corpus),"rev-parse","HEAD"],text=True
    ).strip()
    if head!=prior["corpus_commit"] or head!=freeze.CORPUS_REV:
        raise ValueError("source corpus changed")
    raw=freeze.blob(corpus,"manifest.json")
    if hash_bytes(raw)!=prior["manifest_sha256"]:
        raise ValueError("corpus manifest changed")
    manifest=json.loads(raw)
    results=[]
    for row in choose(manifest,prior):
        root="boards/"+row["id"]+"/"
        names=subprocess.check_output(
            ["git","-C",str(corpus),"ls-tree","-r","--name-only",head,"--",root],
            text=True).splitlines()
        expected=[f for f in ("board.kicad_pcb","board.kicad_pro","SOURCE.json","board.kicad_dru")
                  if root+f in names]
        if not all(f in expected for f in ("board.kicad_pcb","board.kicad_pro","SOURCE.json")):
            raise ValueError("frozen board source missing mandatory input")
        source=json.loads(freeze.blob(corpus,root+"SOURCE.json"))
        if source["repo"]!=row["repo"] or source["commit"]!=row["commit"]:
            raise ValueError("wrong original repo revision")
        lic=source.get("licence_file")
        if lic and root+lic in names:expected.append(lic)
        digests={name:hash_bytes(freeze.blob(corpus,root+name)) for name in expected}
        results.append({"id":row["id"],"origin_repo":row["repo"],
                        "origin_commit":row["commit"],"source":source,
                        "metadata":row,"sha256":digests})
    result={
        "schema":"hs.posttuning_electrical_holdout.v1",
        "corpus_git_commit":head,
        "corpus_manifest_sha256":hash_bytes(raw),
        "prior_training_cohort_sha256":hash_bytes(prior_lock.read_bytes()),
        "selection_seed":SEED,"method":"first 3 SHA256-seeded metadata-only eligible boards per layer, 2-layer and 4-layer; mutually distinct source repos; excludes all original training repos; 0 initial DRC errors and 0 open pads; <=360 pads, <=700 segments",
        "board_count":len(results),"cases":results,
        "selection_locked_before_electrical_invocation":True,
        "no_physical_tests":True,
    }
    target.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--corpus",type=Path,required=True)
    p.add_argument("--prior-lock",type=Path,default=Path(__file__).with_name("cases.lock.json"))
    p.add_argument("--out",type=Path,default=Path(__file__).with_name("posttuning-cases.lock.json"))
    a=p.parse_args()
    print(json.dumps(lock(a.corpus,a.prior_lock,a.out),indent=2))
