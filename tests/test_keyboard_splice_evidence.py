"""Inspect frozen GH60 reference experiment without downloading third-party source."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"examples/arbitrage_lab/keyboard_splice/evidence/gh60_round2"


def _load(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))


def test_real_gh60_virtual_cut_source_and_artifacts_have_same_revision():
    overview=_load("CUT_OVERVIEW.json")
    route=_load("STEPPED_CUT.json")
    topology=_load("POSTCUT_ISLANDS.json")
    handoff=_load("MACHINE_PROJECT_HANDOFF.json")
    manifest=_load("interposer/INTERPOSER_CHANNEL_MAP.json")
    verification=_load("interposer/INTERPOSER_VERIFICATION.json")
    native_drc=_load("interposer/INTERPOSER_NATIVE_DRC.json")
    source="a99aafb9f1ca77c5cac67037d161fa849b9b200de5dec9f63964520af3ff3daf"
    assert source==overview["source_file_sha256"]==route["source_sha256"]==topology["source_sha256"]
    for receipt in [route,topology]:
        signature=receipt["payload_sha256"]
        body={k:v for k,v in receipt.items() if k!="payload_sha256"}
        check=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False,
                                        separators=(",",":")).encode()).hexdigest()
        assert check==signature
    assert topology["cut_path_sha256"]==route["payload_sha256"]
    assert overview["postcut_topology_summary"]["payload_sha256"]==topology["payload_sha256"]
    assert manifest["topology_sha256"]==topology["payload_sha256"]
    assert verification["topology_sha256"]==topology["payload_sha256"]
    pcb=ROOT/"interposer"/"reference_bridge_interposer.kicad_pcb"
    assert hashlib.sha256(pcb.read_bytes()).hexdigest()==verification["pcb_sha256"]
    assert not native_drc["violations"] and not native_drc["unconnected_items"]
    assert verification["native_drc_errors"]==0 and verification["native_unconnected_items"]==0
    assert verification["native_design_checks_passed"] is True
    assert overview["stepped_path_summary"]["physical_cut_authorized"] is False
    assert route["collision_counts"]["pads"]+route["collision_counts"]["switches"]>0
    assert topology["model_replay_remaining_split_components"]>0
    assert topology["model_replay_achieved_full_restoration"] is False
    assert not handoff["physical_authority_granted"]
    assert not handoff["release_assessment"]["requested_state"]=="operationally_authorized"
    assert handoff["release_assessment"]["achieved_state"]=="design_ready"
    assert manifest["fabrication_release"]=="BLOCKED_PREVIEW_ONLY"
    assert manifest["connector_mpn"] is None
