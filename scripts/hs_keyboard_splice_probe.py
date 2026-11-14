#!/usr/bin/env python3
"""Read-only engineering screen of a *reference* rigid PCB before donor splicing."""
from __future__ import annotations
import argparse
import csv
import hashlib
import tempfile
import json
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"src"))
from hardware_splicer.keyboard_splice import CutConfig,evaluate_cut,write_report
from hardware_splicer.keyboard_splice_handoff import build_keyboard_splice_handoff

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--pcb",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    ap.add_argument("--system-python",default="/usr/bin/python3",
                    help="Interpreter with native KiCad pcbnew for board geometry extraction")
    ap.add_argument("--topology-python",default=None,
                    help="Interpreter with Shapely for island reconstruction (defaults to --system-python)")
    ap.add_argument("--harness-csv",type=Path,default=None)
    ap.add_argument("--postcut-islands-json",type=Path,default=None)
    ap.add_argument("--postcut-edges-csv",type=Path,default=None)
    ap.add_argument("--machine-project-json",type=Path,default=None)
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
    topology_result=None
    if args.postcut_islands_json:
        # The plan may only restore circuits actually affected in THIS revision.
        # This is not an inferred set of solder points or an authority to cut.
        target = result["best_scanned_straight_seam"]["all_intersected_nets"]
        island_helper=REPO/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_islands.py"
        with tempfile.TemporaryDirectory(prefix="hs-virtual-copper-") as temp:
            board_file=Path(temp)/"board.json"
            nets_file=Path(temp)/"nets.json"
            board_file.write_text(json.dumps(board), encoding="utf-8")
            nets_file.write_text(json.dumps(target), encoding="utf-8")
            cmd = [
                args.topology_python or args.system_python, str(island_helper), "--board-json", str(board_file),
                "--net-inventory-json", str(nets_file),
                "--cut-x-mm", str(result["best_scanned_straight_seam"]["x_mm"]),
                "--kerf-mm", str(CutConfig().kerf_mm),
                "--output", str(args.postcut_islands_json.resolve()),
            ]
            if args.postcut_edges_csv:
                cmd.extend(["--bridge-csv",str(args.postcut_edges_csv.resolve())])
            analysis=subprocess.run(cmd,capture_output=True,text=True,check=False,timeout=160)
            if analysis.returncode != 0:
                raise SystemExit("Native KiCad-island model unavailable: "+analysis.stderr[-1600:])
        topology_result=json.loads(args.postcut_islands_json.read_text(encoding="utf-8"))
        digest=topology_result.pop("payload_sha256",None)
        payload=json.dumps(topology_result,sort_keys=True,ensure_ascii=False,separators=(",",":"))
        verified=hashlib.sha256(payload.encode()).hexdigest()
        topology_result["payload_sha256"]=digest
        if digest != verified or topology_result.get("source_sha256") != result["source_file_sha256"]:
            raise SystemExit("Topological receipt/source digest mismatch")
        if topology_result.get("cut_x_mm") != result["best_scanned_straight_seam"]["x_mm"]:
            raise SystemExit("Topological cutline differs from reference scan")
        if topology_result.get("target_net_count") != len(target):
            raise SystemExit("Topological net inventory differs from source")
        if topology_result.get("qualified_for_build") is not False or topology_result.get("release") != "BLOCKED_REFERENCE_TOPOLOGY_ONLY":
            raise SystemExit("Topological tool attempted physical authority promotion")
        result["postcut_topology_summary"]={
            key:topology_result[key] for key in (
                "model_pre_cut_island_count", "model_post_cut_island_count",
                "split_pre_cut_components", "candidate_graph_edges",
                "unanchored_split_components", "model_replay_remaining_split_components",
                "model_replay_achieved_full_restoration", "issues", "release", "payload_sha256"
            )
        }
        result["blockers"].append(
            "Modeled electrical islands are partial track/pad/via evidence, not validated post-cut conductivity"
        )
    if args.machine_project_json:
        if topology_result is None:
            raise SystemExit("Canonical machine handoff requires --postcut-islands-json first")
        handoff=build_keyboard_splice_handoff(result,topology_result)
        args.machine_project_json.parent.mkdir(parents=True,exist_ok=True)
        args.machine_project_json.write_text(json.dumps(handoff,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        result["canonical_machine_release"]=handoff["canonical_summary"]
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
