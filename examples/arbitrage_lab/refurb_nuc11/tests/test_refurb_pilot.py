from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
S=ROOT/"refurb_pilot.py"
_spec=importlib.util.spec_from_file_location("hs_refurb_pilot",S)
mod=importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(mod)


def load():
    return json.loads((ROOT/"market_case.json").read_text())


def test_real_case_source_and_no_device_ownership():
    c=load()
    assert c["target"]["url"].startswith("https://www.ruten.com.tw/item/")
    assert c["target"]["acquired"] is False
    assert c["target"]["exact_cpu"] is None
    assert c["target"]["listing_price"]==1470
    assert all(row["source"].startswith("https://") for row in c["parts"])


def test_hypothetical_success_not_equivalent_to_expected_profit():
    r=mod.economics(load(),8000,0.5)
    assert r["net_if_verified_repaired_and_sold_twd"]==1895
    assert r["net_if_diagnosed_irreparable_twd"]==-1930
    assert r["expected_profit_twd"]==-18
    assert r["max_bid_for_target_EV_twd"]==952
    assert 0.5<r["p_break_even_under_scenario"]<0.51


def test_asp_6500_bad_ev_even_75pct_hypothesis():
    r=mod.economics(load(),6500,0.75)
    assert r["net_if_verified_repaired_and_sold_twd"]==545
    assert r["expected_profit_twd"]<0


@pytest.mark.parametrize("badp",[-0.01,1.1])
def test_prob_outside_zero_one_rejected(badp):
    with pytest.raises(ValueError):
        mod.economics(load(),9000,badp)


def test_led_routing_uses_actual_operator_observation_only():
    assert mod.technical_route({})[0]["step"]=="prebid_identity"
    assert mod.technical_route({"power_led_state":"dark"})[0]["step"]=="check_verified_adapter"
    assert mod.technical_route({"power_led_state":"blink"})[0]["step"]=="decode_led"
    assert mod.technical_route({"power_led_state":"solid_no_video"})[0]["step"]=="diagnose_post"
    assert mod.technical_route({"power_led_state":"solid_and_posts"})[0]["step"]=="functional_validation"


def test_seller_claims_cannot_grant_repair_or_transaction_authority(monkeypatch):
    monkeypatch.setattr(mod,"hs_existing_authority",lambda case:{"authority_available":False})
    result=mod.run(load(),{})
    assert result["decision"]=="DO_NOT_BUY_UNVERIFIED_UNIT"
    assert result["released_as_functional"] is False
    assert result["actual_acquired"] is False
    assert len(result["bench_missing_gates"])==len(mod.OBSERVED_GATES)
    assert "NONE" in result["physical_proof"]


def test_unverified_claims_without_evidence_are_not_passes(monkeypatch):
    monkeypatch.setattr(mod,"hs_existing_authority",lambda case:{"authority_available":False})
    observations={key:{"pass":True,"evidence_path":"does-not-exist.png"} for key in mod.OBSERVED_GATES}
    r=mod.run(load(),observations)
    assert len(r["bench_missing_gates"])==len(mod.OBSERVED_GATES)
    assert not r["released_as_functional"]


def test_even_all_claimed_passes_cannot_make_unowned_unit_repaired(monkeypatch):
    monkeypatch.setattr(mod,"hs_existing_authority",lambda case:{"authority_available":False})
    # Even if a local claimant supplied files, an unacquired unit is not refurbished.
    f=ROOT/"evidence"/"test_operator_bench_photo.txt"
    f.write_text("synthetic test fixture, not real evidence")
    try:
        obs={key:{"pass":True,"evidence_path":"evidence/test_operator_bench_photo.txt"} for key in mod.OBSERVED_GATES}
        c=load();c["target"]["exact_cpu"]="i5"
        r=mod.run(c,obs)
        assert r["released_as_functional"] is False
        assert r["actual_acquired"] is False
    finally:
        f.unlink(missing_ok=True)


def test_even_pretended_acquisition_and_files_cannot_authorize_physical_release(monkeypatch):
    monkeypatch.setattr(mod,"hs_existing_authority",lambda case:{"authority_available":False})
    f=ROOT/"evidence"/"fixture.txt"
    f.write_text("UNTRUSTED OPERATOR-SUPPLIED FIXTURE")
    try:
        c=load()
        c["target"]["acquired"]=True
        c["target"]["exact_cpu"]="i5"
        obs={key:{"pass":True,"evidence_path":"evidence/fixture.txt"} for key in mod.OBSERVED_GATES}
        report=mod.run(c,obs)
        assert report["operator_reported_bench_complete"] is True
        assert report["released_as_functional"] is False
    finally:
        f.unlink(missing_ok=True)


def test_seller_variant_i5_only_requires_physical_evidence(monkeypatch):
    monkeypatch.setattr(mod,"hs_existing_authority",lambda case:{"authority_available":False})
    c=load();c["target"]["exact_cpu"]="i5"
    r=mod.run(c,{})
    assert r["decision"]=="DO_NOT_BUY_UNVERIFIED_UNIT"


def test_public_artifact_has_no_fake_bench_metrics():
    obs=json.loads((ROOT/"bench_observations.template.json").read_text())
    for gate in mod.OBSERVED_GATES:
        assert obs[gate] is None
    assert obs["power_led_state"] is None
