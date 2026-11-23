#!/usr/bin/env python3
"""Unseen external PCB corpus, genuine KiCad extraction, bounded splice replay.

This is a convenience sample of public KiCad keyboard designs, NOT a random
sample of physical discarded keyboards. No actual salvaged hardware is
available. It records failed models and unsupported inputs without promoting
source or model checks into physical repair authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from hardware_splicer.keyboard_splice_arbitrary import (
    triage_reference_pcb, assess_arbitrary_outcome
)


def read_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def limited_call(cmd: list[str], *, timeout: int, stdout_file: Path | None = None):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        if stdout_file:
            stdout_file.write_text(proc.stdout[-3000:] + "\nSTDERR:\n" +
                                   proc.stderr[-3000:], encoding="utf-8")
        return proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired:
        if stdout_file:
            stdout_file.write_text("TIMEOUT at "+str(timeout)+" sec\n",encoding="utf-8")
        return 124, "", "PROCESS_TIMEOUT", True


def source(path: Path, case: dict, do_fetch: bool):
    if path.is_file():
        return path
    if not do_fetch:
        return None
    path.parent.mkdir(parents=True,exist_ok=True)
    req = urllib.request.Request(case["raw_url"],headers={"User-Agent":"HS-keyboard-arbitrary-model-pilot"})
    with urllib.request.urlopen(req, timeout=25) as r:
        content = r.read(20_000_001)
    if len(content)>20_000_000:
        raise ValueError("source PCB exceeds 20MB bounds")
    # Do not persist an unverified branch download.
    if hashlib.sha256(content).hexdigest()!=case["sha256"]:
        raise ValueError("external repository changed since manifest pin")
    path.write_bytes(content)
    return path


def one_case(case: dict, *, source_dir: Path, output_dir: Path,
             system_python: str, engine_python: str, fetch: bool):
    name=case["id"]
    dest=output_dir/name
    dest.mkdir(parents=True,exist_ok=False)
    record={
        "schema":"hs.arbitrary-keyboard-real-reference.v1",
        "case_id":name,
        "repository":case["repository"],
        "reference_path":case["path"],
        "source_url":case["raw_url"],
        "expected_source_sha256":case["sha256"],
        "physical_donor_present":False,
        "engine_uses_hand_written_wiring_map":False,
    }
    path=source_dir/case["filename"]
    try:
        actual=source(path,case,fetch)
        if actual is None:
            record.update(status="SOURCE_UNAVAILABLE_OFFLINE",
                          error="Expected exact source PCB missing; no substituted board")
            return record
        digest=hashlib.sha256(actual.read_bytes()).hexdigest()
        record["actual_sha256"]=digest
        if digest!=case["sha256"]:
            record.update(status="SOURCE_HASH_MISMATCH_REJECTED",
                          error="PCB bytes differ from pinned manifest")
            return record
    except Exception as exc:
        record.update(status="SOURCE_FETCH_OR_HASH_REJECTED",error=str(exc)[:350])
        return record

    extractor=REPO/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_extract.py"
    code,out,err,timed=limited_call(
        [system_python,str(extractor),"--pcb",str(path.resolve())],timeout=60
    )
    if code!=0:
        record.update(
            status="UNSUPPORTED_KICAD_SOURCE_FORMAT_OR_NATIVE_IMPORT",
            native_parser_exit=code, native_parser_timeout=timed,
            parser_error=err[-450:] or out[-200:],
        )
        return record
    try:
        board=json.loads(out)
    except json.JSONDecodeError:
        record.update(status="NATIVE_KICAD_EXTRACTION_MALFORMED")
        return record
    intake=triage_reference_pcb(board)
    record["intake"]=intake
    if not intake["eligible_for_bounded_virtual_reconstruction"]:
        record.update(
            status="SOURCE_TRIAGE_REJECTED",
            verdict=assess_arbitrary_outcome(intake),
        )
        return record

    native_drc=dest/"SOURCE_NATIVE_DRC.json"
    native_rc,_,drc_err,_=limited_call([
        "kicad-cli","pcb","drc","--format","json",
        "--output",str(native_drc.resolve()),str(path.resolve())
    ],timeout=20)
    drc=read_json(native_drc)
    record["native_source_drc"]={
        "exit":native_rc,
        "violations":len(drc.get("violations",[])) if drc else None,
        "unconnected_items":len(drc.get("unconnected_items",[])) if drc else None,
        "kicad_version":drc.get("kicad_version") if drc else None,
        "report_present":bool(drc),
    }
    if not drc:
        record["native_source_drc"]["error"]=drc_err[-160:]

    run_dir=dest/"run"
    run_dir.mkdir()
    args=[
        engine_python, str(REPO/"scripts/hs_keyboard_splice_probe.py"),
        "--pcb",str(path.resolve()),
        "--system-python",system_python,
        "--topology-python",system_python,
        "--out",str((run_dir/"CUT.json").resolve()),
        "--postcut-islands-json",str((run_dir/"POSTCUT.json").resolve()),
        "--postcut-edges-csv",str((run_dir/"BRIDGES.csv").resolve()),
        "--machine-project-json",str((run_dir/"MACHINE.json").resolve()),
        "--optimize-stepped","--stepped-path-json",str((run_dir/"PATH.json").resolve()),
        "--repair-mode","auto","--repair-iterations-json",str((run_dir/"ITERATIONS.json").resolve()),
        "--interposer-out",str((run_dir/"interposer").resolve())
    ]
    rc, stdout, stderr, timed=limited_call(
        args,timeout=175,stdout_file=dest/"RUN_OUTPUT.log"
    )
    record["engine_execution"]={
        "exit":rc, "timeout":timed,
        "error_tail":stderr[-340:] if rc else None,
    }
    cut=read_json(run_dir/"CUT.json")
    candidate=read_json(run_dir/"PATH.json")
    topology=read_json(run_dir/"POSTCUT.json")
    iterations=read_json(run_dir/"ITERATIONS.json")
    interposer=read_json(run_dir/"interposer/INTERPOSER_VERIFICATION.json")
    try:
        verdict=assess_arbitrary_outcome(
            intake,path=candidate,topology=topology,
            interposer=interposer,source_drc=drc
        )
    except ValueError as exc:
        record.update(status="CROSS_REVISION_OR_AUTHORITY_MISMATCH",error=str(exc))
        return record
    record["status"]=verdict["status"]
    record["verdict"]=verdict
    if candidate:
        record["cut"]={
            "left_switch_candidates":candidate.get("switch_candidates_left"),
            "right_switch_candidates":candidate.get("switch_candidates_right"),
            "collisions":candidate.get("collision_counts"),
            "affected_nets":candidate.get("affected_net_count"),
        }
    if topology:
        record["reconstruction"]={
            "mode":topology.get("repair_mode"),
            "bridge_channels":topology.get("candidate_graph_edges"),
            "remaining_required_groups":topology.get("model_replay_remaining_required_components"),
            "preexisting_terminal_net_gaps":topology.get("preexisting_unconnected_terminal_net_count"),
            "inert_remnants_to_isolate":topology.get("planned_inert_track_remnants"),
            "model_issues":topology.get("issues"),
        }
    if iterations:
        record["iterations"]=[
            {"mode":stage["strategy"],"remaining":stage["unconnected_required_groups"]}
            for stage in iterations["iterations"]
        ]
    if interposer:
        record["interposer"]={
            "native_drc_pass":interposer["native_design_checks_passed"],
            "channel_count":interposer["channel_count"],
            "fabrication_release":interposer["fabrication_release"],
        }
    return record


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,default=REPO/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/manifest.json")
    ap.add_argument("--sources",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--system-python",default="/usr/bin/python3")
    ap.add_argument("--engine-python",default=sys.executable)
    ap.add_argument("--fetch",action="store_true",help="Fetch exact sha-pinned public PCB when absent")
    ap.add_argument("--only",nargs="+",default=None,
                    help="Execute selected pinned case IDs; all entries by default")
    args=ap.parse_args()
    manifest=json.loads(args.manifest.read_text(encoding="utf-8"))
    names=[c["id"] for c in manifest["cases"]]
    if len(names)!=len(set(names)):
        raise SystemExit("duplicate case identifier")
    if args.out.exists():
        raise SystemExit("Output directory must be new to prevent stale successful evidence")
    args.out.mkdir(parents=True)
    selected=manifest["cases"]
    if args.only is not None:
        unknown=sorted(set(args.only)-set(names))
        if unknown:
            raise SystemExit("Unknown case IDs: "+", ".join(unknown))
        selected=[case for case in selected if case["id"] in set(args.only)]
    records=[]
    for case in selected:
        record=one_case(case,source_dir=args.sources,output_dir=args.out,
                        system_python=args.system_python,engine_python=args.engine_python,
                        fetch=args.fetch)
        records.append(record)
        print(case["id"],record["status"],
              "switches",record.get("intake",{}).get("key_switch_candidates"),
              "remaining",record.get("reconstruction",{}).get("remaining_required_groups"),
              flush=True)
        (args.out/(case["id"]+"_SUMMARY.json")).write_text(
            json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
        )
    statuses={}
    for record in records:
        s=record["status"]
        statuses[s]=statuses.get(s,0)+1
    report={
        "schema":"hs.arbitrary-keyboard-public-reference-benchmark.v1",
        "manifest_sha256":hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "case_count":len(records),
        "selected_case_ids":[c["id"] for c in selected],
        "cases":records,
        "status_counts":dict(sorted(statuses.items())),
        "strict_reference_digital_passes":sum(
            bool(c.get("verdict",{}).get("strict_reference_digital_pass")) for c in records),
        "modeled_copper_reconnections":sum(
            c.get("reconstruction",{}).get("remaining_required_groups") == 0
            and c.get("reconstruction",{}).get("bridge_channels",0)>0
            for c in records if c.get("reconstruction")
        ),
        "actual_physical_discarded_boards":0,
        "fabrication_or_sale_authorized":False,
        "sample_is_random":False,
    }
    (args.out/"BENCHMARK.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("SUMMARY",report["status_counts"],
          "strict_digital_pass",report["strict_reference_digital_passes"],
          "model_reconnects",report["modeled_copper_reconnections"],
          "physical",report["actual_physical_discarded_boards"])
    return 0


if __name__=="__main__":
    raise SystemExit(main())
