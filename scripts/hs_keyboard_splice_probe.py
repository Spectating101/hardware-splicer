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
from hardware_splicer.keyboard_splice_handoff import (
    build_keyboard_splice_handoff,
    extend_keyboard_splice_handoff,
)
from hardware_splicer.keyboard_splice_repair_loop import run_repair_loop
from hardware_splicer.keyboard_splice_matrix import verify_one_row_matrix
from hardware_splicer.keyboard_splice_full_matrix import full_matrix_proof
from hardware_splicer.keyboard_splice_source_audit import audit_independent_source
from hardware_splicer.keyboard_splice_teensy2 import audit_teensy2_gpio
from hardware_splicer.keyboard_splice_zone_drc import verify_legacy_refilled_copy_receipt

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
    ap.add_argument("--multi-route-json",type=Path,default=None)
    ap.add_argument("--key-relocation-out",type=Path,default=None)
    ap.add_argument("--independent-source-dir",type=Path,default=None)
    ap.add_argument("--source-pin-manifest",type=Path,default=None)
    ap.add_argument("--independent-source-audit-json",type=Path,default=None)
    ap.add_argument("--full-matrix-proof-json",type=Path,default=None)
    ap.add_argument("--source-teensy2-footprint",type=Path,default=None)
    ap.add_argument("--pjrc-pinout-proof-json",type=Path,default=None)
    ap.add_argument("--legacy-zone-drc-receipt-json",type=Path,default=None)
    ap.add_argument("--full-junction-out",type=Path,default=None)
    ap.add_argument("--compact-junction-out",type=Path,default=None)
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
    if args.multi_route_json and not args.optimize_stepped:
        raise SystemExit("multi-route reconstruction requires --optimize-stepped")
    if args.key_relocation_out and not args.multi_route_json:
        raise SystemExit("key relocation needs a source-bound multi-route audit")
    if args.interposer_out and (not args.postcut_islands_json or not args.machine_project_json):
        raise SystemExit("interposer preview requires both topology and canonical machine handoff")
    if args.compact_junction_out and not args.full_junction_out:
        raise SystemExit("compact IDC junction requires the already verified full source-net junction")

    if args.postcut_islands_json:
        # The plan may only restore circuits actually affected in THIS revision.
        # This is not an inferred set of solder points or an authority to cut.
        target = result["best_scanned_straight_seam"]["all_intersected_nets"]
        if args.optimize_stepped:
            route_search=bool(args.multi_route_json)
            path_helper=REPO/(
                "src/hardware_splicer/_pcbnew_helpers/keyboard_splice_route_search.py"
                if route_search else
                "src/hardware_splicer/_pcbnew_helpers/keyboard_splice_path.py"
            )
            with tempfile.TemporaryDirectory(prefix="hs-virtual-cutpath-") as temp:
                input_path=Path(temp)/"source_board.json"
                input_path.write_text(json.dumps(board),encoding="utf-8")
                cmd=[args.topology_python or args.system_python, str(path_helper),
                     "--board-json",str(input_path)]
                if route_search:
                    cmd.extend(["--output",str(args.multi_route_json.resolve()),
                                "--selected-cut-json",str(args.stepped_path_json.resolve())])
                else:
                    cmd.extend(["--output",str(args.stepped_path_json.resolve())])
                proc=subprocess.run(
                    cmd,capture_output=True,text=True,timeout=160,check=False
                )
                if proc.returncode:
                    raise SystemExit("Cut route solver unavailable: "+proc.stderr[-1400:])
            if route_search:
                multi=json.loads(args.multi_route_json.read_text(encoding="utf-8"))
                audit=multi.get("selected_consequence",{})
                if (multi.get("source_sha256")!=board["source_sha256"] or
                    multi.get("fabrication_authorized") is not False or
                    multi.get("release")!="BLOCKED_RESEARCH_ROUTE_ONLY" or
                    audit.get("source_sha256")!=board["source_sha256"] or
                    audit.get("manufacturing_authority") is not False):
                    raise SystemExit("Multi-route audit did not preserve source identity or release boundary")
                result["multi_route_summary"]={
                    "selected_strategy":multi["selected_strategy"],
                    "attempted_strategies":multi["attempted_strategies"],
                    "unique_proposed_paths":multi["unique_proposed_paths"],
                    "sacrificed_key_count":audit["sacrificed_key_count"],
                    "retained_keys":audit["remaining_switches"],
                    "retained_left":audit["remaining_left"],
                    "retained_right":audit["remaining_right"],
                    "model_critical_clear":audit["nominally_salvageable_except_sacrificed_switches"],
                    "physical_authority_granted":False,
                }
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
    if args.interposer_out and topology_result is not None and not topology_result.get("bridge_edges"):
        result["interposer_preview_summary"]={
            "channels":0,
            "native_design_checks_passed":False,
            "skipped_due_to_no_source_connected_bridge_endpoints":True,
            "fabrication_release":"BLOCKED_NO_QUALIFYING_CONNECTIONS",
        }
    else:
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
    if args.key_relocation_out:
        if (topology_result is None or chosen_stepped is None or
            not result.get("repair_loop_summary",{}).get("required_graph_connected_in_model") or
            not result.get("interposer_preview_summary",{}).get("native_design_checks_passed")):
            raise SystemExit("Cannot generate replacement keys before modeled continuity and KiCad bridge checks")
        if topology_result.get("preexisting_unconnected_terminal_net_count") != 0:
            raise SystemExit("Cannot relabel source keypad before original source terminal connectivity is modeled")
        multi=json.loads(args.multi_route_json.read_text(encoding="utf-8"))
        audit=multi.get("selected_consequence",{})
        if (audit.get("nominally_salvageable_except_sacrificed_switches") is not True or
            audit.get("cut_path_sha256")!=chosen_stepped["payload_sha256"] or
            multi.get("source_sha256")!=board["source_sha256"]):
            raise SystemExit("Selected path damages an unremovable component or is unbound")
        key_helper=REPO/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_key_relocation.py"
        with tempfile.TemporaryDirectory(prefix="hs-key-source-audit-") as source_tmp:
            pcb_data=Path(source_tmp)/"board.json"
            pcb_data.write_text(json.dumps(board),encoding="utf-8")
            process=subprocess.run([
                args.system_python,str(key_helper),
                "--board-json",str(pcb_data),
                "--route-search-json",str(args.multi_route_json.resolve()),
                "--out",str(args.key_relocation_out.resolve()),
            ],capture_output=True,text=True,check=False,timeout=120)
            if process.returncode:
                raise SystemExit("Source-bound relocation board failed: "+process.stderr[-1400:])
        remount_path=args.key_relocation_out/"remount_keys.kicad_pcb"
        mapping=json.loads((args.key_relocation_out/"RELOCATION_MAP.json").read_text(encoding="utf-8"))
        if (mapping.get("source_sha256")!=board["source_sha256"] or
            mapping.get("cut_path_sha256")!=chosen_stepped["payload_sha256"] or
            mapping.get("fabrication_release")!="BLOCKED_RELOCATION_PREVIEW_ONLY" or
            mapping.get("physical_authority_granted") is not False or
            mapping.get("total_original_switch_positions_accounted")!=len(board["switch_positions"])):
            raise SystemExit("Replacement-key source, count, or authority mismatch")
        kicad_cli=shutil.which("kicad-cli")
        if not kicad_cli:
            raise SystemExit("Native KiCad unavailable for replacement-key electrical design check")
        drc_path=args.key_relocation_out/"RELOCATION_NATIVE_DRC.json"
        proc=subprocess.run([
            kicad_cli,"pcb","drc","--format","json",
            "--output",str(drc_path.resolve()),str(remount_path.resolve())
        ],capture_output=True,text=True,check=False,timeout=120)
        if not drc_path.is_file():
            raise SystemExit("KiCad produced no replacement-key verification receipt")
        native=json.loads(drc_path.read_text(encoding="utf-8"))
        violations=len(native.get("violations",[]))
        opens=len(native.get("unconnected_items",[]))
        check={
            "schema":"hs.source-bound-relocated-keys-kicad-check.v1",
            "source_sha256":board["source_sha256"],
            "cut_path_sha256":chosen_stepped["payload_sha256"],
            "remount_pcb_sha256":hashlib.sha256(remount_path.read_bytes()).hexdigest(),
            "relocated_key_count":mapping["key_switches_relocated"],
            "reference_original_keys_accounted":mapping["total_original_switch_positions_accounted"],
            "native_kicad_drc_exit":proc.returncode,
            "drc_violations":violations,
            "unconnected_items":opens,
            "geometry_model_verified":proc.returncode==0 and violations==0 and opens==0,
            "original_keyboard_source_drc_certified":False,
            "physical_authority_granted":False,
            "fabrication_release":"BLOCKED_RELOCATION_PREVIEW_ONLY",
        }
        (args.key_relocation_out/"RELOCATION_VERIFICATION.json").write_text(
            json.dumps(check,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        result["key_relocation_summary"]={
            "relocated_keys":mapping["key_switches_relocated"],
            "original_switch_positions_accounted":mapping["total_original_switch_positions_accounted"],
            "native_drc_violations":violations,
            "native_unconnected_items":opens,
            "geometry_model_verified":check["geometry_model_verified"],
            "source_original_assembly_certified":False,
            "fabrication_release":check["fabrication_release"],
        }
        if not check["geometry_model_verified"]:
            raise SystemExit("KiCad replacement-key daughterboard failed native DRC")
    if (args.source_teensy2_footprint is None) != (args.pjrc_pinout_proof_json is None):
        raise SystemExit("PJRC Teensy pinout requires both pinned original footprint and output")
    if args.pjrc_pinout_proof_json and not args.full_matrix_proof_json:
        raise SystemExit("Original firmware/keymap proof must be generated before Teensy pinout audit")
    if args.full_matrix_proof_json or args.independent_source_audit_json:
        required=(
            args.full_matrix_proof_json,args.independent_source_audit_json,
            args.independent_source_dir,args.source_pin_manifest,
            args.key_relocation_out,args.multi_route_json,
            args.postcut_islands_json,args.interposer_out
        )
        if any(x is None for x in required):
            raise SystemExit(
                "Full matrix proof requires original firmware/netlist source, SHA manifest, "
                "cut topology, remounted keys, bridge evidence, and both output paths"
            )
        manifest=json.loads(args.source_pin_manifest.read_text(encoding="utf-8"))
        if manifest.get("original_pcb_source_sha256")!=board["source_sha256"]:
            raise SystemExit("Independent source pin manifest does not match this PCB")
        expected={entry["name"]:entry["sha256"] for entry in manifest["files"]}
        needed=("keyboard.net","config.h","matrix.c","keymap_common.h","keymap.c")
        if not set(needed).issubset(set(expected)):
            raise SystemExit("Independent source pin manifest missing required original netlist/firmware")
        if any(len(value)!=64 for value in expected.values()):
            raise SystemExit("Independent source pin hashes must all be SHA256 identifiers")
        sources={}
        for name in needed:
            file=args.independent_source_dir/name
            if not file.is_file() or file.stat().st_size>200000:
                raise SystemExit("Original upstream netlist or firmware file missing/unbounded: "+name)
            sources[name]=file.read_bytes()
        upstream_audit=audit_independent_source(
            board,*(sources[name] for name in needed),
            expected_hashes={name:expected[name] for name in needed},
        )
        multi=json.loads(args.multi_route_json.read_text(encoding="utf-8"))
        remount=json.loads(
            (args.key_relocation_out/"RELOCATION_MAP.json").read_text(encoding="utf-8")
        )
        remount_receipt=json.loads(
            (args.key_relocation_out/"RELOCATION_VERIFICATION.json").read_text(encoding="utf-8")
        )
        bridge=json.loads(
            (args.interposer_out/"INTERPOSER_CHANNEL_MAP.json").read_text(encoding="utf-8")
        )
        bridge_receipt=json.loads(
            (args.interposer_out/"INTERPOSER_VERIFICATION.json").read_text(encoding="utf-8")
        )
        complete=full_matrix_proof(
            board,chosen_stepped,topology_result,multi,remount,remount_receipt,
            bridge,bridge_receipt,
        )
        if (upstream_audit["pcb_switch_diode_firmware_position_verified"]
                !=complete["original_switch_count"]):
            raise SystemExit("Original schematic/firmware does not cover every tested key")
        if (upstream_audit["firmware_matrix_rows"]!=complete["source_row_count"]
            or upstream_audit["firmware_matrix_columns"]!=complete["source_column_count"]):
            raise SystemExit("Original firmware and physical PCB disagree on scan dimensions")
        original_positions=upstream_audit["original_switch_to_firmware_default_keycode"]
        for link in complete["source_switch_diode_controller_map"]:
            if link["ref"] not in original_positions:
                raise SystemExit("Firmware has no keycode for source switch "+link["ref"])
        args.independent_source_audit_json.parent.mkdir(parents=True,exist_ok=True)
        args.full_matrix_proof_json.parent.mkdir(parents=True,exist_ok=True)
        args.independent_source_audit_json.write_text(
            json.dumps(upstream_audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
        )
        args.full_matrix_proof_json.write_text(
            json.dumps(complete,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
        )
        if args.pjrc_pinout_proof_json:
            footprint_filename="Teensy_20.kicad_mod"
            expected_footprint_sha=expected.get(footprint_filename)
            if not expected_footprint_sha:
                raise SystemExit("Pinned original source manifest lacks Teensy footprint SHA256")
            if (not args.source_teensy2_footprint.is_file() or
                args.source_teensy2_footprint.stat().st_size>25000):
                raise SystemExit("Original Teensy footprint missing/unbounded")
            pinout=audit_teensy2_gpio(
                board,upstream_audit,complete,
                args.source_teensy2_footprint.read_bytes(),
                expected_footprint_sha256=expected_footprint_sha,
            )
            args.pjrc_pinout_proof_json.parent.mkdir(parents=True,exist_ok=True)
            args.pjrc_pinout_proof_json.write_text(
                json.dumps(pinout,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            result["source_controller_pinout_summary"]={
                "original_physical_pads_mapped":pinout["source_original_controller_pads_positionally_verified"],
                "firmware_matrix_GPIOs_mapped":pinout["firmware_total_gpio_assignments_verified"],
                "pinout_proof_sha256":pinout["payload_sha256"],
                "official_reference":pinout["external_PJRC_C_pinout_reference"],
                "physical_controller_tested":False,
            }
        result["full_matrix_summary"]={
            "schematic_connected_nodes_verified":upstream_audit["matched_original_pcb_net_nodes"],
            "firmware_key_positions_verified":upstream_audit["pcb_switch_diode_firmware_position_verified"],
            "original_source_sha256":board["source_sha256"],
            "upstream_audit_sha256":upstream_audit["payload_sha256"],
            "matrix_proof_sha256":complete["payload_sha256"],
            "ideal_press_patterns":complete["total_ideal_press_patterns_tested"],
            "simulated_pattern_failures":complete["mismatched_ideal_patterns"],
            "real_keyboard_function_verified":False,
            "firmware_compiled":False,
            "original_source_kicad_drc_completed":False,
            "release":"PASS_SOURCE_BOUND_IDEAL_MATRIX_ONLY",
        }
    if args.full_junction_out:
        if not all((
            args.full_matrix_proof_json,args.independent_source_audit_json,
            args.postcut_islands_json,args.interposer_out,args.key_relocation_out
        )):
            raise SystemExit("Unified junction requires independent schematic, full keyboard matrix and remount evidence")
        if not args.full_matrix_proof_json.is_file():
            raise SystemExit("Full matrix proof must complete before junction routing")
        junction_helper=REPO/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_harness_bus.py"
        with tempfile.TemporaryDirectory(prefix="hs-junction-source-") as source_tmp:
            pcb_data=Path(source_tmp)/"exact_board.json"
            pcb_data.write_text(json.dumps(board),encoding="utf-8")
            action=subprocess.run([
                args.system_python,str(junction_helper),
                "--source-json",str(pcb_data),
                "--topology-json",str(args.postcut_islands_json.resolve()),
                "--bridge-json",str((args.interposer_out/"INTERPOSER_CHANNEL_MAP.json").resolve()),
                "--remount-json",str((args.key_relocation_out/"RELOCATION_MAP.json").resolve()),
                "--matrix-json",str(args.full_matrix_proof_json.resolve()),
                "--source-audit-json",str(args.independent_source_audit_json.resolve()),
                "--out",str(args.full_junction_out.resolve()),
            ],capture_output=True,text=True,timeout=120,check=False)
            if action.returncode:
                raise SystemExit("Source-bound junction board generation failed: "+action.stderr[-1400:])
        junction=json.loads((args.full_junction_out/"FULL_JUNCTION_WIRING.json").read_text(encoding="utf-8"))
        proof=json.loads(args.full_matrix_proof_json.read_text(encoding="utf-8"))
        if (junction["source_sha256"]!=board["source_sha256"] or
            junction["full_matrix_sha256"]!=proof["payload_sha256"] or
            junction["topology_sha256"]!=topology_result["payload_sha256"] or
            junction["physical_assembly_authorized"] is not False or
            junction["fabrication_release"]!="BLOCKED_SOURCE_REFERENCE_JUNCTION_PREVIEW"):
            raise SystemExit("Junction wrong source, incomplete graph or invalid physical release")
        kicad_cli=shutil.which("kicad-cli")
        if not kicad_cli:
            raise SystemExit("Native KiCad is unavailable for unified junction DRC")
        pcb_path=args.full_junction_out/"keyboard_recovery_junction.kicad_pcb"
        drc_path=args.full_junction_out/"NATIVE_JUNCTION_DRC.json"
        checked=subprocess.run([
            kicad_cli,"pcb","drc","--format","json",
            "--output",str(drc_path.resolve()),str(pcb_path.resolve())
        ],capture_output=True,text=True,timeout=120,check=False)
        if not drc_path.is_file():
            raise SystemExit("KiCad produced no junction DRC evidence")
        drc=json.loads(drc_path.read_text(encoding="utf-8"))
        failures=len(drc.get("violations",[]))
        opens=len(drc.get("unconnected_items",[]))
        ver={
            "schema":"hs.native-full-junction-check.v1",
            "source_sha256":board["source_sha256"],
            "full_matrix_sha256":proof["payload_sha256"],
            "topology_sha256":topology_result["payload_sha256"],
            "pcb_sha256":hashlib.sha256(pcb_path.read_bytes()).hexdigest(),
            "junction_net_groups":junction["unique_source_nets_joined"],
            "donor_source_wires":junction["source_original_pads_with_only_one_wire_each"],
            "remounted_key_port_wires":junction["relocated_key_header_pins"],
            "total_physical_source_wire_assignments":junction["total_junction_board_pins"],
            "native_kicad_drc_exit":checked.returncode,
            "drc_violations":failures,"unconnected_items":opens,
            "native_design_checks_passed":checked.returncode==0 and not failures and not opens,
            "source_original_native_drc_completed":False,
            "physical_harness_verified":False,
            "fabrication_release":"BLOCKED_SOURCE_REFERENCE_JUNCTION_PREVIEW",
        }
        (args.full_junction_out/"JUNCTION_VERIFICATION.json").write_text(
            json.dumps(ver,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        result["full_junction_summary"]={
            "source_sha256":board["source_sha256"],
            "unique_net_groups":junction["unique_source_nets_joined"],
            "donor_source_contacts":junction["source_original_pads_with_only_one_wire_each"],
            "remounted_key_wires":junction["relocated_key_header_pins"],
            "total_junction_pins":junction["total_junction_board_pins"],
            "native_design_checks_passed":ver["native_design_checks_passed"],
            "fabrication_release":ver["fabrication_release"],
        }
        if not ver["native_design_checks_passed"]:
            raise SystemExit("KiCad full junction board failed DRC")
        compact_manifest=None
        compact_verified=None
        if args.compact_junction_out:
            helper=REPO/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_compact_junction.py"
            operation=subprocess.run([
                args.system_python,str(helper),
                "--full-junction-json",
                str((args.full_junction_out/"FULL_JUNCTION_WIRING.json").resolve()),
                "--out",str(args.compact_junction_out.resolve()),
            ],capture_output=True,text=True,check=False,timeout=120)
            if operation.returncode:
                raise SystemExit("Compact IDC junction source-net routing failed: "+operation.stderr[-1200:])
            compact_manifest=json.loads(
                (args.compact_junction_out/"COMPACT_JUNCTION_WIRING.json").read_text(encoding="utf-8")
            )
            if (compact_manifest["source_sha256"]!=board["source_sha256"]
                or compact_manifest["source_original_wiring_assignments"]!=junction["total_junction_board_pins"]
                or compact_manifest["source_junction_original_net_groups"]!=junction["unique_source_nets_joined"]
                or compact_manifest["fabrication_authorized"] is not False
                or compact_manifest["release"]!="BLOCKED_NATIVE_KICAD_COMPACT_IDC_PREVIEW"):
                raise SystemExit("Compact junction revision, topology or authority mismatched")
            compact_pcb=args.compact_junction_out/"compact_idc50_junction.kicad_pcb"
            compact_drc=args.compact_junction_out/"NATIVE_COMPACT_DRC.json"
            checked=subprocess.run([
                kicad_cli,"pcb","drc","--severity-all","--format","json",
                "--output",str(compact_drc.resolve()),str(compact_pcb.resolve())
            ],capture_output=True,text=True,check=False,timeout=120)
            if not compact_drc.is_file():
                raise SystemExit("KiCad did not report compact junction electrical geometry")
            report=json.loads(compact_drc.read_text(encoding="utf-8"))
            errors=len([r for r in report["violations"] if r.get("severity")=="error"])
            warnings=len([r for r in report["violations"] if r.get("severity")=="warning"])
            opens=len(report.get("unconnected_items",[]))
            compact_verified={
                "schema":"hs.native-compact-junction-drc.v1",
                "source_sha256":board["source_sha256"],
                "full_source_junction_model_sha256":junction["full_matrix_sha256"],
                "pcb_sha256":hashlib.sha256(compact_pcb.read_bytes()).hexdigest(),
                "native_kicad_exit":checked.returncode,
                "errors":errors,"warnings":warnings,"unconnected_items":opens,
                "native_drc_passed":checked.returncode==0 and errors==0 and warnings==0 and opens==0,
                "physical_harness_verified":False,
                "fabrication_release":"BLOCKED_NATIVE_KICAD_COMPACT_IDC_PREVIEW",
            }
            (args.compact_junction_out/"COMPACT_JUNCTION_VERIFICATION.json").write_text(
                json.dumps(compact_verified,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
            )
            if not compact_verified["native_drc_passed"]:
                raise SystemExit("Compact source-net IDC PCB did not pass native DRC")
            result["compact_junction_summary"]={
                "source_sha256":board["source_sha256"],
                "original_board_area_mm2":compact_manifest["full_size_junction_area_mm2"],
                "compact_board_area_mm2":compact_manifest["compact_board_area_mm2"],
                "area_reduction_percent":compact_manifest["board_area_reduction_percent"],
                "source_nets":compact_manifest["independent_source_bus_net_count"],
                "donor_contacts":compact_manifest["original_source_donor_contacts"],
                "remounted_key_wires":compact_manifest["original_remounted_key_ports"],
                "native_drc_passed":True,"fabrication_authorized":False,
            }
        if args.machine_project_json is not None:
            previous_handoff=json.loads(
                args.machine_project_json.read_text(encoding="utf-8")
            )
            enriched=extend_keyboard_splice_handoff(
                previous_handoff,
                json.loads(args.independent_source_audit_json.read_text(encoding="utf-8")),
                proof,
                junction,
                ver,
                pinout_proof=(
                    json.loads(args.pjrc_pinout_proof_json.read_text(encoding="utf-8"))
                    if args.pjrc_pinout_proof_json else None
                ),
                legacy_zone_drc_receipt=(
                    json.loads(args.legacy_zone_drc_receipt_json.read_text(encoding="utf-8"))
                    if args.legacy_zone_drc_receipt_json else None
                ),
                compact_junction=compact_manifest,
                compact_junction_verification=compact_verified,
            )
            args.machine_project_json.write_text(
                json.dumps(enriched,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
            )
            result["canonical_machine_release"]=enriched["canonical_summary"]
            result["full_junction_summary"]["canonical_machine_authorized"]=(
                enriched["canonical_summary"]["allowed"]
            )
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
    if args.legacy_zone_drc_receipt_json:
        original_zone_receipt=json.loads(
            args.legacy_zone_drc_receipt_json.read_text(encoding="utf-8")
        )
        verified=verify_legacy_refilled_copy_receipt(
            original_zone_receipt,board["source_sha256"]
        )
        result["source_legacy_zone_drc_summary"]=verified
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
