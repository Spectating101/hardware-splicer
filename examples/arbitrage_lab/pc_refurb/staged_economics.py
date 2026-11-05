"""Staged-triage economics for a used-PC lot. One model, replacing three copies.

``refurb_nuc11``, ``channel_20261105.batch_unit`` and ``whole_working_control`` each
hand-wrote the same buy -> test -> sell expected-value formula and priced a failed
unit at zero salvage. This module keeps the same honest boundary (every number is a
labelled input, nothing is a measurement) but adds what actually moves profit:

* Sequential stages. A unit that dies at stage k has only paid for stages 1..k.
  Cheap gates first is the main conversion lever.
* Hands-on vs unattended time. Memtest/burn-in occupy a bench slot, not the operator,
  so profit per *hands-on hour* is the number that ranks projects.
* Expected returns cost, sell-through and markdown, instead of flat "reserves".
* A Bayesian pre-purchase inspection rule: inspect n units, see k pass, and get a
  bid ceiling at a conservative percentile of the posterior, not at the prior mean.
* Max bid is solved, not assumed: EV is linear in the bid (every unit is paid for).

All outputs are conditional on the inputs in ``scenarios.json``. Each input carries a
``basis`` tag (public_source | handoff_assumed | assumed | measured_on_unit) so no
assumption can pass for evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIN_WAGE_TWD_PER_HR_2026 = 196  # public: Taiwan Ministry of Labor, effective 2026-01-01 (a floor, not your opportunity cost)


def _bought_at(s: dict) -> int:
    """Index of the first stage that happens AFTER purchase.

    buy_all: 0 (every unit is paid for). inspect_each: after the last ``pre_purchase`` stage,
    so a unit that fails inspection is never bought and costs only the inspection labor."""
    if s.get("policy", "buy_all") != "inspect_each":
        return 0
    idx = [i for i, st in enumerate(s["stages"]) if st.get("pre_purchase")]
    return (idx[-1] + 1) if idx else 0


def ev_unit(s: dict, bid: float, rate: float | None = None, ps: list[float] | None = None) -> dict:
    """Expected net TWD for ONE candidate unit offered at `bid`, plus time and probability facts."""
    rate = s["labor_rate_twd_per_hr"] if rate is None else rate
    stages = s["stages"]
    ps = ps if ps is not None else [st["p_pass"] for st in stages]
    if len(ps) != len(stages) or any(not 0 <= p <= 1 for p in ps):
        raise ValueError("stage probabilities must be 0..1, one per stage")
    if bid < 0:
        raise ValueError("bid cannot be negative")
    paid = bid + s["transport_total_twd"] / s["lot_size"] + s.get("inbound_shipping_twd", 0)
    bought_at = _bought_at(s)
    reach, ev, hands, unatt = 1.0, 0.0, 0.0, 0.0
    p_bought = 1.0
    for i, (st, p) in enumerate(zip(stages, ps)):
        if i == bought_at:
            ev -= reach * paid
            p_bought = reach
        ev -= reach * (st["hands_on_min"] / 60 * rate + st.get("cost_twd", 0))
        hands += reach * st["hands_on_min"] / 60
        unatt += reach * st.get("unattended_min", 0) / 60
        if i >= bought_at:  # a unit that fails before purchase is simply not bought
            ev += reach * (1 - p) * (st.get("fail_partout_twd", 0) - s["disposal_on_fail_twd"])
        reach *= p
    sell = s["sell_through"]
    resale = s["resale_twd"] * (sell + (1 - sell) * (1 - s["unsold_markdown"]))
    returns = s["return_rate"] * (2 * s["outbound_shipping_twd"] + s["return_handling_min"] / 60 * rate
                                  + s["return_loss_fraction"] * s["resale_twd"])
    net_success = resale * (1 - s["fee_rate"]) - s["outbound_shipping_twd"] - returns
    ev += reach * net_success
    return {"ev_twd": round(ev, 1), "p_success_overall": round(reach, 4), "p_unit_is_bought": round(p_bought, 4),
            "net_per_success_before_acq_twd": round(net_success, 1),
            "hands_on_hours_expected": round(hands, 2), "unattended_hours_expected": round(unatt, 2),
            "ev_per_hands_on_hour_twd": round(ev / hands, 1) if hands else None}


def max_bid(s: dict, target_ev: float | None = None, rate: float | None = None, ps: list[float] | None = None) -> float:
    """EV(bid) = EV(0) - p_bought * bid (exact: the bid is paid only on bought units)."""
    t = s["target_ev_twd"] if target_ev is None else target_ev
    r0 = ev_unit(s, 0, rate, ps)
    return max(0.0, (r0["ev_twd"] - t) / r0["p_unit_is_bought"])


def with_overall_yield(s: dict, q: float) -> list[float]:
    """Stage probabilities scaled (equal exponent) so their product equals q."""
    base = [st["p_pass"] for st in s["stages"]]
    Q = math.prod(base)
    if not 0 < q <= 1 or Q <= 0:
        raise ValueError("overall yield must be in (0,1]")
    if Q >= 1:
        if q < 1:
            raise ValueError("every stage is certain (p=1): an equal-exponent rescale cannot reach a lower overall yield")
        return base
    return [p ** (math.log(q) / math.log(Q)) for p in base]


# ------------------------------------------------------------ Bayesian inspection
def _beta(p: float, strength: float, passes: int = 0, trials: int = 0) -> tuple[float, float]:
    p = min(max(p, 1e-3), 1 - 1e-3)
    return p * strength + passes, (1 - p) * strength + (trials - passes)


def _draw_stage_ps(s: dict, inspected: dict | None, n: int, seed: int):
    """Yield n stage-probability vectors, each stage ~ Beta(prior) updated by `inspected`={stage: (passes, trials)}."""
    rng, inspected = random.Random(seed), inspected or {}
    for _ in range(n):
        ps = []
        for st in s["stages"]:
            a, b = _beta(st["p_pass"], st.get("prior_strength", s["prior_strength"]), *inspected.get(st["name"], (0, 0)))
            ps.append(rng.betavariate(a, b))
        yield ps


def ev_draws(s: dict, bid: float, inspected: dict | None = None, n: int = 20000, seed: int = 20261105,
             rate: float | None = None) -> list[float]:
    """Posterior draws of the expected net TWD per candidate unit at a fixed `bid`."""
    return [ev_unit(s, bid, rate, ps)["ev_twd"] for ps in _draw_stage_ps(s, inspected, n, seed)]


def ceiling_draws(s: dict, inspected: dict | None = None, n: int = 20000, seed: int = 20261105,
                  rate: float | None = None) -> list[float]:
    """Posterior draws of the bid ceiling for the target EV. Each draw uses its OWN purchase probability
    (it differs per draw under inspect_each): ceiling = (EV(0) - target) / p_bought."""
    t, out = s["target_ev_twd"], []
    for ps in _draw_stage_ps(s, inspected, n, seed):
        r0 = ev_unit(s, 0, rate, ps)
        out.append((r0["ev_twd"] - t) / r0["p_unit_is_bought"])
    return out


def pct(v: list[float], q: float) -> float:
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


def bid_ceiling_after_inspection(s: dict, passes: int, trials: int, conservative_pct: float = 0.20,
                                 rate: float | None = None) -> dict:
    """Pre-purchase rule. Only stages flagged ``pre_purchase`` can be observed before buying."""
    pre = [st["name"] for st in s["stages"] if st.get("pre_purchase")]
    obs = {name: (passes, trials) for name in pre} if trials else {}
    draws = ceiling_draws(s, obs, rate=rate)
    return {"inspected": trials, "passed_pre_purchase": passes,
            "bid_ceiling_conservative_twd": max(0, math.floor(pct(draws, conservative_pct))),
            "bid_ceiling_at_mean_twd": max(0, math.floor(sum(draws) / len(draws))),
            "conservative_percentile": conservative_pct}


def decide(quoted: float, ceilings: dict) -> str:
    if quoted <= ceilings["bid_ceiling_conservative_twd"]:
        return "BUY_FIRST_TRANCHE"
    if quoted <= ceilings["bid_ceiling_at_mean_twd"]:
        return "NEGOTIATE_OR_SMALLER_TRANCHE"
    return "PASS"


# ------------------------------------------------------------ report
def scenario_report(name: str, s: dict) -> dict:
    base = ev_unit(s, s.get("assumed_bid_twd", 0))
    ceilings = max_bid(s)
    yields = {}
    for q in (0.25, 0.5, 0.65, 0.8):
        try:
            ps = with_overall_yield(s, q)
        except ValueError:
            continue
        yields[str(q)] = {"max_bid_twd": math.floor(max_bid(s, ps=ps)), **ev_unit(s, s.get("assumed_bid_twd", 0), ps=ps)}
    rates = {str(r): {"ev_per_unit_at_assumed_bid_twd": ev_unit(s, s.get("assumed_bid_twd", 0), rate=r)["ev_twd"],
                      "max_bid_twd": math.floor(max_bid(s, rate=r))} for r in (MIN_WAGE_TWD_PER_HR_2026, 300, 500)}
    resale = {}
    for f in (0.7, 0.85, 1.0, 1.15):
        s2 = {**s, "resale_twd": round(s["resale_twd"] * f)}
        resale[str(f)] = {"resale_twd": s2["resale_twd"], "max_bid_twd": math.floor(max_bid(s2))}
    table = []
    for trials in ((0, 3, 4) if s.get("policy", "buy_all") == "buy_all" else ()):
        for passes in range(trials, -1, -1) if trials else [0]:
            c = bid_ceiling_after_inspection(s, passes, trials)
            table.append(c)
    return {"scenario": name, "description": s["description"], "inputs_basis": s["basis"],
            "bid_assumed_twd": s.get("assumed_bid_twd"), "at_assumed_bid": base,
            "max_bid_at_prior_twd": math.floor(ceilings), "sensitivity_overall_yield": yields,
            "sensitivity_labor_rate": rates, "sensitivity_resale_price": resale,
            "inspection_walkaway_table": table,
            "claim_boundary": "Conditional on labelled inputs; no seller has quoted, no unit is acquired, yields are priors not measurements."}


def load_scenarios(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    d = raw["defaults"]
    out = {}
    for name, sc in raw["scenarios"].items():
        merged = {**d, **{k: v for k, v in sc.items() if k != "stages"}}
        merged["stages"] = sc.get("stages") or d["stages"]
        if "stage_overrides" in sc:
            merged["stages"] = [{**st, **sc["stage_overrides"].get(st["name"], {})} for st in merged["stages"]]
        out[name] = merged
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=Path, default=HERE / "scenarios.json")
    ap.add_argument("--out", type=Path, default=HERE / "evidence")
    a = ap.parse_args()
    reports = {n: scenario_report(n, s) for n, s in load_scenarios(a.scenarios).items()}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "staged_economics.json").write_text(json.dumps(
        {"schema": "hs.pc_staged_economics.v1", "labor_floor_basis": "Taiwan 2026 minimum wage NT$196/h (public)",
         "scenarios": reports}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (a.out / "inspection_walkaway.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["scenario", "inspected", "passed", "bid_ceiling_conservative_twd", "bid_ceiling_at_mean_twd"])
        for n, r in reports.items():
            for t in r["inspection_walkaway_table"]:
                w.writerow([n, t["inspected"], t["passed_pre_purchase"], t["bid_ceiling_conservative_twd"], t["bid_ceiling_at_mean_twd"]])
    for n, r in reports.items():
        b = r["at_assumed_bid"]
        print(f"{n}: max_bid@prior={r['max_bid_at_prior_twd']}  EV@bid{r['bid_assumed_twd']}={b['ev_twd']}  "
              f"P(success)={b['p_success_overall']}  hands={b['hands_on_hours_expected']}h  EV/h={b['ev_per_hands_on_hour_twd']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
