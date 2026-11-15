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
import shutil
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"src"))
from hardware_splicer.keyboard_splice import CutConfig,evaluate_cut,write_report
from hardware_splicer.keyboard_splice_handoff import build_keyboard_splice_handoff
from hardware_splicer.keyboard_splice_repair_loop import run_repair_loop
from hardware_splicer.keyboard_splice_matrix import verify_one_row_matrix

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
    ap.add_argument("--repair-mode",choices=("auto","pad_only","adaptive","adaptive_functional"),
                    default="auto")
    ap.add_argument("--repair-iterations-json",type=Path,default=None)
    ap.add_argument("--passive-matrix-json",type=Path,default=None)
    ap.add_argument("--machine-project-json",type=Path,default=None)
    ap.add_argument("--optimize-stepped",action="store_true")
    ap.add_argument("--stepped-path-json",type=Path,default=None)
    ap.add_argument("--interposer-out",type=Path,default=None)
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
    chosen_stepped=None
    if args.optimize_stepped:
        if not args.stepped_path_json or not args.postcut_islands_json:
            raise SystemExit("stepped analysis requires --stepped-path-json and --postcut-islands-json")
    if args.interposer_out and (not args.postcut_islands_json or not args.machine_project_json):
        raise SystemExit("interposer preview requires both topology and canonical machine handoff")
    if args.postcut_islands_json:
        # The plan may only restore circuits actually affected in THIS revision.
        # This is not an inferred set of solder points or an authority to cut.
        target = result["best_scanned_straight_seam"]["all_intersected_nets"]
        if args.optimize_stepped:
            path_helper=REPO/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_path.py"
            with tempfile.TemporaryDirectory(prefix="hs-virtual-cutpath-") as temp:
                input_path=Path(temp)/"source_board.json"
                input_path.write_text(json.dumps(board),encoding="utf-8")
                proc=subprocess.run([
                    args.topology_python or args.system_python, str(path_helper),
                    "--board-json",str(input_path),
                    "--output",str(args.stepped_path_json.resolve()),
                ],capture_output=True,text=True,timeout=160,check=False)
                if proc.returncode:
                    raise SystemExit("Stepped cut solver unavailable: "+proc.stderr[-1200:])
            chosen_stepped=json.loads(args.stepped_path_json.read_text(encoding="utf-8"))
            original={k:v for k,v in chosen_stepped.items() if k!="payload_sha256"}
            digest=hashlib.sha256(json.dumps(original,sort_keys=True,ensure_ascii=False,
                                           separators=(",",":")).encode()).hexdigest()
            if (chosen_stepped.get("payload_sha256")!=digest or
                chosen_stepped.get("source_sha256")!=result["source_file_sha256"] or
                chosen_stepped.get("release")!="PROPOSED_CUT_ONLY_NOT_VERIFIED" or
                chosen_stepped.get("physical_cut_authorized") is not False):
                raise SystemExit("Proposed stepped cut source or authority was tampered")
            target=chosen_stepped["affected_nets"]
            result["stepped_path_summary"]={
                k:chosen_stepped[k] for k in (
                    "payload_sha256","nominal_path_length_mm","collision_counts",
                    "affected_net_count","source_geometry_issues","release",
                    "physical_cut_authorized",
                )
            }
            result["blockers"].append(
                "Stepped cut is only a modeled path; component destruction and actual populated donor layout unverified"
            )
        island_helper=REPO/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_islands.py"
        restoration=run_repair_loop(
            script=island_helper,
            interpreter=args.topology_python or args.system_python,
            source_board=board,
            net_names=target,
            seam_x=result["best_scanned_straight_seam"]["x_mm"],
            kerf_mm=CutConfig().kerf_mm,
            path_file=args.stepped_path_json if chosen_stepped is not None else None,
            topology_file=args.postcut_islands_json.resolve(),
            edge_csv=args.postcut_edges_csv.resolve() if args.postcut_edges_csv else None,
            repair_mode=args.repair_mode,
        )
        result["repair_loop_summary"]={
            "selected_strategy":restoration["selected_strategy"],
            "total_iterations":restoration["total_iterations"],
            "required_graph_connected_in_model":restoration["required_graph_connected_in_model"],
            "unresolved_source_baseline_terminal_net_gaps":restoration[
                "unresolved_source_baseline_terminal_net_gaps"],
            "physical_authority_granted":False,
            "result":restoration["result"],
        }
        if args.repair_iterations_json:
            args.repair_iterations_json.parent.mkdir(parents=True,exist_ok=True)
            args.repair_iterations_json.write_text(json.dumps(
                restoration,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
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
        if chosen_stepped is not None:
            if topology_result.get("cut_path_sha256") != chosen_stepped["payload_sha256"]:
                raise SystemExit("Copper model did not evaluate the selected stepped path")
        elif topology_result.get("cut_path_sha256") is not None:
            raise SystemExit("Copper model unexpectedly substituted a stepped path")
        if topology_result.get("qualified_for_build") is not False or topology_result.get("release") != "BLOCKED_REFERENCE_TOPOLOGY_ONLY":
            raise SystemExit("Topological tool attempted physical authority promotion")
        result["postcut_topology_summary"]={
            key:topology_result[key] for key in (
                "model_pre_cut_island_count", "model_post_cut_island_count",
                "split_pre_cut_components", "candidate_graph_edges",
                "unanchored_split_components", "model_replay_remaining_split_components",
                "model_replay_remaining_required_components",
                "model_replay_achieved_required_restoration",
                "planned_inert_track_remnants", "damaged_electrical_pad_count",
                "preexisting_unconnected_terminal_net_count",
                "repair_mode",
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
    if args.interposer_out:
        interposer_helper=REPO/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_interposer.py"
        build=subprocess.run(
            [args.system_python,str(interposer_helper),
             "--topology-json",str(args.postcut_islands_json.resolve()),
             "--out",str(args.interposer_out.resolve())],
            capture_output=True,text=True,timeout=120,check=False
        )
        if build.returncode:
            raise SystemExit("Interposer KiCad preview failed: "+build.stderr[-1400:])
        manifest=json.loads((args.interposer_out/"INTERPOSER_CHANNEL_MAP.json").read_text(encoding="utf-8"))
        if (manifest.get("source_reference_sha256")!=result["source_file_sha256"] or
            manifest.get("topology_sha256")!=topology_result["payload_sha256"] or
            manifest.get("fabrication_release")!="BLOCKED_PREVIEW_ONLY" or
            manifest.get("physical_authority_granted") is not False):
            raise SystemExit("Interposer preview source or physical authority mismatch")
        kicad_cli=shutil.which("kicad-cli")
        if not kicad_cli:
            raise SystemExit("Actual KiCad DRC unavailable; refuse interposer verification claim")
        pcb_path=args.interposer_out/"reference_bridge_interposer.kicad_pcb"
        drc_path=args.interposer_out/"INTERPOSER_NATIVE_DRC.json"
        checked=subprocess.run(
            [kicad_cli,"pcb","drc","--format","json",
             "--output",str(drc_path.resolve()),str(pcb_path.resolve())],
            capture_output=True,text=True,timeout=180,check=False
        )
        if not drc_path.is_file():
            raise SystemExit("Native KiCad returned no verifiable DRC report")
        drc=json.loads(drc_path.read_text(encoding="utf-8"))
        n_errors=sum(str(row.get("severity","")).lower()=="error" for row in drc.get("violations",[]))
        n_warnings=sum(str(row.get("severity","")).lower()=="warning" for row in drc.get("violations",[]))
        n_open=len(drc.get("unconnected_items",[]))
        ver={
            "schema":"hs.keyboard-interposer-native-drc.v1",
            "source_sha256":result["source_file_sha256"],
            "topology_sha256":topology_result["payload_sha256"],
            "pcb_sha256":hashlib.sha256(pcb_path.read_bytes()).hexdigest(),
            "pcb_filename":pcb_path.name,
            "channel_count":manifest["channel_count"],
            "native_kicad_exit":checked.returncode,
            "native_drc_errors":n_errors,
            "native_drc_warnings":n_warnings,
            "native_unconnected_items":n_open,
            "native_design_checks_passed":checked.returncode==0 and n_errors==0 and n_open==0,
            "physical_authority_granted":False,
            "fabrication_release":"BLOCKED_PREVIEW_ONLY",
        }
        (args.interposer_out/"INTERPOSER_VERIFICATION.json").write_text(
            json.dumps(ver,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        result["interposer_preview_summary"]={
            "channels":ver["channel_count"],"pcb_sha256":ver["pcb_sha256"],
            "native_drc_errors":n_errors,"native_drc_warnings":n_warnings,
            "native_unconnected_items":n_open,
            "native_design_checks_passed":ver["native_design_checks_passed"],
            "fabrication_release":ver["fabrication_release"]
        }
        if not ver["native_design_checks_passed"]:
            raise SystemExit("Native KiCad interposer PCB verification failed; inspect DRC report")
    if args.passive_matrix_json:
        if topology_result is None or chosen_stepped is None:
            raise SystemExit("Passive matrix verification needs the original source and stepped reconstruction")
        kicad_cli=shutil.which("kicad-cli")
        if not kicad_cli:
            raise SystemExit("Native KiCad source DRC unavailable")
        with tempfile.TemporaryDirectory(prefix="hs-source-matrix-drc-") as tmp:
            path=Path(tmp)/"source_drc.json"
            checked=subprocess.run([
                kicad_cli,"pcb","drc","--format","json",
                "--output",str(path),str(args.pcb.resolve())
            ],capture_output=True,text=True,timeout=120,check=False)
            if checked.returncode or not path.is_file():
                raise SystemExit("Original keyboard PCB fails native DRC; cannot assert matrix function")
            source_drc=json.loads(path.read_text(encoding="utf-8"))
        functional=verify_one_row_matrix(board,topology_result,chosen_stepped,source_drc)
        args.passive_matrix_json.parent.mkdir(parents=True,exist_ok=True)
        args.passive_matrix_json.write_text(json.dumps(
            functional,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        result["passive_matrix_summary"]={
            "model_passed":functional["passive_keyboard_matrix_model_passed"],
            "key_switch_count":functional["keys"],
            "ideal_combinations_tested":functional["ideal_switch_combinations_tested"],
            "ideal_combinations_failed":functional["ideal_switch_combinations_failed"],
            "payload_sha256":functional["payload_sha256"],
            "physical_repair_verified":False,
        }
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
    if result.get("repair_loop_summary"):
        s=result["repair_loop_summary"]
        print("REPAIR_ITERATIONS",s["total_iterations"],"strategy",s["selected_strategy"])
        print("MODELED_REQUIRED_GRAPH_CONNECTED",s["required_graph_connected_in_model"],
              "source_baseline_terminal_gaps",s["unresolved_source_baseline_terminal_net_gaps"])
    print("VERDICT",result["release"],"report",args.out)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
