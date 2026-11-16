"""Iterate through repair strategies until required electrical topology reconnects.

The loop never upgrades physical or manufacturing release. It only expands
candidate contact methods on actual surviving source copper and may isolate
bounded, terminal-free track remnants rather than reconnecting dead copper.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


MODES = ("pad_only", "adaptive", "adaptive_functional")


def verify_receipt(topology: dict, *, source_sha: str, net_count: int,
                   seam_x: float, path_sha: str | None) -> None:
    receipt = topology.get("payload_sha256")
    body = {k: v for k, v in topology.items() if k != "payload_sha256"}
    content = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    if receipt != hashlib.sha256(content.encode()).hexdigest():
        raise ValueError("tampered copper-island topology receipt")
    if topology.get("source_sha256") != source_sha or topology.get("target_net_count") != net_count:
        raise ValueError("source copper revision/net inventory differs")
    if topology.get("cut_x_mm") != seam_x or topology.get("cut_path_sha256") != path_sha:
        raise ValueError("repair iteration substituted the cut path")
    if topology.get("qualified_for_build") is not False or topology.get("release") != "BLOCKED_REFERENCE_TOPOLOGY_ONLY":
        raise ValueError("topology iteration attempted to upgrade fabrication authority")


def _candidate_mix(t: dict) -> dict[str, int]:
    counter = Counter()
    for edge in t["bridge_edges"]:
        for key in ("from_candidate_contact", "to_candidate_contact"):
            contact = edge.get(key)
            if contact:
                counter[contact["contact_type"]] += 1
    return dict(sorted(counter.items()))


def run_repair_loop(*, script: Path, interpreter: str, source_board: dict,
                    net_names: list[str], seam_x: float, kerf_mm: float,
                    path_file: Path | None, topology_file: Path,
                    edge_csv: Path | None = None,
                    repair_mode: str = "auto") -> dict:
    if repair_mode != "auto" and repair_mode not in MODES:
        raise ValueError("unsupported repair strategy")
    if not net_names:
        raise ValueError("empty source net inventory")
    expected_sha = source_board["source_sha256"]
    path_sha = None
    if path_file:
        path = json.loads(path_file.read_text(encoding="utf-8"))
        path_sha = path["payload_sha256"]
    sequence = MODES if repair_mode == "auto" else (repair_mode,)
    history = []
    with tempfile.TemporaryDirectory(prefix="hs-copper-repair-") as folder:
        tmp = Path(folder)
        (tmp / "board.json").write_text(json.dumps(source_board), encoding="utf-8")
        (tmp / "nets.json").write_text(json.dumps(net_names), encoding="utf-8")
        chosen = None
        selected_json = None
        selected_csv = None
        for mode in sequence:
            result_file = tmp / (mode + ".json")
            candidate_csv = tmp / (mode + ".csv")
            cmd = [
                interpreter, str(script), "--board-json", str(tmp / "board.json"),
                "--net-inventory-json", str(tmp / "nets.json"),
                "--cut-x-mm", str(seam_x), "--kerf-mm", str(kerf_mm),
                "--repair-mode", mode,
                "--output", str(result_file),
                "--bridge-csv", str(candidate_csv),
            ]
            if path_file:
                cmd.extend(["--cut-path-json", str(path_file.resolve())])
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
            if proc.returncode:
                raise ValueError(f"native copper restoration stage {mode} failed: {proc.stderr[-1300:]}")
            topology = json.loads(result_file.read_text(encoding="utf-8"))
            verify_receipt(topology, source_sha=expected_sha, net_count=len(net_names),
                           seam_x=seam_x, path_sha=path_sha)
            required = topology["model_replay_remaining_required_components"]
            complete_model = required == 0 and topology["damaged_electrical_pad_count"] == 0
            history.append({
                "strategy": mode,
                "source_sha256": expected_sha,
                "topology_sha256": topology["payload_sha256"],
                "bridge_channels": topology["candidate_graph_edges"],
                "strict_unconnected_groups": topology["model_replay_remaining_split_components"],
                "unconnected_required_groups": required,
                "isolated_terminal_free_remnants": topology["planned_inert_track_remnants"],
                "damaged_electrical_pads": topology["damaged_electrical_pad_count"],
                "preexisting_source_terminal_net_gaps": topology["preexisting_unconnected_terminal_net_count"],
                "contact_kinds": _candidate_mix(topology),
                "required_graph_connected_in_model": complete_model,
            })
            chosen = topology
            selected_json = result_file
            selected_csv = candidate_csv
            if complete_model:
                break
        if chosen is None:
            raise RuntimeError("no restoration stages executed")
        topology_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(selected_json, topology_file)
        if edge_csv:
            edge_csv.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(selected_csv, edge_csv)
    fully_recovered = (
        chosen["model_replay_remaining_required_components"] == 0
        and chosen["damaged_electrical_pad_count"] == 0
    )
    return {
        "schema": "hs.keyboard-copper-repair-loop.v1",
        "source_sha256": expected_sha,
        "cut_path_sha256": path_sha,
        "selected_strategy": history[-1]["strategy"],
        "iterations": history,
        "total_iterations": len(history),
        "required_graph_connected_in_model": fully_recovered,
        "unresolved_source_baseline_terminal_net_gaps": chosen["preexisting_unconnected_terminal_net_count"],
        "verified_original_keyboard_firmware_function": False,
        "physical_authority_granted": False,
        "fabrication_release": "BLOCKED_REFERENCE_ONLY",
        "result": (
            "MODELED_POSTCUT_REQUIRED_GRAPH_RESTORED_WITH_REMNANT_ISOLATION"
            if fully_recovered else "POSTCUT_REQUIRED_GRAPH_STILL_DISCONNECTED"
        ),
    }
