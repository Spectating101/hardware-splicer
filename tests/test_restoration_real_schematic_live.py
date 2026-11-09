"""Frozen, genuine KiCad + Gemini A/B receipt verification."""
import importlib.util
import json
from pathlib import Path

import pytest

from hardware_splicer.restoration_reasoning_agent import sha

HERE=Path(__file__).resolve().parents[1]/"examples/restoration_video_bench/real_schematic"
spec=importlib.util.spec_from_file_location("audit_dmg",HERE/"inspect_dmg_model_ab.py")
# Import sibling script as a module without requiring an installed package.
import sys
sys.path.insert(0,str(HERE))
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

def test_real_schematic_pilot_a_b_is_frozen_and_source_identical():
    p=HERE/"real_dmg_kicad_model_ab.json"
    report=json.loads(p.read_text())
    summary=audit.inspect(report)
    assert summary["same_initial_evidence"] is True
    assert summary["board_variant_match_not_physically_verified"] is True
    assert summary["creator_repair_accuracy_not_scored"] is True
    assert summary["real_source_pinned"]=="032eb9c2578125b157ab88048113b2d52663b819"
    for x in summary["results"].values():
        assert x["status"]=="proposed_unverified_differential"
        assert x["actual_pinout_verified_against_target"] is False
    assert summary==json.loads((HERE/"real_dmg_kicad_no_gold_audit.json").read_text())

def test_real_schematic_model_hypothesis_cites_known_pinned_net_only():
    a=json.loads((HERE/"real_dmg_kicad_model_ab.json").read_text())
    model=a["arms"]["hs_real_kicad"]["plan"]["hypotheses"][0]
    assert "BT1" in model["mechanism"]
    assert "DC1" in model["mechanism"]
    assert "/Power/BT+" in model["mechanism"]
    assert a["tool_result"]["status"]=="reference_netlist_available_reported_revision_match_only"
    assert all(x["reference_circuit_only"] is True for x in a["tool_result"]["candidate_battery_nets"])
    assert "no_inferred_conduction_through_components" in a["tool_result"]
    assert a["tool_result"]["no_inferred_conduction_through_components"] is True

def test_prior_receipt_tamper_is_detected(tmp_path):
    report=json.loads((HERE/"real_dmg_kicad_model_ab.json").read_text())
    report["arms"]["hs_real_kicad"]["plan"]["hypotheses"][0]["mechanism"]="manually changed"
    with pytest.raises(ValueError,match="response was modified"):
        audit.inspect(report)

def test_missing_graph_data_cannot_appear_in_plain_arm():
    report=json.loads((HERE/"real_dmg_kicad_model_ab.json").read_text())
    plain=report["arms"]["plain"]
    ref=report["arms"]["hs_real_kicad"]
    assert "real_schematic_tool_result_sha256" not in plain
    assert ref["real_schematic_tool_result_sha256"]==sha(report["tool_result"])
    assert ref["target_board_physically_verified"] is False
    assert plain["evidence_sha256"]==ref["evidence_sha256"]
