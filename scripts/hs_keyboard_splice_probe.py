#!/usr/bin/env python3
"""Read-only engineering screen of a *reference* rigid PCB before donor splicing."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"src"))
from hardware_splicer.keyboard_splice import CutConfig,evaluate_cut,write_report

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--pcb",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--system-python",default="/usr/bin/python3")
    ap.add_argument("--harness-csv",type=Path,default=None)
    ap.add_argument("--x",type=float,default=None,help="Optional x coordinate to assess without searching a cut route")
    args=ap.parse_args()
    if not args.pcb.is_file(): raise SystemExit("PCB file not found")
    extractor=REPO/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_extract.py"
    completed=subprocess.run(
        [args.system_python,str(extractor),"--pcb",str(args.pcb.resolve())],
        capture_output=True,text=True,check=False,timeout=120
    )
    if completed.returncode: raise SystemExit("KiCad evidence extraction unavailable: "+completed.stderr[-1400:])
    try: board=json.loads(completed.stdout)
    except json.JSONDecodeError as exc: raise SystemExit("Unparseable pcbnew extraction; refuse design authorization") from exc
    result=evaluate_cut(board,cfg=CutConfig(),requested_x_mm=args.x)
    write_report(result,args.out)
    if args.harness_csv:
        args.harness_csv.parent.mkdir(parents=True,exist_ok=True)
        with args.harness_csv.open("w",encoding="utf-8",newline="") as stream:
            writer=csv.writer(stream,lineterminator="\n")
            writer.writerow(["net","classification","crossings","left_ref_pad","right_ref_pad","status"])
            for row in result["best_scanned_straight_seam"]["harness_candidates"]:
                def id_pad(key: str) -> str:
                    p=row.get(key)
                    return (str(p.get("ref",""))+"/"+str(p.get("pad",""))) if p else "NO_PAD_FOUND"
                writer.writerow([
                    row["net"],row["function_class"],row["crossed_segments"],
                    id_pad("left_candidate_pad"),id_pad("right_candidate_pad"),
                    "VIRTUAL_PROPOSAL_ONLY_UNPROVEN_CONTINUITY"
                ])
    best=result["best_scanned_straight_seam"]
    mid=result["midpoint"]
    print("SOURCE_SHA256",result["source_file_sha256"])
    print("SCAN",result["scanned_straight_seams"],"passing",result["passing_seams"])
    print("CENTRAL",mid["track_segments_touched"],"segments;",mid["distinct_nets_touched"],"nets;",mid["switch_centers_at_risk"],"switch keepouts")
    print("BEST",best["x_mm"],"mm;",best["distinct_nets_touched"],"nets;",len(best["matrix_nets_touched"]),"matrix nets;",best["switch_centers_at_risk"],"switch keepouts;",best["pads_at_risk"],"pads")
    print("VERDICT",result["release"],"report",args.out)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
