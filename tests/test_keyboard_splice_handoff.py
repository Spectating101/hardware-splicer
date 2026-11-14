"""HS canonical release cannot be upgraded by external reference geometry."""
from __future__ import annotations

import pytest

from hardware_splicer.keyboard_splice_handoff import build_keyboard_splice_handoff


def data():
    source="a"*64
    cut={"source_file_sha256":source,"release":"BLOCKED_REFERENCE_ONLY",
         "best_scanned_straight_seam":{"x_mm":35.0}}
    topology={"source_sha256":source,"qualified_for_build":False,
              "release":"BLOCKED_REFERENCE_TOPOLOGY_ONLY","cut_x_mm":35.0,
              "candidate_graph_edges":3,"payload_sha256":"b"*64}
    return cut,topology


def test_canonical_release_blocks_even_if_virtual_islands_reconnect():
    cut,topology=data()
    topology["model_replay_achieved_full_restoration"]=True
    handoff=build_keyboard_splice_handoff(cut,topology)
    assessment=handoff["release_assessment"]
    project=handoff["project"]
    assert handoff["physical_authority_granted"] is False
    assert handoff["canonical_summary"]["allowed"] is False
    assert handoff["canonical_summary"]["achieved"]=="design_ready"
    assert {"unresolved_interface","safety_not_closed","verification_not_passed","release_state_not_reached"}.issubset(
        {row["code"] for row in assessment["blockers"]}
    )
    assert project["evidence"][0]["simulated"] is True
    assert project["verifications"][0]["status"]=="blocked"
    assert project["discipline_payloads"]["keyboard_splice"]["fabrication_authorized"] is False


@pytest.mark.parametrize("field,value",[
    ("qualified_for_build",True),
    ("release","AUTHORISED"),
    ("source_sha256","f"*64),
    ("cut_x_mm",27.0),
])
def test_tampered_topology_never_upgrades_to_physical_authority(field,value):
    cut,topology=data()
    topology[field]=value
    with pytest.raises(ValueError):
        build_keyboard_splice_handoff(cut,topology)


def test_cut_release_tampering_never_upgrades_to_physical_authority():
    cut,topology=data()
    cut["release"]="BUILD_READY"
    with pytest.raises(ValueError):
        build_keyboard_splice_handoff(cut,topology)
