"""Native KiCad prototype interposer from modeled post-cut bridge edges.

This produces a 2.54-mm paired-pin pass-through board, not a verified donor
connector, FPC harness, wiring instruction, or manufacturing release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import pcbnew as p

PITCH_MM = 2.54
BOARD_WIDTH_MM = 40.64
CONNECTOR_X_MM = (8.89, 31.75)
PAD_DIAMETER_MM = 1.7
HOLE_DIAMETER_MM = 0.9
TRACE_WIDTH_MM = 0.5


def _point(x: float, y: float):
    return p.VECTOR2I(p.FromMM(float(x)), p.FromMM(float(y)))


def _sha(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def _validate(result: dict):
    source = result.get("source_sha256")
    if not isinstance(source, str) or not re.fullmatch(r"[a-f0-9]{64}", source):
        raise ValueError("missing exact source SHA256")
    receipt = result.get("payload_sha256")
    payload = {k: v for k, v in result.items() if k != "payload_sha256"}
    if not receipt or _sha(payload) != receipt:
        raise ValueError("model receipt digest mismatch")
    if result.get("qualified_for_build") is not False:
        raise ValueError("virtual copper does not grant physical authority")
    if result.get("release") != "BLOCKED_REFERENCE_TOPOLOGY_ONLY":
        raise ValueError("unrecognized copper model release state")
    edges = result.get("bridge_edges", [])
    if not edges or len(edges) > 40:
        raise ValueError("1 to 40 paired channels required")
    seen = set()
    for index, edge in enumerate(edges):
        if edge.get("status") != "PROPOSED_MODEL_ONLY_NOT_A_WIRING_AUTHORIZATION":
            raise ValueError("unapproved bridge edge at channel " + str(index))
        a = edge.get("from_candidate_contact") or edge.get("from_candidate_pad")
        b = edge.get("to_candidate_contact") or edge.get("to_candidate_pad")
        if not isinstance(a, dict) or not isinstance(b, dict):
            raise ValueError("unanchored bridge")
        if a.get("net") != edge.get("net") or b.get("net") != edge.get("net"):
            raise ValueError("cross-net bridge candidate")
        for contact in (a, b):
            kind = contact.get("contact_type", "existing_pad")
            if kind not in ("existing_pad", "via_annulus", "trace_exposure"):
                raise ValueError("unqualified contact method")
            if not contact.get("ref") or not contact.get("pad"):
                raise ValueError("missing source contact identity")
            if kind == "trace_exposure":
                if (float(contact.get("exposure_length_mm") or 0) < 2.0 or
                    float(contact.get("conductor_width_mm") or 0) < 0.35):
                    raise ValueError("track exposure too small for modeled repair")
            if kind == "via_annulus" and not str(contact["ref"]).startswith("VIA"):
                raise ValueError("missing source via identity")
        key = (edge.get("from_island"), edge.get("to_island"))
        if not all(key) or key in seen:
            raise ValueError("duplicated or unidentified island edge")
        seen.add(key)
    return source, edges


def make_interposer(result: dict, output_dir: Path) -> dict:
    source, edges = _validate(result)
    output_dir.mkdir(parents=True, exist_ok=True)
    board = p.BOARD()
    count = len(edges)
    first_y = 8.89
    height = first_y + PITCH_MM * (count - 1) + 8.89
    nets = []
    for index in range(count):
        # Separate channels do NOT short repeated donor net names together.
        net = p.NETINFO_ITEM(board, "CH_" + str(index + 1).zfill(2))
        board.Add(net)
        nets.append(net)

    def connector(ref, x):
        library = Path("/usr/share/kicad/footprints/Connector_PinHeader_2.54mm.pretty")
        footprint_name = f"PinHeader_1x{count:02d}_P2.54mm_Vertical"
        if not (library / (footprint_name + ".kicad_mod")).is_file():
            raise ValueError("Exact KiCad header footprint unavailable: " + footprint_name)
        fp = p.FootprintLoad(str(library), footprint_name)
        if fp is None:
            raise ValueError("Native KiCad failed to load header: " + footprint_name)
        fp.SetReference(ref)
        fp.SetValue(footprint_name)
        fp.SetPosition(_point(x, first_y))
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        board.Add(fp)
        pads = {int(pad.GetNumber()): pad for pad in fp.Pads()}
        if set(pads) != set(range(1, count + 1)):
            raise ValueError("Vendor footprint pin numbering does not match bridge")
        for index, net in enumerate(nets):
            pads[index + 1].SetNet(net)

    connector("J1", CONNECTOR_X_MM[0])
    connector("J2", CONNECTOR_X_MM[1])

    for index, net in enumerate(nets):
        y = first_y + index * PITCH_MM
        track = p.PCB_TRACK(board)
        track.SetStart(_point(CONNECTOR_X_MM[0], y))
        track.SetEnd(_point(CONNECTOR_X_MM[1], y))
        track.SetWidth(p.FromMM(TRACE_WIDTH_MM))
        track.SetLayer(p.F_Cu)
        track.SetNet(net)
        board.Add(track)

    corners = [(0, 0), (BOARD_WIDTH_MM, 0), (BOARD_WIDTH_MM, height), (0, height)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        edge = p.PCB_SHAPE(board)
        edge.SetShape(p.SHAPE_T_SEGMENT)
        edge.SetStart(_point(*a))
        edge.SetEnd(_point(*b))
        edge.SetLayer(p.Edge_Cuts)
        edge.SetWidth(p.FromMM(0.05))
        board.Add(edge)

    output = output_dir / "reference_bridge_interposer.kicad_pcb"
    p.SaveBoard(str(output), board)
    channels = []
    for index, edge in enumerate(edges, 1):
        channels.append({
            "channel": index, "pcb_net": "CH_" + str(index).zfill(2),
            "J1_pad": index, "J2_pad": index,
            "source_net": edge["net"],
            "from_model_island": edge["from_island"],
            "to_model_island": edge["to_island"],
            "from_candidate_contact": edge.get("from_candidate_contact") or edge["from_candidate_pad"],
            "to_candidate_contact": edge.get("to_candidate_contact") or edge["to_candidate_pad"],
            "status": "UNVERIFIED_DONOR_SOLDER_LOCATION",
        })
    manifest = {
        "schema": "hs.keyboard-splice-interposer-preview.v1",
        "source_reference_sha256": source,
        "topology_sha256": result["payload_sha256"],
        "physical_authority_granted": False,
        "fabrication_release": "BLOCKED_PREVIEW_ONLY",
        "actual_donor_reworked": False,
        "remaining_disconnected_groups": result["model_replay_remaining_split_components"],
        "remaining_required_groups": result.get(
            "model_replay_remaining_required_components",
            result["model_replay_remaining_split_components"]
        ),
        "inert_remnants_to_isolate": result.get("planned_inert_track_remnants", 0),
        "preexisting_terminal_net_gaps": result.get("preexisting_unconnected_terminal_net_count", 0),
        "unanchored_groups": result["unanchored_split_components"],
        "channel_count": count,
        "board_width_mm": BOARD_WIDTH_MM,
        "board_height_mm": round(height, 3),
        "pin_pitch_mm": PITCH_MM,
        "connector_mpn": None,
        "connector_mating_verified": False,
        "cable_pinout_verified": False,
        "strain_relief_verified": False,
        "assembly_bom_complete": False,
        "drc_success_is_not_build_authorization": True,
        "channel_mapping": channels,
    }
    (output_dir / "INTERPOSER_CHANNEL_MAP.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topology-json", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    topology = json.loads(args.topology_json.read_text(encoding="utf-8"))
    result = make_interposer(topology, args.out)
    print("KICAD_INTERPOSER", args.out / "reference_bridge_interposer.kicad_pcb")
    print("MODELED_CHANNELS", result["channel_count"])
    print("FABRICATION_RELEASE", result["fabrication_release"])


if __name__ == "__main__":
    main()
