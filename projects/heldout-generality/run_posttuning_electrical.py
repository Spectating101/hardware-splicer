"""Pre-registered independent post-tuning KiCad track-tap holdout.

No model/software tuning on these source boards. Uses the pre-existing
track_tap.py from HS #371 *unchanged*, native KiCad DRC and source audit.
Every original source, blocked case, native DRC report and trial is retained.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,shutil
from pathlib import Path
import freeze

HERE=Path(__file__).resolve().parent
LIMIT=24
def sha(b):return hashlib.sha256(b).hexdigest()
def serial(x):return json.dumps(x,sort_keys=True,separators=(",",":"))

def invoke(args,cwd,name,seconds=180):
    try:
        r=subprocess.run(args,cwd=cwd,capture_output=True,timeout=seconds)
        stdout,stderr,code=r.stdout,r.stderr,r.returncode
    except subprocess.TimeoutExpired as exc:
        stdout=exc.stdout or b"";stderr=(exc.stderr or b"")+b"\nTIMEOUT"
        code=-1
    (cwd/(name+".stdout")).write_bytes(stdout)
    (cwd/(name+".stderr")).write_bytes(stderr)
    return code

def run(corpus,lock,out):
    if out.exists():raise FileExistsError("refusing to reuse heldout output")
    frozen=json.loads(lock.read_text())
    if frozen["schema"] not in ("hs.posttuning_electrical_holdout.v1", "hs.postfix_electrical_confirmatory_v2") or len(frozen["cases"])!=6:
        raise ValueError("must use exactly the frozen cohort")
    head=subprocess.check_output(["git","-C",str(corpus),"rev-parse","HEAD"],text=True).strip()
    if head!=frozen["corpus_git_commit"]:raise ValueError("corpus revision disagreement")
    if sha(freeze.blob(corpus,"manifest.json"))!=frozen["corpus_manifest_sha256"]:
        raise ValueError("source corpus manifest wrong")
    out.mkdir(parents=True)
    rounds=[]
    for round_num in (1,2):
        rd=out/("round-"+str(round_num));rd.mkdir()
        results=[]
        for case in frozen["cases"]:
            tag=case["id"]
            work=rd/tag;work.mkdir()
            source=work/"original";source.mkdir()
            for name,digest in case["sha256"].items():
                raw=freeze.blob(corpus,"boards/"+tag+"/"+name)
                if sha(raw)!=digest:raise ValueError("SOURCE_BYTES_CHANGED:"+tag+"/"+name)
                (source/name).write_bytes(raw)
            print("ROUND",round_num,"EVALUATE",tag,flush=True)
            candidate_dir=work/"engine"
            code=invoke([
                "/usr/bin/python3",str(HERE/"track_tap.py"),
                "--source-dir",str(source),"--out",str(candidate_dir),
                "--limit",str(LIMIT)
            ],work,"track-tap",250)
            attempts=json.loads((candidate_dir/"attempts.json").read_text()) if (candidate_dir/"attempts.json").exists() else []
            failed_types=sorted({str(k) for a in attempts for k in a.get("drc",{}).get("finding_types",{})})
            record={
                "id":tag,"original_repo":case["origin_repo"],
                "original_pcb_sha256":case["sha256"]["board.kicad_pcb"],
                "original_layer_count":case["metadata"]["copper_layers"],
                "candidate_count_attempted":len(attempts),
                "max_candidates":LIMIT,
                "drc_finding_types_encountered":failed_types,
                "fabrication_authorized":False,
                "physical_test_performed":False,
            }
            if code==0 and (candidate_dir/"result.json").exists():
                rec=json.loads((candidate_dir/"result.json").read_text())
                revised=candidate_dir/("trial-"+str(rec["candidate_attempts"]).zfill(3))/"board.kicad_pcb"
                audit_path=work/"independent-native.json"
                wrong=work/"wrong-net-negative"
                audit_rc=invoke([
                    "/usr/bin/python3",str(HERE/"audit_track_tap.py"),
                    "--source",str(source/"board.kicad_pcb"),
                    "--revised",str(revised),
                    "--receipt",str(candidate_dir/"result.json"),
                    "--negative",str(wrong),
                    "--out",str(audit_path)
                ],work,"independent-audit",180)
                if audit_rc==0 and audit_path.exists():
                    verified=json.loads(audit_path.read_text())
                    good=(verified.get("status")=="PASS"
                          and verified.get("wrong_net_negative",{}).get("rejected") is True)
                    record.update({
                        "status":"INDEPENDENT_DIGITAL_PASS" if good else "INDEPENDENT_AUDIT_FAILED",
                        "edited_pcb_sha256":rec["edited_sha256"],
                        "tap_source_net":rec["source_anchor_net"],
                        "tap_ref":rec["new_testpoint"],
                        "tap_xy":rec["branch_end_mm"],
                        "drc_errors":rec["native_drc"]["errors"],
                        "drc_unconnected":rec["native_drc"]["unconnected"],
                        "independent_original_copper_preserved":verified.get("original_copper_items_preserved"),
                        "wrong_net_injected_drc_rejected":good,
                    })
                else:
                    record.update({"status":"INDEPENDENT_AUDIT_FAILED",
                                   "audit_process_exit":audit_rc})
            else:
                stderr=(work/"track-tap.stderr").read_text(errors="replace")
                permitted_reasons=("NO_SOURCE_BACKED_TRACK_TAP_CANDIDATES",
                                   "NO_DRC_ZERO_BOUNDED_TRACK_TAP",
                                   "UNSUPPORTED_EDGE_CUTS")
                matched=next((t for t in permitted_reasons if t in stderr),None)
                record.update({
                    "status":"NO_ELIGIBLE_SOURCE_TRACKS" if matched==permitted_reasons[0] else
                             "NO_DRC_CLEAN_SOLUTION_WITHIN_BUDGET" if matched==permitted_reasons[1] else
                             "UNSUPPORTED_SOURCE" if matched==permitted_reasons[2] else
                             "ENGINE_ERROR",
                    "failure_class":matched or "UNCLASSIFIED_ENGINE_FAILURE",
                    "engine_process_exit":code
                })
            (work/"case-verdict.json").write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
            results.append(record)
            print("  VERDICT",record["status"],"attempts",len(attempts),flush=True)
        (rd/"summary.json").write_text(json.dumps(results,indent=2,sort_keys=True)+"\n")
        rounds.append(results)
    digests=[sha(serial(r).encode()) for r in rounds]
    statuses=[r["status"] for r in rounds[0]]
    result={
        "schema":"hs.posttuning_electrical_benchmark_result.v1",
        "precommitted_lock_sha256":sha(lock.read_bytes()),
        "original_corpus_commit":frozen["corpus_git_commit"],
        "development_branch_baseline":("HS #371 unchanged original electrical candidate search" if frozen["schema"]=="hs.posttuning_electrical_holdout.v1" else "HS #371 electrical search unchanged; only source-UUID serialization and empty-cutout negative-control fixes"),
        "allowed_candidates_per_board":LIMIT,
        "distinct_unseen_original_repositories":len({r["original_repo"] for r in rounds[0]}),
        "total_cases":len(rounds[0]),
        "clean_electrical_edits_independently_verified":sum(s=="INDEPENDENT_DIGITAL_PASS" for s in statuses),
        "drc_blocked":sum(s=="NO_DRC_CLEAN_SOLUTION_WITHIN_BUDGET" for s in statuses),
        "no_track_candidates":sum(s=="NO_ELIGIBLE_SOURCE_TRACKS" for s in statuses),
        "engine_or_audit_errors":sum(s in ("ENGINE_ERROR","INDEPENDENT_AUDIT_FAILED") for s in statuses),
        "canonical_semantic_round_sha256":digests,
        "exact_semantic_repeatability":digests[0]==digests[1],
        "second_machine_reproduction":"NOT_PERFORMED",
        "general_arbitrary_autorouting":"NOT_PROVEN",
        "physical_testing":"NOT_PERFORMED",
        "fabrication_authorized":False,
    }
    result["benchmark_integrity_pass"]=(result["exact_semantic_repeatability"]
                                      and result["total_cases"]==6
                                      and result["distinct_unseen_original_repositories"]==6
                                      and result["engine_or_audit_errors"]==0)
    (out/"result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--corpus",type=Path,required=True)
    p.add_argument("--cohort",type=Path,default=HERE/"posttuning-cases.lock.json")
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=run(a.corpus,a.cohort,a.out)
    raise SystemExit(0 if result["benchmark_integrity_pass"] else 2)
