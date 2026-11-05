from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("hs_pc_staged", ROOT / "staged_economics.py")
se = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(se)
SC = se.load_scenarios(ROOT / "scenarios.json")


def handoff_ev(bid, q):
    """PR #286 channel_pilot.batch_unit arithmetic, written out independently."""
    success = 2200 * 0.9 - bid - 600 / 5 - 500 - 150 - 150 - 250
    fail = -bid - 600 / 5 - 200 - 150
    return q * success + (1 - q) * fail


HANDOFF_EQUIV = {
    "labor_rate_twd_per_hr": 60, "lot_size": 5, "transport_total_twd": 600, "disposal_on_fail_twd": 350, "fee_rate": 0.10,
    "outbound_shipping_twd": 0, "return_rate": 0, "return_handling_min": 0, "return_loss_fraction": 0, "sell_through": 1,
    "unsold_markdown": 0, "target_ev_twd": 150, "prior_strength": 4, "policy": "buy_all", "resale_twd": 2200,
    "stages": [{"name": "x", "hands_on_min": 0, "p_pass": 0.5}, {"name": "y", "hands_on_min": 0, "cost_twd": 1050, "p_pass": 1.0}],
}


@pytest.mark.parametrize("q", [0.25, 0.5, 0.65, 0.8])
def test_engine_reproduces_the_handoff_numbers_exactly(q):
    assert se.ev_unit(HANDOFF_EQUIV, 250, ps=[q, 1.0])["ev_twd"] == pytest.approx(handoff_ev(250, q), abs=0.05)


def test_handoff_headline_figures():
    # PR #286 text: -400 at 50%, +560 at 65%, +1520 at 80% per 5-PC batch; max bid NT$212 at 65%.
    for q, batch in ((0.5, -400), (0.65, 560), (0.8, 1520)):
        assert 5 * se.ev_unit(HANDOFF_EQUIV, 250, ps=[q, 1.0])["ev_twd"] == pytest.approx(batch, abs=0.5)
    assert math.floor(se.max_bid(HANDOFF_EQUIV, ps=[0.65, 1.0])) == 212


@pytest.mark.parametrize("name", list(SC))
def test_max_bid_is_the_exact_inverse_of_ev(name):
    s = SC[name]
    b = se.max_bid(s)
    r = se.ev_unit(s, b)
    assert r["ev_twd"] == pytest.approx(s["target_ev_twd"], abs=0.2)
    assert se.ev_unit(s, b + 100)["ev_twd"] < s["target_ev_twd"]


def test_inspecting_each_unit_first_raises_the_ceiling_because_failures_are_never_bought():
    a, b = SC["scrap_lot_buy_all"], SC["scrap_lot_inspect_each"]
    assert se.max_bid(b) > se.max_bid(a)
    assert se.ev_unit(b, 250)["p_unit_is_bought"] == pytest.approx(0.80)
    assert se.ev_unit(a, 250)["p_unit_is_bought"] == 1.0


def test_early_failures_cost_less_than_late_ones():
    s = SC["scrap_lot_buy_all"]
    early = se.ev_unit(s, 250, ps=[0.2, 1, 1, 1, 1])["ev_twd"]
    late = se.ev_unit(s, 250, ps=[1, 1, 1, 0.2, 1])["ev_twd"]
    assert early > late  # same overall pass probability shape, but late failures have already spent the labor


def test_unattended_bench_time_is_not_charged_as_labor():
    s = {**SC["scrap_lot_buy_all"]}
    base = se.ev_unit(s, 250)
    longer = {**s, "stages": [{**st, "unattended_min": st.get("unattended_min", 0) + 600} for st in s["stages"]]}
    again = se.ev_unit(longer, 250)
    assert again["ev_twd"] == base["ev_twd"] and again["unattended_hours_expected"] > base["unattended_hours_expected"]


def test_higher_labor_rate_never_raises_max_bid_and_scrap_class_dies_at_high_rates():
    s = SC["scrap_lot_buy_all"]
    bids = [se.max_bid(s, rate=r) for r in (196, 300, 500)]
    assert bids == sorted(bids, reverse=True) and bids[-1] == 0
    biz = SC["business_8th_gen_inspect_each"]
    assert se.max_bid(biz, rate=500) > 500  # the better class survives a high labor valuation


def test_the_assumed_acer_listing_loses_money_at_its_ask_under_these_inputs():
    s = SC["working_claimed_acer"]
    assert se.ev_unit(s, 2800)["ev_twd"] < 0 < se.max_bid(s)
    assert se.max_bid(s) < 2800


def test_overall_yield_scaling_preserves_the_product():
    s = SC["scrap_lot_buy_all"]
    for q in (0.25, 0.5, 0.8):
        assert math.prod(se.with_overall_yield(s, q)) == pytest.approx(q)


def test_posterior_is_monotone_in_inspection_results_and_conservative_below_mean():
    s = SC["scrap_lot_buy_all"]
    cons = [se.bid_ceiling_after_inspection(s, k, 4)["bid_ceiling_conservative_twd"] for k in range(5)]
    mean = [se.bid_ceiling_after_inspection(s, k, 4)["bid_ceiling_at_mean_twd"] for k in range(5)]
    assert mean == sorted(mean) and cons == sorted(cons)
    assert all(c <= m for c, m in zip(cons, mean))
    assert mean[0] < mean[4]


def test_decision_rule_is_ordered():
    c = {"bid_ceiling_conservative_twd": 100, "bid_ceiling_at_mean_twd": 200}
    assert se.decide(80, c) == "BUY_FIRST_TRANCHE"
    assert se.decide(150, c) == "NEGOTIATE_OR_SMALLER_TRANCHE"
    assert se.decide(250, c) == "PASS"


def test_input_validation():
    s = SC["scrap_lot_buy_all"]
    with pytest.raises(ValueError):
        se.ev_unit(s, -1)
    with pytest.raises(ValueError):
        se.ev_unit(s, 100, ps=[1.2, 1, 1, 1, 1])
    with pytest.raises(ValueError):
        se.ev_unit(s, 100, ps=[1, 1])


def test_every_scenario_input_group_declares_a_basis_and_none_claims_measurement():
    raw = json.loads((ROOT / "scenarios.json").read_text())
    for name, sc in raw["scenarios"].items():
        assert sc["basis"], name
        text = json.dumps(sc["basis"]).lower()
        assert "measured_on_unit" not in text, f"{name}: nothing here is a measurement"
    assert "assumed" in json.dumps(raw["scenarios"]["business_8th_gen_inspect_each"]["basis"])


def test_committed_evidence_matches_a_fresh_run(tmp_path):
    reports = {n: se.scenario_report(n, s) for n, s in SC.items()}
    committed = json.loads((ROOT / "evidence" / "staged_economics.json").read_text())["scenarios"]
    for n in reports:
        assert committed[n]["max_bid_at_prior_twd"] == reports[n]["max_bid_at_prior_twd"]
        assert committed[n]["at_assumed_bid"] == reports[n]["at_assumed_bid"]
